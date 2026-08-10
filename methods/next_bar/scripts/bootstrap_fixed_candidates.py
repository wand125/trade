#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from trade_data.next_bar_bootstrap import run_paired_daily_block_bootstrap


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compare fixed confidence candidates with paired UTC-day bootstrap."
    )
    parser.add_argument("--first-dir", type=Path, action="append", required=True)
    parser.add_argument("--first-name", required=True)
    parser.add_argument("--second-dir", type=Path, action="append", required=True)
    parser.add_argument("--second-name", required=True)
    parser.add_argument("--threshold", type=float, required=True)
    parser.add_argument("--timeframe", type=int, default=15)
    parser.add_argument("--iterations", type=int, default=2_000)
    parser.add_argument("--random-seed", type=int, default=42)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = run_paired_daily_block_bootstrap(
        args.first_dir,
        args.second_dir,
        args.first_name,
        args.second_name,
        args.threshold,
        args.timeframe,
        args.iterations,
        args.random_seed,
        args.output,
    )
    print(json.dumps(report["periods"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
