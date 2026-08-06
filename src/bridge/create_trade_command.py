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


# 銘柄ごとのロット設計(campaign.md のサイズ計画に対応)。
# 同じ「ロット」でも単価が銘柄で67倍違うため、取り違えると致命的になる。
# default: --volume 省略時の値 / cap: これを超える指定はエラーにする
SYMBOL_LOTS = {
    "XAUUSD-m": {"default": 0.3, "floor": 0.05, "cap": 1.0},   # 1ドル≈1,570円/ロット
    "USDJPY-m": {"default": 20.0, "floor": 5.0, "cap": 40.0},  # 1pip=10円/ロット
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a pending MT5 trade command.")
    parser.add_argument(
        "action",
        choices=[
            "buy",
            "sell",
            "buy_limit",
            "sell_limit",
            "buy_stop",
            "sell_stop",
            "modify",
            "cancel",
            "close",
            "close_all",
        ],
    )
    parser.add_argument("--symbol", default="XAUUSD-m")
    parser.add_argument(
        "--volume",
        type=float,
        help="Lot size. Defaults per symbol (see SYMBOL_LOTS); 0.1 for unlisted symbols.",
    )
    parser.add_argument(
        "--allow-oversize",
        action="store_true",
        help="Bypass the per-symbol lot cap. Requires an explicit reason for the record.",
    )
    parser.add_argument("--price", type=float, help="Entry price for pending orders (limit/stop).")
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


def resolve_volume(args: argparse.Namespace) -> float:
    """Fill in the per-symbol default lot and reject sizes above the symbol's cap."""
    lots = SYMBOL_LOTS.get(args.symbol)
    volume = args.volume
    if volume is None:
        volume = lots["default"] if lots else 0.1
    if lots and not args.allow_oversize:
        if volume > lots["cap"]:
            raise SystemExit(
                f"{args.symbol}: --volume {volume} exceeds the cap {lots['cap']} "
                f"(default {lots['default']}). Pass --allow-oversize to override."
            )
        # 下限も見る。他銘柄のロットを取り違えて渡すと、ここに引っかかる。
        if volume < lots["floor"]:
            raise SystemExit(
                f"{args.symbol}: --volume {volume} is below the floor {lots['floor']} "
                f"(default {lots['default']}). Wrong symbol's lot size? "
                f"Pass --allow-oversize to override."
            )
    return volume


def main() -> None:
    args = parse_args()
    if args.live and args.confirm != "LIVE":
        raise SystemExit("--live requires --confirm LIVE")
    args.volume = resolve_volume(args)
    if args.action in {"buy", "sell"}:
        if args.sl is None or args.tp is None:
            raise SystemExit("buy/sell require --sl and --tp")
        if args.volume <= 0:
            raise SystemExit("--volume must be positive")
    if args.action in {"buy_limit", "sell_limit", "buy_stop", "sell_stop"}:
        if args.price is None:
            raise SystemExit(f"{args.action} requires --price")
        if args.sl is None or args.tp is None:
            raise SystemExit(f"{args.action} requires --sl and --tp")
        if args.volume <= 0:
            raise SystemExit("--volume must be positive")
        if args.action in {"sell_limit", "sell_stop"} and not (args.tp < args.price < args.sl):
            raise SystemExit(f"{args.action} requires tp < price < sl")
        if args.action in {"buy_limit", "buy_stop"} and not (args.sl < args.price < args.tp):
            raise SystemExit(f"{args.action} requires sl < price < tp")
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
