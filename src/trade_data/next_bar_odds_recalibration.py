from __future__ import annotations

import json
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
