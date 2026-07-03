#!/usr/bin/env python3
"""Diagnose risk rules that remove winners in near-best replay scenarios."""

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
from entry_ev_positive_pnl_failure_diagnostics import (  # noqa: E402
    DEFAULT_RULES,
    load_candidate_files,
    normalize_candidates,
    rule_masks,
)


SCENARIO_COLUMNS = [
    "row_scope",
    "prob_threshold",
    "ev_threshold",
    "tail_prob_threshold",
    "require_model_used",
    "ranker_score_mode",
    "ranker_abstention_rule",
    "positive_pnl_gate_rule",
    "positive_pnl_penalty_label",
]
SUMMARY_CONTEXT_COLUMNS = [
    "ranker_score_mode",
    "ranker_abstention_rule",
    "hv_chosen_horizon_minutes",
    "side",
    "combined_regime",
    "session_regime",
    "near_miss_bucket",
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


def normalize_scenario_columns(frame: pd.DataFrame) -> pd.DataFrame:
    output = frame.copy()
    defaults: dict[str, Any] = {
        "row_scope": "available_candidates",
        "prob_threshold": 0.0,
        "ev_threshold": 0.0,
        "tail_prob_threshold": 0.0,
        "require_model_used": False,
        "ranker_score_mode": "missing",
        "ranker_abstention_rule": "none",
        "positive_pnl_gate_rule": "none",
        "positive_pnl_penalty_label": "none",
    }
    for column, default in defaults.items():
        if column not in output.columns:
            output[column] = default
    for column in [
        "row_scope",
        "ranker_score_mode",
        "ranker_abstention_rule",
        "positive_pnl_gate_rule",
        "positive_pnl_penalty_label",
    ]:
        output[column] = text_series(output, column, default=str(defaults[column]))
    for column in ["prob_threshold", "ev_threshold", "tail_prob_threshold"]:
        output[column] = numeric_series(output, column, default=float(defaults[column]))
    output["require_model_used"] = bool_series(
        output,
        "require_model_used",
        default=bool(defaults["require_model_used"]),
    )
    return output


def add_scenario_key(frame: pd.DataFrame) -> pd.DataFrame:
    output = normalize_scenario_columns(frame)
    output["scenario_key"] = [
        "|".join(value_key(row[column]) for column in SCENARIO_COLUMNS)
        for _, row in output[SCENARIO_COLUMNS].iterrows()
    ]
    return output


def select_focus_scenarios(
    summary: pd.DataFrame,
    *,
    top_n: int,
    near_best_margin: float,
    best_per_columns: list[str],
) -> pd.DataFrame:
    if summary.empty:
        return pd.DataFrame()
    output = add_scenario_key(summary)
    output["combined_total_pnl"] = numeric_series(output, "combined_total_pnl", default=0.0)
    output = output.sort_values(
        ["combined_total_pnl", "added_pnl", "added_count"],
        ascending=[False, False, False],
    ).reset_index(drop=True)
    output["scenario_focus_rank"] = np.arange(1, len(output) + 1)
    best_total = float(output["combined_total_pnl"].max()) if len(output) else 0.0

    frames: list[pd.DataFrame] = []
    if top_n > 0:
        top = output.head(top_n).copy()
        top["focus_reason"] = "global_top"
        frames.append(top)
    near = output[output["combined_total_pnl"].ge(best_total - near_best_margin)].copy()
    if not near.empty:
        near["focus_reason"] = f"within_{near_best_margin:g}_of_best"
        frames.append(near)
    group_columns = [column for column in best_per_columns if column in output.columns]
    if group_columns:
        best_per = output.loc[output.groupby(group_columns, dropna=False)["combined_total_pnl"].idxmax()].copy()
        best_per["focus_reason"] = "best_per_" + "_".join(group_columns)
        frames.append(best_per)

    if not frames:
        return pd.DataFrame()
    focus = pd.concat(frames, ignore_index=True, sort=False)
    focus = focus.sort_values("scenario_focus_rank").drop_duplicates("scenario_key", keep="first")
    return focus.reset_index(drop=True)


def scenario_candidate_key(frame: pd.DataFrame) -> pd.Series:
    return frame["scenario_key"].astype(str) + "|" + frame["market_candidate_key"].astype(str)


def attach_selected_additions(candidates: pd.DataFrame, additions: pd.DataFrame) -> pd.DataFrame:
    output = add_scenario_key(candidates)
    selected = add_scenario_key(additions)
    selected_keys = set(scenario_candidate_key(selected))
    output["selected_addition"] = scenario_candidate_key(output).isin(selected_keys)
    return output


def safe_rate(numerator: float, denominator: float) -> float:
    return float(numerator / denominator) if denominator else 0.0


def damage_ratio(win_pnl: float, loss_abs: float) -> float:
    if loss_abs > 0.0:
        return float(win_pnl / loss_abs)
    return float("inf") if win_pnl > 0.0 else 0.0


def summarize_rule_scope(
    frame: pd.DataFrame,
    *,
    rule: str,
    rule_mask: pd.Series,
) -> dict[str, Any]:
    actual = numeric_series(frame, "actual_pnl_at_hv_chosen_horizon", default=0.0)
    positive = bool_series(frame, "predicted_positive_pnl", default=False)
    losses = bool_series(frame, "positive_pred_loss", default=False)
    wins = bool_series(frame, "positive_pred_win", default=False)
    selected = bool_series(frame, "selected_addition", default=False)
    flagged = rule_mask.reindex(frame.index).fillna(False).astype(bool) & positive
    flagged_losses = flagged & losses
    flagged_wins = flagged & wins
    selected_flagged = flagged & selected
    selected_flagged_losses = selected_flagged & losses
    selected_flagged_wins = selected_flagged & wins
    flagged_loss_pnl = float(actual.where(flagged_losses, 0.0).sum())
    flagged_win_pnl = float(actual.where(flagged_wins, 0.0).sum())
    selected_flagged_loss_pnl = float(actual.where(selected_flagged_losses, 0.0).sum())
    selected_flagged_win_pnl = float(actual.where(selected_flagged_wins, 0.0).sum())
    return {
        "rule": rule,
        "candidate_rows": int(len(frame)),
        "market_candidate_count": int(frame["market_candidate_key"].nunique()) if len(frame) else 0,
        "positive_pred_count": int(positive.sum()),
        "positive_pred_actual_pnl_sum": float(actual.where(positive, 0.0).sum()),
        "positive_pred_loss_count": int(losses.sum()),
        "positive_pred_loss_pnl": float(actual.where(losses, 0.0).sum()),
        "positive_pred_win_count": int(wins.sum()),
        "positive_pred_win_pnl": float(actual.where(wins, 0.0).sum()),
        "flagged_count": int(flagged.sum()),
        "flagged_actual_pnl_sum": float(actual.where(flagged, 0.0).sum()),
        "flagged_loss_count": int(flagged_losses.sum()),
        "flagged_loss_pnl": flagged_loss_pnl,
        "flagged_win_count": int(flagged_wins.sum()),
        "flagged_win_pnl": flagged_win_pnl,
        "flagged_loss_recall": safe_rate(int(flagged_losses.sum()), int(losses.sum())),
        "flagged_loss_precision": safe_rate(int(flagged_losses.sum()), int(flagged.sum())),
        "winner_damage_ratio": damage_ratio(flagged_win_pnl, -flagged_loss_pnl),
        "pointwise_gate_delta": -float(actual.where(flagged, 0.0).sum()),
        "selected_count": int(selected.sum()),
        "selected_actual_pnl_sum": float(actual.where(selected, 0.0).sum()),
        "selected_flagged_count": int(selected_flagged.sum()),
        "selected_flagged_actual_pnl_sum": float(actual.where(selected_flagged, 0.0).sum()),
        "selected_flagged_loss_count": int(selected_flagged_losses.sum()),
        "selected_flagged_loss_pnl": selected_flagged_loss_pnl,
        "selected_flagged_win_count": int(selected_flagged_wins.sum()),
        "selected_flagged_win_pnl": selected_flagged_win_pnl,
        "selected_winner_damage_ratio": damage_ratio(
            selected_flagged_win_pnl,
            -selected_flagged_loss_pnl,
        ),
        "over_gating_selected_winner": bool(int(selected_flagged_wins.sum()) > 0),
        "over_gating_candidate_surface": bool(flagged_win_pnl > max(-flagged_loss_pnl, 0.0)),
    }


def scenario_rule_summary(
    candidates: pd.DataFrame,
    focus: pd.DataFrame,
    *,
    rules: list[str],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    focus_keys = set(focus["scenario_key"].astype(str))
    scoped_candidates = candidates[candidates["scenario_key"].isin(focus_keys)].copy()
    focus_by_key = focus.set_index("scenario_key", drop=False)
    for scenario_key, group in scoped_candidates.groupby("scenario_key", dropna=False, sort=False):
        scenario = focus_by_key.loc[scenario_key]
        for rule, mask in rule_masks(group, rules):
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
                "month_pnl_min",
                "role_trade_count_min",
                "observed_max_side_trade_share",
                "remaining_extra_trades_needed",
            ]:
                if column in scenario.index:
                    row[column] = scenario[column]
            row.update(summarize_rule_scope(group, rule=rule, rule_mask=mask))
            rows.append(row)
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(
        [
            "scenario_focus_rank",
            "over_gating_selected_winner",
            "selected_flagged_win_pnl",
            "flagged_actual_pnl_sum",
        ],
        ascending=[True, False, False, True],
    ).reset_index(drop=True)


def context_rule_summary(
    candidates: pd.DataFrame,
    focus: pd.DataFrame,
    *,
    rules: list[str],
    context_columns: list[str],
) -> pd.DataFrame:
    focus_keys = set(focus["scenario_key"].astype(str))
    scoped = candidates[candidates["scenario_key"].isin(focus_keys)].copy()
    columns = [column for column in context_columns if column in scoped.columns]
    rows: list[dict[str, Any]] = []
    for rule, mask in rule_masks(scoped, rules):
        scoped_rule = scoped.copy()
        scoped_rule["_rule_mask"] = mask.reindex(scoped.index).fillna(False).astype(bool)
        for keys, group in scoped_rule.groupby(columns, dropna=False, sort=True):
            if not isinstance(keys, tuple):
                keys = (keys,)
            row = dict(zip(columns, keys, strict=True))
            row["scenario_count"] = int(group["scenario_key"].nunique())
            row.update(
                summarize_rule_scope(
                    group,
                    rule=rule,
                    rule_mask=bool_series(group, "_rule_mask", default=False),
                )
            )
            rows.append(row)
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(
        [
            "selected_flagged_win_pnl",
            "flagged_win_pnl",
            "flagged_loss_pnl",
            "flagged_count",
        ],
        ascending=[False, False, True, False],
    ).reset_index(drop=True)


def aggregate_rule_tradeoff(summary: pd.DataFrame) -> pd.DataFrame:
    if summary.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    numeric_columns = [
        "candidate_rows",
        "positive_pred_count",
        "positive_pred_actual_pnl_sum",
        "positive_pred_loss_count",
        "positive_pred_loss_pnl",
        "positive_pred_win_count",
        "positive_pred_win_pnl",
        "flagged_count",
        "flagged_actual_pnl_sum",
        "flagged_loss_count",
        "flagged_loss_pnl",
        "flagged_win_count",
        "flagged_win_pnl",
        "pointwise_gate_delta",
        "selected_count",
        "selected_actual_pnl_sum",
        "selected_flagged_count",
        "selected_flagged_actual_pnl_sum",
        "selected_flagged_loss_count",
        "selected_flagged_loss_pnl",
        "selected_flagged_win_count",
        "selected_flagged_win_pnl",
    ]
    for rule, group in summary.groupby("rule", dropna=False, sort=True):
        row: dict[str, Any] = {"rule": rule, "scenario_count": int(group["scenario_key"].nunique())}
        for column in numeric_columns:
            row[column] = float(numeric_series(group, column, default=0.0).sum())
        row["scenario_over_gating_selected_winner_count"] = int(
            bool_series(group, "over_gating_selected_winner", default=False).sum()
        )
        row["winner_damage_ratio"] = damage_ratio(row["flagged_win_pnl"], -row["flagged_loss_pnl"])
        row["selected_winner_damage_ratio"] = damage_ratio(
            row["selected_flagged_win_pnl"],
            -row["selected_flagged_loss_pnl"],
        )
        rows.append(row)
    return pd.DataFrame(rows).sort_values(
        [
            "scenario_over_gating_selected_winner_count",
            "selected_flagged_win_pnl",
            "flagged_actual_pnl_sum",
        ],
        ascending=[False, False, True],
    ).reset_index(drop=True)


def existing_unique_columns(frame: pd.DataFrame, columns: list[str]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for column in columns:
        if column in frame.columns and column not in seen:
            output.append(column)
            seen.add(column)
    return output


def selected_over_gating_cases(
    additions: pd.DataFrame,
    focus: pd.DataFrame,
    *,
    rules: list[str],
) -> pd.DataFrame:
    focus_keys = set(focus["scenario_key"].astype(str))
    scoped = additions[additions["scenario_key"].isin(focus_keys)].copy()
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
    rows: list[pd.DataFrame] = []
    for rule, mask in rule_masks(scoped, rules):
        flagged = mask.reindex(scoped.index).fillna(False).astype(bool) & bool_series(
            scoped,
            "predicted_positive_pnl",
            default=False,
        )
        if not flagged.any():
            continue
        subset = scoped[flagged].copy()
        subset["rule"] = rule
        subset["selected_over_gating_winner"] = bool_series(
            subset,
            "positive_pred_win",
            default=False,
        )
        subset["selected_flagged_loss"] = bool_series(subset, "positive_pred_loss", default=False)
        rows.append(subset)
    if not rows:
        return pd.DataFrame()
    cases = pd.concat(rows, ignore_index=True, sort=False)
    columns = [
        "rule",
        "selected_over_gating_winner",
        "selected_flagged_loss",
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
        "row_scope",
        "decision_timestamp",
        "hv_chosen_horizon_minutes",
        "hv_chosen_pred_pnl",
        "actual_pnl_at_hv_chosen_horizon",
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
        "combined_regime",
        "session_regime",
        "near_miss_bucket",
        "repair_score",
        "positive_pnl_penalty_amount",
    ]
    columns = existing_unique_columns(cases, columns)
    return cases.sort_values(
        [
            "selected_over_gating_winner",
            "actual_pnl_at_hv_chosen_horizon",
            "scenario_focus_rank",
        ],
        ascending=[False, False, True],
    )[columns].reset_index(drop=True)


def run_diagnostics(args: argparse.Namespace) -> Path:
    rules = parse_csv(args.rules)
    context_columns = parse_csv(args.context_columns)
    summary = add_scenario_key(pd.read_csv(args.summary_file))
    additions = normalize_candidates(pd.read_csv(args.additions_file))
    additions = add_scenario_key(additions)
    candidates = normalize_candidates(load_candidate_files([Path(path) for path in args.candidate_files]))
    candidates = add_scenario_key(candidates)
    candidates = attach_selected_additions(candidates, additions)

    focus = select_focus_scenarios(
        summary,
        top_n=args.top_scenarios,
        near_best_margin=args.near_best_margin,
        best_per_columns=parse_csv(args.best_per_columns),
    )
    scenario_summary = scenario_rule_summary(candidates, focus, rules=rules)
    context_summary = context_rule_summary(
        candidates,
        focus,
        rules=rules,
        context_columns=context_columns,
    )
    rule_tradeoff = aggregate_rule_tradeoff(scenario_summary)
    cases = selected_over_gating_cases(additions, focus, rules=rules)

    run_dir = make_run_dir(args.output_dir, args.label)
    focus.to_csv(run_dir / "over_gating_focus_scenarios.csv", index=False)
    scenario_summary.to_csv(run_dir / "over_gating_scenario_rule_summary.csv", index=False)
    rule_tradeoff.to_csv(run_dir / "over_gating_rule_tradeoff_summary.csv", index=False)
    context_summary.to_csv(run_dir / "over_gating_context_rule_summary.csv", index=False)
    cases.to_csv(run_dir / "over_gating_selected_cases.csv", index=False)
    (run_dir / "config.json").write_text(
        json.dumps(
            {
                "summary_file": str(args.summary_file),
                "additions_file": str(args.additions_file),
                "candidate_files": [str(path) for path in args.candidate_files],
                "rules": rules,
                "top_scenarios": args.top_scenarios,
                "near_best_margin": args.near_best_margin,
                "best_per_columns": parse_csv(args.best_per_columns),
                "context_columns": context_columns,
            },
            indent=2,
            sort_keys=True,
            default=local_json_default,
        )
        + "\n",
        encoding="utf-8",
    )

    print("Over-gating rule tradeoff:")
    print(rule_tradeoff.head(args.print_rows).to_string(index=False))
    print("\nSelected over-gating cases:")
    print(cases.head(args.print_rows).to_string(index=False))
    print("\nContext rule summary:")
    print(context_summary.head(args.print_rows).to_string(index=False))
    print(f"artifacts: {run_dir}")
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary-file", type=Path, required=True)
    parser.add_argument("--additions-file", type=Path, required=True)
    parser.add_argument("--candidate-files", nargs="+", required=True)
    parser.add_argument("--rules", default=DEFAULT_RULES)
    parser.add_argument("--top-scenarios", type=int, default=20)
    parser.add_argument("--near-best-margin", type=float, default=5.0)
    parser.add_argument(
        "--best-per-columns",
        default="ranker_score_mode,ranker_abstention_rule,positive_pnl_penalty_label",
    )
    parser.add_argument("--context-columns", default=",".join(SUMMARY_CONTEXT_COLUMNS))
    parser.add_argument("--output-dir", type=Path, default=Path("data/reports/backtests"))
    parser.add_argument("--label", default="entry_ev_over_gating_diagnostics")
    parser.add_argument("--print-rows", type=int, default=20)
    return parser


def main(argv: list[str] | None = None) -> int:
    run_diagnostics(build_parser().parse_args(argv))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
