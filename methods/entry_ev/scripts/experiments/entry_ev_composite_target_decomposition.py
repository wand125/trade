#!/usr/bin/env python3
"""Decompose composite selector signals into modelable features and targets."""

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

from entry_ev_side_balance_downside_interaction import normalize_trades  # noqa: E402


MODEL_TIME_FEATURE_COLUMNS = [
    "prior_trade_count",
    "prior_month_count",
    "prior_downside_support_weight",
    "prior_downside_risk_score",
    "side_balance_signed_drift_for_trade",
    "side_balance_abs_signed_drift_for_trade",
    "side_balance_downside_interaction_score",
    "selected_side_overrepresented_feature",
    "selected_side_underrepresented_feature",
    "missing_prior_support_feature",
    "low_prior_support_feature",
    "prior_zero_feature",
    "feature_pressure_score",
    "support_gap_feature",
]

TARGET_COLUMNS = [
    "direction_side_inversion_target",
    "large_exit_regret_target",
    "low_exit_capture_target",
    "exit_capture_failure_target",
    "executable_ev_overestimate_target",
    "realized_loss_target",
    "composite_failure_target",
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


def read_trade_frames(paths: list[Path]) -> pd.DataFrame:
    frames = [pd.read_csv(path) for path in paths]
    if not frames:
        raise ValueError("at least one enriched trade CSV is required")
    return pd.concat(frames, ignore_index=True)


def numeric_series(frame: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=float)
    return pd.to_numeric(frame[column], errors="coerce").fillna(default).astype(float)


def bool_series(frame: pd.DataFrame, column: str, default: bool = False) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=bool)
    series = frame[column]
    if pd.api.types.is_bool_dtype(series):
        return series.fillna(default).astype(bool)
    if pd.api.types.is_numeric_dtype(series):
        return series.fillna(float(default)).astype(float).ne(0.0)
    normalized = series.astype(str).str.lower().str.strip()
    return normalized.isin({"true", "1", "yes", "y"})


def filter_values(frame: pd.DataFrame, column: str, values: list[str]) -> pd.DataFrame:
    if not values:
        return frame.copy()
    return frame[frame[column].astype(str).isin(values)].copy()


def feature_pressure_score(
    *,
    risk_high: pd.Series,
    interaction_high: pd.Series,
    risk_score: pd.Series,
    prior_zero: pd.Series,
) -> pd.Series:
    return (
        0.35 * risk_high.astype(float)
        + 0.30 * interaction_high.astype(float)
        + 0.20 * risk_score.clip(lower=0.0, upper=1.0).astype(float)
        + 0.15 * prior_zero.astype(float)
    ).astype(float)


