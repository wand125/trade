from __future__ import annotations

import json
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss, log_loss

from trade_data.next_bar import (
    confidence_calibration_error,
    evaluate_probabilities,
    wilson_accuracy_lower_bound,
)


DEFAULT_DEVELOPMENT_FOLDS = ("test2020", "test2021", "test2022", "test2023")
DEFAULT_RELIABILITY_EDGES = (0.5, 0.515, 0.525, 0.535, 0.55, 0.575, 0.6, 1.0)
DEFAULT_RELIABILITY_THRESHOLDS = (0.515, 0.525, 0.535, 0.55, 0.575, 0.6)
REQUIRED_PREDICTION_COLUMNS = {
    "fold",
    "timestamp",
    "target_up",
    "probability_up",
    "confidence",
    "correct",
}


@dataclass(frozen=True)
class CandidateSpec:
    candidate_id: str
    config_path: Path
    prediction_dir: Path
    status: str
    threshold: float
    role: str
    eligible: bool


def confidence_role(threshold: float) -> str:
    if threshold <= 0.52:
        return "broad"
    if threshold < 0.53:
        return "balanced"
    if threshold <= 0.54:
        return "selective"
    return "precision"


def read_prediction_sets(
    directories: Sequence[Path], timeframe: int
) -> pd.DataFrame:
    if not directories:
        raise ValueError("at least one prediction directory is required")
    filename = f"m{timeframe}_walk_forward_predictions.parquet"
    frames: list[pd.DataFrame] = []
    for directory in directories:
        path = directory / filename
        if not path.exists():
            manifest_path = directory / "manifest.json"
            if not manifest_path.exists():
                raise FileNotFoundError(path)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            entry = manifest.get("timeframes", {}).get(f"M{timeframe}")
            if not isinstance(entry, dict) or not entry.get("predictions"):
                raise FileNotFoundError(path)
            path = directory / str(entry["predictions"])
            if not path.exists():
                raise FileNotFoundError(path)
        frames.append(pd.read_parquet(path))
    output = pd.concat(frames, ignore_index=True)
    missing = sorted(REQUIRED_PREDICTION_COLUMNS - set(output.columns))
    if missing:
        raise ValueError(f"predictions are missing columns: {', '.join(missing)}")
    keys = ["fold", "timestamp"]
    if output.duplicated(keys).any():
        raise ValueError("prediction sets contain duplicate fold/timestamp rows")
    return output.sort_values(keys).reset_index(drop=True)


def align_prediction_subset(
    predictions: pd.DataFrame, reference: pd.DataFrame
) -> pd.DataFrame:
    """Select predictions on exactly the ordered fold/timestamp/target reference."""
    keys = ["fold", "timestamp", "target_up"]
    for name, frame in (("predictions", predictions), ("reference", reference)):
        missing = sorted(set(keys) - set(frame.columns))
        if missing:
            raise ValueError(f"{name} are missing alignment columns: {', '.join(missing)}")
        if frame.duplicated(["fold", "timestamp"]).any():
            raise ValueError(f"{name} contain duplicate fold/timestamp rows")

    ordered_keys = reference[keys].copy()
    ordered_keys["_reference_order"] = np.arange(len(ordered_keys), dtype="int64")
    aligned = ordered_keys.merge(
        predictions,
        on=keys,
        how="left",
        validate="one_to_one",
        indicator=True,
    )
    if not aligned["_merge"].eq("both").all():
        raise ValueError("predictions do not cover every reference row and target")
    return (
        aligned.sort_values("_reference_order")
        .drop(columns=["_reference_order", "_merge"])
        .reset_index(drop=True)
    )


def apply_confidence_exclusion_guard(
    frame: pd.DataFrame,
    excluded_groups: Sequence[Mapping[str, object]],
    abstain_confidence: float = 0.5,
) -> pd.DataFrame:
    """Turn development-selected weak subgroups into confidence abstentions."""
    if not excluded_groups:
        raise ValueError("at least one excluded confidence group is required")
    if not 0.5 <= abstain_confidence < 1:
        raise ValueError("abstain_confidence must be between 0.5 inclusive and 1")
    if "confidence" not in frame:
        raise ValueError("predictions are missing confidence")

    output = frame.copy()
    excluded = pd.Series(False, index=output.index, dtype="bool")
    normalized_groups: list[dict[str, object]] = []
    for group in excluded_groups:
        normalized = dict(group)
        if not normalized:
            raise ValueError("excluded confidence groups cannot be empty")
        missing = sorted(set(normalized) - set(output.columns))
        if missing:
            raise ValueError(
                f"confidence guard columns are missing: {', '.join(missing)}"
            )
        group_mask = pd.Series(True, index=output.index, dtype="bool")
        for column, value in normalized.items():
            group_mask &= output[column].eq(value)
        excluded |= group_mask
        normalized_groups.append(normalized)

    output["pre_guard_confidence"] = output["confidence"].astype("float64")
    output["confidence_guard_excluded"] = excluded
    output.loc[excluded, "confidence"] = abstain_confidence
    output.attrs["confidence_guard"] = {
        "excluded_groups": normalized_groups,
        "abstain_confidence": abstain_confidence,
    }
    return output


def blend_confidence_frames(
    base: pd.DataFrame,
    contributor: pd.DataFrame,
    contributor_weight: float,
) -> pd.DataFrame:
    """Blend aligned correctness confidence without changing direction probabilities."""
    if not 0 <= contributor_weight <= 1:
        raise ValueError("contributor_weight must be between 0 and 1")
    assert_aligned(base, contributor, "confidence contributor")
    if "confidence" not in base or "confidence" not in contributor:
        raise ValueError("predictions are missing confidence")

    output = base.copy()
    output["base_confidence"] = base["confidence"].to_numpy(dtype="float64")
    output["contributor_confidence"] = contributor["confidence"].to_numpy(
        dtype="float64"
    )
    output["confidence"] = (
        (1 - contributor_weight) * output["base_confidence"]
        + contributor_weight * output["contributor_confidence"]
    )
    output["confidence_contributor_weight"] = contributor_weight
    return output


