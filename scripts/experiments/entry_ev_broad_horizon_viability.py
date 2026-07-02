#!/usr/bin/env python3
"""Train horizon viability heads on broad candidates and evaluate near-miss rows."""

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

from entry_ev_forced_exit_selector_inputs import parse_family_predictions  # noqa: E402
from entry_ev_near_miss_exit_head import (  # noqa: E402
    DEFAULT_CATEGORICAL_FEATURES,
    DEFAULT_NUMERIC_FEATURES,
    available_features,
    bool_series,
    fit_predict_classifier,
    fit_predict_regressor,
    normalize_rows,
    numeric_series,
    parse_csv,
    parse_float_csv,
    parse_group_specs,
    parse_int_csv,
    safe_spearman,
    text_series,
)
from entry_ev_near_miss_exit_target_diagnostics import (  # noqa: E402
    add_fixed_horizon_targets,
    add_predicted_fixed_choice,
    month_series,
    parquet_columns,
)
from entry_ev_near_miss_horizon_viability import (  # noqa: E402
    DEFAULT_EV_THRESHOLDS,
    DEFAULT_GROUP_SPECS,
    DEFAULT_HORIZONS,
    DEFAULT_PROB_THRESHOLDS,
    DEFAULT_TAIL_PROB_THRESHOLDS,
    add_horizon_targets,
    choose_horizon,
    group_summary,
    metric_summary,
    threshold_summary,
)
from entry_ev_quantile_policy_backtest import policy_candidate_from_name  # noqa: E402
from entry_ev_thin_month_opposite_candidate_diagnostics import (  # noqa: E402
    SIDE_LABELS,
    add_side_specific_quantiles,
    apply_side_penalties,
    parse_side_penalty_rules,
)


