from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    r2_score,
)

from trade_data.dataset import (
    EXIT_FIXED_HORIZON_MINUTES,
    PROFIT_BARRIER_HORIZON_MINUTES,
    iter_months,
    output_stem,
)
from trade_data.regime import REGIME_COLUMNS, REGIME_NUMERIC_COLUMNS


EV_TARGETS = [
    "long_best_adjusted_pnl",
    "short_best_adjusted_pnl",
]
EXIT_FIXED_HORIZON_TARGETS = [
    f"{side}_fixed_{minutes}m_adjusted_pnl"
    for minutes in EXIT_FIXED_HORIZON_MINUTES
    for side in ["long", "short"]
]
PROFIT_BARRIER_HORIZON_TARGETS = [
    f"{side}_profit_barrier_hit_{minutes}m"
    for minutes in PROFIT_BARRIER_HORIZON_MINUTES
    for side in ["long", "short"]
]

REGRESSION_TARGETS = [
    *EV_TARGETS,
    *EXIT_FIXED_HORIZON_TARGETS,
    "side_score",
    "long_best_holding_minutes",
    "short_best_holding_minutes",
    "long_exit_event_minutes",
    "short_exit_event_minutes",
    "long_max_adverse_pnl",
    "short_max_adverse_pnl",
    "long_wait_regret",
    "short_wait_regret",
    "long_entry_local_rank",
    "short_entry_local_rank",
    "long_entry_urgency",
    "short_entry_urgency",
]

CLASSIFICATION_TARGETS = [
    "best_adjusted_pnl_quantile",
    "side_score_quantile",
    "long_profit_barrier_hit",
    "short_profit_barrier_hit",
    *PROFIT_BARRIER_HORIZON_TARGETS,
    "long_wait_regret_quantile",
    "short_wait_regret_quantile",
    "long_entry_local_rank_bin",
    "short_entry_local_rank_bin",
    "best_holding_time_bin",
    "long_best_holding_time_bin",
    "short_best_holding_time_bin",
    "long_exit_event",
    "short_exit_event",
    "long_exit_event_time_bin",
    "short_exit_event_time_bin",
    "best_side",
    "label",
]

POLICY_REGRESSION_TARGETS = [
    *EV_TARGETS,
    *EXIT_FIXED_HORIZON_TARGETS,
    "side_score",
    "long_best_holding_minutes",
    "short_best_holding_minutes",
    "long_exit_event_minutes",
    "short_exit_event_minutes",
    "long_max_adverse_pnl",
    "short_max_adverse_pnl",
    "long_wait_regret",
    "short_wait_regret",
    "long_entry_local_rank",
    "short_entry_local_rank",
]

POLICY_CLASSIFICATION_TARGETS = [
    "long_profit_barrier_hit",
    "short_profit_barrier_hit",
    *PROFIT_BARRIER_HORIZON_TARGETS,
    "long_exit_event",
    "short_exit_event",
    "long_exit_event_time_bin",
    "short_exit_event_time_bin",
    "best_side",
    "label",
]

TARGET_SETS = {
    "full": (REGRESSION_TARGETS, CLASSIFICATION_TARGETS),
    "policy": (POLICY_REGRESSION_TARGETS, POLICY_CLASSIFICATION_TARGETS),
    "side_confidence": (EV_TARGETS, ["best_side"]),
    "profit_barrier": ([], ["long_profit_barrier_hit", "short_profit_barrier_hit"]),
}

SELECTION_COLUMNS = {
    "pred_long_best_adjusted_pnl",
    "pred_short_best_adjusted_pnl",
    "long_best_adjusted_pnl",
    "short_best_adjusted_pnl",
}

GENERALIZATION_FEATURE_COLUMNS = [
    "ret_15",
    "ret_60",
    "diff_1",
    "hl_range",
    "gap_minutes",
    "gap_flag",
    "rsi_14",
    "ema_12_dist",
    "ema_26_dist",
    "ema_12_26",
    "hour_sin",
    "hour_cos",
    "dow_sin",
    "dow_cos",
    "roll_z_60",
    "roll_vol_60",
    "roll_return_60",
    "roll_min_dist_60",
    "roll_max_dist_60",
    "atr_60",
    "roll_z_240",
    "roll_vol_240",
    "roll_return_240",
    "roll_min_dist_240",
    "roll_max_dist_240",
    "atr_240",
    "fft_low_power_64",
    "fft_high_power_64",
    "fft_centroid_64",
    "fft_low_power_256",
    "fft_high_power_256",
    "fft_centroid_256",
    *REGIME_NUMERIC_COLUMNS,
]


@dataclass(frozen=True)
class SplitConfig:
    train_start: str | None
    train_end: str | None
    valid_start: str | None
    valid_end: str | None
    test_start: str | None
    test_end: str | None
    train_months: list[str]
    valid_months: list[str]
    test_months: list[str]
    horizon_hours: float
    min_adjusted_edge: float
    purge_label_overlap: bool
    embargo_hours: float


@dataclass(frozen=True)
class ModelConfig:
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
    sample_frac: float
    entry_threshold: float
    target_clip_quantile: float
    sample_weighting: str
    target_set: str


@dataclass(frozen=True)
class LinearCalibrator:
    slope: float
    intercept: float


def dataset_path(dataset_dir: Path, month: str, horizon_hours: float, edge: float) -> Path:
    return dataset_dir / f"{output_stem(month, horizon_hours, edge)}.parquet"


def summary_path(dataset_dir: Path, month: str, horizon_hours: float, edge: float) -> Path:
    return dataset_path(dataset_dir, month, horizon_hours, edge).with_suffix(".summary.json")


