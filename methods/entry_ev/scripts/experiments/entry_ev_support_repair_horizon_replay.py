#!/usr/bin/env python3
"""Replay horizon-viability near-miss additions against support repair targets."""

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

from entry_ev_admission_repair_target_diagnostics import (  # noqa: E402
    minimal_side_balanced_additions,
)
from entry_ev_hold_extension_stateful_replay import max_drawdown_from_trades  # noqa: E402
from entry_ev_near_miss_exit_head import parse_csv  # noqa: E402


SCENARIO_COLUMNS = [
    "row_scope",
    "prob_threshold",
    "ev_threshold",
    "tail_prob_threshold",
    "require_model_used",
]
BASE_MONTHLY_COLUMNS = {
    "role",
    "month",
    "total_adjusted_pnl",
    "trade_count",
    "long_trade_count",
    "short_trade_count",
}
BASE_TRADE_COLUMNS = {
    "role",
    "family",
    "month",
    "direction",
    "entry_timestamp",
    "exit_timestamp",
    "adjusted_pnl",
}
CHOICE_COLUMNS = {
    "role",
    "family",
    "month",
    "decision_timestamp",
    "side",
    "needed_side",
    "extra_side_needed",
    "hv_chosen_horizon_minutes",
    "hv_chosen_score",
    "actual_pnl_at_hv_chosen_horizon",
    *SCENARIO_COLUMNS,
}
COMMON_CHOICE_COLUMNS = {
    "role",
    "month",
    "decision_timestamp",
    "side",
    "needed_side",
    "extra_side_needed",
    "row_scope",
}
ROW_HORIZON_FIXED_PREFIX = "side_fixed_"


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


