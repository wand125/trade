from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from trade_data.backtest import (
    FIXED_HORIZON_SCORE_MODES,
    enrich_trades_with_predictions,
    prepare_analysis_predictions,
    read_trades_csv,
)
from trade_data.modeling import GENERALIZATION_FEATURE_COLUMNS, parse_bool, selection_metrics


SIDE_COLUMNS = {
    "long": {
        "target": "long_best_adjusted_pnl",
        "opposite_target": "short_best_adjusted_pnl",
        "ev": "pred_long_best_adjusted_pnl",
        "opposite_ev": "pred_short_best_adjusted_pnl",
        "calibrated_ev": "pred_calibrated_long_best_adjusted_pnl",
        "opposite_calibrated_ev": "pred_calibrated_short_best_adjusted_pnl",
        "risk": "pred_long_max_adverse_pnl",
        "holding": "pred_long_best_holding_minutes",
        "wait_regret": "pred_long_wait_regret",
        "entry_rank": "pred_long_entry_local_rank",
        "entry_urgency": "pred_long_entry_urgency",
        "profit_barrier_hit": "pred_long_profit_barrier_hit",
        "wait_regret_quantile": "pred_long_wait_regret_quantile",
        "entry_rank_bin": "pred_long_entry_local_rank_bin",
    },
    "short": {
        "target": "short_best_adjusted_pnl",
        "opposite_target": "long_best_adjusted_pnl",
        "ev": "pred_short_best_adjusted_pnl",
        "opposite_ev": "pred_long_best_adjusted_pnl",
        "calibrated_ev": "pred_calibrated_short_best_adjusted_pnl",
        "opposite_calibrated_ev": "pred_calibrated_long_best_adjusted_pnl",
        "risk": "pred_short_max_adverse_pnl",
        "holding": "pred_short_best_holding_minutes",
        "wait_regret": "pred_short_wait_regret",
        "entry_rank": "pred_short_entry_local_rank",
        "entry_urgency": "pred_short_entry_urgency",
        "profit_barrier_hit": "pred_short_profit_barrier_hit",
        "wait_regret_quantile": "pred_short_wait_regret_quantile",
        "entry_rank_bin": "pred_short_entry_local_rank_bin",
    },
}

BASE_FEATURE_COLUMNS = [
    "side",
    "pred_side_ev",
    "pred_opposite_ev",
    "pred_side_calibrated_ev",
    "pred_opposite_calibrated_ev",
    "pred_side_gap",
    "pred_side_risk",
    "pred_side_holding",
    "pred_side_wait_regret",
    "pred_side_entry_rank",
    "pred_side_entry_urgency",
    "pred_side_profit_barrier_hit",
    "pred_side_wait_regret_quantile",
    "pred_side_entry_rank_bin",
    "pred_best_adjusted_pnl_quantile",
    "pred_side_score_quantile",
    "pred_label",
]

MONTH_PATTERN = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


@dataclass(frozen=True)
class MetaModelConfig:
    max_iter: int
    learning_rate: float
    max_leaf_nodes: int
    max_depth: int | None
    min_samples_leaf: int
    l2_regularization: float
    max_features: float
    early_stopping: bool
    validation_fraction: float
    n_iter_no_change: int
    tol: float
    random_seed: int
    target_clip_quantile: float
    entry_threshold: float
    sample_weighting: str
    prediction_shrinkage: float


@dataclass(frozen=True)
class GroupEVCalibrationConfig:
    group_columns: tuple[str, ...]
    min_group_size: int
    prior_strength: float
    prediction_shrinkage: float
    lower_z: float = 0.0


@dataclass(frozen=True)
class GroupEVStats:
    n: int
    pred_mean: float
    target_mean: float
    target_std: float = 0.0
    target_standard_error: float = 0.0


@dataclass(frozen=True)
class GroupEVCalibrator:
    config: GroupEVCalibrationConfig
    side_stats: dict[str, GroupEVStats]
    group_stats: dict[str, dict[tuple[str, ...], GroupEVStats]]


@dataclass(frozen=True)
class GroupTargetSpec:
    name: str
    target_column: str
    prediction_column: str
    output_column: str


@dataclass(frozen=True)
class GroupTargetCalibrator:
    config: GroupEVCalibrationConfig
    specs: tuple[GroupTargetSpec, ...]
    target_stats: dict[str, GroupEVStats]
    group_stats: dict[str, dict[tuple[str, ...], GroupEVStats]]


@dataclass(frozen=True)
class TradeQualityCalibrator:
    config: GroupEVCalibrationConfig
    overall_stats: GroupEVStats
    side_stats: dict[str, GroupEVStats]
    group_stats: dict[str, dict[tuple[str, ...], GroupEVStats]]


@dataclass(frozen=True)
class TradeQualityModelConfig:
    max_iter: int
    learning_rate: float
    max_leaf_nodes: int
    max_depth: int | None
    min_samples_leaf: int
    l2_regularization: float
    max_features: float
    early_stopping: bool
    validation_fraction: float
    n_iter_no_change: int
    tol: float
    random_seed: int
    target_clip_quantile: float
    sample_weighting: str
    prediction_shrinkage: float


@dataclass
class TradeQualityModelBundle:
    config: TradeQualityModelConfig
    model: HistGradientBoostingRegressor
    feature_columns: list[str]
    category_mappings: dict[str, dict[str, int]]
    target_mean: float


FIXED_HORIZON_MINUTES = (60, 240, 720)
TRADE_SOURCE_LONG_EV_COLUMN = "pred_trade_source_long_ev"
TRADE_SOURCE_SHORT_EV_COLUMN = "pred_trade_source_short_ev"
TRADE_QUALITY_LONG_COLUMN = "pred_trade_quality_long_adjusted_pnl"
TRADE_QUALITY_SHORT_COLUMN = "pred_trade_quality_short_adjusted_pnl"
TRADE_QUALITY_TAKEN_COLUMN = "pred_trade_quality_taken_adjusted_pnl"
TRADE_QUALITY_NUMERIC_FEATURE_COLUMNS = [
    "side",
    "pred_taken_ev",
    "pred_opposite_ev",
    "pred_best_ev",
    "pred_side_gap",
    "pred_abs_side_gap",
    "pred_taken_best_holding_minutes",
    "pred_taken_max_adverse_pnl",
    "pred_taken_wait_regret",
    "pred_taken_entry_local_rank",
    "pred_taken_profit_barrier_hit",
    "trend_score_240",
    "volatility_score_60",
    "decision_hour_sin",
    "decision_hour_cos",
]
TRADE_QUALITY_CATEGORY_FEATURE_COLUMNS = [
    "trend_regime",
    "volatility_regime",
    "session_regime",
    "gap_regime",
    "combined_regime",
]


def fixed_horizon_target_specs(
    minutes: tuple[int, ...] = FIXED_HORIZON_MINUTES,
) -> tuple[GroupTargetSpec, ...]:
    specs: list[GroupTargetSpec] = []
    for side_name in ("long", "short"):
        for horizon_minutes in minutes:
            name = f"{side_name}_fixed_{horizon_minutes}m_adjusted_pnl"
            specs.append(
                GroupTargetSpec(
                    name=name,
                    target_column=name,
                    prediction_column=f"pred_{name}",
                    output_column=f"pred_regime_calibrated_{name}",
                )
            )
    return tuple(specs)


def make_run_dir(root: Path, label: str) -> Path:
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    for index in range(100):
        suffix = "" if index == 0 else f"_{index}"
        path = root / f"{timestamp}_{label}{suffix}"
        try:
            path.mkdir(parents=True, exist_ok=False)
            return path
        except FileExistsError:
            continue
    raise FileExistsError(f"could not create unique run directory for {label}")


def optional_column(df: pd.DataFrame, primary: str, fallback: str) -> pd.Series:
    if primary in df.columns:
        return df[primary]
    return df[fallback]


def available_feature_columns(df: pd.DataFrame) -> list[str]:
    return [
        *BASE_FEATURE_COLUMNS,
        *[column for column in GENERALIZATION_FEATURE_COLUMNS if column in df.columns],
    ]


def parse_csv_months(value: str | None) -> list[str] | None:
    if value is None:
        return None
    months = [part.strip() for part in value.split(",") if part.strip()]
    if not months:
        raise argparse.ArgumentTypeError("at least one month is required")
    for month in months:
        if not MONTH_PATTERN.match(month):
            raise argparse.ArgumentTypeError("months must be in YYYY-MM format")
    return months


def parse_csv_strings(value: str | None) -> list[str]:
    if value is None:
        return []
    return [part.strip() for part in value.split(",") if part.strip()]


def parse_csv_ints(value: str | None) -> list[int]:
    if value is None:
        return []
    output: list[int] = []
    for part in value.split(","):
        stripped = part.strip()
        if not stripped:
            continue
        try:
            output.append(int(stripped))
        except ValueError as exc:
            raise argparse.ArgumentTypeError("CSV values must be integers") from exc
    return output


def parse_csv_paths(value: str | None) -> list[Path]:
    if value is None:
        return []
    paths = [Path(part.strip()) for part in value.split(",") if part.strip()]
    if not paths:
        raise argparse.ArgumentTypeError("at least one path is required")
    return paths


def fixed_horizon_score_series(frame: pd.DataFrame, columns: tuple[str, ...], score_mode: str) -> pd.Series:
    if score_mode not in FIXED_HORIZON_SCORE_MODES:
        raise ValueError(f"unknown fixed horizon score mode: {score_mode}")
    missing = sorted(set(columns) - set(frame.columns))
    if missing:
        raise ValueError(f"predictions missing fixed horizon columns: {', '.join(missing)}")
    values = frame.loc[:, list(columns)].astype(float)
    if score_mode == "max":
        score = values.max(axis=1)
    elif score_mode == "mean":
        score = values.mean(axis=1)
    elif score_mode == "median":
        score = values.median(axis=1)
    elif score_mode == "min":
        score = values.min(axis=1)
    else:
        raise ValueError(f"unknown fixed horizon score mode: {score_mode}")
    return pd.Series(score.to_numpy(), index=frame.index)


def add_trade_source_ev_columns(
    predictions: pd.DataFrame,
    *,
    source_mode: str,
    long_column: str,
    short_column: str,
    long_fixed_horizon_columns: tuple[str, ...],
    short_fixed_horizon_columns: tuple[str, ...],
    fixed_horizon_score_mode: str,
) -> pd.DataFrame:
    output = predictions.copy()
    if source_mode == "columns":
        missing = sorted({long_column, short_column} - set(output.columns))
        if missing:
            raise ValueError(f"predictions missing trade source columns: {', '.join(missing)}")
        output[TRADE_SOURCE_LONG_EV_COLUMN] = output[long_column].astype(float)
        output[TRADE_SOURCE_SHORT_EV_COLUMN] = output[short_column].astype(float)
    elif source_mode == "fixed_horizon":
        output[TRADE_SOURCE_LONG_EV_COLUMN] = fixed_horizon_score_series(
            output,
            long_fixed_horizon_columns,
            fixed_horizon_score_mode,
        )
        output[TRADE_SOURCE_SHORT_EV_COLUMN] = fixed_horizon_score_series(
            output,
            short_fixed_horizon_columns,
            fixed_horizon_score_mode,
        )
    else:
        raise ValueError("trade source mode must be columns or fixed_horizon")
    return output


def read_trade_frames(paths: list[Path]) -> pd.DataFrame:
    if not paths:
        raise ValueError("at least one trade CSV is required")
    frames = [read_trades_csv(path) for path in paths]
    return pd.concat(frames, ignore_index=True)


def filter_months(df: pd.DataFrame, months: list[str] | None, label: str) -> pd.DataFrame:
    if months is None:
        return df
    if "dataset_month" not in df.columns:
        raise ValueError(f"{label} predictions do not include dataset_month")
    filtered = df[df["dataset_month"].isin(months)].copy()
    missing = sorted(set(months) - set(filtered["dataset_month"].dropna().unique()))
    if missing:
        raise ValueError(f"{label} predictions missing months: {', '.join(missing)}")
    if filtered.empty:
        raise ValueError(f"{label} predictions are empty after month filtering")
    return filtered


def month_counts(df: pd.DataFrame) -> dict[str, int]:
    if "dataset_month" not in df.columns:
        return {}
    counts = df["dataset_month"].value_counts().sort_index()
    return {str(month): int(count) for month, count in counts.items()}


