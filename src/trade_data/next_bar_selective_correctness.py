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
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from trade_data.next_bar import context_diagnostics, evaluate_probabilities
from trade_data.next_bar_registry import lane_metrics, read_prediction_sets


@dataclass(frozen=True)
class SelectiveCorrectnessConfig:
    timeframe: int = 15
    regularization_c: float = 0.10
    random_seed: int = 42


SELECTIVE_CORRECTNESS_FEATURES = (
    "baseline_aligned_edge",
    "reference_candidate_aligned_edge",
    "shape_candidate_aligned_edge",
    "profile_candidate_aligned_edge",
    "reference_blend_edge",
    "shape_blend_aligned_edge",
    "profile_blend_aligned_edge",
    "candidate_aligned_edge_mean",
    "candidate_aligned_edge_min",
    "candidate_aligned_edge_max",
    "candidate_aligned_edge_std",
    "candidate_direction_agreement_fraction",
    "reference_candidate_peer_delta",
    "shape_profile_candidate_gap",
    "body_ratio_feature",
    "volatility_20_feature",
    "reference_predicted_up_feature",
    "minute_sin",
    "minute_cos",
    "weekday_sin",
    "weekday_cos",
    "regime_low",
    "regime_normal",
    "regime_high",
)


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


def _aligned_edge(probability: pd.Series, direction_sign: np.ndarray) -> np.ndarray:
    values = probability.to_numpy(dtype="float64")
    if not np.isfinite(values).all() or np.any((values < 0) | (values > 1)):
        raise ValueError("source probabilities must be finite and between zero and one")
    return 2 * direction_sign * (values - 0.5)


