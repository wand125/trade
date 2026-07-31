#!/usr/bin/env python3
"""Estimate prior-only context guards on policy trade-delta rows."""

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

from trade_data.backtest import json_default, make_run_dir  # noqa: E402


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


def parse_ints(value: str) -> list[int]:
    return [int(part) for part in parse_csv(value)]


def parse_floats(value: str) -> list[float]:
    return [float(part) for part in parse_csv(value)]


def numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(np.nan, index=frame.index, dtype="float64")
    values = pd.to_numeric(frame[column], errors="coerce")
    return values.where(np.isfinite(values))


def normalize_text(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series("missing", index=frame.index, dtype="object")
    return (
        frame[column]
        .fillna("missing")
        .astype(str)
        .replace({"": "missing", "nan": "missing", "None": "missing"})
    )


def add_context_scopes(frame: pd.DataFrame) -> pd.DataFrame:
    output = frame.copy()
    direction = normalize_text(output, "direction")
    combined = normalize_text(output, "combined_regime")
    session = normalize_text(output, "session_regime")
    output["direction_regime"] = direction + "/" + combined
    output["direction_session"] = direction + "/" + session
    output["direction_regime_session"] = direction + "/" + combined + "/" + session
    if "context_id" not in output.columns:
        output["context_id"] = output["direction_regime_session"]
    else:
        output["context_id"] = normalize_text(output, "context_id")
    return output


def add_month_period(frame: pd.DataFrame) -> pd.DataFrame:
    output = frame.copy()
    if "month" not in output.columns:
        raise ValueError("input rows must contain a month column")
    month = output["month"].fillna("").astype(str).str.slice(0, 7)
    output["month"] = month
    output["month_period"] = pd.PeriodIndex(month, freq="M")
    return output


def add_prior_stats(
    frame: pd.DataFrame,
    *,
    scope_column: str,
    pnl_column: str = "candidate_adjusted_pnl",
) -> pd.DataFrame:
    source = add_month_period(add_context_scopes(frame))
    if scope_column not in source.columns:
        raise ValueError(f"missing scope column: {scope_column}")
    if "candidate" not in source.columns:
        raise ValueError("input rows must contain candidate")
    source[pnl_column] = numeric(source, pnl_column).fillna(0.0)
    prior_source = source[source["delta_status"].eq("only_candidate")].copy()
    prior_columns = [
        "prior_trade_count",
        "prior_month_count",
        "prior_pnl_sum",
        "prior_negative_pnl",
        "prior_positive_pnl",
        "prior_loss_count",
        "prior_worst_trade",
        "prior_avg_pnl",
    ]
    for column in prior_columns:
        source[column] = 0.0
    group_columns = ["candidate", scope_column]
    for _, group in source.groupby(group_columns, dropna=False):
        prior_group = prior_source.loc[group.index.intersection(prior_source.index)]
        for idx, row in group.iterrows():
            prior = prior_group[prior_group["month_period"] < row["month_period"]]
            pnl = prior[pnl_column].astype(float)
            source.at[idx, "prior_trade_count"] = int(len(prior))
            source.at[idx, "prior_month_count"] = int(prior["month"].nunique())
            source.at[idx, "prior_pnl_sum"] = float(pnl.sum())
            source.at[idx, "prior_negative_pnl"] = float(pnl[pnl < 0].sum())
            source.at[idx, "prior_positive_pnl"] = float(pnl[pnl > 0].sum())
            source.at[idx, "prior_loss_count"] = int((pnl < 0).sum())
            source.at[idx, "prior_worst_trade"] = float(pnl.min()) if len(pnl) else 0.0
            source.at[idx, "prior_avg_pnl"] = float(pnl.mean()) if len(pnl) else 0.0
    return source.drop(columns=["month_period"])


def summarize_thresholds(
    rows: pd.DataFrame,
    *,
    scope_column: str,
    min_prior_counts: list[int],
    min_prior_months: list[int],
    loss_thresholds: list[float],
    pnl_column: str = "candidate_adjusted_pnl",
) -> pd.DataFrame:
    only = rows[rows["delta_status"].eq("only_candidate")].copy()
    if only.empty:
        return pd.DataFrame()
    pnl = numeric(only, pnl_column).fillna(0.0)
    only[pnl_column] = pnl
    summary_rows: list[dict[str, object]] = []
    for min_count in min_prior_counts:
        for min_months in min_prior_months:
            for threshold in loss_thresholds:
                flagged = (
                    only["prior_trade_count"].astype(float).ge(min_count)
                    & only["prior_month_count"].astype(float).ge(min_months)
                    & only["prior_pnl_sum"].astype(float).le(-threshold)
                )
                flagged_pnl = only.loc[flagged, pnl_column].astype(float)
                kept_pnl = only.loc[~flagged, pnl_column].astype(float)
                total_pnl = float(only[pnl_column].sum())
                flagged_count = int(flagged.sum())
                summary_rows.append(
                    {
                        "scope": scope_column,
                        "min_prior_count": min_count,
                        "min_prior_months": min_months,
                        "prior_loss_threshold": threshold,
                        "row_count": int(len(only)),
                        "flagged_count": flagged_count,
                        "flagged_share": float(flagged_count / len(only)),
                        "flagged_pnl": float(flagged_pnl.sum()),
                        "flagged_positive_pnl": float(flagged_pnl[flagged_pnl > 0].sum()),
                        "flagged_negative_pnl": float(flagged_pnl[flagged_pnl < 0].sum()),
                        "kept_pnl": float(kept_pnl.sum()),
                        "total_pnl": total_pnl,
                        "no_replacement_estimated_pnl": float(kept_pnl.sum()),
                        "no_replacement_estimated_delta": float(-flagged_pnl.sum()),
                        "flagged_wins": int((flagged_pnl > 0).sum()),
                        "flagged_losses": int((flagged_pnl < 0).sum()),
                        "first_flagged_month": (
                            str(only.loc[flagged, "month"].min()) if flagged_count else ""
                        ),
                    }
                )
    return pd.DataFrame(summary_rows).sort_values(
        [
            "no_replacement_estimated_pnl",
            "no_replacement_estimated_delta",
            "flagged_count",
        ],
        ascending=[False, False, True],
    )


def summarize_flagged_contexts(
    rows: pd.DataFrame,
    *,
    scope_column: str,
    min_prior_count: int,
    min_prior_months: int,
    prior_loss_threshold: float,
    pnl_column: str = "candidate_adjusted_pnl",
) -> pd.DataFrame:
    output_columns = [
        "candidate",
        scope_column,
        "flagged_count",
        "flagged_pnl",
        "flagged_positive_pnl",
        "flagged_negative_pnl",
        "first_month",
        "last_month",
        "prior_pnl_sum_mean",
        "prior_trade_count_mean",
    ]
    only = rows[rows["delta_status"].eq("only_candidate")].copy()
    if only.empty:
        return pd.DataFrame(columns=output_columns)
    only[pnl_column] = numeric(only, pnl_column).fillna(0.0)
    flagged = (
        only["prior_trade_count"].astype(float).ge(min_prior_count)
        & only["prior_month_count"].astype(float).ge(min_prior_months)
        & only["prior_pnl_sum"].astype(float).le(-prior_loss_threshold)
    )
    flagged_rows = only[flagged].copy()
    if flagged_rows.empty:
        return pd.DataFrame(columns=output_columns)
    group_columns = ["candidate", scope_column]
    rows_out: list[dict[str, object]] = []
    for key, group in flagged_rows.groupby(group_columns, dropna=False):
        if not isinstance(key, tuple):
            key = (key,)
        pnl = group[pnl_column].astype(float)
        rows_out.append(
            {
                **dict(zip(group_columns, key, strict=True)),
                "flagged_count": int(len(group)),
                "flagged_pnl": float(pnl.sum()),
                "flagged_positive_pnl": float(pnl[pnl > 0].sum()),
                "flagged_negative_pnl": float(pnl[pnl < 0].sum()),
                "first_month": str(group["month"].min()),
                "last_month": str(group["month"].max()),
                "prior_pnl_sum_mean": float(group["prior_pnl_sum"].astype(float).mean()),
                "prior_trade_count_mean": float(
                    group["prior_trade_count"].astype(float).mean()
                ),
            }
        )
    return pd.DataFrame(rows_out, columns=output_columns).sort_values(
        ["flagged_pnl", "flagged_count"],
        ascending=[True, False],
    )


def run_diagnostics(args: argparse.Namespace) -> Path:
    rows = pd.read_csv(args.enriched_delta_rows)
    rows = add_context_scopes(rows)
    if args.candidates:
        candidates = set(parse_csv(args.candidates))
        rows = rows[rows["candidate"].astype(str).isin(candidates)].copy()
    if args.families:
        families = set(parse_csv(args.families))
        rows = rows[rows["family"].astype(str).isin(families)].copy()
    scopes = parse_csv(args.scopes)
    min_prior_counts = parse_ints(args.min_prior_counts)
    min_prior_months = parse_ints(args.min_prior_months)
    loss_thresholds = parse_floats(args.prior_loss_thresholds)
    run_dir = make_run_dir(args.output_dir, args.label)

    summary_frames: list[pd.DataFrame] = []
    candidate_summary_frames: list[pd.DataFrame] = []
    for scope in scopes:
        scoped = add_prior_stats(rows, scope_column=scope)
        scoped.to_csv(run_dir / f"{scope}_prior_context_rows.csv", index=False)
        summary = summarize_thresholds(
            scoped,
            scope_column=scope,
            min_prior_counts=min_prior_counts,
            min_prior_months=min_prior_months,
            loss_thresholds=loss_thresholds,
        )
        summary.to_csv(run_dir / f"{scope}_prior_context_guard_summary.csv", index=False)
        scoped_candidate_summaries: list[pd.DataFrame] = []
        for candidate, candidate_rows in scoped.groupby("candidate", dropna=False):
            candidate_summary = summarize_thresholds(
                candidate_rows,
                scope_column=scope,
                min_prior_counts=min_prior_counts,
                min_prior_months=min_prior_months,
                loss_thresholds=loss_thresholds,
            )
            if not candidate_summary.empty:
                candidate_summary.insert(0, "candidate", candidate)
                scoped_candidate_summaries.append(candidate_summary)
        scoped_candidate_summary = (
            pd.concat(scoped_candidate_summaries, ignore_index=True)
            if scoped_candidate_summaries
            else pd.DataFrame()
        )
        scoped_candidate_summary.to_csv(
            run_dir / f"{scope}_candidate_prior_context_guard_summary.csv",
            index=False,
        )
        if not summary.empty:
            best = summary.iloc[0]
            contexts = summarize_flagged_contexts(
                scoped,
                scope_column=scope,
                min_prior_count=int(best["min_prior_count"]),
                min_prior_months=int(best["min_prior_months"]),
                prior_loss_threshold=float(best["prior_loss_threshold"]),
            )
            contexts.to_csv(run_dir / f"{scope}_best_flagged_contexts.csv", index=False)
        summary_frames.append(summary)
        candidate_summary_frames.append(scoped_candidate_summary)

    all_summary = (
        pd.concat(summary_frames, ignore_index=True)
        if summary_frames
        else pd.DataFrame()
    )
    all_summary.to_csv(run_dir / "prior_context_guard_summary.csv", index=False)
    all_candidate_summary = (
        pd.concat(candidate_summary_frames, ignore_index=True)
        if candidate_summary_frames
        else pd.DataFrame()
    )
    all_candidate_summary.to_csv(
        run_dir / "candidate_prior_context_guard_summary.csv",
        index=False,
    )
    config = {
        "enriched_delta_rows": args.enriched_delta_rows,
        "candidates": args.candidates,
        "families": args.families,
        "scopes": scopes,
        "min_prior_counts": min_prior_counts,
        "min_prior_months": min_prior_months,
        "prior_loss_thresholds": loss_thresholds,
    }
    (run_dir / "config.json").write_text(
        json.dumps(config, indent=2, default=local_json_default) + "\n",
        encoding="utf-8",
    )
    if not all_summary.empty:
        print("Prior context guard summary:")
        print(
            all_summary.head(20)[
                [
                    "scope",
                    "min_prior_count",
                    "min_prior_months",
                    "prior_loss_threshold",
                    "flagged_count",
                    "flagged_pnl",
                    "kept_pnl",
                    "no_replacement_estimated_delta",
                    "first_flagged_month",
                ]
            ].to_string(index=False)
        )
    print(f"artifacts: {run_dir}")
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--enriched-delta-rows", type=Path, required=True)
    parser.add_argument("--candidates", default="")
    parser.add_argument("--families", default="")
    parser.add_argument(
        "--scopes",
        default="direction_regime,context_id",
        help="comma-separated context columns to evaluate",
    )
    parser.add_argument("--min-prior-counts", default="1,2,3")
    parser.add_argument("--min-prior-months", default="1")
    parser.add_argument("--prior-loss-thresholds", default="20,40,60,100")
    parser.add_argument("--output-dir", type=Path, default=Path("data/reports/backtests"))
    parser.add_argument("--label", default="entry_ev_delta_prior_context_guard")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    run_diagnostics(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