def numeric_series(frame: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
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
    if values.dtype == bool:
        return values.fillna(default).astype(bool)
    lowered = values.fillna(str(default)).astype(str).str.lower()
    return lowered.isin({"true", "1", "yes", "y"})


def threshold_label(value: float) -> str:
    return f"{float(value):g}".replace(".", "p").replace("-", "m")


def parse_float_csv(value: str) -> list[float]:
    return [float(item) for item in parse_csv(value)]


def parse_bool_csv(value: str) -> list[bool]:
    output: list[bool] = []
    for item in parse_csv(value):
        lowered = item.lower()
        if lowered in {"true", "1", "yes", "y"}:
            output.append(True)
        elif lowered in {"false", "0", "no", "n"}:
            output.append(False)
        else:
            raise ValueError(f"invalid boolean value: {item}")
    return output


def scenario_label(row: pd.Series) -> str:
    require = "reqmodel" if bool(row["require_model_used"]) else "allowfallback"
    return (
        f"{row['row_scope']}_p{threshold_label(row['prob_threshold'])}"
        f"_ev{threshold_label(row['ev_threshold'])}"
        f"_tail{threshold_label(row['tail_prob_threshold'])}_{require}"
    )


def apply_branch_filters(
    frame: pd.DataFrame,
    *,
    candidate: str,
    variant_contains: str,
    entry_block_rule: str,
) -> pd.DataFrame:
    output = frame.copy()
    if candidate:
        output = output[output["candidate"].astype(str).eq(candidate)]
    if variant_contains:
        variant_column = "selector_variant" if "selector_variant" in output.columns else "variant"
        output = output[
            output[variant_column].astype(str).str.contains(variant_contains, regex=False)
        ]
    if entry_block_rule:
        output = output[output["entry_block_rule"].astype(str).eq(entry_block_rule)]
    if output.empty:
        raise ValueError("branch filters removed all rows")
    return output.reset_index(drop=True)


def read_base_monthly(
    path: Path,
    *,
    candidate: str,
    variant_contains: str,
    entry_block_rule: str,
) -> pd.DataFrame:
    frame = pd.read_csv(path)
    missing = sorted(BASE_MONTHLY_COLUMNS - set(frame.columns))
    if missing:
        raise ValueError(f"{path} missing columns: {', '.join(missing)}")
    output = apply_branch_filters(
        frame,
        candidate=candidate,
        variant_contains=variant_contains,
        entry_block_rule=entry_block_rule,
    )
    output["role"] = output["role"].astype(str)
    if "family" not in output.columns:
        output["family"] = ""
    output["family"] = output["family"].astype(str)
    output["month"] = output["month"].astype(str).str.slice(0, 7)
    output["total_adjusted_pnl"] = numeric_series(output, "total_adjusted_pnl")
    output["trade_count"] = numeric_series(output, "trade_count")
    output["long_trade_count"] = numeric_series(output, "long_trade_count")
    output["short_trade_count"] = numeric_series(output, "short_trade_count")
    output["max_drawdown"] = numeric_series(output, "max_drawdown")
    return output


def read_base_trades(
    path: Path,
    *,
    candidate: str,
    variant_contains: str,
    entry_block_rule: str,
) -> pd.DataFrame:
    frame = pd.read_csv(path)
    missing = sorted(BASE_TRADE_COLUMNS - set(frame.columns))
    if missing:
        raise ValueError(f"{path} missing columns: {', '.join(missing)}")
    output = apply_branch_filters(
        frame,
        candidate=candidate,
        variant_contains=variant_contains,
        entry_block_rule=entry_block_rule,
    )
    if "entry_blocked" in output.columns:
        output = output[~bool_series(output, "entry_blocked")].copy()
    output["role"] = output["role"].astype(str)
    output["family"] = output["family"].astype(str)
    output["month"] = output["month"].astype(str).str.slice(0, 7)
    output["direction"] = output["direction"].astype(str)
    output["entry_timestamp"] = pd.to_datetime(
        output["entry_timestamp"],
        utc=True,
        errors="coerce",
    )
    output["exit_timestamp"] = pd.to_datetime(
        output["exit_timestamp"],
        utc=True,
        errors="coerce",
    )
    output["adjusted_pnl"] = numeric_series(output, "adjusted_pnl")
    output = output.dropna(subset=["entry_timestamp", "exit_timestamp"])
    output["repair_source"] = "base"
    return output.reset_index(drop=True)


def read_choice_candidates(
    path: Path,
    *,
    row_scopes: list[str],
    target_only: bool,
    choice_input_mode: str = "chosen",
    prob_thresholds: list[float] | None = None,
    ev_thresholds: list[float] | None = None,
    tail_prob_thresholds: list[float] | None = None,
    require_model_used_options: list[bool] | None = None,
) -> pd.DataFrame:
    frame = pd.read_csv(path)
    if choice_input_mode == "chosen":
        required_columns = CHOICE_COLUMNS
    elif choice_input_mode == "row_horizon":
        required_columns = COMMON_CHOICE_COLUMNS | set(SCENARIO_COLUMNS)
    elif choice_input_mode == "row_horizon_grid":
        required_columns = COMMON_CHOICE_COLUMNS
    else:
        raise ValueError(f"unknown choice input mode: {choice_input_mode}")
    missing = sorted(required_columns - set(frame.columns))
    if missing:
        raise ValueError(f"{path} missing columns: {', '.join(missing)}")
    output = frame.copy()
    output["role"] = output["role"].astype(str)
    if "family" not in output.columns:
        output["family"] = ""
    output["family"] = output["family"].astype(str)
    output["month"] = output["month"].astype(str).str.slice(0, 7)
    output["side"] = output["side"].astype(str)
    output["needed_side"] = output["needed_side"].astype(str)
    output["row_scope"] = output["row_scope"].astype(str)
    if row_scopes:
        output = output[output["row_scope"].isin(row_scopes)].copy()
    output["decision_timestamp"] = pd.to_datetime(
        output["decision_timestamp"],
        utc=True,
        errors="coerce",
    )
    output = output[output["decision_timestamp"].notna()].copy()
    output["extra_side_needed"] = numeric_series(output, "extra_side_needed")
    if target_only:
        output = output[
            output["side"].eq(output["needed_side"]) & output["extra_side_needed"].gt(0.0)
        ].copy()
    if choice_input_mode == "row_horizon_grid":
        output = add_scenario_grid(
            output,
            prob_thresholds=prob_thresholds or [0.5],
            ev_thresholds=ev_thresholds or [0.0],
            tail_prob_thresholds=tail_prob_thresholds or [0.3],
            require_model_used_options=require_model_used_options or [True],
        )
    if choice_input_mode in {"row_horizon", "row_horizon_grid"}:
        for column in ["prob_threshold", "ev_threshold", "tail_prob_threshold"]:
            output[column] = numeric_series(output, column)
        output["require_model_used"] = bool_series(output, "require_model_used")
        return expand_row_horizon_candidates(output).reset_index(drop=True)

    output["hv_chosen_horizon_minutes"] = numeric_series(
        output,
        "hv_chosen_horizon_minutes",
    )
    output["hv_chosen_score"] = numeric_series(output, "hv_chosen_score", default=-np.inf)
    output["actual_pnl_at_hv_chosen_horizon"] = numeric_series(
        output,
        "actual_pnl_at_hv_chosen_horizon",
    )
    output["extra_side_needed"] = numeric_series(output, "extra_side_needed")
    for column in ["prob_threshold", "ev_threshold", "tail_prob_threshold"]:
        output[column] = numeric_series(output, column)
    output["require_model_used"] = bool_series(output, "require_model_used")
    output = output[
        output["hv_chosen_horizon_minutes"].gt(0.0)
    ].copy()
    output["entry_timestamp"] = output["decision_timestamp"]
    output["exit_timestamp"] = output["decision_timestamp"] + pd.to_timedelta(
        output["hv_chosen_horizon_minutes"],
        unit="m",
    )
    output["direction"] = output["side"]
    output["adjusted_pnl"] = output["actual_pnl_at_hv_chosen_horizon"]
    output = add_chosen_prediction_columns(output)
    return output.reset_index(drop=True)


def add_scenario_grid(
    frame: pd.DataFrame,
    *,
    prob_thresholds: list[float],
    ev_thresholds: list[float],
    tail_prob_thresholds: list[float],
    require_model_used_options: list[bool],
) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for prob_threshold in prob_thresholds:
        for ev_threshold in ev_thresholds:
            for tail_prob_threshold in tail_prob_thresholds:
                for require_model_used in require_model_used_options:
                    scenario = frame.copy()
                    scenario["prob_threshold"] = float(prob_threshold)
                    scenario["ev_threshold"] = float(ev_threshold)
                    scenario["tail_prob_threshold"] = float(tail_prob_threshold)
                    scenario["require_model_used"] = bool(require_model_used)
                    frames.append(scenario)
    return pd.concat(frames, ignore_index=True) if frames else frame.iloc[0:0].copy()


def infer_horizons(frame: pd.DataFrame) -> list[int]:
    horizons: list[int] = []
    for column in frame.columns:
        if not column.startswith("pred_hv_") or not column.endswith("m_pnl"):
            continue
        raw = column.removeprefix("pred_hv_").removesuffix("m_pnl")
        try:
            horizons.append(int(raw))
        except ValueError:
            continue
    return sorted(set(horizons))


def required_row_horizon_columns(horizons: list[int]) -> set[str]:
    columns: set[str] = set()
    for horizon in horizons:
        columns.update(
            {
                f"{ROW_HORIZON_FIXED_PREFIX}{horizon}m_adjusted_pnl",
                f"pred_hv_{horizon}m_executable_prob",
                f"pred_hv_{horizon}m_pnl",
                f"pred_hv_{horizon}m_tail_loss_prob",
                f"pred_hv_{horizon}m_executable_model_used",
                f"pred_hv_{horizon}m_pnl_model_used",
                f"pred_hv_{horizon}m_tail_model_used",
            }
        )
    return columns


def expand_row_horizon_candidates(frame: pd.DataFrame) -> pd.DataFrame:
    horizons = infer_horizons(frame)
    if not horizons:
        raise ValueError("row-horizon input has no pred_hv_*m_pnl columns")
    missing = sorted(required_row_horizon_columns(horizons) - set(frame.columns))
    if missing:
        raise ValueError("row-horizon input missing columns: " + ", ".join(missing))
    frames: list[pd.DataFrame] = []
    for horizon in horizons:
        output = frame.copy()
        output["hv_chosen_horizon_minutes"] = float(horizon)
        output["hv_chosen_pred_executable_prob"] = numeric_series(
            output,
            f"pred_hv_{horizon}m_executable_prob",
        )
        output["hv_chosen_pred_pnl"] = numeric_series(output, f"pred_hv_{horizon}m_pnl")
        output["hv_chosen_pred_tail_loss_prob"] = numeric_series(
            output,
            f"pred_hv_{horizon}m_tail_loss_prob",
            default=1.0,
        )
        output["hv_chosen_pred_harmful_overestimate_prob"] = numeric_series(
            output,
            f"ranker_hv_{horizon}m_pred_harmful_overestimate_prob",
            default=0.0,
        )
        output["hv_chosen_pred_model_used"] = (
            bool_series(output, f"pred_hv_{horizon}m_executable_model_used")
            & bool_series(output, f"pred_hv_{horizon}m_pnl_model_used")
            & bool_series(output, f"pred_hv_{horizon}m_tail_model_used")
        )
        output["row_horizon_prob_pass"] = output["hv_chosen_pred_executable_prob"].ge(
            numeric_series(output, "prob_threshold")
        )
        output["row_horizon_ev_pass"] = output["hv_chosen_pred_pnl"].ge(
            numeric_series(output, "ev_threshold")
        )
        output["row_horizon_tail_pass"] = output["hv_chosen_pred_tail_loss_prob"].le(
            numeric_series(output, "tail_prob_threshold")
        )
        output["row_horizon_model_pass"] = (
            ~bool_series(output, "require_model_used")
            | output["hv_chosen_pred_model_used"]
        )
        output["row_horizon_gate_pass"] = (
            output["row_horizon_prob_pass"]
            & output["row_horizon_ev_pass"]
            & output["row_horizon_tail_pass"]
            & output["row_horizon_model_pass"]
        )
        output = output[output["row_horizon_gate_pass"]].copy()
        if output.empty:
            continue
        output["hv_chosen_score"] = (
            output["hv_chosen_pred_executable_prob"] * output["hv_chosen_pred_pnl"]
        )
        output["actual_pnl_at_hv_chosen_horizon"] = numeric_series(
            output,
            f"{ROW_HORIZON_FIXED_PREFIX}{horizon}m_adjusted_pnl",
        )
        output["entry_timestamp"] = output["decision_timestamp"]
        output["exit_timestamp"] = output["decision_timestamp"] + pd.to_timedelta(
            horizon,
            unit="m",
        )
        output["direction"] = output["side"]
        output["adjusted_pnl"] = output["actual_pnl_at_hv_chosen_horizon"]
        output["row_horizon_choice_score"] = output["hv_chosen_score"]
        frames.append(output)
    if not frames:
        return frame.iloc[0:0].copy()
    return pd.concat(frames, ignore_index=True, sort=False)


def add_chosen_prediction_columns(frame: pd.DataFrame) -> pd.DataFrame:
    output = frame.copy()
    output["hv_chosen_pred_executable_prob"] = np.nan
    output["hv_chosen_pred_pnl"] = np.nan
    output["hv_chosen_pred_tail_loss_prob"] = np.nan
    output["hv_chosen_pred_harmful_overestimate_prob"] = 0.0
    output["hv_chosen_pred_model_used"] = False
    if "hv_chosen_horizon_minutes" not in output.columns:
        return output
    chosen_horizon = numeric_series(output, "hv_chosen_horizon_minutes", default=0.0)
    for horizon in infer_horizons(output):
        mask = chosen_horizon.eq(float(horizon))
        if not mask.any():
            continue
        prob_column = f"pred_hv_{horizon}m_executable_prob"
        pnl_column = f"pred_hv_{horizon}m_pnl"
        tail_column = f"pred_hv_{horizon}m_tail_loss_prob"
        harmful_column = f"ranker_hv_{horizon}m_pred_harmful_overestimate_prob"
        executable_model_column = f"pred_hv_{horizon}m_executable_model_used"
        pnl_model_column = f"pred_hv_{horizon}m_pnl_model_used"
        tail_model_column = f"pred_hv_{horizon}m_tail_model_used"
        if prob_column in output.columns:
            output.loc[mask, "hv_chosen_pred_executable_prob"] = numeric_series(
                output,
                prob_column,
            )[mask]
        if pnl_column in output.columns:
            output.loc[mask, "hv_chosen_pred_pnl"] = numeric_series(output, pnl_column)[mask]
        if tail_column in output.columns:
            output.loc[mask, "hv_chosen_pred_tail_loss_prob"] = numeric_series(
                output,
                tail_column,
            )[mask]
        if harmful_column in output.columns:
            output.loc[mask, "hv_chosen_pred_harmful_overestimate_prob"] = numeric_series(
                output,
                harmful_column,
            )[mask]
        model_used = (
            bool_series(output, executable_model_column)
            & bool_series(output, pnl_model_column)
            & bool_series(output, tail_model_column)
        )
        output.loc[mask, "hv_chosen_pred_model_used"] = model_used[mask]
    return output


def support_reduction_for_addition(
    *,
    long_count: int,
    short_count: int,
    side: str,
    min_month_trades: int,
    max_side_trade_share: float,
) -> int:
    before = minimal_side_balanced_additions(
        long_count=long_count,
        short_count=short_count,
        min_trades=min_month_trades,
        max_side_trade_share=max_side_trade_share,
    )
    after_long = long_count + (1 if side == "long" else 0)
    after_short = short_count + (1 if side == "short" else 0)
    after = minimal_side_balanced_additions(
        long_count=after_long,
        short_count=after_short,
        min_trades=min_month_trades,
        max_side_trade_share=max_side_trade_share,
    )
    return max(0, int(before["extra_trades_needed"]) - int(after["extra_trades_needed"]))


def add_repair_utility_columns(
    base_monthly: pd.DataFrame,
    choices: pd.DataFrame,
    *,
    min_month_trades: int,
    max_side_trade_share: float,
    repair_support_weight: float,
    repair_expected_pnl_weight: float,
    repair_tail_penalty_weight: float,
    repair_horizon_penalty_weight: float,
    repair_harmful_penalty_weight: float = 0.0,
    repair_harmful_penalty_threshold: float = 0.0,
) -> pd.DataFrame:
    output = choices.copy()
    lookup = {
        (str(row["role"]), str(row["month"])): row
        for _, row in base_monthly.iterrows()
    }
    support_values: list[int] = []
    base_month_pnls: list[float] = []
    base_trade_counts: list[int] = []
    for _, row in output.iterrows():
        base_row = lookup.get((str(row["role"]), str(row["month"])))
        if base_row is None:
            long_count = 0
            short_count = 0
            base_month_pnls.append(0.0)
            base_trade_counts.append(0)
        else:
            long_count = int(float(base_row["long_trade_count"]))
            short_count = int(float(base_row["short_trade_count"]))
            base_month_pnls.append(float(base_row["total_adjusted_pnl"]))
            base_trade_counts.append(int(float(base_row["trade_count"])))
        support_values.append(
            support_reduction_for_addition(
                long_count=long_count,
                short_count=short_count,
                side=str(row["side"]),
                min_month_trades=min_month_trades,
                max_side_trade_share=max_side_trade_share,
            )
        )
    output["base_month_pnl"] = base_month_pnls
    output["base_month_trade_count"] = base_trade_counts
    output["support_reduction_value"] = support_values
    expected_pnl = numeric_series(output, "hv_chosen_pred_pnl", default=np.nan)
    if expected_pnl.isna().all():
        expected_pnl = numeric_series(output, "hv_chosen_score", default=0.0)
    tail_prob = numeric_series(output, "hv_chosen_pred_tail_loss_prob", default=0.0)
    horizon_penalty = numeric_series(output, "hv_chosen_horizon_minutes", default=0.0) / 60.0
    if "repair_horizon_penalty_weight_effective" in output.columns:
        horizon_penalty_weight = numeric_series(
            output,
            "repair_horizon_penalty_weight_effective",
            default=repair_horizon_penalty_weight,
        )
    else:
        horizon_penalty_weight = pd.Series(
            repair_horizon_penalty_weight,
            index=output.index,
            dtype=float,
        )
    output["repair_expected_pnl"] = expected_pnl.fillna(0.0)
    output["repair_tail_penalty"] = tail_prob.fillna(0.0)
    output["repair_horizon_penalty"] = horizon_penalty.fillna(0.0)
    output["repair_horizon_penalty_weight_effective"] = horizon_penalty_weight.fillna(
        repair_horizon_penalty_weight
    )
    output["repair_horizon_penalty_amount"] = (
        output["repair_horizon_penalty_weight_effective"] * output["repair_horizon_penalty"]
    )
    duration_risk_penalty = numeric_series(
        output,
        "repair_duration_risk_penalty_amount",
        default=0.0,
    ).fillna(0.0)
    output["repair_duration_risk_penalty_amount"] = duration_risk_penalty
    support_success_proxy = (
        numeric_series(output, "support_reduction_value", default=0.0).clip(0.0, 1.0)
        * numeric_series(output, "hv_chosen_pred_executable_prob", default=0.0).clip(0.0, 1.0)
        * (1.0 - tail_prob.fillna(0.0).clip(0.0, 1.0))
    )
    raw_harmful_penalty = numeric_series(
        output,
        "hv_chosen_pred_harmful_overestimate_prob",
        default=0.0,
    ).clip(0.0, 1.0)
    harmful_threshold = min(max(float(repair_harmful_penalty_threshold), 0.0), 0.999999)
    if harmful_threshold > 0.0:
        harmful_penalty = (raw_harmful_penalty - harmful_threshold).clip(lower=0.0) / (
            1.0 - harmful_threshold
        )
    else:
        harmful_penalty = raw_harmful_penalty
    output["repair_support_success_proxy"] = support_success_proxy
    output["repair_harmful_penalty_raw"] = raw_harmful_penalty
    output["repair_harmful_penalty"] = harmful_penalty
    output["repair_harmful_penalty_threshold"] = harmful_threshold
    output["repair_harmful_penalty_amount"] = (
        repair_harmful_penalty_weight
        * harmful_penalty
        * (1.0 - support_success_proxy)
    )
    output["repair_score"] = (
        repair_support_weight * numeric_series(output, "support_reduction_value")
        + repair_expected_pnl_weight * output["repair_expected_pnl"]
        - repair_tail_penalty_weight * output["repair_tail_penalty"]
        - output["repair_horizon_penalty_amount"]
        - output["repair_duration_risk_penalty_amount"]
        - output["repair_harmful_penalty_amount"]
    )
    return output


def apply_choice_prefilters(
    choices: pd.DataFrame,
    *,
    min_chosen_pred_pnl: float | None,
    min_chosen_actual_pnl: float | None,
    max_chosen_tail_prob: float | None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    kept = choices.copy()
    rejected_frames: list[pd.DataFrame] = []
    filters = [
        (
            "pred_pnl_floor",
            min_chosen_pred_pnl,
            lambda frame, value: numeric_series(
                frame,
                "hv_chosen_pred_pnl",
                default=-np.inf,
            ).lt(float(value)),
        ),
        (
            "actual_pnl_floor",
            min_chosen_actual_pnl,
            lambda frame, value: numeric_series(frame, "adjusted_pnl", default=-np.inf).lt(
                float(value)
            ),
        ),
        (
            "tail_prob_ceiling",
            max_chosen_tail_prob,
            lambda frame, value: numeric_series(
                frame,
                "hv_chosen_pred_tail_loss_prob",
                default=np.inf,
            ).gt(float(value)),
        ),
    ]
    for reason, value, mask_fn in filters:
        if value is None or kept.empty:
            continue
        rejected = kept[mask_fn(kept, value)].copy()
        if not rejected.empty:
            rejected["reject_reason"] = reason
            rejected_frames.append(rejected)
            kept = kept.drop(rejected.index)
    rejected_all = pd.concat(rejected_frames, ignore_index=True) if rejected_frames else pd.DataFrame()
    return kept.reset_index(drop=True), rejected_all


def intervals_overlap(
    start: pd.Timestamp,
    end: pd.Timestamp,
    intervals: list[tuple[pd.Timestamp, pd.Timestamp]],
) -> bool:
    return any(start < other_end and end > other_start for other_start, other_end in intervals)


def select_support_additions(
    base_trades: pd.DataFrame,
    choices: pd.DataFrame,
    *,
    cap_to_extra_side_needed: bool = True,
    overlap_key_columns: list[str] | None = None,
    selection_mode: str = "score",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if overlap_key_columns is None:
        overlap_key_columns = ["role"]
    intervals: dict[tuple[Any, ...], list[tuple[pd.Timestamp, pd.Timestamp]]] = {}
    for _, row in base_trades.iterrows():
        key = tuple(row[column] for column in overlap_key_columns)
        intervals.setdefault(key, []).append((row["entry_timestamp"], row["exit_timestamp"]))

    quotas: dict[tuple[str, str, str], int] = {}
    if cap_to_extra_side_needed:
        quota_frame = (
            choices.groupby(["role", "month", "side"], dropna=False)["extra_side_needed"]
            .max()
            .reset_index()
        )
        for _, row in quota_frame.iterrows():
            quotas[(str(row["role"]), str(row["month"]), str(row["side"]))] = int(
                max(0, np.ceil(float(row["extra_side_needed"])))
            )

    quota_used: dict[tuple[str, str, str], int] = {}
    selected_rows: list[dict[str, Any]] = []
    rejected_rows: list[dict[str, Any]] = []
    if selection_mode == "repair_score" and "repair_score" in choices.columns:
        candidate_sort_columns = [
            "repair_score",
            "support_reduction_value",
            "repair_expected_pnl",
            "decision_timestamp",
            "entry_timestamp",
            "hv_chosen_horizon_minutes",
        ]
    else:
        candidate_sort_columns = [
            "hv_chosen_score",
            "decision_timestamp",
            "entry_timestamp",
            "hv_chosen_horizon_minutes",
        ]
    sort_columns = [column for column in candidate_sort_columns if column in choices.columns]
    ascending = [
        False
        if column
        in {
            "hv_chosen_score",
            "repair_score",
            "support_reduction_value",
            "repair_expected_pnl",
        }
        else True
        for column in sort_columns
    ]
    sorted_choices = choices.sort_values(
        sort_columns,
        ascending=ascending,
    )
    for _, row in sorted_choices.iterrows():
        quota_key = (str(row["role"]), str(row["month"]), str(row["side"]))
        if cap_to_extra_side_needed and quota_used.get(quota_key, 0) >= quotas.get(quota_key, 0):
            rejected = row.to_dict()
            rejected["reject_reason"] = "quota_full"
            rejected_rows.append(rejected)
            continue
        overlap_key = tuple(row[column] for column in overlap_key_columns)
        start = row["entry_timestamp"]
        end = row["exit_timestamp"]
        if intervals_overlap(start, end, intervals.get(overlap_key, [])):
            rejected = row.to_dict()
            rejected["reject_reason"] = "overlap"
            rejected_rows.append(rejected)
            continue
        accepted = row.to_dict()
        accepted["addition_rank"] = len(selected_rows) + 1
        selected_rows.append(accepted)
        quota_used[quota_key] = quota_used.get(quota_key, 0) + 1
        intervals.setdefault(overlap_key, []).append((start, end))

    selected = pd.DataFrame(selected_rows)
    rejected = pd.DataFrame(rejected_rows)
    return selected, rejected


def base_summary(monthly: pd.DataFrame) -> dict[str, Any]:
    role_pnl = monthly.groupby("role", dropna=False)["total_adjusted_pnl"].sum()
    role_trades = monthly.groupby("role", dropna=False)["trade_count"].sum()
    total_trades = int(monthly["trade_count"].sum())
    long_trades = int(monthly["long_trade_count"].sum())
    short_trades = int(monthly["short_trade_count"].sum())
    overall_side_share = max(long_trades, short_trades) / total_trades if total_trades else 0.0
    return {
        "base_total_pnl": float(monthly["total_adjusted_pnl"].sum()),
        "base_month_pnl_min": float(monthly["total_adjusted_pnl"].min()),
        "base_role_total_pnl_min": float(role_pnl.min()) if len(role_pnl) else 0.0,
        "base_trade_count": total_trades,
        "base_role_trade_count_min": int(role_trades.min()) if len(role_trades) else 0,
        "base_month_trade_count_min": int(monthly["trade_count"].min()) if len(monthly) else 0,
        "base_observed_max_side_trade_share": float(
            max(overall_side_share, monthly["max_side_trade_share"].max())
        )
        if len(monthly)
        else 0.0,
    }


def update_monthly_metrics(
    base_monthly: pd.DataFrame,
    base_trades: pd.DataFrame,
    additions: pd.DataFrame,
    *,
    scenario: dict[str, Any],
) -> pd.DataFrame:
    monthly = base_monthly.copy()
    for column, value in scenario.items():
        monthly[column] = value
    if "max_side_trade_share" not in monthly.columns:
        monthly["max_side_trade_share"] = 0.0

    if not additions.empty:
        grouped = additions.groupby(["role", "family", "month", "side"], dropna=False).agg(
            added_pnl=("adjusted_pnl", "sum"),
            added_count=("adjusted_pnl", "size"),
        )
        for key, row in grouped.reset_index().iterrows():
            del key
            mask = monthly["role"].astype(str).eq(str(row["role"])) & monthly[
                "month"
            ].astype(str).eq(str(row["month"]))
            if not mask.any():
                new_row = {column: np.nan for column in monthly.columns}
                new_row.update(scenario)
                new_row.update(
                    {
                        "source": "support_repair",
                        "role": str(row["role"]),
                        "family": str(row["family"]),
                        "month": str(row["month"]),
                        "total_adjusted_pnl": 0.0,
                        "trade_count": 0.0,
                        "long_trade_count": 0.0,
                        "short_trade_count": 0.0,
                        "max_drawdown": 0.0,
                    }
                )
                monthly = pd.concat([monthly, pd.DataFrame([new_row])], ignore_index=True)
                mask = monthly["role"].astype(str).eq(str(row["role"])) & monthly[
                    "month"
                ].astype(str).eq(str(row["month"]))
            idx = monthly.index[mask][0]
            monthly.loc[idx, "total_adjusted_pnl"] = float(
                monthly.loc[idx, "total_adjusted_pnl"]
            ) + float(row["added_pnl"])
            monthly.loc[idx, "trade_count"] = float(monthly.loc[idx, "trade_count"]) + float(
                row["added_count"]
            )
            count_column = "long_trade_count" if str(row["side"]) == "long" else "short_trade_count"
            monthly.loc[idx, count_column] = float(monthly.loc[idx, count_column]) + float(
                row["added_count"]
            )

    trades = normalize_combined_trades(base_trades, additions)
    drawdowns = {}
    for key, group in trades.groupby(["role", "month"], dropna=False):
        drawdowns[key] = max_drawdown_from_trades(group)
    for idx, row in monthly.iterrows():
        long_count = float(row["long_trade_count"])
        short_count = float(row["short_trade_count"])
        trade_count = float(row["trade_count"])
        monthly.loc[idx, "max_side_trade_share"] = (
            max(long_count, short_count) / trade_count if trade_count else 0.0
        )
        monthly.loc[idx, "max_drawdown"] = float(
            drawdowns.get((str(row["role"]), str(row["month"])), 0.0)
        )
    return monthly.reset_index(drop=True)


def normalize_combined_trades(base_trades: pd.DataFrame, additions: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "role",
        "family",
        "month",
        "direction",
        "entry_timestamp",
        "exit_timestamp",
        "adjusted_pnl",
        "repair_source",
    ]
    base = base_trades.copy()
    base["repair_source"] = "base"
    frames = [base[columns]]
    if not additions.empty:
        add = additions.copy()
        add["repair_source"] = "support_repair"
        if "direction" not in add.columns and "side" in add.columns:
            add["direction"] = add["side"]
        frames.append(add[columns])
    return pd.concat(frames, ignore_index=True).sort_values(
        ["role", "entry_timestamp", "exit_timestamp"]
    )


def summarize_repair_targets(
    monthly: pd.DataFrame,
    *,
    month_floor: float,
    min_month_trades: int,
    max_side_trade_share: float,
    shallow_month_floor: float,
) -> tuple[dict[str, Any], pd.DataFrame]:
    rows: list[dict[str, Any]] = []
    for _, row in monthly.iterrows():
        long_count = int(float(row["long_trade_count"]))
        short_count = int(float(row["short_trade_count"]))
        addition = minimal_side_balanced_additions(
            long_count=long_count,
            short_count=short_count,
            min_trades=min_month_trades,
            max_side_trade_share=max_side_trade_share,
        )
        pnl = float(row["total_adjusted_pnl"])
        trade_count = int(float(row["trade_count"]))
        side_share = float(row["max_side_trade_share"])
        month_trade_shortfall = max(0, min_month_trades - trade_count)
        side_share_excess = max(0.0, side_share - max_side_trade_share)
        support_limited = bool(
            month_trade_shortfall > 0
            or side_share_excess > 0
            or addition["extra_trades_needed"] > 0
        )
        if pnl >= month_floor:
            floor_class = "pass"
        elif support_limited:
            floor_class = "support_limited"
        elif pnl >= shallow_month_floor:
            floor_class = "shallow"
        else:
            floor_class = "structural"
        rows.append(
            {
                **{
                    column: row[column]
                    for column in SCENARIO_COLUMNS
                    if column in row.index
                },
                "role": row["role"],
                "family": row.get("family", ""),
                "month": row["month"],
                "total_adjusted_pnl": pnl,
                "trade_count": trade_count,
                "long_trade_count": long_count,
                "short_trade_count": short_count,
                "month_pnl_hurdle": max(0.0, month_floor - pnl),
                "month_trade_shortfall": month_trade_shortfall,
                "side_share_excess": side_share_excess,
                **addition,
                "support_limited_month": support_limited,
                "support_limited_negative_month": bool(pnl < month_floor and support_limited),
                "floor_breach_class": floor_class,
            }
        )
    targets = pd.DataFrame(rows)
    if targets.empty:
        return {}, targets
    summary = {
        "remaining_month_pnl_hurdle_sum": float(targets["month_pnl_hurdle"].sum()),
        "remaining_extra_trades_needed": int(targets["extra_trades_needed"].sum()),
        "remaining_extra_long_needed": int(targets["extra_long_needed"].sum()),
        "remaining_extra_short_needed": int(targets["extra_short_needed"].sum()),
        "negative_month_count": int((targets["total_adjusted_pnl"] < month_floor).sum()),
        "support_limited_negative_month_count": int(
            targets["support_limited_negative_month"].sum()
        ),
        "shallow_negative_month_count": int(targets["floor_breach_class"].eq("shallow").sum()),
        "structural_negative_month_count": int(
            targets["floor_breach_class"].eq("structural").sum()
        ),
    }
    return summary, targets


def summarize_admission(
    monthly: pd.DataFrame,
    *,
    min_total_pnl: float,
    min_role_total_pnl: float,
    month_floor: float,
    min_role_trades: int,
    min_month_trades: int,
    max_side_trade_share: float,
) -> dict[str, Any]:
    role_totals = monthly.groupby("role", dropna=False)["total_adjusted_pnl"].sum()
    role_trades = monthly.groupby("role", dropna=False)["trade_count"].sum()
    total_pnl = float(monthly["total_adjusted_pnl"].sum())
    total_trades = int(monthly["trade_count"].sum())
    long_trades = int(monthly["long_trade_count"].sum())
    short_trades = int(monthly["short_trade_count"].sum())
    overall_side_share = max(long_trades, short_trades) / total_trades if total_trades else 0.0
    observed_side_share = float(max(overall_side_share, monthly["max_side_trade_share"].max()))
    blockers: list[str] = []
    if total_pnl < min_total_pnl:
        blockers.append("total_pnl_below_floor")
    if float(role_totals.min()) < min_role_total_pnl:
        blockers.append("role_total_pnl_below_floor")
    if float(monthly["total_adjusted_pnl"].min()) < month_floor:
        blockers.append("month_pnl_below_floor")
    if int(role_trades.min()) < min_role_trades:
        blockers.append("role_trades_low")
    if int(monthly["trade_count"].min()) < min_month_trades:
        blockers.append("month_trades_low")
    if observed_side_share > max_side_trade_share:
        blockers.append("side_share_high")
    return {
        "selector_pass": not blockers,
        "blockers": ",".join(blockers),
        "combined_total_pnl": total_pnl,
        "combined_trade_count": total_trades,
        "combined_long_trade_count": long_trades,
        "combined_short_trade_count": short_trades,
        "role_total_pnl_min": float(role_totals.min()),
        "month_pnl_min": float(monthly["total_adjusted_pnl"].min()),
        "role_trade_count_min": int(role_trades.min()),
        "month_trade_count_min": int(monthly["trade_count"].min()),
        "observed_max_side_trade_share": observed_side_share,
        "max_drawdown": float(monthly["max_drawdown"].max()),
    }


def replay_scenarios(
    base_monthly: pd.DataFrame,
    base_trades: pd.DataFrame,
    choices: pd.DataFrame,
    *,
    min_total_pnl: float,
    min_role_total_pnl: float,
    month_floor: float,
    shallow_month_floor: float,
    min_role_trades: int,
    min_month_trades: int,
    max_side_trade_share: float,
    cap_to_extra_side_needed: bool,
    overlap_key_columns: list[str],
    selection_mode: str = "score",
    repair_support_weight: float = 1.0,
    repair_expected_pnl_weight: float = 1.0,
    repair_tail_penalty_weight: float = 1.0,
    repair_horizon_penalty_weight: float = 0.0,
    repair_harmful_penalty_weight: float = 0.0,
    repair_harmful_penalty_threshold: float = 0.0,
    min_chosen_pred_pnl: float | None = None,
    min_chosen_actual_pnl: float | None = None,
    max_chosen_tail_prob: float | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    summary_rows: list[dict[str, Any]] = []
    monthly_frames: list[pd.DataFrame] = []
    addition_frames: list[pd.DataFrame] = []
    rejection_frames: list[pd.DataFrame] = []
    base_stats = base_summary(base_monthly)
    if selection_mode == "repair_score":
        choices = add_repair_utility_columns(
            base_monthly,
            choices,
            min_month_trades=min_month_trades,
            max_side_trade_share=max_side_trade_share,
            repair_support_weight=repair_support_weight,
            repair_expected_pnl_weight=repair_expected_pnl_weight,
            repair_tail_penalty_weight=repair_tail_penalty_weight,
            repair_horizon_penalty_weight=repair_horizon_penalty_weight,
            repair_harmful_penalty_weight=repair_harmful_penalty_weight,
            repair_harmful_penalty_threshold=repair_harmful_penalty_threshold,
        )
    for key, group in choices.groupby(SCENARIO_COLUMNS, dropna=False, sort=False):
        scenario = dict(zip(SCENARIO_COLUMNS, key, strict=True))
        label = scenario_label(pd.Series(scenario))
        filtered_group, prefilter_rejections = apply_choice_prefilters(
            group,
            min_chosen_pred_pnl=min_chosen_pred_pnl,
            min_chosen_actual_pnl=min_chosen_actual_pnl,
            max_chosen_tail_prob=max_chosen_tail_prob,
        )
        additions, selection_rejections = select_support_additions(
            base_trades,
            filtered_group,
            cap_to_extra_side_needed=cap_to_extra_side_needed,
            overlap_key_columns=overlap_key_columns,
            selection_mode=selection_mode,
        )
        rejections = pd.concat(
            [prefilter_rejections, selection_rejections],
            ignore_index=True,
        ) if not prefilter_rejections.empty or not selection_rejections.empty else pd.DataFrame()
        if not additions.empty:
            additions["selection_mode"] = selection_mode
        if not rejections.empty:
            rejections["selection_mode"] = selection_mode
        if not additions.empty:
            additions["scenario_label"] = label
            for column, value in scenario.items():
                additions[column] = value
            addition_frames.append(additions)
        if not rejections.empty:
            rejections["scenario_label"] = label
            for column, value in scenario.items():
                rejections[column] = value
            rejection_frames.append(rejections)
        monthly = update_monthly_metrics(
            base_monthly,
            base_trades,
            additions,
            scenario={**scenario, "scenario_label": label},
        )
        repair_summary, repair_targets = summarize_repair_targets(
            monthly,
            month_floor=month_floor,
            min_month_trades=min_month_trades,
            max_side_trade_share=max_side_trade_share,
            shallow_month_floor=shallow_month_floor,
        )
        del repair_targets
        admission = summarize_admission(
            monthly,
            min_total_pnl=min_total_pnl,
            min_role_total_pnl=min_role_total_pnl,
            month_floor=month_floor,
            min_role_trades=min_role_trades,
            min_month_trades=min_month_trades,
            max_side_trade_share=max_side_trade_share,
        )
        monthly["scenario_label"] = label
        monthly_frames.append(monthly)
        added_pnl = float(additions["adjusted_pnl"].sum()) if not additions.empty else 0.0
        summary_rows.append(
            {
                **scenario,
                "scenario_label": label,
                "selection_mode": selection_mode,
                **base_stats,
                "candidate_rows": int(len(group)),
                "post_filter_candidate_rows": int(len(filtered_group)),
                "chosen_input_rows": int(group["hv_chosen_horizon_minutes"].gt(0).sum()),
                "added_count": int(len(additions)),
                "added_pnl": added_pnl,
                "rejected_overlap_count": int(
                    rejections["reject_reason"].eq("overlap").sum()
                )
                if not rejections.empty
                else 0,
                "rejected_quota_count": int(
                    rejections["reject_reason"].eq("quota_full").sum()
                )
                if not rejections.empty
                else 0,
                "rejected_pred_pnl_floor_count": int(
                    rejections["reject_reason"].eq("pred_pnl_floor").sum()
                )
                if not rejections.empty
                else 0,
                "rejected_actual_pnl_floor_count": int(
                    rejections["reject_reason"].eq("actual_pnl_floor").sum()
                )
                if not rejections.empty
                else 0,
                "rejected_tail_prob_ceiling_count": int(
                    rejections["reject_reason"].eq("tail_prob_ceiling").sum()
                )
                if not rejections.empty
                else 0,
                "delta_vs_base": float(admission["combined_total_pnl"] - base_stats["base_total_pnl"]),
                **admission,
                **repair_summary,
            }
        )
    summary = pd.DataFrame(summary_rows)
    if not summary.empty:
        summary = summary.sort_values(
            [
                "selector_pass",
                "remaining_extra_trades_needed",
                "month_pnl_min",
                "combined_total_pnl",
                "added_count",
            ],
            ascending=[False, True, False, False, True],
        ).reset_index(drop=True)
    monthly_all = pd.concat(monthly_frames, ignore_index=True) if monthly_frames else pd.DataFrame()
    additions_all = (
        pd.concat(addition_frames, ignore_index=True) if addition_frames else pd.DataFrame()
    )
    rejections_all = (
        pd.concat(rejection_frames, ignore_index=True) if rejection_frames else pd.DataFrame()
    )
    return summary, monthly_all, additions_all, rejections_all


def run_replay(args: argparse.Namespace) -> Path:
    row_scopes = parse_csv(args.row_scopes)
    overlap_keys = parse_csv(args.overlap_keys)
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
        args.choices,
        row_scopes=row_scopes,
        target_only=args.target_only,
        choice_input_mode=args.choice_input_mode,
        prob_thresholds=parse_float_csv(args.prob_thresholds),
        ev_thresholds=parse_float_csv(args.ev_thresholds),
        tail_prob_thresholds=parse_float_csv(args.tail_prob_thresholds),
        require_model_used_options=parse_bool_csv(args.require_model_used_options),
    )
    summary, monthly, additions, rejections = replay_scenarios(
        base_monthly,
        base_trades,
        choices,
        min_total_pnl=args.min_total_pnl,
        min_role_total_pnl=args.min_role_total_pnl,
        month_floor=args.month_floor,
        shallow_month_floor=args.shallow_month_floor,
        min_role_trades=args.min_role_trades,
        min_month_trades=args.min_month_trades,
        max_side_trade_share=args.max_side_trade_share,
        cap_to_extra_side_needed=args.cap_to_extra_side_needed,
        overlap_key_columns=overlap_keys,
        selection_mode=args.selection_mode,
        repair_support_weight=args.repair_support_weight,
        repair_expected_pnl_weight=args.repair_expected_pnl_weight,
        repair_tail_penalty_weight=args.repair_tail_penalty_weight,
        repair_horizon_penalty_weight=args.repair_horizon_penalty_weight,
        repair_harmful_penalty_weight=args.repair_harmful_penalty_weight,
        repair_harmful_penalty_threshold=args.repair_harmful_penalty_threshold,
        min_chosen_pred_pnl=args.min_chosen_pred_pnl,
        min_chosen_actual_pnl=args.min_chosen_actual_pnl,
        max_chosen_tail_prob=args.max_chosen_tail_prob,
    )
    run_dir = make_run_dir(args.output_dir, args.label)
    summary.to_csv(run_dir / "support_repair_horizon_replay_summary.csv", index=False)
    monthly.to_csv(run_dir / "support_repair_horizon_replay_monthly_metrics.csv", index=False)
    additions.to_csv(run_dir / "support_repair_horizon_replay_additions.csv", index=False)
    rejections.to_csv(run_dir / "support_repair_horizon_replay_rejections.csv", index=False)
    (run_dir / "config.json").write_text(
        json.dumps(
            {
                "base_monthly_metrics": args.base_monthly_metrics,
                "base_trades": args.base_trades,
                "choices": args.choices,
                "choice_input_mode": args.choice_input_mode,
                "candidate": args.candidate,
                "variant_contains": args.variant_contains,
                "base_entry_block_rule": args.base_entry_block_rule,
                "row_scopes": row_scopes,
                "prob_thresholds": parse_float_csv(args.prob_thresholds),
                "ev_thresholds": parse_float_csv(args.ev_thresholds),
                "tail_prob_thresholds": parse_float_csv(args.tail_prob_thresholds),
                "require_model_used_options": parse_bool_csv(args.require_model_used_options),
                "target_only": args.target_only,
                "cap_to_extra_side_needed": args.cap_to_extra_side_needed,
                "overlap_keys": overlap_keys,
                "selection_mode": args.selection_mode,
                "repair_support_weight": args.repair_support_weight,
                "repair_expected_pnl_weight": args.repair_expected_pnl_weight,
                "repair_tail_penalty_weight": args.repair_tail_penalty_weight,
                "repair_horizon_penalty_weight": args.repair_horizon_penalty_weight,
                "repair_harmful_penalty_weight": args.repair_harmful_penalty_weight,
                "repair_harmful_penalty_threshold": args.repair_harmful_penalty_threshold,
                "min_chosen_pred_pnl": args.min_chosen_pred_pnl,
                "min_chosen_actual_pnl": args.min_chosen_actual_pnl,
                "max_chosen_tail_prob": args.max_chosen_tail_prob,
                "min_total_pnl": args.min_total_pnl,
                "min_role_total_pnl": args.min_role_total_pnl,
                "month_floor": args.month_floor,
                "shallow_month_floor": args.shallow_month_floor,
                "min_role_trades": args.min_role_trades,
                "min_month_trades": args.min_month_trades,
                "max_side_trade_share": args.max_side_trade_share,
            },
            indent=2,
            default=local_json_default,
        ),
        encoding="utf-8",
    )

    print("Support repair horizon replay summary:")
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
                    "delta_vs_base",
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
    parser.add_argument("--choices", type=Path, required=True)
    parser.add_argument(
        "--choice-input-mode",
        choices=["chosen", "row_horizon", "row_horizon_grid"],
        default="chosen",
        help=(
            "chosen replays pre-selected threshold choices; row_horizon expands existing "
            "scenario rows by horizon; row_horizon_grid builds threshold scenarios from "
            "prediction rows before horizon expansion."
        ),
    )
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
    parser.add_argument("--target-only", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument(
        "--cap-to-extra-side-needed",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    parser.add_argument("--overlap-keys", default="role")
    parser.add_argument("--selection-mode", choices=["score", "repair_score"], default="score")
    parser.add_argument("--repair-support-weight", type=float, default=1.0)
    parser.add_argument("--repair-expected-pnl-weight", type=float, default=1.0)
    parser.add_argument("--repair-tail-penalty-weight", type=float, default=1.0)
    parser.add_argument("--repair-horizon-penalty-weight", type=float, default=0.0)
    parser.add_argument("--repair-harmful-penalty-weight", type=float, default=0.0)
    parser.add_argument("--repair-harmful-penalty-threshold", type=float, default=0.0)
    parser.add_argument("--min-chosen-pred-pnl", type=float)
    parser.add_argument("--min-chosen-actual-pnl", type=float)
    parser.add_argument("--max-chosen-tail-prob", type=float)
    parser.add_argument("--min-total-pnl", type=float, default=0.0)
    parser.add_argument("--min-role-total-pnl", type=float, default=0.0)
    parser.add_argument("--month-floor", type=float, default=0.0)
    parser.add_argument("--shallow-month-floor", type=float, default=-1.0)
    parser.add_argument("--min-role-trades", type=int, default=4)
    parser.add_argument("--min-month-trades", type=int, default=1)
    parser.add_argument("--max-side-trade-share", type=float, default=0.95)
    parser.add_argument("--output-dir", type=Path, default=Path("data/reports/backtests"))
    parser.add_argument("--label", default="entry_ev_support_repair_horizon_replay")
    parser.add_argument("--print-top", type=int, default=20)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    run_replay(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