DEFAULT_CANDIDATE = "q95_sg95_rank90_floor5_side_regime_session_month"
DEFAULT_SCORE_KIND = "fixed60_uncertainty_margin_famdirregsess_w5"
DEFAULT_LONG_COLUMN = (
    "pred_fixed60_uncertainty_margin_famdirregsess_w5_long_best_adjusted_pnl"
)
DEFAULT_SHORT_COLUMN = (
    "pred_fixed60_uncertainty_margin_famdirregsess_w5_short_best_adjusted_pnl"
)
DEFAULT_LONG_HOLDING_COLUMN = "pred_mlp_long_exit_event_minutes"
DEFAULT_SHORT_HOLDING_COLUMN = "pred_mlp_short_exit_event_minutes"
DEFAULT_TRAIN_GROUP_SPECS = (
    "family;month;side;near_miss_bucket;family,month;side,combined_regime,session_regime"
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


def family_role_map(eval_rows: pd.DataFrame) -> dict[str, str]:
    if "family" not in eval_rows.columns or "role" not in eval_rows.columns:
        return {}
    rows = eval_rows[["family", "role"]].dropna().astype(str)
    mapping: dict[str, str] = {}
    for family, group in rows.groupby("family"):
        mapping[family] = group["role"].mode().iloc[0]
    return mapping


def prediction_read_columns(
    *,
    horizons: list[int],
    long_column: str,
    short_column: str,
    long_holding_column: str,
    short_holding_column: str,
    side_penalty_rules: list[tuple[str, str, str, float]],
) -> list[str]:
    columns = [
        "decision_timestamp",
        "entry_timestamp",
        "dataset_month",
        "month",
        "combined_regime",
        "session_regime",
        long_column,
        short_column,
        long_holding_column,
        short_holding_column,
        "pred_long_entry_local_rank",
        "pred_short_entry_local_rank",
        "long_best_adjusted_pnl",
        "short_best_adjusted_pnl",
        "long_best_holding_minutes",
        "short_best_holding_minutes",
        *[rule[1] for rule in side_penalty_rules],
    ]
    for horizon in horizons:
        for side in SIDE_LABELS:
            columns.extend(
                [
                    f"{side}_fixed_{horizon}m_adjusted_pnl",
                    f"pred_{side}_fixed_{horizon}m_adjusted_pnl",
                ]
            )
    for side in SIDE_LABELS:
        columns.extend(
            [
                f"pred_{side}_exit_event_minutes",
                f"pred_mlp_{side}_exit_event_minutes",
                f"pred_{side}_exit_event_time_bin_expected_minutes",
                f"pred_{side}_exit_event_prob_0",
                f"pred_{side}_exit_event_prob_1",
                f"pred_{side}_exit_event_prob_2",
            ]
        )
    return list(dict.fromkeys(columns))


def build_side_rows_from_predictions(
    predictions: pd.DataFrame,
    *,
    family: str,
    role: str,
    horizons: list[int],
    long_column: str,
    short_column: str,
    long_holding_column: str,
    short_holding_column: str,
    side_penalty_rules: list[tuple[str, str, str, float]],
    min_valid_predicted_hold_minutes: float,
    max_predicted_hold_minutes: float,
) -> pd.DataFrame:
    frame = predictions.copy()
    frame["family"] = family
    frame["role"] = role
    frame["month"] = month_series(frame)
    frame["decision_timestamp"] = pd.to_datetime(
        frame["decision_timestamp"],
        utc=True,
        errors="coerce",
    )
    frame = apply_side_penalties(
        frame,
        long_column=long_column,
        short_column=short_column,
        rules=side_penalty_rules,
    )
    frame["_long_holding"] = numeric_series(frame, long_holding_column)
    frame["_short_holding"] = numeric_series(frame, short_holding_column)
    frames: list[pd.DataFrame] = []
    for side in SIDE_LABELS:
        opposite = "short" if side == "long" else "long"
        side_frame = pd.DataFrame(
            {
                "family": frame["family"],
                "role": frame["role"],
                "month": frame["month"],
                "decision_timestamp": frame["decision_timestamp"],
                "side": side,
                "needed_side": side,
                "side_score": frame[f"_{side}_score"],
                "opposite_score": frame[f"_{opposite}_score"],
                "side_pred_holding_minutes": frame[f"_{side}_holding"],
                "side_entry_rank": numeric_series(frame, f"pred_{side}_entry_local_rank"),
                "side_best_adjusted_pnl": numeric_series(
                    frame,
                    f"{side}_best_adjusted_pnl",
                ),
                "side_best_holding_minutes": numeric_series(
                    frame,
                    f"{side}_best_holding_minutes",
                ),
                "combined_regime": text_series(frame, "combined_regime"),
                "session_regime": text_series(frame, "session_regime"),
                "entry_hour": frame["decision_timestamp"].dt.hour,
            }
        )
        for horizon in horizons:
            side_frame[f"side_fixed_{horizon}m_adjusted_pnl"] = numeric_series(
                frame,
                f"{side}_fixed_{horizon}m_adjusted_pnl",
            )
            side_frame[f"pred_fixed_{horizon}m_adjusted_pnl"] = numeric_series(
                frame,
                f"pred_{side}_fixed_{horizon}m_adjusted_pnl",
            )
        for suffix in [
            "exit_event_minutes",
            "exit_event_time_bin_expected_minutes",
            "exit_event_prob_0",
            "exit_event_prob_1",
            "exit_event_prob_2",
        ]:
            side_frame[f"pred_{suffix}"] = numeric_series(frame, f"pred_{side}_{suffix}")
        side_frame["pred_mlp_exit_event_minutes"] = numeric_series(
            frame,
            f"pred_mlp_{side}_exit_event_minutes",
        )
        side_frame["side_margin"] = side_frame["side_score"] - side_frame["opposite_score"]
        side_frame["holding_ok"] = (
            side_frame["side_pred_holding_minutes"].notna()
            & side_frame["side_pred_holding_minutes"].ge(min_valid_predicted_hold_minutes)
            & side_frame["side_pred_holding_minutes"].le(max_predicted_hold_minutes)
        )
        frames.append(side_frame)
    rows = pd.concat(frames, ignore_index=True)
    rows = add_side_specific_quantiles(rows)
    return rows


def add_candidate_flags(
    rows: pd.DataFrame,
    *,
    candidate_name: str,
    min_strict_side_margin: float,
    relaxed_min_score: float,
    relaxed_score_quantile: float,
    relaxed_side_margin_quantile: float,
    relaxed_rank_quantile: float,
    relaxed_min_side_margin: float,
) -> pd.DataFrame:
    policy = policy_candidate_from_name(candidate_name)
    output = rows.copy()
    output["strict_side_specific"] = (
        output["holding_ok"]
        & output["side_score"].gt(policy.entry_threshold)
        & output["score_pct"].ge(policy.score_quantile)
        & output["side_margin_pct"].ge(policy.side_gap_quantile)
        & output["entry_rank_pct"].ge(policy.rank_quantile)
        & output["side_margin"].ge(min_strict_side_margin)
    )
    output["relaxed_side_specific"] = (
        output["holding_ok"]
        & output["side_score"].gt(relaxed_min_score)
        & output["score_pct"].ge(relaxed_score_quantile)
        & output["side_margin_pct"].ge(relaxed_side_margin_quantile)
        & output["entry_rank_pct"].ge(relaxed_rank_quantile)
        & output["side_margin"].ge(relaxed_min_side_margin)
    )
    strict_stage_ok = pd.DataFrame(
        {
            "holding": output["holding_ok"],
            "score_floor": output["side_score"].gt(policy.entry_threshold),
            "score_q": output["score_pct"].ge(policy.score_quantile),
            "side_margin_q": output["side_margin_pct"].ge(policy.side_gap_quantile),
            "rank_q": output["entry_rank_pct"].ge(policy.rank_quantile),
            "side_margin": output["side_margin"].ge(min_strict_side_margin),
        }
    )
    output["strict_failed_stage_count"] = (~strict_stage_ok).sum(axis=1)
    output["one_failed_strict_stage"] = output["strict_failed_stage_count"].eq(1)
    output["near_miss_bucket"] = np.select(
        [
            output["strict_side_specific"].astype(bool),
            output["relaxed_side_specific"].astype(bool),
            output["one_failed_strict_stage"].astype(bool),
        ],
        ["strict", "relaxed", "one_failed_strict_stage"],
        default="broad_candidate",
    )
    output["row_scope"] = "broad_train"
    output["selection_bucket"] = "broad_train"
    output["selected_any"] = False
    output["stateful_available"] = True
    output["extra_side_needed"] = 0
    return output


def filter_broad_candidates(
    rows: pd.DataFrame,
    *,
    min_score: float,
    min_score_pct: float,
    min_side_margin_pct: float,
    min_entry_rank_pct: float,
    include_one_failed: bool,
) -> pd.DataFrame:
    output = rows[
        rows["holding_ok"].astype(bool)
        & rows["side_score"].ge(min_score)
        & rows["score_pct"].ge(min_score_pct)
        & rows["side_margin_pct"].ge(min_side_margin_pct)
        & rows["entry_rank_pct"].ge(min_entry_rank_pct)
    ].copy()
    if include_one_failed:
        one_failed = rows[rows["one_failed_strict_stage"].astype(bool)].copy()
        output = pd.concat([output, one_failed], ignore_index=True)
    return output.drop_duplicates(["family", "month", "decision_timestamp", "side"])


def build_broad_training_rows(
    *,
    family_predictions: dict[str, Path],
    eval_rows: pd.DataFrame,
    horizons: list[int],
    long_column: str,
    short_column: str,
    long_holding_column: str,
    short_holding_column: str,
    side_penalty_rules: list[tuple[str, str, str, float]],
    min_valid_predicted_hold_minutes: float,
    max_predicted_hold_minutes: float,
    candidate_name: str,
    min_strict_side_margin: float,
    relaxed_min_score: float,
    relaxed_score_quantile: float,
    relaxed_side_margin_quantile: float,
    relaxed_rank_quantile: float,
    relaxed_min_side_margin: float,
    broad_min_score: float,
    broad_min_score_pct: float,
    broad_min_side_margin_pct: float,
    broad_min_entry_rank_pct: float,
    broad_include_one_failed: bool,
    min_executable_pnl: float,
    tail_loss_threshold: float,
    min_predicted_pnl: float,
) -> pd.DataFrame:
    role_by_family = family_role_map(eval_rows)
    parts: list[pd.DataFrame] = []
    needed = prediction_read_columns(
        horizons=horizons,
        long_column=long_column,
        short_column=short_column,
        long_holding_column=long_holding_column,
        short_holding_column=short_holding_column,
        side_penalty_rules=side_penalty_rules,
    )
    for family, path in family_predictions.items():
        columns = parquet_columns(path)
        read_columns = [column for column in needed if column in columns]
        if "decision_timestamp" not in read_columns:
            raise ValueError(f"{path} missing decision_timestamp")
        predictions = pd.read_parquet(path, columns=read_columns)
        role = role_by_family.get(family, f"{family}_broad")
        side_rows = build_side_rows_from_predictions(
            predictions,
            family=family,
            role=role,
            horizons=horizons,
            long_column=long_column,
            short_column=short_column,
            long_holding_column=long_holding_column,
            short_holding_column=short_holding_column,
            side_penalty_rules=side_penalty_rules,
            min_valid_predicted_hold_minutes=min_valid_predicted_hold_minutes,
            max_predicted_hold_minutes=max_predicted_hold_minutes,
        )
        side_rows = add_candidate_flags(
            side_rows,
            candidate_name=candidate_name,
            min_strict_side_margin=min_strict_side_margin,
            relaxed_min_score=relaxed_min_score,
            relaxed_score_quantile=relaxed_score_quantile,
            relaxed_side_margin_quantile=relaxed_side_margin_quantile,
            relaxed_rank_quantile=relaxed_rank_quantile,
            relaxed_min_side_margin=relaxed_min_side_margin,
        )
        side_rows = filter_broad_candidates(
            side_rows,
            min_score=broad_min_score,
            min_score_pct=broad_min_score_pct,
            min_side_margin_pct=broad_min_side_margin_pct,
            min_entry_rank_pct=broad_min_entry_rank_pct,
            include_one_failed=broad_include_one_failed,
        )
        parts.append(side_rows)
    if not parts:
        raise ValueError("no broad training rows built")
    broad = pd.concat(parts, ignore_index=True)
    broad = add_fixed_horizon_targets(
        broad,
        horizons=horizons,
        min_executable_pnl=min_executable_pnl,
    )
    broad = add_predicted_fixed_choice(
        broad,
        horizons=horizons,
        min_predicted_pnl=min_predicted_pnl,
        min_executable_pnl=min_executable_pnl,
    )
    broad = add_horizon_targets(
        broad,
        horizons=horizons,
        min_executable_pnl=min_executable_pnl,
        tail_loss_threshold=tail_loss_threshold,
    )
    return normalize_rows(broad, horizons=horizons)


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
        .sort_values(["month", "decision_timestamp", "family", "side"])
        .reset_index(drop=True)
    )


