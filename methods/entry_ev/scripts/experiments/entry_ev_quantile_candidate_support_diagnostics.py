#!/usr/bin/env python3
"""Diagnose quantile policy candidate row support before stateful replay."""

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
EXPERIMENTS = ROOT / "scripts" / "experiments"
if str(EXPERIMENTS) not in sys.path:
    sys.path.insert(0, str(EXPERIMENTS))

from trade_data.backtest import json_default, make_run_dir  # noqa: E402

from entry_ev_quantile_policy_backtest import (  # noqa: E402
    PolicyCandidate,
    parse_family_predictions,
    parse_policy_candidates,
    parse_role_months,
    policy_candidate_from_name,
    quantile_column,
)


SUMMARY_QUANTILES = (0.50, 0.90, 0.95, 0.99)
FUNNEL_COLUMNS = [
    "row_count",
    "valid_prediction_count",
    "selected_holding_ok_count",
    "score_quantile_ok_count",
    "side_gap_quantile_ok_count",
    "rank_quantile_ok_count",
    "quantile_all_ok_count",
    "quantile_hold_ok_count",
    "threshold_after_quantile_hold_count",
    "side_margin_after_quantile_hold_count",
    "candidate_row_count",
]


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


def month_series(frame: pd.DataFrame) -> pd.Series:
    if "dataset_month" in frame.columns:
        return frame["dataset_month"].astype(str).str.slice(0, 7)
    if "month" in frame.columns:
        return frame["month"].astype(str).str.slice(0, 7)
    if "decision_timestamp" in frame.columns:
        return pd.to_datetime(frame["decision_timestamp"], utc=True).dt.strftime(
            "%Y-%m"
        )
    raise ValueError("prediction frame needs dataset_month, month, or decision_timestamp")


def finite_numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        raise ValueError(f"missing prediction column: {column}")
    values = pd.to_numeric(frame[column], errors="coerce")
    return values.where(np.isfinite(values))


def bool_count(values: pd.Series) -> int:
    return int(values.fillna(False).astype(bool).sum())


def quantile_summary(values: pd.Series, prefix: str) -> dict[str, float]:
    clean = pd.to_numeric(values, errors="coerce").dropna()
    if clean.empty:
        result = {f"{prefix}_q{int(q * 100):02d}": np.nan for q in SUMMARY_QUANTILES}
        result[f"{prefix}_max"] = np.nan
        result[f"{prefix}_mean"] = np.nan
        return result
    result = {
        f"{prefix}_q{int(q * 100):02d}": float(clean.quantile(q))
        for q in SUMMARY_QUANTILES
    }
    result[f"{prefix}_max"] = float(clean.max())
    result[f"{prefix}_mean"] = float(clean.mean())
    return result


def add_base_columns(
    frame: pd.DataFrame,
    *,
    family: str,
    long_column: str,
    short_column: str,
    long_holding_column: str,
    short_holding_column: str,
    min_valid_predicted_hold_minutes: float,
) -> pd.DataFrame:
    result = frame.copy()
    result["family"] = family
    result["month"] = month_series(result)
    result["long_score"] = finite_numeric(result, long_column)
    result["short_score"] = finite_numeric(result, short_column)
    result["long_holding"] = finite_numeric(result, long_holding_column)
    result["short_holding"] = finite_numeric(result, short_holding_column)
    result["valid_prediction"] = (
        result["long_score"].notna() & result["short_score"].notna()
    )
    result["selected_side"] = np.where(
        result["long_score"] >= result["short_score"],
        1,
        -1,
    )
    result.loc[~result["valid_prediction"], "selected_side"] = 0
    result["selected_score"] = np.where(
        result["selected_side"].eq(1),
        result["long_score"],
        result["short_score"],
    )
    result["side_gap"] = (result["long_score"] - result["short_score"]).abs()
    result["long_holding_ok"] = result["long_holding"].notna() & (
        result["long_holding"] >= min_valid_predicted_hold_minutes
    )
    result["short_holding_ok"] = result["short_holding"].notna() & (
        result["short_holding"] >= min_valid_predicted_hold_minutes
    )
    result["selected_holding"] = np.where(
        result["selected_side"].eq(1),
        result["long_holding"],
        result["short_holding"],
    )
    result["selected_holding_ok"] = np.where(
        result["selected_side"].eq(1),
        result["long_holding_ok"],
        result["short_holding_ok"],
    )
    return result


