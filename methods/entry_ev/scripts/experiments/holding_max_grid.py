#!/usr/bin/env python3
"""Run fixed max-predicted-hold grids from one or more prediction parquet files."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import fields
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from trade_data.backtest import (  # noqa: E402
    BacktestConfig,
    ModelPolicyConfig,
    json_default,
    make_run_dir,
    month_bounds,
    prediction_required_columns,
    read_ohlcv,
    run_model_policy,
    slice_for_month,
    write_result,
)


MODEL_POLICY_TUPLE_FIELDS = {
    "fixed_horizon_minutes",
    "long_fixed_horizon_columns",
    "short_fixed_horizon_columns",
    "side_confidence_penalty_rules",
    "side_confidence_overfit_penalty_rules",
    "side_ev_penalty_rules",
    "extra_side_margin_rules",
    "side_extra_margin_rules",
    "side_block_rules",
    "block_trend_regimes",
    "block_volatility_regimes",
    "block_session_regimes",
    "block_gap_regimes",
    "block_combined_regimes",
}


def parse_csv_strings(value: str) -> list[str]:
    values = [part.strip() for part in value.split(",") if part.strip()]
    if not values:
        raise argparse.ArgumentTypeError("at least one value is required")
    return values


def parse_csv_floats(value: str) -> list[float]:
    values = [float(part.strip()) for part in value.split(",") if part.strip()]
    if not values:
        raise argparse.ArgumentTypeError("at least one float is required")
    return values


def parse_csv_paths(value: str) -> list[Path]:
    return [Path(part) for part in parse_csv_strings(value)]


def parse_cost_cases(value: str) -> list[tuple[str, float, float, int]]:
    cases: list[tuple[str, float, float, int]] = []
    for raw_case in parse_csv_strings(value):
        parts = [part.strip() for part in raw_case.split(":")]
        if len(parts) != 4:
            raise argparse.ArgumentTypeError(
                "cost cases must use label:spread:slippage:delay"
            )
        label, spread, slippage, delay = parts
        if not label:
            raise argparse.ArgumentTypeError("cost case label must not be empty")
        delay_value = int(float(delay))
        if delay_value < 0:
            raise argparse.ArgumentTypeError("execution delay must be non-negative")
        cases.append((label, float(spread), float(slippage), delay_value))
    return cases


def local_json_default(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    try:
        return json_default(value)
    except TypeError:
        pass
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, np.bool_):
        return bool(value)
    raise TypeError(f"cannot serialize {type(value).__name__}")


def load_base_policy_config(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if "model_policy_config" not in raw:
        raise ValueError(f"{path} is missing model_policy_config")
    allowed = {field.name for field in fields(ModelPolicyConfig)}
    config = {key: value for key, value in raw["model_policy_config"].items() if key in allowed}
    for key in MODEL_POLICY_TUPLE_FIELDS:
        if key in config and isinstance(config[key], list):
            config[key] = tuple(config[key])
    config["predictions"] = Path(config["predictions"])
    return config


def merge_prediction_frames(
    paths: list[Path],
    *,
    required_columns: list[str],
) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for path in paths:
        frame = pd.read_parquet(path)
        missing_required = sorted(set(required_columns) - set(frame.columns))
        if missing_required:
            raise ValueError(
                f"{path} missing required columns: {', '.join(missing_required)}"
            )
        if "dataset_month" not in frame.columns:
            raise ValueError(f"{path} is missing dataset_month")
        frame = frame.copy()
        frame["source_path"] = str(path)
        frames.append(frame)
    return merge_prediction_frames_from_frames(frames, required_columns=required_columns)


def merge_prediction_frames_from_frames(
    frames: list[pd.DataFrame],
    *,
    required_columns: list[str],
) -> pd.DataFrame:
    if not frames:
        raise ValueError("at least one prediction frame is required")
    for index, frame in enumerate(frames):
        missing_required = sorted(set(required_columns) - set(frame.columns))
        if missing_required:
            raise ValueError(
                f"prediction frame {index} missing required columns: "
                f"{', '.join(missing_required)}"
            )
        if "dataset_month" not in frame.columns:
            raise ValueError(f"prediction frame {index} is missing dataset_month")
    combined = pd.concat(frames, ignore_index=True, sort=False)
    combined["decision_timestamp"] = pd.to_datetime(
        combined["decision_timestamp"],
        utc=True,
    )
    duplicated = combined["decision_timestamp"].duplicated()
    if duplicated.any():
        duplicate_count = int(duplicated.sum())
        raise ValueError(f"combined predictions contain duplicate timestamps: {duplicate_count}")
    return combined.sort_values("decision_timestamp").reset_index(drop=True)


def prediction_coverage(
    predictions: pd.DataFrame,
    *,
    months: list[str],
    max_hold_hours: float,
) -> pd.DataFrame:
    timestamps = pd.to_datetime(predictions["decision_timestamp"], utc=True)
    rows: list[dict[str, object]] = []
    for month in months:
        start, end = month_bounds(month)
        max_exit_end = end + pd.Timedelta(hours=max_hold_hours)
        evaluation_mask = (timestamps >= start) & (timestamps < end)
        post_mask = (timestamps >= end) & (timestamps <= max_exit_end)
        month_values = predictions.get("dataset_month", pd.Series("", index=predictions.index))
        month_match = month_values.astype(str).eq(month)
        post_timestamps = timestamps[post_mask]
        rows.append(
            {
                "month": month,
                "evaluation_start": start,
                "evaluation_end": end,
                "max_exit_end": max_exit_end,
                "evaluation_prediction_rows": int(evaluation_mask.sum()),
                "post_exit_prediction_rows": int(post_mask.sum()),
                "dataset_month_rows": int(month_match.sum()),
                "first_prediction_timestamp": timestamps.min(),
                "last_prediction_timestamp": timestamps.max(),
                "first_post_exit_prediction_timestamp": (
                    post_timestamps.min() if not post_timestamps.empty else pd.NaT
                ),
                "last_post_exit_prediction_timestamp": (
                    post_timestamps.max() if not post_timestamps.empty else pd.NaT
                ),
                "has_post_exit_predictions": bool(post_mask.any()),
                "covers_full_max_exit_window": bool(
                    post_mask.any() and timestamps.max() >= max_exit_end
                ),
            }
        )
    return pd.DataFrame(rows)


def build_policy_config(
    base_config: dict[str, Any],
    *,
    predictions_path: Path,
    max_hold_minutes: float,
) -> ModelPolicyConfig:
    config = dict(base_config)
    config["predictions"] = predictions_path
    config["max_predicted_hold_minutes"] = max_hold_minutes
    return ModelPolicyConfig(**config)


def aggregate_metrics(metrics: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for keys, group in metrics.groupby(["cost_case", "variant", "max_hold"], sort=False):
        cost_case, variant, max_hold = keys
        rows.append(
            {
                "cost_case": cost_case,
                "variant": variant,
                "max_hold": float(max_hold),
                "months": int(group["month"].nunique()),
                "trades": int(group["trade_count"].sum()),
                "total_pnl": float(group["total_adjusted_pnl"].sum()),
                "worst_month": float(group["total_adjusted_pnl"].min()),
                "max_dd": float(group["max_drawdown"].max()),
                "mean_win_rate": float(group["win_rate"].mean()),
                "forced_exit_count": int(group["forced_exit_count"].sum()),
            }
        )
    return pd.DataFrame(rows).sort_values(
        ["cost_case", "total_pnl", "worst_month"],
        ascending=[True, False, False],
    )


def run_grid(
    *,
    base_config: dict[str, Any],
    predictions: pd.DataFrame,
    predictions_path: Path,
    months: list[str],
    max_holds: list[float],
    cost_cases: list[tuple[str, float, float, int]],
    data_path: Path,
    backtest_dir: Path,
    max_hold_hours: float,
    warmup_days: int,
    post_days: int,
    profit_multiplier: float,
    loss_multiplier: float,
) -> pd.DataFrame:
    all_data = read_ohlcv(data_path)
    rows: list[dict[str, Any]] = []
    for cost_label, spread, slippage, delay in cost_cases:
        for max_hold in max_holds:
            config = build_policy_config(
                base_config,
                predictions_path=predictions_path,
                max_hold_minutes=max_hold,
            )
            variant = f"{cost_label}_maxhold_{int(max_hold)}"
            for month in months:
                start, end = month_bounds(month)
                max_holding = pd.Timedelta(hours=max_hold_hours)
                data = slice_for_month(
                    all_data,
                    start=start,
                    end=end,
                    warmup_days=warmup_days,
                    post_days=post_days,
                    max_holding=max_holding,
                )
                backtest_config = BacktestConfig(
                    evaluation_start=start,
                    evaluation_end=end,
                    max_holding=max_holding,
                    profit_multiplier=profit_multiplier,
                    loss_multiplier=loss_multiplier,
                    spread_points=spread,
                    slippage_points=slippage,
                    execution_delay_bars=delay,
                )
                metrics, trades, curve, signal = run_model_policy(
                    data,
                    backtest_config,
                    config,
                    predictions=predictions,
                )
                run_dir = make_run_dir(backtest_dir / variant, f"model_{config.policy}_{month}")
                write_result(
                    run_dir,
                    metrics,
                    trades,
                    curve,
                    strategy_config=None,
                    backtest_config=backtest_config,
                    model_policy_config=config,
                )
                pd.DataFrame(
                    {"timestamp": data["timestamp"], "desired_position": signal}
                ).to_csv(run_dir / "desired_position.csv", index=False)
                rows.append(
                    {
                        "cost_case": cost_label,
                        "variant": variant,
                        "max_hold": float(max_hold),
                        "month": month,
                        "run_dir": str(run_dir),
                        **metrics,
                    }
                )
    return pd.DataFrame(rows)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-config", type=Path, required=True)
    parser.add_argument("--prediction-paths", type=parse_csv_paths, required=True)
    parser.add_argument("--months", required=True)
    parser.add_argument("--max-holds", default="240,480")
    parser.add_argument(
        "--cost-cases",
        default="nocost:0:0:0,coststress:0.2:0.1:1",
        help="comma-separated label:spread:slippage:delay cases",
    )
    parser.add_argument("--data", type=Path, default=Path("data/processed/histdata/xauusd/xauusd_m1.parquet"))
    parser.add_argument("--max-hold-hours", type=float, default=24.0)
    parser.add_argument("--warmup-days", type=int, default=7)
    parser.add_argument("--post-days", type=int, default=4)
    parser.add_argument("--profit-multiplier", type=float, default=1.0)
    parser.add_argument("--loss-multiplier", type=float, default=1.2)
    parser.add_argument("--label", default="holding_max_grid")
    parser.add_argument("--modeling-output-dir", type=Path, default=Path("data/reports/modeling"))
    parser.add_argument("--backtest-output-dir", type=Path, default=Path("data/reports/backtests"))
    parser.add_argument(
        "--require-post-coverage",
        action="store_true",
        help="fail if any month has no predictions after evaluation_end",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    months = parse_csv_strings(args.months)
    max_holds = parse_csv_floats(args.max_holds)
    cost_cases = parse_cost_cases(args.cost_cases)
    base_config = load_base_policy_config(args.base_config)
    required_columns = prediction_required_columns(
        build_policy_config(
            base_config,
            predictions_path=Path("__combined_predictions__.parquet"),
            max_hold_minutes=max_holds[0],
        )
    )
    predictions = merge_prediction_frames(
        args.prediction_paths,
        required_columns=required_columns,
    )

    modeling_dir = make_run_dir(args.modeling_output_dir, args.label)
    backtest_dir = make_run_dir(args.backtest_output_dir, args.label)
    predictions_path = modeling_dir / "predictions_holding_max_grid_input.parquet"
    predictions.to_parquet(predictions_path, index=False)

    coverage = prediction_coverage(
        predictions,
        months=months,
        max_hold_hours=args.max_hold_hours,
    )
    coverage.to_csv(modeling_dir / "prediction_coverage.csv", index=False)
    coverage.to_csv(backtest_dir / "prediction_coverage.csv", index=False)
    if args.require_post_coverage and not coverage["has_post_exit_predictions"].all():
        missing_months = ",".join(
            coverage.loc[~coverage["has_post_exit_predictions"], "month"].astype(str)
        )
        raise SystemExit(f"missing post-exit predictions for months: {missing_months}")

    by_month = run_grid(
        base_config=base_config,
        predictions=predictions,
        predictions_path=predictions_path,
        months=months,
        max_holds=max_holds,
        cost_cases=cost_cases,
        data_path=args.data,
        backtest_dir=backtest_dir,
        max_hold_hours=args.max_hold_hours,
        warmup_days=args.warmup_days,
        post_days=args.post_days,
        profit_multiplier=args.profit_multiplier,
        loss_multiplier=args.loss_multiplier,
    )
    summary = aggregate_metrics(by_month)
    by_month.to_csv(modeling_dir / "policy_summary.csv", index=False)
    by_month.to_csv(backtest_dir / "policy_summary.csv", index=False)
    summary.to_csv(modeling_dir / "policy_summary_by_variant.csv", index=False)
    summary.to_csv(backtest_dir / "policy_summary_by_variant.csv", index=False)

    manifest = {
        "mode": "holding_max_grid",
        "base_config": str(args.base_config),
        "prediction_paths": [str(path) for path in args.prediction_paths],
        "predictions": str(predictions_path),
        "modeling_dir": str(modeling_dir),
        "backtest_dir": str(backtest_dir),
        "months": months,
        "max_holds": max_holds,
        "cost_cases": [
            {
                "label": label,
                "spread_points": spread,
                "slippage_points": slippage,
                "execution_delay_bars": delay,
            }
            for label, spread, slippage, delay in cost_cases
        ],
        "max_hold_hours": args.max_hold_hours,
        "warmup_days": args.warmup_days,
        "post_days": args.post_days,
        "profit_multiplier": args.profit_multiplier,
        "loss_multiplier": args.loss_multiplier,
    }
    for directory in (modeling_dir, backtest_dir):
        (directory / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, default=local_json_default) + "\n",
            encoding="utf-8",
        )

    print(f"modeling artifacts: {modeling_dir}")
    print(f"backtest artifacts: {backtest_dir}")
    print(summary.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
