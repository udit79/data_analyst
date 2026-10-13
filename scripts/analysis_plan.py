"""Validated, executable plans for preparing a dataset for analysis."""

from __future__ import annotations

from typing import Literal

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, model_validator

MissingAction = Literal["keep", "mean", "median", "mode", "drop_rows"]
Conversion = Literal["numeric", "datetime", "category", "string"]
OutlierAction = Literal["keep", "cap_iqr"]
ChartType = Literal["histogram", "box", "scatter", "bar", "correlation"]
MAX_CHART_REQUESTS = 4

class ColumnTransformation(BaseModel):
    """A small allow-listed set of transformations for a single column."""

    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1, max_length=300)
    missing_values: MissingAction = "keep"
    convert_to: Conversion | None = None
    outliers: OutlierAction = "keep"


class ChartRequest(BaseModel):
    """A chart the agent recommends for the dataset; rendering is a later step."""

    model_config = ConfigDict(extra="forbid")

    chart_type: ChartType
    columns: list[str] = Field(min_length=1, max_length=10)
    question: str = Field(min_length=1, max_length=200)
    reason: str = Field(min_length=1, max_length=300)

    @model_validator(mode="after")
    def validate_column_count(self) -> ChartRequest:
        required_counts = {"histogram": 1, "box": 1, "scatter": 2, "bar": 1}
        if self.chart_type in required_counts and len(self.columns) != required_counts[self.chart_type]:
            raise ValueError(f"{self.chart_type} charts require {required_counts[self.chart_type]} column(s)")
        if self.chart_type == "correlation" and len(self.columns) < 2:
            raise ValueError("correlation charts require at least two columns")
        if len(set(self.columns)) != len(self.columns):
            raise ValueError("chart columns must be unique")
        return self


class AnalysisPlan(BaseModel):
    """Agent findings and validated transformations for one tabular dataset."""

    model_config = ConfigDict(extra="forbid")

    findings: list[str] = Field(max_length=20)
    column_transformations: dict[str, ColumnTransformation] = Field(max_length=100)
    remove_duplicates: bool
    duplicate_reason: str = Field(min_length=1, max_length=300)
    # Do not put a maxItems limit in the tool schema: some model providers reject
    # the entire tool call before the agent can recover from an overlong plan.
    chart_requests: list[ChartRequest]

    def validate_for(self, frame: pd.DataFrame) -> None:
        """Reject references to columns absent from this input before changing it."""
        input_columns = set(map(str, frame.columns))
        unknown_columns = set(self.column_transformations) - input_columns
        unknown_columns.update(
            column
            for request in self.chart_requests
            for column in request.columns
            if column not in input_columns
        )
        if unknown_columns:
            raise ValueError(f"Analysis plan references unknown columns: {sorted(unknown_columns)}")


def apply_analysis_plan(frame: pd.DataFrame, plan: AnalysisPlan) -> tuple[pd.DataFrame, dict]:
    """Apply allowed transformations to a copy and return it with a change log."""
    plan.validate_for(frame)
    chart_requests = plan.chart_requests[:MAX_CHART_REQUESTS]
    omitted_chart_requests = plan.chart_requests[MAX_CHART_REQUESTS:]
    transformed = frame.copy(deep=True)
    applied: list[dict[str, object]] = []

    for column, operation in plan.column_transformations.items():
        before = transformed[column].copy()
        rows_before_operation = len(transformed)
        if operation.convert_to == "numeric":
            converted = pd.to_numeric(before, errors="coerce")
            if (before.notna() & pd.isna(converted)).any():
                raise ValueError(f"Column '{column}' contains values that cannot convert to numeric")
            transformed[column] = converted
        elif operation.convert_to == "datetime":
            converted = pd.to_datetime(before, errors="coerce")
            if (before.notna() & pd.isna(converted)).any():
                raise ValueError(f"Column '{column}' contains values that cannot convert to datetime")
            transformed[column] = converted
        elif operation.convert_to == "category":
            transformed[column] = before.astype("category")
        elif operation.convert_to == "string":
            transformed[column] = before.astype("string")

        missing = operation.missing_values
        if missing in {"mean", "median"}:
            if not pd.api.types.is_numeric_dtype(transformed[column]):
                raise ValueError(f"Missing-value strategy '{missing}' requires numeric column '{column}'")
            fill_value = getattr(transformed[column], missing)()
            transformed[column] = transformed[column].fillna(fill_value)
        elif missing == "mode":
            modes = transformed[column].mode(dropna=True)
            if not modes.empty:
                transformed[column] = transformed[column].fillna(modes.iloc[0])
        elif missing == "drop_rows":
            transformed = transformed.dropna(subset=[column])

        if operation.outliers == "cap_iqr":
            if pd.api.types.is_bool_dtype(transformed[column]):
                raise ValueError(
                    f"IQR outlier capping is not supported for boolean column '{column}'"
                )
            if not pd.api.types.is_numeric_dtype(transformed[column]):
                raise ValueError(f"IQR outlier capping requires numeric column '{column}'")
            values = transformed[column].dropna()
            if not values.empty:
                q1, q3 = values.quantile([0.25, 0.75])
                spread = q3 - q1
                transformed[column] = transformed[column].clip(q1 - 1.5 * spread, q3 + 1.5 * spread)

        applied.append(
            {
                "column": column,
                "reason": operation.reason,
                "conversion": operation.convert_to,
                "missing_values": missing,
                "outliers": operation.outliers,
                "rows_with_missing_before": int(before.isna().sum()),
                "rows_with_missing_after": int(transformed[column].isna().sum()),
                "rows_removed": rows_before_operation - len(transformed),
            }
        )

    duplicate_count = int(transformed.duplicated().sum()) if plan.remove_duplicates else 0
    if plan.remove_duplicates:
        transformed = transformed.drop_duplicates()

    log = {
        "input_rows": len(frame),
        "output_rows": len(transformed),
        "findings": plan.findings,
        "column_transformations": applied,
        "duplicate_rows_removed": duplicate_count,
        "duplicate_reason": plan.duplicate_reason,
        "chart_requests": [request.model_dump(mode="json") for request in chart_requests],
        "omitted_chart_requests": [
            request.model_dump(mode="json") for request in omitted_chart_requests
        ],
    }
    return transformed, log