def _selection_mask(
    frame: pd.DataFrame,
    threshold: float,
    selection_column: str | None = None,
) -> pd.Series:
    if not 0.5 <= threshold < 1:
        raise ValueError("threshold must be between 0.5 inclusive and 1")
    if selection_column is None:
        if "confidence" not in frame:
            raise ValueError("predictions are missing confidence")
        return frame["confidence"].ge(threshold)
    if selection_column not in frame:
        raise ValueError(f"predictions are missing selection column: {selection_column}")
    values = frame[selection_column]
    if values.isna().any() or not values.isin([True, False]).all():
        raise ValueError("selection column must contain only finite booleans")
    return values.astype("bool")


def selection_mask_metrics(
    frame: pd.DataFrame, selected: pd.Series | np.ndarray
) -> dict[str, float | int | None]:
    resolved = pd.Series(selected, index=frame.index)
    if len(resolved) != len(frame) or resolved.isna().any():
        raise ValueError("selection mask must align with predictions")
    if not resolved.isin([True, False]).all():
        raise ValueError("selection mask must contain only booleans")
    chosen = frame.loc[resolved.astype("bool")]
    coverage = len(chosen) / len(frame) if len(frame) else 0.0
    if chosen.empty:
        return {
            "rows": 0,
            "coverage": coverage,
            "accuracy": None,
            "wilson_lower": None,
            "selection_score": None,
        }
    successes = int(chosen["correct"].sum())
    lower = wilson_accuracy_lower_bound(successes, len(chosen))
    return {
        "rows": len(chosen),
        "coverage": coverage,
        "accuracy": float(successes / len(chosen)),
        "wilson_lower": lower,
        "selection_score": float(np.sqrt(coverage) * (lower - 0.5)),
    }


def selection_source_reliability(
    frame: pd.DataFrame, selected: pd.Series | np.ndarray
) -> dict[str, object]:
    """Audit each source's stated odds inside one fixed selection set."""
    resolved = pd.Series(selected, index=frame.index)
    if len(resolved) != len(frame) or resolved.isna().any():
        raise ValueError("selection mask must align with predictions")
    if not resolved.isin([True, False]).all():
        raise ValueError("selection mask must contain only booleans")
    chosen = frame.loc[resolved.astype("bool")]
    output: dict[str, object] = {}
    for source in ("first", "second"):
        column = f"{source}_source_confidence"
        if column not in chosen:
            raise ValueError(f"predictions are missing source confidence: {column}")
        source_frame = chosen[["correct", column]].rename(
            columns={column: "confidence"}
        )
        output[source] = reliability_metrics(source_frame)
    return output


def combine_confidence_selection_frames(
    first: pd.DataFrame,
    second: pd.DataFrame,
    first_threshold: float,
    second_threshold: float,
    operator: str,
) -> pd.DataFrame:
    """Combine fixed selection sets while preserving the first probability/confidence."""
    if operator not in {"first", "second", "union", "intersection"}:
        raise ValueError("selection operator must be first, second, union, or intersection")
    assert_aligned(first, second, "selection contributor")
    first_correct = first["correct"].to_numpy(dtype="bool")
    second_correct = second["correct"].to_numpy(dtype="bool")
    if not np.array_equal(first_correct, second_correct):
        raise ValueError("selection candidates must preserve the same direction")
    first_selected = _selection_mask(first, first_threshold)
    second_selected = _selection_mask(second, second_threshold)
    masks = {
        "first": first_selected,
        "second": second_selected,
        "union": first_selected | second_selected,
        "intersection": first_selected & second_selected,
    }
    output = first.copy()
    output["first_source_confidence"] = first["confidence"].to_numpy(dtype="float64")
    output["second_source_confidence"] = second["confidence"].to_numpy(dtype="float64")
    output["first_source_selected"] = first_selected.to_numpy(dtype="bool")
    output["second_source_selected"] = second_selected.to_numpy(dtype="bool")
    output["confidence_selection_eligible"] = masks[operator].to_numpy(dtype="bool")
    output["confidence_selection_operator"] = operator
    output["first_source_threshold"] = first_threshold
    output["second_source_threshold"] = second_threshold
    return output


