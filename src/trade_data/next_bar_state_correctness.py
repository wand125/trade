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
from sklearn.ensemble import HistGradientBoostingClassifier

from trade_data.next_bar import (
    PlattCalibrator,
    build_feature_frame,
    evaluate_probabilities,
    fit_platt_calibrator,
    predict_latest,
    resample_complete_bars,
    validate_stationary_feature_set,
)
from trade_data.next_bar_registry import lane_metrics, read_prediction_sets


DEFAULT_THRESHOLD_GRID = (
    0.50,
    0.505,
    0.51,
    0.515,
    0.52,
    0.525,
    0.53,
    0.54,
    0.55,
    0.575,
    0.60,
)
REFERENCE_STATE_FEATURES = (
    "reference_confidence_feature",
    "reference_aligned_edge_feature",
    "reference_predicted_up_feature",
)
DEFAULT_HIGH_CONFIDENCE_THRESHOLD = 0.55
DEFAULT_HIGH_CONFIDENCE_DIRECTIONS = ("up",)
DEFAULT_HIGH_CONFIDENCE_VOLATILITY_REGIMES = ("normal", "high")
RUNTIME_MINIMUM_M1_BARS = 4_096


@dataclass(frozen=True)
class StateCorrectnessConfig:
    timeframe: int = 1
    feature_set: str = "distribution_shift"
    calibration_fraction: float = 0.20
    max_train_rows: int = 750_000
    max_iter: int = 100
    learning_rate: float = 0.05
    max_leaf_nodes: int = 15
    min_samples_leaf: int = 50
    l2_regularization: float = 2.0
    random_seed: int = 42


def build_state_correctness_frame(
    reference_predictions: pd.DataFrame,
    m1_bars: pd.DataFrame,
    config: StateCorrectnessConfig,
) -> tuple[pd.DataFrame, tuple[str, ...]]:
    required = {
        "fold",
        "timestamp",
        "decision_timestamp",
        "target_timestamp",
        "target_up",
        "probability_up",
        "predicted_up",
        "correct",
    }
    missing = sorted(required - set(reference_predictions.columns))
    if missing:
        raise ValueError(f"reference predictions are missing: {', '.join(missing)}")
    if reference_predictions.duplicated(["fold", "timestamp"]).any():
        raise ValueError("reference predictions contain duplicate fold/timestamp rows")
    if reference_predictions["timestamp"].duplicated().any():
        raise ValueError("reference timestamps must be unique across folds")

    bars = resample_complete_bars(m1_bars, config.timeframe)
    state, state_features = build_feature_frame(
        bars, config.timeframe, config.feature_set
    )
    validate_stationary_feature_set(state_features)
    state = state[["timestamp", *state_features]].copy()

    frame = reference_predictions.copy()
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
    frame["decision_timestamp"] = pd.to_datetime(
        frame["decision_timestamp"], utc=True
    )
    frame["target_timestamp"] = pd.to_datetime(frame["target_timestamp"], utc=True)
    frame["reference_probability_up"] = frame["probability_up"].astype("float64")
    frame["reference_confidence"] = np.maximum(
        frame["reference_probability_up"], 1 - frame["reference_probability_up"]
    )
    frame["reference_predicted_up"] = frame["predicted_up"].astype("int8")
    frame["reference_correct"] = frame["correct"].astype(bool)
    overlapping_state_columns = [
        column for column in state_features if column in frame.columns
    ]
    frame = frame.drop(columns=overlapping_state_columns)
    frame = frame.merge(state, on="timestamp", how="left", validate="one_to_one")
    if len(frame) != len(reference_predictions):
        raise ValueError("state features do not align with every reference row")

    frame["reference_confidence_feature"] = frame["reference_confidence"]
    frame["reference_aligned_edge_feature"] = 2 * (
        frame["reference_confidence"] - 0.5
    )
    frame["reference_predicted_up_feature"] = frame[
        "reference_predicted_up"
    ].astype("float64")
    feature_columns = tuple(state_features) + REFERENCE_STATE_FEATURES
    values = frame[list(feature_columns)].to_numpy(dtype="float64")
    if not np.isfinite(values).all():
        raise ValueError("state correctness features must be finite and fully aligned")
    return (
        frame.sort_values(["decision_timestamp", "fold", "timestamp"])
        .reset_index(drop=True),
        feature_columns,
    )


