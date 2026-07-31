#!/usr/bin/env python3
"""Inventory existing entry-EV sweep artifacts for validation reuse."""

from __future__ import annotations

import argparse
import glob
import json
import re
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from trade_data.backtest import json_default, make_run_dir  # noqa: E402


FULL_RANK_VALUES = (0.0, 0.5, 0.6, 0.7, 0.8, 0.9)
FULL_RANK_ENTRY_THRESHOLDS = (8.0, 10.0, 12.0, 14.0)
FULL_RANK_SHORT_OFFSETS = (3.0, 6.0, 9.0)
NONRANK_ENTRY_THRESHOLDS = (0.0, 2.0, 4.0, 6.0, 8.0, 10.0, 12.0)
NONRANK_SHORT_OFFSETS = (0.0, 3.0, 6.0)
REFERENCE_KEY_COLUMNS = [
    "policy",
    "entry_threshold",
    "short_entry_threshold_offset",
    "side_margin",
    "risk_penalty",
    "min_entry_rank",
]
MONTH_PATTERN = re.compile(r"20\d{2}-\d{2}")


def local_json_default(value: Any) -> Any:
    try:
        return json_default(value)
    except TypeError:
        pass
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, np.bool_):
        return bool(value)
    raise TypeError(f"cannot serialize {type(value).__name__}")


def unique_float_values(frame: pd.DataFrame, column: str) -> list[float]:
    if column not in frame.columns:
        return []
    values = pd.to_numeric(frame[column], errors="coerce").dropna().unique().tolist()
    return sorted(float(value) for value in values)


def values_cover(values: list[float], expected: tuple[float, ...]) -> bool:
    observed = {round(value, 10) for value in values}
    required = {round(value, 10) for value in expected}
    return required.issubset(observed)


def classify_grid_profile(
    *,
    row_count: int,
    rank_values: list[float],
    entry_threshold_values: list[float],
    short_offset_values: list[float],
) -> str:
    has_full_rank = values_cover(rank_values, FULL_RANK_VALUES)
    has_full_entries = values_cover(
        entry_threshold_values,
        FULL_RANK_ENTRY_THRESHOLDS,
    )
    has_full_offsets = values_cover(short_offset_values, FULL_RANK_SHORT_OFFSETS)
    expected_full_rows = (
        len(FULL_RANK_VALUES)
        * len(FULL_RANK_ENTRY_THRESHOLDS)
        * len(FULL_RANK_SHORT_OFFSETS)
    )
    if (
        has_full_rank
        and has_full_entries
        and has_full_offsets
        and row_count >= expected_full_rows
    ):
        return "full_rank_grid"

    nonzero_ranks = [value for value in rank_values if round(value, 10) != 0.0]
    if nonzero_ranks:
        return "partial_rank_grid"

    has_nonrank_entries = values_cover(
        entry_threshold_values,
        NONRANK_ENTRY_THRESHOLDS,
    )
    has_nonrank_offsets = values_cover(short_offset_values, NONRANK_SHORT_OFFSETS)
    expected_nonrank_rows = len(NONRANK_ENTRY_THRESHOLDS) * len(
        NONRANK_SHORT_OFFSETS
    )
    if has_nonrank_entries and has_nonrank_offsets and row_count >= expected_nonrank_rows:
        return "nonrank_grid"

    return "other_grid"


def month_from_frame_or_path(frame: pd.DataFrame, metric_path: Path) -> str:
    if "period_start" in frame.columns and not frame["period_start"].dropna().empty:
        timestamp = pd.to_datetime(frame["period_start"].dropna().iloc[0], utc=True)
        return timestamp.strftime("%Y-%m")
    for part in reversed(metric_path.parts):
        match = MONTH_PATTERN.search(part)
        if match is not None:
            return match.group(0)
    return ""


def family_root(metric_path: Path) -> str:
    if len(metric_path.parents) >= 2:
        return metric_path.parents[1].name
    return ""


def infer_role_hint(metric_path: Path) -> str:
    raw = str(metric_path).lower()
    family = family_root(metric_path).lower()
    if "_test_" in raw or "fixed" in raw or "holdout" in raw:
        return "fixed_test_or_holdout"
    if family in {
        "20260630_entry_evcal_rank_fresh0304_calibrated",
        "20260630_entry_evcal_rank_refit2025_validation_calibrated",
    }:
        return "validation_candidate"
    if "rank_calibration" in family:
        return "calibration_validation_rank"
    if "validation" in family and "rank" not in family:
        return "calibration_validation_nonrank"
    if "fresh0304" in family and "rank" not in family:
        return "fresh_validation_nonrank"
    return "unknown"


