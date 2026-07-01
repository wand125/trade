#!/usr/bin/env python3
"""Summarize candidate-row clustering into entry episodes."""

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
from entry_ev_prior_context_guard_prediction_inputs import candidate_pass_mask  # noqa: E402
from entry_ev_quantile_policy_backtest import (  # noqa: E402
    parse_policy_candidates,
    policy_candidate_from_name,
)


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
    return pd.to_datetime(frame["decision_timestamp"], utc=True).dt.strftime("%Y-%m")


def side_labels(side: pd.Series) -> pd.Series:
    return side.map({"long": "long", "short": "short"}).fillna("none")


def episode_rows(
    rows: pd.DataFrame,
    *,
    family: str,
    candidate: str,
    episode_gap_minutes: float,
) -> pd.DataFrame:
    output_rows: list[dict[str, object]] = []
    if rows.empty:
        return pd.DataFrame(
            columns=[
                "family",
                "candidate",
                "month",
                "side",
                "episode_id",
                "row_count",
                "start",
                "end",
                "duration_minutes",
            ]
        )
    ordered = rows.sort_values("decision_timestamp").copy()
    ordered["decision_timestamp"] = pd.to_datetime(
        ordered["decision_timestamp"],
        utc=True,
    )
    for (month, side), group in ordered.groupby(["month", "side"], dropna=False):
        ts = group["decision_timestamp"].reset_index(drop=True)
        episode_id = (ts.diff().dt.total_seconds().fillna(np.inf) > episode_gap_minutes * 60).cumsum()
        for local_id, episode in group.reset_index(drop=True).groupby(episode_id):
            start = pd.to_datetime(episode["decision_timestamp"].min(), utc=True)
            end = pd.to_datetime(episode["decision_timestamp"].max(), utc=True)
            output_rows.append(
                {
                    "family": family,
                    "candidate": candidate,
                    "month": month,
                    "side": side,
                    "episode_id": int(local_id),
                    "row_count": int(len(episode)),
                    "start": start,
                    "end": end,
                    "duration_minutes": float((end - start).total_seconds() / 60),
                }
            )
    return pd.DataFrame(output_rows)


def summarize_episodes(episodes: pd.DataFrame) -> pd.DataFrame:
    if episodes.empty:
        return pd.DataFrame()
    rows: list[dict[str, object]] = []
    for keys, group in episodes.groupby(["family", "candidate", "month"], dropna=False):
        family, candidate, month = keys
        rows.append(
            {
                "family": family,
                "candidate": candidate,
                "month": month,
                "candidate_rows": int(group["row_count"].sum()),
                "episode_count": int(len(group)),
                "max_episode_rows": int(group["row_count"].max()),
                "long_episodes": int(group["side"].eq("long").sum()),
                "short_episodes": int(group["side"].eq("short").sum()),
                "first_episode_start": group["start"].min(),
                "last_episode_end": group["end"].max(),
            }
        )
    return pd.DataFrame(rows).sort_values(["family", "candidate", "month"])


def summarize_family(episodes: pd.DataFrame) -> pd.DataFrame:
    if episodes.empty:
        return pd.DataFrame()
    rows: list[dict[str, object]] = []
    for keys, group in episodes.groupby(["family", "candidate"], dropna=False):
        family, candidate = keys
        active_months = group.groupby("month")["row_count"].sum()
        rows.append(
            {
                "family": family,
                "candidate": candidate,
                "candidate_rows": int(group["row_count"].sum()),
                "episode_count": int(len(group)),
                "active_months": int((active_months > 0).sum()),
                "max_episode_rows": int(group["row_count"].max()),
                "long_episodes": int(group["side"].eq("long").sum()),
                "short_episodes": int(group["side"].eq("short").sum()),
                "first_episode_start": group["start"].min(),
                "last_episode_end": group["end"].max(),
            }
        )
    return pd.DataFrame(rows).sort_values(["family", "candidate"])


def run_diagnostics(args: argparse.Namespace) -> Path:
    family_predictions = parse_family_predictions(args.family_predictions)
    candidate_names = parse_policy_candidates(args.policy_candidates)
    candidates = [policy_candidate_from_name(name) for name in candidate_names]
    episode_parts: list[pd.DataFrame] = []
    for family, prediction_path in family_predictions.items():
        predictions = pd.read_parquet(prediction_path)
        predictions["month"] = month_series(predictions)
        for candidate in candidates:
            mask, side = candidate_pass_mask(
                predictions,
                candidate=candidate,
                score_kind=args.score_kind,
                long_column=args.long_column,
                short_column=args.short_column,
                long_holding_column=args.long_holding_column,
                short_holding_column=args.short_holding_column,
                min_valid_predicted_hold_minutes=args.min_valid_predicted_hold_minutes,
            )
            rows = predictions.loc[mask, ["decision_timestamp", "month"]].copy()
            rows["side"] = side_labels(side.loc[mask])
            episode_parts.append(
                episode_rows(
                    rows,
                    family=family,
                    candidate=candidate.name,
                    episode_gap_minutes=args.episode_gap_minutes,
                )
            )
    episodes = (
        pd.concat(episode_parts, ignore_index=True)
        if episode_parts
        else pd.DataFrame()
    )
    monthly = summarize_episodes(episodes)
    family_summary = summarize_family(episodes)

    run_dir = make_run_dir(args.output_dir, args.label)
    episodes.to_csv(run_dir / "candidate_episode_rows.csv", index=False)
    monthly.to_csv(run_dir / "candidate_episode_monthly.csv", index=False)
    family_summary.to_csv(run_dir / "candidate_episode_summary.csv", index=False)
    config = {
        "family_predictions": family_predictions,
        "policy_candidates": candidate_names,
        "score_kind": args.score_kind,
        "long_column": args.long_column,
        "short_column": args.short_column,
        "long_holding_column": args.long_holding_column,
        "short_holding_column": args.short_holding_column,
        "min_valid_predicted_hold_minutes": args.min_valid_predicted_hold_minutes,
        "episode_gap_minutes": args.episode_gap_minutes,
    }
    (run_dir / "config.json").write_text(
        json.dumps(config, indent=2, default=local_json_default) + "\n",
        encoding="utf-8",
    )
    print("Candidate episode summary:")
    if not family_summary.empty:
        print(family_summary.to_string(index=False))
    print(f"artifacts: {run_dir}")
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--family-predictions", action="append", required=True)
    parser.add_argument("--policy-candidates", required=True)
    parser.add_argument("--score-kind", required=True)
    parser.add_argument("--long-column", required=True)
    parser.add_argument("--short-column", required=True)
    parser.add_argument("--long-holding-column", default="pred_mlp_long_exit_event_minutes")
    parser.add_argument("--short-holding-column", default="pred_mlp_short_exit_event_minutes")
    parser.add_argument("--min-valid-predicted-hold-minutes", type=float, default=30.0)
    parser.add_argument("--episode-gap-minutes", type=float, default=1.0)
    parser.add_argument("--output-dir", type=Path, default=Path("data/reports/backtests"))
    parser.add_argument("--label", default="entry_ev_candidate_episode_support")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    run_diagnostics(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
