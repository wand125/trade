from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable, Sequence

import joblib
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from sklearn.ensemble import (
    ExtraTreesClassifier,
    HistGradientBoostingClassifier,
    HistGradientBoostingRegressor,
)
from sklearn.isotonic import IsotonicRegression
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
FEATURE_SETS = (
    "baseline",
    "enhanced_manual",
    "trend_structure",
    "volatility_state",
    "path_persistence",
    "direction_transition_state",
    "haar_multiscale",
    "session_relative",
    "candle_pressure_state",
    "bar_breakout_rejection",
    "distribution_shift",
    "rolling_distribution_shape",
    "rolling_spectral_state",
    "rolling_ordinal_motif",
    "rolling_autoregressive_state",
    "rolling_transition_memory",
    "rolling_full_path",
    "change_point_state",
    "shock_recovery_state",
    "sequence_manual",
    "tcn_sequence",
    "intrabar_manual",
    "intrabar_structure",
    "intrabar_profile",
    "intrabar_full_path",
    "intrabar_path_signature",
    "intrabar_full_path_volatility_shape",
    "intrabar_pressure",
    "intrabar_volatility_shape",
    "intrabar_frequency_shape",
    "intrabar_ordinal_shape",
    "intrabar_signed_variation",
    "intrabar_distribution_shape",
    "intrabar_flow_shape",
    "intrabar_breakout_state",
)
CONFIDENCE_MODELS = ("class_probability", "side_platt", "context_hgb")
PROBABILITY_CALIBRATIONS = ("platt", "isotonic", "beta", "temperature")
CHANGE_POINT_REFERENCE_WINDOW = 64
CHANGE_POINT_DRIFT = 0.25
CHANGE_POINT_ALARM_THRESHOLD = 5.0
CHANGE_POINT_SCORE_CAP = 20.0
CHANGE_POINT_AGE_CAP = 64
SHOCK_REFERENCE_WINDOW = 64
SHOCK_Z_THRESHOLD = 2.0
SHOCK_TRACKING_BARS = 16
SHOCK_RESPONSE_CAP = 3.0
ROLLING_SPECTRAL_WINDOW = 64
ROLLING_SPECTRAL_PHASE_FREQUENCIES = (1, 2, 4, 8)
ROLLING_ORDINAL_WINDOWS = (32, 128)
ROLLING_ORDINAL_PATTERNS = {
    "012": 5,
    "021": 7,
    "102": 11,
    "120": 15,
    "201": 19,
    "210": 21,
}
ROLLING_AR_WINDOWS = (32, 128)
ROLLING_AR_LAGS = 3
ROLLING_AR_RIDGE_STRENGTH = 0.05
ROLLING_TRANSITION_WINDOWS = (32, 128)
ROLLING_TRANSITION_PRIOR_STRENGTH = 8.0
MODEL_TYPES = (
    "hgb",
    "mlp",
    "logistic",
    "extra_trees",
    "xgboost",
    "catboost",
    "lightgbm",
    "regime_hgb",
    "body_atr_soft_hgb",
    "body_multiclass_hgb",
    "signed_body_hgb",
    "signed_clarity_hgb",
    "signed_body_quantile_hgb",
    "transition_bayes",
    "tcn",
    "causal_gru",
    "causal_transformer",
)
TCN_SEQUENCE_LENGTH = 16
TCN_SEQUENCE_CHANNELS = (
    "return_atr",
    "body_atr",
    "range_atr",
    "close_location_centered",
    "wick_balance_atr",
)
INTRABAR_FULL_PATH_GRID_POINTS = (1, 2, 4, 5, 7, 8, 10, 11, 13, 14, 15)
INTRABAR_PATH_SIGNATURE_COLUMNS = (
    "intrabar_path_signed_area",
    "intrabar_path_time_time_price_bracket",
    "intrabar_path_price_time_price_bracket",
)
TRAIN_WEIGHTING_MODES = (
    "uniform",
    "body_atr",
    "directional_clarity",
    "directional_follow_through",
    "recency_half_life_730d",
)
RECENCY_WEIGHT_HALF_LIFE_DAYS = 730.0
TRAIN_TARGET_FILTERS = (
    "all",
    "body_atr_upper_half",
    "body_range_upper_half",
)
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
    probability_calibration: str = "platt"
    train_weighting: str = "uniform"
    train_target_filter: str = "all"
    model_type: str = "hgb"
    mlp_learning_rate: float = 0.001
    mlp_alpha: float = 0.001
    mlp_batch_size: int = 1024
    logistic_c: float = 0.10
    train_window_days: int = 0
    extra_trees_estimators: int = 200
    extra_trees_max_depth: int = 12
    extra_trees_min_samples_leaf: int = 50
    extra_trees_max_features: float = 0.75
    xgboost_estimators: int = 300
    xgboost_max_depth: int = 4
    xgboost_learning_rate: float = 0.03
    xgboost_min_child_weight: float = 20.0
    xgboost_subsample: float = 0.80
    xgboost_column_sample: float = 0.80
    xgboost_l2: float = 5.0
    catboost_iterations: int = 300
    catboost_depth: int = 6
    catboost_learning_rate: float = 0.03
    catboost_l2: float = 5.0
    catboost_random_strength: float = 1.0
    catboost_bagging_temperature: float = 1.0
    lightgbm_estimators: int = 300
    lightgbm_num_leaves: int = 31
    lightgbm_learning_rate: float = 0.03
    lightgbm_min_child_samples: int = 100
    lightgbm_subsample: float = 0.80
    lightgbm_column_sample: float = 0.80
    lightgbm_l2: float = 5.0
    transition_state_prior_strength: float = 64.0
    transition_parent_prior_strength: float = 256.0
    tcn_epochs: int = 8
    tcn_batch_size: int = 2048
    tcn_learning_rate: float = 0.001
    tcn_hidden_channels: int = 16
    tcn_weight_decay: float = 0.0001
    transformer_epochs: int = 8
    transformer_batch_size: int = 2048
    transformer_learning_rate: float = 0.0005
    transformer_model_dimension: int = 16
    transformer_attention_heads: int = 4
    transformer_encoder_layers: int = 1
    transformer_feedforward_dimension: int = 32
    transformer_weight_decay: float = 0.0001


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
class IsotonicCalibrator:
    x_thresholds: tuple[float, ...]
    y_thresholds: tuple[float, ...]

    def predict(self, probability_up: np.ndarray) -> np.ndarray:
        raw = np.asarray(probability_up, dtype="float64")
        calibrated = np.interp(raw, self.x_thresholds, self.y_thresholds)
        return np.clip(calibrated, 1e-6, 1 - 1e-6)


@dataclass(frozen=True)
class BetaCalibrator:
    log_probability_coefficient: float
    negative_log_complement_coefficient: float
    intercept: float

    def predict(self, probability_up: np.ndarray) -> np.ndarray:
        probability = np.clip(
            np.asarray(probability_up, dtype="float64"), 1e-6, 1 - 1e-6
        )
        linear = (
            self.log_probability_coefficient * np.log(probability)
            - self.negative_log_complement_coefficient * np.log1p(-probability)
            + self.intercept
        )
        calibrated = 1.0 / (1.0 + np.exp(-np.clip(linear, -40, 40)))
        return np.clip(calibrated, 1e-6, 1 - 1e-6)


@dataclass(frozen=True)
class TemperatureCalibrator:
    temperature: float

    def predict(self, probability_up: np.ndarray) -> np.ndarray:
        probability = np.clip(
            np.asarray(probability_up, dtype="float64"), 1e-6, 1 - 1e-6
        )
        logits = np.log(probability / (1 - probability))
        scaled_logits = logits / self.temperature
        calibrated = 1.0 / (1.0 + np.exp(-np.clip(scaled_logits, -40, 40)))
        return np.clip(calibrated, 1e-6, 1 - 1e-6)


@dataclass
class VolatilityRegimeHGBClassifier:
    max_iter: int
    learning_rate: float
    max_leaf_nodes: int
    min_samples_leaf: int
    l2_regularization: float
    random_state: int
    volatility_column: str = "volatility_20"
    low_threshold_: float | None = field(default=None, init=False)
    high_threshold_: float | None = field(default=None, init=False)
    models_: dict[str, HistGradientBoostingClassifier] = field(
        default_factory=dict,
        init=False,
    )
    regime_counts_: dict[str, int] = field(default_factory=dict, init=False)
    classes_: np.ndarray = field(
        default_factory=lambda: np.array([0, 1], dtype="int8"),
        init=False,
    )

    def _regime_masks(self, values: pd.DataFrame) -> dict[str, np.ndarray]:
        if self.low_threshold_ is None or self.high_threshold_ is None:
            raise ValueError("volatility regime model has not been fitted")
        volatility = values[self.volatility_column].to_numpy(dtype="float64")
        return {
            "low": volatility <= self.low_threshold_,
            "normal": (volatility > self.low_threshold_)
            & (volatility <= self.high_threshold_),
            "high": volatility > self.high_threshold_,
        }

    def fit(
        self,
        values: pd.DataFrame,
        labels: pd.Series | np.ndarray,
        sample_weight: np.ndarray | None = None,
    ) -> VolatilityRegimeHGBClassifier:
        if self.volatility_column not in values:
            raise ValueError(
                f"regime model requires feature: {self.volatility_column}"
            )
        volatility = values[self.volatility_column].to_numpy(dtype="float64")
        if not np.isfinite(volatility).all():
            raise ValueError("regime model volatility values must be finite")
        low, high = np.quantile(volatility, [1 / 3, 2 / 3])
        if not low < high:
            raise ValueError("regime model requires distinct volatility quantiles")
        self.low_threshold_ = float(low)
        self.high_threshold_ = float(high)
        target = np.asarray(labels, dtype="int8")
        weights = (
            None if sample_weight is None else np.asarray(sample_weight, dtype="float64")
        )
        self.models_.clear()
        self.regime_counts_.clear()
        for regime, mask in self._regime_masks(values).items():
            regime_labels = target[mask]
            if len(regime_labels) == 0 or np.unique(regime_labels).size != 2:
                raise ValueError(
                    f"regime training partition must contain both classes: {regime}"
                )
            model = HistGradientBoostingClassifier(
                max_iter=self.max_iter,
                learning_rate=self.learning_rate,
                max_leaf_nodes=self.max_leaf_nodes,
                min_samples_leaf=self.min_samples_leaf,
                l2_regularization=self.l2_regularization,
                early_stopping=False,
                random_state=self.random_state,
            )
            model.fit(
                values.loc[mask],
                regime_labels,
                sample_weight=None if weights is None else weights[mask],
            )
            self.models_[regime] = model
            self.regime_counts_[regime] = int(mask.sum())
        return self

    def predict_proba(self, values: pd.DataFrame) -> np.ndarray:
        if set(self.models_) != {"low", "normal", "high"}:
            raise ValueError("volatility regime model has not been fitted")
        output = np.empty((len(values), 2), dtype="float64")
        for regime, mask in self._regime_masks(values).items():
            if not mask.any():
                continue
            model = self.models_[regime]
            probabilities = model.predict_proba(values.loc[mask])
            match = np.flatnonzero(model.classes_ == 1)
            if len(match) != 1:
                raise ValueError(f"regime model does not contain the up class: {regime}")
            probability_up = probabilities[:, int(match[0])]
            output[mask, 0] = 1 - probability_up
            output[mask, 1] = probability_up
        return output

    def diagnostics(self) -> dict[str, object]:
        return {
            "volatility_column": self.volatility_column,
            "low_threshold": self.low_threshold_,
            "high_threshold": self.high_threshold_,
            "train_rows_by_regime": self.regime_counts_,
        }


@dataclass
class BodyATRSoftHGBClassifier:
    max_iter: int
    learning_rate: float
    max_leaf_nodes: int
    min_samples_leaf: int
    l2_regularization: float
    random_state: int
    model_: HistGradientBoostingRegressor | None = field(default=None, init=False)
    target_summary_: dict[str, float] = field(default_factory=dict, init=False)
    classes_: np.ndarray = field(
        default_factory=lambda: np.array([0, 1], dtype="int8"),
        init=False,
    )

    def fit(
        self,
        values: pd.DataFrame,
        soft_direction_target: pd.Series | np.ndarray,
        sample_weight: np.ndarray | None = None,
    ) -> BodyATRSoftHGBClassifier:
        target = np.asarray(soft_direction_target, dtype="float64")
        if not np.isfinite(target).all() or np.any((target < 0) | (target > 1)):
            raise ValueError("body/ATR soft target must be finite and within [0, 1]")
        if not (np.any(target < 0.5) and np.any(target > 0.5)):
            raise ValueError("body/ATR soft target must contain both directions")
        self.model_ = HistGradientBoostingRegressor(
            loss="squared_error",
            max_iter=self.max_iter,
            learning_rate=self.learning_rate,
            max_leaf_nodes=self.max_leaf_nodes,
            min_samples_leaf=self.min_samples_leaf,
            l2_regularization=self.l2_regularization,
            early_stopping=False,
            random_state=self.random_state,
        )
        self.model_.fit(values, target, sample_weight=sample_weight)
        self.target_summary_ = {
            "minimum": float(target.min()),
            "mean": float(target.mean()),
            "standard_deviation": float(target.std()),
            "maximum": float(target.max()),
        }
        return self

    def predict_proba(self, values: pd.DataFrame) -> np.ndarray:
        if self.model_ is None:
            raise ValueError("body/ATR soft-label model has not been fitted")
        probability_up = np.clip(self.model_.predict(values), 1e-6, 1 - 1e-6)
        return np.column_stack([1 - probability_up, probability_up])

    def diagnostics(self) -> dict[str, object]:
        return {
            "target_transform": "0.5 + direction_sign * 0.5 * tanh(next_bar_body_atr)",
            "regression_loss": "squared_error",
            "transformed_target": self.target_summary_,
        }


@dataclass
class BodyMulticlassHGBClassifier:
    max_iter: int
    learning_rate: float
    max_leaf_nodes: int
    min_samples_leaf: int
    l2_regularization: float
    random_state: int
    model_: HistGradientBoostingClassifier | None = field(default=None, init=False)
    target_counts_: dict[str, int] = field(default_factory=dict, init=False)
    classes_: np.ndarray = field(
        default_factory=lambda: np.array([0, 1], dtype="int8"),
        init=False,
    )

    def fit(
        self,
        values: pd.DataFrame,
        body_class_target: pd.Series | np.ndarray,
        sample_weight: np.ndarray | None = None,
    ) -> BodyMulticlassHGBClassifier:
        target = np.asarray(body_class_target, dtype="int8")
        unique, counts = np.unique(target, return_counts=True)
        if not np.array_equal(unique, np.array([0, 1, 2, 3], dtype="int8")):
            raise ValueError("body multiclass target must contain all four classes")
        self.model_ = HistGradientBoostingClassifier(
            max_iter=self.max_iter,
            learning_rate=self.learning_rate,
            max_leaf_nodes=self.max_leaf_nodes,
            min_samples_leaf=self.min_samples_leaf,
            l2_regularization=self.l2_regularization,
            early_stopping=False,
            random_state=self.random_state,
        )
        self.model_.fit(values, target, sample_weight=sample_weight)
        self.target_counts_ = {
            str(int(label)): int(count) for label, count in zip(unique, counts, strict=True)
        }
        return self

    def predict_proba(self, values: pd.DataFrame) -> np.ndarray:
        if self.model_ is None:
            raise ValueError("body multiclass model has not been fitted")
        probabilities = self.model_.predict_proba(values)
        up_columns = np.flatnonzero(np.isin(self.model_.classes_, [2, 3]))
        if len(up_columns) != 2:
            raise ValueError("body multiclass model does not contain both up classes")
        probability_up = probabilities[:, up_columns].sum(axis=1)
        return np.column_stack([1 - probability_up, probability_up])

    def diagnostics(self) -> dict[str, object]:
        return {
            "target_transform": "direction x next_bar_body_atr above sampled-train median",
            "class_mapping": {
                "0": "down_large",
                "1": "down_small",
                "2": "up_small",
                "3": "up_large",
            },
            "train_rows_by_class": self.target_counts_,
            "direction_probability": "P(up_small) + P(up_large)",
        }


@dataclass
class SignedBodyHGBClassifier:
    max_iter: int
    learning_rate: float
    max_leaf_nodes: int
    min_samples_leaf: int
    l2_regularization: float
    random_state: int
    target_transform: str = (
        "sign(next_bar_body) * asinh(abs(next_bar_body) / decision_atr20)"
    )
    model_: HistGradientBoostingRegressor | None = field(default=None, init=False)
    target_summary_: dict[str, float] = field(default_factory=dict, init=False)
    classes_: np.ndarray = field(
        default_factory=lambda: np.array([0, 1], dtype="int8"),
        init=False,
    )

    def fit(
        self,
        values: pd.DataFrame,
        signed_body_target: pd.Series | np.ndarray,
        sample_weight: np.ndarray | None = None,
    ) -> SignedBodyHGBClassifier:
        target = np.asarray(signed_body_target, dtype="float64")
        if not np.isfinite(target).all():
            raise ValueError("signed body regression target must be finite")
        if not (np.any(target < 0) and np.any(target > 0)):
            raise ValueError("signed body regression target must contain both directions")
        self.model_ = HistGradientBoostingRegressor(
            loss="squared_error",
            max_iter=self.max_iter,
            learning_rate=self.learning_rate,
            max_leaf_nodes=self.max_leaf_nodes,
            min_samples_leaf=self.min_samples_leaf,
            l2_regularization=self.l2_regularization,
            early_stopping=False,
            random_state=self.random_state,
        )
        self.model_.fit(values, target, sample_weight=sample_weight)
        self.target_summary_ = {
            "minimum": float(target.min()),
            "mean": float(target.mean()),
            "standard_deviation": float(target.std()),
            "maximum": float(target.max()),
        }
        return self

    def predict_proba(self, values: pd.DataFrame) -> np.ndarray:
        if self.model_ is None:
            raise ValueError("signed body regression model has not been fitted")
        score = self.model_.predict(values)
        probability_up = 1.0 / (1.0 + np.exp(-np.clip(score, -40, 40)))
        return np.column_stack([1 - probability_up, probability_up])

    def diagnostics(self) -> dict[str, object]:
        return {
            "target_transform": self.target_transform,
            "regression_loss": "squared_error",
            "transformed_target": self.target_summary_,
        }


@dataclass
class SignedBodyQuantileHGBClassifier:
    max_iter: int
    learning_rate: float
    max_leaf_nodes: int
    min_samples_leaf: int
    l2_regularization: float
    random_state: int
    quantiles: tuple[float, ...] = (0.25, 0.50, 0.75)
    models_: dict[float, HistGradientBoostingRegressor] = field(
        default_factory=dict, init=False
    )
    target_summary_: dict[str, float] = field(default_factory=dict, init=False)
    classes_: np.ndarray = field(
        default_factory=lambda: np.array([0, 1], dtype="int8"),
        init=False,
    )

    def fit(
        self,
        values: pd.DataFrame,
        signed_body_target: pd.Series | np.ndarray,
        sample_weight: np.ndarray | None = None,
    ) -> SignedBodyQuantileHGBClassifier:
        target = np.asarray(signed_body_target, dtype="float64")
        if not np.isfinite(target).all():
            raise ValueError("signed body quantile target must be finite")
        if not (np.any(target < 0) and np.any(target > 0)):
            raise ValueError("signed body quantile target must contain both directions")
        self.models_.clear()
        for quantile in self.quantiles:
            model = HistGradientBoostingRegressor(
                loss="quantile",
                quantile=quantile,
                max_iter=self.max_iter,
                learning_rate=self.learning_rate,
                max_leaf_nodes=self.max_leaf_nodes,
                min_samples_leaf=self.min_samples_leaf,
                l2_regularization=self.l2_regularization,
                early_stopping=False,
                random_state=self.random_state,
            )
            model.fit(values, target, sample_weight=sample_weight)
            self.models_[quantile] = model
        self.target_summary_ = {
            "minimum": float(target.min()),
            "mean": float(target.mean()),
            "standard_deviation": float(target.std()),
            "maximum": float(target.max()),
        }
        return self

    def predict_proba(self, values: pd.DataFrame) -> np.ndarray:
        if set(self.models_) != set(self.quantiles):
            raise ValueError("signed body quantile model has not been fitted")
        lower = self.models_[0.25].predict(values)
        median = self.models_[0.50].predict(values)
        upper = self.models_[0.75].predict(values)
        interquartile_width = np.maximum(np.abs(upper - lower), 1e-6)
        standardized_score = median / interquartile_width
        probability_up = 1.0 / (
            1.0 + np.exp(-np.clip(standardized_score, -40, 40))
        )
        return np.column_stack([1 - probability_up, probability_up])

    def diagnostics(self) -> dict[str, object]:
        return {
            "target_transform": "sign(next_bar_body) * asinh(abs(next_bar_body) / decision_atr20)",
            "regression_loss": "quantile",
            "quantiles": list(self.quantiles),
            "direction_score": "median / max(abs(q75 - q25), 1e-6)",
            "transformed_target": self.target_summary_,
        }


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


def intrabar_path_signature(levels: np.ndarray) -> np.ndarray:
    """Return order-sensitive level-2/3 coefficients of time x close paths.

    ``levels`` contains range-normalized closes after each equally spaced M1
    step, with the path implicitly starting at time/price ``(0, 0)``.  Chen's
    identity composes the exact piecewise-linear signature.  Symmetric
    endpoint terms are removed by Lie-bracket projections, leaving three
    compact path-shape summaries rather than another copy of the endpoint.
    """

    values = np.asarray(levels, dtype="float64")
    if values.ndim != 2 or values.shape[1] == 0:
        raise ValueError("levels must be a non-empty two-dimensional array")
    if not np.isfinite(values).all():
        raise ValueError("levels must contain only finite values")

    rows, steps = values.shape
    previous = np.column_stack(
        [np.zeros(rows, dtype="float64"), values[:, :-1]]
    )
    price_increment = values - previous
    time_increment = np.full(rows, 1.0 / steps, dtype="float64")
    level_1 = np.zeros((rows, 2), dtype="float64")
    level_2 = np.zeros((rows, 2, 2), dtype="float64")
    level_3 = np.zeros((rows, 2, 2, 2), dtype="float64")

    for step in range(steps):
        increment = np.column_stack(
            [time_increment, price_increment[:, step]]
        )
        segment_2 = np.einsum("bi,bj->bij", increment, increment) / 2.0
        segment_3 = (
            np.einsum("bi,bj,bk->bijk", increment, increment, increment)
            / 6.0
        )
        level_3 += (
            np.einsum("bij,bk->bijk", level_2, increment)
            + np.einsum("bi,bjk->bijk", level_1, segment_2)
            + segment_3
        )
        level_2 += np.einsum("bi,bj->bij", level_1, increment) + segment_2
        level_1 += increment

    signed_area = level_2[:, 0, 1] - level_2[:, 1, 0]
    time_time_price = (
        level_3[:, 0, 0, 1]
        - 2.0 * level_3[:, 0, 1, 0]
        + level_3[:, 1, 0, 0]
    )
    price_time_price = (
        2.0 * level_3[:, 1, 0, 1]
        - level_3[:, 1, 1, 0]
        - level_3[:, 0, 1, 1]
    )
    return np.column_stack([signed_area, time_time_price, price_time_price])