def _new_model(config: StateCorrectnessConfig) -> HistGradientBoostingClassifier:
    if not 0 < config.calibration_fraction < 0.5:
        raise ValueError("calibration_fraction must be between zero and 0.5")
    if config.max_train_rows <= 0:
        raise ValueError("max_train_rows must be positive")
    return HistGradientBoostingClassifier(
        max_iter=config.max_iter,
        learning_rate=config.learning_rate,
        max_leaf_nodes=config.max_leaf_nodes,
        min_samples_leaf=config.min_samples_leaf,
        l2_regularization=config.l2_regularization,
        early_stopping=False,
        random_state=config.random_seed,
    )


def _positive_probability(
    model: HistGradientBoostingClassifier, values: pd.DataFrame
) -> np.ndarray:
    probabilities = model.predict_proba(values)
    matches = np.flatnonzero(model.classes_ == 1)
    if len(matches) != 1:
        raise ValueError("correctness model does not contain the correct class")
    return probabilities[:, int(matches[0])]


def _even_sample(frame: pd.DataFrame, max_rows: int) -> pd.DataFrame:
    if len(frame) <= max_rows:
        return frame
    indices = np.linspace(0, len(frame) - 1, max_rows, dtype="int64")
    return frame.iloc[indices]


def _apply_correctness_probability(
    test: pd.DataFrame,
    raw_probability: np.ndarray,
    calibrated_probability: np.ndarray,
    mode: str,
    evaluation: bool,
) -> pd.DataFrame:
    output = test.copy()
    raw = np.asarray(raw_probability, dtype="float64")
    calibrated = np.asarray(calibrated_probability, dtype="float64")
    if (
        len(raw) != len(output)
        or len(calibrated) != len(output)
        or not np.isfinite(raw).all()
        or not np.isfinite(calibrated).all()
    ):
        raise ValueError("correctness probabilities must be finite and aligned")
    output["state_probability_correct_raw"] = np.clip(raw, 0, 1)
    output["state_probability_correct_calibrated"] = np.clip(calibrated, 0, 1)
    confidence = np.maximum(
        output["state_probability_correct_calibrated"].to_numpy(dtype="float64"),
        np.nextafter(0.5, 1.0),
    )
    predicted_up = output["reference_predicted_up"].to_numpy(dtype="int8")
    output["probability_up"] = np.where(predicted_up == 1, confidence, 1 - confidence)
    output["probability_down"] = 1 - output["probability_up"]
    output["predicted_up"] = predicted_up
    output["predicted_direction"] = np.where(predicted_up == 1, "up", "down")
    output["confidence"] = confidence
    output["class_confidence"] = confidence
    output["correct"] = output["reference_correct"].astype(bool)
    output["state_correctness_mode"] = mode
    output["state_correctness_evaluation"] = evaluation
    return output


