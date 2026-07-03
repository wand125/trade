#!/usr/bin/env python3
"""Diagnose tail-pass positive-PnL failures near the actual selector boundary."""

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

from entry_ev_contextual_penalty_near_selected_diagnostics import (  # noqa: E402
    DEFAULT_QUOTA_COLUMNS,
    DEFAULT_RANK_SPECS,
    add_selection_rank_columns,
    attach_selection_outcomes,
    load_candidate_files,
    load_rejection_rows,
    normalize_replay_rows,
    parse_score_specs,
    resolve_candidate_paths,
)
from entry_ev_near_miss_exit_head import bool_series, numeric_series, parse_csv, text_series  # noqa: E402
from entry_ev_positive_pnl_failure_diagnostics import (  # noqa: E402
    DEFAULT_RULES,
    add_chosen_wide_columns,
    rule_masks,
)


DEFAULT_GROUP_COLUMNS = (
    "positive_pnl_penalty_label,"
    "ranker_score_mode,"
    "ranker_abstention_rule,"
    "row_scope"
)
DEFAULT_FOCUS_SCOPES = (
    "all_tail_pass_positive,"
    "selected_addition,"
    "near_selected_boundary,"
    "within_quota,"
    "quota_or_near"
)
DEFAULT_DEDUP_MODES = "row_weighted,candidate_identity_key"
CASE_COLUMNS = [
    "candidate_file",
    "positive_pnl_penalty_label",
    "ranker_score_mode",
    "ranker_abstention_rule",
    "role",
    "month",
    "side",
    "row_scope",
    "selection_outcome",
    "selected_addition",
    "decision_timestamp",
    "entry_timestamp",
    "exit_timestamp",
    "hv_chosen_horizon_minutes",
    "quota_rank",
    "group_quota",
    "selected_boundary_rank",
    "rank_vs_selected_boundary",
    "repair_score",
    "selected_score_floor",
    "score_gap_to_selected_floor",
    "support_reduction_value",
    "repair_expected_pnl",
    "hv_chosen_pred_pnl",
    "actual_pnl_at_hv_chosen_horizon",
    "positive_pred_overestimate",
    "hv_chosen_pred_tail_loss_prob",
    "hv_chosen_pred_harmful_overestimate_prob",
    "chosen_prior_mean_pnl",
    "chosen_prior_tail_loss_rate",
    "chosen_prior_risk_score",
    "chosen_residual_bias",
    "chosen_residual_mae",
    "chosen_residual_overestimate_rate",
    "chosen_residual_tail_miss_rate",
    "chosen_tail_reliability",
    "chosen_tail_reliability_used",
    "chosen_pnl_model_used",
    "combined_regime",
    "session_regime",
    "near_miss_bucket",
    "prob_threshold",
    "ev_threshold",
    "tail_prob_threshold",
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


def filter_penalty_labels(frame: pd.DataFrame, labels: list[str]) -> pd.DataFrame:
    if not labels:
        return frame.copy()
    label_series = text_series(frame, "positive_pnl_penalty_label", default="none")
    return frame[label_series.isin(labels)].copy()


def add_tail_residual_columns(frame: pd.DataFrame, *, max_tail_prob: float) -> pd.DataFrame:
    output = add_chosen_wide_columns(frame.copy())
    pred = numeric_series(output, "hv_chosen_pred_pnl", default=0.0)
    actual = numeric_series(output, "actual_pnl_at_hv_chosen_horizon", default=0.0)
    tail_prob = numeric_series(output, "hv_chosen_pred_tail_loss_prob", default=np.inf)
    selected = bool_series(output, "selected_addition", default=False)
    near_boundary = bool_series(output, "near_selected_boundary", default=False)
    within_quota = bool_series(output, "within_quota", default=False)

    output["tail_ceiling_max_prob"] = float(max_tail_prob)
    output["predicted_positive_pnl"] = pred.gt(0.0)
    output["realized_loss"] = actual.lt(0.0)
    output["realized_win"] = actual.gt(0.0)
    output["positive_pred_overestimate"] = pred - actual
    output["tail_ceiling_pass"] = tail_prob.le(float(max_tail_prob))
    output["tail_ceiling_blocked"] = tail_prob.gt(float(max_tail_prob))
    output["tail_pass_positive"] = (
        output["predicted_positive_pnl"] & output["tail_ceiling_pass"]
    )
    output["tail_pass_positive_loss"] = output["tail_pass_positive"] & output["realized_loss"]
    output["tail_pass_positive_win"] = output["tail_pass_positive"] & output["realized_win"]
    output["tail_pass_positive_selected"] = output["tail_pass_positive"] & selected
    output["tail_pass_positive_near_selected"] = output["tail_pass_positive"] & near_boundary
    output["tail_pass_positive_within_quota"] = output["tail_pass_positive"] & within_quota
    output["tail_pass_positive_quota_or_near"] = (
        output["tail_pass_positive"] & (within_quota | near_boundary)
    )
    return output


def focus_mask(frame: pd.DataFrame, scope: str) -> pd.Series:
    tail_pass = bool_series(frame, "tail_pass_positive", default=False)
    if scope == "all_tail_pass_positive":
        return tail_pass
    if scope == "selected_addition":
        return tail_pass & bool_series(frame, "selected_addition", default=False)
    if scope == "near_selected_boundary":
        return tail_pass & bool_series(frame, "near_selected_boundary", default=False)
    if scope == "within_quota":
        return tail_pass & bool_series(frame, "within_quota", default=False)
    if scope == "quota_or_near":
        return tail_pass & (
            bool_series(frame, "within_quota", default=False)
            | bool_series(frame, "near_selected_boundary", default=False)
        )
    raise ValueError(f"unknown focus scope: {scope}")


def deduplicate_frame(frame: pd.DataFrame, mode: str) -> pd.DataFrame:
    if mode == "row_weighted":
        return frame.copy()
    if mode == "candidate_identity_key":
        return frame.drop_duplicates("candidate_identity_key").copy()
    raise ValueError(f"unknown dedup mode: {mode}")


def summarize_mask(frame: pd.DataFrame, mask: pd.Series, *, prefix: str) -> dict[str, Any]:
    scoped = mask.fillna(False).astype(bool)
    actual = numeric_series(frame, "actual_pnl_at_hv_chosen_horizon", default=0.0)
    pred = numeric_series(frame, "hv_chosen_pred_pnl", default=0.0)
    selected = bool_series(frame, "selected_addition", default=False)
    near_boundary = bool_series(frame, "near_selected_boundary", default=False)
    within_quota = bool_series(frame, "within_quota", default=False)
    losses = bool_series(frame, "realized_loss", default=False)
    wins = bool_series(frame, "realized_win", default=False)
    large_losses = actual.le(-5.0)
    return {
        f"{prefix}count": int(scoped.sum()),
        f"{prefix}actual_pnl_sum": float(actual.where(scoped, 0.0).sum()),
        f"{prefix}mean_pred_pnl": float(pred.where(scoped).mean()) if scoped.any() else 0.0,
        f"{prefix}loss_count": int((scoped & losses).sum()),
        f"{prefix}loss_rate": float((scoped & losses).sum() / scoped.sum())
        if scoped.any()
        else 0.0,
        f"{prefix}loss_pnl": float(actual.where(scoped & losses, 0.0).sum()),
        f"{prefix}large_loss_count": int((scoped & large_losses).sum()),
        f"{prefix}large_loss_pnl": float(actual.where(scoped & large_losses, 0.0).sum()),
        f"{prefix}win_count": int((scoped & wins).sum()),
        f"{prefix}win_pnl": float(actual.where(scoped & wins, 0.0).sum()),
        f"{prefix}selected_count": int((scoped & selected).sum()),
        f"{prefix}selected_pnl": float(actual.where(scoped & selected, 0.0).sum()),
        f"{prefix}near_selected_count": int((scoped & near_boundary).sum()),
        f"{prefix}near_selected_pnl": float(actual.where(scoped & near_boundary, 0.0).sum()),
        f"{prefix}within_quota_count": int((scoped & within_quota).sum()),
        f"{prefix}within_quota_pnl": float(actual.where(scoped & within_quota, 0.0).sum()),
    }


def overall_summary(
    frame: pd.DataFrame,
    *,
    group_columns: list[str],
    focus_scopes: list[str],
    dedup_mode: str = "row_weighted",
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    group_columns = [column for column in group_columns if column in frame.columns]

    def build_row(group: pd.DataFrame, scope_name: str, extras: dict[str, Any]) -> dict[str, Any]:
        row = {
            "dedup_mode": dedup_mode,
            "summary_scope": scope_name,
            "row_count": int(len(group)),
            "candidate_identity_count": int(group["candidate_identity_key"].nunique())
            if len(group)
            else 0,
            "selected_count": int(bool_series(group, "selected_addition").sum()),
            "selected_actual_pnl_sum": float(
                numeric_series(group, "actual_pnl_at_hv_chosen_horizon").where(
                    bool_series(group, "selected_addition"),
                    0.0,
                ).sum()
            ),
        }
        for scope in focus_scopes:
            row.update(summarize_mask(group, focus_mask(group, scope), prefix=f"{scope}_"))
        row.update(extras)
        return row

    rows.append(build_row(frame, "overall", {}))
    for keys, group in frame.groupby(group_columns, dropna=False, sort=True):
        key_values = keys if isinstance(keys, tuple) else (keys,)
        rows.append(
            build_row(
                group,
                "group",
                dict(zip(group_columns, key_values, strict=True)),
            )
        )
    return pd.DataFrame(rows)


def selection_outcome_summary(
    frame: pd.DataFrame,
    *,
    dedup_mode: str = "row_weighted",
) -> pd.DataFrame:
    focus = bool_series(frame, "tail_pass_positive", default=False)
    scoped = frame[focus].copy()
    if scoped.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    group_columns = ["selection_outcome", "row_scope"]
    for keys, group in scoped.groupby(group_columns, dropna=False, sort=True):
        key_values = keys if isinstance(keys, tuple) else (keys,)
        row = {"dedup_mode": dedup_mode}
        row.update(dict(zip(group_columns, key_values, strict=True)))
        row.update(summarize_mask(group, pd.Series(True, index=group.index), prefix="tail_pass_"))
        rows.append(row)
    return pd.DataFrame(rows).sort_values(
        ["tail_pass_loss_pnl", "tail_pass_actual_pnl_sum"],
        ascending=[True, True],
    ).reset_index(drop=True)


def quota_group_summary(frame: pd.DataFrame, *, quota_columns: list[str]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    tail_failures = bool_series(frame, "tail_pass_positive_loss", default=False)
    for keys, group in frame.groupby(quota_columns, dropna=False, sort=False):
        failures = group[tail_failures.reindex(group.index).fillna(False)].copy()
        if failures.empty:
            continue
        key_values = keys if isinstance(keys, tuple) else (keys,)
        row = dict(zip(quota_columns, key_values, strict=True))
        for column in [
            "positive_pnl_penalty_label",
            "ranker_score_mode",
            "ranker_abstention_rule",
            "role",
            "month",
            "side",
            "row_scope",
            "combined_regime",
            "session_regime",
            "near_miss_bucket",
        ]:
            if column in group.columns and column not in row:
                row[column] = group[column].iloc[0]
        row.update(
            {
                "group_row_count": int(len(group)),
                "group_quota": int(numeric_series(group, "group_quota").max()),
                "selected_count": int(bool_series(group, "selected_addition").sum()),
                "selected_pnl": float(
                    numeric_series(group, "actual_pnl_at_hv_chosen_horizon").where(
                        bool_series(group, "selected_addition"),
                        0.0,
                    ).sum()
                ),
            }
        )
        row.update(summarize_mask(group, tail_failures.reindex(group.index), prefix="failure_"))
        ordered = failures.sort_values(
            [
                "selected_addition",
                "rank_vs_selected_boundary",
                "quota_rank",
                "actual_pnl_at_hv_chosen_horizon",
            ],
            ascending=[False, True, True, True],
        )
        best = ordered.iloc[0]
        row.update(
            {
                "best_failure_selected": bool(best["selected_addition"]),
                "best_failure_outcome": best["selection_outcome"],
                "best_failure_rank": int(best["quota_rank"]),
                "best_failure_rank_gap": float(best["rank_vs_selected_boundary"]),
                "best_failure_repair_score": float(best["repair_score"]),
                "best_failure_score_gap_to_selected_floor": float(
                    best["score_gap_to_selected_floor"]
                )
                if pd.notna(best["score_gap_to_selected_floor"])
                else np.nan,
                "best_failure_pred_pnl": float(best["hv_chosen_pred_pnl"]),
                "best_failure_actual_pnl": float(best["actual_pnl_at_hv_chosen_horizon"]),
                "best_failure_tail_prob": float(best["hv_chosen_pred_tail_loss_prob"]),
                "best_failure_horizon_minutes": int(best["hv_chosen_horizon_minutes"]),
            }
        )
        rows.append(row)
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(
        [
            "failure_selected_count",
            "failure_near_selected_count",
            "failure_actual_pnl_sum",
            "best_failure_rank_gap",
        ],
        ascending=[False, False, True, True],
    ).reset_index(drop=True)


def scoped_rule_summary(
    frame: pd.DataFrame,
    *,
    rules: list[str],
    focus_scopes: list[str],
    dedup_mode: str = "row_weighted",
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    actual = numeric_series(frame, "actual_pnl_at_hv_chosen_horizon", default=0.0)
    failures = bool_series(frame, "tail_pass_positive_loss", default=False)
    wins = bool_series(frame, "tail_pass_positive_win", default=False)
    for scope in focus_scopes:
        scoped_mask = focus_mask(frame, scope)
        scoped = frame[scoped_mask].copy()
        if scoped.empty:
            continue
        scoped_actual = actual.reindex(scoped.index)
        scoped_failures = failures.reindex(scoped.index).fillna(False)
        scoped_wins = wins.reindex(scoped.index).fillna(False)
        for rule, mask in rule_masks(scoped, rules):
            flagged = mask.reindex(scoped.index).fillna(False).astype(bool)
            flagged_failure = flagged & scoped_failures
            flagged_win = flagged & scoped_wins
            rows.append(
                {
                    "dedup_mode": dedup_mode,
                    "focus_scope": scope,
                    "rule": rule,
                    "evaluated_count": int(len(scoped)),
                    "evaluated_actual_pnl_sum": float(scoped_actual.sum()),
                    "failure_count": int(scoped_failures.sum()),
                    "failure_pnl": float(scoped_actual.where(scoped_failures, 0.0).sum()),
                    "win_count": int(scoped_wins.sum()),
                    "win_pnl": float(scoped_actual.where(scoped_wins, 0.0).sum()),
                    "flagged_count": int(flagged.sum()),
                    "flagged_actual_pnl_sum": float(scoped_actual.where(flagged, 0.0).sum()),
                    "kept_actual_pnl_sum": float(scoped_actual.where(~flagged, 0.0).sum()),
                    "flagged_failure_count": int(flagged_failure.sum()),
                    "flagged_failure_pnl": float(
                        scoped_actual.where(flagged_failure, 0.0).sum()
                    ),
                    "failure_precision": float(flagged_failure.sum() / flagged.sum())
                    if int(flagged.sum())
                    else 0.0,
                    "failure_recall": float(flagged_failure.sum() / scoped_failures.sum())
                    if int(scoped_failures.sum())
                    else 0.0,
                    "flagged_win_count": int(flagged_win.sum()),
                    "flagged_win_pnl": float(scoped_actual.where(flagged_win, 0.0).sum()),
                }
            )
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(
        ["focus_scope", "flagged_actual_pnl_sum", "flagged_failure_pnl"],
        ascending=[True, True, True],
    ).reset_index(drop=True)


def failure_cases(frame: pd.DataFrame, *, limit: int) -> pd.DataFrame:
    failures = frame[bool_series(frame, "tail_pass_positive_loss", default=False)].copy()
    columns = [column for column in CASE_COLUMNS if column in failures.columns]
    if failures.empty:
        return pd.DataFrame(columns=columns)
    return failures.sort_values(
        [
            "selected_addition",
            "near_selected_boundary",
            "within_quota",
            "rank_vs_selected_boundary",
            "quota_rank",
            "actual_pnl_at_hv_chosen_horizon",
        ],
        ascending=[False, False, False, True, True, True],
    )[columns].head(limit).reset_index(drop=True)


def run_diagnostics(args: argparse.Namespace) -> Path:
    candidate_paths = resolve_candidate_paths(args)
    candidates = normalize_replay_rows(load_candidate_files(candidate_paths))
    candidates = filter_penalty_labels(candidates, parse_csv(args.positive_pnl_penalty_labels))
    additions = pd.read_csv(args.additions)
    rejections = load_rejection_rows(args.rejections) if args.rejections else None
    attached = attach_selection_outcomes(candidates, additions, rejections)
    ranked = add_selection_rank_columns(
        attached,
        quota_columns=parse_csv(args.quota_columns),
        rank_specs=parse_score_specs(args.rank_specs),
        near_rank_window=args.near_rank_window,
    )
    enriched = add_tail_residual_columns(ranked, max_tail_prob=args.max_tail_prob)
    group_columns = parse_csv(args.group_columns)
    focus_scopes = parse_csv(args.focus_scopes)
    rules = parse_csv(args.rules)
    dedup_modes = parse_csv(args.dedup_modes)

    overall_frames: list[pd.DataFrame] = []
    outcome_frames: list[pd.DataFrame] = []
    rule_frames: list[pd.DataFrame] = []
    for dedup_mode in dedup_modes:
        deduped = deduplicate_frame(enriched, dedup_mode)
        overall_frames.append(
            overall_summary(
                deduped,
                group_columns=group_columns,
                focus_scopes=focus_scopes,
                dedup_mode=dedup_mode,
            )
        )
        outcome = selection_outcome_summary(deduped, dedup_mode=dedup_mode)
        if not outcome.empty:
            outcome_frames.append(outcome)
        rules_for_mode = scoped_rule_summary(
            deduped,
            rules=rules,
            focus_scopes=focus_scopes,
            dedup_mode=dedup_mode,
        )
        if not rules_for_mode.empty:
            rule_frames.append(rules_for_mode)
    overall = pd.concat(overall_frames, ignore_index=True, sort=False)
    outcomes = (
        pd.concat(outcome_frames, ignore_index=True, sort=False)
        if outcome_frames
        else pd.DataFrame()
    )
    groups = quota_group_summary(enriched, quota_columns=parse_csv(args.quota_columns))
    rules_frame = (
        pd.concat(rule_frames, ignore_index=True, sort=False)
        if rule_frames
        else pd.DataFrame()
    )
    cases = failure_cases(enriched, limit=args.case_limit)
    unique_cases = failure_cases(
        deduplicate_frame(enriched, "candidate_identity_key"),
        limit=args.case_limit,
    )

    run_dir = make_run_dir(args.output_dir, args.label)
    overall.to_csv(run_dir / "tail_selected_residual_overall_summary.csv", index=False)
    outcomes.to_csv(run_dir / "tail_selected_residual_outcome_summary.csv", index=False)
    groups.to_csv(run_dir / "tail_selected_residual_group_summary.csv", index=False)
    rules_frame.to_csv(run_dir / "tail_selected_residual_rule_summary.csv", index=False)
    cases.to_csv(run_dir / "tail_selected_residual_cases.csv", index=False)
    unique_cases.to_csv(run_dir / "tail_selected_residual_unique_cases.csv", index=False)
    enriched[bool_series(enriched, "tail_pass_positive_loss", default=False)].to_csv(
        run_dir / "tail_selected_residual_failure_rows.csv",
        index=False,
    )
    (run_dir / "config.json").write_text(
        json.dumps(
            {
                "candidate_files": [str(path) for path in candidate_paths],
                "additions": str(args.additions),
                "rejections": str(args.rejections) if args.rejections else None,
                "positive_pnl_penalty_labels": parse_csv(args.positive_pnl_penalty_labels),
                "max_tail_prob": args.max_tail_prob,
                "quota_columns": parse_csv(args.quota_columns),
                "rank_specs": [
                    (column, "asc" if ascending else "desc")
                    for column, ascending in parse_score_specs(args.rank_specs)
                ],
                "near_rank_window": args.near_rank_window,
                "group_columns": group_columns,
                "focus_scopes": focus_scopes,
                "dedup_modes": dedup_modes,
                "rules": rules,
                "case_limit": args.case_limit,
            },
            indent=2,
            sort_keys=True,
            default=local_json_default,
        )
        + "\n",
        encoding="utf-8",
    )

    print("Tail selected residual overall summary:")
    print(overall.head(args.print_rows).to_string(index=False))
    if not outcomes.empty:
        print("\nSelection outcome summary:")
        print(outcomes.head(args.print_rows).to_string(index=False))
    if not groups.empty:
        print("\nQuota group summary:")
        print(groups.head(args.print_rows).to_string(index=False))
    if not rules_frame.empty:
        print("\nScoped rule summary:")
        print(rules_frame.head(args.print_rows).to_string(index=False))
    print("\nResidual failure cases:")
    print(cases.head(args.print_rows).to_string(index=False))
    print(f"artifacts: {run_dir}")
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-files", nargs="*", default=[])
    parser.add_argument("--candidate-glob", action="append", default=[])
    parser.add_argument("--additions", type=Path, required=True)
    parser.add_argument("--rejections", type=Path)
    parser.add_argument("--positive-pnl-penalty-labels", default="none")
    parser.add_argument("--max-tail-prob", type=float, default=0.3)
    parser.add_argument("--quota-columns", default=DEFAULT_QUOTA_COLUMNS)
    parser.add_argument("--rank-specs", default=DEFAULT_RANK_SPECS)
    parser.add_argument("--near-rank-window", type=int, default=3)
    parser.add_argument("--group-columns", default=DEFAULT_GROUP_COLUMNS)
    parser.add_argument("--focus-scopes", default=DEFAULT_FOCUS_SCOPES)
    parser.add_argument("--dedup-modes", default=DEFAULT_DEDUP_MODES)
    parser.add_argument("--rules", default=DEFAULT_RULES)
    parser.add_argument("--case-limit", type=int, default=500)
    parser.add_argument("--output-dir", type=Path, default=Path("data/reports/backtests"))
    parser.add_argument(
        "--label",
        default="entry_ev_tail_selected_residual_diagnostics",
    )
    parser.add_argument("--print-rows", type=int, default=20)
    return parser


def main(argv: list[str] | None = None) -> int:
    run_diagnostics(build_parser().parse_args(argv))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