def group_key_series(df: pd.DataFrame, group_columns: tuple[str, ...]) -> pd.Series:
    if not group_columns:
        return pd.Series([tuple()] * len(df), index=df.index, dtype="object")
    return df.loc[:, list(group_columns)].astype("string").fillna("__missing__").apply(tuple, axis=1)


def target_std(values: pd.Series) -> float:
    numeric = values.astype(float).replace([np.inf, -np.inf], np.nan).dropna()
    if len(numeric) < 2:
        return 0.0
    return float(numeric.std(ddof=0))


def target_standard_error(values: pd.Series) -> float:
    numeric = values.astype(float).replace([np.inf, -np.inf], np.nan).dropna()
    if len(numeric) < 2:
        return 0.0
    return float(numeric.std(ddof=0) / (len(numeric) ** 0.5))


def support_aware_lower_margin(stats: pd.DataFrame, config: GroupEVCalibrationConfig) -> pd.Series:
    if config.lower_z <= 0:
        return pd.Series(0.0, index=stats.index, dtype="float64")
    if config.prior_strength > 0:
        support = pd.to_numeric(stats["support"], errors="coerce").fillna(0.0).clip(lower=0.0)
        support_factor = (config.prior_strength / (support + config.prior_strength)).pow(0.5)
        return config.lower_z * pd.to_numeric(stats["target_std"], errors="coerce").fillna(0.0) * support_factor
    return config.lower_z * pd.to_numeric(stats["target_standard_error"], errors="coerce").fillna(0.0)


def fit_group_ev_calibrator(
    predictions: pd.DataFrame,
    config: GroupEVCalibrationConfig,
) -> GroupEVCalibrator:
    if config.min_group_size <= 0:
        raise ValueError("min_group_size must be positive")
    if config.prior_strength < 0:
        raise ValueError("prior_strength must be non-negative")
    if not 0.0 <= config.prediction_shrinkage <= 1.0:
        raise ValueError("prediction_shrinkage must be in [0, 1]")
    if config.lower_z < 0:
        raise ValueError("lower_z must be non-negative")
    missing_group_columns = sorted(set(config.group_columns) - set(predictions.columns))
    if missing_group_columns:
        raise ValueError(f"predictions missing group columns: {', '.join(missing_group_columns)}")

    side_stats: dict[str, GroupEVStats] = {}
    group_stats: dict[str, dict[tuple[str, ...], GroupEVStats]] = {}
    keys = group_key_series(predictions, config.group_columns)
    for side_name, spec in SIDE_COLUMNS.items():
        frame = pd.DataFrame(
            {
                "target": predictions[spec["target"]].astype(float),
                "pred": predictions[spec["ev"]].astype(float),
                "key": keys,
            }
        ).replace([np.inf, -np.inf], np.nan).dropna(subset=["target", "pred"])
        if frame.empty:
            raise ValueError(f"no valid rows for {side_name} calibration")
        side_stat = GroupEVStats(
            n=int(len(frame)),
            pred_mean=float(frame["pred"].mean()),
            target_mean=float(frame["target"].mean()),
            target_std=target_std(frame["target"]),
            target_standard_error=target_standard_error(frame["target"]),
        )
        side_stats[side_name] = side_stat
        group_stats[side_name] = {}
        for key, group in frame.groupby("key", sort=False):
            group_count = int(len(group))
            if group_count < config.min_group_size:
                continue
            if config.prior_strength == 0:
                weight = 1.0
            else:
                weight = group_count / (group_count + config.prior_strength)
            group_stats[side_name][key] = GroupEVStats(
                n=group_count,
                pred_mean=float(weight * group["pred"].mean() + (1.0 - weight) * side_stat.pred_mean),
                target_mean=float(
                    weight * group["target"].mean() + (1.0 - weight) * side_stat.target_mean
                ),
                target_std=target_std(group["target"]),
                target_standard_error=target_standard_error(group["target"]),
            )
    return GroupEVCalibrator(config=config, side_stats=side_stats, group_stats=group_stats)


def group_ev_stats_frame(
    predictions: pd.DataFrame,
    side_name: str,
    calibrator: GroupEVCalibrator,
    index: pd.Index | None = None,
) -> pd.DataFrame:
    index = predictions.index if index is None else index
    side_stat = calibrator.side_stats[side_name]
    stats = pd.DataFrame(
        {
            "pred_mean": side_stat.pred_mean,
            "target_mean": side_stat.target_mean,
            "support": side_stat.n,
            "target_std": side_stat.target_std,
            "target_standard_error": side_stat.target_standard_error,
            "source": "side",
        },
        index=index,
    ).reset_index(drop=True)
    if calibrator.config.group_columns:
        keys = group_key_series(predictions, calibrator.config.group_columns).reset_index(drop=True)
        for key, group_stat in calibrator.group_stats[side_name].items():
            mask = keys == key
            if mask.any():
                stats.loc[mask, "pred_mean"] = group_stat.pred_mean
                stats.loc[mask, "target_mean"] = group_stat.target_mean
                stats.loc[mask, "support"] = group_stat.n
                stats.loc[mask, "target_std"] = group_stat.target_std
                stats.loc[mask, "target_standard_error"] = group_stat.target_standard_error
                stats.loc[mask, "source"] = "group"
    return stats


def calibrated_group_ev_values(
    predictions: pd.DataFrame,
    side_name: str,
    calibrator: GroupEVCalibrator,
) -> pd.Series:
    spec = SIDE_COLUMNS[side_name]
    raw = predictions[spec["ev"]].astype(float).reset_index(drop=True)
    stats = group_ev_stats_frame(predictions, side_name, calibrator)
    values = stats["target_mean"] + calibrator.config.prediction_shrinkage * (raw - stats["pred_mean"])
    return pd.Series(values.to_numpy(), index=predictions.index)


def add_group_calibrated_ev_columns(
    predictions: pd.DataFrame,
    calibrator: GroupEVCalibrator,
) -> pd.DataFrame:
    output = predictions.copy()
    for side_name in ("long", "short"):
        spec = SIDE_COLUMNS[side_name]
        output_column = f"pred_regime_calibrated_{side_name}_best_adjusted_pnl"
        raw = predictions[spec["ev"]].astype(float).reset_index(drop=True)
        stats = group_ev_stats_frame(predictions, side_name, calibrator)
        calibrated = (
            stats["target_mean"] + calibrator.config.prediction_shrinkage * (raw - stats["pred_mean"])
        )
        lower_margin = support_aware_lower_margin(stats, calibrator.config)
        output[output_column] = pd.Series(calibrated.to_numpy(), index=predictions.index)
        output[f"{output_column}_lower"] = pd.Series(
            (calibrated - lower_margin).to_numpy(),
            index=predictions.index,
        )
        output[f"{output_column}_support"] = pd.Series(
            stats["support"].to_numpy(),
            index=predictions.index,
        )
        output[f"{output_column}_lower_margin"] = pd.Series(
            lower_margin.to_numpy(),
            index=predictions.index,
        )
        output[f"{output_column}_source"] = pd.Series(
            stats["source"].to_numpy(),
            index=predictions.index,
        )
    return output


def fit_group_target_calibrator(
    predictions: pd.DataFrame,
    config: GroupEVCalibrationConfig,
    specs: tuple[GroupTargetSpec, ...],
) -> GroupTargetCalibrator:
    if not specs:
        raise ValueError("at least one target spec is required")
    if config.min_group_size <= 0:
        raise ValueError("min_group_size must be positive")
    if config.prior_strength < 0:
        raise ValueError("prior_strength must be non-negative")
    if not 0.0 <= config.prediction_shrinkage <= 1.0:
        raise ValueError("prediction_shrinkage must be in [0, 1]")
    if config.lower_z < 0:
        raise ValueError("lower_z must be non-negative")

    required_columns = set(config.group_columns)
    for spec in specs:
        required_columns.add(spec.target_column)
        required_columns.add(spec.prediction_column)
    missing_columns = sorted(required_columns - set(predictions.columns))
    if missing_columns:
        raise ValueError(f"predictions missing calibration columns: {', '.join(missing_columns)}")

    target_stats: dict[str, GroupEVStats] = {}
    group_stats: dict[str, dict[tuple[str, ...], GroupEVStats]] = {}
    keys = group_key_series(predictions, config.group_columns)
    for spec in specs:
        frame = pd.DataFrame(
            {
                "target": predictions[spec.target_column].astype(float),
                "pred": predictions[spec.prediction_column].astype(float),
                "key": keys,
            }
        ).replace([np.inf, -np.inf], np.nan).dropna(subset=["target", "pred"])
        if frame.empty:
            raise ValueError(f"no valid rows for {spec.name} calibration")
        global_stat = GroupEVStats(
            n=int(len(frame)),
            pred_mean=float(frame["pred"].mean()),
            target_mean=float(frame["target"].mean()),
            target_std=target_std(frame["target"]),
            target_standard_error=target_standard_error(frame["target"]),
        )
        target_stats[spec.name] = global_stat
        group_stats[spec.name] = {}
        for key, group in frame.groupby("key", sort=False):
            group_count = int(len(group))
            if group_count < config.min_group_size:
                continue
            if config.prior_strength == 0:
                weight = 1.0
            else:
                weight = group_count / (group_count + config.prior_strength)
            group_stats[spec.name][key] = GroupEVStats(
                n=group_count,
                pred_mean=float(weight * group["pred"].mean() + (1.0 - weight) * global_stat.pred_mean),
                target_mean=float(
                    weight * group["target"].mean() + (1.0 - weight) * global_stat.target_mean
                ),
                target_std=target_std(group["target"]),
                target_standard_error=target_standard_error(group["target"]),
            )
    return GroupTargetCalibrator(
        config=config,
        specs=specs,
        target_stats=target_stats,
        group_stats=group_stats,
    )


def group_target_stats_frame(
    predictions: pd.DataFrame,
    spec: GroupTargetSpec,
    calibrator: GroupTargetCalibrator,
) -> pd.DataFrame:
    global_stat = calibrator.target_stats[spec.name]
    stats = pd.DataFrame(
        {
            "pred_mean": global_stat.pred_mean,
            "target_mean": global_stat.target_mean,
            "support": global_stat.n,
            "target_std": global_stat.target_std,
            "target_standard_error": global_stat.target_standard_error,
            "source": "target",
        },
        index=predictions.index,
    ).reset_index(drop=True)
    if calibrator.config.group_columns:
        keys = group_key_series(predictions, calibrator.config.group_columns).reset_index(drop=True)
        for key, group_stat in calibrator.group_stats[spec.name].items():
            mask = keys == key
            if mask.any():
                stats.loc[mask, "pred_mean"] = group_stat.pred_mean
                stats.loc[mask, "target_mean"] = group_stat.target_mean
                stats.loc[mask, "support"] = group_stat.n
                stats.loc[mask, "target_std"] = group_stat.target_std
                stats.loc[mask, "target_standard_error"] = group_stat.target_standard_error
                stats.loc[mask, "source"] = "group"
    return stats


def calibrated_group_target_values(
    predictions: pd.DataFrame,
    spec: GroupTargetSpec,
    calibrator: GroupTargetCalibrator,
) -> pd.Series:
    raw = predictions[spec.prediction_column].astype(float).reset_index(drop=True)
    stats = group_target_stats_frame(predictions, spec, calibrator)
    values = stats["target_mean"] + calibrator.config.prediction_shrinkage * (raw - stats["pred_mean"])
    return pd.Series(values.to_numpy(), index=predictions.index)


def add_group_calibrated_target_columns(
    predictions: pd.DataFrame,
    calibrator: GroupTargetCalibrator,
) -> pd.DataFrame:
    output = predictions.copy()
    for spec in calibrator.specs:
        raw = predictions[spec.prediction_column].astype(float).reset_index(drop=True)
        stats = group_target_stats_frame(predictions, spec, calibrator)
        calibrated = (
            stats["target_mean"] + calibrator.config.prediction_shrinkage * (raw - stats["pred_mean"])
        )
        lower_margin = support_aware_lower_margin(stats, calibrator.config)
        output[spec.output_column] = pd.Series(calibrated.to_numpy(), index=predictions.index)
        output[f"{spec.output_column}_lower"] = pd.Series(
            (calibrated - lower_margin).to_numpy(),
            index=predictions.index,
        )
        output[f"{spec.output_column}_support"] = pd.Series(
            stats["support"].to_numpy(),
            index=predictions.index,
        )
        output[f"{spec.output_column}_lower_margin"] = pd.Series(
            lower_margin.to_numpy(),
            index=predictions.index,
        )
        output[f"{spec.output_column}_source"] = pd.Series(
            stats["source"].to_numpy(),
            index=predictions.index,
        )
    return output