def build_selective_correctness_frame(
    reference_predictions: pd.DataFrame,
    shape_predictions: pd.DataFrame,
    profile_predictions: pd.DataFrame,
) -> pd.DataFrame:
    keys = ["fold", "timestamp"]
    alignment_columns = (
        "decision_timestamp",
        "target_timestamp",
        "target_up",
        "volatility_regime",
        "volatility_20",
        "body_ratio",
    )
    common_required = {
        *keys,
        *alignment_columns,
        "probability_up",
        "candidate_probability_up",
        "predicted_up",
        "correct",
    }
    reference_required = {*common_required, "baseline_probability_up"}
    for name, predictions, required in (
        ("reference", reference_predictions, reference_required),
        ("shape", shape_predictions, common_required),
        ("profile", profile_predictions, common_required),
    ):
        missing = sorted(required - set(predictions.columns))
        if missing:
            raise ValueError(f"{name} predictions are missing: {', '.join(missing)}")
        if predictions.duplicated(keys).any():
            raise ValueError(f"{name} predictions contain duplicate fold/timestamp rows")

    reference_columns = [
        *keys,
        *alignment_columns,
        "probability_up",
        "candidate_probability_up",
        "baseline_probability_up",
        "predicted_up",
        "correct",
    ]
    frame = reference_predictions[reference_columns].copy().rename(
        columns={
            "probability_up": "reference_probability_up",
            "candidate_probability_up": "reference_candidate_probability_up",
            "predicted_up": "reference_predicted_up",
            "correct": "reference_correct",
        }
    )
    for name, predictions in (
        ("shape", shape_predictions),
        ("profile", profile_predictions),
    ):
        columns = [
            *keys,
            *alignment_columns,
            "probability_up",
            "candidate_probability_up",
            "predicted_up",
            "correct",
        ]
        renamed = {
            column: f"{name}_{column}" for column in alignment_columns
        }
        source = predictions[columns].copy().rename(
            columns={
                **renamed,
                "probability_up": f"{name}_probability_up",
                "candidate_probability_up": f"{name}_candidate_probability_up",
                "predicted_up": f"{name}_predicted_up",
                "correct": f"{name}_correct",
            }
        )
        frame = frame.merge(source, on=keys, how="inner", validate="one_to_one")

    expected_rows = len(reference_predictions)
    if len(frame) != expected_rows or any(
        len(source) != expected_rows
        for source in (shape_predictions, profile_predictions)
    ):
        raise ValueError("selective correctness sources do not contain identical rows")

    for name in ("shape", "profile"):
        for column in alignment_columns:
            other = f"{name}_{column}"
            if pd.api.types.is_numeric_dtype(frame[column]):
                aligned = np.allclose(
                    frame[column].to_numpy(dtype="float64"),
                    frame[other].to_numpy(dtype="float64"),
                    equal_nan=True,
                )
            else:
                aligned = frame[column].astype(str).equals(
                    frame[other].astype(str)
                )
            if not aligned:
                raise ValueError(f"{name} source mismatch: {column}")
            frame = frame.drop(columns=other)
        if not frame["reference_predicted_up"].astype("int8").equals(
            frame[f"{name}_predicted_up"].astype("int8")
        ):
            raise ValueError(
                f"{name} source must preserve the reference prediction direction"
            )
        if not frame["reference_correct"].astype(bool).equals(
            frame[f"{name}_correct"].astype(bool)
        ):
            raise ValueError(f"{name} correctness does not align with reference")

    direction_sign = np.where(frame["reference_predicted_up"].eq(1), 1.0, -1.0)
    frame["baseline_aligned_edge"] = _aligned_edge(
        frame["baseline_probability_up"], direction_sign
    )
    frame["reference_candidate_aligned_edge"] = _aligned_edge(
        frame["reference_candidate_probability_up"], direction_sign
    )
    frame["shape_candidate_aligned_edge"] = _aligned_edge(
        frame["shape_candidate_probability_up"], direction_sign
    )
    frame["profile_candidate_aligned_edge"] = _aligned_edge(
        frame["profile_candidate_probability_up"], direction_sign
    )
    frame["reference_blend_edge"] = _aligned_edge(
        frame["reference_probability_up"], direction_sign
    )
    frame["shape_blend_aligned_edge"] = _aligned_edge(
        frame["shape_probability_up"], direction_sign
    )
    frame["profile_blend_aligned_edge"] = _aligned_edge(
        frame["profile_probability_up"], direction_sign
    )
    candidate_edges = frame[
        [
            "reference_candidate_aligned_edge",
            "shape_candidate_aligned_edge",
            "profile_candidate_aligned_edge",
        ]
    ].to_numpy(dtype="float64")
    frame["candidate_aligned_edge_mean"] = candidate_edges.mean(axis=1)
    frame["candidate_aligned_edge_min"] = candidate_edges.min(axis=1)
    frame["candidate_aligned_edge_max"] = candidate_edges.max(axis=1)
    frame["candidate_aligned_edge_std"] = candidate_edges.std(axis=1)
    frame["candidate_direction_agreement_fraction"] = (
        candidate_edges >= 0
    ).mean(axis=1)
    frame["reference_candidate_peer_delta"] = candidate_edges[:, 0] - candidate_edges[
        :, 1:
    ].mean(axis=1)
    frame["shape_profile_candidate_gap"] = np.abs(
        candidate_edges[:, 1] - candidate_edges[:, 2]
    )
    frame["body_ratio_feature"] = frame["body_ratio"].astype("float64")
    frame["volatility_20_feature"] = frame["volatility_20"].astype("float64")
    frame["reference_predicted_up_feature"] = frame[
        "reference_predicted_up"
    ].astype("float64")
    decision = pd.to_datetime(frame["decision_timestamp"], utc=True)
    minute = decision.dt.hour.to_numpy(dtype="float64") * 60 + decision.dt.minute
    weekday = decision.dt.dayofweek.to_numpy(dtype="float64")
    frame["minute_sin"] = np.sin(2 * np.pi * minute / (24 * 60))
    frame["minute_cos"] = np.cos(2 * np.pi * minute / (24 * 60))
    frame["weekday_sin"] = np.sin(2 * np.pi * weekday / 7)
    frame["weekday_cos"] = np.cos(2 * np.pi * weekday / 7)
    regime = frame["volatility_regime"].astype(str)
    for name in ("low", "normal", "high"):
        frame[f"regime_{name}"] = regime.eq(name).astype("float64")

    features = frame[list(SELECTIVE_CORRECTNESS_FEATURES)].to_numpy(dtype="float64")
    if not np.isfinite(features).all():
        raise ValueError("selective correctness features must be finite")
    return frame.sort_values(["decision_timestamp", "fold", "timestamp"]).reset_index(
        drop=True
    )


