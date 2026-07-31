from __future__ import annotations

import json
from bisect import bisect_right
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


TIME_FORMAT = "%Y.%m.%d %H:%M"


@dataclass(frozen=True)
class Bar:
    time: datetime
    time_text: str
    open: float
    high: float
    low: float
    close: float
    tick_volume: int


@dataclass(frozen=True)
class MarketHistory:
    symbol: str
    server_time: str
    history_hours: int
    point: float
    spread_points: int
    timeframes: dict[str, list[Bar]]
    indicators: dict[str, dict[str, list[float | None]]]

    def bars(self, timeframe: str) -> list[Bar]:
        return self.timeframes.get(timeframe, [])

    def indicator(self, timeframe: str, name: str) -> list[float | None]:
        return self.indicators.get(timeframe, {}).get(name, [])


def parse_bar(raw: dict[str, Any]) -> Bar:
    time_text = str(raw["time"])
    return Bar(
        time=datetime.strptime(time_text, TIME_FORMAT),
        time_text=time_text,
        open=float(raw["open"]),
        high=float(raw["high"]),
        low=float(raw["low"]),
        close=float(raw["close"]),
        tick_volume=int(raw.get("tick_volume", 0)),
    )


def load_history(path: str | Path) -> MarketHistory:
    with Path(path).open(encoding="utf-8") as f:
        payload = json.load(f)

    raw_timeframes = payload.get("timeframes") or {}
    timeframes: dict[str, list[Bar]] = {}
    for name, obj in raw_timeframes.items():
        timeframes[name] = [parse_bar(row) for row in obj.get("bars") or []]

    if "M1" not in timeframes and payload.get("bars"):
        timeframes["M1"] = [parse_bar(row) for row in payload.get("bars") or []]

    indicators = {name: build_indicator_series(bars) for name, bars in timeframes.items()}

    return MarketHistory(
        symbol=str(payload.get("symbol", "")),
        server_time=str(payload.get("server_time", "")),
        history_hours=int(payload.get("history_hours", 0) or 0),
        point=float(payload.get("point", 0.01) or 0.01),
        spread_points=int(payload.get("spread_points", 0) or 0),
        timeframes=timeframes,
        indicators=indicators,
    )


def build_indicator_series(bars: list[Bar]) -> dict[str, list[float | None]]:
    closes = [bar.close for bar in bars]
    highs = [bar.high for bar in bars]
    lows = [bar.low for bar in bars]
    return {
        "ema_fast": ema(closes, 9),
        "ema_slow": ema(closes, 21),
        "ema_mid": ema(closes, 50),
        "ema_long": ema(closes, 100),
        "rsi14": rsi(closes, 14),
        "atr14": atr(highs, lows, closes, 14),
    }


def ema(values: list[float], period: int) -> list[float | None]:
    if not values:
        return []
    result: list[float | None] = [None] * len(values)
    if len(values) < period:
        return result
    seed = sum(values[:period]) / period
    result[period - 1] = seed
    k = 2 / (period + 1)
    previous = seed
    for i in range(period, len(values)):
        previous = values[i] * k + previous * (1 - k)
        result[i] = previous
    return result


def rsi(values: list[float], period: int = 14) -> list[float | None]:
    result: list[float | None] = [None] * len(values)
    if len(values) <= period:
        return result

    gains: list[float] = []
    losses: list[float] = []
    for i in range(1, period + 1):
        change = values[i] - values[i - 1]
        gains.append(max(change, 0.0))
        losses.append(max(-change, 0.0))
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    result[period] = 100.0 if avg_loss == 0 else 100.0 - (100.0 / (1.0 + avg_gain / avg_loss))

    for i in range(period + 1, len(values)):
        change = values[i] - values[i - 1]
        gain = max(change, 0.0)
        loss = max(-change, 0.0)
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
        result[i] = 100.0 if avg_loss == 0 else 100.0 - (100.0 / (1.0 + avg_gain / avg_loss))
    return result


def atr(highs: list[float], lows: list[float], closes: list[float], period: int = 14) -> list[float | None]:
    result: list[float | None] = [None] * len(closes)
    if len(closes) <= period:
        return result
    true_ranges: list[float] = []
    for i in range(len(closes)):
        if i == 0:
            tr = highs[i] - lows[i]
        else:
            tr = max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1]))
        true_ranges.append(tr)
    initial = sum(true_ranges[1 : period + 1]) / period
    result[period] = initial
    previous = initial
    for i in range(period + 1, len(closes)):
        previous = (previous * (period - 1) + true_ranges[i]) / period
        result[i] = previous
    return result


def index_at_or_before(bars: list[Bar], moment: datetime) -> int | None:
    if not bars:
        return None
    times = [bar.time for bar in bars]
    index = bisect_right(times, moment) - 1
    return index if index >= 0 else None