def add_group_calibrated_fixed_horizon_columns(
    predictions: pd.DataFrame,
    calibrator: GroupTargetCalibrator,
) -> pd.DataFrame:
    return add_group_calibrated_target_columns(predictions, calibrator)


def fit_trade_quality_calibrator(
    enriched_trades: pd.DataFrame,
    config: GroupEVCalibrationConfig,
) -> TradeQualityCalibrator:
    if config.min_group_size <= 0:
        raise ValueError("min_group_size must be positive")
    if config.prior_strength < 0:
        raise ValueError("prior_strength must be non-negative")
    if not 0.0 <= config.prediction_shrinkage <= 1.0:
        raise ValueError("prediction_shrinkage must be in [0, 1]")
    if config.lower_z < 0:
        raise ValueError("lower_z must be non-negative")

    required_columns = {
        "direction",
        "adjusted_pnl",
        "pred_taken_ev",
        *config.group_columns,
    }
    missing_columns = sorted(required_columns - set(enriched_trades.columns))
    if missing_columns:
        raise ValueError(f"enriched trades missing calibration columns: {', '.join(missing_columns)}")

    working = enriched_trades.copy()
    working["side_name"] = working["direction"].astype(str).str.lower()
    working["target"] = working["adjusted_pnl"].astype(float)
    working["pred"] = working["pred_taken_ev"].astype(float)
    working = working.replace([np.inf, -np.inf], np.nan).dropna(subset=["target", "pred"])
    if working.empty:
        raise ValueError("no valid selected trades for trade quality calibration")

    overall_stats = GroupEVStats(
        n=int(len(working)),
        pred_mean=float(working["pred"].mean()),
        target_mean=float(working["target"].mean()),
        target_std=target_std(working["target"]),
        target_standard_error=target_standard_error(working["target"]),
    )
    keys = group_key_series(working, config.group_columns)
    side_stats: dict[str, GroupEVStats] = {}
    group_stats: dict[str, dict[tuple[str, ...], GroupEVStats]] = {}
    for side_name in ("long", "short"):
        side_frame = working[working["side_name"] == side_name]
        group_stats[side_name] = {}
        if side_frame.empty:
            continue
        side_stats[side_name] = GroupEVStats(
            n=int(len(side_frame)),
            pred_mean=float(side_frame["pred"].mean()),
            target_mean=float(side_frame["target"].mean()),
            target_std=target_std(side_frame["target"]),
            target_standard_error=target_standard_error(side_frame["target"]),
        )
        side_keys = keys.loc[side_frame.index]
        side_working = side_frame.assign(_key=side_keys)
        for key, group in side_working.groupby("_key", sort=False):
            group_count = int(len(group))
            if group_count < config.min_group_size:
                continue
            if config.prior_strength == 0:
                weight = 1.0
            else:
                weight = group_count / (group_count + config.prior_strength)
            side_stat = side_stats[side_name]
            group_stats[side_name][key] = GroupEVStats(
                n=group_count,
                pred_mean=float(weight * group["pred"].mean() + (1.0 - weight) * side_stat.pred_mean),
                target_mean=float(
                    weight * group["target"].mean() + (1.0 - weight) * side_stat.target_mean
                ),
                target_std=target_std(group["target"]),
                target_standard_error=target_standard_error(group["target"]),
            )
    return TradeQualityCalibrator(
        config=config,
        overall_stats=overall_stats,
        side_stats=side_stats,
        group_stats=group_stats,
    )


def trade_quality_side_values(
    predictions: pd.DataFrame,
    side_name: str,
    raw_column: str,
    calibrator: TradeQualityCalibrator,
) -> pd.Series:
    raw = predictions[raw_column].astype(float).reset_index(drop=True)
    fallback_stat = calibrator.side_stats.get(side_name, calibrator.overall_stats)
    stats = pd.DataFrame(
        {
            "pred_mean": fallback_stat.pred_mean,
            "target_mean": fallback_stat.target_mean,
        },
        index=predictions.index,
    ).reset_index(drop=True)
    if calibrator.config.group_columns:
        keys = group_key_series(predictions, calibrator.config.group_columns).reset_index(drop=True)
        for key, group_stat in calibrator.group_stats.get(side_name, {}).items():
            mask = keys == key
            if mask.any():
                stats.loc[mask, "pred_mean"] = group_stat.pred_mean
                stats.loc[mask, "target_mean"] = group_stat.target_mean
    values = stats["target_mean"] + calibrator.config.prediction_shrinkage * (raw - stats["pred_mean"])
    return pd.Series(values.to_numpy(), index=predictions.index)


def add_trade_quality_columns(
    predictions: pd.DataFrame,
    calibrator: TradeQualityCalibrator,
) -> pd.DataFrame:
    missing = sorted(
        {TRADE_SOURCE_LONG_EV_COLUMN, TRADE_SOURCE_SHORT_EV_COLUMN} - set(predictions.columns)
    )
    if missing:
        raise ValueError(f"predictions missing trade source columns: {', '.join(missing)}")
    output = predictions.copy()
    output[TRADE_QUALITY_LONG_COLUMN] = trade_quality_side_values(
        output,
        "long",
        TRADE_SOURCE_LONG_EV_COLUMN,
        calibrator,
    )
    output[TRADE_QUALITY_SHORT_COLUMN] = trade_quality_side_values(
        output,
        "short",
        TRADE_SOURCE_SHORT_EV_COLUMN,
        calibrator,
    )
    return output


def add_trade_quality_values_to_enriched(
    enriched_trades: pd.DataFrame,
    calibrator: TradeQualityCalibrator,
) -> pd.DataFrame:
    output = enriched_trades.copy()
    calibrated = []
    keys = group_key_series(output, calibrator.config.group_columns)
    for index, row in output.iterrows():
        side_name = str(row["direction"]).lower()
        stat = calibrator.side_stats.get(side_name, calibrator.overall_stats)
        key = keys.loc[index]
        stat = calibrator.group_stats.get(side_name, {}).get(key, stat)
        raw = float(row["pred_taken_ev"])
        calibrated.append(stat.target_mean + calibrator.config.prediction_shrinkage * (raw - stat.pred_mean))
    output["pred_trade_quality_taken_adjusted_pnl"] = calibrated
    return output


def trade_quality_calibration_metrics(
    enriched_trades: pd.DataFrame,
    calibrator: TradeQualityCalibrator,
) -> dict[str, float]:
    if enriched_trades.empty:
        return trade_quality_scored_metrics(enriched_trades)
    scored = add_trade_quality_values_to_enriched(enriched_trades, calibrator)
    return trade_quality_scored_metrics(scored)


def trade_quality_scored_metrics(scored: pd.DataFrame) -> dict[str, float]:
    if scored.empty:
        return {
            "trade_count": 0,
            "raw_bias": 0.0,
            "calibrated_bias": 0.0,
            "bias_reduction": 0.0,
            "raw_overestimate_mean": 0.0,
            "calibrated_overestimate_mean": 0.0,
            "calibrated_mae": 0.0,
            "calibrated_rmse": 0.0,
            "calibrated_r2": 0.0,
        }
    target = scored["adjusted_pnl"].astype(float)
    raw_pred = scored["pred_taken_ev"].astype(float)
    calibrated_pred = scored["pred_trade_quality_taken_adjusted_pnl"].astype(float)
    raw_error = raw_pred - target
    calibrated_error = calibrated_pred - target
    if len(scored) >= 2:
        calibrated_r2 = float(r2_score(target, calibrated_pred))
    else:
        calibrated_r2 = 0.0
    return {
        "trade_count": int(len(scored)),
        "raw_bias": float(raw_error.mean()),
        "calibrated_bias": float(calibrated_error.mean()),
        "bias_reduction": float(abs(raw_error.mean()) - abs(calibrated_error.mean())),
        "raw_overestimate_mean": float(raw_error.clip(lower=0).mean()),
        "calibrated_overestimate_mean": float(calibrated_error.clip(lower=0).mean()),
        "calibrated_mae": float(mean_absolute_error(target, calibrated_pred)),
        "calibrated_rmse": float(mean_squared_error(target, calibrated_pred) ** 0.5),
        "calibrated_r2": calibrated_r2,
    }


def finite_float_series(frame: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype="float64")
    values = pd.to_numeric(frame[column], errors="coerce").replace([np.inf, -np.inf], np.nan)
    return values.fillna(default).astype(float)


def timestamp_hour_features(frame: pd.DataFrame, timestamp_column: str) -> tuple[pd.Series, pd.Series]:
    if timestamp_column not in frame.columns:
        zeros = pd.Series(0.0, index=frame.index)
        return zeros, zeros
    hours = pd.to_datetime(frame[timestamp_column], utc=True).dt.hour.astype(float)
    radians = 2.0 * np.pi * hours / 24.0
    return (
        pd.Series(np.sin(radians), index=frame.index),
        pd.Series(np.cos(radians), index=frame.index),
    )


def trade_quality_features_from_enriched(enriched: pd.DataFrame) -> pd.DataFrame:
    output = pd.DataFrame(index=enriched.index)
    output["side"] = finite_float_series(enriched, "direction_sign")
    output["pred_taken_ev"] = finite_float_series(enriched, "pred_taken_ev")
    output["pred_opposite_ev"] = finite_float_series(enriched, "pred_opposite_ev")
    output["pred_best_ev"] = finite_float_series(enriched, "pred_best_ev")
    output["pred_side_gap"] = output["pred_taken_ev"] - output["pred_opposite_ev"]
    output["pred_abs_side_gap"] = output["pred_side_gap"].abs()
    for column in [
        "pred_taken_best_holding_minutes",
        "pred_taken_max_adverse_pnl",
        "pred_taken_wait_regret",
        "pred_taken_entry_local_rank",
        "pred_taken_profit_barrier_hit",
        "trend_score_240",
        "volatility_score_60",
    ]:
        output[column] = finite_float_series(enriched, column)
    output["decision_hour_sin"], output["decision_hour_cos"] = timestamp_hour_features(
        enriched,
        "entry_decision_timestamp",
    )
    for column in TRADE_QUALITY_CATEGORY_FEATURE_COLUMNS:
        if column in enriched.columns:
            output[column] = enriched[column].astype("string").fillna("__missing__")
        else:
            output[column] = "__missing__"
    if "dataset_month" in enriched.columns:
        output["dataset_month"] = enriched["dataset_month"].astype(str)
    output["target"] = finite_float_series(enriched, "adjusted_pnl")
    return output


def side_prediction_series(
    predictions: pd.DataFrame,
    side_name: str,
    column_stem: str,
    default: float = 0.0,
) -> pd.Series:
    column = f"pred_{side_name}_{column_stem}"
    return finite_float_series(predictions, column, default)


def side_profit_barrier_series(predictions: pd.DataFrame, side_name: str) -> pd.Series:
    for column in [
        f"pred_{side_name}_profit_barrier_hit_prob",
        f"pred_{side_name}_profit_barrier_hit",
    ]:
        if column in predictions.columns:
            return finite_float_series(predictions, column)
    return pd.Series(0.0, index=predictions.index)