def _new_model(config: SelectiveCorrectnessConfig) -> Pipeline:
    if config.regularization_c <= 0:
        raise ValueError("regularization_c must be positive")
    return Pipeline(
        [
            ("scale", StandardScaler()),
            (
                "logistic",
                LogisticRegression(
                    C=config.regularization_c,
                    max_iter=1_000,
                    random_state=config.random_seed,
                ),
            ),
        ]
    )


def _apply_selection_probability(
    test: pd.DataFrame,
    raw_probability_correct: np.ndarray,
    mode: str,
    evaluation: bool,
) -> pd.DataFrame:
    output = test.copy()
    raw = np.asarray(raw_probability_correct, dtype="float64")
    if len(raw) != len(output) or not np.isfinite(raw).all():
        raise ValueError("correctness probabilities must be finite and aligned")
    raw = np.clip(raw, 0.0, 1.0)
    confidence = np.maximum(raw, 0.5 + np.finfo("float64").eps)
    output["selection_probability_correct_raw"] = raw
    output["selection_confidence"] = confidence
    output["probability_up"] = np.where(
        output["reference_predicted_up"].eq(1), confidence, 1 - confidence
    )
    output["probability_down"] = 1 - output["probability_up"]
    output["predicted_up"] = output["reference_predicted_up"].astype("int8")
    output["predicted_direction"] = np.where(
        output["predicted_up"].eq(1), "up", "down"
    )
    output["confidence"] = confidence
    output["class_confidence"] = confidence
    output["correct"] = output["reference_correct"].astype(bool)
    output["selective_correctness_mode"] = mode
    output["selective_correctness_evaluation"] = evaluation
    return output


def chronological_selective_correctness_predictions(
    frame: pd.DataFrame,
    config: SelectiveCorrectnessConfig,
) -> tuple[pd.DataFrame, list[dict[str, object]], list[dict[str, object]]]:
    fold_order = [
        str(fold)
        for fold in frame.groupby("fold", sort=False)["decision_timestamp"]
        .min()
        .sort_values()
        .index
    ]
    if len(fold_order) < 2:
        raise ValueError("selective correctness requires at least two folds")

    predictions: list[pd.DataFrame] = []
    reports: list[dict[str, object]] = []
    models: list[dict[str, object]] = []
    for position, test_fold in enumerate(fold_order):
        test = frame.loc[frame["fold"].astype(str).eq(test_fold)].copy()
        train_folds = fold_order[:position]
        train = frame.loc[frame["fold"].astype(str).isin(train_folds)]
        if not train_folds:
            raw_probability = np.maximum(
                test["reference_probability_up"].to_numpy(dtype="float64"),
                1 - test["reference_probability_up"].to_numpy(dtype="float64"),
            )
            model = None
            mode = "reference_confidence_fallback_no_prior_oos"
            evaluation = False
            coefficients = None
            intercept = None
        elif train["reference_correct"].nunique() < 2:
            raw_probability = np.full(
                len(test), float(train["reference_correct"].mean()), dtype="float64"
            )
            model = None
            mode = "prior_oos_constant"
            evaluation = True
            coefficients = None
            intercept = None
        else:
            model = _new_model(config)
            model.fit(
                train[list(SELECTIVE_CORRECTNESS_FEATURES)],
                train["reference_correct"].astype("int8"),
            )
            raw_probability = model.predict_proba(
                test[list(SELECTIVE_CORRECTNESS_FEATURES)]
            )[:, 1]
            logistic = model.named_steps["logistic"]
            coefficients = {
                feature: float(value)
                for feature, value in zip(
                    SELECTIVE_CORRECTNESS_FEATURES,
                    logistic.coef_[0],
                    strict=True,
                )
            }
            intercept = float(logistic.intercept_[0])
            mode = "prior_oos_logistic"
            evaluation = True

        predicted = _apply_selection_probability(
            test, raw_probability, mode, evaluation
        )
        correctness_metrics = evaluate_probabilities(
            predicted["reference_correct"].to_numpy(dtype="int8"),
            predicted["selection_probability_correct_raw"].to_numpy(
                dtype="float64"
            ),
        )
        reports.append(
            {
                "test_fold": test_fold,
                "train_folds": train_folds,
                "train_rows": len(train),
                "test_rows": len(test),
                "mode": mode,
                "evaluation": evaluation,
                "correctness_probability": correctness_metrics,
                "raw_probability_correct_mean": float(
                    predicted["selection_probability_correct_raw"].mean()
                ),
                "raw_probability_correct_min": float(
                    predicted["selection_probability_correct_raw"].min()
                ),
                "raw_probability_correct_max": float(
                    predicted["selection_probability_correct_raw"].max()
                ),
                "coefficients_scaled_features": coefficients,
                "intercept": intercept,
            }
        )
        predicted["selective_correctness_train_fold_count"] = len(train_folds)
        predictions.append(predicted)
        models.append(
            {
                "test_fold": test_fold,
                "train_folds": train_folds,
                "mode": mode,
                "model": model,
            }
        )
    return pd.concat(predictions, ignore_index=True), reports, models


