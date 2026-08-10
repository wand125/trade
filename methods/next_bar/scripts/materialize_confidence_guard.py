#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from trade_data.next_bar_registry import (
    apply_confidence_exclusion_guard,
    read_prediction_sets,
)


def key_value_group(value: str) -> dict[str, str]:
    group: dict[str, str] = {}
    for item in value.split(","):
        key, separator, resolved_value = item.strip().partition("=")
        if not separator or not key or not resolved_value:
            raise argparse.ArgumentTypeError(
                "groups must use comma-separated column=value pairs"
            )
        if key in group:
            raise argparse.ArgumentTypeError(f"duplicate group column: {key}")
        group[key] = resolved_value
    return group


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Materialize fixed subgroup confidence abstention guards."
    )
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--timeframe", type=int, default=15)
    parser.add_argument(
        "--exclude-group",
        type=key_value_group,
        action="append",
        required=True,
        help="Repeatable comma-separated column=value group.",
    )
    parser.add_argument("--abstain-confidence", type=float, default=0.5)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    predictions = read_prediction_sets([args.input_dir], args.timeframe)
    guarded = apply_confidence_exclusion_guard(
        predictions,
        args.exclude_group,
        args.abstain_confidence,
    )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    filename = f"m{args.timeframe}_walk_forward_predictions.parquet"
    guarded.to_parquet(args.output_dir / filename, index=False)
    manifest = {
        "format_version": 1,
        "kind": "next_bar_confidence_exclusion_guard",
        "sources": {
            "input_dir": str(args.input_dir),
            "excluded_groups": args.exclude_group,
            "abstain_confidence": args.abstain_confidence,
        },
        "timeframes": {
            f"M{args.timeframe}": {
                "minutes": args.timeframe,
                "predictions": filename,
            }
        },
    }
    payload = json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
    (args.output_dir / "manifest.json").write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