def trade_quality_features_from_predictions(
    predictions: pd.DataFrame,
    side_name: str,
) -> pd.DataFrame:
    side_value = 1.0 if side_name == "long" else -1.0
    side_ev_column = TRADE_SOURCE_LONG_EV_COLUMN if side_name == "long" else TRADE_SOURCE_SHORT_EV_COLUMN
    opposite_ev_column = TRADE_SOURCE_SHORT_EV_COLUMN if side_name == "long" else TRADE_SOURCE_LONG_EV_COLUMN
    output = pd.DataFrame(index=predictions.index)
    output["side"] = side_value
    output["pred_taken_ev"] = finite_float_series(predictions, side_ev_column)
    output["pred_opposite_ev"] = finite_float_series(predictions, opposite_ev_column)
    output["pred_best_ev"] = pd.concat(
        [
            finite_float_series(predictions, TRADE_SOURCE_LONG_EV_COLUMN),
            finite_float_series(predictions, TRADE_SOURCE_SHORT_EV_COLUMN),
        ],
        axis=1,
    ).max(axis=1)
    output["pred_side_gap"] = output["pred_taken_ev"] - output["pred_opposite_ev"]
    output["pred_abs_side_gap"] = output["pred_side_gap"].abs()
    output["pred_taken_best_holding_minutes"] = side_prediction_series(
        predictions,
        side_name,
        "best_holding_minutes",
    )
    output["pred_taken_max_adverse_pnl"] = side_prediction_series(
        predictions,
        side_name,
        "max_adverse_pnl",
    )
    output["pred_taken_wait_regret"] = side_prediction_series(predictions, side_name, "wait_regret")
    output["pred_taken_entry_local_rank"] = side_prediction_series(
        predictions,
        side_name,
        "entry_local_rank",
    )
    output["pred_taken_profit_barrier_hit"] = side_profit_barrier_series(predictions, side_name)
    output["trend_score_240"] = finite_float_series(predictions, "trend_score_240")
    output["volatility_score_60"] = finite_float_series(predictions, "volatility_score_60")
    output["decision_hour_sin"], output["decision_hour_cos"] = timestamp_hour_features(
        predictions,
        "decision_timestamp",
    )
    for column in TRADE_QUALITY_CATEGORY_FEATURE_COLUMNS:
        if column in predictions.columns:
            output[column] = predictions[column].astype("string").fillna("__missing__")
        else:
            output[column] = "__missing__"
    return output


def category_mappings(frame: pd.DataFrame, columns: list[str]) -> dict[str, dict[str, int]]:
    mappings: dict[str, dict[str, int]] = {}
    for column in columns:
        values = sorted(str(value) for value in frame[column].astype("string").fillna("__missing__").unique())
        mappings[column] = {value: index for index, value in enumerate(values)}
    return mappings


def encode_trade_quality_features(
    frame: pd.DataFrame,
    mappings: dict[str, dict[str, int]],
) -> pd.DataFrame:
    output = pd.DataFrame(index=frame.index)
    for column in TRADE_QUALITY_NUMERIC_FEATURE_COLUMNS:
        output[column] = finite_float_series(frame, column)
    for column in TRADE_QUALITY_CATEGORY_FEATURE_COLUMNS:
        mapping = mappings.get(column, {})
        output[f"{column}_code"] = (
            frame[column].astype("string").fillna("__missing__").map(mapping).fillna(-1).astype(float)
        )
    return output.replace([np.inf, -np.inf], np.nan).fillna(0.0)


def trade_quality_feature_columns(encoded: pd.DataFrame) -> list[str]:
    return [
        *TRADE_QUALITY_NUMERIC_FEATURE_COLUMNS,
        *[f"{column}_code" for column in TRADE_QUALITY_CATEGORY_FEATURE_COLUMNS],
    ]


def build_trade_quality_training_frame(enriched: pd.DataFrame) -> pd.DataFrame:
    frame = trade_quality_features_from_enriched(enriched)
    return frame.replace([np.inf, -np.inf], np.nan).dropna(subset=["target"])


def trade_quality_sample_weights(frame: pd.DataFrame, weighting: str) -> np.ndarray | None:
    if weighting == "none":
        return None
    weights = pd.Series(1.0, index=frame.index, dtype="float64")
    if weighting == "month":
        if "dataset_month" not in frame.columns:
            raise ValueError("month sample weighting requires dataset_month")
        weights *= 1.0 / frame.groupby("dataset_month")["target"].transform("size")
    elif weighting == "side":
        weights *= 1.0 / frame.groupby("side")["target"].transform("size")
    elif weighting == "month_side":
        if "dataset_month" not in frame.columns:
            raise ValueError("month_side sample weighting requires dataset_month")
        weights *= 1.0 / frame.groupby(["dataset_month", "side"])["target"].transform("size")
    else:
        raise ValueError(f"unknown sample weighting: {weighting}")
    weights = weights / weights.mean()
    return weights.to_numpy(dtype="float64")


def fit_trade_quality_model(
    enriched: pd.DataFrame,
    config: TradeQualityModelConfig,
) -> TradeQualityModelBundle:
    if not 0.0 <= config.prediction_shrinkage <= 1.0:
        raise ValueError("prediction_shrinkage must be in [0, 1]")
    frame = build_trade_quality_training_frame(enriched)
    if frame.empty:
        raise ValueError("trade quality model training frame is empty")
    mappings = category_mappings(frame, TRADE_QUALITY_CATEGORY_FEATURE_COLUMNS)
    encoded = encode_trade_quality_features(frame, mappings)
    feature_columns = trade_quality_feature_columns(encoded)
    model = HistGradientBoostingRegressor(
        max_iter=config.max_iter,
        learning_rate=config.learning_rate,
        max_leaf_nodes=config.max_leaf_nodes,
        max_depth=config.max_depth,
        min_samples_leaf=config.min_samples_leaf,
        l2_regularization=config.l2_regularization,
        max_features=config.max_features,
        early_stopping=config.early_stopping,
        validation_fraction=config.validation_fraction,
        n_iter_no_change=config.n_iter_no_change,
        tol=config.tol,
        random_state=config.random_seed,
    )
    model.fit(
        encoded[feature_columns].astype("float32").to_numpy(),
        clipped_target(frame["target"], config.target_clip_quantile),
        sample_weight=trade_quality_sample_weights(frame, config.sample_weighting),
    )
    return TradeQualityModelBundle(
        config=config,
        model=model,
        feature_columns=feature_columns,
        category_mappings=mappings,
        target_mean=float(frame["target"].mean()),
    )


def predict_trade_quality_features(raw_features: pd.DataFrame, bundle: TradeQualityModelBundle) -> np.ndarray:
    encoded = encode_trade_quality_features(raw_features, bundle.category_mappings)
    predictions = bundle.model.predict(encoded[bundle.feature_columns].astype("float32").to_numpy())
    if bundle.config.prediction_shrinkage < 1.0:
        predictions = (
            bundle.config.prediction_shrinkage * predictions
            + (1.0 - bundle.config.prediction_shrinkage) * bundle.target_mean
        )
    return predictions


def add_trade_quality_model_columns(
    predictions: pd.DataFrame,
    bundle: TradeQualityModelBundle,
) -> pd.DataFrame:
    output = predictions.copy()
    output[TRADE_QUALITY_LONG_COLUMN] = predict_trade_quality_features(
        trade_quality_features_from_predictions(output, "long"),
        bundle,
    )
    output[TRADE_QUALITY_SHORT_COLUMN] = predict_trade_quality_features(
        trade_quality_features_from_predictions(output, "short"),
        bundle,
    )
    return output


def add_trade_quality_model_values_to_enriched(
    enriched: pd.DataFrame,
    bundle: TradeQualityModelBundle,
) -> pd.DataFrame:
    output = enriched.copy()
    predictions = predict_trade_quality_features(trade_quality_features_from_enriched(output), bundle)
    output[TRADE_QUALITY_TAKEN_COLUMN] = predictions
    return output


def side_examples(df: pd.DataFrame, side_name: str) -> pd.DataFrame:
    spec = SIDE_COLUMNS[side_name]
    side_value = 1.0 if side_name == "long" else -1.0
    side_ev = df[spec["ev"]].astype(float)
    opposite_ev = df[spec["opposite_ev"]].astype(float)
    output = pd.DataFrame(
        {
            "side": side_value,
            "pred_side_ev": side_ev,
            "pred_opposite_ev": opposite_ev,
            "pred_side_calibrated_ev": optional_column(
                df,
                spec["calibrated_ev"],
                spec["ev"],
            ).astype(float),
            "pred_opposite_calibrated_ev": optional_column(
                df,
                spec["opposite_calibrated_ev"],
                spec["opposite_ev"],
            ).astype(float),
            "pred_side_gap": side_ev - opposite_ev,
            "pred_side_risk": df[spec["risk"]].astype(float),
            "pred_side_holding": df[spec["holding"]].astype(float),
            "pred_side_wait_regret": df[spec["wait_regret"]].astype(float),
            "pred_side_entry_rank": df[spec["entry_rank"]].astype(float),
            "pred_side_entry_urgency": df[spec["entry_urgency"]].astype(float),
            "pred_side_profit_barrier_hit": df[spec["profit_barrier_hit"]].astype(float),
            "pred_side_wait_regret_quantile": df[spec["wait_regret_quantile"]].astype(float),
            "pred_side_entry_rank_bin": df[spec["entry_rank_bin"]].astype(float),
            "pred_best_adjusted_pnl_quantile": df["pred_best_adjusted_pnl_quantile"].astype(float),
            "pred_side_score_quantile": df["pred_side_score_quantile"].astype(float),
            "pred_label": df["pred_label"].astype(float),
            "target": df[spec["target"]].astype(float),
            "opposite_target": df[spec["opposite_target"]].astype(float),
            "side_name": side_name,
        }
    )
    if "dataset_month" in df.columns:
        output["dataset_month"] = df["dataset_month"].astype(str)
    for column in GENERALIZATION_FEATURE_COLUMNS:
        if column in df.columns:
            output[column] = df[column].astype(float)
    return output


def build_training_frame(df: pd.DataFrame, feature_columns: list[str] | None = None) -> pd.DataFrame:
    feature_columns = feature_columns or available_feature_columns(df)
    frame = pd.concat(
        [side_examples(df, "long"), side_examples(df, "short")],
        ignore_index=True,
    )
    return frame.replace([np.inf, -np.inf], np.nan).dropna(subset=[*feature_columns, "target"])


def as_matrix(df: pd.DataFrame, feature_columns: list[str] | None = None) -> np.ndarray:
    feature_columns = feature_columns or BASE_FEATURE_COLUMNS
    return df[feature_columns].astype("float32").to_numpy()


def clipped_target(values: pd.Series, clip_quantile: float) -> np.ndarray:
    target = values.astype(float)
    if clip_quantile >= 1.0:
        return target.to_numpy()
    if not 0.5 < clip_quantile <= 1.0:
        raise ValueError("target_clip_quantile must be in (0.5, 1.0]")
    lower = target.quantile(1.0 - clip_quantile)
    upper = target.quantile(clip_quantile)
    return target.clip(lower=lower, upper=upper).to_numpy()


def regression_metrics(y_true: pd.Series, y_pred: np.ndarray) -> dict[str, float]:
    return {
        "mae": float(mean_absolute_error(y_true, y_pred)),
        "rmse": float(mean_squared_error(y_true, y_pred) ** 0.5),
        "r2": float(r2_score(y_true, y_pred)),
    }


def build_sample_weights(frame: pd.DataFrame, weighting: str) -> np.ndarray | None:
    if weighting == "none":
        return None
    weights = pd.Series(1.0, index=frame.index, dtype="float64")
    if weighting == "month":
        if "dataset_month" not in frame.columns:
            raise ValueError("month sample weighting requires dataset_month")
        weights *= 1.0 / frame.groupby("dataset_month")["target"].transform("size")
    elif weighting == "side":
        weights *= 1.0 / frame.groupby("side")["target"].transform("size")
    elif weighting == "month_side":
        if "dataset_month" not in frame.columns:
            raise ValueError("month_side sample weighting requires dataset_month")
        weights *= 1.0 / frame.groupby(["dataset_month", "side"])["target"].transform("size")
    else:
        raise ValueError(f"unknown sample weighting: {weighting}")
    weights = weights / weights.mean()
    return weights.to_numpy(dtype="float64")


def side_target_means(frame: pd.DataFrame) -> dict[str, float]:
    means = frame.groupby("side")["target"].mean()
    return {
        "long": float(means.get(1.0, frame["target"].mean())),
        "short": float(means.get(-1.0, frame["target"].mean())),
    }


def train_model(
    frame: pd.DataFrame,
    config: MetaModelConfig,
    feature_columns: list[str] | None = None,
) -> HistGradientBoostingRegressor:
    model = HistGradientBoostingRegressor(
        max_iter=config.max_iter,
        learning_rate=config.learning_rate,
        max_leaf_nodes=config.max_leaf_nodes,
        max_depth=config.max_depth,
        min_samples_leaf=config.min_samples_leaf,
        l2_regularization=config.l2_regularization,
        max_features=config.max_features,
        early_stopping=config.early_stopping,
        validation_fraction=config.validation_fraction,
        n_iter_no_change=config.n_iter_no_change,
        tol=config.tol,
        random_state=config.random_seed,
    )
    model.fit(
        as_matrix(frame, feature_columns),
        clipped_target(frame["target"], config.target_clip_quantile),
        sample_weight=build_sample_weights(frame, config.sample_weighting),
    )
    return model


