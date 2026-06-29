#!/usr/bin/env python3
"""Merge selected columns from one prediction parquet into another."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


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
    parser.add_argument("--base-predictions", type=Path, required=True)
    parser.add_argument(
        "--source-predictions",
        type=Path,
        required=True,
        help="comma-separated parquet files containing columns to merge",
    )
    parser.add_argument("--output-path", type=Path, required=True)
    parser.add_argument("--summary-path", type=Path)
    parser.add_argument("--columns", required=True, help="comma-separated columns to merge")
    parser.add_argument("--keys", default="dataset_month,decision_timestamp")
    parser.add_argument(
        "--replace-existing",
        action="store_true",
        help="replace columns already present in the base prediction frame",
    )
    return parser


def read_sources(paths: list[Path], keys: list[str], columns: list[str]) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for path in paths:
        frame = pd.read_parquet(path)
        available_columns = [column for column in columns if column in frame.columns]
        missing_keys = [key for key in keys if key not in frame.columns]
        if missing_keys:
            raise ValueError(f"{path} missing merge keys: {', '.join(missing_keys)}")
        if not available_columns:
            continue
        frames.append(frame[[*keys, *available_columns]].copy())
    if not frames:
        raise ValueError("no requested columns were found in source predictions")
    source = pd.concat(frames, ignore_index=True)
    duplicated = source.duplicated(keys)
    if duplicated.any():
        duplicate_count = int(duplicated.sum())
        raise ValueError(f"source predictions contain duplicate merge keys: {duplicate_count}")
    return source


def merge_prediction_columns(
    base: pd.DataFrame,
    source: pd.DataFrame,
    keys: list[str],
    columns: list[str],
    replace_existing: bool,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    missing_base_keys = [key for key in keys if key not in base.columns]
    if missing_base_keys:
        raise ValueError(f"base predictions missing merge keys: {', '.join(missing_base_keys)}")

    output = base.copy()
    merge_columns = [
        column
        for column in columns
        if column in source.columns and (replace_existing or column not in output.columns)
    ]
    skipped_existing = [
        column for column in columns if column in source.columns and column in output.columns and not replace_existing
    ]
    missing_source_columns = [column for column in columns if column not in source.columns]
    if not merge_columns:
        return output, {
            "rows": int(len(output)),
            "added_columns": [],
            "skipped_existing_columns": skipped_existing,
            "missing_source_columns": missing_source_columns,
            "matched_rows": 0,
            "missing_matches": int(len(output)),
        }

    if replace_existing:
        output = output.drop(columns=[column for column in merge_columns if column in output.columns])

    source_subset = source[[*keys, *merge_columns]].copy()
    source_subset["__merge_prediction_columns_matched"] = True
    merged = output.merge(source_subset, on=keys, how="left", validate="many_to_one")
    matched = merged["__merge_prediction_columns_matched"].eq(True)
    merged = merged.drop(columns=["__merge_prediction_columns_matched"])
    return merged, {
        "rows": int(len(merged)),
        "added_columns": merge_columns,
        "skipped_existing_columns": skipped_existing,
        "missing_source_columns": missing_source_columns,
        "matched_rows": int(matched.sum()),
        "missing_matches": int((~matched).sum()),
    }


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    source_paths = [Path(part.strip()) for part in str(args.source_predictions).split(",") if part.strip()]
    columns = parse_csv_strings(args.columns)
    keys = parse_csv_strings(args.keys)
    base = pd.read_parquet(args.base_predictions)
    source = read_sources(source_paths, keys, columns)
    output, summary = merge_prediction_columns(
        base,
        source,
        keys,
        columns,
        replace_existing=args.replace_existing,
    )
    summary.update(
        {
            "base_predictions": str(args.base_predictions),
            "source_predictions": [str(path) for path in source_paths],
            "output_path": str(args.output_path),
            "keys": keys,
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
