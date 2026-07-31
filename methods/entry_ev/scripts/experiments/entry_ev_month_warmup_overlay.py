#!/usr/bin/env python3
"""Apply observable month-warmup gates to an existing overlay trade path."""

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

from entry_ev_hold_extension_stateful_replay import max_drawdown_from_trades  # noqa: E402


DEFAULT_WARMUP_RULES = (
    "none,"
    "skip_first_1,"
    "skip_first_2,"
    "skip_first_3,"
    "wait_opposite_seen,"
    "skip_first_1_wait_opposite_seen,"
    "wait_both_sides_seen"
)
REQUIRED_COLUMNS = {
    "role",
    "month",
    "candidate",
    "direction",
    "entry_decision_timestamp",
    "adjusted_pnl",
}
GROUP_COLUMNS = ["source", "role", "family", "selector_variant", "candidate", "month"]


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


def filter_values(frame: pd.DataFrame, column: str, values: list[str]) -> pd.DataFrame:
    if not values:
        return frame
    if column not in frame.columns:
        raise ValueError(f"cannot filter by missing column: {column}")
    return frame[frame[column].astype(str).isin(values)].copy()


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


def read_overlay_trades(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    missing = sorted(REQUIRED_COLUMNS - set(frame.columns))
    if missing:
        raise ValueError(f"{path} missing columns: {', '.join(missing)}")
    output = frame.copy()
    if "selector_variant" not in output.columns:
        if "variant" not in output.columns:
            raise ValueError(f"{path} missing columns: selector_variant or variant")
        output["selector_variant"] = output["variant"]
    for column, fallback in [("source", "unknown"), ("family", "unknown")]:
        if column not in output.columns:
            output[column] = fallback
    output["role"] = output["role"].astype(str)
    output["source"] = output["source"].astype(str)
    output["family"] = output["family"].astype(str)
    output["candidate"] = output["candidate"].astype(str)
    output["selector_variant"] = output["selector_variant"].astype(str)
    output["month"] = output["month"].astype(str).str.slice(0, 7)
    output["direction"] = output["direction"].astype(str).str.lower()
    output["adjusted_pnl"] = numeric_series(output, "adjusted_pnl")
    output["entry_blocked"] = bool_series(output, "entry_blocked")
    for column in ["entry_decision_timestamp", "entry_timestamp", "exit_timestamp"]:
        if column in output.columns:
            output[column] = pd.to_datetime(output[column], utc=True, errors="coerce")
    return output.sort_values(GROUP_COLUMNS + ["entry_decision_timestamp"]).reset_index(drop=True)


def warmup_variant(selector_variant: str, rule: str) -> str:
    return f"{selector_variant}__monthwarmup_{rule}"


def safe_max_drawdown_from_trades(trades: pd.DataFrame) -> float:
    if trades.empty:
        return 0.0
    if "exit_timestamp" in trades.columns:
        return max_drawdown_from_trades(trades)
    equity = trades["adjusted_pnl"].cumsum()
    peak = equity.cummax()
    drawdown = peak - equity
    return float(drawdown.max()) if len(drawdown) else 0.0


def apply_month_warmup_rule(group: pd.DataFrame, rule: str) -> pd.DataFrame:
    rule = rule.strip()
    frame = group.sort_values("entry_decision_timestamp").copy()
    eligible = ~frame["entry_blocked"].fillna(False).astype(bool)
    direction = frame["direction"].astype(str).str.lower()
    prior_signal_count = eligible.cumsum() - eligible.astype(int)
    prior_long_count = (eligible & direction.eq("long")).cumsum() - (
        eligible & direction.eq("long")
    ).astype(int)
    prior_short_count = (eligible & direction.eq("short")).cumsum() - (
        eligible & direction.eq("short")
    ).astype(int)

    if rule == "none":
        warmup_blocked = pd.Series(False, index=frame.index, dtype=bool)
    elif rule.startswith("skip_first_") and rule.endswith("_wait_opposite_seen"):
        count_part = rule.removeprefix("skip_first_").removesuffix("_wait_opposite_seen")
        skip_count = int(count_part)
        lacks_opposite = (direction.eq("long") & prior_short_count.eq(0)) | (
            direction.eq("short") & prior_long_count.eq(0)
        )
        warmup_blocked = eligible & (prior_signal_count.lt(skip_count) | lacks_opposite)
    elif rule.startswith("skip_first_"):
        skip_count = int(rule.removeprefix("skip_first_"))
        warmup_blocked = eligible & prior_signal_count.lt(skip_count)
    elif rule == "wait_opposite_seen":
        warmup_blocked = eligible & (
            (direction.eq("long") & prior_short_count.eq(0))
            | (direction.eq("short") & prior_long_count.eq(0))
        )
    elif rule == "wait_both_sides_seen":
        warmup_blocked = eligible & (prior_long_count.eq(0) | prior_short_count.eq(0))
    else:
        raise ValueError(f"unknown month warmup rule: {rule}")

    frame["month_signal_index"] = prior_signal_count.where(eligible, np.nan)
    frame["prior_month_long_signal_count"] = prior_long_count
    frame["prior_month_short_signal_count"] = prior_short_count
    frame["month_warmup_rule"] = rule
    frame["month_warmup_blocked"] = warmup_blocked.astype(bool)
    frame["final_blocked"] = frame["entry_blocked"].astype(bool) | frame["month_warmup_blocked"]
    frame["input_selector_variant"] = frame["selector_variant"]
    frame["variant"] = frame["selector_variant"].map(lambda value: warmup_variant(value, rule))
    return frame


def summarize_month_warmup(trades: pd.DataFrame, rules: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    annotated_frames: list[pd.DataFrame] = []
    monthly_rows: list[dict[str, Any]] = []
    for rule in rules:
        annotated = pd.concat(
            [
                apply_month_warmup_rule(group, rule)
                for _, group in trades.groupby(GROUP_COLUMNS, dropna=False, sort=False)
            ],
            ignore_index=True,
        )
        annotated_frames.append(annotated)
        for key, group in annotated.groupby(GROUP_COLUMNS + ["variant", "month_warmup_rule"], dropna=False):
            key_columns = GROUP_COLUMNS + ["variant", "month_warmup_rule"]
            key_row = dict(zip(key_columns, key, strict=True))
            input_available = group[~group["entry_blocked"].astype(bool)]
            kept = group[~group["final_blocked"].astype(bool)]
            warmup_blocked = group[group["month_warmup_blocked"].astype(bool)]
            long_count = int(kept["direction"].eq("long").sum()) if len(kept) else 0
            short_count = int(kept["direction"].eq("short").sum()) if len(kept) else 0
            trade_count = int(len(kept))
            monthly_rows.append(
                {
                    "source": key_row["source"],
                    "role": key_row["role"],
                    "family": key_row["family"],
                    "variant": key_row["variant"],
                    "candidate": key_row["candidate"],
                    "month": key_row["month"],
                    "month_warmup_rule": key_row["month_warmup_rule"],
                    "input_selector_variant": key_row["selector_variant"],
                    "total_adjusted_pnl": float(kept["adjusted_pnl"].sum())
                    if trade_count
                    else 0.0,
                    "trade_count": trade_count,
                    "input_available_trade_count": int(len(input_available)),
                    "warmup_blocked_trade_count": int(len(warmup_blocked)),
                    "warmup_blocked_adjusted_pnl": float(warmup_blocked["adjusted_pnl"].sum())
                    if len(warmup_blocked)
                    else 0.0,
                    "input_total_adjusted_pnl": float(input_available["adjusted_pnl"].sum())
                    if len(input_available)
                    else 0.0,
                    "pnl_delta_vs_input": float(
                        (kept["adjusted_pnl"].sum() if trade_count else 0.0)
                        - (input_available["adjusted_pnl"].sum() if len(input_available) else 0.0)
                    ),
                    "long_trade_count": long_count,
                    "short_trade_count": short_count,
                    "max_side_trade_share": float(max(long_count, short_count) / trade_count)
                    if trade_count
                    else 0.0,
                    "max_drawdown": safe_max_drawdown_from_trades(kept),
                }
            )
    annotated_trades = pd.concat(annotated_frames, ignore_index=True)
    monthly = pd.DataFrame(monthly_rows)
    if monthly.empty:
        return annotated_trades, monthly
    monthly = monthly.sort_values(["month_warmup_rule", "variant", "candidate", "role", "month"])
    return annotated_trades.reset_index(drop=True), monthly.reset_index(drop=True)


def summarize_selection(monthly: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    if monthly.empty:
        return pd.DataFrame()
    for key, group in monthly.groupby(["variant", "candidate", "month_warmup_rule"], dropna=False):
        variant, candidate, rule = key
        role_group = group.groupby("role", dropna=False).agg(
            role_total_pnl=("total_adjusted_pnl", "sum"),
            role_trade_count=("trade_count", "sum"),
        )
        rows.append(
            {
                "variant": variant,
                "candidate": candidate,
                "month_warmup_rule": rule,
                "total_adjusted_pnl_sum": float(group["total_adjusted_pnl"].sum()),
                "input_total_adjusted_pnl_sum": float(group["input_total_adjusted_pnl"].sum()),
                "pnl_delta_vs_input_sum": float(group["pnl_delta_vs_input"].sum()),
                "trade_count_sum": int(group["trade_count"].sum()),
                "warmup_blocked_trade_count_sum": int(
                    group["warmup_blocked_trade_count"].sum()
                ),
                "warmup_blocked_adjusted_pnl_sum": float(
                    group["warmup_blocked_adjusted_pnl"].sum()
                ),
                "month_pnl_min": float(group["total_adjusted_pnl"].min()),
                "role_total_pnl_min": float(role_group["role_total_pnl"].min())
                if len(role_group)
                else 0.0,
                "positive_role_count": int((role_group["role_total_pnl"] > 0).sum())
                if len(role_group)
                else 0,
                "role_count": int(len(role_group)),
                "max_side_trade_share": float(group["max_side_trade_share"].max()),
                "max_drawdown_max": float(group["max_drawdown"].max()),
            }
        )
    return pd.DataFrame(rows).sort_values(
        ["month_pnl_min", "total_adjusted_pnl_sum"],
        ascending=[False, False],
    )


def run_overlay(args: argparse.Namespace) -> Path:
    trades = read_overlay_trades(args.overlay_trades)
    trades = filter_values(trades, "selector_variant", parse_csv(args.selector_variants))
    trades = filter_values(trades, "candidate", parse_csv(args.candidates))
    if trades.empty:
        raise ValueError("no trades left after filters")
    rules = parse_csv(args.warmup_rules)
    run_dir = make_run_dir(args.output_dir, args.label)
    annotated_trades, monthly = summarize_month_warmup(trades, rules)
    selection = summarize_selection(monthly)

    annotated_trades.to_csv(run_dir / "month_warmup_overlay_trades.csv", index=False)
    monthly.to_csv(run_dir / "month_warmup_overlay_monthly_metrics.csv", index=False)
    monthly.to_csv(run_dir / "month_warmup_overlay_selector_monthly_metrics.csv", index=False)
    selection.to_csv(run_dir / "month_warmup_overlay_selection_summary.csv", index=False)
    (run_dir / "config.json").write_text(
        json.dumps(
            {
                "overlay_trades": args.overlay_trades,
                "warmup_rules": rules,
                "selector_variants": parse_csv(args.selector_variants),
                "candidates": parse_csv(args.candidates),
            },
            indent=2,
            default=local_json_default,
        ),
        encoding="utf-8",
    )

    print("Month warmup overlay selection summary:")
    if selection.empty:
        print("<empty>")
    else:
        print(
            selection[
                [
                    "month_warmup_rule",
                    "total_adjusted_pnl_sum",
                    "pnl_delta_vs_input_sum",
                    "month_pnl_min",
                    "role_total_pnl_min",
                    "trade_count_sum",
                    "warmup_blocked_trade_count_sum",
                    "warmup_blocked_adjusted_pnl_sum",
                    "max_side_trade_share",
                ]
            ]
            .head(args.print_top)
            .to_string(index=False)
        )
    print(f"artifacts: {run_dir}")
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--overlay-trades", type=Path, required=True)
    parser.add_argument("--warmup-rules", default=DEFAULT_WARMUP_RULES)
    parser.add_argument("--selector-variants", default="")
    parser.add_argument("--candidates", default="")
    parser.add_argument("--output-dir", type=Path, default=Path("data/reports/backtests"))
    parser.add_argument("--label", default="entry_ev_month_warmup_overlay")
    parser.add_argument("--print-top", type=int, default=20)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    run_overlay(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
