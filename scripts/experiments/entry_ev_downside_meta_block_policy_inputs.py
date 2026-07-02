#!/usr/bin/env python3
"""Build downside-meta side-block input columns for entry-EV prediction parquets."""

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
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from trade_data.backtest import make_run_dir  # noqa: E402

from entry_ev_supervised_shrinkage_policy_inputs import (  # noqa: E402
    decision_hour_features,
    local_json_default,
    numeric_series,
    parse_csv,
    parse_family_predictions,
    read_trade_frames,
    side_numeric,
    text_series,
)
from entry_ev_scale_quantile_diagnostics import month_series  # noqa: E402


DEFAULT_OUTPUT_PREFIX = "pred_downside_meta"
DEFAULT_THRESHOLDS = "0.25,0.5,1,2,3,5"

NUMERIC_FEATURES = (
    "side_sign",
    "decision_hour_sin",
    "decision_hour_cos",
    "raw_pred_ev",
    "opposite_pred_ev",
    "raw_side_gap",
    "raw_selected_side_match",
    "side_entry_rank",
    "opposite_entry_rank",
    "pred_side_holding_minutes",
    "pred_opposite_holding_minutes",
    "side_time_exit_prob",
    "opposite_time_exit_prob",
    "side_loss_first_prob",
    "opposite_loss_first_prob",
    "pred_side_fixed_60m",
    "pred_side_fixed_240m",
    "pred_side_fixed_720m",
    "pred_opposite_fixed_60m",
    "pred_opposite_fixed_240m",
    "pred_opposite_fixed_720m",
    "pred_best_side_prob_taken",
    "pred_best_side_prob_opposite",
    "shrink_score",
    "opposite_shrink_score",
    "shrink_side_gap",
    "shrink_raw_target",
    "shrink_score_ratio",
)
CATEGORICAL_FEATURES = ("family", "side", "combined_regime", "session_regime")


def parse_float_csv(value: str) -> list[float]:
    return [float(part) for part in parse_csv(value)]


def threshold_label(value: float) -> str:
    text = f"{value:g}".replace("-", "neg").replace(".", "p")
    return text


def normalize_train_frame(
    frame: pd.DataFrame,
    *,
    target_mode: str,
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
        "pred_opposite_ev",
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"train trades missing columns: {', '.join(missing)}")
    output = frame.copy()
    if "supervised_target_mode" in output.columns:
        output = output[output["supervised_target_mode"].astype(str).eq(target_mode)].copy()
    output["month"] = output["month"].astype(str).str.slice(0, 7)
    output["candidate"] = output["candidate"].astype(str)
    output["role"] = output["role"].astype(str)
    output["family"] = text_series(output, "family")
    output["direction"] = output["direction"].astype(str).str.lower()
    output["entry_decision_timestamp"] = pd.to_datetime(
        output["entry_decision_timestamp"],
        utc=True,
        errors="coerce",
    )
    output["adjusted_pnl"] = numeric_series(output, "adjusted_pnl", default=0.0)
    if candidates:
        output = output[output["candidate"].isin(candidates)].copy()
    if roles:
        output = output[output["role"].isin(roles)].copy()
    if months:
        output = output[output["month"].isin(months)].copy()
    if output.empty:
        raise ValueError("no train trades remain after filters")
    return output.sort_values(["month", "entry_decision_timestamp"]).reset_index(drop=True)


def side_value_from_direction(
    frame: pd.DataFrame,
    *,
    direction: pd.Series,
    long_column: str,
    short_column: str,
    default: float = np.nan,
) -> pd.Series:
    long_values = numeric_series(frame, long_column, default=default)
    short_values = numeric_series(frame, short_column, default=default)
    return pd.Series(
        np.where(direction.eq("long"), long_values, short_values),
        index=frame.index,
        dtype=float,
    )


def opposite_value_from_direction(
    frame: pd.DataFrame,
    *,
    direction: pd.Series,
    long_column: str,
    short_column: str,
    default: float = np.nan,
) -> pd.Series:
    long_values = numeric_series(frame, long_column, default=default)
    short_values = numeric_series(frame, short_column, default=default)
    return pd.Series(
        np.where(direction.eq("long"), short_values, long_values),
        index=frame.index,
        dtype=float,
    )


