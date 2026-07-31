#!/usr/bin/env python3
"""Diagnose residual losses after direction-inversion adjusted scoring."""

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

from trade_data.backtest import (  # noqa: E402
    enrich_trades_with_predictions,
    json_default,
    make_run_dir,
    prepare_analysis_predictions,
    read_trades_csv,
)


DEFAULT_EXTRA_COLUMNS = [
    "combined_regime",
    "session_regime",
    "pred_direction_inversion_long_predicted_direction_inversion_risk",
    "pred_direction_inversion_short_predicted_direction_inversion_risk",
    "pred_direction_inversion_long_direction_inversion_prediction_support",
    "pred_direction_inversion_short_direction_inversion_prediction_support",
    "pred_direction_inversion_long_direction_inversion_prediction_source",
    "pred_direction_inversion_short_direction_inversion_prediction_source",
    "pred_direction_inversion_long_selected_risk_bucket",
    "pred_direction_inversion_short_selected_risk_bucket",
    "pred_direction_inversion_long_selected_side_support_bucket",
    "pred_direction_inversion_short_selected_side_support_bucket",
    "pred_direction_inversion_long_selected_side_pressure_bucket",
    "pred_direction_inversion_short_selected_side_pressure_bucket",
    "pred_replacement_quality_risk_pressure_long_predicted_replacement_quality",
    "pred_replacement_quality_risk_pressure_short_predicted_replacement_quality",
    "pred_replacement_quality_risk_pressure_long_replacement_quality_prediction_support",
    "pred_replacement_quality_risk_pressure_short_replacement_quality_prediction_support",
    "pred_replacement_quality_risk_pressure_long_replacement_quality_prediction_source",
    "pred_replacement_quality_risk_pressure_short_replacement_quality_prediction_source",
    "pred_replacement_quality_risk_pressure_long_selected_risk_bucket",
    "pred_replacement_quality_risk_pressure_short_selected_risk_bucket",
    "pred_replacement_quality_risk_pressure_long_selected_side_support_bucket",
    "pred_replacement_quality_risk_pressure_short_selected_side_support_bucket",
    "pred_replacement_quality_risk_pressure_long_selected_side_pressure_bucket",
    "pred_replacement_quality_risk_pressure_short_selected_side_pressure_bucket",
    "pred_side_prior_pressure_long_predicted_ev_overestimate_risk",
    "pred_side_prior_pressure_short_predicted_ev_overestimate_risk",
    "pred_side_prior_pressure_long_ev_overestimate_prediction_source",
    "pred_side_prior_pressure_short_ev_overestimate_prediction_source",
    "pred_mlp_long_exit_event_minutes",
    "pred_mlp_short_exit_event_minutes",
    "pred_long_exit_event_prob_0",
    "pred_short_exit_event_prob_0",
    "pred_long_exit_event_prob_2",
    "pred_short_exit_event_prob_2",
    "pred_long_profit_barrier_hit",
    "pred_short_profit_barrier_hit",
    "pred_long_fixed_60m_adjusted_pnl",
    "pred_short_fixed_60m_adjusted_pnl",
    "pred_long_fixed_240m_adjusted_pnl",
    "pred_short_fixed_240m_adjusted_pnl",
    "pred_long_fixed_720m_adjusted_pnl",
    "pred_short_fixed_720m_adjusted_pnl",
    "long_fixed_60m_adjusted_pnl",
    "short_fixed_60m_adjusted_pnl",
    "long_fixed_240m_adjusted_pnl",
    "short_fixed_240m_adjusted_pnl",
    "long_fixed_720m_adjusted_pnl",
    "short_fixed_720m_adjusted_pnl",
]

TARGET_FLAGS = [
    "residual_loss_target",
    "large_loss_target",
    "direction_side_inversion_target",
    "exit_capture_failure_target",
    "low_capture_with_oracle_edge_target",
    "forced_exit_loss_target",
    "profit_barrier_miss_loss_target",
    "ev_overestimate_loss_target",
    "hold_too_long_loss_target",
    "low_direction_risk_large_loss_target",
    "low_replacement_quality_loss_target",
]

