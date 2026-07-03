#!/usr/bin/env python3
"""Diagnose positive predicted PnL candidates that realize losses."""

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


DEFAULT_RULES = (
    "tail_prob_ge_0p30,"
    "tail_prob_ge_0p40,"
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
    "tail_prob_ge_0p30_or_harmful_ge_0p30,"
    "positive_bias_and_tail_miss_ge_0p10"
)
REQUIRED_COLUMNS = {
    "role",
    "month",
    "side",
    "row_scope",
    "decision_timestamp",
    "ranker_score_mode",
    "ranker_abstention_rule",
    "hv_chosen_horizon_minutes",
    "hv_chosen_pred_pnl",
    "hv_chosen_pred_tail_loss_prob",
    "hv_chosen_pred_harmful_overestimate_prob",
    "hv_chosen_pred_model_used",
    "actual_pnl_at_hv_chosen_horizon",
}
CONTEXT_COLUMNS = [
    "role",
    "month",
    "side",
    "row_scope",
    "ranker_score_mode",
    "ranker_abstention_rule",
    "hv_chosen_horizon_minutes",
    "combined_regime",
    "session_regime",
    "near_miss_bucket",
]
CHOSEN_WIDE_SUFFIXES = {
    "chosen_prior_count": "prior_count",
    "chosen_prior_months": "prior_months",
    "chosen_prior_mean_pnl": "prior_mean_pnl",
    "chosen_prior_delta_vs_60_mean": "prior_delta_vs_60_mean",
    "chosen_prior_tail_loss_rate": "prior_tail_loss_rate",
    "chosen_prior_risk_score": "prior_risk_score",
    "chosen_residual_count": "residual_count",
    "chosen_residual_months": "residual_months",
    "chosen_residual_bias": "residual_bias",
    "chosen_residual_mae": "residual_mae",
    "chosen_residual_overestimate_rate": "residual_overestimate_rate",
    "chosen_residual_tail_miss_rate": "residual_tail_miss_rate",
    "chosen_tail_reliability": "tail_reliability",
    "chosen_tail_reliability_used": "tail_reliability_used",
    "chosen_tail_train_months": "tail_train_months",
    "chosen_tail_train_rows": "tail_train_rows",
    "chosen_pnl_model_used": "pnl_model_used",
    "chosen_tail_model_used": "tail_model_used",
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


def load_candidate_files(paths: list[Path]) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for path in paths:
        frame = pd.read_csv(path)
        frame = pd.concat(
            [frame, pd.Series(path.name, index=frame.index, name="candidate_file")],
            axis=1,
        ).copy()
        frames.append(frame)
    if not frames:
        raise ValueError("at least one candidate file is required")
    return pd.concat(frames, ignore_index=True, sort=False)


def chosen_wide_value(
    frame: pd.DataFrame,
    *,
    suffix: str,
    horizon: int,
    default: float | bool,
    as_bool: bool = False,
) -> pd.Series:
    column = f"ranker_hv_{horizon}m_{suffix}"
    if column not in frame.columns and suffix.endswith("_model_used"):
        column = f"pred_hv_{horizon}m_{suffix}"
    if column not in frame.columns:
        if as_bool:
            return pd.Series(bool(default), index=frame.index, dtype=bool)
        return pd.Series(float(default), index=frame.index, dtype=float)
    if as_bool:
        return bool_series(frame, column, default=bool(default))
    return numeric_series(frame, column, default=float(default))


def add_chosen_wide_columns(frame: pd.DataFrame) -> pd.DataFrame:
    output = frame.copy()
    horizons = numeric_series(output, "hv_chosen_horizon_minutes", default=0.0).round().astype(int)
    for output_column, suffix in CHOSEN_WIDE_SUFFIXES.items():
        as_bool = output_column.endswith("_used") or output_column.endswith("_model_used")
        default: float | bool = False if as_bool else 0.0
        values = pd.Series(default, index=output.index)
        for horizon in [60, 240, 720]:
            horizon_values = chosen_wide_value(
                output,
                suffix=suffix,
                horizon=horizon,
                default=default,
                as_bool=as_bool,
            )
            values = values.where(~horizons.eq(horizon), horizon_values)
        if as_bool:
            output[output_column] = values.fillna(False).astype(bool)
        else:
            output[output_column] = pd.to_numeric(values, errors="coerce").fillna(0.0).astype(float)
    return output


def normalize_candidates(frame: pd.DataFrame) -> pd.DataFrame:
    missing = sorted(REQUIRED_COLUMNS - set(frame.columns))
    if missing:
        raise ValueError("candidate rows missing columns: " + ", ".join(missing))
    output = frame.copy()
    for column in [
        "candidate_file",
        "family",
        "role",
        "month",
        "side",
        "row_scope",
        "ranker_score_mode",
        "ranker_abstention_rule",
        "combined_regime",
        "session_regime",
        "near_miss_bucket",
        "selection_bucket",
        "scenario_label",
    ]:
        output[column] = text_series(output, column, default="missing")
    output["month"] = output["month"].astype(str).str.slice(0, 7)
    output["decision_timestamp"] = pd.to_datetime(
        output["decision_timestamp"],
        utc=True,
        errors="coerce",
    )
    output = output[output["decision_timestamp"].notna()].copy()
    for column in [
        "hv_chosen_horizon_minutes",
        "hv_chosen_pred_pnl",
        "hv_chosen_pred_tail_loss_prob",
        "hv_chosen_pred_harmful_overestimate_prob",
        "hv_chosen_pred_executable_prob",
        "actual_pnl_at_hv_chosen_horizon",
        "target_pnl_hurdle",
        "extra_side_needed",
        "prob_threshold",
        "ev_threshold",
        "tail_prob_threshold",
        "repair_score",
        "repair_expected_pnl",
        "repair_support_success_proxy",
        "repair_tail_penalty",
        "repair_harmful_penalty_raw",
    ]:
        output[column] = numeric_series(output, column, default=0.0)
    for column in [
        "hv_chosen_pred_model_used",
        "ranker_abstention_veto",
        "require_model_used",
    ]:
        output[column] = bool_series(output, column, default=False)
    output["hv_chosen_horizon_minutes"] = (
        output["hv_chosen_horizon_minutes"].round().astype(int)
    )
    output = add_chosen_wide_columns(output)
    output["target_key"] = (
        output["role"].astype(str)
        + "|"
        + output["month"].astype(str)
        + "|"
        + output["side"].astype(str)
    )
    output["decision_key"] = (
        output["target_key"]
        + "|"
        + output["row_scope"].astype(str)
        + "|"
        + output["decision_timestamp"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    )
    output["candidate_key"] = (
        output["decision_key"]
        + "|"
        + output["hv_chosen_horizon_minutes"].astype(str)
        + "|"
        + output["ranker_score_mode"].astype(str)
        + "|"
        + output["ranker_abstention_rule"].astype(str)
    )
    output["market_candidate_key"] = (
        output["decision_key"] + "|" + output["hv_chosen_horizon_minutes"].astype(str)
    )
    output["predicted_positive_pnl"] = output["hv_chosen_pred_pnl"].gt(0.0)
    output["realized_loss"] = output["actual_pnl_at_hv_chosen_horizon"].lt(0.0)
    output["realized_win"] = output["actual_pnl_at_hv_chosen_horizon"].gt(0.0)
    output["positive_pred_loss"] = output["predicted_positive_pnl"] & output["realized_loss"]
    output["positive_pred_win"] = output["predicted_positive_pnl"] & output["realized_win"]
    output["positive_pred_overestimate"] = (
        output["hv_chosen_pred_pnl"] - output["actual_pnl_at_hv_chosen_horizon"]
    )
    output["positive_pred_large_loss"] = (
        output["predicted_positive_pnl"] & output["actual_pnl_at_hv_chosen_horizon"].le(-5.0)
    )
    return output.reset_index(drop=True)


def deduplicate_candidates(frame: pd.DataFrame, mode: str) -> pd.DataFrame:
    if mode == "row_weighted":
        return frame.copy()
    if mode == "candidate_key":
        return frame.drop_duplicates("candidate_key").copy()
    if mode == "market_candidate_key":
        return frame.drop_duplicates("market_candidate_key").copy()
    raise ValueError(f"unknown dedup mode: {mode}")


def summarize_failure_scope(frame: pd.DataFrame, *, scope_name: str) -> dict[str, Any]:
    pnl = numeric_series(frame, "actual_pnl_at_hv_chosen_horizon", default=0.0)
    pred = numeric_series(frame, "hv_chosen_pred_pnl", default=0.0)
    positive = bool_series(frame, "predicted_positive_pnl", default=False)
    failures = bool_series(frame, "positive_pred_loss", default=False)
    wins = bool_series(frame, "positive_pred_win", default=False)
    return {
        "scope": scope_name,
        "row_count": int(len(frame)),
        "decision_count": int(frame["decision_key"].nunique()) if len(frame) else 0,
        "positive_pred_count": int(positive.sum()),
        "positive_pred_actual_pnl_sum": float(pnl.where(positive, 0.0).sum()),
        "positive_pred_mean_pred_pnl": float(pred.where(positive).mean()) if positive.any() else 0.0,
        "positive_pred_loss_count": int(failures.sum()),
        "positive_pred_loss_rate": float(failures.sum() / positive.sum()) if positive.any() else 0.0,
        "positive_pred_loss_pnl": float(pnl.where(failures, 0.0).sum()),
        "positive_pred_win_count": int(wins.sum()),
        "positive_pred_win_pnl": float(pnl.where(wins, 0.0).sum()),
        "positive_pred_overestimate_mean": float(
            numeric_series(frame[positive], "positive_pred_overestimate", default=0.0).mean()
        )
        if positive.any()
        else 0.0,
        "h60_positive_count": int(
            (positive & numeric_series(frame, "hv_chosen_horizon_minutes").eq(60.0)).sum()
        ),
        "h240_positive_count": int(
            (positive & numeric_series(frame, "hv_chosen_horizon_minutes").eq(240.0)).sum()
        ),
        "h720_positive_count": int(
            (positive & numeric_series(frame, "hv_chosen_horizon_minutes").eq(720.0)).sum()
        ),
    }


def overall_summary(frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for mode in ["row_weighted", "candidate_key", "market_candidate_key"]:
        deduped = deduplicate_candidates(frame, mode)
        rows.append(summarize_failure_scope(deduped, scope_name=mode))
        group_columns = ["ranker_score_mode", "ranker_abstention_rule", "row_scope"]
        for keys, group in deduped.groupby(group_columns, dropna=False, sort=True):
            row = summarize_failure_scope(group, scope_name=mode)
            row.update(dict(zip(group_columns, keys, strict=True)))
            rows.append(row)
    return pd.DataFrame(rows)


def context_summary(frame: pd.DataFrame, *, dedup_mode: str) -> pd.DataFrame:
    deduped = deduplicate_candidates(frame, dedup_mode)
    rows: list[dict[str, Any]] = []
    columns = [column for column in CONTEXT_COLUMNS if column in deduped.columns]
    for keys, group in deduped.groupby(columns, dropna=False, sort=True):
        if not isinstance(keys, tuple):
            keys = (keys,)
        row = summarize_failure_scope(group, scope_name=dedup_mode)
        row.update(dict(zip(columns, keys, strict=True)))
        rows.append(row)
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(
        ["positive_pred_loss_pnl", "positive_pred_loss_count", "positive_pred_win_pnl"],
        ascending=[True, False, True],
    ).reset_index(drop=True)


def top_failure_cases(frame: pd.DataFrame, *, dedup_mode: str, limit: int) -> pd.DataFrame:
    deduped = deduplicate_candidates(frame, dedup_mode)
    failures = deduped[bool_series(deduped, "positive_pred_loss", default=False)].copy()
    columns = [
        "candidate_file",
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
    columns = [column for column in columns if column in failures.columns]
    return failures.sort_values(
        ["actual_pnl_at_hv_chosen_horizon", "positive_pred_overestimate"],
        ascending=[True, False],
    )[columns].head(limit).reset_index(drop=True)


def rule_masks(frame: pd.DataFrame, rules: list[str]) -> list[tuple[str, pd.Series]]:
    masks: list[tuple[str, pd.Series]] = []
    for rule in rules:
        if rule == "tail_prob_ge_0p30":
            mask = numeric_series(frame, "hv_chosen_pred_tail_loss_prob").ge(0.30)
        elif rule == "tail_prob_ge_0p40":
            mask = numeric_series(frame, "hv_chosen_pred_tail_loss_prob").ge(0.40)
        elif rule == "harmful_prob_ge_0p30":
            mask = numeric_series(frame, "hv_chosen_pred_harmful_overestimate_prob").ge(0.30)
        elif rule == "harmful_prob_ge_0p50":
            mask = numeric_series(frame, "hv_chosen_pred_harmful_overestimate_prob").ge(0.50)
        elif rule == "pred_pnl_lt_1":
            mask = numeric_series(frame, "hv_chosen_pred_pnl").lt(1.0)
        elif rule == "pred_pnl_lt_2":
            mask = numeric_series(frame, "hv_chosen_pred_pnl").lt(2.0)
        elif rule == "pred_pnl_lt_5":
            mask = numeric_series(frame, "hv_chosen_pred_pnl").lt(5.0)
        elif rule == "horizon_720m":
            mask = numeric_series(frame, "hv_chosen_horizon_minutes").eq(720.0)
        elif rule == "prior_mean_lt_0":
            mask = numeric_series(frame, "chosen_prior_mean_pnl").lt(0.0)
        elif rule == "prior_tail_ge_0p30":
            mask = numeric_series(frame, "chosen_prior_tail_loss_rate").ge(0.30)
        elif rule == "prior_risk_ge_5":
            mask = numeric_series(frame, "chosen_prior_risk_score").ge(5.0)
        elif rule == "residual_mae_ge_10":
            mask = numeric_series(frame, "chosen_residual_mae").ge(10.0)
        elif rule == "residual_bias_gt_0":
            mask = numeric_series(frame, "chosen_residual_bias").gt(0.0)
        elif rule == "residual_bias_ge_2":
            mask = numeric_series(frame, "chosen_residual_bias").ge(2.0)
        elif rule == "residual_overestimate_ge_0p60":
            mask = numeric_series(frame, "chosen_residual_overestimate_rate").ge(0.60)
        elif rule == "residual_tail_miss_ge_0p10":
            mask = numeric_series(frame, "chosen_residual_tail_miss_rate").ge(0.10)
        elif rule == "tail_reliability_not_used":
            mask = ~bool_series(frame, "chosen_tail_reliability_used", default=False)
        elif rule == "model_not_used":
            mask = ~bool_series(frame, "hv_chosen_pred_model_used", default=False)
        elif rule == "tail_prob_ge_0p30_or_harmful_ge_0p30":
            mask = numeric_series(frame, "hv_chosen_pred_tail_loss_prob").ge(0.30) | numeric_series(
                frame,
                "hv_chosen_pred_harmful_overestimate_prob",
            ).ge(0.30)
        elif rule == "positive_bias_and_tail_miss_ge_0p10":
            mask = numeric_series(frame, "chosen_residual_bias").gt(0.0) & numeric_series(
                frame,
                "chosen_residual_tail_miss_rate",
            ).ge(0.10)
        else:
            raise ValueError(f"unknown rule: {rule}")
        masks.append((rule, mask.fillna(False).astype(bool)))
    return masks


def rule_summary(frame: pd.DataFrame, *, rules: list[str], dedup_mode: str) -> pd.DataFrame:
    deduped = deduplicate_candidates(frame, dedup_mode)
    positive = bool_series(deduped, "predicted_positive_pnl", default=False)
    scoped = deduped[positive].copy()
    if scoped.empty:
        return pd.DataFrame()
    actual = numeric_series(scoped, "actual_pnl_at_hv_chosen_horizon", default=0.0)
    failures = bool_series(scoped, "positive_pred_loss", default=False)
    wins = bool_series(scoped, "positive_pred_win", default=False)
    rows: list[dict[str, Any]] = []
    for rule, full_mask in rule_masks(scoped, rules):
        flagged = full_mask.reindex(scoped.index).fillna(False).astype(bool)
        flagged_count = int(flagged.sum())
        flagged_failure = flagged & failures
        flagged_win = flagged & wins
        rows.append(
            {
                "dedup_mode": dedup_mode,
                "rule": rule,
                "positive_pred_count": int(len(scoped)),
                "total_failure_count": int(failures.sum()),
                "total_failure_pnl": float(actual.where(failures, 0.0).sum()),
                "flagged_count": flagged_count,
                "flagged_share": float(flagged.mean()) if len(scoped) else 0.0,
                "flagged_actual_pnl": float(actual.where(flagged, 0.0).sum()),
                "kept_actual_pnl": float(actual.where(~flagged, 0.0).sum()),
                "flagged_failure_count": int(flagged_failure.sum()),
                "flagged_failure_pnl": float(actual.where(flagged_failure, 0.0).sum()),
                "failure_precision": float(flagged_failure.sum() / flagged_count)
                if flagged_count
                else 0.0,
                "failure_recall": float(flagged_failure.sum() / failures.sum())
                if int(failures.sum())
                else 0.0,
                "flagged_win_count": int(flagged_win.sum()),
                "flagged_win_pnl": float(actual.where(flagged_win, 0.0).sum()),
                "removed_loss_abs": float(-actual.where(flagged_failure, 0.0).sum()),
                "removed_win_pnl": float(actual.where(flagged_win, 0.0).sum()),
            }
        )
    return pd.DataFrame(rows).sort_values(
        ["flagged_actual_pnl", "flagged_failure_pnl", "flagged_win_pnl"],
        ascending=[True, True, True],
    ).reset_index(drop=True)


def run_diagnostics(args: argparse.Namespace) -> Path:
    candidate_paths = [Path(path) for path in args.candidate_files]
    candidates = normalize_candidates(load_candidate_files(candidate_paths))
    rules = parse_csv(args.rules)
    overall = overall_summary(candidates)
    context = context_summary(candidates, dedup_mode=args.context_dedup_mode)
    cases = top_failure_cases(candidates, dedup_mode=args.case_dedup_mode, limit=args.case_limit)
    rule_frames = [
        rule_summary(candidates, rules=rules, dedup_mode=mode)
        for mode in ["row_weighted", "candidate_key", "market_candidate_key"]
    ]
    rule_summaries = pd.concat(
        [frame for frame in rule_frames if not frame.empty],
        ignore_index=True,
        sort=False,
    )

    run_dir = make_run_dir(args.output_dir, args.label)
    candidates.to_csv(run_dir / "positive_pnl_failure_candidates.csv", index=False)
    overall.to_csv(run_dir / "positive_pnl_failure_overall_summary.csv", index=False)
    context.to_csv(run_dir / "positive_pnl_failure_context_summary.csv", index=False)
    rule_summaries.to_csv(run_dir / "positive_pnl_failure_rule_summary.csv", index=False)
    cases.to_csv(run_dir / "positive_pnl_failure_cases.csv", index=False)
    (run_dir / "config.json").write_text(
        json.dumps(
            {
                "candidate_files": [str(path) for path in candidate_paths],
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

    print("Positive predicted PnL failure diagnostics:")
    print(overall.head(args.print_rows).to_string(index=False))
    print("\nRule summary:")
    print(rule_summaries.head(args.print_rows).to_string(index=False))
    print("\nWorst cases:")
    print(cases.head(args.print_rows).to_string(index=False))
    print(f"artifacts: {run_dir}")
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-files", nargs="+", required=True)
    parser.add_argument("--rules", default=DEFAULT_RULES)
    parser.add_argument(
        "--context-dedup-mode",
        choices=["row_weighted", "candidate_key", "market_candidate_key"],
        default="candidate_key",
    )
    parser.add_argument(
        "--case-dedup-mode",
        choices=["row_weighted", "candidate_key", "market_candidate_key"],
        default="market_candidate_key",
    )
    parser.add_argument("--case-limit", type=int, default=80)
    parser.add_argument("--output-dir", type=Path, default=Path("data/reports/backtests"))
    parser.add_argument("--label", default="entry_ev_positive_pnl_failure_diagnostics")
    parser.add_argument("--print-rows", type=int, default=20)
    return parser


def main(argv: list[str] | None = None) -> int:
    run_diagnostics(build_parser().parse_args(argv))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