def chronological_broad_horizon_predictions(
    *,
    train_rows: pd.DataFrame,
    eval_rows: pd.DataFrame,
    horizons: list[int],
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
    scored = eval_rows.copy()
    eval_months = sorted(scored["month"].astype(str).unique().tolist())
    train_periods = pd.PeriodIndex(train_rows["month"].astype(str), freq="M")
    fold_rows: list[dict[str, Any]] = []
    for horizon in horizons:
        scored[f"pred_hv_{horizon}m_executable_prob"] = 0.0
        scored[f"pred_hv_{horizon}m_pnl"] = 0.0
        scored[f"pred_hv_{horizon}m_tail_loss_prob"] = 0.0
        scored[f"pred_hv_{horizon}m_executable_model_used"] = False
        scored[f"pred_hv_{horizon}m_pnl_model_used"] = False
        scored[f"pred_hv_{horizon}m_tail_model_used"] = False

    for month in eval_months:
        target_period = pd.Period(month, freq="M")
        train_full = train_rows[train_periods < target_period].copy()
        train_months = int(train_full["month"].nunique()) if len(train_full) else 0
        train = sample_train_rows(
            train_full,
            max_train_rows=max_train_rows,
            random_state=random_state + int(target_period.ordinal),
        )
        target = scored[scored["month"].eq(month)].copy()
        can_fit = train_months >= min_train_months and len(train) >= min_train_rows
        for horizon in horizons:
            specs = [
                (
                    "executable",
                    f"target_fixed_{horizon}m_executable",
                    f"pred_hv_{horizon}m_executable_prob",
                    "classifier",
                ),
                (
                    "pnl",
                    f"side_fixed_{horizon}m_adjusted_pnl",
                    f"pred_hv_{horizon}m_pnl",
                    "regressor",
                ),
                (
                    "tail_loss",
                    f"target_fixed_{horizon}m_tail_loss",
                    f"pred_hv_{horizon}m_tail_loss_prob",
                    "classifier",
                ),
            ]
            for target_name, target_column, prediction_column, model_kind in specs:
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
                model_column = (
                    f"pred_hv_{horizon}m_"
                    f"{target_name if target_name != 'tail_loss' else 'tail'}_model_used"
                )
                scored.loc[target.index, model_column] = model_used

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
                        "horizon_minutes": int(horizon),
                        "target_name": target_name,
                        "target_column": target_column,
                        "prediction_column": prediction_column,
                        "model_kind": model_kind,
                        "target_rows": int(len(target)),
                        "train_rows_full": int(len(train_full)),
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
    return scored, pd.DataFrame(fold_rows)


def train_summary(train_rows: pd.DataFrame, group_specs: list[list[str]]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for columns in group_specs:
        available = [column for column in columns if column in train_rows.columns]
        if not available:
            continue
        for key, group in train_rows.groupby(available, dropna=False):
            if not isinstance(key, tuple):
                key = (key,)
            row = {
                "group_spec": ",".join(available),
                "group_key": "|".join(str(value) for value in key),
                "row_count": int(len(group)),
                "fixed60_sum": float(numeric_series(group, "side_fixed_60m_adjusted_pnl").sum()),
                "fixed240_sum": float(
                    numeric_series(group, "side_fixed_240m_adjusted_pnl").sum()
                ),
                "fixed720_sum": float(
                    numeric_series(group, "side_fixed_720m_adjusted_pnl").sum()
                ),
                "fixed_best_sum": float(
                    numeric_series(group, "target_fixed_best_adjusted_pnl").sum()
                ),
                "executable_rate_60m": float(
                    bool_series(group, "target_fixed_60m_executable").mean()
                ),
                "tail_loss_rate_720m": float(
                    bool_series(group, "target_fixed_720m_tail_loss").mean()
                ),
            }
            row.update(dict(zip(available, key)))
            rows.append(row)
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(
        ["group_spec", "row_count"],
        ascending=[True, False],
    )


def build_diagnostics(args: argparse.Namespace) -> Path:
    horizons = parse_int_csv(args.horizons)
    raw_eval = pd.read_csv(args.eval_input)
    eval_rows = normalize_rows(raw_eval, horizons=horizons)
    eval_rows = add_horizon_targets(
        eval_rows,
        horizons=horizons,
        min_executable_pnl=args.min_executable_pnl,
        tail_loss_threshold=args.tail_loss_threshold,
    )
    family_predictions = parse_family_predictions(args.family_predictions)
    train_rows = build_broad_training_rows(
        family_predictions=family_predictions,
        eval_rows=eval_rows,
        horizons=horizons,
        long_column=args.long_column,
        short_column=args.short_column,
        long_holding_column=args.long_holding_column,
        short_holding_column=args.short_holding_column,
        side_penalty_rules=parse_side_penalty_rules(args.side_ev_penalty_rules),
        min_valid_predicted_hold_minutes=args.min_valid_predicted_hold_minutes,
        max_predicted_hold_minutes=args.max_predicted_hold_minutes,
        candidate_name=args.candidate,
        min_strict_side_margin=args.min_strict_side_margin,
        relaxed_min_score=args.relaxed_min_score,
        relaxed_score_quantile=args.relaxed_score_quantile,
        relaxed_side_margin_quantile=args.relaxed_side_margin_quantile,
        relaxed_rank_quantile=args.relaxed_rank_quantile,
        relaxed_min_side_margin=args.relaxed_min_side_margin,
        broad_min_score=args.broad_min_score,
        broad_min_score_pct=args.broad_min_score_pct,
        broad_min_side_margin_pct=args.broad_min_side_margin_pct,
        broad_min_entry_rank_pct=args.broad_min_entry_rank_pct,
        broad_include_one_failed=args.broad_include_one_failed,
        min_executable_pnl=args.min_executable_pnl,
        tail_loss_threshold=args.tail_loss_threshold,
        min_predicted_pnl=args.min_predicted_pnl,
    )
    numeric_features = available_features(
        train_rows,
        parse_csv(args.numeric_features),
        DEFAULT_NUMERIC_FEATURES,
    )
    categorical_features = available_features(
        train_rows,
        parse_csv(args.categorical_features),
        DEFAULT_CATEGORICAL_FEATURES,
    )
    scored, folds = chronological_broad_horizon_predictions(
        train_rows=train_rows,
        eval_rows=eval_rows,
        horizons=horizons,
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
    metrics = metric_summary(scored, horizons=horizons)
    threshold, chosen_all = threshold_summary(
        scored,
        horizons=horizons,
        prob_thresholds=parse_float_csv(args.prob_thresholds),
        ev_thresholds=parse_float_csv(args.ev_thresholds),
        tail_prob_thresholds=parse_float_csv(args.tail_prob_thresholds),
        require_model_used_options=[False, True],
    )
    default_chosen = choose_horizon(
        scored,
        horizons=horizons,
        prob_threshold=args.default_prob_threshold,
        ev_threshold=args.default_ev_threshold,
        tail_prob_threshold=args.default_tail_prob_threshold,
        require_model_used=args.default_require_model_used,
    )
    groups = group_summary(default_chosen, parse_group_specs(args.group_specs))
    train_groups = train_summary(train_rows, parse_group_specs(args.train_group_specs))

    run_dir = make_run_dir(args.output_dir, args.label)
    scored.to_csv(run_dir / "broad_horizon_viability_predictions.csv", index=False)
    folds.to_csv(run_dir / "broad_horizon_viability_fold_summary.csv", index=False)
    metrics.to_csv(run_dir / "broad_horizon_viability_metric_summary.csv", index=False)
    threshold.to_csv(run_dir / "broad_horizon_viability_threshold_summary.csv", index=False)
    chosen_all.to_csv(run_dir / "broad_horizon_viability_threshold_choices.csv", index=False)
    default_chosen.to_csv(run_dir / "broad_horizon_viability_default_choices.csv", index=False)
    groups.to_csv(run_dir / "broad_horizon_viability_group_summary.csv", index=False)
    train_groups.to_csv(run_dir / "broad_horizon_viability_train_summary.csv", index=False)
    if args.write_train_rows:
        train_rows.to_csv(run_dir / "broad_horizon_viability_train_rows.csv", index=False)

    config = {
        "eval_input": args.eval_input,
        "family_predictions": family_predictions,
        "horizons": horizons,
        "candidate": args.candidate,
        "score_kind": args.score_kind,
        "long_column": args.long_column,
        "short_column": args.short_column,
        "long_holding_column": args.long_holding_column,
        "short_holding_column": args.short_holding_column,
        "side_ev_penalty_rules": args.side_ev_penalty_rules,
        "broad_min_score": args.broad_min_score,
        "broad_min_score_pct": args.broad_min_score_pct,
        "broad_min_side_margin_pct": args.broad_min_side_margin_pct,
        "broad_min_entry_rank_pct": args.broad_min_entry_rank_pct,
        "broad_include_one_failed": args.broad_include_one_failed,
        "train_row_count": int(len(train_rows)),
        "eval_row_count": int(len(scored)),
        "max_train_rows": args.max_train_rows,
        "min_train_months": args.min_train_months,
        "min_train_rows": args.min_train_rows,
        "numeric_features": numeric_features,
        "categorical_features": categorical_features,
        "max_iter": args.max_iter,
        "learning_rate": args.learning_rate,
        "l2_regularization": args.l2_regularization,
        "max_leaf_nodes": args.max_leaf_nodes,
        "random_state": args.random_state,
        "min_executable_pnl": args.min_executable_pnl,
        "tail_loss_threshold": args.tail_loss_threshold,
        "prob_thresholds": args.prob_thresholds,
        "ev_thresholds": args.ev_thresholds,
        "tail_prob_thresholds": args.tail_prob_thresholds,
        "default_prob_threshold": args.default_prob_threshold,
        "default_ev_threshold": args.default_ev_threshold,
        "default_tail_prob_threshold": args.default_tail_prob_threshold,
        "default_require_model_used": args.default_require_model_used,
    }
    (run_dir / "config.json").write_text(
        json.dumps(config, indent=2, sort_keys=True, default=local_json_default) + "\n",
        encoding="utf-8",
    )

    print("Broad horizon viability train rows:", len(train_rows))
    print("Broad horizon viability metrics:")
    print(metrics.to_string(index=False))
    print("\nBroad horizon viability threshold summary:")
    print(threshold.head(40).to_string(index=False))
    print(f"artifacts: {run_dir}")
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--eval-input", type=Path, required=True)
    parser.add_argument("--family-predictions", action="append", required=True)
    parser.add_argument("--horizons", default=DEFAULT_HORIZONS)
    parser.add_argument("--candidate", default=DEFAULT_CANDIDATE)
    parser.add_argument("--score-kind", default=DEFAULT_SCORE_KIND)
    parser.add_argument("--long-column", default=DEFAULT_LONG_COLUMN)
    parser.add_argument("--short-column", default=DEFAULT_SHORT_COLUMN)
    parser.add_argument("--long-holding-column", default=DEFAULT_LONG_HOLDING_COLUMN)
    parser.add_argument("--short-holding-column", default=DEFAULT_SHORT_HOLDING_COLUMN)
    parser.add_argument("--side-ev-penalty-rules", default="")
    parser.add_argument("--min-valid-predicted-hold-minutes", type=float, default=30.0)
    parser.add_argument("--max-predicted-hold-minutes", type=float, default=720.0)
    parser.add_argument("--min-strict-side-margin", type=float, default=0.0)
    parser.add_argument("--relaxed-min-score", type=float, default=5.0)
    parser.add_argument("--relaxed-score-quantile", type=float, default=0.90)
    parser.add_argument("--relaxed-side-margin-quantile", type=float, default=0.90)
    parser.add_argument("--relaxed-rank-quantile", type=float, default=0.80)
    parser.add_argument("--relaxed-min-side-margin", type=float, default=0.0)
    parser.add_argument("--broad-min-score", type=float, default=0.0)
    parser.add_argument("--broad-min-score-pct", type=float, default=0.90)
    parser.add_argument("--broad-min-side-margin-pct", type=float, default=0.90)
    parser.add_argument("--broad-min-entry-rank-pct", type=float, default=0.80)
    parser.add_argument("--broad-include-one-failed", action="store_true")
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
    parser.add_argument("--min-executable-pnl", type=float, default=0.0)
    parser.add_argument("--tail-loss-threshold", type=float, default=-5.0)
    parser.add_argument("--min-predicted-pnl", type=float, default=0.0)
    parser.add_argument("--prob-thresholds", default=DEFAULT_PROB_THRESHOLDS)
    parser.add_argument("--ev-thresholds", default=DEFAULT_EV_THRESHOLDS)
    parser.add_argument("--tail-prob-thresholds", default=DEFAULT_TAIL_PROB_THRESHOLDS)
    parser.add_argument("--default-prob-threshold", type=float, default=0.7)
    parser.add_argument("--default-ev-threshold", type=float, default=0.0)
    parser.add_argument("--default-tail-prob-threshold", type=float, default=0.5)
    parser.add_argument("--default-require-model-used", action="store_true")
    parser.add_argument("--group-specs", default=DEFAULT_GROUP_SPECS)
    parser.add_argument("--train-group-specs", default=DEFAULT_TRAIN_GROUP_SPECS)
    parser.add_argument("--write-train-rows", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=Path("data/reports/backtests"))
    parser.add_argument("--label", default="entry_ev_broad_horizon_viability")
    return parser


def main(argv: list[str] | None = None) -> int:
    build_diagnostics(build_parser().parse_args(argv))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
