#!/usr/bin/env python3
"""Find opposite-side candidate rows for thin admission-repair months."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from trade_data.backtest import json_default, make_run_dir  # noqa: E402

from entry_ev_forced_exit_selector_inputs import parse_family_predictions  # noqa: E402
from entry_ev_quantile_policy_backtest import policy_candidate_from_name  # noqa: E402
from entry_ev_stateful_entry_block_overlay import parse_csv  # noqa: E402


SIDE_LABELS = ("long", "short")
TARGET_REQUIRED_COLUMNS = {
    "role",
    "family",
    "month",
    "candidate",
    "variant",
    "entry_block_rule",
    "extra_long_needed",
    "extra_short_needed",
}
TRADE_REQUIRED_COLUMNS = {
    "role",
    "family",
    "month",
    "candidate",
    "selector_variant",
    "entry_block_rule",
    "entry_blocked",
    "entry_decision_timestamp",
    "exit_decision_timestamp",
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


def numeric_series(frame: pd.DataFrame, column: str, default: float = np.nan) -> pd.Series:
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


def month_series(frame: pd.DataFrame) -> pd.Series:
    if "dataset_month" in frame.columns:
        return frame["dataset_month"].astype(str).str.slice(0, 7)
    if "month" in frame.columns:
        return frame["month"].astype(str).str.slice(0, 7)
    if "decision_timestamp" in frame.columns:
        return pd.to_datetime(frame["decision_timestamp"], utc=True).dt.strftime("%Y-%m")
    raise ValueError("prediction frame needs dataset_month, month, or decision_timestamp")


def parquet_columns(path: Path) -> list[str]:
    return list(pq.ParquetFile(path).schema.names)


def read_repair_targets(
    path: Path,
    *,
    candidate: str,
    variant_contains: str,
    entry_block_rule: str,
) -> pd.DataFrame:
    frame = pd.read_csv(path)
    missing = sorted(TARGET_REQUIRED_COLUMNS - set(frame.columns))
    if missing:
        raise ValueError(f"{path} missing columns: {', '.join(missing)}")
    output = frame.copy()
    output["month"] = output["month"].astype(str).str.slice(0, 7)
    output = output[output["candidate"].astype(str).eq(candidate)]
    if variant_contains:
        output = output[output["variant"].astype(str).str.contains(variant_contains, regex=False)]
    if entry_block_rule:
        output = output[output["entry_block_rule"].astype(str).eq(entry_block_rule)]
    output["extra_long_needed"] = numeric_series(output, "extra_long_needed", default=0.0).astype(int)
    output["extra_short_needed"] = numeric_series(output, "extra_short_needed", default=0.0).astype(int)
    rows: list[dict[str, Any]] = []
    for _, row in output.iterrows():
        for side in SIDE_LABELS:
            extra = int(row[f"extra_{side}_needed"])
            if extra <= 0:
                continue
            row_out = row.to_dict()
            row_out["needed_side"] = side
            row_out["extra_side_needed"] = extra
            rows.append(row_out)
    if not rows:
        raise ValueError("no repair target rows with needed extra side trades")
    return pd.DataFrame(rows).reset_index(drop=True)


def read_current_trades(
    path: Path,
    *,
    candidate: str,
    selector_variant_contains: str,
    entry_block_rule: str,
) -> pd.DataFrame:
    frame = pd.read_csv(path)
    missing = sorted(TRADE_REQUIRED_COLUMNS - set(frame.columns))
    if missing:
        raise ValueError(f"{path} missing columns: {', '.join(missing)}")
    output = frame.copy()
    output["month"] = output["month"].astype(str).str.slice(0, 7)
    output = output[output["candidate"].astype(str).eq(candidate)]
    if selector_variant_contains:
        output = output[
            output["selector_variant"].astype(str).str.contains(
                selector_variant_contains,
                regex=False,
            )
        ]
    if entry_block_rule:
        output = output[output["entry_block_rule"].astype(str).eq(entry_block_rule)]
    output = output[~bool_series(output, "entry_blocked")]
    for column in ["entry_decision_timestamp", "exit_decision_timestamp", "exit_timestamp"]:
        if column in output.columns:
            output[column] = pd.to_datetime(output[column], utc=True, errors="coerce")
    if "exit_decision_timestamp" not in output.columns:
        output["exit_decision_timestamp"] = output["exit_timestamp"]
    output["exit_decision_timestamp"] = output["exit_decision_timestamp"].fillna(output["exit_timestamp"])
    return output.sort_values(["family", "role", "month", "entry_decision_timestamp"]).reset_index(drop=True)


def parse_side_penalty_rules(value: str) -> list[tuple[str, str, str, float]]:
    rules: list[tuple[str, str, str, float]] = []
    for part in parse_csv(value):
        fields = part.split(":")
        if len(fields) != 3 or "=" not in fields[1]:
            raise argparse.ArgumentTypeError(
                "side penalty rules must use side:column=value:penalty"
            )
        side = fields[0].strip().lower()
        column, expected = fields[1].split("=", 1)
        if side not in SIDE_LABELS:
            raise argparse.ArgumentTypeError(f"unknown penalty side: {side}")
        rules.append((side, column.strip(), expected.strip().lower(), float(fields[2])))
    return rules


def apply_side_penalties(
    frame: pd.DataFrame,
    *,
    long_column: str,
    short_column: str,
    rules: list[tuple[str, str, str, float]],
) -> pd.DataFrame:
    output = frame.copy()
    output["_long_score"] = numeric_series(output, long_column)
    output["_short_score"] = numeric_series(output, short_column)
    for side, column, expected, penalty in rules:
        if column not in output.columns:
            continue
        if expected in {"true", "1", "yes", "y"}:
            mask = bool_series(output, column)
        elif expected in {"false", "0", "no", "n"}:
            mask = ~bool_series(output, column)
        else:
            mask = output[column].fillna("").astype(str).str.lower().eq(expected)
        score_column = f"_{side}_score"
        output.loc[mask, score_column] = output.loc[mask, score_column] - float(penalty)
    return output


def add_side_specific_quantiles(rows: pd.DataFrame) -> pd.DataFrame:
    output = rows.copy()
    group_columns = ["month", "side", "combined_regime", "session_regime"]
    output["score_pct"] = output.groupby(group_columns, dropna=False)["side_score"].rank(pct=True)
    output["side_margin_pct"] = output.groupby(group_columns, dropna=False)["side_margin"].rank(pct=True)
    output["entry_rank_pct"] = output.groupby(group_columns, dropna=False)["side_entry_rank"].rank(pct=True)
    return output


def build_side_rows(
    predictions: pd.DataFrame,
    *,
    family: str,
    long_column: str,
    short_column: str,
    long_holding_column: str,
    short_holding_column: str,
    min_valid_predicted_hold_minutes: float,
    max_predicted_hold_minutes: float,
    side_penalty_rules: list[tuple[str, str, str, float]],
) -> pd.DataFrame:
    frame = predictions.copy()
    frame["family"] = family
    frame["month"] = month_series(frame)
    frame["decision_timestamp"] = pd.to_datetime(frame["decision_timestamp"], utc=True, errors="coerce")
    frame = apply_side_penalties(
        frame,
        long_column=long_column,
        short_column=short_column,
        rules=side_penalty_rules,
    )
    frame["_long_holding"] = numeric_series(frame, long_holding_column)
    frame["_short_holding"] = numeric_series(frame, short_holding_column)
    frames: list[pd.DataFrame] = []
    for side in SIDE_LABELS:
        opposite = "short" if side == "long" else "long"
        side_rows = pd.DataFrame(
            {
                "family": frame["family"],
                "month": frame["month"],
                "decision_timestamp": frame["decision_timestamp"],
                "side": side,
                "side_score": frame[f"_{side}_score"],
                "opposite_score": frame[f"_{opposite}_score"],
                "side_pred_holding_minutes": frame[f"_{side}_holding"],
                "side_entry_rank": numeric_series(frame, f"pred_{side}_entry_local_rank"),
                "side_best_adjusted_pnl": numeric_series(frame, f"{side}_best_adjusted_pnl"),
                "side_best_holding_minutes": numeric_series(frame, f"{side}_best_holding_minutes"),
                "side_fixed_60m_adjusted_pnl": numeric_series(frame, f"{side}_fixed_60m_adjusted_pnl"),
                "side_fixed_240m_adjusted_pnl": numeric_series(frame, f"{side}_fixed_240m_adjusted_pnl"),
                "side_fixed_720m_adjusted_pnl": numeric_series(frame, f"{side}_fixed_720m_adjusted_pnl"),
                "combined_regime": frame.get("combined_regime", "missing"),
                "session_regime": frame.get("session_regime", "missing"),
                "entry_hour": pd.to_datetime(frame["decision_timestamp"], utc=True, errors="coerce").dt.hour,
            }
        )
        side_rows["side_margin"] = side_rows["side_score"] - side_rows["opposite_score"]
        side_rows["holding_ok"] = (
            side_rows["side_pred_holding_minutes"].notna()
            & side_rows["side_pred_holding_minutes"].ge(min_valid_predicted_hold_minutes)
            & side_rows["side_pred_holding_minutes"].le(max_predicted_hold_minutes)
        )
        frames.append(side_rows)
    output = pd.concat(frames, ignore_index=True)
    output["combined_regime"] = output["combined_regime"].fillna("missing").astype(str)
    output["session_regime"] = output["session_regime"].fillna("missing").astype(str)
    output = add_side_specific_quantiles(output)
    return output


def interval_overlaps(start: pd.Timestamp, end: pd.Timestamp, intervals: list[tuple[pd.Timestamp, pd.Timestamp]]) -> bool:
    for interval_start, interval_end in intervals:
        if start < interval_end and end > interval_start:
            return True
    return False


def current_intervals(trades: pd.DataFrame, *, family: str, role: str, month: str) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    subset = trades[
        trades["family"].astype(str).eq(str(family))
        & trades["role"].astype(str).eq(str(role))
        & trades["month"].astype(str).eq(str(month))
    ].copy()
    intervals: list[tuple[pd.Timestamp, pd.Timestamp]] = []
    for _, row in subset.iterrows():
        start = pd.to_datetime(row["entry_decision_timestamp"], utc=True, errors="coerce")
        end = pd.to_datetime(row["exit_decision_timestamp"], utc=True, errors="coerce")
        if pd.isna(start) or pd.isna(end):
            continue
        if end <= start:
            end = start + pd.Timedelta(minutes=1)
        intervals.append((start, end))
    return sorted(intervals)


def mark_stateful_available(
    rows: pd.DataFrame,
    intervals: list[tuple[pd.Timestamp, pd.Timestamp]],
) -> pd.DataFrame:
    output = rows.copy()
    starts = pd.to_datetime(output["decision_timestamp"], utc=True, errors="coerce")
    holding = numeric_series(output, "side_pred_holding_minutes", default=1.0).clip(lower=1.0)
    ends = starts + pd.to_timedelta(holding, unit="m")
    output["candidate_interval_start"] = starts
    output["candidate_interval_end"] = ends
    output["stateful_available"] = [
        not interval_overlaps(start, end, intervals)
        for start, end in zip(starts, ends, strict=True)
    ]
    return output


def greedy_select_available(
    rows: pd.DataFrame,
    *,
    needed_count: int,
    intervals: list[tuple[pd.Timestamp, pd.Timestamp]],
) -> pd.DataFrame:
    if needed_count <= 0 or rows.empty:
        return rows.iloc[0:0].copy()
    selected_rows: list[pd.Series] = []
    occupied = list(intervals)
    ordered = rows.sort_values(
        ["side_score", "score_pct", "side_margin_pct", "entry_rank_pct"],
        ascending=[False, False, False, False],
    )
    for _, row in ordered.iterrows():
        start = pd.to_datetime(row["candidate_interval_start"], utc=True, errors="coerce")
        end = pd.to_datetime(row["candidate_interval_end"], utc=True, errors="coerce")
        if pd.isna(start) or pd.isna(end) or interval_overlaps(start, end, occupied):
            continue
        selected_rows.append(row)
        occupied.append((start, end))
        occupied.sort()
        if len(selected_rows) >= needed_count:
            break
    if not selected_rows:
        return rows.iloc[0:0].copy()
    output = pd.DataFrame(selected_rows).reset_index(drop=True)
    output["greedy_rank"] = np.arange(1, len(output) + 1)
    return output


def summarize_bucket(rows: pd.DataFrame, prefix: str) -> dict[str, Any]:
    if rows.empty:
        return {
            f"{prefix}_rows": 0,
            f"{prefix}_available_rows": 0,
            f"{prefix}_best_pnl_sum": 0.0,
            f"{prefix}_fixed60_pnl_sum": 0.0,
            f"{prefix}_fixed240_pnl_sum": 0.0,
            f"{prefix}_fixed720_pnl_sum": 0.0,
            f"{prefix}_score_max": np.nan,
            f"{prefix}_score_median": np.nan,
        }
    available = rows[rows["stateful_available"].astype(bool)]
    return {
        f"{prefix}_rows": int(len(rows)),
        f"{prefix}_available_rows": int(len(available)),
        f"{prefix}_best_pnl_sum": float(available["side_best_adjusted_pnl"].sum()),
        f"{prefix}_fixed60_pnl_sum": float(available["side_fixed_60m_adjusted_pnl"].sum()),
        f"{prefix}_fixed240_pnl_sum": float(available["side_fixed_240m_adjusted_pnl"].sum()),
        f"{prefix}_fixed720_pnl_sum": float(available["side_fixed_720m_adjusted_pnl"].sum()),
        f"{prefix}_score_max": float(rows["side_score"].max()),
        f"{prefix}_score_median": float(rows["side_score"].median()),
    }


def run_diagnostics(args: argparse.Namespace) -> Path:
    policy = policy_candidate_from_name(args.candidate)
    repair_targets = read_repair_targets(
        args.repair_targets,
        candidate=args.candidate,
        variant_contains=args.variant_contains,
        entry_block_rule=args.entry_block_rule,
    )
    current = read_current_trades(
        args.current_trades,
        candidate=args.candidate,
        selector_variant_contains=args.selector_variant_contains,
        entry_block_rule=args.entry_block_rule,
    )
    family_predictions = parse_family_predictions(args.family_predictions)
    side_penalty_rules = parse_side_penalty_rules(args.side_ev_penalty_rules)

    target_months = {
        family: sorted(group["month"].astype(str).unique().tolist())
        for family, group in repair_targets.groupby("family")
    }
    side_parts: list[pd.DataFrame] = []
    needed_columns = [
        "decision_timestamp",
        "entry_timestamp",
        "dataset_month",
        "combined_regime",
        "session_regime",
        args.long_column,
        args.short_column,
        args.long_holding_column,
        args.short_holding_column,
        "pred_long_entry_local_rank",
        "pred_short_entry_local_rank",
        "long_best_adjusted_pnl",
        "short_best_adjusted_pnl",
        "long_best_holding_minutes",
        "short_best_holding_minutes",
        "long_fixed_60m_adjusted_pnl",
        "short_fixed_60m_adjusted_pnl",
        "long_fixed_240m_adjusted_pnl",
        "short_fixed_240m_adjusted_pnl",
        "long_fixed_720m_adjusted_pnl",
        "short_fixed_720m_adjusted_pnl",
        *[rule[1] for rule in side_penalty_rules],
    ]
    for family, months in target_months.items():
        if family not in family_predictions:
            raise ValueError(f"missing prediction path for family {family}")
        prediction_path = family_predictions[family]
        columns = parquet_columns(prediction_path)
        read_columns = [column for column in dict.fromkeys(needed_columns) if column in columns]
        predictions = pd.read_parquet(prediction_path, columns=read_columns)
        predictions["month"] = month_series(predictions)
        predictions = predictions[predictions["month"].isin(months)].copy()
        if predictions.empty:
            continue
        side_rows = build_side_rows(
            predictions,
            family=family,
            long_column=args.long_column,
            short_column=args.short_column,
            long_holding_column=args.long_holding_column,
            short_holding_column=args.short_holding_column,
            min_valid_predicted_hold_minutes=args.min_valid_predicted_hold_minutes,
            max_predicted_hold_minutes=args.max_predicted_hold_minutes,
            side_penalty_rules=side_penalty_rules,
        )
        side_parts.append(side_rows)
    if not side_parts:
        raise ValueError("no prediction rows found for repair target months")
    all_side_rows = pd.concat(side_parts, ignore_index=True)

    candidate_rows: list[pd.DataFrame] = []
    selected_rows: list[pd.DataFrame] = []
    summary_rows: list[dict[str, Any]] = []
    for _, target in repair_targets.iterrows():
        role = str(target["role"])
        family = str(target["family"])
        month = str(target["month"])
        side = str(target["needed_side"])
        needed_count = int(target["extra_side_needed"])
        rows = all_side_rows[
            all_side_rows["family"].astype(str).eq(family)
            & all_side_rows["month"].astype(str).eq(month)
            & all_side_rows["side"].astype(str).eq(side)
        ].copy()
        intervals = current_intervals(current, family=family, role=role, month=month)
        rows["role"] = role
        rows["needed_side"] = side
        rows["extra_side_needed"] = needed_count
        rows["strict_side_specific"] = (
            rows["holding_ok"]
            & rows["side_score"].gt(policy.entry_threshold)
            & rows["score_pct"].ge(policy.score_quantile)
            & rows["side_margin_pct"].ge(policy.side_gap_quantile)
            & rows["entry_rank_pct"].ge(policy.rank_quantile)
            & rows["side_margin"].ge(args.min_strict_side_margin)
        )
        rows["relaxed_side_specific"] = (
            rows["holding_ok"]
            & rows["side_score"].gt(args.relaxed_min_score)
            & rows["score_pct"].ge(args.relaxed_score_quantile)
            & rows["side_margin_pct"].ge(args.relaxed_side_margin_quantile)
            & rows["entry_rank_pct"].ge(args.relaxed_rank_quantile)
            & rows["side_margin"].ge(args.relaxed_min_side_margin)
        )
        strict_stage_ok = pd.DataFrame(
            {
                "holding": rows["holding_ok"],
                "score_floor": rows["side_score"].gt(policy.entry_threshold),
                "score_q": rows["score_pct"].ge(policy.score_quantile),
                "side_margin_q": rows["side_margin_pct"].ge(policy.side_gap_quantile),
                "rank_q": rows["entry_rank_pct"].ge(policy.rank_quantile),
                "side_margin": rows["side_margin"].ge(args.min_strict_side_margin),
            }
        )
        rows["strict_failed_stage_count"] = (~strict_stage_ok).sum(axis=1)
        rows["one_failed_strict_stage"] = rows["strict_failed_stage_count"].eq(1)
        rows = mark_stateful_available(rows, intervals)
        keep = rows[
            rows["strict_side_specific"]
            | rows["relaxed_side_specific"]
            | rows["one_failed_strict_stage"]
        ].copy()
        keep["target_pnl_hurdle"] = float(target.get("month_pnl_hurdle", 0.0))
        keep["target_trade_count"] = int(float(target.get("trade_count", 0.0)))
        keep["target_long_trade_count"] = int(float(target.get("long_trade_count", 0.0)))
        keep["target_short_trade_count"] = int(float(target.get("short_trade_count", 0.0)))
        candidate_rows.append(keep)

        strict_selected = greedy_select_available(
            keep[keep["strict_side_specific"] & keep["stateful_available"]],
            needed_count=needed_count,
            intervals=intervals,
        )
        strict_selected["selection_bucket"] = "strict"
        relaxed_selected = greedy_select_available(
            keep[keep["relaxed_side_specific"] & keep["stateful_available"]],
            needed_count=needed_count,
            intervals=intervals,
        )
        relaxed_selected["selection_bucket"] = "relaxed"
        onefail_selected = greedy_select_available(
            keep[keep["one_failed_strict_stage"] & keep["stateful_available"]],
            needed_count=needed_count,
            intervals=intervals,
        )
        onefail_selected["selection_bucket"] = "one_failed_strict_stage"
        selected_rows.extend([strict_selected, relaxed_selected, onefail_selected])

        summary = {
            "role": role,
            "family": family,
            "month": month,
            "needed_side": side,
            "extra_side_needed": needed_count,
            "current_month_pnl": float(target.get("total_adjusted_pnl", 0.0)),
            "month_pnl_hurdle": float(target.get("month_pnl_hurdle", 0.0)),
            "current_trade_count": int(float(target.get("trade_count", 0.0))),
            "current_long_trade_count": int(float(target.get("long_trade_count", 0.0))),
            "current_short_trade_count": int(float(target.get("short_trade_count", 0.0))),
            "current_interval_count": int(len(intervals)),
            "side_rows": int(len(rows)),
            "holding_ok_rows": int(rows["holding_ok"].sum()),
            **summarize_bucket(rows[rows["strict_side_specific"]], "strict"),
            **summarize_bucket(rows[rows["relaxed_side_specific"]], "relaxed"),
            **summarize_bucket(rows[rows["one_failed_strict_stage"]], "onefail"),
            "strict_greedy_selected": int(len(strict_selected)),
            "strict_greedy_best_pnl_sum": float(strict_selected["side_best_adjusted_pnl"].sum()) if len(strict_selected) else 0.0,
            "strict_greedy_fixed60_pnl_sum": float(strict_selected["side_fixed_60m_adjusted_pnl"].sum()) if len(strict_selected) else 0.0,
            "strict_greedy_fixed240_pnl_sum": float(strict_selected["side_fixed_240m_adjusted_pnl"].sum()) if len(strict_selected) else 0.0,
            "strict_greedy_fixed720_pnl_sum": float(strict_selected["side_fixed_720m_adjusted_pnl"].sum()) if len(strict_selected) else 0.0,
            "relaxed_greedy_selected": int(len(relaxed_selected)),
            "relaxed_greedy_best_pnl_sum": float(relaxed_selected["side_best_adjusted_pnl"].sum()) if len(relaxed_selected) else 0.0,
            "relaxed_greedy_fixed60_pnl_sum": float(relaxed_selected["side_fixed_60m_adjusted_pnl"].sum()) if len(relaxed_selected) else 0.0,
            "relaxed_greedy_fixed240_pnl_sum": float(relaxed_selected["side_fixed_240m_adjusted_pnl"].sum()) if len(relaxed_selected) else 0.0,
            "relaxed_greedy_fixed720_pnl_sum": float(relaxed_selected["side_fixed_720m_adjusted_pnl"].sum()) if len(relaxed_selected) else 0.0,
            "onefail_greedy_selected": int(len(onefail_selected)),
            "onefail_greedy_best_pnl_sum": float(onefail_selected["side_best_adjusted_pnl"].sum()) if len(onefail_selected) else 0.0,
            "onefail_greedy_fixed60_pnl_sum": float(onefail_selected["side_fixed_60m_adjusted_pnl"].sum()) if len(onefail_selected) else 0.0,
            "onefail_greedy_fixed240_pnl_sum": float(onefail_selected["side_fixed_240m_adjusted_pnl"].sum()) if len(onefail_selected) else 0.0,
            "onefail_greedy_fixed720_pnl_sum": float(onefail_selected["side_fixed_720m_adjusted_pnl"].sum()) if len(onefail_selected) else 0.0,
        }
        summary_rows.append(summary)

    candidate_frame = (
        pd.concat(candidate_rows, ignore_index=True)
        if candidate_rows
        else pd.DataFrame()
    )
    selected_frame = (
        pd.concat(selected_rows, ignore_index=True)
        if selected_rows
        else pd.DataFrame()
    )
    summary_frame = pd.DataFrame(summary_rows).sort_values(["role", "month", "needed_side"])

    run_dir = make_run_dir(args.output_dir, args.label)
    candidate_frame.to_csv(run_dir / "thin_month_opposite_candidate_rows.csv", index=False)
    selected_frame.to_csv(run_dir / "thin_month_opposite_greedy_selection.csv", index=False)
    summary_frame.to_csv(run_dir / "thin_month_opposite_month_summary.csv", index=False)
    config = {
        "repair_targets": args.repair_targets,
        "current_trades": args.current_trades,
        "family_predictions": family_predictions,
        "candidate": args.candidate,
        "score_kind": args.score_kind,
        "long_column": args.long_column,
        "short_column": args.short_column,
        "long_holding_column": args.long_holding_column,
        "short_holding_column": args.short_holding_column,
        "variant_contains": args.variant_contains,
        "selector_variant_contains": args.selector_variant_contains,
        "entry_block_rule": args.entry_block_rule,
        "side_ev_penalty_rules": args.side_ev_penalty_rules,
        "min_valid_predicted_hold_minutes": args.min_valid_predicted_hold_minutes,
        "max_predicted_hold_minutes": args.max_predicted_hold_minutes,
        "min_strict_side_margin": args.min_strict_side_margin,
        "relaxed_min_score": args.relaxed_min_score,
        "relaxed_score_quantile": args.relaxed_score_quantile,
        "relaxed_side_margin_quantile": args.relaxed_side_margin_quantile,
        "relaxed_rank_quantile": args.relaxed_rank_quantile,
        "relaxed_min_side_margin": args.relaxed_min_side_margin,
    }
    (run_dir / "config.json").write_text(
        json.dumps(config, indent=2, default=local_json_default) + "\n",
        encoding="utf-8",
    )

    print("Thin month opposite candidate summary:")
    print(
        summary_frame[
            [
                "role",
                "month",
                "needed_side",
                "extra_side_needed",
                "strict_available_rows",
                "strict_greedy_selected",
                "strict_greedy_fixed60_pnl_sum",
                "relaxed_available_rows",
                "relaxed_greedy_selected",
                "relaxed_greedy_fixed60_pnl_sum",
                "relaxed_greedy_best_pnl_sum",
                "onefail_available_rows",
                "onefail_greedy_selected",
                "onefail_greedy_fixed60_pnl_sum",
                "onefail_greedy_best_pnl_sum",
            ]
        ].to_string(index=False)
    )
    print(f"artifacts: {run_dir}")
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repair-targets", type=Path, required=True)
    parser.add_argument("--current-trades", type=Path, required=True)
    parser.add_argument("--family-predictions", action="append", required=True)
    parser.add_argument("--candidate", default="q95_sg95_rank90_floor5_side_regime_session_month")
    parser.add_argument("--score-kind", default="fixed60_uncertainty_margin_famdirregsess_w5")
    parser.add_argument("--long-column", required=True)
    parser.add_argument("--short-column", required=True)
    parser.add_argument("--long-holding-column", default="pred_mlp_long_exit_event_minutes")
    parser.add_argument("--short-holding-column", default="pred_mlp_short_exit_event_minutes")
    parser.add_argument("--variant-contains", default="")
    parser.add_argument("--selector-variant-contains", default="")
    parser.add_argument("--entry-block-rule", default="long_range_normal_ny_fixed60_pred_gt0")
    parser.add_argument("--side-ev-penalty-rules", default="")
    parser.add_argument("--min-valid-predicted-hold-minutes", type=float, default=30.0)
    parser.add_argument("--max-predicted-hold-minutes", type=float, default=720.0)
    parser.add_argument("--min-strict-side-margin", type=float, default=0.0)
    parser.add_argument("--relaxed-min-score", type=float, default=5.0)
    parser.add_argument("--relaxed-score-quantile", type=float, default=0.90)
    parser.add_argument("--relaxed-side-margin-quantile", type=float, default=0.90)
    parser.add_argument("--relaxed-rank-quantile", type=float, default=0.80)
    parser.add_argument("--relaxed-min-side-margin", type=float, default=0.0)
    parser.add_argument("--output-dir", type=Path, default=Path("data/reports/backtests"))
    parser.add_argument("--label", default="entry_ev_thin_month_opposite_candidate_diagnostics")
    return parser


def main(argv: list[str] | None = None) -> int:
    run_diagnostics(build_parser().parse_args(argv))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