def build_latest_state_correctness_prediction(
    m1_bars: pd.DataFrame,
    reference_latest: pd.DataFrame,
    artifact: dict[str, object],
    threshold: float = DEFAULT_HIGH_CONFIDENCE_THRESHOLD,
    allowed_directions: Sequence[str] = DEFAULT_HIGH_CONFIDENCE_DIRECTIONS,
    allowed_volatility_regimes: Sequence[str] = (
        DEFAULT_HIGH_CONFIDENCE_VOLATILITY_REGIMES
    ),
) -> pd.DataFrame:
    """Apply one saved correctness model without changing reference direction."""
    if len(reference_latest) != 1:
        raise ValueError("reference latest prediction must contain exactly one timeframe")
    if not 0.5 < threshold < 1:
        raise ValueError("high-confidence threshold must be between 0.5 and 1")
    required_reference = {
        "timeframe",
        "timeframe_minutes",
        "bar_start",
        "decision_timestamp",
        "probability_up",
        "predicted_direction",
        "volatility_regime",
    }
    missing_reference = sorted(required_reference - set(reference_latest.columns))
    if missing_reference:
        raise ValueError(
            "reference latest prediction is missing: "
            + ", ".join(missing_reference)
        )
    required_artifact = {"model", "calibrator", "config", "feature_columns"}
    missing_artifact = sorted(required_artifact - set(artifact))
    if missing_artifact:
        raise ValueError(
            "state correctness artifact is missing: " + ", ".join(missing_artifact)
        )

    reference = reference_latest.iloc[0]
    config = StateCorrectnessConfig(**dict(artifact["config"]))
    if int(reference["timeframe_minutes"]) != config.timeframe:
        raise ValueError("reference and correctness timeframes do not match")
    runtime_rows = max(RUNTIME_MINIMUM_M1_BARS, config.timeframe * 256)
    runtime_bars = (
        m1_bars.sort_values("timestamp").tail(runtime_rows).reset_index(drop=True)
    )
    bars = resample_complete_bars(runtime_bars, config.timeframe)
    state, state_features = build_feature_frame(
        bars, config.timeframe, config.feature_set
    )
    validate_stationary_feature_set(state_features)
    feature_columns = tuple(str(column) for column in artifact["feature_columns"])
    expected_features = tuple(state_features) + REFERENCE_STATE_FEATURES
    if feature_columns != expected_features:
        raise ValueError("saved correctness feature order does not match runtime features")

    bar_start = pd.Timestamp(reference["bar_start"])
    if bar_start.tzinfo is None:
        bar_start = bar_start.tz_localize("UTC")
    else:
        bar_start = bar_start.tz_convert("UTC")
    matching = state.loc[pd.to_datetime(state["timestamp"], utc=True).eq(bar_start)]
    if len(matching) != 1:
        raise ValueError("reference bar does not align with runtime state features")
    latest = matching.iloc[[-1]].copy()

    reference_probability_up = float(reference["probability_up"])
    if not 0 <= reference_probability_up <= 1:
        raise ValueError("reference probability must be between zero and one")
    reference_direction = str(reference["predicted_direction"])
    expected_direction = "up" if reference_probability_up >= 0.5 else "down"
    if reference_direction != expected_direction:
        raise ValueError("reference probability and direction disagree")
    reference_confidence = max(reference_probability_up, 1 - reference_probability_up)
    latest["reference_confidence_feature"] = reference_confidence
    latest["reference_aligned_edge_feature"] = 2 * (reference_confidence - 0.5)
    latest["reference_predicted_up_feature"] = float(reference_direction == "up")
    values = latest[list(feature_columns)].to_numpy(dtype="float64")
    if not np.isfinite(values).all():
        raise ValueError("latest correctness features must be finite")

    raw = float(_positive_probability(artifact["model"], latest[list(feature_columns)])[0])
    calibrated = float(artifact["calibrator"].predict(np.asarray([raw]))[0])
    confidence = max(float(np.clip(calibrated, 0, 1)), np.nextafter(0.5, 1.0))
    probability_up = confidence if reference_direction == "up" else 1 - confidence
    volatility_regime = str(reference["volatility_regime"])
    direction_allowed = reference_direction in set(allowed_directions)
    volatility_allowed = volatility_regime in set(allowed_volatility_regimes)
    threshold_passed = confidence >= threshold
    eligible = bool(direction_allowed and volatility_allowed and threshold_passed)
    if not threshold_passed:
        eligibility_reason = "state_confidence_below_fixed_threshold"
    elif not direction_allowed:
        eligibility_reason = "reference_direction_outside_fixed_precision_lane"
    elif not volatility_allowed:
        eligibility_reason = "volatility_outside_fixed_precision_lane"
    else:
        eligibility_reason = "fixed_state_correctness_precision_lane_passed"

    return pd.DataFrame(
        [
            {
                "timeframe": reference["timeframe"],
                "timeframe_minutes": config.timeframe,
                "bar_start": bar_start,
                "decision_timestamp": pd.Timestamp(reference["decision_timestamp"]),
                "predicted_direction": reference_direction,
                "probability_up": probability_up,
                "probability_down": 1 - probability_up,
                "confidence": confidence,
                "model_confidence": confidence,
                "class_confidence": confidence,
                "state_probability_correct_raw": raw,
                "state_probability_correct_calibrated": calibrated,
                "reference_probability_up": reference_probability_up,
                "reference_confidence": reference_confidence,
                "volatility_regime": volatility_regime,
                "fixed_confidence_threshold": threshold,
                "allowed_directions": list(allowed_directions),
                "allowed_volatility_regimes": list(allowed_volatility_regimes),
                "prediction_eligible": eligible,
                "strict_prediction_eligible": False,
                "eligibility_reason": eligibility_reason,
                "fair_decimal_odds_shadow": 1 / confidence,
                "odds_valid": False,
                "odds_edge_confirmed": False,
                "deployment_status": "forward_shadow_not_authoritative",
            }
        ]
    )


