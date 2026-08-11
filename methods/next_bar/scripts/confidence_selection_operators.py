#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from trade_data.next_bar_registry import (
    combine_confidence_selection_frames,
    compare_confidence_selection_operators,
    read_prediction_sets,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compare and materialize fixed confidence selection-set operators."
    )
    parser.add_argument("--first-dir", type=Path, required=True)
    parser.add_argument("--first-name", required=True)
    parser.add_argument("--first-threshold", type=float, required=True)
    parser.add_argument("--second-dir", type=Path, required=True)
    parser.add_argument("--second-name", required=True)
    parser.add_argument("--second-threshold", type=float, required=True)
    parser.add_argument("--timeframe", type=int, default=1)
    parser.add_argument(
        "--development-folds",
        default="test2020,test2021,test2022,test2023",
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    first = read_prediction_sets([args.first_dir], args.timeframe)
    second = read_prediction_sets([args.second_dir], args.timeframe)
    development_folds = tuple(
        value.strip() for value in args.development_folds.split(",") if value.strip()
    )
    report = compare_confidence_selection_operators(
        first,
        second,
        args.first_threshold,
        args.second_threshold,
        args.first_name,
        args.second_name,
        development_folds,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    report_path = args.output_dir / "selection_operator_metrics.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    for operator in ("first", "second", "union", "intersection"):
        frame = combine_confidence_selection_frames(
            first,
            second,
            args.first_threshold,
            args.second_threshold,
            operator,
        )
        operator_dir = args.output_dir / operator
        operator_dir.mkdir(parents=True, exist_ok=True)
        filename = f"m{args.timeframe}_walk_forward_predictions.parquet"
        frame.to_parquet(operator_dir / filename, index=False)
        manifest = {
            "format_version": 1,
            "kind": "next_bar_confidence_selection_set",
            "operator": operator,
            "selection_column": "confidence_selection_eligible",
            "sources": {
                "first_dir": str(args.first_dir),
                "first_name": args.first_name,
                "first_threshold": args.first_threshold,
                "second_dir": str(args.second_dir),
                "second_name": args.second_name,
                "second_threshold": args.second_threshold,
            },
            "timeframes": {
                f"M{args.timeframe}": {
                    "minutes": args.timeframe,
                    "predictions": filename,
                }
            },
        }
        (operator_dir / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