def compare_confidence_selection_operators(
    first: pd.DataFrame,
    second: pd.DataFrame,
    first_threshold: float,
    second_threshold: float,
    first_name: str = "first",
    second_name: str = "second",
    development_folds: Sequence[str] = DEFAULT_DEVELOPMENT_FOLDS,
) -> dict[str, object]:
    """Compare fixed union/intersection sets without inventing synthetic odds."""
    combined = {
        operator: combine_confidence_selection_frames(
            first, second, first_threshold, second_threshold, operator
        )
        for operator in ("first", "second", "union", "intersection")
    }
    periods: dict[str, object] = {}
    for period, period_mask in _period_masks(first, development_folds).items():
        period_frames = {
            operator: frame.loc[period_mask]
            for operator, frame in combined.items()
        }
        first_selected = period_frames["first"]["confidence_selection_eligible"]
        second_selected = period_frames["second"]["confidence_selection_eligible"]
        segment_masks = {
            "both": first_selected & second_selected,
            "first_only": first_selected & ~second_selected,
            "second_only": second_selected & ~first_selected,
            "neither": ~first_selected & ~second_selected,
        }
        periods[period] = {
            "operators": {
                operator: {
                    **selection_mask_metrics(
                        frame, frame["confidence_selection_eligible"]
                    ),
                    "source_reliability": selection_source_reliability(
                        frame, frame["confidence_selection_eligible"]
                    ),
                }
                for operator, frame in period_frames.items()
            },
            "segments": {
                segment: {
                    **selection_mask_metrics(period_frames["first"], mask),
                    "source_reliability": selection_source_reliability(
                        period_frames["first"], mask
                    ),
                }
                for segment, mask in segment_masks.items()
            },
        }
    development_scores = {
        operator: metrics["selection_score"]
        for operator, metrics in periods["development"]["operators"].items()
    }
    selected_operator = max(
        development_scores,
        key=lambda operator: (
            float("-inf")
            if development_scores[operator] is None
            else float(development_scores[operator])
        ),
    )
    composite_scores = {
        operator: development_scores[operator]
        for operator in ("union", "intersection")
    }
    selected_composite = max(
        composite_scores,
        key=lambda operator: (
            float("-inf")
            if composite_scores[operator] is None
            else float(composite_scores[operator])
        ),
    )
    folds: dict[str, object] = {}
    for fold in first["fold"].drop_duplicates():
        fold_mask = first["fold"].eq(fold)
        folds[str(fold)] = {
            operator: selection_mask_metrics(
                frame.loc[fold_mask],
                frame.loc[fold_mask, "confidence_selection_eligible"],
            )
            for operator, frame in combined.items()
        }

    def fold_wins(candidate: str, parent: str, metric: str) -> dict[str, int]:
        candidate_wins = 0
        parent_wins = 0
        ties = 0
        for fold_metrics in folds.values():
            candidate_value = fold_metrics[candidate][metric]
            parent_value = fold_metrics[parent][metric]
            if candidate_value is None and parent_value is None:
                ties += 1
            elif parent_value is None or (
                candidate_value is not None and candidate_value > parent_value
            ):
                candidate_wins += 1
            elif candidate_value is None or parent_value > candidate_value:
                parent_wins += 1
            else:
                ties += 1
        return {candidate: candidate_wins, parent: parent_wins, "ties": ties}

    return {
        "format_version": 1,
        "first_name": first_name,
        "second_name": second_name,
        "first_threshold": first_threshold,
        "second_threshold": second_threshold,
        "development_folds": list(development_folds),
        "selection_score": "sqrt(coverage) * (Wilson95Lower(accuracy) - 0.50)",
        "confirmation_usage": "audit only",
        "development_selected_operator": selected_operator,
        "development_selected_composite": selected_composite,
        "periods": periods,
        "folds": folds,
        "fold_wins": {
            "union_vs_second_accuracy": fold_wins("union", "second", "accuracy"),
            "union_vs_second_selection_score": fold_wins(
                "union", "second", "selection_score"
            ),
            "intersection_vs_first_accuracy": fold_wins(
                "intersection", "first", "accuracy"
            ),
            "intersection_vs_first_selection_score": fold_wins(
                "intersection", "first", "selection_score"
            ),
        },
    }


def pairwise_confidence_complementarity(
    candidates: Mapping[str, tuple[pd.DataFrame, float]],
    development_folds: Sequence[str] = DEFAULT_DEVELOPMENT_FOLDS,
) -> dict[str, object]:
    """Screen fixed candidate selection sets using development evidence only."""
    if len(candidates) < 2:
        raise ValueError("at least two confidence candidates are required")
    names = list(candidates)
    reference = candidates[names[0]][0]
    masks: dict[str, pd.Series] = {}
    thresholds: dict[str, float] = {}
    for name, (frame, threshold) in candidates.items():
        assert_aligned(reference, frame, name)
        if not np.array_equal(
            reference["correct"].to_numpy(dtype="bool"),
            frame["correct"].to_numpy(dtype="bool"),
        ):
            raise ValueError("confidence candidates must preserve the same direction")
        thresholds[name] = float(threshold)
        masks[name] = _selection_mask(frame, threshold)

    period_masks = _period_masks(reference, development_folds)
    pairs: list[dict[str, object]] = []

    def score_or_negative_infinity(value: object) -> float:
        return float("-inf") if value is None else float(value)

    for first_name, second_name in combinations(names, 2):
        first_selected = masks[first_name]
        second_selected = masks[second_name]
        operators = {
            "first": first_selected,
            "second": second_selected,
            "union": first_selected | second_selected,
            "intersection": first_selected & second_selected,
        }
        segments = {
            "both": first_selected & second_selected,
            "first_only": first_selected & ~second_selected,
            "second_only": second_selected & ~first_selected,
            "neither": ~first_selected & ~second_selected,
        }
        periods: dict[str, object] = {}
        for period, period_mask in period_masks.items():
            period_frame = reference.loc[period_mask]
            operator_metrics = {
                operator: selection_mask_metrics(
                    period_frame, selected.loc[period_mask]
                )
                for operator, selected in operators.items()
            }
            segment_metrics = {
                segment: selection_mask_metrics(
                    period_frame, selected.loc[period_mask]
                )
                for segment, selected in segments.items()
            }
            both_rows = segment_metrics["both"]["rows"]
            union_rows = operator_metrics["union"]["rows"]
            periods[period] = {
                "operators": operator_metrics,
                "segments": segment_metrics,
                "jaccard": (
                    float(both_rows / union_rows) if union_rows else None
                ),
            }

        def screen_period(period: str) -> dict[str, object]:
            period_operators = periods[period]["operators"]
            period_segments = periods[period]["segments"]
            parent_score = max(
                score_or_negative_infinity(
                    period_operators["first"]["selection_score"]
                ),
                score_or_negative_infinity(
                    period_operators["second"]["selection_score"]
                ),
            )
            union_score = period_operators["union"]["selection_score"]
            union_gain = (
                None if union_score is None else float(union_score) - parent_score
            )
            exclusive_edges = {
                segment: bool(
                    period_segments[segment]["wilson_lower"] is not None
                    and float(period_segments[segment]["wilson_lower"]) > 0.5
                )
                for segment in ("first_only", "second_only")
            }
            return {
                "union_score_gain_over_better_parent": union_gain,
                "exclusive_edge_confirmed": exclusive_edges,
                "passed": bool(
                    union_gain is not None
                    and union_gain > 0
                    and all(exclusive_edges.values())
                ),
            }

        development_screen = screen_period("development")
        confirmation_audit = screen_period("confirmation")
        pairs.append(
            {
                "first_name": first_name,
                "second_name": second_name,
                "first_threshold": thresholds[first_name],
                "second_threshold": thresholds[second_name],
                "periods": periods,
                "development_screen": development_screen,
                "confirmation_audit": confirmation_audit,
            }
        )

    ranked_pairs = sorted(
        pairs,
        key=lambda pair: (
            bool(pair["development_screen"]["passed"]),
            score_or_negative_infinity(
                pair["development_screen"]["union_score_gain_over_better_parent"]
            ),
        ),
        reverse=True,
    )
    eligible_pairs = [
        pair for pair in ranked_pairs if pair["development_screen"]["passed"]
    ]
    return {
        "format_version": 1,
        "development_folds": list(development_folds),
        "confirmation_usage": "audit only; never used for pair selection",
        "selection_score": "sqrt(coverage) * (Wilson95Lower(accuracy) - 0.50)",
        "eligibility": {
            "union_score_gain_over_better_parent": "> 0 on development",
            "first_only_wilson_lower": "> 0.5 on development",
            "second_only_wilson_lower": "> 0.5 on development",
        },
        "candidates": {
            name: {"threshold": thresholds[name]} for name in names
        },
        "development_selected_pair": (
            {
                "first_name": eligible_pairs[0]["first_name"],
                "second_name": eligible_pairs[0]["second_name"],
            }
            if eligible_pairs
            else None
        ),
        "pairs": ranked_pairs,
    }


