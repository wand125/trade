from __future__ import annotations

import json
from pathlib import Path
from typing import Sequence

import numpy as np
import pandas as pd

from trade_data.next_bar_registry import (
    DEFAULT_DEVELOPMENT_FOLDS,
    _selection_mask,
    assert_aligned,
    read_prediction_sets,
)


def _wilson_lower(
    successes: np.ndarray, rows: np.ndarray, z: float = 1.96
) -> np.ndarray:
    output = np.full(np.shape(rows), np.nan, dtype="float64")
    valid = rows > 0
    probability = np.divide(
        successes, rows, out=np.zeros_like(successes, dtype="float64"), where=valid
    )
    z_squared = z * z
    denominator = 1 + z_squared / rows[valid]
    center = probability[valid] + z_squared / (2 * rows[valid])
    margin = z * np.sqrt(
        probability[valid] * (1 - probability[valid]) / rows[valid]
        + z_squared / (4 * rows[valid] ** 2)
    )
    output[valid] = (center - margin) / denominator
    return output


def _daily_aggregates(
    first: pd.DataFrame,
    second: pd.DataFrame,
    first_threshold: float,
    second_threshold: float,
    first_selection_column: str | None = None,
    second_selection_column: str | None = None,
) -> pd.DataFrame:
    assert_aligned(second, first, "first")
    timestamp = pd.to_datetime(first["timestamp"], utc=True)
    target = first["target_up"].to_numpy(dtype="float64")
    first_probability = np.clip(
        first["probability_up"].to_numpy(dtype="float64"), 1e-12, 1 - 1e-12
    )
    second_probability = np.clip(
        second["probability_up"].to_numpy(dtype="float64"), 1e-12, 1 - 1e-12
    )
    first_selected = _selection_mask(
        first, first_threshold, first_selection_column
    ).to_numpy(dtype="int64")
    second_selected = _selection_mask(
        second, second_threshold, second_selection_column
    ).to_numpy(dtype="int64")
    first_correct = first["correct"].to_numpy(dtype="int64")
    second_correct = second["correct"].to_numpy(dtype="int64")
    source = pd.DataFrame(
        {
            "day": timestamp.dt.floor("D"),
            "rows": 1,
            "first_selected": first_selected,
            "first_correct": first_selected * first_correct,
            "second_selected": second_selected,
            "second_correct": second_selected * second_correct,
            "first_brier": (first_probability - target) ** 2,
            "second_brier": (second_probability - target) ** 2,
            "first_log_loss": -(
                target * np.log(first_probability)
                + (1 - target) * np.log1p(-first_probability)
            ),
            "second_log_loss": -(
                target * np.log(second_probability)
                + (1 - target) * np.log1p(-second_probability)
            ),
        }
    )
    return source.groupby("day", sort=True).sum()


def _metric_arrays(
    totals: dict[str, np.ndarray],
) -> dict[str, tuple[np.ndarray, bool]]:
    rows = totals["rows"].astype("float64")

    def lane(prefix: str) -> dict[str, np.ndarray]:
        selected = totals[f"{prefix}_selected"].astype("float64")
        correct = totals[f"{prefix}_correct"].astype("float64")
        accuracy = np.divide(
            correct,
            selected,
            out=np.full_like(correct, np.nan),
            where=selected > 0,
        )
        coverage = selected / rows
        lower = _wilson_lower(correct, selected)
        return {
            "accuracy": accuracy,
            "coverage": coverage,
            "wilson_lower": lower,
            "selection_score": np.sqrt(coverage) * (lower - 0.5),
        }

    first_lane = lane("first")
    second_lane = lane("second")
    return {
        "lane_accuracy": (first_lane["accuracy"] - second_lane["accuracy"], True),
        "lane_coverage": (first_lane["coverage"] - second_lane["coverage"], True),
        "lane_wilson_lower": (
            first_lane["wilson_lower"] - second_lane["wilson_lower"],
            True,
        ),
        "lane_selection_score": (
            first_lane["selection_score"] - second_lane["selection_score"],
            True,
        ),
        "brier_score": (
            totals["first_brier"] / rows - totals["second_brier"] / rows,
            False,
        ),
        "log_loss": (
            totals["first_log_loss"] / rows - totals["second_log_loss"] / rows,
            False,
        ),
    }


