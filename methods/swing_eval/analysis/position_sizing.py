from __future__ import annotations

import math
import statistics
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from analysis.risk_gate import deal_profit, parse_time


@dataclass(frozen=True)
class PositionSize:
    volume: float
    raw_volume: float
    risk_amount: float
    stop_distance: float
    loss_at_volume: float
    price_value_per_lot: float
    risk_percent: float
    equity: float
    volume_step: float
    min_volume: float
    max_volume: float

    def as_dict(self) -> dict[str, object]:
        return {
            "volume": self.volume,
            "raw_volume": round(self.raw_volume, 6),
            "risk_amount": round(self.risk_amount, 2),
            "stop_distance": round(self.stop_distance, 5),
            "loss_at_volume": round(self.loss_at_volume, 2),
            "price_value_per_lot": round(self.price_value_per_lot, 6),
            "risk_percent": self.risk_percent,
            "equity": round(self.equity, 2),
            "volume_step": self.volume_step,
            "min_volume": self.min_volume,
            "max_volume": self.max_volume,
        }


def calculate_position_size(
    *,
    entry: float,
    stop_loss: float,
    equity: float,
    risk_percent: float,
    price_value_per_lot: float,
    volume_step: float = 0.01,
    min_volume: float = 0.1,
    max_volume: float = 0.1,
) -> PositionSize:
    if equity <= 0:
        raise ValueError("equity must be positive")
    if risk_percent <= 0:
        raise ValueError("risk_percent must be positive")
    if price_value_per_lot <= 0:
        raise ValueError("price_value_per_lot must be positive")
    if volume_step <= 0:
        raise ValueError("volume_step must be positive")
    if min_volume <= 0 or max_volume <= 0 or min_volume > max_volume:
        raise ValueError("invalid volume bounds")

    stop_distance = abs(float(entry) - float(stop_loss))
    if stop_distance <= 0:
        raise ValueError("stop distance must be positive")

    risk_amount = equity * (risk_percent / 100.0)
    raw_volume = risk_amount / (stop_distance * price_value_per_lot)
    capped = min(raw_volume, max_volume)
    volume = round_volume_down(capped, volume_step)
    if volume < min_volume:
        raise ValueError(
            f"risk budget allows {raw_volume:.4f} lot, below minimum volume {min_volume:g}"
        )

    volume = max(min_volume, volume)
    loss_at_volume = stop_distance * price_value_per_lot * volume
    return PositionSize(
        volume=round(volume, volume_decimals(volume_step)),
        raw_volume=raw_volume,
        risk_amount=risk_amount,
        stop_distance=stop_distance,
        loss_at_volume=loss_at_volume,
        price_value_per_lot=price_value_per_lot,
        risk_percent=risk_percent,
        equity=equity,
        volume_step=volume_step,
        min_volume=min_volume,
        max_volume=max_volume,
    )


def position_size_from_signal(
    signal: dict[str, Any],
    *,
    account_payload: dict[str, Any] | None,
    risk_percent: float,
    price_value_per_lot: float,
    volume_step: float = 0.01,
    min_volume: float = 0.1,
    max_volume: float = 0.1,
) -> PositionSize:
    equity = account_equity(account_payload)
    if equity is None:
        raise ValueError("account equity is required for risk-based sizing")
    entry = number(signal.get("current_entry_reference"))
    if entry is None:
        low = number(signal.get("entry_low"))
        high = number(signal.get("entry_high"))
        if low is not None and high is not None:
            entry = (low + high) / 2.0
    stop_loss = number(signal.get("stop_loss"))
    if entry is None or stop_loss is None:
        raise ValueError("signal requires entry reference and stop_loss for risk-based sizing")
    return calculate_position_size(
        entry=entry,
        stop_loss=stop_loss,
        equity=equity,
        risk_percent=risk_percent,
        price_value_per_lot=price_value_per_lot,
        volume_step=volume_step,
        min_volume=min_volume,
        max_volume=max_volume,
    )


