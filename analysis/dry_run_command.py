from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analysis.economic_calendar import EconomicEvent, load_economic_calendar, parse_currencies
from analysis.position_sizing import (
    PositionSize,
    estimate_price_value_per_lot,
    position_size_from_signal,
)
from analysis.risk_gate import RiskGateResult, evaluate_risk_gate, parse_time
from analysis.time_filters import blackout_reasons


def command_from_signal(
    signal: dict[str, Any],
    *,
    volume: float = 0.1,
    max_spread_points: int = 80,
    expires_in_seconds: int = 30,
    min_score: float = 50.0,
    comment: str = "codex signal dry-run",
    risk_gate: RiskGateResult | None = None,
    position_size: PositionSize | None = None,
    lot_policy: dict[str, object] | None = None,
    reject_blackout_times: bool = True,
    blackout_events: list[EconomicEvent] | tuple[EconomicEvent, ...] = (),
    news_before_minutes: int = 10,
    news_after_minutes: int = 10,
    news_min_impact: str = "high",
    news_currencies: tuple[str, ...] | list[str] | None = ("USD", "XAU", "ALL", "*"),
) -> dict[str, Any]:
    if position_size is not None:
        volume = position_size.volume
    lot_policy_payload = lot_policy or build_lot_policy(volume=volume, position_size=position_size)
    rejection = validate_signal_for_command(
        signal,
        volume=volume,
        expires_in_seconds=expires_in_seconds,
        min_score=min_score,
        reject_blackout_times=reject_blackout_times,
        blackout_events=blackout_events,
        news_before_minutes=news_before_minutes,
        news_after_minutes=news_after_minutes,
        news_min_impact=news_min_impact,
        news_currencies=news_currencies,
    )
    if not rejection and risk_gate is not None and not risk_gate.allowed:
        rejection = "risk gate rejected command: " + "; ".join(risk_gate.reasons)
    if rejection:
        return rejected_command(
            signal,
            rejection,
            risk_gate=risk_gate,
            position_size=position_size,
            lot_policy=lot_policy_payload,
        )

    now = int(time.time())
    action = str(signal["action"]).lower()
    command = {
        "id": uuid.uuid4().hex,
        "status": "pending",
        "created_at": now,
        "expires_at": now + expires_in_seconds,
        "action": action,
        "symbol": str(signal.get("symbol") or "XAUUSD-m"),
        "volume": volume,
        "sl": float(signal["stop_loss"]),
        "tp": float(signal["take_profit"]),
        "ticket": None,
        "max_spread_points": max_spread_points,
        "dry_run": True,
        "comment": comment,
        "reason": command_reason(signal),
        "risk_gate": risk_gate.as_dict() if risk_gate else None,
        "position_size": position_size.as_dict() if position_size else None,
        "lot_policy": lot_policy_payload,
        "source_signal": source_signal_summary(signal, action=action),
    }
    return command


def build_lot_policy(
    *,
    volume: float,
    position_size: PositionSize | None = None,
    max_total_volume: float = 0.3,
) -> dict[str, object]:
    min_volume = position_size.min_volume if position_size else 0.1
    max_order_volume = position_size.max_volume if position_size else 0.1
    return {
        "mode": "risk_sized_min_0.1" if position_size else "fixed_baseline_0.1",
        "order_volume": round(float(volume), 2),
        "base_volume": 0.1,
        "min_volume": min_volume,
        "max_order_volume": max_order_volume,
        "max_total_volume": max_total_volume,
        "note": "0.1 lot is the baseline; averaging is capped by max_total_volume.",
    }


