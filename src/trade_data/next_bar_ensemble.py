from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np
import pandas as pd

from trade_data.next_bar import (
    calibrate_prediction_odds,
    context_diagnostics,
    evaluate_context_rule,
    evaluate_probabilities,
    parse_timeframes,
    predict_latest,
)
from trade_data.next_bar_overlay import read_prediction_sets


PARITY_CONFIG_KEYS = (
    "flat_tolerance",
    "max_train_rows",
    "random_seed",
    "max_iter",
    "learning_rate",
    "max_leaf_nodes",
    "min_samples_leaf",
    "l2_regularization",
    "confidence_model",
    "probability_calibration",
    "train_weighting",
    "train_target_filter",
    "model_type",
    "train_window_days",
)


def blend_probability_values(
    baseline_probability: np.ndarray | Sequence[float] | float,
    candidate_probability: np.ndarray | Sequence[float] | float,
    candidate_weight: float,
    preserve_baseline_direction: bool = False,
) -> np.ndarray:
    """Use one probability blend implementation for OOS and runtime inference."""
    if not 0 <= candidate_weight <= 1:
        raise ValueError("candidate_weight must be between 0 and 1")
    baseline = np.asarray(baseline_probability, dtype="float64")
    candidate = np.asarray(candidate_probability, dtype="float64")
    if baseline.shape != candidate.shape:
        raise ValueError("baseline and candidate probability shapes do not match")
    if (
        not np.isfinite(baseline).all()
        or not np.isfinite(candidate).all()
        or np.any((baseline < 0) | (baseline > 1))
        or np.any((candidate < 0) | (candidate > 1))
    ):
        raise ValueError("probabilities must be finite and between zero and one")
    blended = (1 - candidate_weight) * baseline + candidate_weight * candidate
    if not preserve_baseline_direction:
        return blended
    baseline_sign = np.where(baseline >= 0.5, 1.0, -1.0)
    aligned_edge = baseline_sign * (blended - 0.5)
    return 0.5 + baseline_sign * np.maximum(
        aligned_edge,
        np.finfo("float64").eps,
    )


def blend_prediction_frames(
    baseline: pd.DataFrame,
    candidate: pd.DataFrame,
    candidate_weight: float,
    preserve_baseline_direction: bool = False,
) -> pd.DataFrame:
    keys = ["fold", "timestamp"]
    required = {
        *keys,
        "decision_timestamp",
        "target_timestamp",
        "target_up",
        "probability_up",
    }
    for name, frame in (("baseline", baseline), ("candidate", candidate)):
        missing = sorted(required - set(frame.columns))
        if missing:
            raise ValueError(f"{name} predictions are missing: {', '.join(missing)}")
        if frame.duplicated(keys).any():
            raise ValueError(f"{name} predictions contain duplicate fold/timestamp rows")
    candidate_probability_column = "__ensemble_candidate_probability_up"
    if candidate_probability_column in baseline.columns:
        raise ValueError(
            f"baseline predictions contain reserved column: {candidate_probability_column}"
        )
    candidate_columns = candidate[
        [*keys, "decision_timestamp", "target_timestamp", "target_up", "probability_up"]
    ].rename(
        columns={
            "decision_timestamp": "candidate_decision_timestamp",
            "target_timestamp": "candidate_target_timestamp",
            "target_up": "candidate_target_up",
            "probability_up": candidate_probability_column,
        }
    )
    output = baseline.merge(candidate_columns, on=keys, how="inner", validate="one_to_one")
    if len(output) != len(baseline) or len(output) != len(candidate):
        raise ValueError("ensemble sources do not contain identical fold/timestamp rows")
    for baseline_column, candidate_column in (
        ("decision_timestamp", "candidate_decision_timestamp"),
        ("target_timestamp", "candidate_target_timestamp"),
        ("target_up", "candidate_target_up"),
    ):
        left = output[baseline_column].astype(str)
        right = output[candidate_column].astype(str)
        if not left.equals(right):
            raise ValueError(f"ensemble source mismatch: {baseline_column}")
    output["baseline_probability_up"] = output["probability_up"].astype("float64")
    output["candidate_probability_up"] = output[
        candidate_probability_column
    ].astype("float64")
    output["probability_up"] = blend_probability_values(
        output["baseline_probability_up"].to_numpy(dtype="float64"),
        output["candidate_probability_up"].to_numpy(dtype="float64"),
        candidate_weight,
        preserve_baseline_direction,
    )
    output["probability_down"] = 1 - output["probability_up"]
    output["predicted_up"] = output["probability_up"].ge(0.5).astype("int8")
    output["predicted_direction"] = np.where(
        output["predicted_up"].eq(1), "up", "down"
    )
    output["confidence"] = np.maximum(
        output["probability_up"], output["probability_down"]
    )
    output["class_confidence"] = output["confidence"]
    output["correct"] = output["predicted_up"].eq(output["target_up"].astype("int8"))
    output["ensemble_candidate_weight"] = candidate_weight
    output["ensemble_preserve_baseline_direction"] = preserve_baseline_direction
    return output.drop(
        columns=[
            "candidate_decision_timestamp",
            "candidate_target_timestamp",
            "candidate_target_up",
            candidate_probability_column,
        ]
    ).sort_values("decision_timestamp").reset_index(drop=True)


