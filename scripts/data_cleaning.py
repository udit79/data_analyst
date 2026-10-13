from collections.abc import Mapping
from typing import ClassVar, Literal, TypeAlias

import pandas as pd

MissingValueStrategy: TypeAlias = Literal["mean", "median", "mode", "drop"]
CleaningStrategy: TypeAlias = MissingValueStrategy | Mapping[str, str]


class DataCleaning:
    STRATEGIES: ClassVar[frozenset[MissingValueStrategy]] = frozenset(
        {"mean", "median", "mode", "drop"}
    )

    def handle_missing_values(
        self, df: pd.DataFrame, strategy: CleaningStrategy = "mean"
    ) -> pd.DataFrame:
        """Fill or drop missing values using the requested strategy."""
        if isinstance(strategy, Mapping):
            result = df.copy()
            unknown_columns = set(strategy) - set(df.columns)
            if unknown_columns:
                raise ValueError(f"Unknown columns in cleaning strategy: {sorted(unknown_columns)}")
            for column, column_strategy in strategy.items():
                if column_strategy not in self.STRATEGIES:
                    raise ValueError(f"Unsupported missing-value strategy: {column_strategy}")
                if column_strategy == "drop":
                    result = result.dropna(subset=[column])
                elif column_strategy in {"mean", "median"}:
                    if not pd.api.types.is_numeric_dtype(result[column]):
                        raise ValueError(f"Strategy '{column_strategy}' requires numeric column '{column}'")
                    value = getattr(result[column], column_strategy)()
                    result[column] = result[column].fillna(value)
                else:
                    modes = result[column].mode(dropna=True)
                    if not modes.empty:
                        result[column] = result[column].fillna(modes.iloc[0])
            return result
        if strategy == "mean":
            return df.fillna(df.mean(numeric_only=True))
        if strategy == "median":
            return df.fillna(df.median(numeric_only=True))
        if strategy == "mode":
            modes = df.mode(dropna=True)
            if modes.empty:
                return df.copy()
            return df.fillna(modes.iloc[0])
        if strategy == "drop":
            return df.dropna()
        raise ValueError(f"Unsupported missing-value strategy: {strategy}")
    def remove_duplicates(self, df: pd.DataFrame) -> pd.DataFrame:
        """Remove duplicate rows."""
        return df.drop_duplicates()

    def fix_data_types(self, df: pd.DataFrame) -> pd.DataFrame:
        """Convert columns that can be represented numerically."""
        for col in df.columns:
            try:
                df[col]=pd.to_numeric(df[col])
            except ValueError:
                pass
        return df
    def clean_data(
        self, df: pd.DataFrame, strategy: CleaningStrategy = "mean"
    ) -> pd.DataFrame:
        df = self.handle_missing_values(df, strategy)
        df=self.remove_duplicates(df)
        df=self.fix_data_types(df)
        return df