MONTHLY_METRIC_FILENAMES = (
    "monthly_policy_metrics.csv",
    "monthly_exit_timing_metrics.csv",
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


def parse_csv(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def parse_policy_runs(values: list[str]) -> dict[str, Path]:
    runs: dict[str, Path] = {}
    for value in values:
        if "=" not in value:
            raise argparse.ArgumentTypeError("policy runs must use name=path")
        name, path = value.split("=", 1)
        name = name.strip()
        if not name:
            raise argparse.ArgumentTypeError("policy run name must not be empty")
        runs[name] = Path(path.strip())
    if not runs:
        raise argparse.ArgumentTypeError("at least one policy run is required")
    return runs


def numeric_series(frame: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=float)
    values = pd.to_numeric(frame[column], errors="coerce")
    return values.where(np.isfinite(values), default).fillna(default).astype(float)


def bool_series(frame: pd.DataFrame, column: str, default: bool = False) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=bool)
    values = frame[column]
    if pd.api.types.is_bool_dtype(values):
        return values.fillna(default).astype(bool)
    if pd.api.types.is_numeric_dtype(values):
        return values.fillna(float(default)).astype(float).ne(0.0)
    normalized = values.astype(str).str.lower().str.strip()
    return normalized.isin({"true", "1", "yes", "y"})


def text_series(frame: pd.DataFrame, column: str, default: str = "missing") -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index)
    return (
        frame[column]
        .fillna(default)
        .astype(str)
        .str.strip()
        .replace({"": default, "nan": default, "None": default})
    )


def selected_side_value(
    frame: pd.DataFrame,
    *,
    long_column: str,
    short_column: str,
    default: float = 0.0,
) -> pd.Series:
    direction = frame["direction"].astype(str).str.lower()
    long_values = numeric_series(frame, long_column, default=default)
    short_values = numeric_series(frame, short_column, default=default)
    return pd.Series(np.where(direction.eq("long"), long_values, short_values), index=frame.index)


def selected_side_text(
    frame: pd.DataFrame,
    *,
    long_column: str,
    short_column: str,
    default: str = "missing",
) -> pd.Series:
    direction = frame["direction"].astype(str).str.lower()
    long_values = text_series(frame, long_column, default=default)
    short_values = text_series(frame, short_column, default=default)
    return pd.Series(np.where(direction.eq("long"), long_values, short_values), index=frame.index)


def read_monthly_metrics(run_dir: Path) -> pd.DataFrame:
    path = next(
        (run_dir / name for name in MONTHLY_METRIC_FILENAMES if (run_dir / name).exists()),
        None,
    )
    if path is None:
        expected = ", ".join(MONTHLY_METRIC_FILENAMES)
        raise FileNotFoundError(f"{run_dir} has none of: {expected}")
    frame = pd.read_csv(path)
    required = {"family", "role", "month", "candidate"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"{path} missing columns: {', '.join(missing)}")
    return frame


def trade_path(run_dir: Path, row: pd.Series) -> Path:
    family = str(row["family"])
    candidate = str(row["candidate"])
    month = str(row["month"])
    variant = str(row.get("variant", "")).strip()
    if variant and variant.lower() != "nan":
        variant_path = run_dir / "trades" / family / variant / candidate / f"{month}.csv"
        if variant_path.exists():
            return variant_path
    return run_dir / "trades" / family / candidate / f"{month}.csv"


