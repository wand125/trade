#!/usr/bin/env python3
"""Run hold-cap sensitivity for entry-EV quantile policies."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, replace
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


DEFAULT_Q95_Q99_CANDIDATES = (
    "q95_sg95_rank90_floor5_side_regime_session_month",
    "q95_sg95_rank90_floor10_side_regime_session_month",
    "q99_sg95_rank90_floor5_side_regime_session_month",
    "q99_sg95_rank90_floor10_side_regime_session_month",
)


def parse_float_csv(value: str) -> list[float]:
    values = [float(part.strip()) for part in value.split(",") if part.strip()]
    if not values:
        raise argparse.ArgumentTypeError("at least one numeric value is required")
    return values


def rule_for_context(direction: str, combined_regime: str, session_regime: str) -> str:
    return (
        f"{direction}:combined_regime={combined_regime}"
        f"+session_regime={session_regime}"
    )


def derive_context_side_block_rules(
    context_summary: pd.DataFrame,
    *,
    roles: set[str],
    candidates: set[str],
    min_trade_count: int,
    min_direction_error_rate: float,
    max_total_pnl: float,
) -> tuple[list[str], pd.DataFrame]:
    required = {
        "role",
        "candidate",
        "direction",
        "combined_regime",
        "session_regime",
        "trade_count",
        "total_adjusted_pnl",
        "direction_error_rate",
    }
    missing = sorted(required - set(context_summary.columns))
    if missing:
        raise ValueError(f"guard context summary missing columns: {', '.join(missing)}")

    frame = context_summary.copy()
    if roles:
        frame = frame[frame["role"].astype(str).isin(roles)].copy()
    if candidates:
        frame = frame[frame["candidate"].astype(str).isin(candidates)].copy()
    if frame.empty:
        return [], pd.DataFrame()

    frame["trade_count"] = frame["trade_count"].astype(float)
    frame["total_adjusted_pnl"] = frame["total_adjusted_pnl"].astype(float)
    frame["direction_error_count"] = (
        frame["direction_error_rate"].astype(float) * frame["trade_count"]
    )
    if "exit_regret_sum" not in frame.columns:
        frame["exit_regret_sum"] = 0.0

    grouped = (
        frame.groupby(["direction", "combined_regime", "session_regime"], dropna=False)
        .agg(
            trade_count=("trade_count", "sum"),
            total_adjusted_pnl=("total_adjusted_pnl", "sum"),
            direction_error_count=("direction_error_count", "sum"),
            exit_regret_sum=("exit_regret_sum", "sum"),
        )
        .reset_index()
    )
    grouped["direction_error_rate"] = np.where(
        grouped["trade_count"] > 0,
        grouped["direction_error_count"] / grouped["trade_count"],
        0.0,
    )
    eligible = grouped[
        (grouped["trade_count"] >= min_trade_count)
        & (grouped["direction_error_rate"] >= min_direction_error_rate)
        & (grouped["total_adjusted_pnl"] <= max_total_pnl)
    ].copy()
    eligible["side_block_rule"] = [
        rule_for_context(str(row.direction), str(row.combined_regime), str(row.session_regime))
        for row in eligible.itertuples(index=False)
    ]
    eligible = eligible.sort_values(
        ["direction_error_rate", "total_adjusted_pnl", "trade_count"],
        ascending=[False, True, False],
    ).reset_index(drop=True)
    rules = eligible["side_block_rule"].drop_duplicates().astype(str).tolist()
    return rules, eligible


def prior_trade_context_frame(
    trades: pd.DataFrame,
    *,
    roles: set[str],
    candidates: set[str],
) -> pd.DataFrame:
    required = {
        "role",
        "candidate",
        "month",
        "direction",
        "entry_decision_timestamp",
        "combined_regime",
        "session_regime",
        "adjusted_pnl",
        "direction_error",
    }
    missing = sorted(required - set(trades.columns))
    if missing:
        raise ValueError(f"prior enriched trades missing columns: {', '.join(missing)}")
    frame = trades.copy()
    if roles:
        frame = frame[frame["role"].astype(str).isin(roles)].copy()
    if candidates:
        frame = frame[frame["candidate"].astype(str).isin(candidates)].copy()
    if frame.empty:
        return frame
    frame["month"] = frame["month"].astype(str).str.slice(0, 7)
    frame["entry_decision_timestamp"] = pd.to_datetime(
        frame["entry_decision_timestamp"],
        utc=True,
    )
    frame["direction_error"] = frame["direction_error"].fillna(False).astype(bool)
    frame["adjusted_pnl"] = frame["adjusted_pnl"].astype(float)
    if "exit_regret" not in frame.columns:
        frame["exit_regret"] = 0.0
    frame["exit_regret"] = frame["exit_regret"].astype(float)
    dedupe_columns = [
        "month",
        "entry_decision_timestamp",
        "direction",
        "combined_regime",
        "session_regime",
    ]
    return frame.drop_duplicates(subset=dedupe_columns).reset_index(drop=True)


def derive_prior_context_side_block_rules(
    trades: pd.DataFrame,
    *,
    target_month: str,
    min_prior_months: int,
    recent_month_count: int,
    min_trade_count: int,
    min_direction_error_rate: float,
    max_total_pnl: float,
) -> tuple[list[str], pd.DataFrame]:
    if trades.empty:
        return [], pd.DataFrame()
    target_period = pd.Period(target_month, freq="M")
    trade_periods = pd.PeriodIndex(trades["month"].astype(str), freq="M")
    prior_mask = trade_periods < target_period
    if recent_month_count > 0:
        prior_mask &= trade_periods >= (target_period - recent_month_count)
    prior = trades[prior_mask].copy()
    if prior.empty:
        return [], pd.DataFrame()
    prior_month_count = int(prior["month"].nunique())
    if prior_month_count < min_prior_months:
        return [], pd.DataFrame()

    grouped = (
        prior.groupby(["direction", "combined_regime", "session_regime"], dropna=False)
        .agg(
            trade_count=("adjusted_pnl", "size"),
            total_adjusted_pnl=("adjusted_pnl", "sum"),
            direction_error_count=("direction_error", "sum"),
            exit_regret_sum=("exit_regret", "sum"),
            prior_month_count=("month", "nunique"),
        )
        .reset_index()
    )
    grouped["target_month"] = target_month
    grouped["direction_error_rate"] = np.where(
        grouped["trade_count"] > 0,
        grouped["direction_error_count"] / grouped["trade_count"],
        0.0,
    )
    eligible = grouped[
        (grouped["trade_count"] >= min_trade_count)
        & (grouped["direction_error_rate"] >= min_direction_error_rate)
        & (grouped["total_adjusted_pnl"] <= max_total_pnl)
    ].copy()
    eligible["side_block_rule"] = [
        rule_for_context(str(row.direction), str(row.combined_regime), str(row.session_regime))
        for row in eligible.itertuples(index=False)
    ]
    eligible = eligible.sort_values(
        ["target_month", "direction_error_rate", "total_adjusted_pnl", "trade_count"],
        ascending=[True, False, True, False],
    ).reset_index(drop=True)
    return eligible["side_block_rule"].drop_duplicates().astype(str).tolist(), eligible


def summarize_candidates(monthly: pd.DataFrame) -> pd.DataFrame:
    role_summary = summarize_by_group(
        monthly,
        ["guard_mode", "max_predicted_hold_minutes", "role", "candidate"],
    )
    if role_summary.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    for key, group in role_summary.groupby(
        ["guard_mode", "max_predicted_hold_minutes", "candidate"],
        dropna=False,
    ):
        guard_mode, max_hold, candidate = key
        role_totals = group["total_adjusted_pnl_sum"].astype(float)
        role_trades = group["trade_count_sum"].astype(float)
        month_group = monthly[
            (monthly["guard_mode"].astype(str) == str(guard_mode))
            & (monthly["max_predicted_hold_minutes"].astype(float) == float(max_hold))
            & (monthly["candidate"].astype(str) == str(candidate))
        ]
        row = {
            "guard_mode": guard_mode,
            "max_predicted_hold_minutes": float(max_hold),
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
            "max_drawdown_max": float(month_group["max_drawdown"].astype(float).max()),
            "max_side_trade_share": float(group["max_side_trade_share"].astype(float).max()),
        }
        blockers: list[str] = []
        if row["positive_role_count"] < row["role_count"]:
            blockers.append("positive_roles_low")
        if row["role_total_pnl_min"] <= 0:
            blockers.append("role_total_pnl_below_floor")
        if row["month_pnl_min"] < 0:
            blockers.append("month_pnl_below_floor")
        if row["role_trade_count_min"] < 10:
            blockers.append("role_trades_low")
        if row["max_side_trade_share"] > 0.95:
            blockers.append("side_share_high")
        row["selector_pass"] = not blockers
        row["blockers"] = ",".join(blockers)
        rows.append(row)
    return pd.DataFrame(rows).sort_values(
        ["selector_pass", "role_total_pnl_min", "total_adjusted_pnl_sum"],
        ascending=[False, False, False],
    )


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
        "guard_mode": row["guard_mode"],
        "max_predicted_hold_minutes": row["max_predicted_hold_minutes"],
        "reason": "best_passing_candidate_by_role_worst_then_total",
        "row": row,
    }


def run_sensitivity(args: argparse.Namespace) -> Path:
    family_predictions = parse_family_predictions(args.family_predictions)
    candidate_names = parse_policy_candidates(args.policy_candidates)
    role_lookup = parse_role_months(args.role_months)
    roles = set(parse_optional_csv(args.roles))
    hold_caps = parse_float_csv(args.max_predicted_hold_minutes)
    guard_modes = parse_optional_csv(args.guard_modes)
    if not guard_modes:
        guard_modes = ["none"]
    invalid_modes = sorted(
        set(guard_modes) - {"none", "diagnostic_inversion", "prior_inversion"}
    )
    if invalid_modes:
        raise ValueError(f"unknown guard modes: {', '.join(invalid_modes)}")
    candidates = [policy_candidate_from_name(name) for name in candidate_names]

    guard_rules: list[str] = []
    guard_contexts = pd.DataFrame()
    if "diagnostic_inversion" in guard_modes:
        if not args.guard_context_summary:
            raise ValueError("--guard-context-summary is required for diagnostic_inversion")
        context_summary = pd.read_csv(args.guard_context_summary)
        guard_rules, guard_contexts = derive_context_side_block_rules(
            context_summary,
            roles=roles,
            candidates=set(candidate_names),
            min_trade_count=args.guard_min_trade_count,
            min_direction_error_rate=args.guard_min_direction_error_rate,
            max_total_pnl=args.guard_max_total_pnl,
        )
    prior_trades = pd.DataFrame()
    if "prior_inversion" in guard_modes:
        if not args.prior_enriched_trades:
            raise ValueError("--prior-enriched-trades is required for prior_inversion")
        prior_trades = prior_trade_context_frame(
            pd.read_csv(args.prior_enriched_trades),
            roles=roles,
            candidates=set(candidate_names),
        )

    run_dir = make_run_dir(args.output_dir, args.label)
    price_data = read_ohlcv(args.data)
    monthly_rows: list[dict[str, Any]] = []
    prior_guard_rows: list[pd.DataFrame] = []

    for family, prediction_path in family_predictions.items():
        predictions = pd.read_parquet(prediction_path)
        months = prediction_months(predictions)
        for candidate in candidates:
            for max_hold in hold_caps:
                base_model_config = build_model_policy_config(
                    prediction_path=prediction_path,
                    candidate=candidate,
                    score_kind=args.score_kind,
                    long_column=args.long_column,
                    short_column=args.short_column,
                    long_holding_column=args.long_holding_column,
                    short_holding_column=args.short_holding_column,
                    min_valid_predicted_hold_minutes=args.min_valid_predicted_hold_minutes,
                    max_predicted_hold_minutes=max_hold,
                )
                for guard_mode in guard_modes:
                    for month in months:
                        role = role_lookup.get((family, month), family)
                        if roles and role not in roles:
                            continue
                        if guard_mode == "diagnostic_inversion":
                            side_block_rules = tuple(guard_rules)
                        elif guard_mode == "prior_inversion":
                            prior_rules, prior_contexts = derive_prior_context_side_block_rules(
                                prior_trades,
                                target_month=month,
                                min_prior_months=args.prior_min_months,
                                recent_month_count=args.prior_recent_month_count,
                                min_trade_count=args.prior_min_trade_count,
                                min_direction_error_rate=args.prior_min_direction_error_rate,
                                max_total_pnl=args.prior_max_total_pnl,
                            )
                            side_block_rules = tuple(prior_rules)
                            if not prior_contexts.empty:
                                prior_contexts = prior_contexts.copy()
                                prior_contexts["family"] = family
                                prior_contexts["role"] = role
                                prior_contexts["candidate"] = candidate.name
                                prior_contexts["max_predicted_hold_minutes"] = max_hold
                                prior_guard_rows.append(prior_contexts)
                        else:
                            side_block_rules = ()
                        model_config = replace(
                            base_model_config,
                            side_block_rules=side_block_rules,
                        )
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
                        metrics, _trades, _curve, _signal = run_model_policy(
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
                                "guard_mode": guard_mode,
                                "side_block_rule_count": len(side_block_rules),
                                "side_block_rules": ";".join(side_block_rules),
                                "max_predicted_hold_minutes": max_hold,
                                **asdict(candidate),
                                **metrics,
                            }
                        )

    if not monthly_rows:
        raise ValueError("no monthly backtests were executed")
    monthly = pd.DataFrame(monthly_rows)
    monthly.to_csv(run_dir / "monthly_hold_cap_metrics.csv", index=False)
    role_summary = summarize_by_group(
        monthly,
        ["guard_mode", "max_predicted_hold_minutes", "role", "candidate"],
    )
    role_summary.to_csv(run_dir / "role_hold_cap_summary.csv", index=False)
    candidate_summary = summarize_candidates(monthly)
    candidate_summary.to_csv(run_dir / "candidate_hold_cap_selection_summary.csv", index=False)
    cap_summary = summarize_by_group(monthly, ["guard_mode", "max_predicted_hold_minutes"])
    cap_summary.to_csv(run_dir / "hold_cap_summary.csv", index=False)
    if not guard_contexts.empty:
        guard_contexts.to_csv(run_dir / "diagnostic_inversion_guard_contexts.csv", index=False)
    if prior_guard_rows:
        pd.concat(prior_guard_rows, ignore_index=True).drop_duplicates().to_csv(
            run_dir / "prior_inversion_guard_contexts.csv",
            index=False,
        )
    selected = select_policy(candidate_summary)
    (run_dir / "selected_policy.json").write_text(
        json.dumps(selected, indent=2, default=local_json_default),
        encoding="utf-8",
    )
    config = {
        "family_predictions": family_predictions,
        "policy_candidates": candidate_names,
        "role_months": args.role_months,
        "roles": sorted(roles),
        "guard_modes": guard_modes,
        "guard_context_summary": args.guard_context_summary,
        "guard_min_trade_count": args.guard_min_trade_count,
        "guard_min_direction_error_rate": args.guard_min_direction_error_rate,
        "guard_max_total_pnl": args.guard_max_total_pnl,
        "guard_rule_count": len(guard_rules),
        "guard_rules": guard_rules,
        "prior_enriched_trades": args.prior_enriched_trades,
        "prior_min_months": args.prior_min_months,
        "prior_recent_month_count": args.prior_recent_month_count,
        "prior_min_trade_count": args.prior_min_trade_count,
        "prior_min_direction_error_rate": args.prior_min_direction_error_rate,
        "prior_max_total_pnl": args.prior_max_total_pnl,
        "max_predicted_hold_minutes": hold_caps,
        "data": args.data,
        "score_kind": args.score_kind,
        "long_column": args.long_column,
        "short_column": args.short_column,
        "long_holding_column": args.long_holding_column,
        "short_holding_column": args.short_holding_column,
        "min_valid_predicted_hold_minutes": args.min_valid_predicted_hold_minutes,
        "max_hold_hours": args.max_hold_hours,
        "profit_multiplier": args.profit_multiplier,
        "loss_multiplier": args.loss_multiplier,
        "warmup_days": args.warmup_days,
        "post_days": args.post_days,
    }
    (run_dir / "config.json").write_text(
        json.dumps(config, indent=2, default=local_json_default),
        encoding="utf-8",
    )

    print("Hold-cap summary:")
    print(
        cap_summary[
            [
                "guard_mode",
                "max_predicted_hold_minutes",
                "total_adjusted_pnl_sum",
                "total_adjusted_pnl_min",
                "trade_count_sum",
                "max_drawdown_max",
                "max_side_trade_share",
            ]
        ].to_string(index=False)
    )
    print("\nTop candidate/cap rows:")
    print(
        candidate_summary[
            [
                "guard_mode",
                "max_predicted_hold_minutes",
                "candidate",
                "selector_pass",
                "total_adjusted_pnl_sum",
                "role_total_pnl_min",
                "month_pnl_min",
                "trade_count_sum",
                "blockers",
            ]
        ].head(20).to_string(index=False)
    )
    print(f"\nselected: {selected['selected']}")
    print(f"artifacts: {run_dir}")
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--family-predictions", action="append", required=True)
    parser.add_argument(
        "--policy-candidates",
        default=",".join(DEFAULT_Q95_Q99_CANDIDATES),
    )
    parser.add_argument("--roles", default="")
    parser.add_argument("--role-months", action="append", default=[])
    parser.add_argument("--guard-modes", default="none,diagnostic_inversion")
    parser.add_argument("--guard-context-summary", type=Path, default=None)
    parser.add_argument("--guard-min-trade-count", type=int, default=1)
    parser.add_argument("--guard-min-direction-error-rate", type=float, default=1.0)
    parser.add_argument("--guard-max-total-pnl", type=float, default=-1e-9)
    parser.add_argument("--prior-enriched-trades", type=Path, default=None)
    parser.add_argument("--prior-min-months", type=int, default=1)
    parser.add_argument("--prior-recent-month-count", type=int, default=0)
    parser.add_argument("--prior-min-trade-count", type=int, default=2)
    parser.add_argument("--prior-min-direction-error-rate", type=float, default=0.75)
    parser.add_argument("--prior-max-total-pnl", type=float, default=-1e-9)
    parser.add_argument("--max-predicted-hold-minutes", default="260,480,720,1440")
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
    parser.add_argument("--max-hold-hours", type=float, default=24.0)
    parser.add_argument("--profit-multiplier", type=float, default=1.0)
    parser.add_argument("--loss-multiplier", type=float, default=1.2)
    parser.add_argument("--spread-points", type=float, default=0.0)
    parser.add_argument("--slippage-points", type=float, default=0.0)
    parser.add_argument("--execution-delay-bars", type=int, default=0)
    parser.add_argument("--warmup-days", type=int, default=7)
    parser.add_argument("--post-days", type=int, default=4)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/reports/backtests"),
    )
    parser.add_argument("--label", default="entry_ev_quantile_hold_cap_sensitivity")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    run_sensitivity(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
