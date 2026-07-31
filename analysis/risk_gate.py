from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any


TIME_FORMAT_SECONDS = "%Y.%m.%d %H:%M:%S"
TIME_FORMAT_MINUTES = "%Y.%m.%d %H:%M"


@dataclass(frozen=True)
class RiskGateResult:
    allowed: bool
    reasons: list[str]
    metrics: dict[str, object]

    def as_dict(self) -> dict[str, object]:
        return {
            "allowed": self.allowed,
            "reasons": self.reasons,
            "metrics": self.metrics,
        }


def evaluate_risk_gate(
    *,
    account_payload: dict[str, Any] | None = None,
    deal_history_payload: dict[str, Any] | None = None,
    symbol: str = "XAUUSD-m",
    max_open_positions: int = 3,
    new_order_volume: float = 0.0,
    max_total_volume: float = 0.3,
    daily_loss_limit: float = 5000.0,
    consecutive_loss_limit: int = 20,
    consecutive_loss_cooldown_minutes: int = 120,
) -> RiskGateResult:
    positions = open_positions(account_payload, symbol)
    new_order_position_count = 1 if number(new_order_volume) > 0 else 0
    projected_open_positions = len(positions) + new_order_position_count
    current_volume = sum_position_volume(positions)
    projected_volume = current_volume + max(0.0, number(new_order_volume))
    deals = closed_deals(account_payload, deal_history_payload, symbol)
    server_time = current_server_time(account_payload, deal_history_payload)
    server_day = server_time.date() if server_time else None
    daily_pnl = realized_pnl_for_day(deals, server_day) if server_day else 0.0
    losses = consecutive_losses(deals)
    latest_loss_time = latest_consecutive_loss_time(deals)
    cooldown_until = consecutive_loss_cooldown_until(
        latest_loss_time,
        losses=losses,
        consecutive_loss_limit=consecutive_loss_limit,
        consecutive_loss_cooldown_minutes=consecutive_loss_cooldown_minutes,
    )
    cooldown_active = bool(cooldown_until and server_time and server_time < cooldown_until)
    reasons: list[str] = []

    if len(positions) > max_open_positions:
        reasons.append(f"open positions {len(positions)} exceed limit {max_open_positions}")
    if new_order_position_count and projected_open_positions > max_open_positions:
        reasons.append(
            f"projected open positions {projected_open_positions} exceed limit {max_open_positions}"
        )
    if max_total_volume > 0 and projected_volume > max_total_volume + 1e-9:
        reasons.append(f"projected volume {projected_volume:.2f} exceeds limit {max_total_volume:.2f}")
    if daily_loss_limit > 0 and daily_pnl <= -abs(daily_loss_limit):
        reasons.append(f"daily realized P/L {daily_pnl:.0f} is below stop {-abs(daily_loss_limit):.0f}")
    if consecutive_loss_limit > 0 and losses >= consecutive_loss_limit:
        if consecutive_loss_cooldown_minutes <= 0:
            reasons.append(f"consecutive losses {losses} reached limit {consecutive_loss_limit}")
        elif not server_time or not cooldown_until:
            reasons.append(f"consecutive losses {losses} reached limit {consecutive_loss_limit}; cooldown time is unknown")
        elif cooldown_active:
            reasons.append(
                "consecutive loss cooldown active "
                f"{losses} >= {consecutive_loss_limit} until {cooldown_until.strftime(TIME_FORMAT_SECONDS)}"
            )

    metrics = {
        "symbol": symbol,
        "open_positions": len(positions),
        "max_open_positions": max_open_positions,
        "new_order_position_count": new_order_position_count,
        "projected_open_positions": projected_open_positions,
        "current_volume": round(current_volume, 2),
        "new_order_volume": round(max(0.0, number(new_order_volume)), 2),
        "projected_volume": round(projected_volume, 2),
        "max_total_volume": max_total_volume,
        "server_day": server_day.isoformat() if server_day else "",
        "daily_realized_pnl": round(daily_pnl, 2),
        "daily_loss_limit": daily_loss_limit,
        "consecutive_losses": losses,
        "consecutive_loss_limit": consecutive_loss_limit,
        "consecutive_loss_cooldown_minutes": consecutive_loss_cooldown_minutes,
        "consecutive_loss_cooldown_until": cooldown_until.strftime(TIME_FORMAT_SECONDS) if cooldown_until else "",
        "consecutive_loss_cooldown_active": cooldown_active,
        "closed_deals_count": len(deals),
    }
    return RiskGateResult(allowed=not reasons, reasons=reasons, metrics=metrics)


