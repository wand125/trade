from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

import numpy as np
import pandas as pd

from trade_data.backtest import read_ohlcv
from trade_data.next_bar import resample_complete_bars, validate_m1_frame


def parse_positive_ints(value: str) -> tuple[int, ...]:
    try:
        values = tuple(int(item.strip()) for item in value.split(",") if item.strip())
    except ValueError as error:
        raise argparse.ArgumentTypeError("expected comma-separated integers") from error
    if not values or any(value <= 0 for value in values) or len(set(values)) != len(values):
        raise argparse.ArgumentTypeError("holding bars must be unique positive integers")
    return values


def load_predictions(paths: Sequence[Path]) -> pd.DataFrame:
    if not paths:
        raise ValueError("at least one predictions file is required")
    required = {
        "timestamp",
        "decision_timestamp",
        "target_timestamp",
        "predicted_direction",
        "confidence",
        "fold",
    }
    frames: list[pd.DataFrame] = []
    for path in paths:
        frame = pd.read_parquet(path)
        missing = sorted(required - set(frame.columns))
        if missing:
            raise ValueError(f"{path} is missing columns: {', '.join(missing)}")
        frames.append(frame[list(required)].copy())
    combined = pd.concat(frames, ignore_index=True)
    for column in ("timestamp", "decision_timestamp", "target_timestamp"):
        combined[column] = pd.to_datetime(combined[column], utc=True)
    combined = combined.sort_values(["decision_timestamp", "fold"]).reset_index(drop=True)
    duplicate = combined.duplicated(["decision_timestamp"], keep=False)
    if duplicate.any():
        raise ValueError("prediction inputs contain duplicate decision timestamps")
    if not combined["predicted_direction"].isin(["up", "down"]).all():
        raise ValueError("predicted_direction must contain only up/down")
    if not combined["confidence"].between(0.5, 1.0).all():
        raise ValueError("confidence must be between 0.5 and 1.0")
    return combined


def build_fixed_horizon_outcomes(
    m1: pd.DataFrame,
    predictions: pd.DataFrame,
    timeframe_minutes: int,
    holding_bars: Sequence[int],
) -> pd.DataFrame:
    if timeframe_minutes <= 0:
        raise ValueError("timeframe_minutes must be positive")
    if not holding_bars or any(value <= 0 for value in holding_bars):
        raise ValueError("holding_bars must contain positive values")
    source = validate_m1_frame(m1)
    bars = resample_complete_bars(source, timeframe_minutes).sort_values("timestamp")
    if bars["timestamp"].duplicated().any():
        raise ValueError("resampled bars contain duplicate timestamps")

    predictions = predictions.copy()
    for column in ("timestamp", "decision_timestamp", "target_timestamp"):
        predictions[column] = pd.to_datetime(predictions[column], utc=True)
    step = pd.Timedelta(minutes=timeframe_minutes)
    if not predictions["decision_timestamp"].eq(predictions["timestamp"] + step).all():
        raise ValueError("prediction decision timestamps are not one bar after feature timestamps")
    if not predictions["target_timestamp"].eq(
        predictions["decision_timestamp"] + step
    ).all():
        raise ValueError("prediction target timestamps are not one bar after decisions")

    execution = bars[["timestamp", "open", "close"]].copy()
    for horizon in sorted(set(holding_bars)):
        offset = horizon - 1
        exit_timestamp = execution["timestamp"].shift(-offset)
        expected_exit = execution["timestamp"] + offset * step
        execution[f"exit_close_{horizon}"] = execution["close"].shift(-offset).where(
            exit_timestamp.eq(expected_exit)
        )

    execution = execution.rename(
        columns={"timestamp": "decision_timestamp", "open": "entry_open"}
    )
    frame = predictions.merge(
        execution.drop(columns=["close"]),
        on="decision_timestamp",
        how="left",
        validate="one_to_one",
    )
    direction_sign = np.where(frame["predicted_direction"].eq("up"), 1.0, -1.0)
    for horizon in sorted(set(holding_bars)):
        frame[f"gross_price_{horizon}"] = direction_sign * (
            frame[f"exit_close_{horizon}"] - frame["entry_open"]
        )
    return frame