def load_feature_columns(dataset_dir: Path, month: str, horizon_hours: float, edge: float) -> list[str]:
    path = summary_path(dataset_dir, month, horizon_hours, edge)
    if not path.exists():
        raise FileNotFoundError(f"summary not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        summary = json.load(handle)
    return list(summary["feature_columns"])


def load_months(
    dataset_dir: Path,
    months: list[str],
    horizon_hours: float,
    edge: float,
) -> tuple[pd.DataFrame, list[str]]:
    if not months:
        raise ValueError("months must not be empty")
    feature_columns = load_feature_columns(dataset_dir, months[0], horizon_hours, edge)
    frames: list[pd.DataFrame] = []
    for month in months:
        path = dataset_path(dataset_dir, month, horizon_hours, edge)
        if not path.exists():
            raise FileNotFoundError(f"dataset not found: {path}")
        expected_features = load_feature_columns(dataset_dir, month, horizon_hours, edge)
        if expected_features != feature_columns:
            raise ValueError(f"feature columns differ for {month}")
        frame = pd.read_parquet(path)
        frame["dataset_month"] = month
        frames.append(frame)
    return pd.concat(frames, ignore_index=True), feature_columns


def parse_csv_months(value: str) -> list[str]:
    months = [part.strip() for part in value.split(",") if part.strip()]
    if not months:
        raise argparse.ArgumentTypeError("at least one month is required")
    for month in months:
        try:
            pd.Timestamp(f"{month}-01")
        except ValueError as exc:
            raise argparse.ArgumentTypeError("months must be in YYYY-MM format") from exc
        if pd.Timestamp(f"{month}-01").strftime("%Y-%m") != month:
            raise argparse.ArgumentTypeError("months must be in YYYY-MM format")
    return months


def resolve_split_months(
    split_name: str,
    explicit_months: str | None,
    start_month: str | None,
    end_month: str | None,
) -> list[str]:
    if explicit_months:
        return parse_csv_months(explicit_months)
    if start_month and end_month:
        return iter_months(start_month, end_month)
    raise ValueError(f"{split_name} requires either --{split_name}-months or --{split_name}-start/--{split_name}-end")


def validate_disjoint_splits(splits: dict[str, list[str]]) -> None:
    seen: dict[str, str] = {}
    for split_name, months in splits.items():
        duplicate_months = sorted({month for month in months if months.count(month) > 1})
        if duplicate_months:
            raise ValueError(f"{split_name} has duplicate months: {', '.join(duplicate_months)}")
        for month in months:
            if month in seen:
                raise ValueError(f"month {month} appears in both {seen[month]} and {split_name}")
            seen[month] = split_name


def label_end_timestamp(df: pd.DataFrame, horizon_hours: float) -> pd.Series:
    horizon = pd.Timedelta(hours=horizon_hours)
    if "entry_timestamp" in df.columns:
        entry = pd.to_datetime(df["entry_timestamp"], utc=True)
        end = entry + horizon
    else:
        end = pd.to_datetime(df["decision_timestamp"], utc=True) + horizon
    fallback = pd.to_datetime(df["decision_timestamp"], utc=True) + horizon
    return end.fillna(fallback)


def label_interval_window(
    df: pd.DataFrame,
    horizon_hours: float,
    embargo_hours: float,
) -> tuple[pd.Timestamp, pd.Timestamp]:
    if df.empty:
        raise ValueError("cannot build label interval window from empty frame")
    embargo = pd.Timedelta(hours=embargo_hours)
    starts = pd.to_datetime(df["decision_timestamp"], utc=True)
    ends = label_end_timestamp(df, horizon_hours)
    return starts.min() - embargo, ends.max() + embargo


def label_interval_windows(
    df: pd.DataFrame,
    horizon_hours: float,
    embargo_hours: float,
) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    if df.empty:
        return []
    if "dataset_month" not in df.columns:
        return [label_interval_window(df, horizon_hours, embargo_hours)]
    return [
        label_interval_window(group, horizon_hours, embargo_hours)
        for _, group in df.groupby("dataset_month", sort=False)
        if not group.empty
    ]


def purge_overlapping_labels(
    source: pd.DataFrame,
    blocked_frames: list[pd.DataFrame],
    horizon_hours: float,
    embargo_hours: float,
) -> tuple[pd.DataFrame, int]:
    if source.empty or not blocked_frames:
        return source, 0
    windows: list[tuple[pd.Timestamp, pd.Timestamp]] = []
    for frame in blocked_frames:
        windows.extend(label_interval_windows(frame, horizon_hours, embargo_hours))
    if not windows:
        return source, 0
    source_start = pd.to_datetime(source["decision_timestamp"], utc=True)
    source_end = label_end_timestamp(source, horizon_hours)
    keep = pd.Series(True, index=source.index)
    for blocked_start, blocked_end in windows:
        overlaps = (source_start <= blocked_end) & (source_end >= blocked_start)
        keep &= ~overlaps
    removed = int((~keep).sum())
    return source.loc[keep].copy(), removed


def apply_split_purging(
    train_df: pd.DataFrame,
    valid_df: pd.DataFrame,
    test_df: pd.DataFrame,
    horizon_hours: float,
    embargo_hours: float,
    enabled: bool,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, object]]:
    stats: dict[str, object] = {
        "enabled": bool(enabled),
        "horizon_hours": float(horizon_hours),
        "embargo_hours": float(embargo_hours),
        "train_rows_before": int(len(train_df)),
        "valid_rows_before": int(len(valid_df)),
        "test_rows_before": int(len(test_df)),
        "train_rows_removed": 0,
        "valid_rows_removed": 0,
    }
    if not enabled:
        stats.update(
            {
                "train_rows_after": int(len(train_df)),
                "valid_rows_after": int(len(valid_df)),
                "test_rows_after": int(len(test_df)),
            }
        )
        return train_df, valid_df, test_df, stats

    purged_train, train_removed = purge_overlapping_labels(
        train_df,
        [valid_df, test_df],
        horizon_hours,
        embargo_hours,
    )
    purged_valid, valid_removed = purge_overlapping_labels(
        valid_df,
        [test_df],
        horizon_hours,
        embargo_hours,
    )
    stats.update(
        {
            "train_rows_removed": train_removed,
            "valid_rows_removed": valid_removed,
            "train_rows_after": int(len(purged_train)),
            "valid_rows_after": int(len(purged_valid)),
            "test_rows_after": int(len(test_df)),
        }
    )
    if purged_train.empty:
        raise ValueError("purging removed all train rows")
    if purged_valid.empty:
        raise ValueError("purging removed all validation rows")
    return purged_train, purged_valid, test_df, stats


def split_months_from_args(args: argparse.Namespace) -> tuple[list[str], list[str], list[str]]:
    train_months = resolve_split_months("train", args.train_months, args.train_start, args.train_end)
    valid_months = resolve_split_months("valid", args.valid_months, args.valid_start, args.valid_end)
    test_months = resolve_split_months("test", args.test_months, args.test_start, args.test_end)
    validate_disjoint_splits({"train": train_months, "valid": valid_months, "test": test_months})
    return train_months, valid_months, test_months


def build_sample_weights(df: pd.DataFrame, weighting: str) -> np.ndarray | None:
    if weighting == "none":
        return None
    weights = pd.Series(1.0, index=df.index, dtype="float64")
    if weighting == "month":
        month_counts = df["dataset_month"].value_counts()
        weights *= df["dataset_month"].map(1.0 / month_counts)
    elif weighting == "label":
        label_counts = df["label"].value_counts()
        weights *= df["label"].map(1.0 / label_counts)
    elif weighting == "month_label":
        group_counts = df.groupby(["dataset_month", "label"])["label"].transform("size")
        weights *= 1.0 / group_counts
    elif weighting != "none":
        raise ValueError(f"unknown sample weighting: {weighting}")
    weights = weights / weights.mean()
    return weights.to_numpy(dtype="float64")


def split_summary(df: pd.DataFrame) -> dict[str, object]:
    label_counts = df["label"].value_counts().sort_index()
    month_counts = df["dataset_month"].value_counts().sort_index()
    return {
        "label_counts": {str(int(label)): int(count) for label, count in label_counts.items()},
        "month_rows": {str(month): int(count) for month, count in month_counts.items()},
    }


def month_counts(df: pd.DataFrame) -> dict[str, int]:
    if "dataset_month" not in df.columns:
        return {}
    counts = df["dataset_month"].value_counts().sort_index()
    return {str(month): int(count) for month, count in counts.items()}


def resolve_target_names(target_set: str) -> tuple[list[str], list[str]]:
    if target_set not in TARGET_SETS:
        raise ValueError(f"unknown target_set: {target_set}")
    regression_targets, classification_targets = TARGET_SETS[target_set]
    return list(regression_targets), list(classification_targets)


def filter_available_target_names(
    frames: list[pd.DataFrame],
    regression_targets: list[str],
    classification_targets: list[str],
) -> tuple[list[str], list[str], dict[str, list[str]]]:
    if not frames:
        raise ValueError("at least one frame is required")
    available = set(frames[0].columns)
    for frame in frames[1:]:
        available &= set(frame.columns)
    filtered_regression = [target for target in regression_targets if target in available]
    filtered_classification = [target for target in classification_targets if target in available]
    missing = {
        "regression": [target for target in regression_targets if target not in available],
        "classification": [target for target in classification_targets if target not in available],
    }
    if not filtered_regression and not filtered_classification:
        raise ValueError("no requested targets are available in all frames")
    return filtered_regression, filtered_classification, missing


def maybe_sample(df: pd.DataFrame, sample_frac: float, random_seed: int) -> pd.DataFrame:
    if sample_frac >= 1.0:
        return df
    if not 0 < sample_frac <= 1:
        raise ValueError("sample_frac must be in (0, 1]")
    return df.sample(frac=sample_frac, random_state=random_seed).sort_values("decision_timestamp")


def as_matrix(df: pd.DataFrame, feature_columns: list[str]) -> np.ndarray:
    return df[feature_columns].astype("float32").to_numpy()


