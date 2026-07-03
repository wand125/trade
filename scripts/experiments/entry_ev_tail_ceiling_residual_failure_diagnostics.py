#!/usr/bin/env python3
"""Diagnose positive-PnL failures that remain after the tail ceiling filter."""

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

from entry_ev_near_miss_exit_head import bool_series, numeric_series, parse_csv, text_series  # noqa: E402
from entry_ev_positive_pnl_failure_diagnostics import (  # noqa: E402
    CONTEXT_COLUMNS,
    deduplicate_candidates,
    load_candidate_files,
    normalize_candidates,
    rule_summary,
    top_failure_cases,
)


DEFAULT_RESIDUAL_RULES = (
    "harmful_prob_ge_0p30,"
    "harmful_prob_ge_0p50,"
    "pred_pnl_lt_1,"
    "pred_pnl_lt_2,"
    "pred_pnl_lt_5,"
    "horizon_720m,"
    "prior_mean_lt_0,"
    "prior_tail_ge_0p30,"
    "prior_risk_ge_5,"
    "residual_mae_ge_10,"
    "residual_bias_gt_0,"
    "residual_bias_ge_2,"
    "residual_overestimate_ge_0p60,"
    "residual_tail_miss_ge_0p10,"
    "tail_reliability_not_used,"
    "model_not_used,"
    "positive_bias_and_tail_miss_ge_0p10"
)
DEFAULT_GROUP_COLUMNS = (
    "positive_pnl_penalty_label,"
    "ranker_score_mode,"
    "ranker_abstention_rule,"
    "row_scope"
)
CASE_COLUMNS = [
    "candidate_file",
    "positive_pnl_penalty_label",
    "ranker_score_mode",
    "ranker_abstention_rule",
    "role",
    "month",
    "side",
    "row_scope",
    "decision_timestamp",
    "hv_chosen_horizon_minutes",
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


def resolve_candidate_paths(args: argparse.Namespace) -> list[Path]:
    paths = [Path(path) for path in args.candidate_files]
    for pattern in args.candidate_glob:
        paths.extend(sorted(Path().glob(pattern)))
    paths = sorted({path for path in paths})
    if not paths:
        raise ValueError("no candidate files matched")
    missing = [path for path in paths if not path.exists()]
    if missing:
        raise FileNotFoundError("missing candidate files: " + ", ".join(map(str, missing)))
    return paths


def add_penalty_label(frame: pd.DataFrame) -> pd.DataFrame:
    output = frame.copy()
    output["positive_pnl_penalty_label"] = text_series(
        output,
        "positive_pnl_penalty_label",
        default="none",
    )
    output["positive_pnl_gate_rule"] = text_series(
        output,
        "positive_pnl_gate_rule",
        default="none",
    )
    return output


def filter_penalty_labels(frame: pd.DataFrame, labels: list[str]) -> pd.DataFrame:
    if not labels:
        return frame.copy()
    return frame[frame["positive_pnl_penalty_label"].isin(labels)].copy()


def add_tail_ceiling_columns(frame: pd.DataFrame, *, max_tail_prob: float) -> pd.DataFrame:
    output = add_penalty_label(frame)
    tail_prob = numeric_series(output, "hv_chosen_pred_tail_loss_prob", default=np.inf)
    positive = bool_series(output, "predicted_positive_pnl", default=False)
    realized_loss = bool_series(output, "realized_loss", default=False)
    realized_win = bool_series(output, "realized_win", default=False)
    actual = numeric_series(output, "actual_pnl_at_hv_chosen_horizon", default=0.0)
    output["tail_ceiling_max_prob"] = float(max_tail_prob)
    output["tail_ceiling_pass"] = tail_prob.le(float(max_tail_prob))
    output["tail_ceiling_blocked"] = tail_prob.gt(float(max_tail_prob))
    output["tail_pass_positive"] = positive & output["tail_ceiling_pass"]
    output["tail_blocked_positive"] = positive & output["tail_ceiling_blocked"]
    output["tail_pass_positive_loss"] = output["tail_pass_positive"] & realized_loss
    output["tail_pass_positive_win"] = output["tail_pass_positive"] & realized_win
    output["tail_pass_positive_large_loss"] = (
        output["tail_pass_positive"] & actual.le(-5.0)
    )
    output["tail_blocked_positive_loss"] = output["tail_blocked_positive"] & realized_loss
    output["tail_blocked_positive_win"] = output["tail_blocked_positive"] & realized_win
    output["tail_blocked_positive_large_loss"] = (
        output["tail_blocked_positive"] & actual.le(-5.0)
    )
    return output


def summarize_tail_scope(frame: pd.DataFrame, *, scope: str) -> dict[str, Any]:
    actual = numeric_series(frame, "actual_pnl_at_hv_chosen_horizon", default=0.0)
    pred = numeric_series(frame, "hv_chosen_pred_pnl", default=0.0)
    positive = bool_series(frame, "predicted_positive_pnl", default=False)
    pass_positive = bool_series(frame, "tail_pass_positive", default=False)
    pass_loss = bool_series(frame, "tail_pass_positive_loss", default=False)
    pass_win = bool_series(frame, "tail_pass_positive_win", default=False)
    pass_large_loss = bool_series(frame, "tail_pass_positive_large_loss", default=False)
    blocked_positive = bool_series(frame, "tail_blocked_positive", default=False)
    blocked_loss = bool_series(frame, "tail_blocked_positive_loss", default=False)
    blocked_win = bool_series(frame, "tail_blocked_positive_win", default=False)
    blocked_large_loss = bool_series(
        frame,
        "tail_blocked_positive_large_loss",
        default=False,
    )
    return {
        "scope": scope,
        "row_count": int(len(frame)),
        "decision_count": int(frame["decision_key"].nunique()) if len(frame) else 0,
        "positive_pred_count": int(positive.sum()),
        "positive_pred_actual_pnl_sum": float(actual.where(positive, 0.0).sum()),
        "tail_pass_positive_count": int(pass_positive.sum()),
        "tail_pass_positive_actual_pnl_sum": float(actual.where(pass_positive, 0.0).sum()),
        "tail_pass_positive_mean_pred_pnl": float(pred.where(pass_positive).mean())
        if pass_positive.any()
        else 0.0,
        "tail_pass_positive_loss_count": int(pass_loss.sum()),
        "tail_pass_positive_loss_rate": float(pass_loss.sum() / pass_positive.sum())
        if pass_positive.any()
        else 0.0,
        "tail_pass_positive_loss_pnl": float(actual.where(pass_loss, 0.0).sum()),
        "tail_pass_positive_large_loss_count": int(pass_large_loss.sum()),
        "tail_pass_positive_large_loss_pnl": float(
            actual.where(pass_large_loss, 0.0).sum()
        ),
        "tail_pass_positive_win_count": int(pass_win.sum()),
        "tail_pass_positive_win_pnl": float(actual.where(pass_win, 0.0).sum()),
        "tail_blocked_positive_count": int(blocked_positive.sum()),
        "tail_blocked_positive_actual_pnl_sum": float(
            actual.where(blocked_positive, 0.0).sum()
        ),
        "tail_blocked_positive_loss_count": int(blocked_loss.sum()),
        "tail_blocked_positive_loss_rate": float(blocked_loss.sum() / blocked_positive.sum())
        if blocked_positive.any()
        else 0.0,
        "tail_blocked_positive_loss_pnl": float(actual.where(blocked_loss, 0.0).sum()),
        "tail_blocked_positive_large_loss_count": int(blocked_large_loss.sum()),
        "tail_blocked_positive_large_loss_pnl": float(
            actual.where(blocked_large_loss, 0.0).sum()
        ),
        "tail_blocked_positive_win_count": int(blocked_win.sum()),
        "tail_blocked_positive_win_pnl": float(actual.where(blocked_win, 0.0).sum()),
    }


def tail_ceiling_summary(
    frame: pd.DataFrame,
    *,
    dedup_modes: list[str],
    group_columns: list[str],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    group_columns = [column for column in group_columns if column in frame.columns]
    for mode in dedup_modes:
        deduped = deduplicate_candidates(frame, mode)
        rows.append(summarize_tail_scope(deduped, scope=mode))
        for keys, group in deduped.groupby(group_columns, dropna=False, sort=True):
            key_values = keys if isinstance(keys, tuple) else (keys,)
            row = summarize_tail_scope(group, scope=mode)
            row.update(dict(zip(group_columns, key_values, strict=True)))
            rows.append(row)
    return pd.DataFrame(rows)


def tail_pass_context_summary(frame: pd.DataFrame, *, dedup_mode: str) -> pd.DataFrame:
    deduped = deduplicate_candidates(frame, dedup_mode)
    pass_positive = bool_series(deduped, "tail_pass_positive", default=False)
    scoped = deduped[pass_positive].copy()
    if scoped.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    columns = [
        "positive_pnl_penalty_label",
        *[column for column in CONTEXT_COLUMNS if column in scoped.columns],
    ]
    for keys, group in scoped.groupby(columns, dropna=False, sort=True):
        key_values = keys if isinstance(keys, tuple) else (keys,)
        row = summarize_tail_scope(group, scope=dedup_mode)
        row.update(dict(zip(columns, key_values, strict=True)))
        rows.append(row)
    return pd.DataFrame(rows).sort_values(
        [
            "tail_pass_positive_loss_pnl",
            "tail_pass_positive_large_loss_pnl",
            "tail_pass_positive_win_pnl",
        ],
        ascending=[True, True, True],
    ).reset_index(drop=True)


def tail_pass_failure_cases(
    frame: pd.DataFrame,
    *,
    dedup_mode: str,
    limit: int,
) -> pd.DataFrame:
    deduped = deduplicate_candidates(frame, dedup_mode)
    failures = deduped[bool_series(deduped, "tail_pass_positive_loss", default=False)].copy()
    columns = [column for column in CASE_COLUMNS if column in failures.columns]
    if failures.empty:
        return pd.DataFrame(columns=columns)
    return failures.sort_values(
        ["actual_pnl_at_hv_chosen_horizon", "positive_pred_overestimate"],
        ascending=[True, False],
    )[columns].head(limit).reset_index(drop=True)


def run_diagnostics(args: argparse.Namespace) -> Path:
    candidate_paths = resolve_candidate_paths(args)
    candidates = normalize_candidates(load_candidate_files(candidate_paths))
    candidates = add_tail_ceiling_columns(candidates, max_tail_prob=args.max_tail_prob)
    candidates = filter_penalty_labels(candidates, parse_csv(args.positive_pnl_penalty_labels))
    dedup_modes = parse_csv(args.dedup_modes)
    group_columns = parse_csv(args.group_columns)
    rules = parse_csv(args.rules)

    overall = tail_ceiling_summary(
        candidates,
        dedup_modes=dedup_modes,
        group_columns=group_columns,
    )
    context = tail_pass_context_summary(candidates, dedup_mode=args.context_dedup_mode)
    pass_candidates = candidates[
        bool_series(candidates, "tail_pass_positive", default=False)
    ].copy()
    rule_frames = [
        rule_summary(pass_candidates, rules=rules, dedup_mode=mode)
        for mode in dedup_modes
    ]
    rule_summaries = pd.concat(
        [frame for frame in rule_frames if not frame.empty],
        ignore_index=True,
        sort=False,
    ) if any(not frame.empty for frame in rule_frames) else pd.DataFrame()
    cases = tail_pass_failure_cases(
        candidates,
        dedup_mode=args.case_dedup_mode,
        limit=args.case_limit,
    )

    run_dir = make_run_dir(args.output_dir, args.label)
    overall.to_csv(run_dir / "tail_ceiling_residual_overall_summary.csv", index=False)
    context.to_csv(run_dir / "tail_ceiling_residual_context_summary.csv", index=False)
    rule_summaries.to_csv(run_dir / "tail_ceiling_residual_rule_summary.csv", index=False)
    cases.to_csv(run_dir / "tail_ceiling_residual_failure_cases.csv", index=False)
    columns = [column for column in CASE_COLUMNS if column in candidates.columns]
    candidates[bool_series(candidates, "tail_pass_positive_loss", default=False)][
        columns
    ].to_csv(run_dir / "tail_ceiling_residual_failure_rows.csv", index=False)
    (run_dir / "config.json").write_text(
        json.dumps(
            {
                "candidate_files": [str(path) for path in candidate_paths],
                "max_tail_prob": args.max_tail_prob,
                "positive_pnl_penalty_labels": parse_csv(args.positive_pnl_penalty_labels),
                "dedup_modes": dedup_modes,
                "group_columns": group_columns,
                "rules": rules,
                "context_dedup_mode": args.context_dedup_mode,
                "case_dedup_mode": args.case_dedup_mode,
                "case_limit": args.case_limit,
            },
            indent=2,
            sort_keys=True,
            default=local_json_default,
        )
        + "\n",
        encoding="utf-8",
    )

    print("Tail ceiling residual overall summary:")
    print(overall.head(args.print_rows).to_string(index=False))
    print("\nResidual rule summary:")
    print(rule_summaries.head(args.print_rows).to_string(index=False))
    print("\nResidual failure cases:")
    print(cases.head(args.print_rows).to_string(index=False))
    print(f"artifacts: {run_dir}")
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-files", nargs="*", default=[])
    parser.add_argument("--candidate-glob", action="append", default=[])
    parser.add_argument("--max-tail-prob", type=float, default=0.3)
    parser.add_argument("--positive-pnl-penalty-labels", default="none")
    parser.add_argument(
        "--dedup-modes",
        default="row_weighted,candidate_key,market_candidate_key",
    )
    parser.add_argument("--group-columns", default=DEFAULT_GROUP_COLUMNS)
    parser.add_argument("--rules", default=DEFAULT_RESIDUAL_RULES)
    parser.add_argument(
        "--context-dedup-mode",
        choices=["row_weighted", "candidate_key", "market_candidate_key"],
        default="market_candidate_key",
    )
    parser.add_argument(
        "--case-dedup-mode",
        choices=["row_weighted", "candidate_key", "market_candidate_key"],
        default="market_candidate_key",
    )
    parser.add_argument("--case-limit", type=int, default=120)
    parser.add_argument("--output-dir", type=Path, default=Path("data/reports/backtests"))
    parser.add_argument(
        "--label",
        default="entry_ev_tail_ceiling_residual_failure_diagnostics",
    )
    parser.add_argument("--print-rows", type=int, default=20)
    return parser


def main(argv: list[str] | None = None) -> int:
    run_diagnostics(build_parser().parse_args(argv))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
