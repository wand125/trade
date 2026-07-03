#!/usr/bin/env python3
"""Diagnose abstention rules for reliability-driven horizon switches."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable

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
    "no_veto,"
    "veto_all_switches,"
    "veto_longer_horizon_switch,"
    "veto_60_to_longer_switch,"
    "veto_chosen_pred_pnl_below_baseline,"
    "veto_chosen_pred_pnl_lt0,"
    "veto_tail_prob_ge_0p30,"
    "veto_uncertain_beats60_switch,"
    "veto_longer_tail_or_lowpnl"
)
REQUIRED_COLUMNS = {
    "score_mode",
    "role",
    "month",
    "side",
    "row_scope",
    "decision_timestamp",
    "decision_key",
    "horizon_minutes",
    "horizon_actual_pnl",
    "baseline_horizon_minutes",
    "baseline_actual_pnl",
    "actual_delta_vs_baseline",
    "choice_changed_vs_baseline",
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


def normalize_choice_deltas(frame: pd.DataFrame) -> pd.DataFrame:
    missing = sorted(REQUIRED_COLUMNS - set(frame.columns))
    if missing:
        raise ValueError("choice deltas missing columns: " + ", ".join(missing))
    output = frame.copy()
    for column in [
        "score_mode",
        "role",
        "month",
        "side",
        "row_scope",
        "decision_key",
        "combined_regime",
        "session_regime",
        "near_miss_bucket",
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
        "horizon_minutes",
        "horizon_actual_pnl",
        "baseline_horizon_minutes",
        "baseline_actual_pnl",
        "baseline_score",
        "ranker_pred_pnl",
        "ranker_pred_delta_vs_60",
        "ranker_pred_beats60_prob",
        "ranker_pred_tail_loss_prob",
        "delta_reliability_positive_score",
        "beats60_reliability_positive_score",
        "tail_reliability_positive_score",
        "chosen_score",
        "actual_delta_vs_baseline",
    ]:
        output[column] = numeric_series(output, column, default=0.0)
    for column in [
        "choice_changed_vs_baseline",
        "choice_worse_than_baseline",
        "choice_better_than_baseline",
        "ranker_core_model_used",
    ]:
        output[column] = bool_series(output, column, default=False)
    output["horizon_minutes"] = output["horizon_minutes"].round().astype(int)
    output["baseline_horizon_minutes"] = output["baseline_horizon_minutes"].round().astype(int)
    return output.reset_index(drop=True)


def switch_mask(frame: pd.DataFrame) -> pd.Series:
    return bool_series(frame, "choice_changed_vs_baseline", default=False)


def rule_no_veto(frame: pd.DataFrame) -> pd.Series:
    return pd.Series(False, index=frame.index, dtype=bool)


def rule_veto_all_switches(frame: pd.DataFrame) -> pd.Series:
    return switch_mask(frame)


def rule_veto_longer_horizon_switch(frame: pd.DataFrame) -> pd.Series:
    return switch_mask(frame) & numeric_series(frame, "horizon_minutes").gt(
        numeric_series(frame, "baseline_horizon_minutes")
    )


def rule_veto_60_to_longer_switch(frame: pd.DataFrame) -> pd.Series:
    return (
        switch_mask(frame)
        & numeric_series(frame, "baseline_horizon_minutes").eq(60.0)
        & numeric_series(frame, "horizon_minutes").gt(60.0)
    )


def rule_veto_chosen_pred_pnl_below_baseline(frame: pd.DataFrame) -> pd.Series:
    return switch_mask(frame) & numeric_series(frame, "ranker_pred_pnl").lt(
        numeric_series(frame, "baseline_score")
    )


def rule_veto_chosen_pred_pnl_lt0(frame: pd.DataFrame) -> pd.Series:
    return switch_mask(frame) & numeric_series(frame, "ranker_pred_pnl").lt(0.0)


def rule_veto_tail_prob_ge_0p30(frame: pd.DataFrame) -> pd.Series:
    return switch_mask(frame) & numeric_series(frame, "ranker_pred_tail_loss_prob").ge(0.30)


def rule_veto_uncertain_beats60_switch(frame: pd.DataFrame) -> pd.Series:
    return (
        switch_mask(frame)
        & numeric_series(frame, "beats60_reliability_positive_score").ge(0.20)
        & numeric_series(frame, "ranker_pred_beats60_prob").lt(0.70)
    )


def rule_veto_longer_tail_or_lowpnl(frame: pd.DataFrame) -> pd.Series:
    longer = rule_veto_longer_horizon_switch(frame)
    tail = numeric_series(frame, "ranker_pred_tail_loss_prob").ge(0.30)
    low_pnl = numeric_series(frame, "ranker_pred_pnl").lt(
        numeric_series(frame, "baseline_score")
    )
    return longer & (tail | low_pnl)


RULES: dict[str, Callable[[pd.DataFrame], pd.Series]] = {
    "no_veto": rule_no_veto,
    "veto_all_switches": rule_veto_all_switches,
    "veto_longer_horizon_switch": rule_veto_longer_horizon_switch,
    "veto_60_to_longer_switch": rule_veto_60_to_longer_switch,
    "veto_chosen_pred_pnl_below_baseline": rule_veto_chosen_pred_pnl_below_baseline,
    "veto_chosen_pred_pnl_lt0": rule_veto_chosen_pred_pnl_lt0,
    "veto_tail_prob_ge_0p30": rule_veto_tail_prob_ge_0p30,
    "veto_uncertain_beats60_switch": rule_veto_uncertain_beats60_switch,
    "veto_longer_tail_or_lowpnl": rule_veto_longer_tail_or_lowpnl,
}


def apply_veto_rule(
    frame: pd.DataFrame,
    *,
    rule_name: str,
    baseline_score_mode: str,
) -> pd.DataFrame:
    if rule_name not in RULES:
        raise ValueError(f"unknown abstention rule: {rule_name}")
    output = frame.copy()
    non_baseline = ~output["score_mode"].eq(baseline_score_mode)
    veto = RULES[rule_name](output) & non_baseline
    output["abstention_rule"] = rule_name
    output["veto_switch"] = veto
    output["post_veto_horizon_minutes"] = np.where(
        veto,
        output["baseline_horizon_minutes"],
        output["horizon_minutes"],
    )
    output["post_veto_actual_pnl"] = np.where(
        veto,
        output["baseline_actual_pnl"],
        output["horizon_actual_pnl"],
    )
    output["post_veto_delta_vs_baseline"] = (
        output["post_veto_actual_pnl"] - output["baseline_actual_pnl"]
    )
    output["veto_recovers_loss"] = veto & output["actual_delta_vs_baseline"].lt(0.0)
    output["veto_removes_gain"] = veto & output["actual_delta_vs_baseline"].gt(0.0)
    return output


def summarize_rule_outcomes(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    group_columns = ["abstention_rule", "score_mode", "row_scope"]
    for keys, group in frame.groupby(group_columns, dropna=False, sort=True):
        row = dict(zip(group_columns, keys, strict=True))
        row["decision_count"] = int(group["decision_key"].nunique())
        row["original_actual_sum"] = float(
            numeric_series(group, "horizon_actual_pnl", default=0.0).sum()
        )
        row["baseline_actual_sum"] = float(
            numeric_series(group, "baseline_actual_pnl", default=0.0).sum()
        )
        row["post_veto_actual_sum"] = float(
            numeric_series(group, "post_veto_actual_pnl", default=0.0).sum()
        )
        row["original_delta_vs_baseline"] = float(
            numeric_series(group, "actual_delta_vs_baseline", default=0.0).sum()
        )
        row["post_veto_delta_vs_baseline"] = float(
            numeric_series(group, "post_veto_delta_vs_baseline", default=0.0).sum()
        )
        row["recovered_pnl_vs_original"] = (
            row["post_veto_actual_sum"] - row["original_actual_sum"]
        )
        row["switch_count"] = int(bool_series(group, "choice_changed_vs_baseline").sum())
        row["veto_count"] = int(bool_series(group, "veto_switch").sum())
        row["veto_recovers_loss_count"] = int(bool_series(group, "veto_recovers_loss").sum())
        row["veto_removes_gain_count"] = int(bool_series(group, "veto_removes_gain").sum())
        row["vetoed_original_delta_sum"] = float(
            numeric_series(group[bool_series(group, "veto_switch")], "actual_delta_vs_baseline", 0.0).sum()
        )
        rows.append(row)
    return pd.DataFrame(rows)


def summarize_rule_targets(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    group_columns = ["abstention_rule", "score_mode", "role", "month", "side", "row_scope"]
    for keys, group in frame.groupby(group_columns, dropna=False, sort=True):
        row = dict(zip(group_columns, keys, strict=True))
        row["decision_count"] = int(group["decision_key"].nunique())
        row["original_delta_vs_baseline"] = float(
            numeric_series(group, "actual_delta_vs_baseline", 0.0).sum()
        )
        row["post_veto_delta_vs_baseline"] = float(
            numeric_series(group, "post_veto_delta_vs_baseline", 0.0).sum()
        )
        row["veto_count"] = int(bool_series(group, "veto_switch").sum())
        row["veto_recovers_loss_count"] = int(bool_series(group, "veto_recovers_loss").sum())
        row["veto_removes_gain_count"] = int(bool_series(group, "veto_removes_gain").sum())
        rows.append(row)
    return pd.DataFrame(rows)


def run_diagnostics(args: argparse.Namespace) -> Path:
    choice_deltas = normalize_choice_deltas(pd.read_csv(args.choice_deltas))
    rules = parse_csv(args.rules)
    frames = [
        apply_veto_rule(
            choice_deltas,
            rule_name=rule,
            baseline_score_mode=args.baseline_score_mode,
        )
        for rule in rules
    ]
    outcomes = pd.concat(frames, ignore_index=True, sort=False) if frames else pd.DataFrame()
    summary = summarize_rule_outcomes(outcomes)
    target_summary = summarize_rule_targets(outcomes)
    cases = outcomes[
        bool_series(outcomes, "veto_switch")
        | bool_series(outcomes, "choice_changed_vs_baseline")
    ].copy()
    cases = cases.sort_values(
        ["abstention_rule", "actual_delta_vs_baseline", "role", "month", "decision_timestamp"],
    )

    run_dir = make_run_dir(args.output_dir, args.label)
    outcomes.to_csv(run_dir / "horizon_reliability_abstention_outcomes.csv", index=False)
    summary.to_csv(run_dir / "horizon_reliability_abstention_summary.csv", index=False)
    target_summary.to_csv(
        run_dir / "horizon_reliability_abstention_target_summary.csv",
        index=False,
    )
    cases.to_csv(run_dir / "horizon_reliability_abstention_cases.csv", index=False)
    (run_dir / "config.json").write_text(
        json.dumps(
            {
                "choice_deltas": args.choice_deltas,
                "rules": rules,
                "baseline_score_mode": args.baseline_score_mode,
            },
            indent=2,
            sort_keys=True,
            default=local_json_default,
        )
        + "\n",
        encoding="utf-8",
    )

    print("Horizon reliability abstention diagnostics:")
    print(summary.to_string(index=False) if not summary.empty else "no summary")
    print(f"artifacts: {run_dir}")
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--choice-deltas", type=Path, required=True)
    parser.add_argument("--rules", default=DEFAULT_RULES)
    parser.add_argument("--baseline-score-mode", default="pnl")
    parser.add_argument("--output-dir", type=Path, default=Path("data/reports/backtests"))
    parser.add_argument("--label", default="entry_ev_horizon_reliability_abstention_diagnostics")
    return parser


def main(argv: list[str] | None = None) -> int:
    run_diagnostics(build_parser().parse_args(argv))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
