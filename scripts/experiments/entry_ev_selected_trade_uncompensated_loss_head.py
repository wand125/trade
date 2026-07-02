#!/usr/bin/env python3
"""Chronological head for uncompensated path-aware large-loss targets."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
SCRIPT_DIR = Path(__file__).resolve().parent
for path in (SRC, SCRIPT_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from trade_data.backtest import json_default, make_run_dir  # noqa: E402
from entry_ev_selected_trade_calibration_diagnostics import parse_csv  # noqa: E402


BASE_NUMERIC_FEATURES = (
    "score",
    "raw_score",
    "pred_taken_ev",
    "selected_loss_first_prob",
    "pred_side_confidence_gap",
    "pred_taken_entry_local_rank",
    "train_rows",
    "train_months",
)

PRIOR_NUMERIC_FEATURES = (
    "prior_trade_count",
    "prior_month_count",
    "prior_total_pnl",
    "prior_avg_pnl",
    "prior_loss_rate",
    "prior_large_loss_rate",
    "prior_bias_mean",
    "prior_mae_mean",
    "prior_overestimate_rate",
    "prior_overestimate_mean",
    "prior_residual_pressure",
)

RISK_NUMERIC_FEATURES = (
    "pred_large_loss_prob",
)

DEFAULT_CATEGORICAL_FEATURES = (
    "role",
    "direction",
    "combined_regime",
    "session_regime",
    "group_key",
)

DEFAULT_THRESHOLDS = "0.05,0.10,0.15,0.20,0.30,0.40"
DEFAULT_QUANTILES = "0.70,0.80,0.90,0.95"


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


def parse_float_csv(value: str) -> list[float]:
    return [float(part) for part in parse_csv(value)]


def parse_semicolon(value: str) -> list[str]:
    return [part.strip() for part in str(value).split(";") if part.strip()]


def read_frames(paths: list[Path]) -> pd.DataFrame:
    if not paths:
        raise ValueError("at least one --path-rows path is required")
    return pd.concat([pd.read_csv(path) for path in paths], ignore_index=True)


def numeric_series(frame: pd.DataFrame, column: str, default: float = np.nan) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=float)
    values = pd.to_numeric(frame[column], errors="coerce")
    return values.where(np.isfinite(values), default).fillna(default).astype(float)


def bool_series(frame: pd.DataFrame, column: str, default: bool = False) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=bool)
    series = frame[column]
    if pd.api.types.is_bool_dtype(series):
        return series.fillna(default).astype(bool)
    if pd.api.types.is_numeric_dtype(series):
        return series.fillna(float(default)).astype(float).ne(0.0)
    return series.astype(str).str.lower().str.strip().isin({"true", "1", "yes", "y"})


def text_series(frame: pd.DataFrame, column: str, default: str = "missing") -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype="string")
    return (
        frame[column]
        .astype("string")
        .fillna(default)
        .str.strip()
        .replace({"": default, "nan": default, "None": default})
    )


def normalize_path_rows(
    frame: pd.DataFrame,
    *,
    target_column: str,
    target_modes: set[str],
    group_specs: set[str],
    source_large_loss_feature_sets: set[str],
) -> pd.DataFrame:
    required = {
        "supervised_target_mode",
        "group_spec",
        "large_loss_feature_set",
        "month",
        "adjusted_pnl",
        "is_large_loss",
        target_column,
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"path row frame missing columns: {', '.join(missing)}")
    output = frame.copy()
    output["supervised_target_mode"] = text_series(output, "supervised_target_mode")
    output["group_spec"] = text_series(output, "group_spec")
    output["large_loss_feature_set"] = text_series(output, "large_loss_feature_set")
    output["month"] = text_series(output, "month").str.slice(0, 7)
    if target_modes:
        output = output[output["supervised_target_mode"].isin(target_modes)].copy()
    if group_specs:
        output = output[output["group_spec"].isin(group_specs)].copy()
    if source_large_loss_feature_sets:
        output = output[
            output["large_loss_feature_set"].isin(source_large_loss_feature_sets)
        ].copy()
    if output.empty:
        raise ValueError("no rows remain after filters")

    for column in [
        "role",
        "direction",
        "combined_regime",
        "session_regime",
        "group_key",
        "source",
        "family",
        "context_key",
    ]:
        output[column] = text_series(output, column)
    for column in [
        "adjusted_pnl",
        "score",
        "raw_score",
        "pred_taken_ev",
        "selected_loss_first_prob",
        "pred_side_confidence_gap",
        "pred_taken_entry_local_rank",
        "train_rows",
        "train_months",
        *PRIOR_NUMERIC_FEATURES,
        *RISK_NUMERIC_FEATURES,
    ]:
        output[column] = numeric_series(output, column)
    output["is_loss"] = bool_series(output, "is_loss")
    output["is_large_loss"] = bool_series(output, "is_large_loss")
    output["uncompensated_loss_target"] = bool_series(output, target_column)
    return output.sort_values(
        [
            "supervised_target_mode",
            "group_spec",
            "large_loss_feature_set",
            "month",
        ]
    ).reset_index(drop=True)


def build_feature_sets(
    frame: pd.DataFrame,
    *,
    numeric_features: list[str],
    prior_numeric_features: list[str],
    risk_numeric_features: list[str],
) -> dict[str, list[str]]:
    base = [column for column in numeric_features if column in frame.columns]
    prior = [column for column in prior_numeric_features if column in frame.columns]
    risk = [column for column in risk_numeric_features if column in frame.columns]
    return {
        "base": base,
        "base_prior": [*base, *prior],
        "base_risk": [*base, *risk],
        "base_prior_risk": [*base, *prior, *risk],
    }


def fit_category_maps(
    frame: pd.DataFrame,
    categorical_features: list[str],
) -> dict[str, dict[str, int]]:
    maps: dict[str, dict[str, int]] = {}
    for column in categorical_features:
        values = sorted(str(value) for value in frame[column].astype(str).unique())
        maps[column] = {value: index for index, value in enumerate(values)}
    return maps


def encode_features(
    frame: pd.DataFrame,
    *,
    numeric_features: list[str],
    categorical_features: list[str],
    category_maps: dict[str, dict[str, int]],
) -> pd.DataFrame:
    encoded = pd.DataFrame(index=frame.index)
    for column in numeric_features:
        encoded[column] = numeric_series(frame, column, default=np.nan)
    for column in categorical_features:
        mapping = category_maps[column]
        encoded[f"{column}__code"] = (
            frame[column].astype(str).map(mapping).fillna(-1).astype(float)
        )
    return encoded


def train_predict_fold(
    train: pd.DataFrame,
    test: pd.DataFrame,
    *,
    numeric_features: list[str],
    categorical_features: list[str],
    max_iter: int,
    learning_rate: float,
    max_leaf_nodes: int,
    min_samples_leaf: int,
    l2_regularization: float,
    random_seed: int,
) -> tuple[np.ndarray, bool]:
    y_train = train["uncompensated_loss_target"].astype(int)
    if y_train.nunique() < 2:
        default = float(y_train.mean()) if len(y_train) else 0.0
        return np.full(len(test), default, dtype=float), False
    maps = fit_category_maps(train, categorical_features)
    x_train = encode_features(
        train,
        numeric_features=numeric_features,
        categorical_features=categorical_features,
        category_maps=maps,
    )
    x_test = encode_features(
        test,
        numeric_features=numeric_features,
        categorical_features=categorical_features,
        category_maps=maps,
    )
    model = HistGradientBoostingClassifier(
        max_iter=max_iter,
        learning_rate=learning_rate,
        max_leaf_nodes=max_leaf_nodes,
        min_samples_leaf=min_samples_leaf,
        l2_regularization=l2_regularization,
        random_state=random_seed,
    )
    model.fit(x_train, y_train)
    return model.predict_proba(x_test)[:, 1], True


def chronological_predictions(
    frame: pd.DataFrame,
    *,
    feature_sets: dict[str, list[str]],
    categorical_features: list[str],
    min_train_months: int,
    min_train_rows: int,
    max_iter: int,
    learning_rate: float,
    max_leaf_nodes: int,
    min_samples_leaf: int,
    l2_regularization: float,
    random_seed: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    prediction_rows: list[pd.DataFrame] = []
    fold_rows: list[dict[str, Any]] = []
    group_columns = ["supervised_target_mode", "group_spec", "large_loss_feature_set"]
    for keys, group in frame.groupby(group_columns, dropna=False):
        mode, group_spec, source_feature_set = keys
        months = sorted(group["month"].astype(str).unique())
        for feature_set_name, numeric_features in feature_sets.items():
            for month in months:
                train = group[group["month"].astype(str) < month].copy()
                test = group[group["month"].astype(str).eq(month)].copy()
                if test.empty:
                    continue
                train_months = int(train["month"].nunique()) if not train.empty else 0
                can_train = len(train) >= min_train_rows and train_months >= min_train_months
                if can_train:
                    preds, model_used = train_predict_fold(
                        train,
                        test,
                        numeric_features=numeric_features,
                        categorical_features=categorical_features,
                        max_iter=max_iter,
                        learning_rate=learning_rate,
                        max_leaf_nodes=max_leaf_nodes,
                        min_samples_leaf=min_samples_leaf,
                        l2_regularization=l2_regularization,
                        random_seed=random_seed,
                    )
                else:
                    default = (
                        float(train["uncompensated_loss_target"].mean())
                        if len(train)
                        else 0.0
                    )
                    preds = np.full(len(test), default, dtype=float)
                    model_used = False
                scored = test.copy()
                scored["uncompensated_feature_set"] = feature_set_name
                scored["pred_uncompensated_loss_prob"] = preds
                scored["uncompensated_model_used"] = bool(model_used)
                scored["uncompensated_train_rows"] = int(len(train))
                scored["uncompensated_train_months"] = train_months
                prediction_rows.append(scored)
                fold_rows.append(
                    {
                        "supervised_target_mode": mode,
                        "group_spec": group_spec,
                        "source_large_loss_feature_set": source_feature_set,
                        "feature_set": feature_set_name,
                        "fold": month,
                        "target_rows": int(len(test)),
                        "train_rows": int(len(train)),
                        "train_months": train_months,
                        "positive_train_rows": int(
                            train["uncompensated_loss_target"].sum()
                        )
                        if len(train)
                        else 0,
                        "model_used": bool(model_used),
                        "target_rate": float(test["uncompensated_loss_target"].mean()),
                        "pred_mean": float(np.mean(preds)) if len(preds) else 0.0,
                    }
                )
    if not prediction_rows:
        raise ValueError("no predictions were generated")
    return pd.concat(prediction_rows, ignore_index=True), pd.DataFrame(fold_rows)


def safe_auc(y_true: pd.Series, y_score: pd.Series) -> float:
    if y_true.nunique() < 2:
        return float("nan")
    return float(roc_auc_score(y_true.astype(int), y_score.astype(float)))


def safe_average_precision(y_true: pd.Series, y_score: pd.Series) -> float:
    if y_true.nunique() < 2:
        return float("nan")
    return float(average_precision_score(y_true.astype(int), y_score.astype(float)))


def score_summary(frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    group_columns = [
        "supervised_target_mode",
        "group_spec",
        "large_loss_feature_set",
        "uncompensated_feature_set",
    ]
    for keys, group in frame.groupby(group_columns, dropna=False):
        mode, group_spec, source_feature_set, feature_set = keys
        y = group["uncompensated_loss_target"].astype(int)
        pred = group["pred_uncompensated_loss_prob"].astype(float)
        rows.append(
            {
                "supervised_target_mode": mode,
                "group_spec": group_spec,
                "source_large_loss_feature_set": source_feature_set,
                "feature_set": feature_set,
                "row_count": int(len(group)),
                "total_pnl": float(group["adjusted_pnl"].sum()),
                "target_count": int(y.sum()),
                "target_rate": float(y.mean()) if len(y) else 0.0,
                "pred_mean": float(pred.mean()) if len(pred) else 0.0,
                "auc": safe_auc(y, pred),
                "average_precision": safe_average_precision(y, pred),
                "brier": float(brier_score_loss(y, pred)) if len(group) else float("nan"),
                "model_used_rate": float(group["uncompensated_model_used"].mean())
                if len(group)
                else 0.0,
            }
        )
    return pd.DataFrame(rows).sort_values(
        ["average_precision", "auc"],
        ascending=[False, False],
    )


def summarize_flagged(frame: pd.DataFrame, mask: pd.Series) -> dict[str, Any]:
    flagged = frame[mask]
    targets = frame[frame["uncompensated_loss_target"].fillna(False).astype(bool)]
    flagged_targets = flagged[
        flagged["uncompensated_loss_target"].fillna(False).astype(bool)
    ]
    large_losses = frame[frame["is_large_loss"].fillna(False).astype(bool)]
    flagged_large = flagged[flagged["is_large_loss"].fillna(False).astype(bool)]
    losses = frame[frame["is_loss"].fillna(False).astype(bool)]
    flagged_losses = flagged[flagged["is_loss"].fillna(False).astype(bool)]
    total_pnl = float(frame["adjusted_pnl"].sum()) if len(frame) else 0.0
    flagged_pnl = float(flagged["adjusted_pnl"].sum()) if len(flagged) else 0.0
    return {
        "total_trade_count": int(len(frame)),
        "total_pnl": total_pnl,
        "target_count": int(len(targets)),
        "large_loss_count": int(len(large_losses)),
        "loss_count": int(len(losses)),
        "flagged_trade_count": int(len(flagged)),
        "flagged_trade_share": float(len(flagged) / len(frame)) if len(frame) else 0.0,
        "flagged_pnl": flagged_pnl,
        "kept_pnl_if_removed": total_pnl - flagged_pnl,
        "block_delta_if_removed": -flagged_pnl,
        "flagged_loss_count": int(len(flagged_losses)),
        "flagged_loss_precision": float(len(flagged_losses) / len(flagged))
        if len(flagged)
        else 0.0,
        "loss_recall": float(len(flagged_losses) / len(losses)) if len(losses) else 0.0,
        "flagged_large_loss_count": int(len(flagged_large)),
        "large_loss_recall": float(len(flagged_large) / len(large_losses))
        if len(large_losses)
        else 0.0,
        "flagged_target_count": int(len(flagged_targets)),
        "flagged_target_precision": float(len(flagged_targets) / len(flagged))
        if len(flagged)
        else 0.0,
        "target_recall": float(len(flagged_targets) / len(targets)) if len(targets) else 0.0,
        "flagged_pred_mean": float(flagged["pred_uncompensated_loss_prob"].mean())
        if len(flagged)
        else 0.0,
    }


def threshold_summary(
    frame: pd.DataFrame,
    *,
    thresholds: list[float],
    quantiles: list[float],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    group_columns = [
        "supervised_target_mode",
        "group_spec",
        "large_loss_feature_set",
        "uncompensated_feature_set",
    ]
    for keys, group in frame.groupby(group_columns, dropna=False):
        mode, group_spec, source_feature_set, feature_set = keys
        pred = group["pred_uncompensated_loss_prob"].astype(float)
        threshold_items = [(f"prob_ge_{value:g}", value) for value in thresholds]
        for quantile in quantiles:
            threshold_items.append((f"top_q{int(quantile * 100)}", float(pred.quantile(quantile))))
        for label, threshold in threshold_items:
            mask = pred.ge(threshold)
            row: dict[str, Any] = {
                "supervised_target_mode": mode,
                "group_spec": group_spec,
                "source_large_loss_feature_set": source_feature_set,
                "feature_set": feature_set,
                "threshold_label": label,
                "threshold": threshold,
            }
            row.update(summarize_flagged(group, mask))
            rows.append(row)
    return pd.DataFrame(rows).sort_values(
        ["block_delta_if_removed", "flagged_target_count", "flagged_trade_count"],
        ascending=[False, False, False],
    )


def worst_rows(frame: pd.DataFrame, *, top_n: int) -> pd.DataFrame:
    columns = [
        "supervised_target_mode",
        "group_spec",
        "large_loss_feature_set",
        "uncompensated_feature_set",
        "month",
        "role",
        "direction",
        "combined_regime",
        "session_regime",
        "context_key",
        "adjusted_pnl",
        "is_large_loss",
        "large_loss_uncompensated_by_context",
        "uncompensated_loss_target",
        "pred_large_loss_prob",
        "pred_uncompensated_loss_prob",
        "score",
        "prior_residual_pressure",
        "context_month_total_pnl",
    ]
    available = [column for column in columns if column in frame.columns]
    return frame.sort_values(
        ["pred_uncompensated_loss_prob", "adjusted_pnl"],
        ascending=[False, True],
    )[available].head(top_n)


def build_diagnostics(args: argparse.Namespace) -> Path:
    raw = read_frames(args.path_rows)
    normalized = normalize_path_rows(
        raw,
        target_column=args.target_column,
        target_modes=set(parse_csv(args.target_modes)),
        group_specs=set(parse_semicolon(args.group_specs)),
        source_large_loss_feature_sets=set(parse_csv(args.source_large_loss_feature_sets)),
    )
    numeric_features = parse_csv(args.numeric_features) or list(BASE_NUMERIC_FEATURES)
    prior_numeric_features = parse_csv(args.prior_numeric_features) or list(
        PRIOR_NUMERIC_FEATURES
    )
    risk_numeric_features = parse_csv(args.risk_numeric_features) or list(
        RISK_NUMERIC_FEATURES
    )
    categorical_features = [
        column
        for column in (parse_csv(args.categorical_features) or list(DEFAULT_CATEGORICAL_FEATURES))
        if column in normalized.columns
    ]
    feature_sets = build_feature_sets(
        normalized,
        numeric_features=numeric_features,
        prior_numeric_features=prior_numeric_features,
        risk_numeric_features=risk_numeric_features,
    )
    predictions, folds = chronological_predictions(
        normalized,
        feature_sets=feature_sets,
        categorical_features=categorical_features,
        min_train_months=args.min_train_months,
        min_train_rows=args.min_train_rows,
        max_iter=args.max_iter,
        learning_rate=args.learning_rate,
        max_leaf_nodes=args.max_leaf_nodes,
        min_samples_leaf=args.min_samples_leaf,
        l2_regularization=args.l2_regularization,
        random_seed=args.random_seed,
    )
    score = score_summary(predictions)
    thresholds = threshold_summary(
        predictions,
        thresholds=parse_float_csv(args.thresholds),
        quantiles=parse_float_csv(args.quantiles),
    )
    worst = worst_rows(predictions, top_n=args.top_n)

    run_dir = make_run_dir(args.output_dir, args.label)
    predictions.to_csv(
        run_dir / "selected_trade_uncompensated_loss_head_predictions.csv",
        index=False,
    )
    folds.to_csv(run_dir / "selected_trade_uncompensated_loss_head_folds.csv", index=False)
    score.to_csv(
        run_dir / "selected_trade_uncompensated_loss_head_score_summary.csv",
        index=False,
    )
    thresholds.to_csv(
        run_dir / "selected_trade_uncompensated_loss_head_threshold_summary.csv",
        index=False,
    )
    worst.to_csv(
        run_dir / "selected_trade_uncompensated_loss_head_worst_rows.csv",
        index=False,
    )
    config = {
        "path_rows": args.path_rows,
        "target_column": args.target_column,
        "target_modes": args.target_modes,
        "group_specs": args.group_specs,
        "source_large_loss_feature_sets": args.source_large_loss_feature_sets,
        "numeric_features": numeric_features,
        "prior_numeric_features": prior_numeric_features,
        "risk_numeric_features": risk_numeric_features,
        "categorical_features": categorical_features,
        "thresholds": args.thresholds,
        "quantiles": args.quantiles,
        "min_train_months": args.min_train_months,
        "min_train_rows": args.min_train_rows,
        "max_iter": args.max_iter,
        "learning_rate": args.learning_rate,
        "max_leaf_nodes": args.max_leaf_nodes,
        "min_samples_leaf": args.min_samples_leaf,
        "l2_regularization": args.l2_regularization,
        "random_seed": args.random_seed,
    }
    (run_dir / "config.json").write_text(
        json.dumps(config, indent=2, sort_keys=True, default=local_json_default),
        encoding="utf-8",
    )

    print(f"Wrote uncompensated-loss head diagnostics to {run_dir}")
    print("\nScore summary:")
    print(score.to_string(index=False))
    print("\nTop threshold summary:")
    print(thresholds.head(args.top_n).to_string(index=False))
    print("\nTop predicted target rows:")
    print(worst.head(args.top_n).to_string(index=False))
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path-rows", type=Path, action="append", required=True)
    parser.add_argument("--label", default="entry_ev_uncompensated_loss_head")
    parser.add_argument("--output-dir", type=Path, default=Path("data/reports/backtests"))
    parser.add_argument("--target-column", default="large_loss_uncompensated_by_context")
    parser.add_argument("--target-modes", default="factor,pnl")
    parser.add_argument("--group-specs", default="direction,combined_regime,session_regime")
    parser.add_argument("--source-large-loss-feature-sets", default="base,base_prior")
    parser.add_argument("--numeric-features", default="")
    parser.add_argument("--prior-numeric-features", default="")
    parser.add_argument("--risk-numeric-features", default="")
    parser.add_argument("--categorical-features", default="")
    parser.add_argument("--thresholds", default=DEFAULT_THRESHOLDS)
    parser.add_argument("--quantiles", default=DEFAULT_QUANTILES)
    parser.add_argument("--min-train-months", type=int, default=3)
    parser.add_argument("--min-train-rows", type=int, default=30)
    parser.add_argument("--max-iter", type=int, default=80)
    parser.add_argument("--learning-rate", type=float, default=0.05)
    parser.add_argument("--max-leaf-nodes", type=int, default=7)
    parser.add_argument("--min-samples-leaf", type=int, default=20)
    parser.add_argument("--l2-regularization", type=float, default=0.10)
    parser.add_argument("--random-seed", type=int, default=42)
    parser.add_argument("--top-n", type=int, default=40)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    build_diagnostics(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