def open_positions(account_payload: dict[str, Any] | None, symbol: str) -> list[dict[str, Any]]:
    if not account_payload:
        return []
    account = account_payload.get("account") if isinstance(account_payload.get("account"), dict) else account_payload
    positions = account.get("positions") if isinstance(account, dict) else []
    if not isinstance(positions, list):
        return []
    return [position for position in positions if isinstance(position, dict) and str(position.get("symbol", symbol)) == symbol]


def sum_position_volume(positions: list[dict[str, Any]]) -> float:
    return sum(number(position.get("volume")) for position in positions)


def closed_deals(
    account_payload: dict[str, Any] | None,
    deal_history_payload: dict[str, Any] | None,
    symbol: str,
) -> list[dict[str, Any]]:
    raw_deals: list[dict[str, Any]] = []
    for payload in (deal_history_payload, account_payload):
        if not payload:
            continue
        if payload is account_payload and isinstance(payload.get("account"), dict):
            deals = payload["account"].get("deals", [])
        else:
            deals = payload.get("deals", [])
        if isinstance(deals, list):
            raw_deals.extend(deal for deal in deals if isinstance(deal, dict))

    by_ticket: dict[str, dict[str, Any]] = {}
    for deal in raw_deals:
        if str(deal.get("symbol", symbol)) != symbol:
            continue
        if str(deal.get("entry", "")).lower() != "out":
            continue
        ticket = str(deal.get("ticket", f"{deal.get('time')}:{deal.get('price')}"))
        by_ticket[ticket] = deal
    return sorted(by_ticket.values(), key=lambda deal: parse_time(str(deal.get("time", ""))) or datetime.min, reverse=True)


def current_server_time(
    account_payload: dict[str, Any] | None,
    deal_history_payload: dict[str, Any] | None,
) -> datetime | None:
    for payload in (account_payload, deal_history_payload):
        if not payload:
            continue
        parsed = parse_time(str(payload.get("server_time", "")))
        if parsed:
            return parsed
    return None


def realized_pnl_for_day(deals: list[dict[str, Any]], day) -> float:
    total = 0.0
    for deal in deals:
        moment = parse_time(str(deal.get("time", "")))
        if not moment or moment.date() != day:
            continue
        total += deal_profit(deal)
    return total


def consecutive_losses(deals: list[dict[str, Any]]) -> int:
    count = 0
    for deal in deals:
        profit = deal_profit(deal)
        if profit < 0:
            count += 1
            continue
        if profit > 0:
            break
    return count


def latest_consecutive_loss_time(deals: list[dict[str, Any]]) -> datetime | None:
    for deal in deals:
        profit = deal_profit(deal)
        if profit < 0:
            return parse_time(str(deal.get("time", "")))
        if profit > 0:
            return None
    return None


def consecutive_loss_cooldown_until(
    latest_loss_time: datetime | None,
    *,
    losses: int,
    consecutive_loss_limit: int,
    consecutive_loss_cooldown_minutes: int,
) -> datetime | None:
    if losses < consecutive_loss_limit or consecutive_loss_limit <= 0 or consecutive_loss_cooldown_minutes <= 0:
        return None
    if latest_loss_time is None:
        return None
    return latest_loss_time + timedelta(minutes=consecutive_loss_cooldown_minutes)


def deal_profit(deal: dict[str, Any]) -> float:
    return number(deal.get("profit")) + number(deal.get("commission")) + number(deal.get("swap"))


def parse_time(value: str) -> datetime | None:
    for fmt in (TIME_FORMAT_SECONDS, TIME_FORMAT_MINUTES):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def number(value: object) -> float:
    if value is None or isinstance(value, bool):
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