def add_component_features_and_targets(
    frame: pd.DataFrame,
    *,
    risk_threshold: float,
    interaction_threshold: float,
    min_prior_support_weight: float,
    large_exit_regret_threshold: float,
    low_exit_capture_threshold: float,
    min_oracle_edge: float,
    ev_overestimate_threshold: float,
) -> pd.DataFrame:
    output = frame.copy()
    for column in [
        "prior_trade_count",
        "prior_month_count",
        "prior_downside_support_weight",
        "prior_downside_risk_score",
        "side_balance_downside_interaction_score",
        "side_balance_signed_drift_for_trade",
        "side_balance_abs_signed_drift_for_trade",
        "adjusted_pnl",
        "actual_taken_best_adjusted_pnl",
        "exit_regret",
        "pred_taken_ev",
        "ev_overestimate_vs_realized",
    ]:
        output[column] = numeric_series(output, column)
    for column in [
        "direction_error",
        "no_edge_entry",
        "side_balance_selected_side_overrepresented",
        "side_balance_selected_side_underrepresented",
    ]:
        output[column] = bool_series(output, column)

    prior_zero = output["prior_trade_count"].astype(float).le(0.0)
    missing_support = prior_zero | output["prior_downside_support_weight"].astype(float).le(0.0)
    low_support = output["prior_downside_support_weight"].astype(float) < min_prior_support_weight
    risk_high = output["prior_downside_risk_score"].astype(float) >= risk_threshold
    interaction_high = (
        output["side_balance_downside_interaction_score"].astype(float) >= interaction_threshold
    )
    pressure = feature_pressure_score(
        risk_high=risk_high,
        interaction_high=interaction_high,
        risk_score=output["prior_downside_risk_score"].astype(float),
        prior_zero=prior_zero,
    )

    oracle_edge = output["actual_taken_best_adjusted_pnl"].astype(float)
    realized = output["adjusted_pnl"].astype(float)
    positive_oracle = oracle_edge >= min_oracle_edge
    positive_realized = realized.clip(lower=0.0)
    capture_ratio = np.where(
        oracle_edge > 0.0,
        positive_realized / oracle_edge.replace(0.0, np.nan),
        np.nan,
    )
    capture_ratio = pd.Series(capture_ratio, index=output.index).fillna(0.0).clip(0.0, 1.0)
    low_exit_capture = positive_oracle & (capture_ratio <= low_exit_capture_threshold)
    large_exit_regret = output["exit_regret"].astype(float) >= large_exit_regret_threshold
    ev_overestimate = (
        output["ev_overestimate_vs_realized"].astype(float) >= ev_overestimate_threshold
    )
    direction_inversion = output["direction_error"].astype(bool)
    realized_loss = realized < 0.0

    output["prior_zero_feature"] = prior_zero
    output["missing_prior_support_feature"] = missing_support
    output["low_prior_support_feature"] = low_support
    output["support_gap_feature"] = 1.0 - output["prior_downside_support_weight"].clip(0.0, 1.0)
    output["risk_high_feature"] = risk_high
    output["interaction_high_feature"] = interaction_high
    output["feature_pressure_score"] = pressure
    output["selected_side_overrepresented_feature"] = output[
        "side_balance_selected_side_overrepresented"
    ]
    output["selected_side_underrepresented_feature"] = output[
        "side_balance_selected_side_underrepresented"
    ]
    output["same_side_oracle_edge"] = oracle_edge
    output["realized_executable_pnl"] = realized
    output["exit_capture_ratio"] = capture_ratio
    output["direction_side_inversion_target"] = direction_inversion
    output["large_exit_regret_target"] = large_exit_regret
    output["low_exit_capture_target"] = low_exit_capture
    output["exit_capture_failure_target"] = large_exit_regret | low_exit_capture
    output["executable_ev_overestimate_target"] = ev_overestimate
    output["realized_loss_target"] = realized_loss
    output["composite_failure_target"] = (
        direction_inversion | large_exit_regret | low_exit_capture | ev_overestimate | realized_loss
    )
    output["pressure_bucket"] = pd.cut(
        output["feature_pressure_score"].astype(float),
        bins=[-0.001, 0.15, 0.35, 0.60, float("inf")],
        labels=["low", "medium", "high", "extreme"],
    ).astype(str)
    output["support_bucket"] = np.select(
        [
            output["missing_prior_support_feature"].astype(bool),
            output["prior_downside_support_weight"].astype(float) < min_prior_support_weight,
            output["prior_downside_support_weight"].astype(float) < 0.50,
        ],
        ["missing", "low", "medium"],
        default="high",
    )
    return output


def summarize_group(group: pd.DataFrame) -> dict[str, Any]:
    pnl = group["adjusted_pnl"].astype(float)
    row: dict[str, Any] = {
        "trade_count": int(len(group)),
        "total_pnl": float(pnl.sum()),
        "avg_pnl": float(pnl.mean()) if len(group) else 0.0,
        "win_rate": float(pnl.gt(0.0).mean()) if len(group) else 0.0,
        "prior_support_mean": float(group["prior_downside_support_weight"].astype(float).mean()),
        "prior_zero_share": float(group["prior_zero_feature"].astype(bool).mean()),
        "missing_support_share": float(
            group["missing_prior_support_feature"].astype(bool).mean()
        ),
        "low_support_share": float(group["low_prior_support_feature"].astype(bool).mean()),
        "pressure_mean": float(group["feature_pressure_score"].astype(float).mean()),
        "exit_capture_ratio_mean": float(group["exit_capture_ratio"].astype(float).mean()),
        "ev_overestimate_mean": float(
            group["ev_overestimate_vs_realized"].astype(float).mean()
        ),
    }
    for column in TARGET_COLUMNS:
        row[f"{column}_rate"] = float(group[column].astype(bool).mean())
        row[f"{column}_loss_pnl"] = float(pnl.where(group[column].astype(bool), 0.0).sum())
    return row


