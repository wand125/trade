#!/usr/bin/env python3
"""Diagnose singleton abstention rules across many support-repair scenarios."""

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

from entry_ev_support_repair_listwise_cluster_diagnostics import (  # noqa: E402
    DEFAULT_CLUSTER_COLUMNS,
    DEFAULT_INCLUDE_REJECT_REASONS,
    DEFAULT_OVERLAP_COLUMNS,
    DEFAULT_QUOTA_COLUMNS,
    add_rank_columns,
    add_selector_flags,
    assign_interval_clusters,
    prepare_stateful_universe,
)
from entry_ev_support_repair_pairwise_switch_diagnostics import (  # noqa: E402
    numeric_series,
    parse_csv,
    text_series,
)
from entry_ev_support_repair_singleton_abstention_diagnostics import (  # noqa: E402
    DEFAULT_RULES,
    bool_series,
    rule_mask,
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


def scenario_labels_from_summary(
    summary: pd.DataFrame,
    *,
    scenario_labels: str,
    row_scopes: str,
    max_scenarios: int,
) -> list[str]:
    if scenario_labels:
        labels = parse_csv(scenario_labels)
    else:
        if "scenario_label" not in summary.columns:
            raise ValueError("summary must contain scenario_label when scenario_labels is omitted")
        output = summary.copy()
        scopes = parse_csv(row_scopes)
        if scopes and "row_scope" in output.columns:
            output = output[text_series(output, "row_scope").isin(scopes)].copy()
        labels = text_series(output, "scenario_label").drop_duplicates().tolist()
    if max_scenarios > 0:
        labels = labels[:max_scenarios]
    if not labels:
        raise ValueError("no scenario labels selected")
    return labels


def add_singleton_surface_columns(
    frame: pd.DataFrame,
    *,
    quota_columns: list[str],
) -> pd.DataFrame:
    output = frame.copy()
    group = output.groupby(quota_columns, dropna=False)
    output["quota_group_row_count"] = group["candidate_id"].transform("size").astype(int)
    output["quota_group_quota"] = group["extra_side_needed"].transform(
        lambda values: max(0, int(np.ceil(float(pd.to_numeric(values).max())))),
    )
    output["quota_group_is_singleton"] = output["quota_group_row_count"].le(
        output["quota_group_quota"],
    )
    output["actual_positive"] = numeric_series(
        output,
        "actual_pnl_at_hv_chosen_horizon",
    ).gt(0.0)
    output["actual_loss"] = numeric_series(
        output,
        "actual_pnl_at_hv_chosen_horizon",
    ).lt(0.0)
    output["actual_tail_loss"] = numeric_series(
        output,
        "actual_pnl_at_hv_chosen_horizon",
    ).le(-5.0)

    timestamp = pd.to_datetime(
        output["decision_timestamp"],
        utc=True,
        errors="coerce",
    ).dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    horizon = numeric_series(output, "hv_chosen_horizon_minutes").round(6).astype(str)
    output["singleton_surface_key"] = (
        text_series(output, "role")
        + "|"
        + text_series(output, "month")
        + "|"
        + text_series(output, "side")
        + "|"
        + timestamp.fillna("")
        + "|"
        + horizon
    )
    return output


def row_stats(frame: pd.DataFrame, *, prefix: str) -> dict[str, Any]:
    actual = numeric_series(frame, "actual_pnl_at_hv_chosen_horizon")
    count = int(len(frame))
    loss_count = int(actual.lt(0.0).sum()) if count else 0
    tail_count = int(actual.le(-5.0).sum()) if count else 0
    positive_count = int(actual.gt(0.0).sum()) if count else 0
    return {
        f"{prefix}_count": count,
        f"{prefix}_actual_sum": float(actual.sum()) if count else 0.0,
        f"{prefix}_actual_mean": float(actual.mean()) if count else np.nan,
        f"{prefix}_loss_count": loss_count,
        f"{prefix}_tail_loss_count": tail_count,
        f"{prefix}_positive_count": positive_count,
        f"{prefix}_loss_rate": float(loss_count / count) if count else np.nan,
        f"{prefix}_tail_loss_rate": float(tail_count / count) if count else np.nan,
        f"{prefix}_positive_actual_sum": float(actual[actual.gt(0.0)].sum())
        if count
        else 0.0,
    }


def unique_rows(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    return frame.sort_values(
        ["singleton_surface_key", "scenario_label", "candidate_id"],
        kind="mergesort",
    ).drop_duplicates("singleton_surface_key", keep="first")


def surface_rule_summary(frame: pd.DataFrame, *, rules: list[str]) -> pd.DataFrame:
    singleton = bool_series(frame, "quota_group_is_singleton")
    current = bool_series(frame, "current_replay_selected")
    singleton_rows = frame[singleton].copy()
    current_singleton = frame[singleton & current].copy()
    current_singleton_losses = current_singleton[
        numeric_series(current_singleton, "actual_pnl_at_hv_chosen_horizon").lt(0.0)
    ].copy()
    current_singleton_tail_losses = current_singleton[
        numeric_series(current_singleton, "actual_pnl_at_hv_chosen_horizon").le(-5.0)
    ].copy()

    rows: list[dict[str, Any]] = []
    for rule in rules:
        flags = rule_mask(frame, rule)
        flagged = frame[flags].copy()
        flagged_current = frame[flags & current].copy()
        flagged_current_losses = flagged_current[
            numeric_series(flagged_current, "actual_pnl_at_hv_chosen_horizon").lt(0.0)
        ].copy()
        flagged_current_tail_losses = flagged_current[
            numeric_series(flagged_current, "actual_pnl_at_hv_chosen_horizon").le(-5.0)
        ].copy()
        row: dict[str, Any] = {
            "rule": rule,
            "scenario_count": int(text_series(frame, "scenario_label").nunique()),
            "candidate_row_count": int(len(frame)),
            "singleton_row_count": int(len(singleton_rows)),
            "singleton_unique_count": int(unique_rows(singleton_rows)["singleton_surface_key"].nunique())
            if not singleton_rows.empty
            else 0,
            "current_singleton_row_count": int(len(current_singleton)),
            "current_singleton_unique_count": int(
                unique_rows(current_singleton)["singleton_surface_key"].nunique()
            )
            if not current_singleton.empty
            else 0,
            "current_singleton_loss_count": int(len(current_singleton_losses)),
            "current_singleton_tail_loss_count": int(len(current_singleton_tail_losses)),
        }
        row.update(row_stats(flagged, prefix="flagged"))
        row.update(row_stats(unique_rows(flagged), prefix="flagged_unique"))
        row.update(row_stats(flagged_current, prefix="flagged_current"))
        row.update(row_stats(unique_rows(flagged_current), prefix="flagged_current_unique"))
        row["current_loss_capture_rate"] = (
            float(len(flagged_current_losses) / len(current_singleton_losses))
            if len(current_singleton_losses)
            else np.nan
        )
        row["current_tail_loss_capture_rate"] = (
            float(len(flagged_current_tail_losses) / len(current_singleton_tail_losses))
            if len(current_singleton_tail_losses)
            else np.nan
        )
        row["current_positive_damage_sum"] = float(
            numeric_series(flagged_current, "actual_pnl_at_hv_chosen_horizon")[
                numeric_series(flagged_current, "actual_pnl_at_hv_chosen_horizon").gt(0.0)
            ].sum()
        )
        rows.append(row)
    return pd.DataFrame(rows)


def scenario_rule_summary(frame: pd.DataFrame, *, rules: list[str]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for scenario_label, scenario in frame.groupby("scenario_label", dropna=False, sort=False):
        current = bool_series(scenario, "current_replay_selected")
        singleton = bool_series(scenario, "quota_group_is_singleton")
        current_rows = scenario[current].copy()
        current_singleton = scenario[current & singleton].copy()
        for rule in rules:
            flags = rule_mask(scenario, rule)
            flagged_current = scenario[flags & current].copy()
            row: dict[str, Any] = {
                "scenario_label": scenario_label,
                "rule": rule,
                "candidate_row_count": int(len(scenario)),
                "current_count": int(len(current_rows)),
                "current_singleton_count": int(len(current_singleton)),
            }
            row.update(row_stats(current_rows, prefix="current"))
            row.update(row_stats(current_singleton, prefix="current_singleton"))
            row.update(row_stats(flagged_current, prefix="flagged_current"))
            rows.append(row)
    return pd.DataFrame(rows)


def build_surface(
    *,
    additions: pd.DataFrame,
    rejections: pd.DataFrame,
    scenario_labels: list[str],
    include_reject_reasons: list[str],
    quota_columns: list[str],
    overlap_columns: list[str],
    cluster_columns: list[str],
    cluster_gap_minutes: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    frames: list[pd.DataFrame] = []
    skipped: list[dict[str, str]] = []
    for scenario_label in scenario_labels:
        try:
            universe = prepare_stateful_universe(
                additions,
                rejections,
                scenario_label=scenario_label,
                include_reject_reasons=include_reject_reasons,
            )
            universe = assign_interval_clusters(
                universe,
                cluster_columns=cluster_columns,
                cluster_gap_minutes=cluster_gap_minutes,
            )
            universe = add_selector_flags(
                universe,
                quota_columns=quota_columns,
                overlap_columns=overlap_columns,
            )
            universe = add_rank_columns(universe, quota_columns=quota_columns)
            universe = add_singleton_surface_columns(universe, quota_columns=quota_columns)
            frames.append(universe)
        except Exception as exc:  # pragma: no cover - reported as diagnostic artifact
            skipped.append({"scenario_label": scenario_label, "reason": str(exc)})
    if not frames:
        raise ValueError("no singleton surface rows could be built")
    return (
        pd.concat(frames, ignore_index=True, sort=False),
        pd.DataFrame(skipped),
    )


def flagged_rows(frame: pd.DataFrame, *, rules: list[str]) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for rule in rules:
        flags = rule_mask(frame, rule)
        if flags.any():
            flagged = frame[flags].copy()
            flagged["abstention_rule"] = rule
            frames.append(flagged)
    return pd.concat(frames, ignore_index=True, sort=False) if frames else pd.DataFrame()


def run_diagnostics(args: argparse.Namespace) -> Path:
    additions = pd.read_csv(args.additions)
    rejections = pd.read_csv(args.rejections) if args.rejections else pd.DataFrame()
    summary = pd.read_csv(args.summary)
    quota_columns = parse_csv(args.quota_columns)
    overlap_columns = parse_csv(args.overlap_columns)
    cluster_columns = parse_csv(args.cluster_columns)
    rules = parse_csv(args.rules)
    labels = scenario_labels_from_summary(
        summary,
        scenario_labels=args.scenario_labels,
        row_scopes=args.summary_row_scopes,
        max_scenarios=args.max_scenarios,
    )
    surface, skipped = build_surface(
        additions=additions,
        rejections=rejections,
        scenario_labels=labels,
        include_reject_reasons=parse_csv(args.include_reject_reasons),
        quota_columns=quota_columns,
        overlap_columns=overlap_columns,
        cluster_columns=cluster_columns,
        cluster_gap_minutes=args.cluster_gap_minutes,
    )
    rule_summary = surface_rule_summary(surface, rules=rules)
    per_scenario = scenario_rule_summary(surface, rules=rules)
    flagged = flagged_rows(surface, rules=rules)
    unique_singleton = unique_rows(surface[bool_series(surface, "quota_group_is_singleton")])

    run_dir = make_run_dir(args.output_dir, args.label)
    rule_summary.to_csv(run_dir / "singleton_surface_rule_summary.csv", index=False)
    per_scenario.to_csv(run_dir / "singleton_surface_scenario_rule_summary.csv", index=False)
    flagged.to_csv(run_dir / "singleton_surface_flagged_rows.csv", index=False)
    unique_singleton.to_csv(run_dir / "singleton_surface_unique_singletons.csv", index=False)
    skipped.to_csv(run_dir / "singleton_surface_skipped_scenarios.csv", index=False)
    (run_dir / "config.json").write_text(
        json.dumps(
            {
                "additions": args.additions,
                "rejections": args.rejections,
                "summary": args.summary,
                "scenario_labels": labels,
                "summary_row_scopes": parse_csv(args.summary_row_scopes),
                "include_reject_reasons": parse_csv(args.include_reject_reasons),
                "quota_columns": quota_columns,
                "overlap_columns": overlap_columns,
                "cluster_columns": cluster_columns,
                "cluster_gap_minutes": args.cluster_gap_minutes,
                "rules": rules,
                "max_scenarios": args.max_scenarios,
            },
            indent=2,
            sort_keys=True,
            default=local_json_default,
        )
        + "\n",
        encoding="utf-8",
    )

    print("Singleton surface diagnostics:")
    print(rule_summary.to_string(index=False))
    if not skipped.empty:
        print("Skipped scenarios:")
        print(skipped.to_string(index=False))
    print(f"artifacts: {run_dir}")
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--additions", type=Path, required=True)
    parser.add_argument("--rejections", type=Path)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--scenario-labels", default="")
    parser.add_argument("--summary-row-scopes", default="available_candidates,greedy_selected")
    parser.add_argument("--max-scenarios", type=int, default=0)
    parser.add_argument("--include-reject-reasons", default=DEFAULT_INCLUDE_REJECT_REASONS)
    parser.add_argument("--quota-columns", default=DEFAULT_QUOTA_COLUMNS)
    parser.add_argument("--overlap-columns", default=DEFAULT_OVERLAP_COLUMNS)
    parser.add_argument("--cluster-columns", default=DEFAULT_CLUSTER_COLUMNS)
    parser.add_argument("--cluster-gap-minutes", type=float, default=0.0)
    parser.add_argument("--rules", default=DEFAULT_RULES)
    parser.add_argument("--output-dir", type=Path, default=Path("data/reports/backtests"))
    parser.add_argument("--label", default="entry_ev_support_repair_singleton_surface")
    return parser


def main(argv: list[str] | None = None) -> int:
    run_diagnostics(build_parser().parse_args(argv))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
