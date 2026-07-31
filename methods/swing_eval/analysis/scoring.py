from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ScoreBreakdown:
    score: float
    trend_score: float
    structure_score: float
    entry_trigger_score: float
    risk_reward_score: float
    cost_penalty: float
    chop_penalty: float
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, float | str]:
        return {
            "score": round(self.score, 2),
            "trend_score": round(self.trend_score, 2),
            "structure_score": round(self.structure_score, 2),
            "entry_trigger_score": round(self.entry_trigger_score, 2),
            "risk_reward_score": round(self.risk_reward_score, 2),
            "cost_penalty": round(self.cost_penalty, 2),
            "chop_penalty": round(self.chop_penalty, 2),
            "notes": "; ".join(self.notes),
        }


def score_candidate(features: dict[str, float | int | str | bool | None], profile: str | None = None) -> ScoreBreakdown:
    side = str(features.get("side", ""))
    notes: list[str] = []
    active_profile = side if profile in (None, "side") else profile

    trend_score = _trend_score(features, side, active_profile, notes)
    structure_score = _structure_score(features, notes)
    entry_trigger_score = _entry_trigger_score(features, side, notes)
    risk_reward_score = _risk_reward_score(features, active_profile, notes)
    cost_penalty = _cost_penalty(features, notes)
    chop_penalty = _chop_penalty(features, side, active_profile, notes)
    score = trend_score + structure_score + entry_trigger_score + risk_reward_score + cost_penalty + chop_penalty
    score = max(0.0, min(100.0, score))

    return ScoreBreakdown(
        score=score,
        trend_score=trend_score,
        structure_score=structure_score,
        entry_trigger_score=entry_trigger_score,
        risk_reward_score=risk_reward_score,
        cost_penalty=cost_penalty,
        chop_penalty=chop_penalty,
        notes=notes,
    )


def _trend_score(features: dict[str, float | int | str | bool | None], side: str, profile: str, notes: list[str]) -> float:
    score = 0.0
    for tf, weight in (("M30", 10.0), ("M15", 10.0), ("M5", 5.0)):
        ema_fast = _num(features.get(f"{tf}_ema_fast"))
        ema_slow = _num(features.get(f"{tf}_ema_slow"))
        ema_mid = _num(features.get(f"{tf}_ema_mid"))
        ema_long = _num(features.get(f"{tf}_ema_long"))
        rsi = _num(features.get(f"{tf}_rsi14"))
        close_ema_slow_atr = _num(features.get(f"{tf}_close_ema_slow_atr"))
        ema_slow_slope_atr = _num(features.get(f"{tf}_ema_slow_slope_atr"))
        if ema_fast is None or ema_slow is None:
            continue
        aligned = ema_fast > ema_slow if side == "buy" else ema_fast < ema_slow
        if aligned:
            score += weight * 0.35
        if rsi is not None:
            rsi_aligned = _rsi_supports_side(rsi, side)
            if rsi_aligned:
                score += weight * 0.20
        if close_ema_slow_atr is not None:
            price_aligned = close_ema_slow_atr > 0 if side == "buy" else close_ema_slow_atr < 0
            if price_aligned:
                score += weight * 0.18
        if ema_slow_slope_atr is not None:
            slope_aligned = ema_slow_slope_atr > 0 if side == "buy" else ema_slow_slope_atr < 0
            if slope_aligned:
                score += weight * 0.17
        if ema_mid is not None and ema_long is not None:
            macro_aligned = ema_mid > ema_long if side == "buy" else ema_mid < ema_long
            if macro_aligned:
                score += weight * 0.10

    htf_alignment_count = _num(features.get("htf_alignment_count")) or 0.0
    htf_slope_count = _num(features.get("htf_slope_count")) or 0.0
    swing_trend_score = _swing_trend_score(features, side, notes)
    score += swing_trend_score
    if htf_alignment_count >= 5 and htf_slope_count >= 3:
        notes.append("higher timeframe bias aligned")
    elif htf_alignment_count <= 2:
        notes.append("higher timeframe bias is weak")
    return min(score, 25.0)


