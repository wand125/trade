#!/usr/bin/env python3
"""Run exit-timing sensitivity for entry-EV quantile policies."""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from trade_data.backtest import (  # noqa: E402
    json_default,
    make_run_dir,
    read_ohlcv,
    run_model_policy,
    slice_for_month,
)

from entry_ev_quantile_policy_backtest import (  # noqa: E402
    build_backtest_config,
    build_model_policy_config,
    local_json_default,
    parse_family_predictions,
    parse_optional_csv,
    parse_policy_candidates,
    parse_role_months,
    policy_candidate_from_name,
    prediction_months,
    summarize_by_group,
)


DEFAULT_CANDIDATES = (
    "q95_sg95_rank90_floor5_side_regime_session_month",
    "q99_sg95_rank90_floor5_side_regime_session_month",
)

DEFAULT_VARIANTS = (
    "base:0:0:inf:inf",
    "time_shrink25:0.25:0:inf:inf",
    "time_shrink50:0.5:0:inf:inf",
    "loss_shrink25:0:0.25:inf:inf",
    "loss_shrink50:0:0.5:inf:inf",
    "loss_shrink75:0:0.75:inf:inf",
    "both_shrink25:0.25:0.25:inf:inf",
    "both_shrink50:0.5:0.5:inf:inf",
    "loss_exit75:0:0:inf:0.75",
    "loss_exit90:0:0:inf:0.90",
    "time_exit90:0:0:0.90:inf",
    "both_exit90_75:0:0:0.90:0.75",
)


@dataclass(frozen=True)
class ExitTimingVariant:
    label: str
    time_exit_holding_shrink: float
    loss_first_holding_shrink: float
    time_exit_exit_threshold: float
    loss_first_exit_threshold: float


def parse_float_token(value: str) -> float:
    text = value.strip().lower()
    if text in {"inf", "+inf", "infinity", "+infinity"}:
        return float("inf")
    return float(text)


def validate_probability_or_inf(value: float, *, name: str) -> None:
    if math.isinf(value):
        if value > 0:
            return
        raise argparse.ArgumentTypeError(f"{name} must be non-negative infinity or 0..1")
    if not 0.0 <= value <= 1.0:
        raise argparse.ArgumentTypeError(f"{name} must be between 0 and 1 or inf")


def parse_exit_timing_variant(value: str) -> ExitTimingVariant:
    parts = [part.strip() for part in value.split(":")]
    if len(parts) != 5:
        raise argparse.ArgumentTypeError(
            "variant must use label:time_shrink:loss_shrink:time_exit_threshold:"
            "loss_exit_threshold"
        )
    label = parts[0]
    if not label:
        raise argparse.ArgumentTypeError("variant label must not be empty")
    if any(char in label for char in ",: \t\n"):
        raise argparse.ArgumentTypeError("variant label must not contain comma, colon, or space")
    time_shrink = parse_float_token(parts[1])
    loss_shrink = parse_float_token(parts[2])
    time_exit = parse_float_token(parts[3])
    loss_exit = parse_float_token(parts[4])
    validate_probability_or_inf(time_shrink, name="time_shrink")
    validate_probability_or_inf(loss_shrink, name="loss_shrink")
    validate_probability_or_inf(time_exit, name="time_exit_threshold")
    validate_probability_or_inf(loss_exit, name="loss_exit_threshold")
    if math.isinf(time_shrink) or math.isinf(loss_shrink):
        raise argparse.ArgumentTypeError("holding shrinks must be finite 0..1 values")
    return ExitTimingVariant(
        label=label,
        time_exit_holding_shrink=time_shrink,
        loss_first_holding_shrink=loss_shrink,
        time_exit_exit_threshold=time_exit,
        loss_first_exit_threshold=loss_exit,
    )


def parse_exit_timing_variants(value: str) -> list[ExitTimingVariant]:
    variants = [
        parse_exit_timing_variant(part)
        for part in value.split(",")
        if part.strip()
    ]
    if not variants:
        raise argparse.ArgumentTypeError("at least one exit-timing variant is required")
    labels = [variant.label for variant in variants]
    duplicates = sorted({label for label in labels if labels.count(label) > 1})
    if duplicates:
        raise argparse.ArgumentTypeError(f"duplicate variant labels: {', '.join(duplicates)}")
    return variants


