#!/usr/bin/env python3
"""Replay support repair with duration-risk priors learned from broad candidates."""

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


DEFAULT_CONTEXT_SPECS = (
    "side,combined_regime,session_regime,near_miss_bucket;"
    "side,combined_regime,session_regime;"
    "side,combined_regime;"
    "side,session_regime;"
    "combined_regime,session_regime;"
    "side;"
    "global"
)
DEFAULT_DURATION_RISK_WEIGHTS = "0,0.05,0.1,0.25,0.5,1.0"


def duration_json_default(value: Any) -> Any:
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


def parse_context_specs(value: str) -> list[list[str]]:
    specs: list[list[str]] = []
    for raw_spec in value.split(";"):
        raw_spec = raw_spec.strip()
        if not raw_spec:
            continue
        if raw_spec.lower() == "global":
            specs.append([])
            continue
        specs.append([column.strip() for column in raw_spec.split(",") if column.strip()])
    return specs or [[]]


def horizon_column(horizon: int | float) -> str:
    return f"side_fixed_{int(float(horizon))}m_adjusted_pnl"


def group_prior_metrics(
    group: pd.DataFrame,
    *,
    horizon: int,
    tail_loss_threshold: float,
) -> dict[str, float]:
    horizon_pnl = numeric_series(group, horizon_column(horizon), default=np.nan)
    fixed60 = numeric_series(group, "side_fixed_60m_adjusted_pnl", default=np.nan)
    valid = horizon_pnl.notna()
    if not valid.any():
        return {
            "prior_count": 0.0,
            "prior_months": 0.0,
            "prior_mean_pnl": np.nan,
            "prior_delta_vs_60_mean": np.nan,
            "prior_loss_rate": np.nan,
            "prior_tail_loss_rate": np.nan,
            "prior_underperform_60_rate": np.nan,
        }
    pnl = horizon_pnl[valid]
    fixed60_valid = fixed60[valid]
    return {
        "prior_count": float(len(pnl)),
        "prior_months": float(group.loc[valid, "month"].astype(str).nunique()),
        "prior_mean_pnl": float(pnl.mean()),
        "prior_delta_vs_60_mean": float((pnl - fixed60_valid).mean()),
        "prior_loss_rate": float(pnl.lt(0.0).mean()),
        "prior_tail_loss_rate": float(pnl.le(tail_loss_threshold).mean()),
        "prior_underperform_60_rate": float(pnl.lt(fixed60_valid).mean()),
    }


def shrink_metric(value: float, global_value: float, count: float, shrinkage_count: float) -> float:
    if not np.isfinite(value):
        return global_value if np.isfinite(global_value) else 0.0
    if shrinkage_count <= 0 or not np.isfinite(global_value):
        return value
    return float((count * value + shrinkage_count * global_value) / (count + shrinkage_count))


