from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable, Sequence

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor

from trade_data.backtest import read_ohlcv
from trade_data.next_bar import (
    OddsCalibrationConfig,
    apply_empirical_odds_calibrator,
    build_feature_frame,
    fit_empirical_odds_calibrator,
    resample_complete_bars,
    validate_m1_frame,
    validate_stationary_feature_set,
)


@dataclass(frozen=True)
class EVConfig:
    timeframes: tuple[int, ...] = (15,)
    min_confidence: float = 0.54
    tail_loss_atr: float = 0.75
    max_tail_probability: float = 0.25
    min_expected_ev_atr: float = 0.0
    loss_multiplier: float = 1.00
    decision_round_trip_cost: float = 0.05
    round_trip_costs: tuple[float, ...] = (0.0, 0.05, 0.10, 0.20, 0.30)
    stop_atr_levels: tuple[float, ...] = (0.50, 0.75, 1.00, 1.50, 2.00)
    max_train_rows: int = 250_000
    max_iter: int = 150
    learning_rate: float = 0.05
    max_leaf_nodes: int = 15
    min_samples_leaf: int = 100
    l2_regularization: float = 2.0
    random_seed: int = 42
    odds_bins: int = 8
    odds_min_support: int = 200
    odds_prior_strength: float = 200.0


@dataclass(frozen=True)
class ConstantProbabilityModel:
    probability: float

    def predict_proba(self, rows: pd.DataFrame) -> np.ndarray:
        positive = np.full(len(rows), self.probability, dtype="float64")
        return np.column_stack([1 - positive, positive])


def parse_timeframes(value: str) -> tuple[int, ...]:
    values = tuple(int(item.strip()) for item in value.split(",") if item.strip())
    if not values or any(item <= 0 for item in values):
        raise argparse.ArgumentTypeError("timeframes must be positive comma-separated integers")
    return values


def parse_float_tuple(value: str) -> tuple[float, ...]:
    try:
        values = tuple(float(item.strip()) for item in value.split(",") if item.strip())
    except ValueError as error:
        raise argparse.ArgumentTypeError("expected comma-separated numbers") from error
    if not values or any(item < 0 for item in values):
        raise argparse.ArgumentTypeError("values must be non-negative")
    return values


