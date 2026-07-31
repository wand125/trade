from __future__ import annotations

from datetime import timedelta

from analysis.economic_calendar import EconomicEvent
from analysis.features import build_features
from analysis.market_data import MarketHistory
from analysis.models import Candidate
from analysis.scoring import score_candidate
from analysis.swing_points import SwingPoint, detect_swings
from analysis.time_filters import DEFAULT_BLACKOUT_WINDOWS, TimeWindow, blackout_reasons


def generate_candidates(
    history: MarketHistory,
    *,
    risk_reward: float = 5.0,
    swing_left: int = 3,
    swing_right: int = 3,
    min_atr_distance: float = 0.5,
    min_risk_atr: float = 0.20,
    max_risk_atr: float = 3.0,
    min_risk_spread: float = 1.5,
    cooldown_minutes: int = 3,
    min_score: float | None = None,
    score_profile: str = "side",
    exclude_blackout_times: bool = True,
    blackout_windows: tuple[TimeWindow, ...] = DEFAULT_BLACKOUT_WINDOWS,
    blackout_events: list[EconomicEvent] | tuple[EconomicEvent, ...] = (),
    news_before_minutes: int = 10,
    news_after_minutes: int = 10,
    news_min_impact: str = "high",
    news_currencies: tuple[str, ...] | list[str] | None = ("USD", "XAU", "ALL", "*"),
) -> list[Candidate]:
    m1 = history.bars("M1")
    if not m1:
        return []

    atr_values = history.indicator("M1", "atr14")
    swings = detect_swings(
        m1,
        atr_values,
        left=swing_left,
        right=swing_right,
        min_atr_distance=min_atr_distance,
    )
    candidates: list[Candidate] = []
    last_entry_time_by_side: dict[str, object] = {}
    previous_price_by_kind: dict[str, tuple[float, float]] = {}

    for swing in swings:
        entry_index = swing.index + swing_right + 1
        if entry_index >= len(m1):
            continue
        side = "sell" if swing.kind == "high" else "buy"
        entry_bar = m1[entry_index]
        last_time = last_entry_time_by_side.get(side)
        if last_time is not None and entry_bar.time - last_time < timedelta(minutes=cooldown_minutes):
            continue
        if exclude_blackout_times and blackout_reasons(
            entry_bar.time,
            blackout_windows,
            events=blackout_events,
            news_before_minutes=news_before_minutes,
            news_after_minutes=news_after_minutes,
            news_min_impact=news_min_impact,
            news_currencies=news_currencies,
        ):
            continue

        atr = _atr_at(atr_values, entry_index) or swing.atr
        if atr <= 0:
            continue
        spread_price = history.spread_points * history.point
        buffer = atr * 0.3
        entry = entry_bar.close

        if side == "sell":
            sl = swing.price + spread_price + buffer
            risk = sl - entry
            tp = entry - risk_reward * risk
        else:
            sl = swing.price - spread_price - buffer
            risk = entry - sl
            tp = entry + risk_reward * risk

        if risk <= 0:
            continue
        if risk < max(atr * min_risk_atr, spread_price * min_risk_spread):
            continue
        if risk > atr * max_risk_atr:
            continue

        previous_distance_atr = _previous_distance_atr(swing, previous_price_by_kind)
        obstacle_count = _tp_obstacle_count(swings, swing.index, side, entry, tp)
        pattern, pattern_features = _classify_pattern(history, swings, swing, entry_index, side, atr)
        candidate = Candidate(
            candidate_id=f"{entry_bar.time_text}-{side}-{swing.index}",
            time=entry_bar.time,
            time_text=entry_bar.time_text,
            index=entry_index,
            symbol=history.symbol,
            side=side,
            pattern=pattern,
            entry=entry,
            sl=sl,
            tp=tp,
            risk=risk,
            risk_reward=risk_reward,
            swing_time=swing.time_text,
            swing_price=swing.price,
            swing_kind=swing.kind,
            features={"swing_strength_atr": swing.strength_atr, **pattern_features},
        )
        candidate.features = build_features(
            history,
            candidate,
            swings,
            tp_obstacle_count=obstacle_count,
            previous_swing_distance_atr=previous_distance_atr,
        )
        candidate.features["score_profile"] = score_profile
        breakdown = score_candidate(candidate.features, profile=score_profile)
        candidate.score = breakdown.score
        candidate.score_parts = breakdown.as_dict()
        previous_price_by_kind[swing.kind] = (swing.price, swing.atr)

        if min_score is not None and candidate.score < min_score:
            continue
        candidates.append(candidate)
        last_entry_time_by_side[side] = entry_bar.time

    return candidates


