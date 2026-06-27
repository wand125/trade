from __future__ import annotations

import argparse
import json
import random
import sys
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

from trade_data.regime import REGIME_COLUMNS


DIRECTION_LABELS = {
    1: "long",
    -1: "short",
}

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
    "exit_threshold",
    "side_margin",
    "risk_penalty",
    "max_wait_regret",
    "min_entry_rank",
    "require_profit_barrier",
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
    exit_threshold: float = 0.0
    side_margin: float = 0.0
    long_column: str = "pred_long_best_adjusted_pnl"
    short_column: str = "pred_short_best_adjusted_pnl"
    long_risk_column: str = "pred_long_max_adverse_pnl"
    short_risk_column: str = "pred_short_max_adverse_pnl"
    risk_penalty: float = 0.0
    long_holding_column: str = "pred_long_best_holding_minutes"
    short_holding_column: str = "pred_short_best_holding_minutes"
    min_predicted_hold_minutes: float = 1.0
    max_predicted_hold_minutes: float = 1440.0
    long_wait_regret_column: str = "pred_long_wait_regret"
    short_wait_regret_column: str = "pred_short_wait_regret"
    long_entry_rank_column: str = "pred_long_entry_local_rank"
    short_entry_rank_column: str = "pred_short_entry_local_rank"
    long_profit_barrier_column: str = "pred_long_profit_barrier_hit"
    short_profit_barrier_column: str = "pred_short_profit_barrier_hit"
    max_wait_regret: float = float("inf")
    min_entry_rank: float = 0.0
    require_profit_barrier: bool = False
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
    return ["stateful_ev", "stateless_ev", "timed_ev"]


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


def read_prediction_frame(path: Path, config: ModelPolicyConfig) -> pd.DataFrame:
    columns = ["decision_timestamp", config.long_column, config.short_column]
    if config.risk_penalty > 0:
        columns.extend([config.long_risk_column, config.short_risk_column])
    if config.policy == "timed_ev":
        columns.extend([config.long_holding_column, config.short_holding_column])
    if np.isfinite(config.max_wait_regret):
        columns.extend([config.long_wait_regret_column, config.short_wait_regret_column])
    if config.min_entry_rank > 0:
        columns.extend([config.long_entry_rank_column, config.short_entry_rank_column])
    if config.require_profit_barrier:
        columns.extend([config.long_profit_barrier_column, config.short_profit_barrier_column])
    columns.extend([column for column, _ in blocked_regime_columns(config)])
    columns = list(dict.fromkeys(columns))
    predictions = pd.read_parquet(path, columns=columns)
    missing = sorted(set(columns) - set(predictions.columns))
    if missing:
        raise ValueError(f"{path} is missing columns: {', '.join(missing)}")
    predictions = predictions.dropna(subset=columns).sort_values("decision_timestamp")
    if predictions["decision_timestamp"].dt.tz is None:
        predictions["decision_timestamp"] = predictions["decision_timestamp"].dt.tz_localize("UTC")
    else:
        predictions["decision_timestamp"] = predictions["decision_timestamp"].dt.tz_convert("UTC")
    duplicated = predictions["decision_timestamp"].duplicated()
    if duplicated.any():
        duplicated_count = int(duplicated.sum())
        raise ValueError(f"{path} has duplicated decision_timestamp values: {duplicated_count}")
    return predictions.reset_index(drop=True)


