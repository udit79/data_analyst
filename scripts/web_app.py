"""Local web API that connects the Pivot frontend to the local analysis agent."""

from __future__ import annotations

import base64
import json
import os
import shutil
import subprocess
import threading
import uuid
from io import StringIO
from pathlib import Path
from typing import Any
from urllib.parse import quote

import pandas as pd
from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool

load_dotenv()

from scripts.data_policy import DataClassification, ensure_hosted_upload_allowed
from scripts.data_tools import CHART_MANIFEST_PATH, _compact_profile, _profile
from scripts.docker_sandbox import DockerSandbox
from scripts.local_agent import create_local_agent
from scripts.main import _write_artifacts

# Load project imports first: some of them load the .env file. LangChain's
# LangGraph callback uses project/session routing, which LangSmith disallows in
# the same run as an AgentAddress. Route the local app into one named project.
if os.getenv("LANGSMITH_AGENT_ID"):
    import langsmith

    _trace_project = os.getenv("LANGSMITH_PROJECT") or "Pivot"
    os.environ.pop("LANGSMITH_AGENT_ID", None)
    os.environ.pop("LANGSMITH_AGENT_ENVIRONMENT", None)
    os.environ["LANGCHAIN_PROJECT"] = _trace_project
    langsmith.configure(project_name=_trace_project, address=None)

MAX_UPLOAD_BYTES = 25 * 1024 * 1024
OUTPUT_ROOT = Path("artifacts/web").resolve()
app = FastAPI(title="Pivot Data Agent API", version="1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4173", "http://127.0.0.1:4173"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

_analyses: dict[str, dict[str, Any]] = {}
_sessions: dict[str, tuple[Any, DockerSandbox]] = {}
_lock = threading.RLock()


def _local_artifacts(backend: DockerSandbox, output_dir: Path) -> list[Path]:
    required = [
        "/workspace/artifacts/cleaned_data.csv",
        "/workspace/artifacts/transformation_log.json",
        "/workspace/artifacts/analysis_profile.json",
        "/workspace/artifacts/analysis_report.md",
        "/workspace/artifacts/analysis_dashboard.html",
        CHART_MANIFEST_PATH,
    ]
    manifest_download = backend.download_files([CHART_MANIFEST_PATH])[0]
    if manifest_download.error or manifest_download.content is None:
        raise RuntimeError("The sandbox did not return its chart manifest")
    manifest = json.loads(manifest_download.content)
    required.extend(
        chart["path"]
        for chart in manifest.get("charts", [])
        if chart.get("status") == "generated"
    )
    downloaded = backend.download_files(required)
    items = []
    for remote_path, response in zip(required, downloaded, strict=True):
        if response.error or response.content is None:
            raise RuntimeError(
                f"Could not retrieve analysis artifact {remote_path}: {response.error}"
            )
        relative = remote_path.removeprefix("/workspace/")
        items.append(
            {
                "path": relative,
                "content_base64": base64.b64encode(response.content).decode("ascii"),
            }
        )
    return _write_artifacts(json.dumps({"artifacts": items}), output_dir)


def _artifact_result(
    analysis_id: str, output_dir: Path, row_count: int
) -> dict[str, Any]:
    artifact_dir = output_dir / "artifacts"
    profile_path = artifact_dir / "analysis_profile.json"
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    after = profile["after"]
    before_columns = profile["before"]["columns"]
    columns = after["columns"]
    missing = sum(column["missing_count"] for column in before_columns.values())
    names = sorted(
        path.relative_to(artifact_dir).as_posix()
        for path in artifact_dir.rglob("*")
        if path.is_file()
    )
    urls = {
        name: f"/api/analyses/{analysis_id}/artifacts/{quote(name, safe='/')}"
        for name in names
        if name not in {"chart_manifest.json", "chart_requests.json"}
    }
    dashboard_name = "analysis_dashboard.html"
    if dashboard_name not in urls:
        raise RuntimeError("The hosted analysis did not return its dashboard")
    return {
        "row_count": row_count,
        "column_count": len(columns),
        "missing_value_count": missing,
        "duplicate_row_count": profile["before"]["duplicate_row_count"],
        "profile": profile,
        "dashboard_url": urls[dashboard_name],
        "artifacts": [{"name": name, "url": url} for name, url in urls.items()],
    }


def _run_analysis(analysis_id: str, csv_text: str, filename: str) -> None:
    with _lock:
        job = _analyses[analysis_id]
        job.update(
            status="running", progress=12, message="Checking columns and data quality"
        )
    try:
        frame = pd.read_csv(StringIO(csv_text))
        output_dir = OUTPUT_ROOT / analysis_id
        output_dir.mkdir(parents=True, exist_ok=True)
        backend = DockerSandbox(root_dir=OUTPUT_ROOT)
        graph = create_local_agent(backend)
        row_count = min(10, len(frame))
        preview_json = frame.sample(n=row_count, random_state=42).to_json(
            orient="records", date_format="iso"
        )
        if preview_json is None:
            raise RuntimeError("Could not serialize the reproducible data preview")
        preview = json.loads(preview_json)
        planning_context = {
            "profile": _compact_profile(json.loads(_profile(frame))),
            "preview": {
                "columns": [str(column) for column in frame.columns],
                "rows": preview,
            },
        }
        job.update(progress=40, message="Agent is planning EDA and charts")
        state = graph.invoke(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": (
                            f"Analyze the approved sample CSV ({filename}). Use the aggregate profile and reproducible "
                            "sample to report findings, propose justified transformations, and request useful charts. "
                            "The full CSV is available only to the plan tool.\n\n"
                            + json.dumps(
                                planning_context,
                                ensure_ascii=False,
                                separators=(",", ":"),
                            )
                        ),
                    }
                ]
            },
            context={"csv_data": csv_text},
        )
        paths = _local_artifacts(backend, output_dir)
        with _lock:
            job.update(
                progress=92, message="Collecting dashboard and downloadable artifacts"
            )
        result = _artifact_result(
            analysis_id, output_dir, len(pd.read_csv(StringIO(csv_text)))
        )
        with _lock:
            _sessions[analysis_id] = (graph, backend)
            job["conversation"] = state.get("messages", [])
        with _lock:
            job.update(
                status="completed",
                progress=100,
                message="Your dashboard is ready",
                result=result,
                artifact_paths={
                    path.relative_to(output_dir / "artifacts").as_posix(): path.resolve()
                    for path in paths
                },
            )
    except Exception as error:  # noqa: BLE001 - background boundary must preserve job failure state
        with _lock:
            job.update(status="failed", progress=0, message=str(error))


