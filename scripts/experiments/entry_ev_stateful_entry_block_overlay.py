#!/usr/bin/env python3
"""Apply observable entry-block rules to an existing stateful trade path."""

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

from entry_ev_hold_extension_stateful_replay import (  # noqa: E402
    DEFAULT_GROUP_COLUMNS,
    max_drawdown_from_trades,
)


DEFAULT_BLOCK_RULES = (
    "none,"
    "short_rollover_lossprob_ge0p4,"
    "short_rollover_sidegap_neg,"
    "short_rollover_sidegap_neg_lossprob_ge0p4,"
    "short_down_high_vol_rollover,"
    "short_down_high_vol_rollover_lossprob_ge0p4,"
    "short_rollover_entry_rank_lt0p5,"
    "short_entry_hour_23_lossprob_ge0p4,"
    "short_london_midloss_sidegap_pos,"
    "holdext_long_range_normal_ny,"
    "short_london_midloss_or_holdext_range_ny,"
    "short_rollover_or_london_midloss_or_holdext_range_ny"
)
DEFAULT_GROUP_EXTRA_COLUMNS = ["apply_universe", "threshold", "horizon_mode"]
OPTIONAL_GROUP_EXTRA_COLUMNS = ["extension_veto_rule"]
FEATURE_COLUMNS = [
    "trend_regime",
    "volatility_regime",
    "combined_regime",
    "session_regime",
    "gap_regime",
    "entry_hour",
    "selected_loss_first_prob",
    "pred_side_confidence_gap",
    "pred_taken_entry_local_rank",
    "pred_taken_ev",
    "pred_opposite_ev",
    "selected_fixed_60m_pred_pnl",
    "selected_fixed_240m_pred_pnl",
    "selected_fixed_720m_pred_pnl",
    "selected_fixed_60m_actual_pnl",
    "selected_fixed_240m_actual_pnl",
    "selected_fixed_720m_actual_pnl",
    "exit_capture_ratio",
]
REQUIRED_STATEFUL_COLUMNS = {
    *DEFAULT_GROUP_COLUMNS,
    *DEFAULT_GROUP_EXTRA_COLUMNS,
    "direction",
    "entry_timestamp",
    "entry_decision_timestamp",
    "adjusted_pnl",
}


def group_extra_columns(frame: pd.DataFrame) -> list[str]:
    return DEFAULT_GROUP_EXTRA_COLUMNS + [
        column for column in OPTIONAL_GROUP_EXTRA_COLUMNS if column in frame.columns
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
    return [part.strip() for part in value.split(",") if part.strip()]


def numeric_series(frame: pd.DataFrame, column: str, default: float = np.nan) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=float)
    values = pd.to_numeric(frame[column], errors="coerce")
    return values.replace([np.inf, -np.inf], np.nan).fillna(default).astype(float)


def string_series(frame: pd.DataFrame, column: str, default: str = "") -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=str)
    return frame[column].fillna(default).astype(str)


