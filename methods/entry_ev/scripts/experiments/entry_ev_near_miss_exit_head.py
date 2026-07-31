#!/usr/bin/env python3
"""Chronological exit-viability and horizon head for near-miss candidates."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, roc_auc_score

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from trade_data.backtest import json_default, make_run_dir  # noqa: E402


DEFAULT_HORIZONS = "60,240,720"
DEFAULT_PROB_THRESHOLDS = "0.40,0.50,0.60,0.70"
DEFAULT_EV_THRESHOLDS = "-5,0,2,5"
DEFAULT_TRAIN_UNIVERSE = "all"
DEFAULT_NUMERIC_FEATURES = (
    "side_score",
    "opposite_score",
    "side_margin",
    "score_pct",
    "side_margin_pct",
    "entry_rank_pct",
    "side_pred_holding_minutes",
    "side_entry_rank",
    "strict_failed_stage_count",
    "entry_hour",
    "strict_side_specific",
    "relaxed_side_specific",
    "one_failed_strict_stage",
    "holding_ok",
    "pred_fixed_available",
    "pred_fixed_60m_adjusted_pnl",
    "pred_fixed_240m_adjusted_pnl",
    "pred_fixed_720m_adjusted_pnl",
    "pred_fixed_best_adjusted_pnl",
    "pred_fixed_best_horizon_minutes",
    "pred_exit_event_minutes",
    "pred_exit_event_time_bin_expected_minutes",
    "pred_exit_event_prob_0",
    "pred_exit_event_prob_1",
    "pred_exit_event_prob_2",
    "pred_mlp_exit_event_minutes",
)
DEFAULT_CATEGORICAL_FEATURES = (
    "family",
    "role",
    "side",
    "needed_side",
    "combined_regime",
    "session_regime",
    "near_miss_bucket",
)
DEFAULT_GROUP_SPECS = (
    "row_scope;selection_bucket;near_miss_bucket;role;family;month;side;"
    "family,month;role,month;side,combined_regime,session_regime;"
    "near_miss_bucket,side"
)
REQUIRED_COLUMNS = {
    "month",
    "decision_timestamp",
    "target_fixed_executable",
    "target_fixed_best_adjusted_pnl",
    "target_fixed_best_horizon_minutes",
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


def parse_int_csv(value: str) -> list[int]:
    return [int(part) for part in parse_csv(value)]


def parse_float_csv(value: str) -> list[float]:
    return [float(part) for part in parse_csv(value)]


def parse_group_specs(value: str) -> list[list[str]]:
    specs: list[list[str]] = []
    for raw_spec in value.split(";"):
        columns = parse_csv(raw_spec)
        if columns:
            specs.append(columns)
    return specs


def numeric_series(frame: pd.DataFrame, column: str, default: float = np.nan) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=float)
    values = pd.to_numeric(frame[column], errors="coerce")
    return values.replace([np.inf, -np.inf], np.nan).fillna(default).astype(float)


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


def available_features(
    frame: pd.DataFrame,
    requested: list[str],
    defaults: tuple[str, ...],
) -> list[str]:
    columns = requested or list(defaults)
    return [column for column in columns if column in frame.columns]


def normalize_rows(frame: pd.DataFrame, *, horizons: list[int]) -> pd.DataFrame:
    missing = sorted(REQUIRED_COLUMNS - set(frame.columns))
    if missing:
        raise ValueError(f"near-miss rows missing columns: {', '.join(missing)}")
    missing_horizons = [
        f"side_fixed_{horizon}m_adjusted_pnl"
        for horizon in horizons
        if f"side_fixed_{horizon}m_adjusted_pnl" not in frame.columns
    ]
    if missing_horizons:
        raise ValueError(
            "near-miss rows missing horizon columns: " + ", ".join(missing_horizons)
        )
    output = frame.copy()
    output["month"] = output["month"].astype(str).str.slice(0, 7)
    output["decision_timestamp"] = pd.to_datetime(
        output["decision_timestamp"],
        utc=True,
        errors="coerce",
    )
    for column in [
        "family",
        "role",
        "side",
        "needed_side",
        "combined_regime",
        "session_regime",
        "near_miss_bucket",
        "row_scope",
        "selection_bucket",
    ]:
        output[column] = text_series(output, column)
    for column in [
        "target_fixed_best_adjusted_pnl",
        "target_fixed_best_horizon_minutes",
        "target_oracle_gap_vs_fixed_best",
        "side_best_adjusted_pnl",
        *[f"side_fixed_{horizon}m_adjusted_pnl" for horizon in horizons],
        *DEFAULT_NUMERIC_FEATURES,
    ]:
        if column in output.columns:
            output[column] = numeric_series(output, column)
    for column in [
        "target_fixed_executable",
        "target_fixed60_loss_rescuable",
        "stateful_available",
        "selected_any",
        "strict_side_specific",
        "relaxed_side_specific",
        "one_failed_strict_stage",
        "holding_ok",
        "pred_fixed_available",
    ]:
        output[column] = bool_series(output, column)
    return output.sort_values(["month", "decision_timestamp"]).reset_index(drop=True)


def train_universe_mask(frame: pd.DataFrame, universe: str) -> pd.Series:
    if universe == "all":
        return pd.Series(True, index=frame.index, dtype=bool)
    if universe == "available":
        return frame["row_scope"].astype(str).eq("available_candidates")
    if universe == "greedy_selected":
        return frame["row_scope"].astype(str).eq("greedy_selected")
    if universe == "one_failed_strict_stage":
        return frame["near_miss_bucket"].astype(str).eq("one_failed_strict_stage")
    raise ValueError(f"unknown train universe: {universe}")


def make_feature_frame(
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
    output = pd.DataFrame(index=frame.index)
    for column in numeric_features:
        output[column] = (
            pd.to_numeric(frame[column], errors="coerce")
            .replace([np.inf, -np.inf], np.nan)
            .fillna(0.0)
            .astype(float)
        )
    for column in categorical_features:
        mapping = category_maps.get(column, {})
        output[f"{column}_code"] = (
            frame[column]
            .astype("string")
            .fillna("missing")
            .map(mapping)
            .fillna(-1)
            .astype(float)
        )
    return output


def encoded_train_target(
    train: pd.DataFrame,
    target: pd.DataFrame,
    *,
    numeric_features: list[str],
    categorical_features: list[str],
) -> tuple[np.ndarray, np.ndarray]:
    train_features = make_feature_frame(
        train,
        numeric_features=numeric_features,
        categorical_features=categorical_features,
    )
    target_features = make_feature_frame(
        target,
        numeric_features=numeric_features,
        categorical_features=categorical_features,
    )
    category_maps = fit_category_maps(train_features, categorical_features)
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
    return (
        x_train.astype("float32").to_numpy(),
        x_target.astype("float32").to_numpy(),
    )


def fit_predict_classifier(
    train: pd.DataFrame,
    target: pd.DataFrame,
    *,
    target_column: str,
    numeric_features: list[str],
    categorical_features: list[str],
    max_iter: int,
    learning_rate: float,
    l2_regularization: float,
    max_leaf_nodes: int,
    random_state: int,
) -> tuple[np.ndarray, dict[str, Any]]:
    y = bool_series(train, target_column)
    fallback = float(y.mean()) if len(y) else 0.0
    if len(train) < 3 or y.nunique(dropna=True) < 2:
        return np.full(len(target), fallback, dtype=float), {
            "model_used": False,
            "train_rows_used": int(len(train)),
            "train_target_mean": fallback,
            "train_target_std": float(y.astype(float).std(ddof=0)) if len(y) else 0.0,
        }
    x_train, x_target = encoded_train_target(
        train,
        target,
        numeric_features=numeric_features,
        categorical_features=categorical_features,
    )
    model = HistGradientBoostingClassifier(
        max_iter=max_iter,
        learning_rate=learning_rate,
        l2_regularization=l2_regularization,
        max_leaf_nodes=max_leaf_nodes,
        random_state=random_state,
    )
    model.fit(x_train, y.astype(int).to_numpy())
    return model.predict_proba(x_target)[:, 1].astype(float), {
        "model_used": True,
        "train_rows_used": int(len(train)),
        "train_target_mean": fallback,
        "train_target_std": float(y.astype(float).std(ddof=0)),
    }


def fit_predict_regressor(
    train: pd.DataFrame,
    target: pd.DataFrame,
    *,
    target_column: str,
    numeric_features: list[str],
    categorical_features: list[str],
    max_iter: int,
    learning_rate: float,
    l2_regularization: float,
    max_leaf_nodes: int,
    random_state: int,
) -> tuple[np.ndarray, dict[str, Any]]:
    y = numeric_series(train, target_column, default=np.nan)
    valid = y.notna()
    train_fit = train[valid].copy()
    y_fit = y[valid]
    fallback = float(y_fit.mean()) if len(y_fit) else 0.0
    if len(train_fit) < 3 or y_fit.std(ddof=0) <= 1e-12:
        return np.full(len(target), fallback, dtype=float), {
            "model_used": False,
            "train_rows_used": int(len(train_fit)),
            "train_target_mean": fallback,
            "train_target_std": float(y_fit.std(ddof=0)) if len(y_fit) else 0.0,
        }
    x_train, x_target = encoded_train_target(
        train_fit,
        target,
        numeric_features=numeric_features,
        categorical_features=categorical_features,
    )
    model = HistGradientBoostingRegressor(
        max_iter=max_iter,
        learning_rate=learning_rate,
        l2_regularization=l2_regularization,
        max_leaf_nodes=max_leaf_nodes,
        random_state=random_state,
    )
    model.fit(x_train, y_fit.astype(float).to_numpy())
    return model.predict(x_target).astype(float), {
        "model_used": True,
        "train_rows_used": int(len(train_fit)),
        "train_target_mean": fallback,
        "train_target_std": float(y_fit.std(ddof=0)),
    }


def chronological_head_predictions(
    frame: pd.DataFrame,
    *,
    horizons: list[int],
    train_universe: str,
    min_train_months: int,
    min_train_rows: int,
    numeric_features: list[str],
    categorical_features: list[str],
    max_iter: int,
    learning_rate: float,
    l2_regularization: float,
    max_leaf_nodes: int,
    random_state: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    scored = frame.copy()
    periods = pd.PeriodIndex(scored["month"].astype(str), freq="M")
    months = sorted(scored["month"].astype(str).unique().tolist())
    base_train_mask = train_universe_mask(scored, train_universe)
    fold_rows: list[dict[str, Any]] = []
    scored["pred_exit_viability_prob"] = 0.0
    scored["pred_exit_best_fixed_pnl"] = 0.0
    scored["pred_exit_head_any_model_used"] = False
    scored["pred_exit_viability_model_used"] = False
    scored["pred_exit_best_pnl_model_used"] = False
    for horizon in horizons:
        scored[f"pred_exit_head_fixed_{horizon}m_pnl"] = 0.0
        scored[f"pred_exit_head_fixed_{horizon}m_model_used"] = False

    for month in months:
        target_period = pd.Period(month, freq="M")
        train = scored[(periods < target_period) & base_train_mask].copy()
        target = scored[scored["month"].eq(month)].copy()
        train_months = int(train["month"].nunique()) if len(train) else 0
        can_fit = train_months >= min_train_months and len(train) >= min_train_rows

        target_specs = [
            ("viability", "target_fixed_executable", "pred_exit_viability_prob", "classifier"),
            ("fixed_best", "target_fixed_best_adjusted_pnl", "pred_exit_best_fixed_pnl", "regressor"),
            *[
                (
                    f"fixed_{horizon}m",
                    f"side_fixed_{horizon}m_adjusted_pnl",
                    f"pred_exit_head_fixed_{horizon}m_pnl",
                    "regressor",
                )
                for horizon in horizons
            ],
        ]
        used_any = False
        for target_name, target_column, prediction_column, model_kind in target_specs:
            if can_fit:
                if model_kind == "classifier":
                    pred, fit_info = fit_predict_classifier(
                        train,
                        target,
                        target_column=target_column,
                        numeric_features=numeric_features,
                        categorical_features=categorical_features,
                        max_iter=max_iter,
                        learning_rate=learning_rate,
                        l2_regularization=l2_regularization,
                        max_leaf_nodes=max_leaf_nodes,
                        random_state=random_state,
                    )
                else:
                    pred, fit_info = fit_predict_regressor(
                        train,
                        target,
                        target_column=target_column,
                        numeric_features=numeric_features,
                        categorical_features=categorical_features,
                        max_iter=max_iter,
                        learning_rate=learning_rate,
                        l2_regularization=l2_regularization,
                        max_leaf_nodes=max_leaf_nodes,
                        random_state=random_state,
                    )
            else:
                if model_kind == "classifier":
                    y = bool_series(train, target_column)
                    fallback = float(y.mean()) if len(y) else 0.0
                    train_std = float(y.astype(float).std(ddof=0)) if len(y) else 0.0
                else:
                    y = numeric_series(train, target_column, default=np.nan).dropna()
                    fallback = float(y.mean()) if len(y) else 0.0
                    train_std = float(y.std(ddof=0)) if len(y) else 0.0
                pred = np.full(len(target), fallback, dtype=float)
                fit_info = {
                    "model_used": False,
                    "train_rows_used": int(len(train)),
                    "train_target_mean": fallback,
                    "train_target_std": train_std,
                }
            scored.loc[target.index, prediction_column] = pred
            model_used = bool(fit_info["model_used"])
            used_any = used_any or model_used
            if target_name == "viability":
                scored.loc[target.index, "pred_exit_viability_model_used"] = model_used
            elif target_name == "fixed_best":
                scored.loc[target.index, "pred_exit_best_pnl_model_used"] = model_used
            elif target_name.startswith("fixed_"):
                horizon = target_name.removeprefix("fixed_").removesuffix("m")
                scored.loc[
                    target.index,
                    f"pred_exit_head_fixed_{horizon}m_model_used",
                ] = model_used

            actual = (
                bool_series(target, target_column).astype(float)
                if model_kind == "classifier"
                else numeric_series(target, target_column, default=np.nan)
            )
            valid_eval = actual.notna()
            if model_kind == "classifier" and valid_eval.any():
                y_true = actual[valid_eval].astype(int)
                if y_true.nunique(dropna=True) >= 2:
                    auc = float(roc_auc_score(y_true, pred[valid_eval]))
                else:
                    auc = float("nan")
                mae = float(np.abs(pred[valid_eval] - actual[valid_eval]).mean())
                rmse = float(np.sqrt(((pred[valid_eval] - actual[valid_eval]) ** 2).mean()))
            elif valid_eval.any():
                auc = float("nan")
                mae = float(mean_absolute_error(actual[valid_eval], pred[valid_eval]))
                rmse = float(mean_squared_error(actual[valid_eval], pred[valid_eval]) ** 0.5)
            else:
                auc = float("nan")
                mae = float("nan")
                rmse = float("nan")
            fold_rows.append(
                {
                    "target_month": month,
                    "target_name": target_name,
                    "target_column": target_column,
                    "prediction_column": prediction_column,
                    "model_kind": model_kind,
                    "target_rows": int(len(target)),
                    "train_rows": int(len(train)),
                    "train_months": train_months,
                    "model_used": model_used,
                    "train_rows_used": int(fit_info["train_rows_used"]),
                    "train_target_mean": float(fit_info["train_target_mean"]),
                    "train_target_std": float(fit_info["train_target_std"]),
                    "actual_mean": float(actual.dropna().mean())
                    if actual.notna().any()
                    else float("nan"),
                    "pred_mean": float(np.mean(pred)) if len(pred) else 0.0,
                    "mae": mae,
                    "rmse": rmse,
                    "auc": auc,
                }
            )
        scored.loc[target.index, "pred_exit_head_any_model_used"] = used_any

    add_head_horizon_choice(scored, horizons=horizons, min_predicted_pnl=0.0)
    return scored, pd.DataFrame(fold_rows)


def add_head_horizon_choice(
    frame: pd.DataFrame,
    *,
    horizons: list[int],
    min_predicted_pnl: float,
) -> pd.DataFrame:
    pred_columns = [f"pred_exit_head_fixed_{horizon}m_pnl" for horizon in horizons]
    pred = frame[pred_columns].astype(float)
    best_idx = pred.to_numpy(dtype=float).argmax(axis=1)
    best_values = pred.to_numpy(dtype=float)[np.arange(len(frame)), best_idx]
    best_horizons = np.array(horizons, dtype=int)[best_idx]
    best_horizons = np.where(best_values >= min_predicted_pnl, best_horizons, 0)
    best_values = np.where(best_horizons > 0, best_values, np.nan)
    frame["pred_exit_head_best_horizon_minutes"] = best_horizons
    frame["pred_exit_head_best_horizon_score"] = best_values
    actual_at_head = np.full(len(frame), np.nan, dtype=float)
    for horizon in horizons:
        mask = frame["pred_exit_head_best_horizon_minutes"].astype(int).eq(horizon)
        actual_at_head[mask.to_numpy()] = numeric_series(
            frame.loc[mask],
            f"side_fixed_{horizon}m_adjusted_pnl",
        ).to_numpy(dtype=float)
    frame["actual_pnl_at_exit_head_horizon"] = actual_at_head
    frame["exit_head_choice_executable"] = frame["actual_pnl_at_exit_head_horizon"].ge(0.0)
    frame["exit_head_choice_regret"] = (
        frame["target_fixed_best_adjusted_pnl"].astype(float)
        - frame["actual_pnl_at_exit_head_horizon"].astype(float)
    )
    return frame


def safe_auc(y_true: pd.Series, pred: pd.Series) -> float:
    valid = y_true.notna() & pred.notna()
    if not valid.any():
        return float("nan")
    target = y_true[valid].astype(int)
    if target.nunique(dropna=True) < 2:
        return float("nan")
    return float(roc_auc_score(target, pred[valid]))


def safe_spearman(left: pd.Series, right: pd.Series) -> float:
    frame = pd.DataFrame({"left": left, "right": right}).replace([np.inf, -np.inf], np.nan)
    frame = frame.dropna()
    if len(frame) < 2 or frame["left"].nunique() < 2 or frame["right"].nunique() < 2:
        return float("nan")
    return float(frame["left"].corr(frame["right"], method="spearman"))


def metric_summary(scored: pd.DataFrame, *, horizons: list[int]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    specs = [
        (
            "exit_viability",
            "pred_exit_viability_prob",
            "target_fixed_executable",
            "classifier",
        ),
        (
            "fixed_best_pnl",
            "pred_exit_best_fixed_pnl",
            "target_fixed_best_adjusted_pnl",
            "regressor",
        ),
        (
            "head_horizon_actual",
            "pred_exit_head_best_horizon_score",
            "actual_pnl_at_exit_head_horizon",
            "regressor",
        ),
    ]
    specs.extend(
        [
            (
                f"fixed_{horizon}m_pnl",
                f"pred_exit_head_fixed_{horizon}m_pnl",
                f"side_fixed_{horizon}m_adjusted_pnl",
                "regressor",
            )
            for horizon in horizons
        ]
    )
    for scope, group in scored.groupby("row_scope", dropna=False):
        for name, pred_column, actual_column, kind in specs:
            if pred_column not in group.columns or actual_column not in group.columns:
                continue
            pred = numeric_series(group, pred_column)
            actual = (
                bool_series(group, actual_column).astype(float)
                if kind == "classifier"
                else numeric_series(group, actual_column)
            )
            valid = pred.notna() & actual.notna()
            if not valid.any():
                continue
            error = pred[valid] - actual[valid]
            rows.append(
                {
                    "row_scope": scope,
                    "target_name": name,
                    "prediction_column": pred_column,
                    "actual_column": actual_column,
                    "row_count": int(valid.sum()),
                    "pred_mean": float(pred[valid].mean()),
                    "actual_mean": float(actual[valid].mean()),
                    "bias": float(error.mean()),
                    "mae": float(error.abs().mean()),
                    "rmse": float(np.sqrt((error**2).mean())),
                    "spearman": safe_spearman(pred[valid], actual[valid]),
                    "auc": safe_auc(actual[valid], pred[valid])
                    if kind == "classifier"
                    else float("nan"),
                    "model_used_share": float(
                        bool_series(group.loc[valid], "pred_exit_head_any_model_used").mean()
                    ),
                }
            )
    return pd.DataFrame(rows)


def summarize_group(frame: pd.DataFrame) -> dict[str, Any]:
    head_horizon = numeric_series(frame, "pred_exit_head_best_horizon_minutes", default=0.0)
    head_selected = head_horizon.gt(0.0)
    actual_at_head = numeric_series(frame, "actual_pnl_at_exit_head_horizon")
    return {
        "row_count": int(len(frame)),
        "selected_count": int(bool_series(frame, "selected_any").sum()),
        "target_executable_count": int(bool_series(frame, "target_fixed_executable").sum()),
        "target_executable_rate": float(bool_series(frame, "target_fixed_executable").mean())
        if len(frame)
        else float("nan"),
        "target_fixed_best_pnl_sum": float(
            numeric_series(frame, "target_fixed_best_adjusted_pnl").sum()
        ),
        "target_fixed_best_pnl_mean": float(
            numeric_series(frame, "target_fixed_best_adjusted_pnl").mean()
        ),
        "fixed60_sum": float(numeric_series(frame, "side_fixed_60m_adjusted_pnl").sum()),
        "fixed240_sum": float(numeric_series(frame, "side_fixed_240m_adjusted_pnl").sum()),
        "fixed720_sum": float(numeric_series(frame, "side_fixed_720m_adjusted_pnl").sum()),
        "oracle_best_sum": float(numeric_series(frame, "side_best_adjusted_pnl").sum()),
        "head_selected_count": int(head_selected.sum()),
        "head_actual_pnl_sum": float(actual_at_head[head_selected].sum())
        if head_selected.any()
        else 0.0,
        "head_choice_executable_count": int(
            bool_series(frame, "exit_head_choice_executable").sum()
        ),
        "head_choice_regret_sum": float(
            numeric_series(frame, "exit_head_choice_regret").dropna().sum()
        ),
        "head_model_used_count": int(bool_series(frame, "pred_exit_head_any_model_used").sum()),
    }


def group_summary(scored: pd.DataFrame, group_specs: list[list[str]]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for columns in group_specs:
        available = [column for column in columns if column in scored.columns]
        if not available:
            continue
        for key, group in scored.groupby(available, dropna=False):
            if not isinstance(key, tuple):
                key = (key,)
            row = {
                "group_spec": ",".join(available),
                "group_key": "|".join(str(value) for value in key),
            }
            row.update(dict(zip(available, key)))
            row.update(summarize_group(group))
            rows.append(row)
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(
        ["group_spec", "target_fixed_best_pnl_sum", "row_count"],
        ascending=[True, True, False],
    )


def threshold_summary(
    scored: pd.DataFrame,
    *,
    prob_thresholds: list[float],
    ev_thresholds: list[float],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    prob = numeric_series(scored, "pred_exit_viability_prob", default=0.0)
    head_score = numeric_series(scored, "pred_exit_head_best_horizon_score")
    head_horizon = numeric_series(scored, "pred_exit_head_best_horizon_minutes", default=0.0)
    actual_at_head = numeric_series(scored, "actual_pnl_at_exit_head_horizon")
    for scope, group in scored.groupby("row_scope", dropna=False):
        index = group.index
        for prob_threshold in prob_thresholds:
            for ev_threshold in ev_thresholds:
                flag = (
                    prob.loc[index].ge(prob_threshold)
                    & head_score.loc[index].ge(ev_threshold)
                    & head_horizon.loc[index].gt(0.0)
                )
                flagged = group.loc[flag]
                rows.append(
                    {
                        "row_scope": scope,
                        "prob_threshold": float(prob_threshold),
                        "ev_threshold": float(ev_threshold),
                        "row_count": int(len(group)),
                        "flagged_count": int(flag.sum()),
                        "flagged_selected_count": int(
                            bool_series(flagged, "selected_any").sum()
                        )
                        if len(flagged)
                        else 0,
                        "flagged_actual_pnl_sum": float(
                            actual_at_head.loc[flagged.index].sum()
                        )
                        if len(flagged)
                        else 0.0,
                        "flagged_fixed_best_pnl_sum": float(
                            numeric_series(flagged, "target_fixed_best_adjusted_pnl").sum()
                        )
                        if len(flagged)
                        else 0.0,
                        "flagged_oracle_best_sum": float(
                            numeric_series(flagged, "side_best_adjusted_pnl").sum()
                        )
                        if len(flagged)
                        else 0.0,
                        "flagged_target_executable_count": int(
                            bool_series(flagged, "target_fixed_executable").sum()
                        )
                        if len(flagged)
                        else 0,
                        "flagged_target_executable_rate": float(
                            bool_series(flagged, "target_fixed_executable").mean()
                        )
                        if len(flagged)
                        else float("nan"),
                        "flagged_head_choice_executable_count": int(
                            bool_series(flagged, "exit_head_choice_executable").sum()
                        )
                        if len(flagged)
                        else 0,
                        "flagged_model_used_count": int(
                            bool_series(flagged, "pred_exit_head_any_model_used").sum()
                        )
                        if len(flagged)
                        else 0,
                    }
                )
    return pd.DataFrame(rows).sort_values(
        ["row_scope", "flagged_actual_pnl_sum", "flagged_count"],
        ascending=[True, False, False],
    )


def horizon_summary(scored: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for scope, group in scored.groupby("row_scope", dropna=False):
        for horizon, horizon_group in group.groupby(
            "target_fixed_best_horizon_minutes",
            dropna=False,
        ):
            rows.append(
                {
                    "row_scope": scope,
                    "horizon_kind": "target_fixed_best",
                    "horizon_minutes": int(horizon),
                    **summarize_group(horizon_group),
                }
            )
        for horizon, horizon_group in group.groupby(
            "pred_exit_head_best_horizon_minutes",
            dropna=False,
        ):
            rows.append(
                {
                    "row_scope": scope,
                    "horizon_kind": "predicted_head_best",
                    "horizon_minutes": int(horizon),
                    **summarize_group(horizon_group),
                }
            )
    return pd.DataFrame(rows).sort_values(
        ["row_scope", "horizon_kind", "horizon_minutes"]
    )


def build_diagnostics(args: argparse.Namespace) -> Path:
    horizons = parse_int_csv(args.horizons)
    rows = normalize_rows(pd.read_csv(args.input), horizons=horizons)
    numeric_features = available_features(
        rows,
        parse_csv(args.numeric_features),
        DEFAULT_NUMERIC_FEATURES,
    )
    categorical_features = available_features(
        rows,
        parse_csv(args.categorical_features),
        DEFAULT_CATEGORICAL_FEATURES,
    )
    scored, folds = chronological_head_predictions(
        rows,
        horizons=horizons,
        train_universe=args.train_universe,
        min_train_months=args.min_train_months,
        min_train_rows=args.min_train_rows,
        numeric_features=numeric_features,
        categorical_features=categorical_features,
        max_iter=args.max_iter,
        learning_rate=args.learning_rate,
        l2_regularization=args.l2_regularization,
        max_leaf_nodes=args.max_leaf_nodes,
        random_state=args.random_state,
    )
    add_head_horizon_choice(
        scored,
        horizons=horizons,
        min_predicted_pnl=args.min_predicted_pnl,
    )
    metrics = metric_summary(scored, horizons=horizons)
    groups = group_summary(scored, parse_group_specs(args.group_specs))
    thresholds = threshold_summary(
        scored,
        prob_thresholds=parse_float_csv(args.prob_thresholds),
        ev_thresholds=parse_float_csv(args.ev_thresholds),
    )
    horizons_out = horizon_summary(scored)

    run_dir = make_run_dir(args.output_dir, args.label)
    scored.to_csv(run_dir / "near_miss_exit_head_predictions.csv", index=False)
    folds.to_csv(run_dir / "near_miss_exit_head_fold_summary.csv", index=False)
    metrics.to_csv(run_dir / "near_miss_exit_head_metric_summary.csv", index=False)
    groups.to_csv(run_dir / "near_miss_exit_head_group_summary.csv", index=False)
    thresholds.to_csv(run_dir / "near_miss_exit_head_threshold_summary.csv", index=False)
    horizons_out.to_csv(run_dir / "near_miss_exit_head_horizon_summary.csv", index=False)
    config = {
        "input": args.input,
        "horizons": horizons,
        "train_universe": args.train_universe,
        "min_train_months": args.min_train_months,
        "min_train_rows": args.min_train_rows,
        "numeric_features": numeric_features,
        "categorical_features": categorical_features,
        "max_iter": args.max_iter,
        "learning_rate": args.learning_rate,
        "l2_regularization": args.l2_regularization,
        "max_leaf_nodes": args.max_leaf_nodes,
        "random_state": args.random_state,
        "min_predicted_pnl": args.min_predicted_pnl,
        "prob_thresholds": args.prob_thresholds,
        "ev_thresholds": args.ev_thresholds,
        "row_count": int(len(scored)),
    }
    (run_dir / "config.json").write_text(
        json.dumps(config, indent=2, sort_keys=True, default=local_json_default) + "\n",
        encoding="utf-8",
    )

    print("Near-miss exit head metrics:")
    print(metrics.to_string(index=False))
    print("\nNear-miss exit head threshold summary:")
    print(thresholds.head(30).to_string(index=False))
    print(f"artifacts: {run_dir}")
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--horizons", default=DEFAULT_HORIZONS)
    parser.add_argument("--train-universe", default=DEFAULT_TRAIN_UNIVERSE)
    parser.add_argument("--min-train-months", type=int, default=2)
    parser.add_argument("--min-train-rows", type=int, default=20)
    parser.add_argument("--numeric-features", default="")
    parser.add_argument("--categorical-features", default="")
    parser.add_argument("--max-iter", type=int, default=80)
    parser.add_argument("--learning-rate", type=float, default=0.05)
    parser.add_argument("--l2-regularization", type=float, default=1.0)
    parser.add_argument("--max-leaf-nodes", type=int, default=8)
    parser.add_argument("--random-state", type=int, default=42)
    parser.add_argument("--min-predicted-pnl", type=float, default=0.0)
    parser.add_argument("--prob-thresholds", default=DEFAULT_PROB_THRESHOLDS)
    parser.add_argument("--ev-thresholds", default=DEFAULT_EV_THRESHOLDS)
    parser.add_argument("--group-specs", default=DEFAULT_GROUP_SPECS)
    parser.add_argument("--output-dir", type=Path, default=Path("data/reports/backtests"))
    parser.add_argument("--label", default="entry_ev_near_miss_exit_head")
    return parser


def main(argv: list[str] | None = None) -> int:
    build_diagnostics(build_parser().parse_args(argv))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
