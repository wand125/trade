from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np
import pandas as pd
from scipy.stats import binomtest

from trade_data.next_bar import evaluate_probabilities, wilson_accuracy_lower_bound


DEFAULT_THRESHOLDS = (0.515, 0.52, 0.525, 0.53, 0.54, 0.55, 0.60)
DEFAULT_DEVELOPMENT_FOLDS = ("test2020", "test2021", "test2022", "test2023")


def read_prediction_sets(directories: Sequence[Path], timeframe: int) -> pd.DataFrame:
    if not directories:
        raise ValueError("at least one prediction directory is required")
    filename = f"m{timeframe}_walk_forward_predictions.parquet"
    frames = []
    for directory in directories:
        path = directory / filename
        if not path.exists():
            raise FileNotFoundError(path)
        frames.append(pd.read_parquet(path))
    output = pd.concat(frames, ignore_index=True)
    keys = ["fold", "timestamp"]
    required = {*keys, "target_up", "probability_up", "confidence", "correct"}
    missing = sorted(required - set(output.columns))
    if missing:
        raise ValueError(f"predictions are missing columns: {', '.join(missing)}")
    if output.duplicated(keys).any():
        raise ValueError("prediction sets contain duplicate fold/timestamp rows")
    return output.sort_values(keys).reset_index(drop=True)


def assert_aligned(reference: pd.DataFrame, candidate: pd.DataFrame, name: str) -> None:
    keys = ["fold", "timestamp", "target_up"]
    if len(reference) != len(candidate) or not reference[keys].equals(candidate[keys]):
        raise ValueError(f"{name} predictions do not align with baseline")


def period_metrics(frame: pd.DataFrame) -> dict[str, float | int]:
    values = evaluate_probabilities(
        frame["target_up"].to_numpy(dtype="int8"),
        frame["probability_up"].to_numpy(dtype="float64"),
    )
    return {
        "rows": len(frame),
        "accuracy": values["accuracy"],
        "brier_score": values["brier_score"],
        "log_loss": values["log_loss"],
        "expected_calibration_error": values["expected_calibration_error"],
    }


def lane_metrics(frame: pd.DataFrame, threshold: float) -> dict[str, float | int | None]:
    selected = frame.loc[frame["confidence"].ge(threshold)]
    coverage = len(selected) / len(frame) if len(frame) else 0.0
    if selected.empty:
        return {
            "rows": 0,
            "coverage": coverage,
            "accuracy": None,
            "wilson_lower": None,
            "selection_score": None,
        }
    accuracy = float(selected["correct"].mean())
    lower = wilson_accuracy_lower_bound(int(selected["correct"].sum()), len(selected))
    return {
        "rows": len(selected),
        "coverage": coverage,
        "accuracy": accuracy,
        "wilson_lower": lower,
        "selection_score": float(np.sqrt(coverage) * (lower - 0.5)),
    }


def paired_direction_metrics(
    reference: pd.DataFrame, candidate: pd.DataFrame
) -> dict[str, float | int]:
    reference_correct = reference["correct"].astype(bool).to_numpy()
    candidate_correct = candidate["correct"].astype(bool).to_numpy()
    fixes = int((~reference_correct & candidate_correct).sum())
    harms = int((reference_correct & ~candidate_correct).sum())
    discordant_rows = fixes + harms
    paired_p = (
        float(
            binomtest(
                fixes, discordant_rows, 0.5, alternative="two-sided"
            ).pvalue
        )
        if discordant_rows
        else 1.0
    )
    return {
        "fixes": fixes,
        "harms": harms,
        "discordant_rows": discordant_rows,
        "net_fixes": fixes - harms,
        "mcnemar_exact_p": paired_p,
    }


