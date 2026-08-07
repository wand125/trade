from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable, Sequence

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, balanced_accuracy_score, brier_score_loss, log_loss
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from trade_data.backtest import read_ohlcv


DEFAULT_TIMEFRAMES = (1, 5, 15, 30)
CONFIDENCE_THRESHOLDS = (0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80)
LAG_PERIODS = (1, 2, 3, 5, 8, 13, 21)
ROLLING_WINDOWS = (5, 10, 20, 50)
RAW_PRICE_COLUMNS = {"open", "high", "low", "close"}
FEATURE_SETS = ("baseline", "enhanced_manual", "sequence_manual")
CONFIDENCE_MODELS = ("class_probability", "side_platt", "context_hgb")
MODEL_TYPES = ("hgb", "mlp")
CONFIDENCE_CONTEXT_FEATURES = (
    "body_ratio",
    "range_ratio",
    "close_location",
    "rsi_14",
    "zscore_20",
    "volatility_5",
    "volatility_20",
    "volatility_50",
    "atr_ratio_20",
    "efficiency_20",
    "gap_bars",
    "time_sin",
    "time_cos",
    "dow_sin",
    "dow_cos",
)


@dataclass(frozen=True)
class TrainConfig:
    timeframes: tuple[int, ...] = DEFAULT_TIMEFRAMES
    train_fraction: float = 0.60
    calibration_fraction: float = 0.20
    flat_tolerance: float = 0.0
    max_train_rows: int = 750_000
    random_seed: int = 42
    max_iter: int = 200
    learning_rate: float = 0.05
    max_leaf_nodes: int = 31
    min_samples_leaf: int = 100
    l2_regularization: float = 1.0
    feature_set: str = "baseline"
    confidence_model: str = "class_probability"
    model_type: str = "hgb"
    mlp_learning_rate: float = 0.001
    mlp_alpha: float = 0.001
    mlp_batch_size: int = 1024


@dataclass(frozen=True)
class AdoptionOptimizationConfig:
    """Constraints and utility weights for selective next-bar predictions."""

    min_rows: int = 500
    min_coverage: float = 0.01
    coverage_power: float = 0.5
    break_even_accuracy: float = 0.5
    wilson_z: float = 1.96
    confidence_thresholds: tuple[float, ...] = (
        0.50,
        0.505,
        0.51,
        0.515,
        0.52,
        0.525,
        0.53,
        0.54,
        0.55,
        0.575,
        0.60,
    )


@dataclass(frozen=True)
class OddsCalibrationConfig:
    """Configuration for empirical probability-of-correctness calibration."""

    bins: int = 10
    min_support: int = 500
    prior_strength: float = 500.0
    wilson_z: float = 1.96


@dataclass(frozen=True)
class WalkForwardFold:
    name: str
    train_end: pd.Timestamp
    calibration_end: pd.Timestamp
    test_end: pd.Timestamp


@dataclass(frozen=True)
class PlattCalibrator:
    slope: float
    intercept: float

    def predict(self, probability_up: np.ndarray) -> np.ndarray:
        raw = np.asarray(probability_up, dtype="float64")
        logits = np.log(np.clip(raw, 1e-6, 1 - 1e-6) / np.clip(1 - raw, 1e-6, 1))
        calibrated = 1.0 / (1.0 + np.exp(-(self.slope * logits + self.intercept)))
        return np.clip(calibrated, 1e-6, 1 - 1e-6)


@dataclass(frozen=True)
class DirectionConfidenceCalibrator:
    predicted_down: PlattCalibrator
    predicted_up: PlattCalibrator
    predicted_down_rows: int
    predicted_up_rows: int

    def predict(self, probability_up: np.ndarray) -> np.ndarray:
        probability = np.asarray(probability_up, dtype="float64")
        class_confidence = np.maximum(probability, 1 - probability)
        predicted_up = probability >= 0.5
        output = np.empty(len(probability), dtype="float64")
        output[predicted_up] = self.predicted_up.predict(class_confidence[predicted_up])
        output[~predicted_up] = self.predicted_down.predict(class_confidence[~predicted_up])
        return output


@dataclass(frozen=True)
class ContextConfidenceModel:
    model: object
    calibrator: PlattCalibrator
    feature_columns: tuple[str, ...]

    def predict(self, frame: pd.DataFrame, probability_up: np.ndarray) -> np.ndarray:
        inputs = confidence_context_frame(frame, probability_up)
        raw_probability = _positive_probability(self.model, inputs[list(self.feature_columns)])
        return self.calibrator.predict(raw_probability)


def parse_timeframes(value: str) -> tuple[int, ...]:
    try:
        values = tuple(dict.fromkeys(int(item.strip()) for item in value.split(",") if item.strip()))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("timeframes must be comma-separated positive integers") from exc
    if not values or any(value <= 0 for value in values):
        raise argparse.ArgumentTypeError("timeframes must be comma-separated positive integers")
    return values


def parse_walk_forward_fold(value: str) -> WalkForwardFold:
    parts = [part.strip() for part in value.split(",")]
    if len(parts) != 4 or not parts[0]:
        raise argparse.ArgumentTypeError(
            "fold must be name,train_end,calibration_end,test_end"
        )
    try:
        train_end, calibration_end, test_end = (_utc_timestamp(part) for part in parts[1:])
    except (TypeError, ValueError) as exc:
        raise argparse.ArgumentTypeError(f"invalid fold timestamp: {value}") from exc
    if not train_end < calibration_end < test_end:
        raise argparse.ArgumentTypeError(
            "fold boundaries must satisfy train_end < calibration_end < test_end"
        )
    return WalkForwardFold(parts[0], train_end, calibration_end, test_end)


def validate_m1_frame(frame: pd.DataFrame) -> pd.DataFrame:
    required = ["timestamp", "open", "high", "low", "close"]
    missing = sorted(set(required) - set(frame.columns))
    if missing:
        raise ValueError(f"OHLCV frame is missing columns: {', '.join(missing)}")

    output = frame[required].copy()
    output["timestamp"] = pd.to_datetime(output["timestamp"], utc=True)
    for column in ["open", "high", "low", "close"]:
        output[column] = pd.to_numeric(output[column], errors="coerce")
    output = output.dropna(subset=required).sort_values("timestamp").reset_index(drop=True)
    duplicated = output["timestamp"].duplicated(keep=False)
    if duplicated.any():
        raise ValueError(f"M1 input contains {int(duplicated.sum())} rows with duplicate timestamps")
    if (output["high"] < output[["open", "close", "low"]].max(axis=1)).any():
        raise ValueError("M1 input contains a high below open, close, or low")
    if (output["low"] > output[["open", "close", "high"]].min(axis=1)).any():
        raise ValueError("M1 input contains a low above open, close, or high")
    return output


def resample_complete_bars(m1: pd.DataFrame, timeframe_minutes: int) -> pd.DataFrame:
    """Aggregate UTC M1 bars and keep only fully observed timeframe bars."""

    if timeframe_minutes <= 0:
        raise ValueError("timeframe_minutes must be positive")
    source = validate_m1_frame(m1).set_index("timestamp")
    rule = f"{timeframe_minutes}min"
    grouped = source.resample(rule, origin="epoch", label="left", closed="left")
    bars = grouped.agg(
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        source_rows=("close", "count"),
    )
    bars = bars.loc[bars["source_rows"] == timeframe_minutes].reset_index()
    bars["timeframe_minutes"] = timeframe_minutes
    return bars


def _rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    loss = -delta.clip(upper=0).ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    relative_strength = gain / loss.replace(0, np.nan)
    return 100.0 - (100.0 / (1.0 + relative_strength))


