import argparse
import base64
import json
import os
from io import StringIO
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

import pandas as pd

from scripts.data_ingestion import DataIngestion
from scripts.data_policy import DataClassification, ensure_hosted_upload_allowed
from scripts.data_tools import _compact_profile, _profile
from scripts.db_cn import get_database_url


def _write_artifacts(payload: str, output_dir: Path) -> list[Path]:
    """Decode artifact tool results into files contained by output_dir."""
    decoded = json.loads(payload)
    saved = []
    root = output_dir.resolve()
    for artifact in decoded.get("artifacts", []):
        relative = PurePosixPath(artifact["path"])
        windows_path = PureWindowsPath(artifact["path"])
        if (
            relative.is_absolute()
            or windows_path.is_absolute()
            or ".." in relative.parts
            or ".." in windows_path.parts
            or "\\" in artifact["path"]
        ):
            raise ValueError(f"Unsafe sandbox artifact path: {relative}")
        destination = (root / Path(*relative.parts)).resolve()
        if not destination.is_relative_to(root):
            raise ValueError(f"Unsafe sandbox artifact path: {relative}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(
            base64.b64decode(artifact["content_base64"], validate=True)
        )
        saved.append(destination)
    return saved


def _tool_artifact_payloads(state: dict) -> list[str]:
    payloads = []
    for message in state.get("messages", []):
        content = (
            message.get("content")
            if isinstance(message, dict)
            else getattr(message, "content", None)
        )
        if isinstance(content, str) and content.startswith('{"artifacts":'):
            payloads.append(content)
    return payloads


def _run_dataset_walkthrough(
    frame: pd.DataFrame,
    csv_text: str,
    output_dir: Path,
    *,
    description: str,
    client=None,
    agent_id=None,
) -> list[Path]:
    """Send approved data as run context and retrieve its analysis artifacts."""
    row_count = min(10, len(frame))
    preview_json = frame.sample(n=row_count, random_state=42).to_json(
        orient="records", date_format="iso"
    )
    if preview_json is None:
        raise RuntimeError("Pandas did not serialize the sample preview")
    preview_rows = json.loads(preview_json)
    planning_context = {
        "profile": _compact_profile(json.loads(_profile(frame))),
        "preview": {
            "columns": [str(column) for column in frame.columns],
            "rows": preview_rows,
        },
    }
    planning_message = (
        f"Analyze the approved {description} and return the required artifacts. Use the "
        "aggregate profile and reproducible sample to propose findings, transformations, "
        "and charts. The full CSV is available only to the plan tool.\n\n"
        + json.dumps(planning_context, ensure_ascii=False, separators=(",", ":"))
    )

    if client is None:
        from langgraph_sdk import get_sync_client

        client = get_sync_client(
            url=os.getenv(
                "LANGSMITH_MANAGED_AGENTS_URL",
                "https://api.smith.langchain.com/v1/deepagents",
            ),
            api_key=os.getenv("LANGSMITH_API_KEY") or os.getenv("LANGSMITH_API"),
        )
    agent_id = agent_id or os.getenv("MANAGED_DEEP_AGENT_ID")
    if not agent_id:
        raise RuntimeError(
            "Set MANAGED_DEEP_AGENT_ID to the deployed Managed Deep Agent ID"
        )

    thread = client.threads.create()
    stream = client.runs.stream(
        thread["thread_id"],
        agent_id,
        input={"messages": [{"role": "user", "content": planning_message}]},
        stream_mode=["values"],
        context={"csv_data": csv_text},
    )
    final_state = None
    for event in stream:
        if getattr(event, "event", None) == "values":
            final_state = event.data
    if final_state is None:
        raise RuntimeError(
            "Managed agent run completed without returning a final state"
        )

    saved = []
    for payload in _tool_artifact_payloads(final_state):
        saved.extend(_write_artifacts(payload, output_dir))
    if not saved:
        raise RuntimeError("The agent run returned no downloadable artifacts")
    required = {
        "analysis_report.md",
        "analysis_dashboard.html",
        "cleaned_data.csv",
        "transformation_log.json",
        "analysis_profile.json",
    }
    returned = {path.name for path in saved}
    if not required.issubset(returned):
        raise RuntimeError(
            "The agent must return the report, profile, transformed CSV, and transformation log"
        )
    return saved


