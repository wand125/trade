#!/usr/bin/env python3
"""Diagnose context-specific confidence for positive-PnL risk rules."""

from __future__ import annotations

import argparse
import json
import math
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
from entry_ev_over_gating_diagnostics import (  # noqa: E402
    SCENARIO_COLUMNS,
    add_scenario_key,
    attach_selected_additions,
    damage_ratio,
    existing_unique_columns,
    summarize_rule_scope,
)
from entry_ev_positive_pnl_failure_diagnostics import (  # noqa: E402
    load_candidate_files,
    normalize_candidates,
    rule_masks,
)


DEFAULT_RULES = (
    "tail_prob_ge_0p30,"
    "tail_prob_ge_0p40,"
    "harmful_prob_ge_0p30,"
    "harmful_prob_ge_0p50,"
    "positive_bias_and_tail_miss_ge_0p10,"
    "residual_tail_miss_ge_0p10,"
    "horizon_720m"
)
DEFAULT_CONTEXT_COLUMNS = (
    "hv_chosen_horizon_minutes,side,combined_regime,session_regime,near_miss_bucket"
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


def value_key(value: Any) -> str:
    if isinstance(value, (bool, np.bool_)):
        return "true" if bool(value) else "false"
    if value is None:
        return "missing"
    if isinstance(value, float) and math.isnan(value):
        return "missing"
    if isinstance(value, (int, np.integer)):
        return str(int(value))
    if isinstance(value, (float, np.floating)):
        return f"{float(value):g}"
    text = str(value)
    return "missing" if text == "" or text.lower() == "nan" else text


def add_context_key(frame: pd.DataFrame, context_columns: list[str]) -> pd.DataFrame:
    output = frame.copy()
    for column in context_columns:
        if column not in output.columns:
            output[column] = "missing"
    output["context_key"] = [
        "|".join(value_key(row[column]) for column in context_columns)
        for _, row in output[context_columns].iterrows()
    ]
    return output


def add_month_period(frame: pd.DataFrame) -> pd.DataFrame:
    output = frame.copy()
    output["month"] = text_series(output, "month", default="missing").str.slice(0, 7)
    output["month_period"] = pd.PeriodIndex(output["month"], freq="M")
    output["month_ordinal"] = output["month_period"].map(lambda value: int(value.ordinal))
    return output


def expand_rule_rows(
    candidates: pd.DataFrame,
    *,
    rules: list[str],
    context_columns: list[str],
) -> pd.DataFrame:
    base = add_month_period(add_context_key(add_scenario_key(candidates), context_columns))
    frames: list[pd.DataFrame] = []
    for rule, mask in rule_masks(base, rules):
        output = base.copy()
        rule_flag = mask.reindex(output.index).fillna(False).astype(bool)
        output["rule"] = rule
        output["rule_flag"] = rule_flag & bool_series(
            output,
            "predicted_positive_pnl",
            default=False,
        )
        frames.append(output)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True, sort=False)


def deduplicate_prior_rows(frame: pd.DataFrame, mode: str) -> pd.DataFrame:
    if mode == "row_weighted":
        return frame.copy()
    if mode not in {"candidate_key", "market_candidate_key"}:
        raise ValueError(f"unknown prior dedup mode: {mode}")
    if mode not in frame.columns:
        raise ValueError(f"prior dedup mode requires column: {mode}")

    output = frame.copy()
    output["_selected_addition_rank"] = bool_series(
        output,
        "selected_addition",
        default=False,
    ).astype(int)
    output = output.sort_values(
        ["rule", mode, "_selected_addition_rank"],
        ascending=[True, True, False],
    )
    return (
        output.drop_duplicates(["rule", mode], keep="first")
        .drop(columns=["_selected_addition_rank"])
        .reset_index(drop=True)
    )


