from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np
import pandas as pd

from trade_data.next_bar_registry import (
    DEFAULT_DEVELOPMENT_FOLDS,
    assert_aligned,
    lane_metrics,
    probability_metrics,
    read_prediction_sets,
)


DEFAULT_REGIMES = ("low", "normal", "high")
SOURCE_SPECIFIC_COLUMNS = (
    "baseline_probability_up",
    "candidate_probability_up",
    "ensemble_candidate_weight",
    "ensemble_preserve_baseline_direction",
)


def _refresh_prediction_columns(frame: pd.DataFrame) -> pd.DataFrame:
    output = frame.copy()
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
    return output


def _validate_inputs(
    baseline: pd.DataFrame,
    candidates: Mapping[str, pd.DataFrame],
    regime_column: str,
    regimes: Sequence[str],
) -> None:
    if not candidates:
        raise ValueError("regime router requires at least one candidate")
    if regime_column not in baseline:
        raise ValueError(f"baseline is missing regime column: {regime_column}")
    if not regimes or len(set(regimes)) != len(regimes):
        raise ValueError("regimes must be a non-empty unique sequence")
    observed = set(baseline[regime_column].astype(str).unique())
    expected = set(regimes)
    if observed != expected:
        raise ValueError(
            f"regime values do not match: expected {sorted(expected)}, "
            f"observed {sorted(observed)}"
        )
    for candidate_id, frame in candidates.items():
        assert_aligned(baseline, frame, candidate_id)
        if regime_column not in frame:
            raise ValueError(
                f"{candidate_id} is missing regime column: {regime_column}"
            )
        if not baseline[regime_column].astype(str).equals(
            frame[regime_column].astype(str)
        ):
            raise ValueError(f"{candidate_id} regime labels do not align with baseline")
        probability = frame["probability_up"].to_numpy(dtype="float64")
        if not np.isfinite(probability).all() or np.any(
            (probability < 0) | (probability > 1)
        ):
            raise ValueError(
                f"{candidate_id} probabilities must be finite and within [0, 1]"
            )


def _candidate_accuracy(frame: pd.DataFrame, mask: pd.Series) -> dict[str, float | int]:
    rows = int(mask.sum())
    if rows == 0:
        raise ValueError("candidate selection partition is empty")
    correct = frame.loc[mask, "probability_up"].ge(0.5).eq(
        frame.loc[mask, "target_up"].astype("int8")
    )
    return {"rows": rows, "correct": int(correct.sum()), "accuracy": float(correct.mean())}


def _select_winner(
    candidates: Mapping[str, pd.DataFrame], mask: pd.Series
) -> tuple[str, dict[str, dict[str, float | int]]]:
    metrics = {
        candidate_id: _candidate_accuracy(frame, mask)
        for candidate_id, frame in candidates.items()
    }
    winner = max(
        sorted(candidates),
        key=lambda candidate_id: (metrics[candidate_id]["accuracy"], candidate_id),
    )
    return winner, metrics


def _route_rows(
    baseline: pd.DataFrame,
    candidates: Mapping[str, pd.DataFrame],
    selections: Mapping[tuple[str | None, str], str],
    mode: str,
    regime_column: str,
) -> pd.DataFrame:
    output = baseline.copy()
    output = output.drop(
        columns=[column for column in SOURCE_SPECIFIC_COLUMNS if column in output],
        errors="ignore",
    )
    output["router_candidate_id"] = ""
    output["router_selection_mode"] = mode
    fold_specific = any(fold is not None for fold, _ in selections)
    for (fold, regime), candidate_id in selections.items():
        mask = output[regime_column].astype(str).eq(regime)
        if fold_specific:
            mask &= output["fold"].astype(str).eq(str(fold))
        candidate = candidates[candidate_id]
        output.loc[mask, "probability_up"] = candidate.loc[
            mask, "probability_up"
        ].to_numpy(dtype="float64")
        if "raw_probability_up" in output and "raw_probability_up" in candidate:
            output.loc[mask, "raw_probability_up"] = candidate.loc[
                mask, "raw_probability_up"
            ].to_numpy(dtype="float64")
        output.loc[mask, "router_candidate_id"] = candidate_id
    if output["router_candidate_id"].eq("").any():
        raise ValueError("regime selections did not cover every prediction row")
    return _refresh_prediction_columns(output)


def _period_metrics(
    frame: pd.DataFrame,
    development_folds: Sequence[str],
    confidence_threshold: float,
    evaluation: pd.Series | None = None,
) -> dict[str, object]:
    development = frame["fold"].astype(str).isin(set(development_folds))
    if evaluation is None:
        evaluation = pd.Series(True, index=frame.index)
    masks = {
        "development": development & evaluation,
        "confirmation": ~development & evaluation,
        "all": evaluation,
    }
    return {
        period: {
            "probability": probability_metrics(frame.loc[mask]),
            "confidence_0515": lane_metrics(
                frame.loc[mask], confidence_threshold
            ),
        }
        for period, mask in masks.items()
        if mask.any()
    }