def validate_signal_for_command(
    signal: dict[str, Any],
    *,
    volume: float,
    expires_in_seconds: int,
    min_score: float,
    reject_blackout_times: bool = True,
    blackout_events: list[EconomicEvent] | tuple[EconomicEvent, ...] = (),
    news_before_minutes: int = 10,
    news_after_minutes: int = 10,
    news_min_impact: str = "high",
    news_currencies: tuple[str, ...] | list[str] | None = ("USD", "XAU", "ALL", "*"),
) -> str | None:
    action = str(signal.get("action", "")).lower()
    if action not in {"buy", "sell"}:
        return f"signal action is not tradable: {action or '(missing)'}"
    if signal.get("mode") != "manual_review":
        return "signal mode must be manual_review"
    if volume <= 0:
        return "volume must be positive"
    if expires_in_seconds < 5 or expires_in_seconds > 300:
        return "expires_in_seconds must be between 5 and 300"
    score = _float(signal.get("score"))
    if score is None or score < min_score:
        return f"signal score below minimum: {score}"
    sl = _float(signal.get("stop_loss"))
    tp = _float(signal.get("take_profit"))
    reference = _float(signal.get("current_entry_reference")) or _mid_entry(signal)
    if sl is None or tp is None or reference is None:
        return "signal requires stop_loss, take_profit, and entry reference"
    if action == "buy" and not (sl < reference < tp):
        return "invalid buy SL/TP around entry reference"
    if action == "sell" and not (tp < reference < sl):
        return "invalid sell SL/TP around entry reference"
    expiration_rejection = signal_expiration_rejection(signal)
    if expiration_rejection:
        return expiration_rejection
    if reject_blackout_times:
        reasons = signal_blackout_reasons(
            signal,
            blackout_events=blackout_events,
            news_before_minutes=news_before_minutes,
            news_after_minutes=news_after_minutes,
            news_min_impact=news_min_impact,
            news_currencies=news_currencies,
        )
        if reasons:
            return "signal candidate time is in no-entry window: " + "; ".join(reasons)
    return None


def signal_expiration_rejection(signal: dict[str, Any], *, now: datetime | None = None) -> str | None:
    try:
        valid_for_seconds = int(signal.get("valid_for_seconds") or 0)
    except (TypeError, ValueError):
        valid_for_seconds = 0
    if valid_for_seconds <= 0:
        return "signal is no longer valid"

    generated_value = signal.get("generated_at")
    if not generated_value:
        return None
    generated_at = parse_time(str(generated_value))
    if generated_at is None:
        return None
    expires_at = generated_at + timedelta(seconds=valid_for_seconds)
    current_time = now or datetime.now()
    if current_time > expires_at:
        return f"signal expired at {expires_at.strftime('%Y.%m.%d %H:%M:%S')}"
    return None


def signal_blackout_reasons(
    signal: dict[str, Any],
    *,
    blackout_events: list[EconomicEvent] | tuple[EconomicEvent, ...] = (),
    news_before_minutes: int = 10,
    news_after_minutes: int = 10,
    news_min_impact: str = "high",
    news_currencies: tuple[str, ...] | list[str] | None = ("USD", "XAU", "ALL", "*"),
) -> list[str]:
    for key in ("candidate_time", "latest_bar_time", "generated_at"):
        value = signal.get(key)
        if not value:
            continue
        moment = parse_time(str(value))
        if moment:
            return blackout_reasons(
                moment,
                events=blackout_events,
                news_before_minutes=news_before_minutes,
                news_after_minutes=news_after_minutes,
                news_min_impact=news_min_impact,
                news_currencies=news_currencies,
            )
    return []


def rejected_command(
    signal: dict[str, Any],
    reason: str,
    *,
    risk_gate: RiskGateResult | None = None,
    position_size: PositionSize | None = None,
    lot_policy: dict[str, object] | None = None,
) -> dict[str, Any]:
    action = str(signal.get("action", "hold")).lower()
    return {
        "id": uuid.uuid4().hex,
        "status": "rejected",
        "created_at": int(time.time()),
        "action": action,
        "symbol": str(signal.get("symbol") or ""),
        "dry_run": True,
        "reason": reason,
        "risk_gate": risk_gate.as_dict() if risk_gate else None,
        "position_size": position_size.as_dict() if position_size else None,
        "lot_policy": lot_policy or build_lot_policy(volume=0.0),
        "source_signal": source_signal_summary(signal, action=action),
    }


