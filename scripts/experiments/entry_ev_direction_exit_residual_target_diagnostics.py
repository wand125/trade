#!/usr/bin/env python3
"""Diagnose direction and exit-capture residual loss targets from enriched trades."""

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

from entry_ev_exit_shortening_target_diagnostics import (  # noqa: E402
    brier_score,
    bool_series,
    bucketize,
    chronological_calibration,
    numeric_series,
    rank_auc,
    target_summary,
    text_series,
)


DEFAULT_TARGETS = [
    "realized_loss_target",
    "direction_error_loss_target",
    "same_side_missed_loss_target",
    "low_capture_loss_target",
    "large_exit_regret_loss_target",
    "profit_barrier_miss_loss_target",
    "hold_too_long_loss_target",
    "direction_and_exit_loss_target",
    "same_side_large_regret_loss_target",
    "direction_or_exit_loss_target",
]

CALIBRATION_SPECS = {
    "side_context": ["direction", "combined_regime", "session_regime"],
    "confidence_exit": [
        "direction",
        "side_confidence_gap_bucket",
        "loss_first_prob_bucket",
        "time_exit_prob_bucket",
    ],
    "profit_exit": [
        "direction",
        "pred_profit_barrier_bucket",
        "loss_first_prob_bucket",
        "pred_exit_hold_bucket",
    ],
    "ev_exit": [
        "direction",
        "selected_ev_overestimate_bucket",
        "pred_fixed_slope_bucket",
        "pred_720_bucket",
    ],
    "context_confidence": [
        "direction",
        "combined_regime",
        "session_regime",
        "side_confidence_gap_bucket",
    ],
}


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


def read_frames(paths: list[Path]) -> pd.DataFrame:
    if not paths:
        raise ValueError("at least one --enriched-trades path is required")
    return pd.concat([pd.read_csv(path) for path in paths], ignore_index=True)


def normalize_trades(frame: pd.DataFrame, *, candidates: set[str], months: set[str]) -> pd.DataFrame:
    required = {
        "run_name",
        "role",
        "month",
        "candidate",
        "direction",
        "entry_decision_timestamp",
        "combined_regime",
        "session_regime",
        "adjusted_pnl",
        "direction_error",
        "actual_taken_best_adjusted_pnl",
        "actual_taken_profit_barrier_hit",
        "exit_regret",
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"enriched trade frame missing columns: {', '.join(missing)}")
    output = frame.copy()
    output["run_name"] = output["run_name"].astype(str)
    output["role"] = output["role"].astype(str)
    output["month"] = output["month"].astype(str).str.slice(0, 7)
    output["candidate"] = output["candidate"].astype(str)
    output["direction"] = output["direction"].astype(str).str.lower()
    output["entry_decision_timestamp"] = pd.to_datetime(
        output["entry_decision_timestamp"],
        utc=True,
    )
    output["combined_regime"] = text_series(output, "combined_regime")
    output["session_regime"] = text_series(output, "session_regime")
    if candidates:
        output = output[output["candidate"].isin(candidates)].copy()
    if months:
        output = output[output["month"].isin(months)].copy()
    if output.empty:
        raise ValueError("no trades remain after filters")
    return output.reset_index(drop=True)