def infer_protocol_hint(metric_path: Path) -> str:
    family = family_root(metric_path).lower()
    if "rank_fresh0304" in family:
        return "fresh2024_rank_validation"
    if "fresh0304" in family:
        return "fresh2024_nonrank_validation"
    if "rank_refit2025_validation" in family:
        return "refit2025_rank_validation"
    if "rank_refit2025_test" in family:
        return "refit2025_rank_fixed_test"
    if "rank_test_2024_05_12" in family:
        return "chrono2024_rank_fixed_test"
    if "rank_calibration" in family:
        return "chrono2024_rank_calibration_validation"
    if "validation" in family:
        return "chrono2024_calibration_validation"
    return "unknown"


def comparable_keys(frame: pd.DataFrame, key_columns: list[str]) -> set[tuple[str, ...]]:
    if not key_columns:
        return set()
    missing = [column for column in key_columns if column not in frame.columns]
    if missing:
        return set()
    normalized = frame[key_columns].copy()
    for column in key_columns:
        normalized[column] = normalized[column].map(lambda value: "" if pd.isna(value) else str(value))
    return set(map(tuple, normalized.drop_duplicates().itertuples(index=False, name=None)))


def build_inventory_row(
    metric_path: Path,
    frame: pd.DataFrame,
    reference_keys: set[tuple[str, ...]] | None = None,
    reference_key_columns: list[str] | None = None,
) -> dict[str, object]:
    rank_values = unique_float_values(frame, "min_entry_rank")
    entry_threshold_values = unique_float_values(frame, "entry_threshold")
    short_offset_values = unique_float_values(frame, "short_entry_threshold_offset")
    row_count = int(len(frame))
    grid_class = classify_grid_profile(
        row_count=row_count,
        rank_values=rank_values,
        entry_threshold_values=entry_threshold_values,
        short_offset_values=short_offset_values,
    )
    key_columns = reference_key_columns or []
    candidate_keys = comparable_keys(frame, key_columns)
    match_count = (
        len(candidate_keys & reference_keys)
        if reference_keys is not None
        else 0
    )
    candidate_key_count = len(candidate_keys)
    expected_full_rows = (
        len(FULL_RANK_VALUES)
        * len(FULL_RANK_ENTRY_THRESHOLDS)
        * len(FULL_RANK_SHORT_OFFSETS)
    )
    return {
        "metrics_path": str(metric_path),
        "family_root": family_root(metric_path),
        "run_name": metric_path.parent.name,
        "month": month_from_frame_or_path(frame, metric_path),
        "role_hint": infer_role_hint(metric_path),
        "protocol_hint": infer_protocol_hint(metric_path),
        "grid_class": grid_class,
        "row_count": row_count,
        "column_count": int(len(frame.columns)),
        "rank_count": len(rank_values),
        "entry_threshold_count": len(entry_threshold_values),
        "short_offset_count": len(short_offset_values),
        "rank_values": json.dumps(rank_values, ensure_ascii=False),
        "entry_threshold_values": json.dumps(entry_threshold_values, ensure_ascii=False),
        "short_offset_values": json.dumps(short_offset_values, ensure_ascii=False),
        "has_full_rank_values": values_cover(rank_values, FULL_RANK_VALUES),
        "has_full_rank_entries": values_cover(
            entry_threshold_values,
            FULL_RANK_ENTRY_THRESHOLDS,
        ),
        "has_full_rank_short_offsets": values_cover(
            short_offset_values,
            FULL_RANK_SHORT_OFFSETS,
        ),
        "full_rank_grid_coverage": float(row_count / expected_full_rows),
        "total_adjusted_pnl_sum": float(frame["total_adjusted_pnl"].sum())
        if "total_adjusted_pnl" in frame.columns
        else np.nan,
        "trade_count_sum": int(frame["trade_count"].sum())
        if "trade_count" in frame.columns
        else 0,
        "reference_key_columns": json.dumps(key_columns, ensure_ascii=False),
        "candidate_key_count": candidate_key_count,
        "reference_key_match_count": match_count,
        "reference_key_match_ratio": float(match_count / candidate_key_count)
        if candidate_key_count
        else 0.0,
    }