def blocked_regime_columns(config: ModelPolicyConfig) -> list[tuple[str, tuple[str, ...]]]:
    return [
        (column, tuple(getattr(config, field)))
        for field, column in REGIME_BLOCK_FIELDS
        if getattr(config, field)
    ]


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

    prediction_index = predictions.set_index("decision_timestamp")
    aligned = prediction_index[[config.long_column, config.short_column]].reindex(df["timestamp"])
    long_ev = aligned[config.long_column].reset_index(drop=True).astype(float)
    short_ev = aligned[config.short_column].reset_index(drop=True).astype(float)
    if config.risk_penalty > 0:
        risk_aligned = prediction_index[[config.long_risk_column, config.short_risk_column]].reindex(
            df["timestamp"]
        )
        long_risk = risk_aligned[config.long_risk_column].reset_index(drop=True).astype(float)
        short_risk = risk_aligned[config.short_risk_column].reset_index(drop=True).astype(float)
        long_ev = long_ev - config.risk_penalty * (-long_risk).clip(lower=0)
        short_ev = short_ev - config.risk_penalty * (-short_risk).clip(lower=0)
    long_holding = None
    short_holding = None
    if config.policy == "timed_ev":
        holding_aligned = prediction_index[[config.long_holding_column, config.short_holding_column]].reindex(
            df["timestamp"]
        )
        long_holding = holding_aligned[config.long_holding_column].reset_index(drop=True).astype(float)
        short_holding = holding_aligned[config.short_holding_column].reset_index(drop=True).astype(float)
    best_side = pd.Series(0, index=df.index, dtype="int8")
    best_score = pd.concat([long_ev, short_ev], axis=1).max(axis=1)
    side_gap = (long_ev - short_ev).abs()
    valid_prediction = long_ev.notna() & short_ev.notna()
    best_side.iloc[(valid_prediction & (long_ev >= short_ev)).to_numpy()] = 1
    best_side.iloc[(valid_prediction & (long_ev < short_ev)).to_numpy()] = -1
    quality_ok = pd.Series(True, index=df.index)
    if np.isfinite(config.max_wait_regret):
        wait_aligned = prediction_index[
            [config.long_wait_regret_column, config.short_wait_regret_column]
        ].reindex(df["timestamp"])
        long_wait = wait_aligned[config.long_wait_regret_column].reset_index(drop=True).astype(float)
        short_wait = wait_aligned[config.short_wait_regret_column].reset_index(drop=True).astype(float)
        side_wait = pd.Series(np.where(best_side == 1, long_wait, short_wait), index=df.index)
        quality_ok &= side_wait.notna() & (side_wait <= config.max_wait_regret)
    if config.min_entry_rank > 0:
        rank_aligned = prediction_index[
            [config.long_entry_rank_column, config.short_entry_rank_column]
        ].reindex(df["timestamp"])
        long_rank = rank_aligned[config.long_entry_rank_column].reset_index(drop=True).astype(float)
        short_rank = rank_aligned[config.short_entry_rank_column].reset_index(drop=True).astype(float)
        side_rank = pd.Series(np.where(best_side == 1, long_rank, short_rank), index=df.index)
        quality_ok &= side_rank.notna() & (side_rank >= config.min_entry_rank)
    if config.require_profit_barrier:
        barrier_aligned = prediction_index[
            [config.long_profit_barrier_column, config.short_profit_barrier_column]
        ].reindex(df["timestamp"])
        long_barrier = barrier_aligned[config.long_profit_barrier_column].reset_index(drop=True).astype(float)
        short_barrier = barrier_aligned[config.short_profit_barrier_column].reset_index(drop=True).astype(float)
        side_barrier = pd.Series(np.where(best_side == 1, long_barrier, short_barrier), index=df.index)
        quality_ok &= side_barrier.notna() & (side_barrier >= 0.5)
    for column, blocked_values in blocked_regime_columns(config):
        regime_aligned = prediction_index[[column]].reindex(df["timestamp"])
        regime_values = pd.Series(
            regime_aligned[column].reset_index(drop=True).astype("string").to_numpy(),
            index=df.index,
        )
        quality_ok &= regime_values.notna() & ~regime_values.isin(set(blocked_values))

    if config.policy == "stateless_ev":
        enter = (
            valid_prediction
            & quality_ok
            & (best_score > config.entry_threshold)
            & (side_gap >= config.side_margin)
        )
        signal = pd.Series(0, index=df.index, dtype="int8")
        signal.iloc[enter.to_numpy()] = best_side.iloc[enter.to_numpy()]
        return signal

    current = 0
    planned_exit_timestamp: pd.Timestamp | None = None
    values: list[int] = []
    long_values = long_ev.tolist()
    short_values = short_ev.tolist()
    timestamps = df["timestamp"].reset_index(drop=True).tolist()
    long_holding_values = [] if long_holding is None else long_holding.tolist()
    short_holding_values = [] if short_holding is None else short_holding.tolist()
    quality_ok_values = quality_ok.tolist()
    for idx, has_prediction in enumerate(valid_prediction.tolist()):
        if not has_prediction:
            current = 0
            planned_exit_timestamp = None
            values.append(current)
            continue

        decision_timestamp = timestamps[idx]
        if config.policy == "timed_ev" and current != 0 and planned_exit_timestamp is not None:
            if decision_timestamp >= planned_exit_timestamp:
                current = 0
                planned_exit_timestamp = None
                values.append(current)
                continue

        long_value = float(long_values[idx])
        short_value = float(short_values[idx])
        if long_value >= short_value:
            candidate_side = 1
            candidate_score = long_value
            candidate_gap = long_value - short_value
        else:
            candidate_side = -1
            candidate_score = short_value
            candidate_gap = short_value - long_value

        if current == 0:
            if (
                quality_ok_values[idx]
                and candidate_score > config.entry_threshold
                and candidate_gap >= config.side_margin
            ):
                current = candidate_side
                if config.policy == "timed_ev":
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
            should_exit = current_score < config.exit_threshold
            should_flip = (
                opposite_score > config.entry_threshold
                and opposite_score > current_score + config.side_margin
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
) -> list[Trade]:
    if len(df) != len(desired_position):
        raise ValueError("df and desired_position must have the same length")
    if config.execution_delay_bars < 0:
        raise ValueError("execution_delay_bars must be non-negative")
    if len(df) < 2:
        return []
    if len(df) < 2 + config.execution_delay_bars:
        return []

    timestamps = df["timestamp"].tolist()
    opens = df["open"].astype(float).tolist()
    signals = desired_position.fillna(0).astype("int8").tolist()

    position: Position | None = None
    trades: list[Trade] = []

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
                trades.append(
                    close_position(
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
                )
                position = None
                continue

        if position is None and config.evaluation_start <= execution_timestamp < config.evaluation_end:
            if desired in (-1, 1):
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
        "long_trade_count": int((trades["direction"] == "long").sum()),
        "short_trade_count": int((trades["direction"] == "short").sum()),
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


def parse_csv_strings(value: str) -> list[str]:
    values = [part.strip() for part in value.split(",") if part.strip()]
    if not values:
        raise argparse.ArgumentTypeError("at least one value is required")
    return values


def parse_optional_csv_strings(value: str | None) -> tuple[str, ...]:
    if value is None:
        return ()
    return tuple(dict.fromkeys(part.strip() for part in value.split(",") if part.strip()))


def regime_values_to_string(values: Iterable[str]) -> str:
    return ",".join(values)


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
    analysis_columns = [*ANALYSIS_PREDICTION_COLUMNS, long_column, short_column]
    columns = list(dict.fromkeys(column for column in analysis_columns if column in predictions.columns))
    predictions = predictions[columns].copy()
    predictions["pred_long_best_adjusted_pnl"] = predictions[long_column]
    predictions["pred_short_best_adjusted_pnl"] = predictions[short_column]
    return predictions


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


def enrich_trades_with_predictions(trades: pd.DataFrame, predictions: pd.DataFrame) -> pd.DataFrame:
    if trades.empty:
        output = trades.copy()
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

    prediction_columns = [column for column in ANALYSIS_PREDICTION_COLUMNS if column in predictions.columns]
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

    for column in ANALYSIS_PREDICTION_COLUMNS:
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
        }
    adjusted = enriched["adjusted_pnl"].astype(float)
    raw = enriched["raw_pnl"].astype(float)
    return {
        "trade_count": int(len(enriched)),
        "matched_prediction_count": int(enriched["matched_prediction"].sum()),
        "total_adjusted_pnl": float(adjusted.sum()),
        "total_raw_pnl": float(raw.sum()),
        "win_rate": float((adjusted > 0).mean()),
        "long_adjusted_pnl": float(enriched.loc[enriched["is_long"], "adjusted_pnl"].sum()),
        "short_adjusted_pnl": float(enriched.loc[enriched["is_short"], "adjusted_pnl"].sum()),
        "direction_error_rate": float(numeric_indicator(enriched["direction_error"]).mean()),
        "no_edge_rate": float(numeric_indicator(enriched["no_edge_entry"]).mean()),
        "predicted_side_error_rate": float(numeric_indicator(enriched["predicted_side_error"]).mean()),
        "exit_regret_sum": float(enriched["exit_regret"].sum()),
        "best_side_regret_sum": float(enriched["best_side_regret"].sum()),
        "ev_overestimate_vs_oracle_mean": float(enriched["ev_overestimate_vs_oracle"].mean()),
        "ev_overestimate_vs_realized_mean": float(enriched["ev_overestimate_vs_realized"].mean()),
        "avg_holding_minutes": float(enriched["holding_minutes"].mean()),
    }


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
        exit_threshold=args.exit_threshold,
        side_margin=args.side_margin,
        long_column=args.long_column,
        short_column=args.short_column,
        long_risk_column=args.long_risk_column,
        short_risk_column=args.short_risk_column,
        risk_penalty=args.risk_penalty,
        long_holding_column=args.long_holding_column,
        short_holding_column=args.short_holding_column,
        min_predicted_hold_minutes=args.min_predicted_hold_minutes,
        max_predicted_hold_minutes=args.max_predicted_hold_minutes,
        long_wait_regret_column=args.long_wait_regret_column,
        short_wait_regret_column=args.short_wait_regret_column,
        long_entry_rank_column=args.long_entry_rank_column,
        short_entry_rank_column=args.short_entry_rank_column,
        long_profit_barrier_column=args.long_profit_barrier_column,
        short_profit_barrier_column=args.short_profit_barrier_column,
        max_wait_regret=args.max_wait_regret,
        min_entry_rank=args.min_entry_rank,
        require_profit_barrier=args.require_profit_barrier,
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
) -> tuple[dict[str, object], pd.DataFrame, pd.DataFrame, pd.Series]:
    predictions = read_prediction_frame(model_policy_config.predictions, model_policy_config)
    signal = model_signal_from_predictions(df, predictions, model_policy_config)
    trades = trades_to_frame(run_backtest(df, signal, backtest_config))
    strategy_name = f"model_{model_policy_config.policy}"
    metrics = summarize_trades(trades, backtest_config, strategy_name)
    metrics["prediction_rows"] = int(len(predictions))
    metrics["signal_long_count"] = int((signal == 1).sum())
    metrics["signal_short_count"] = int((signal == -1).sum())
    metrics["signal_flat_count"] = int((signal == 0).sum())
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
    parser.add_argument("--exit-threshold", type=float, default=0.0)
    parser.add_argument("--side-margin", type=float, default=0.0)
    parser.add_argument("--long-column", default="pred_long_best_adjusted_pnl")
    parser.add_argument("--short-column", default="pred_short_best_adjusted_pnl")
    parser.add_argument("--long-risk-column", default="pred_long_max_adverse_pnl")
    parser.add_argument("--short-risk-column", default="pred_short_max_adverse_pnl")
    parser.add_argument("--risk-penalty", type=float, default=0.0)
    parser.add_argument("--long-holding-column", default="pred_long_best_holding_minutes")
    parser.add_argument("--short-holding-column", default="pred_short_best_holding_minutes")
    parser.add_argument("--min-predicted-hold-minutes", type=float, default=1.0)
    parser.add_argument("--max-predicted-hold-minutes", type=float, default=1440.0)
    parser.add_argument("--long-wait-regret-column", default="pred_long_wait_regret")
    parser.add_argument("--short-wait-regret-column", default="pred_short_wait_regret")
    parser.add_argument("--long-entry-rank-column", default="pred_long_entry_local_rank")
    parser.add_argument("--short-entry-rank-column", default="pred_short_entry_local_rank")
    parser.add_argument("--long-profit-barrier-column", default="pred_long_profit_barrier_hit")
    parser.add_argument("--short-profit-barrier-column", default="pred_short_profit_barrier_hit")
    parser.add_argument("--max-wait-regret", type=float, default=float("inf"))
    parser.add_argument("--min-entry-rank", type=float, default=0.0)
    parser.add_argument("--require-profit-barrier", action="store_true")
    add_regime_gate_args(parser)