def source_signal_summary(signal: dict[str, Any], *, action: str | None = None) -> dict[str, object]:
    return {
        "action": action if action is not None else str(signal.get("action", "")).lower(),
        "mode": signal.get("mode"),
        "score": signal.get("score"),
        "risk_reward": signal.get("risk_reward"),
        "pattern": signal.get("pattern"),
        "generated_at": signal.get("generated_at"),
        "valid_for_seconds": signal.get("valid_for_seconds"),
        "candidate_time": signal.get("candidate_time"),
        "latest_bar_time": signal.get("latest_bar_time"),
        "history_server_time": signal.get("history_server_time"),
    }


def command_reason(signal: dict[str, Any]) -> str:
    reason = str(signal.get("reason") or "")
    score = signal.get("score")
    rr = signal.get("risk_reward")
    return f"signal dry-run; score={score}; rr={rr}; {reason}".strip()


def load_json(path: str | Path) -> dict[str, Any]:
    with Path(path).open(encoding="utf-8") as f:
        payload = json.load(f)
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def load_optional_json(path: str | Path | None) -> dict[str, Any] | None:
    if not path:
        return None
    json_path = Path(path)
    if not json_path.exists():
        return None
    return load_json(json_path)


def write_command(path: str | Path, command: dict[str, Any], *, replace: bool = False) -> None:
    output = Path(path)
    if output.exists() and not replace:
        existing = load_json(output)
        if existing.get("status") == "pending":
            raise RuntimeError(f"pending command already exists at {output}; use --replace to overwrite")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(command, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _mid_entry(signal: dict[str, Any]) -> float | None:
    low = _float(signal.get("entry_low"))
    high = _float(signal.get("entry_high"))
    if low is None or high is None:
        return None
    return (low + high) / 2.0


def _float(value: object) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a dry-run MT5 trade command from latest manual-review signal.")
    parser.add_argument("--signal", default="runtime/latest_signal.json")
    parser.add_argument("--output", default="runtime/trade_command.json")
    parser.add_argument("--volume", type=float, default=0.1)
    parser.add_argument("--risk-percent", type=float, default=0.0, help="If positive, size volume from equity and SL distance.")
    parser.add_argument("--price-value-per-lot", type=float, default=0.0, help="Account-currency P/L for a 1.00 price move at 1.0 lot. If omitted, estimate from deal history.")
    parser.add_argument("--volume-step", type=float, default=0.01)
    parser.add_argument("--min-volume", type=float, default=0.1)
    parser.add_argument("--max-volume", type=float, default=0.1, help="Default caps one command at the current 0.1 lot baseline.")
    parser.add_argument("--max-spread-points", type=int, default=80)
    parser.add_argument("--expires-in-seconds", type=int, default=30)
    parser.add_argument("--min-score", type=float, default=50.0)
    parser.add_argument("--comment", default="codex signal dry-run")
    parser.add_argument("--account", default="runtime/latest_account.json")
    parser.add_argument("--deal-history", default="runtime/latest_deal_history.json")
    parser.add_argument("--max-open-positions", type=int, default=3)
    parser.add_argument("--max-total-volume", type=float, default=0.3)
    parser.add_argument("--daily-loss-limit", type=float, default=5000.0)
    parser.add_argument("--consecutive-loss-limit", type=int, default=20)
    parser.add_argument("--consecutive-loss-cooldown-minutes", type=int, default=120)
    parser.add_argument("--skip-risk-gate", action="store_true")
    parser.add_argument("--include-blackout-times", action="store_true", help="Do not reject signals in rollover/news-proxy no-entry windows.")
    parser.add_argument("--calendar", default="runtime/economic_calendar.json", help="Optional economic calendar JSON/CSV in MT5 server time.")
    parser.add_argument("--calendar-input-utc-offset", type=float, default=None, help="UTC offset of naive calendar times, e.g. 9 for JST. Omit when calendar is already MT5 server time.")
    parser.add_argument("--calendar-server-utc-offset", type=float, default=None, help="MT5 server UTC offset used when converting calendar times.")
    parser.add_argument("--news-before-minutes", type=int, default=10)
    parser.add_argument("--news-after-minutes", type=int, default=10)
    parser.add_argument("--news-min-impact", default="high", choices=("low", "medium", "high"))
    parser.add_argument("--news-currencies", default="USD,XAU,ALL")
    parser.add_argument("--replace", action="store_true", help="Overwrite an existing pending command.")
    parser.add_argument("--write-rejections", action="store_true", help="Write rejected command records instead of only printing them.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    signal = load_json(args.signal)
    account_payload = load_optional_json(args.account)
    deal_history_payload = load_optional_json(args.deal_history)
    calendar_events = load_economic_calendar(
        args.calendar,
        input_utc_offset_hours=args.calendar_input_utc_offset,
        server_utc_offset_hours=args.calendar_server_utc_offset,
    )
    position_size = None
    sizing_rejection = None
    volume = args.volume
    if args.risk_percent > 0:
        try:
            price_value_per_lot = args.price_value_per_lot or estimate_price_value_per_lot(
                account_payload=account_payload,
                deal_history_payload=deal_history_payload,
                symbol=str(signal.get("symbol") or "XAUUSD-m"),
            )
            position_size = position_size_from_signal(
                signal,
                account_payload=account_payload,
                risk_percent=args.risk_percent,
                price_value_per_lot=price_value_per_lot,
                volume_step=args.volume_step,
                min_volume=args.min_volume,
                max_volume=args.max_volume,
            )
            volume = position_size.volume
        except ValueError as exc:
            sizing_rejection = f"position sizing failed: {exc}"
    risk_gate = None
    if not args.skip_risk_gate:
        risk_gate = evaluate_risk_gate(
            account_payload=account_payload,
            deal_history_payload=deal_history_payload,
            symbol=str(signal.get("symbol") or "XAUUSD-m"),
            max_open_positions=args.max_open_positions,
            new_order_volume=volume,
            max_total_volume=args.max_total_volume,
            daily_loss_limit=args.daily_loss_limit,
            consecutive_loss_limit=args.consecutive_loss_limit,
            consecutive_loss_cooldown_minutes=args.consecutive_loss_cooldown_minutes,
        )
    lot_policy = build_lot_policy(
        volume=volume,
        position_size=position_size,
        max_total_volume=args.max_total_volume,
    )
    if sizing_rejection and args.risk_percent > 0:
        lot_policy = {
            **lot_policy,
            "mode": "risk_sizing_rejected_min_0.1",
            "risk_percent": args.risk_percent,
        }
    if sizing_rejection:
        command = rejected_command(signal, sizing_rejection, risk_gate=risk_gate, lot_policy=lot_policy)
    else:
        command = command_from_signal(
            signal,
            volume=volume,
            max_spread_points=args.max_spread_points,
            expires_in_seconds=args.expires_in_seconds,
            min_score=args.min_score,
            comment=args.comment,
            risk_gate=risk_gate,
            position_size=position_size,
            lot_policy=lot_policy,
            reject_blackout_times=not args.include_blackout_times,
            blackout_events=calendar_events,
            news_before_minutes=args.news_before_minutes,
            news_after_minutes=args.news_after_minutes,
            news_min_impact=args.news_min_impact,
            news_currencies=parse_currencies(args.news_currencies),
        )
    if command["status"] == "rejected" and not args.write_rejections:
        print(json.dumps(command, ensure_ascii=False, indent=2))
        print("not written: rejected signal")
        return 2
    write_command(args.output, command, replace=args.replace)
    print(json.dumps(command, ensure_ascii=False, indent=2))
    print(f"wrote {args.output}")
    return 0 if command["status"] == "pending" else 2


if __name__ == "__main__":
    raise SystemExit(main())
