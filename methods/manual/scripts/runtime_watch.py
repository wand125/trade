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
    out = {"balance": None, "equity": None, "positions": None}
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
    out["positions"] = positions
    return out


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

    last_price: dict[str, float] = {}
    last_balance: float | None = None
    last_positions: int | None = None
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

        sym = snap.get("symbol")
        bid = snap.get("bid")
        if sym and isinstance(bid, (int, float)):
            prev = last_price.get(sym)
            if prev is not None:
                for lsym, level in levels:
                    if lsym != sym:
                        continue
                    if prev < level <= bid:
                        emit(f"[watch] LEVEL_UP {sym} が {level} を上抜け(bid {bid})")
                    elif prev > level >= bid:
                        emit(f"[watch] LEVEL_DOWN {sym} が {level} を下抜け(bid {bid})")
            last_price[sym] = bid

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

        time.sleep(args.interval)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
