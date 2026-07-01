#!/usr/bin/env python3
"""Build narrow exit-shortening residual targets from selected trade diagnostics."""

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


DEFAULT_TARGETS = [
    "hold_too_long_loss_target",
    "exit_shortening_residual_target",
    "hold_prediction_too_long_loss_target",
    "same_side_missed_loss_target",
    "low_capture_loss_target",
    "late_exit_regret_loss_target",
    "forced_exit_loss_target",
    "profit_barrier_miss_loss_target",
    "large_exit_shortening_loss_target",
]

CALIBRATION_SPECS = {
    "side_context": ["direction", "combined_regime", "session_regime"],
    "exit_plan": [
        "direction",
        "pred_exit_hold_bucket",
        "pred_hold_gap_bucket",
        "time_exit_prob_bucket",
    ],
    "exit_risk": [
        "direction",
        "loss_first_prob_bucket",
        "pred_profit_barrier_bucket",
        "pred_fixed_slope_bucket",
    ],
    "direction_exit": [
        "direction",
        "selected_direction_risk_bucket",
        "pred_exit_hold_bucket",
        "session_regime",
    ],
    "ev_exit": [
        "direction",
        "selected_ev_overestimate_bucket",
        "pred_fixed_slope_bucket",
        "pred_720_bucket",
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
        raise ValueError("at least one --residual-trades path is required")
    frames = [pd.read_csv(path) for path in paths]
    return pd.concat(frames, ignore_index=True)


def numeric_series(frame: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=float)
    values = pd.to_numeric(frame[column], errors="coerce")
    return values.where(np.isfinite(values), default).fillna(default).astype(float)


def bool_series(frame: pd.DataFrame, column: str, default: bool = False) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=bool)
    values = frame[column]
    if pd.api.types.is_bool_dtype(values):
        return values.fillna(default).astype(bool)
    if pd.api.types.is_numeric_dtype(values):
        return values.fillna(float(default)).astype(float).ne(0.0)
    normalized = values.astype(str).str.lower().str.strip()
    return normalized.isin({"true", "1", "yes", "y"})


def text_series(frame: pd.DataFrame, column: str, default: str = "missing") -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index)
    return (
        frame[column]
        .fillna(default)
        .astype(str)
        .str.strip()
        .replace({"": default, "nan": default, "None": default})
    )


def normalize_trades(frame: pd.DataFrame, *, candidates: set[str], months: set[str]) -> pd.DataFrame:
    required = {
        "run_name",
        "month",
        "candidate",
        "direction",
        "entry_decision_timestamp",
        "combined_regime",
        "session_regime",
        "adjusted_pnl",
        "holding_minutes",
        "actual_taken_best_adjusted_pnl",
        "actual_taken_best_holding_minutes",
        "exit_regret",
        "oracle_holding_gap_minutes",
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"residual trade frame missing columns: {', '.join(missing)}")
    output = frame.copy()
    output["run_name"] = output["run_name"].astype(str)
    output["role"] = text_series(output, "role", default="missing")
    output["month"] = output["month"].astype(str).str.slice(0, 7)
    output["candidate"] = output["candidate"].astype(str)
    output["direction"] = output["direction"].astype(str).str.lower()
    output["entry_decision_timestamp"] = pd.to_datetime(
        output["entry_decision_timestamp"],
        utc=True,
    )
    for column in ["combined_regime", "session_regime"]:
        output[column] = text_series(output, column)
    if candidates:
        output = output[output["candidate"].isin(candidates)].copy()
    if months:
        output = output[output["month"].isin(months)].copy()
    if output.empty:
        raise ValueError("no trades remain after filters")
    return output.reset_index(drop=True)


def bucketize(
    values: pd.Series,
    *,
    bins: list[float],
    labels: list[str],
    missing: str = "missing",
) -> pd.Series:
    numeric = pd.to_numeric(values, errors="coerce")
    bucket = pd.cut(numeric, bins=bins, labels=labels, include_lowest=True)
    return bucket.astype(str).replace({"nan": missing})


