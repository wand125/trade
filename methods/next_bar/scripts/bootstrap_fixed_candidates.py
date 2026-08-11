#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from trade_data.next_bar_bootstrap import run_paired_daily_block_bootstrap


def comma_strings(value: str) -> tuple[str, ...]:
    output = tuple(item.strip() for item in value.split(",") if item.strip())
    if not output:
        raise argparse.ArgumentTypeError("value must contain at least one item")
    return output


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compare fixed confidence candidates with paired UTC-day bootstrap."
    )
    parser.add_argument("--first-dir", type=Path, action="append", required=True)
    parser.add_argument("--first-name", required=True)
    parser.add_argument("--second-dir", type=Path, action="append", required=True)
    parser.add_argument("--second-name", required=True)
    parser.add_argument(
        "--threshold", type=float, required=True,
        help="Fixed threshold for the first candidate and, by default, the second.",
    )
    parser.add_argument(
        "--second-threshold", type=float,
        help="Optional independently fixed threshold for the second candidate.",
    )
    parser.add_argument("--timeframe", type=int, default=15)
    parser.add_argument("--iterations", type=int, default=2_000)
    parser.add_argument("--random-seed", type=int, default=42)
    parser.add_argument(
        "--first-selection-column",
        help="Optional boolean column used instead of thresholding first confidence.",
    )
    parser.add_argument(
        "--second-selection-column",
        help="Optional boolean column used instead of thresholding second confidence.",
    )
    parser.add_argument(
        "--exclude-folds",
        type=comma_strings,
        default=(),
        help="Optional folds excluded before all bootstrap periods.",
    )
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
        args.second_threshold,
        args.first_selection_column,
        args.second_selection_column,
        args.exclude_folds,
    )
    print(json.dumps(report["periods"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