def build_train_rows(
    frame: pd.DataFrame,
    *,
    shrink_score_column: str,
    shrink_raw_target_column: str,
    downside_threshold: float,
) -> pd.DataFrame:
    direction = frame["direction"].astype(str).str.lower()
    raw_ev = numeric_series(frame, "pred_taken_ev", default=np.nan)
    opposite_ev = numeric_series(frame, "pred_opposite_ev", default=np.nan)
    shrink_score = numeric_series(frame, shrink_score_column, default=np.nan)
    hour_sin, hour_cos = decision_hour_features(frame, "entry_decision_timestamp")
    pnl = numeric_series(frame, "adjusted_pnl", default=0.0)
    rows = pd.DataFrame(
        {
            "family": text_series(frame, "family").to_numpy(),
            "month": frame["month"].astype(str).to_numpy(),
            "side": direction.to_numpy(),
            "side_sign": np.where(direction.eq("long"), 1.0, -1.0),
            "combined_regime": text_series(frame, "combined_regime").to_numpy(),
            "session_regime": text_series(frame, "session_regime").to_numpy(),
            "decision_hour_sin": hour_sin.to_numpy(),
            "decision_hour_cos": hour_cos.to_numpy(),
            "raw_pred_ev": raw_ev.to_numpy(),
            "opposite_pred_ev": opposite_ev.to_numpy(),
            "raw_side_gap": (raw_ev - opposite_ev).abs().to_numpy(),
            "raw_selected_side_match": numeric_series(
                frame,
                "predicted_side_matches_trade",
                default=1.0,
            ).to_numpy(),
            "side_entry_rank": numeric_series(
                frame,
                "pred_taken_entry_local_rank",
                default=np.nan,
            ).to_numpy(),
            "opposite_entry_rank": opposite_value_from_direction(
                frame,
                direction=direction,
                long_column="pred_long_entry_local_rank",
                short_column="pred_short_entry_local_rank",
            ).to_numpy(),
            "pred_side_holding_minutes": numeric_series(
                frame,
                "selected_pred_mlp_exit_minutes",
                default=np.nan,
            ).to_numpy(),
            "pred_opposite_holding_minutes": opposite_value_from_direction(
                frame,
                direction=direction,
                long_column="pred_mlp_long_exit_event_minutes",
                short_column="pred_mlp_short_exit_event_minutes",
            ).to_numpy(),
            "side_time_exit_prob": numeric_series(
                frame,
                "selected_time_exit_prob",
                default=np.nan,
            ).to_numpy(),
            "opposite_time_exit_prob": opposite_value_from_direction(
                frame,
                direction=direction,
                long_column="pred_long_exit_event_prob_0",
                short_column="pred_short_exit_event_prob_0",
            ).to_numpy(),
            "side_loss_first_prob": numeric_series(
                frame,
                "selected_loss_first_prob",
                default=np.nan,
            ).to_numpy(),
            "opposite_loss_first_prob": opposite_value_from_direction(
                frame,
                direction=direction,
                long_column="pred_long_exit_event_prob_2",
                short_column="pred_short_exit_event_prob_2",
            ).to_numpy(),
            "pred_side_fixed_60m": numeric_series(
                frame,
                "selected_fixed_60m_pred_pnl",
                default=np.nan,
            ).to_numpy(),
            "pred_side_fixed_240m": numeric_series(
                frame,
                "selected_fixed_240m_pred_pnl",
                default=np.nan,
            ).to_numpy(),
            "pred_side_fixed_720m": numeric_series(
                frame,
                "selected_fixed_720m_pred_pnl",
                default=np.nan,
            ).to_numpy(),
            "pred_opposite_fixed_60m": opposite_value_from_direction(
                frame,
                direction=direction,
                long_column="pred_long_fixed_60m_adjusted_pnl",
                short_column="pred_short_fixed_60m_adjusted_pnl",
            ).to_numpy(),
            "pred_opposite_fixed_240m": opposite_value_from_direction(
                frame,
                direction=direction,
                long_column="pred_long_fixed_240m_adjusted_pnl",
                short_column="pred_short_fixed_240m_adjusted_pnl",
            ).to_numpy(),
            "pred_opposite_fixed_720m": opposite_value_from_direction(
                frame,
                direction=direction,
                long_column="pred_long_fixed_720m_adjusted_pnl",
                short_column="pred_short_fixed_720m_adjusted_pnl",
            ).to_numpy(),
            "pred_best_side_prob_taken": side_value_from_direction(
                frame,
                direction=direction,
                long_column="pred_best_side_prob_1",
                short_column="pred_best_side_prob_-1",
            ).to_numpy(),
            "pred_best_side_prob_opposite": opposite_value_from_direction(
                frame,
                direction=direction,
                long_column="pred_best_side_prob_1",
                short_column="pred_best_side_prob_-1",
            ).to_numpy(),
            "shrink_score": shrink_score.to_numpy(),
            "opposite_shrink_score": np.nan,
            "shrink_side_gap": np.nan,
            "shrink_raw_target": numeric_series(
                frame,
                shrink_raw_target_column,
                default=np.nan,
            ).to_numpy(),
            "shrink_score_ratio": (shrink_score / raw_ev.replace(0.0, np.nan)).to_numpy(),
            "adjusted_pnl": pnl.to_numpy(),
            "target_downside": np.maximum(0.0, downside_threshold - pnl).to_numpy(),
        }
    )
    rows["opposite_shrink_score"] = rows["opposite_pred_ev"]
    rows["shrink_side_gap"] = (rows["shrink_score"] - rows["opposite_shrink_score"]).abs()
    return rows