def assert_aligned(
    reference: pd.DataFrame, candidate: pd.DataFrame, candidate_id: str
) -> None:
    keys = ["fold", "timestamp", "target_up"]
    if len(reference) != len(candidate) or not reference[keys].equals(candidate[keys]):
        raise ValueError(f"{candidate_id} predictions do not align with baseline")


def probability_metrics(frame: pd.DataFrame) -> dict[str, float | int]:
    metrics = evaluate_probabilities(
        frame["target_up"].to_numpy(dtype="int8"),
        frame["probability_up"].to_numpy(dtype="float64"),
    )
    return {
        "rows": len(frame),
        "accuracy": metrics["accuracy"],
        "brier_score": metrics["brier_score"],
        "log_loss": metrics["log_loss"],
        "expected_calibration_error": metrics["expected_calibration_error"],
    }


def lane_metrics(
    frame: pd.DataFrame, threshold: float
) -> dict[str, float | int | None]:
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
    successes = int(selected["correct"].sum())
    lower = wilson_accuracy_lower_bound(successes, len(selected))
    return {
        "rows": len(selected),
        "coverage": coverage,
        "accuracy": float(successes / len(selected)),
        "wilson_lower": lower,
        "selection_score": float(np.sqrt(coverage) * (lower - 0.5)),
    }


def reliability_metrics(frame: pd.DataFrame) -> dict[str, float | int | bool | None]:
    """Summarize whether mean stated confidence matches observed correctness."""
    rows = len(frame)
    if rows == 0:
        return {
            "rows": 0,
            "accuracy": None,
            "mean_confidence": None,
            "brier_score": None,
            "log_loss": None,
            "expected_calibration_error": None,
            "calibration_gap": None,
            "absolute_calibration_gap": None,
            "wilson_lower": None,
            "wilson_upper": None,
            "locally_consistent": None,
            "edge_confirmed": None,
        }
    confidence = frame["confidence"].to_numpy(dtype="float64")
    if not np.isfinite(confidence).all() or np.any((confidence < 0) | (confidence > 1)):
        raise ValueError("confidence must be finite and between 0 and 1")
    successes = int(frame["correct"].sum())
    accuracy = successes / rows
    mean_confidence = float(confidence.mean())
    lower = wilson_accuracy_lower_bound(successes, rows)
    upper = 1 - wilson_accuracy_lower_bound(rows - successes, rows)
    gap = accuracy - mean_confidence
    return {
        "rows": rows,
        "accuracy": float(accuracy),
        "mean_confidence": mean_confidence,
        "brier_score": float(brier_score_loss(frame["correct"], confidence)),
        "log_loss": float(log_loss(frame["correct"], confidence, labels=[0, 1])),
        "expected_calibration_error": float(
            confidence_calibration_error(frame["correct"], confidence)
        ),
        "calibration_gap": float(gap),
        "absolute_calibration_gap": float(abs(gap)),
        "wilson_lower": lower,
        "wilson_upper": upper,
        "locally_consistent": bool(lower <= mean_confidence <= upper),
        "edge_confirmed": bool(lower > 0.5),
    }


