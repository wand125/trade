#!/usr/bin/env python3
"""Diagnose support-repair candidate switches within local decision clusters."""

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
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from trade_data.backtest import json_default, make_run_dir  # noqa: E402


DEFAULT_GROUP_COLUMNS = "scenario_label,role,month,side"
DEFAULT_CONTEXT_COLUMNS = "hv_chosen_horizon_minutes,side,combined_regime,session_regime,near_miss_bucket"
DEFAULT_SWITCH_THRESHOLDS = "0,1,2,5"
DEFAULT_HARMFUL_DELTAS = "0,0.05,0.10,0.20"
SCENARIO_COLUMNS = [
    "row_scope",
    "prob_threshold",
    "ev_threshold",
    "tail_prob_threshold",
    "require_model_used",
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


def parse_csv(value: str) -> list[str]:
    return [item.strip() for item in str(value).split(",") if item.strip()]


def parse_float_csv(value: str) -> list[float]:
    return [float(item) for item in parse_csv(value)]


def threshold_label(value: float) -> str:
    return f"{float(value):g}".replace(".", "p").replace("-", "m")


def bool_series(frame: pd.DataFrame, column: str, default: bool = False) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=bool)
    values = frame[column]
    if pd.api.types.is_bool_dtype(values):
        return values.fillna(default).astype(bool)
    if pd.api.types.is_numeric_dtype(values):
        return values.fillna(float(default)).astype(float).ne(0.0)
    return (
        values.fillna(str(default))
        .astype(str)
        .str.lower()
        .str.strip()
        .isin({"true", "1", "yes", "y"})
    )


def numeric_series(frame: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=float)
    return (
        pd.to_numeric(frame[column], errors="coerce")
        .replace([np.inf, -np.inf], np.nan)
        .fillna(default)
        .astype(float)
    )


def text_series(frame: pd.DataFrame, column: str, default: str = "missing") -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=object)
    return frame[column].fillna(default).astype(str)


def add_scenario_label(frame: pd.DataFrame) -> pd.DataFrame:
    output = frame.copy()
    if "scenario_label" in output.columns:
        return output
    missing = sorted(set(SCENARIO_COLUMNS) - set(output.columns))
    if missing:
        raise ValueError(
            "frame needs scenario_label or scenario columns: " + ", ".join(missing)
        )
    row_scope = text_series(output, "row_scope")
    prob = numeric_series(output, "prob_threshold")
    ev = numeric_series(output, "ev_threshold")
    tail = numeric_series(output, "tail_prob_threshold")
    require = bool_series(output, "require_model_used")
    output["scenario_label"] = [
        (
            f"{scope}_p{threshold_label(prob_value)}"
            f"_ev{threshold_label(ev_value)}"
            f"_tail{threshold_label(tail_value)}_"
            f"{'reqmodel' if require_value else 'allowfallback'}"
        )
        for scope, prob_value, ev_value, tail_value, require_value in zip(
            row_scope,
            prob,
            ev,
            tail,
            require,
            strict=True,
        )
    ]
    if "ranker_score_mode" in output.columns:
        output["scenario_label"] = (
            output["scenario_label"].astype(str)
            + "_ranker_"
            + text_series(output, "ranker_score_mode", default="")
        )
    return output


