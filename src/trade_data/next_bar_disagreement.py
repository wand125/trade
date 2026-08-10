from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np
import pandas as pd

from trade_data.next_bar import context_diagnostics, evaluate_probabilities
from trade_data.next_bar_overlay import read_prediction_sets


def aligned_prediction_matrix(
    baseline: pd.DataFrame,
    candidates: Sequence[pd.DataFrame],
) -> tuple[pd.DataFrame, np.ndarray]:
    if not candidates:
        raise ValueError("at least one candidate prediction frame is required")
    keys = ["fold", "timestamp"]
    required = {
        *keys,
        "decision_timestamp",
        "target_timestamp",
        "target_up",
        "probability_up",
    }
    for name, frame in [("baseline", baseline), *[
        (f"candidate_{index}", frame) for index, frame in enumerate(candidates)
    ]]:
        missing = sorted(required - set(frame.columns))
        if missing:
            raise ValueError(f"{name} predictions are missing: {', '.join(missing)}")
        if frame.duplicated(keys).any():
            raise ValueError(f"{name} predictions contain duplicate fold/timestamp rows")

    output = baseline.copy().sort_values(keys).reset_index(drop=True)
    probability_columns = [output["probability_up"].to_numpy(dtype="float64")]
    reference = output[[*keys, "decision_timestamp", "target_timestamp", "target_up"]]
    for index, candidate in enumerate(candidates):
        aligned = candidate.sort_values(keys).reset_index(drop=True)
        if len(aligned) != len(reference) or not aligned[
            [*keys, "decision_timestamp", "target_timestamp", "target_up"]
        ].equals(reference):
            raise ValueError(f"candidate_{index} predictions do not align with baseline")
        probability_columns.append(
            aligned["probability_up"].to_numpy(dtype="float64")
        )
    probabilities = np.column_stack(probability_columns)
    if not np.isfinite(probabilities).all() or np.any(
        (probabilities < 0) | (probabilities > 1)
    ):
        raise ValueError("model probabilities must be finite and within [0, 1]")
    return output, probabilities


def combine_disagreement_predictions(
    baseline: pd.DataFrame,
    candidates: Sequence[pd.DataFrame],
    uncertainty_penalty: float = 1.0,
    preserve_baseline_direction: bool = True,
) -> pd.DataFrame:
    if uncertainty_penalty < 0:
        raise ValueError("uncertainty_penalty must not be negative")
    output, probabilities = aligned_prediction_matrix(baseline, candidates)

    baseline_probability = probabilities[:, 0]
    baseline_sign = np.where(baseline_probability >= 0.5, 1.0, -1.0)
    aligned_edges = baseline_sign[:, None] * (probabilities - 0.5)
    edge_mean = aligned_edges.mean(axis=1)
    edge_standard_deviation = aligned_edges.std(axis=1, ddof=0)
    edge_lower_bound = edge_mean - uncertainty_penalty * edge_standard_deviation
    if preserve_baseline_direction:
        final_edge = np.maximum(edge_lower_bound, np.finfo("float64").eps)
        probability_up = 0.5 + baseline_sign * final_edge
    else:
        probability_up = probabilities.mean(axis=1)

    output["baseline_probability_up"] = baseline_probability
    output["probability_up"] = np.clip(probability_up, 1e-6, 1 - 1e-6)
    output["probability_down"] = 1 - output["probability_up"]
    output["predicted_up"] = output["probability_up"].ge(0.5).astype("int8")
    output["predicted_direction"] = np.where(
        output["predicted_up"].eq(1), "up", "down"
    )
    output["class_confidence"] = np.maximum(
        output["probability_up"], 1 - output["probability_up"]
    )
    output["confidence"] = output["class_confidence"]
    output["correct"] = output["predicted_up"].eq(
        output["target_up"].astype("int8")
    )
    output["ensemble_model_count"] = probabilities.shape[1]
    output["ensemble_uncertainty_penalty"] = uncertainty_penalty
    output["ensemble_preserve_baseline_direction"] = preserve_baseline_direction
    output["model_probability_std"] = probabilities.std(axis=1, ddof=0)
    output["aligned_edge_mean"] = edge_mean
    output["aligned_edge_std"] = edge_standard_deviation
    output["aligned_edge_lower_bound"] = edge_lower_bound
    return output.sort_values("decision_timestamp").reset_index(drop=True)


def build_disagreement_ensemble(
    baseline_dirs: Sequence[Path],
    candidate_dirs: Sequence[Path],
    output_dir: Path,
    timeframe: int = 15,
    uncertainty_penalty: float = 1.0,
    preserve_baseline_direction: bool = True,
) -> dict[str, object]:
    baseline = read_prediction_sets(baseline_dirs, timeframe)
    candidates = [read_prediction_sets([directory], timeframe) for directory in candidate_dirs]
    combined = combine_disagreement_predictions(
        baseline,
        candidates,
        uncertainty_penalty,
        preserve_baseline_direction,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    prediction_name = f"m{timeframe}_walk_forward_predictions.parquet"
    combined.to_parquet(output_dir / prediction_name, index=False)
    aggregate = evaluate_probabilities(
        combined["target_up"].to_numpy(dtype="int8"),
        combined["probability_up"].to_numpy(dtype="float64"),
    )
    folds = []
    for fold, group in combined.groupby("fold", sort=False):
        values = evaluate_probabilities(
            group["target_up"].to_numpy(dtype="int8"),
            group["probability_up"].to_numpy(dtype="float64"),
        )
        folds.append({"fold": str(fold), **values})
    created_at = datetime.now(UTC).isoformat()
    report = {
        "created_at": created_at,
        "timeframe": f"M{timeframe}",
        "baseline_dirs": [str(path) for path in baseline_dirs],
        "candidate_dirs": [str(path) for path in candidate_dirs],
        "model_count": 1 + len(candidate_dirs),
        "uncertainty_penalty": uncertainty_penalty,
        "preserve_baseline_direction": preserve_baseline_direction,
        "aggregate": aggregate,
        "folds": folds,
        "context_diagnostics": context_diagnostics(combined),
    }
    manifest = {
        "format_version": 1,
        "created_at": created_at,
        "kind": "next_bar_disagreement_ensemble",
        "sources": {
            "baseline": [str(path) for path in baseline_dirs],
            "candidates": [str(path) for path in candidate_dirs],
        },
        "formula": {
            "uncertainty_penalty": uncertainty_penalty,
            "preserve_baseline_direction": preserve_baseline_direction,
            "confidence_edge": "max(mean(baseline-aligned model edges) - penalty * population_std(baseline-aligned model edges), epsilon)",
        },
        "timeframes": {
            f"M{timeframe}": {
                "minutes": timeframe,
                "predictions": prediction_name,
            }
        },
    }
    (output_dir / "disagreement_metrics.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Combine aligned OOS models and penalize confidence by disagreement."
    )
    parser.add_argument("--baseline-dir", type=Path, action="append", required=True)
    parser.add_argument("--candidate-dir", type=Path, action="append", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--timeframe", type=int, default=15)
    parser.add_argument("--uncertainty-penalty", type=float, default=1.0)
    parser.add_argument("--preserve-baseline-direction", action="store_true")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    report = build_disagreement_ensemble(
        args.baseline_dir,
        args.candidate_dir,
        args.output_dir,
        args.timeframe,
        args.uncertainty_penalty,
        args.preserve_baseline_direction,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