def run_csv_walkthrough(
    sample_path: Path,
    output_dir: Path,
    *,
    client=None,
    agent_id=None,
    classification: DataClassification | str = DataClassification.SAMPLE,
) -> list[Path]:
    """Send raw, approved sample data as run context and retrieve its artifacts."""
    ensure_hosted_upload_allowed(classification)
    csv_text = sample_path.read_text(encoding="utf-8")
    frame = pd.read_csv(StringIO(csv_text))
    return _run_dataset_walkthrough(
        frame,
        csv_text,
        output_dir,
        description="sample CSV",
        client=client,
        agent_id=agent_id,
    )


def run_database_walkthrough(
    query: str,
    output_dir: Path,
    *,
    database_url_env: str = "DATABASE_URL",
    client=None,
    agent_id=None,
    classification: DataClassification | str = DataClassification.PRIVATE,
) -> list[Path]:
    """Load a database query on the host; only explicitly public data may be uploaded."""
    ensure_hosted_upload_allowed(classification)
    if not query.strip():
        raise ValueError("A non-empty SQL query is required")
    database_url = os.getenv(database_url_env) or get_database_url()

    frame = DataIngestion(database_url).load_from_database(query)
    csv_text = frame.to_csv(index=False)
    return _run_dataset_walkthrough(
        frame,
        csv_text,
        output_dir,
        description="public database result",
        client=client,
        agent_id=agent_id,
    )


def run_api_walkthrough(
    api_url: str,
    output_dir: Path,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    client=None,
    agent_id=None,
    classification: DataClassification | str = DataClassification.PRIVATE,
) -> list[Path]:
    """Fetch an API response on the host; only explicitly public data may be uploaded."""
    ensure_hosted_upload_allowed(classification)
    if not api_url.strip():
        raise ValueError("A non-empty API URL is required")
    frame = DataIngestion().fetch_from_api(api_url, params=params, headers=headers)
    csv_text = frame.to_csv(index=False)
    return _run_dataset_walkthrough(
        frame,
        csv_text,
        output_dir,
        description="public API response",
        client=client,
        agent_id=agent_id,
    )


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Analyze data with a Managed Deep Agent"
    )
    parser.add_argument(
        "--source", choices=("sample-csv", "database", "api"), default="sample-csv"
    )
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts"))
    parser.add_argument("--query", help="SQL query to run on the host database")
    parser.add_argument("--database-url-env", default="DATABASE_URL", metavar="ENV_VAR")
    parser.add_argument("--api-url", help="API endpoint to fetch on the host")
    parser.add_argument("--api-params", help="JSON object of API query parameters")
    parser.add_argument(
        "--api-headers-env",
        default="API_HEADERS",
        metavar="ENV_VAR",
        help="Environment variable containing a JSON object of host-side API headers",
    )
    parser.add_argument(
        "--classification",
        choices=tuple(value.value for value in DataClassification),
        help="Hosted-data classification; database and API uploads default to private",
    )
    args = parser.parse_args(argv)
    if args.source == "database":
        if args.query is None:
            parser.error("--query is required with --source database")
        if (
            args.api_url is not None
            or args.api_params is not None
            or args.api_headers_env != "API_HEADERS"
        ):
            parser.error("API options are only valid with --source api")
        paths = run_database_walkthrough(
            args.query,
            args.output_dir,
            database_url_env=args.database_url_env,
            classification=args.classification or DataClassification.PRIVATE,
        )
    elif args.source == "api":
        if args.api_url is None:
            parser.error("--api-url is required with --source api")
        if args.query is not None:
            parser.error("--query is only valid with --source database")
        try:
            params = json.loads(args.api_params or "{}")
            headers = json.loads(os.getenv(args.api_headers_env, "{}"))
        except json.JSONDecodeError as error:
            parser.error(
                f"API params and headers must be valid JSON objects: {error.msg}"
            )
        if not isinstance(params, dict) or not isinstance(headers, dict):
            parser.error("API params and headers must be JSON objects")
        if not all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in headers.items()
        ):
            parser.error("API header names and values must be strings")
        paths = run_api_walkthrough(
            args.api_url,
            args.output_dir,
            params=params,
            headers=headers,
            classification=args.classification or DataClassification.PRIVATE,
        )
    else:
        if (
            args.query is not None
            or args.classification is not None
            or args.api_url is not None
            or args.api_params is not None
            or args.api_headers_env != "API_HEADERS"
        ):
            parser.error(
                "source-specific options are not valid with --source sample-csv"
            )
        sample_path = Path(__file__).parents[1] / "data" / "sample_data.csv"
        paths = run_csv_walkthrough(sample_path, args.output_dir)
    for path in paths:
        print(f"Saved {path}")


if __name__ == "__main__":
    main()