def add_exit_features_and_targets(
    frame: pd.DataFrame,
    *,
    large_loss_threshold: float,
    min_oracle_edge: float,
    low_capture_threshold: float,
    large_exit_regret_threshold: float,
    hold_too_long_minutes: float,
    pred_hold_too_long_minutes: float,
) -> pd.DataFrame:
    output = frame.copy()
    pnl = numeric_series(output, "adjusted_pnl")
    oracle_edge = numeric_series(output, "actual_taken_best_adjusted_pnl", default=np.nan)
    actual_hold = numeric_series(output, "actual_taken_best_holding_minutes", default=np.nan)
    holding = numeric_series(output, "holding_minutes", default=np.nan)
    exit_regret = numeric_series(output, "exit_regret", default=0.0)
    oracle_gap = numeric_series(output, "oracle_holding_gap_minutes", default=np.nan)
    pred_mlp_hold = numeric_series(output, "selected_pred_mlp_exit_minutes", default=np.nan)
    pred_taken_hold = numeric_series(output, "pred_taken_best_holding_minutes", default=np.nan)
    pred_hold_gap = pred_mlp_hold - pred_taken_hold
    realized_positive = pnl.clip(lower=0.0)
    output["exit_capture_ratio"] = np.where(
        oracle_edge.gt(0.0),
        realized_positive / oracle_edge.replace(0.0, np.nan),
        np.nan,
    )
    output["exit_capture_ratio"] = (
        pd.Series(output["exit_capture_ratio"], index=output.index).fillna(0.0).clip(0.0, 1.0)
    )
    output["same_side_oracle_edge"] = oracle_edge.ge(min_oracle_edge)
    output["selected_pred_hold_gap_minutes"] = pred_hold_gap
    output["selected_actual_hold_gap_minutes"] = holding - actual_hold
    output["selected_fixed_slope_60_720"] = (
        numeric_series(output, "selected_fixed_720m_pred_pnl", default=np.nan)
        - numeric_series(output, "selected_fixed_60m_pred_pnl", default=np.nan)
    )
    output["selected_ev_overestimate_bucket"] = bucketize(
        numeric_series(output, "selected_ev_overestimate_risk", default=np.nan),
        bins=[-0.001, 0.25, 0.50, 0.75, 1.0],
        labels=["low", "medium", "high", "extreme"],
    )
    output["selected_replacement_quality_bucket"] = bucketize(
        numeric_series(output, "selected_replacement_quality", default=np.nan),
        bins=[-0.001, 0.25, 0.50, 0.75, 1.0],
        labels=["low", "medium", "high", "very_high"],
    )
    output["pred_exit_hold_bucket"] = bucketize(
        pred_mlp_hold,
        bins=[-0.001, 60.0, 240.0, 720.0, 1440.0, float("inf")],
        labels=["lt60", "60_240", "240_720", "720_1440", "gt1440"],
    )
    output["pred_taken_hold_bucket"] = bucketize(
        pred_taken_hold,
        bins=[-0.001, 60.0, 240.0, 720.0, 1440.0, float("inf")],
        labels=["lt60", "60_240", "240_720", "720_1440", "gt1440"],
    )
    output["pred_hold_gap_bucket"] = bucketize(
        pred_hold_gap,
        bins=[-float("inf"), -240.0, -60.0, 60.0, 240.0, float("inf")],
        labels=["mlp_much_shorter", "mlp_shorter", "aligned", "mlp_longer", "mlp_much_longer"],
    )
    output["time_exit_prob_bucket"] = bucketize(
        numeric_series(output, "selected_time_exit_prob", default=np.nan),
        bins=[-0.001, 0.20, 0.40, 0.60, 0.80, 1.0],
        labels=["very_low", "low", "medium", "high", "very_high"],
    )
    output["loss_first_prob_bucket"] = bucketize(
        numeric_series(output, "selected_loss_first_prob", default=np.nan),
        bins=[-0.001, 0.20, 0.40, 0.60, 0.80, 1.0],
        labels=["very_low", "low", "medium", "high", "very_high"],
    )
    output["pred_fixed_slope_bucket"] = bucketize(
        output["selected_fixed_slope_60_720"],
        bins=[-float("inf"), -20.0, -5.0, 5.0, 20.0, float("inf")],
        labels=["strong_decay", "decay", "flat", "improve", "strong_improve"],
    )
    output["pred_720_bucket"] = bucketize(
        numeric_series(output, "selected_fixed_720m_pred_pnl", default=np.nan),
        bins=[-float("inf"), 0.0, 5.0, 15.0, 30.0, float("inf")],
        labels=["nonpositive", "low", "medium", "high", "extreme"],
    )
    predicted_barrier = numeric_series(output, "pred_taken_profit_barrier_hit", default=np.nan)
    output["pred_profit_barrier_bucket"] = np.where(
        predicted_barrier.ge(0.5),
        "pred_hit",
        "pred_miss",
    )
    output.loc[predicted_barrier.isna(), "pred_profit_barrier_bucket"] = "missing"

    realized_loss = pnl.lt(0.0)
    hold_too_long = oracle_gap.le(-abs(hold_too_long_minutes)) & exit_regret.gt(0.0)
    pred_hold_too_long = (
        (pred_mlp_hold - actual_hold).ge(abs(pred_hold_too_long_minutes))
        & exit_regret.gt(0.0)
    )
    output["hold_too_long_loss_target"] = hold_too_long & realized_loss
    output["exit_shortening_residual_target"] = (
        output["hold_too_long_loss_target"]
        & oracle_edge.ge(min_oracle_edge)
        & exit_regret.ge(large_exit_regret_threshold)
    )
    output["hold_prediction_too_long_loss_target"] = pred_hold_too_long & realized_loss
    output["same_side_missed_loss_target"] = output["same_side_oracle_edge"] & realized_loss
    output["low_capture_loss_target"] = (
        output["same_side_missed_loss_target"]
        & numeric_series(output, "exit_capture_ratio").le(low_capture_threshold)
    )
    output["late_exit_regret_loss_target"] = (
        exit_regret.ge(large_exit_regret_threshold) & realized_loss
    )
    output["forced_exit_loss_target"] = bool_series(output, "is_forced_exit") & realized_loss
    output["profit_barrier_miss_loss_target"] = (
        numeric_series(output, "actual_taken_profit_barrier_hit", default=0.0).lt(0.5)
        & realized_loss
    )
    output["large_exit_shortening_loss_target"] = (
        pnl.le(large_loss_threshold) & output["exit_shortening_residual_target"]
    )
    return output