def add_feature_buckets_and_targets(
    frame: pd.DataFrame,
    *,
    min_oracle_edge: float,
    low_capture_threshold: float,
    large_exit_regret_threshold: float,
    hold_too_long_minutes: float,
) -> pd.DataFrame:
    output = frame.copy()
    pnl = numeric_series(output, "adjusted_pnl")
    realized_positive = pnl.clip(lower=0.0)
    actual_edge = numeric_series(output, "actual_taken_best_adjusted_pnl", default=np.nan)
    exit_regret = numeric_series(output, "exit_regret", default=0.0)
    direction_error = bool_series(output, "direction_error")
    actual_profit_hit = numeric_series(output, "actual_taken_profit_barrier_hit", default=np.nan)
    oracle_gap = numeric_series(output, "oracle_holding_gap_minutes", default=np.nan)

    output["same_side_oracle_edge"] = actual_edge.ge(min_oracle_edge)
    output["exit_capture_ratio"] = np.where(
        actual_edge.gt(0.0),
        realized_positive / actual_edge.replace(0.0, np.nan),
        np.nan,
    )
    output["exit_capture_ratio"] = (
        pd.Series(output["exit_capture_ratio"], index=output.index).fillna(0.0).clip(0.0, 1.0)
    )
    output["low_exit_capture"] = output["same_side_oracle_edge"] & numeric_series(
        output,
        "exit_capture_ratio",
    ).le(low_capture_threshold)
    output["large_exit_regret"] = exit_regret.ge(large_exit_regret_threshold)
    output["profit_barrier_miss"] = actual_profit_hit.lt(0.5)
    output["hold_too_long"] = oracle_gap.le(-abs(hold_too_long_minutes)) & exit_regret.gt(0.0)

    realized_loss = pnl.lt(0.0)
    output["realized_loss_target"] = realized_loss
    output["direction_error_loss_target"] = realized_loss & direction_error
    output["same_side_missed_loss_target"] = realized_loss & output["same_side_oracle_edge"]
    output["low_capture_loss_target"] = realized_loss & output["low_exit_capture"]
    output["large_exit_regret_loss_target"] = realized_loss & output["large_exit_regret"]
    output["profit_barrier_miss_loss_target"] = realized_loss & output["profit_barrier_miss"]
    output["hold_too_long_loss_target"] = realized_loss & output["hold_too_long"]
    output["direction_and_exit_loss_target"] = (
        realized_loss
        & direction_error
        & (output["large_exit_regret"] | output["low_exit_capture"] | output["profit_barrier_miss"])
    )
    output["same_side_large_regret_loss_target"] = (
        realized_loss & output["same_side_oracle_edge"] & output["large_exit_regret"]
    )
    output["direction_or_exit_loss_target"] = (
        realized_loss
        & (
            direction_error
            | output["large_exit_regret"]
            | output["low_exit_capture"]
            | output["profit_barrier_miss"]
        )
    )

    pred_barrier = numeric_series(output, "pred_taken_profit_barrier_hit", default=np.nan)
    output["pred_profit_barrier_bucket"] = np.where(pred_barrier.ge(0.5), "pred_hit", "pred_miss")
    output.loc[pred_barrier.isna(), "pred_profit_barrier_bucket"] = "missing"
    output["side_confidence_gap_bucket"] = bucketize(
        numeric_series(output, "pred_side_confidence_gap", default=np.nan),
        bins=[-float("inf"), -0.05, 0.0, 0.10, 0.25, float("inf")],
        labels=["opposite_favored", "nonpositive", "weak", "medium", "strong"],
    )
    output["taken_side_confidence_bucket"] = bucketize(
        numeric_series(output, "pred_taken_side_confidence", default=np.nan),
        bins=[-0.001, 0.45, 0.50, 0.55, 0.65, 1.0],
        labels=["low", "weak", "neutral", "medium", "high"],
    )
    output["loss_first_prob_bucket"] = bucketize(
        numeric_series(output, "selected_loss_first_prob", default=np.nan),
        bins=[-0.001, 0.20, 0.40, 0.60, 0.80, 1.0],
        labels=["very_low", "low", "medium", "high", "very_high"],
    )
    output["time_exit_prob_bucket"] = bucketize(
        numeric_series(output, "selected_time_exit_prob", default=np.nan),
        bins=[-0.001, 0.20, 0.40, 0.60, 0.80, 1.0],
        labels=["very_low", "low", "medium", "high", "very_high"],
    )
    pred_mlp_hold = numeric_series(output, "selected_pred_mlp_exit_minutes", default=np.nan)
    pred_taken_hold = numeric_series(output, "pred_taken_best_holding_minutes", default=np.nan)
    output["pred_exit_hold_bucket"] = bucketize(
        pred_mlp_hold,
        bins=[-0.001, 60.0, 240.0, 720.0, 1440.0, float("inf")],
        labels=["lt60", "60_240", "240_720", "720_1440", "gt1440"],
    )
    output["pred_hold_gap_bucket"] = bucketize(
        pred_mlp_hold - pred_taken_hold,
        bins=[-float("inf"), -240.0, -60.0, 60.0, 240.0, float("inf")],
        labels=["mlp_much_shorter", "mlp_shorter", "aligned", "mlp_longer", "mlp_much_longer"],
    )
    output["selected_ev_overestimate_bucket"] = bucketize(
        numeric_series(output, "selected_ev_overestimate_risk", default=np.nan),
        bins=[-0.001, 0.25, 0.50, 0.75, 1.0],
        labels=["low", "medium", "high", "extreme"],
    )
    pred_fixed_60 = numeric_series(output, "selected_fixed_60m_pred_pnl", default=np.nan)
    pred_fixed_720 = numeric_series(output, "selected_fixed_720m_pred_pnl", default=np.nan)
    output["pred_fixed_slope_bucket"] = bucketize(
        pred_fixed_720 - pred_fixed_60,
        bins=[-float("inf"), -20.0, -5.0, 5.0, 20.0, float("inf")],
        labels=["strong_decay", "decay", "flat", "improve", "strong_improve"],
    )
    output["pred_720_bucket"] = bucketize(
        pred_fixed_720,
        bins=[-float("inf"), 0.0, 5.0, 15.0, 30.0, float("inf")],
        labels=["nonpositive", "low", "medium", "high", "extreme"],
    )
    return output


