from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

from trade_data.backtest import adjusted_pnl, compute_rsi, month_bounds, read_ohlcv, slice_for_month
from trade_data.regime import REGIME_CATEGORY_COLUMNS, REGIME_NUMERIC_COLUMNS, add_regime_columns


BASE_FEATURE_COLUMNS = [
    "ret_1",
    "ret_5",
    "ret_15",
    "ret_60",
    "diff_1",
    "diff_2",
    "hl_range",
    "oc_body",
    "upper_wick",
    "lower_wick",
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
]

ROLLING_WINDOWS = [15, 60, 240]
FFT_WINDOWS = [64, 256]
EXIT_FIXED_HORIZON_MINUTES = [60, 240, 720]
PROFIT_BARRIER_HORIZON_MINUTES = EXIT_FIXED_HORIZON_MINUTES
EXIT_EVENT_TIME = 0
EXIT_EVENT_PROFIT = 1
EXIT_EVENT_LOSS = 2


@dataclass(frozen=True)
class DatasetConfig:
    month: str
    horizon_hours: float
    warmup_days: int
    post_days: int
    min_adjusted_edge: float
    profit_multiplier: float
    loss_multiplier: float
    include_fft: bool
    quantile_bins: int
    entry_timing_lookahead_minutes: int = 60


def log_returns(close: pd.Series, periods: int = 1) -> pd.Series:
    return np.log(close / close.shift(periods))


def build_features(df: pd.DataFrame, include_fft: bool = True) -> tuple[pd.DataFrame, list[str]]:
    features = pd.DataFrame(index=df.index)
    close = df["close"].astype(float)
    open_ = df["open"].astype(float)
    high = df["high"].astype(float)
    low = df["low"].astype(float)

    features["ret_1"] = log_returns(close, 1)
    features["ret_5"] = log_returns(close, 5)
    features["ret_15"] = log_returns(close, 15)
    features["ret_60"] = log_returns(close, 60)
    features["diff_1"] = close.diff()
    features["diff_2"] = close.diff().diff()
    features["hl_range"] = high - low
    features["oc_body"] = close - open_
    features["upper_wick"] = high - pd.concat([open_, close], axis=1).max(axis=1)
    features["lower_wick"] = pd.concat([open_, close], axis=1).min(axis=1) - low
    features["gap_minutes"] = df["timestamp"].diff() / pd.Timedelta(minutes=1)
    features["gap_flag"] = (features["gap_minutes"] > 5).astype("float64")
    features["rsi_14"] = compute_rsi(close, 14)

    ema_12 = close.ewm(span=12, adjust=False, min_periods=12).mean()
    ema_26 = close.ewm(span=26, adjust=False, min_periods=26).mean()
    features["ema_12_dist"] = close - ema_12
    features["ema_26_dist"] = close - ema_26
    features["ema_12_26"] = ema_12 - ema_26

    timestamp = df["timestamp"]
    minute_of_day = timestamp.dt.hour * 60 + timestamp.dt.minute
    features["hour_sin"] = np.sin(2 * np.pi * minute_of_day / 1440)
    features["hour_cos"] = np.cos(2 * np.pi * minute_of_day / 1440)
    day_of_week = timestamp.dt.dayofweek
    features["dow_sin"] = np.sin(2 * np.pi * day_of_week / 7)
    features["dow_cos"] = np.cos(2 * np.pi * day_of_week / 7)

    true_range = pd.concat(
        [
            high - low,
            (high - close.shift(1)).abs(),
            (low - close.shift(1)).abs(),
        ],
        axis=1,
    ).max(axis=1)
    for window in ROLLING_WINDOWS:
        rolling_mean = close.rolling(window, min_periods=window).mean()
        rolling_std = close.rolling(window, min_periods=window).std()
        rolling_min = close.rolling(window, min_periods=window).min()
        rolling_max = close.rolling(window, min_periods=window).max()
        rolling_ret = log_returns(close, window)
        features[f"roll_mean_dist_{window}"] = close - rolling_mean
        features[f"roll_z_{window}"] = (close - rolling_mean) / rolling_std.replace(0, np.nan)
        features[f"roll_vol_{window}"] = features["ret_1"].rolling(window, min_periods=window).std()
        features[f"roll_return_{window}"] = rolling_ret
        features[f"roll_min_dist_{window}"] = close - rolling_min
        features[f"roll_max_dist_{window}"] = close - rolling_max
        features[f"atr_{window}"] = true_range.rolling(window, min_periods=window).mean()

    if include_fft:
        fft_features = rolling_fft_features(features["ret_1"].fillna(0.0).to_numpy(), FFT_WINDOWS)
        for name, values in fft_features.items():
            features[name] = values

    feature_columns = list(features.columns)
    return features, feature_columns


