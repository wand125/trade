#!/usr/bin/env python3
"""Request a one-time historical MT5 snapshot from the EA."""

from __future__ import annotations

import json
import sys
import time
import uuid
from pathlib import Path


def main() -> None:
    hours = 24
    if len(sys.argv) > 1:
        hours = int(sys.argv[1])
    if hours < 1 or hours > 168:
        raise SystemExit("hours must be between 1 and 168")

    state_dir = Path("runtime")
    state_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "id": uuid.uuid4().hex,
        "hours": hours,
        "requested_at": int(time.time()),
        "status": "pending",
    }
    (state_dir / "history_request.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"requested {hours}h history; wait for the next MT5 EA post")


if __name__ == "__main__":
    main()
