#!/usr/bin/env python3
"""Candidate-path diagnostics for uncompensated large-loss targets."""

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


DEFAULT_CONTEXT_COLUMNS = "direction,combined_regime,session_regime"
PATH_COLUMNS = ["source", "role", "family", "variant", "candidate", "month"]
OPTIONAL_TEXT_COLUMNS = [
    "direction",
    "combined_regime",
    "session_regime",
    "entry_block_rule",
    "apply_universe",
    "horizon_mode",
]


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
    return [part.strip() for part in str(value).split(",") if part.strip()]


def numeric_series(frame: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=float)
    values = pd.to_numeric(frame[column], errors="coerce")
    return values.replace([np.inf, -np.inf], np.nan).fillna(default).astype(float)


def bool_series(frame: pd.DataFrame, column: str, default: bool = False) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=bool)
    series = frame[column]
    if pd.api.types.is_bool_dtype(series):
        return series.fillna(default).astype(bool)
    if pd.api.types.is_numeric_dtype(series):
        return series.fillna(float(default)).astype(float).ne(0.0)
    return series.astype(str).str.strip().str.lower().isin({"true", "1", "yes", "y"})


def text_series(frame: pd.DataFrame, column: str, default: str = "missing") -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype="string")
    return (
        frame[column]
        .astype("string")
        .fillna(default)
        .str.strip()
        .replace({"": default, "nan": default, "None": default})
    )


