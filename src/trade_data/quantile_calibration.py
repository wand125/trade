from __future__ import annotations

from typing import Iterable

import numpy as np
import pandas as pd


def finite_numeric_series(values: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(values, errors="coerce")
    return numeric[np.isfinite(numeric)]


def empirical_cdf_scores(fit_values: pd.Series, values: pd.Series) -> pd.Series:
    fit = finite_numeric_series(fit_values)
    if fit.empty:
        raise ValueError("cannot build empirical CDF from empty finite fit values")

    sorted_fit = np.sort(fit.to_numpy(dtype="float64"))
    numeric_values = pd.to_numeric(values, errors="coerce")
    finite_mask = np.isfinite(numeric_values)
    output = pd.Series(np.nan, index=values.index, dtype="float64")
    if finite_mask.any():
        value_array = numeric_values[finite_mask].to_numpy(dtype="float64")
        output.loc[finite_mask] = (
            np.searchsorted(sorted_fit, value_array, side="right") / sorted_fit.size
        )
    return output


def quantile_summary(frame: pd.DataFrame, columns: Iterable[str]) -> dict[str, dict[str, float]]:
    summary: dict[str, dict[str, float]] = {}
    for column in columns:
        values = finite_numeric_series(frame[column])
        if values.empty:
            summary[column] = {
                "count": 0,
                "mean": float("nan"),
                "min": float("nan"),
                "p25": float("nan"),
                "p50": float("nan"),
                "p75": float("nan"),
                "p90": float("nan"),
                "max": float("nan"),
            }
            continue
        summary[column] = {
            "count": int(values.shape[0]),
            "mean": float(values.mean()),
            "min": float(values.min()),
            "p25": float(values.quantile(0.25)),
            "p50": float(values.quantile(0.50)),
            "p75": float(values.quantile(0.75)),
            "p90": float(values.quantile(0.90)),
            "max": float(values.max()),
        }
    return summary


def add_empirical_quantile_columns(
    fit_frame: pd.DataFrame,
    apply_frame: pd.DataFrame,
    columns: Iterable[str],
    *,
    suffix: str = "_valid_quantile",
    output_columns: Iterable[str] | None = None,
) -> tuple[pd.DataFrame, dict[str, object]]:
    source_columns = list(columns)
    if not source_columns:
        raise ValueError("at least one source column is required")
    missing_fit = [column for column in source_columns if column not in fit_frame.columns]
    missing_apply = [column for column in source_columns if column not in apply_frame.columns]
    if missing_fit:
        raise ValueError(f"fit frame is missing columns: {', '.join(missing_fit)}")
    if missing_apply:
        raise ValueError(f"apply frame is missing columns: {', '.join(missing_apply)}")

    if output_columns is None:
        target_columns = [f"{column}{suffix}" for column in source_columns]
    else:
        target_columns = list(output_columns)
    if len(target_columns) != len(source_columns):
        raise ValueError("output_columns must have the same length as columns")
    if len(set(target_columns)) != len(target_columns):
        raise ValueError("output columns must be unique")

    output = apply_frame.copy()
    for source_column, target_column in zip(source_columns, target_columns):
        output[target_column] = empirical_cdf_scores(
            fit_frame[source_column],
            apply_frame[source_column],
        )

    summary: dict[str, object] = {
        "source_columns": source_columns,
        "output_columns": target_columns,
        "fit": quantile_summary(fit_frame, source_columns),
        "apply": quantile_summary(output, [*source_columns, *target_columns]),
    }
    return output, summary
