from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np
import pandas as pd

from trade_data.next_bar import (
    context_diagnostics,
    evaluate_probabilities,
    parse_timeframes,
)


def blend_prediction_frames(
    baseline: pd.DataFrame,
    candidate: pd.DataFrame,
    candidate_weight: float,
) -> pd.DataFrame:
    if not 0 <= candidate_weight <= 1:
        raise ValueError("candidate_weight must be between 0 and 1")
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
    candidate_columns = candidate[
        [*keys, "decision_timestamp", "target_timestamp", "target_up", "probability_up"]
    ].rename(
        columns={
            "decision_timestamp": "candidate_decision_timestamp",
            "target_timestamp": "candidate_target_timestamp",
            "target_up": "candidate_target_up",
            "probability_up": "candidate_probability_up",
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
    output["probability_up"] = (
        (1 - candidate_weight) * output["baseline_probability_up"]
        + candidate_weight * output["candidate_probability_up"].astype("float64")
    )
    output["predicted_up"] = output["probability_up"].ge(0.5).astype("int8")
    output["predicted_direction"] = np.where(
        output["predicted_up"].eq(1), "up", "down"
    )
    output["confidence"] = np.maximum(
        output["probability_up"], 1 - output["probability_up"]
    )
    output["correct"] = output["predicted_up"].eq(output["target_up"].astype("int8"))
    output["ensemble_candidate_weight"] = candidate_weight
    return output.drop(
        columns=[
            "candidate_decision_timestamp",
            "candidate_target_timestamp",
            "candidate_target_up",
        ]
    ).sort_values("decision_timestamp").reset_index(drop=True)


def build_ensemble_predictions(
    baseline_dir: Path,
    candidate_dir: Path,
    output_dir: Path,
    timeframes: Sequence[int],
    candidate_weight: float,
) -> dict[str, object]:
    baseline_manifest = json.loads(
        (baseline_dir / "manifest.json").read_text(encoding="utf-8")
    )
    candidate_manifest = json.loads(
        (candidate_dir / "manifest.json").read_text(encoding="utf-8")
    )
    created_at = datetime.now(UTC).isoformat()
    output_dir.mkdir(parents=True, exist_ok=True)
    report: dict[str, object] = {
        "created_at": created_at,
        "baseline_dir": str(baseline_dir),
        "candidate_dir": str(candidate_dir),
        "candidate_weight": candidate_weight,
        "timeframes": {},
    }
    manifest: dict[str, object] = {
        "format_version": 1,
        "created_at": created_at,
        "kind": "next_bar_probability_ensemble",
        "sources": {
            "baseline": str(baseline_dir),
            "candidate": str(candidate_dir),
            "candidate_weight": candidate_weight,
        },
        "timeframes": {},
    }
    for timeframe in timeframes:
        name = f"M{timeframe}"
        if name not in baseline_manifest["timeframes"]:
            raise ValueError(f"baseline manifest does not contain {name}")
        if name not in candidate_manifest["timeframes"]:
            raise ValueError(f"candidate manifest does not contain {name}")
        baseline_entry = baseline_manifest["timeframes"][name]
        candidate_entry = candidate_manifest["timeframes"][name]
        baseline = pd.read_parquet(baseline_dir / baseline_entry["predictions"])
        candidate = pd.read_parquet(candidate_dir / candidate_entry["predictions"])
        blended = blend_prediction_frames(baseline, candidate, candidate_weight)
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
    parser.add_argument("--baseline-dir", type=Path, required=True)
    parser.add_argument("--candidate-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--timeframes", type=parse_timeframes, default=(15,))
    parser.add_argument("--candidate-weight", type=float, default=0.25)
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    report = build_ensemble_predictions(
        args.baseline_dir,
        args.candidate_dir,
        args.output_dir,
        args.timeframes,
        args.candidate_weight,
    )
    summary = {
        name: values["aggregate"] for name, values in report["timeframes"].items()
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
