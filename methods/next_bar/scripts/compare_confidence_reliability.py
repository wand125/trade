from __future__ import annotations

import argparse
import json
from pathlib import Path

from trade_data.next_bar_registry import (
    DEFAULT_DEVELOPMENT_FOLDS,
    DEFAULT_RELIABILITY_EDGES,
    DEFAULT_RELIABILITY_THRESHOLDS,
    compare_confidence_reliability_frames,
    read_prediction_sets,
)


def comma_strings(value: str) -> tuple[str, ...]:
    output = tuple(item.strip() for item in value.split(",") if item.strip())
    if not output:
        raise argparse.ArgumentTypeError("value must contain at least one item")
    return output


def comma_floats(value: str) -> tuple[float, ...]:
    try:
        output = tuple(float(item.strip()) for item in value.split(",") if item.strip())
    except ValueError as error:
        raise argparse.ArgumentTypeError("value must contain only numbers") from error
    if not output:
        raise argparse.ArgumentTypeError("value must contain at least one number")
    return output


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compare two aligned next-bar confidence reliability profiles."
    )
    parser.add_argument("--first-dir", type=Path, action="append", required=True)
    parser.add_argument("--first-name", required=True)
    parser.add_argument("--second-dir", type=Path, action="append", required=True)
    parser.add_argument("--second-name", required=True)
    parser.add_argument("--timeframe", type=int, default=15)
    parser.add_argument(
        "--development-folds",
        type=comma_strings,
        default=DEFAULT_DEVELOPMENT_FOLDS,
    )
    parser.add_argument("--band-edges", type=comma_floats, default=DEFAULT_RELIABILITY_EDGES)
    parser.add_argument(
        "--thresholds", type=comma_floats, default=DEFAULT_RELIABILITY_THRESHOLDS
    )
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    report = compare_confidence_reliability_frames(
        read_prediction_sets(args.first_dir, args.timeframe),
        read_prediction_sets(args.second_dir, args.timeframe),
        args.first_name,
        args.second_name,
        args.development_folds,
        args.band_edges,
        args.thresholds,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    args.output.write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
