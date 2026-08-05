#!/usr/bin/env python3
"""Create a Codex-to-MT5 trade command file.

Default mode is dry-run. Live commands require --live --confirm LIVE.
"""

from __future__ import annotations

import argparse
import json
import time
import uuid
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a pending MT5 trade command.")
    parser.add_argument(
        "action",
        choices=["buy", "sell", "buy_limit", "sell_limit", "modify", "cancel", "close", "close_all"],
    )
    parser.add_argument("--symbol", default="XAUUSD-m")
    parser.add_argument("--volume", type=float, default=0.1)
    parser.add_argument("--price", type=float, help="Entry price for buy_limit/sell_limit.")
    parser.add_argument("--sl", type=float)
    parser.add_argument("--tp", type=float)
    parser.add_argument("--ticket", type=int)
    parser.add_argument("--max-spread-points", type=int, default=80)
    parser.add_argument("--expires-in-seconds", type=int, default=30)
    parser.add_argument("--comment", default="codex command")
    parser.add_argument("--reason", default="manual user-approved command")
    parser.add_argument("--state-dir", default="runtime")
    parser.add_argument("--live", action="store_true", help="Request live execution instead of dry-run.")
    parser.add_argument("--confirm", default="", help="Must be LIVE when --live is used.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.live and args.confirm != "LIVE":
        raise SystemExit("--live requires --confirm LIVE")
    if args.action in {"buy", "sell"}:
        if args.sl is None or args.tp is None:
            raise SystemExit("buy/sell require --sl and --tp")
        if args.volume <= 0:
            raise SystemExit("--volume must be positive")
    if args.action in {"buy_limit", "sell_limit"}:
        if args.price is None:
            raise SystemExit("buy_limit/sell_limit require --price")
        if args.sl is None or args.tp is None:
            raise SystemExit("buy_limit/sell_limit require --sl and --tp")
        if args.volume <= 0:
            raise SystemExit("--volume must be positive")
        if args.action == "sell_limit" and not (args.tp < args.price < args.sl):
            raise SystemExit("sell_limit requires tp < price < sl")
        if args.action == "buy_limit" and not (args.sl < args.price < args.tp):
            raise SystemExit("buy_limit requires sl < price < tp")
    if args.action == "modify":
        if not args.ticket:
            raise SystemExit("modify requires --ticket")
        if args.sl is None and args.tp is None:
            raise SystemExit("modify requires --sl and/or --tp")
    if args.action == "cancel" and not args.ticket:
        raise SystemExit("cancel requires --ticket")
    if args.action == "close" and not args.ticket:
        raise SystemExit("close requires --ticket")
    if args.expires_in_seconds < 5 or args.expires_in_seconds > 300:
        raise SystemExit("--expires-in-seconds must be between 5 and 300")

    now = int(time.time())
    command = {
        "id": uuid.uuid4().hex,
        "status": "pending",
        "created_at": now,
        "expires_at": now + args.expires_in_seconds,
        "action": args.action,
        "symbol": args.symbol,
        "volume": args.volume,
        "price": args.price,
        "sl": args.sl,
        "tp": args.tp,
        "ticket": args.ticket,
        "max_spread_points": args.max_spread_points,
        "dry_run": not args.live,
        "comment": args.comment,
        "reason": args.reason,
    }

    state_dir = Path(args.state_dir)
    state_dir.mkdir(parents=True, exist_ok=True)
    path = state_dir / "trade_command.json"
    path.write_text(json.dumps(command, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"created {'live' if args.live else 'dry-run'} command {command['id']} at {path}")


if __name__ == "__main__":
    main()