def build_fixed_regime_route(
    baseline: pd.DataFrame,
    candidates: Mapping[str, pd.DataFrame],
    development_folds: Sequence[str] = DEFAULT_DEVELOPMENT_FOLDS,
    regime_column: str = "volatility_regime",
    regimes: Sequence[str] = DEFAULT_REGIMES,
    confidence_threshold: float = 0.515,
) -> tuple[dict[str, object], pd.DataFrame]:
    """Choose one candidate per regime on development folds, then freeze the map."""
    if not 0.5 <= confidence_threshold < 1:
        raise ValueError("confidence threshold must be between 0.5 inclusive and 1")
    _validate_inputs(baseline, candidates, regime_column, regimes)
    development = baseline["fold"].astype(str).isin(set(development_folds))
    selections: dict[tuple[str | None, str], str] = {}
    selection_report: dict[str, object] = {}
    for regime in regimes:
        mask = development & baseline[regime_column].astype(str).eq(regime)
        winner, metrics = _select_winner(candidates, mask)
        selections[(None, regime)] = winner
        selection_report[regime] = {
            "selected_candidate": winner,
            "development_candidate_metrics": metrics,
        }
    routed = _route_rows(
        baseline, candidates, selections, "fixed_development", regime_column
    )
    return (
        {
            "mode": "fixed_development",
            "selection_objective": "maximum development direction accuracy within each fixed volatility regime",
            "development_folds": list(development_folds),
            "regime_column": regime_column,
            "regimes": list(regimes),
            "selections": selection_report,
            "periods": _period_metrics(
                routed, development_folds, confidence_threshold
            ),
        },
        routed,
    )


def build_chronological_regime_route(
    baseline: pd.DataFrame,
    candidates: Mapping[str, pd.DataFrame],
    fallback_candidate_id: str,
    development_folds: Sequence[str] = DEFAULT_DEVELOPMENT_FOLDS,
    regime_column: str = "volatility_regime",
    regimes: Sequence[str] = DEFAULT_REGIMES,
    confidence_threshold: float = 0.515,
) -> tuple[dict[str, object], pd.DataFrame]:
    """Choose per-regime candidates for each fold using only earlier OOS folds."""
    if not 0.5 <= confidence_threshold < 1:
        raise ValueError("confidence threshold must be between 0.5 inclusive and 1")
    _validate_inputs(baseline, candidates, regime_column, regimes)
    if fallback_candidate_id not in candidates:
        raise ValueError("fallback candidate is not in the candidate pool")
    fold_order = [
        str(value)
        for value in (
            baseline.groupby("fold", sort=False)["timestamp"].min().sort_values().index
        )
    ]
    selections: dict[tuple[str | None, str], str] = {}
    selection_rows: list[dict[str, object]] = []
    for position, fold in enumerate(fold_order):
        for regime in regimes:
            if position == 0:
                winner = fallback_candidate_id
                metrics: dict[str, object] = {}
            else:
                mask = baseline["fold"].astype(str).isin(fold_order[:position])
                mask &= baseline[regime_column].astype(str).eq(regime)
                winner, metrics = _select_winner(candidates, mask)
            selections[(fold, regime)] = winner
            selection_rows.append(
                {
                    "fold": fold,
                    "regime": regime,
                    "evaluation": position > 0,
                    "calibration_folds": fold_order[:position],
                    "selected_candidate": winner,
                    "prior_candidate_metrics": metrics,
                }
            )
    routed = _route_rows(
        baseline, candidates, selections, "chronological_prior_oos", regime_column
    )
    evaluation = ~routed["fold"].astype(str).eq(fold_order[0])
    routed["router_evaluation"] = evaluation
    return (
        {
            "mode": "chronological_prior_oos",
            "selection_objective": "maximum cumulative prior-OOS direction accuracy within each fixed volatility regime",
            "development_folds": list(development_folds),
            "regime_column": regime_column,
            "regimes": list(regimes),
            "first_fold_policy": f"{fallback_candidate_id} fallback; excluded from nested metrics",
            "folds": selection_rows,
            "periods": _period_metrics(
                routed, development_folds, confidence_threshold, evaluation
            ),
        },
        routed,
    )


def run_regime_router(
    candidate_dirs: Mapping[str, Path],
    output_dir: Path,
    timeframe: int = 1,
    development_folds: Sequence[str] = DEFAULT_DEVELOPMENT_FOLDS,
    fallback_candidate_id: str = "path",
) -> dict[str, object]:
    if fallback_candidate_id not in candidate_dirs:
        raise ValueError("fallback candidate is not in the candidate pool")
    candidates = {
        candidate_id: read_prediction_sets([directory], timeframe)
        for candidate_id, directory in candidate_dirs.items()
    }
    baseline = candidates[fallback_candidate_id]
    fixed_report, fixed = build_fixed_regime_route(
        baseline, candidates, development_folds
    )
    chronological_report, chronological = build_chronological_regime_route(
        baseline,
        candidates,
        fallback_candidate_id,
        development_folds,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    fixed_name = f"m{timeframe}_walk_forward_predictions.parquet"
    chronological_name = f"m{timeframe}_chronological_predictions.parquet"
    fixed.to_parquet(output_dir / fixed_name, index=False)
    chronological.to_parquet(output_dir / chronological_name, index=False)
    report = {
        "format_version": 1,
        "timeframe": timeframe,
        "candidate_dirs": {
            candidate_id: str(directory)
            for candidate_id, directory in candidate_dirs.items()
        },
        "fixed": fixed_report,
        "chronological": chronological_report,
    }
    (output_dir / "router_metrics.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (output_dir / "manifest.json").write_text(
        json.dumps(
            {
                "format_version": 1,
                "kind": "volatility_regime_candidate_router",
                "timeframe": timeframe,
                "fixed_predictions": fixed_name,
                "chronological_predictions": chronological_name,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return report
