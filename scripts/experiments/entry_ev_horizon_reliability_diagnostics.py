#!/usr/bin/env python3
"""Diagnose horizon head reliability versus realized horizon choices."""

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

from entry_ev_broad_prior_horizon_choice_replay import score_predictions  # noqa: E402
from entry_ev_near_miss_exit_head import bool_series, numeric_series, parse_csv, text_series  # noqa: E402


DEFAULT_TARGETS = (
    "fresh2024_validation:2024-03:long,"
    "fresh2024_validation:2024-08:long,"
    "fresh2024_validation:2024-11:long,"
    "refit2025_validation:2025-03:short,"
    "refit2025_validation:2025-07:short,"
    "hybrid2025_0912_external:2025-10:long,"
    "hybrid2025_0912_external:2025-11:short"
)
DEFAULT_ROW_SCOPES = "available_candidates,greedy_selected"
DEFAULT_SCORE_MODES = "pnl,pnl_delta_tail,pnl_tail_reliability_gated,pnl_delta_tail_reliability_gated"
REQUIRED_COLUMNS = {
    "role",
    "month",
    "side",
    "row_scope",
    "decision_timestamp",
    "hv_chosen_horizon_minutes",
    "horizon_actual_pnl",
    "ranker_pred_pnl",
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


def parse_targets(value: str) -> list[tuple[str, str, str]]:
    targets: list[tuple[str, str, str]] = []
    for item in parse_csv(value):
        parts = item.split(":")
        if len(parts) != 3:
            raise ValueError(f"target must be role:YYYY-MM:side: {item}")
        role, month, side = parts
        targets.append((role, month[:7], side))
    return targets


def normalize_scored_examples(frame: pd.DataFrame) -> pd.DataFrame:
    missing = sorted(REQUIRED_COLUMNS - set(frame.columns))
    if missing:
        raise ValueError("scored examples missing columns: " + ", ".join(missing))
    output = frame.copy()
    for column in [
        "family",
        "role",
        "side",
        "row_scope",
        "combined_regime",
        "session_regime",
        "near_miss_bucket",
        "horizon_bucket",
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
        "horizon_actual_pnl",
        "horizon_actual_delta_vs_60",
        "ranker_pred_pnl",
        "ranker_pred_delta_vs_60",
        "ranker_pred_beats60_prob",
        "ranker_pred_tail_loss_prob",
        "ranker_pred_executable_prob",
        "delta_reliability_positive_score",
        "beats60_reliability_positive_score",
        "tail_reliability_positive_score",
        "delta_reliability_score",
        "beats60_reliability_score",
        "tail_reliability_score",
        "delta_reliability_count",
        "beats60_reliability_count",
        "tail_reliability_count",
        "delta_reliability_months",
        "beats60_reliability_months",
        "tail_reliability_months",
        "ranker_pred_pnl_train_rows",
        "ranker_pred_delta_vs_60_train_rows",
        "ranker_pred_beats60_prob_train_rows",
        "ranker_pred_tail_loss_prob_train_rows",
    ]:
        output[column] = numeric_series(output, column, default=0.0)
    for column in [
        "target_horizon_beats_60",
        "target_horizon_tail_loss",
        "delta_reliability_used",
        "beats60_reliability_used",
        "tail_reliability_used",
        "ranker_core_model_used",
    ]:
        output[column] = bool_series(output, column, default=False)
    output["horizon_minutes"] = output["hv_chosen_horizon_minutes"].round().astype(int)
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
    output["pnl_error"] = output["ranker_pred_pnl"] - output["horizon_actual_pnl"]
    output["delta_error"] = (
        output["ranker_pred_delta_vs_60"] - output["horizon_actual_delta_vs_60"]
    )
    output["beats60_error"] = (
        output["ranker_pred_beats60_prob"] - output["target_horizon_beats_60"].astype(float)
    )
    output["tail_error"] = (
        output["ranker_pred_tail_loss_prob"] - output["target_horizon_tail_loss"].astype(float)
    )
    return output.reset_index(drop=True)


def filter_targets(
    frame: pd.DataFrame,
    *,
    targets: list[tuple[str, str, str]],
    row_scopes: list[str],
) -> pd.DataFrame:
    output = frame.copy()
    if targets:
        target_index = pd.MultiIndex.from_tuples(targets, names=["role", "month", "side"])
        current_index = pd.MultiIndex.from_frame(output[["role", "month", "side"]])
        output = output[current_index.isin(target_index)].copy()
    if row_scopes:
        output = output[output["row_scope"].isin(row_scopes)].copy()
    return output.reset_index(drop=True)


def add_score_mode_columns(
    frame: pd.DataFrame,
    *,
    score_modes: list[str],
    delta_weight: float,
    beats60_weight: float,
    tail_score_weight: float,
    support_score_weight: float,
    harmful_score_weight: float,
    lower_bound_mae_weight: float,
    lower_bound_bias_weight: float,
    lower_bound_tail_miss_weight: float,
) -> pd.DataFrame:
    output = frame.copy()
    for score_mode in score_modes:
        output[f"score_{score_mode}"] = score_predictions(
            output,
            score_mode=score_mode,
            delta_weight=delta_weight,
            beats60_weight=beats60_weight,
            tail_score_weight=tail_score_weight,
            support_score_weight=support_score_weight,
            harmful_score_weight=harmful_score_weight,
            lower_bound_mae_weight=lower_bound_mae_weight,
            lower_bound_bias_weight=lower_bound_bias_weight,
            lower_bound_tail_miss_weight=lower_bound_tail_miss_weight,
        )
    return output


def choose_by_score(frame: pd.DataFrame, *, score_mode: str) -> pd.DataFrame:
    score_column = f"score_{score_mode}"
    if frame.empty:
        return pd.DataFrame()
    idx = frame.groupby("decision_key", dropna=False)[score_column].idxmax()
    chosen = frame.loc[idx].copy()
    chosen["score_mode"] = score_mode
    chosen["chosen_score"] = chosen[score_column].astype(float)
    return chosen.reset_index(drop=True)


def choice_deltas(
    frame: pd.DataFrame,
    *,
    score_modes: list[str],
    baseline_score_mode: str,
) -> pd.DataFrame:
    choices = [choose_by_score(frame, score_mode=mode) for mode in score_modes]
    choices = [choice for choice in choices if not choice.empty]
    if not choices:
        return pd.DataFrame()
    all_choices = pd.concat(choices, ignore_index=True, sort=False)
    baseline = all_choices[all_choices["score_mode"].eq(baseline_score_mode)].copy()
    baseline = baseline[
        [
            "decision_key",
            "horizon_minutes",
            "horizon_actual_pnl",
            "chosen_score",
        ]
    ].rename(
        columns={
            "horizon_minutes": "baseline_horizon_minutes",
            "horizon_actual_pnl": "baseline_actual_pnl",
            "chosen_score": "baseline_score",
        }
    )
    merged = all_choices.merge(baseline, on="decision_key", how="left")
    merged["actual_delta_vs_baseline"] = (
        merged["horizon_actual_pnl"] - merged["baseline_actual_pnl"]
    )
    merged["choice_changed_vs_baseline"] = (
        merged["horizon_minutes"] != merged["baseline_horizon_minutes"]
    )
    merged["choice_worse_than_baseline"] = merged["actual_delta_vs_baseline"].lt(0.0)
    merged["choice_better_than_baseline"] = merged["actual_delta_vs_baseline"].gt(0.0)
    return merged.sort_values(
        ["role", "month", "side", "row_scope", "decision_timestamp", "score_mode"],
    ).reset_index(drop=True)


def summarize_bool_rate(group: pd.DataFrame, column: str) -> float:
    if column not in group.columns or len(group) == 0:
        return 0.0
    return float(bool_series(group, column).mean())


def horizon_head_summary(frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    group_columns = ["role", "month", "side", "row_scope", "horizon_minutes"]
    for keys, group in frame.groupby(group_columns, dropna=False, sort=True):
        row = dict(zip(group_columns, keys, strict=True))
        actual = numeric_series(group, "horizon_actual_pnl", default=0.0)
        row["row_count"] = int(len(group))
        row["decision_count"] = int(group["decision_key"].nunique())
        row["actual_pnl_sum"] = float(actual.sum())
        row["actual_pnl_mean"] = float(actual.mean()) if len(group) else np.nan
        row["actual_positive_rate"] = float(actual.gt(0.0).mean()) if len(group) else 0.0
        row["actual_tail_rate"] = summarize_bool_rate(group, "target_horizon_tail_loss")
        row["actual_beats60_rate"] = summarize_bool_rate(group, "target_horizon_beats_60")
        row["model_used_rate"] = summarize_bool_rate(group, "ranker_core_model_used")
        for column in [
            "ranker_pred_pnl",
            "ranker_pred_delta_vs_60",
            "ranker_pred_beats60_prob",
            "ranker_pred_tail_loss_prob",
            "horizon_actual_delta_vs_60",
            "pnl_error",
            "delta_error",
            "beats60_error",
            "tail_error",
            "delta_reliability_positive_score",
            "beats60_reliability_positive_score",
            "tail_reliability_positive_score",
            "delta_reliability_score",
            "beats60_reliability_score",
            "tail_reliability_score",
            "delta_reliability_count",
            "beats60_reliability_count",
            "tail_reliability_count",
        ]:
            row[f"{column}_mean"] = float(numeric_series(group, column, default=0.0).mean())
        row["pnl_abs_error_mean"] = float(numeric_series(group, "pnl_error", 0.0).abs().mean())
        row["delta_abs_error_mean"] = float(numeric_series(group, "delta_error", 0.0).abs().mean())
        row["pnl_overestimate_rate"] = float(numeric_series(group, "pnl_error", 0.0).gt(0).mean())
        row["delta_overestimate_rate"] = float(
            numeric_series(group, "delta_error", 0.0).gt(0).mean()
        )
        row["delta_reliability_used_rate"] = summarize_bool_rate(group, "delta_reliability_used")
        row["beats60_reliability_used_rate"] = summarize_bool_rate(
            group,
            "beats60_reliability_used",
        )
        row["tail_reliability_used_rate"] = summarize_bool_rate(group, "tail_reliability_used")
        rows.append(row)
    return pd.DataFrame(rows)


def choice_summary(deltas: pd.DataFrame) -> pd.DataFrame:
    if deltas.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    group_columns = ["score_mode", "role", "month", "side", "row_scope"]
    for keys, group in deltas.groupby(group_columns, dropna=False, sort=True):
        row = dict(zip(group_columns, keys, strict=True))
        row["decision_count"] = int(group["decision_key"].nunique())
        row["chosen_actual_sum"] = float(numeric_series(group, "horizon_actual_pnl", 0.0).sum())
        row["baseline_actual_sum"] = float(numeric_series(group, "baseline_actual_pnl", 0.0).sum())
        row["delta_vs_baseline_sum"] = float(
            numeric_series(group, "actual_delta_vs_baseline", 0.0).sum()
        )
        row["changed_count"] = int(bool_series(group, "choice_changed_vs_baseline").sum())
        row["worse_count"] = int(bool_series(group, "choice_worse_than_baseline").sum())
        row["better_count"] = int(bool_series(group, "choice_better_than_baseline").sum())
        for horizon in [60, 240, 720]:
            row[f"chosen_{horizon}m_count"] = int(group["horizon_minutes"].eq(horizon).sum())
            row[f"baseline_{horizon}m_count"] = int(
                group["baseline_horizon_minutes"].eq(horizon).sum()
            )
        for column in [
            "delta_reliability_positive_score",
            "beats60_reliability_positive_score",
            "tail_reliability_positive_score",
            "ranker_pred_pnl",
            "ranker_pred_delta_vs_60",
            "ranker_pred_beats60_prob",
            "ranker_pred_tail_loss_prob",
        ]:
            row[f"chosen_{column}_mean"] = float(
                numeric_series(group, column, default=0.0).mean()
            )
        rows.append(row)
    return pd.DataFrame(rows)


def failure_cases(deltas: pd.DataFrame, *, baseline_score_mode: str) -> pd.DataFrame:
    if deltas.empty:
        return pd.DataFrame()
    output = deltas[
        (~deltas["score_mode"].eq(baseline_score_mode))
        & (deltas["choice_changed_vs_baseline"] | deltas["choice_worse_than_baseline"])
    ].copy()
    return output.sort_values(
        ["actual_delta_vs_baseline", "role", "month", "side", "decision_timestamp"],
    ).reset_index(drop=True)


def missing_target_summary(
    frame: pd.DataFrame,
    *,
    targets: list[tuple[str, str, str]],
    row_scopes: list[str],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for role, month, side in targets:
        target_rows = frame[
            frame["role"].eq(role) & frame["month"].eq(month) & frame["side"].eq(side)
        ]
        for scope in row_scopes:
            scoped = target_rows[target_rows["row_scope"].eq(scope)]
            rows.append(
                {
                    "target_key": f"{role}|{month}|{side}",
                    "role": role,
                    "month": month,
                    "side": side,
                    "row_scope": scope,
                    "has_rows": bool(len(scoped)),
                    "row_count": int(len(scoped)),
                    "decision_count": int(scoped["decision_key"].nunique()) if len(scoped) else 0,
                }
            )
    return pd.DataFrame(rows)


def run_diagnostics(args: argparse.Namespace) -> Path:
    targets = parse_targets(args.targets)
    row_scopes = parse_csv(args.row_scopes)
    score_modes = parse_csv(args.score_modes)
    if args.baseline_score_mode not in score_modes:
        score_modes = [args.baseline_score_mode, *score_modes]
    scored = normalize_scored_examples(pd.read_csv(args.scored_examples))
    scored = add_score_mode_columns(
        scored,
        score_modes=score_modes,
        delta_weight=args.delta_weight,
        beats60_weight=args.beats60_weight,
        tail_score_weight=args.tail_score_weight,
        support_score_weight=args.support_score_weight,
        harmful_score_weight=args.harmful_score_weight,
        lower_bound_mae_weight=args.lower_bound_mae_weight,
        lower_bound_bias_weight=args.lower_bound_bias_weight,
        lower_bound_tail_miss_weight=args.lower_bound_tail_miss_weight,
    )
    filtered = filter_targets(scored, targets=targets, row_scopes=row_scopes)
    horizon_summary = horizon_head_summary(filtered)
    deltas = choice_deltas(
        filtered,
        score_modes=score_modes,
        baseline_score_mode=args.baseline_score_mode,
    )
    summary = choice_summary(deltas)
    failures = failure_cases(deltas, baseline_score_mode=args.baseline_score_mode)
    missing = missing_target_summary(scored, targets=targets, row_scopes=row_scopes)

    run_dir = make_run_dir(args.output_dir, args.label)
    filtered.to_csv(run_dir / "horizon_reliability_rows.csv", index=False)
    horizon_summary.to_csv(run_dir / "horizon_reliability_head_summary.csv", index=False)
    deltas.to_csv(run_dir / "horizon_reliability_choice_deltas.csv", index=False)
    summary.to_csv(run_dir / "horizon_reliability_choice_summary.csv", index=False)
    failures.to_csv(run_dir / "horizon_reliability_failure_cases.csv", index=False)
    missing.to_csv(run_dir / "horizon_reliability_missing_targets.csv", index=False)
    (run_dir / "config.json").write_text(
        json.dumps(
            {
                "scored_examples": args.scored_examples,
                "targets": args.targets,
                "row_scopes": row_scopes,
                "score_modes": score_modes,
                "baseline_score_mode": args.baseline_score_mode,
                "delta_weight": args.delta_weight,
                "beats60_weight": args.beats60_weight,
                "tail_score_weight": args.tail_score_weight,
                "support_score_weight": args.support_score_weight,
                "harmful_score_weight": args.harmful_score_weight,
                "lower_bound_mae_weight": args.lower_bound_mae_weight,
                "lower_bound_bias_weight": args.lower_bound_bias_weight,
                "lower_bound_tail_miss_weight": args.lower_bound_tail_miss_weight,
            },
            indent=2,
            sort_keys=True,
            default=local_json_default,
        )
        + "\n",
        encoding="utf-8",
    )

    print("Horizon reliability diagnostics:")
    print(f"rows: {len(filtered)}")
    print(missing.to_string(index=False))
    print(summary.head(30).to_string(index=False) if not summary.empty else "no choices")
    print(f"failure cases: {len(failures)}")
    print(f"artifacts: {run_dir}")
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scored-examples", type=Path, required=True)
    parser.add_argument("--targets", default=DEFAULT_TARGETS)
    parser.add_argument("--row-scopes", default=DEFAULT_ROW_SCOPES)
    parser.add_argument("--score-modes", default=DEFAULT_SCORE_MODES)
    parser.add_argument("--baseline-score-mode", default="pnl")
    parser.add_argument("--delta-weight", type=float, default=0.25)
    parser.add_argument("--beats60-weight", type=float, default=0.5)
    parser.add_argument("--tail-score-weight", type=float, default=2.0)
    parser.add_argument("--support-score-weight", type=float, default=2.0)
    parser.add_argument("--harmful-score-weight", type=float, default=5.0)
    parser.add_argument("--lower-bound-mae-weight", type=float, default=0.25)
    parser.add_argument("--lower-bound-bias-weight", type=float, default=0.25)
    parser.add_argument("--lower-bound-tail-miss-weight", type=float, default=5.0)
    parser.add_argument("--output-dir", type=Path, default=Path("data/reports/backtests"))
    parser.add_argument("--label", default="entry_ev_horizon_reliability_diagnostics")
    return parser


def main(argv: list[str] | None = None) -> int:
    run_diagnostics(build_parser().parse_args(argv))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