def _validate_reliability_grid(
    edges: Sequence[float], thresholds: Sequence[float]
) -> tuple[tuple[float, ...], tuple[float, ...]]:
    resolved_edges = tuple(float(value) for value in edges)
    resolved_thresholds = tuple(float(value) for value in thresholds)
    if (
        len(resolved_edges) < 2
        or resolved_edges[0] != 0.5
        or resolved_edges[-1] != 1.0
        or any(left >= right for left, right in zip(resolved_edges, resolved_edges[1:]))
    ):
        raise ValueError("reliability edges must increase strictly from 0.5 to 1.0")
    if not resolved_thresholds or any(
        value <= 0.5 or value >= 1 for value in resolved_thresholds
    ):
        raise ValueError("reliability thresholds must be between 0.5 and 1")
    if any(left >= right for left, right in zip(resolved_thresholds, resolved_thresholds[1:])):
        raise ValueError("reliability thresholds must increase strictly")
    return resolved_edges, resolved_thresholds


def confidence_reliability_profile(
    frame: pd.DataFrame,
    edges: Sequence[float] = DEFAULT_RELIABILITY_EDGES,
    thresholds: Sequence[float] = DEFAULT_RELIABILITY_THRESHOLDS,
) -> dict[str, object]:
    """Evaluate fixed disjoint confidence bands and cumulative high-confidence lanes."""
    resolved_edges, resolved_thresholds = _validate_reliability_grid(edges, thresholds)
    overall = reliability_metrics(frame)
    below_first_edge = frame["confidence"].lt(resolved_edges[0])
    bands: list[dict[str, object]] = []
    populated_accuracies: list[float] = []
    for index, (lower, upper) in enumerate(zip(resolved_edges, resolved_edges[1:])):
        is_last = index == len(resolved_edges) - 2
        mask = frame["confidence"].ge(lower) & (
            frame["confidence"].le(upper)
            if is_last
            else frame["confidence"].lt(upper)
        )
        metrics = reliability_metrics(frame.loc[mask])
        if metrics["accuracy"] is not None:
            populated_accuracies.append(float(metrics["accuracy"]))
        bands.append(
            {
                "lower": lower,
                "upper": upper,
                "upper_inclusive": is_last,
                "coverage": float(mask.mean()) if len(frame) else 0.0,
                **metrics,
            }
        )
    violations = sum(
        current < previous
        for previous, current in zip(populated_accuracies, populated_accuracies[1:])
    )
    cumulative = []
    for threshold in resolved_thresholds:
        mask = frame["confidence"].ge(threshold)
        cumulative.append(
            {
                "threshold": threshold,
                "coverage": float(mask.mean()) if len(frame) else 0.0,
                **reliability_metrics(frame.loc[mask]),
            }
        )
    return {
        "overall": overall,
        "below_first_edge": {
            "upper": resolved_edges[0],
            "coverage": float(below_first_edge.mean()) if len(frame) else 0.0,
            **reliability_metrics(frame.loc[below_first_edge]),
        },
        "bands": bands,
        "cumulative_thresholds": cumulative,
        "monotonicity": {
            "evaluated_adjacent_pairs": max(len(populated_accuracies) - 1, 0),
            "accuracy_decrease_violations": int(violations),
            "observed_accuracy_nondecreasing": bool(violations == 0),
        },
    }


def compare_confidence_reliability_frames(
    first: pd.DataFrame,
    second: pd.DataFrame,
    first_name: str = "first",
    second_name: str = "second",
    development_folds: Sequence[str] = DEFAULT_DEVELOPMENT_FOLDS,
    edges: Sequence[float] = DEFAULT_RELIABILITY_EDGES,
    thresholds: Sequence[float] = DEFAULT_RELIABILITY_THRESHOLDS,
) -> dict[str, object]:
    """Compare fixed reliability bands without optimizing them on confirmation data."""
    resolved_edges, resolved_thresholds = _validate_reliability_grid(edges, thresholds)
    assert_aligned(first, second, second_name)
    periods: dict[str, object] = {}
    for period, mask in _period_masks(first, development_folds).items():
        first_period = first.loc[mask]
        second_period = second.loc[mask]
        periods[period] = {
            first_name: confidence_reliability_profile(
                first_period, resolved_edges, resolved_thresholds
            ),
            second_name: confidence_reliability_profile(
                second_period, resolved_edges, resolved_thresholds
            ),
            "direction_agreement_rate": float(
                (
                    first_period["correct"].to_numpy(dtype="bool")
                    == second_period["correct"].to_numpy(dtype="bool")
                ).mean()
            ),
        }
    return {
        "format_version": 1,
        "development_folds": list(development_folds),
        "fixed_band_edges": list(resolved_edges),
        "fixed_cumulative_thresholds": list(resolved_thresholds),
        "periods": periods,
    }


def confidence_reliability_subgroups(
    frame: pd.DataFrame,
    group_columns: Sequence[str],
    development_folds: Sequence[str] = DEFAULT_DEVELOPMENT_FOLDS,
    edges: Sequence[float] = DEFAULT_RELIABILITY_EDGES,
    thresholds: Sequence[float] = DEFAULT_RELIABILITY_THRESHOLDS,
) -> dict[str, object]:
    """Audit fixed reliability profiles within predeclared categorical groups."""
    resolved_edges, resolved_thresholds = _validate_reliability_grid(edges, thresholds)
    resolved_groups = tuple(str(column) for column in group_columns)
    if not resolved_groups:
        raise ValueError("at least one reliability subgroup column is required")
    missing = sorted(set(resolved_groups) - set(frame.columns))
    if missing:
        raise ValueError(
            f"reliability subgroup columns are missing: {', '.join(missing)}"
        )

    periods: dict[str, object] = {}
    for period, mask in _period_masks(frame, development_folds).items():
        period_frame = frame.loc[mask]
        groups: list[dict[str, object]] = []
        grouped = period_frame.groupby(list(resolved_groups), sort=True, dropna=False)
        for group_key, group_frame in grouped:
            keys = group_key if isinstance(group_key, tuple) else (group_key,)
            labels: dict[str, object] = {}
            for column, value in zip(resolved_groups, keys):
                if pd.isna(value):
                    labels[column] = None
                elif isinstance(value, np.generic):
                    labels[column] = value.item()
                else:
                    labels[column] = value
            groups.append(
                {
                    "group": labels,
                    "period_coverage": float(len(group_frame) / len(period_frame))
                    if len(period_frame)
                    else 0.0,
                    "profile": confidence_reliability_profile(
                        group_frame,
                        resolved_edges,
                        resolved_thresholds,
                    ),
                }
            )
        periods[period] = {
            "rows": len(period_frame),
            "groups": groups,
        }
    return {
        "format_version": 1,
        "development_folds": list(development_folds),
        "group_columns": list(resolved_groups),
        "fixed_band_edges": list(resolved_edges),
        "fixed_cumulative_thresholds": list(resolved_thresholds),
        "periods": periods,
    }


