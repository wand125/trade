#!/usr/bin/env python3
"""Token-free runtime watcher for the manual trading method.

Polls runtime/ state written by the MT5 bridge and prints one line per
meaningful transition (edge-triggered). Designed to run under a session
Monitor: stdout lines wake Claude; quiet markets produce no output.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--state-dir", default="runtime")
    p.add_argument("--interval", type=int, default=30)
    p.add_argument(
        "--levels",
        default="",
        help="Comma list of SYMBOL:price entries, e.g. 'USDJPY-m:157.15,USDJPY-m:157.75'",
    )
    p.add_argument("--stale-seconds", type=int, default=300)
    p.add_argument("--level-cooldown", type=int, default=900,
                   help="Seconds to suppress repeat alerts for the same level (default 900)")
    p.add_argument("--digest-minutes", type=int, default=0,
                   help="Emit a compact state digest every N minutes (0=off)")
    p.add_argument(
        "--events",
        default="",
        help="Semicolon list of 'YYYY-MM-DDTHH:MM|label' (local time) to warn about at T-60min and T-10min",
    )
    return p.parse_args()


def read_json(path: Path) -> dict:
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def read_account(path: Path) -> dict:
    out = {"balance": None, "equity": None, "positions": None, "tickets": {}, "prices": {}}
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return out
    in_positions = False
    positions = 0
    for line in text.splitlines():
        if line.startswith("- Balance:"):
            out["balance"] = float(line.split(":")[1].strip())
        elif line.startswith("- Equity:"):
            out["equity"] = float(line.split(":")[1].strip())
        elif line.startswith("## Open Positions"):
            in_positions = True
        elif line.startswith("## ") and in_positions:
            in_positions = False
        elif in_positions and line.startswith("- ") and "None" not in line:
            positions += 1
            fields = line[2:].split()
            info = {}
            for i, token in enumerate(fields):
                if token in ("ticket", "current", "SL", "TP") and i + 1 < len(fields):
                    info[token] = fields[i + 1]
            ticket = info.get("ticket")
            if ticket:
                out["tickets"][ticket] = {
                    "symbol": fields[2] if len(fields) > 2 else "",
                    "current": _to_float(info.get("current")),
                    "sl": _to_float(info.get("SL")),
                    "tp": _to_float(info.get("TP")),
                }
    out["positions"] = positions
    # 保有玉の current 価格は銘柄別に取れるため、単一銘柄しか載らない
    # latest_snapshot.json の穴(交互更新で片方が盲目になる)を埋める。
    for info in out["tickets"].values():
        symbol, price = info.get("symbol"), info.get("current")
        if symbol and price is not None:
            out["prices"][symbol] = price
    return out


def _to_float(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def emit(msg: str) -> None:
    stamp = time.strftime("%H:%M:%S")
    print(f"{stamp} {msg}", flush=True)


def main() -> None:
    args = parse_args()
    state_dir = Path(args.state_dir)
    levels: list[tuple[str, float]] = []
    if args.levels:
        for entry in args.levels.split(","):
            sym, _, val = entry.partition(":")
            if val:
                levels.append((sym.strip(), float(val)))

    events: list[tuple[float, str]] = []
    if args.events:
        for entry in args.events.split(";"):
            ts, _, label = entry.partition("|")
            if label:
                events.append((time.mktime(time.strptime(ts.strip(), "%Y-%m-%dT%H:%M")), label.strip()))
    warned: set[tuple[str, int]] = set()
    level_last_fired: dict[tuple[str, float], float] = {}

    last_price: dict[str, float] = {}
    last_seen: dict[str, float] = {}
    symbol_stale: set[str] = set()
    watch_symbols = sorted({sym for sym, _ in levels})
    last_balance: float | None = None
    last_positions: int | None = None
    last_tickets: dict | None = None
    stale_reported = False
    last_digest = time.time()

    while True:
        now = time.time()
        if args.digest_minutes and now - last_digest >= args.digest_minutes * 60:
            parts = [f"{s_}:{p_:g}" for s_, p_ in sorted(last_price.items())]
            line = "[watch] DIGEST " + (" | ".join(parts) if parts else "no data")
            if last_positions is not None:
                line += f" | pos {last_positions}"
            if last_balance is not None:
                line += f" | bal {last_balance:,.0f}"
            emit(line)
            last_digest = now
        for ev_ts, label in events:
            remaining = ev_ts - now
            for lead_min in (60, 10):
                key = (label, lead_min)
                if key not in warned and 0 < remaining <= lead_min * 60:
                    emit(f"[watch] EVENT_WARN {label} まで約{int(remaining/60)}分")
                    warned.add(key)
        snap = read_json(state_dir / "latest_snapshot.json")
        acct = read_account(state_dir / "latest_account.md")

        mtime = (state_dir / "latest_snapshot.json").stat().st_mtime if (state_dir / "latest_snapshot.json").exists() else 0
        age = time.time() - mtime
        if age > args.stale_seconds and not stale_reported:
            emit(f"[watch] DATA_STALE snapshotが{int(age)}秒更新されていない(MT5/EA/ブリッジ停止の可能性)")
            stale_reported = True
        elif age <= args.stale_seconds and stale_reported:
            emit("[watch] DATA_RESUMED snapshot更新が再開")
            stale_reported = False

        for wsym in watch_symbols:
            seen = last_seen.get(wsym)
            if seen is not None and now - seen > args.stale_seconds and wsym not in symbol_stale:
                emit(f"[watch] SYMBOL_STALE {wsym} のsnapshotが{int((now-seen)/60)}分更新されていない(EAがpassive/停止の可能性。価格・水準監視は盲目)")
                symbol_stale.add(wsym)
            elif seen is not None and now - seen <= args.stale_seconds and wsym in symbol_stale:
                emit(f"[watch] SYMBOL_RESUMED {wsym} の更新が再開")
                symbol_stale.discard(wsym)

        # スナップショットは1銘柄ずつしか載らないので、保有玉の current 価格も
        # 価格源として併用する(保有中の銘柄が交互更新で盲目にならないように)。
        observed = dict(acct.get("prices") or {})
        sym = snap.get("symbol")
        bid = snap.get("bid")
        if sym and isinstance(bid, (int, float)):
            observed[sym] = bid

        for osym, price in observed.items():
            last_seen[osym] = now
            prev = last_price.get(osym)
            if prev is not None:
                for lsym, level in levels:
                    if lsym != osym:
                        continue
                    crossed_up = prev < level <= price
                    crossed_down = prev > level >= price
                    if not (crossed_up or crossed_down):
                        continue
                    key = (lsym, level)
                    if now - level_last_fired.get(key, 0) < args.level_cooldown:
                        continue
                    level_last_fired[key] = now
                    if crossed_up:
                        emit(f"[watch] LEVEL_UP {osym} が {level} を上抜け(価格 {price})")
                    else:
                        emit(f"[watch] LEVEL_DOWN {osym} が {level} を下抜け(価格 {price})")
            last_price[osym] = price

        bal = acct.get("balance")
        if bal is not None:
            if last_balance is not None and abs(bal - last_balance) > 0.5:
                emit(f"[watch] BALANCE 残高が {last_balance:,.0f} -> {bal:,.0f} に変化(入金/決済)")
            last_balance = bal

        pos = acct.get("positions")
        if pos is not None:
            if last_positions is not None and pos != last_positions:
                emit(f"[watch] POSITIONS ポジション数が {last_positions} -> {pos} に変化")
            last_positions = pos

        tickets = acct.get("tickets") or {}
        if last_tickets is not None:
            for t, info in tickets.items():
                if t not in last_tickets:
                    emit(f"[watch] FILLED ticket {t} {info['symbol']} 約定を検知"
                         f"(current {info['current']} SL {info['sl']} TP {info['tp']})")
            for t, info in last_tickets.items():
                if t not in tickets:
                    emit(f"[watch] CLOSED ticket {t} {info['symbol']} が消滅(決済)")
                elif tickets[t]["sl"] != info["sl"] or tickets[t]["tp"] != info["tp"]:
                    emit(f"[watch] SLTP_CHANGED ticket {t} {info['symbol']} "
                         f"SL {info['sl']}->{tickets[t]['sl']} TP {info['tp']}->{tickets[t]['tp']}")
        last_tickets = tickets

        time.sleep(args.interval)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