def add_meta_predictions(
    df: pd.DataFrame,
    model: HistGradientBoostingRegressor,
    feature_columns: list[str] | None = None,
    prediction_shrinkage: float = 1.0,
    side_means: dict[str, float] | None = None,
) -> pd.DataFrame:
    if not 0.0 <= prediction_shrinkage <= 1.0:
        raise ValueError("prediction_shrinkage must be in [0, 1]")
    output = df.copy()
    for side_name, output_column in [
        ("long", "pred_meta_long_adjusted_pnl"),
        ("short", "pred_meta_short_adjusted_pnl"),
    ]:
        examples = side_examples(df, side_name)
        predictions = model.predict(as_matrix(examples, feature_columns))
        if side_means is not None and prediction_shrinkage < 1.0:
            center = side_means[side_name]
            predictions = prediction_shrinkage * predictions + (1.0 - prediction_shrinkage) * center
        output[output_column] = predictions
    return output


def split_meta_metrics(df: pd.DataFrame, entry_threshold: float) -> dict[str, object]:
    metrics = {
        "long": regression_metrics(df["long_best_adjusted_pnl"], df["pred_meta_long_adjusted_pnl"].to_numpy()),
        "short": regression_metrics(df["short_best_adjusted_pnl"], df["pred_meta_short_adjusted_pnl"].to_numpy()),
        "selection": selection_metrics(
            df,
            threshold=entry_threshold,
            long_column="pred_meta_long_adjusted_pnl",
            short_column="pred_meta_short_adjusted_pnl",
        ),
    }
    return metrics


def split_group_calibration_metrics(df: pd.DataFrame, entry_threshold: float) -> dict[str, object]:
    metrics: dict[str, object] = {
        "long": regression_metrics(
            df["long_best_adjusted_pnl"],
            df["pred_regime_calibrated_long_best_adjusted_pnl"].to_numpy(),
        ),
        "short": regression_metrics(
            df["short_best_adjusted_pnl"],
            df["pred_regime_calibrated_short_best_adjusted_pnl"].to_numpy(),
        ),
        "selection": selection_metrics(
            df,
            threshold=entry_threshold,
            long_column="pred_regime_calibrated_long_best_adjusted_pnl",
            short_column="pred_regime_calibrated_short_best_adjusted_pnl",
        ),
    }
    if (
        "pred_regime_calibrated_long_best_adjusted_pnl_lower" in df.columns
        and "pred_regime_calibrated_short_best_adjusted_pnl_lower" in df.columns
    ):
        long_lower_error = (
            df["pred_regime_calibrated_long_best_adjusted_pnl_lower"].astype(float)
            - df["long_best_adjusted_pnl"].astype(float)
        )
        short_lower_error = (
            df["pred_regime_calibrated_short_best_adjusted_pnl_lower"].astype(float)
            - df["short_best_adjusted_pnl"].astype(float)
        )
        metrics["long_lower"] = regression_metrics(
            df["long_best_adjusted_pnl"],
            df["pred_regime_calibrated_long_best_adjusted_pnl_lower"].to_numpy(),
        )
        metrics["short_lower"] = regression_metrics(
            df["short_best_adjusted_pnl"],
            df["pred_regime_calibrated_short_best_adjusted_pnl_lower"].to_numpy(),
        )
        metrics["lower_selection"] = selection_metrics(
            df,
            threshold=entry_threshold,
            long_column="pred_regime_calibrated_long_best_adjusted_pnl_lower",
            short_column="pred_regime_calibrated_short_best_adjusted_pnl_lower",
        )
        metrics["lower_bias"] = {
            "long": float(long_lower_error.mean()),
            "short": float(short_lower_error.mean()),
        }
        metrics["lower_overestimate_mean"] = {
            "long": float(long_lower_error.clip(lower=0).mean()),
            "short": float(short_lower_error.clip(lower=0).mean()),
        }
    return metrics


def split_group_target_calibration_metrics(
    df: pd.DataFrame,
    specs: tuple[GroupTargetSpec, ...],
) -> dict[str, object]:
    per_target: dict[str, object] = {}
    all_targets: list[pd.Series] = []
    all_predictions: list[np.ndarray] = []
    for spec in specs:
        raw_metrics = regression_metrics(
            df[spec.target_column],
            df[spec.prediction_column].to_numpy(),
        )
        calibrated_metrics = regression_metrics(
            df[spec.target_column],
            df[spec.output_column].to_numpy(),
        )
        pred_error = df[spec.prediction_column].astype(float) - df[spec.target_column].astype(float)
        calibrated_error = df[spec.output_column].astype(float) - df[spec.target_column].astype(float)
        metrics = {
            "raw": raw_metrics,
            "calibrated": calibrated_metrics,
            "raw_bias": float(pred_error.mean()),
            "calibrated_bias": float(calibrated_error.mean()),
            "bias_reduction": float(abs(pred_error.mean()) - abs(calibrated_error.mean())),
        }
        lower_column = f"{spec.output_column}_lower"
        if lower_column in df.columns:
            lower_error = df[lower_column].astype(float) - df[spec.target_column].astype(float)
            metrics["lower"] = regression_metrics(
                df[spec.target_column],
                df[lower_column].to_numpy(),
            )
            metrics["lower_bias"] = float(lower_error.mean())
            metrics["lower_overestimate_mean"] = float(lower_error.clip(lower=0).mean())
            metrics["lower_margin_mean"] = float(df[f"{spec.output_column}_lower_margin"].mean())
        per_target[spec.name] = metrics
        all_targets.append(df[spec.target_column].astype(float))
        all_predictions.append(df[spec.output_column].astype(float).to_numpy())
    return {
        "targets": per_target,
        "pooled": regression_metrics(
            pd.concat(all_targets, ignore_index=True),
            np.concatenate(all_predictions),
        ),
    }


def serializable_group_calibrator(calibrator: GroupEVCalibrator) -> dict[str, object]:
    return {
        "config": asdict(calibrator.config),
        "side_stats": {side: asdict(stats) for side, stats in calibrator.side_stats.items()},
        "group_stats": {
            side: {
                "|".join(key): asdict(stats)
                for key, stats in side_groups.items()
            }
            for side, side_groups in calibrator.group_stats.items()
        },
    }


def serializable_group_target_calibrator(calibrator: GroupTargetCalibrator) -> dict[str, object]:
    return {
        "config": asdict(calibrator.config),
        "specs": [asdict(spec) for spec in calibrator.specs],
        "target_stats": {name: asdict(stats) for name, stats in calibrator.target_stats.items()},
        "group_stats": {
            name: {
                "|".join(key): asdict(stats)
                for key, stats in target_groups.items()
            }
            for name, target_groups in calibrator.group_stats.items()
        },
    }


def serializable_trade_quality_calibrator(calibrator: TradeQualityCalibrator) -> dict[str, object]:
    return {
        "config": asdict(calibrator.config),
        "overall_stats": asdict(calibrator.overall_stats),
        "side_stats": {side: asdict(stats) for side, stats in calibrator.side_stats.items()},
        "group_stats": {
            side: {
                "|".join(key): asdict(stats)
                for key, stats in side_groups.items()
            }
            for side, side_groups in calibrator.group_stats.items()
        },
    }


def validate_group_columns(
    fit_predictions: pd.DataFrame,
    apply_predictions: pd.DataFrame,
    group_columns: tuple[str, ...],
) -> None:
    missing_fit = sorted(set(group_columns) - set(fit_predictions.columns))
    missing_apply = sorted(set(group_columns) - set(apply_predictions.columns))
    if missing_fit:
        raise ValueError(f"fit predictions missing group columns: {', '.join(missing_fit)}")
    if missing_apply:
        raise ValueError(f"apply predictions missing group columns: {', '.join(missing_apply)}")


def combine_fit_predictions(
    primary_fit_predictions: pd.DataFrame,
    base_fit_predictions: pd.DataFrame | None,
) -> pd.DataFrame:
    if primary_fit_predictions.empty:
        raise ValueError("primary fit predictions are empty")
    if base_fit_predictions is None:
        return primary_fit_predictions.copy()
    if base_fit_predictions.empty:
        raise ValueError("base fit predictions are empty")
    return pd.concat([base_fit_predictions, primary_fit_predictions], ignore_index=True)


def fit_group_calibration(args: argparse.Namespace) -> int:
    fit_months = parse_csv_months(args.fit_months)
    apply_months = parse_csv_months(args.apply_months)
    fit_predictions = filter_months(
        pd.read_parquet(args.fit_predictions),
        fit_months,
        "fit",
    )
    apply_predictions = filter_months(
        pd.read_parquet(args.apply_predictions),
        apply_months,
        "apply",
    )
    config = GroupEVCalibrationConfig(
        group_columns=tuple(parse_csv_strings(args.group_columns)),
        min_group_size=args.min_group_size,
        prior_strength=args.prior_strength,
        prediction_shrinkage=args.prediction_shrinkage,
        lower_z=args.lower_z,
    )
    validate_group_columns(fit_predictions, apply_predictions, config.group_columns)
    calibrator = fit_group_ev_calibrator(fit_predictions, config)
    fit_output = add_group_calibrated_ev_columns(fit_predictions, calibrator)
    apply_output = add_group_calibrated_ev_columns(apply_predictions, calibrator)

    run_dir = make_run_dir(args.output_dir, args.label)
    fit_output.to_parquet(run_dir / "predictions_fit_regime_calibrated.parquet", index=False)
    apply_output.to_parquet(run_dir / "predictions_apply_regime_calibrated.parquet", index=False)
    metrics = {
        "mode": "fit_apply",
        "fit_predictions": str(args.fit_predictions),
        "apply_predictions": str(args.apply_predictions),
        "fit_months": fit_months,
        "apply_months": apply_months,
        "rows": {
            "fit": int(len(fit_predictions)),
            "apply": int(len(apply_predictions)),
        },
        "month_rows": {
            "fit": month_counts(fit_predictions),
            "apply": month_counts(apply_predictions),
        },
        "calibrator": serializable_group_calibrator(calibrator),
        "fit": split_group_calibration_metrics(fit_output, args.entry_threshold),
        "apply": split_group_calibration_metrics(apply_output, args.entry_threshold),
    }
    with (run_dir / "metrics.json").open("w", encoding="utf-8") as handle:
        json.dump(metrics, handle, ensure_ascii=False, indent=2)
    print(json.dumps(metrics["fit"], indent=2))
    print(json.dumps(metrics["apply"], indent=2))
    print(f"artifacts: {run_dir}")
    return 0