def read_policy_run_trades(
    *,
    run_name: str,
    run_dir: Path,
    predictions: pd.DataFrame,
    long_column: str,
    short_column: str,
    extra_prediction_columns: list[str],
) -> pd.DataFrame:
    analysis_predictions = prepare_analysis_predictions(
        predictions,
        long_column,
        short_column,
        extra_prediction_columns,
    )
    monthly = read_monthly_metrics(run_dir)
    frames: list[pd.DataFrame] = []
    missing_paths: list[Path] = []
    for _, row in monthly.iterrows():
        path = trade_path(run_dir, row)
        if not path.exists():
            missing_paths.append(path)
            continue
        trades = read_trades_csv(path)
        if trades.empty:
            continue
        enriched = enrich_trades_with_predictions(
            trades,
            analysis_predictions,
            extra_prediction_columns,
        )
        enriched.insert(0, "run_name", run_name)
        enriched.insert(1, "family", str(row["family"]))
        enriched.insert(2, "role", str(row["role"]))
        enriched.insert(3, "variant", str(row.get("variant", "base")))
        enriched.insert(4, "month", str(row["month"]))
        enriched.insert(5, "candidate", str(row["candidate"]))
        frames.append(enriched)
    if missing_paths:
        preview = ", ".join(str(path) for path in missing_paths[:5])
        suffix = "" if len(missing_paths) <= 5 else f" ... ({len(missing_paths)} missing)"
        raise FileNotFoundError(f"missing trade files: {preview}{suffix}")
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def exit_capture_ratio(realized: pd.Series, oracle_edge: pd.Series) -> pd.Series:
    realized_positive = realized.astype(float).clip(lower=0.0)
    oracle = oracle_edge.astype(float)
    ratio = np.where(oracle > 0.0, realized_positive / oracle.replace(0.0, np.nan), np.nan)
    return pd.Series(ratio, index=realized.index).fillna(0.0).clip(0.0, 1.0)


def add_selected_residual_features(frame: pd.DataFrame) -> pd.DataFrame:
    output = frame.copy()
    output["selected_direction_inversion_risk"] = selected_side_value(
        output,
        long_column="pred_direction_inversion_long_predicted_direction_inversion_risk",
        short_column="pred_direction_inversion_short_predicted_direction_inversion_risk",
        default=np.nan,
    )
    output["selected_direction_inversion_support"] = selected_side_value(
        output,
        long_column="pred_direction_inversion_long_direction_inversion_prediction_support",
        short_column="pred_direction_inversion_short_direction_inversion_prediction_support",
    )
    output["selected_direction_inversion_source"] = selected_side_text(
        output,
        long_column="pred_direction_inversion_long_direction_inversion_prediction_source",
        short_column="pred_direction_inversion_short_direction_inversion_prediction_source",
    )
    output["selected_direction_risk_bucket"] = selected_side_text(
        output,
        long_column="pred_direction_inversion_long_selected_risk_bucket",
        short_column="pred_direction_inversion_short_selected_risk_bucket",
    )
    output["selected_direction_support_bucket"] = selected_side_text(
        output,
        long_column="pred_direction_inversion_long_selected_side_support_bucket",
        short_column="pred_direction_inversion_short_selected_side_support_bucket",
    )
    output["selected_direction_pressure_bucket"] = selected_side_text(
        output,
        long_column="pred_direction_inversion_long_selected_side_pressure_bucket",
        short_column="pred_direction_inversion_short_selected_side_pressure_bucket",
    )
    output["selected_replacement_quality"] = selected_side_value(
        output,
        long_column="pred_replacement_quality_risk_pressure_long_predicted_replacement_quality",
        short_column="pred_replacement_quality_risk_pressure_short_predicted_replacement_quality",
        default=np.nan,
    )
    output["selected_replacement_quality_support"] = selected_side_value(
        output,
        long_column="pred_replacement_quality_risk_pressure_long_replacement_quality_prediction_support",
        short_column="pred_replacement_quality_risk_pressure_short_replacement_quality_prediction_support",
    )
    output["selected_replacement_quality_source"] = selected_side_text(
        output,
        long_column="pred_replacement_quality_risk_pressure_long_replacement_quality_prediction_source",
        short_column="pred_replacement_quality_risk_pressure_short_replacement_quality_prediction_source",
    )
    output["selected_ev_overestimate_risk"] = selected_side_value(
        output,
        long_column="pred_side_prior_pressure_long_predicted_ev_overestimate_risk",
        short_column="pred_side_prior_pressure_short_predicted_ev_overestimate_risk",
        default=np.nan,
    )
    output["selected_ev_overestimate_source"] = selected_side_text(
        output,
        long_column="pred_side_prior_pressure_long_ev_overestimate_prediction_source",
        short_column="pred_side_prior_pressure_short_ev_overestimate_prediction_source",
    )
    output["selected_pred_mlp_exit_minutes"] = selected_side_value(
        output,
        long_column="pred_mlp_long_exit_event_minutes",
        short_column="pred_mlp_short_exit_event_minutes",
        default=np.nan,
    )
    output["selected_time_exit_prob"] = selected_side_value(
        output,
        long_column="pred_long_exit_event_prob_0",
        short_column="pred_short_exit_event_prob_0",
        default=np.nan,
    )
    output["selected_loss_first_prob"] = selected_side_value(
        output,
        long_column="pred_long_exit_event_prob_2",
        short_column="pred_short_exit_event_prob_2",
        default=np.nan,
    )
    output["selected_fixed_60m_pred_pnl"] = selected_side_value(
        output,
        long_column="pred_long_fixed_60m_adjusted_pnl",
        short_column="pred_short_fixed_60m_adjusted_pnl",
        default=np.nan,
    )
    output["selected_fixed_240m_pred_pnl"] = selected_side_value(
        output,
        long_column="pred_long_fixed_240m_adjusted_pnl",
        short_column="pred_short_fixed_240m_adjusted_pnl",
        default=np.nan,
    )
    output["selected_fixed_720m_pred_pnl"] = selected_side_value(
        output,
        long_column="pred_long_fixed_720m_adjusted_pnl",
        short_column="pred_short_fixed_720m_adjusted_pnl",
        default=np.nan,
    )
    output["selected_fixed_60m_actual_pnl"] = selected_side_value(
        output,
        long_column="long_fixed_60m_adjusted_pnl",
        short_column="short_fixed_60m_adjusted_pnl",
        default=np.nan,
    )
    output["selected_fixed_240m_actual_pnl"] = selected_side_value(
        output,
        long_column="long_fixed_240m_adjusted_pnl",
        short_column="short_fixed_240m_adjusted_pnl",
        default=np.nan,
    )
    output["selected_fixed_720m_actual_pnl"] = selected_side_value(
        output,
        long_column="long_fixed_720m_adjusted_pnl",
        short_column="short_fixed_720m_adjusted_pnl",
        default=np.nan,
    )
    output["exit_capture_ratio"] = exit_capture_ratio(
        numeric_series(output, "adjusted_pnl"),
        numeric_series(output, "actual_taken_best_adjusted_pnl", default=np.nan),
    )
    return output