def normalize_trade_paths(
    frame: pd.DataFrame,
    *,
    large_loss_threshold: float,
    variant_column: str | None = None,
    exclude_entry_blocked: bool = True,
) -> pd.DataFrame:
    required = {"role", "month", "candidate", "variant", "adjusted_pnl"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError("trade path frame missing columns: " + ", ".join(missing))

    output = frame.copy()
    if variant_column is None and "selector_variant" in output.columns:
        variant_column = "selector_variant"
    if variant_column:
        if variant_column not in output.columns:
            raise ValueError(f"variant column not found: {variant_column}")
        output["variant"] = output[variant_column]
    if exclude_entry_blocked and "entry_blocked" in output.columns:
        output = output[~bool_series(output, "entry_blocked")].copy()
        if output.empty:
            raise ValueError("no trades remain after entry_blocked exclusion")
    for column in PATH_COLUMNS:
        output[column] = text_series(output, column, default="unknown")
    output["month"] = output["month"].astype("string").str.slice(0, 7)
    for column in OPTIONAL_TEXT_COLUMNS:
        output[column] = text_series(output, column)
    for column in ["entry_decision_timestamp", "exit_decision_timestamp", "entry_timestamp", "exit_timestamp"]:
        if column in output.columns:
            output[column] = pd.to_datetime(output[column], utc=True, errors="coerce")
    output["adjusted_pnl"] = numeric_series(output, "adjusted_pnl")
    output["trade_count_unit"] = 1
    output["is_loss"] = output["adjusted_pnl"].lt(0.0)
    if "is_large_loss" in output.columns:
        output["is_large_loss"] = bool_series(output, "is_large_loss")
    else:
        output["is_large_loss"] = output["adjusted_pnl"].le(float(large_loss_threshold))
    return output.reset_index(drop=True)


def make_context_key(frame: pd.DataFrame, context_columns: list[str]) -> pd.Series:
    available = [column for column in context_columns if column in frame.columns]
    if not available:
        return pd.Series("all", index=frame.index, dtype="string")
    return frame[available].astype(str).agg("|".join, axis=1)


def _sum_positive(values: pd.Series) -> float:
    numeric = values.astype(float)
    return float(numeric[numeric.gt(0.0)].sum())


def _sum_negative(values: pd.Series) -> float:
    numeric = values.astype(float)
    return float(numeric[numeric.lt(0.0)].sum())


def add_context_targets(
    frame: pd.DataFrame,
    *,
    context_columns: list[str],
    large_win_threshold: float,
) -> pd.DataFrame:
    output = frame.copy()
    output["context_key"] = make_context_key(output, context_columns)
    group_columns = [*PATH_COLUMNS, "context_key"]
    context = (
        output.groupby(group_columns, dropna=False)
        .agg(
            context_trade_count=("adjusted_pnl", "size"),
            context_total_pnl=("adjusted_pnl", "sum"),
            context_win_count=("adjusted_pnl", lambda values: int((values > 0).sum())),
            context_loss_count=("adjusted_pnl", lambda values: int((values < 0).sum())),
            context_large_loss_count=("is_large_loss", lambda values: int(values.astype(bool).sum())),
            context_win_pnl=("adjusted_pnl", _sum_positive),
            context_loss_pnl=("adjusted_pnl", _sum_negative),
            context_max_win=("adjusted_pnl", "max"),
            context_min_pnl=("adjusted_pnl", "min"),
        )
        .reset_index()
    )
    output = output.merge(context, on=group_columns, how="left", validate="many_to_one")
    output["context_net_positive"] = output["context_total_pnl"].gt(0.0)
    output["context_has_large_win"] = output["context_max_win"].ge(float(large_win_threshold))
    output["large_loss_compensated_by_context"] = output["is_large_loss"] & output[
        "context_net_positive"
    ]
    output["large_loss_uncompensated_by_context"] = output["is_large_loss"] & ~output[
        "context_net_positive"
    ]
    return output


def add_sequence_state(frame: pd.DataFrame) -> pd.DataFrame:
    output = frame.copy()
    if "entry_decision_timestamp" not in output.columns:
        output["entry_decision_timestamp"] = pd.NaT
    if "exit_decision_timestamp" not in output.columns:
        output["exit_decision_timestamp"] = pd.NaT
    output = output.sort_values([*PATH_COLUMNS, "entry_decision_timestamp"]).reset_index(drop=True)
    grouped = output.groupby(PATH_COLUMNS, dropna=False)
    output["trade_index_in_month"] = grouped.cumcount() + 1
    output["month_trade_count"] = grouped["adjusted_pnl"].transform("size")
    output["prev_adjusted_pnl"] = grouped["adjusted_pnl"].shift(1)
    output["next_adjusted_pnl"] = grouped["adjusted_pnl"].shift(-1)
    output["prev_is_uncompensated_target"] = (
        grouped["large_loss_uncompensated_by_context"].shift(1).fillna(False).astype(bool)
    )
    output["next_is_uncompensated_target"] = (
        grouped["large_loss_uncompensated_by_context"].shift(-1).fillna(False).astype(bool)
    )
    output["prev_exit_decision_timestamp"] = grouped["exit_decision_timestamp"].shift(1)
    output["next_entry_decision_timestamp"] = grouped["entry_decision_timestamp"].shift(-1)
    output["decision_minutes_since_prev_exit"] = (
        output["entry_decision_timestamp"] - output["prev_exit_decision_timestamp"]
    ).dt.total_seconds() / 60.0
    output["decision_minutes_until_next_entry"] = (
        output["next_entry_decision_timestamp"] - output["exit_decision_timestamp"]
    ).dt.total_seconds() / 60.0
    output["prev_result_bucket"] = np.select(
        [
            output["prev_adjusted_pnl"].isna(),
            output["prev_adjusted_pnl"].lt(0.0),
            output["prev_adjusted_pnl"].ge(0.0),
        ],
        ["first", "prev_loss", "prev_win"],
        default="unknown",
    )
    output["next_result_bucket"] = np.select(
        [
            output["next_adjusted_pnl"].isna(),
            output["next_adjusted_pnl"].lt(0.0),
            output["next_adjusted_pnl"].ge(0.0),
        ],
        ["last", "next_loss", "next_win"],
        default="unknown",
    )
    return output


def summarize_month_paths(frame: pd.DataFrame) -> pd.DataFrame:
    working = frame.copy()
    working["target_pnl_component"] = working["adjusted_pnl"].where(
        working["large_loss_uncompensated_by_context"].astype(bool),
        0.0,
    )
    working["target_next_win"] = (
        working["large_loss_uncompensated_by_context"].astype(bool)
        & working["next_adjusted_pnl"].fillna(0.0).gt(0.0)
    )
    working["target_next_win_pnl_component"] = working["next_adjusted_pnl"].where(
        working["target_next_win"],
        0.0,
    )
    working["target_prev_win"] = (
        working["large_loss_uncompensated_by_context"].astype(bool)
        & working["prev_adjusted_pnl"].fillna(0.0).gt(0.0)
    )
    grouped = working.groupby(PATH_COLUMNS, dropna=False)
    summary = grouped.agg(
        total_pnl=("adjusted_pnl", "sum"),
        trade_count=("adjusted_pnl", "size"),
        loss_count=("is_loss", "sum"),
        large_loss_count=("is_large_loss", "sum"),
        uncompensated_target_count=("large_loss_uncompensated_by_context", "sum"),
        compensated_large_loss_count=("large_loss_compensated_by_context", "sum"),
        uncompensated_target_pnl=("target_pnl_component", "sum"),
        uncompensated_target_next_win_count=("target_next_win", "sum"),
        uncompensated_target_next_win_pnl=("target_next_win_pnl_component", "sum"),
        uncompensated_target_prev_win_count=("target_prev_win", "sum"),
        long_trade_count=("direction", lambda values: int(values.astype(str).eq("long").sum())),
        short_trade_count=("direction", lambda values: int(values.astype(str).eq("short").sum())),
        max_drawdown=("adjusted_pnl", max_drawdown_from_pnl),
    ).reset_index()
    trades = summary["trade_count"].replace(0, np.nan)
    summary["max_side_trade_share"] = (
        pd.concat(
            [
                summary["long_trade_count"].astype(float) / trades,
                summary["short_trade_count"].astype(float) / trades,
            ],
            axis=1,
        )
        .max(axis=1)
        .fillna(0.0)
    )
    return summary.sort_values(["total_pnl", "uncompensated_target_count"], ascending=[True, False])


def max_drawdown_from_pnl(values: pd.Series) -> float:
    if values.empty:
        return 0.0
    equity = values.astype(float).cumsum()
    running_max = equity.cummax().clip(lower=0.0)
    drawdown = running_max - equity
    return float(drawdown.max()) if len(drawdown) else 0.0


def summarize_candidates(monthly: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for key, group in monthly.groupby(["variant", "candidate"], dropna=False):
        variant, candidate = key
        role_totals = group.groupby("role")["total_pnl"].sum()
        role_trades = group.groupby("role")["trade_count"].sum()
        total_pnl = float(group["total_pnl"].sum())
        trade_count = int(group["trade_count"].sum())
        long_count = int(group["long_trade_count"].sum())
        short_count = int(group["short_trade_count"].sum())
        rows.append(
            {
                "source": "all_sources",
                "source_count": int(group["source"].nunique()) if "source" in group.columns else 0,
                "variant": variant,
                "candidate": candidate,
                "total_pnl": total_pnl,
                "trade_count": trade_count,
                "role_total_pnl_min": float(role_totals.min()) if len(role_totals) else 0.0,
                "month_pnl_min": float(group["total_pnl"].min()) if len(group) else 0.0,
                "role_trade_count_min": int(role_trades.min()) if len(role_trades) else 0,
                "month_trade_count_min": int(group["trade_count"].min()) if len(group) else 0,
                "positive_role_count": int((role_totals > 0).sum()) if len(role_totals) else 0,
                "role_count": int(len(role_totals)),
                "uncompensated_target_count": int(group["uncompensated_target_count"].sum()),
                "uncompensated_target_pnl": float(group["uncompensated_target_pnl"].sum()),
                "large_loss_count": int(group["large_loss_count"].sum()),
                "compensated_large_loss_count": int(group["compensated_large_loss_count"].sum()),
                "uncompensated_target_next_win_count": int(
                    group["uncompensated_target_next_win_count"].sum()
                ),
                "uncompensated_target_next_win_pnl": float(
                    group["uncompensated_target_next_win_pnl"].sum()
                ),
                "max_drawdown_max": float(group["max_drawdown"].max()) if len(group) else 0.0,
                "max_side_trade_share": float(group["max_side_trade_share"].max())
                if len(group)
                else 0.0,
                "overall_side_trade_share": float(max(long_count, short_count) / trade_count)
                if trade_count
                else 0.0,
            }
        )
    output = pd.DataFrame(rows)
    if output.empty:
        return output
    return output.sort_values(
        [
            "month_pnl_min",
            "role_total_pnl_min",
            "total_pnl",
            "uncompensated_target_count",
        ],
        ascending=[False, False, False, True],
    ).reset_index(drop=True)


def summarize_target_rows(frame: pd.DataFrame, *, top_n: int) -> pd.DataFrame:
    columns = [
        *PATH_COLUMNS,
        "entry_block_rule",
        "apply_universe",
        "horizon_mode",
        "trade_index_in_month",
        "month_trade_count",
        "direction",
        "combined_regime",
        "session_regime",
        "adjusted_pnl",
        "context_total_pnl",
        "context_trade_count",
        "prev_result_bucket",
        "next_result_bucket",
        "prev_adjusted_pnl",
        "next_adjusted_pnl",
    ]
    available = [column for column in columns if column in frame.columns]
    return (
        frame[frame["large_loss_uncompensated_by_context"].astype(bool)]
        .sort_values(["adjusted_pnl", "context_total_pnl"], ascending=[True, True])
        [available]
        .head(top_n)
    )


def build_diagnostics(args: argparse.Namespace) -> Path:
    raw = pd.concat([pd.read_csv(path) for path in args.trade_paths], ignore_index=True)
    normalized = normalize_trade_paths(
        raw,
        large_loss_threshold=args.large_loss_threshold,
        variant_column=args.variant_column,
        exclude_entry_blocked=not args.include_entry_blocked,
    )
    context_columns = parse_csv(args.context_columns)
    enriched = add_context_targets(
        normalized,
        context_columns=context_columns,
        large_win_threshold=args.large_win_threshold,
    )
    enriched = add_sequence_state(enriched)
    monthly = summarize_month_paths(enriched)
    candidates = summarize_candidates(monthly)
    targets = summarize_target_rows(enriched, top_n=args.top_n)

    run_dir = make_run_dir(args.output_dir, args.label)
    enriched.to_csv(run_dir / "uncompensated_candidate_path_rows.csv", index=False)
    monthly.to_csv(run_dir / "uncompensated_candidate_month_summary.csv", index=False)
    candidates.to_csv(run_dir / "uncompensated_candidate_summary.csv", index=False)
    targets.to_csv(run_dir / "uncompensated_candidate_target_rows.csv", index=False)
    config = {
        "trade_paths": args.trade_paths,
        "context_columns": context_columns,
        "large_loss_threshold": args.large_loss_threshold,
        "large_win_threshold": args.large_win_threshold,
        "variant_column": args.variant_column,
        "exclude_entry_blocked": not args.include_entry_blocked,
        "note": (
            "Candidate paths are realized path variants, not the full unselected entry "
            "candidate feed. next_* columns are diagnostics only."
        ),
    }
    (run_dir / "config.json").write_text(
        json.dumps(config, indent=2, sort_keys=True, default=local_json_default),
        encoding="utf-8",
    )

    print(f"Wrote uncompensated candidate-path diagnostics to {run_dir}")
    print("\nTop candidate summary:")
    print(candidates.head(args.top_n).to_string(index=False))
    print("\nTop target rows:")
    print(targets.head(args.top_n).to_string(index=False))
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trade-paths", type=Path, action="append", required=True)
    parser.add_argument("--label", default="entry_ev_uncompensated_candidate_path")
    parser.add_argument("--output-dir", type=Path, default=Path("data/reports/backtests"))
    parser.add_argument("--context-columns", default=DEFAULT_CONTEXT_COLUMNS)
    parser.add_argument("--large-loss-threshold", type=float, default=-2.0)
    parser.add_argument("--large-win-threshold", type=float, default=5.0)
    parser.add_argument(
        "--variant-column",
        default=None,
        help="Column to use as the candidate path variant. Defaults to selector_variant when present.",
    )
    parser.add_argument(
        "--include-entry-blocked",
        action="store_true",
        help="Include rows already blocked by entry-block overlays. Defaults to excluding them.",
    )
    parser.add_argument("--top-n", type=int, default=40)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    build_diagnostics(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
