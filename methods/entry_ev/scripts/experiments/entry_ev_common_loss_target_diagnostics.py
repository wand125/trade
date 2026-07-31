#!/usr/bin/env python3
"""Build target diagnostics for common-entry and replacement losses."""

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


COMMON_TARGETS = [
    "common_realized_loss_target",
    "common_large_loss_target",
    "common_degraded_target",
    "direction_side_inversion_target",
    "exit_capture_failure_target",
    "common_low_risk_large_loss_target",
    "common_failure_target",
]

REPLACEMENT_TARGETS = [
    "replacement_realized_loss_target",
    "replacement_large_loss_target",
    "replacement_direction_side_inversion_target",
    "replacement_exit_capture_failure_target",
    "replacement_positive_quality_target",
]

CALIBRATION_SPECS = {
    "side_context": ["direction", "combined_regime", "session_regime"],
    "risk_pressure": [
        "direction",
        "selected_risk_bucket",
        "selected_side_support_bucket",
        "selected_side_pressure_bucket",
    ],
    "score_hold": [
        "direction",
        "selected_risk_bucket",
        "score_delta_bucket",
        "pred_hold_bucket",
        "pred_rank_bucket",
    ],
    "side_context_risk": [
        "direction",
        "combined_regime",
        "session_regime",
        "selected_risk_bucket",
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


def normalize_combined_trades(frame: pd.DataFrame) -> pd.DataFrame:
    required = {
        "variant",
        "month",
        "candidate",
        "direction",
        "entry_decision_timestamp",
        "replacement_status",
        "adjusted_pnl",
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"combined trade frame missing columns: {', '.join(missing)}")
    output = frame.copy()
    output["month"] = output["month"].astype(str).str.slice(0, 7)
    output["variant"] = output["variant"].astype(str)
    output["candidate"] = output["candidate"].astype(str)
    output["direction"] = output["direction"].astype(str).str.lower()
    output["entry_decision_timestamp"] = pd.to_datetime(
        output["entry_decision_timestamp"],
        utc=True,
    ).astype(str)
    if "_trade_key" not in output.columns:
        output["_trade_key"] = (
            output[["candidate", "month", "direction", "entry_decision_timestamp"]]
            .astype(str)
            .agg("|".join, axis=1)
        )
    return output


def exit_capture_ratio(realized: pd.Series, oracle_edge: pd.Series) -> pd.Series:
    positive_realized = realized.astype(float).clip(lower=0.0)
    oracle = oracle_edge.astype(float)
    ratio = np.where(oracle > 0.0, positive_realized / oracle.replace(0.0, np.nan), np.nan)
    return pd.Series(ratio, index=realized.index).fillna(0.0).clip(0.0, 1.0)


def bucketize_features(frame: pd.DataFrame) -> pd.DataFrame:
    output = frame.copy()
    output["selected_risk_bucket"] = pd.cut(
        numeric_series(output, "selected_side_prior_pressure_risk", default=np.nan),
        bins=[-0.001, 0.20, 0.45, 0.60, float("inf")],
        labels=["very_low", "medium", "high", "extreme"],
    ).astype(str).replace({"nan": "missing"})
    output["score_delta_bucket"] = pd.cut(
        numeric_series(output, "selected_side_score_delta", default=np.nan),
        bins=[-float("inf"), -2.0, -1.0, -0.25, 0.25, float("inf")],
        labels=["strong_penalty", "penalty", "mild_penalty", "flat", "boost"],
    ).astype(str).replace({"nan": "missing"})
    output["pred_ev_bucket"] = pd.cut(
        numeric_series(output, "pred_taken_ev", default=np.nan),
        bins=[-float("inf"), 0.0, 5.0, 15.0, 30.0, float("inf")],
        labels=["nonpositive", "low", "medium", "high", "extreme"],
    ).astype(str).replace({"nan": "missing"})
    output["pred_hold_bucket"] = pd.cut(
        numeric_series(output, "pred_taken_best_holding_minutes", default=np.nan),
        bins=[-0.001, 60.0, 240.0, 720.0, 1440.0, float("inf")],
        labels=["lt60", "60_240", "240_720", "720_1440", "gt1440"],
    ).astype(str).replace({"nan": "missing"})
    output["pred_rank_bucket"] = pd.cut(
        numeric_series(output, "pred_taken_entry_local_rank", default=np.nan),
        bins=[-0.001, 0.50, 0.80, 0.95, 0.99, float("inf")],
        labels=["low", "mid", "high", "very_high", "top"],
    ).astype(str).replace({"nan": "missing"})
    output["pred_side_gap_bucket"] = pd.cut(
        numeric_series(output, "pred_side_confidence_gap", default=np.nan),
        bins=[-float("inf"), 0.0, 0.10, 0.25, 0.50, float("inf")],
        labels=["nonpositive", "small", "medium", "large", "extreme"],
    ).astype(str).replace({"nan": "missing"})
    return output


def candidate_column(frame: pd.DataFrame, column: str, default: Any = np.nan) -> pd.Series:
    candidate_name = f"{column}_candidate"
    if candidate_name in frame.columns:
        return frame[candidate_name]
    if column in frame.columns:
        return frame[column]
    return pd.Series(default, index=frame.index)


def build_common_entry_targets(
    combined: pd.DataFrame,
    *,
    base_label: str,
    candidate_label: str,
    large_loss_threshold: float,
    degradation_threshold: float,
    low_risk_threshold: float,
    large_exit_regret_threshold: float,
    low_exit_capture_threshold: float,
    min_oracle_edge: float,
) -> pd.DataFrame:
    common = combined[combined["replacement_status"].astype(str).eq("common")].copy()
    base = common[common["variant"].eq(base_label)].copy()
    candidate = common[common["variant"].eq(candidate_label)].copy()
    if base.empty or candidate.empty:
        return pd.DataFrame()
    base = base.drop_duplicates("_trade_key", keep="first")
    candidate = candidate.drop_duplicates("_trade_key", keep="first")
    merged = base.merge(
        candidate,
        on="_trade_key",
        how="inner",
        suffixes=("_base", "_candidate"),
    )
    if merged.empty:
        return pd.DataFrame()

    output = pd.DataFrame(index=merged.index)
    for column in [
        "candidate",
        "month",
        "direction",
        "entry_decision_timestamp",
        "combined_regime",
        "session_regime",
        "selected_side_support_bucket",
        "selected_side_pressure_bucket",
        "selected_side_prior_support_bucket",
        "selected_side_feature_pressure_bucket",
        "selected_side_prediction_source",
    ]:
        output[column] = text_series(merged, f"{column}_candidate")
    for column in [
        "selected_side_prior_pressure_risk",
        "selected_side_score_delta",
        "selected_side_base_score",
        "selected_side_side_prior_score",
        "selected_side_prior_downside_risk",
        "selected_side_feature_pressure",
        "selected_side_signed_drift",
        "pred_taken_ev",
        "pred_opposite_ev",
        "pred_side_confidence_gap",
        "pred_taken_best_holding_minutes",
        "pred_taken_entry_local_rank",
        "pred_taken_wait_regret",
        "actual_taken_best_adjusted_pnl",
        "exit_regret",
        "best_side_regret",
        "ev_overestimate_vs_realized",
        "ev_overestimate_vs_oracle",
    ]:
        output[column] = numeric_series(merged, f"{column}_candidate", default=np.nan)
    output["_trade_key"] = merged["_trade_key"].astype(str)
    output["base_adjusted_pnl"] = numeric_series(merged, "adjusted_pnl_base")
    output["candidate_adjusted_pnl"] = numeric_series(merged, "adjusted_pnl_candidate")
    output["same_entry_exit_delta"] = (
        output["candidate_adjusted_pnl"] - output["base_adjusted_pnl"]
    )
    output["direction_side_inversion_target"] = bool_series(
        merged,
        "direction_error_candidate",
    )
    output["no_edge_entry_target"] = bool_series(merged, "no_edge_entry_candidate")
    capture_ratio = exit_capture_ratio(
        output["candidate_adjusted_pnl"],
        output["actual_taken_best_adjusted_pnl"],
    )
    output["exit_capture_ratio"] = capture_ratio
    output["common_realized_loss_target"] = output["candidate_adjusted_pnl"] < 0.0
    output["common_large_loss_target"] = output["candidate_adjusted_pnl"] <= large_loss_threshold
    output["common_degraded_target"] = output["same_entry_exit_delta"] <= degradation_threshold
    output["exit_capture_failure_target"] = (
        output["exit_regret"].fillna(0.0).ge(large_exit_regret_threshold)
        | (
            output["actual_taken_best_adjusted_pnl"].fillna(0.0).ge(min_oracle_edge)
            & capture_ratio.le(low_exit_capture_threshold)
        )
    )
    output["common_low_risk_large_loss_target"] = (
        output["selected_side_prior_pressure_risk"].fillna(1.0).le(low_risk_threshold)
        & output["common_large_loss_target"]
    )
    output["common_failure_target"] = (
        output["common_large_loss_target"]
        | output["common_degraded_target"]
        | output["direction_side_inversion_target"]
        | output["exit_capture_failure_target"]
    )
    output = bucketize_features(output)
    return output.reset_index(drop=True)


def build_replacement_targets(
    combined: pd.DataFrame,
    *,
    candidate_label: str,
    large_loss_threshold: float,
    large_exit_regret_threshold: float,
    low_exit_capture_threshold: float,
    min_oracle_edge: float,
) -> pd.DataFrame:
    status = f"only_{candidate_label}"
    replacements = combined[
        combined["variant"].eq(candidate_label)
        & combined["replacement_status"].astype(str).eq(status)
    ].copy()
    if replacements.empty:
        return pd.DataFrame()
    output = replacements.copy()
    output["replacement_adjusted_pnl"] = numeric_series(output, "adjusted_pnl")
    output["replacement_realized_loss_target"] = output["replacement_adjusted_pnl"] < 0.0
    output["replacement_large_loss_target"] = (
        output["replacement_adjusted_pnl"] <= large_loss_threshold
    )
    output["replacement_direction_side_inversion_target"] = bool_series(
        output,
        "direction_error",
    )
    capture_ratio = exit_capture_ratio(
        output["replacement_adjusted_pnl"],
        numeric_series(output, "actual_taken_best_adjusted_pnl", default=np.nan),
    )
    output["exit_capture_ratio"] = capture_ratio
    output["replacement_exit_capture_failure_target"] = (
        numeric_series(output, "exit_regret", default=0.0).ge(large_exit_regret_threshold)
        | (
            numeric_series(output, "actual_taken_best_adjusted_pnl", default=0.0).ge(
                min_oracle_edge
            )
            & capture_ratio.le(low_exit_capture_threshold)
        )
    )
    output["replacement_positive_quality_target"] = output["replacement_adjusted_pnl"] > 0.0
    output = bucketize_features(output)
    return output.reset_index(drop=True)


def target_metric_row(
    frame: pd.DataFrame,
    *,
    target: str,
    pnl_column: str,
    score_column: str | None = None,
) -> dict[str, Any]:
    target_values = bool_series(frame, target)
    pnl = numeric_series(frame, pnl_column)
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
        score = numeric_series(frame, score_column, default=np.nan)
        valid = score.notna() & np.isfinite(score)
        row.update(
            {
                "score_column": score_column,
                "predicted_count": int(valid.sum()),
                "predicted_mean": float(score[valid].mean()) if bool(valid.any()) else float("nan"),
                "auc": rank_auc(target_values[valid], score[valid]),
                "brier": brier_score(target_values[valid], score[valid]),
            }
        )
    return row


def target_overall_summary(
    frame: pd.DataFrame,
    *,
    targets: list[str],
    pnl_column: str,
    score_column: str | None = None,
) -> pd.DataFrame:
    rows = []
    for target in targets:
        row = {"target": target}
        row.update(target_metric_row(frame, target=target, pnl_column=pnl_column, score_column=score_column))
        rows.append(row)
    return pd.DataFrame(rows).sort_values(
        ["target_true_pnl", "target_rate"],
        ascending=[True, False],
    ).reset_index(drop=True)


def target_group_summary(
    frame: pd.DataFrame,
    *,
    targets: list[str],
    group_columns: list[str],
    pnl_column: str,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for target in targets:
        for keys, group in frame.groupby(group_columns, dropna=False):
            if not isinstance(keys, tuple):
                keys = (keys,)
            row = {"target": target}
            row.update(dict(zip(group_columns, keys, strict=True)))
            row.update(target_metric_row(group, target=target, pnl_column=pnl_column))
            rows.append(row)
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(
        ["target", "target_true_pnl", "row_count"],
        ascending=[True, True, False],
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
                    target_metric_row(
                        predicted,
                        target=target,
                        pnl_column="candidate_adjusted_pnl",
                        score_column="predicted_target_rate",
                    )
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
            summary_rows.append(
                {
                    "calibration_spec": spec_name,
                    "target": target,
                    "fold_count": int(len(group)),
                    "row_count": int(group["row_count"].sum()),
                    "target_rate": float(
                        group["target_count"].sum() / max(group["row_count"].sum(), 1)
                    ),
                    "target_true_pnl": float(group["target_true_pnl"].sum()),
                    "mean_auc": float(group["auc"].dropna().mean())
                    if bool(group["auc"].notna().any())
                    else float("nan"),
                    "mean_brier": float(group["brier"].dropna().mean())
                    if bool(group["brier"].notna().any())
                    else float("nan"),
                    "bucket_prediction_share": float(
                        (predictions[
                            predictions["calibration_spec"].eq(spec_name)
                            & predictions["target"].eq(target)
                        ]["prediction_source"].eq("bucket")).mean()
                    ),
                }
            )
    summary = pd.DataFrame(summary_rows).sort_values(
        ["mean_auc", "target_true_pnl"],
        ascending=[False, True],
    ).reset_index(drop=True) if summary_rows else pd.DataFrame()
    return predictions, metrics, summary


def build_diagnostics(args: argparse.Namespace) -> Path:
    combined = normalize_combined_trades(pd.read_csv(args.combined_trades))
    common_targets = build_common_entry_targets(
        combined,
        base_label=args.base_label,
        candidate_label=args.candidate_label,
        large_loss_threshold=args.large_loss_threshold,
        degradation_threshold=args.degradation_threshold,
        low_risk_threshold=args.low_risk_threshold,
        large_exit_regret_threshold=args.large_exit_regret_threshold,
        low_exit_capture_threshold=args.low_exit_capture_threshold,
        min_oracle_edge=args.min_oracle_edge,
    )
    replacement_targets = build_replacement_targets(
        combined,
        candidate_label=args.candidate_label,
        large_loss_threshold=args.large_loss_threshold,
        large_exit_regret_threshold=args.large_exit_regret_threshold,
        low_exit_capture_threshold=args.low_exit_capture_threshold,
        min_oracle_edge=args.min_oracle_edge,
    )
    common_summary = target_overall_summary(
        common_targets,
        targets=COMMON_TARGETS,
        pnl_column="candidate_adjusted_pnl",
        score_column="selected_side_prior_pressure_risk",
    )
    common_context_summary = target_group_summary(
        common_targets,
        targets=COMMON_TARGETS,
        group_columns=["candidate", "direction", "combined_regime", "session_regime"],
        pnl_column="candidate_adjusted_pnl",
    )
    low_risk_loss_context = common_context_summary[
        common_context_summary["target"].eq("common_low_risk_large_loss_target")
        & common_context_summary["target_count"].gt(0)
    ].copy()
    replacement_summary = target_overall_summary(
        replacement_targets,
        targets=REPLACEMENT_TARGETS,
        pnl_column="replacement_adjusted_pnl",
        score_column="selected_side_prior_pressure_risk",
    )
    replacement_context_summary = target_group_summary(
        replacement_targets,
        targets=REPLACEMENT_TARGETS,
        group_columns=["candidate", "direction", "combined_regime", "session_regime"],
        pnl_column="replacement_adjusted_pnl",
    )
    calibration_predictions, calibration_metrics, calibration_summary = chronological_calibration(
        common_targets,
        targets=[
            "common_large_loss_target",
            "common_degraded_target",
            "direction_side_inversion_target",
            "exit_capture_failure_target",
            "common_low_risk_large_loss_target",
        ],
        specs=CALIBRATION_SPECS,
        prior_strength=args.prior_strength,
        min_group_support=args.min_group_support,
    )

    run_dir = make_run_dir(args.output_dir, args.label)
    common_targets.to_csv(run_dir / "common_entry_targets.csv", index=False)
    replacement_targets.to_csv(run_dir / "replacement_targets.csv", index=False)
    common_summary.to_csv(run_dir / "common_target_summary.csv", index=False)
    common_context_summary.to_csv(run_dir / "common_context_target_summary.csv", index=False)
    low_risk_loss_context.to_csv(run_dir / "common_low_risk_loss_context_summary.csv", index=False)
    replacement_summary.to_csv(run_dir / "replacement_target_summary.csv", index=False)
    replacement_context_summary.to_csv(
        run_dir / "replacement_context_target_summary.csv",
        index=False,
    )
    calibration_predictions.to_csv(
        run_dir / "common_chronological_calibration_predictions.csv",
        index=False,
    )
    calibration_metrics.to_csv(
        run_dir / "common_chronological_calibration_metrics.csv",
        index=False,
    )
    calibration_summary.to_csv(
        run_dir / "common_chronological_calibration_summary.csv",
        index=False,
    )
    config = {
        "combined_trades": args.combined_trades,
        "base_label": args.base_label,
        "candidate_label": args.candidate_label,
        "large_loss_threshold": args.large_loss_threshold,
        "degradation_threshold": args.degradation_threshold,
        "low_risk_threshold": args.low_risk_threshold,
        "large_exit_regret_threshold": args.large_exit_regret_threshold,
        "low_exit_capture_threshold": args.low_exit_capture_threshold,
        "min_oracle_edge": args.min_oracle_edge,
        "prior_strength": args.prior_strength,
        "min_group_support": args.min_group_support,
        "calibration_specs": CALIBRATION_SPECS,
    }
    (run_dir / "config.json").write_text(
        json.dumps(config, indent=2, default=local_json_default),
        encoding="utf-8",
    )

    print("Common target summary:")
    print(common_summary.to_string(index=False))
    print("\nCommon chronological calibration summary:")
    print(calibration_summary.head(20).to_string(index=False))
    print("\nReplacement target summary:")
    print(replacement_summary.to_string(index=False))
    print(f"artifacts: {run_dir}")
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--combined-trades", type=Path, required=True)
    parser.add_argument("--base-label", default="base")
    parser.add_argument("--candidate-label", default="side_prior")
    parser.add_argument("--large-loss-threshold", type=float, default=-20.0)
    parser.add_argument("--degradation-threshold", type=float, default=-5.0)
    parser.add_argument("--low-risk-threshold", type=float, default=0.25)
    parser.add_argument("--large-exit-regret-threshold", type=float, default=20.0)
    parser.add_argument("--low-exit-capture-threshold", type=float, default=0.25)
    parser.add_argument("--min-oracle-edge", type=float, default=5.0)
    parser.add_argument("--prior-strength", type=float, default=5.0)
    parser.add_argument("--min-group-support", type=int, default=3)
    parser.add_argument("--output-dir", type=Path, default=Path("data/reports/backtests"))
    parser.add_argument("--label", default="entry_ev_common_loss_target_diagnostics")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    build_diagnostics(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
