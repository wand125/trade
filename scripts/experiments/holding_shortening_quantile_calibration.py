#!/usr/bin/env python3
"""Add validation empirical-CDF quantile columns for holding-shortening scores."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from trade_data.quantile_calibration import add_empirical_quantile_columns  # noqa: E402


DEFAULT_COLUMNS = (
    "pred_long_fixed_60m_beats_exit_event_prob_1,"
    "pred_short_fixed_60m_beats_exit_event_prob_1"
)


def parse_csv_strings(value: str) -> list[str]:
    values = [part.strip() for part in value.split(",") if part.strip()]
    if not values:
        raise argparse.ArgumentTypeError("at least one value is required")
    return values


def json_default(value: Any) -> Any:
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, Path):
        return str(value)
    if pd.isna(value):
        return None
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fit-predictions", type=Path, required=True)
    parser.add_argument("--apply-predictions", type=Path, required=True)
    parser.add_argument("--output-path", type=Path, required=True)
    parser.add_argument("--summary-path", type=Path)
    parser.add_argument("--columns", default=DEFAULT_COLUMNS)
    parser.add_argument("--output-columns", default="")
    parser.add_argument("--suffix", default="_valid_quantile")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    columns = parse_csv_strings(args.columns)
    output_columns = parse_csv_strings(args.output_columns) if args.output_columns else None

    fit_frame = pd.read_parquet(args.fit_predictions)
    apply_frame = pd.read_parquet(args.apply_predictions)
    output, summary = add_empirical_quantile_columns(
        fit_frame,
        apply_frame,
        columns,
        suffix=args.suffix,
        output_columns=output_columns,
    )
    summary.update(
        {
            "fit_predictions": str(args.fit_predictions),
            "apply_predictions": str(args.apply_predictions),
            "output_path": str(args.output_path),
        }
    )

    args.output_path.parent.mkdir(parents=True, exist_ok=True)
    output.to_parquet(args.output_path, index=False)
    summary_path = args.summary_path or args.output_path.with_suffix(".summary.json")
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=json_default) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=json_default))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