def _relative_path(path: Path, project_root: Path) -> str:
    try:
        return path.relative_to(project_root).as_posix()
    except ValueError:
        return path.as_posix()


def discover_candidate_specs(
    config_dir: Path, project_root: Path, timeframe: int
) -> list[CandidateSpec]:
    specs: list[CandidateSpec] = []
    pattern = f"m{timeframe}_*confidence*.json"
    for path in sorted(config_dir.glob(pattern)):
        config = json.loads(path.read_text(encoding="utf-8"))
        candidate = config.get("confidence_candidate")
        if candidate is None:
            candidate = config.get("confidence_shadow")
        if not isinstance(candidate, dict):
            raise ValueError(f"{path} has no confidence_candidate/confidence_shadow")
        threshold = candidate.get("fixed_confidence_threshold")
        if threshold is None:
            raise ValueError(f"{path} has no explicit fixed_confidence_threshold")
        threshold = float(threshold)
        if not 0.5 < threshold < 1.0:
            raise ValueError(f"{path} has invalid fixed_confidence_threshold")
        experiments = config.get("experiments", {})
        prediction_value = experiments.get("direction_preserving_blend")
        if prediction_value is None:
            prediction_value = experiments.get("mean_edge_direction_preserved")
        if prediction_value is None:
            prediction_value = experiments.get("predictions")
        if prediction_value is None:
            prediction_value = experiments.get("final_confidence_blend")
        if not prediction_value:
            raise ValueError(f"{path} has no direction-preserving prediction path")
        prediction_dir = project_root / str(prediction_value)
        if not prediction_dir.is_dir():
            raise FileNotFoundError(prediction_dir)
        status = str(config.get("status", ""))
        specs.append(
            CandidateSpec(
                candidate_id=path.stem.removeprefix(f"m{timeframe}_"),
                config_path=path,
                prediction_dir=prediction_dir,
                status=status,
                threshold=threshold,
                role=confidence_role(threshold),
                eligible=status.startswith("forward_candidate"),
            )
        )
    if not specs:
        raise ValueError(f"no confidence configs matched {config_dir / pattern}")
    return specs


def _period_masks(
    baseline: pd.DataFrame, development_folds: Sequence[str]
) -> dict[str, pd.Series]:
    development = baseline["fold"].isin(set(development_folds))
    return {
        "development": development,
        "confirmation": ~development,
        "all": pd.Series(True, index=baseline.index),
    }


def _fold_stability(
    baseline: pd.DataFrame, candidate: pd.DataFrame, threshold: float
) -> dict[str, object]:
    accuracy_improvements = 0
    score_improvements = 0
    proper_improvements = {
        "brier_score": 0,
        "log_loss": 0,
        "expected_calibration_error": 0,
    }
    folds = baseline["fold"].drop_duplicates().tolist()
    for fold in folds:
        mask = baseline["fold"].eq(fold)
        baseline_lane = lane_metrics(baseline.loc[mask], threshold)
        candidate_lane = lane_metrics(candidate.loc[mask], threshold)
        if (
            baseline_lane["accuracy"] is not None
            and candidate_lane["accuracy"] is not None
            and candidate_lane["accuracy"] > baseline_lane["accuracy"]
        ):
            accuracy_improvements += 1
        if (
            baseline_lane["selection_score"] is not None
            and candidate_lane["selection_score"] is not None
            and candidate_lane["selection_score"] > baseline_lane["selection_score"]
        ):
            score_improvements += 1
        baseline_probability = probability_metrics(baseline.loc[mask])
        candidate_probability = probability_metrics(candidate.loc[mask])
        for metric in proper_improvements:
            proper_improvements[metric] += int(
                candidate_probability[metric] < baseline_probability[metric]
            )
    return {
        "evaluated_folds": len(folds),
        "lane_accuracy_improved_folds": accuracy_improvements,
        "lane_selection_score_improved_folds": score_improvements,
        "proper_score_improved_folds": proper_improvements,
    }


