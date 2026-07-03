#!/usr/bin/env python3
"""Diagnose replacement candidates for thin or losing support-repair months."""

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

from entry_ev_support_repair_listwise_cluster_diagnostics import (  # noqa: E402
    prepare_stateful_universe,
)
from entry_ev_support_repair_pairwise_switch_diagnostics import (  # noqa: E402
    bool_series,
    choose_scenario,
    numeric_series,
    parse_csv,
    text_series,
)


DEFAULT_INCLUDE_REJECT_REASONS = "quota_full,overlap,pred_pnl_floor"
DEFAULT_EXTERNAL_ROW_SCOPES = "available_candidates"
DEFAULT_EXAMPLE_COLUMNS = [
    "target_key",
    "target_reason",
    "target_needed_side",
    "candidate_rank_by_pred_pnl",
    "candidate_key",
    "selection_status",
    "reject_reason",
    "role",
    "family",
    "month",
    "side",
    "decision_timestamp",
    "hv_chosen_horizon_minutes",
    "hv_chosen_pred_pnl",
    "hv_chosen_pred_executable_prob",
    "hv_chosen_pred_tail_loss_prob",
    "hv_chosen_pred_harmful_overestimate_prob",
    "hv_chosen_pred_model_used_bool",
    "pred_fixed_best_horizon_minutes",
    "singleton_720_pred_pnl_lt2",
    "strict_pass",
    "strict_guarded_pass",
    "relaxed_pass",
    "relaxed_guarded_pass",
    "actual_pnl_at_hv_chosen_horizon",
    "repair_score",
]
EXTERNAL_HORIZON_REQUIRED_COLUMNS = {
    "role",
    "month",
    "decision_timestamp",
    "side",
    "horizon_minutes",
    "actual_pnl",
    "pred_executable_prob",
    "pred_pnl",
    "pred_tail_loss_prob",
    "pred_model_used",
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


def infer_needed_side(long_count: float, short_count: float) -> str:
    if long_count < short_count:
        return "long"
    if short_count < long_count:
        return "short"
    return "both"


def normalize_monthly_metrics(monthly: pd.DataFrame) -> pd.DataFrame:
    required = {
        "scenario_label",
        "role",
        "family",
        "month",
        "total_adjusted_pnl",
        "trade_count",
        "long_trade_count",
        "short_trade_count",
        "max_side_trade_share",
    }
    missing = sorted(required - set(monthly.columns))
    if missing:
        raise ValueError("monthly metrics missing columns: " + ", ".join(missing))
    output = monthly.copy()
    for column in ["scenario_label", "role", "family"]:
        output[column] = text_series(output, column)
    output["month"] = output["month"].astype(str).str.slice(0, 7)
    for column in [
        "total_adjusted_pnl",
        "trade_count",
        "long_trade_count",
        "short_trade_count",
        "max_side_trade_share",
        "max_drawdown",
    ]:
        output[column] = numeric_series(output, column)
    return output.reset_index(drop=True)


def select_target_months(
    monthly: pd.DataFrame,
    *,
    scenario_label: str,
    month_pnl_floor: float,
    min_month_trades: float,
    max_side_share: float,
) -> pd.DataFrame:
    output = normalize_monthly_metrics(monthly)
    output = output[output["scenario_label"].astype(str).eq(str(scenario_label))].copy()
    if output.empty:
        raise ValueError(f"no monthly metrics for scenario_label={scenario_label}")

    reasons: list[str] = []
    for _, row in output.iterrows():
        row_reasons: list[str] = []
        if float(row["total_adjusted_pnl"]) < month_pnl_floor:
            row_reasons.append("month_pnl_below_floor")
        if float(row["trade_count"]) < min_month_trades:
            row_reasons.append("month_trades_low")
        if (
            float(row["trade_count"]) > 0.0
            and float(row["max_side_trade_share"]) > max_side_share
        ):
            row_reasons.append("side_share_high")
        reasons.append(",".join(row_reasons))

    output["target_reason"] = reasons
    output = output[output["target_reason"].ne("")].copy()
    output["target_needed_side"] = [
        infer_needed_side(long_count, short_count)
        for long_count, short_count in zip(
            output["long_trade_count"],
            output["short_trade_count"],
            strict=True,
        )
    ]
    output["target_key"] = output["role"].astype(str) + "|" + output["month"].astype(str)
    return output.sort_values(
        ["total_adjusted_pnl", "trade_count", "role", "month"],
        kind="mergesort",
    ).reset_index(drop=True)


def candidate_key(frame: pd.DataFrame) -> pd.Series:
    timestamp = pd.to_datetime(
        frame["decision_timestamp"],
        utc=True,
        errors="coerce",
    ).dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    horizon = numeric_series(frame, "hv_chosen_horizon_minutes").round(6).astype(str)
    return (
        text_series(frame, "role")
        + "|"
        + text_series(frame, "month")
        + "|"
        + text_series(frame, "side")
        + "|"
        + timestamp.fillna("")
        + "|"
        + horizon
    )


def add_candidate_diagnostic_columns(
    frame: pd.DataFrame,
    *,
    strict_min_prob: float,
    strict_min_pred_pnl: float,
    strict_max_tail_prob: float,
    relaxed_min_pred_pnl: float,
) -> pd.DataFrame:
    output = frame.copy()
    output["candidate_key"] = candidate_key(output)
    output["hv_chosen_pred_model_used_bool"] = bool_series(
        output,
        "hv_chosen_pred_model_used",
        default=False,
    )
    output["hv_chosen_pred_pnl"] = numeric_series(output, "hv_chosen_pred_pnl")
    output["hv_chosen_pred_executable_prob"] = numeric_series(
        output,
        "hv_chosen_pred_executable_prob",
    )
    output["hv_chosen_pred_tail_loss_prob"] = numeric_series(
        output,
        "hv_chosen_pred_tail_loss_prob",
    )
    output["hv_chosen_horizon_minutes"] = numeric_series(
        output,
        "hv_chosen_horizon_minutes",
    )
    output["actual_pnl_at_hv_chosen_horizon"] = numeric_series(
        output,
        "actual_pnl_at_hv_chosen_horizon",
    )
    output["repair_score"] = numeric_series(output, "repair_score")
    output["pred_fixed_best_horizon_minutes"] = numeric_series(
        output,
        "pred_fixed_best_horizon_minutes",
        default=np.nan,
    )
    output["singleton_720_pred_pnl_lt2"] = (
        output["hv_chosen_horizon_minutes"].round().eq(720.0)
        & output["hv_chosen_pred_pnl"].lt(2.0)
    )

    model = output["hv_chosen_pred_model_used_bool"]
    prob = output["hv_chosen_pred_executable_prob"].ge(strict_min_prob)
    tail = output["hv_chosen_pred_tail_loss_prob"].le(strict_max_tail_prob)
    strict_ev = output["hv_chosen_pred_pnl"].ge(strict_min_pred_pnl)
    relaxed_ev = output["hv_chosen_pred_pnl"].ge(relaxed_min_pred_pnl)
    guard = ~output["singleton_720_pred_pnl_lt2"]
    output["strict_pass"] = model & prob & strict_ev & tail
    output["strict_guarded_pass"] = output["strict_pass"] & guard
    output["relaxed_pass"] = model & prob & relaxed_ev & tail
    output["relaxed_guarded_pass"] = output["relaxed_pass"] & guard
    return output.reset_index(drop=True)


def normalize_external_horizon_candidates(
    frame: pd.DataFrame,
    *,
    scenario_label: str,
    row_scopes: list[str],
) -> pd.DataFrame:
    missing = sorted(EXTERNAL_HORIZON_REQUIRED_COLUMNS - set(frame.columns))
    if missing:
        raise ValueError("external horizon candidates missing columns: " + ", ".join(missing))
    output = frame.copy()
    if row_scopes and "row_scope" in output.columns:
        output = output[text_series(output, "row_scope").isin(row_scopes)].copy()
    if output.empty:
        return pd.DataFrame()
    output["scenario_label"] = scenario_label
    output["family"] = text_series(output, "family", default="")
    output["role"] = text_series(output, "role")
    output["month"] = output["month"].astype(str).str.slice(0, 7)
    output["side"] = text_series(output, "side")
    output["decision_timestamp"] = pd.to_datetime(
        output["decision_timestamp"],
        utc=True,
        errors="coerce",
    )
    output = output[output["decision_timestamp"].notna()].copy()
    output["hv_chosen_horizon_minutes"] = numeric_series(output, "horizon_minutes")
    output["actual_pnl_at_hv_chosen_horizon"] = numeric_series(output, "actual_pnl")
    output["hv_chosen_pred_pnl"] = numeric_series(output, "pred_pnl")
    output["hv_chosen_pred_executable_prob"] = numeric_series(
        output,
        "pred_executable_prob",
    )
    output["hv_chosen_pred_tail_loss_prob"] = numeric_series(
        output,
        "pred_tail_loss_prob",
    )
    output["hv_chosen_pred_model_used"] = bool_series(output, "pred_model_used")
    output["repair_score"] = (
        output["hv_chosen_pred_pnl"] * output["hv_chosen_pred_executable_prob"]
    )
    output["selection_status"] = "external_horizon"
    if "row_scope" in output.columns:
        output["reject_reason"] = "external_" + text_series(output, "row_scope")
    else:
        output["reject_reason"] = "external_horizon"
    output["current_selected"] = False
    output["needed_side"] = text_series(output, "needed_side", default="")
    output["extra_side_needed"] = numeric_series(output, "extra_side_needed", default=0.0)
    output["pred_fixed_best_horizon_minutes"] = numeric_series(
        output,
        "target_fixed_best_horizon_minutes",
        default=np.nan,
    )
    output["candidate_id"] = np.arange(len(output), dtype=int)
    return output.reset_index(drop=True)


def unique_candidates(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    output = frame.copy()
    output["current_selected_sort"] = bool_series(
        output,
        "current_selected",
        default=False,
    ).astype(int)
    return (
        output.sort_values(
            [
                "candidate_key",
                "current_selected_sort",
                "selection_status",
                "reject_reason",
            ],
            ascending=[True, False, True, True],
            kind="mergesort",
        )
        .drop_duplicates("candidate_key", keep="first")
        .drop(columns=["current_selected_sort"])
        .reset_index(drop=True)
    )


def prefixed_stats(frame: pd.DataFrame, *, prefix: str) -> dict[str, Any]:
    unique = unique_candidates(frame)
    actual = numeric_series(unique, "actual_pnl_at_hv_chosen_horizon")
    positive = actual.gt(0.0)
    return {
        f"{prefix}_row_count": int(len(frame)),
        f"{prefix}_unique_count": int(len(unique)),
        f"{prefix}_current_selected_count": int(
            bool_series(unique, "current_selected", default=False).sum()
        ),
        f"{prefix}_model_used_unique_count": int(
            bool_series(unique, "hv_chosen_pred_model_used_bool", default=False).sum()
        ),
        f"{prefix}_strict_pass_unique_count": int(
            bool_series(unique, "strict_pass", default=False).sum()
        ),
        f"{prefix}_strict_guarded_pass_unique_count": int(
            bool_series(unique, "strict_guarded_pass", default=False).sum()
        ),
        f"{prefix}_relaxed_pass_unique_count": int(
            bool_series(unique, "relaxed_pass", default=False).sum()
        ),
        f"{prefix}_relaxed_guarded_pass_unique_count": int(
            bool_series(unique, "relaxed_guarded_pass", default=False).sum()
        ),
        f"{prefix}_singleton_guard_flag_unique_count": int(
            bool_series(unique, "singleton_720_pred_pnl_lt2", default=False).sum()
        ),
        f"{prefix}_oracle_positive_unique_count": int(positive.sum()),
        f"{prefix}_oracle_positive_actual_sum": float(actual[positive].sum())
        if len(unique)
        else 0.0,
        f"{prefix}_oracle_best_actual": float(actual.max()) if len(unique) else np.nan,
        f"{prefix}_oracle_worst_actual": float(actual.min()) if len(unique) else np.nan,
    }


def top_observable_candidate(
    frame: pd.DataFrame,
    *,
    prefix: str,
    sort_columns: list[str],
    ascending: list[bool],
) -> dict[str, Any]:
    unique = unique_candidates(frame)
    if unique.empty:
        return {
            f"{prefix}_candidate_key": "",
            f"{prefix}_side": "",
            f"{prefix}_decision_timestamp": "",
            f"{prefix}_horizon_minutes": np.nan,
            f"{prefix}_pred_pnl": np.nan,
            f"{prefix}_prob": np.nan,
            f"{prefix}_tail_prob": np.nan,
            f"{prefix}_model_used": False,
            f"{prefix}_singleton_720_pred_pnl_lt2": False,
            f"{prefix}_actual_pnl": np.nan,
            f"{prefix}_selection_status": "",
            f"{prefix}_reject_reason": "",
        }
    existing_columns = [column for column in sort_columns if column in unique.columns]
    existing_ascending = [
        direction
        for column, direction in zip(sort_columns, ascending, strict=True)
        if column in unique.columns
    ]
    if not existing_columns:
        existing_columns = ["decision_timestamp"]
        existing_ascending = [True]
    top = unique.sort_values(
        existing_columns,
        ascending=existing_ascending,
        kind="mergesort",
    ).iloc[0]
    timestamp = pd.to_datetime(top["decision_timestamp"], utc=True, errors="coerce")
    timestamp_text = "" if pd.isna(timestamp) else timestamp.strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        f"{prefix}_candidate_key": top.get("candidate_key", ""),
        f"{prefix}_side": top.get("side", ""),
        f"{prefix}_decision_timestamp": timestamp_text,
        f"{prefix}_horizon_minutes": float(top.get("hv_chosen_horizon_minutes", np.nan)),
        f"{prefix}_pred_pnl": float(top.get("hv_chosen_pred_pnl", np.nan)),
        f"{prefix}_prob": float(top.get("hv_chosen_pred_executable_prob", np.nan)),
        f"{prefix}_tail_prob": float(top.get("hv_chosen_pred_tail_loss_prob", np.nan)),
        f"{prefix}_model_used": bool(top.get("hv_chosen_pred_model_used_bool", False)),
        f"{prefix}_singleton_720_pred_pnl_lt2": bool(
            top.get("singleton_720_pred_pnl_lt2", False)
        ),
        f"{prefix}_actual_pnl": float(top.get("actual_pnl_at_hv_chosen_horizon", np.nan)),
        f"{prefix}_selection_status": top.get("selection_status", ""),
        f"{prefix}_reject_reason": top.get("reject_reason", ""),
    }


def summarize_target_candidates(
    targets: pd.DataFrame,
    candidates: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, target in targets.iterrows():
        role = str(target["role"])
        month = str(target["month"])
        side = str(target["target_needed_side"])
        full_pool = candidates[
            text_series(candidates, "role").eq(role)
            & text_series(candidates, "month").eq(month)
        ].copy()
        needed_pool = (
            full_pool.copy()
            if side == "both"
            else full_pool[text_series(full_pool, "side").eq(side)].copy()
        )
        row: dict[str, Any] = {
            "target_key": target["target_key"],
            "scenario_label": target["scenario_label"],
            "role": role,
            "family": target["family"],
            "month": month,
            "target_reason": target["target_reason"],
            "target_needed_side": side,
            "target_total_adjusted_pnl": float(target["total_adjusted_pnl"]),
            "target_trade_count": float(target["trade_count"]),
            "target_long_trade_count": float(target["long_trade_count"]),
            "target_short_trade_count": float(target["short_trade_count"]),
            "target_max_side_trade_share": float(target["max_side_trade_share"]),
        }
        row.update(prefixed_stats(full_pool, prefix="all_side"))
        row.update(prefixed_stats(needed_pool, prefix="needed_side"))
        row.update(
            top_observable_candidate(
                needed_pool,
                prefix="needed_top_pred_pnl",
                sort_columns=[
                    "hv_chosen_pred_pnl",
                    "hv_chosen_pred_executable_prob",
                    "repair_score",
                    "decision_timestamp",
                ],
                ascending=[False, False, False, True],
            )
        )
        strict_pool = needed_pool[bool_series(needed_pool, "strict_guarded_pass")]
        row.update(
            top_observable_candidate(
                strict_pool,
                prefix="needed_top_strict_guarded",
                sort_columns=[
                    "hv_chosen_pred_pnl",
                    "hv_chosen_pred_executable_prob",
                    "repair_score",
                    "decision_timestamp",
                ],
                ascending=[False, False, False, True],
            )
        )
        relaxed_pool = needed_pool[bool_series(needed_pool, "relaxed_guarded_pass")]
        row.update(
            top_observable_candidate(
                relaxed_pool,
                prefix="needed_top_relaxed_guarded",
                sort_columns=[
                    "hv_chosen_pred_pnl",
                    "hv_chosen_pred_executable_prob",
                    "repair_score",
                    "decision_timestamp",
                ],
                ascending=[False, False, False, True],
            )
        )
        row.update(
            top_observable_candidate(
                needed_pool,
                prefix="needed_top_tail_low",
                sort_columns=[
                    "hv_chosen_pred_tail_loss_prob",
                    "hv_chosen_pred_pnl",
                    "repair_score",
                    "decision_timestamp",
                ],
                ascending=[True, False, False, True],
            )
        )
        row.update(
            top_observable_candidate(
                needed_pool,
                prefix="needed_top_oracle_actual",
                sort_columns=[
                    "actual_pnl_at_hv_chosen_horizon",
                    "hv_chosen_pred_pnl",
                    "repair_score",
                    "decision_timestamp",
                ],
                ascending=[False, False, False, True],
            )
        )
        rows.append(row)
    return pd.DataFrame(rows)


def candidate_examples(
    targets: pd.DataFrame,
    candidates: pd.DataFrame,
    *,
    top_n: int,
) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for _, target in targets.iterrows():
        role = str(target["role"])
        month = str(target["month"])
        side = str(target["target_needed_side"])
        pool = candidates[
            text_series(candidates, "role").eq(role)
            & text_series(candidates, "month").eq(month)
        ].copy()
        if side != "both":
            pool = pool[text_series(pool, "side").eq(side)].copy()
        pool = unique_candidates(pool)
        if pool.empty:
            continue
        pool = pool.sort_values(
            [
                "hv_chosen_pred_pnl",
                "hv_chosen_pred_executable_prob",
                "repair_score",
                "decision_timestamp",
            ],
            ascending=[False, False, False, True],
            kind="mergesort",
        ).head(top_n)
        pool.insert(0, "candidate_rank_by_pred_pnl", np.arange(1, len(pool) + 1))
        pool.insert(0, "target_needed_side", target["target_needed_side"])
        pool.insert(0, "target_reason", target["target_reason"])
        pool.insert(0, "target_key", target["target_key"])
        frames.append(pool)
    if not frames:
        return pd.DataFrame(columns=DEFAULT_EXAMPLE_COLUMNS)
    output = pd.concat(frames, ignore_index=True, sort=False)
    columns = [column for column in DEFAULT_EXAMPLE_COLUMNS if column in output.columns]
    return output[columns].reset_index(drop=True)


def overall_summary(
    targets: pd.DataFrame,
    candidates: pd.DataFrame,
    target_summary: pd.DataFrame,
    *,
    scenario_label: str,
) -> pd.DataFrame:
    target_keys = set(targets["target_key"].astype(str))
    target_pool = candidates[
        (text_series(candidates, "role") + "|" + text_series(candidates, "month")).isin(
            target_keys,
        )
    ].copy()
    unique_pool = unique_candidates(target_pool)
    row: dict[str, Any] = {
        "scenario_label": scenario_label,
        "target_count": int(len(targets)),
        "target_pnl_sum": float(numeric_series(targets, "total_adjusted_pnl").sum()),
        "target_trade_count_sum": float(numeric_series(targets, "trade_count").sum()),
        "target_month_pnl_min": float(numeric_series(targets, "total_adjusted_pnl").min())
        if len(targets)
        else np.nan,
    }
    row.update(prefixed_stats(target_pool, prefix="target_pool"))
    for column in [
        "needed_top_pred_pnl_actual_pnl",
        "needed_top_strict_guarded_actual_pnl",
        "needed_top_relaxed_guarded_actual_pnl",
        "needed_top_tail_low_actual_pnl",
        "needed_top_oracle_actual_actual_pnl",
    ]:
        values = numeric_series(target_summary, column, default=np.nan)
        row[f"{column}_sum"] = float(values.sum(skipna=True)) if len(values) else 0.0
        row[f"{column}_positive_count"] = int(values.gt(0.0).sum()) if len(values) else 0
    row["target_pool_unique_actual_sum"] = float(
        numeric_series(unique_pool, "actual_pnl_at_hv_chosen_horizon").sum()
    )
    return pd.DataFrame([row])


def run_diagnostics(args: argparse.Namespace) -> Path:
    monthly = pd.read_csv(args.monthly_metrics)
    additions = pd.read_csv(args.additions)
    rejections = pd.read_csv(args.rejections) if args.rejections else pd.DataFrame()
    summary = pd.read_csv(args.summary) if args.summary else pd.DataFrame()
    scenario = choose_scenario(summary, args.scenario_label)

    targets = select_target_months(
        monthly,
        scenario_label=scenario,
        month_pnl_floor=args.month_pnl_floor,
        min_month_trades=args.min_month_trades,
        max_side_share=args.max_side_share,
    )
    universe = prepare_stateful_universe(
        additions,
        rejections,
        scenario_label=scenario,
        include_reject_reasons=parse_csv(args.include_reject_reasons),
    )
    if args.external_horizon_candidates:
        external = normalize_external_horizon_candidates(
            pd.read_csv(args.external_horizon_candidates),
            scenario_label=scenario,
            row_scopes=parse_csv(args.external_row_scopes),
        )
        if not external.empty:
            universe = pd.concat([universe, external], ignore_index=True, sort=False)
    universe = add_candidate_diagnostic_columns(
        universe,
        strict_min_prob=args.strict_min_prob,
        strict_min_pred_pnl=args.strict_min_pred_pnl,
        strict_max_tail_prob=args.strict_max_tail_prob,
        relaxed_min_pred_pnl=args.relaxed_min_pred_pnl,
    )
    target_summary = summarize_target_candidates(targets, universe)
    examples = candidate_examples(targets, universe, top_n=args.top_n)
    overall = overall_summary(
        targets,
        universe,
        target_summary,
        scenario_label=scenario,
    )

    run_dir = make_run_dir(args.output_dir, args.label)
    targets.to_csv(run_dir / "thin_month_targets.csv", index=False)
    target_summary.to_csv(run_dir / "thin_month_candidate_summary.csv", index=False)
    examples.to_csv(run_dir / "thin_month_candidate_examples.csv", index=False)
    overall.to_csv(run_dir / "thin_month_overall_summary.csv", index=False)
    universe.to_csv(run_dir / "thin_month_candidate_universe.csv", index=False)
    (run_dir / "config.json").write_text(
        json.dumps(
            {
                "monthly_metrics": args.monthly_metrics,
                "additions": args.additions,
                "rejections": args.rejections,
                "summary": args.summary,
                "external_horizon_candidates": args.external_horizon_candidates,
                "external_row_scopes": parse_csv(args.external_row_scopes),
                "scenario_label": scenario,
                "include_reject_reasons": parse_csv(args.include_reject_reasons),
                "month_pnl_floor": args.month_pnl_floor,
                "min_month_trades": args.min_month_trades,
                "max_side_share": args.max_side_share,
                "strict_min_prob": args.strict_min_prob,
                "strict_min_pred_pnl": args.strict_min_pred_pnl,
                "strict_max_tail_prob": args.strict_max_tail_prob,
                "relaxed_min_pred_pnl": args.relaxed_min_pred_pnl,
                "top_n": args.top_n,
            },
            indent=2,
            sort_keys=True,
            default=local_json_default,
        )
        + "\n",
        encoding="utf-8",
    )

    print("Support repair thin-month candidate diagnostics:")
    print(f"scenario_label: {scenario}")
    print(overall.to_string(index=False))
    print(f"targets: {len(targets)}")
    print(f"artifacts: {run_dir}")
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--monthly-metrics", type=Path, required=True)
    parser.add_argument("--additions", type=Path, required=True)
    parser.add_argument("--rejections", type=Path)
    parser.add_argument("--summary", type=Path)
    parser.add_argument("--external-horizon-candidates", type=Path)
    parser.add_argument("--external-row-scopes", default=DEFAULT_EXTERNAL_ROW_SCOPES)
    parser.add_argument("--scenario-label", default="")
    parser.add_argument("--include-reject-reasons", default=DEFAULT_INCLUDE_REJECT_REASONS)
    parser.add_argument("--month-pnl-floor", type=float, default=0.0)
    parser.add_argument("--min-month-trades", type=float, default=2.0)
    parser.add_argument("--max-side-share", type=float, default=0.95)
    parser.add_argument("--strict-min-prob", type=float, default=0.45)
    parser.add_argument("--strict-min-pred-pnl", type=float, default=0.0)
    parser.add_argument("--strict-max-tail-prob", type=float, default=0.30)
    parser.add_argument("--relaxed-min-pred-pnl", type=float, default=-2.0)
    parser.add_argument("--top-n", type=int, default=10)
    parser.add_argument("--output-dir", type=Path, default=Path("data/reports/backtests"))
    parser.add_argument("--label", default="entry_ev_support_repair_thin_month_candidates")
    return parser


def main(argv: list[str] | None = None) -> int:
    run_diagnostics(build_parser().parse_args(argv))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