def resample_complete_bars(m1: pd.DataFrame, timeframe_minutes: int) -> pd.DataFrame:
    """Aggregate UTC M1 bars and keep only fully observed timeframe bars."""

    if timeframe_minutes <= 0:
        raise ValueError("timeframe_minutes must be positive")
    source = validate_m1_frame(m1).set_index("timestamp")
    rule = f"{timeframe_minutes}min"
    previous_close = source["close"].shift(1).replace(0, np.nan)
    source["_intrabar_return"] = np.log(source["close"] / previous_close)
    source["_intrabar_body_return"] = (
        (source["close"] - source["open"])
        / source["open"].abs().replace(0, np.nan)
    )
    source["_intrabar_abs_body_return"] = source["_intrabar_body_return"].abs()
    source["_intrabar_up"] = source["_intrabar_body_return"].gt(0).astype("float64")
    bucket = source.index.floor(rule)
    position = source.groupby(bucket, sort=False).cumcount()
    bucket_group = source.groupby(bucket, sort=False)
    normalized_position = position / max(timeframe_minutes - 1, 1)
    bucket_high = bucket_group["high"].transform("max")
    bucket_low = bucket_group["low"].transform("min")
    bucket_open = bucket_group["open"].transform("first")
    bucket_close = bucket_group["close"].transform("last")
    bucket_range = bucket_high - bucket_low
    profile_scale = bucket_range.replace(0, np.nan)
    m1_range = source["high"] - source["low"]
    m1_range_scale = m1_range.replace(0, np.nan)
    lower_wick = np.minimum(source["open"], source["close"]) - source["low"]
    upper_wick = source["high"] - np.maximum(source["open"], source["close"])
    source["_intrabar_clv"] = (
        (2 * source["close"] - source["high"] - source["low"]) / m1_range_scale
    ).fillna(0.0)
    source["_intrabar_range"] = m1_range
    source["_intrabar_clv_range_product"] = source["_intrabar_clv"] * m1_range
    source["_intrabar_signed_range"] = np.sign(
        source["close"] - source["open"]
    ) * m1_range
    source["_intrabar_wick_pressure"] = lower_wick - upper_wick
    source["_intrabar_body"] = source["close"] - source["open"]
    source["_intrabar_clv_body_agreement"] = (
        np.sign(source["_intrabar_clv"])
        * np.sign(source["close"] - source["open"])
        > 0
    ).astype("float64")
    source["_intrabar_high_position"] = normalized_position.where(
        source["high"].eq(bucket_high)
    )
    source["_intrabar_low_position"] = normalized_position.where(
        source["low"].eq(bucket_low)
    )
    body_direction = np.sign(source["_intrabar_body_return"])
    previous_body_direction = body_direction.groupby(bucket, sort=False).shift(1)
    source["_intrabar_direction_change"] = (
        position.gt(0) & body_direction.ne(previous_body_direction)
    ).astype("float64")
    previous_high = source["high"].groupby(bucket, sort=False).shift(1)
    previous_low = source["low"].groupby(bucket, sort=False).shift(1)
    previous_range = m1_range.groupby(bucket, sort=False).shift(1)
    has_previous = position.gt(0)
    source["_intrabar_close_breakout_up"] = (
        has_previous & source["close"].gt(previous_high)
    ).astype("float64")
    source["_intrabar_close_breakout_down"] = (
        has_previous & source["close"].lt(previous_low)
    ).astype("float64")
    source["_intrabar_high_rejection"] = (
        has_previous
        & source["high"].gt(previous_high)
        & source["close"].le(previous_high)
    ).astype("float64")
    source["_intrabar_low_rejection"] = (
        has_previous
        & source["low"].lt(previous_low)
        & source["close"].ge(previous_low)
    ).astype("float64")
    source["_intrabar_inside_bar"] = (
        has_previous
        & source["high"].le(previous_high)
        & source["low"].ge(previous_low)
    ).astype("float64")
    source["_intrabar_outside_bar"] = (
        has_previous
        & source["high"].gt(previous_high)
        & source["low"].lt(previous_low)
    ).astype("float64")
    range_expansion = has_previous & m1_range.gt(previous_range)
    source["_intrabar_range_expansion"] = range_expansion.astype("float64")
    source["_intrabar_upward_range_expansion"] = (
        range_expansion & body_direction.gt(0)
    ).astype("float64")
    source["_intrabar_downward_range_expansion"] = (
        range_expansion & body_direction.lt(0)
    ).astype("float64")
    valid_direction_transition = (
        has_previous & body_direction.ne(0) & previous_body_direction.ne(0)
    )
    source["_intrabar_direction_continuation"] = (
        valid_direction_transition & body_direction.eq(previous_body_direction)
    ).astype("float64")
    source["_intrabar_direction_reversal"] = (
        valid_direction_transition & body_direction.ne(previous_body_direction)
    ).astype("float64")
    run_boundary = position.eq(0) | body_direction.ne(previous_body_direction)
    run_id = run_boundary.cumsum()
    run_length = source.groupby(run_id, sort=False).cumcount().add(1)
    source["_intrabar_up_run_length"] = run_length.where(
        body_direction.gt(0), 0
    )
    source["_intrabar_down_run_length"] = run_length.where(
        body_direction.lt(0), 0
    )
    source["_intrabar_abs_return"] = source["_intrabar_return"].abs()
    source["_intrabar_return_square"] = source["_intrabar_return"].pow(2)
    for percentile, quantile in ((10, 0.10), (25, 0.25), (50, 0.50), (75, 0.75), (90, 0.90)):
        source[f"_intrabar_return_quantile_{percentile}"] = source[
            "_intrabar_return"
        ].groupby(bucket, sort=False).transform("quantile", q=quantile)
    source["_intrabar_return_abs_median_deviation"] = (
        source["_intrabar_return"] - source["_intrabar_return_quantile_50"]
    ).abs()
    for frequency in range(1, 5):
        basis = (
            np.sqrt(2.0 / timeframe_minutes)
            * np.cos(
                np.pi
                * (position.to_numpy(dtype="float64") + 0.5)
                * frequency
                / timeframe_minutes
            )
            if frequency < timeframe_minutes
            else np.zeros(len(source), dtype="float64")
        )
        source[f"_intrabar_return_dct_{frequency}"] = (
            source["_intrabar_return"] * basis
        )
    for frequency in range(1, 3):
        basis = (
            np.sqrt(2.0 / timeframe_minutes)
            * np.cos(
                np.pi
                * (position.to_numpy(dtype="float64") + 0.5)
                * frequency
                / timeframe_minutes
            )
            if frequency < timeframe_minutes
            else np.zeros(len(source), dtype="float64")
        )
        source[f"_intrabar_range_dct_{frequency}"] = (
            source["_intrabar_range"] * basis
        )
    source["_intrabar_range_square"] = source["_intrabar_range"].pow(2)
    for lag in range(1, 4):
        lagged_return = source["_intrabar_return"].groupby(
            bucket, sort=False
        ).shift(lag)
        source[f"_intrabar_return_lag_product_{lag}"] = (
            source["_intrabar_return"] * lagged_return
        ).fillna(0.0)
    ordinal_return_0 = source["_intrabar_return"].groupby(
        bucket, sort=False
    ).shift(2)
    ordinal_return_1 = source["_intrabar_return"].groupby(
        bucket, sort=False
    ).shift(1)
    ordinal_return_2 = source["_intrabar_return"]
    ordinal_valid = position.ge(2) & ordinal_return_0.notna()
    source["_intrabar_ordinal_pattern_valid"] = ordinal_valid.astype("float64")
    # Rank each three-return window lexicographically by (return, position).
    # The position tie-break keeps all six patterns mutually exclusive without
    # injecting a price-scale-dependent epsilon.
    ordinal_rank_0 = (
        ordinal_return_1.lt(ordinal_return_0).astype("int8")
        + ordinal_return_2.lt(ordinal_return_0).astype("int8")
    )
    ordinal_rank_1 = (
        ordinal_return_0.le(ordinal_return_1).astype("int8")
        + ordinal_return_2.lt(ordinal_return_1).astype("int8")
    )
    ordinal_rank_2 = (
        ordinal_return_0.le(ordinal_return_2).astype("int8")
        + ordinal_return_1.le(ordinal_return_2).astype("int8")
    )
    ordinal_code = ordinal_rank_0 * 9 + ordinal_rank_1 * 3 + ordinal_rank_2
    ordinal_patterns = {
        "012": 5,
        "021": 7,
        "102": 11,
        "120": 15,
        "201": 19,
        "210": 21,
    }
    for pattern, code in ordinal_patterns.items():
        source[f"_intrabar_ordinal_pattern_{pattern}"] = (
            ordinal_valid & ordinal_code.eq(code)
        ).astype("float64")
    source["_intrabar_upside_variance"] = source[
        "_intrabar_return_square"
    ].where(source["_intrabar_return"].gt(0), 0.0)
    source["_intrabar_downside_variance"] = source[
        "_intrabar_return_square"
    ].where(source["_intrabar_return"].lt(0), 0.0)
    range_rank = source["_intrabar_range"].groupby(bucket, sort=False).rank(
        method="first", ascending=False
    )
    variance_rank = source["_intrabar_return_square"].groupby(
        bucket, sort=False
    ).rank(method="first", ascending=False)
    source["_intrabar_upside_variance_position_product"] = (
        source["_intrabar_upside_variance"] * normalized_position
    )
    source["_intrabar_downside_variance_position_product"] = (
        source["_intrabar_downside_variance"] * normalized_position
    )
    previous_abs_return = source["_intrabar_abs_return"].groupby(
        bucket, sort=False
    ).shift(1)
    source["_intrabar_bipower_product"] = (
        source["_intrabar_abs_return"] * previous_abs_return
    ).fillna(0.0)
    source["_intrabar_signed_largest_jump"] = (
        np.sign(source["_intrabar_return"])
        * source["_intrabar_return_square"]
    ).where(variance_rank.eq(1), 0.0)
    source["_intrabar_continuous_upside_variance"] = source[
        "_intrabar_upside_variance"
    ].where(~variance_rank.eq(1), 0.0)
    source["_intrabar_continuous_downside_variance"] = source[
        "_intrabar_downside_variance"
    ].where(~variance_rank.eq(1), 0.0)
    source["_intrabar_range_top3"] = source["_intrabar_range"].where(
        range_rank.le(3), 0.0
    )
    source["_intrabar_variance_top3"] = source[
        "_intrabar_return_square"
    ].where(variance_rank.le(3), 0.0)
    source["_intrabar_range_position_product"] = (
        source["_intrabar_range"] * normalized_position
    )
    source["_intrabar_variance_position_product"] = (
        source["_intrabar_return_square"] * normalized_position
    )
    running_high_close = source["close"].groupby(bucket, sort=False).cummax()
    running_low_close = source["close"].groupby(bucket, sort=False).cummin()
    source["_intrabar_drawdown"] = 1 - source["close"] / running_high_close
    source["_intrabar_runup"] = source["close"] / running_low_close - 1
    profile_progress = (position + 1) / timeframe_minutes
    source["_intrabar_profile_level"] = (
        source["close"] - bucket_open
    ) / profile_scale
    source["_intrabar_profile_deviation"] = source[
        "_intrabar_profile_level"
    ] - ((bucket_close - bucket_open) / profile_scale) * profile_progress
    flat_bucket = bucket_range.eq(0)
    source.loc[flat_bucket, "_intrabar_profile_level"] = 0.0
    source.loc[flat_bucket, "_intrabar_profile_deviation"] = 0.0
    source["_intrabar_profile_deviation_square"] = source[
        "_intrabar_profile_deviation"
    ].pow(2)
    for percentile in (20, 40, 60, 80):
        sample_position = max(
            0,
            min(
                timeframe_minutes - 1,
                int(np.ceil(timeframe_minutes * percentile / 100)) - 1,
            ),
        )
        source[f"_intrabar_profile_level_{percentile}"] = source[
            "_intrabar_profile_level"
        ].where(position.eq(sample_position))
        source[f"_intrabar_profile_deviation_{percentile}"] = source[
            "_intrabar_profile_deviation"
        ].where(position.eq(sample_position))
    segment_rows = max(1, timeframe_minutes // 3)
    source["_intrabar_early_body_return"] = source["_intrabar_body_return"].where(
        position < segment_rows,
        0.0,
    )
    source["_intrabar_late_body_return"] = source["_intrabar_body_return"].where(
        position >= timeframe_minutes - segment_rows,
        0.0,
    )
    source["_intrabar_early_clv"] = source["_intrabar_clv"].where(
        position < segment_rows
    )
    source["_intrabar_late_clv"] = source["_intrabar_clv"].where(
        position >= timeframe_minutes - segment_rows
    )
    source["_intrabar_early_range"] = source["_intrabar_range"].where(
        position < segment_rows, 0.0
    )
    source["_intrabar_late_range"] = source["_intrabar_range"].where(
        position >= timeframe_minutes - segment_rows, 0.0
    )
    source["_intrabar_early_variance"] = source[
        "_intrabar_return_square"
    ].where(position < segment_rows, 0.0)
    source["_intrabar_late_variance"] = source[
        "_intrabar_return_square"
    ].where(position >= timeframe_minutes - segment_rows, 0.0)
    source["_intrabar_early_upside_variance"] = source[
        "_intrabar_upside_variance"
    ].where(position < segment_rows, 0.0)
    source["_intrabar_early_downside_variance"] = source[
        "_intrabar_downside_variance"
    ].where(position < segment_rows, 0.0)
    source["_intrabar_late_upside_variance"] = source[
        "_intrabar_upside_variance"
    ].where(position >= timeframe_minutes - segment_rows, 0.0)
    source["_intrabar_late_downside_variance"] = source[
        "_intrabar_downside_variance"
    ].where(position >= timeframe_minutes - segment_rows, 0.0)
    grouped = source.resample(rule, origin="epoch", label="left", closed="left")
    full_profile_levels = source["_intrabar_profile_level"].groupby(
        [bucket, position], sort=False
    ).first().unstack()
    bars = grouped.agg(
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        source_rows=("close", "count"),
        intrabar_return_std=("_intrabar_return", "std"),
        intrabar_up_fraction=("_intrabar_up", "mean"),
        _intrabar_body_return_sum=("_intrabar_body_return", "sum"),
        _intrabar_abs_body_return_sum=("_intrabar_abs_body_return", "sum"),
        _intrabar_max_abs_body_return=("_intrabar_abs_body_return", "max"),
        intrabar_early_body_return=("_intrabar_early_body_return", "sum"),
        intrabar_late_body_return=("_intrabar_late_body_return", "sum"),
        intrabar_high_position=("_intrabar_high_position", "min"),
        intrabar_low_position=("_intrabar_low_position", "min"),
        intrabar_direction_change_fraction=("_intrabar_direction_change", "mean"),
        _intrabar_close_breakout_up_sum=("_intrabar_close_breakout_up", "sum"),
        _intrabar_close_breakout_down_sum=(
            "_intrabar_close_breakout_down",
            "sum",
        ),
        _intrabar_high_rejection_sum=("_intrabar_high_rejection", "sum"),
        _intrabar_low_rejection_sum=("_intrabar_low_rejection", "sum"),
        _intrabar_inside_bar_sum=("_intrabar_inside_bar", "sum"),
        _intrabar_outside_bar_sum=("_intrabar_outside_bar", "sum"),
        _intrabar_range_expansion_sum=("_intrabar_range_expansion", "sum"),
        _intrabar_upward_range_expansion_sum=(
            "_intrabar_upward_range_expansion",
            "sum",
        ),
        _intrabar_downward_range_expansion_sum=(
            "_intrabar_downward_range_expansion",
            "sum",
        ),
        _intrabar_direction_continuation_sum=(
            "_intrabar_direction_continuation",
            "sum",
        ),
        _intrabar_direction_reversal_sum=("_intrabar_direction_reversal", "sum"),
        _intrabar_max_up_run_length=("_intrabar_up_run_length", "max"),
        _intrabar_max_down_run_length=("_intrabar_down_run_length", "max"),
        _intrabar_return_sum=("_intrabar_return", "sum"),
        _intrabar_abs_return_sum=("_intrabar_abs_return", "sum"),
        _intrabar_return_square_sum=("_intrabar_return_square", "sum"),
        _intrabar_return_quantile_10=("_intrabar_return_quantile_10", "first"),
        _intrabar_return_quantile_25=("_intrabar_return_quantile_25", "first"),
        _intrabar_return_quantile_50=("_intrabar_return_quantile_50", "first"),
        _intrabar_return_quantile_75=("_intrabar_return_quantile_75", "first"),
        _intrabar_return_quantile_90=("_intrabar_return_quantile_90", "first"),
        _intrabar_return_mad=("_intrabar_return_abs_median_deviation", "median"),
        _intrabar_return_dct_1_sum=("_intrabar_return_dct_1", "sum"),
        _intrabar_return_dct_2_sum=("_intrabar_return_dct_2", "sum"),
        _intrabar_return_dct_3_sum=("_intrabar_return_dct_3", "sum"),
        _intrabar_return_dct_4_sum=("_intrabar_return_dct_4", "sum"),
        _intrabar_return_lag_product_1_sum=(
            "_intrabar_return_lag_product_1",
            "sum",
        ),
        _intrabar_return_lag_product_2_sum=(
            "_intrabar_return_lag_product_2",
            "sum",
        ),
        _intrabar_return_lag_product_3_sum=(
            "_intrabar_return_lag_product_3",
            "sum",
        ),
        _intrabar_ordinal_pattern_012_sum=(
            "_intrabar_ordinal_pattern_012",
            "sum",
        ),
        _intrabar_ordinal_pattern_021_sum=(
            "_intrabar_ordinal_pattern_021",
            "sum",
        ),
        _intrabar_ordinal_pattern_102_sum=(
            "_intrabar_ordinal_pattern_102",
            "sum",
        ),
        _intrabar_ordinal_pattern_120_sum=(
            "_intrabar_ordinal_pattern_120",
            "sum",
        ),
        _intrabar_ordinal_pattern_201_sum=(
            "_intrabar_ordinal_pattern_201",
            "sum",
        ),
        _intrabar_ordinal_pattern_210_sum=(
            "_intrabar_ordinal_pattern_210",
            "sum",
        ),
        _intrabar_ordinal_pattern_valid_sum=(
            "_intrabar_ordinal_pattern_valid",
            "sum",
        ),
        intrabar_max_drawdown=("_intrabar_drawdown", "max"),
        intrabar_max_runup=("_intrabar_runup", "max"),
        intrabar_profile_level_20=("_intrabar_profile_level_20", "min"),
        intrabar_profile_level_40=("_intrabar_profile_level_40", "min"),
        intrabar_profile_level_60=("_intrabar_profile_level_60", "min"),
        intrabar_profile_level_80=("_intrabar_profile_level_80", "min"),
        intrabar_profile_deviation_20=(
            "_intrabar_profile_deviation_20",
            "min",
        ),
        intrabar_profile_deviation_40=(
            "_intrabar_profile_deviation_40",
            "min",
        ),
        intrabar_profile_deviation_60=(
            "_intrabar_profile_deviation_60",
            "min",
        ),
        intrabar_profile_deviation_80=(
            "_intrabar_profile_deviation_80",
            "min",
        ),
        intrabar_profile_mean_deviation=(
            "_intrabar_profile_deviation",
            "mean",
        ),
        _intrabar_profile_mean_square_deviation=(
            "_intrabar_profile_deviation_square",
            "mean",
        ),
        intrabar_profile_max_deviation=(
            "_intrabar_profile_deviation",
            "max",
        ),
        intrabar_profile_min_deviation=(
            "_intrabar_profile_deviation",
            "min",
        ),
        intrabar_clv_mean=("_intrabar_clv", "mean"),
        intrabar_clv_std=("_intrabar_clv", "std"),
        intrabar_early_clv_mean=("_intrabar_early_clv", "mean"),
        intrabar_late_clv_mean=("_intrabar_late_clv", "mean"),
        _intrabar_range_sum=("_intrabar_range", "sum"),
        _intrabar_range_square_sum=("_intrabar_range_square", "sum"),
        _intrabar_range_dct_1_sum=("_intrabar_range_dct_1", "sum"),
        _intrabar_range_dct_2_sum=("_intrabar_range_dct_2", "sum"),
        _intrabar_range_max=("_intrabar_range", "max"),
        _intrabar_range_mean=("_intrabar_range", "mean"),
        _intrabar_range_std=("_intrabar_range", "std"),
        _intrabar_range_top3_sum=("_intrabar_range_top3", "sum"),
        _intrabar_range_position_sum=(
            "_intrabar_range_position_product",
            "sum",
        ),
        _intrabar_early_range_sum=("_intrabar_early_range", "sum"),
        _intrabar_late_range_sum=("_intrabar_late_range", "sum"),
        _intrabar_return_square_max=("_intrabar_return_square", "max"),
        _intrabar_variance_top3_sum=("_intrabar_variance_top3", "sum"),
        _intrabar_variance_position_sum=(
            "_intrabar_variance_position_product",
            "sum",
        ),
        _intrabar_early_variance_sum=("_intrabar_early_variance", "sum"),
        _intrabar_late_variance_sum=("_intrabar_late_variance", "sum"),
        _intrabar_upside_variance_sum=("_intrabar_upside_variance", "sum"),
        _intrabar_downside_variance_sum=("_intrabar_downside_variance", "sum"),
        _intrabar_upside_variance_max=("_intrabar_upside_variance", "max"),
        _intrabar_downside_variance_max=("_intrabar_downside_variance", "max"),
        _intrabar_upside_variance_position_sum=(
            "_intrabar_upside_variance_position_product",
            "sum",
        ),
        _intrabar_downside_variance_position_sum=(
            "_intrabar_downside_variance_position_product",
            "sum",
        ),
        _intrabar_bipower_product_sum=("_intrabar_bipower_product", "sum"),
        _intrabar_signed_largest_jump_sum=(
            "_intrabar_signed_largest_jump",
            "sum",
        ),
        _intrabar_continuous_upside_variance_sum=(
            "_intrabar_continuous_upside_variance",
            "sum",
        ),
        _intrabar_continuous_downside_variance_sum=(
            "_intrabar_continuous_downside_variance",
            "sum",
        ),
        _intrabar_early_upside_variance_sum=(
            "_intrabar_early_upside_variance",
            "sum",
        ),
        _intrabar_early_downside_variance_sum=(
            "_intrabar_early_downside_variance",
            "sum",
        ),
        _intrabar_late_upside_variance_sum=(
            "_intrabar_late_upside_variance",
            "sum",
        ),
        _intrabar_late_downside_variance_sum=(
            "_intrabar_late_downside_variance",
            "sum",
        ),
        _intrabar_clv_range_product_sum=("_intrabar_clv_range_product", "sum"),
        _intrabar_signed_range_sum=("_intrabar_signed_range", "sum"),
        _intrabar_wick_pressure_sum=("_intrabar_wick_pressure", "sum"),
        _intrabar_body_sum=("_intrabar_body", "sum"),
        intrabar_clv_body_agreement=("_intrabar_clv_body_agreement", "mean"),
    )
    bars = bars.loc[bars["source_rows"] == timeframe_minutes].reset_index()
    complete_profile_levels = full_profile_levels.reindex(
        index=pd.DatetimeIndex(bars["timestamp"]),
        columns=range(timeframe_minutes),
    )
    complete_profile_array = complete_profile_levels.to_numpy(dtype="float64")
    signature_values = np.empty(
        (len(complete_profile_array), len(INTRABAR_PATH_SIGNATURE_COLUMNS)),
        dtype="float64",
    )
    if timeframe_minutes == 1:
        # A one-segment path has no order interaction, so all bracket
        # projections are identically zero.  Avoid large temporary tensors on
        # multi-million-row M1 datasets.
        signature_values.fill(0.0)
    else:
        # M1 inputs can contain millions of rows.  Chunking caps the temporary
        # level-3 tensor while leaving the exact path calculation unchanged.
        signature_chunk_rows = 100_000
        for chunk_start in range(
            0, len(complete_profile_array), signature_chunk_rows
        ):
            chunk_end = min(
                chunk_start + signature_chunk_rows, len(complete_profile_array)
            )
            signature_values[chunk_start:chunk_end] = intrabar_path_signature(
                complete_profile_array[chunk_start:chunk_end]
            )
    for column_index, column in enumerate(INTRABAR_PATH_SIGNATURE_COLUMNS):
        bars[column] = signature_values[:, column_index]
    for grid_point in INTRABAR_FULL_PATH_GRID_POINTS:
        sample_position = max(
            0,
            min(
                timeframe_minutes - 1,
                int(np.ceil(timeframe_minutes * grid_point / 15)) - 1,
            ),
        )
        bars[f"intrabar_full_path_level_{grid_point:02d}"] = bars[
            "timestamp"
        ].map(full_profile_levels[sample_position])
    intrabar_denominator = bars["_intrabar_abs_body_return_sum"].replace(0, np.nan)
    bars["intrabar_body_directional_efficiency"] = (
        bars["_intrabar_body_return_sum"] / intrabar_denominator
    )
    bars["intrabar_body_concentration"] = (
        bars["_intrabar_max_abs_body_return"] / intrabar_denominator
    )
    no_intrabar_body = bars["_intrabar_abs_body_return_sum"].eq(0)
    bars.loc[
        no_intrabar_body, "intrabar_body_directional_efficiency"
    ] = 0.0
    bars.loc[no_intrabar_body, "intrabar_body_concentration"] = 0.0
    bars["intrabar_late_minus_early"] = (
        bars["intrabar_late_body_return"] - bars["intrabar_early_body_return"]
    )
    bars["intrabar_high_minus_low_position"] = (
        bars["intrabar_high_position"] - bars["intrabar_low_position"]
    )
    bars["intrabar_close_path_efficiency"] = (
        bars["_intrabar_return_sum"].abs()
        / bars["_intrabar_abs_return_sum"].replace(0, np.nan)
    )
    bars.loc[
        bars["_intrabar_abs_return_sum"].eq(0),
        "intrabar_close_path_efficiency",
    ] = 0.0
    log_range = np.log(bars["high"] / bars["low"])
    bars["intrabar_realized_variance_range"] = (
        bars["_intrabar_return_square_sum"] / log_range.pow(2).replace(0, np.nan)
    )
    bars.loc[log_range.eq(0), "intrabar_realized_variance_range"] = 0.0
    bars["intrabar_profile_rms_deviation"] = np.sqrt(
        bars["_intrabar_profile_mean_square_deviation"]
    )
    bars["intrabar_clv_std"] = bars["intrabar_clv_std"].fillna(0.0)
    bars["intrabar_clv_late_minus_early"] = (
        bars["intrabar_late_clv_mean"] - bars["intrabar_early_clv_mean"]
    )
    range_denominator = bars["_intrabar_range_sum"].replace(0, np.nan)
    bars["intrabar_range_weighted_clv"] = (
        bars["_intrabar_clv_range_product_sum"] / range_denominator
    )
    bars["intrabar_signed_range_pressure"] = (
        bars["_intrabar_signed_range_sum"] / range_denominator
    )
    bars["intrabar_wick_pressure"] = (
        bars["_intrabar_wick_pressure_sum"] / range_denominator
    )
    bars["intrabar_body_range_pressure"] = (
        bars["_intrabar_body_sum"] / range_denominator
    )
    zero_intrabar_range = bars["_intrabar_range_sum"].eq(0)
    pressure_ratio_columns = [
        "intrabar_range_weighted_clv",
        "intrabar_signed_range_pressure",
        "intrabar_wick_pressure",
        "intrabar_body_range_pressure",
    ]
    bars.loc[zero_intrabar_range, pressure_ratio_columns] = 0.0
    bars["intrabar_clv_body_divergence"] = (
        bars["intrabar_range_weighted_clv"]
        - bars["intrabar_body_range_pressure"]
    )
    bars["intrabar_range_concentration"] = (
        bars["_intrabar_range_max"] / range_denominator
    )
    bars["intrabar_range_top3_fraction"] = (
        bars["_intrabar_range_top3_sum"] / range_denominator
    )
    bars["intrabar_range_dispersion"] = (
        bars["_intrabar_range_std"]
        / bars["_intrabar_range_mean"].replace(0, np.nan)
    )
    bars["intrabar_range_center_of_mass"] = (
        bars["_intrabar_range_position_sum"] / range_denominator
    )
    bars["intrabar_early_range_fraction"] = (
        bars["_intrabar_early_range_sum"] / range_denominator
    )
    bars["intrabar_late_range_fraction"] = (
        bars["_intrabar_late_range_sum"] / range_denominator
    )
    bars["intrabar_range_late_minus_early"] = (
        bars["intrabar_late_range_fraction"]
        - bars["intrabar_early_range_fraction"]
    )
    range_shape_columns = [
        "intrabar_range_concentration",
        "intrabar_range_top3_fraction",
        "intrabar_range_dispersion",
        "intrabar_range_center_of_mass",
        "intrabar_early_range_fraction",
        "intrabar_late_range_fraction",
        "intrabar_range_late_minus_early",
    ]
    bars.loc[zero_intrabar_range, range_shape_columns] = 0.0

    variance_denominator = bars["_intrabar_return_square_sum"].replace(0, np.nan)
    bars["intrabar_variance_concentration"] = (
        bars["_intrabar_return_square_max"] / variance_denominator
    )
    bars["intrabar_variance_top3_fraction"] = (
        bars["_intrabar_variance_top3_sum"] / variance_denominator
    )
    bars["intrabar_variance_center_of_mass"] = (
        bars["_intrabar_variance_position_sum"] / variance_denominator
    )
    bars["intrabar_early_variance_fraction"] = (
        bars["_intrabar_early_variance_sum"] / variance_denominator
    )
    bars["intrabar_late_variance_fraction"] = (
        bars["_intrabar_late_variance_sum"] / variance_denominator
    )
    bars["intrabar_variance_late_minus_early"] = (
        bars["intrabar_late_variance_fraction"]
        - bars["intrabar_early_variance_fraction"]
    )
    variance_shape_columns = [
        "intrabar_variance_concentration",
        "intrabar_variance_top3_fraction",
        "intrabar_variance_center_of_mass",
        "intrabar_early_variance_fraction",
        "intrabar_late_variance_fraction",
        "intrabar_variance_late_minus_early",
    ]
    zero_intrabar_variance = bars["_intrabar_return_square_sum"].eq(0)
    bars.loc[zero_intrabar_variance, variance_shape_columns] = 0.0
    bars["intrabar_range_variance_concentration_gap"] = (
        bars["intrabar_range_concentration"]
        - bars["intrabar_variance_concentration"]
    )
    return_rms = np.sqrt(
        bars["_intrabar_return_square_sum"] / timeframe_minutes
    ).replace(0, np.nan)
    distribution_shape_columns = []
    for percentile in (10, 25, 50, 75, 90):
        name = f"intrabar_return_quantile_{percentile}_rms"
        bars[name] = bars[f"_intrabar_return_quantile_{percentile}"] / return_rms
        distribution_shape_columns.append(name)
    interquartile_range = (
        bars["_intrabar_return_quantile_75"]
        - bars["_intrabar_return_quantile_25"]
    )
    interdecile_range = (
        bars["_intrabar_return_quantile_90"]
        - bars["_intrabar_return_quantile_10"]
    )
    bars["intrabar_return_bowley_skew"] = (
        bars["_intrabar_return_quantile_75"]
        + bars["_intrabar_return_quantile_25"]
        - 2 * bars["_intrabar_return_quantile_50"]
    ) / interquartile_range.replace(0, np.nan)
    bars["intrabar_return_tail_skew"] = (
        bars["_intrabar_return_quantile_90"]
        + bars["_intrabar_return_quantile_10"]
        - 2 * bars["_intrabar_return_quantile_50"]
    ) / interdecile_range.replace(0, np.nan)
    bars["intrabar_return_central_spread_fraction"] = (
        interquartile_range / interdecile_range.replace(0, np.nan)
    )
    bars["intrabar_return_mad_rms"] = bars["_intrabar_return_mad"] / return_rms
    distribution_shape_columns.extend(
        [
            "intrabar_return_bowley_skew",
            "intrabar_return_tail_skew",
            "intrabar_return_central_spread_fraction",
            "intrabar_return_mad_rms",
        ]
    )
    bars.loc[
        bars["_intrabar_return_square_sum"].eq(0), distribution_shape_columns
    ] = 0.0
    bars[distribution_shape_columns] = bars[distribution_shape_columns].fillna(0.0)
    ordinal_patterns = ("012", "021", "102", "120", "201", "210")
    ordinal_denominator = bars["_intrabar_ordinal_pattern_valid_sum"].replace(
        0, np.nan
    )
    ordinal_columns = []
    for pattern in ordinal_patterns:
        name = f"intrabar_ordinal_pattern_{pattern}_fraction"
        bars[name] = (
            bars[f"_intrabar_ordinal_pattern_{pattern}_sum"]
            / ordinal_denominator
        )
        ordinal_columns.append(name)
    ordinal_probabilities = bars[ordinal_columns]
    entropy_terms = ordinal_probabilities * np.log(
        ordinal_probabilities.where(ordinal_probabilities.gt(0), 1.0)
    )
    bars["intrabar_ordinal_pattern_entropy"] = (
        -entropy_terms.sum(axis=1) / np.log(len(ordinal_patterns))
    )
    ordinal_output_columns = [
        *ordinal_columns,
        "intrabar_ordinal_pattern_entropy",
    ]
    no_ordinal_dynamics = ordinal_denominator.isna() | bars[
        "_intrabar_return_square_sum"
    ].eq(0)
    bars.loc[no_ordinal_dynamics, ordinal_output_columns] = 0.0
    transition_denominator = float(max(timeframe_minutes - 1, 1))
    breakout_state_columns = {
        "intrabar_close_breakout_up_fraction": "_intrabar_close_breakout_up_sum",
        "intrabar_close_breakout_down_fraction": "_intrabar_close_breakout_down_sum",
        "intrabar_high_rejection_fraction": "_intrabar_high_rejection_sum",
        "intrabar_low_rejection_fraction": "_intrabar_low_rejection_sum",
        "intrabar_inside_bar_fraction": "_intrabar_inside_bar_sum",
        "intrabar_outside_bar_fraction": "_intrabar_outside_bar_sum",
        "intrabar_range_expansion_fraction": "_intrabar_range_expansion_sum",
        "intrabar_upward_range_expansion_fraction": "_intrabar_upward_range_expansion_sum",
        "intrabar_downward_range_expansion_fraction": "_intrabar_downward_range_expansion_sum",
        "intrabar_direction_continuation_fraction": "_intrabar_direction_continuation_sum",
        "intrabar_direction_reversal_fraction": "_intrabar_direction_reversal_sum",
    }
    for output_column, aggregate_column in breakout_state_columns.items():
        bars[output_column] = bars[aggregate_column] / transition_denominator
    bars["intrabar_signed_run_length_imbalance"] = (
        bars["_intrabar_max_up_run_length"]
        - bars["_intrabar_max_down_run_length"]
    ) / float(timeframe_minutes)
    breakout_output_columns = [
        *breakout_state_columns,
        "intrabar_signed_run_length_imbalance",
    ]
    bars.loc[
        bars["high"].eq(bars["low"]), breakout_output_columns
    ] = 0.0
    centered_return_energy = (
        bars["_intrabar_return_square_sum"]
        - bars["_intrabar_return_sum"].pow(2) / timeframe_minutes
    ).clip(lower=0.0)
    centered_return_denominator = centered_return_energy.replace(0, np.nan)
    return_frequency_columns = []
    for frequency in range(1, 5):
        name = f"intrabar_return_dct_energy_fraction_{frequency}"
        bars[name] = (
            bars[f"_intrabar_return_dct_{frequency}_sum"].pow(2)
            / centered_return_denominator
        ).clip(lower=0.0, upper=1.0)
        return_frequency_columns.append(name)
    bars["intrabar_return_low_frequency_fraction"] = (
        bars["intrabar_return_dct_energy_fraction_1"]
        + bars["intrabar_return_dct_energy_fraction_2"]
    ).clip(upper=1.0)
    bars["intrabar_return_mid_frequency_fraction"] = (
        bars["intrabar_return_dct_energy_fraction_3"]
        + bars["intrabar_return_dct_energy_fraction_4"]
    ).clip(upper=1.0)
    bars["intrabar_return_high_frequency_fraction"] = (
        1.0
        - bars[return_frequency_columns].sum(axis=1)
    ).clip(lower=0.0, upper=1.0)
    bars["intrabar_return_low_high_frequency_balance"] = (
        bars["intrabar_return_low_frequency_fraction"]
        - bars["intrabar_return_high_frequency_fraction"]
    )
    return_energy_denominator = bars["_intrabar_return_square_sum"].replace(
        0, np.nan
    )
    for lag in range(1, 4):
        scale_factor = (
            timeframe_minutes / (timeframe_minutes - lag)
            if timeframe_minutes > lag
            else 0.0
        )
        bars[f"intrabar_return_autocorrelation_{lag}"] = (
            scale_factor
            * bars[f"_intrabar_return_lag_product_{lag}_sum"]
            / return_energy_denominator
        ).clip(lower=-1.0, upper=1.0)
    centered_range_energy = (
        bars["_intrabar_range_square_sum"]
        - bars["_intrabar_range_sum"].pow(2) / timeframe_minutes
    ).clip(lower=0.0)
    centered_range_denominator = centered_range_energy.replace(0, np.nan)
    bars["intrabar_range_low_frequency_fraction"] = (
        (
            bars["_intrabar_range_dct_1_sum"].pow(2)
            + bars["_intrabar_range_dct_2_sum"].pow(2)
        )
        / centered_range_denominator
    ).clip(lower=0.0, upper=1.0)
    frequency_shape_columns = [
        *return_frequency_columns,
        "intrabar_return_low_frequency_fraction",
        "intrabar_return_mid_frequency_fraction",
        "intrabar_return_high_frequency_fraction",
        "intrabar_return_low_high_frequency_balance",
        "intrabar_return_autocorrelation_1",
        "intrabar_return_autocorrelation_2",
        "intrabar_return_autocorrelation_3",
        "intrabar_range_low_frequency_fraction",
    ]
    bars.loc[
        centered_return_energy.eq(0),
        return_frequency_columns
        + [
            "intrabar_return_low_frequency_fraction",
            "intrabar_return_mid_frequency_fraction",
            "intrabar_return_high_frequency_fraction",
            "intrabar_return_low_high_frequency_balance",
        ],
    ] = 0.0
    bars.loc[
        bars["_intrabar_return_square_sum"].eq(0),
        [
            "intrabar_return_autocorrelation_1",
            "intrabar_return_autocorrelation_2",
            "intrabar_return_autocorrelation_3",
        ],
    ] = 0.0
    bars.loc[
        centered_range_energy.eq(0),
        "intrabar_range_low_frequency_fraction",
    ] = 0.0
    upside_variance_denominator = bars["_intrabar_upside_variance_sum"].replace(
        0, np.nan
    )
    downside_variance_denominator = bars[
        "_intrabar_downside_variance_sum"
    ].replace(0, np.nan)
    bars["intrabar_upside_semivariance_fraction"] = (
        bars["_intrabar_upside_variance_sum"] / variance_denominator
    )
    bars["intrabar_downside_semivariance_fraction"] = (
        bars["_intrabar_downside_variance_sum"] / variance_denominator
    )
    bars["intrabar_semivariance_imbalance"] = (
        bars["_intrabar_upside_variance_sum"]
        - bars["_intrabar_downside_variance_sum"]
    ) / variance_denominator
    upside_fraction = bars["intrabar_upside_semivariance_fraction"].clip(
        1e-12, 1 - 1e-12
    )
    bars["intrabar_semivariance_entropy"] = -(
        upside_fraction * np.log(upside_fraction)
        + (1 - upside_fraction) * np.log1p(-upside_fraction)
    ) / np.log(2.0)
    bars["intrabar_upside_variance_concentration"] = (
        bars["_intrabar_upside_variance_max"] / upside_variance_denominator
    )
    bars["intrabar_downside_variance_concentration"] = (
        bars["_intrabar_downside_variance_max"] / downside_variance_denominator
    )
    bars["intrabar_upside_variance_center_of_mass"] = (
        bars["_intrabar_upside_variance_position_sum"]
        / upside_variance_denominator
    )
    bars["intrabar_downside_variance_center_of_mass"] = (
        bars["_intrabar_downside_variance_position_sum"]
        / downside_variance_denominator
    )
    bars["intrabar_semivariance_timing_spread"] = (
        bars["intrabar_upside_variance_center_of_mass"]
        - bars["intrabar_downside_variance_center_of_mass"]
    )
    bars["intrabar_bipower_variation_ratio"] = (
        (np.pi / 2.0) * bars["_intrabar_bipower_product_sum"]
        / variance_denominator
    )
    bars["intrabar_jump_variation_fraction"] = (
        1.0 - bars["intrabar_bipower_variation_ratio"]
    ).clip(lower=0.0)
    bars["intrabar_signed_largest_jump_fraction"] = (
        bars["_intrabar_signed_largest_jump_sum"] / variance_denominator
    )
    continuous_variance_denominator = (
        bars["_intrabar_continuous_upside_variance_sum"]
        + bars["_intrabar_continuous_downside_variance_sum"]
    ).replace(0, np.nan)
    bars["intrabar_continuous_semivariance_imbalance"] = (
        bars["_intrabar_continuous_upside_variance_sum"]
        - bars["_intrabar_continuous_downside_variance_sum"]
    ) / continuous_variance_denominator
    early_variance_denominator = (
        bars["_intrabar_early_upside_variance_sum"]
        + bars["_intrabar_early_downside_variance_sum"]
    ).replace(0, np.nan)
    late_variance_denominator = (
        bars["_intrabar_late_upside_variance_sum"]
        + bars["_intrabar_late_downside_variance_sum"]
    ).replace(0, np.nan)
    early_semivariance_imbalance = (
        bars["_intrabar_early_upside_variance_sum"]
        - bars["_intrabar_early_downside_variance_sum"]
    ) / early_variance_denominator
    late_semivariance_imbalance = (
        bars["_intrabar_late_upside_variance_sum"]
        - bars["_intrabar_late_downside_variance_sum"]
    ) / late_variance_denominator
    bars["intrabar_semivariance_imbalance_late_minus_early"] = (
        late_semivariance_imbalance.fillna(0.0)
        - early_semivariance_imbalance.fillna(0.0)
    )
    signed_variation_columns = [
        "intrabar_upside_semivariance_fraction",
        "intrabar_downside_semivariance_fraction",
        "intrabar_semivariance_imbalance",
        "intrabar_semivariance_entropy",
        "intrabar_upside_variance_concentration",
        "intrabar_downside_variance_concentration",
        "intrabar_upside_variance_center_of_mass",
        "intrabar_downside_variance_center_of_mass",
        "intrabar_semivariance_timing_spread",
        "intrabar_bipower_variation_ratio",
        "intrabar_jump_variation_fraction",
        "intrabar_signed_largest_jump_fraction",
        "intrabar_continuous_semivariance_imbalance",
        "intrabar_semivariance_imbalance_late_minus_early",
    ]
    bars.loc[zero_intrabar_variance, signed_variation_columns] = 0.0
    one_sided_up = bars["_intrabar_downside_variance_sum"].eq(0)
    one_sided_down = bars["_intrabar_upside_variance_sum"].eq(0)
    bars.loc[
        one_sided_up,
        [
            "intrabar_downside_variance_concentration",
            "intrabar_downside_variance_center_of_mass",
        ],
    ] = 0.0
    bars.loc[
        one_sided_down,
        [
            "intrabar_upside_variance_concentration",
            "intrabar_upside_variance_center_of_mass",
        ],
    ] = 0.0
    bars.loc[
        one_sided_up | one_sided_down,
        "intrabar_semivariance_entropy",
    ] = 0.0
    bars["intrabar_semivariance_timing_spread"] = (
        bars["intrabar_upside_variance_center_of_mass"]
        - bars["intrabar_downside_variance_center_of_mass"]
    )
    bars["intrabar_continuous_semivariance_imbalance"] = bars[
        "intrabar_continuous_semivariance_imbalance"
    ].fillna(0.0)
    bars = bars.drop(
        columns=[
            "_intrabar_body_return_sum",
            "_intrabar_abs_body_return_sum",
            "_intrabar_max_abs_body_return",
            "_intrabar_return_sum",
            "_intrabar_abs_return_sum",
            "_intrabar_return_square_sum",
            "_intrabar_return_quantile_10",
            "_intrabar_return_quantile_25",
            "_intrabar_return_quantile_50",
            "_intrabar_return_quantile_75",
            "_intrabar_return_quantile_90",
            "_intrabar_return_mad",
            "_intrabar_return_dct_1_sum",
            "_intrabar_return_dct_2_sum",
            "_intrabar_return_dct_3_sum",
            "_intrabar_return_dct_4_sum",
            "_intrabar_return_lag_product_1_sum",
            "_intrabar_return_lag_product_2_sum",
            "_intrabar_return_lag_product_3_sum",
            "_intrabar_ordinal_pattern_012_sum",
            "_intrabar_ordinal_pattern_021_sum",
            "_intrabar_ordinal_pattern_102_sum",
            "_intrabar_ordinal_pattern_120_sum",
            "_intrabar_ordinal_pattern_201_sum",
            "_intrabar_ordinal_pattern_210_sum",
            "_intrabar_ordinal_pattern_valid_sum",
            "_intrabar_close_breakout_up_sum",
            "_intrabar_close_breakout_down_sum",
            "_intrabar_high_rejection_sum",
            "_intrabar_low_rejection_sum",
            "_intrabar_inside_bar_sum",
            "_intrabar_outside_bar_sum",
            "_intrabar_range_expansion_sum",
            "_intrabar_upward_range_expansion_sum",
            "_intrabar_downward_range_expansion_sum",
            "_intrabar_direction_continuation_sum",
            "_intrabar_direction_reversal_sum",
            "_intrabar_max_up_run_length",
            "_intrabar_max_down_run_length",
            "_intrabar_profile_mean_square_deviation",
            "_intrabar_range_sum",
            "_intrabar_range_square_sum",
            "_intrabar_range_dct_1_sum",
            "_intrabar_range_dct_2_sum",
            "_intrabar_range_max",
            "_intrabar_range_mean",
            "_intrabar_range_std",
            "_intrabar_range_top3_sum",
            "_intrabar_range_position_sum",
            "_intrabar_early_range_sum",
            "_intrabar_late_range_sum",
            "_intrabar_return_square_max",
            "_intrabar_variance_top3_sum",
            "_intrabar_variance_position_sum",
            "_intrabar_early_variance_sum",
            "_intrabar_late_variance_sum",
            "_intrabar_upside_variance_sum",
            "_intrabar_downside_variance_sum",
            "_intrabar_upside_variance_max",
            "_intrabar_downside_variance_max",
            "_intrabar_upside_variance_position_sum",
            "_intrabar_downside_variance_position_sum",
            "_intrabar_bipower_product_sum",
            "_intrabar_signed_largest_jump_sum",
            "_intrabar_continuous_upside_variance_sum",
            "_intrabar_continuous_downside_variance_sum",
            "_intrabar_early_upside_variance_sum",
            "_intrabar_early_downside_variance_sum",
            "_intrabar_late_upside_variance_sum",
            "_intrabar_late_downside_variance_sum",
            "_intrabar_clv_range_product_sum",
            "_intrabar_signed_range_sum",
            "_intrabar_wick_pressure_sum",
            "_intrabar_body_sum",
        ]
    )
    bars["timeframe_minutes"] = timeframe_minutes
    return bars


def _rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    loss = -delta.clip(upper=0).ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    relative_strength = gain / loss.replace(0, np.nan)
    return 100.0 - (100.0 / (1.0 + relative_strength))


def _causal_change_point_state(
    values: pd.Series,
    timestamps: pd.Series,
    timeframe_minutes: int,
) -> dict[str, pd.Series]:
    prior_mean = values.shift(1).rolling(
        CHANGE_POINT_REFERENCE_WINDOW,
        min_periods=CHANGE_POINT_REFERENCE_WINDOW,
    ).mean()
    prior_std = values.shift(1).rolling(
        CHANGE_POINT_REFERENCE_WINDOW,
        min_periods=CHANGE_POINT_REFERENCE_WINDOW,
    ).std()
    innovation = (
        (values - prior_mean) / prior_std.replace(0, np.nan)
    ).replace([np.inf, -np.inf], np.nan).fillna(0.0).clip(-5.0, 5.0)
    gap_units = pd.to_datetime(timestamps, utc=True).diff() / pd.Timedelta(
        minutes=timeframe_minutes
    )

    positive = np.zeros(len(values), dtype="float64")
    negative = np.zeros(len(values), dtype="float64")
    alarm_direction = np.zeros(len(values), dtype="float64")
    alarm_age = np.zeros(len(values), dtype="float64")
    positive_score = 0.0
    negative_score = 0.0
    previous_alarm = 0.0
    active_age = 0
    innovations = innovation.to_numpy(dtype="float64")
    gaps = gap_units.to_numpy(dtype="float64")
    for row, value in enumerate(innovations):
        if row and (not np.isfinite(gaps[row]) or gaps[row] > 1.0):
            positive_score = 0.0
            negative_score = 0.0
            previous_alarm = 0.0
            active_age = 0
        positive_score = min(
            CHANGE_POINT_SCORE_CAP,
            max(0.0, positive_score + value - CHANGE_POINT_DRIFT),
        )
        negative_score = min(
            CHANGE_POINT_SCORE_CAP,
            max(0.0, negative_score - value - CHANGE_POINT_DRIFT),
        )
        if (
            positive_score >= CHANGE_POINT_ALARM_THRESHOLD
            and positive_score > negative_score
        ):
            current_alarm = 1.0
        elif (
            negative_score >= CHANGE_POINT_ALARM_THRESHOLD
            and negative_score > positive_score
        ):
            current_alarm = -1.0
        else:
            current_alarm = 0.0
        if current_alarm:
            active_age = active_age + 1 if current_alarm == previous_alarm else 1
        else:
            active_age = 0
        positive[row] = positive_score / CHANGE_POINT_SCORE_CAP
        negative[row] = negative_score / CHANGE_POINT_SCORE_CAP
        alarm_direction[row] = current_alarm
        alarm_age[row] = min(active_age, CHANGE_POINT_AGE_CAP) / CHANGE_POINT_AGE_CAP
        previous_alarm = current_alarm

    index = values.index
    denominator = positive + negative
    balance = np.divide(
        positive - negative,
        denominator,
        out=np.zeros_like(denominator),
        where=denominator > 0,
    )
    return {
        "positive": pd.Series(positive, index=index),
        "negative": pd.Series(negative, index=index),
        "balance": pd.Series(balance, index=index),
        "alarm_direction": pd.Series(alarm_direction, index=index),
        "alarm_age": pd.Series(alarm_age, index=index),
    }


def _causal_shock_recovery_state(
    returns: pd.Series,
    ranges: pd.Series,
    timestamps: pd.Series,
    timeframe_minutes: int,
) -> dict[str, pd.Series]:
    def prior_innovation(values: pd.Series) -> pd.Series:
        prior_mean = values.shift(1).rolling(
            SHOCK_REFERENCE_WINDOW,
            min_periods=SHOCK_REFERENCE_WINDOW,
        ).mean()
        prior_std = values.shift(1).rolling(
            SHOCK_REFERENCE_WINDOW,
            min_periods=SHOCK_REFERENCE_WINDOW,
        ).std()
        return (
            (values - prior_mean) / prior_std.replace(0, np.nan)
        ).replace([np.inf, -np.inf], np.nan).fillna(0.0).clip(-5.0, 5.0)

    return_innovation = prior_innovation(returns)
    range_innovation = prior_innovation(ranges)
    gap_units = pd.to_datetime(timestamps, utc=True).diff() / pd.Timedelta(
        minutes=timeframe_minutes
    )

    row_count = len(returns)
    return_direction = np.zeros(row_count, dtype="float64")
    return_excess = np.zeros(row_count, dtype="float64")
    return_age = np.zeros(row_count, dtype="float64")
    return_response = np.zeros(row_count, dtype="float64")
    return_max_continuation = np.zeros(row_count, dtype="float64")
    return_max_reversal = np.zeros(row_count, dtype="float64")
    range_direction = np.zeros(row_count, dtype="float64")
    range_excess = np.zeros(row_count, dtype="float64")
    range_age = np.zeros(row_count, dtype="float64")
    joint_event = np.zeros(row_count, dtype="float64")

    active_return_direction = 0.0
    active_return_excess = 0.0
    active_return_age = 0
    active_return_scale = 1.0
    cumulative_after_shock = 0.0
    maximum_continuation = 0.0
    maximum_reversal = 0.0
    active_range_direction = 0.0
    active_range_excess = 0.0
    active_range_age = 0

    return_values = returns.to_numpy(dtype="float64")
    return_innovations = return_innovation.to_numpy(dtype="float64")
    range_innovations = range_innovation.to_numpy(dtype="float64")
    gaps = gap_units.to_numpy(dtype="float64")
    for row, (return_value, return_z, range_z) in enumerate(
        zip(return_values, return_innovations, range_innovations, strict=True)
    ):
        if row and (not np.isfinite(gaps[row]) or gaps[row] > 1.0):
            active_return_direction = 0.0
            active_return_excess = 0.0
            active_return_age = 0
            active_return_scale = 1.0
            cumulative_after_shock = 0.0
            maximum_continuation = 0.0
            maximum_reversal = 0.0
            active_range_direction = 0.0
            active_range_excess = 0.0
            active_range_age = 0

        is_return_shock = abs(return_z) >= SHOCK_Z_THRESHOLD
        is_range_shock = abs(range_z) >= SHOCK_Z_THRESHOLD
        if is_return_shock:
            active_return_direction = float(np.sign(return_z))
            active_return_excess = min(
                abs(return_z) - SHOCK_Z_THRESHOLD,
                SHOCK_RESPONSE_CAP,
            ) / SHOCK_RESPONSE_CAP
            active_return_age = 0
            active_return_scale = max(abs(return_value), np.finfo("float64").eps)
            cumulative_after_shock = 0.0
            maximum_continuation = 0.0
            maximum_reversal = 0.0
        elif active_return_direction:
            active_return_age += 1
            if active_return_age <= SHOCK_TRACKING_BARS:
                cumulative_after_shock += return_value
                signed_response = (
                    active_return_direction
                    * cumulative_after_shock
                    / active_return_scale
                )
                maximum_continuation = max(maximum_continuation, signed_response)
                maximum_reversal = max(maximum_reversal, -signed_response)
            else:
                active_return_direction = 0.0
                active_return_excess = 0.0
                active_return_age = 0
                cumulative_after_shock = 0.0
                maximum_continuation = 0.0
                maximum_reversal = 0.0

        if is_range_shock:
            active_range_direction = float(np.sign(range_z))
            active_range_excess = min(
                abs(range_z) - SHOCK_Z_THRESHOLD,
                SHOCK_RESPONSE_CAP,
            ) / SHOCK_RESPONSE_CAP
            active_range_age = 0
        elif active_range_direction:
            active_range_age += 1
            if active_range_age > SHOCK_TRACKING_BARS:
                active_range_direction = 0.0
                active_range_excess = 0.0
                active_range_age = 0

        return_direction[row] = active_return_direction
        return_excess[row] = active_return_excess
        return_age[row] = active_return_age / SHOCK_TRACKING_BARS
        if active_return_direction:
            signed_response = (
                active_return_direction
                * cumulative_after_shock
                / active_return_scale
            )
            return_response[row] = np.clip(
                signed_response,
                -SHOCK_RESPONSE_CAP,
                SHOCK_RESPONSE_CAP,
            ) / SHOCK_RESPONSE_CAP
            return_max_continuation[row] = min(
                maximum_continuation,
                SHOCK_RESPONSE_CAP,
            ) / SHOCK_RESPONSE_CAP
            return_max_reversal[row] = min(
                maximum_reversal,
                SHOCK_RESPONSE_CAP,
            ) / SHOCK_RESPONSE_CAP
        range_direction[row] = active_range_direction
        range_excess[row] = active_range_excess
        range_age[row] = active_range_age / SHOCK_TRACKING_BARS
        joint_event[row] = float(is_return_shock and is_range_shock)

    index = returns.index
    return {
        "return_innovation": return_innovation / 5.0,
        "range_innovation": range_innovation / 5.0,
        "return_direction": pd.Series(return_direction, index=index),
        "return_excess": pd.Series(return_excess, index=index),
        "return_age": pd.Series(return_age, index=index),
        "return_response": pd.Series(return_response, index=index),
        "return_max_continuation": pd.Series(return_max_continuation, index=index),
        "return_max_reversal": pd.Series(return_max_reversal, index=index),
        "range_direction": pd.Series(range_direction, index=index),
        "range_excess": pd.Series(range_excess, index=index),
        "range_age": pd.Series(range_age, index=index),
        "joint_event": pd.Series(joint_event, index=index),
    }


def _rolling_sum_array(values: np.ndarray, window: int) -> np.ndarray:
    if window <= 0:
        raise ValueError("rolling sum window must be positive")
    raw = np.asarray(values)
    output = np.full(len(raw), np.nan, dtype=np.result_type(raw.dtype, "float64"))
    if len(raw) < window:
        return output
    cumulative = np.concatenate(
        [np.zeros(1, dtype=output.dtype), np.cumsum(raw, dtype=output.dtype)]
    )
    output[window - 1 :] = cumulative[window:] - cumulative[:-window]
    return output


def rolling_spectral_state(
    returns: pd.Series,
    timestamps: pd.Series,
    timeframe_minutes: int,
    window: int = ROLLING_SPECTRAL_WINDOW,
) -> dict[str, pd.Series]:
    """Fixed-window causal DFT state with gap-safe, scale-free components."""
    if timeframe_minutes <= 0:
        raise ValueError("timeframe_minutes must be positive")
    if window < 16:
        raise ValueError("rolling spectral window must be at least 16")

    raw = returns.to_numpy(dtype="float64")
    finite = np.isfinite(raw)
    values = np.where(finite, raw, 0.0)
    rows = len(values)
    row_number = np.arange(rows, dtype="float64")
    count = _rolling_sum_array(finite.astype("float64"), window)
    rolling_sum = _rolling_sum_array(values, window)
    rolling_square_sum = _rolling_sum_array(values * values, window)
    centered_energy = rolling_square_sum - rolling_sum * rolling_sum / window
    centered_energy = np.maximum(centered_energy, 0.0)
    denominator = window * centered_energy

    timestamp = pd.to_datetime(timestamps, utc=True)
    expected_delta = pd.Timedelta(minutes=timeframe_minutes)
    gap_event = timestamp.diff().ne(expected_delta).to_numpy(dtype="float64")
    if rows:
        gap_event[0] = 0.0
    # A return at the first row after a gap crosses that gap, so invalidate
    # every window containing the marked return itself.
    gap_count = _rolling_sum_array(gap_event, window)
    valid = (
        np.equal(count, window)
        & np.equal(gap_count, 0.0)
        & np.isfinite(denominator)
        & (denominator > 0)
    )

    low_fraction = np.zeros(rows, dtype="float64")
    mid_fraction = np.zeros(rows, dtype="float64")
    phase_components: dict[str, np.ndarray] = {}
    frequencies = sorted(set(range(1, 7)) | set(ROLLING_SPECTRAL_PHASE_FREQUENCIES))
    for frequency in frequencies:
        angular_frequency = 2.0 * np.pi * frequency / window
        modulation = np.exp(-1j * angular_frequency * row_number)
        absolute_sum = _rolling_sum_array(values * modulation, window)
        window_start = row_number - window + 1
        coefficient = absolute_sum * np.exp(
            1j * angular_frequency * window_start
        )
        energy_fraction = np.zeros(rows, dtype="float64")
        energy_fraction[valid] = (
            2.0 * np.abs(coefficient[valid]) ** 2 / denominator[valid]
        )
        energy_fraction = np.clip(energy_fraction, 0.0, 1.0)
        if frequency <= 2:
            low_fraction += energy_fraction
        elif frequency <= 6:
            mid_fraction += energy_fraction
        if frequency in ROLLING_SPECTRAL_PHASE_FREQUENCIES:
            normalization = np.zeros(rows, dtype="float64")
            normalization[valid] = np.sqrt(2.0 / denominator[valid])
            cosine_component = np.zeros(rows, dtype="float64")
            sine_component = np.zeros(rows, dtype="float64")
            cosine_component[valid] = coefficient.real[valid] * normalization[valid]
            sine_component[valid] = coefficient.imag[valid] * normalization[valid]
            phase_components[f"rolling_spectral_cos_k{frequency}_64"] = (
                np.clip(cosine_component, -1.0, 1.0)
            )
            phase_components[f"rolling_spectral_sin_k{frequency}_64"] = (
                np.clip(sine_component, -1.0, 1.0)
            )

    low_fraction = np.clip(low_fraction, 0.0, 1.0)
    mid_fraction = np.clip(mid_fraction, 0.0, 1.0)
    high_fraction = np.where(
        valid,
        np.clip(1.0 - low_fraction - mid_fraction, 0.0, 1.0),
        0.0,
    )
    output = {
        "rolling_spectral_low_fraction_64": low_fraction,
        "rolling_spectral_mid_fraction_64": mid_fraction,
        "rolling_spectral_high_fraction_64": high_fraction,
        "rolling_spectral_low_high_balance_64": low_fraction - high_fraction,
        **phase_components,
    }
    return {
        name: pd.Series(values, index=returns.index, dtype="float64")
        for name, values in output.items()
    }


def _prior_window_sums(
    values: np.ndarray,
    windows: Sequence[int],
) -> dict[int, np.ndarray]:
    raw = np.asarray(values, dtype="float64")
    if any(window <= 0 for window in windows):
        raise ValueError("prior windows must be positive")
    cumulative = np.concatenate(
        [np.zeros(1, dtype="float64"), np.cumsum(raw, dtype="float64")]
    )
    positions = np.arange(len(raw), dtype="int64")
    return {
        window: cumulative[positions]
        - cumulative[np.maximum(positions - window, 0)]
        for window in windows
    }


def rolling_ordinal_motif(
    returns: pd.Series,
    timestamps: pd.Series,
    timeframe_minutes: int,
    windows: Sequence[int] = ROLLING_ORDINAL_WINDOWS,
) -> dict[str, pd.Series]:
    """Gap-safe ordinal distributions of completed-bar three-return motifs."""
    if timeframe_minutes <= 0:
        raise ValueError("timeframe_minutes must be positive")
    normalized_windows = tuple(int(window) for window in windows)
    if not normalized_windows or any(window < 8 for window in normalized_windows):
        raise ValueError("rolling ordinal windows must be at least 8")

    raw = returns.to_numpy(dtype="float64")
    rows = len(raw)
    if len(timestamps) != rows:
        raise ValueError("rolling ordinal inputs must have identical lengths")
    finite = np.isfinite(raw)
    values = np.where(finite, raw, 0.0)
    timestamp = pd.to_datetime(timestamps, utc=True)
    expected_delta = pd.Timedelta(minutes=timeframe_minutes)
    contiguous = timestamp.diff().eq(expected_delta).to_numpy(dtype="bool")
    if rows:
        contiguous[0] = False

    return_0 = np.roll(values, 2)
    return_1 = np.roll(values, 1)
    return_2 = values
    valid_0 = np.roll(finite, 2)
    valid_1 = np.roll(finite, 1)
    contiguous_1 = np.roll(contiguous, 1)
    if rows:
        return_0[:2] = 0.0
        return_1[0] = 0.0
        valid_0[:2] = False
        valid_1[0] = False
        contiguous_1[0] = False
    motif_valid = finite & valid_0 & valid_1 & contiguous & contiguous_1

    # Lexicographic (return, position) ranks keep tied observations in one of
    # six mutually exclusive patterns without a scale-dependent epsilon.
    rank_0 = (return_1 < return_0).astype("int8") + (
        return_2 < return_0
    ).astype("int8")
    rank_1 = (return_0 <= return_1).astype("int8") + (
        return_2 < return_1
    ).astype("int8")
    rank_2 = (return_0 <= return_2).astype("int8") + (
        return_1 <= return_2
    ).astype("int8")
    motif_code = rank_0 * 9 + rank_1 * 3 + rank_2
    pattern_masks = {
        pattern: motif_valid & (motif_code == code)
        for pattern, code in ROLLING_ORDINAL_PATTERNS.items()
    }

    gap_event = timestamp.diff().ne(expected_delta).to_numpy(dtype="float64")
    if rows:
        gap_event[0] = 0.0
    outputs: dict[str, np.ndarray] = {}
    entropies: dict[int, np.ndarray] = {}
    current_frequencies: dict[int, np.ndarray] = {}
    for window in normalized_windows:
        motif_count = _rolling_sum_array(
            motif_valid.astype("float64"), window
        )
        return_window = window + 2
        return_count = _rolling_sum_array(finite.astype("float64"), return_window)
        return_sum = _rolling_sum_array(values, return_window)
        return_square_sum = _rolling_sum_array(values * values, return_window)
        centered_energy = return_square_sum - return_sum * return_sum / return_window
        gap_count = _rolling_sum_array(gap_event, return_window)
        valid = (
            np.equal(motif_count, window)
            & np.equal(return_count, return_window)
            & np.equal(gap_count, 0.0)
            & np.isfinite(centered_energy)
            & (centered_energy > np.finfo("float64").eps)
        )

        fractions: dict[str, np.ndarray] = {}
        for pattern, pattern_mask in pattern_masks.items():
            pattern_count = _rolling_sum_array(
                pattern_mask.astype("float64"), window
            )
            fraction = np.zeros(rows, dtype="float64")
            fraction[valid] = pattern_count[valid] / window
            fractions[pattern] = fraction
            outputs[f"rolling_ordinal_{pattern}_fraction_{window}"] = fraction

        probabilities = np.column_stack(list(fractions.values()))
        entropy_terms = np.where(
            probabilities > 0,
            probabilities * np.log(np.where(probabilities > 0, probabilities, 1.0)),
            0.0,
        )
        entropy = np.zeros(rows, dtype="float64")
        entropy[valid] = -entropy_terms[valid].sum(axis=1) / np.log(
            len(ROLLING_ORDINAL_PATTERNS)
        )
        current_frequency = np.zeros(rows, dtype="float64")
        for pattern, code in ROLLING_ORDINAL_PATTERNS.items():
            current = valid & motif_valid & (motif_code == code)
            current_frequency[current] = fractions[pattern][current]
        outputs[f"rolling_ordinal_entropy_{window}"] = entropy
        outputs[f"rolling_ordinal_current_frequency_{window}"] = current_frequency
        entropies[window] = entropy
        current_frequencies[window] = current_frequency

    short_window = min(normalized_windows)
    long_window = max(normalized_windows)
    outputs["rolling_ordinal_entropy_short_long_delta"] = (
        entropies[short_window] - entropies[long_window]
    )
    outputs["rolling_ordinal_current_frequency_short_long_delta"] = (
        current_frequencies[short_window] - current_frequencies[long_window]
    )
    return {
        name: pd.Series(np.clip(values, -1.0, 1.0), index=returns.index)
        for name, values in outputs.items()
    }


def rolling_autoregressive_state(
    returns: pd.Series,
    timestamps: pd.Series,
    timeframe_minutes: int,
    windows: Sequence[int] = ROLLING_AR_WINDOWS,
    ridge_strength: float = ROLLING_AR_RIDGE_STRENGTH,
) -> dict[str, pd.Series]:
    """Causal scale-free local AR(3) state and prior-model innovation."""
    if timeframe_minutes <= 0:
        raise ValueError("timeframe_minutes must be positive")
    normalized_windows = tuple(int(window) for window in windows)
    if not normalized_windows or any(window < 8 for window in normalized_windows):
        raise ValueError("rolling autoregressive windows must be at least 8")
    if ridge_strength <= 0:
        raise ValueError("rolling autoregressive ridge strength must be positive")

    raw = returns.to_numpy(dtype="float64")
    rows = len(raw)
    if len(timestamps) != rows:
        raise ValueError("rolling autoregressive inputs must have identical lengths")
    finite = np.isfinite(raw)
    values = np.where(finite, raw, 0.0)
    timestamp = pd.to_datetime(timestamps, utc=True)
    expected_delta = pd.Timedelta(minutes=timeframe_minutes)
    contiguous = timestamp.diff().eq(expected_delta).to_numpy(dtype="bool")
    if rows:
        contiguous[0] = False

    lagged_values: list[np.ndarray] = []
    lagged_finite: list[np.ndarray] = []
    for lag in range(1, ROLLING_AR_LAGS + 1):
        lag_values = np.roll(values, lag)
        lag_finite = np.roll(finite, lag)
        lag_values[:lag] = 0.0
        lag_finite[:lag] = False
        lagged_values.append(lag_values)
        lagged_finite.append(lag_finite)

    sample_valid = finite.copy()
    for lag_finite in lagged_finite:
        sample_valid &= lag_finite
    for offset in range(ROLLING_AR_LAGS):
        transition_valid = np.roll(contiguous, offset)
        if offset:
            transition_valid[:offset] = False
        sample_valid &= transition_valid
    if rows:
        sample_valid[:ROLLING_AR_LAGS] = False

    design = np.column_stack(lagged_values)
    safe_design = np.where(sample_valid[:, None], design, 0.0)
    safe_target = np.where(sample_valid, values, 0.0)
    outputs: dict[str, np.ndarray] = {}
    forecasts: dict[int, np.ndarray] = {}
    fit_energies: dict[int, np.ndarray] = {}
    innovations: dict[int, np.ndarray] = {}

    for window in normalized_windows:
        sample_count = _rolling_sum_array(sample_valid.astype("float64"), window)
        target_sum = _rolling_sum_array(safe_target, window)
        target_square_sum = _rolling_sum_array(safe_target * safe_target, window)
        centered_target_energy = (
            target_square_sum - target_sum * target_sum / window
        )

        xtx = np.zeros((rows, ROLLING_AR_LAGS, ROLLING_AR_LAGS), dtype="float64")
        xty = np.zeros((rows, ROLLING_AR_LAGS), dtype="float64")
        for left in range(ROLLING_AR_LAGS):
            xty[:, left] = _rolling_sum_array(
                safe_design[:, left] * safe_target,
                window,
            )
            for right in range(left, ROLLING_AR_LAGS):
                product_sum = _rolling_sum_array(
                    safe_design[:, left] * safe_design[:, right],
                    window,
                )
                xtx[:, left, right] = product_sum
                xtx[:, right, left] = product_sum

        trace = np.trace(xtx, axis1=1, axis2=2)
        valid = (
            np.equal(sample_count, window)
            & np.isfinite(centered_target_energy)
            & (centered_target_energy > np.finfo("float64").eps)
            & np.isfinite(trace)
            & (trace > np.finfo("float64").eps)
        )
        coefficients = np.zeros((rows, ROLLING_AR_LAGS), dtype="float64")
        if valid.any():
            regularized = xtx[valid].copy()
            ridge = ridge_strength * trace[valid] / ROLLING_AR_LAGS
            diagonal = np.arange(ROLLING_AR_LAGS)
            regularized[:, diagonal, diagonal] += ridge[:, None]
            coefficients[valid] = np.linalg.solve(regularized, xty[valid])

        target_rms = np.zeros(rows, dtype="float64")
        target_rms[valid] = np.sqrt(target_square_sum[valid] / window)
        next_design = np.column_stack([values, *lagged_values[:2]])
        raw_forecast = np.einsum("ij,ij->i", coefficients, next_design)
        forecast = np.zeros(rows, dtype="float64")
        forecast[valid] = np.clip(
            raw_forecast[valid] / target_rms[valid],
            -3.0,
            3.0,
        ) / 3.0

        fitted_energy = np.zeros(rows, dtype="float64")
        if valid.any():
            coefficient_valid = coefficients[valid]
            explained = (
                2.0 * np.einsum("ij,ij->i", coefficient_valid, xty[valid])
                - np.einsum(
                    "ij,ijk,ik->i",
                    coefficient_valid,
                    xtx[valid],
                    coefficient_valid,
                )
            )
            fitted_energy[valid] = np.clip(
                explained / target_square_sum[valid],
                -1.0,
                1.0,
            )

        previous_coefficients = np.roll(coefficients, 1, axis=0)
        previous_valid = np.roll(valid, 1)
        previous_rms = np.roll(target_rms, 1)
        if rows:
            previous_coefficients[0] = 0.0
            previous_valid[0] = False
            previous_rms[0] = 0.0
        current_prior_forecast = np.einsum(
            "ij,ij->i",
            previous_coefficients,
            design,
        )
        innovation_valid = (
            sample_valid
            & previous_valid
            & np.isfinite(previous_rms)
            & (previous_rms > np.finfo("float64").eps)
        )
        innovation = np.zeros(rows, dtype="float64")
        innovation[innovation_valid] = np.clip(
            (
                values[innovation_valid]
                - current_prior_forecast[innovation_valid]
            )
            / previous_rms[innovation_valid],
            -3.0,
            3.0,
        ) / 3.0

        for lag in range(ROLLING_AR_LAGS):
            outputs[f"rolling_ar_lag{lag + 1}_coefficient_{window}"] = (
                np.clip(coefficients[:, lag], -2.0, 2.0) / 2.0
            )
        outputs[f"rolling_ar_forecast_{window}"] = forecast
        outputs[f"rolling_ar_fit_energy_{window}"] = fitted_energy
        outputs[f"rolling_ar_latest_innovation_{window}"] = innovation
        forecasts[window] = forecast
        fit_energies[window] = fitted_energy
        innovations[window] = innovation

    short_window = min(normalized_windows)
    long_window = max(normalized_windows)
    outputs["rolling_ar_forecast_short_long_delta"] = (
        forecasts[short_window] - forecasts[long_window]
    )
    outputs["rolling_ar_fit_energy_short_long_delta"] = (
        fit_energies[short_window] - fit_energies[long_window]
    )
    outputs["rolling_ar_innovation_short_long_delta"] = (
        innovations[short_window] - innovations[long_window]
    )
    return {
        name: pd.Series(np.clip(values, -1.0, 1.0), index=returns.index)
        for name, values in outputs.items()
    }


def rolling_transition_memory(
    returns: pd.Series,
    body_fraction: pd.Series,
    close_location: pd.Series,
    true_range: pd.Series,
    timestamps: pd.Series,
    timeframe_minutes: int,
    windows: Sequence[int] = ROLLING_TRANSITION_WINDOWS,
    prior_strength: float = ROLLING_TRANSITION_PRIOR_STRENGTH,
) -> dict[str, pd.Series]:
    """Causal local transition memory over fixed stationary candle states."""
    if timeframe_minutes <= 0:
        raise ValueError("timeframe_minutes must be positive")
    normalized_windows = tuple(int(window) for window in windows)
    if not normalized_windows or any(window <= 0 for window in normalized_windows):
        raise ValueError("transition memory windows must be positive")
    if prior_strength <= 0:
        raise ValueError("transition memory prior strength must be positive")

    raw_return = returns.to_numpy(dtype="float64")
    raw_body = body_fraction.to_numpy(dtype="float64")
    raw_close_location = close_location.to_numpy(dtype="float64")
    raw_range = true_range.to_numpy(dtype="float64")
    rows = len(raw_return)
    if not (
        len(raw_body) == rows
        and len(raw_close_location) == rows
        and len(raw_range) == rows
        and len(timestamps) == rows
    ):
        raise ValueError("transition memory inputs must have identical lengths")

    timestamp = pd.to_datetime(timestamps, utc=True)
    expected_delta = pd.Timedelta(minutes=timeframe_minutes)
    contiguous = timestamp.diff().eq(expected_delta).to_numpy(dtype="bool")
    if rows:
        contiguous[0] = False
    finite = (
        np.isfinite(raw_return)
        & np.isfinite(raw_body)
        & np.isfinite(raw_close_location)
        & np.isfinite(raw_range)
    )
    state_valid = contiguous & finite & (np.abs(raw_return) > 1e-15)

    body_bit = np.abs(np.nan_to_num(raw_body, nan=0.0)) >= 0.5
    close_bit = np.nan_to_num(raw_close_location, nan=0.5) >= 0.5
    range_series = pd.Series(raw_range, index=true_range.index, dtype="float64")
    prior_range_median = (
        range_series.rolling(20, min_periods=5).median().shift(1).to_numpy()
    )
    range_bit = np.isfinite(prior_range_median) & (raw_range >= prior_range_median)
    up_bit = raw_return > 0
    state = (
        up_bit.astype("int8") * 8
        + body_bit.astype("int8") * 4
        + close_bit.astype("int8") * 2
        + range_bit.astype("int8")
    )

    transition_valid = np.zeros(rows, dtype="bool")
    transition_up = np.zeros(rows, dtype="bool")
    if rows > 1:
        transition_valid[:-1] = state_valid[:-1] & state_valid[1:]
        transition_up[:-1] = raw_return[1:] > 0

    global_counts = _prior_window_sums(
        transition_valid.astype("float64"), normalized_windows
    )
    global_ups = _prior_window_sums(
        (transition_valid & transition_up).astype("float64"), normalized_windows
    )
    selected_counts = {
        window: np.zeros(rows, dtype="float64") for window in normalized_windows
    }
    selected_ups = {
        window: np.zeros(rows, dtype="float64") for window in normalized_windows
    }
    for state_value in range(16):
        current_mask = state_valid & (state == state_value)
        historical_mask = transition_valid & (state == state_value)
        count_sums = _prior_window_sums(
            historical_mask.astype("float64"), normalized_windows
        )
        up_sums = _prior_window_sums(
            (historical_mask & transition_up).astype("float64"),
            normalized_windows,
        )
        for window in normalized_windows:
            selected_counts[window][current_mask] = count_sums[window][current_mask]
            selected_ups[window][current_mask] = up_sums[window][current_mask]

    probabilities: dict[int, np.ndarray] = {}
    output: dict[str, np.ndarray] = {}
    for window in normalized_windows:
        global_probability = (global_ups[window] + 1.0) / (
            global_counts[window] + 2.0
        )
        probability = np.full(rows, 0.5, dtype="float64")
        posterior = (
            selected_ups[window] + prior_strength * global_probability
        ) / (selected_counts[window] + prior_strength)
        probability[state_valid] = posterior[state_valid]
        probabilities[window] = probability
        reversal_probability = np.where(up_bit, 1.0 - probability, probability)
        output[f"transition_memory_up_edge_{window}"] = np.where(
            state_valid, 2.0 * probability - 1.0, 0.0
        )
        output[f"transition_memory_support_fraction_{window}"] = np.where(
            state_valid,
            np.clip(selected_counts[window] / window, 0.0, 1.0),
            0.0,
        )
        output[f"transition_memory_local_global_delta_{window}"] = np.where(
            state_valid, probability - global_probability, 0.0
        )
        output[f"transition_memory_reversal_edge_{window}"] = np.where(
            state_valid, 2.0 * reversal_probability - 1.0, 0.0
        )

    short_window = min(normalized_windows)
    long_window = max(normalized_windows)
    output["transition_memory_short_long_delta"] = np.where(
        state_valid,
        probabilities[short_window] - probabilities[long_window],
        0.0,
    )
    return {
        name: pd.Series(np.clip(values, -1.0, 1.0), index=returns.index)
        for name, values in output.items()
    }


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
    close_location = (close - low) / (high - low).replace(0, np.nan)
    add("close_location", close_location)
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

    if feature_set == "trend_structure":
        def zero_safe_ratio(
            numerator: pd.Series, denominator: pd.Series
        ) -> pd.Series:
            output = numerator / denominator.replace(0, np.nan)
            return output.mask(denominator.eq(0), 0.0).fillna(0.0)

        period = 14
        up_move = high.diff()
        down_move = -low.diff()
        plus_directional_movement = up_move.where(
            (up_move > down_move) & (up_move > 0), 0.0
        )
        minus_directional_movement = down_move.where(
            (down_move > up_move) & (down_move > 0), 0.0
        )
        atr_14 = true_range.ewm(
            alpha=1 / period,
            adjust=False,
            min_periods=period,
        ).mean()
        plus_di = zero_safe_ratio(plus_directional_movement.ewm(
            alpha=1 / period,
            adjust=False,
            min_periods=period,
        ).mean(), atr_14)
        minus_di = zero_safe_ratio(minus_directional_movement.ewm(
            alpha=1 / period,
            adjust=False,
            min_periods=period,
        ).mean(), atr_14)
        directional_sum = plus_di + minus_di
        directional_index = zero_safe_ratio(
            (plus_di - minus_di).abs(), directional_sum
        )
        adx = directional_index.ewm(
            alpha=1 / period,
            adjust=False,
            min_periods=period,
        ).mean().fillna(0.0)
        add("plus_di_14", plus_di)
        add("minus_di_14", minus_di)
        add("adx_14", adx)
        add("di_balance_14", zero_safe_ratio(plus_di - minus_di, directional_sum))
        add("adx_change_3", adx.diff(3).fillna(0.0))

        atr_20 = rolling_atr[20].replace(0, np.nan)
        ema_12 = close.ewm(span=12, adjust=False, min_periods=12).mean()
        ema_26 = close.ewm(span=26, adjust=False, min_periods=26).mean()
        macd = ema_12 - ema_26
        macd_signal = macd.ewm(span=9, adjust=False, min_periods=9).mean()
        add("macd_atr_20", zero_safe_ratio(macd, atr_20))
        add(
            "macd_signal_gap_atr_20",
            zero_safe_ratio(macd - macd_signal, atr_20),
        )
        add(
            "atr_compression_5_20",
            zero_safe_ratio(rolling_atr[5], rolling_atr[20]),
        )
        add(
            "volatility_ratio_5_20",
            zero_safe_ratio(rolling_volatility[5], rolling_volatility[20]),
        )

        positive_realized = (
            log_return_1.clip(lower=0).pow(2).rolling(20, min_periods=20).sum().pow(0.5)
        )
        negative_realized = (
            log_return_1.clip(upper=0).pow(2).rolling(20, min_periods=20).sum().pow(0.5)
        )
        realized_sum = (positive_realized + negative_realized).replace(0, np.nan)
        add(
            "realized_volatility_balance_20",
            zero_safe_ratio(
                positive_realized - negative_realized,
                positive_realized + negative_realized,
            ),
        )
        up_fraction = (
            log_return_1.gt(0).astype("float64").rolling(20, min_periods=20).mean()
        )
        bounded_up_fraction = up_fraction.clip(1e-6, 1 - 1e-6)
        direction_entropy = -(
                bounded_up_fraction * np.log(bounded_up_fraction)
                + (1 - bounded_up_fraction) * np.log1p(-bounded_up_fraction)
            )
        direction_activity = log_return_1.abs().rolling(
            20, min_periods=20
        ).sum()
        add(
            "direction_entropy_20",
            (direction_entropy / np.log(2.0))
            .mask(direction_activity.eq(0), 0.0)
            .fillna(0.0),
        )

    if feature_set == "volatility_state":
        def zero_safe_ratio(
            numerator: pd.Series, denominator: pd.Series
        ) -> pd.Series:
            output = numerator / denominator.replace(0, np.nan)
            return output.mask(denominator.eq(0), 0.0)

        def symmetric_change(current: pd.Series, previous: pd.Series) -> pd.Series:
            denominator = current.abs() + previous.abs()
            return zero_safe_ratio(current - previous, denominator)

        volatility_5 = rolling_volatility[5]
        volatility_20 = rolling_volatility[20]
        for state_window in (20, 50):
            volatility_mean = volatility_5.rolling(
                state_window, min_periods=state_window
            ).mean()
            volatility_std = volatility_5.rolling(
                state_window, min_periods=state_window
            ).std()
            add(
                f"volatility_of_volatility_5_{state_window}",
                zero_safe_ratio(volatility_std, volatility_mean),
            )
        add(
            "volatility_acceleration_5_3",
            symmetric_change(volatility_5, volatility_5.shift(3)),
        )
        add(
            "volatility_acceleration_20_5",
            symmetric_change(volatility_20, volatility_20.shift(5)),
        )

        log_range = np.log(high / low.replace(0, np.nan)).clip(lower=0)
        range_mean_20 = log_range.rolling(20, min_periods=20).mean()
        range_std_20 = log_range.rolling(20, min_periods=20).std()
        add("range_coefficient_of_variation_20", zero_safe_ratio(
            range_std_20, range_mean_20
        ))
        range_autocorrelation_20 = log_range.rolling(
            20, min_periods=20
        ).corr(log_range.shift(1))
        constant_range = range_std_20.eq(0)
        add(
            "range_autocorrelation_20",
            range_autocorrelation_20.mask(constant_range, 0.0),
        )
        range_median_20 = log_range.rolling(20, min_periods=20).median()
        add(
            "range_median_deviation_20",
            symmetric_change(log_range, range_median_20),
        )
        prior_range_median_50 = log_range.rolling(
            50, min_periods=50
        ).median().shift(1)
        range_is_compressed = log_range.lt(prior_range_median_50).where(
            prior_range_median_50.notna()
        )
        add(
            "range_compression_fraction_5_50",
            range_is_compressed.astype("float64").rolling(
                5, min_periods=5
            ).mean(),
        )

        squared_return = log_return_1.pow(2)
        realized_variance_20 = squared_return.rolling(
            20, min_periods=20
        ).mean()
        bipower_variance_20 = (
            np.pi
            / 2.0
            * (
                log_return_1.abs() * log_return_1.abs().shift(1)
            ).rolling(20, min_periods=20).mean()
        )
        add(
            "jump_variation_fraction_20",
            zero_safe_ratio(
                (realized_variance_20 - bipower_variance_20).clip(lower=0),
                realized_variance_20,
            ).clip(0, 1),
        )
        parkinson_variance_20 = (
            log_range.pow(2).rolling(20, min_periods=20).mean()
            / (4.0 * np.log(2.0))
        )
        log_open_close = np.log(close / open_.replace(0, np.nan))
        garman_klass_variance = (
            0.5 * log_range.pow(2)
            - (2.0 * np.log(2.0) - 1.0) * log_open_close.pow(2)
        ).clip(lower=0)
        garman_klass_variance_20 = garman_klass_variance.rolling(
            20, min_periods=20
        ).mean()
        add(
            "parkinson_close_variance_balance_20",
            symmetric_change(parkinson_variance_20, realized_variance_20),
        )
        add(
            "garman_klass_close_variance_balance_20",
            symmetric_change(garman_klass_variance_20, realized_variance_20),
        )

    if feature_set == "path_persistence":
        absolute_path = log_return_1.abs()
        for window in (5, 10, 20, 50):
            path_length = absolute_path.rolling(
                window, min_periods=window
            ).sum().replace(0, np.nan)
            add(
                f"signed_efficiency_{window}",
                (np.log(close / close.shift(window)) / path_length).fillna(0.0),
            )

        for window in (10, 20):
            add(
                f"return_autocorrelation_{window}",
                log_return_1.rolling(window, min_periods=window).corr(
                    log_return_1.shift(1)
                ).fillna(0.0),
            )

        direction = np.sign(log_return_1).astype("float64")
        direction_changed = direction.ne(direction.shift(1)).astype("float64")
        for window in (10, 20):
            add(
                f"direction_change_fraction_{window}",
                direction_changed.rolling(window, min_periods=window).mean(),
            )

        one_step_variance = log_return_1.rolling(50, min_periods=50).var()
        for aggregation in (2, 5, 10):
            aggregated_return = np.log(close / close.shift(aggregation))
            aggregated_variance = aggregated_return.rolling(
                50, min_periods=50
            ).var()
            add(
                f"variance_ratio_{aggregation}_50",
                (
                    aggregated_variance
                    / (aggregation * one_step_variance).replace(0, np.nan)
                )
                .replace([np.inf, -np.inf], np.nan)
                .fillna(0.0),
            )

        previous_up = direction.shift(1).gt(0)
        previous_down = direction.shift(1).lt(0)
        previous_up_count = (
            previous_up.astype("float64")
            .rolling(20, min_periods=20)
            .sum()
            .replace(0, np.nan)
        )
        previous_down_count = (
            previous_down.astype("float64")
            .rolling(20, min_periods=20)
            .sum()
            .replace(0, np.nan)
        )
        add(
            "up_persistence_20",
            (
                (previous_up & direction.gt(0))
                .astype("float64")
                .rolling(20, min_periods=20)
                .sum()
                / previous_up_count
            ).fillna(0.0),
        )
        add(
            "down_persistence_20",
            (
                (previous_down & direction.lt(0))
                .astype("float64")
                .rolling(20, min_periods=20)
                .sum()
                / previous_down_count
            ).fillna(0.0),
        )
        direction_group = direction.ne(direction.shift(1)).cumsum()
        signed_streak = (
            direction.groupby(direction_group).cumcount().add(1).astype("float64")
            * direction
        )
        add("signed_return_streak_20", signed_streak.clip(-20, 20) / 20.0)

    if feature_set == "direction_transition_state":
        direction = np.sign(log_return_1).astype("float64")
        previous_direction = direction.shift(1)
        run_group = direction.ne(previous_direction).cumsum()
        run_length = (
            direction.groupby(run_group).cumcount().add(1).clip(upper=4)
        )
        add("transition_current_direction", direction)
        add(
            "transition_run_length_bucket",
            run_length.where(direction.ne(0), 0).astype("float64"),
        )

        valid_transition = direction.ne(0) & previous_direction.ne(0)
        reversal = (
            valid_transition & direction.ne(previous_direction)
        ).astype("float64")
        valid_count = valid_transition.astype("float64").rolling(
            8, min_periods=8
        ).sum()
        reversal_count = reversal.rolling(8, min_periods=8).sum()
        add(
            "transition_reversal_fraction_8",
            (reversal_count / valid_count.replace(0, np.nan)).fillna(0.0),
        )

        short_volatility = log_return_1.rolling(5, min_periods=5).std()
        long_volatility = log_return_1.rolling(20, min_periods=20).std()
        volatility_ratio = short_volatility / long_volatility.replace(0, np.nan)
        volatility_ratio = volatility_ratio.mask(
            short_volatility.eq(0) & long_volatility.eq(0), 1.0
        )
        volatility_ratio = volatility_ratio.mask(
            short_volatility.gt(0) & long_volatility.eq(0), np.inf
        )
        volatility_state = pd.Series(0.0, index=result.index)
        volatility_state = volatility_state.mask(volatility_ratio.lt(0.8), -1.0)
        volatility_state = volatility_state.mask(volatility_ratio.gt(1.25), 1.0)
        add("transition_volatility_state_5_20", volatility_state)

    if feature_set == "haar_multiscale":
        def zero_safe_haar_ratio(
            numerator: pd.Series, denominator: pd.Series
        ) -> pd.Series:
            output = numerator / denominator.replace(0, np.nan)
            return output.mask(denominator.eq(0), 0.0)

        absolute_return = log_return_1.abs()
        direction = np.sign(log_return_1).astype("float64")
        for window in (4, 8, 16, 32):
            half_window = window // 2
            recent_return = log_return_1.rolling(
                half_window, min_periods=half_window
            ).sum()
            prior_return = recent_return.shift(half_window)
            return_scale = (
                log_return_1.rolling(window, min_periods=window).std()
                * np.sqrt(window)
            )
            add(
                f"haar_return_detail_{window}",
                zero_safe_haar_ratio(recent_return - prior_return, return_scale),
            )

            recent_absolute = absolute_return.rolling(
                half_window, min_periods=half_window
            ).sum()
            prior_absolute = recent_absolute.shift(half_window)
            total_absolute = absolute_return.rolling(
                window, min_periods=window
            ).sum()
            add(
                f"haar_absolute_detail_{window}",
                zero_safe_haar_ratio(
                    recent_absolute - prior_absolute, total_absolute
                ),
            )

            recent_direction = direction.rolling(
                half_window, min_periods=half_window
            ).mean()
            prior_direction = recent_direction.shift(half_window)
            add(
                f"haar_direction_detail_{window}",
                (recent_direction - prior_direction) / 2.0,
            )

    if feature_set == "candle_pressure_state":
        candle_range = high - low
        safe_range = candle_range.replace(0, np.nan)
        upper_wick = high - pd.concat([open_, close], axis=1).max(axis=1)
        lower_wick = pd.concat([open_, close], axis=1).min(axis=1) - low
        body_share = ((close - open_) / safe_range).fillna(0.0).clip(-1, 1)
        wick_balance = (
            (lower_wick - upper_wick) / safe_range
        ).fillna(0.0).clip(-1, 1)
        close_pressure = (
            (2.0 * close - high - low) / safe_range
        ).fillna(0.0).clip(-1, 1)

        rolling_body_pressure: dict[int, pd.Series] = {}
        rolling_wick_pressure: dict[int, pd.Series] = {}
        rolling_close_pressure: dict[int, pd.Series] = {}
        for pressure_window in (3, 8, 21):
            rolling_body_pressure[pressure_window] = body_share.rolling(
                pressure_window, min_periods=pressure_window
            ).mean()
            rolling_wick_pressure[pressure_window] = wick_balance.rolling(
                pressure_window, min_periods=pressure_window
            ).mean()
            rolling_close_pressure[pressure_window] = close_pressure.rolling(
                pressure_window, min_periods=pressure_window
            ).mean()
            range_sum = candle_range.rolling(
                pressure_window, min_periods=pressure_window
            ).sum()
            add(
                f"body_pressure_mean_{pressure_window}",
                rolling_body_pressure[pressure_window],
            )
            add(
                f"wick_pressure_mean_{pressure_window}",
                rolling_wick_pressure[pressure_window],
            )
            add(
                f"close_pressure_mean_{pressure_window}",
                rolling_close_pressure[pressure_window],
            )
            add(
                f"range_weighted_body_pressure_{pressure_window}",
                (
                    (close - open_).rolling(
                        pressure_window, min_periods=pressure_window
                    ).sum()
                    / range_sum.replace(0, np.nan)
                ).fillna(0.0).clip(-1, 1),
            )
            add(
                f"range_weighted_wick_pressure_{pressure_window}",
                (
                    (lower_wick - upper_wick).rolling(
                        pressure_window, min_periods=pressure_window
                    ).sum()
                    / range_sum.replace(0, np.nan)
                ).fillna(0.0).clip(-1, 1),
            )

        add(
            "body_pressure_acceleration_3_8",
            rolling_body_pressure[3] - rolling_body_pressure[8],
        )
        add(
            "wick_pressure_acceleration_3_8",
            rolling_wick_pressure[3] - rolling_wick_pressure[8],
        )
        add(
            "close_pressure_acceleration_3_8",
            rolling_close_pressure[3] - rolling_close_pressure[8],
        )

    if feature_set == "bar_breakout_rejection":
        for breakout_window in (1, 5, 20):
            prior_high = high.rolling(
                breakout_window, min_periods=breakout_window
            ).max().shift(1)
            prior_low = low.rolling(
                breakout_window, min_periods=breakout_window
            ).min().shift(1)
            add(
                f"close_breakout_up_{breakout_window}",
                close.gt(prior_high).astype("float64"),
            )
            add(
                f"close_breakout_down_{breakout_window}",
                close.lt(prior_low).astype("float64"),
            )
            add(
                f"high_rejection_{breakout_window}",
                (high.gt(prior_high) & close.le(prior_high)).astype("float64"),
            )
            add(
                f"low_rejection_{breakout_window}",
                (low.lt(prior_low) & close.ge(prior_low)).astype("float64"),
            )

        candle_range = high - low
        previous_range = candle_range.shift(1)
        range_active = candle_range.gt(0) | previous_range.gt(0)
        add(
            "inside_previous_bar",
            (
                range_active
                & high.le(high.shift(1))
                & low.ge(low.shift(1))
            ).astype("float64"),
        )
        add(
            "outside_previous_bar",
            (
                range_active
                & high.gt(high.shift(1))
                & low.lt(low.shift(1))
            ).astype("float64"),
        )
        expanding_range = candle_range.gt(previous_range)
        add(
            "upward_range_expansion",
            (expanding_range & close.gt(open_)).astype("float64"),
        )
        add(
            "downward_range_expansion",
            (expanding_range & close.lt(open_)).astype("float64"),
        )

        prior_high_20 = high.rolling(20, min_periods=20).max().shift(1)
        prior_low_20 = low.rolling(20, min_periods=20).min().shift(1)
        prior_atr_20 = rolling_atr[20].shift(1)

        def bounded_breakout_distance(numerator: pd.Series) -> pd.Series:
            output = numerator / prior_atr_20.replace(0, np.nan)
            output = output.mask(prior_atr_20.eq(0) & numerator.eq(0), 0.0)
            output = output.mask(prior_atr_20.eq(0) & numerator.gt(0), 10.0)
            output = output.mask(prior_atr_20.eq(0) & numerator.lt(0), -10.0)
            return output.clip(-10, 10)

        add(
            "close_distance_to_prior_high_20_atr",
            bounded_breakout_distance(close - prior_high_20),
        )
        add(
            "close_distance_to_prior_low_20_atr",
            bounded_breakout_distance(close - prior_low_20),
        )

    if feature_set == "distribution_shift":
        recent_window = 8
        reference_window = 64
        rank_window = 128

        def zero_safe_ratio(
            numerator: pd.Series, denominator: pd.Series
        ) -> pd.Series:
            output = numerator / denominator.replace(0, np.nan)
            return output.mask(denominator.eq(0), 0.0)

        def symmetric_shift(
            recent: pd.Series, reference: pd.Series
        ) -> pd.Series:
            denominator = recent.abs() + reference.abs()
            return zero_safe_ratio(recent - reference, denominator).clip(-1, 1)

        def centered_rolling_rank(values: pd.Series) -> pd.Series:
            rank = values.rolling(
                rank_window, min_periods=rank_window
            ).rank(method="average")
            midpoint = (rank_window + 1.0) / 2.0
            half_span = (rank_window - 1.0) / 2.0
            return ((rank - midpoint) / half_span).clip(-1, 1)

        log_range = np.log(high / low.replace(0, np.nan)).clip(lower=0)
        log_body = np.log(close / open_.replace(0, np.nan))
        for name, values in (
            ("return", log_return_1),
            ("absolute_return", log_return_1.abs()),
            ("range", log_range),
            ("absolute_body", log_body.abs()),
        ):
            add(
                f"distribution_shift_{name}_rank_{rank_window}",
                centered_rolling_rank(values),
            )

        def recent_mean(values: pd.Series) -> pd.Series:
            return values.rolling(
                recent_window, min_periods=recent_window
            ).mean()

        def reference_mean(values: pd.Series) -> pd.Series:
            return values.shift(recent_window).rolling(
                reference_window, min_periods=reference_window
            ).mean()

        reference_return_mean = reference_mean(log_return_1)
        reference_return_std = log_return_1.shift(recent_window).rolling(
            reference_window, min_periods=reference_window
        ).std()
        add(
            "distribution_shift_return_location_8_64",
            zero_safe_ratio(
                recent_mean(log_return_1) - reference_return_mean,
                reference_return_std,
            ).clip(-5, 5),
        )

        recent_absolute_return = recent_mean(log_return_1.abs())
        reference_absolute_return = reference_mean(log_return_1.abs())
        add(
            "distribution_shift_absolute_return_scale_8_64",
            symmetric_shift(recent_absolute_return, reference_absolute_return),
        )
        add(
            "distribution_shift_variance_scale_8_64",
            symmetric_shift(
                recent_mean(log_return_1.pow(2)),
                reference_mean(log_return_1.pow(2)),
            ),
        )
        add(
            "distribution_shift_up_fraction_8_64",
            recent_mean(log_return_1.gt(0).astype("float64"))
            - reference_mean(log_return_1.gt(0).astype("float64")),
        )

        upper_threshold = log_return_1.shift(recent_window).rolling(
            reference_window, min_periods=reference_window
        ).quantile(0.80)
        lower_threshold = log_return_1.shift(recent_window).rolling(
            reference_window, min_periods=reference_window
        ).quantile(0.20)
        recent_returns = pd.concat(
            [log_return_1.shift(offset) for offset in range(recent_window)],
            axis=1,
        )
        upper_fraction = recent_returns.gt(upper_threshold, axis=0).mean(axis=1)
        lower_fraction = recent_returns.lt(lower_threshold, axis=0).mean(axis=1)
        active_reference = reference_absolute_return.gt(0)
        add(
            "distribution_shift_tail_balance_8_64",
            (upper_fraction - lower_fraction).where(active_reference, 0.0),
        )
        add(
            "distribution_shift_tail_activity_8_64",
            (upper_fraction + lower_fraction - 0.40).where(
                active_reference, 0.0
            ),
        )

        add(
            "distribution_shift_range_scale_8_64",
            symmetric_shift(recent_mean(log_range), reference_mean(log_range)),
        )
        add(
            "distribution_shift_body_scale_8_64",
            symmetric_shift(
                recent_mean(log_body.abs()), reference_mean(log_body.abs())
            ),
        )

        candle_range = (high - low).astype("float64")
        body_pressure = zero_safe_ratio(close - open_, candle_range).fillna(0.0)
        upper_wick = high - pd.concat([open_, close], axis=1).max(axis=1)
        lower_wick = pd.concat([open_, close], axis=1).min(axis=1) - low
        wick_pressure = zero_safe_ratio(
            lower_wick - upper_wick, candle_range
        ).fillna(0.0)
        close_pressure = zero_safe_ratio(
            2.0 * close - high - low, candle_range
        ).fillna(0.0)
        for name, values in (
            ("body_pressure", body_pressure),
            ("wick_pressure", wick_pressure),
            ("close_pressure", close_pressure),
        ):
            add(
                f"distribution_shift_{name}_8_64",
                (recent_mean(values) - reference_mean(values)).clip(-2, 2)
                / 2.0,
            )
        add(
            "distribution_shift_close_pressure_dispersion_8_64",
            symmetric_shift(
                close_pressure.rolling(
                    recent_window, min_periods=recent_window
                ).std(),
                close_pressure.shift(recent_window).rolling(
                    reference_window, min_periods=reference_window
                ).std(),
            ),
        )

    if feature_set == "rolling_spectral_state":
        spectral_features = rolling_spectral_state(
            log_return_1,
            result["timestamp"],
            timeframe_minutes,
        )
        for feature_name, values in spectral_features.items():
            add(feature_name, values)

    if feature_set == "rolling_ordinal_motif":
        ordinal_features = rolling_ordinal_motif(
            log_return_1,
            result["timestamp"],
            timeframe_minutes,
        )
        for feature_name, values in ordinal_features.items():
            add(feature_name, values)

    if feature_set == "rolling_autoregressive_state":
        autoregressive_features = rolling_autoregressive_state(
            log_return_1,
            result["timestamp"],
            timeframe_minutes,
        )
        for feature_name, values in autoregressive_features.items():
            add(feature_name, values)

    if feature_set == "rolling_transition_memory":
        candle_range = (high - low).replace(0, np.nan)
        transition_features = rolling_transition_memory(
            log_return_1,
            ((close - open_).abs() / candle_range).fillna(0.0),
            close_location.fillna(0.5),
            true_range,
            result["timestamp"],
            timeframe_minutes,
        )
        for feature_name, values in transition_features.items():
            add(feature_name, values)

    if feature_set == "rolling_distribution_shape":
        distribution_window = 64
        rolling_returns = log_return_1.rolling(
            distribution_window,
            min_periods=distribution_window,
        )
        return_rms = log_return_1.pow(2).rolling(
            distribution_window,
            min_periods=distribution_window,
        ).mean().pow(0.5)
        return_rms = return_rms.replace(0, np.nan)
        return_quantiles = {
            percentile: rolling_returns.quantile(quantile)
            for percentile, quantile in (
                (10, 0.10),
                (25, 0.25),
                (50, 0.50),
                (75, 0.75),
                (90, 0.90),
            )
        }
        for percentile in (10, 25, 50, 75, 90):
            add(
                f"rolling_return_quantile_{percentile}_rms_64",
                (return_quantiles[percentile] / return_rms).fillna(0.0),
            )

        interquartile_range = return_quantiles[75] - return_quantiles[25]
        interdecile_range = return_quantiles[90] - return_quantiles[10]
        add(
            "rolling_return_bowley_skew_64",
            (
                (
                    return_quantiles[75]
                    + return_quantiles[25]
                    - 2.0 * return_quantiles[50]
                )
                / interquartile_range.replace(0, np.nan)
            ).fillna(0.0),
        )
        add(
            "rolling_return_tail_skew_64",
            (
                (
                    return_quantiles[90]
                    + return_quantiles[10]
                    - 2.0 * return_quantiles[50]
                )
                / interdecile_range.replace(0, np.nan)
            ).fillna(0.0),
        )
        add(
            "rolling_return_central_spread_fraction_64",
            (
                interquartile_range
                / interdecile_range.replace(0, np.nan)
            ).fillna(0.0).clip(0, 1),
        )
        add(
            "rolling_return_l1_l2_concentration_64",
            (
                log_return_1.abs().rolling(
                    distribution_window,
                    min_periods=distribution_window,
                ).mean()
                / return_rms
            ).fillna(0.0).clip(0, 1),
        )

    if feature_set == "rolling_full_path":
        path_window = 15
        path_open = open_.shift(path_window - 1)
        path_high = high.rolling(
            path_window,
            min_periods=path_window,
        ).max()
        path_low = low.rolling(
            path_window,
            min_periods=path_window,
        ).min()
        path_range = path_high - path_low
        for point in INTRABAR_FULL_PATH_GRID_POINTS:
            point_close = close.shift(path_window - point)
            add(
                f"rolling_full_path_level_{point:02d}",
                (
                    (point_close - path_open)
                    / path_range.replace(0, np.nan)
                ).fillna(0.0).clip(-1, 1),
            )

    if feature_set == "change_point_state":
        change_channels = {
            "return": log_return_1,
            "range": np.log(high / low.replace(0, np.nan))
            .replace([np.inf, -np.inf], np.nan)
            .fillna(0.0)
            .clip(lower=0.0),
        }
        for channel_name, channel in change_channels.items():
            states = _causal_change_point_state(
                channel,
                result["timestamp"],
                timeframe_minutes,
            )
            for state_name, state in states.items():
                add(
                    f"change_point_{channel_name}_{state_name}_64",
                    state,
                )

    if feature_set == "shock_recovery_state":
        shock_states = _causal_shock_recovery_state(
            log_return_1,
            np.log(high / low.replace(0, np.nan))
            .replace([np.inf, -np.inf], np.nan)
            .fillna(0.0)
            .clip(lower=0.0),
            result["timestamp"],
            timeframe_minutes,
        )
        for state_name, state in shock_states.items():
            add(f"shock_{state_name}", state)

    if feature_set == "session_relative":
        session_hour = result["timestamp"].dt.dayofweek * 24 + result["timestamp"].dt.hour
        window = 32
        min_periods = 12

        def zero_safe_session_z(
            numerator: pd.Series, denominator: pd.Series
        ) -> pd.Series:
            output = numerator / denominator.replace(0, np.nan)
            zero_denominator = denominator.eq(0)
            output = output.mask(zero_denominator & numerator.eq(0), 0.0)
            output = output.mask(zero_denominator & numerator.gt(0), 10.0)
            output = output.mask(zero_denominator & numerator.lt(0), -10.0)
            return output.clip(-10, 10)

        def zero_safe_session_ratio(
            numerator: pd.Series, denominator: pd.Series
        ) -> pd.Series:
            output = numerator / denominator.replace(0, np.nan)
            zero_denominator = denominator.eq(0)
            output = output.mask(zero_denominator & numerator.eq(0), 0.0)
            output = output.mask(zero_denominator & numerator.gt(0), 10.0)
            return output.clip(0, 10)

        def prior_session_stat(values: pd.Series, statistic: str) -> pd.Series:
            shifted = values.groupby(session_hour, sort=False).shift(1)
            rolling = shifted.groupby(session_hour, sort=False).rolling(
                window, min_periods=min_periods
            )
            if statistic == "mean":
                computed = rolling.mean()
            elif statistic == "std":
                computed = rolling.std(ddof=0)
            else:
                raise ValueError(f"unknown session statistic: {statistic}")
            return computed.droplevel(0).sort_index()

        body_ratio = (close - open_) / scale
        range_ratio = (high - low) / scale
        prior_return_mean = prior_session_stat(log_return_1, "mean")
        prior_return_std = prior_session_stat(log_return_1, "std")
        prior_body_mean = prior_session_stat(body_ratio, "mean")
        prior_body_std = prior_session_stat(body_ratio, "std")
        prior_absolute_return = prior_session_stat(log_return_1.abs(), "mean")
        prior_range = prior_session_stat(range_ratio, "mean")
        prior_direction = prior_session_stat(
            np.sign(log_return_1).astype("float64"), "mean"
        )
        add(
            "session_return_z_32",
            zero_safe_session_z(log_return_1 - prior_return_mean, prior_return_std),
        )
        add(
            "session_body_z_32",
            zero_safe_session_z(body_ratio - prior_body_mean, prior_body_std),
        )
        add(
            "session_absolute_return_ratio_32",
            zero_safe_session_ratio(log_return_1.abs(), prior_absolute_return),
        )
        add(
            "session_range_ratio_32",
            zero_safe_session_ratio(range_ratio, prior_range),
        )
        add("session_direction_bias_32", prior_direction.clip(-1, 1))

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

    if feature_set in ("sequence_manual", "tcn_sequence"):
        atr_20 = rolling_atr[20]

        def zero_safe_sequence_ratio(
            numerator: pd.Series, denominator: pd.Series
        ) -> pd.Series:
            output = numerator / denominator.replace(0, np.nan)
            return output.mask(denominator.eq(0), 0.0).fillna(0.0)

        candle_range = high - low
        close_location_centered = (
            (close - low) / candle_range.replace(0, np.nan) - 0.5
        ).mask(candle_range.eq(0), 0.0).fillna(0.0)
        sequence_values = {
            "return_atr": zero_safe_sequence_ratio(close.diff(), atr_20),
            "body_atr": zero_safe_sequence_ratio(close - open_, atr_20),
            "range_atr": zero_safe_sequence_ratio(candle_range, atr_20),
            "close_location_centered": close_location_centered,
            "wick_balance_atr": zero_safe_sequence_ratio(
                (pd.concat([open_, close], axis=1).min(axis=1) - low)
                - (high - pd.concat([open_, close], axis=1).max(axis=1)),
                atr_20,
            ),
        }

    if feature_set == "sequence_manual":
        for lag in range(8):
            for sequence_name, values in sequence_values.items():
                add(f"sequence_{sequence_name}_lag_{lag}", values.shift(lag))

    if feature_set == "tcn_sequence":
        if tuple(sequence_values) != TCN_SEQUENCE_CHANNELS:
            raise AssertionError("TCN sequence channel order must remain fixed")
        tcn_features = {
            f"tcn_{sequence_name}_lag_{lag}": values.shift(lag)
            for lag in range(TCN_SEQUENCE_LENGTH)
            for sequence_name, values in sequence_values.items()
        }
        result = pd.concat(
            [result, pd.DataFrame(tcn_features, index=result.index)], axis=1
        )
        feature_columns.extend(tcn_features)

    if feature_set in (
        "intrabar_manual",
        "intrabar_structure",
        "intrabar_profile",
        "intrabar_full_path",
        "intrabar_path_signature",
        "intrabar_full_path_volatility_shape",
        "intrabar_pressure",
        "intrabar_volatility_shape",
        "intrabar_frequency_shape",
        "intrabar_ordinal_shape",
        "intrabar_signed_variation",
        "intrabar_distribution_shape",
        "intrabar_flow_shape",
        "intrabar_breakout_state",
    ):
        intrabar_columns = (
            "intrabar_return_std",
            "intrabar_up_fraction",
            "intrabar_body_directional_efficiency",
            "intrabar_body_concentration",
            "intrabar_early_body_return",
            "intrabar_late_body_return",
            "intrabar_late_minus_early",
        )
        missing_intrabar = sorted(set(intrabar_columns) - set(bars.columns))
        if missing_intrabar:
            raise ValueError(
                "bar frame is missing intrabar columns: " + ", ".join(missing_intrabar)
            )
        for column in intrabar_columns:
            add(column, bars[column].to_numpy(dtype="float64"))

    if feature_set in (
        "intrabar_structure",
        "intrabar_profile",
        "intrabar_full_path",
        "intrabar_path_signature",
        "intrabar_full_path_volatility_shape",
        "intrabar_pressure",
        "intrabar_volatility_shape",
        "intrabar_frequency_shape",
        "intrabar_ordinal_shape",
        "intrabar_signed_variation",
        "intrabar_distribution_shape",
        "intrabar_flow_shape",
        "intrabar_breakout_state",
    ):
        structure_columns = (
            "intrabar_high_position",
            "intrabar_low_position",
            "intrabar_high_minus_low_position",
            "intrabar_direction_change_fraction",
            "intrabar_close_path_efficiency",
            "intrabar_realized_variance_range",
            "intrabar_max_drawdown",
            "intrabar_max_runup",
        )
        missing_structure = sorted(set(structure_columns) - set(bars.columns))
        if missing_structure:
            raise ValueError(
                "bar frame is missing intrabar structure columns: "
                + ", ".join(missing_structure)
            )
        atr_ratio_20 = rolling_atr[20] / scale
        for column in structure_columns[:-2]:
            add(column, bars[column].to_numpy(dtype="float64"))
        add(
            "intrabar_max_drawdown_atr_20",
            bars["intrabar_max_drawdown"].to_numpy(dtype="float64")
            / atr_ratio_20.replace(0, np.nan),
        )
        add(
            "intrabar_max_runup_atr_20",
            bars["intrabar_max_runup"].to_numpy(dtype="float64")
            / atr_ratio_20.replace(0, np.nan),
        )

    if feature_set in (
        "intrabar_profile",
        "intrabar_full_path",
        "intrabar_path_signature",
        "intrabar_full_path_volatility_shape",
        "intrabar_pressure",
        "intrabar_volatility_shape",
        "intrabar_frequency_shape",
        "intrabar_ordinal_shape",
        "intrabar_signed_variation",
        "intrabar_distribution_shape",
        "intrabar_flow_shape",
        "intrabar_breakout_state",
    ):
        profile_columns = (
            "intrabar_profile_level_20",
            "intrabar_profile_level_40",
            "intrabar_profile_level_60",
            "intrabar_profile_level_80",
            "intrabar_profile_deviation_20",
            "intrabar_profile_deviation_40",
            "intrabar_profile_deviation_60",
            "intrabar_profile_deviation_80",
            "intrabar_profile_mean_deviation",
            "intrabar_profile_rms_deviation",
            "intrabar_profile_max_deviation",
            "intrabar_profile_min_deviation",
        )
        missing_profile = sorted(set(profile_columns) - set(bars.columns))
        if missing_profile:
            raise ValueError(
                "bar frame is missing intrabar profile columns: "
                + ", ".join(missing_profile)
            )
        for column in profile_columns:
            add(column, bars[column].to_numpy(dtype="float64"))

    if feature_set in (
        "intrabar_full_path",
        "intrabar_path_signature",
        "intrabar_full_path_volatility_shape",
    ):
        full_path_columns = tuple(
            f"intrabar_full_path_level_{grid_point:02d}"
            for grid_point in INTRABAR_FULL_PATH_GRID_POINTS
        )
        missing_full_path = sorted(set(full_path_columns) - set(bars.columns))
        if missing_full_path:
            raise ValueError(
                "bar frame is missing intrabar full-path columns: "
                + ", ".join(missing_full_path)
            )
        for column in full_path_columns:
            add(column, bars[column].to_numpy(dtype="float64"))

    if feature_set == "intrabar_path_signature":
        missing_path_signature = sorted(
            set(INTRABAR_PATH_SIGNATURE_COLUMNS) - set(bars.columns)
        )
        if missing_path_signature:
            raise ValueError(
                "bar frame is missing intrabar path-signature columns: "
                + ", ".join(missing_path_signature)
            )
        for column in INTRABAR_PATH_SIGNATURE_COLUMNS:
            add(column, bars[column].to_numpy(dtype="float64"))

    if feature_set in ("intrabar_pressure", "intrabar_flow_shape"):
        pressure_columns = (
            "intrabar_clv_mean",
            "intrabar_clv_std",
            "intrabar_early_clv_mean",
            "intrabar_late_clv_mean",
            "intrabar_clv_late_minus_early",
            "intrabar_range_weighted_clv",
            "intrabar_signed_range_pressure",
            "intrabar_wick_pressure",
            "intrabar_body_range_pressure",
            "intrabar_clv_body_divergence",
            "intrabar_clv_body_agreement",
        )
        missing_pressure = sorted(set(pressure_columns) - set(bars.columns))
        if missing_pressure:
            raise ValueError(
                "bar frame is missing intrabar pressure columns: "
                + ", ".join(missing_pressure)
            )
        for column in pressure_columns:
            add(column, bars[column].to_numpy(dtype="float64"))

    if feature_set == "intrabar_breakout_state":
        breakout_state_columns = (
            "intrabar_close_breakout_up_fraction",
            "intrabar_close_breakout_down_fraction",
            "intrabar_high_rejection_fraction",
            "intrabar_low_rejection_fraction",
            "intrabar_inside_bar_fraction",
            "intrabar_outside_bar_fraction",
            "intrabar_range_expansion_fraction",
            "intrabar_upward_range_expansion_fraction",
            "intrabar_downward_range_expansion_fraction",
            "intrabar_direction_continuation_fraction",
            "intrabar_direction_reversal_fraction",
            "intrabar_signed_run_length_imbalance",
        )
        missing_breakout_state = sorted(
            set(breakout_state_columns) - set(bars.columns)
        )
        if missing_breakout_state:
            raise ValueError(
                "bar frame is missing intrabar breakout state columns: "
                + ", ".join(missing_breakout_state)
            )
        for column in breakout_state_columns:
            add(column, bars[column].to_numpy(dtype="float64"))

    if feature_set in (
        "intrabar_volatility_shape",
        "intrabar_full_path_volatility_shape",
        "intrabar_frequency_shape",
        "intrabar_ordinal_shape",
        "intrabar_signed_variation",
        "intrabar_distribution_shape",
        "intrabar_flow_shape",
    ):
        volatility_shape_columns = (
            "intrabar_range_concentration",
            "intrabar_range_top3_fraction",
            "intrabar_range_dispersion",
            "intrabar_range_center_of_mass",
            "intrabar_early_range_fraction",
            "intrabar_late_range_fraction",
            "intrabar_range_late_minus_early",
            "intrabar_variance_concentration",
            "intrabar_variance_top3_fraction",
            "intrabar_variance_center_of_mass",
            "intrabar_early_variance_fraction",
            "intrabar_late_variance_fraction",
            "intrabar_variance_late_minus_early",
            "intrabar_range_variance_concentration_gap",
        )
        missing_volatility_shape = sorted(
            set(volatility_shape_columns) - set(bars.columns)
        )
        if missing_volatility_shape:
            raise ValueError(
                "bar frame is missing intrabar volatility shape columns: "
                + ", ".join(missing_volatility_shape)
            )
        for column in volatility_shape_columns:
            add(column, bars[column].to_numpy(dtype="float64"))

    if feature_set == "intrabar_frequency_shape":
        frequency_shape_columns = (
            "intrabar_return_dct_energy_fraction_1",
            "intrabar_return_dct_energy_fraction_2",
            "intrabar_return_dct_energy_fraction_3",
            "intrabar_return_dct_energy_fraction_4",
            "intrabar_return_low_frequency_fraction",
            "intrabar_return_mid_frequency_fraction",
            "intrabar_return_high_frequency_fraction",
            "intrabar_return_low_high_frequency_balance",
            "intrabar_return_autocorrelation_1",
            "intrabar_return_autocorrelation_2",
            "intrabar_return_autocorrelation_3",
            "intrabar_range_low_frequency_fraction",
        )
        missing_frequency_shape = sorted(
            set(frequency_shape_columns) - set(bars.columns)
        )
        if missing_frequency_shape:
            raise ValueError(
                "bar frame is missing intrabar frequency shape columns: "
                + ", ".join(missing_frequency_shape)
            )
        for column in frequency_shape_columns:
            add(column, bars[column].to_numpy(dtype="float64"))

    if feature_set == "intrabar_ordinal_shape":
        ordinal_shape_columns = (
            "intrabar_ordinal_pattern_012_fraction",
            "intrabar_ordinal_pattern_021_fraction",
            "intrabar_ordinal_pattern_102_fraction",
            "intrabar_ordinal_pattern_120_fraction",
            "intrabar_ordinal_pattern_201_fraction",
            "intrabar_ordinal_pattern_210_fraction",
            "intrabar_ordinal_pattern_entropy",
        )
        missing_ordinal_shape = sorted(
            set(ordinal_shape_columns) - set(bars.columns)
        )
        if missing_ordinal_shape:
            raise ValueError(
                "bar frame is missing intrabar ordinal shape columns: "
                + ", ".join(missing_ordinal_shape)
            )
        for column in ordinal_shape_columns:
            add(column, bars[column].to_numpy(dtype="float64"))

    if feature_set == "intrabar_signed_variation":
        signed_variation_columns = (
            "intrabar_upside_semivariance_fraction",
            "intrabar_downside_semivariance_fraction",
            "intrabar_semivariance_imbalance",
            "intrabar_semivariance_entropy",
            "intrabar_upside_variance_concentration",
            "intrabar_downside_variance_concentration",
            "intrabar_upside_variance_center_of_mass",
            "intrabar_downside_variance_center_of_mass",
            "intrabar_semivariance_timing_spread",
            "intrabar_bipower_variation_ratio",
            "intrabar_jump_variation_fraction",
            "intrabar_signed_largest_jump_fraction",
            "intrabar_continuous_semivariance_imbalance",
            "intrabar_semivariance_imbalance_late_minus_early",
        )
        missing_signed_variation = sorted(
            set(signed_variation_columns) - set(bars.columns)
        )
        if missing_signed_variation:
            raise ValueError(
                "bar frame is missing intrabar signed variation columns: "
                + ", ".join(missing_signed_variation)
            )
        for column in signed_variation_columns:
            add(column, bars[column].to_numpy(dtype="float64"))

    if feature_set == "intrabar_distribution_shape":
        distribution_shape_columns = (
            "intrabar_return_quantile_10_rms",
            "intrabar_return_quantile_25_rms",
            "intrabar_return_quantile_50_rms",
            "intrabar_return_quantile_75_rms",
            "intrabar_return_quantile_90_rms",
            "intrabar_return_bowley_skew",
            "intrabar_return_tail_skew",
            "intrabar_return_central_spread_fraction",
            "intrabar_return_mad_rms",
        )
        missing_distribution_shape = sorted(
            set(distribution_shape_columns) - set(bars.columns)
        )
        if missing_distribution_shape:
            raise ValueError(
                "bar frame is missing intrabar distribution shape columns: "
                + ", ".join(missing_distribution_shape)
            )
        for column in distribution_shape_columns:
            add(column, bars[column].to_numpy(dtype="float64"))

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
    next_range = frame["high"].shift(-1) - frame["low"].shift(-1)
    consecutive = next_start.eq(expected_next_start)
    flat = next_body.abs() <= flat_tolerance

    frame["target_timestamp"] = next_start + pd.Timedelta(minutes=timeframe_minutes)
    frame["next_bar_body"] = next_body
    frame["next_bar_body_atr"] = (
        next_body.abs()
        / (frame["close"].abs() * frame["atr_ratio_20"]).replace(0, np.nan)
    )
    frame["next_bar_directional_clarity"] = (
        next_body.abs() / next_range.replace(0, np.nan)
    ).clip(lower=0.0, upper=1.0)
    next_close_location = (
        (frame["close"].shift(-1) - frame["low"].shift(-1))
        / next_range.replace(0, np.nan)
    ).clip(lower=0.0, upper=1.0)
    direction_aligned_close_location = next_close_location.where(
        next_body > 0,
        1.0 - next_close_location,
    )
    frame["next_bar_directional_follow_through"] = (
        frame["next_bar_directional_clarity"] * direction_aligned_close_location
    ).clip(lower=0.0, upper=1.0)
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


def fit_isotonic_calibrator(
    y_true: np.ndarray, raw_probability_up: np.ndarray
) -> IsotonicCalibrator:
    labels = np.asarray(y_true, dtype="int8")
    if len(np.unique(labels)) != 2:
        raise ValueError("calibration partition must contain both up and down classes")
    probability = np.asarray(raw_probability_up, dtype="float64")
    model = IsotonicRegression(
        y_min=1e-6,
        y_max=1 - 1e-6,
        out_of_bounds="clip",
    )
    model.fit(probability, labels)
    return IsotonicCalibrator(
        x_thresholds=tuple(float(value) for value in model.X_thresholds_),
        y_thresholds=tuple(float(value) for value in model.y_thresholds_),
    )


def fit_beta_calibrator(
    y_true: np.ndarray, raw_probability_up: np.ndarray
) -> BetaCalibrator:
    labels = np.asarray(y_true, dtype="float64")
    if len(np.unique(labels)) != 2:
        raise ValueError("calibration partition must contain both up and down classes")
    probability = np.clip(
        np.asarray(raw_probability_up, dtype="float64"), 1e-6, 1 - 1e-6
    )
    log_probability = np.log(probability)
    negative_log_complement = -np.log1p(-probability)
    platt = fit_platt_calibrator(labels.astype("int8"), probability)
    initial = np.array(
        [max(platt.slope, 0.0), max(platt.slope, 0.0), platt.intercept],
        dtype="float64",
    )
    regularization = 1e-6

    def objective(parameters: np.ndarray) -> tuple[float, np.ndarray]:
        first, second, intercept = parameters
        linear = first * log_probability + second * negative_log_complement + intercept
        loss = np.mean(np.logaddexp(0.0, linear) - labels * linear)
        loss += regularization * (first * first + second * second)
        fitted = 1.0 / (1.0 + np.exp(-np.clip(linear, -40, 40)))
        error = fitted - labels
        gradient = np.array(
            [
                np.mean(error * log_probability) + 2 * regularization * first,
                np.mean(error * negative_log_complement)
                + 2 * regularization * second,
                np.mean(error),
            ],
            dtype="float64",
        )
        return float(loss), gradient

    fitted = minimize(
        objective,
        initial,
        method="L-BFGS-B",
        jac=True,
        bounds=((0.0, None), (0.0, None), (None, None)),
        options={"maxiter": 500, "ftol": 1e-12},
    )
    if not fitted.success or not np.isfinite(fitted.x).all():
        raise ValueError(f"beta calibration failed: {fitted.message}")
    return BetaCalibrator(
        log_probability_coefficient=float(fitted.x[0]),
        negative_log_complement_coefficient=float(fitted.x[1]),
        intercept=float(fitted.x[2]),
    )


def fit_temperature_calibrator(
    y_true: np.ndarray, raw_probability_up: np.ndarray
) -> TemperatureCalibrator:
    labels = np.asarray(y_true, dtype="float64")
    if len(np.unique(labels)) != 2:
        raise ValueError("calibration partition must contain both up and down classes")
    probability = np.clip(
        np.asarray(raw_probability_up, dtype="float64"), 1e-6, 1 - 1e-6
    )
    logits = np.log(probability / (1 - probability))

    def objective(log_temperature: np.ndarray) -> tuple[float, np.ndarray]:
        scaled_logits = logits * np.exp(-log_temperature[0])
        loss = np.mean(np.logaddexp(0.0, scaled_logits) - labels * scaled_logits)
        fitted_probability = 1.0 / (
            1.0 + np.exp(-np.clip(scaled_logits, -40, 40))
        )
        gradient = -np.mean((fitted_probability - labels) * scaled_logits)
        return float(loss), np.array([gradient], dtype="float64")

    fitted = minimize(
        objective,
        np.zeros(1, dtype="float64"),
        method="L-BFGS-B",
        jac=True,
        bounds=((np.log(0.05), np.log(20.0)),),
        options={"maxiter": 200, "ftol": 1e-12},
    )
    if not fitted.success or not np.isfinite(fitted.x).all():
        raise ValueError(f"temperature calibration failed: {fitted.message}")
    return TemperatureCalibrator(temperature=float(np.exp(fitted.x[0])))


def fit_probability_calibrator(
    y_true: np.ndarray,
    raw_probability_up: np.ndarray,
    method: str,
) -> PlattCalibrator | IsotonicCalibrator | BetaCalibrator | TemperatureCalibrator:
    if method == "platt":
        return fit_platt_calibrator(y_true, raw_probability_up)
    if method == "isotonic":
        return fit_isotonic_calibrator(y_true, raw_probability_up)
    if method == "beta":
        return fit_beta_calibrator(y_true, raw_probability_up)
    if method == "temperature":
        return fit_temperature_calibrator(y_true, raw_probability_up)
    raise ValueError(f"unknown probability_calibration: {method}")


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


def training_sample_weights(
    train: pd.DataFrame,
    mode: str,
) -> np.ndarray | None:
    if mode == "uniform":
        return None
    if mode not in {
        "body_atr",
        "directional_clarity",
        "directional_follow_through",
        "recency_half_life_730d",
    }:
        raise ValueError(f"unknown train_weighting: {mode}")
    if mode == "recency_half_life_730d":
        column = "decision_timestamp"
        if column not in train:
            raise ValueError(f"training data is missing {column}")
        timestamps = pd.to_datetime(train[column], utc=True, errors="coerce")
        if timestamps.isna().any():
            raise ValueError("decision_timestamp must be finite for recency weighting")
        age_days = (
            (timestamps.max() - timestamps) / pd.Timedelta(days=1)
        ).to_numpy(dtype="float64")
        if not np.isfinite(age_days).all() or np.any(age_days < 0):
            raise ValueError("training age must be finite and non-negative")
        raw_weight = np.exp2(-age_days / RECENCY_WEIGHT_HALF_LIFE_DAYS)
        return raw_weight / raw_weight.mean()
    if mode in {"directional_clarity", "directional_follow_through"}:
        column = (
            "next_bar_directional_clarity"
            if mode == "directional_clarity"
            else "next_bar_directional_follow_through"
        )
        if column not in train:
            raise ValueError(f"training data is missing {column}")
        quality = train[column].to_numpy(dtype="float64")
        if not np.isfinite(quality).all() or np.any((quality < 0) | (quality > 1)):
            raise ValueError(f"{column} must be finite and within [0, 1]")
        raw_weight = 0.5 + quality
        return raw_weight / raw_weight.mean()
    if "next_bar_body_atr" not in train:
        raise ValueError("training data is missing next_bar_body_atr")
    strength = train["next_bar_body_atr"].to_numpy(dtype="float64")
    if not np.isfinite(strength).all():
        raise ValueError("next_bar_body_atr must be finite for weighted training")
    raw_weight = 0.5 + np.clip(strength, 0.0, 1.5)
    return raw_weight / raw_weight.mean()


def model_training_target(train: pd.DataFrame, model_type: str) -> np.ndarray:
    direction = train["target_up"].to_numpy(dtype="int8")
    if model_type not in {
        "body_atr_soft_hgb",
        "body_multiclass_hgb",
        "signed_body_hgb",
        "signed_clarity_hgb",
        "signed_body_quantile_hgb",
    }:
        return direction
    sign = np.where(direction == 1, 1.0, -1.0)
    if model_type == "signed_clarity_hgb":
        column = "next_bar_directional_clarity"
        if column not in train:
            raise ValueError(f"signed clarity target model requires {column}")
        clarity = train[column].to_numpy(dtype="float64")
        if not np.isfinite(clarity).all() or np.any((clarity < 0) | (clarity > 1)):
            raise ValueError(
                "next_bar_directional_clarity must be finite and within [0, 1]"
            )
        return sign * clarity
    if "next_bar_body_atr" not in train:
        raise ValueError("body/ATR target model requires next_bar_body_atr")
    magnitude = train["next_bar_body_atr"].to_numpy(dtype="float64")
    if not np.isfinite(magnitude).all() or np.any(magnitude < 0):
        raise ValueError("next_bar_body_atr must be finite and non-negative")
    if model_type == "body_atr_soft_hgb":
        return 0.5 + sign * 0.5 * np.tanh(magnitude)
    if model_type == "body_multiclass_hgb":
        large = magnitude >= np.median(magnitude)
        output = np.empty(len(direction), dtype="int8")
        output[(direction == 0) & large] = 0
        output[(direction == 0) & ~large] = 1
        output[(direction == 1) & ~large] = 2
        output[(direction == 1) & large] = 3
        return output
    return sign * np.arcsinh(magnitude)


def filter_training_targets(
    train: pd.DataFrame, mode: str
) -> tuple[pd.DataFrame, dict[str, object]]:
    if mode == "all":
        return train, {
            "mode": mode,
            "input_rows": len(train),
            "output_rows": len(train),
            "body_atr_threshold": None,
            "directional_clarity_threshold": None,
        }
    if mode not in {"body_atr_upper_half", "body_range_upper_half"}:
        raise ValueError(f"unknown train_target_filter: {mode}")
    column = (
        "next_bar_body_atr"
        if mode == "body_atr_upper_half"
        else "next_bar_directional_clarity"
    )
    if column not in train:
        raise ValueError(f"target filtering requires {column}")
    quality = train[column].to_numpy(dtype="float64")
    if not np.isfinite(quality).all():
        raise ValueError(f"{column} must be finite for target filtering")
    if column == "next_bar_directional_clarity" and (
        (quality < 0).any() or (quality > 1).any()
    ):
        raise ValueError("next_bar_directional_clarity must be between zero and one")
    threshold = float(np.median(quality))
    filtered = train.loc[train[column].ge(threshold)].copy()
    if filtered.empty or filtered["target_up"].nunique() != 2:
        raise ValueError("target filtering must retain both direction classes")
    return filtered, {
        "mode": mode,
        "input_rows": len(train),
        "output_rows": len(filtered),
        "body_atr_threshold": (
            threshold if mode == "body_atr_upper_half" else None
        ),
        "directional_clarity_threshold": (
            threshold if mode == "body_range_upper_half" else None
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
    if config.probability_calibration not in PROBABILITY_CALIBRATIONS:
        raise ValueError(
            f"unknown probability_calibration: {config.probability_calibration}"
        )
    if config.model_type not in MODEL_TYPES:
        raise ValueError(f"unknown model_type: {config.model_type}")
    sequence_model_types = {"tcn", "causal_gru", "causal_transformer"}
    if config.model_type in sequence_model_types and config.feature_set != "tcn_sequence":
        raise ValueError(
            f"{config.model_type} model_type requires feature_set=tcn_sequence"
        )
    if (
        config.model_type == "transition_bayes"
        and config.feature_set != "direction_transition_state"
    ):
        raise ValueError(
            "transition_bayes model_type requires "
            "feature_set=direction_transition_state"
        )
    if config.train_weighting not in TRAIN_WEIGHTING_MODES:
        raise ValueError(f"unknown train_weighting: {config.train_weighting}")
    if config.train_target_filter not in TRAIN_TARGET_FILTERS:
        raise ValueError(f"unknown train_target_filter: {config.train_target_filter}")
    if config.train_weighting != "uniform" and config.model_type not in {
        "hgb",
        "regime_hgb",
    }:
        raise ValueError(
            "non-uniform train weighting is currently supported only for hgb models"
        )
    splits = chronological_split(dataset, train_end, calibration_end, test_end)
    if config.train_window_days < 0:
        raise ValueError("train_window_days must not be negative")
    if config.train_window_days > 0:
        window_start = train_end - pd.Timedelta(days=config.train_window_days)
        splits["train"] = splits["train"].loc[
            pd.to_datetime(splits["train"]["decision_timestamp"], utc=True)
            >= window_start
        ].copy()
        if splits["train"].empty:
            raise ValueError("training window produced an empty training partition")
    filtered_train, target_filter_diagnostics = filter_training_targets(
        splits["train"], config.train_target_filter
    )
    train = _even_sample(filtered_train, config.max_train_rows)
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
    elif config.model_type == "logistic":
        if config.logistic_c <= 0:
            raise ValueError("logistic_c must be positive")
        model = make_pipeline(
            StandardScaler(),
            LogisticRegression(
                C=config.logistic_c,
                solver="lbfgs",
                max_iter=max(config.max_iter, 500),
                random_state=config.random_seed,
            ),
        )
    elif config.model_type == "extra_trees":
        if config.extra_trees_estimators <= 0:
            raise ValueError("extra_trees_estimators must be positive")
        if config.extra_trees_max_depth <= 0:
            raise ValueError("extra_trees_max_depth must be positive")
        if config.extra_trees_min_samples_leaf <= 0:
            raise ValueError("extra_trees_min_samples_leaf must be positive")
        if not 0 < config.extra_trees_max_features <= 1:
            raise ValueError("extra_trees_max_features must be in (0, 1]")
        model = ExtraTreesClassifier(
            n_estimators=config.extra_trees_estimators,
            max_depth=config.extra_trees_max_depth,
            min_samples_leaf=config.extra_trees_min_samples_leaf,
            max_features=config.extra_trees_max_features,
            n_jobs=-1,
            random_state=config.random_seed,
        )
    elif config.model_type == "xgboost":
        # XGBoost and PyTorch ship separate OpenMP runtimes on Intel macOS.
        # Keep both optional backends lazy so a single-model CLI process loads
        # only the runtime it actually needs.
        from xgboost import XGBClassifier

        if config.xgboost_estimators <= 0:
            raise ValueError("xgboost_estimators must be positive")
        if config.xgboost_max_depth <= 0:
            raise ValueError("xgboost_max_depth must be positive")
        if config.xgboost_learning_rate <= 0:
            raise ValueError("xgboost_learning_rate must be positive")
        if config.xgboost_min_child_weight <= 0:
            raise ValueError("xgboost_min_child_weight must be positive")
        if not 0 < config.xgboost_subsample <= 1:
            raise ValueError("xgboost_subsample must be in (0, 1]")
        if not 0 < config.xgboost_column_sample <= 1:
            raise ValueError("xgboost_column_sample must be in (0, 1]")
        if config.xgboost_l2 < 0:
            raise ValueError("xgboost_l2 must not be negative")
        model = XGBClassifier(
            n_estimators=config.xgboost_estimators,
            max_depth=config.xgboost_max_depth,
            learning_rate=config.xgboost_learning_rate,
            min_child_weight=config.xgboost_min_child_weight,
            subsample=config.xgboost_subsample,
            colsample_bytree=config.xgboost_column_sample,
            reg_lambda=config.xgboost_l2,
            objective="binary:logistic",
            eval_metric="logloss",
            tree_method="hist",
            n_jobs=-1,
            random_state=config.random_seed,
            verbosity=0,
        )
    elif config.model_type == "catboost":
        from catboost import CatBoostClassifier

        if config.catboost_iterations <= 0:
            raise ValueError("catboost_iterations must be positive")
        if config.catboost_depth <= 0:
            raise ValueError("catboost_depth must be positive")
        if config.catboost_learning_rate <= 0:
            raise ValueError("catboost_learning_rate must be positive")
        if config.catboost_l2 < 0:
            raise ValueError("catboost_l2 must not be negative")
        if config.catboost_random_strength < 0:
            raise ValueError("catboost_random_strength must not be negative")
        if config.catboost_bagging_temperature < 0:
            raise ValueError("catboost_bagging_temperature must not be negative")
        model = CatBoostClassifier(
            iterations=config.catboost_iterations,
            depth=config.catboost_depth,
            learning_rate=config.catboost_learning_rate,
            l2_leaf_reg=config.catboost_l2,
            random_strength=config.catboost_random_strength,
            bootstrap_type="Bayesian",
            bagging_temperature=config.catboost_bagging_temperature,
            boosting_type="Ordered",
            loss_function="Logloss",
            eval_metric="Logloss",
            random_seed=config.random_seed,
            thread_count=-1,
            verbose=False,
            allow_writing_files=False,
        )
    elif config.model_type == "lightgbm":
        from lightgbm import LGBMClassifier

        if config.lightgbm_estimators <= 0:
            raise ValueError("lightgbm_estimators must be positive")
        if config.lightgbm_num_leaves <= 1:
            raise ValueError("lightgbm_num_leaves must be greater than one")
        if config.lightgbm_learning_rate <= 0:
            raise ValueError("lightgbm_learning_rate must be positive")
        if config.lightgbm_min_child_samples <= 0:
            raise ValueError("lightgbm_min_child_samples must be positive")
        if not 0 < config.lightgbm_subsample <= 1:
            raise ValueError("lightgbm_subsample must be in (0, 1]")
        if not 0 < config.lightgbm_column_sample <= 1:
            raise ValueError("lightgbm_column_sample must be in (0, 1]")
        if config.lightgbm_l2 < 0:
            raise ValueError("lightgbm_l2 must not be negative")
        model = LGBMClassifier(
            boosting_type="gbdt",
            objective="binary",
            n_estimators=config.lightgbm_estimators,
            num_leaves=config.lightgbm_num_leaves,
            learning_rate=config.lightgbm_learning_rate,
            min_child_samples=config.lightgbm_min_child_samples,
            subsample=config.lightgbm_subsample,
            subsample_freq=1,
            colsample_bytree=config.lightgbm_column_sample,
            reg_lambda=config.lightgbm_l2,
            random_state=config.random_seed,
            n_jobs=-1,
            deterministic=True,
            force_col_wise=True,
            verbosity=-1,
        )
    elif config.model_type == "regime_hgb":
        model = VolatilityRegimeHGBClassifier(
            max_iter=config.max_iter,
            learning_rate=config.learning_rate,
            max_leaf_nodes=config.max_leaf_nodes,
            min_samples_leaf=config.min_samples_leaf,
            l2_regularization=config.l2_regularization,
            random_state=config.random_seed,
        )
    elif config.model_type == "body_atr_soft_hgb":
        model = BodyATRSoftHGBClassifier(
            max_iter=config.max_iter,
            learning_rate=config.learning_rate,
            max_leaf_nodes=config.max_leaf_nodes,
            min_samples_leaf=config.min_samples_leaf,
            l2_regularization=config.l2_regularization,
            random_state=config.random_seed,
        )
    elif config.model_type == "body_multiclass_hgb":
        model = BodyMulticlassHGBClassifier(
            max_iter=config.max_iter,
            learning_rate=config.learning_rate,
            max_leaf_nodes=config.max_leaf_nodes,
            min_samples_leaf=config.min_samples_leaf,
            l2_regularization=config.l2_regularization,
            random_state=config.random_seed,
        )
    elif config.model_type == "signed_body_hgb":
        model = SignedBodyHGBClassifier(
            max_iter=config.max_iter,
            learning_rate=config.learning_rate,
            max_leaf_nodes=config.max_leaf_nodes,
            min_samples_leaf=config.min_samples_leaf,
            l2_regularization=config.l2_regularization,
            random_state=config.random_seed,
        )
    elif config.model_type == "signed_clarity_hgb":
        model = SignedBodyHGBClassifier(
            max_iter=config.max_iter,
            learning_rate=config.learning_rate,
            max_leaf_nodes=config.max_leaf_nodes,
            min_samples_leaf=config.min_samples_leaf,
            l2_regularization=config.l2_regularization,
            random_state=config.random_seed,
            target_transform=(
                "sign(next_bar_body) * abs(next_bar_body) / next_bar_range"
            ),
        )
    elif config.model_type == "signed_body_quantile_hgb":
        model = SignedBodyQuantileHGBClassifier(
            max_iter=config.max_iter,
            learning_rate=config.learning_rate,
            max_leaf_nodes=config.max_leaf_nodes,
            min_samples_leaf=config.min_samples_leaf,
            l2_regularization=config.l2_regularization,
            random_state=config.random_seed,
        )
    elif config.model_type == "transition_bayes":
        from trade_data.next_bar_transition import (
            HierarchicalDirectionTransitionClassifier,
        )

        model = HierarchicalDirectionTransitionClassifier(
            state_prior_strength=config.transition_state_prior_strength,
            parent_prior_strength=config.transition_parent_prior_strength,
        )
    elif config.model_type == "tcn":
        from trade_data.next_bar_tcn import CausalTCNClassifier

        model = CausalTCNClassifier(
            sequence_length=TCN_SEQUENCE_LENGTH,
            hidden_channels=config.tcn_hidden_channels,
            epochs=config.tcn_epochs,
            batch_size=config.tcn_batch_size,
            learning_rate=config.tcn_learning_rate,
            weight_decay=config.tcn_weight_decay,
            random_state=config.random_seed,
        )
    elif config.model_type == "causal_gru":
        from trade_data.next_bar_tcn import CausalGRUClassifier

        model = CausalGRUClassifier(
            sequence_length=TCN_SEQUENCE_LENGTH,
            hidden_channels=config.tcn_hidden_channels,
            epochs=config.tcn_epochs,
            batch_size=config.tcn_batch_size,
            learning_rate=config.tcn_learning_rate,
            weight_decay=config.tcn_weight_decay,
            random_state=config.random_seed,
        )
    elif config.model_type == "causal_transformer":
        from trade_data.next_bar_tcn import CausalTransformerClassifier

        model = CausalTransformerClassifier(
            sequence_length=TCN_SEQUENCE_LENGTH,
            model_dimension=config.transformer_model_dimension,
            attention_heads=config.transformer_attention_heads,
            encoder_layers=config.transformer_encoder_layers,
            feedforward_dimension=config.transformer_feedforward_dimension,
            epochs=config.transformer_epochs,
            batch_size=config.transformer_batch_size,
            learning_rate=config.transformer_learning_rate,
            weight_decay=config.transformer_weight_decay,
            random_state=config.random_seed,
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
    sample_weight = training_sample_weights(train, config.train_weighting)
    training_target = model_training_target(train, config.model_type)
    if sample_weight is None:
        model.fit(train[feature_columns], training_target)
    else:
        model.fit(
            train[feature_columns],
            training_target,
            sample_weight=sample_weight,
        )
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
    calibrator = fit_probability_calibrator(
        class_calibration["target_up"].to_numpy(),
        class_calibration_probability,
        config.probability_calibration,
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
        "train_window_days": config.train_window_days,
        "train_weighting": config.train_weighting,
        "train_target_filter": target_filter_diagnostics,
        "train_sample_weight": (
            {
                "minimum": float(sample_weight.min()),
                "mean": float(sample_weight.mean()),
                "maximum": float(sample_weight.max()),
            }
            if sample_weight is not None
            else None
        ),
        "model_diagnostics": (
            model.diagnostics() if callable(getattr(model, "diagnostics", None)) else None
        ),
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
        "probability_calibration": config.probability_calibration,
        "probability_calibrator": {
            "method": config.probability_calibration,
            **asdict(calibrator),
        },
        "platt_calibrator": (
            asdict(calibrator) if isinstance(calibrator, PlattCalibrator) else None
        ),
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
        "probability_calibration": config.probability_calibration,
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
        "probability_calibration": config.probability_calibration,
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
    predictions_dir: Path | Sequence[Path],
    output: Path,
    config: OddsCalibrationConfig | None = None,
) -> dict[str, object]:
    """Fit deployable odds tables and validate calibration on later OOS folds."""
    odds_config = config or OddsCalibrationConfig()
    prediction_dirs = (
        (predictions_dir,)
        if isinstance(predictions_dir, Path)
        else tuple(Path(directory) for directory in predictions_dir)
    )
    if not prediction_dirs:
        raise ValueError("at least one predictions directory is required")
    manifests = [
        json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
        for directory in prediction_dirs
    ]
    timeframe_names = list(
        dict.fromkeys(
            timeframe
            for manifest in manifests
            for timeframe in manifest["timeframes"]
        )
    )
    payload: dict[str, object] = {
        "_meta": {
            "format_version": 1,
            "created_at": datetime.now(UTC).isoformat(),
            "source": (
                str(prediction_dirs[0])
                if len(prediction_dirs) == 1
                else [str(directory) for directory in prediction_dirs]
            ),
            "config": asdict(odds_config),
            "validation": "nested chronological: prior OOS folds calibrate, next fold evaluates",
            "confidence_definition": "estimated probability that predicted direction is correct",
        }
    }
    for timeframe in timeframe_names:
        frames = []
        for directory, manifest in zip(prediction_dirs, manifests):
            entry = manifest["timeframes"].get(timeframe)
            if entry is None:
                continue
            prediction_name = entry.get("predictions")
            if prediction_name is None:
                raise ValueError(
                    f"walk-forward manifest has no predictions for {timeframe}"
                )
            frames.append(pd.read_parquet(directory / prediction_name))
        frame = _prepare_policy_frame(pd.concat(frames, ignore_index=True))
        if "fold" not in frame:
            raise ValueError(f"walk-forward predictions have no fold column for {timeframe}")
        duplicate_keys = ["fold", "timestamp"]
        if frame.duplicated(duplicate_keys).any():
            raise ValueError(
                f"walk-forward prediction directories overlap for {timeframe}"
            )
        frame = frame.sort_values(["decision_timestamp", "fold"]).reset_index(
            drop=True
        )
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
    train.add_argument(
        "--probability-calibration",
        choices=PROBABILITY_CALIBRATIONS,
        default="platt",
    )
    train.add_argument(
        "--train-weighting", choices=TRAIN_WEIGHTING_MODES, default="uniform"
    )
    train.add_argument(
        "--train-target-filter", choices=TRAIN_TARGET_FILTERS, default="all"
    )
    train.add_argument("--model-type", choices=MODEL_TYPES, default="hgb")
    train.add_argument("--mlp-learning-rate", type=float, default=0.001)
    train.add_argument("--mlp-alpha", type=float, default=0.001)
    train.add_argument("--mlp-batch-size", type=int, default=1024)
    train.add_argument("--logistic-c", type=float, default=0.10)
    train.add_argument(
        "--train-window-days",
        type=int,
        default=0,
        help="Use only this many days before train_end; zero keeps the full expanding history.",
    )
    train.add_argument("--extra-trees-estimators", type=int, default=200)
    train.add_argument("--extra-trees-max-depth", type=int, default=12)
    train.add_argument("--extra-trees-min-samples-leaf", type=int, default=50)
    train.add_argument("--extra-trees-max-features", type=float, default=0.75)
    train.add_argument("--xgboost-estimators", type=int, default=300)
    train.add_argument("--xgboost-max-depth", type=int, default=4)
    train.add_argument("--xgboost-learning-rate", type=float, default=0.03)
    train.add_argument("--xgboost-min-child-weight", type=float, default=20.0)
    train.add_argument("--xgboost-subsample", type=float, default=0.80)
    train.add_argument("--xgboost-column-sample", type=float, default=0.80)
    train.add_argument("--xgboost-l2", type=float, default=5.0)
    train.add_argument("--catboost-iterations", type=int, default=300)
    train.add_argument("--catboost-depth", type=int, default=6)
    train.add_argument("--catboost-learning-rate", type=float, default=0.03)
    train.add_argument("--catboost-l2", type=float, default=5.0)
    train.add_argument("--catboost-random-strength", type=float, default=1.0)
    train.add_argument("--catboost-bagging-temperature", type=float, default=1.0)
    train.add_argument("--lightgbm-estimators", type=int, default=300)
    train.add_argument("--lightgbm-num-leaves", type=int, default=31)
    train.add_argument("--lightgbm-learning-rate", type=float, default=0.03)
    train.add_argument("--lightgbm-min-child-samples", type=int, default=100)
    train.add_argument("--lightgbm-subsample", type=float, default=0.80)
    train.add_argument("--lightgbm-column-sample", type=float, default=0.80)
    train.add_argument("--lightgbm-l2", type=float, default=5.0)
    train.add_argument("--transition-state-prior-strength", type=float, default=64.0)
    train.add_argument("--transition-parent-prior-strength", type=float, default=256.0)
    train.add_argument("--tcn-epochs", type=int, default=8)
    train.add_argument("--tcn-batch-size", type=int, default=2048)
    train.add_argument("--tcn-learning-rate", type=float, default=0.001)
    train.add_argument("--tcn-hidden-channels", type=int, default=16)
    train.add_argument("--tcn-weight-decay", type=float, default=0.0001)
    train.add_argument("--transformer-epochs", type=int, default=8)
    train.add_argument("--transformer-batch-size", type=int, default=2048)
    train.add_argument("--transformer-learning-rate", type=float, default=0.0005)
    train.add_argument("--transformer-model-dimension", type=int, default=16)
    train.add_argument("--transformer-attention-heads", type=int, default=4)
    train.add_argument("--transformer-encoder-layers", type=int, default=1)
    train.add_argument(
        "--transformer-feedforward-dimension", type=int, default=32
    )
    train.add_argument("--transformer-weight-decay", type=float, default=0.0001)

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
    walk_forward.add_argument(
        "--probability-calibration",
        choices=PROBABILITY_CALIBRATIONS,
        default="platt",
    )
    walk_forward.add_argument(
        "--train-weighting", choices=TRAIN_WEIGHTING_MODES, default="uniform"
    )
    walk_forward.add_argument(
        "--train-target-filter", choices=TRAIN_TARGET_FILTERS, default="all"
    )
    walk_forward.add_argument("--model-type", choices=MODEL_TYPES, default="hgb")
    walk_forward.add_argument("--mlp-learning-rate", type=float, default=0.001)
    walk_forward.add_argument("--mlp-alpha", type=float, default=0.001)
    walk_forward.add_argument("--mlp-batch-size", type=int, default=1024)
    walk_forward.add_argument("--logistic-c", type=float, default=0.10)
    walk_forward.add_argument(
        "--train-window-days",
        type=int,
        default=0,
        help="Use only this many days before each train_end; zero keeps expanding history.",
    )
    walk_forward.add_argument("--extra-trees-estimators", type=int, default=200)
    walk_forward.add_argument("--extra-trees-max-depth", type=int, default=12)
    walk_forward.add_argument("--extra-trees-min-samples-leaf", type=int, default=50)
    walk_forward.add_argument("--extra-trees-max-features", type=float, default=0.75)
    walk_forward.add_argument("--xgboost-estimators", type=int, default=300)
    walk_forward.add_argument("--xgboost-max-depth", type=int, default=4)
    walk_forward.add_argument("--xgboost-learning-rate", type=float, default=0.03)
    walk_forward.add_argument("--xgboost-min-child-weight", type=float, default=20.0)
    walk_forward.add_argument("--xgboost-subsample", type=float, default=0.80)
    walk_forward.add_argument("--xgboost-column-sample", type=float, default=0.80)
    walk_forward.add_argument("--xgboost-l2", type=float, default=5.0)
    walk_forward.add_argument("--catboost-iterations", type=int, default=300)
    walk_forward.add_argument("--catboost-depth", type=int, default=6)
    walk_forward.add_argument("--catboost-learning-rate", type=float, default=0.03)
    walk_forward.add_argument("--catboost-l2", type=float, default=5.0)
    walk_forward.add_argument("--catboost-random-strength", type=float, default=1.0)
    walk_forward.add_argument(
        "--catboost-bagging-temperature", type=float, default=1.0
    )
    walk_forward.add_argument("--lightgbm-estimators", type=int, default=300)
    walk_forward.add_argument("--lightgbm-num-leaves", type=int, default=31)
    walk_forward.add_argument("--lightgbm-learning-rate", type=float, default=0.03)
    walk_forward.add_argument("--lightgbm-min-child-samples", type=int, default=100)
    walk_forward.add_argument("--lightgbm-subsample", type=float, default=0.80)
    walk_forward.add_argument("--lightgbm-column-sample", type=float, default=0.80)
    walk_forward.add_argument("--lightgbm-l2", type=float, default=5.0)
    walk_forward.add_argument(
        "--transition-state-prior-strength", type=float, default=64.0
    )
    walk_forward.add_argument(
        "--transition-parent-prior-strength", type=float, default=256.0
    )
    walk_forward.add_argument("--tcn-epochs", type=int, default=8)
    walk_forward.add_argument("--tcn-batch-size", type=int, default=2048)
    walk_forward.add_argument("--tcn-learning-rate", type=float, default=0.001)
    walk_forward.add_argument("--tcn-hidden-channels", type=int, default=16)
    walk_forward.add_argument("--tcn-weight-decay", type=float, default=0.0001)
    walk_forward.add_argument("--transformer-epochs", type=int, default=8)
    walk_forward.add_argument("--transformer-batch-size", type=int, default=2048)
    walk_forward.add_argument(
        "--transformer-learning-rate", type=float, default=0.0005
    )
    walk_forward.add_argument("--transformer-model-dimension", type=int, default=16)
    walk_forward.add_argument("--transformer-attention-heads", type=int, default=4)
    walk_forward.add_argument("--transformer-encoder-layers", type=int, default=1)
    walk_forward.add_argument(
        "--transformer-feedforward-dimension", type=int, default=32
    )
    walk_forward.add_argument("--transformer-weight-decay", type=float, default=0.0001)

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
    odds.add_argument(
        "--predictions-dir",
        type=Path,
        action="append",
        required=True,
        help="repeat to combine non-overlapping chronological OOS prediction sets",
    )
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
        probability_calibration=args.probability_calibration,
        train_weighting=args.train_weighting,
        train_target_filter=args.train_target_filter,
        model_type=args.model_type,
        mlp_learning_rate=args.mlp_learning_rate,
        mlp_alpha=args.mlp_alpha,
        mlp_batch_size=args.mlp_batch_size,
        logistic_c=args.logistic_c,
        train_window_days=args.train_window_days,
        extra_trees_estimators=args.extra_trees_estimators,
        extra_trees_max_depth=args.extra_trees_max_depth,
        extra_trees_min_samples_leaf=args.extra_trees_min_samples_leaf,
        extra_trees_max_features=args.extra_trees_max_features,
        xgboost_estimators=args.xgboost_estimators,
        xgboost_max_depth=args.xgboost_max_depth,
        xgboost_learning_rate=args.xgboost_learning_rate,
        xgboost_min_child_weight=args.xgboost_min_child_weight,
        xgboost_subsample=args.xgboost_subsample,
        xgboost_column_sample=args.xgboost_column_sample,
        xgboost_l2=args.xgboost_l2,
        catboost_iterations=args.catboost_iterations,
        catboost_depth=args.catboost_depth,
        catboost_learning_rate=args.catboost_learning_rate,
        catboost_l2=args.catboost_l2,
        catboost_random_strength=args.catboost_random_strength,
        catboost_bagging_temperature=args.catboost_bagging_temperature,
        lightgbm_estimators=args.lightgbm_estimators,
        lightgbm_num_leaves=args.lightgbm_num_leaves,
        lightgbm_learning_rate=args.lightgbm_learning_rate,
        lightgbm_min_child_samples=args.lightgbm_min_child_samples,
        lightgbm_subsample=args.lightgbm_subsample,
        lightgbm_column_sample=args.lightgbm_column_sample,
        lightgbm_l2=args.lightgbm_l2,
        transition_state_prior_strength=args.transition_state_prior_strength,
        transition_parent_prior_strength=args.transition_parent_prior_strength,
        tcn_epochs=args.tcn_epochs,
        tcn_batch_size=args.tcn_batch_size,
        tcn_learning_rate=args.tcn_learning_rate,
        tcn_hidden_channels=args.tcn_hidden_channels,
        tcn_weight_decay=args.tcn_weight_decay,
        transformer_epochs=args.transformer_epochs,
        transformer_batch_size=args.transformer_batch_size,
        transformer_learning_rate=args.transformer_learning_rate,
        transformer_model_dimension=args.transformer_model_dimension,
        transformer_attention_heads=args.transformer_attention_heads,
        transformer_encoder_layers=args.transformer_encoder_layers,
        transformer_feedforward_dimension=args.transformer_feedforward_dimension,
        transformer_weight_decay=args.transformer_weight_decay,
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
    # Running this file with ``python -m trade_data.next_bar`` otherwise defines
    # calibrator classes under ``__main__`` and produces non-portable joblib
    # artifacts. Re-enter through the canonical module name before training.
    from trade_data.next_bar import main as canonical_main

    raise SystemExit(canonical_main())
