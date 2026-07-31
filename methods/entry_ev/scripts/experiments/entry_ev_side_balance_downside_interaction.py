#!/usr/bin/env python3
"""Diagnose interactions between side-balance drift and prior downside evidence."""

from __future__ import annotations

import argparse
import json
import sys
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

from trade_data.backtest import json_default, make_run_dir  # noqa: E402

from entry_ev_side_balance_feature_diagnostics import (  # noqa: E402
    add_side_balance_trade_features,
    parse_float_csv,
    summarize_candidate_path,
    summarize_trade_slice,
)


CONTEXT_COLUMNS = ["direction", "combined_regime", "session_regime"]


def local_json_default(value: Any) -> Any:
    try:
        return json_default(value)
    except TypeError:
        pass
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, np.bool_):
        return bool(value)
    raise TypeError(f"cannot serialize {type(value).__name__}")


def parse_csv(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def numeric_series(frame: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=float)
    return pd.to_numeric(frame[column], errors="coerce").fillna(default).astype(float)


def bool_series(frame: pd.DataFrame, column: str, default: bool = False) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=bool)
    series = frame[column]
    if pd.api.types.is_bool_dtype(series):
        return series.fillna(default).astype(bool)
    if pd.api.types.is_numeric_dtype(series):
        return series.fillna(float(default)).astype(float).ne(0.0)
    normalized = series.astype(str).str.lower().str.strip()
    return normalized.isin({"true", "1", "yes", "y"})


def normalize_trades(frame: pd.DataFrame) -> pd.DataFrame:
    required = {
        "role",
        "candidate",
        "month",
        "direction",
        "entry_decision_timestamp",
        "combined_regime",
        "session_regime",
        "adjusted_pnl",
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"side-balance trades missing columns: {', '.join(missing)}")
    output = frame.copy()
    output["role"] = output["role"].astype(str)
    output["candidate"] = output["candidate"].astype(str)
    output["month"] = output["month"].astype(str).str.slice(0, 7)
    output["direction"] = output["direction"].astype(str).str.lower()
    output["combined_regime"] = output["combined_regime"].astype(str)
    output["session_regime"] = output["session_regime"].astype(str)
    output["entry_decision_timestamp"] = pd.to_datetime(
        output["entry_decision_timestamp"],
        utc=True,
    )
    output["adjusted_pnl"] = numeric_series(output, "adjusted_pnl")
    output["direction_error"] = bool_series(output, "direction_error")
    output["no_edge_entry"] = bool_series(output, "no_edge_entry")
    output["exit_regret"] = numeric_series(output, "exit_regret")
    output = add_side_balance_trade_features(output)
    return output


def filter_by_values(frame: pd.DataFrame, column: str, values: set[str]) -> pd.DataFrame:
    if not values:
        return frame
    return frame[frame[column].astype(str).isin(values)].copy()


def build_prior_stats_for_month(
    prior: pd.DataFrame,
    *,
    target_month: str,
    min_prior_months: int,
    recent_month_count: int,
    large_exit_regret_threshold: float,
) -> pd.DataFrame:
    if prior.empty:
        return pd.DataFrame()
    target_period = pd.Period(target_month, freq="M")
    prior_periods = pd.PeriodIndex(prior["month"].astype(str), freq="M")
    mask = prior_periods < target_period
    if recent_month_count > 0:
        mask &= prior_periods >= (target_period - recent_month_count)
    frame = prior[mask].copy()
    if frame.empty or int(frame["month"].nunique()) < min_prior_months:
        return pd.DataFrame()
    frame["_loss"] = frame["adjusted_pnl"].astype(float) < 0.0
    frame["_loss_pnl"] = frame["adjusted_pnl"].astype(float).where(frame["_loss"], 0.0)
    frame["_large_exit_regret"] = frame["exit_regret"].astype(float) >= large_exit_regret_threshold
    grouped = (
        frame.groupby(CONTEXT_COLUMNS, dropna=False)
        .agg(
            prior_trade_count=("adjusted_pnl", "size"),
            prior_month_count=("month", "nunique"),
            prior_total_adjusted_pnl=("adjusted_pnl", "sum"),
            prior_loss_adjusted_pnl=("_loss_pnl", "sum"),
            prior_loss_count=("_loss", "sum"),
            prior_direction_error_count=("direction_error", "sum"),
            prior_no_edge_count=("no_edge_entry", "sum"),
            prior_large_exit_regret_count=("_large_exit_regret", "sum"),
            prior_exit_regret_sum=("exit_regret", "sum"),
        )
        .reset_index()
    )
    grouped["target_month"] = target_month
    grouped["prior_avg_adjusted_pnl"] = np.where(
        grouped["prior_trade_count"] > 0,
        grouped["prior_total_adjusted_pnl"] / grouped["prior_trade_count"],
        0.0,
    )
    grouped["prior_loss_rate"] = np.where(
        grouped["prior_trade_count"] > 0,
        grouped["prior_loss_count"] / grouped["prior_trade_count"],
        0.0,
    )
    grouped["prior_direction_error_rate"] = np.where(
        grouped["prior_trade_count"] > 0,
        grouped["prior_direction_error_count"] / grouped["prior_trade_count"],
        0.0,
    )
    grouped["prior_no_edge_rate"] = np.where(
        grouped["prior_trade_count"] > 0,
        grouped["prior_no_edge_count"] / grouped["prior_trade_count"],
        0.0,
    )
    grouped["prior_large_exit_regret_rate"] = np.where(
        grouped["prior_trade_count"] > 0,
        grouped["prior_large_exit_regret_count"] / grouped["prior_trade_count"],
        0.0,
    )
    grouped["prior_exit_regret_mean"] = np.where(
        grouped["prior_trade_count"] > 0,
        grouped["prior_exit_regret_sum"] / grouped["prior_trade_count"],
        0.0,
    )
    return grouped


