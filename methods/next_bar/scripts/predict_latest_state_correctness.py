#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
SOURCE_ROOT = REPOSITORY_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from trade_data.next_bar_state_correctness import (  # noqa: E402
    DEFAULT_HIGH_CONFIDENCE_THRESHOLD,
    predict_latest_state_correctness,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the fixed M1 state-correctness precision shadow."
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--reference-model-dir", type=Path, required=True)
    parser.add_argument("--state-model-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--threshold", type=float, default=DEFAULT_HIGH_CONFIDENCE_THRESHOLD
    )
    args = parser.parse_args()

    prediction = predict_latest_state_correctness(
        pd.read_parquet(args.input),
        args.reference_model_dir,
        args.state_model_dir,
        args.threshold,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    payload = prediction.to_json(orient="records", date_format="iso", indent=2)
    args.output.write_text(payload + "\n", encoding="utf-8")
    print(json.dumps(json.loads(payload), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
