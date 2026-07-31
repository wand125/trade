from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analysis.candidate_generator import generate_candidates
from analysis.economic_calendar import EconomicEvent, load_economic_calendar, parse_currencies
from analysis.market_data import Bar, MarketHistory, TIME_FORMAT, load_history
from analysis.models import Candidate
from analysis.rr_experiment import VARIABLE_POLICIES, parse_rr_values, select_variable_rr_candidates
from analysis.time_filters import blackout_reasons


def generate_signal(
    history: MarketHistory,
    *,
    snapshot: dict[str, Any] | None = None,
    strategy: str = "side_ladder",
    rr_values: list[float] | None = None,
    fixed_rr: float = 4.0,
    min_score: float = 50.0,
    side: str = "both",
    max_candidate_age_minutes: int = 30,
    valid_for_seconds: int = 120,
    max_entry_drift_atr: float = 0.75,
    score_profile: str = "side",
    exclude_blackout_times: bool = True,
    blackout_events: list[EconomicEvent] | tuple[EconomicEvent, ...] = (),
    news_before_minutes: int = 10,
    news_after_minutes: int = 10,
    news_min_impact: str = "high",
    news_currencies: tuple[str, ...] | list[str] | None = ("USD", "XAU", "ALL", "*"),
) -> dict[str, object]:
    bars = history.bars("M1")
    if not bars:
        return hold_payload(history, reason="No M1 bars available.")

    latest_bar = bars[-1]
    current_blackouts = blackout_reasons(
        latest_bar.time,
        events=blackout_events,
        news_before_minutes=news_before_minutes,
        news_after_minutes=news_after_minutes,
        news_min_impact=news_min_impact,
        news_currencies=news_currencies,
    )
    if exclude_blackout_times and current_blackouts:
        return hold_payload(
            history,
            latest_bar=latest_bar,
            reason="Current time is in no-entry window: " + "; ".join(current_blackouts),
        )
    candidates = strategy_candidates(
        history,
        strategy=strategy,
        rr_values=rr_values or [3.0, 4.0, 5.0],
        fixed_rr=fixed_rr,
        score_profile=score_profile,
        exclude_blackout_times=exclude_blackout_times,
        blackout_events=blackout_events,
        news_before_minutes=news_before_minutes,
        news_after_minutes=news_after_minutes,
        news_min_impact=news_min_impact,
        news_currencies=news_currencies,
    )
    candidates = [
        candidate
        for candidate in candidates
        if candidate.score >= min_score
        and (side == "both" or candidate.side == side)
        and 0 <= candidate_age_minutes(candidate, latest_bar) <= max_candidate_age_minutes
    ]
    if not candidates:
        return hold_payload(
            history,
            latest_bar=latest_bar,
            reason=f"No candidate within {max_candidate_age_minutes} minutes above score {min_score:g}.",
        )

    ranked = sorted(candidates, key=lambda candidate: signal_rank(candidate, latest_bar, snapshot), reverse=True)
    for candidate in ranked:
        price = current_entry_price(snapshot, latest_bar, candidate.side)
        drift_atr = entry_drift_atr(history, candidate, price)
        if drift_atr is None or drift_atr <= max_entry_drift_atr:
            return candidate_signal_payload(
                candidate,
                history,
                latest_bar=latest_bar,
                snapshot=snapshot,
                current_price=price,
                valid_for_seconds=max(1, min(valid_for_seconds, remaining_valid_seconds(candidate, latest_bar, max_candidate_age_minutes))),
                max_entry_drift_atr=max_entry_drift_atr,
            )

    best = ranked[0]
    current_price = current_entry_price(snapshot, latest_bar, best.side)
    drift_atr = entry_drift_atr(history, best, current_price)
    return hold_payload(
        history,
        latest_bar=latest_bar,
        reason=f"Best candidate is stale by price drift: {drift_atr:.2f} ATR from candidate entry.",
    )


