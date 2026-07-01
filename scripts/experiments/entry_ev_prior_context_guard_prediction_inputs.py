#!/usr/bin/env python3
"""Add prior-context guard flags to pre-block Entry EV prediction inputs."""

from __future__ import annotations

import argparse
import json
import re
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
from entry_ev_quantile_policy_backtest import (  # noqa: E402
    PolicyCandidate,
    policy_candidate_from_name,
    quantile_column,
)


BLOCK_TRUE = "1"
BLOCK_FALSE = "0"


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


def parse_floats(value: str) -> list[float]:
    return [float(part) for part in parse_csv(value)]


def safe_name(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z]+", "_", value).strip("_").lower()


def threshold_name(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return str(value).replace(".", "p").replace("-", "m")


def numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(np.nan, index=frame.index, dtype="float64")
    values = pd.to_numeric(frame[column], errors="coerce")
    return values.where(np.isfinite(values))


def selected_side(long_score: pd.Series, short_score: pd.Series) -> pd.Series:
    output = pd.Series("none", index=long_score.index, dtype="object")
    valid = long_score.notna() & short_score.notna()
    output.loc[valid & (long_score >= short_score)] = "long"
    output.loc[valid & (long_score < short_score)] = "short"
    return output


def candidate_pass_mask(
    frame: pd.DataFrame,
    *,
    candidate: PolicyCandidate,
    score_kind: str,
    long_column: str,
    short_column: str,
    long_holding_column: str,
    short_holding_column: str,
    min_valid_predicted_hold_minutes: float,
) -> tuple[pd.Series, pd.Series]:
    long_score = numeric(frame, long_column)
    short_score = numeric(frame, short_column)
    side = selected_side(long_score, short_score)
    selected_score = pd.Series(
        np.where(side.eq("long"), long_score, short_score),
        index=frame.index,
        dtype="float64",
    )
    side_gap = (long_score - short_score).abs()
    threshold = pd.Series(candidate.entry_threshold, index=frame.index, dtype="float64")
    threshold = threshold.where(
        ~side.eq("short"),
        candidate.entry_threshold + candidate.short_entry_threshold_offset,
    )
    mask = (
        side.ne("none")
        & selected_score.notna()
        & side_gap.notna()
        & selected_score.gt(threshold)
        & side_gap.ge(candidate.side_margin)
    )
    if candidate.score_quantile > 0:
        score_quantile = numeric(
            frame,
            quantile_column(score_kind, "selected_score", candidate.scope),
        )
        mask &= score_quantile.notna() & score_quantile.ge(candidate.score_quantile)
    if candidate.side_gap_quantile > 0:
        side_gap_quantile = numeric(
            frame,
            quantile_column(score_kind, "side_gap", candidate.scope),
        )
        mask &= side_gap_quantile.notna() & side_gap_quantile.ge(candidate.side_gap_quantile)
    if candidate.rank_quantile > 0:
        rank_quantile = numeric(
            frame,
            quantile_column(score_kind, "selected_entry_rank", candidate.scope),
        )
        mask &= rank_quantile.notna() & rank_quantile.ge(candidate.rank_quantile)
    if candidate.min_entry_rank > 0:
        raise ValueError("candidate min_entry_rank is not supported by this diagnostic")
    if np.isfinite(min_valid_predicted_hold_minutes):
        long_holding = numeric(frame, long_holding_column)
        short_holding = numeric(frame, short_holding_column)
        side_holding = pd.Series(
            np.where(side.eq("long"), long_holding, short_holding),
            index=frame.index,
            dtype="float64",
        )
        mask &= (
            side_holding.notna()
            & np.isfinite(side_holding)
            & side_holding.ge(min_valid_predicted_hold_minutes)
        )
    return mask.fillna(False).astype(bool), side


def add_direction_regime(frame: pd.DataFrame, side: pd.Series) -> pd.Series:
    if "combined_regime" not in frame.columns:
        raise ValueError("predictions must contain combined_regime")
    regime = (
        frame["combined_regime"]
        .fillna("missing")
        .astype(str)
        .replace({"": "missing", "nan": "missing", "None": "missing"})
    )
    return side.astype(str) + "/" + regime


def prior_context_active_table(
    delta_rows: pd.DataFrame,
    *,
    candidates: list[str],
    thresholds: list[float],
) -> dict[tuple[str, str, str, float], bool]:
    rows = delta_rows.copy()
    rows = rows[rows["candidate"].astype(str).isin(candidates)].copy()
    rows = rows[rows["delta_status"].eq("only_candidate")].copy()
    if rows.empty:
        return {}
    rows["month"] = rows["month"].astype(str).str.slice(0, 7)
    rows["month_period"] = pd.PeriodIndex(rows["month"], freq="M")
    if "direction_regime" not in rows.columns:
        rows["direction_regime"] = (
            rows["direction"].fillna("missing").astype(str)
            + "/"
            + rows["combined_regime"].fillna("missing").astype(str)
        )
    rows["candidate_adjusted_pnl"] = numeric(rows, "candidate_adjusted_pnl").fillna(0.0)
    first_month = rows["month_period"].min()
    last_month = rows["month_period"].max() + 1
    months = list(pd.period_range(first_month, last_month, freq="M"))
    active: dict[tuple[str, str, str, float], bool] = {}
    for candidate in candidates:
        candidate_rows = rows[rows["candidate"].astype(str).eq(candidate)]
        contexts = sorted(candidate_rows["direction_regime"].dropna().unique().tolist())
        for month_period in months:
            month = str(month_period)
            for context in contexts:
                prior = candidate_rows[
                    (candidate_rows["direction_regime"].eq(context))
                    & (candidate_rows["month_period"] < month_period)
                ]
                prior_pnl = float(prior["candidate_adjusted_pnl"].sum())
                prior_count = int(len(prior))
                prior_months = int(prior["month"].nunique())
                for threshold in thresholds:
                    active[(candidate, month, context, threshold)] = (
                        prior_count >= 1
                        and prior_months >= 1
                        and prior_pnl <= -threshold
                    )
    return active


def align_post_predictions(
    pre: pd.DataFrame,
    post: pd.DataFrame,
    required_columns: list[str],
) -> pd.DataFrame:
    post_index = post.set_index("decision_timestamp", drop=False)
    aligned = post_index[required_columns].reindex(pre["decision_timestamp"])
    return aligned.reset_index(drop=True)


def candidate_required_columns(
    *,
    candidate: PolicyCandidate,
    score_kind: str,
    long_column: str,
    short_column: str,
    long_holding_column: str,
    short_holding_column: str,
) -> list[str]:
    columns = [
        "decision_timestamp",
        "dataset_month",
        "combined_regime",
        long_column,
        short_column,
        long_holding_column,
        short_holding_column,
    ]
    if candidate.score_quantile > 0:
        columns.append(quantile_column(score_kind, "selected_score", candidate.scope))
    if candidate.side_gap_quantile > 0:
        columns.append(quantile_column(score_kind, "side_gap", candidate.scope))
    if candidate.rank_quantile > 0:
        columns.append(quantile_column(score_kind, "selected_entry_rank", candidate.scope))
    return list(dict.fromkeys(columns))


def add_prior_guard_columns(
    pre: pd.DataFrame,
    post: pd.DataFrame,
    *,
    family: str,
    candidates: list[PolicyCandidate],
    prior_active: dict[tuple[str, str, str, float], bool],
    thresholds: list[float],
    pre_score_kind: str,
    post_score_kind: str,
    pre_long_column: str,
    pre_short_column: str,
    post_long_column: str,
    post_short_column: str,
    long_holding_column: str,
    short_holding_column: str,
    min_valid_predicted_hold_minutes: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    output = pre.copy()
    summary_rows: list[dict[str, object]] = []
    for candidate in candidates:
        post_columns = candidate_required_columns(
            candidate=candidate,
            score_kind=post_score_kind,
            long_column=post_long_column,
            short_column=post_short_column,
            long_holding_column=long_holding_column,
            short_holding_column=short_holding_column,
        )
        post_aligned = align_post_predictions(pre, post, post_columns)
        pre_pass, pre_side = candidate_pass_mask(
            pre,
            candidate=candidate,
            score_kind=pre_score_kind,
            long_column=pre_long_column,
            short_column=pre_short_column,
            long_holding_column=long_holding_column,
            short_holding_column=short_holding_column,
            min_valid_predicted_hold_minutes=min_valid_predicted_hold_minutes,
        )
        post_pass, _post_side = candidate_pass_mask(
            post_aligned,
            candidate=candidate,
            score_kind=post_score_kind,
            long_column=post_long_column,
            short_column=post_short_column,
            long_holding_column=long_holding_column,
            short_holding_column=short_holding_column,
            min_valid_predicted_hold_minutes=min_valid_predicted_hold_minutes,
        )
        direction_regime = add_direction_regime(pre, pre_side)
        months = pre["dataset_month"].astype(str).str.slice(0, 7)
        newly_admitted = pre_pass & ~post_pass
        newly_admitted_short = newly_admitted & pre_side.eq("short")
        for threshold in thresholds:
            column = (
                "pred_prior_direction_regime_guard_"
                + safe_name(candidate.name)
                + "_loss"
                + threshold_name(threshold)
                + "_block"
            )
            active = pd.Series(False, index=pre.index, dtype="bool")
            for idx in pre.index[newly_admitted_short]:
                active.at[idx] = prior_active.get(
                    (
                        candidate.name,
                        str(months.at[idx]),
                        str(direction_regime.at[idx]),
                        threshold,
                    ),
                    False,
                )
            output[column] = np.where(active, BLOCK_TRUE, BLOCK_FALSE)
            summary_rows.append(
                {
                    "family": family,
                    "candidate": candidate.name,
                    "threshold": threshold,
                    "guard_column": column,
                    "pre_pass_rows": int(pre_pass.sum()),
                    "post_pass_rows": int(post_pass.sum()),
                    "newly_admitted_rows": int(newly_admitted.sum()),
                    "newly_admitted_short_rows": int(newly_admitted_short.sum()),
                    "blocked_rows": int(active.sum()),
                    "blocked_months": int(months[active].nunique()),
                    "blocked_direction_regimes": int(direction_regime[active].nunique()),
                }
            )
    return output, pd.DataFrame(summary_rows)


def run_generation(args: argparse.Namespace) -> Path:
    pre_predictions = parse_family_predictions(args.pre_family_predictions)
    post_predictions = parse_family_predictions(args.post_family_predictions)
    missing_post = sorted(set(pre_predictions) - set(post_predictions))
    if missing_post:
        raise ValueError(f"missing post predictions for families: {','.join(missing_post)}")
    candidate_names = parse_csv(args.candidates)
    candidates = [policy_candidate_from_name(name) for name in candidate_names]
    thresholds = parse_floats(args.prior_loss_thresholds)
    delta_rows = pd.read_csv(args.enriched_delta_rows)
    prior_active = prior_context_active_table(
        delta_rows,
        candidates=candidate_names,
        thresholds=thresholds,
    )
    run_dir = make_run_dir(args.output_dir, args.label)
    prediction_dir = run_dir / "enriched_predictions"
    prediction_dir.mkdir(parents=True, exist_ok=True)

    summaries: list[pd.DataFrame] = []
    output_paths: dict[str, Path] = {}
    for family, pre_path in pre_predictions.items():
        pre = pd.read_parquet(pre_path)
        post = pd.read_parquet(post_predictions[family])
        guarded, summary = add_prior_guard_columns(
            pre,
            post,
            family=family,
            candidates=candidates,
            prior_active=prior_active,
            thresholds=thresholds,
            pre_score_kind=args.pre_score_kind,
            post_score_kind=args.post_score_kind,
            pre_long_column=args.pre_long_column,
            pre_short_column=args.pre_short_column,
            post_long_column=args.post_long_column,
            post_short_column=args.post_short_column,
            long_holding_column=args.long_holding_column,
            short_holding_column=args.short_holding_column,
            min_valid_predicted_hold_minutes=args.min_valid_predicted_hold_minutes,
        )
        out_path = prediction_dir / f"{family}_predictions_prior_context_guard.parquet"
        guarded.to_parquet(out_path, index=False)
        output_paths[family] = out_path
        summaries.append(summary)

    summary = pd.concat(summaries, ignore_index=True) if summaries else pd.DataFrame()
    summary.to_csv(run_dir / "prior_context_guard_input_summary.csv", index=False)
    config = {
        "pre_family_predictions": pre_predictions,
        "post_family_predictions": post_predictions,
        "output_paths": output_paths,
        "enriched_delta_rows": args.enriched_delta_rows,
        "candidates": candidate_names,
        "prior_loss_thresholds": thresholds,
        "pre_score_kind": args.pre_score_kind,
        "post_score_kind": args.post_score_kind,
        "pre_long_column": args.pre_long_column,
        "pre_short_column": args.pre_short_column,
        "post_long_column": args.post_long_column,
        "post_short_column": args.post_short_column,
        "long_holding_column": args.long_holding_column,
        "short_holding_column": args.short_holding_column,
        "min_valid_predicted_hold_minutes": args.min_valid_predicted_hold_minutes,
    }
    (run_dir / "config.json").write_text(
        json.dumps(config, indent=2, default=local_json_default) + "\n",
        encoding="utf-8",
    )
    print("Prior context guard input summary:")
    if not summary.empty:
        print(summary.to_string(index=False))
    print(f"artifacts: {run_dir}")
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pre-family-predictions", action="append", required=True)
    parser.add_argument("--post-family-predictions", action="append", required=True)
    parser.add_argument("--enriched-delta-rows", type=Path, required=True)
    parser.add_argument("--candidates", required=True)
    parser.add_argument("--prior-loss-thresholds", default="20,40,60")
    parser.add_argument("--pre-score-kind", required=True)
    parser.add_argument("--post-score-kind", required=True)
    parser.add_argument("--pre-long-column", required=True)
    parser.add_argument("--pre-short-column", required=True)
    parser.add_argument("--post-long-column", required=True)
    parser.add_argument("--post-short-column", required=True)
    parser.add_argument("--long-holding-column", default="pred_mlp_long_exit_event_minutes")
    parser.add_argument("--short-holding-column", default="pred_mlp_short_exit_event_minutes")
    parser.add_argument("--min-valid-predicted-hold-minutes", type=float, default=30.0)
    parser.add_argument("--output-dir", type=Path, default=Path("data/reports/backtests"))
    parser.add_argument("--label", default="entry_ev_prior_context_guard_prediction_inputs")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    run_generation(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