def build_feature_frame(
    bars: pd.DataFrame,
    timeframe_minutes: int,
    feature_set: str = "baseline",
) -> tuple[pd.DataFrame, list[str]]:
    if feature_set not in FEATURE_SETS:
        raise ValueError(f"unknown feature_set: {feature_set}")
    required = ["timestamp", "open", "high", "low", "close"]
    missing = sorted(set(required) - set(bars.columns))
    if missing:
        raise ValueError(f"bar frame is missing columns: {', '.join(missing)}")

    result = bars[required].copy()
    result["timestamp"] = pd.to_datetime(result["timestamp"], utc=True)
    close = result["close"].astype("float64")
    open_ = result["open"].astype("float64")
    high = result["high"].astype("float64")
    low = result["low"].astype("float64")
    scale = close.shift(1).replace(0, np.nan)
    feature_columns: list[str] = []

    def add(name: str, values: pd.Series | np.ndarray) -> None:
        result[name] = values
        feature_columns.append(name)

    log_return_1 = np.log(close / close.shift(1))
    add("log_return_1", log_return_1)
    for lag in LAG_PERIODS[1:]:
        add(f"log_return_{lag}", np.log(close / close.shift(lag)))
    add("body_ratio", (close - open_) / scale)
    add("range_ratio", (high - low) / scale)
    add("upper_wick_ratio", (high - pd.concat([open_, close], axis=1).max(axis=1)) / scale)
    add("lower_wick_ratio", (pd.concat([open_, close], axis=1).min(axis=1) - low) / scale)
    add("close_location", (close - low) / (high - low).replace(0, np.nan))
    add("rsi_14", _rsi(close, 14) / 100.0)

    previous_close = close.shift(1)
    true_range = pd.concat(
        [high - low, (high - previous_close).abs(), (low - previous_close).abs()], axis=1
    ).max(axis=1)
    rolling_volatility: dict[int, pd.Series] = {}
    rolling_atr: dict[int, pd.Series] = {}
    for window in ROLLING_WINDOWS:
        rolling_mean = close.rolling(window, min_periods=window).mean()
        rolling_std = close.rolling(window, min_periods=window).std()
        rolling_high = high.rolling(window, min_periods=window).max()
        rolling_low = low.rolling(window, min_periods=window).min()
        net_move = close.diff(window).abs()
        path_length = close.diff().abs().rolling(window, min_periods=window).sum()
        add(f"zscore_{window}", (close - rolling_mean) / rolling_std.replace(0, np.nan))
        rolling_volatility[window] = log_return_1.rolling(window, min_periods=window).std()
        rolling_atr[window] = true_range.rolling(window, min_periods=window).mean()
        add(f"volatility_{window}", rolling_volatility[window])
        add(f"atr_ratio_{window}", rolling_atr[window] / scale)
        add(f"range_location_{window}", (close - rolling_low) / (rolling_high - rolling_low).replace(0, np.nan))
        add(f"efficiency_{window}", net_move / path_length.replace(0, np.nan))

    if feature_set == "enhanced_manual":
        body = close - open_
        direction = np.sign(body).astype("float64")
        atr_20 = rolling_atr[20].replace(0, np.nan)
        add("candle_direction", direction)
        for lag in range(1, 6):
            add(f"candle_direction_lag_{lag}", direction.shift(lag))
        direction_change = direction.ne(direction.shift(1)).cumsum()
        streak = direction.groupby(direction_change).cumcount().add(1).astype("float64") * direction
        add("signed_direction_streak", streak.clip(-20, 20) / 20.0)
        add("body_atr_20", body / atr_20)
        add("range_atr_20", (high - low) / atr_20)
        add("wick_balance_atr_20", (
            (pd.concat([open_, close], axis=1).min(axis=1) - low)
            - (high - pd.concat([open_, close], axis=1).max(axis=1))
        ) / atr_20)
        for window in (5, 10, 20, 50):
            add(
                f"up_fraction_{window}",
                direction.gt(0).astype("float64").rolling(window, min_periods=window).mean(),
            )
        add("trend_volatility_20", np.log(close / close.shift(20)) / (
            rolling_volatility[20].replace(0, np.nan) * np.sqrt(20)
        ))
        add("volatility_ratio_5_50", rolling_volatility[5] / rolling_volatility[50].replace(0, np.nan))
        add("atr_ratio_5_50", rolling_atr[5] / rolling_atr[50].replace(0, np.nan))
        add("return_autocorrelation_20", log_return_1.rolling(20, min_periods=20).corr(log_return_1.shift(1)))
        add("return_skew_20", log_return_1.rolling(20, min_periods=20).skew())
        add("return_skew_50", log_return_1.rolling(50, min_periods=50).skew())
        ema_12 = close.ewm(span=12, adjust=False, min_periods=12).mean()
        ema_26 = close.ewm(span=26, adjust=False, min_periods=26).mean()
        add("ema_spread_atr_20", (ema_12 - ema_26) / atr_20)
        add("ema_12_slope_atr_20", ema_12.diff(3) / atr_20)

    if feature_set == "sequence_manual":
        atr_20 = rolling_atr[20].replace(0, np.nan)
        sequence_values = {
            "return_atr": close.diff() / atr_20,
            "body_atr": (close - open_) / atr_20,
            "range_atr": (high - low) / atr_20,
            "close_location_centered": (
                (close - low) / (high - low).replace(0, np.nan) - 0.5
            ),
            "wick_balance_atr": (
                (pd.concat([open_, close], axis=1).min(axis=1) - low)
                - (high - pd.concat([open_, close], axis=1).max(axis=1))
            )
            / atr_20,
        }
        for lag in range(8):
            for sequence_name, values in sequence_values.items():
                add(f"sequence_{sequence_name}_lag_{lag}", values.shift(lag))

    gap_units = result["timestamp"].diff() / pd.Timedelta(minutes=timeframe_minutes)
    add("gap_bars", gap_units.clip(upper=100))
    minute_of_day = result["timestamp"].dt.hour * 60 + result["timestamp"].dt.minute
    add("time_sin", np.sin(2 * np.pi * minute_of_day / 1440.0))
    add("time_cos", np.cos(2 * np.pi * minute_of_day / 1440.0))
    day_of_week = result["timestamp"].dt.dayofweek
    add("dow_sin", np.sin(2 * np.pi * day_of_week / 7.0))
    add("dow_cos", np.cos(2 * np.pi * day_of_week / 7.0))
    result["decision_timestamp"] = result["timestamp"] + pd.Timedelta(minutes=timeframe_minutes)
    return result, feature_columns


def build_labeled_dataset(
    bars: pd.DataFrame,
    timeframe_minutes: int,
    flat_tolerance: float = 0.0,
    feature_set: str = "baseline",
) -> tuple[pd.DataFrame, list[str], dict[str, int]]:
    if flat_tolerance < 0:
        raise ValueError("flat_tolerance must be non-negative")
    frame, feature_columns = build_feature_frame(bars, timeframe_minutes, feature_set)
    next_start = frame["timestamp"].shift(-1)
    expected_next_start = frame["timestamp"] + pd.Timedelta(minutes=timeframe_minutes)
    next_body = frame["close"].shift(-1) - frame["open"].shift(-1)
    consecutive = next_start.eq(expected_next_start)
    flat = next_body.abs() <= flat_tolerance

    frame["target_timestamp"] = next_start + pd.Timedelta(minutes=timeframe_minutes)
    frame["next_bar_body"] = next_body
    frame["target_up"] = np.where(consecutive & ~flat, (next_body > 0).astype("float64"), np.nan)
    non_finite_features = ~np.isfinite(frame[feature_columns].to_numpy(dtype="float64")).all(axis=1)
    diagnostics = {
        "source_bars": len(frame),
        "excluded_nonconsecutive_targets": int((~consecutive).sum()),
        "excluded_flat_targets": int((consecutive & flat).sum()),
        "excluded_feature_warmup_or_nonfinite": int(non_finite_features.sum()),
    }
    frame = frame.loc[frame["target_up"].notna() & ~non_finite_features].copy()
    frame["target_up"] = frame["target_up"].astype("int8")
    frame = frame.reset_index(drop=True)
    diagnostics["usable_rows"] = len(frame)
    return frame, feature_columns, diagnostics


def _utc_timestamp(value: str | pd.Timestamp) -> pd.Timestamp:
    timestamp = pd.Timestamp(value)
    return timestamp.tz_localize("UTC") if timestamp.tz is None else timestamp.tz_convert("UTC")


def resolve_split_boundaries(
    timestamps: pd.Series,
    train_fraction: float,
    calibration_fraction: float,
    train_end: str | pd.Timestamp | None = None,
    calibration_end: str | pd.Timestamp | None = None,
    test_end: str | pd.Timestamp | None = None,
) -> tuple[pd.Timestamp, pd.Timestamp, pd.Timestamp]:
    if timestamps.empty:
        raise ValueError("cannot split an empty timestamp series")
    values = pd.to_datetime(timestamps, utc=True).sort_values().reset_index(drop=True)
    if (train_end is None) != (calibration_end is None):
        raise ValueError("train_end and calibration_end must be provided together")
    if train_end is not None:
        train_boundary = _utc_timestamp(train_end)
        calibration_boundary = _utc_timestamp(calibration_end)
    else:
        if train_fraction <= 0 or calibration_fraction <= 0 or train_fraction + calibration_fraction >= 1:
            raise ValueError("split fractions must be positive and leave a non-empty test fraction")
        train_boundary = values.iloc[min(int(len(values) * train_fraction), len(values) - 1)]
        calibration_boundary = values.iloc[
            min(int(len(values) * (train_fraction + calibration_fraction)), len(values) - 1)
        ]
    test_boundary = (
        values.iloc[-1] + pd.Timedelta(nanoseconds=1) if test_end is None else _utc_timestamp(test_end)
    )
    if not train_boundary < calibration_boundary < test_boundary:
        raise ValueError("split boundaries must satisfy train_end < calibration_end < test_end")
    return train_boundary, calibration_boundary, test_boundary


def chronological_split(
    dataset: pd.DataFrame,
    train_end: pd.Timestamp,
    calibration_end: pd.Timestamp,
    test_end: pd.Timestamp,
) -> dict[str, pd.DataFrame]:
    decision = pd.to_datetime(dataset["decision_timestamp"], utc=True)
    target = pd.to_datetime(dataset["target_timestamp"], utc=True)
    splits = {
        "train": dataset.loc[(decision < train_end) & (target <= train_end)].copy(),
        "calibration": dataset.loc[
            (decision >= train_end) & (decision < calibration_end) & (target <= calibration_end)
        ].copy(),
        "test": dataset.loc[
            (decision >= calibration_end) & (decision < test_end) & (target <= test_end)
        ].copy(),
    }
    if any(split.empty for split in splits.values()):
        counts = {name: len(split) for name, split in splits.items()}
        raise ValueError(f"chronological split produced an empty partition: {counts}")
    return splits


def _positive_probability(model: object, values: pd.DataFrame) -> np.ndarray:
    probabilities = model.predict_proba(values)
    matches = np.flatnonzero(model.classes_ == 1)
    if len(matches) != 1:
        raise ValueError("model does not contain the up class")
    return probabilities[:, int(matches[0])]


def confidence_context_frame(
    frame: pd.DataFrame, probability_up: np.ndarray
) -> pd.DataFrame:
    missing = sorted(set(CONFIDENCE_CONTEXT_FEATURES) - set(frame.columns))
    if missing:
        raise ValueError(f"missing confidence context features: {', '.join(missing)}")
    output = frame[list(CONFIDENCE_CONTEXT_FEATURES)].copy()
    probability = np.asarray(probability_up, dtype="float64")
    output["probability_up"] = probability
    output["class_confidence"] = np.maximum(probability, 1 - probability)
    output["predicted_up"] = (probability >= 0.5).astype("float64")
    return output