def summarize_flagged_scope(frame: pd.DataFrame, prefix: str = "") -> dict[str, Any]:
    actual = numeric_series(frame, "actual_pnl_at_hv_chosen_horizon", default=0.0)
    flag = bool_series(frame, "rule_flag", default=False)
    loss = bool_series(frame, "positive_pred_loss", default=False)
    win = bool_series(frame, "positive_pred_win", default=False)
    selected = bool_series(frame, "selected_addition", default=False)
    flagged_loss = flag & loss
    flagged_win = flag & win
    selected_flag = flag & selected
    selected_flagged_loss = selected_flag & loss
    selected_flagged_win = selected_flag & win
    return {
        f"{prefix}candidate_rows": int(len(frame)),
        f"{prefix}flagged_count": int(flag.sum()),
        f"{prefix}flagged_actual_pnl_sum": float(actual.where(flag, 0.0).sum()),
        f"{prefix}flagged_loss_count": int(flagged_loss.sum()),
        f"{prefix}flagged_loss_pnl": float(actual.where(flagged_loss, 0.0).sum()),
        f"{prefix}flagged_win_count": int(flagged_win.sum()),
        f"{prefix}flagged_win_pnl": float(actual.where(flagged_win, 0.0).sum()),
        f"{prefix}selected_flagged_count": int(selected_flag.sum()),
        f"{prefix}selected_flagged_loss_count": int(selected_flagged_loss.sum()),
        f"{prefix}selected_flagged_loss_pnl": float(
            actual.where(selected_flagged_loss, 0.0).sum()
        ),
        f"{prefix}selected_flagged_win_count": int(selected_flagged_win.sum()),
        f"{prefix}selected_flagged_win_pnl": float(
            actual.where(selected_flagged_win, 0.0).sum()
        ),
    }


