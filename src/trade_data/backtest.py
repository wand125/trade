from __future__ import annotations

import argparse
import json
import random
import sys
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from itertools import product
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

from trade_data.regime import REGIME_COLUMNS


DIRECTION_LABELS = {
    1: "long",
    -1: "short",
}

DEFAULT_FIXED_HORIZON_MINUTES = (60.0, 240.0, 720.0)
DEFAULT_LONG_FIXED_HORIZON_COLUMNS = tuple(
    f"pred_long_fixed_{int(minutes)}m_adjusted_pnl" for minutes in DEFAULT_FIXED_HORIZON_MINUTES
)
DEFAULT_SHORT_FIXED_HORIZON_COLUMNS = tuple(
    f"pred_short_fixed_{int(minutes)}m_adjusted_pnl" for minutes in DEFAULT_FIXED_HORIZON_MINUTES
)
FIXED_HORIZON_SCORE_MODES = ("max", "mean", "median", "min")
CANDIDATE_RANK_MODES = ("pnl", "near_top_risk", "stress_score")
DEFAULT_MLP_MIN_VALID_HOLD_MINUTES = 30.0

TRADE_COLUMNS = [
    "direction",
    "entry_timestamp",
    "exit_timestamp",
    "entry_price",
    "exit_price",
    "raw_pnl",
    "adjusted_pnl",
    "holding_minutes",
    "exit_reason",
    "entry_decision_timestamp",
    "exit_decision_timestamp",
]

SWEEP_KEY_COLUMNS = [
    "policy",
    "entry_threshold",
    "long_entry_threshold_offset",
    "short_entry_threshold_offset",
    "exit_threshold",
    "side_margin",
    "risk_penalty",
    "fixed_horizon_score_mode",
    "min_predicted_hold_minutes",
    "max_predicted_hold_minutes",
    "min_valid_predicted_hold_minutes",
    "long_holding_fallback_column",
    "short_holding_fallback_column",
    "max_wait_regret",
    "min_entry_rank",
    "min_trade_quality",
    "profit_barrier_miss_penalty",
    "time_exit_penalty",
    "loss_first_penalty",
    "time_exit_holding_shrink",
    "loss_first_holding_shrink",
    "holding_shortening_threshold",
    "holding_shortening_cap_minutes",
    "time_exit_exit_threshold",
    "loss_first_exit_threshold",
    "side_confidence_penalty",
    "side_confidence_penalty_rules",
    "side_confidence_overfit_penalty_rules",
    "min_side_confidence",
    "require_profit_barrier",
    "profit_barrier_threshold",
    "secondary_score_tie_margin",
    "long_secondary_score_column",
    "short_secondary_score_column",
    "side_ev_penalty_rules",
    "side_ev_penalty_replacement_min_margin",
    "extra_side_margin_rules",
    "side_extra_margin_rules",
    "side_block_rules",
    "context_drawdown_guard_loss_threshold",
    "context_drawdown_guard_min_entry_margin",
    "context_drawdown_guard_context_columns",
    "context_drawdown_guard_reset_monthly",
    "block_trend_regimes",
    "block_volatility_regimes",
    "block_session_regimes",
    "block_gap_regimes",
    "block_combined_regimes",
]

REGIME_BLOCK_FIELDS = [
    ("block_trend_regimes", "trend_regime"),
    ("block_volatility_regimes", "volatility_regime"),
    ("block_session_regimes", "session_regime"),
    ("block_gap_regimes", "gap_regime"),
    ("block_combined_regimes", "combined_regime"),
]

ANALYSIS_TRADE_FAILURE_TARGETS = [
    "large_loss",
    "wrong_side",
    "profit_barrier_miss",
    "pred_hit_actual_miss",
    "exit_regret_high",
    "ev_overestimate_high",
    "any_failure",
]
ANALYSIS_TRADE_FAILURE_COLUMNS = [
    f"pred_trade_failure_{target_name}_{side_name}_prob"
    for target_name in ANALYSIS_TRADE_FAILURE_TARGETS
    for side_name in ("long", "short")
]
ANALYSIS_TRADE_QUALITY_COLUMNS = [
    f"pred_trade_quality_{side_name}_adjusted_pnl"
    for side_name in ("long", "short")
]

ANALYSIS_PREDICTION_COLUMNS = [
    "decision_timestamp",
    "dataset_month",
    *REGIME_COLUMNS,
    "long_best_adjusted_pnl",
    "short_best_adjusted_pnl",
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
    "pred_long_best_adjusted_pnl",
    "pred_short_best_adjusted_pnl",
    "pred_long_best_holding_minutes",
    "pred_short_best_holding_minutes",
    "pred_long_max_adverse_pnl",
    "pred_short_max_adverse_pnl",
    "pred_long_wait_regret",
    "pred_short_wait_regret",
    "pred_long_entry_local_rank",
    "pred_short_entry_local_rank",
    "pred_long_profit_barrier_hit",
    "pred_short_profit_barrier_hit",
    "pred_best_side",
    "pred_best_side_prob_1",
    "pred_best_side_prob_-1",
    *ANALYSIS_TRADE_FAILURE_COLUMNS,
    *ANALYSIS_TRADE_QUALITY_COLUMNS,
]

ANALYSIS_GROUP_COLUMNS = [
    "dataset_month",
    "direction",
    "exit_reason",
    "entry_hour",
    "trend_regime",
    "volatility_regime",
    "session_regime",
    "gap_regime",
    "combined_regime",
    "holding_bucket",
    "predicted_best_side",
    "actual_best_side",
    "actual_taken_profit_barrier_hit",
    "pred_taken_profit_barrier_hit",
    "actual_taken_best_bucket",
    "pred_taken_ev_bucket",
    "actual_taken_wait_regret_bucket",
    "pred_taken_wait_regret_bucket",
    "actual_taken_entry_rank_bucket",
    "pred_taken_entry_rank_bucket",
]

DIRECTION_SESSION_DIAGNOSTIC_COLUMNS = [
    "direction_session_adjusted_pnl_min",
    "worst_direction_session",
    "worst_direction_session_trade_count",
]

COMBINED_REGIME_DIAGNOSTIC_COLUMNS = [
    "combined_regime_adjusted_pnl_min",
    "worst_combined_regime",
    "worst_combined_regime_trade_count",
    "direction_combined_regime_adjusted_pnl_min",
    "worst_direction_combined_regime",
    "worst_direction_combined_regime_trade_count",
]

SIDE_EXPOSURE_DIAGNOSTIC_COLUMNS = [
    "long_trade_share",
    "short_trade_share",
    "max_side_trade_share",
]

TRADE_ANALYSIS_DIAGNOSTIC_COLUMNS = [
    "analysis_matched_prediction_rate",
    "direction_error_rate",
    "no_edge_rate",
    "predicted_side_error_rate",
    "exit_regret_sum",
    "exit_regret_mean",
    "best_side_regret_sum",
    "best_side_regret_mean",
    "ev_overestimate_vs_oracle_mean",
    "ev_overestimate_vs_realized_mean",
]

PROFIT_BARRIER_LABEL_COLUMNS = [
    "long_profit_barrier_hit",
    "short_profit_barrier_hit",
]

PROFIT_BARRIER_DIAGNOSTIC_COLUMNS = [
    "predicted_profit_barrier_miss_rate",
    "predicted_profit_barrier_miss_rate_smoothed",
    "predicted_profit_barrier_miss_count",
    "predicted_profit_barrier_observed_count",
    "predicted_profit_barrier_miss_adjusted_pnl",
    "actual_profit_barrier_miss_rate",
    "actual_profit_barrier_miss_rate_smoothed",
    "actual_profit_barrier_miss_count",
    "actual_profit_barrier_observed_count",
    "actual_profit_barrier_miss_adjusted_pnl",
]

PROFIT_BARRIER_CALIBRATION_BUCKETS = (
    (0.0, 0.2),
    (0.2, 0.4),
    (0.4, 0.6),
    (0.6, 0.8),
    (0.8, 1.0),
)

PROFIT_BARRIER_CALIBRATION_SUMMARY_COLUMNS = [
    "profit_barrier_calibration_observed_count",
    "profit_barrier_calibration_bucket_count",
    "profit_barrier_calibration_overestimate_max",
    "profit_barrier_calibration_overestimate_smoothed_max",
    "profit_barrier_calibration_abs_error_max",
    "worst_profit_barrier_calibration_bucket_count",
    "worst_profit_barrier_calibration_predicted_mean",
    "worst_profit_barrier_calibration_actual_hit_rate",
    "worst_profit_barrier_calibration_actual_hit_rate_smoothed",
    "worst_profit_barrier_calibration_overestimate",
    "worst_profit_barrier_calibration_overestimate_smoothed",
]

PROFIT_BARRIER_CALIBRATION_STRING_COLUMNS = [
    "worst_profit_barrier_calibration_bucket",
]


def probability_bucket_key(lower: float, upper: float) -> str:
    return f"{lower:.1f}_{upper:.1f}".replace(".", "p")


def probability_bucket_label(lower: float, upper: float) -> str:
    return f"{lower:.1f}-{upper:.1f}"


PROFIT_BARRIER_CALIBRATION_BUCKET_COLUMNS = [
    f"profit_barrier_calibration_{probability_bucket_key(lower, upper)}_{field}"
    for lower, upper in PROFIT_BARRIER_CALIBRATION_BUCKETS
    for field in (
        "count",
        "predicted_mean",
        "actual_hit_rate",
        "actual_hit_rate_smoothed",
        "overestimate",
        "overestimate_smoothed",
    )
]

PROFIT_BARRIER_CALIBRATION_COLUMNS = [
    *PROFIT_BARRIER_CALIBRATION_SUMMARY_COLUMNS,
    *PROFIT_BARRIER_CALIBRATION_BUCKET_COLUMNS,
]

COERCED_NUMERIC_DIAGNOSTIC_COLUMNS = {
    "direction_session_adjusted_pnl_min",
    "worst_direction_session_trade_count",
    "combined_regime_adjusted_pnl_min",
    "worst_combined_regime_trade_count",
    "direction_combined_regime_adjusted_pnl_min",
    "worst_direction_combined_regime_trade_count",
    *SIDE_EXPOSURE_DIAGNOSTIC_COLUMNS,
    *TRADE_ANALYSIS_DIAGNOSTIC_COLUMNS,
    *PROFIT_BARRIER_DIAGNOSTIC_COLUMNS,
    *PROFIT_BARRIER_CALIBRATION_COLUMNS,
}


@dataclass(frozen=True)
class BacktestConfig:
    evaluation_start: pd.Timestamp
    evaluation_end: pd.Timestamp
    max_holding: pd.Timedelta = pd.Timedelta(hours=24)
    profit_multiplier: float = 1.0
    loss_multiplier: float = 1.2
    spread_points: float = 0.0
    slippage_points: float = 0.0
    execution_delay_bars: int = 0


@dataclass(frozen=True)
class StrategyConfig:
    strategy: str
    fast_window: int = 20
    slow_window: int = 80
    rsi_window: int = 14
    rsi_lower: float = 30.0
    rsi_upper: float = 70.0
    rsi_exit_lower: float = 45.0
    rsi_exit_upper: float = 55.0
    breakout_window: int = 120
    random_entry_probability: float = 0.002
    random_exit_probability: float = 0.01
    random_seed: int = 7


@dataclass(frozen=True)
class ModelPolicyConfig:
    predictions: Path
    policy: str = "stateful_ev"
    entry_threshold: float = 15.0
    long_entry_threshold_offset: float = 0.0
    short_entry_threshold_offset: float = 0.0
    exit_threshold: float = 0.0
    side_margin: float = 0.0
    long_column: str = "pred_long_best_adjusted_pnl"
    short_column: str = "pred_short_best_adjusted_pnl"
    long_risk_column: str = "pred_long_max_adverse_pnl"
    short_risk_column: str = "pred_short_max_adverse_pnl"
    risk_penalty: float = 0.0
    long_secondary_score_column: str = ""
    short_secondary_score_column: str = ""
    secondary_score_tie_margin: float = -float("inf")
    long_holding_column: str = "pred_long_best_holding_minutes"
    short_holding_column: str = "pred_short_best_holding_minutes"
    min_predicted_hold_minutes: float = 1.0
    max_predicted_hold_minutes: float = 1440.0
    min_valid_predicted_hold_minutes: float = -float("inf")
    long_holding_fallback_column: str = ""
    short_holding_fallback_column: str = ""
    fixed_horizon_minutes: tuple[float, ...] = DEFAULT_FIXED_HORIZON_MINUTES
    long_fixed_horizon_columns: tuple[str, ...] = DEFAULT_LONG_FIXED_HORIZON_COLUMNS
    short_fixed_horizon_columns: tuple[str, ...] = DEFAULT_SHORT_FIXED_HORIZON_COLUMNS
    fixed_horizon_score_mode: str = "max"
    long_wait_regret_column: str = "pred_long_wait_regret"
    short_wait_regret_column: str = "pred_short_wait_regret"
    long_entry_rank_column: str = "pred_long_entry_local_rank"
    short_entry_rank_column: str = "pred_short_entry_local_rank"
    long_profit_barrier_column: str = "pred_long_profit_barrier_hit"
    short_profit_barrier_column: str = "pred_short_profit_barrier_hit"
    long_time_exit_column: str = "pred_long_exit_event_prob_0"
    short_time_exit_column: str = "pred_short_exit_event_prob_0"
    long_loss_first_column: str = "pred_long_exit_event_prob_2"
    short_loss_first_column: str = "pred_short_exit_event_prob_2"
    long_side_confidence_column: str = "pred_best_side_prob_1"
    short_side_confidence_column: str = "pred_best_side_prob_-1"
    long_trade_quality_column: str = "pred_trade_quality_long_adjusted_pnl"
    short_trade_quality_column: str = "pred_trade_quality_short_adjusted_pnl"
    max_wait_regret: float = float("inf")
    min_entry_rank: float = 0.0
    min_trade_quality: float = -float("inf")
    profit_barrier_miss_penalty: float = 0.0
    time_exit_penalty: float = 0.0
    loss_first_penalty: float = 0.0
    time_exit_holding_shrink: float = 0.0
    loss_first_holding_shrink: float = 0.0
    long_holding_shortening_column: str = "pred_long_fixed_60m_beats_exit_event_prob_1"
    short_holding_shortening_column: str = "pred_short_fixed_60m_beats_exit_event_prob_1"
    holding_shortening_threshold: float = float("inf")
    holding_shortening_cap_minutes: float = 60.0
    time_exit_exit_threshold: float = float("inf")
    loss_first_exit_threshold: float = float("inf")
    side_confidence_penalty: float = 0.0
    side_confidence_penalty_rules: tuple[str, ...] = ()
    side_confidence_overfit_penalty_rules: tuple[str, ...] = ()
    min_side_confidence: float = 0.0
    require_profit_barrier: bool = False
    profit_barrier_threshold: float = 0.5
    side_ev_penalty_rules: tuple[str, ...] = ()
    side_ev_penalty_replacement_min_margin: float = -float("inf")
    extra_side_margin_rules: tuple[str, ...] = ()
    side_extra_margin_rules: tuple[str, ...] = ()
    side_block_rules: tuple[str, ...] = ()
    context_drawdown_guard_loss_threshold: float = float("inf")
    context_drawdown_guard_min_entry_margin: float = float("inf")
    context_drawdown_guard_context_columns: tuple[str, ...] = ("combined_regime", "session_regime")
    context_drawdown_guard_reset_monthly: bool = True
    block_trend_regimes: tuple[str, ...] = ()
    block_volatility_regimes: tuple[str, ...] = ()
    block_session_regimes: tuple[str, ...] = ()
    block_gap_regimes: tuple[str, ...] = ()
    block_combined_regimes: tuple[str, ...] = ()


@dataclass
class Position:
    direction: int
    entry_timestamp: pd.Timestamp
    entry_price: float
    entry_decision_timestamp: pd.Timestamp
    max_exit_timestamp: pd.Timestamp
    context_drawdown_key: str = ""


@dataclass(frozen=True)
class Trade:
    direction: str
    entry_timestamp: pd.Timestamp
    exit_timestamp: pd.Timestamp
    entry_price: float
    exit_price: float
    raw_pnl: float
    adjusted_pnl: float
    holding_minutes: float
    exit_reason: str
    entry_decision_timestamp: pd.Timestamp
    exit_decision_timestamp: pd.Timestamp


def adjusted_pnl(raw_pnl: float, profit_multiplier: float, loss_multiplier: float) -> float:
    if raw_pnl > 0:
        return raw_pnl * profit_multiplier
    if raw_pnl < 0:
        return raw_pnl * loss_multiplier
    return 0.0


def execution_cost_per_side(config: BacktestConfig) -> float:
    if config.spread_points < 0:
        raise ValueError("spread_points must be non-negative")
    if config.slippage_points < 0:
        raise ValueError("slippage_points must be non-negative")
    return config.spread_points / 2.0 + config.slippage_points


def apply_execution_cost(
    open_price: float,
    direction: int,
    is_entry: bool,
    config: BacktestConfig,
) -> float:
    cost = execution_cost_per_side(config)
    if is_entry:
        return float(open_price + direction * cost)
    return float(open_price - direction * cost)


def month_bounds(month: str) -> tuple[pd.Timestamp, pd.Timestamp]:
    try:
        start = pd.Timestamp(f"{month}-01", tz="UTC")
    except ValueError as exc:
        raise argparse.ArgumentTypeError("month must be in YYYY-MM format") from exc
    if start.strftime("%Y-%m") != month:
        raise argparse.ArgumentTypeError("month must be in YYYY-MM format")
    end = start + pd.DateOffset(months=1)
    return start, end


def read_ohlcv(path: Path) -> pd.DataFrame:
    columns = ["timestamp", "open", "high", "low", "close"]
    df = pd.read_parquet(path, columns=columns)
    missing = sorted(set(columns) - set(df.columns))
    if missing:
        raise ValueError(f"{path} is missing columns: {', '.join(missing)}")
    df = df.dropna(subset=columns).sort_values("timestamp").reset_index(drop=True)
    if df["timestamp"].dt.tz is None:
        df["timestamp"] = df["timestamp"].dt.tz_localize("UTC")
    else:
        df["timestamp"] = df["timestamp"].dt.tz_convert("UTC")
    return df


def slice_for_month(
    df: pd.DataFrame,
    start: pd.Timestamp,
    end: pd.Timestamp,
    warmup_days: int,
    post_days: int,
    max_holding: pd.Timedelta,
) -> pd.DataFrame:
    left = start - pd.Timedelta(days=warmup_days)
    right = end + max_holding + pd.Timedelta(days=post_days)
    sliced = df[(df["timestamp"] >= left) & (df["timestamp"] <= right)].copy()
    if sliced.empty:
        raise ValueError(f"no data found for requested window: {left} to {right}")
    return sliced.reset_index(drop=True)


def build_signal(df: pd.DataFrame, config: StrategyConfig) -> pd.Series:
    strategy = config.strategy
    if strategy == "no_trade":
        return pd.Series(0, index=df.index, dtype="int8")
    if strategy == "random":
        return random_signal(df, config)
    if strategy == "ma_cross":
        return ma_cross_signal(df, config.fast_window, config.slow_window)
    if strategy == "rsi_reversal":
        return rsi_reversal_signal(
            df,
            config.rsi_window,
            config.rsi_lower,
            config.rsi_upper,
            config.rsi_exit_lower,
            config.rsi_exit_upper,
        )
    if strategy == "breakout":
        return breakout_signal(df, config.breakout_window)
    raise ValueError(f"unknown strategy: {strategy}")


def available_strategies() -> list[str]:
    return ["no_trade", "random", "ma_cross", "rsi_reversal", "breakout"]


def available_model_policies() -> list[str]:
    return ["stateful_ev", "stateless_ev", "timed_ev", "fixed_horizon_ev"]


def random_signal(df: pd.DataFrame, config: StrategyConfig) -> pd.Series:
    rng = random.Random(config.random_seed)
    state = 0
    values: list[int] = []
    for _ in range(len(df)):
        if state == 0:
            if rng.random() < config.random_entry_probability:
                state = rng.choice([-1, 1])
        elif rng.random() < config.random_exit_probability:
            state = 0
        values.append(state)
    return pd.Series(values, index=df.index, dtype="int8")


def ma_cross_signal(df: pd.DataFrame, fast_window: int, slow_window: int) -> pd.Series:
    if fast_window <= 0 or slow_window <= 0:
        raise ValueError("MA windows must be positive")
    if fast_window >= slow_window:
        raise ValueError("fast_window must be smaller than slow_window")
    fast = df["close"].rolling(fast_window, min_periods=fast_window).mean()
    slow = df["close"].rolling(slow_window, min_periods=slow_window).mean()
    signal = pd.Series(0, index=df.index, dtype="int8")
    signal[fast > slow] = 1
    signal[fast < slow] = -1
    signal[slow.isna()] = 0
    return signal


def compute_rsi(close: pd.Series, window: int) -> pd.Series:
    if window <= 0:
        raise ValueError("RSI window must be positive")
    diff = close.diff()
    gains = diff.clip(lower=0)
    losses = -diff.clip(upper=0)
    avg_gain = gains.rolling(window, min_periods=window).mean()
    avg_loss = losses.rolling(window, min_periods=window).mean()
    rs = avg_gain / avg_loss.mask(avg_loss == 0)
    rsi = 100 - (100 / (1 + rs))
    rsi = rsi.fillna(50.0)
    return rsi


def rsi_reversal_signal(
    df: pd.DataFrame,
    window: int,
    lower: float,
    upper: float,
    exit_lower: float,
    exit_upper: float,
) -> pd.Series:
    if not lower < exit_lower <= exit_upper < upper:
        raise ValueError("RSI thresholds must satisfy lower < exit_lower <= exit_upper < upper")
    rsi = compute_rsi(df["close"], window)
    state = 0
    values: list[int] = []
    for value in rsi:
        if value <= lower:
            state = 1
        elif value >= upper:
            state = -1
        elif exit_lower <= value <= exit_upper:
            state = 0
        values.append(state)
    return pd.Series(values, index=df.index, dtype="int8")


def breakout_signal(df: pd.DataFrame, window: int) -> pd.Series:
    if window <= 1:
        raise ValueError("breakout window must be greater than 1")
    previous_high = df["high"].rolling(window, min_periods=window).max().shift(1)
    previous_low = df["low"].rolling(window, min_periods=window).min().shift(1)
    state = 0
    values: list[int] = []
    for close, high_level, low_level in zip(df["close"], previous_high, previous_low):
        if pd.notna(high_level) and close > high_level:
            state = 1
        elif pd.notna(low_level) and close < low_level:
            state = -1
        values.append(state)
    return pd.Series(values, index=df.index, dtype="int8")


def prediction_required_columns(config: ModelPolicyConfig) -> list[str]:
    if config.policy == "fixed_horizon_ev":
        validate_fixed_horizon_config(config)
    required_columns = ["decision_timestamp", config.long_column, config.short_column]
    if secondary_score_tie_break_enabled(config):
        required_columns.extend(
            [config.long_secondary_score_column, config.short_secondary_score_column]
        )
    if config.risk_penalty > 0:
        required_columns.extend([config.long_risk_column, config.short_risk_column])
    if config.policy == "timed_ev":
        required_columns.extend([config.long_holding_column, config.short_holding_column])
        if config.long_holding_fallback_column:
            required_columns.append(config.long_holding_fallback_column)
        if config.short_holding_fallback_column:
            required_columns.append(config.short_holding_fallback_column)
    if config.policy == "fixed_horizon_ev":
        required_columns.extend([*config.long_fixed_horizon_columns, *config.short_fixed_horizon_columns])
    if np.isfinite(config.max_wait_regret):
        required_columns.extend([config.long_wait_regret_column, config.short_wait_regret_column])
    if config.min_entry_rank > 0:
        required_columns.extend([config.long_entry_rank_column, config.short_entry_rank_column])
    profit_barrier_prediction_columns = [
        config.long_profit_barrier_column,
        config.short_profit_barrier_column,
    ]
    if config.require_profit_barrier or config.profit_barrier_miss_penalty > 0:
        required_columns.extend(profit_barrier_prediction_columns)
    time_exit_prediction_columns = [
        config.long_time_exit_column,
        config.short_time_exit_column,
    ]
    if (
        config.time_exit_penalty > 0
        or config.time_exit_holding_shrink > 0
        or np.isfinite(config.time_exit_exit_threshold)
    ):
        required_columns.extend(time_exit_prediction_columns)
    loss_first_prediction_columns = [
        config.long_loss_first_column,
        config.short_loss_first_column,
    ]
    if (
        config.loss_first_penalty > 0
        or config.loss_first_holding_shrink > 0
        or np.isfinite(config.loss_first_exit_threshold)
    ):
        required_columns.extend(loss_first_prediction_columns)
    holding_shortening_prediction_columns = [
        config.long_holding_shortening_column,
        config.short_holding_shortening_column,
    ]
    if np.isfinite(config.holding_shortening_threshold):
        required_columns.extend(holding_shortening_prediction_columns)
    side_confidence_prediction_columns = [
        config.long_side_confidence_column,
        config.short_side_confidence_column,
    ]
    if (
        config.min_side_confidence > 0
        or config.side_confidence_penalty > 0
        or config.side_confidence_penalty_rules
        or config.side_confidence_overfit_penalty_rules
    ):
        required_columns.extend(side_confidence_prediction_columns)
    trade_quality_prediction_columns = [
        config.long_trade_quality_column,
        config.short_trade_quality_column,
    ]
    if np.isfinite(config.min_trade_quality):
        required_columns.extend(trade_quality_prediction_columns)
    required_columns.extend(extra_side_margin_rule_columns(config))
    required_columns.extend(side_rule_columns(config))
    required_columns.extend([column for column, _ in blocked_regime_columns(config)])
    if context_drawdown_guard_enabled(config):
        required_columns.extend(config.context_drawdown_guard_context_columns)
    return list(dict.fromkeys(required_columns))


def prediction_optional_columns(path: Path, config: ModelPolicyConfig) -> list[str]:
    optional_columns: list[str] = []
    profit_barrier_prediction_columns = [
        config.long_profit_barrier_column,
        config.short_profit_barrier_column,
    ]
    if not (config.require_profit_barrier or config.profit_barrier_miss_penalty > 0):
        optional_columns.extend(optional_parquet_columns(path, profit_barrier_prediction_columns))
    time_exit_prediction_columns = [
        config.long_time_exit_column,
        config.short_time_exit_column,
    ]
    if not (
        config.time_exit_penalty > 0
        or config.time_exit_holding_shrink > 0
        or np.isfinite(config.time_exit_exit_threshold)
    ):
        optional_columns.extend(optional_parquet_columns(path, time_exit_prediction_columns))
    loss_first_prediction_columns = [
        config.long_loss_first_column,
        config.short_loss_first_column,
    ]
    if not (
        config.loss_first_penalty > 0
        or config.loss_first_holding_shrink > 0
        or np.isfinite(config.loss_first_exit_threshold)
    ):
        optional_columns.extend(optional_parquet_columns(path, loss_first_prediction_columns))
    holding_shortening_prediction_columns = [
        config.long_holding_shortening_column,
        config.short_holding_shortening_column,
    ]
    if not np.isfinite(config.holding_shortening_threshold):
        optional_columns.extend(
            optional_parquet_columns(path, holding_shortening_prediction_columns)
        )
    side_confidence_prediction_columns = [
        config.long_side_confidence_column,
        config.short_side_confidence_column,
    ]
    if not (
        config.min_side_confidence > 0
        or config.side_confidence_penalty > 0
        or config.side_confidence_penalty_rules
        or config.side_confidence_overfit_penalty_rules
    ):
        optional_columns.extend(optional_parquet_columns(path, side_confidence_prediction_columns))
    trade_quality_prediction_columns = [
        config.long_trade_quality_column,
        config.short_trade_quality_column,
    ]
    if not np.isfinite(config.min_trade_quality):
        optional_columns.extend(optional_parquet_columns(path, trade_quality_prediction_columns))
    optional_columns.extend(optional_parquet_columns(path, ANALYSIS_PREDICTION_COLUMNS))
    optional_columns.extend(optional_parquet_columns(path, PROFIT_BARRIER_LABEL_COLUMNS))
    optional_columns.extend(optional_parquet_columns(path, REGIME_COLUMNS))
    return list(dict.fromkeys(optional_columns))


def normalize_prediction_frame(
    predictions: pd.DataFrame,
    required_columns: list[str],
    path: Path,
    *,
    drop_required_na: bool = True,
) -> pd.DataFrame:
    predictions = predictions.copy()
    missing = sorted(set(required_columns) - set(predictions.columns))
    if missing:
        raise ValueError(f"{path} is missing columns: {', '.join(missing)}")
    if not pd.api.types.is_datetime64_any_dtype(predictions["decision_timestamp"]):
        predictions["decision_timestamp"] = pd.to_datetime(
            predictions["decision_timestamp"],
            utc=True,
        )
    subset = required_columns if drop_required_na else ["decision_timestamp"]
    predictions = predictions.dropna(subset=subset).sort_values("decision_timestamp")
    if predictions["decision_timestamp"].dt.tz is None:
        predictions["decision_timestamp"] = predictions["decision_timestamp"].dt.tz_localize("UTC")
    else:
        predictions["decision_timestamp"] = predictions["decision_timestamp"].dt.tz_convert("UTC")
    duplicated = predictions["decision_timestamp"].duplicated()
    if duplicated.any():
        duplicated_count = int(duplicated.sum())
        raise ValueError(f"{path} has duplicated decision_timestamp values: {duplicated_count}")
    return predictions.reset_index(drop=True)


def read_prediction_frame(
    path: Path,
    config: ModelPolicyConfig,
    *,
    drop_required_na: bool = True,
) -> pd.DataFrame:
    required_columns = prediction_required_columns(config)
    optional_columns = prediction_optional_columns(path, config)
    columns = list(dict.fromkeys([*required_columns, *optional_columns]))
    predictions = pd.read_parquet(path, columns=columns)
    return normalize_prediction_frame(
        predictions,
        required_columns,
        path,
        drop_required_na=drop_required_na,
    )


def blocked_regime_columns(config: ModelPolicyConfig) -> list[tuple[str, tuple[str, ...]]]:
    return [
        (column, tuple(getattr(config, field)))
        for field, column in REGIME_BLOCK_FIELDS
        if getattr(config, field)
    ]


def fixed_horizon_scores(
    horizon_frame: pd.DataFrame,
    minutes: tuple[float, ...],
    score_mode: str = "max",
) -> tuple[pd.Series, pd.Series]:
    if horizon_frame.shape[1] != len(minutes):
        raise ValueError("horizon_frame column count must match fixed horizon minutes")
    if score_mode not in FIXED_HORIZON_SCORE_MODES:
        raise ValueError(f"unknown fixed horizon score mode: {score_mode}")
    values = horizon_frame.to_numpy(dtype=float)
    finite = np.isfinite(values)
    filled = np.where(finite, values, -np.inf)
    best_indices = filled.argmax(axis=1)
    rows = np.arange(len(horizon_frame))
    if score_mode == "max":
        scores = filled[rows, best_indices]
    else:
        aggregate_values = np.where(finite, values, np.nan)
        aggregate_frame = pd.DataFrame(aggregate_values, index=horizon_frame.index)
        if score_mode == "mean":
            scores = aggregate_frame.mean(axis=1, skipna=True).to_numpy()
        elif score_mode == "median":
            scores = aggregate_frame.median(axis=1, skipna=True).to_numpy()
        else:
            scores = aggregate_frame.min(axis=1, skipna=True).to_numpy()
    best_minutes = np.asarray(minutes, dtype=float)[best_indices]
    no_valid_horizon = ~finite.any(axis=1)
    scores[no_valid_horizon] = np.nan
    best_minutes[no_valid_horizon] = np.nan
    return (
        pd.Series(scores, index=horizon_frame.index),
        pd.Series(best_minutes, index=horizon_frame.index),
    )


def side_rule_condition_mask(
    prediction_index: pd.DataFrame,
    timestamps: pd.Series,
    index: pd.Index,
    conditions: tuple[tuple[str, str], ...],
) -> pd.Series:
    mask = pd.Series(True, index=index)
    for column, expected_value in conditions:
        aligned = prediction_index[[column]].reindex(timestamps)
        values = pd.Series(
            aligned[column].reset_index(drop=True).astype("string").to_numpy(),
            index=index,
        )
        mask &= values.notna() & (values == expected_value)
    return mask


def secondary_score_tie_break_enabled(config: ModelPolicyConfig) -> bool:
    return (
        np.isfinite(config.secondary_score_tie_margin)
        and config.secondary_score_tie_margin >= 0
        and bool(config.long_secondary_score_column)
        and bool(config.short_secondary_score_column)
    )


def model_signal_from_predictions(
    df: pd.DataFrame,
    predictions: pd.DataFrame,
    config: ModelPolicyConfig,
) -> pd.Series:
    if config.policy not in available_model_policies():
        raise ValueError(f"unknown model policy: {config.policy}")
    if config.side_margin < 0:
        raise ValueError("side_margin must be non-negative")
    if config.risk_penalty < 0:
        raise ValueError("risk_penalty must be non-negative")
    if (
        np.isfinite(config.secondary_score_tie_margin)
        and config.secondary_score_tie_margin < 0
    ):
        raise ValueError("secondary_score_tie_margin must be non-negative or -inf")
    if (
        config.side_ev_penalty_replacement_min_margin < 0
        and not np.isneginf(config.side_ev_penalty_replacement_min_margin)
    ):
        raise ValueError(
            "side_ev_penalty_replacement_min_margin must be non-negative or -inf"
        )
    if (
        np.isfinite(config.secondary_score_tie_margin)
        and config.secondary_score_tie_margin >= 0
        and (
            not config.long_secondary_score_column
            or not config.short_secondary_score_column
        )
    ):
        raise ValueError(
            "secondary score tie-break requires both long and short secondary score columns"
        )
    if config.profit_barrier_miss_penalty < 0:
        raise ValueError("profit_barrier_miss_penalty must be non-negative")
    if config.time_exit_penalty < 0:
        raise ValueError("time_exit_penalty must be non-negative")
    if config.loss_first_penalty < 0:
        raise ValueError("loss_first_penalty must be non-negative")
    if not 0 <= config.time_exit_holding_shrink <= 1:
        raise ValueError("time_exit_holding_shrink must be between 0 and 1")
    if not 0 <= config.loss_first_holding_shrink <= 1:
        raise ValueError("loss_first_holding_shrink must be between 0 and 1")
    holding_shortening_enabled = np.isfinite(config.holding_shortening_threshold)
    if holding_shortening_enabled:
        if not 0 <= config.holding_shortening_threshold <= 1:
            raise ValueError("holding_shortening_threshold must be between 0 and 1 or inf")
        if config.holding_shortening_cap_minutes <= 0:
            raise ValueError("holding_shortening_cap_minutes must be positive")
        if config.policy not in {"timed_ev", "fixed_horizon_ev"}:
            raise ValueError(
                "holding shortening requires timed_ev or fixed_horizon_ev policy"
            )
        if (
            not config.long_holding_shortening_column
            or not config.short_holding_shortening_column
        ):
            raise ValueError(
                "holding shortening requires both long and short probability columns"
            )
    if np.isfinite(config.time_exit_exit_threshold) and not 0 <= config.time_exit_exit_threshold <= 1:
        raise ValueError("time_exit_exit_threshold must be between 0 and 1 or inf")
    if np.isfinite(config.loss_first_exit_threshold) and not 0 <= config.loss_first_exit_threshold <= 1:
        raise ValueError("loss_first_exit_threshold must be between 0 and 1 or inf")
    if config.side_confidence_penalty < 0:
        raise ValueError("side_confidence_penalty must be non-negative")
    if not 0 <= config.min_side_confidence <= 1:
        raise ValueError("min_side_confidence must be between 0 and 1")
    if config.min_predicted_hold_minutes < 0:
        raise ValueError("min_predicted_hold_minutes must be non-negative")
    if config.max_predicted_hold_minutes < config.min_predicted_hold_minutes:
        raise ValueError(
            "max_predicted_hold_minutes must be greater than or equal to "
            "min_predicted_hold_minutes"
        )
    if (
        np.isfinite(config.min_valid_predicted_hold_minutes)
        and config.min_valid_predicted_hold_minutes < 0
    ):
        raise ValueError("min_valid_predicted_hold_minutes must be non-negative or -inf")

    prediction_index = predictions.set_index("decision_timestamp")
    aligned = prediction_index[[config.long_column, config.short_column]].reindex(df["timestamp"])
    long_ev = aligned[config.long_column].reset_index(drop=True).astype(float)
    short_ev = aligned[config.short_column].reset_index(drop=True).astype(float)
    long_holding = None
    short_holding = None
    long_holding_entry_ok = None
    short_holding_entry_ok = None
    long_time_exit = None
    short_time_exit = None
    long_loss_first = None
    short_loss_first = None
    if config.policy == "fixed_horizon_ev":
        validate_fixed_horizon_config(config)
        long_fixed_aligned = prediction_index[list(config.long_fixed_horizon_columns)].reindex(df["timestamp"])
        short_fixed_aligned = prediction_index[list(config.short_fixed_horizon_columns)].reindex(df["timestamp"])
        long_ev, long_holding = fixed_horizon_scores(
            long_fixed_aligned.reset_index(drop=True),
            config.fixed_horizon_minutes,
            config.fixed_horizon_score_mode,
        )
        short_ev, short_holding = fixed_horizon_scores(
            short_fixed_aligned.reset_index(drop=True),
            config.fixed_horizon_minutes,
            config.fixed_horizon_score_mode,
        )
    if config.risk_penalty > 0:
        risk_aligned = prediction_index[[config.long_risk_column, config.short_risk_column]].reindex(
            df["timestamp"]
        )
        long_risk = risk_aligned[config.long_risk_column].reset_index(drop=True).astype(float)
        short_risk = risk_aligned[config.short_risk_column].reset_index(drop=True).astype(float)
        long_ev = long_ev - config.risk_penalty * (-long_risk).clip(lower=0)
        short_ev = short_ev - config.risk_penalty * (-short_risk).clip(lower=0)
    if config.profit_barrier_miss_penalty > 0:
        barrier_aligned = prediction_index[
            [config.long_profit_barrier_column, config.short_profit_barrier_column]
        ].reindex(df["timestamp"])
        long_barrier = barrier_aligned[config.long_profit_barrier_column].reset_index(drop=True).astype(float)
        short_barrier = barrier_aligned[config.short_profit_barrier_column].reset_index(drop=True).astype(float)
        long_ev = long_ev - config.profit_barrier_miss_penalty * (1.0 - long_barrier).clip(0.0, 1.0)
        short_ev = short_ev - config.profit_barrier_miss_penalty * (1.0 - short_barrier).clip(0.0, 1.0)
    if (
        config.time_exit_penalty > 0
        or config.time_exit_holding_shrink > 0
        or np.isfinite(config.time_exit_exit_threshold)
    ):
        time_exit_aligned = prediction_index[
            [config.long_time_exit_column, config.short_time_exit_column]
        ].reindex(df["timestamp"])
        long_time_exit = time_exit_aligned[config.long_time_exit_column].reset_index(drop=True).astype(float)
        short_time_exit = time_exit_aligned[config.short_time_exit_column].reset_index(drop=True).astype(float)
    if config.time_exit_penalty > 0:
        long_ev = long_ev - config.time_exit_penalty * long_time_exit.clip(0.0, 1.0)
        short_ev = short_ev - config.time_exit_penalty * short_time_exit.clip(0.0, 1.0)
    if (
        config.loss_first_penalty > 0
        or config.loss_first_holding_shrink > 0
        or np.isfinite(config.loss_first_exit_threshold)
    ):
        loss_first_aligned = prediction_index[
            [config.long_loss_first_column, config.short_loss_first_column]
        ].reindex(df["timestamp"])
        long_loss_first = loss_first_aligned[config.long_loss_first_column].reset_index(drop=True).astype(float)
        short_loss_first = loss_first_aligned[config.short_loss_first_column].reset_index(drop=True).astype(float)
    if config.loss_first_penalty > 0:
        long_ev = long_ev - config.loss_first_penalty * long_loss_first.clip(0.0, 1.0)
        short_ev = short_ev - config.loss_first_penalty * short_loss_first.clip(0.0, 1.0)
    pre_side_ev_penalty_long_ev = long_ev.copy()
    pre_side_ev_penalty_short_ev = short_ev.copy()
    long_side_ev_penalty = pd.Series(0.0, index=df.index, dtype="float64")
    short_side_ev_penalty = pd.Series(0.0, index=df.index, dtype="float64")
    for side, conditions, penalty in parsed_side_ev_penalty_rules(config):
        condition_mask = side_rule_condition_mask(
            prediction_index,
            df["timestamp"],
            df.index,
            conditions,
        )
        side_penalty = pd.Series(
            np.where(condition_mask.to_numpy(), penalty, 0.0),
            index=df.index,
        )
        if side == 1:
            long_ev = long_ev - side_penalty
            long_side_ev_penalty = long_side_ev_penalty + side_penalty
        else:
            short_ev = short_ev - side_penalty
            short_side_ev_penalty = short_side_ev_penalty + side_penalty
    long_side_confidence = None
    short_side_confidence = None
    if (
        config.min_side_confidence > 0
        or config.side_confidence_penalty > 0
        or config.side_confidence_penalty_rules
        or config.side_confidence_overfit_penalty_rules
    ):
        side_confidence_aligned = prediction_index[
            [config.long_side_confidence_column, config.short_side_confidence_column]
        ].reindex(df["timestamp"])
        long_side_confidence = (
            side_confidence_aligned[config.long_side_confidence_column]
            .reset_index(drop=True)
            .astype(float)
        )
        short_side_confidence = (
            side_confidence_aligned[config.short_side_confidence_column]
            .reset_index(drop=True)
            .astype(float)
        )
        if config.side_confidence_penalty > 0 or config.side_confidence_penalty_rules:
            side_confidence_penalty = pd.Series(
                config.side_confidence_penalty,
                index=df.index,
                dtype="float64",
            )
            for conditions, penalty in parsed_side_confidence_penalty_rules(config):
                condition_mask = side_rule_condition_mask(
                    prediction_index,
                    df["timestamp"],
                    df.index,
                    conditions,
                )
                side_confidence_penalty += np.where(condition_mask.to_numpy(), penalty, 0.0)
            long_ev = long_ev - side_confidence_penalty * (1.0 - long_side_confidence).clip(0.0, 1.0)
            short_ev = short_ev - side_confidence_penalty * (1.0 - short_side_confidence).clip(0.0, 1.0)
        if config.side_confidence_overfit_penalty_rules:
            side_confidence_overfit_penalty = pd.Series(0.0, index=df.index, dtype="float64")
            for conditions, penalty in parsed_side_confidence_overfit_penalty_rules(config):
                condition_mask = side_rule_condition_mask(
                    prediction_index,
                    df["timestamp"],
                    df.index,
                    conditions,
                )
                side_confidence_overfit_penalty += np.where(condition_mask.to_numpy(), penalty, 0.0)
            long_ev = long_ev - side_confidence_overfit_penalty * long_side_confidence.clip(0.0, 1.0)
            short_ev = short_ev - side_confidence_overfit_penalty * short_side_confidence.clip(0.0, 1.0)
    if config.policy == "timed_ev":
        holding_columns = [config.long_holding_column, config.short_holding_column]
        if config.long_holding_fallback_column:
            holding_columns.append(config.long_holding_fallback_column)
        if config.short_holding_fallback_column:
            holding_columns.append(config.short_holding_fallback_column)
        holding_columns = list(dict.fromkeys(holding_columns))
        holding_aligned = prediction_index[holding_columns].reindex(df["timestamp"])
        long_holding = holding_aligned[config.long_holding_column].reset_index(drop=True).astype(float)
        short_holding = holding_aligned[config.short_holding_column].reset_index(drop=True).astype(float)
        holding_guard_enabled = (
            np.isfinite(config.min_valid_predicted_hold_minutes)
            or bool(config.long_holding_fallback_column)
            or bool(config.short_holding_fallback_column)
        )
        if holding_guard_enabled:
            min_valid_hold = (
                config.min_valid_predicted_hold_minutes
                if np.isfinite(config.min_valid_predicted_hold_minutes)
                else -float("inf")
            )
            long_primary_ok = (
                long_holding.notna()
                & np.isfinite(long_holding)
                & (long_holding >= min_valid_hold)
            )
            short_primary_ok = (
                short_holding.notna()
                & np.isfinite(short_holding)
                & (short_holding >= min_valid_hold)
            )
            long_holding_entry_ok = long_primary_ok.copy()
            short_holding_entry_ok = short_primary_ok.copy()
            if config.long_holding_fallback_column:
                long_fallback = (
                    holding_aligned[config.long_holding_fallback_column]
                    .reset_index(drop=True)
                    .astype(float)
                )
                long_fallback_ok = (
                    long_fallback.notna()
                    & np.isfinite(long_fallback)
                    & (long_fallback >= min_valid_hold)
                )
                long_holding = long_holding.where(long_primary_ok, long_fallback)
                long_holding_entry_ok = long_primary_ok | (~long_primary_ok & long_fallback_ok)
            if config.short_holding_fallback_column:
                short_fallback = (
                    holding_aligned[config.short_holding_fallback_column]
                    .reset_index(drop=True)
                    .astype(float)
                )
                short_fallback_ok = (
                    short_fallback.notna()
                    & np.isfinite(short_fallback)
                    & (short_fallback >= min_valid_hold)
                )
                short_holding = short_holding.where(short_primary_ok, short_fallback)
                short_holding_entry_ok = short_primary_ok | (~short_primary_ok & short_fallback_ok)
    if (
        config.policy in {"timed_ev", "fixed_horizon_ev"}
        and long_holding is not None
        and short_holding is not None
        and (config.time_exit_holding_shrink > 0 or config.loss_first_holding_shrink > 0)
    ):
        long_holding_multiplier = pd.Series(1.0, index=long_holding.index, dtype="float64")
        short_holding_multiplier = pd.Series(1.0, index=short_holding.index, dtype="float64")
        if config.time_exit_holding_shrink > 0:
            long_holding_multiplier -= (
                config.time_exit_holding_shrink * long_time_exit.clip(0.0, 1.0)
            )
            short_holding_multiplier -= (
                config.time_exit_holding_shrink * short_time_exit.clip(0.0, 1.0)
            )
        if config.loss_first_holding_shrink > 0:
            long_holding_multiplier -= (
                config.loss_first_holding_shrink * long_loss_first.clip(0.0, 1.0)
            )
            short_holding_multiplier -= (
                config.loss_first_holding_shrink * short_loss_first.clip(0.0, 1.0)
            )
        long_holding = long_holding * long_holding_multiplier.clip(0.0, 1.0)
        short_holding = short_holding * short_holding_multiplier.clip(0.0, 1.0)
    if (
        holding_shortening_enabled
        and config.policy in {"timed_ev", "fixed_horizon_ev"}
        and long_holding is not None
        and short_holding is not None
    ):
        shortening_aligned = prediction_index[
            [
                config.long_holding_shortening_column,
                config.short_holding_shortening_column,
            ]
        ].reindex(df["timestamp"])
        long_shortening_prob = (
            shortening_aligned[config.long_holding_shortening_column]
            .reset_index(drop=True)
            .astype(float)
            .clip(0.0, 1.0)
        )
        short_shortening_prob = (
            shortening_aligned[config.short_holding_shortening_column]
            .reset_index(drop=True)
            .astype(float)
            .clip(0.0, 1.0)
        )
        cap_minutes = config.holding_shortening_cap_minutes
        long_shortening_mask = (
            long_shortening_prob.notna()
            & (long_shortening_prob >= config.holding_shortening_threshold)
        )
        short_shortening_mask = (
            short_shortening_prob.notna()
            & (short_shortening_prob >= config.holding_shortening_threshold)
        )
        long_holding = long_holding.where(
            ~long_shortening_mask,
            np.minimum(long_holding, cap_minutes),
        )
        short_holding = short_holding.where(
            ~short_shortening_mask,
            np.minimum(short_holding, cap_minutes),
        )
    best_side = pd.Series(0, index=df.index, dtype="int8")
    best_score = pd.concat([long_ev, short_ev], axis=1).max(axis=1)
    side_gap = (long_ev - short_ev).abs()
    valid_prediction = long_ev.notna() & short_ev.notna()
    best_side.iloc[(valid_prediction & (long_ev >= short_ev)).to_numpy()] = 1
    best_side.iloc[(valid_prediction & (long_ev < short_ev)).to_numpy()] = -1
    selected_side = best_side.copy()
    selected_score = best_score.copy()
    if secondary_score_tie_break_enabled(config):
        secondary_aligned = prediction_index[
            [config.long_secondary_score_column, config.short_secondary_score_column]
        ].reindex(df["timestamp"])
        long_secondary_score = (
            secondary_aligned[config.long_secondary_score_column]
            .reset_index(drop=True)
            .astype(float)
        )
        short_secondary_score = (
            secondary_aligned[config.short_secondary_score_column]
            .reset_index(drop=True)
            .astype(float)
        )
        secondary_valid = long_secondary_score.notna() & short_secondary_score.notna()
        secondary_valid &= np.isfinite(long_secondary_score) & np.isfinite(
            short_secondary_score
        )
        near_tie = valid_prediction & secondary_valid & (
            side_gap <= config.secondary_score_tie_margin
        )
        secondary_prefers_long = long_secondary_score >= short_secondary_score
        selected_side.iloc[(near_tie & secondary_prefers_long).to_numpy()] = 1
        selected_side.iloc[(near_tie & ~secondary_prefers_long).to_numpy()] = -1
        selected_score = pd.Series(
            np.where(selected_side == 1, long_ev, short_ev),
            index=df.index,
        )
    pre_side_ev_penalty_best_side = pd.Series(0, index=df.index, dtype="int8")
    pre_side_ev_penalty_valid = (
        pre_side_ev_penalty_long_ev.notna() & pre_side_ev_penalty_short_ev.notna()
    )
    pre_side_ev_penalty_best_side.iloc[
        (
            pre_side_ev_penalty_valid
            & (pre_side_ev_penalty_long_ev >= pre_side_ev_penalty_short_ev)
        ).to_numpy()
    ] = 1
    pre_side_ev_penalty_best_side.iloc[
        (
            pre_side_ev_penalty_valid
            & (pre_side_ev_penalty_long_ev < pre_side_ev_penalty_short_ev)
        ).to_numpy()
    ] = -1
    side_ev_penalized_preferred_side = pd.Series(
        np.where(
            pre_side_ev_penalty_best_side == 1,
            long_side_ev_penalty > 0,
            np.where(pre_side_ev_penalty_best_side == -1, short_side_ev_penalty > 0, False),
        ),
        index=df.index,
    ).astype(bool)
    side_ev_penalty_replacement = (
        valid_prediction
        & pre_side_ev_penalty_valid
        & side_ev_penalized_preferred_side
        & (selected_side != pre_side_ev_penalty_best_side)
    )
    selected_side_ev_penalty = pd.Series(
        np.where(selected_side == 1, long_side_ev_penalty, short_side_ev_penalty),
        index=df.index,
    )
    side_ev_penalty_guarded_entry = (
        valid_prediction
        & (selected_side_ev_penalty > 0)
    )
    side_ev_penalty_admission_entry = (
        side_ev_penalty_guarded_entry | side_ev_penalty_replacement
    )
    long_entry_threshold = config.entry_threshold + config.long_entry_threshold_offset
    short_entry_threshold = config.entry_threshold + config.short_entry_threshold_offset
    required_entry_threshold = pd.Series(
        np.where(selected_side == 1, long_entry_threshold, short_entry_threshold),
        index=df.index,
    )
    quality_ok = pd.Series(True, index=df.index)
    extra_side_margin = pd.Series(0.0, index=df.index)
    if np.isfinite(config.max_wait_regret):
        wait_aligned = prediction_index[
            [config.long_wait_regret_column, config.short_wait_regret_column]
        ].reindex(df["timestamp"])
        long_wait = wait_aligned[config.long_wait_regret_column].reset_index(drop=True).astype(float)
        short_wait = wait_aligned[config.short_wait_regret_column].reset_index(drop=True).astype(float)
        side_wait = pd.Series(np.where(selected_side == 1, long_wait, short_wait), index=df.index)
        quality_ok &= side_wait.notna() & (side_wait <= config.max_wait_regret)
    if config.min_entry_rank > 0:
        rank_aligned = prediction_index[
            [config.long_entry_rank_column, config.short_entry_rank_column]
        ].reindex(df["timestamp"])
        long_rank = rank_aligned[config.long_entry_rank_column].reset_index(drop=True).astype(float)
        short_rank = rank_aligned[config.short_entry_rank_column].reset_index(drop=True).astype(float)
        side_rank = pd.Series(np.where(selected_side == 1, long_rank, short_rank), index=df.index)
        quality_ok &= side_rank.notna() & (side_rank >= config.min_entry_rank)
    if np.isfinite(config.min_trade_quality):
        trade_quality_aligned = prediction_index[
            [config.long_trade_quality_column, config.short_trade_quality_column]
        ].reindex(df["timestamp"])
        long_trade_quality = (
            trade_quality_aligned[config.long_trade_quality_column].reset_index(drop=True).astype(float)
        )
        short_trade_quality = (
            trade_quality_aligned[config.short_trade_quality_column].reset_index(drop=True).astype(float)
        )
        side_trade_quality = pd.Series(
            np.where(selected_side == 1, long_trade_quality, short_trade_quality),
            index=df.index,
        )
        quality_ok &= side_trade_quality.notna() & (side_trade_quality >= config.min_trade_quality)
    if not np.isneginf(config.side_ev_penalty_replacement_min_margin):
        replacement_score_margin = selected_score - required_entry_threshold
        quality_ok &= (
            ~side_ev_penalty_admission_entry
            | (
                replacement_score_margin.notna()
                & (replacement_score_margin >= config.side_ev_penalty_replacement_min_margin)
            )
        )
    if config.min_side_confidence > 0:
        if long_side_confidence is None or short_side_confidence is None:
            side_confidence_aligned = prediction_index[
                [config.long_side_confidence_column, config.short_side_confidence_column]
            ].reindex(df["timestamp"])
            long_side_confidence = (
                side_confidence_aligned[config.long_side_confidence_column]
                .reset_index(drop=True)
                .astype(float)
            )
            short_side_confidence = (
                side_confidence_aligned[config.short_side_confidence_column]
                .reset_index(drop=True)
                .astype(float)
            )
        side_confidence = pd.Series(
            np.where(selected_side == 1, long_side_confidence, short_side_confidence),
            index=df.index,
        )
        quality_ok &= side_confidence.notna() & (side_confidence >= config.min_side_confidence)
    if config.require_profit_barrier:
        barrier_aligned = prediction_index[
            [config.long_profit_barrier_column, config.short_profit_barrier_column]
        ].reindex(df["timestamp"])
        long_barrier = barrier_aligned[config.long_profit_barrier_column].reset_index(drop=True).astype(float)
        short_barrier = barrier_aligned[config.short_profit_barrier_column].reset_index(drop=True).astype(float)
        side_barrier = pd.Series(
            np.where(selected_side == 1, long_barrier, short_barrier),
            index=df.index,
        )
        quality_ok &= side_barrier.notna() & (side_barrier >= config.profit_barrier_threshold)
    if long_holding_entry_ok is not None and short_holding_entry_ok is not None:
        side_holding_entry_ok = pd.Series(
            np.where(selected_side == 1, long_holding_entry_ok, short_holding_entry_ok),
            index=df.index,
        )
        quality_ok &= side_holding_entry_ok.astype(bool)
    for column, blocked_values in blocked_regime_columns(config):
        regime_aligned = prediction_index[[column]].reindex(df["timestamp"])
        regime_values = pd.Series(
            regime_aligned[column].reset_index(drop=True).astype("string").to_numpy(),
            index=df.index,
        )
        quality_ok &= regime_values.notna() & ~regime_values.isin(set(blocked_values))
    for side, conditions in parsed_side_block_rules(config):
        condition_mask = side_rule_condition_mask(prediction_index, df["timestamp"], df.index, conditions)
        quality_ok &= ~((selected_side == side) & condition_mask)
    for column, value, margin in parsed_extra_side_margin_rules(config):
        rule_aligned = prediction_index[[column]].reindex(df["timestamp"])
        rule_values = pd.Series(
            rule_aligned[column].reset_index(drop=True).astype("string").to_numpy(),
            index=df.index,
        )
        extra_side_margin += np.where((rule_values == value).fillna(False).to_numpy(), margin, 0.0)
    for side, conditions, margin in parsed_side_extra_margin_rules(config):
        condition_mask = side_rule_condition_mask(prediction_index, df["timestamp"], df.index, conditions)
        extra_side_margin += np.where(((selected_side == side) & condition_mask).to_numpy(), margin, 0.0)
    required_side_margin = config.side_margin + extra_side_margin

    if config.policy == "stateless_ev":
        enter = (
            valid_prediction
            & quality_ok
            & (selected_score > required_entry_threshold)
            & (side_gap >= required_side_margin)
        )
        signal = pd.Series(0, index=df.index, dtype="int8")
        signal.iloc[enter.to_numpy()] = selected_side.iloc[enter.to_numpy()]
        return signal

    current = 0
    planned_exit_timestamp: pd.Timestamp | None = None
    values: list[int] = []
    long_values = long_ev.tolist()
    short_values = short_ev.tolist()
    selected_side_values = selected_side.tolist()
    selected_score_values = selected_score.tolist()
    timestamps = df["timestamp"].reset_index(drop=True).tolist()
    long_holding_values = [] if long_holding is None else long_holding.tolist()
    short_holding_values = [] if short_holding is None else short_holding.tolist()
    long_time_exit_values = [] if long_time_exit is None else long_time_exit.tolist()
    short_time_exit_values = [] if short_time_exit is None else short_time_exit.tolist()
    long_loss_first_values = [] if long_loss_first is None else long_loss_first.tolist()
    short_loss_first_values = [] if short_loss_first is None else short_loss_first.tolist()
    quality_ok_values = quality_ok.tolist()
    required_side_margin_values = required_side_margin.tolist()
    required_entry_threshold_values = required_entry_threshold.tolist()
    for idx, has_prediction in enumerate(valid_prediction.tolist()):
        if not has_prediction:
            current = 0
            planned_exit_timestamp = None
            values.append(current)
            continue

        decision_timestamp = timestamps[idx]
        if config.policy in {"timed_ev", "fixed_horizon_ev"} and current != 0 and planned_exit_timestamp is not None:
            if decision_timestamp >= planned_exit_timestamp:
                current = 0
                planned_exit_timestamp = None
                values.append(current)
                continue
        if current != 0:
            dynamic_exit = False
            if np.isfinite(config.time_exit_exit_threshold):
                time_exit_value = (
                    long_time_exit_values[idx] if current == 1 else short_time_exit_values[idx]
                )
                dynamic_exit |= (
                    np.isfinite(time_exit_value)
                    and float(time_exit_value) >= config.time_exit_exit_threshold
                )
            if np.isfinite(config.loss_first_exit_threshold):
                loss_first_value = (
                    long_loss_first_values[idx] if current == 1 else short_loss_first_values[idx]
                )
                dynamic_exit |= (
                    np.isfinite(loss_first_value)
                    and float(loss_first_value) >= config.loss_first_exit_threshold
                )
            if dynamic_exit:
                current = 0
                planned_exit_timestamp = None
                values.append(current)
                continue

        long_value = float(long_values[idx])
        short_value = float(short_values[idx])
        candidate_side = int(selected_side_values[idx])
        candidate_score = float(selected_score_values[idx])
        candidate_gap = abs(long_value - short_value)
        candidate_entry_threshold = required_entry_threshold_values[idx]

        if current == 0:
            if (
                quality_ok_values[idx]
                and candidate_score > candidate_entry_threshold
                and candidate_gap >= required_side_margin_values[idx]
            ):
                current = candidate_side
                if config.policy in {"timed_ev", "fixed_horizon_ev"}:
                    holding_value = (
                        long_holding_values[idx] if current == 1 else short_holding_values[idx]
                    )
                    if not np.isfinite(holding_value):
                        holding_value = config.max_predicted_hold_minutes
                    holding_value = min(
                        config.max_predicted_hold_minutes,
                        max(config.min_predicted_hold_minutes, float(holding_value)),
                    )
                    execution_idx = min(idx + 1, len(timestamps) - 1)
                    planned_exit_timestamp = timestamps[execution_idx] + pd.Timedelta(
                        minutes=holding_value,
                    )
        else:
            current_score = long_value if current == 1 else short_value
            opposite_score = short_value if current == 1 else long_value
            opposite_entry_threshold = (
                short_entry_threshold if current == 1 else long_entry_threshold
            )
            should_exit = current_score < config.exit_threshold
            should_flip = (
                int(selected_side_values[idx]) == -current
                and float(selected_score_values[idx]) > opposite_entry_threshold
                and opposite_score > current_score + required_side_margin_values[idx]
            )
            if should_exit or should_flip:
                current = 0
                planned_exit_timestamp = None
        values.append(current)
    return pd.Series(values, index=df.index, dtype="int8")


def run_backtest(
    df: pd.DataFrame,
    desired_position: pd.Series,
    config: BacktestConfig,
    *,
    entry_context: pd.Series | None = None,
    entry_margin: pd.Series | None = None,
    context_drawdown_guard_loss_threshold: float = float("inf"),
    context_drawdown_guard_min_entry_margin: float = float("inf"),
    context_drawdown_guard_reset_monthly: bool = True,
) -> list[Trade]:
    if len(df) != len(desired_position):
        raise ValueError("df and desired_position must have the same length")
    context_drawdown_guard_enabled = np.isfinite(context_drawdown_guard_loss_threshold)
    if context_drawdown_guard_enabled:
        if context_drawdown_guard_loss_threshold <= 0:
            raise ValueError("context_drawdown_guard_loss_threshold must be positive or inf")
        if entry_context is None:
            raise ValueError("entry_context is required when context drawdown guard is enabled")
        if len(df) != len(entry_context):
            raise ValueError("df and entry_context must have the same length")
        if (
            context_drawdown_guard_min_entry_margin < 0
            and not np.isneginf(context_drawdown_guard_min_entry_margin)
        ):
            raise ValueError(
                "context_drawdown_guard_min_entry_margin must be non-negative, inf, or -inf"
            )
        if (
            np.isfinite(context_drawdown_guard_min_entry_margin)
            and entry_margin is None
        ):
            raise ValueError(
                "entry_margin is required when context drawdown guard min entry margin is finite"
            )
        if entry_margin is not None and len(df) != len(entry_margin):
            raise ValueError("df and entry_margin must have the same length")
    if config.execution_delay_bars < 0:
        raise ValueError("execution_delay_bars must be non-negative")
    if len(df) < 2:
        return []
    if len(df) < 2 + config.execution_delay_bars:
        return []

    timestamps = df["timestamp"].tolist()
    opens = df["open"].astype(float).tolist()
    signals = desired_position.fillna(0).astype("int8").tolist()
    if entry_context is None:
        context_values = [""] * len(df)
    else:
        context_values = entry_context.astype("string").fillna("__missing__").tolist()
    if entry_margin is None:
        entry_margin_values = [float("nan")] * len(df)
    else:
        entry_margin_values = entry_margin.astype(float).tolist()

    position: Position | None = None
    trades: list[Trade] = []
    context_pnl: dict[str, float] = {}
    blocked_contexts: set[str] = set()

    def context_drawdown_key(
        decision_timestamp: pd.Timestamp,
        desired: int,
        context_value: str,
    ) -> str:
        direction = DIRECTION_LABELS.get(desired, "flat")
        if context_drawdown_guard_reset_monthly:
            month = decision_timestamp.strftime("%Y-%m")
            return f"{month}|{direction}|{context_value}"
        return f"{direction}|{context_value}"

    for decision_idx in range(len(df) - 1 - config.execution_delay_bars):
        execution_idx = decision_idx + 1 + config.execution_delay_bars
        decision_timestamp = timestamps[decision_idx]
        execution_timestamp = timestamps[execution_idx]
        execution_open_price = opens[execution_idx]
        desired = int(signals[decision_idx])
        if desired not in (-1, 0, 1):
            desired = 0

        if position is not None:
            forced = execution_timestamp >= position.max_exit_timestamp
            signal_close = desired != position.direction
            if forced or signal_close:
                trade = close_position(
                    position=position,
                    exit_timestamp=execution_timestamp,
                    exit_price=apply_execution_cost(
                        execution_open_price,
                        position.direction,
                        is_entry=False,
                        config=config,
                    ),
                    exit_decision_timestamp=decision_timestamp,
                    exit_reason="forced_exit" if forced else "signal_close",
                    config=config,
                )
                trades.append(trade)
                if context_drawdown_guard_enabled and position.context_drawdown_key:
                    context_pnl[position.context_drawdown_key] = (
                        context_pnl.get(position.context_drawdown_key, 0.0)
                        + trade.adjusted_pnl
                    )
                    if (
                        context_pnl[position.context_drawdown_key]
                        <= -context_drawdown_guard_loss_threshold
                    ):
                        blocked_contexts.add(position.context_drawdown_key)
                position = None
                continue

        if position is None and config.evaluation_start <= execution_timestamp < config.evaluation_end:
            if desired in (-1, 1):
                drawdown_key = ""
                if context_drawdown_guard_enabled:
                    drawdown_key = context_drawdown_key(
                        decision_timestamp,
                        desired,
                        str(context_values[decision_idx]),
                    )
                    if drawdown_key in blocked_contexts:
                        if np.isposinf(context_drawdown_guard_min_entry_margin):
                            continue
                        if not np.isneginf(context_drawdown_guard_min_entry_margin):
                            current_entry_margin = entry_margin_values[decision_idx]
                            if (
                                not np.isfinite(current_entry_margin)
                                or current_entry_margin < context_drawdown_guard_min_entry_margin
                            ):
                                continue
                position = Position(
                    direction=desired,
                    entry_timestamp=execution_timestamp,
                    entry_price=apply_execution_cost(
                        execution_open_price,
                        desired,
                        is_entry=True,
                        config=config,
                    ),
                    entry_decision_timestamp=decision_timestamp,
                    max_exit_timestamp=execution_timestamp + config.max_holding,
                    context_drawdown_key=drawdown_key,
                )

    if position is not None:
        trades.append(
            close_position(
                position=position,
                exit_timestamp=timestamps[-1],
                exit_price=apply_execution_cost(
                    opens[-1],
                    position.direction,
                    is_entry=False,
                    config=config,
                ),
                exit_decision_timestamp=timestamps[-1],
                exit_reason="end_of_data",
                config=config,
            )
        )

    return [
        trade
        for trade in trades
        if config.evaluation_start <= trade.entry_timestamp < config.evaluation_end
    ]


def close_position(
    position: Position,
    exit_timestamp: pd.Timestamp,
    exit_price: float,
    exit_decision_timestamp: pd.Timestamp,
    exit_reason: str,
    config: BacktestConfig,
) -> Trade:
    raw = (exit_price - position.entry_price) * position.direction
    adjusted = adjusted_pnl(raw, config.profit_multiplier, config.loss_multiplier)
    holding_minutes = (exit_timestamp - position.entry_timestamp) / pd.Timedelta(minutes=1)
    return Trade(
        direction=DIRECTION_LABELS[position.direction],
        entry_timestamp=position.entry_timestamp,
        exit_timestamp=exit_timestamp,
        entry_price=position.entry_price,
        exit_price=exit_price,
        raw_pnl=float(raw),
        adjusted_pnl=float(adjusted),
        holding_minutes=float(holding_minutes),
        exit_reason=exit_reason,
        entry_decision_timestamp=position.entry_decision_timestamp,
        exit_decision_timestamp=exit_decision_timestamp,
    )


def trades_to_frame(trades: list[Trade]) -> pd.DataFrame:
    if not trades:
        return pd.DataFrame(columns=TRADE_COLUMNS)
    return pd.DataFrame([asdict(trade) for trade in trades], columns=TRADE_COLUMNS)


def equity_curve(trades: pd.DataFrame, start: pd.Timestamp) -> pd.DataFrame:
    rows = [{"timestamp": start, "equity": 0.0}]
    equity = 0.0
    if not trades.empty:
        ordered = trades.sort_values("exit_timestamp")
        for _, trade in ordered.iterrows():
            equity += float(trade["adjusted_pnl"])
            rows.append({"timestamp": trade["exit_timestamp"], "equity": equity})
    return pd.DataFrame(rows)


def summarize_trades(
    trades: pd.DataFrame,
    config: BacktestConfig,
    strategy: str,
) -> dict[str, object]:
    trade_count = int(len(trades))
    if trade_count == 0:
        return {
            "strategy": strategy,
            "period_start": config.evaluation_start.isoformat(),
            "period_end": config.evaluation_end.isoformat(),
            "total_adjusted_pnl": 0.0,
            "total_raw_pnl": 0.0,
            "trade_count": 0,
            "win_rate": 0.0,
            "avg_adjusted_pnl": 0.0,
            "profit_factor": None,
            "max_drawdown": 0.0,
            "exposure_hours": 0.0,
            "long_trade_count": 0,
            "short_trade_count": 0,
            "long_trade_share": 0.0,
            "short_trade_share": 0.0,
            "max_side_trade_share": 0.0,
            "long_adjusted_pnl": 0.0,
            "short_adjusted_pnl": 0.0,
            "long_raw_pnl": 0.0,
            "short_raw_pnl": 0.0,
            "long_win_rate": 0.0,
            "short_win_rate": 0.0,
            "forced_exit_count": 0,
            "avg_holding_minutes": 0.0,
            "median_holding_minutes": 0.0,
            "spread_points": config.spread_points,
            "slippage_points": config.slippage_points,
            "execution_delay_bars": config.execution_delay_bars,
        }

    adjusted = trades["adjusted_pnl"].astype(float)
    raw = trades["raw_pnl"].astype(float)
    gross_profit = float(adjusted[adjusted > 0].sum())
    gross_loss = float(-adjusted[adjusted < 0].sum())
    curve = equity_curve(trades, config.evaluation_start)
    running_max = curve["equity"].cummax()
    drawdowns = running_max - curve["equity"]
    profit_factor = None if gross_loss == 0 else gross_profit / gross_loss
    long_mask = trades["direction"] == "long"
    short_mask = trades["direction"] == "short"
    long_trade_count = int(long_mask.sum())
    short_trade_count = int(short_mask.sum())
    long_trade_share = long_trade_count / trade_count
    short_trade_share = short_trade_count / trade_count
    long_adjusted = adjusted[long_mask]
    short_adjusted = adjusted[short_mask]
    long_raw = raw[long_mask]
    short_raw = raw[short_mask]

    return {
        "strategy": strategy,
        "period_start": config.evaluation_start.isoformat(),
        "period_end": config.evaluation_end.isoformat(),
        "total_adjusted_pnl": float(adjusted.sum()),
        "total_raw_pnl": float(raw.sum()),
        "trade_count": trade_count,
        "win_rate": float((adjusted > 0).mean()),
        "avg_adjusted_pnl": float(adjusted.mean()),
        "profit_factor": None if profit_factor is None else float(profit_factor),
        "max_drawdown": float(drawdowns.max()),
        "exposure_hours": float(trades["holding_minutes"].sum() / 60),
        "long_trade_count": long_trade_count,
        "short_trade_count": short_trade_count,
        "long_trade_share": float(long_trade_share),
        "short_trade_share": float(short_trade_share),
        "max_side_trade_share": float(max(long_trade_share, short_trade_share)),
        "long_adjusted_pnl": float(long_adjusted.sum()),
        "short_adjusted_pnl": float(short_adjusted.sum()),
        "long_raw_pnl": float(long_raw.sum()),
        "short_raw_pnl": float(short_raw.sum()),
        "long_win_rate": float((long_adjusted > 0).mean()) if len(long_adjusted) else 0.0,
        "short_win_rate": float((short_adjusted > 0).mean()) if len(short_adjusted) else 0.0,
        "forced_exit_count": int((trades["exit_reason"] == "forced_exit").sum()),
        "avg_holding_minutes": float(trades["holding_minutes"].mean()),
        "median_holding_minutes": float(trades["holding_minutes"].median()),
        "spread_points": config.spread_points,
        "slippage_points": config.slippage_points,
        "execution_delay_bars": config.execution_delay_bars,
    }


def attach_trade_prediction_columns(
    trades: pd.DataFrame,
    predictions: pd.DataFrame,
    columns: Iterable[str],
) -> pd.DataFrame:
    output = trades.copy()
    selected_columns = [
        "decision_timestamp",
        *[column for column in columns if column in predictions.columns],
    ]
    selected_columns = list(dict.fromkeys(selected_columns))
    if trades.empty or len(selected_columns) == 1:
        for column in selected_columns:
            if column != "decision_timestamp" and column not in output.columns:
                output[column] = pd.Series(dtype="object")
        return output
    output["entry_decision_timestamp"] = pd.to_datetime(output["entry_decision_timestamp"], utc=True)
    context = predictions[selected_columns].copy()
    context["decision_timestamp"] = pd.to_datetime(context["decision_timestamp"], utc=True)
    return output.merge(
        context,
        left_on="entry_decision_timestamp",
        right_on="decision_timestamp",
        how="left",
        validate="many_to_one",
    )


def worst_group_pnl_diagnostics(
    trades: pd.DataFrame,
    predictions: pd.DataFrame,
    *,
    group_columns: list[str],
    context_columns: list[str],
    value_column: str,
    label_column: str,
    count_column: str,
    label_separator: str = ":",
) -> dict[str, object]:
    default = {
        value_column: 0.0,
        label_column: "",
        count_column: 0,
    }
    if trades.empty:
        return default
    missing_prediction_columns = [column for column in context_columns if column not in predictions.columns]
    if missing_prediction_columns:
        return {
            value_column: None,
            label_column: "",
            count_column: 0,
        }
    enriched = attach_trade_prediction_columns(trades, predictions, context_columns)
    if any(column not in enriched.columns for column in group_columns):
        return {
            value_column: None,
            label_column: "",
            count_column: 0,
        }
    grouped = (
        enriched.dropna(subset=group_columns)
        .groupby(group_columns, dropna=False, observed=True)
        .agg(
            total_adjusted_pnl=("adjusted_pnl", "sum"),
            trade_count=("adjusted_pnl", "size"),
        )
        .reset_index()
    )
    if grouped.empty:
        return default
    worst = grouped.sort_values(["total_adjusted_pnl", "trade_count"], ascending=[True, False]).iloc[0]
    worst_label = label_separator.join(str(worst[column]) for column in group_columns)
    return {
        value_column: float(worst["total_adjusted_pnl"]),
        label_column: worst_label,
        count_column: int(worst["trade_count"]),
    }


def direction_session_diagnostics(
    trades: pd.DataFrame,
    predictions: pd.DataFrame,
) -> dict[str, object]:
    return worst_group_pnl_diagnostics(
        trades,
        predictions,
        group_columns=["direction", "session_regime"],
        context_columns=["session_regime"],
        value_column="direction_session_adjusted_pnl_min",
        label_column="worst_direction_session",
        count_column="worst_direction_session_trade_count",
    )


def combined_regime_diagnostics(
    trades: pd.DataFrame,
    predictions: pd.DataFrame,
) -> dict[str, object]:
    combined = worst_group_pnl_diagnostics(
        trades,
        predictions,
        group_columns=["combined_regime"],
        context_columns=["combined_regime"],
        value_column="combined_regime_adjusted_pnl_min",
        label_column="worst_combined_regime",
        count_column="worst_combined_regime_trade_count",
    )
    direction_combined = worst_group_pnl_diagnostics(
        trades,
        predictions,
        group_columns=["direction", "combined_regime"],
        context_columns=["combined_regime"],
        value_column="direction_combined_regime_adjusted_pnl_min",
        label_column="worst_direction_combined_regime",
        count_column="worst_direction_combined_regime_trade_count",
    )
    return {**combined, **direction_combined}


def barrier_miss_summary(
    trades: pd.DataFrame,
    values: pd.Series,
    threshold: float,
    prefix: str,
) -> dict[str, object]:
    observed = values.notna()
    if not observed.any():
        return {
            f"{prefix}_profit_barrier_miss_rate": None,
            f"{prefix}_profit_barrier_miss_rate_smoothed": None,
            f"{prefix}_profit_barrier_miss_count": 0,
            f"{prefix}_profit_barrier_observed_count": 0,
            f"{prefix}_profit_barrier_miss_adjusted_pnl": 0.0,
        }
    miss = observed & (values.astype(float) < threshold)
    miss_count = int(miss.sum())
    observed_count = int(observed.sum())
    return {
        f"{prefix}_profit_barrier_miss_rate": float(miss_count / observed_count),
        f"{prefix}_profit_barrier_miss_rate_smoothed": float(
            (miss_count + 1.0) / (observed_count + 2.0)
        ),
        f"{prefix}_profit_barrier_miss_count": miss_count,
        f"{prefix}_profit_barrier_observed_count": observed_count,
        f"{prefix}_profit_barrier_miss_adjusted_pnl": float(
            trades.loc[miss, "adjusted_pnl"].astype(float).sum()
        ),
    }


def profit_barrier_diagnostics(
    trades: pd.DataFrame,
    predictions: pd.DataFrame,
    config: ModelPolicyConfig,
) -> dict[str, object]:
    if trades.empty:
        return {
            "predicted_profit_barrier_miss_rate": 0.0,
            "predicted_profit_barrier_miss_rate_smoothed": 0.0,
            "predicted_profit_barrier_miss_count": 0,
            "predicted_profit_barrier_observed_count": 0,
            "predicted_profit_barrier_miss_adjusted_pnl": 0.0,
            "actual_profit_barrier_miss_rate": 0.0,
            "actual_profit_barrier_miss_rate_smoothed": 0.0,
            "actual_profit_barrier_miss_count": 0,
            "actual_profit_barrier_observed_count": 0,
            "actual_profit_barrier_miss_adjusted_pnl": 0.0,
        }

    prediction_columns = [config.long_profit_barrier_column, config.short_profit_barrier_column]
    label_columns = PROFIT_BARRIER_LABEL_COLUMNS
    enriched = attach_trade_prediction_columns(trades, predictions, [*prediction_columns, *label_columns])
    direction = enriched["direction"].astype(str).str.lower()
    output: dict[str, object] = {}

    if all(column in enriched.columns for column in prediction_columns):
        predicted_values = side_values(
            enriched,
            direction,
            config.long_profit_barrier_column,
            config.short_profit_barrier_column,
        )
        output.update(
            barrier_miss_summary(
                enriched,
                predicted_values,
                threshold=config.profit_barrier_threshold,
                prefix="predicted",
            )
        )
    else:
        output.update(
            {
                "predicted_profit_barrier_miss_rate": None,
                "predicted_profit_barrier_miss_rate_smoothed": None,
                "predicted_profit_barrier_miss_count": 0,
                "predicted_profit_barrier_observed_count": 0,
                "predicted_profit_barrier_miss_adjusted_pnl": 0.0,
            }
        )

    if all(column in enriched.columns for column in label_columns):
        actual_values = side_values(
            enriched,
            direction,
            "long_profit_barrier_hit",
            "short_profit_barrier_hit",
        )
        output.update(
            barrier_miss_summary(
                enriched,
                actual_values,
                threshold=0.5,
                prefix="actual",
            )
        )
    else:
        output.update(
            {
                "actual_profit_barrier_miss_rate": None,
                "actual_profit_barrier_miss_rate_smoothed": None,
                "actual_profit_barrier_miss_count": 0,
                "actual_profit_barrier_observed_count": 0,
                "actual_profit_barrier_miss_adjusted_pnl": 0.0,
            }
        )

    return output


def empty_profit_barrier_calibration_diagnostics() -> dict[str, object]:
    output: dict[str, object] = {
        "profit_barrier_calibration_observed_count": 0,
        "profit_barrier_calibration_bucket_count": 0,
        "profit_barrier_calibration_overestimate_max": 0.0,
        "profit_barrier_calibration_overestimate_smoothed_max": 0.0,
        "profit_barrier_calibration_abs_error_max": 0.0,
        "worst_profit_barrier_calibration_bucket": "",
        "worst_profit_barrier_calibration_bucket_count": 0,
        "worst_profit_barrier_calibration_predicted_mean": 0.0,
        "worst_profit_barrier_calibration_actual_hit_rate": 0.0,
        "worst_profit_barrier_calibration_actual_hit_rate_smoothed": 0.0,
        "worst_profit_barrier_calibration_overestimate": 0.0,
        "worst_profit_barrier_calibration_overestimate_smoothed": 0.0,
    }
    for lower, upper in PROFIT_BARRIER_CALIBRATION_BUCKETS:
        prefix = f"profit_barrier_calibration_{probability_bucket_key(lower, upper)}"
        output[f"{prefix}_count"] = 0
        output[f"{prefix}_predicted_mean"] = 0.0
        output[f"{prefix}_actual_hit_rate"] = 0.0
        output[f"{prefix}_actual_hit_rate_smoothed"] = 0.0
        output[f"{prefix}_overestimate"] = 0.0
        output[f"{prefix}_overestimate_smoothed"] = 0.0
    return output


def profit_barrier_calibration_diagnostics(
    trades: pd.DataFrame,
    predictions: pd.DataFrame,
    config: ModelPolicyConfig,
) -> dict[str, object]:
    output = empty_profit_barrier_calibration_diagnostics()
    if trades.empty:
        return output

    prediction_columns = [config.long_profit_barrier_column, config.short_profit_barrier_column]
    label_columns = PROFIT_BARRIER_LABEL_COLUMNS
    enriched = attach_trade_prediction_columns(trades, predictions, [*prediction_columns, *label_columns])
    if not all(column in enriched.columns for column in [*prediction_columns, *label_columns]):
        return output

    direction = enriched["direction"].astype(str).str.lower()
    predicted_values = side_values(
        enriched,
        direction,
        config.long_profit_barrier_column,
        config.short_profit_barrier_column,
    ).astype(float)
    actual_values = side_values(
        enriched,
        direction,
        "long_profit_barrier_hit",
        "short_profit_barrier_hit",
    ).astype(float)
    observed = predicted_values.notna() & actual_values.notna()
    output["profit_barrier_calibration_observed_count"] = int(observed.sum())
    if not observed.any():
        return output

    actual_hits = (actual_values >= 0.5).astype(float)
    bucket_rows: list[dict[str, object]] = []
    for lower, upper in PROFIT_BARRIER_CALIBRATION_BUCKETS:
        bucket_key = probability_bucket_key(lower, upper)
        bucket_label = probability_bucket_label(lower, upper)
        if lower == 0.0:
            in_bucket = observed & (predicted_values >= lower) & (predicted_values <= upper)
        else:
            in_bucket = observed & (predicted_values > lower) & (predicted_values <= upper)
        count = int(in_bucket.sum())
        prefix = f"profit_barrier_calibration_{bucket_key}"
        output[f"{prefix}_count"] = count
        if count == 0:
            bucket_rows.append(
                {
                    "bucket": bucket_label,
                    "count": 0,
                    "predicted_mean": 0.0,
                    "actual_hit_rate": 0.0,
                    "actual_hit_rate_smoothed": 0.0,
                    "overestimate": 0.0,
                    "overestimate_smoothed": 0.0,
                    "abs_error": 0.0,
                }
            )
            continue
        predicted_mean = float(predicted_values.loc[in_bucket].mean())
        actual_hit_rate = float(actual_hits.loc[in_bucket].mean())
        hit_count = float(actual_hits.loc[in_bucket].sum())
        actual_hit_rate_smoothed = float((hit_count + 1.0) / (count + 2.0))
        overestimate = max(0.0, predicted_mean - actual_hit_rate)
        overestimate_smoothed = max(0.0, predicted_mean - actual_hit_rate_smoothed)
        abs_error = abs(predicted_mean - actual_hit_rate)
        output[f"{prefix}_predicted_mean"] = predicted_mean
        output[f"{prefix}_actual_hit_rate"] = actual_hit_rate
        output[f"{prefix}_actual_hit_rate_smoothed"] = actual_hit_rate_smoothed
        output[f"{prefix}_overestimate"] = overestimate
        output[f"{prefix}_overestimate_smoothed"] = overestimate_smoothed
        bucket_rows.append(
            {
                "bucket": bucket_label,
                "count": count,
                "predicted_mean": predicted_mean,
                "actual_hit_rate": actual_hit_rate,
                "actual_hit_rate_smoothed": actual_hit_rate_smoothed,
                "overestimate": overestimate,
                "overestimate_smoothed": overestimate_smoothed,
                "abs_error": abs_error,
            }
        )

    non_empty_buckets = [row for row in bucket_rows if row["count"] > 0]
    output["profit_barrier_calibration_bucket_count"] = int(len(non_empty_buckets))
    output["profit_barrier_calibration_overestimate_max"] = float(
        max((row["overestimate"] for row in non_empty_buckets), default=0.0)
    )
    output["profit_barrier_calibration_overestimate_smoothed_max"] = float(
        max((row["overestimate_smoothed"] for row in non_empty_buckets), default=0.0)
    )
    output["profit_barrier_calibration_abs_error_max"] = float(
        max((row["abs_error"] for row in non_empty_buckets), default=0.0)
    )
    if non_empty_buckets:
        worst = sorted(
            non_empty_buckets,
            key=lambda row: (row["overestimate"], row["abs_error"], row["count"]),
            reverse=True,
        )[0]
        output["worst_profit_barrier_calibration_bucket"] = str(worst["bucket"])
        output["worst_profit_barrier_calibration_bucket_count"] = int(worst["count"])
        output["worst_profit_barrier_calibration_predicted_mean"] = float(
            worst["predicted_mean"]
        )
        output["worst_profit_barrier_calibration_actual_hit_rate"] = float(
            worst["actual_hit_rate"]
        )
        output["worst_profit_barrier_calibration_actual_hit_rate_smoothed"] = float(
            worst["actual_hit_rate_smoothed"]
        )
        output["worst_profit_barrier_calibration_overestimate"] = float(worst["overestimate"])
        output["worst_profit_barrier_calibration_overestimate_smoothed"] = float(
            worst["overestimate_smoothed"]
        )
    return output


def json_default(value: object) -> str:
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, np.bool_):
        return bool(value)
    raise TypeError(f"cannot serialize {type(value).__name__}")


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


def write_result(
    run_dir: Path,
    metrics: dict[str, object],
    trades: pd.DataFrame,
    curve: pd.DataFrame,
    strategy_config: StrategyConfig | None,
    backtest_config: BacktestConfig,
    model_policy_config: ModelPolicyConfig | None = None,
) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    trades.to_csv(run_dir / "trades.csv", index=False)
    curve.to_csv(run_dir / "equity_curve.csv", index=False)
    with (run_dir / "metrics.json").open("w", encoding="utf-8") as handle:
        json.dump(metrics, handle, ensure_ascii=False, indent=2, default=json_default)
    metadata = {
        "backtest_config": {
            "evaluation_start": backtest_config.evaluation_start.isoformat(),
            "evaluation_end": backtest_config.evaluation_end.isoformat(),
            "max_holding": str(backtest_config.max_holding),
            "profit_multiplier": backtest_config.profit_multiplier,
            "loss_multiplier": backtest_config.loss_multiplier,
            "spread_points": backtest_config.spread_points,
            "slippage_points": backtest_config.slippage_points,
            "execution_delay_bars": backtest_config.execution_delay_bars,
        },
    }
    if strategy_config is not None:
        metadata["strategy_config"] = asdict(strategy_config)
    if model_policy_config is not None:
        model_metadata = asdict(model_policy_config)
        model_metadata["predictions"] = str(model_policy_config.predictions)
        metadata["model_policy_config"] = model_metadata
    with (run_dir / "config.json").open("w", encoding="utf-8") as handle:
        json.dump(metadata, handle, ensure_ascii=False, indent=2)


def print_metrics(metrics: dict[str, object]) -> None:
    print(f"strategy: {metrics['strategy']}")
    print(f"period: {metrics['period_start']} -> {metrics['period_end']}")
    print(f"total_adjusted_pnl: {metrics['total_adjusted_pnl']:.6f}")
    print(f"total_raw_pnl: {metrics['total_raw_pnl']:.6f}")
    print(f"trade_count: {metrics['trade_count']}")
    print(f"win_rate: {metrics['win_rate']:.4f}")
    profit_factor = metrics["profit_factor"]
    if profit_factor is None:
        print("profit_factor: null")
    else:
        print(f"profit_factor: {profit_factor:.4f}")
    print(f"max_drawdown: {metrics['max_drawdown']:.6f}")
    print(f"forced_exit_count: {metrics['forced_exit_count']}")


def parse_csv_floats(value: str) -> list[float]:
    values = [float(part.strip()) for part in value.split(",") if part.strip()]
    if not values:
        raise argparse.ArgumentTypeError("at least one numeric value is required")
    return values


def default_min_valid_predicted_hold_minutes(
    long_holding_column: str,
    short_holding_column: str,
) -> float:
    holding_columns = (long_holding_column, short_holding_column)
    if any(column.startswith("pred_mlp_") for column in holding_columns):
        return DEFAULT_MLP_MIN_VALID_HOLD_MINUTES
    return -float("inf")


def resolve_min_valid_predicted_hold_minutes(
    value: float | None,
    long_holding_column: str,
    short_holding_column: str,
) -> float:
    if value is not None:
        return value
    return default_min_valid_predicted_hold_minutes(
        long_holding_column,
        short_holding_column,
    )


def parse_min_valid_predicted_hold_minutes_values(
    value: str,
    long_holding_column: str,
    short_holding_column: str,
) -> list[float]:
    if value.strip().lower() == "auto":
        return [
            default_min_valid_predicted_hold_minutes(
                long_holding_column,
                short_holding_column,
            )
        ]
    return parse_csv_floats(value)


def parse_csv_strings(value: str) -> list[str]:
    values = [part.strip() for part in value.split(",") if part.strip()]
    if not values:
        raise argparse.ArgumentTypeError("at least one value is required")
    return values


def parse_csv_float_tuple(value: str) -> tuple[float, ...]:
    return tuple(parse_csv_floats(value))


def parse_csv_string_tuple(value: str) -> tuple[str, ...]:
    return tuple(parse_csv_strings(value))


def validate_fixed_horizon_config(config: ModelPolicyConfig) -> None:
    if config.fixed_horizon_score_mode not in FIXED_HORIZON_SCORE_MODES:
        raise ValueError(f"unknown fixed horizon score mode: {config.fixed_horizon_score_mode}")
    lengths = {
        "fixed_horizon_minutes": len(config.fixed_horizon_minutes),
        "long_fixed_horizon_columns": len(config.long_fixed_horizon_columns),
        "short_fixed_horizon_columns": len(config.short_fixed_horizon_columns),
    }
    if len(set(lengths.values())) != 1:
        detail = ", ".join(f"{key}={value}" for key, value in lengths.items())
        raise ValueError(f"fixed horizon config lengths must match: {detail}")
    if not config.fixed_horizon_minutes:
        raise ValueError("at least one fixed horizon must be configured")
    if any(minutes <= 0 for minutes in config.fixed_horizon_minutes):
        raise ValueError("fixed horizon minutes must be positive")


def parse_extra_side_margin_rule(rule: str) -> tuple[str, str, float]:
    try:
        condition, margin_text = rule.split(":", maxsplit=1)
        column, value = condition.split("=", maxsplit=1)
    except ValueError as exc:
        raise ValueError(
            f"extra side margin rule must use column=value:margin syntax: {rule}"
        ) from exc
    column = column.strip()
    value = value.strip()
    if not column or not value:
        raise ValueError(f"extra side margin rule must include column and value: {rule}")
    margin = float(margin_text.strip())
    if margin < 0:
        raise ValueError("extra side margin must be non-negative")
    return column, value, margin


def parse_side_name(value: str) -> int:
    normalized = value.strip().lower()
    if normalized == "long":
        return 1
    if normalized == "short":
        return -1
    raise ValueError(f"side must be long or short: {value}")


def parse_condition_parts(condition_text: str, rule: str) -> tuple[tuple[str, str], ...]:
    conditions: list[tuple[str, str]] = []
    for part in condition_text.split("+"):
        part = part.strip()
        if not part:
            continue
        try:
            column, value = part.split("=", maxsplit=1)
        except ValueError as exc:
            raise ValueError(f"side rule condition must use column=value syntax: {rule}") from exc
        column = column.strip()
        value = value.strip()
        if not column or not value:
            raise ValueError(f"side rule condition must include column and value: {rule}")
        conditions.append((column, value))
    if not conditions:
        raise ValueError(f"side rule must include at least one condition: {rule}")
    return tuple(conditions)


def parse_side_block_rule(rule: str) -> tuple[int, tuple[tuple[str, str], ...]]:
    try:
        side_text, condition_text = rule.split(":", maxsplit=1)
    except ValueError as exc:
        raise ValueError(f"side block rule must use side:column=value+... syntax: {rule}") from exc
    return parse_side_name(side_text), parse_condition_parts(condition_text, rule)


def parse_side_extra_margin_rule(rule: str) -> tuple[int, tuple[tuple[str, str], ...], float]:
    try:
        side_and_conditions, margin_text = rule.rsplit(":", maxsplit=1)
        side_text, condition_text = side_and_conditions.split(":", maxsplit=1)
    except ValueError as exc:
        raise ValueError(
            f"side extra margin rule must use side:column=value+...:margin syntax: {rule}"
        ) from exc
    margin = float(margin_text.strip())
    if margin < 0:
        raise ValueError("side extra margin must be non-negative")
    return parse_side_name(side_text), parse_condition_parts(condition_text, rule), margin


def parse_side_ev_penalty_rule(rule: str) -> tuple[int, tuple[tuple[str, str], ...], float]:
    try:
        side_and_conditions, penalty_text = rule.rsplit(":", maxsplit=1)
        side_text, condition_text = side_and_conditions.split(":", maxsplit=1)
    except ValueError as exc:
        raise ValueError(
            f"side EV penalty rule must use side:column=value+...:penalty syntax: {rule}"
        ) from exc
    penalty = float(penalty_text.strip())
    if penalty < 0:
        raise ValueError("side EV penalty must be non-negative")
    return parse_side_name(side_text), parse_condition_parts(condition_text, rule), penalty


def parse_side_confidence_penalty_rule(rule: str) -> tuple[tuple[tuple[str, str], ...], float]:
    try:
        condition_text, penalty_text = rule.rsplit(":", maxsplit=1)
    except ValueError as exc:
        raise ValueError(
            f"side confidence penalty rule must use column=value+...:penalty syntax: {rule}"
        ) from exc
    penalty = float(penalty_text.strip())
    if penalty < 0:
        raise ValueError("side confidence penalty rule penalty must be non-negative")
    return parse_condition_parts(condition_text, rule), penalty


def parsed_extra_side_margin_rules(config: ModelPolicyConfig) -> list[tuple[str, str, float]]:
    return [parse_extra_side_margin_rule(rule) for rule in config.extra_side_margin_rules]


def parsed_side_block_rules(config: ModelPolicyConfig) -> list[tuple[int, tuple[tuple[str, str], ...]]]:
    return [parse_side_block_rule(rule) for rule in config.side_block_rules]


def parsed_side_extra_margin_rules(
    config: ModelPolicyConfig,
) -> list[tuple[int, tuple[tuple[str, str], ...], float]]:
    return [parse_side_extra_margin_rule(rule) for rule in config.side_extra_margin_rules]


def parsed_side_ev_penalty_rules(
    config: ModelPolicyConfig,
) -> list[tuple[int, tuple[tuple[str, str], ...], float]]:
    return [parse_side_ev_penalty_rule(rule) for rule in config.side_ev_penalty_rules]


def parsed_side_confidence_penalty_rules(
    config: ModelPolicyConfig,
) -> list[tuple[tuple[tuple[str, str], ...], float]]:
    return [parse_side_confidence_penalty_rule(rule) for rule in config.side_confidence_penalty_rules]


def parsed_side_confidence_overfit_penalty_rules(
    config: ModelPolicyConfig,
) -> list[tuple[tuple[tuple[str, str], ...], float]]:
    return [
        parse_side_confidence_penalty_rule(rule)
        for rule in config.side_confidence_overfit_penalty_rules
    ]


def extra_side_margin_rule_columns(config: ModelPolicyConfig) -> list[str]:
    return list(dict.fromkeys(column for column, _, _ in parsed_extra_side_margin_rules(config)))


def side_rule_columns(config: ModelPolicyConfig) -> list[str]:
    columns: list[str] = []
    for _, conditions in parsed_side_block_rules(config):
        columns.extend(column for column, _ in conditions)
    for _, conditions, _ in parsed_side_extra_margin_rules(config):
        columns.extend(column for column, _ in conditions)
    for _, conditions, _ in parsed_side_ev_penalty_rules(config):
        columns.extend(column for column, _ in conditions)
    for conditions, _ in parsed_side_confidence_penalty_rules(config):
        columns.extend(column for column, _ in conditions)
    for conditions, _ in parsed_side_confidence_overfit_penalty_rules(config):
        columns.extend(column for column, _ in conditions)
    return list(dict.fromkeys(columns))


def context_drawdown_guard_enabled(config: ModelPolicyConfig) -> bool:
    return np.isfinite(config.context_drawdown_guard_loss_threshold)


def model_policy_entry_context(
    df: pd.DataFrame,
    predictions: pd.DataFrame,
    config: ModelPolicyConfig,
) -> pd.Series | None:
    if not context_drawdown_guard_enabled(config):
        return None
    columns = list(config.context_drawdown_guard_context_columns)
    if not columns:
        return pd.Series("__all__", index=df.index, dtype="string")
    prediction_index = predictions.set_index("decision_timestamp")
    missing = sorted(set(columns) - set(prediction_index.columns))
    if missing:
        raise ValueError(
            "context drawdown guard missing prediction columns: "
            + ", ".join(missing)
        )
    aligned = prediction_index[columns].reindex(df["timestamp"]).reset_index(drop=True)
    parts: list[pd.Series] = []
    for column in columns:
        values = aligned[column].astype("string").fillna("__missing__")
        parts.append(column + "=" + values)
    output = parts[0]
    for part in parts[1:]:
        output = output + "|" + part
    return pd.Series(output.to_numpy(), index=df.index, dtype="string")


def model_policy_entry_margin(
    df: pd.DataFrame,
    predictions: pd.DataFrame,
    config: ModelPolicyConfig,
) -> pd.Series:
    prediction_index = predictions.set_index("decision_timestamp")
    aligned = prediction_index[[config.long_column, config.short_column]].reindex(df["timestamp"])
    long_ev = aligned[config.long_column].reset_index(drop=True).astype(float)
    short_ev = aligned[config.short_column].reset_index(drop=True).astype(float)

    if config.policy == "fixed_horizon_ev":
        validate_fixed_horizon_config(config)
        long_fixed_aligned = prediction_index[list(config.long_fixed_horizon_columns)].reindex(
            df["timestamp"]
        )
        short_fixed_aligned = prediction_index[list(config.short_fixed_horizon_columns)].reindex(
            df["timestamp"]
        )
        long_ev, _ = fixed_horizon_scores(
            long_fixed_aligned.reset_index(drop=True),
            config.fixed_horizon_minutes,
            config.fixed_horizon_score_mode,
        )
        short_ev, _ = fixed_horizon_scores(
            short_fixed_aligned.reset_index(drop=True),
            config.fixed_horizon_minutes,
            config.fixed_horizon_score_mode,
        )
    if config.risk_penalty > 0:
        risk_aligned = prediction_index[[config.long_risk_column, config.short_risk_column]].reindex(
            df["timestamp"]
        )
        long_risk = risk_aligned[config.long_risk_column].reset_index(drop=True).astype(float)
        short_risk = risk_aligned[config.short_risk_column].reset_index(drop=True).astype(float)
        long_ev = long_ev - config.risk_penalty * (-long_risk).clip(lower=0)
        short_ev = short_ev - config.risk_penalty * (-short_risk).clip(lower=0)
    if config.profit_barrier_miss_penalty > 0:
        barrier_aligned = prediction_index[
            [config.long_profit_barrier_column, config.short_profit_barrier_column]
        ].reindex(df["timestamp"])
        long_barrier = barrier_aligned[config.long_profit_barrier_column].reset_index(drop=True).astype(float)
        short_barrier = barrier_aligned[config.short_profit_barrier_column].reset_index(drop=True).astype(float)
        long_ev = long_ev - config.profit_barrier_miss_penalty * (1.0 - long_barrier).clip(0.0, 1.0)
        short_ev = short_ev - config.profit_barrier_miss_penalty * (1.0 - short_barrier).clip(0.0, 1.0)
    if config.time_exit_penalty > 0:
        time_exit_aligned = prediction_index[
            [config.long_time_exit_column, config.short_time_exit_column]
        ].reindex(df["timestamp"])
        long_time_exit = time_exit_aligned[config.long_time_exit_column].reset_index(drop=True).astype(float)
        short_time_exit = time_exit_aligned[config.short_time_exit_column].reset_index(drop=True).astype(float)
        long_ev = long_ev - config.time_exit_penalty * long_time_exit.clip(0.0, 1.0)
        short_ev = short_ev - config.time_exit_penalty * short_time_exit.clip(0.0, 1.0)
    if config.loss_first_penalty > 0:
        loss_first_aligned = prediction_index[
            [config.long_loss_first_column, config.short_loss_first_column]
        ].reindex(df["timestamp"])
        long_loss_first = loss_first_aligned[config.long_loss_first_column].reset_index(drop=True).astype(float)
        short_loss_first = loss_first_aligned[config.short_loss_first_column].reset_index(drop=True).astype(float)
        long_ev = long_ev - config.loss_first_penalty * long_loss_first.clip(0.0, 1.0)
        short_ev = short_ev - config.loss_first_penalty * short_loss_first.clip(0.0, 1.0)
    for side, conditions, penalty in parsed_side_ev_penalty_rules(config):
        condition_mask = side_rule_condition_mask(
            prediction_index,
            df["timestamp"],
            df.index,
            conditions,
        )
        side_penalty = pd.Series(
            np.where(condition_mask.to_numpy(), penalty, 0.0),
            index=df.index,
        )
        if side == 1:
            long_ev = long_ev - side_penalty
        else:
            short_ev = short_ev - side_penalty
    if config.side_confidence_penalty > 0 or config.side_confidence_penalty_rules:
        side_confidence_aligned = prediction_index[
            [config.long_side_confidence_column, config.short_side_confidence_column]
        ].reindex(df["timestamp"])
        long_side_confidence = (
            side_confidence_aligned[config.long_side_confidence_column]
            .reset_index(drop=True)
            .astype(float)
        )
        short_side_confidence = (
            side_confidence_aligned[config.short_side_confidence_column]
            .reset_index(drop=True)
            .astype(float)
        )
        side_confidence_penalty = pd.Series(
            config.side_confidence_penalty,
            index=df.index,
            dtype="float64",
        )
        for conditions, penalty in parsed_side_confidence_penalty_rules(config):
            condition_mask = side_rule_condition_mask(
                prediction_index,
                df["timestamp"],
                df.index,
                conditions,
            )
            side_confidence_penalty += np.where(condition_mask.to_numpy(), penalty, 0.0)
        long_ev = long_ev - side_confidence_penalty * (1.0 - long_side_confidence).clip(0.0, 1.0)
        short_ev = short_ev - side_confidence_penalty * (1.0 - short_side_confidence).clip(0.0, 1.0)
    if config.side_confidence_overfit_penalty_rules:
        side_confidence_aligned = prediction_index[
            [config.long_side_confidence_column, config.short_side_confidence_column]
        ].reindex(df["timestamp"])
        long_side_confidence = (
            side_confidence_aligned[config.long_side_confidence_column]
            .reset_index(drop=True)
            .astype(float)
        )
        short_side_confidence = (
            side_confidence_aligned[config.short_side_confidence_column]
            .reset_index(drop=True)
            .astype(float)
        )
        side_confidence_overfit_penalty = pd.Series(0.0, index=df.index, dtype="float64")
        for conditions, penalty in parsed_side_confidence_overfit_penalty_rules(config):
            condition_mask = side_rule_condition_mask(
                prediction_index,
                df["timestamp"],
                df.index,
                conditions,
            )
            side_confidence_overfit_penalty += np.where(condition_mask.to_numpy(), penalty, 0.0)
        long_ev = long_ev - side_confidence_overfit_penalty * long_side_confidence.clip(0.0, 1.0)
        short_ev = short_ev - side_confidence_overfit_penalty * short_side_confidence.clip(0.0, 1.0)

    valid_prediction = long_ev.notna() & short_ev.notna()
    selected_side = pd.Series(0, index=df.index, dtype="int8")
    selected_side.iloc[(valid_prediction & (long_ev >= short_ev)).to_numpy()] = 1
    selected_side.iloc[(valid_prediction & (long_ev < short_ev)).to_numpy()] = -1
    selected_score = pd.Series(
        np.where(selected_side == 1, long_ev, short_ev),
        index=df.index,
    )
    if secondary_score_tie_break_enabled(config):
        secondary_aligned = prediction_index[
            [config.long_secondary_score_column, config.short_secondary_score_column]
        ].reindex(df["timestamp"])
        long_secondary_score = (
            secondary_aligned[config.long_secondary_score_column]
            .reset_index(drop=True)
            .astype(float)
        )
        short_secondary_score = (
            secondary_aligned[config.short_secondary_score_column]
            .reset_index(drop=True)
            .astype(float)
        )
        secondary_valid = long_secondary_score.notna() & short_secondary_score.notna()
        secondary_valid &= np.isfinite(long_secondary_score) & np.isfinite(
            short_secondary_score
        )
        side_gap = (long_ev - short_ev).abs()
        near_tie = valid_prediction & secondary_valid & (
            side_gap <= config.secondary_score_tie_margin
        )
        secondary_prefers_long = long_secondary_score >= short_secondary_score
        selected_side.iloc[(near_tie & secondary_prefers_long).to_numpy()] = 1
        selected_side.iloc[(near_tie & ~secondary_prefers_long).to_numpy()] = -1
        selected_score = pd.Series(
            np.where(selected_side == 1, long_ev, short_ev),
            index=df.index,
        )

    long_entry_threshold = config.entry_threshold + config.long_entry_threshold_offset
    short_entry_threshold = config.entry_threshold + config.short_entry_threshold_offset
    selected_threshold = pd.Series(
        np.where(selected_side == 1, long_entry_threshold, short_entry_threshold),
        index=df.index,
    )
    margin = selected_score - selected_threshold
    return margin.where(valid_prediction)


def parse_optional_csv_strings(value: str | None) -> tuple[str, ...]:
    if value is None:
        return ()
    return tuple(dict.fromkeys(part.strip() for part in value.split(",") if part.strip()))


def parse_optional_rule_sets(
    value: str | None,
    fallback: tuple[str, ...] = (),
) -> list[tuple[str, ...]]:
    if value is None:
        return [fallback]
    rule_sets: list[tuple[str, ...]] = []
    for part in value.split(";"):
        text = part.strip()
        if not text or text.lower() in {"none", "empty", "-"}:
            rules: tuple[str, ...] = ()
        else:
            rules = parse_optional_csv_strings(text)
        if rules not in rule_sets:
            rule_sets.append(rules)
    if not rule_sets:
        return [()]
    return rule_sets


def regime_values_to_string(values: Iterable[str]) -> str:
    return ",".join(values)


def flatten_rule_sets(rule_sets: Iterable[Iterable[str]]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(rule for rule_set in rule_sets for rule in rule_set))


def model_policy_sweep_key_defaults() -> dict[str, object]:
    defaults = asdict(ModelPolicyConfig(predictions=Path("")))
    return {column: defaults[column] for column in SWEEP_KEY_COLUMNS}


def stringify_sweep_key_value(value: object) -> str:
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    if isinstance(value, str):
        return value
    if isinstance(value, Iterable) and not isinstance(value, (bytes, bytearray, dict)):
        return regime_values_to_string(str(part) for part in value)
    return str(value)


def normalize_sweep_key_columns(frame: pd.DataFrame) -> pd.DataFrame:
    output = frame.copy()
    defaults = model_policy_sweep_key_defaults()
    for column, default in defaults.items():
        if column not in output.columns:
            output[column] = stringify_sweep_key_value(default)

    numeric_columns = [
        "entry_threshold",
        "long_entry_threshold_offset",
        "short_entry_threshold_offset",
        "exit_threshold",
        "side_margin",
        "risk_penalty",
        "min_predicted_hold_minutes",
        "max_predicted_hold_minutes",
        "min_valid_predicted_hold_minutes",
        "max_wait_regret",
        "min_entry_rank",
        "min_trade_quality",
        "profit_barrier_miss_penalty",
        "time_exit_penalty",
        "loss_first_penalty",
        "time_exit_holding_shrink",
        "loss_first_holding_shrink",
        "holding_shortening_threshold",
        "holding_shortening_cap_minutes",
        "time_exit_exit_threshold",
        "loss_first_exit_threshold",
        "side_confidence_penalty",
        "min_side_confidence",
        "profit_barrier_threshold",
        "secondary_score_tie_margin",
        "side_ev_penalty_replacement_min_margin",
        "context_drawdown_guard_loss_threshold",
        "context_drawdown_guard_min_entry_margin",
    ]
    for column in numeric_columns:
        output[column] = pd.to_numeric(output[column], errors="raise")

    if output["require_profit_barrier"].dtype == object:
        output["require_profit_barrier"] = output["require_profit_barrier"].map(
            lambda value: str(value).strip().lower() in {"1", "true", "yes", "y"}
        )
    else:
        output["require_profit_barrier"] = output["require_profit_barrier"].astype(bool)
    if output["context_drawdown_guard_reset_monthly"].dtype == object:
        output["context_drawdown_guard_reset_monthly"] = output[
            "context_drawdown_guard_reset_monthly"
        ].map(lambda value: str(value).strip().lower() in {"1", "true", "yes", "y"})
    else:
        output["context_drawdown_guard_reset_monthly"] = output[
            "context_drawdown_guard_reset_monthly"
        ].astype(bool)

    string_columns = [
        "policy",
        "fixed_horizon_score_mode",
        "long_holding_fallback_column",
        "short_holding_fallback_column",
        "long_secondary_score_column",
        "short_secondary_score_column",
        "side_confidence_penalty_rules",
        "side_confidence_overfit_penalty_rules",
        "side_ev_penalty_rules",
        "extra_side_margin_rules",
        "side_extra_margin_rules",
        "side_block_rules",
        "context_drawdown_guard_context_columns",
        "block_trend_regimes",
        "block_volatility_regimes",
        "block_session_regimes",
        "block_gap_regimes",
        "block_combined_regimes",
    ]
    for column in string_columns:
        output[column] = output[column].map(stringify_sweep_key_value).fillna("")
    return output


def regime_blocks_from_args(args: argparse.Namespace) -> dict[str, tuple[str, ...]]:
    return {
        field: parse_optional_csv_strings(getattr(args, field))
        for field, _ in REGIME_BLOCK_FIELDS
    }


def regime_block_metric_columns(config: ModelPolicyConfig) -> dict[str, str]:
    return {
        field: regime_values_to_string(getattr(config, field))
        for field, _ in REGIME_BLOCK_FIELDS
    }


def parse_csv_bools(value: str) -> list[bool]:
    values: list[bool] = []
    for part in [part.strip().lower() for part in value.split(",") if part.strip()]:
        if part in {"1", "true", "yes", "y"}:
            values.append(True)
        elif part in {"0", "false", "no", "n"}:
            values.append(False)
        else:
            raise argparse.ArgumentTypeError("boolean values must be true/false")
    if not values:
        raise argparse.ArgumentTypeError("at least one boolean value is required")
    return values


def parse_csv_paths(value: str) -> list[Path]:
    values = [Path(part.strip()) for part in value.split(",") if part.strip()]
    if not values:
        raise argparse.ArgumentTypeError("at least one path is required")
    return values


def read_trades_csv(path: Path) -> pd.DataFrame:
    trades = pd.read_csv(path)
    missing = sorted(set(TRADE_COLUMNS) - set(trades.columns))
    if missing:
        raise ValueError(f"{path} is missing columns: {', '.join(missing)}")
    for column in ["entry_timestamp", "exit_timestamp", "entry_decision_timestamp", "exit_decision_timestamp"]:
        trades[column] = pd.to_datetime(trades[column], utc=True)
    return trades


def prepare_analysis_predictions(
    predictions: pd.DataFrame,
    long_column: str,
    short_column: str,
    extra_prediction_columns: Iterable[str] = (),
) -> pd.DataFrame:
    required = [
        "decision_timestamp",
        "long_best_adjusted_pnl",
        "short_best_adjusted_pnl",
        long_column,
        short_column,
    ]
    missing = sorted(set(required) - set(predictions.columns))
    if missing:
        raise ValueError(f"predictions are missing columns: {', '.join(missing)}")
    analysis_columns = [
        *ANALYSIS_PREDICTION_COLUMNS,
        long_column,
        short_column,
        *extra_prediction_columns,
    ]
    columns = list(dict.fromkeys(column for column in analysis_columns if column in predictions.columns))
    predictions = predictions[columns].copy()
    predictions["pred_long_best_adjusted_pnl"] = predictions[long_column]
    predictions["pred_short_best_adjusted_pnl"] = predictions[short_column]
    return predictions


def optional_parquet_columns(path: Path, columns: Iterable[str]) -> list[str]:
    try:
        import pyarrow.parquet as pq

        available = set(pq.ParquetFile(path).schema.names)
    except Exception:
        return []
    return [column for column in columns if column in available]


def read_analysis_predictions(path: Path, long_column: str, short_column: str) -> pd.DataFrame:
    predictions = prepare_analysis_predictions(pd.read_parquet(path), long_column, short_column)
    predictions["decision_timestamp"] = pd.to_datetime(predictions["decision_timestamp"], utc=True)
    duplicated = predictions["decision_timestamp"].duplicated()
    if duplicated.any():
        duplicated_count = int(duplicated.sum())
        raise ValueError(f"{path} has duplicated decision_timestamp values: {duplicated_count}")
    return predictions.sort_values("decision_timestamp").reset_index(drop=True)


def side_values(
    frame: pd.DataFrame,
    direction: pd.Series,
    long_column: str,
    short_column: str,
) -> pd.Series:
    values = np.where(direction.eq("long"), frame[long_column], frame[short_column])
    return pd.Series(values, index=frame.index)


def opposite_side_values(
    frame: pd.DataFrame,
    direction: pd.Series,
    long_column: str,
    short_column: str,
) -> pd.Series:
    values = np.where(direction.eq("long"), frame[short_column], frame[long_column])
    return pd.Series(values, index=frame.index)


def numeric_indicator(series: pd.Series) -> pd.Series:
    return series.fillna(False).astype(float)


def bucket_series(values: pd.Series, bins: list[float], labels: list[str]) -> pd.Series:
    return pd.cut(values.astype(float), bins=bins, labels=labels, include_lowest=True)


def add_trade_analysis_buckets(enriched: pd.DataFrame) -> pd.DataFrame:
    output = enriched.copy()
    output["entry_hour"] = output["entry_timestamp"].dt.hour
    output["holding_bucket"] = bucket_series(
        output["holding_minutes"],
        [-float("inf"), 5, 30, 120, 360, 720, 1440, float("inf")],
        ["<=5m", "5-30m", "30-120m", "2-6h", "6-12h", "12-24h", ">24h"],
    )
    pnl_bins = [-float("inf"), 0, 5, 15, 30, float("inf")]
    pnl_labels = ["<=0", "0-5", "5-15", "15-30", ">30"]
    output["actual_taken_best_bucket"] = bucket_series(
        output["actual_taken_best_adjusted_pnl"], pnl_bins, pnl_labels
    )
    output["pred_taken_ev_bucket"] = bucket_series(output["pred_taken_ev"], pnl_bins, pnl_labels)
    wait_bins = [-float("inf"), 0, 2, 4, 10, float("inf")]
    wait_labels = ["<=0", "0-2", "2-4", "4-10", ">10"]
    output["actual_taken_wait_regret_bucket"] = bucket_series(
        output["actual_taken_wait_regret"], wait_bins, wait_labels
    )
    output["pred_taken_wait_regret_bucket"] = bucket_series(
        output["pred_taken_wait_regret"], wait_bins, wait_labels
    )
    rank_bins = [-float("inf"), 0.25, 0.5, 0.75, 1.0, float("inf")]
    rank_labels = ["<=0.25", "0.25-0.5", "0.5-0.75", "0.75-1.0", ">1.0"]
    output["actual_taken_entry_rank_bucket"] = bucket_series(
        output["actual_taken_entry_local_rank"], rank_bins, rank_labels
    )
    output["pred_taken_entry_rank_bucket"] = bucket_series(
        output["pred_taken_entry_local_rank"], rank_bins, rank_labels
    )
    return output


def enrich_trades_with_predictions(
    trades: pd.DataFrame,
    predictions: pd.DataFrame,
    extra_prediction_columns: Iterable[str] = (),
) -> pd.DataFrame:
    prediction_column_candidates = [
        *ANALYSIS_PREDICTION_COLUMNS,
        *extra_prediction_columns,
    ]
    if trades.empty:
        output = trades.copy()
        for column in prediction_column_candidates:
            if column not in output.columns:
                output[column] = pd.Series(dtype="float64")
        for column in [
            "matched_prediction",
            "direction_error",
            "no_edge_entry",
            "predicted_side_error",
            "exit_regret",
            "best_side_regret",
            "ev_overestimate_vs_oracle",
            "ev_overestimate_vs_realized",
            "is_win",
            "is_long",
            "is_short",
            "is_forced_exit",
            "is_loss",
        ]:
            output[column] = pd.Series(dtype="float64")
        return output

    output = trades.copy()
    for column in ["entry_timestamp", "exit_timestamp", "entry_decision_timestamp", "exit_decision_timestamp"]:
        output[column] = pd.to_datetime(output[column], utc=True)

    prediction_columns = list(
        dict.fromkeys(column for column in prediction_column_candidates if column in predictions.columns)
    )
    prediction_frame = predictions[prediction_columns].copy()
    prediction_frame["decision_timestamp"] = pd.to_datetime(
        prediction_frame["decision_timestamp"], utc=True
    )
    output = output.merge(
        prediction_frame,
        left_on="entry_decision_timestamp",
        right_on="decision_timestamp",
        how="left",
        validate="many_to_one",
    )
    output["matched_prediction"] = output["decision_timestamp"].notna()

    for column in prediction_column_candidates:
        if column != "decision_timestamp" and column not in output.columns:
            output[column] = np.nan

    direction = output["direction"].astype(str).str.lower()
    output["direction_sign"] = direction.map({"long": 1, "short": -1}).fillna(0).astype(int)
    output["actual_taken_best_adjusted_pnl"] = side_values(
        output, direction, "long_best_adjusted_pnl", "short_best_adjusted_pnl"
    )
    output["actual_opposite_best_adjusted_pnl"] = opposite_side_values(
        output, direction, "long_best_adjusted_pnl", "short_best_adjusted_pnl"
    )
    output["actual_best_adjusted_pnl"] = output[
        ["long_best_adjusted_pnl", "short_best_adjusted_pnl"]
    ].max(axis=1)
    output["actual_best_side"] = np.where(
        output["long_best_adjusted_pnl"] >= output["short_best_adjusted_pnl"], "long", "short"
    )
    output["actual_best_side"] = pd.Series(output["actual_best_side"], index=output.index).where(
        output["matched_prediction"], pd.NA
    )

    output["actual_taken_best_holding_minutes"] = side_values(
        output, direction, "long_best_holding_minutes", "short_best_holding_minutes"
    )
    output["actual_taken_max_adverse_pnl"] = side_values(
        output, direction, "long_max_adverse_pnl", "short_max_adverse_pnl"
    )
    output["actual_taken_profit_barrier_hit"] = side_values(
        output, direction, "long_profit_barrier_hit", "short_profit_barrier_hit"
    )
    output["actual_taken_wait_regret"] = side_values(
        output, direction, "long_wait_regret", "short_wait_regret"
    )
    output["actual_taken_entry_local_rank"] = side_values(
        output, direction, "long_entry_local_rank", "short_entry_local_rank"
    )

    output["pred_taken_ev"] = side_values(
        output, direction, "pred_long_best_adjusted_pnl", "pred_short_best_adjusted_pnl"
    )
    output["pred_opposite_ev"] = opposite_side_values(
        output, direction, "pred_long_best_adjusted_pnl", "pred_short_best_adjusted_pnl"
    )
    output["pred_best_ev"] = output[
        ["pred_long_best_adjusted_pnl", "pred_short_best_adjusted_pnl"]
    ].max(axis=1)
    output["predicted_best_side"] = np.where(
        output["pred_long_best_adjusted_pnl"] >= output["pred_short_best_adjusted_pnl"],
        "long",
        "short",
    )
    output["predicted_best_side"] = pd.Series(
        output["predicted_best_side"], index=output.index
    ).where(output["matched_prediction"], pd.NA)
    output["pred_taken_best_holding_minutes"] = side_values(
        output, direction, "pred_long_best_holding_minutes", "pred_short_best_holding_minutes"
    )
    output["pred_taken_max_adverse_pnl"] = side_values(
        output, direction, "pred_long_max_adverse_pnl", "pred_short_max_adverse_pnl"
    )
    output["pred_taken_wait_regret"] = side_values(
        output, direction, "pred_long_wait_regret", "pred_short_wait_regret"
    )
    output["pred_taken_entry_local_rank"] = side_values(
        output, direction, "pred_long_entry_local_rank", "pred_short_entry_local_rank"
    )
    output["pred_taken_profit_barrier_hit"] = side_values(
        output, direction, "pred_long_profit_barrier_hit", "pred_short_profit_barrier_hit"
    )
    output["pred_taken_side_confidence"] = side_values(
        output, direction, "pred_best_side_prob_1", "pred_best_side_prob_-1"
    )
    output["pred_opposite_side_confidence"] = opposite_side_values(
        output, direction, "pred_best_side_prob_1", "pred_best_side_prob_-1"
    )
    output["pred_side_confidence_gap"] = (
        output["pred_taken_side_confidence"] - output["pred_opposite_side_confidence"]
    )

    output["direction_error"] = (
        output["actual_opposite_best_adjusted_pnl"] > output["actual_taken_best_adjusted_pnl"]
    )
    output["no_edge_entry"] = output["actual_taken_best_adjusted_pnl"] <= 0
    output["predicted_side_error"] = output["predicted_best_side"] != output["actual_best_side"]
    output["predicted_side_matches_trade"] = output["predicted_best_side"] == direction
    output["actual_side_matches_trade"] = output["actual_best_side"] == direction
    output["exit_regret"] = (
        output["actual_taken_best_adjusted_pnl"] - output["adjusted_pnl"].astype(float)
    ).clip(lower=0)
    output["best_side_regret"] = (
        output["actual_best_adjusted_pnl"] - output["adjusted_pnl"].astype(float)
    ).clip(lower=0)
    output["ev_overestimate_vs_oracle"] = (
        output["pred_taken_ev"] - output["actual_taken_best_adjusted_pnl"]
    )
    output["ev_overestimate_vs_realized"] = output["pred_taken_ev"] - output["adjusted_pnl"].astype(float)
    output["holding_error_minutes"] = (
        output["pred_taken_best_holding_minutes"] - output["holding_minutes"].astype(float)
    )
    output["oracle_holding_gap_minutes"] = (
        output["actual_taken_best_holding_minutes"] - output["holding_minutes"].astype(float)
    )

    output["is_win"] = output["adjusted_pnl"].astype(float) > 0
    output["is_long"] = direction.eq("long")
    output["is_short"] = direction.eq("short")
    output["is_forced_exit"] = output["exit_reason"].eq("forced_exit")
    output["is_loss"] = output["adjusted_pnl"].astype(float) < 0
    return add_trade_analysis_buckets(output)


def trade_group_summary(frame: pd.DataFrame, group_column: str) -> pd.DataFrame:
    if frame.empty or group_column not in frame.columns:
        return pd.DataFrame()
    working = frame.copy()
    working["_wins"] = numeric_indicator(working["is_win"])
    working["_longs"] = numeric_indicator(working["is_long"])
    working["_shorts"] = numeric_indicator(working["is_short"])
    working["_forced"] = numeric_indicator(working["is_forced_exit"])
    working["_direction_errors"] = numeric_indicator(working["direction_error"])
    working["_no_edge"] = numeric_indicator(working["no_edge_entry"])
    working["_pred_side_errors"] = numeric_indicator(working["predicted_side_error"])

    grouped = working.groupby(group_column, dropna=False, observed=True)
    summary = grouped.agg(
        trade_count=("adjusted_pnl", "size"),
        total_adjusted_pnl=("adjusted_pnl", "sum"),
        total_raw_pnl=("raw_pnl", "sum"),
        avg_adjusted_pnl=("adjusted_pnl", "mean"),
        win_rate=("_wins", "mean"),
        long_trade_count=("_longs", "sum"),
        short_trade_count=("_shorts", "sum"),
        forced_exit_count=("_forced", "sum"),
        direction_error_rate=("_direction_errors", "mean"),
        no_edge_rate=("_no_edge", "mean"),
        predicted_side_error_rate=("_pred_side_errors", "mean"),
        exit_regret_sum=("exit_regret", "sum"),
        exit_regret_mean=("exit_regret", "mean"),
        best_side_regret_sum=("best_side_regret", "sum"),
        ev_overestimate_vs_oracle_mean=("ev_overestimate_vs_oracle", "mean"),
        ev_overestimate_vs_realized_mean=("ev_overestimate_vs_realized", "mean"),
        avg_holding_minutes=("holding_minutes", "mean"),
    ).reset_index()
    return summary.sort_values(["total_adjusted_pnl", "trade_count"], ascending=[True, False])


def trade_failure_flags(enriched: pd.DataFrame) -> pd.DataFrame:
    flag_masks = {
        "losing_trade": enriched["adjusted_pnl"].astype(float) < 0,
        "direction_error": enriched["direction_error"],
        "no_edge_entry": enriched["no_edge_entry"],
        "predicted_side_error": enriched["predicted_side_error"],
        "exit_regret_positive": enriched["exit_regret"] > 0,
        "ev_overestimated_oracle": enriched["ev_overestimate_vs_oracle"] > 0,
        "ev_overestimated_realized": enriched["ev_overestimate_vs_realized"] > 0,
        "profit_barrier_miss": enriched["actual_taken_profit_barrier_hit"] < 0.5,
        "forced_exit": enriched["is_forced_exit"],
    }
    rows: list[dict[str, object]] = []
    for name, mask in flag_masks.items():
        selected = enriched[mask.fillna(False)]
        losing = selected[selected["adjusted_pnl"].astype(float) < 0]
        rows.append(
            {
                "flag": name,
                "trade_count": int(len(selected)),
                "losing_trade_count": int(len(losing)),
                "total_adjusted_pnl": float(selected["adjusted_pnl"].sum()) if len(selected) else 0.0,
                "avg_adjusted_pnl": float(selected["adjusted_pnl"].mean()) if len(selected) else 0.0,
                "loss_adjusted_pnl": float(losing["adjusted_pnl"].sum()) if len(losing) else 0.0,
                "exit_regret_sum": float(selected["exit_regret"].sum()) if len(selected) else 0.0,
                "ev_overestimate_vs_realized_mean": (
                    float(selected["ev_overestimate_vs_realized"].mean()) if len(selected) else 0.0
                ),
            }
        )
    return pd.DataFrame(rows).sort_values(["loss_adjusted_pnl", "trade_count"])


def trade_analysis_summary(enriched: pd.DataFrame) -> dict[str, object]:
    if enriched.empty:
        return {
            "trade_count": 0,
            "matched_prediction_count": 0,
            "total_adjusted_pnl": 0.0,
            "total_raw_pnl": 0.0,
            "analysis_matched_prediction_rate": 0.0,
            "direction_error_rate": 0.0,
            "no_edge_rate": 0.0,
            "predicted_side_error_rate": 0.0,
            "exit_regret_sum": 0.0,
            "exit_regret_mean": 0.0,
            "best_side_regret_sum": 0.0,
            "best_side_regret_mean": 0.0,
            "ev_overestimate_vs_oracle_mean": 0.0,
            "ev_overestimate_vs_realized_mean": 0.0,
            "avg_holding_minutes": 0.0,
        }
    adjusted = enriched["adjusted_pnl"].astype(float)
    raw = enriched["raw_pnl"].astype(float)
    exit_regret = enriched["exit_regret"].astype(float)
    best_side_regret = enriched["best_side_regret"].astype(float)
    return {
        "trade_count": int(len(enriched)),
        "matched_prediction_count": int(enriched["matched_prediction"].sum()),
        "total_adjusted_pnl": float(adjusted.sum()),
        "total_raw_pnl": float(raw.sum()),
        "analysis_matched_prediction_rate": float(numeric_indicator(enriched["matched_prediction"]).mean()),
        "win_rate": float((adjusted > 0).mean()),
        "long_adjusted_pnl": float(enriched.loc[enriched["is_long"], "adjusted_pnl"].sum()),
        "short_adjusted_pnl": float(enriched.loc[enriched["is_short"], "adjusted_pnl"].sum()),
        "direction_error_rate": float(numeric_indicator(enriched["direction_error"]).mean()),
        "no_edge_rate": float(numeric_indicator(enriched["no_edge_entry"]).mean()),
        "predicted_side_error_rate": float(numeric_indicator(enriched["predicted_side_error"]).mean()),
        "exit_regret_sum": float(exit_regret.sum()),
        "exit_regret_mean": float(exit_regret.mean()),
        "best_side_regret_sum": float(best_side_regret.sum()),
        "best_side_regret_mean": float(best_side_regret.mean()),
        "ev_overestimate_vs_oracle_mean": float(enriched["ev_overestimate_vs_oracle"].mean()),
        "ev_overestimate_vs_realized_mean": float(enriched["ev_overestimate_vs_realized"].mean()),
        "avg_holding_minutes": float(enriched["holding_minutes"].mean()),
    }


def trade_prediction_diagnostics(
    trades: pd.DataFrame,
    predictions: pd.DataFrame,
    long_column: str = "pred_long_best_adjusted_pnl",
    short_column: str = "pred_short_best_adjusted_pnl",
) -> dict[str, float]:
    try:
        analysis_predictions = prepare_analysis_predictions(predictions, long_column, short_column)
    except ValueError:
        analysis_predictions = predictions
    summary = trade_analysis_summary(enrich_trades_with_predictions(trades, analysis_predictions))
    diagnostics: dict[str, float] = {}
    for column in TRADE_ANALYSIS_DIAGNOSTIC_COLUMNS:
        value = summary.get(column, 0.0)
        if value is None or not np.isfinite(float(value)):
            value = 0.0
        diagnostics[column] = float(value)
    return diagnostics


def strategy_config_from_args(args: argparse.Namespace, strategy: str | None = None) -> StrategyConfig:
    return StrategyConfig(
        strategy=strategy or args.strategy,
        fast_window=args.fast_window,
        slow_window=args.slow_window,
        rsi_window=args.rsi_window,
        rsi_lower=args.rsi_lower,
        rsi_upper=args.rsi_upper,
        rsi_exit_lower=args.rsi_exit_lower,
        rsi_exit_upper=args.rsi_exit_upper,
        breakout_window=args.breakout_window,
        random_entry_probability=args.random_entry_probability,
        random_exit_probability=args.random_exit_probability,
        random_seed=args.random_seed,
    )


def model_policy_config_from_args(args: argparse.Namespace) -> ModelPolicyConfig:
    return ModelPolicyConfig(
        predictions=args.predictions,
        policy=args.policy,
        entry_threshold=args.entry_threshold,
        long_entry_threshold_offset=args.long_entry_threshold_offset,
        short_entry_threshold_offset=args.short_entry_threshold_offset,
        exit_threshold=args.exit_threshold,
        side_margin=args.side_margin,
        long_column=args.long_column,
        short_column=args.short_column,
        long_risk_column=args.long_risk_column,
        short_risk_column=args.short_risk_column,
        risk_penalty=args.risk_penalty,
        long_secondary_score_column=args.long_secondary_score_column,
        short_secondary_score_column=args.short_secondary_score_column,
        secondary_score_tie_margin=args.secondary_score_tie_margin,
        long_holding_column=args.long_holding_column,
        short_holding_column=args.short_holding_column,
        min_predicted_hold_minutes=args.min_predicted_hold_minutes,
        max_predicted_hold_minutes=args.max_predicted_hold_minutes,
        min_valid_predicted_hold_minutes=resolve_min_valid_predicted_hold_minutes(
            args.min_valid_predicted_hold_minutes,
            args.long_holding_column,
            args.short_holding_column,
        ),
        long_holding_fallback_column=args.long_holding_fallback_column,
        short_holding_fallback_column=args.short_holding_fallback_column,
        fixed_horizon_minutes=parse_csv_float_tuple(args.fixed_horizon_minutes),
        long_fixed_horizon_columns=parse_csv_string_tuple(args.long_fixed_horizon_columns),
        short_fixed_horizon_columns=parse_csv_string_tuple(args.short_fixed_horizon_columns),
        fixed_horizon_score_mode=args.fixed_horizon_score_mode,
        long_wait_regret_column=args.long_wait_regret_column,
        short_wait_regret_column=args.short_wait_regret_column,
        long_entry_rank_column=args.long_entry_rank_column,
        short_entry_rank_column=args.short_entry_rank_column,
        long_profit_barrier_column=args.long_profit_barrier_column,
        short_profit_barrier_column=args.short_profit_barrier_column,
        long_time_exit_column=args.long_time_exit_column,
        short_time_exit_column=args.short_time_exit_column,
        long_loss_first_column=args.long_loss_first_column,
        short_loss_first_column=args.short_loss_first_column,
        long_side_confidence_column=args.long_side_confidence_column,
        short_side_confidence_column=args.short_side_confidence_column,
        long_trade_quality_column=args.long_trade_quality_column,
        short_trade_quality_column=args.short_trade_quality_column,
        max_wait_regret=args.max_wait_regret,
        min_entry_rank=args.min_entry_rank,
        min_trade_quality=args.min_trade_quality,
        profit_barrier_miss_penalty=args.profit_barrier_miss_penalty,
        time_exit_penalty=args.time_exit_penalty,
        loss_first_penalty=args.loss_first_penalty,
        time_exit_holding_shrink=args.time_exit_holding_shrink,
        loss_first_holding_shrink=args.loss_first_holding_shrink,
        long_holding_shortening_column=args.long_holding_shortening_column,
        short_holding_shortening_column=args.short_holding_shortening_column,
        holding_shortening_threshold=args.holding_shortening_threshold,
        holding_shortening_cap_minutes=args.holding_shortening_cap_minutes,
        time_exit_exit_threshold=args.time_exit_exit_threshold,
        loss_first_exit_threshold=args.loss_first_exit_threshold,
        side_confidence_penalty=args.side_confidence_penalty,
        side_confidence_penalty_rules=parse_optional_csv_strings(args.side_confidence_penalty_rules),
        side_confidence_overfit_penalty_rules=parse_optional_csv_strings(
            args.side_confidence_overfit_penalty_rules
        ),
        min_side_confidence=args.min_side_confidence,
        require_profit_barrier=args.require_profit_barrier,
        profit_barrier_threshold=args.profit_barrier_threshold,
        side_ev_penalty_rules=parse_optional_csv_strings(args.side_ev_penalty_rules),
        side_ev_penalty_replacement_min_margin=args.side_ev_penalty_replacement_min_margin,
        extra_side_margin_rules=parse_optional_csv_strings(args.extra_side_margin_rules),
        side_extra_margin_rules=parse_optional_csv_strings(args.side_extra_margin_rules),
        side_block_rules=parse_optional_csv_strings(args.side_block_rules),
        context_drawdown_guard_loss_threshold=args.context_drawdown_guard_loss_threshold,
        context_drawdown_guard_min_entry_margin=args.context_drawdown_guard_min_entry_margin,
        context_drawdown_guard_context_columns=parse_csv_string_tuple(
            args.context_drawdown_guard_context_columns
        ),
        context_drawdown_guard_reset_monthly=args.context_drawdown_guard_reset_monthly,
        **regime_blocks_from_args(args),
    )


def prepare_data_and_config(args: argparse.Namespace) -> tuple[pd.DataFrame, BacktestConfig]:
    start, end = month_bounds(args.month)
    max_holding = pd.Timedelta(hours=args.max_hold_hours)
    all_data = read_ohlcv(args.data)
    data = slice_for_month(
        all_data,
        start=start,
        end=end,
        warmup_days=args.warmup_days,
        post_days=args.post_days,
        max_holding=max_holding,
    )
    config = BacktestConfig(
        evaluation_start=start,
        evaluation_end=end,
        max_holding=max_holding,
        profit_multiplier=args.profit_multiplier,
        loss_multiplier=args.loss_multiplier,
        spread_points=args.spread_points,
        slippage_points=args.slippage_points,
        execution_delay_bars=args.execution_delay_bars,
    )
    return data, config


def run_strategy(
    df: pd.DataFrame,
    backtest_config: BacktestConfig,
    strategy_config: StrategyConfig,
) -> tuple[dict[str, object], pd.DataFrame, pd.DataFrame]:
    signal = build_signal(df, strategy_config)
    trades = trades_to_frame(run_backtest(df, signal, backtest_config))
    metrics = summarize_trades(trades, backtest_config, strategy_config.strategy)
    curve = equity_curve(trades, backtest_config.evaluation_start)
    return metrics, trades, curve


def run_model_policy(
    df: pd.DataFrame,
    backtest_config: BacktestConfig,
    model_policy_config: ModelPolicyConfig,
    predictions: pd.DataFrame | None = None,
) -> tuple[dict[str, object], pd.DataFrame, pd.DataFrame, pd.Series]:
    if predictions is None:
        predictions = read_prediction_frame(model_policy_config.predictions, model_policy_config)
    else:
        predictions = normalize_prediction_frame(
            predictions,
            prediction_required_columns(model_policy_config),
            model_policy_config.predictions,
        )
    if (
        context_drawdown_guard_enabled(model_policy_config)
        and model_policy_config.context_drawdown_guard_loss_threshold <= 0
    ):
        raise ValueError("context_drawdown_guard_loss_threshold must be positive or inf")
    signal = model_signal_from_predictions(df, predictions, model_policy_config)
    entry_context = model_policy_entry_context(df, predictions, model_policy_config)
    entry_margin = (
        model_policy_entry_margin(df, predictions, model_policy_config)
        if (
            context_drawdown_guard_enabled(model_policy_config)
            and np.isfinite(model_policy_config.context_drawdown_guard_min_entry_margin)
        )
        else None
    )
    trades = trades_to_frame(
        run_backtest(
            df,
            signal,
            backtest_config,
            entry_context=entry_context,
            entry_margin=entry_margin,
            context_drawdown_guard_loss_threshold=(
                model_policy_config.context_drawdown_guard_loss_threshold
            ),
            context_drawdown_guard_min_entry_margin=(
                model_policy_config.context_drawdown_guard_min_entry_margin
            ),
            context_drawdown_guard_reset_monthly=(
                model_policy_config.context_drawdown_guard_reset_monthly
            ),
        )
    )
    strategy_name = f"model_{model_policy_config.policy}"
    metrics = summarize_trades(trades, backtest_config, strategy_name)
    metrics["prediction_rows"] = int(len(predictions))
    metrics["signal_long_count"] = int((signal == 1).sum())
    metrics["signal_short_count"] = int((signal == -1).sum())
    metrics["signal_flat_count"] = int((signal == 0).sum())
    metrics.update(direction_session_diagnostics(trades, predictions))
    metrics.update(combined_regime_diagnostics(trades, predictions))
    metrics.update(
        trade_prediction_diagnostics(
            trades,
            predictions,
            model_policy_config.long_column,
            model_policy_config.short_column,
        )
    )
    metrics.update(profit_barrier_diagnostics(trades, predictions, model_policy_config))
    metrics.update(profit_barrier_calibration_diagnostics(trades, predictions, model_policy_config))
    curve = equity_curve(trades, backtest_config.evaluation_start)
    return metrics, trades, curve, signal


def handle_model_cost_sensitivity(args: argparse.Namespace) -> int:
    df, base_backtest_config = prepare_data_and_config(args)
    model_policy_config = model_policy_config_from_args(args)
    spreads = parse_csv_floats(args.spread_points_list)
    slippages = parse_csv_floats(args.slippage_points_list)
    delays = [int(value) for value in parse_csv_floats(args.execution_delay_bars_list)]
    if any(value < 0 for value in delays):
        raise SystemExit("execution delay bars must be non-negative")

    run_dir = make_run_dir(args.output_dir, f"model_cost_sensitivity_{args.month}")
    rows: list[dict[str, object]] = []
    for spread_points in spreads:
        for slippage_points in slippages:
            for execution_delay_bars in delays:
                backtest_config = replace(
                    base_backtest_config,
                    spread_points=spread_points,
                    slippage_points=slippage_points,
                    execution_delay_bars=execution_delay_bars,
                )
                metrics, _, _, _ = run_model_policy(df, backtest_config, model_policy_config)
                rows.append(metrics)

    metrics_frame = pd.DataFrame(rows).sort_values(
        ["spread_points", "slippage_points", "execution_delay_bars"],
    )
    metrics_frame.to_csv(run_dir / "metrics.csv", index=False)
    metadata = {
        "month": args.month,
        "predictions": str(args.predictions),
        "model_policy_config": {
            **asdict(model_policy_config),
            "predictions": str(model_policy_config.predictions),
        },
        "spread_points_list": spreads,
        "slippage_points_list": slippages,
        "execution_delay_bars_list": delays,
    }
    with (run_dir / "config.json").open("w", encoding="utf-8") as handle:
        json.dump(metadata, handle, ensure_ascii=False, indent=2, default=json_default)
    print(metrics_frame.to_string(index=False))
    print(f"artifacts: {run_dir}")
    return 0


def handle_run(args: argparse.Namespace) -> int:
    df, backtest_config = prepare_data_and_config(args)
    strategy_config = strategy_config_from_args(args)
    metrics, trades, curve = run_strategy(df, backtest_config, strategy_config)
    label = f"{args.strategy}_{args.month}"
    run_dir = make_run_dir(args.output_dir, label)
    write_result(run_dir, metrics, trades, curve, strategy_config, backtest_config)
    print_metrics(metrics)
    print(f"artifacts: {run_dir}")
    return 0


def handle_model_policy(args: argparse.Namespace) -> int:
    df, backtest_config = prepare_data_and_config(args)
    model_policy_config = model_policy_config_from_args(args)
    metrics, trades, curve, signal = run_model_policy(df, backtest_config, model_policy_config)
    label = f"model_{args.policy}_{args.month}"
    run_dir = make_run_dir(args.output_dir, label)
    write_result(
        run_dir,
        metrics,
        trades,
        curve,
        strategy_config=None,
        backtest_config=backtest_config,
        model_policy_config=model_policy_config,
    )
    pd.DataFrame({"timestamp": df["timestamp"], "desired_position": signal}).to_csv(
        run_dir / "desired_position.csv",
        index=False,
    )
    print_metrics(metrics)
    print(f"prediction_rows: {metrics['prediction_rows']}")
    print(f"signal_long_count: {metrics['signal_long_count']}")
    print(f"signal_short_count: {metrics['signal_short_count']}")
    print(f"signal_flat_count: {metrics['signal_flat_count']}")
    print(f"artifacts: {run_dir}")
    return 0


def add_regime_gate_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--block-trend-regimes",
        default="",
        help="comma-separated trend_regime values that may not open new positions",
    )
    parser.add_argument(
        "--block-volatility-regimes",
        default="",
        help="comma-separated volatility_regime values that may not open new positions",
    )
    parser.add_argument(
        "--block-session-regimes",
        default="",
        help="comma-separated session_regime values that may not open new positions",
    )
    parser.add_argument(
        "--block-gap-regimes",
        default="",
        help="comma-separated gap_regime values that may not open new positions",
    )
    parser.add_argument(
        "--block-combined-regimes",
        default="",
        help="comma-separated combined_regime values that may not open new positions",
    )


def add_model_policy_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--policy", choices=available_model_policies(), default="stateful_ev")
    parser.add_argument("--entry-threshold", type=float, default=15.0)
    parser.add_argument("--long-entry-threshold-offset", type=float, default=0.0)
    parser.add_argument("--short-entry-threshold-offset", type=float, default=0.0)
    parser.add_argument("--exit-threshold", type=float, default=0.0)
    parser.add_argument("--side-margin", type=float, default=0.0)
    parser.add_argument("--long-column", default="pred_long_best_adjusted_pnl")
    parser.add_argument("--short-column", default="pred_short_best_adjusted_pnl")
    parser.add_argument("--long-risk-column", default="pred_long_max_adverse_pnl")
    parser.add_argument("--short-risk-column", default="pred_short_max_adverse_pnl")
    parser.add_argument("--risk-penalty", type=float, default=0.0)
    parser.add_argument(
        "--long-secondary-score-column",
        default="",
        help="optional long-side secondary score used only for near-tie side selection",
    )
    parser.add_argument(
        "--short-secondary-score-column",
        default="",
        help="optional short-side secondary score used only for near-tie side selection",
    )
    parser.add_argument(
        "--secondary-score-tie-margin",
        type=float,
        default=-float("inf"),
        help=(
            "primary EV side-gap at or below which secondary score columns may choose "
            "the side; use -inf to disable"
        ),
    )
    parser.add_argument("--long-holding-column", default="pred_long_best_holding_minutes")
    parser.add_argument("--short-holding-column", default="pred_short_best_holding_minutes")
    parser.add_argument("--min-predicted-hold-minutes", type=float, default=1.0)
    parser.add_argument("--max-predicted-hold-minutes", type=float, default=1440.0)
    parser.add_argument(
        "--min-valid-predicted-hold-minutes",
        type=float,
        default=None,
        help=(
            "minimum raw timed_ev holding prediction required before an entry; "
            "omit to use 30 for pred_mlp_* holding columns and -inf otherwise; "
            "use -inf to force the historical clip-only behavior"
        ),
    )
    parser.add_argument(
        "--long-holding-fallback-column",
        default="",
        help="optional long holding column used when the primary timed_ev holding is invalid",
    )
    parser.add_argument(
        "--short-holding-fallback-column",
        default="",
        help="optional short holding column used when the primary timed_ev holding is invalid",
    )
    parser.add_argument(
        "--fixed-horizon-minutes",
        default=",".join(str(int(minutes)) for minutes in DEFAULT_FIXED_HORIZON_MINUTES),
    )
    parser.add_argument(
        "--long-fixed-horizon-columns",
        default=",".join(DEFAULT_LONG_FIXED_HORIZON_COLUMNS),
    )
    parser.add_argument(
        "--short-fixed-horizon-columns",
        default=",".join(DEFAULT_SHORT_FIXED_HORIZON_COLUMNS),
    )
    parser.add_argument(
        "--fixed-horizon-score-mode",
        choices=FIXED_HORIZON_SCORE_MODES,
        default="max",
        help="how fixed-horizon EV columns are aggregated into the entry score",
    )
    parser.add_argument("--long-wait-regret-column", default="pred_long_wait_regret")
    parser.add_argument("--short-wait-regret-column", default="pred_short_wait_regret")
    parser.add_argument("--long-entry-rank-column", default="pred_long_entry_local_rank")
    parser.add_argument("--short-entry-rank-column", default="pred_short_entry_local_rank")
    parser.add_argument("--long-profit-barrier-column", default="pred_long_profit_barrier_hit")
    parser.add_argument("--short-profit-barrier-column", default="pred_short_profit_barrier_hit")
    parser.add_argument("--long-time-exit-column", default="pred_long_exit_event_prob_0")
    parser.add_argument("--short-time-exit-column", default="pred_short_exit_event_prob_0")
    parser.add_argument("--long-loss-first-column", default="pred_long_exit_event_prob_2")
    parser.add_argument("--short-loss-first-column", default="pred_short_exit_event_prob_2")
    parser.add_argument("--long-side-confidence-column", default="pred_best_side_prob_1")
    parser.add_argument("--short-side-confidence-column", default="pred_best_side_prob_-1")
    parser.add_argument("--long-trade-quality-column", default="pred_trade_quality_long_adjusted_pnl")
    parser.add_argument("--short-trade-quality-column", default="pred_trade_quality_short_adjusted_pnl")
    parser.add_argument("--max-wait-regret", type=float, default=float("inf"))
    parser.add_argument("--min-entry-rank", type=float, default=0.0)
    parser.add_argument("--min-trade-quality", type=float, default=-float("inf"))
    parser.add_argument(
        "--profit-barrier-miss-penalty",
        type=float,
        default=0.0,
        help="EV penalty multiplied by 1 - side profit-barrier prediction",
    )
    parser.add_argument(
        "--time-exit-penalty",
        type=float,
        default=0.0,
        help="EV penalty multiplied by side time-exit probability",
    )
    parser.add_argument(
        "--loss-first-penalty",
        type=float,
        default=0.0,
        help="EV penalty multiplied by side loss-first exit-event probability",
    )
    parser.add_argument(
        "--time-exit-holding-shrink",
        type=float,
        default=0.0,
        help="fractional holding-time shrink multiplied by side time-exit probability",
    )
    parser.add_argument(
        "--loss-first-holding-shrink",
        type=float,
        default=0.0,
        help="fractional holding-time shrink multiplied by side loss-first exit-event probability",
    )
    parser.add_argument(
        "--long-holding-shortening-column",
        default="pred_long_fixed_60m_beats_exit_event_prob_1",
        help="long-side probability that a shorter fixed hold beats the exit-event hold",
    )
    parser.add_argument(
        "--short-holding-shortening-column",
        default="pred_short_fixed_60m_beats_exit_event_prob_1",
        help="short-side probability that a shorter fixed hold beats the exit-event hold",
    )
    parser.add_argument(
        "--holding-shortening-threshold",
        type=float,
        default=float("inf"),
        help="cap holding time when side shortening probability is at or above this value; inf disables",
    )
    parser.add_argument(
        "--holding-shortening-cap-minutes",
        type=float,
        default=60.0,
        help="maximum holding minutes used after holding-shortening threshold is met",
    )
    parser.add_argument(
        "--time-exit-exit-threshold",
        type=float,
        default=float("inf"),
        help="exit an open position when side time-exit probability is at or above this value",
    )
    parser.add_argument(
        "--loss-first-exit-threshold",
        type=float,
        default=float("inf"),
        help="exit an open position when side loss-first probability is at or above this value",
    )
    parser.add_argument(
        "--side-confidence-penalty",
        type=float,
        default=0.0,
        help="EV penalty multiplied by 1 - predicted best-side probability",
    )
    parser.add_argument(
        "--side-confidence-penalty-rules",
        default="",
        help=(
            "comma-separated column=value+...:penalty rules that add to side-confidence "
            "penalty in matching regimes"
        ),
    )
    parser.add_argument(
        "--side-confidence-overfit-penalty-rules",
        default="",
        help=(
            "comma-separated column=value+...:penalty rules that subtract penalty * "
            "side confidence in matching regimes"
        ),
    )
    parser.add_argument(
        "--min-side-confidence",
        type=float,
        default=0.0,
        help="minimum predicted best-side probability for the selected side",
    )
    parser.add_argument("--require-profit-barrier", action="store_true")
    parser.add_argument("--profit-barrier-threshold", type=float, default=0.5)
    parser.add_argument(
        "--side-ev-penalty-rules",
        default="",
        help=(
            "comma-separated side:column=value+...:penalty rules that subtract EV from "
            "the matching side before side selection"
        ),
    )
    parser.add_argument(
        "--side-ev-penalty-replacement-min-margin",
        type=float,
        default=-float("inf"),
        help=(
            "extra selected-score margin over the normal entry threshold required only "
            "when side-EV penalty rules match the selected side or change the selected "
            "side; -inf disables"
        ),
    )
    parser.add_argument(
        "--extra-side-margin-rules",
        default="",
        help="comma-separated column=value:margin rules that add side-margin in matching regimes",
    )
    parser.add_argument(
        "--side-extra-margin-rules",
        default="",
        help=(
            "comma-separated side:column=value+...:margin rules that add side-margin only "
            "when the selected side and all conditions match"
        ),
    )
    parser.add_argument(
        "--side-block-rules",
        default="",
        help=(
            "comma-separated side:column=value+... rules that block entries only when the "
            "selected side and all conditions match"
        ),
    )
    parser.add_argument(
        "--context-drawdown-guard-loss-threshold",
        type=float,
        default=float("inf"),
        help=(
            "block later entries in the same direction/context once realized adjusted "
            "PnL for that context is at or below -threshold; inf disables"
        ),
    )
    parser.add_argument(
        "--context-drawdown-guard-min-entry-margin",
        type=float,
        default=float("inf"),
        help=(
            "after a context drawdown breach, allow a later same-context entry only "
            "when selected score minus normal entry threshold is at least this value; "
            "inf preserves hard blocking"
        ),
    )
    parser.add_argument(
        "--context-drawdown-guard-context-columns",
        default="combined_regime,session_regime",
        help="comma-separated prediction columns used with direction as the online drawdown context",
    )
    parser.add_argument(
        "--context-drawdown-guard-reset-monthly",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="reset online context drawdown guard by entry decision month",
    )
    add_regime_gate_args(parser)


def handle_model_sweep(args: argparse.Namespace) -> int:
    df, backtest_config = prepare_data_and_config(args)
    policies = parse_csv_strings(args.policies)
    unknown = sorted(set(policies) - set(available_model_policies()))
    if unknown:
        raise SystemExit(f"unknown model policies: {', '.join(unknown)}")
    entry_thresholds = parse_csv_floats(args.entry_thresholds)
    long_entry_threshold_offsets = parse_csv_floats(args.long_entry_threshold_offsets)
    short_entry_threshold_offsets = parse_csv_floats(args.short_entry_threshold_offsets)
    exit_thresholds = parse_csv_floats(args.exit_thresholds)
    side_margins = parse_csv_floats(args.side_margins)
    risk_penalties = parse_csv_floats(args.risk_penalties)
    secondary_score_tie_margins = parse_csv_floats(args.secondary_score_tie_margins)
    profit_barrier_miss_penalties = parse_csv_floats(args.profit_barrier_miss_penalties)
    time_exit_penalties = parse_csv_floats(args.time_exit_penalties)
    loss_first_penalties = parse_csv_floats(args.loss_first_penalties)
    time_exit_holding_shrinks = parse_csv_floats(args.time_exit_holding_shrinks)
    loss_first_holding_shrinks = parse_csv_floats(args.loss_first_holding_shrinks)
    holding_shortening_thresholds = parse_csv_floats(args.holding_shortening_thresholds)
    holding_shortening_cap_minutes_values = parse_csv_floats(
        args.holding_shortening_cap_minutes
    )
    time_exit_exit_thresholds = parse_csv_floats(args.time_exit_exit_thresholds)
    loss_first_exit_thresholds = parse_csv_floats(args.loss_first_exit_thresholds)
    side_confidence_penalties = parse_csv_floats(args.side_confidence_penalties)
    fixed_horizon_score_modes = parse_csv_strings(args.fixed_horizon_score_modes)
    unknown_fixed_horizon_score_modes = sorted(
        set(fixed_horizon_score_modes) - set(FIXED_HORIZON_SCORE_MODES)
    )
    if unknown_fixed_horizon_score_modes:
        raise SystemExit(
            "unknown fixed horizon score modes: "
            + ", ".join(unknown_fixed_horizon_score_modes)
        )
    max_wait_regrets = parse_csv_floats(args.max_wait_regrets)
    min_predicted_hold_minutes_values = parse_csv_floats(args.min_predicted_hold_minutes)
    max_predicted_hold_minutes_values = parse_csv_floats(args.max_predicted_hold_minutes)
    min_valid_predicted_hold_minutes_values = parse_min_valid_predicted_hold_minutes_values(
        args.min_valid_predicted_hold_minutes,
        args.long_holding_column,
        args.short_holding_column,
    )
    min_entry_ranks = parse_csv_floats(args.min_entry_ranks)
    min_trade_qualities = parse_csv_floats(args.min_trade_qualities)
    min_side_confidences = parse_csv_floats(args.min_side_confidences)
    require_profit_barriers = parse_csv_bools(args.require_profit_barriers)
    profit_barrier_thresholds = parse_csv_floats(args.profit_barrier_thresholds)
    side_ev_penalty_replacement_min_margins = parse_csv_floats(
        args.side_ev_penalty_replacement_min_margins
    )
    context_drawdown_guard_loss_thresholds = parse_csv_floats(
        args.context_drawdown_guard_loss_thresholds
    )
    context_drawdown_guard_min_entry_margins = parse_csv_floats(
        args.context_drawdown_guard_min_entry_margins
    )
    regime_blocks = regime_blocks_from_args(args)
    side_ev_penalty_rule_sets = parse_optional_rule_sets(
        args.side_ev_penalty_rule_sets,
        parse_optional_csv_strings(args.side_ev_penalty_rules),
    )
    side_extra_margin_rule_sets = parse_optional_rule_sets(
        args.side_extra_margin_rule_sets,
        parse_optional_csv_strings(args.side_extra_margin_rules),
    )
    side_block_rule_sets = parse_optional_rule_sets(
        args.side_block_rule_sets,
        parse_optional_csv_strings(args.side_block_rules),
    )

    run_dir = make_run_dir(args.output_dir, f"model_sweep_{args.month}")
    preloaded_predictions: pd.DataFrame | None = None
    if len(policies) == 1:
        finite_wait_regrets = [value for value in max_wait_regrets if np.isfinite(value)]
        finite_trade_qualities = [value for value in min_trade_qualities if np.isfinite(value)]
        finite_time_exit_exit_thresholds = [
            value for value in time_exit_exit_thresholds if np.isfinite(value)
        ]
        finite_loss_first_exit_thresholds = [
            value for value in loss_first_exit_thresholds if np.isfinite(value)
        ]
        finite_holding_shortening_thresholds = [
            value for value in holding_shortening_thresholds if np.isfinite(value)
        ]
        finite_context_drawdown_guard_loss_thresholds = [
            value
            for value in context_drawdown_guard_loss_thresholds
            if np.isfinite(value)
        ]
        read_config = ModelPolicyConfig(
            predictions=args.predictions,
            policy=policies[0],
            long_column=args.long_column,
            short_column=args.short_column,
            long_risk_column=args.long_risk_column,
            short_risk_column=args.short_risk_column,
            risk_penalty=max(risk_penalties),
            long_secondary_score_column=args.long_secondary_score_column,
            short_secondary_score_column=args.short_secondary_score_column,
            secondary_score_tie_margin=max(
                [value for value in secondary_score_tie_margins if np.isfinite(value)],
                default=-float("inf"),
            ),
            long_holding_column=args.long_holding_column,
            short_holding_column=args.short_holding_column,
            min_valid_predicted_hold_minutes=(
                max(
                    [
                        value
                        for value in min_valid_predicted_hold_minutes_values
                        if np.isfinite(value)
                    ],
                    default=-float("inf"),
                )
            ),
            long_holding_fallback_column=args.long_holding_fallback_column,
            short_holding_fallback_column=args.short_holding_fallback_column,
            fixed_horizon_minutes=parse_csv_float_tuple(args.fixed_horizon_minutes),
            long_fixed_horizon_columns=parse_csv_string_tuple(args.long_fixed_horizon_columns),
            short_fixed_horizon_columns=parse_csv_string_tuple(args.short_fixed_horizon_columns),
            fixed_horizon_score_mode=fixed_horizon_score_modes[0],
            long_wait_regret_column=args.long_wait_regret_column,
            short_wait_regret_column=args.short_wait_regret_column,
            long_entry_rank_column=args.long_entry_rank_column,
            short_entry_rank_column=args.short_entry_rank_column,
            long_profit_barrier_column=args.long_profit_barrier_column,
            short_profit_barrier_column=args.short_profit_barrier_column,
            long_time_exit_column=args.long_time_exit_column,
            short_time_exit_column=args.short_time_exit_column,
            long_loss_first_column=args.long_loss_first_column,
            short_loss_first_column=args.short_loss_first_column,
            long_side_confidence_column=args.long_side_confidence_column,
            short_side_confidence_column=args.short_side_confidence_column,
            long_trade_quality_column=args.long_trade_quality_column,
            short_trade_quality_column=args.short_trade_quality_column,
            max_wait_regret=min(finite_wait_regrets) if finite_wait_regrets else float("inf"),
            min_entry_rank=max(min_entry_ranks),
            min_trade_quality=max(finite_trade_qualities) if finite_trade_qualities else -float("inf"),
            profit_barrier_miss_penalty=max(profit_barrier_miss_penalties),
            time_exit_penalty=max(time_exit_penalties),
            loss_first_penalty=max(loss_first_penalties),
            time_exit_holding_shrink=max(time_exit_holding_shrinks),
            loss_first_holding_shrink=max(loss_first_holding_shrinks),
            long_holding_shortening_column=args.long_holding_shortening_column,
            short_holding_shortening_column=args.short_holding_shortening_column,
            holding_shortening_threshold=(
                min(finite_holding_shortening_thresholds)
                if finite_holding_shortening_thresholds
                else float("inf")
            ),
            holding_shortening_cap_minutes=max(holding_shortening_cap_minutes_values),
            time_exit_exit_threshold=(
                min(finite_time_exit_exit_thresholds)
                if finite_time_exit_exit_thresholds
                else float("inf")
            ),
            loss_first_exit_threshold=(
                min(finite_loss_first_exit_thresholds)
                if finite_loss_first_exit_thresholds
                else float("inf")
            ),
            side_confidence_penalty=max(side_confidence_penalties),
            side_confidence_penalty_rules=parse_optional_csv_strings(
                args.side_confidence_penalty_rules
            ),
            side_confidence_overfit_penalty_rules=parse_optional_csv_strings(
                args.side_confidence_overfit_penalty_rules
            ),
            min_side_confidence=max(min_side_confidences),
            require_profit_barrier=any(require_profit_barriers),
            side_ev_penalty_rules=flatten_rule_sets(side_ev_penalty_rule_sets),
            side_ev_penalty_replacement_min_margin=max(
                [
                    value
                    for value in side_ev_penalty_replacement_min_margins
                    if np.isfinite(value)
                ],
                default=-float("inf"),
            ),
            extra_side_margin_rules=parse_optional_csv_strings(args.extra_side_margin_rules),
            side_extra_margin_rules=flatten_rule_sets(side_extra_margin_rule_sets),
            side_block_rules=flatten_rule_sets(side_block_rule_sets),
            context_drawdown_guard_loss_threshold=(
                min(finite_context_drawdown_guard_loss_thresholds)
                if finite_context_drawdown_guard_loss_thresholds
                else float("inf")
            ),
            context_drawdown_guard_context_columns=parse_csv_string_tuple(
                args.context_drawdown_guard_context_columns
            ),
            context_drawdown_guard_reset_monthly=args.context_drawdown_guard_reset_monthly,
            **regime_blocks,
        )
        preloaded_predictions = read_prediction_frame(
            args.predictions,
            read_config,
            drop_required_na=False,
        )
    rows: list[dict[str, object]] = []
    base_grid = product(
        policies,
        entry_thresholds,
        long_entry_threshold_offsets,
        short_entry_threshold_offsets,
        side_margins,
        risk_penalties,
        secondary_score_tie_margins,
        fixed_horizon_score_modes,
        min_predicted_hold_minutes_values,
        max_predicted_hold_minutes_values,
        min_valid_predicted_hold_minutes_values,
        max_wait_regrets,
        min_entry_ranks,
        min_trade_qualities,
        profit_barrier_miss_penalties,
        time_exit_penalties,
        loss_first_penalties,
        time_exit_holding_shrinks,
        loss_first_holding_shrinks,
        holding_shortening_thresholds,
        holding_shortening_cap_minutes_values,
        time_exit_exit_thresholds,
        loss_first_exit_thresholds,
        side_confidence_penalties,
        min_side_confidences,
        require_profit_barriers,
        side_ev_penalty_rule_sets,
        side_ev_penalty_replacement_min_margins,
        side_extra_margin_rule_sets,
        side_block_rule_sets,
        context_drawdown_guard_loss_thresholds,
        context_drawdown_guard_min_entry_margins,
    )
    for (
        policy,
        entry_threshold,
        long_entry_threshold_offset,
        short_entry_threshold_offset,
        side_margin,
        risk_penalty,
        secondary_score_tie_margin,
        fixed_horizon_score_mode,
        min_predicted_hold_minutes,
        max_predicted_hold_minutes,
        min_valid_predicted_hold_minutes,
        max_wait_regret,
        min_entry_rank,
        min_trade_quality,
        profit_barrier_miss_penalty,
        time_exit_penalty,
        loss_first_penalty,
        time_exit_holding_shrink,
        loss_first_holding_shrink,
        holding_shortening_threshold,
        holding_shortening_cap_minutes,
        time_exit_exit_threshold,
        loss_first_exit_threshold,
        side_confidence_penalty,
        min_side_confidence,
        require_profit_barrier,
        side_ev_penalty_rules,
        side_ev_penalty_replacement_min_margin,
        side_extra_margin_rules,
        side_block_rules,
        context_drawdown_guard_loss_threshold,
        context_drawdown_guard_min_entry_margin,
    ) in base_grid:
        if max_predicted_hold_minutes < min_predicted_hold_minutes:
            raise SystemExit(
                "max_predicted_hold_minutes must be greater than or equal to "
                "min_predicted_hold_minutes"
            )
        if np.isfinite(holding_shortening_threshold):
            if not 0 <= holding_shortening_threshold <= 1:
                raise SystemExit(
                    "holding_shortening_thresholds must contain values between 0 and 1 or inf"
                )
            if holding_shortening_cap_minutes <= 0:
                raise SystemExit("holding_shortening_cap_minutes must be positive")
        if np.isfinite(context_drawdown_guard_loss_threshold) and (
            context_drawdown_guard_loss_threshold <= 0
        ):
            raise SystemExit(
                "context_drawdown_guard_loss_thresholds must contain positive values or inf"
            )
        if (
            np.isfinite(context_drawdown_guard_min_entry_margin)
            and context_drawdown_guard_min_entry_margin < 0
        ):
            raise SystemExit(
                "context_drawdown_guard_min_entry_margins must contain non-negative values, inf, or -inf"
            )
        policy_exit_thresholds = exit_thresholds if policy == "stateful_ev" else [0.0]
        active_profit_barrier_thresholds = (
            profit_barrier_thresholds if require_profit_barrier else [0.5]
        )
        for exit_threshold in policy_exit_thresholds:
            for profit_barrier_threshold in active_profit_barrier_thresholds:
                model_policy_config = ModelPolicyConfig(
                    predictions=args.predictions,
                    policy=policy,
                    entry_threshold=entry_threshold,
                    long_entry_threshold_offset=long_entry_threshold_offset,
                    short_entry_threshold_offset=short_entry_threshold_offset,
                    exit_threshold=exit_threshold,
                    side_margin=side_margin,
                    long_column=args.long_column,
                    short_column=args.short_column,
                    long_risk_column=args.long_risk_column,
                    short_risk_column=args.short_risk_column,
                    risk_penalty=risk_penalty,
                    long_secondary_score_column=args.long_secondary_score_column,
                    short_secondary_score_column=args.short_secondary_score_column,
                    secondary_score_tie_margin=secondary_score_tie_margin,
                    long_holding_column=args.long_holding_column,
                    short_holding_column=args.short_holding_column,
                    min_predicted_hold_minutes=min_predicted_hold_minutes,
                    max_predicted_hold_minutes=max_predicted_hold_minutes,
                    min_valid_predicted_hold_minutes=min_valid_predicted_hold_minutes,
                    long_holding_fallback_column=args.long_holding_fallback_column,
                    short_holding_fallback_column=args.short_holding_fallback_column,
                    fixed_horizon_minutes=parse_csv_float_tuple(args.fixed_horizon_minutes),
                    long_fixed_horizon_columns=parse_csv_string_tuple(
                        args.long_fixed_horizon_columns
                    ),
                    short_fixed_horizon_columns=parse_csv_string_tuple(
                        args.short_fixed_horizon_columns
                    ),
                    fixed_horizon_score_mode=fixed_horizon_score_mode,
                    long_wait_regret_column=args.long_wait_regret_column,
                    short_wait_regret_column=args.short_wait_regret_column,
                    long_entry_rank_column=args.long_entry_rank_column,
                    short_entry_rank_column=args.short_entry_rank_column,
                    long_profit_barrier_column=args.long_profit_barrier_column,
                    short_profit_barrier_column=args.short_profit_barrier_column,
                    long_time_exit_column=args.long_time_exit_column,
                    short_time_exit_column=args.short_time_exit_column,
                    long_loss_first_column=args.long_loss_first_column,
                    short_loss_first_column=args.short_loss_first_column,
                    long_side_confidence_column=args.long_side_confidence_column,
                    short_side_confidence_column=args.short_side_confidence_column,
                    long_trade_quality_column=args.long_trade_quality_column,
                    short_trade_quality_column=args.short_trade_quality_column,
                    max_wait_regret=max_wait_regret,
                    min_entry_rank=min_entry_rank,
                    min_trade_quality=min_trade_quality,
                    profit_barrier_miss_penalty=profit_barrier_miss_penalty,
                    time_exit_penalty=time_exit_penalty,
                    loss_first_penalty=loss_first_penalty,
                    time_exit_holding_shrink=time_exit_holding_shrink,
                    loss_first_holding_shrink=loss_first_holding_shrink,
                    long_holding_shortening_column=args.long_holding_shortening_column,
                    short_holding_shortening_column=args.short_holding_shortening_column,
                    holding_shortening_threshold=holding_shortening_threshold,
                    holding_shortening_cap_minutes=holding_shortening_cap_minutes,
                    time_exit_exit_threshold=time_exit_exit_threshold,
                    loss_first_exit_threshold=loss_first_exit_threshold,
                    side_confidence_penalty=side_confidence_penalty,
                    side_confidence_penalty_rules=parse_optional_csv_strings(
                        args.side_confidence_penalty_rules
                    ),
                    side_confidence_overfit_penalty_rules=parse_optional_csv_strings(
                        args.side_confidence_overfit_penalty_rules
                    ),
                    min_side_confidence=min_side_confidence,
                    require_profit_barrier=require_profit_barrier,
                    profit_barrier_threshold=profit_barrier_threshold,
                    side_ev_penalty_rules=side_ev_penalty_rules,
                    side_ev_penalty_replacement_min_margin=(
                        side_ev_penalty_replacement_min_margin
                    ),
                    extra_side_margin_rules=parse_optional_csv_strings(args.extra_side_margin_rules),
                    side_extra_margin_rules=side_extra_margin_rules,
                    side_block_rules=side_block_rules,
                    context_drawdown_guard_loss_threshold=(
                        context_drawdown_guard_loss_threshold
                    ),
                    context_drawdown_guard_min_entry_margin=(
                        context_drawdown_guard_min_entry_margin
                    ),
                    context_drawdown_guard_context_columns=parse_csv_string_tuple(
                        args.context_drawdown_guard_context_columns
                    ),
                    context_drawdown_guard_reset_monthly=(
                        args.context_drawdown_guard_reset_monthly
                    ),
                    **regime_blocks,
                )
                metrics, _, _, _ = run_model_policy(
                    df,
                    backtest_config,
                    model_policy_config,
                    predictions=preloaded_predictions,
                )
                forced_exit_rate = (
                    0.0
                    if metrics["trade_count"] == 0
                    else float(metrics["forced_exit_count"] / metrics["trade_count"])
                )
                eligible = (
                    metrics["trade_count"] >= args.min_trades
                    and forced_exit_rate <= args.max_forced_exit_rate
                    and metrics["max_drawdown"] <= args.max_drawdown
                )
                row = {
                    "policy": policy,
                    "entry_threshold": entry_threshold,
                    "long_entry_threshold_offset": long_entry_threshold_offset,
                    "short_entry_threshold_offset": short_entry_threshold_offset,
                    "exit_threshold": exit_threshold,
                    "side_margin": side_margin,
                    "risk_penalty": risk_penalty,
                    "secondary_score_tie_margin": secondary_score_tie_margin,
                    "long_secondary_score_column": args.long_secondary_score_column,
                    "short_secondary_score_column": args.short_secondary_score_column,
                    "fixed_horizon_score_mode": fixed_horizon_score_mode,
                    "min_predicted_hold_minutes": min_predicted_hold_minutes,
                    "max_predicted_hold_minutes": max_predicted_hold_minutes,
                    "min_valid_predicted_hold_minutes": min_valid_predicted_hold_minutes,
                    "long_holding_fallback_column": args.long_holding_fallback_column,
                    "short_holding_fallback_column": args.short_holding_fallback_column,
                    "max_wait_regret": max_wait_regret,
                    "min_entry_rank": min_entry_rank,
                    "min_trade_quality": min_trade_quality,
                    "profit_barrier_miss_penalty": profit_barrier_miss_penalty,
                    "time_exit_penalty": time_exit_penalty,
                    "loss_first_penalty": loss_first_penalty,
                    "time_exit_holding_shrink": time_exit_holding_shrink,
                    "loss_first_holding_shrink": loss_first_holding_shrink,
                    "holding_shortening_threshold": holding_shortening_threshold,
                    "holding_shortening_cap_minutes": holding_shortening_cap_minutes,
                    "time_exit_exit_threshold": time_exit_exit_threshold,
                    "loss_first_exit_threshold": loss_first_exit_threshold,
                    "side_confidence_penalty": side_confidence_penalty,
                    "side_confidence_penalty_rules": regime_values_to_string(
                        model_policy_config.side_confidence_penalty_rules
                    ),
                    "side_confidence_overfit_penalty_rules": regime_values_to_string(
                        model_policy_config.side_confidence_overfit_penalty_rules
                    ),
                    "min_side_confidence": min_side_confidence,
                    "require_profit_barrier": require_profit_barrier,
                    "profit_barrier_threshold": profit_barrier_threshold,
                    "side_ev_penalty_rules": regime_values_to_string(
                        model_policy_config.side_ev_penalty_rules
                    ),
                    "side_ev_penalty_replacement_min_margin": (
                        side_ev_penalty_replacement_min_margin
                    ),
                    "extra_side_margin_rules": regime_values_to_string(
                        model_policy_config.extra_side_margin_rules
                    ),
                    "side_extra_margin_rules": regime_values_to_string(
                        model_policy_config.side_extra_margin_rules
                    ),
                    "side_block_rules": regime_values_to_string(
                        model_policy_config.side_block_rules
                    ),
                    "context_drawdown_guard_loss_threshold": (
                        context_drawdown_guard_loss_threshold
                    ),
                    "context_drawdown_guard_min_entry_margin": (
                        context_drawdown_guard_min_entry_margin
                    ),
                    "context_drawdown_guard_context_columns": regime_values_to_string(
                        model_policy_config.context_drawdown_guard_context_columns
                    ),
                    "context_drawdown_guard_reset_monthly": (
                        model_policy_config.context_drawdown_guard_reset_monthly
                    ),
                    **regime_block_metric_columns(model_policy_config),
                    "forced_exit_rate": forced_exit_rate,
                    "eligible": bool(eligible),
                    **metrics,
                }
                rows.append(row)

    metrics_frame = pd.DataFrame(rows).sort_values(
        ["eligible", "total_adjusted_pnl"],
        ascending=[False, False],
    )
    metrics_frame.to_csv(run_dir / "metrics.csv", index=False)
    metadata = {
        "predictions": str(args.predictions),
        "month": args.month,
        "policies": policies,
        "entry_thresholds": entry_thresholds,
        "long_entry_threshold_offsets": long_entry_threshold_offsets,
        "short_entry_threshold_offsets": short_entry_threshold_offsets,
        "exit_thresholds": exit_thresholds,
        "side_margins": side_margins,
        "risk_penalties": risk_penalties,
        "secondary_score_tie_margins": secondary_score_tie_margins,
        "long_secondary_score_column": args.long_secondary_score_column,
        "short_secondary_score_column": args.short_secondary_score_column,
        "profit_barrier_miss_penalties": profit_barrier_miss_penalties,
        "time_exit_penalties": time_exit_penalties,
        "loss_first_penalties": loss_first_penalties,
        "time_exit_holding_shrinks": time_exit_holding_shrinks,
        "loss_first_holding_shrinks": loss_first_holding_shrinks,
        "holding_shortening_thresholds": holding_shortening_thresholds,
        "holding_shortening_cap_minutes": holding_shortening_cap_minutes_values,
        "long_holding_shortening_column": args.long_holding_shortening_column,
        "short_holding_shortening_column": args.short_holding_shortening_column,
        "time_exit_exit_thresholds": time_exit_exit_thresholds,
        "loss_first_exit_thresholds": loss_first_exit_thresholds,
        "side_confidence_penalties": side_confidence_penalties,
        "side_confidence_penalty_rules": parse_optional_csv_strings(
            args.side_confidence_penalty_rules
        ),
        "side_confidence_overfit_penalty_rules": parse_optional_csv_strings(
            args.side_confidence_overfit_penalty_rules
        ),
        "fixed_horizon_score_modes": fixed_horizon_score_modes,
        "min_predicted_hold_minutes": min_predicted_hold_minutes_values,
        "max_predicted_hold_minutes": max_predicted_hold_minutes_values,
        "min_valid_predicted_hold_minutes": min_valid_predicted_hold_minutes_values,
        "max_wait_regrets": max_wait_regrets,
        "min_entry_ranks": min_entry_ranks,
        "min_trade_qualities": min_trade_qualities,
        "min_side_confidences": min_side_confidences,
        "require_profit_barriers": require_profit_barriers,
        "profit_barrier_thresholds": profit_barrier_thresholds,
        "side_ev_penalty_rules": parse_optional_csv_strings(args.side_ev_penalty_rules),
        "side_ev_penalty_rule_sets": [
            regime_values_to_string(values) for values in side_ev_penalty_rule_sets
        ],
        "side_ev_penalty_replacement_min_margins": (
            side_ev_penalty_replacement_min_margins
        ),
        "extra_side_margin_rules": parse_optional_csv_strings(args.extra_side_margin_rules),
        "side_extra_margin_rules": parse_optional_csv_strings(args.side_extra_margin_rules),
        "side_extra_margin_rule_sets": [
            regime_values_to_string(values) for values in side_extra_margin_rule_sets
        ],
        "side_block_rules": parse_optional_csv_strings(args.side_block_rules),
        "side_block_rule_sets": [
            regime_values_to_string(values) for values in side_block_rule_sets
        ],
        "context_drawdown_guard_loss_thresholds": (
            context_drawdown_guard_loss_thresholds
        ),
        "context_drawdown_guard_min_entry_margins": (
            context_drawdown_guard_min_entry_margins
        ),
        "context_drawdown_guard_context_columns": parse_csv_string_tuple(
            args.context_drawdown_guard_context_columns
        ),
        "context_drawdown_guard_reset_monthly": args.context_drawdown_guard_reset_monthly,
        **{field: list(values) for field, values in regime_blocks.items()},
        "min_trades": args.min_trades,
        "max_forced_exit_rate": args.max_forced_exit_rate,
        "max_drawdown": args.max_drawdown,
        "long_column": args.long_column,
        "short_column": args.short_column,
        "long_risk_column": args.long_risk_column,
        "short_risk_column": args.short_risk_column,
        "long_holding_column": args.long_holding_column,
        "short_holding_column": args.short_holding_column,
        "long_holding_fallback_column": args.long_holding_fallback_column,
        "short_holding_fallback_column": args.short_holding_fallback_column,
        "fixed_horizon_minutes": parse_csv_floats(args.fixed_horizon_minutes),
        "long_fixed_horizon_columns": parse_csv_strings(args.long_fixed_horizon_columns),
        "short_fixed_horizon_columns": parse_csv_strings(args.short_fixed_horizon_columns),
        "long_wait_regret_column": args.long_wait_regret_column,
        "short_wait_regret_column": args.short_wait_regret_column,
        "long_entry_rank_column": args.long_entry_rank_column,
        "short_entry_rank_column": args.short_entry_rank_column,
        "long_profit_barrier_column": args.long_profit_barrier_column,
        "short_profit_barrier_column": args.short_profit_barrier_column,
        "long_time_exit_column": args.long_time_exit_column,
        "short_time_exit_column": args.short_time_exit_column,
        "long_loss_first_column": args.long_loss_first_column,
        "short_loss_first_column": args.short_loss_first_column,
        "long_side_confidence_column": args.long_side_confidence_column,
        "short_side_confidence_column": args.short_side_confidence_column,
        "long_trade_quality_column": args.long_trade_quality_column,
        "short_trade_quality_column": args.short_trade_quality_column,
    }
    with (run_dir / "config.json").open("w", encoding="utf-8") as handle:
        json.dump(metadata, handle, ensure_ascii=False, indent=2)
    print(metrics_frame.head(args.top_n).to_string(index=False))
    print(f"artifacts: {run_dir}")
    return 0


def normalize_sweep_metrics(frame: pd.DataFrame, source: str) -> pd.DataFrame:
    output = frame.copy()
    if "risk_penalty" not in output.columns:
        output["risk_penalty"] = 0.0
    if "profit_barrier_miss_penalty" not in output.columns:
        output["profit_barrier_miss_penalty"] = 0.0
    if "time_exit_penalty" not in output.columns:
        output["time_exit_penalty"] = 0.0
    if "loss_first_penalty" not in output.columns:
        output["loss_first_penalty"] = 0.0
    if "time_exit_holding_shrink" not in output.columns:
        output["time_exit_holding_shrink"] = 0.0
    if "loss_first_holding_shrink" not in output.columns:
        output["loss_first_holding_shrink"] = 0.0
    if "holding_shortening_threshold" not in output.columns:
        output["holding_shortening_threshold"] = float("inf")
    if "holding_shortening_cap_minutes" not in output.columns:
        output["holding_shortening_cap_minutes"] = 60.0
    if "time_exit_exit_threshold" not in output.columns:
        output["time_exit_exit_threshold"] = float("inf")
    if "loss_first_exit_threshold" not in output.columns:
        output["loss_first_exit_threshold"] = float("inf")
    if "side_confidence_penalty" not in output.columns:
        output["side_confidence_penalty"] = 0.0
    if "side_confidence_penalty_rules" not in output.columns:
        output["side_confidence_penalty_rules"] = ""
    if "side_confidence_overfit_penalty_rules" not in output.columns:
        output["side_confidence_overfit_penalty_rules"] = ""
    if "min_side_confidence" not in output.columns:
        output["min_side_confidence"] = 0.0
    if "fixed_horizon_score_mode" not in output.columns:
        output["fixed_horizon_score_mode"] = "max"
    if "min_predicted_hold_minutes" not in output.columns:
        output["min_predicted_hold_minutes"] = 1.0
    if "max_predicted_hold_minutes" not in output.columns:
        output["max_predicted_hold_minutes"] = 1440.0
    if "min_valid_predicted_hold_minutes" not in output.columns:
        output["min_valid_predicted_hold_minutes"] = -float("inf")
    if "long_holding_fallback_column" not in output.columns:
        output["long_holding_fallback_column"] = ""
    if "short_holding_fallback_column" not in output.columns:
        output["short_holding_fallback_column"] = ""
    if "long_entry_threshold_offset" not in output.columns:
        output["long_entry_threshold_offset"] = 0.0
    if "short_entry_threshold_offset" not in output.columns:
        output["short_entry_threshold_offset"] = 0.0
    if "secondary_score_tie_margin" not in output.columns:
        output["secondary_score_tie_margin"] = -float("inf")
    if "long_secondary_score_column" not in output.columns:
        output["long_secondary_score_column"] = ""
    if "short_secondary_score_column" not in output.columns:
        output["short_secondary_score_column"] = ""
    if "max_wait_regret" not in output.columns:
        output["max_wait_regret"] = float("inf")
    if "min_entry_rank" not in output.columns:
        output["min_entry_rank"] = 0.0
    if "min_trade_quality" not in output.columns:
        output["min_trade_quality"] = -float("inf")
    if "require_profit_barrier" not in output.columns:
        output["require_profit_barrier"] = False
    if "profit_barrier_threshold" not in output.columns:
        output["profit_barrier_threshold"] = 0.5
    if "side_ev_penalty_rules" not in output.columns:
        output["side_ev_penalty_rules"] = ""
    if "side_ev_penalty_replacement_min_margin" not in output.columns:
        output["side_ev_penalty_replacement_min_margin"] = -float("inf")
    if "extra_side_margin_rules" not in output.columns:
        output["extra_side_margin_rules"] = ""
    if "side_extra_margin_rules" not in output.columns:
        output["side_extra_margin_rules"] = ""
    if "side_block_rules" not in output.columns:
        output["side_block_rules"] = ""
    if "direction_session_adjusted_pnl_min" not in output.columns:
        output["direction_session_adjusted_pnl_min"] = np.inf
    if "worst_direction_session" not in output.columns:
        output["worst_direction_session"] = ""
    if "worst_direction_session_trade_count" not in output.columns:
        output["worst_direction_session_trade_count"] = 0
    if "combined_regime_adjusted_pnl_min" not in output.columns:
        output["combined_regime_adjusted_pnl_min"] = np.inf
    if "worst_combined_regime" not in output.columns:
        output["worst_combined_regime"] = ""
    if "worst_combined_regime_trade_count" not in output.columns:
        output["worst_combined_regime_trade_count"] = 0
    if "direction_combined_regime_adjusted_pnl_min" not in output.columns:
        output["direction_combined_regime_adjusted_pnl_min"] = np.inf
    if "worst_direction_combined_regime" not in output.columns:
        output["worst_direction_combined_regime"] = ""
    if "worst_direction_combined_regime_trade_count" not in output.columns:
        output["worst_direction_combined_regime_trade_count"] = 0
    for column in SIDE_EXPOSURE_DIAGNOSTIC_COLUMNS:
        if column not in output.columns:
            output[column] = 0.0
    for column in TRADE_ANALYSIS_DIAGNOSTIC_COLUMNS:
        if column not in output.columns:
            output[column] = 0.0
    if {"long_trade_count", "trade_count"}.issubset(output.columns):
        trade_count = output["trade_count"].replace(0, np.nan)
        output["long_trade_share"] = output["long_trade_share"].mask(
            output["long_trade_share"].isna() | (output["long_trade_share"] == 0),
            output["long_trade_count"] / trade_count,
        )
    if {"short_trade_count", "trade_count"}.issubset(output.columns):
        trade_count = output["trade_count"].replace(0, np.nan)
        output["short_trade_share"] = output["short_trade_share"].mask(
            output["short_trade_share"].isna() | (output["short_trade_share"] == 0),
            output["short_trade_count"] / trade_count,
        )
    output["max_side_trade_share"] = output["max_side_trade_share"].mask(
        output["max_side_trade_share"].isna() | (output["max_side_trade_share"] == 0),
        output[["long_trade_share", "short_trade_share"]].max(axis=1),
    )
    late_defaults: dict[str, object] = {}
    for column in PROFIT_BARRIER_DIAGNOSTIC_COLUMNS:
        if column not in output.columns:
            late_defaults[column] = 0.0
    for column in PROFIT_BARRIER_CALIBRATION_COLUMNS:
        if column not in output.columns:
            late_defaults[column] = 0.0
    for column in PROFIT_BARRIER_CALIBRATION_STRING_COLUMNS:
        if column not in output.columns:
            late_defaults[column] = ""
    for field, _ in REGIME_BLOCK_FIELDS:
        if field not in output.columns:
            late_defaults[field] = ""
    if "context_drawdown_guard_loss_threshold" not in output.columns:
        late_defaults["context_drawdown_guard_loss_threshold"] = float("inf")
    if "context_drawdown_guard_min_entry_margin" not in output.columns:
        late_defaults["context_drawdown_guard_min_entry_margin"] = float("inf")
    if "context_drawdown_guard_context_columns" not in output.columns:
        late_defaults["context_drawdown_guard_context_columns"] = "combined_regime,session_regime"
    if "context_drawdown_guard_reset_monthly" not in output.columns:
        late_defaults["context_drawdown_guard_reset_monthly"] = True
    if "forced_exit_rate" not in output.columns:
        trade_count = output["trade_count"].replace(0, np.nan)
        late_defaults["forced_exit_rate"] = (
            output["forced_exit_count"] / trade_count
        ).fillna(0.0)
    if "sweep_source" in output.columns:
        output["sweep_source"] = output["sweep_source"].fillna(source)
    else:
        late_defaults["sweep_source"] = source
    if late_defaults:
        output = pd.concat(
            [output, pd.DataFrame(late_defaults, index=output.index)],
            axis=1,
        )

    required = [
        *SWEEP_KEY_COLUMNS,
        "total_adjusted_pnl",
        "total_raw_pnl",
        "trade_count",
        "win_rate",
        "max_drawdown",
        "forced_exit_rate",
        "forced_exit_count",
    ]
    missing = sorted(set(required) - set(output.columns))
    if missing:
        raise ValueError(f"sweep metrics missing columns: {', '.join(missing)}")
    numeric_columns = [
        "entry_threshold",
        "long_entry_threshold_offset",
        "short_entry_threshold_offset",
        "exit_threshold",
        "side_margin",
        "risk_penalty",
        "secondary_score_tie_margin",
        "side_ev_penalty_replacement_min_margin",
        "context_drawdown_guard_loss_threshold",
        "context_drawdown_guard_min_entry_margin",
        "min_predicted_hold_minutes",
        "max_predicted_hold_minutes",
        "profit_barrier_miss_penalty",
        "time_exit_penalty",
        "loss_first_penalty",
        "time_exit_holding_shrink",
        "loss_first_holding_shrink",
        "time_exit_exit_threshold",
        "loss_first_exit_threshold",
        "max_wait_regret",
        "min_entry_rank",
        "min_trade_quality",
        "profit_barrier_threshold",
        "side_confidence_penalty",
        "min_side_confidence",
        "total_adjusted_pnl",
        "total_raw_pnl",
        "trade_count",
        "win_rate",
        "max_drawdown",
        "forced_exit_rate",
        "forced_exit_count",
        "direction_session_adjusted_pnl_min",
        "worst_direction_session_trade_count",
        "combined_regime_adjusted_pnl_min",
        "worst_combined_regime_trade_count",
        "direction_combined_regime_adjusted_pnl_min",
        "worst_direction_combined_regime_trade_count",
        *SIDE_EXPOSURE_DIAGNOSTIC_COLUMNS,
        *PROFIT_BARRIER_DIAGNOSTIC_COLUMNS,
        *PROFIT_BARRIER_CALIBRATION_SUMMARY_COLUMNS,
    ]
    for column in numeric_columns:
        errors = "coerce" if column in COERCED_NUMERIC_DIAGNOSTIC_COLUMNS else "raise"
        output[column] = pd.to_numeric(output[column], errors=errors)
    output["direction_session_adjusted_pnl_min"] = output[
        "direction_session_adjusted_pnl_min"
    ].fillna(np.inf)
    output["worst_direction_session_trade_count"] = output[
        "worst_direction_session_trade_count"
    ].fillna(0)
    output["combined_regime_adjusted_pnl_min"] = output[
        "combined_regime_adjusted_pnl_min"
    ].fillna(np.inf)
    output["worst_combined_regime_trade_count"] = output[
        "worst_combined_regime_trade_count"
    ].fillna(0)
    output["direction_combined_regime_adjusted_pnl_min"] = output[
        "direction_combined_regime_adjusted_pnl_min"
    ].fillna(np.inf)
    output["worst_direction_combined_regime_trade_count"] = output[
        "worst_direction_combined_regime_trade_count"
    ].fillna(0)
    for column in SIDE_EXPOSURE_DIAGNOSTIC_COLUMNS:
        output[column] = output[column].fillna(0.0)
    for column in TRADE_ANALYSIS_DIAGNOSTIC_COLUMNS:
        output[column] = output[column].fillna(0.0)
    for column in PROFIT_BARRIER_DIAGNOSTIC_COLUMNS:
        output[column] = output[column].fillna(0.0)
    for column in PROFIT_BARRIER_CALIBRATION_COLUMNS:
        output[column] = output[column].fillna(0.0)
    if output["require_profit_barrier"].dtype == object:
        output["require_profit_barrier"] = output["require_profit_barrier"].map(
            lambda value: str(value).strip().lower() in {"1", "true", "yes", "y"}
        )
    else:
        output["require_profit_barrier"] = output["require_profit_barrier"].astype(bool)
    if output["context_drawdown_guard_reset_monthly"].dtype == object:
        output["context_drawdown_guard_reset_monthly"] = output[
            "context_drawdown_guard_reset_monthly"
        ].map(lambda value: str(value).strip().lower() in {"1", "true", "yes", "y"})
    else:
        output["context_drawdown_guard_reset_monthly"] = output[
            "context_drawdown_guard_reset_monthly"
        ].astype(bool)
    output["extra_side_margin_rules"] = output["extra_side_margin_rules"].fillna("").astype(str)
    output["side_ev_penalty_rules"] = output["side_ev_penalty_rules"].fillna("").astype(str)
    output["side_extra_margin_rules"] = output["side_extra_margin_rules"].fillna("").astype(str)
    output["side_block_rules"] = output["side_block_rules"].fillna("").astype(str)
    output["context_drawdown_guard_context_columns"] = (
        output["context_drawdown_guard_context_columns"].fillna("").astype(str)
    )
    output["long_secondary_score_column"] = (
        output["long_secondary_score_column"].fillna("").astype(str)
    )
    output["short_secondary_score_column"] = (
        output["short_secondary_score_column"].fillna("").astype(str)
    )
    output["side_confidence_penalty_rules"] = (
        output["side_confidence_penalty_rules"].fillna("").astype(str)
    )
    output["side_confidence_overfit_penalty_rules"] = (
        output["side_confidence_overfit_penalty_rules"].fillna("").astype(str)
    )
    output["fixed_horizon_score_mode"] = output["fixed_horizon_score_mode"].fillna("max").astype(str)
    output["worst_direction_session"] = output["worst_direction_session"].fillna("").astype(str)
    output["worst_combined_regime"] = output["worst_combined_regime"].fillna("").astype(str)
    output["worst_direction_combined_regime"] = (
        output["worst_direction_combined_regime"].fillna("").astype(str)
    )
    for column in PROFIT_BARRIER_CALIBRATION_STRING_COLUMNS:
        output[column] = output[column].fillna("").astype(str)
    for field, _ in REGIME_BLOCK_FIELDS:
        output[field] = output[field].fillna("").astype(str)
    return output


def summarize_sweep_frames(
    frames: list[pd.DataFrame],
    min_folds: int,
    min_trades_per_fold: int,
    max_forced_exit_rate: float,
    max_drawdown: float,
    min_adjusted_pnl_per_fold: float,
    sort_by: str,
) -> pd.DataFrame:
    if min_folds <= 0:
        raise ValueError("min_folds must be positive")
    if not frames:
        raise ValueError("at least one sweep frame is required")
    metrics = pd.concat(
        [normalize_sweep_metrics(frame, f"frame_{index}") for index, frame in enumerate(frames)],
        ignore_index=True,
    ).copy()
    metrics["fold_eligible"] = (
        (metrics["trade_count"] >= min_trades_per_fold)
        & (metrics["forced_exit_rate"] <= max_forced_exit_rate)
        & (metrics["max_drawdown"] <= max_drawdown)
        & (metrics["total_adjusted_pnl"] >= min_adjusted_pnl_per_fold)
    )

    grouped = metrics.groupby(SWEEP_KEY_COLUMNS, dropna=False)
    aggregations: dict[str, tuple[str, str]] = {
        "fold_count": ("sweep_source", "nunique"),
        "eligible_fold_count": ("fold_eligible", "sum"),
        "total_adjusted_pnl_mean": ("total_adjusted_pnl", "mean"),
        "total_adjusted_pnl_median": ("total_adjusted_pnl", "median"),
        "total_adjusted_pnl_min": ("total_adjusted_pnl", "min"),
        "total_adjusted_pnl_sum": ("total_adjusted_pnl", "sum"),
        "total_adjusted_pnl_std": ("total_adjusted_pnl", "std"),
        "total_raw_pnl_mean": ("total_raw_pnl", "mean"),
        "total_raw_pnl_min": ("total_raw_pnl", "min"),
        "trade_count_mean": ("trade_count", "mean"),
        "trade_count_min": ("trade_count", "min"),
        "win_rate_mean": ("win_rate", "mean"),
        "max_drawdown_mean": ("max_drawdown", "mean"),
        "max_drawdown_max": ("max_drawdown", "max"),
        "forced_exit_rate_mean": ("forced_exit_rate", "mean"),
        "forced_exit_rate_max": ("forced_exit_rate", "max"),
        "forced_exit_count_sum": ("forced_exit_count", "sum"),
    }
    optional_metric_columns = [
        "long_adjusted_pnl",
        "short_adjusted_pnl",
        "long_trade_count",
        "short_trade_count",
        *SIDE_EXPOSURE_DIAGNOSTIC_COLUMNS,
        "spread_points",
        "slippage_points",
        "execution_delay_bars",
        "direction_session_adjusted_pnl_min",
        "worst_direction_session_trade_count",
        "combined_regime_adjusted_pnl_min",
        "worst_combined_regime_trade_count",
        "direction_combined_regime_adjusted_pnl_min",
        "worst_direction_combined_regime_trade_count",
        *TRADE_ANALYSIS_DIAGNOSTIC_COLUMNS,
        *PROFIT_BARRIER_DIAGNOSTIC_COLUMNS,
        *PROFIT_BARRIER_CALIBRATION_SUMMARY_COLUMNS,
    ]
    for column in optional_metric_columns:
        if column in metrics.columns:
            aggregations[f"{column}_mean"] = (column, "mean")
            aggregations[f"{column}_min"] = (column, "min")
            aggregations[f"{column}_max"] = (column, "max")

    summary = grouped.agg(
        **aggregations,
    ).reset_index()
    summary["total_adjusted_pnl_std"] = summary["total_adjusted_pnl_std"].fillna(0.0)
    summary["eligible"] = (
        (summary["fold_count"] >= min_folds)
        & (summary["eligible_fold_count"] == summary["fold_count"])
    )

    sort_options = {
        "mean_pnl": ["eligible", "total_adjusted_pnl_mean", "total_adjusted_pnl_min"],
        "min_pnl": ["eligible", "total_adjusted_pnl_min", "total_adjusted_pnl_mean"],
        "sum_pnl": ["eligible", "total_adjusted_pnl_sum", "total_adjusted_pnl_min"],
    }
    if sort_by not in sort_options:
        raise ValueError(f"unknown sort_by: {sort_by}")
    summary = summary.sort_values(
        sort_options[sort_by],
        ascending=[False, False, False],
    ).reset_index(drop=True)
    return summary


def prefixed_summary(summary: pd.DataFrame, suffix: str) -> pd.DataFrame:
    rename = {
        column: f"{column}_{suffix}"
        for column in summary.columns
        if column not in SWEEP_KEY_COLUMNS
    }
    return summary.rename(columns=rename)


def row_min_or_default(frame: pd.DataFrame, columns: list[str], default: float) -> pd.Series:
    existing = [column for column in columns if column in frame.columns]
    if not existing:
        return pd.Series(default, index=frame.index, dtype="float64")
    return frame[existing].min(axis=1)


def row_max_or_default(frame: pd.DataFrame, columns: list[str], default: float) -> pd.Series:
    existing = [column for column in columns if column in frame.columns]
    if not existing:
        return pd.Series(default, index=frame.index, dtype="float64")
    return frame[existing].max(axis=1)


def row_gap_from_best(frame: pd.DataFrame, value_column: str, eligible_column: str) -> pd.Series:
    eligible_values = frame.loc[frame[eligible_column].astype(bool), value_column]
    if eligible_values.empty:
        return pd.Series(np.inf, index=frame.index, dtype="float64")
    return float(eligible_values.max()) - frame[value_column]


def loss_depth(series: pd.Series) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce").replace(np.inf, np.nan)
    return (-values.fillna(0.0)).clip(lower=0.0)


def plateau_support_counts(
    frame: pd.DataFrame,
    plateau_column: str,
    plateau_radius: float,
    eligible_column: str,
) -> pd.Series:
    if plateau_column not in SWEEP_KEY_COLUMNS:
        raise ValueError(f"plateau column must be a sweep key: {plateau_column}")
    if plateau_radius < 0:
        raise ValueError("plateau_radius must be non-negative")
    if frame.empty:
        return pd.Series(dtype="int64")

    support = pd.Series(0, index=frame.index, dtype="int64")
    group_columns = [column for column in SWEEP_KEY_COLUMNS if column != plateau_column]
    numeric_plateau_values = pd.to_numeric(frame[plateau_column], errors="coerce")
    use_numeric_distance = numeric_plateau_values.notna().all()
    plateau_values = (
        numeric_plateau_values
        if use_numeric_distance
        else frame[plateau_column].fillna("").astype(str)
    )
    for _, group in frame.groupby(group_columns, dropna=False):
        eligible_indices = group.index[frame.loc[group.index, eligible_column].to_numpy()]
        if len(eligible_indices) == 0:
            continue
        eligible_values = plateau_values.loc[eligible_indices]
        for index in group.index:
            if use_numeric_distance:
                distance = (eligible_values - plateau_values.loc[index]).abs()
                support.loc[index] = int(((distance > 0) & (distance <= plateau_radius)).sum())
            else:
                same_category = eligible_values == plateau_values.loc[index]
                support.loc[index] = int(same_category.drop(index, errors="ignore").sum())
    return support


def summarize_candidate_selection(
    base_frames: list[pd.DataFrame],
    cost_frames: list[pd.DataFrame],
    min_folds: int,
    min_trades_per_fold: int,
    max_forced_exit_rate: float,
    max_drawdown: float,
    min_base_adjusted_pnl_per_fold: float,
    min_cost_adjusted_pnl_per_fold: float,
    max_cost_pnl_drop: float,
    max_side_loss_per_fold: float,
    plateau_column: str,
    plateau_radius: float,
    min_plateau_neighbors: int,
    max_direction_session_loss_per_fold: float = 1e100,
    max_combined_regime_loss_per_fold: float = 1e100,
    max_direction_combined_regime_loss_per_fold: float = 1e100,
    max_predicted_profit_barrier_miss_rate: float = 1.0,
    max_actual_profit_barrier_miss_rate: float = 1.0,
    max_profit_barrier_calibration_overestimate: float = 1.0,
    max_short_trade_share: float = 1.0,
    max_side_trade_share: float = 1.0,
    max_smoothed_actual_profit_barrier_miss_rate: float = 1.0,
    max_smoothed_profit_barrier_calibration_overestimate: float = 1.0,
    max_direction_error_rate: float = 1.0,
    max_predicted_side_error_rate: float = 1.0,
    max_no_edge_rate: float = 1.0,
    max_exit_regret_mean: float = 1e100,
    max_ev_overestimate_vs_realized_mean: float = 1e100,
    group_loss_penalty_weight: float = 0.0,
    diagnostic_penalty_weight: float = 0.0,
    diagnostic_direction_error_rate_threshold: float = 1.0,
    diagnostic_actual_profit_barrier_miss_rate_threshold: float = 1.0,
    diagnostic_ev_overestimate_vs_realized_mean_threshold: float = 1e100,
    diagnostic_direction_error_rate_scale: float = 100.0,
    diagnostic_actual_profit_barrier_miss_rate_scale: float = 100.0,
    diagnostic_ev_overestimate_vs_realized_mean_scale: float = 1.0,
    candidate_rank_mode: str = "pnl",
    near_top_cost_pnl_tolerance: float = 0.0,
    near_top_group_loss_weight: float = 1.0,
    near_top_drawdown_weight: float = 1.0,
    near_top_ev_overestimate_weight: float = 1.0,
    near_top_exit_regret_weight: float = 1.0,
    near_top_actual_miss_weight: float = 100.0,
    near_top_side_share_weight: float = 100.0,
    near_top_pnl_stability_weight: float = 0.0,
    stress_cost_pnl_sum_reward_weight: float = 0.0,
    stress_base_pnl_sum_reward_weight: float = 0.0,
    min_base_folds: int | None = None,
    min_cost_folds: int | None = None,
) -> pd.DataFrame:
    if max_cost_pnl_drop < 0:
        raise ValueError("max_cost_pnl_drop must be non-negative")
    if max_side_loss_per_fold < 0:
        raise ValueError("max_side_loss_per_fold must be non-negative")
    if max_direction_session_loss_per_fold < 0:
        raise ValueError("max_direction_session_loss_per_fold must be non-negative")
    if max_combined_regime_loss_per_fold < 0:
        raise ValueError("max_combined_regime_loss_per_fold must be non-negative")
    if max_direction_combined_regime_loss_per_fold < 0:
        raise ValueError("max_direction_combined_regime_loss_per_fold must be non-negative")
    if not 0 <= max_predicted_profit_barrier_miss_rate <= 1:
        raise ValueError("max_predicted_profit_barrier_miss_rate must be between 0 and 1")
    if not 0 <= max_actual_profit_barrier_miss_rate <= 1:
        raise ValueError("max_actual_profit_barrier_miss_rate must be between 0 and 1")
    if not 0 <= max_profit_barrier_calibration_overestimate <= 1:
        raise ValueError("max_profit_barrier_calibration_overestimate must be between 0 and 1")
    if not 0 <= max_short_trade_share <= 1:
        raise ValueError("max_short_trade_share must be between 0 and 1")
    if not 0 <= max_side_trade_share <= 1:
        raise ValueError("max_side_trade_share must be between 0 and 1")
    if not 0 <= max_smoothed_actual_profit_barrier_miss_rate <= 1:
        raise ValueError("max_smoothed_actual_profit_barrier_miss_rate must be between 0 and 1")
    if not 0 <= max_smoothed_profit_barrier_calibration_overestimate <= 1:
        raise ValueError(
            "max_smoothed_profit_barrier_calibration_overestimate must be between 0 and 1"
        )
    if not 0 <= max_direction_error_rate <= 1:
        raise ValueError("max_direction_error_rate must be between 0 and 1")
    if not 0 <= max_predicted_side_error_rate <= 1:
        raise ValueError("max_predicted_side_error_rate must be between 0 and 1")
    if not 0 <= max_no_edge_rate <= 1:
        raise ValueError("max_no_edge_rate must be between 0 and 1")
    if max_exit_regret_mean < 0:
        raise ValueError("max_exit_regret_mean must be non-negative")
    if max_ev_overestimate_vs_realized_mean < 0:
        raise ValueError("max_ev_overestimate_vs_realized_mean must be non-negative")
    if group_loss_penalty_weight < 0:
        raise ValueError("group_loss_penalty_weight must be non-negative")
    if diagnostic_penalty_weight < 0:
        raise ValueError("diagnostic_penalty_weight must be non-negative")
    if not 0 <= diagnostic_direction_error_rate_threshold <= 1:
        raise ValueError("diagnostic_direction_error_rate_threshold must be between 0 and 1")
    if not 0 <= diagnostic_actual_profit_barrier_miss_rate_threshold <= 1:
        raise ValueError(
            "diagnostic_actual_profit_barrier_miss_rate_threshold must be between 0 and 1"
        )
    if diagnostic_ev_overestimate_vs_realized_mean_threshold < 0:
        raise ValueError(
            "diagnostic_ev_overestimate_vs_realized_mean_threshold must be non-negative"
        )
    if diagnostic_direction_error_rate_scale < 0:
        raise ValueError("diagnostic_direction_error_rate_scale must be non-negative")
    if diagnostic_actual_profit_barrier_miss_rate_scale < 0:
        raise ValueError("diagnostic_actual_profit_barrier_miss_rate_scale must be non-negative")
    if diagnostic_ev_overestimate_vs_realized_mean_scale < 0:
        raise ValueError(
            "diagnostic_ev_overestimate_vs_realized_mean_scale must be non-negative"
        )
    if candidate_rank_mode not in CANDIDATE_RANK_MODES:
        raise ValueError(f"unknown candidate_rank_mode: {candidate_rank_mode}")
    if near_top_cost_pnl_tolerance < 0:
        raise ValueError("near_top_cost_pnl_tolerance must be non-negative")
    if near_top_group_loss_weight < 0:
        raise ValueError("near_top_group_loss_weight must be non-negative")
    if near_top_drawdown_weight < 0:
        raise ValueError("near_top_drawdown_weight must be non-negative")
    if near_top_ev_overestimate_weight < 0:
        raise ValueError("near_top_ev_overestimate_weight must be non-negative")
    if near_top_exit_regret_weight < 0:
        raise ValueError("near_top_exit_regret_weight must be non-negative")
    if near_top_actual_miss_weight < 0:
        raise ValueError("near_top_actual_miss_weight must be non-negative")
    if near_top_side_share_weight < 0:
        raise ValueError("near_top_side_share_weight must be non-negative")
    if near_top_pnl_stability_weight < 0:
        raise ValueError("near_top_pnl_stability_weight must be non-negative")
    if stress_cost_pnl_sum_reward_weight < 0:
        raise ValueError("stress_cost_pnl_sum_reward_weight must be non-negative")
    if stress_base_pnl_sum_reward_weight < 0:
        raise ValueError("stress_base_pnl_sum_reward_weight must be non-negative")
    if min_plateau_neighbors < 0:
        raise ValueError("min_plateau_neighbors must be non-negative")
    base_min_folds = min_folds if min_base_folds is None else min_base_folds
    cost_min_folds = min_folds if min_cost_folds is None else min_cost_folds
    if base_min_folds <= 0:
        raise ValueError("min_base_folds must be positive")
    if cost_min_folds <= 0:
        raise ValueError("min_cost_folds must be positive")

    base_summary = summarize_sweep_frames(
        frames=base_frames,
        min_folds=base_min_folds,
        min_trades_per_fold=min_trades_per_fold,
        max_forced_exit_rate=max_forced_exit_rate,
        max_drawdown=max_drawdown,
        min_adjusted_pnl_per_fold=min_base_adjusted_pnl_per_fold,
        sort_by="min_pnl",
    )
    cost_summary = summarize_sweep_frames(
        frames=cost_frames,
        min_folds=cost_min_folds,
        min_trades_per_fold=min_trades_per_fold,
        max_forced_exit_rate=max_forced_exit_rate,
        max_drawdown=max_drawdown,
        min_adjusted_pnl_per_fold=min_cost_adjusted_pnl_per_fold,
        sort_by="min_pnl",
    )
    merged = prefixed_summary(base_summary, "base").merge(
        prefixed_summary(cost_summary, "cost"),
        on=SWEEP_KEY_COLUMNS,
        how="inner",
    )
    if merged.empty:
        return merged

    merged["cost_pnl_drop_min"] = (
        merged["total_adjusted_pnl_min_base"] - merged["total_adjusted_pnl_min_cost"]
    )
    base_abs = merged["total_adjusted_pnl_min_base"].abs().replace(0, np.nan)
    merged["cost_pnl_retention_min"] = merged["total_adjusted_pnl_min_cost"] / base_abs
    merged["long_adjusted_pnl_min_all"] = row_min_or_default(
        merged,
        ["long_adjusted_pnl_min_base", "long_adjusted_pnl_min_cost"],
        float("inf"),
    )
    merged["short_adjusted_pnl_min_all"] = row_min_or_default(
        merged,
        ["short_adjusted_pnl_min_base", "short_adjusted_pnl_min_cost"],
        float("inf"),
    )
    merged["side_adjusted_pnl_min_all"] = merged[
        ["long_adjusted_pnl_min_all", "short_adjusted_pnl_min_all"]
    ].min(axis=1)
    merged["direction_session_adjusted_pnl_min_all"] = row_min_or_default(
        merged,
        [
            "direction_session_adjusted_pnl_min_min_base",
            "direction_session_adjusted_pnl_min_min_cost",
        ],
        float("inf"),
    )
    merged["combined_regime_adjusted_pnl_min_all"] = row_min_or_default(
        merged,
        [
            "combined_regime_adjusted_pnl_min_min_base",
            "combined_regime_adjusted_pnl_min_min_cost",
        ],
        float("inf"),
    )
    merged["direction_combined_regime_adjusted_pnl_min_all"] = row_min_or_default(
        merged,
        [
            "direction_combined_regime_adjusted_pnl_min_min_base",
            "direction_combined_regime_adjusted_pnl_min_min_cost",
        ],
        float("inf"),
    )
    merged["side_loss_depth_all"] = loss_depth(merged["side_adjusted_pnl_min_all"])
    merged["direction_session_loss_depth_all"] = loss_depth(
        merged["direction_session_adjusted_pnl_min_all"]
    )
    merged["combined_regime_loss_depth_all"] = loss_depth(
        merged["combined_regime_adjusted_pnl_min_all"]
    )
    merged["direction_combined_regime_loss_depth_all"] = loss_depth(
        merged["direction_combined_regime_adjusted_pnl_min_all"]
    )
    merged["group_loss_penalty"] = (
        merged["side_loss_depth_all"]
        + merged["direction_session_loss_depth_all"]
        + merged["combined_regime_loss_depth_all"]
        + merged["direction_combined_regime_loss_depth_all"]
    )
    merged["max_drawdown_max_all"] = row_max_or_default(
        merged,
        ["max_drawdown_max_base", "max_drawdown_max_cost"],
        0.0,
    )
    merged["pnl_stability_risk_all"] = row_max_or_default(
        merged,
        ["total_adjusted_pnl_std_base", "total_adjusted_pnl_std_cost"],
        0.0,
    ).fillna(0.0)
    merged["short_trade_share_max_all"] = row_max_or_default(
        merged,
        ["short_trade_share_max_base", "short_trade_share_max_cost"],
        0.0,
    )
    merged["max_side_trade_share_max_all"] = row_max_or_default(
        merged,
        ["max_side_trade_share_max_base", "max_side_trade_share_max_cost"],
        0.0,
    )
    merged["predicted_profit_barrier_miss_rate_max_all"] = row_max_or_default(
        merged,
        [
            "predicted_profit_barrier_miss_rate_max_base",
            "predicted_profit_barrier_miss_rate_max_cost",
        ],
        0.0,
    )
    merged["direction_error_rate_max_all"] = row_max_or_default(
        merged,
        ["direction_error_rate_max_base", "direction_error_rate_max_cost"],
        0.0,
    )
    merged["predicted_side_error_rate_max_all"] = row_max_or_default(
        merged,
        ["predicted_side_error_rate_max_base", "predicted_side_error_rate_max_cost"],
        0.0,
    )
    merged["no_edge_rate_max_all"] = row_max_or_default(
        merged,
        ["no_edge_rate_max_base", "no_edge_rate_max_cost"],
        0.0,
    )
    merged["exit_regret_mean_max_all"] = row_max_or_default(
        merged,
        ["exit_regret_mean_max_base", "exit_regret_mean_max_cost"],
        0.0,
    )
    merged["ev_overestimate_vs_realized_mean_max_all"] = row_max_or_default(
        merged,
        [
            "ev_overestimate_vs_realized_mean_max_base",
            "ev_overestimate_vs_realized_mean_max_cost",
        ],
        0.0,
    )
    merged["actual_profit_barrier_miss_rate_max_all"] = row_max_or_default(
        merged,
        [
            "actual_profit_barrier_miss_rate_max_base",
            "actual_profit_barrier_miss_rate_max_cost",
        ],
        0.0,
    )
    merged["actual_profit_barrier_miss_rate_smoothed_max_all"] = row_max_or_default(
        merged,
        [
            "actual_profit_barrier_miss_rate_smoothed_max_base",
            "actual_profit_barrier_miss_rate_smoothed_max_cost",
        ],
        0.0,
    )
    merged["profit_barrier_calibration_overestimate_max_all"] = row_max_or_default(
        merged,
        [
            "profit_barrier_calibration_overestimate_max_max_base",
            "profit_barrier_calibration_overestimate_max_max_cost",
        ],
        0.0,
    )
    merged["profit_barrier_calibration_overestimate_smoothed_max_all"] = row_max_or_default(
        merged,
        [
            "profit_barrier_calibration_overestimate_smoothed_max_max_base",
            "profit_barrier_calibration_overestimate_smoothed_max_max_cost",
        ],
        0.0,
    )
    merged["diagnostic_direction_error_rate_excess"] = (
        merged["direction_error_rate_max_all"] - diagnostic_direction_error_rate_threshold
    ).clip(lower=0.0)
    merged["diagnostic_actual_profit_barrier_miss_rate_excess"] = (
        merged["actual_profit_barrier_miss_rate_smoothed_max_all"]
        - diagnostic_actual_profit_barrier_miss_rate_threshold
    ).clip(lower=0.0)
    merged["diagnostic_ev_overestimate_vs_realized_mean_excess"] = (
        merged["ev_overestimate_vs_realized_mean_max_all"]
        - diagnostic_ev_overestimate_vs_realized_mean_threshold
    ).clip(lower=0.0)
    merged["diagnostic_penalty"] = (
        diagnostic_direction_error_rate_scale * merged["diagnostic_direction_error_rate_excess"]
        + diagnostic_actual_profit_barrier_miss_rate_scale
        * merged["diagnostic_actual_profit_barrier_miss_rate_excess"]
        + diagnostic_ev_overestimate_vs_realized_mean_scale
        * merged["diagnostic_ev_overestimate_vs_realized_mean_excess"]
    )
    total_soft_penalty = (
        group_loss_penalty_weight * merged["group_loss_penalty"]
        + diagnostic_penalty_weight * merged["diagnostic_penalty"]
    )
    merged["robust_total_adjusted_pnl_min_cost"] = (
        merged["total_adjusted_pnl_min_cost"] - total_soft_penalty
    )
    merged["robust_total_adjusted_pnl_min_base"] = (
        merged["total_adjusted_pnl_min_base"] - total_soft_penalty
    )
    merged["side_loss_ok"] = merged["side_adjusted_pnl_min_all"] >= -max_side_loss_per_fold
    merged["direction_session_loss_ok"] = (
        merged["direction_session_adjusted_pnl_min_all"] >= -max_direction_session_loss_per_fold
    )
    merged["combined_regime_loss_ok"] = (
        merged["combined_regime_adjusted_pnl_min_all"] >= -max_combined_regime_loss_per_fold
    )
    merged["direction_combined_regime_loss_ok"] = (
        merged["direction_combined_regime_adjusted_pnl_min_all"]
        >= -max_direction_combined_regime_loss_per_fold
    )
    merged["short_trade_share_ok"] = merged["short_trade_share_max_all"] <= max_short_trade_share
    merged["side_trade_share_ok"] = merged["max_side_trade_share_max_all"] <= max_side_trade_share
    merged["predicted_profit_barrier_miss_ok"] = (
        merged["predicted_profit_barrier_miss_rate_max_all"] <= max_predicted_profit_barrier_miss_rate
    )
    merged["actual_profit_barrier_miss_ok"] = (
        merged["actual_profit_barrier_miss_rate_max_all"] <= max_actual_profit_barrier_miss_rate
    )
    merged["smoothed_actual_profit_barrier_miss_ok"] = (
        merged["actual_profit_barrier_miss_rate_smoothed_max_all"]
        <= max_smoothed_actual_profit_barrier_miss_rate
    )
    merged["profit_barrier_calibration_ok"] = (
        merged["profit_barrier_calibration_overestimate_max_all"]
        <= max_profit_barrier_calibration_overestimate
    )
    merged["smoothed_profit_barrier_calibration_ok"] = (
        merged["profit_barrier_calibration_overestimate_smoothed_max_all"]
        <= max_smoothed_profit_barrier_calibration_overestimate
    )
    merged["direction_error_rate_ok"] = (
        merged["direction_error_rate_max_all"] <= max_direction_error_rate
    )
    merged["predicted_side_error_rate_ok"] = (
        merged["predicted_side_error_rate_max_all"] <= max_predicted_side_error_rate
    )
    merged["no_edge_rate_ok"] = merged["no_edge_rate_max_all"] <= max_no_edge_rate
    merged["exit_regret_ok"] = merged["exit_regret_mean_max_all"] <= max_exit_regret_mean
    merged["ev_overestimate_vs_realized_ok"] = (
        merged["ev_overestimate_vs_realized_mean_max_all"]
        <= max_ev_overestimate_vs_realized_mean
    )
    merged["cost_drop_ok"] = merged["cost_pnl_drop_min"] <= max_cost_pnl_drop
    merged["pre_plateau_eligible"] = (
        merged["eligible_base"].astype(bool)
        & merged["eligible_cost"].astype(bool)
        & merged["side_loss_ok"]
        & merged["direction_session_loss_ok"]
        & merged["combined_regime_loss_ok"]
        & merged["direction_combined_regime_loss_ok"]
        & merged["short_trade_share_ok"]
        & merged["side_trade_share_ok"]
        & merged["predicted_profit_barrier_miss_ok"]
        & merged["actual_profit_barrier_miss_ok"]
        & merged["smoothed_actual_profit_barrier_miss_ok"]
        & merged["profit_barrier_calibration_ok"]
        & merged["smoothed_profit_barrier_calibration_ok"]
        & merged["direction_error_rate_ok"]
        & merged["predicted_side_error_rate_ok"]
        & merged["no_edge_rate_ok"]
        & merged["exit_regret_ok"]
        & merged["ev_overestimate_vs_realized_ok"]
        & merged["cost_drop_ok"]
    )
    merged["plateau_support_count"] = plateau_support_counts(
        merged,
        plateau_column=plateau_column,
        plateau_radius=plateau_radius,
        eligible_column="pre_plateau_eligible",
    )
    merged["plateau_ok"] = merged["plateau_support_count"] >= min_plateau_neighbors
    merged["eligible"] = merged["pre_plateau_eligible"] & merged["plateau_ok"]
    merged["near_top_cost_pnl_gap"] = row_gap_from_best(
        merged,
        "total_adjusted_pnl_min_cost",
        "eligible",
    )
    merged["near_top_cost_pnl_ok"] = (
        merged["eligible"] & (merged["near_top_cost_pnl_gap"] <= near_top_cost_pnl_tolerance)
    )
    merged["near_top_risk_score"] = (
        near_top_group_loss_weight * merged["group_loss_penalty"]
        + near_top_drawdown_weight * merged["max_drawdown_max_all"]
        + near_top_ev_overestimate_weight * merged["ev_overestimate_vs_realized_mean_max_all"]
        + near_top_exit_regret_weight * merged["exit_regret_mean_max_all"]
        + near_top_actual_miss_weight * merged["actual_profit_barrier_miss_rate_smoothed_max_all"]
        + near_top_side_share_weight * merged["max_side_trade_share_max_all"]
        + near_top_pnl_stability_weight * merged["pnl_stability_risk_all"]
    )
    merged["stress_risk_score"] = (
        merged["near_top_risk_score"]
        - stress_cost_pnl_sum_reward_weight * merged["total_adjusted_pnl_sum_cost"]
        - stress_base_pnl_sum_reward_weight * merged["total_adjusted_pnl_sum_base"]
    )

    if candidate_rank_mode == "near_top_risk":
        sort_columns = [
            "eligible",
            "near_top_cost_pnl_ok",
            "near_top_risk_score",
            "max_drawdown_max_all",
            "group_loss_penalty",
            "ev_overestimate_vs_realized_mean_max_all",
            "exit_regret_mean_max_all",
            "total_adjusted_pnl_min_cost",
            "total_adjusted_pnl_min_base",
            "near_top_cost_pnl_gap",
            "plateau_support_count",
            "side_adjusted_pnl_min_all",
            "direction_session_adjusted_pnl_min_all",
            "combined_regime_adjusted_pnl_min_all",
            "direction_combined_regime_adjusted_pnl_min_all",
            "direction_error_rate_max_all",
            "predicted_side_error_rate_max_all",
            "no_edge_rate_max_all",
            "short_trade_share_max_all",
            "max_side_trade_share_max_all",
            "actual_profit_barrier_miss_rate_smoothed_max_all",
            "actual_profit_barrier_miss_rate_max_all",
            "profit_barrier_calibration_overestimate_smoothed_max_all",
            "predicted_profit_barrier_miss_rate_max_all",
            "profit_barrier_calibration_overestimate_max_all",
            "cost_pnl_drop_min",
        ]
        ascending = [
            False,
            False,
            True,
            True,
            True,
            True,
            True,
            False,
            False,
            True,
            False,
            False,
            False,
            False,
            False,
            True,
            True,
            True,
            True,
            True,
            True,
            True,
            True,
            True,
            True,
            True,
        ]
    elif candidate_rank_mode == "stress_score":
        sort_columns = [
            "eligible",
            "near_top_cost_pnl_ok",
            "stress_risk_score",
            "max_drawdown_max_all",
            "group_loss_penalty",
            "ev_overestimate_vs_realized_mean_max_all",
            "exit_regret_mean_max_all",
            "total_adjusted_pnl_sum_cost",
            "total_adjusted_pnl_sum_base",
            "total_adjusted_pnl_min_cost",
            "total_adjusted_pnl_min_base",
            "near_top_cost_pnl_gap",
            "plateau_support_count",
            "side_adjusted_pnl_min_all",
            "direction_session_adjusted_pnl_min_all",
            "combined_regime_adjusted_pnl_min_all",
            "direction_combined_regime_adjusted_pnl_min_all",
            "direction_error_rate_max_all",
            "predicted_side_error_rate_max_all",
            "no_edge_rate_max_all",
            "short_trade_share_max_all",
            "max_side_trade_share_max_all",
            "actual_profit_barrier_miss_rate_smoothed_max_all",
            "actual_profit_barrier_miss_rate_max_all",
            "profit_barrier_calibration_overestimate_smoothed_max_all",
            "predicted_profit_barrier_miss_rate_max_all",
            "profit_barrier_calibration_overestimate_max_all",
            "cost_pnl_drop_min",
        ]
        ascending = [
            False,
            False,
            True,
            True,
            True,
            True,
            True,
            False,
            False,
            False,
            False,
            True,
            False,
            False,
            False,
            False,
            False,
            True,
            True,
            True,
            True,
            True,
            True,
            True,
            True,
            True,
            True,
            True,
        ]
    else:
        sort_columns = [
            "eligible",
            "robust_total_adjusted_pnl_min_cost",
            "robust_total_adjusted_pnl_min_base",
            "total_adjusted_pnl_min_cost",
            "total_adjusted_pnl_min_base",
            "plateau_support_count",
            "side_adjusted_pnl_min_all",
            "direction_session_adjusted_pnl_min_all",
            "combined_regime_adjusted_pnl_min_all",
            "direction_combined_regime_adjusted_pnl_min_all",
            "ev_overestimate_vs_realized_mean_max_all",
            "exit_regret_mean_max_all",
            "direction_error_rate_max_all",
            "predicted_side_error_rate_max_all",
            "no_edge_rate_max_all",
            "short_trade_share_max_all",
            "max_side_trade_share_max_all",
            "actual_profit_barrier_miss_rate_smoothed_max_all",
            "actual_profit_barrier_miss_rate_max_all",
            "profit_barrier_calibration_overestimate_smoothed_max_all",
            "predicted_profit_barrier_miss_rate_max_all",
            "profit_barrier_calibration_overestimate_max_all",
            "cost_pnl_drop_min",
        ]
        ascending = [
            False,
            False,
            False,
            False,
            False,
            False,
            False,
            False,
            False,
            False,
            True,
            True,
            True,
            True,
            True,
            True,
            True,
            True,
            True,
            True,
            True,
            True,
            True,
        ]

    return merged.sort_values(sort_columns, ascending=ascending).reset_index(drop=True)


def read_sweep_frames(paths: list[Path]) -> list[pd.DataFrame]:
    frames: list[pd.DataFrame] = []
    for path in paths:
        frame = pd.read_csv(path)
        frames.append(normalize_sweep_metrics(frame, str(path)))
    return frames


def sweep_key_values_from_model_policy_config(config: dict[str, object]) -> dict[str, object]:
    defaults = model_policy_sweep_key_defaults()
    values = {column: config.get(column, default) for column, default in defaults.items()}
    return normalize_sweep_key_columns(pd.DataFrame([values])).iloc[0].to_dict()


def expand_holdout_run_paths(paths: list[Path]) -> list[Path]:
    expanded: list[Path] = []
    for path in paths:
        if path.is_dir() and not (path / "metrics.json").exists() and not (path / "metrics.csv").exists():
            children = [
                child
                for child in sorted(path.iterdir())
                if child.is_dir()
                and (child / "config.json").exists()
                and ((child / "metrics.json").exists() or (child / "metrics.csv").exists())
            ]
            if children:
                expanded.extend(children)
                continue
        expanded.append(path)
    return expanded


def read_holdout_run_frame(path: Path) -> pd.DataFrame:
    run_dir = path if path.is_dir() else path.parent
    if path.is_dir():
        metrics_path = path / "metrics.csv" if (path / "metrics.csv").exists() else path / "metrics.json"
    else:
        metrics_path = path
    config_path = run_dir / "config.json"
    if not metrics_path.exists():
        raise FileNotFoundError(f"holdout metrics not found: {metrics_path}")
    if not config_path.exists():
        raise FileNotFoundError(f"holdout config not found: {config_path}")

    config = json.loads(config_path.read_text(encoding="utf-8"))
    model_policy_config = config.get("model_policy_config")

    if metrics_path.suffix == ".csv":
        frame = pd.read_csv(metrics_path)
    elif metrics_path.suffix == ".json":
        frame = pd.DataFrame([json.loads(metrics_path.read_text(encoding="utf-8"))])
    else:
        raise ValueError(f"unsupported holdout metrics file: {metrics_path}")

    if isinstance(model_policy_config, dict):
        key_values = sweep_key_values_from_model_policy_config(model_policy_config)
        for column, value in key_values.items():
            frame[column] = value
    elif metrics_path.suffix != ".csv":
        raise ValueError(f"holdout run has no model_policy_config: {run_dir}")
    frame = normalize_sweep_metrics(frame, str(run_dir)).copy()
    frame["holdout_run"] = str(run_dir)
    return frame


def read_holdout_run_frames(paths: list[Path]) -> list[pd.DataFrame]:
    return [read_holdout_run_frame(path) for path in expand_holdout_run_paths(paths)]


def expand_model_trade_exposure_run_paths(paths: list[Path]) -> list[Path]:
    expanded: list[Path] = []
    for path in paths:
        if path.is_dir() and not (path / "trades.csv").exists():
            children = [
                child
                for child in sorted(path.iterdir())
                if child.is_dir()
                and (child / "config.json").exists()
                and (child / "trades.csv").exists()
            ]
            if children:
                expanded.extend(children)
                continue
        expanded.append(path)
    return expanded


def month_label_from_run_config(config: dict[str, object], run_dir: Path) -> str:
    backtest_config = config.get("backtest_config", {})
    if isinstance(backtest_config, dict):
        evaluation_start = backtest_config.get("evaluation_start")
        if evaluation_start:
            return pd.Timestamp(evaluation_start).strftime("%Y-%m")
    suffix = run_dir.name[-7:]
    if len(suffix) == 7 and suffix[4] == "-":
        return suffix
    return run_dir.name


def read_model_trade_exposure_frame(
    path: Path,
    long_column: str = "",
    short_column: str = "",
) -> pd.DataFrame:
    run_dir = path if path.is_dir() else path.parent
    trades_path = path if path.name == "trades.csv" else run_dir / "trades.csv"
    config_path = run_dir / "config.json"
    if not trades_path.exists():
        raise FileNotFoundError(f"trades.csv not found: {trades_path}")
    if not config_path.exists():
        raise FileNotFoundError(f"model-policy config not found: {config_path}")

    config = json.loads(config_path.read_text(encoding="utf-8"))
    model_policy_config = config.get("model_policy_config")
    if not isinstance(model_policy_config, dict):
        raise ValueError(f"run has no model_policy_config: {run_dir}")
    predictions_value = model_policy_config.get("predictions")
    if not predictions_value:
        raise ValueError(f"run has no model_policy_config.predictions: {run_dir}")
    predictions_path = Path(str(predictions_value))
    selected_long_column = long_column or str(
        model_policy_config.get("long_column", "pred_long_best_adjusted_pnl")
    )
    selected_short_column = short_column or str(
        model_policy_config.get("short_column", "pred_short_best_adjusted_pnl")
    )

    trades = read_trades_csv(trades_path)
    predictions = read_analysis_predictions(
        predictions_path,
        selected_long_column,
        selected_short_column,
    )
    enriched = enrich_trades_with_predictions(trades, predictions)
    enriched.insert(0, "month", month_label_from_run_config(config, run_dir))
    enriched.insert(1, "run_dir", str(run_dir))
    enriched.insert(2, "predictions_path", str(predictions_path))
    return enriched


def read_model_trade_exposure_frames(
    paths: list[Path],
    long_column: str = "",
    short_column: str = "",
) -> list[pd.DataFrame]:
    return [
        read_model_trade_exposure_frame(path, long_column, short_column)
        for path in expand_model_trade_exposure_run_paths(paths)
    ]


def model_policy_run_month_label(path: Path) -> str:
    run_dir, config, _ = read_model_policy_run_metadata(path)
    return month_label_from_run_config(config, run_dir)


def map_model_policy_runs_by_month(paths: list[Path], label: str) -> dict[str, Path]:
    runs: dict[str, Path] = {}
    for path in paths:
        month = model_policy_run_month_label(path)
        if month in runs:
            raise ValueError(
                f"{label} runs contain duplicate month {month}: {runs[month]} and {path}"
            )
        runs[month] = path
    return runs


def pair_model_trade_delta_run_paths(
    base_paths: list[Path],
    candidate_paths: list[Path],
) -> list[tuple[Path, Path]]:
    expanded_base_paths = expand_model_trade_exposure_run_paths(base_paths)
    expanded_candidate_paths = expand_model_trade_exposure_run_paths(candidate_paths)
    if len(expanded_base_paths) == 1 and len(expanded_candidate_paths) == 1:
        return [(expanded_base_paths[0], expanded_candidate_paths[0])]

    base_by_month = map_model_policy_runs_by_month(expanded_base_paths, "base")
    candidate_by_month = map_model_policy_runs_by_month(expanded_candidate_paths, "candidate")
    base_months = set(base_by_month)
    candidate_months = set(candidate_by_month)
    if base_months != candidate_months:
        missing_candidate = sorted(base_months - candidate_months)
        missing_base = sorted(candidate_months - base_months)
        details: list[str] = []
        if missing_candidate:
            details.append(f"missing candidate months: {','.join(missing_candidate)}")
        if missing_base:
            details.append(f"missing base months: {','.join(missing_base)}")
        raise ValueError(f"base and candidate run months differ; {'; '.join(details)}")
    return [(base_by_month[month], candidate_by_month[month]) for month in sorted(base_months)]


def resolve_single_model_policy_run_path(path: Path) -> Path:
    expanded = expand_model_trade_exposure_run_paths([path])
    if len(expanded) != 1:
        raise ValueError(f"expected exactly one model-policy run under {path}, found {len(expanded)}")
    return expanded[0]


def read_model_policy_run_metadata(path: Path) -> tuple[Path, dict[str, object], dict[str, object]]:
    run_dir = path if path.is_dir() else path.parent
    config_path = run_dir / "config.json"
    if not config_path.exists():
        raise FileNotFoundError(f"model-policy config not found: {config_path}")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    model_policy_config = config.get("model_policy_config")
    if not isinstance(model_policy_config, dict):
        raise ValueError(f"run has no model_policy_config: {run_dir}")
    return run_dir, config, model_policy_config


def add_side_prediction_values(
    trades: pd.DataFrame,
    predictions_path: Path,
    long_column: str,
    short_column: str,
    prefix: str,
) -> pd.DataFrame:
    output = trades.copy()
    long_output = f"{prefix}_long"
    short_output = f"{prefix}_short"
    taken_output = f"{prefix}_taken"
    opposite_output = f"{prefix}_opposite"
    for column in [long_output, short_output, taken_output, opposite_output]:
        output[column] = np.nan

    source_columns = [column for column in [long_column, short_column] if column]
    if not source_columns:
        return output

    available = optional_parquet_columns(predictions_path, ["decision_timestamp", *source_columns])
    if "decision_timestamp" not in available:
        return output
    value_columns = [column for column in source_columns if column in available]
    if not value_columns:
        return output

    values = pd.read_parquet(predictions_path, columns=["decision_timestamp", *value_columns])
    values["decision_timestamp"] = pd.to_datetime(values["decision_timestamp"], utc=True)
    rename_columns = {"decision_timestamp": "entry_decision_timestamp"}
    if long_column in value_columns:
        rename_columns[long_column] = long_output
    if short_column in value_columns:
        rename_columns[short_column] = short_output
    values = values.rename(columns=rename_columns)
    output = output.drop(columns=[long_output, short_output, taken_output, opposite_output])
    output = output.merge(values, on="entry_decision_timestamp", how="left", validate="many_to_one")
    for column in [long_output, short_output]:
        if column not in output.columns:
            output[column] = np.nan

    direction = output["direction"].astype(str).str.lower()
    output[taken_output] = side_values(output, direction, long_output, short_output)
    output[opposite_output] = opposite_side_values(output, direction, long_output, short_output)
    return output


TRADE_DELTA_CONTEXT_COLUMNS = [
    "month",
    "dataset_month",
    *REGIME_COLUMNS,
    "entry_hour",
    "holding_bucket",
    "actual_taken_best_bucket",
    "pred_taken_ev_bucket",
    "actual_taken_wait_regret_bucket",
    "pred_taken_wait_regret_bucket",
    "actual_taken_entry_rank_bucket",
    "pred_taken_entry_rank_bucket",
    "predicted_best_side",
    "actual_best_side",
    "actual_taken_best_adjusted_pnl",
    "actual_opposite_best_adjusted_pnl",
    "actual_best_adjusted_pnl",
    "pred_taken_ev",
    "pred_opposite_ev",
    "pred_best_ev",
    "pred_taken_best_holding_minutes",
    "pred_taken_max_adverse_pnl",
    "pred_taken_wait_regret",
    "pred_taken_entry_local_rank",
    "pred_taken_profit_barrier_hit",
    "pred_taken_side_confidence",
    "pred_opposite_side_confidence",
    "pred_side_confidence_gap",
    "direction_error",
    "no_edge_entry",
    "predicted_side_error",
    "predicted_side_matches_trade",
    "actual_side_matches_trade",
    "exit_regret",
    "best_side_regret",
    "ev_overestimate_vs_oracle",
    "ev_overestimate_vs_realized",
    "holding_error_minutes",
    "oracle_holding_gap_minutes",
    "is_win",
    "is_long",
    "is_short",
    "is_forced_exit",
    "is_loss",
    "gate_trade_quality_long",
    "gate_trade_quality_short",
    "gate_trade_quality_taken",
    "gate_trade_quality_opposite",
]


def coalesce_merged_column(merged: pd.DataFrame, column: str) -> pd.Series:
    base_column = f"{column}_base"
    candidate_column = f"{column}_candidate"
    if base_column in merged.columns and candidate_column in merged.columns:
        base_values = merged[base_column].astype("object")
        candidate_values = merged[candidate_column].astype("object")
        return base_values.where(base_values.notna(), candidate_values)
    if base_column in merged.columns:
        return merged[base_column]
    if candidate_column in merged.columns:
        return merged[candidate_column]
    return pd.Series(np.nan, index=merged.index)


def build_trade_delta_frame(base: pd.DataFrame, candidate: pd.DataFrame) -> pd.DataFrame:
    key_columns = ["entry_decision_timestamp", "direction"]
    for name, frame in [("base", base), ("candidate", candidate)]:
        missing = sorted(set(key_columns) - set(frame.columns))
        if missing:
            raise ValueError(f"{name} trade frame missing columns: {', '.join(missing)}")
        duplicated = frame[key_columns].duplicated()
        if duplicated.any():
            raise ValueError(f"{name} trade frame has duplicated trade keys: {int(duplicated.sum())}")

    passthrough_columns = [
        column
        for column in [
            *TRADE_COLUMNS,
            *TRADE_DELTA_CONTEXT_COLUMNS,
        ]
        if column not in key_columns
    ]
    base_columns = [*key_columns, *[column for column in passthrough_columns if column in base.columns]]
    candidate_columns = [
        *key_columns,
        *[column for column in passthrough_columns if column in candidate.columns],
    ]
    merged = base.loc[:, list(dict.fromkeys(base_columns))].merge(
        candidate.loc[:, list(dict.fromkeys(candidate_columns))],
        on=key_columns,
        how="outer",
        suffixes=("_base", "_candidate"),
        indicator=True,
        validate="one_to_one",
    )

    output = pd.DataFrame(
        {
            "entry_decision_timestamp": merged["entry_decision_timestamp"],
            "direction": merged["direction"],
            "delta_status": merged["_merge"].map(
                {
                    "left_only": "only_base",
                    "right_only": "only_candidate",
                    "both": "common",
                }
            ),
        }
    )
    output["base_present"] = merged["_merge"].isin(["left_only", "both"])
    output["candidate_present"] = merged["_merge"].isin(["right_only", "both"])

    for column in TRADE_COLUMNS:
        if column in key_columns:
            continue
        base_column = f"{column}_base"
        candidate_column = f"{column}_candidate"
        output[f"base_{column}"] = (
            merged[base_column] if base_column in merged.columns else pd.Series(np.nan, index=merged.index)
        )
        output[f"candidate_{column}"] = (
            merged[candidate_column]
            if candidate_column in merged.columns
            else pd.Series(np.nan, index=merged.index)
        )

    for column in TRADE_DELTA_CONTEXT_COLUMNS:
        output[column] = coalesce_merged_column(merged, column)

    output["base_adjusted_pnl"] = pd.to_numeric(output["base_adjusted_pnl"], errors="coerce")
    output["candidate_adjusted_pnl"] = pd.to_numeric(
        output["candidate_adjusted_pnl"], errors="coerce"
    )
    output["base_raw_pnl"] = pd.to_numeric(output["base_raw_pnl"], errors="coerce")
    output["candidate_raw_pnl"] = pd.to_numeric(output["candidate_raw_pnl"], errors="coerce")
    output["pnl_delta"] = output["candidate_adjusted_pnl"].fillna(0.0) - output[
        "base_adjusted_pnl"
    ].fillna(0.0)
    output["raw_pnl_delta"] = output["candidate_raw_pnl"].fillna(0.0) - output[
        "base_raw_pnl"
    ].fillna(0.0)
    output["entry_timestamp"] = coalesce_merged_column(merged, "entry_timestamp")
    output["exit_timestamp"] = coalesce_merged_column(merged, "exit_timestamp")
    entry_timestamp = pd.to_datetime(output["entry_timestamp"], utc=True, errors="coerce")
    output["entry_date"] = entry_timestamp.dt.strftime("%Y-%m-%d")
    output["entry_hour"] = entry_timestamp.dt.hour
    if "gate_trade_quality_taken" in output.columns:
        output["gate_trade_quality_taken_bucket"] = bucket_series(
            pd.to_numeric(output["gate_trade_quality_taken"], errors="coerce"),
            [-float("inf"), -10, 0, 5, 10, float("inf")],
            ["<=-10", "-10-0", "0-5", "5-10", ">10"],
        )
    output = output.sort_values(["entry_decision_timestamp", "direction"]).reset_index(drop=True)
    output.insert(0, "trade_delta_row_id", np.arange(len(output), dtype="int64"))
    return output


def trade_delta_group_summary(frame: pd.DataFrame, group_columns: list[str]) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=group_columns)
    missing = sorted(set(group_columns) - set(frame.columns))
    if missing:
        raise ValueError(f"trade delta frame missing columns: {', '.join(missing)}")

    working = frame.copy()
    base_pnl = working["base_adjusted_pnl"].astype(float)
    candidate_pnl = working["candidate_adjusted_pnl"].astype(float)
    working["_base_present"] = numeric_indicator(working["base_present"])
    working["_candidate_present"] = numeric_indicator(working["candidate_present"])
    working["_only_base"] = numeric_indicator(working["delta_status"].eq("only_base"))
    working["_only_candidate"] = numeric_indicator(working["delta_status"].eq("only_candidate"))
    working["_common"] = numeric_indicator(working["delta_status"].eq("common"))
    working["_base_win"] = pd.Series(np.where(working["base_present"], base_pnl > 0, np.nan), index=working.index)
    working["_candidate_win"] = pd.Series(
        np.where(working["candidate_present"], candidate_pnl > 0, np.nan), index=working.index
    )
    working["_removed_positive_pnl"] = np.where(
        working["delta_status"].eq("only_base") & (base_pnl > 0),
        base_pnl,
        0.0,
    )
    working["_removed_negative_pnl"] = np.where(
        working["delta_status"].eq("only_base") & (base_pnl < 0),
        base_pnl,
        0.0,
    )
    working["_added_positive_pnl"] = np.where(
        working["delta_status"].eq("only_candidate") & (candidate_pnl > 0),
        candidate_pnl,
        0.0,
    )
    working["_added_negative_pnl"] = np.where(
        working["delta_status"].eq("only_candidate") & (candidate_pnl < 0),
        candidate_pnl,
        0.0,
    )

    aggregations: dict[str, tuple[str, str]] = {
        "row_count": ("pnl_delta", "size"),
        "base_trade_count": ("_base_present", "sum"),
        "candidate_trade_count": ("_candidate_present", "sum"),
        "only_base_count": ("_only_base", "sum"),
        "only_candidate_count": ("_only_candidate", "sum"),
        "common_count": ("_common", "sum"),
        "base_adjusted_pnl": ("base_adjusted_pnl", "sum"),
        "candidate_adjusted_pnl": ("candidate_adjusted_pnl", "sum"),
        "pnl_delta": ("pnl_delta", "sum"),
        "base_avg_adjusted_pnl": ("base_adjusted_pnl", "mean"),
        "candidate_avg_adjusted_pnl": ("candidate_adjusted_pnl", "mean"),
        "base_win_rate": ("_base_win", "mean"),
        "candidate_win_rate": ("_candidate_win", "mean"),
        "removed_positive_pnl": ("_removed_positive_pnl", "sum"),
        "removed_negative_pnl": ("_removed_negative_pnl", "sum"),
        "added_positive_pnl": ("_added_positive_pnl", "sum"),
        "added_negative_pnl": ("_added_negative_pnl", "sum"),
    }
    for column in [
        "gate_trade_quality_taken",
        "pred_taken_ev",
        "actual_taken_best_adjusted_pnl",
        "exit_regret",
        "ev_overestimate_vs_realized",
    ]:
        if column in working.columns:
            working[column] = pd.to_numeric(working[column], errors="coerce")
            aggregations[f"{column}_mean"] = (column, "mean")

    summary = working.groupby(group_columns, dropna=False, observed=True).agg(**aggregations).reset_index()
    sort_columns = [column for column in ["month"] if column in group_columns]
    sort_columns.extend(["pnl_delta", "row_count"])
    ascending = [True] * (len(sort_columns) - 2) + [True, False]
    return summary.sort_values(sort_columns, ascending=ascending).reset_index(drop=True)


def trade_delta_case_mask(frame: pd.DataFrame, row: pd.Series) -> pd.Series:
    mask = pd.Series(True, index=frame.index)
    for column in ["month", "base_run_dir", "candidate_run_dir"]:
        if column in frame.columns and column in row.index:
            mask &= frame[column].eq(row[column])
    return mask


def add_trade_delta_blocking_diagnostics(delta: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    output = delta.copy().reset_index(drop=True)
    if "trade_delta_row_id" not in output.columns:
        output.insert(0, "trade_delta_row_id", np.arange(len(output), dtype="int64"))
    for column in [
        "entry_decision_timestamp",
        "candidate_exit_decision_timestamp",
        "base_exit_decision_timestamp",
    ]:
        if column in output.columns:
            output[column] = pd.to_datetime(output[column], utc=True, errors="coerce")

    output["candidate_blocked_base_count"] = 0
    output["candidate_blocked_base_adjusted_pnl"] = 0.0
    output["candidate_blocked_base_positive_pnl"] = 0.0
    output["candidate_blocked_base_negative_pnl"] = 0.0
    output["candidate_stateful_net_adjusted_pnl"] = pd.to_numeric(
        output.get("candidate_adjusted_pnl", pd.Series(np.nan, index=output.index)),
        errors="coerce",
    )
    output["candidate_stateful_positive_cost_adjusted_pnl"] = output[
        "candidate_stateful_net_adjusted_pnl"
    ]
    output["blocked_by_candidate_row_id"] = np.nan
    output["blocked_by_candidate_direction"] = ""
    output["blocked_by_candidate_adjusted_pnl"] = np.nan

    if output.empty:
        return output, pd.DataFrame()

    candidate_present = output["candidate_present"].fillna(False).astype(bool)
    only_base = output["delta_status"].eq("only_base")
    pairs: list[dict[str, object]] = []
    for candidate_index, candidate_row in output.loc[candidate_present].iterrows():
        start = candidate_row.get("entry_decision_timestamp")
        end = candidate_row.get("candidate_exit_decision_timestamp")
        if pd.isna(start) or pd.isna(end):
            continue
        case_mask = trade_delta_case_mask(output, candidate_row)
        blocked_mask = (
            case_mask
            & only_base
            & (output["entry_decision_timestamp"] > start)
            & (output["entry_decision_timestamp"] <= end)
        )
        blocked = output.loc[blocked_mask].copy()
        if blocked.empty:
            continue

        blocked_pnl = pd.to_numeric(blocked["base_adjusted_pnl"], errors="coerce").fillna(0.0)
        blocked_sum = float(blocked_pnl.sum())
        blocked_positive = float(blocked_pnl[blocked_pnl > 0].sum())
        blocked_negative = float(blocked_pnl[blocked_pnl < 0].sum())
        candidate_pnl = float(
            pd.to_numeric(
                pd.Series([candidate_row.get("candidate_adjusted_pnl", np.nan)]),
                errors="coerce",
            ).fillna(0.0).iloc[0]
        )

        output.loc[candidate_index, "candidate_blocked_base_count"] = int(len(blocked))
        output.loc[candidate_index, "candidate_blocked_base_adjusted_pnl"] = blocked_sum
        output.loc[candidate_index, "candidate_blocked_base_positive_pnl"] = blocked_positive
        output.loc[candidate_index, "candidate_blocked_base_negative_pnl"] = blocked_negative
        output.loc[candidate_index, "candidate_stateful_net_adjusted_pnl"] = (
            candidate_pnl - blocked_sum
        )
        output.loc[candidate_index, "candidate_stateful_positive_cost_adjusted_pnl"] = (
            candidate_pnl - blocked_positive
        )

        for blocked_index, blocked_row in blocked.iterrows():
            if pd.isna(output.loc[blocked_index, "blocked_by_candidate_row_id"]):
                output.loc[blocked_index, "blocked_by_candidate_row_id"] = candidate_row[
                    "trade_delta_row_id"
                ]
                output.loc[blocked_index, "blocked_by_candidate_direction"] = candidate_row[
                    "direction"
                ]
                output.loc[blocked_index, "blocked_by_candidate_adjusted_pnl"] = candidate_pnl
            blocked_row_pnl = float(blocked_row.get("base_adjusted_pnl", 0.0) or 0.0)
            pairs.append(
                {
                    "month": candidate_row.get("month", ""),
                    "candidate_row_id": candidate_row["trade_delta_row_id"],
                    "candidate_delta_status": candidate_row["delta_status"],
                    "candidate_entry_decision_timestamp": start,
                    "candidate_exit_decision_timestamp": end,
                    "candidate_direction": candidate_row["direction"],
                    "candidate_combined_regime": candidate_row.get("combined_regime", ""),
                    "candidate_session_regime": candidate_row.get("session_regime", ""),
                    "candidate_adjusted_pnl": candidate_pnl,
                    "candidate_gate_trade_quality_taken": candidate_row.get(
                        "gate_trade_quality_taken",
                        np.nan,
                    ),
                    "blocked_base_row_id": blocked_row["trade_delta_row_id"],
                    "blocked_base_entry_decision_timestamp": blocked_row[
                        "entry_decision_timestamp"
                    ],
                    "blocked_base_direction": blocked_row["direction"],
                    "blocked_base_combined_regime": blocked_row.get("combined_regime", ""),
                    "blocked_base_session_regime": blocked_row.get("session_regime", ""),
                    "blocked_base_adjusted_pnl": blocked_row_pnl,
                    "blocked_base_positive_pnl": max(blocked_row_pnl, 0.0),
                    "blocked_base_negative_pnl": min(blocked_row_pnl, 0.0),
                }
            )

    pairs_frame = pd.DataFrame(pairs)
    return output, pairs_frame


def trade_delta_blocking_group_summary(frame: pd.DataFrame, group_columns: list[str]) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=group_columns)
    missing = sorted(set(group_columns) - set(frame.columns))
    if missing:
        raise ValueError(f"trade delta frame missing columns: {', '.join(missing)}")
    candidates = frame[frame["candidate_present"].fillna(False).astype(bool)].copy()
    if candidates.empty:
        return pd.DataFrame(columns=group_columns)
    for column in [
        "candidate_adjusted_pnl",
        "candidate_blocked_base_adjusted_pnl",
        "candidate_blocked_base_positive_pnl",
        "candidate_blocked_base_negative_pnl",
        "candidate_stateful_net_adjusted_pnl",
        "candidate_stateful_positive_cost_adjusted_pnl",
        "gate_trade_quality_taken",
    ]:
        if column in candidates.columns:
            candidates[column] = pd.to_numeric(candidates[column], errors="coerce")

    aggregations: dict[str, tuple[str, str]] = {
        "candidate_trade_count": ("candidate_present", "size"),
        "candidate_adjusted_pnl": ("candidate_adjusted_pnl", "sum"),
        "blocked_base_count": ("candidate_blocked_base_count", "sum"),
        "blocked_base_adjusted_pnl": ("candidate_blocked_base_adjusted_pnl", "sum"),
        "blocked_base_positive_pnl": ("candidate_blocked_base_positive_pnl", "sum"),
        "blocked_base_negative_pnl": ("candidate_blocked_base_negative_pnl", "sum"),
        "candidate_stateful_net_adjusted_pnl": (
            "candidate_stateful_net_adjusted_pnl",
            "sum",
        ),
        "candidate_stateful_positive_cost_adjusted_pnl": (
            "candidate_stateful_positive_cost_adjusted_pnl",
            "sum",
        ),
    }
    if "gate_trade_quality_taken" in candidates.columns:
        aggregations["gate_trade_quality_taken_mean"] = ("gate_trade_quality_taken", "mean")

    summary = candidates.groupby(group_columns, dropna=False, observed=True).agg(**aggregations).reset_index()
    sort_columns = [column for column in ["month"] if column in group_columns]
    sort_columns.extend(["candidate_stateful_net_adjusted_pnl", "candidate_trade_count"])
    ascending = [True] * (len(sort_columns) - 2) + [True, False]
    return summary.sort_values(sort_columns, ascending=ascending).reset_index(drop=True)


def add_decision_hour_features(frame: pd.DataFrame, timestamp_column: str) -> tuple[pd.Series, pd.Series]:
    if timestamp_column not in frame.columns:
        zeros = pd.Series(0.0, index=frame.index, dtype="float64")
        return zeros, zeros
    hours = pd.to_datetime(frame[timestamp_column], utc=True, errors="coerce").dt.hour.astype(float)
    radians = 2.0 * np.pi * hours / 24.0
    return (
        pd.Series(np.sin(radians), index=frame.index).fillna(0.0),
        pd.Series(np.cos(radians), index=frame.index).fillna(0.0),
    )


def stateful_example_target_column(target_mode: str) -> str:
    if target_mode == "stateful_net":
        return "candidate_stateful_net_adjusted_pnl"
    if target_mode == "stateful_positive_cost":
        return "candidate_stateful_positive_cost_adjusted_pnl"
    if target_mode == "candidate_pnl":
        return "candidate_adjusted_pnl"
    raise ValueError(f"unknown stateful example target mode: {target_mode}")


def stateful_candidate_examples_from_delta(
    delta: pd.DataFrame,
    target_mode: str = "stateful_net",
) -> pd.DataFrame:
    if delta.empty:
        return pd.DataFrame()
    target_column = stateful_example_target_column(target_mode)
    if target_column not in delta.columns:
        raise ValueError(f"trade delta frame missing target column: {target_column}")

    candidates = delta[delta["candidate_present"].fillna(False).astype(bool)].copy()
    if candidates.empty:
        return candidates
    direction = candidates["direction"].astype(str).str.lower()
    candidates["side"] = direction.map({"long": 1.0, "short": -1.0}).fillna(0.0)
    candidates["candidate_side"] = direction
    candidates["candidate_source_index"] = candidates["trade_delta_row_id"].astype(str)
    candidates["decision_timestamp"] = candidates["entry_decision_timestamp"]
    candidates["pred_side_gap"] = (
        pd.to_numeric(candidates["pred_taken_ev"], errors="coerce").fillna(0.0)
        - pd.to_numeric(candidates["pred_opposite_ev"], errors="coerce").fillna(0.0)
    )
    candidates["pred_abs_side_gap"] = candidates["pred_side_gap"].abs()
    candidates["decision_hour_sin"], candidates["decision_hour_cos"] = add_decision_hour_features(
        candidates,
        "entry_decision_timestamp",
    )
    candidates["candidate_actual_adjusted_pnl"] = pd.to_numeric(
        candidates["candidate_adjusted_pnl"],
        errors="coerce",
    )
    candidates["stateful_entry_value"] = pd.to_numeric(
        candidates["candidate_stateful_net_adjusted_pnl"],
        errors="coerce",
    )
    candidates["stateful_positive_cost_value"] = pd.to_numeric(
        candidates["candidate_stateful_positive_cost_adjusted_pnl"],
        errors="coerce",
    )
    blocked_base = pd.to_numeric(
        candidates["candidate_blocked_base_adjusted_pnl"],
        errors="coerce",
    ).fillna(0.0)
    blocked_positive = pd.to_numeric(
        candidates["candidate_blocked_base_positive_pnl"],
        errors="coerce",
    ).fillna(0.0)
    candidate_pnl = pd.to_numeric(candidates["candidate_adjusted_pnl"], errors="coerce").fillna(0.0)
    candidates["blocking_cost"] = blocked_base.clip(lower=0.0)
    candidates["positive_blocking_cost"] = blocked_positive.clip(lower=0.0)
    candidates["replacement_regret"] = blocked_base - candidate_pnl
    candidates["positive_replacement_regret"] = blocked_positive - candidate_pnl
    candidates["target"] = pd.to_numeric(candidates[target_column], errors="coerce")
    numeric_columns = candidates.select_dtypes(include=[np.number]).columns
    candidates.loc[:, numeric_columns] = candidates.loc[:, numeric_columns].replace(
        [np.inf, -np.inf],
        np.nan,
    )
    return candidates.dropna(subset=["target"]).reset_index(drop=True)


def expand_stateful_example_paths(paths: list[Path]) -> list[Path]:
    expanded: list[Path] = []
    for path in paths:
        if path.is_file():
            expanded.append(path)
            continue
        direct = path / "stateful_candidate_examples.csv"
        if direct.exists():
            expanded.append(direct)
            continue
        if path.is_dir():
            children = [
                child / "stateful_candidate_examples.csv"
                for child in sorted(path.iterdir())
                if child.is_dir() and (child / "stateful_candidate_examples.csv").exists()
            ]
            if children:
                expanded.extend(children)
                continue
        expanded.append(direct)
    return expanded


def read_stateful_example_frames(paths: list[Path], split: str) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for path in expand_stateful_example_paths(paths):
        if not path.exists():
            raise FileNotFoundError(f"stateful examples not found: {path}")
        frame = pd.read_csv(path)
        if frame.empty:
            continue
        frame = frame.copy()
        frame["split"] = split
        frame["example_source"] = str(path)
        frame["case_label"] = path.parent.name
        if "dataset_month" not in frame.columns and "month" in frame.columns:
            frame["dataset_month"] = frame["month"].astype(str)
        if "month" not in frame.columns and "dataset_month" in frame.columns:
            frame["month"] = frame["dataset_month"].astype(str)
        if "candidate_side" not in frame.columns and "direction" in frame.columns:
            frame["candidate_side"] = frame["direction"].astype(str).str.lower()
        frames.append(frame)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def stateful_examples_metric_summary(
    frame: pd.DataFrame,
    *,
    group_columns: list[str],
    target_column: str = "target",
    raw_prediction_column: str = "pred_taken_ev",
    downside_threshold: float = 0.0,
    large_downside_threshold: float = -15.0,
) -> pd.DataFrame:
    columns = ["split", *group_columns]
    if frame.empty:
        return pd.DataFrame(columns=columns)
    missing_group_columns = [column for column in group_columns if column not in frame.columns]
    if missing_group_columns:
        raise ValueError(f"stateful examples missing group columns: {missing_group_columns}")
    if target_column not in frame.columns:
        raise ValueError(f"stateful examples missing target column: {target_column}")

    working = frame.copy()
    working["_target"] = pd.to_numeric(working[target_column], errors="coerce")
    if raw_prediction_column in working.columns:
        working["_raw_pred"] = pd.to_numeric(working[raw_prediction_column], errors="coerce")
    else:
        working["_raw_pred"] = np.nan
    working["_raw_error"] = working["_raw_pred"] - working["_target"]
    working["_raw_overestimate"] = working["_raw_error"].clip(lower=0.0)
    working["_downside"] = working["_target"] <= downside_threshold
    working["_large_downside"] = working["_target"] <= large_downside_threshold
    numeric_columns = working.select_dtypes(include=[np.number]).columns
    working.loc[:, numeric_columns] = working.loc[:, numeric_columns].replace(
        [np.inf, -np.inf],
        np.nan,
    )
    working = working.dropna(subset=["_target"])
    if working.empty:
        return pd.DataFrame(columns=columns)
    for column in group_columns:
        working[column] = working[column].astype("string").fillna("__missing__")
    if "dataset_month" not in working.columns:
        working["dataset_month"] = ""

    grouped = (
        working.groupby(["split", *group_columns], dropna=False, observed=True)
        .agg(
            support=("_target", "size"),
            month_count=("dataset_month", "nunique"),
            target_sum=("_target", "sum"),
            target_mean=("_target", "mean"),
            target_min=("_target", "min"),
            target_q10=("_target", lambda series: float(series.quantile(0.10))),
            downside_rate=("_downside", "mean"),
            large_downside_rate=("_large_downside", "mean"),
            raw_predicted_mean=("_raw_pred", "mean"),
            raw_bias=("_raw_error", "mean"),
            raw_overestimate_mean=("_raw_overestimate", "mean"),
        )
        .reset_index()
    )
    return grouped.sort_values(["split", "target_mean", "support"], ascending=[True, True, False])


def stateful_examples_month_group_metrics(
    frame: pd.DataFrame,
    *,
    group_columns: list[str],
    target_column: str = "target",
    raw_prediction_column: str = "pred_taken_ev",
    downside_threshold: float = 0.0,
    large_downside_threshold: float = -15.0,
) -> pd.DataFrame:
    if "dataset_month" not in frame.columns and "month" not in frame.columns:
        return pd.DataFrame()
    working = frame.copy()
    if "dataset_month" not in working.columns:
        working["dataset_month"] = working["month"].astype(str)
    return stateful_examples_metric_summary(
        working,
        group_columns=["dataset_month", *group_columns],
        target_column=target_column,
        raw_prediction_column=raw_prediction_column,
        downside_threshold=downside_threshold,
        large_downside_threshold=large_downside_threshold,
    )


def stateful_examples_drift_metrics(
    split_metrics: pd.DataFrame,
    *,
    group_columns: list[str],
) -> pd.DataFrame:
    if split_metrics.empty:
        return pd.DataFrame()

    metric_columns = [
        column
        for column in split_metrics.columns
        if column not in ["split", *group_columns]
    ]

    def prefixed(split: str) -> pd.DataFrame:
        subset = split_metrics.loc[split_metrics["split"].eq(split)].drop(columns=["split"])
        rename = {
            column: f"{split}_{column}"
            for column in metric_columns
            if column in subset.columns
        }
        return subset.rename(columns=rename)

    validation = prefixed("validation")
    holdout = prefixed("holdout")
    drift = validation.merge(holdout, on=group_columns, how="outer")
    for split in ["validation", "holdout"]:
        for column in metric_columns:
            prefixed_column = f"{split}_{column}"
            if prefixed_column not in drift.columns:
                continue
            if column in {"support", "month_count"}:
                drift[prefixed_column] = drift[prefixed_column].fillna(0.0)

    if "validation_target_mean" in drift.columns and "holdout_target_mean" in drift.columns:
        drift["target_mean_holdout_minus_validation"] = (
            drift["holdout_target_mean"] - drift["validation_target_mean"]
        )
        drift["validation_positive_holdout_negative_mean"] = (
            drift["validation_target_mean"].gt(0.0) & drift["holdout_target_mean"].lt(0.0)
        )
    if "validation_target_sum" in drift.columns and "holdout_target_sum" in drift.columns:
        drift["target_sum_holdout_minus_validation"] = (
            drift["holdout_target_sum"] - drift["validation_target_sum"]
        )
        drift["validation_positive_holdout_negative_sum"] = (
            drift["validation_target_sum"].gt(0.0) & drift["holdout_target_sum"].lt(0.0)
        )
    if "validation_downside_rate" in drift.columns and "holdout_downside_rate" in drift.columns:
        drift["downside_rate_holdout_minus_validation"] = (
            drift["holdout_downside_rate"] - drift["validation_downside_rate"]
        )

    sort_columns = [
        column
        for column in [
            "validation_positive_holdout_negative_mean",
            "validation_positive_holdout_negative_sum",
            "target_sum_holdout_minus_validation",
            "target_mean_holdout_minus_validation",
        ]
        if column in drift.columns
    ]
    ascending = [False, False, True, True][: len(sort_columns)]
    if sort_columns:
        drift = drift.sort_values(sort_columns, ascending=ascending)
    return drift.reset_index(drop=True)


def add_stateful_examples_context_stress_columns(
    examples: pd.DataFrame,
    drift: pd.DataFrame,
    *,
    group_columns: list[str],
    target_column: str = "target",
) -> pd.DataFrame:
    output = examples.copy()
    if output.empty:
        output["context_stress_flag"] = False
        output["context_stress_penalty"] = 0.0
        output["target_context_stress_adjusted"] = pd.to_numeric(
            output.get(target_column, pd.Series(dtype=float)),
            errors="coerce",
        )
        output["target_context_holdout_mean_floor"] = output[
            "target_context_stress_adjusted"
        ]
        return output

    missing_group_columns = [column for column in group_columns if column not in output.columns]
    if missing_group_columns:
        raise ValueError(f"stateful examples missing group columns: {missing_group_columns}")
    if target_column not in output.columns:
        raise ValueError(f"stateful examples missing target column: {target_column}")
    if drift.empty:
        target = pd.to_numeric(output[target_column], errors="coerce")
        output["context_stress_flag"] = False
        output["context_stress_penalty"] = 0.0
        output["target_context_stress_adjusted"] = target
        output["target_context_holdout_mean_floor"] = target
        return output

    profile_columns = [
        column
        for column in [
            *group_columns,
            "validation_support",
            "holdout_support",
            "validation_target_mean",
            "holdout_target_mean",
            "target_mean_holdout_minus_validation",
            "validation_target_sum",
            "holdout_target_sum",
            "target_sum_holdout_minus_validation",
            "validation_downside_rate",
            "holdout_downside_rate",
            "downside_rate_holdout_minus_validation",
            "validation_positive_holdout_negative_mean",
            "validation_positive_holdout_negative_sum",
        ]
        if column in drift.columns
    ]
    profile = drift.loc[:, profile_columns].copy()
    rename = {
        column: f"context_{column}"
        for column in profile.columns
        if column not in group_columns
    }
    profile = profile.rename(columns=rename)
    generated_columns = [
        *rename.values(),
        "context_stress_flag",
        "context_stress_penalty",
        "target_context_stress_adjusted",
        "target_context_holdout_mean_floor",
    ]
    output = output.drop(
        columns=[column for column in generated_columns if column in output.columns],
        errors="ignore",
    )

    merge_keys: list[str] = []
    for index, column in enumerate(group_columns):
        key = f"__context_group_key_{index}"
        while key in output.columns or key in profile.columns:
            key = f"_{key}"
        merge_keys.append(key)
        output[key] = output[column].astype("string").fillna("__missing__")
        profile[key] = profile[column].astype("string").fillna("__missing__")
    profile = profile.drop(columns=group_columns)
    output = output.merge(profile, on=merge_keys, how="left")
    output = output.drop(columns=merge_keys)

    flag_source = output.get(
        "context_validation_positive_holdout_negative_mean",
        pd.Series(False, index=output.index),
    )
    flag = flag_source.mask(flag_source.isna(), False).astype(bool)
    validation_mean = pd.to_numeric(
        output.get("context_validation_target_mean", pd.Series(np.nan, index=output.index)),
        errors="coerce",
    )
    holdout_mean = pd.to_numeric(
        output.get("context_holdout_target_mean", pd.Series(np.nan, index=output.index)),
        errors="coerce",
    )
    target = pd.to_numeric(output[target_column], errors="coerce")
    penalty = (validation_mean - holdout_mean).clip(lower=0.0).fillna(0.0)
    penalty = penalty.where(flag, 0.0)

    output["context_stress_flag"] = flag
    output["context_stress_penalty"] = penalty
    output["target_context_stress_adjusted"] = target - penalty
    output["target_context_holdout_mean_floor"] = np.minimum(
        target,
        holdout_mean.fillna(target),
    )
    return output


def add_blank_walkforward_stress_columns(
    frame: pd.DataFrame,
    *,
    target_column: str,
    status: str,
) -> pd.DataFrame:
    output = frame.copy()
    target = pd.to_numeric(output[target_column], errors="coerce")
    output["walkforward_profile_status"] = status
    output["walkforward_context_stress_flag"] = False
    output["walkforward_context_stress_penalty"] = 0.0
    output["target_walkforward_context_stress_adjusted"] = target
    output["target_walkforward_context_holdout_mean_floor"] = target
    return output


def add_blank_walkforward_prior_context_columns(
    frame: pd.DataFrame,
    *,
    target_column: str,
    status: str,
) -> pd.DataFrame:
    output = frame.copy()
    target = pd.to_numeric(output[target_column], errors="coerce")
    output["walkforward_prior_context_status"] = status
    output["walkforward_prior_context_support"] = 0.0
    output["walkforward_prior_context_month_count"] = 0.0
    output["walkforward_prior_context_target_sum"] = np.nan
    output["walkforward_prior_context_target_mean"] = np.nan
    output["walkforward_prior_context_target_min"] = np.nan
    output["walkforward_prior_context_target_q10"] = np.nan
    output["walkforward_prior_context_downside_rate"] = np.nan
    output["walkforward_prior_context_large_downside_rate"] = np.nan
    output["walkforward_prior_context_raw_bias"] = np.nan
    output["walkforward_prior_context_support_ok"] = False
    output["walkforward_prior_context_loss_flag"] = False
    output["target_walkforward_prior_context_mean_floor"] = target
    return output


def add_walkforward_prior_context_columns(
    examples: pd.DataFrame,
    *,
    group_columns: list[str],
    target_column: str = "target",
    raw_prediction_column: str = "pred_taken_ev",
    downside_threshold: float = 0.0,
    large_downside_threshold: float = -15.0,
    min_prior_support: int = 1,
) -> pd.DataFrame:
    if examples.empty:
        return add_blank_walkforward_prior_context_columns(
            examples,
            target_column=target_column,
            status="empty",
        )
    if min_prior_support <= 0:
        raise ValueError("min_prior_support must be positive")
    missing_group_columns = [column for column in group_columns if column not in examples.columns]
    if missing_group_columns:
        raise ValueError(f"stateful examples missing group columns: {missing_group_columns}")
    if target_column not in examples.columns:
        raise ValueError(f"stateful examples missing target column: {target_column}")

    working = examples.copy()
    if "dataset_month" not in working.columns and "month" in working.columns:
        working["dataset_month"] = working["month"].astype(str)
    if "dataset_month" not in working.columns:
        raise ValueError("stateful examples missing dataset_month/month column")
    month_values = working["dataset_month"].astype("string").str.slice(0, 7)
    if month_values.isna().any() or month_values.eq("").any():
        raise ValueError("stateful examples contain missing dataset_month values")
    working["__walkforward_month"] = month_values
    working["__walkforward_order"] = np.arange(len(working), dtype="int64")
    months = sorted(str(month) for month in working["__walkforward_month"].unique())

    annotated_frames: list[pd.DataFrame] = []
    for month_index, target_month in enumerate(months):
        target_rows = working.loc[working["__walkforward_month"].eq(target_month)].copy()
        prior_months = months[:month_index]
        if not prior_months:
            annotated_frames.append(
                add_blank_walkforward_prior_context_columns(
                    target_rows,
                    target_column=target_column,
                    status="insufficient_prior_months",
                )
            )
            continue

        prior = working.loc[working["__walkforward_month"].isin(prior_months)].copy()
        prior["split"] = "prior"
        metrics = stateful_examples_metric_summary(
            prior,
            group_columns=group_columns,
            target_column=target_column,
            raw_prediction_column=raw_prediction_column,
            downside_threshold=downside_threshold,
            large_downside_threshold=large_downside_threshold,
        )
        metrics = metrics.loc[metrics["split"].eq("prior")].drop(columns=["split"])
        if metrics.empty:
            annotated_frames.append(
                add_blank_walkforward_prior_context_columns(
                    target_rows,
                    target_column=target_column,
                    status="insufficient_prior_context",
                )
            )
            continue

        rename = {
            "support": "walkforward_prior_context_support",
            "month_count": "walkforward_prior_context_month_count",
            "target_sum": "walkforward_prior_context_target_sum",
            "target_mean": "walkforward_prior_context_target_mean",
            "target_min": "walkforward_prior_context_target_min",
            "target_q10": "walkforward_prior_context_target_q10",
            "downside_rate": "walkforward_prior_context_downside_rate",
            "large_downside_rate": "walkforward_prior_context_large_downside_rate",
            "raw_bias": "walkforward_prior_context_raw_bias",
        }
        keep_columns = [*group_columns, *[column for column in rename if column in metrics.columns]]
        profile = metrics.loc[:, keep_columns].rename(columns=rename)

        merge_keys: list[str] = []
        for index, column in enumerate(group_columns):
            key = f"__prior_context_group_key_{index}"
            while key in target_rows.columns or key in profile.columns:
                key = f"_{key}"
            merge_keys.append(key)
            target_rows[key] = target_rows[column].astype("string").fillna("__missing__")
            profile[key] = profile[column].astype("string").fillna("__missing__")
        profile = profile.drop(columns=group_columns)
        annotated = target_rows.merge(profile, on=merge_keys, how="left")
        annotated = annotated.drop(columns=merge_keys)

        support = pd.to_numeric(
            annotated.get(
                "walkforward_prior_context_support",
                pd.Series(0.0, index=annotated.index),
            ),
            errors="coerce",
        ).fillna(0.0)
        prior_mean = pd.to_numeric(
            annotated.get(
                "walkforward_prior_context_target_mean",
                pd.Series(np.nan, index=annotated.index),
            ),
            errors="coerce",
        )
        target = pd.to_numeric(annotated[target_column], errors="coerce")
        support_ok = support.ge(min_prior_support)
        annotated["walkforward_prior_context_status"] = np.where(
            support_ok,
            "profiled",
            "insufficient_prior_context",
        )
        annotated["walkforward_prior_context_support"] = support
        annotated["walkforward_prior_context_month_count"] = pd.to_numeric(
            annotated.get(
                "walkforward_prior_context_month_count",
                pd.Series(0.0, index=annotated.index),
            ),
            errors="coerce",
        ).fillna(0.0)
        annotated["walkforward_prior_context_support_ok"] = support_ok
        annotated["walkforward_prior_context_loss_flag"] = support_ok & prior_mean.lt(0.0)
        annotated["target_walkforward_prior_context_mean_floor"] = np.minimum(
            target,
            prior_mean.fillna(target),
        ).where(support_ok, target)
        annotated_frames.append(annotated)

    return (
        pd.concat(annotated_frames, ignore_index=True)
        .sort_values("__walkforward_order")
        .drop(columns=["__walkforward_order"], errors="ignore")
        .reset_index(drop=True)
    )


def rename_walkforward_stress_columns(frame: pd.DataFrame) -> pd.DataFrame:
    rename = {
        column: f"walkforward_{column}"
        for column in frame.columns
        if column.startswith("context_")
    }
    rename.update(
        {
            "target_context_stress_adjusted": (
                "target_walkforward_context_stress_adjusted"
            ),
            "target_context_holdout_mean_floor": (
                "target_walkforward_context_holdout_mean_floor"
            ),
        }
    )
    return frame.rename(columns=rename)


def stateful_examples_walkforward_stress_targets(
    examples: pd.DataFrame,
    *,
    group_columns: list[str],
    target_column: str = "target",
    raw_prediction_column: str = "pred_taken_ev",
    downside_threshold: float = 0.0,
    large_downside_threshold: float = -15.0,
    holdout_month_count: int = 1,
    min_validation_months: int = 1,
    min_validation_support: int = 1,
    min_holdout_support: int = 1,
    min_prior_support: int = 1,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if examples.empty:
        raise ValueError("stateful examples are empty")
    if holdout_month_count <= 0:
        raise ValueError("holdout_month_count must be positive")
    if min_validation_months <= 0:
        raise ValueError("min_validation_months must be positive")
    if min_validation_support <= 0:
        raise ValueError("min_validation_support must be positive")
    if min_holdout_support <= 0:
        raise ValueError("min_holdout_support must be positive")
    if min_prior_support <= 0:
        raise ValueError("min_prior_support must be positive")

    missing_group_columns = [column for column in group_columns if column not in examples.columns]
    if missing_group_columns:
        raise ValueError(f"stateful examples missing group columns: {missing_group_columns}")
    if target_column not in examples.columns:
        raise ValueError(f"stateful examples missing target column: {target_column}")

    working = examples.copy()
    if "dataset_month" not in working.columns and "month" in working.columns:
        working["dataset_month"] = working["month"].astype(str)
    if "dataset_month" not in working.columns:
        raise ValueError("stateful examples missing dataset_month/month column")
    month_values = working["dataset_month"].astype("string").str.slice(0, 7)
    if month_values.isna().any() or month_values.eq("").any():
        raise ValueError("stateful examples contain missing dataset_month values")
    working["__walkforward_month"] = month_values
    months = sorted(str(month) for month in working["__walkforward_month"].unique())

    annotated_frames: list[pd.DataFrame] = []
    drift_frames: list[pd.DataFrame] = []
    summary_rows: list[dict[str, object]] = []

    for month_index, target_month in enumerate(months):
        target_rows = working.loc[working["__walkforward_month"].eq(target_month)].copy()
        prior_months = months[:month_index]
        profile_validation_months: list[str] = []
        profile_holdout_months: list[str] = []
        status = "profiled"
        if len(prior_months) < holdout_month_count + min_validation_months:
            status = "insufficient_prior_months"
            annotated = add_blank_walkforward_stress_columns(
                target_rows,
                target_column=target_column,
                status=status,
            )
        else:
            profile_holdout_months = prior_months[-holdout_month_count:]
            profile_validation_months = prior_months[:-holdout_month_count]
            if len(profile_validation_months) < min_validation_months:
                status = "insufficient_validation_months"
                annotated = add_blank_walkforward_stress_columns(
                    target_rows,
                    target_column=target_column,
                    status=status,
                )
            else:
                profile = working.loc[
                    working["__walkforward_month"].isin(
                        [*profile_validation_months, *profile_holdout_months]
                    )
                ].copy()
                profile["split"] = np.where(
                    profile["__walkforward_month"].isin(profile_holdout_months),
                    "holdout",
                    "validation",
                )
                split_metrics = stateful_examples_metric_summary(
                    profile,
                    group_columns=group_columns,
                    target_column=target_column,
                    raw_prediction_column=raw_prediction_column,
                    downside_threshold=downside_threshold,
                    large_downside_threshold=large_downside_threshold,
                )
                drift = stateful_examples_drift_metrics(
                    split_metrics,
                    group_columns=group_columns,
                )
                if not drift.empty:
                    validation_support = pd.to_numeric(
                        drift.get(
                            "validation_support",
                            pd.Series(0.0, index=drift.index),
                        ),
                        errors="coerce",
                    ).fillna(0.0)
                    holdout_support = pd.to_numeric(
                        drift.get("holdout_support", pd.Series(0.0, index=drift.index)),
                        errors="coerce",
                    ).fillna(0.0)
                    validation_mean = pd.to_numeric(
                        drift.get(
                            "validation_target_mean",
                            pd.Series(np.nan, index=drift.index),
                        ),
                        errors="coerce",
                    )
                    holdout_mean = pd.to_numeric(
                        drift.get(
                            "holdout_target_mean",
                            pd.Series(np.nan, index=drift.index),
                        ),
                        errors="coerce",
                    )
                    support_ok = (
                        validation_support.ge(min_validation_support)
                        & holdout_support.ge(min_holdout_support)
                    )
                    flag_source = drift.get(
                        "validation_positive_holdout_negative_mean",
                        pd.Series(False, index=drift.index),
                    )
                    stress_flag = flag_source.mask(
                        flag_source.isna(),
                        False,
                    ).astype(bool)
                    stress_flag = stress_flag & support_ok
                    drift["target_month"] = target_month
                    drift["profile_validation_months"] = ",".join(
                        profile_validation_months
                    )
                    drift["profile_holdout_months"] = ",".join(profile_holdout_months)
                    drift["profile_validation_month_count"] = len(
                        profile_validation_months
                    )
                    drift["profile_holdout_month_count"] = len(profile_holdout_months)
                    drift["walkforward_support_ok"] = support_ok
                    drift["walkforward_context_stress_flag"] = stress_flag
                    drift["walkforward_context_stress_penalty"] = (
                        (validation_mean - holdout_mean).clip(lower=0.0).fillna(0.0)
                    ).where(stress_flag, 0.0)
                    drift_frames.append(drift)

                annotated = add_stateful_examples_context_stress_columns(
                    target_rows,
                    drift,
                    group_columns=group_columns,
                    target_column=target_column,
                )
                validation_support = pd.to_numeric(
                    annotated.get(
                        "context_validation_support",
                        pd.Series(0.0, index=annotated.index),
                    ),
                    errors="coerce",
                ).fillna(0.0)
                holdout_support = pd.to_numeric(
                    annotated.get(
                        "context_holdout_support",
                        pd.Series(0.0, index=annotated.index),
                    ),
                    errors="coerce",
                ).fillna(0.0)
                support_ok = (
                    validation_support.ge(min_validation_support)
                    & holdout_support.ge(min_holdout_support)
                )
                target = pd.to_numeric(annotated[target_column], errors="coerce")
                holdout_mean = pd.to_numeric(
                    annotated.get(
                        "context_holdout_target_mean",
                        pd.Series(np.nan, index=annotated.index),
                    ),
                    errors="coerce",
                )
                flag_source = annotated["context_stress_flag"]
                stress_flag = flag_source.mask(flag_source.isna(), False).astype(bool)
                stress_flag = stress_flag & support_ok
                penalty = (
                    pd.to_numeric(annotated["context_stress_penalty"], errors="coerce")
                    .fillna(0.0)
                    .where(stress_flag, 0.0)
                )
                annotated["context_stress_flag"] = stress_flag
                annotated["context_stress_penalty"] = penalty
                annotated["target_context_stress_adjusted"] = target - penalty
                holdout_floor = pd.Series(
                    np.minimum(target, holdout_mean.fillna(target)),
                    index=annotated.index,
                )
                annotated["target_context_holdout_mean_floor"] = holdout_floor.where(
                    support_ok,
                    target,
                )
                annotated["walkforward_profile_status"] = status

        annotated["walkforward_target_month"] = target_month
        annotated["walkforward_profile_validation_months"] = ",".join(
            profile_validation_months
        )
        annotated["walkforward_profile_holdout_months"] = ",".join(
            profile_holdout_months
        )
        annotated["walkforward_profile_validation_month_count"] = len(
            profile_validation_months
        )
        annotated["walkforward_profile_holdout_month_count"] = len(profile_holdout_months)
        annotated = rename_walkforward_stress_columns(annotated)
        annotated_frames.append(annotated)

        flag_source = annotated["walkforward_context_stress_flag"]
        stress_flag = flag_source.mask(flag_source.isna(), False).astype(bool)
        penalty = pd.to_numeric(
            annotated["walkforward_context_stress_penalty"],
            errors="coerce",
        ).fillna(0.0)
        target = pd.to_numeric(annotated[target_column], errors="coerce")
        adjusted = pd.to_numeric(
            annotated["target_walkforward_context_stress_adjusted"],
            errors="coerce",
        )
        summary_rows.append(
            {
                "target_month": target_month,
                "profile_status": status,
                "row_count": int(len(annotated)),
                "profile_validation_months": ",".join(profile_validation_months),
                "profile_holdout_months": ",".join(profile_holdout_months),
                "profile_validation_month_count": len(profile_validation_months),
                "profile_holdout_month_count": len(profile_holdout_months),
                "stress_flag_count": int(stress_flag.sum()),
                "stress_penalty_sum": float(penalty.sum()),
                "stress_penalty_mean": float(penalty.mean()) if len(penalty) else 0.0,
                "target_mean": float(target.mean()),
                "target_walkforward_context_stress_adjusted_mean": float(
                    adjusted.mean()
                ),
            }
        )

    annotated_examples = pd.concat(annotated_frames, ignore_index=True)
    annotated_examples = add_walkforward_prior_context_columns(
        annotated_examples,
        group_columns=group_columns,
        target_column=target_column,
        raw_prediction_column=raw_prediction_column,
        downside_threshold=downside_threshold,
        large_downside_threshold=large_downside_threshold,
        min_prior_support=min_prior_support,
    )
    annotated_examples = annotated_examples.drop(columns=["__walkforward_month"], errors="ignore")
    profile_drift = (
        pd.concat(drift_frames, ignore_index=True) if drift_frames else pd.DataFrame()
    )
    month_summary = pd.DataFrame(summary_rows)
    return annotated_examples, profile_drift, month_summary


def read_model_trade_delta_frames(
    base_paths: list[Path],
    candidate_paths: list[Path],
    gate_long_quality_column: str = "",
    gate_short_quality_column: str = "",
) -> list[pd.DataFrame]:
    frames: list[pd.DataFrame] = []
    for base_path, candidate_path in pair_model_trade_delta_run_paths(base_paths, candidate_paths):
        base_run_dir = resolve_single_model_policy_run_path(base_path)
        candidate_run_dir = resolve_single_model_policy_run_path(candidate_path)
        _, _, candidate_policy_config = read_model_policy_run_metadata(candidate_run_dir)
        candidate_predictions_value = candidate_policy_config.get("predictions")
        if not candidate_predictions_value:
            raise ValueError(f"candidate run has no predictions path: {candidate_run_dir}")
        selected_long_quality = gate_long_quality_column or str(
            candidate_policy_config.get("long_trade_quality_column", "")
        )
        selected_short_quality = gate_short_quality_column or str(
            candidate_policy_config.get("short_trade_quality_column", "")
        )
        predictions_path = Path(str(candidate_predictions_value))

        base = read_model_trade_exposure_frame(base_run_dir)
        candidate = read_model_trade_exposure_frame(candidate_run_dir)
        base = add_side_prediction_values(
            base,
            predictions_path,
            selected_long_quality,
            selected_short_quality,
            "gate_trade_quality",
        )
        candidate = add_side_prediction_values(
            candidate,
            predictions_path,
            selected_long_quality,
            selected_short_quality,
            "gate_trade_quality",
        )
        delta = build_trade_delta_frame(base, candidate)
        delta.insert(1, "base_run_dir", str(base_run_dir))
        delta.insert(2, "candidate_run_dir", str(candidate_run_dir))
        delta["gate_long_quality_column"] = selected_long_quality
        delta["gate_short_quality_column"] = selected_short_quality
        delta["gate_min_trade_quality"] = candidate_policy_config.get("min_trade_quality", np.nan)
        frames.append(delta)
    return frames


def trade_exposure_group_summary(
    frame: pd.DataFrame,
    group_columns: list[str],
) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=group_columns)
    missing = sorted(set(group_columns) - set(frame.columns))
    if missing:
        raise ValueError(f"trade exposure frame missing columns: {', '.join(missing)}")
    working = frame.copy()
    working["_wins"] = numeric_indicator(working["is_win"])
    working["_longs"] = numeric_indicator(working["is_long"])
    working["_shorts"] = numeric_indicator(working["is_short"])
    working["_forced"] = numeric_indicator(working["is_forced_exit"])
    working["_direction_errors"] = numeric_indicator(working["direction_error"])
    working["_no_edge"] = numeric_indicator(working["no_edge_entry"])
    working["_pred_side_errors"] = numeric_indicator(working["predicted_side_error"])

    summary = (
        working.groupby(group_columns, dropna=False, observed=True)
        .agg(
            trade_count=("adjusted_pnl", "size"),
            total_adjusted_pnl=("adjusted_pnl", "sum"),
            avg_adjusted_pnl=("adjusted_pnl", "mean"),
            win_rate=("_wins", "mean"),
            long_trade_count=("_longs", "sum"),
            short_trade_count=("_shorts", "sum"),
            forced_exit_count=("_forced", "sum"),
            direction_error_rate=("_direction_errors", "mean"),
            no_edge_rate=("_no_edge", "mean"),
            predicted_side_error_rate=("_pred_side_errors", "mean"),
            exit_regret_mean=("exit_regret", "mean"),
            ev_overestimate_vs_realized_mean=("ev_overestimate_vs_realized", "mean"),
        )
        .reset_index()
    )
    if "month" in group_columns:
        month_totals = (
            working.groupby("month", dropna=False, observed=True)
            .agg(
                month_trade_count=("adjusted_pnl", "size"),
                month_total_adjusted_pnl=("adjusted_pnl", "sum"),
            )
            .reset_index()
        )
        summary = summary.merge(month_totals, on="month", how="left")
        month_trade_count = summary["month_trade_count"].replace(0, np.nan)
        month_pnl = summary["month_total_adjusted_pnl"].replace(0, np.nan)
        summary["trade_share"] = summary["trade_count"] / month_trade_count
        summary["pnl_share"] = summary["total_adjusted_pnl"] / month_pnl
    sort_columns = ["total_adjusted_pnl", "trade_count"]
    ascending = [True, False]
    if "month" in group_columns:
        sort_columns = ["month", *sort_columns]
        ascending = [True, *ascending]
    return summary.sort_values(sort_columns, ascending=ascending).reset_index(drop=True)


def add_trade_exposure_diagnostic_buckets(frame: pd.DataFrame) -> pd.DataFrame:
    output = frame.copy()

    numeric_defaults = {
        "pred_taken_ev": np.nan,
        "pred_opposite_ev": np.nan,
        "pred_taken_best_holding_minutes": np.nan,
        "holding_minutes": np.nan,
        "pred_taken_wait_regret": np.nan,
        "pred_taken_entry_local_rank": np.nan,
        "pred_taken_profit_barrier_hit": np.nan,
        "actual_taken_profit_barrier_hit": np.nan,
        "pred_taken_side_confidence": np.nan,
        "pred_side_confidence_gap": np.nan,
        "exit_regret": np.nan,
        "best_side_regret": np.nan,
        "ev_overestimate_vs_realized": np.nan,
    }
    for column, default in numeric_defaults.items():
        if column not in output.columns:
            output[column] = default
        output[column] = pd.to_numeric(output[column], errors="coerce")

    output["pred_side_gap"] = output["pred_taken_ev"] - output["pred_opposite_ev"]
    output["holding_ratio_actual_vs_pred"] = output["holding_minutes"] / output[
        "pred_taken_best_holding_minutes"
    ].replace(0, np.nan)
    output["pred_side_gap_bucket"] = bucket_series(
        output["pred_side_gap"],
        [-float("inf"), 0, 2, 5, 10, float("inf")],
        ["<=0", "0-2", "2-5", "5-10", ">10"],
    )
    output["pred_holding_bucket"] = bucket_series(
        output["pred_taken_best_holding_minutes"],
        [-float("inf"), 120, 360, 720, 1440, float("inf")],
        ["<=2h", "2-6h", "6-12h", "12-24h", ">24h"],
    )
    output["holding_ratio_bucket"] = bucket_series(
        output["holding_ratio_actual_vs_pred"],
        [-float("inf"), 0.1, 0.25, 0.5, 1.0, 2.0, float("inf")],
        ["<=0.1", "0.1-0.25", "0.25-0.5", "0.5-1", "1-2", ">2"],
    )
    output["ev_overestimate_bucket"] = bucket_series(
        output["ev_overestimate_vs_realized"],
        [-float("inf"), 0, 10, 20, 40, float("inf")],
        ["<=0", "0-10", "10-20", "20-40", ">40"],
    )
    output["exit_regret_bucket"] = bucket_series(
        output["exit_regret"],
        [-float("inf"), 0, 10, 20, 40, float("inf")],
        ["<=0", "0-10", "10-20", "20-40", ">40"],
    )
    output["best_side_regret_bucket"] = bucket_series(
        output["best_side_regret"],
        [-float("inf"), 0, 10, 20, 40, float("inf")],
        ["<=0", "0-10", "10-20", "20-40", ">40"],
    )
    output["pred_entry_rank_bucket"] = bucket_series(
        output["pred_taken_entry_local_rank"],
        [-float("inf"), 0.25, 0.5, 0.75, 1.0, float("inf")],
        ["<=0.25", "0.25-0.5", "0.5-0.75", "0.75-1.0", ">1.0"],
    )
    output["pred_side_confidence_bucket"] = bucket_series(
        output["pred_taken_side_confidence"],
        [-float("inf"), 0.4, 0.55, 0.7, 0.85, 1.0, float("inf")],
        ["<=0.4", "0.4-0.55", "0.55-0.7", "0.7-0.85", "0.85-1.0", ">1.0"],
    )
    output["pred_side_confidence_gap_bucket"] = bucket_series(
        output["pred_side_confidence_gap"],
        [-float("inf"), -0.2, 0, 0.2, 0.5, float("inf")],
        ["<=-0.2", "-0.2-0", "0-0.2", "0.2-0.5", ">0.5"],
    )

    predicted_hit = output["pred_taken_profit_barrier_hit"].eq(1)
    actual_hit = output["actual_taken_profit_barrier_hit"].eq(1)
    output["profit_barrier_outcome"] = np.select(
        [
            predicted_hit & actual_hit,
            predicted_hit & ~actual_hit,
            ~predicted_hit & actual_hit,
        ],
        [
            "pred_hit_actual_hit",
            "pred_hit_actual_miss",
            "pred_miss_actual_hit",
        ],
        default="pred_miss_actual_miss",
    )
    return output


def trade_exposure_diagnostic_summary(
    frame: pd.DataFrame,
    group_columns: list[str],
    *,
    large_loss_threshold: float = -15.0,
) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=group_columns)
    missing = sorted(set(group_columns) - set(frame.columns))
    if missing:
        raise ValueError(f"trade exposure diagnostics missing columns: {', '.join(missing)}")

    working = frame.copy()
    working["adjusted_pnl"] = pd.to_numeric(working["adjusted_pnl"], errors="coerce")
    working["_wins"] = numeric_indicator(working["adjusted_pnl"] > 0)
    working["_losses"] = numeric_indicator(working["adjusted_pnl"] <= 0)
    working["_large_losses"] = numeric_indicator(working["adjusted_pnl"] <= large_loss_threshold)
    working["_direction_errors"] = numeric_indicator(
        working.get("direction_error", pd.Series(False, index=working.index))
    )
    working["_pred_side_errors"] = numeric_indicator(
        working.get("predicted_side_error", pd.Series(False, index=working.index))
    )
    working["_predicted_profit_barrier_hits"] = numeric_indicator(
        working["pred_taken_profit_barrier_hit"].eq(1)
    )
    working["_actual_profit_barrier_hits"] = numeric_indicator(
        working["actual_taken_profit_barrier_hit"].eq(1)
    )
    aggregations: dict[str, tuple[str, str]] = {
        "trade_count": ("adjusted_pnl", "size"),
        "total_adjusted_pnl": ("adjusted_pnl", "sum"),
        "avg_adjusted_pnl": ("adjusted_pnl", "mean"),
        "win_rate": ("_wins", "mean"),
        "loss_rate": ("_losses", "mean"),
        "large_loss_count": ("_large_losses", "sum"),
        "large_loss_rate": ("_large_losses", "mean"),
        "direction_error_rate": ("_direction_errors", "mean"),
        "predicted_side_error_rate": ("_pred_side_errors", "mean"),
        "predicted_profit_barrier_hit_rate": ("_predicted_profit_barrier_hits", "mean"),
        "actual_profit_barrier_hit_rate": ("_actual_profit_barrier_hits", "mean"),
        "pred_side_gap_mean": ("pred_side_gap", "mean"),
        "pred_taken_ev_mean": ("pred_taken_ev", "mean"),
        "pred_taken_holding_mean": ("pred_taken_best_holding_minutes", "mean"),
        "holding_ratio_mean": ("holding_ratio_actual_vs_pred", "mean"),
        "pred_taken_side_confidence_mean": ("pred_taken_side_confidence", "mean"),
        "pred_side_confidence_gap_mean": ("pred_side_confidence_gap", "mean"),
        "exit_regret_mean": ("exit_regret", "mean"),
        "best_side_regret_mean": ("best_side_regret", "mean"),
        "ev_overestimate_vs_realized_mean": ("ev_overestimate_vs_realized", "mean"),
    }
    summary = (
        working.groupby(group_columns, dropna=False, observed=True)
        .agg(**aggregations)
        .reset_index()
    )
    if "month" in group_columns:
        month_totals = (
            working.groupby("month", dropna=False, observed=True)
            .agg(
                month_trade_count=("adjusted_pnl", "size"),
                month_total_adjusted_pnl=("adjusted_pnl", "sum"),
            )
            .reset_index()
        )
        summary = summary.merge(month_totals, on="month", how="left")
        summary["trade_share"] = summary["trade_count"] / summary[
            "month_trade_count"
        ].replace(0, np.nan)
        summary["pnl_share"] = summary["total_adjusted_pnl"] / summary[
            "month_total_adjusted_pnl"
        ].replace(0, np.nan)
    sort_columns = ["total_adjusted_pnl", "trade_count"]
    ascending = [True, False]
    if "month" in group_columns:
        sort_columns = ["month", *sort_columns]
        ascending = [True, *ascending]
    return summary.sort_values(sort_columns, ascending=ascending).reset_index(drop=True)


def selected_trade_walkforward_context_outcomes(
    annotated: pd.DataFrame,
    *,
    group_columns: list[str],
    target_column: str = "adjusted_pnl",
    downside_threshold: float = 0.0,
    large_downside_threshold: float = -15.0,
) -> pd.DataFrame:
    if annotated.empty:
        return pd.DataFrame(columns=["target_month", *group_columns])
    missing_group_columns = [column for column in group_columns if column not in annotated.columns]
    if missing_group_columns:
        raise ValueError(f"selected trades missing group columns: {missing_group_columns}")
    if target_column not in annotated.columns:
        raise ValueError(f"selected trades missing target column: {target_column}")

    working = annotated.copy()
    if "dataset_month" not in working.columns and "month" in working.columns:
        working["dataset_month"] = working["month"].astype(str)
    if "dataset_month" not in working.columns:
        raise ValueError("selected trades missing dataset_month/month column")
    working["target_month"] = working["dataset_month"].astype("string").str.slice(0, 7)
    working["_target"] = pd.to_numeric(working[target_column], errors="coerce")
    working["_downside"] = working["_target"] <= downside_threshold
    working["_large_downside"] = working["_target"] <= large_downside_threshold
    working["_stress_flag"] = (
        working.get(
            "walkforward_context_stress_flag",
            pd.Series(False, index=working.index),
        )
        .mask(lambda series: series.isna(), False)
        .astype(bool)
    )
    working["_stress_penalty"] = pd.to_numeric(
        working.get(
            "walkforward_context_stress_penalty",
            pd.Series(0.0, index=working.index),
        ),
        errors="coerce",
    ).fillna(0.0)
    working = working.dropna(subset=["_target"])
    if working.empty:
        return pd.DataFrame(columns=["target_month", *group_columns])

    for column in group_columns:
        working[column] = working[column].astype("string").fillna("__missing__")

    keys = ["target_month", *group_columns]
    outcomes = (
        working.groupby(keys, dropna=False, observed=True)
        .agg(
            target_support=("_target", "size"),
            target_adjusted_pnl_sum=("_target", "sum"),
            target_adjusted_pnl_mean=("_target", "mean"),
            target_adjusted_pnl_min=("_target", "min"),
            target_adjusted_pnl_q10=("_target", lambda series: float(series.quantile(0.10))),
            target_downside_rate=("_downside", "mean"),
            target_large_downside_rate=("_large_downside", "mean"),
            walkforward_stress_flag_count=("_stress_flag", "sum"),
            walkforward_stress_penalty_sum=("_stress_penalty", "sum"),
        )
        .reset_index()
    )

    profile_columns = [
        column
        for column in [
            "walkforward_profile_status",
            "walkforward_profile_validation_months",
            "walkforward_profile_holdout_months",
            "walkforward_profile_validation_month_count",
            "walkforward_profile_holdout_month_count",
            "walkforward_context_validation_support",
            "walkforward_context_holdout_support",
            "walkforward_context_validation_target_sum",
            "walkforward_context_holdout_target_sum",
            "walkforward_context_target_sum_holdout_minus_validation",
            "walkforward_context_validation_target_mean",
            "walkforward_context_holdout_target_mean",
            "walkforward_context_target_mean_holdout_minus_validation",
            "walkforward_context_validation_downside_rate",
            "walkforward_context_holdout_downside_rate",
            "walkforward_context_downside_rate_holdout_minus_validation",
            "walkforward_context_validation_positive_holdout_negative_mean",
            "walkforward_context_validation_positive_holdout_negative_sum",
            "walkforward_prior_context_status",
            "walkforward_prior_context_support",
            "walkforward_prior_context_month_count",
            "walkforward_prior_context_target_mean",
            "walkforward_prior_context_downside_rate",
            "walkforward_prior_context_large_downside_rate",
            "walkforward_prior_context_support_ok",
            "walkforward_prior_context_loss_flag",
        ]
        if column in working.columns
    ]
    if profile_columns:
        profile = working.groupby(keys, dropna=False, observed=True)[profile_columns].first().reset_index()
        outcomes = outcomes.merge(profile, on=keys, how="left")

    return outcomes.sort_values(
        ["target_month", "target_adjusted_pnl_sum", "target_support"],
        ascending=[True, True, False],
    ).reset_index(drop=True)


def selected_trade_walkforward_context_stress_targets(
    trades: pd.DataFrame,
    *,
    group_columns: list[str],
    target_column: str = "adjusted_pnl",
    raw_prediction_column: str = "pred_taken_ev",
    downside_threshold: float = 0.0,
    large_downside_threshold: float = -15.0,
    holdout_month_count: int = 1,
    min_validation_months: int = 1,
    min_validation_support: int = 1,
    min_holdout_support: int = 1,
    min_prior_support: int = 1,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if trades.empty:
        raise ValueError("selected trades are empty")
    working = trades.copy()
    if "dataset_month" not in working.columns and "month" in working.columns:
        working["dataset_month"] = working["month"].astype(str)
    if "candidate_side" not in working.columns and "direction" in working.columns:
        working["candidate_side"] = working["direction"].astype(str).str.lower()

    annotated, profile_drift, month_summary = stateful_examples_walkforward_stress_targets(
        working,
        group_columns=group_columns,
        target_column=target_column,
        raw_prediction_column=raw_prediction_column,
        downside_threshold=downside_threshold,
        large_downside_threshold=large_downside_threshold,
        holdout_month_count=holdout_month_count,
        min_validation_months=min_validation_months,
        min_validation_support=min_validation_support,
        min_holdout_support=min_holdout_support,
        min_prior_support=min_prior_support,
    )
    outcomes = selected_trade_walkforward_context_outcomes(
        annotated,
        group_columns=group_columns,
        target_column=target_column,
        downside_threshold=downside_threshold,
        large_downside_threshold=large_downside_threshold,
    )
    return annotated, profile_drift, month_summary, outcomes


def holdout_case_ids(frame: pd.DataFrame) -> pd.Series:
    period = frame["period_start"].astype(str).str.slice(0, 10)
    spread = frame.get("spread_points", pd.Series(0.0, index=frame.index)).astype(str)
    slippage = frame.get("slippage_points", pd.Series(0.0, index=frame.index)).astype(str)
    delay = frame.get("execution_delay_bars", pd.Series(0, index=frame.index)).astype(str)
    return (
        frame["sweep_source"].astype(str)
        + "|"
        + period
        + "|spread="
        + spread
        + "|slippage="
        + slippage
        + "|delay="
        + delay
    )


def summarize_holdout_audit(
    holdout_frames: list[pd.DataFrame],
    validation_summary: pd.DataFrame | None = None,
    min_holdout_cases: int = 1,
    min_trades_per_case: int = 1,
    max_forced_exit_rate: float = 1.0,
    max_drawdown: float = 1e100,
    min_adjusted_pnl_per_case: float = 0.0,
) -> pd.DataFrame:
    if min_holdout_cases <= 0:
        raise ValueError("min_holdout_cases must be positive")
    if min_trades_per_case < 0:
        raise ValueError("min_trades_per_case must be non-negative")
    if max_forced_exit_rate < 0:
        raise ValueError("max_forced_exit_rate must be non-negative")
    if max_drawdown < 0:
        raise ValueError("max_drawdown must be non-negative")
    if not holdout_frames:
        raise ValueError("at least one holdout frame is required")

    holdouts = pd.concat(
        [normalize_sweep_metrics(frame, f"holdout_{index}") for index, frame in enumerate(holdout_frames)],
        ignore_index=True,
    ).copy()
    holdouts["holdout_case"] = holdout_case_ids(holdouts)
    holdouts["holdout_month"] = holdouts["period_start"].astype(str).str.slice(0, 7)
    holdouts["holdout_case_ok"] = (
        (holdouts["trade_count"] >= min_trades_per_case)
        & (holdouts["forced_exit_rate"] <= max_forced_exit_rate)
        & (holdouts["max_drawdown"] <= max_drawdown)
        & (holdouts["total_adjusted_pnl"] >= min_adjusted_pnl_per_case)
    )
    holdouts["holdout_positive_case"] = holdouts["total_adjusted_pnl"] > 0

    grouped = holdouts.groupby(SWEEP_KEY_COLUMNS, dropna=False)
    summary = grouped.agg(
        holdout_case_count=("holdout_case", "nunique"),
        holdout_month_count=("holdout_month", "nunique"),
        holdout_case_ok_count=("holdout_case_ok", "sum"),
        holdout_positive_case_count=("holdout_positive_case", "sum"),
        holdout_total_adjusted_pnl_min=("total_adjusted_pnl", "min"),
        holdout_total_adjusted_pnl_sum=("total_adjusted_pnl", "sum"),
        holdout_total_adjusted_pnl_mean=("total_adjusted_pnl", "mean"),
        holdout_total_raw_pnl_min=("total_raw_pnl", "min"),
        holdout_trade_count_min=("trade_count", "min"),
        holdout_trade_count_sum=("trade_count", "sum"),
        holdout_forced_exit_rate_max=("forced_exit_rate", "max"),
        holdout_max_drawdown_max=("max_drawdown", "max"),
        holdout_short_trade_share_max=("short_trade_share", "max"),
        holdout_max_side_trade_share_max=("max_side_trade_share", "max"),
        holdout_direction_combined_regime_pnl_min=(
            "direction_combined_regime_adjusted_pnl_min",
            "min",
        ),
        holdout_direction_error_rate_max=("direction_error_rate", "max"),
        holdout_ev_overestimate_vs_realized_mean_max=(
            "ev_overestimate_vs_realized_mean",
            "max",
        ),
    ).reset_index()
    summary["holdout_eligible"] = (
        (summary["holdout_case_count"] >= min_holdout_cases)
        & (summary["holdout_case_ok_count"] == summary["holdout_case_count"])
    )
    summary["holdout_positive_case_rate"] = (
        summary["holdout_positive_case_count"] / summary["holdout_case_count"].replace(0, np.nan)
    ).fillna(0.0)

    if validation_summary is not None:
        validation = normalize_sweep_key_columns(validation_summary).drop_duplicates(
            subset=SWEEP_KEY_COLUMNS,
            keep="first",
        )
        summary = validation.merge(
            summary,
            on=SWEEP_KEY_COLUMNS,
            how="inner",
            suffixes=("_validation", ""),
        )
        if "eligible" in summary.columns:
            summary["validation_eligible"] = summary["eligible"].astype(bool)
            summary["audit_eligible"] = summary["validation_eligible"] & summary["holdout_eligible"]
        else:
            summary["audit_eligible"] = summary["holdout_eligible"]
    else:
        summary["audit_eligible"] = summary["holdout_eligible"]

    validation_sort_column = (
        "total_adjusted_pnl_min_cost"
        if "total_adjusted_pnl_min_cost" in summary.columns
        else "holdout_total_adjusted_pnl_min"
    )
    return summary.sort_values(
        [
            "audit_eligible",
            "holdout_eligible",
            "holdout_total_adjusted_pnl_min",
            validation_sort_column,
            "holdout_total_adjusted_pnl_sum",
            "holdout_max_drawdown_max",
        ],
        ascending=[False, False, False, False, False, True],
    ).reset_index(drop=True)


def handle_model_sweep_summary(args: argparse.Namespace) -> int:
    paths = parse_csv_paths(args.sweeps)
    frames = read_sweep_frames(paths)
    summary = summarize_sweep_frames(
        frames=frames,
        min_folds=args.min_folds,
        min_trades_per_fold=args.min_trades_per_fold,
        max_forced_exit_rate=args.max_forced_exit_rate,
        max_drawdown=args.max_drawdown,
        min_adjusted_pnl_per_fold=args.min_adjusted_pnl_per_fold,
        sort_by=args.sort_by,
    )
    run_dir = make_run_dir(args.output_dir, "model_sweep_summary")
    summary.to_csv(run_dir / "metrics.csv", index=False)
    metadata = {
        "sweeps": [str(path) for path in paths],
        "min_folds": args.min_folds,
        "min_trades_per_fold": args.min_trades_per_fold,
        "max_forced_exit_rate": args.max_forced_exit_rate,
        "max_drawdown": args.max_drawdown,
        "min_adjusted_pnl_per_fold": args.min_adjusted_pnl_per_fold,
        "sort_by": args.sort_by,
    }
    with (run_dir / "config.json").open("w", encoding="utf-8") as handle:
        json.dump(metadata, handle, ensure_ascii=False, indent=2)
    print(summary.head(args.top_n).to_string(index=False))
    print(f"artifacts: {run_dir}")
    return 0


def handle_model_candidate_selection(args: argparse.Namespace) -> int:
    base_paths = parse_csv_paths(args.base_sweeps)
    cost_paths = parse_csv_paths(args.cost_sweeps)
    base_frames = read_sweep_frames(base_paths)
    cost_frames = read_sweep_frames(cost_paths)
    summary = summarize_candidate_selection(
        base_frames=base_frames,
        cost_frames=cost_frames,
        min_folds=args.min_folds,
        min_base_folds=args.min_base_folds,
        min_cost_folds=args.min_cost_folds,
        min_trades_per_fold=args.min_trades_per_fold,
        max_forced_exit_rate=args.max_forced_exit_rate,
        max_drawdown=args.max_drawdown,
        min_base_adjusted_pnl_per_fold=args.min_base_adjusted_pnl_per_fold,
        min_cost_adjusted_pnl_per_fold=args.min_cost_adjusted_pnl_per_fold,
        max_cost_pnl_drop=args.max_cost_pnl_drop,
        max_side_loss_per_fold=args.max_side_loss_per_fold,
        plateau_column=args.plateau_column,
        plateau_radius=args.plateau_radius,
        min_plateau_neighbors=args.min_plateau_neighbors,
        max_direction_session_loss_per_fold=args.max_direction_session_loss_per_fold,
        max_combined_regime_loss_per_fold=args.max_combined_regime_loss_per_fold,
        max_direction_combined_regime_loss_per_fold=(
            args.max_direction_combined_regime_loss_per_fold
        ),
        max_predicted_profit_barrier_miss_rate=args.max_predicted_profit_barrier_miss_rate,
        max_actual_profit_barrier_miss_rate=args.max_actual_profit_barrier_miss_rate,
        max_profit_barrier_calibration_overestimate=args.max_profit_barrier_calibration_overestimate,
        max_short_trade_share=args.max_short_trade_share,
        max_side_trade_share=args.max_side_trade_share,
        max_smoothed_actual_profit_barrier_miss_rate=(
            args.max_smoothed_actual_profit_barrier_miss_rate
        ),
        max_smoothed_profit_barrier_calibration_overestimate=(
            args.max_smoothed_profit_barrier_calibration_overestimate
        ),
        max_direction_error_rate=args.max_direction_error_rate,
        max_predicted_side_error_rate=args.max_predicted_side_error_rate,
        max_no_edge_rate=args.max_no_edge_rate,
        max_exit_regret_mean=args.max_exit_regret_mean,
        max_ev_overestimate_vs_realized_mean=args.max_ev_overestimate_vs_realized_mean,
        group_loss_penalty_weight=args.group_loss_penalty_weight,
        diagnostic_penalty_weight=args.diagnostic_penalty_weight,
        diagnostic_direction_error_rate_threshold=(
            args.diagnostic_direction_error_rate_threshold
        ),
        diagnostic_actual_profit_barrier_miss_rate_threshold=(
            args.diagnostic_actual_profit_barrier_miss_rate_threshold
        ),
        diagnostic_ev_overestimate_vs_realized_mean_threshold=(
            args.diagnostic_ev_overestimate_vs_realized_mean_threshold
        ),
        diagnostic_direction_error_rate_scale=args.diagnostic_direction_error_rate_scale,
        diagnostic_actual_profit_barrier_miss_rate_scale=(
            args.diagnostic_actual_profit_barrier_miss_rate_scale
        ),
        diagnostic_ev_overestimate_vs_realized_mean_scale=(
            args.diagnostic_ev_overestimate_vs_realized_mean_scale
        ),
        candidate_rank_mode=args.candidate_rank_mode,
        near_top_cost_pnl_tolerance=args.near_top_cost_pnl_tolerance,
        near_top_group_loss_weight=args.near_top_group_loss_weight,
        near_top_drawdown_weight=args.near_top_drawdown_weight,
        near_top_ev_overestimate_weight=args.near_top_ev_overestimate_weight,
        near_top_exit_regret_weight=args.near_top_exit_regret_weight,
        near_top_actual_miss_weight=args.near_top_actual_miss_weight,
        near_top_side_share_weight=args.near_top_side_share_weight,
        near_top_pnl_stability_weight=args.near_top_pnl_stability_weight,
        stress_cost_pnl_sum_reward_weight=args.stress_cost_pnl_sum_reward_weight,
        stress_base_pnl_sum_reward_weight=args.stress_base_pnl_sum_reward_weight,
    )
    run_dir = make_run_dir(args.output_dir, "model_candidate_selection")
    summary.to_csv(run_dir / "metrics.csv", index=False)
    metadata = {
        "base_sweeps": [str(path) for path in base_paths],
        "cost_sweeps": [str(path) for path in cost_paths],
        "min_folds": args.min_folds,
        "min_base_folds": args.min_base_folds,
        "min_cost_folds": args.min_cost_folds,
        "min_trades_per_fold": args.min_trades_per_fold,
        "max_forced_exit_rate": args.max_forced_exit_rate,
        "max_drawdown": args.max_drawdown,
        "min_base_adjusted_pnl_per_fold": args.min_base_adjusted_pnl_per_fold,
        "min_cost_adjusted_pnl_per_fold": args.min_cost_adjusted_pnl_per_fold,
        "max_cost_pnl_drop": args.max_cost_pnl_drop,
        "max_side_loss_per_fold": args.max_side_loss_per_fold,
        "max_direction_session_loss_per_fold": args.max_direction_session_loss_per_fold,
        "max_combined_regime_loss_per_fold": args.max_combined_regime_loss_per_fold,
        "max_direction_combined_regime_loss_per_fold": (
            args.max_direction_combined_regime_loss_per_fold
        ),
        "max_predicted_profit_barrier_miss_rate": args.max_predicted_profit_barrier_miss_rate,
        "max_actual_profit_barrier_miss_rate": args.max_actual_profit_barrier_miss_rate,
        "max_profit_barrier_calibration_overestimate": args.max_profit_barrier_calibration_overestimate,
        "max_short_trade_share": args.max_short_trade_share,
        "max_side_trade_share": args.max_side_trade_share,
        "max_smoothed_actual_profit_barrier_miss_rate": (
            args.max_smoothed_actual_profit_barrier_miss_rate
        ),
        "max_smoothed_profit_barrier_calibration_overestimate": (
            args.max_smoothed_profit_barrier_calibration_overestimate
        ),
        "max_direction_error_rate": args.max_direction_error_rate,
        "max_predicted_side_error_rate": args.max_predicted_side_error_rate,
        "max_no_edge_rate": args.max_no_edge_rate,
        "max_exit_regret_mean": args.max_exit_regret_mean,
        "max_ev_overestimate_vs_realized_mean": args.max_ev_overestimate_vs_realized_mean,
        "group_loss_penalty_weight": args.group_loss_penalty_weight,
        "diagnostic_penalty_weight": args.diagnostic_penalty_weight,
        "diagnostic_direction_error_rate_threshold": (
            args.diagnostic_direction_error_rate_threshold
        ),
        "diagnostic_actual_profit_barrier_miss_rate_threshold": (
            args.diagnostic_actual_profit_barrier_miss_rate_threshold
        ),
        "diagnostic_ev_overestimate_vs_realized_mean_threshold": (
            args.diagnostic_ev_overestimate_vs_realized_mean_threshold
        ),
        "diagnostic_direction_error_rate_scale": args.diagnostic_direction_error_rate_scale,
        "diagnostic_actual_profit_barrier_miss_rate_scale": (
            args.diagnostic_actual_profit_barrier_miss_rate_scale
        ),
        "diagnostic_ev_overestimate_vs_realized_mean_scale": (
            args.diagnostic_ev_overestimate_vs_realized_mean_scale
        ),
        "candidate_rank_mode": args.candidate_rank_mode,
        "near_top_cost_pnl_tolerance": args.near_top_cost_pnl_tolerance,
        "near_top_group_loss_weight": args.near_top_group_loss_weight,
        "near_top_drawdown_weight": args.near_top_drawdown_weight,
        "near_top_ev_overestimate_weight": args.near_top_ev_overestimate_weight,
        "near_top_exit_regret_weight": args.near_top_exit_regret_weight,
        "near_top_actual_miss_weight": args.near_top_actual_miss_weight,
        "near_top_side_share_weight": args.near_top_side_share_weight,
        "near_top_pnl_stability_weight": args.near_top_pnl_stability_weight,
        "stress_cost_pnl_sum_reward_weight": args.stress_cost_pnl_sum_reward_weight,
        "stress_base_pnl_sum_reward_weight": args.stress_base_pnl_sum_reward_weight,
        "plateau_column": args.plateau_column,
        "plateau_radius": args.plateau_radius,
        "min_plateau_neighbors": args.min_plateau_neighbors,
    }
    with (run_dir / "config.json").open("w", encoding="utf-8") as handle:
        json.dump(metadata, handle, ensure_ascii=False, indent=2)
    print(summary.head(args.top_n).to_string(index=False))
    print(f"artifacts: {run_dir}")
    return 0


CANDIDATE_SELECTION_CONFIG_DEFAULTS: dict[str, object] = {
    "min_folds": 2,
    "min_base_folds": None,
    "min_cost_folds": None,
    "min_trades_per_fold": 30,
    "max_forced_exit_rate": 0.0,
    "max_drawdown": 100.0,
    "min_base_adjusted_pnl_per_fold": 0.0,
    "min_cost_adjusted_pnl_per_fold": 0.0,
    "max_cost_pnl_drop": 1e100,
    "max_side_loss_per_fold": 1e100,
    "max_direction_session_loss_per_fold": 1e100,
    "max_combined_regime_loss_per_fold": 1e100,
    "max_direction_combined_regime_loss_per_fold": 1e100,
    "max_predicted_profit_barrier_miss_rate": 1.0,
    "max_actual_profit_barrier_miss_rate": 1.0,
    "max_profit_barrier_calibration_overestimate": 1.0,
    "max_short_trade_share": 1.0,
    "max_side_trade_share": 1.0,
    "max_smoothed_actual_profit_barrier_miss_rate": 1.0,
    "max_smoothed_profit_barrier_calibration_overestimate": 1.0,
    "max_direction_error_rate": 1.0,
    "max_predicted_side_error_rate": 1.0,
    "max_no_edge_rate": 1.0,
    "max_exit_regret_mean": 1e100,
    "max_ev_overestimate_vs_realized_mean": 1e100,
    "group_loss_penalty_weight": 0.0,
    "diagnostic_penalty_weight": 0.0,
    "diagnostic_direction_error_rate_threshold": 1.0,
    "diagnostic_actual_profit_barrier_miss_rate_threshold": 1.0,
    "diagnostic_ev_overestimate_vs_realized_mean_threshold": 1e100,
    "diagnostic_direction_error_rate_scale": 100.0,
    "diagnostic_actual_profit_barrier_miss_rate_scale": 100.0,
    "diagnostic_ev_overestimate_vs_realized_mean_scale": 1.0,
    "candidate_rank_mode": "pnl",
    "near_top_cost_pnl_tolerance": 0.0,
    "near_top_group_loss_weight": 1.0,
    "near_top_drawdown_weight": 1.0,
    "near_top_ev_overestimate_weight": 1.0,
    "near_top_exit_regret_weight": 1.0,
    "near_top_actual_miss_weight": 100.0,
    "near_top_side_share_weight": 100.0,
    "near_top_pnl_stability_weight": 0.0,
    "stress_cost_pnl_sum_reward_weight": 0.0,
    "stress_base_pnl_sum_reward_weight": 0.0,
    "plateau_column": "short_entry_threshold_offset",
    "plateau_radius": 0.0,
    "min_plateau_neighbors": 0,
}


def candidate_selection_kwargs_from_mapping(mapping: dict[str, object]) -> dict[str, object]:
    return {
        key: mapping.get(key, default)
        for key, default in CANDIDATE_SELECTION_CONFIG_DEFAULTS.items()
    }


def candidate_key_frame(row: pd.Series) -> pd.DataFrame:
    return normalize_sweep_key_columns(
        pd.DataFrame([{column: row[column] for column in SWEEP_KEY_COLUMNS}])
    )


def candidate_keys_equal(left: pd.Series, right: pd.Series) -> bool:
    left_key = candidate_key_frame(left).iloc[0]
    right_key = candidate_key_frame(right).iloc[0]
    return all(left_key[column] == right_key[column] for column in SWEEP_KEY_COLUMNS)


def sweep_fold_label(frame: pd.DataFrame) -> str:
    if "period_start" in frame.columns:
        values = frame["period_start"].dropna().astype(str).str.slice(0, 7).unique()
        if len(values) == 1 and values[0]:
            return str(values[0])
    if "sweep_source" in frame.columns:
        values = frame["sweep_source"].dropna().astype(str).unique()
        if len(values) == 1:
            return str(values[0])
    return f"frame_{id(frame)}"


def candidate_summary_row(summary: pd.DataFrame, candidate: pd.Series) -> pd.Series | None:
    if summary.empty:
        return None
    key = candidate_key_frame(candidate)
    merged = normalize_sweep_key_columns(summary).merge(key, on=SWEEP_KEY_COLUMNS, how="inner")
    if merged.empty:
        return None
    return merged.iloc[0]


def selected_candidate_fold_summary(
    frames: list[pd.DataFrame],
    candidate: pd.Series,
    min_trades_per_fold: int,
    max_forced_exit_rate: float,
    max_drawdown: float,
    min_adjusted_pnl_per_fold: float,
) -> pd.Series | None:
    if not frames:
        return None
    summary = summarize_sweep_frames(
        frames=frames,
        min_folds=len(frames),
        min_trades_per_fold=min_trades_per_fold,
        max_forced_exit_rate=max_forced_exit_rate,
        max_drawdown=max_drawdown,
        min_adjusted_pnl_per_fold=min_adjusted_pnl_per_fold,
        sort_by="min_pnl",
    )
    return candidate_summary_row(summary, candidate)


def add_fold_summary_metrics(
    row: dict[str, object],
    prefix: str,
    summary: pd.Series | None,
) -> None:
    if summary is None:
        row[f"{prefix}_fold_count"] = 0
        row[f"{prefix}_eligible"] = False
        row[f"{prefix}_total_adjusted_pnl_min"] = np.nan
        row[f"{prefix}_total_adjusted_pnl_sum"] = np.nan
        row[f"{prefix}_trade_count_min"] = np.nan
        row[f"{prefix}_max_drawdown_max"] = np.nan
        row[f"{prefix}_forced_exit_rate_max"] = np.nan
        return
    row[f"{prefix}_fold_count"] = int(summary.get("fold_count", 0))
    row[f"{prefix}_eligible"] = bool(summary.get("eligible", False))
    row[f"{prefix}_total_adjusted_pnl_min"] = float(
        summary.get("total_adjusted_pnl_min", np.nan)
    )
    row[f"{prefix}_total_adjusted_pnl_sum"] = float(
        summary.get("total_adjusted_pnl_sum", np.nan)
    )
    row[f"{prefix}_trade_count_min"] = float(summary.get("trade_count_min", np.nan))
    row[f"{prefix}_max_drawdown_max"] = float(summary.get("max_drawdown_max", np.nan))
    row[f"{prefix}_forced_exit_rate_max"] = float(
        summary.get("forced_exit_rate_max", np.nan)
    )


def summarize_candidate_selection_jackknife(
    base_frames: list[pd.DataFrame],
    cost_frames: list[pd.DataFrame],
    selection_config: dict[str, object],
) -> pd.DataFrame:
    if len(base_frames) < 2:
        raise ValueError("at least two base frames are required for jackknife")
    if len(cost_frames) < 2:
        raise ValueError("at least two cost frames are required for jackknife")

    kwargs = candidate_selection_kwargs_from_mapping(selection_config)
    full_summary = summarize_candidate_selection(
        base_frames=base_frames,
        cost_frames=cost_frames,
        **kwargs,
    )
    full_top = full_summary.iloc[0] if not full_summary.empty else None
    base_labeled = [(sweep_fold_label(frame), frame) for frame in base_frames]
    cost_labeled = [(sweep_fold_label(frame), frame) for frame in cost_frames]
    fold_labels = sorted({label for label, _ in base_labeled} | {label for label, _ in cost_labeled})

    rows: list[dict[str, object]] = []
    for fold_label in fold_labels:
        train_base = [frame for label, frame in base_labeled if label != fold_label]
        train_cost = [frame for label, frame in cost_labeled if label != fold_label]
        holdout_base = [frame for label, frame in base_labeled if label == fold_label]
        holdout_cost = [frame for label, frame in cost_labeled if label == fold_label]
        row: dict[str, object] = {
            "left_out_fold": fold_label,
            "train_base_fold_count": len(train_base),
            "train_cost_fold_count": len(train_cost),
            "holdout_base_fold_count": len(holdout_base),
            "holdout_cost_fold_count": len(holdout_cost),
        }
        if not train_base or not train_cost:
            row["status"] = "insufficient_train_folds"
            rows.append(row)
            continue

        train_kwargs = dict(kwargs)
        train_kwargs["min_base_folds"] = min(
            int(train_kwargs["min_base_folds"] or train_kwargs["min_folds"]),
            len(train_base),
        )
        train_kwargs["min_cost_folds"] = min(
            int(train_kwargs["min_cost_folds"] or train_kwargs["min_folds"]),
            len(train_cost),
        )
        train_kwargs["min_folds"] = min(
            int(train_kwargs["min_folds"]),
            int(train_kwargs["min_base_folds"]),
            int(train_kwargs["min_cost_folds"]),
        )
        train_summary = summarize_candidate_selection(
            base_frames=train_base,
            cost_frames=train_cost,
            **train_kwargs,
        )
        row["train_candidate_count"] = len(train_summary)
        row["train_eligible_count"] = (
            int(train_summary["eligible"].sum()) if "eligible" in train_summary.columns else 0
        )
        if train_summary.empty:
            row["status"] = "no_candidates"
            rows.append(row)
            continue

        selected = train_summary.iloc[0]
        row["status"] = "selected"
        row["selected_train_eligible"] = bool(selected.get("eligible", False))
        row["matches_full_top"] = (
            bool(candidate_keys_equal(selected, full_top)) if full_top is not None else False
        )
        for column in SWEEP_KEY_COLUMNS:
            row[column] = selected[column]
        for column in [
            "total_adjusted_pnl_min_base",
            "total_adjusted_pnl_sum_base",
            "total_adjusted_pnl_min_cost",
            "total_adjusted_pnl_sum_cost",
            "total_adjusted_pnl_std_base",
            "total_adjusted_pnl_std_cost",
            "pnl_stability_risk_all",
            "near_top_risk_score",
            "stress_risk_score",
            "max_drawdown_max_all",
            "group_loss_penalty",
        ]:
            if column in selected:
                row[f"train_{column}"] = selected[column]

        holdout_base_summary = selected_candidate_fold_summary(
            holdout_base,
            selected,
            min_trades_per_fold=int(kwargs["min_trades_per_fold"]),
            max_forced_exit_rate=float(kwargs["max_forced_exit_rate"]),
            max_drawdown=float(kwargs["max_drawdown"]),
            min_adjusted_pnl_per_fold=float(kwargs["min_base_adjusted_pnl_per_fold"]),
        )
        holdout_cost_summary = selected_candidate_fold_summary(
            holdout_cost,
            selected,
            min_trades_per_fold=int(kwargs["min_trades_per_fold"]),
            max_forced_exit_rate=float(kwargs["max_forced_exit_rate"]),
            max_drawdown=float(kwargs["max_drawdown"]),
            min_adjusted_pnl_per_fold=float(kwargs["min_cost_adjusted_pnl_per_fold"]),
        )
        add_fold_summary_metrics(row, "holdout_base", holdout_base_summary)
        add_fold_summary_metrics(row, "holdout_cost", holdout_cost_summary)
        holdout_mins = [
            row["holdout_base_total_adjusted_pnl_min"],
            row["holdout_cost_total_adjusted_pnl_min"],
        ]
        row["holdout_total_adjusted_pnl_min_all"] = float(np.nanmin(holdout_mins))
        row["holdout_pass"] = bool(row["holdout_base_eligible"] and row["holdout_cost_eligible"])
        rows.append(row)

    return pd.DataFrame(rows)


def resolve_config_path(path: Path) -> Path:
    return path / "config.json" if path.is_dir() else path


def handle_model_candidate_selection_jackknife(args: argparse.Namespace) -> int:
    config_path = resolve_config_path(args.selection_config)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    base_paths = [Path(path) for path in config["base_sweeps"]]
    cost_paths = [Path(path) for path in config["cost_sweeps"]]
    base_frames = read_sweep_frames(base_paths)
    cost_frames = read_sweep_frames(cost_paths)
    summary = summarize_candidate_selection_jackknife(
        base_frames=base_frames,
        cost_frames=cost_frames,
        selection_config=config,
    )
    run_dir = make_run_dir(args.output_dir, "model_candidate_selection_jackknife")
    summary.to_csv(run_dir / "metrics.csv", index=False)
    metadata = {
        "selection_config": str(config_path),
        "base_sweeps": [str(path) for path in base_paths],
        "cost_sweeps": [str(path) for path in cost_paths],
    }
    with (run_dir / "config.json").open("w", encoding="utf-8") as handle:
        json.dump(metadata, handle, ensure_ascii=False, indent=2)
    display_columns = [
        "left_out_fold",
        "status",
        "matches_full_top",
        "side_ev_penalty_rules",
        "train_total_adjusted_pnl_min_cost",
        "train_pnl_stability_risk_all",
        "holdout_base_total_adjusted_pnl_min",
        "holdout_cost_total_adjusted_pnl_min",
        "holdout_total_adjusted_pnl_min_all",
        "holdout_pass",
    ]
    existing_display_columns = [column for column in display_columns if column in summary.columns]
    print(summary.loc[:, existing_display_columns].head(args.top_n).to_string(index=False))
    print(f"artifacts: {run_dir}")
    return 0


def handle_model_holdout_audit(args: argparse.Namespace) -> int:
    holdout_paths = parse_csv_paths(args.holdout_runs)
    holdout_frames = read_holdout_run_frames(holdout_paths)
    validation_summary = (
        pd.read_csv(args.validation_summary) if args.validation_summary is not None else None
    )
    summary = summarize_holdout_audit(
        holdout_frames=holdout_frames,
        validation_summary=validation_summary,
        min_holdout_cases=args.min_holdout_cases,
        min_trades_per_case=args.min_trades_per_case,
        max_forced_exit_rate=args.max_forced_exit_rate,
        max_drawdown=args.max_drawdown,
        min_adjusted_pnl_per_case=args.min_adjusted_pnl_per_case,
    )
    run_dir = make_run_dir(args.output_dir, "model_holdout_audit")
    summary.to_csv(run_dir / "metrics.csv", index=False)
    metadata = {
        "holdout_runs": [str(path) for path in holdout_paths],
        "expanded_holdout_runs": [str(path) for path in expand_holdout_run_paths(holdout_paths)],
        "validation_summary": str(args.validation_summary) if args.validation_summary else None,
        "min_holdout_cases": args.min_holdout_cases,
        "min_trades_per_case": args.min_trades_per_case,
        "max_forced_exit_rate": args.max_forced_exit_rate,
        "max_drawdown": args.max_drawdown,
        "min_adjusted_pnl_per_case": args.min_adjusted_pnl_per_case,
    }
    with (run_dir / "config.json").open("w", encoding="utf-8") as handle:
        json.dump(metadata, handle, ensure_ascii=False, indent=2)
    display_columns = [
        "policy",
        "entry_threshold",
        "short_entry_threshold_offset",
        "side_margin",
        "min_entry_rank",
        "side_ev_penalty_rules",
        "eligible",
        "holdout_case_count",
        "holdout_month_count",
        "holdout_case_ok_count",
        "holdout_total_adjusted_pnl_min",
        "holdout_total_adjusted_pnl_sum",
        "holdout_positive_case_rate",
        "holdout_max_drawdown_max",
        "holdout_eligible",
        "audit_eligible",
    ]
    existing_display_columns = [column for column in display_columns if column in summary.columns]
    print(summary.loc[:, existing_display_columns].head(args.top_n).to_string(index=False))
    print(f"artifacts: {run_dir}")
    return 0


def handle_model_trade_exposure(args: argparse.Namespace) -> int:
    run_paths = parse_csv_paths(args.runs)
    expanded_run_paths = expand_model_trade_exposure_run_paths(run_paths)
    exposure_frames = read_model_trade_exposure_frames(
        run_paths,
        args.long_column,
        args.short_column,
    )
    enriched = pd.concat(exposure_frames, ignore_index=True) if exposure_frames else pd.DataFrame()

    run_dir = make_run_dir(args.output_dir, args.label)
    enriched.to_csv(run_dir / "enriched_trades.csv", index=False)
    if enriched.empty:
        metadata = {
            "runs": [str(path) for path in run_paths],
            "expanded_runs": [str(path) for path in expanded_run_paths],
            "long_column": args.long_column,
            "short_column": args.short_column,
            "label": args.label,
            "top_n": args.top_n,
        }
        with (run_dir / "config.json").open("w", encoding="utf-8") as handle:
            json.dump(metadata, handle, ensure_ascii=False, indent=2)
        print("no trades to summarize")
        print(f"artifacts: {run_dir}")
        return 0

    group_specs = {
        "month": ["month"],
        "direction": ["month", "direction"],
        "combined_regime": ["month", "combined_regime"],
        "direction_combined_regime": ["month", "direction", "combined_regime"],
        "session_regime": ["month", "session_regime"],
        "direction_session_regime": ["month", "direction", "session_regime"],
        "volatility_regime": ["month", "volatility_regime"],
        "direction_volatility_regime": ["month", "direction", "volatility_regime"],
    }
    summaries: dict[str, pd.DataFrame] = {}
    for name, group_columns in group_specs.items():
        summary = trade_exposure_group_summary(enriched, group_columns)
        summaries[name] = summary
        summary.to_csv(run_dir / f"group_by_{name}.csv", index=False)

    metadata = {
        "runs": [str(path) for path in run_paths],
        "expanded_runs": [str(path) for path in expanded_run_paths],
        "long_column": args.long_column,
        "short_column": args.short_column,
        "label": args.label,
        "top_n": args.top_n,
    }
    with (run_dir / "config.json").open("w", encoding="utf-8") as handle:
        json.dump(metadata, handle, ensure_ascii=False, indent=2)

    month_summary = summaries["month"]
    display_columns = [
        "month",
        "trade_count",
        "total_adjusted_pnl",
        "avg_adjusted_pnl",
        "win_rate",
        "forced_exit_count",
        "direction_error_rate",
        "no_edge_rate",
        "ev_overestimate_vs_realized_mean",
    ]
    print("month exposure:")
    print(month_summary.loc[:, display_columns].to_string(index=False))
    print("worst direction x combined regime:")
    worst = summaries["direction_combined_regime"].groupby("month", group_keys=False).head(args.top_n)
    worst_columns = [
        "month",
        "direction",
        "combined_regime",
        "trade_count",
        "total_adjusted_pnl",
        "avg_adjusted_pnl",
        "win_rate",
        "trade_share",
    ]
    print(worst.loc[:, worst_columns].to_string(index=False))
    print(f"artifacts: {run_dir}")
    return 0


def handle_model_trade_exposure_diagnostics(args: argparse.Namespace) -> int:
    run_paths = parse_csv_paths(args.runs) if args.runs else []
    trade_paths = parse_csv_paths(args.trades) if args.trades else []
    if not run_paths and not trade_paths:
        raise ValueError("one of --runs or --trades is required")

    frames: list[pd.DataFrame] = []
    expanded_run_paths: list[Path] = []
    if run_paths:
        expanded_run_paths = expand_model_trade_exposure_run_paths(run_paths)
        frames.extend(
            read_model_trade_exposure_frames(
                run_paths,
                args.long_column,
                args.short_column,
            )
        )
    for path in trade_paths:
        frame = pd.read_csv(path)
        frames.append(frame)

    trades = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    diagnostics = add_trade_exposure_diagnostic_buckets(trades)

    run_dir = make_run_dir(args.output_dir, args.label)
    diagnostics.to_csv(run_dir / "diagnostic_trades.csv", index=False)

    group_specs = {
        "context": ["month", "direction", "combined_regime", "session_regime"],
        "context_overall": ["direction", "combined_regime", "session_regime"],
        "context_side_gap": [
            "month",
            "direction",
            "combined_regime",
            "session_regime",
            "pred_side_gap_bucket",
        ],
        "context_side_confidence": [
            "month",
            "direction",
            "combined_regime",
            "session_regime",
            "pred_side_confidence_bucket",
        ],
        "context_side_confidence_gap": [
            "month",
            "direction",
            "combined_regime",
            "session_regime",
            "pred_side_confidence_gap_bucket",
        ],
        "context_pred_holding": [
            "month",
            "direction",
            "combined_regime",
            "session_regime",
            "pred_holding_bucket",
        ],
        "context_holding_ratio": [
            "month",
            "direction",
            "combined_regime",
            "session_regime",
            "holding_ratio_bucket",
        ],
        "context_profit_barrier": [
            "month",
            "direction",
            "combined_regime",
            "session_regime",
            "profit_barrier_outcome",
        ],
        "context_ev_overestimate": [
            "month",
            "direction",
            "combined_regime",
            "session_regime",
            "ev_overestimate_bucket",
        ],
        "context_exit_regret": [
            "month",
            "direction",
            "combined_regime",
            "session_regime",
            "exit_regret_bucket",
        ],
        "diagnostic_combo": [
            "month",
            "direction",
            "combined_regime",
            "session_regime",
            "pred_side_gap_bucket",
            "pred_side_confidence_bucket",
            "pred_holding_bucket",
            "profit_barrier_outcome",
        ],
        "diagnostic_combo_overall": [
            "direction",
            "combined_regime",
            "session_regime",
            "pred_side_gap_bucket",
            "pred_side_confidence_bucket",
            "pred_holding_bucket",
            "profit_barrier_outcome",
        ],
    }
    summaries: dict[str, pd.DataFrame] = {}
    for name, group_columns in group_specs.items():
        missing = [column for column in group_columns if column not in diagnostics.columns]
        if missing:
            continue
        summary = trade_exposure_diagnostic_summary(
            diagnostics,
            group_columns,
            large_loss_threshold=args.large_loss_threshold,
        )
        summaries[name] = summary
        summary.to_csv(run_dir / f"group_by_{name}.csv", index=False)

    metadata = {
        "runs": [str(path) for path in run_paths],
        "expanded_runs": [str(path) for path in expanded_run_paths],
        "trades": [str(path) for path in trade_paths],
        "long_column": args.long_column,
        "short_column": args.short_column,
        "label": args.label,
        "large_loss_threshold": args.large_loss_threshold,
        "top_n": args.top_n,
        "row_count": int(len(diagnostics)),
    }
    with (run_dir / "config.json").open("w", encoding="utf-8") as handle:
        json.dump(metadata, handle, ensure_ascii=False, indent=2)

    display_columns = [
        "month",
        "direction",
        "combined_regime",
        "session_regime",
        "trade_count",
        "total_adjusted_pnl",
        "avg_adjusted_pnl",
        "ev_overestimate_vs_realized_mean",
        "exit_regret_mean",
        "pred_side_gap_mean",
        "pred_taken_side_confidence_mean",
        "predicted_profit_barrier_hit_rate",
        "actual_profit_barrier_hit_rate",
    ]
    if "context" in summaries:
        print("worst monthly context diagnostics:")
        existing_columns = [column for column in display_columns if column in summaries["context"].columns]
        print(summaries["context"].loc[:, existing_columns].head(args.top_n).to_string(index=False))
    if "context_overall" in summaries:
        print("worst overall context diagnostics:")
        existing_columns = [
            column
            for column in display_columns
            if column != "month" and column in summaries["context_overall"].columns
        ]
        print(
            summaries["context_overall"]
            .loc[:, existing_columns]
            .head(args.top_n)
            .to_string(index=False)
        )
    if "diagnostic_combo" in summaries:
        print("worst monthly diagnostic combos:")
        combo_columns = [
            "month",
            "direction",
            "combined_regime",
            "session_regime",
            "pred_side_gap_bucket",
            "pred_side_confidence_bucket",
            "pred_holding_bucket",
            "profit_barrier_outcome",
            "trade_count",
            "total_adjusted_pnl",
            "ev_overestimate_vs_realized_mean",
        ]
        existing_columns = [
            column for column in combo_columns if column in summaries["diagnostic_combo"].columns
        ]
        print(
            summaries["diagnostic_combo"]
            .loc[:, existing_columns]
            .head(args.top_n)
            .to_string(index=False)
        )
    if "diagnostic_combo_overall" in summaries:
        print("worst overall diagnostic combos:")
        combo_columns = [
            "direction",
            "combined_regime",
            "session_regime",
            "pred_side_gap_bucket",
            "pred_side_confidence_bucket",
            "pred_holding_bucket",
            "profit_barrier_outcome",
            "trade_count",
            "total_adjusted_pnl",
            "ev_overestimate_vs_realized_mean",
        ]
        existing_columns = [
            column
            for column in combo_columns
            if column in summaries["diagnostic_combo_overall"].columns
        ]
        print(
            summaries["diagnostic_combo_overall"]
            .loc[:, existing_columns]
            .head(args.top_n)
            .to_string(index=False)
        )
    print(f"artifacts: {run_dir}")
    return 0


def handle_model_trade_context_walkforward_stress(args: argparse.Namespace) -> int:
    run_paths = parse_csv_paths(args.runs)
    expanded_run_paths = expand_model_trade_exposure_run_paths(run_paths)
    group_columns = parse_csv_strings(args.group_columns)
    if not group_columns:
        raise ValueError("at least one group column is required")
    exposure_frames = read_model_trade_exposure_frames(
        run_paths,
        args.long_column,
        args.short_column,
    )
    selected_trades = pd.concat(exposure_frames, ignore_index=True) if exposure_frames else pd.DataFrame()
    if selected_trades.empty:
        raise ValueError("selected trades are empty")

    annotated, profile_drift, month_summary, outcomes = (
        selected_trade_walkforward_context_stress_targets(
            selected_trades,
            group_columns=group_columns,
            target_column=args.target_column,
            raw_prediction_column=args.raw_prediction_column,
            downside_threshold=args.downside_threshold,
            large_downside_threshold=args.large_downside_threshold,
            holdout_month_count=args.holdout_month_count,
            min_validation_months=args.min_validation_months,
            min_validation_support=args.min_validation_support,
            min_holdout_support=args.min_holdout_support,
            min_prior_support=args.min_prior_support,
        )
    )

    run_dir = make_run_dir(args.output_dir, args.label)
    selected_trades.to_csv(run_dir / "selected_trades.csv", index=False)
    annotated.to_csv(run_dir / "walkforward_selected_trades.csv", index=False)
    walkforward_stress_flag = annotated["walkforward_context_stress_flag"].mask(
        annotated["walkforward_context_stress_flag"].isna(),
        False,
    ).astype(bool)
    stressed = annotated.loc[walkforward_stress_flag]
    if not stressed.empty:
        stressed.to_csv(run_dir / "walkforward_context_stressed_trades.csv", index=False)
    if not profile_drift.empty:
        profile_drift.to_csv(run_dir / "walkforward_profile_drift.csv", index=False)
    month_summary.to_csv(run_dir / "walkforward_month_summary.csv", index=False)
    outcomes.to_csv(run_dir / "walkforward_context_outcomes.csv", index=False)

    target = pd.to_numeric(annotated[args.target_column], errors="coerce")
    adjusted = pd.to_numeric(
        annotated["target_walkforward_context_stress_adjusted"],
        errors="coerce",
    )
    floor = pd.to_numeric(
        annotated["target_walkforward_context_holdout_mean_floor"],
        errors="coerce",
    )
    summary = {
        "runs": [str(path) for path in run_paths],
        "expanded_runs": [str(path) for path in expanded_run_paths],
        "long_column": args.long_column,
        "short_column": args.short_column,
        "target_column": args.target_column,
        "raw_prediction_column": args.raw_prediction_column,
        "group_columns": group_columns,
        "downside_threshold": args.downside_threshold,
        "large_downside_threshold": args.large_downside_threshold,
        "holdout_month_count": args.holdout_month_count,
        "min_validation_months": args.min_validation_months,
        "min_validation_support": args.min_validation_support,
        "min_holdout_support": args.min_holdout_support,
        "min_prior_support": args.min_prior_support,
        "row_count": int(len(annotated)),
        "month_count": int(annotated["dataset_month"].astype(str).str.slice(0, 7).nunique()),
        "context_outcome_count": int(len(outcomes)),
        "walkforward_profiled_month_count": int(
            month_summary["profile_status"].eq("profiled").sum()
            if "profile_status" in month_summary.columns
            else 0
        ),
        "walkforward_stress_flag_count": int(walkforward_stress_flag.sum()),
        "walkforward_stress_penalty_sum": float(
            pd.to_numeric(
                annotated["walkforward_context_stress_penalty"],
                errors="coerce",
            )
            .fillna(0.0)
            .sum()
        ),
        "target_mean": float(target.mean()),
        "target_walkforward_context_stress_adjusted_mean": float(adjusted.mean()),
        "target_walkforward_context_holdout_mean_floor_mean": float(floor.mean()),
        "target_walkforward_prior_context_mean_floor_mean": float(
            pd.to_numeric(
                annotated["target_walkforward_prior_context_mean_floor"],
                errors="coerce",
            ).mean()
        ),
        "walkforward_prior_context_loss_flag_count": int(
            annotated["walkforward_prior_context_loss_flag"].mask(
                annotated["walkforward_prior_context_loss_flag"].isna(),
                False,
            ).astype(bool).sum()
        ),
    }
    with (run_dir / "summary.json").open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2, default=json_default)

    print("selected trade walk-forward context stress summary:")
    for key, value in summary.items():
        if not isinstance(value, list):
            print(f"{key}: {value}")
    display_columns = [
        "target_month",
        *group_columns,
        "target_support",
        "target_adjusted_pnl_sum",
        "target_adjusted_pnl_mean",
        "target_downside_rate",
        "walkforward_stress_flag_count",
        "walkforward_context_validation_support",
        "walkforward_context_holdout_support",
        "walkforward_context_validation_target_mean",
        "walkforward_context_holdout_target_mean",
        "walkforward_context_validation_positive_holdout_negative_mean",
        "walkforward_prior_context_support",
        "walkforward_prior_context_target_mean",
        "walkforward_prior_context_loss_flag",
    ]
    existing_display_columns = [column for column in display_columns if column in outcomes.columns]
    print("worst selected trade contexts:")
    print(outcomes.loc[:, existing_display_columns].head(args.top_n).to_string(index=False))
    print(f"artifacts: {run_dir}")
    return 0


def handle_stateful_examples_drift(args: argparse.Namespace) -> int:
    validation_paths = parse_csv_paths(args.validation_examples)
    holdout_paths = parse_csv_paths(args.holdout_examples)
    group_columns = parse_csv_strings(args.group_columns)
    if not group_columns:
        raise ValueError("at least one group column is required")
    validation = read_stateful_example_frames(validation_paths, "validation")
    holdout = read_stateful_example_frames(holdout_paths, "holdout")
    examples = pd.concat([validation, holdout], ignore_index=True)
    if examples.empty:
        raise ValueError("stateful examples are empty")

    split_metrics = stateful_examples_metric_summary(
        examples,
        group_columns=group_columns,
        target_column=args.target_column,
        raw_prediction_column=args.raw_prediction_column,
        downside_threshold=args.downside_threshold,
        large_downside_threshold=args.large_downside_threshold,
    )
    month_metrics = stateful_examples_month_group_metrics(
        examples,
        group_columns=group_columns,
        target_column=args.target_column,
        raw_prediction_column=args.raw_prediction_column,
        downside_threshold=args.downside_threshold,
        large_downside_threshold=args.large_downside_threshold,
    )
    drift = stateful_examples_drift_metrics(split_metrics, group_columns=group_columns)
    examples_with_stress = add_stateful_examples_context_stress_columns(
        examples,
        drift,
        group_columns=group_columns,
        target_column=args.target_column,
    )

    run_dir = make_run_dir(args.output_dir, args.label)
    examples_with_stress.to_csv(run_dir / "combined_stateful_examples.csv", index=False)
    context_stress_flag = examples_with_stress["context_stress_flag"].mask(
        examples_with_stress["context_stress_flag"].isna(),
        False,
    ).astype(bool)
    stressed_examples = examples_with_stress.loc[
        context_stress_flag
    ]
    if not stressed_examples.empty:
        stressed_examples.to_csv(run_dir / "context_stressed_examples.csv", index=False)
    split_metrics.to_csv(run_dir / "split_group_metrics.csv", index=False)
    if not month_metrics.empty:
        month_metrics.to_csv(run_dir / "month_group_metrics.csv", index=False)
    drift.to_csv(run_dir / "group_drift.csv", index=False)
    summary = {
        "validation_examples": [str(path) for path in validation_paths],
        "expanded_validation_examples": [
            str(path) for path in expand_stateful_example_paths(validation_paths)
        ],
        "holdout_examples": [str(path) for path in holdout_paths],
        "expanded_holdout_examples": [
            str(path) for path in expand_stateful_example_paths(holdout_paths)
        ],
        "target_column": args.target_column,
        "raw_prediction_column": args.raw_prediction_column,
        "group_columns": group_columns,
        "downside_threshold": args.downside_threshold,
        "large_downside_threshold": args.large_downside_threshold,
        "row_count": int(len(examples)),
        "validation_row_count": int(len(validation)),
        "holdout_row_count": int(len(holdout)),
        "group_count": int(len(drift)),
        "validation_positive_holdout_negative_mean_count": int(
            drift.get(
                "validation_positive_holdout_negative_mean",
                pd.Series(False, index=drift.index),
            ).sum()
        ),
        "validation_positive_holdout_negative_sum_count": int(
            drift.get(
                "validation_positive_holdout_negative_sum",
                pd.Series(False, index=drift.index),
            ).sum()
        ),
        "context_stress_flag_count": int(context_stress_flag.sum()),
        "context_stress_penalty_sum": float(
            pd.to_numeric(
                examples_with_stress["context_stress_penalty"],
                errors="coerce",
            )
            .fillna(0.0)
            .sum()
        ),
        "context_stress_penalty_mean": float(
            pd.to_numeric(
                examples_with_stress["context_stress_penalty"],
                errors="coerce",
            )
            .fillna(0.0)
            .mean()
        ),
        "target_mean": float(
            pd.to_numeric(examples_with_stress[args.target_column], errors="coerce").mean()
        ),
        "target_context_stress_adjusted_mean": float(
            pd.to_numeric(
                examples_with_stress["target_context_stress_adjusted"],
                errors="coerce",
            ).mean()
        ),
    }
    with (run_dir / "summary.json").open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2, default=json_default)

    print("stateful examples drift summary:")
    for key, value in summary.items():
        if not isinstance(value, list):
            print(f"{key}: {value}")
    display_columns = [
        *group_columns,
        "validation_support",
        "holdout_support",
        "validation_target_sum",
        "holdout_target_sum",
        "target_sum_holdout_minus_validation",
        "validation_target_mean",
        "holdout_target_mean",
        "target_mean_holdout_minus_validation",
        "validation_downside_rate",
        "holdout_downside_rate",
        "downside_rate_holdout_minus_validation",
        "validation_raw_overestimate_mean",
        "holdout_raw_overestimate_mean",
        "validation_positive_holdout_negative_mean",
        "validation_positive_holdout_negative_sum",
    ]
    existing_display_columns = [column for column in display_columns if column in drift.columns]
    print("worst stateful example drift:")
    print(drift.loc[:, existing_display_columns].head(args.top_n).to_string(index=False))
    print(f"artifacts: {run_dir}")
    return 0


def handle_stateful_examples_walkforward_stress(args: argparse.Namespace) -> int:
    example_paths = parse_csv_paths(args.examples)
    group_columns = parse_csv_strings(args.group_columns)
    if not group_columns:
        raise ValueError("at least one group column is required")
    examples = read_stateful_example_frames(example_paths, "examples")
    annotated, profile_drift, month_summary = stateful_examples_walkforward_stress_targets(
        examples,
        group_columns=group_columns,
        target_column=args.target_column,
        raw_prediction_column=args.raw_prediction_column,
        downside_threshold=args.downside_threshold,
        large_downside_threshold=args.large_downside_threshold,
        holdout_month_count=args.holdout_month_count,
        min_validation_months=args.min_validation_months,
        min_validation_support=args.min_validation_support,
        min_holdout_support=args.min_holdout_support,
        min_prior_support=args.min_prior_support,
    )

    run_dir = make_run_dir(args.output_dir, args.label)
    annotated.to_csv(run_dir / "walkforward_stateful_examples.csv", index=False)
    walkforward_stress_flag = annotated["walkforward_context_stress_flag"].mask(
        annotated["walkforward_context_stress_flag"].isna(),
        False,
    ).astype(bool)
    stressed = annotated.loc[walkforward_stress_flag]
    if not stressed.empty:
        stressed.to_csv(run_dir / "walkforward_context_stressed_examples.csv", index=False)
    if not profile_drift.empty:
        profile_drift.to_csv(run_dir / "walkforward_profile_drift.csv", index=False)
    month_summary.to_csv(run_dir / "walkforward_month_summary.csv", index=False)

    summary = {
        "examples": [str(path) for path in example_paths],
        "expanded_examples": [
            str(path) for path in expand_stateful_example_paths(example_paths)
        ],
        "target_column": args.target_column,
        "raw_prediction_column": args.raw_prediction_column,
        "group_columns": group_columns,
        "downside_threshold": args.downside_threshold,
        "large_downside_threshold": args.large_downside_threshold,
        "holdout_month_count": args.holdout_month_count,
        "min_validation_months": args.min_validation_months,
        "min_validation_support": args.min_validation_support,
        "min_holdout_support": args.min_holdout_support,
        "min_prior_support": args.min_prior_support,
        "row_count": int(len(annotated)),
        "month_count": int(month_summary["target_month"].nunique()),
        "profiled_month_count": int(month_summary["profile_status"].eq("profiled").sum()),
        "stress_flag_count": int(walkforward_stress_flag.sum()),
        "stress_penalty_sum": float(
            pd.to_numeric(
                annotated["walkforward_context_stress_penalty"],
                errors="coerce",
            )
            .fillna(0.0)
            .sum()
        ),
        "stress_penalty_mean": float(
            pd.to_numeric(
                annotated["walkforward_context_stress_penalty"],
                errors="coerce",
            )
            .fillna(0.0)
            .mean()
        ),
        "target_mean": float(
            pd.to_numeric(annotated[args.target_column], errors="coerce").mean()
        ),
        "target_walkforward_context_stress_adjusted_mean": float(
            pd.to_numeric(
                annotated["target_walkforward_context_stress_adjusted"],
                errors="coerce",
            ).mean()
        ),
        "target_walkforward_prior_context_mean_floor_mean": float(
            pd.to_numeric(
                annotated["target_walkforward_prior_context_mean_floor"],
                errors="coerce",
            ).mean()
        ),
        "walkforward_prior_context_loss_flag_count": int(
            annotated["walkforward_prior_context_loss_flag"].mask(
                annotated["walkforward_prior_context_loss_flag"].isna(),
                False,
            ).astype(bool).sum()
        ),
    }
    with (run_dir / "summary.json").open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2, default=json_default)

    print("stateful examples walk-forward stress summary:")
    for key, value in summary.items():
        if not isinstance(value, list):
            print(f"{key}: {value}")
    display_columns = [
        "target_month",
        "profile_status",
        "row_count",
        "profile_validation_months",
        "profile_holdout_months",
        "stress_flag_count",
        "stress_penalty_mean",
        "target_mean",
        "target_walkforward_context_stress_adjusted_mean",
    ]
    print(month_summary.loc[:, display_columns].tail(args.top_n).to_string(index=False))
    print(f"artifacts: {run_dir}")
    return 0


def handle_model_trade_delta(args: argparse.Namespace) -> int:
    base_paths = parse_csv_paths(args.base_runs)
    candidate_paths = parse_csv_paths(args.candidate_runs)
    delta_frames = read_model_trade_delta_frames(
        base_paths,
        candidate_paths,
        args.gate_long_quality_column,
        args.gate_short_quality_column,
    )
    delta = pd.concat(delta_frames, ignore_index=True) if delta_frames else pd.DataFrame()
    delta, blocking_pairs = add_trade_delta_blocking_diagnostics(delta)
    stateful_examples = stateful_candidate_examples_from_delta(
        delta,
        args.stateful_example_target,
    )

    run_dir = make_run_dir(args.output_dir, args.label)
    delta.to_csv(run_dir / "trade_delta_rows.csv", index=False)
    blocking_pairs.to_csv(run_dir / "blocking_pairs.csv", index=False)
    stateful_examples.to_csv(run_dir / "stateful_candidate_examples.csv", index=False)
    group_specs = {
        "month": ["month"],
        "month_status": ["month", "delta_status"],
        "month_status_direction": ["month", "delta_status", "direction"],
        "month_status_direction_combined_regime": [
            "month",
            "delta_status",
            "direction",
            "combined_regime",
        ],
        "month_status_direction_session_regime": [
            "month",
            "delta_status",
            "direction",
            "session_regime",
        ],
        "month_status_quality_bucket": [
            "month",
            "delta_status",
            "gate_trade_quality_taken_bucket",
        ],
    }
    summaries: dict[str, pd.DataFrame] = {}
    for name, group_columns in group_specs.items():
        existing_group_columns = [column for column in group_columns if column in delta.columns]
        if len(existing_group_columns) != len(group_columns):
            continue
        summary = trade_delta_group_summary(delta, group_columns)
        summaries[name] = summary
        summary.to_csv(run_dir / f"group_by_{name}.csv", index=False)
    blocking_group_specs = {
        "blocking_candidate_month_status_direction": ["month", "delta_status", "direction"],
        "blocking_candidate_month_status_direction_combined_regime": [
            "month",
            "delta_status",
            "direction",
            "combined_regime",
        ],
        "blocking_candidate_month_status_direction_session_regime": [
            "month",
            "delta_status",
            "direction",
            "session_regime",
        ],
    }
    blocking_summaries: dict[str, pd.DataFrame] = {}
    for name, group_columns in blocking_group_specs.items():
        existing_group_columns = [column for column in group_columns if column in delta.columns]
        if len(existing_group_columns) != len(group_columns):
            continue
        summary = trade_delta_blocking_group_summary(delta, group_columns)
        blocking_summaries[name] = summary
        summary.to_csv(run_dir / f"group_by_{name}.csv", index=False)

    metadata = {
        "base_runs": [str(path) for path in base_paths],
        "candidate_runs": [str(path) for path in candidate_paths],
        "gate_long_quality_column": args.gate_long_quality_column,
        "gate_short_quality_column": args.gate_short_quality_column,
        "stateful_example_target": args.stateful_example_target,
        "label": args.label,
        "top_n": args.top_n,
    }
    with (run_dir / "config.json").open("w", encoding="utf-8") as handle:
        json.dump(metadata, handle, ensure_ascii=False, indent=2, default=json_default)

    if delta.empty:
        print("no trade deltas to summarize")
        print(f"artifacts: {run_dir}")
        return 0

    month_summary = summaries["month"]
    display_columns = [
        "month",
        "base_trade_count",
        "candidate_trade_count",
        "base_adjusted_pnl",
        "candidate_adjusted_pnl",
        "pnl_delta",
        "removed_positive_pnl",
        "removed_negative_pnl",
        "added_positive_pnl",
        "added_negative_pnl",
    ]
    print("month delta:")
    print(month_summary.loc[:, display_columns].to_string(index=False))
    print("worst status x direction x combined regime:")
    worst = summaries["month_status_direction_combined_regime"].groupby("month", group_keys=False).head(
        args.top_n
    )
    worst_columns = [
        "month",
        "delta_status",
        "direction",
        "combined_regime",
        "row_count",
        "base_adjusted_pnl",
        "candidate_adjusted_pnl",
        "pnl_delta",
        "gate_trade_quality_taken_mean",
    ]
    existing_worst_columns = [column for column in worst_columns if column in worst.columns]
    print(worst.loc[:, existing_worst_columns].to_string(index=False))
    if "blocking_candidate_month_status_direction_combined_regime" in blocking_summaries:
        blocking = blocking_summaries["blocking_candidate_month_status_direction_combined_regime"]
        if not blocking.empty:
            print("worst candidate blocking stateful value:")
            blocking_worst = blocking.groupby("month", group_keys=False).head(args.top_n)
            blocking_columns = [
                "month",
                "delta_status",
                "direction",
                "combined_regime",
                "candidate_trade_count",
                "candidate_adjusted_pnl",
                "blocked_base_count",
                "blocked_base_adjusted_pnl",
                "blocked_base_positive_pnl",
                "candidate_stateful_net_adjusted_pnl",
                "gate_trade_quality_taken_mean",
            ]
            existing_blocking_columns = [
                column for column in blocking_columns if column in blocking_worst.columns
            ]
            print(blocking_worst.loc[:, existing_blocking_columns].to_string(index=False))
    if not stateful_examples.empty:
        example_summary = stateful_examples.groupby("month", dropna=False).agg(
            candidate_count=("target", "size"),
            target_mean=("target", "mean"),
            stateful_entry_value_mean=("stateful_entry_value", "mean"),
            stateful_positive_cost_value_mean=("stateful_positive_cost_value", "mean"),
            blocking_cost_sum=("blocking_cost", "sum"),
            positive_blocking_cost_sum=("positive_blocking_cost", "sum"),
        ).reset_index()
        print("stateful candidate examples:")
        print(example_summary.to_string(index=False))
    print(f"artifacts: {run_dir}")
    return 0


def expand_model_trade_delta_run_paths(paths: list[Path]) -> list[Path]:
    expanded: list[Path] = []
    for path in paths:
        if path.is_dir() and not (path / "group_by_month.csv").exists():
            children = [
                child
                for child in sorted(path.iterdir())
                if child.is_dir()
                and (child / "group_by_month.csv").exists()
                and (child / "group_by_month_status.csv").exists()
            ]
            if children:
                expanded.extend(children)
                continue
        expanded.append(path)
    return expanded


def numeric_column_sum(frame: pd.DataFrame, column: str) -> float:
    if column not in frame.columns:
        return 0.0
    return float(pd.to_numeric(frame[column], errors="coerce").fillna(0.0).sum())


def read_model_trade_delta_preflight_case(path: Path, split: str) -> dict[str, object]:
    month_path = path / "group_by_month.csv"
    status_path = path / "group_by_month_status.csv"
    stateful_path = path / "stateful_candidate_examples.csv"
    if not month_path.exists():
        raise FileNotFoundError(f"group_by_month.csv not found: {month_path}")

    month = pd.read_csv(month_path)
    if month.empty:
        raise ValueError(f"delta run has no monthly rows: {path}")

    row: dict[str, object] = {
        "split": split,
        "case_label": path.name,
        "delta_run": str(path),
        "month_count": int(month["month"].nunique()) if "month" in month.columns else len(month),
        "base_trade_count_sum": numeric_column_sum(month, "base_trade_count"),
        "candidate_trade_count_sum": numeric_column_sum(month, "candidate_trade_count"),
        "base_adjusted_pnl_sum": numeric_column_sum(month, "base_adjusted_pnl"),
        "candidate_adjusted_pnl_sum": numeric_column_sum(month, "candidate_adjusted_pnl"),
        "pnl_delta_sum": numeric_column_sum(month, "pnl_delta"),
        "removed_positive_pnl_sum": numeric_column_sum(month, "removed_positive_pnl"),
        "removed_negative_pnl_sum": numeric_column_sum(month, "removed_negative_pnl"),
        "added_positive_pnl_sum": numeric_column_sum(month, "added_positive_pnl"),
        "added_negative_pnl_sum": numeric_column_sum(month, "added_negative_pnl"),
    }
    pnl_delta = pd.to_numeric(month.get("pnl_delta", pd.Series(dtype=float)), errors="coerce")
    if pnl_delta.empty:
        row["pnl_delta_min_month"] = np.nan
        row["pnl_delta_negative_month_count"] = 0
    else:
        row["pnl_delta_min_month"] = float(pnl_delta.min())
        row["pnl_delta_negative_month_count"] = int((pnl_delta < 0).sum())

    if status_path.exists():
        status = pd.read_csv(status_path)
        if "delta_status" in status.columns:
            for delta_status in ["common", "only_base", "only_candidate"]:
                subset = status.loc[status["delta_status"].astype(str).eq(delta_status)]
                prefix = delta_status
                row[f"{prefix}_pnl_delta_sum"] = numeric_column_sum(subset, "pnl_delta")
                row[f"{prefix}_base_adjusted_pnl_sum"] = numeric_column_sum(
                    subset,
                    "base_adjusted_pnl",
                )
                row[f"{prefix}_candidate_adjusted_pnl_sum"] = numeric_column_sum(
                    subset,
                    "candidate_adjusted_pnl",
                )
                row[f"{prefix}_row_count_sum"] = numeric_column_sum(subset, "row_count")

    if stateful_path.exists():
        stateful = pd.read_csv(stateful_path)
        if not stateful.empty and "target" in stateful.columns:
            stateful["target"] = pd.to_numeric(stateful["target"], errors="coerce")
            row["stateful_target_mean"] = float(stateful["target"].mean())
            row["stateful_target_sum"] = float(stateful["target"].sum())
            if "month" in stateful.columns:
                stateful_by_month = stateful.groupby("month", dropna=False)["target"].mean()
                row["stateful_target_mean_min_month"] = float(stateful_by_month.min())
                row["stateful_target_negative_month_count"] = int((stateful_by_month < 0).sum())
            else:
                row["stateful_target_mean_min_month"] = row["stateful_target_mean"]
                row["stateful_target_negative_month_count"] = int(row["stateful_target_mean"] < 0)
        if not stateful.empty and "blocking_cost" in stateful.columns:
            row["blocking_cost_sum"] = numeric_column_sum(stateful, "blocking_cost")
        if not stateful.empty and "replacement_regret" in stateful.columns:
            row["replacement_regret_mean"] = float(
                pd.to_numeric(stateful["replacement_regret"], errors="coerce").mean()
            )
    return row


def summarize_model_trade_delta_preflight(
    validation_paths: list[Path],
    holdout_paths: list[Path],
    *,
    min_validation_cases: int = 1,
    min_holdout_cases: int = 1,
    min_validation_pnl_delta: float = 0.0,
    min_holdout_pnl_delta: float = 0.0,
    min_validation_month_pnl_delta: float = -float("inf"),
    min_holdout_month_pnl_delta: float = 0.0,
    min_validation_stateful_target_mean: float = -float("inf"),
    min_holdout_stateful_target_mean: float = 0.0,
) -> tuple[pd.DataFrame, dict[str, object]]:
    expanded_validation_paths = expand_model_trade_delta_run_paths(validation_paths)
    expanded_holdout_paths = expand_model_trade_delta_run_paths(holdout_paths)
    rows = [
        read_model_trade_delta_preflight_case(path, "validation")
        for path in expanded_validation_paths
    ]
    rows.extend(
        read_model_trade_delta_preflight_case(path, "holdout")
        for path in expanded_holdout_paths
    )
    cases = pd.DataFrame(rows)
    if cases.empty:
        raise ValueError("at least one delta run is required")

    optional_metric_columns = [
        "stateful_target_mean",
        "stateful_target_sum",
        "stateful_target_mean_min_month",
        "stateful_target_negative_month_count",
        "blocking_cost_sum",
        "replacement_regret_mean",
    ]
    for column in optional_metric_columns:
        if column not in cases.columns:
            cases[column] = np.nan

    def threshold_ok(value: object, threshold: float) -> bool:
        if pd.isna(value):
            return not np.isfinite(threshold)
        return bool(float(value) >= threshold)

    def case_pass(row: pd.Series) -> bool:
        is_validation = str(row["split"]) == "validation"
        min_pnl_delta = min_validation_pnl_delta if is_validation else min_holdout_pnl_delta
        min_month_pnl_delta = (
            min_validation_month_pnl_delta if is_validation else min_holdout_month_pnl_delta
        )
        min_stateful_target_mean = (
            min_validation_stateful_target_mean
            if is_validation
            else min_holdout_stateful_target_mean
        )
        return bool(
            threshold_ok(row["pnl_delta_sum"], min_pnl_delta)
            and threshold_ok(row["pnl_delta_min_month"], min_month_pnl_delta)
            and threshold_ok(
                row["stateful_target_mean_min_month"],
                min_stateful_target_mean,
            )
        )

    cases["case_pass"] = cases.apply(case_pass, axis=1)
    cases["pnl_delta_sum_ok"] = cases.apply(
        lambda row: threshold_ok(
            row["pnl_delta_sum"],
            min_validation_pnl_delta
            if row["split"] == "validation"
            else min_holdout_pnl_delta,
        ),
        axis=1,
    )
    cases["pnl_delta_min_month_ok"] = cases.apply(
        lambda row: threshold_ok(
            row["pnl_delta_min_month"],
            min_validation_month_pnl_delta
            if row["split"] == "validation"
            else min_holdout_month_pnl_delta,
        ),
        axis=1,
    )
    cases["stateful_target_mean_min_month_ok"] = cases.apply(
        lambda row: threshold_ok(
            row["stateful_target_mean_min_month"],
            min_validation_stateful_target_mean
            if row["split"] == "validation"
            else min_holdout_stateful_target_mean,
        ),
        axis=1,
    )

    validation = cases.loc[cases["split"].eq("validation")]
    holdout = cases.loc[cases["split"].eq("holdout")]
    validation_case_count = int(len(validation))
    holdout_case_count = int(len(holdout))
    validation_case_pass_count = int(validation["case_pass"].sum())
    holdout_case_pass_count = int(holdout["case_pass"].sum())
    validation_all_pass = (
        validation_case_count >= min_validation_cases
        and validation_case_pass_count == validation_case_count
    )
    holdout_all_pass = (
        holdout_case_count >= min_holdout_cases
        and holdout_case_pass_count == holdout_case_count
    )
    summary = {
        "validation_case_count": validation_case_count,
        "validation_case_pass_count": validation_case_pass_count,
        "holdout_case_count": holdout_case_count,
        "holdout_case_pass_count": holdout_case_pass_count,
        "validation_all_pass": validation_all_pass,
        "holdout_all_pass": holdout_all_pass,
        "preflight_pass": validation_all_pass and holdout_all_pass,
        "min_validation_cases": min_validation_cases,
        "min_holdout_cases": min_holdout_cases,
        "min_validation_pnl_delta": min_validation_pnl_delta,
        "min_holdout_pnl_delta": min_holdout_pnl_delta,
        "min_validation_month_pnl_delta": min_validation_month_pnl_delta,
        "min_holdout_month_pnl_delta": min_holdout_month_pnl_delta,
        "min_validation_stateful_target_mean": min_validation_stateful_target_mean,
        "min_holdout_stateful_target_mean": min_holdout_stateful_target_mean,
    }
    return cases.sort_values(["split", "case_pass", "pnl_delta_sum"]).reset_index(drop=True), summary


def read_model_trade_delta_preflight_group_frame(
    path: Path,
    split: str,
    filename: str,
) -> pd.DataFrame:
    group_path = path / filename
    if not group_path.exists():
        return pd.DataFrame()
    frame = pd.read_csv(group_path)
    if frame.empty:
        return pd.DataFrame()
    frame = frame.copy()
    frame["split"] = split
    frame["case_label"] = path.name
    frame["delta_run"] = str(path)
    return frame


def summarize_model_trade_delta_preflight_group_drift(
    validation_paths: list[Path],
    holdout_paths: list[Path],
    *,
    filename: str = "group_by_month_status_direction_combined_regime.csv",
    group_columns: list[str] | None = None,
    metric_column: str = "pnl_delta",
    extra_metric_columns: list[str] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if group_columns is None:
        group_columns = ["delta_status", "direction", "combined_regime"]
    metric_columns = [metric_column]
    for column in extra_metric_columns or []:
        if column not in metric_columns:
            metric_columns.append(column)

    frames: list[pd.DataFrame] = []
    for path in expand_model_trade_delta_run_paths(validation_paths):
        frame = read_model_trade_delta_preflight_group_frame(path, "validation", filename)
        if not frame.empty:
            frames.append(frame)
    for path in expand_model_trade_delta_run_paths(holdout_paths):
        frame = read_model_trade_delta_preflight_group_frame(path, "holdout", filename)
        if not frame.empty:
            frames.append(frame)
    if not frames:
        return pd.DataFrame(), pd.DataFrame()

    rows = pd.concat(frames, ignore_index=True)
    missing_group_columns = [column for column in group_columns if column not in rows.columns]
    if missing_group_columns or metric_column not in rows.columns:
        return pd.DataFrame(), pd.DataFrame()

    rows = rows.copy()
    for column in metric_columns:
        if column in rows.columns:
            rows[column] = pd.to_numeric(rows[column], errors="coerce").fillna(0.0)
    if "row_count" not in rows.columns:
        rows["row_count"] = 1.0
    rows["row_count"] = pd.to_numeric(rows["row_count"], errors="coerce").fillna(0.0)
    if "month" not in rows.columns:
        rows["month"] = ""

    aggregations: dict[str, tuple[str, str] | tuple[str, object]] = {
        "month_count": ("month", "nunique"),
        "row_count_sum": ("row_count", "sum"),
    }
    for column in metric_columns:
        if column not in rows.columns:
            continue
        aggregations[f"{column}_sum"] = (column, "sum")
        aggregations[f"{column}_min_month"] = (column, "min")
        aggregations[f"{column}_negative_month_count"] = (
            column,
            lambda series: int((pd.to_numeric(series, errors="coerce").fillna(0.0) < 0).sum()),
        )

    split_group_columns = ["split", *group_columns]
    split_metrics = (
        rows.groupby(split_group_columns, dropna=False)
        .agg(**aggregations)
        .reset_index()
        .sort_values(["split", f"{metric_column}_sum"], ascending=[True, True])
        .reset_index(drop=True)
    )

    def prefixed(split: str) -> pd.DataFrame:
        subset = split_metrics.loc[split_metrics["split"].eq(split)].drop(columns=["split"])
        rename = {
            column: f"{split}_{column}"
            for column in subset.columns
            if column not in group_columns
        }
        return subset.rename(columns=rename)

    validation = prefixed("validation")
    holdout = prefixed("holdout")
    drift = validation.merge(holdout, on=group_columns, how="outer")
    for split in ["validation", "holdout"]:
        for column in ["month_count", "row_count_sum", f"{metric_column}_sum"]:
            prefixed_column = f"{split}_{column}"
            if prefixed_column in drift.columns:
                drift[prefixed_column] = drift[prefixed_column].fillna(0.0)

    validation_sum = f"validation_{metric_column}_sum"
    holdout_sum = f"holdout_{metric_column}_sum"
    if validation_sum in drift.columns and holdout_sum in drift.columns:
        drift[f"{metric_column}_holdout_minus_validation"] = (
            drift[holdout_sum] - drift[validation_sum]
        )
        drift["validation_positive_holdout_negative"] = (
            drift[validation_sum].gt(0.0) & drift[holdout_sum].lt(0.0)
        )
        drift["validation_nonnegative_holdout_negative"] = (
            drift[validation_sum].ge(0.0) & drift[holdout_sum].lt(0.0)
        )
        drift = drift.sort_values(
            [
                "validation_positive_holdout_negative",
                "validation_nonnegative_holdout_negative",
                holdout_sum,
            ],
            ascending=[False, False, True],
        ).reset_index(drop=True)

    return split_metrics, drift


def summarize_model_trade_delta_drift_stability(
    preflight_paths: list[Path],
    *,
    filename: str,
    metric_column: str,
    group_columns: list[str] | None = None,
) -> tuple[pd.DataFrame, dict[str, object]]:
    if group_columns is None:
        group_columns = ["delta_status", "direction", "combined_regime"]
    if not preflight_paths:
        raise ValueError("at least one preflight run is required")

    frames: list[pd.DataFrame] = []
    for path in preflight_paths:
        drift_path = path / filename
        if not drift_path.exists():
            raise FileNotFoundError(f"drift file not found: {drift_path}")
        frame = pd.read_csv(drift_path)
        if frame.empty:
            continue
        missing_group_columns = [column for column in group_columns if column not in frame.columns]
        required_columns = [
            "validation_positive_holdout_negative",
            f"validation_{metric_column}_sum",
            f"holdout_{metric_column}_sum",
            f"{metric_column}_holdout_minus_validation",
        ]
        missing_required_columns = [
            column for column in required_columns if column not in frame.columns
        ]
        if missing_group_columns or missing_required_columns:
            missing = [*missing_group_columns, *missing_required_columns]
            raise ValueError(f"{drift_path} missing columns: {missing}")
        frame = frame.copy()
        frame["comparison"] = path.name
        frames.append(frame)

    if not frames:
        summary = {
            "preflight_run_count": len(preflight_paths),
            "flip_group_count": 0,
            "common_flip_group_count": 0,
            "metric_column": metric_column,
            "filename": filename,
        }
        return pd.DataFrame(), summary

    rows = pd.concat(frames, ignore_index=True)
    rows["validation_positive_holdout_negative"] = rows[
        "validation_positive_holdout_negative"
    ].astype(bool)
    flip_rows = rows.loc[rows["validation_positive_holdout_negative"]].copy()
    if flip_rows.empty:
        summary = {
            "preflight_run_count": len(preflight_paths),
            "flip_group_count": 0,
            "common_flip_group_count": 0,
            "metric_column": metric_column,
            "filename": filename,
        }
        return pd.DataFrame(), summary

    validation_sum_column = f"validation_{metric_column}_sum"
    holdout_sum_column = f"holdout_{metric_column}_sum"
    delta_column = f"{metric_column}_holdout_minus_validation"
    for column in [validation_sum_column, holdout_sum_column, delta_column]:
        flip_rows[column] = pd.to_numeric(flip_rows[column], errors="coerce").fillna(0.0)

    stability = (
        flip_rows.groupby(group_columns, dropna=False)
        .agg(
            flip_comparison_count=("comparison", "nunique"),
            validation_sum_total=(validation_sum_column, "sum"),
            holdout_sum_total=(holdout_sum_column, "sum"),
            holdout_minus_validation_sum=(delta_column, "sum"),
            holdout_sum_min=(holdout_sum_column, "min"),
            comparisons=("comparison", lambda series: ",".join(sorted(set(map(str, series))))),
        )
        .reset_index()
    )
    stability["preflight_run_count"] = len(preflight_paths)
    stability["flip_comparison_share"] = (
        stability["flip_comparison_count"] / len(preflight_paths)
    )
    stability["all_comparisons_flip"] = stability["flip_comparison_count"].eq(
        len(preflight_paths)
    )
    stability = stability.sort_values(
        [
            "all_comparisons_flip",
            "flip_comparison_count",
            "holdout_minus_validation_sum",
        ],
        ascending=[False, False, True],
    ).reset_index(drop=True)

    summary = {
        "preflight_run_count": len(preflight_paths),
        "flip_group_count": int(len(stability)),
        "common_flip_group_count": int(stability["all_comparisons_flip"].sum()),
        "metric_column": metric_column,
        "filename": filename,
    }
    return stability, summary


def read_model_trade_delta_preflight_config_paths(path: Path) -> dict[str, list[Path]]:
    config_path = path / "config.json"
    if not config_path.exists():
        raise FileNotFoundError(f"preflight config not found: {config_path}")
    with config_path.open("r", encoding="utf-8") as handle:
        config = json.load(handle)
    validation = config.get("expanded_validation_deltas") or config.get("validation_deltas") or []
    holdout = config.get("expanded_holdout_deltas") or config.get("holdout_deltas") or []
    return {
        "validation": [Path(value) for value in validation],
        "holdout": [Path(value) for value in holdout],
    }


def summarize_model_trade_delta_drift_monthly_support(
    preflight_paths: list[Path],
    stability: pd.DataFrame,
    *,
    filename: str,
    metric_column: str,
    group_columns: list[str] | None = None,
    only_all_comparisons_flip: bool = True,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if group_columns is None:
        group_columns = ["delta_status", "direction", "combined_regime"]
    if stability.empty:
        return pd.DataFrame(), pd.DataFrame()

    candidate_groups = stability.copy()
    if only_all_comparisons_flip and "all_comparisons_flip" in candidate_groups.columns:
        candidate_groups = candidate_groups.loc[candidate_groups["all_comparisons_flip"]]
    if candidate_groups.empty:
        return pd.DataFrame(), pd.DataFrame()

    group_keys = {
        tuple(row[column] for column in group_columns)
        for _, row in candidate_groups.loc[:, group_columns].iterrows()
    }
    rows: list[pd.DataFrame] = []
    for preflight_path in preflight_paths:
        paths_by_split = read_model_trade_delta_preflight_config_paths(preflight_path)
        for split, delta_paths in paths_by_split.items():
            for delta_path in delta_paths:
                frame = read_model_trade_delta_preflight_group_frame(
                    delta_path,
                    split,
                    filename,
                )
                if frame.empty:
                    continue
                missing_group_columns = [
                    column for column in group_columns if column not in frame.columns
                ]
                if missing_group_columns or metric_column not in frame.columns:
                    continue
                mask = frame.loc[:, group_columns].apply(
                    lambda row: tuple(row[column] for column in group_columns) in group_keys,
                    axis=1,
                )
                subset = frame.loc[mask].copy()
                if subset.empty:
                    continue
                subset["comparison"] = preflight_path.name
                rows.append(subset)

    if not rows:
        return pd.DataFrame(), pd.DataFrame()

    support = pd.concat(rows, ignore_index=True)
    support[metric_column] = pd.to_numeric(support[metric_column], errors="coerce").fillna(0.0)
    if "row_count" not in support.columns:
        support["row_count"] = 1.0
    support["row_count"] = pd.to_numeric(support["row_count"], errors="coerce").fillna(0.0)
    if "month" not in support.columns:
        support["month"] = ""

    support = support.sort_values(
        ["comparison", "split", *group_columns, "month"],
    ).reset_index(drop=True)
    summary = (
        support.groupby(["comparison", "split", *group_columns], dropna=False)
        .agg(
            month_count=("month", "nunique"),
            row_count_sum=("row_count", "sum"),
            metric_sum=(metric_column, "sum"),
            metric_min_month=(metric_column, "min"),
            metric_negative_month_count=(
                metric_column,
                lambda series: int((pd.to_numeric(series, errors="coerce").fillna(0.0) < 0).sum()),
            ),
            metric_positive_month_count=(
                metric_column,
                lambda series: int((pd.to_numeric(series, errors="coerce").fillna(0.0) > 0).sum()),
            ),
        )
        .reset_index()
        .sort_values(["comparison", *group_columns, "split"])
        .reset_index(drop=True)
    )
    return support, summary


def handle_model_trade_delta_preflight(args: argparse.Namespace) -> int:
    validation_paths = parse_csv_paths(args.validation_deltas)
    holdout_paths = parse_csv_paths(args.holdout_deltas)
    available_context_group_columns = ["direction", "combined_regime"]
    cases, summary = summarize_model_trade_delta_preflight(
        validation_paths,
        holdout_paths,
        min_validation_cases=args.min_validation_cases,
        min_holdout_cases=args.min_holdout_cases,
        min_validation_pnl_delta=args.min_validation_pnl_delta,
        min_holdout_pnl_delta=args.min_holdout_pnl_delta,
        min_validation_month_pnl_delta=args.min_validation_month_pnl_delta,
        min_holdout_month_pnl_delta=args.min_holdout_month_pnl_delta,
        min_validation_stateful_target_mean=args.min_validation_stateful_target_mean,
        min_holdout_stateful_target_mean=args.min_holdout_stateful_target_mean,
    )
    split_group_metrics, group_drift = summarize_model_trade_delta_preflight_group_drift(
        validation_paths,
        holdout_paths,
        extra_metric_columns=[
            "row_count",
            "base_adjusted_pnl",
            "candidate_adjusted_pnl",
            "base_trade_count",
            "candidate_trade_count",
        ],
    )
    split_stateful_group_metrics, stateful_group_drift = (
        summarize_model_trade_delta_preflight_group_drift(
            validation_paths,
            holdout_paths,
            filename="group_by_blocking_candidate_month_status_direction_combined_regime.csv",
            metric_column="candidate_stateful_net_adjusted_pnl",
            extra_metric_columns=[
                "candidate_adjusted_pnl",
                "blocked_base_adjusted_pnl",
                "blocked_base_positive_pnl",
                "blocked_base_negative_pnl",
            ],
        )
    )
    split_available_group_metrics, available_group_drift = (
        summarize_model_trade_delta_preflight_group_drift(
            validation_paths,
            holdout_paths,
            group_columns=available_context_group_columns,
            extra_metric_columns=[
                "row_count",
                "base_adjusted_pnl",
                "candidate_adjusted_pnl",
                "base_trade_count",
                "candidate_trade_count",
            ],
        )
    )
    split_available_stateful_group_metrics, available_stateful_group_drift = (
        summarize_model_trade_delta_preflight_group_drift(
            validation_paths,
            holdout_paths,
            filename="group_by_blocking_candidate_month_status_direction_combined_regime.csv",
            group_columns=available_context_group_columns,
            metric_column="candidate_stateful_net_adjusted_pnl",
            extra_metric_columns=[
                "candidate_adjusted_pnl",
                "blocked_base_adjusted_pnl",
                "blocked_base_positive_pnl",
                "blocked_base_negative_pnl",
            ],
        )
    )
    if not group_drift.empty:
        summary["group_drift_validation_positive_holdout_negative_count"] = int(
            group_drift["validation_positive_holdout_negative"].sum()
        )
        summary["group_drift_validation_nonnegative_holdout_negative_count"] = int(
            group_drift["validation_nonnegative_holdout_negative"].sum()
        )
    if not stateful_group_drift.empty:
        summary["stateful_group_drift_validation_positive_holdout_negative_count"] = int(
            stateful_group_drift["validation_positive_holdout_negative"].sum()
        )
        summary["stateful_group_drift_validation_nonnegative_holdout_negative_count"] = int(
            stateful_group_drift["validation_nonnegative_holdout_negative"].sum()
        )
    if not available_group_drift.empty:
        summary["available_group_drift_validation_positive_holdout_negative_count"] = int(
            available_group_drift["validation_positive_holdout_negative"].sum()
        )
        summary["available_group_drift_validation_nonnegative_holdout_negative_count"] = int(
            available_group_drift["validation_nonnegative_holdout_negative"].sum()
        )
    if not available_stateful_group_drift.empty:
        summary["available_stateful_group_drift_validation_positive_holdout_negative_count"] = int(
            available_stateful_group_drift["validation_positive_holdout_negative"].sum()
        )
        summary["available_stateful_group_drift_validation_nonnegative_holdout_negative_count"] = int(
            available_stateful_group_drift["validation_nonnegative_holdout_negative"].sum()
        )

    run_dir = make_run_dir(args.output_dir, args.label)
    cases.to_csv(run_dir / "case_metrics.csv", index=False)
    cases.loc[~cases["case_pass"]].to_csv(run_dir / "failed_cases.csv", index=False)
    if not split_group_metrics.empty:
        split_group_metrics.to_csv(
            run_dir / "split_group_metrics_status_direction_combined_regime.csv",
            index=False,
        )
    if not group_drift.empty:
        group_drift.to_csv(
            run_dir / "group_drift_status_direction_combined_regime.csv",
            index=False,
        )
    if not split_stateful_group_metrics.empty:
        split_stateful_group_metrics.to_csv(
            run_dir / "split_stateful_group_metrics_status_direction_combined_regime.csv",
            index=False,
        )
    if not stateful_group_drift.empty:
        stateful_group_drift.to_csv(
            run_dir / "stateful_group_drift_status_direction_combined_regime.csv",
            index=False,
        )
    if not split_available_group_metrics.empty:
        split_available_group_metrics.to_csv(
            run_dir / "split_group_metrics_direction_combined_regime.csv",
            index=False,
        )
    if not available_group_drift.empty:
        available_group_drift.to_csv(
            run_dir / "group_drift_direction_combined_regime.csv",
            index=False,
        )
    if not split_available_stateful_group_metrics.empty:
        split_available_stateful_group_metrics.to_csv(
            run_dir / "split_stateful_group_metrics_direction_combined_regime.csv",
            index=False,
        )
    if not available_stateful_group_drift.empty:
        available_stateful_group_drift.to_csv(
            run_dir / "stateful_group_drift_direction_combined_regime.csv",
            index=False,
        )
    metadata = {
        "validation_deltas": [str(path) for path in validation_paths],
        "expanded_validation_deltas": [
            str(path) for path in expand_model_trade_delta_run_paths(validation_paths)
        ],
        "holdout_deltas": [str(path) for path in holdout_paths],
        "expanded_holdout_deltas": [
            str(path) for path in expand_model_trade_delta_run_paths(holdout_paths)
        ],
        "summary": summary,
    }
    with (run_dir / "config.json").open("w", encoding="utf-8") as handle:
        json.dump(metadata, handle, ensure_ascii=False, indent=2, default=json_default)
    with (run_dir / "summary.json").open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2, default=json_default)

    print("preflight summary:")
    for key, value in summary.items():
        print(f"{key}: {value}")
    display_columns = [
        "split",
        "case_label",
        "case_pass",
        "pnl_delta_sum",
        "pnl_delta_min_month",
        "stateful_target_mean_min_month",
        "pnl_delta_negative_month_count",
        "stateful_target_negative_month_count",
    ]
    existing_display_columns = [column for column in display_columns if column in cases.columns]
    print("cases:")
    print(cases.loc[:, existing_display_columns].head(args.top_n).to_string(index=False))
    if not group_drift.empty:
        drift_columns = [
            "delta_status",
            "direction",
            "combined_regime",
            "validation_pnl_delta_sum",
            "holdout_pnl_delta_sum",
            "pnl_delta_holdout_minus_validation",
            "validation_positive_holdout_negative",
        ]
        existing_drift_columns = [column for column in drift_columns if column in group_drift.columns]
        print("worst validation/holdout group drift:")
        print(group_drift.loc[:, existing_drift_columns].head(args.top_n).to_string(index=False))
    if not stateful_group_drift.empty:
        stateful_columns = [
            "delta_status",
            "direction",
            "combined_regime",
            "validation_candidate_stateful_net_adjusted_pnl_sum",
            "holdout_candidate_stateful_net_adjusted_pnl_sum",
            "candidate_stateful_net_adjusted_pnl_holdout_minus_validation",
            "validation_positive_holdout_negative",
        ]
        existing_stateful_columns = [
            column for column in stateful_columns if column in stateful_group_drift.columns
        ]
        print("worst validation/holdout stateful group drift:")
        print(
            stateful_group_drift.loc[:, existing_stateful_columns]
            .head(args.top_n)
            .to_string(index=False)
        )
    if not available_group_drift.empty:
        available_columns = [
            "direction",
            "combined_regime",
            "validation_pnl_delta_sum",
            "holdout_pnl_delta_sum",
            "pnl_delta_holdout_minus_validation",
            "validation_positive_holdout_negative",
        ]
        existing_available_columns = [
            column for column in available_columns if column in available_group_drift.columns
        ]
        print("worst available-context validation/holdout group drift:")
        print(
            available_group_drift.loc[:, existing_available_columns]
            .head(args.top_n)
            .to_string(index=False)
        )
    if not available_stateful_group_drift.empty:
        available_stateful_columns = [
            "direction",
            "combined_regime",
            "validation_candidate_stateful_net_adjusted_pnl_sum",
            "holdout_candidate_stateful_net_adjusted_pnl_sum",
            "candidate_stateful_net_adjusted_pnl_holdout_minus_validation",
            "validation_positive_holdout_negative",
        ]
        existing_available_stateful_columns = [
            column
            for column in available_stateful_columns
            if column in available_stateful_group_drift.columns
        ]
        print("worst available-context validation/holdout stateful group drift:")
        print(
            available_stateful_group_drift.loc[:, existing_available_stateful_columns]
            .head(args.top_n)
            .to_string(index=False)
        )
    print(f"artifacts: {run_dir}")
    return 0


def optional_model_trade_delta_drift_stability(
    preflight_paths: list[Path],
    *,
    filename: str,
    metric_column: str,
    group_columns: list[str],
) -> tuple[pd.DataFrame, dict[str, object]]:
    missing = [str(path / filename) for path in preflight_paths if not (path / filename).exists()]
    if missing:
        return pd.DataFrame(), {
            "preflight_run_count": len(preflight_paths),
            "flip_group_count": 0,
            "common_flip_group_count": 0,
            "metric_column": metric_column,
            "filename": filename,
            "missing_files": missing,
        }
    return summarize_model_trade_delta_drift_stability(
        preflight_paths,
        filename=filename,
        metric_column=metric_column,
        group_columns=group_columns,
    )


def handle_model_trade_delta_drift_stability(args: argparse.Namespace) -> int:
    preflight_paths = parse_csv_paths(args.preflight_runs)
    available_context_group_columns = ["direction", "combined_regime"]
    pnl_stability, pnl_summary = summarize_model_trade_delta_drift_stability(
        preflight_paths,
        filename="group_drift_status_direction_combined_regime.csv",
        metric_column="pnl_delta",
    )
    stateful_stability, stateful_summary = summarize_model_trade_delta_drift_stability(
        preflight_paths,
        filename="stateful_group_drift_status_direction_combined_regime.csv",
        metric_column="candidate_stateful_net_adjusted_pnl",
    )
    available_pnl_stability, available_pnl_summary = (
        optional_model_trade_delta_drift_stability(
            preflight_paths,
            filename="group_drift_direction_combined_regime.csv",
            metric_column="pnl_delta",
            group_columns=available_context_group_columns,
        )
    )
    available_stateful_stability, available_stateful_summary = (
        optional_model_trade_delta_drift_stability(
            preflight_paths,
            filename="stateful_group_drift_direction_combined_regime.csv",
            metric_column="candidate_stateful_net_adjusted_pnl",
            group_columns=available_context_group_columns,
        )
    )
    pnl_support, pnl_support_summary = summarize_model_trade_delta_drift_monthly_support(
        preflight_paths,
        pnl_stability,
        filename="group_by_month_status_direction_combined_regime.csv",
        metric_column="pnl_delta",
    )
    stateful_support, stateful_support_summary = (
        summarize_model_trade_delta_drift_monthly_support(
            preflight_paths,
            stateful_stability,
            filename="group_by_blocking_candidate_month_status_direction_combined_regime.csv",
            metric_column="candidate_stateful_net_adjusted_pnl",
        )
    )
    available_pnl_support, available_pnl_support_summary = (
        summarize_model_trade_delta_drift_monthly_support(
            preflight_paths,
            available_pnl_stability,
            filename="group_by_month_status_direction_combined_regime.csv",
            metric_column="pnl_delta",
            group_columns=available_context_group_columns,
        )
    )
    available_stateful_support, available_stateful_support_summary = (
        summarize_model_trade_delta_drift_monthly_support(
            preflight_paths,
            available_stateful_stability,
            filename="group_by_blocking_candidate_month_status_direction_combined_regime.csv",
            metric_column="candidate_stateful_net_adjusted_pnl",
            group_columns=available_context_group_columns,
        )
    )
    run_dir = make_run_dir(args.output_dir, args.label)
    if not pnl_stability.empty:
        pnl_stability.to_csv(run_dir / "flip_stability_pnl.csv", index=False)
    if not stateful_stability.empty:
        stateful_stability.to_csv(run_dir / "flip_stability_stateful.csv", index=False)
    if not available_pnl_stability.empty:
        available_pnl_stability.to_csv(
            run_dir / "flip_stability_available_pnl.csv",
            index=False,
        )
    if not available_stateful_stability.empty:
        available_stateful_stability.to_csv(
            run_dir / "flip_stability_available_stateful.csv",
            index=False,
        )
    if not pnl_support.empty:
        pnl_support.to_csv(run_dir / "flip_stability_pnl_monthly_support.csv", index=False)
        pnl_support_summary.to_csv(
            run_dir / "flip_stability_pnl_monthly_support_summary.csv",
            index=False,
        )
    if not stateful_support.empty:
        stateful_support.to_csv(
            run_dir / "flip_stability_stateful_monthly_support.csv",
            index=False,
        )
        stateful_support_summary.to_csv(
            run_dir / "flip_stability_stateful_monthly_support_summary.csv",
            index=False,
        )
    if not available_pnl_support.empty:
        available_pnl_support.to_csv(
            run_dir / "flip_stability_available_pnl_monthly_support.csv",
            index=False,
        )
        available_pnl_support_summary.to_csv(
            run_dir / "flip_stability_available_pnl_monthly_support_summary.csv",
            index=False,
        )
    if not available_stateful_support.empty:
        available_stateful_support.to_csv(
            run_dir / "flip_stability_available_stateful_monthly_support.csv",
            index=False,
        )
        available_stateful_support_summary.to_csv(
            run_dir / "flip_stability_available_stateful_monthly_support_summary.csv",
            index=False,
        )
    summary = {
        "preflight_runs": [str(path) for path in preflight_paths],
        "pnl": pnl_summary,
        "stateful": stateful_summary,
        "available_pnl": available_pnl_summary,
        "available_stateful": available_stateful_summary,
        "pnl_monthly_support_rows": int(len(pnl_support)),
        "stateful_monthly_support_rows": int(len(stateful_support)),
        "available_pnl_monthly_support_rows": int(len(available_pnl_support)),
        "available_stateful_monthly_support_rows": int(len(available_stateful_support)),
    }
    with (run_dir / "summary.json").open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2, default=json_default)

    print("drift stability summary:")
    print(f"pnl common flip groups: {pnl_summary['common_flip_group_count']}")
    print(f"stateful common flip groups: {stateful_summary['common_flip_group_count']}")
    print(f"available-context pnl common flip groups: {available_pnl_summary['common_flip_group_count']}")
    print(
        "available-context stateful common flip groups: "
        f"{available_stateful_summary['common_flip_group_count']}"
    )
    print(f"pnl monthly support rows: {len(pnl_support)}")
    print(f"stateful monthly support rows: {len(stateful_support)}")
    print(f"available-context pnl monthly support rows: {len(available_pnl_support)}")
    print(f"available-context stateful monthly support rows: {len(available_stateful_support)}")
    display_columns = [
        "delta_status",
        "direction",
        "combined_regime",
        "flip_comparison_count",
        "flip_comparison_share",
        "validation_sum_total",
        "holdout_sum_total",
        "holdout_minus_validation_sum",
        "comparisons",
    ]
    if not pnl_stability.empty:
        print("pnl flip stability:")
        existing_columns = [column for column in display_columns if column in pnl_stability.columns]
        print(pnl_stability.loc[:, existing_columns].head(args.top_n).to_string(index=False))
    if not stateful_stability.empty:
        print("stateful flip stability:")
        existing_columns = [
            column for column in display_columns if column in stateful_stability.columns
        ]
        print(stateful_stability.loc[:, existing_columns].head(args.top_n).to_string(index=False))
    available_display_columns = [
        "direction",
        "combined_regime",
        "flip_comparison_count",
        "flip_comparison_share",
        "validation_sum_total",
        "holdout_sum_total",
        "holdout_minus_validation_sum",
        "comparisons",
    ]
    if not available_pnl_stability.empty:
        print("available-context pnl flip stability:")
        existing_columns = [
            column for column in available_display_columns if column in available_pnl_stability.columns
        ]
        print(
            available_pnl_stability.loc[:, existing_columns]
            .head(args.top_n)
            .to_string(index=False)
        )
    if not available_stateful_stability.empty:
        print("available-context stateful flip stability:")
        existing_columns = [
            column
            for column in available_display_columns
            if column in available_stateful_stability.columns
        ]
        print(
            available_stateful_stability.loc[:, existing_columns]
            .head(args.top_n)
            .to_string(index=False)
        )
    print(f"artifacts: {run_dir}")
    return 0


def handle_analyze_trades(args: argparse.Namespace) -> int:
    trades = read_trades_csv(args.trades)
    predictions = read_analysis_predictions(args.predictions, args.long_column, args.short_column)
    enriched = enrich_trades_with_predictions(trades, predictions)
    flags = trade_failure_flags(enriched)
    summary = trade_analysis_summary(enriched)

    run_dir = make_run_dir(args.output_dir, args.label)
    enriched.to_csv(run_dir / "enriched_trades.csv", index=False)
    flags.to_csv(run_dir / "failure_flags.csv", index=False)
    enriched.sort_values("adjusted_pnl").head(args.top_n).to_csv(
        run_dir / "worst_trades.csv",
        index=False,
    )
    for column in ANALYSIS_GROUP_COLUMNS:
        group = trade_group_summary(enriched, column)
        if not group.empty:
            group.to_csv(run_dir / f"group_by_{column}.csv", index=False)

    metadata = {
        "trades": str(args.trades),
        "predictions": str(args.predictions),
        "long_column": args.long_column,
        "short_column": args.short_column,
        "label": args.label,
        "top_n": args.top_n,
        "summary": summary,
    }
    with (run_dir / "summary.json").open("w", encoding="utf-8") as handle:
        json.dump(metadata, handle, ensure_ascii=False, indent=2, default=json_default)

    print("summary:")
    for key, value in summary.items():
        if isinstance(value, float):
            print(f"{key}: {value:.6f}")
        else:
            print(f"{key}: {value}")
    print("failure flags:")
    print(flags.head(args.top_n).to_string(index=False))
    print(f"artifacts: {run_dir}")
    return 0


def handle_benchmark(args: argparse.Namespace) -> int:
    df, backtest_config = prepare_data_and_config(args)
    strategies = args.strategies.split(",") if args.strategies else available_strategies()
    strategies = [strategy.strip() for strategy in strategies if strategy.strip()]
    unknown = sorted(set(strategies) - set(available_strategies()))
    if unknown:
        raise SystemExit(f"unknown strategies: {', '.join(unknown)}")

    benchmark_dir = make_run_dir(args.output_dir, f"benchmark_{args.month}")
    rows: list[dict[str, object]] = []
    for strategy in strategies:
        strategy_config = strategy_config_from_args(args, strategy=strategy)
        metrics, trades, curve = run_strategy(df, backtest_config, strategy_config)
        rows.append(metrics)
        write_result(
            benchmark_dir / strategy,
            metrics,
            trades,
            curve,
            strategy_config,
            backtest_config,
        )

    metrics_frame = pd.DataFrame(rows).sort_values("total_adjusted_pnl", ascending=False)
    metrics_frame.to_csv(benchmark_dir / "metrics.csv", index=False)
    print(metrics_frame.to_string(index=False))
    print(f"artifacts: {benchmark_dir}")
    return 0


def add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--data",
        type=Path,
        default=Path("data/processed/histdata/xauusd/xauusd_m1.parquet"),
    )
    parser.add_argument("--month", required=True, help="evaluation month in YYYY-MM")
    parser.add_argument("--output-dir", type=Path, default=Path("data/reports/backtests"))
    parser.add_argument("--warmup-days", type=int, default=7)
    parser.add_argument("--post-days", type=int, default=4)
    parser.add_argument("--max-hold-hours", type=float, default=24.0)
    parser.add_argument("--profit-multiplier", type=float, default=1.0)
    parser.add_argument("--loss-multiplier", type=float, default=1.2)
    parser.add_argument(
        "--spread-points",
        type=float,
        default=0.0,
        help="full spread in price points; half is charged on each execution side",
    )
    parser.add_argument(
        "--slippage-points",
        type=float,
        default=0.0,
        help="additional adverse price points charged on each execution side",
    )
    parser.add_argument(
        "--execution-delay-bars",
        type=int,
        default=0,
        help="extra bars to delay execution after the normal next-open fill",
    )
    parser.add_argument("--fast-window", type=int, default=20)
    parser.add_argument("--slow-window", type=int, default=80)
    parser.add_argument("--rsi-window", type=int, default=14)
    parser.add_argument("--rsi-lower", type=float, default=30.0)
    parser.add_argument("--rsi-upper", type=float, default=70.0)
    parser.add_argument("--rsi-exit-lower", type=float, default=45.0)
    parser.add_argument("--rsi-exit-upper", type=float, default=55.0)
    parser.add_argument("--breakout-window", type=int, default=120)
    parser.add_argument("--random-entry-probability", type=float, default=0.002)
    parser.add_argument("--random-exit-probability", type=float, default=0.01)
    parser.add_argument("--random-seed", type=int, default=7)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run XAUUSD backtests")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run = subparsers.add_parser("run", help="run one strategy for one month")
    add_common_args(run)
    run.add_argument("--strategy", choices=available_strategies(), required=True)
    run.set_defaults(func=handle_run)

    benchmark = subparsers.add_parser("benchmark", help="run baseline strategies")
    add_common_args(benchmark)
    benchmark.add_argument(
        "--strategies",
        default="",
        help="comma-separated strategy list; defaults to all baselines",
    )
    benchmark.set_defaults(func=handle_benchmark)

    model_policy = subparsers.add_parser("model-policy", help="run a backtest from saved model predictions")
    add_common_args(model_policy)
    add_model_policy_args(model_policy)
    model_policy.set_defaults(func=handle_model_policy)

    model_cost_sensitivity = subparsers.add_parser(
        "model-cost-sensitivity",
        help="run one model policy across spread, slippage, and execution-delay stress settings",
    )
    add_common_args(model_cost_sensitivity)
    add_model_policy_args(model_cost_sensitivity)
    model_cost_sensitivity.add_argument("--spread-points-list", default="0,0.1,0.2")
    model_cost_sensitivity.add_argument("--slippage-points-list", default="0,0.05,0.1")
    model_cost_sensitivity.add_argument("--execution-delay-bars-list", default="0,1")
    model_cost_sensitivity.set_defaults(func=handle_model_cost_sensitivity)

    model_sweep = subparsers.add_parser("model-sweep", help="sweep thresholds for saved model predictions")
    add_common_args(model_sweep)
    model_sweep.add_argument("--predictions", type=Path, required=True)
    model_sweep.add_argument("--policies", default="stateful_ev,stateless_ev")
    model_sweep.add_argument("--entry-thresholds", default="5,10,15,20,25")
    model_sweep.add_argument("--long-entry-threshold-offsets", default="0")
    model_sweep.add_argument("--short-entry-threshold-offsets", default="0")
    model_sweep.add_argument("--exit-thresholds", default="-5,0,5,10")
    model_sweep.add_argument("--side-margins", default="0,5,10")
    model_sweep.add_argument("--risk-penalties", default="0")
    model_sweep.add_argument(
        "--profit-barrier-miss-penalties",
        default="0",
        help="comma-separated EV penalties multiplied by 1 - side profit-barrier prediction",
    )
    model_sweep.add_argument(
        "--time-exit-penalties",
        default="0",
        help="comma-separated EV penalties multiplied by side time-exit probability",
    )
    model_sweep.add_argument(
        "--loss-first-penalties",
        default="0",
        help="comma-separated EV penalties multiplied by side loss-first exit-event probability",
    )
    model_sweep.add_argument(
        "--time-exit-holding-shrinks",
        default="0",
        help="comma-separated holding-time shrink factors multiplied by side time-exit probability",
    )
    model_sweep.add_argument(
        "--loss-first-holding-shrinks",
        default="0",
        help="comma-separated holding-time shrink factors multiplied by side loss-first exit-event probability",
    )
    model_sweep.add_argument(
        "--holding-shortening-thresholds",
        default="inf",
        help=(
            "comma-separated probability thresholds that cap holding time when a "
            "short fixed hold is predicted to beat the exit-event hold; inf disables"
        ),
    )
    model_sweep.add_argument(
        "--holding-shortening-cap-minutes",
        default="60",
        help="comma-separated holding-time caps used after holding-shortening threshold is met",
    )
    model_sweep.add_argument(
        "--time-exit-exit-thresholds",
        default="inf",
        help="comma-separated thresholds that exit open positions on side time-exit probability",
    )
    model_sweep.add_argument(
        "--loss-first-exit-thresholds",
        default="inf",
        help="comma-separated thresholds that exit open positions on side loss-first probability",
    )
    model_sweep.add_argument(
        "--side-confidence-penalties",
        default="0",
        help="comma-separated EV penalties multiplied by 1 - predicted best-side probability",
    )
    model_sweep.add_argument(
        "--side-confidence-penalty-rules",
        default="",
        help=(
            "comma-separated column=value+...:penalty rules that add to side-confidence "
            "penalty in matching regimes"
        ),
    )
    model_sweep.add_argument(
        "--side-confidence-overfit-penalty-rules",
        default="",
        help=(
            "comma-separated column=value+...:penalty rules that subtract penalty * "
            "side confidence in matching regimes"
        ),
    )
    model_sweep.add_argument("--max-wait-regrets", default="inf")
    model_sweep.add_argument("--min-entry-ranks", default="0")
    model_sweep.add_argument("--min-trade-qualities", default="-inf")
    model_sweep.add_argument("--min-side-confidences", default="0")
    model_sweep.add_argument("--require-profit-barriers", default="false")
    model_sweep.add_argument("--profit-barrier-thresholds", default="0.5")
    model_sweep.add_argument(
        "--side-ev-penalty-rules",
        default="",
        help=(
            "comma-separated side:column=value+...:penalty rules that subtract EV from "
            "the matching side before side selection"
        ),
    )
    model_sweep.add_argument(
        "--side-ev-penalty-rule-sets",
        default=None,
        help=(
            "semicolon-separated side-EV-penalty rule sets; each set uses comma-separated "
            "side:column=value+...:penalty rules, with none/empty/- for no rules"
        ),
    )
    model_sweep.add_argument(
        "--side-ev-penalty-replacement-min-margins",
        default="-inf",
        help=(
            "comma-separated extra selected-score margins over the normal entry threshold "
            "required only when side-EV penalty rules match the selected side or change "
            "the selected side; -inf disables"
        ),
    )
    model_sweep.add_argument(
        "--extra-side-margin-rules",
        default="",
        help="comma-separated column=value:margin rules that add side-margin in matching regimes",
    )
    model_sweep.add_argument(
        "--side-extra-margin-rules",
        default="",
        help=(
            "comma-separated side:column=value+...:margin rules that add side-margin only "
            "when the selected side and all conditions match"
        ),
    )
    model_sweep.add_argument(
        "--side-extra-margin-rule-sets",
        default=None,
        help=(
            "semicolon-separated side-extra-margin rule sets; each set uses comma-separated "
            "side:column=value+...:margin rules, with none/empty/- for no rules"
        ),
    )
    model_sweep.add_argument(
        "--side-block-rules",
        default="",
        help=(
            "comma-separated side:column=value+... rules that block entries only when the "
            "selected side and all conditions match"
        ),
    )
    model_sweep.add_argument(
        "--side-block-rule-sets",
        default=None,
        help=(
            "semicolon-separated side-block rule sets; each set uses comma-separated "
            "side:column=value+... rules, with none/empty/- for no rules"
        ),
    )
    model_sweep.add_argument(
        "--context-drawdown-guard-loss-thresholds",
        default="inf",
        help=(
            "comma-separated positive realized loss thresholds that block later entries "
            "in the same online direction/context; inf disables"
        ),
    )
    model_sweep.add_argument(
        "--context-drawdown-guard-min-entry-margins",
        default="inf",
        help=(
            "comma-separated selected-score margins required after a context drawdown "
            "breach; inf preserves hard blocking"
        ),
    )
    model_sweep.add_argument(
        "--context-drawdown-guard-context-columns",
        default="combined_regime,session_regime",
        help="comma-separated prediction columns used with direction as the online drawdown context",
    )
    model_sweep.add_argument(
        "--context-drawdown-guard-reset-monthly",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="reset online context drawdown guard by entry decision month",
    )
    model_sweep.add_argument("--min-trades", type=int, default=0)
    model_sweep.add_argument("--max-forced-exit-rate", type=float, default=1.0)
    model_sweep.add_argument("--max-drawdown", type=float, default=float("inf"))
    model_sweep.add_argument("--long-column", default="pred_long_best_adjusted_pnl")
    model_sweep.add_argument("--short-column", default="pred_short_best_adjusted_pnl")
    model_sweep.add_argument("--long-risk-column", default="pred_long_max_adverse_pnl")
    model_sweep.add_argument("--short-risk-column", default="pred_short_max_adverse_pnl")
    model_sweep.add_argument(
        "--long-secondary-score-column",
        default="",
        help="optional long-side secondary score used only for near-tie side selection",
    )
    model_sweep.add_argument(
        "--short-secondary-score-column",
        default="",
        help="optional short-side secondary score used only for near-tie side selection",
    )
    model_sweep.add_argument(
        "--secondary-score-tie-margins",
        default="-inf",
        help=(
            "comma-separated primary EV side gaps at or below which secondary score "
            "columns may choose the side; -inf disables"
        ),
    )
    model_sweep.add_argument("--long-holding-column", default="pred_long_best_holding_minutes")
    model_sweep.add_argument("--short-holding-column", default="pred_short_best_holding_minutes")
    model_sweep.add_argument("--min-predicted-hold-minutes", default="1")
    model_sweep.add_argument("--max-predicted-hold-minutes", default="1440")
    model_sweep.add_argument(
        "--min-valid-predicted-hold-minutes",
        default="auto",
        help=(
            "comma-separated raw timed_ev holding validity thresholds; entries below the "
            "threshold are skipped unless a valid fallback holding column is supplied; "
            "auto uses 30 for pred_mlp_* holding columns and -inf otherwise"
        ),
    )
    model_sweep.add_argument(
        "--long-holding-fallback-column",
        default="",
        help="optional long holding fallback column for timed_ev hold guards",
    )
    model_sweep.add_argument(
        "--short-holding-fallback-column",
        default="",
        help="optional short holding fallback column for timed_ev hold guards",
    )
    model_sweep.add_argument(
        "--fixed-horizon-minutes",
        default=",".join(str(int(minutes)) for minutes in DEFAULT_FIXED_HORIZON_MINUTES),
    )
    model_sweep.add_argument(
        "--long-fixed-horizon-columns",
        default=",".join(DEFAULT_LONG_FIXED_HORIZON_COLUMNS),
    )
    model_sweep.add_argument(
        "--short-fixed-horizon-columns",
        default=",".join(DEFAULT_SHORT_FIXED_HORIZON_COLUMNS),
    )
    model_sweep.add_argument(
        "--fixed-horizon-score-modes",
        default="max",
        help="comma-separated fixed-horizon EV aggregation modes: max,mean,median,min",
    )
    model_sweep.add_argument("--long-wait-regret-column", default="pred_long_wait_regret")
    model_sweep.add_argument("--short-wait-regret-column", default="pred_short_wait_regret")
    model_sweep.add_argument("--long-entry-rank-column", default="pred_long_entry_local_rank")
    model_sweep.add_argument("--short-entry-rank-column", default="pred_short_entry_local_rank")
    model_sweep.add_argument("--long-profit-barrier-column", default="pred_long_profit_barrier_hit")
    model_sweep.add_argument("--short-profit-barrier-column", default="pred_short_profit_barrier_hit")
    model_sweep.add_argument("--long-time-exit-column", default="pred_long_exit_event_prob_0")
    model_sweep.add_argument("--short-time-exit-column", default="pred_short_exit_event_prob_0")
    model_sweep.add_argument("--long-loss-first-column", default="pred_long_exit_event_prob_2")
    model_sweep.add_argument("--short-loss-first-column", default="pred_short_exit_event_prob_2")
    model_sweep.add_argument(
        "--long-holding-shortening-column",
        default="pred_long_fixed_60m_beats_exit_event_prob_1",
    )
    model_sweep.add_argument(
        "--short-holding-shortening-column",
        default="pred_short_fixed_60m_beats_exit_event_prob_1",
    )
    model_sweep.add_argument("--long-side-confidence-column", default="pred_best_side_prob_1")
    model_sweep.add_argument("--short-side-confidence-column", default="pred_best_side_prob_-1")
    model_sweep.add_argument("--long-trade-quality-column", default="pred_trade_quality_long_adjusted_pnl")
    model_sweep.add_argument("--short-trade-quality-column", default="pred_trade_quality_short_adjusted_pnl")
    add_regime_gate_args(model_sweep)
    model_sweep.add_argument("--top-n", type=int, default=10)
    model_sweep.set_defaults(func=handle_model_sweep)

    model_sweep_summary = subparsers.add_parser(
        "model-sweep-summary",
        help="aggregate multiple model-sweep CSV files by policy parameters",
    )
    model_sweep_summary.add_argument(
        "--sweeps",
        required=True,
        help="comma-separated paths to model-sweep metrics.csv files",
    )
    model_sweep_summary.add_argument("--output-dir", type=Path, default=Path("data/reports/backtests"))
    model_sweep_summary.add_argument("--min-folds", type=int, default=2)
    model_sweep_summary.add_argument("--min-trades-per-fold", type=int, default=30)
    model_sweep_summary.add_argument("--max-forced-exit-rate", type=float, default=0.0)
    model_sweep_summary.add_argument("--max-drawdown", type=float, default=100.0)
    model_sweep_summary.add_argument("--min-adjusted-pnl-per-fold", type=float, default=-1e100)
    model_sweep_summary.add_argument(
        "--sort-by",
        choices=["mean_pnl", "min_pnl", "sum_pnl"],
        default="mean_pnl",
    )
    model_sweep_summary.add_argument("--top-n", type=int, default=10)
    model_sweep_summary.set_defaults(func=handle_model_sweep_summary)

    model_candidate_selection = subparsers.add_parser(
        "model-candidate-selection",
        help="combine no-cost and cost-aware sweep summaries with robustness gates",
    )
    model_candidate_selection.add_argument(
        "--base-sweeps",
        required=True,
        help="comma-separated no-cost model-sweep metrics.csv files",
    )
    model_candidate_selection.add_argument(
        "--cost-sweeps",
        required=True,
        help="comma-separated cost-aware model-sweep metrics.csv files",
    )
    model_candidate_selection.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/reports/backtests"),
    )
    model_candidate_selection.add_argument("--min-folds", type=int, default=2)
    model_candidate_selection.add_argument(
        "--min-base-folds",
        type=int,
        default=None,
        help="minimum required base/no-cost folds; defaults to --min-folds",
    )
    model_candidate_selection.add_argument(
        "--min-cost-folds",
        type=int,
        default=None,
        help="minimum required cost-aware folds; defaults to --min-folds",
    )
    model_candidate_selection.add_argument("--min-trades-per-fold", type=int, default=30)
    model_candidate_selection.add_argument("--max-forced-exit-rate", type=float, default=0.0)
    model_candidate_selection.add_argument("--max-drawdown", type=float, default=100.0)
    model_candidate_selection.add_argument("--min-base-adjusted-pnl-per-fold", type=float, default=0.0)
    model_candidate_selection.add_argument("--min-cost-adjusted-pnl-per-fold", type=float, default=0.0)
    model_candidate_selection.add_argument("--max-cost-pnl-drop", type=float, default=1e100)
    model_candidate_selection.add_argument("--max-side-loss-per-fold", type=float, default=1e100)
    model_candidate_selection.add_argument(
        "--max-direction-session-loss-per-fold",
        type=float,
        default=1e100,
        help="maximum allowed loss for any direction:session_regime group in each fold",
    )
    model_candidate_selection.add_argument(
        "--max-combined-regime-loss-per-fold",
        type=float,
        default=1e100,
        help="maximum allowed loss for any combined_regime group in each fold",
    )
    model_candidate_selection.add_argument(
        "--max-direction-combined-regime-loss-per-fold",
        type=float,
        default=1e100,
        help="maximum allowed loss for any direction:combined_regime group in each fold",
    )
    model_candidate_selection.add_argument(
        "--max-predicted-profit-barrier-miss-rate",
        type=float,
        default=1.0,
        help="maximum allowed share of trades below the predicted profit-barrier threshold",
    )
    model_candidate_selection.add_argument(
        "--max-actual-profit-barrier-miss-rate",
        type=float,
        default=1.0,
        help="maximum allowed share of trades whose actual side profit barrier was missed",
    )
    model_candidate_selection.add_argument(
        "--max-profit-barrier-calibration-overestimate",
        type=float,
        default=1.0,
        help="maximum allowed predicted-minus-actual hit rate in any profit-barrier probability bucket",
    )
    model_candidate_selection.add_argument(
        "--max-short-trade-share",
        type=float,
        default=1.0,
        help="maximum allowed short-trade share in any fold",
    )
    model_candidate_selection.add_argument(
        "--max-side-trade-share",
        type=float,
        default=1.0,
        help="maximum allowed dominant side trade share in any fold",
    )
    model_candidate_selection.add_argument(
        "--max-smoothed-actual-profit-barrier-miss-rate",
        type=float,
        default=1.0,
        help="maximum allowed Laplace-smoothed actual profit-barrier miss rate",
    )
    model_candidate_selection.add_argument(
        "--max-smoothed-profit-barrier-calibration-overestimate",
        type=float,
        default=1.0,
        help="maximum allowed Laplace-smoothed profit-barrier calibration overestimate",
    )
    model_candidate_selection.add_argument(
        "--max-direction-error-rate",
        type=float,
        default=1.0,
        help="maximum allowed actual opposite-side-better rate in any fold",
    )
    model_candidate_selection.add_argument(
        "--max-predicted-side-error-rate",
        type=float,
        default=1.0,
        help="maximum allowed predicted best side mismatch rate in any fold",
    )
    model_candidate_selection.add_argument(
        "--max-no-edge-rate",
        type=float,
        default=1.0,
        help="maximum allowed share of trades with non-positive oracle same-side edge",
    )
    model_candidate_selection.add_argument(
        "--max-exit-regret-mean",
        type=float,
        default=1e100,
        help="maximum allowed mean same-side oracle exit regret in any fold",
    )
    model_candidate_selection.add_argument(
        "--max-ev-overestimate-vs-realized-mean",
        type=float,
        default=1e100,
        help="maximum allowed mean predicted EV over realized adjusted PnL in any fold",
    )
    model_candidate_selection.add_argument(
        "--group-loss-penalty-weight",
        type=float,
        default=0.0,
        help=(
            "soft ranking penalty weight applied to the summed worst side/regime loss depth; "
            "0 keeps the historical ranking"
        ),
    )
    model_candidate_selection.add_argument(
        "--diagnostic-penalty-weight",
        type=float,
        default=0.0,
        help=(
            "soft ranking penalty weight for excess direction error, smoothed actual profit-barrier "
            "miss rate, and EV overestimate diagnostics"
        ),
    )
    model_candidate_selection.add_argument(
        "--diagnostic-direction-error-rate-threshold",
        type=float,
        default=1.0,
        help="direction error rate allowed before diagnostic soft penalty applies",
    )
    model_candidate_selection.add_argument(
        "--diagnostic-actual-profit-barrier-miss-rate-threshold",
        type=float,
        default=1.0,
        help="smoothed actual profit-barrier miss rate allowed before diagnostic soft penalty applies",
    )
    model_candidate_selection.add_argument(
        "--diagnostic-ev-overestimate-vs-realized-mean-threshold",
        type=float,
        default=1e100,
        help="mean EV overestimate allowed before diagnostic soft penalty applies",
    )
    model_candidate_selection.add_argument(
        "--diagnostic-direction-error-rate-scale",
        type=float,
        default=100.0,
        help="scale applied to excess direction error rate before diagnostic penalty weight",
    )
    model_candidate_selection.add_argument(
        "--diagnostic-actual-profit-barrier-miss-rate-scale",
        type=float,
        default=100.0,
        help="scale applied to excess smoothed actual profit-barrier miss rate",
    )
    model_candidate_selection.add_argument(
        "--diagnostic-ev-overestimate-vs-realized-mean-scale",
        type=float,
        default=1.0,
        help="scale applied to excess mean EV overestimate",
    )
    model_candidate_selection.add_argument(
        "--candidate-rank-mode",
        default="pnl",
        choices=CANDIDATE_RANK_MODES,
        help=(
            "pnl keeps historical ranking; near_top_risk ranks candidates within the "
            "near-top cost min-PnL tolerance by risk proxy; stress_score also rewards "
            "validation cost/base scenario sum PnL"
        ),
    )
    model_candidate_selection.add_argument(
        "--near-top-cost-pnl-tolerance",
        type=float,
        default=0.0,
        help=(
            "allowed degradation from the best eligible cost min PnL for near_top_risk "
            "and stress_score ranking"
        ),
    )
    model_candidate_selection.add_argument(
        "--near-top-group-loss-weight",
        type=float,
        default=1.0,
        help="weight for summed side/regime loss depth in near_top_risk score",
    )
    model_candidate_selection.add_argument(
        "--near-top-drawdown-weight",
        type=float,
        default=1.0,
        help="weight for max drawdown in near_top_risk score",
    )
    model_candidate_selection.add_argument(
        "--near-top-ev-overestimate-weight",
        type=float,
        default=1.0,
        help="weight for EV overestimate in near_top_risk score",
    )
    model_candidate_selection.add_argument(
        "--near-top-exit-regret-weight",
        type=float,
        default=1.0,
        help="weight for exit regret in near_top_risk score",
    )
    model_candidate_selection.add_argument(
        "--near-top-actual-miss-weight",
        type=float,
        default=100.0,
        help="weight for smoothed actual profit-barrier miss rate in near_top_risk score",
    )
    model_candidate_selection.add_argument(
        "--near-top-side-share-weight",
        type=float,
        default=100.0,
        help="weight for dominant side trade share in near_top_risk score",
    )
    model_candidate_selection.add_argument(
        "--near-top-pnl-stability-weight",
        type=float,
        default=0.0,
        help=(
            "weight for fold-to-fold adjusted-PnL standard deviation in near_top_risk "
            "and stress_score ranking; 0 keeps historical ranking"
        ),
    )
    model_candidate_selection.add_argument(
        "--stress-cost-pnl-sum-reward-weight",
        type=float,
        default=0.0,
        help="reward weight for cost scenario total adjusted PnL sum in stress_score ranking",
    )
    model_candidate_selection.add_argument(
        "--stress-base-pnl-sum-reward-weight",
        type=float,
        default=0.0,
        help="reward weight for base/no-cost total adjusted PnL sum in stress_score ranking",
    )
    model_candidate_selection.add_argument(
        "--plateau-column",
        default="short_entry_threshold_offset",
        choices=SWEEP_KEY_COLUMNS,
    )
    model_candidate_selection.add_argument("--plateau-radius", type=float, default=0.0)
    model_candidate_selection.add_argument("--min-plateau-neighbors", type=int, default=0)
    model_candidate_selection.add_argument("--top-n", type=int, default=10)
    model_candidate_selection.set_defaults(func=handle_model_candidate_selection)

    model_candidate_selection_jackknife = subparsers.add_parser(
        "model-candidate-selection-jackknife",
        help="rerun candidate selection while leaving out one validation fold at a time",
    )
    model_candidate_selection_jackknife.add_argument(
        "--selection-config",
        type=Path,
        required=True,
        help="model-candidate-selection config.json or its run directory",
    )
    model_candidate_selection_jackknife.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/reports/backtests"),
    )
    model_candidate_selection_jackknife.add_argument("--top-n", type=int, default=20)
    model_candidate_selection_jackknife.set_defaults(
        func=handle_model_candidate_selection_jackknife
    )

    model_holdout_audit = subparsers.add_parser(
        "model-holdout-audit",
        help="audit selected model-policy candidates across fixed holdout run artifacts",
    )
    model_holdout_audit.add_argument(
        "--holdout-runs",
        required=True,
        help=(
            "comma-separated model-policy/model-cost-sensitivity run dirs, metrics files, "
            "or parent dirs containing run dirs"
        ),
    )
    model_holdout_audit.add_argument(
        "--validation-summary",
        type=Path,
        help="optional model-candidate-selection or sweep summary CSV to merge by policy keys",
    )
    model_holdout_audit.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/reports/backtests"),
    )
    model_holdout_audit.add_argument("--min-holdout-cases", type=int, default=1)
    model_holdout_audit.add_argument("--min-trades-per-case", type=int, default=1)
    model_holdout_audit.add_argument("--max-forced-exit-rate", type=float, default=1.0)
    model_holdout_audit.add_argument("--max-drawdown", type=float, default=1e100)
    model_holdout_audit.add_argument("--min-adjusted-pnl-per-case", type=float, default=0.0)
    model_holdout_audit.add_argument("--top-n", type=int, default=10)
    model_holdout_audit.set_defaults(func=handle_model_holdout_audit)

    model_trade_exposure = subparsers.add_parser(
        "model-trade-exposure",
        help="aggregate model-policy trade exposure by month, side, and market regime",
    )
    model_trade_exposure.add_argument(
        "--runs",
        required=True,
        help="comma-separated model-policy run dirs, trades.csv files, or parent dirs containing runs",
    )
    model_trade_exposure.add_argument(
        "--long-column",
        default="",
        help="optional prediction column override; defaults to each run config long_column",
    )
    model_trade_exposure.add_argument(
        "--short-column",
        default="",
        help="optional prediction column override; defaults to each run config short_column",
    )
    model_trade_exposure.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/reports/backtests"),
    )
    model_trade_exposure.add_argument("--label", default="model_trade_exposure")
    model_trade_exposure.add_argument("--top-n", type=int, default=3)
    model_trade_exposure.set_defaults(func=handle_model_trade_exposure)

    model_trade_exposure_diagnostics = subparsers.add_parser(
        "model-trade-exposure-diagnostics",
        help="bucket selected trades by exit, EV overestimate, and profit-barrier diagnostics",
    )
    model_trade_exposure_diagnostics.add_argument(
        "--runs",
        default="",
        help="optional comma-separated model-policy run dirs, trades.csv files, or parent dirs",
    )
    model_trade_exposure_diagnostics.add_argument(
        "--trades",
        default="",
        help="optional comma-separated enriched trade CSVs such as walkforward_selected_trades.csv",
    )
    model_trade_exposure_diagnostics.add_argument(
        "--long-column",
        default="",
        help="optional prediction column override when --runs is used",
    )
    model_trade_exposure_diagnostics.add_argument(
        "--short-column",
        default="",
        help="optional prediction column override when --runs is used",
    )
    model_trade_exposure_diagnostics.add_argument(
        "--large-loss-threshold",
        type=float,
        default=-15.0,
    )
    model_trade_exposure_diagnostics.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/reports/backtests"),
    )
    model_trade_exposure_diagnostics.add_argument(
        "--label",
        default="model_trade_exposure_diagnostics",
    )
    model_trade_exposure_diagnostics.add_argument("--top-n", type=int, default=10)
    model_trade_exposure_diagnostics.set_defaults(
        func=handle_model_trade_exposure_diagnostics
    )

    model_trade_context_walkforward_stress = subparsers.add_parser(
        "model-trade-context-walkforward-stress",
        help="build leak-free walk-forward context stress diagnostics for selected trades",
    )
    model_trade_context_walkforward_stress.add_argument(
        "--runs",
        required=True,
        help="comma-separated model-policy run dirs, trades.csv files, or parent dirs containing runs",
    )
    model_trade_context_walkforward_stress.add_argument(
        "--group-columns",
        default="direction,combined_regime",
        help="comma-separated decision-time context columns for rolling selected-trade profiles",
    )
    model_trade_context_walkforward_stress.add_argument(
        "--target-column",
        default="adjusted_pnl",
    )
    model_trade_context_walkforward_stress.add_argument(
        "--raw-prediction-column",
        default="pred_taken_ev",
    )
    model_trade_context_walkforward_stress.add_argument(
        "--long-column",
        default="",
        help="optional prediction column override; defaults to each run config long_column",
    )
    model_trade_context_walkforward_stress.add_argument(
        "--short-column",
        default="",
        help="optional prediction column override; defaults to each run config short_column",
    )
    model_trade_context_walkforward_stress.add_argument(
        "--downside-threshold",
        type=float,
        default=0.0,
    )
    model_trade_context_walkforward_stress.add_argument(
        "--large-downside-threshold",
        type=float,
        default=-15.0,
    )
    model_trade_context_walkforward_stress.add_argument(
        "--holdout-month-count",
        type=int,
        default=1,
        help="number of immediately prior months used as pseudo-holdout profile",
    )
    model_trade_context_walkforward_stress.add_argument(
        "--min-validation-months",
        type=int,
        default=1,
        help="minimum older months required before the pseudo-holdout window",
    )
    model_trade_context_walkforward_stress.add_argument(
        "--min-validation-support",
        type=int,
        default=1,
        help="minimum prior validation trades required for a context penalty",
    )
    model_trade_context_walkforward_stress.add_argument(
        "--min-holdout-support",
        type=int,
        default=1,
        help="minimum prior pseudo-holdout trades required for a context penalty",
    )
    model_trade_context_walkforward_stress.add_argument(
        "--min-prior-support",
        type=int,
        default=1,
        help="minimum all-prior trades required for the prior-context mean floor",
    )
    model_trade_context_walkforward_stress.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/reports/backtests"),
    )
    model_trade_context_walkforward_stress.add_argument(
        "--label",
        default="model_trade_context_walkforward_stress",
    )
    model_trade_context_walkforward_stress.add_argument("--top-n", type=int, default=20)
    model_trade_context_walkforward_stress.set_defaults(
        func=handle_model_trade_context_walkforward_stress
    )

    model_trade_delta = subparsers.add_parser(
        "model-trade-delta",
        help="compare base and candidate model-policy trades and summarize added/removed exposure",
    )
    model_trade_delta.add_argument(
        "--base-runs",
        required=True,
        help="comma-separated base model-policy run dirs, trades.csv files, or parent dirs",
    )
    model_trade_delta.add_argument(
        "--candidate-runs",
        required=True,
        help="comma-separated candidate model-policy run dirs, trades.csv files, or parent dirs",
    )
    model_trade_delta.add_argument(
        "--gate-long-quality-column",
        default="",
        help="optional gate quality long column; defaults to each candidate run config",
    )
    model_trade_delta.add_argument(
        "--gate-short-quality-column",
        default="",
        help="optional gate quality short column; defaults to each candidate run config",
    )
    model_trade_delta.add_argument(
        "--stateful-example-target",
        choices=("stateful_net", "stateful_positive_cost", "candidate_pnl"),
        default="stateful_net",
        help="target column used in stateful_candidate_examples.csv",
    )
    model_trade_delta.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/reports/backtests"),
    )
    model_trade_delta.add_argument("--label", default="model_trade_delta")
    model_trade_delta.add_argument("--top-n", type=int, default=5)
    model_trade_delta.set_defaults(func=handle_model_trade_delta)

    stateful_examples_drift = subparsers.add_parser(
        "stateful-examples-drift",
        help="compare validation and holdout stateful_candidate_examples by context",
    )
    stateful_examples_drift.add_argument(
        "--validation-examples",
        required=True,
        help="comma-separated stateful_candidate_examples.csv files, run dirs, or parent dirs",
    )
    stateful_examples_drift.add_argument(
        "--holdout-examples",
        required=True,
        help="comma-separated stateful_candidate_examples.csv files, run dirs, or parent dirs",
    )
    stateful_examples_drift.add_argument(
        "--group-columns",
        default="candidate_side,combined_regime",
        help="comma-separated decision-time context columns for split drift",
    )
    stateful_examples_drift.add_argument("--target-column", default="target")
    stateful_examples_drift.add_argument("--raw-prediction-column", default="pred_taken_ev")
    stateful_examples_drift.add_argument("--downside-threshold", type=float, default=0.0)
    stateful_examples_drift.add_argument("--large-downside-threshold", type=float, default=-15.0)
    stateful_examples_drift.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/reports/backtests"),
    )
    stateful_examples_drift.add_argument("--label", default="stateful_examples_drift")
    stateful_examples_drift.add_argument("--top-n", type=int, default=20)
    stateful_examples_drift.set_defaults(func=handle_stateful_examples_drift)

    stateful_examples_walkforward_stress = subparsers.add_parser(
        "stateful-examples-walkforward-stress",
        help="build leak-free walk-forward stress targets for stateful examples",
    )
    stateful_examples_walkforward_stress.add_argument(
        "--examples",
        required=True,
        help="comma-separated stateful_candidate_examples.csv files, run dirs, or parent dirs",
    )
    stateful_examples_walkforward_stress.add_argument(
        "--group-columns",
        default="candidate_side,combined_regime",
        help="comma-separated decision-time context columns for rolling stress profiles",
    )
    stateful_examples_walkforward_stress.add_argument("--target-column", default="target")
    stateful_examples_walkforward_stress.add_argument(
        "--raw-prediction-column",
        default="pred_taken_ev",
    )
    stateful_examples_walkforward_stress.add_argument(
        "--downside-threshold",
        type=float,
        default=0.0,
    )
    stateful_examples_walkforward_stress.add_argument(
        "--large-downside-threshold",
        type=float,
        default=-15.0,
    )
    stateful_examples_walkforward_stress.add_argument(
        "--holdout-month-count",
        type=int,
        default=1,
        help="number of immediately prior months used as pseudo-holdout profile",
    )
    stateful_examples_walkforward_stress.add_argument(
        "--min-validation-months",
        type=int,
        default=1,
        help="minimum older months required before the pseudo-holdout window",
    )
    stateful_examples_walkforward_stress.add_argument(
        "--min-validation-support",
        type=int,
        default=1,
        help="minimum prior validation examples required for a context penalty",
    )
    stateful_examples_walkforward_stress.add_argument(
        "--min-holdout-support",
        type=int,
        default=1,
        help="minimum prior pseudo-holdout examples required for a context penalty",
    )
    stateful_examples_walkforward_stress.add_argument(
        "--min-prior-support",
        type=int,
        default=1,
        help="minimum all-prior examples required for the prior-context mean floor",
    )
    stateful_examples_walkforward_stress.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/reports/backtests"),
    )
    stateful_examples_walkforward_stress.add_argument(
        "--label",
        default="stateful_examples_walkforward_stress",
    )
    stateful_examples_walkforward_stress.add_argument("--top-n", type=int, default=20)
    stateful_examples_walkforward_stress.set_defaults(
        func=handle_stateful_examples_walkforward_stress
    )

    model_trade_delta_preflight = subparsers.add_parser(
        "model-trade-delta-preflight",
        help="audit validation and holdout model-trade-delta runs before adopting a candidate",
    )
    model_trade_delta_preflight.add_argument(
        "--validation-deltas",
        required=True,
        help="comma-separated model-trade-delta run dirs or parent dirs for validation cases",
    )
    model_trade_delta_preflight.add_argument(
        "--holdout-deltas",
        required=True,
        help="comma-separated model-trade-delta run dirs or parent dirs for holdout cases",
    )
    model_trade_delta_preflight.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/reports/backtests"),
    )
    model_trade_delta_preflight.add_argument("--label", default="model_trade_delta_preflight")
    model_trade_delta_preflight.add_argument("--top-n", type=int, default=20)
    model_trade_delta_preflight.add_argument("--min-validation-cases", type=int, default=1)
    model_trade_delta_preflight.add_argument("--min-holdout-cases", type=int, default=1)
    model_trade_delta_preflight.add_argument("--min-validation-pnl-delta", type=float, default=0.0)
    model_trade_delta_preflight.add_argument("--min-holdout-pnl-delta", type=float, default=0.0)
    model_trade_delta_preflight.add_argument(
        "--min-validation-month-pnl-delta",
        type=float,
        default=-float("inf"),
    )
    model_trade_delta_preflight.add_argument(
        "--min-holdout-month-pnl-delta",
        type=float,
        default=0.0,
    )
    model_trade_delta_preflight.add_argument(
        "--min-validation-stateful-target-mean",
        type=float,
        default=-float("inf"),
    )
    model_trade_delta_preflight.add_argument(
        "--min-holdout-stateful-target-mean",
        type=float,
        default=0.0,
    )
    model_trade_delta_preflight.set_defaults(func=handle_model_trade_delta_preflight)

    model_trade_delta_drift_stability = subparsers.add_parser(
        "model-trade-delta-drift-stability",
        help="summarize repeated validation-positive holdout-negative drift groups",
    )
    model_trade_delta_drift_stability.add_argument(
        "--preflight-runs",
        required=True,
        help="comma-separated model-trade-delta-preflight run dirs with group drift CSVs",
    )
    model_trade_delta_drift_stability.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/reports/backtests"),
    )
    model_trade_delta_drift_stability.add_argument(
        "--label",
        default="model_trade_delta_drift_stability",
    )
    model_trade_delta_drift_stability.add_argument("--top-n", type=int, default=20)
    model_trade_delta_drift_stability.set_defaults(
        func=handle_model_trade_delta_drift_stability
    )

    analyze_trades = subparsers.add_parser(
        "analyze-trades",
        help="join trades.csv with saved predictions and diagnose failure modes",
    )
    analyze_trades.add_argument("--trades", type=Path, required=True)
    analyze_trades.add_argument("--predictions", type=Path, required=True)
    analyze_trades.add_argument("--long-column", default="pred_long_best_adjusted_pnl")
    analyze_trades.add_argument("--short-column", default="pred_short_best_adjusted_pnl")
    analyze_trades.add_argument("--output-dir", type=Path, default=Path("data/reports/backtests"))
    analyze_trades.add_argument("--label", default="trade_analysis")
    analyze_trades.add_argument("--top-n", type=int, default=20)
    analyze_trades.set_defaults(func=handle_analyze_trades)
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