def analyze_candidate(
    baseline: pd.DataFrame,
    single: pd.DataFrame,
    normal_blend: pd.DataFrame,
    confidence_blend: pd.DataFrame,
    development_folds: Sequence[str] = DEFAULT_DEVELOPMENT_FOLDS,
    thresholds: Sequence[float] = DEFAULT_THRESHOLDS,
) -> dict[str, object]:
    for name, frame in (
        ("single", single),
        ("normal_blend", normal_blend),
        ("confidence_blend", confidence_blend),
    ):
        assert_aligned(baseline, frame, name)
    development_names = set(development_folds)
    period_masks = {
        "development": baseline["fold"].isin(development_names),
        "confirmation": ~baseline["fold"].isin(development_names),
        "all": pd.Series(True, index=baseline.index),
    }
    frames = {
        "baseline": baseline,
        "single": single,
        "normal_blend": normal_blend,
        "confidence_blend": confidence_blend,
    }
    periods = {
        period: {
            name: period_metrics(frame.loc[mask]) for name, frame in frames.items()
        }
        for period, mask in period_masks.items()
    }

    development_mask = period_masks["development"]
    development_grid: dict[str, object] = {}
    for threshold in thresholds:
        development_grid[str(threshold)] = {
            "baseline": lane_metrics(baseline.loc[development_mask], threshold),
            "candidate": lane_metrics(
                confidence_blend.loc[development_mask], threshold
            ),
        }
    valid_thresholds = [
        threshold
        for threshold in thresholds
        if development_grid[str(threshold)]["candidate"]["selection_score"] is not None
    ]
    if not valid_thresholds:
        raise ValueError("no threshold produced a non-empty development lane")
    selected_threshold = max(
        valid_thresholds,
        key=lambda threshold: development_grid[str(threshold)]["candidate"][
            "selection_score"
        ],
    )
    selected_lane = {
        period: {
            "baseline": lane_metrics(baseline.loc[mask], selected_threshold),
            "candidate": lane_metrics(
                confidence_blend.loc[mask], selected_threshold
            ),
        }
        for period, mask in period_masks.items()
    }

    fold_comparison: dict[str, object] = {}
    for fold in baseline["fold"].drop_duplicates():
        mask = baseline["fold"].eq(fold)
        base_lane = lane_metrics(baseline.loc[mask], selected_threshold)
        candidate_lane = lane_metrics(confidence_blend.loc[mask], selected_threshold)
        fold_comparison[str(fold)] = {
            "baseline": base_lane,
            "candidate": candidate_lane,
            "accuracy_improved": bool(
                candidate_lane["accuracy"] is not None
                and base_lane["accuracy"] is not None
                and candidate_lane["accuracy"] > base_lane["accuracy"]
            ),
            "score_improved": bool(
                candidate_lane["selection_score"] is not None
                and base_lane["selection_score"] is not None
                and candidate_lane["selection_score"]
                > base_lane["selection_score"]
            ),
        }

    proper_score_fold_improvements = {}
    for metric in ("brier_score", "log_loss", "expected_calibration_error"):
        improvements = 0
        for fold in baseline["fold"].drop_duplicates():
            mask = baseline["fold"].eq(fold)
            base_value = period_metrics(baseline.loc[mask])[metric]
            candidate_value = period_metrics(confidence_blend.loc[mask])[metric]
            improvements += int(candidate_value < base_value)
        proper_score_fold_improvements[metric] = improvements

    direction_candidates = {
        "single": single,
        "normal_blend": normal_blend,
    }
    direction_paired = {
        period: {
            name: paired_direction_metrics(
                baseline.loc[mask], candidate.loc[mask]
            )
            for name, candidate in direction_candidates.items()
        }
        for period, mask in period_masks.items()
    }
    direction_fold_improvements: dict[str, dict[str, int]] = {}
    for name, candidate in direction_candidates.items():
        counts = {
            "accuracy": 0,
            "brier_score": 0,
            "log_loss": 0,
            "expected_calibration_error": 0,
        }
        for fold in baseline["fold"].drop_duplicates():
            mask = baseline["fold"].eq(fold)
            base_values = period_metrics(baseline.loc[mask])
            candidate_values = period_metrics(candidate.loc[mask])
            counts["accuracy"] += int(
                candidate_values["accuracy"] > base_values["accuracy"]
            )
            for metric in (
                "brier_score",
                "log_loss",
                "expected_calibration_error",
            ):
                counts[metric] += int(candidate_values[metric] < base_values[metric])
        direction_fold_improvements[name] = counts

    normal_blend_paired = direction_paired["all"]["normal_blend"]
    return {
        "periods": periods,
        "development_grid": development_grid,
        "selected_threshold": selected_threshold,
        "selected_lane": selected_lane,
        "fold_comparison": fold_comparison,
        "proper_score_fold_improvements": proper_score_fold_improvements,
        "direction_paired": direction_paired,
        "direction_fold_improvements": direction_fold_improvements,
        "normal_blend_paired": {
            "fixes": normal_blend_paired["fixes"],
            "harms": normal_blend_paired["harms"],
            "mcnemar_exact_p": normal_blend_paired["mcnemar_exact_p"],
        },
    }


def comma_strings(value: str) -> tuple[str, ...]:
    output = tuple(item.strip() for item in value.split(",") if item.strip())
    if not output:
        raise argparse.ArgumentTypeError("value must contain at least one item")
    return output


def comma_floats(value: str) -> tuple[float, ...]:
    try:
        output = tuple(float(item.strip()) for item in value.split(",") if item.strip())
    except ValueError as exc:
        raise argparse.ArgumentTypeError("thresholds must be comma-separated numbers") from exc
    if not output or any(not 0.5 < item < 1 for item in output):
        raise argparse.ArgumentTypeError("thresholds must be between 0.5 and 1")
    return output


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compare a next-bar candidate and fixed blends by chronological period."
    )
    parser.add_argument("--baseline-dir", type=Path, action="append", required=True)
    parser.add_argument("--single-dir", type=Path, required=True)
    parser.add_argument("--normal-blend-dir", type=Path, required=True)
    parser.add_argument("--confidence-blend-dir", type=Path, required=True)
    parser.add_argument("--timeframe", type=int, default=15)
    parser.add_argument(
        "--development-folds",
        type=comma_strings,
        default=DEFAULT_DEVELOPMENT_FOLDS,
    )
    parser.add_argument(
        "--thresholds", type=comma_floats, default=DEFAULT_THRESHOLDS
    )
    parser.add_argument("--output", type=Path, default=None)
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    baseline = read_prediction_sets(args.baseline_dir, args.timeframe)
    report = analyze_candidate(
        baseline,
        read_prediction_sets([args.single_dir], args.timeframe),
        read_prediction_sets([args.normal_blend_dir], args.timeframe),
        read_prediction_sets([args.confidence_blend_dir], args.timeframe),
        args.development_folds,
        args.thresholds,
    )
    payload = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
