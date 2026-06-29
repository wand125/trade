#!/usr/bin/env python3
"""Evaluate small interaction-risk overlays for the fixed high-cost policy."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

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
    read_ohlcv,
    run_model_policy,
    slice_for_month,
    write_result,
)


STATEFUL_PREFIX = "pred_stateful_risk_wf_exp_session_mm_walkforward_floor_lowered"
PREDHIT_PREFIX = "pred_trade_failure_pred_hit_actual_miss"
EVHIGH_PREFIX = "pred_trade_failure_ev_overestimate_high"
Q75_PREFIX = "pred_trade_overestimate_high_q75"


def parse_csv_floats(value: str) -> list[float]:
    values = [float(part.strip()) for part in value.split(",") if part.strip()]
    if not values:
        raise argparse.ArgumentTypeError("at least one float is required")
    return values


def parse_csv_strings(value: str) -> list[str]:
    values = [part.strip() for part in value.split(",") if part.strip()]
    if not values:
        raise argparse.ArgumentTypeError("at least one string is required")
    return values


def weight_label(value: float) -> str:
    return f"{value:g}".replace(".", "p").replace("-", "m")


def read_and_filter(path: Path, months: list[str]) -> pd.DataFrame:
    frame = pd.read_parquet(path)
    if "dataset_month" not in frame.columns:
        raise ValueError(f"{path} is missing dataset_month")
    return frame[frame["dataset_month"].astype(str).isin(months)].copy()


def combine_predictions(validation_path: Path, apply_path: Path, months: list[str]) -> pd.DataFrame:
    validation = read_and_filter(validation_path, months)
    apply = read_and_filter(apply_path, months)
    combined = pd.concat([validation, apply], ignore_index=True)
    missing_months = sorted(set(months) - set(combined["dataset_month"].astype(str).unique()))
    if missing_months:
        raise ValueError(f"combined predictions missing months: {', '.join(missing_months)}")
    combined["decision_timestamp"] = pd.to_datetime(combined["decision_timestamp"], utc=True)
    duplicated = combined["decision_timestamp"].duplicated()
    if duplicated.any():
        raise ValueError(f"combined predictions contain duplicate decision_timestamp rows: {int(duplicated.sum())}")
    return combined.sort_values("decision_timestamp").reset_index(drop=True)


def require_columns(frame: pd.DataFrame, columns: list[str]) -> None:
    missing = sorted(set(columns) - set(frame.columns))
    if missing:
        raise ValueError(f"predictions are missing columns: {', '.join(missing)}")


def add_interaction_risks(frame: pd.DataFrame, weights: list[float]) -> tuple[pd.DataFrame, pd.DataFrame]:
    output = frame.copy()
    summary_rows: list[dict[str, object]] = []
    required = [
        f"{STATEFUL_PREFIX}_{side}_risk"
        for side in ("long", "short")
    ] + [
        f"{prefix}_{side}_prob"
        for prefix in (PREDHIT_PREFIX, EVHIGH_PREFIX, Q75_PREFIX)
        for side in ("long", "short")
    ]
    require_columns(output, required)

    for side in ("long", "short"):
        predhit = pd.to_numeric(output[f"{PREDHIT_PREFIX}_{side}_prob"], errors="raise").clip(0.0, 1.0)
        evhigh = pd.to_numeric(output[f"{EVHIGH_PREFIX}_{side}_prob"], errors="raise").clip(0.0, 1.0)
        q75 = pd.to_numeric(output[f"{Q75_PREFIX}_{side}_prob"], errors="raise").clip(0.0, 1.0)
        output[f"pred_interaction_predhit_evhigh_{side}_risk"] = -(predhit * evhigh)
        output[f"pred_interaction_predhit_q75_{side}_risk"] = -(predhit * q75)
        for name in ("predhit_evhigh", "predhit_q75"):
            interaction = output[f"pred_interaction_{name}_{side}_risk"]
            for weight in weights:
                label = weight_label(weight)
                column = f"pred_combined_floor_{name}_w{label}_{side}_risk"
                output[column] = (
                    pd.to_numeric(output[f"{STATEFUL_PREFIX}_{side}_risk"], errors="raise")
                    + (weight / 5.0) * interaction
                )
        for column in [
            f"pred_interaction_predhit_evhigh_{side}_risk",
            f"pred_interaction_predhit_q75_{side}_risk",
        ]:
            values = -pd.to_numeric(output[column], errors="raise")
            summary_rows.append(
                {
                    "column": column,
                    "side": side,
                    "mean_positive_risk": float(values.mean()),
                    "p75_positive_risk": float(values.quantile(0.75)),
                    "p90_positive_risk": float(values.quantile(0.90)),
                    "max_positive_risk": float(values.max()),
                    "nonzero_rate": float((values > 0).mean()),
                }
            )
    return output, pd.DataFrame(summary_rows)


def base_policy_config(predictions_path: Path, *, risk_penalty: float, long_risk: str, short_risk: str) -> ModelPolicyConfig:
    return ModelPolicyConfig(
        predictions=predictions_path,
        policy="timed_ev",
        entry_threshold=12.0,
        short_entry_threshold_offset=6.0,
        side_margin=5.0,
        long_column="pred_long_best_adjusted_pnl",
        short_column="pred_short_best_adjusted_pnl",
        long_risk_column=long_risk,
        short_risk_column=short_risk,
        risk_penalty=risk_penalty,
        long_holding_column="pred_mlp_long_exit_event_minutes",
        short_holding_column="pred_mlp_short_exit_event_minutes",
        min_predicted_hold_minutes=1.0,
        max_predicted_hold_minutes=480.0,
        min_valid_predicted_hold_minutes=30.0,
        fixed_horizon_minutes=(60.0, 240.0, 720.0),
        long_fixed_horizon_columns=(
            "pred_long_fixed_60m_adjusted_pnl",
            "pred_long_fixed_240m_adjusted_pnl",
            "pred_long_fixed_720m_adjusted_pnl",
        ),
        short_fixed_horizon_columns=(
            "pred_short_fixed_60m_adjusted_pnl",
            "pred_short_fixed_240m_adjusted_pnl",
            "pred_short_fixed_720m_adjusted_pnl",
        ),
        fixed_horizon_score_mode="max",
        long_wait_regret_column="pred_long_wait_regret",
        short_wait_regret_column="pred_short_wait_regret",
        long_entry_rank_column="pred_long_entry_local_rank",
        short_entry_rank_column="pred_short_entry_local_rank",
        long_profit_barrier_column="pred_long_profit_barrier_hit",
        short_profit_barrier_column="pred_short_profit_barrier_hit",
        long_time_exit_column="pred_long_exit_event_prob_0",
        short_time_exit_column="pred_short_exit_event_prob_0",
        long_loss_first_column="pred_long_exit_event_prob_2",
        short_loss_first_column="pred_short_exit_event_prob_2",
        long_side_confidence_column="pred_best_side_prob_1",
        short_side_confidence_column="pred_best_side_prob_-1",
        long_trade_quality_column="pred_trade_quality_long_adjusted_pnl",
        short_trade_quality_column="pred_trade_quality_short_adjusted_pnl",
        min_entry_rank=0.5,
        side_ev_penalty_rules=(
            "short:combined_regime=down_low_vol:5",
            "short:combined_regime=up_low_vol:10",
        ),
    )


def policy_configs(predictions_path: Path, weights: list[float]) -> list[tuple[str, ModelPolicyConfig]]:
    configs: list[tuple[str, ModelPolicyConfig]] = [
        (
            "risk0",
            base_policy_config(
                predictions_path,
                risk_penalty=0.0,
                long_risk=f"{STATEFUL_PREFIX}_long_risk",
                short_risk=f"{STATEFUL_PREFIX}_short_risk",
            ),
        ),
        (
            "baseline_risk5",
            base_policy_config(
                predictions_path,
                risk_penalty=5.0,
                long_risk=f"{STATEFUL_PREFIX}_long_risk",
                short_risk=f"{STATEFUL_PREFIX}_short_risk",
            ),
        ),
    ]
    for name in ("predhit_evhigh", "predhit_q75"):
        for weight in weights:
            label = weight_label(weight)
            configs.append(
                (
                    f"{name}_w{label}",
                    base_policy_config(
                        predictions_path,
                        risk_penalty=5.0,
                        long_risk=f"pred_combined_floor_{name}_w{label}_long_risk",
                        short_risk=f"pred_combined_floor_{name}_w{label}_short_risk",
                    ),
                )
            )
    return configs


def aggregate_metrics(metrics: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for label, group in metrics.groupby("label", sort=False):
        rows.append(
            {
                "label": label,
                "total_adjusted_pnl": float(group["total_adjusted_pnl"].sum()),
                "min_month_adjusted_pnl": float(group["total_adjusted_pnl"].min()),
                "max_monthly_drawdown": float(group["max_drawdown"].max()),
                "trade_count": int(group["trade_count"].sum()),
                "forced_exit_count": int(group["forced_exit_count"].sum()),
                "mean_win_rate": float(group["win_rate"].mean()),
                "months": ",".join(group["month"].astype(str)),
            }
        )
    return pd.DataFrame(rows).sort_values(
        ["total_adjusted_pnl", "min_month_adjusted_pnl"],
        ascending=[False, False],
    )


def serializable_policy_config(config: ModelPolicyConfig) -> dict[str, object]:
    data = asdict(config)
    data["predictions"] = str(config.predictions)
    return data


def run_policy_grid(
    *,
    predictions_path: Path,
    predictions: pd.DataFrame,
    months: list[str],
    data_path: Path,
    backtest_dir: Path,
    weights: list[float],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    all_data = read_ohlcv(data_path)
    metrics_rows: list[dict[str, object]] = []
    for label, config in policy_configs(predictions_path, weights):
        for month in months:
            start, end = month_bounds(month)
            max_holding = pd.Timedelta(hours=24)
            data = slice_for_month(
                all_data,
                start=start,
                end=end,
                warmup_days=7,
                post_days=4,
                max_holding=max_holding,
            )
            backtest_config = BacktestConfig(
                evaluation_start=start,
                evaluation_end=end,
                max_holding=max_holding,
                profit_multiplier=1.0,
                loss_multiplier=1.2,
                spread_points=0.2,
                slippage_points=0.1,
                execution_delay_bars=1,
            )
            metrics, trades, curve, signal = run_model_policy(
                data,
                backtest_config,
                config,
                predictions=predictions,
            )
            run_dir = make_run_dir(backtest_dir, f"{label}_{month}")
            write_result(
                run_dir,
                metrics,
                trades,
                curve,
                strategy_config=None,
                backtest_config=backtest_config,
                model_policy_config=config,
            )
            pd.DataFrame({"timestamp": data["timestamp"], "desired_position": signal}).to_csv(
                run_dir / "desired_position.csv",
                index=False,
            )
            metrics_rows.append(
                {
                    "label": label,
                    "month": month,
                    "run_dir": str(run_dir),
                    **metrics,
                }
            )
    by_month = pd.DataFrame(metrics_rows)
    summary = aggregate_metrics(by_month)
    return by_month, summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--validation-predictions",
        type=Path,
        default=Path(
            "experiments/20260629_073137_trade_overestimate_high_q75_expanding_min3_highcost_risk5/"
            "predictions_validation_oof_trade_overestimate_high_model.parquet"
        ),
    )
    parser.add_argument(
        "--apply-predictions",
        type=Path,
        default=Path(
            "experiments/20260629_073137_trade_overestimate_high_q75_expanding_min3_highcost_risk5/"
            "predictions_apply_trade_overestimate_high_model.parquet"
        ),
    )
    parser.add_argument(
        "--data",
        type=Path,
        default=Path("data/processed/histdata/xauusd/xauusd_m1.parquet"),
    )
    parser.add_argument("--months", default="2025-02,2025-03,2025-04,2025-05")
    parser.add_argument("--weights", default="1,2,5,10")
    parser.add_argument("--label", default="predhit_overestimate_interaction_2025_02_05")
    parser.add_argument("--modeling-output-dir", type=Path, default=Path("data/reports/modeling"))
    parser.add_argument("--backtest-output-dir", type=Path, default=Path("data/reports/backtests"))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    months = parse_csv_strings(args.months)
    weights = parse_csv_floats(args.weights)

    modeling_dir = make_run_dir(args.modeling_output_dir, args.label)
    backtest_dir = make_run_dir(args.backtest_output_dir, args.label)

    combined = combine_predictions(args.validation_predictions, args.apply_predictions, months)
    scored, risk_summary = add_interaction_risks(combined, weights)
    predictions_path = modeling_dir / "predictions_interaction_risk.parquet"
    scored.to_parquet(predictions_path, index=False)
    risk_summary.to_csv(modeling_dir / "risk_column_summary.csv", index=False)

    by_month, summary = run_policy_grid(
        predictions_path=predictions_path,
        predictions=scored,
        months=months,
        data_path=args.data,
        backtest_dir=backtest_dir,
        weights=weights,
    )
    by_month.to_csv(modeling_dir / "policy_metrics_by_month.csv", index=False)
    summary.to_csv(modeling_dir / "policy_metrics_summary.csv", index=False)
    by_month.to_csv(backtest_dir / "policy_metrics_by_month.csv", index=False)
    summary.to_csv(backtest_dir / "policy_metrics_summary.csv", index=False)

    manifest = {
        "mode": "predhit_overestimate_interaction",
        "validation_predictions": str(args.validation_predictions),
        "apply_predictions": str(args.apply_predictions),
        "predictions": str(predictions_path),
        "modeling_dir": str(modeling_dir),
        "backtest_dir": str(backtest_dir),
        "months": months,
        "weights": weights,
        "stateful_prefix": STATEFUL_PREFIX,
        "interaction_columns": [
            "pred_interaction_predhit_evhigh_<side>_risk",
            "pred_interaction_predhit_q75_<side>_risk",
        ],
        "policy": {
            "profit_multiplier": 1.0,
            "loss_multiplier": 1.2,
            "spread_points": 0.2,
            "slippage_points": 0.1,
            "execution_delay_bars": 1,
            "entry_threshold": 12.0,
            "short_entry_threshold_offset": 6.0,
            "side_margin": 5.0,
            "risk_penalty": 5.0,
            "side_ev_penalty_rules": [
                "short:combined_regime=down_low_vol:5",
                "short:combined_regime=up_low_vol:10",
            ],
        },
        "policy_configs": [
            {"label": label, "config": serializable_policy_config(config)}
            for label, config in policy_configs(predictions_path, weights)
        ],
    }
    for path in (modeling_dir / "manifest.json", backtest_dir / "manifest.json"):
        with path.open("w", encoding="utf-8") as handle:
            json.dump(manifest, handle, ensure_ascii=False, indent=2, default=json_default)

    print("modeling_dir:", modeling_dir)
    print("backtest_dir:", backtest_dir)
    print(summary.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