def oof_group_calibration(args: argparse.Namespace) -> int:
    validation_months = parse_csv_months(args.validation_months)
    test_months = parse_csv_months(args.test_months)
    base_fit_months = parse_csv_months(args.base_fit_months)
    if validation_months is None or len(validation_months) < 2:
        raise ValueError("at least two validation months are required for OOF calibration")
    if args.base_fit_predictions is None and base_fit_months is not None:
        raise ValueError("--base-fit-months requires --base-fit-predictions")
    validation_predictions = filter_months(
        pd.read_parquet(args.validation_predictions),
        validation_months,
        "validation",
    )
    test_predictions = filter_months(
        pd.read_parquet(args.test_predictions),
        test_months,
        "test",
    )
    base_fit_predictions = None
    if args.base_fit_predictions is not None:
        base_fit_predictions = filter_months(
            pd.read_parquet(args.base_fit_predictions),
            base_fit_months,
            "base_fit",
        )
    config = GroupEVCalibrationConfig(
        group_columns=tuple(parse_csv_strings(args.group_columns)),
        min_group_size=args.min_group_size,
        prior_strength=args.prior_strength,
        prediction_shrinkage=args.prediction_shrinkage,
        lower_z=args.lower_z,
    )
    validate_group_columns(validation_predictions, test_predictions, config.group_columns)
    if base_fit_predictions is not None:
        validate_group_columns(base_fit_predictions, validation_predictions, config.group_columns)

    fold_outputs: list[pd.DataFrame] = []
    fold_metrics: dict[str, object] = {}
    for holdout_month in validation_months:
        validation_fit_predictions = validation_predictions[
            validation_predictions["dataset_month"] != holdout_month
        ].copy()
        fit_predictions = combine_fit_predictions(validation_fit_predictions, base_fit_predictions)
        holdout_predictions = validation_predictions[
            validation_predictions["dataset_month"] == holdout_month
        ].copy()
        if fit_predictions.empty or holdout_predictions.empty:
            raise ValueError(f"cannot build OOF fold for {holdout_month}")
        fold_calibrator = fit_group_ev_calibrator(fit_predictions, config)
        holdout_output = add_group_calibrated_ev_columns(holdout_predictions, fold_calibrator)
        fold_outputs.append(holdout_output)
        fold_metrics[holdout_month] = {
            "fit_rows": int(len(fit_predictions)),
            "base_fit_rows": 0 if base_fit_predictions is None else int(len(base_fit_predictions)),
            "validation_fit_rows": int(len(validation_fit_predictions)),
            "holdout_rows": int(len(holdout_predictions)),
            "holdout": split_group_calibration_metrics(holdout_output, args.entry_threshold),
            "calibrator": serializable_group_calibrator(fold_calibrator),
        }

    validation_oof = pd.concat(fold_outputs, ignore_index=True).sort_values("decision_timestamp")
    final_fit_predictions = combine_fit_predictions(validation_predictions, base_fit_predictions)
    final_calibrator = fit_group_ev_calibrator(final_fit_predictions, config)
    test_output = add_group_calibrated_ev_columns(test_predictions, final_calibrator)

    run_dir = make_run_dir(args.output_dir, args.label)
    validation_oof.to_parquet(
        run_dir / "predictions_validation_oof_regime_calibrated.parquet",
        index=False,
    )
    test_output.to_parquet(run_dir / "predictions_test_regime_calibrated.parquet", index=False)
    metrics = {
        "mode": "validation_oof_test",
        "validation_predictions": str(args.validation_predictions),
        "test_predictions": str(args.test_predictions),
        "base_fit_predictions": None if args.base_fit_predictions is None else str(args.base_fit_predictions),
        "validation_months": validation_months,
        "test_months": test_months,
        "base_fit_months": base_fit_months,
        "rows": {
            "base_fit": 0 if base_fit_predictions is None else int(len(base_fit_predictions)),
            "validation": int(len(validation_predictions)),
            "validation_oof": int(len(validation_oof)),
            "final_fit": int(len(final_fit_predictions)),
            "test": int(len(test_predictions)),
        },
        "month_rows": {
            "base_fit": {} if base_fit_predictions is None else month_counts(base_fit_predictions),
            "validation": month_counts(validation_predictions),
            "validation_oof": month_counts(validation_oof),
            "test": month_counts(test_predictions),
        },
        "final_calibrator": serializable_group_calibrator(final_calibrator),
        "folds": fold_metrics,
        "validation_oof": split_group_calibration_metrics(validation_oof, args.entry_threshold),
        "test": split_group_calibration_metrics(test_output, args.entry_threshold),
    }
    with (run_dir / "metrics.json").open("w", encoding="utf-8") as handle:
        json.dump(metrics, handle, ensure_ascii=False, indent=2)
    print(json.dumps(metrics["validation_oof"], indent=2))
    print(json.dumps(metrics["test"], indent=2))
    print(f"artifacts: {run_dir}")
    return 0


def oof_fixed_horizon_calibration(args: argparse.Namespace) -> int:
    validation_months = parse_csv_months(args.validation_months)
    base_fit_months = parse_csv_months(args.base_fit_months)
    apply_months = parse_csv_months(args.apply_months)
    if validation_months is None or len(validation_months) < 2:
        raise ValueError("at least two validation months are required for OOF calibration")
    if args.base_fit_predictions is None and base_fit_months is not None:
        raise ValueError("--base-fit-months requires --base-fit-predictions")
    if args.apply_predictions is None and apply_months is not None:
        raise ValueError("--apply-months requires --apply-predictions")

    validation_predictions = filter_months(
        pd.read_parquet(args.validation_predictions),
        validation_months,
        "validation",
    )
    base_fit_predictions = None
    if args.base_fit_predictions is not None:
        base_fit_predictions = filter_months(
            pd.read_parquet(args.base_fit_predictions),
            base_fit_months,
            "base_fit",
        )
    apply_predictions = None
    if args.apply_predictions is not None:
        apply_predictions = filter_months(
            pd.read_parquet(args.apply_predictions),
            apply_months,
            "apply",
        )

    fixed_horizon_minutes = tuple(parse_csv_ints(args.fixed_horizon_minutes))
    if not fixed_horizon_minutes:
        raise ValueError("at least one fixed horizon minute is required")
    if any(minutes <= 0 for minutes in fixed_horizon_minutes):
        raise ValueError("fixed horizon minutes must be positive")
    specs = fixed_horizon_target_specs(fixed_horizon_minutes)
    config = GroupEVCalibrationConfig(
        group_columns=tuple(parse_csv_strings(args.group_columns)),
        min_group_size=args.min_group_size,
        prior_strength=args.prior_strength,
        prediction_shrinkage=args.prediction_shrinkage,
        lower_z=args.lower_z,
    )
    if base_fit_predictions is not None:
        validate_group_columns(base_fit_predictions, validation_predictions, config.group_columns)
    if apply_predictions is not None:
        validate_group_columns(validation_predictions, apply_predictions, config.group_columns)

    fold_outputs: list[pd.DataFrame] = []
    fold_metrics: dict[str, object] = {}
    for holdout_month in validation_months:
        validation_fit_predictions = validation_predictions[
            validation_predictions["dataset_month"] != holdout_month
        ].copy()
        fit_predictions = combine_fit_predictions(validation_fit_predictions, base_fit_predictions)
        holdout_predictions = validation_predictions[
            validation_predictions["dataset_month"] == holdout_month
        ].copy()
        if fit_predictions.empty or holdout_predictions.empty:
            raise ValueError(f"cannot build OOF fold for {holdout_month}")
        fold_calibrator = fit_group_target_calibrator(fit_predictions, config, specs)
        holdout_output = add_group_calibrated_fixed_horizon_columns(holdout_predictions, fold_calibrator)
        fold_outputs.append(holdout_output)
        fold_metrics[holdout_month] = {
            "fit_rows": int(len(fit_predictions)),
            "base_fit_rows": 0 if base_fit_predictions is None else int(len(base_fit_predictions)),
            "validation_fit_rows": int(len(validation_fit_predictions)),
            "holdout_rows": int(len(holdout_predictions)),
            "holdout": split_group_target_calibration_metrics(holdout_output, specs),
            "calibrator": serializable_group_target_calibrator(fold_calibrator),
        }

    validation_oof = pd.concat(fold_outputs, ignore_index=True)
    if "decision_timestamp" in validation_oof.columns:
        validation_oof = validation_oof.sort_values("decision_timestamp")
    final_fit_predictions = combine_fit_predictions(validation_predictions, base_fit_predictions)
    final_calibrator = fit_group_target_calibrator(final_fit_predictions, config, specs)
    apply_output = None
    if apply_predictions is not None:
        apply_output = add_group_calibrated_fixed_horizon_columns(apply_predictions, final_calibrator)

    run_dir = make_run_dir(args.output_dir, args.label)
    validation_oof.to_parquet(
        run_dir / "predictions_validation_oof_fixed_horizon_calibrated.parquet",
        index=False,
    )
    if apply_output is not None:
        apply_output.to_parquet(
            run_dir / "predictions_apply_fixed_horizon_calibrated.parquet",
            index=False,
        )
    metrics = {
        "mode": "validation_oof_fixed_horizon",
        "validation_predictions": str(args.validation_predictions),
        "base_fit_predictions": None if args.base_fit_predictions is None else str(args.base_fit_predictions),
        "apply_predictions": None if args.apply_predictions is None else str(args.apply_predictions),
        "validation_months": validation_months,
        "base_fit_months": base_fit_months,
        "apply_months": apply_months,
        "fixed_horizon_minutes": list(fixed_horizon_minutes),
        "rows": {
            "base_fit": 0 if base_fit_predictions is None else int(len(base_fit_predictions)),
            "validation": int(len(validation_predictions)),
            "validation_oof": int(len(validation_oof)),
            "final_fit": int(len(final_fit_predictions)),
            "apply": 0 if apply_predictions is None else int(len(apply_predictions)),
        },
        "month_rows": {
            "base_fit": {} if base_fit_predictions is None else month_counts(base_fit_predictions),
            "validation": month_counts(validation_predictions),
            "validation_oof": month_counts(validation_oof),
            "apply": {} if apply_predictions is None else month_counts(apply_predictions),
        },
        "final_calibrator": serializable_group_target_calibrator(final_calibrator),
        "folds": fold_metrics,
        "validation_oof": split_group_target_calibration_metrics(validation_oof, specs),
        "apply": None if apply_output is None else split_group_target_calibration_metrics(apply_output, specs),
    }
    with (run_dir / "metrics.json").open("w", encoding="utf-8") as handle:
        json.dump(metrics, handle, ensure_ascii=False, indent=2)
    print(json.dumps(metrics["validation_oof"], indent=2))
    if metrics["apply"] is not None:
        print(json.dumps(metrics["apply"], indent=2))
    print(f"artifacts: {run_dir}")
    return 0


def trade_source_kwargs_from_args(args: argparse.Namespace) -> dict[str, object]:
    return {
        "source_mode": args.source_mode,
        "long_column": args.long_column,
        "short_column": args.short_column,
        "long_fixed_horizon_columns": tuple(parse_csv_strings(args.long_fixed_horizon_columns)),
        "short_fixed_horizon_columns": tuple(parse_csv_strings(args.short_fixed_horizon_columns)),
        "fixed_horizon_score_mode": args.fixed_horizon_score_mode,
    }


def prepare_trade_quality_prediction_frame(
    predictions: pd.DataFrame,
    args: argparse.Namespace,
) -> pd.DataFrame:
    return add_trade_source_ev_columns(predictions, **trade_source_kwargs_from_args(args))


def enrich_trades_for_trade_quality(
    trades: pd.DataFrame,
    predictions: pd.DataFrame,
) -> pd.DataFrame:
    analysis_predictions = prepare_analysis_predictions(
        predictions,
        TRADE_SOURCE_LONG_EV_COLUMN,
        TRADE_SOURCE_SHORT_EV_COLUMN,
    )
    return enrich_trades_with_predictions(trades, analysis_predictions)