def normalize_repair_rows(frame: pd.DataFrame, *, source_name: str) -> pd.DataFrame:
    frame = add_scenario_label(frame)
    required = {
        "scenario_label",
        "role",
        "month",
        "side",
        "decision_timestamp",
        "hv_chosen_horizon_minutes",
        "actual_pnl_at_hv_chosen_horizon",
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"{source_name} missing columns: {', '.join(missing)}")
    output = frame.copy()
    for column in [
        "scenario_label",
        "family",
        "role",
        "side",
        "needed_side",
        "row_scope",
        "combined_regime",
        "session_regime",
        "near_miss_bucket",
        "selection_bucket",
    ]:
        output[column] = text_series(output, column)
    output["month"] = output["month"].astype(str).str.slice(0, 7)
    output["decision_timestamp"] = pd.to_datetime(
        output["decision_timestamp"],
        utc=True,
        errors="coerce",
    )
    output = output[output["decision_timestamp"].notna()].copy()
    for column in [
        "hv_chosen_horizon_minutes",
        "actual_pnl_at_hv_chosen_horizon",
        "adjusted_pnl",
        "hv_chosen_pred_pnl",
        "hv_chosen_pred_executable_prob",
        "hv_chosen_pred_tail_loss_prob",
        "hv_chosen_pred_harmful_overestimate_prob",
        "repair_score",
        "repair_expected_pnl",
        "repair_tail_penalty",
        "repair_support_success_proxy",
        "repair_harmful_penalty",
        "repair_harmful_penalty_raw",
        "repair_harmful_penalty_amount",
        "support_reduction_value",
        "extra_side_needed",
        "addition_rank",
    ]:
        output[column] = numeric_series(output, column, default=0.0)
    output["actual_pnl_at_hv_chosen_horizon"] = numeric_series(
        output,
        "actual_pnl_at_hv_chosen_horizon",
        default=0.0,
    )
    output["horizon_bucket"] = (
        output["hv_chosen_horizon_minutes"].round().astype(int).astype(str) + "m"
    )
    output["repair_row_id"] = np.arange(len(output), dtype=int)
    return output.reset_index(drop=True)


def choose_scenario(summary: pd.DataFrame, scenario_label: str | None) -> str:
    if scenario_label:
        return scenario_label
    if summary.empty:
        raise ValueError("scenario_label is required when summary is empty or omitted")
    required = {"scenario_label", "selector_pass", "combined_total_pnl", "month_pnl_min"}
    missing = sorted(required - set(summary.columns))
    if missing:
        raise ValueError("summary missing columns: " + ", ".join(missing))
    ordered = summary.copy()
    ordered["selector_pass"] = ordered["selector_pass"].astype(str).str.lower().isin(
        {"true", "1", "yes"},
    )
    if "remaining_extra_trades_needed" not in ordered.columns:
        ordered["remaining_extra_trades_needed"] = 0
    ordered = ordered.sort_values(
        [
            "selector_pass",
            "combined_total_pnl",
            "month_pnl_min",
            "remaining_extra_trades_needed",
        ],
        ascending=[False, False, False, True],
    )
    return str(ordered.iloc[0]["scenario_label"])