def estimate_price_value_per_lot(
    *,
    account_payload: dict[str, Any] | None = None,
    deal_history_payload: dict[str, Any] | None = None,
    symbol: str = "XAUUSD-m",
    fallback: float = 1615.0,
    min_price_move: float = 0.05,
) -> float:
    values = price_value_samples(
        account_payload=account_payload,
        deal_history_payload=deal_history_payload,
        symbol=symbol,
        min_price_move=min_price_move,
    )
    if not values:
        return fallback
    return float(statistics.median(values))


def price_value_samples(
    *,
    account_payload: dict[str, Any] | None = None,
    deal_history_payload: dict[str, Any] | None = None,
    symbol: str = "XAUUSD-m",
    min_price_move: float = 0.05,
) -> list[float]:
    deals = merged_deals(account_payload=account_payload, deal_history_payload=deal_history_payload, symbol=symbol)
    open_by_side: dict[str, deque[dict[str, float | datetime]]] = {"buy": deque(), "sell": deque()}
    values: list[float] = []

    for deal in deals:
        entry_type = str(deal.get("entry", "")).lower()
        side = str(deal.get("type", "")).lower()
        volume = number(deal.get("volume")) or 0.0
        price = number(deal.get("price")) or 0.0
        if side not in {"buy", "sell"} or volume <= 0:
            continue

        if entry_type == "in":
            open_by_side[side].append({"volume": volume, "price": price})
            continue

        if entry_type != "out":
            continue
        original_side = "sell" if side == "buy" else "buy"
        remaining = volume
        total_profit = abs(deal_profit(deal))
        while remaining > 1e-9 and open_by_side[original_side]:
            opened = open_by_side[original_side][0]
            opened_volume = float(opened["volume"])
            matched_volume = min(remaining, opened_volume)
            remaining -= matched_volume
            opened["volume"] = opened_volume - matched_volume
            move = abs(price - float(opened["price"]))
            if move >= min_price_move and total_profit > 0:
                allocated_profit = total_profit * (matched_volume / volume)
                values.append(allocated_profit / (move * matched_volume))
            if float(opened["volume"]) <= 1e-9:
                open_by_side[original_side].popleft()

    return values


def merged_deals(
    *,
    account_payload: dict[str, Any] | None,
    deal_history_payload: dict[str, Any] | None,
    symbol: str,
) -> list[dict[str, Any]]:
    by_ticket: dict[str, dict[str, Any]] = {}
    for payload in (deal_history_payload, account_payload):
        if not payload:
            continue
        if payload is account_payload and isinstance(payload.get("account"), dict):
            raw_deals = payload["account"].get("deals", [])
        else:
            raw_deals = payload.get("deals", [])
        if not isinstance(raw_deals, list):
            continue
        for deal in raw_deals:
            if not isinstance(deal, dict):
                continue
            if str(deal.get("symbol", symbol)) != symbol:
                continue
            ticket = str(deal.get("ticket", f"{deal.get('time')}:{deal.get('type')}:{deal.get('price')}"))
            by_ticket[ticket] = deal
    return sorted(by_ticket.values(), key=lambda deal: parse_time(str(deal.get("time", ""))) or datetime.min)


def account_equity(account_payload: dict[str, Any] | None) -> float | None:
    if not account_payload:
        return None
    account = account_payload.get("account") if isinstance(account_payload.get("account"), dict) else account_payload
    if not isinstance(account, dict):
        return None
    equity = number(account.get("equity"))
    if equity is not None and equity > 0:
        return equity
    balance = number(account.get("balance"))
    if balance is not None and balance > 0:
        return balance
    return None


def round_volume_down(volume: float, step: float) -> float:
    return math.floor((volume + 1e-12) / step) * step


def volume_decimals(step: float) -> int:
    text = f"{step:.10f}".rstrip("0")
    if "." not in text:
        return 0
    return len(text.split(".", 1)[1])


def number(value: object) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
