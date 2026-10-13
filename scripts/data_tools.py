"""Sandbox-backed profiling and cleaning tools for CSV analysis."""

import json
from io import StringIO

import pandas as pd

from scripts.data_cleaning import DataCleaning

RAW_PATH = "/workspace/raw_data.csv"
CLEANED_PATH = "/workspace/artifacts/cleaned_data.csv"


def _check_responses(responses, operation: str) -> None:
    for response in responses:
        if response.error:
            raise RuntimeError(f"Sandbox {operation} failed: {response.error}")


def _read_csv_text(content: str) -> pd.DataFrame:
    return pd.read_csv(StringIO(content))


def _profile(frame: pd.DataFrame) -> str:
    columns = {}
    for name in frame.columns:
        series = frame[name]
        missing = int(series.isna().sum())
        entry = {
            "dtype": str(series.dtype),
            "missing_count": missing,
            "missing_percent": (100.0 * missing / len(frame)) if len(frame) else 0.0,
            "unique_count": int(series.nunique(dropna=True)),
        }
        if pd.api.types.is_numeric_dtype(series):
            entry.update(
                mean=None if series.count() == 0 else float(series.mean()),
                median=None if series.count() == 0 else float(series.median()),
                skew=None if series.count() < 3 else _finite_or_none(series.skew()),
            )
        else:
            modes = series.mode(dropna=True)
            entry["mode"] = None if modes.empty else _json_value(modes.iloc[0])
            entry["mode_frequency"] = 0 if modes.empty else int((series == modes.iloc[0]).sum())
        columns[str(name)] = entry
    return json.dumps(
        {"row_count": len(frame), "column_count": len(frame.columns),
         "duplicate_row_count": int(frame.duplicated().sum()), "columns": columns},
        allow_nan=False,
    )


def _finite_or_none(value):
    return float(value) if pd.notna(value) else None


def _json_value(value):
    return value.item() if hasattr(value, "item") else value


def _clean_and_profile_csv(strategy_by_column: dict[str, str], runtime) -> str:
    context = runtime.context
    csv_text = context.get("csv_data") if isinstance(context, dict) else getattr(context, "csv_data", None)
    if not isinstance(csv_text, str) or not csv_text:
        raise ValueError("Run context must include non-empty csv_data")
    source = _read_csv_text(csv_text)
    missing_columns = set(source.columns[source.isna().any()])
    if set(strategy_by_column) != missing_columns:
        raise ValueError(
            "Provide exactly one strategy for every column with missing values; "
            f"expected {sorted(missing_columns)}"
        )
    rows_removed_by_drop = {}
    before_drop = source
    for column, strategy in strategy_by_column.items():
        if strategy == "drop":
            after_drop = before_drop.dropna(subset=[column])
            rows_removed_by_drop[column] = len(before_drop) - len(after_drop)
            before_drop = after_drop
    cleaned = DataCleaning().clean_data(source, strategy_by_column)
    payload = cleaned.to_csv(index=False).encode("utf-8")
    _check_responses(
        runtime.backend.upload_files(
            [(RAW_PATH, csv_text.encode("utf-8")), (CLEANED_PATH, payload)]
        ),
        "upload",
    )
    return json.dumps(
        {
            "cleaned_path": CLEANED_PATH,
            "input_row_count": len(source),
            "row_count": len(cleaned),
            "rows_removed_by_drop": rows_removed_by_drop,
            "cleaned_profile": json.loads(_profile(cleaned)),
        }
    )


def create_data_tools():
    """Build the runtime-injected CSV cleaning and profiling tool."""
    from langchain.tools import tool
    from managed_deepagents import ManagedToolRuntime

    @tool
    def clean_dataset(strategy_by_column: dict[str, str], runtime: ManagedToolRuntime) -> str:
        """Stage the CSV, clean with one strategy per missing column, and return its new profile."""
        return _clean_and_profile_csv(strategy_by_column, runtime)

    return [clean_dataset]
