#!/usr/bin/env python3
"""Build exit-timing targets for near-miss admission-repair candidates."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from trade_data.backtest import json_default, make_run_dir  # noqa: E402

from entry_ev_forced_exit_selector_inputs import parse_family_predictions  # noqa: E402


SIDE_LABELS = ("long", "short")
DEFAULT_HORIZONS = "60,240,720"
DEFAULT_GROUP_SPECS = (
    "row_scope;near_miss_bucket;selection_bucket;role;family;month;side;"
    "family,month;role,month;side,combined_regime,session_regime;"
    "near_miss_bucket,side;strict_failed_stage_count"
)
DEFAULT_THRESHOLDS = "-5,0,2,5,10"
REQUIRED_CANDIDATE_COLUMNS = {
    "family",
    "month",
    "decision_timestamp",
    "side",
    "side_score",
    "side_best_adjusted_pnl",
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
    return [part.strip() for part in value.split(",") if part.strip()]


def parse_int_csv(value: str) -> list[int]:
    return [int(part) for part in parse_csv(value)]


def parse_float_csv(value: str) -> list[float]:
    return [float(part) for part in parse_csv(value)]


def parse_group_specs(value: str) -> list[list[str]]:
    specs: list[list[str]] = []
    for raw_spec in value.split(";"):
        columns = parse_csv(raw_spec)
        if columns:
            specs.append(columns)
    return specs


def numeric_series(frame: pd.DataFrame, column: str, default: float = np.nan) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=float)
    values = pd.to_numeric(frame[column], errors="coerce")
    return values.replace([np.inf, -np.inf], np.nan).fillna(default).astype(float)


def bool_series(frame: pd.DataFrame, column: str, default: bool = False) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=bool)
    series = frame[column]
    if pd.api.types.is_bool_dtype(series):
        return series.fillna(default).astype(bool)
    if pd.api.types.is_numeric_dtype(series):
        return series.fillna(float(default)).astype(float).ne(0.0)
    return series.astype(str).str.lower().str.strip().isin({"true", "1", "yes", "y"})


def text_series(frame: pd.DataFrame, column: str, default: str = "missing") -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype="string")
    return (
        frame[column]
        .astype("string")
        .fillna(default)
        .str.strip()
        .replace({"": default, "nan": default, "None": default})
    )


def parquet_columns(path: Path) -> list[str]:
    return list(pq.ParquetFile(path).schema.names)


def month_series(frame: pd.DataFrame) -> pd.Series:
    if "dataset_month" in frame.columns:
        return frame["dataset_month"].astype(str).str.slice(0, 7)
    if "month" in frame.columns:
        return frame["month"].astype(str).str.slice(0, 7)
    if "decision_timestamp" in frame.columns:
        return pd.to_datetime(frame["decision_timestamp"], utc=True).dt.strftime("%Y-%m")
    raise ValueError("prediction frame needs dataset_month, month, or decision_timestamp")


def normalize_candidate_rows(frame: pd.DataFrame, *, horizons: list[int]) -> pd.DataFrame:
    missing = sorted(REQUIRED_CANDIDATE_COLUMNS - set(frame.columns))
    if missing:
        raise ValueError(f"candidate rows missing columns: {', '.join(missing)}")
    horizon_columns = {f"side_fixed_{horizon}m_adjusted_pnl" for horizon in horizons}
    missing_horizons = sorted(horizon_columns - set(frame.columns))
    if missing_horizons:
        raise ValueError(
            "candidate rows missing fixed horizon columns: " + ", ".join(missing_horizons)
        )

    output = frame.copy()
    output["family"] = text_series(output, "family")
    output["role"] = text_series(output, "role")
    output["month"] = text_series(output, "month").astype(str).str.slice(0, 7)
    output["side"] = text_series(output, "side").astype(str).str.lower()
    output["decision_timestamp"] = pd.to_datetime(
        output["decision_timestamp"],
        utc=True,
        errors="coerce",
    )
    for column in [
        "combined_regime",
        "session_regime",
        "needed_side",
    ]:
        output[column] = text_series(output, column)
    for column in [
        "side_score",
        "opposite_score",
        "side_margin",
        "score_pct",
        "side_margin_pct",
        "entry_rank_pct",
        "side_best_adjusted_pnl",
        "side_best_holding_minutes",
        "side_pred_holding_minutes",
        "strict_failed_stage_count",
        "target_pnl_hurdle",
        "target_trade_count",
        "target_long_trade_count",
        "target_short_trade_count",
        *[f"side_fixed_{horizon}m_adjusted_pnl" for horizon in horizons],
    ]:
        output[column] = numeric_series(output, column)
    for column in [
        "strict_side_specific",
        "relaxed_side_specific",
        "one_failed_strict_stage",
        "stateful_available",
        "holding_ok",
    ]:
        output[column] = bool_series(output, column)

    output = output[output["side"].isin(SIDE_LABELS)].copy()
    if output.empty:
        raise ValueError("no long/short candidate rows found")
    output["near_miss_bucket"] = np.select(
        [
            output["strict_side_specific"].astype(bool),
            output["relaxed_side_specific"].astype(bool),
            output["one_failed_strict_stage"].astype(bool),
        ],
        ["strict", "relaxed", "one_failed_strict_stage"],
        default="other",
    )
    output["row_scope"] = np.where(
        output["stateful_available"].astype(bool),
        "available_candidates",
        "stateful_blocked_candidates",
    )
    output["selection_bucket"] = "not_selected"
    output["selected_any"] = False
    return output.reset_index(drop=True)


def selection_key(frame: pd.DataFrame) -> pd.DataFrame:
    output = frame.copy()
    output["family"] = output["family"].astype(str)
    output["role"] = output["role"].astype(str)
    output["month"] = output["month"].astype(str).str.slice(0, 7)
    output["side"] = output["side"].astype(str).str.lower()
    output["decision_timestamp"] = pd.to_datetime(
        output["decision_timestamp"],
        utc=True,
        errors="coerce",
    )
    return output


def mark_selected_rows(candidates: pd.DataFrame, selected: pd.DataFrame | None) -> pd.DataFrame:
    if selected is None or selected.empty:
        return candidates.copy()
    required = {"family", "role", "month", "side", "decision_timestamp", "selection_bucket"}
    missing = sorted(required - set(selected.columns))
    if missing:
        raise ValueError(f"selection rows missing columns: {', '.join(missing)}")
    output = candidates.copy()
    selected_norm = selection_key(selected)
    selected_norm = selected_norm[
        ["family", "role", "month", "side", "decision_timestamp", "selection_bucket"]
    ].drop_duplicates()
    merged = output.merge(
        selected_norm,
        on=["family", "role", "month", "side", "decision_timestamp"],
        how="left",
        suffixes=("", "_selected"),
    )
    hit = merged["selection_bucket_selected"].notna()
    merged["selected_any"] = hit
    merged["selection_bucket"] = merged["selection_bucket_selected"].fillna("not_selected")
    merged["row_scope"] = np.where(hit, "greedy_selected", merged["row_scope"])
    return merged.drop(columns=["selection_bucket_selected"])


def add_fixed_horizon_targets(
    frame: pd.DataFrame,
    *,
    horizons: list[int],
    min_executable_pnl: float,
) -> pd.DataFrame:
    output = frame.copy()
    actual_columns = [f"side_fixed_{horizon}m_adjusted_pnl" for horizon in horizons]
    actual = output[actual_columns].astype(float)
    actual_filled = actual.fillna(-np.inf)
    best_idx = actual_filled.to_numpy(dtype=float).argmax(axis=1)
    best_values = actual_filled.to_numpy(dtype=float)[np.arange(len(output)), best_idx]
    best_values = np.where(np.isfinite(best_values), best_values, np.nan)
    best_horizons = np.array(horizons, dtype=int)[best_idx]
    fixed60_column = "side_fixed_60m_adjusted_pnl"
    output["target_fixed_best_adjusted_pnl"] = best_values
    output["target_fixed_best_horizon_minutes"] = best_horizons
    output["target_fixed_executable"] = output["target_fixed_best_adjusted_pnl"].ge(
        min_executable_pnl
    )
    output["target_fixed_executable_horizon_minutes"] = np.where(
        output["target_fixed_executable"],
        output["target_fixed_best_horizon_minutes"],
        0,
    )
    output["target_fixed_all_negative"] = actual.max(axis=1).lt(min_executable_pnl)
    if fixed60_column in output.columns:
        output["target_fixed_best_vs_60m_delta"] = (
            output["target_fixed_best_adjusted_pnl"] - output[fixed60_column].astype(float)
        )
        output["target_fixed60_loss_rescuable"] = (
            output[fixed60_column].astype(float).lt(min_executable_pnl)
            & output["target_fixed_executable"].astype(bool)
        )
    else:
        output["target_fixed_best_vs_60m_delta"] = np.nan
        output["target_fixed60_loss_rescuable"] = False
    output["target_oracle_gap_vs_fixed_best"] = (
        output["side_best_adjusted_pnl"].astype(float)
        - output["target_fixed_best_adjusted_pnl"].astype(float)
    )
    oracle = output["side_best_adjusted_pnl"].astype(float)
    output["target_fixed_best_oracle_capture_ratio"] = np.where(
        oracle.gt(0.0),
        output["target_fixed_best_adjusted_pnl"].astype(float) / oracle,
        np.nan,
    )
    return output


def prediction_columns_for_horizons(horizons: list[int]) -> list[str]:
    columns = ["decision_timestamp", "dataset_month", "month"]
    for side in SIDE_LABELS:
        columns.extend(
            [
                f"pred_{side}_fixed_{horizon}m_adjusted_pnl"
                for horizon in horizons
            ]
        )
        columns.extend(
            [
                f"pred_{side}_exit_event_minutes",
                f"pred_mlp_{side}_exit_event_minutes",
                f"pred_{side}_exit_event_time_bin_expected_minutes",
                f"pred_{side}_exit_event_prob_0",
                f"pred_{side}_exit_event_prob_1",
                f"pred_{side}_exit_event_prob_2",
            ]
        )
    return columns


def load_prediction_side_rows(
    *,
    family_predictions: dict[str, Path],
    target_months: dict[str, list[str]],
    horizons: list[int],
) -> pd.DataFrame:
    parts: list[pd.DataFrame] = []
    needed_columns = prediction_columns_for_horizons(horizons)
    for family, months in target_months.items():
        if family not in family_predictions:
            continue
        path = family_predictions[family]
        columns = parquet_columns(path)
        read_columns = [column for column in dict.fromkeys(needed_columns) if column in columns]
        if "decision_timestamp" not in read_columns:
            raise ValueError(f"{path} missing decision_timestamp")
        predictions = pd.read_parquet(path, columns=read_columns)
        predictions["month"] = month_series(predictions)
        predictions = predictions[predictions["month"].isin(months)].copy()
        if predictions.empty:
            continue
        predictions["decision_timestamp"] = pd.to_datetime(
            predictions["decision_timestamp"],
            utc=True,
            errors="coerce",
        )
        for side in SIDE_LABELS:
            side_rows = pd.DataFrame(
                {
                    "family": family,
                    "month": predictions["month"].astype(str).str.slice(0, 7),
                    "decision_timestamp": predictions["decision_timestamp"],
                    "side": side,
                }
            )
            for horizon in horizons:
                side_rows[f"pred_fixed_{horizon}m_adjusted_pnl"] = numeric_series(
                    predictions,
                    f"pred_{side}_fixed_{horizon}m_adjusted_pnl",
                )
            for column_suffix in [
                "exit_event_minutes",
                "exit_event_time_bin_expected_minutes",
                "exit_event_prob_0",
                "exit_event_prob_1",
                "exit_event_prob_2",
            ]:
                side_rows[f"pred_{column_suffix}"] = numeric_series(
                    predictions,
                    f"pred_{side}_{column_suffix}",
                )
            side_rows["pred_mlp_exit_event_minutes"] = numeric_series(
                predictions,
                f"pred_mlp_{side}_exit_event_minutes",
            )
            parts.append(side_rows)
    if not parts:
        return pd.DataFrame()
    return pd.concat(parts, ignore_index=True).drop_duplicates(
        ["family", "month", "decision_timestamp", "side"]
    )


def enrich_with_prediction_rows(
    candidates: pd.DataFrame,
    *,
    family_predictions: dict[str, Path],
    horizons: list[int],
) -> pd.DataFrame:
    if not family_predictions:
        return candidates.copy()
    target_months = {
        str(family): sorted(group["month"].astype(str).unique().tolist())
        for family, group in candidates.groupby("family", dropna=False)
    }
    prediction_rows = load_prediction_side_rows(
        family_predictions=family_predictions,
        target_months=target_months,
        horizons=horizons,
    )
    if prediction_rows.empty:
        return candidates.copy()
    return candidates.merge(
        prediction_rows,
        on=["family", "month", "decision_timestamp", "side"],
        how="left",
    )


def add_predicted_fixed_choice(
    frame: pd.DataFrame,
    *,
    horizons: list[int],
    min_predicted_pnl: float,
    min_executable_pnl: float,
) -> pd.DataFrame:
    output = frame.copy()
    pred_columns = [f"pred_fixed_{horizon}m_adjusted_pnl" for horizon in horizons]
    if not all(column in output.columns for column in pred_columns):
        output["pred_fixed_available"] = False
        output["pred_fixed_best_adjusted_pnl"] = np.nan
        output["pred_fixed_best_horizon_minutes"] = 0
        output["actual_pnl_at_pred_fixed_best_horizon"] = np.nan
        output["pred_fixed_choice_executable"] = False
        output["pred_fixed_choice_regret"] = np.nan
        output["pred_fixed_best_error"] = np.nan
        return output

    pred = output[pred_columns].astype(float)
    pred_available = pred.notna().any(axis=1)
    filled_pred = pred.fillna(-np.inf)
    best_idx = filled_pred.to_numpy(dtype=float).argmax(axis=1)
    best_values = filled_pred.to_numpy(dtype=float)[np.arange(len(output)), best_idx]
    best_horizons = np.array(horizons, dtype=int)[best_idx]
    best_horizons = np.where(best_values >= min_predicted_pnl, best_horizons, 0)
    best_values = np.where(best_horizons > 0, best_values, np.nan)
    output["pred_fixed_available"] = pred_available
    output["pred_fixed_best_adjusted_pnl"] = best_values
    output["pred_fixed_best_horizon_minutes"] = best_horizons

    actual_at_pred = np.zeros(len(output), dtype=float)
    actual_at_pred[:] = np.nan
    for horizon in horizons:
        mask = output["pred_fixed_best_horizon_minutes"].astype(int).eq(horizon)
        actual_at_pred[mask.to_numpy()] = numeric_series(
            output.loc[mask],
            f"side_fixed_{horizon}m_adjusted_pnl",
        ).to_numpy(dtype=float)
        output[f"pred_fixed_{horizon}m_error"] = (
            output[f"pred_fixed_{horizon}m_adjusted_pnl"].astype(float)
            - output[f"side_fixed_{horizon}m_adjusted_pnl"].astype(float)
        )
    output["actual_pnl_at_pred_fixed_best_horizon"] = actual_at_pred
    output["pred_fixed_choice_executable"] = output[
        "actual_pnl_at_pred_fixed_best_horizon"
    ].ge(min_executable_pnl)
    output["pred_fixed_choice_regret"] = (
        output["target_fixed_best_adjusted_pnl"].astype(float)
        - output["actual_pnl_at_pred_fixed_best_horizon"].astype(float)
    )
    output["pred_fixed_best_error"] = (
        output["pred_fixed_best_adjusted_pnl"].astype(float)
        - output["target_fixed_best_adjusted_pnl"].astype(float)
    )
    return output


def safe_spearman(left: pd.Series, right: pd.Series) -> float:
    frame = pd.DataFrame({"left": left, "right": right}).replace([np.inf, -np.inf], np.nan)
    frame = frame.dropna()
    if len(frame) < 2 or frame["left"].nunique() < 2 or frame["right"].nunique() < 2:
        return float("nan")
    return float(frame["left"].corr(frame["right"], method="spearman"))


def score_summary(frame: pd.DataFrame, *, horizons: list[int]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    score_specs = [
        ("side_score", "target_fixed_best_adjusted_pnl"),
        ("side_score", "side_best_adjusted_pnl"),
        ("pred_fixed_best_adjusted_pnl", "target_fixed_best_adjusted_pnl"),
    ]
    for horizon in horizons:
        score_specs.append(
            (
                f"pred_fixed_{horizon}m_adjusted_pnl",
                f"side_fixed_{horizon}m_adjusted_pnl",
            )
        )
    for scope, scope_frame in frame.groupby("row_scope", dropna=False):
        for score_column, target_column in score_specs:
            if score_column not in scope_frame.columns or target_column not in scope_frame.columns:
                continue
            score = numeric_series(scope_frame, score_column)
            target = numeric_series(scope_frame, target_column)
            valid = score.notna() & target.notna()
            if not valid.any():
                continue
            error = score[valid] - target[valid]
            rows.append(
                {
                    "row_scope": scope,
                    "score_column": score_column,
                    "target_column": target_column,
                    "row_count": int(valid.sum()),
                    "score_mean": float(score[valid].mean()),
                    "target_mean": float(target[valid].mean()),
                    "bias": float(error.mean()),
                    "mae": float(error.abs().mean()),
                    "rmse": float(np.sqrt((error**2).mean())),
                    "spearman": safe_spearman(score[valid], target[valid]),
                    "overestimate_rate": float(error.gt(0.0).mean()),
                    "overestimate_sum": float(error.clip(lower=0.0).sum()),
                }
            )
    return pd.DataFrame(rows)


def summarize_group(frame: pd.DataFrame) -> dict[str, Any]:
    pred_available = bool_series(frame, "pred_fixed_available")
    pred_selected = numeric_series(frame, "pred_fixed_best_horizon_minutes", default=0.0).gt(0.0)
    pred_actual = numeric_series(frame, "actual_pnl_at_pred_fixed_best_horizon")
    return {
        "row_count": int(len(frame)),
        "available_count": int(bool_series(frame, "stateful_available").sum()),
        "selected_count": int(bool_series(frame, "selected_any").sum()),
        "strict_count": int(bool_series(frame, "strict_side_specific").sum()),
        "relaxed_count": int(bool_series(frame, "relaxed_side_specific").sum()),
        "onefail_count": int(bool_series(frame, "one_failed_strict_stage").sum()),
        "fixed_best_pnl_sum": float(numeric_series(frame, "target_fixed_best_adjusted_pnl").sum()),
        "fixed_best_pnl_mean": float(
            numeric_series(frame, "target_fixed_best_adjusted_pnl").mean()
        ),
        "fixed_executable_count": int(bool_series(frame, "target_fixed_executable").sum()),
        "fixed_executable_rate": float(bool_series(frame, "target_fixed_executable").mean()),
        "fixed60_sum": float(numeric_series(frame, "side_fixed_60m_adjusted_pnl").sum()),
        "fixed240_sum": float(numeric_series(frame, "side_fixed_240m_adjusted_pnl").sum()),
        "fixed720_sum": float(numeric_series(frame, "side_fixed_720m_adjusted_pnl").sum()),
        "oracle_best_sum": float(numeric_series(frame, "side_best_adjusted_pnl").sum()),
        "oracle_gap_sum": float(numeric_series(frame, "target_oracle_gap_vs_fixed_best").sum()),
        "fixed60_loss_rescuable_count": int(
            bool_series(frame, "target_fixed60_loss_rescuable").sum()
        ),
        "pred_fixed_available_count": int(pred_available.sum()),
        "pred_fixed_selected_count": int(pred_selected.sum()),
        "pred_choice_actual_pnl_sum": float(pred_actual[pred_selected].sum())
        if pred_selected.any()
        else 0.0,
        "pred_choice_executable_count": int(
            bool_series(frame, "pred_fixed_choice_executable").sum()
        ),
        "pred_choice_regret_sum": float(
            numeric_series(frame, "pred_fixed_choice_regret").dropna().sum()
        ),
    }


def group_summary(frame: pd.DataFrame, group_specs: list[list[str]]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for columns in group_specs:
        available = [column for column in columns if column in frame.columns]
        if not available:
            continue
        for keys, group in frame.groupby(available, dropna=False):
            if not isinstance(keys, tuple):
                keys = (keys,)
            row = {
                "group_spec": ",".join(available),
                "group_key": "|".join(str(value) for value in keys),
            }
            row.update(dict(zip(available, keys)))
            row.update(summarize_group(group))
            rows.append(row)
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(
        ["group_spec", "fixed_best_pnl_sum", "row_count"],
        ascending=[True, True, False],
    )


def threshold_summary(frame: pd.DataFrame, thresholds: list[float]) -> pd.DataFrame:
    if "pred_fixed_best_adjusted_pnl" not in frame.columns:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    pred_score = numeric_series(frame, "pred_fixed_best_adjusted_pnl")
    pred_actual = numeric_series(frame, "actual_pnl_at_pred_fixed_best_horizon")
    for scope, scope_frame in frame.groupby("row_scope", dropna=False):
        scope_index = scope_frame.index
        for threshold in thresholds:
            flag = pred_score.loc[scope_index].ge(threshold)
            flagged = scope_frame.loc[flag]
            rows.append(
                {
                    "row_scope": scope,
                    "threshold": float(threshold),
                    "row_count": int(len(scope_frame)),
                    "flagged_count": int(flag.sum()),
                    "flagged_actual_pnl_sum": float(pred_actual.loc[flagged.index].sum())
                    if len(flagged)
                    else 0.0,
                    "flagged_fixed_best_pnl_sum": float(
                        numeric_series(flagged, "target_fixed_best_adjusted_pnl").sum()
                    )
                    if len(flagged)
                    else 0.0,
                    "flagged_oracle_best_sum": float(
                        numeric_series(flagged, "side_best_adjusted_pnl").sum()
                    )
                    if len(flagged)
                    else 0.0,
                    "flagged_executable_count": int(
                        bool_series(flagged, "pred_fixed_choice_executable").sum()
                    )
                    if len(flagged)
                    else 0,
                    "flagged_executable_rate": float(
                        bool_series(flagged, "pred_fixed_choice_executable").mean()
                    )
                    if len(flagged)
                    else float("nan"),
                }
            )
    return pd.DataFrame(rows).sort_values(
        ["row_scope", "flagged_actual_pnl_sum", "flagged_count"],
        ascending=[True, False, False],
    )


def horizon_summary(frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for scope, scope_frame in frame.groupby("row_scope", dropna=False):
        for target_horizon, group in scope_frame.groupby(
            "target_fixed_best_horizon_minutes",
            dropna=False,
        ):
            rows.append(
                {
                    "row_scope": scope,
                    "horizon_kind": "actual_best_fixed",
                    "horizon_minutes": int(target_horizon),
                    **summarize_group(group),
                }
            )
        if "pred_fixed_best_horizon_minutes" not in scope_frame.columns:
            continue
        for pred_horizon, group in scope_frame.groupby(
            "pred_fixed_best_horizon_minutes",
            dropna=False,
        ):
            rows.append(
                {
                    "row_scope": scope,
                    "horizon_kind": "predicted_best_fixed",
                    "horizon_minutes": int(pred_horizon),
                    **summarize_group(group),
                }
            )
    return pd.DataFrame(rows).sort_values(
        ["row_scope", "horizon_kind", "horizon_minutes"]
    )


def build_diagnostics(args: argparse.Namespace) -> Path:
    horizons = parse_int_csv(args.horizons)
    candidates = normalize_candidate_rows(pd.read_csv(args.candidate_rows), horizons=horizons)
    selected = pd.read_csv(args.selected_rows) if args.selected_rows else None
    candidates = mark_selected_rows(candidates, selected)
    candidates = add_fixed_horizon_targets(
        candidates,
        horizons=horizons,
        min_executable_pnl=args.min_executable_pnl,
    )
    family_predictions = (
        parse_family_predictions(args.family_predictions)
        if args.family_predictions
        else {}
    )
    enriched = enrich_with_prediction_rows(
        candidates,
        family_predictions=family_predictions,
        horizons=horizons,
    )
    enriched = add_predicted_fixed_choice(
        enriched,
        horizons=horizons,
        min_predicted_pnl=args.min_predicted_pnl,
        min_executable_pnl=args.min_executable_pnl,
    )

    run_dir = make_run_dir(args.output_dir, args.label)
    enriched.to_csv(run_dir / "near_miss_exit_target_rows.csv", index=False)
    summary = group_summary(enriched, parse_group_specs(args.group_specs))
    scores = score_summary(enriched, horizons=horizons)
    thresholds = threshold_summary(enriched, parse_float_csv(args.thresholds))
    horizons_out = horizon_summary(enriched)
    summary.to_csv(run_dir / "near_miss_exit_target_group_summary.csv", index=False)
    scores.to_csv(run_dir / "near_miss_exit_target_score_summary.csv", index=False)
    thresholds.to_csv(run_dir / "near_miss_exit_target_threshold_summary.csv", index=False)
    horizons_out.to_csv(run_dir / "near_miss_exit_target_horizon_summary.csv", index=False)
    config = {
        "candidate_rows": args.candidate_rows,
        "selected_rows": args.selected_rows,
        "family_predictions": family_predictions,
        "horizons": horizons,
        "min_executable_pnl": args.min_executable_pnl,
        "min_predicted_pnl": args.min_predicted_pnl,
        "thresholds": args.thresholds,
        "group_specs": args.group_specs,
        "row_count": int(len(enriched)),
    }
    (run_dir / "config.json").write_text(
        json.dumps(config, indent=2, sort_keys=True, default=local_json_default) + "\n",
        encoding="utf-8",
    )

    print("Near-miss exit target score summary:")
    print(scores.to_string(index=False))
    print("\nNear-miss exit target horizon summary:")
    print(horizons_out.to_string(index=False))
    print(f"artifacts: {run_dir}")
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-rows", type=Path, required=True)
    parser.add_argument("--selected-rows", type=Path)
    parser.add_argument("--family-predictions", action="append")
    parser.add_argument("--horizons", default=DEFAULT_HORIZONS)
    parser.add_argument("--min-executable-pnl", type=float, default=0.0)
    parser.add_argument("--min-predicted-pnl", type=float, default=0.0)
    parser.add_argument("--thresholds", default=DEFAULT_THRESHOLDS)
    parser.add_argument("--group-specs", default=DEFAULT_GROUP_SPECS)
    parser.add_argument("--output-dir", type=Path, default=Path("data/reports/backtests"))
    parser.add_argument("--label", default="entry_ev_near_miss_exit_target_diagnostics")
    return parser


def main(argv: list[str] | None = None) -> int:
    build_diagnostics(build_parser().parse_args(argv))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
