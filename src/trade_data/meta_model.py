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
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.metrics import brier_score_loss, mean_absolute_error, mean_squared_error, r2_score, roc_auc_score

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
class ResidualPenaltyConfig:
    group_columns: tuple[str, ...]
    min_group_size: int
    prior_strength: float
    penalty_weight: float
    min_excess_overestimate: float = 0.0
    candidate_entry_only: bool = False
    entry_threshold: float = 15.0
    long_entry_threshold_offset: float = 0.0
    short_entry_threshold_offset: float = 0.0
    side_margin: float = 0.0
    min_entry_rank: float = 0.0
    long_entry_rank_column: str = "pred_long_entry_local_rank"
    short_entry_rank_column: str = "pred_short_entry_local_rank"


@dataclass(frozen=True)
class ResidualPenaltyStats:
    n: int
    pred_mean: float
    target_mean: float
    bias: float
    overestimate_mean: float
    overestimate_rate: float


@dataclass(frozen=True)
class ResidualPenaltyCalibrator:
    config: ResidualPenaltyConfig
    long_column: str
    short_column: str
    side_stats: dict[str, ResidualPenaltyStats]
    group_stats: dict[str, dict[tuple[str, ...], ResidualPenaltyStats]]


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


@dataclass(frozen=True)
class TradeFailureModelConfig:
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
    sample_weighting: str
    prediction_shrinkage: float
    large_loss_threshold: float
    exit_regret_threshold: float
    target_names: tuple[str, ...]


@dataclass
class TradeFailureModelBundle:
    config: TradeFailureModelConfig
    models: dict[str, HistGradientBoostingClassifier | None]
    feature_columns: list[str]
    category_mappings: dict[str, dict[str, int]]
    target_means: dict[str, float]


@dataclass(frozen=True)
class CandidateFailureModelConfig:
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
    sample_weighting: str
    prediction_shrinkage: float
    large_adverse_threshold: float
    large_loss_threshold: float
    target_names: tuple[str, ...]
    entry_threshold: float
    long_entry_threshold_offset: float
    short_entry_threshold_offset: float
    side_margin: float
    min_entry_rank: float
    long_entry_rank_column: str = "pred_long_entry_local_rank"
    short_entry_rank_column: str = "pred_short_entry_local_rank"


@dataclass
class CandidateFailureModelBundle:
    config: CandidateFailureModelConfig
    models: dict[str, HistGradientBoostingClassifier | None]
    feature_columns: list[str]
    category_mappings: dict[str, dict[str, int]]
    target_means: dict[str, float]


@dataclass(frozen=True)
class CandidateQualityModelConfig:
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
    lower_quantile: float
    entry_threshold: float
    long_entry_threshold_offset: float
    short_entry_threshold_offset: float
    side_margin: float
    min_entry_rank: float
    target_mode: str = "best_adjusted_pnl"
    min_adjusted_edge: float = 15.0
    time_exit_target_minutes: int = 720
    joint_barrier_weight: float = 0.7
    joint_fixed_horizon_weight: float = 0.2
    joint_best_weight: float = 0.1
    joint_time_decay: float = 0.25
    joint_component_clip_multiple: float = 1.0
    joint_fixed_horizon_minutes: tuple[int, ...] = (60, 240, 720)
    prediction_prefix: str = ""
    long_entry_rank_column: str = "pred_long_entry_local_rank"
    short_entry_rank_column: str = "pred_short_entry_local_rank"


@dataclass
class CandidateQualityModelBundle:
    config: CandidateQualityModelConfig
    mean_model: HistGradientBoostingRegressor
    lower_model: HistGradientBoostingRegressor
    feature_columns: list[str]
    category_mappings: dict[str, dict[str, int]]
    target_mean: float
    lower_target_mean: float


@dataclass(frozen=True)
class CandidateQualityDownsideCalibrationBundle:
    input_prediction_prefix: str
    output_prefix: str
    group_columns: tuple[str, ...]
    bucket_edges: tuple[float, ...]
    min_group_size: int
    prior_strength: float
    lower_z: float
    downside_threshold: float
    large_downside_threshold: float
    global_stats: dict[str, float]
    side_stats: dict[str, dict[str, float]]
    group_stats: dict[tuple[str, ...], dict[str, float]]


@dataclass(frozen=True)
class EntryTimingCalibrationBundle:
    output_prefix: str
    group_columns: tuple[str, ...]
    bucket_edges: tuple[float, ...]
    min_group_size: int
    prior_strength: float
    bad_wait_threshold: float
    global_stats: dict[str, float]
    side_stats: dict[str, dict[str, float]]
    group_stats: dict[tuple[str, ...], dict[str, float]]


@dataclass(frozen=True)
class TradeFailureProbabilityCalibrator:
    config: GroupEVCalibrationConfig
    target_name: str
    overall_stats: GroupEVStats
    side_stats: dict[str, GroupEVStats]
    group_stats: dict[str, dict[tuple[str, ...], GroupEVStats]]


FIXED_HORIZON_MINUTES = (60, 240, 720)
TRADE_FAILURE_TARGET_NAMES = (
    "large_loss",
    "wrong_side",
    "profit_barrier_miss",
    "exit_regret_high",
    "any_failure",
)
CANDIDATE_FAILURE_TARGET_NAMES = (
    "large_adverse",
    "large_loss",
    "wrong_side",
    "range_normal_vol_selected_failure",
    "normal_vol_selected_failure",
    "time_session_selected_failure",
    "any_failure",
)
CANDIDATE_QUALITY_TARGET_MODES = (
    "best_adjusted_pnl",
    "barrier_event_adjusted_pnl",
    "timed_barrier_component_adjusted_pnl",
    "fixed_horizon_component_adjusted_pnl",
    "clipped_best_adjusted_pnl",
    "joint_exit_adjusted_pnl",
)
BARRIER_COMPONENT_TARGET_MODES = (
    "barrier_event_adjusted_pnl",
    "timed_barrier_component_adjusted_pnl",
    "joint_exit_adjusted_pnl",
)
FIXED_HORIZON_COMPONENT_TARGET_MODES = (
    "fixed_horizon_component_adjusted_pnl",
    "joint_exit_adjusted_pnl",
)
CANDIDATE_EXIT_EVENT_TIME = 0
CANDIDATE_EXIT_EVENT_PROFIT = 1
CANDIDATE_EXIT_EVENT_LOSS = 2
TRADE_SOURCE_LONG_EV_COLUMN = "pred_trade_source_long_ev"
TRADE_SOURCE_SHORT_EV_COLUMN = "pred_trade_source_short_ev"
TRADE_QUALITY_LONG_COLUMN = "pred_trade_quality_long_adjusted_pnl"
TRADE_QUALITY_SHORT_COLUMN = "pred_trade_quality_short_adjusted_pnl"
TRADE_QUALITY_TAKEN_COLUMN = "pred_trade_quality_taken_adjusted_pnl"
TRADE_QUALITY_LONG_OVERESTIMATE_COLUMN = "pred_trade_quality_long_overestimate"
TRADE_QUALITY_SHORT_OVERESTIMATE_COLUMN = "pred_trade_quality_short_overestimate"
TRADE_QUALITY_LONG_OVERESTIMATE_RISK_COLUMN = "pred_trade_quality_long_overestimate_risk"
TRADE_QUALITY_SHORT_OVERESTIMATE_RISK_COLUMN = "pred_trade_quality_short_overestimate_risk"
CANDIDATE_QUALITY_LONG_COLUMN = "pred_candidate_quality_long_adjusted_pnl"
CANDIDATE_QUALITY_SHORT_COLUMN = "pred_candidate_quality_short_adjusted_pnl"
CANDIDATE_QUALITY_LONG_LOWER_COLUMN = "pred_candidate_quality_long_lower_adjusted_pnl"
CANDIDATE_QUALITY_SHORT_LOWER_COLUMN = "pred_candidate_quality_short_lower_adjusted_pnl"
CANDIDATE_QUALITY_TAKEN_COLUMN = "pred_candidate_quality_taken_adjusted_pnl"
CANDIDATE_QUALITY_TAKEN_LOWER_COLUMN = "pred_candidate_quality_taken_lower_adjusted_pnl"
CANDIDATE_QUALITY_LONG_OVERESTIMATE_RISK_COLUMN = "pred_candidate_quality_long_overestimate_risk"
CANDIDATE_QUALITY_SHORT_OVERESTIMATE_RISK_COLUMN = "pred_candidate_quality_short_overestimate_risk"
CANDIDATE_QUALITY_LONG_LOWER_OVERESTIMATE_RISK_COLUMN = (
    "pred_candidate_quality_long_lower_overestimate_risk"
)
CANDIDATE_QUALITY_SHORT_LOWER_OVERESTIMATE_RISK_COLUMN = (
    "pred_candidate_quality_short_lower_overestimate_risk"
)
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


def parse_csv_floats(value: str | None) -> list[float]:
    if value is None:
        return []
    output: list[float] = []
    for part in value.split(","):
        stripped = part.strip()
        if not stripped:
            continue
        try:
            output.append(float(stripped))
        except ValueError as exc:
            raise argparse.ArgumentTypeError("CSV values must be floats") from exc
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


def residual_penalty_output_column(side_name: str) -> str:
    return f"pred_regime_residual_penalized_{side_name}_best_adjusted_pnl"


def residual_penalty_stat(pred: pd.Series, target: pd.Series) -> ResidualPenaltyStats:
    frame = (
        pd.DataFrame({"pred": pred.astype(float), "target": target.astype(float)})
        .replace([np.inf, -np.inf], np.nan)
        .dropna(subset=["pred", "target"])
    )
    if frame.empty:
        raise ValueError("no valid rows for residual penalty stats")
    error = frame["pred"] - frame["target"]
    return ResidualPenaltyStats(
        n=int(len(frame)),
        pred_mean=float(frame["pred"].mean()),
        target_mean=float(frame["target"].mean()),
        bias=float(error.mean()),
        overestimate_mean=float(error.clip(lower=0.0).mean()),
        overestimate_rate=float((error > 0.0).mean()),
    )


def shrink_residual_penalty_stats(
    raw: ResidualPenaltyStats,
    prior: ResidualPenaltyStats,
    weight: float,
) -> ResidualPenaltyStats:
    return ResidualPenaltyStats(
        n=raw.n,
        pred_mean=float(weight * raw.pred_mean + (1.0 - weight) * prior.pred_mean),
        target_mean=float(weight * raw.target_mean + (1.0 - weight) * prior.target_mean),
        bias=float(weight * raw.bias + (1.0 - weight) * prior.bias),
        overestimate_mean=float(
            weight * raw.overestimate_mean + (1.0 - weight) * prior.overestimate_mean
        ),
        overestimate_rate=float(
            weight * raw.overestimate_rate + (1.0 - weight) * prior.overestimate_rate
        ),
    )


def residual_side_columns(calibrator: ResidualPenaltyCalibrator, side_name: str) -> tuple[str, str]:
    if side_name == "long":
        return calibrator.long_column, SIDE_COLUMNS[side_name]["target"]
    if side_name == "short":
        return calibrator.short_column, SIDE_COLUMNS[side_name]["target"]
    raise ValueError(f"unknown side: {side_name}")


def validate_residual_penalty_inputs(
    predictions: pd.DataFrame,
    config: ResidualPenaltyConfig,
    long_column: str,
    short_column: str,
) -> None:
    if config.min_group_size <= 0:
        raise ValueError("min_group_size must be positive")
    if config.prior_strength < 0:
        raise ValueError("prior_strength must be non-negative")
    if config.penalty_weight < 0:
        raise ValueError("penalty_weight must be non-negative")
    if config.min_excess_overestimate < 0:
        raise ValueError("min_excess_overestimate must be non-negative")
    if config.side_margin < 0:
        raise ValueError("side_margin must be non-negative")
    if config.min_entry_rank < 0:
        raise ValueError("min_entry_rank must be non-negative")
    required_columns = {
        long_column,
        short_column,
        SIDE_COLUMNS["long"]["target"],
        SIDE_COLUMNS["short"]["target"],
        *config.group_columns,
    }
    if config.candidate_entry_only and config.min_entry_rank > 0:
        required_columns.update(
            {
                config.long_entry_rank_column,
                config.short_entry_rank_column,
            }
        )
    missing_columns = sorted(required_columns - set(predictions.columns))
    if missing_columns:
        raise ValueError(f"predictions missing residual penalty columns: {', '.join(missing_columns)}")


def candidate_entry_side_masks(
    predictions: pd.DataFrame,
    config: ResidualPenaltyConfig,
    *,
    long_column: str,
    short_column: str,
) -> dict[str, pd.Series]:
    long_score = predictions[long_column].astype(float)
    short_score = predictions[short_column].astype(float)
    valid = long_score.notna() & short_score.notna()
    side_gap = (long_score - short_score).abs()
    long_mask = (
        valid
        & (long_score >= short_score)
        & (long_score > config.entry_threshold + config.long_entry_threshold_offset)
        & (side_gap >= config.side_margin)
    )
    short_mask = (
        valid
        & (short_score > long_score)
        & (short_score > config.entry_threshold + config.short_entry_threshold_offset)
        & (side_gap >= config.side_margin)
    )
    if config.min_entry_rank > 0:
        long_rank = predictions[config.long_entry_rank_column].astype(float)
        short_rank = predictions[config.short_entry_rank_column].astype(float)
        long_mask &= long_rank.notna() & (long_rank >= config.min_entry_rank)
        short_mask &= short_rank.notna() & (short_rank >= config.min_entry_rank)
    return {
        "long": pd.Series(long_mask.to_numpy(), index=predictions.index),
        "short": pd.Series(short_mask.to_numpy(), index=predictions.index),
    }


def fit_residual_penalty_calibrator(
    predictions: pd.DataFrame,
    config: ResidualPenaltyConfig,
    *,
    long_column: str,
    short_column: str,
) -> ResidualPenaltyCalibrator:
    validate_residual_penalty_inputs(predictions, config, long_column, short_column)

    side_stats: dict[str, ResidualPenaltyStats] = {}
    group_stats: dict[str, dict[tuple[str, ...], ResidualPenaltyStats]] = {}
    keys = group_key_series(predictions, config.group_columns)
    candidate_masks = (
        candidate_entry_side_masks(
            predictions,
            config,
            long_column=long_column,
            short_column=short_column,
        )
        if config.candidate_entry_only
        else {
            "long": pd.Series(True, index=predictions.index),
            "short": pd.Series(True, index=predictions.index),
        }
    )
    for side_name, score_column in [("long", long_column), ("short", short_column)]:
        target_column = SIDE_COLUMNS[side_name]["target"]
        side_mask = candidate_masks[side_name]
        side_frame = (
            pd.DataFrame(
                {
                    "pred": predictions[score_column].astype(float),
                    "target": predictions[target_column].astype(float),
                    "key": keys,
                }
            )
            .loc[side_mask]
            .replace([np.inf, -np.inf], np.nan)
            .dropna(subset=["pred", "target"])
        )
        if side_frame.empty:
            raise ValueError(f"no valid rows for {side_name} residual penalty")
        side_stat = residual_penalty_stat(side_frame["pred"], side_frame["target"])
        side_stats[side_name] = side_stat
        group_stats[side_name] = {}
        for key, group in side_frame.groupby("key", sort=False):
            group_count = int(len(group))
            if group_count < config.min_group_size:
                continue
            if config.prior_strength == 0:
                weight = 1.0
            else:
                weight = group_count / (group_count + config.prior_strength)
            raw_stat = residual_penalty_stat(group["pred"], group["target"])
            group_stats[side_name][key] = shrink_residual_penalty_stats(raw_stat, side_stat, weight)
    return ResidualPenaltyCalibrator(
        config=config,
        long_column=long_column,
        short_column=short_column,
        side_stats=side_stats,
        group_stats=group_stats,
    )


def residual_penalty_stats_frame(
    predictions: pd.DataFrame,
    side_name: str,
    calibrator: ResidualPenaltyCalibrator,
) -> pd.DataFrame:
    side_stat = calibrator.side_stats[side_name]
    stats = pd.DataFrame(
        {
            "pred_mean": side_stat.pred_mean,
            "target_mean": side_stat.target_mean,
            "bias": side_stat.bias,
            "overestimate_mean": side_stat.overestimate_mean,
            "overestimate_rate": side_stat.overestimate_rate,
            "support": side_stat.n,
            "source": "side",
        },
        index=predictions.index,
    ).reset_index(drop=True)
    if calibrator.config.group_columns:
        keys = group_key_series(predictions, calibrator.config.group_columns).reset_index(drop=True)
        for key, group_stat in calibrator.group_stats[side_name].items():
            mask = keys == key
            if mask.any():
                stats.loc[mask, "pred_mean"] = group_stat.pred_mean
                stats.loc[mask, "target_mean"] = group_stat.target_mean
                stats.loc[mask, "bias"] = group_stat.bias
                stats.loc[mask, "overestimate_mean"] = group_stat.overestimate_mean
                stats.loc[mask, "overestimate_rate"] = group_stat.overestimate_rate
                stats.loc[mask, "support"] = group_stat.n
                stats.loc[mask, "source"] = "group"
    return stats


def residual_penalty_values(
    predictions: pd.DataFrame,
    side_name: str,
    calibrator: ResidualPenaltyCalibrator,
) -> tuple[pd.Series, pd.Series, pd.Series, pd.DataFrame]:
    score_column, _ = residual_side_columns(calibrator, side_name)
    raw = predictions[score_column].astype(float).reset_index(drop=True)
    stats = residual_penalty_stats_frame(predictions, side_name, calibrator)
    side_overestimate = calibrator.side_stats[side_name].overestimate_mean
    excess = (
        stats["overestimate_mean"].astype(float)
        - side_overestimate
        - calibrator.config.min_excess_overestimate
    ).clip(lower=0.0)
    penalty = calibrator.config.penalty_weight * excess
    penalized = raw - penalty
    return (
        pd.Series(penalized.to_numpy(), index=predictions.index),
        pd.Series(penalty.to_numpy(), index=predictions.index),
        pd.Series(excess.to_numpy(), index=predictions.index),
        stats,
    )


def add_residual_penalty_columns(
    predictions: pd.DataFrame,
    calibrator: ResidualPenaltyCalibrator,
) -> pd.DataFrame:
    output = predictions.copy()
    for side_name in ("long", "short"):
        output_column = residual_penalty_output_column(side_name)
        penalized, penalty, excess, stats = residual_penalty_values(output, side_name, calibrator)
        output[output_column] = penalized
        output[f"{output_column}_penalty"] = penalty
        output[f"{output_column}_excess_overestimate"] = excess
        output[f"{output_column}_overestimate_mean"] = pd.Series(
            stats["overestimate_mean"].to_numpy(),
            index=predictions.index,
        )
        output[f"{output_column}_side_overestimate_mean"] = calibrator.side_stats[
            side_name
        ].overestimate_mean
        output[f"{output_column}_bias"] = pd.Series(stats["bias"].to_numpy(), index=predictions.index)
        output[f"{output_column}_support"] = pd.Series(
            stats["support"].to_numpy(),
            index=predictions.index,
        )
        output[f"{output_column}_source"] = pd.Series(
            stats["source"].to_numpy(),
            index=predictions.index,
        )
    return output


def residual_penalty_scored_metrics(
    predictions: pd.DataFrame,
    *,
    long_column: str,
    short_column: str,
    entry_threshold: float,
) -> dict[str, object]:
    long_output = residual_penalty_output_column("long")
    short_output = residual_penalty_output_column("short")
    metrics: dict[str, object] = {
        "raw_selection": selection_metrics(
            predictions,
            threshold=entry_threshold,
            long_column=long_column,
            short_column=short_column,
        ),
        "penalized_selection": selection_metrics(
            predictions,
            threshold=entry_threshold,
            long_column=long_output,
            short_column=short_output,
        ),
        "long_penalized": regression_metrics(
            predictions[SIDE_COLUMNS["long"]["target"]],
            predictions[long_output].to_numpy(),
        ),
        "short_penalized": regression_metrics(
            predictions[SIDE_COLUMNS["short"]["target"]],
            predictions[short_output].to_numpy(),
        ),
        "penalty_mean": {
            "long": float(predictions[f"{long_output}_penalty"].mean()),
            "short": float(predictions[f"{short_output}_penalty"].mean()),
        },
        "penalty_positive_rate": {
            "long": float((predictions[f"{long_output}_penalty"] > 0).mean()),
            "short": float((predictions[f"{short_output}_penalty"] > 0).mean()),
        },
    }
    return metrics


def serializable_residual_penalty_calibrator(
    calibrator: ResidualPenaltyCalibrator,
) -> dict[str, object]:
    return {
        "config": asdict(calibrator.config),
        "long_column": calibrator.long_column,
        "short_column": calibrator.short_column,
        "side_stats": {side: asdict(stats) for side, stats in calibrator.side_stats.items()},
        "group_stats": {
            side: {
                "|".join(key): asdict(stats)
                for key, stats in side_groups.items()
            }
            for side, side_groups in calibrator.group_stats.items()
        },
    }


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
    long_overestimate = (
        output[TRADE_SOURCE_LONG_EV_COLUMN].astype(float) - output[TRADE_QUALITY_LONG_COLUMN].astype(float)
    ).clip(lower=0.0)
    short_overestimate = (
        output[TRADE_SOURCE_SHORT_EV_COLUMN].astype(float) - output[TRADE_QUALITY_SHORT_COLUMN].astype(float)
    ).clip(lower=0.0)
    output[TRADE_QUALITY_LONG_OVERESTIMATE_COLUMN] = long_overestimate
    output[TRADE_QUALITY_SHORT_OVERESTIMATE_COLUMN] = short_overestimate
    output[TRADE_QUALITY_LONG_OVERESTIMATE_RISK_COLUMN] = -long_overestimate
    output[TRADE_QUALITY_SHORT_OVERESTIMATE_RISK_COLUMN] = -short_overestimate
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
    if "dataset_month" in predictions.columns:
        output["dataset_month"] = predictions["dataset_month"].astype(str)
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


