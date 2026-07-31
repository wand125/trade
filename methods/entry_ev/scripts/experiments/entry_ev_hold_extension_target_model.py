#!/usr/bin/env python3
"""Chronological hold-extension target diagnostics for entry-EV trades."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from trade_data.backtest import json_default, make_run_dir  # noqa: E402


DEFAULT_HORIZONS = "60,240,720"
DEFAULT_THRESHOLDS = "0,1,2,5,10"
DEFAULT_TRAIN_UNIVERSE = "isolated"
DEFAULT_APPLY_UNIVERSES = (
    "isolated,isolated_loss,isolated_large_loss,"
    "isolated_large_loss_capture_failure"
)
DEFAULT_NUMERIC_FEATURES = (
    "adjusted_pnl",
    "holding_minutes",
    "pred_taken_ev",
    "pred_opposite_ev",
    "pred_best_ev",
    "pred_taken_best_holding_minutes",
    "pred_taken_max_adverse_pnl",
    "pred_taken_wait_regret",
    "pred_taken_entry_local_rank",
    "pred_taken_side_confidence",
    "pred_opposite_side_confidence",
    "pred_side_confidence_gap",
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
    "trade_index_in_month",
    "prev_adjusted_pnl",
    "decision_minutes_since_prev_exit",
)
DEFAULT_CATEGORICAL_FEATURES = (
    "source",
    "family",
    "role",
    "direction",
    "combined_regime",
    "session_regime",
    "prev_result_bucket",
    "post_exit_gap_bucket",
)
REQUIRED_COLUMNS = {
    "month",
    "entry_decision_timestamp",
    "adjusted_pnl",
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


def read_trade_frame(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    missing = sorted(REQUIRED_COLUMNS - set(frame.columns))
    if missing:
        raise ValueError(f"{path} missing columns: {', '.join(missing)}")
    return frame


def normalize_trades(frame: pd.DataFrame, *, horizons: list[int]) -> pd.DataFrame:
    output = frame.copy()
    output["month"] = output["month"].astype(str).str.slice(0, 7)
    output["entry_decision_timestamp"] = pd.to_datetime(
        output["entry_decision_timestamp"],
        utc=True,
        errors="coerce",
    )
    output["adjusted_pnl"] = numeric_series(output, "adjusted_pnl", default=0.0)
    for column in [
        *DEFAULT_NUMERIC_FEATURES,
        *[f"actual_taken_fixed_{horizon}m_adjusted_pnl" for horizon in horizons],
        *[f"fixed_{horizon}m_delta_vs_realized" for horizon in horizons],
    ]:
        if column in output.columns:
            output[column] = numeric_series(output, column, default=np.nan)
    for column in [
        "source",
        "family",
        "role",
        "direction",
        "combined_regime",
        "session_regime",
        "prev_result_bucket",
        "post_exit_gap_bucket",
    ]:
        output[column] = text_series(output, column)
    for column in [
        "is_loss",
        "is_large_loss",
        "isolated_context",
        "isolated_large_loss",
        "exit_capture_failure",
        "isolated_exit_capture_failure",
        "isolated_large_loss_capture_failure",
    ]:
        output[column] = bool_series(output, column)
    return output.sort_values(["month", "entry_decision_timestamp"]).reset_index(drop=True)


def universe_mask(frame: pd.DataFrame, universe: str) -> pd.Series:
    if universe == "all":
        return pd.Series(True, index=frame.index, dtype=bool)
    if universe == "loss":
        return frame["adjusted_pnl"].astype(float).lt(0.0)
    if universe == "isolated":
        return frame["isolated_context"].astype(bool)
    if universe == "isolated_loss":
        return frame["isolated_context"].astype(bool) & frame["adjusted_pnl"].astype(float).lt(0.0)
    if universe == "isolated_large_loss":
        return frame["isolated_large_loss"].astype(bool)
    if universe == "isolated_exit_capture_failure":
        return frame["isolated_exit_capture_failure"].astype(bool)
    if universe == "isolated_large_loss_capture_failure":
        return frame["isolated_large_loss_capture_failure"].astype(bool)
    raise ValueError(f"unknown universe: {universe}")


def add_hold_extension_targets(
    frame: pd.DataFrame,
    *,
    horizons: list[int],
    min_improvement: float,
) -> pd.DataFrame:
    output = frame.copy()
    delta_columns: list[str] = []
    for horizon in horizons:
        fixed_column = f"actual_taken_fixed_{horizon}m_adjusted_pnl"
        if fixed_column not in output.columns:
            raise ValueError(f"missing fixed horizon column: {fixed_column}")
        delta_column = f"target_delta_{horizon}m"
        output[delta_column] = (
            numeric_series(output, fixed_column, default=np.nan)
            - output["adjusted_pnl"].astype(float)
        )
        delta_columns.append(delta_column)
    deltas = output[delta_columns].copy()
    deltas_with_zero = pd.concat(
        [pd.Series(0.0, index=output.index, name="target_delta_0m"), deltas],
        axis=1,
    )
    best_column = deltas_with_zero.idxmax(axis=1)
    output["target_best_delta"] = deltas_with_zero.max(axis=1).fillna(0.0)
    output["target_best_horizon_minutes"] = (
        best_column.str.removeprefix("target_delta_").str.removesuffix("m").astype(int)
    )
    output["target_extend_positive"] = output["target_best_delta"].ge(min_improvement)
    return output


def available_features(
    frame: pd.DataFrame,
    requested: list[str],
    defaults: tuple[str, ...],
) -> list[str]:
    columns = requested or list(defaults)
    return [column for column in columns if column in frame.columns]


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


def fit_predict_horizon(
    train: pd.DataFrame,
    target: pd.DataFrame,
    *,
    horizon: int,
    numeric_features: list[str],
    categorical_features: list[str],
    max_iter: int,
    learning_rate: float,
    l2_regularization: float,
    max_leaf_nodes: int,
    random_state: int,
) -> tuple[np.ndarray, dict[str, Any]]:
    y = numeric_series(train, f"target_delta_{horizon}m", default=np.nan)
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
    train_features = make_feature_frame(
        train_fit,
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
    model = HistGradientBoostingRegressor(
        max_iter=max_iter,
        learning_rate=learning_rate,
        l2_regularization=l2_regularization,
        max_leaf_nodes=max_leaf_nodes,
        random_state=random_state,
    )
    model.fit(x_train.astype("float32").to_numpy(), y_fit.astype(float).to_numpy())
    prediction = model.predict(x_target.astype("float32").to_numpy())
    return prediction.astype(float), {
        "model_used": True,
        "train_rows_used": int(len(train_fit)),
        "train_target_mean": float(y_fit.mean()),
        "train_target_std": float(y_fit.std(ddof=0)),
    }


def chronological_predictions(
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
    months = sorted(scored["month"].astype(str).unique().tolist())
    periods = pd.PeriodIndex(scored["month"].astype(str), freq="M")
    train_mask_all = universe_mask(scored, train_universe)
    fold_rows: list[dict[str, Any]] = []
    for horizon in horizons:
        scored[f"pred_hold_extension_delta_{horizon}m"] = 0.0
        scored[f"pred_hold_extension_model_used_{horizon}m"] = False
    for month in months:
        target_period = pd.Period(month, freq="M")
        target_mask = scored["month"].eq(month)
        train = scored[(periods < target_period) & train_mask_all].copy()
        target = scored[target_mask].copy()
        train_months = int(train["month"].nunique()) if len(train) else 0
        use_model = train_months >= min_train_months and len(train) >= min_train_rows
        for horizon in horizons:
            if use_model:
                pred, fit_info = fit_predict_horizon(
                    train,
                    target,
                    horizon=horizon,
                    numeric_features=numeric_features,
                    categorical_features=categorical_features,
                    max_iter=max_iter,
                    learning_rate=learning_rate,
                    l2_regularization=l2_regularization,
                    max_leaf_nodes=max_leaf_nodes,
                    random_state=random_state,
                )
            else:
                target_mean = float(
                    numeric_series(train, f"target_delta_{horizon}m", default=np.nan)
                    .dropna()
                    .mean()
                ) if len(train) else 0.0
                if not np.isfinite(target_mean):
                    target_mean = 0.0
                pred = np.full(len(target), target_mean, dtype=float)
                fit_info = {
                    "model_used": False,
                    "train_rows_used": int(len(train)),
                    "train_target_mean": target_mean,
                    "train_target_std": 0.0,
                }
            scored.loc[target.index, f"pred_hold_extension_delta_{horizon}m"] = pred
            scored.loc[target.index, f"pred_hold_extension_model_used_{horizon}m"] = bool(
                fit_info["model_used"]
            )
            actual = numeric_series(target, f"target_delta_{horizon}m", default=np.nan)
            valid_eval = actual.notna()
            if valid_eval.any():
                mae = mean_absolute_error(actual[valid_eval], pred[valid_eval])
                rmse = mean_squared_error(actual[valid_eval], pred[valid_eval]) ** 0.5
            else:
                mae = float("nan")
                rmse = float("nan")
            fold_rows.append(
                {
                    "target_month": month,
                    "horizon_minutes": int(horizon),
                    "target_rows": int(len(target)),
                    "train_rows": int(len(train)),
                    "train_months": train_months,
                    "model_used": bool(fit_info["model_used"]),
                    "train_rows_used": int(fit_info["train_rows_used"]),
                    "train_target_mean": float(fit_info["train_target_mean"]),
                    "train_target_std": float(fit_info["train_target_std"]),
                    "actual_delta_mean": float(actual.dropna().mean())
                    if actual.notna().any()
                    else float("nan"),
                    "pred_delta_mean": float(np.mean(pred)) if len(pred) else 0.0,
                    "mae": float(mae),
                    "rmse": float(rmse),
                }
            )
    prediction_columns = [f"pred_hold_extension_delta_{horizon}m" for horizon in horizons]
    pred_matrix = scored[prediction_columns].to_numpy(dtype=float)
    best_idx = np.argmax(pred_matrix, axis=1)
    best_delta = pred_matrix[np.arange(len(scored)), best_idx]
    best_horizon = np.array(horizons, dtype=int)[best_idx]
    best_horizon = np.where(best_delta > 0.0, best_horizon, 0)
    best_delta = np.where(best_delta > 0.0, best_delta, 0.0)
    scored["pred_hold_extension_best_delta"] = best_delta
    scored["pred_hold_extension_best_horizon_minutes"] = best_horizon
    scored["pred_hold_extension_any_model_used"] = scored[
        [f"pred_hold_extension_model_used_{horizon}m" for horizon in horizons]
    ].any(axis=1)
    return scored, pd.DataFrame(fold_rows)


def prediction_metric_summary(scored: pd.DataFrame, *, horizons: list[int]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for horizon in horizons:
        actual = numeric_series(scored, f"target_delta_{horizon}m", default=np.nan)
        pred = numeric_series(scored, f"pred_hold_extension_delta_{horizon}m", default=np.nan)
        valid = actual.notna() & pred.notna()
        rows.append(
            {
                "horizon_minutes": int(horizon),
                "row_count": int(valid.sum()),
                "actual_delta_mean": float(actual[valid].mean()) if valid.any() else 0.0,
                "pred_delta_mean": float(pred[valid].mean()) if valid.any() else 0.0,
                "mae": float(mean_absolute_error(actual[valid], pred[valid]))
                if valid.any()
                else 0.0,
                "rmse": float(mean_squared_error(actual[valid], pred[valid]) ** 0.5)
                if valid.any()
                else 0.0,
                "model_used_share": float(
                    scored[f"pred_hold_extension_model_used_{horizon}m"].astype(bool).mean()
                ),
            }
        )
    return pd.DataFrame(rows)


def selected_predicted_delta(scored: pd.DataFrame, *, horizons: list[int]) -> pd.Series:
    values = pd.Series(0.0, index=scored.index, dtype=float)
    for horizon in horizons:
        mask = scored["pred_hold_extension_best_horizon_minutes"].astype(int).eq(horizon)
        values.loc[mask] = numeric_series(
            scored.loc[mask],
            f"target_delta_{horizon}m",
            default=np.nan,
        )
    return values.fillna(0.0)


def threshold_summary(
    scored: pd.DataFrame,
    *,
    horizons: list[int],
    thresholds: list[float],
    apply_universes: list[str],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    total_pnl = float(scored["adjusted_pnl"].sum())
    actual_selected_delta = selected_predicted_delta(scored, horizons=horizons)
    month_keys = ["source", "role", "family", "variant", "candidate", "month"]
    rows: list[dict[str, Any]] = []
    monthly_rows: list[dict[str, Any]] = []
    for universe in apply_universes:
        universe_mask_values = universe_mask(scored, universe)
        for threshold in thresholds:
            flag = (
                universe_mask_values
                & scored["pred_hold_extension_best_delta"].astype(float).ge(threshold)
                & scored["pred_hold_extension_best_horizon_minutes"].astype(int).gt(0)
            )
            adjusted_after = scored["adjusted_pnl"].astype(float) + actual_selected_delta.where(
                flag,
                0.0,
            )
            grouped_after = adjusted_after.groupby(
                [scored[column] for column in month_keys],
                dropna=False,
            ).sum()
            rows.append(
                {
                    "apply_universe": universe,
                    "threshold": float(threshold),
                    "trade_count": int(len(scored)),
                    "total_pnl": total_pnl,
                    "flagged_trade_count": int(flag.sum()),
                    "flagged_pnl": float(scored.loc[flag, "adjusted_pnl"].sum()),
                    "flagged_actual_delta_sum": float(actual_selected_delta[flag].sum()),
                    "total_pnl_if_replaced_no_replay": float(
                        total_pnl + actual_selected_delta[flag].sum()
                    ),
                    "month_min_if_replaced_no_replay": float(grouped_after.min())
                    if len(grouped_after)
                    else 0.0,
                    "flagged_loss_count": int(scored.loc[flag, "is_loss"].sum())
                    if "is_loss" in scored.columns
                    else int(scored.loc[flag, "adjusted_pnl"].lt(0.0).sum()),
                    "flagged_large_loss_count": int(scored.loc[flag, "is_large_loss"].sum())
                    if "is_large_loss" in scored.columns
                    else 0,
                    "flagged_target_extend_positive_count": int(
                        scored.loc[flag, "target_extend_positive"].sum()
                    ),
                }
            )
            month_frame = scored.copy()
            month_frame["_actual_selected_delta"] = actual_selected_delta.where(flag, 0.0)
            month_frame["_adjusted_after"] = adjusted_after
            for key, group in month_frame.groupby(month_keys, dropna=False):
                if not isinstance(key, tuple):
                    key = (key,)
                group_flag = flag.loc[group.index]
                row = dict(zip(month_keys, key))
                row.update(
                    {
                        "apply_universe": universe,
                        "threshold": float(threshold),
                        "total_pnl": float(group["adjusted_pnl"].sum()),
                        "flagged_trade_count": int(group_flag.sum()),
                        "flagged_pnl": float(group.loc[group_flag, "adjusted_pnl"].sum()),
                        "flagged_actual_delta_sum": float(
                            group.loc[group_flag, "_actual_selected_delta"].sum()
                        ),
                        "pnl_if_replaced_no_replay": float(group["_adjusted_after"].sum()),
                    }
                )
                monthly_rows.append(row)
    summary = pd.DataFrame(rows).sort_values(
        [
            "month_min_if_replaced_no_replay",
            "total_pnl_if_replaced_no_replay",
            "flagged_actual_delta_sum",
        ],
        ascending=[False, False, False],
    )
    monthly = pd.DataFrame(monthly_rows).sort_values(
        ["pnl_if_replaced_no_replay", "flagged_actual_delta_sum"],
        ascending=[True, False],
    )
    return summary, monthly


def target_summary(scored: pd.DataFrame, *, group_columns: list[str]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for key, group in scored.groupby(group_columns, dropna=False, observed=True):
        if not isinstance(key, tuple):
            key = (key,)
        row = dict(zip(group_columns, key))
        row.update(
            {
                "row_count": int(len(group)),
                "total_pnl": float(group["adjusted_pnl"].sum()),
                "target_extend_positive_count": int(group["target_extend_positive"].sum()),
                "target_extend_positive_rate": float(
                    group["target_extend_positive"].astype(bool).mean()
                ),
                "target_best_delta_sum": float(group["target_best_delta"].sum()),
                "target_best_delta_mean": float(group["target_best_delta"].mean()),
                "pred_best_delta_mean": float(
                    group["pred_hold_extension_best_delta"].astype(float).mean()
                ),
                "pred_positive_count": int(
                    group["pred_hold_extension_best_horizon_minutes"].astype(int).gt(0).sum()
                ),
            }
        )
        rows.append(row)
    return pd.DataFrame(rows).sort_values(
        ["total_pnl", "target_best_delta_sum"],
        ascending=[True, False],
    )


def build_diagnostics(args: argparse.Namespace) -> Path:
    horizons = parse_int_csv(args.horizons)
    thresholds = parse_float_csv(args.thresholds)
    apply_universes = parse_csv(args.apply_universes)
    raw = read_trade_frame(args.isolated_trades)
    frame = normalize_trades(raw, horizons=horizons)
    frame = add_hold_extension_targets(
        frame,
        horizons=horizons,
        min_improvement=args.min_improvement,
    )
    numeric_features = available_features(
        frame,
        parse_csv(args.numeric_features),
        DEFAULT_NUMERIC_FEATURES,
    )
    categorical_features = available_features(
        frame,
        parse_csv(args.categorical_features),
        DEFAULT_CATEGORICAL_FEATURES,
    )
    scored, fold_summary = chronological_predictions(
        frame,
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
    threshold, monthly_threshold = threshold_summary(
        scored,
        horizons=horizons,
        thresholds=thresholds,
        apply_universes=apply_universes,
    )

    run_dir = make_run_dir(args.output_dir, args.label)
    scored.to_csv(run_dir / "hold_extension_scored_trades.csv", index=False)
    fold_summary.to_csv(run_dir / "hold_extension_fold_summary.csv", index=False)
    prediction_metric_summary(scored, horizons=horizons).to_csv(
        run_dir / "hold_extension_prediction_metric_summary.csv",
        index=False,
    )
    threshold.to_csv(run_dir / "hold_extension_threshold_summary.csv", index=False)
    monthly_threshold.to_csv(
        run_dir / "hold_extension_monthly_threshold_summary.csv",
        index=False,
    )
    target_summary(
        scored,
        group_columns=["source", "role", "month"],
    ).to_csv(run_dir / "hold_extension_target_month_summary.csv", index=False)
    target_summary(
        scored,
        group_columns=["prev_result_bucket", "post_exit_gap_bucket", "isolated_context"],
    ).to_csv(run_dir / "hold_extension_target_path_summary.csv", index=False)
    config = {
        "isolated_trades": args.isolated_trades,
        "horizons": horizons,
        "thresholds": thresholds,
        "train_universe": args.train_universe,
        "apply_universes": apply_universes,
        "min_improvement": args.min_improvement,
        "min_train_months": args.min_train_months,
        "min_train_rows": args.min_train_rows,
        "numeric_features": numeric_features,
        "categorical_features": categorical_features,
        "max_iter": args.max_iter,
        "learning_rate": args.learning_rate,
        "l2_regularization": args.l2_regularization,
        "max_leaf_nodes": args.max_leaf_nodes,
        "random_state": args.random_state,
        "note": (
            "Chronological folds train only on months earlier than the target month. "
            "Fixed-horizon replacement summaries are no-replay diagnostics, not policy evidence."
        ),
    }
    (run_dir / "config.json").write_text(
        json.dumps(config, indent=2, default=local_json_default),
        encoding="utf-8",
    )
    print("Hold-extension threshold summary:")
    print(
        threshold[
            [
                "apply_universe",
                "threshold",
                "flagged_trade_count",
                "flagged_actual_delta_sum",
                "total_pnl_if_replaced_no_replay",
                "month_min_if_replaced_no_replay",
                "flagged_target_extend_positive_count",
            ]
        ]
        .head(args.print_top)
        .to_string(index=False)
    )
    print(f"artifacts: {run_dir}")
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--isolated-trades", type=Path, required=True)
    parser.add_argument("--horizons", default=DEFAULT_HORIZONS)
    parser.add_argument("--thresholds", default=DEFAULT_THRESHOLDS)
    parser.add_argument("--train-universe", default=DEFAULT_TRAIN_UNIVERSE)
    parser.add_argument("--apply-universes", default=DEFAULT_APPLY_UNIVERSES)
    parser.add_argument("--min-improvement", type=float, default=1.0)
    parser.add_argument("--min-train-months", type=int, default=3)
    parser.add_argument("--min-train-rows", type=int, default=30)
    parser.add_argument("--numeric-features", default="")
    parser.add_argument("--categorical-features", default="")
    parser.add_argument("--max-iter", type=int, default=80)
    parser.add_argument("--learning-rate", type=float, default=0.05)
    parser.add_argument("--l2-regularization", type=float, default=0.25)
    parser.add_argument("--max-leaf-nodes", type=int, default=15)
    parser.add_argument("--random-state", type=int, default=42)
    parser.add_argument("--print-top", type=int, default=12)
    parser.add_argument("--output-dir", type=Path, default=Path("data/reports/backtests"))
    parser.add_argument("--label", default="entry_ev_hold_extension_target_model")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    build_diagnostics(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