def filter_scenario(
    candidates: pd.DataFrame,
    additions: pd.DataFrame,
    *,
    scenario_label: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    candidates = add_scenario_label(candidates)
    additions = add_scenario_label(additions)
    cand = candidates[candidates["scenario_label"].astype(str).eq(scenario_label)].copy()
    add = additions[additions["scenario_label"].astype(str).eq(scenario_label)].copy()
    if cand.empty:
        raise ValueError(f"no candidates for scenario_label={scenario_label}")
    if add.empty:
        raise ValueError(f"no additions for scenario_label={scenario_label}")
    return cand.reset_index(drop=True), add.reset_index(drop=True)


def same_choice_mask(candidates: pd.DataFrame, chosen: pd.Series) -> pd.Series:
    mask = candidates["decision_timestamp"].eq(chosen["decision_timestamp"])
    mask &= numeric_series(candidates, "hv_chosen_horizon_minutes").eq(
        float(chosen["hv_chosen_horizon_minutes"]),
    )
    if "family" in candidates.columns and "family" in chosen.index:
        mask &= candidates["family"].astype(str).eq(str(chosen["family"]))
    return mask


def prefixed(row: pd.Series, prefix: str, columns: list[str]) -> dict[str, Any]:
    return {f"{prefix}_{column}": row.get(column, np.nan) for column in columns}


def exceeds_threshold(values: pd.Series | float, threshold: float) -> pd.Series | bool:
    if threshold <= 0:
        return values > 0.0
    return values >= threshold


def build_pairwise_examples(
    candidates: pd.DataFrame,
    additions: pd.DataFrame,
    *,
    group_columns: list[str],
    near_window_minutes: float,
    max_alternatives_per_choice: int,
    min_actual_delta: float,
    min_harmful_delta: float,
) -> pd.DataFrame:
    candidate_rows = normalize_repair_rows(candidates, source_name="candidates")
    chosen_rows = normalize_repair_rows(additions, source_name="additions")
    group_columns = [column for column in group_columns if column in candidate_rows.columns]
    if not group_columns:
        raise ValueError("no valid group columns")

    candidate_groups = {
        key if isinstance(key, tuple) else (key,): group.copy()
        for key, group in candidate_rows.groupby(group_columns, dropna=False, sort=False)
    }
    pair_rows: list[dict[str, Any]] = []
    chosen_columns = [
        "repair_row_id",
        "addition_rank",
        "family",
        "role",
        "month",
        "side",
        "needed_side",
        "decision_timestamp",
        "horizon_bucket",
        "hv_chosen_horizon_minutes",
        "actual_pnl_at_hv_chosen_horizon",
        "repair_score",
        "repair_expected_pnl",
        "repair_support_success_proxy",
        "support_reduction_value",
        "hv_chosen_pred_pnl",
        "hv_chosen_pred_executable_prob",
        "hv_chosen_pred_tail_loss_prob",
        "hv_chosen_pred_harmful_overestimate_prob",
        "combined_regime",
        "session_regime",
        "near_miss_bucket",
    ]
    alt_columns = [column for column in chosen_columns if column != "addition_rank"]

    for chosen_number, (_, chosen) in enumerate(chosen_rows.iterrows(), start=1):
        key = tuple(chosen[column] for column in group_columns)
        group = candidate_groups.get(key)
        if group is None or group.empty:
            continue
        alts = group[~same_choice_mask(group, chosen)].copy()
        if alts.empty:
            continue
        alts["time_delta_minutes"] = (
            alts["decision_timestamp"] - chosen["decision_timestamp"]
        ).abs().dt.total_seconds() / 60.0
        if near_window_minutes >= 0:
            alts = alts[alts["time_delta_minutes"].le(float(near_window_minutes))].copy()
        if alts.empty:
            continue
        alts = alts.sort_values(
            ["time_delta_minutes", "repair_score", "actual_pnl_at_hv_chosen_horizon"],
            ascending=[True, False, False],
        )
        if max_alternatives_per_choice > 0:
            alts = alts.head(max_alternatives_per_choice)
        for _, alt in alts.iterrows():
            actual_delta = float(alt["actual_pnl_at_hv_chosen_horizon"]) - float(
                chosen["actual_pnl_at_hv_chosen_horizon"],
            )
            harmful_reduction = float(
                chosen["hv_chosen_pred_harmful_overestimate_prob"],
            ) - float(alt["hv_chosen_pred_harmful_overestimate_prob"])
            pair_rows.append(
                {
                    **{column: chosen[column] for column in group_columns},
                    "selected_number": chosen_number,
                    "time_delta_minutes": float(alt["time_delta_minutes"]),
                    "switch_actual_delta": actual_delta,
                    "target_switch_improves": bool(actual_delta >= min_actual_delta),
                    "target_switch_hurts": bool(actual_delta < -abs(min_actual_delta)),
                    "repair_score_delta": float(alt["repair_score"])
                    - float(chosen["repair_score"]),
                    "pred_pnl_delta": float(alt["hv_chosen_pred_pnl"])
                    - float(chosen["hv_chosen_pred_pnl"]),
                    "executable_prob_delta": float(alt["hv_chosen_pred_executable_prob"])
                    - float(chosen["hv_chosen_pred_executable_prob"]),
                    "tail_prob_delta": float(alt["hv_chosen_pred_tail_loss_prob"])
                    - float(chosen["hv_chosen_pred_tail_loss_prob"]),
                    "harmful_prob_delta": float(
                        alt["hv_chosen_pred_harmful_overestimate_prob"],
                    )
                    - float(chosen["hv_chosen_pred_harmful_overestimate_prob"]),
                    "harmful_prob_reduction": harmful_reduction,
                    "support_proxy_delta": float(alt["repair_support_success_proxy"])
                    - float(chosen["repair_support_success_proxy"]),
                    "harmful_prefers_alt": bool(
                        exceeds_threshold(harmful_reduction, min_harmful_delta)
                    ),
                    "repair_prefers_alt": bool(
                        float(alt["repair_score"]) > float(chosen["repair_score"])
                    ),
                    **prefixed(chosen, "chosen", chosen_columns),
                    **prefixed(alt, "alt", alt_columns),
                }
            )
    return pd.DataFrame(pair_rows)


def listwise_switch_summary(pairs: pd.DataFrame, *, min_actual_delta: float) -> pd.DataFrame:
    if pairs.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    for selected_number, group in pairs.groupby("selected_number", dropna=False, sort=False):
        first = group.iloc[0]
        best_actual = group.loc[group["alt_actual_pnl_at_hv_chosen_horizon"].idxmax()]
        lowest_harmful = group.loc[
            group["alt_hv_chosen_pred_harmful_overestimate_prob"].idxmin()
        ]
        highest_repair = group.loc[group["alt_repair_score"].idxmax()]
        rows.append(
            {
                "selected_number": int(selected_number),
                "scenario_label": first.get("scenario_label", ""),
                "role": first.get("role", ""),
                "month": first.get("month", ""),
                "side": first.get("side", ""),
                "chosen_decision_timestamp": first["chosen_decision_timestamp"],
                "chosen_horizon_minutes": first["chosen_hv_chosen_horizon_minutes"],
                "chosen_actual_pnl": first["chosen_actual_pnl_at_hv_chosen_horizon"],
                "chosen_repair_score": first["chosen_repair_score"],
                "chosen_harmful_prob": first[
                    "chosen_hv_chosen_pred_harmful_overestimate_prob"
                ],
                "near_alt_count": int(len(group)),
                "improving_alt_count": int(
                    group["switch_actual_delta"].ge(min_actual_delta).sum()
                ),
                "harmful_prefers_alt_count": int(group["harmful_prefers_alt"].sum()),
                "harmful_correct_count": int(
                    (group["harmful_prefers_alt"] & group["switch_actual_delta"].gt(0.0)).sum()
                ),
                "harmful_wrong_count": int(
                    (group["harmful_prefers_alt"] & group["switch_actual_delta"].lt(0.0)).sum()
                ),
                "best_actual_alt_timestamp": best_actual["alt_decision_timestamp"],
                "best_actual_alt_horizon_minutes": best_actual["alt_hv_chosen_horizon_minutes"],
                "best_actual_alt_pnl": best_actual["alt_actual_pnl_at_hv_chosen_horizon"],
                "best_actual_switch_delta": best_actual["switch_actual_delta"],
                "best_actual_alt_harmful_prob": best_actual[
                    "alt_hv_chosen_pred_harmful_overestimate_prob"
                ],
                "lowest_harmful_alt_timestamp": lowest_harmful["alt_decision_timestamp"],
                "lowest_harmful_alt_horizon_minutes": lowest_harmful[
                    "alt_hv_chosen_horizon_minutes"
                ],
                "lowest_harmful_alt_pnl": lowest_harmful[
                    "alt_actual_pnl_at_hv_chosen_horizon"
                ],
                "lowest_harmful_switch_delta": lowest_harmful["switch_actual_delta"],
                "lowest_harmful_alt_harmful_prob": lowest_harmful[
                    "alt_hv_chosen_pred_harmful_overestimate_prob"
                ],
                "highest_repair_alt_timestamp": highest_repair["alt_decision_timestamp"],
                "highest_repair_alt_horizon_minutes": highest_repair[
                    "alt_hv_chosen_horizon_minutes"
                ],
                "highest_repair_alt_pnl": highest_repair[
                    "alt_actual_pnl_at_hv_chosen_horizon"
                ],
                "highest_repair_switch_delta": highest_repair["switch_actual_delta"],
                "highest_repair_alt_harmful_prob": highest_repair[
                    "alt_hv_chosen_pred_harmful_overestimate_prob"
                ],
                "oracle_near_switch_improves": bool(
                    best_actual["switch_actual_delta"] >= min_actual_delta
                ),
                "lowest_harmful_switch_improves": bool(
                    lowest_harmful["switch_actual_delta"] >= min_actual_delta
                ),
                "highest_repair_switch_improves": bool(
                    highest_repair["switch_actual_delta"] >= min_actual_delta
                ),
            }
        )
    return pd.DataFrame(rows)


def summarize_mask(
    pairs: pd.DataFrame,
    *,
    rule: str,
    mask: pd.Series,
    switch_threshold: float,
) -> dict[str, Any]:
    subset = pairs[mask].copy()
    if subset.empty:
        return {
            "rule": rule,
            "switch_threshold": switch_threshold,
            "pair_count": 0,
            "selected_count": 0,
            "switch_improves_count": 0,
            "switch_hurts_count": 0,
            "switch_improves_rate": np.nan,
            "switch_hurts_rate": np.nan,
            "actual_delta_sum": 0.0,
            "actual_delta_mean": np.nan,
            "harmful_reduction_mean": np.nan,
            "repair_score_delta_mean": np.nan,
        }
    improves = subset["switch_actual_delta"].ge(switch_threshold)
    hurts = subset["switch_actual_delta"].lt(-abs(switch_threshold))
    return {
        "rule": rule,
        "switch_threshold": switch_threshold,
        "pair_count": int(len(subset)),
        "selected_count": int(subset["selected_number"].nunique()),
        "switch_improves_count": int(improves.sum()),
        "switch_hurts_count": int(hurts.sum()),
        "switch_improves_rate": float(improves.mean()),
        "switch_hurts_rate": float(hurts.mean()),
        "actual_delta_sum": float(subset["switch_actual_delta"].sum()),
        "actual_delta_mean": float(subset["switch_actual_delta"].mean()),
        "harmful_reduction_mean": float(subset["harmful_prob_reduction"].mean()),
        "repair_score_delta_mean": float(subset["repair_score_delta"].mean()),
    }


def pairwise_rule_summary(
    pairs: pd.DataFrame,
    *,
    switch_thresholds: list[float],
    harmful_deltas: list[float],
) -> pd.DataFrame:
    if pairs.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    for switch_threshold in switch_thresholds:
        base_rules = {
            "all_near_pairs": pd.Series(True, index=pairs.index),
            "repair_score_prefers_alt": pairs["repair_score_delta"].gt(0.0),
            "pred_pnl_prefers_alt": pairs["pred_pnl_delta"].gt(0.0),
            "tail_prob_lower_alt": pairs["tail_prob_delta"].lt(0.0),
            "support_proxy_higher_alt": pairs["support_proxy_delta"].gt(0.0),
        }
        for rule, mask in base_rules.items():
            rows.append(
                summarize_mask(
                    pairs,
                    rule=rule,
                    mask=mask,
                    switch_threshold=switch_threshold,
                )
            )
        for delta in harmful_deltas:
            rows.append(
                summarize_mask(
                    pairs,
                    rule=f"harmful_lower_alt_ge_{delta:g}",
                    mask=exceeds_threshold(pairs["harmful_prob_reduction"], delta),
                    switch_threshold=switch_threshold,
                )
            )
    return pd.DataFrame(rows)


def context_summary(
    frame: pd.DataFrame,
    *,
    source_name: str,
    context_columns: list[str],
    tail_threshold: float,
) -> pd.DataFrame:
    rows = normalize_repair_rows(frame, source_name=source_name)
    columns = [column for column in context_columns if column in rows.columns]
    if not columns:
        columns = ["horizon_bucket"]
    actual = numeric_series(rows, "actual_pnl_at_hv_chosen_horizon", default=0.0)
    rows["actual_loss"] = actual.lt(0.0)
    rows["actual_tail_loss"] = actual.le(float(tail_threshold))
    grouped = rows.groupby(columns, dropna=False)
    summary = grouped.agg(
        row_count=("actual_pnl_at_hv_chosen_horizon", "size"),
        actual_pnl_sum=("actual_pnl_at_hv_chosen_horizon", "sum"),
        actual_pnl_mean=("actual_pnl_at_hv_chosen_horizon", "mean"),
        harmful_prob_mean=("hv_chosen_pred_harmful_overestimate_prob", "mean"),
        repair_score_mean=("repair_score", "mean"),
        support_proxy_mean=("repair_support_success_proxy", "mean"),
        loss_rate=("actual_loss", "mean"),
        tail_loss_rate=("actual_tail_loss", "mean"),
    ).reset_index()
    summary.insert(0, "source", source_name)
    return summary.sort_values(["actual_pnl_sum", "row_count"], ascending=[True, False])


def run_diagnostics(args: argparse.Namespace) -> Path:
    candidates = pd.read_csv(args.candidates)
    additions = pd.read_csv(args.additions)
    summary = pd.read_csv(args.summary) if args.summary else pd.DataFrame()
    scenario = choose_scenario(summary, args.scenario_label)
    candidates, additions = filter_scenario(candidates, additions, scenario_label=scenario)

    pairs = build_pairwise_examples(
        candidates,
        additions,
        group_columns=parse_csv(args.group_columns),
        near_window_minutes=args.near_window_minutes,
        max_alternatives_per_choice=args.max_alternatives_per_choice,
        min_actual_delta=args.min_actual_delta,
        min_harmful_delta=args.min_harmful_delta,
    )
    listwise = listwise_switch_summary(pairs, min_actual_delta=args.min_actual_delta)
    rules = pairwise_rule_summary(
        pairs,
        switch_thresholds=parse_float_csv(args.switch_thresholds),
        harmful_deltas=parse_float_csv(args.harmful_deltas),
    )
    context = pd.concat(
        [
            context_summary(
                candidates,
                source_name="candidates",
                context_columns=parse_csv(args.context_columns),
                tail_threshold=args.tail_threshold,
            ),
            context_summary(
                additions,
                source_name="additions",
                context_columns=parse_csv(args.context_columns),
                tail_threshold=args.tail_threshold,
            ),
        ],
        ignore_index=True,
        sort=False,
    )

    run_dir = make_run_dir(args.output_dir, args.label)
    pairs.to_csv(run_dir / "support_repair_pairwise_switch_examples.csv", index=False)
    listwise.to_csv(run_dir / "support_repair_listwise_switch_summary.csv", index=False)
    rules.to_csv(run_dir / "support_repair_pairwise_rule_summary.csv", index=False)
    context.to_csv(run_dir / "support_repair_context_harmful_summary.csv", index=False)
    (run_dir / "config.json").write_text(
        json.dumps(
            {
                "candidates": args.candidates,
                "additions": args.additions,
                "summary": args.summary,
                "scenario_label": scenario,
                "group_columns": parse_csv(args.group_columns),
                "context_columns": parse_csv(args.context_columns),
                "near_window_minutes": args.near_window_minutes,
                "max_alternatives_per_choice": args.max_alternatives_per_choice,
                "min_actual_delta": args.min_actual_delta,
                "min_harmful_delta": args.min_harmful_delta,
                "switch_thresholds": parse_float_csv(args.switch_thresholds),
                "harmful_deltas": parse_float_csv(args.harmful_deltas),
                "tail_threshold": args.tail_threshold,
            },
            indent=2,
            sort_keys=True,
            default=local_json_default,
        )
        + "\n",
        encoding="utf-8",
    )

    print("Support repair pairwise switch diagnostics:")
    print(f"scenario_label: {scenario}")
    if listwise.empty:
        print("no near alternatives")
    else:
        print(
            listwise[
                [
                    "selected_number",
                    "role",
                    "month",
                    "side",
                    "chosen_actual_pnl",
                    "near_alt_count",
                    "best_actual_switch_delta",
                    "lowest_harmful_switch_delta",
                    "harmful_correct_count",
                    "harmful_wrong_count",
                ]
            ].to_string(index=False)
        )
    print(f"artifacts: {run_dir}")
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--additions", type=Path, required=True)
    parser.add_argument("--summary", type=Path)
    parser.add_argument("--scenario-label", default="")
    parser.add_argument("--group-columns", default=DEFAULT_GROUP_COLUMNS)
    parser.add_argument("--context-columns", default=DEFAULT_CONTEXT_COLUMNS)
    parser.add_argument("--near-window-minutes", type=float, default=30.0)
    parser.add_argument("--max-alternatives-per-choice", type=int, default=100)
    parser.add_argument("--min-actual-delta", type=float, default=0.0)
    parser.add_argument("--min-harmful-delta", type=float, default=0.0)
    parser.add_argument("--switch-thresholds", default=DEFAULT_SWITCH_THRESHOLDS)
    parser.add_argument("--harmful-deltas", default=DEFAULT_HARMFUL_DELTAS)
    parser.add_argument("--tail-threshold", type=float, default=-5.0)
    parser.add_argument("--output-dir", type=Path, default=Path("data/reports/backtests"))
    parser.add_argument("--label", default="entry_ev_support_repair_pairwise_switch")
    return parser


def main(argv: list[str] | None = None) -> int:
    run_diagnostics(build_parser().parse_args(argv))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