def oof_trade_quality_calibration(args: argparse.Namespace) -> int:
    validation_months = parse_csv_months(args.validation_months)
    apply_months = parse_csv_months(args.apply_months)
    if validation_months is None or len(validation_months) < 2:
        raise ValueError("at least two validation months are required for OOF trade quality calibration")
    if args.apply_predictions is None and apply_months is not None:
        raise ValueError("--apply-months requires --apply-predictions")

    validation_predictions = filter_months(
        pd.read_parquet(args.validation_predictions),
        validation_months,
        "validation",
    )
    validation_predictions = prepare_trade_quality_prediction_frame(validation_predictions, args)
    validation_trades = read_trade_frames(parse_csv_paths(args.validation_trades))
    validation_enriched = enrich_trades_for_trade_quality(validation_trades, validation_predictions)
    validation_enriched = validation_enriched[
        validation_enriched["dataset_month"].isin(validation_months)
    ].copy()
    if validation_enriched.empty:
        raise ValueError("validation selected-trade frame is empty after month filtering")

    apply_predictions = None
    if args.apply_predictions is not None:
        apply_predictions = filter_months(
            pd.read_parquet(args.apply_predictions),
            apply_months,
            "apply",
        )
        apply_predictions = prepare_trade_quality_prediction_frame(apply_predictions, args)

    config = GroupEVCalibrationConfig(
        group_columns=tuple(parse_csv_strings(args.group_columns)),
        min_group_size=args.min_group_size,
        prior_strength=args.prior_strength,
        prediction_shrinkage=args.prediction_shrinkage,
        lower_z=args.lower_z,
    )
    validate_group_columns(validation_predictions, validation_predictions, config.group_columns)
    if apply_predictions is not None:
        validate_group_columns(validation_predictions, apply_predictions, config.group_columns)

    fold_prediction_outputs: list[pd.DataFrame] = []
    fold_trade_outputs: list[pd.DataFrame] = []
    fold_metrics: dict[str, object] = {}
    for holdout_month in validation_months:
        fit_trades = validation_enriched[validation_enriched["dataset_month"] != holdout_month].copy()
        holdout_trades = validation_enriched[validation_enriched["dataset_month"] == holdout_month].copy()
        holdout_predictions = validation_predictions[
            validation_predictions["dataset_month"] == holdout_month
        ].copy()
        if fit_trades.empty or holdout_predictions.empty:
            raise ValueError(f"cannot build trade quality OOF fold for {holdout_month}")
        fold_calibrator = fit_trade_quality_calibrator(fit_trades, config)
        holdout_prediction_output = add_trade_quality_columns(holdout_predictions, fold_calibrator)
        holdout_trade_output = add_trade_quality_values_to_enriched(holdout_trades, fold_calibrator)
        fold_prediction_outputs.append(holdout_prediction_output)
        fold_trade_outputs.append(holdout_trade_output)
        fold_metrics[holdout_month] = {
            "fit_trades": int(len(fit_trades)),
            "holdout_trades": int(len(holdout_trades)),
            "holdout_predictions": int(len(holdout_predictions)),
            "holdout": trade_quality_calibration_metrics(holdout_trades, fold_calibrator),
            "calibrator": serializable_trade_quality_calibrator(fold_calibrator),
        }

    validation_oof = pd.concat(fold_prediction_outputs, ignore_index=True)
    if "decision_timestamp" in validation_oof.columns:
        validation_oof = validation_oof.sort_values("decision_timestamp")
    validation_oof_trades = pd.concat(fold_trade_outputs, ignore_index=True)
    if "entry_timestamp" in validation_oof_trades.columns:
        validation_oof_trades = validation_oof_trades.sort_values("entry_timestamp")

    final_calibrator = fit_trade_quality_calibrator(validation_enriched, config)
    apply_output = None
    if apply_predictions is not None:
        apply_output = add_trade_quality_columns(apply_predictions, final_calibrator)

    run_dir = make_run_dir(args.output_dir, args.label)
    validation_oof.to_parquet(
        run_dir / "predictions_validation_oof_trade_quality_calibrated.parquet",
        index=False,
    )
    validation_oof_trades.to_csv(run_dir / "validation_oof_enriched_trades.csv", index=False)
    validation_enriched.to_csv(run_dir / "validation_fit_enriched_trades.csv", index=False)
    if apply_output is not None:
        apply_output.to_parquet(
            run_dir / "predictions_apply_trade_quality_calibrated.parquet",
            index=False,
        )
    metrics = {
        "mode": "validation_oof_trade_quality",
        "validation_trades": [str(path) for path in parse_csv_paths(args.validation_trades)],
        "validation_predictions": str(args.validation_predictions),
        "apply_predictions": None if args.apply_predictions is None else str(args.apply_predictions),
        "validation_months": validation_months,
        "apply_months": apply_months,
        "source": {
            "source_mode": args.source_mode,
            "long_column": args.long_column,
            "short_column": args.short_column,
            "long_fixed_horizon_columns": parse_csv_strings(args.long_fixed_horizon_columns),
            "short_fixed_horizon_columns": parse_csv_strings(args.short_fixed_horizon_columns),
            "fixed_horizon_score_mode": args.fixed_horizon_score_mode,
        },
        "rows": {
            "validation_predictions": int(len(validation_predictions)),
            "validation_trades": int(len(validation_enriched)),
            "validation_oof": int(len(validation_oof)),
            "apply": 0 if apply_predictions is None else int(len(apply_predictions)),
        },
        "month_rows": {
            "validation_predictions": month_counts(validation_predictions),
            "validation_trades": month_counts(validation_enriched),
            "validation_oof": month_counts(validation_oof),
            "apply": {} if apply_predictions is None else month_counts(apply_predictions),
        },
        "final_calibrator": serializable_trade_quality_calibrator(final_calibrator),
        "folds": fold_metrics,
        "validation_oof": trade_quality_scored_metrics(validation_oof_trades),
    }
    with (run_dir / "metrics.json").open("w", encoding="utf-8") as handle:
        json.dump(metrics, handle, ensure_ascii=False, indent=2, default=str)
    print(json.dumps(metrics["validation_oof"], indent=2))
    print(f"artifacts: {run_dir}")
    return 0


def trade_quality_model_config_from_args(args: argparse.Namespace) -> TradeQualityModelConfig:
    return TradeQualityModelConfig(
        max_iter=args.max_iter,
        learning_rate=args.learning_rate,
        max_leaf_nodes=args.max_leaf_nodes,
        max_depth=None if args.max_depth <= 0 else args.max_depth,
        min_samples_leaf=args.min_samples_leaf,
        l2_regularization=args.l2_regularization,
        max_features=args.max_features,
        early_stopping=args.early_stopping,
        validation_fraction=args.validation_fraction,
        n_iter_no_change=args.n_iter_no_change,
        tol=args.tol,
        random_seed=args.random_seed,
        target_clip_quantile=args.target_clip_quantile,
        sample_weighting=args.sample_weighting,
        prediction_shrinkage=args.prediction_shrinkage,
    )


def oof_trade_quality_model(args: argparse.Namespace) -> int:
    validation_months = parse_csv_months(args.validation_months)
    apply_months = parse_csv_months(args.apply_months)
    if validation_months is None or len(validation_months) < 2:
        raise ValueError("at least two validation months are required for OOF trade quality model")
    if args.apply_predictions is None and apply_months is not None:
        raise ValueError("--apply-months requires --apply-predictions")

    validation_predictions = filter_months(
        pd.read_parquet(args.validation_predictions),
        validation_months,
        "validation",
    )
    validation_predictions = prepare_trade_quality_prediction_frame(validation_predictions, args)
    validation_trades = read_trade_frames(parse_csv_paths(args.validation_trades))
    validation_enriched = enrich_trades_for_trade_quality(validation_trades, validation_predictions)
    validation_enriched = validation_enriched[
        validation_enriched["dataset_month"].isin(validation_months)
    ].copy()
    if validation_enriched.empty:
        raise ValueError("validation selected-trade frame is empty after month filtering")

    apply_predictions = None
    if args.apply_predictions is not None:
        apply_predictions = filter_months(
            pd.read_parquet(args.apply_predictions),
            apply_months,
            "apply",
        )
        apply_predictions = prepare_trade_quality_prediction_frame(apply_predictions, args)

    config = trade_quality_model_config_from_args(args)
    fold_prediction_outputs: list[pd.DataFrame] = []
    fold_trade_outputs: list[pd.DataFrame] = []
    fold_metrics: dict[str, object] = {}
    for fold_index, holdout_month in enumerate(validation_months):
        fit_trades = validation_enriched[validation_enriched["dataset_month"] != holdout_month].copy()
        holdout_trades = validation_enriched[validation_enriched["dataset_month"] == holdout_month].copy()
        holdout_predictions = validation_predictions[
            validation_predictions["dataset_month"] == holdout_month
        ].copy()
        if fit_trades.empty or holdout_predictions.empty:
            raise ValueError(f"cannot build trade quality model OOF fold for {holdout_month}")
        fold_config = TradeQualityModelConfig(
            **{
                **asdict(config),
                "random_seed": config.random_seed + fold_index,
            }
        )
        fold_bundle = fit_trade_quality_model(fit_trades, fold_config)
        holdout_prediction_output = add_trade_quality_model_columns(holdout_predictions, fold_bundle)
        holdout_trade_output = add_trade_quality_model_values_to_enriched(holdout_trades, fold_bundle)
        fold_prediction_outputs.append(holdout_prediction_output)
        fold_trade_outputs.append(holdout_trade_output)
        fold_metrics[holdout_month] = {
            "fit_trades": int(len(fit_trades)),
            "holdout_trades": int(len(holdout_trades)),
            "holdout_predictions": int(len(holdout_predictions)),
            "holdout": trade_quality_scored_metrics(holdout_trade_output),
            "target_mean": fold_bundle.target_mean,
            "feature_columns": fold_bundle.feature_columns,
            "category_mappings": fold_bundle.category_mappings,
        }

    validation_oof = pd.concat(fold_prediction_outputs, ignore_index=True)
    if "decision_timestamp" in validation_oof.columns:
        validation_oof = validation_oof.sort_values("decision_timestamp")
    validation_oof_trades = pd.concat(fold_trade_outputs, ignore_index=True)
    if "entry_timestamp" in validation_oof_trades.columns:
        validation_oof_trades = validation_oof_trades.sort_values("entry_timestamp")

    final_bundle = fit_trade_quality_model(validation_enriched, config)
    apply_output = None
    if apply_predictions is not None:
        apply_output = add_trade_quality_model_columns(apply_predictions, final_bundle)

    run_dir = make_run_dir(args.output_dir, args.label)
    validation_oof.to_parquet(
        run_dir / "predictions_validation_oof_trade_quality_model.parquet",
        index=False,
    )
    validation_oof_trades.to_csv(run_dir / "validation_oof_model_enriched_trades.csv", index=False)
    validation_enriched.to_csv(run_dir / "validation_fit_enriched_trades.csv", index=False)
    if apply_output is not None:
        apply_output.to_parquet(
            run_dir / "predictions_apply_trade_quality_model.parquet",
            index=False,
        )
    joblib.dump(final_bundle, run_dir / "trade_quality_model.joblib")
    metrics = {
        "mode": "validation_oof_trade_quality_model",
        "config": asdict(config),
        "validation_trades": [str(path) for path in parse_csv_paths(args.validation_trades)],
        "validation_predictions": str(args.validation_predictions),
        "apply_predictions": None if args.apply_predictions is None else str(args.apply_predictions),
        "validation_months": validation_months,
        "apply_months": apply_months,
        "source": {
            "source_mode": args.source_mode,
            "long_column": args.long_column,
            "short_column": args.short_column,
            "long_fixed_horizon_columns": parse_csv_strings(args.long_fixed_horizon_columns),
            "short_fixed_horizon_columns": parse_csv_strings(args.short_fixed_horizon_columns),
            "fixed_horizon_score_mode": args.fixed_horizon_score_mode,
        },
        "rows": {
            "validation_predictions": int(len(validation_predictions)),
            "validation_trades": int(len(validation_enriched)),
            "validation_oof": int(len(validation_oof)),
            "apply": 0 if apply_predictions is None else int(len(apply_predictions)),
        },
        "month_rows": {
            "validation_predictions": month_counts(validation_predictions),
            "validation_trades": month_counts(validation_enriched),
            "validation_oof": month_counts(validation_oof),
            "apply": {} if apply_predictions is None else month_counts(apply_predictions),
        },
        "final_model": {
            "target_mean": final_bundle.target_mean,
            "feature_columns": final_bundle.feature_columns,
            "category_mappings": final_bundle.category_mappings,
        },
        "folds": fold_metrics,
        "validation_oof": trade_quality_scored_metrics(validation_oof_trades),
    }
    with (run_dir / "metrics.json").open("w", encoding="utf-8") as handle:
        json.dump(metrics, handle, ensure_ascii=False, indent=2, default=str)
    print(json.dumps(metrics["validation_oof"], indent=2))
    print(f"artifacts: {run_dir}")
    return 0


