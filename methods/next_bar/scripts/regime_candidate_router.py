#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from trade_data.next_bar_regime_router import run_regime_router


def candidate(value: str) -> tuple[str, Path]:
    candidate_id, separator, directory = value.partition("=")
    if not separator or not candidate_id or not directory:
        raise argparse.ArgumentTypeError("candidate must use ID=PATH")
    return candidate_id, Path(directory)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Route fixed next-bar candidates by causal volatility regime."
    )
    parser.add_argument("--candidate", type=candidate, action="append", required=True)
    parser.add_argument("--fallback-candidate", default="path")
    parser.add_argument("--timeframe", type=int, default=1)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    candidate_ids = [candidate_id for candidate_id, _ in args.candidate]
    if len(candidate_ids) != len(set(candidate_ids)):
        parser.error("candidate IDs must be unique")
    report = run_regime_router(
        dict(args.candidate),
        args.output_dir,
        args.timeframe,
        fallback_candidate_id=args.fallback_candidate,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
