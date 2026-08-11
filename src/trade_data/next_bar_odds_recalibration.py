from __future__ import annotations

import json
from collections import defaultdict, deque
from pathlib import Path
from typing import Sequence

import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression

from trade_data.next_bar import evaluate_odds_calibration, wilson_accuracy_lower_bound
from trade_data.next_bar_bootstrap import paired_daily_block_bootstrap
from trade_data.next_bar_registry import DEFAULT_DEVELOPMENT_FOLDS, read_prediction_sets


REQUIRED_COLUMNS = {"fold", "timestamp", "confidence", "correct"}
DEFAULT_ODDS_THRESHOLDS = (0.515, 0.525, 0.535, 0.55)
DEFAULT_ADAPTIVE_THRESHOLDS = (0.51, 0.515, 0.525, 0.535, 0.55)
DEFAULT_ADAPTIVE_LOWER_THRESHOLDS = (0.5, 0.515)
DEFAULT_ADAPTIVE_BAND_EDGES = (0.5, 0.51, 0.515, 0.525, 0.535, 0.55, 0.575, 0.6, 1.0)
ADAPTIVE_REQUIRED_COLUMNS = REQUIRED_COLUMNS | {
    "decision_timestamp",
    "target_timestamp",
    "predicted_direction",
    "volatility_regime",
}


def _fold_order(frame: pd.DataFrame) -> list[str]:
    return [
        str(value)
        for value in frame.groupby("fold", sort=False)["timestamp"].min().sort_values().index
    ]


def _platt_correctness_probability(
    train_confidence: np.ndarray,
    train_correct: np.ndarray,
    test_confidence: np.ndarray,
) -> np.ndarray:
    if np.unique(train_correct).size == 1:
        return np.full(len(test_confidence), float(train_correct[0]), dtype="float64")
    model = LogisticRegression(C=1e6, solver="lbfgs")
    model.fit(train_confidence.reshape(-1, 1), train_correct)
    return model.predict_proba(test_confidence.reshape(-1, 1))[:, 1]


def _correctness_lane_metrics(
    frame: pd.DataFrame, confidence_column: str, threshold: float
) -> dict[str, float | int | None]:
    selected = frame[confidence_column].ge(threshold)
    rows = int(selected.sum())
    coverage = float(selected.mean()) if len(frame) else 0.0
    if rows == 0:
        return {
            "rows": 0,
            "coverage": coverage,
            "accuracy": None,
            "mean_confidence": None,
            "wilson_lower": None,
            "selection_score": None,
        }
    successes = int(frame.loc[selected, "correct"].sum())
    lower = wilson_accuracy_lower_bound(successes, rows)
    return {
        "rows": rows,
        "coverage": coverage,
        "accuracy": float(successes / rows),
        "mean_confidence": float(frame.loc[selected, confidence_column].mean()),
        "wilson_lower": lower,
        "selection_score": float(np.sqrt(coverage) * (lower - 0.5)),
    }


def _method_report(
    frame: pd.DataFrame,
    methods: dict[str, str],
    thresholds: Sequence[float],
) -> dict[str, object]:
    return {
        name: {
            "probability": evaluate_odds_calibration(
                frame["correct"].to_numpy(), frame[column].to_numpy()
            ),
            "lanes": {
                str(threshold): _correctness_lane_metrics(
                    frame, column, threshold
                )
                for threshold in thresholds
            },
        }
        for name, column in methods.items()
    }


def _correctness_probability_frame(
    frame: pd.DataFrame, confidence_column: str
) -> pd.DataFrame:
    output = frame.copy()
    output["target_up"] = output["correct"].astype("int8")
    output["probability_up"] = output[confidence_column].astype("float64")
    output["confidence"] = output[confidence_column].astype("float64")
    return output