def summarize_inventory(inventory: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    grouped = inventory.groupby(
        ["family_root", "role_hint", "protocol_hint", "grid_class"],
        dropna=False,
    )
    for keys, group in grouped:
        family, role, protocol, grid_class = keys
        months = sorted(month for month in group["month"].astype(str).unique() if month)
        full_rank_months = int((group["grid_class"] == "full_rank_grid").sum())
        partial_rank_months = int((group["grid_class"] == "partial_rank_grid").sum())
        nonrank_months = int((group["grid_class"] == "nonrank_grid").sum())
        if role == "validation_candidate" and grid_class == "full_rank_grid":
            reuse_status = "usable_full_rank_validation_window"
        elif role == "calibration_validation_rank" and grid_class == "full_rank_grid":
            reuse_status = "calibration_full_rank_not_clean_holdout"
        elif role == "fixed_test_or_holdout":
            reuse_status = "fixed_test_not_reusable_for_same_audit"
        elif grid_class == "partial_rank_grid":
            reuse_status = "incomplete_grid_regenerate_before_comparison"
        elif grid_class == "nonrank_grid":
            reuse_status = "nonrank_grid_regenerate_rank_sweep_if_needed"
        else:
            reuse_status = "review_before_use"
        rows.append(
            {
                "family_root": family,
                "role_hint": role,
                "protocol_hint": protocol,
                "grid_class": grid_class,
                "admission_reuse_status": reuse_status,
                "metric_file_count": int(len(group)),
                "month_count": len(months),
                "months": ",".join(months),
                "total_rows": int(group["row_count"].sum()),
                "row_count_min": int(group["row_count"].min()),
                "row_count_max": int(group["row_count"].max()),
                "full_rank_months": full_rank_months,
                "partial_rank_months": partial_rank_months,
                "nonrank_months": nonrank_months,
                "trade_count_sum": int(group["trade_count_sum"].sum()),
                "total_adjusted_pnl_sum": float(group["total_adjusted_pnl_sum"].sum()),
                "candidate_key_count_min": int(group["candidate_key_count"].min()),
                "reference_key_match_count_min": int(
                    group["reference_key_match_count"].min()
                ),
                "reference_key_match_ratio_min": float(
                    group["reference_key_match_ratio"].min()
                ),
            }
        )
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(
        ["role_hint", "protocol_hint", "family_root", "grid_class"],
    ).reset_index(drop=True)


def expand_metric_paths(patterns: list[str]) -> list[Path]:
    paths: list[Path] = []
    for pattern in patterns:
        matches = [Path(match) for match in glob.glob(pattern, recursive=True)]
        if not matches and Path(pattern).exists():
            matches = [Path(pattern)]
        paths.extend(matches)
    unique = sorted({path for path in paths if path.name == "metrics.csv"})
    if not unique:
        raise ValueError("no metrics.csv files matched")
    return unique


def build_reference_keys(
    reference_summary: Path | None,
) -> tuple[set[tuple[str, ...]] | None, list[str]]:
    if reference_summary is None:
        return None, []
    frame = pd.read_csv(reference_summary)
    key_columns = [
        column for column in REFERENCE_KEY_COLUMNS if column in frame.columns
    ]
    keys = comparable_keys(frame, key_columns)
    return keys, key_columns


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--metric-glob",
        action="append",
        default=[],
        help="Glob for entry-EV metrics.csv files. Can be repeated.",
    )
    parser.add_argument("--reference-summary", type=Path)
    parser.add_argument("--label", default="entry_ev_validation_inventory")
    parser.add_argument("--output-dir", type=Path, default=Path("data/reports/backtests"))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    metric_globs = args.metric_glob or [
        "data/reports/backtests/20260630_entry_evcal*/**/metrics.csv"
    ]
    metric_paths = expand_metric_paths(metric_globs)
    reference_keys, reference_key_columns = build_reference_keys(args.reference_summary)

    rows: list[dict[str, object]] = []
    for metric_path in metric_paths:
        frame = pd.read_csv(metric_path)
        rows.append(
            build_inventory_row(
                metric_path,
                frame,
                reference_keys=reference_keys,
                reference_key_columns=reference_key_columns,
            )
        )
    inventory = pd.DataFrame(rows).sort_values(
        ["family_root", "month", "run_name", "metrics_path"],
    )
    summary = summarize_inventory(inventory)

    run_dir = make_run_dir(args.output_dir, args.label)
    inventory.to_csv(run_dir / "monthly_inventory.csv", index=False)
    summary.to_csv(run_dir / "window_candidate_summary.csv", index=False)
    manifest = {
        "mode": "entry_ev_validation_inventory",
        "metric_globs": metric_globs,
        "metric_file_count": int(len(metric_paths)),
        "reference_summary": str(args.reference_summary)
        if args.reference_summary is not None
        else None,
        "reference_key_columns": reference_key_columns,
        "reference_key_count": len(reference_keys) if reference_keys is not None else 0,
        "monthly_inventory": "monthly_inventory.csv",
        "window_candidate_summary": "window_candidate_summary.csv",
    }
    (run_dir / "inventory.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, default=local_json_default) + "\n",
        encoding="utf-8",
    )

    print(f"artifacts: {run_dir}")
    print(summary.to_string(index=False))
    usable = summary[
        summary["admission_reuse_status"] == "usable_full_rank_validation_window"
    ]
    print(f"usable full-rank validation windows: {len(usable)}")
    if not usable.empty:
        print(usable[["family_root", "months", "month_count"]].to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