def predict_latest_state_correctness(
    m1_bars: pd.DataFrame,
    reference_model_dir: Path,
    state_model_dir: Path,
    threshold: float = DEFAULT_HIGH_CONFIDENCE_THRESHOLD,
) -> pd.DataFrame:
    manifest = json.loads(
        (state_model_dir / "manifest.json").read_text(encoding="utf-8")
    )
    entries = list(manifest.get("timeframes", {}).values())
    if len(entries) != 1:
        raise ValueError("state correctness manifest must contain exactly one timeframe")
    entry = entries[0]
    timeframe = int(entry["minutes"])
    model_entries = [model for model in entry.get("models", []) if model.get("model")]
    if not model_entries:
        raise ValueError("state correctness manifest has no saved model")
    artifact = joblib.load(state_model_dir / str(model_entries[-1]["model"]))
    runtime_rows = max(RUNTIME_MINIMUM_M1_BARS, timeframe * 256)
    runtime_bars = (
        m1_bars.sort_values("timestamp").tail(runtime_rows).reset_index(drop=True)
    )
    reference = predict_latest(runtime_bars, reference_model_dir)
    reference = reference.loc[reference["timeframe_minutes"].eq(timeframe)].reset_index(
        drop=True
    )
    return build_latest_state_correctness_prediction(
        runtime_bars,
        reference,
        artifact,
        threshold,
    )