def monthly_context_rule_summary(expanded: pd.DataFrame, context_columns: list[str]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    group_columns = ["rule", "context_key", "month_period", "month_ordinal"]
    for keys, group in expanded.groupby(group_columns, dropna=False, sort=True):
        row = dict(zip(group_columns, keys, strict=True))
        row["month"] = str(row["month_period"])
        for column in context_columns:
            row[column] = group[column].iloc[0] if column in group.columns and len(group) else "missing"
        row.update(summarize_flagged_scope(group))
        rows.append(row)
    return pd.DataFrame(rows)


def add_prior_context_stats(monthly: pd.DataFrame) -> pd.DataFrame:
    if monthly.empty:
        return pd.DataFrame()
    output = monthly.sort_values(["rule", "context_key", "month_ordinal"]).copy()
    stat_columns = [
        "candidate_rows",
        "flagged_count",
        "flagged_actual_pnl_sum",
        "flagged_loss_count",
        "flagged_loss_pnl",
        "flagged_win_count",
        "flagged_win_pnl",
        "selected_flagged_count",
        "selected_flagged_loss_count",
        "selected_flagged_loss_pnl",
        "selected_flagged_win_count",
        "selected_flagged_win_pnl",
    ]
    group = output.groupby(["rule", "context_key"], dropna=False, sort=False)
    for column in stat_columns:
        output[f"prior_{column}"] = group[column].cumsum().shift(fill_value=0.0)
    context_first = group.cumcount().eq(0)
    for column in stat_columns:
        output.loc[context_first, f"prior_{column}"] = 0.0
    output["prior_pointwise_gate_delta"] = -numeric_series(
        output,
        "prior_flagged_actual_pnl_sum",
        default=0.0,
    )
    output["prior_loss_precision"] = np.where(
        numeric_series(output, "prior_flagged_count", default=0.0).gt(0.0),
        numeric_series(output, "prior_flagged_loss_count", default=0.0)
        / numeric_series(output, "prior_flagged_count", default=0.0),
        0.0,
    )
    output["prior_winner_damage_ratio"] = [
        damage_ratio(win_pnl, -loss_pnl)
        for win_pnl, loss_pnl in zip(
            numeric_series(output, "prior_flagged_win_pnl", default=0.0),
            numeric_series(output, "prior_flagged_loss_pnl", default=0.0),
            strict=True,
        )
    ]
    return output


def apply_confidence_thresholds(
    prior_monthly: pd.DataFrame,
    *,
    min_prior_flagged: int,
    min_prior_gate_delta: float,
    min_prior_loss_precision: float,
    max_prior_winner_damage_ratio: float,
    max_prior_selected_win_count: int,
) -> pd.DataFrame:
    output = prior_monthly.copy()
    output["context_risk_confident"] = (
        numeric_series(output, "prior_flagged_count", default=0.0).ge(min_prior_flagged)
        & numeric_series(output, "prior_pointwise_gate_delta", default=0.0).ge(
            min_prior_gate_delta
        )
        & numeric_series(output, "prior_loss_precision", default=0.0).ge(
            min_prior_loss_precision
        )
        & numeric_series(output, "prior_winner_damage_ratio", default=np.inf).le(
            max_prior_winner_damage_ratio
        )
        & numeric_series(output, "prior_selected_flagged_win_count", default=0.0).le(
            max_prior_selected_win_count
        )
    )
    return output


def attach_prior_confidence(expanded: pd.DataFrame, prior_monthly: pd.DataFrame) -> pd.DataFrame:
    prior_columns = [
        column
        for column in prior_monthly.columns
        if column.startswith("prior_") or column == "context_risk_confident"
    ]
    keys = ["rule", "context_key", "month_ordinal"]
    output = expanded.merge(
        prior_monthly[[*keys, *prior_columns]],
        on=keys,
        how="left",
    )
    for column in prior_columns:
        if column == "context_risk_confident":
            output[column] = bool_series(output, column, default=False)
        else:
            output[column] = numeric_series(output, column, default=0.0)
    output["context_risk_flag"] = bool_series(output, "rule_flag", default=False) & bool_series(
        output,
        "context_risk_confident",
        default=False,
    )
    return output


def summarize_contextual_rule_scope(frame: pd.DataFrame, *, rule: str) -> dict[str, Any]:
    mask = bool_series(frame, "context_risk_flag", default=False)
    row = summarize_rule_scope(frame, rule=rule, rule_mask=mask)
    row["confident_context_count"] = int(
        frame.loc[bool_series(frame, "context_risk_confident", default=False), "context_key"].nunique()
    )
    row["context_risk_flag_count"] = int(mask.sum())
    return row


def contextual_rule_summary(expanded: pd.DataFrame, focus: pd.DataFrame) -> pd.DataFrame:
    focus_keys = set(text_series(focus, "scenario_key", default="missing"))
    scoped = expanded[expanded["scenario_key"].isin(focus_keys)].copy()
    rows: list[dict[str, Any]] = []
    for rule, group in scoped.groupby("rule", dropna=False, sort=True):
        rows.append(summarize_contextual_rule_scope(group, rule=str(rule)))
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(
        ["selected_flagged_win_pnl", "pointwise_gate_delta", "flagged_actual_pnl_sum"],
        ascending=[True, False, True],
    ).reset_index(drop=True)


def contextual_scenario_summary(expanded: pd.DataFrame, focus: pd.DataFrame) -> pd.DataFrame:
    focus_keys = set(text_series(focus, "scenario_key", default="missing"))
    scoped = expanded[expanded["scenario_key"].isin(focus_keys)].copy()
    focus_by_key = focus.set_index("scenario_key", drop=False)
    rows: list[dict[str, Any]] = []
    for (scenario_key, rule), group in scoped.groupby(
        ["scenario_key", "rule"],
        dropna=False,
        sort=False,
    ):
        scenario = focus_by_key.loc[scenario_key]
        row = {column: scenario[column] for column in SCENARIO_COLUMNS if column in scenario.index}
        for column in [
            "scenario_key",
            "scenario_focus_rank",
            "focus_reason",
            "combined_total_pnl",
            "added_count",
            "added_pnl",
            "selector_pass",
            "blockers",
        ]:
            if column in scenario.index:
                row[column] = scenario[column]
        row.update(summarize_contextual_rule_scope(group, rule=str(rule)))
        rows.append(row)
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(
        ["scenario_focus_rank", "selected_flagged_win_pnl", "pointwise_gate_delta"],
        ascending=[True, True, False],
    ).reset_index(drop=True)


def contextual_context_summary(
    expanded: pd.DataFrame,
    focus: pd.DataFrame,
    *,
    context_columns: list[str],
) -> pd.DataFrame:
    focus_keys = set(text_series(focus, "scenario_key", default="missing"))
    scoped = expanded[expanded["scenario_key"].isin(focus_keys)].copy()
    rows: list[dict[str, Any]] = []
    columns = ["rule", *context_columns]
    for keys, group in scoped.groupby(columns, dropna=False, sort=True):
        if not isinstance(keys, tuple):
            keys = (keys,)
        row = dict(zip(columns, keys, strict=True))
        row["scenario_count"] = int(group["scenario_key"].nunique())
        row.update(summarize_contextual_rule_scope(group, rule=str(row["rule"])))
        rows.append(row)
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(
        ["pointwise_gate_delta", "selected_flagged_win_pnl", "flagged_actual_pnl_sum"],
        ascending=[False, True, True],
    ).reset_index(drop=True)


def selected_cases(expanded: pd.DataFrame, focus: pd.DataFrame) -> pd.DataFrame:
    focus_keys = set(text_series(focus, "scenario_key", default="missing"))
    scoped = expanded[
        expanded["scenario_key"].isin(focus_keys)
        & bool_series(expanded, "selected_addition", default=False)
        & bool_series(expanded, "context_risk_flag", default=False)
    ].copy()
    if scoped.empty:
        return pd.DataFrame()
    focus_columns = [
        "scenario_key",
        "scenario_focus_rank",
        "focus_reason",
        "combined_total_pnl",
        "added_count",
        "added_pnl",
        "blockers",
    ]
    scoped = scoped.merge(
        focus[[column for column in focus_columns if column in focus.columns]],
        on="scenario_key",
        how="left",
        suffixes=("", "_scenario"),
    )
    columns = existing_unique_columns(
        scoped,
        [
            "rule",
            "scenario_focus_rank",
            "focus_reason",
            "combined_total_pnl",
            "added_pnl",
            "blockers",
            *SCENARIO_COLUMNS,
            "family",
            "role",
            "month",
            "side",
            "decision_timestamp",
            "hv_chosen_horizon_minutes",
            "hv_chosen_pred_pnl",
            "actual_pnl_at_hv_chosen_horizon",
            "hv_chosen_pred_tail_loss_prob",
            "hv_chosen_pred_harmful_overestimate_prob",
            "combined_regime",
            "session_regime",
            "near_miss_bucket",
            "prior_flagged_count",
            "prior_pointwise_gate_delta",
            "prior_loss_precision",
            "prior_winner_damage_ratio",
            "prior_selected_flagged_win_count",
            "prior_selected_flagged_win_pnl",
        ],
    )
    return scoped.sort_values(
        ["actual_pnl_at_hv_chosen_horizon", "scenario_focus_rank"],
        ascending=[False, True],
    )[columns].reset_index(drop=True)


def run_diagnostics(args: argparse.Namespace) -> Path:
    rules = parse_csv(args.rules)
    context_columns = parse_csv(args.context_columns)
    candidates = normalize_candidates(load_candidate_files([Path(path) for path in args.candidate_files]))
    additions = normalize_candidates(pd.read_csv(args.additions_file))
    candidates = attach_selected_additions(candidates, additions)
    focus = add_scenario_key(pd.read_csv(args.focus_scenarios_file))
    expanded = expand_rule_rows(
        candidates,
        rules=rules,
        context_columns=context_columns,
    )
    prior_input = deduplicate_prior_rows(expanded, args.prior_dedup_mode)
    monthly = monthly_context_rule_summary(prior_input, context_columns)
    prior_monthly = apply_confidence_thresholds(
        add_prior_context_stats(monthly),
        min_prior_flagged=args.min_prior_flagged,
        min_prior_gate_delta=args.min_prior_gate_delta,
        min_prior_loss_precision=args.min_prior_loss_precision,
        max_prior_winner_damage_ratio=args.max_prior_winner_damage_ratio,
        max_prior_selected_win_count=args.max_prior_selected_win_count,
    )
    expanded_with_prior = attach_prior_confidence(expanded, prior_monthly)
    rule_summary = contextual_rule_summary(expanded_with_prior, focus)
    scenario_summary = contextual_scenario_summary(expanded_with_prior, focus)
    context_summary = contextual_context_summary(
        expanded_with_prior,
        focus,
        context_columns=context_columns,
    )
    cases = selected_cases(expanded_with_prior, focus)

    run_dir = make_run_dir(args.output_dir, args.label)
    monthly.to_csv(run_dir / "contextual_risk_monthly_context_summary.csv", index=False)
    prior_monthly.to_csv(run_dir / "contextual_risk_prior_context_summary.csv", index=False)
    rule_summary.to_csv(run_dir / "contextual_risk_rule_summary.csv", index=False)
    scenario_summary.to_csv(run_dir / "contextual_risk_scenario_summary.csv", index=False)
    context_summary.to_csv(run_dir / "contextual_risk_context_summary.csv", index=False)
    cases.to_csv(run_dir / "contextual_risk_selected_cases.csv", index=False)
    (run_dir / "config.json").write_text(
        json.dumps(
            {
                "candidate_files": [str(path) for path in args.candidate_files],
                "additions_file": str(args.additions_file),
                "focus_scenarios_file": str(args.focus_scenarios_file),
                "rules": rules,
                "context_columns": context_columns,
                "prior_dedup_mode": args.prior_dedup_mode,
                "min_prior_flagged": args.min_prior_flagged,
                "min_prior_gate_delta": args.min_prior_gate_delta,
                "min_prior_loss_precision": args.min_prior_loss_precision,
                "max_prior_winner_damage_ratio": args.max_prior_winner_damage_ratio,
                "max_prior_selected_win_count": args.max_prior_selected_win_count,
            },
            indent=2,
            sort_keys=True,
            default=local_json_default,
        )
        + "\n",
        encoding="utf-8",
    )

    print("Contextual risk rule summary:")
    print(rule_summary.head(args.print_rows).to_string(index=False))
    print("\nContextual risk context summary:")
    print(context_summary.head(args.print_rows).to_string(index=False))
    print("\nSelected cases:")
    print(cases.head(args.print_rows).to_string(index=False))
    print(f"artifacts: {run_dir}")
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-files", nargs="+", required=True)
    parser.add_argument("--additions-file", type=Path, required=True)
    parser.add_argument("--focus-scenarios-file", type=Path, required=True)
    parser.add_argument("--rules", default=DEFAULT_RULES)
    parser.add_argument("--context-columns", default=DEFAULT_CONTEXT_COLUMNS)
    parser.add_argument(
        "--prior-dedup-mode",
        choices=["row_weighted", "candidate_key", "market_candidate_key"],
        default="market_candidate_key",
    )
    parser.add_argument("--min-prior-flagged", type=int, default=5)
    parser.add_argument("--min-prior-gate-delta", type=float, default=10.0)
    parser.add_argument("--min-prior-loss-precision", type=float, default=0.60)
    parser.add_argument("--max-prior-winner-damage-ratio", type=float, default=0.25)
    parser.add_argument("--max-prior-selected-win-count", type=int, default=0)
    parser.add_argument("--output-dir", type=Path, default=Path("data/reports/backtests"))
    parser.add_argument("--label", default="entry_ev_contextual_risk_confidence_diagnostics")
    parser.add_argument("--print-rows", type=int, default=20)
    return parser


def main(argv: list[str] | None = None) -> int:
    run_diagnostics(build_parser().parse_args(argv))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