def side_rows_for_family(
    predictions: pd.DataFrame,
    *,
    family: str,
    long_column: str,
    short_column: str,
    long_rank_column: str,
    short_rank_column: str,
    long_holding_column: str,
    short_holding_column: str,
    long_shrink_column: str,
    short_shrink_column: str,
) -> pd.DataFrame:
    missing = sorted(
        {long_column, short_column, long_shrink_column, short_shrink_column}
        - set(predictions.columns)
    )
    if missing:
        raise ValueError(f"{family} predictions missing columns: {', '.join(missing)}")
    months = month_series(predictions).astype(str).str.slice(0, 7)
    hour_sin, hour_cos = decision_hour_features(predictions, "decision_timestamp")
    combined_regime = text_series(predictions, "combined_regime")
    session_regime = text_series(predictions, "session_regime")
    long_raw = numeric_series(predictions, long_column, default=np.nan)
    short_raw = numeric_series(predictions, short_column, default=np.nan)
    long_shrink = numeric_series(predictions, long_shrink_column, default=np.nan)
    short_shrink = numeric_series(predictions, short_shrink_column, default=np.nan)
    selected_side = np.where(long_raw >= short_raw, "long", "short")

    rows: list[pd.DataFrame] = []
    for side in ["long", "short"]:
        opposite = "short" if side == "long" else "long"
        raw = side_numeric(
            predictions,
            side=side,
            long_column=long_column,
            short_column=short_column,
        )
        opposite_raw = side_numeric(
            predictions,
            side=opposite,
            long_column=long_column,
            short_column=short_column,
        )
        shrink = side_numeric(
            predictions,
            side=side,
            long_column=long_shrink_column,
            short_column=short_shrink_column,
        )
        opposite_shrink = side_numeric(
            predictions,
            side=opposite,
            long_column=long_shrink_column,
            short_column=short_shrink_column,
        )
        rows.append(
            pd.DataFrame(
                {
                    "family": family,
                    "_row_id": np.arange(len(predictions), dtype=int),
                    "month": months.to_numpy(),
                    "side": side,
                    "side_sign": 1.0 if side == "long" else -1.0,
                    "combined_regime": combined_regime.to_numpy(),
                    "session_regime": session_regime.to_numpy(),
                    "decision_hour_sin": hour_sin.to_numpy(),
                    "decision_hour_cos": hour_cos.to_numpy(),
                    "raw_pred_ev": raw.to_numpy(),
                    "opposite_pred_ev": opposite_raw.to_numpy(),
                    "raw_side_gap": (long_raw - short_raw).abs().to_numpy(),
                    "raw_selected_side_match": (selected_side == side).astype(float),
                    "side_entry_rank": side_numeric(
                        predictions,
                        side=side,
                        long_column=long_rank_column,
                        short_column=short_rank_column,
                    ).to_numpy(),
                    "opposite_entry_rank": side_numeric(
                        predictions,
                        side=opposite,
                        long_column=long_rank_column,
                        short_column=short_rank_column,
                    ).to_numpy(),
                    "pred_side_holding_minutes": side_numeric(
                        predictions,
                        side=side,
                        long_column=long_holding_column,
                        short_column=short_holding_column,
                    ).to_numpy(),
                    "pred_opposite_holding_minutes": side_numeric(
                        predictions,
                        side=opposite,
                        long_column=long_holding_column,
                        short_column=short_holding_column,
                    ).to_numpy(),
                    "side_time_exit_prob": side_numeric(
                        predictions,
                        side=side,
                        long_column="pred_long_exit_event_prob_0",
                        short_column="pred_short_exit_event_prob_0",
                    ).to_numpy(),
                    "opposite_time_exit_prob": side_numeric(
                        predictions,
                        side=opposite,
                        long_column="pred_long_exit_event_prob_0",
                        short_column="pred_short_exit_event_prob_0",
                    ).to_numpy(),
                    "side_loss_first_prob": side_numeric(
                        predictions,
                        side=side,
                        long_column="pred_long_exit_event_prob_2",
                        short_column="pred_short_exit_event_prob_2",
                    ).to_numpy(),
                    "opposite_loss_first_prob": side_numeric(
                        predictions,
                        side=opposite,
                        long_column="pred_long_exit_event_prob_2",
                        short_column="pred_short_exit_event_prob_2",
                    ).to_numpy(),
                    "pred_side_fixed_60m": side_numeric(
                        predictions,
                        side=side,
                        long_column="pred_long_fixed_60m_adjusted_pnl",
                        short_column="pred_short_fixed_60m_adjusted_pnl",
                    ).to_numpy(),
                    "pred_side_fixed_240m": side_numeric(
                        predictions,
                        side=side,
                        long_column="pred_long_fixed_240m_adjusted_pnl",
                        short_column="pred_short_fixed_240m_adjusted_pnl",
                    ).to_numpy(),
                    "pred_side_fixed_720m": side_numeric(
                        predictions,
                        side=side,
                        long_column="pred_long_fixed_720m_adjusted_pnl",
                        short_column="pred_short_fixed_720m_adjusted_pnl",
                    ).to_numpy(),
                    "pred_opposite_fixed_60m": side_numeric(
                        predictions,
                        side=opposite,
                        long_column="pred_long_fixed_60m_adjusted_pnl",
                        short_column="pred_short_fixed_60m_adjusted_pnl",
                    ).to_numpy(),
                    "pred_opposite_fixed_240m": side_numeric(
                        predictions,
                        side=opposite,
                        long_column="pred_long_fixed_240m_adjusted_pnl",
                        short_column="pred_short_fixed_240m_adjusted_pnl",
                    ).to_numpy(),
                    "pred_opposite_fixed_720m": side_numeric(
                        predictions,
                        side=opposite,
                        long_column="pred_long_fixed_720m_adjusted_pnl",
                        short_column="pred_short_fixed_720m_adjusted_pnl",
                    ).to_numpy(),
                    "pred_best_side_prob_taken": side_numeric(
                        predictions,
                        side=side,
                        long_column="pred_best_side_prob_1",
                        short_column="pred_best_side_prob_-1",
                    ).to_numpy(),
                    "pred_best_side_prob_opposite": side_numeric(
                        predictions,
                        side=opposite,
                        long_column="pred_best_side_prob_1",
                        short_column="pred_best_side_prob_-1",
                    ).to_numpy(),
                    "shrink_score": shrink.to_numpy(),
                    "opposite_shrink_score": opposite_shrink.to_numpy(),
                    "shrink_side_gap": (long_shrink - short_shrink).abs().to_numpy(),
                    "shrink_raw_target": np.nan,
                    "shrink_score_ratio": (shrink / raw.replace(0.0, np.nan)).to_numpy(),
                }
            )
        )
    return pd.concat(rows, ignore_index=True)


