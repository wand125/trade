#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from trade_data.next_bar_registry import align_prediction_subset, read_prediction_sets


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Materialize predictions on an exact aligned reference subset."
    )
    parser.add_argument("--predictions-dir", type=Path, required=True)
    parser.add_argument("--reference-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--timeframe", type=int, default=15)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    predictions = read_prediction_sets([args.predictions_dir], args.timeframe)
    reference = read_prediction_sets([args.reference_dir], args.timeframe)
    aligned = align_prediction_subset(predictions, reference)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    filename = f"m{args.timeframe}_walk_forward_predictions.parquet"
    aligned.to_parquet(args.output_dir / filename, index=False)
    manifest = {
        "format_version": 1,
        "kind": "next_bar_aligned_prediction_subset",
        "sources": {
            "predictions_dir": str(args.predictions_dir),
            "reference_dir": str(args.reference_dir),
        },
        "timeframes": {
            f"M{args.timeframe}": {
                "minutes": args.timeframe,
                "predictions": filename,
                "rows": len(aligned),
            }
        },
    }
    payload = json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
    (args.output_dir / "manifest.json").write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
