#!/usr/bin/env python3
"""Build chronological supervised-shrinkage policy input columns for entry-EV predictions."""

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

from trade_data.backtest import json_default, make_run_dir  # noqa: E402

from entry_ev_executable_ev_policy_inputs import (  # noqa: E402
    add_executable_quantile_columns,
)
from entry_ev_scale_quantile_diagnostics import month_series, parse_scope_csv  # noqa: E402


DEFAULT_SCORE_KIND = "supervised_shrink"
DEFAULT_LONG_OUTPUT_COLUMN = "pred_supervised_shrink_long_best_adjusted_pnl"
DEFAULT_SHORT_OUTPUT_COLUMN = "pred_supervised_shrink_short_best_adjusted_pnl"
DEFAULT_QUANTILE_SCOPES = "month,side_month,side_regime_session_month"

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
)
CATEGORY_FEATURES = ("family", "side", "combined_regime", "session_regime")


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


def parse_family_predictions(values: list[str]) -> dict[str, Path]:
    families: dict[str, Path] = {}
    for value in values:
        if "=" not in value:
            raise argparse.ArgumentTypeError("family predictions must use family=path")
        family, path = value.split("=", 1)
        family = family.strip()
        if not family:
            raise argparse.ArgumentTypeError("family name must not be empty")
        families[family] = Path(path.strip())
    if not families:
        raise argparse.ArgumentTypeError("at least one family prediction is required")
    return families


def read_trade_frames(paths: list[Path]) -> pd.DataFrame:
    if not paths:
        raise ValueError("at least one --train-trades path is required")
    return pd.concat([pd.read_csv(path) for path in paths], ignore_index=True)


def numeric_series(frame: pd.DataFrame, column: str, default: float = np.nan) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=float)
    values = pd.to_numeric(frame[column], errors="coerce")
    return values.replace([np.inf, -np.inf], np.nan).fillna(default).astype(float)


def text_series(frame: pd.DataFrame, column: str, default: str = "__missing__") -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype="string")
    return (
        frame[column]
        .astype("string")
        .fillna(default)
        .str.strip()
        .replace({"": default, "nan": default, "None": default})
    )


def side_numeric(
    frame: pd.DataFrame,
    *,
    side: str,
    long_column: str,
    short_column: str,
    default: float = np.nan,
) -> pd.Series:
    column = long_column if side == "long" else short_column
    return numeric_series(frame, column, default=default)


