from __future__ import annotations

import argparse
import json
from pathlib import Path

from trade_data.next_bar_registry import (
    DEFAULT_DEVELOPMENT_FOLDS,
    compare_fixed_candidate_frames,
    read_prediction_sets,
)


def comma_strings(value: str) -> tuple[str, ...]:
    output = tuple(item.strip() for item in value.split(",") if item.strip())
    if not output:
        raise argparse.ArgumentTypeError("value must contain at least one item")
    return output


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compare two aligned next-bar candidates at one fixed threshold."
    )
    parser.add_argument("--first-dir", type=Path, required=True)
    parser.add_argument("--first-name", required=True)
    parser.add_argument("--second-dir", type=Path, required=True)
    parser.add_argument("--second-name", required=True)
    parser.add_argument("--threshold", type=float, required=True)
    parser.add_argument("--timeframe", type=int, default=15)
    parser.add_argument(
        "--development-folds",
        type=comma_strings,
        default=DEFAULT_DEVELOPMENT_FOLDS,
    )
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    report = compare_fixed_candidate_frames(
        read_prediction_sets([args.first_dir], args.timeframe),
        read_prediction_sets([args.second_dir], args.timeframe),
        args.threshold,
        args.first_name,
        args.second_name,
        args.development_folds,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    args.output.write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