def summarize_by_columns(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for keys, group in frame.groupby(columns, dropna=False):
        if not isinstance(keys, tuple):
            keys = (keys,)
        row = dict(zip(columns, keys, strict=True))
        row.update(summarize_group(group))
        rows.append(row)
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(
        columns + ["total_pnl"],
        ascending=[True] * len(columns) + [True],
    ).reset_index(drop=True)


def summarize_target_overlap(frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    working = frame.copy()
    working["target_overlap_key"] = working[TARGET_COLUMNS].apply(
        lambda row: "+".join(
            column.removesuffix("_target")
            for column, active in row.astype(bool).items()
            if active
        )
        or "none",
        axis=1,
    )
    for key, group in working.groupby("target_overlap_key", dropna=False):
        row = {"target_overlap_key": key}
        row.update(summarize_group(group))
        rows.append(row)
    return pd.DataFrame(rows).sort_values(
        ["trade_count", "total_pnl"],
        ascending=[False, True],
    ).reset_index(drop=True)


def build_diagnostics(args: argparse.Namespace) -> Path:
    trades = normalize_trades(read_trade_frames(args.trades))
    trades = filter_values(trades, "role", parse_csv(args.roles))
    trades = filter_values(trades, "candidate", parse_csv(args.candidates))
    if trades.empty:
        raise ValueError("no trades remain after filters")

    enriched = add_component_features_and_targets(
        trades,
        risk_threshold=args.risk_threshold,
        interaction_threshold=args.interaction_threshold,
        min_prior_support_weight=args.min_prior_support_weight,
        large_exit_regret_threshold=args.large_exit_regret_threshold,
        low_exit_capture_threshold=args.low_exit_capture_threshold,
        min_oracle_edge=args.min_oracle_edge,
        ev_overestimate_threshold=args.ev_overestimate_threshold,
    )
    candidate_summary = summarize_by_columns(enriched, ["candidate"])
    role_summary = summarize_by_columns(enriched, ["candidate", "role"])
    month_summary = summarize_by_columns(enriched, ["candidate", "role", "month"])
    feature_bucket_summary = summarize_by_columns(
        enriched,
        ["candidate", "support_bucket", "pressure_bucket"],
    )
    target_overlap = summarize_target_overlap(enriched)

    run_dir = make_run_dir(args.output_dir, args.label)
    selected_columns = [
        "candidate",
        "role",
        "month",
        "direction",
        "entry_decision_timestamp",
        "adjusted_pnl",
        "actual_taken_best_adjusted_pnl",
        "pred_taken_ev",
        "ev_overestimate_vs_realized",
        "exit_regret",
        "exit_capture_ratio",
        "support_bucket",
        "pressure_bucket",
        *MODEL_TIME_FEATURE_COLUMNS,
        *TARGET_COLUMNS,
    ]
    existing_selected = [column for column in selected_columns if column in enriched.columns]
    enriched[existing_selected].to_csv(run_dir / "component_trade_targets.csv", index=False)
    candidate_summary.to_csv(run_dir / "component_candidate_summary.csv", index=False)
    role_summary.to_csv(run_dir / "component_role_summary.csv", index=False)
    month_summary.to_csv(run_dir / "component_month_summary.csv", index=False)
    feature_bucket_summary.to_csv(run_dir / "component_feature_bucket_summary.csv", index=False)
    target_overlap.to_csv(run_dir / "component_target_overlap_summary.csv", index=False)

    config = {
        "trades": args.trades,
        "roles": parse_csv(args.roles),
        "candidates": parse_csv(args.candidates),
        "risk_threshold": args.risk_threshold,
        "interaction_threshold": args.interaction_threshold,
        "min_prior_support_weight": args.min_prior_support_weight,
        "large_exit_regret_threshold": args.large_exit_regret_threshold,
        "low_exit_capture_threshold": args.low_exit_capture_threshold,
        "min_oracle_edge": args.min_oracle_edge,
        "ev_overestimate_threshold": args.ev_overestimate_threshold,
        "model_time_feature_columns": MODEL_TIME_FEATURE_COLUMNS,
        "target_columns": TARGET_COLUMNS,
        "note": (
            "model_time_feature_columns use only prior/context or prediction-time values; "
            "target_columns use realized labels and are for training/evaluation only"
        ),
    }
    (run_dir / "config.json").write_text(
        json.dumps(config, indent=2, default=local_json_default),
        encoding="utf-8",
    )

    print("Composite component candidate summary:")
    print(
        candidate_summary[
            [
                "candidate",
                "trade_count",
                "total_pnl",
                "prior_zero_share",
                "missing_support_share",
                "pressure_mean",
                "direction_side_inversion_target_rate",
                "exit_capture_failure_target_rate",
                "executable_ev_overestimate_target_rate",
                "composite_failure_target_rate",
            ]
        ].to_string(index=False)
    )
    print("\nTarget overlap summary:")
    print(target_overlap.head(args.top_n).to_string(index=False))
    print(f"artifacts: {run_dir}")
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trades", type=Path, action="append", required=True)
    parser.add_argument("--roles", default="")
    parser.add_argument("--candidates", default="")
    parser.add_argument("--risk-threshold", type=float, default=0.20)
    parser.add_argument("--interaction-threshold", type=float, default=0.005)
    parser.add_argument("--min-prior-support-weight", type=float, default=0.10)
    parser.add_argument("--large-exit-regret-threshold", type=float, default=10.0)
    parser.add_argument("--low-exit-capture-threshold", type=float, default=0.50)
    parser.add_argument("--min-oracle-edge", type=float, default=5.0)
    parser.add_argument("--ev-overestimate-threshold", type=float, default=10.0)
    parser.add_argument("--top-n", type=int, default=30)
    parser.add_argument("--output-dir", type=Path, default=Path("data/reports/backtests"))
    parser.add_argument("--label", default="entry_ev_composite_target_decomposition")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    build_diagnostics(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
