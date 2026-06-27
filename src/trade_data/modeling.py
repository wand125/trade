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

from trade_data.dataset import iter_months, output_stem


EV_TARGETS = [
    "long_best_adjusted_pnl",
    "short_best_adjusted_pnl",
]

REGRESSION_TARGETS = [
    *EV_TARGETS,
    "side_score",
    "long_best_holding_minutes",
    "short_best_holding_minutes",
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
    "long_wait_regret_quantile",
    "short_wait_regret_quantile",
    "long_entry_local_rank_bin",
    "short_entry_local_rank_bin",
    "best_holding_time_bin",
    "long_best_holding_time_bin",
    "short_best_holding_time_bin",
    "label",
]

POLICY_REGRESSION_TARGETS = [
    *EV_TARGETS,
    "side_score",
    "long_best_holding_minutes",
    "short_best_holding_minutes",
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
    "label",
]

TARGET_SETS = {
    "full": (REGRESSION_TARGETS, CLASSIFICATION_TARGETS),
    "policy": (POLICY_REGRESSION_TARGETS, POLICY_CLASSIFICATION_TARGETS),
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


def resolve_target_names(target_set: str) -> tuple[list[str], list[str]]:
    if target_set not in TARGET_SETS:
        raise ValueError(f"unknown target_set: {target_set}")
    regression_targets, classification_targets = TARGET_SETS[target_set]
    return list(regression_targets), list(classification_targets)


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


def prediction_frame(df: pd.DataFrame, predictions: dict[str, np.ndarray]) -> pd.DataFrame:
    columns = [
        "decision_timestamp",
        "entry_timestamp",
        "dataset_month",
        "label",
        "long_best_adjusted_pnl",
        "short_best_adjusted_pnl",
        "side_score",
        "best_adjusted_pnl",
        "best_holding_minutes",
        "long_best_holding_minutes",
        "short_best_holding_minutes",
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
    columns = list(dict.fromkeys(columns))
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
    regression_targets = regression_targets or REGRESSION_TARGETS
    classification_targets = classification_targets or CLASSIFICATION_TARGETS
    x = as_matrix(df, feature_columns)
    metrics: dict[str, dict[str, float]] = {"regression": {}, "classification": {}}
    predictions: dict[str, np.ndarray] = {}
    for target in regression_targets:
        pred = models[target].predict(x)
        predictions[target] = pred
        metrics["regression"][target] = regression_metrics(df[target].to_numpy(), pred)
    for target in classification_targets:
        pred = models[target].predict(x)
        predictions[target] = pred
        metrics["classification"][target] = classification_metrics(df[target].astype(int).to_numpy(), pred)
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
    )
    model_config = ModelConfig(
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
    regression_targets, classification_targets = resolve_target_names(args.target_set)

    train_df, feature_columns = load_months(
        args.dataset_dir,
        train_months,
        args.horizon_hours,
        args.min_adjusted_edge,
    )
    valid_df, _ = load_months(args.dataset_dir, valid_months, args.horizon_hours, args.min_adjusted_edge)
    test_df, _ = load_months(args.dataset_dir, test_months, args.horizon_hours, args.min_adjusted_edge)
    train_df = maybe_sample(train_df, args.sample_frac, args.random_seed)
    sample_weight = build_sample_weights(train_df, args.sample_weighting)

    x_train = as_matrix(train_df, feature_columns)
    models: dict[str, object] = {}
    for target in regression_targets:
        print(f"train regressor: {target}")
        model = train_regressor(model_config)
        model.fit(
            x_train,
            regression_training_values(train_df[target], args.target_clip_quantile),
            sample_weight=sample_weight,
        )
        models[target] = model
    for target in classification_targets:
        print(f"train classifier: {target}")
        model = train_classifier(model_config)
        model.fit(x_train, train_df[target].astype(int).to_numpy(), sample_weight=sample_weight)
        models[target] = model

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
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
