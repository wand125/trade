#!/usr/bin/env python3
"""Chronological horizon-specific viability diagnostics for near-miss candidates."""

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
    train_universe_mask,
)


DEFAULT_HORIZONS = "60,240,720"
DEFAULT_PROB_THRESHOLDS = "0.50,0.60,0.70,0.80"
DEFAULT_EV_THRESHOLDS = "-2,0,2,5"
DEFAULT_TAIL_PROB_THRESHOLDS = "0.30,0.50,0.70"
DEFAULT_GROUP_SPECS = (
    "row_scope;selection_bucket;near_miss_bucket;role;family;month;side;"
    "family,month;role,month;side,combined_regime,session_regime;"
    "near_miss_bucket,side"
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


def add_horizon_targets(
    frame: pd.DataFrame,
    *,
    horizons: list[int],
    min_executable_pnl: float,
    tail_loss_threshold: float,
) -> pd.DataFrame:
    output = frame.copy()
    for horizon in horizons:
        pnl_column = f"side_fixed_{horizon}m_adjusted_pnl"
        pnl = numeric_series(output, pnl_column)
        output[f"target_fixed_{horizon}m_executable"] = pnl.ge(min_executable_pnl)
        output[f"target_fixed_{horizon}m_tail_loss"] = pnl.le(tail_loss_threshold)
    return output


def chronological_horizon_predictions(
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

    for horizon in horizons:
        scored[f"pred_hv_{horizon}m_executable_prob"] = 0.0
        scored[f"pred_hv_{horizon}m_pnl"] = 0.0
        scored[f"pred_hv_{horizon}m_tail_loss_prob"] = 0.0
        scored[f"pred_hv_{horizon}m_executable_model_used"] = False
        scored[f"pred_hv_{horizon}m_pnl_model_used"] = False
        scored[f"pred_hv_{horizon}m_tail_model_used"] = False

    for month in months:
        target_period = pd.Period(month, freq="M")
        train = scored[(periods < target_period) & base_train_mask].copy()
        target = scored[scored["month"].eq(month)].copy()
        train_months = int(train["month"].nunique()) if len(train) else 0
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
                scored.loc[
                    target.index,
                    f"pred_hv_{horizon}m_{target_name if target_name != 'tail_loss' else 'tail'}_model_used",
                ] = model_used

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


def choose_horizon(
    frame: pd.DataFrame,
    *,
    horizons: list[int],
    prob_threshold: float,
    ev_threshold: float,
    tail_prob_threshold: float,
    require_model_used: bool,
) -> pd.DataFrame:
    output = frame.copy()
    chosen_horizon = np.zeros(len(output), dtype=int)
    chosen_score = np.full(len(output), np.nan, dtype=float)
    actual_at_choice = np.full(len(output), np.nan, dtype=float)
    chosen_model_used = np.zeros(len(output), dtype=bool)
    for row_pos, (_, row) in enumerate(output.iterrows()):
        best_score = -np.inf
        best_horizon = 0
        best_actual = np.nan
        best_model_used = False
        for horizon in horizons:
            prob = float(row.get(f"pred_hv_{horizon}m_executable_prob", 0.0))
            pred_pnl = float(row.get(f"pred_hv_{horizon}m_pnl", np.nan))
            tail_prob = float(row.get(f"pred_hv_{horizon}m_tail_loss_prob", 1.0))
            model_used = bool(row.get(f"pred_hv_{horizon}m_executable_model_used", False)) and bool(
                row.get(f"pred_hv_{horizon}m_pnl_model_used", False)
            ) and bool(row.get(f"pred_hv_{horizon}m_tail_model_used", False))
            if require_model_used and not model_used:
                continue
            if not np.isfinite(pred_pnl):
                continue
            if prob < prob_threshold or pred_pnl < ev_threshold or tail_prob > tail_prob_threshold:
                continue
            score = prob * pred_pnl
            if score > best_score:
                best_score = score
                best_horizon = int(horizon)
                best_actual = float(row.get(f"side_fixed_{horizon}m_adjusted_pnl", np.nan))
                best_model_used = model_used
        chosen_horizon[row_pos] = best_horizon
        chosen_score[row_pos] = best_score if best_horizon else np.nan
        actual_at_choice[row_pos] = best_actual
        chosen_model_used[row_pos] = best_model_used
    output["hv_chosen_horizon_minutes"] = chosen_horizon
    output["hv_chosen_score"] = chosen_score
    output["actual_pnl_at_hv_chosen_horizon"] = actual_at_choice
    output["hv_choice_executable"] = output["actual_pnl_at_hv_chosen_horizon"].ge(0.0)
    output["hv_choice_regret"] = (
        output["target_fixed_best_adjusted_pnl"].astype(float)
        - output["actual_pnl_at_hv_chosen_horizon"].astype(float)
    )
    output["hv_choice_model_used"] = chosen_model_used
    return output


def safe_auc_from_series(actual: pd.Series, pred: pd.Series) -> float:
    valid = actual.notna() & pred.notna()
    if not valid.any():
        return float("nan")
    target = actual[valid].astype(int)
    if target.nunique(dropna=True) < 2:
        return float("nan")
    return float(roc_auc_score(target, pred[valid]))


def metric_summary(scored: pd.DataFrame, *, horizons: list[int]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for scope, group in scored.groupby("row_scope", dropna=False):
        for horizon in horizons:
            specs = [
                (
                    "executable",
                    f"pred_hv_{horizon}m_executable_prob",
                    f"target_fixed_{horizon}m_executable",
                    "classifier",
                ),
                (
                    "pnl",
                    f"pred_hv_{horizon}m_pnl",
                    f"side_fixed_{horizon}m_adjusted_pnl",
                    "regressor",
                ),
                (
                    "tail_loss",
                    f"pred_hv_{horizon}m_tail_loss_prob",
                    f"target_fixed_{horizon}m_tail_loss",
                    "classifier",
                ),
            ]
            for target_name, pred_column, actual_column, kind in specs:
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
                        "horizon_minutes": int(horizon),
                        "target_name": target_name,
                        "prediction_column": pred_column,
                        "actual_column": actual_column,
                        "row_count": int(valid.sum()),
                        "pred_mean": float(pred[valid].mean()),
                        "actual_mean": float(actual[valid].mean()),
                        "bias": float(error.mean()),
                        "mae": float(error.abs().mean()),
                        "rmse": float(np.sqrt((error**2).mean())),
                        "spearman": safe_spearman(pred[valid], actual[valid]),
                        "auc": safe_auc_from_series(actual[valid], pred[valid])
                        if kind == "classifier"
                        else float("nan"),
                        "model_used_share": float(
                            bool_series(
                                group.loc[valid],
                                f"pred_hv_{horizon}m_{target_name if target_name != 'tail_loss' else 'tail'}_model_used",
                            ).mean()
                        ),
                    }
                )
    return pd.DataFrame(rows)


def summarize_choice(frame: pd.DataFrame) -> dict[str, Any]:
    chosen = numeric_series(frame, "hv_chosen_horizon_minutes", default=0.0).gt(0.0)
    actual = numeric_series(frame, "actual_pnl_at_hv_chosen_horizon")
    return {
        "row_count": int(len(frame)),
        "selected_count": int(bool_series(frame, "selected_any").sum()),
        "target_fixed_best_pnl_sum": float(
            numeric_series(frame, "target_fixed_best_adjusted_pnl").sum()
        ),
        "fixed60_sum": float(numeric_series(frame, "side_fixed_60m_adjusted_pnl").sum()),
        "fixed240_sum": float(numeric_series(frame, "side_fixed_240m_adjusted_pnl").sum()),
        "fixed720_sum": float(numeric_series(frame, "side_fixed_720m_adjusted_pnl").sum()),
        "oracle_best_sum": float(numeric_series(frame, "side_best_adjusted_pnl").sum()),
        "chosen_count": int(chosen.sum()),
        "chosen_actual_pnl_sum": float(actual[chosen].sum()) if chosen.any() else 0.0,
        "chosen_actual_pnl_mean": float(actual[chosen].mean()) if chosen.any() else float("nan"),
        "chosen_executable_count": int(bool_series(frame, "hv_choice_executable").sum()),
        "chosen_model_used_count": int(bool_series(frame, "hv_choice_model_used").sum()),
        "choice_regret_sum": float(numeric_series(frame, "hv_choice_regret").dropna().sum()),
    }


def threshold_summary(
    scored: pd.DataFrame,
    *,
    horizons: list[int],
    prob_thresholds: list[float],
    ev_thresholds: list[float],
    tail_prob_thresholds: list[float],
    require_model_used_options: list[bool],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[dict[str, Any]] = []
    chosen_frames: list[pd.DataFrame] = []
    for require_model_used in require_model_used_options:
        for prob_threshold in prob_thresholds:
            for ev_threshold in ev_thresholds:
                for tail_prob_threshold in tail_prob_thresholds:
                    chosen = choose_horizon(
                        scored,
                        horizons=horizons,
                        prob_threshold=prob_threshold,
                        ev_threshold=ev_threshold,
                        tail_prob_threshold=tail_prob_threshold,
                        require_model_used=require_model_used,
                    )
                    chosen["prob_threshold"] = float(prob_threshold)
                    chosen["ev_threshold"] = float(ev_threshold)
                    chosen["tail_prob_threshold"] = float(tail_prob_threshold)
                    chosen["require_model_used"] = bool(require_model_used)
                    chosen_frames.append(chosen)
                    for scope, group in chosen.groupby("row_scope", dropna=False):
                        row = {
                            "row_scope": scope,
                            "prob_threshold": float(prob_threshold),
                            "ev_threshold": float(ev_threshold),
                            "tail_prob_threshold": float(tail_prob_threshold),
                            "require_model_used": bool(require_model_used),
                        }
                        row.update(summarize_choice(group))
                        rows.append(row)
    summary = pd.DataFrame(rows).sort_values(
        ["row_scope", "chosen_actual_pnl_sum", "chosen_count"],
        ascending=[True, False, False],
    )
    chosen_all = pd.concat(chosen_frames, ignore_index=True) if chosen_frames else pd.DataFrame()
    return summary, chosen_all


def group_summary(chosen: pd.DataFrame, group_specs: list[list[str]]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for columns in group_specs:
        available = [column for column in columns if column in chosen.columns]
        if not available:
            continue
        for key, group in chosen.groupby(available, dropna=False):
            if not isinstance(key, tuple):
                key = (key,)
            row = {
                "group_spec": ",".join(available),
                "group_key": "|".join(str(value) for value in key),
            }
            row.update(dict(zip(available, key)))
            row.update(summarize_choice(group))
            rows.append(row)
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(
        ["group_spec", "chosen_actual_pnl_sum", "chosen_count"],
        ascending=[True, False, False],
    )


def build_diagnostics(args: argparse.Namespace) -> Path:
    horizons = parse_int_csv(args.horizons)
    raw = pd.read_csv(args.input)
    rows = normalize_rows(raw, horizons=horizons)
    rows = add_horizon_targets(
        rows,
        horizons=horizons,
        min_executable_pnl=args.min_executable_pnl,
        tail_loss_threshold=args.tail_loss_threshold,
    )
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
    scored, folds = chronological_horizon_predictions(
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
    metrics = metric_summary(scored, horizons=horizons)
    groups = group_summary(default_chosen, parse_group_specs(args.group_specs))

    run_dir = make_run_dir(args.output_dir, args.label)
    scored.to_csv(run_dir / "near_miss_horizon_viability_predictions.csv", index=False)
    folds.to_csv(run_dir / "near_miss_horizon_viability_fold_summary.csv", index=False)
    metrics.to_csv(run_dir / "near_miss_horizon_viability_metric_summary.csv", index=False)
    threshold.to_csv(run_dir / "near_miss_horizon_viability_threshold_summary.csv", index=False)
    chosen_all.to_csv(run_dir / "near_miss_horizon_viability_threshold_choices.csv", index=False)
    default_chosen.to_csv(run_dir / "near_miss_horizon_viability_default_choices.csv", index=False)
    groups.to_csv(run_dir / "near_miss_horizon_viability_group_summary.csv", index=False)
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
        "min_executable_pnl": args.min_executable_pnl,
        "tail_loss_threshold": args.tail_loss_threshold,
        "prob_thresholds": args.prob_thresholds,
        "ev_thresholds": args.ev_thresholds,
        "tail_prob_thresholds": args.tail_prob_thresholds,
        "default_prob_threshold": args.default_prob_threshold,
        "default_ev_threshold": args.default_ev_threshold,
        "default_tail_prob_threshold": args.default_tail_prob_threshold,
        "default_require_model_used": args.default_require_model_used,
        "row_count": int(len(scored)),
    }
    (run_dir / "config.json").write_text(
        json.dumps(config, indent=2, sort_keys=True, default=local_json_default) + "\n",
        encoding="utf-8",
    )

    print("Near-miss horizon viability metrics:")
    print(metrics.to_string(index=False))
    print("\nNear-miss horizon viability threshold summary:")
    print(threshold.head(40).to_string(index=False))
    print(f"artifacts: {run_dir}")
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--horizons", default=DEFAULT_HORIZONS)
    parser.add_argument("--train-universe", default="all")
    parser.add_argument("--min-train-months", type=int, default=2)
    parser.add_argument("--min-train-rows", type=int, default=20)
    parser.add_argument("--numeric-features", default="")
    parser.add_argument("--categorical-features", default="")
    parser.add_argument("--max-iter", type=int, default=80)
    parser.add_argument("--learning-rate", type=float, default=0.05)
    parser.add_argument("--l2-regularization", type=float, default=1.0)
    parser.add_argument("--max-leaf-nodes", type=int, default=8)
    parser.add_argument("--random-state", type=int, default=42)
    parser.add_argument("--min-executable-pnl", type=float, default=0.0)
    parser.add_argument("--tail-loss-threshold", type=float, default=-5.0)
    parser.add_argument("--prob-thresholds", default=DEFAULT_PROB_THRESHOLDS)
    parser.add_argument("--ev-thresholds", default=DEFAULT_EV_THRESHOLDS)
    parser.add_argument("--tail-prob-thresholds", default=DEFAULT_TAIL_PROB_THRESHOLDS)
    parser.add_argument("--default-prob-threshold", type=float, default=0.7)
    parser.add_argument("--default-ev-threshold", type=float, default=0.0)
    parser.add_argument("--default-tail-prob-threshold", type=float, default=0.5)
    parser.add_argument("--default-require-model-used", action="store_true")
    parser.add_argument("--group-specs", default=DEFAULT_GROUP_SPECS)
    parser.add_argument("--output-dir", type=Path, default=Path("data/reports/backtests"))
    parser.add_argument("--label", default="entry_ev_near_miss_horizon_viability")
    return parser


def main(argv: list[str] | None = None) -> int:
    build_diagnostics(build_parser().parse_args(argv))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