def add_candidate_columns(
    frame: pd.DataFrame,
    *,
    candidate: PolicyCandidate,
    score_kind: str,
) -> pd.DataFrame:
    result = frame.copy()
    score_quantile_col = quantile_column(score_kind, "selected_score", candidate.scope)
    side_gap_quantile_col = quantile_column(score_kind, "side_gap", candidate.scope)
    rank_quantile_col = quantile_column(score_kind, "selected_entry_rank", candidate.scope)
    result["score_quantile"] = finite_numeric(result, score_quantile_col)
    result["side_gap_quantile"] = finite_numeric(result, side_gap_quantile_col)
    result["rank_quantile"] = finite_numeric(result, rank_quantile_col)
    result["score_quantile_ok"] = result["score_quantile"] >= candidate.score_quantile
    result["side_gap_quantile_ok"] = (
        result["side_gap_quantile"] >= candidate.side_gap_quantile
    )
    result["rank_quantile_ok"] = result["rank_quantile"] >= candidate.rank_quantile
    result["quantile_all_ok"] = (
        result["valid_prediction"]
        & result["score_quantile_ok"]
        & result["side_gap_quantile_ok"]
        & result["rank_quantile_ok"]
    )
    selected_threshold = np.where(
        result["selected_side"].eq(-1),
        candidate.entry_threshold + candidate.short_entry_threshold_offset,
        candidate.entry_threshold,
    )
    result["threshold_ok"] = result["selected_score"] > selected_threshold
    result["side_margin_ok"] = result["side_gap"] >= candidate.side_margin
    result["quantile_hold_ok"] = (
        result["quantile_all_ok"] & result["selected_holding_ok"].astype(bool)
    )
    result["threshold_after_quantile_hold_ok"] = (
        result["quantile_hold_ok"] & result["threshold_ok"]
    )
    result["side_margin_after_quantile_hold_ok"] = (
        result["quantile_hold_ok"] & result["side_margin_ok"]
    )
    result["candidate_row_ok"] = (
        result["quantile_hold_ok"] & result["threshold_ok"] & result["side_margin_ok"]
    )
    return result


def first_zero_stage(row: pd.Series) -> str:
    for column in FUNNEL_COLUMNS[1:]:
        if int(row[column]) == 0:
            return column.replace("_count", "")
    return ""


def summarize_candidate_group(
    group: pd.DataFrame,
    *,
    candidate: PolicyCandidate,
) -> dict[str, object]:
    valid = group["valid_prediction"].fillna(False).astype(bool)
    selected_long = group["selected_side"].eq(1)
    selected_short = group["selected_side"].eq(-1)
    candidate_ok = group["candidate_row_ok"].fillna(False).astype(bool)
    result: dict[str, object] = {
        "candidate": candidate.name,
        "scope": candidate.scope,
        "score_quantile": candidate.score_quantile,
        "side_gap_quantile": candidate.side_gap_quantile,
        "rank_quantile": candidate.rank_quantile,
        "entry_threshold": candidate.entry_threshold,
        "row_count": int(len(group)),
        "valid_prediction_count": bool_count(valid),
        "selected_holding_ok_count": bool_count(valid & group["selected_holding_ok"]),
        "score_quantile_ok_count": bool_count(valid & group["score_quantile_ok"]),
        "side_gap_quantile_ok_count": bool_count(valid & group["side_gap_quantile_ok"]),
        "rank_quantile_ok_count": bool_count(valid & group["rank_quantile_ok"]),
        "quantile_all_ok_count": bool_count(group["quantile_all_ok"]),
        "quantile_hold_ok_count": bool_count(group["quantile_hold_ok"]),
        "threshold_after_quantile_hold_count": bool_count(
            group["threshold_after_quantile_hold_ok"]
        ),
        "side_margin_after_quantile_hold_count": bool_count(
            group["side_margin_after_quantile_hold_ok"]
        ),
        "candidate_row_count": bool_count(candidate_ok),
        "candidate_long_count": bool_count(candidate_ok & selected_long),
        "candidate_short_count": bool_count(candidate_ok & selected_short),
        "valid_selected_long_count": bool_count(valid & selected_long),
        "valid_selected_short_count": bool_count(valid & selected_short),
    }
    for column, prefix in [
        ("selected_score", "selected_score"),
        ("side_gap", "side_gap"),
        ("score_quantile", "score_quantile"),
        ("side_gap_quantile", "side_gap_quantile"),
        ("rank_quantile", "rank_quantile"),
        ("selected_holding", "selected_holding"),
    ]:
        result.update(quantile_summary(group[column], prefix))
    quantile_hold = group["quantile_hold_ok"].fillna(False).astype(bool)
    candidate_rows = group["candidate_row_ok"].fillna(False).astype(bool)
    for mask, prefix in [
        (quantile_hold, "quantile_hold_selected_score"),
        (quantile_hold, "quantile_hold_side_gap"),
        (candidate_rows, "candidate_selected_score"),
        (candidate_rows, "candidate_side_gap"),
    ]:
        source_column = "selected_score" if "score" in prefix else "side_gap"
        result.update(quantile_summary(group.loc[mask, source_column], prefix))
    result["first_zero_stage"] = first_zero_stage(pd.Series(result))
    return result