def feature_frame(frame: pd.DataFrame) -> pd.DataFrame:
    output = pd.DataFrame(index=frame.index)
    for column in NUMERIC_FEATURES:
        output[column] = numeric_series(frame, column, default=np.nan)
    for column in CATEGORICAL_FEATURES:
        output[column] = text_series(frame, column)
    return output


def fit_category_maps(frame: pd.DataFrame) -> dict[str, dict[str, int]]:
    maps: dict[str, dict[str, int]] = {}
    for column in CATEGORICAL_FEATURES:
        values = sorted(str(value) for value in frame[column].astype(str).unique())
        maps[column] = {value: index for index, value in enumerate(values)}
    return maps


def encode_features(
    frame: pd.DataFrame,
    *,
    category_maps: dict[str, dict[str, int]],
) -> pd.DataFrame:
    encoded = pd.DataFrame(index=frame.index)
    for column in NUMERIC_FEATURES:
        values = pd.to_numeric(frame[column], errors="coerce")
        encoded[column] = values.replace([np.inf, -np.inf], np.nan).fillna(0.0)
    for column in CATEGORICAL_FEATURES:
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
    max_iter: int,
    learning_rate: float,
    max_leaf_nodes: int,
    min_samples_leaf: int,
    l2_regularization: float,
    random_seed: int,
    max_train_rows: int,
    default_downside: float,
    max_downside_prediction: float,
) -> tuple[np.ndarray, dict[str, Any]]:
    train_fit = sample_training_rows(
        train,
        max_train_rows=max_train_rows,
        random_seed=random_seed,
    )
    y = numeric_series(train_fit, "target_downside", default=np.nan).dropna()
    train_fit = train_fit.loc[y.index].copy()
    fallback = float(default_downside)
    if y.notna().any():
        fallback = float(y.mean())
    fallback = float(np.clip(fallback, 0.0, max_downside_prediction))

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

    train_features = feature_frame(train_fit)
    target_features = feature_frame(target)
    category_maps = fit_category_maps(train_features)
    x_train = encode_features(train_features, category_maps=category_maps)
    x_target = encode_features(target_features, category_maps=category_maps)
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
    train_prediction = np.clip(
        model.predict(x_train.astype("float32").to_numpy()),
        0.0,
        max_downside_prediction,
    )
    prediction = np.clip(
        model.predict(x_target.astype("float32").to_numpy()),
        0.0,
        max_downside_prediction,
    )
    return prediction.astype(float), {
        "model_used": True,
        "train_rows_used": int(len(train_fit)),
        "train_target_mean": float(y.mean()),
        "train_target_std": float(y.std(ddof=0)),
        "train_mae": float(mean_absolute_error(y, train_prediction)),
        "train_rmse": float(mean_squared_error(y, train_prediction) ** 0.5),
        "train_r2": float(r2_score(y, train_prediction)),
    }


