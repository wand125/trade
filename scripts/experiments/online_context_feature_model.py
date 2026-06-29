#!/usr/bin/env python3
"""Evaluate online context state as chronological trade-risk features."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import brier_score_loss, roc_auc_score

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from trade_data.backtest import json_default, make_run_dir, parse_csv_floats  # noqa: E402


TARGETS = {
    "nonpositive": lambda pnl, large_loss_threshold: pnl <= 0.0,
    "large_loss": lambda pnl, large_loss_threshold: pnl <= large_loss_threshold,
}

BASE_NUMERIC_FEATURES = (
    "direction_sign",
    "entry_margin",
    "pred_taken_score",
    "pred_opposite_score",
    "pred_taken_score_gap",
    "pred_best_side_prob_1",
    "pred_best_side_prob_-1",
    "decision_hour_sin",
    "decision_hour_cos",
)
CONTEXT_NUMERIC_FEATURES = (
    "prior_context_pnl",
    "prior_context_trade_count",
    "prior_context_win_rate",
    "prior_side_month_pnl",
    "prior_side_month_trade_count",
    "minutes_since_context_last_exit",
    "prior_context_active_loss_breach_20",
    "prior_context_ever_breached_20",
    "minutes_since_context_breach_20",
    "prior_side_month_active_loss_breach_20",
    "prior_side_month_ever_breached_20",
    "prior_context_active_loss_breach_40",
    "prior_context_ever_breached_40",
    "minutes_since_context_breach_40",
    "prior_side_month_active_loss_breach_40",
    "prior_side_month_ever_breached_40",
    "prior_context_active_loss_breach_60",
    "prior_context_ever_breached_60",
    "minutes_since_context_breach_60",
    "prior_side_month_active_loss_breach_60",
    "prior_side_month_ever_breached_60",
)
BASE_CATEGORY_FEATURES = ("direction", "combined_regime", "session_regime")
CONTEXT_CATEGORY_FEATURES = (
    "prior_context_pnl_bucket",
    "prior_context_trade_count_bucket",
    "entry_margin_bucket",
    "minutes_since_breach20_bucket",
)


@dataclass(frozen=True)
class FeatureSpec:
    name: str
    numeric_features: tuple[str, ...]
    category_features: tuple[str, ...]


FEATURE_SPECS = (
    FeatureSpec("base", BASE_NUMERIC_FEATURES, BASE_CATEGORY_FEATURES),
    FeatureSpec(
        "context",
        (*BASE_NUMERIC_FEATURES, *CONTEXT_NUMERIC_FEATURES),
        (*BASE_CATEGORY_FEATURES, *CONTEXT_CATEGORY_FEATURES),
    ),
)


def local_json_default(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    try:
        return json_default(value)
    except TypeError:
        pass
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, np.bool_):
        return bool(value)
    raise TypeError(f"cannot serialize {type(value).__name__}")


def parse_csv_strings(value: str) -> list[str]:
    values = [part.strip() for part in value.split(",") if part.strip()]
    if not values:
        raise argparse.ArgumentTypeError("at least one value is required")
    return values


def normalize_trades(frame: pd.DataFrame, *, large_loss_threshold: float) -> pd.DataFrame:
    required = {
        "direction",
        "entry_decision_timestamp",
        "adjusted_pnl",
        "entry_month",
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"trades missing required columns: {', '.join(missing)}")

    output = frame.copy()
    output["entry_decision_timestamp"] = pd.to_datetime(
        output["entry_decision_timestamp"],
        utc=True,
    )
    output["entry_month"] = output["entry_month"].astype(str).str.slice(0, 7)
    output["adjusted_pnl"] = pd.to_numeric(output["adjusted_pnl"], errors="raise")
    output["direction"] = output["direction"].astype(str).str.lower()
    output["direction_sign"] = np.select(
        [output["direction"].eq("long"), output["direction"].eq("short")],
        [1.0, -1.0],
        default=0.0,
    )
    hours = (
        output["entry_decision_timestamp"].dt.hour
        + output["entry_decision_timestamp"].dt.minute / 60.0
    )
    radians = 2.0 * np.pi * hours / 24.0
    output["decision_hour_sin"] = np.sin(radians)
    output["decision_hour_cos"] = np.cos(radians)
    for name, factory in TARGETS.items():
        output[f"target_{name}"] = factory(output["adjusted_pnl"], large_loss_threshold).astype(
            int
        )
    return output


def feature_frame(frame: pd.DataFrame, spec: FeatureSpec) -> pd.DataFrame:
    output = pd.DataFrame(index=frame.index)
    for column in spec.numeric_features:
        if column in frame.columns:
            output[column] = pd.to_numeric(frame[column], errors="coerce")
        else:
            output[column] = np.nan
    for column in spec.category_features:
        if column in frame.columns:
            output[column] = frame[column].astype("string").fillna("__missing__")
        else:
            output[column] = "__missing__"
    return output


def fit_category_maps(train: pd.DataFrame, category_features: tuple[str, ...]) -> dict[str, dict[str, int]]:
    maps: dict[str, dict[str, int]] = {}
    for column in category_features:
        values = sorted(str(value) for value in train[column].astype("string").fillna("__missing__").unique())
        maps[column] = {value: index for index, value in enumerate(values)}
    return maps


def encode_features(
    frame: pd.DataFrame,
    *,
    spec: FeatureSpec,
    category_maps: dict[str, dict[str, int]],
) -> pd.DataFrame:
    encoded = pd.DataFrame(index=frame.index)
    for column in spec.numeric_features:
        series = pd.to_numeric(frame[column], errors="coerce")
        encoded[column] = series.replace([np.inf, -np.inf], np.nan).fillna(0.0)
    for column in spec.category_features:
        mapping = category_maps.get(column, {})
        encoded[f"{column}_code"] = (
            frame[column]
            .astype("string")
            .fillna("__missing__")
            .map(mapping)
            .fillna(-1)
            .astype(float)
        )
    return encoded


def fit_predict_probabilities(
    train_features: pd.DataFrame,
    train_target: pd.Series,
    test_features: pd.DataFrame,
    *,
    max_iter: int,
    learning_rate: float,
    max_leaf_nodes: int,
    min_samples_leaf: int,
    l2_regularization: float,
    random_seed: int,
) -> tuple[np.ndarray, np.ndarray]:
    target = train_target.astype(int)
    target_mean = float(target.mean()) if len(target) else 0.0
    if target.nunique(dropna=True) < 2:
        train_prob = np.full(len(train_features), target_mean, dtype="float64")
        test_prob = np.full(len(test_features), target_mean, dtype="float64")
        return train_prob, test_prob

    model = HistGradientBoostingClassifier(
        max_iter=max_iter,
        learning_rate=learning_rate,
        max_leaf_nodes=max_leaf_nodes,
        min_samples_leaf=min_samples_leaf,
        l2_regularization=l2_regularization,
        random_state=random_seed,
    )
    model.fit(train_features.astype("float32").to_numpy(), target.to_numpy(dtype="int8"))
    classes = list(model.classes_)
    positive_index = classes.index(1)
    train_prob = model.predict_proba(train_features.astype("float32").to_numpy())[
        :, positive_index
    ]
    test_prob = model.predict_proba(test_features.astype("float32").to_numpy())[
        :, positive_index
    ]
    return np.clip(train_prob, 0.0, 1.0), np.clip(test_prob, 0.0, 1.0)


def auc_or_half(y_true: pd.Series, y_pred: pd.Series) -> float:
    if y_true.nunique(dropna=True) < 2:
        return 0.5
    return float(roc_auc_score(y_true.astype(int), y_pred.astype(float)))


def model_metrics(scored: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for feature_set in sorted(scored["feature_set"].unique()):
        for target_name in TARGETS:
            subset = scored[scored["feature_set"].eq(feature_set)]
            y_true = subset[f"target_{target_name}"].astype(int)
            y_pred = subset[f"pred_{target_name}_risk"].astype(float).clip(0.0, 1.0)
            rows.append(
                {
                    "feature_set": feature_set,
                    "target": target_name,
                    "trade_count": int(len(subset)),
                    "prevalence": float(y_true.mean()) if len(y_true) else 0.0,
                    "predicted_mean": float(y_pred.mean()) if len(y_pred) else 0.0,
                    "bias": float(y_pred.mean() - y_true.mean()) if len(y_pred) else 0.0,
                    "brier": float(brier_score_loss(y_true, y_pred)) if len(y_true) else 0.0,
                    "auc": auc_or_half(y_true, y_pred),
                }
            )
    return pd.DataFrame(rows)


def summarize_filters(scored: pd.DataFrame, quantiles: tuple[float, ...]) -> tuple[pd.DataFrame, pd.DataFrame]:
    monthly_rows: list[dict[str, Any]] = []
    for (feature_set, target_name, month), subset in scored.groupby(
        ["feature_set", "target_name", "entry_month"],
        dropna=False,
    ):
        original_pnl = float(subset["adjusted_pnl"].sum())
        for quantile in quantiles:
            threshold_column = f"train_q{quantile:g}_{target_name}_risk"
            if threshold_column not in subset.columns:
                continue
            threshold = float(subset[threshold_column].iloc[0])
            risk = subset[f"pred_{target_name}_risk"].astype(float)
            keep = risk < threshold
            filtered_pnl = float(subset.loc[~keep, "adjusted_pnl"].sum())
            monthly_rows.append(
                {
                    "feature_set": feature_set,
                    "target": target_name,
                    "risk_quantile": quantile,
                    "entry_month": month,
                    "threshold": threshold,
                    "baseline_trade_count": int(len(subset)),
                    "kept_trade_count": int(keep.sum()),
                    "filtered_trade_count": int((~keep).sum()),
                    "baseline_adjusted_pnl": original_pnl,
                    "kept_adjusted_pnl": float(subset.loc[keep, "adjusted_pnl"].sum()),
                    "filtered_adjusted_pnl": filtered_pnl,
                    "delta_vs_baseline": -filtered_pnl,
                }
            )
    monthly = pd.DataFrame(monthly_rows)
    if monthly.empty:
        return monthly, pd.DataFrame()
    summary = (
        monthly.groupby(["feature_set", "target", "risk_quantile"], dropna=False)
        .agg(
            month_count=("entry_month", "nunique"),
            baseline_trade_count=("baseline_trade_count", "sum"),
            kept_trade_count=("kept_trade_count", "sum"),
            filtered_trade_count=("filtered_trade_count", "sum"),
            baseline_adjusted_pnl=("baseline_adjusted_pnl", "sum"),
            kept_adjusted_pnl=("kept_adjusted_pnl", "sum"),
            filtered_adjusted_pnl=("filtered_adjusted_pnl", "sum"),
            delta_vs_baseline=("delta_vs_baseline", "sum"),
            worst_month_kept_pnl=("kept_adjusted_pnl", "min"),
            worst_month_delta=("delta_vs_baseline", "min"),
        )
        .reset_index()
        .sort_values(["delta_vs_baseline", "worst_month_kept_pnl"], ascending=[False, False])
    )
    return monthly, summary


def run_experiment(
    *,
    trades_path: Path,
    output_dir: Path,
    label: str,
    min_train_months: int,
    large_loss_threshold: float,
    risk_quantiles: tuple[float, ...],
    max_iter: int,
    learning_rate: float,
    max_leaf_nodes: int,
    min_samples_leaf: int,
    l2_regularization: float,
    random_seed: int,
) -> Path:
    if min_train_months < 1:
        raise ValueError("min_train_months must be positive")
    trades = normalize_trades(pd.read_csv(trades_path), large_loss_threshold=large_loss_threshold)
    months = sorted(trades["entry_month"].dropna().astype(str).unique())
    if len(months) <= min_train_months:
        raise ValueError("not enough months for chronological OOF")

    scored_frames: list[pd.DataFrame] = []
    fold_rows: list[dict[str, Any]] = []
    for target_month in months[min_train_months:]:
        train_months = [month for month in months if month < target_month]
        train = trades[trades["entry_month"].isin(train_months)].copy()
        test = trades[trades["entry_month"].eq(target_month)].copy()
        if train.empty or test.empty:
            continue
        for spec in FEATURE_SPECS:
            raw_train = feature_frame(train, spec)
            raw_test = feature_frame(test, spec)
            maps = fit_category_maps(raw_train, spec.category_features)
            encoded_train = encode_features(raw_train, spec=spec, category_maps=maps)
            encoded_test = encode_features(raw_test, spec=spec, category_maps=maps)
            scored = test.copy()
            scored["feature_set"] = spec.name
            scored["target_name"] = "__all__"
            for target_name in TARGETS:
                train_prob, test_prob = fit_predict_probabilities(
                    encoded_train,
                    train[f"target_{target_name}"],
                    encoded_test,
                    max_iter=max_iter,
                    learning_rate=learning_rate,
                    max_leaf_nodes=max_leaf_nodes,
                    min_samples_leaf=min_samples_leaf,
                    l2_regularization=l2_regularization,
                    random_seed=random_seed,
                )
                scored[f"pred_{target_name}_risk"] = test_prob
                for quantile in risk_quantiles:
                    scored[f"train_q{quantile:g}_{target_name}_risk"] = float(
                        np.quantile(train_prob, quantile)
                    )
                fold_rows.append(
                    {
                        "target_month": target_month,
                        "feature_set": spec.name,
                        "target": target_name,
                        "train_month_count": len(train_months),
                        "train_trade_count": int(len(train)),
                        "test_trade_count": int(len(test)),
                        "train_prevalence": float(train[f"target_{target_name}"].mean()),
                        "test_prevalence": float(test[f"target_{target_name}"].mean()),
                        "test_adjusted_pnl": float(test["adjusted_pnl"].sum()),
                    }
                )
            scored_frames.append(scored)

    if not scored_frames:
        raise ValueError("no OOF folds were scored")
    scored_all = pd.concat(scored_frames, ignore_index=True)
    model_rows: list[pd.DataFrame] = []
    for feature_set, subset in scored_all.groupby("feature_set", dropna=False):
        frame = subset.copy()
        frame["feature_set"] = feature_set
        model_rows.append(frame)
    scored_all = pd.concat(model_rows, ignore_index=True)

    long_scored_rows: list[pd.DataFrame] = []
    for target_name in TARGETS:
        subset = scored_all.copy()
        subset["target_name"] = target_name
        long_scored_rows.append(subset)
    scored_long = pd.concat(long_scored_rows, ignore_index=True)

    metrics = model_metrics(scored_all)
    filter_monthly, filter_summary = summarize_filters(scored_long, risk_quantiles)

    run_dir = make_run_dir(output_dir, label)
    scored_all.to_csv(run_dir / "oof_predictions.csv", index=False)
    pd.DataFrame(fold_rows).to_csv(run_dir / "fold_summary.csv", index=False)
    metrics.to_csv(run_dir / "model_metrics.csv", index=False)
    filter_monthly.to_csv(run_dir / "risk_filter_by_month.csv", index=False)
    filter_summary.to_csv(run_dir / "risk_filter_summary.csv", index=False)

    best_filters = (
        filter_summary.head(10).to_dict(orient="records") if not filter_summary.empty else []
    )
    config = {
        "trades_path": trades_path,
        "output_dir": output_dir,
        "label": label,
        "min_train_months": min_train_months,
        "large_loss_threshold": large_loss_threshold,
        "risk_quantiles": risk_quantiles,
        "max_iter": max_iter,
        "learning_rate": learning_rate,
        "max_leaf_nodes": max_leaf_nodes,
        "min_samples_leaf": min_samples_leaf,
        "l2_regularization": l2_regularization,
        "random_seed": random_seed,
        "feature_sets": {
            spec.name: {
                "numeric_features": spec.numeric_features,
                "category_features": spec.category_features,
            }
            for spec in FEATURE_SPECS
        },
    }
    summary = {
        "row_count": int(len(trades)),
        "scored_row_count": int(len(scored_all)),
        "month_count": int(len(months)),
        "scored_month_count": int(scored_all["entry_month"].nunique()),
        "baseline_scored_adjusted_pnl": float(
            scored_all[scored_all["feature_set"].eq("base")]
            .drop_duplicates(["source_run", "entry_decision_timestamp", "direction"], keep="first")[
                "adjusted_pnl"
            ]
            .sum()
        )
        if {"source_run", "entry_decision_timestamp", "direction"}.issubset(scored_all.columns)
        else float(scored_all[scored_all["feature_set"].eq("base")]["adjusted_pnl"].sum()),
        "best_filters": best_filters,
    }
    (run_dir / "config.json").write_text(
        json.dumps(config, ensure_ascii=False, indent=2, default=local_json_default) + "\n",
        encoding="utf-8",
    )
    (run_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=local_json_default) + "\n",
        encoding="utf-8",
    )

    print("model metrics:")
    print(metrics.to_string(index=False))
    print("top risk filters:")
    if filter_summary.empty:
        print("(none)")
    else:
        print(filter_summary.head(12).to_string(index=False))
    print(f"artifacts: {run_dir}")
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Chronological OOF diagnostic for online context state features.",
    )
    parser.add_argument("--trades", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("data/reports/modeling"))
    parser.add_argument("--label", default="online_context_feature_model")
    parser.add_argument("--min-train-months", type=int, default=4)
    parser.add_argument("--large-loss-threshold", type=float, default=-15.0)
    parser.add_argument("--risk-quantiles", type=parse_csv_floats, default=[0.70, 0.80, 0.90])
    parser.add_argument("--max-iter", type=int, default=80)
    parser.add_argument("--learning-rate", type=float, default=0.05)
    parser.add_argument("--max-leaf-nodes", type=int, default=15)
    parser.add_argument("--min-samples-leaf", type=int, default=20)
    parser.add_argument("--l2-regularization", type=float, default=1.0)
    parser.add_argument("--random-seed", type=int, default=42)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    run_experiment(
        trades_path=args.trades,
        output_dir=args.output_dir,
        label=args.label,
        min_train_months=args.min_train_months,
        large_loss_threshold=args.large_loss_threshold,
        risk_quantiles=tuple(args.risk_quantiles),
        max_iter=args.max_iter,
        learning_rate=args.learning_rate,
        max_leaf_nodes=args.max_leaf_nodes,
        min_samples_leaf=args.min_samples_leaf,
        l2_regularization=args.l2_regularization,
        random_seed=args.random_seed,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