def support_summaries_for_family(
    frame: pd.DataFrame,
    *,
    family: str,
    role_lookup: dict[tuple[str, str], str],
    candidates: list[PolicyCandidate],
    score_kind: str,
    long_column: str,
    short_column: str,
    long_holding_column: str,
    short_holding_column: str,
    min_valid_predicted_hold_minutes: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    base = add_base_columns(
        frame,
        family=family,
        long_column=long_column,
        short_column=short_column,
        long_holding_column=long_holding_column,
        short_holding_column=short_holding_column,
        min_valid_predicted_hold_minutes=min_valid_predicted_hold_minutes,
    )
    summary_rows: list[dict[str, object]] = []
    monthly_rows: list[dict[str, object]] = []
    for candidate in candidates:
        candidate_frame = add_candidate_columns(
            base,
            candidate=candidate,
            score_kind=score_kind,
        )
        summary = summarize_candidate_group(candidate_frame, candidate=candidate)
        summary["family"] = family
        summary_rows.append(summary)
        for month, group in candidate_frame.groupby("month", dropna=False):
            month_text = str(month)
            row = summarize_candidate_group(group, candidate=candidate)
            row["family"] = family
            row["month"] = month_text
            row["role"] = role_lookup.get((family, month_text), "")
            monthly_rows.append(row)
    return pd.DataFrame(summary_rows), pd.DataFrame(monthly_rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--family-predictions",
        action="append",
        required=True,
        help="family=path parquet prediction input. Repeat for each family.",
    )
    parser.add_argument(
        "--role-months",
        action="append",
        default=[],
        help="role=family:YYYY-MM,YYYY-MM. Repeat as needed.",
    )
    parser.add_argument("--score-kind", required=True)
    parser.add_argument("--long-column", required=True)
    parser.add_argument("--short-column", required=True)
    parser.add_argument("--long-holding-column", required=True)
    parser.add_argument("--short-holding-column", required=True)
    parser.add_argument("--policy-candidates", required=True)
    parser.add_argument("--min-valid-predicted-hold-minutes", type=float, default=30.0)
    parser.add_argument("--label", required=True)
    parser.add_argument("--output-root", type=Path, default=Path("data/reports/backtests"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    family_predictions = parse_family_predictions(args.family_predictions)
    role_lookup = parse_role_months(args.role_months) if args.role_months else {}
    candidates = [
        policy_candidate_from_name(name)
        for name in parse_policy_candidates(args.policy_candidates)
    ]
    summary_parts: list[pd.DataFrame] = []
    monthly_parts: list[pd.DataFrame] = []
    for family, prediction_path in family_predictions.items():
        frame = pd.read_parquet(prediction_path)
        summary, monthly = support_summaries_for_family(
            frame,
            family=family,
            role_lookup=role_lookup,
            candidates=candidates,
            score_kind=args.score_kind,
            long_column=args.long_column,
            short_column=args.short_column,
            long_holding_column=args.long_holding_column,
            short_holding_column=args.short_holding_column,
            min_valid_predicted_hold_minutes=args.min_valid_predicted_hold_minutes,
        )
        summary_parts.append(summary)
        monthly_parts.append(monthly)
    summary_df = pd.concat(summary_parts, ignore_index=True)
    monthly_df = pd.concat(monthly_parts, ignore_index=True)
    run_dir = make_run_dir(args.output_root, args.label)
    summary_df.to_csv(run_dir / "candidate_support_summary.csv", index=False)
    monthly_df.to_csv(run_dir / "candidate_support_monthly.csv", index=False)
    config = {
        "family_predictions": family_predictions,
        "role_months": args.role_months,
        "score_kind": args.score_kind,
        "long_column": args.long_column,
        "short_column": args.short_column,
        "long_holding_column": args.long_holding_column,
        "short_holding_column": args.short_holding_column,
        "policy_candidates": [candidate.name for candidate in candidates],
        "min_valid_predicted_hold_minutes": args.min_valid_predicted_hold_minutes,
    }
    (run_dir / "config.json").write_text(
        json.dumps(config, indent=2, default=local_json_default) + "\n",
        encoding="utf-8",
    )
    print(
        summary_df[
            [
                "family",
                "candidate",
                "valid_prediction_count",
                "quantile_all_ok_count",
                "quantile_hold_ok_count",
                "threshold_after_quantile_hold_count",
                "candidate_row_count",
                "candidate_long_count",
                "candidate_short_count",
                "first_zero_stage",
            ]
        ].to_string(index=False)
    )
    print(f"artifacts: {run_dir}")


if __name__ == "__main__":
    main()