def select_duration_prior(
    row: pd.Series,
    prior: pd.DataFrame,
    *,
    context_specs: list[list[str]],
    horizon: int,
    min_prior_rows: int,
    min_prior_months: int,
    shrinkage_count: float,
    tail_loss_threshold: float,
) -> dict[str, Any]:
    if prior.empty:
        return {
            "duration_prior_context_spec": "none",
            "duration_prior_context_key": "",
            "duration_prior_count": 0,
            "duration_prior_months": 0,
            "duration_prior_mean_pnl": 0.0,
            "duration_prior_delta_vs_60_mean": 0.0,
            "duration_prior_loss_rate": 0.0,
            "duration_prior_tail_loss_rate": 0.0,
            "duration_prior_underperform_60_rate": 0.0,
            "duration_prior_used": False,
        }

    global_metrics = group_prior_metrics(
        prior,
        horizon=horizon,
        tail_loss_threshold=tail_loss_threshold,
    )
    selected_group = prior
    selected_spec: list[str] = []
    selected_metrics = global_metrics
    used = False
    for spec in context_specs:
        group = prior
        missing_column = False
        for column in spec:
            if column not in group.columns or column not in row.index:
                missing_column = True
                break
            group = group[group[column].astype(str).eq(str(row[column]))]
        if missing_column:
            continue
        metrics = group_prior_metrics(
            group,
            horizon=horizon,
            tail_loss_threshold=tail_loss_threshold,
        )
        if (
            int(metrics["prior_count"]) >= min_prior_rows
            and int(metrics["prior_months"]) >= min_prior_months
        ):
            selected_group = group
            selected_spec = spec
            selected_metrics = metrics
            used = True
            break

    if not used and int(global_metrics["prior_count"]) > 0:
        selected_group = prior
        selected_spec = []
        selected_metrics = global_metrics
        used = int(global_metrics["prior_months"]) >= min_prior_months

    count = float(selected_metrics["prior_count"])
    mean_pnl = shrink_metric(
        float(selected_metrics["prior_mean_pnl"]),
        float(global_metrics["prior_mean_pnl"]),
        count,
        shrinkage_count,
    )
    delta_vs_60 = shrink_metric(
        float(selected_metrics["prior_delta_vs_60_mean"]),
        float(global_metrics["prior_delta_vs_60_mean"]),
        count,
        shrinkage_count,
    )
    loss_rate = shrink_metric(
        float(selected_metrics["prior_loss_rate"]),
        float(global_metrics["prior_loss_rate"]),
        count,
        shrinkage_count,
    )
    tail_loss_rate = shrink_metric(
        float(selected_metrics["prior_tail_loss_rate"]),
        float(global_metrics["prior_tail_loss_rate"]),
        count,
        shrinkage_count,
    )
    underperform_rate = shrink_metric(
        float(selected_metrics["prior_underperform_60_rate"]),
        float(global_metrics["prior_underperform_60_rate"]),
        count,
        shrinkage_count,
    )
    key = "|".join(str(row[column]) for column in selected_spec) if selected_spec else "global"
    del selected_group
    return {
        "duration_prior_context_spec": ",".join(selected_spec) if selected_spec else "global",
        "duration_prior_context_key": key,
        "duration_prior_count": int(selected_metrics["prior_count"]),
        "duration_prior_months": int(selected_metrics["prior_months"]),
        "duration_prior_mean_pnl": mean_pnl,
        "duration_prior_delta_vs_60_mean": delta_vs_60,
        "duration_prior_loss_rate": loss_rate,
        "duration_prior_tail_loss_rate": tail_loss_rate,
        "duration_prior_underperform_60_rate": underperform_rate,
        "duration_prior_used": bool(used),
    }


def add_duration_prior_columns(
    choices: pd.DataFrame,
    broad_train_rows: pd.DataFrame,
    *,
    context_specs: list[list[str]],
    min_prior_rows: int,
    min_prior_months: int,
    shrinkage_count: float,
    tail_loss_threshold: float,
    negative_pnl_weight: float,
    underperform_weight: float,
    loss_rate_weight: float,
    tail_loss_rate_weight: float,
) -> pd.DataFrame:
    output = choices.copy()
    train = broad_train_rows.copy()
    train_periods = pd.Series(
        pd.PeriodIndex(train["month"].astype(str), freq="M"),
        index=train.index,
    )
    context_columns = sorted({column for spec in context_specs for column in spec})
    key_columns = [
        "month",
        "hv_chosen_horizon_minutes",
        *[column for column in context_columns if column in output.columns],
    ]
    prior_rows: list[dict[str, Any]] = []
    for _, row in output[key_columns].drop_duplicates().iterrows():
        target_period = pd.Period(str(row["month"]), freq="M")
        horizon = int(float(row["hv_chosen_horizon_minutes"]))
        prior = train[train_periods < target_period]
        metrics = select_duration_prior(
            row,
            prior,
            context_specs=context_specs,
            horizon=horizon,
            min_prior_rows=min_prior_rows,
            min_prior_months=min_prior_months,
            shrinkage_count=shrinkage_count,
            tail_loss_threshold=tail_loss_threshold,
        )
        risk_score = (
            negative_pnl_weight * max(0.0, -float(metrics["duration_prior_mean_pnl"]))
            + underperform_weight
            * max(0.0, -float(metrics["duration_prior_delta_vs_60_mean"]))
            + loss_rate_weight * float(metrics["duration_prior_loss_rate"])
            + tail_loss_rate_weight * float(metrics["duration_prior_tail_loss_rate"])
        )
        prior_rows.append(
            {
                **{column: row[column] for column in key_columns},
                **metrics,
                "repair_duration_risk_score": float(risk_score),
            }
        )
    prior_frame = pd.DataFrame(prior_rows)
    return output.merge(prior_frame, on=key_columns, how="left")