def strategy_candidates(
    history: MarketHistory,
    *,
    strategy: str,
    rr_values: list[float],
    fixed_rr: float,
    score_profile: str,
    exclude_blackout_times: bool,
    blackout_events: list[EconomicEvent] | tuple[EconomicEvent, ...],
    news_before_minutes: int,
    news_after_minutes: int,
    news_min_impact: str,
    news_currencies: tuple[str, ...] | list[str] | None,
) -> list[Candidate]:
    if strategy == "fixed":
        return generate_candidates(
            history,
            risk_reward=fixed_rr,
            score_profile=score_profile,
            exclude_blackout_times=exclude_blackout_times,
            blackout_events=blackout_events,
            news_before_minutes=news_before_minutes,
            news_after_minutes=news_after_minutes,
            news_min_impact=news_min_impact,
            news_currencies=news_currencies,
        )
    if strategy not in VARIABLE_POLICIES:
        raise ValueError(f"Unknown strategy: {strategy}")
    candidate_sets = {
        rr: generate_candidates(
            history,
            risk_reward=rr,
            min_score=None,
            score_profile=score_profile,
            exclude_blackout_times=exclude_blackout_times,
            blackout_events=blackout_events,
            news_before_minutes=news_before_minutes,
            news_after_minutes=news_after_minutes,
            news_min_impact=news_min_impact,
            news_currencies=news_currencies,
        )
        for rr in sorted(set(rr_values))
    }
    return select_variable_rr_candidates(candidate_sets, strategy)


def candidate_signal_payload(
    candidate: Candidate,
    history: MarketHistory,
    *,
    latest_bar: Bar,
    snapshot: dict[str, Any] | None,
    current_price: float,
    valid_for_seconds: int,
    max_entry_drift_atr: float,
) -> dict[str, object]:
    spread_price = history.spread_points * history.point
    atr = latest_atr(history)
    tolerance = max(spread_price, (atr or 0.0) * 0.15, history.point * 10)
    entry_low = current_price - tolerance
    entry_high = current_price + tolerance
    drift_atr = entry_drift_atr(history, candidate, current_price)
    risk_notes = risk_notes_for(candidate, history, drift_atr=drift_atr, max_entry_drift_atr=max_entry_drift_atr)
    payload: dict[str, object] = {
        "ok": True,
        "mode": "manual_review",
        "action": candidate.side,
        "symbol": candidate.symbol,
        "generated_at": datetime.now().strftime(TIME_FORMAT),
        "history_server_time": history.server_time,
        "latest_bar_time": latest_bar.time_text,
        "candidate_time": candidate.time_text,
        "candidate_age_minutes": round(candidate_age_minutes(candidate, latest_bar), 2),
        "entry_low": round_price(entry_low, history),
        "entry_high": round_price(entry_high, history),
        "candidate_entry": round_price(candidate.entry, history),
        "current_entry_reference": round_price(current_price, history),
        "stop_loss": round_price(candidate.sl, history),
        "take_profit": round_price(candidate.tp, history),
        "risk": round_price(candidate.risk, history),
        "risk_reward": round(candidate.risk_reward, 2),
        "score": round(candidate.score, 2),
        "pattern": candidate.pattern,
        "valid_for_seconds": valid_for_seconds,
        "reason": reason_for(candidate),
        "risk_notes": risk_notes,
        "score_parts": candidate.score_parts,
        "features": selected_features(candidate),
        "snapshot_time": str(snapshot.get("server_time", "")) if snapshot else "",
    }
    return payload


def hold_payload(history: MarketHistory, *, latest_bar: Bar | None = None, reason: str) -> dict[str, object]:
    return {
        "ok": True,
        "mode": "manual_review",
        "action": "hold",
        "symbol": history.symbol,
        "generated_at": datetime.now().strftime(TIME_FORMAT),
        "history_server_time": history.server_time,
        "latest_bar_time": latest_bar.time_text if latest_bar else "",
        "entry_low": None,
        "entry_high": None,
        "stop_loss": None,
        "take_profit": None,
        "risk_reward": None,
        "score": 0.0,
        "pattern": None,
        "valid_for_seconds": 30,
        "reason": reason,
        "risk_notes": ["No order is sent. Manual review only."],
    }