def build_prior_stats(
    target: pd.DataFrame,
    prior: pd.DataFrame,
    *,
    min_prior_months: int,
    recent_month_count: int,
    large_exit_regret_threshold: float,
) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for month in sorted(target["month"].astype(str).unique()):
        stats = build_prior_stats_for_month(
            prior,
            target_month=month,
            min_prior_months=min_prior_months,
            recent_month_count=recent_month_count,
            large_exit_regret_threshold=large_exit_regret_threshold,
        )
        if not stats.empty:
            frames.append(stats)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def add_prior_downside_features(
    target: pd.DataFrame,
    prior: pd.DataFrame,
    *,
    min_prior_months: int,
    recent_month_count: int,
    support_scale: float,
    pnl_scale: float,
    large_exit_regret_threshold: float,
) -> pd.DataFrame:
    stats = build_prior_stats(
        target,
        prior,
        min_prior_months=min_prior_months,
        recent_month_count=recent_month_count,
        large_exit_regret_threshold=large_exit_regret_threshold,
    )
    if stats.empty:
        enriched = target.copy()
    else:
        enriched = target.merge(
            stats,
            how="left",
            left_on=["month", *CONTEXT_COLUMNS],
            right_on=["target_month", *CONTEXT_COLUMNS],
        )
    defaults = {
        "prior_trade_count": 0.0,
        "prior_month_count": 0.0,
        "prior_total_adjusted_pnl": 0.0,
        "prior_loss_adjusted_pnl": 0.0,
        "prior_loss_count": 0.0,
        "prior_direction_error_count": 0.0,
        "prior_no_edge_count": 0.0,
        "prior_large_exit_regret_count": 0.0,
        "prior_exit_regret_sum": 0.0,
        "prior_avg_adjusted_pnl": 0.0,
        "prior_loss_rate": 0.0,
        "prior_direction_error_rate": 0.0,
        "prior_no_edge_rate": 0.0,
        "prior_large_exit_regret_rate": 0.0,
        "prior_exit_regret_mean": 0.0,
    }
    for column, default in defaults.items():
        if column not in enriched.columns:
            enriched[column] = default
        enriched[column] = enriched[column].fillna(default).astype(float)
    support_weight = np.clip(enriched["prior_trade_count"] / support_scale, 0.0, 1.0)
    pnl_risk = np.clip(-enriched["prior_avg_adjusted_pnl"] / pnl_scale, 0.0, 1.0)
    enriched["prior_downside_support_weight"] = support_weight
    enriched["prior_downside_pnl_risk_component"] = pnl_risk
    enriched["prior_downside_risk_score"] = support_weight * (
        0.30 * enriched["prior_loss_rate"]
        + 0.25 * enriched["prior_direction_error_rate"]
        + 0.25 * enriched["prior_large_exit_regret_rate"]
        + 0.20 * pnl_risk
    )
    enriched["side_balance_abs_signed_drift_for_trade"] = (
        enriched["side_balance_signed_drift_for_trade"].astype(float).abs()
    )
    enriched["side_balance_downside_interaction_score"] = (
        enriched["side_balance_abs_signed_drift_for_trade"]
        * enriched["prior_downside_risk_score"]
    )
    return enriched


