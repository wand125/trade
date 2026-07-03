#!/usr/bin/env python3
"""Audit where thin target months lose candidate support before stateful replay."""

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


DEFAULT_HORIZONS = [60, 240, 720]
DEFAULT_TARGETS = (
    "fresh2024_validation:2024-03:long,"
    "fresh2024_validation:2024-08:long,"
    "fresh2024_validation:2024-11:long,"
    "refit2025_validation:2025-03:short,"
    "refit2025_validation:2025-07:short"
)
DEFAULT_ROW_SCOPES = "available_candidates,greedy_selected"
BASE_REQUIRED_COLUMNS = {
    "role",
    "month",
    "decision_timestamp",
    "side",
    "needed_side",
    "extra_side_needed",
    "row_scope",
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


def parse_csv(value: str) -> list[str]:
    return [item.strip() for item in str(value).split(",") if item.strip()]


def parse_int_csv(value: str) -> list[int]:
    return [int(item) for item in parse_csv(value)]


def parse_targets(value: str) -> list[tuple[str, str, str]]:
    targets: list[tuple[str, str, str]] = []
    for item in parse_csv(value):
        parts = item.split(":")
        if len(parts) != 3:
            raise ValueError(f"target must be role:YYYY-MM:side: {item}")
        role, month, side = parts
        if not role or not month or not side:
            raise ValueError(f"target must be role:YYYY-MM:side: {item}")
        targets.append((role, month[:7], side))
    return targets


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


def text_series(frame: pd.DataFrame, column: str, default: str = "") -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=object)
    return frame[column].fillna(default).astype(str)


def required_columns_for_horizons(horizons: list[int]) -> set[str]:
    columns = set(BASE_REQUIRED_COLUMNS)
    for horizon in horizons:
        columns.update(
            {
                f"side_fixed_{horizon}m_adjusted_pnl",
                f"pred_hv_{horizon}m_executable_prob",
                f"pred_hv_{horizon}m_tail_loss_prob",
                f"pred_hv_{horizon}m_executable_model_used",
                f"pred_hv_{horizon}m_pnl_model_used",
                f"pred_hv_{horizon}m_tail_model_used",
            }
        )
    return columns


