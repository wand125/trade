#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from trade_data.next_bar_registry import blend_confidence_frames, read_prediction_sets


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Materialize a fixed blend of two aligned confidence estimates."
    )
    parser.add_argument("--base-dir", type=Path, required=True)
    parser.add_argument("--contributor-dir", type=Path, required=True)
    parser.add_argument("--contributor-weight", type=float, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--timeframe", type=int, default=15)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    base = read_prediction_sets([args.base_dir], args.timeframe)
    contributor = read_prediction_sets([args.contributor_dir], args.timeframe)
    blended = blend_confidence_frames(base, contributor, args.contributor_weight)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    filename = f"m{args.timeframe}_walk_forward_predictions.parquet"
    blended.to_parquet(args.output_dir / filename, index=False)
    manifest = {
        "format_version": 1,
        "kind": "next_bar_confidence_blend",
        "sources": {
            "base_dir": str(args.base_dir),
            "contributor_dir": str(args.contributor_dir),
            "contributor_weight": args.contributor_weight,
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