def selected_side_numeric(
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


def opposite_side_numeric(
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


def decision_hour_features(frame: pd.DataFrame, column: str) -> tuple[pd.Series, pd.Series]:
    if column not in frame.columns:
        hours = pd.Series(0.0, index=frame.index)
    else:
        timestamp = pd.to_datetime(frame[column], utc=True, errors="coerce")
        hours = timestamp.dt.hour.fillna(0) + timestamp.dt.minute.fillna(0) / 60.0
    radians = 2.0 * np.pi * hours / 24.0
    return pd.Series(np.sin(radians), index=frame.index), pd.Series(
        np.cos(radians),
        index=frame.index,
    )


def normalize_train_trades(
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
        raise ValueError(f"train trades missing columns: {', '.join(missing)}")
    output = frame.copy()
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
    output["pred_taken_ev"] = numeric_series(output, "pred_taken_ev", default=np.nan)
    if candidates:
        output = output[output["candidate"].isin(candidates)].copy()
    if roles:
        output = output[output["role"].isin(roles)].copy()
    if months:
        output = output[output["month"].isin(months)].copy()
    if output.empty:
        raise ValueError("no train trades remain after filters")
    return output.sort_values(["month", "entry_decision_timestamp"]).reset_index(drop=True)


def train_rows_from_selected_trades(frame: pd.DataFrame) -> pd.DataFrame:
    direction = frame["direction"].astype(str).str.lower()
    hour_sin, hour_cos = decision_hour_features(frame, "entry_decision_timestamp")
    raw_ev = numeric_series(frame, "pred_taken_ev", default=np.nan)
    opposite_ev = numeric_series(frame, "pred_opposite_ev", default=np.nan)
    selected_match = numeric_series(frame, "predicted_side_matches_trade", default=1.0)

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
            "raw_selected_side_match": selected_match.to_numpy(),
            "side_entry_rank": numeric_series(
                frame,
                "pred_taken_entry_local_rank",
                default=np.nan,
            ).to_numpy(),
            "opposite_entry_rank": opposite_side_numeric(
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
            "pred_opposite_holding_minutes": opposite_side_numeric(
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
            "opposite_time_exit_prob": opposite_side_numeric(
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
            "opposite_loss_first_prob": opposite_side_numeric(
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
            "pred_opposite_fixed_60m": opposite_side_numeric(
                frame,
                direction=direction,
                long_column="pred_long_fixed_60m_adjusted_pnl",
                short_column="pred_short_fixed_60m_adjusted_pnl",
            ).to_numpy(),
            "pred_opposite_fixed_240m": opposite_side_numeric(
                frame,
                direction=direction,
                long_column="pred_long_fixed_240m_adjusted_pnl",
                short_column="pred_short_fixed_240m_adjusted_pnl",
            ).to_numpy(),
            "pred_opposite_fixed_720m": opposite_side_numeric(
                frame,
                direction=direction,
                long_column="pred_long_fixed_720m_adjusted_pnl",
                short_column="pred_short_fixed_720m_adjusted_pnl",
            ).to_numpy(),
            "pred_best_side_prob_taken": selected_side_numeric(
                frame,
                direction=direction,
                long_column="pred_best_side_prob_1",
                short_column="pred_best_side_prob_-1",
            ).to_numpy(),
            "pred_best_side_prob_opposite": opposite_side_numeric(
                frame,
                direction=direction,
                long_column="pred_best_side_prob_1",
                short_column="pred_best_side_prob_-1",
            ).to_numpy(),
            "target_pnl": numeric_series(frame, "adjusted_pnl", default=0.0).to_numpy(),
        }
    )
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
) -> pd.DataFrame:
    missing = sorted({long_column, short_column} - set(predictions.columns))
    if missing:
        raise ValueError(f"{family} predictions missing columns: {', '.join(missing)}")
    months = month_series(predictions).astype(str).str.slice(0, 7)
    hour_sin, hour_cos = decision_hour_features(predictions, "decision_timestamp")
    combined_regime = text_series(predictions, "combined_regime")
    session_regime = text_series(predictions, "session_regime")
    long_raw = numeric_series(predictions, long_column, default=np.nan)
    short_raw = numeric_series(predictions, short_column, default=np.nan)
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
                }
            )
        )
    return pd.concat(rows, ignore_index=True)


def feature_frame(frame: pd.DataFrame) -> pd.DataFrame:
    output = pd.DataFrame(index=frame.index)
    for column in NUMERIC_FEATURES:
        output[column] = numeric_series(frame, column, default=np.nan)
    for column in CATEGORY_FEATURES:
        output[column] = text_series(frame, column)
    return output


def fit_category_maps(train: pd.DataFrame) -> dict[str, dict[str, int]]:
    maps: dict[str, dict[str, int]] = {}
    for column in CATEGORY_FEATURES:
        values = sorted(str(value) for value in train[column].astype(str).unique())
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
    for column in CATEGORY_FEATURES:
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


def target_values(
    frame: pd.DataFrame,
    *,
    target_mode: str,
    min_factor: float,
    max_factor: float,
) -> pd.Series:
    if target_mode == "pnl":
        return numeric_series(frame, "target_pnl", default=0.0)
    if target_mode == "factor":
        raw = numeric_series(frame, "raw_pred_ev", default=np.nan).replace(0.0, np.nan)
        factor = numeric_series(frame, "target_pnl", default=0.0) / raw
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
        return numeric_series(frame, "raw_pred_ev", default=np.nan).to_numpy(dtype=float) * prediction
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
    train_rows: pd.DataFrame,
    target_rows: pd.DataFrame,
    *,
    target_mode: str,
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
    output = target_rows.copy()
    output["pred_supervised_shrink_score"] = np.nan
    output["pred_supervised_shrink_raw_target"] = np.nan
    output["pred_supervised_shrink_model_used"] = False
    output["pred_supervised_shrink_train_rows"] = 0
    output["pred_supervised_shrink_train_months"] = 0
    output["pred_supervised_shrink_target_mode"] = target_mode

    train_month_values = train_rows["month"].astype(str)
    train_periods = pd.PeriodIndex(train_month_values, freq="M")
    target_month_values = output["month"].astype(str)
    fold_rows: list[dict[str, Any]] = []

    for month in sorted(target_month_values.unique()):
        target_period = pd.Period(month, freq="M")
        train = train_rows[train_periods < target_period].copy()
        target = output[target_month_values.eq(month)].copy()
        train_months = int(train["month"].nunique())
        if train_months >= min_train_months and len(train) >= min_train_rows:
            prediction, fit_info = fit_predict_fold(
                train,
                target,
                target_mode=target_mode,
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
        output.loc[target.index, "pred_supervised_shrink_score"] = score
        output.loc[target.index, "pred_supervised_shrink_raw_target"] = prediction
        output.loc[target.index, "pred_supervised_shrink_model_used"] = bool(
            fit_info["model_used"]
        )
        output.loc[target.index, "pred_supervised_shrink_train_rows"] = int(len(train))
        output.loc[target.index, "pred_supervised_shrink_train_months"] = train_months
        fold_rows.append(
            {
                "target_month": month,
                "target_rows": int(len(target)),
                "train_rows": int(len(train)),
                "train_months": train_months,
                **fit_info,
                "raw_score_mean": float(
                    pd.to_numeric(target["raw_pred_ev"], errors="coerce").mean()
                ),
                "pred_score_mean": float(np.nanmean(score)) if len(score) else np.nan,
            }
        )
    return output, pd.DataFrame(fold_rows)


def attach_predictions_to_families(
    family_frames: dict[str, pd.DataFrame],
    scored_rows: pd.DataFrame,
    *,
    long_output_column: str,
    short_output_column: str,
    score_kind: str,
    long_rank_column: str,
    short_rank_column: str,
    quantile_scopes: list[str],
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
            output_column = long_output_column if side == "long" else short_output_column
            prefix = f"pred_supervised_shrink_{side}"
            enriched[output_column] = side_rows["pred_supervised_shrink_score"].to_numpy()
            enriched[f"{prefix}_raw_target"] = side_rows[
                "pred_supervised_shrink_raw_target"
            ].to_numpy()
            enriched[f"{prefix}_model_used"] = side_rows[
                "pred_supervised_shrink_model_used"
            ].to_numpy()
            enriched[f"{prefix}_train_rows"] = side_rows[
                "pred_supervised_shrink_train_rows"
            ].to_numpy()
            enriched[f"{prefix}_train_months"] = side_rows[
                "pred_supervised_shrink_train_months"
            ].to_numpy()
        enriched = add_executable_quantile_columns(
            enriched,
            family=family,
            score_kind=score_kind,
            long_output_column=long_output_column,
            short_output_column=short_output_column,
            long_rank_column=long_rank_column,
            short_rank_column=short_rank_column,
            quantile_scopes=quantile_scopes,
        )
        outputs[family] = enriched
    return outputs


def summarize_prediction_effect(
    outputs: dict[str, pd.DataFrame],
    *,
    base_long_column: str,
    base_short_column: str,
    shrink_long_column: str,
    shrink_short_column: str,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for family, frame in outputs.items():
        months = month_series(frame).astype(str).str.slice(0, 7)
        base_long = pd.to_numeric(frame[base_long_column], errors="coerce")
        base_short = pd.to_numeric(frame[base_short_column], errors="coerce")
        shrink_long = pd.to_numeric(frame[shrink_long_column], errors="coerce")
        shrink_short = pd.to_numeric(frame[shrink_short_column], errors="coerce")
        base_side = np.where(base_long >= base_short, 1, -1)
        shrink_side = np.where(shrink_long >= shrink_short, 1, -1)
        base_score = np.where(base_side == 1, base_long, base_short)
        shrink_score = np.where(shrink_side == 1, shrink_long, shrink_short)
        summary = pd.DataFrame(
            {
                "month": months,
                "base_side": base_side,
                "shrink_side": shrink_side,
                "base_score": base_score,
                "shrink_score": shrink_score,
                "base_gap": (base_long - base_short).abs(),
                "shrink_gap": (shrink_long - shrink_short).abs(),
                "long_model_used": frame[
                    "pred_supervised_shrink_long_model_used"
                ].astype(bool),
                "short_model_used": frame[
                    "pred_supervised_shrink_short_model_used"
                ].astype(bool),
            }
        )
        for month, group in summary.groupby("month", dropna=False):
            model_used = group["long_model_used"] | group["short_model_used"]
            rows.append(
                {
                    "family": family,
                    "month": month,
                    "row_count": int(len(group)),
                    "model_used_share": float(model_used.mean()),
                    "base_selected_long_share": float(group["base_side"].eq(1).mean()),
                    "shrink_selected_long_share": float(
                        group["shrink_side"].eq(1).mean()
                    ),
                    "side_switch_share": float(
                        (group["base_side"] != group["shrink_side"]).mean()
                    ),
                    "base_score_mean": float(group["base_score"].mean()),
                    "shrink_score_mean": float(group["shrink_score"].mean()),
                    "base_score_q95": float(group["base_score"].quantile(0.95)),
                    "shrink_score_q95": float(group["shrink_score"].quantile(0.95)),
                    "base_gap_q95": float(group["base_gap"].quantile(0.95)),
                    "shrink_gap_q95": float(group["shrink_gap"].quantile(0.95)),
                }
            )
    return pd.DataFrame(rows).sort_values(["family", "month"]).reset_index(drop=True)


def run_policy_input_generation(args: argparse.Namespace) -> Path:
    family_paths = parse_family_predictions(args.family_predictions)
    quantile_scopes = parse_scope_csv(args.quantile_scopes)
    train_trades = normalize_train_trades(
        read_trade_frames(args.train_trades),
        candidates=set(parse_csv(args.train_candidates)),
        roles=set(parse_csv(args.train_roles)),
        months=set(parse_csv(args.train_months)),
    )
    train_rows = train_rows_from_selected_trades(train_trades)

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
            )
        )
    target_rows = pd.concat(side_frames, ignore_index=True)
    scored_rows, fold_summary = chronological_predictions(
        train_rows,
        target_rows,
        target_mode=args.target_mode,
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
    outputs = attach_predictions_to_families(
        family_frames,
        scored_rows,
        long_output_column=args.long_output_column,
        short_output_column=args.short_output_column,
        score_kind=args.score_kind,
        long_rank_column=args.long_rank_column,
        short_rank_column=args.short_rank_column,
        quantile_scopes=quantile_scopes,
    )

    run_dir = make_run_dir(args.output_dir, args.label)
    prediction_dir = run_dir / "enriched_predictions"
    prediction_dir.mkdir(parents=True, exist_ok=True)
    output_paths: dict[str, Path] = {}
    for family, frame in outputs.items():
        path = prediction_dir / f"{family}_predictions_supervised_shrinkage.parquet"
        frame.to_parquet(path, index=False)
        output_paths[family] = path

    scored_rows.to_parquet(run_dir / "supervised_shrinkage_side_rows.parquet", index=False)
    fold_summary.to_csv(run_dir / "supervised_shrinkage_fold_summary.csv", index=False)
    effect_summary = summarize_prediction_effect(
        outputs,
        base_long_column=args.long_column,
        base_short_column=args.short_column,
        shrink_long_column=args.long_output_column,
        shrink_short_column=args.short_output_column,
    )
    effect_summary.to_csv(
        run_dir / "prediction_supervised_shrinkage_effect_summary.csv",
        index=False,
    )
    config = {
        "family_predictions": family_paths,
        "output_paths": output_paths,
        "train_trades": args.train_trades,
        "train_candidates": parse_csv(args.train_candidates),
        "train_roles": parse_csv(args.train_roles),
        "train_months": parse_csv(args.train_months),
        "target_mode": args.target_mode,
        "score_kind": args.score_kind,
        "long_column": args.long_column,
        "short_column": args.short_column,
        "long_output_column": args.long_output_column,
        "short_output_column": args.short_output_column,
        "long_rank_column": args.long_rank_column,
        "short_rank_column": args.short_rank_column,
        "long_holding_column": args.long_holding_column,
        "short_holding_column": args.short_holding_column,
        "quantile_scopes": quantile_scopes,
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
        "note": "target month prediction rows use selected trades with month earlier than the target month",
    }
    (run_dir / "config.json").write_text(
        json.dumps(config, indent=2, default=local_json_default),
        encoding="utf-8",
    )

    print("Supervised shrinkage fold summary:")
    print(
        fold_summary[
            [
                "target_month",
                "model_used",
                "train_months",
                "train_rows",
                "target_rows",
                "train_target_mean",
                "pred_score_mean",
            ]
        ].to_string(index=False)
    )
    print("\nPrediction effect:")
    print(
        effect_summary[
            [
                "family",
                "month",
                "model_used_share",
                "base_selected_long_share",
                "shrink_selected_long_share",
                "side_switch_share",
                "base_score_q95",
                "shrink_score_q95",
            ]
        ].to_string(index=False)
    )
    print(f"artifacts: {run_dir}")
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--family-predictions", action="append", required=True)
    parser.add_argument("--train-trades", type=Path, action="append", required=True)
    parser.add_argument("--train-candidates", default="")
    parser.add_argument("--train-roles", default="")
    parser.add_argument("--train-months", default="")
    parser.add_argument("--target-mode", choices=["pnl", "factor"], default="factor")
    parser.add_argument("--score-kind", default=DEFAULT_SCORE_KIND)
    parser.add_argument("--long-column", default="pred_calibrated_long_best_adjusted_pnl")
    parser.add_argument("--short-column", default="pred_calibrated_short_best_adjusted_pnl")
    parser.add_argument("--long-output-column", default=DEFAULT_LONG_OUTPUT_COLUMN)
    parser.add_argument("--short-output-column", default=DEFAULT_SHORT_OUTPUT_COLUMN)
    parser.add_argument("--long-rank-column", default="pred_long_entry_local_rank")
    parser.add_argument("--short-rank-column", default="pred_short_entry_local_rank")
    parser.add_argument("--long-holding-column", default="pred_mlp_long_exit_event_minutes")
    parser.add_argument("--short-holding-column", default="pred_mlp_short_exit_event_minutes")
    parser.add_argument("--quantile-scopes", default=DEFAULT_QUANTILE_SCOPES)
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
    parser.add_argument("--output-dir", type=Path, default=Path("data/reports/backtests"))
    parser.add_argument("--label", default="entry_ev_supervised_shrinkage_policy_inputs")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    run_policy_input_generation(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
