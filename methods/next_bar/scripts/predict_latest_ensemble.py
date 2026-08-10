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

from trade_data.next_bar import read_ohlcv  # noqa: E402
from trade_data.next_bar_ensemble import predict_latest_ensemble  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Predict an aligned baseline/candidate latest probability ensemble."
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--baseline-model-dir", type=Path, required=True)
    parser.add_argument("--candidate-model-dir", type=Path, required=True)
    parser.add_argument("--candidate-weight", type=float, default=0.25)
    parser.add_argument("--preserve-baseline-direction", action="store_true")
    parser.add_argument("--context-policy", type=Path, default=None)
    parser.add_argument("--odds-calibration", type=Path, default=None)
    parser.add_argument(
        "--authorize-odds",
        action="store_true",
        help="Allow a statistically valid calibration to emit odds_valid=true.",
    )
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--parity-output", type=Path, default=None)
    return parser


def read_optional_json(path: Path | None) -> dict[str, object] | None:
    return None if path is None else json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    args = build_parser().parse_args()
    predictions, parity = predict_latest_ensemble(
        read_ohlcv(args.input),
        args.baseline_model_dir,
        args.candidate_model_dir,
        args.candidate_weight,
        args.preserve_baseline_direction,
        read_optional_json(args.context_policy),
        read_optional_json(args.odds_calibration),
        args.authorize_odds,
    )
    payload = predictions.to_json(orient="records", date_format="iso", indent=2)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
    if args.parity_output is not None:
        args.parity_output.parent.mkdir(parents=True, exist_ok=True)
        args.parity_output.write_text(
            json.dumps(parity, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
