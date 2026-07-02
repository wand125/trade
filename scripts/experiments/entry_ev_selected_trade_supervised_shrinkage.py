#!/usr/bin/env python3
"""Chronological supervised shrinkage diagnostics for selected entry-EV trades."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from trade_data.backtest import json_default, make_run_dir  # noqa: E402


DEFAULT_NUMERIC_FEATURES = (
    "pred_taken_ev",
    "pred_opposite_ev",
    "pred_best_ev",
    "pred_taken_side_confidence",
    "pred_opposite_side_confidence",
    "pred_side_confidence_gap",
    "pred_taken_entry_local_rank",
    "pred_taken_best_holding_minutes",
    "pred_taken_max_adverse_pnl",
    "pred_taken_wait_regret",
    "selected_pred_mlp_exit_minutes",
    "selected_time_exit_prob",
    "selected_loss_first_prob",
    "selected_fixed_60m_pred_pnl",
    "selected_fixed_240m_pred_pnl",
    "selected_fixed_720m_pred_pnl",
    "selected_direction_inversion_risk",
    "selected_direction_inversion_support",
    "selected_replacement_quality",
    "selected_replacement_quality_support",
    "selected_ev_overestimate_risk",
    "prior_exit_trade_count",
    "prior_exit_month_count",
    "prior_exit_loss_adjusted_pnl",
    "prior_exit_capture_ratio_mean",
    "prior_exit_regret_mean",
    "prior_exit_capture_shortfall_mean",
    "prior_same_side_oracle_rate",
    "prior_same_side_missed_loss_rate",
    "prior_low_exit_capture_rate",
    "prior_large_exit_regret_rate",
    "prior_exit_capture_failure_rate",
    "prior_exit_capture_support_weight",
    "prior_exit_capture_risk_score",
    "prior_global_trade_count",
    "prior_global_capture_count",
    "prior_global_capture_factor",
    "prior_context_capture_count",
    "prior_context_capture_factor",
    "prior_context_exit_capture_failure_rate",
    "prior_context_same_side_missed_loss_rate",
    "prior_context_large_exit_regret_rate",
    "prior_capture_support_weight",
    "global_executable_capture_factor",
    "context_executable_capture_factor",
    "executable_capture_factor",
    "pred_capture_calibrated_ev",
)

DEFAULT_CATEGORICAL_FEATURES = (
    "family",
    "role",
    "direction",
    "combined_regime",
    "session_regime",
    "selected_direction_inversion_source",
    "selected_replacement_quality_source",
    "selected_ev_overestimate_source",
    "prior_exit_capture_risk_bucket",
)

DEFAULT_THRESHOLDS = "-5,-2,-1,0,1,2,5"


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


def parse_float_csv(value: str) -> list[float]:
    return [float(part) for part in parse_csv(value)]


def read_trade_frames(paths: list[Path]) -> pd.DataFrame:
    if not paths:
        raise ValueError("at least one --trades path is required")
    frames = [pd.read_csv(path) for path in paths]
    return pd.concat(frames, ignore_index=True)


def numeric_series(frame: pd.DataFrame, column: str, default: float = np.nan) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=float)
    values = pd.to_numeric(frame[column], errors="coerce")
    return values.where(np.isfinite(values), default).fillna(default).astype(float)


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


def normalize_trade_frame(
    frame: pd.DataFrame,
    *,
    candidates: set[str],
    roles: set[str],
    months: set[str],
) -> pd.DataFrame:
    required = {
        "month",
        "candidate",
        "role",
        "direction",
        "entry_decision_timestamp",
        "adjusted_pnl",
        "pred_taken_ev",
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"trade frame missing columns: {', '.join(missing)}")
    output = frame.copy()
    output["month"] = output["month"].astype(str).str.slice(0, 7)
    output["candidate"] = output["candidate"].astype(str)
    output["role"] = output["role"].astype(str)
    output["family"] = text_series(output, "family")
    output["direction"] = output["direction"].astype(str).str.lower()
    output["entry_decision_timestamp"] = pd.to_datetime(
        output["entry_decision_timestamp"],
        utc=True,
    )
    output["adjusted_pnl"] = numeric_series(output, "adjusted_pnl", default=0.0)
    output["pred_taken_ev"] = numeric_series(output, "pred_taken_ev", default=np.nan)
    if candidates:
        output = output[output["candidate"].isin(candidates)].copy()
    if roles:
        output = output[output["role"].isin(roles)].copy()
    if months:
        output = output[output["month"].isin(months)].copy()
    if output.empty:
        raise ValueError("no trades remain after filters")
    return output.sort_values(["month", "entry_decision_timestamp"]).reset_index(drop=True)


def available_columns(frame: pd.DataFrame, requested: list[str], defaults: tuple[str, ...]) -> list[str]:
    columns = requested or list(defaults)
    return [column for column in columns if column in frame.columns]


def feature_frame(
    frame: pd.DataFrame,
    *,
    numeric_features: list[str],
    categorical_features: list[str],
) -> pd.DataFrame:
    output = pd.DataFrame(index=frame.index)
    for column in numeric_features:
        output[column] = numeric_series(frame, column, default=np.nan)
    for column in categorical_features:
        output[column] = text_series(frame, column)
    return output


def fit_category_maps(
    frame: pd.DataFrame,
    *,
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
        encoded[column] = (
            pd.to_numeric(frame[column], errors="coerce")
            .replace([np.inf, -np.inf], np.nan)
            .fillna(0.0)
            .astype(float)
        )
    for column in categorical_features:
        mapping = category_maps.get(column, {})
        encoded[f"{column}_code"] = (
            frame[column]
            .astype("string")
            .fillna("missing")
            .map(mapping)
            .fillna(-1)
            .astype(float)
        )
    return encoded


def target_values(
    frame: pd.DataFrame,
    *,
    target_mode: str,
    min_factor: float,
    max_factor: float,
) -> pd.Series:
    if target_mode == "pnl":
        return numeric_series(frame, "adjusted_pnl", default=0.0)
    if target_mode == "factor":
        raw = numeric_series(frame, "pred_taken_ev", default=np.nan).replace(0.0, np.nan)
        factor = numeric_series(frame, "adjusted_pnl", default=0.0) / raw
        return factor.replace([np.inf, -np.inf], np.nan).clip(min_factor, max_factor)
    raise ValueError(f"unknown target mode: {target_mode}")


def score_from_prediction(
    frame: pd.DataFrame,
    prediction: np.ndarray,
    *,
    target_mode: str,
) -> np.ndarray:
    if target_mode == "pnl":
        return prediction.astype(float)
    if target_mode == "factor":
        return numeric_series(frame, "pred_taken_ev", default=np.nan).to_numpy(dtype=float) * prediction
    raise ValueError(f"unknown target mode: {target_mode}")


def sample_training_rows(
    train: pd.DataFrame,
    *,
    max_train_rows: int,
    random_seed: int,
) -> pd.DataFrame:
    if max_train_rows <= 0 or len(train) <= max_train_rows:
        return train
    return train.sample(n=max_train_rows, random_state=random_seed).sort_index()


def fit_predict_fold(
    train: pd.DataFrame,
    target: pd.DataFrame,
    *,
    target_mode: str,
    numeric_features: list[str],
    categorical_features: list[str],
    max_iter: int,
    learning_rate: float,
    max_leaf_nodes: int,
    min_samples_leaf: int,
    l2_regularization: float,
    random_seed: int,
    max_train_rows: int,
    default_pnl: float,
    default_factor: float,
    min_factor: float,
    max_factor: float,
) -> tuple[np.ndarray, dict[str, Any]]:
    train_fit = sample_training_rows(
        train,
        max_train_rows=max_train_rows,
        random_seed=random_seed,
    )
    y = target_values(
        train_fit,
        target_mode=target_mode,
        min_factor=min_factor,
        max_factor=max_factor,
    ).dropna()
    train_fit = train_fit.loc[y.index].copy()
    fallback = float(default_pnl if target_mode == "pnl" else default_factor)
    if y.notna().any():
        fallback = float(y.mean())
    if target_mode == "factor":
        fallback = float(np.clip(fallback, min_factor, max_factor))

    if len(y) < 2 or y.nunique(dropna=True) < 2:
        return np.full(len(target), fallback, dtype=float), {
            "model_used": False,
            "train_rows_used": int(len(train_fit)),
            "train_target_mean": fallback,
            "train_target_std": float(y.std(ddof=0)) if len(y) else 0.0,
            "train_mae": 0.0,
            "train_rmse": 0.0,
            "train_r2": 0.0,
        }

    train_features = feature_frame(
        train_fit,
        numeric_features=numeric_features,
        categorical_features=categorical_features,
    )
    target_features = feature_frame(
        target,
        numeric_features=numeric_features,
        categorical_features=categorical_features,
    )
    category_maps = fit_category_maps(
        train_features,
        categorical_features=categorical_features,
    )
    x_train = encode_features(
        train_features,
        numeric_features=numeric_features,
        categorical_features=categorical_features,
        category_maps=category_maps,
    )
    x_target = encode_features(
        target_features,
        numeric_features=numeric_features,
        categorical_features=categorical_features,
        category_maps=category_maps,
    )
    model = HistGradientBoostingRegressor(
        max_iter=max_iter,
        learning_rate=learning_rate,
        max_leaf_nodes=max_leaf_nodes,
        min_samples_leaf=min_samples_leaf,
        l2_regularization=l2_regularization,
        random_state=random_seed,
        loss="squared_error",
    )
    model.fit(x_train.astype("float32").to_numpy(), y.to_numpy(dtype=float))
    train_prediction = model.predict(x_train.astype("float32").to_numpy())
    prediction = model.predict(x_target.astype("float32").to_numpy())
    if target_mode == "factor":
        train_prediction = np.clip(train_prediction, min_factor, max_factor)
        prediction = np.clip(prediction, min_factor, max_factor)
    return prediction.astype(float), {
        "model_used": True,
        "train_rows_used": int(len(train_fit)),
        "train_target_mean": float(y.mean()),
        "train_target_std": float(y.std(ddof=0)),
        "train_mae": float(mean_absolute_error(y, train_prediction)),
        "train_rmse": float(mean_squared_error(y, train_prediction) ** 0.5),
        "train_r2": float(r2_score(y, train_prediction)),
    }


def chronological_predictions(
    frame: pd.DataFrame,
    *,
    target_modes: list[str],
    numeric_features: list[str],
    categorical_features: list[str],
    min_train_months: int,
    min_train_rows: int,
    max_train_rows: int,
    max_iter: int,
    learning_rate: float,
    max_leaf_nodes: int,
    min_samples_leaf: int,
    l2_regularization: float,
    random_seed: int,
    default_pnl: float,
    default_factor: float,
    min_factor: float,
    max_factor: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    scored_frames: list[pd.DataFrame] = []
    fold_rows: list[dict[str, Any]] = []
    month_values = frame["month"].astype(str)
    periods = pd.PeriodIndex(month_values, freq="M")
    for target_mode in target_modes:
        scored = frame.copy()
        score_column = f"pred_supervised_{target_mode}_ev"
        raw_prediction_column = f"pred_supervised_{target_mode}_raw_target"
        scored[score_column] = np.nan
        scored[raw_prediction_column] = np.nan
        scored[f"pred_supervised_{target_mode}_model_used"] = False
        scored[f"pred_supervised_{target_mode}_train_rows"] = 0
        scored[f"pred_supervised_{target_mode}_train_months"] = 0

        for month in sorted(month_values.unique()):
            target_period = pd.Period(month, freq="M")
            train = frame[periods < target_period].copy()
            target = frame[month_values.eq(month)].copy()
            train_months = int(train["month"].nunique())
            if train_months >= min_train_months and len(train) >= min_train_rows:
                prediction, fit_info = fit_predict_fold(
                    train,
                    target,
                    target_mode=target_mode,
                    numeric_features=numeric_features,
                    categorical_features=categorical_features,
                    max_iter=max_iter,
                    learning_rate=learning_rate,
                    max_leaf_nodes=max_leaf_nodes,
                    min_samples_leaf=min_samples_leaf,
                    l2_regularization=l2_regularization,
                    random_seed=random_seed,
                    max_train_rows=max_train_rows,
                    default_pnl=default_pnl,
                    default_factor=default_factor,
                    min_factor=min_factor,
                    max_factor=max_factor,
                )
            else:
                prediction = np.full(
                    len(target),
                    default_pnl if target_mode == "pnl" else default_factor,
                    dtype=float,
                )
                fit_info = {
                    "model_used": False,
                    "train_rows_used": int(len(train)),
                    "train_target_mean": float(default_pnl if target_mode == "pnl" else default_factor),
                    "train_target_std": 0.0,
                    "train_mae": 0.0,
                    "train_rmse": 0.0,
                    "train_r2": 0.0,
                }
            score = score_from_prediction(target, prediction, target_mode=target_mode)
            scored.loc[target.index, score_column] = score
            scored.loc[target.index, raw_prediction_column] = prediction
            scored.loc[target.index, f"pred_supervised_{target_mode}_model_used"] = bool(
                fit_info["model_used"]
            )
            scored.loc[target.index, f"pred_supervised_{target_mode}_train_rows"] = int(
                len(train)
            )
            scored.loc[target.index, f"pred_supervised_{target_mode}_train_months"] = train_months
            actual = target["adjusted_pnl"].astype(float)
            valid = np.isfinite(score)
            fold_rows.append(
                {
                    "target_mode": target_mode,
                    "fold": month,
                    "target_rows": int(len(target)),
                    "train_rows": int(len(train)),
                    "train_months": train_months,
                    **fit_info,
                    "score_mean": float(np.nanmean(score)) if len(score) else np.nan,
                    "actual_mean": float(actual.mean()) if len(actual) else np.nan,
                    "score_mae": float(mean_absolute_error(actual[valid], score[valid]))
                    if bool(valid.any())
                    else np.nan,
                    "score_rmse": float(mean_squared_error(actual[valid], score[valid]) ** 0.5)
                    if bool(valid.any())
                    else np.nan,
                    "score_bias": float((score[valid] - actual[valid]).mean())
                    if bool(valid.any())
                    else np.nan,
                }
            )
        scored["supervised_target_mode"] = target_mode
        scored_frames.append(scored)
    return pd.concat(scored_frames, ignore_index=True), pd.DataFrame(fold_rows)


def safe_spearman(actual: pd.Series, score: pd.Series) -> float:
    valid = score.notna() & np.isfinite(score.astype(float))
    if int(valid.sum()) < 2:
        return float("nan")
    value = actual[valid].astype(float).corr(score[valid].astype(float), method="spearman")
    return float(value) if pd.notna(value) else float("nan")


def score_summary(frame: pd.DataFrame, score_columns: list[str], group_columns: list[str]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    grouped = [((), frame)] if not group_columns else frame.groupby(group_columns, dropna=False)
    for keys, group in grouped:
        if group_columns and not isinstance(keys, tuple):
            keys = (keys,)
        prefix = dict(zip(group_columns, keys, strict=True)) if group_columns else {}
        actual = group["adjusted_pnl"].astype(float)
        for score_column in score_columns:
            if score_column not in group.columns:
                continue
            score = pd.to_numeric(group[score_column], errors="coerce")
            valid = score.notna() & np.isfinite(score)
            if not bool(valid.any()):
                continue
            error = score[valid] - actual[valid]
            rows.append(
                {
                    **prefix,
                    "score": score_column,
                    "row_count": int(len(group)),
                    "valid_count": int(valid.sum()),
                    "total_pnl": float(actual.sum()),
                    "actual_mean": float(actual.mean()),
                    "score_mean": float(score[valid].mean()),
                    "bias": float(error.mean()),
                    "mae": float(error.abs().mean()),
                    "rmse": float((error.pow(2).mean()) ** 0.5),
                    "spearman": safe_spearman(actual, score),
                }
            )
    return pd.DataFrame(rows).sort_values(
        [*group_columns, "mae"] if group_columns else ["mae"],
    ).reset_index(drop=True)


def threshold_summary(
    frame: pd.DataFrame,
    *,
    score_columns: list[str],
    thresholds: list[float],
    group_columns: list[str],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    grouped = [((), frame)] if not group_columns else frame.groupby(group_columns, dropna=False)
    for keys, group in grouped:
        if group_columns and not isinstance(keys, tuple):
            keys = (keys,)
        prefix = dict(zip(group_columns, keys, strict=True)) if group_columns else {}
        actual = group["adjusted_pnl"].astype(float)
        total_pnl = float(actual.sum())
        total_count = int(len(group))
        loss_count = int(actual.lt(0.0).sum())
        for score_column in score_columns:
            if score_column not in group.columns:
                continue
            score = pd.to_numeric(group[score_column], errors="coerce")
            valid_score = score.notna() & np.isfinite(score)
            if not bool(valid_score.any()):
                continue
            for threshold in thresholds:
                flagged = score.lt(threshold) & valid_score
                flagged_actual = actual[flagged]
                flagged_pnl = float(flagged_actual.sum())
                flagged_count = int(flagged.sum())
                flagged_loss_count = int(flagged_actual.lt(0.0).sum())
                rows.append(
                    {
                        **prefix,
                        "score": score_column,
                        "threshold": float(threshold),
                        "total_trade_count": total_count,
                        "total_pnl": total_pnl,
                        "loss_trade_count": loss_count,
                        "flagged_trade_count": flagged_count,
                        "flagged_pnl": flagged_pnl,
                        "kept_pnl_if_removed": float(total_pnl - flagged_pnl),
                        "block_delta_if_removed": float(-flagged_pnl),
                        "flagged_trade_share": float(flagged_count / total_count)
                        if total_count
                        else 0.0,
                        "flagged_loss_count": flagged_loss_count,
                        "flagged_loss_precision": float(flagged_loss_count / flagged_count)
                        if flagged_count
                        else 0.0,
                        "loss_recall": float(flagged_loss_count / loss_count)
                        if loss_count
                        else 0.0,
                    }
                )
    return pd.DataFrame(rows).sort_values(
        ["block_delta_if_removed", "flagged_loss_count"],
        ascending=[False, False],
    ).reset_index(drop=True)


def add_baseline_scores(frame: pd.DataFrame) -> pd.DataFrame:
    output = frame.copy()
    output["score_raw_ev"] = numeric_series(output, "pred_taken_ev", default=np.nan)
    if "pred_capture_calibrated_ev" in output.columns:
        output["score_prior_capture_calibrated_ev"] = numeric_series(
            output,
            "pred_capture_calibrated_ev",
            default=np.nan,
        )
    return output


def build_diagnostics(args: argparse.Namespace) -> Path:
    target_modes = parse_csv(args.target_modes) or ["pnl", "factor"]
    frame = normalize_trade_frame(
        read_trade_frames(args.trades),
        candidates=set(parse_csv(args.candidates)),
        roles=set(parse_csv(args.roles)),
        months=set(parse_csv(args.months)),
    )
    frame = add_baseline_scores(frame)
    numeric_features = available_columns(
        frame,
        parse_csv(args.numeric_features),
        DEFAULT_NUMERIC_FEATURES,
    )
    categorical_features = available_columns(
        frame,
        parse_csv(args.categorical_features),
        DEFAULT_CATEGORICAL_FEATURES,
    )
    scored, fold_summary = chronological_predictions(
        frame,
        target_modes=target_modes,
        numeric_features=numeric_features,
        categorical_features=categorical_features,
        min_train_months=args.min_train_months,
        min_train_rows=args.min_train_rows,
        max_train_rows=args.max_train_rows,
        max_iter=args.max_iter,
        learning_rate=args.learning_rate,
        max_leaf_nodes=args.max_leaf_nodes,
        min_samples_leaf=args.min_samples_leaf,
        l2_regularization=args.l2_regularization,
        random_seed=args.random_seed,
        default_pnl=args.default_pnl,
        default_factor=args.default_factor,
        min_factor=args.min_factor,
        max_factor=args.max_factor,
    )
    baseline_columns = [column for column in ["score_raw_ev", "score_prior_capture_calibrated_ev"] if column in frame.columns]
    score_columns = baseline_columns + [
        f"pred_supervised_{target_mode}_ev" for target_mode in target_modes
    ]
    thresholds = parse_float_csv(args.thresholds)

    run_dir = make_run_dir(args.output_dir, args.label)
    scored.to_csv(run_dir / "selected_trade_supervised_shrinkage_predictions.csv", index=False)
    fold_summary.to_csv(run_dir / "selected_trade_supervised_shrinkage_folds.csv", index=False)
    overall_summary = score_summary(scored, score_columns, group_columns=["supervised_target_mode"])
    overall_summary.to_csv(run_dir / "selected_trade_supervised_shrinkage_score_summary.csv", index=False)
    role_summary = score_summary(
        scored,
        score_columns,
        group_columns=["supervised_target_mode", "role"],
    )
    role_summary.to_csv(run_dir / "selected_trade_supervised_shrinkage_role_summary.csv", index=False)
    threshold = threshold_summary(
        scored,
        score_columns=score_columns,
        thresholds=thresholds,
        group_columns=["supervised_target_mode"],
    )
    threshold.to_csv(run_dir / "selected_trade_supervised_shrinkage_threshold_summary.csv", index=False)
    role_threshold = threshold_summary(
        scored,
        score_columns=score_columns,
        thresholds=thresholds,
        group_columns=["supervised_target_mode", "role"],
    )
    role_threshold.to_csv(
        run_dir / "selected_trade_supervised_shrinkage_role_threshold_summary.csv",
        index=False,
    )
    config = {
        "trades": args.trades,
        "target_modes": target_modes,
        "numeric_features": numeric_features,
        "categorical_features": categorical_features,
        "candidates": args.candidates,
        "roles": args.roles,
        "months": args.months,
        "thresholds": thresholds,
        "min_train_months": args.min_train_months,
        "min_train_rows": args.min_train_rows,
        "max_train_rows": args.max_train_rows,
        "max_iter": args.max_iter,
        "learning_rate": args.learning_rate,
        "max_leaf_nodes": args.max_leaf_nodes,
        "min_samples_leaf": args.min_samples_leaf,
        "l2_regularization": args.l2_regularization,
        "default_pnl": args.default_pnl,
        "default_factor": args.default_factor,
        "min_factor": args.min_factor,
        "max_factor": args.max_factor,
        "random_seed": args.random_seed,
        "note": "chronological folds use only rows with month earlier than the target month",
    }
    (run_dir / "config.json").write_text(
        json.dumps(config, indent=2, default=local_json_default),
        encoding="utf-8",
    )

    print("Selected-trade supervised shrinkage score summary:")
    print(overall_summary.to_string(index=False))
    print("\nTop threshold rows:")
    print(
        threshold[
            [
                "supervised_target_mode",
                "score",
                "threshold",
                "flagged_trade_count",
                "flagged_pnl",
                "kept_pnl_if_removed",
                "block_delta_if_removed",
                "flagged_loss_precision",
                "loss_recall",
            ]
        ].head(args.top_n).to_string(index=False)
    )
    print(f"artifacts: {run_dir}")
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trades", type=Path, action="append", required=True)
    parser.add_argument("--target-modes", default="pnl,factor")
    parser.add_argument("--numeric-features", default="")
    parser.add_argument("--categorical-features", default="")
    parser.add_argument("--candidates", default="")
    parser.add_argument("--roles", default="")
    parser.add_argument("--months", default="")
    parser.add_argument("--thresholds", default=DEFAULT_THRESHOLDS)
    parser.add_argument("--min-train-months", type=int, default=2)
    parser.add_argument("--min-train-rows", type=int, default=30)
    parser.add_argument("--max-train-rows", type=int, default=0)
    parser.add_argument("--max-iter", type=int, default=60)
    parser.add_argument("--learning-rate", type=float, default=0.05)
    parser.add_argument("--max-leaf-nodes", type=int, default=7)
    parser.add_argument("--min-samples-leaf", type=int, default=20)
    parser.add_argument("--l2-regularization", type=float, default=0.10)
    parser.add_argument("--default-pnl", type=float, default=0.0)
    parser.add_argument("--default-factor", type=float, default=0.0)
    parser.add_argument("--min-factor", type=float, default=-1.0)
    parser.add_argument("--max-factor", type=float, default=1.0)
    parser.add_argument("--random-seed", type=int, default=42)
    parser.add_argument("--top-n", type=int, default=20)
    parser.add_argument("--output-dir", type=Path, default=Path("data/reports/backtests"))
    parser.add_argument("--label", default="entry_ev_selected_trade_supervised_shrinkage")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    build_diagnostics(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
