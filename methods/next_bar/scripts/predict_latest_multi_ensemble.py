#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
SOURCE_ROOT = REPOSITORY_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from trade_data.next_bar import predict_latest, read_ohlcv  # noqa: E402
from trade_data.next_bar_ensemble import (  # noqa: E402
    assert_walk_forward_artifact_parity,
    blend_latest_prediction_sources,
)


def source(value: str) -> tuple[str, Path, float]:
    parts = value.split("=", 2)
    if len(parts) != 3:
        raise argparse.ArgumentTypeError("source must be LABEL=MODEL_DIR=WEIGHT")
    label, path, weight_text = parts
    try:
        weight = float(weight_text)
    except ValueError as error:
        raise argparse.ArgumentTypeError("source weight must be numeric") from error
    return label, Path(path), weight


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Predict a fixed multi-source latest shadow ensemble")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--source", action="append", type=source, required=True)
    parser.add_argument("--preserve-first-direction", action="store_true")
    parser.add_argument(
        "--allow-config-difference",
        action="append",
        default=[],
        help="Explicit walk-forward config key allowed to differ across sources.",
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--parity-output", type=Path, required=True)
    args = parser.parse_args(argv)
    directories = [path for _, path, _ in args.source]
    parity = assert_walk_forward_artifact_parity(
        directories,
        allowed_config_differences=args.allow_config_difference,
    )
    m1 = read_ohlcv(args.input)
    frames = [(label, predict_latest(m1, path), weight) for label, path, weight in args.source]
    predictions = blend_latest_prediction_sources(
        frames,
        preserve_first_direction=args.preserve_first_direction,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        predictions.to_json(orient="records", date_format="iso", indent=2) + "\n",
        encoding="utf-8",
    )
    parity.update(
        {
            "weights": {label: weight for label, _, weight in args.source},
            "preserve_first_direction": args.preserve_first_direction,
            "odds_runtime_authorized": False,
        }
    )
    args.parity_output.parent.mkdir(parents=True, exist_ok=True)
    args.parity_output.write_text(json.dumps(parity, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(predictions.to_json(orient="records", date_format="iso", indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
