#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from trade_data.next_bar_odds_recalibration import (
    run_chronological_correctness_recalibration,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compare prior-OOS isotonic and Platt correctness recalibration."
    )
    parser.add_argument("--predictions-dir", type=Path, action="append", required=True)
    parser.add_argument("--timeframe", type=int, default=15)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--bootstrap-iterations", type=int, default=0)
    parser.add_argument("--random-seed", type=int, default=42)
    args = parser.parse_args()
    report = run_chronological_correctness_recalibration(
        args.predictions_dir,
        args.timeframe,
        args.output_dir,
        args.bootstrap_iterations,
        args.random_seed,
    )
    print(json.dumps(report["combined"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