def train_regressor(config: ModelConfig) -> HistGradientBoostingRegressor:
    return HistGradientBoostingRegressor(
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


def train_classifier(config: ModelConfig) -> HistGradientBoostingClassifier:
    return HistGradientBoostingClassifier(
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


def model_config_from_args(args: argparse.Namespace) -> ModelConfig:
    return ModelConfig(
        max_iter=args.max_iter,
        learning_rate=args.learning_rate,
        max_leaf_nodes=args.max_leaf_nodes,
        max_depth=None if args.max_depth <= 0 else args.max_depth,
        l2_regularization=args.l2_regularization,
        max_features=args.max_features,
        early_stopping=args.early_stopping,
        validation_fraction=args.validation_fraction,
        n_iter_no_change=args.n_iter_no_change,
        tol=args.tol,
        random_seed=args.random_seed,
        sample_frac=args.sample_frac,
        entry_threshold=args.entry_threshold,
        min_samples_leaf=args.min_samples_leaf,
        target_clip_quantile=args.target_clip_quantile,
        sample_weighting=args.sample_weighting,
        target_set=args.target_set,
    )


def regression_training_values(series: pd.Series, clip_quantile: float) -> np.ndarray:
    values = series.astype(float)
    if clip_quantile >= 1.0:
        return values.to_numpy()
    if not 0.5 < clip_quantile <= 1.0:
        raise ValueError("target_clip_quantile must be in (0.5, 1.0]")
    lower = values.quantile(1.0 - clip_quantile)
    upper = values.quantile(clip_quantile)
    return values.clip(lower=lower, upper=upper).to_numpy()


def regression_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    return {
        "mae": float(mean_absolute_error(y_true, y_pred)),
        "rmse": float(mean_squared_error(y_true, y_pred) ** 0.5),
        "r2": float(r2_score(y_true, y_pred)),
    }


def classification_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "balanced_accuracy": float(balanced_accuracy_score(y_true, y_pred)),
        "macro_f1": float(f1_score(y_true, y_pred, average="macro")),
    }


def classifier_probability_predictions(
    target: str,
    model: object,
    x: np.ndarray,
) -> dict[str, np.ndarray]:
    if not hasattr(model, "predict_proba"):
        return {}
    classes = list(getattr(model, "classes_", []))
    if not classes:
        return {}
    probabilities = model.predict_proba(x)
    predictions: dict[str, np.ndarray] = {}
    for class_index, class_value in enumerate(classes):
        predictions[f"{target}_prob_{class_value}"] = probabilities[:, class_index]
    if set(classes) <= {0, 1} and 1 in classes:
        predictions[f"{target}_prob"] = probabilities[:, classes.index(1)]
    return predictions


def prediction_frame(df: pd.DataFrame, predictions: dict[str, np.ndarray]) -> pd.DataFrame:
    columns = [
        "decision_timestamp",
        "entry_timestamp",
        "dataset_month",
        "label",
        "best_side",
        "long_best_adjusted_pnl",
        "short_best_adjusted_pnl",
        *EXIT_FIXED_HORIZON_TARGETS,
        "side_score",
        "best_adjusted_pnl",
        "best_holding_minutes",
        "long_best_holding_minutes",
        "short_best_holding_minutes",
        "long_exit_event",
        "short_exit_event",
        "long_exit_event_minutes",
        "short_exit_event_minutes",
        "long_exit_event_time_bin",
        "short_exit_event_time_bin",
        "long_max_adverse_pnl",
        "short_max_adverse_pnl",
        "long_profit_barrier_hit",
        "short_profit_barrier_hit",
        "long_wait_regret",
        "short_wait_regret",
        "long_entry_local_rank",
        "short_entry_local_rank",
        "long_entry_urgency",
        "short_entry_urgency",
        "long_wait_regret_quantile",
        "short_wait_regret_quantile",
        "long_entry_local_rank_bin",
        "short_entry_local_rank_bin",
    ]
    columns.extend([column for column in GENERALIZATION_FEATURE_COLUMNS if column in df.columns])
    columns.extend([column for column in REGIME_COLUMNS if column in df.columns])
    columns = [column for column in dict.fromkeys(columns) if column in df.columns]
    output = df[columns].copy()
    for name, values in predictions.items():
        output[f"pred_{name}"] = values
    return output


def selection_metrics(
    predictions: pd.DataFrame,
    threshold: float,
    long_column: str = "pred_long_best_adjusted_pnl",
    short_column: str = "pred_short_best_adjusted_pnl",
) -> dict[str, object]:
    pred_long = predictions[long_column]
    pred_short = predictions[short_column]
    best_pred = pd.concat([pred_long, pred_short], axis=1).max(axis=1)
    side = np.where(pred_long >= pred_short, 1, -1)
    trade_mask = best_pred > threshold
    chosen_actual = np.where(
        side == 1,
        predictions["long_best_adjusted_pnl"],
        predictions["short_best_adjusted_pnl"],
    )
    selected = pd.Series(np.where(trade_mask, chosen_actual, 0.0), index=predictions.index)
    best_actual = predictions[["long_best_adjusted_pnl", "short_best_adjusted_pnl"]].max(axis=1)
    oracle_selected = best_actual.where(best_actual > threshold, 0.0)
    actual_best_side = np.where(
        predictions["long_best_adjusted_pnl"] >= predictions["short_best_adjusted_pnl"],
        1,
        -1,
    )
    predicted_side = pd.Series(side, index=predictions.index)
    actual_best_side = pd.Series(actual_best_side, index=predictions.index)
    side_accuracy = float((predicted_side[trade_mask] == actual_best_side[trade_mask]).mean()) if trade_mask.any() else 0.0
    return {
        "entry_threshold": threshold,
        "selected_trade_count": int(trade_mask.sum()),
        "selected_oracle_exit_adjusted_pnl": float(selected.sum()),
        "selected_avg_adjusted_pnl": float(selected[trade_mask].mean()) if trade_mask.any() else 0.0,
        "selected_side_accuracy": side_accuracy,
        "oracle_trade_count": int((best_actual > threshold).sum()),
        "oracle_exit_adjusted_pnl_upper_bound": float(oracle_selected.sum()),
    }


def prediction_split_from_path(path: Path) -> str:
    stem = path.stem
    if stem.startswith("predictions_"):
        return stem.removeprefix("predictions_")
    return stem


def side_confidence_frame(
    predictions: pd.DataFrame,
    long_probability_column: str = "pred_best_side_prob_1",
    short_probability_column: str = "pred_best_side_prob_-1",
) -> pd.DataFrame:
    required_columns = ["best_side", long_probability_column, short_probability_column]
    missing_columns = [column for column in required_columns if column not in predictions.columns]
    if missing_columns:
        raise ValueError(f"missing side confidence columns: {', '.join(missing_columns)}")

    output = predictions.copy()
    long_probability = output[long_probability_column].astype(float)
    short_probability = output[short_probability_column].astype(float)
    output["side_confidence_predicted_side"] = np.where(long_probability >= short_probability, 1, -1)
    output["side_confidence"] = np.where(
        output["side_confidence_predicted_side"] == 1,
        long_probability,
        short_probability,
    )
    output["side_confidence_margin"] = (long_probability - short_probability).abs()
    output["side_confidence_hit"] = (
        output["side_confidence_predicted_side"].astype(int) == output["best_side"].astype(int)
    )
    return output


def safe_side_balanced_accuracy(actual: pd.Series, predicted: pd.Series) -> float:
    actual_values = actual.astype(int)
    predicted_values = predicted.astype(int)
    recalls: list[float] = []
    for class_value in sorted(actual_values.dropna().unique()):
        class_mask = actual_values == class_value
        if class_mask.any():
            recalls.append(float((predicted_values[class_mask] == class_value).mean()))
    return float(np.mean(recalls)) if recalls else 0.0


def side_confidence_summary_row(frame: pd.DataFrame, group_key: str, group_value: str) -> dict[str, object]:
    if frame.empty:
        return {
            "group_key": group_key,
            "group_value": group_value,
            "rows": 0,
            "accuracy": 0.0,
            "balanced_accuracy": 0.0,
            "confidence_mean": 0.0,
            "confidence_median": 0.0,
            "calibration_error": 0.0,
            "overconfidence": 0.0,
            "underconfidence": 0.0,
            "predicted_long_share": 0.0,
            "actual_long_share": 0.0,
            "high_confidence_share": 0.0,
        }
    accuracy = float(frame["side_confidence_hit"].mean())
    confidence_mean = float(frame["side_confidence"].mean())
    calibration_error = confidence_mean - accuracy
    return {
        "group_key": group_key,
        "group_value": group_value,
        "rows": int(len(frame)),
        "accuracy": accuracy,
        "balanced_accuracy": safe_side_balanced_accuracy(
            frame["best_side"],
            frame["side_confidence_predicted_side"],
        ),
        "confidence_mean": confidence_mean,
        "confidence_median": float(frame["side_confidence"].median()),
        "calibration_error": float(calibration_error),
        "overconfidence": float(max(calibration_error, 0.0)),
        "underconfidence": float(max(-calibration_error, 0.0)),
        "predicted_long_share": float((frame["side_confidence_predicted_side"] == 1).mean()),
        "actual_long_share": float((frame["best_side"].astype(int) == 1).mean()),
        "high_confidence_share": float((frame["side_confidence"] >= 0.75).mean()),
    }


def side_confidence_group_metrics(
    predictions: pd.DataFrame,
    group_columns: list[str],
    min_rows: int = 1,
) -> pd.DataFrame:
    frame = side_confidence_frame(predictions)
    rows = [side_confidence_summary_row(frame, "overall", "all")]
    available_columns = [column for column in group_columns if column in frame.columns]
    for column in available_columns:
        grouped = frame.groupby(column, dropna=False, sort=True)
        for value, group in grouped:
            if len(group) >= min_rows:
                rows.append(side_confidence_summary_row(group, column, str(value)))
    if "prediction_split" in frame.columns:
        for column in available_columns:
            if column == "prediction_split":
                continue
            grouped = frame.groupby(["prediction_split", column], dropna=False, sort=True)
            for (split, value), group in grouped:
                if len(group) >= min_rows:
                    rows.append(
                        side_confidence_summary_row(
                            group,
                            f"prediction_split:{column}",
                            f"{split}|{value}",
                        )
                    )
    return pd.DataFrame(rows)


def side_confidence_bucket_metrics(
    predictions: pd.DataFrame,
    bucket_count: int = 5,
    min_confidence: float = 0.5,
) -> pd.DataFrame:
    if bucket_count <= 0:
        raise ValueError("bucket_count must be positive")
    if not 0 <= min_confidence < 1:
        raise ValueError("min_confidence must be in [0, 1)")
    frame = side_confidence_frame(predictions)
    edges = np.linspace(min_confidence, 1.0, bucket_count + 1)
    bucket_indexes = np.searchsorted(edges, frame["side_confidence"], side="right") - 1
    frame = frame.copy()
    frame["confidence_bucket_index"] = np.clip(bucket_indexes, 0, bucket_count - 1)
    rows: list[dict[str, object]] = []
    grouping_columns = ["confidence_bucket_index"]
    if "prediction_split" in frame.columns:
        grouping_columns = ["prediction_split", "confidence_bucket_index"]
    for keys, group in frame.groupby(grouping_columns, dropna=False, sort=True):
        if isinstance(keys, tuple):
            split, bucket_index = keys
        else:
            split, bucket_index = "all", keys
        bucket_index = int(bucket_index)
        lower = float(edges[bucket_index])
        upper = float(edges[bucket_index + 1])
        row = side_confidence_summary_row(group, "confidence_bucket", f"{lower:.2f}-{upper:.2f}")
        row.update(
            {
                "prediction_split": str(split),
                "bucket_index": bucket_index,
                "bucket_lower": lower,
                "bucket_upper": upper,
            }
        )
        rows.append(row)
    return pd.DataFrame(rows)


def profit_barrier_frame(
    predictions: pd.DataFrame,
    long_actual_column: str = "long_profit_barrier_hit",
    short_actual_column: str = "short_profit_barrier_hit",
    long_probability_column: str = "pred_long_profit_barrier_hit_prob_1",
    short_probability_column: str = "pred_short_profit_barrier_hit_prob_1",
) -> pd.DataFrame:
    required_columns = [
        long_actual_column,
        short_actual_column,
        long_probability_column,
        short_probability_column,
    ]
    missing_columns = [column for column in required_columns if column not in predictions.columns]
    if missing_columns:
        raise ValueError(f"missing profit barrier columns: {', '.join(missing_columns)}")

    metadata_columns = [
        column
        for column in [
            "prediction_file",
            "prediction_split",
            "decision_timestamp",
            "entry_timestamp",
            "dataset_month",
            *REGIME_COLUMNS,
        ]
        if column in predictions.columns
    ]
    frames: list[pd.DataFrame] = []
    for side, actual_column, probability_column in [
        ("long", long_actual_column, long_probability_column),
        ("short", short_actual_column, short_probability_column),
    ]:
        side_frame = predictions[metadata_columns].copy()
        side_frame["barrier_side"] = side
        side_frame["profit_barrier_actual"] = predictions[actual_column].astype(float)
        side_frame["profit_barrier_probability"] = predictions[probability_column].astype(float)
        frames.append(side_frame)
    output = pd.concat(frames, ignore_index=True)
    return output.replace([np.inf, -np.inf], np.nan).dropna(
        subset=["profit_barrier_actual", "profit_barrier_probability"]
    )


def profit_barrier_summary_row(
    frame: pd.DataFrame,
    group_key: str,
    group_value: str,
    threshold: float,
) -> dict[str, object]:
    if frame.empty:
        return {
            "group_key": group_key,
            "group_value": group_value,
            "rows": 0,
            "actual_hit_rate": 0.0,
            "predicted_probability_mean": 0.0,
            "predicted_probability_median": 0.0,
            "calibration_error": 0.0,
            "overestimate": 0.0,
            "underestimate": 0.0,
            "brier_score": 0.0,
            "predicted_hit_rate": 0.0,
            "threshold_accuracy": 0.0,
            "long_side_share": 0.0,
        }
    actual = frame["profit_barrier_actual"].astype(float)
    probability = frame["profit_barrier_probability"].astype(float).clip(0.0, 1.0)
    actual_hit_rate = float(actual.mean())
    probability_mean = float(probability.mean())
    calibration_error = probability_mean - actual_hit_rate
    predicted_hit = probability >= threshold
    actual_hit = actual >= 0.5
    return {
        "group_key": group_key,
        "group_value": group_value,
        "rows": int(len(frame)),
        "actual_hit_rate": actual_hit_rate,
        "predicted_probability_mean": probability_mean,
        "predicted_probability_median": float(probability.median()),
        "calibration_error": float(calibration_error),
        "overestimate": float(max(calibration_error, 0.0)),
        "underestimate": float(max(-calibration_error, 0.0)),
        "brier_score": float(((probability - actual) ** 2).mean()),
        "predicted_hit_rate": float(predicted_hit.mean()),
        "threshold_accuracy": float((predicted_hit == actual_hit).mean()),
        "long_side_share": float((frame["barrier_side"] == "long").mean()),
    }


def profit_barrier_group_metrics(
    predictions: pd.DataFrame,
    group_columns: list[str],
    min_rows: int = 1,
    threshold: float = 0.5,
    long_actual_column: str = "long_profit_barrier_hit",
    short_actual_column: str = "short_profit_barrier_hit",
    long_probability_column: str = "pred_long_profit_barrier_hit_prob_1",
    short_probability_column: str = "pred_short_profit_barrier_hit_prob_1",
) -> pd.DataFrame:
    frame = profit_barrier_frame(
        predictions,
        long_actual_column=long_actual_column,
        short_actual_column=short_actual_column,
        long_probability_column=long_probability_column,
        short_probability_column=short_probability_column,
    )
    rows = [profit_barrier_summary_row(frame, "overall", "all", threshold)]
    available_columns = [column for column in group_columns if column in frame.columns]
    for column in available_columns:
        grouped = frame.groupby(column, dropna=False, sort=True)
        for value, group in grouped:
            if len(group) >= min_rows:
                rows.append(profit_barrier_summary_row(group, column, str(value), threshold))
    if "prediction_split" in frame.columns:
        for column in available_columns:
            if column == "prediction_split":
                continue
            grouped = frame.groupby(["prediction_split", column], dropna=False, sort=True)
            for (split, value), group in grouped:
                if len(group) >= min_rows:
                    rows.append(
                        profit_barrier_summary_row(
                            group,
                            f"prediction_split:{column}",
                            f"{split}|{value}",
                            threshold,
                        )
                    )
    return pd.DataFrame(rows)


def profit_barrier_bucket_metrics(
    predictions: pd.DataFrame,
    bucket_count: int = 5,
    min_probability: float = 0.0,
    threshold: float = 0.5,
    long_actual_column: str = "long_profit_barrier_hit",
    short_actual_column: str = "short_profit_barrier_hit",
    long_probability_column: str = "pred_long_profit_barrier_hit_prob_1",
    short_probability_column: str = "pred_short_profit_barrier_hit_prob_1",
) -> pd.DataFrame:
    if bucket_count <= 0:
        raise ValueError("bucket_count must be positive")
    if not 0 <= min_probability < 1:
        raise ValueError("min_probability must be in [0, 1)")
    frame = profit_barrier_frame(
        predictions,
        long_actual_column=long_actual_column,
        short_actual_column=short_actual_column,
        long_probability_column=long_probability_column,
        short_probability_column=short_probability_column,
    )
    edges = np.linspace(min_probability, 1.0, bucket_count + 1)
    bucket_indexes = np.searchsorted(edges, frame["profit_barrier_probability"], side="right") - 1
    frame = frame.copy()
    frame["probability_bucket_index"] = np.clip(bucket_indexes, 0, bucket_count - 1)
    rows: list[dict[str, object]] = []
    grouping_columns = ["probability_bucket_index"]
    if "prediction_split" in frame.columns:
        grouping_columns = ["prediction_split", "probability_bucket_index"]
    for keys, group in frame.groupby(grouping_columns, dropna=False, sort=True):
        if isinstance(keys, tuple):
            split, bucket_index = keys
        else:
            split, bucket_index = "all", keys
        bucket_index = int(bucket_index)
        lower = float(edges[bucket_index])
        upper = float(edges[bucket_index + 1])
        row = profit_barrier_summary_row(
            group,
            "probability_bucket",
            f"{lower:.2f}-{upper:.2f}",
            threshold,
        )
        row.update(
            {
                "prediction_split": str(split),
                "bucket_index": bucket_index,
                "bucket_lower": lower,
                "bucket_upper": upper,
            }
        )
        rows.append(row)
    return pd.DataFrame(rows)


def load_report_predictions(paths: list[Path]) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for path in paths:
        frame = pd.read_parquet(path)
        frame["prediction_file"] = str(path)
        frame["prediction_split"] = prediction_split_from_path(path)
        frames.append(frame)
    if not frames:
        raise ValueError("at least one prediction file is required")
    return pd.concat(frames, ignore_index=True)


def parse_csv_strings(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def handle_side_confidence_report(args: argparse.Namespace) -> int:
    predictions = load_report_predictions(args.predictions)
    group_columns = parse_csv_strings(args.group_columns)
    group_metrics = side_confidence_group_metrics(
        predictions,
        group_columns,
        min_rows=args.min_group_rows,
    )
    bucket_metrics = side_confidence_bucket_metrics(
        predictions,
        bucket_count=args.bucket_count,
        min_confidence=args.min_confidence,
    )
    eligible_groups = group_metrics.loc[group_metrics["rows"] >= args.min_group_rows].copy()
    worst_groups = eligible_groups.sort_values(
        ["overconfidence", "rows"],
        ascending=[False, False],
    ).head(args.top_n)
    output_dir = make_run_dir(args.output_dir, args.label or "side_confidence_report")
    group_metrics.to_csv(output_dir / "group_metrics.csv", index=False)
    bucket_metrics.to_csv(output_dir / "bucket_metrics.csv", index=False)
    worst_groups.to_csv(output_dir / "worst_groups.csv", index=False)
    summary = {
        "prediction_files": [str(path) for path in args.predictions],
        "rows": int(len(predictions)),
        "group_columns": group_columns,
        "min_group_rows": args.min_group_rows,
        "bucket_count": args.bucket_count,
        "min_confidence": args.min_confidence,
        "overall": group_metrics.iloc[0].to_dict(),
        "worst_groups": worst_groups.to_dict(orient="records"),
    }
    with (output_dir / "summary.json").open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2)
    print(json.dumps(summary["overall"], ensure_ascii=False, indent=2))
    print(f"artifacts: {output_dir}")
    return 0


def handle_profit_barrier_report(args: argparse.Namespace) -> int:
    predictions = load_report_predictions(args.predictions)
    group_columns = parse_csv_strings(args.group_columns)
    group_metrics = profit_barrier_group_metrics(
        predictions,
        group_columns,
        min_rows=args.min_group_rows,
        threshold=args.threshold,
        long_actual_column=args.long_actual_column,
        short_actual_column=args.short_actual_column,
        long_probability_column=args.long_probability_column,
        short_probability_column=args.short_probability_column,
    )
    bucket_metrics = profit_barrier_bucket_metrics(
        predictions,
        bucket_count=args.bucket_count,
        min_probability=args.min_probability,
        threshold=args.threshold,
        long_actual_column=args.long_actual_column,
        short_actual_column=args.short_actual_column,
        long_probability_column=args.long_probability_column,
        short_probability_column=args.short_probability_column,
    )
    eligible_groups = group_metrics.loc[group_metrics["rows"] >= args.min_group_rows].copy()
    worst_groups = eligible_groups.sort_values(
        ["overestimate", "rows"],
        ascending=[False, False],
    ).head(args.top_n)
    output_dir = make_run_dir(args.output_dir, args.label or "profit_barrier_report")
    group_metrics.to_csv(output_dir / "group_metrics.csv", index=False)
    bucket_metrics.to_csv(output_dir / "bucket_metrics.csv", index=False)
    worst_groups.to_csv(output_dir / "worst_groups.csv", index=False)
    summary = {
        "prediction_files": [str(path) for path in args.predictions],
        "rows": int(len(predictions)),
        "stacked_rows": int(group_metrics.iloc[0]["rows"]),
        "group_columns": group_columns,
        "min_group_rows": args.min_group_rows,
        "bucket_count": args.bucket_count,
        "min_probability": args.min_probability,
        "threshold": args.threshold,
        "long_actual_column": args.long_actual_column,
        "short_actual_column": args.short_actual_column,
        "long_probability_column": args.long_probability_column,
        "short_probability_column": args.short_probability_column,
        "overall": group_metrics.iloc[0].to_dict(),
        "worst_groups": worst_groups.to_dict(orient="records"),
    }
    with (output_dir / "summary.json").open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2)
    print(json.dumps(summary["overall"], ensure_ascii=False, indent=2))
    print(f"artifacts: {output_dir}")
    return 0