def fit_context_confidence_model(
    train_frame: pd.DataFrame,
    train_probability_up: np.ndarray,
    calibration_frame: pd.DataFrame,
    calibration_probability_up: np.ndarray,
    min_samples_leaf: int,
    random_seed: int,
) -> ContextConfidenceModel:
    train_inputs = confidence_context_frame(train_frame, train_probability_up)
    train_labels = (
        (np.asarray(train_probability_up) >= 0.5).astype("int8")
        == train_frame["target_up"].to_numpy(dtype="int8")
    ).astype("int8")
    if len(np.unique(train_labels)) != 2:
        raise ValueError("confidence model training rows must contain correct and incorrect predictions")
    feature_columns = tuple(train_inputs.columns)
    model = HistGradientBoostingClassifier(
        max_iter=100,
        learning_rate=0.05,
        max_leaf_nodes=15,
        min_samples_leaf=max(20, min_samples_leaf // 2),
        l2_regularization=2.0,
        early_stopping=False,
        random_state=random_seed,
    )
    model.fit(train_inputs[list(feature_columns)], train_labels)
    calibration_inputs = confidence_context_frame(
        calibration_frame, calibration_probability_up
    )
    raw_confidence = _positive_probability(model, calibration_inputs[list(feature_columns)])
    calibration_labels = (
        (np.asarray(calibration_probability_up) >= 0.5).astype("int8")
        == calibration_frame["target_up"].to_numpy(dtype="int8")
    ).astype("int8")
    calibrator = fit_platt_calibrator(calibration_labels, raw_confidence)
    return ContextConfidenceModel(model, calibrator, feature_columns)


def fit_platt_calibrator(y_true: np.ndarray, raw_probability_up: np.ndarray) -> PlattCalibrator:
    labels = np.asarray(y_true, dtype="int8")
    if len(np.unique(labels)) != 2:
        raise ValueError("calibration partition must contain both up and down classes")
    probability = np.asarray(raw_probability_up, dtype="float64")
    logits = np.log(np.clip(probability, 1e-6, 1 - 1e-6) / np.clip(1 - probability, 1e-6, 1))
    model = LogisticRegression(random_state=0)
    model.fit(logits.reshape(-1, 1), labels)
    return PlattCalibrator(slope=float(model.coef_[0, 0]), intercept=float(model.intercept_[0]))


def _fit_correctness_calibrator(
    correct: np.ndarray, class_confidence: np.ndarray
) -> PlattCalibrator:
    labels = np.asarray(correct, dtype="int8")
    confidence = np.asarray(class_confidence, dtype="float64")
    if len(labels) == 0:
        raise ValueError("cannot calibrate confidence without rows")
    if len(np.unique(labels)) == 1:
        smoothed_rate = (float(labels.sum()) + 1.0) / (len(labels) + 2.0)
        intercept = float(np.log(smoothed_rate / (1 - smoothed_rate)))
        return PlattCalibrator(slope=0.0, intercept=intercept)
    return fit_platt_calibrator(labels, confidence)


def fit_direction_confidence_calibrator(
    y_true: np.ndarray, probability_up: np.ndarray
) -> DirectionConfidenceCalibrator:
    labels = np.asarray(y_true, dtype="int8")
    probability = np.asarray(probability_up, dtype="float64")
    predicted_up = probability >= 0.5
    correct = predicted_up.astype("int8") == labels
    class_confidence = np.maximum(probability, 1 - probability)
    overall = _fit_correctness_calibrator(correct, class_confidence)

    def fit_side(mask: np.ndarray) -> PlattCalibrator:
        if not mask.any():
            return overall
        return _fit_correctness_calibrator(correct[mask], class_confidence[mask])

    return DirectionConfidenceCalibrator(
        predicted_down=fit_side(~predicted_up),
        predicted_up=fit_side(predicted_up),
        predicted_down_rows=int((~predicted_up).sum()),
        predicted_up_rows=int(predicted_up.sum()),
    )


def confidence_calibration_error(
    correct: np.ndarray, confidence: np.ndarray, bins: int = 10
) -> float:
    correctness = np.asarray(correct, dtype="float64")
    values = np.asarray(confidence, dtype="float64")
    edges = np.linspace(0.0, 1.0, bins + 1)
    error = 0.0
    for index in range(bins):
        if index == bins - 1:
            mask = (values >= edges[index]) & (values <= edges[index + 1])
        else:
            mask = (values >= edges[index]) & (values < edges[index + 1])
        if mask.any():
            error += float(mask.mean()) * abs(
                float(correctness[mask].mean()) - float(values[mask].mean())
            )
    return error if len(correctness) else float("nan")


def expected_calibration_error(y_true: np.ndarray, probability_up: np.ndarray, bins: int = 10) -> float:
    labels = np.asarray(y_true, dtype="int8")
    probability = np.asarray(probability_up, dtype="float64")
    confidence = np.maximum(probability, 1 - probability)
    correct = ((probability >= 0.5).astype("int8") == labels).astype("float64")
    return confidence_calibration_error(correct, confidence, bins)


def evaluate_probabilities(
    y_true: np.ndarray,
    probability_up: np.ndarray,
    thresholds: Sequence[float] = CONFIDENCE_THRESHOLDS,
    confidence_override: np.ndarray | None = None,
) -> dict[str, object]:
    labels = np.asarray(y_true, dtype="int8")
    probability = np.clip(np.asarray(probability_up, dtype="float64"), 1e-6, 1 - 1e-6)
    prediction = (probability >= 0.5).astype("int8")
    confidence = (
        np.maximum(probability, 1 - probability)
        if confidence_override is None
        else np.clip(np.asarray(confidence_override, dtype="float64"), 0, 1)
    )
    correct = prediction == labels
    confidence_rows = []
    for threshold in thresholds:
        selected = confidence >= threshold
        confidence_rows.append(
            {
                "threshold": float(threshold),
                "rows": int(selected.sum()),
                "coverage": float(selected.mean()),
                "accuracy": float(correct[selected].mean()) if selected.any() else None,
                "mean_confidence": float(confidence[selected].mean()) if selected.any() else None,
            }
        )
    return {
        "rows": int(len(labels)),
        "up_rate": float(labels.mean()),
        "accuracy": float(accuracy_score(labels, prediction)),
        "balanced_accuracy": float(balanced_accuracy_score(labels, prediction)),
        "log_loss": float(log_loss(labels, np.column_stack([1 - probability, probability]), labels=[0, 1])),
        "brier_score": float(brier_score_loss(labels, probability)),
        "expected_calibration_error": float(confidence_calibration_error(correct, confidence)),
        "mean_confidence": float(confidence.mean()),
        "confidence_table": confidence_rows,
    }


def _diagnostic_row(frame: pd.DataFrame, group_value: object) -> dict[str, object]:
    probability = frame["probability_up"].to_numpy(dtype="float64")
    labels = frame["target_up"].to_numpy(dtype="int8")
    prediction = probability >= 0.5
    confidence = (
        frame["confidence"].to_numpy(dtype="float64")
        if "confidence" in frame.columns
        else np.maximum(probability, 1 - probability)
    )
    correct = prediction == labels
    confident = confidence >= 0.55
    return {
        "group_value": str(group_value),
        "rows": len(frame),
        "up_rate": float(labels.mean()),
        "accuracy": float(correct.mean()),
        "mean_confidence": float(confidence.mean()),
        "calibration_gap": float(correct.mean() - confidence.mean()),
        "brier_score": float(brier_score_loss(labels, probability)),
        "expected_calibration_error": float(confidence_calibration_error(correct, confidence)),
        "confidence_055_rows": int(confident.sum()),
        "confidence_055_coverage": float(confident.mean()),
        "confidence_055_accuracy": float(correct[confident].mean()) if confident.any() else None,
    }


def context_diagnostics(predictions: pd.DataFrame) -> dict[str, list[dict[str, object]]]:
    required = {
        "decision_timestamp",
        "target_up",
        "probability_up",
        "volatility_regime",
    }
    missing = sorted(required - set(predictions.columns))
    if missing:
        raise ValueError(f"predictions are missing diagnostic columns: {', '.join(missing)}")
    frame = predictions.copy()
    decision = pd.to_datetime(frame["decision_timestamp"], utc=True)
    frame["month"] = decision.dt.strftime("%Y-%m")
    frame["utc_hour"] = decision.dt.hour
    frame["target_direction"] = np.where(frame["target_up"] == 1, "up", "down")
    diagnostics: dict[str, list[dict[str, object]]] = {}
    for column in [
        "month",
        "utc_hour",
        "volatility_regime",
        "target_direction",
        "predicted_direction",
    ]:
        rows = [
            _diagnostic_row(group, value)
            for value, group in frame.groupby(column, observed=True, sort=True)
        ]
        diagnostics[column] = rows
    return diagnostics


def _even_sample(frame: pd.DataFrame, max_rows: int) -> pd.DataFrame:
    if max_rows <= 0 or len(frame) <= max_rows:
        return frame
    indices = np.linspace(0, len(frame) - 1, max_rows, dtype="int64")
    return frame.iloc[indices]


def validate_stationary_feature_set(feature_columns: Sequence[str]) -> None:
    raw_features = sorted(RAW_PRICE_COLUMNS.intersection(feature_columns))
    if raw_features:
        raise ValueError(
            "raw price levels cannot be model features; transform them first: "
            + ", ".join(raw_features)
        )


def evaluate_context_rule(
    decision_timestamp: pd.Timestamp,
    volatility_regime: str,
    rule: dict[str, object] | None,
    confidence: float | None = None,
    predicted_direction: str | None = None,
) -> tuple[bool, str]:
    if not rule:
        return True, "no_context_filter"
    if rule.get("enabled") is False:
        return False, "policy_disabled"
    min_confidence = rule.get("min_confidence")
    if min_confidence is not None and (
        confidence is None or confidence < float(min_confidence)
    ):
        return False, "confidence_below_threshold"
    allowed_directions = rule.get("predicted_directions")
    if allowed_directions is not None and predicted_direction not in {
        str(value) for value in allowed_directions
    }:
        return False, "predicted_direction_not_selected"
    allowed_hours = rule.get("utc_hours")
    if allowed_hours is not None and int(decision_timestamp.hour) not in {
        int(value) for value in allowed_hours
    }:
        return False, "utc_hour_not_selected"
    allowed_volatility = rule.get("volatility_regimes")
    if allowed_volatility is not None and volatility_regime not in {
        str(value) for value in allowed_volatility
    }:
        return False, "volatility_regime_not_selected"
    return True, "context_selected"


def wilson_accuracy_lower_bound(successes: int, rows: int, z: float = 1.96) -> float:
    """One-sided conservative accuracy estimate using the Wilson score formula."""
    if rows <= 0:
        return 0.0
    if successes < 0 or successes > rows:
        raise ValueError("successes must be between zero and rows")
    probability = successes / rows
    z_squared = z * z
    denominator = 1 + z_squared / rows
    center = probability + z_squared / (2 * rows)
    margin = z * np.sqrt(
        probability * (1 - probability) / rows + z_squared / (4 * rows * rows)
    )
    return float((center - margin) / denominator)


def _prepare_policy_frame(predictions: pd.DataFrame) -> pd.DataFrame:
    required = {"decision_timestamp", "target_up", "probability_up", "volatility_regime"}
    missing = sorted(required - set(predictions.columns))
    if missing:
        raise ValueError(f"predictions are missing policy columns: {', '.join(missing)}")
    frame = predictions.copy()
    frame["decision_timestamp"] = pd.to_datetime(frame["decision_timestamp"], utc=True)
    frame["utc_hour"] = frame["decision_timestamp"].dt.hour.astype("int8")
    if "predicted_direction" not in frame:
        frame["predicted_direction"] = np.where(frame["probability_up"] >= 0.5, "up", "down")
    if "confidence" not in frame:
        frame["confidence"] = np.maximum(frame["probability_up"], 1 - frame["probability_up"])
    if "correct" not in frame:
        frame["correct"] = (
            (frame["probability_up"] >= 0.5).astype("int8")
            == frame["target_up"].astype("int8")
        )
    return frame


def adoption_rule_mask(predictions: pd.DataFrame, rule: dict[str, object]) -> np.ndarray:
    frame = _prepare_policy_frame(predictions)
    if rule.get("enabled") is False:
        return np.zeros(len(frame), dtype=bool)
    selected = frame["confidence"].to_numpy(dtype="float64") >= float(
        rule.get("min_confidence", 0.5)
    )
    directions = rule.get("predicted_directions")
    if directions is not None:
        selected &= frame["predicted_direction"].isin(
            [str(value) for value in directions]
        ).to_numpy()
    regimes = rule.get("volatility_regimes")
    if regimes is not None:
        selected &= frame["volatility_regime"].isin(
            [str(value) for value in regimes]
        ).to_numpy()
    hours = rule.get("utc_hours")
    if hours is not None:
        selected &= frame["utc_hour"].isin([int(value) for value in hours]).to_numpy()
    return selected


def _selection_metrics(
    frame: pd.DataFrame,
    selected: np.ndarray,
    config: AdoptionOptimizationConfig,
) -> dict[str, object]:
    rows = int(selected.sum())
    total_rows = len(frame)
    coverage = rows / total_rows if total_rows else 0.0
    if rows == 0:
        return {
            "rows": 0,
            "total_rows": total_rows,
            "coverage": coverage,
            "accuracy": None,
            "balanced_accuracy": None,
            "accuracy_lower_bound": 0.0,
            "accuracy_lift": None,
            "selection_score": -1.0,
            "quality_score": 0.0,
        }
    chosen = frame.loc[selected]
    correct = chosen["correct"].to_numpy(dtype=bool)
    successes = int(correct.sum())
    accuracy = successes / rows
    lower_bound = wilson_accuracy_lower_bound(successes, rows, config.wilson_z)
    excess = lower_bound - config.break_even_accuracy
    selection_score = coverage ** config.coverage_power * excess
    labels = chosen["target_up"].to_numpy(dtype="int8")
    predictions = (chosen["probability_up"].to_numpy(dtype="float64") >= 0.5).astype("int8")
    balanced = (
        float(balanced_accuracy_score(labels, predictions))
        if np.unique(labels).size == 2
        else None
    )
    return {
        "rows": rows,
        "total_rows": total_rows,
        "coverage": float(coverage),
        "accuracy": float(accuracy),
        "balanced_accuracy": balanced,
        "accuracy_lower_bound": lower_bound,
        "accuracy_lift": float(accuracy - config.break_even_accuracy),
        "selection_score": float(selection_score),
        "quality_score": float(200 * np.clip(excess, 0, 0.5)),
    }


def evaluate_adoption_rule(
    predictions: pd.DataFrame,
    rule: dict[str, object],
    config: AdoptionOptimizationConfig | None = None,
) -> dict[str, object]:
    policy_config = config or AdoptionOptimizationConfig()
    frame = _prepare_policy_frame(predictions)
    metrics = _selection_metrics(frame, adoption_rule_mask(frame, rule), policy_config)
    if "fold" in frame and metrics["rows"]:
        fold_rows = []
        for fold, group in frame.groupby("fold", sort=False):
            selected = adoption_rule_mask(group, rule)
            fold_metrics = _selection_metrics(group, selected, policy_config)
            fold_rows.append({"fold": str(fold), **fold_metrics})
        nonempty = [row for row in fold_rows if row["accuracy"] is not None]
        metrics["fold_metrics"] = fold_rows
        metrics["worst_fold_accuracy"] = (
            float(min(row["accuracy"] for row in nonempty)) if nonempty else None
        )
    return metrics


def _policy_context_options() -> list[tuple[list[int] | None, list[str] | None]]:
    hour_options: list[list[int] | None] = [None]
    hour_options.extend([[hour] for hour in range(24)])
    hour_options.extend([list(range(start, start + 6)) for start in (0, 6, 12, 18)])
    regime_options: list[list[str] | None] = [
        None,
        ["low"],
        ["normal"],
        ["high"],
        ["low", "normal"],
        ["normal", "high"],
    ]
    return [(hours, regimes) for hours in hour_options for regimes in regime_options]


def optimize_adoption_rule(
    predictions: pd.DataFrame,
    config: AdoptionOptimizationConfig | None = None,
) -> tuple[dict[str, object], dict[str, object]]:
    """Select an interpretable abstention rule from out-of-sample predictions."""
    policy_config = config or AdoptionOptimizationConfig()
    if policy_config.min_rows <= 0:
        raise ValueError("min_rows must be positive")
    if not 0 < policy_config.min_coverage <= 1:
        raise ValueError("min_coverage must be in (0, 1]")
    if not 0 <= policy_config.coverage_power <= 1:
        raise ValueError("coverage_power must be in [0, 1]")
    frame = _prepare_policy_frame(predictions)
    if frame.empty:
        raise ValueError("cannot optimize an empty prediction frame")

    confidence = frame["confidence"].to_numpy(dtype="float64")
    thresholds = sorted(
        {
            float(np.clip(value, 0.5, 1.0))
            for value in policy_config.confidence_thresholds
        }
        | {
            float(value)
            for value in np.quantile(confidence, [0.50, 0.75, 0.90, 0.95, 0.975, 0.99])
        }
    )
    correct = frame["correct"].to_numpy(dtype=bool)
    directions = frame["predicted_direction"].astype(str).to_numpy()
    regimes = frame["volatility_regime"].astype(str).to_numpy()
    hours = frame["utc_hour"].to_numpy(dtype="int8")
    direction_options: list[list[str] | None] = [None, ["up"], ["down"]]
    best_rule: dict[str, object] | None = None
    best_rank: tuple[float, float, float] | None = None
    candidates_evaluated = 0

    for allowed_hours, allowed_regimes in _policy_context_options():
        context_mask = np.ones(len(frame), dtype=bool)
        if allowed_hours is not None:
            context_mask &= np.isin(hours, allowed_hours)
        if allowed_regimes is not None:
            context_mask &= np.isin(regimes, allowed_regimes)
        for allowed_directions in direction_options:
            base_mask = context_mask.copy()
            if allowed_directions is not None:
                base_mask &= np.isin(directions, allowed_directions)
            base_indices = np.flatnonzero(base_mask)
            if base_indices.size < policy_config.min_rows:
                continue
            order = np.argsort(-confidence[base_indices], kind="stable")
            sorted_indices = base_indices[order]
            sorted_confidence = confidence[sorted_indices]
            cumulative_correct = np.cumsum(correct[sorted_indices], dtype="int64")
            for threshold in thresholds:
                rows = int(np.searchsorted(-sorted_confidence, -threshold, side="right"))
                coverage = rows / len(frame)
                if rows < policy_config.min_rows or coverage < policy_config.min_coverage:
                    continue
                candidates_evaluated += 1
                successes = int(cumulative_correct[rows - 1])
                accuracy = successes / rows
                lower_bound = wilson_accuracy_lower_bound(
                    successes, rows, policy_config.wilson_z
                )
                score = coverage ** policy_config.coverage_power * (
                    lower_bound - policy_config.break_even_accuracy
                )
                rank = (score, lower_bound, coverage)
                if best_rank is None or rank > best_rank:
                    rule: dict[str, object] = {"min_confidence": float(threshold)}
                    if allowed_directions is not None:
                        rule["predicted_directions"] = allowed_directions
                    if allowed_regimes is not None:
                        rule["volatility_regimes"] = allowed_regimes
                    if allowed_hours is not None:
                        rule["utc_hours"] = allowed_hours
                    best_rule = rule
                    best_rank = rank

    if best_rule is None:
        best_rule = {"enabled": False, "min_confidence": 1.0}
    metrics = evaluate_adoption_rule(frame, best_rule, policy_config)
    best_rule["enabled"] = bool(
        metrics["accuracy_lower_bound"] > policy_config.break_even_accuracy
    )
    metrics["candidates_evaluated"] = candidates_evaluated
    metrics["objective"] = (
        "coverage^coverage_power * (wilson_accuracy_lower_bound - break_even_accuracy)"
    )
    return best_rule, metrics


def _wilson_interval_from_rate(
    probability: float, rows: float, z: float = 1.96
) -> tuple[float, float]:
    if rows <= 0:
        return 0.0, 1.0
    probability = float(np.clip(probability, 0, 1))
    z_squared = z * z
    denominator = 1 + z_squared / rows
    center = probability + z_squared / (2 * rows)
    margin = z * np.sqrt(
        probability * (1 - probability) / rows + z_squared / (4 * rows * rows)
    )
    return (
        float((center - margin) / denominator),
        float((center + margin) / denominator),
    )


def _odds_cell(
    successes: int,
    rows: int,
    prior_probability: float,
    prior_strength: float,
    z: float,
) -> dict[str, object]:
    effective_rows = rows + prior_strength
    probability = (
        (successes + prior_probability * prior_strength) / effective_rows
        if effective_rows
        else prior_probability
    )
    lower, upper = _wilson_interval_from_rate(probability, effective_rows, z)
    return {
        "support_count": int(rows),
        "correct_count": int(successes),
        "confidence": float(probability),
        "confidence_lower": lower,
        "confidence_upper": upper,
    }


def fit_empirical_odds_calibrator(
    predictions: pd.DataFrame,
    config: OddsCalibrationConfig | None = None,
) -> dict[str, object]:
    """Fit a shrinkage reliability table on already out-of-sample predictions."""
    odds_config = config or OddsCalibrationConfig()
    if odds_config.bins < 2:
        raise ValueError("odds calibration bins must be at least two")
    if odds_config.min_support <= 0:
        raise ValueError("odds calibration min_support must be positive")
    if odds_config.prior_strength < 0:
        raise ValueError("odds calibration prior_strength must be non-negative")
    frame = _prepare_policy_frame(predictions)
    if frame.empty:
        raise ValueError("cannot fit odds calibration without predictions")
    confidence = frame["confidence"].to_numpy(dtype="float64")
    quantiles = np.linspace(0, 1, odds_config.bins + 1)[1:-1]
    edges = np.unique(np.quantile(confidence, quantiles)).astype("float64")
    frame["odds_bin"] = np.searchsorted(edges, confidence, side="right").astype("int16")
    global_successes = int(frame["correct"].sum())
    global_rows = len(frame)
    global_probability = global_successes / global_rows
    global_cell = _odds_cell(
        global_successes, global_rows, global_probability, 0.0, odds_config.wilson_z
    )

    def grouped_cells(columns: list[str]) -> dict[str, dict[str, object]]:
        cells: dict[str, dict[str, object]] = {}
        grouper: str | list[str] = columns[0] if len(columns) == 1 else columns
        for values, group in frame.groupby(grouper, observed=True, sort=True):
            if not isinstance(values, tuple):
                values = (values,)
            key = "|".join(str(value) for value in values)
            cells[key] = _odds_cell(
                int(group["correct"].sum()),
                len(group),
                global_probability,
                odds_config.prior_strength,
                odds_config.wilson_z,
            )
        return cells

    return {
        "format_version": 1,
        "config": asdict(odds_config),
        "confidence_bin_edges": [float(value) for value in edges],
        "global": global_cell,
        "cells": {
            "side_regime_bin": grouped_cells(
                ["predicted_direction", "volatility_regime", "odds_bin"]
            ),
            "side_bin": grouped_cells(["predicted_direction", "odds_bin"]),
            "bin": grouped_cells(["odds_bin"]),
        },
    }


def calibrate_prediction_odds(
    model_confidence: float,
    predicted_direction: str,
    volatility_regime: str,
    calibrator: dict[str, object],
) -> dict[str, object]:
    edges = np.asarray(calibrator["confidence_bin_edges"], dtype="float64")
    odds_bin = int(np.searchsorted(edges, model_confidence, side="right"))
    min_support = int(calibrator["config"]["min_support"])
    cells = calibrator["cells"]
    candidates = [
        (
            "side_regime_bin",
            f"{predicted_direction}|{volatility_regime}|{odds_bin}",
        ),
        ("side_bin", f"{predicted_direction}|{odds_bin}"),
        ("bin", str(odds_bin)),
        ("global", "global"),
    ]
    selected_level = "global"
    selected = calibrator["global"]
    for level, key in candidates[:-1]:
        cell = cells[level].get(key)
        if cell is not None and int(cell["support_count"]) >= min_support:
            selected_level = level
            selected = cell
            break
    empirical_confidence = float(selected["confidence"])
    selected_source = str(calibrator.get("selected_source", "empirical_odds"))
    confidence = (
        float(model_confidence)
        if selected_source == "model_confidence"
        else empirical_confidence
    )
    locally_consistent = bool(
        float(selected["confidence_lower"])
        <= confidence
        <= float(selected["confidence_upper"])
    )
    return {
        "confidence": confidence,
        "empirical_accuracy": empirical_confidence,
        "confidence_lower": float(selected["confidence_lower"]),
        "confidence_upper": float(selected["confidence_upper"]),
        "support_count": int(selected["support_count"]),
        "calibration_level": selected_level,
        "calibration_source": selected_source,
        "locally_consistent": locally_consistent,
        "fair_decimal_odds": float(1 / confidence) if confidence > 0 else None,
        "odds_ratio": float(confidence / (1 - confidence)) if confidence < 1 else None,
        "odds_valid": bool(
            calibrator.get("calibration_valid", False) and locally_consistent
        ),
        "odds_edge_confirmed": bool(float(selected["confidence_lower"]) > 0.5),
    }


def apply_empirical_odds_calibrator(
    predictions: pd.DataFrame,
    calibrator: dict[str, object],
) -> pd.DataFrame:
    frame = _prepare_policy_frame(predictions)
    rows = [
        calibrate_prediction_odds(confidence, direction, regime, calibrator)
        for confidence, direction, regime in zip(
            frame["confidence"].to_numpy(dtype="float64"),
            frame["predicted_direction"].astype(str),
            frame["volatility_regime"].astype(str),
            strict=True,
        )
    ]
    return pd.DataFrame(rows, index=frame.index)


def evaluate_odds_calibration(
    correct: np.ndarray,
    confidence: np.ndarray,
) -> dict[str, float]:
    labels = np.asarray(correct, dtype="int8")
    probability = np.clip(np.asarray(confidence, dtype="float64"), 1e-6, 1 - 1e-6)
    return {
        "rows": int(len(labels)),
        "accuracy": float(labels.mean()),
        "mean_confidence": float(probability.mean()),
        "brier_score": float(brier_score_loss(labels, probability)),
        "log_loss": float(log_loss(labels, probability, labels=[0, 1])),
        "expected_calibration_error": float(
            confidence_calibration_error(labels, probability)
        ),
    }


def train_timeframe(
    dataset: pd.DataFrame,
    feature_columns: list[str],
    train_end: pd.Timestamp,
    calibration_end: pd.Timestamp,
    test_end: pd.Timestamp,
    config: TrainConfig,
) -> tuple[dict[str, object], pd.DataFrame, dict[str, object]]:
    validate_stationary_feature_set(feature_columns)
    if config.confidence_model not in CONFIDENCE_MODELS:
        raise ValueError(f"unknown confidence_model: {config.confidence_model}")
    if config.model_type not in MODEL_TYPES:
        raise ValueError(f"unknown model_type: {config.model_type}")
    splits = chronological_split(dataset, train_end, calibration_end, test_end)
    train = _even_sample(splits["train"], config.max_train_rows)
    if train["target_up"].nunique() != 2:
        raise ValueError("training partition must contain both up and down classes")
    if config.model_type == "mlp":
        model = make_pipeline(
            StandardScaler(),
            MLPClassifier(
                hidden_layer_sizes=(64, 32),
                activation="relu",
                solver="adam",
                alpha=config.mlp_alpha,
                batch_size=config.mlp_batch_size,
                learning_rate_init=config.mlp_learning_rate,
                max_iter=config.max_iter,
                early_stopping=False,
                shuffle=False,
                random_state=config.random_seed,
            ),
        )
    else:
        model = HistGradientBoostingClassifier(
            max_iter=config.max_iter,
            learning_rate=config.learning_rate,
            max_leaf_nodes=config.max_leaf_nodes,
            min_samples_leaf=config.min_samples_leaf,
            l2_regularization=config.l2_regularization,
            early_stopping=False,
            random_state=config.random_seed,
        )
    model.fit(train[feature_columns], train["target_up"])
    calibration = splits["calibration"]
    raw_calibration_probability = _positive_probability(model, calibration[feature_columns])
    class_calibration = calibration
    class_calibration_probability = raw_calibration_probability
    if config.confidence_model == "context_hgb":
        midpoint = len(calibration) // 2
        if midpoint < 100 or len(calibration) - midpoint < 200:
            raise ValueError("context confidence model requires at least 300 calibration rows")
        class_calibration = calibration.iloc[:midpoint]
        class_calibration_probability = raw_calibration_probability[:midpoint]
    calibrator = fit_platt_calibrator(
        class_calibration["target_up"].to_numpy(), class_calibration_probability
    )
    calibrated_calibration_probability = calibrator.predict(raw_calibration_probability)
    direction_confidence_calibrator: DirectionConfidenceCalibrator | None = None
    context_confidence_model: ContextConfidenceModel | None = None
    if config.confidence_model == "side_platt":
        direction_confidence_calibrator = fit_direction_confidence_calibrator(
            calibration["target_up"].to_numpy(), calibrated_calibration_probability
        )
    elif config.confidence_model == "context_hgb":
        remaining = len(calibration) - midpoint
        context_split = midpoint + remaining // 2
        context_train = calibration.iloc[midpoint:context_split]
        context_calibration = calibration.iloc[context_split:]
        context_confidence_model = fit_context_confidence_model(
            context_train,
            calibrated_calibration_probability[midpoint:context_split],
            context_calibration,
            calibrated_calibration_probability[context_split:],
            config.min_samples_leaf,
            config.random_seed,
        )
    test = splits["test"].copy()
    raw_probability = _positive_probability(model, test[feature_columns])
    probability = calibrator.predict(raw_probability)
    test["raw_probability_up"] = raw_probability
    test["probability_up"] = probability
    test["probability_down"] = 1 - probability
    test["predicted_up"] = (probability >= 0.5).astype("int8")
    test["predicted_direction"] = np.where(test["predicted_up"] == 1, "up", "down")
    test["class_confidence"] = np.maximum(probability, 1 - probability)
    if config.confidence_model == "side_platt":
        assert direction_confidence_calibrator is not None
        test["confidence"] = direction_confidence_calibrator.predict(probability)
    elif config.confidence_model == "context_hgb":
        assert context_confidence_model is not None
        test["confidence"] = context_confidence_model.predict(test, probability)
    else:
        test["confidence"] = test["class_confidence"]
    test["correct"] = test["predicted_up"] == test["target_up"]

    volatility_column = "volatility_20"
    volatility_low, volatility_high = splits["calibration"][volatility_column].quantile(
        [1 / 3, 2 / 3]
    )
    test["volatility_regime"] = pd.cut(
        test[volatility_column],
        bins=[-np.inf, volatility_low, volatility_high, np.inf],
        labels=["low", "normal", "high"],
        include_lowest=True,
    ).astype("string")

    labels = test["target_up"].to_numpy()
    majority_class = int(splits["train"]["target_up"].mean() >= 0.5)
    previous_direction = (test["body_ratio"] > 0).astype("int8").to_numpy()
    metrics = {
        "split_rows": {name: len(value) for name, value in splits.items()},
        "sampled_train_rows": len(train),
        "split_ranges": {
            name: {
                "decision_start": value["decision_timestamp"].min().isoformat(),
                "decision_end": value["decision_timestamp"].max().isoformat(),
            }
            for name, value in splits.items()
        },
        "raw_test": evaluate_probabilities(labels, raw_probability),
        "class_probability_test": evaluate_probabilities(labels, probability),
        "calibrated_test": evaluate_probabilities(
            labels, probability, confidence_override=test["confidence"].to_numpy()
        ),
        "baselines": {
            "train_majority_class": "up" if majority_class else "down",
            "majority_accuracy": float((labels == majority_class).mean()),
            "previous_bar_direction_accuracy": float((labels == previous_direction).mean()),
        },
        "platt_calibrator": asdict(calibrator),
        "confidence_model": config.confidence_model,
        "direction_confidence_calibrator": (
            asdict(direction_confidence_calibrator)
            if direction_confidence_calibrator is not None
            else None
        ),
        "context_confidence_model_rows": (
            {
                "class_calibration": len(class_calibration),
                "context_train": len(context_train),
                "context_calibration": len(context_calibration),
            }
            if context_confidence_model is not None
            else None
        ),
        "volatility_regime_boundaries": {
            "feature": volatility_column,
            "low_normal": float(volatility_low),
            "normal_high": float(volatility_high),
        },
        "context_diagnostics": context_diagnostics(test),
    }
    artifact = {
        "model": model,
        "calibrator": calibrator,
        "direction_confidence_calibrator": direction_confidence_calibrator,
        "context_confidence_model": context_confidence_model,
        "feature_columns": feature_columns,
        "volatility_regime_boundaries": {
            "feature": volatility_column,
            "low_normal": float(volatility_low),
            "normal_high": float(volatility_high),
        },
    }
    return artifact, test, metrics


def train_all_timeframes(
    m1: pd.DataFrame,
    output_dir: Path,
    config: TrainConfig,
    train_end: str | pd.Timestamp | None = None,
    calibration_end: str | pd.Timestamp | None = None,
    test_end: str | pd.Timestamp | None = None,
) -> dict[str, object]:
    source = validate_m1_frame(m1)
    boundaries = resolve_split_boundaries(
        source["timestamp"], config.train_fraction, config.calibration_fraction,
        train_end, calibration_end, test_end,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    report: dict[str, object] = {
        "created_at": datetime.now(UTC).isoformat(),
        "config": asdict(config),
        "split_boundaries": {
            "train_end": boundaries[0].isoformat(),
            "calibration_end": boundaries[1].isoformat(),
            "test_end": boundaries[2].isoformat(),
        },
        "target_definition": "direction of next consecutive completed candle: close > open",
        "confidence_definition": config.confidence_model,
        "timeframes": {},
    }
    manifest: dict[str, object] = {
        "format_version": 1, "created_at": report["created_at"], "timeframes": {}
    }
    for timeframe in config.timeframes:
        bars = resample_complete_bars(source, timeframe)
        dataset, feature_columns, diagnostics = build_labeled_dataset(
            bars, timeframe, config.flat_tolerance, config.feature_set
        )
        artifact, predictions, metrics = train_timeframe(
            dataset, feature_columns, *boundaries, config
        )
        artifact["timeframe_minutes"] = timeframe
        artifact["flat_tolerance"] = config.flat_tolerance
        artifact["feature_set"] = config.feature_set
        model_name = f"m{timeframe}_model.joblib"
        prediction_name = f"m{timeframe}_test_predictions.parquet"
        joblib.dump(artifact, output_dir / model_name)
        predictions.to_parquet(output_dir / prediction_name, index=False)
        report["timeframes"][f"M{timeframe}"] = {"dataset_diagnostics": diagnostics, **metrics}
        manifest["timeframes"][f"M{timeframe}"] = {
            "minutes": timeframe, "model": model_name, "features": feature_columns,
        }
    (output_dir / "metrics.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return report


def walk_forward_all_timeframes(
    m1: pd.DataFrame,
    output_dir: Path,
    config: TrainConfig,
    folds: Sequence[WalkForwardFold],
) -> dict[str, object]:
    if not folds:
        raise ValueError("at least one walk-forward fold is required")
    fold_names = [fold.name for fold in folds]
    if len(set(fold_names)) != len(fold_names):
        raise ValueError("walk-forward fold names must be unique")
    source = validate_m1_frame(m1)
    output_dir.mkdir(parents=True, exist_ok=True)
    report: dict[str, object] = {
        "created_at": datetime.now(UTC).isoformat(),
        "config": asdict(config),
        "folds": [
            {
                "name": fold.name,
                "train_end": fold.train_end.isoformat(),
                "calibration_end": fold.calibration_end.isoformat(),
                "test_end": fold.test_end.isoformat(),
            }
            for fold in folds
        ],
        "feature_policy": "derived stationary indicators only; raw OHLC levels prohibited",
        "timeframes": {},
    }
    manifest: dict[str, object] = {
        "format_version": 1,
        "created_at": report["created_at"],
        "kind": "walk_forward",
        "timeframes": {},
    }
    compact_columns = [
        "timestamp",
        "decision_timestamp",
        "target_timestamp",
        "target_up",
        "next_bar_body",
        "body_ratio",
        "volatility_20",
        "volatility_regime",
        "raw_probability_up",
        "probability_up",
        "probability_down",
        "predicted_up",
        "predicted_direction",
        "class_confidence",
        "confidence",
        "correct",
    ]
    for timeframe in config.timeframes:
        bars = resample_complete_bars(source, timeframe)
        dataset, feature_columns, diagnostics = build_labeled_dataset(
            bars, timeframe, config.flat_tolerance, config.feature_set
        )
        fold_metrics: list[dict[str, object]] = []
        fold_predictions: list[pd.DataFrame] = []
        model_entries: list[dict[str, object]] = []
        for fold in folds:
            artifact, predictions, metrics = train_timeframe(
                dataset,
                feature_columns,
                fold.train_end,
                fold.calibration_end,
                fold.test_end,
                config,
            )
            artifact["timeframe_minutes"] = timeframe
            artifact["flat_tolerance"] = config.flat_tolerance
            artifact["feature_set"] = config.feature_set
            artifact["fold"] = fold.name
            model_name = f"m{timeframe}_{fold.name}_model.joblib"
            joblib.dump(artifact, output_dir / model_name)
            predictions = predictions[compact_columns].copy()
            predictions["fold"] = fold.name
            fold_predictions.append(predictions)
            fold_metrics.append({"fold": fold.name, **metrics})
            model_entries.append({"fold": fold.name, "model": model_name})

        combined = pd.concat(fold_predictions, ignore_index=True)
        combined_name = f"m{timeframe}_walk_forward_predictions.parquet"
        combined.to_parquet(output_dir / combined_name, index=False)
        aggregate = evaluate_probabilities(
            combined["target_up"].to_numpy(),
            combined["probability_up"].to_numpy(),
            confidence_override=combined["confidence"].to_numpy(),
        )
        report["timeframes"][f"M{timeframe}"] = {
            "dataset_diagnostics": diagnostics,
            "aggregate": aggregate,
            "fold_metrics": fold_metrics,
            "aggregate_context_diagnostics": context_diagnostics(combined),
        }
        manifest["timeframes"][f"M{timeframe}"] = {
            "minutes": timeframe,
            "features": feature_columns,
            "models": model_entries,
            "predictions": combined_name,
        }
    (output_dir / "walk_forward_metrics.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return report


def optimize_walk_forward_policy(
    predictions_dir: Path,
    output: Path,
    config: AdoptionOptimizationConfig | None = None,
) -> dict[str, object]:
    """Optimize final rules and test the selection process on later unseen folds."""
    policy_config = config or AdoptionOptimizationConfig()
    manifest = json.loads((predictions_dir / "manifest.json").read_text(encoding="utf-8"))
    policy: dict[str, object] = {
        "_meta": {
            "format_version": 2,
            "created_at": datetime.now(UTC).isoformat(),
            "source": str(predictions_dir),
            "optimization_config": asdict(policy_config),
            "objective": (
                "coverage^coverage_power * "
                "(wilson_accuracy_lower_bound - break_even_accuracy)"
            ),
            "validation": "nested chronological: prior OOS folds select, next fold evaluates",
        }
    }
    for timeframe, entry in manifest["timeframes"].items():
        prediction_name = entry.get("predictions")
        if prediction_name is None:
            raise ValueError(f"walk-forward manifest has no predictions for {timeframe}")
        frame = _prepare_policy_frame(pd.read_parquet(predictions_dir / prediction_name))
        if "fold" not in frame:
            raise ValueError(f"walk-forward predictions have no fold column for {timeframe}")
        fold_order = [
            str(value)
            for value in (
                frame.groupby("fold", sort=False)["decision_timestamp"].min().sort_values().index
            )
        ]
        nested_rows: list[dict[str, object]] = []
        nested_selected: list[pd.DataFrame] = []
        for position in range(1, len(fold_order)):
            selection_folds = fold_order[:position]
            evaluation_fold = fold_order[position]
            selection_frame = frame.loc[frame["fold"].astype(str).isin(selection_folds)]
            evaluation_frame = frame.loc[frame["fold"].astype(str) == evaluation_fold]
            selected_rule, selection_metrics = optimize_adoption_rule(
                selection_frame, policy_config
            )
            evaluation_metrics = evaluate_adoption_rule(
                evaluation_frame, selected_rule, policy_config
            )
            selected_mask = adoption_rule_mask(evaluation_frame, selected_rule)
            if selected_mask.any():
                nested_selected.append(evaluation_frame.loc[selected_mask].copy())
            selection_summary = {
                key: value
                for key, value in selection_metrics.items()
                if key not in {"fold_metrics", "objective"}
            }
            evaluation_summary = {
                key: value
                for key, value in evaluation_metrics.items()
                if key != "fold_metrics"
            }
            nested_rows.append(
                {
                    "selection_folds": selection_folds,
                    "evaluation_fold": evaluation_fold,
                    "rule": selected_rule,
                    "selection_metrics": selection_summary,
                    "evaluation_metrics": evaluation_summary,
                }
            )

        final_rule, final_metrics = optimize_adoption_rule(frame, policy_config)
        if nested_selected:
            nested_frame = pd.concat(nested_selected, ignore_index=True)
            nested_metrics = _selection_metrics(
                nested_frame,
                np.ones(len(nested_frame), dtype=bool),
                policy_config,
            )
            nested_metrics["evaluation_total_rows"] = int(
                sum(row["evaluation_metrics"]["total_rows"] for row in nested_rows)
            )
            nested_metrics["coverage"] = (
                nested_metrics["rows"] / nested_metrics["evaluation_total_rows"]
            )
            lower_excess = (
                nested_metrics["accuracy_lower_bound"]
                - policy_config.break_even_accuracy
            )
            nested_metrics["selection_score"] = (
                nested_metrics["coverage"] ** policy_config.coverage_power * lower_excess
            )
        else:
            nested_metrics = {
                "rows": 0,
                "evaluation_total_rows": int(
                    sum(row["evaluation_metrics"]["total_rows"] for row in nested_rows)
                ),
                "coverage": 0.0,
                "accuracy": None,
                "accuracy_lower_bound": 0.0,
                "selection_score": -1.0,
                "quality_score": 0.0,
            }
        fold_accuracies = [
            row["evaluation_metrics"]["accuracy"]
            for row in nested_rows
            if row["evaluation_metrics"]["accuracy"] is not None
        ]
        nested_metrics["worst_fold_accuracy"] = (
            float(min(fold_accuracies)) if fold_accuracies else None
        )

        final_rule.update(
            {
                "reference_accuracy": final_metrics["accuracy"],
                "accuracy_lower_bound": final_metrics["accuracy_lower_bound"],
                "reference_coverage": final_metrics["coverage"],
                "quality_score": final_metrics["quality_score"],
                "selection_score": final_metrics["selection_score"],
                "worst_fold_accuracy": final_metrics.get("worst_fold_accuracy"),
                "evaluated_folds": len(fold_order),
                "nested_validation": {
                    "summary": nested_metrics,
                    "folds": nested_rows,
                },
            }
        )
        policy[timeframe] = final_rule

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(policy, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return policy


def build_walk_forward_odds_calibration(
    predictions_dir: Path,
    output: Path,
    config: OddsCalibrationConfig | None = None,
) -> dict[str, object]:
    """Fit deployable odds tables and validate calibration on later OOS folds."""
    odds_config = config or OddsCalibrationConfig()
    manifest = json.loads((predictions_dir / "manifest.json").read_text(encoding="utf-8"))
    payload: dict[str, object] = {
        "_meta": {
            "format_version": 1,
            "created_at": datetime.now(UTC).isoformat(),
            "source": str(predictions_dir),
            "config": asdict(odds_config),
            "validation": "nested chronological: prior OOS folds calibrate, next fold evaluates",
            "confidence_definition": "estimated probability that predicted direction is correct",
        }
    }
    for timeframe, entry in manifest["timeframes"].items():
        prediction_name = entry.get("predictions")
        if prediction_name is None:
            raise ValueError(f"walk-forward manifest has no predictions for {timeframe}")
        frame = _prepare_policy_frame(pd.read_parquet(predictions_dir / prediction_name))
        if "fold" not in frame:
            raise ValueError(f"walk-forward predictions have no fold column for {timeframe}")
        fold_order = [
            str(value)
            for value in (
                frame.groupby("fold", sort=False)["decision_timestamp"].min().sort_values().index
            )
        ]
        nested_rows: list[dict[str, object]] = []
        evaluated_frames: list[pd.DataFrame] = []
        for position in range(1, len(fold_order)):
            calibration_folds = fold_order[:position]
            evaluation_fold = fold_order[position]
            calibration_frame = frame.loc[frame["fold"].astype(str).isin(calibration_folds)]
            evaluation_frame = frame.loc[frame["fold"].astype(str) == evaluation_fold]
            fold_calibrator = fit_empirical_odds_calibrator(calibration_frame, odds_config)
            odds = apply_empirical_odds_calibrator(evaluation_frame, fold_calibrator)
            evaluated = evaluation_frame[["correct", "confidence"]].copy()
            evaluated["odds_confidence"] = odds["confidence"].to_numpy()
            evaluated_frames.append(evaluated)
            nested_rows.append(
                {
                    "calibration_folds": calibration_folds,
                    "evaluation_fold": evaluation_fold,
                    "raw_model_confidence": evaluate_odds_calibration(
                        evaluated["correct"].to_numpy(),
                        evaluated["confidence"].to_numpy(),
                    ),
                    "empirical_odds": evaluate_odds_calibration(
                        evaluated["correct"].to_numpy(),
                        evaluated["odds_confidence"].to_numpy(),
                    ),
                }
            )
        if not evaluated_frames:
            raise ValueError(f"at least two folds are required to validate odds for {timeframe}")
        combined = pd.concat(evaluated_frames, ignore_index=True)
        raw_metrics = evaluate_odds_calibration(
            combined["correct"].to_numpy(), combined["confidence"].to_numpy()
        )
        odds_metrics = evaluate_odds_calibration(
            combined["correct"].to_numpy(), combined["odds_confidence"].to_numpy()
        )
        empirical_better = bool(
            odds_metrics["brier_score"] <= raw_metrics["brier_score"]
            and odds_metrics["log_loss"] <= raw_metrics["log_loss"]
            and odds_metrics["expected_calibration_error"]
            <= raw_metrics["expected_calibration_error"]
        )
        selected_source = "empirical_odds" if empirical_better else "model_confidence"
        selected_metrics = odds_metrics if empirical_better else raw_metrics
        null_brier = selected_metrics["accuracy"] * (1 - selected_metrics["accuracy"])
        calibration_valid = bool(
            selected_metrics["expected_calibration_error"] <= 0.01
            and selected_metrics["brier_score"] <= null_brier
        )
        final_calibrator = fit_empirical_odds_calibrator(frame, odds_config)
        final_calibrator["selected_source"] = selected_source
        final_calibrator["calibration_valid"] = calibration_valid
        final_calibrator["nested_validation"] = {
            "selected_source": selected_source,
            "selected_metrics": selected_metrics,
            "null_brier_score": null_brier,
            "raw_model_confidence": raw_metrics,
            "empirical_odds": odds_metrics,
            "improvement": {
                "brier_score": raw_metrics["brier_score"] - odds_metrics["brier_score"],
                "log_loss": raw_metrics["log_loss"] - odds_metrics["log_loss"],
                "expected_calibration_error": (
                    raw_metrics["expected_calibration_error"]
                    - odds_metrics["expected_calibration_error"]
                ),
            },
            "folds": nested_rows,
        }
        payload[timeframe] = final_calibrator
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def predict_latest(
    m1: pd.DataFrame,
    model_dir: Path,
    context_policy: dict[str, object] | None = None,
    odds_calibration: dict[str, object] | None = None,
) -> pd.DataFrame:
    source = validate_m1_frame(m1)
    manifest = json.loads((model_dir / "manifest.json").read_text(encoding="utf-8"))
    rows: list[dict[str, object]] = []
    for name, entry in manifest["timeframes"].items():
        timeframe = int(entry["minutes"])
        model_name = entry.get("model")
        if model_name is None:
            models = entry.get("models", [])
            if not models:
                raise ValueError(f"manifest has no model for {name}")
            model_name = models[-1]["model"]
        artifact = joblib.load(model_dir / model_name)
        bars = resample_complete_bars(source, timeframe)
        features, _ = build_feature_frame(
            bars, timeframe, artifact.get("feature_set", "baseline")
        )
        feature_columns = list(artifact["feature_columns"])
        usable = features.replace([np.inf, -np.inf], np.nan).dropna(subset=feature_columns)
        if usable.empty:
            raise ValueError(f"not enough complete bars to predict {name}")
        latest = usable.iloc[[-1]]
        raw_probability = _positive_probability(artifact["model"], latest[feature_columns])
        probability = float(artifact["calibrator"].predict(raw_probability)[0])
        class_confidence = max(probability, 1 - probability)
        context_confidence_model = artifact.get("context_confidence_model")
        direction_confidence_calibrator = artifact.get("direction_confidence_calibrator")
        if context_confidence_model is not None:
            confidence = float(context_confidence_model.predict(latest, np.array([probability]))[0])
        elif direction_confidence_calibrator is not None:
            confidence = float(
                direction_confidence_calibrator.predict(np.array([probability]))[0]
            )
        else:
            confidence = class_confidence
        volatility_value = float(latest["volatility_20"].iloc[0])
        boundaries = artifact.get("volatility_regime_boundaries")
        if boundaries is None:
            volatility_regime = "unknown"
        elif volatility_value <= float(boundaries["low_normal"]):
            volatility_regime = "low"
        elif volatility_value <= float(boundaries["normal_high"]):
            volatility_regime = "normal"
        else:
            volatility_regime = "high"
        decision_timestamp = latest["decision_timestamp"].iloc[0]
        rule = None if context_policy is None else context_policy.get(name)
        predicted_direction = "up" if probability >= 0.5 else "down"
        model_confidence = confidence
        timeframe_odds = (
            None if odds_calibration is None else odds_calibration.get(name)
        )
        if timeframe_odds is not None:
            odds = calibrate_prediction_odds(
                model_confidence,
                predicted_direction,
                volatility_regime,
                timeframe_odds,
            )
        else:
            odds = {
                "confidence": model_confidence,
                "confidence_lower": None,
                "confidence_upper": None,
                "support_count": 0,
                "calibration_level": "model_probability",
                "calibration_source": "model_confidence",
                "empirical_accuracy": None,
                "locally_consistent": False,
                "fair_decimal_odds": 1 / model_confidence,
                "odds_ratio": model_confidence / (1 - model_confidence),
                "odds_valid": False,
                "odds_edge_confirmed": False,
            }
        eligible, eligibility_reason = evaluate_context_rule(
            decision_timestamp,
            volatility_regime,
            rule,
            confidence=model_confidence,
            predicted_direction=predicted_direction,
        )
        rows.append(
            {
                "timeframe": name,
                "timeframe_minutes": timeframe,
                "bar_start": latest["timestamp"].iloc[0],
                "decision_timestamp": decision_timestamp,
                "predicted_direction": predicted_direction,
                "direction_score": (2 * probability - 1) * 100,
                "probability_up": probability,
                "probability_down": 1 - probability,
                "class_confidence": class_confidence,
                "model_confidence": model_confidence,
                "confidence": odds["confidence"],
                "confidence_lower": odds["confidence_lower"],
                "confidence_upper": odds["confidence_upper"],
                "fair_decimal_odds": odds["fair_decimal_odds"],
                "odds_ratio": odds["odds_ratio"],
                "odds_support": odds["support_count"],
                "odds_calibration_level": odds["calibration_level"],
                "odds_calibration_source": odds["calibration_source"],
                "odds_empirical_accuracy": odds["empirical_accuracy"],
                "odds_locally_consistent": odds["locally_consistent"],
                "odds_valid": odds["odds_valid"],
                "odds_edge_confirmed": odds["odds_edge_confirmed"],
                "volatility_regime": volatility_regime,
                "prediction_eligible": eligible,
                "strict_prediction_eligible": bool(
                    eligible and odds["odds_valid"] and odds["odds_edge_confirmed"]
                ),
                "eligibility_reason": eligibility_reason,
                "context_accuracy_estimate": (
                    rule.get("reference_accuracy") if rule is not None else None
                ),
                "accuracy_lower_bound": (
                    rule.get("accuracy_lower_bound") if rule is not None else None
                ),
                "policy_coverage": (
                    rule.get("reference_coverage") if rule is not None else None
                ),
                "quality_score": (
                    rule.get("quality_score") if rule is not None else None
                ),
                "context_worst_fold_accuracy": (
                    rule.get("worst_fold_accuracy") if rule is not None else None
                ),
            }
        )
    return pd.DataFrame(rows).sort_values("timeframe_minutes").reset_index(drop=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Train and evaluate independent next-candle direction models."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    train = subparsers.add_parser("train-evaluate", help="train, calibrate, and test all timeframes")
    train.add_argument("--input", type=Path, required=True, help="UTC M1 OHLC parquet")
    train.add_argument("--output-dir", type=Path, required=True)
    train.add_argument("--timeframes", type=parse_timeframes, default=DEFAULT_TIMEFRAMES)
    train.add_argument("--train-end", default=None, help="exclusive UTC boundary")
    train.add_argument("--calibration-end", default=None, help="exclusive UTC boundary")
    train.add_argument("--test-end", default=None, help="exclusive UTC boundary")
    train.add_argument("--train-fraction", type=float, default=0.60)
    train.add_argument("--calibration-fraction", type=float, default=0.20)
    train.add_argument("--flat-tolerance", type=float, default=0.0)
    train.add_argument("--max-train-rows", type=int, default=750_000)
    train.add_argument("--random-seed", type=int, default=42)
    train.add_argument("--max-iter", type=int, default=200)
    train.add_argument("--learning-rate", type=float, default=0.05)
    train.add_argument("--max-leaf-nodes", type=int, default=31)
    train.add_argument("--min-samples-leaf", type=int, default=100)
    train.add_argument("--l2-regularization", type=float, default=1.0)
    train.add_argument("--feature-set", choices=FEATURE_SETS, default="baseline")
    train.add_argument(
        "--confidence-model", choices=CONFIDENCE_MODELS, default="class_probability"
    )
    train.add_argument("--model-type", choices=MODEL_TYPES, default="hgb")
    train.add_argument("--mlp-learning-rate", type=float, default=0.001)
    train.add_argument("--mlp-alpha", type=float, default=0.001)
    train.add_argument("--mlp-batch-size", type=int, default=1024)

    walk_forward = subparsers.add_parser(
        "walk-forward", help="run multiple expanding chronological folds"
    )
    walk_forward.add_argument("--input", type=Path, required=True, help="UTC M1 OHLC parquet")
    walk_forward.add_argument("--output-dir", type=Path, required=True)
    walk_forward.add_argument("--timeframes", type=parse_timeframes, default=DEFAULT_TIMEFRAMES)
    walk_forward.add_argument(
        "--fold",
        type=parse_walk_forward_fold,
        action="append",
        required=True,
        help="repeat name,train_end,calibration_end,test_end",
    )
    walk_forward.add_argument("--train-fraction", type=float, default=0.60)
    walk_forward.add_argument("--calibration-fraction", type=float, default=0.20)
    walk_forward.add_argument("--flat-tolerance", type=float, default=0.0)
    walk_forward.add_argument("--max-train-rows", type=int, default=750_000)
    walk_forward.add_argument("--random-seed", type=int, default=42)
    walk_forward.add_argument("--max-iter", type=int, default=200)
    walk_forward.add_argument("--learning-rate", type=float, default=0.05)
    walk_forward.add_argument("--max-leaf-nodes", type=int, default=31)
    walk_forward.add_argument("--min-samples-leaf", type=int, default=100)
    walk_forward.add_argument("--l2-regularization", type=float, default=1.0)
    walk_forward.add_argument("--feature-set", choices=FEATURE_SETS, default="baseline")
    walk_forward.add_argument(
        "--confidence-model", choices=CONFIDENCE_MODELS, default="class_probability"
    )
    walk_forward.add_argument("--model-type", choices=MODEL_TYPES, default="hgb")
    walk_forward.add_argument("--mlp-learning-rate", type=float, default=0.001)
    walk_forward.add_argument("--mlp-alpha", type=float, default=0.001)
    walk_forward.add_argument("--mlp-batch-size", type=int, default=1024)

    optimize = subparsers.add_parser(
        "optimize-policy",
        help="optimize abstention rules from walk-forward out-of-sample predictions",
    )
    optimize.add_argument("--predictions-dir", type=Path, required=True)
    optimize.add_argument("--output", type=Path, required=True)
    optimize.add_argument("--min-rows", type=int, default=500)
    optimize.add_argument("--min-coverage", type=float, default=0.01)
    optimize.add_argument("--coverage-power", type=float, default=0.5)
    optimize.add_argument("--break-even-accuracy", type=float, default=0.5)
    optimize.add_argument("--wilson-z", type=float, default=1.96)

    odds = subparsers.add_parser(
        "build-odds-calibration",
        help="calibrate probability-of-correctness from walk-forward predictions",
    )
    odds.add_argument("--predictions-dir", type=Path, required=True)
    odds.add_argument("--output", type=Path, required=True)
    odds.add_argument("--bins", type=int, default=10)
    odds.add_argument("--min-support", type=int, default=500)
    odds.add_argument("--prior-strength", type=float, default=500.0)
    odds.add_argument("--wilson-z", type=float, default=1.96)

    predict = subparsers.add_parser("predict-latest", help="predict from the latest completed bars")
    predict.add_argument("--input", type=Path, required=True, help="UTC M1 OHLC parquet")
    predict.add_argument("--model-dir", type=Path, required=True)
    predict.add_argument("--output", type=Path, default=None, help="optional JSON output")
    predict.add_argument(
        "--context-policy", type=Path, default=None, help="optional JSON abstention policy"
    )
    predict.add_argument(
        "--odds-calibration",
        type=Path,
        default=None,
        help="optional empirical probability-of-correctness calibration JSON",
    )
    return parser


def _train_config_from_args(args: argparse.Namespace) -> TrainConfig:
    return TrainConfig(
        timeframes=tuple(args.timeframes),
        train_fraction=args.train_fraction,
        calibration_fraction=args.calibration_fraction,
        flat_tolerance=args.flat_tolerance,
        max_train_rows=args.max_train_rows,
        random_seed=args.random_seed,
        max_iter=args.max_iter,
        learning_rate=args.learning_rate,
        max_leaf_nodes=args.max_leaf_nodes,
        min_samples_leaf=args.min_samples_leaf,
        l2_regularization=args.l2_regularization,
        feature_set=args.feature_set,
        confidence_model=args.confidence_model,
        model_type=args.model_type,
        mlp_learning_rate=args.mlp_learning_rate,
        mlp_alpha=args.mlp_alpha,
        mlp_batch_size=args.mlp_batch_size,
    )


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    if args.command == "train-evaluate":
        report = train_all_timeframes(
            read_ohlcv(args.input), args.output_dir, _train_config_from_args(args),
            args.train_end, args.calibration_end, args.test_end,
        )
        summary = {
            timeframe: values["calibrated_test"]
            for timeframe, values in report["timeframes"].items()
        }
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0
    if args.command == "walk-forward":
        report = walk_forward_all_timeframes(
            read_ohlcv(args.input),
            args.output_dir,
            _train_config_from_args(args),
            args.fold,
        )
        summary = {
            timeframe: {
                "aggregate": values["aggregate"],
                "folds": [
                    {
                        "fold": fold["fold"],
                        "accuracy": fold["calibrated_test"]["accuracy"],
                        "balanced_accuracy": fold["calibrated_test"]["balanced_accuracy"],
                    }
                    for fold in values["fold_metrics"]
                ],
            }
            for timeframe, values in report["timeframes"].items()
        }
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0
    if args.command == "optimize-policy":
        policy = optimize_walk_forward_policy(
            args.predictions_dir,
            args.output,
            AdoptionOptimizationConfig(
                min_rows=args.min_rows,
                min_coverage=args.min_coverage,
                coverage_power=args.coverage_power,
                break_even_accuracy=args.break_even_accuracy,
                wilson_z=args.wilson_z,
            ),
        )
        summary = {
            timeframe: {
                "enabled": rule["enabled"],
                "accuracy": rule["reference_accuracy"],
                "accuracy_lower_bound": rule["accuracy_lower_bound"],
                "coverage": rule["reference_coverage"],
                "quality_score": rule["quality_score"],
                "selection_score": rule["selection_score"],
                "nested_validation": rule["nested_validation"]["summary"],
            }
            for timeframe, rule in policy.items()
            if not timeframe.startswith("_")
        }
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0
    if args.command == "build-odds-calibration":
        calibration = build_walk_forward_odds_calibration(
            args.predictions_dir,
            args.output,
            OddsCalibrationConfig(
                bins=args.bins,
                min_support=args.min_support,
                prior_strength=args.prior_strength,
                wilson_z=args.wilson_z,
            ),
        )
        summary = {
            timeframe: {
                "calibration_valid": values["calibration_valid"],
                **values["nested_validation"],
            }
            for timeframe, values in calibration.items()
            if not timeframe.startswith("_")
        }
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0
    if args.command == "predict-latest":
        context_policy = (
            json.loads(args.context_policy.read_text(encoding="utf-8"))
            if args.context_policy is not None
            else None
        )
        odds_calibration = (
            json.loads(args.odds_calibration.read_text(encoding="utf-8"))
            if args.odds_calibration is not None
            else None
        )
        predictions = predict_latest(
            read_ohlcv(args.input), args.model_dir, context_policy, odds_calibration
        )
        payload = predictions.to_json(orient="records", date_format="iso", indent=2)
        if args.output is not None:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(payload + "\n", encoding="utf-8")
        print(payload)
        return 0
    raise AssertionError(f"unsupported command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