def read_stateful_trades(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    missing = sorted(REQUIRED_STATEFUL_COLUMNS - set(frame.columns))
    if missing:
        raise ValueError(f"{path} missing columns: {', '.join(missing)}")
    output = frame.copy()
    for column in ["entry_timestamp", "entry_decision_timestamp", "exit_timestamp"]:
        if column in output.columns:
            output[column] = pd.to_datetime(output[column], utc=True, errors="coerce")
    extras = group_extra_columns(output)
    for column in DEFAULT_GROUP_COLUMNS + extras + ["direction"]:
        output[column] = output[column].astype(str)
    output["month"] = output["month"].astype(str).str.slice(0, 7)
    output["threshold"] = numeric_series(output, "threshold", default=0.0)
    output["adjusted_pnl"] = numeric_series(output, "adjusted_pnl", default=0.0)
    return output.sort_values(
        DEFAULT_GROUP_COLUMNS + extras + ["entry_decision_timestamp"]
    ).reset_index(drop=True)


def read_feature_trades(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    keys = DEFAULT_GROUP_COLUMNS + ["direction", "entry_timestamp"]
    missing = sorted(set(keys) - set(frame.columns))
    if missing:
        raise ValueError(f"{path} missing columns: {', '.join(missing)}")
    output = frame.copy()
    output["entry_timestamp"] = pd.to_datetime(
        output["entry_timestamp"],
        utc=True,
        errors="coerce",
    )
    for column in DEFAULT_GROUP_COLUMNS + ["direction"]:
        output[column] = output[column].astype(str)
    output["month"] = output["month"].astype(str).str.slice(0, 7)
    keep_columns = keys + [column for column in FEATURE_COLUMNS if column in output.columns]
    return output[keep_columns].drop_duplicates(keys, keep="last")


def attach_features(stateful: pd.DataFrame, features: pd.DataFrame) -> pd.DataFrame:
    keys = DEFAULT_GROUP_COLUMNS + ["direction", "entry_timestamp"]
    return stateful.merge(features, on=keys, how="left", validate="many_to_one")


def entry_block_mask(frame: pd.DataFrame, rule: str) -> pd.Series:
    rule = rule.strip()
    if rule == "none":
        return pd.Series(False, index=frame.index, dtype=bool)
    short = frame["direction"].astype(str).eq("short")
    long = frame["direction"].astype(str).eq("long")
    rollover = string_series(frame, "session_regime").eq("rollover")
    high_vol = string_series(frame, "volatility_regime").eq("high_vol")
    down_high_vol = string_series(frame, "combined_regime").eq("down_high_vol")
    loss_first = numeric_series(frame, "selected_loss_first_prob", default=-np.inf)
    side_gap = numeric_series(frame, "pred_side_confidence_gap", default=np.inf)
    entry_rank = numeric_series(frame, "pred_taken_entry_local_rank", default=np.inf)
    entry_hour = numeric_series(frame, "entry_hour", default=-1.0)
    holding_minutes = numeric_series(frame, "holding_minutes", default=np.inf)
    hold_extension_applied = frame.get("hold_extension_applied", False)
    if not isinstance(hold_extension_applied, pd.Series):
        hold_extension_applied = pd.Series(False, index=frame.index, dtype=bool)
    hold_extension_applied = hold_extension_applied.fillna(False).astype(bool)

    if rule == "short_rollover":
        return short & rollover
    if rule == "short_rollover_highvol":
        return short & rollover & high_vol
    if rule == "short_rollover_lossprob_ge0p4":
        return short & rollover & loss_first.ge(0.4)
    if rule == "short_rollover_sidegap_neg":
        return short & rollover & side_gap.lt(0.0)
    if rule == "short_rollover_sidegap_neg_lossprob_ge0p4":
        return short & rollover & side_gap.lt(0.0) & loss_first.ge(0.4)
    if rule == "short_down_high_vol_rollover":
        return short & rollover & down_high_vol
    if rule == "short_down_high_vol_rollover_lossprob_ge0p4":
        return short & rollover & down_high_vol & loss_first.ge(0.4)
    if rule == "short_rollover_entry_rank_lt0p5":
        return short & rollover & entry_rank.lt(0.5)
    if rule == "short_entry_hour_23_lossprob_ge0p4":
        return short & entry_hour.eq(23.0) & loss_first.ge(0.4)
    if rule == "short_london_midloss_sidegap_pos":
        return (
            short
            & string_series(frame, "session_regime").eq("london")
            & loss_first.between(0.3, 0.45)
            & side_gap.gt(0.0)
        )
    if rule == "holdext_long_range_normal_ny":
        return (
            hold_extension_applied
            & long
            & string_series(frame, "combined_regime").eq("range_normal_vol")
            & string_series(frame, "session_regime").eq("ny_overlap")
            & holding_minutes.ge(720.0)
        )
    if rule == "short_london_midloss_or_holdext_range_ny":
        return entry_block_mask(frame, "short_london_midloss_sidegap_pos") | entry_block_mask(
            frame,
            "holdext_long_range_normal_ny",
        )
    if rule == "short_rollover_or_london_midloss_or_holdext_range_ny":
        return (
            entry_block_mask(frame, "short_rollover_lossprob_ge0p4")
            | entry_block_mask(frame, "short_london_midloss_sidegap_pos")
            | entry_block_mask(frame, "holdext_long_range_normal_ny")
        )
    raise ValueError(f"unknown entry block rule: {rule}")


def threshold_label(value: float) -> str:
    return f"{float(value):g}".replace(".", "p")


def overlay_variant(row: pd.Series, rule: str) -> str:
    variant = (
        str(row["variant"])
        + "__holdext_"
        + str(row["apply_universe"])
        + "_t"
        + threshold_label(float(row["threshold"]))
        + "_h"
        + str(row["horizon_mode"])
    )
    extension_veto_rule = str(row.get("extension_veto_rule", "none"))
    if extension_veto_rule != "none":
        variant += "__veto_" + extension_veto_rule
    return variant + "__entryblock_" + rule


def summarize_overlay(annotated: pd.DataFrame, rules: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    monthly_rows: list[dict[str, Any]] = []
    annotated_frames: list[pd.DataFrame] = []
    group_columns = DEFAULT_GROUP_COLUMNS + group_extra_columns(annotated)
    for rule in rules:
        frame = annotated.copy()
        frame["entry_block_rule"] = rule
        frame["entry_blocked"] = entry_block_mask(frame, rule)
        frame["selector_variant"] = frame.apply(lambda row: overlay_variant(row, rule), axis=1)
        annotated_frames.append(frame)
        for key, group in frame.groupby(group_columns, dropna=False, sort=False):
            key_row = dict(zip(group_columns, key, strict=True))
            kept = group[~group["entry_blocked"]].copy()
            blocked = group[group["entry_blocked"]].copy()
            long_count = int(kept["direction"].astype(str).eq("long").sum()) if len(kept) else 0
            short_count = int(kept["direction"].astype(str).eq("short").sum()) if len(kept) else 0
            trade_count = int(len(kept))
            row = {
                **key_row,
                "variant": overlay_variant(group.iloc[0], rule),
                "candidate": str(group["candidate"].iloc[0]),
                "entry_block_rule": rule,
                "total_adjusted_pnl": float(kept["adjusted_pnl"].sum()) if trade_count else 0.0,
                "trade_count": trade_count,
                "blocked_trade_count": int(len(blocked)),
                "blocked_adjusted_pnl": float(blocked["adjusted_pnl"].sum())
                if len(blocked)
                else 0.0,
                "input_total_adjusted_pnl": float(group["adjusted_pnl"].sum()),
                "pnl_delta_vs_input": float(
                    (kept["adjusted_pnl"].sum() if trade_count else 0.0)
                    - group["adjusted_pnl"].sum()
                ),
                "long_trade_count": long_count,
                "short_trade_count": short_count,
                "max_side_trade_share": float(max(long_count, short_count) / trade_count)
                if trade_count
                else 0.0,
                "max_drawdown": max_drawdown_from_trades(kept),
            }
            monthly_rows.append(row)
    annotated_trades = pd.concat(annotated_frames, ignore_index=True)
    monthly = pd.DataFrame(monthly_rows)
    if monthly.empty:
        return annotated_trades, monthly
    return annotated_trades, monthly.sort_values(
        ["entry_block_rule", "variant", "candidate", "role", "month"]
    ).reset_index(drop=True)


def summarize_selection(monthly: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    if monthly.empty:
        return pd.DataFrame()
    for key, group in monthly.groupby(["variant", "candidate", "entry_block_rule"], dropna=False):
        variant, candidate, rule = key
        role_group = group.groupby("role", dropna=False).agg(
            role_total_pnl=("total_adjusted_pnl", "sum"),
            role_trade_count=("trade_count", "sum"),
        )
        rows.append(
            {
                "variant": variant,
                "candidate": candidate,
                "entry_block_rule": rule,
                "total_adjusted_pnl_sum": float(group["total_adjusted_pnl"].sum()),
                "input_total_adjusted_pnl_sum": float(group["input_total_adjusted_pnl"].sum()),
                "pnl_delta_vs_input_sum": float(group["pnl_delta_vs_input"].sum()),
                "trade_count_sum": int(group["trade_count"].sum()),
                "blocked_trade_count_sum": int(group["blocked_trade_count"].sum()),
                "blocked_adjusted_pnl_sum": float(group["blocked_adjusted_pnl"].sum()),
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
    stateful = read_stateful_trades(args.stateful_trades)
    features = read_feature_trades(args.feature_trades)
    annotated = attach_features(stateful, features)
    rules = parse_csv(args.block_rules)
    run_dir = make_run_dir(args.output_dir, args.label)
    annotated_trades, monthly = summarize_overlay(annotated, rules)
    selection = summarize_selection(monthly)

    annotated_trades.to_csv(run_dir / "entry_block_overlay_trades.csv", index=False)
    monthly.to_csv(run_dir / "entry_block_overlay_monthly_metrics.csv", index=False)
    selection.to_csv(run_dir / "entry_block_overlay_selection_summary.csv", index=False)
    monthly.to_csv(run_dir / "entry_block_overlay_selector_monthly_metrics.csv", index=False)
    (run_dir / "config.json").write_text(
        json.dumps(
            {
                "stateful_trades": args.stateful_trades,
                "feature_trades": args.feature_trades,
                "block_rules": rules,
            },
            indent=2,
            default=local_json_default,
        ),
        encoding="utf-8",
    )

    print("Entry block overlay selection summary:")
    print(
        selection[
            [
                "entry_block_rule",
                "total_adjusted_pnl_sum",
                "pnl_delta_vs_input_sum",
                "month_pnl_min",
                "role_total_pnl_min",
                "trade_count_sum",
                "blocked_trade_count_sum",
                "blocked_adjusted_pnl_sum",
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
    parser.add_argument("--stateful-trades", type=Path, required=True)
    parser.add_argument("--feature-trades", type=Path, required=True)
    parser.add_argument("--block-rules", default=DEFAULT_BLOCK_RULES)
    parser.add_argument("--output-dir", type=Path, default=Path("data/reports/backtests"))
    parser.add_argument("--label", default="entry_ev_stateful_entry_block_overlay")
    parser.add_argument("--print-top", type=int, default=20)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    run_overlay(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