def _structure_score(features: dict[str, float | int | str | bool | None], notes: list[str]) -> float:
    strength = max(_num(features.get("swing_strength_atr")) or 0.0, 0.0)
    distance = max(_num(features.get("distance_from_previous_swing_atr")) or 0.0, 0.0)
    score = min(strength * 8.0, 12.0) + min(distance * 2.0, 8.0)
    if strength >= 0.7:
        notes.append("clear swing")
    return min(score, 20.0)


def _entry_trigger_score(features: dict[str, float | int | str | bool | None], side: str, notes: list[str]) -> float:
    score = 0.0
    candle_body = _num(features.get("entry_body_atr")) or 0.0
    wick_reject = _num(features.get("rejection_wick_ratio")) or 0.0
    broke_trigger = bool(features.get("broke_trigger"))
    ema_reclaim = bool(features.get("ema_trigger"))

    if broke_trigger:
        score += 8.0
    if ema_reclaim:
        score += 5.0
    score += min(abs(candle_body) * 8.0, 4.0)
    score += min(wick_reject * 3.0, 3.0)
    if side == "sell" and (_num(features.get("entry_body")) or 0.0) < 0:
        score += 2.0
    if side == "buy" and (_num(features.get("entry_body")) or 0.0) > 0:
        score += 2.0
    if score >= 12:
        notes.append("entry trigger present")
    return min(score, 20.0)


def _risk_reward_score(features: dict[str, float | int | str | bool | None], profile: str, notes: list[str]) -> float:
    rr = _num(features.get("risk_reward")) or 0.0
    obstacle_count = _num(features.get("tp_obstacle_count")) or 0.0
    m5_obstacle_count = _num(features.get("M5_tp_obstacle_count")) or 0.0
    m15_obstacle_count = _num(features.get("M15_tp_obstacle_count")) or 0.0
    obstacle_count = max(obstacle_count, m5_obstacle_count, m15_obstacle_count)
    risk_atr = _num(features.get("risk_atr")) or 0.0
    rr_weight = 8.0 if profile in ("buy", "sell") else 12.0
    score = min(rr / 5.0, 1.0) * rr_weight
    if 0.4 <= risk_atr <= 2.5:
        score += 7.0
    elif risk_atr > 0:
        score += 3.0
    score += max(5.0 - min(obstacle_count, 5.0), 0.0)
    if obstacle_count == 0:
        notes.append("clear TP space")
    elif m5_obstacle_count > 0:
        notes.append("M5 swing obstacle before TP")
    elif m15_obstacle_count > 0:
        notes.append("M15 swing obstacle before TP")
    return min(score, 20.0)


def _cost_penalty(features: dict[str, float | int | str | bool | None], notes: list[str]) -> float:
    spread_r = _num(features.get("spread_r")) or 0.0
    penalty = -min(spread_r * 10.0, 15.0)
    if spread_r > 0.25:
        notes.append("spread is large versus risk")
    return penalty


def _chop_penalty(features: dict[str, float | int | str | bool | None], side: str, profile: str, notes: list[str]) -> float:
    penalty = 0.0
    ema_gap_atr = abs(_num(features.get("M5_ema_gap_atr")) or 0.0)
    alternating_ratio = _num(features.get("m1_alternating_ratio")) or 0.0
    if ema_gap_atr < 0.15:
        penalty -= 8.0
        notes.append("M5 EMA is flat/entangled")
    if alternating_ratio > 0.55:
        penalty -= min((alternating_ratio - 0.55) * 30.0, 12.0)
        notes.append("choppy recent M1 candles")
    if profile in ("buy", "sell"):
        penalty += _direction_context_penalty(features, side, notes)
    return max(penalty, -20.0)