def _period_metrics(frame: pd.DataFrame) -> dict[str, float | int]:
    return evaluate_probabilities(
        frame["target_up"].to_numpy(dtype="int8"),
        frame["probability_up"].to_numpy(dtype="float64"),
    )


def _analyze_nested_candidate(
    predictions: pd.DataFrame,
    reference_threshold: float,
    threshold_grid: Sequence[float],
) -> dict[str, object]:
    evaluation = predictions["selective_correctness_evaluation"].astype(bool)
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
    if not valid:
        raise ValueError("no selective threshold produced development rows")
    selected_threshold = max(
        valid,
        key=lambda threshold: (
            float(development_grid[str(threshold)]["selection_score"]),
            -threshold,
        ),
    )
    period_masks = {
        "nested_development": development,
        "confirmation": confirmation,
        "all_nested": evaluation,
    }
    periods: dict[str, object] = {}
    for period, mask in period_masks.items():
        candidate = predictions.loc[mask]
        reference = candidate.copy()
        reference["probability_up"] = reference["reference_probability_up"]
        reference["probability_down"] = 1 - reference["probability_up"]
        reference["confidence"] = np.maximum(
            reference["probability_up"], reference["probability_down"]
        )
        periods[period] = {
            "rows": len(candidate),
            "candidate": {
                "probability": _period_metrics(candidate),
                "lane": lane_metrics(candidate, selected_threshold),
            },
            "reference": {
                "probability": _period_metrics(reference),
                "lane": lane_metrics(reference, reference_threshold),
            },
        }

    fold_comparison: dict[str, object] = {}
    candidate_wins = {"accuracy": 0, "selection_score": 0}
    reference_wins = {"accuracy": 0, "selection_score": 0}
    ties = {"accuracy": 0, "selection_score": 0}
    for fold in predictions.loc[evaluation, "fold"].drop_duplicates():
        mask = predictions["fold"].astype(str).eq(str(fold))
        candidate = predictions.loc[mask]
        reference = candidate.copy()
        reference["confidence"] = np.maximum(
            reference["reference_probability_up"],
            1 - reference["reference_probability_up"],
        )
        candidate_lane = lane_metrics(candidate, selected_threshold)
        reference_lane = lane_metrics(reference, reference_threshold)
        fold_comparison[str(fold)] = {
            "candidate": candidate_lane,
            "reference": reference_lane,
        }
        for metric in ("accuracy", "selection_score"):
            first = candidate_lane[metric]
            second = reference_lane[metric]
            if first is None or second is None or np.isclose(first, second):
                ties[metric] += 1
            elif first > second:
                candidate_wins[metric] += 1
            else:
                reference_wins[metric] += 1
    return {
        "first_fold_policy": (
            "reference confidence fallback; excluded from threshold selection "
            "and nested metrics"
        ),
        "nested_development_folds": ["test2021", "test2022", "test2023"],
        "confirmation_folds": ["test2024", "test2025", "test2026_partial"],
        "reference_threshold": reference_threshold,
        "threshold_grid": list(threshold_grid),
        "development_grid": development_grid,
        "selected_threshold": selected_threshold,
        "periods": periods,
        "fold_wins": {
            "candidate": candidate_wins,
            "reference": reference_wins,
            "ties": ties,
        },
        "fold_comparison": fold_comparison,
    }