def interaction_masks(
    frame: pd.DataFrame,
    *,
    drift_threshold: float,
    risk_threshold: float,
    interaction_threshold: float,
) -> dict[str, pd.Series]:
    signed = frame["side_balance_signed_drift_for_trade"].astype(float)
    abs_drift = frame["side_balance_abs_signed_drift_for_trade"].astype(float)
    risk = frame["prior_downside_risk_score"].astype(float)
    interaction = frame["side_balance_downside_interaction_score"].astype(float)
    risky = risk >= risk_threshold
    return {
        "risk_only": risky,
        "risk_and_abs_drift": risky & (abs_drift >= drift_threshold),
        "risk_and_overrepresented": risky & (signed >= drift_threshold),
        "risk_and_underrepresented": risky & (signed <= -drift_threshold),
        "interaction_score": interaction >= interaction_threshold,
    }


def summarize_interaction_screens(
    frame: pd.DataFrame,
    *,
    drift_thresholds: list[float],
    risk_thresholds: list[float],
    interaction_thresholds: list[float],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for candidate, candidate_frame in frame.groupby("candidate", dropna=False):
        original = summarize_candidate_path(candidate_frame)
        for drift_threshold in drift_thresholds:
            for risk_threshold in risk_thresholds:
                for interaction_threshold in interaction_thresholds:
                    masks = interaction_masks(
                        candidate_frame,
                        drift_threshold=drift_threshold,
                        risk_threshold=risk_threshold,
                        interaction_threshold=interaction_threshold,
                    )
                    for screen, mask in masks.items():
                        removed = candidate_frame[mask]
                        kept = candidate_frame[~mask]
                        removed_summary = summarize_trade_slice(removed)
                        kept_summary = summarize_candidate_path(kept)
                        rows.append(
                            {
                                "candidate": candidate,
                                "screen": screen,
                                "drift_threshold": drift_threshold,
                                "risk_threshold": risk_threshold,
                                "interaction_threshold": interaction_threshold,
                                "original_total_pnl": original["total_adjusted_pnl"],
                                "original_min_role_total_pnl": original[
                                    "min_role_total_pnl"
                                ],
                                "original_min_month_pnl": original["min_month_pnl"],
                                "original_trade_count": original["trade_count"],
                                "removed_trade_count": removed_summary["trade_count"],
                                "removed_total_pnl": removed_summary[
                                    "total_adjusted_pnl"
                                ],
                                "removed_loss_pnl": removed_summary["loss_adjusted_pnl"],
                                "removed_win_pnl": removed_summary["win_adjusted_pnl"],
                                "kept_total_pnl": kept_summary["total_adjusted_pnl"],
                                "kept_min_role_total_pnl": kept_summary[
                                    "min_role_total_pnl"
                                ],
                                "kept_min_month_pnl": kept_summary["min_month_pnl"],
                                "kept_trade_count": kept_summary["trade_count"],
                                "kept_max_side_trade_share": kept_summary[
                                    "max_side_trade_share"
                                ],
                                "pointwise_delta_if_removed": (
                                    kept_summary["total_adjusted_pnl"]
                                    - original["total_adjusted_pnl"]
                                ),
                            }
                        )
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(
        [
            "pointwise_delta_if_removed",
            "kept_min_role_total_pnl",
            "kept_total_pnl",
            "removed_trade_count",
        ],
        ascending=[False, False, False, False],
    ).reset_index(drop=True)


def summarize_feature_buckets(frame: pd.DataFrame) -> pd.DataFrame:
    output = frame.copy()
    output["risk_bucket"] = pd.cut(
        output["prior_downside_risk_score"].astype(float),
        bins=[-np.inf, 0.0, 0.10, 0.25, 0.50, np.inf],
        labels=["none", "0_0p10", "0p10_0p25", "0p25_0p50", "0p50_inf"],
    )
    output["interaction_bucket"] = pd.cut(
        output["side_balance_downside_interaction_score"].astype(float),
        bins=[-np.inf, 0.0, 0.005, 0.02, 0.05, np.inf],
        labels=["none", "0_0p005", "0p005_0p02", "0p02_0p05", "0p05_inf"],
    )
    rows: list[dict[str, Any]] = []
    for (candidate, risk_bucket, interaction_bucket), group in output.groupby(
        ["candidate", "risk_bucket", "interaction_bucket"],
        dropna=False,
        observed=True,
    ):
        summary = summarize_trade_slice(group)
        rows.append(
            {
                "candidate": candidate,
                "risk_bucket": str(risk_bucket),
                "interaction_bucket": str(interaction_bucket),
                **summary,
            }
        )
    return pd.DataFrame(rows).sort_values(
        ["total_adjusted_pnl", "trade_count"],
        ascending=[True, False],
    ).reset_index(drop=True)


def build_diagnostics(args: argparse.Namespace) -> Path:
    trades = normalize_trades(pd.read_csv(args.trades))
    target_roles = set(parse_csv(args.target_roles))
    prior_roles = set(parse_csv(args.prior_roles))
    candidates = set(parse_csv(args.candidates))
    target = filter_by_values(trades, "role", target_roles)
    target = filter_by_values(target, "candidate", candidates)
    prior = filter_by_values(trades, "role", prior_roles)
    prior = filter_by_values(prior, "candidate", candidates)
    if target.empty:
        raise ValueError("no target trades remain after filters")
    if prior.empty:
        prior = target.copy()

    enriched = add_prior_downside_features(
        target,
        prior,
        min_prior_months=args.min_prior_months,
        recent_month_count=args.recent_month_count,
        support_scale=args.support_scale,
        pnl_scale=args.pnl_scale,
        large_exit_regret_threshold=args.large_exit_regret_threshold,
    )
    screens = summarize_interaction_screens(
        enriched,
        drift_thresholds=parse_float_csv(args.drift_thresholds),
        risk_thresholds=parse_float_csv(args.risk_thresholds),
        interaction_thresholds=parse_float_csv(args.interaction_thresholds),
    )
    buckets = summarize_feature_buckets(enriched)

    run_dir = make_run_dir(args.output_dir, args.label)
    enriched.to_csv(run_dir / "enriched_side_balance_downside_trades.csv", index=False)
    screens.to_csv(run_dir / "side_balance_downside_screen_effects.csv", index=False)
    buckets.to_csv(run_dir / "side_balance_downside_feature_buckets.csv", index=False)

    config = {
        "trades": args.trades,
        "target_roles": parse_csv(args.target_roles),
        "prior_roles": parse_csv(args.prior_roles),
        "candidates": parse_csv(args.candidates),
        "min_prior_months": args.min_prior_months,
        "recent_month_count": args.recent_month_count,
        "support_scale": args.support_scale,
        "pnl_scale": args.pnl_scale,
        "large_exit_regret_threshold": args.large_exit_regret_threshold,
        "drift_thresholds": parse_float_csv(args.drift_thresholds),
        "risk_thresholds": parse_float_csv(args.risk_thresholds),
        "interaction_thresholds": parse_float_csv(args.interaction_thresholds),
        "note": "screen effects are pointwise diagnostics and do not model stateful replacements",
    }
    (run_dir / "config.json").write_text(
        json.dumps(config, indent=2, default=local_json_default),
        encoding="utf-8",
    )

    print("Side-balance x downside screens:")
    print(
        screens[
            [
                "candidate",
                "screen",
                "drift_threshold",
                "risk_threshold",
                "interaction_threshold",
                "removed_trade_count",
                "removed_total_pnl",
                "kept_total_pnl",
                "kept_min_role_total_pnl",
                "pointwise_delta_if_removed",
            ]
        ]
        .head(args.top_n)
        .to_string(index=False)
    )
    print("\nWorst buckets:")
    print(
        buckets[
            [
                "candidate",
                "risk_bucket",
                "interaction_bucket",
                "trade_count",
                "total_adjusted_pnl",
                "abs_drift_mean",
                "taken_penalty_mean",
            ]
        ]
        .head(args.top_n)
        .to_string(index=False)
    )
    print(f"artifacts: {run_dir}")
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trades", type=Path, required=True)
    parser.add_argument("--target-roles", default="")
    parser.add_argument("--prior-roles", default="")
    parser.add_argument("--candidates", default="")
    parser.add_argument("--min-prior-months", type=int, default=1)
    parser.add_argument("--recent-month-count", type=int, default=0)
    parser.add_argument("--support-scale", type=float, default=10.0)
    parser.add_argument("--pnl-scale", type=float, default=20.0)
    parser.add_argument("--large-exit-regret-threshold", type=float, default=10.0)
    parser.add_argument("--drift-thresholds", default="0.02,0.05")
    parser.add_argument("--risk-thresholds", default="0.05,0.10,0.20")
    parser.add_argument("--interaction-thresholds", default="0.002,0.005,0.010")
    parser.add_argument("--top-n", type=int, default=30)
    parser.add_argument("--output-dir", type=Path, default=Path("data/reports/backtests"))
    parser.add_argument("--label", default="entry_ev_side_balance_downside_interaction")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    build_diagnostics(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