def chronological_correctness_recalibration(
    predictions: pd.DataFrame,
    thresholds: Sequence[float] = DEFAULT_ODDS_THRESHOLDS,
) -> tuple[pd.DataFrame, dict[str, object]]:
    """Fit correctness calibrators on prior OOS folds and evaluate the next fold."""
    missing = REQUIRED_COLUMNS.difference(predictions.columns)
    if missing:
        raise ValueError(f"predictions are missing columns: {sorted(missing)}")
    frame = predictions.copy()
    if frame.duplicated(["fold", "timestamp"]).any():
        raise ValueError("predictions contain duplicate fold/timestamp rows")
    confidence = frame["confidence"].to_numpy(dtype="float64")
    if not np.isfinite(confidence).all() or ((confidence < 0) | (confidence > 1)).any():
        raise ValueError("confidence must be finite and between zero and one")
    frame["correct"] = frame["correct"].astype(bool)
    order = _fold_order(frame)
    if len(order) < 2:
        raise ValueError("at least two chronological folds are required")
    if not thresholds or any(not 0.5 <= threshold < 1 for threshold in thresholds):
        raise ValueError("odds thresholds must be between 0.5 inclusive and 1")

    outputs: list[pd.DataFrame] = []
    fold_reports: list[dict[str, object]] = []
    for position in range(1, len(order)):
        calibration_folds = order[:position]
        evaluation_fold = order[position]
        train = frame.loc[frame["fold"].astype(str).isin(calibration_folds)]
        test = frame.loc[frame["fold"].astype(str).eq(evaluation_fold)].copy()
        train_confidence = train["confidence"].to_numpy(dtype="float64")
        train_correct = train["correct"].to_numpy(dtype="int8")
        test_confidence = test["confidence"].to_numpy(dtype="float64")

        isotonic = IsotonicRegression(y_min=0, y_max=1, out_of_bounds="clip")
        isotonic.fit(train_confidence, train_correct)
        test["isotonic_confidence"] = isotonic.predict(test_confidence)
        test["platt_correctness_confidence"] = _platt_correctness_probability(
            train_confidence, train_correct, test_confidence
        )
        test["odds_calibration_folds"] = len(calibration_folds)
        outputs.append(test)
        fold_reports.append(
            {
                "evaluation_fold": evaluation_fold,
                "calibration_folds": calibration_folds,
                "raw_model_confidence": evaluate_odds_calibration(
                    test["correct"].to_numpy(), test["confidence"].to_numpy()
                ),
                "isotonic": evaluate_odds_calibration(
                    test["correct"].to_numpy(),
                    test["isotonic_confidence"].to_numpy(),
                ),
                "platt_correctness": evaluate_odds_calibration(
                    test["correct"].to_numpy(),
                    test["platt_correctness_confidence"].to_numpy(),
                ),
                "fixed_lanes": {
                    name: {
                        str(threshold): _correctness_lane_metrics(
                            test, column, threshold
                        )
                        for threshold in thresholds
                    }
                    for name, column in {
                        "raw_model_confidence": "confidence",
                        "isotonic": "isotonic_confidence",
                        "platt_correctness": "platt_correctness_confidence",
                    }.items()
                },
            }
        )

    combined = pd.concat(outputs, ignore_index=True)
    methods = {
        "raw_model_confidence": "confidence",
        "isotonic": "isotonic_confidence",
        "platt_correctness": "platt_correctness_confidence",
    }
    combined_metrics = {
        name: evaluate_odds_calibration(
            combined["correct"].to_numpy(), combined[column].to_numpy()
        )
        for name, column in methods.items()
    }
    raw = combined_metrics["raw_model_confidence"]
    for name in ("isotonic", "platt_correctness"):
        metrics = combined_metrics[name]
        metrics["improves_all_proper_metrics"] = bool(
            metrics["brier_score"] <= raw["brier_score"]
            and metrics["log_loss"] <= raw["log_loss"]
            and metrics["expected_calibration_error"]
            <= raw["expected_calibration_error"]
        )
    development = combined["fold"].astype(str).isin(
        set(DEFAULT_DEVELOPMENT_FOLDS)
    )
    period_masks = {
        "nested_development": development,
        "confirmation": ~development,
        "all_nested": pd.Series(True, index=combined.index),
    }
    report = {
        "format_version": 1,
        "validation": "nested chronological: all prior OOS folds fit, next OOS fold evaluates",
        "first_fold_policy": "excluded because no prior OOS calibration fold exists",
        "rows": len(combined),
        "combined": combined_metrics,
        "fixed_thresholds": list(thresholds),
        "periods": {
            period: _method_report(
                combined.loc[mask].reset_index(drop=True), methods, thresholds
            )
            for period, mask in period_masks.items()
            if mask.any()
        },
        "folds": fold_reports,
    }
    return combined, report