def normalize_predictions(
    frame: pd.DataFrame,
    *,
    horizons: list[int],
    prefer_ranker_pnl: bool,
) -> pd.DataFrame:
    missing = sorted(required_columns_for_horizons(horizons) - set(frame.columns))
    for horizon in horizons:
        pred_column = f"pred_hv_{horizon}m_pnl"
        ranker_column = f"ranker_hv_{horizon}m_pred_pnl"
        if pred_column not in frame.columns and ranker_column not in frame.columns:
            missing.append(f"{pred_column} or {ranker_column}")
    if missing:
        raise ValueError("predictions missing columns: " + ", ".join(sorted(set(missing))))

    output = frame.copy()
    for column in [
        "family",
        "role",
        "side",
        "needed_side",
        "row_scope",
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
    output["extra_side_needed"] = numeric_series(output, "extra_side_needed", default=0.0)
    output["stateful_available"] = bool_series(output, "stateful_available", default=False)
    output["selected_any"] = bool_series(output, "selected_any", default=False)
    output["strict_side_specific"] = bool_series(
        output,
        "strict_side_specific",
        default=False,
    )
    output["relaxed_side_specific"] = bool_series(
        output,
        "relaxed_side_specific",
        default=False,
    )
    for horizon in horizons:
        ranker_column = f"ranker_hv_{horizon}m_pred_pnl"
        pred_column = f"pred_hv_{horizon}m_pnl"
        pnl_source = (
            ranker_column
            if prefer_ranker_pnl and ranker_column in output.columns
            else pred_column
        )
        output[f"effective_hv_{horizon}m_pred_pnl"] = numeric_series(output, pnl_source)
        output[f"side_fixed_{horizon}m_adjusted_pnl"] = numeric_series(
            output,
            f"side_fixed_{horizon}m_adjusted_pnl",
        )
        output[f"pred_hv_{horizon}m_executable_prob"] = numeric_series(
            output,
            f"pred_hv_{horizon}m_executable_prob",
            default=0.0,
        )
        output[f"pred_hv_{horizon}m_tail_loss_prob"] = numeric_series(
            output,
            f"pred_hv_{horizon}m_tail_loss_prob",
            default=1.0,
        )
        for suffix in [
            "executable_model_used",
            "pnl_model_used",
            "tail_model_used",
        ]:
            output[f"pred_hv_{horizon}m_{suffix}"] = bool_series(
                output,
                f"pred_hv_{horizon}m_{suffix}",
                default=False,
            )
    return output.reset_index(drop=True)


def normalize_replay_candidates(frame: pd.DataFrame) -> pd.DataFrame:
    required = {
        "role",
        "month",
        "side",
        "row_scope",
        "decision_timestamp",
        "hv_chosen_horizon_minutes",
        "actual_pnl_at_hv_chosen_horizon",
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError("replay candidates missing columns: " + ", ".join(missing))
    output = frame.copy()
    for column in ["role", "family", "side", "row_scope"]:
        output[column] = text_series(output, column)
    output["month"] = output["month"].astype(str).str.slice(0, 7)
    output["decision_timestamp"] = pd.to_datetime(
        output["decision_timestamp"],
        utc=True,
        errors="coerce",
    )
    output["hv_chosen_horizon_minutes"] = numeric_series(
        output,
        "hv_chosen_horizon_minutes",
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
    output["actual_pnl_at_hv_chosen_horizon"] = numeric_series(
        output,
        "actual_pnl_at_hv_chosen_horizon",
    )
    output["hv_chosen_pred_model_used"] = bool_series(
        output,
        "hv_chosen_pred_model_used",
        default=False,
    )
    return output[output["decision_timestamp"].notna()].reset_index(drop=True)


def select_target_scope_rows(
    predictions: pd.DataFrame,
    *,
    role: str,
    month: str,
    side: str,
    row_scope: str,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    month_rows = predictions[
        predictions["role"].eq(role) & predictions["month"].eq(month)
    ].copy()
    scope_rows = month_rows[month_rows["row_scope"].eq(row_scope)].copy()
    side_rows = scope_rows[scope_rows["side"].eq(side)].copy()
    support_rows = side_rows[
        side_rows["side"].eq(side_rows["needed_side"])
        & side_rows["extra_side_needed"].gt(0.0)
    ].copy()
    return month_rows, scope_rows, side_rows, support_rows


def horizon_long_frame(rows: pd.DataFrame, *, horizons: list[int]) -> pd.DataFrame:
    output_rows: list[dict[str, Any]] = []
    metadata_columns = [
        "family",
        "role",
        "month",
        "decision_timestamp",
        "row_scope",
        "selection_bucket",
        "selected_any",
        "side",
        "needed_side",
        "extra_side_needed",
        "stateful_available",
        "strict_side_specific",
        "relaxed_side_specific",
        "target_fixed_best_adjusted_pnl",
        "target_fixed_best_horizon_minutes",
    ]
    available_metadata = [column for column in metadata_columns if column in rows.columns]
    for _, row in rows.iterrows():
        base = {column: row[column] for column in available_metadata}
        timestamp = pd.Timestamp(row["decision_timestamp"]).strftime("%Y-%m-%dT%H:%M:%SZ")
        candidate_key = (
            f"{row['role']}|{row['month']}|{row['side']}|{row['row_scope']}|{timestamp}"
        )
        for horizon in horizons:
            model_used = (
                bool(row[f"pred_hv_{horizon}m_executable_model_used"])
                and bool(row[f"pred_hv_{horizon}m_pnl_model_used"])
                and bool(row[f"pred_hv_{horizon}m_tail_model_used"])
            )
            output_rows.append(
                {
                    **base,
                    "candidate_key": candidate_key,
                    "horizon_minutes": int(horizon),
                    "actual_pnl": float(row[f"side_fixed_{horizon}m_adjusted_pnl"]),
                    "pred_executable_prob": float(
                        row[f"pred_hv_{horizon}m_executable_prob"]
                    ),
                    "pred_pnl": float(row[f"effective_hv_{horizon}m_pred_pnl"]),
                    "pred_tail_loss_prob": float(
                        row[f"pred_hv_{horizon}m_tail_loss_prob"]
                    ),
                    "pred_model_used": bool(model_used),
                    "pred_executable_model_used": bool(
                        row[f"pred_hv_{horizon}m_executable_model_used"]
                    ),
                    "pred_pnl_model_used": bool(row[f"pred_hv_{horizon}m_pnl_model_used"]),
                    "pred_tail_model_used": bool(
                        row[f"pred_hv_{horizon}m_tail_model_used"]
                    ),
                }
            )
    return pd.DataFrame(output_rows)


def add_gate_columns(
    horizon_rows: pd.DataFrame,
    *,
    prefix: str,
    min_prob: float,
    min_pred_pnl: float,
    max_tail_prob: float,
    require_model_used: bool,
) -> pd.DataFrame:
    output = horizon_rows.copy()
    output[f"{prefix}_prob_pass"] = numeric_series(
        output,
        "pred_executable_prob",
        default=0.0,
    ).ge(min_prob)
    output[f"{prefix}_ev_pass"] = numeric_series(output, "pred_pnl", default=-np.inf).ge(
        min_pred_pnl
    )
    output[f"{prefix}_tail_pass"] = numeric_series(
        output,
        "pred_tail_loss_prob",
        default=1.0,
    ).le(max_tail_prob)
    output[f"{prefix}_model_pass"] = (
        bool_series(output, "pred_model_used")
        if require_model_used
        else pd.Series(True, index=output.index, dtype=bool)
    )
    output[f"{prefix}_gate_pass"] = (
        output[f"{prefix}_prob_pass"]
        & output[f"{prefix}_ev_pass"]
        & output[f"{prefix}_tail_pass"]
        & output[f"{prefix}_model_pass"]
    )
    return output


def summarize_gate(
    horizon_rows: pd.DataFrame,
    *,
    prefix: str,
    min_prob: float,
    min_pred_pnl: float,
    max_tail_prob: float,
    require_model_used: bool,
) -> pd.DataFrame:
    if horizon_rows.empty:
        return pd.DataFrame()
    frame = add_gate_columns(
        horizon_rows,
        prefix=prefix,
        min_prob=min_prob,
        min_pred_pnl=min_pred_pnl,
        max_tail_prob=max_tail_prob,
        require_model_used=require_model_used,
    )
    frame["choice_score"] = (
        numeric_series(frame, "pred_pnl", default=-np.inf)
        + numeric_series(frame, "pred_executable_prob", default=0.0)
        - numeric_series(frame, "pred_tail_loss_prob", default=1.0)
    )
    gate_column = f"{prefix}_gate_pass"
    choices = (
        frame[frame[gate_column]]
        .sort_values(
            [
                "role",
                "month",
                "side",
                "row_scope",
                "decision_timestamp",
                "choice_score",
            ],
            ascending=[True, True, True, True, True, False],
        )
        .drop_duplicates(
            ["role", "month", "side", "row_scope", "decision_timestamp"],
            keep="first",
        )
    )
    rows: list[dict[str, Any]] = []
    group_columns = ["role", "month", "side", "row_scope"]
    for key, group in frame.groupby(group_columns, dropna=False, sort=True):
        group_key = dict(zip(group_columns, key, strict=True))
        choice_group = choices
        for column, value in group_key.items():
            choice_group = choice_group[choice_group[column].eq(value)]
        choice_actual = numeric_series(choice_group, "actual_pnl", default=0.0)
        positive_actual = numeric_series(group, "actual_pnl", default=np.nan).gt(0.0)
        rows.append(
            {
                **group_key,
                f"{prefix}_horizon_count": int(len(group)),
                f"{prefix}_prob_pass_count": int(group[f"{prefix}_prob_pass"].sum()),
                f"{prefix}_ev_pass_count": int(group[f"{prefix}_ev_pass"].sum()),
                f"{prefix}_tail_pass_count": int(group[f"{prefix}_tail_pass"].sum()),
                f"{prefix}_model_pass_count": int(group[f"{prefix}_model_pass"].sum()),
                f"{prefix}_gate_pass_horizon_count": int(group[gate_column].sum()),
                f"{prefix}_choice_count": int(len(choice_group)),
                f"{prefix}_choice_actual_pnl_sum": float(choice_actual.sum())
                if len(choice_group)
                else 0.0,
                f"{prefix}_choice_positive_count": int(choice_actual.gt(0.0).sum())
                if len(choice_group)
                else 0,
                f"{prefix}_positive_actual_blocked_by_prob_count": int(
                    (positive_actual & ~group[f"{prefix}_prob_pass"]).sum()
                ),
                f"{prefix}_positive_actual_blocked_by_ev_count": int(
                    (positive_actual & ~group[f"{prefix}_ev_pass"]).sum()
                ),
                f"{prefix}_positive_actual_blocked_by_tail_count": int(
                    (positive_actual & ~group[f"{prefix}_tail_pass"]).sum()
                ),
                f"{prefix}_positive_actual_blocked_by_model_count": int(
                    (positive_actual & ~group[f"{prefix}_model_pass"]).sum()
                ),
            }
        )
    return pd.DataFrame(rows)


def summarize_replay_candidates(
    replay: pd.DataFrame,
    *,
    targets: list[tuple[str, str, str]],
    row_scopes: list[str],
) -> pd.DataFrame:
    if replay.empty:
        return pd.DataFrame()
    target_index = pd.MultiIndex.from_tuples(targets, names=["role", "month", "side"])
    current_index = pd.MultiIndex.from_frame(replay[["role", "month", "side"]])
    output = replay[current_index.isin(target_index)].copy()
    if row_scopes:
        output = output[output["row_scope"].isin(row_scopes)].copy()
    if output.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    for key, group in output.groupby(["role", "month", "side", "row_scope"], sort=True):
        actual = numeric_series(group, "actual_pnl_at_hv_chosen_horizon", default=0.0)
        rows.append(
            {
                **dict(
                    zip(
                        ["role", "month", "side", "row_scope"],
                        key,
                        strict=True,
                    )
                ),
                "replay_candidate_count": int(len(group)),
                "replay_model_used_count": int(
                    bool_series(group, "hv_chosen_pred_model_used").sum()
                ),
                "replay_actual_pnl_sum": float(actual.sum()),
                "replay_positive_count": int(actual.gt(0.0).sum()),
                "replay_negative_count": int(actual.lt(0.0).sum()),
                "replay_pred_pnl_max": float(
                    numeric_series(group, "hv_chosen_pred_pnl").max()
                ),
            }
        )
    return pd.DataFrame(rows)


def classify_gap(row: pd.Series) -> str:
    if int(row.get("role_month_rows", 0)) == 0:
        return "no_prediction_rows"
    if int(row.get("scope_rows", 0)) == 0:
        return "no_rows_in_scope"
    if int(row.get("target_side_rows", 0)) == 0:
        return "no_target_side_rows"
    if int(row.get("target_support_rows", 0)) == 0:
        return "no_target_support_rows"
    if int(row.get("horizon_rows", 0)) == 0:
        return "no_horizon_rows"
    if int(row.get("strict_choice_count", 0)) > 0:
        return "strict_candidate_exists"
    if int(row.get("relaxed_choice_count", 0)) > 0:
        return "relaxed_only_candidate"
    if int(row.get("model_used_horizon_count", 0)) == 0:
        return "no_model_used_horizons"
    return "threshold_filtered"


def target_scope_summary(
    predictions: pd.DataFrame,
    *,
    targets: list[tuple[str, str, str]],
    row_scopes: list[str],
    horizons: list[int],
    strict_summary: pd.DataFrame,
    relaxed_summary: pd.DataFrame,
    replay_summary: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    all_horizon_rows: list[pd.DataFrame] = []
    for role, month, side in targets:
        for row_scope in row_scopes:
            month_rows, scope_rows, side_rows, support_rows = select_target_scope_rows(
                predictions,
                role=role,
                month=month,
                side=side,
                row_scope=row_scope,
            )
            horizon_rows = horizon_long_frame(support_rows, horizons=horizons)
            if not horizon_rows.empty:
                all_horizon_rows.append(horizon_rows)
            actual = numeric_series(horizon_rows, "actual_pnl", default=np.nan)
            pred_pnl = numeric_series(horizon_rows, "pred_pnl", default=np.nan)
            prob = numeric_series(horizon_rows, "pred_executable_prob", default=np.nan)
            tail = numeric_series(horizon_rows, "pred_tail_loss_prob", default=np.nan)
            model_used = bool_series(horizon_rows, "pred_model_used")
            rows.append(
                {
                    "role": role,
                    "month": month,
                    "side": side,
                    "row_scope": row_scope,
                    "role_month_rows": int(len(month_rows)),
                    "scope_rows": int(len(scope_rows)),
                    "target_side_rows": int(len(side_rows)),
                    "target_support_rows": int(len(support_rows)),
                    "stateful_available_rows": int(
                        bool_series(support_rows, "stateful_available").sum()
                    ),
                    "selected_any_rows": int(
                        bool_series(support_rows, "selected_any").sum()
                    ),
                    "strict_side_specific_rows": int(
                        bool_series(support_rows, "strict_side_specific").sum()
                    ),
                    "relaxed_side_specific_rows": int(
                        bool_series(support_rows, "relaxed_side_specific").sum()
                    ),
                    "horizon_rows": int(len(horizon_rows)),
                    "model_used_horizon_count": int(model_used.sum()),
                    "actual_positive_horizon_count": int(actual.gt(0.0).sum()),
                    "actual_negative_horizon_count": int(actual.lt(0.0).sum()),
                    "best_oracle_actual_pnl": float(actual.max())
                    if actual.notna().any()
                    else np.nan,
                    "worst_oracle_actual_pnl": float(actual.min())
                    if actual.notna().any()
                    else np.nan,
                    "max_pred_pnl": float(pred_pnl.max()) if pred_pnl.notna().any() else np.nan,
                    "max_pred_executable_prob": float(prob.max())
                    if prob.notna().any()
                    else np.nan,
                    "min_pred_tail_loss_prob": float(tail.min())
                    if tail.notna().any()
                    else np.nan,
                }
            )

    summary = pd.DataFrame(rows)
    for prefix, gate_summary in [
        ("strict", strict_summary),
        ("relaxed", relaxed_summary),
    ]:
        if gate_summary.empty:
            continue
        summary = summary.merge(
            gate_summary,
            on=["role", "month", "side", "row_scope"],
            how="left",
        )
        for column in summary.columns:
            if column.startswith(f"{prefix}_") and column.endswith("_count"):
                summary[column] = numeric_series(summary, column, default=0.0).astype(int)
    if not replay_summary.empty:
        summary = summary.merge(
            replay_summary,
            on=["role", "month", "side", "row_scope"],
            how="left",
        )
    for column in [
        "strict_choice_count",
        "relaxed_choice_count",
        "replay_candidate_count",
        "replay_model_used_count",
    ]:
        if column in summary.columns:
            summary[column] = numeric_series(summary, column, default=0.0).astype(int)
    summary["gap_stage"] = [classify_gap(row) for _, row in summary.iterrows()]
    return summary.sort_values(["role", "month", "side", "row_scope"]).reset_index(
        drop=True
    )


def build_horizon_rows(
    predictions: pd.DataFrame,
    *,
    targets: list[tuple[str, str, str]],
    row_scopes: list[str],
    horizons: list[int],
) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for role, month, side in targets:
        for row_scope in row_scopes:
            _, _, _, support_rows = select_target_scope_rows(
                predictions,
                role=role,
                month=month,
                side=side,
                row_scope=row_scope,
            )
            frame = horizon_long_frame(support_rows, horizons=horizons)
            if not frame.empty:
                frames.append(frame)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--replay-candidates", type=Path, default=None)
    parser.add_argument("--output-root", type=Path, default=ROOT / "data" / "reports" / "backtests")
    parser.add_argument(
        "--run-label",
        default="entry_ev_candidate_generation_gap_audit",
    )
    parser.add_argument("--targets", default=DEFAULT_TARGETS)
    parser.add_argument("--row-scopes", default=DEFAULT_ROW_SCOPES)
    parser.add_argument("--horizons", default="60,240,720")
    parser.add_argument("--strict-min-prob", type=float, default=0.45)
    parser.add_argument("--strict-min-pred-pnl", type=float, default=0.0)
    parser.add_argument("--strict-max-tail-prob", type=float, default=0.50)
    parser.add_argument("--relaxed-min-prob", type=float, default=0.30)
    parser.add_argument("--relaxed-min-pred-pnl", type=float, default=-2.0)
    parser.add_argument("--relaxed-max-tail-prob", type=float, default=0.50)
    parser.add_argument(
        "--use-base-pnl",
        action="store_true",
        help="Use pred_hv_*_pnl even when ranker_hv_*_pred_pnl exists.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    targets = parse_targets(args.targets)
    row_scopes = parse_csv(args.row_scopes)
    horizons = parse_int_csv(args.horizons)
    predictions = normalize_predictions(
        pd.read_csv(args.predictions),
        horizons=horizons,
        prefer_ranker_pnl=not args.use_base_pnl,
    )
    horizon_rows = build_horizon_rows(
        predictions,
        targets=targets,
        row_scopes=row_scopes,
        horizons=horizons,
    )
    strict_summary = summarize_gate(
        horizon_rows,
        prefix="strict",
        min_prob=args.strict_min_prob,
        min_pred_pnl=args.strict_min_pred_pnl,
        max_tail_prob=args.strict_max_tail_prob,
        require_model_used=True,
    )
    relaxed_summary = summarize_gate(
        horizon_rows,
        prefix="relaxed",
        min_prob=args.relaxed_min_prob,
        min_pred_pnl=args.relaxed_min_pred_pnl,
        max_tail_prob=args.relaxed_max_tail_prob,
        require_model_used=True,
    )
    replay_summary = pd.DataFrame()
    if args.replay_candidates is not None and args.replay_candidates.exists():
        replay_summary = summarize_replay_candidates(
            normalize_replay_candidates(pd.read_csv(args.replay_candidates)),
            targets=targets,
            row_scopes=row_scopes,
        )
    summary = target_scope_summary(
        predictions,
        targets=targets,
        row_scopes=row_scopes,
        horizons=horizons,
        strict_summary=strict_summary,
        relaxed_summary=relaxed_summary,
        replay_summary=replay_summary,
    )

    run_dir = make_run_dir(args.output_root, args.run_label)
    summary.to_csv(run_dir / "candidate_generation_gap_target_scope_summary.csv", index=False)
    horizon_rows.to_csv(run_dir / "candidate_generation_gap_horizon_rows.csv", index=False)
    if not strict_summary.empty:
        strict_summary.to_csv(run_dir / "candidate_generation_gap_strict_gate_summary.csv", index=False)
    if not relaxed_summary.empty:
        relaxed_summary.to_csv(
            run_dir / "candidate_generation_gap_relaxed_gate_summary.csv",
            index=False,
        )
    if not replay_summary.empty:
        replay_summary.to_csv(
            run_dir / "candidate_generation_gap_replay_summary.csv",
            index=False,
        )
    meta = {
        "predictions": args.predictions,
        "replay_candidates": args.replay_candidates,
        "targets": targets,
        "row_scopes": row_scopes,
        "horizons": horizons,
        "strict": {
            "min_prob": args.strict_min_prob,
            "min_pred_pnl": args.strict_min_pred_pnl,
            "max_tail_prob": args.strict_max_tail_prob,
            "require_model_used": True,
        },
        "relaxed": {
            "min_prob": args.relaxed_min_prob,
            "min_pred_pnl": args.relaxed_min_pred_pnl,
            "max_tail_prob": args.relaxed_max_tail_prob,
            "require_model_used": True,
        },
        "prefer_ranker_pnl": not args.use_base_pnl,
        "output_files": {
            "target_scope_summary": run_dir
            / "candidate_generation_gap_target_scope_summary.csv",
            "horizon_rows": run_dir / "candidate_generation_gap_horizon_rows.csv",
        },
    }
    (run_dir / "candidate_generation_gap_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2, default=local_json_default),
        encoding="utf-8",
    )
    print(run_dir)


if __name__ == "__main__":
    main()
