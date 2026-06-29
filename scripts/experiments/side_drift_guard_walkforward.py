#!/usr/bin/env python3
"""Walk-forward side-prior drift guard using prior prediction/trade diagnostics."""

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
SCRIPT_DIR = Path(__file__).resolve().parent
for path in (SRC, SCRIPT_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from side_drift_diagnostics import (  # noqa: E402
    SIDE_NAME_TO_VALUE,
    add_prediction_side_columns,
    enrich_trades_with_predictions,
    read_selected_trades,
)
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


def parse_optional_csv_strings(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def parse_csv_floats(value: str) -> list[float]:
    values = [float(part.strip()) for part in value.split(",") if part.strip()]
    if not values:
        raise argparse.ArgumentTypeError("at least one numeric value is required")
    return values


def parse_csv_paths(value: str) -> list[Path]:
    return [Path(part) for part in parse_csv_strings(value)]


def parse_cost_cases(value: str) -> list[tuple[str, float, float, int]]:
    cases: list[tuple[str, float, float, int]] = []
    for raw_case in parse_csv_strings(value):
        parts = [part.strip() for part in raw_case.split(":")]
        if len(parts) != 4:
            raise argparse.ArgumentTypeError("cost cases must use label:spread:slippage:delay")
        label, spread, slippage, delay = parts
        cases.append((label, float(spread), float(slippage), int(float(delay))))
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


def read_prediction_frames(paths: list[Path]) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for path in paths:
        frame = pd.read_parquet(path).copy()
        frame["source_path"] = str(path)
        frames.append(frame)
    if not frames:
        raise ValueError("at least one prediction path is required")
    combined = pd.concat(frames, ignore_index=True, sort=False)
    combined["decision_timestamp"] = pd.to_datetime(combined["decision_timestamp"], utc=True)
    duplicate_count = int(combined["decision_timestamp"].duplicated().sum())
    if duplicate_count:
        raise ValueError(f"combined predictions contain duplicate timestamps: {duplicate_count}")
    return combined.sort_values("decision_timestamp").reset_index(drop=True)


def read_selected_trades_from_summaries(
    paths: list[Path],
    *,
    months: list[str],
    variants: list[str],
    cost_cases: list[str],
) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for path in paths:
        frame = read_selected_trades(
            path,
            months=months,
            variants=variants,
            cost_cases=cost_cases,
        )
        if not frame.empty:
            frame["policy_summary_source"] = str(path)
            frames.append(frame)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True, sort=False)


def build_side_prediction_profile(
    predictions: pd.DataFrame,
    *,
    context_columns: list[str],
    side_name: str,
) -> pd.DataFrame:
    side_value = SIDE_NAME_TO_VALUE[side_name]
    missing = sorted(set(context_columns) - set(predictions.columns))
    if missing:
        raise ValueError(f"predictions missing context columns: {', '.join(missing)}")
    working = predictions.copy()
    for column in context_columns:
        working[column] = working[column].astype("string").fillna("__missing__")
    working["_is_pred_side"] = working["pred_ev_side"].astype(float).eq(float(side_value))
    working["_is_actual_label_side"] = working["actual_label_side"].astype(float).eq(float(side_value))
    profile = (
        working.groupby(context_columns, dropna=False, observed=True)
        .agg(
            prediction_rows=("pred_ev_side", "size"),
            prediction_month_count=("dataset_month", "nunique"),
            pred_side_share=("_is_pred_side", "mean"),
            actual_label_side_share=("_is_actual_label_side", "mean"),
        )
        .reset_index()
    )
    profile["side"] = side_name
    profile["side_share_bias"] = profile["pred_side_share"] - profile["actual_label_side_share"]
    return profile


def build_selected_trade_profile(
    trades: pd.DataFrame,
    *,
    context_columns: list[str],
    side_name: str,
) -> pd.DataFrame:
    side_value = SIDE_NAME_TO_VALUE[side_name]
    if trades.empty:
        return pd.DataFrame(columns=[*context_columns, "side"])
    missing = sorted(set(context_columns) - set(trades.columns))
    if missing:
        raise ValueError(f"trades missing context columns: {', '.join(missing)}")
    working = trades[trades["direction_side"].astype(float).eq(float(side_value))].copy()
    if working.empty:
        return pd.DataFrame(columns=[*context_columns, "side"])
    for column in context_columns:
        working[column] = working[column].astype("string").fillna("__missing__")
    working["_direction_error"] = pd.to_numeric(working["direction_error"], errors="coerce")
    profile = (
        working.groupby(context_columns, dropna=False, observed=True)
        .agg(
            selected_trade_count=("adjusted_pnl", "size"),
            selected_month_count=("month", "nunique"),
            selected_adjusted_pnl=("adjusted_pnl", "sum"),
            selected_avg_adjusted_pnl=("adjusted_pnl", "mean"),
            selected_direction_error_rate=("_direction_error", "mean"),
        )
        .reset_index()
    )
    profile["side"] = side_name
    return profile


def select_prior_guard_rules(
    prior_predictions: pd.DataFrame,
    prior_trades: pd.DataFrame,
    *,
    context_columns: list[str],
    sides: list[str],
    min_prediction_rows: int,
    min_prediction_months: int,
    min_side_bias: float,
    min_selected_trades: int,
    min_selected_months: int,
    max_selected_pnl: float,
) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    for side_name in sides:
        prediction_profile = build_side_prediction_profile(
            prior_predictions,
            context_columns=context_columns,
            side_name=side_name,
        )
        trade_profile = build_selected_trade_profile(
            prior_trades,
            context_columns=context_columns,
            side_name=side_name,
        )
        if trade_profile.empty:
            continue
        joined = prediction_profile.merge(
            trade_profile,
            on=[*context_columns, "side"],
            how="inner",
        )
        selected = joined[
            joined["prediction_rows"].ge(min_prediction_rows)
            & joined["prediction_month_count"].ge(min_prediction_months)
            & joined["side_share_bias"].ge(min_side_bias)
            & joined["selected_trade_count"].ge(min_selected_trades)
            & joined["selected_month_count"].ge(min_selected_months)
            & joined["selected_adjusted_pnl"].lt(max_selected_pnl)
        ].copy()
        if not selected.empty:
            rows.append(selected)
    if not rows:
        return pd.DataFrame(columns=[*context_columns, "side"])
    output = pd.concat(rows, ignore_index=True, sort=False)
    output["loss_bias_score"] = output["side_share_bias"] * (-output["selected_adjusted_pnl"].clip(upper=0))
    return output.sort_values(
        ["loss_bias_score", "side_share_bias", "selected_trade_count"],
        ascending=[False, False, False],
    ).reset_index(drop=True)


def context_rule(rule: pd.Series, context_columns: list[str], penalty: float) -> str:
    conditions = "+".join(f"{column}={rule[column]}" for column in context_columns)
    return f"{rule['side']}:{conditions}:{penalty:g}"


def build_policy_config(
    base_config: dict[str, Any],
    *,
    predictions_path: Path,
    max_predicted_hold_minutes: float,
    side_ev_penalty_rules: tuple[str, ...],
) -> ModelPolicyConfig:
    config = dict(base_config)
    config["predictions"] = predictions_path
    config["max_predicted_hold_minutes"] = max_predicted_hold_minutes
    config["side_ev_penalty_rules"] = tuple(config.get("side_ev_penalty_rules", ())) + side_ev_penalty_rules
    return ModelPolicyConfig(**config)


def aggregate_policy_summary(metrics: pd.DataFrame) -> pd.DataFrame:
    if metrics.empty:
        return pd.DataFrame()
    return (
        metrics.groupby(["cost_case", "variant", "penalty"], dropna=False, observed=True)
        .agg(
            months=("month", "nunique"),
            trades=("trade_count", "sum"),
            total_pnl=("total_adjusted_pnl", "sum"),
            worst_month=("total_adjusted_pnl", "min"),
            max_dd=("max_drawdown", "max"),
            mean_win_rate=("win_rate", "mean"),
            forced_exit_count=("forced_exit_count", "sum"),
            total_rule_count=("guard_rule_count", "sum"),
        )
        .reset_index()
        .sort_values(["cost_case", "total_pnl", "worst_month"], ascending=[True, False, False])
    )


def run_walkforward_guard(
    *,
    base_config: dict[str, Any],
    predictions: pd.DataFrame,
    predictions_path: Path,
    baseline_trades: pd.DataFrame,
    months: list[str],
    context_columns: list[str],
    sides: list[str],
    penalties: list[float],
    cost_cases: list[tuple[str, float, float, int]],
    data_path: Path,
    output_dir: Path,
    backtest_dir: Path,
    max_predicted_hold_minutes: float,
    max_hold_hours: float,
    warmup_days: int,
    post_days: int,
    profit_multiplier: float,
    loss_multiplier: float,
    min_prior_months: int,
    min_prediction_rows: int,
    min_prediction_months: int,
    min_side_bias: float,
    min_selected_trades: int,
    min_selected_months: int,
    max_selected_pnl: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    all_data = read_ohlcv(data_path)
    prediction_rows: list[pd.DataFrame] = []
    metrics_rows: list[dict[str, object]] = []

    timestamps = pd.to_datetime(predictions["decision_timestamp"], utc=True)
    for month in months:
        prior_months = [candidate for candidate in months if candidate < month]
        prior_predictions = predictions[predictions["dataset_month"].astype(str).isin(prior_months)].copy()
        prior_trades = baseline_trades[baseline_trades["month"].astype(str).isin(prior_months)].copy()
        if len(prior_months) >= min_prior_months and not prior_predictions.empty and not prior_trades.empty:
            selected_rules = select_prior_guard_rules(
                prior_predictions,
                prior_trades,
                context_columns=context_columns,
                sides=sides,
                min_prediction_rows=min_prediction_rows,
                min_prediction_months=min_prediction_months,
                min_side_bias=min_side_bias,
                min_selected_trades=min_selected_trades,
                min_selected_months=min_selected_months,
                max_selected_pnl=max_selected_pnl,
            )
        else:
            selected_rules = pd.DataFrame(columns=[*context_columns, "side"])
        selected_rules = selected_rules.copy()
        selected_rules["target_month"] = month
        selected_rules["prior_month_count"] = len(prior_months)
        prediction_rows.append(selected_rules)

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
        prediction_window = predictions[
            (timestamps >= start - pd.Timedelta(days=warmup_days))
            & (timestamps <= end + pd.Timedelta(days=post_days) + max_holding)
        ].copy()
        if prediction_window.empty:
            prediction_window = predictions.copy()

        for cost_label, spread, slippage, delay in cost_cases:
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
            for penalty in penalties:
                if penalty <= 0:
                    rule_strings: tuple[str, ...] = ()
                    variant = f"{cost_label}_no_guard"
                else:
                    rule_strings = tuple(
                        context_rule(row, context_columns, penalty)
                        for _, row in selected_rules.iterrows()
                    )
                    variant = f"{cost_label}_side_guard_p{penalty:g}".replace(".", "p")
                policy_config = build_policy_config(
                    base_config,
                    predictions_path=predictions_path,
                    max_predicted_hold_minutes=max_predicted_hold_minutes,
                    side_ev_penalty_rules=rule_strings,
                )
                run_dir = make_run_dir(backtest_dir / variant, f"model_{policy_config.policy}_{month}")
                metrics, trades, curve, _ = run_model_policy(
                    data,
                    backtest_config,
                    policy_config,
                    predictions=prediction_window,
                )
                write_result(run_dir, metrics, trades, curve, None, backtest_config, policy_config)
                row = dict(metrics)
                row.update(
                    {
                        "cost_case": cost_label,
                        "variant": variant,
                        "penalty": float(penalty),
                        "month": month,
                        "run_dir": str(run_dir),
                        "guard_rule_count": int(len(rule_strings)),
                        "guard_rules": ";".join(rule_strings),
                        "prior_month_count": int(len(prior_months)),
                    }
                )
                metrics_rows.append(row)
    non_empty_prediction_rows = [frame for frame in prediction_rows if not frame.empty]
    selected_by_month = (
        pd.concat(non_empty_prediction_rows, ignore_index=True, sort=False)
        if non_empty_prediction_rows
        else pd.DataFrame()
    )
    metrics = pd.DataFrame(metrics_rows)
    return selected_by_month, metrics


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-config", type=Path, required=True)
    parser.add_argument("--prediction-paths", type=parse_csv_paths, required=True)
    parser.add_argument("--policy-summaries", type=parse_csv_paths, required=True)
    parser.add_argument("--months", type=parse_csv_strings, required=True)
    parser.add_argument("--baseline-variants", type=parse_csv_strings, default=["coststress_maxhold_260"])
    parser.add_argument("--baseline-cost-cases", type=parse_csv_strings, default=["coststress"])
    parser.add_argument("--context-columns", type=parse_csv_strings, default=["combined_regime", "session_regime"])
    parser.add_argument("--sides", type=parse_csv_strings, default=["short", "long"])
    parser.add_argument("--penalties", type=parse_csv_floats, default=[0.0, 5.0, 10.0])
    parser.add_argument("--cost-cases", type=parse_cost_cases, default=[("coststress", 0.2, 0.1, 1)])
    parser.add_argument("--data", type=Path, default=Path("data/processed/xauusd_m1.parquet"))
    parser.add_argument("--max-predicted-hold-minutes", type=float, default=260.0)
    parser.add_argument("--max-hold-hours", type=float, default=24.0)
    parser.add_argument("--warmup-days", type=int, default=7)
    parser.add_argument("--post-days", type=int, default=4)
    parser.add_argument("--profit-multiplier", type=float, default=1.0)
    parser.add_argument("--loss-multiplier", type=float, default=1.2)
    parser.add_argument("--min-prior-months", type=int, default=3)
    parser.add_argument("--min-prediction-rows", type=int, default=100)
    parser.add_argument("--min-prediction-months", type=int, default=2)
    parser.add_argument("--min-side-bias", type=float, default=0.20)
    parser.add_argument("--min-selected-trades", type=int, default=5)
    parser.add_argument("--min-selected-months", type=int, default=2)
    parser.add_argument("--max-selected-pnl", type=float, default=0.0)
    parser.add_argument("--modeling-output-dir", type=Path, default=Path("data/reports/modeling"))
    parser.add_argument("--backtest-output-dir", type=Path, default=Path("data/reports/backtests"))
    parser.add_argument("--label", default="side_drift_guard_walkforward")
    args = parser.parse_args(argv)

    modeling_dir = make_run_dir(args.modeling_output_dir, args.label)
    backtest_dir = make_run_dir(args.backtest_output_dir, args.label)
    base_config = load_base_policy_config(args.base_config)
    raw_predictions = read_prediction_frames(args.prediction_paths)
    predictions = add_prediction_side_columns(
        raw_predictions,
        long_column=base_config.get("long_column", "pred_long_best_adjusted_pnl"),
        short_column=base_config.get("short_column", "pred_short_best_adjusted_pnl"),
    )
    predictions = predictions[predictions["dataset_month"].astype(str).isin(args.months)].copy()
    predictions_path = modeling_dir / "predictions_side_guard_input.parquet"
    predictions.to_parquet(predictions_path, index=False)

    baseline_trades = read_selected_trades_from_summaries(
        args.policy_summaries,
        months=args.months,
        variants=args.baseline_variants,
        cost_cases=args.baseline_cost_cases,
    )
    baseline_trades = enrich_trades_with_predictions(
        baseline_trades,
        predictions,
        long_column=base_config.get("long_column", "pred_long_best_adjusted_pnl"),
        short_column=base_config.get("short_column", "pred_short_best_adjusted_pnl"),
    )
    baseline_trades_path = modeling_dir / "baseline_enriched_trades.csv"
    baseline_trades.to_csv(baseline_trades_path, index=False)

    selected_rules, metrics = run_walkforward_guard(
        base_config=base_config,
        predictions=predictions,
        predictions_path=predictions_path,
        baseline_trades=baseline_trades,
        months=args.months,
        context_columns=args.context_columns,
        sides=args.sides,
        penalties=args.penalties,
        cost_cases=args.cost_cases,
        data_path=args.data,
        output_dir=modeling_dir,
        backtest_dir=backtest_dir,
        max_predicted_hold_minutes=args.max_predicted_hold_minutes,
        max_hold_hours=args.max_hold_hours,
        warmup_days=args.warmup_days,
        post_days=args.post_days,
        profit_multiplier=args.profit_multiplier,
        loss_multiplier=args.loss_multiplier,
        min_prior_months=args.min_prior_months,
        min_prediction_rows=args.min_prediction_rows,
        min_prediction_months=args.min_prediction_months,
        min_side_bias=args.min_side_bias,
        min_selected_trades=args.min_selected_trades,
        min_selected_months=args.min_selected_months,
        max_selected_pnl=args.max_selected_pnl,
    )
    selected_rules.to_csv(modeling_dir / "selected_guard_rules_by_month.csv", index=False)
    metrics.to_csv(backtest_dir / "policy_summary.csv", index=False)
    aggregate = aggregate_policy_summary(metrics)
    aggregate.to_csv(backtest_dir / "policy_summary_by_variant.csv", index=False)

    manifest = {
        "mode": "side_drift_guard_walkforward",
        "base_config": str(args.base_config),
        "prediction_paths": [str(path) for path in args.prediction_paths],
        "policy_summaries": [str(path) for path in args.policy_summaries],
        "modeling_dir": str(modeling_dir),
        "backtest_dir": str(backtest_dir),
        "predictions": str(predictions_path),
        "baseline_enriched_trades": str(baseline_trades_path),
        "months": args.months,
        "baseline_variants": args.baseline_variants,
        "baseline_cost_cases": args.baseline_cost_cases,
        "context_columns": args.context_columns,
        "sides": args.sides,
        "penalties": args.penalties,
        "cost_cases": [
            {
                "label": label,
                "spread_points": spread,
                "slippage_points": slippage,
                "execution_delay_bars": delay,
            }
            for label, spread, slippage, delay in args.cost_cases
        ],
        "thresholds": {
            "min_prior_months": args.min_prior_months,
            "min_prediction_rows": args.min_prediction_rows,
            "min_prediction_months": args.min_prediction_months,
            "min_side_bias": args.min_side_bias,
            "min_selected_trades": args.min_selected_trades,
            "min_selected_months": args.min_selected_months,
            "max_selected_pnl": args.max_selected_pnl,
        },
        "rows": {
            "predictions": int(len(predictions)),
            "baseline_trades": int(len(baseline_trades)),
            "selected_rule_rows": int(len(selected_rules)),
            "policy_rows": int(len(metrics)),
        },
    }
    (modeling_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, default=local_json_default) + "\n",
        encoding="utf-8",
    )
    (backtest_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, default=local_json_default) + "\n",
        encoding="utf-8",
    )
    print(f"modeling artifacts: {modeling_dir}")
    print(f"backtest artifacts: {backtest_dir}")
    if not aggregate.empty:
        print(
            aggregate[
                [
                    "cost_case",
                    "variant",
                    "penalty",
                    "months",
                    "trades",
                    "total_pnl",
                    "worst_month",
                    "max_dd",
                    "forced_exit_count",
                    "total_rule_count",
                ]
            ].to_string(index=False)
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