def risk_notes_for(
    candidate: Candidate,
    history: MarketHistory,
    *,
    drift_atr: float | None,
    max_entry_drift_atr: float,
) -> list[str]:
    notes = ["No order is sent. Manual review only."]
    notes.append(f"spread is {history.spread_points} points")
    if drift_atr is not None:
        notes.append(f"current price drift is {drift_atr:.2f} ATR from candidate entry")
        if drift_atr > max_entry_drift_atr * 0.7:
            notes.append("entry price is close to the drift limit")
    score_notes = str(candidate.score_parts.get("notes", ""))
    for note in [item.strip() for item in score_notes.split(";") if item.strip()]:
        if note not in notes:
            notes.append(note)
    if candidate.side == "buy":
        notes.append("invalidate manually if price loses the latest M1 swing low/EMA trigger")
    else:
        notes.append("invalidate manually if price reclaims the latest M1 swing high/EMA trigger")
    return notes


def selected_features(candidate: Candidate) -> dict[str, object]:
    names = (
        "htf_alignment_count",
        "htf_slope_count",
        "M5_ema_gap_atr",
        "M15_rsi14",
        "M30_rsi14",
        "m15_extension_atr",
        "m30_extension_atr",
        "risk_atr",
        "spread_r",
        "tp_obstacle_count",
        "M5_tp_obstacle_count",
        "M5_nearest_tp_obstacle_price",
        "M5_nearest_tp_obstacle_distance_atr",
        "M15_tp_obstacle_count",
        "M15_nearest_tp_obstacle_price",
        "M15_nearest_tp_obstacle_distance_atr",
        "M15_last_swing_high_distance_atr",
        "M15_last_swing_low_distance_atr",
        "M30_last_swing_high_distance_atr",
        "M30_last_swing_low_distance_atr",
        "rejection_wick_ratio",
        "broke_trigger",
        "ema_trigger",
    )
    return {name: candidate.features.get(name) for name in names if name in candidate.features}


def reason_for(candidate: Candidate) -> str:
    side_label = "Buy" if candidate.side == "buy" else "Sell"
    return (
        f"{side_label} {candidate.pattern}: score {candidate.score:.1f}, "
        f"RR {candidate.risk_reward:g}, swing {candidate.swing_kind} at {candidate.swing_price:.2f}."
    )


def signal_rank(candidate: Candidate, latest_bar: Bar, snapshot: dict[str, Any] | None) -> tuple[float, float, float]:
    age = candidate_age_minutes(candidate, latest_bar)
    price = current_entry_price(snapshot, latest_bar, candidate.side)
    drift = entry_drift_value(candidate, price)
    return (candidate.score, -age, -drift)


def candidate_age_minutes(candidate: Candidate, latest_bar: Bar) -> float:
    return (latest_bar.time - candidate.time).total_seconds() / 60.0


def remaining_valid_seconds(candidate: Candidate, latest_bar: Bar, max_candidate_age_minutes: int) -> int:
    elapsed = max(0.0, candidate_age_minutes(candidate, latest_bar) * 60.0)
    return int(max_candidate_age_minutes * 60 - elapsed)


def current_entry_price(snapshot: dict[str, Any] | None, latest_bar: Bar, side: str) -> float:
    if snapshot:
        key = "ask" if side == "buy" else "bid"
        value = snapshot.get(key)
        if value is not None:
            try:
                return float(value)
            except (TypeError, ValueError):
                pass
    return latest_bar.close


def entry_drift_value(candidate: Candidate, current_price: float) -> float:
    return abs(current_price - candidate.entry)