def handle_model_sweep(args: argparse.Namespace) -> int:
    df, backtest_config = prepare_data_and_config(args)
    policies = parse_csv_strings(args.policies)
    unknown = sorted(set(policies) - set(available_model_policies()))
    if unknown:
        raise SystemExit(f"unknown model policies: {', '.join(unknown)}")
    entry_thresholds = parse_csv_floats(args.entry_thresholds)
    exit_thresholds = parse_csv_floats(args.exit_thresholds)
    side_margins = parse_csv_floats(args.side_margins)
    risk_penalties = parse_csv_floats(args.risk_penalties)
    max_wait_regrets = parse_csv_floats(args.max_wait_regrets)
    min_entry_ranks = parse_csv_floats(args.min_entry_ranks)
    require_profit_barriers = parse_csv_bools(args.require_profit_barriers)
    regime_blocks = regime_blocks_from_args(args)

    run_dir = make_run_dir(args.output_dir, f"model_sweep_{args.month}")
    rows: list[dict[str, object]] = []
    for policy in policies:
        policy_exit_thresholds = exit_thresholds if policy == "stateful_ev" else [0.0]
        for entry_threshold in entry_thresholds:
            for exit_threshold in policy_exit_thresholds:
                for side_margin in side_margins:
                    for risk_penalty in risk_penalties:
                        for max_wait_regret in max_wait_regrets:
                            for min_entry_rank in min_entry_ranks:
                                for require_profit_barrier in require_profit_barriers:
                                    model_policy_config = ModelPolicyConfig(
                                        predictions=args.predictions,
                                        policy=policy,
                                        entry_threshold=entry_threshold,
                                        exit_threshold=exit_threshold,
                                        side_margin=side_margin,
                                        long_column=args.long_column,
                                        short_column=args.short_column,
                                        long_risk_column=args.long_risk_column,
                                        short_risk_column=args.short_risk_column,
                                        risk_penalty=risk_penalty,
                                        long_holding_column=args.long_holding_column,
                                        short_holding_column=args.short_holding_column,
                                        min_predicted_hold_minutes=args.min_predicted_hold_minutes,
                                        max_predicted_hold_minutes=args.max_predicted_hold_minutes,
                                        long_wait_regret_column=args.long_wait_regret_column,
                                        short_wait_regret_column=args.short_wait_regret_column,
                                        long_entry_rank_column=args.long_entry_rank_column,
                                        short_entry_rank_column=args.short_entry_rank_column,
                                        long_profit_barrier_column=args.long_profit_barrier_column,
                                        short_profit_barrier_column=args.short_profit_barrier_column,
                                        max_wait_regret=max_wait_regret,
                                        min_entry_rank=min_entry_rank,
                                        require_profit_barrier=require_profit_barrier,
                                        **regime_blocks,
                                    )
                                    metrics, _, _, _ = run_model_policy(
                                        df,
                                        backtest_config,
                                        model_policy_config,
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
                                        "exit_threshold": exit_threshold,
                                        "side_margin": side_margin,
                                        "risk_penalty": risk_penalty,
                                        "max_wait_regret": max_wait_regret,
                                        "min_entry_rank": min_entry_rank,
                                        "require_profit_barrier": require_profit_barrier,
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
        "exit_thresholds": exit_thresholds,
        "side_margins": side_margins,
        "risk_penalties": risk_penalties,
        "max_wait_regrets": max_wait_regrets,
        "min_entry_ranks": min_entry_ranks,
        "require_profit_barriers": require_profit_barriers,
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
        "min_predicted_hold_minutes": args.min_predicted_hold_minutes,
        "max_predicted_hold_minutes": args.max_predicted_hold_minutes,
        "long_wait_regret_column": args.long_wait_regret_column,
        "short_wait_regret_column": args.short_wait_regret_column,
        "long_entry_rank_column": args.long_entry_rank_column,
        "short_entry_rank_column": args.short_entry_rank_column,
        "long_profit_barrier_column": args.long_profit_barrier_column,
        "short_profit_barrier_column": args.short_profit_barrier_column,
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
    if "max_wait_regret" not in output.columns:
        output["max_wait_regret"] = float("inf")
    if "min_entry_rank" not in output.columns:
        output["min_entry_rank"] = 0.0
    if "require_profit_barrier" not in output.columns:
        output["require_profit_barrier"] = False
    for field, _ in REGIME_BLOCK_FIELDS:
        if field not in output.columns:
            output[field] = ""
    if "forced_exit_rate" not in output.columns:
        trade_count = output["trade_count"].replace(0, np.nan)
        output["forced_exit_rate"] = (output["forced_exit_count"] / trade_count).fillna(0.0)
    output["sweep_source"] = source

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
        "exit_threshold",
        "side_margin",
        "risk_penalty",
        "max_wait_regret",
        "min_entry_rank",
        "total_adjusted_pnl",
        "total_raw_pnl",
        "trade_count",
        "win_rate",
        "max_drawdown",
        "forced_exit_rate",
        "forced_exit_count",
    ]
    for column in numeric_columns:
        output[column] = pd.to_numeric(output[column])
    if output["require_profit_barrier"].dtype == object:
        output["require_profit_barrier"] = output["require_profit_barrier"].map(
            lambda value: str(value).strip().lower() in {"1", "true", "yes", "y"}
        )
    else:
        output["require_profit_barrier"] = output["require_profit_barrier"].astype(bool)
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
    )
    metrics["fold_eligible"] = (
        (metrics["trade_count"] >= min_trades_per_fold)
        & (metrics["forced_exit_rate"] <= max_forced_exit_rate)
        & (metrics["max_drawdown"] <= max_drawdown)
        & (metrics["total_adjusted_pnl"] >= min_adjusted_pnl_per_fold)
    )

    grouped = metrics.groupby(SWEEP_KEY_COLUMNS, dropna=False)
    summary = grouped.agg(
        fold_count=("sweep_source", "nunique"),
        eligible_fold_count=("fold_eligible", "sum"),
        total_adjusted_pnl_mean=("total_adjusted_pnl", "mean"),
        total_adjusted_pnl_median=("total_adjusted_pnl", "median"),
        total_adjusted_pnl_min=("total_adjusted_pnl", "min"),
        total_adjusted_pnl_sum=("total_adjusted_pnl", "sum"),
        total_raw_pnl_mean=("total_raw_pnl", "mean"),
        total_raw_pnl_min=("total_raw_pnl", "min"),
        trade_count_mean=("trade_count", "mean"),
        trade_count_min=("trade_count", "min"),
        win_rate_mean=("win_rate", "mean"),
        max_drawdown_mean=("max_drawdown", "mean"),
        max_drawdown_max=("max_drawdown", "max"),
        forced_exit_rate_mean=("forced_exit_rate", "mean"),
        forced_exit_rate_max=("forced_exit_rate", "max"),
        forced_exit_count_sum=("forced_exit_count", "sum"),
    ).reset_index()
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


