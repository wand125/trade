#!/usr/bin/env python3
"""Replay horizon-viability near-miss additions against support repair targets."""

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

from entry_ev_admission_repair_target_diagnostics import (  # noqa: E402
    minimal_side_balanced_additions,
)
from entry_ev_hold_extension_stateful_replay import max_drawdown_from_trades  # noqa: E402
from entry_ev_near_miss_exit_head import parse_csv  # noqa: E402


SCENARIO_COLUMNS = [
    "row_scope",
    "prob_threshold",
    "ev_threshold",
    "tail_prob_threshold",
    "require_model_used",
]
BASE_MONTHLY_COLUMNS = {
    "role",
    "month",
    "total_adjusted_pnl",
    "trade_count",
    "long_trade_count",
    "short_trade_count",
}
BASE_TRADE_COLUMNS = {
    "role",
    "family",
    "month",
    "direction",
    "entry_timestamp",
    "exit_timestamp",
    "adjusted_pnl",
}
CHOICE_COLUMNS = {
    "role",
    "family",
    "month",
    "decision_timestamp",
    "side",
    "needed_side",
    "extra_side_needed",
    "hv_chosen_horizon_minutes",
    "hv_chosen_score",
    "actual_pnl_at_hv_chosen_horizon",
    *SCENARIO_COLUMNS,
}


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


def numeric_series(frame: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=float)
    return (
        pd.to_numeric(frame[column], errors="coerce")
        .replace([np.inf, -np.inf], np.nan)
        .fillna(default)
        .astype(float)
    )


def bool_series(frame: pd.DataFrame, column: str, default: bool = False) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=bool)
    values = frame[column]
    if values.dtype == bool:
        return values.fillna(default).astype(bool)
    lowered = values.fillna(str(default)).astype(str).str.lower()
    return lowered.isin({"true", "1", "yes", "y"})


def threshold_label(value: float) -> str:
    return f"{float(value):g}".replace(".", "p").replace("-", "m")


def scenario_label(row: pd.Series) -> str:
    require = "reqmodel" if bool(row["require_model_used"]) else "allowfallback"
    return (
        f"{row['row_scope']}_p{threshold_label(row['prob_threshold'])}"
        f"_ev{threshold_label(row['ev_threshold'])}"
        f"_tail{threshold_label(row['tail_prob_threshold'])}_{require}"
    )


def apply_branch_filters(
    frame: pd.DataFrame,
    *,
    candidate: str,
    variant_contains: str,
    entry_block_rule: str,
) -> pd.DataFrame:
    output = frame.copy()
    if candidate:
        output = output[output["candidate"].astype(str).eq(candidate)]
    if variant_contains:
        variant_column = "selector_variant" if "selector_variant" in output.columns else "variant"
        output = output[
            output[variant_column].astype(str).str.contains(variant_contains, regex=False)
        ]
    if entry_block_rule:
        output = output[output["entry_block_rule"].astype(str).eq(entry_block_rule)]
    if output.empty:
        raise ValueError("branch filters removed all rows")
    return output.reset_index(drop=True)


def read_base_monthly(
    path: Path,
    *,
    candidate: str,
    variant_contains: str,
    entry_block_rule: str,
) -> pd.DataFrame:
    frame = pd.read_csv(path)
    missing = sorted(BASE_MONTHLY_COLUMNS - set(frame.columns))
    if missing:
        raise ValueError(f"{path} missing columns: {', '.join(missing)}")
    output = apply_branch_filters(
        frame,
        candidate=candidate,
        variant_contains=variant_contains,
        entry_block_rule=entry_block_rule,
    )
    output["role"] = output["role"].astype(str)
    if "family" not in output.columns:
        output["family"] = ""
    output["family"] = output["family"].astype(str)
    output["month"] = output["month"].astype(str).str.slice(0, 7)
    output["total_adjusted_pnl"] = numeric_series(output, "total_adjusted_pnl")
    output["trade_count"] = numeric_series(output, "trade_count")
    output["long_trade_count"] = numeric_series(output, "long_trade_count")
    output["short_trade_count"] = numeric_series(output, "short_trade_count")
    output["max_drawdown"] = numeric_series(output, "max_drawdown")
    return output