def run_selective_correctness(
    reference_dir: Path,
    shape_dir: Path,
    profile_dir: Path,
    output_dir: Path,
    config: SelectiveCorrectnessConfig,
    reference_threshold: float,
    threshold_grid: Sequence[float] = DEFAULT_THRESHOLD_GRID,
) -> dict[str, object]:
    if not 0.5 < reference_threshold < 1:
        raise ValueError("reference threshold must be between 0.5 and 1")
    reference = read_prediction_sets([reference_dir], config.timeframe)
    shape = read_prediction_sets([shape_dir], config.timeframe)
    profile = read_prediction_sets([profile_dir], config.timeframe)
    frame = build_selective_correctness_frame(reference, shape, profile)
    combined, fold_reports, models = chronological_selective_correctness_predictions(
        frame, config
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    model_entries: list[dict[str, object]] = []
    for entry in models:
        model = entry["model"]
        model_name = None
        if model is not None:
            model_name = (
                f"m{config.timeframe}_{entry['test_fold']}_selective_correctness.joblib"
            )
            joblib.dump(
                {
                    "model": model,
                    "config": asdict(config),
                    "feature_columns": list(SELECTIVE_CORRECTNESS_FEATURES),
                    "train_folds": entry["train_folds"],
                    "test_fold": entry["test_fold"],
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

    final_model = _new_model(config)
    final_model.fit(
        frame[list(SELECTIVE_CORRECTNESS_FEATURES)],
        frame["reference_correct"].astype("int8"),
    )
    final_model_name = f"m{config.timeframe}_selective_correctness_research_final.joblib"
    joblib.dump(
        {
            "model": final_model,
            "config": asdict(config),
            "feature_columns": list(SELECTIVE_CORRECTNESS_FEATURES),
            "train_folds": [str(fold) for fold in frame["fold"].drop_duplicates()],
            "deployment_status": "research_only",
        },
        output_dir / final_model_name,
    )

    analysis = _analyze_nested_candidate(
        combined, reference_threshold, threshold_grid
    )
    created_at = datetime.now(UTC).isoformat()
    prediction_name = f"m{config.timeframe}_walk_forward_predictions.parquet"
    combined.to_parquet(output_dir / prediction_name, index=False)
    report = {
        "created_at": created_at,
        "config": asdict(config),
        "reference_dir": str(reference_dir),
        "shape_dir": str(shape_dir),
        "profile_dir": str(profile_dir),
        "feature_columns": list(SELECTIVE_CORRECTNESS_FEATURES),
        "rows": len(combined),
        "folds": fold_reports,
        "analysis": analysis,
        "context_diagnostics": context_diagnostics(combined),
    }
    manifest = {
        "format_version": 1,
        "created_at": created_at,
        "kind": "next_bar_chronological_selective_correctness",
        "sources": {
            "reference": str(reference_dir),
            "shape": str(shape_dir),
            "profile": str(profile_dir),
        },
        "timeframes": {
            f"M{config.timeframe}": {
                "minutes": config.timeframe,
                "features": list(SELECTIVE_CORRECTNESS_FEATURES),
                "models": model_entries,
                "research_final_model": final_model_name,
                "predictions": prediction_name,
                "selected_threshold": analysis["selected_threshold"],
                "reference_threshold": reference_threshold,
            }
        },
    }
    (output_dir / "selective_correctness_metrics.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Estimate fixed-reference correctness from prior OOS model outputs and "
            "emit direction-preserving selective probabilities."
        )
    )
    parser.add_argument("--reference-dir", type=Path, required=True)
    parser.add_argument("--shape-dir", type=Path, required=True)
    parser.add_argument("--profile-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--timeframe", type=int, required=True)
    parser.add_argument("--reference-threshold", type=float, required=True)
    parser.add_argument("--regularization-c", type=float, default=0.10)
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    report = run_selective_correctness(
        reference_dir=args.reference_dir,
        shape_dir=args.shape_dir,
        profile_dir=args.profile_dir,
        output_dir=args.output_dir,
        config=SelectiveCorrectnessConfig(
            timeframe=args.timeframe,
            regularization_c=args.regularization_c,
        ),
        reference_threshold=args.reference_threshold,
    )
    print(
        json.dumps(
            {
                "rows": report["rows"],
                "selected_threshold": report["analysis"]["selected_threshold"],
                "periods": report["analysis"]["periods"],
                "fold_wins": report["analysis"]["fold_wins"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
