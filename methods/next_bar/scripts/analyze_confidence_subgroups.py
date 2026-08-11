#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from trade_data.next_bar_registry import (
    DEFAULT_DEVELOPMENT_FOLDS,
    DEFAULT_RELIABILITY_EDGES,
    DEFAULT_RELIABILITY_THRESHOLDS,
    confidence_reliability_subgroups,
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
        description="Audit next-bar confidence reliability within fixed subgroups."
    )
    parser.add_argument("--predictions-dir", type=Path, action="append", required=True)
    parser.add_argument("--timeframe", type=int, default=15)
    parser.add_argument(
        "--confidence-column",
        default="confidence",
        help="Prediction column to audit as probability of correctness.",
    )
    parser.add_argument(
        "--group-columns",
        type=comma_strings,
        default=("predicted_direction", "volatility_regime"),
    )
    parser.add_argument(
        "--development-folds",
        type=comma_strings,
        default=DEFAULT_DEVELOPMENT_FOLDS,
    )
    parser.add_argument(
        "--exclude-folds",
        type=comma_strings,
        default=(),
        help="Comma-separated folds omitted from every period.",
    )
    parser.add_argument("--band-edges", type=comma_floats, default=DEFAULT_RELIABILITY_EDGES)
    parser.add_argument(
        "--thresholds", type=comma_floats, default=DEFAULT_RELIABILITY_THRESHOLDS
    )
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    predictions = read_prediction_sets(args.predictions_dir, args.timeframe)
    if args.confidence_column not in predictions:
        parser.error(
            f"predictions do not contain confidence column: {args.confidence_column}"
        )
    predictions = predictions.copy()
    predictions["confidence"] = predictions[args.confidence_column]
    report = confidence_reliability_subgroups(
        predictions,
        args.group_columns,
        args.development_folds,
        args.band_edges,
        args.thresholds,
        args.exclude_folds,
    )
    report["confidence_column"] = args.confidence_column
    args.output.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    args.output.write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