def _direction_context_penalty(features: dict[str, float | int | str | bool | None], side: str, notes: list[str]) -> float:
    penalty = 0.0
    htf_alignment_count = _num(features.get("htf_alignment_count")) or 0.0
    htf_slope_count = _num(features.get("htf_slope_count")) or 0.0
    m5_gap = _num(features.get("M5_ema_gap_atr")) or 0.0
    m15_rsi = _num(features.get("M15_rsi14"))
    m30_rsi = _num(features.get("M30_rsi14"))
    m15_extension = _num(features.get("m15_extension_atr"))
    m30_extension = _num(features.get("m30_extension_atr"))
    m15_resistance = _num(features.get("M15_last_swing_high_distance_atr")) if side == "buy" else _num(features.get("M15_last_swing_low_distance_atr"))
    m30_resistance = _num(features.get("M30_last_swing_high_distance_atr")) if side == "buy" else _num(features.get("M30_last_swing_low_distance_atr"))

    if htf_alignment_count < 3:
        penalty -= 8.0
        notes.append("higher timeframe direction conflict")
    if htf_slope_count < 2:
        penalty -= 4.0
        notes.append("higher timeframe slope is weak")

    if side == "buy":
        if m15_rsi is not None and m15_rsi > 66:
            penalty -= min((m15_rsi - 66.0) * 0.5, 5.0)
            notes.append("M15 is overbought for buy")
        if m30_rsi is not None and m30_rsi > 70:
            penalty -= min((m30_rsi - 70.0) * 0.4, 4.0)
            notes.append("M30 is overbought for buy")
        if m5_gap > 0.75:
            penalty -= min((m5_gap - 0.75) * 4.0, 5.0)
            notes.append("M5 buy trend is extended")
    else:
        if m15_rsi is not None and m15_rsi < 34:
            penalty -= min((34.0 - m15_rsi) * 0.5, 5.0)
            notes.append("M15 is oversold for sell")
        if m30_rsi is not None and m30_rsi < 30:
            penalty -= min((30.0 - m30_rsi) * 0.4, 4.0)
            notes.append("M30 is oversold for sell")
        if m5_gap < -0.75:
            penalty -= min((-0.75 - m5_gap) * 4.0, 5.0)
            notes.append("M5 sell trend is extended")

    for value, label in ((m15_extension, "M15"), (m30_extension, "M30")):
        if value is None:
            continue
        if value > 2.0:
            penalty -= min((value - 2.0) * 2.5, 6.0)
            notes.append(f"{label} is extended in entry direction")
        elif value < -1.0:
            penalty -= min((-1.0 - value) * 3.0, 6.0)
            notes.append(f"{label} is against entry direction")
    for value, label in ((m15_resistance, "M15"), (m30_resistance, "M30")):
        if value is None:
            continue
        if 0.0 <= value < 0.6:
            penalty -= min((0.6 - value) * 4.0, 3.0)
            level = "resistance" if side == "buy" else "support"
            notes.append(f"{label} {level} is close")
    return penalty


def _swing_trend_score(features: dict[str, float | int | str | bool | None], side: str, notes: list[str]) -> float:
    score = 0.0
    for tf in ("M15", "M30"):
        high_trend = str(features.get(f"{tf}_swing_high_trend") or "")
        low_trend = str(features.get(f"{tf}_swing_low_trend") or "")
        if side == "buy":
            aligned_high = high_trend == "higher_high"
            aligned_low = low_trend == "higher_low"
            conflict_high = high_trend == "lower_high"
            conflict_low = low_trend == "lower_low"
        else:
            aligned_high = high_trend == "lower_high"
            aligned_low = low_trend == "lower_low"
            conflict_high = high_trend == "higher_high"
            conflict_low = low_trend == "higher_low"
        if aligned_high:
            score += 1.5
        if aligned_low:
            score += 1.5
        if aligned_high and aligned_low:
            notes.append(f"{tf} swing trend aligned")
        elif conflict_high and conflict_low:
            notes.append(f"{tf} swing trend conflicts")
    return min(score, 6.0)


def _rsi_supports_side(rsi: float, side: str) -> bool:
    if side == "buy":
        return 48.0 <= rsi <= 66.0
    return 34.0 <= rsi <= 52.0


def _num(value: float | int | str | bool | None) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
