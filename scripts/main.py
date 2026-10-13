import argparse
import base64
import json
import os
from io import StringIO
from pathlib import Path, PurePosixPath, PureWindowsPath

import pandas as pd

from scripts.data_policy import DataClassification, ensure_hosted_upload_allowed
from scripts.data_tools import _profile


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
        destination.write_bytes(base64.b64decode(artifact["content_base64"], validate=True))
        saved.append(destination)
    return saved


def _tool_artifact_payloads(state: dict) -> list[str]:
    payloads = []
    for message in state.get("messages", []):
        content = message.get("content") if isinstance(message, dict) else getattr(message, "content", None)
        if isinstance(content, str) and content.startswith('{"artifacts":'):
            payloads.append(content)
    return payloads


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
    row_count = min(10, len(frame))
    preview_json = frame.sample(n=row_count, random_state=42).to_json(
        orient="records", date_format="iso"
    )
    if preview_json is None:
        raise RuntimeError("Pandas did not serialize the sample preview")
    preview_rows = json.loads(preview_json)
    planning_context = {
        "profile": json.loads(_profile(frame)),
        "preview": {"columns": [str(column) for column in frame.columns], "rows": preview_rows},
    }
    planning_message = (
        "Analyze the approved sample CSV and return the required artifacts. Use this "
        "aggregate profile and reproducible sample to choose cleaning strategies. "
        "The full CSV is available to the cleaning tool.\n\n"
        + json.dumps(planning_context, ensure_ascii=False, separators=(",", ":"))
    )

    if client is None:
        from langgraph_sdk import get_sync_client

        client = get_sync_client(
            url=os.getenv("LANGSMITH_MANAGED_AGENTS_URL", "https://api.smith.langchain.com/v1/deepagents")
        )
    agent_id = agent_id or os.getenv("MANAGED_DEEP_AGENT_ID")
    if not agent_id:
        raise RuntimeError("Set MANAGED_DEEP_AGENT_ID to the deployed Managed Deep Agent ID")

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
        raise RuntimeError("Managed agent run completed without returning a final state")

    saved = []
    for payload in _tool_artifact_payloads(final_state):
        saved.extend(_write_artifacts(payload, output_dir))
    if not saved:
        raise RuntimeError("The agent run returned no downloadable artifacts")
    required = {"analysis_report.md", "cleaned_data.csv"}
    returned = {path.name for path in saved}
    if not required.issubset(returned):
        raise RuntimeError("The agent must return analysis_report.md and cleaned_data.csv")
    return saved


def main(argv=None):
    parser = argparse.ArgumentParser(description="Analyze the public sample CSV with a Managed Deep Agent")
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts"))
    args = parser.parse_args(argv)
    sample_path = Path(__file__).parents[1] / "data" / "sample_data.csv"
    for path in run_csv_walkthrough(sample_path, args.output_dir):
        print(f"Saved {path}")


if __name__ == "__main__":
    main()