def serializable_variant(variant: ExitTimingVariant) -> dict[str, Any]:
    data = asdict(variant)
    for key, value in list(data.items()):
        if isinstance(value, float) and math.isinf(value):
            data[key] = "inf"
    return data


def local_default(value: Any) -> Any:
    try:
        return local_json_default(value)
    except TypeError:
        return json_default(value)


def summarize_candidates(
    monthly: pd.DataFrame,
    *,
    min_role_trades: int,
    min_month_trades: int,
    max_side_trade_share: float,
) -> pd.DataFrame:
    role_summary = summarize_by_group(monthly, ["variant", "role", "candidate"])
    if role_summary.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    for key, group in role_summary.groupby(["variant", "candidate"], dropna=False):
        variant, candidate = key
        role_totals = group["total_adjusted_pnl_sum"].astype(float)
        role_trades = group["trade_count_sum"].astype(float)
        month_group = monthly[
            monthly["variant"].astype(str).eq(str(variant))
            & monthly["candidate"].astype(str).eq(str(candidate))
        ]
        month_trades = month_group["trade_count"].astype(float)
        row = {
            "variant": variant,
            "candidate": candidate,
            "role_count": int(group["role"].nunique()),
            "positive_role_count": int((role_totals > 0).sum()),
            "active_role_count": int((role_trades > 0).sum()),
            "total_adjusted_pnl_sum": float(role_totals.sum()),
            "role_total_pnl_min": float(role_totals.min()),
            "role_total_pnl_max": float(role_totals.max()),
            "trade_count_sum": int(role_trades.sum()),
            "role_trade_count_min": int(role_trades.min()),
            "month_pnl_min": float(month_group["total_adjusted_pnl"].astype(float).min()),
            "month_trade_count_min": int(month_trades.min()),
            "max_drawdown_max": float(month_group["max_drawdown"].astype(float).max()),
            "max_side_trade_share": float(group["max_side_trade_share"].astype(float).max()),
        }
        blockers: list[str] = []
        if row["positive_role_count"] < row["role_count"]:
            blockers.append("positive_roles_low")
        if row["total_adjusted_pnl_sum"] <= 0:
            blockers.append("total_pnl_below_floor")
        if row["role_total_pnl_min"] <= 0:
            blockers.append("role_total_pnl_below_floor")
        if row["month_pnl_min"] < 0:
            blockers.append("month_pnl_below_floor")
        if row["role_trade_count_min"] < min_role_trades:
            blockers.append("role_trades_low")
        if row["month_trade_count_min"] < min_month_trades:
            blockers.append("month_trades_low")
        if row["max_side_trade_share"] > max_side_trade_share:
            blockers.append("side_share_high")
        row["selector_pass"] = not blockers
        row["blockers"] = ",".join(blockers)
        rows.append(row)
    return pd.DataFrame(rows).sort_values(
        ["selector_pass", "role_total_pnl_min", "total_adjusted_pnl_sum", "trade_count_sum"],
        ascending=[False, False, False, False],
    ).reset_index(drop=True)


def select_policy(candidate_summary: pd.DataFrame) -> dict[str, Any]:
    if candidate_summary.empty:
        return {"selected": "NoTrade", "reason": "empty_candidate_summary"}
    eligible = candidate_summary[candidate_summary["selector_pass"].astype(bool)]
    if eligible.empty:
        return {
            "selected": "NoTrade",
            "reason": "no_candidate_passed_notrade_first_gates",
        }
    row = eligible.iloc[0].to_dict()
    return {
        "selected": row["candidate"],
        "variant": row["variant"],
        "reason": "best_passing_candidate_by_role_worst_then_total",
        "row": row,
    }


