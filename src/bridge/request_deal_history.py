#!/usr/bin/env python3
"""Request a one-time MT5 deal history export from the EA."""

from __future__ import annotations

import json
import sys
import time
import uuid
from pathlib import Path


def parse_days(value: str) -> int:
    if value.lower() == "all":
        return 0
    days = int(value)
    if days < 1 or days > 3650:
        raise SystemExit("days must be between 1 and 3650, or use 'all'")
    return days


def main() -> None:
    days = 0
    max_deals = 0
    chunk_size = 500
    if len(sys.argv) > 1:
        days = parse_days(sys.argv[1])
    if len(sys.argv) > 2:
        max_deals = int(sys.argv[2])
    if len(sys.argv) > 3:
        chunk_size = int(sys.argv[3])
    if max_deals < 0:
        raise SystemExit("max_deals must be 0 or greater; 0 means no limit")
    if chunk_size < 1 or chunk_size > 2000:
        raise SystemExit("chunk_size must be between 1 and 2000")

    state_dir = Path("runtime")
    state_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "id": uuid.uuid4().hex,
        "days": days,
        "max_deals": max_deals,
        "chunk_size": chunk_size,
        "requested_at": int(time.time()),
        "status": "pending",
    }
    (state_dir / "deal_history_request.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    label = "all available" if days == 0 else f"{days} days"
    limit = "no limit" if max_deals == 0 else str(max_deals)
    print(f"requested MT5 deal history: range={label}, max_deals={limit}, chunk_size={chunk_size}")
    print("wait for the next MT5 EA post, then check runtime/latest_deal_history.json")


if __name__ == "__main__":
    main()