def target_metric_row(frame: pd.DataFrame, *, target: str, score_column: str | None = None) -> dict[str, Any]:
    target_values = bool_series(frame, target)
    pnl = numeric_series(frame, "adjusted_pnl")
    row: dict[str, Any] = {
        "row_count": int(len(frame)),
        "target_count": int(target_values.sum()),
        "target_rate": float(target_values.mean()) if len(frame) else 0.0,
        "total_pnl": float(pnl.sum()) if len(frame) else 0.0,
        "target_true_pnl": float(pnl.where(target_values, 0.0).sum()) if len(frame) else 0.0,
        "target_false_pnl": float(pnl.where(~target_values, 0.0).sum()) if len(frame) else 0.0,
        "target_true_avg_pnl": float(pnl[target_values].mean())
        if bool(target_values.any())
        else float("nan"),
        "target_false_avg_pnl": float(pnl[~target_values].mean())
        if bool((~target_values).any())
        else float("nan"),
    }
    if score_column is not None and score_column in frame.columns:
        scores = numeric_series(frame, score_column, default=np.nan)
        valid = scores.notna() & np.isfinite(scores)
        row.update(
            {
                "predicted_count": int(valid.sum()),
                "predicted_mean": float(scores[valid].mean()) if bool(valid.any()) else float("nan"),
                "auc": rank_auc(target_values[valid], scores[valid]),
                "brier": brier_score(target_values[valid], scores[valid]),
            }
        )
    return row


def score_column_summary(frame: pd.DataFrame, *, targets: list[str]) -> pd.DataFrame:
    score_columns = [
        "pred_side_confidence_gap",
        "selected_loss_first_prob",
        "selected_time_exit_prob",
        "selected_ev_overestimate_risk",
        "pred_taken_profit_barrier_hit",
    ]
    rows: list[dict[str, Any]] = []
    for target in targets:
        for score_column in score_columns:
            if score_column not in frame.columns:
                continue
            row = {"target": target, "score_column": score_column}
            row.update(target_metric_row(frame, target=target, score_column=score_column))
            rows.append(row)
    return pd.DataFrame(rows).sort_values(
        ["auc", "target_true_pnl"],
        ascending=[False, True],
    ).reset_index(drop=True)


def worst_examples(frame: pd.DataFrame, *, targets: list[str], top_n: int) -> pd.DataFrame:
    output = frame.copy()
    output["target_combo"] = output[targets].apply(
        lambda row: "+".join([target for target, value in row.items() if bool(value)]) or "none",
        axis=1,
    )
    columns = [
        "run_name",
        "role",
        "family",
        "candidate",
        "month",
        "direction",
        "entry_decision_timestamp",
        "adjusted_pnl",
        "exit_reason",
        "holding_minutes",
        "actual_taken_best_adjusted_pnl",
        "actual_taken_best_holding_minutes",
        "exit_regret",
        "oracle_holding_gap_minutes",
        "direction_error",
        "actual_taken_profit_barrier_hit",
        "pred_taken_profit_barrier_hit",
        "pred_side_confidence_gap",
        "selected_loss_first_prob",
        "selected_time_exit_prob",
        "combined_regime",
        "session_regime",
        "target_combo",
    ]
    existing = [column for column in columns if column in output.columns]
    return output.sort_values("adjusted_pnl").loc[:, existing].head(top_n).reset_index(drop=True)


