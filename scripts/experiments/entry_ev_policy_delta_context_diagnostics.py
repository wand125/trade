#!/usr/bin/env python3
"""Join policy trade-delta rows to prediction context and summarize failures."""

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
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from trade_data.backtest import json_default, make_run_dir  # noqa: E402

from entry_ev_forced_exit_selector_inputs import parse_family_predictions  # noqa: E402


CONTEXT_COLUMNS = [
    "dataset_month",
    "combined_regime",
    "session_regime",
    "trend_regime",
    "volatility_regime",
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


def parse_csv(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(np.nan, index=frame.index, dtype="float64")
    values = pd.to_numeric(frame[column], errors="coerce")
    return values.where(np.isfinite(values))


def optional_prediction_columns(frame: pd.DataFrame, score_kind: str) -> list[str]:
    columns = [
        "decision_timestamp",
        *[column for column in CONTEXT_COLUMNS if column in frame.columns],
    ]
    score_columns = [
        f"pred_{score_kind}_long_best_adjusted_pnl",
        f"pred_{score_kind}_short_best_adjusted_pnl",
        f"pred_{score_kind}_selected_score_pct_side_regime_session_month",
        f"pred_{score_kind}_side_gap_pct_side_regime_session_month",
        f"pred_{score_kind}_selected_entry_rank_pct_side_regime_session_month",
        f"pred_{score_kind}_long_forced_exit_blocked",
        f"pred_{score_kind}_short_forced_exit_blocked",
        f"pred_{score_kind}_long_risk_blocked",
        f"pred_{score_kind}_short_risk_blocked",
        f"pred_{score_kind}_long_replacement_guard_blocked",
        f"pred_{score_kind}_short_replacement_guard_blocked",
    ]
    columns.extend(column for column in score_columns if column in frame.columns)
    return list(dict.fromkeys(columns))


def load_prediction_lookup(path: Path, *, family: str, score_kind: str) -> pd.DataFrame:
    frame = pd.read_parquet(path, columns=None)
    columns = optional_prediction_columns(frame, score_kind)
    output = frame[columns].copy()
    output["family"] = family
    output["decision_timestamp"] = pd.to_datetime(
        output["decision_timestamp"],
        utc=True,
    )
    for column in CONTEXT_COLUMNS:
        if column not in output.columns:
            output[column] = "missing"
        output[column] = (
            output[column]
            .fillna("missing")
            .astype(str)
            .replace({"": "missing", "nan": "missing", "None": "missing"})
        )
    long_score = numeric(output, f"pred_{score_kind}_long_best_adjusted_pnl")
    short_score = numeric(output, f"pred_{score_kind}_short_best_adjusted_pnl")
    output["prediction_selected_side"] = np.where(long_score >= short_score, "long", "short")
    output.loc[long_score.isna() | short_score.isna(), "prediction_selected_side"] = "none"
    output["prediction_selected_score"] = np.where(
        output["prediction_selected_side"].eq("long"),
        long_score,
        short_score,
    )
    output["prediction_side_gap"] = (long_score - short_score).abs()
    return output


def add_delta_decision_timestamp(delta: pd.DataFrame) -> pd.DataFrame:
    output = delta.copy()
    candidate_ts = pd.Series(pd.NaT, index=output.index, dtype="datetime64[ns, UTC]")
    base_ts = pd.Series(pd.NaT, index=output.index, dtype="datetime64[ns, UTC]")
    shared_ts = pd.Series(pd.NaT, index=output.index, dtype="datetime64[ns, UTC]")
    if "candidate_entry_decision_timestamp" in output.columns:
        candidate_ts = pd.to_datetime(
            output["candidate_entry_decision_timestamp"],
            utc=True,
            errors="coerce",
        )
    if "base_entry_decision_timestamp" in output.columns:
        base_ts = pd.to_datetime(
            output["base_entry_decision_timestamp"],
            utc=True,
            errors="coerce",
        )
    if "entry_decision_timestamp" in output.columns:
        shared_ts = pd.to_datetime(
            output["entry_decision_timestamp"],
            utc=True,
            errors="coerce",
        )
    output["delta_entry_decision_timestamp"] = (
        candidate_ts.where(candidate_ts.notna(), base_ts)
        .where(lambda values: values.notna(), shared_ts)
    )
    return output


def enrich_delta_with_context(
    delta: pd.DataFrame,
    *,
    family_predictions: dict[str, Path],
    score_kind: str,
) -> pd.DataFrame:
    output = add_delta_decision_timestamp(delta)
    lookups = [
        load_prediction_lookup(path, family=family, score_kind=score_kind)
        for family, path in family_predictions.items()
    ]
    lookup = pd.concat(lookups, ignore_index=True)
    enriched = output.merge(
        lookup,
        left_on=["family", "delta_entry_decision_timestamp"],
        right_on=["family", "decision_timestamp"],
        how="left",
        suffixes=("", "_prediction"),
    )
    enriched["context_id"] = (
        enriched["direction"].astype(str)
        + "/"
        + enriched["combined_regime"].fillna("missing").astype(str)
        + "/"
        + enriched["session_regime"].fillna("missing").astype(str)
    )
    return enriched


def summarize_group(frame: pd.DataFrame, group_columns: list[str]) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame()
    rows: list[dict[str, object]] = []
    for keys, group in frame.groupby(group_columns, dropna=False):
        if not isinstance(keys, tuple):
            keys = (keys,)
        candidate_pnl = numeric(group, "candidate_adjusted_pnl")
        base_pnl = numeric(group, "base_adjusted_pnl")
        rows.append(
            {
                **dict(zip(group_columns, keys, strict=True)),
                "row_count": int(len(group)),
                "base_trade_count": int(group["base_present"].fillna(False).sum())
                if "base_present" in group.columns
                else 0,
                "candidate_trade_count": int(
                    group["candidate_present"].fillna(False).sum()
                )
                if "candidate_present" in group.columns
                else 0,
                "base_adjusted_pnl": float(base_pnl.sum(skipna=True)),
                "candidate_adjusted_pnl": float(candidate_pnl.sum(skipna=True)),
                "pnl_delta": float(numeric(group, "pnl_delta").sum(skipna=True)),
                "candidate_win_rate": float((candidate_pnl > 0).mean())
                if candidate_pnl.notna().any()
                else np.nan,
                "added_positive_pnl": float(candidate_pnl[candidate_pnl > 0].sum()),
                "added_negative_pnl": float(candidate_pnl[candidate_pnl < 0].sum()),
                "avg_prediction_selected_score": float(
                    numeric(group, "prediction_selected_score").mean()
                ),
                "avg_prediction_side_gap": float(numeric(group, "prediction_side_gap").mean()),
            }
        )
    return pd.DataFrame(rows).sort_values(
        ["candidate_adjusted_pnl", "row_count"],
        ascending=[True, False],
    )


def run_diagnostics(args: argparse.Namespace) -> Path:
    family_predictions = parse_family_predictions(args.family_predictions)
    delta = pd.read_csv(args.trade_delta_rows)
    if args.candidates:
        candidates = set(parse_csv(args.candidates))
        delta = delta[delta["candidate"].astype(str).isin(candidates)].copy()
    if args.families:
        families = set(parse_csv(args.families))
        delta = delta[delta["family"].astype(str).isin(families)].copy()
    enriched = enrich_delta_with_context(
        delta,
        family_predictions=family_predictions,
        score_kind=args.score_kind,
    )
    run_dir = make_run_dir(args.output_dir, args.label)
    enriched.to_csv(run_dir / "enriched_trade_delta_rows.csv", index=False)

    summaries = {
        "status_context": ["delta_status", "context_id"],
        "candidate_status_context": ["candidate", "delta_status", "context_id"],
        "month_candidate_status_context": [
            "month",
            "candidate",
            "delta_status",
            "context_id",
        ],
        "only_candidate_context": ["candidate", "context_id"],
        "only_candidate_month_context": ["month", "candidate", "context_id"],
    }
    for name, columns in summaries.items():
        source = enriched
        if name.startswith("only_candidate"):
            source = enriched[enriched["delta_status"].eq("only_candidate")].copy()
        summary = summarize_group(source, columns)
        summary.to_csv(run_dir / f"{name}_summary.csv", index=False)

    config = {
        "trade_delta_rows": args.trade_delta_rows,
        "family_predictions": family_predictions,
        "score_kind": args.score_kind,
        "candidates": args.candidates,
        "families": args.families,
    }
    (run_dir / "config.json").write_text(
        json.dumps(config, indent=2, default=local_json_default) + "\n",
        encoding="utf-8",
    )
    only_candidate = summarize_group(
        enriched[enriched["delta_status"].eq("only_candidate")],
        ["candidate", "context_id"],
    )
    print("only-candidate context:")
    print(
        only_candidate.head(20)[
            [
                "candidate",
                "context_id",
                "row_count",
                "candidate_adjusted_pnl",
                "added_positive_pnl",
                "added_negative_pnl",
            ]
        ].to_string(index=False)
    )
    print(f"artifacts: {run_dir}")
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trade-delta-rows", type=Path, required=True)
    parser.add_argument("--family-predictions", action="append", required=True)
    parser.add_argument("--score-kind", required=True)
    parser.add_argument("--candidates", default="")
    parser.add_argument("--families", default="")
    parser.add_argument("--output-dir", type=Path, default=Path("data/reports/backtests"))
    parser.add_argument("--label", default="entry_ev_policy_delta_context_diagnostics")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    run_diagnostics(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