def add_residual_targets(
    frame: pd.DataFrame,
    *,
    large_loss_threshold: float,
    low_direction_risk_threshold: float,
    low_replacement_quality_threshold: float,
    min_oracle_edge: float,
    low_exit_capture_threshold: float,
    large_exit_regret_threshold: float,
    hold_too_long_minutes: float,
) -> pd.DataFrame:
    output = frame.copy()
    pnl = numeric_series(output, "adjusted_pnl")
    actual_edge = numeric_series(output, "actual_taken_best_adjusted_pnl", default=np.nan)
    output["residual_loss_target"] = pnl < 0.0
    output["large_loss_target"] = pnl <= large_loss_threshold
    output["direction_side_inversion_target"] = bool_series(output, "direction_error")
    output["low_capture_with_oracle_edge_target"] = (
        actual_edge.ge(min_oracle_edge)
        & numeric_series(output, "exit_capture_ratio").le(low_exit_capture_threshold)
    )
    output["exit_capture_failure_target"] = (
        numeric_series(output, "exit_regret").ge(large_exit_regret_threshold)
        | output["low_capture_with_oracle_edge_target"]
    )
    output["forced_exit_loss_target"] = bool_series(output, "is_forced_exit") & pnl.lt(0.0)
    output["profit_barrier_miss_loss_target"] = (
        numeric_series(output, "actual_taken_profit_barrier_hit", default=0.0).lt(0.5)
        & pnl.lt(0.0)
    )
    output["ev_overestimate_loss_target"] = (
        numeric_series(output, "ev_overestimate_vs_realized", default=0.0).gt(0.0)
        & pnl.lt(0.0)
    )
    output["hold_too_long_loss_target"] = (
        numeric_series(output, "oracle_holding_gap_minutes", default=0.0).le(
            -abs(hold_too_long_minutes)
        )
        & numeric_series(output, "exit_regret", default=0.0).gt(0.0)
        & pnl.lt(0.0)
    )
    output["low_direction_risk_large_loss_target"] = (
        numeric_series(output, "selected_direction_inversion_risk", default=1.0).le(
            low_direction_risk_threshold
        )
        & output["large_loss_target"]
    )
    output["low_replacement_quality_loss_target"] = (
        numeric_series(output, "selected_replacement_quality", default=1.0).le(
            low_replacement_quality_threshold
        )
        & pnl.lt(0.0)
    )
    output["residual_failure_combo"] = output[TARGET_FLAGS].apply(
        lambda row: "+".join([flag for flag, value in row.items() if bool(value)]) or "none",
        axis=1,
    )
    return output


