#!/usr/bin/env python3
"""Diagnose listwise support-repair choices before stateful quota selection."""

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

from entry_ev_support_repair_pairwise_switch_diagnostics import (  # noqa: E402
    add_scenario_label,
    choose_scenario,
    normalize_repair_rows,
    numeric_series,
    parse_csv,
    text_series,
)


DEFAULT_INCLUDE_REJECT_REASONS = "quota_full,overlap"
DEFAULT_QUOTA_COLUMNS = "scenario_label,role,month,side"
DEFAULT_OVERLAP_COLUMNS = "role"
DEFAULT_CLUSTER_COLUMNS = "scenario_label,role,month,side"
SELECTOR_SPECS: dict[str, tuple[list[str], list[bool]]] = {
    "repair_score_greedy": (
        [
            "repair_score",
            "support_reduction_value",
            "repair_expected_pnl",
            "actual_pnl_at_hv_chosen_horizon",
            "decision_timestamp",
        ],
        [False, False, False, False, True],
    ),
    "actual_oracle_greedy": (
        [
            "actual_pnl_at_hv_chosen_horizon",
            "support_reduction_value",
            "repair_score",
            "decision_timestamp",
        ],
        [False, False, False, True],
    ),
    "pred_pnl_greedy": (
        [
            "hv_chosen_pred_pnl",
            "repair_score",
            "support_reduction_value",
            "decision_timestamp",
        ],
        [False, False, False, True],
    ),
    "harmful_low_greedy": (
        [
            "hv_chosen_pred_harmful_overestimate_prob",
            "repair_score",
            "support_reduction_value",
            "decision_timestamp",
        ],
        [True, False, False, True],
    ),
    "tail_low_greedy": (
        [
            "hv_chosen_pred_tail_loss_prob",
            "repair_score",
            "support_reduction_value",
            "decision_timestamp",
        ],
        [True, False, False, True],
    ),
    "support_proxy_high_greedy": (
        [
            "repair_support_success_proxy",
            "repair_score",
            "actual_pnl_at_hv_chosen_horizon",
            "decision_timestamp",
        ],
        [False, False, False, True],
    ),
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


def interval_overlaps(
    start: pd.Timestamp,
    end: pd.Timestamp,
    intervals: list[tuple[pd.Timestamp, pd.Timestamp]],
) -> bool:
    return any(start < other_end and end > other_start for other_start, other_end in intervals)


def prepare_stateful_universe(
    additions: pd.DataFrame,
    rejections: pd.DataFrame,
    *,
    scenario_label: str,
    include_reject_reasons: list[str],
) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    selected = add_scenario_label(additions)
    selected = selected[selected["scenario_label"].astype(str).eq(scenario_label)].copy()
    if not selected.empty:
        selected["selection_status"] = "selected"
        selected["reject_reason"] = "selected"
        selected["current_selected"] = True
        frames.append(selected)

    if not rejections.empty:
        rejected = add_scenario_label(rejections)
        rejected = rejected[rejected["scenario_label"].astype(str).eq(scenario_label)].copy()
        rejected["reject_reason"] = text_series(rejected, "reject_reason")
        rejected = rejected[rejected["reject_reason"].isin(include_reject_reasons)].copy()
        if not rejected.empty:
            rejected["selection_status"] = rejected["reject_reason"]
            rejected["current_selected"] = False
            frames.append(rejected)

    if not frames:
        raise ValueError(f"no stateful candidate rows for scenario_label={scenario_label}")
    universe = pd.concat(frames, ignore_index=True, sort=False)
    normalized = normalize_repair_rows(universe, source_name="stateful_universe")
    normalized["selection_status"] = text_series(normalized, "selection_status")
    normalized["reject_reason"] = text_series(normalized, "reject_reason")
    normalized["current_selected"] = normalized["selection_status"].eq("selected")
    normalized["entry_timestamp"] = pd.to_datetime(
        normalized.get("entry_timestamp", normalized["decision_timestamp"]),
        utc=True,
        errors="coerce",
    )
    normalized["exit_timestamp"] = pd.to_datetime(
        normalized.get("exit_timestamp"),
        utc=True,
        errors="coerce",
    )
    missing_exit = normalized["exit_timestamp"].isna()
    if missing_exit.any():
        normalized.loc[missing_exit, "exit_timestamp"] = normalized.loc[
            missing_exit,
            "decision_timestamp",
        ] + pd.to_timedelta(
            numeric_series(normalized.loc[missing_exit], "hv_chosen_horizon_minutes"),
            unit="m",
        )
    normalized = normalized[
        normalized["entry_timestamp"].notna() & normalized["exit_timestamp"].notna()
    ].copy()
    normalized["candidate_id"] = np.arange(len(normalized), dtype=int)
    return normalized.reset_index(drop=True)


def group_key(row: pd.Series, columns: list[str]) -> tuple[Any, ...]:
    return tuple(row[column] for column in columns)


def quota_by_group(frame: pd.DataFrame, quota_columns: list[str]) -> dict[tuple[Any, ...], int]:
    quotas: dict[tuple[Any, ...], int] = {}
    for key, group in frame.groupby(quota_columns, dropna=False, sort=False):
        group_key_value = key if isinstance(key, tuple) else (key,)
        quota = int(max(0, np.ceil(numeric_series(group, "extra_side_needed").max())))
        quotas[group_key_value] = quota
    return quotas


def greedy_select_with_quotas(
    frame: pd.DataFrame,
    *,
    sort_columns: list[str],
    ascending: list[bool],
    quota_columns: list[str],
    overlap_columns: list[str],
) -> set[int]:
    if frame.empty:
        return set()
    columns = [column for column in sort_columns if column in frame.columns]
    if not columns:
        columns = ["decision_timestamp"]
        ascending = [True]
    else:
        ascending = [direction for column, direction in zip(sort_columns, ascending, strict=True) if column in columns]
    sorted_rows = frame.sort_values(columns, ascending=ascending)
    quotas = quota_by_group(frame, quota_columns)
    quota_used: dict[tuple[Any, ...], int] = {}
    intervals: dict[tuple[Any, ...], list[tuple[pd.Timestamp, pd.Timestamp]]] = {}
    selected_ids: set[int] = set()
    for _, row in sorted_rows.iterrows():
        quota_key = group_key(row, quota_columns)
        if quota_used.get(quota_key, 0) >= quotas.get(quota_key, 0):
            continue
        overlap_key = group_key(row, overlap_columns)
        start = row["entry_timestamp"]
        end = row["exit_timestamp"]
        if interval_overlaps(start, end, intervals.get(overlap_key, [])):
            continue
        candidate_id = int(row["candidate_id"])
        selected_ids.add(candidate_id)
        quota_used[quota_key] = quota_used.get(quota_key, 0) + 1
        intervals.setdefault(overlap_key, []).append((start, end))
    return selected_ids


def assign_interval_clusters(
    frame: pd.DataFrame,
    *,
    cluster_columns: list[str],
    cluster_gap_minutes: float,
) -> pd.DataFrame:
    output = frame.copy()
    output["interval_cluster_id"] = ""
    cluster_number = 0
    gap = pd.Timedelta(minutes=float(cluster_gap_minutes))
    for key, group in output.groupby(cluster_columns, dropna=False, sort=False):
        sorted_group = group.sort_values(["entry_timestamp", "exit_timestamp"])
        current_end: pd.Timestamp | None = None
        current_cluster = -1
        for idx, row in sorted_group.iterrows():
            if current_end is None or row["entry_timestamp"] > current_end + gap:
                cluster_number += 1
                current_cluster = cluster_number
                current_end = row["exit_timestamp"]
            else:
                current_end = max(current_end, row["exit_timestamp"])
            key_parts = key if isinstance(key, tuple) else (key,)
            output.loc[idx, "interval_cluster_id"] = (
                "|".join(str(part) for part in key_parts) + f"|c{current_cluster:05d}"
            )
    return output


def add_selector_flags(
    frame: pd.DataFrame,
    *,
    quota_columns: list[str],
    overlap_columns: list[str],
) -> pd.DataFrame:
    output = frame.copy()
    output["current_replay_selected"] = output["current_selected"].astype(bool)
    for selector, (sort_columns, ascending) in SELECTOR_SPECS.items():
        selected_ids = greedy_select_with_quotas(
            output,
            sort_columns=sort_columns,
            ascending=ascending,
            quota_columns=quota_columns,
            overlap_columns=overlap_columns,
        )
        output[f"{selector}_selected"] = output["candidate_id"].isin(selected_ids)
    return output


def summarize_selector(
    frame: pd.DataFrame,
    *,
    selector: str,
    selected_column: str,
    current_actual_sum: float,
) -> dict[str, Any]:
    selected = frame[frame[selected_column]].copy()
    actual = numeric_series(selected, "actual_pnl_at_hv_chosen_horizon", default=0.0)
    harmful = numeric_series(
        selected,
        "hv_chosen_pred_harmful_overestimate_prob",
        default=0.0,
    )
    tail = numeric_series(selected, "hv_chosen_pred_tail_loss_prob", default=0.0)
    return {
        "selector": selector,
        "selected_count": int(len(selected)),
        "actual_pnl_sum": float(actual.sum()) if len(selected) else 0.0,
        "actual_pnl_mean": float(actual.mean()) if len(selected) else np.nan,
        "actual_pnl_min": float(actual.min()) if len(selected) else np.nan,
        "loss_count": int(actual.lt(0.0).sum()) if len(selected) else 0,
        "tail_loss_count": int(actual.le(-5.0).sum()) if len(selected) else 0,
        "harmful_prob_mean": float(harmful.mean()) if len(selected) else np.nan,
        "tail_prob_mean": float(tail.mean()) if len(selected) else np.nan,
        "delta_vs_current": float(actual.sum() - current_actual_sum) if len(selected) else -current_actual_sum,
    }


def selector_summary(frame: pd.DataFrame) -> pd.DataFrame:
    current_actual_sum = float(
        numeric_series(
            frame[frame["current_replay_selected"]],
            "actual_pnl_at_hv_chosen_horizon",
            default=0.0,
        ).sum()
    )
    rows = [
        summarize_selector(
            frame,
            selector="current_replay",
            selected_column="current_replay_selected",
            current_actual_sum=current_actual_sum,
        )
    ]
    for selector in SELECTOR_SPECS:
        rows.append(
            summarize_selector(
                frame,
                selector=selector,
                selected_column=f"{selector}_selected",
                current_actual_sum=current_actual_sum,
            )
        )
    return pd.DataFrame(rows)


def cluster_summary(frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for cluster_id, group in frame.groupby("interval_cluster_id", dropna=False, sort=False):
        actual = numeric_series(group, "actual_pnl_at_hv_chosen_horizon", default=0.0)
        best_idx = actual.idxmax()
        repair_idx = numeric_series(group, "repair_score", default=0.0).idxmax()
        harmful_idx = numeric_series(
            group,
            "hv_chosen_pred_harmful_overestimate_prob",
            default=0.0,
        ).idxmin()
        selected = group[group["current_replay_selected"]]
        rows.append(
            {
                "interval_cluster_id": cluster_id,
                "scenario_label": group.iloc[0]["scenario_label"],
                "role": group.iloc[0]["role"],
                "month": group.iloc[0]["month"],
                "side": group.iloc[0]["side"],
                "row_count": int(len(group)),
                "current_selected_count": int(len(selected)),
                "current_selected_actual_sum": float(
                    numeric_series(selected, "actual_pnl_at_hv_chosen_horizon").sum()
                )
                if len(selected)
                else 0.0,
                "best_actual_pnl": float(group.loc[best_idx, "actual_pnl_at_hv_chosen_horizon"]),
                "best_actual_decision_timestamp": group.loc[best_idx, "decision_timestamp"],
                "best_actual_horizon_minutes": group.loc[best_idx, "hv_chosen_horizon_minutes"],
                "repair_top_actual_pnl": float(
                    group.loc[repair_idx, "actual_pnl_at_hv_chosen_horizon"]
                ),
                "repair_top_decision_timestamp": group.loc[repair_idx, "decision_timestamp"],
                "harmful_low_actual_pnl": float(
                    group.loc[harmful_idx, "actual_pnl_at_hv_chosen_horizon"]
                ),
                "harmful_low_decision_timestamp": group.loc[harmful_idx, "decision_timestamp"],
                "best_minus_current": float(
                    group.loc[best_idx, "actual_pnl_at_hv_chosen_horizon"]
                    - numeric_series(selected, "actual_pnl_at_hv_chosen_horizon").max()
                )
                if len(selected)
                else np.nan,
            }
        )
    return pd.DataFrame(rows)


def quota_group_summary(frame: pd.DataFrame, *, quota_columns: list[str]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for key, group in frame.groupby(quota_columns, dropna=False, sort=False):
        key_values = key if isinstance(key, tuple) else (key,)
        row = {column: value for column, value in zip(quota_columns, key_values, strict=True)}
        row["row_count"] = int(len(group))
        row["quota"] = int(max(0, np.ceil(numeric_series(group, "extra_side_needed").max())))
        for selector in ["current_replay", *SELECTOR_SPECS.keys()]:
            column = (
                "current_replay_selected"
                if selector == "current_replay"
                else f"{selector}_selected"
            )
            selected = group[group[column]]
            row[f"{selector}_count"] = int(len(selected))
            row[f"{selector}_actual_sum"] = float(
                numeric_series(selected, "actual_pnl_at_hv_chosen_horizon").sum()
            )
        row["oracle_delta_vs_current"] = (
            row["actual_oracle_greedy_actual_sum"] - row["current_replay_actual_sum"]
        )
        rows.append(row)
    return pd.DataFrame(rows)


def add_rank_columns(frame: pd.DataFrame, *, quota_columns: list[str]) -> pd.DataFrame:
    output = frame.copy()
    output["actual_rank_in_quota_group"] = (
        output.groupby(quota_columns, dropna=False)["actual_pnl_at_hv_chosen_horizon"]
        .rank(method="first", ascending=False)
        .astype(int)
    )
    output["repair_rank_in_quota_group"] = (
        output.groupby(quota_columns, dropna=False)["repair_score"]
        .rank(method="first", ascending=False)
        .astype(int)
    )
    output["harmful_rank_in_quota_group"] = (
        output.groupby(quota_columns, dropna=False)[
            "hv_chosen_pred_harmful_overestimate_prob"
        ]
        .rank(method="first", ascending=True)
        .astype(int)
    )
    output["actual_rank_in_cluster"] = (
        output.groupby("interval_cluster_id", dropna=False)[
            "actual_pnl_at_hv_chosen_horizon"
        ]
        .rank(method="first", ascending=False)
        .astype(int)
    )
    return output


def run_diagnostics(args: argparse.Namespace) -> Path:
    additions = pd.read_csv(args.additions)
    rejections = pd.read_csv(args.rejections) if args.rejections else pd.DataFrame()
    summary = pd.read_csv(args.summary) if args.summary else pd.DataFrame()
    scenario = choose_scenario(summary, args.scenario_label)
    quota_columns = parse_csv(args.quota_columns)
    overlap_columns = parse_csv(args.overlap_columns)
    cluster_columns = parse_csv(args.cluster_columns)
    universe = prepare_stateful_universe(
        additions,
        rejections,
        scenario_label=scenario,
        include_reject_reasons=parse_csv(args.include_reject_reasons),
    )
    universe = assign_interval_clusters(
        universe,
        cluster_columns=cluster_columns,
        cluster_gap_minutes=args.cluster_gap_minutes,
    )
    universe = add_selector_flags(
        universe,
        quota_columns=quota_columns,
        overlap_columns=overlap_columns,
    )
    universe = add_rank_columns(universe, quota_columns=quota_columns)

    selectors = selector_summary(universe)
    clusters = cluster_summary(universe)
    quota_groups = quota_group_summary(universe, quota_columns=quota_columns)

    run_dir = make_run_dir(args.output_dir, args.label)
    universe.to_csv(run_dir / "support_repair_listwise_candidate_examples.csv", index=False)
    selectors.to_csv(run_dir / "support_repair_listwise_selector_summary.csv", index=False)
    clusters.to_csv(run_dir / "support_repair_listwise_cluster_summary.csv", index=False)
    quota_groups.to_csv(run_dir / "support_repair_listwise_quota_group_summary.csv", index=False)
    (run_dir / "config.json").write_text(
        json.dumps(
            {
                "additions": args.additions,
                "rejections": args.rejections,
                "summary": args.summary,
                "scenario_label": scenario,
                "include_reject_reasons": parse_csv(args.include_reject_reasons),
                "quota_columns": quota_columns,
                "overlap_columns": overlap_columns,
                "cluster_columns": cluster_columns,
                "cluster_gap_minutes": args.cluster_gap_minutes,
            },
            indent=2,
            sort_keys=True,
            default=local_json_default,
        )
        + "\n",
        encoding="utf-8",
    )

    print("Support repair listwise cluster diagnostics:")
    print(f"scenario_label: {scenario}")
    print(selectors.to_string(index=False))
    print(f"artifacts: {run_dir}")
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--additions", type=Path, required=True)
    parser.add_argument("--rejections", type=Path)
    parser.add_argument("--summary", type=Path)
    parser.add_argument("--scenario-label", default="")
    parser.add_argument("--include-reject-reasons", default=DEFAULT_INCLUDE_REJECT_REASONS)
    parser.add_argument("--quota-columns", default=DEFAULT_QUOTA_COLUMNS)
    parser.add_argument("--overlap-columns", default=DEFAULT_OVERLAP_COLUMNS)
    parser.add_argument("--cluster-columns", default=DEFAULT_CLUSTER_COLUMNS)
    parser.add_argument("--cluster-gap-minutes", type=float, default=0.0)
    parser.add_argument("--output-dir", type=Path, default=Path("data/reports/backtests"))
    parser.add_argument("--label", default="entry_ev_support_repair_listwise_cluster")
    return parser


def main(argv: list[str] | None = None) -> int:
    run_diagnostics(build_parser().parse_args(argv))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