def trade_failure_prob_column(target_name: str, side_name: str) -> str:
    return f"pred_trade_failure_{target_name}_{side_name}_prob"


def trade_failure_risk_column(target_name: str, side_name: str) -> str:
    return f"pred_trade_failure_{target_name}_{side_name}_risk"


def trade_failure_taken_prob_column(target_name: str) -> str:
    return f"pred_trade_failure_{target_name}_taken_prob"


def validate_trade_failure_targets(target_names: tuple[str, ...]) -> None:
    unknown = sorted(set(target_names) - set(TRADE_FAILURE_TARGET_NAMES))
    if unknown:
        raise ValueError(f"unknown trade failure targets: {', '.join(unknown)}")


def trade_failure_targets_from_enriched(
    enriched: pd.DataFrame,
    config: TradeFailureModelConfig,
) -> pd.DataFrame:
    validate_trade_failure_targets(config.target_names)
    adjusted = finite_float_series(enriched, "adjusted_pnl")
    exit_regret = finite_float_series(enriched, "exit_regret")
    targets = pd.DataFrame(index=enriched.index)
    targets["large_loss"] = adjusted <= -config.large_loss_threshold
    targets["wrong_side"] = enriched["direction_error"].fillna(False).astype(bool)
    targets["profit_barrier_miss"] = finite_float_series(
        enriched,
        "actual_taken_profit_barrier_hit",
        default=0.0,
    ) < 0.5
    targets["exit_regret_high"] = exit_regret >= config.exit_regret_threshold
    targets["any_failure"] = targets[
        ["large_loss", "wrong_side", "profit_barrier_miss", "exit_regret_high"]
    ].any(axis=1)
    return targets.loc[:, list(config.target_names)].astype(int)


def build_trade_failure_training_frame(
    enriched: pd.DataFrame,
    config: TradeFailureModelConfig,
) -> pd.DataFrame:
    frame = trade_quality_features_from_enriched(enriched).drop(columns=["target"])
    targets = trade_failure_targets_from_enriched(enriched, config)
    frame = pd.concat([frame, targets], axis=1)
    return frame.replace([np.inf, -np.inf], np.nan).dropna(subset=list(config.target_names))


def fit_trade_failure_model(
    enriched: pd.DataFrame,
    config: TradeFailureModelConfig,
) -> TradeFailureModelBundle:
    if not 0.0 <= config.prediction_shrinkage <= 1.0:
        raise ValueError("prediction_shrinkage must be in [0, 1]")
    if config.large_loss_threshold < 0:
        raise ValueError("large_loss_threshold must be non-negative")
    if config.exit_regret_threshold < 0:
        raise ValueError("exit_regret_threshold must be non-negative")
    validate_trade_failure_targets(config.target_names)
    frame = build_trade_failure_training_frame(enriched, config)
    if frame.empty:
        raise ValueError("trade failure model training frame is empty")
    mappings = category_mappings(frame, TRADE_QUALITY_CATEGORY_FEATURE_COLUMNS)
    encoded = encode_trade_quality_features(frame, mappings)
    feature_columns = trade_quality_feature_columns(encoded)
    models: dict[str, HistGradientBoostingClassifier | None] = {}
    target_means: dict[str, float] = {}
    for index, target_name in enumerate(config.target_names):
        target = frame[target_name].astype(int)
        target_means[target_name] = float(target.mean())
        if target.nunique(dropna=True) < 2:
            models[target_name] = None
            continue
        model = HistGradientBoostingClassifier(
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
            random_state=config.random_seed + index,
        )
        weight_frame = frame.assign(target=target)
        model.fit(
            encoded[feature_columns].astype("float32").to_numpy(),
            target.to_numpy(dtype="int8"),
            sample_weight=trade_quality_sample_weights(weight_frame, config.sample_weighting),
        )
        models[target_name] = model
    return TradeFailureModelBundle(
        config=config,
        models=models,
        feature_columns=feature_columns,
        category_mappings=mappings,
        target_means=target_means,
    )


def predict_trade_failure_features(
    raw_features: pd.DataFrame,
    bundle: TradeFailureModelBundle,
    target_name: str,
) -> np.ndarray:
    if target_name not in bundle.target_means:
        raise ValueError(f"unknown fitted trade failure target: {target_name}")
    model = bundle.models.get(target_name)
    if model is None:
        probabilities = np.full(len(raw_features), bundle.target_means[target_name], dtype="float64")
    else:
        encoded = encode_trade_quality_features(raw_features, bundle.category_mappings)
        classes = list(model.classes_)
        positive_index = classes.index(1) if 1 in classes else None
        if positive_index is None:
            probabilities = np.full(len(raw_features), bundle.target_means[target_name], dtype="float64")
        else:
            probabilities = model.predict_proba(
                encoded[bundle.feature_columns].astype("float32").to_numpy()
            )[:, positive_index]
    if bundle.config.prediction_shrinkage < 1.0:
        probabilities = (
            bundle.config.prediction_shrinkage * probabilities
            + (1.0 - bundle.config.prediction_shrinkage) * bundle.target_means[target_name]
        )
    return np.clip(probabilities, 0.0, 1.0)


def add_trade_failure_model_columns(
    predictions: pd.DataFrame,
    bundle: TradeFailureModelBundle,
) -> pd.DataFrame:
    output = predictions.copy()
    for side_name in ("long", "short"):
        features = trade_quality_features_from_predictions(output, side_name)
        for target_name in bundle.config.target_names:
            probability = predict_trade_failure_features(features, bundle, target_name)
            prob_column = trade_failure_prob_column(target_name, side_name)
            output[prob_column] = probability
            output[trade_failure_risk_column(target_name, side_name)] = -output[prob_column]
    return output


def add_trade_failure_model_values_to_enriched(
    enriched: pd.DataFrame,
    bundle: TradeFailureModelBundle,
) -> pd.DataFrame:
    output = enriched.copy()
    targets = trade_failure_targets_from_enriched(output, bundle.config)
    features = trade_quality_features_from_enriched(output)
    for target_name in bundle.config.target_names:
        output[f"trade_failure_{target_name}"] = targets[target_name].astype(int)
        output[trade_failure_taken_prob_column(target_name)] = predict_trade_failure_features(
            features,
            bundle,
            target_name,
        )
    return output


def trade_failure_scored_metrics(scored: pd.DataFrame, target_names: tuple[str, ...]) -> dict[str, object]:
    if scored.empty:
        return {
            target_name: {
                "trade_count": 0,
                "prevalence": 0.0,
                "predicted_mean": 0.0,
                "bias": 0.0,
                "brier": 0.0,
                "auc": 0.5,
            }
            for target_name in target_names
        }
    metrics: dict[str, object] = {}
    for target_name in target_names:
        target_column = f"trade_failure_{target_name}"
        pred_column = trade_failure_taken_prob_column(target_name)
        y_true = scored[target_column].astype(int)
        y_pred = scored[pred_column].astype(float).clip(0.0, 1.0)
        if y_true.nunique(dropna=True) >= 2:
            auc = float(roc_auc_score(y_true, y_pred))
        else:
            auc = 0.5
        metrics[target_name] = {
            "trade_count": int(len(scored)),
            "prevalence": float(y_true.mean()),
            "predicted_mean": float(y_pred.mean()),
            "bias": float(y_pred.mean() - y_true.mean()),
            "brier": float(brier_score_loss(y_true, y_pred)),
            "auc": auc,
        }
    return metrics


def validate_candidate_failure_targets(target_names: tuple[str, ...]) -> None:
    unknown = sorted(set(target_names) - set(CANDIDATE_FAILURE_TARGET_NAMES))
    if unknown:
        raise ValueError(f"unknown candidate failure targets: {', '.join(unknown)}")


def candidate_failure_target_column(target_name: str) -> str:
    return f"candidate_failure_{target_name}"


def candidate_failure_prob_column(target_name: str, side_name: str) -> str:
    return f"pred_candidate_failure_{target_name}_{side_name}_prob"


def candidate_failure_risk_column(target_name: str, side_name: str) -> str:
    return f"pred_candidate_failure_{target_name}_{side_name}_risk"


def candidate_failure_taken_prob_column(target_name: str) -> str:
    return f"pred_candidate_failure_{target_name}_taken_prob"


def candidate_failure_mask_config(config: CandidateFailureModelConfig) -> ResidualPenaltyConfig:
    return ResidualPenaltyConfig(
        group_columns=(),
        min_group_size=1,
        prior_strength=0.0,
        penalty_weight=0.0,
        candidate_entry_only=True,
        entry_threshold=config.entry_threshold,
        long_entry_threshold_offset=config.long_entry_threshold_offset,
        short_entry_threshold_offset=config.short_entry_threshold_offset,
        side_margin=config.side_margin,
        min_entry_rank=config.min_entry_rank,
        long_entry_rank_column=config.long_entry_rank_column,
        short_entry_rank_column=config.short_entry_rank_column,
    )


def candidate_failure_targets_from_predictions(
    predictions: pd.DataFrame,
    side_name: str,
    config: CandidateFailureModelConfig,
) -> pd.DataFrame:
    validate_candidate_failure_targets(config.target_names)
    actual_adverse_column = f"{side_name}_max_adverse_pnl"
    if actual_adverse_column not in predictions.columns:
        raise ValueError(f"predictions missing candidate target column: {actual_adverse_column}")
    actual_adverse = finite_float_series(predictions, actual_adverse_column)
    large_adverse = actual_adverse <= -config.large_adverse_threshold
    targets = pd.DataFrame(index=predictions.index)
    if "large_adverse" in config.target_names:
        targets[candidate_failure_target_column("large_adverse")] = large_adverse
    needs_adjusted = bool(
        {
            "large_loss",
            "wrong_side",
            "range_normal_vol_selected_failure",
            "normal_vol_selected_failure",
            "time_session_selected_failure",
            "any_failure",
        }.intersection(config.target_names)
    )
    if not needs_adjusted:
        return targets.astype(int)

    actual_adjusted = finite_float_series(predictions, SIDE_COLUMNS[side_name]["target"])
    selected_loss = actual_adjusted <= 0.0
    large_loss = actual_adjusted <= -config.large_loss_threshold
    if "large_loss" in config.target_names:
        targets[candidate_failure_target_column("large_loss")] = large_loss
    if "wrong_side" in config.target_names or "any_failure" in config.target_names:
        opposite_adjusted = finite_float_series(predictions, SIDE_COLUMNS[side_name]["opposite_target"])
        wrong_side = opposite_adjusted > actual_adjusted
    else:
        wrong_side = pd.Series(False, index=predictions.index)
    if "wrong_side" in config.target_names:
        targets[candidate_failure_target_column("wrong_side")] = wrong_side

    if (
        "range_normal_vol_selected_failure" in config.target_names
        or "normal_vol_selected_failure" in config.target_names
        or "any_failure" in config.target_names
    ):
        combined_regime = predictions["combined_regime"].astype("string").fillna("__missing__")
        range_normal_failure = (combined_regime == "range_normal_vol") & selected_loss
        normal_vol_failure = combined_regime.str.endswith("_normal_vol").fillna(False) & selected_loss
    else:
        range_normal_failure = pd.Series(False, index=predictions.index)
        normal_vol_failure = pd.Series(False, index=predictions.index)
    if "range_normal_vol_selected_failure" in config.target_names:
        targets[candidate_failure_target_column("range_normal_vol_selected_failure")] = (
            range_normal_failure
        )
    if "normal_vol_selected_failure" in config.target_names:
        targets[candidate_failure_target_column("normal_vol_selected_failure")] = normal_vol_failure
    if "time_session_selected_failure" in config.target_names or "any_failure" in config.target_names:
        session_regime = predictions["session_regime"].astype("string").fillna("__missing__")
        time_session_failure = session_regime.isin(["rollover", "ny_late"]) & selected_loss
    else:
        time_session_failure = pd.Series(False, index=predictions.index)
    if "time_session_selected_failure" in config.target_names:
        targets[candidate_failure_target_column("time_session_selected_failure")] = (
            time_session_failure
        )
    if "any_failure" in config.target_names:
        targets[candidate_failure_target_column("any_failure")] = (
            large_adverse
            | large_loss
            | wrong_side
            | range_normal_failure
            | normal_vol_failure
            | time_session_failure
        )
    return targets.astype(int)


def build_candidate_failure_training_frame(
    predictions: pd.DataFrame,
    config: CandidateFailureModelConfig,
    *,
    long_column: str,
    short_column: str,
) -> pd.DataFrame:
    validate_candidate_failure_targets(config.target_names)
    required_columns = {
        long_column,
        short_column,
        "long_max_adverse_pnl",
        "short_max_adverse_pnl",
    }
    targets_requiring_adjusted = {
        "large_loss",
        "wrong_side",
        "range_normal_vol_selected_failure",
        "normal_vol_selected_failure",
        "time_session_selected_failure",
        "any_failure",
    }
    if targets_requiring_adjusted.intersection(config.target_names):
        required_columns.update(
            {
                SIDE_COLUMNS["long"]["target"],
                SIDE_COLUMNS["short"]["target"],
            }
        )
    targets_requiring_combined_regime = {
        "range_normal_vol_selected_failure",
        "normal_vol_selected_failure",
        "any_failure",
    }
    if targets_requiring_combined_regime.intersection(config.target_names):
        required_columns.add("combined_regime")
    if {"time_session_selected_failure", "any_failure"}.intersection(config.target_names):
        required_columns.add("session_regime")
    if config.min_entry_rank > 0:
        required_columns.update(
            {
                config.long_entry_rank_column,
                config.short_entry_rank_column,
            }
        )
    missing_columns = sorted(required_columns - set(predictions.columns))
    if missing_columns:
        raise ValueError(f"predictions missing candidate failure columns: {', '.join(missing_columns)}")

    masks = candidate_entry_side_masks(
        predictions,
        candidate_failure_mask_config(config),
        long_column=long_column,
        short_column=short_column,
    )
    frames: list[pd.DataFrame] = []
    for side_name in ("long", "short"):
        side_predictions = predictions.loc[masks[side_name]].copy()
        if side_predictions.empty:
            continue
        features = trade_quality_features_from_predictions(side_predictions, side_name)
        features["candidate_side"] = side_name
        features["candidate_source_index"] = side_predictions.index.astype(str)
        if "decision_timestamp" in side_predictions.columns:
            features["decision_timestamp"] = side_predictions["decision_timestamp"]
        actual_adverse = finite_float_series(side_predictions, f"{side_name}_max_adverse_pnl")
        features["candidate_actual_max_adverse_pnl"] = actual_adverse
        targets = candidate_failure_targets_from_predictions(side_predictions, side_name, config)
        frames.append(pd.concat([features, targets], axis=1))

    if not frames:
        return pd.DataFrame()
    target_columns = [candidate_failure_target_column(target_name) for target_name in config.target_names]
    frame = pd.concat(frames, ignore_index=True)
    return frame.replace([np.inf, -np.inf], np.nan).dropna(subset=target_columns)


def fit_candidate_failure_model_from_frame(
    frame: pd.DataFrame,
    config: CandidateFailureModelConfig,
) -> CandidateFailureModelBundle:
    if not 0.0 <= config.prediction_shrinkage <= 1.0:
        raise ValueError("prediction_shrinkage must be in [0, 1]")
    if config.large_adverse_threshold < 0:
        raise ValueError("large_adverse_threshold must be non-negative")
    if config.large_loss_threshold < 0:
        raise ValueError("large_loss_threshold must be non-negative")
    validate_candidate_failure_targets(config.target_names)
    if frame.empty:
        raise ValueError("candidate failure model training frame is empty")

    mappings = category_mappings(frame, TRADE_QUALITY_CATEGORY_FEATURE_COLUMNS)
    encoded = encode_trade_quality_features(frame, mappings)
    feature_columns = trade_quality_feature_columns(encoded)
    models: dict[str, HistGradientBoostingClassifier | None] = {}
    target_means: dict[str, float] = {}
    for index, target_name in enumerate(config.target_names):
        target_column = candidate_failure_target_column(target_name)
        target = frame[target_column].astype(int)
        target_means[target_name] = float(target.mean())
        if target.nunique(dropna=True) < 2:
            models[target_name] = None
            continue
        model = HistGradientBoostingClassifier(
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
            random_state=config.random_seed + index,
        )
        weight_frame = frame.assign(target=target)
        model.fit(
            encoded[feature_columns].astype("float32").to_numpy(),
            target.to_numpy(dtype="int8"),
            sample_weight=trade_quality_sample_weights(weight_frame, config.sample_weighting),
        )
        models[target_name] = model
    return CandidateFailureModelBundle(
        config=config,
        models=models,
        feature_columns=feature_columns,
        category_mappings=mappings,
        target_means=target_means,
    )


def fit_candidate_failure_model(
    predictions: pd.DataFrame,
    config: CandidateFailureModelConfig,
    *,
    long_column: str,
    short_column: str,
) -> CandidateFailureModelBundle:
    frame = build_candidate_failure_training_frame(
        predictions,
        config,
        long_column=long_column,
        short_column=short_column,
    )
    return fit_candidate_failure_model_from_frame(frame, config)


def predict_candidate_failure_features(
    raw_features: pd.DataFrame,
    bundle: CandidateFailureModelBundle,
    target_name: str,
) -> np.ndarray:
    if target_name not in bundle.target_means:
        raise ValueError(f"unknown fitted candidate failure target: {target_name}")
    model = bundle.models.get(target_name)
    if model is None:
        probabilities = np.full(len(raw_features), bundle.target_means[target_name], dtype="float64")
    else:
        encoded = encode_trade_quality_features(raw_features, bundle.category_mappings)
        classes = list(model.classes_)
        positive_index = classes.index(1) if 1 in classes else None
        if positive_index is None:
            probabilities = np.full(len(raw_features), bundle.target_means[target_name], dtype="float64")
        else:
            probabilities = model.predict_proba(
                encoded[bundle.feature_columns].astype("float32").to_numpy()
            )[:, positive_index]
    if bundle.config.prediction_shrinkage < 1.0:
        probabilities = (
            bundle.config.prediction_shrinkage * probabilities
            + (1.0 - bundle.config.prediction_shrinkage) * bundle.target_means[target_name]
        )
    return np.clip(probabilities, 0.0, 1.0)


def add_candidate_failure_model_columns(
    predictions: pd.DataFrame,
    bundle: CandidateFailureModelBundle,
) -> pd.DataFrame:
    output = predictions.copy()
    for side_name in ("long", "short"):
        features = trade_quality_features_from_predictions(output, side_name)
        for target_name in bundle.config.target_names:
            probability = predict_candidate_failure_features(features, bundle, target_name)
            prob_column = candidate_failure_prob_column(target_name, side_name)
            output[prob_column] = probability
            output[candidate_failure_risk_column(target_name, side_name)] = -output[prob_column]
    return output


def add_candidate_failure_model_values_to_examples(
    examples: pd.DataFrame,
    bundle: CandidateFailureModelBundle,
) -> pd.DataFrame:
    output = examples.copy()
    for target_name in bundle.config.target_names:
        output[candidate_failure_taken_prob_column(target_name)] = predict_candidate_failure_features(
            output,
            bundle,
            target_name,
        )
    return output


def candidate_failure_scored_metrics(
    scored: pd.DataFrame,
    target_names: tuple[str, ...],
) -> dict[str, object]:
    if scored.empty:
        return {
            target_name: {
                "candidate_count": 0,
                "prevalence": 0.0,
                "predicted_mean": 0.0,
                "bias": 0.0,
                "brier": 0.0,
                "auc": 0.5,
            }
            for target_name in target_names
        }
    metrics: dict[str, object] = {}
    for target_name in target_names:
        target_column = candidate_failure_target_column(target_name)
        pred_column = candidate_failure_taken_prob_column(target_name)
        y_true = scored[target_column].astype(int)
        y_pred = scored[pred_column].astype(float).clip(0.0, 1.0)
        if y_true.nunique(dropna=True) >= 2:
            auc = float(roc_auc_score(y_true, y_pred))
        else:
            auc = 0.5
        metrics[target_name] = {
            "candidate_count": int(len(scored)),
            "prevalence": float(y_true.mean()),
            "predicted_mean": float(y_pred.mean()),
            "bias": float(y_pred.mean() - y_true.mean()),
            "brier": float(brier_score_loss(y_true, y_pred)),
            "auc": auc,
        }
    return metrics


def candidate_quality_mask_config(config: CandidateQualityModelConfig) -> ResidualPenaltyConfig:
    return ResidualPenaltyConfig(
        group_columns=(),
        min_group_size=1,
        prior_strength=0.0,
        penalty_weight=0.0,
        candidate_entry_only=True,
        entry_threshold=config.entry_threshold,
        long_entry_threshold_offset=config.long_entry_threshold_offset,
        short_entry_threshold_offset=config.short_entry_threshold_offset,
        side_margin=config.side_margin,
        min_entry_rank=config.min_entry_rank,
        long_entry_rank_column=config.long_entry_rank_column,
        short_entry_rank_column=config.short_entry_rank_column,
    )