def _historical_gate(candidate: dict[str, object]) -> dict[str, object]:
    periods = candidate["periods"]
    stability = candidate["fold_stability"]
    checks = {
        "development_lane_accuracy_above_baseline": (
            periods["development"]["candidate_lane"]["accuracy"]
            > periods["development"]["baseline_lane"]["accuracy"]
        ),
        "development_selection_score_above_baseline": (
            periods["development"]["candidate_lane"]["selection_score"]
            > periods["development"]["baseline_lane"]["selection_score"]
        ),
        "confirmation_lane_accuracy_above_baseline": (
            periods["confirmation"]["candidate_lane"]["accuracy"]
            > periods["confirmation"]["baseline_lane"]["accuracy"]
        ),
        "confirmation_selection_score_above_baseline": (
            periods["confirmation"]["candidate_lane"]["selection_score"]
            > periods["confirmation"]["baseline_lane"]["selection_score"]
        ),
        "confirmation_brier_not_above_baseline": (
            periods["confirmation"]["candidate_probability"]["brier_score"]
            <= periods["confirmation"]["baseline_probability"]["brier_score"]
        ),
        "confirmation_log_loss_not_above_baseline": (
            periods["confirmation"]["candidate_probability"]["log_loss"]
            <= periods["confirmation"]["baseline_probability"]["log_loss"]
        ),
        "lane_accuracy_improved_at_least_5_of_7_folds": (
            stability["lane_accuracy_improved_folds"] >= 5
        ),
        "lane_score_improved_at_least_5_of_7_folds": (
            stability["lane_selection_score_improved_folds"] >= 5
        ),
        "brier_improved_at_least_4_of_7_folds": (
            stability["proper_score_improved_folds"]["brier_score"] >= 4
        ),
        "log_loss_improved_at_least_4_of_7_folds": (
            stability["proper_score_improved_folds"]["log_loss"] >= 4
        ),
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "meaning": "historical robustness only; a fresh untouched forward period remains required for promotion",
    }


def _dominates(first: dict[str, object], second: dict[str, object]) -> bool:
    first_lane = first["periods"]["development"]["candidate_lane"]
    second_lane = second["periods"]["development"]["candidate_lane"]
    coverage_not_worse = first_lane["coverage"] >= second_lane["coverage"]
    accuracy_not_worse = first_lane["accuracy"] >= second_lane["accuracy"]
    strictly_better = (
        first_lane["coverage"] > second_lane["coverage"]
        or first_lane["accuracy"] > second_lane["accuracy"]
    )
    return coverage_not_worse and accuracy_not_worse and strictly_better


def _rank_roles(candidates: list[dict[str, object]]) -> dict[str, object]:
    output: dict[str, object] = {}
    for role in ("broad", "balanced", "selective", "precision"):
        members = [candidate for candidate in candidates if candidate["role"] == role]
        eligible = [candidate for candidate in members if candidate["eligible"]]
        shadows = [candidate["candidate_id"] for candidate in members if not candidate["eligible"]]
        if not eligible:
            output[role] = {
                "champion": None,
                "challengers": [],
                "dominated": [],
                "shadows": shadows,
            }
            continue
        champion = max(
            eligible,
            key=lambda candidate: candidate["periods"]["development"][
                "candidate_lane"
            ]["selection_score"],
        )
        development_accuracy_leader = max(
            eligible,
            key=lambda candidate: candidate["periods"]["development"][
                "candidate_lane"
            ]["accuracy"],
        )
        development_coverage_leader = max(
            eligible,
            key=lambda candidate: candidate["periods"]["development"][
                "candidate_lane"
            ]["coverage"],
        )
        confirmation_accuracy_leader = max(
            eligible,
            key=lambda candidate: candidate["periods"]["confirmation"][
                "candidate_lane"
            ]["accuracy"],
        )
        dominated = [
            candidate
            for candidate in eligible
            if any(
                _dominates(other, candidate)
                for other in eligible
                if other is not candidate
            )
        ]
        dominated_ids = {candidate["candidate_id"] for candidate in dominated}
        challengers = [
            candidate["candidate_id"]
            for candidate in eligible
            if candidate is not champion
            and candidate["candidate_id"] not in dominated_ids
        ]
        output[role] = {
            "champion": champion["candidate_id"],
            "champion_historical_gate_passed": champion["historical_gate"]["passed"],
            "development_accuracy_leader": development_accuracy_leader[
                "candidate_id"
            ],
            "development_coverage_leader": development_coverage_leader[
                "candidate_id"
            ],
            "confirmation_accuracy_leader_audit_only": confirmation_accuracy_leader[
                "candidate_id"
            ],
            "challengers": challengers,
            "dominated": sorted(dominated_ids),
            "shadows": shadows,
        }
    return output


def build_candidate_registry(
    project_root: Path,
    config_dir: Path,
    baseline_dirs: Sequence[Path],
    timeframe: int = 15,
    development_folds: Sequence[str] = DEFAULT_DEVELOPMENT_FOLDS,
) -> dict[str, object]:
    project_root = project_root.resolve()
    config_dir = config_dir.resolve()
    resolved_baseline_dirs = [path.resolve() for path in baseline_dirs]
    baseline = read_prediction_sets(resolved_baseline_dirs, timeframe)
    masks = _period_masks(baseline, development_folds)
    specs = discover_candidate_specs(config_dir, project_root, timeframe)
    candidates: list[dict[str, object]] = []
    for spec in specs:
        prediction = read_prediction_sets([spec.prediction_dir], timeframe)
        assert_aligned(baseline, prediction, spec.candidate_id)
        periods = {}
        for period, mask in masks.items():
            baseline_period = baseline.loc[mask]
            candidate_period = prediction.loc[mask]
            periods[period] = {
                "baseline_probability": probability_metrics(baseline_period),
                "candidate_probability": probability_metrics(candidate_period),
                "baseline_lane": lane_metrics(baseline_period, spec.threshold),
                "candidate_lane": lane_metrics(candidate_period, spec.threshold),
            }
        candidate: dict[str, object] = {
            "candidate_id": spec.candidate_id,
            "config": _relative_path(spec.config_path, project_root),
            "prediction_dir": _relative_path(spec.prediction_dir, project_root),
            "status": spec.status,
            "eligible": spec.eligible,
            "role": spec.role,
            "fixed_confidence_threshold": spec.threshold,
            "periods": periods,
            "fold_stability": _fold_stability(
                baseline, prediction, spec.threshold
            ),
        }
        candidate["historical_gate"] = _historical_gate(candidate)
        candidates.append(candidate)
    roles = _rank_roles(candidates)
    for candidate in candidates:
        role_result = roles[candidate["role"]]
        if not candidate["eligible"]:
            candidate["registry_class"] = "shadow"
        elif candidate["candidate_id"] == role_result["champion"]:
            candidate["registry_class"] = "champion"
        elif candidate["candidate_id"] in role_result["dominated"]:
            candidate["registry_class"] = "dominated"
        else:
            candidate["registry_class"] = "challenger"
    return {
        "format_version": 1,
        "scope": f"M{timeframe} direction-preserving confidence candidates",
        "selection_policy": {
            "development_folds": list(development_folds),
            "confirmation_folds": [
                str(fold)
                for fold in baseline["fold"].drop_duplicates()
                if fold not in set(development_folds)
            ],
            "role_boundaries": {
                "broad": "confidence <= 0.52",
                "balanced": "0.52 < confidence < 0.53",
                "selective": "0.53 <= confidence <= 0.54",
                "precision": "confidence > 0.54",
            },
            "champion_objective": "maximum development selection score among forward candidates within each role",
            "selection_score": "sqrt(coverage) * (Wilson95Lower(accuracy) - 0.50)",
            "pareto_axes": ["development coverage", "development accuracy"],
            "confirmation_usage": "audit only; never used to choose the champion",
        },
        "baseline_dirs": [
            _relative_path(path, project_root) for path in resolved_baseline_dirs
        ],
        "rows": len(baseline),
        "candidate_count": len(candidates),
        "roles": roles,
        "candidates": candidates,
    }


