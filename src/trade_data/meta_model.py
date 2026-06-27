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


@dataclass(frozen=True)
class GroupEVStats:
    n: int
    pred_mean: float
    target_mean: float


@dataclass(frozen=True)
class GroupEVCalibrator:
    config: GroupEVCalibrationConfig
    side_stats: dict[str, GroupEVStats]
    group_stats: dict[str, dict[tuple[str, ...], GroupEVStats]]


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
            )
    return GroupEVCalibrator(config=config, side_stats=side_stats, group_stats=group_stats)


def calibrated_group_ev_values(
    predictions: pd.DataFrame,
    side_name: str,
    calibrator: GroupEVCalibrator,
) -> pd.Series:
    spec = SIDE_COLUMNS[side_name]
    raw = predictions[spec["ev"]].astype(float).reset_index(drop=True)
    stats = pd.DataFrame(
        {
            "pred_mean": calibrator.side_stats[side_name].pred_mean,
            "target_mean": calibrator.side_stats[side_name].target_mean,
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
    values = stats["target_mean"] + calibrator.config.prediction_shrinkage * (raw - stats["pred_mean"])
    return pd.Series(values.to_numpy(), index=predictions.index)


def add_group_calibrated_ev_columns(
    predictions: pd.DataFrame,
    calibrator: GroupEVCalibrator,
) -> pd.DataFrame:
    output = predictions.copy()
    output["pred_regime_calibrated_long_best_adjusted_pnl"] = calibrated_group_ev_values(
        predictions,
        "long",
        calibrator,
    )
    output["pred_regime_calibrated_short_best_adjusted_pnl"] = calibrated_group_ev_values(
        predictions,
        "short",
        calibrator,
    )
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
    return {
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

    def add_group_calibration_args(group_parser: argparse.ArgumentParser) -> None:
        group_parser.add_argument(
            "--group-columns",
            default="volatility_regime,session_regime",
            help="comma-separated categorical columns for side/regime EV calibration",
        )
        group_parser.add_argument("--min-group-size", type=int, default=500)
        group_parser.add_argument("--prior-strength", type=float, default=2000.0)
        group_parser.add_argument("--prediction-shrinkage", type=float, default=0.65)
        group_parser.add_argument("--entry-threshold", type=float, default=15.0)
        group_parser.add_argument("--output-dir", type=Path, default=Path("experiments"))
        group_parser.add_argument("--label", default="regime_ev_calibration")

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
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
