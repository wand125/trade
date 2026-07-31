#!/usr/bin/env python3
"""Diagnose exit capture for entry-EV quantile selected trades."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


def parse_optional_csv(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def side_values(
    frame: pd.DataFrame,
    direction: pd.Series,
    long_column: str,
    short_column: str,
) -> pd.Series:
    long_values = frame[long_column].astype(float)
    short_values = frame[short_column].astype(float)
    return pd.Series(
        np.where(direction.eq("long"), long_values, short_values),
        index=frame.index,
        dtype="float64",
    )


def bool_mean(series: pd.Series) -> float:
    if series.empty:
        return 0.0
    return float(series.fillna(False).astype(bool).mean())


def safe_mean(series: pd.Series) -> float:
    numeric = pd.to_numeric(series, errors="coerce")
    if numeric.notna().sum() == 0:
        return 0.0
    return float(numeric.mean())


def add_exit_capture_columns(
    trades: pd.DataFrame,
    *,
    long_policy_hold_column: str,
    short_policy_hold_column: str,
    min_policy_hold_minutes: float,
    max_policy_hold_minutes: float,
    tolerance_minutes: float,
) -> pd.DataFrame:
    required = {
        "direction",
        "holding_minutes",
        "actual_taken_best_holding_minutes",
        "actual_taken_best_adjusted_pnl",
        "adjusted_pnl",
        "exit_regret",
        long_policy_hold_column,
        short_policy_hold_column,
    }
    missing = sorted(required - set(trades.columns))
    if missing:
        raise ValueError(f"enriched trades missing columns: {', '.join(missing)}")

    output = trades.copy()
    direction = output["direction"].astype(str).str.lower()
    raw_policy_hold = side_values(
        output,
        direction,
        long_policy_hold_column,
        short_policy_hold_column,
    )
    effective_policy_hold = raw_policy_hold.where(np.isfinite(raw_policy_hold), max_policy_hold_minutes)
    effective_policy_hold = effective_policy_hold.clip(
        lower=min_policy_hold_minutes,
        upper=max_policy_hold_minutes,
    )

    realized_hold = output["holding_minutes"].astype(float)
    oracle_hold = output["actual_taken_best_holding_minutes"].astype(float)
    adjusted = output["adjusted_pnl"].astype(float)
    actual_best = output["actual_taken_best_adjusted_pnl"].astype(float)
    exit_regret = output["exit_regret"].astype(float)

    output["policy_raw_hold_minutes"] = raw_policy_hold
    output["policy_effective_hold_minutes"] = effective_policy_hold
    output["policy_hold_minus_realized_minutes"] = effective_policy_hold - realized_hold
    output["policy_hold_minus_oracle_minutes"] = effective_policy_hold - oracle_hold
    output["oracle_hold_minus_realized_minutes"] = oracle_hold - realized_hold
    output["policy_hold_clipped_to_max"] = raw_policy_hold > max_policy_hold_minutes
    output["policy_hold_clipped_to_min"] = raw_policy_hold < min_policy_hold_minutes
    output["realized_near_policy_cap"] = realized_hold >= (max_policy_hold_minutes - tolerance_minutes)
    output["early_exit_vs_oracle"] = realized_hold < (oracle_hold - tolerance_minutes)
    output["late_exit_vs_oracle"] = realized_hold > (oracle_hold + tolerance_minutes)
    output["exit_regret_positive"] = exit_regret > 0
    output["oracle_potential_positive"] = actual_best > 0
    output["loss_with_oracle_edge"] = (adjusted < 0) & (actual_best > 0)
    output["win_but_large_exit_regret"] = (adjusted > 0) & (exit_regret > adjusted.abs())
    return output


def summarize_exit_capture(frame: pd.DataFrame, group_columns: list[str]) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=group_columns)
    rows: list[dict[str, Any]] = []
    working = frame.copy()
    working["_loss_adjusted_pnl"] = working["adjusted_pnl"].astype(float).where(
        working["adjusted_pnl"].astype(float) < 0,
        0.0,
    )
    for key, group in working.groupby(group_columns, dropna=False, observed=True):
        if not isinstance(key, tuple):
            key = (key,)
        row = dict(zip(group_columns, key))
        trade_count = int(len(group))
        row.update(
            {
                "trade_count": trade_count,
                "total_adjusted_pnl": float(group["adjusted_pnl"].astype(float).sum()),
                "loss_adjusted_pnl": float(group["_loss_adjusted_pnl"].sum()),
                "win_rate": bool_mean(group["adjusted_pnl"].astype(float) > 0),
                "exit_regret_sum": float(group["exit_regret"].astype(float).sum()),
                "exit_regret_mean": safe_mean(group["exit_regret"]),
                "exit_regret_positive_rate": bool_mean(group["exit_regret_positive"]),
                "oracle_potential_rate": bool_mean(group["oracle_potential_positive"]),
                "loss_with_oracle_edge_count": int(group["loss_with_oracle_edge"].sum()),
                "loss_with_oracle_edge_rate": bool_mean(group["loss_with_oracle_edge"]),
                "early_exit_vs_oracle_rate": bool_mean(group["early_exit_vs_oracle"]),
                "late_exit_vs_oracle_rate": bool_mean(group["late_exit_vs_oracle"]),
                "policy_hold_clipped_to_max_rate": bool_mean(group["policy_hold_clipped_to_max"]),
                "realized_near_policy_cap_rate": bool_mean(group["realized_near_policy_cap"]),
                "policy_raw_hold_mean": safe_mean(group["policy_raw_hold_minutes"]),
                "policy_effective_hold_mean": safe_mean(group["policy_effective_hold_minutes"]),
                "realized_hold_mean": safe_mean(group["holding_minutes"]),
                "oracle_hold_mean": safe_mean(group["actual_taken_best_holding_minutes"]),
                "policy_hold_minus_oracle_mean": safe_mean(group["policy_hold_minus_oracle_minutes"]),
                "oracle_hold_minus_realized_mean": safe_mean(group["oracle_hold_minus_realized_minutes"]),
                "policy_hold_minus_realized_mean": safe_mean(group["policy_hold_minus_realized_minutes"]),
                "direction_error_rate": (
                    bool_mean(group["direction_error"]) if "direction_error" in group.columns else 0.0
                ),
                "no_edge_rate": (
                    bool_mean(group["no_edge_entry"]) if "no_edge_entry" in group.columns else 0.0
                ),
            }
        )
        rows.append(row)
    return pd.DataFrame(rows).sort_values(
        ["exit_regret_sum", "total_adjusted_pnl", "trade_count"],
        ascending=[False, True, False],
    )


def build_diagnostics(args: argparse.Namespace) -> Path:
    trades = pd.read_csv(args.enriched_trades)
    if args.roles:
        roles = set(parse_optional_csv(args.roles))
        trades = trades[trades["role"].astype(str).isin(roles)].copy()
    if args.candidates:
        candidates = set(parse_optional_csv(args.candidates))
        trades = trades[trades["candidate"].astype(str).isin(candidates)].copy()
    if trades.empty:
        raise ValueError("no enriched trades remain after filters")

    enriched = add_exit_capture_columns(
        trades,
        long_policy_hold_column=args.long_policy_hold_column,
        short_policy_hold_column=args.short_policy_hold_column,
        min_policy_hold_minutes=args.min_policy_hold_minutes,
        max_policy_hold_minutes=args.max_policy_hold_minutes,
        tolerance_minutes=args.tolerance_minutes,
    )

    output_dir = args.output_dir
    timestamp = pd.Timestamp.now(tz="UTC").strftime("%Y%m%d_%H%M%S")
    run_dir = output_dir / f"{timestamp}_{args.label}"
    run_dir.mkdir(parents=True, exist_ok=True)

    enriched.to_csv(run_dir / "exit_capture_enriched_trades.csv", index=False)
    role_candidate = summarize_exit_capture(enriched, ["role", "candidate"])
    role_candidate.to_csv(run_dir / "role_candidate_exit_capture_summary.csv", index=False)
    role_context = summarize_exit_capture(
        enriched,
        ["role", "candidate", "direction", "combined_regime", "session_regime"],
    )
    role_context.to_csv(run_dir / "role_context_exit_capture_summary.csv", index=False)
    role_context.head(args.top_n).to_csv(run_dir / "top_exit_regret_contexts.csv", index=False)
    role_month = summarize_exit_capture(enriched, ["role", "candidate", "month"])
    role_month.to_csv(run_dir / "role_month_exit_capture_summary.csv", index=False)

    config = {
        "enriched_trades": args.enriched_trades,
        "roles": args.roles,
        "candidates": args.candidates,
        "long_policy_hold_column": args.long_policy_hold_column,
        "short_policy_hold_column": args.short_policy_hold_column,
        "min_policy_hold_minutes": args.min_policy_hold_minutes,
        "max_policy_hold_minutes": args.max_policy_hold_minutes,
        "tolerance_minutes": args.tolerance_minutes,
        "top_n": args.top_n,
    }
    (run_dir / "config.json").write_text(json.dumps(config, indent=2, default=str), encoding="utf-8")

    print("Role/candidate exit capture:")
    print(
        role_candidate[
            [
                "role",
                "candidate",
                "trade_count",
                "total_adjusted_pnl",
                "exit_regret_sum",
                "loss_with_oracle_edge_rate",
                "early_exit_vs_oracle_rate",
                "late_exit_vs_oracle_rate",
                "policy_hold_clipped_to_max_rate",
                "policy_hold_minus_oracle_mean",
            ]
        ].to_string(index=False)
    )
    print("\nTop exit-regret contexts:")
    print(
        role_context[
            [
                "role",
                "candidate",
                "direction",
                "combined_regime",
                "session_regime",
                "trade_count",
                "total_adjusted_pnl",
                "exit_regret_sum",
                "loss_with_oracle_edge_rate",
                "policy_hold_minus_oracle_mean",
            ]
        ].head(args.top_n).to_string(index=False)
    )
    print(f"artifacts: {run_dir}")
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--enriched-trades", type=Path, required=True)
    parser.add_argument("--roles", default="")
    parser.add_argument("--candidates", default="")
    parser.add_argument("--long-policy-hold-column", default="pred_mlp_long_exit_event_minutes")
    parser.add_argument("--short-policy-hold-column", default="pred_mlp_short_exit_event_minutes")
    parser.add_argument("--min-policy-hold-minutes", type=float, default=0.0)
    parser.add_argument("--max-policy-hold-minutes", type=float, default=260.0)
    parser.add_argument("--tolerance-minutes", type=float, default=30.0)
    parser.add_argument("--top-n", type=int, default=30)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/reports/backtests"),
    )
    parser.add_argument("--label", default="entry_ev_quantile_exit_capture_diagnostics")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    build_diagnostics(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
