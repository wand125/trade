from __future__ import annotations

from analysis.market_data import MarketHistory, index_at_or_before
from analysis.models import Candidate
from analysis.swing_points import SwingPoint, detect_swings, swing_window


def build_features(
    history: MarketHistory,
    candidate: Candidate,
    m1_swings: list[SwingPoint],
    *,
    tp_obstacle_count: int,
    previous_swing_distance_atr: float,
) -> dict[str, float | int | str | bool | None]:
    m1 = history.bars("M1")
    entry_bar = m1[candidate.index]
    swing_bar = m1[max(0, min(candidate.index, _index_by_time(m1, candidate.swing_time)))]
    atr_m1 = _indicator_at(history, "M1", "atr14", candidate.index) or 0.0
    spread_price = history.spread_points * history.point

    features: dict[str, float | int | str | bool | None] = {
        "side": candidate.side,
        "pattern": candidate.pattern,
        "risk": candidate.risk,
        "risk_reward": candidate.risk_reward,
        "risk_atr": candidate.risk / atr_m1 if atr_m1 > 0 else None,
        "spread_r": spread_price / candidate.risk if candidate.risk > 0 else None,
        "tp_obstacle_count": tp_obstacle_count,
        "swing_strength_atr": _safe(candidate.features.get("swing_strength_atr")),
        "distance_from_previous_swing_atr": previous_swing_distance_atr,
        "retest_level_kind": candidate.features.get("retest_level_kind"),
        "retest_level_time": candidate.features.get("retest_level_time"),
        "retest_level_price": _safe(candidate.features.get("retest_level_price")),
        "retest_broken_time": candidate.features.get("retest_broken_time"),
        "retest_distance_atr": _safe(candidate.features.get("retest_distance_atr")),
        "retest_entry_reclaimed": candidate.features.get("retest_entry_reclaimed"),
        "entry_body": entry_bar.close - entry_bar.open,
        "entry_body_atr": (entry_bar.close - entry_bar.open) / atr_m1 if atr_m1 > 0 else None,
        "rejection_wick_ratio": _rejection_wick_ratio(swing_bar, candidate.side),
        "broke_trigger": _broke_trigger(m1, candidate.index, candidate.side),
        "ema_trigger": _ema_trigger(history, candidate.index, candidate.side),
        "m1_alternating_ratio": _alternating_ratio(m1, candidate.index, 10),
    }

    for tf in ("M5", "M15", "M30"):
        tf_bars = history.bars(tf)
        tf_index = index_at_or_before(tf_bars, candidate.time)
        if tf_index is None:
            continue
        for name in ("ema_fast", "ema_slow", "ema_mid", "ema_long", "rsi14", "atr14"):
            features[f"{tf}_{name}"] = _indicator_at(history, tf, name, tf_index)
        ema_fast = _indicator_at(history, tf, "ema_fast", tf_index)
        ema_slow = _indicator_at(history, tf, "ema_slow", tf_index)
        ema_mid = _indicator_at(history, tf, "ema_mid", tf_index)
        ema_long = _indicator_at(history, tf, "ema_long", tf_index)
        atr = _indicator_at(history, tf, "atr14", tf_index)
        close = tf_bars[tf_index].close
        if tf == "M5" and ema_fast is not None and ema_slow is not None and atr and atr > 0:
            features["M5_ema_gap_atr"] = (ema_fast - ema_slow) / atr
        if ema_slow is not None and atr and atr > 0:
            features[f"{tf}_close_ema_slow_atr"] = (close - ema_slow) / atr
            features[f"{tf}_ema_slow_slope_atr"] = _ema_slope_atr(history, tf, "ema_slow", tf_index, atr)
        if ema_mid is not None and atr and atr > 0:
            features[f"{tf}_close_ema_mid_atr"] = (close - ema_mid) / atr
            features[f"{tf}_ema_mid_slope_atr"] = _ema_slope_atr(history, tf, "ema_mid", tf_index, atr)
        if ema_long is not None and atr and atr > 0:
            features[f"{tf}_close_ema_long_atr"] = (close - ema_long) / atr
        if ema_mid is not None and ema_long is not None:
            features[f"{tf}_macro_ema_aligned"] = ema_mid > ema_long if candidate.side == "buy" else ema_mid < ema_long
        if tf in ("M5", "M15", "M30"):
            features.update(_swing_context_features(history, candidate, tf_index, timeframe=tf))

    features["htf_alignment_count"] = _htf_alignment_count(features, candidate.side)
    features["htf_slope_count"] = _htf_slope_count(features, candidate.side)
    features["m15_extension_atr"] = _side_extension(features, "M15", candidate.side)
    features["m30_extension_atr"] = _side_extension(features, "M30", candidate.side)

    return features