def read_base_trades(
    path: Path,
    *,
    candidate: str,
    variant_contains: str,
    entry_block_rule: str,
) -> pd.DataFrame:
    frame = pd.read_csv(path)
    missing = sorted(BASE_TRADE_COLUMNS - set(frame.columns))
    if missing:
        raise ValueError(f"{path} missing columns: {', '.join(missing)}")
    output = apply_branch_filters(
        frame,
        candidate=candidate,
        variant_contains=variant_contains,
        entry_block_rule=entry_block_rule,
    )
    if "entry_blocked" in output.columns:
        output = output[~bool_series(output, "entry_blocked")].copy()
    output["role"] = output["role"].astype(str)
    output["family"] = output["family"].astype(str)
    output["month"] = output["month"].astype(str).str.slice(0, 7)
    output["direction"] = output["direction"].astype(str)
    output["entry_timestamp"] = pd.to_datetime(
        output["entry_timestamp"],
        utc=True,
        errors="coerce",
    )
    output["exit_timestamp"] = pd.to_datetime(
        output["exit_timestamp"],
        utc=True,
        errors="coerce",
    )
    output["adjusted_pnl"] = numeric_series(output, "adjusted_pnl")
    output = output.dropna(subset=["entry_timestamp", "exit_timestamp"])
    output["repair_source"] = "base"
    return output.reset_index(drop=True)


def read_choice_candidates(
    path: Path,
    *,
    row_scopes: list[str],
    target_only: bool,
) -> pd.DataFrame:
    frame = pd.read_csv(path)
    missing = sorted(CHOICE_COLUMNS - set(frame.columns))
    if missing:
        raise ValueError(f"{path} missing columns: {', '.join(missing)}")
    output = frame.copy()
    output["role"] = output["role"].astype(str)
    output["family"] = output["family"].astype(str)
    output["month"] = output["month"].astype(str).str.slice(0, 7)
    output["side"] = output["side"].astype(str)
    output["needed_side"] = output["needed_side"].astype(str)
    output["row_scope"] = output["row_scope"].astype(str)
    if row_scopes:
        output = output[output["row_scope"].isin(row_scopes)].copy()
    output["decision_timestamp"] = pd.to_datetime(
        output["decision_timestamp"],
        utc=True,
        errors="coerce",
    )
    output["hv_chosen_horizon_minutes"] = numeric_series(
        output,
        "hv_chosen_horizon_minutes",
    )
    output["hv_chosen_score"] = numeric_series(output, "hv_chosen_score", default=-np.inf)
    output["actual_pnl_at_hv_chosen_horizon"] = numeric_series(
        output,
        "actual_pnl_at_hv_chosen_horizon",
    )
    output["extra_side_needed"] = numeric_series(output, "extra_side_needed")
    for column in ["prob_threshold", "ev_threshold", "tail_prob_threshold"]:
        output[column] = numeric_series(output, column)
    output["require_model_used"] = bool_series(output, "require_model_used")
    output = output[
        output["decision_timestamp"].notna()
        & output["hv_chosen_horizon_minutes"].gt(0.0)
    ].copy()
    if target_only:
        output = output[
            output["side"].eq(output["needed_side"]) & output["extra_side_needed"].gt(0.0)
        ].copy()
    output["entry_timestamp"] = output["decision_timestamp"]
    output["exit_timestamp"] = output["decision_timestamp"] + pd.to_timedelta(
        output["hv_chosen_horizon_minutes"],
        unit="m",
    )
    output["direction"] = output["side"]
    output["adjusted_pnl"] = output["actual_pnl_at_hv_chosen_horizon"]
    return output.reset_index(drop=True)


def intervals_overlap(
    start: pd.Timestamp,
    end: pd.Timestamp,
    intervals: list[tuple[pd.Timestamp, pd.Timestamp]],
) -> bool:
    return any(start < other_end and end > other_start for other_start, other_end in intervals)