def run_sensitivity(args: argparse.Namespace) -> Path:
    family_predictions = parse_family_predictions(args.family_predictions)
    candidate_names = parse_policy_candidates(args.policy_candidates)
    role_lookup = parse_role_months(args.role_months)
    requested_roles = set(parse_optional_csv(args.roles))
    requested_months = set(parse_optional_csv(args.months))
    variants = parse_exit_timing_variants(args.variants)
    candidates = [policy_candidate_from_name(name) for name in candidate_names]

    run_dir = make_run_dir(args.output_dir, args.label)
    price_data = read_ohlcv(args.data)
    monthly_rows: list[dict[str, Any]] = []
    config_rows = [asdict(candidate) for candidate in candidates]

    for family, prediction_path in family_predictions.items():
        predictions = pd.read_parquet(prediction_path)
        months = prediction_months(predictions)
        if requested_months:
            months = [month for month in months if month in requested_months]
        if not months:
            raise ValueError(f"no evaluation months for family: {family}")

        for candidate in candidates:
            base_model_config = build_model_policy_config(
                prediction_path=prediction_path,
                candidate=candidate,
                score_kind=args.score_kind,
                long_column=args.long_column,
                short_column=args.short_column,
                long_holding_column=args.long_holding_column,
                short_holding_column=args.short_holding_column,
                min_valid_predicted_hold_minutes=args.min_valid_predicted_hold_minutes,
                max_predicted_hold_minutes=args.max_predicted_hold_minutes,
            )
            for variant in variants:
                model_config = replace(
                    base_model_config,
                    time_exit_holding_shrink=variant.time_exit_holding_shrink,
                    loss_first_holding_shrink=variant.loss_first_holding_shrink,
                    time_exit_exit_threshold=variant.time_exit_exit_threshold,
                    loss_first_exit_threshold=variant.loss_first_exit_threshold,
                )
                for month in months:
                    role = role_lookup.get((family, month), family)
                    if requested_roles and role not in requested_roles:
                        continue
                    backtest_config = build_backtest_config(
                        month=month,
                        max_hold_hours=args.max_hold_hours,
                        profit_multiplier=args.profit_multiplier,
                        loss_multiplier=args.loss_multiplier,
                        spread_points=args.spread_points,
                        slippage_points=args.slippage_points,
                        execution_delay_bars=args.execution_delay_bars,
                    )
                    df = slice_for_month(
                        price_data,
                        start=backtest_config.evaluation_start,
                        end=backtest_config.evaluation_end,
                        warmup_days=args.warmup_days,
                        post_days=args.post_days,
                        max_holding=backtest_config.max_holding,
                    )
                    metrics, trades, _curve, signal = run_model_policy(
                        df,
                        backtest_config,
                        model_config,
                        predictions=predictions,
                    )
                    monthly_rows.append(
                        {
                            "family": family,
                            "role": role,
                            "month": month,
                            "candidate": candidate.name,
                            "variant": variant.label,
                            **serializable_variant(variant),
                            **asdict(candidate),
                            **metrics,
                        }
                    )
                    if args.write_trades:
                        trade_path = run_dir / "trades" / family / variant.label / candidate.name
                        trade_path.mkdir(parents=True, exist_ok=True)
                        trades.to_csv(trade_path / f"{month}.csv", index=False)
                        pd.DataFrame(
                            {
                                "timestamp": df["timestamp"],
                                "desired_position": signal,
                            }
                        ).to_csv(trade_path / f"{month}_desired_position.csv", index=False)

    if not monthly_rows:
        raise ValueError("no monthly backtests were executed")

    monthly = pd.DataFrame(monthly_rows)
    monthly.to_csv(run_dir / "monthly_exit_timing_metrics.csv", index=False)
    pd.DataFrame(config_rows).to_csv(run_dir / "policy_candidates.csv", index=False)

    role_summary = summarize_by_group(monthly, ["variant", "role", "candidate"])
    role_summary.to_csv(run_dir / "role_exit_timing_summary.csv", index=False)
    variant_summary = summarize_by_group(monthly, ["variant"])
    variant_summary.to_csv(run_dir / "variant_exit_timing_summary.csv", index=False)
    candidate_summary = summarize_candidates(
        monthly,
        min_role_trades=args.min_role_trades,
        min_month_trades=args.min_month_trades,
        max_side_trade_share=args.max_side_trade_share,
    )
    candidate_summary.to_csv(run_dir / "candidate_exit_timing_selection_summary.csv", index=False)
    selected = select_policy(candidate_summary)
    (run_dir / "selected_policy.json").write_text(
        json.dumps(selected, indent=2, default=local_default),
        encoding="utf-8",
    )
    config = {
        "family_predictions": family_predictions,
        "policy_candidates": candidate_names,
        "variants": [serializable_variant(variant) for variant in variants],
        "role_months": args.role_months,
        "roles": sorted(requested_roles),
        "months": sorted(requested_months),
        "data": args.data,
        "score_kind": args.score_kind,
        "long_column": args.long_column,
        "short_column": args.short_column,
        "long_holding_column": args.long_holding_column,
        "short_holding_column": args.short_holding_column,
        "min_valid_predicted_hold_minutes": args.min_valid_predicted_hold_minutes,
        "max_predicted_hold_minutes": args.max_predicted_hold_minutes,
        "max_hold_hours": args.max_hold_hours,
        "profit_multiplier": args.profit_multiplier,
        "loss_multiplier": args.loss_multiplier,
        "spread_points": args.spread_points,
        "slippage_points": args.slippage_points,
        "execution_delay_bars": args.execution_delay_bars,
        "warmup_days": args.warmup_days,
        "post_days": args.post_days,
        "min_role_trades": args.min_role_trades,
        "min_month_trades": args.min_month_trades,
        "max_side_trade_share": args.max_side_trade_share,
        "write_trades": args.write_trades,
    }
    (run_dir / "config.json").write_text(
        json.dumps(config, indent=2, default=local_default),
        encoding="utf-8",
    )

    print("Variant summary:")
    print(
        variant_summary[
            [
                "variant",
                "total_adjusted_pnl_sum",
                "total_adjusted_pnl_min",
                "trade_count_sum",
                "max_drawdown_max",
                "max_side_trade_share",
            ]
        ].to_string(index=False)
    )
    print("\nTop candidate/variant rows:")
    print(
        candidate_summary[
            [
                "variant",
                "candidate",
                "selector_pass",
                "total_adjusted_pnl_sum",
                "role_total_pnl_min",
                "month_pnl_min",
                "trade_count_sum",
                "blockers",
            ]
        ].head(30).to_string(index=False)
    )
    print(f"\nselected: {selected['selected']}")
    print(f"artifacts: {run_dir}")
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--family-predictions", action="append", required=True)
    parser.add_argument("--policy-candidates", default=",".join(DEFAULT_CANDIDATES))
    parser.add_argument("--variants", default=",".join(DEFAULT_VARIANTS))
    parser.add_argument("--roles", default="")
    parser.add_argument("--months", default="")
    parser.add_argument("--role-months", action="append", default=[])
    parser.add_argument(
        "--data",
        type=Path,
        default=Path("data/processed/histdata/xauusd/xauusd_m1.parquet"),
    )
    parser.add_argument("--score-kind", default="calibrated")
    parser.add_argument("--long-column", default="pred_calibrated_long_best_adjusted_pnl")
    parser.add_argument("--short-column", default="pred_calibrated_short_best_adjusted_pnl")
    parser.add_argument("--long-holding-column", default="pred_mlp_long_exit_event_minutes")
    parser.add_argument("--short-holding-column", default="pred_mlp_short_exit_event_minutes")
    parser.add_argument("--min-valid-predicted-hold-minutes", type=float, default=30.0)
    parser.add_argument("--max-predicted-hold-minutes", type=float, default=260.0)
    parser.add_argument("--max-hold-hours", type=float, default=24.0)
    parser.add_argument("--profit-multiplier", type=float, default=1.0)
    parser.add_argument("--loss-multiplier", type=float, default=1.2)
    parser.add_argument("--spread-points", type=float, default=0.0)
    parser.add_argument("--slippage-points", type=float, default=0.0)
    parser.add_argument("--execution-delay-bars", type=int, default=0)
    parser.add_argument("--warmup-days", type=int, default=7)
    parser.add_argument("--post-days", type=int, default=4)
    parser.add_argument("--min-role-trades", type=int, default=10)
    parser.add_argument("--min-month-trades", type=int, default=10)
    parser.add_argument("--max-side-trade-share", type=float, default=0.95)
    parser.add_argument("--write-trades", action="store_true")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/reports/backtests"),
    )
    parser.add_argument("--label", default="entry_ev_quantile_exit_timing_sensitivity")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    run_sensitivity(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