def fit_linear_calibrator(y_true: pd.Series, y_pred: pd.Series) -> LinearCalibrator:
    frame = pd.DataFrame({"y_true": y_true, "y_pred": y_pred}).replace([np.inf, -np.inf], np.nan).dropna()
    if len(frame) < 2:
        return LinearCalibrator(slope=1.0, intercept=0.0)
    pred = frame["y_pred"].astype(float)
    true = frame["y_true"].astype(float)
    variance = float(((pred - pred.mean()) ** 2).mean())
    if variance <= 1e-12:
        return LinearCalibrator(slope=1.0, intercept=float(true.mean() - pred.mean()))
    covariance = float(((pred - pred.mean()) * (true - true.mean())).mean())
    slope = covariance / variance
    intercept = float(true.mean() - slope * pred.mean())
    return LinearCalibrator(slope=float(slope), intercept=intercept)


def fit_ev_calibrators(valid_predictions: pd.DataFrame) -> dict[str, LinearCalibrator]:
    calibrators: dict[str, LinearCalibrator] = {}
    for target in EV_TARGETS:
        calibrators[target] = fit_linear_calibrator(
            valid_predictions[target],
            valid_predictions[f"pred_{target}"],
        )
    return calibrators


def add_calibrated_ev_columns(
    predictions: pd.DataFrame,
    calibrators: dict[str, LinearCalibrator],
) -> pd.DataFrame:
    output = predictions.copy()
    for target, calibrator in calibrators.items():
        output[f"pred_calibrated_{target}"] = (
            output[f"pred_{target}"].astype(float) * calibrator.slope + calibrator.intercept
        )
    return output


