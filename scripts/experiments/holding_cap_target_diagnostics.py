#!/usr/bin/env python3
"""Build diagnostics for direct holding-cap target candidates."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from trade_data.backtest import json_default, make_run_dir  # noqa: E402


def parse_csv_paths(value: str) -> list[Path]:
    paths = [Path(part.strip()) for part in value.split(",") if part.strip()]
    if not paths:
        raise argparse.ArgumentTypeError("at least one path is required")
    return paths


def parse_csv_strings(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def expand_delta_paths(paths: list[Path]) -> list[Path]:
    expanded: list[Path] = []
    for path in paths:
        if path.is_file():
            expanded.append(path)
            continue
        direct = path / "trade_delta_rows.csv"
        if direct.exists():
            expanded.append(direct)
            continue
        if path.is_dir():
            children = [
                child / "trade_delta_rows.csv"
                for child in sorted(path.iterdir())
                if child.is_dir() and (child / "trade_delta_rows.csv").exists()
            ]
            if children:
                expanded.extend(children)
                continue
        expanded.append(direct)
    return expanded


def infer_case_label(path: Path) -> str:
    name = path.parent.name
    if "risk5" in name:
        return "risk5"
    if "risk0" in name:
        return "risk0"
    return name


def read_delta_rows(paths: list[Path]) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for path in expand_delta_paths(paths):
        if not path.exists():
            raise FileNotFoundError(f"trade delta rows not found: {path}")
        frame = pd.read_csv(path)
        if frame.empty:
            continue
        frame = frame.copy()
        frame["delta_source"] = str(path)
        frame["case_label"] = infer_case_label(path)
        frames.append(frame)
    if not frames:
        raise ValueError("no non-empty trade_delta_rows.csv files found")
    return pd.concat(frames, ignore_index=True)


def bucket_series(series: pd.Series, bins: list[float], labels: list[str]) -> pd.Series:
    return pd.cut(
        pd.to_numeric(series, errors="coerce"),
        bins=bins,
        labels=labels,
        include_lowest=True,
    ).astype("string").fillna("__missing__")


def add_derived_columns(frame: pd.DataFrame) -> pd.DataFrame:
    output = frame.copy()
    for column in [
        "base_adjusted_pnl",
        "candidate_adjusted_pnl",
        "pnl_delta",
        "base_holding_minutes",
        "candidate_holding_minutes",
        "pred_taken_ev",
        "pred_opposite_ev",
        "pred_taken_best_holding_minutes",
        "pred_taken_wait_regret",
        "pred_taken_entry_local_rank",
        "pred_taken_side_confidence",
        "pred_side_confidence_gap",
        "gate_trade_quality_taken",
    ]:
        if column in output.columns:
            output[column] = pd.to_numeric(output[column], errors="coerce")

    output["cap_delta_minutes"] = output["base_holding_minutes"] - output["candidate_holding_minutes"]
    output["cap_value"] = output["pnl_delta"]
    output["cap_beneficial"] = output["cap_value"] > 0.0
    output["cap_harmful"] = output["cap_value"] < 0.0
    output["pred_side_gap"] = output["pred_taken_ev"] - output["pred_opposite_ev"]
    output["entry_hour_bucket"] = bucket_series(
        output.get("entry_hour", pd.Series(np.nan, index=output.index)),
        [-0.1, 5, 9, 13, 17, 21, 24],
        ["00-05", "06-09", "10-13", "14-17", "18-21", "22-23"],
    )
    output["cap_delta_bucket"] = bucket_series(
        output["cap_delta_minutes"],
        [-float("inf"), 0, 30, 60, 120, 240, float("inf")],
        ["<=0", "0-30", "30-60", "60-120", "120-240", ">240"],
    )
    output["pred_side_gap_bucket"] = bucket_series(
        output["pred_side_gap"],
        [-float("inf"), 0, 5, 10, 20, 40, float("inf")],
        ["<=0", "0-5", "5-10", "10-20", "20-40", ">40"],
    )
    output["pred_holding_bucket"] = bucket_series(
        output["pred_taken_best_holding_minutes"],
        [-float("inf"), 60, 120, 240, 480, 720, float("inf")],
        ["<=60", "60-120", "120-240", "240-480", "480-720", ">720"],
    )
    return output


def summarize(frame: pd.DataFrame, group_columns: list[str]) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=group_columns)
    working = frame.copy()
    for column in group_columns:
        working[column] = working[column].astype("string").fillna("__missing__")
    summary = (
        working.groupby(group_columns, dropna=False, observed=True)
        .agg(
            support=("cap_value", "size"),
            cap_value_sum=("cap_value", "sum"),
            cap_value_mean=("cap_value", "mean"),
            cap_value_median=("cap_value", "median"),
            cap_value_min=("cap_value", "min"),
            cap_value_q10=("cap_value", lambda series: float(series.quantile(0.10))),
            cap_value_q90=("cap_value", lambda series: float(series.quantile(0.90))),
            beneficial_rate=("cap_beneficial", "mean"),
            harmful_rate=("cap_harmful", "mean"),
            cap_delta_minutes_mean=("cap_delta_minutes", "mean"),
            pred_taken_ev_mean=("pred_taken_ev", "mean"),
            pred_side_gap_mean=("pred_side_gap", "mean"),
            pred_side_confidence_gap_mean=("pred_side_confidence_gap", "mean"),
            gate_trade_quality_taken_mean=("gate_trade_quality_taken", "mean"),
        )
        .reset_index()
    )
    return summary.sort_values(
        ["cap_value_sum", "support"],
        ascending=[True, False],
    ).reset_index(drop=True)


def walkforward_profiles(frame: pd.DataFrame, group_columns: list[str], min_prior_support: int) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=["target_month", *group_columns])
    months = sorted(frame["month"].astype(str).unique())
    rows: list[pd.DataFrame] = []
    for month in months:
        prior = frame[frame["month"].astype(str) < month].copy()
        holdout = frame[frame["month"].astype(str).eq(month)].copy()
        if prior.empty or holdout.empty:
            continue
        prior_summary = summarize(prior, group_columns).rename(
            columns={
                "support": "prior_support",
                "cap_value_sum": "prior_cap_value_sum",
                "cap_value_mean": "prior_cap_value_mean",
                "beneficial_rate": "prior_beneficial_rate",
                "harmful_rate": "prior_harmful_rate",
            }
        )
        holdout_summary = summarize(holdout, group_columns).rename(
            columns={
                "support": "holdout_support",
                "cap_value_sum": "holdout_cap_value_sum",
                "cap_value_mean": "holdout_cap_value_mean",
                "beneficial_rate": "holdout_beneficial_rate",
                "harmful_rate": "holdout_harmful_rate",
            }
        )
        keep_prior = [
            *group_columns,
            "prior_support",
            "prior_cap_value_sum",
            "prior_cap_value_mean",
            "prior_beneficial_rate",
            "prior_harmful_rate",
        ]
        keep_holdout = [
            *group_columns,
            "holdout_support",
            "holdout_cap_value_sum",
            "holdout_cap_value_mean",
            "holdout_beneficial_rate",
            "holdout_harmful_rate",
        ]
        joined = prior_summary[keep_prior].merge(
            holdout_summary[keep_holdout],
            on=group_columns,
            how="inner",
        )
        joined = joined[joined["prior_support"] >= min_prior_support].copy()
        if joined.empty:
            continue
        joined["target_month"] = month
        joined["prior_positive_holdout_negative"] = (
            joined["prior_cap_value_mean"].gt(0.0) & joined["holdout_cap_value_mean"].lt(0.0)
        )
        joined["prior_negative_holdout_positive"] = (
            joined["prior_cap_value_mean"].lt(0.0) & joined["holdout_cap_value_mean"].gt(0.0)
        )
        joined["holdout_minus_prior_mean"] = (
            joined["holdout_cap_value_mean"] - joined["prior_cap_value_mean"]
        )
        rows.append(joined)
    if not rows:
        return pd.DataFrame(columns=["target_month", *group_columns])
    output = pd.concat(rows, ignore_index=True)
    return output.sort_values(
        ["prior_positive_holdout_negative", "holdout_cap_value_sum", "prior_support"],
        ascending=[False, True, False],
    ).reset_index(drop=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--delta-runs", type=parse_csv_paths, required=True)
    parser.add_argument("--focus-regime", default="range_low_vol")
    parser.add_argument("--focus-side", default="short")
    parser.add_argument("--min-prior-support", type=int, default=3)
    parser.add_argument("--output-dir", type=Path, default=Path("data/reports/backtests"))
    parser.add_argument("--label", default="holding_cap_target_diagnostics")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    run_dir = make_run_dir(args.output_dir, args.label)
    deltas = add_derived_columns(read_delta_rows(args.delta_runs))
    common = deltas[
        deltas["delta_status"].astype(str).eq("common")
        & deltas["direction"].astype(str).eq(args.focus_side)
        & deltas["combined_regime"].astype(str).eq(args.focus_regime)
        & deltas["cap_delta_minutes"].gt(0)
        & deltas["cap_value"].notna()
        & deltas["cap_value"].abs().gt(1e-9)
    ].copy()
    common.to_csv(run_dir / "direct_cap_target_examples.csv", index=False)

    group_sets = {
        "by_month": ["case_label", "month"],
        "by_month_session": ["case_label", "month", "session_regime"],
        "by_session": ["case_label", "session_regime"],
        "by_entry_hour_bucket": ["case_label", "entry_hour_bucket"],
        "by_pred_ev_bucket": ["case_label", "pred_taken_ev_bucket"],
        "by_side_gap_bucket": ["case_label", "pred_side_gap_bucket"],
        "by_pred_holding_bucket": ["case_label", "pred_holding_bucket"],
        "by_quality_bucket": ["case_label", "gate_trade_quality_taken_bucket"],
        "by_session_quality": ["case_label", "session_regime", "gate_trade_quality_taken_bucket"],
        "by_session_sidegap": ["case_label", "session_regime", "pred_side_gap_bucket"],
    }
    summaries: dict[str, pd.DataFrame] = {}
    for name, columns in group_sets.items():
        frame = summarize(common, columns)
        frame.to_csv(run_dir / f"{name}.csv", index=False)
        summaries[name] = frame

    wf_columns = ["case_label", "session_regime", "pred_side_gap_bucket"]
    wf = walkforward_profiles(common, wf_columns, args.min_prior_support)
    wf.to_csv(run_dir / "walkforward_prior_profiles.csv", index=False)

    metrics = {
        "mode": "holding_cap_target_diagnostics",
        "delta_runs": [str(path) for path in args.delta_runs],
        "expanded_delta_paths": [str(path) for path in expand_delta_paths(args.delta_runs)],
        "focus_side": args.focus_side,
        "focus_regime": args.focus_regime,
        "rows": {
            "all_delta_rows": int(len(deltas)),
            "direct_cap_target_examples": int(len(common)),
            "walkforward_profiles": int(len(wf)),
        },
        "direct_target": {
            "cap_value_sum": float(common["cap_value"].sum()) if len(common) else 0.0,
            "cap_value_mean": float(common["cap_value"].mean()) if len(common) else 0.0,
            "beneficial_rate": float(common["cap_beneficial"].mean()) if len(common) else 0.0,
            "harmful_rate": float(common["cap_harmful"].mean()) if len(common) else 0.0,
            "month_count": int(common["month"].astype(str).nunique()) if len(common) else 0,
        },
        "outputs": {
            "direct_cap_target_examples": str(run_dir / "direct_cap_target_examples.csv"),
            "walkforward_prior_profiles": str(run_dir / "walkforward_prior_profiles.csv"),
            **{name: str(run_dir / f"{name}.csv") for name in summaries},
        },
    }
    with (run_dir / "metrics.json").open("w", encoding="utf-8") as handle:
        json.dump(metrics, handle, ensure_ascii=False, indent=2, default=json_default)

    print(json.dumps(metrics, ensure_ascii=False, indent=2, default=json_default))
    print("artifacts:", run_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
