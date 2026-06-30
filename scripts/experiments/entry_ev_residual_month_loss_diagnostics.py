#!/usr/bin/env python3
"""Diagnose a residual losing month from enriched entry-EV policy trades."""

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
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from trade_data.backtest import json_default, make_run_dir  # noqa: E402


DEFAULT_FLAG_COLUMNS = (
    "is_loss",
    "direction_error",
    "no_edge_entry",
    "loss_with_same_side_oracle_edge",
    "large_exit_regret",
    "large_best_side_regret",
    "ev_overestimate_positive",
    "prior_has_context",
    "prior_context_risk_high",
)


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


def parse_optional_csv(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def read_trade_frames(paths: list[Path]) -> pd.DataFrame:
    frames = [pd.read_csv(path) for path in paths]
    if not frames:
        raise ValueError("at least one enriched trade CSV is required")
    return pd.concat(frames, ignore_index=True)


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


def numeric_series(frame: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=float)
    return pd.to_numeric(frame[column], errors="coerce").fillna(default).astype(float)


def normalize_trade_frame(frame: pd.DataFrame) -> pd.DataFrame:
    required = {"role", "candidate", "month", "direction", "adjusted_pnl"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"enriched trades missing columns: {', '.join(missing)}")

    normalized = frame.copy()
    normalized["role"] = normalized["role"].astype(str)
    normalized["candidate"] = normalized["candidate"].astype(str)
    normalized["month"] = normalized["month"].astype(str).str.slice(0, 7)
    normalized["direction"] = normalized["direction"].astype(str).str.lower()
    if "combined_regime" not in normalized.columns:
        normalized["combined_regime"] = ""
    if "session_regime" not in normalized.columns:
        normalized["session_regime"] = ""
    normalized["combined_regime"] = normalized["combined_regime"].astype(str)
    normalized["session_regime"] = normalized["session_regime"].astype(str)

    for column in [
        "adjusted_pnl",
        "actual_taken_best_adjusted_pnl",
        "actual_opposite_best_adjusted_pnl",
        "actual_best_adjusted_pnl",
        "pred_taken_ev",
        "pred_opposite_ev",
        "pred_side_confidence_gap",
        "exit_regret",
        "best_side_regret",
        "ev_overestimate_vs_oracle",
        "ev_overestimate_vs_realized",
        "holding_minutes",
        "actual_taken_best_holding_minutes",
        "oracle_holding_gap_minutes",
        "prior_context_risk_score",
        "prior_trade_count",
        "prior_total_adjusted_pnl",
        "prior_direction_error_rate",
        "prior_loss_rate",
    ]:
        normalized[column] = numeric_series(normalized, column)
    for column in [
        "direction_error",
        "no_edge_entry",
        "predicted_side_error",
        "actual_taken_profit_barrier_hit",
        "prior_has_context",
    ]:
        normalized[column] = bool_series(normalized, column)
    return normalized


def filter_frame(
    frame: pd.DataFrame,
    *,
    roles: set[str],
    candidates: set[str],
    months: set[str],
) -> pd.DataFrame:
    filtered = frame.copy()
    if roles:
        filtered = filtered[filtered["role"].isin(roles)].copy()
    if candidates:
        filtered = filtered[filtered["candidate"].isin(candidates)].copy()
    if months:
        filtered = filtered[filtered["month"].isin(months)].copy()
    return filtered


def add_failure_flags(
    frame: pd.DataFrame,
    *,
    exit_regret_threshold: float,
    best_side_regret_threshold: float,
    prior_risk_threshold: float,
) -> pd.DataFrame:
    enriched = frame.copy()
    adjusted = enriched["adjusted_pnl"].astype(float)
    same_side_oracle = enriched["actual_taken_best_adjusted_pnl"].astype(float)
    enriched["is_loss"] = adjusted < 0.0
    enriched["same_side_oracle_profitable"] = same_side_oracle > 0.0
    enriched["loss_with_same_side_oracle_edge"] = (
        enriched["is_loss"] & enriched["same_side_oracle_profitable"]
    )
    enriched["large_exit_regret"] = (
        enriched["exit_regret"].astype(float) >= exit_regret_threshold
    )
    enriched["large_best_side_regret"] = (
        enriched["best_side_regret"].astype(float) >= best_side_regret_threshold
    )
    enriched["ev_overestimate_positive"] = (
        enriched["ev_overestimate_vs_realized"].astype(float) > 0.0
    )
    enriched["prior_context_risk_high"] = (
        enriched["prior_context_risk_score"].astype(float) >= prior_risk_threshold
    )
    return enriched


def safe_float_sum(frame: pd.DataFrame, column: str) -> float:
    if frame.empty:
        return 0.0
    return float(frame[column].astype(float).sum())


def safe_float_mean(frame: pd.DataFrame, column: str) -> float:
    if frame.empty:
        return 0.0
    return float(frame[column].astype(float).mean())


def safe_bool_count(frame: pd.DataFrame, column: str) -> int:
    if frame.empty:
        return 0
    return int(frame[column].fillna(False).astype(bool).sum())


def safe_bool_rate(frame: pd.DataFrame, column: str) -> float:
    if frame.empty:
        return 0.0
    return float(frame[column].fillna(False).astype(bool).mean())


def build_residual_summary(frame: pd.DataFrame) -> dict[str, Any]:
    losses = frame[frame["is_loss"].astype(bool)]
    summary: dict[str, Any] = {
        "trade_count": int(len(frame)),
        "total_adjusted_pnl": safe_float_sum(frame, "adjusted_pnl"),
        "loss_trade_count": int(len(losses)),
        "loss_adjusted_pnl": safe_float_sum(losses, "adjusted_pnl"),
        "win_rate": float((frame["adjusted_pnl"].astype(float) > 0.0).mean())
        if len(frame)
        else 0.0,
        "same_side_oracle_total": safe_float_sum(frame, "actual_taken_best_adjusted_pnl"),
        "actual_best_total": safe_float_sum(frame, "actual_best_adjusted_pnl"),
        "exit_regret_sum": safe_float_sum(frame, "exit_regret"),
        "best_side_regret_sum": safe_float_sum(frame, "best_side_regret"),
        "ev_overestimate_vs_realized_sum": safe_float_sum(
            frame,
            "ev_overestimate_vs_realized",
        ),
        "ev_overestimate_vs_oracle_sum": safe_float_sum(
            frame,
            "ev_overestimate_vs_oracle",
        ),
        "pred_taken_ev_mean": safe_float_mean(frame, "pred_taken_ev"),
        "actual_taken_best_adjusted_pnl_mean": safe_float_mean(
            frame,
            "actual_taken_best_adjusted_pnl",
        ),
    }
    for column in [
        "direction_error",
        "no_edge_entry",
        "predicted_side_error",
        "same_side_oracle_profitable",
        "loss_with_same_side_oracle_edge",
        "large_exit_regret",
        "large_best_side_regret",
        "ev_overestimate_positive",
        "prior_has_context",
        "prior_context_risk_high",
    ]:
        summary[f"{column}_count"] = safe_bool_count(frame, column)
        summary[f"{column}_rate"] = safe_bool_rate(frame, column)
    return summary


def summarize_slice(frame: pd.DataFrame) -> dict[str, Any]:
    return {
        "trade_count": int(len(frame)),
        "total_adjusted_pnl": safe_float_sum(frame, "adjusted_pnl"),
        "loss_adjusted_pnl": safe_float_sum(frame[frame["is_loss"].astype(bool)], "adjusted_pnl"),
        "avg_adjusted_pnl": safe_float_mean(frame, "adjusted_pnl"),
        "same_side_oracle_total": safe_float_sum(frame, "actual_taken_best_adjusted_pnl"),
        "actual_best_total": safe_float_sum(frame, "actual_best_adjusted_pnl"),
        "exit_regret_sum": safe_float_sum(frame, "exit_regret"),
        "best_side_regret_sum": safe_float_sum(frame, "best_side_regret"),
        "ev_overestimate_vs_realized_sum": safe_float_sum(
            frame,
            "ev_overestimate_vs_realized",
        ),
        "pred_taken_ev_mean": safe_float_mean(frame, "pred_taken_ev"),
        "actual_taken_best_adjusted_pnl_mean": safe_float_mean(
            frame,
            "actual_taken_best_adjusted_pnl",
        ),
        "direction_error_rate": safe_bool_rate(frame, "direction_error"),
        "no_edge_rate": safe_bool_rate(frame, "no_edge_entry"),
        "same_side_oracle_profitable_rate": safe_bool_rate(
            frame,
            "same_side_oracle_profitable",
        ),
        "prior_has_context_rate": safe_bool_rate(frame, "prior_has_context"),
        "prior_context_risk_score_mean": safe_float_mean(
            frame,
            "prior_context_risk_score",
        ),
    }


def summarize_flags(
    frame: pd.DataFrame,
    *,
    flag_columns: tuple[str, ...] = DEFAULT_FLAG_COLUMNS,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    total_pnl = safe_float_sum(frame, "adjusted_pnl")
    total_count = int(len(frame))
    for column in flag_columns:
        if column not in frame.columns:
            continue
        flagged = frame[frame[column].fillna(False).astype(bool)]
        row = {
            "flag": column,
            "flagged_trade_count": int(len(flagged)),
            "flagged_trade_share": float(len(flagged) / total_count) if total_count else 0.0,
            "flagged_adjusted_pnl": safe_float_sum(flagged, "adjusted_pnl"),
            "block_delta_if_removed": -safe_float_sum(flagged, "adjusted_pnl"),
            "total_adjusted_pnl": total_pnl,
            "kept_adjusted_pnl_if_removed": total_pnl - safe_float_sum(flagged, "adjusted_pnl"),
            **summarize_slice(flagged),
        }
        rows.append(row)
    return pd.DataFrame(rows).sort_values(
        ["block_delta_if_removed", "flagged_trade_count"],
        ascending=[False, False],
    )


def summarize_groups(frame: pd.DataFrame, group_columns: list[str]) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=group_columns)
    rows: list[dict[str, Any]] = []
    for key, group in frame.groupby(group_columns, dropna=False, observed=True):
        if not isinstance(key, tuple):
            key = (key,)
        row = dict(zip(group_columns, key))
        row.update(summarize_slice(group))
        row["loss_trade_count"] = safe_bool_count(group, "is_loss")
        row["direction_error_count"] = safe_bool_count(group, "direction_error")
        row["large_exit_regret_count"] = safe_bool_count(group, "large_exit_regret")
        row["loss_with_same_side_oracle_edge_count"] = safe_bool_count(
            group,
            "loss_with_same_side_oracle_edge",
        )
        rows.append(row)
    return pd.DataFrame(rows).sort_values(
        ["total_adjusted_pnl", "trade_count"],
        ascending=[True, False],
    )


def build_diagnostics(args: argparse.Namespace) -> Path:
    trades = normalize_trade_frame(read_trade_frames(args.enriched_trades))
    filtered = filter_frame(
        trades,
        roles=set(parse_optional_csv(args.roles)),
        candidates=set(parse_optional_csv(args.candidates)),
        months=set(parse_optional_csv(args.months)),
    )
    if filtered.empty:
        raise ValueError("no enriched trades remain after filters")
    residual = add_failure_flags(
        filtered,
        exit_regret_threshold=args.exit_regret_threshold,
        best_side_regret_threshold=args.best_side_regret_threshold,
        prior_risk_threshold=args.prior_risk_threshold,
    )

    run_dir = make_run_dir(args.output_dir, args.label)
    residual.to_csv(run_dir / "residual_trades.csv", index=False)

    summary = build_residual_summary(residual)
    (run_dir / "residual_summary.json").write_text(
        json.dumps(summary, indent=2, default=local_json_default),
        encoding="utf-8",
    )

    flag_summary = summarize_flags(residual)
    flag_summary.to_csv(run_dir / "failure_flag_summary.csv", index=False)

    role_month = summarize_groups(residual, ["role", "candidate", "month"])
    role_month.to_csv(run_dir / "role_month_residual_summary.csv", index=False)

    context = summarize_groups(
        residual,
        ["role", "candidate", "month", "direction", "combined_regime", "session_regime"],
    )
    context.to_csv(run_dir / "context_failure_summary.csv", index=False)
    context.head(args.top_n).to_csv(run_dir / "top_negative_contexts.csv", index=False)

    losses = residual[residual["adjusted_pnl"].astype(float) < 0.0].sort_values(
        "adjusted_pnl",
        ascending=True,
    )
    losses.head(args.top_n).to_csv(run_dir / "loss_trade_details.csv", index=False)

    config = {
        "enriched_trades": args.enriched_trades,
        "roles": args.roles,
        "candidates": args.candidates,
        "months": args.months,
        "exit_regret_threshold": args.exit_regret_threshold,
        "best_side_regret_threshold": args.best_side_regret_threshold,
        "prior_risk_threshold": args.prior_risk_threshold,
        "input_trade_count": int(len(trades)),
        "residual_trade_count": int(len(residual)),
    }
    (run_dir / "config.json").write_text(
        json.dumps(config, indent=2, default=local_json_default),
        encoding="utf-8",
    )

    print("Residual summary:")
    print(json.dumps(summary, indent=2, default=local_json_default))
    print("\nFailure flag summary:")
    print(
        flag_summary[
            [
                "flag",
                "flagged_trade_count",
                "flagged_adjusted_pnl",
                "block_delta_if_removed",
                "exit_regret_sum",
                "best_side_regret_sum",
            ]
        ].to_string(index=False)
    )
    print(f"artifacts: {run_dir}")
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--enriched-trades", type=Path, action="append", required=True)
    parser.add_argument("--roles", default="")
    parser.add_argument("--candidates", default="")
    parser.add_argument("--months", default="")
    parser.add_argument("--exit-regret-threshold", type=float, default=10.0)
    parser.add_argument("--best-side-regret-threshold", type=float, default=10.0)
    parser.add_argument("--prior-risk-threshold", type=float, default=0.50)
    parser.add_argument("--top-n", type=int, default=20)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/reports/backtests"),
    )
    parser.add_argument("--label", default="entry_ev_residual_month_loss_diagnostics")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    build_diagnostics(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