def _adaptive_confidence_band(value: float, edges: np.ndarray) -> int:
    return min(int(np.searchsorted(edges[1:], value, side="right")), len(edges) - 2)


def prequential_hierarchical_beta_recalibration(
    predictions: pd.DataFrame,
    *,
    window_days: int = 90,
    global_prior_strength: float = 8192.0,
    band_prior_strength: float = 4096.0,
    cell_prior_strength: float = 2048.0,
    band_edges: Sequence[float] = DEFAULT_ADAPTIVE_BAND_EDGES,
    thresholds: Sequence[float] = DEFAULT_ADAPTIVE_THRESHOLDS,
) -> tuple[pd.DataFrame, dict[str, object]]:
    """Adapt correctness odds using only outcomes resolved before each decision.

    The rolling hierarchy is global -> fixed raw-confidence band -> predicted
    direction x volatility regime.  Each child posterior is shrunk to its
    parent, so sparse local cells cannot create extreme odds.
    """
    missing = ADAPTIVE_REQUIRED_COLUMNS.difference(predictions.columns)
    if missing:
        raise ValueError(f"predictions are missing columns: {sorted(missing)}")
    if window_days <= 0:
        raise ValueError("window_days must be positive")
    strengths = (global_prior_strength, band_prior_strength, cell_prior_strength)
    if any(not np.isfinite(value) or value <= 0 for value in strengths):
        raise ValueError("adaptive prior strengths must be finite and positive")
    resolved_edges = np.asarray(tuple(band_edges), dtype="float64")
    if (
        len(resolved_edges) < 2
        or not np.isfinite(resolved_edges).all()
        or np.any(np.diff(resolved_edges) <= 0)
        or resolved_edges[0] > 0.5
        or resolved_edges[-1] < 1.0
    ):
        raise ValueError("band_edges must be increasing and cover [0.5, 1.0]")
    if not thresholds or any(not 0.5 <= threshold < 1 for threshold in thresholds):
        raise ValueError("odds thresholds must be between 0.5 inclusive and 1")

    frame = predictions.copy()
    if frame.duplicated(["fold", "timestamp"]).any():
        raise ValueError("predictions contain duplicate fold/timestamp rows")
    for column in ("timestamp", "decision_timestamp", "target_timestamp"):
        frame[column] = pd.to_datetime(frame[column], utc=True)
    frame = frame.sort_values(
        ["decision_timestamp", "fold", "timestamp"]
    ).reset_index(drop=True)
    confidence = frame["confidence"].to_numpy(dtype="float64")
    if (
        not np.isfinite(confidence).all()
        or ((confidence < 0.5) | (confidence > 1)).any()
    ):
        raise ValueError("confidence must be finite and between 0.5 and one")
    correct = frame["correct"].astype("int8").to_numpy()
    decisions = frame["decision_timestamp"].astype("int64").to_numpy()
    targets = frame["target_timestamp"].astype("int64").to_numpy()
    if np.any(targets <= decisions):
        raise ValueError("target_timestamp must be after decision_timestamp")
    if np.any(np.diff(decisions) < 0) or np.any(np.diff(targets) < 0):
        raise ValueError("decision and target timestamps must be chronological")

    directions = frame["predicted_direction"].astype(str).to_numpy()
    regimes = frame["volatility_regime"].astype(str).to_numpy()
    bands = np.asarray(
        [_adaptive_confidence_band(value, resolved_edges) for value in confidence],
        dtype="int8",
    )
    global_queue: deque[int] = deque()
    band_queues: dict[int, deque[int]] = defaultdict(deque)
    cell_queues: dict[tuple[int, str, str], deque[int]] = defaultdict(deque)
    global_successes = 0
    band_successes: dict[int, int] = defaultdict(int)
    cell_successes: dict[tuple[int, str, str], int] = defaultdict(int)
    observed_position = 0
    window_ns = int(pd.Timedelta(days=window_days).value)

    adaptive = np.empty(len(frame), dtype="float64")
    adaptive_lower = np.empty(len(frame), dtype="float64")
    global_support = np.empty(len(frame), dtype="int32")
    band_support = np.empty(len(frame), dtype="int32")
    cell_support = np.empty(len(frame), dtype="int32")

    def purge(queue: deque[int], successes: int, cutoff: int) -> int:
        while queue and targets[queue[0]] < cutoff:
            successes -= int(correct[queue.popleft()])
        return successes

    for row in range(len(frame)):
        decision = decisions[row]
        while observed_position < len(frame) and targets[observed_position] <= decision:
            observed_band = int(bands[observed_position])
            observed_cell = (
                observed_band,
                directions[observed_position],
                regimes[observed_position],
            )
            global_queue.append(observed_position)
            band_queues[observed_band].append(observed_position)
            cell_queues[observed_cell].append(observed_position)
            outcome = int(correct[observed_position])
            global_successes += outcome
            band_successes[observed_band] += outcome
            cell_successes[observed_cell] += outcome
            observed_position += 1

        cutoff = decision - window_ns
        global_successes = purge(global_queue, global_successes, cutoff)
        band = int(bands[row])
        cell = (band, directions[row], regimes[row])
        band_successes[band] = purge(
            band_queues[band], band_successes[band], cutoff
        )
        cell_successes[cell] = purge(
            cell_queues[cell], cell_successes[cell], cutoff
        )

        raw = confidence[row]
        n_global = len(global_queue)
        n_band = len(band_queues[band])
        n_cell = len(cell_queues[cell])
        global_mean = (
            global_successes + global_prior_strength * raw
        ) / (n_global + global_prior_strength)
        band_mean = (
            band_successes[band] + band_prior_strength * global_mean
        ) / (n_band + band_prior_strength)
        cell_mean = (
            cell_successes[cell] + cell_prior_strength * band_mean
        ) / (n_cell + cell_prior_strength)
        adaptive[row] = np.clip(cell_mean, 0.0, 1.0)
        posterior_strength = n_cell + cell_prior_strength
        standard_error = np.sqrt(
            adaptive[row] * (1.0 - adaptive[row]) / (posterior_strength + 1.0)
        )
        adaptive_lower[row] = np.clip(adaptive[row] - 1.96 * standard_error, 0.0, 1.0)
        global_support[row] = n_global
        band_support[row] = n_band
        cell_support[row] = n_cell

    frame["raw_model_confidence"] = confidence
    frame["adaptive_confidence"] = adaptive
    frame["adaptive_confidence_lower"] = adaptive_lower
    frame["adaptive_global_support"] = global_support
    frame["adaptive_band_support"] = band_support
    frame["adaptive_cell_support"] = cell_support
    frame["adaptive_confidence_band"] = bands

    methods = {
        "raw_model_confidence": "raw_model_confidence",
        "adaptive_hierarchical_beta": "adaptive_confidence",
    }
    development = frame["fold"].astype(str).isin(set(DEFAULT_DEVELOPMENT_FOLDS))
    period_masks = {
        "development": development,
        "confirmation": ~development,
        "all": pd.Series(True, index=frame.index),
    }
    report = {
        "format_version": 1,
        "validation": "prequential rolling: only target outcomes resolved at or before each decision are visible",
        "fixed_specification": {
            "window_days": window_days,
            "global_prior_strength": global_prior_strength,
            "band_prior_strength": band_prior_strength,
            "cell_prior_strength": cell_prior_strength,
            "band_edges": resolved_edges.tolist(),
            "hierarchy": "global -> raw confidence band -> predicted direction x volatility regime",
            "lower_bound": "posterior normal approximation, 1.96 standard errors",
        },
        "fixed_thresholds": list(thresholds),
        "periods": {
            period: _method_report(frame.loc[mask], methods, thresholds)
            for period, mask in period_masks.items()
            if mask.any()
        },
        "adaptive_lower_bound_lanes": {
            period: {
                str(threshold): _correctness_lane_metrics(
                    frame.loc[mask], "adaptive_confidence_lower", threshold
                )
                for threshold in DEFAULT_ADAPTIVE_LOWER_THRESHOLDS
            }
            for period, mask in period_masks.items()
            if mask.any()
        },
        "folds": {
            str(fold): _method_report(group, methods, thresholds)
            for fold, group in frame.groupby("fold", sort=False)
        },
    }
    return frame, report


