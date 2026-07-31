#!/usr/bin/env python3
"""Diagnose residual floor breaches from entry-block overlay trades."""

from __future__ import annotations

import argparse
import json
import re
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

from trade_data.backtest import make_run_dir  # noqa: E402

from entry_ev_supervised_shrinkage_policy_inputs import local_json_default  # noqa: E402


DEFAULT_HORIZONS = (60, 240, 720)
REQUIRED_TRADE_COLUMNS = {
    "role",
    "month",
    "selector_variant",
    "direction",
    "adjusted_pnl",
    "entry_blocked",
}
REQUIRED_MONTHLY_COLUMNS = {
    "role",
    "month",
    "variant",
    "total_adjusted_pnl",
    "trade_count",
}


def parse_int_csv(value: str) -> list[int]:
    return [int(part.strip()) for part in value.split(",") if part.strip()]


def numeric_series(frame: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=float)
    values = pd.to_numeric(frame[column], errors="coerce")
    return values.replace([np.inf, -np.inf], np.nan).fillna(default).astype(float)


def bool_series(frame: pd.DataFrame, column: str, default: bool = False) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=bool)
    values = frame[column]
    if pd.api.types.is_bool_dtype(values):
        return values.fillna(default).astype(bool)
    if pd.api.types.is_numeric_dtype(values):
        return values.fillna(float(default)).astype(float).ne(0.0)
    normalized = values.astype(str).str.lower().str.strip()
    return normalized.isin({"true", "1", "yes", "y"})


def require_columns(frame: pd.DataFrame, required: set[str], *, source: Path) -> None:
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"{source} missing columns: {', '.join(missing)}")


def normalize_overlay_trades(path: Path, *, horizons: list[int]) -> pd.DataFrame:
    frame = pd.read_csv(path)
    require_columns(frame, REQUIRED_TRADE_COLUMNS, source=path)
    output = frame.copy()
    output["role"] = output["role"].astype(str)
    output["month"] = output["month"].astype(str).str.slice(0, 7)
    output["selector_variant"] = output["selector_variant"].astype(str)
    output["direction"] = output["direction"].astype(str).str.lower()
    output["entry_blocked"] = bool_series(output, "entry_blocked")
    output["adjusted_pnl"] = numeric_series(output, "adjusted_pnl")
    output["holding_minutes"] = numeric_series(output, "holding_minutes")
    for column in [
        "combined_regime",
        "session_regime",
        "entry_hour",
        "selected_loss_first_prob",
        "pred_side_confidence_gap",
        "pred_taken_entry_local_rank",
        "pred_taken_ev",
        "pred_opposite_ev",
        "exit_capture_ratio",
    ]:
        if column in output.columns and column not in {"combined_regime", "session_regime"}:
            output[column] = numeric_series(output, column, default=np.nan)
        elif column not in output.columns:
            output[column] = "" if column in {"combined_regime", "session_regime"} else np.nan
    output["combined_regime"] = output["combined_regime"].fillna("").astype(str)
    output["session_regime"] = output["session_regime"].fillna("").astype(str)
    output["context"] = (
        output["direction"]
        + "|"
        + output["combined_regime"]
        + "|"
        + output["session_regime"]
    )
    return add_fixed_horizon_deltas(output, horizons=horizons)


