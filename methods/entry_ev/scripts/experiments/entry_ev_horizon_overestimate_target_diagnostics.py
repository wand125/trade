#!/usr/bin/env python3
"""Diagnose harmful horizon overestimates versus profitable high-variance 720m rows."""

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


DEFAULT_CONTEXT_COLUMNS = "horizon_bucket,side,combined_regime,session_regime,near_miss_bucket"
DEFAULT_MAE_THRESHOLDS = "5,10,15,20,25"
DEFAULT_TAIL_MISS_THRESHOLDS = "0.05,0.10,0.20,0.30"
DEFAULT_BIAS_THRESHOLDS = "0,2,5,10"


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


def numeric_series(frame: pd.DataFrame, column: str, default: float = np.nan) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=float)
    return (
        pd.to_numeric(frame[column], errors="coerce")
        .replace([np.inf, -np.inf], np.nan)
        .fillna(default)
        .astype(float)
    )


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


def normalize_scored_examples(frame: pd.DataFrame) -> pd.DataFrame:
    required = {
        "role",
        "month",
        "side",
        "needed_side",
        "row_scope",
        "horizon_minutes",
        "horizon_bucket",
        "horizon_actual_pnl",
        "horizon_actual_delta_vs_60",
        "ranker_pred_pnl",
        "target_pnl_hurdle",
        "extra_side_needed",
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError("scored examples missing columns: " + ", ".join(missing))
    output = frame.copy()
    for column in [
        "role",
        "family",
        "side",
        "needed_side",
        "row_scope",
        "horizon_bucket",
        "combined_regime",
        "session_regime",
        "near_miss_bucket",
        "duration_prior_context_spec",
        "residual_prior_context_spec",
    ]:
        if column in output.columns:
            output[column] = output[column].fillna("missing").astype(str)
    output["month"] = output["month"].astype(str).str.slice(0, 7)
    for column in [
        "horizon_minutes",
        "horizon_actual_pnl",
        "horizon_actual_delta_vs_60",
        "ranker_pred_pnl",
        "ranker_pred_executable_prob",
        "ranker_pred_tail_loss_prob",
        "target_pnl_hurdle",
        "extra_side_needed",
        "residual_prior_count",
        "residual_prior_months",
        "residual_prior_bias",
        "residual_prior_mae",
        "residual_prior_rmse",
        "residual_prior_overestimate_rate",
        "residual_prior_tail_miss_rate",
        "duration_prior_mean_pnl",
        "duration_prior_delta_vs_60_mean",
        "duration_prior_tail_loss_rate",
        "repair_duration_risk_score",
    ]:
        output[column] = numeric_series(output, column, default=0.0)
    output["ranker_core_model_used"] = bool_series(output, "ranker_core_model_used", default=False)
    output["target_horizon_tail_loss"] = bool_series(
        output,
        "target_horizon_tail_loss",
        default=False,
    )
    return output


def add_target_columns(
    frame: pd.DataFrame,
    *,
    overestimate_threshold: float,
    underperform_60_threshold: float,
    min_executable_pnl: float,
    min_profitable_pnl: float,
    high_variance_mae_threshold: float,
    high_tail_miss_threshold: float,
) -> pd.DataFrame:
    output = normalize_scored_examples(frame)
    support_hurdle = np.maximum(
        numeric_series(output, "target_pnl_hurdle", default=0.0),
        float(min_executable_pnl),
    )
    output["support_hurdle"] = support_hurdle
    output["ranker_overestimate_amount"] = (
        output["ranker_pred_pnl"] - output["horizon_actual_pnl"]
    )
    output["ranker_underestimate_amount"] = (
        output["horizon_actual_pnl"] - output["ranker_pred_pnl"]
    )
    output["predicted_executable"] = output["ranker_pred_pnl"].ge(min_executable_pnl)
    output["model_overestimated"] = output["ranker_overestimate_amount"].ge(
        overestimate_threshold,
    )
    output["actual_below_support_hurdle"] = output["horizon_actual_pnl"].lt(support_hurdle)
    output["actual_underperforms_60"] = output["horizon_actual_delta_vs_60"].le(
        -abs(underperform_60_threshold),
    )
    output["support_needed"] = (
        output["side"].eq(output["needed_side"]) & output["extra_side_needed"].gt(0.0)
    )
    output["support_success"] = output["support_needed"] & output["horizon_actual_pnl"].ge(
        support_hurdle,
    )
    output["harmful_overestimate"] = (
        output["predicted_executable"]
        & output["model_overestimated"]
        & (
            output["actual_below_support_hurdle"]
            | output["actual_underperforms_60"]
            | output["target_horizon_tail_loss"]
        )
    )
    output["support_harmful_overestimate"] = (
        output["support_needed"] & output["harmful_overestimate"] & ~output["support_success"]
    )
    output["high_variance_context"] = (
        output["residual_prior_mae"].ge(high_variance_mae_threshold)
        | output["residual_prior_tail_miss_rate"].ge(high_tail_miss_threshold)
    )
    output["profitable_high_variance_720"] = (
        output["horizon_minutes"].eq(720.0)
        & output["high_variance_context"]
        & output["horizon_actual_pnl"].ge(min_profitable_pnl)
    )
    output["dangerous_high_variance_720"] = (
        output["horizon_minutes"].eq(720.0)
        & output["high_variance_context"]
        & output["harmful_overestimate"]
    )
    output["target_class"] = np.select(
        [
            output["support_harmful_overestimate"],
            output["harmful_overestimate"],
            output["profitable_high_variance_720"],
            output["support_success"],
        ],
        [
            "support_harmful_overestimate",
            "harmful_overestimate",
            "profitable_high_variance_720",
            "support_success",
        ],
        default="other",
    )
    return output


def summarize_group(group: pd.DataFrame) -> dict[str, Any]:
    rows = int(len(group))
    pnl = numeric_series(group, "horizon_actual_pnl", default=0.0)
    harmful = group["harmful_overestimate"].astype(bool)
    support_harmful = group["support_harmful_overestimate"].astype(bool)
    profitable_hv = group["profitable_high_variance_720"].astype(bool)
    dangerous_hv = group["dangerous_high_variance_720"].astype(bool)
    support_needed = group["support_needed"].astype(bool)
    support_success = group["support_success"].astype(bool)
    return {
        "row_count": rows,
        "actual_pnl_sum": float(pnl.sum()),
        "actual_pnl_mean": float(pnl.mean()) if rows else 0.0,
        "ranker_pred_mean": float(numeric_series(group, "ranker_pred_pnl", default=0.0).mean())
        if rows
        else 0.0,
        "overestimate_mean": float(
            numeric_series(group, "ranker_overestimate_amount", default=0.0).mean(),
        )
        if rows
        else 0.0,
        "harmful_count": int(harmful.sum()),
        "harmful_rate": float(harmful.mean()) if rows else 0.0,
        "harmful_pnl": float(pnl.where(harmful, 0.0).sum()),
        "support_needed_count": int(support_needed.sum()),
        "support_success_count": int(support_success.sum()),
        "support_success_pnl": float(pnl.where(support_success, 0.0).sum()),
        "support_harmful_count": int(support_harmful.sum()),
        "support_harmful_pnl": float(pnl.where(support_harmful, 0.0).sum()),
        "profitable_hv720_count": int(profitable_hv.sum()),
        "profitable_hv720_pnl": float(pnl.where(profitable_hv, 0.0).sum()),
        "dangerous_hv720_count": int(dangerous_hv.sum()),
        "dangerous_hv720_pnl": float(pnl.where(dangerous_hv, 0.0).sum()),
        "residual_mae_mean": float(numeric_series(group, "residual_prior_mae", default=0.0).mean())
        if rows
        else 0.0,
        "residual_tail_miss_mean": float(
            numeric_series(group, "residual_prior_tail_miss_rate", default=0.0).mean(),
        )
        if rows
        else 0.0,
    }


def summarize_by(frame: pd.DataFrame, group_columns: list[str]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for keys, group in frame.groupby(group_columns, dropna=False):
        if not isinstance(keys, tuple):
            keys = (keys,)
        row = dict(zip(group_columns, keys, strict=True))
        row.update(summarize_group(group))
        rows.append(row)
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(
        ["harmful_pnl", "dangerous_hv720_pnl", "profitable_hv720_pnl"],
        ascending=[True, True, False],
    ).reset_index(drop=True)


def threshold_rule_summary(
    frame: pd.DataFrame,
    *,
    mae_thresholds: list[float],
    tail_miss_thresholds: list[float],
    bias_thresholds: list[float],
) -> pd.DataFrame:
    rules: list[tuple[str, pd.Series]] = []
    for threshold in mae_thresholds:
        rules.append((f"residual_mae_ge_{threshold:g}", frame["residual_prior_mae"].ge(threshold)))
    for threshold in tail_miss_thresholds:
        rules.append(
            (
                f"residual_tail_miss_ge_{threshold:g}",
                frame["residual_prior_tail_miss_rate"].ge(threshold),
            ),
        )
    for threshold in bias_thresholds:
        rules.append(
            (
                f"residual_positive_bias_ge_{threshold:g}",
                frame["residual_prior_bias"].ge(threshold),
            ),
        )
    rules.append(
        (
            "residual_mae_ge10_or_tail_miss_ge0p1",
            frame["residual_prior_mae"].ge(10.0)
            | frame["residual_prior_tail_miss_rate"].ge(0.10),
        ),
    )
    rules.append(
        (
            "positive_bias_and_tail_miss_ge0p1",
            frame["residual_prior_bias"].gt(0.0)
            & frame["residual_prior_tail_miss_rate"].ge(0.10),
        ),
    )

    rows: list[dict[str, Any]] = []
    total_harmful = int(frame["harmful_overestimate"].sum())
    total_profitable = int(frame["profitable_high_variance_720"].sum())
    for scope_name, scope_mask in {
        "all": pd.Series(True, index=frame.index),
        "720m": frame["horizon_minutes"].eq(720.0),
        "support_needed": frame["support_needed"].astype(bool),
    }.items():
        scoped = frame[scope_mask].copy()
        if scoped.empty:
            continue
        scoped_pnl = numeric_series(scoped, "horizon_actual_pnl", default=0.0)
        for rule_name, full_mask in rules:
            flag = full_mask.reindex(scoped.index).fillna(False).astype(bool)
            harmful = scoped["harmful_overestimate"].astype(bool)
            profitable = scoped["profitable_high_variance_720"].astype(bool)
            rows.append(
                {
                    "scope": scope_name,
                    "rule": rule_name,
                    "row_count": int(len(scoped)),
                    "flagged_count": int(flag.sum()),
                    "flagged_share": float(flag.mean()) if len(scoped) else 0.0,
                    "flagged_pnl": float(scoped_pnl.where(flag, 0.0).sum()),
                    "flagged_harmful_count": int((flag & harmful).sum()),
                    "flagged_harmful_pnl": float(scoped_pnl.where(flag & harmful, 0.0).sum()),
                    "harmful_precision": float((flag & harmful).sum() / flag.sum())
                    if int(flag.sum())
                    else 0.0,
                    "harmful_recall_all": float((flag & harmful).sum() / total_harmful)
                    if total_harmful
                    else 0.0,
                    "flagged_profitable_hv720_count": int((flag & profitable).sum()),
                    "flagged_profitable_hv720_pnl": float(
                        scoped_pnl.where(flag & profitable, 0.0).sum(),
                    ),
                    "profitable_hv720_damage_rate": float((flag & profitable).sum() / total_profitable)
                    if total_profitable
                    else 0.0,
                },
            )
    return pd.DataFrame(rows).sort_values(
        ["scope", "flagged_harmful_pnl", "flagged_profitable_hv720_pnl"],
        ascending=[True, True, True],
    ).reset_index(drop=True)


def selection_summary(additions: pd.DataFrame, *, args: argparse.Namespace) -> pd.DataFrame:
    if additions.empty:
        return pd.DataFrame()
    output = additions.copy()
    for column in ["ranker_score_mode", "scenario_label", "selection_mode", "side"]:
        if column in output.columns:
            output[column] = output[column].fillna("missing").astype(str)
    for column in [
        "hv_chosen_horizon_minutes",
        "hv_chosen_pred_pnl",
        "actual_pnl_at_hv_chosen_horizon",
        "side_fixed_60m_adjusted_pnl",
        "adjusted_pnl",
        "target_pnl_hurdle",
        "extra_side_needed",
    ]:
        output[column] = numeric_series(output, column, default=0.0)
    output["chosen_overestimate_amount"] = (
        output["hv_chosen_pred_pnl"] - output["actual_pnl_at_hv_chosen_horizon"]
    )
    output["chosen_actual_delta_vs_60"] = (
        output["actual_pnl_at_hv_chosen_horizon"] - output["side_fixed_60m_adjusted_pnl"]
    )
    support_hurdle = np.maximum(output["target_pnl_hurdle"], float(args.min_executable_pnl))
    output["chosen_harmful_overestimate"] = (
        output["hv_chosen_pred_pnl"].ge(args.min_executable_pnl)
        & output["chosen_overestimate_amount"].ge(args.overestimate_threshold)
        & (
            output["actual_pnl_at_hv_chosen_horizon"].lt(support_hurdle)
            | output["chosen_actual_delta_vs_60"].le(-abs(args.underperform_60_threshold))
        )
    )
    output["chosen_profitable_720"] = (
        output["hv_chosen_horizon_minutes"].eq(720.0)
        & output["actual_pnl_at_hv_chosen_horizon"].ge(args.min_profitable_pnl)
    )
    rows: list[dict[str, Any]] = []
    for keys, group in output.groupby(["ranker_score_mode", "selection_mode"], dropna=False):
        if not isinstance(keys, tuple):
            keys = (keys,)
        pnl = numeric_series(group, "adjusted_pnl", default=0.0)
        harmful = group["chosen_harmful_overestimate"].astype(bool)
        profitable = group["chosen_profitable_720"].astype(bool)
        rows.append(
            {
                "ranker_score_mode": keys[0],
                "selection_mode": keys[1],
                "addition_rows": int(len(group)),
                "adjusted_pnl_sum": float(pnl.sum()),
                "adjusted_pnl_mean": float(pnl.mean()) if len(group) else 0.0,
                "harmful_count": int(harmful.sum()),
                "harmful_pnl": float(pnl.where(harmful, 0.0).sum()),
                "profitable_720_count": int(profitable.sum()),
                "profitable_720_pnl": float(pnl.where(profitable, 0.0).sum()),
                "h60_count": int(group["hv_chosen_horizon_minutes"].eq(60.0).sum()),
                "h240_count": int(group["hv_chosen_horizon_minutes"].eq(240.0).sum()),
                "h720_count": int(group["hv_chosen_horizon_minutes"].eq(720.0).sum()),
            },
        )
    return pd.DataFrame(rows).sort_values(
        ["ranker_score_mode", "adjusted_pnl_sum"],
        ascending=[True, False],
    ).reset_index(drop=True)


def build_diagnostics(args: argparse.Namespace) -> Path:
    scored = pd.read_csv(args.scored_examples)
    context_columns = parse_csv(args.context_columns)
    missing_context = sorted(set(context_columns) - set(scored.columns))
    if missing_context:
        raise ValueError("context columns missing: " + ", ".join(missing_context))

    targets = add_target_columns(
        scored,
        overestimate_threshold=args.overestimate_threshold,
        underperform_60_threshold=args.underperform_60_threshold,
        min_executable_pnl=args.min_executable_pnl,
        min_profitable_pnl=args.min_profitable_pnl,
        high_variance_mae_threshold=args.high_variance_mae_threshold,
        high_tail_miss_threshold=args.high_tail_miss_threshold,
    )
    overall = summarize_by(targets, ["row_scope", "horizon_bucket"])
    role_month = summarize_by(targets, ["role", "month", "horizon_bucket"])
    context = summarize_by(targets, context_columns)
    threshold_summary = threshold_rule_summary(
        targets,
        mae_thresholds=parse_float_csv(args.mae_thresholds),
        tail_miss_thresholds=parse_float_csv(args.tail_miss_thresholds),
        bias_thresholds=parse_float_csv(args.bias_thresholds),
    )
    additions_summary = pd.DataFrame()
    if args.additions:
        additions = pd.read_csv(args.additions)
        additions_summary = selection_summary(additions, args=args)

    run_dir = make_run_dir(Path(args.output_dir), args.label)
    targets.to_csv(run_dir / "horizon_overestimate_target_examples.csv", index=False)
    overall.to_csv(run_dir / "horizon_overestimate_overall_summary.csv", index=False)
    role_month.to_csv(run_dir / "horizon_overestimate_role_month_summary.csv", index=False)
    context.to_csv(run_dir / "horizon_overestimate_context_summary.csv", index=False)
    threshold_summary.to_csv(run_dir / "horizon_overestimate_threshold_summary.csv", index=False)
    additions_summary.to_csv(run_dir / "horizon_overestimate_additions_summary.csv", index=False)
    (run_dir / "config.json").write_text(
        json.dumps(vars(args), indent=2, default=local_json_default, sort_keys=True),
        encoding="utf-8",
    )

    print("Horizon overestimate target overall summary:")
    print(overall.head(args.print_rows).to_string(index=False))
    print("\nThreshold sensitivity:")
    print(threshold_summary.head(args.print_rows).to_string(index=False))
    if not additions_summary.empty:
        print("\nAdditions summary:")
        print(additions_summary.head(args.print_rows).to_string(index=False))
    print(f"artifacts: {run_dir}")
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scored-examples", required=True)
    parser.add_argument("--additions")
    parser.add_argument("--context-columns", default=DEFAULT_CONTEXT_COLUMNS)
    parser.add_argument("--overestimate-threshold", type=float, default=2.0)
    parser.add_argument("--underperform-60-threshold", type=float, default=2.0)
    parser.add_argument("--min-executable-pnl", type=float, default=0.0)
    parser.add_argument("--min-profitable-pnl", type=float, default=5.0)
    parser.add_argument("--high-variance-mae-threshold", type=float, default=10.0)
    parser.add_argument("--high-tail-miss-threshold", type=float, default=0.10)
    parser.add_argument("--mae-thresholds", default=DEFAULT_MAE_THRESHOLDS)
    parser.add_argument("--tail-miss-thresholds", default=DEFAULT_TAIL_MISS_THRESHOLDS)
    parser.add_argument("--bias-thresholds", default=DEFAULT_BIAS_THRESHOLDS)
    parser.add_argument("--output-dir", default="data/reports/backtests")
    parser.add_argument("--label", default="entry_ev_horizon_overestimate_target_diagnostics")
    parser.add_argument("--print-rows", type=int, default=20)
    return parser


def main() -> None:
    build_diagnostics(build_parser().parse_args())


if __name__ == "__main__":
    main()