def weighted_mean(values: pd.Series, weights: pd.Series) -> float:
    valid = values.notna() & np.isfinite(values.astype(float)) & weights.astype(float).gt(0.0)
    if not bool(valid.any()):
        return float("nan")
    return float(np.average(values.astype(float)[valid], weights=weights.astype(float)[valid]))


def summarize_slice(frame: pd.DataFrame) -> dict[str, Any]:
    if frame.empty:
        return {"trade_count": 0, "total_pnl": 0.0, "loss_pnl": 0.0, "max_drawdown": 0.0}
    ordered = frame.sort_values("entry_decision_timestamp")
    pnl = numeric_series(ordered, "adjusted_pnl")
    loss = pnl.lt(0.0)
    direction = ordered["direction"].astype(str).str.lower()
    cumulative = pnl.cumsum()
    max_drawdown = float((cumulative.cummax() - cumulative).max()) if len(cumulative) else 0.0
    return {
        "trade_count": int(len(ordered)),
        "total_pnl": float(pnl.sum()),
        "loss_pnl": float(pnl.where(loss, 0.0).sum()),
        "win_pnl": float(pnl.where(pnl.gt(0.0), 0.0).sum()),
        "avg_pnl": float(pnl.mean()),
        "win_rate": float(pnl.gt(0.0).mean()),
        "max_drawdown": max_drawdown,
        "long_count": int(direction.eq("long").sum()),
        "short_count": int(direction.eq("short").sum()),
        "forced_exit_share": float(bool_series(ordered, "is_forced_exit").mean()),
        "direction_error_rate": float(bool_series(ordered, "direction_error").mean()),
        "exit_capture_failure_rate": float(
            bool_series(ordered, "exit_capture_failure_target").mean()
        ),
        "low_capture_rate": float(
            bool_series(ordered, "low_capture_with_oracle_edge_target").mean()
        ),
        "profit_barrier_miss_rate": float(
            numeric_series(ordered, "actual_taken_profit_barrier_hit", default=0.0).lt(0.5).mean()
        ),
        "exit_regret_sum": float(numeric_series(ordered, "exit_regret").sum()),
        "exit_regret_mean": float(numeric_series(ordered, "exit_regret").mean()),
        "best_side_regret_sum": float(numeric_series(ordered, "best_side_regret").sum()),
        "ev_overestimate_realized_mean": float(
            numeric_series(ordered, "ev_overestimate_vs_realized").mean()
        ),
        "direction_risk_mean": float(
            numeric_series(ordered, "selected_direction_inversion_risk", default=np.nan)
            .dropna()
            .mean()
        )
        if numeric_series(ordered, "selected_direction_inversion_risk", default=np.nan)
        .notna()
        .any()
        else float("nan"),
        "replacement_quality_mean": float(
            numeric_series(ordered, "selected_replacement_quality", default=np.nan)
            .dropna()
            .mean()
        )
        if numeric_series(ordered, "selected_replacement_quality", default=np.nan).notna().any()
        else float("nan"),
        "exit_capture_ratio_mean": float(
            numeric_series(ordered, "exit_capture_ratio", default=np.nan).dropna().mean()
        )
        if numeric_series(ordered, "exit_capture_ratio", default=np.nan).notna().any()
        else float("nan"),
        "pred_hold_mean": float(
            numeric_series(ordered, "selected_pred_mlp_exit_minutes", default=np.nan)
            .dropna()
            .mean()
        )
        if numeric_series(ordered, "selected_pred_mlp_exit_minutes", default=np.nan).notna().any()
        else float("nan"),
        "actual_hold_mean": float(numeric_series(ordered, "holding_minutes").mean()),
    }