def assert_latest_artifact_parity(
    baseline_model_dir: Path,
    candidate_model_dir: Path,
    allow_model_type_mismatch: bool = False,
) -> dict[str, object]:
    """Require matching time boundaries and training settings before runtime blend."""
    reports = []
    for directory in (baseline_model_dir, candidate_model_dir):
        path = directory / "metrics.json"
        if not path.exists():
            raise FileNotFoundError(path)
        reports.append(json.loads(path.read_text(encoding="utf-8")))
    baseline_report, candidate_report = reports
    baseline_boundaries = baseline_report.get("split_boundaries")
    candidate_boundaries = candidate_report.get("split_boundaries")
    if baseline_boundaries != candidate_boundaries:
        raise ValueError("latest ensemble artifact split boundaries do not match")
    baseline_config = baseline_report.get("config", {})
    candidate_config = candidate_report.get("config", {})
    mismatches: dict[str, dict[str, object]] = {}
    allowed_differences: dict[str, dict[str, object]] = {}
    for key in PARITY_CONFIG_KEYS:
        baseline_value = baseline_config.get(key)
        candidate_value = candidate_config.get(key)
        if baseline_value != candidate_value:
            difference = {
                "baseline": baseline_value,
                "candidate": candidate_value,
            }
            if key == "model_type" and allow_model_type_mismatch:
                allowed_differences[key] = difference
            else:
                mismatches[key] = difference
    if mismatches:
        raise ValueError(
            "latest ensemble artifact training settings do not match: "
            + ", ".join(sorted(mismatches))
        )
    return {
        "split_boundaries": baseline_boundaries,
        "matched_config": {
            key: baseline_config.get(key)
            for key in PARITY_CONFIG_KEYS
            if baseline_config.get(key) == candidate_config.get(key)
        },
        "allowed_config_differences": allowed_differences,
        "baseline_feature_set": baseline_config.get("feature_set"),
        "candidate_feature_set": candidate_config.get("feature_set"),
        "baseline_model_type": baseline_config.get("model_type"),
        "candidate_model_type": candidate_config.get("model_type"),
    }


