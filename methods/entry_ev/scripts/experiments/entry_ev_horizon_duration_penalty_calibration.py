#!/usr/bin/env python3
"""Chronological duration-penalty calibration for row x horizon support repair."""

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

from entry_ev_support_repair_horizon_replay import (  # noqa: E402
    SCENARIO_COLUMNS,
    add_repair_utility_columns,
    apply_choice_prefilters,
    local_json_default,
    numeric_series,
    parse_bool_csv,
    parse_csv,
    parse_float_csv,
    read_base_monthly,
    read_base_trades,
    read_choice_candidates,
    replay_scenarios,
)


DEFAULT_PENALTY_WEIGHTS = "0,0.1,0.25,0.5,0.75,1.0"
ROW_ID_COLUMNS = [
    "role",
    "family",
    "month",
    "side",
    "row_scope",
    "decision_timestamp",
]


def calibration_json_default(value: Any) -> Any:
    try:
        return local_json_default(value)
    except TypeError:
        pass
    try:
        return json_default(value)
    except TypeError:
        pass
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"cannot serialize {type(value).__name__}")


def row_id_columns(frame: pd.DataFrame) -> list[str]:
    return [column for column in ROW_ID_COLUMNS if column in frame.columns]


def score_with_penalty(frame: pd.DataFrame, penalty_weight: float) -> pd.Series:
    return (
        numeric_series(frame, "support_reduction_value")
        + numeric_series(frame, "repair_expected_pnl")
        - numeric_series(frame, "repair_tail_penalty")
        - float(penalty_weight) * numeric_series(frame, "repair_horizon_penalty")
    )


def choose_row_horizons(frame: pd.DataFrame, *, penalty_weight: float) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    output = frame.copy()
    output["calibration_score"] = score_with_penalty(output, penalty_weight)
    sort_columns = [
        *row_id_columns(output),
        "calibration_score",
        "actual_pnl_at_hv_chosen_horizon",
        "hv_chosen_horizon_minutes",
    ]
    ascending = [True] * len(row_id_columns(output)) + [False, False, True]
    return (
        output.sort_values(sort_columns, ascending=ascending)
        .drop_duplicates(row_id_columns(output), keep="first")
        .reset_index(drop=True)
    )


def summarize_weight_on_prior(
    prior: pd.DataFrame,
    *,
    penalty_weight: float,
) -> dict[str, Any]:
    selected = choose_row_horizons(prior, penalty_weight=penalty_weight)
    pnl = numeric_series(selected, "actual_pnl_at_hv_chosen_horizon", default=0.0)
    return {
        "penalty_weight": float(penalty_weight),
        "prior_candidate_rows": int(len(prior)),
        "prior_row_choices": int(len(selected)),
        "prior_choice_pnl_sum": float(pnl.sum()) if len(selected) else 0.0,
        "prior_choice_pnl_mean": float(pnl.mean()) if len(selected) else np.nan,
        "prior_choice_pnl_min": float(pnl.min()) if len(selected) else np.nan,
        "prior_choice_loss_count": int(pnl.lt(0.0).sum()) if len(selected) else 0,
        "prior_choice_positive_count": int(pnl.gt(0.0).sum()) if len(selected) else 0,
        "prior_avg_horizon_minutes": float(
            numeric_series(selected, "hv_chosen_horizon_minutes", default=0.0).mean()
        )
        if len(selected)
        else np.nan,
    }


def choose_weight_from_metrics(
    metrics: pd.DataFrame,
    *,
    fallback_weight: float,
    min_prior_rows: int,
    min_prior_months: int,
    prior_months: int,
) -> tuple[float, str, pd.Series | None]:
    if (
        metrics.empty
        or int(metrics["prior_candidate_rows"].max()) < min_prior_rows
        or prior_months < min_prior_months
    ):
        return float(fallback_weight), "fallback_insufficient_prior", None
    ordered = metrics.sort_values(
        [
            "prior_choice_pnl_sum",
            "prior_choice_loss_count",
            "prior_choice_pnl_min",
            "penalty_weight",
        ],
        ascending=[False, True, False, True],
    )
    best = ordered.iloc[0]
    return float(best["penalty_weight"]), "prior_best", best