def select_support_additions(
    base_trades: pd.DataFrame,
    choices: pd.DataFrame,
    *,
    cap_to_extra_side_needed: bool = True,
    overlap_key_columns: list[str] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if overlap_key_columns is None:
        overlap_key_columns = ["role"]
    intervals: dict[tuple[Any, ...], list[tuple[pd.Timestamp, pd.Timestamp]]] = {}
    for _, row in base_trades.iterrows():
        key = tuple(row[column] for column in overlap_key_columns)
        intervals.setdefault(key, []).append((row["entry_timestamp"], row["exit_timestamp"]))

    quotas: dict[tuple[str, str, str], int] = {}
    if cap_to_extra_side_needed:
        quota_frame = (
            choices.groupby(["role", "month", "side"], dropna=False)["extra_side_needed"]
            .max()
            .reset_index()
        )
        for _, row in quota_frame.iterrows():
            quotas[(str(row["role"]), str(row["month"]), str(row["side"]))] = int(
                max(0, np.ceil(float(row["extra_side_needed"])))
            )

    quota_used: dict[tuple[str, str, str], int] = {}
    selected_rows: list[dict[str, Any]] = []
    rejected_rows: list[dict[str, Any]] = []
    sort_columns = [
        column
        for column in [
            "hv_chosen_score",
            "actual_pnl_at_hv_chosen_horizon",
            "decision_timestamp",
            "entry_timestamp",
        ]
        if column in choices.columns
    ]
    ascending = [
        False if column in {"hv_chosen_score", "actual_pnl_at_hv_chosen_horizon"} else True
        for column in sort_columns
    ]
    sorted_choices = choices.sort_values(
        sort_columns,
        ascending=ascending,
    )
    for _, row in sorted_choices.iterrows():
        quota_key = (str(row["role"]), str(row["month"]), str(row["side"]))
        if cap_to_extra_side_needed and quota_used.get(quota_key, 0) >= quotas.get(quota_key, 0):
            rejected = row.to_dict()
            rejected["reject_reason"] = "quota_full"
            rejected_rows.append(rejected)
            continue
        overlap_key = tuple(row[column] for column in overlap_key_columns)
        start = row["entry_timestamp"]
        end = row["exit_timestamp"]
        if intervals_overlap(start, end, intervals.get(overlap_key, [])):
            rejected = row.to_dict()
            rejected["reject_reason"] = "overlap"
            rejected_rows.append(rejected)
            continue
        accepted = row.to_dict()
        accepted["addition_rank"] = len(selected_rows) + 1
        selected_rows.append(accepted)
        quota_used[quota_key] = quota_used.get(quota_key, 0) + 1
        intervals.setdefault(overlap_key, []).append((start, end))

    selected = pd.DataFrame(selected_rows)
    rejected = pd.DataFrame(rejected_rows)
    return selected, rejected


def base_summary(monthly: pd.DataFrame) -> dict[str, Any]:
    role_pnl = monthly.groupby("role", dropna=False)["total_adjusted_pnl"].sum()
    role_trades = monthly.groupby("role", dropna=False)["trade_count"].sum()
    total_trades = int(monthly["trade_count"].sum())
    long_trades = int(monthly["long_trade_count"].sum())
    short_trades = int(monthly["short_trade_count"].sum())
    overall_side_share = max(long_trades, short_trades) / total_trades if total_trades else 0.0
    return {
        "base_total_pnl": float(monthly["total_adjusted_pnl"].sum()),
        "base_month_pnl_min": float(monthly["total_adjusted_pnl"].min()),
        "base_role_total_pnl_min": float(role_pnl.min()) if len(role_pnl) else 0.0,
        "base_trade_count": total_trades,
        "base_role_trade_count_min": int(role_trades.min()) if len(role_trades) else 0,
        "base_month_trade_count_min": int(monthly["trade_count"].min()) if len(monthly) else 0,
        "base_observed_max_side_trade_share": float(
            max(overall_side_share, monthly["max_side_trade_share"].max())
        )
        if len(monthly)
        else 0.0,
    }


def update_monthly_metrics(
    base_monthly: pd.DataFrame,
    base_trades: pd.DataFrame,
    additions: pd.DataFrame,
    *,
    scenario: dict[str, Any],
) -> pd.DataFrame:
    monthly = base_monthly.copy()
    for column, value in scenario.items():
        monthly[column] = value
    if "max_side_trade_share" not in monthly.columns:
        monthly["max_side_trade_share"] = 0.0

    if not additions.empty:
        grouped = additions.groupby(["role", "family", "month", "side"], dropna=False).agg(
            added_pnl=("adjusted_pnl", "sum"),
            added_count=("adjusted_pnl", "size"),
        )
        for key, row in grouped.reset_index().iterrows():
            del key
            mask = monthly["role"].astype(str).eq(str(row["role"])) & monthly[
                "month"
            ].astype(str).eq(str(row["month"]))
            if not mask.any():
                new_row = {column: np.nan for column in monthly.columns}
                new_row.update(scenario)
                new_row.update(
                    {
                        "source": "support_repair",
                        "role": str(row["role"]),
                        "family": str(row["family"]),
                        "month": str(row["month"]),
                        "total_adjusted_pnl": 0.0,
                        "trade_count": 0.0,
                        "long_trade_count": 0.0,
                        "short_trade_count": 0.0,
                        "max_drawdown": 0.0,
                    }
                )
                monthly = pd.concat([monthly, pd.DataFrame([new_row])], ignore_index=True)
                mask = monthly["role"].astype(str).eq(str(row["role"])) & monthly[
                    "month"
                ].astype(str).eq(str(row["month"]))
            idx = monthly.index[mask][0]
            monthly.loc[idx, "total_adjusted_pnl"] = float(
                monthly.loc[idx, "total_adjusted_pnl"]
            ) + float(row["added_pnl"])
            monthly.loc[idx, "trade_count"] = float(monthly.loc[idx, "trade_count"]) + float(
                row["added_count"]
            )
            count_column = "long_trade_count" if str(row["side"]) == "long" else "short_trade_count"
            monthly.loc[idx, count_column] = float(monthly.loc[idx, count_column]) + float(
                row["added_count"]
            )

    trades = normalize_combined_trades(base_trades, additions)
    drawdowns = {}
    for key, group in trades.groupby(["role", "month"], dropna=False):
        drawdowns[key] = max_drawdown_from_trades(group)
    for idx, row in monthly.iterrows():
        long_count = float(row["long_trade_count"])
        short_count = float(row["short_trade_count"])
        trade_count = float(row["trade_count"])
        monthly.loc[idx, "max_side_trade_share"] = (
            max(long_count, short_count) / trade_count if trade_count else 0.0
        )
        monthly.loc[idx, "max_drawdown"] = float(
            drawdowns.get((str(row["role"]), str(row["month"])), 0.0)
        )
    return monthly.reset_index(drop=True)


def normalize_combined_trades(base_trades: pd.DataFrame, additions: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "role",
        "family",
        "month",
        "direction",
        "entry_timestamp",
        "exit_timestamp",
        "adjusted_pnl",
        "repair_source",
    ]
    base = base_trades.copy()
    base["repair_source"] = "base"
    frames = [base[columns]]
    if not additions.empty:
        add = additions.copy()
        add["repair_source"] = "support_repair"
        if "direction" not in add.columns and "side" in add.columns:
            add["direction"] = add["side"]
        frames.append(add[columns])
    return pd.concat(frames, ignore_index=True).sort_values(
        ["role", "entry_timestamp", "exit_timestamp"]
    )


def summarize_repair_targets(
    monthly: pd.DataFrame,
    *,
    month_floor: float,
    min_month_trades: int,
    max_side_trade_share: float,
    shallow_month_floor: float,
) -> tuple[dict[str, Any], pd.DataFrame]:
    rows: list[dict[str, Any]] = []
    for _, row in monthly.iterrows():
        long_count = int(float(row["long_trade_count"]))
        short_count = int(float(row["short_trade_count"]))
        addition = minimal_side_balanced_additions(
            long_count=long_count,
            short_count=short_count,
            min_trades=min_month_trades,
            max_side_trade_share=max_side_trade_share,
        )
        pnl = float(row["total_adjusted_pnl"])
        trade_count = int(float(row["trade_count"]))
        side_share = float(row["max_side_trade_share"])
        month_trade_shortfall = max(0, min_month_trades - trade_count)
        side_share_excess = max(0.0, side_share - max_side_trade_share)
        support_limited = bool(
            month_trade_shortfall > 0
            or side_share_excess > 0
            or addition["extra_trades_needed"] > 0
        )
        if pnl >= month_floor:
            floor_class = "pass"
        elif support_limited:
            floor_class = "support_limited"
        elif pnl >= shallow_month_floor:
            floor_class = "shallow"
        else:
            floor_class = "structural"
        rows.append(
            {
                **{
                    column: row[column]
                    for column in SCENARIO_COLUMNS
                    if column in row.index
                },
                "role": row["role"],
                "family": row.get("family", ""),
                "month": row["month"],
                "total_adjusted_pnl": pnl,
                "trade_count": trade_count,
                "long_trade_count": long_count,
                "short_trade_count": short_count,
                "month_pnl_hurdle": max(0.0, month_floor - pnl),
                "month_trade_shortfall": month_trade_shortfall,
                "side_share_excess": side_share_excess,
                **addition,
                "support_limited_month": support_limited,
                "support_limited_negative_month": bool(pnl < month_floor and support_limited),
                "floor_breach_class": floor_class,
            }
        )
    targets = pd.DataFrame(rows)
    if targets.empty:
        return {}, targets
    summary = {
        "remaining_month_pnl_hurdle_sum": float(targets["month_pnl_hurdle"].sum()),
        "remaining_extra_trades_needed": int(targets["extra_trades_needed"].sum()),
        "remaining_extra_long_needed": int(targets["extra_long_needed"].sum()),
        "remaining_extra_short_needed": int(targets["extra_short_needed"].sum()),
        "negative_month_count": int((targets["total_adjusted_pnl"] < month_floor).sum()),
        "support_limited_negative_month_count": int(
            targets["support_limited_negative_month"].sum()
        ),
        "shallow_negative_month_count": int(targets["floor_breach_class"].eq("shallow").sum()),
        "structural_negative_month_count": int(
            targets["floor_breach_class"].eq("structural").sum()
        ),
    }
    return summary, targets


def summarize_admission(
    monthly: pd.DataFrame,
    *,
    min_total_pnl: float,
    min_role_total_pnl: float,
    month_floor: float,
    min_role_trades: int,
    min_month_trades: int,
    max_side_trade_share: float,
) -> dict[str, Any]:
    role_totals = monthly.groupby("role", dropna=False)["total_adjusted_pnl"].sum()
    role_trades = monthly.groupby("role", dropna=False)["trade_count"].sum()
    total_pnl = float(monthly["total_adjusted_pnl"].sum())
    total_trades = int(monthly["trade_count"].sum())
    long_trades = int(monthly["long_trade_count"].sum())
    short_trades = int(monthly["short_trade_count"].sum())
    overall_side_share = max(long_trades, short_trades) / total_trades if total_trades else 0.0
    observed_side_share = float(max(overall_side_share, monthly["max_side_trade_share"].max()))
    blockers: list[str] = []
    if total_pnl < min_total_pnl:
        blockers.append("total_pnl_below_floor")
    if float(role_totals.min()) < min_role_total_pnl:
        blockers.append("role_total_pnl_below_floor")
    if float(monthly["total_adjusted_pnl"].min()) < month_floor:
        blockers.append("month_pnl_below_floor")
    if int(role_trades.min()) < min_role_trades:
        blockers.append("role_trades_low")
    if int(monthly["trade_count"].min()) < min_month_trades:
        blockers.append("month_trades_low")
    if observed_side_share > max_side_trade_share:
        blockers.append("side_share_high")
    return {
        "selector_pass": not blockers,
        "blockers": ",".join(blockers),
        "combined_total_pnl": total_pnl,
        "combined_trade_count": total_trades,
        "combined_long_trade_count": long_trades,
        "combined_short_trade_count": short_trades,
        "role_total_pnl_min": float(role_totals.min()),
        "month_pnl_min": float(monthly["total_adjusted_pnl"].min()),
        "role_trade_count_min": int(role_trades.min()),
        "month_trade_count_min": int(monthly["trade_count"].min()),
        "observed_max_side_trade_share": observed_side_share,
        "max_drawdown": float(monthly["max_drawdown"].max()),
    }


def replay_scenarios(
    base_monthly: pd.DataFrame,
    base_trades: pd.DataFrame,
    choices: pd.DataFrame,
    *,
    min_total_pnl: float,
    min_role_total_pnl: float,
    month_floor: float,
    shallow_month_floor: float,
    min_role_trades: int,
    min_month_trades: int,
    max_side_trade_share: float,
    cap_to_extra_side_needed: bool,
    overlap_key_columns: list[str],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    summary_rows: list[dict[str, Any]] = []
    monthly_frames: list[pd.DataFrame] = []
    addition_frames: list[pd.DataFrame] = []
    rejection_frames: list[pd.DataFrame] = []
    base_stats = base_summary(base_monthly)
    for key, group in choices.groupby(SCENARIO_COLUMNS, dropna=False, sort=False):
        scenario = dict(zip(SCENARIO_COLUMNS, key, strict=True))
        label = scenario_label(pd.Series(scenario))
        additions, rejections = select_support_additions(
            base_trades,
            group,
            cap_to_extra_side_needed=cap_to_extra_side_needed,
            overlap_key_columns=overlap_key_columns,
        )
        if not additions.empty:
            additions["scenario_label"] = label
            for column, value in scenario.items():
                additions[column] = value
            addition_frames.append(additions)
        if not rejections.empty:
            rejections["scenario_label"] = label
            for column, value in scenario.items():
                rejections[column] = value
            rejection_frames.append(rejections)
        monthly = update_monthly_metrics(
            base_monthly,
            base_trades,
            additions,
            scenario={**scenario, "scenario_label": label},
        )
        repair_summary, repair_targets = summarize_repair_targets(
            monthly,
            month_floor=month_floor,
            min_month_trades=min_month_trades,
            max_side_trade_share=max_side_trade_share,
            shallow_month_floor=shallow_month_floor,
        )
        del repair_targets
        admission = summarize_admission(
            monthly,
            min_total_pnl=min_total_pnl,
            min_role_total_pnl=min_role_total_pnl,
            month_floor=month_floor,
            min_role_trades=min_role_trades,
            min_month_trades=min_month_trades,
            max_side_trade_share=max_side_trade_share,
        )
        monthly["scenario_label"] = label
        monthly_frames.append(monthly)
        added_pnl = float(additions["adjusted_pnl"].sum()) if not additions.empty else 0.0
        summary_rows.append(
            {
                **scenario,
                "scenario_label": label,
                **base_stats,
                "candidate_rows": int(len(group)),
                "chosen_input_rows": int(group["hv_chosen_horizon_minutes"].gt(0).sum()),
                "added_count": int(len(additions)),
                "added_pnl": added_pnl,
                "rejected_overlap_count": int(
                    rejections["reject_reason"].eq("overlap").sum()
                )
                if not rejections.empty
                else 0,
                "rejected_quota_count": int(
                    rejections["reject_reason"].eq("quota_full").sum()
                )
                if not rejections.empty
                else 0,
                "delta_vs_base": float(admission["combined_total_pnl"] - base_stats["base_total_pnl"]),
                **admission,
                **repair_summary,
            }
        )
    summary = pd.DataFrame(summary_rows)
    if not summary.empty:
        summary = summary.sort_values(
            [
                "selector_pass",
                "remaining_extra_trades_needed",
                "month_pnl_min",
                "combined_total_pnl",
                "added_count",
            ],
            ascending=[False, True, False, False, True],
        ).reset_index(drop=True)
    monthly_all = pd.concat(monthly_frames, ignore_index=True) if monthly_frames else pd.DataFrame()
    additions_all = (
        pd.concat(addition_frames, ignore_index=True) if addition_frames else pd.DataFrame()
    )
    rejections_all = (
        pd.concat(rejection_frames, ignore_index=True) if rejection_frames else pd.DataFrame()
    )
    return summary, monthly_all, additions_all, rejections_all


def run_replay(args: argparse.Namespace) -> Path:
    row_scopes = parse_csv(args.row_scopes)
    overlap_keys = parse_csv(args.overlap_keys)
    base_monthly = read_base_monthly(
        args.base_monthly_metrics,
        candidate=args.candidate,
        variant_contains=args.variant_contains,
        entry_block_rule=args.base_entry_block_rule,
    )
    base_trades = read_base_trades(
        args.base_trades,
        candidate=args.candidate,
        variant_contains=args.variant_contains,
        entry_block_rule=args.base_entry_block_rule,
    )
    choices = read_choice_candidates(
        args.choices,
        row_scopes=row_scopes,
        target_only=args.target_only,
    )
    summary, monthly, additions, rejections = replay_scenarios(
        base_monthly,
        base_trades,
        choices,
        min_total_pnl=args.min_total_pnl,
        min_role_total_pnl=args.min_role_total_pnl,
        month_floor=args.month_floor,
        shallow_month_floor=args.shallow_month_floor,
        min_role_trades=args.min_role_trades,
        min_month_trades=args.min_month_trades,
        max_side_trade_share=args.max_side_trade_share,
        cap_to_extra_side_needed=args.cap_to_extra_side_needed,
        overlap_key_columns=overlap_keys,
    )
    run_dir = make_run_dir(args.output_dir, args.label)
    summary.to_csv(run_dir / "support_repair_horizon_replay_summary.csv", index=False)
    monthly.to_csv(run_dir / "support_repair_horizon_replay_monthly_metrics.csv", index=False)
    additions.to_csv(run_dir / "support_repair_horizon_replay_additions.csv", index=False)
    rejections.to_csv(run_dir / "support_repair_horizon_replay_rejections.csv", index=False)
    (run_dir / "config.json").write_text(
        json.dumps(
            {
                "base_monthly_metrics": args.base_monthly_metrics,
                "base_trades": args.base_trades,
                "choices": args.choices,
                "candidate": args.candidate,
                "variant_contains": args.variant_contains,
                "base_entry_block_rule": args.base_entry_block_rule,
                "row_scopes": row_scopes,
                "target_only": args.target_only,
                "cap_to_extra_side_needed": args.cap_to_extra_side_needed,
                "overlap_keys": overlap_keys,
                "min_total_pnl": args.min_total_pnl,
                "min_role_total_pnl": args.min_role_total_pnl,
                "month_floor": args.month_floor,
                "shallow_month_floor": args.shallow_month_floor,
                "min_role_trades": args.min_role_trades,
                "min_month_trades": args.min_month_trades,
                "max_side_trade_share": args.max_side_trade_share,
            },
            indent=2,
            default=local_json_default,
        ),
        encoding="utf-8",
    )

    print("Support repair horizon replay summary:")
    if summary.empty:
        print("empty summary")
    else:
        print(
            summary[
                [
                    "scenario_label",
                    "selector_pass",
                    "blockers",
                    "added_count",
                    "added_pnl",
                    "combined_total_pnl",
                    "delta_vs_base",
                    "month_pnl_min",
                    "role_total_pnl_min",
                    "remaining_extra_trades_needed",
                    "remaining_month_pnl_hurdle_sum",
                ]
            ]
            .head(args.print_top)
            .to_string(index=False)
        )
    print(f"artifacts: {run_dir}")
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-monthly-metrics", type=Path, required=True)
    parser.add_argument("--base-trades", type=Path, required=True)
    parser.add_argument("--choices", type=Path, required=True)
    parser.add_argument(
        "--candidate",
        default="q95_sg95_rank90_floor5_side_regime_session_month",
    )
    parser.add_argument(
        "--variant-contains",
        default="loss_exit30_cd15__holdext_isolated_large_loss_long_t-5_h720",
    )
    parser.add_argument("--base-entry-block-rule", default="long_range_normal_ny_fixed60_pred_gt0")
    parser.add_argument("--row-scopes", default="available_candidates,greedy_selected")
    parser.add_argument("--target-only", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument(
        "--cap-to-extra-side-needed",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    parser.add_argument("--overlap-keys", default="role")
    parser.add_argument("--min-total-pnl", type=float, default=0.0)
    parser.add_argument("--min-role-total-pnl", type=float, default=0.0)
    parser.add_argument("--month-floor", type=float, default=0.0)
    parser.add_argument("--shallow-month-floor", type=float, default=-1.0)
    parser.add_argument("--min-role-trades", type=int, default=4)
    parser.add_argument("--min-month-trades", type=int, default=1)
    parser.add_argument("--max-side-trade-share", type=float, default=0.95)
    parser.add_argument("--output-dir", type=Path, default=Path("data/reports/backtests"))
    parser.add_argument("--label", default="entry_ev_support_repair_horizon_replay")
    parser.add_argument("--print-top", type=int, default=20)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    run_replay(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