def normalize_monthly_metrics(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    require_columns(frame, REQUIRED_MONTHLY_COLUMNS, source=path)
    output = frame.copy()
    output["role"] = output["role"].astype(str)
    output["month"] = output["month"].astype(str).str.slice(0, 7)
    output["variant"] = output["variant"].astype(str)
    output["total_adjusted_pnl"] = numeric_series(output, "total_adjusted_pnl")
    output["trade_count"] = numeric_series(output, "trade_count").astype(int)
    output["long_trade_count"] = numeric_series(output, "long_trade_count").astype(int)
    output["short_trade_count"] = numeric_series(output, "short_trade_count").astype(int)
    if "max_side_trade_share" in output.columns:
        output["max_side_trade_share"] = numeric_series(output, "max_side_trade_share")
    else:
        trade_count = output["trade_count"].replace(0, np.nan)
        output["max_side_trade_share"] = (
            pd.concat(
                [
                    output["long_trade_count"] / trade_count,
                    output["short_trade_count"] / trade_count,
                ],
                axis=1,
            )
            .max(axis=1)
            .fillna(0.0)
        )
    return output


def add_fixed_horizon_deltas(frame: pd.DataFrame, *, horizons: list[int]) -> pd.DataFrame:
    output = frame.copy()
    delta_columns: list[str] = []
    horizon_by_delta_column: dict[str, int] = {}
    for horizon in horizons:
        actual_column = f"selected_fixed_{horizon}m_actual_pnl"
        if actual_column not in output.columns:
            output[actual_column] = np.nan
        output[actual_column] = numeric_series(output, actual_column, default=np.nan)
        delta_column = f"fixed_{horizon}m_delta_vs_realized"
        output[delta_column] = output[actual_column] - output["adjusted_pnl"]
        delta_columns.append(delta_column)
        horizon_by_delta_column[delta_column] = horizon

    deltas = output[delta_columns]
    output["best_fixed_delta_vs_realized"] = deltas.max(axis=1, skipna=True)
    best_delta_column = deltas.idxmax(axis=1, skipna=True)
    output["best_fixed_horizon_minutes"] = best_delta_column.map(horizon_by_delta_column)
    output["best_fixed_horizon_minutes"] = numeric_series(
        output,
        "best_fixed_horizon_minutes",
        default=np.nan,
    )
    output["best_fixed_actual_pnl"] = (
        output["adjusted_pnl"] + output["best_fixed_delta_vs_realized"]
    )
    output["best_fixed_improves_realized"] = output["best_fixed_delta_vs_realized"].gt(0.0)
    return output


def horizon_mode_counts(frame: pd.DataFrame) -> str:
    if frame.empty or "best_fixed_horizon_minutes" not in frame.columns:
        return ""
    values = (
        frame.loc[frame["best_fixed_delta_vs_realized"].gt(0.0), "best_fixed_horizon_minutes"]
        .dropna()
        .astype(int)
    )
    if values.empty:
        return ""
    counts = values.value_counts().sort_index()
    return ";".join(f"{int(horizon)}m:{int(count)}" for horizon, count in counts.items())


def summarize_negative_months(
    *,
    monthly: pd.DataFrame,
    trades: pd.DataFrame,
    horizons: list[int],
    month_floor: float,
    thin_month_trade_threshold: int,
    side_share_threshold: float,
) -> pd.DataFrame:
    negative = monthly[monthly["total_adjusted_pnl"].lt(month_floor)].copy()
    rows: list[dict[str, Any]] = []
    for _, month_row in negative.sort_values("total_adjusted_pnl").iterrows():
        role = str(month_row["role"])
        month = str(month_row["month"])
        month_trades = trades[(trades["role"].eq(role)) & (trades["month"].eq(month))]
        losses = month_trades[month_trades["adjusted_pnl"].lt(0.0)]
        wins = month_trades[month_trades["adjusted_pnl"].ge(0.0)]
        best_improved_losses = losses[losses["best_fixed_delta_vs_realized"].gt(0.0)]
        row = month_row.to_dict()
        row.update(
            {
                "loss_trade_count": int(len(losses)),
                "loss_adjusted_pnl": float(losses["adjusted_pnl"].sum()),
                "win_adjusted_pnl": float(wins["adjusted_pnl"].sum()),
                "min_trade_pnl": float(month_trades["adjusted_pnl"].min())
                if len(month_trades)
                else 0.0,
                "single_trade_month": bool(int(month_row["trade_count"]) <= 1),
                "thin_month": bool(int(month_row["trade_count"]) < thin_month_trade_threshold),
                "side_share_high": bool(
                    float(month_row["max_side_trade_share"]) > side_share_threshold
                ),
                "fixed_best_improved_loss_count": int(len(best_improved_losses)),
                "fixed_best_improved_loss_delta_sum": float(
                    best_improved_losses["best_fixed_delta_vs_realized"].sum()
                ),
                "fixed_best_horizon_counts": horizon_mode_counts(losses),
            }
        )
        for horizon in horizons:
            delta_column = f"fixed_{horizon}m_delta_vs_realized"
            if delta_column in losses.columns:
                row[f"loss_fixed_{horizon}m_delta_sum"] = float(losses[delta_column].sum())
        rows.append(row)
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values("total_adjusted_pnl").reset_index(drop=True)


def summarize_negative_contexts(trades: pd.DataFrame, negative_months: pd.DataFrame) -> pd.DataFrame:
    if negative_months.empty:
        return pd.DataFrame()
    keys = negative_months[["role", "month"]].drop_duplicates()
    negative_trades = trades.merge(keys, on=["role", "month"], how="inner")
    negative_loss_contexts = set(
        negative_trades.loc[negative_trades["adjusted_pnl"].lt(0.0), "context"].astype(str)
    )
    rows: list[dict[str, Any]] = []
    for context, group in trades[trades["context"].isin(negative_loss_contexts)].groupby(
        "context",
        dropna=False,
    ):
        negative_group = negative_trades[negative_trades["context"].eq(context)]
        losses = group[group["adjusted_pnl"].lt(0.0)]
        rows.append(
            {
                "context": context,
                "trade_count": int(len(group)),
                "total_adjusted_pnl": float(group["adjusted_pnl"].sum()),
                "loss_trade_count": int(len(losses)),
                "loss_adjusted_pnl": float(losses["adjusted_pnl"].sum()),
                "win_adjusted_pnl": float(group.loc[group["adjusted_pnl"].ge(0.0), "adjusted_pnl"].sum()),
                "negative_month_trade_count": int(len(negative_group)),
                "negative_month_adjusted_pnl": float(negative_group["adjusted_pnl"].sum()),
                "block_delta_if_context_removed": -float(group["adjusted_pnl"].sum()),
            }
        )
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values("total_adjusted_pnl").reset_index(drop=True)


def summarize_role_support(monthly: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for role, group in monthly.groupby("role", dropna=False):
        rows.append(
            {
                "role": role,
                "role_total_pnl": float(group["total_adjusted_pnl"].sum()),
                "role_trade_count": int(group["trade_count"].sum()),
                "role_month_min_pnl": float(group["total_adjusted_pnl"].min()),
                "role_month_trade_min": int(group["trade_count"].min()),
                "active_month_count": int(group["trade_count"].gt(0).sum()),
                "month_count": int(group["month"].nunique()),
            }
        )
    return pd.DataFrame(rows).sort_values("role_total_pnl").reset_index(drop=True)


def selector_variant_slug(variant: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", variant).strip("_")[:80]


def build_diagnostics(args: argparse.Namespace) -> Path:
    horizons = parse_int_csv(args.fixed_horizons)
    trades = normalize_overlay_trades(args.overlay_trades, horizons=horizons)
    monthly = normalize_monthly_metrics(args.monthly_metrics)
    trades = trades[trades["selector_variant"].eq(args.variant)].copy()
    monthly = monthly[monthly["variant"].eq(args.variant)].copy()
    if trades.empty:
        raise ValueError(f"no overlay trades for variant: {args.variant}")
    if monthly.empty:
        raise ValueError(f"no monthly metrics for variant: {args.variant}")
    if not args.include_blocked:
        trades = trades[~trades["entry_blocked"].astype(bool)].copy()

    negative_months = summarize_negative_months(
        monthly=monthly,
        trades=trades,
        horizons=horizons,
        month_floor=args.month_floor,
        thin_month_trade_threshold=args.thin_month_trade_threshold,
        side_share_threshold=args.side_share_threshold,
    )
    negative_contexts = summarize_negative_contexts(trades, negative_months)
    role_support = summarize_role_support(monthly)
    negative_keys = negative_months[["role", "month"]].drop_duplicates()
    negative_trades = trades.merge(negative_keys, on=["role", "month"], how="inner")
    negative_losses = negative_trades[negative_trades["adjusted_pnl"].lt(0.0)].copy()

    run_dir = make_run_dir(args.output_dir, args.label)
    monthly.to_csv(run_dir / "variant_monthly_metrics.csv", index=False)
    trades.to_csv(run_dir / "variant_unblocked_trades.csv", index=False)
    negative_months.to_csv(run_dir / "negative_month_summary.csv", index=False)
    negative_losses.sort_values(["role", "month", "adjusted_pnl"]).to_csv(
        run_dir / "negative_loss_trade_details.csv",
        index=False,
    )
    negative_contexts.to_csv(run_dir / "negative_context_summary.csv", index=False)
    role_support.to_csv(run_dir / "role_support_summary.csv", index=False)

    summary = {
        "variant": args.variant,
        "variant_slug": selector_variant_slug(args.variant),
        "month_floor": args.month_floor,
        "trade_count": int(len(trades)),
        "total_adjusted_pnl": float(monthly["total_adjusted_pnl"].sum()),
        "negative_month_count": int(len(negative_months)),
        "single_trade_negative_month_count": int(
            negative_months.get("single_trade_month", pd.Series(dtype=bool)).sum()
        ),
        "thin_negative_month_count": int(
            negative_months.get("thin_month", pd.Series(dtype=bool)).sum()
        ),
        "side_share_high_negative_month_count": int(
            negative_months.get("side_share_high", pd.Series(dtype=bool)).sum()
        ),
        "negative_loss_trade_count": int(len(negative_losses)),
        "fixed_best_improved_negative_loss_count": int(
            negative_losses["best_fixed_delta_vs_realized"].gt(0.0).sum()
        )
        if not negative_losses.empty
        else 0,
    }
    (run_dir / "diagnostic_summary.json").write_text(
        json.dumps(summary, indent=2, default=local_json_default),
        encoding="utf-8",
    )
    config = {
        "overlay_trades": args.overlay_trades,
        "monthly_metrics": args.monthly_metrics,
        "variant": args.variant,
        "fixed_horizons": horizons,
        "include_blocked": args.include_blocked,
        "month_floor": args.month_floor,
        "thin_month_trade_threshold": args.thin_month_trade_threshold,
        "side_share_threshold": args.side_share_threshold,
    }
    (run_dir / "config.json").write_text(
        json.dumps(config, indent=2, default=local_json_default),
        encoding="utf-8",
    )

    print("Residual floor diagnostic summary:")
    print(json.dumps(summary, indent=2, default=local_json_default))
    print("\nNegative months:")
    printable_columns = [
        "role",
        "month",
        "total_adjusted_pnl",
        "trade_count",
        "loss_trade_count",
        "single_trade_month",
        "thin_month",
        "side_share_high",
        "fixed_best_improved_loss_count",
        "fixed_best_horizon_counts",
    ]
    if not negative_months.empty:
        print(negative_months[printable_columns].to_string(index=False))
    print(f"artifacts: {run_dir}")
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--overlay-trades", type=Path, required=True)
    parser.add_argument("--monthly-metrics", type=Path, required=True)
    parser.add_argument("--variant", required=True)
    parser.add_argument("--fixed-horizons", default="60,240,720")
    parser.add_argument("--include-blocked", action="store_true")
    parser.add_argument("--month-floor", type=float, default=0.0)
    parser.add_argument("--thin-month-trade-threshold", type=int, default=5)
    parser.add_argument("--side-share-threshold", type=float, default=0.95)
    parser.add_argument("--output-dir", type=Path, default=Path("data/reports/backtests"))
    parser.add_argument("--label", default="entry_ev_overlay_residual_floor_diagnostics")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    build_diagnostics(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