def rolling_fft_features(values: np.ndarray, windows: list[int]) -> dict[str, np.ndarray]:
    output: dict[str, np.ndarray] = {}
    n = len(values)
    for window in windows:
        low_power = np.full(n, np.nan, dtype="float64")
        high_power = np.full(n, np.nan, dtype="float64")
        centroid = np.full(n, np.nan, dtype="float64")
        if n >= window:
            windows_view = np.lib.stride_tricks.sliding_window_view(values, window)
            windows_view = windows_view - windows_view.mean(axis=1, keepdims=True)
            spectrum = np.fft.rfft(windows_view, axis=1)
            power = np.abs(spectrum) ** 2
            if power.shape[1] > 1:
                power_no_dc = power[:, 1:]
                split = max(1, power_no_dc.shape[1] // 3)
                low = power_no_dc[:, :split].sum(axis=1)
                high = power_no_dc[:, split:].sum(axis=1)
                freqs = np.arange(1, power.shape[1], dtype="float64")
                total = power_no_dc.sum(axis=1)
                spec_centroid = (power_no_dc * freqs).sum(axis=1) / np.where(total == 0, np.nan, total)
            else:
                low = np.zeros(len(windows_view))
                high = np.zeros(len(windows_view))
                spec_centroid = np.zeros(len(windows_view))
            low_power[window - 1 :] = low
            high_power[window - 1 :] = high
            centroid[window - 1 :] = spec_centroid
        output[f"fft_low_power_{window}"] = low_power
        output[f"fft_high_power_{window}"] = high_power
        output[f"fft_centroid_{window}"] = centroid
    return output


def future_best_labels(
    df: pd.DataFrame,
    horizon: pd.Timedelta,
    min_adjusted_edge: float,
    profit_multiplier: float,
    loss_multiplier: float,
) -> pd.DataFrame:
    timestamps = df["timestamp"].reset_index(drop=True)
    opens = df["open"].astype(float).to_numpy()
    ts_ns = timestamps.astype("int64").to_numpy()
    horizon_ns = int(horizon / pd.Timedelta(nanoseconds=1))
    force_indices = np.searchsorted(ts_ns, ts_ns + horizon_ns, side="left")

    n = len(df)
    label = np.full(n, np.nan)
    long_adj = np.full(n, np.nan)
    short_adj = np.full(n, np.nan)
    long_raw = np.full(n, np.nan)
    short_raw = np.full(n, np.nan)
    long_forced_raw = np.full(n, np.nan)
    short_forced_raw = np.full(n, np.nan)
    long_forced_adj = np.full(n, np.nan)
    short_forced_adj = np.full(n, np.nan)
    long_adverse = np.full(n, np.nan)
    short_adverse = np.full(n, np.nan)
    long_profit_barrier_hit = np.full(n, np.nan)
    short_profit_barrier_hit = np.full(n, np.nan)
    long_exit_event = np.full(n, np.nan)
    short_exit_event = np.full(n, np.nan)
    long_exit_event_minutes = np.full(n, np.nan)
    short_exit_event_minutes = np.full(n, np.nan)
    profit_barrier_horizon_targets: dict[str, np.ndarray] = {}
    for minutes in PROFIT_BARRIER_HORIZON_MINUTES:
        profit_barrier_horizon_targets[f"long_profit_barrier_hit_{minutes}m"] = np.full(n, np.nan)
        profit_barrier_horizon_targets[f"short_profit_barrier_hit_{minutes}m"] = np.full(n, np.nan)
    fixed_horizon_targets: dict[str, np.ndarray] = {}
    for minutes in EXIT_FIXED_HORIZON_MINUTES:
        fixed_horizon_targets[f"long_fixed_{minutes}m_adjusted_pnl"] = np.full(n, np.nan)
        fixed_horizon_targets[f"short_fixed_{minutes}m_adjusted_pnl"] = np.full(n, np.nan)
    long_best_exit_idx = np.full(n, -1, dtype="int64")
    short_best_exit_idx = np.full(n, -1, dtype="int64")
    long_best_exit_price = np.full(n, np.nan)
    short_best_exit_price = np.full(n, np.nan)
    long_best_holding_minutes = np.full(n, np.nan)
    short_best_holding_minutes = np.full(n, np.nan)
    best_adj = np.full(n, np.nan)
    best_raw = np.full(n, np.nan)
    best_exit_idx = np.full(n, -1, dtype="int64")
    best_exit_price = np.full(n, np.nan)
    best_holding_minutes = np.full(n, np.nan)
    entry_idx_values = np.full(n, -1, dtype="int64")
    profit_barrier_raw = min_adjusted_edge / profit_multiplier
    loss_barrier_raw = min_adjusted_edge / loss_multiplier
    fixed_horizon_ns = {
        minutes: int(pd.Timedelta(minutes=minutes) / pd.Timedelta(nanoseconds=1))
        for minutes in EXIT_FIXED_HORIZON_MINUTES
    }

    for decision_idx in range(n - 1):
        entry_idx = decision_idx + 1
        exit_start = entry_idx + 1
        exit_end = int(force_indices[entry_idx])
        if exit_start >= n or exit_end >= n or exit_start > exit_end:
            continue

        entry_price = opens[entry_idx]
        future_prices = opens[exit_start : exit_end + 1]
        if len(future_prices) == 0:
            continue

        long_relative_idx = int(np.argmax(future_prices))
        short_relative_idx = int(np.argmin(future_prices))
        long_exit_idx = exit_start + long_relative_idx
        short_exit_idx = exit_start + short_relative_idx
        long_raw_value = opens[long_exit_idx] - entry_price
        short_raw_value = entry_price - opens[short_exit_idx]
        long_value = adjusted_pnl(long_raw_value, profit_multiplier, loss_multiplier)
        short_value = adjusted_pnl(short_raw_value, profit_multiplier, loss_multiplier)

        forced_exit_idx = exit_end
        long_forced_raw_value = opens[forced_exit_idx] - entry_price
        short_forced_raw_value = entry_price - opens[forced_exit_idx]
        long_forced_value = adjusted_pnl(
            long_forced_raw_value,
            profit_multiplier,
            loss_multiplier,
        )
        short_forced_value = adjusted_pnl(
            short_forced_raw_value,
            profit_multiplier,
            loss_multiplier,
        )
        long_adverse_value = float(np.min(future_prices - entry_price))
        short_adverse_value = float(np.min(entry_price - future_prices))
        long_event, long_event_relative_idx = barrier_exit_event(
            future_prices - entry_price,
            profit_barrier_raw,
            loss_barrier_raw,
        )
        short_event, short_event_relative_idx = barrier_exit_event(
            entry_price - future_prices,
            profit_barrier_raw,
            loss_barrier_raw,
        )
        long_event_idx = exit_start + long_event_relative_idx
        short_event_idx = exit_start + short_event_relative_idx
        long_exit_event[decision_idx] = long_event
        short_exit_event[decision_idx] = short_event
        long_exit_event_minutes[decision_idx] = (
            timestamps.iloc[long_event_idx] - timestamps.iloc[entry_idx]
        ) / pd.Timedelta(minutes=1)
        short_exit_event_minutes[decision_idx] = (
            timestamps.iloc[short_event_idx] - timestamps.iloc[entry_idx]
        ) / pd.Timedelta(minutes=1)
        long_profit_barrier_hit[decision_idx] = int(long_event == EXIT_EVENT_PROFIT)
        short_profit_barrier_hit[decision_idx] = int(short_event == EXIT_EVENT_PROFIT)
        for minutes in PROFIT_BARRIER_HORIZON_MINUTES:
            fixed_ns = fixed_horizon_ns[minutes]
            fixed_exit_idx = int(np.searchsorted(ts_ns, ts_ns[entry_idx] + fixed_ns, side="left"))
            barrier_exit_idx = min(fixed_exit_idx, exit_end)
            if barrier_exit_idx >= exit_start and barrier_exit_idx < n:
                horizon_prices = opens[exit_start : barrier_exit_idx + 1]
                profit_barrier_horizon_targets[f"long_profit_barrier_hit_{minutes}m"][
                    decision_idx
                ] = profit_barrier_hit_before_loss(
                    horizon_prices - entry_price,
                    profit_barrier_raw,
                    loss_barrier_raw,
                )
                profit_barrier_horizon_targets[f"short_profit_barrier_hit_{minutes}m"][
                    decision_idx
                ] = profit_barrier_hit_before_loss(
                    entry_price - horizon_prices,
                    profit_barrier_raw,
                    loss_barrier_raw,
                )
            if fixed_exit_idx <= exit_end and fixed_exit_idx < n:
                long_fixed_raw = opens[fixed_exit_idx] - entry_price
                short_fixed_raw = entry_price - opens[fixed_exit_idx]
                fixed_horizon_targets[f"long_fixed_{minutes}m_adjusted_pnl"][decision_idx] = adjusted_pnl(
                    long_fixed_raw,
                    profit_multiplier,
                    loss_multiplier,
                )
                fixed_horizon_targets[f"short_fixed_{minutes}m_adjusted_pnl"][decision_idx] = adjusted_pnl(
                    short_fixed_raw,
                    profit_multiplier,
                    loss_multiplier,
                )

        if long_value >= short_value:
            chosen_label = 1
            chosen_adj = long_value
            chosen_raw = long_raw_value
            chosen_exit_idx = long_exit_idx
        else:
            chosen_label = -1
            chosen_adj = short_value
            chosen_raw = short_raw_value
            chosen_exit_idx = short_exit_idx

        if chosen_adj < min_adjusted_edge:
            chosen_label = 0

        label[decision_idx] = chosen_label
        long_adj[decision_idx] = long_value
        short_adj[decision_idx] = short_value
        long_raw[decision_idx] = long_raw_value
        short_raw[decision_idx] = short_raw_value
        long_forced_raw[decision_idx] = long_forced_raw_value
        short_forced_raw[decision_idx] = short_forced_raw_value
        long_forced_adj[decision_idx] = long_forced_value
        short_forced_adj[decision_idx] = short_forced_value
        long_adverse[decision_idx] = long_adverse_value
        short_adverse[decision_idx] = short_adverse_value
        long_best_exit_idx[decision_idx] = long_exit_idx
        short_best_exit_idx[decision_idx] = short_exit_idx
        long_best_exit_price[decision_idx] = opens[long_exit_idx]
        short_best_exit_price[decision_idx] = opens[short_exit_idx]
        long_best_holding_minutes[decision_idx] = (
            timestamps.iloc[long_exit_idx] - timestamps.iloc[entry_idx]
        ) / pd.Timedelta(minutes=1)
        short_best_holding_minutes[decision_idx] = (
            timestamps.iloc[short_exit_idx] - timestamps.iloc[entry_idx]
        ) / pd.Timedelta(minutes=1)
        best_adj[decision_idx] = chosen_adj
        best_raw[decision_idx] = chosen_raw
        best_exit_idx[decision_idx] = chosen_exit_idx
        best_exit_price[decision_idx] = opens[chosen_exit_idx]
        best_holding_minutes[decision_idx] = (
            timestamps.iloc[chosen_exit_idx] - timestamps.iloc[entry_idx]
        ) / pd.Timedelta(minutes=1)
        entry_idx_values[decision_idx] = entry_idx

    result = pd.DataFrame(
        {
            "entry_idx": entry_idx_values,
            "label": label,
            "long_best_adjusted_pnl": long_adj,
            "short_best_adjusted_pnl": short_adj,
            "long_best_raw_pnl": long_raw,
            "short_best_raw_pnl": short_raw,
            "long_forced_raw_pnl": long_forced_raw,
            "short_forced_raw_pnl": short_forced_raw,
            "long_forced_adjusted_pnl": long_forced_adj,
            "short_forced_adjusted_pnl": short_forced_adj,
            "long_max_adverse_pnl": long_adverse,
            "short_max_adverse_pnl": short_adverse,
            "long_profit_barrier_hit": long_profit_barrier_hit,
            "short_profit_barrier_hit": short_profit_barrier_hit,
            "long_exit_event": long_exit_event,
            "short_exit_event": short_exit_event,
            "long_exit_event_minutes": long_exit_event_minutes,
            "short_exit_event_minutes": short_exit_event_minutes,
            **profit_barrier_horizon_targets,
            **fixed_horizon_targets,
            "long_best_exit_idx": long_best_exit_idx,
            "short_best_exit_idx": short_best_exit_idx,
            "long_best_exit_price": long_best_exit_price,
            "short_best_exit_price": short_best_exit_price,
            "long_best_holding_minutes": long_best_holding_minutes,
            "short_best_holding_minutes": short_best_holding_minutes,
            "best_adjusted_pnl": best_adj,
            "best_raw_pnl": best_raw,
            "best_exit_idx": best_exit_idx,
            "best_exit_price": best_exit_price,
            "best_holding_minutes": best_holding_minutes,
            "side_score": long_adj - short_adj,
            "forced_side_score": long_forced_adj - short_forced_adj,
        },
        index=df.index,
    )
    return result


def profit_barrier_hit_before_loss(
    side_path: np.ndarray,
    profit_barrier_raw: float,
    loss_barrier_raw: float,
) -> int:
    event, _ = barrier_exit_event(side_path, profit_barrier_raw, loss_barrier_raw)
    return int(event == EXIT_EVENT_PROFIT)


def barrier_exit_event(
    side_path: np.ndarray,
    profit_barrier_raw: float,
    loss_barrier_raw: float,
) -> tuple[int, int]:
    profit_hits = np.flatnonzero(side_path >= profit_barrier_raw)
    loss_hits = np.flatnonzero(side_path <= -loss_barrier_raw)
    if len(profit_hits) == 0 and len(loss_hits) == 0:
        return EXIT_EVENT_TIME, max(0, len(side_path) - 1)
    if len(profit_hits) == 0:
        return EXIT_EVENT_LOSS, int(loss_hits[0])
    if len(loss_hits) == 0:
        return EXIT_EVENT_PROFIT, int(profit_hits[0])
    if profit_hits[0] <= loss_hits[0]:
        return EXIT_EVENT_PROFIT, int(profit_hits[0])
    return EXIT_EVENT_LOSS, int(loss_hits[0])


def add_entry_timing_targets(dataset: pd.DataFrame, lookahead_minutes: int) -> list[str]:
    if lookahead_minutes <= 0:
        raise ValueError("entry_timing_lookahead_minutes must be positive")
    timestamps = dataset["decision_timestamp"]
    ts_ns = timestamps.astype("int64").to_numpy()
    lookahead_ns = int(pd.Timedelta(minutes=lookahead_minutes) / pd.Timedelta(nanoseconds=1))
    target_columns: list[str] = []
    for side in ["long", "short"]:
        quality_column = f"{side}_best_adjusted_pnl"
        values = dataset[quality_column].astype(float).to_numpy()
        wait_regret = np.full(len(dataset), np.nan, dtype="float64")
        local_rank = np.full(len(dataset), np.nan, dtype="float64")
        urgency = np.full(len(dataset), np.nan, dtype="float64")
        for idx, current_value in enumerate(values):
            if not np.isfinite(current_value):
                continue
            right = int(np.searchsorted(ts_ns, ts_ns[idx] + lookahead_ns, side="right"))
            window = values[idx:right]
            window = window[np.isfinite(window)]
            if len(window) == 0:
                continue
            best_imminent = float(window.max())
            median_imminent = float(np.median(window))
            wait_regret[idx] = max(0.0, best_imminent - current_value)
            local_rank[idx] = float((window <= current_value).mean())
            urgency[idx] = current_value - median_imminent
        dataset[f"{side}_wait_regret"] = wait_regret
        dataset[f"{side}_entry_local_rank"] = local_rank
        dataset[f"{side}_entry_urgency"] = urgency
        target_columns.extend(
            [
                f"{side}_wait_regret",
                f"{side}_entry_local_rank",
                f"{side}_entry_urgency",
            ]
        )
    return target_columns


def quantile_codes(values: pd.Series, bins: int) -> pd.Series:
    if bins <= 1:
        raise ValueError("quantile bins must be greater than 1")
    valid = values.dropna()
    codes = pd.Series(pd.NA, index=values.index, dtype="Int16")
    if valid.empty:
        return codes
    ranked = valid.rank(method="first")
    try:
        binned = pd.qcut(ranked, q=bins, labels=False, duplicates="drop")
    except ValueError:
        return codes
    codes.loc[valid.index] = binned.astype("int16")
    return codes


def holding_time_bins(values: pd.Series) -> pd.Series:
    bins = [-0.1, 15, 60, 240, 720, 1440, float("inf")]
    labels = [0, 1, 2, 3, 4, 5]
    binned = pd.cut(values, bins=bins, labels=labels)
    return binned.astype("Int16")


def rank_bins(values: pd.Series, bins: int) -> pd.Series:
    if bins <= 1:
        raise ValueError("rank bins must be greater than 1")
    edges = np.linspace(0.0, 1.0, bins + 1)
    edges[0] = -0.001
    edges[-1] = 1.001
    labels = list(range(bins))
    binned = pd.cut(values, bins=edges, labels=labels, include_lowest=True)
    return binned.astype("Int16")


def add_quantized_targets(dataset: pd.DataFrame, bins: int) -> list[str]:
    target_columns = [
        "best_adjusted_pnl_quantile",
        "side_score_quantile",
        "long_wait_regret_quantile",
        "short_wait_regret_quantile",
        "long_entry_local_rank_bin",
        "short_entry_local_rank_bin",
        "best_holding_time_bin",
        "long_best_holding_time_bin",
        "short_best_holding_time_bin",
        "long_exit_event_time_bin",
        "short_exit_event_time_bin",
    ]
    dataset["best_adjusted_pnl_quantile"] = quantile_codes(dataset["best_adjusted_pnl"], bins)
    dataset["side_score_quantile"] = quantile_codes(dataset["side_score"], bins)
    dataset["long_wait_regret_quantile"] = quantile_codes(dataset["long_wait_regret"], bins)
    dataset["short_wait_regret_quantile"] = quantile_codes(dataset["short_wait_regret"], bins)
    dataset["long_entry_local_rank_bin"] = rank_bins(dataset["long_entry_local_rank"], bins)
    dataset["short_entry_local_rank_bin"] = rank_bins(dataset["short_entry_local_rank"], bins)
    dataset["best_holding_time_bin"] = holding_time_bins(dataset["best_holding_minutes"])
    dataset["long_best_holding_time_bin"] = holding_time_bins(dataset["long_best_holding_minutes"])
    dataset["short_best_holding_time_bin"] = holding_time_bins(dataset["short_best_holding_minutes"])
    dataset["long_exit_event_time_bin"] = holding_time_bins(dataset["long_exit_event_minutes"])
    dataset["short_exit_event_time_bin"] = holding_time_bins(dataset["short_exit_event_minutes"])
    return target_columns


def build_month_dataset(
    df: pd.DataFrame,
    month: str,
    config: DatasetConfig,
) -> tuple[pd.DataFrame, dict[str, object]]:
    start, end = month_bounds(month)
    horizon = pd.Timedelta(hours=config.horizon_hours)
    sliced = slice_for_month(
        df,
        start=start,
        end=end,
        warmup_days=config.warmup_days,
        post_days=config.post_days,
        max_holding=horizon,
    )
    features, feature_columns = build_features(sliced, include_fft=config.include_fft)
    labels = future_best_labels(
        sliced,
        horizon=horizon,
        min_adjusted_edge=config.min_adjusted_edge,
        profit_multiplier=config.profit_multiplier,
        loss_multiplier=config.loss_multiplier,
    )

    output = pd.concat(
        [
            sliced[["timestamp", "open", "high", "low", "close"]].rename(
                columns={"timestamp": "decision_timestamp"}
            ),
            features,
            labels,
        ],
        axis=1,
    )
    output = add_regime_columns(output)
    feature_columns = [*feature_columns, *REGIME_NUMERIC_COLUMNS]
    valid_entry = output["entry_idx"] >= 0
    entry_timestamps = pd.Series(pd.NaT, index=output.index, dtype="datetime64[ns, UTC]")
    valid_entry_indices = output.loc[valid_entry, "entry_idx"].astype(int)
    entry_timestamps.loc[valid_entry] = sliced.loc[valid_entry_indices, "timestamp"].to_numpy()
    output["entry_timestamp"] = entry_timestamps

    valid_exit = output["best_exit_idx"] >= 0
    exit_timestamps = pd.Series(pd.NaT, index=output.index, dtype="datetime64[ns, UTC]")
    valid_exit_indices = output.loc[valid_exit, "best_exit_idx"].astype(int)
    exit_timestamps.loc[valid_exit] = sliced.loc[valid_exit_indices, "timestamp"].to_numpy()
    output["best_exit_timestamp"] = exit_timestamps
    timing_target_columns = add_entry_timing_targets(output, config.entry_timing_lookahead_minutes)

    in_eval = (output["entry_timestamp"] >= start) & (output["entry_timestamp"] < end)
    feature_ready = output[feature_columns].notna().all(axis=1)
    label_ready = output["label"].notna()
    output = output.loc[in_eval & feature_ready & label_ready].copy()
    output["label"] = output["label"].astype("int8")
    output["entry_idx"] = output["entry_idx"].astype("int64")
    output["best_exit_idx"] = output["best_exit_idx"].astype("int64")
    output["long_best_exit_idx"] = output["long_best_exit_idx"].astype("int64")
    output["short_best_exit_idx"] = output["short_best_exit_idx"].astype("int64")
    output["long_profit_barrier_hit"] = output["long_profit_barrier_hit"].astype("int8")
    output["short_profit_barrier_hit"] = output["short_profit_barrier_hit"].astype("int8")
    output["long_exit_event"] = output["long_exit_event"].astype("int8")
    output["short_exit_event"] = output["short_exit_event"].astype("int8")
    profit_barrier_horizon_target_columns = [
        f"{side}_profit_barrier_hit_{minutes}m"
        for minutes in PROFIT_BARRIER_HORIZON_MINUTES
        for side in ["long", "short"]
    ]
    for column in profit_barrier_horizon_target_columns:
        output[column] = output[column].astype("int8")

    for column in feature_columns:
        output[column] = output[column].astype("float32")

    quantized_target_columns = add_quantized_targets(output, config.quantile_bins)
    fixed_horizon_target_columns = [
        f"{side}_fixed_{minutes}m_adjusted_pnl"
        for minutes in EXIT_FIXED_HORIZON_MINUTES
        for side in ["long", "short"]
    ]

    ordered_columns = [
        "decision_timestamp",
        "entry_timestamp",
        "best_exit_timestamp",
        "label",
        *quantized_target_columns,
        "long_profit_barrier_hit",
        "short_profit_barrier_hit",
        "long_exit_event",
        "short_exit_event",
        *profit_barrier_horizon_target_columns,
        *fixed_horizon_target_columns,
        "open",
        "high",
        "low",
        "close",
        *feature_columns,
        *REGIME_CATEGORY_COLUMNS,
        "long_best_adjusted_pnl",
        "short_best_adjusted_pnl",
        "long_best_raw_pnl",
        "short_best_raw_pnl",
        "long_forced_adjusted_pnl",
        "short_forced_adjusted_pnl",
        "long_forced_raw_pnl",
        "short_forced_raw_pnl",
        "long_max_adverse_pnl",
        "short_max_adverse_pnl",
        "long_exit_event_minutes",
        "short_exit_event_minutes",
        "long_wait_regret",
        "short_wait_regret",
        "long_entry_local_rank",
        "short_entry_local_rank",
        "long_entry_urgency",
        "short_entry_urgency",
        "side_score",
        "forced_side_score",
        "best_adjusted_pnl",
        "best_raw_pnl",
        "best_exit_price",
        "best_holding_minutes",
        "long_best_exit_price",
        "short_best_exit_price",
        "long_best_holding_minutes",
        "short_best_holding_minutes",
    ]
    output = output[ordered_columns].reset_index(drop=True)
    summary = dataset_summary(
        output,
        config,
        feature_columns,
        quantized_target_columns,
        [
            "long_profit_barrier_hit",
            "short_profit_barrier_hit",
            "long_exit_event",
            "short_exit_event",
            "long_exit_event_minutes",
            "short_exit_event_minutes",
            *profit_barrier_horizon_target_columns,
            *fixed_horizon_target_columns,
            *timing_target_columns,
        ],
    )
    return output, summary


def dataset_summary(
    dataset: pd.DataFrame,
    config: DatasetConfig,
    feature_columns: list[str],
    quantized_target_columns: list[str],
    extra_target_columns: list[str] | None = None,
) -> dict[str, object]:
    label_counts = dataset["label"].value_counts().sort_index().to_dict()
    label_counts = {str(int(key)): int(value) for key, value in label_counts.items()}
    quantile_counts = {}
    for column in quantized_target_columns:
        counts = dataset[column].value_counts().sort_index().to_dict()
        quantile_counts[column] = {str(int(key)): int(value) for key, value in counts.items()}
    regime_counts = {}
    for column in REGIME_CATEGORY_COLUMNS:
        if column in dataset.columns and not pd.api.types.is_numeric_dtype(dataset[column]):
            counts = dataset[column].value_counts().sort_index().to_dict()
            regime_counts[column] = {str(key): int(value) for key, value in counts.items()}
    return {
        "config": asdict(config),
        "rows": int(len(dataset)),
        "feature_count": len(feature_columns),
        "feature_columns": feature_columns,
        "target_columns": [
            "label",
            *quantized_target_columns,
            *(extra_target_columns or []),
            "long_best_adjusted_pnl",
            "short_best_adjusted_pnl",
            "long_forced_adjusted_pnl",
            "short_forced_adjusted_pnl",
            "long_max_adverse_pnl",
            "short_max_adverse_pnl",
            "side_score",
            "forced_side_score",
            "best_adjusted_pnl",
            "best_holding_minutes",
        ],
        "start_decision_timestamp": None
        if dataset.empty
        else dataset["decision_timestamp"].min().isoformat(),
        "end_decision_timestamp": None
        if dataset.empty
        else dataset["decision_timestamp"].max().isoformat(),
        "label_counts": label_counts,
        "label_meanings": {"-1": "short", "0": "stay_flat", "1": "long"},
        "exit_event_meanings": {
            str(EXIT_EVENT_TIME): "time_exit",
            str(EXIT_EVENT_PROFIT): "profit_first",
            str(EXIT_EVENT_LOSS): "loss_first",
        },
        "quantized_target_counts": quantile_counts,
        "regime_counts": regime_counts,
        "best_adjusted_pnl": {
            "mean": None if dataset.empty else float(dataset["best_adjusted_pnl"].mean()),
            "median": None if dataset.empty else float(dataset["best_adjusted_pnl"].median()),
            "p90": None if dataset.empty else float(dataset["best_adjusted_pnl"].quantile(0.9)),
        },
        "side_score": {
            "mean": None if dataset.empty else float(dataset["side_score"].mean()),
            "median": None if dataset.empty else float(dataset["side_score"].median()),
            "p10": None if dataset.empty else float(dataset["side_score"].quantile(0.1)),
            "p90": None if dataset.empty else float(dataset["side_score"].quantile(0.9)),
        },
    }


def print_summary(summary: dict[str, object]) -> None:
    print(f"rows: {summary['rows']:,}")
    print(f"feature_count: {summary['feature_count']}")
    print(f"start: {summary['start_decision_timestamp']}")
    print(f"end: {summary['end_decision_timestamp']}")
    print(f"label_counts: {summary['label_counts']}")
    print(f"quantized_target_counts: {summary['quantized_target_counts']}")
    print(f"best_adjusted_pnl: {summary['best_adjusted_pnl']}")
    print(f"side_score: {summary['side_score']}")


def config_from_args(args: argparse.Namespace, month: str) -> DatasetConfig:
    return DatasetConfig(
        month=month,
        horizon_hours=args.horizon_hours,
        warmup_days=args.warmup_days,
        post_days=args.post_days,
        min_adjusted_edge=args.min_adjusted_edge,
        profit_multiplier=args.profit_multiplier,
        loss_multiplier=args.loss_multiplier,
        include_fft=args.include_fft,
        quantile_bins=args.quantile_bins,
        entry_timing_lookahead_minutes=args.entry_timing_lookahead_minutes,
    )


def output_stem(month: str, horizon_hours: float, min_adjusted_edge: float) -> str:
    return f"xauusd_m1_{month}_h{int(horizon_hours)}_edge{min_adjusted_edge:g}"


def write_dataset(
    dataset: pd.DataFrame,
    summary: dict[str, object],
    output_path: Path,
    compression: str,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path = output_path.with_suffix(".summary.json")
    dataset.to_parquet(output_path, index=False, compression=compression)
    with summary_path.open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2)
    print(f"wrote: {output_path}")
    print(f"wrote: {summary_path}")


def iter_months(start_month: str, end_month: str) -> list[str]:
    start, _ = month_bounds(start_month)
    end, _ = month_bounds(end_month)
    if start > end:
        raise ValueError("start month must be <= end month")
    months: list[str] = []
    current = start
    while current <= end:
        months.append(current.strftime("%Y-%m"))
        current = current + pd.DateOffset(months=1)
    return months


def handle_build(args: argparse.Namespace) -> int:
    config = config_from_args(args, args.month)
    df = read_ohlcv(args.data)
    dataset, summary = build_month_dataset(df, args.month, config)
    stem = output_stem(args.month, args.horizon_hours, args.min_adjusted_edge)
    output_path = args.output or args.output_dir / f"{stem}.parquet"
    write_dataset(dataset, summary, output_path, args.compression)
    print_summary(summary)
    return 0


def handle_build_range(args: argparse.Namespace) -> int:
    months = iter_months(args.start_month, args.end_month)
    df = read_ohlcv(args.data)
    summaries: list[dict[str, object]] = []
    for index, month in enumerate(months, start=1):
        print(f"[{index}/{len(months)}] build dataset for {month}")
        config = config_from_args(args, month)
        stem = output_stem(month, args.horizon_hours, args.min_adjusted_edge)
        output_path = args.output_dir / f"{stem}.parquet"
        summary_path = output_path.with_suffix(".summary.json")
        if args.skip_existing and output_path.exists() and summary_path.exists():
            print(f"skip existing: {output_path}")
            with summary_path.open("r", encoding="utf-8") as handle:
                summaries.append(json.load(handle))
            continue
        dataset, summary = build_month_dataset(df, month, config)
        write_dataset(dataset, summary, output_path, args.compression)
        print_summary(summary)
        summaries.append(summary)

    combined_path = (
        args.output_dir
        / f"build_range_{months[0]}_{months[-1]}_edge{args.min_adjusted_edge:g}.summary.json"
    )
    with combined_path.open("w", encoding="utf-8") as handle:
        json.dump({"months": months, "summaries": summaries}, handle, ensure_ascii=False, indent=2)
    print(f"wrote: {combined_path}")
    return 0


def add_dataset_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--data",
        type=Path,
        default=Path("data/processed/histdata/xauusd/xauusd_m1.parquet"),
    )
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed/datasets/xauusd_m1"))
    parser.add_argument("--horizon-hours", type=float, default=24.0)
    parser.add_argument("--warmup-days", type=int, default=14)
    parser.add_argument("--post-days", type=int, default=4)
    parser.add_argument("--min-adjusted-edge", type=float, default=1.0)
    parser.add_argument("--profit-multiplier", type=float, default=1.0)
    parser.add_argument("--loss-multiplier", type=float, default=1.2)
    parser.add_argument("--quantile-bins", type=int, default=5)
    parser.add_argument(
        "--entry-timing-lookahead-minutes",
        type=int,
        default=60,
        help="future window used to score local entry quality targets",
    )
    parser.add_argument("--compression", default="zstd")
    parser.add_argument("--include-fft", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--skip-existing", action="store_true")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build feature and label datasets")
    subparsers = parser.add_subparsers(dest="command", required=True)

    build = subparsers.add_parser("build", help="build one month of M1 features and labels")
    add_dataset_args(build)
    build.add_argument("--month", required=True, help="evaluation month in YYYY-MM")
    build.add_argument("--output", type=Path, default=None)
    build.set_defaults(func=handle_build)

    build_range = subparsers.add_parser(
        "build-range",
        help="build multiple monthly M1 feature/label datasets",
    )
    add_dataset_args(build_range)
    build_range.add_argument("--start-month", required=True, help="start month in YYYY-MM")
    build_range.add_argument("--end-month", required=True, help="end month in YYYY-MM")
    build_range.set_defaults(func=handle_build_range)
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