def calibrated_regression_metrics(predictions: pd.DataFrame) -> dict[str, dict[str, float]]:
    metrics: dict[str, dict[str, float]] = {}
    for target in EV_TARGETS:
        metrics[target] = regression_metrics(
            predictions[target].to_numpy(),
            predictions[f"pred_calibrated_{target}"].to_numpy(),
        )
    return metrics


def evaluate_models(
    models: dict[str, object],
    df: pd.DataFrame,
    feature_columns: list[str],
    regression_targets: list[str] | None = None,
    classification_targets: list[str] | None = None,
) -> tuple[dict[str, dict[str, float]], dict[str, np.ndarray]]:
    if regression_targets is None:
        regression_targets = REGRESSION_TARGETS
    if classification_targets is None:
        classification_targets = CLASSIFICATION_TARGETS
    x = as_matrix(df, feature_columns)
    metrics: dict[str, dict[str, float]] = {"regression": {}, "classification": {}}
    predictions: dict[str, np.ndarray] = {}
    for target in regression_targets:
        pred = models[target].predict(x)
        predictions[target] = pred
        metrics["regression"][target] = regression_metrics(df[target].to_numpy(), pred)
    for target in classification_targets:
        model = models[target]
        pred = model.predict(x)
        predictions[target] = pred
        metrics["classification"][target] = classification_metrics(df[target].astype(int).to_numpy(), pred)
        predictions.update(classifier_probability_predictions(target, model, x))
    return metrics, predictions


def model_diagnostics(models: dict[str, object], config: ModelConfig) -> dict[str, dict[str, object]]:
    diagnostics: dict[str, dict[str, object]] = {}
    for target, model in models.items():
        train_score = getattr(model, "train_score_", None)
        validation_score = getattr(model, "validation_score_", None)
        n_iter = int(getattr(model, "n_iter_", config.max_iter))
        diagnostics[target] = {
            "n_iter": n_iter,
            "max_iter": config.max_iter,
            "hit_max_iter": bool(n_iter >= config.max_iter),
            "early_stopping_enabled": bool(config.early_stopping),
            "train_score_final": None if train_score is None or len(train_score) == 0 else float(train_score[-1]),
            "validation_score_final": None
            if validation_score is None or len(validation_score) == 0
            else float(validation_score[-1]),
        }
    return diagnostics


