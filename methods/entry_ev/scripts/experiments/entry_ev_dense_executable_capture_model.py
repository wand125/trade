#!/usr/bin/env python3
"""Train chronological dense executable-capture models for entry-EV predictions."""

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
from entry_ev_scale_quantile_diagnostics import month_series  # noqa: E402


DEFAULT_LONG_OUTPUT_COLUMN = "pred_dense_executable_long_best_adjusted_pnl"
DEFAULT_SHORT_OUTPUT_COLUMN = "pred_dense_executable_short_best_adjusted_pnl"
DEFAULT_SCORE_KIND = "dense_executable"
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


def parse_csv(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def numeric_or_nan(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(np.nan, index=frame.index, dtype=float)
    values = pd.to_numeric(frame[column], errors="coerce")
    return values.where(np.isfinite(values))


def required_numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        raise ValueError(f"predictions missing required column: {column}")
    return numeric_or_nan(frame, column)


def side_target_column(side: str, target_mode: str) -> str:
    if target_mode.startswith("fixed_") and target_mode.endswith("m"):
        minutes = target_mode.removeprefix("fixed_").removesuffix("m")
        return f"{side}_fixed_{minutes}m_adjusted_pnl"
    if target_mode == "forced":
        return f"{side}_forced_adjusted_pnl"
    if target_mode == "best":
        return f"{side}_best_adjusted_pnl"
    if target_mode == "exit_event":
        return f"{side}_exit_event_adjusted_pnl"
    raise ValueError(f"unknown target mode: {target_mode}")


def decision_hour_features(frame: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    if "decision_timestamp" not in frame.columns:
        hours = pd.Series(0.0, index=frame.index)
    else:
        timestamp = pd.to_datetime(frame["decision_timestamp"], utc=True)
        hours = timestamp.dt.hour + timestamp.dt.minute / 60.0
    radians = 2.0 * np.pi * hours / 24.0
    return pd.Series(np.sin(radians), index=frame.index), pd.Series(
        np.cos(radians),
        index=frame.index,
    )


def side_rows_for_family(
    predictions: pd.DataFrame,
    *,
    family: str,
    target_mode: str,
    long_column: str,
    short_column: str,
    long_rank_column: str,
    short_rank_column: str,
    long_holding_column: str,
    short_holding_column: str,
    min_oracle_edge: float,
    min_capture_factor: float,
    max_capture_factor: float,
) -> pd.DataFrame:
    missing = sorted({long_column, short_column} - set(predictions.columns))
    if missing:
        raise ValueError(f"{family} predictions missing columns: {', '.join(missing)}")

    months = month_series(predictions).astype(str).str.slice(0, 7)
    hour_sin, hour_cos = decision_hour_features(predictions)
    combined_regime = predictions.get(
        "combined_regime",
        pd.Series("__missing__", index=predictions.index),
    ).astype(str)
    session_regime = predictions.get(
        "session_regime",
        pd.Series("__missing__", index=predictions.index),
    ).astype(str)

    long_raw = required_numeric(predictions, long_column)
    short_raw = required_numeric(predictions, short_column)
    raw_side_gap = (long_raw - short_raw).abs()
    selected_side = np.where(long_raw >= short_raw, "long", "short")

    rows: list[pd.DataFrame] = []
    side_specs = {
        "long": {
            "raw": long_raw,
            "opposite_raw": short_raw,
            "rank": numeric_or_nan(predictions, long_rank_column),
            "opposite_rank": numeric_or_nan(predictions, short_rank_column),
            "holding": numeric_or_nan(predictions, long_holding_column),
            "opposite_holding": numeric_or_nan(predictions, short_holding_column),
            "side_sign": 1.0,
            "prob_taken": numeric_or_nan(predictions, "pred_best_side_prob_1"),
            "prob_opposite": numeric_or_nan(predictions, "pred_best_side_prob_-1"),
        },
        "short": {
            "raw": short_raw,
            "opposite_raw": long_raw,
            "rank": numeric_or_nan(predictions, short_rank_column),
            "opposite_rank": numeric_or_nan(predictions, long_rank_column),
            "holding": numeric_or_nan(predictions, short_holding_column),
            "opposite_holding": numeric_or_nan(predictions, long_holding_column),
            "side_sign": -1.0,
            "prob_taken": numeric_or_nan(predictions, "pred_best_side_prob_-1"),
            "prob_opposite": numeric_or_nan(predictions, "pred_best_side_prob_1"),
        },
    }

    for side, spec in side_specs.items():
        best = required_numeric(predictions, f"{side}_best_adjusted_pnl")
        executable = required_numeric(predictions, side_target_column(side, target_mode))
        edge = best > min_oracle_edge
        raw_ratio = executable / best.replace(0.0, np.nan)
        capture = pd.Series(raw_ratio, index=predictions.index).where(edge)
        capture = capture.clip(lower=min_capture_factor, upper=max_capture_factor)

        side_fixed_60 = numeric_or_nan(predictions, f"pred_{side}_fixed_60m_adjusted_pnl")
        side_fixed_240 = numeric_or_nan(predictions, f"pred_{side}_fixed_240m_adjusted_pnl")
        side_fixed_720 = numeric_or_nan(predictions, f"pred_{side}_fixed_720m_adjusted_pnl")
        opposite = "short" if side == "long" else "long"
        opposite_fixed_60 = numeric_or_nan(
            predictions,
            f"pred_{opposite}_fixed_60m_adjusted_pnl",
        )
        opposite_fixed_240 = numeric_or_nan(
            predictions,
            f"pred_{opposite}_fixed_240m_adjusted_pnl",
        )
        opposite_fixed_720 = numeric_or_nan(
            predictions,
            f"pred_{opposite}_fixed_720m_adjusted_pnl",
        )

        rows.append(
            pd.DataFrame(
                {
                    "family": family,
                    "_row_id": np.arange(len(predictions), dtype=int),
                    "month": months.to_numpy(),
                    "side": side,
                    "side_sign": spec["side_sign"],
                    "combined_regime": combined_regime.to_numpy(),
                    "session_regime": session_regime.to_numpy(),
                    "decision_hour_sin": hour_sin.to_numpy(),
                    "decision_hour_cos": hour_cos.to_numpy(),
                    "raw_pred_ev": spec["raw"].to_numpy(),
                    "opposite_pred_ev": spec["opposite_raw"].to_numpy(),
                    "raw_side_gap": raw_side_gap.to_numpy(),
                    "raw_selected_side_match": (selected_side == side).astype(float),
                    "side_entry_rank": spec["rank"].to_numpy(),
                    "opposite_entry_rank": spec["opposite_rank"].to_numpy(),
                    "pred_side_holding_minutes": spec["holding"].to_numpy(),
                    "pred_opposite_holding_minutes": spec["opposite_holding"].to_numpy(),
                    "pred_side_fixed_60m": side_fixed_60.to_numpy(),
                    "pred_side_fixed_240m": side_fixed_240.to_numpy(),
                    "pred_side_fixed_720m": side_fixed_720.to_numpy(),
                    "pred_opposite_fixed_60m": opposite_fixed_60.to_numpy(),
                    "pred_opposite_fixed_240m": opposite_fixed_240.to_numpy(),
                    "pred_opposite_fixed_720m": opposite_fixed_720.to_numpy(),
                    "pred_best_side_prob_taken": spec["prob_taken"].to_numpy(),
                    "pred_best_side_prob_opposite": spec["prob_opposite"].to_numpy(),
                    "target_best_ev": best.to_numpy(),
                    "target_executable_ev": executable.to_numpy(),
                    "target_capture_factor": capture.to_numpy(),
                    "target_eligible": edge.to_numpy() & executable.notna().to_numpy(),
                }
            )
        )

    return pd.concat(rows, ignore_index=True)


def feature_frame(frame: pd.DataFrame) -> pd.DataFrame:
    output = pd.DataFrame(index=frame.index)
    for column in NUMERIC_FEATURES:
        output[column] = pd.to_numeric(frame.get(column), errors="coerce")
    for column in CATEGORY_FEATURES:
        output[column] = frame.get(
            column,
            pd.Series("__missing__", index=frame.index),
        ).astype("string").fillna("__missing__")
    return output


def fit_category_maps(train: pd.DataFrame) -> dict[str, dict[str, int]]:
    maps: dict[str, dict[str, int]] = {}
    for column in CATEGORY_FEATURES:
        values = sorted(str(value) for value in train[column].unique())
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
    default_capture_factor: float,
    min_capture_factor: float,
    max_capture_factor: float,
) -> tuple[np.ndarray, dict[str, Any]]:
    train_fit = sample_training_rows(
        train,
        max_train_rows=max_train_rows,
        random_seed=random_seed,
    )
    y_train = pd.to_numeric(train_fit["target_capture_factor"], errors="coerce")
    y_train = y_train.clip(lower=min_capture_factor, upper=max_capture_factor)
    fallback = (
        float(y_train.mean())
        if y_train.notna().any()
        else float(default_capture_factor)
    )
    fallback = float(np.clip(fallback, min_capture_factor, max_capture_factor))

    if y_train.nunique(dropna=True) < 2:
        prediction = np.full(len(target), fallback, dtype="float64")
        return prediction, {
            "model_used": False,
            "train_rows_used": int(len(train_fit)),
            "train_target_mean": fallback,
            "train_target_std": float(y_train.std(ddof=0)) if len(y_train) else 0.0,
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
    model.fit(x_train.astype("float32").to_numpy(), y_train.to_numpy(dtype="float64"))
    train_pred = model.predict(x_train.astype("float32").to_numpy())
    target_pred = model.predict(x_target.astype("float32").to_numpy())
    train_pred = np.clip(train_pred, min_capture_factor, max_capture_factor)
    target_pred = np.clip(target_pred, min_capture_factor, max_capture_factor)
    return target_pred, {
        "model_used": True,
        "train_rows_used": int(len(train_fit)),
        "train_target_mean": float(y_train.mean()),
        "train_target_std": float(y_train.std(ddof=0)),
        "train_mae": float(mean_absolute_error(y_train, train_pred)),
        "train_rmse": float(mean_squared_error(y_train, train_pred) ** 0.5),
        "train_r2": float(r2_score(y_train, train_pred)),
    }


def chronological_capture_predictions(
    side_rows: pd.DataFrame,
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
    default_capture_factor: float,
    min_capture_factor: float,
    max_capture_factor: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    output = side_rows.copy()
    output["pred_dense_capture_factor"] = float(default_capture_factor)
    output["pred_dense_capture_model_used"] = False
    output["pred_dense_capture_train_rows"] = 0
    output["pred_dense_capture_train_months"] = 0
    fold_rows: list[dict[str, Any]] = []

    periods = pd.PeriodIndex(output["month"].astype(str), freq="M")
    months = sorted(output["month"].dropna().astype(str).unique())
    for month in months:
        target_mask = output["month"].eq(month)
        train_mask = (
            (periods < pd.Period(month, freq="M"))
            & output["target_eligible"].astype(bool)
            & output["target_capture_factor"].notna()
        )
        train = output.loc[train_mask].copy()
        target = output.loc[target_mask].copy()
        train_months = int(train["month"].nunique())

        model_used = False
        if train_months >= min_train_months and len(train) >= min_train_rows:
            pred, fit_info = fit_predict_fold(
                train,
                target,
                max_iter=max_iter,
                learning_rate=learning_rate,
                max_leaf_nodes=max_leaf_nodes,
                min_samples_leaf=min_samples_leaf,
                l2_regularization=l2_regularization,
                random_seed=random_seed,
                max_train_rows=max_train_rows,
                default_capture_factor=default_capture_factor,
                min_capture_factor=min_capture_factor,
                max_capture_factor=max_capture_factor,
            )
            model_used = bool(fit_info["model_used"])
        else:
            pred = np.full(len(target), default_capture_factor, dtype="float64")
            fit_info = {
                "model_used": False,
                "train_rows_used": int(len(train)),
                "train_target_mean": float(default_capture_factor),
                "train_target_std": 0.0,
                "train_mae": 0.0,
                "train_rmse": 0.0,
                "train_r2": 0.0,
            }

        pred = np.clip(pred, min_capture_factor, max_capture_factor)
        output.loc[target.index, "pred_dense_capture_factor"] = pred
        output.loc[target.index, "pred_dense_capture_model_used"] = model_used
        output.loc[target.index, "pred_dense_capture_train_rows"] = int(len(train))
        output.loc[target.index, "pred_dense_capture_train_months"] = train_months

        target_eval = target.copy()
        target_eval["pred_dense_capture_factor"] = pred
        eligible_eval = target_eval[
            target_eval["target_eligible"].astype(bool)
            & target_eval["target_capture_factor"].notna()
        ].copy()
        if eligible_eval.empty:
            pred_mae = np.nan
            pred_rmse = np.nan
            raw_ev_mae = np.nan
            dense_ev_mae = np.nan
            raw_ev_bias = np.nan
            dense_ev_bias = np.nan
        else:
            actual_factor = eligible_eval["target_capture_factor"].astype(float)
            pred_factor = eligible_eval["pred_dense_capture_factor"].astype(float)
            actual_ev = eligible_eval["target_executable_ev"].astype(float)
            raw_ev = eligible_eval["raw_pred_ev"].astype(float)
            dense_ev = raw_ev * pred_factor
            pred_mae = float(mean_absolute_error(actual_factor, pred_factor))
            pred_rmse = float(mean_squared_error(actual_factor, pred_factor) ** 0.5)
            raw_ev_mae = float(mean_absolute_error(actual_ev, raw_ev))
            dense_ev_mae = float(mean_absolute_error(actual_ev, dense_ev))
            raw_ev_bias = float((raw_ev - actual_ev).mean())
            dense_ev_bias = float((dense_ev - actual_ev).mean())

        fold_rows.append(
            {
                "target_month": month,
                "target_rows": int(len(target)),
                "target_eligible_rows": int(len(eligible_eval)),
                "train_months": train_months,
                "train_rows": int(len(train)),
                **fit_info,
                "target_capture_factor_mean": float(
                    eligible_eval["target_capture_factor"].astype(float).mean()
                )
                if len(eligible_eval)
                else np.nan,
                "pred_capture_factor_mean": float(np.mean(pred)) if len(pred) else np.nan,
                "pred_capture_factor_mae": pred_mae,
                "pred_capture_factor_rmse": pred_rmse,
                "raw_ev_mae": raw_ev_mae,
                "dense_ev_mae": dense_ev_mae,
                "raw_ev_bias": raw_ev_bias,
                "dense_ev_bias": dense_ev_bias,
            }
        )

    return output, pd.DataFrame(fold_rows)


def attach_predictions_to_families(
    family_frames: dict[str, pd.DataFrame],
    scored_rows: pd.DataFrame,
    *,
    long_column: str,
    short_column: str,
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
            prefix = f"pred_dense_executable_{side}"
            enriched[f"{prefix}_capture_factor"] = side_rows[
                "pred_dense_capture_factor"
            ].to_numpy()
            enriched[f"{prefix}_capture_model_used"] = side_rows[
                "pred_dense_capture_model_used"
            ].to_numpy()
            enriched[f"{prefix}_capture_train_rows"] = side_rows[
                "pred_dense_capture_train_rows"
            ].to_numpy()
            enriched[f"{prefix}_capture_train_months"] = side_rows[
                "pred_dense_capture_train_months"
            ].to_numpy()
            output_column = long_output_column if side == "long" else short_output_column
            source_column = long_column if side == "long" else short_column
            enriched[output_column] = (
                pd.to_numeric(enriched[source_column], errors="coerce")
                * enriched[f"{prefix}_capture_factor"]
            )
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
    long_column: str,
    short_column: str,
    long_output_column: str,
    short_output_column: str,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for family, frame in outputs.items():
        months = month_series(frame).astype(str).str.slice(0, 7)
        base_long = pd.to_numeric(frame[long_column], errors="coerce")
        base_short = pd.to_numeric(frame[short_column], errors="coerce")
        dense_long = pd.to_numeric(frame[long_output_column], errors="coerce")
        dense_short = pd.to_numeric(frame[short_output_column], errors="coerce")
        base_side = np.where(base_long >= base_short, 1, -1)
        dense_side = np.where(dense_long >= dense_short, 1, -1)
        base_score = np.where(base_side == 1, base_long, base_short)
        dense_score = np.where(dense_side == 1, dense_long, dense_short)
        summary = pd.DataFrame(
            {
                "month": months,
                "base_side": base_side,
                "dense_side": dense_side,
                "base_score": base_score,
                "dense_score": dense_score,
                "base_gap": (base_long - base_short).abs(),
                "dense_gap": (dense_long - dense_short).abs(),
                "long_factor": pd.to_numeric(
                    frame["pred_dense_executable_long_capture_factor"],
                    errors="coerce",
                ),
                "short_factor": pd.to_numeric(
                    frame["pred_dense_executable_short_capture_factor"],
                    errors="coerce",
                ),
                "model_used": frame[
                    "pred_dense_executable_long_capture_model_used"
                ].astype(bool)
                | frame["pred_dense_executable_short_capture_model_used"].astype(bool),
            }
        )
        for month, group in summary.groupby("month", dropna=False):
            rows.append(
                {
                    "family": family,
                    "month": month,
                    "row_count": int(len(group)),
                    "model_used_share": float(group["model_used"].mean()),
                    "base_selected_long_share": float(group["base_side"].eq(1).mean()),
                    "dense_selected_long_share": float(group["dense_side"].eq(1).mean()),
                    "side_switch_share": float(
                        (group["base_side"] != group["dense_side"]).mean()
                    ),
                    "base_score_q95": float(group["base_score"].quantile(0.95)),
                    "dense_score_q95": float(group["dense_score"].quantile(0.95)),
                    "base_gap_q95": float(group["base_gap"].quantile(0.95)),
                    "dense_gap_q95": float(group["dense_gap"].quantile(0.95)),
                    "long_capture_factor_mean": float(group["long_factor"].mean()),
                    "short_capture_factor_mean": float(group["short_factor"].mean()),
                }
            )
    return pd.DataFrame(rows).sort_values(["family", "month"]).reset_index(drop=True)


def summarize_side_metrics(scored_rows: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    frame = scored_rows[
        scored_rows["target_eligible"].astype(bool)
        & scored_rows["target_capture_factor"].notna()
    ].copy()
    if frame.empty:
        return pd.DataFrame()
    frame["dense_pred_ev"] = (
        pd.to_numeric(frame["raw_pred_ev"], errors="coerce")
        * pd.to_numeric(frame["pred_dense_capture_factor"], errors="coerce")
    )
    for (family, month, side), group in frame.groupby(
        ["family", "month", "side"],
        dropna=False,
    ):
        actual_ev = group["target_executable_ev"].astype(float)
        raw_ev = group["raw_pred_ev"].astype(float)
        dense_ev = group["dense_pred_ev"].astype(float)
        rows.append(
            {
                "family": family,
                "month": month,
                "side": side,
                "eligible_rows": int(len(group)),
                "target_best_ev_mean": float(group["target_best_ev"].mean()),
                "target_executable_ev_mean": float(actual_ev.mean()),
                "target_capture_factor_mean": float(
                    group["target_capture_factor"].astype(float).mean()
                ),
                "pred_capture_factor_mean": float(
                    group["pred_dense_capture_factor"].astype(float).mean()
                ),
                "capture_factor_mae": float(
                    mean_absolute_error(
                        group["target_capture_factor"].astype(float),
                        group["pred_dense_capture_factor"].astype(float),
                    )
                ),
                "raw_ev_mean": float(raw_ev.mean()),
                "dense_ev_mean": float(dense_ev.mean()),
                "raw_ev_bias": float((raw_ev - actual_ev).mean()),
                "dense_ev_bias": float((dense_ev - actual_ev).mean()),
                "raw_ev_mae": float(mean_absolute_error(actual_ev, raw_ev)),
                "dense_ev_mae": float(mean_absolute_error(actual_ev, dense_ev)),
            }
        )
    return pd.DataFrame(rows).sort_values(["family", "month", "side"]).reset_index(
        drop=True
    )


def run_dense_capture_model(args: argparse.Namespace) -> Path:
    family_paths = parse_family_predictions(args.family_predictions)
    quantile_scopes = parse_csv(args.quantile_scopes)
    run_dir = make_run_dir(args.output_dir, args.label)
    prediction_dir = run_dir / "enriched_predictions"
    prediction_dir.mkdir(parents=True, exist_ok=True)

    family_frames: dict[str, pd.DataFrame] = {}
    side_frames: list[pd.DataFrame] = []
    for family, path in family_paths.items():
        frame = pd.read_parquet(path)
        family_frames[family] = frame
        side_frames.append(
            side_rows_for_family(
                frame,
                family=family,
                target_mode=args.target_mode,
                long_column=args.long_column,
                short_column=args.short_column,
                long_rank_column=args.long_rank_column,
                short_rank_column=args.short_rank_column,
                long_holding_column=args.long_holding_column,
                short_holding_column=args.short_holding_column,
                min_oracle_edge=args.min_oracle_edge,
                min_capture_factor=args.min_capture_factor,
                max_capture_factor=args.max_capture_factor,
            )
        )
    side_rows = pd.concat(side_frames, ignore_index=True)
    scored_rows, fold_summary = chronological_capture_predictions(
        side_rows,
        min_train_months=args.min_train_months,
        min_train_rows=args.min_train_rows,
        max_train_rows=args.max_train_rows,
        max_iter=args.max_iter,
        learning_rate=args.learning_rate,
        max_leaf_nodes=args.max_leaf_nodes,
        min_samples_leaf=args.min_samples_leaf,
        l2_regularization=args.l2_regularization,
        random_seed=args.random_seed,
        default_capture_factor=args.default_capture_factor,
        min_capture_factor=args.min_capture_factor,
        max_capture_factor=args.max_capture_factor,
    )
    outputs = attach_predictions_to_families(
        family_frames,
        scored_rows,
        long_column=args.long_column,
        short_column=args.short_column,
        long_output_column=args.long_output_column,
        short_output_column=args.short_output_column,
        score_kind=args.score_kind,
        long_rank_column=args.long_rank_column,
        short_rank_column=args.short_rank_column,
        quantile_scopes=quantile_scopes,
    )

    output_paths: dict[str, Path] = {}
    for family, frame in outputs.items():
        path = prediction_dir / f"{family}_predictions_dense_executable.parquet"
        frame.to_parquet(path, index=False)
        output_paths[family] = path

    scored_rows.to_parquet(run_dir / "dense_capture_side_rows.parquet", index=False)
    fold_summary.to_csv(run_dir / "dense_capture_fold_summary.csv", index=False)
    side_metrics = summarize_side_metrics(scored_rows)
    side_metrics.to_csv(run_dir / "dense_capture_side_metric_summary.csv", index=False)
    effect_summary = summarize_prediction_effect(
        outputs,
        long_column=args.long_column,
        short_column=args.short_column,
        long_output_column=args.long_output_column,
        short_output_column=args.short_output_column,
    )
    effect_summary.to_csv(run_dir / "prediction_dense_capture_effect_summary.csv", index=False)

    config = {
        "family_predictions": family_paths,
        "output_paths": output_paths,
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
        "min_oracle_edge": args.min_oracle_edge,
        "min_train_months": args.min_train_months,
        "min_train_rows": args.min_train_rows,
        "max_train_rows": args.max_train_rows,
        "max_iter": args.max_iter,
        "learning_rate": args.learning_rate,
        "max_leaf_nodes": args.max_leaf_nodes,
        "min_samples_leaf": args.min_samples_leaf,
        "l2_regularization": args.l2_regularization,
        "default_capture_factor": args.default_capture_factor,
        "min_capture_factor": args.min_capture_factor,
        "max_capture_factor": args.max_capture_factor,
        "random_seed": args.random_seed,
    }
    (run_dir / "config.json").write_text(
        json.dumps(config, indent=2, default=local_json_default),
        encoding="utf-8",
    )

    print("Dense capture fold summary:")
    print(
        fold_summary[
            [
                "target_month",
                "model_used",
                "train_months",
                "train_rows",
                "target_eligible_rows",
                "target_capture_factor_mean",
                "pred_capture_factor_mean",
                "raw_ev_mae",
                "dense_ev_mae",
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
                "dense_selected_long_share",
                "side_switch_share",
                "base_score_q95",
                "dense_score_q95",
                "long_capture_factor_mean",
                "short_capture_factor_mean",
            ]
        ].to_string(index=False)
    )
    print(f"artifacts: {run_dir}")
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--family-predictions", action="append", required=True)
    parser.add_argument("--target-mode", default="fixed_720m")
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
    parser.add_argument("--min-oracle-edge", type=float, default=0.0)
    parser.add_argument("--min-train-months", type=int, default=2)
    parser.add_argument("--min-train-rows", type=int, default=1000)
    parser.add_argument("--max-train-rows", type=int, default=200000)
    parser.add_argument("--max-iter", type=int, default=80)
    parser.add_argument("--learning-rate", type=float, default=0.04)
    parser.add_argument("--max-leaf-nodes", type=int, default=15)
    parser.add_argument("--min-samples-leaf", type=int, default=200)
    parser.add_argument("--l2-regularization", type=float, default=0.05)
    parser.add_argument("--default-capture-factor", type=float, default=1.0)
    parser.add_argument("--min-capture-factor", type=float, default=0.0)
    parser.add_argument("--max-capture-factor", type=float, default=1.0)
    parser.add_argument("--random-seed", type=int, default=42)
    parser.add_argument("--output-dir", type=Path, default=Path("data/reports/backtests"))
    parser.add_argument("--label", default="entry_ev_dense_executable_capture_model")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    run_dense_capture_model(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