def _indicator_at(history: MarketHistory, timeframe: str, name: str, index: int) -> float | None:
    series = history.indicator(timeframe, name)
    if index < 0 or index >= len(series):
        return None
    value = series[index]
    return float(value) if value is not None else None


def _index_by_time(bars, time_text: str) -> int:
    for index, bar in enumerate(bars):
        if bar.time_text == time_text:
            return index
    return 0


def _safe(value: float | int | str | bool | None) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _rejection_wick_ratio(bar, side: str) -> float:
    candle_range = bar.high - bar.low
    if candle_range <= 0:
        return 0.0
    if side == "sell":
        upper_wick = bar.high - max(bar.open, bar.close)
        return max(upper_wick / candle_range, 0.0)
    lower_wick = min(bar.open, bar.close) - bar.low
    return max(lower_wick / candle_range, 0.0)


def _broke_trigger(bars, index: int, side: str, lookback: int = 3) -> bool:
    if index <= lookback:
        return False
    current = bars[index]
    previous = bars[index - lookback : index]
    if side == "sell":
        return current.close < min(bar.low for bar in previous)
    return current.close > max(bar.high for bar in previous)


def _ema_trigger(history: MarketHistory, index: int, side: str) -> bool:
    close = history.bars("M1")[index].close
    ema_fast = _indicator_at(history, "M1", "ema_fast", index)
    if ema_fast is None:
        return False
    return close < ema_fast if side == "sell" else close > ema_fast


def _ema_slope_atr(history: MarketHistory, timeframe: str, name: str, index: int, atr: float) -> float | None:
    lookbacks = {"M5": 6, "M15": 4, "M30": 3}
    lookback = lookbacks.get(timeframe, 3)
    previous_index = index - lookback
    if previous_index < 0:
        return None
    current = _indicator_at(history, timeframe, name, index)
    previous = _indicator_at(history, timeframe, name, previous_index)
    if current is None or previous is None or atr <= 0:
        return None
    return (current - previous) / atr