def calibrate_penalty_weights(
    choices: pd.DataFrame,
    *,
    penalty_weights: list[float],
    fallback_weight: float,
    min_prior_rows: int,
    min_prior_months: int,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    calibrated = choices.copy()
    calibrated["repair_horizon_penalty_weight_effective"] = float(fallback_weight)
    periods = pd.Series(
        pd.PeriodIndex(calibrated["month"].astype(str), freq="M"),
        index=calibrated.index,
    )
    metrics_rows: list[dict[str, Any]] = []
    choice_rows: list[dict[str, Any]] = []

    for key, scenario_group in calibrated.groupby(SCENARIO_COLUMNS, dropna=False, sort=False):
        scenario = dict(zip(SCENARIO_COLUMNS, key, strict=True))
        scenario_index = scenario_group.index
        scenario_periods = periods.loc[scenario_index]
        months = sorted(scenario_group["month"].astype(str).unique().tolist())
        for month in months:
            target_period = pd.Period(month, freq="M")
            month_mask = scenario_group["month"].astype(str).eq(month)
            month_indices = scenario_group[month_mask].index
            prior = scenario_group[scenario_periods < target_period].copy()
            prior_months = int(prior["month"].nunique()) if len(prior) else 0
            weight_metrics = []
            for penalty_weight in penalty_weights:
                row = {
                    **scenario,
                    "target_month": month,
                    "prior_months": prior_months,
                    **summarize_weight_on_prior(prior, penalty_weight=penalty_weight),
                }
                metrics_rows.append(row)
                weight_metrics.append(row)
            metrics_frame = pd.DataFrame(weight_metrics)
            chosen_weight, reason, best = choose_weight_from_metrics(
                metrics_frame,
                fallback_weight=fallback_weight,
                min_prior_rows=min_prior_rows,
                min_prior_months=min_prior_months,
                prior_months=prior_months,
            )
            calibrated.loc[month_indices, "repair_horizon_penalty_weight_effective"] = chosen_weight
            choice_row = {
                **scenario,
                "target_month": month,
                "chosen_penalty_weight": chosen_weight,
                "choice_reason": reason,
                "prior_months": prior_months,
                "prior_candidate_rows": int(len(prior)),
            }
            if best is not None:
                for column in [
                    "prior_row_choices",
                    "prior_choice_pnl_sum",
                    "prior_choice_pnl_mean",
                    "prior_choice_pnl_min",
                    "prior_choice_loss_count",
                    "prior_choice_positive_count",
                    "prior_avg_horizon_minutes",
                ]:
                    choice_row[column] = best[column]
            choice_rows.append(choice_row)

    metrics = pd.DataFrame(metrics_rows)
    choices_out = pd.DataFrame(choice_rows)
    return calibrated, metrics, choices_out


def run_calibration(args: argparse.Namespace) -> Path:
    row_scopes = parse_csv(args.row_scopes)
    overlap_keys = parse_csv(args.overlap_keys)
    penalty_weights = parse_float_csv(args.penalty_weights)
    base_monthly = read_base_monthly(
        args.base_monthly_metrics,
        candidate=args.candidate,
        variant_contains=args.variant_contains,
        entry_block_rule=args.base_entry_block_rule,
    )
    base_trades = read_base_trades(
        args.base_trades,
        candidate=args.candidate,
        variant_contains=args.variant_contains,
        entry_block_rule=args.base_entry_block_rule,
    )
    choices = read_choice_candidates(
        args.predictions,
        row_scopes=row_scopes,
        target_only=args.target_only,
        choice_input_mode="row_horizon_grid",
        prob_thresholds=parse_float_csv(args.prob_thresholds),
        ev_thresholds=parse_float_csv(args.ev_thresholds),
        tail_prob_thresholds=parse_float_csv(args.tail_prob_thresholds),
        require_model_used_options=parse_bool_csv(args.require_model_used_options),
    )
    choices = add_repair_utility_columns(
        base_monthly,
        choices,
        min_month_trades=args.min_month_trades,
        max_side_trade_share=args.max_side_trade_share,
        repair_support_weight=args.repair_support_weight,
        repair_expected_pnl_weight=args.repair_expected_pnl_weight,
        repair_tail_penalty_weight=args.repair_tail_penalty_weight,
        repair_horizon_penalty_weight=0.0,
    )
    filtered_choices, prefilter_rejections = apply_choice_prefilters(
        choices,
        min_chosen_pred_pnl=args.min_chosen_pred_pnl,
        min_chosen_actual_pnl=None,
        max_chosen_tail_prob=args.max_chosen_tail_prob,
    )
    calibrated, calibration_metrics, calibration_choices = calibrate_penalty_weights(
        filtered_choices,
        penalty_weights=penalty_weights,
        fallback_weight=args.fallback_penalty_weight,
        min_prior_rows=args.min_prior_rows,
        min_prior_months=args.min_prior_months,
    )
    summary, monthly, additions, rejections = replay_scenarios(
        base_monthly,
        base_trades,
        calibrated,
        min_total_pnl=args.min_total_pnl,
        min_role_total_pnl=args.min_role_total_pnl,
        month_floor=args.month_floor,
        shallow_month_floor=args.shallow_month_floor,
        min_role_trades=args.min_role_trades,
        min_month_trades=args.min_month_trades,
        max_side_trade_share=args.max_side_trade_share,
        cap_to_extra_side_needed=args.cap_to_extra_side_needed,
        overlap_key_columns=overlap_keys,
        selection_mode="repair_score",
        repair_support_weight=args.repair_support_weight,
        repair_expected_pnl_weight=args.repair_expected_pnl_weight,
        repair_tail_penalty_weight=args.repair_tail_penalty_weight,
        repair_horizon_penalty_weight=0.0,
        min_chosen_pred_pnl=None,
        min_chosen_actual_pnl=None,
        max_chosen_tail_prob=None,
    )

    run_dir = make_run_dir(args.output_dir, args.label)
    summary.to_csv(run_dir / "horizon_duration_penalty_replay_summary.csv", index=False)
    monthly.to_csv(run_dir / "horizon_duration_penalty_monthly_metrics.csv", index=False)
    additions.to_csv(run_dir / "horizon_duration_penalty_additions.csv", index=False)
    rejections.to_csv(run_dir / "horizon_duration_penalty_rejections.csv", index=False)
    calibration_metrics.to_csv(
        run_dir / "horizon_duration_penalty_calibration_metrics.csv",
        index=False,
    )
    calibration_choices.to_csv(
        run_dir / "horizon_duration_penalty_calibration_choices.csv",
        index=False,
    )
    prefilter_rejections.to_csv(
        run_dir / "horizon_duration_penalty_prefilter_rejections.csv",
        index=False,
    )
    calibrated.to_csv(run_dir / "horizon_duration_penalty_candidates.csv", index=False)
    (run_dir / "config.json").write_text(
        json.dumps(
            {
                "base_monthly_metrics": args.base_monthly_metrics,
                "base_trades": args.base_trades,
                "predictions": args.predictions,
                "candidate": args.candidate,
                "variant_contains": args.variant_contains,
                "base_entry_block_rule": args.base_entry_block_rule,
                "row_scopes": row_scopes,
                "target_only": args.target_only,
                "prob_thresholds": parse_float_csv(args.prob_thresholds),
                "ev_thresholds": parse_float_csv(args.ev_thresholds),
                "tail_prob_thresholds": parse_float_csv(args.tail_prob_thresholds),
                "require_model_used_options": parse_bool_csv(args.require_model_used_options),
                "penalty_weights": penalty_weights,
                "fallback_penalty_weight": args.fallback_penalty_weight,
                "min_prior_rows": args.min_prior_rows,
                "min_prior_months": args.min_prior_months,
                "min_chosen_pred_pnl": args.min_chosen_pred_pnl,
                "max_chosen_tail_prob": args.max_chosen_tail_prob,
                "repair_support_weight": args.repair_support_weight,
                "repair_expected_pnl_weight": args.repair_expected_pnl_weight,
                "repair_tail_penalty_weight": args.repair_tail_penalty_weight,
                "min_total_pnl": args.min_total_pnl,
                "min_role_total_pnl": args.min_role_total_pnl,
                "month_floor": args.month_floor,
                "shallow_month_floor": args.shallow_month_floor,
                "min_role_trades": args.min_role_trades,
                "min_month_trades": args.min_month_trades,
                "max_side_trade_share": args.max_side_trade_share,
                "cap_to_extra_side_needed": args.cap_to_extra_side_needed,
                "overlap_keys": overlap_keys,
            },
            indent=2,
            default=calibration_json_default,
        ),
        encoding="utf-8",
    )

    print("Horizon duration penalty calibration summary:")
    if summary.empty:
        print("empty summary")
    else:
        print(
            summary[
                [
                    "scenario_label",
                    "selector_pass",
                    "blockers",
                    "added_count",
                    "added_pnl",
                    "combined_total_pnl",
                    "month_pnl_min",
                    "role_total_pnl_min",
                    "remaining_extra_trades_needed",
                    "remaining_month_pnl_hurdle_sum",
                ]
            ]
            .head(args.print_top)
            .to_string(index=False)
        )
    print(f"artifacts: {run_dir}")
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-monthly-metrics", type=Path, required=True)
    parser.add_argument("--base-trades", type=Path, required=True)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument(
        "--candidate",
        default="q95_sg95_rank90_floor5_side_regime_session_month",
    )
    parser.add_argument(
        "--variant-contains",
        default="loss_exit30_cd15__holdext_isolated_large_loss_long_t-5_h720",
    )
    parser.add_argument("--base-entry-block-rule", default="long_range_normal_ny_fixed60_pred_gt0")
    parser.add_argument("--row-scopes", default="available_candidates,greedy_selected")
    parser.add_argument("--prob-thresholds", default="0.3,0.4,0.5,0.6")
    parser.add_argument("--ev-thresholds", default="-2,0,2")
    parser.add_argument("--tail-prob-thresholds", default="0.3,0.5,0.7")
    parser.add_argument("--require-model-used-options", default="true,false")
    parser.add_argument("--penalty-weights", default=DEFAULT_PENALTY_WEIGHTS)
    parser.add_argument("--fallback-penalty-weight", type=float, default=0.0)
    parser.add_argument("--min-prior-rows", type=int, default=10)
    parser.add_argument("--min-prior-months", type=int, default=2)
    parser.add_argument("--min-chosen-pred-pnl", type=float, default=0.0)
    parser.add_argument("--max-chosen-tail-prob", type=float, default=0.3)
    parser.add_argument("--repair-support-weight", type=float, default=1.0)
    parser.add_argument("--repair-expected-pnl-weight", type=float, default=1.0)
    parser.add_argument("--repair-tail-penalty-weight", type=float, default=1.0)
    parser.add_argument("--target-only", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument(
        "--cap-to-extra-side-needed",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    parser.add_argument("--overlap-keys", default="role")
    parser.add_argument("--min-total-pnl", type=float, default=0.0)
    parser.add_argument("--min-role-total-pnl", type=float, default=0.0)
    parser.add_argument("--month-floor", type=float, default=0.0)
    parser.add_argument("--shallow-month-floor", type=float, default=-1.0)
    parser.add_argument("--min-role-trades", type=int, default=4)
    parser.add_argument("--min-month-trades", type=int, default=1)
    parser.add_argument("--max-side-trade-share", type=float, default=0.95)
    parser.add_argument("--output-dir", type=Path, default=Path("data/reports/backtests"))
    parser.add_argument("--label", default="entry_ev_horizon_duration_penalty_calibration")
    parser.add_argument("--print-top", type=int, default=20)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    run_calibration(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