def time_exit_target_column(
    predictions: pd.DataFrame,
    side_name: str,
    time_exit_target_minutes: int,
) -> str:
    forced_column = f"{side_name}_forced_adjusted_pnl"
    fixed_column = f"{side_name}_fixed_{time_exit_target_minutes}m_adjusted_pnl"
    return forced_column if forced_column in predictions.columns else fixed_column


def validate_joint_exit_target_config(config: CandidateQualityModelConfig) -> None:
    if config.time_exit_target_minutes <= 0:
        raise ValueError("time_exit_target_minutes must be positive")
    if not 0.0 <= config.joint_time_decay <= 1.0:
        raise ValueError("joint_time_decay must be in [0, 1]")
    if config.joint_component_clip_multiple <= 0:
        raise ValueError("joint_component_clip_multiple must be positive")
    if any(minutes <= 0 for minutes in config.joint_fixed_horizon_minutes):
        raise ValueError("joint_fixed_horizon_minutes must contain positive values")
    if config.joint_fixed_horizon_weight > 0 and not config.joint_fixed_horizon_minutes:
        raise ValueError("joint_fixed_horizon_minutes is required when joint_fixed_horizon_weight > 0")
    weights = (
        config.joint_barrier_weight,
        config.joint_fixed_horizon_weight,
        config.joint_best_weight,
    )
    if any(weight < 0 for weight in weights):
        raise ValueError("joint target weights must be non-negative")
    if sum(weights) <= 0:
        raise ValueError("at least one joint target weight must be positive")


def joint_component_clip_value(config: CandidateQualityModelConfig) -> float:
    if config.joint_component_clip_multiple <= 0:
        raise ValueError("joint_component_clip_multiple must be positive")
    return config.min_adjusted_edge * config.joint_component_clip_multiple


def clipped_candidate_component(component: pd.Series, config: CandidateQualityModelConfig) -> pd.Series:
    clip_value = joint_component_clip_value(config)
    return component.astype(float).clip(lower=-clip_value, upper=clip_value)


def candidate_barrier_event_target(
    side_predictions: pd.DataFrame,
    side_name: str,
    config: CandidateQualityModelConfig,
    *,
    time_decay: float = 0.0,
) -> tuple[pd.Series, pd.Series, str]:
    exit_event = side_predictions[f"{side_name}_exit_event"].astype(float)
    time_exit_column = time_exit_target_column(
        side_predictions,
        side_name,
        config.time_exit_target_minutes,
    )
    time_exit_adjusted = finite_float_series(side_predictions, time_exit_column)
    if time_decay > 0:
        minutes = finite_float_series(side_predictions, f"{side_name}_exit_event_minutes")
        speed = (minutes / float(config.time_exit_target_minutes)).clip(lower=0.0, upper=1.0)
        edge_multiplier = 1.0 - time_decay * speed
    else:
        edge_multiplier = pd.Series(1.0, index=side_predictions.index, dtype="float64")
    target = np.select(
        [
            exit_event == CANDIDATE_EXIT_EVENT_PROFIT,
            exit_event == CANDIDATE_EXIT_EVENT_LOSS,
            exit_event == CANDIDATE_EXIT_EVENT_TIME,
        ],
        [
            config.min_adjusted_edge * edge_multiplier,
            -config.min_adjusted_edge * edge_multiplier,
            time_exit_adjusted,
        ],
        default=np.nan,
    )
    return pd.Series(target, index=side_predictions.index), time_exit_adjusted, time_exit_column


def candidate_timed_barrier_component(
    side_predictions: pd.DataFrame,
    side_name: str,
    config: CandidateQualityModelConfig,
) -> pd.Series:
    if not 0.0 <= config.joint_time_decay <= 1.0:
        raise ValueError("joint_time_decay must be in [0, 1]")
    component, _, _ = candidate_barrier_event_target(
        side_predictions,
        side_name,
        config,
        time_decay=config.joint_time_decay,
    )
    return clipped_candidate_component(component, config)


def candidate_fixed_horizon_component(
    side_predictions: pd.DataFrame,
    side_name: str,
    config: CandidateQualityModelConfig,
) -> pd.Series:
    if any(minutes <= 0 for minutes in config.joint_fixed_horizon_minutes):
        raise ValueError("joint_fixed_horizon_minutes must contain positive values")
    if not config.joint_fixed_horizon_minutes:
        raise ValueError("joint_fixed_horizon_minutes is required")
    fixed_columns = [
        f"{side_name}_fixed_{minutes}m_adjusted_pnl"
        for minutes in config.joint_fixed_horizon_minutes
    ]
    component = side_predictions[fixed_columns].astype(float).mean(axis=1)
    return clipped_candidate_component(component, config)


