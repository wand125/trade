#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from trade_data.next_bar_registry import (
    DEFAULT_DEVELOPMENT_FOLDS,
    pairwise_confidence_complementarity,
    read_prediction_sets,
)


def comma_strings(value: str) -> tuple[str, ...]:
    output = tuple(item.strip() for item in value.split(",") if item.strip())
    if not output:
        raise argparse.ArgumentTypeError("value must contain at least one item")
    return output


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Screen fixed confidence candidates for complementary selection sets."
    )
    parser.add_argument(
        "--candidate",
        action="append",
        nargs=3,
        metavar=("NAME", "THRESHOLD", "PREDICTION_DIR"),
        required=True,
        help="Repeat for each candidate; thresholds must already be fixed.",
    )
    parser.add_argument("--timeframe", type=int, default=1)
    parser.add_argument(
        "--development-folds",
        type=comma_strings,
        default=DEFAULT_DEVELOPMENT_FOLDS,
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    candidates = {}
    for name, threshold_text, prediction_dir_text in args.candidate:
        if name in candidates:
            parser.error(f"duplicate candidate name: {name}")
        try:
            threshold = float(threshold_text)
        except ValueError:
            parser.error(f"invalid threshold for {name}: {threshold_text}")
        candidates[name] = (
            read_prediction_sets([Path(prediction_dir_text)], args.timeframe),
            threshold,
        )
    report = pairwise_confidence_complementarity(
        candidates, args.development_folds
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    args.output.write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
