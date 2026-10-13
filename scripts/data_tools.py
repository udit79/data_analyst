"""Sandbox-backed profiling and cleaning tools for CSV analysis."""

import json
import math
import re
from io import StringIO
from pathlib import Path
from typing import cast

import pandas as pd

from scripts.analysis_plan import AnalysisPlan, apply_analysis_plan

RAW_PATH = "/workspace/raw_data.csv"
CLEANED_PATH = "/workspace/artifacts/cleaned_data.csv"
TRANSFORMATION_LOG_PATH = "/workspace/artifacts/transformation_log.json"
PROFILE_PATH = "/workspace/artifacts/analysis_profile.json"
CHART_REQUESTS_PATH = "/workspace/artifacts/chart_requests.json"
CHART_MANIFEST_PATH = "/workspace/artifacts/chart_manifest.json"
RENDERER_PATH = "/workspace/eda_renderer.py"
REPORT_PATH = "/workspace/artifacts/analysis_report.md"
DASHBOARD_PATH = "/workspace/artifacts/analysis_dashboard.html"


def _check_responses(responses, operation: str) -> None:
    for response in responses:
        if response.error:
            raise RuntimeError(f"Sandbox {operation} failed: {response.error}")


def _read_csv_text(content: str) -> pd.DataFrame:
    return pd.read_csv(StringIO(content))


def _profile(frame: pd.DataFrame) -> str:
    columns = {}
    for name in frame.columns:
        series = cast(pd.Series, frame[name])
        missing = int(series.isna().sum())
        unique_count = int(series.nunique(dropna=True))
        non_missing_count = int(series.notna().sum())
        name_looks_like_identifier = bool(
            re.search(r"(^|[_\s])(id|uuid|key|index)($|[_\s])", str(name).lower())
        )
        identifier_likelihood = name_looks_like_identifier or (
            non_missing_count >= 10
            and unique_count == non_missing_count
            and series.is_monotonic_increasing
        )
        entry = {
            "dtype": str(series.dtype),
            "missing_count": missing,
            "missing_percent": (100.0 * missing / len(frame)) if len(frame) else 0.0,
            "unique_count": unique_count,
            "unique_percent": (100.0 * unique_count / non_missing_count)
            if non_missing_count
            else 0.0,
            "likely_identifier": identifier_likelihood,
            "identifier_reason": (
                "column name suggests an identifier"
                if name_looks_like_identifier
                else "all observed values are unique and monotonic"
                if identifier_likelihood
                else None
            ),
        }
        numeric = cast(pd.Series, pd.to_numeric(series, errors="coerce"))
        numeric_parse_rate = (
            float(numeric.notna().sum() / non_missing_count)
            if non_missing_count
            else 0.0
        )
        inferred_numeric = not pd.api.types.is_bool_dtype(series) and (
            pd.api.types.is_numeric_dtype(series) or numeric_parse_rate >= 0.95
        )
        entry["inferred_type"] = "numeric" if inferred_numeric else "categorical"
        if inferred_numeric:
            values = cast(pd.Series, numeric.dropna())
            values = cast(pd.Series, values[values.map(math.isfinite)])
            if values.empty:
                q1 = q3 = None
            else:
                q1 = float(cast(float, values.quantile(0.25)))
                q3 = float(cast(float, values.quantile(0.75)))
            outlier_count = (
                0
                if q1 is None or q3 is None
                else int(
                    (
                        (values < q1 - 1.5 * (q3 - q1))
                        | (values > q3 + 1.5 * (q3 - q1))
                    ).sum()
                )
            )
            entry.update(
                mean=None if values.empty else _finite_or_none(values.mean()),
                median=None if values.empty else _finite_or_none(values.median()),
                minimum=None if values.empty else _finite_or_none(values.min()),
                q1=q1,
                q3=q3,
                maximum=None if values.empty else _finite_or_none(values.max()),
                skew=None if len(values) < 3 else _finite_or_none(values.skew()),
                iqr_outlier_count=outlier_count,
            )
        else:
            modes = series.mode(dropna=True)
            entry["mode"] = None if modes.empty else _json_value(modes.iloc[0])
            entry["mode_frequency"] = (
                0 if modes.empty else int((series == modes.iloc[0]).sum())
            )
            entry["top_frequencies"] = [
                {"value": _json_value(value), "count": int(count)}
                for value, count in series.value_counts(dropna=True).head(5).items()
            ]
        columns[str(name)] = entry
    return json.dumps(
        {
            "row_count": len(frame),
            "column_count": len(frame.columns),
            "duplicate_row_count": int(frame.duplicated().sum()),
            "columns": columns,
        },
        allow_nan=False,
    )


def _compact_profile(profile: dict) -> dict:
    """Keep model-visible profiling to the decision-relevant aggregate matrix."""
    compact_columns = {}
    shared_fields = (
        "dtype",
        "inferred_type",
        "missing_count",
        "missing_percent",
        "unique_count",
        "unique_percent",
        "likely_identifier",
        "identifier_reason",
    )
    numeric_fields = (
        "mean",
        "median",
        "skew",
        "minimum",
        "maximum",
        "iqr_outlier_count",
    )
    for name, details in profile["columns"].items():
        fields = shared_fields + (
            numeric_fields
            if details["inferred_type"] == "numeric"
            else ("mode", "mode_frequency", "top_frequencies")
        )
        compact_columns[name] = {key: details[key] for key in fields if key in details}
        if "top_frequencies" in compact_columns[name]:
            compact_columns[name]["top_frequencies"] = compact_columns[name][
                "top_frequencies"
            ][:3]
    return {
        "row_count": profile["row_count"],
        "column_count": profile["column_count"],
        "duplicate_row_count": profile["duplicate_row_count"],
        "columns": compact_columns,
    }