def build_diagnostics(args: argparse.Namespace) -> Path:
    targets = parse_csv(args.targets) or DEFAULT_TARGETS
    selected_specs = parse_csv(args.calibration_specs)
    specs = {
        name: columns
        for name, columns in CALIBRATION_SPECS.items()
        if not selected_specs or name in selected_specs
    }
    if not specs:
        raise ValueError("--calibration-specs did not match any known spec")
    frame = normalize_trades(
        read_frames(args.enriched_trades),
        candidates=set(parse_csv(args.candidates)),
        months=set(parse_csv(args.months)),
    )
    frame = add_feature_buckets_and_targets(
        frame,
        min_oracle_edge=args.min_oracle_edge,
        low_capture_threshold=args.low_capture_threshold,
        large_exit_regret_threshold=args.large_exit_regret_threshold,
        hold_too_long_minutes=args.hold_too_long_minutes,
    )
    missing_targets = [target for target in targets if target not in frame.columns]
    if missing_targets:
        raise ValueError(f"unknown targets: {', '.join(missing_targets)}")

    overall = target_summary(frame, targets=targets, groups=[])
    candidate = target_summary(frame, targets=targets, groups=["run_name", "role", "candidate"])
    context = target_summary(
        frame,
        targets=targets,
        groups=["run_name", "role", "candidate", "direction", "combined_regime", "session_regime"],
    )
    score_summary = score_column_summary(frame, targets=targets)
    calibration_predictions, calibration_metrics, calibration_summary = chronological_calibration(
        frame,
        targets=targets,
        specs=specs,
        prior_strength=args.prior_strength,
        min_group_support=args.min_group_support,
    )
    worst = worst_examples(frame, targets=targets, top_n=args.top_n)

    run_dir = make_run_dir(args.output_dir, args.label)
    frame.to_csv(run_dir / "direction_exit_residual_targets.csv", index=False)
    overall.to_csv(run_dir / "direction_exit_target_summary.csv", index=False)
    candidate.to_csv(run_dir / "candidate_direction_exit_target_summary.csv", index=False)
    context.to_csv(run_dir / "context_direction_exit_target_summary.csv", index=False)
    score_summary.to_csv(run_dir / "score_direction_exit_target_summary.csv", index=False)
    calibration_predictions.to_csv(
        run_dir / "direction_exit_chronological_predictions.csv",
        index=False,
    )
    calibration_metrics.to_csv(
        run_dir / "direction_exit_chronological_metrics.csv",
        index=False,
    )
    calibration_summary.to_csv(
        run_dir / "direction_exit_chronological_summary.csv",
        index=False,
    )
    worst.to_csv(run_dir / "worst_direction_exit_examples.csv", index=False)
    config = {
        "enriched_trades": args.enriched_trades,
        "targets": targets,
        "calibration_specs": specs,
        "candidates": args.candidates,
        "months": args.months,
        "min_oracle_edge": args.min_oracle_edge,
        "low_capture_threshold": args.low_capture_threshold,
        "large_exit_regret_threshold": args.large_exit_regret_threshold,
        "hold_too_long_minutes": args.hold_too_long_minutes,
        "prior_strength": args.prior_strength,
        "min_group_support": args.min_group_support,
        "note": "chronological calibration uses only rows with month earlier than the fold month; group columns are decision-time features",
    }
    (run_dir / "config.json").write_text(
        json.dumps(config, indent=2, default=local_json_default),
        encoding="utf-8",
    )

    print("Direction/exit residual target summary:")
    print(overall.to_string(index=False))
    print("\nScore summary:")
    print(score_summary.head(args.top_n).to_string(index=False))
    print("\nChronological calibration summary:")
    print(calibration_summary.head(args.top_n).to_string(index=False))
    print(f"artifacts: {run_dir}")
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--enriched-trades", type=Path, action="append", required=True)
    parser.add_argument("--targets", default=",".join(DEFAULT_TARGETS))
    parser.add_argument("--calibration-specs", default="")
    parser.add_argument("--candidates", default="")
    parser.add_argument("--months", default="")
    parser.add_argument("--min-oracle-edge", type=float, default=5.0)
    parser.add_argument("--low-capture-threshold", type=float, default=0.25)
    parser.add_argument("--large-exit-regret-threshold", type=float, default=20.0)
    parser.add_argument("--hold-too-long-minutes", type=float, default=30.0)
    parser.add_argument("--prior-strength", type=float, default=5.0)
    parser.add_argument("--min-group-support", type=int, default=3)
    parser.add_argument("--top-n", type=int, default=20)
    parser.add_argument("--output-dir", type=Path, default=Path("data/reports/backtests"))
    parser.add_argument("--label", default="entry_ev_direction_exit_residual_target_diagnostics")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    build_diagnostics(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