def _atr_at(values: list[float | None], index: int) -> float | None:
    if index < 0 or index >= len(values):
        return None
    value = values[index]
    return float(value) if value is not None else None


def _previous_distance_atr(swing: SwingPoint, previous_price_by_kind: dict[str, tuple[float, float]]) -> float:
    previous = previous_price_by_kind.get(swing.kind)
    if previous is None:
        return 0.0
    previous_price, previous_atr = previous
    denominator = swing.atr or previous_atr or 1.0
    return abs(swing.price - previous_price) / denominator if denominator > 0 else 0.0


def _tp_obstacle_count(swings: list[SwingPoint], swing_index: int, side: str, entry: float, tp: float) -> int:
    count = 0
    relevant_kind = "high" if side == "buy" else "low"
    lower = min(entry, tp)
    upper = max(entry, tp)
    for swing in swings:
        if swing.index >= swing_index:
            continue
        if swing.kind != relevant_kind:
            continue
        if lower <= swing.price <= upper:
            count += 1
    return count


def _classify_pattern(
    history: MarketHistory,
    swings: list[SwingPoint],
    swing: SwingPoint,
    index: int,
    side: str,
    atr: float,
) -> tuple[str, dict[str, float | int | str | bool | None]]:
    breakout_features = _breakout_retest_features(history, swings, swing, index, side, atr)
    if breakout_features:
        return "breakout_retest", breakout_features

    m15_fast = _indicator(history, "M15", "ema_fast", index)
    m15_slow = _indicator(history, "M15", "ema_slow", index)
    m30_fast = _indicator(history, "M30", "ema_fast", index)
    m30_slow = _indicator(history, "M30", "ema_slow", index)
    if None in (m15_fast, m15_slow, m30_fast, m30_slow):
        return "liquidity_sweep_reversal", {}
    aligned = (m15_fast > m15_slow and m30_fast > m30_slow) if side == "buy" else (m15_fast < m15_slow and m30_fast < m30_slow)
    return ("pullback_continuation" if aligned else "liquidity_sweep_reversal"), {}


def _breakout_retest_features(
    history: MarketHistory,
    swings: list[SwingPoint],
    swing: SwingPoint,
    index: int,
    side: str,
    atr: float,
    *,
    retest_atr_band: float = 0.80,
    max_level_lookback: int = 8,
) -> dict[str, float | int | str | bool | None]:
    if atr <= 0:
        return {}
    m1 = history.bars("M1")
    if index <= 0 or index >= len(m1):
        return {}

    level_kind = "high" if side == "buy" else "low"
    previous_levels = [item for item in swings if item.kind == level_kind and item.index < swing.index]
    for level in reversed(previous_levels[-max_level_lookback:]):
        broken_index = _breakout_index(m1, level.index + 1, swing.index, side, level.price)
        if broken_index is None:
            continue
        retest_distance_atr = abs(swing.price - level.price) / atr
        if retest_distance_atr > retest_atr_band:
            continue
        entry_close = m1[index].close
        entry_reclaimed = entry_close > level.price if side == "buy" else entry_close < level.price
        if not entry_reclaimed:
            continue
        return {
            "retest_level_kind": level_kind,
            "retest_level_time": level.time_text,
            "retest_level_price": level.price,
            "retest_broken_time": m1[broken_index].time_text,
            "retest_distance_atr": retest_distance_atr,
            "retest_entry_reclaimed": entry_reclaimed,
        }
    return {}


def _breakout_index(bars, start: int, end: int, side: str, level: float) -> int | None:
    begin = max(0, start)
    finish = min(len(bars), end + 1)
    for index in range(begin, finish):
        close = bars[index].close
        if side == "buy" and close > level:
            return index
        if side == "sell" and close < level:
            return index
    return None


def _indicator(history: MarketHistory, timeframe: str, name: str, m1_index: int) -> float | None:
    m1_bars = history.bars("M1")
    if not m1_bars:
        return None
    from analysis.market_data import index_at_or_before

    index = index_at_or_before(history.bars(timeframe), m1_bars[m1_index].time)
    if index is None:
        return None
    series = history.indicator(timeframe, name)
    if index >= len(series):
        return None
    value = series[index]
    return float(value) if value is not None else None