def chronological_state_correctness_predictions(
    frame: pd.DataFrame,
    feature_columns: Sequence[str],
    config: StateCorrectnessConfig,
) -> tuple[pd.DataFrame, list[dict[str, object]], list[dict[str, object]]]:
    fold_order = [
        str(fold)
        for fold in frame.groupby("fold", sort=False)["decision_timestamp"]
        .min()
        .sort_values()
        .index
    ]
    if len(fold_order) < 2:
        raise ValueError("state correctness requires at least two folds")

    predictions: list[pd.DataFrame] = []
    reports: list[dict[str, object]] = []
    models: list[dict[str, object]] = []
    for position, test_fold in enumerate(fold_order):
        test = frame.loc[frame["fold"].astype(str).eq(test_fold)].copy()
        train_folds = fold_order[:position]
        prior = frame.loc[frame["fold"].astype(str).isin(train_folds)].copy()
        if not train_folds:
            raw_probability = test["reference_confidence"].to_numpy(dtype="float64")
            calibrated_probability = raw_probability.copy()
            model = None
            calibrator = None
            fit_rows = 0
            calibration_rows = 0
            mode = "reference_confidence_fallback_no_prior_oos"
            evaluation = False
        else:
            prior = prior.sort_values("decision_timestamp").reset_index(drop=True)
            split = int(np.floor(len(prior) * (1 - config.calibration_fraction)))
            if split <= 0 or split >= len(prior):
                raise ValueError("prior OOS calibration split is empty")
            fit = _even_sample(prior.iloc[:split], config.max_train_rows)
            calibration = prior.iloc[split:]
            if (
                fit["reference_correct"].nunique() < 2
                or calibration["reference_correct"].nunique() < 2
            ):
                raise ValueError("fit and calibration rows need both correctness classes")
            model = _new_model(config)
            model.fit(
                fit[list(feature_columns)], fit["reference_correct"].astype("int8")
            )
            calibration_raw = _positive_probability(
                model, calibration[list(feature_columns)]
            )
            calibrator = fit_platt_calibrator(
                calibration["reference_correct"].to_numpy(dtype="int8"),
                calibration_raw,
            )
            raw_probability = _positive_probability(
                model, test[list(feature_columns)]
            )
            calibrated_probability = calibrator.predict(raw_probability)
            fit_rows = len(fit)
            calibration_rows = len(calibration)
            mode = "prior_oos_state_hgb_platt"
            evaluation = True

        predicted = _apply_correctness_probability(
            test,
            raw_probability,
            calibrated_probability,
            mode,
            evaluation,
        )
        reports.append(
            {
                "test_fold": test_fold,
                "train_folds": train_folds,
                "prior_rows": len(prior),
                "fit_rows": fit_rows,
                "calibration_rows": calibration_rows,
                "test_rows": len(test),
                "mode": mode,
                "evaluation": evaluation,
                "raw_correctness_probability": evaluate_probabilities(
                    predicted["reference_correct"].to_numpy(dtype="int8"),
                    predicted["state_probability_correct_raw"].to_numpy(
                        dtype="float64"
                    ),
                ),
                "calibrated_correctness_probability": evaluate_probabilities(
                    predicted["reference_correct"].to_numpy(dtype="int8"),
                    predicted["state_probability_correct_calibrated"].to_numpy(
                        dtype="float64"
                    ),
                ),
            }
        )
        predictions.append(predicted)
        models.append(
            {
                "test_fold": test_fold,
                "train_folds": train_folds,
                "mode": mode,
                "model": model,
                "calibrator": calibrator,
            }
        )
    return pd.concat(predictions, ignore_index=True), reports, models


def analyze_state_correctness(
    predictions: pd.DataFrame,
    threshold_grid: Sequence[float] = DEFAULT_THRESHOLD_GRID,
) -> dict[str, object]:
    evaluation = predictions["state_correctness_evaluation"].astype(bool)
    development = evaluation & predictions["fold"].astype(str).isin(
        {"test2021", "test2022", "test2023"}
    )
    confirmation = evaluation & predictions["fold"].astype(str).isin(
        {"test2024", "test2025", "test2026_partial"}
    )
    if not development.any() or not confirmation.any():
        raise ValueError("nested development and confirmation folds are required")
    development_grid = {
        str(threshold): lane_metrics(predictions.loc[development], threshold)
        for threshold in threshold_grid
    }
    valid = [
        threshold
        for threshold in threshold_grid
        if development_grid[str(threshold)]["selection_score"] is not None
    ]
    selected_threshold = max(
        valid,
        key=lambda threshold: (
            float(development_grid[str(threshold)]["selection_score"]),
            -threshold,
        ),
    )
    periods: dict[str, object] = {}
    for period, mask in {
        "nested_development": development,
        "confirmation": confirmation,
        "all_nested": evaluation,
    }.items():
        candidate = predictions.loc[mask]
        reference = candidate.copy()
        reference["probability_up"] = reference["reference_probability_up"]
        reference["confidence"] = reference["reference_confidence"]
        periods[period] = {
            "rows": len(candidate),
            "candidate_probability": evaluate_probabilities(
                candidate["target_up"].to_numpy(dtype="int8"),
                candidate["probability_up"].to_numpy(dtype="float64"),
            ),
            "candidate_lane": lane_metrics(candidate, selected_threshold),
            "reference_probability": evaluate_probabilities(
                reference["target_up"].to_numpy(dtype="int8"),
                reference["probability_up"].to_numpy(dtype="float64"),
            ),
            "reference_lane_same_threshold": lane_metrics(
                reference, selected_threshold
            ),
        }
    return {
        "first_fold_policy": "reference confidence fallback; excluded from nested evaluation",
        "nested_development_folds": ["test2021", "test2022", "test2023"],
        "confirmation_folds": ["test2024", "test2025", "test2026_partial"],
        "threshold_grid": list(threshold_grid),
        "development_grid": development_grid,
        "selected_threshold": selected_threshold,
        "periods": periods,
    }