def fit_models(
    train_df: pd.DataFrame,
    feature_columns: list[str],
    config: ModelConfig,
    regression_targets: list[str],
    classification_targets: list[str],
    log_prefix: str = "",
) -> dict[str, object]:
    sample_weight = build_sample_weights(train_df, config.sample_weighting)
    x_train = as_matrix(train_df, feature_columns)
    models: dict[str, object] = {}
    prefix = f"{log_prefix} " if log_prefix else ""
    for target in regression_targets:
        print(f"{prefix}train regressor: {target}")
        model = train_regressor(config)
        model.fit(
            x_train,
            regression_training_values(train_df[target], config.target_clip_quantile),
            sample_weight=sample_weight,
        )
        models[target] = model
    for target in classification_targets:
        print(f"{prefix}train classifier: {target}")
        model = train_classifier(config)
        model.fit(x_train, train_df[target].astype(int).to_numpy(), sample_weight=sample_weight)
        models[target] = model
    return models


def chunk_months(months: list[str], chunk_size: int) -> list[list[str]]:
    if chunk_size <= 0:
        raise ValueError("fold month count must be positive")
    return [months[index : index + chunk_size] for index in range(0, len(months), chunk_size)]


def prediction_frame_evaluation_metrics(
    pred_frame: pd.DataFrame,
    regression_targets: list[str],
    classification_targets: list[str],
    entry_threshold: float,
) -> dict[str, object]:
    metrics: dict[str, object] = {"regression": {}, "classification": {}}
    for target in regression_targets:
        pred_column = f"pred_{target}"
        if target in pred_frame.columns and pred_column in pred_frame.columns:
            metrics["regression"][target] = regression_metrics(
                pred_frame[target].to_numpy(),
                pred_frame[pred_column].to_numpy(),
            )
    for target in classification_targets:
        pred_column = f"pred_{target}"
        if target in pred_frame.columns and pred_column in pred_frame.columns:
            metrics["classification"][target] = classification_metrics(
                pred_frame[target].astype(int).to_numpy(),
                pred_frame[pred_column].astype(int).to_numpy(),
            )
    if SELECTION_COLUMNS.issubset(pred_frame.columns):
        metrics["selection"] = selection_metrics(pred_frame, entry_threshold)
    return metrics


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


def parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "y"}:
        return True
    if normalized in {"0", "false", "no", "n"}:
        return False
    raise argparse.ArgumentTypeError("value must be true/false")


def train(args: argparse.Namespace) -> int:
    train_months, valid_months, test_months = split_months_from_args(args)
    split = SplitConfig(
        train_start=args.train_start,
        train_end=args.train_end,
        valid_start=args.valid_start,
        valid_end=args.valid_end,
        test_start=args.test_start,
        test_end=args.test_end,
        train_months=train_months,
        valid_months=valid_months,
        test_months=test_months,
        horizon_hours=args.horizon_hours,
        min_adjusted_edge=args.min_adjusted_edge,
        purge_label_overlap=args.purge_label_overlap,
        embargo_hours=args.embargo_hours,
    )
    model_config = model_config_from_args(args)
    regression_targets, classification_targets = resolve_target_names(args.target_set)

    train_df, feature_columns = load_months(
        args.dataset_dir,
        train_months,
        args.horizon_hours,
        args.min_adjusted_edge,
    )
    valid_df, _ = load_months(args.dataset_dir, valid_months, args.horizon_hours, args.min_adjusted_edge)
    test_df, _ = load_months(args.dataset_dir, test_months, args.horizon_hours, args.min_adjusted_edge)
    regression_targets, classification_targets, missing_targets = filter_available_target_names(
        [train_df, valid_df, test_df],
        regression_targets,
        classification_targets,
    )
    train_df, valid_df, test_df, purge_stats = apply_split_purging(
        train_df,
        valid_df,
        test_df,
        horizon_hours=args.horizon_hours,
        embargo_hours=args.embargo_hours,
        enabled=args.purge_label_overlap,
    )
    train_df = maybe_sample(train_df, args.sample_frac, args.random_seed)

    models = fit_models(
        train_df,
        feature_columns,
        model_config,
        regression_targets,
        classification_targets,
    )

    metrics: dict[str, object] = {
        "split": asdict(split),
        "model_config": asdict(model_config),
        "rows": {
            "train": int(len(train_df)),
            "valid": int(len(valid_df)),
            "test": int(len(test_df)),
        },
        "split_summary": {
            "train": split_summary(train_df),
            "valid": split_summary(valid_df),
            "test": split_summary(test_df),
        },
        "months": {
            "train": train_months,
            "valid": valid_months,
            "test": test_months,
        },
        "feature_count": len(feature_columns),
        "target_set": args.target_set,
        "regression_targets": regression_targets,
        "classification_targets": classification_targets,
        "missing_targets": missing_targets,
        "purging": purge_stats,
        "model_diagnostics": model_diagnostics(models, model_config),
    }
    metrics_by_split: dict[str, dict[str, object]] = {}
    predictions_by_split: dict[str, pd.DataFrame] = {}
    for split_name, frame in [("train", train_df), ("valid", valid_df), ("test", test_df)]:
        split_metrics, predictions = evaluate_models(
            models,
            frame,
            feature_columns,
            regression_targets,
            classification_targets,
        )
        pred_frame = prediction_frame(frame, predictions)
        split_metrics["selection"] = selection_metrics(pred_frame, args.entry_threshold)
        metrics_by_split[split_name] = split_metrics
        predictions_by_split[split_name] = pred_frame

    calibrators = fit_ev_calibrators(predictions_by_split["valid"])
    metrics["calibration"] = {target: asdict(calibrator) for target, calibrator in calibrators.items()}
    for split_name, pred_frame in predictions_by_split.items():
        pred_frame = add_calibrated_ev_columns(pred_frame, calibrators)
        metrics_by_split[split_name]["selection_calibrated"] = selection_metrics(
            pred_frame,
            args.entry_threshold,
            long_column="pred_calibrated_long_best_adjusted_pnl",
            short_column="pred_calibrated_short_best_adjusted_pnl",
        )
        metrics_by_split[split_name]["regression_calibrated"] = calibrated_regression_metrics(pred_frame)
        metrics[split_name] = metrics_by_split[split_name]
        predictions_by_split[split_name] = pred_frame

    run_label = args.label or f"hgb_{args.target_set}_edge{args.min_adjusted_edge:g}"
    run_dir = make_run_dir(args.output_dir, run_label)
    model_dir = run_dir / "models"
    model_dir.mkdir(parents=True, exist_ok=True)
    for target, model in models.items():
        joblib.dump(model, model_dir / f"{target}.joblib")
    for split_name, pred_frame in predictions_by_split.items():
        pred_frame.to_parquet(run_dir / f"predictions_{split_name}.parquet", index=False)
    with (run_dir / "feature_columns.json").open("w", encoding="utf-8") as handle:
        json.dump(feature_columns, handle, ensure_ascii=False, indent=2)
    with (run_dir / "metrics.json").open("w", encoding="utf-8") as handle:
        json.dump(metrics, handle, ensure_ascii=False, indent=2)
    write_report(run_dir, metrics)
    print(json.dumps(metrics["valid"], indent=2))
    print(json.dumps(metrics["test"], indent=2))
    print(f"artifacts: {run_dir}")
    return 0


def resolve_oof_months(args: argparse.Namespace) -> list[str]:
    if args.months:
        return parse_csv_months(args.months)
    if args.start_month and args.end_month:
        return iter_months(args.start_month, args.end_month)
    raise ValueError("oof requires either --months or --start-month/--end-month")