def _swing_context_features(
    history: MarketHistory,
    candidate: Candidate,
    tf_index: int,
    *,
    timeframe: str = "M5",
    min_atr_distance: float = 0.5,
) -> dict[str, float | int | str | bool | None]:
    bars = history.bars(timeframe)
    if not bars or tf_index < 0 or tf_index >= len(bars):
        return {}
    left, right = swing_window(timeframe)
    swings = detect_swings(
        bars,
        history.indicator(timeframe, "atr14"),
        left=left,
        right=right,
        min_atr_distance=min_atr_distance,
    )
    confirmed = [swing for swing in swings if swing.index + right <= tf_index]
    if not confirmed:
        return {}

    close = bars[tf_index].close
    atr = _indicator_at(history, timeframe, "atr14", tf_index) or confirmed[-1].atr or 0.0
    features: dict[str, float | int | str | bool | None] = {}
    for kind in ("high", "low"):
        same_kind = [swing for swing in confirmed if swing.kind == kind]
        if not same_kind:
            continue
        swing = same_kind[-1]
        prefix = f"{timeframe}_last_swing_{kind}"
        features[f"{prefix}_time"] = swing.time_text
        features[f"{prefix}_price"] = swing.price
        features[f"{prefix}_age_bars"] = tf_index - swing.index
        if len(same_kind) >= 2:
            previous = same_kind[-2]
            features[f"{prefix}_previous_time"] = previous.time_text
            features[f"{prefix}_previous_price"] = previous.price
            features[f"{timeframe}_swing_{kind}_trend"] = _swing_trend_label(kind, previous.price, swing.price)
        if atr > 0:
            if kind == "high":
                features[f"{prefix}_distance_atr"] = (swing.price - close) / atr
            else:
                features[f"{prefix}_distance_atr"] = (close - swing.price) / atr

    obstacle_kind = "high" if candidate.side == "buy" else "low"
    lower = min(candidate.entry, candidate.tp)
    upper = max(candidate.entry, candidate.tp)
    obstacles = [
        swing
        for swing in confirmed
        if swing.kind == obstacle_kind and lower <= swing.price <= upper
    ]
    features[f"{timeframe}_tp_obstacle_count"] = len(obstacles)
    if obstacles and atr > 0:
        nearest = min(obstacles, key=lambda swing: abs(swing.price - candidate.entry))
        features[f"{timeframe}_nearest_tp_obstacle_time"] = nearest.time_text
        features[f"{timeframe}_nearest_tp_obstacle_price"] = nearest.price
        features[f"{timeframe}_nearest_tp_obstacle_distance_atr"] = abs(nearest.price - candidate.entry) / atr
    return features


def _swing_trend_label(kind: str, previous_price: float, current_price: float) -> str:
    if current_price == previous_price:
        return "flat"
    if kind == "high":
        return "higher_high" if current_price > previous_price else "lower_high"
    return "higher_low" if current_price > previous_price else "lower_low"


def _htf_alignment_count(features: dict[str, float | int | str | bool | None], side: str) -> int:
    count = 0
    for tf in ("M15", "M30"):
        ema_fast = _safe(features.get(f"{tf}_ema_fast"))
        ema_slow = _safe(features.get(f"{tf}_ema_slow"))
        ema_mid = _safe(features.get(f"{tf}_ema_mid"))
        ema_long = _safe(features.get(f"{tf}_ema_long"))
        close_to_slow = _safe(features.get(f"{tf}_close_ema_slow_atr"))
        if ema_fast is not None and ema_slow is not None:
            if (ema_fast > ema_slow) if side == "buy" else (ema_fast < ema_slow):
                count += 1
        if ema_mid is not None and ema_long is not None:
            if (ema_mid > ema_long) if side == "buy" else (ema_mid < ema_long):
                count += 1
        if close_to_slow is not None:
            if close_to_slow > 0 if side == "buy" else close_to_slow < 0:
                count += 1
    return count


def _htf_slope_count(features: dict[str, float | int | str | bool | None], side: str) -> int:
    count = 0
    for tf in ("M15", "M30"):
        for name in ("ema_slow_slope_atr", "ema_mid_slope_atr"):
            slope = _safe(features.get(f"{tf}_{name}"))
            if slope is None:
                continue
            if slope > 0 if side == "buy" else slope < 0:
                count += 1
    return count


def _side_extension(features: dict[str, float | int | str | bool | None], timeframe: str, side: str) -> float | None:
    value = _safe(features.get(f"{timeframe}_close_ema_slow_atr"))
    if value is None:
        return None
    return value if side == "buy" else -value


def _alternating_ratio(bars, index: int, lookback: int) -> float:
    start = max(0, index - lookback + 1)
    recent = bars[start : index + 1]
    if len(recent) < 3:
        return 0.0
    signs: list[int] = []
    for bar in recent:
        if bar.close > bar.open:
            signs.append(1)
        elif bar.close < bar.open:
            signs.append(-1)
        else:
            signs.append(0)
    changes = 0
    comparable = 0
    previous = signs[0]
    for sign in signs[1:]:
        if previous != 0 and sign != 0:
            comparable += 1
            if sign != previous:
                changes += 1
        if sign != 0:
            previous = sign
    return changes / comparable if comparable else 0.0