def blend_latest_prediction_frames(
    baseline: pd.DataFrame,
    candidate: pd.DataFrame,
    candidate_weight: float,
    preserve_baseline_direction: bool = False,
    context_policy: dict[str, object] | None = None,
    odds_calibration: dict[str, object] | None = None,
    odds_runtime_authorized: bool = False,
) -> pd.DataFrame:
    """Blend aligned latest predictions, then apply policy and odds to the blend."""
    keys = ["timeframe", "timeframe_minutes", "bar_start", "decision_timestamp"]
    required = {*keys, "probability_up", "volatility_regime"}
    for name, frame in (("baseline", baseline), ("candidate", candidate)):
        missing = sorted(required - set(frame.columns))
        if missing:
            raise ValueError(f"{name} latest predictions are missing: {', '.join(missing)}")
        if frame.duplicated(keys).any():
            raise ValueError(f"{name} latest predictions contain duplicate keys")
    candidate_values = candidate[[*keys, "probability_up"]].rename(
        columns={"probability_up": "candidate_probability_up"}
    )
    output = baseline.merge(candidate_values, on=keys, how="inner", validate="one_to_one")
    if len(output) != len(baseline) or len(output) != len(candidate):
        raise ValueError("latest ensemble sources do not contain identical prediction keys")
    output["baseline_probability_up"] = output["probability_up"].astype("float64")
    output["probability_up"] = blend_probability_values(
        output["baseline_probability_up"].to_numpy(dtype="float64"),
        output["candidate_probability_up"].to_numpy(dtype="float64"),
        candidate_weight,
        preserve_baseline_direction,
    )
    output["probability_down"] = 1 - output["probability_up"]
    output["predicted_direction"] = np.where(
        output["probability_up"].ge(0.5), "up", "down"
    )
    output["direction_score"] = (2 * output["probability_up"] - 1) * 100
    output["class_confidence"] = np.maximum(
        output["probability_up"], output["probability_down"]
    )
    output["model_confidence"] = output["class_confidence"]
    odds_rows: list[dict[str, object]] = []
    policy_rows: list[dict[str, object]] = []
    for row in output.itertuples(index=False):
        name = str(row.timeframe)
        model_confidence = float(row.model_confidence)
        timeframe_odds = None if odds_calibration is None else odds_calibration.get(name)
        if timeframe_odds is None:
            odds = {
                "confidence": model_confidence,
                "confidence_lower": None,
                "confidence_upper": None,
                "support_count": 0,
                "calibration_level": "model_probability",
                "calibration_source": "model_confidence",
                "empirical_accuracy": None,
                "locally_consistent": False,
                "fair_decimal_odds": 1 / model_confidence,
                "odds_ratio": model_confidence / (1 - model_confidence),
                "odds_valid": False,
                "odds_edge_confirmed": False,
            }
        else:
            odds = calibrate_prediction_odds(
                model_confidence,
                str(row.predicted_direction),
                str(row.volatility_regime),
                timeframe_odds,
            )
        calibration_gate_passed = bool(odds["odds_valid"])
        odds["odds_valid"] = bool(odds_runtime_authorized and calibration_gate_passed)
        odds["odds_calibration_gate_passed"] = calibration_gate_passed
        odds["odds_runtime_authorized"] = odds_runtime_authorized
        rule = None if context_policy is None else context_policy.get(name)
        eligible, reason = evaluate_context_rule(
            pd.Timestamp(row.decision_timestamp),
            str(row.volatility_regime),
            rule,
            confidence=model_confidence,
            predicted_direction=str(row.predicted_direction),
        )
        odds_rows.append(odds)
        policy_rows.append(
            {
                "prediction_eligible": eligible,
                "strict_prediction_eligible": bool(
                    eligible and odds["odds_valid"] and odds["odds_edge_confirmed"]
                ),
                "eligibility_reason": reason,
                "context_accuracy_estimate": (
                    rule.get("reference_accuracy") if rule is not None else None
                ),
                "accuracy_lower_bound": (
                    rule.get("accuracy_lower_bound") if rule is not None else None
                ),
                "policy_coverage": (
                    rule.get("reference_coverage") if rule is not None else None
                ),
                "quality_score": rule.get("quality_score") if rule is not None else None,
                "context_worst_fold_accuracy": (
                    rule.get("worst_fold_accuracy") if rule is not None else None
                ),
            }
        )
    odds_frame = pd.DataFrame(odds_rows, index=output.index).rename(
        columns={
            "support_count": "odds_support",
            "calibration_level": "odds_calibration_level",
            "calibration_source": "odds_calibration_source",
            "empirical_accuracy": "odds_empirical_accuracy",
            "locally_consistent": "odds_locally_consistent",
        }
    )
    output = output.drop(
        columns=[
            "confidence",
            "confidence_lower",
            "confidence_upper",
            "fair_decimal_odds",
            "odds_ratio",
            "odds_support",
            "odds_calibration_level",
            "odds_calibration_source",
            "odds_empirical_accuracy",
            "odds_locally_consistent",
            "odds_valid",
            "odds_edge_confirmed",
            "prediction_eligible",
            "strict_prediction_eligible",
            "eligibility_reason",
            "context_accuracy_estimate",
            "accuracy_lower_bound",
            "policy_coverage",
            "quality_score",
            "context_worst_fold_accuracy",
        ],
        errors="ignore",
    )
    output = pd.concat(
        [output, odds_frame, pd.DataFrame(policy_rows, index=output.index)], axis=1
    )
    output["ensemble_candidate_weight"] = candidate_weight
    output["ensemble_preserve_baseline_direction"] = preserve_baseline_direction
    return output.sort_values("timeframe_minutes").reset_index(drop=True)


def predict_latest_ensemble(
    m1: pd.DataFrame,
    baseline_model_dir: Path,
    candidate_model_dir: Path,
    candidate_weight: float,
    preserve_baseline_direction: bool = False,
    context_policy: dict[str, object] | None = None,
    odds_calibration: dict[str, object] | None = None,
    odds_runtime_authorized: bool = False,
    allow_model_type_mismatch: bool = False,
) -> tuple[pd.DataFrame, dict[str, object]]:
    parity = assert_latest_artifact_parity(
        baseline_model_dir,
        candidate_model_dir,
        allow_model_type_mismatch=allow_model_type_mismatch,
    )
    baseline = predict_latest(m1, baseline_model_dir)
    candidate = predict_latest(m1, candidate_model_dir)
    blended = blend_latest_prediction_frames(
        baseline,
        candidate,
        candidate_weight,
        preserve_baseline_direction,
        context_policy,
        odds_calibration,
        odds_runtime_authorized,
    )
    return blended, parity