def _summarize_delta(
    point: float,
    samples: np.ndarray,
    higher_is_better: bool,
) -> dict[str, object]:
    finite = samples[np.isfinite(samples)]
    if finite.size == 0:
        return {
            "available": False,
            "delta_first_minus_second": None,
            "bootstrap_mean_delta": None,
            "confidence_interval_95": [None, None],
            "higher_is_better": higher_is_better,
            "probability_first_better": None,
            "interval_supports_first_better": False,
            "reason": "metric is undefined because at least one lane has no selected rows",
        }
    lower, upper = np.quantile(finite, [0.025, 0.975])
    probability_first_better = (
        np.mean(finite > 0) if higher_is_better else np.mean(finite < 0)
    )
    return {
        "available": True,
        "delta_first_minus_second": float(point),
        "bootstrap_mean_delta": float(finite.mean()),
        "confidence_interval_95": [float(lower), float(upper)],
        "higher_is_better": higher_is_better,
        "probability_first_better": float(probability_first_better),
        "interval_supports_first_better": bool(
            lower > 0 if higher_is_better else upper < 0
        ),
    }


def paired_daily_block_bootstrap(
    first: pd.DataFrame,
    second: pd.DataFrame,
    threshold: float,
    iterations: int = 2_000,
    random_seed: int = 42,
    development_folds: Sequence[str] = DEFAULT_DEVELOPMENT_FOLDS,
    second_threshold: float | None = None,
    first_selection_column: str | None = None,
    second_selection_column: str | None = None,
    excluded_folds: Sequence[str] = (),
) -> dict[str, object]:
    if second_threshold is None:
        second_threshold = threshold
    if not 0.5 <= threshold < 1:
        raise ValueError("first threshold must be between 0.5 inclusive and 1")
    if not 0.5 <= second_threshold < 1:
        raise ValueError("second threshold must be between 0.5 inclusive and 1")
    if iterations < 100:
        raise ValueError("iterations must be at least 100")
    assert_aligned(first, second, "second")
    excluded = {str(fold) for fold in excluded_folds}
    if excluded:
        included = ~first["fold"].astype(str).isin(excluded)
        first = first.loc[included].reset_index(drop=True)
        second = second.loc[included].reset_index(drop=True)
        if first.empty:
            raise ValueError("excluded_folds removed every prediction row")
    development = first["fold"].astype(str).isin(set(development_folds))
    period_masks = {
        "development": development,
        "confirmation": ~development,
        "all": pd.Series(True, index=first.index),
    }
    rng = np.random.default_rng(random_seed)
    periods: dict[str, object] = {}
    for period, mask in period_masks.items():
        daily = _daily_aggregates(
            first.loc[mask].reset_index(drop=True),
            second.loc[mask].reset_index(drop=True),
            threshold,
            second_threshold,
            first_selection_column,
            second_selection_column,
        )
        if daily.empty:
            continue
        values = {column: daily[column].to_numpy(dtype="float64") for column in daily}
        point_totals = {
            column: np.asarray([array.sum()], dtype="float64")
            for column, array in values.items()
        }
        sampled_days = rng.integers(0, len(daily), size=(iterations, len(daily)))
        bootstrap_totals = {
            column: array[sampled_days].sum(axis=1) for column, array in values.items()
        }
        point_metrics = _metric_arrays(point_totals)
        bootstrap_metrics = _metric_arrays(bootstrap_totals)
        periods[period] = {
            "rows": int(point_totals["rows"][0]),
            "utc_day_blocks": len(daily),
            "metrics": {
                metric: _summarize_delta(
                    float(point_metrics[metric][0][0]),
                    bootstrap_metrics[metric][0],
                    bootstrap_metrics[metric][1],
                )
                for metric in point_metrics
            },
        }
    return {
        "format_version": 1,
        "method": "paired nonparametric UTC-day block bootstrap",
        "first_threshold": threshold,
        "second_threshold": second_threshold,
        "first_selection_column": first_selection_column,
        "second_selection_column": second_selection_column,
        "excluded_folds": sorted(excluded),
        "iterations": iterations,
        "random_seed": random_seed,
        "development_folds": list(development_folds),
        "delta_definition": "first minus second; negative is better for Brier/log loss",
        "periods": periods,
    }


def run_paired_daily_block_bootstrap(
    first_dirs: Sequence[Path],
    second_dirs: Sequence[Path],
    first_name: str,
    second_name: str,
    threshold: float,
    timeframe: int,
    iterations: int,
    random_seed: int,
    output: Path,
    second_threshold: float | None = None,
    first_selection_column: str | None = None,
    second_selection_column: str | None = None,
    excluded_folds: Sequence[str] = (),
) -> dict[str, object]:
    report = paired_daily_block_bootstrap(
        read_prediction_sets(first_dirs, timeframe),
        read_prediction_sets(second_dirs, timeframe),
        threshold,
        iterations,
        random_seed,
        second_threshold=second_threshold,
        first_selection_column=first_selection_column,
        second_selection_column=second_selection_column,
        excluded_folds=excluded_folds,
    )
    report["first_name"] = first_name
    report["second_name"] = second_name
    report["first_dirs"] = [str(path) for path in first_dirs]
    report["second_dirs"] = [str(path) for path in second_dirs]
    report["timeframe"] = timeframe
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return report