def _atr_absolute(bars: pd.DataFrame, window: int = 20) -> pd.Series:
    previous_close = bars["close"].shift(1)
    true_range = pd.concat(
        [
            bars["high"] - bars["low"],
            (bars["high"] - previous_close).abs(),
            (bars["low"] - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return true_range.rolling(window, min_periods=window).mean()


def build_ev_dataset(
    m1: pd.DataFrame,
    predictions: pd.DataFrame,
    timeframe_minutes: int,
    feature_columns: Sequence[str],
    feature_set: str = "baseline",
) -> tuple[pd.DataFrame, list[str]]:
    source = validate_m1_frame(m1)
    bars = resample_complete_bars(source, timeframe_minutes)
    features, generated_columns = build_feature_frame(bars, timeframe_minutes, feature_set)
    missing = sorted(set(feature_columns) - set(generated_columns))
    if missing:
        raise ValueError(f"cannot regenerate EV features: {', '.join(missing)}")
    validate_stationary_feature_set(feature_columns)
    features = features[["timestamp", *feature_columns]].copy()
    atr = bars[["timestamp"]].copy()
    atr["atr_absolute_20"] = _atr_absolute(bars)
    features = features.merge(atr, on="timestamp", how="left", validate="one_to_one")
    execution = bars[
        ["timestamp", "open", "high", "low", "close"]
    ].copy()
    execution = execution.rename(
        columns={
            "timestamp": "decision_timestamp",
            "open": "target_open",
            "high": "target_high",
            "low": "target_low",
            "close": "target_close",
        }
    )

    required_predictions = {
        "timestamp",
        "decision_timestamp",
        "target_timestamp",
        "target_up",
        "next_bar_body",
        "probability_up",
        "predicted_up",
        "predicted_direction",
        "confidence",
        "correct",
        "volatility_regime",
        "fold",
    }
    missing_predictions = sorted(required_predictions - set(predictions.columns))
    if missing_predictions:
        raise ValueError(
            f"predictions are missing EV columns: {', '.join(missing_predictions)}"
        )
    prediction_columns = list(required_predictions)
    frame = predictions[prediction_columns].merge(
        features, on="timestamp", how="inner", validate="many_to_one"
    )
    frame["decision_timestamp"] = pd.to_datetime(frame["decision_timestamp"], utc=True)
    frame = frame.merge(
        execution, on="decision_timestamp", how="left", validate="many_to_one"
    )
    direction_sign = np.where(frame["predicted_direction"].eq("up"), 1.0, -1.0)
    frame["model_confidence"] = frame["confidence"].astype("float64")
    frame["direction_score"] = 2 * frame["probability_up"].astype("float64") - 1
    frame["realized_gross_price"] = direction_sign * frame["next_bar_body"]
    frame["realized_signed_atr"] = (
        frame["realized_gross_price"] / frame["atr_absolute_20"]
    )
    frame["realized_magnitude_atr"] = frame["realized_signed_atr"].abs()
    adverse_price = np.where(
        direction_sign > 0,
        frame["target_open"] - frame["target_low"],
        frame["target_high"] - frame["target_open"],
    )
    frame["realized_mae_atr"] = adverse_price / frame["atr_absolute_20"]
    frame["tail_loss"] = frame["realized_signed_atr"] <= -0.75
    ev_features = [
        *feature_columns,
        "probability_up",
        "predicted_up",
        "model_confidence",
        "direction_score",
    ]
    validate_stationary_feature_set(ev_features)
    finite = np.isfinite(frame[[*ev_features, "atr_absolute_20", "realized_signed_atr"]]).all(
        axis=1
    )
    frame = frame.loc[finite & frame["atr_absolute_20"].gt(0)].copy()
    frame = frame.sort_values("decision_timestamp").reset_index(drop=True)
    return frame, ev_features


def _even_sample(frame: pd.DataFrame, max_rows: int) -> pd.DataFrame:
    if max_rows <= 0 or len(frame) <= max_rows:
        return frame
    indices = np.linspace(0, len(frame) - 1, max_rows, dtype="int64")
    return frame.iloc[indices]


def _regressor(config: EVConfig, loss: str, quantile: float | None = None):
    parameters = {
        "loss": loss,
        "max_iter": config.max_iter,
        "learning_rate": config.learning_rate,
        "max_leaf_nodes": config.max_leaf_nodes,
        "min_samples_leaf": config.min_samples_leaf,
        "l2_regularization": config.l2_regularization,
        "early_stopping": False,
        "random_state": config.random_seed,
    }
    if quantile is not None:
        parameters["quantile"] = quantile
    return HistGradientBoostingRegressor(**parameters)


def fit_ev_models(
    train: pd.DataFrame,
    feature_columns: Sequence[str],
    config: EVConfig,
) -> dict[str, object]:
    sampled = _even_sample(train, config.max_train_rows)
    correct = sampled.loc[sampled["correct"].astype(bool)]
    wrong = sampled.loc[~sampled["correct"].astype(bool)]
    if len(correct) < 100 or len(wrong) < 100:
        raise ValueError("EV training needs at least 100 correct and 100 wrong rows")
    gain_mean = _regressor(config, "squared_error")
    gain_q25 = _regressor(config, "quantile", 0.25)
    loss_mean = _regressor(config, "squared_error")
    loss_q75 = _regressor(config, "quantile", 0.75)
    gain_mean.fit(correct[list(feature_columns)], correct["realized_magnitude_atr"])
    gain_q25.fit(correct[list(feature_columns)], correct["realized_magnitude_atr"])
    loss_mean.fit(wrong[list(feature_columns)], wrong["realized_magnitude_atr"])
    loss_q75.fit(wrong[list(feature_columns)], wrong["realized_magnitude_atr"])

    realized_risk_adjusted_atr = sampled["realized_signed_atr"].where(
        sampled["realized_signed_atr"] >= 0,
        sampled["realized_signed_atr"] * config.loss_multiplier,
    )
    direct_risk_mean = _regressor(config, "squared_error")
    direct_risk_q25 = _regressor(config, "quantile", 0.25)
    direct_risk_mean.fit(sampled[list(feature_columns)], realized_risk_adjusted_atr)
    direct_risk_q25.fit(sampled[list(feature_columns)], realized_risk_adjusted_atr)

    tail_labels = (
        sampled["realized_signed_atr"] <= -config.tail_loss_atr
    ).astype("int8")
    if tail_labels.nunique() == 1:
        tail_model: object = ConstantProbabilityModel(float(tail_labels.iloc[0]))
    else:
        tail_model = HistGradientBoostingClassifier(
            max_iter=config.max_iter,
            learning_rate=config.learning_rate,
            max_leaf_nodes=config.max_leaf_nodes,
            min_samples_leaf=config.min_samples_leaf,
            l2_regularization=config.l2_regularization,
            early_stopping=False,
            random_state=config.random_seed,
        )
        tail_model.fit(sampled[list(feature_columns)], tail_labels)
    return {
        "gain_mean": gain_mean,
        "gain_q25": gain_q25,
        "loss_mean": loss_mean,
        "loss_q75": loss_q75,
        "direct_risk_mean": direct_risk_mean,
        "direct_risk_q25": direct_risk_q25,
        "tail_model": tail_model,
        "feature_columns": list(feature_columns),
        "training_rows": len(sampled),
        "correct_rows": len(correct),
        "wrong_rows": len(wrong),
    }


def predict_ev(
    frame: pd.DataFrame,
    models: dict[str, object],
    odds_calibrator: dict[str, object],
    config: EVConfig,
) -> pd.DataFrame:
    output = frame.copy()
    columns = list(models["feature_columns"])
    inputs = output[columns]
    output["predicted_gain_mean_atr"] = np.clip(
        models["gain_mean"].predict(inputs), 0, None
    )
    output["predicted_gain_q25_atr"] = np.clip(
        models["gain_q25"].predict(inputs), 0, None
    )
    output["predicted_loss_mean_atr"] = np.clip(
        models["loss_mean"].predict(inputs), 0, None
    )
    output["predicted_loss_q75_atr"] = np.clip(
        models["loss_q75"].predict(inputs), 0, None
    )
    output["tail_loss_probability"] = models["tail_model"].predict_proba(inputs)[:, 1]
    odds = apply_empirical_odds_calibrator(output, odds_calibrator)
    output["correct_probability"] = output["model_confidence"]
    output["correct_probability_lower"] = odds["confidence_lower"].to_numpy()
    probability = output["correct_probability"].to_numpy(dtype="float64")
    lower = np.minimum(
        probability, output["correct_probability_lower"].to_numpy(dtype="float64")
    )
    output["expected_ev_atr"] = (
        probability * output["predicted_gain_mean_atr"]
        - (1 - probability) * output["predicted_loss_mean_atr"]
    )
    output["risk_adjusted_expected_ev_atr"] = (
        probability * output["predicted_gain_mean_atr"]
        - config.loss_multiplier
        * (1 - probability)
        * output["predicted_loss_mean_atr"]
    )
    output["conservative_ev_atr"] = (
        lower * output["predicted_gain_q25_atr"]
        - config.loss_multiplier
        * (1 - lower)
        * output["predicted_loss_q75_atr"]
    )
    mean_loss = config.loss_multiplier * output["predicted_loss_mean_atr"]
    conservative_loss = config.loss_multiplier * output["predicted_loss_q75_atr"]
    output["breakeven_probability"] = mean_loss / (
        output["predicted_gain_mean_atr"] + mean_loss
    ).replace(0, np.nan)
    output["probability_edge"] = probability - output["breakeven_probability"]
    output["kelly_fraction_raw"] = np.clip(
        probability
        - (1 - probability)
        * mean_loss
        / output["predicted_gain_mean_atr"].replace(0, np.nan),
        0,
        1,
    ).fillna(0)
    output["kelly_fraction_conservative"] = np.clip(
        lower
        - (1 - lower)
        * conservative_loss
        / output["predicted_gain_q25_atr"].replace(0, np.nan),
        0,
        1,
    ).fillna(0)
    cost_atr = config.decision_round_trip_cost / output["atr_absolute_20"]
    output["risk_adjusted_ev_after_cost_atr"] = (
        output["risk_adjusted_expected_ev_atr"] - cost_atr
    )
    output["conservative_ev_after_cost_atr"] = output["conservative_ev_atr"] - cost_atr
    output["direct_risk_ev_atr"] = models["direct_risk_mean"].predict(inputs)
    output["direct_risk_q25_atr"] = models["direct_risk_q25"].predict(inputs)
    output["expected_ev_price"] = output["expected_ev_atr"] * output["atr_absolute_20"]
    output["conservative_ev_price"] = (
        output["conservative_ev_atr"] * output["atr_absolute_20"]
    )
    output["tail_loss"] = output["realized_signed_atr"] <= -config.tail_loss_atr
    output["realized_risk_adjusted_atr"] = output["realized_signed_atr"].where(
        output["realized_signed_atr"] >= 0,
        output["realized_signed_atr"] * config.loss_multiplier,
    )
    return output


def _max_drawdown(values: pd.Series) -> float:
    if values.empty:
        return 0.0
    equity = values.cumsum()
    return float((equity.cummax() - equity).max())


def evaluate_ev_selection(
    frame: pd.DataFrame,
    selected: pd.Series | np.ndarray,
    config: EVConfig,
) -> dict[str, object]:
    mask = np.asarray(selected, dtype=bool)
    chosen = frame.loc[mask].copy()
    rows = len(chosen)
    total_rows = len(frame)
    if not rows:
        return {
            "rows": 0,
            "coverage": 0.0,
            "accuracy": None,
            "gross_total": 0.0,
            "gross_mean": None,
            "profit_factor": None,
            "positive_gross_folds": 0,
            "risk_adjusted_total": 0.0,
            "risk_adjusted_mean": None,
            "positive_risk_adjusted_folds": 0,
            "cost_sensitivity": [],
        }
    gross = chosen["realized_gross_price"].astype("float64")
    positive = gross[gross > 0]
    negative = gross[gross < 0]
    risk_adjusted = gross.where(gross >= 0, gross * config.loss_multiplier)
    fold_frame = chosen[["fold"]].copy()
    fold_frame["gross"] = gross
    fold_frame["risk_adjusted"] = risk_adjusted
    fold_metrics = []
    for fold, group in fold_frame.groupby("fold", sort=False):
        fold_metrics.append(
            {
                "fold": str(fold),
                "rows": len(group),
                "gross_total": float(group["gross"].sum()),
                "gross_mean": float(group["gross"].mean()),
                "risk_adjusted_total": float(group["risk_adjusted"].sum()),
                "risk_adjusted_mean": float(group["risk_adjusted"].mean()),
            }
        )
    cost_rows = []
    for cost in config.round_trip_costs:
        net = gross - cost
        risk_net = risk_adjusted - cost
        cost_fold_frame = chosen[["fold"]].copy()
        cost_fold_frame["net"] = net
        cost_fold_total = cost_fold_frame.groupby("fold", sort=False)["net"].sum()
        cost_fold_mean = cost_fold_frame.groupby("fold", sort=False)["net"].mean()
        cost_rows.append(
            {
                "round_trip_cost": float(cost),
                "net_total": float(net.sum()),
                "net_mean": float(net.mean()),
                "risk_adjusted_net_total": float(risk_net.sum()),
                "risk_adjusted_net_mean": float(risk_net.mean()),
                "positive_net_folds": int((cost_fold_total > 0).sum()),
                "worst_fold_net_mean": float(cost_fold_mean.min()),
                "max_drawdown": _max_drawdown(net),
            }
        )
    stop_rows = []
    for stop_atr in config.stop_atr_levels:
        stop_hit = chosen["realized_mae_atr"].ge(stop_atr)
        stopped_gross = gross.where(
            ~stop_hit, -stop_atr * chosen["atr_absolute_20"].astype("float64")
        )
        stopped_risk = stopped_gross.where(
            stopped_gross >= 0, stopped_gross * config.loss_multiplier
        )
        stopped_fold_total = pd.DataFrame(
            {"fold": chosen["fold"], "pnl": stopped_gross}
        ).groupby("fold", sort=False)["pnl"].sum()
        stopped_risk_fold_total = pd.DataFrame(
            {"fold": chosen["fold"], "pnl": stopped_risk}
        ).groupby("fold", sort=False)["pnl"].sum()
        stop_rows.append(
            {
                "stop_atr": float(stop_atr),
                "stop_hits": int(stop_hit.sum()),
                "stop_hit_rate": float(stop_hit.mean()),
                "gross_total": float(stopped_gross.sum()),
                "gross_mean": float(stopped_gross.mean()),
                "risk_adjusted_total": float(stopped_risk.sum()),
                "risk_adjusted_mean": float(stopped_risk.mean()),
                "positive_gross_folds": int((stopped_fold_total > 0).sum()),
                "positive_risk_adjusted_folds": int(
                    (stopped_risk_fold_total > 0).sum()
                ),
                "cost_005_total": float((stopped_gross - 0.05).sum()),
                "risk_adjusted_cost_005_total": float(
                    (stopped_risk - 0.05).sum()
                ),
                "max_drawdown": _max_drawdown(stopped_gross),
            }
        )
    return {
        "rows": rows,
        "coverage": float(rows / total_rows),
        "accuracy": float(chosen["correct"].mean()),
        "gross_total": float(gross.sum()),
        "gross_mean": float(gross.mean()),
        "gross_median": float(gross.median()),
        "average_win": float(positive.mean()) if len(positive) else None,
        "average_loss_abs": float(-negative.mean()) if len(negative) else None,
        "profit_factor": (
            float(positive.sum() / -negative.sum()) if len(negative) else None
        ),
        "positive_gross_folds": int(
            sum(row["gross_total"] > 0 for row in fold_metrics)
        ),
        "risk_adjusted_total": float(risk_adjusted.sum()),
        "risk_adjusted_mean": float(risk_adjusted.mean()),
        "positive_risk_adjusted_folds": int(
            sum(row["risk_adjusted_total"] > 0 for row in fold_metrics)
        ),
        "break_even_round_trip_cost": float(gross.mean()),
        "all_fold_cost_ceiling": float(
            min(row["gross_mean"] for row in fold_metrics)
        ),
        "decision_cost_headroom": float(
            min(row["gross_mean"] for row in fold_metrics)
            - config.decision_round_trip_cost
        ),
        "mean_expected_ev_atr": float(chosen["expected_ev_atr"].mean()),
        "mean_risk_adjusted_expected_ev_atr": float(
            chosen["risk_adjusted_expected_ev_atr"].mean()
        ),
        "mean_conservative_ev_atr": float(chosen["conservative_ev_atr"].mean()),
        "mean_direct_risk_ev_atr": float(chosen["direct_risk_ev_atr"].mean()),
        "mean_direct_risk_q25_atr": float(chosen["direct_risk_q25_atr"].mean()),
        "mean_probability_edge": float(chosen["probability_edge"].mean()),
        "mean_kelly_fraction_raw": float(chosen["kelly_fraction_raw"].mean()),
        "mean_kelly_fraction_conservative": float(
            chosen["kelly_fraction_conservative"].mean()
        ),
        "actual_mean_risk_adjusted_atr": float(
            chosen["realized_risk_adjusted_atr"].mean()
        ),
        "direct_risk_ev_bias_atr": float(
            (
                chosen["direct_risk_ev_atr"]
                - chosen["realized_risk_adjusted_atr"]
            ).mean()
        ),
        "mean_tail_loss_probability": float(chosen["tail_loss_probability"].mean()),
        "actual_tail_loss_rate": float(chosen["tail_loss"].mean()),
        "fold_metrics": fold_metrics,
        "cost_sensitivity": cost_rows,
        "stop_sensitivity": stop_rows,
    }


def candidate_masks(frame: pd.DataFrame, config: EVConfig) -> dict[str, pd.Series]:
    direction = frame["model_confidence"] >= config.min_confidence
    expected = frame["expected_ev_atr"] > config.min_expected_ev_atr
    tail = frame["tail_loss_probability"] <= config.max_tail_probability
    risk_adjusted = frame["risk_adjusted_expected_ev_atr"] > 0
    direct_risk = frame["direct_risk_ev_atr"] > 0
    direct_risk_q25 = frame["direct_risk_q25_atr"] > 0
    deployable_mean = frame["risk_adjusted_ev_after_cost_atr"] > 0
    deployable_conservative = frame["conservative_ev_after_cost_atr"] > 0
    conservative = frame["conservative_ev_atr"] > 0
    return {
        "direction_only": direction,
        "expected_ev_positive": direction & expected,
        "expected_ev_tail": direction & expected & tail,
        "risk_adjusted_ev_positive": direction & risk_adjusted,
        "risk_adjusted_ev_tail": direction & risk_adjusted & tail,
        "direct_risk_ev_positive": direction & direct_risk,
        "direct_risk_ev_tail": direction & direct_risk & tail,
        "direct_risk_q25_positive": direction & direct_risk_q25 & tail,
        "deployable_mean_ev": direction & deployable_mean & tail,
        "deployable_conservative_ev": direction & deployable_conservative & tail,
        "conservative_ev_positive": direction & conservative & tail,
    }


def run_ev_walk_forward(
    m1: pd.DataFrame,
    predictions_dirs: Path | Sequence[Path],
    output_dir: Path,
    config: EVConfig,
) -> dict[str, object]:
    source_dirs = (
        [predictions_dirs] if isinstance(predictions_dirs, Path) else list(predictions_dirs)
    )
    if not source_dirs:
        raise ValueError("at least one predictions directory is required")
    manifests = [
        json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
        for directory in source_dirs
    ]
    output_dir.mkdir(parents=True, exist_ok=True)
    report: dict[str, object] = {
        "created_at": datetime.now(UTC).isoformat(),
        "config": asdict(config),
        "source_predictions": [str(directory) for directory in source_dirs],
        "execution_assumption": "enter next bar open, exit same bar close, one ounce",
        "timeframes": {},
    }
    output_manifest: dict[str, object] = {
        "format_version": 1,
        "created_at": report["created_at"],
        "kind": "next_bar_ev_walk_forward",
        "timeframes": {},
    }
    for timeframe in config.timeframes:
        name = f"M{timeframe}"
        entries = []
        prediction_frames = []
        for directory, manifest in zip(source_dirs, manifests, strict=True):
            if name not in manifest["timeframes"]:
                continue
            source_entry = manifest["timeframes"][name]
            entries.append(source_entry)
            prediction_frames.append(
                pd.read_parquet(directory / source_entry["predictions"])
            )
        if not entries:
            raise ValueError(f"prediction manifests do not contain {name}")
        feature_sets = {tuple(entry["features"]) for entry in entries}
        if len(feature_sets) != 1:
            raise ValueError(f"prediction feature sets differ for {name}")
        predictions = pd.concat(prediction_frames, ignore_index=True)
        duplicate = predictions.duplicated(["fold", "timestamp"])
        if duplicate.any():
            raise ValueError(f"duplicate fold/timestamp predictions for {name}")
        feature_columns_from_manifest = list(next(iter(feature_sets)))
        feature_set = "baseline"
        dataset, feature_columns = build_ev_dataset(
            m1, predictions, timeframe, feature_columns_from_manifest, feature_set
        )
        fold_order = [
            str(value)
            for value in (
                dataset.groupby("fold", sort=False)["decision_timestamp"].min().sort_values().index
            )
        ]
        fold_reports = []
        fold_predictions = []
        model_entries = []
        for position in range(1, len(fold_order)):
            train_folds = fold_order[:position]
            test_fold = fold_order[position]
            train = dataset.loc[dataset["fold"].astype(str).isin(train_folds)]
            test = dataset.loc[dataset["fold"].astype(str) == test_fold]
            models = fit_ev_models(train, feature_columns, config)
            odds = fit_empirical_odds_calibrator(
                train,
                OddsCalibrationConfig(
                    bins=config.odds_bins,
                    min_support=config.odds_min_support,
                    prior_strength=config.odds_prior_strength,
                ),
            )
            predicted = predict_ev(test, models, odds, config)
            model_name = f"m{timeframe}_{test_fold}_ev_models.joblib"
            joblib.dump(
                {
                    "models": models,
                    "odds_calibrator": odds,
                    "timeframe_minutes": timeframe,
                    "feature_set": feature_set,
                    "config": asdict(config),
                    "train_folds": train_folds,
                    "test_fold": test_fold,
                },
                output_dir / model_name,
            )
            masks = candidate_masks(predicted, config)
            fold_reports.append(
                {
                    "train_folds": train_folds,
                    "test_fold": test_fold,
                    "test_rows": len(predicted),
                    "candidates": {
                        candidate: evaluate_ev_selection(predicted, mask, config)
                        for candidate, mask in masks.items()
                    },
                }
            )
            predicted["ev_model_test_fold"] = test_fold
            fold_predictions.append(predicted)
            model_entries.append({"test_fold": test_fold, "model": model_name})
        if not fold_predictions:
            raise ValueError(f"at least two prediction folds are required for {name}")
        combined = pd.concat(fold_predictions, ignore_index=True)
        prediction_name = f"m{timeframe}_ev_walk_forward_predictions.parquet"
        combined.to_parquet(output_dir / prediction_name, index=False)
        aggregate_masks = candidate_masks(combined, config)
        report["timeframes"][name] = {
            "rows": len(combined),
            "folds": fold_reports,
            "aggregate_candidates": {
                candidate: evaluate_ev_selection(combined, mask, config)
                for candidate, mask in aggregate_masks.items()
            },
        }
        output_manifest["timeframes"][name] = {
            "minutes": timeframe,
            "features": feature_columns,
            "models": model_entries,
            "predictions": prediction_name,
        }
    (output_dir / "metrics.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (output_dir / "manifest.json").write_text(
        json.dumps(output_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Estimate magnitude, tail risk, and executable EV for next-bar predictions."
    )
    parser.add_argument("--input", type=Path, required=True, help="UTC M1 OHLC parquet")
    parser.add_argument(
        "--predictions-dir",
        type=Path,
        action="append",
        required=True,
        help="repeat to combine non-overlapping walk-forward prediction sets",
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--timeframes", type=parse_timeframes, default=(15,))
    parser.add_argument("--min-confidence", type=float, default=0.54)
    parser.add_argument("--tail-loss-atr", type=float, default=0.75)
    parser.add_argument("--max-tail-probability", type=float, default=0.25)
    parser.add_argument("--min-expected-ev-atr", type=float, default=0.0)
    parser.add_argument("--loss-multiplier", type=float, default=1.00)
    parser.add_argument("--decision-round-trip-cost", type=float, default=0.05)
    parser.add_argument(
        "--round-trip-costs", type=parse_float_tuple, default=(0.0, 0.05, 0.10, 0.20, 0.30)
    )
    parser.add_argument(
        "--stop-atr-levels", type=parse_float_tuple, default=(0.50, 0.75, 1.00, 1.50, 2.00)
    )
    parser.add_argument("--max-train-rows", type=int, default=250_000)
    parser.add_argument("--max-iter", type=int, default=150)
    parser.add_argument("--learning-rate", type=float, default=0.05)
    parser.add_argument("--max-leaf-nodes", type=int, default=15)
    parser.add_argument("--min-samples-leaf", type=int, default=100)
    parser.add_argument("--l2-regularization", type=float, default=2.0)
    parser.add_argument("--random-seed", type=int, default=42)
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    config = EVConfig(
        timeframes=tuple(args.timeframes),
        min_confidence=args.min_confidence,
        tail_loss_atr=args.tail_loss_atr,
        max_tail_probability=args.max_tail_probability,
        min_expected_ev_atr=args.min_expected_ev_atr,
        loss_multiplier=args.loss_multiplier,
        decision_round_trip_cost=args.decision_round_trip_cost,
        round_trip_costs=tuple(args.round_trip_costs),
        stop_atr_levels=tuple(args.stop_atr_levels),
        max_train_rows=args.max_train_rows,
        max_iter=args.max_iter,
        learning_rate=args.learning_rate,
        max_leaf_nodes=args.max_leaf_nodes,
        min_samples_leaf=args.min_samples_leaf,
        l2_regularization=args.l2_regularization,
        random_seed=args.random_seed,
    )
    report = run_ev_walk_forward(
        read_ohlcv(args.input), args.predictions_dir, args.output_dir, config
    )
    summary = {
        timeframe: values["aggregate_candidates"]
        for timeframe, values in report["timeframes"].items()
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