def oof(args: argparse.Namespace) -> int:
    months = resolve_oof_months(args)
    model_config = model_config_from_args(args)
    regression_targets, classification_targets = resolve_target_names(args.target_set)
    all_df, feature_columns = load_months(
        args.dataset_dir,
        months,
        args.horizon_hours,
        args.min_adjusted_edge,
    )
    regression_targets, classification_targets, missing_targets = filter_available_target_names(
        [all_df],
        regression_targets,
        classification_targets,
    )
    fold_months = chunk_months(months, args.fold_month_count)
    run_label = args.label or f"hgb_{args.target_set}_oof_edge{args.min_adjusted_edge:g}"
    run_dir = make_run_dir(args.output_dir, run_label)

    fold_outputs: list[pd.DataFrame] = []
    fold_metrics: dict[str, object] = {}
    for fold_index, holdout_months in enumerate(fold_months):
        holdout_mask = all_df["dataset_month"].isin(holdout_months)
        holdout_df = all_df.loc[holdout_mask].copy()
        fit_df = all_df.loc[~holdout_mask].copy()
        if holdout_df.empty:
            raise ValueError(f"empty OOF holdout fold: {', '.join(holdout_months)}")
        if fit_df.empty:
            raise ValueError(f"empty OOF fit fold for holdout: {', '.join(holdout_months)}")
        fit_rows_before_purge = int(len(fit_df))
        fit_rows_removed = 0
        if args.purge_label_overlap:
            fit_df, fit_rows_removed = purge_overlapping_labels(
                fit_df,
                [holdout_df],
                horizon_hours=args.horizon_hours,
                embargo_hours=args.embargo_hours,
            )
            if fit_df.empty:
                raise ValueError(f"purging removed all fit rows for holdout: {', '.join(holdout_months)}")
        fit_df = maybe_sample(fit_df, args.sample_frac, args.random_seed + fold_index)

        models = fit_models(
            fit_df,
            feature_columns,
            model_config,
            regression_targets,
            classification_targets,
            log_prefix=f"[fold {fold_index}]",
        )
        split_metrics, predictions = evaluate_models(
            models,
            holdout_df,
            feature_columns,
            regression_targets,
            classification_targets,
        )
        pred_frame = prediction_frame(holdout_df, predictions)
        pred_frame["oof_fold"] = fold_index
        pred_frame["oof_holdout_months"] = ",".join(holdout_months)
        fold_outputs.append(pred_frame)
        if SELECTION_COLUMNS.issubset(pred_frame.columns):
            split_metrics["selection"] = selection_metrics(pred_frame, args.entry_threshold)
        fold_metrics[str(fold_index)] = {
            "holdout_months": holdout_months,
            "fit_rows_before_purge": fit_rows_before_purge,
            "fit_rows_removed_by_purge": fit_rows_removed,
            "fit_rows_after_purge_and_sampling": int(len(fit_df)),
            "holdout_rows": int(len(holdout_df)),
            "metrics": split_metrics,
            "model_diagnostics": model_diagnostics(models, model_config),
        }

    oof_predictions = pd.concat(fold_outputs, ignore_index=True).sort_values("decision_timestamp")
    oof_predictions.to_parquet(run_dir / "predictions_oof.parquet", index=False)
    with (run_dir / "feature_columns.json").open("w", encoding="utf-8") as handle:
        json.dump(feature_columns, handle, ensure_ascii=False, indent=2)
    metrics: dict[str, object] = {
        "mode": "blocked_oof",
        "months": months,
        "fold_months": fold_months,
        "dataset_dir": str(args.dataset_dir),
        "horizon_hours": args.horizon_hours,
        "min_adjusted_edge": args.min_adjusted_edge,
        "purge_label_overlap": args.purge_label_overlap,
        "embargo_hours": args.embargo_hours,
        "model_config": asdict(model_config),
        "target_set": args.target_set,
        "regression_targets": regression_targets,
        "classification_targets": classification_targets,
        "missing_targets": missing_targets,
        "feature_count": len(feature_columns),
        "rows": {
            "input": int(len(all_df)),
            "oof_predictions": int(len(oof_predictions)),
        },
        "month_rows": month_counts(oof_predictions),
        "folds": fold_metrics,
        "oof": prediction_frame_evaluation_metrics(
            oof_predictions,
            regression_targets,
            classification_targets,
            args.entry_threshold,
        ),
    }
    with (run_dir / "metrics.json").open("w", encoding="utf-8") as handle:
        json.dump(metrics, handle, ensure_ascii=False, indent=2)
    write_oof_report(run_dir, metrics)
    print(json.dumps(metrics["oof"], indent=2))
    print(f"artifacts: {run_dir}")
    return 0


