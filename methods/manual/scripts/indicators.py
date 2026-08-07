#!/usr/bin/env python3
"""Compute indicators from the per-symbol snapshot bars.

The EA sends OHLC bars but leaves the indicator fields at zero, so RSI and the
moving averages have to be derived here before they can inform a trade.

Usage:
    python3 methods/manual/scripts/indicators.py XAUUSD-m
    python3 methods/manual/scripts/indicators.py USDJPY-m --tf M5
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def rsi(closes: list[float], period: int = 14) -> float | None:
    if len(closes) <= period:
        return None
    gains, losses = [], []
    for prev, cur in zip(closes, closes[1:]):
        diff = cur - prev
        gains.append(max(diff, 0.0))
        losses.append(max(-diff, 0.0))
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    # Wilder smoothing for the remaining bars
    for g, l in zip(gains[period:], losses[period:]):
        avg_gain = (avg_gain * (period - 1) + g) / period
        avg_loss = (avg_loss * (period - 1) + l) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - 100.0 / (1.0 + rs)


def sma(values: list[float], period: int) -> float | None:
    if len(values) < period:
        return None
    return sum(values[-period:]) / period


def ema(values: list[float], period: int) -> float | None:
    if len(values) < period:
        return None
    k = 2.0 / (period + 1)
    out = sum(values[:period]) / period
    for v in values[period:]:
        out = v * k + out * (1 - k)
    return out


def atr(bars: list[dict], period: int = 14) -> float | None:
    if len(bars) <= period:
        return None
    trs = []
    for prev, cur in zip(bars, bars[1:]):
        trs.append(
            max(
                cur["high"] - cur["low"],
                abs(cur["high"] - prev["close"]),
                abs(cur["low"] - prev["close"]),
            )
        )
    out = sum(trs[:period]) / period
    for tr in trs[period:]:
        out = (out * (period - 1) + tr) / period
    return out


def aggregate(bars: list[dict], minutes: int) -> list[dict]:
    """Fold M1 bars into a coarser timeframe."""
    if minutes <= 1:
        return bars
    out = []
    for i in range(0, len(bars), minutes):
        chunk = bars[i : i + minutes]
        if not chunk:
            continue
        out.append(
            {
                "time": chunk[0]["time"],
                "open": chunk[0]["open"],
                "high": max(b["high"] for b in chunk),
                "low": min(b["low"] for b in chunk),
                "close": chunk[-1]["close"],
            }
        )
    return out


def load_bars(data: dict, tf: str) -> list[dict]:
    """Prefer the EA's own bars for a timeframe; fold M1 only as a fallback.

    The EA sends M1/M5/M15/M30/H1/H4/D1 under "timeframes". Folding M1 can
    only ever reach one hour back, which is far too short to judge a swing.
    """
    frames = data.get("timeframes") or {}
    native = frames.get(tf)
    if isinstance(native, dict) and native.get("bars"):
        return native["bars"]
    minutes = {"M1": 1, "M5": 5, "M15": 15, "M30": 30}.get(tf)
    if minutes is None:
        return []
    return aggregate(data.get("bars") or [], minutes)


def report(symbol: str, tf: str, bars: list[dict], data: dict) -> None:
    closes = [b["close"] for b in bars]
    lows = [b["low"] for b in bars]
    highs = [b["high"] for b in bars]
    price = data.get("bid")
    unit = 100 if price and price < 1000 else 1
    unit_name = "pips" if unit == 100 else "ドル"

    span = f"{bars[0]['time']} 〜 {bars[-1]['time']}"
    print(f"{symbol} {tf}  bid {price}  ({data.get('server_time')})")
    print(f"  bars {len(bars)}  {span}")
    print(f"  レンジ {min(lows):.3f}-{max(highs):.3f} "
          f"(幅 {(max(highs) - min(lows)) * unit:.1f}{unit_name})")

    r = rsi(closes)
    print(f"  RSI14      {r:.1f}" if r is not None else "  RSI14      n/a")

    for period in (10, 20, 50):
        e, s = ema(closes, period), sma(closes, period)
        if e is None:
            continue
        rel = "上" if price and price > e else "下"
        print(f"  EMA{period:<3}     {e:.3f}   SMA{period:<3} {s:.3f}   (現値は EMA の{rel})")

    a = atr(bars)
    if a is not None:
        print(f"  ATR14      {a * unit:.1f}{unit_name}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("symbol", help="e.g. XAUUSD-m")
    parser.add_argument("--tf", default="M1",
                        choices=["M1", "M5", "M15", "M30", "H1", "H4", "D1"])
    parser.add_argument("--all", action="store_true",
                        help="every timeframe at once — the swing view")
    parser.add_argument("--state-dir", default="runtime")
    args = parser.parse_args()

    path = Path(args.state_dir) / f"latest_snapshot_{args.symbol}.json"
    if not path.exists():
        raise SystemExit(f"{path} not found")
    data = json.loads(path.read_text(encoding="utf-8"))

    if args.all:
        for tf in ("M1", "M5", "M15", "M30", "H1", "H4", "D1"):
            bars = load_bars(data, tf)
            if bars:
                report(args.symbol, tf, bars, data)
                print()
        return

    bars = load_bars(data, args.tf)
    if len(bars) < 3:
        raise SystemExit(f"not enough {args.tf} bars ({len(bars)})")

    report(args.symbol, args.tf, bars, data)


if __name__ == "__main__":
    main()
