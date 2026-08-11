from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

from trade_data.next_bar import context_diagnostics
from trade_data.next_bar_registry import (
    compare_fixed_candidate_frames,
    read_prediction_sets,
)
from trade_data.next_bar_selective_correctness import (
    build_selective_correctness_frame,
)


@dataclass(frozen=True)
class ComponentConsensusFilterConfig:
    timeframe: int = 15
    minimum_support: int = 2
    direction_tolerance: float = 1e-15


def apply_component_consensus_filter(
    frame: pd.DataFrame,
    config: ComponentConsensusFilterConfig,
) -> pd.DataFrame:
    if config.minimum_support not in (2, 3):
        raise ValueError("minimum_support must be 2 or 3")
    if config.direction_tolerance < 0:
        raise ValueError("direction_tolerance must be non-negative")
    required = {
        "reference_probability_up",
        "reference_predicted_up",
        "reference_correct",
        "reference_candidate_probability_up",
        "shape_candidate_probability_up",
        "profile_candidate_probability_up",
        "target_up",
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"consensus frame is missing: {', '.join(missing)}")

    output = frame.copy()
    direction_sign = np.where(output["reference_predicted_up"].eq(1), 1.0, -1.0)
    component_columns = (
        "reference_candidate_probability_up",
        "shape_candidate_probability_up",
        "profile_candidate_probability_up",
    )
    aligned_edges = np.column_stack(
        [
            direction_sign
            * (output[column].to_numpy(dtype="float64") - 0.5)
            for column in component_columns
        ]
    )
    if not np.isfinite(aligned_edges).all():
        raise ValueError("component probabilities must be finite")
    support = aligned_edges > config.direction_tolerance
    output["consensus_support_count"] = support.sum(axis=1).astype("int8")
    output["consensus_support_fraction"] = support.mean(axis=1)
    output["consensus_minimum_aligned_edge"] = aligned_edges.min(axis=1)
    output["consensus_mean_aligned_edge"] = aligned_edges.mean(axis=1)
    selected = output["consensus_support_count"].ge(config.minimum_support)
    output["component_consensus_selected"] = selected

    reference_probability = output["reference_probability_up"].to_numpy(
        dtype="float64"
    )
    reference_confidence = np.maximum(
        reference_probability, 1 - reference_probability
    )
    neutral_confidence = 0.5 + np.finfo("float64").eps
    confidence = np.where(selected, reference_confidence, neutral_confidence)
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
    output["component_consensus_minimum_support"] = config.minimum_support
    if not output["probability_up"].ge(0.5).astype("int8").equals(
        output["predicted_up"]
    ):
        raise ValueError("consensus probability does not preserve reference direction")
    return output.sort_values(["fold", "timestamp"]).reset_index(drop=True)


def _reference_frame(frame: pd.DataFrame) -> pd.DataFrame:
    reference = frame.copy()
    reference["probability_up"] = reference["reference_probability_up"].astype(
        "float64"
    )
    reference["probability_down"] = 1 - reference["probability_up"]
    reference["predicted_up"] = reference["reference_predicted_up"].astype("int8")
    reference["confidence"] = np.maximum(
        reference["probability_up"], reference["probability_down"]
    )
    reference["correct"] = reference["reference_correct"].astype(bool)
    return reference.sort_values(["fold", "timestamp"]).reset_index(drop=True)


def _support_report(frame: pd.DataFrame) -> dict[str, object]:
    development = frame["fold"].astype(str).isin(
        {"test2020", "test2021", "test2022", "test2023"}
    )
    masks = {
        "development": development,
        "confirmation": ~development,
        "all": pd.Series(True, index=frame.index),
    }
    return {
        period: {
            "rows": len(frame.loc[mask]),
            "support_count_fraction": {
                str(count): float(
                    frame.loc[mask, "consensus_support_count"].eq(count).mean()
                )
                for count in range(4)
            },
            "consensus_selected_fraction": float(
                frame.loc[mask, "component_consensus_selected"].mean()
            ),
        }
        for period, mask in masks.items()
    }


def run_component_consensus_filter(
    reference_dir: Path,
    shape_dir: Path,
    profile_dir: Path,
    output_dir: Path,
    config: ComponentConsensusFilterConfig,
    reference_threshold: float,
) -> dict[str, object]:
    if not 0.5 < reference_threshold < 1:
        raise ValueError("reference_threshold must be between 0.5 and 1")
    reference_predictions = read_prediction_sets(
        [reference_dir], config.timeframe
    )
    shape_predictions = read_prediction_sets([shape_dir], config.timeframe)
    profile_predictions = read_prediction_sets([profile_dir], config.timeframe)
    frame = build_selective_correctness_frame(
        reference_predictions, shape_predictions, profile_predictions
    )
    candidate = apply_component_consensus_filter(frame, config)
    reference = _reference_frame(frame)
    candidate_name = f"component_consensus_{config.minimum_support}_of_3"
    comparison = compare_fixed_candidate_frames(
        candidate,
        reference,
        reference_threshold,
        candidate_name,
        "reference",
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    created_at = datetime.now(UTC).isoformat()
    prediction_name = f"m{config.timeframe}_walk_forward_predictions.parquet"
    candidate.to_parquet(output_dir / prediction_name, index=False)
    report = {
        "created_at": created_at,
        "config": asdict(config),
        "reference_threshold": reference_threshold,
        "reference_dir": str(reference_dir),
        "shape_dir": str(shape_dir),
        "profile_dir": str(profile_dir),
        "rows": len(candidate),
        "comparison": comparison,
        "support": _support_report(candidate),
        "context_diagnostics": context_diagnostics(candidate),
    }
    manifest = {
        "format_version": 1,
        "created_at": created_at,
        "kind": "next_bar_fixed_component_consensus_filter",
        "sources": {
            "reference": str(reference_dir),
            "shape": str(shape_dir),
            "profile": str(profile_dir),
        },
        "timeframes": {
            f"M{config.timeframe}": {
                "minutes": config.timeframe,
                "features": [
                    "reference_candidate_direction",
                    "shape_candidate_direction",
                    "profile_candidate_direction",
                ],
                "minimum_support": config.minimum_support,
                "reference_threshold": reference_threshold,
                "predictions": prediction_name,
                "deployment_status": "research_only",
            }
        },
    }
    (output_dir / "consensus_filter_metrics.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Veto a fixed confidence candidate unless two or three component "
            "candidate directions support its direction."
        )
    )
    parser.add_argument("--reference-dir", type=Path, required=True)
    parser.add_argument("--shape-dir", type=Path, required=True)
    parser.add_argument("--profile-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--timeframe", type=int, required=True)
    parser.add_argument("--reference-threshold", type=float, required=True)
    parser.add_argument("--minimum-support", type=int, choices=(2, 3), required=True)
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    report = run_component_consensus_filter(
        reference_dir=args.reference_dir,
        shape_dir=args.shape_dir,
        profile_dir=args.profile_dir,
        output_dir=args.output_dir,
        config=ComponentConsensusFilterConfig(
            timeframe=args.timeframe,
            minimum_support=args.minimum_support,
        ),
        reference_threshold=args.reference_threshold,
    )
    print(
        json.dumps(
            {
                "rows": report["rows"],
                "comparison": report["comparison"]["periods"],
                "fold_wins": report["comparison"]["fold_wins"],
                "support": report["support"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
