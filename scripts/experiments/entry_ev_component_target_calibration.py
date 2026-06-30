#!/usr/bin/env python3
"""Low-capacity calibration diagnostics for decomposed entry EV targets."""

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
    "direction_side_inversion_target",
    "exit_capture_failure_target",
    "executable_ev_overestimate_target",
    "realized_loss_target",
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


def bool_series(frame: pd.DataFrame, column: str) -> pd.Series:
    series = frame[column]
    if pd.api.types.is_bool_dtype(series):
        return series.fillna(False).astype(bool)
    if pd.api.types.is_numeric_dtype(series):
        return pd.to_numeric(series, errors="coerce").fillna(0.0).ne(0.0)
    normalized = series.astype(str).str.lower().str.strip()
    return normalized.isin({"true", "1", "yes", "y"})


def normalize_targets(frame: pd.DataFrame, *, targets: list[str], group_columns: list[str]) -> pd.DataFrame:
    required = {"candidate", "role", "month", "adjusted_pnl", *targets, *group_columns}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"component target frame missing columns: {', '.join(missing)}")
    output = frame.copy()
    output["candidate"] = output["candidate"].astype(str)
    output["role"] = output["role"].astype(str)
    output["month"] = output["month"].astype(str).str.slice(0, 7)
    output["adjusted_pnl"] = pd.to_numeric(output["adjusted_pnl"], errors="coerce").fillna(0.0)
    for column in group_columns:
        output[column] = (
            output[column]
            .fillna("missing")
            .astype(str)
            .str.strip()
            .replace({"": "missing", "nan": "missing", "None": "missing"})
        )
    for target in targets:
        output[target] = bool_series(output, target)
    return output


def rank_auc(y_true: pd.Series, y_score: pd.Series) -> float:
    y = y_true.astype(bool).to_numpy()
    score = y_score.astype(float).to_numpy()
    valid = np.isfinite(score)
    y = y[valid]
    score = score[valid]
    positives = int(y.sum())
    negatives = int((~y).sum())
    if positives == 0 or negatives == 0:
        return float("nan")
    ranks = pd.Series(score).rank(method="average").to_numpy()
    rank_sum_positive = float(ranks[y].sum())
    return float((rank_sum_positive - positives * (positives + 1) / 2) / (positives * negatives))


def brier_score(y_true: pd.Series, y_score: pd.Series) -> float:
    y = y_true.astype(float)
    score = y_score.astype(float)
    valid = np.isfinite(score)
    if not bool(valid.any()):
        return float("nan")
    return float(((score[valid] - y[valid]) ** 2).mean())


def metric_row(frame: pd.DataFrame, *, target: str, score_column: str | None = None) -> dict[str, Any]:
    target_values = frame[target].astype(bool)
    pnl = frame["adjusted_pnl"].astype(float)
    row: dict[str, Any] = {
        "row_count": int(len(frame)),
        "target_count": int(target_values.sum()),
        "target_rate": float(target_values.mean()) if len(frame) else 0.0,
        "total_pnl": float(pnl.sum()) if len(frame) else 0.0,
        "target_true_pnl": float(pnl.where(target_values, 0.0).sum()) if len(frame) else 0.0,
        "target_false_pnl": float(pnl.where(~target_values, 0.0).sum()) if len(frame) else 0.0,
    }
    if score_column is not None and score_column in frame.columns:
        scores = frame[score_column].astype(float)
        valid = scores.notna() & np.isfinite(scores)
        row.update(
            {
                "predicted_count": int(valid.sum()),
                "predicted_mean": float(scores[valid].mean()) if bool(valid.any()) else float("nan"),
                "brier": brier_score(target_values[valid], scores[valid]),
                "auc": rank_auc(target_values[valid], scores[valid]),
            }
        )
    return row


def target_overall_summary(frame: pd.DataFrame, targets: list[str]) -> pd.DataFrame:
    rows = []
    for target in targets:
        row = {"target": target}
        row.update(metric_row(frame, target=target))
        rows.append(row)
    return pd.DataFrame(rows).sort_values(["target_rate", "target"], ascending=[False, True])