def fit(args: argparse.Namespace) -> int:
    config = MetaModelConfig(
        max_iter=args.max_iter,
        learning_rate=args.learning_rate,
        max_leaf_nodes=args.max_leaf_nodes,
        max_depth=None if args.max_depth <= 0 else args.max_depth,
        min_samples_leaf=args.min_samples_leaf,
        l2_regularization=args.l2_regularization,
        max_features=args.max_features,
        early_stopping=args.early_stopping,
        validation_fraction=args.validation_fraction,
        n_iter_no_change=args.n_iter_no_change,
        tol=args.tol,
        random_seed=args.random_seed,
        target_clip_quantile=args.target_clip_quantile,
        entry_threshold=args.entry_threshold,
        sample_weighting=args.sample_weighting,
        prediction_shrinkage=args.prediction_shrinkage,
    )
    train_months = parse_csv_months(args.train_months)
    apply_months = parse_csv_months(args.apply_months)
    train_predictions = filter_months(
        pd.read_parquet(args.train_predictions),
        train_months,
        "train",
    )
    apply_predictions = filter_months(
        pd.read_parquet(args.apply_predictions),
        apply_months,
        "apply",
    )
    feature_columns = available_feature_columns(train_predictions)
    regime_feature_columns = [column for column in GENERALIZATION_FEATURE_COLUMNS if column in train_predictions.columns]
    missing_apply_features = sorted(set(regime_feature_columns) - set(apply_predictions.columns))
    if missing_apply_features:
        raise ValueError(f"apply predictions missing feature columns: {', '.join(missing_apply_features)}")
    train_frame = build_training_frame(train_predictions, feature_columns)
    means = side_target_means(train_frame)
    model = train_model(train_frame, config, feature_columns)
    train_output = add_meta_predictions(
        train_predictions,
        model,
        feature_columns,
        config.prediction_shrinkage,
        means,
    )
    apply_output = add_meta_predictions(
        apply_predictions,
        model,
        feature_columns,
        config.prediction_shrinkage,
        means,
    )

    run_dir = make_run_dir(args.output_dir, args.label)
    train_output.to_parquet(run_dir / "predictions_train_meta.parquet", index=False)
    apply_output.to_parquet(run_dir / "predictions_apply_meta.parquet", index=False)
    joblib.dump(model, run_dir / "meta_ev_regressor.joblib")
    metrics = {
        "config": asdict(config),
        "train_predictions": str(args.train_predictions),
        "apply_predictions": str(args.apply_predictions),
        "train_months": train_months,
        "apply_months": apply_months,
        "rows": {
            "train_predictions": int(len(train_predictions)),
            "train_side_examples": int(len(train_frame)),
            "apply_predictions": int(len(apply_predictions)),
        },
        "month_rows": {
            "train": month_counts(train_predictions),
            "apply": month_counts(apply_predictions),
        },
        "feature_columns": feature_columns,
        "side_target_means": means,
        "train": split_meta_metrics(train_output, args.entry_threshold),
        "apply": split_meta_metrics(apply_output, args.entry_threshold),
    }
    with (run_dir / "metrics.json").open("w", encoding="utf-8") as handle:
        json.dump(metrics, handle, ensure_ascii=False, indent=2)
    print(json.dumps(metrics["train"], indent=2))
    print(json.dumps(metrics["apply"], indent=2))
    print(f"artifacts: {run_dir}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fit second-stage meta models from prediction frames")
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_group_calibration_args(
        group_parser: argparse.ArgumentParser,
        default_label: str = "regime_ev_calibration",
    ) -> None:
        group_parser.add_argument(
            "--group-columns",
            default="volatility_regime,session_regime",
            help="comma-separated categorical columns for side/regime EV calibration",
        )
        group_parser.add_argument("--min-group-size", type=int, default=500)
        group_parser.add_argument("--prior-strength", type=float, default=2000.0)
        group_parser.add_argument("--prediction-shrinkage", type=float, default=0.65)
        group_parser.add_argument(
            "--lower-z",
            type=float,
            default=0.0,
            help=(
                "non-negative margin weight for support-aware lower EV columns; with prior_strength > 0 "
                "the margin uses target std scaled by sqrt(prior/(support+prior))"
            ),
        )
        group_parser.add_argument("--entry-threshold", type=float, default=15.0)
        group_parser.add_argument("--output-dir", type=Path, default=Path("experiments"))
        group_parser.add_argument("--label", default=default_label)

    def add_trade_source_args(source_parser: argparse.ArgumentParser) -> None:
        source_parser.add_argument(
            "--source-mode",
            choices=["columns", "fixed_horizon"],
            default="fixed_horizon",
            help="which side EV source to calibrate from selected trades",
        )
        source_parser.add_argument("--long-column", default="pred_long_best_adjusted_pnl")
        source_parser.add_argument("--short-column", default="pred_short_best_adjusted_pnl")
        source_parser.add_argument(
            "--long-fixed-horizon-columns",
            default="pred_long_fixed_60m_adjusted_pnl,pred_long_fixed_240m_adjusted_pnl,pred_long_fixed_720m_adjusted_pnl",
        )
        source_parser.add_argument(
            "--short-fixed-horizon-columns",
            default="pred_short_fixed_60m_adjusted_pnl,pred_short_fixed_240m_adjusted_pnl,pred_short_fixed_720m_adjusted_pnl",
        )
        source_parser.add_argument(
            "--fixed-horizon-score-mode",
            choices=FIXED_HORIZON_SCORE_MODES,
            default="max",
        )

    def add_trade_quality_model_args(model_parser: argparse.ArgumentParser) -> None:
        model_parser.add_argument("--max-iter", type=int, default=80)
        model_parser.add_argument("--learning-rate", type=float, default=0.03)
        model_parser.add_argument("--max-leaf-nodes", type=int, default=5)
        model_parser.add_argument("--max-depth", type=int, default=2, help="<=0 disables depth limit")
        model_parser.add_argument("--min-samples-leaf", type=int, default=20)
        model_parser.add_argument("--l2-regularization", type=float, default=1.0)
        model_parser.add_argument("--max-features", type=float, default=0.8)
        model_parser.add_argument("--early-stopping", type=parse_bool, default=True)
        model_parser.add_argument("--validation-fraction", type=float, default=0.2)
        model_parser.add_argument("--n-iter-no-change", type=int, default=10)
        model_parser.add_argument("--tol", type=float, default=1e-6)
        model_parser.add_argument("--random-seed", type=int, default=31)
        model_parser.add_argument("--target-clip-quantile", type=float, default=0.98)
        model_parser.add_argument(
            "--sample-weighting",
            choices=["none", "month", "side", "month_side"],
            default="month_side",
        )
        model_parser.add_argument("--prediction-shrinkage", type=float, default=0.7)

    fit_parser = subparsers.add_parser("fit", help="fit a meta EV model and apply it")
    fit_parser.add_argument("--train-predictions", type=Path, required=True)
    fit_parser.add_argument("--apply-predictions", type=Path, required=True)
    fit_parser.add_argument("--train-months", help="comma-separated dataset months to fit on")
    fit_parser.add_argument("--apply-months", help="comma-separated dataset months to apply to")
    fit_parser.add_argument("--output-dir", type=Path, default=Path("experiments"))
    fit_parser.add_argument("--label", default="meta_ev")
    fit_parser.add_argument("--max-iter", type=int, default=200)
    fit_parser.add_argument("--learning-rate", type=float, default=0.025)
    fit_parser.add_argument("--max-leaf-nodes", type=int, default=7)
    fit_parser.add_argument("--max-depth", type=int, default=3, help="<=0 disables depth limit")
    fit_parser.add_argument("--min-samples-leaf", type=int, default=300)
    fit_parser.add_argument("--l2-regularization", type=float, default=1.0)
    fit_parser.add_argument("--max-features", type=float, default=0.8)
    fit_parser.add_argument("--early-stopping", type=parse_bool, default=True)
    fit_parser.add_argument("--validation-fraction", type=float, default=0.15)
    fit_parser.add_argument("--n-iter-no-change", type=int, default=10)
    fit_parser.add_argument("--tol", type=float, default=1e-6)
    fit_parser.add_argument("--random-seed", type=int, default=17)
    fit_parser.add_argument("--target-clip-quantile", type=float, default=0.98)
    fit_parser.add_argument("--entry-threshold", type=float, default=15.0)
    fit_parser.add_argument(
        "--sample-weighting",
        choices=["none", "month", "side", "month_side"],
        default="month_side",
    )
    fit_parser.add_argument("--prediction-shrinkage", type=float, default=0.75)
    fit_parser.set_defaults(func=fit)

    group_fit_parser = subparsers.add_parser(
        "fit-group-calibration",
        help="fit side/regime EV calibration on one prediction frame and apply it to another",
    )
    group_fit_parser.add_argument("--fit-predictions", type=Path, required=True)
    group_fit_parser.add_argument("--apply-predictions", type=Path, required=True)
    group_fit_parser.add_argument("--fit-months", help="comma-separated dataset months to fit on")
    group_fit_parser.add_argument("--apply-months", help="comma-separated dataset months to apply to")
    add_group_calibration_args(group_fit_parser)
    group_fit_parser.set_defaults(func=fit_group_calibration)

    group_oof_parser = subparsers.add_parser(
        "oof-group-calibration",
        help="build validation OOF side/regime EV calibration and a fixed test application",
    )
    group_oof_parser.add_argument("--validation-predictions", type=Path, required=True)
    group_oof_parser.add_argument("--test-predictions", type=Path, required=True)
    group_oof_parser.add_argument(
        "--base-fit-predictions",
        type=Path,
        help="optional OOF prediction frame to include in every validation calibration fit",
    )
    group_oof_parser.add_argument(
        "--validation-months",
        required=True,
        help="comma-separated validation dataset months for OOF folds",
    )
    group_oof_parser.add_argument("--test-months", required=True, help="comma-separated test dataset months")
    group_oof_parser.add_argument("--base-fit-months", help="comma-separated base fit months")
    add_group_calibration_args(group_oof_parser)
    group_oof_parser.set_defaults(func=oof_group_calibration)

    fixed_horizon_oof_parser = subparsers.add_parser(
        "oof-fixed-horizon-calibration",
        help="build validation OOF side/regime calibration for fixed-horizon EV targets",
    )
    fixed_horizon_oof_parser.add_argument("--validation-predictions", type=Path, required=True)
    fixed_horizon_oof_parser.add_argument(
        "--base-fit-predictions",
        type=Path,
        help="optional prediction frame to include in every validation calibration fit",
    )
    fixed_horizon_oof_parser.add_argument(
        "--apply-predictions",
        type=Path,
        help="optional prediction frame to calibrate with the final validation-fitted calibrator",
    )
    fixed_horizon_oof_parser.add_argument(
        "--validation-months",
        required=True,
        help="comma-separated validation dataset months for OOF folds",
    )
    fixed_horizon_oof_parser.add_argument("--base-fit-months", help="comma-separated base fit months")
    fixed_horizon_oof_parser.add_argument("--apply-months", help="comma-separated apply months")
    fixed_horizon_oof_parser.add_argument(
        "--fixed-horizon-minutes",
        default="60,240,720",
        help="comma-separated fixed horizon minutes with target/prediction columns",
    )
    add_group_calibration_args(fixed_horizon_oof_parser, "fixed_horizon_regime_calibration")
    fixed_horizon_oof_parser.set_defaults(func=oof_fixed_horizon_calibration)

    trade_quality_oof_parser = subparsers.add_parser(
        "oof-trade-quality-calibration",
        help="build validation OOF selected-trade realized-PnL calibration columns",
    )
    trade_quality_oof_parser.add_argument(
        "--validation-trades",
        required=True,
        help="comma-separated model-policy trades.csv files for validation months",
    )
    trade_quality_oof_parser.add_argument("--validation-predictions", type=Path, required=True)
    trade_quality_oof_parser.add_argument(
        "--apply-predictions",
        type=Path,
        help="optional prediction frame to calibrate with the final validation-trade calibrator",
    )
    trade_quality_oof_parser.add_argument(
        "--validation-months",
        required=True,
        help="comma-separated validation dataset months for OOF folds",
    )
    trade_quality_oof_parser.add_argument("--apply-months", help="comma-separated apply months")
    add_trade_source_args(trade_quality_oof_parser)
    add_group_calibration_args(trade_quality_oof_parser, "trade_quality_calibration")
    trade_quality_oof_parser.set_defaults(func=oof_trade_quality_calibration)

    trade_quality_model_parser = subparsers.add_parser(
        "oof-trade-quality-model",
        help="build validation OOF selected-trade realized-PnL model columns",
    )
    trade_quality_model_parser.add_argument(
        "--validation-trades",
        required=True,
        help="comma-separated model-policy trades.csv files for validation months",
    )
    trade_quality_model_parser.add_argument("--validation-predictions", type=Path, required=True)
    trade_quality_model_parser.add_argument(
        "--apply-predictions",
        type=Path,
        help="optional prediction frame to score with the final validation-trade model",
    )
    trade_quality_model_parser.add_argument(
        "--validation-months",
        required=True,
        help="comma-separated validation dataset months for OOF folds",
    )
    trade_quality_model_parser.add_argument("--apply-months", help="comma-separated apply months")
    trade_quality_model_parser.add_argument("--output-dir", type=Path, default=Path("experiments"))
    trade_quality_model_parser.add_argument("--label", default="trade_quality_model")
    add_trade_source_args(trade_quality_model_parser)
    add_trade_quality_model_args(trade_quality_model_parser)
    trade_quality_model_parser.set_defaults(func=oof_trade_quality_model)
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