def run_prequential_hierarchical_beta_recalibration(
    prediction_dirs: Sequence[Path],
    timeframe: int,
    output_dir: Path,
    bootstrap_iterations: int = 0,
    random_seed: int = 42,
) -> dict[str, object]:
    predictions = read_prediction_sets(prediction_dirs, timeframe)
    calibrated, report = prequential_hierarchical_beta_recalibration(predictions)
    if bootstrap_iterations:
        if bootstrap_iterations < 100:
            raise ValueError("bootstrap iterations must be zero or at least 100")
        report["paired_utc_day_bootstrap"] = paired_daily_block_bootstrap(
            _correctness_probability_frame(calibrated, "adaptive_confidence"),
            _correctness_probability_frame(calibrated, "raw_model_confidence"),
            0.515,
            bootstrap_iterations,
            random_seed,
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    predictions_name = f"m{timeframe}_walk_forward_predictions.parquet"
    calibrated["confidence"] = calibrated["adaptive_confidence"]
    calibrated.to_parquet(output_dir / predictions_name, index=False)
    report["timeframe"] = timeframe
    report["prediction_dirs"] = [str(path) for path in prediction_dirs]
    (output_dir / "adaptive_beta_metrics.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (output_dir / "manifest.json").write_text(
        json.dumps(
            {
                "format_version": 1,
                "kind": "next_bar_prequential_hierarchical_beta_recalibration",
                "timeframes": {f"M{timeframe}": {"predictions": predictions_name}},
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return report


def run_chronological_correctness_recalibration(
    prediction_dirs: Sequence[Path],
    timeframe: int,
    output_dir: Path,
    bootstrap_iterations: int = 0,
    random_seed: int = 42,
) -> dict[str, object]:
    predictions = read_prediction_sets(prediction_dirs, timeframe)
    combined, report = chronological_correctness_recalibration(predictions)
    if bootstrap_iterations:
        if bootstrap_iterations < 100:
            raise ValueError("bootstrap iterations must be zero or at least 100")
        raw = _correctness_probability_frame(combined, "confidence")
        report["paired_utc_day_bootstrap"] = {
            name: paired_daily_block_bootstrap(
                _correctness_probability_frame(combined, column),
                raw,
                0.515,
                bootstrap_iterations,
                random_seed,
            )
            for name, column in {
                "isotonic_minus_raw": "isotonic_confidence",
                "platt_correctness_minus_raw": "platt_correctness_confidence",
            }.items()
        }
    output_dir.mkdir(parents=True, exist_ok=True)
    predictions_name = f"m{timeframe}_correctness_recalibration.parquet"
    combined.to_parquet(output_dir / predictions_name, index=False)
    report["timeframe"] = timeframe
    report["prediction_dirs"] = [str(path) for path in prediction_dirs]
    (output_dir / "recalibration_metrics.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (output_dir / "manifest.json").write_text(
        json.dumps(
            {
                "format_version": 1,
                "kind": "next_bar_chronological_correctness_recalibration",
                "timeframes": {f"M{timeframe}": {"predictions": predictions_name}},
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return report