def compare_fixed_candidate_frames(
    first: pd.DataFrame,
    second: pd.DataFrame,
    threshold: float,
    first_name: str = "first",
    second_name: str = "second",
    development_folds: Sequence[str] = DEFAULT_DEVELOPMENT_FOLDS,
    second_threshold: float | None = None,
) -> dict[str, object]:
    if not 0.5 <= threshold < 1:
        raise ValueError("threshold must be between 0.5 inclusive and 1")
    resolved_second_threshold = (
        threshold if second_threshold is None else second_threshold
    )
    if not 0.5 <= resolved_second_threshold < 1:
        raise ValueError(
            "second_threshold must be between 0.5 inclusive and 1"
        )
    assert_aligned(first, second, second_name)
    masks = _period_masks(first, development_folds)
    periods: dict[str, object] = {}
    for period, mask in masks.items():
        first_period = first.loc[mask]
        second_period = second.loc[mask]
        first_selected = first_period["confidence"].ge(threshold)
        second_selected = second_period["confidence"].ge(
            resolved_second_threshold
        )
        both = first_selected & second_selected
        union = first_selected | second_selected
        periods[period] = {
            first_name: {
                "probability": probability_metrics(first_period),
                "lane": lane_metrics(first_period, threshold),
            },
            second_name: {
                "probability": probability_metrics(second_period),
                "lane": lane_metrics(second_period, resolved_second_threshold),
            },
            "selection_overlap": {
                "both_rows": int(both.sum()),
                "first_only_rows": int((first_selected & ~second_selected).sum()),
                "second_only_rows": int((second_selected & ~first_selected).sum()),
                "union_rows": int(union.sum()),
                "jaccard": float(both.sum() / union.sum()) if union.any() else None,
            },
        }
    fold_comparison: dict[str, object] = {}
    first_accuracy_wins = 0
    first_score_wins = 0
    second_accuracy_wins = 0
    second_score_wins = 0
    def compare_optional(
        first_value: float | int | None, second_value: float | int | None
    ) -> int:
        if first_value is None and second_value is None:
            return 0
        if first_value is None:
            return -1
        if second_value is None:
            return 1
        return int(first_value > second_value) - int(first_value < second_value)

    for fold in first["fold"].drop_duplicates():
        mask = first["fold"].eq(fold)
        first_lane = lane_metrics(first.loc[mask], threshold)
        second_lane = lane_metrics(second.loc[mask], resolved_second_threshold)
        accuracy_comparison = compare_optional(
            first_lane["accuracy"], second_lane["accuracy"]
        )
        score_comparison = compare_optional(
            first_lane["selection_score"], second_lane["selection_score"]
        )
        first_accuracy_win = accuracy_comparison > 0
        first_score_win = score_comparison > 0
        second_accuracy_win = accuracy_comparison < 0
        second_score_win = score_comparison < 0
        first_accuracy_wins += int(first_accuracy_win)
        first_score_wins += int(first_score_win)
        second_accuracy_wins += int(second_accuracy_win)
        second_score_wins += int(second_score_win)
        fold_comparison[str(fold)] = {
            first_name: first_lane,
            second_name: second_lane,
            "accuracy_winner": (
                first_name
                if first_accuracy_win
                else second_name if second_accuracy_win else "tie"
            ),
            "selection_score_winner": (
                first_name
                if first_score_win
                else second_name if second_score_win else "tie"
            ),
        }
    return {
        "fixed_confidence_threshold": threshold,
        "first_threshold": threshold,
        "second_threshold": resolved_second_threshold,
        "development_folds": list(development_folds),
        "periods": periods,
        "fold_wins": {
            first_name: {
                "accuracy": first_accuracy_wins,
                "selection_score": first_score_wins,
            },
            second_name: {
                "accuracy": second_accuracy_wins,
                "selection_score": second_score_wins,
            },
            "ties": {
                "accuracy": len(fold_comparison)
                - first_accuracy_wins
                - second_accuracy_wins,
                "selection_score": len(fold_comparison)
                - first_score_wins
                - second_score_wins,
            },
        },
        "fold_comparison": fold_comparison,
    }