def read_sweep_frames(paths: list[Path]) -> list[pd.DataFrame]:
    frames: list[pd.DataFrame] = []
    for path in paths:
        frame = pd.read_csv(path)
        frames.append(normalize_sweep_metrics(frame, str(path)))
    return frames


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
    model_sweep.add_argument("--exit-thresholds", default="-5,0,5,10")
    model_sweep.add_argument("--side-margins", default="0,5,10")
    model_sweep.add_argument("--risk-penalties", default="0")
    model_sweep.add_argument("--max-wait-regrets", default="inf")
    model_sweep.add_argument("--min-entry-ranks", default="0")
    model_sweep.add_argument("--require-profit-barriers", default="false")
    model_sweep.add_argument("--min-trades", type=int, default=0)
    model_sweep.add_argument("--max-forced-exit-rate", type=float, default=1.0)
    model_sweep.add_argument("--max-drawdown", type=float, default=float("inf"))
    model_sweep.add_argument("--long-column", default="pred_long_best_adjusted_pnl")
    model_sweep.add_argument("--short-column", default="pred_short_best_adjusted_pnl")
    model_sweep.add_argument("--long-risk-column", default="pred_long_max_adverse_pnl")
    model_sweep.add_argument("--short-risk-column", default="pred_short_max_adverse_pnl")
    model_sweep.add_argument("--long-holding-column", default="pred_long_best_holding_minutes")
    model_sweep.add_argument("--short-holding-column", default="pred_short_best_holding_minutes")
    model_sweep.add_argument("--min-predicted-hold-minutes", type=float, default=1.0)
    model_sweep.add_argument("--max-predicted-hold-minutes", type=float, default=1440.0)
    model_sweep.add_argument("--long-wait-regret-column", default="pred_long_wait_regret")
    model_sweep.add_argument("--short-wait-regret-column", default="pred_short_wait_regret")
    model_sweep.add_argument("--long-entry-rank-column", default="pred_long_entry_local_rank")
    model_sweep.add_argument("--short-entry-rank-column", default="pred_short_entry_local_rank")
    model_sweep.add_argument("--long-profit-barrier-column", default="pred_long_profit_barrier_hit")
    model_sweep.add_argument("--short-profit-barrier-column", default="pred_short_profit_barrier_hit")
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