def write_report(run_dir: Path, metrics: dict[str, object]) -> None:
    test_selection = metrics["test"]["selection"]
    valid_selection = metrics["valid"]["selection"]
    test_calibrated = metrics["test"]["selection_calibrated"]
    valid_calibrated = metrics["valid"]["selection_calibrated"]
    lines = [
        "# HistGradientBoosting Multi-Task Model Report",
        "",
        f"- train months: {', '.join(metrics['months']['train'])}",
        f"- valid months: {', '.join(metrics['months']['valid'])}",
        f"- test months: {', '.join(metrics['months']['test'])}",
        f"- feature count: {metrics['feature_count']}",
        f"- train rows: {metrics['rows']['train']}",
        f"- valid rows: {metrics['rows']['valid']}",
        f"- test rows: {metrics['rows']['test']}",
        "",
        "## Selection Metrics",
        "",
        "| split | ev | trades | oracle-exit pnl | avg pnl | side acc | oracle upper bound |",
        "|---|---|---:|---:|---:|---:|---:|",
        (
            f"| valid | raw | {valid_selection['selected_trade_count']} | "
            f"{valid_selection['selected_oracle_exit_adjusted_pnl']:.4f} | "
            f"{valid_selection['selected_avg_adjusted_pnl']:.4f} | "
            f"{valid_selection['selected_side_accuracy']:.4f} | "
            f"{valid_selection['oracle_exit_adjusted_pnl_upper_bound']:.4f} |"
        ),
        (
            f"| valid | calibrated | {valid_calibrated['selected_trade_count']} | "
            f"{valid_calibrated['selected_oracle_exit_adjusted_pnl']:.4f} | "
            f"{valid_calibrated['selected_avg_adjusted_pnl']:.4f} | "
            f"{valid_calibrated['selected_side_accuracy']:.4f} | "
            f"{valid_calibrated['oracle_exit_adjusted_pnl_upper_bound']:.4f} |"
        ),
        (
            f"| test | raw | {test_selection['selected_trade_count']} | "
            f"{test_selection['selected_oracle_exit_adjusted_pnl']:.4f} | "
            f"{test_selection['selected_avg_adjusted_pnl']:.4f} | "
            f"{test_selection['selected_side_accuracy']:.4f} | "
            f"{test_selection['oracle_exit_adjusted_pnl_upper_bound']:.4f} |"
        ),
        (
            f"| test | calibrated | {test_calibrated['selected_trade_count']} | "
            f"{test_calibrated['selected_oracle_exit_adjusted_pnl']:.4f} | "
            f"{test_calibrated['selected_avg_adjusted_pnl']:.4f} | "
            f"{test_calibrated['selected_side_accuracy']:.4f} | "
            f"{test_calibrated['oracle_exit_adjusted_pnl_upper_bound']:.4f} |"
        ),
        "",
        "This selection metric still uses oracle exits from the target data. It evaluates entry and side ranking only, not executable exit timing.",
    ]
    (run_dir / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_oof_report(run_dir: Path, metrics: dict[str, object]) -> None:
    lines = [
        "# HistGradientBoosting Blocked OOF Report",
        "",
        f"- months: {', '.join(metrics['months'])}",
        f"- fold months: {'; '.join(','.join(fold) for fold in metrics['fold_months'])}",
        f"- feature count: {metrics['feature_count']}",
        f"- input rows: {metrics['rows']['input']}",
        f"- oof rows: {metrics['rows']['oof_predictions']}",
        f"- purge label overlap: {metrics['purge_label_overlap']}",
        f"- embargo hours: {metrics['embargo_hours']}",
    ]
    selection = metrics["oof"].get("selection")
    if selection:
        lines.extend(
            [
                "",
                "## OOF Selection",
                "",
                "| threshold | trades | oracle-exit pnl | avg pnl | side acc | oracle upper bound |",
                "|---:|---:|---:|---:|---:|---:|",
                (
                    f"| {selection['entry_threshold']:.4f} | "
                    f"{selection['selected_trade_count']} | "
                    f"{selection['selected_oracle_exit_adjusted_pnl']:.4f} | "
                    f"{selection['selected_avg_adjusted_pnl']:.4f} | "
                    f"{selection['selected_side_accuracy']:.4f} | "
                    f"{selection['oracle_exit_adjusted_pnl_upper_bound']:.4f} |"
                ),
            ]
        )
    lines.extend(
        [
            "",
            "This report evaluates blocked out-of-fold predictions. It is intended for calibration and meta-model training data, not as a final executable policy score.",
        ]
    )
    (run_dir / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Train lightweight XAUUSD models")
    subparsers = parser.add_subparsers(dest="command", required=True)

    train_parser = subparsers.add_parser("train", help="train lightweight multi-task models")
    train_parser.add_argument("--dataset-dir", type=Path, default=Path("data/processed/datasets/xauusd_m1"))
    train_parser.add_argument("--output-dir", type=Path, default=Path("experiments"))
    train_parser.add_argument("--label", default="", help="optional run label for the experiment directory")
    train_parser.add_argument("--train-start")
    train_parser.add_argument("--train-end")
    train_parser.add_argument("--valid-start")
    train_parser.add_argument("--valid-end")
    train_parser.add_argument("--test-start")
    train_parser.add_argument("--test-end")
    train_parser.add_argument("--train-months", help="comma-separated train months in YYYY-MM format")
    train_parser.add_argument("--valid-months", help="comma-separated validation months in YYYY-MM format")
    train_parser.add_argument("--test-months", help="comma-separated test months in YYYY-MM format")
    train_parser.add_argument("--horizon-hours", type=float, default=24.0)
    train_parser.add_argument("--min-adjusted-edge", type=float, default=15.0)
    train_parser.add_argument(
        "--purge-label-overlap",
        type=parse_bool,
        default=True,
        help="remove train/validation rows whose label horizon overlaps later validation/test windows",
    )
    train_parser.add_argument(
        "--embargo-hours",
        type=float,
        default=0.0,
        help="extra time buffer around blocked validation/test label windows",
    )
    train_parser.add_argument("--max-iter", type=int, default=200)
    train_parser.add_argument("--learning-rate", type=float, default=0.03)
    train_parser.add_argument("--max-leaf-nodes", type=int, default=15)
    train_parser.add_argument("--max-depth", type=int, default=4, help="<=0 disables depth limit")
    train_parser.add_argument("--min-samples-leaf", type=int, default=100)
    train_parser.add_argument("--l2-regularization", type=float, default=0.2)
    train_parser.add_argument("--max-features", type=float, default=0.8)
    train_parser.add_argument("--early-stopping", type=parse_bool, default=True)
    train_parser.add_argument("--validation-fraction", type=float, default=0.15)
    train_parser.add_argument("--n-iter-no-change", type=int, default=10)
    train_parser.add_argument("--tol", type=float, default=1e-6)
    train_parser.add_argument("--random-seed", type=int, default=7)
    train_parser.add_argument("--sample-frac", type=float, default=1.0)
    train_parser.add_argument("--entry-threshold", type=float, default=15.0)
    train_parser.add_argument("--target-clip-quantile", type=float, default=0.99)
    train_parser.add_argument(
        "--sample-weighting",
        choices=["none", "month", "label", "month_label"],
        default="month_label",
        help="training sample weighting scheme",
    )
    train_parser.add_argument(
        "--target-set",
        choices=sorted(TARGET_SETS),
        default="full",
        help="full trains all research targets; policy trains only columns needed by executable policy sweeps",
    )
    train_parser.set_defaults(func=train)

    oof_parser = subparsers.add_parser(
        "oof",
        help="train blocked out-of-fold predictions for calibration/meta-model data",
    )
    oof_parser.add_argument("--dataset-dir", type=Path, default=Path("data/processed/datasets/xauusd_m1"))
    oof_parser.add_argument("--output-dir", type=Path, default=Path("experiments"))
    oof_parser.add_argument("--label", default="", help="optional run label for the experiment directory")
    oof_parser.add_argument("--months", help="comma-separated OOF months in YYYY-MM format")
    oof_parser.add_argument("--start-month", help="first OOF month in YYYY-MM format")
    oof_parser.add_argument("--end-month", help="last OOF month in YYYY-MM format")
    oof_parser.add_argument(
        "--fold-month-count",
        type=int,
        default=1,
        help="number of contiguous months held out per OOF fold",
    )
    oof_parser.add_argument("--horizon-hours", type=float, default=24.0)
    oof_parser.add_argument("--min-adjusted-edge", type=float, default=15.0)
    oof_parser.add_argument(
        "--purge-label-overlap",
        type=parse_bool,
        default=True,
        help="remove fit rows whose label horizon overlaps each OOF holdout window",
    )
    oof_parser.add_argument(
        "--embargo-hours",
        type=float,
        default=0.0,
        help="extra time buffer around each OOF holdout label window",
    )
    oof_parser.add_argument("--max-iter", type=int, default=200)
    oof_parser.add_argument("--learning-rate", type=float, default=0.03)
    oof_parser.add_argument("--max-leaf-nodes", type=int, default=15)
    oof_parser.add_argument("--max-depth", type=int, default=4, help="<=0 disables depth limit")
    oof_parser.add_argument("--min-samples-leaf", type=int, default=100)
    oof_parser.add_argument("--l2-regularization", type=float, default=0.2)
    oof_parser.add_argument("--max-features", type=float, default=0.8)
    oof_parser.add_argument("--early-stopping", type=parse_bool, default=True)
    oof_parser.add_argument("--validation-fraction", type=float, default=0.15)
    oof_parser.add_argument("--n-iter-no-change", type=int, default=10)
    oof_parser.add_argument("--tol", type=float, default=1e-6)
    oof_parser.add_argument("--random-seed", type=int, default=7)
    oof_parser.add_argument("--sample-frac", type=float, default=1.0)
    oof_parser.add_argument("--entry-threshold", type=float, default=15.0)
    oof_parser.add_argument("--target-clip-quantile", type=float, default=0.99)
    oof_parser.add_argument(
        "--sample-weighting",
        choices=["none", "month", "label", "month_label"],
        default="month_label",
        help="training sample weighting scheme",
    )
    oof_parser.add_argument(
        "--target-set",
        choices=sorted(TARGET_SETS),
        default="full",
        help="full trains all research targets; policy trains only columns needed by executable policy sweeps",
    )
    oof_parser.set_defaults(func=oof)

    side_confidence_report = subparsers.add_parser(
        "side-confidence-report",
        help="summarize best_side probability calibration from saved predictions",
    )
    side_confidence_report.add_argument(
        "--predictions",
        type=Path,
        action="append",
        required=True,
        help="prediction parquet; pass multiple times to combine valid/test/OOF files",
    )
    side_confidence_report.add_argument("--output-dir", type=Path, default=Path("data/reports/modeling"))
    side_confidence_report.add_argument("--label", default="side_confidence_report")
    side_confidence_report.add_argument(
        "--group-columns",
        default="prediction_split,dataset_month,session_regime,volatility_regime,trend_regime,combined_regime",
        help="comma-separated columns to summarize independently",
    )
    side_confidence_report.add_argument("--min-group-rows", type=int, default=100)
    side_confidence_report.add_argument("--bucket-count", type=int, default=5)
    side_confidence_report.add_argument("--min-confidence", type=float, default=0.5)
    side_confidence_report.add_argument("--top-n", type=int, default=20)
    side_confidence_report.set_defaults(func=handle_side_confidence_report)

    profit_barrier_report = subparsers.add_parser(
        "profit-barrier-report",
        help="summarize profit-barrier hit probability calibration from saved predictions",
    )
    profit_barrier_report.add_argument(
        "--predictions",
        type=Path,
        action="append",
        required=True,
        help="prediction parquet; pass multiple times to combine valid/test/OOF files",
    )
    profit_barrier_report.add_argument("--output-dir", type=Path, default=Path("data/reports/modeling"))
    profit_barrier_report.add_argument("--label", default="profit_barrier_report")
    profit_barrier_report.add_argument(
        "--group-columns",
        default="prediction_split,dataset_month,barrier_side,session_regime,volatility_regime,trend_regime,combined_regime",
        help="comma-separated columns to summarize independently",
    )
    profit_barrier_report.add_argument("--min-group-rows", type=int, default=100)
    profit_barrier_report.add_argument("--bucket-count", type=int, default=5)
    profit_barrier_report.add_argument("--min-probability", type=float, default=0.0)
    profit_barrier_report.add_argument("--threshold", type=float, default=0.5)
    profit_barrier_report.add_argument("--long-actual-column", default="long_profit_barrier_hit")
    profit_barrier_report.add_argument("--short-actual-column", default="short_profit_barrier_hit")
    profit_barrier_report.add_argument(
        "--long-probability-column",
        default="pred_long_profit_barrier_hit_prob_1",
    )
    profit_barrier_report.add_argument(
        "--short-probability-column",
        default="pred_short_profit_barrier_hit_prob_1",
    )
    profit_barrier_report.add_argument("--top-n", type=int, default=20)
    profit_barrier_report.set_defaults(func=handle_profit_barrier_report)
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