def entry_drift_atr(history: MarketHistory, candidate: Candidate, current_price: float) -> float | None:
    atr = latest_atr(history)
    if atr is None or atr <= 0:
        return None
    return entry_drift_value(candidate, current_price) / atr


def latest_atr(history: MarketHistory) -> float | None:
    series = history.indicator("M1", "atr14")
    for value in reversed(series):
        if value is not None:
            return float(value)
    return None


def round_price(value: float, history: MarketHistory) -> float:
    digits = 2
    if history.point > 0:
        text = f"{history.point:.10f}".rstrip("0")
        if "." in text:
            digits = len(text.split(".", 1)[1])
    return round(value, digits)


def load_snapshot(path: str | Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    snapshot_path = Path(path)
    if not snapshot_path.exists():
        return None
    with snapshot_path.open(encoding="utf-8") as f:
        return json.load(f)


def write_signal(path: str | Path, payload: dict[str, object]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a manual-review trading signal from latest MT5 bridge history.")
    parser.add_argument("--history", default="runtime/latest_history_168h.json")
    parser.add_argument("--snapshot", default="runtime/latest_snapshot.json")
    parser.add_argument("--output", default="runtime/latest_signal.json")
    parser.add_argument("--strategy", choices=("fixed", *VARIABLE_POLICIES), default="side_ladder")
    parser.add_argument("--rr-values", type=parse_rr_values, default=parse_rr_values("3,4,5"))
    parser.add_argument("--fixed-rr", type=float, default=4.0)
    parser.add_argument("--min-score", type=float, default=50.0)
    parser.add_argument("--side", choices=("buy", "sell", "both"), default="both")
    parser.add_argument("--max-candidate-age-minutes", type=int, default=30)
    parser.add_argument("--valid-for-seconds", type=int, default=120)
    parser.add_argument("--max-entry-drift-atr", type=float, default=0.75)
    parser.add_argument("--score-profile", choices=("side", "balanced", "buy", "sell"), default="side")
    parser.add_argument("--include-blackout-times", action="store_true", help="Allow signals during rollover/news-proxy no-entry windows.")
    parser.add_argument("--calendar", default="runtime/economic_calendar.json", help="Optional economic calendar JSON/CSV in MT5 server time.")
    parser.add_argument("--calendar-input-utc-offset", type=float, default=None, help="UTC offset of naive calendar times, e.g. 9 for JST. Omit when calendar is already MT5 server time.")
    parser.add_argument("--calendar-server-utc-offset", type=float, default=None, help="MT5 server UTC offset used when converting calendar times.")
    parser.add_argument("--news-before-minutes", type=int, default=10)
    parser.add_argument("--news-after-minutes", type=int, default=10)
    parser.add_argument("--news-min-impact", default="high", choices=("low", "medium", "high"))
    parser.add_argument("--news-currencies", default="USD,XAU,ALL")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    history = load_history(args.history)
    snapshot = load_snapshot(args.snapshot)
    calendar_events = load_economic_calendar(
        args.calendar,
        input_utc_offset_hours=args.calendar_input_utc_offset,
        server_utc_offset_hours=args.calendar_server_utc_offset,
    )
    payload = generate_signal(
        history,
        snapshot=snapshot,
        strategy=args.strategy,
        rr_values=args.rr_values,
        fixed_rr=args.fixed_rr,
        min_score=args.min_score,
        side=args.side,
        max_candidate_age_minutes=args.max_candidate_age_minutes,
        valid_for_seconds=args.valid_for_seconds,
        max_entry_drift_atr=args.max_entry_drift_atr,
        score_profile=args.score_profile,
        exclude_blackout_times=not args.include_blackout_times,
        blackout_events=calendar_events,
        news_before_minutes=args.news_before_minutes,
        news_after_minutes=args.news_after_minutes,
        news_min_impact=args.news_min_impact,
        news_currencies=parse_currencies(args.news_currencies),
    )
    write_signal(args.output, payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