def candidate_joint_exit_target(
    side_predictions: pd.DataFrame,
    side_name: str,
    config: CandidateQualityModelConfig,
    actual_adjusted_pnl: pd.Series,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    validate_joint_exit_target_config(config)
    barrier_component = candidate_timed_barrier_component(
        side_predictions,
        side_name,
        config,
    )
    fixed_component = candidate_fixed_horizon_component(side_predictions, side_name, config)
    best_component = clipped_candidate_component(actual_adjusted_pnl, config)
    total_weight = (
        config.joint_barrier_weight
        + config.joint_fixed_horizon_weight
        + config.joint_best_weight
    )
    target = (
        config.joint_barrier_weight * barrier_component
        + config.joint_fixed_horizon_weight * fixed_component
        + config.joint_best_weight * best_component
    ) / total_weight
    return target, barrier_component, fixed_component


def build_candidate_quality_training_frame(
    predictions: pd.DataFrame,
    config: CandidateQualityModelConfig,
    *,
    long_column: str,
    short_column: str,
) -> pd.DataFrame:
    if config.target_mode not in CANDIDATE_QUALITY_TARGET_MODES:
        raise ValueError(f"unknown candidate quality target mode: {config.target_mode}")
    if config.min_adjusted_edge <= 0:
        raise ValueError("min_adjusted_edge must be positive")
    required_columns = {
        long_column,
        short_column,
        SIDE_COLUMNS["long"]["target"],
        SIDE_COLUMNS["short"]["target"],
    }
    if config.target_mode in BARRIER_COMPONENT_TARGET_MODES:
        required_columns.update({"long_exit_event", "short_exit_event"})
        if config.target_mode != "barrier_event_adjusted_pnl":
            required_columns.update({"long_exit_event_minutes", "short_exit_event_minutes"})
        for side_name in ("long", "short"):
            time_exit_column = time_exit_target_column(
                predictions,
                side_name,
                config.time_exit_target_minutes,
            )
            required_columns.add(time_exit_column)
    if config.target_mode in FIXED_HORIZON_COMPONENT_TARGET_MODES:
        for side_name in ("long", "short"):
            for minutes in config.joint_fixed_horizon_minutes:
                required_columns.add(f"{side_name}_fixed_{minutes}m_adjusted_pnl")
    if config.min_entry_rank > 0:
        required_columns.update(
            {
                config.long_entry_rank_column,
                config.short_entry_rank_column,
            }
        )
    missing_columns = sorted(required_columns - set(predictions.columns))
    if missing_columns:
        raise ValueError(f"predictions missing candidate quality columns: {', '.join(missing_columns)}")

    masks = candidate_entry_side_masks(
        predictions,
        candidate_quality_mask_config(config),
        long_column=long_column,
        short_column=short_column,
    )
    frames: list[pd.DataFrame] = []
    for side_name in ("long", "short"):
        side_predictions = predictions.loc[masks[side_name]].copy()
        if side_predictions.empty:
            continue
        features = trade_quality_features_from_predictions(side_predictions, side_name)
        features["candidate_side"] = side_name
        features["candidate_source_index"] = side_predictions.index.astype(str)
        if "decision_timestamp" in side_predictions.columns:
            features["decision_timestamp"] = side_predictions["decision_timestamp"]
        target_column = SIDE_COLUMNS[side_name]["target"]
        features["candidate_actual_adjusted_pnl"] = finite_float_series(
            side_predictions,
            target_column,
        )
        if f"{side_name}_exit_event" in side_predictions.columns:
            features["candidate_actual_exit_event"] = side_predictions[f"{side_name}_exit_event"].astype(
                float
            )
        if f"{side_name}_exit_event_minutes" in side_predictions.columns:
            features["candidate_actual_exit_event_minutes"] = finite_float_series(
                side_predictions,
                f"{side_name}_exit_event_minutes",
            )
        if f"{side_name}_forced_adjusted_pnl" in side_predictions.columns:
            features["candidate_actual_forced_adjusted_pnl"] = finite_float_series(
                side_predictions,
                f"{side_name}_forced_adjusted_pnl",
            )
        if config.target_mode in BARRIER_COMPONENT_TARGET_MODES:
            barrier_target, time_exit_adjusted, time_exit_column = candidate_barrier_event_target(
                side_predictions,
                side_name,
                config,
            )
            features["candidate_actual_time_exit_adjusted_pnl"] = time_exit_adjusted
            features["candidate_actual_time_exit_source"] = time_exit_column
            features["candidate_actual_barrier_target"] = barrier_target
            if config.target_mode == "barrier_event_adjusted_pnl":
                features["target"] = barrier_target
            else:
                features["candidate_actual_timed_barrier_component"] = candidate_timed_barrier_component(
                    side_predictions,
                    side_name,
                    config,
                )
        if config.target_mode in FIXED_HORIZON_COMPONENT_TARGET_MODES:
            features["candidate_actual_fixed_horizon_component"] = candidate_fixed_horizon_component(
                side_predictions,
                side_name,
                config,
            )
        if config.target_mode == "timed_barrier_component_adjusted_pnl":
            features["target"] = features["candidate_actual_timed_barrier_component"]
        elif config.target_mode == "fixed_horizon_component_adjusted_pnl":
            features["target"] = features["candidate_actual_fixed_horizon_component"]
        elif config.target_mode == "clipped_best_adjusted_pnl":
            features["target"] = clipped_candidate_component(
                features["candidate_actual_adjusted_pnl"],
                config,
            )
        elif config.target_mode == "joint_exit_adjusted_pnl":
            joint_target, timed_barrier_component, fixed_component = candidate_joint_exit_target(
                side_predictions,
                side_name,
                config,
                features["candidate_actual_adjusted_pnl"],
            )
            features["candidate_actual_timed_barrier_component"] = timed_barrier_component
            features["candidate_actual_fixed_horizon_component"] = fixed_component
            features["target"] = joint_target
        elif config.target_mode == "barrier_event_adjusted_pnl":
            pass
        else:
            features["target"] = features["candidate_actual_adjusted_pnl"]
        frames.append(features)

    if not frames:
        return pd.DataFrame()
    frame = pd.concat(frames, ignore_index=True)
    return frame.replace([np.inf, -np.inf], np.nan).dropna(subset=["target"])


def fit_candidate_quality_model_from_frame(
    frame: pd.DataFrame,
    config: CandidateQualityModelConfig,
) -> CandidateQualityModelBundle:
    if frame.empty:
        raise ValueError("candidate quality model training frame is empty")
    if not 0.0 <= config.prediction_shrinkage <= 1.0:
        raise ValueError("prediction_shrinkage must be in [0, 1]")
    if not 0.0 < config.lower_quantile < 0.5:
        raise ValueError("lower_quantile must be in (0, 0.5)")
    if config.target_mode not in CANDIDATE_QUALITY_TARGET_MODES:
        raise ValueError(f"unknown candidate quality target mode: {config.target_mode}")

    mappings = category_mappings(frame, TRADE_QUALITY_CATEGORY_FEATURE_COLUMNS)
    encoded = encode_trade_quality_features(frame, mappings)
    feature_columns = trade_quality_feature_columns(encoded)
    x = encoded[feature_columns].astype("float32").to_numpy()
    y = clipped_target(frame["target"], config.target_clip_quantile)
    sample_weight = trade_quality_sample_weights(frame, config.sample_weighting)

    mean_model = HistGradientBoostingRegressor(
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
    mean_model.fit(x, y, sample_weight=sample_weight)

    lower_model = HistGradientBoostingRegressor(
        loss="quantile",
        quantile=config.lower_quantile,
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
        random_state=config.random_seed + 101,
    )
    lower_model.fit(x, y, sample_weight=sample_weight)

    return CandidateQualityModelBundle(
        config=config,
        mean_model=mean_model,
        lower_model=lower_model,
        feature_columns=feature_columns,
        category_mappings=mappings,
        target_mean=float(frame["target"].mean()),
        lower_target_mean=float(frame["target"].quantile(config.lower_quantile)),
    )


def fit_candidate_quality_model(
    predictions: pd.DataFrame,
    config: CandidateQualityModelConfig,
    *,
    long_column: str,
    short_column: str,
) -> CandidateQualityModelBundle:
    frame = build_candidate_quality_training_frame(
        predictions,
        config,
        long_column=long_column,
        short_column=short_column,
    )
    return fit_candidate_quality_model_from_frame(frame, config)


def predict_candidate_quality_features(
    raw_features: pd.DataFrame,
    bundle: CandidateQualityModelBundle,
    *,
    lower: bool = False,
) -> np.ndarray:
    encoded = encode_trade_quality_features(raw_features, bundle.category_mappings)
    model = bundle.lower_model if lower else bundle.mean_model
    predictions = model.predict(encoded[bundle.feature_columns].astype("float32").to_numpy())
    if bundle.config.prediction_shrinkage < 1.0:
        center = bundle.lower_target_mean if lower else bundle.target_mean
        predictions = bundle.config.prediction_shrinkage * predictions + (
            1.0 - bundle.config.prediction_shrinkage
        ) * center
    return predictions


def validate_candidate_quality_prediction_prefix(prefix: str) -> str:
    normalized = prefix.strip()
    if not normalized:
        return ""
    if re.fullmatch(r"[A-Za-z0-9_]+", normalized) is None:
        raise ValueError("prediction_prefix must contain only letters, digits, and underscores")
    return normalized


def candidate_quality_columns_for_side(
    side_name: str,
    prediction_prefix: str = "",
) -> tuple[str, str, str, str]:
    prefix = validate_candidate_quality_prediction_prefix(prediction_prefix)
    if not prefix:
        if side_name == "long":
            return (
                CANDIDATE_QUALITY_LONG_COLUMN,
                CANDIDATE_QUALITY_LONG_LOWER_COLUMN,
                CANDIDATE_QUALITY_LONG_OVERESTIMATE_RISK_COLUMN,
                CANDIDATE_QUALITY_LONG_LOWER_OVERESTIMATE_RISK_COLUMN,
            )
        return (
            CANDIDATE_QUALITY_SHORT_COLUMN,
            CANDIDATE_QUALITY_SHORT_LOWER_COLUMN,
            CANDIDATE_QUALITY_SHORT_OVERESTIMATE_RISK_COLUMN,
            CANDIDATE_QUALITY_SHORT_LOWER_OVERESTIMATE_RISK_COLUMN,
        )

    base = f"pred_candidate_quality_{prefix}_{side_name}"
    return (
        f"{base}_adjusted_pnl",
        f"{base}_lower_adjusted_pnl",
        f"{base}_overestimate_risk",
        f"{base}_lower_overestimate_risk",
    )


def combine_candidate_quality_values(
    values: pd.DataFrame,
    mode: str,
    weights: list[float] | None = None,
) -> pd.Series:
    numeric = values.astype(float)
    complete_rows = ~numeric.isna().any(axis=1)
    if mode == "mean":
        combined = numeric.mean(axis=1)
    elif mode == "min":
        combined = numeric.min(axis=1)
    elif mode == "max":
        combined = numeric.max(axis=1)
    elif mode == "weighted_mean":
        if weights is None:
            raise ValueError("weights are required for weighted_mean")
        if len(weights) != numeric.shape[1]:
            raise ValueError("weights length must match component count")
        weight_array = np.asarray(weights, dtype=float)
        if (weight_array < 0).any() or weight_array.sum() <= 0:
            raise ValueError("weights must be non-negative and sum to a positive value")
        normalized_weights = weight_array / weight_array.sum()
        combined = pd.Series(
            numeric.to_numpy(dtype=float) @ normalized_weights,
            index=numeric.index,
        )
    else:
        raise ValueError(f"unknown candidate quality component combine mode: {mode}")
    return combined.where(complete_rows)


def combine_candidate_quality_component_columns(
    predictions: pd.DataFrame,
    component_prefixes: list[str],
    output_prefix: str,
    mode: str = "mean",
    weights: list[float] | None = None,
) -> pd.DataFrame:
    prefixes = [
        validate_candidate_quality_prediction_prefix(prefix) for prefix in component_prefixes
    ]
    if not prefixes:
        raise ValueError("at least one component prefix is required")
    if any(not prefix for prefix in prefixes):
        raise ValueError("component prefixes must be non-empty")
    normalized_output_prefix = validate_candidate_quality_prediction_prefix(output_prefix)
    if not normalized_output_prefix:
        raise ValueError("output prefix must be non-empty")

    missing = sorted(
        {TRADE_SOURCE_LONG_EV_COLUMN, TRADE_SOURCE_SHORT_EV_COLUMN} - set(predictions.columns)
    )
    for side_name in ("long", "short"):
        for prefix in prefixes:
            missing.extend(
                column
                for column in candidate_quality_columns_for_side(side_name, prefix)[:2]
                if column not in predictions.columns
            )
    if missing:
        raise ValueError(
            "predictions missing candidate quality component columns: "
            f"{', '.join(sorted(set(missing)))}"
        )

    output = predictions.copy()
    for side_name in ("long", "short"):
        quality_column, lower_column, risk_column, lower_risk_column = candidate_quality_columns_for_side(
            side_name,
            normalized_output_prefix,
        )
        component_quality_columns = [
            candidate_quality_columns_for_side(side_name, prefix)[0] for prefix in prefixes
        ]
        component_lower_columns = [
            candidate_quality_columns_for_side(side_name, prefix)[1] for prefix in prefixes
        ]
        output[quality_column] = combine_candidate_quality_values(
            output[component_quality_columns],
            mode,
            weights,
        )
        output[lower_column] = combine_candidate_quality_values(
            output[component_lower_columns],
            mode,
            weights,
        )
        source_column = (
            TRADE_SOURCE_LONG_EV_COLUMN
            if side_name == "long"
            else TRADE_SOURCE_SHORT_EV_COLUMN
        )
        overestimate = (
            output[source_column].astype(float) - output[quality_column].astype(float)
        ).clip(lower=0.0)
        lower_overestimate = (
            output[source_column].astype(float) - output[lower_column].astype(float)
        ).clip(lower=0.0)
        output[risk_column] = -overestimate
        output[lower_risk_column] = -lower_overestimate
    return output


def add_candidate_quality_model_columns(
    predictions: pd.DataFrame,
    bundle: CandidateQualityModelBundle,
) -> pd.DataFrame:
    missing = sorted(
        {TRADE_SOURCE_LONG_EV_COLUMN, TRADE_SOURCE_SHORT_EV_COLUMN} - set(predictions.columns)
    )
    if missing:
        raise ValueError(f"predictions missing trade source columns: {', '.join(missing)}")
    output = predictions.copy()
    for side_name in ("long", "short"):
        quality_column, lower_column, risk_column, lower_risk_column = (
            candidate_quality_columns_for_side(side_name, bundle.config.prediction_prefix)
        )
        source_column = TRADE_SOURCE_LONG_EV_COLUMN if side_name == "long" else TRADE_SOURCE_SHORT_EV_COLUMN
        features = trade_quality_features_from_predictions(output, side_name)
        output[quality_column] = predict_candidate_quality_features(features, bundle, lower=False)
        output[lower_column] = predict_candidate_quality_features(features, bundle, lower=True)
        overestimate = (
            output[source_column].astype(float) - output[quality_column].astype(float)
        ).clip(lower=0.0)
        lower_overestimate = (
            output[source_column].astype(float) - output[lower_column].astype(float)
        ).clip(lower=0.0)
        output[risk_column] = -overestimate
        output[lower_risk_column] = -lower_overestimate
    return output


def add_candidate_quality_model_values_to_examples(
    examples: pd.DataFrame,
    bundle: CandidateQualityModelBundle,
) -> pd.DataFrame:
    output = examples.copy()
    output[CANDIDATE_QUALITY_TAKEN_COLUMN] = predict_candidate_quality_features(
        output,
        bundle,
        lower=False,
    )
    output[CANDIDATE_QUALITY_TAKEN_LOWER_COLUMN] = predict_candidate_quality_features(
        output,
        bundle,
        lower=True,
    )
    return output


def candidate_quality_scored_metrics(scored: pd.DataFrame) -> dict[str, float]:
    if scored.empty:
        return {
            "candidate_count": 0,
            "raw_bias": 0.0,
            "mean_bias": 0.0,
            "lower_bias": 0.0,
            "raw_overestimate_mean": 0.0,
            "mean_overestimate_mean": 0.0,
            "lower_overestimate_mean": 0.0,
            "mean_mae": 0.0,
            "mean_rmse": 0.0,
            "mean_r2": 0.0,
            "lower_coverage": 0.0,
        }
    target = finite_float_series(scored, "target")
    raw_pred = finite_float_series(scored, "pred_taken_ev")
    mean_pred = finite_float_series(scored, CANDIDATE_QUALITY_TAKEN_COLUMN)
    lower_pred = finite_float_series(scored, CANDIDATE_QUALITY_TAKEN_LOWER_COLUMN)
    raw_error = raw_pred - target
    mean_error = mean_pred - target
    lower_error = lower_pred - target
    mean_r2 = float(r2_score(target, mean_pred)) if len(scored) >= 2 else 0.0
    metrics = {
        "candidate_count": int(len(scored)),
        "target_mean": float(target.mean()),
        "raw_predicted_mean": float(raw_pred.mean()),
        "mean_predicted_mean": float(mean_pred.mean()),
        "lower_predicted_mean": float(lower_pred.mean()),
        "raw_bias": float(raw_error.mean()),
        "mean_bias": float(mean_error.mean()),
        "lower_bias": float(lower_error.mean()),
        "raw_overestimate_mean": float(raw_error.clip(lower=0).mean()),
        "mean_overestimate_mean": float(mean_error.clip(lower=0).mean()),
        "lower_overestimate_mean": float(lower_error.clip(lower=0).mean()),
        "mean_mae": float(mean_absolute_error(target, mean_pred)),
        "mean_rmse": float(mean_squared_error(target, mean_pred) ** 0.5),
        "mean_r2": mean_r2,
        "lower_coverage": float((lower_pred <= target).mean()),
    }
    if "candidate_actual_exit_event" in scored.columns:
        event_counts = scored["candidate_actual_exit_event"].value_counts(dropna=False).sort_index()
        for event, count in event_counts.items():
            if pd.isna(event):
                key = "nan"
            else:
                key = str(int(event))
            metrics[f"exit_event_{key}_count"] = int(count)
    return metrics


def candidate_quality_threshold_suffix(threshold: float) -> str:
    text = f"{threshold:g}".replace("-", "neg").replace(".", "p")
    return f"le_{text}"


def prepare_candidate_quality_report_frame(
    examples: pd.DataFrame,
    *,
    target_column: str = "target",
    raw_prediction_column: str = "pred_taken_ev",
    mean_prediction_column: str = CANDIDATE_QUALITY_TAKEN_COLUMN,
    lower_prediction_column: str = CANDIDATE_QUALITY_TAKEN_LOWER_COLUMN,
) -> pd.DataFrame:
    required_columns = {
        target_column,
        raw_prediction_column,
        mean_prediction_column,
        lower_prediction_column,
    }
    missing = sorted(required_columns - set(examples.columns))
    if missing:
        raise ValueError(f"candidate quality examples missing columns: {', '.join(missing)}")
    output = examples.copy()
    output["_target"] = pd.to_numeric(output[target_column], errors="coerce")
    output["_raw_pred"] = pd.to_numeric(output[raw_prediction_column], errors="coerce")
    output["_mean_pred"] = pd.to_numeric(output[mean_prediction_column], errors="coerce")
    output["_lower_pred"] = pd.to_numeric(output[lower_prediction_column], errors="coerce")
    output = output.replace([np.inf, -np.inf], np.nan).dropna(
        subset=["_target", "_raw_pred", "_mean_pred", "_lower_pred"]
    )
    output["_raw_error"] = output["_raw_pred"] - output["_target"]
    output["_mean_error"] = output["_mean_pred"] - output["_target"]
    output["_lower_error"] = output["_lower_pred"] - output["_target"]
    output["_raw_overestimate"] = output["_raw_error"].clip(lower=0.0)
    output["_mean_overestimate"] = output["_mean_error"].clip(lower=0.0)
    output["_lower_overestimate"] = output["_lower_error"].clip(lower=0.0)
    output["_lower_covered"] = output["_lower_pred"] <= output["_target"]
    return output


def candidate_quality_distribution_metrics(
    frame: pd.DataFrame,
    downside_thresholds: tuple[float, ...] = (0.0, -15.0),
) -> dict[str, float]:
    if frame.empty:
        metrics = {
            "support": 0,
            "target_mean": 0.0,
            "target_std": 0.0,
            "target_q10": 0.0,
            "target_q25": 0.0,
            "target_median": 0.0,
            "raw_predicted_mean": 0.0,
            "mean_predicted_mean": 0.0,
            "lower_predicted_mean": 0.0,
            "raw_bias": 0.0,
            "mean_bias": 0.0,
            "lower_bias": 0.0,
            "raw_overestimate_mean": 0.0,
            "mean_overestimate_mean": 0.0,
            "lower_overestimate_mean": 0.0,
            "mean_mae": 0.0,
            "lower_coverage": 0.0,
        }
        for threshold in downside_thresholds:
            suffix = candidate_quality_threshold_suffix(threshold)
            metrics[f"target_rate_{suffix}"] = 0.0
            metrics[f"raw_pred_rate_{suffix}"] = 0.0
            metrics[f"mean_pred_rate_{suffix}"] = 0.0
            metrics[f"lower_pred_rate_{suffix}"] = 0.0
        return metrics

    metrics = {
        "support": int(len(frame)),
        "target_mean": float(frame["_target"].mean()),
        "target_std": float(frame["_target"].std(ddof=0)),
        "target_q10": float(frame["_target"].quantile(0.10)),
        "target_q25": float(frame["_target"].quantile(0.25)),
        "target_median": float(frame["_target"].median()),
        "raw_predicted_mean": float(frame["_raw_pred"].mean()),
        "mean_predicted_mean": float(frame["_mean_pred"].mean()),
        "lower_predicted_mean": float(frame["_lower_pred"].mean()),
        "raw_bias": float(frame["_raw_error"].mean()),
        "mean_bias": float(frame["_mean_error"].mean()),
        "lower_bias": float(frame["_lower_error"].mean()),
        "raw_overestimate_mean": float(frame["_raw_overestimate"].mean()),
        "mean_overestimate_mean": float(frame["_mean_overestimate"].mean()),
        "lower_overestimate_mean": float(frame["_lower_overestimate"].mean()),
        "mean_mae": float(frame["_mean_error"].abs().mean()),
        "lower_coverage": float(frame["_lower_covered"].mean()),
    }
    for threshold in downside_thresholds:
        suffix = candidate_quality_threshold_suffix(threshold)
        metrics[f"target_rate_{suffix}"] = float((frame["_target"] <= threshold).mean())
        metrics[f"raw_pred_rate_{suffix}"] = float((frame["_raw_pred"] <= threshold).mean())
        metrics[f"mean_pred_rate_{suffix}"] = float((frame["_mean_pred"] <= threshold).mean())
        metrics[f"lower_pred_rate_{suffix}"] = float((frame["_lower_pred"] <= threshold).mean())
    return metrics


def parse_groupings(value: str | None) -> list[tuple[str, ...]]:
    if value is None:
        return []
    groupings: list[tuple[str, ...]] = []
    for raw_grouping in value.split(";"):
        columns = tuple(parse_csv_strings(raw_grouping))
        if columns:
            groupings.append(columns)
    return groupings


def candidate_quality_group_metrics(
    frame: pd.DataFrame,
    groupings: list[tuple[str, ...]],
    *,
    downside_thresholds: tuple[float, ...] = (0.0, -15.0),
    min_support: int = 1,
) -> pd.DataFrame:
    overall = candidate_quality_distribution_metrics(frame, downside_thresholds)
    rows: list[dict[str, object]] = []
    for grouping in groupings:
        missing = [column for column in grouping if column not in frame.columns]
        if missing:
            continue
        grouping_name = ",".join(grouping)
        for key, group in frame.groupby(list(grouping), dropna=False, sort=True, observed=False):
            if len(group) < min_support:
                continue
            key_tuple = key if isinstance(key, tuple) else (key,)
            metrics = candidate_quality_distribution_metrics(group, downside_thresholds)
            row: dict[str, object] = {
                "grouping": grouping_name,
                "group_key": "|".join("__missing__" if pd.isna(value) else str(value) for value in key_tuple),
            }
            for column, value in zip(grouping, key_tuple, strict=True):
                row[column] = "__missing__" if pd.isna(value) else value
            row.update(metrics)
            row["target_mean_shift"] = row["target_mean"] - overall["target_mean"]
            row["mean_bias_shift"] = row["mean_bias"] - overall["mean_bias"]
            row["lower_coverage_shift"] = row["lower_coverage"] - overall["lower_coverage"]
            if 0.0 in downside_thresholds:
                suffix = candidate_quality_threshold_suffix(0.0)
                row[f"target_rate_{suffix}_shift"] = (
                    row[f"target_rate_{suffix}"] - overall[f"target_rate_{suffix}"]
                )
            rows.append(row)
    return pd.DataFrame(rows)


def candidate_quality_bucket_metrics(
    frame: pd.DataFrame,
    *,
    score_column: str = "_mean_pred",
    bucket_count: int = 10,
    group_columns: tuple[str, ...] = (),
    downside_thresholds: tuple[float, ...] = (0.0, -15.0),
    min_support: int = 1,
) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame()
    if score_column not in frame.columns:
        raise ValueError(f"unknown candidate quality score column: {score_column}")
    if bucket_count < 2:
        raise ValueError("bucket_count must be at least 2")
    missing_groups = [column for column in group_columns if column not in frame.columns]
    if missing_groups:
        raise ValueError(f"candidate quality bucket groups missing columns: {', '.join(missing_groups)}")
    output = frame.copy()
    bucket_total = min(bucket_count, len(output))
    labels = [f"q{index + 1:02d}" for index in range(bucket_total)]
    ranks = output[score_column].rank(method="first")
    output["_quality_score_bucket"] = pd.qcut(ranks, q=bucket_total, labels=labels)
    grouping_columns = [*group_columns, "_quality_score_bucket"]
    rows: list[dict[str, object]] = []
    for key, group in output.groupby(grouping_columns, dropna=False, sort=True, observed=False):
        if len(group) < min_support:
            continue
        key_tuple = key if isinstance(key, tuple) else (key,)
        metrics = candidate_quality_distribution_metrics(group, downside_thresholds)
        row: dict[str, object] = {
            "score_column": score_column,
            "bucket": str(key_tuple[-1]),
            "score_min": float(group[score_column].min()),
            "score_max": float(group[score_column].max()),
        }
        for column, value in zip(grouping_columns[:-1], key_tuple[:-1], strict=True):
            row[column] = "__missing__" if pd.isna(value) else value
        row.update(metrics)
        rows.append(row)
    return pd.DataFrame(rows)


def candidate_quality_report_cli(args: argparse.Namespace) -> int:
    examples = pd.read_csv(args.examples)
    downside_thresholds = tuple(parse_csv_floats(args.downside_thresholds) or [0.0, -15.0])
    frame = prepare_candidate_quality_report_frame(
        examples,
        target_column=args.target_column,
        raw_prediction_column=args.raw_prediction_column,
        mean_prediction_column=args.mean_prediction_column,
        lower_prediction_column=args.lower_prediction_column,
    )
    groupings = parse_groupings(args.groupings)
    if not groupings:
        groupings = [
            ("dataset_month",),
            ("candidate_side",),
            ("combined_regime",),
            ("session_regime",),
            ("dataset_month", "candidate_side"),
            ("dataset_month", "combined_regime"),
            ("dataset_month", "session_regime"),
        ]
    used_groupings = [
        grouping for grouping in groupings if all(column in frame.columns for column in grouping)
    ]
    skipped_groupings = [
        grouping for grouping in groupings if any(column not in frame.columns for column in grouping)
    ]
    bucket_group_columns = tuple(
        column for column in parse_csv_strings(args.bucket_group_columns) if column in frame.columns
    )
    bucket_score_map = {
        "raw": "_raw_pred",
        "mean": "_mean_pred",
        "lower": "_lower_pred",
    }
    if args.bucket_score not in bucket_score_map:
        raise ValueError("bucket_score must be raw, mean, or lower")

    overall = candidate_quality_distribution_metrics(frame, downside_thresholds)
    group_metrics = candidate_quality_group_metrics(
        frame,
        used_groupings,
        downside_thresholds=downside_thresholds,
        min_support=args.min_group_support,
    )
    bucket_metrics = candidate_quality_bucket_metrics(
        frame,
        score_column=bucket_score_map[args.bucket_score],
        bucket_count=args.bucket_count,
        group_columns=bucket_group_columns,
        downside_thresholds=downside_thresholds,
        min_support=args.min_group_support,
    )

    run_dir = make_run_dir(args.output_dir, args.label)
    pd.DataFrame([overall]).to_csv(run_dir / "overall_metrics.csv", index=False)
    group_metrics.to_csv(run_dir / "group_metrics.csv", index=False)
    bucket_metrics.to_csv(run_dir / "bucket_metrics.csv", index=False)

    worst_downside_rows: list[dict[str, object]] = []
    worst_overestimate_rows: list[dict[str, object]] = []
    if not group_metrics.empty:
        downside_column = f"target_rate_{candidate_quality_threshold_suffix(0.0)}"
        worst_downside_rows = (
            group_metrics.sort_values([downside_column, "support"], ascending=[False, False])
            .head(args.summary_rows)
            .to_dict(orient="records")
        )
        worst_overestimate_rows = (
            group_metrics.sort_values(["mean_overestimate_mean", "support"], ascending=[False, False])
            .head(args.summary_rows)
            .to_dict(orient="records")
        )
    summary = {
        "mode": "candidate_quality_report",
        "examples": str(args.examples),
        "rows": {
            "input": int(len(examples)),
            "usable": int(len(frame)),
            "group_metrics": int(len(group_metrics)),
            "bucket_metrics": int(len(bucket_metrics)),
        },
        "columns": {
            "target": args.target_column,
            "raw_prediction": args.raw_prediction_column,
            "mean_prediction": args.mean_prediction_column,
            "lower_prediction": args.lower_prediction_column,
        },
        "downside_thresholds": list(downside_thresholds),
        "groupings": {
            "used": [list(grouping) for grouping in used_groupings],
            "skipped": [list(grouping) for grouping in skipped_groupings],
        },
        "bucket": {
            "score": args.bucket_score,
            "score_column": bucket_score_map[args.bucket_score],
            "count": args.bucket_count,
            "group_columns": list(bucket_group_columns),
        },
        "overall": overall,
        "worst_downside_groups": worst_downside_rows,
        "worst_overestimate_groups": worst_overestimate_rows,
    }
    with (run_dir / "summary.json").open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2, default=str)
    print(json.dumps({"overall": overall, "artifacts": str(run_dir)}, indent=2))
    return 0


def candidate_quality_downside_base(side_name: str, output_prefix: str) -> str:
    prefix = validate_candidate_quality_prediction_prefix(output_prefix)
    if not prefix:
        raise ValueError("output prefix must be non-empty")
    return f"pred_candidate_quality_{prefix}_{side_name}"


def candidate_quality_downside_columns_for_side(side_name: str, output_prefix: str) -> dict[str, str]:
    base = candidate_quality_downside_base(side_name, output_prefix)
    return {
        "calibrated_mean": f"{base}_calibrated_target_mean",
        "calibrated_lower": f"{base}_calibrated_target_lower",
        "downside_prob": f"{base}_downside_prob",
        "large_downside_prob": f"{base}_large_downside_prob",
        "overestimate": f"{base}_overestimate",
        "lower_overestimate": f"{base}_lower_overestimate",
        "overestimate_risk": f"{base}_overestimate_risk",
        "downside_risk": f"{base}_downside_risk",
        "large_downside_risk": f"{base}_large_downside_risk",
        "support": f"{base}_support",
        "source": f"{base}_source",
        "quality_bucket": f"{base}_quality_bucket",
    }


def quality_bucket_edges(values: pd.Series, bucket_count: int) -> tuple[float, ...]:
    if bucket_count < 2:
        raise ValueError("bucket_count must be at least 2")
    numeric = pd.to_numeric(values, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    if numeric.empty:
        return (-np.inf, np.inf)
    quantiles = np.linspace(0.0, 1.0, bucket_count + 1)
    edges = np.unique(np.quantile(numeric.to_numpy(dtype=float), quantiles))
    if len(edges) < 2:
        value = float(edges[0])
        edges = np.asarray([value - 1e-9, value + 1e-9], dtype=float)
    edges = edges.astype(float)
    edges[0] = -np.inf
    edges[-1] = np.inf
    return tuple(float(edge) for edge in edges)


def assign_quality_score_buckets(values: pd.Series, edges: tuple[float, ...]) -> pd.Series:
    if len(edges) < 2:
        raise ValueError("bucket edges must contain at least two values")
    labels = [f"q{index + 1:02d}" for index in range(len(edges) - 1)]
    numeric = pd.to_numeric(values, errors="coerce").replace([np.inf, -np.inf], np.nan)
    buckets = pd.cut(numeric, bins=list(edges), labels=labels, include_lowest=True)
    return buckets.astype("string").fillna("__missing__")


def normalize_candidate_quality_group_columns(frame: pd.DataFrame, columns: tuple[str, ...]) -> pd.DataFrame:
    output = pd.DataFrame(index=frame.index)
    for column in columns:
        if column not in frame.columns:
            raise ValueError(f"candidate quality calibration missing group column: {column}")
        output[column] = frame[column].astype("string").fillna("__missing__")
    return output


def candidate_quality_downside_raw_stats(
    frame: pd.DataFrame,
    *,
    downside_threshold: float,
    large_downside_threshold: float,
) -> dict[str, float]:
    if frame.empty:
        return {
            "support": 0.0,
            "target_mean": 0.0,
            "target_std": 0.0,
            "target_standard_error": 0.0,
            "downside_prob": 0.0,
            "large_downside_prob": 0.0,
            "mean_overestimate": 0.0,
            "lower_overestimate": 0.0,
            "lower_coverage": 0.0,
        }
    target = frame["_target"].astype(float)
    target_std_value = target_std(target)
    return {
        "support": float(len(frame)),
        "target_mean": float(target.mean()),
        "target_std": target_std_value,
        "target_standard_error": target_standard_error(target),
        "downside_prob": float((target <= downside_threshold).mean()),
        "large_downside_prob": float((target <= large_downside_threshold).mean()),
        "mean_overestimate": float(frame["_mean_overestimate"].mean()),
        "lower_overestimate": float(frame["_lower_overestimate"].mean()),
        "lower_coverage": float(frame["_lower_covered"].mean()),
    }


def smooth_candidate_quality_downside_stats(
    raw_stats: dict[str, float],
    prior_stats: dict[str, float],
    prior_strength: float,
) -> dict[str, float]:
    if prior_strength < 0:
        raise ValueError("prior_strength must be non-negative")
    support = raw_stats["support"]
    if support + prior_strength <= 0:
        return dict(raw_stats)
    smoothed = dict(raw_stats)
    for key in [
        "target_mean",
        "downside_prob",
        "large_downside_prob",
        "mean_overestimate",
        "lower_overestimate",
        "lower_coverage",
    ]:
        smoothed[key] = float(
            (support * raw_stats[key] + prior_strength * prior_stats[key])
            / (support + prior_strength)
        )
    return smoothed


def finalized_candidate_quality_downside_stats(
    stats: dict[str, float],
    *,
    lower_z: float,
) -> dict[str, float]:
    output = dict(stats)
    output["calibrated_lower"] = float(
        output["target_mean"] - lower_z * output["target_standard_error"]
    )
    output["overestimate_risk"] = -float(max(output["mean_overestimate"], 0.0))
    output["downside_risk"] = -float(max(output["downside_prob"], 0.0))
    output["large_downside_risk"] = -float(max(output["large_downside_prob"], 0.0))
    return output


def fit_candidate_quality_downside_calibrator(
    examples: pd.DataFrame,
    *,
    input_prediction_prefix: str,
    output_prefix: str,
    group_columns: tuple[str, ...] = ("combined_regime",),
    bucket_count: int = 10,
    min_group_size: int = 20,
    prior_strength: float = 50.0,
    lower_z: float = 1.0,
    downside_threshold: float = 0.0,
    large_downside_threshold: float = -15.0,
    target_column: str = "target",
    raw_prediction_column: str = "pred_taken_ev",
    mean_prediction_column: str = CANDIDATE_QUALITY_TAKEN_COLUMN,
    lower_prediction_column: str = CANDIDATE_QUALITY_TAKEN_LOWER_COLUMN,
) -> CandidateQualityDownsideCalibrationBundle:
    if min_group_size < 1:
        raise ValueError("min_group_size must be positive")
    if lower_z < 0:
        raise ValueError("lower_z must be non-negative")
    frame = prepare_candidate_quality_report_frame(
        examples,
        target_column=target_column,
        raw_prediction_column=raw_prediction_column,
        mean_prediction_column=mean_prediction_column,
        lower_prediction_column=lower_prediction_column,
    )
    if "candidate_side" not in frame.columns:
        raise ValueError("candidate quality examples missing candidate_side")
    normalized_groups = normalize_candidate_quality_group_columns(frame, group_columns)
    for column in group_columns:
        frame[column] = normalized_groups[column]
    frame["candidate_side"] = frame["candidate_side"].astype("string").fillna("__missing__")
    edges = quality_bucket_edges(frame["_mean_pred"], bucket_count)
    frame["_quality_score_bucket"] = assign_quality_score_buckets(frame["_mean_pred"], edges)

    raw_global = candidate_quality_downside_raw_stats(
        frame,
        downside_threshold=downside_threshold,
        large_downside_threshold=large_downside_threshold,
    )
    global_stats = finalized_candidate_quality_downside_stats(raw_global, lower_z=lower_z)
    side_stats: dict[str, dict[str, float]] = {}
    for side_name, group in frame.groupby("candidate_side", dropna=False, observed=False):
        raw_side = candidate_quality_downside_raw_stats(
            group,
            downside_threshold=downside_threshold,
            large_downside_threshold=large_downside_threshold,
        )
        side_stats[str(side_name)] = finalized_candidate_quality_downside_stats(
            raw_side,
            lower_z=lower_z,
        )

    key_columns = ["candidate_side", *group_columns, "_quality_score_bucket"]
    group_stats: dict[tuple[str, ...], dict[str, float]] = {}
    for key, group in frame.groupby(key_columns, dropna=False, observed=False):
        if len(group) < min_group_size:
            continue
        key_tuple = tuple(str(value) for value in (key if isinstance(key, tuple) else (key,)))
        side_name = key_tuple[0]
        prior_stats = side_stats.get(side_name, global_stats)
        raw_group = candidate_quality_downside_raw_stats(
            group,
            downside_threshold=downside_threshold,
            large_downside_threshold=large_downside_threshold,
        )
        smoothed = smooth_candidate_quality_downside_stats(
            raw_group,
            prior_stats,
            prior_strength,
        )
        group_stats[key_tuple] = finalized_candidate_quality_downside_stats(
            smoothed,
            lower_z=lower_z,
        )

    return CandidateQualityDownsideCalibrationBundle(
        input_prediction_prefix=validate_candidate_quality_prediction_prefix(input_prediction_prefix),
        output_prefix=validate_candidate_quality_prediction_prefix(output_prefix),
        group_columns=group_columns,
        bucket_edges=edges,
        min_group_size=min_group_size,
        prior_strength=prior_strength,
        lower_z=lower_z,
        downside_threshold=downside_threshold,
        large_downside_threshold=large_downside_threshold,
        global_stats=global_stats,
        side_stats=side_stats,
        group_stats=group_stats,
    )


def candidate_quality_downside_stats_frame(
    bundle: CandidateQualityDownsideCalibrationBundle,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    rows.append({"source": "global", "key": "global", **bundle.global_stats})
    for side_name, stats in sorted(bundle.side_stats.items()):
        rows.append({"source": "side", "key": side_name, "candidate_side": side_name, **stats})
    for key, stats in sorted(bundle.group_stats.items()):
        row: dict[str, object] = {
            "source": "group",
            "key": "|".join(key),
            "candidate_side": key[0],
            "_quality_score_bucket": key[-1],
            **stats,
        }
        for column, value in zip(bundle.group_columns, key[1:-1], strict=True):
            row[column] = value
        rows.append(row)
    return pd.DataFrame(rows)


def candidate_quality_downside_output_frame(
    predictions: pd.DataFrame,
    side_name: str,
    bundle: CandidateQualityDownsideCalibrationBundle,
) -> pd.DataFrame:
    quality_column = candidate_quality_columns_for_side(
        side_name,
        bundle.input_prediction_prefix,
    )[0]
    missing = [quality_column, *[column for column in bundle.group_columns if column not in predictions.columns]]
    missing = [column for column in missing if column not in predictions.columns]
    if missing:
        raise ValueError(f"predictions missing candidate quality calibration columns: {', '.join(missing)}")

    quality_values = pd.to_numeric(predictions[quality_column], errors="coerce")
    buckets = assign_quality_score_buckets(quality_values, bundle.bucket_edges)
    group_values = normalize_candidate_quality_group_columns(predictions, bundle.group_columns)
    rows: list[dict[str, object]] = []
    for index in predictions.index:
        key = tuple(
            [
                side_name,
                *[str(group_values.loc[index, column]) for column in bundle.group_columns],
                str(buckets.loc[index]),
            ]
        )
        stats = bundle.group_stats.get(key)
        source = "group"
        if stats is None:
            stats = bundle.side_stats.get(side_name)
            source = "side"
        if stats is None:
            stats = bundle.global_stats
            source = "global"
        rows.append(
            {
                "calibrated_mean": stats["target_mean"],
                "calibrated_lower": stats["calibrated_lower"],
                "downside_prob": stats["downside_prob"],
                "large_downside_prob": stats["large_downside_prob"],
                "overestimate": stats["mean_overestimate"],
                "lower_overestimate": stats["lower_overestimate"],
                "overestimate_risk": stats["overestimate_risk"],
                "downside_risk": stats["downside_risk"],
                "large_downside_risk": stats["large_downside_risk"],
                "support": stats["support"],
                "source": source,
                "quality_bucket": str(buckets.loc[index]),
            }
        )
    return pd.DataFrame(rows, index=predictions.index)


def add_candidate_quality_downside_calibration_columns(
    predictions: pd.DataFrame,
    bundle: CandidateQualityDownsideCalibrationBundle,
) -> pd.DataFrame:
    output = predictions.copy()
    for side_name in ("long", "short"):
        values = candidate_quality_downside_output_frame(output, side_name, bundle)
        columns = candidate_quality_downside_columns_for_side(side_name, bundle.output_prefix)
        for key, column in columns.items():
            output[column] = values[key]
    return output


def add_candidate_quality_downside_calibration_oof_columns(
    predictions: pd.DataFrame,
    examples: pd.DataFrame,
    *,
    oof_column: str,
    input_prediction_prefix: str,
    output_prefix: str,
    group_columns: tuple[str, ...],
    bucket_count: int,
    min_group_size: int,
    prior_strength: float,
    lower_z: float,
    downside_threshold: float,
    large_downside_threshold: float,
) -> tuple[pd.DataFrame, dict[str, object]]:
    if oof_column not in predictions.columns:
        raise ValueError(f"predictions missing OOF column: {oof_column}")
    if oof_column not in examples.columns:
        raise ValueError(f"candidate quality examples missing OOF column: {oof_column}")
    output = predictions.copy()
    fold_metrics: dict[str, object] = {}
    output_columns = [
        column
        for side_name in ("long", "short")
        for column in candidate_quality_downside_columns_for_side(side_name, output_prefix).values()
    ]
    string_output_columns = {
        column
        for side_name in ("long", "short")
        for key, column in candidate_quality_downside_columns_for_side(side_name, output_prefix).items()
        if key in {"source", "quality_bucket"}
    }
    for column in output_columns:
        if column in string_output_columns:
            output[column] = pd.Series(pd.NA, index=output.index, dtype="string")
        else:
            output[column] = np.nan
    for value in sorted(str(item) for item in output[oof_column].dropna().astype(str).unique()):
        prediction_mask = output[oof_column].astype(str) == value
        fit_examples = examples[examples[oof_column].astype(str) != value]
        if fit_examples.empty:
            fit_examples = examples
        bundle = fit_candidate_quality_downside_calibrator(
            fit_examples,
            input_prediction_prefix=input_prediction_prefix,
            output_prefix=output_prefix,
            group_columns=group_columns,
            bucket_count=bucket_count,
            min_group_size=min_group_size,
            prior_strength=prior_strength,
            lower_z=lower_z,
            downside_threshold=downside_threshold,
            large_downside_threshold=large_downside_threshold,
        )
        scored = add_candidate_quality_downside_calibration_columns(
            output.loc[prediction_mask].copy(),
            bundle,
        )
        output.loc[prediction_mask, output_columns] = scored[output_columns]
        fold_metrics[value] = {
            "fit_examples": int(len(fit_examples)),
            "scored_predictions": int(prediction_mask.sum()),
            "group_stats": int(len(bundle.group_stats)),
            "bucket_edges": list(bundle.bucket_edges),
        }
    return output, fold_metrics


def candidate_quality_downside_calibration_cli(args: argparse.Namespace) -> int:
    examples = pd.read_csv(args.examples)
    predictions = pd.read_parquet(args.predictions)
    group_columns = tuple(parse_csv_strings(args.group_columns))
    output_prefix = validate_candidate_quality_prediction_prefix(args.output_prefix)
    input_prediction_prefix = validate_candidate_quality_prediction_prefix(args.input_prediction_prefix)
    if not output_prefix:
        raise ValueError("--output-prefix must be non-empty")
    if args.oof_column:
        output, fold_metrics = add_candidate_quality_downside_calibration_oof_columns(
            predictions,
            examples,
            oof_column=args.oof_column,
            input_prediction_prefix=input_prediction_prefix,
            output_prefix=output_prefix,
            group_columns=group_columns,
            bucket_count=args.bucket_count,
            min_group_size=args.min_group_support,
            prior_strength=args.prior_strength,
            lower_z=args.lower_z,
            downside_threshold=args.downside_threshold,
            large_downside_threshold=args.large_downside_threshold,
        )
    else:
        bundle = fit_candidate_quality_downside_calibrator(
            examples,
            input_prediction_prefix=input_prediction_prefix,
            output_prefix=output_prefix,
            group_columns=group_columns,
            bucket_count=args.bucket_count,
            min_group_size=args.min_group_support,
            prior_strength=args.prior_strength,
            lower_z=args.lower_z,
            downside_threshold=args.downside_threshold,
            large_downside_threshold=args.large_downside_threshold,
        )
        output = add_candidate_quality_downside_calibration_columns(predictions, bundle)
        fold_metrics = {}

    final_bundle = fit_candidate_quality_downside_calibrator(
        examples,
        input_prediction_prefix=input_prediction_prefix,
        output_prefix=output_prefix,
        group_columns=group_columns,
        bucket_count=args.bucket_count,
        min_group_size=args.min_group_support,
        prior_strength=args.prior_strength,
        lower_z=args.lower_z,
        downside_threshold=args.downside_threshold,
        large_downside_threshold=args.large_downside_threshold,
    )
    args.output_path.parent.mkdir(parents=True, exist_ok=True)
    output.to_parquet(args.output_path, index=False)
    stats_path = args.output_path.with_suffix(".calibration_stats.csv")
    candidate_quality_downside_stats_frame(final_bundle).to_csv(stats_path, index=False)
    output_columns = {
        side_name: candidate_quality_downside_columns_for_side(side_name, output_prefix)
        for side_name in ("long", "short")
    }
    metrics = {
        "mode": "candidate_quality_downside_calibration",
        "examples": str(args.examples),
        "predictions": str(args.predictions),
        "output_path": str(args.output_path),
        "stats_path": str(stats_path),
        "input_prediction_prefix": input_prediction_prefix,
        "output_prefix": output_prefix,
        "group_columns": list(group_columns),
        "bucket_count": args.bucket_count,
        "bucket_edges": list(final_bundle.bucket_edges),
        "min_group_support": args.min_group_support,
        "prior_strength": args.prior_strength,
        "lower_z": args.lower_z,
        "downside_threshold": args.downside_threshold,
        "large_downside_threshold": args.large_downside_threshold,
        "rows": {
            "examples": int(len(examples)),
            "predictions": int(len(predictions)),
            "output": int(len(output)),
            "group_stats": int(len(final_bundle.group_stats)),
        },
        "oof_column": args.oof_column,
        "folds": fold_metrics,
        "output_columns": output_columns,
    }
    metrics_path = args.output_path.with_suffix(".metrics.json")
    with metrics_path.open("w", encoding="utf-8") as handle:
        json.dump(metrics, handle, ensure_ascii=False, indent=2, default=str)
    print(json.dumps({"output": str(args.output_path), "metrics": str(metrics_path)}, indent=2))
    return 0


def read_table(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix == ".parquet":
        return pd.read_parquet(path)
    if suffix == ".csv":
        return pd.read_csv(path)
    raise ValueError(f"unsupported table format: {path}")


def entry_timing_base(side_name: str, output_prefix: str) -> str:
    prefix = validate_candidate_quality_prediction_prefix(output_prefix)
    if not prefix:
        raise ValueError("output prefix must be non-empty")
    return f"pred_entry_timing_{prefix}_{side_name}"


def entry_timing_columns_for_side(side_name: str, output_prefix: str) -> dict[str, str]:
    base = entry_timing_base(side_name, output_prefix)
    return {
        "calibrated_wait_regret": f"{base}_calibrated_wait_regret",
        "bad_wait_prob": f"{base}_bad_wait_prob",
        "wait_excess_mean": f"{base}_wait_excess_mean",
        "wait_underestimate_mean": f"{base}_wait_underestimate_mean",
        "bad_wait_prob_risk": f"{base}_bad_wait_prob_risk",
        "wait_excess_risk": f"{base}_wait_excess_risk",
        "wait_underestimate_risk": f"{base}_wait_underestimate_risk",
        "support": f"{base}_support",
        "source": f"{base}_source",
        "wait_regret_bucket": f"{base}_wait_regret_bucket",
    }


def entry_timing_side_examples(
    examples: pd.DataFrame,
    group_columns: tuple[str, ...],
) -> pd.DataFrame:
    missing = [column for column in group_columns if column not in examples.columns]
    for side_name, spec in SIDE_COLUMNS.items():
        missing.extend(
            column
            for column in (spec["wait_regret"], f"{side_name}_wait_regret")
            if column not in examples.columns
        )
    if missing:
        raise ValueError(f"entry timing examples missing columns: {', '.join(sorted(set(missing)))}")

    frames: list[pd.DataFrame] = []
    for side_name, spec in SIDE_COLUMNS.items():
        side_frame = pd.DataFrame(
            {
                "entry_side": side_name,
                "pred_wait_regret": pd.to_numeric(
                    examples[spec["wait_regret"]],
                    errors="coerce",
                ),
                "actual_wait_regret": pd.to_numeric(
                    examples[f"{side_name}_wait_regret"],
                    errors="coerce",
                ),
            }
        )
        for column in group_columns:
            side_frame[column] = examples[column].astype("string").fillna("__missing__")
        if "dataset_month" in examples.columns:
            side_frame["dataset_month"] = examples["dataset_month"].astype(str)
        frames.append(side_frame)
    frame = pd.concat(frames, ignore_index=True)
    return frame.replace([np.inf, -np.inf], np.nan).dropna(
        subset=["pred_wait_regret", "actual_wait_regret"]
    )


def entry_timing_raw_stats(
    frame: pd.DataFrame,
    *,
    bad_wait_threshold: float,
) -> dict[str, float]:
    if frame.empty:
        return {
            "support": 0.0,
            "pred_wait_regret_mean": 0.0,
            "actual_wait_regret_mean": 0.0,
            "bad_wait_prob": 0.0,
            "wait_excess_mean": 0.0,
            "wait_underestimate_mean": 0.0,
        }
    predicted = frame["pred_wait_regret"].astype(float)
    actual = frame["actual_wait_regret"].astype(float)
    return {
        "support": float(len(frame)),
        "pred_wait_regret_mean": float(predicted.mean()),
        "actual_wait_regret_mean": float(actual.mean()),
        "bad_wait_prob": float((actual > bad_wait_threshold).mean()),
        "wait_excess_mean": float((actual - bad_wait_threshold).clip(lower=0.0).mean()),
        "wait_underestimate_mean": float((actual - predicted).clip(lower=0.0).mean()),
    }


def smooth_entry_timing_stats(
    raw_stats: dict[str, float],
    prior_stats: dict[str, float],
    prior_strength: float,
) -> dict[str, float]:
    if prior_strength < 0:
        raise ValueError("prior_strength must be non-negative")
    support = raw_stats["support"]
    if support + prior_strength <= 0:
        return dict(raw_stats)
    smoothed = dict(raw_stats)
    for key in [
        "pred_wait_regret_mean",
        "actual_wait_regret_mean",
        "bad_wait_prob",
        "wait_excess_mean",
        "wait_underestimate_mean",
    ]:
        smoothed[key] = float(
            (support * raw_stats[key] + prior_strength * prior_stats[key])
            / (support + prior_strength)
        )
    return smoothed


def finalized_entry_timing_stats(stats: dict[str, float]) -> dict[str, float]:
    output = dict(stats)
    output["bad_wait_prob_risk"] = -float(max(output["bad_wait_prob"], 0.0))
    output["wait_excess_risk"] = -float(max(output["wait_excess_mean"], 0.0))
    output["wait_underestimate_risk"] = -float(max(output["wait_underestimate_mean"], 0.0))
    return output


def fit_entry_timing_calibrator(
    examples: pd.DataFrame,
    *,
    output_prefix: str,
    group_columns: tuple[str, ...] = ("combined_regime",),
    bucket_count: int = 10,
    min_group_size: int = 20,
    prior_strength: float = 50.0,
    bad_wait_threshold: float = 4.0,
) -> EntryTimingCalibrationBundle:
    if min_group_size < 1:
        raise ValueError("min_group_size must be positive")
    if prior_strength < 0:
        raise ValueError("prior_strength must be non-negative")
    output_prefix = validate_candidate_quality_prediction_prefix(output_prefix)
    if not output_prefix:
        raise ValueError("output prefix must be non-empty")
    frame = entry_timing_side_examples(examples, group_columns)
    if frame.empty:
        raise ValueError("entry timing examples are empty")
    edges = quality_bucket_edges(frame["pred_wait_regret"], bucket_count)
    frame["_wait_regret_bucket"] = assign_quality_score_buckets(frame["pred_wait_regret"], edges)

    raw_global = entry_timing_raw_stats(frame, bad_wait_threshold=bad_wait_threshold)
    global_stats = finalized_entry_timing_stats(raw_global)
    side_stats: dict[str, dict[str, float]] = {}
    for side_name, group in frame.groupby("entry_side", dropna=False, observed=False):
        raw_side = entry_timing_raw_stats(group, bad_wait_threshold=bad_wait_threshold)
        side_stats[str(side_name)] = finalized_entry_timing_stats(raw_side)

    key_columns = ["entry_side", *group_columns, "_wait_regret_bucket"]
    group_stats: dict[tuple[str, ...], dict[str, float]] = {}
    for key, group in frame.groupby(key_columns, dropna=False, observed=False):
        if len(group) < min_group_size:
            continue
        key_tuple = tuple(str(value) for value in (key if isinstance(key, tuple) else (key,)))
        side_name = key_tuple[0]
        prior_stats = side_stats.get(side_name, global_stats)
        raw_group = entry_timing_raw_stats(group, bad_wait_threshold=bad_wait_threshold)
        smoothed = smooth_entry_timing_stats(raw_group, prior_stats, prior_strength)
        group_stats[key_tuple] = finalized_entry_timing_stats(smoothed)

    return EntryTimingCalibrationBundle(
        output_prefix=output_prefix,
        group_columns=group_columns,
        bucket_edges=edges,
        min_group_size=min_group_size,
        prior_strength=prior_strength,
        bad_wait_threshold=bad_wait_threshold,
        global_stats=global_stats,
        side_stats=side_stats,
        group_stats=group_stats,
    )


def entry_timing_stats_frame(bundle: EntryTimingCalibrationBundle) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    rows.append({"source": "global", "key": "global", **bundle.global_stats})
    for side_name, stats in sorted(bundle.side_stats.items()):
        rows.append({"source": "side", "key": side_name, "entry_side": side_name, **stats})
    for key, stats in sorted(bundle.group_stats.items()):
        row: dict[str, object] = {
            "source": "group",
            "key": "|".join(key),
            "entry_side": key[0],
            "_wait_regret_bucket": key[-1],
            **stats,
        }
        for column, value in zip(bundle.group_columns, key[1:-1], strict=True):
            row[column] = value
        rows.append(row)
    return pd.DataFrame(rows)


def entry_timing_output_frame(
    predictions: pd.DataFrame,
    side_name: str,
    bundle: EntryTimingCalibrationBundle,
) -> pd.DataFrame:
    wait_column = SIDE_COLUMNS[side_name]["wait_regret"]
    missing = [wait_column, *[column for column in bundle.group_columns if column not in predictions.columns]]
    missing = [column for column in missing if column not in predictions.columns]
    if missing:
        raise ValueError(f"predictions missing entry timing calibration columns: {', '.join(missing)}")

    wait_values = pd.to_numeric(predictions[wait_column], errors="coerce")
    buckets = assign_quality_score_buckets(wait_values, bundle.bucket_edges)
    group_values = normalize_candidate_quality_group_columns(predictions, bundle.group_columns)
    rows: list[dict[str, object]] = []
    for index in predictions.index:
        key = tuple(
            [
                side_name,
                *[str(group_values.loc[index, column]) for column in bundle.group_columns],
                str(buckets.loc[index]),
            ]
        )
        stats = bundle.group_stats.get(key)
        source = "group"
        if stats is None:
            stats = bundle.side_stats.get(side_name)
            source = "side"
        if stats is None:
            stats = bundle.global_stats
            source = "global"
        rows.append(
            {
                "calibrated_wait_regret": stats["actual_wait_regret_mean"],
                "bad_wait_prob": stats["bad_wait_prob"],
                "wait_excess_mean": stats["wait_excess_mean"],
                "wait_underestimate_mean": stats["wait_underestimate_mean"],
                "bad_wait_prob_risk": stats["bad_wait_prob_risk"],
                "wait_excess_risk": stats["wait_excess_risk"],
                "wait_underestimate_risk": stats["wait_underestimate_risk"],
                "support": stats["support"],
                "source": source,
                "wait_regret_bucket": str(buckets.loc[index]),
            }
        )
    return pd.DataFrame(rows, index=predictions.index)


def add_entry_timing_calibration_columns(
    predictions: pd.DataFrame,
    bundle: EntryTimingCalibrationBundle,
) -> pd.DataFrame:
    output = predictions.copy()
    for side_name in ("long", "short"):
        values = entry_timing_output_frame(output, side_name, bundle)
        columns = entry_timing_columns_for_side(side_name, bundle.output_prefix)
        for key, column in columns.items():
            output[column] = values[key]
    return output


def add_entry_timing_calibration_oof_columns(
    predictions: pd.DataFrame,
    examples: pd.DataFrame,
    *,
    oof_column: str,
    output_prefix: str,
    group_columns: tuple[str, ...],
    bucket_count: int,
    min_group_size: int,
    prior_strength: float,
    bad_wait_threshold: float,
) -> tuple[pd.DataFrame, dict[str, object]]:
    if oof_column not in predictions.columns:
        raise ValueError(f"predictions missing OOF column: {oof_column}")
    if oof_column not in examples.columns:
        raise ValueError(f"entry timing examples missing OOF column: {oof_column}")
    output = predictions.copy()
    output_columns = [
        column
        for side_name in ("long", "short")
        for column in entry_timing_columns_for_side(side_name, output_prefix).values()
    ]
    string_output_columns = {
        column
        for side_name in ("long", "short")
        for key, column in entry_timing_columns_for_side(side_name, output_prefix).items()
        if key in {"source", "wait_regret_bucket"}
    }
    for column in output_columns:
        if column in string_output_columns:
            output[column] = pd.Series(pd.NA, index=output.index, dtype="string")
        else:
            output[column] = np.nan

    fold_metrics: dict[str, object] = {}
    for value in sorted(str(item) for item in output[oof_column].dropna().astype(str).unique()):
        prediction_mask = output[oof_column].astype(str) == value
        fit_examples = examples[examples[oof_column].astype(str) != value]
        if fit_examples.empty:
            fit_examples = examples
        bundle = fit_entry_timing_calibrator(
            fit_examples,
            output_prefix=output_prefix,
            group_columns=group_columns,
            bucket_count=bucket_count,
            min_group_size=min_group_size,
            prior_strength=prior_strength,
            bad_wait_threshold=bad_wait_threshold,
        )
        scored = add_entry_timing_calibration_columns(output.loc[prediction_mask].copy(), bundle)
        output.loc[prediction_mask, output_columns] = scored[output_columns]
        fold_metrics[value] = {
            "fit_examples": int(len(fit_examples)),
            "scored_predictions": int(prediction_mask.sum()),
            "group_stats": int(len(bundle.group_stats)),
            "bucket_edges": list(bundle.bucket_edges),
        }
    return output, fold_metrics


def entry_timing_calibration_cli(args: argparse.Namespace) -> int:
    examples = read_table(args.examples)
    predictions = pd.read_parquet(args.predictions)
    group_columns = tuple(parse_csv_strings(args.group_columns))
    output_prefix = validate_candidate_quality_prediction_prefix(args.output_prefix)
    if not output_prefix:
        raise ValueError("--output-prefix must be non-empty")
    if args.oof_column:
        output, fold_metrics = add_entry_timing_calibration_oof_columns(
            predictions,
            examples,
            oof_column=args.oof_column,
            output_prefix=output_prefix,
            group_columns=group_columns,
            bucket_count=args.bucket_count,
            min_group_size=args.min_group_support,
            prior_strength=args.prior_strength,
            bad_wait_threshold=args.bad_wait_threshold,
        )
    else:
        bundle = fit_entry_timing_calibrator(
            examples,
            output_prefix=output_prefix,
            group_columns=group_columns,
            bucket_count=args.bucket_count,
            min_group_size=args.min_group_support,
            prior_strength=args.prior_strength,
            bad_wait_threshold=args.bad_wait_threshold,
        )
        output = add_entry_timing_calibration_columns(predictions, bundle)
        fold_metrics = {}

    final_bundle = fit_entry_timing_calibrator(
        examples,
        output_prefix=output_prefix,
        group_columns=group_columns,
        bucket_count=args.bucket_count,
        min_group_size=args.min_group_support,
        prior_strength=args.prior_strength,
        bad_wait_threshold=args.bad_wait_threshold,
    )
    args.output_path.parent.mkdir(parents=True, exist_ok=True)
    output.to_parquet(args.output_path, index=False)
    stats_path = args.output_path.with_suffix(".timing_stats.csv")
    entry_timing_stats_frame(final_bundle).to_csv(stats_path, index=False)
    output_columns = {
        side_name: entry_timing_columns_for_side(side_name, output_prefix)
        for side_name in ("long", "short")
    }
    metrics = {
        "mode": "entry_timing_calibration",
        "examples": str(args.examples),
        "predictions": str(args.predictions),
        "output_path": str(args.output_path),
        "stats_path": str(stats_path),
        "output_prefix": output_prefix,
        "group_columns": list(group_columns),
        "bucket_count": args.bucket_count,
        "bucket_edges": list(final_bundle.bucket_edges),
        "min_group_support": args.min_group_support,
        "prior_strength": args.prior_strength,
        "bad_wait_threshold": args.bad_wait_threshold,
        "rows": {
            "examples": int(len(examples)),
            "predictions": int(len(predictions)),
            "output": int(len(output)),
            "group_stats": int(len(final_bundle.group_stats)),
        },
        "oof_column": args.oof_column,
        "folds": fold_metrics,
        "output_columns": output_columns,
    }
    metrics_path = args.output_path.with_suffix(".metrics.json")
    with metrics_path.open("w", encoding="utf-8") as handle:
        json.dump(metrics, handle, ensure_ascii=False, indent=2, default=str)
    print(json.dumps({"output": str(args.output_path), "metrics": str(metrics_path)}, indent=2))
    return 0


def trade_failure_calibrated_prob_column(target_name: str, side_name: str) -> str:
    return f"pred_trade_failure_{target_name}_{side_name}_calibrated_prob"


def trade_failure_calibrated_risk_column(target_name: str, side_name: str) -> str:
    return f"pred_trade_failure_{target_name}_{side_name}_calibrated_risk"


def trade_failure_upper_prob_column(target_name: str, side_name: str) -> str:
    return f"pred_trade_failure_{target_name}_{side_name}_upper_prob"


def trade_failure_upper_risk_column(target_name: str, side_name: str) -> str:
    return f"pred_trade_failure_{target_name}_{side_name}_upper_risk"


def trade_failure_taken_calibrated_prob_column(target_name: str) -> str:
    return f"pred_trade_failure_{target_name}_taken_calibrated_prob"


def fit_trade_failure_probability_calibrator(
    enriched_trades: pd.DataFrame,
    config: GroupEVCalibrationConfig,
    target_name: str,
) -> TradeFailureProbabilityCalibrator:
    validate_trade_failure_targets((target_name,))
    if config.min_group_size <= 0:
        raise ValueError("min_group_size must be positive")
    if config.prior_strength < 0:
        raise ValueError("prior_strength must be non-negative")
    if not 0.0 <= config.prediction_shrinkage <= 1.0:
        raise ValueError("prediction_shrinkage must be in [0, 1]")
    if config.lower_z < 0:
        raise ValueError("lower_z must be non-negative")

    target_column = f"trade_failure_{target_name}"
    pred_column = trade_failure_taken_prob_column(target_name)
    required_columns = {
        "direction",
        target_column,
        pred_column,
        *config.group_columns,
    }
    missing_columns = sorted(required_columns - set(enriched_trades.columns))
    if missing_columns:
        raise ValueError(
            f"enriched trades missing failure calibration columns: {', '.join(missing_columns)}"
        )

    working = enriched_trades.copy()
    working["side_name"] = working["direction"].astype(str).str.lower()
    working["target"] = finite_float_series(working, target_column).clip(0.0, 1.0)
    working["pred"] = finite_float_series(working, pred_column).clip(0.0, 1.0)
    working = working.replace([np.inf, -np.inf], np.nan).dropna(subset=["target", "pred"])
    if working.empty:
        raise ValueError("no valid selected trades for trade failure probability calibration")

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
        side_stat = GroupEVStats(
            n=int(len(side_frame)),
            pred_mean=float(side_frame["pred"].mean()),
            target_mean=float(side_frame["target"].mean()),
            target_std=target_std(side_frame["target"]),
            target_standard_error=target_standard_error(side_frame["target"]),
        )
        side_stats[side_name] = side_stat
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
            group_stats[side_name][key] = GroupEVStats(
                n=group_count,
                pred_mean=float(weight * group["pred"].mean() + (1.0 - weight) * side_stat.pred_mean),
                target_mean=float(
                    weight * group["target"].mean() + (1.0 - weight) * side_stat.target_mean
                ),
                target_std=target_std(group["target"]),
                target_standard_error=target_standard_error(group["target"]),
            )
    return TradeFailureProbabilityCalibrator(
        config=config,
        target_name=target_name,
        overall_stats=overall_stats,
        side_stats=side_stats,
        group_stats=group_stats,
    )


def trade_failure_probability_stats_frame(
    predictions: pd.DataFrame,
    side_name: str,
    calibrator: TradeFailureProbabilityCalibrator,
) -> pd.DataFrame:
    fallback_stat = calibrator.side_stats.get(side_name, calibrator.overall_stats)
    stats = pd.DataFrame(
        {
            "pred_mean": fallback_stat.pred_mean,
            "target_mean": fallback_stat.target_mean,
            "support": fallback_stat.n,
            "target_std": fallback_stat.target_std,
            "target_standard_error": fallback_stat.target_standard_error,
            "source": "side" if side_name in calibrator.side_stats else "overall",
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
                stats.loc[mask, "support"] = group_stat.n
                stats.loc[mask, "target_std"] = group_stat.target_std
                stats.loc[mask, "target_standard_error"] = group_stat.target_standard_error
                stats.loc[mask, "source"] = "group"
    return stats


def trade_failure_calibrated_probability_values(
    predictions: pd.DataFrame,
    side_name: str,
    calibrator: TradeFailureProbabilityCalibrator,
) -> tuple[pd.Series, pd.Series, pd.DataFrame]:
    raw_column = trade_failure_prob_column(calibrator.target_name, side_name)
    if raw_column not in predictions.columns:
        raise ValueError(f"predictions missing failure probability column: {raw_column}")
    raw = finite_float_series(predictions, raw_column).clip(0.0, 1.0).reset_index(drop=True)
    stats = trade_failure_probability_stats_frame(predictions, side_name, calibrator)
    calibrated = (
        stats["target_mean"].astype(float)
        + calibrator.config.prediction_shrinkage * (raw - stats["pred_mean"].astype(float))
    ).clip(0.0, 1.0)
    upper_margin = support_aware_lower_margin(stats, calibrator.config)
    upper = (calibrated + upper_margin).clip(0.0, 1.0)
    return (
        pd.Series(calibrated.to_numpy(), index=predictions.index),
        pd.Series(upper.to_numpy(), index=predictions.index),
        stats,
    )


def add_trade_failure_probability_calibration_columns(
    predictions: pd.DataFrame,
    calibrator: TradeFailureProbabilityCalibrator,
) -> pd.DataFrame:
    output = predictions.copy()
    target_name = calibrator.target_name
    for side_name in ("long", "short"):
        calibrated, upper, stats = trade_failure_calibrated_probability_values(
            output,
            side_name,
            calibrator,
        )
        calibrated_column = trade_failure_calibrated_prob_column(target_name, side_name)
        upper_column = trade_failure_upper_prob_column(target_name, side_name)
        output[calibrated_column] = calibrated
        output[trade_failure_calibrated_risk_column(target_name, side_name)] = -calibrated
        output[upper_column] = upper
        output[trade_failure_upper_risk_column(target_name, side_name)] = -upper
        output[f"{calibrated_column}_support"] = pd.Series(
            stats["support"].to_numpy(),
            index=predictions.index,
        )
        output[f"{calibrated_column}_source"] = pd.Series(
            stats["source"].to_numpy(),
            index=predictions.index,
        )
        output[f"{calibrated_column}_upper_margin"] = pd.Series(
            support_aware_lower_margin(stats, calibrator.config).to_numpy(),
            index=predictions.index,
        )
    return output


def add_trade_failure_probability_values_to_enriched(
    enriched_trades: pd.DataFrame,
    calibrator: TradeFailureProbabilityCalibrator,
) -> pd.DataFrame:
    output = enriched_trades.copy()
    target_name = calibrator.target_name
    calibrated_values = []
    keys = group_key_series(output, calibrator.config.group_columns)
    for index, row in output.iterrows():
        side_name = str(row["direction"]).lower()
        stat = calibrator.side_stats.get(side_name, calibrator.overall_stats)
        key = keys.loc[index]
        stat = calibrator.group_stats.get(side_name, {}).get(key, stat)
        raw = float(row[trade_failure_taken_prob_column(target_name)])
        calibrated = stat.target_mean + calibrator.config.prediction_shrinkage * (raw - stat.pred_mean)
        calibrated_values.append(float(np.clip(calibrated, 0.0, 1.0)))
    output[trade_failure_taken_calibrated_prob_column(target_name)] = calibrated_values
    return output


def trade_failure_probability_scored_metrics(
    scored: pd.DataFrame,
    target_name: str,
) -> dict[str, float]:
    if scored.empty:
        return {
            "trade_count": 0,
            "prevalence": 0.0,
            "raw_predicted_mean": 0.0,
            "calibrated_predicted_mean": 0.0,
            "raw_bias": 0.0,
            "calibrated_bias": 0.0,
            "raw_brier": 0.0,
            "calibrated_brier": 0.0,
            "raw_auc": 0.5,
            "calibrated_auc": 0.5,
        }
    target = finite_float_series(scored, f"trade_failure_{target_name}").astype(int)
    raw = finite_float_series(scored, trade_failure_taken_prob_column(target_name)).clip(0.0, 1.0)
    calibrated = finite_float_series(
        scored,
        trade_failure_taken_calibrated_prob_column(target_name),
    ).clip(0.0, 1.0)
    if target.nunique(dropna=True) >= 2:
        raw_auc = float(roc_auc_score(target, raw))
        calibrated_auc = float(roc_auc_score(target, calibrated))
    else:
        raw_auc = 0.5
        calibrated_auc = 0.5
    return {
        "trade_count": int(len(scored)),
        "prevalence": float(target.mean()),
        "raw_predicted_mean": float(raw.mean()),
        "calibrated_predicted_mean": float(calibrated.mean()),
        "raw_bias": float(raw.mean() - target.mean()),
        "calibrated_bias": float(calibrated.mean() - target.mean()),
        "raw_brier": float(brier_score_loss(target, raw)),
        "calibrated_brier": float(brier_score_loss(target, calibrated)),
        "raw_auc": raw_auc,
        "calibrated_auc": calibrated_auc,
    }


def trade_failure_probability_calibration_metrics(
    enriched_trades: pd.DataFrame,
    calibrator: TradeFailureProbabilityCalibrator,
) -> dict[str, float]:
    scored = add_trade_failure_probability_values_to_enriched(enriched_trades, calibrator)
    return trade_failure_probability_scored_metrics(scored, calibrator.target_name)


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


def serializable_trade_failure_probability_calibrator(
    calibrator: TradeFailureProbabilityCalibrator,
) -> dict[str, object]:
    return {
        "config": asdict(calibrator.config),
        "target_name": calibrator.target_name,
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


def oof_residual_penalty(args: argparse.Namespace) -> int:
    validation_months = parse_csv_months(args.validation_months)
    apply_months = parse_csv_months(args.apply_months)
    base_fit_months = parse_csv_months(args.base_fit_months)
    if validation_months is None or len(validation_months) < 2:
        raise ValueError("at least two validation months are required for OOF residual penalty")
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

    config = ResidualPenaltyConfig(
        group_columns=tuple(parse_csv_strings(args.group_columns)),
        min_group_size=args.min_group_size,
        prior_strength=args.prior_strength,
        penalty_weight=args.penalty_weight,
        min_excess_overestimate=args.min_excess_overestimate,
        candidate_entry_only=args.candidate_entry_only,
        entry_threshold=args.entry_threshold,
        long_entry_threshold_offset=args.long_entry_threshold_offset,
        short_entry_threshold_offset=args.short_entry_threshold_offset,
        side_margin=args.side_margin,
        min_entry_rank=args.min_entry_rank,
        long_entry_rank_column=args.long_entry_rank_column,
        short_entry_rank_column=args.short_entry_rank_column,
    )
    validate_residual_penalty_inputs(
        validation_predictions,
        config,
        args.long_column,
        args.short_column,
    )
    if base_fit_predictions is not None:
        validate_residual_penalty_inputs(
            base_fit_predictions,
            config,
            args.long_column,
            args.short_column,
        )
    if apply_predictions is not None:
        validate_residual_penalty_inputs(
            apply_predictions,
            config,
            args.long_column,
            args.short_column,
        )

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
            raise ValueError(f"cannot build residual penalty OOF fold for {holdout_month}")
        fold_calibrator = fit_residual_penalty_calibrator(
            fit_predictions,
            config,
            long_column=args.long_column,
            short_column=args.short_column,
        )
        holdout_output = add_residual_penalty_columns(holdout_predictions, fold_calibrator)
        fold_outputs.append(holdout_output)
        fold_metrics[holdout_month] = {
            "fit_rows": int(len(fit_predictions)),
            "base_fit_rows": 0 if base_fit_predictions is None else int(len(base_fit_predictions)),
            "validation_fit_rows": int(len(validation_fit_predictions)),
            "holdout_rows": int(len(holdout_predictions)),
            "holdout": residual_penalty_scored_metrics(
                holdout_output,
                long_column=args.long_column,
                short_column=args.short_column,
                entry_threshold=args.entry_threshold,
            ),
            "calibrator": serializable_residual_penalty_calibrator(fold_calibrator),
        }

    validation_oof = pd.concat(fold_outputs, ignore_index=True)
    if "decision_timestamp" in validation_oof.columns:
        validation_oof = validation_oof.sort_values("decision_timestamp")

    final_fit_predictions = combine_fit_predictions(validation_predictions, base_fit_predictions)
    final_calibrator = fit_residual_penalty_calibrator(
        final_fit_predictions,
        config,
        long_column=args.long_column,
        short_column=args.short_column,
    )
    apply_output = None
    if apply_predictions is not None:
        apply_output = add_residual_penalty_columns(apply_predictions, final_calibrator)

    run_dir = make_run_dir(args.output_dir, args.label)
    validation_oof.to_parquet(
        run_dir / "predictions_validation_oof_residual_penalized.parquet",
        index=False,
    )
    if apply_output is not None:
        apply_output.to_parquet(
            run_dir / "predictions_apply_residual_penalized.parquet",
            index=False,
        )
    metrics = {
        "mode": "validation_oof_residual_penalty",
        "validation_predictions": str(args.validation_predictions),
        "base_fit_predictions": None if args.base_fit_predictions is None else str(args.base_fit_predictions),
        "apply_predictions": None if args.apply_predictions is None else str(args.apply_predictions),
        "validation_months": validation_months,
        "base_fit_months": base_fit_months,
        "apply_months": apply_months,
        "long_column": args.long_column,
        "short_column": args.short_column,
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
        "final_calibrator": serializable_residual_penalty_calibrator(final_calibrator),
        "folds": fold_metrics,
        "validation_oof": residual_penalty_scored_metrics(
            validation_oof,
            long_column=args.long_column,
            short_column=args.short_column,
            entry_threshold=args.entry_threshold,
        ),
        "apply": None
        if apply_output is None
        else residual_penalty_scored_metrics(
            apply_output,
            long_column=args.long_column,
            short_column=args.short_column,
            entry_threshold=args.entry_threshold,
        ),
    }
    with (run_dir / "metrics.json").open("w", encoding="utf-8") as handle:
        json.dump(metrics, handle, ensure_ascii=False, indent=2)
    print(json.dumps(metrics["validation_oof"], indent=2))
    if metrics["apply"] is not None:
        print(json.dumps(metrics["apply"], indent=2))
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


def trade_failure_model_config_from_args(args: argparse.Namespace) -> TradeFailureModelConfig:
    target_names = tuple(parse_csv_strings(args.failure_targets) or list(TRADE_FAILURE_TARGET_NAMES))
    return TradeFailureModelConfig(
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
        sample_weighting=args.sample_weighting,
        prediction_shrinkage=args.prediction_shrinkage,
        large_loss_threshold=args.large_loss_threshold,
        exit_regret_threshold=args.exit_regret_threshold,
        target_names=target_names,
    )


def candidate_failure_model_config_from_args(args: argparse.Namespace) -> CandidateFailureModelConfig:
    target_names = tuple(parse_csv_strings(args.failure_targets) or list(CANDIDATE_FAILURE_TARGET_NAMES))
    return CandidateFailureModelConfig(
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
        sample_weighting=args.sample_weighting,
        prediction_shrinkage=args.prediction_shrinkage,
        large_adverse_threshold=args.large_adverse_threshold,
        large_loss_threshold=args.large_loss_threshold,
        target_names=target_names,
        entry_threshold=args.entry_threshold,
        long_entry_threshold_offset=args.long_entry_threshold_offset,
        short_entry_threshold_offset=args.short_entry_threshold_offset,
        side_margin=args.side_margin,
        min_entry_rank=args.min_entry_rank,
        long_entry_rank_column=args.long_entry_rank_column,
        short_entry_rank_column=args.short_entry_rank_column,
    )


def candidate_quality_model_config_from_args(args: argparse.Namespace) -> CandidateQualityModelConfig:
    return CandidateQualityModelConfig(
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
        lower_quantile=args.lower_quantile,
        entry_threshold=args.entry_threshold,
        long_entry_threshold_offset=args.long_entry_threshold_offset,
        short_entry_threshold_offset=args.short_entry_threshold_offset,
        side_margin=args.side_margin,
        min_entry_rank=args.min_entry_rank,
        target_mode=args.target_mode,
        min_adjusted_edge=args.min_adjusted_edge,
        time_exit_target_minutes=args.time_exit_target_minutes,
        joint_barrier_weight=args.joint_barrier_weight,
        joint_fixed_horizon_weight=args.joint_fixed_horizon_weight,
        joint_best_weight=args.joint_best_weight,
        joint_time_decay=args.joint_time_decay,
        joint_component_clip_multiple=args.joint_component_clip_multiple,
        joint_fixed_horizon_minutes=tuple(parse_csv_ints(args.joint_fixed_horizon_minutes)),
        prediction_prefix=validate_candidate_quality_prediction_prefix(args.prediction_prefix),
        long_entry_rank_column=args.long_entry_rank_column,
        short_entry_rank_column=args.short_entry_rank_column,
    )


def oof_candidate_failure_model(args: argparse.Namespace) -> int:
    validation_months = parse_csv_months(args.validation_months)
    apply_months = parse_csv_months(args.apply_months)
    if validation_months is None or len(validation_months) < 2:
        raise ValueError("at least two validation months are required for OOF candidate failure model")
    if args.apply_predictions is None and apply_months is not None:
        raise ValueError("--apply-months requires --apply-predictions")

    validation_predictions = filter_months(
        pd.read_parquet(args.validation_predictions),
        validation_months,
        "validation",
    )
    validation_predictions = prepare_trade_quality_prediction_frame(validation_predictions, args)

    apply_predictions = None
    if args.apply_predictions is not None:
        apply_predictions = filter_months(
            pd.read_parquet(args.apply_predictions),
            apply_months,
            "apply",
        )
        apply_predictions = prepare_trade_quality_prediction_frame(apply_predictions, args)

    config = candidate_failure_model_config_from_args(args)
    validate_candidate_failure_targets(config.target_names)
    validation_candidates = build_candidate_failure_training_frame(
        validation_predictions,
        config,
        long_column=TRADE_SOURCE_LONG_EV_COLUMN,
        short_column=TRADE_SOURCE_SHORT_EV_COLUMN,
    )
    if validation_candidates.empty:
        raise ValueError("validation candidate failure frame is empty")

    fold_prediction_outputs: list[pd.DataFrame] = []
    fold_candidate_outputs: list[pd.DataFrame] = []
    fold_metrics: dict[str, object] = {}
    for fold_index, holdout_month in enumerate(validation_months):
        fit_predictions = validation_predictions[
            validation_predictions["dataset_month"] != holdout_month
        ].copy()
        holdout_predictions = validation_predictions[
            validation_predictions["dataset_month"] == holdout_month
        ].copy()
        if fit_predictions.empty or holdout_predictions.empty:
            raise ValueError(f"cannot build candidate failure OOF fold for {holdout_month}")
        fold_config = CandidateFailureModelConfig(
            **{
                **asdict(config),
                "random_seed": config.random_seed + 17 * fold_index,
            }
        )
        fit_candidates = build_candidate_failure_training_frame(
            fit_predictions,
            fold_config,
            long_column=TRADE_SOURCE_LONG_EV_COLUMN,
            short_column=TRADE_SOURCE_SHORT_EV_COLUMN,
        )
        holdout_candidates = build_candidate_failure_training_frame(
            holdout_predictions,
            fold_config,
            long_column=TRADE_SOURCE_LONG_EV_COLUMN,
            short_column=TRADE_SOURCE_SHORT_EV_COLUMN,
        )
        if fit_candidates.empty:
            raise ValueError(f"candidate failure fit frame is empty for {holdout_month}")
        fold_bundle = fit_candidate_failure_model_from_frame(fit_candidates, fold_config)
        holdout_prediction_output = add_candidate_failure_model_columns(
            holdout_predictions,
            fold_bundle,
        )
        holdout_candidate_output = add_candidate_failure_model_values_to_examples(
            holdout_candidates,
            fold_bundle,
        )
        fold_prediction_outputs.append(holdout_prediction_output)
        fold_candidate_outputs.append(holdout_candidate_output)
        fold_metrics[holdout_month] = {
            "fit_candidates": int(len(fit_candidates)),
            "holdout_candidates": int(len(holdout_candidates)),
            "holdout_predictions": int(len(holdout_predictions)),
            "holdout": candidate_failure_scored_metrics(
                holdout_candidate_output,
                config.target_names,
            ),
            "target_means": fold_bundle.target_means,
            "feature_columns": fold_bundle.feature_columns,
            "category_mappings": fold_bundle.category_mappings,
        }

    validation_oof = pd.concat(fold_prediction_outputs, ignore_index=True)
    if "decision_timestamp" in validation_oof.columns:
        validation_oof = validation_oof.sort_values("decision_timestamp")
    validation_oof_candidates = pd.concat(fold_candidate_outputs, ignore_index=True)
    if "decision_timestamp" in validation_oof_candidates.columns:
        validation_oof_candidates = validation_oof_candidates.sort_values("decision_timestamp")

    final_bundle = fit_candidate_failure_model_from_frame(validation_candidates, config)
    apply_output = None
    if apply_predictions is not None:
        apply_output = add_candidate_failure_model_columns(apply_predictions, final_bundle)

    run_dir = make_run_dir(args.output_dir, args.label)
    validation_oof.to_parquet(
        run_dir / "predictions_validation_oof_candidate_failure_model.parquet",
        index=False,
    )
    validation_oof_candidates.to_csv(
        run_dir / "validation_oof_candidate_failure_examples.csv",
        index=False,
    )
    validation_candidates.to_csv(run_dir / "validation_fit_candidate_failure_examples.csv", index=False)
    if apply_output is not None:
        apply_output.to_parquet(
            run_dir / "predictions_apply_candidate_failure_model.parquet",
            index=False,
        )
    joblib.dump(final_bundle, run_dir / "candidate_failure_model.joblib")
    metrics = {
        "mode": "validation_oof_candidate_failure_model",
        "config": asdict(config),
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
            "validation_candidates": int(len(validation_candidates)),
            "validation_oof": int(len(validation_oof)),
            "validation_oof_candidates": int(len(validation_oof_candidates)),
            "apply": 0 if apply_predictions is None else int(len(apply_predictions)),
        },
        "month_rows": {
            "validation_predictions": month_counts(validation_predictions),
            "validation_candidates": month_counts(validation_candidates),
            "validation_oof": month_counts(validation_oof),
            "validation_oof_candidates": month_counts(validation_oof_candidates),
            "apply": {} if apply_predictions is None else month_counts(apply_predictions),
        },
        "candidate_side_counts": (
            {}
            if validation_candidates.empty
            else {
                str(side): int(count)
                for side, count in validation_candidates["candidate_side"].value_counts().items()
            }
        ),
        "final_model": {
            "target_means": final_bundle.target_means,
            "feature_columns": final_bundle.feature_columns,
            "category_mappings": final_bundle.category_mappings,
        },
        "folds": fold_metrics,
        "validation_oof": candidate_failure_scored_metrics(
            validation_oof_candidates,
            config.target_names,
        ),
    }
    with (run_dir / "metrics.json").open("w", encoding="utf-8") as handle:
        json.dump(metrics, handle, ensure_ascii=False, indent=2, default=str)
    print(json.dumps(metrics["validation_oof"], indent=2))
    print(f"artifacts: {run_dir}")
    return 0


def oof_candidate_quality_model(args: argparse.Namespace) -> int:
    validation_months = parse_csv_months(args.validation_months)
    apply_months = parse_csv_months(args.apply_months)
    if validation_months is None or len(validation_months) < 2:
        raise ValueError("at least two validation months are required for OOF candidate quality model")
    if args.apply_predictions is None and apply_months is not None:
        raise ValueError("--apply-months requires --apply-predictions")

    validation_predictions = filter_months(
        pd.read_parquet(args.validation_predictions),
        validation_months,
        "validation",
    )
    validation_predictions = prepare_trade_quality_prediction_frame(validation_predictions, args)

    apply_predictions = None
    if args.apply_predictions is not None:
        apply_predictions = filter_months(
            pd.read_parquet(args.apply_predictions),
            apply_months,
            "apply",
        )
        apply_predictions = prepare_trade_quality_prediction_frame(apply_predictions, args)

    config = candidate_quality_model_config_from_args(args)
    validation_candidates = build_candidate_quality_training_frame(
        validation_predictions,
        config,
        long_column=TRADE_SOURCE_LONG_EV_COLUMN,
        short_column=TRADE_SOURCE_SHORT_EV_COLUMN,
    )
    if validation_candidates.empty:
        raise ValueError("validation candidate quality frame is empty")

    fold_prediction_outputs: list[pd.DataFrame] = []
    fold_candidate_outputs: list[pd.DataFrame] = []
    fold_metrics: dict[str, object] = {}
    for fold_index, holdout_month in enumerate(validation_months):
        fit_predictions = validation_predictions[
            validation_predictions["dataset_month"] != holdout_month
        ].copy()
        holdout_predictions = validation_predictions[
            validation_predictions["dataset_month"] == holdout_month
        ].copy()
        if fit_predictions.empty or holdout_predictions.empty:
            raise ValueError(f"cannot build candidate quality OOF fold for {holdout_month}")
        fold_config = CandidateQualityModelConfig(
            **{
                **asdict(config),
                "random_seed": config.random_seed + 19 * fold_index,
            }
        )
        fit_candidates = build_candidate_quality_training_frame(
            fit_predictions,
            fold_config,
            long_column=TRADE_SOURCE_LONG_EV_COLUMN,
            short_column=TRADE_SOURCE_SHORT_EV_COLUMN,
        )
        holdout_candidates = build_candidate_quality_training_frame(
            holdout_predictions,
            fold_config,
            long_column=TRADE_SOURCE_LONG_EV_COLUMN,
            short_column=TRADE_SOURCE_SHORT_EV_COLUMN,
        )
        if fit_candidates.empty:
            raise ValueError(f"candidate quality fit frame is empty for {holdout_month}")
        fold_bundle = fit_candidate_quality_model_from_frame(fit_candidates, fold_config)
        holdout_prediction_output = add_candidate_quality_model_columns(
            holdout_predictions,
            fold_bundle,
        )
        holdout_candidate_output = add_candidate_quality_model_values_to_examples(
            holdout_candidates,
            fold_bundle,
        )
        fold_prediction_outputs.append(holdout_prediction_output)
        fold_candidate_outputs.append(holdout_candidate_output)
        fold_metrics[holdout_month] = {
            "fit_candidates": int(len(fit_candidates)),
            "holdout_candidates": int(len(holdout_candidates)),
            "holdout_predictions": int(len(holdout_predictions)),
            "holdout": candidate_quality_scored_metrics(holdout_candidate_output),
            "target_mean": fold_bundle.target_mean,
            "lower_target_mean": fold_bundle.lower_target_mean,
            "feature_columns": fold_bundle.feature_columns,
            "category_mappings": fold_bundle.category_mappings,
        }

    validation_oof = pd.concat(fold_prediction_outputs, ignore_index=True)
    if "decision_timestamp" in validation_oof.columns:
        validation_oof = validation_oof.sort_values("decision_timestamp")
    validation_oof_candidates = pd.concat(fold_candidate_outputs, ignore_index=True)
    if "decision_timestamp" in validation_oof_candidates.columns:
        validation_oof_candidates = validation_oof_candidates.sort_values("decision_timestamp")

    final_bundle = fit_candidate_quality_model_from_frame(validation_candidates, config)
    apply_output = None
    if apply_predictions is not None:
        apply_output = add_candidate_quality_model_columns(apply_predictions, final_bundle)

    run_dir = make_run_dir(args.output_dir, args.label)
    validation_oof.to_parquet(
        run_dir / "predictions_validation_oof_candidate_quality_model.parquet",
        index=False,
    )
    validation_oof_candidates.to_csv(
        run_dir / "validation_oof_candidate_quality_examples.csv",
        index=False,
    )
    validation_candidates.to_csv(run_dir / "validation_fit_candidate_quality_examples.csv", index=False)
    if apply_output is not None:
        apply_output.to_parquet(
            run_dir / "predictions_apply_candidate_quality_model.parquet",
            index=False,
        )
    joblib.dump(final_bundle, run_dir / "candidate_quality_model.joblib")
    metrics = {
        "mode": "validation_oof_candidate_quality_model",
        "config": asdict(config),
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
            "validation_candidates": int(len(validation_candidates)),
            "validation_oof": int(len(validation_oof)),
            "validation_oof_candidates": int(len(validation_oof_candidates)),
            "apply": 0 if apply_predictions is None else int(len(apply_predictions)),
        },
        "month_rows": {
            "validation_predictions": month_counts(validation_predictions),
            "validation_candidates": month_counts(validation_candidates),
            "validation_oof": month_counts(validation_oof),
            "validation_oof_candidates": month_counts(validation_oof_candidates),
            "apply": {} if apply_predictions is None else month_counts(apply_predictions),
        },
        "candidate_side_counts": (
            {}
            if validation_candidates.empty
            else {
                str(side): int(count)
                for side, count in validation_candidates["candidate_side"].value_counts().items()
            }
        ),
        "final_model": {
            "target_mean": final_bundle.target_mean,
            "lower_target_mean": final_bundle.lower_target_mean,
            "feature_columns": final_bundle.feature_columns,
            "category_mappings": final_bundle.category_mappings,
        },
        "folds": fold_metrics,
        "validation_oof": candidate_quality_scored_metrics(validation_oof_candidates),
    }
    with (run_dir / "metrics.json").open("w", encoding="utf-8") as handle:
        json.dump(metrics, handle, ensure_ascii=False, indent=2, default=str)
    print(json.dumps(metrics["validation_oof"], indent=2))
    print(f"artifacts: {run_dir}")
    return 0


def combine_candidate_quality_components_cli(args: argparse.Namespace) -> int:
    component_prefixes = parse_csv_strings(args.component_prefixes)
    weights = parse_csv_floats(args.weights)
    if args.mode != "weighted_mean" and weights:
        raise ValueError("--weights can only be used with --mode weighted_mean")
    if args.mode == "weighted_mean" and not weights:
        raise ValueError("--weights is required with --mode weighted_mean")

    predictions = pd.read_parquet(args.predictions)
    output = combine_candidate_quality_component_columns(
        predictions,
        component_prefixes=component_prefixes,
        output_prefix=args.output_prefix,
        mode=args.mode,
        weights=weights or None,
    )
    args.output_path.parent.mkdir(parents=True, exist_ok=True)
    output.to_parquet(args.output_path, index=False)

    output_columns: dict[str, list[str]] = {}
    missing_counts: dict[str, int] = {}
    means: dict[str, float] = {}
    for side_name in ("long", "short"):
        columns = list(candidate_quality_columns_for_side(side_name, args.output_prefix))
        output_columns[side_name] = columns
        for column in columns:
            missing_counts[column] = int(output[column].isna().sum())
            means[column] = float(output[column].mean()) if output[column].notna().any() else float("nan")
    metrics = {
        "mode": "candidate_quality_component_composite",
        "predictions": str(args.predictions),
        "output_path": str(args.output_path),
        "component_prefixes": component_prefixes,
        "output_prefix": validate_candidate_quality_prediction_prefix(args.output_prefix),
        "combine_mode": args.mode,
        "weights": weights,
        "rows": int(len(output)),
        "output_columns": output_columns,
        "missing_counts": missing_counts,
        "means": means,
    }
    metrics_path = args.output_path.with_suffix(".metrics.json")
    with metrics_path.open("w", encoding="utf-8") as handle:
        json.dump(metrics, handle, ensure_ascii=False, indent=2, default=str)
    print(json.dumps(metrics, indent=2, default=str))
    return 0


def oof_trade_failure_model(args: argparse.Namespace) -> int:
    validation_months = parse_csv_months(args.validation_months)
    apply_months = parse_csv_months(args.apply_months)
    if validation_months is None or len(validation_months) < 2:
        raise ValueError("at least two validation months are required for OOF trade failure model")
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

    config = trade_failure_model_config_from_args(args)
    validate_trade_failure_targets(config.target_names)
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
            raise ValueError(f"cannot build trade failure model OOF fold for {holdout_month}")
        fold_config = TradeFailureModelConfig(
            **{
                **asdict(config),
                "random_seed": config.random_seed + 13 * fold_index,
            }
        )
        fold_bundle = fit_trade_failure_model(fit_trades, fold_config)
        holdout_prediction_output = add_trade_failure_model_columns(holdout_predictions, fold_bundle)
        holdout_trade_output = add_trade_failure_model_values_to_enriched(holdout_trades, fold_bundle)
        fold_prediction_outputs.append(holdout_prediction_output)
        fold_trade_outputs.append(holdout_trade_output)
        fold_metrics[holdout_month] = {
            "fit_trades": int(len(fit_trades)),
            "holdout_trades": int(len(holdout_trades)),
            "holdout_predictions": int(len(holdout_predictions)),
            "holdout": trade_failure_scored_metrics(holdout_trade_output, config.target_names),
            "target_means": fold_bundle.target_means,
            "feature_columns": fold_bundle.feature_columns,
            "category_mappings": fold_bundle.category_mappings,
        }

    validation_oof = pd.concat(fold_prediction_outputs, ignore_index=True)
    if "decision_timestamp" in validation_oof.columns:
        validation_oof = validation_oof.sort_values("decision_timestamp")
    validation_oof_trades = pd.concat(fold_trade_outputs, ignore_index=True)
    if "entry_timestamp" in validation_oof_trades.columns:
        validation_oof_trades = validation_oof_trades.sort_values("entry_timestamp")

    final_bundle = fit_trade_failure_model(validation_enriched, config)
    apply_output = None
    if apply_predictions is not None:
        apply_output = add_trade_failure_model_columns(apply_predictions, final_bundle)

    run_dir = make_run_dir(args.output_dir, args.label)
    validation_oof.to_parquet(
        run_dir / "predictions_validation_oof_trade_failure_model.parquet",
        index=False,
    )
    validation_oof_trades.to_csv(run_dir / "validation_oof_failure_enriched_trades.csv", index=False)
    validation_enriched.to_csv(run_dir / "validation_fit_enriched_trades.csv", index=False)
    if apply_output is not None:
        apply_output.to_parquet(
            run_dir / "predictions_apply_trade_failure_model.parquet",
            index=False,
        )
    joblib.dump(final_bundle, run_dir / "trade_failure_model.joblib")
    metrics = {
        "mode": "validation_oof_trade_failure_model",
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
            "target_means": final_bundle.target_means,
            "feature_columns": final_bundle.feature_columns,
            "category_mappings": final_bundle.category_mappings,
        },
        "folds": fold_metrics,
        "validation_oof": trade_failure_scored_metrics(validation_oof_trades, config.target_names),
    }
    with (run_dir / "metrics.json").open("w", encoding="utf-8") as handle:
        json.dump(metrics, handle, ensure_ascii=False, indent=2, default=str)
    print(json.dumps(metrics["validation_oof"], indent=2))
    print(f"artifacts: {run_dir}")
    return 0


def oof_trade_failure_calibration(args: argparse.Namespace) -> int:
    validation_months = parse_csv_months(args.validation_months)
    apply_months = parse_csv_months(args.apply_months)
    if validation_months is None or len(validation_months) < 2:
        raise ValueError("at least two validation months are required for OOF trade failure calibration")
    if args.apply_predictions is None and apply_months is not None:
        raise ValueError("--apply-months requires --apply-predictions")
    validate_trade_failure_targets((args.target_name,))

    validation_predictions = filter_months(
        pd.read_parquet(args.validation_predictions),
        validation_months,
        "validation",
    )
    validation_trades = read_trade_frames(parse_csv_paths(args.validation_trades))
    validation_trades = validation_trades[
        validation_trades["dataset_month"].isin(validation_months)
    ].copy()
    if validation_trades.empty:
        raise ValueError("validation failure-trade frame is empty after month filtering")

    apply_predictions = None
    if args.apply_predictions is not None:
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
    validate_group_columns(validation_predictions, validation_predictions, config.group_columns)
    if apply_predictions is not None:
        validate_group_columns(validation_predictions, apply_predictions, config.group_columns)

    fold_prediction_outputs: list[pd.DataFrame] = []
    fold_trade_outputs: list[pd.DataFrame] = []
    fold_metrics: dict[str, object] = {}
    for holdout_month in validation_months:
        fit_trades = validation_trades[validation_trades["dataset_month"] != holdout_month].copy()
        holdout_trades = validation_trades[validation_trades["dataset_month"] == holdout_month].copy()
        holdout_predictions = validation_predictions[
            validation_predictions["dataset_month"] == holdout_month
        ].copy()
        if fit_trades.empty or holdout_predictions.empty:
            raise ValueError(f"cannot build trade failure calibration OOF fold for {holdout_month}")
        fold_calibrator = fit_trade_failure_probability_calibrator(
            fit_trades,
            config,
            args.target_name,
        )
        holdout_prediction_output = add_trade_failure_probability_calibration_columns(
            holdout_predictions,
            fold_calibrator,
        )
        holdout_trade_output = add_trade_failure_probability_values_to_enriched(
            holdout_trades,
            fold_calibrator,
        )
        fold_prediction_outputs.append(holdout_prediction_output)
        fold_trade_outputs.append(holdout_trade_output)
        fold_metrics[holdout_month] = {
            "fit_trades": int(len(fit_trades)),
            "holdout_trades": int(len(holdout_trades)),
            "holdout_predictions": int(len(holdout_predictions)),
            "holdout": trade_failure_probability_calibration_metrics(
                holdout_trades,
                fold_calibrator,
            ),
            "calibrator": serializable_trade_failure_probability_calibrator(fold_calibrator),
        }

    validation_oof = pd.concat(fold_prediction_outputs, ignore_index=True)
    if "decision_timestamp" in validation_oof.columns:
        validation_oof = validation_oof.sort_values("decision_timestamp")
    validation_oof_trades = pd.concat(fold_trade_outputs, ignore_index=True)
    if "entry_timestamp" in validation_oof_trades.columns:
        validation_oof_trades = validation_oof_trades.sort_values("entry_timestamp")

    final_calibrator = fit_trade_failure_probability_calibrator(
        validation_trades,
        config,
        args.target_name,
    )
    apply_output = None
    if apply_predictions is not None:
        apply_output = add_trade_failure_probability_calibration_columns(
            apply_predictions,
            final_calibrator,
        )

    run_dir = make_run_dir(args.output_dir, args.label)
    validation_oof.to_parquet(
        run_dir / "predictions_validation_oof_trade_failure_calibrated.parquet",
        index=False,
    )
    validation_oof_trades.to_csv(
        run_dir / "validation_oof_failure_calibrated_trades.csv",
        index=False,
    )
    validation_trades.to_csv(run_dir / "validation_fit_failure_trades.csv", index=False)
    if apply_output is not None:
        apply_output.to_parquet(
            run_dir / "predictions_apply_trade_failure_calibrated.parquet",
            index=False,
        )

    metrics = {
        "mode": "validation_oof_trade_failure_calibration",
        "target_name": args.target_name,
        "config": asdict(config),
        "validation_trades": [str(path) for path in parse_csv_paths(args.validation_trades)],
        "validation_predictions": str(args.validation_predictions),
        "apply_predictions": None if args.apply_predictions is None else str(args.apply_predictions),
        "validation_months": validation_months,
        "apply_months": apply_months,
        "rows": {
            "validation_predictions": int(len(validation_predictions)),
            "validation_trades": int(len(validation_trades)),
            "validation_oof": int(len(validation_oof)),
            "apply": 0 if apply_predictions is None else int(len(apply_predictions)),
        },
        "month_rows": {
            "validation_predictions": month_counts(validation_predictions),
            "validation_trades": month_counts(validation_trades),
            "validation_oof": month_counts(validation_oof),
            "apply": {} if apply_predictions is None else month_counts(apply_predictions),
        },
        "final_calibrator": serializable_trade_failure_probability_calibrator(final_calibrator),
        "folds": fold_metrics,
        "validation_oof": trade_failure_probability_scored_metrics(
            validation_oof_trades,
            args.target_name,
        ),
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

    def add_residual_penalty_args(
        penalty_parser: argparse.ArgumentParser,
        default_label: str = "regime_residual_penalty",
    ) -> None:
        penalty_parser.add_argument(
            "--group-columns",
            default="volatility_regime,session_regime",
            help="comma-separated categorical columns for side/regime residual penalty",
        )
        penalty_parser.add_argument("--min-group-size", type=int, default=500)
        penalty_parser.add_argument("--prior-strength", type=float, default=2000.0)
        penalty_parser.add_argument(
            "--penalty-weight",
            type=float,
            default=1.0,
            help="non-negative multiplier applied to group excess overestimate",
        )
        penalty_parser.add_argument(
            "--min-excess-overestimate",
            type=float,
            default=0.0,
            help="ignored excess overestimate before the residual penalty starts",
        )
        penalty_parser.add_argument(
            "--candidate-entry-only",
            type=parse_bool,
            default=False,
            help="fit residual stats only on rows that pass the configured entry-side filter",
        )
        penalty_parser.add_argument("--long-column", default="pred_long_best_adjusted_pnl")
        penalty_parser.add_argument("--short-column", default="pred_short_best_adjusted_pnl")
        penalty_parser.add_argument("--entry-threshold", type=float, default=15.0)
        penalty_parser.add_argument("--long-entry-threshold-offset", type=float, default=0.0)
        penalty_parser.add_argument("--short-entry-threshold-offset", type=float, default=0.0)
        penalty_parser.add_argument("--side-margin", type=float, default=0.0)
        penalty_parser.add_argument("--min-entry-rank", type=float, default=0.0)
        penalty_parser.add_argument("--long-entry-rank-column", default="pred_long_entry_local_rank")
        penalty_parser.add_argument("--short-entry-rank-column", default="pred_short_entry_local_rank")
        penalty_parser.add_argument("--output-dir", type=Path, default=Path("experiments"))
        penalty_parser.add_argument("--label", default=default_label)

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

    def add_trade_quality_model_args(
        model_parser: argparse.ArgumentParser,
        *,
        include_target_clip_quantile: bool = True,
    ) -> None:
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
        if include_target_clip_quantile:
            model_parser.add_argument("--target-clip-quantile", type=float, default=0.98)
        model_parser.add_argument(
            "--sample-weighting",
            choices=["none", "month", "side", "month_side"],
            default="month_side",
        )
        model_parser.add_argument("--prediction-shrinkage", type=float, default=0.7)

    def add_candidate_entry_filter_args(candidate_parser: argparse.ArgumentParser) -> None:
        candidate_parser.add_argument("--entry-threshold", type=float, default=12.0)
        candidate_parser.add_argument("--long-entry-threshold-offset", type=float, default=0.0)
        candidate_parser.add_argument("--short-entry-threshold-offset", type=float, default=6.0)
        candidate_parser.add_argument("--side-margin", type=float, default=5.0)
        candidate_parser.add_argument("--min-entry-rank", type=float, default=0.5)
        candidate_parser.add_argument("--long-entry-rank-column", default="pred_long_entry_local_rank")
        candidate_parser.add_argument("--short-entry-rank-column", default="pred_short_entry_local_rank")

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

    residual_penalty_oof_parser = subparsers.add_parser(
        "oof-residual-penalty",
        help="build validation OOF side/regime residual-overestimate penalty columns",
    )
    residual_penalty_oof_parser.add_argument("--validation-predictions", type=Path, required=True)
    residual_penalty_oof_parser.add_argument(
        "--base-fit-predictions",
        type=Path,
        help="optional OOF prediction frame to include in every validation penalty fit",
    )
    residual_penalty_oof_parser.add_argument(
        "--apply-predictions",
        type=Path,
        help="optional prediction frame to score with the final validation-fitted penalty",
    )
    residual_penalty_oof_parser.add_argument(
        "--validation-months",
        required=True,
        help="comma-separated validation dataset months for OOF folds",
    )
    residual_penalty_oof_parser.add_argument("--base-fit-months", help="comma-separated base fit months")
    residual_penalty_oof_parser.add_argument("--apply-months", help="comma-separated apply months")
    add_residual_penalty_args(residual_penalty_oof_parser)
    residual_penalty_oof_parser.set_defaults(func=oof_residual_penalty)

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

    trade_failure_model_parser = subparsers.add_parser(
        "oof-trade-failure-model",
        help="build validation OOF selected-trade failure probability columns",
    )
    trade_failure_model_parser.add_argument(
        "--validation-trades",
        required=True,
        help="comma-separated model-policy trades.csv files for validation months",
    )
    trade_failure_model_parser.add_argument("--validation-predictions", type=Path, required=True)
    trade_failure_model_parser.add_argument(
        "--apply-predictions",
        type=Path,
        help="optional prediction frame to score with the final validation-trade failure model",
    )
    trade_failure_model_parser.add_argument(
        "--validation-months",
        required=True,
        help="comma-separated validation dataset months for OOF folds",
    )
    trade_failure_model_parser.add_argument("--apply-months", help="comma-separated apply months")
    trade_failure_model_parser.add_argument("--output-dir", type=Path, default=Path("experiments"))
    trade_failure_model_parser.add_argument("--label", default="trade_failure_model")
    trade_failure_model_parser.add_argument(
        "--failure-targets",
        default=",".join(TRADE_FAILURE_TARGET_NAMES),
        help="comma-separated failure targets: large_loss,wrong_side,profit_barrier_miss,exit_regret_high,any_failure",
    )
    trade_failure_model_parser.add_argument("--large-loss-threshold", type=float, default=10.0)
    trade_failure_model_parser.add_argument("--exit-regret-threshold", type=float, default=10.0)
    add_trade_source_args(trade_failure_model_parser)
    add_trade_quality_model_args(trade_failure_model_parser, include_target_clip_quantile=False)
    trade_failure_model_parser.set_defaults(func=oof_trade_failure_model)

    candidate_failure_model_parser = subparsers.add_parser(
        "oof-candidate-failure-model",
        help="build validation OOF candidate-entry failure probability columns",
    )
    candidate_failure_model_parser.add_argument("--validation-predictions", type=Path, required=True)
    candidate_failure_model_parser.add_argument(
        "--apply-predictions",
        type=Path,
        help="optional prediction frame to score with the final validation-candidate model",
    )
    candidate_failure_model_parser.add_argument(
        "--validation-months",
        required=True,
        help="comma-separated validation dataset months for OOF folds",
    )
    candidate_failure_model_parser.add_argument("--apply-months", help="comma-separated apply months")
    candidate_failure_model_parser.add_argument("--output-dir", type=Path, default=Path("experiments"))
    candidate_failure_model_parser.add_argument("--label", default="candidate_failure_model")
    candidate_failure_model_parser.add_argument(
        "--failure-targets",
        default="large_adverse",
        help=(
            "comma-separated candidate failure targets: large_adverse,large_loss,"
            "wrong_side,range_normal_vol_selected_failure,normal_vol_selected_failure,"
            "time_session_selected_failure,any_failure; default keeps the legacy "
            "large_adverse-only model"
        ),
    )
    candidate_failure_model_parser.add_argument("--large-adverse-threshold", type=float, default=10.0)
    candidate_failure_model_parser.add_argument("--large-loss-threshold", type=float, default=10.0)
    add_trade_source_args(candidate_failure_model_parser)
    add_trade_quality_model_args(candidate_failure_model_parser, include_target_clip_quantile=False)
    add_candidate_entry_filter_args(candidate_failure_model_parser)
    candidate_failure_model_parser.set_defaults(func=oof_candidate_failure_model)

    candidate_quality_model_parser = subparsers.add_parser(
        "oof-candidate-quality-model",
        help="build validation OOF candidate-entry realized-PnL mean and lower-quantile columns",
    )
    candidate_quality_model_parser.add_argument("--validation-predictions", type=Path, required=True)
    candidate_quality_model_parser.add_argument(
        "--apply-predictions",
        type=Path,
        help="optional prediction frame to score with the final validation-candidate quality model",
    )
    candidate_quality_model_parser.add_argument(
        "--validation-months",
        required=True,
        help="comma-separated validation dataset months for OOF folds",
    )
    candidate_quality_model_parser.add_argument("--apply-months", help="comma-separated apply months")
    candidate_quality_model_parser.add_argument("--output-dir", type=Path, default=Path("experiments"))
    candidate_quality_model_parser.add_argument("--label", default="candidate_quality_model")
    candidate_quality_model_parser.add_argument(
        "--lower-quantile",
        type=float,
        default=0.25,
        help="lower-tail quantile target for conservative candidate quality estimates",
    )
    candidate_quality_model_parser.add_argument(
        "--target-mode",
        choices=CANDIDATE_QUALITY_TARGET_MODES,
        default="best_adjusted_pnl",
        help=(
            "candidate quality target: hindsight best adjusted PnL, first "
            "profit/loss barrier with forced PnL on time exit, individual joint components, "
            "or weighted joint exit target"
        ),
    )
    candidate_quality_model_parser.add_argument(
        "--min-adjusted-edge",
        type=float,
        default=15.0,
        help="adjusted PnL assigned to profit/loss barrier exits in barrier_event_adjusted_pnl mode",
    )
    candidate_quality_model_parser.add_argument(
        "--time-exit-target-minutes",
        type=int,
        default=720,
        help=(
            "fixed-horizon adjusted PnL column to use for time-exit targets when "
            "forced adjusted PnL columns are not present"
        ),
    )
    candidate_quality_model_parser.add_argument(
        "--joint-barrier-weight",
        type=float,
        default=0.7,
        help="joint_exit_adjusted_pnl weight for timed profit/loss/time-exit barrier target",
    )
    candidate_quality_model_parser.add_argument(
        "--joint-fixed-horizon-weight",
        type=float,
        default=0.2,
        help="joint_exit_adjusted_pnl weight for actual fixed-horizon adjusted PnL",
    )
    candidate_quality_model_parser.add_argument(
        "--joint-best-weight",
        type=float,
        default=0.1,
        help="joint_exit_adjusted_pnl weight for clipped hindsight best adjusted PnL",
    )
    candidate_quality_model_parser.add_argument(
        "--joint-time-decay",
        type=float,
        default=0.25,
        help="joint_exit_adjusted_pnl decay applied to slower profit/loss barrier events",
    )
    candidate_quality_model_parser.add_argument(
        "--joint-component-clip-multiple",
        type=float,
        default=1.0,
        help="clip joint target components to min_adjusted_edge times this multiple",
    )
    candidate_quality_model_parser.add_argument(
        "--joint-fixed-horizon-minutes",
        default="60,240,720",
        help="comma-separated fixed-horizon actual PnL minutes used by joint_exit_adjusted_pnl",
    )
    candidate_quality_model_parser.add_argument(
        "--prediction-prefix",
        default="",
        help=(
            "optional prefix for output prediction columns, producing "
            "pred_candidate_quality_<prefix>_<side>_* columns"
        ),
    )
    add_trade_source_args(candidate_quality_model_parser)
    add_trade_quality_model_args(candidate_quality_model_parser)
    add_candidate_entry_filter_args(candidate_quality_model_parser)
    candidate_quality_model_parser.set_defaults(func=oof_candidate_quality_model)

    combine_candidate_quality_parser = subparsers.add_parser(
        "combine-candidate-quality-components",
        help="combine prefixed candidate-quality component columns into one prefixed column set",
    )
    combine_candidate_quality_parser.add_argument("--predictions", type=Path, required=True)
    combine_candidate_quality_parser.add_argument("--output-path", type=Path, required=True)
    combine_candidate_quality_parser.add_argument(
        "--component-prefixes",
        required=True,
        help="comma-separated candidate-quality prediction prefixes to combine",
    )
    combine_candidate_quality_parser.add_argument(
        "--output-prefix",
        required=True,
        help="output prediction prefix for pred_candidate_quality_<prefix>_<side>_* columns",
    )
    combine_candidate_quality_parser.add_argument(
        "--mode",
        choices=("mean", "min", "max", "weighted_mean"),
        default="mean",
    )
    combine_candidate_quality_parser.add_argument(
        "--weights",
        default="",
        help="comma-separated non-negative weights, required for weighted_mean",
    )
    combine_candidate_quality_parser.set_defaults(func=combine_candidate_quality_components_cli)

    candidate_quality_report_parser = subparsers.add_parser(
        "candidate-quality-report",
        help="diagnose candidate-entry quality prediction drift by month, side, regime, and buckets",
    )
    candidate_quality_report_parser.add_argument("--examples", type=Path, required=True)
    candidate_quality_report_parser.add_argument("--output-dir", type=Path, default=Path("experiments"))
    candidate_quality_report_parser.add_argument("--label", default="candidate_quality_report")
    candidate_quality_report_parser.add_argument("--target-column", default="target")
    candidate_quality_report_parser.add_argument("--raw-prediction-column", default="pred_taken_ev")
    candidate_quality_report_parser.add_argument(
        "--mean-prediction-column",
        default=CANDIDATE_QUALITY_TAKEN_COLUMN,
    )
    candidate_quality_report_parser.add_argument(
        "--lower-prediction-column",
        default=CANDIDATE_QUALITY_TAKEN_LOWER_COLUMN,
    )
    candidate_quality_report_parser.add_argument(
        "--downside-thresholds",
        default="0,-15",
        help="comma-separated target thresholds used for downside prevalence diagnostics",
    )
    candidate_quality_report_parser.add_argument(
        "--groupings",
        default=(
            "dataset_month;candidate_side;combined_regime;session_regime;"
            "dataset_month,candidate_side;dataset_month,combined_regime;"
            "dataset_month,session_regime"
        ),
        help="semicolon-separated groupings; each grouping is comma-separated columns",
    )
    candidate_quality_report_parser.add_argument(
        "--bucket-score",
        choices=("raw", "mean", "lower"),
        default="mean",
        help="prediction column family used to build quantile buckets",
    )
    candidate_quality_report_parser.add_argument("--bucket-count", type=int, default=10)
    candidate_quality_report_parser.add_argument(
        "--bucket-group-columns",
        default="dataset_month,candidate_side",
        help="comma-separated columns to include before the prediction quantile bucket",
    )
    candidate_quality_report_parser.add_argument("--min-group-support", type=int, default=20)
    candidate_quality_report_parser.add_argument("--summary-rows", type=int, default=10)
    candidate_quality_report_parser.set_defaults(func=candidate_quality_report_cli)

    candidate_quality_downside_calibration_parser = subparsers.add_parser(
        "candidate-quality-downside-calibration",
        help=(
            "add support-aware candidate-quality downside calibration columns "
            "from OOF candidate examples"
        ),
    )
    candidate_quality_downside_calibration_parser.add_argument("--examples", type=Path, required=True)
    candidate_quality_downside_calibration_parser.add_argument("--predictions", type=Path, required=True)
    candidate_quality_downside_calibration_parser.add_argument("--output-path", type=Path, required=True)
    candidate_quality_downside_calibration_parser.add_argument(
        "--input-prediction-prefix",
        default="",
        help="candidate-quality prediction prefix already present in --predictions",
    )
    candidate_quality_downside_calibration_parser.add_argument(
        "--output-prefix",
        default="downside_calibrated",
        help="output prefix for calibrated downside columns",
    )
    candidate_quality_downside_calibration_parser.add_argument(
        "--group-columns",
        default="combined_regime",
        help="comma-separated columns combined with side and quality bucket for calibration",
    )
    candidate_quality_downside_calibration_parser.add_argument("--bucket-count", type=int, default=10)
    candidate_quality_downside_calibration_parser.add_argument("--min-group-support", type=int, default=20)
    candidate_quality_downside_calibration_parser.add_argument("--prior-strength", type=float, default=50.0)
    candidate_quality_downside_calibration_parser.add_argument("--lower-z", type=float, default=1.0)
    candidate_quality_downside_calibration_parser.add_argument("--downside-threshold", type=float, default=0.0)
    candidate_quality_downside_calibration_parser.add_argument(
        "--large-downside-threshold",
        type=float,
        default=-15.0,
    )
    candidate_quality_downside_calibration_parser.add_argument(
        "--oof-column",
        help=(
            "optional column such as dataset_month; when set, rows are calibrated "
            "with examples from other values of this column"
        ),
    )
    candidate_quality_downside_calibration_parser.set_defaults(
        func=candidate_quality_downside_calibration_cli
    )

    entry_timing_calibration_parser = subparsers.add_parser(
        "entry-timing-calibration",
        help=(
            "add support-aware entry timing risk columns from actual/predicted "
            "wait regret"
        ),
    )
    entry_timing_calibration_parser.add_argument(
        "--examples",
        type=Path,
        required=True,
        help="parquet or csv with actual and predicted wait_regret columns",
    )
    entry_timing_calibration_parser.add_argument("--predictions", type=Path, required=True)
    entry_timing_calibration_parser.add_argument("--output-path", type=Path, required=True)
    entry_timing_calibration_parser.add_argument(
        "--output-prefix",
        default="wait4",
        help="output prefix for pred_entry_timing_<prefix>_<side>_* columns",
    )
    entry_timing_calibration_parser.add_argument(
        "--group-columns",
        default="combined_regime",
        help="comma-separated columns combined with side and wait-regret bucket",
    )
    entry_timing_calibration_parser.add_argument("--bucket-count", type=int, default=10)
    entry_timing_calibration_parser.add_argument("--min-group-support", type=int, default=20)
    entry_timing_calibration_parser.add_argument("--prior-strength", type=float, default=50.0)
    entry_timing_calibration_parser.add_argument(
        "--bad-wait-threshold",
        type=float,
        default=4.0,
        help="actual wait_regret above this value is treated as bad entry timing",
    )
    entry_timing_calibration_parser.add_argument(
        "--oof-column",
        help=(
            "optional column such as dataset_month; when set, rows are calibrated "
            "with examples from other values of this column"
        ),
    )
    entry_timing_calibration_parser.set_defaults(func=entry_timing_calibration_cli)

    trade_failure_calibration_parser = subparsers.add_parser(
        "oof-trade-failure-calibration",
        help="build validation OOF side/regime calibration for trade failure probabilities",
    )
    trade_failure_calibration_parser.add_argument(
        "--validation-trades",
        required=True,
        help="comma-separated enriched failure trade CSVs from oof-trade-failure-model",
    )
    trade_failure_calibration_parser.add_argument("--validation-predictions", type=Path, required=True)
    trade_failure_calibration_parser.add_argument(
        "--apply-predictions",
        type=Path,
        help="optional failure-scored prediction frame to calibrate with the final validation calibrator",
    )
    trade_failure_calibration_parser.add_argument(
        "--validation-months",
        required=True,
        help="comma-separated validation dataset months for OOF folds",
    )
    trade_failure_calibration_parser.add_argument("--apply-months", help="comma-separated apply months")
    trade_failure_calibration_parser.add_argument("--target-name", default="large_loss")
    add_group_calibration_args(trade_failure_calibration_parser, "trade_failure_probability_calibration")
    trade_failure_calibration_parser.set_defaults(func=oof_trade_failure_calibration)
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
