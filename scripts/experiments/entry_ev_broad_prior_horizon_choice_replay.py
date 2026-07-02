#!/usr/bin/env python3
"""Replay support repair using a chronological horizon-choice head with broad priors."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, roc_auc_score

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from trade_data.backtest import json_default, make_run_dir  # noqa: E402

from entry_ev_broad_duration_prior_repair_replay import (  # noqa: E402
    DEFAULT_CONTEXT_SPECS,
    add_duration_prior_columns,
    parse_context_specs,
)
from entry_ev_near_miss_exit_head import (  # noqa: E402
    DEFAULT_CATEGORICAL_FEATURES,
    DEFAULT_NUMERIC_FEATURES,
    available_features,
    bool_series,
    fit_predict_classifier,
    fit_predict_regressor,
    numeric_series,
    parse_csv,
    parse_float_csv,
    parse_int_csv,
    safe_spearman,
    text_series,
)
from entry_ev_near_miss_horizon_viability import DEFAULT_HORIZONS  # noqa: E402
from entry_ev_support_repair_horizon_replay import (  # noqa: E402
    add_repair_utility_columns,
    parse_bool_csv,
    read_base_monthly,
    read_base_trades,
    read_choice_candidates,
    replay_scenarios,
)


DEFAULT_HORIZON_NUMERIC_FEATURES = (
    *DEFAULT_NUMERIC_FEATURES,
    "horizon_minutes",
    "horizon_hours",
    "horizon_order",
    "is_60m",
    "is_240m",
    "is_720m",
    "horizon_pred_fixed_pnl",
    "horizon_pred_delta_vs_60",
    "horizon_pred_gap_vs_pred_best",
    "horizon_is_pred_fixed_best",
    "pred_fixed_60m_adjusted_pnl",
    "pred_fixed_240m_adjusted_pnl",
    "pred_fixed_720m_adjusted_pnl",
    "duration_prior_count",
    "duration_prior_months",
    "duration_prior_mean_pnl",
    "duration_prior_delta_vs_60_mean",
    "duration_prior_loss_rate",
    "duration_prior_tail_loss_rate",
    "duration_prior_underperform_60_rate",
    "repair_duration_risk_score",
)
DEFAULT_HORIZON_CATEGORICAL_FEATURES = (
    *DEFAULT_CATEGORICAL_FEATURES,
    "horizon_bucket",
    "duration_prior_context_spec",
)
DEFAULT_SCORE_MODES = "pnl,pnl_delta,pnl_delta_tail"
DEFAULT_PROB_THRESHOLDS = "0.50,0.60,0.70"
DEFAULT_EV_THRESHOLDS = "-2,0,2"
DEFAULT_TAIL_PROB_THRESHOLDS = "0.30,0.50"
DEFAULT_RESIDUAL_CONTEXT_SPECS = (
    "horizon_bucket,side,combined_regime,session_regime,near_miss_bucket;"
    "horizon_bucket,side,combined_regime,session_regime;"
    "horizon_bucket,side,combined_regime;"
    "horizon_bucket,side,session_regime;"
    "horizon_bucket,combined_regime,session_regime;"
    "horizon_bucket,side;"
    "horizon_bucket;"
    "global"
)


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


def sample_train_rows(
    train: pd.DataFrame,
    *,
    max_train_rows: int,
    random_state: int,
) -> pd.DataFrame:
    if max_train_rows <= 0 or len(train) <= max_train_rows:
        return train.copy()
    return (
        train.sample(n=max_train_rows, random_state=random_state)
        .sort_values(["month", "decision_timestamp", "side", "hv_chosen_horizon_minutes"])
        .reset_index(drop=True)
    )


def normalize_source_rows(frame: pd.DataFrame) -> pd.DataFrame:
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
        if column in output.columns:
            output[column] = text_series(output, column)
    for column in [
        "holding_ok",
        "strict_side_specific",
        "relaxed_side_specific",
        "one_failed_strict_stage",
        "stateful_available",
        "selected_any",
        "target_fixed_executable",
        "target_fixed60_loss_rescuable",
        "pred_fixed_available",
    ]:
        if column in output.columns:
            output[column] = bool_series(output, column)
    return output.sort_values(["month", "decision_timestamp"]).reset_index(drop=True)


def horizon_column(horizon: int | float, *, prefix: str) -> str:
    return f"{prefix}_{int(float(horizon))}m_adjusted_pnl"


def expand_horizon_examples(
    frame: pd.DataFrame,
    *,
    horizons: list[int],
    min_executable_pnl: float,
    tail_loss_threshold: float,
    min_delta_vs_60: float,
) -> pd.DataFrame:
    source = normalize_source_rows(frame)
    frames: list[pd.DataFrame] = []
    fixed60_actual = numeric_series(source, "side_fixed_60m_adjusted_pnl")
    fixed60_pred = numeric_series(source, "pred_fixed_60m_adjusted_pnl")
    pred_best = numeric_series(source, "pred_fixed_best_adjusted_pnl")
    pred_best_horizon = numeric_series(source, "pred_fixed_best_horizon_minutes", default=0.0)
    for order, horizon in enumerate(horizons):
        actual_column = horizon_column(horizon, prefix="side_fixed")
        pred_column = horizon_column(horizon, prefix="pred_fixed")
        if actual_column not in source.columns or pred_column not in source.columns:
            raise ValueError(f"missing horizon columns for {horizon}m")
        output = source.copy()
        actual = numeric_series(output, actual_column)
        pred = numeric_series(output, pred_column)
        output["hv_chosen_horizon_minutes"] = float(horizon)
        output["horizon_minutes"] = float(horizon)
        output["horizon_hours"] = float(horizon) / 60.0
        output["horizon_order"] = float(order)
        output["horizon_bucket"] = f"{int(horizon)}m"
        output["is_60m"] = float(int(horizon == 60))
        output["is_240m"] = float(int(horizon == 240))
        output["is_720m"] = float(int(horizon == 720))
        output["horizon_actual_pnl"] = actual
        output["horizon_actual_delta_vs_60"] = actual - fixed60_actual
        output["horizon_pred_fixed_pnl"] = pred
        output["horizon_pred_fixed_error"] = pred - actual
        output["horizon_pred_fixed_abs_error"] = (pred - actual).abs()
        output["horizon_pred_fixed_overestimate"] = pred.gt(actual)
        output["horizon_pred_delta_vs_60"] = pred - fixed60_pred
        output["horizon_pred_gap_vs_pred_best"] = pred - pred_best
        output["horizon_is_pred_fixed_best"] = pred_best_horizon.eq(float(horizon)).astype(float)
        output["target_horizon_executable"] = actual.ge(min_executable_pnl)
        output["target_horizon_tail_loss"] = actual.le(tail_loss_threshold)
        output["target_horizon_beats_60"] = (actual - fixed60_actual).ge(min_delta_vs_60)
        frames.append(output)
    return pd.concat(frames, ignore_index=True, sort=False)


def add_prior_features_to_examples(
    examples: pd.DataFrame,
    broad_train_rows: pd.DataFrame,
    *,
    context_specs: list[list[str]],
    min_prior_rows: int,
    min_prior_months: int,
    shrinkage_count: float,
    tail_loss_threshold: float,
    negative_pnl_weight: float,
    underperform_weight: float,
    loss_rate_weight: float,
    tail_loss_rate_weight: float,
) -> pd.DataFrame:
    output = add_duration_prior_columns(
        examples,
        broad_train_rows,
        context_specs=context_specs,
        min_prior_rows=min_prior_rows,
        min_prior_months=min_prior_months,
        shrinkage_count=shrinkage_count,
        tail_loss_threshold=tail_loss_threshold,
        negative_pnl_weight=negative_pnl_weight,
        underperform_weight=underperform_weight,
        loss_rate_weight=loss_rate_weight,
        tail_loss_rate_weight=tail_loss_rate_weight,
    )
    for column in [
        "duration_prior_count",
        "duration_prior_months",
        "duration_prior_mean_pnl",
        "duration_prior_delta_vs_60_mean",
        "duration_prior_loss_rate",
        "duration_prior_tail_loss_rate",
        "duration_prior_underperform_60_rate",
        "repair_duration_risk_score",
    ]:
        output[column] = numeric_series(output, column, default=0.0)
    output["duration_prior_context_spec"] = text_series(
        output,
        "duration_prior_context_spec",
        default="none",
    )
    return output


def shrink_metric(value: float, global_value: float, count: float, shrinkage_count: float) -> float:
    if not np.isfinite(value):
        return global_value if np.isfinite(global_value) else 0.0
    if shrinkage_count <= 0 or not np.isfinite(global_value):
        return value
    return float((count * value + shrinkage_count * global_value) / (count + shrinkage_count))


def residual_prior_metrics(
    group: pd.DataFrame,
    *,
    tail_loss_threshold: float,
    min_executable_pnl: float,
) -> dict[str, float]:
    pred = numeric_series(group, "horizon_pred_fixed_pnl", default=np.nan)
    actual = numeric_series(group, "horizon_actual_pnl", default=np.nan)
    valid = pred.notna() & actual.notna()
    if not valid.any():
        return {
            "prior_count": 0.0,
            "prior_months": 0.0,
            "prior_bias": np.nan,
            "prior_mae": np.nan,
            "prior_rmse": np.nan,
            "prior_overestimate_rate": np.nan,
            "prior_tail_miss_rate": np.nan,
        }
    error = pred[valid] - actual[valid]
    tail_miss = actual[valid].le(tail_loss_threshold) & pred[valid].ge(min_executable_pnl)
    return {
        "prior_count": float(valid.sum()),
        "prior_months": float(group.loc[valid, "month"].astype(str).nunique()),
        "prior_bias": float(error.mean()),
        "prior_mae": float(error.abs().mean()),
        "prior_rmse": float(np.sqrt((error**2).mean())),
        "prior_overestimate_rate": float(error.gt(0.0).mean()),
        "prior_tail_miss_rate": float(tail_miss.mean()),
    }


def select_residual_prior(
    row: pd.Series,
    prior: pd.DataFrame,
    *,
    context_specs: list[list[str]],
    min_prior_rows: int,
    min_prior_months: int,
    shrinkage_count: float,
    tail_loss_threshold: float,
    min_executable_pnl: float,
) -> dict[str, Any]:
    if prior.empty:
        return {
            "residual_prior_context_spec": "none",
            "residual_prior_context_key": "",
            "residual_prior_count": 0,
            "residual_prior_months": 0,
            "residual_prior_bias": 0.0,
            "residual_prior_mae": 0.0,
            "residual_prior_rmse": 0.0,
            "residual_prior_overestimate_rate": 0.0,
            "residual_prior_tail_miss_rate": 0.0,
            "residual_prior_used": False,
        }

    global_metrics = residual_prior_metrics(
        prior,
        tail_loss_threshold=tail_loss_threshold,
        min_executable_pnl=min_executable_pnl,
    )
    selected_spec: list[str] = []
    selected_metrics = global_metrics
    used = False
    for spec in context_specs:
        group = prior
        missing_column = False
        for column in spec:
            if column not in group.columns or column not in row.index:
                missing_column = True
                break
            group = group[group[column].astype(str).eq(str(row[column]))]
        if missing_column:
            continue
        metrics = residual_prior_metrics(
            group,
            tail_loss_threshold=tail_loss_threshold,
            min_executable_pnl=min_executable_pnl,
        )
        if (
            int(metrics["prior_count"]) >= min_prior_rows
            and int(metrics["prior_months"]) >= min_prior_months
        ):
            selected_spec = spec
            selected_metrics = metrics
            used = True
            break

    if not used and int(global_metrics["prior_count"]) > 0:
        selected_spec = []
        selected_metrics = global_metrics
        used = int(global_metrics["prior_months"]) >= min_prior_months

    count = float(selected_metrics["prior_count"])
    bias = shrink_metric(
        float(selected_metrics["prior_bias"]),
        float(global_metrics["prior_bias"]),
        count,
        shrinkage_count,
    )
    mae = shrink_metric(
        float(selected_metrics["prior_mae"]),
        float(global_metrics["prior_mae"]),
        count,
        shrinkage_count,
    )
    rmse = shrink_metric(
        float(selected_metrics["prior_rmse"]),
        float(global_metrics["prior_rmse"]),
        count,
        shrinkage_count,
    )
    overestimate_rate = shrink_metric(
        float(selected_metrics["prior_overestimate_rate"]),
        float(global_metrics["prior_overestimate_rate"]),
        count,
        shrinkage_count,
    )
    tail_miss_rate = shrink_metric(
        float(selected_metrics["prior_tail_miss_rate"]),
        float(global_metrics["prior_tail_miss_rate"]),
        count,
        shrinkage_count,
    )
    key = "|".join(str(row[column]) for column in selected_spec) if selected_spec else "global"
    return {
        "residual_prior_context_spec": ",".join(selected_spec) if selected_spec else "global",
        "residual_prior_context_key": key,
        "residual_prior_count": int(selected_metrics["prior_count"]),
        "residual_prior_months": int(selected_metrics["prior_months"]),
        "residual_prior_bias": bias,
        "residual_prior_mae": mae,
        "residual_prior_rmse": rmse,
        "residual_prior_overestimate_rate": overestimate_rate,
        "residual_prior_tail_miss_rate": tail_miss_rate,
        "residual_prior_used": bool(used),
    }


def add_residual_prior_columns(
    examples: pd.DataFrame,
    reference_examples: pd.DataFrame,
    *,
    context_specs: list[list[str]],
    min_prior_rows: int,
    min_prior_months: int,
    shrinkage_count: float,
    tail_loss_threshold: float,
    min_executable_pnl: float,
) -> pd.DataFrame:
    output = examples.copy()
    reference = reference_examples.copy()
    reference_periods = pd.Series(
        pd.PeriodIndex(reference["month"].astype(str), freq="M"),
        index=reference.index,
    )
    context_columns = sorted({column for spec in context_specs for column in spec})
    key_columns = [
        "month",
        "hv_chosen_horizon_minutes",
        *[column for column in context_columns if column in output.columns],
    ]
    prior_rows: list[dict[str, Any]] = []
    for _, row in output[key_columns].drop_duplicates().iterrows():
        target_period = pd.Period(str(row["month"]), freq="M")
        prior = reference[reference_periods < target_period]
        metrics = select_residual_prior(
            row,
            prior,
            context_specs=context_specs,
            min_prior_rows=min_prior_rows,
            min_prior_months=min_prior_months,
            shrinkage_count=shrinkage_count,
            tail_loss_threshold=tail_loss_threshold,
            min_executable_pnl=min_executable_pnl,
        )
        prior_rows.append(
            {
                **{column: row[column] for column in key_columns},
                **metrics,
            }
        )
    prior_frame = pd.DataFrame(prior_rows)
    output = output.merge(prior_frame, on=key_columns, how="left")
    for column in [
        "residual_prior_count",
        "residual_prior_months",
        "residual_prior_bias",
        "residual_prior_mae",
        "residual_prior_rmse",
        "residual_prior_overestimate_rate",
        "residual_prior_tail_miss_rate",
    ]:
        output[column] = numeric_series(output, column, default=0.0)
    output["residual_prior_context_spec"] = text_series(
        output,
        "residual_prior_context_spec",
        default="none",
    )
    return output


def score_predictions(
    frame: pd.DataFrame,
    *,
    score_mode: str,
    delta_weight: float,
    beats60_weight: float,
    tail_score_weight: float,
    lower_bound_mae_weight: float,
    lower_bound_bias_weight: float,
    lower_bound_tail_miss_weight: float,
) -> pd.Series:
    pnl = numeric_series(frame, "ranker_pred_pnl", default=0.0)
    if score_mode == "pnl":
        return pnl
    delta = numeric_series(frame, "ranker_pred_delta_vs_60", default=0.0).clip(lower=0.0)
    beats60 = numeric_series(frame, "ranker_pred_beats60_prob", default=0.0)
    tail = numeric_series(frame, "ranker_pred_tail_loss_prob", default=0.0)
    if score_mode == "pnl_delta":
        return pnl + delta_weight * delta + beats60_weight * beats60
    if score_mode == "pnl_delta_tail":
        return pnl + delta_weight * delta + beats60_weight * beats60 - tail_score_weight * tail
    lower_bound_penalty = (
        lower_bound_mae_weight * numeric_series(frame, "residual_prior_mae", default=0.0)
        + lower_bound_bias_weight
        * numeric_series(frame, "residual_prior_bias", default=0.0).clip(lower=0.0)
        + lower_bound_tail_miss_weight
        * numeric_series(frame, "residual_prior_tail_miss_rate", default=0.0)
    )
    if score_mode == "pnl_lower":
        return pnl - lower_bound_penalty
    if score_mode == "pnl_delta_lower":
        return pnl + delta_weight * delta + beats60_weight * beats60 - lower_bound_penalty
    if score_mode == "pnl_delta_tail_lower":
        return (
            pnl
            + delta_weight * delta
            + beats60_weight * beats60
            - tail_score_weight * tail
            - lower_bound_penalty
        )
    raise ValueError(f"unknown score mode: {score_mode}")


def fit_predict_target(
    train: pd.DataFrame,
    target: pd.DataFrame,
    *,
    target_name: str,
    target_column: str,
    model_kind: str,
    numeric_features: list[str],
    categorical_features: list[str],
    max_iter: int,
    learning_rate: float,
    l2_regularization: float,
    max_leaf_nodes: int,
    random_state: int,
) -> tuple[np.ndarray, dict[str, Any]]:
    if model_kind == "classifier":
        return fit_predict_classifier(
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
    if model_kind == "regressor":
        return fit_predict_regressor(
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
    raise ValueError(f"unknown model kind for {target_name}: {model_kind}")


def fallback_predict_target(
    train: pd.DataFrame,
    target: pd.DataFrame,
    *,
    target_column: str,
    model_kind: str,
) -> tuple[np.ndarray, dict[str, Any]]:
    if model_kind == "classifier":
        y = bool_series(train, target_column)
        fallback = float(y.mean()) if len(y) else 0.0
        train_std = float(y.astype(float).std(ddof=0)) if len(y) else 0.0
    else:
        y = numeric_series(train, target_column, default=np.nan).dropna()
        fallback = float(y.mean()) if len(y) else 0.0
        train_std = float(y.std(ddof=0)) if len(y) else 0.0
    return np.full(len(target), fallback, dtype=float), {
        "model_used": False,
        "train_rows_used": int(len(train)),
        "train_target_mean": fallback,
        "train_target_std": train_std,
    }


def chronological_ranker_predictions(
    *,
    train_examples: pd.DataFrame,
    eval_examples: pd.DataFrame,
    min_train_months: int,
    min_train_rows: int,
    max_train_rows: int,
    numeric_features: list[str],
    categorical_features: list[str],
    max_iter: int,
    learning_rate: float,
    l2_regularization: float,
    max_leaf_nodes: int,
    random_state: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    scored = eval_examples.copy()
    eval_months = sorted(scored["month"].astype(str).unique().tolist())
    train_periods = pd.PeriodIndex(train_examples["month"].astype(str), freq="M")
    fold_rows: list[dict[str, Any]] = []
    target_specs = [
        ("pnl", "horizon_actual_pnl", "ranker_pred_pnl", "regressor"),
        (
            "delta_vs_60",
            "horizon_actual_delta_vs_60",
            "ranker_pred_delta_vs_60",
            "regressor",
        ),
        (
            "executable",
            "target_horizon_executable",
            "ranker_pred_executable_prob",
            "classifier",
        ),
        (
            "tail_loss",
            "target_horizon_tail_loss",
            "ranker_pred_tail_loss_prob",
            "classifier",
        ),
        (
            "beats_60",
            "target_horizon_beats_60",
            "ranker_pred_beats60_prob",
            "classifier",
        ),
    ]
    for _, _, pred_column, _ in target_specs:
        scored[pred_column] = 0.0
        scored[f"{pred_column}_model_used"] = False

    for month in eval_months:
        target_period = pd.Period(month, freq="M")
        train_full = train_examples[train_periods < target_period].copy()
        train_months = int(train_full["month"].nunique()) if len(train_full) else 0
        train = sample_train_rows(
            train_full,
            max_train_rows=max_train_rows,
            random_state=random_state + int(target_period.ordinal),
        )
        target = scored[scored["month"].astype(str).eq(month)].copy()
        can_fit = train_months >= min_train_months and len(train) >= min_train_rows
        for target_name, target_column, pred_column, model_kind in target_specs:
            if can_fit:
                pred, fit_info = fit_predict_target(
                    train,
                    target,
                    target_name=target_name,
                    target_column=target_column,
                    model_kind=model_kind,
                    numeric_features=numeric_features,
                    categorical_features=categorical_features,
                    max_iter=max_iter,
                    learning_rate=learning_rate,
                    l2_regularization=l2_regularization,
                    max_leaf_nodes=max_leaf_nodes,
                    random_state=random_state,
                )
            else:
                pred, fit_info = fallback_predict_target(
                    train,
                    target,
                    target_column=target_column,
                    model_kind=model_kind,
                )
            scored.loc[target.index, pred_column] = pred
            scored.loc[target.index, f"{pred_column}_model_used"] = bool(
                fit_info["model_used"]
            )
            actual = (
                bool_series(target, target_column).astype(float)
                if model_kind == "classifier"
                else numeric_series(target, target_column, default=np.nan)
            )
            valid = actual.notna()
            if model_kind == "classifier" and valid.any():
                y_true = actual[valid].astype(int)
                auc = (
                    float(roc_auc_score(y_true, pred[valid]))
                    if y_true.nunique(dropna=True) >= 2
                    else float("nan")
                )
                mae = float(np.abs(pred[valid] - actual[valid]).mean())
                rmse = float(np.sqrt(((pred[valid] - actual[valid]) ** 2).mean()))
            elif valid.any():
                auc = float("nan")
                mae = float(mean_absolute_error(actual[valid], pred[valid]))
                rmse = float(mean_squared_error(actual[valid], pred[valid]) ** 0.5)
            else:
                auc = float("nan")
                mae = float("nan")
                rmse = float("nan")
            fold_rows.append(
                {
                    "target_month": month,
                    "target_name": target_name,
                    "target_column": target_column,
                    "prediction_column": pred_column,
                    "model_kind": model_kind,
                    "target_rows": int(len(target)),
                    "train_rows_full": int(len(train_full)),
                    "train_rows": int(len(train)),
                    "train_months": train_months,
                    "model_used": bool(fit_info["model_used"]),
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
    scored["ranker_core_model_used"] = (
        bool_series(scored, "ranker_pred_pnl_model_used")
        & bool_series(scored, "ranker_pred_executable_prob_model_used")
        & bool_series(scored, "ranker_pred_tail_loss_prob_model_used")
    )
    return scored, pd.DataFrame(fold_rows)


def metric_summary(scored: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    specs = [
        ("pnl", "ranker_pred_pnl", "horizon_actual_pnl", "regressor"),
        ("delta_vs_60", "ranker_pred_delta_vs_60", "horizon_actual_delta_vs_60", "regressor"),
        ("executable", "ranker_pred_executable_prob", "target_horizon_executable", "classifier"),
        ("tail_loss", "ranker_pred_tail_loss_prob", "target_horizon_tail_loss", "classifier"),
        ("beats_60", "ranker_pred_beats60_prob", "target_horizon_beats_60", "classifier"),
    ]
    for scope, group in scored.groupby("row_scope", dropna=False):
        for horizon, horizon_group in group.groupby("hv_chosen_horizon_minutes", dropna=False):
            for target_name, pred_column, actual_column, kind in specs:
                pred = numeric_series(horizon_group, pred_column, default=np.nan)
                actual = (
                    bool_series(horizon_group, actual_column).astype(float)
                    if kind == "classifier"
                    else numeric_series(horizon_group, actual_column, default=np.nan)
                )
                valid = pred.notna() & actual.notna()
                if not valid.any():
                    continue
                error = pred[valid] - actual[valid]
                auc = float("nan")
                if kind == "classifier":
                    target = actual[valid].astype(int)
                    if target.nunique(dropna=True) >= 2:
                        auc = float(roc_auc_score(target, pred[valid]))
                rows.append(
                    {
                        "row_scope": scope,
                        "horizon_minutes": int(float(horizon)),
                        "target_name": target_name,
                        "row_count": int(valid.sum()),
                        "pred_mean": float(pred[valid].mean()),
                        "actual_mean": float(actual[valid].mean()),
                        "bias": float(error.mean()),
                        "mae": float(error.abs().mean()),
                        "rmse": float(np.sqrt((error**2).mean())),
                        "spearman": safe_spearman(pred[valid], actual[valid]),
                        "auc": auc,
                    }
                )
    return pd.DataFrame(rows)


def prediction_key_columns(frame: pd.DataFrame) -> list[str]:
    keys = [
        "family",
        "role",
        "month",
        "decision_timestamp",
        "side",
        "row_scope",
        "selection_bucket",
        "needed_side",
        "extra_side_needed",
    ]
    return [column for column in keys if column in frame.columns]


def pivot_ranker_predictions(
    base_rows: pd.DataFrame,
    scored_examples: pd.DataFrame,
    *,
    horizons: list[int],
    score_mode: str,
    delta_weight: float,
    beats60_weight: float,
    tail_score_weight: float,
    lower_bound_mae_weight: float,
    lower_bound_bias_weight: float,
    lower_bound_tail_miss_weight: float,
) -> pd.DataFrame:
    output = normalize_source_rows(base_rows)
    stale_prediction_columns = [
        column
        for column in output.columns
        if column.startswith("pred_hv_") or column.startswith("ranker_hv_")
    ]
    if stale_prediction_columns:
        output = output.drop(columns=stale_prediction_columns)
    keys = prediction_key_columns(output)
    scored = scored_examples.copy()
    scored["ranker_choice_score"] = score_predictions(
        scored,
        score_mode=score_mode,
        delta_weight=delta_weight,
        beats60_weight=beats60_weight,
        tail_score_weight=tail_score_weight,
        lower_bound_mae_weight=lower_bound_mae_weight,
        lower_bound_bias_weight=lower_bound_bias_weight,
        lower_bound_tail_miss_weight=lower_bound_tail_miss_weight,
    )
    for horizon in horizons:
        for column, default in {
            "residual_prior_count": 0.0,
            "residual_prior_months": 0.0,
            "residual_prior_bias": 0.0,
            "residual_prior_mae": 0.0,
            "residual_prior_overestimate_rate": 0.0,
            "residual_prior_tail_miss_rate": 0.0,
        }.items():
            if column not in scored.columns:
                scored[column] = default
        horizon_rows = scored[
            numeric_series(scored, "hv_chosen_horizon_minutes").eq(float(horizon))
        ][
            [
                *keys,
                "ranker_pred_executable_prob",
                "ranker_pred_pnl",
                "ranker_pred_tail_loss_prob",
                "ranker_pred_delta_vs_60",
                "ranker_pred_beats60_prob",
                "ranker_choice_score",
                "ranker_core_model_used",
                "duration_prior_count",
                "duration_prior_months",
                "duration_prior_mean_pnl",
                "duration_prior_delta_vs_60_mean",
                "duration_prior_tail_loss_rate",
                "repair_duration_risk_score",
                "residual_prior_count",
                "residual_prior_months",
                "residual_prior_bias",
                "residual_prior_mae",
                "residual_prior_overestimate_rate",
                "residual_prior_tail_miss_rate",
            ]
        ].copy()
        rename = {
            "ranker_pred_executable_prob": f"pred_hv_{horizon}m_executable_prob",
            "ranker_choice_score": f"pred_hv_{horizon}m_pnl",
            "ranker_pred_tail_loss_prob": f"pred_hv_{horizon}m_tail_loss_prob",
            "ranker_core_model_used": f"pred_hv_{horizon}m_executable_model_used",
            "ranker_pred_pnl": f"ranker_hv_{horizon}m_pred_pnl",
            "ranker_pred_delta_vs_60": f"ranker_hv_{horizon}m_pred_delta_vs_60",
            "ranker_pred_beats60_prob": f"ranker_hv_{horizon}m_pred_beats60_prob",
            "duration_prior_count": f"ranker_hv_{horizon}m_prior_count",
            "duration_prior_months": f"ranker_hv_{horizon}m_prior_months",
            "duration_prior_mean_pnl": f"ranker_hv_{horizon}m_prior_mean_pnl",
            "duration_prior_delta_vs_60_mean": f"ranker_hv_{horizon}m_prior_delta_vs_60_mean",
            "duration_prior_tail_loss_rate": f"ranker_hv_{horizon}m_prior_tail_loss_rate",
            "repair_duration_risk_score": f"ranker_hv_{horizon}m_prior_risk_score",
            "residual_prior_count": f"ranker_hv_{horizon}m_residual_count",
            "residual_prior_months": f"ranker_hv_{horizon}m_residual_months",
            "residual_prior_bias": f"ranker_hv_{horizon}m_residual_bias",
            "residual_prior_mae": f"ranker_hv_{horizon}m_residual_mae",
            "residual_prior_overestimate_rate": (
                f"ranker_hv_{horizon}m_residual_overestimate_rate"
            ),
            "residual_prior_tail_miss_rate": (
                f"ranker_hv_{horizon}m_residual_tail_miss_rate"
            ),
        }
        horizon_rows = horizon_rows.rename(columns=rename)
        horizon_rows[f"pred_hv_{horizon}m_pnl_model_used"] = horizon_rows[
            f"pred_hv_{horizon}m_executable_model_used"
        ]
        horizon_rows[f"pred_hv_{horizon}m_tail_model_used"] = horizon_rows[
            f"pred_hv_{horizon}m_executable_model_used"
        ]
        output = output.merge(horizon_rows, on=keys, how="left")
    output["ranker_score_mode"] = score_mode
    return output


def summarize_ranker_choices(scored_examples: pd.DataFrame, *, score_mode: str) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for (scope, month), group in scored_examples.groupby(["row_scope", "month"], dropna=False):
        scored = group.copy()
        choice_idx = scored.groupby(
            ["family", "role", "decision_timestamp", "side"],
            dropna=False,
        )["ranker_choice_score"].idxmax()
        chosen = scored.loc[choice_idx]
        rows.append(
            {
                "score_mode": score_mode,
                "row_scope": scope,
                "month": month,
                "candidate_rows": int(
                    scored[["family", "role", "decision_timestamp", "side"]]
                    .drop_duplicates()
                    .shape[0]
                ),
                "chosen_count": int(len(chosen)),
                "chosen_actual_pnl_sum": float(
                    numeric_series(chosen, "horizon_actual_pnl", default=0.0).sum()
                ),
                "chosen_actual_pnl_mean": float(
                    numeric_series(chosen, "horizon_actual_pnl", default=0.0).mean()
                )
                if len(chosen)
                else float("nan"),
                "chosen_60m_count": int(
                    numeric_series(chosen, "hv_chosen_horizon_minutes").eq(60.0).sum()
                ),
                "chosen_240m_count": int(
                    numeric_series(chosen, "hv_chosen_horizon_minutes").eq(240.0).sum()
                ),
                "chosen_720m_count": int(
                    numeric_series(chosen, "hv_chosen_horizon_minutes").eq(720.0).sum()
                ),
            }
        )
    return pd.DataFrame(rows)


def run_experiment(args: argparse.Namespace) -> Path:
    horizons = parse_int_csv(args.horizons)
    context_specs = parse_context_specs(args.context_specs)
    residual_context_specs = parse_context_specs(args.residual_context_specs)
    score_modes = parse_csv(args.score_modes)
    broad_train_rows = pd.read_csv(args.broad_train_rows)
    eval_rows = pd.read_csv(args.predictions)

    train_examples = expand_horizon_examples(
        broad_train_rows,
        horizons=horizons,
        min_executable_pnl=args.min_executable_pnl,
        tail_loss_threshold=args.tail_loss_threshold,
        min_delta_vs_60=args.min_delta_vs_60,
    )
    eval_examples = expand_horizon_examples(
        eval_rows,
        horizons=horizons,
        min_executable_pnl=args.min_executable_pnl,
        tail_loss_threshold=args.tail_loss_threshold,
        min_delta_vs_60=args.min_delta_vs_60,
    )
    train_examples = add_prior_features_to_examples(
        train_examples,
        broad_train_rows,
        context_specs=context_specs,
        min_prior_rows=args.min_prior_rows,
        min_prior_months=args.min_prior_months,
        shrinkage_count=args.shrinkage_count,
        tail_loss_threshold=args.tail_loss_threshold,
        negative_pnl_weight=args.negative_pnl_weight,
        underperform_weight=args.underperform_weight,
        loss_rate_weight=args.loss_rate_weight,
        tail_loss_rate_weight=args.tail_loss_rate_weight,
    )
    eval_examples = add_prior_features_to_examples(
        eval_examples,
        broad_train_rows,
        context_specs=context_specs,
        min_prior_rows=args.min_prior_rows,
        min_prior_months=args.min_prior_months,
        shrinkage_count=args.shrinkage_count,
        tail_loss_threshold=args.tail_loss_threshold,
        negative_pnl_weight=args.negative_pnl_weight,
        underperform_weight=args.underperform_weight,
        loss_rate_weight=args.loss_rate_weight,
        tail_loss_rate_weight=args.tail_loss_rate_weight,
    )
    train_examples = add_residual_prior_columns(
        train_examples,
        train_examples,
        context_specs=residual_context_specs,
        min_prior_rows=args.min_residual_prior_rows,
        min_prior_months=args.min_residual_prior_months,
        shrinkage_count=args.residual_shrinkage_count,
        tail_loss_threshold=args.tail_loss_threshold,
        min_executable_pnl=args.min_executable_pnl,
    )
    eval_examples = add_residual_prior_columns(
        eval_examples,
        train_examples,
        context_specs=residual_context_specs,
        min_prior_rows=args.min_residual_prior_rows,
        min_prior_months=args.min_residual_prior_months,
        shrinkage_count=args.residual_shrinkage_count,
        tail_loss_threshold=args.tail_loss_threshold,
        min_executable_pnl=args.min_executable_pnl,
    )
    numeric_features = available_features(
        train_examples,
        parse_csv(args.numeric_features),
        DEFAULT_HORIZON_NUMERIC_FEATURES,
    )
    categorical_features = available_features(
        train_examples,
        parse_csv(args.categorical_features),
        DEFAULT_HORIZON_CATEGORICAL_FEATURES,
    )
    scored_examples, folds = chronological_ranker_predictions(
        train_examples=train_examples,
        eval_examples=eval_examples,
        min_train_months=args.min_train_months,
        min_train_rows=args.min_train_rows,
        max_train_rows=args.max_train_rows,
        numeric_features=numeric_features,
        categorical_features=categorical_features,
        max_iter=args.max_iter,
        learning_rate=args.learning_rate,
        l2_regularization=args.l2_regularization,
        max_leaf_nodes=args.max_leaf_nodes,
        random_state=args.random_state,
    )
    metrics = metric_summary(scored_examples)

    base_monthly = read_base_monthly(
        args.base_monthly_metrics,
        candidate=args.candidate,
        variant_contains=args.variant_contains,
        entry_block_rule=args.base_entry_block_rule,
    )
    base_trades = read_base_trades(
        args.base_trades,
        candidate=args.candidate,
        variant_contains=args.variant_contains,
        entry_block_rule=args.base_entry_block_rule,
    )
    run_dir = make_run_dir(args.output_dir, args.label)
    train_examples.to_csv(run_dir / "broad_prior_horizon_choice_train_examples.csv", index=False)
    scored_examples.to_csv(run_dir / "broad_prior_horizon_choice_scored_examples.csv", index=False)
    folds.to_csv(run_dir / "broad_prior_horizon_choice_fold_summary.csv", index=False)
    metrics.to_csv(run_dir / "broad_prior_horizon_choice_metric_summary.csv", index=False)

    summary_frames: list[pd.DataFrame] = []
    monthly_frames: list[pd.DataFrame] = []
    addition_frames: list[pd.DataFrame] = []
    rejection_frames: list[pd.DataFrame] = []
    choice_summary_frames: list[pd.DataFrame] = []
    for score_mode in score_modes:
        scored_for_mode = scored_examples.copy()
        scored_for_mode["ranker_choice_score"] = score_predictions(
            scored_for_mode,
            score_mode=score_mode,
            delta_weight=args.delta_weight,
            beats60_weight=args.beats60_weight,
            tail_score_weight=args.tail_score_weight,
            lower_bound_mae_weight=args.lower_bound_mae_weight,
            lower_bound_bias_weight=args.lower_bound_bias_weight,
            lower_bound_tail_miss_weight=args.lower_bound_tail_miss_weight,
        )
        choice_summary_frames.append(
            summarize_ranker_choices(scored_for_mode, score_mode=score_mode)
        )
        prediction_rows = pivot_ranker_predictions(
            eval_rows,
            scored_for_mode,
            horizons=horizons,
            score_mode=score_mode,
            delta_weight=args.delta_weight,
            beats60_weight=args.beats60_weight,
            tail_score_weight=args.tail_score_weight,
            lower_bound_mae_weight=args.lower_bound_mae_weight,
            lower_bound_bias_weight=args.lower_bound_bias_weight,
            lower_bound_tail_miss_weight=args.lower_bound_tail_miss_weight,
        )
        prediction_path = run_dir / f"ranker_predictions_{score_mode}.csv"
        prediction_rows.to_csv(prediction_path, index=False)
        choices = read_choice_candidates(
            prediction_path,
            row_scopes=parse_csv(args.row_scopes),
            target_only=args.target_only,
            choice_input_mode="row_horizon_grid",
            prob_thresholds=parse_float_csv(args.prob_thresholds),
            ev_thresholds=parse_float_csv(args.ev_thresholds),
            tail_prob_thresholds=parse_float_csv(args.tail_prob_thresholds),
            require_model_used_options=parse_bool_csv(args.require_model_used_options),
        )
        choices["ranker_score_mode"] = score_mode
        choices = add_repair_utility_columns(
            base_monthly,
            choices,
            min_month_trades=args.min_month_trades,
            max_side_trade_share=args.max_side_trade_share,
            repair_support_weight=args.repair_support_weight,
            repair_expected_pnl_weight=args.repair_expected_pnl_weight,
            repair_tail_penalty_weight=args.repair_tail_penalty_weight,
            repair_horizon_penalty_weight=args.repair_horizon_penalty_weight,
        )
        choices.to_csv(run_dir / f"ranker_replay_candidates_{score_mode}.csv", index=False)
        summary, monthly, additions, rejections = replay_scenarios(
            base_monthly,
            base_trades,
            choices,
            min_total_pnl=args.min_total_pnl,
            min_role_total_pnl=args.min_role_total_pnl,
            month_floor=args.month_floor,
            shallow_month_floor=args.shallow_month_floor,
            min_role_trades=args.min_role_trades,
            min_month_trades=args.min_month_trades,
            max_side_trade_share=args.max_side_trade_share,
            cap_to_extra_side_needed=args.cap_to_extra_side_needed,
            overlap_key_columns=parse_csv(args.overlap_keys),
            selection_mode="repair_score",
            repair_support_weight=args.repair_support_weight,
            repair_expected_pnl_weight=args.repair_expected_pnl_weight,
            repair_tail_penalty_weight=args.repair_tail_penalty_weight,
            repair_horizon_penalty_weight=args.repair_horizon_penalty_weight,
            min_chosen_pred_pnl=args.min_chosen_pred_pnl,
            min_chosen_actual_pnl=None,
            max_chosen_tail_prob=args.max_chosen_tail_prob,
        )
        for frame in [summary, monthly, additions, rejections]:
            if not frame.empty:
                frame["ranker_score_mode"] = score_mode
                if "scenario_label" in frame.columns:
                    frame["scenario_label"] = (
                        frame["scenario_label"].astype(str) + f"_ranker_{score_mode}"
                    )
        summary_frames.append(summary)
        monthly_frames.append(monthly)
        addition_frames.append(additions)
        rejection_frames.append(rejections)

    summary_all = pd.concat(summary_frames, ignore_index=True) if summary_frames else pd.DataFrame()
    monthly_all = pd.concat(monthly_frames, ignore_index=True) if monthly_frames else pd.DataFrame()
    additions_all = (
        pd.concat(addition_frames, ignore_index=True) if addition_frames else pd.DataFrame()
    )
    rejections_all = (
        pd.concat(rejection_frames, ignore_index=True) if rejection_frames else pd.DataFrame()
    )
    choice_summary = (
        pd.concat(choice_summary_frames, ignore_index=True)
        if choice_summary_frames
        else pd.DataFrame()
    )
    summary_all.to_csv(run_dir / "broad_prior_horizon_choice_replay_summary.csv", index=False)
    monthly_all.to_csv(run_dir / "broad_prior_horizon_choice_monthly_metrics.csv", index=False)
    additions_all.to_csv(run_dir / "broad_prior_horizon_choice_additions.csv", index=False)
    rejections_all.to_csv(run_dir / "broad_prior_horizon_choice_rejections.csv", index=False)
    choice_summary.to_csv(run_dir / "broad_prior_horizon_choice_selection_summary.csv", index=False)

    config = {
        "base_monthly_metrics": args.base_monthly_metrics,
        "base_trades": args.base_trades,
        "predictions": args.predictions,
        "broad_train_rows": args.broad_train_rows,
        "horizons": horizons,
        "score_modes": score_modes,
        "numeric_features": numeric_features,
        "categorical_features": categorical_features,
        "min_train_months": args.min_train_months,
        "min_train_rows": args.min_train_rows,
        "max_train_rows": args.max_train_rows,
        "max_iter": args.max_iter,
        "learning_rate": args.learning_rate,
        "l2_regularization": args.l2_regularization,
        "max_leaf_nodes": args.max_leaf_nodes,
        "random_state": args.random_state,
        "context_specs": context_specs,
        "residual_context_specs": residual_context_specs,
        "min_prior_rows": args.min_prior_rows,
        "min_prior_months": args.min_prior_months,
        "shrinkage_count": args.shrinkage_count,
        "tail_loss_threshold": args.tail_loss_threshold,
        "negative_pnl_weight": args.negative_pnl_weight,
        "underperform_weight": args.underperform_weight,
        "loss_rate_weight": args.loss_rate_weight,
        "tail_loss_rate_weight": args.tail_loss_rate_weight,
        "min_residual_prior_rows": args.min_residual_prior_rows,
        "min_residual_prior_months": args.min_residual_prior_months,
        "residual_shrinkage_count": args.residual_shrinkage_count,
        "delta_weight": args.delta_weight,
        "beats60_weight": args.beats60_weight,
        "tail_score_weight": args.tail_score_weight,
        "lower_bound_mae_weight": args.lower_bound_mae_weight,
        "lower_bound_bias_weight": args.lower_bound_bias_weight,
        "lower_bound_tail_miss_weight": args.lower_bound_tail_miss_weight,
        "prob_thresholds": args.prob_thresholds,
        "ev_thresholds": args.ev_thresholds,
        "tail_prob_thresholds": args.tail_prob_thresholds,
        "require_model_used_options": args.require_model_used_options,
        "row_scopes": args.row_scopes,
        "target_only": args.target_only,
        "candidate": args.candidate,
        "variant_contains": args.variant_contains,
        "base_entry_block_rule": args.base_entry_block_rule,
    }
    (run_dir / "config.json").write_text(
        json.dumps(config, indent=2, sort_keys=True, default=local_json_default) + "\n",
        encoding="utf-8",
    )

    print("Broad prior horizon-choice replay summary:")
    if summary_all.empty:
        print("empty summary")
    else:
        print(
            summary_all[
                [
                    "ranker_score_mode",
                    "scenario_label",
                    "selector_pass",
                    "blockers",
                    "added_count",
                    "added_pnl",
                    "combined_total_pnl",
                    "month_pnl_min",
                    "role_total_pnl_min",
                    "remaining_extra_trades_needed",
                    "remaining_month_pnl_hurdle_sum",
                ]
            ]
            .head(args.print_top)
            .to_string(index=False)
        )
    print(f"artifacts: {run_dir}")
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-monthly-metrics", type=Path, required=True)
    parser.add_argument("--base-trades", type=Path, required=True)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--broad-train-rows", type=Path, required=True)
    parser.add_argument("--horizons", default=DEFAULT_HORIZONS)
    parser.add_argument(
        "--candidate",
        default="q95_sg95_rank90_floor5_side_regime_session_month",
    )
    parser.add_argument(
        "--variant-contains",
        default="loss_exit30_cd15__holdext_isolated_large_loss_long_t-5_h720",
    )
    parser.add_argument("--base-entry-block-rule", default="long_range_normal_ny_fixed60_pred_gt0")
    parser.add_argument("--row-scopes", default="available_candidates,greedy_selected")
    parser.add_argument("--score-modes", default=DEFAULT_SCORE_MODES)
    parser.add_argument("--prob-thresholds", default=DEFAULT_PROB_THRESHOLDS)
    parser.add_argument("--ev-thresholds", default=DEFAULT_EV_THRESHOLDS)
    parser.add_argument("--tail-prob-thresholds", default=DEFAULT_TAIL_PROB_THRESHOLDS)
    parser.add_argument("--require-model-used-options", default="true")
    parser.add_argument("--context-specs", default=DEFAULT_CONTEXT_SPECS)
    parser.add_argument("--residual-context-specs", default=DEFAULT_RESIDUAL_CONTEXT_SPECS)
    parser.add_argument("--min-prior-rows", type=int, default=20)
    parser.add_argument("--min-prior-months", type=int, default=2)
    parser.add_argument("--shrinkage-count", type=float, default=20.0)
    parser.add_argument("--min-executable-pnl", type=float, default=0.0)
    parser.add_argument("--tail-loss-threshold", type=float, default=-5.0)
    parser.add_argument("--min-delta-vs-60", type=float, default=0.0)
    parser.add_argument("--negative-pnl-weight", type=float, default=1.0)
    parser.add_argument("--underperform-weight", type=float, default=1.0)
    parser.add_argument("--loss-rate-weight", type=float, default=0.0)
    parser.add_argument("--tail-loss-rate-weight", type=float, default=5.0)
    parser.add_argument("--min-residual-prior-rows", type=int, default=20)
    parser.add_argument("--min-residual-prior-months", type=int, default=2)
    parser.add_argument("--residual-shrinkage-count", type=float, default=20.0)
    parser.add_argument("--delta-weight", type=float, default=0.25)
    parser.add_argument("--beats60-weight", type=float, default=0.5)
    parser.add_argument("--tail-score-weight", type=float, default=2.0)
    parser.add_argument("--lower-bound-mae-weight", type=float, default=0.25)
    parser.add_argument("--lower-bound-bias-weight", type=float, default=0.25)
    parser.add_argument("--lower-bound-tail-miss-weight", type=float, default=5.0)
    parser.add_argument("--min-train-months", type=int, default=2)
    parser.add_argument("--min-train-rows", type=int, default=200)
    parser.add_argument("--max-train-rows", type=int, default=80000)
    parser.add_argument("--numeric-features", default="")
    parser.add_argument("--categorical-features", default="")
    parser.add_argument("--max-iter", type=int, default=80)
    parser.add_argument("--learning-rate", type=float, default=0.05)
    parser.add_argument("--l2-regularization", type=float, default=1.0)
    parser.add_argument("--max-leaf-nodes", type=int, default=8)
    parser.add_argument("--random-state", type=int, default=42)
    parser.add_argument("--min-chosen-pred-pnl", type=float, default=0.0)
    parser.add_argument("--max-chosen-tail-prob", type=float, default=0.3)
    parser.add_argument("--repair-support-weight", type=float, default=1.0)
    parser.add_argument("--repair-expected-pnl-weight", type=float, default=1.0)
    parser.add_argument("--repair-tail-penalty-weight", type=float, default=1.0)
    parser.add_argument("--repair-horizon-penalty-weight", type=float, default=0.0)
    parser.add_argument("--target-only", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument(
        "--cap-to-extra-side-needed",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    parser.add_argument("--overlap-keys", default="role")
    parser.add_argument("--min-total-pnl", type=float, default=0.0)
    parser.add_argument("--min-role-total-pnl", type=float, default=0.0)
    parser.add_argument("--month-floor", type=float, default=0.0)
    parser.add_argument("--shallow-month-floor", type=float, default=-1.0)
    parser.add_argument("--min-role-trades", type=int, default=4)
    parser.add_argument("--min-month-trades", type=int, default=1)
    parser.add_argument("--max-side-trade-share", type=float, default=0.95)
    parser.add_argument("--output-dir", type=Path, default=Path("data/reports/backtests"))
    parser.add_argument("--label", default="entry_ev_broad_prior_horizon_choice_replay")
    parser.add_argument("--print-top", type=int, default=30)
    return parser


def main(argv: list[str] | None = None) -> int:
    run_experiment(build_parser().parse_args(argv))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