def summarize_by(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for keys, group in frame.groupby(columns, dropna=False):
        if not isinstance(keys, tuple):
            keys = (keys,)
        row = dict(zip(columns, keys, strict=True))
        row.update(summarize_slice(group))
        rows.append(row)
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(
        [*columns, "total_pnl"],
        ascending=[True] * len(columns) + [True],
    ).reset_index(drop=True)


def flag_summary(frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for (run_name, candidate), group in frame.groupby(["run_name", "candidate"], dropna=False):
        pnl = numeric_series(group, "adjusted_pnl")
        for flag in TARGET_FLAGS:
            mask = bool_series(group, flag)
            selected = group[mask]
            rows.append(
                {
                    "run_name": run_name,
                    "candidate": candidate,
                    "flag": flag,
                    "flag_count": int(mask.sum()),
                    "flag_share": float(mask.mean()) if len(mask) else 0.0,
                    "flag_total_pnl": float(pnl.where(mask, 0.0).sum()),
                    "flag_loss_pnl": float(pnl.where(mask & pnl.lt(0.0), 0.0).sum()),
                    "nonflag_total_pnl": float(pnl.where(~mask, 0.0).sum()),
                    "nonflag_loss_pnl": float(pnl.where((~mask) & pnl.lt(0.0), 0.0).sum()),
                    "large_loss_count": int(bool_series(group, "large_loss_target")[mask].sum())
                    if len(selected)
                    else 0,
                    "direction_error_rate": float(bool_series(selected, "direction_error").mean())
                    if len(selected)
                    else float("nan"),
                    "exit_capture_failure_rate": float(
                        bool_series(selected, "exit_capture_failure_target").mean()
                    )
                    if len(selected)
                    else float("nan"),
                }
            )
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(
        ["candidate", "flag_loss_pnl", "flag_count"],
        ascending=[True, True, False],
    ).reset_index(drop=True)


def overlap_summary(frame: pd.DataFrame) -> pd.DataFrame:
    return summarize_by(frame, ["run_name", "candidate", "residual_failure_combo"]).sort_values(
        ["candidate", "total_pnl", "trade_count"],
        ascending=[True, True, False],
    ).reset_index(drop=True)


def worst_trades(frame: pd.DataFrame, *, top_n: int) -> pd.DataFrame:
    columns = [
        "run_name",
        "candidate",
        "month",
        "direction",
        "entry_decision_timestamp",
        "adjusted_pnl",
        "exit_reason",
        "holding_minutes",
        "combined_regime",
        "session_regime",
        "actual_taken_best_adjusted_pnl",
        "actual_opposite_best_adjusted_pnl",
        "actual_best_side",
        "direction_error",
        "exit_regret",
        "exit_capture_ratio",
        "actual_taken_profit_barrier_hit",
        "pred_taken_ev",
        "ev_overestimate_vs_realized",
        "selected_direction_inversion_risk",
        "selected_direction_inversion_source",
        "selected_replacement_quality",
        "selected_replacement_quality_source",
        "selected_pred_mlp_exit_minutes",
        "oracle_holding_gap_minutes",
        "residual_failure_combo",
    ]
    existing = [column for column in columns if column in frame.columns]
    return frame.sort_values("adjusted_pnl").loc[:, existing].head(top_n).reset_index(drop=True)


def build_diagnostics(args: argparse.Namespace) -> Path:
    policy_runs = parse_policy_runs(args.policy_run)
    predictions = pd.read_parquet(args.predictions)
    extra_columns = list(dict.fromkeys([*DEFAULT_EXTRA_COLUMNS, *parse_csv(args.extra_columns)]))
    frames: list[pd.DataFrame] = []
    for run_name, run_dir in policy_runs.items():
        trades = read_policy_run_trades(
            run_name=run_name,
            run_dir=run_dir,
            predictions=predictions,
            long_column=args.long_column,
            short_column=args.short_column,
            extra_prediction_columns=extra_columns,
        )
        frames.append(trades)
    combined = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    combined = add_selected_residual_features(combined)
    combined = add_residual_targets(
        combined,
        large_loss_threshold=args.large_loss_threshold,
        low_direction_risk_threshold=args.low_direction_risk_threshold,
        low_replacement_quality_threshold=args.low_replacement_quality_threshold,
        min_oracle_edge=args.min_oracle_edge,
        low_exit_capture_threshold=args.low_exit_capture_threshold,
        large_exit_regret_threshold=args.large_exit_regret_threshold,
        hold_too_long_minutes=args.hold_too_long_minutes,
    )

    candidate = summarize_by(combined, ["run_name", "candidate"])
    month = summarize_by(combined, ["run_name", "candidate", "month"])
    context = summarize_by(
        combined,
        ["run_name", "candidate", "direction", "combined_regime", "session_regime"],
    )
    source = summarize_by(
        combined,
        [
            "run_name",
            "candidate",
            "selected_direction_inversion_source",
            "selected_replacement_quality_source",
        ],
    )
    flags = flag_summary(combined)
    overlap = overlap_summary(combined)
    worst = worst_trades(combined, top_n=args.top_n)

    run_dir = make_run_dir(args.output_dir, args.label)
    combined.to_csv(run_dir / "residual_enriched_trades.csv", index=False)
    candidate.to_csv(run_dir / "candidate_residual_summary.csv", index=False)
    month.to_csv(run_dir / "month_residual_summary.csv", index=False)
    context.to_csv(run_dir / "context_residual_summary.csv", index=False)
    source.to_csv(run_dir / "source_residual_summary.csv", index=False)
    flags.to_csv(run_dir / "flag_residual_summary.csv", index=False)
    overlap.to_csv(run_dir / "overlap_residual_summary.csv", index=False)
    worst.to_csv(run_dir / "worst_residual_trades.csv", index=False)
    config = {
        "policy_runs": policy_runs,
        "predictions": args.predictions,
        "long_column": args.long_column,
        "short_column": args.short_column,
        "extra_columns": extra_columns,
        "large_loss_threshold": args.large_loss_threshold,
        "low_direction_risk_threshold": args.low_direction_risk_threshold,
        "low_replacement_quality_threshold": args.low_replacement_quality_threshold,
        "min_oracle_edge": args.min_oracle_edge,
        "low_exit_capture_threshold": args.low_exit_capture_threshold,
        "large_exit_regret_threshold": args.large_exit_regret_threshold,
        "hold_too_long_minutes": args.hold_too_long_minutes,
    }
    (run_dir / "config.json").write_text(
        json.dumps(config, indent=2, default=local_json_default),
        encoding="utf-8",
    )

    print("Candidate residual summary:")
    print(candidate.to_string(index=False))
    print("\nWorst contexts:")
    print(
        context[
            [
                "run_name",
                "candidate",
                "direction",
                "combined_regime",
                "session_regime",
                "trade_count",
                "total_pnl",
                "loss_pnl",
                "direction_error_rate",
                "exit_capture_failure_rate",
                "direction_risk_mean",
                "replacement_quality_mean",
            ]
        ]
        .sort_values(["total_pnl", "trade_count"], ascending=[True, False])
        .head(args.top_n)
        .to_string(index=False)
    )
    print("\nFlag summary:")
    print(flags.sort_values(["flag_loss_pnl", "flag_count"], ascending=[True, False]).head(args.top_n).to_string(index=False))
    print(f"artifacts: {run_dir}")
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy-run", action="append", required=True)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument(
        "--long-column",
        default="pred_direction_inversion_bucket_s0p1_long_best_adjusted_pnl",
    )
    parser.add_argument(
        "--short-column",
        default="pred_direction_inversion_bucket_s0p1_short_best_adjusted_pnl",
    )
    parser.add_argument("--extra-columns", default="")
    parser.add_argument("--large-loss-threshold", type=float, default=-20.0)
    parser.add_argument("--low-direction-risk-threshold", type=float, default=0.45)
    parser.add_argument("--low-replacement-quality-threshold", type=float, default=0.40)
    parser.add_argument("--min-oracle-edge", type=float, default=5.0)
    parser.add_argument("--low-exit-capture-threshold", type=float, default=0.25)
    parser.add_argument("--large-exit-regret-threshold", type=float, default=20.0)
    parser.add_argument("--hold-too-long-minutes", type=float, default=30.0)
    parser.add_argument("--top-n", type=int, default=20)
    parser.add_argument("--output-dir", type=Path, default=Path("data/reports/backtests"))
    parser.add_argument("--label", default="entry_ev_direction_residual_loss_diagnostics")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    build_diagnostics(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
