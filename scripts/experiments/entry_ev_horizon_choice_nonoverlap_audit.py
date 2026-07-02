#!/usr/bin/env python3
"""Audit horizon-choice threshold rows under one-position non-overlap constraints."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


REQUIRED_COLUMNS = {
    "family",
    "role",
    "month",
    "row_scope",
    "decision_timestamp",
    "prob_threshold",
    "ev_threshold",
    "tail_prob_threshold",
    "require_model_used",
    "hv_chosen_horizon_minutes",
    "hv_chosen_score",
    "actual_pnl_at_hv_chosen_horizon",
    "hv_choice_executable",
    "hv_choice_regret",
    "hv_choice_model_used",
}


def bool_series(frame: pd.DataFrame, column: str, default: bool = False) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=bool)
    series = frame[column]
    if pd.api.types.is_bool_dtype(series):
        return series.fillna(default).astype(bool)
    if pd.api.types.is_numeric_dtype(series):
        return series.fillna(float(default)).astype(float).ne(0.0)
    return series.astype(str).str.lower().str.strip().isin({"true", "1", "yes", "y"})


def numeric_series(frame: pd.DataFrame, column: str, default: float = np.nan) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=float)
    return (
        pd.to_numeric(frame[column], errors="coerce")
        .replace([np.inf, -np.inf], np.nan)
        .fillna(default)
        .astype(float)
    )


def normalize_choices(frame: pd.DataFrame) -> pd.DataFrame:
    missing = sorted(REQUIRED_COLUMNS - set(frame.columns))
    if missing:
        raise ValueError("choices missing columns: " + ", ".join(missing))
    output = frame.copy()
    output["month"] = output["month"].astype(str).str.slice(0, 7)
    output["decision_timestamp"] = pd.to_datetime(
        output["decision_timestamp"],
        utc=True,
        errors="coerce",
    )
    for column in ["family", "role", "row_scope", "side"]:
        if column in output.columns:
            output[column] = output[column].astype(str)
    for column in [
        "prob_threshold",
        "ev_threshold",
        "tail_prob_threshold",
        "hv_chosen_horizon_minutes",
        "hv_chosen_score",
        "actual_pnl_at_hv_chosen_horizon",
        "hv_choice_regret",
    ]:
        output[column] = numeric_series(output, column)
    output["require_model_used"] = bool_series(output, "require_model_used")
    output["hv_choice_executable"] = bool_series(output, "hv_choice_executable")
    output["hv_choice_model_used"] = bool_series(output, "hv_choice_model_used")
    return output


def interval_overlaps(
    start: pd.Timestamp,
    end: pd.Timestamp,
    intervals: list[tuple[pd.Timestamp, pd.Timestamp]],
) -> bool:
    return any(start < existing_end and end > existing_start for existing_start, existing_end in intervals)


def greedy_nonoverlap_choices(
    choices: pd.DataFrame,
    *,
    sort_column: str,
) -> pd.DataFrame:
    chosen_rows: list[pd.Series] = []
    if choices.empty:
        return choices.copy()
    sort_values = [sort_column, "decision_timestamp"]
    ascending = [False, True]
    for _, group in choices.sort_values(sort_values, ascending=ascending).groupby(
        ["family", "role", "month"],
        dropna=False,
    ):
        intervals: list[tuple[pd.Timestamp, pd.Timestamp]] = []
        for _, row in group.iterrows():
            start = row["decision_timestamp"]
            if pd.isna(start):
                continue
            horizon = float(row["hv_chosen_horizon_minutes"])
            if not np.isfinite(horizon) or horizon <= 0:
                continue
            end = start + pd.to_timedelta(horizon, unit="m")
            if interval_overlaps(start, end, intervals):
                continue
            intervals.append((start, end))
            intervals.sort()
            chosen_rows.append(row)
    if not chosen_rows:
        return choices.iloc[0:0].copy()
    output = pd.DataFrame(chosen_rows).reset_index(drop=True)
    output["nonoverlap_rank"] = np.arange(1, len(output) + 1)
    return output


def summarize_threshold(raw: pd.DataFrame, nonoverlap: pd.DataFrame) -> dict[str, Any]:
    raw_actual = numeric_series(raw, "actual_pnl_at_hv_chosen_horizon")
    non_actual = numeric_series(nonoverlap, "actual_pnl_at_hv_chosen_horizon")
    return {
        "raw_chosen_count": int(len(raw)),
        "raw_actual_pnl_sum": float(raw_actual.sum()) if len(raw) else 0.0,
        "raw_executable_count": int(bool_series(raw, "hv_choice_executable").sum()),
        "raw_model_used_count": int(bool_series(raw, "hv_choice_model_used").sum()),
        "raw_regret_sum": float(numeric_series(raw, "hv_choice_regret").sum())
        if len(raw)
        else 0.0,
        "nonoverlap_chosen_count": int(len(nonoverlap)),
        "nonoverlap_actual_pnl_sum": float(non_actual.sum()) if len(nonoverlap) else 0.0,
        "nonoverlap_actual_pnl_mean": float(non_actual.mean()) if len(nonoverlap) else np.nan,
        "nonoverlap_executable_count": int(
            bool_series(nonoverlap, "hv_choice_executable").sum()
        ),
        "nonoverlap_model_used_count": int(
            bool_series(nonoverlap, "hv_choice_model_used").sum()
        ),
        "nonoverlap_regret_sum": float(numeric_series(nonoverlap, "hv_choice_regret").sum())
        if len(nonoverlap)
        else 0.0,
    }


def audit_choices(
    frame: pd.DataFrame,
    *,
    sort_column: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    choices = normalize_choices(frame)
    choices = choices[numeric_series(choices, "hv_chosen_horizon_minutes", default=0.0).gt(0.0)]
    rows: list[dict[str, Any]] = []
    selected: list[pd.DataFrame] = []
    group_columns = [
        "row_scope",
        "prob_threshold",
        "ev_threshold",
        "tail_prob_threshold",
        "require_model_used",
    ]
    for key, group in choices.groupby(group_columns, dropna=False):
        if not isinstance(key, tuple):
            key = (key,)
        nonoverlap = greedy_nonoverlap_choices(group, sort_column=sort_column)
        for column, value in zip(group_columns, key):
            nonoverlap[column] = value
        selected.append(nonoverlap)
        row = dict(zip(group_columns, key))
        row.update(summarize_threshold(group, nonoverlap))
        rows.append(row)
    summary = pd.DataFrame(rows)
    if not summary.empty:
        summary = summary.sort_values(
            ["row_scope", "nonoverlap_actual_pnl_sum", "nonoverlap_chosen_count"],
            ascending=[True, False, False],
        )
    selected_frame = pd.concat(selected, ignore_index=True) if selected else pd.DataFrame()
    return summary, selected_frame


def build_outputs(args: argparse.Namespace) -> tuple[Path, Path]:
    choices = pd.read_csv(args.choices)
    summary, selected = audit_choices(choices, sort_column=args.sort_column)
    output_dir = args.output_dir or args.choices.parent
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / f"{args.prefix}_nonoverlap_summary.csv"
    choices_path = output_dir / f"{args.prefix}_nonoverlap_choices.csv"
    summary.to_csv(summary_path, index=False)
    selected.to_csv(choices_path, index=False)
    print("Non-overlap summary:")
    print(summary.head(args.print_rows).to_string(index=False))
    print(f"summary: {summary_path}")
    print(f"choices: {choices_path}")
    return summary_path, choices_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--choices", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--prefix", default="horizon_choice")
    parser.add_argument("--sort-column", default="hv_chosen_score")
    parser.add_argument("--print-rows", type=int, default=20)
    return parser


def main(argv: list[str] | None = None) -> int:
    build_outputs(build_parser().parse_args(argv))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