def build_ensemble_predictions(
    baseline_dir: Path | Sequence[Path],
    candidate_dir: Path | Sequence[Path],
    output_dir: Path,
    timeframes: Sequence[int],
    candidate_weight: float,
    preserve_baseline_direction: bool = False,
) -> dict[str, object]:
    baseline_dirs = [baseline_dir] if isinstance(baseline_dir, Path) else list(baseline_dir)
    candidate_dirs = [candidate_dir] if isinstance(candidate_dir, Path) else list(candidate_dir)
    if not baseline_dirs or not candidate_dirs:
        raise ValueError("ensemble requires at least one baseline and candidate directory")

    def manifest_entry(directories: Sequence[Path], name: str) -> dict[str, object]:
        for directory in directories:
            manifest = json.loads(
                (directory / "manifest.json").read_text(encoding="utf-8")
            )
            if name in manifest["timeframes"]:
                return manifest["timeframes"][name]
        raise ValueError(f"prediction manifests do not contain {name}")

    created_at = datetime.now(UTC).isoformat()
    output_dir.mkdir(parents=True, exist_ok=True)
    report: dict[str, object] = {
        "created_at": created_at,
        "baseline_dirs": [str(path) for path in baseline_dirs],
        "candidate_dirs": [str(path) for path in candidate_dirs],
        "candidate_weight": candidate_weight,
        "preserve_baseline_direction": preserve_baseline_direction,
        "timeframes": {},
    }
    manifest: dict[str, object] = {
        "format_version": 1,
        "created_at": created_at,
        "kind": "next_bar_probability_ensemble",
        "sources": {
            "baseline": [str(path) for path in baseline_dirs],
            "candidate": [str(path) for path in candidate_dirs],
            "candidate_weight": candidate_weight,
            "preserve_baseline_direction": preserve_baseline_direction,
        },
        "timeframes": {},
    }
    for timeframe in timeframes:
        name = f"M{timeframe}"
        baseline_entry = manifest_entry(baseline_dirs, name)
        candidate_entry = manifest_entry(candidate_dirs, name)
        baseline = read_prediction_sets(baseline_dirs, timeframe)
        candidate = read_prediction_sets(candidate_dirs, timeframe)
        blended = blend_prediction_frames(
            baseline,
            candidate,
            candidate_weight,
            preserve_baseline_direction,
        )
        prediction_name = f"m{timeframe}_walk_forward_predictions.parquet"
        blended.to_parquet(output_dir / prediction_name, index=False)
        aggregate = evaluate_probabilities(
            blended["target_up"].to_numpy(dtype="int8"),
            blended["probability_up"].to_numpy(dtype="float64"),
        )
        fold_metrics = []
        for fold, group in blended.groupby("fold", sort=False):
            values = evaluate_probabilities(
                group["target_up"].to_numpy(dtype="int8"),
                group["probability_up"].to_numpy(dtype="float64"),
            )
            fold_metrics.append({"fold": str(fold), **values})
        report["timeframes"][name] = {
            "aggregate": aggregate,
            "folds": fold_metrics,
            "context_diagnostics": context_diagnostics(blended),
        }
        manifest["timeframes"][name] = {
            "minutes": timeframe,
            "features": list(baseline_entry["features"]),
            "predictions": prediction_name,
            "baseline_features": list(baseline_entry["features"]),
            "candidate_features": list(candidate_entry["features"]),
        }
    (output_dir / "ensemble_metrics.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Blend two aligned next-bar OOS probability sets."
    )
    parser.add_argument("--baseline-dir", type=Path, action="append", required=True)
    parser.add_argument("--candidate-dir", type=Path, action="append", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--timeframes", type=parse_timeframes, default=(15,))
    parser.add_argument("--candidate-weight", type=float, default=0.25)
    parser.add_argument(
        "--preserve-baseline-direction",
        action="store_true",
        help="Use the blend only for edge magnitude while keeping the baseline up/down direction.",
    )
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    report = build_ensemble_predictions(
        args.baseline_dir,
        args.candidate_dir,
        args.output_dir,
        args.timeframes,
        args.candidate_weight,
        args.preserve_baseline_direction,
    )
    summary = {
        name: values["aggregate"] for name, values in report["timeframes"].items()
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