def target_group_summary(
    frame: pd.DataFrame,
    *,
    targets: list[str],
    group_columns: list[str],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for target in targets:
        for keys, group in frame.groupby(group_columns, dropna=False):
            if not isinstance(keys, tuple):
                keys = (keys,)
            row = {"target": target}
            row.update(dict(zip(group_columns, keys, strict=True)))
            row.update(metric_row(group, target=target))
            rows.append(row)
    return pd.DataFrame(rows).sort_values(
        ["target", "target_rate", "row_count"],
        ascending=[True, False, False],
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
    target_values = train[target].astype(bool)
    global_rate = float(target_values.mean())
    rates: dict[tuple[str, ...], tuple[int, float]] = {}
    for keys, group in train.groupby(group_columns, dropna=False):
        if not isinstance(keys, tuple):
            keys = (keys,)
        group_count = int(len(group))
        group_sum = int(group[target].astype(bool).sum())
        if group_count >= min_group_support:
            rate = float((group_sum + prior_strength * global_rate) / (group_count + prior_strength))
            rates[tuple(str(key) for key in keys)] = (group_count, rate)
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


def chronological_month_predictions(
    frame: pd.DataFrame,
    *,
    targets: list[str],
    group_columns: list[str],
    prior_strength: float,
    min_group_support: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    prediction_frames: list[pd.DataFrame] = []
    metric_rows: list[dict[str, Any]] = []
    periods = pd.PeriodIndex(frame["month"].astype(str), freq="M")
    for target in targets:
        for month in sorted(frame["month"].astype(str).unique()):
            target_period = pd.Period(month, freq="M")
            train = frame[periods < target_period].copy()
            test = frame[frame["month"].astype(str).eq(month)].copy()
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
            predicted["target"] = target
            predicted["fold"] = month
            prediction_frames.append(predicted)
            row = {
                "target": target,
                "fold": month,
                "train_rows": int(len(train)),
                "train_months": int(train["month"].nunique()) if len(train) else 0,
                "train_target_rate": (
                    float(train[target].astype(bool).mean()) if len(train) else float("nan")
                ),
                "bucket_count": len(rates),
            }
            row.update(metric_row(predicted, target=target, score_column="predicted_target_rate"))
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
    predictions = pd.concat(prediction_frames, ignore_index=True) if prediction_frames else pd.DataFrame()
    metrics = pd.DataFrame(metric_rows)
    return predictions, metrics


def role_holdout_predictions(
    frame: pd.DataFrame,
    *,
    targets: list[str],
    group_columns: list[str],
    prior_strength: float,
    min_group_support: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    prediction_frames: list[pd.DataFrame] = []
    metric_rows: list[dict[str, Any]] = []
    for target in targets:
        for role in sorted(frame["role"].astype(str).unique()):
            train = frame[~frame["role"].astype(str).eq(role)].copy()
            test = frame[frame["role"].astype(str).eq(role)].copy()
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
            predicted["target"] = target
            predicted["fold"] = role
            prediction_frames.append(predicted)
            row = {
                "target": target,
                "fold": role,
                "train_rows": int(len(train)),
                "train_roles": int(train["role"].nunique()) if len(train) else 0,
                "train_target_rate": (
                    float(train[target].astype(bool).mean()) if len(train) else float("nan")
                ),
                "bucket_count": len(rates),
            }
            row.update(metric_row(predicted, target=target, score_column="predicted_target_rate"))
            row["bucket_prediction_share"] = float(
                predicted["prediction_source"].eq("bucket").mean()
            )
            row["global_prediction_share"] = float(
                predicted["prediction_source"].eq("global").mean()
            )
            metric_rows.append(row)
    predictions = pd.concat(prediction_frames, ignore_index=True) if prediction_frames else pd.DataFrame()
    metrics = pd.DataFrame(metric_rows)
    return predictions, metrics


def summarize_prediction_metrics(metrics: pd.DataFrame, *, fold_type: str) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for target, group in metrics.groupby("target", dropna=False):
        predicted = group["predicted_count"].astype(float)
        total_predicted = float(predicted.sum())
        brier_valid = group["brier"].notna() & np.isfinite(group["brier"].astype(float))
        pred_mean_valid = group["predicted_mean"].notna() & np.isfinite(
            group["predicted_mean"].astype(float)
        )
        brier_weight = group.loc[brier_valid, "predicted_count"].astype(float)
        pred_mean_weight = group.loc[pred_mean_valid, "predicted_count"].astype(float)
        weighted_brier = (
            float(np.average(group.loc[brier_valid, "brier"].astype(float), weights=brier_weight))
            if float(brier_weight.sum()) > 0
            else float("nan")
        )
        weighted_pred_mean = (
            float(
                np.average(
                    group.loc[pred_mean_valid, "predicted_mean"].astype(float),
                    weights=pred_mean_weight,
                )
            )
            if float(pred_mean_weight.sum()) > 0
            else float("nan")
        )
        rows.append(
            {
                "fold_type": fold_type,
                "target": target,
                "fold_count": int(len(group)),
                "row_count": int(group["row_count"].sum()),
                "predicted_count": int(group["predicted_count"].sum()),
                "target_count": int(group["target_count"].sum()),
                "target_rate": float(
                    group["target_count"].sum() / group["row_count"].sum()
                )
                if int(group["row_count"].sum()) > 0
                else 0.0,
                "predicted_mean": weighted_pred_mean,
                "brier": weighted_brier,
                "mean_auc": float(group["auc"].dropna().mean())
                if group["auc"].notna().any()
                else float("nan"),
                "bucket_prediction_share": float(
                    np.average(group["bucket_prediction_share"].astype(float), weights=group["row_count"])
                ),
                "global_prediction_share": float(
                    np.average(group["global_prediction_share"].astype(float), weights=group["row_count"])
                ),
            }
        )
    return pd.DataFrame(rows).sort_values(["fold_type", "target"]).reset_index(drop=True)


def build_diagnostics(args: argparse.Namespace) -> Path:
    targets = parse_csv(args.targets) or DEFAULT_TARGETS
    group_columns = parse_csv(args.group_columns)
    if not group_columns:
        raise ValueError("--group-columns must not be empty")
    frame = normalize_targets(
        pd.read_csv(args.component_targets),
        targets=targets,
        group_columns=group_columns,
    )
    overall = target_overall_summary(frame, targets)
    group_summary = target_group_summary(frame, targets=targets, group_columns=group_columns)
    chrono_predictions, chrono_metrics = chronological_month_predictions(
        frame,
        targets=targets,
        group_columns=group_columns,
        prior_strength=args.prior_strength,
        min_group_support=args.min_group_support,
    )
    role_predictions, role_metrics = role_holdout_predictions(
        frame,
        targets=targets,
        group_columns=group_columns,
        prior_strength=args.prior_strength,
        min_group_support=args.min_group_support,
    )
    metric_summary = pd.concat(
        [
            summarize_prediction_metrics(chrono_metrics, fold_type="chronological_month"),
            summarize_prediction_metrics(role_metrics, fold_type="role_holdout"),
        ],
        ignore_index=True,
    )

    run_dir = make_run_dir(args.output_dir, args.label)
    overall.to_csv(run_dir / "target_overall_summary.csv", index=False)
    group_summary.to_csv(run_dir / "target_group_summary.csv", index=False)
    chrono_metrics.to_csv(run_dir / "target_chronological_month_metrics.csv", index=False)
    role_metrics.to_csv(run_dir / "target_role_holdout_metrics.csv", index=False)
    metric_summary.to_csv(run_dir / "target_calibration_metric_summary.csv", index=False)
    chrono_predictions.to_csv(run_dir / "target_chronological_month_predictions.csv", index=False)
    role_predictions.to_csv(run_dir / "target_role_holdout_predictions.csv", index=False)
    config = {
        "component_targets": args.component_targets,
        "targets": targets,
        "group_columns": group_columns,
        "prior_strength": args.prior_strength,
        "min_group_support": args.min_group_support,
        "note": (
            "chronological_month uses only rows with month earlier than the fold month; "
            "role_holdout trains on other roles only"
        ),
    }
    (run_dir / "config.json").write_text(
        json.dumps(config, indent=2, default=local_json_default),
        encoding="utf-8",
    )

    print("Target calibration metric summary:")
    print(metric_summary.to_string(index=False))
    print("\nTarget overall summary:")
    print(overall.to_string(index=False))
    print(f"artifacts: {run_dir}")
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--component-targets", type=Path, required=True)
    parser.add_argument("--targets", default=",".join(DEFAULT_TARGETS))
    parser.add_argument("--group-columns", default="support_bucket,pressure_bucket")
    parser.add_argument("--prior-strength", type=float, default=5.0)
    parser.add_argument("--min-group-support", type=int, default=3)
    parser.add_argument("--output-dir", type=Path, default=Path("data/reports/backtests"))
    parser.add_argument("--label", default="entry_ev_component_target_calibration")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    build_diagnostics(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