def _finite_or_none(value):
    numeric = float(value)
    return numeric if math.isfinite(numeric) else None


def _json_value(value):
    return value.item() if hasattr(value, "item") else value


def _apply_analysis_plan(plan: AnalysisPlan, runtime, backend_override=None) -> str:
    context = runtime.context
    csv_text = (
        context.get("csv_data")
        if isinstance(context, dict)
        else getattr(context, "csv_data", None)
    )
    if not isinstance(csv_text, str) or not csv_text:
        raise ValueError("Run context must include non-empty csv_data")
    source = _read_csv_text(csv_text)
    transformed, transformation_log = apply_analysis_plan(source, plan)
    analysis_profile = {
        "before": json.loads(_profile(source)),
        "after": json.loads(_profile(transformed)),
    }
    model_profile = {
        phase: _compact_profile(profile) for phase, profile in analysis_profile.items()
    }
    payload = transformed.to_csv(index=False).encode("utf-8")
    log_payload = json.dumps(transformation_log, ensure_ascii=False, indent=2).encode(
        "utf-8"
    )
    profile_payload = json.dumps(analysis_profile, ensure_ascii=False, indent=2).encode(
        "utf-8"
    )
    chart_requests = transformation_log["chart_requests"]
    requests_payload = json.dumps(chart_requests, ensure_ascii=False, indent=2).encode(
        "utf-8"
    )
    renderer_payload = Path(__file__).with_name("eda_renderer.py").read_bytes()
    backend = backend_override or runtime.backend
    if backend is None:
        raise RuntimeError("This agent run has no sandbox backend")
    _check_responses(
        backend.upload_files(
            [
                (RAW_PATH, csv_text.encode("utf-8")),
                (CLEANED_PATH, payload),
                (TRANSFORMATION_LOG_PATH, log_payload),
                (PROFILE_PATH, profile_payload),
                (CHART_REQUESTS_PATH, requests_payload),
                (RENDERER_PATH, renderer_payload),
            ]
        ),
        "upload",
    )
    execute = getattr(backend, "execute", None)
    if not callable(execute):
        raise TypeError(
            "The managed sandbox backend does not support command execution"
        )
    execution = execute(f"python {RENDERER_PATH}", timeout=120)
    if getattr(execution, "exit_code", None) != 0:
        output = getattr(execution, "output", "")
        raise RuntimeError(f"Sandbox EDA rendering failed: {output}")
    manifest_responses = backend.download_files([CHART_MANIFEST_PATH])
    _check_responses(manifest_responses, "manifest download")
    if not manifest_responses or manifest_responses[0].content is None:
        raise RuntimeError("Sandbox returned no chart manifest")
    manifest = json.loads(manifest_responses[0].content)
    generated_charts = [
        chart["path"] for chart in manifest["charts"] if chart["status"] == "generated"
    ]
    report_path = REPORT_PATH
    artifact_paths = [
        CLEANED_PATH,
        TRANSFORMATION_LOG_PATH,
        PROFILE_PATH,
        report_path,
        DASHBOARD_PATH,
        *generated_charts,
    ]
    return json.dumps(
        {
            "cleaned_path": CLEANED_PATH,
            "transformation_log_path": TRANSFORMATION_LOG_PATH,
            "analysis_profile_path": PROFILE_PATH,
            "report_path": report_path,
            "dashboard_path": DASHBOARD_PATH,
            "input_row_count": len(source),
            "row_count": len(transformed),
            "analysis_profile": model_profile,
            "generated_chart_paths": generated_charts,
            "omitted_chart_requests": transformation_log[
                "omitted_chart_requests"
            ],
            "skipped_charts": [
                chart for chart in manifest["charts"] if chart["status"] == "skipped"
            ],
            "artifact_paths": artifact_paths,
            "transformation_log": transformation_log,
        }
    )


def create_data_tools():
    """Build the runtime-injected CSV analysis-plan tool."""
    from langchain.tools import ToolRuntime, tool

    @tool
    def apply_dataset_plan(plan: AnalysisPlan, runtime: ToolRuntime) -> str:
        """Validate and apply an allow-listed analysis plan to the staged CSV.

        Provide dataset findings, a reasoned transformation for each referenced column,
        whether to remove duplicate rows, and chart questions. Only listed operations run;
        the raw CSV is preserved and a separate transformed CSV plus audit log are saved.
        """
        return _apply_analysis_plan(plan, runtime)

    return [apply_dataset_plan]


def create_local_data_tools(backend):
    """Build the same analysis tool with an explicitly supplied local Docker backend."""
    from langchain.tools import ToolRuntime, tool

    @tool
    def apply_dataset_plan(plan: AnalysisPlan, runtime: ToolRuntime) -> str:
        """Apply a validated EDA and transformation plan to the uploaded CSV."""
        return _apply_analysis_plan(plan, runtime, backend_override=backend)

    return [apply_dataset_plan]