@app.get("/api/health")
def health():
    configuration_error = _configuration_error()
    return {
        "status": "ok",
        "agent_configured": configuration_error is None,
        "configuration_error": configuration_error,
    }


def _configuration_error() -> str | None:
    if not os.getenv("GROQ_API_KEY"):
        return "Set GROQ_API_KEY before uploading. LangSmith credentials are optional and enable tracing."
    if not shutil.which("docker"):
        return "Docker must be installed and running for isolated dashboard generation."
    image = os.getenv("SANDBOX_DOCKER_IMAGE", "data-agent-eda:checkpoint")
    try:
        inspected = subprocess.run(
            ["docker", "image", "inspect", image],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "Docker must be installed and running for isolated dashboard generation."
    if inspected.returncode != 0:
        return f"Build the local sandbox image first; Docker image '{image}' was not found."
    return None


@app.get("/sample.csv")
def sample_csv():
    path = Path(__file__).parents[1] / "data" / "sample_data.csv"
    return FileResponse(path, media_type="text/csv", filename="sample_data.csv")


@app.post("/api/analyses", status_code=202)
async def create_analysis(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),  # noqa: B008 - FastAPI requires parameter markers for multipart uploads
    classification: str = Form("private"),
):
    try:
        ensure_hosted_upload_allowed(classification)
    except (ValueError, PermissionError) as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    if classification not in {
        DataClassification.SAMPLE.value,
        DataClassification.PUBLIC.value,
    }:
        raise HTTPException(
            status_code=403, detail="Only sample or public data can be uploaded"
        )
    configuration_error = _configuration_error()
    if configuration_error:
        raise HTTPException(status_code=503, detail=configuration_error)
    if not file.filename or Path(file.filename).suffix.lower() != ".csv":
        raise HTTPException(status_code=415, detail="Upload a CSV file")
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if not content:
        raise HTTPException(status_code=400, detail="The CSV file is empty")
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="CSV files are limited to 25 MB")
    try:
        csv_text = content.decode("utf-8-sig")
        frame = pd.read_csv(StringIO(csv_text), nrows=2)
        if frame.empty or not len(frame.columns):
            raise ValueError("The CSV needs a header and at least one data row")
    except (UnicodeDecodeError, pd.errors.ParserError, ValueError) as error:
        raise HTTPException(
            status_code=400, detail=f"Could not read this CSV: {error}"
        ) from error

    analysis_id = uuid.uuid4().hex
    with _lock:
        _analyses[analysis_id] = {
            "analysis_id": analysis_id,
            "status": "queued",
            "progress": 5,
            "message": "Upload received; preparing the local isolated analysis",
            "result": None,
            "csv_text": csv_text,
        }
    background_tasks.add_task(
        _run_analysis, analysis_id, csv_text, Path(file.filename).name
    )
    return {
        "analysis_id": analysis_id,
        "status": "queued",
        "progress": 5,
        "message": "Upload received",
    }