def apply_duration_risk_weight(choices: pd.DataFrame, *, risk_weight: float) -> pd.DataFrame:
    output = choices.copy()
    output["duration_risk_weight"] = float(risk_weight)
    output["repair_duration_risk_penalty_amount"] = (
        float(risk_weight) * numeric_series(output, "repair_duration_risk_score", default=0.0)
    )
    return output


def format_weight_label(weight: float) -> str:
    return str(weight).replace("-", "m").replace(".", "p")


def run_replay(args: argparse.Namespace) -> Path:
    row_scopes = parse_csv(args.row_scopes)
    overlap_keys = parse_csv(args.overlap_keys)
    risk_weights = parse_float_csv(args.duration_risk_weights)
    context_specs = parse_context_specs(args.context_specs)
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
        repair_horizon_penalty_weight=args.repair_horizon_penalty_weight,
    )
    broad_train_rows = pd.read_csv(args.broad_train_rows)
    choices = add_duration_prior_columns(
        choices,
        broad_train_rows,
        context_specs=context_specs,
        min_prior_rows=args.min_prior_rows,
        min_prior_months=args.min_prior_months,
        shrinkage_count=args.shrinkage_count,
        tail_loss_threshold=args.tail_loss_threshold,
        negative_pnl_weight=args.negative_pnl_weight,
        underperform_weight=args.underperform_weight,
        loss_rate_weight=args.loss_rate_weight,
        tail_loss_rate_weight=args.tail_loss_rate_weight,
    )

    summary_frames: list[pd.DataFrame] = []
    monthly_frames: list[pd.DataFrame] = []
    addition_frames: list[pd.DataFrame] = []
    rejection_frames: list[pd.DataFrame] = []
    candidate_frames: list[pd.DataFrame] = []
    for risk_weight in risk_weights:
        weighted_choices = apply_duration_risk_weight(choices, risk_weight=risk_weight)
        summary, monthly, additions, rejections = replay_scenarios(
            base_monthly,
            base_trades,
            weighted_choices,
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
            repair_horizon_penalty_weight=args.repair_horizon_penalty_weight,
            min_chosen_pred_pnl=args.min_chosen_pred_pnl,
            min_chosen_actual_pnl=None,
            max_chosen_tail_prob=args.max_chosen_tail_prob,
        )
        label_suffix = f"_durw{format_weight_label(risk_weight)}"
        for frame in [summary, monthly, additions, rejections, weighted_choices]:
            if not frame.empty:
                frame["duration_risk_weight"] = float(risk_weight)
                if "scenario_label" in frame.columns:
                    frame["scenario_label"] = frame["scenario_label"].astype(str) + label_suffix
        summary_frames.append(summary)
        monthly_frames.append(monthly)
        addition_frames.append(additions)
        rejection_frames.append(rejections)
        candidate_frames.append(weighted_choices)

    summary_all = pd.concat(summary_frames, ignore_index=True) if summary_frames else pd.DataFrame()
    monthly_all = pd.concat(monthly_frames, ignore_index=True) if monthly_frames else pd.DataFrame()
    additions_all = (
        pd.concat(addition_frames, ignore_index=True) if addition_frames else pd.DataFrame()
    )
    rejections_all = (
        pd.concat(rejection_frames, ignore_index=True) if rejection_frames else pd.DataFrame()
    )
    candidates_all = (
        pd.concat(candidate_frames, ignore_index=True) if candidate_frames else pd.DataFrame()
    )

    run_dir = make_run_dir(args.output_dir, args.label)
    summary_all.to_csv(run_dir / "broad_duration_prior_replay_summary.csv", index=False)
    monthly_all.to_csv(run_dir / "broad_duration_prior_monthly_metrics.csv", index=False)
    additions_all.to_csv(run_dir / "broad_duration_prior_additions.csv", index=False)
    rejections_all.to_csv(run_dir / "broad_duration_prior_rejections.csv", index=False)
    candidates_all.to_csv(run_dir / "broad_duration_prior_candidates.csv", index=False)
    choices.to_csv(run_dir / "broad_duration_prior_base_candidates.csv", index=False)
    (run_dir / "config.json").write_text(
        json.dumps(
            {
                "base_monthly_metrics": args.base_monthly_metrics,
                "base_trades": args.base_trades,
                "predictions": args.predictions,
                "broad_train_rows": args.broad_train_rows,
                "candidate": args.candidate,
                "variant_contains": args.variant_contains,
                "base_entry_block_rule": args.base_entry_block_rule,
                "row_scopes": row_scopes,
                "target_only": args.target_only,
                "prob_thresholds": parse_float_csv(args.prob_thresholds),
                "ev_thresholds": parse_float_csv(args.ev_thresholds),
                "tail_prob_thresholds": parse_float_csv(args.tail_prob_thresholds),
                "require_model_used_options": parse_bool_csv(args.require_model_used_options),
                "duration_risk_weights": risk_weights,
                "context_specs": context_specs,
                "min_prior_rows": args.min_prior_rows,
                "min_prior_months": args.min_prior_months,
                "shrinkage_count": args.shrinkage_count,
                "tail_loss_threshold": args.tail_loss_threshold,
                "negative_pnl_weight": args.negative_pnl_weight,
                "underperform_weight": args.underperform_weight,
                "loss_rate_weight": args.loss_rate_weight,
                "tail_loss_rate_weight": args.tail_loss_rate_weight,
                "min_chosen_pred_pnl": args.min_chosen_pred_pnl,
                "max_chosen_tail_prob": args.max_chosen_tail_prob,
                "repair_support_weight": args.repair_support_weight,
                "repair_expected_pnl_weight": args.repair_expected_pnl_weight,
                "repair_tail_penalty_weight": args.repair_tail_penalty_weight,
                "repair_horizon_penalty_weight": args.repair_horizon_penalty_weight,
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
            default=duration_json_default,
        ),
        encoding="utf-8",
    )

    print("Broad duration prior replay summary:")
    if summary_all.empty:
        print("empty summary")
    else:
        print(
            summary_all[
                [
                    "duration_risk_weight",
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
    parser.add_argument("--broad-train-rows", type=Path, required=True)
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
    parser.add_argument("--duration-risk-weights", default=DEFAULT_DURATION_RISK_WEIGHTS)
    parser.add_argument("--context-specs", default=DEFAULT_CONTEXT_SPECS)
    parser.add_argument("--min-prior-rows", type=int, default=20)
    parser.add_argument("--min-prior-months", type=int, default=2)
    parser.add_argument("--shrinkage-count", type=float, default=20.0)
    parser.add_argument("--tail-loss-threshold", type=float, default=-5.0)
    parser.add_argument("--negative-pnl-weight", type=float, default=1.0)
    parser.add_argument("--underperform-weight", type=float, default=1.0)
    parser.add_argument("--loss-rate-weight", type=float, default=0.0)
    parser.add_argument("--tail-loss-rate-weight", type=float, default=5.0)
    parser.add_argument("--min-chosen-pred-pnl", type=float, default=0.0)
    parser.add_argument("--max-chosen-tail-prob", type=float, default=0.3)
    parser.add_argument("--repair-support-weight", type=float, default=1.0)
    parser.add_argument("--repair-expected-pnl-weight", type=float, default=1.0)
    parser.add_argument("--repair-tail-penalty-weight", type=float, default=1.0)
    parser.add_argument("--repair-horizon-penalty-weight", type=float, default=0.0)
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
    parser.add_argument("--label", default="entry_ev_broad_duration_prior_repair_replay")
    parser.add_argument("--print-top", type=int, default=20)
    return parser


def main(argv: list[str] | None = None) -> int:
    run_replay(build_parser().parse_args(argv))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