def rank_auc(y_true: pd.Series, y_score: pd.Series) -> float:
    target = y_true.astype(bool).to_numpy()
    scores = y_score.astype(float).to_numpy()
    valid = np.isfinite(scores)
    target = target[valid]
    scores = scores[valid]
    positives = int(target.sum())
    negatives = int((~target).sum())
    if positives == 0 or negatives == 0:
        return float("nan")
    ranks = pd.Series(scores).rank(method="average").to_numpy()
    rank_sum_positive = float(ranks[target].sum())
    return float((rank_sum_positive - positives * (positives + 1) / 2) / (positives * negatives))


def brier_score(y_true: pd.Series, y_score: pd.Series) -> float:
    target = y_true.astype(float)
    scores = y_score.astype(float)
    valid = scores.notna() & np.isfinite(scores)
    if not bool(valid.any()):
        return float("nan")
    return float(((scores[valid] - target[valid]) ** 2).mean())


def metric_row(frame: pd.DataFrame, *, target: str, score_column: str | None = None) -> dict[str, Any]:
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


def target_summary(frame: pd.DataFrame, *, targets: list[str], groups: list[str]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    grouped = [((), frame)] if not groups else frame.groupby(groups, dropna=False)
    for target in targets:
        for keys, group in grouped:
            if groups and not isinstance(keys, tuple):
                keys = (keys,)
            row = {"target": target}
            if groups:
                row.update(dict(zip(groups, keys, strict=True)))
            row.update(metric_row(group, target=target))
            rows.append(row)
    return pd.DataFrame(rows).sort_values(
        [*groups, "target_true_pnl", "target_rate"] if groups else ["target_true_pnl", "target_rate"],
        ascending=[True] * len(groups) + [True, False] if groups else [True, False],
    ).reset_index(drop=True)


def fit_bucket_rates(
    train: pd.DataFrame,
    *,
    target: str,
    group_columns: list[str],
    prior_strength: float,
    min_group_support: int,
) -> tuple[float, dict[tuple[str, ...], tuple[int, float]]]:
    if train.empty:
        return float("nan"), {}
    target_values = bool_series(train, target)
    global_rate = float(target_values.mean())
    rates: dict[tuple[str, ...], tuple[int, float]] = {}
    for keys, group in train.groupby(group_columns, dropna=False):
        if not isinstance(keys, tuple):
            keys = (keys,)
        count = int(len(group))
        target_sum = int(bool_series(group, target).sum())
        if count >= min_group_support:
            rate = (target_sum + prior_strength * global_rate) / (count + prior_strength)
            rates[tuple(str(key) for key in keys)] = (count, float(rate))
    return global_rate, rates


def predict_bucket_rates(
    test: pd.DataFrame,
    *,
    group_columns: list[str],
    global_rate: float,
    rates: dict[tuple[str, ...], tuple[int, float]],
) -> pd.DataFrame:
    output = test.copy()
    predictions: list[float] = []
    supports: list[int] = []
    sources: list[str] = []
    for _, row in output.iterrows():
        if not np.isfinite(global_rate):
            predictions.append(float("nan"))
            supports.append(0)
            sources.append("no_prior")
            continue
        key = tuple(str(row[column]) for column in group_columns)
        if key in rates:
            support, rate = rates[key]
            predictions.append(rate)
            supports.append(support)
            sources.append("bucket")
        else:
            predictions.append(global_rate)
            supports.append(0)
            sources.append("global")
    output["predicted_target_rate"] = predictions
    output["prediction_support"] = supports
    output["prediction_source"] = sources
    return output


def chronological_calibration(
    frame: pd.DataFrame,
    *,
    targets: list[str],
    specs: dict[str, list[str]],
    prior_strength: float,
    min_group_support: int,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    prediction_frames: list[pd.DataFrame] = []
    metric_rows: list[dict[str, Any]] = []
    month_values = frame["month"].astype(str)
    periods = pd.PeriodIndex(month_values, freq="M")
    for spec_name, group_columns in specs.items():
        missing = [column for column in group_columns if column not in frame.columns]
        if missing:
            raise ValueError(f"calibration spec {spec_name} missing columns: {', '.join(missing)}")
        for target in targets:
            for month in sorted(month_values.unique()):
                target_period = pd.Period(month, freq="M")
                train = frame[periods < target_period].copy()
                test = frame[month_values.eq(month)].copy()
                global_rate, rates = fit_bucket_rates(
                    train,
                    target=target,
                    group_columns=group_columns,
                    prior_strength=prior_strength,
                    min_group_support=min_group_support,
                )
                predicted = predict_bucket_rates(
                    test,
                    group_columns=group_columns,
                    global_rate=global_rate,
                    rates=rates,
                )
                predicted["calibration_spec"] = spec_name
                predicted["target"] = target
                predicted["fold"] = month
                prediction_frames.append(predicted)
                row = {
                    "calibration_spec": spec_name,
                    "target": target,
                    "fold": month,
                    "train_rows": int(len(train)),
                    "train_months": int(train["month"].nunique()) if len(train) else 0,
                    "bucket_count": int(len(rates)),
                }
                row.update(
                    metric_row(
                        predicted,
                        target=target,
                        score_column="predicted_target_rate",
                    )
                )
                row["bucket_prediction_share"] = float(
                    predicted["prediction_source"].eq("bucket").mean()
                )
                row["global_prediction_share"] = float(
                    predicted["prediction_source"].eq("global").mean()
                )
                row["no_prior_prediction_share"] = float(
                    predicted["prediction_source"].eq("no_prior").mean()
                )
                metric_rows.append(row)
    predictions = (
        pd.concat(prediction_frames, ignore_index=True)
        if prediction_frames
        else pd.DataFrame()
    )
    metrics = pd.DataFrame(metric_rows)
    summary_rows: list[dict[str, Any]] = []
    if not metrics.empty:
        for (spec_name, target), group in metrics.groupby(["calibration_spec", "target"]):
            pred_slice = predictions[
                predictions["calibration_spec"].eq(spec_name) & predictions["target"].eq(target)
            ]
            valid_pred = numeric_series(pred_slice, "predicted_target_rate", default=np.nan)
            valid = valid_pred.notna() & np.isfinite(valid_pred)
            brier_valid = group["brier"].notna() & np.isfinite(group["brier"].astype(float))
            brier_weight = group.loc[brier_valid, "predicted_count"].astype(float)
            weighted_brier = (
                float(np.average(group.loc[brier_valid, "brier"].astype(float), weights=brier_weight))
                if float(brier_weight.sum()) > 0.0
                else float("nan")
            )
            summary_rows.append(
                {
                    "calibration_spec": spec_name,
                    "target": target,
                    "fold_count": int(len(group)),
                    "row_count": int(group["row_count"].sum()),
                    "target_count": int(group["target_count"].sum()),
                    "target_rate": float(
                        group["target_count"].sum() / max(group["row_count"].sum(), 1)
                    ),
                    "target_true_pnl": float(group["target_true_pnl"].sum()),
                    "target_false_pnl": float(group["target_false_pnl"].sum()),
                    "predicted_count": int(group["predicted_count"].sum()),
                    "predicted_mean": float(valid_pred[valid].mean()) if bool(valid.any()) else float("nan"),
                    "mean_auc": float(group["auc"].dropna().mean())
                    if bool(group["auc"].notna().any())
                    else float("nan"),
                    "pooled_auc": rank_auc(
                        bool_series(pred_slice[valid], target),
                        valid_pred[valid],
                    )
                    if bool(valid.any())
                    else float("nan"),
                    "mean_brier": weighted_brier,
                    "bucket_prediction_share": float(
                        pred_slice["prediction_source"].eq("bucket").mean()
                    ),
                    "global_prediction_share": float(
                        pred_slice["prediction_source"].eq("global").mean()
                    ),
                    "no_prior_prediction_share": float(
                        pred_slice["prediction_source"].eq("no_prior").mean()
                    ),
                }
            )
    summary = (
        pd.DataFrame(summary_rows).sort_values(
            ["pooled_auc", "target_true_pnl"],
            ascending=[False, True],
        ).reset_index(drop=True)
        if summary_rows
        else pd.DataFrame()
    )
    return predictions, metrics, summary


def worst_examples(frame: pd.DataFrame, *, targets: list[str], top_n: int) -> pd.DataFrame:
    columns = [
        "run_name",
        "candidate",
        "month",
        "direction",
        "entry_decision_timestamp",
        "adjusted_pnl",
        "exit_reason",
        "holding_minutes",
        "actual_taken_best_holding_minutes",
        "oracle_holding_gap_minutes",
        "selected_pred_mlp_exit_minutes",
        "selected_pred_hold_gap_minutes",
        "actual_taken_best_adjusted_pnl",
        "exit_regret",
        "exit_capture_ratio",
        "combined_regime",
        "session_regime",
        "selected_direction_inversion_risk",
        "selected_ev_overestimate_risk",
    ]
    output = frame.copy()
    output["target_combo"] = output[targets].apply(
        lambda row: "+".join([target for target, value in row.items() if bool(value)]) or "none",
        axis=1,
    )
    existing = [column for column in [*columns, "target_combo"] if column in output.columns]
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
    raw = read_frames(args.residual_trades)
    frame = normalize_trades(
        raw,
        candidates=set(parse_csv(args.candidates)),
        months=set(parse_csv(args.months)),
    )
    frame = add_exit_features_and_targets(
        frame,
        large_loss_threshold=args.large_loss_threshold,
        min_oracle_edge=args.min_oracle_edge,
        low_capture_threshold=args.low_capture_threshold,
        large_exit_regret_threshold=args.large_exit_regret_threshold,
        hold_too_long_minutes=args.hold_too_long_minutes,
        pred_hold_too_long_minutes=args.pred_hold_too_long_minutes,
    )
    missing_targets = [target for target in targets if target not in frame.columns]
    if missing_targets:
        raise ValueError(f"unknown targets: {', '.join(missing_targets)}")

    overall = target_summary(frame, targets=targets, groups=[])
    candidate = target_summary(frame, targets=targets, groups=["run_name", "candidate"])
    context = target_summary(
        frame,
        targets=targets,
        groups=["run_name", "candidate", "direction", "combined_regime", "session_regime"],
    )
    calibration_predictions, calibration_metrics, calibration_summary = chronological_calibration(
        frame,
        targets=targets,
        specs=specs,
        prior_strength=args.prior_strength,
        min_group_support=args.min_group_support,
    )
    worst = worst_examples(frame, targets=targets, top_n=args.top_n)

    run_dir = make_run_dir(args.output_dir, args.label)
    frame.to_csv(run_dir / "exit_shortening_targets.csv", index=False)
    overall.to_csv(run_dir / "exit_shortening_target_summary.csv", index=False)
    candidate.to_csv(run_dir / "candidate_exit_shortening_target_summary.csv", index=False)
    context.to_csv(run_dir / "context_exit_shortening_target_summary.csv", index=False)
    calibration_predictions.to_csv(
        run_dir / "exit_shortening_chronological_predictions.csv",
        index=False,
    )
    calibration_metrics.to_csv(
        run_dir / "exit_shortening_chronological_metrics.csv",
        index=False,
    )
    calibration_summary.to_csv(
        run_dir / "exit_shortening_chronological_summary.csv",
        index=False,
    )
    worst.to_csv(run_dir / "worst_exit_shortening_examples.csv", index=False)
    config = {
        "residual_trades": args.residual_trades,
        "targets": targets,
        "calibration_specs": specs,
        "candidates": args.candidates,
        "months": args.months,
        "large_loss_threshold": args.large_loss_threshold,
        "min_oracle_edge": args.min_oracle_edge,
        "low_capture_threshold": args.low_capture_threshold,
        "large_exit_regret_threshold": args.large_exit_regret_threshold,
        "hold_too_long_minutes": args.hold_too_long_minutes,
        "pred_hold_too_long_minutes": args.pred_hold_too_long_minutes,
        "prior_strength": args.prior_strength,
        "min_group_support": args.min_group_support,
        "note": "chronological calibration uses only rows with month earlier than the fold month",
    }
    (run_dir / "config.json").write_text(
        json.dumps(config, indent=2, default=local_json_default),
        encoding="utf-8",
    )

    print("Exit-shortening target summary:")
    print(overall.to_string(index=False))
    print("\nCandidate target summary:")
    print(candidate.to_string(index=False))
    print("\nChronological calibration summary:")
    print(calibration_summary.head(args.top_n).to_string(index=False))
    print(f"artifacts: {run_dir}")
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--residual-trades", type=Path, action="append", required=True)
    parser.add_argument("--targets", default=",".join(DEFAULT_TARGETS))
    parser.add_argument("--calibration-specs", default="")
    parser.add_argument("--candidates", default="")
    parser.add_argument("--months", default="")
    parser.add_argument("--large-loss-threshold", type=float, default=-20.0)
    parser.add_argument("--min-oracle-edge", type=float, default=5.0)
    parser.add_argument("--low-capture-threshold", type=float, default=0.25)
    parser.add_argument("--large-exit-regret-threshold", type=float, default=20.0)
    parser.add_argument("--hold-too-long-minutes", type=float, default=30.0)
    parser.add_argument("--pred-hold-too-long-minutes", type=float, default=30.0)
    parser.add_argument("--prior-strength", type=float, default=5.0)
    parser.add_argument("--min-group-support", type=int, default=3)
    parser.add_argument("--top-n", type=int, default=20)
    parser.add_argument("--output-dir", type=Path, default=Path("data/reports/backtests"))
    parser.add_argument("--label", default="entry_ev_exit_shortening_target_diagnostics")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    build_diagnostics(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