@app.get("/api/analyses/{analysis_id}")
def get_analysis(analysis_id: str):
    with _lock:
        job = _analyses.get(analysis_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Analysis not found")
        return {
            key: job[key]
            for key in ("analysis_id", "status", "progress", "message", "result")
        }


def _message_text(message: Any) -> str:
    if isinstance(message, dict):
        content = message.get("content", "")
        role = message.get("role") or message.get("type")
    else:
        content = getattr(message, "content", "")
        role = getattr(message, "type", None)
    if role not in {"assistant", "ai"}:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            block["text"]
            for block in content
            if isinstance(block, dict) and isinstance(block.get("text"), str)
        )
    return ""


def _ask_agent(analysis_id: str, question: str) -> str:
    with _lock:
        job = _analyses.get(analysis_id)
        if job is None or job.get("status") != "completed":
            raise ValueError("Finish an analysis before asking a question")
        graph, _backend = _sessions[analysis_id]
        conversation = list(job.get("conversation", []))
        csv_text = job["csv_text"]
    conversation.append({"role": "user", "content": question})
    state = graph.invoke(
        {"messages": conversation},
        context={"csv_data": csv_text},
    )
    messages = state.get("messages", []) if isinstance(state, dict) else []
    with _lock:
        _analyses[analysis_id]["conversation"] = messages
    answers = [text for message in messages if (text := _message_text(message))]
    if not answers:
        raise RuntimeError("The analyst returned no text response")
    return answers[-1]


@app.post("/api/analyses/{analysis_id}/questions")
async def ask_analysis(analysis_id: str, payload: dict[str, str]):
    question = payload.get("question", "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="Enter a question")
    if len(question) > 4000:
        raise HTTPException(
            status_code=413, detail="Questions are limited to 4,000 characters"
        )
    try:
        answer = await run_in_threadpool(_ask_agent, analysis_id, question)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    return {"answer": answer}


@app.get("/api/analyses/{analysis_id}/artifacts/{artifact_path:path}")
def get_artifact(analysis_id: str, artifact_path: str, download: bool = False):
    normalized = Path(artifact_path)
    if (
        normalized.is_absolute()
        or ".." in normalized.parts
        or "\\" in artifact_path
    ):
        raise HTTPException(status_code=404, detail="Artifact not found")
    with _lock:
        job = _analyses.get(analysis_id)
        path = job.get("artifact_paths", {}).get(artifact_path) if job else None
    if path is None or not path.is_file() or not path.is_relative_to(OUTPUT_ROOT):
        raise HTTPException(status_code=404, detail="Artifact not found")
    if path.suffix == ".html" and not download:
        return FileResponse(path, media_type="text/html")
    return FileResponse(path, filename=path.name)