def run_state_correctness(
    input_path: Path,
    reference_dir: Path,
    output_dir: Path,
    config: StateCorrectnessConfig,
) -> dict[str, object]:
    reference = read_prediction_sets([reference_dir], config.timeframe)
    m1_bars = pd.read_parquet(input_path)
    frame, feature_columns = build_state_correctness_frame(reference, m1_bars, config)
    predictions, fold_reports, models = chronological_state_correctness_predictions(
        frame, feature_columns, config
    )
    analysis = analyze_state_correctness(predictions)
    output_dir.mkdir(parents=True, exist_ok=True)
    model_entries: list[dict[str, object]] = []
    for entry in models:
        model_name = None
        if entry["model"] is not None:
            model_name = f"m{config.timeframe}_{entry['test_fold']}_state_correctness.joblib"
            joblib.dump(
                {
                    "model": entry["model"],
                    "calibrator": entry["calibrator"],
                    "config": asdict(config),
                    "feature_columns": list(feature_columns),
                    "train_folds": entry["train_folds"],
                    "test_fold": entry["test_fold"],
                    "deployment_status": "research_only",
                },
                output_dir / model_name,
            )
        model_entries.append(
            {
                "test_fold": entry["test_fold"],
                "train_folds": entry["train_folds"],
                "mode": entry["mode"],
                "model": model_name,
            }
        )

    created_at = datetime.now(UTC).isoformat()
    prediction_name = f"m{config.timeframe}_walk_forward_predictions.parquet"
    predictions.to_parquet(output_dir / prediction_name, index=False)
    report = {
        "created_at": created_at,
        "config": asdict(config),
        "input_path": str(input_path),
        "reference_dir": str(reference_dir),
        "feature_columns": list(feature_columns),
        "rows": len(predictions),
        "folds": fold_reports,
        "analysis": analysis,
    }
    manifest = {
        "format_version": 1,
        "created_at": created_at,
        "kind": "next_bar_chronological_state_correctness",
        "sources": {"input": str(input_path), "reference": str(reference_dir)},
        "timeframes": {
            f"M{config.timeframe}": {
                "minutes": config.timeframe,
                "feature_set": config.feature_set,
                "features": list(feature_columns),
                "models": model_entries,
                "predictions": prediction_name,
                "selected_threshold": analysis["selected_threshold"],
            }
        },
    }
    (output_dir / "state_correctness_metrics.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Learn baseline-direction correctness from prior OOS market state."
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--reference-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--timeframe", type=int, default=1)
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    report = run_state_correctness(
        args.input,
        args.reference_dir,
        args.output_dir,
        StateCorrectnessConfig(timeframe=args.timeframe),
    )
    print(
        json.dumps(
            {
                "rows": report["rows"],
                "selected_threshold": report["analysis"]["selected_threshold"],
                "periods": report["analysis"]["periods"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