def summarize_fixed_horizons(
    frame: pd.DataFrame,
    holding_bars: Sequence[int],
    confidence_threshold: float,
    round_trip_cost: float,
    timeframe_minutes: int = 15,
    excluded_folds: Sequence[str] = (),
) -> dict[str, object]:
    if not 0.5 <= confidence_threshold <= 1.0:
        raise ValueError("confidence_threshold must be between 0.5 and 1.0")
    if round_trip_cost < 0:
        raise ValueError("round_trip_cost must be non-negative")
    selected = frame.loc[
        frame["confidence"].ge(confidence_threshold)
        & ~frame["fold"].astype(str).isin(excluded_folds)
    ].copy()
    results: list[dict[str, object]] = []
    for horizon in holding_bars:
        column = f"gross_price_{horizon}"
        valid = selected.loc[np.isfinite(selected[column])].copy()
        valid["net_price"] = valid[column] - round_trip_cost
        folds = []
        for fold, group in valid.groupby("fold", sort=True):
            gross_mean = float(group[column].mean())
            folds.append(
                {
                    "fold": str(fold),
                    "rows": int(len(group)),
                    "gross_mean_per_oz": gross_mean,
                    "net_mean_per_oz": gross_mean - round_trip_cost,
                    "direction_accuracy": float(group[column].gt(0).mean()),
                }
            )
        gross_mean = float(valid[column].mean()) if len(valid) else None
        cost_ceiling = min(row["gross_mean_per_oz"] for row in folds) if folds else None
        positive_net_folds = int(sum(row["net_mean_per_oz"] > 0 for row in folds))
        results.append(
            {
                "holding_bars": int(horizon),
                "holding_minutes": int(horizon * timeframe_minutes),
                "rows": int(len(valid)),
                "direction_accuracy": float(valid[column].gt(0).mean()) if len(valid) else None,
                "gross_mean_per_oz": gross_mean,
                "net_mean_per_oz": gross_mean - round_trip_cost if gross_mean is not None else None,
                "positive_gross_folds": int(sum(row["gross_mean_per_oz"] > 0 for row in folds)),
                "positive_net_folds": positive_net_folds,
                "fold_count": int(len(folds)),
                "all_fold_cost_ceiling_per_oz": cost_ceiling,
                "cost_headroom_per_oz": (
                    cost_ceiling - round_trip_cost if cost_ceiling is not None else None
                ),
                "all_fold_net_positive": bool(folds) and positive_net_folds == len(folds),
                "round_trip_cost_per_oz": float(round_trip_cost),
                "folds": folds,
            }
        )
    return {
        "timeframe_minutes": int(timeframe_minutes),
        "confidence_threshold": float(confidence_threshold),
        "holding_bars": [int(value) for value in holding_bars],
        "round_trip_cost_per_oz": float(round_trip_cost),
        "excluded_folds": [str(value) for value in excluded_folds],
        "results": results,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audit fixed holding horizons for OOS direction predictions")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--predictions", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeframe", type=int, default=15)
    parser.add_argument("--holding-bars", type=parse_positive_ints, default=(1, 2, 4))
    parser.add_argument("--confidence-threshold", type=float, default=0.54)
    parser.add_argument("--round-trip-cost", type=float, default=0.26)
    parser.add_argument("--exclude-fold", action="append", default=[])
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    predictions = load_predictions(args.predictions)
    outcomes = build_fixed_horizon_outcomes(
        read_ohlcv(args.input), predictions, args.timeframe, args.holding_bars
    )
    report = summarize_fixed_horizons(
        outcomes,
        args.holding_bars,
        args.confidence_threshold,
        args.round_trip_cost,
        args.timeframe,
        args.exclude_fold,
    )
    report["inputs"] = {
        "bars": str(args.input),
        "predictions": [str(path) for path in args.predictions],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