def chronological_downside_predictions(
    train_rows: pd.DataFrame,
    target_rows: pd.DataFrame,
    *,
    min_train_months: int,
    min_train_rows: int,
    max_train_rows: int,
    max_iter: int,
    learning_rate: float,
    max_leaf_nodes: int,
    min_samples_leaf: int,
    l2_regularization: float,
    random_seed: int,
    default_downside: float,
    max_downside_prediction: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    output = target_rows.copy()
    output["pred_downside_meta_expected_downside"] = float(default_downside)
    output["pred_downside_meta_model_used"] = False
    output["pred_downside_meta_train_rows"] = 0
    output["pred_downside_meta_train_months"] = 0
    fold_rows: list[dict[str, Any]] = []
    train_month_values = train_rows["month"].astype(str)
    train_periods = pd.PeriodIndex(train_month_values, freq="M")
    target_month_values = output["month"].astype(str)

    for month in sorted(target_month_values.unique()):
        target_period = pd.Period(month, freq="M")
        train = train_rows[train_periods < target_period].copy()
        target = output[target_month_values.eq(month)].copy()
        train_months = int(train["month"].nunique())
        if train_months >= min_train_months and len(train) >= min_train_rows:
            prediction, fit_info = fit_predict_fold(
                train,
                target,
                max_iter=max_iter,
                learning_rate=learning_rate,
                max_leaf_nodes=max_leaf_nodes,
                min_samples_leaf=min_samples_leaf,
                l2_regularization=l2_regularization,
                random_seed=random_seed,
                max_train_rows=max_train_rows,
                default_downside=default_downside,
                max_downside_prediction=max_downside_prediction,
            )
        else:
            prediction = np.full(len(target), default_downside, dtype=float)
            fit_info = {
                "model_used": False,
                "train_rows_used": int(len(train)),
                "train_target_mean": float(default_downside),
                "train_target_std": 0.0,
                "train_mae": 0.0,
                "train_rmse": 0.0,
                "train_r2": 0.0,
            }
        output.loc[target.index, "pred_downside_meta_expected_downside"] = prediction
        output.loc[target.index, "pred_downside_meta_model_used"] = bool(
            fit_info["model_used"]
        )
        output.loc[target.index, "pred_downside_meta_train_rows"] = int(len(train))
        output.loc[target.index, "pred_downside_meta_train_months"] = train_months
        fold_rows.append(
            {
                "target_month": month,
                "target_rows": int(len(target)),
                "train_rows": int(len(train)),
                "train_months": train_months,
                **fit_info,
                "pred_downside_mean": float(np.nanmean(prediction)) if len(prediction) else np.nan,
            }
        )
    return output, pd.DataFrame(fold_rows)


def threshold_summary(
    frame: pd.DataFrame,
    *,
    thresholds: list[float],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    actual = numeric_series(frame, "adjusted_pnl", default=0.0)
    score = numeric_series(frame, "pred_downside_meta_expected_downside", default=np.nan)
    total_pnl = float(actual.sum())
    total_count = int(len(frame))
    loss_count = int(actual.lt(0.0).sum())
    for threshold in thresholds:
        flagged = score.ge(threshold) & score.notna()
        flagged_actual = actual[flagged]
        flagged_count = int(flagged.sum())
        flagged_pnl = float(flagged_actual.sum())
        flagged_loss_count = int(flagged_actual.lt(0.0).sum())
        rows.append(
            {
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


def attach_predictions_to_families(
    family_frames: dict[str, pd.DataFrame],
    scored_rows: pd.DataFrame,
    *,
    thresholds: list[float],
    output_prefix: str,
) -> dict[str, pd.DataFrame]:
    outputs: dict[str, pd.DataFrame] = {}
    for family, frame in family_frames.items():
        enriched = frame.copy()
        for side in ["long", "short"]:
            side_rows = scored_rows[
                scored_rows["family"].eq(family) & scored_rows["side"].eq(side)
            ].sort_values("_row_id")
            if len(side_rows) != len(enriched):
                raise ValueError(
                    f"{family}/{side} scored row count {len(side_rows)} "
                    f"does not match predictions {len(enriched)}"
                )
            side_prefix = f"{output_prefix}_{side}"
            downside = side_rows["pred_downside_meta_expected_downside"].astype(float)
            enriched[f"{side_prefix}_expected_downside"] = downside.to_numpy()
            enriched[f"{side_prefix}_model_used"] = side_rows[
                "pred_downside_meta_model_used"
            ].to_numpy()
            enriched[f"{side_prefix}_train_rows"] = side_rows[
                "pred_downside_meta_train_rows"
            ].to_numpy()
            enriched[f"{side_prefix}_train_months"] = side_rows[
                "pred_downside_meta_train_months"
            ].to_numpy()
            for threshold in thresholds:
                enriched[f"{side_prefix}_block_gte_{threshold_label(threshold)}"] = (
                    downside.ge(threshold).astype("int8").to_numpy()
                )
        outputs[family] = enriched
    return outputs


def prediction_block_summary(
    outputs: dict[str, pd.DataFrame],
    *,
    thresholds: list[float],
    output_prefix: str,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for family, frame in outputs.items():
        months = month_series(frame).astype(str).str.slice(0, 7)
        for month, group in frame.groupby(months, dropna=False):
            row: dict[str, Any] = {
                "family": family,
                "month": month,
                "row_count": int(len(group)),
                "long_expected_downside_mean": float(
                    group[f"{output_prefix}_long_expected_downside"].astype(float).mean()
                ),
                "short_expected_downside_mean": float(
                    group[f"{output_prefix}_short_expected_downside"].astype(float).mean()
                ),
            }
            for threshold in thresholds:
                label = threshold_label(threshold)
                row[f"long_block_gte_{label}_share"] = float(
                    group[f"{output_prefix}_long_block_gte_{label}"].astype(float).mean()
                )
                row[f"short_block_gte_{label}_share"] = float(
                    group[f"{output_prefix}_short_block_gte_{label}"].astype(float).mean()
                )
            rows.append(row)
    return pd.DataFrame(rows).sort_values(["family", "month"]).reset_index(drop=True)


def build_downside_meta_inputs(args: argparse.Namespace) -> Path:
    thresholds = parse_float_csv(args.thresholds)
    train = normalize_train_frame(
        read_trade_frames(args.train_trades),
        target_mode=args.train_target_mode,
        candidates=set(parse_csv(args.train_candidates)),
        roles=set(parse_csv(args.train_roles)),
        months=set(parse_csv(args.train_months)),
    )
    train_rows = build_train_rows(
        train,
        shrink_score_column=args.train_shrink_score_column,
        shrink_raw_target_column=args.train_shrink_raw_target_column,
        downside_threshold=args.downside_threshold,
    )
    family_paths = parse_family_predictions(args.family_predictions)
    family_frames: dict[str, pd.DataFrame] = {}
    side_frames: list[pd.DataFrame] = []
    for family, path in family_paths.items():
        frame = pd.read_parquet(path)
        family_frames[family] = frame
        side_frames.append(
            side_rows_for_family(
                frame,
                family=family,
                long_column=args.long_column,
                short_column=args.short_column,
                long_rank_column=args.long_rank_column,
                short_rank_column=args.short_rank_column,
                long_holding_column=args.long_holding_column,
                short_holding_column=args.short_holding_column,
                long_shrink_column=args.long_shrink_column,
                short_shrink_column=args.short_shrink_column,
            )
        )
    target_rows = pd.concat(side_frames, ignore_index=True)
    scored_rows, fold_summary = chronological_downside_predictions(
        train_rows,
        target_rows,
        min_train_months=args.min_train_months,
        min_train_rows=args.min_train_rows,
        max_train_rows=args.max_train_rows,
        max_iter=args.max_iter,
        learning_rate=args.learning_rate,
        max_leaf_nodes=args.max_leaf_nodes,
        min_samples_leaf=args.min_samples_leaf,
        l2_regularization=args.l2_regularization,
        random_seed=args.random_seed,
        default_downside=args.default_downside,
        max_downside_prediction=args.max_downside_prediction,
    )
    train_oof, train_oof_folds = chronological_downside_predictions(
        train_rows,
        train_rows,
        min_train_months=args.min_train_months,
        min_train_rows=args.min_train_rows,
        max_train_rows=args.max_train_rows,
        max_iter=args.max_iter,
        learning_rate=args.learning_rate,
        max_leaf_nodes=args.max_leaf_nodes,
        min_samples_leaf=args.min_samples_leaf,
        l2_regularization=args.l2_regularization,
        random_seed=args.random_seed,
        default_downside=args.default_downside,
        max_downside_prediction=args.max_downside_prediction,
    )
    outputs = attach_predictions_to_families(
        family_frames,
        scored_rows,
        thresholds=thresholds,
        output_prefix=args.output_prefix,
    )

    run_dir = make_run_dir(args.output_dir, args.label)
    prediction_dir = run_dir / "enriched_predictions"
    prediction_dir.mkdir(parents=True, exist_ok=True)
    output_paths: dict[str, Path] = {}
    for family, frame in outputs.items():
        path = prediction_dir / f"{family}_predictions_downside_meta.parquet"
        frame.to_parquet(path, index=False)
        output_paths[family] = path

    scored_rows.to_parquet(run_dir / "downside_meta_side_rows.parquet", index=False)
    fold_summary.to_csv(run_dir / "downside_meta_fold_summary.csv", index=False)
    train_oof.to_csv(run_dir / "downside_meta_train_oof_predictions.csv", index=False)
    train_oof_folds.to_csv(run_dir / "downside_meta_train_oof_folds.csv", index=False)
    threshold_summary(train_oof, thresholds=thresholds).to_csv(
        run_dir / "downside_meta_train_oof_threshold_summary.csv",
        index=False,
    )
    prediction_block_summary(
        outputs,
        thresholds=thresholds,
        output_prefix=args.output_prefix,
    ).to_csv(run_dir / "prediction_downside_meta_block_summary.csv", index=False)

    config = {
        "family_predictions": family_paths,
        "output_paths": output_paths,
        "train_trades": args.train_trades,
        "train_target_mode": args.train_target_mode,
        "train_candidates": parse_csv(args.train_candidates),
        "train_roles": parse_csv(args.train_roles),
        "train_months": parse_csv(args.train_months),
        "thresholds": thresholds,
        "output_prefix": args.output_prefix,
        "downside_threshold": args.downside_threshold,
        "long_column": args.long_column,
        "short_column": args.short_column,
        "long_shrink_column": args.long_shrink_column,
        "short_shrink_column": args.short_shrink_column,
        "train_shrink_score_column": args.train_shrink_score_column,
        "train_shrink_raw_target_column": args.train_shrink_raw_target_column,
        "min_train_months": args.min_train_months,
        "min_train_rows": args.min_train_rows,
        "max_train_rows": args.max_train_rows,
        "max_iter": args.max_iter,
        "learning_rate": args.learning_rate,
        "max_leaf_nodes": args.max_leaf_nodes,
        "min_samples_leaf": args.min_samples_leaf,
        "l2_regularization": args.l2_regularization,
        "default_downside": args.default_downside,
        "max_downside_prediction": args.max_downside_prediction,
        "random_seed": args.random_seed,
    }
    (run_dir / "config.json").write_text(
        json.dumps(config, indent=2, default=local_json_default),
        encoding="utf-8",
    )

    print("Downside meta OOF threshold summary:")
    print(
        threshold_summary(train_oof, thresholds=thresholds)[
            [
                "threshold",
                "flagged_trade_count",
                "flagged_pnl",
                "kept_pnl_if_removed",
                "block_delta_if_removed",
                "flagged_loss_precision",
                "loss_recall",
            ]
        ].to_string(index=False)
    )
    print(f"artifacts: {run_dir}")
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--family-predictions", action="append", required=True)
    parser.add_argument("--train-trades", type=Path, action="append", required=True)
    parser.add_argument("--train-target-mode", default="factor")
    parser.add_argument("--train-candidates", default="")
    parser.add_argument("--train-roles", default="")
    parser.add_argument("--train-months", default="")
    parser.add_argument("--thresholds", default=DEFAULT_THRESHOLDS)
    parser.add_argument("--output-prefix", default=DEFAULT_OUTPUT_PREFIX)
    parser.add_argument("--downside-threshold", type=float, default=0.0)
    parser.add_argument("--long-column", required=True)
    parser.add_argument("--short-column", required=True)
    parser.add_argument("--long-shrink-column", default="pred_supervised_shrink_factor_long_best_adjusted_pnl")
    parser.add_argument("--short-shrink-column", default="pred_supervised_shrink_factor_short_best_adjusted_pnl")
    parser.add_argument("--train-shrink-score-column", default="pred_supervised_factor_ev")
    parser.add_argument("--train-shrink-raw-target-column", default="pred_supervised_factor_raw_target")
    parser.add_argument("--long-rank-column", default="pred_long_entry_local_rank")
    parser.add_argument("--short-rank-column", default="pred_short_entry_local_rank")
    parser.add_argument("--long-holding-column", default="pred_mlp_long_exit_event_minutes")
    parser.add_argument("--short-holding-column", default="pred_mlp_short_exit_event_minutes")
    parser.add_argument("--min-train-months", type=int, default=2)
    parser.add_argument("--min-train-rows", type=int, default=30)
    parser.add_argument("--max-train-rows", type=int, default=0)
    parser.add_argument("--max-iter", type=int, default=80)
    parser.add_argument("--learning-rate", type=float, default=0.04)
    parser.add_argument("--max-leaf-nodes", type=int, default=7)
    parser.add_argument("--min-samples-leaf", type=int, default=20)
    parser.add_argument("--l2-regularization", type=float, default=0.20)
    parser.add_argument("--default-downside", type=float, default=0.0)
    parser.add_argument("--max-downside-prediction", type=float, default=30.0)
    parser.add_argument("--random-seed", type=int, default=42)
    parser.add_argument("--output-dir", type=Path, default=Path("data/reports/backtests"))
    parser.add_argument("--label", default="entry_ev_downside_meta_block_policy_inputs")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    build_downside_meta_inputs(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
