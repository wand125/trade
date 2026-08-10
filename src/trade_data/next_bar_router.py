from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np
import pandas as pd

from trade_data.next_bar import wilson_accuracy_lower_bound
from trade_data.next_bar_registry import (
    assert_aligned,
    lane_metrics,
    probability_metrics,
    read_prediction_sets,
)


def selected_lane_metrics(
    frame: pd.DataFrame, selected: pd.Series | np.ndarray
) -> dict[str, float | int | None]:
    mask = np.asarray(selected, dtype="bool")
    if len(mask) != len(frame):
        raise ValueError("selected mask must align with the prediction frame")
    rows = int(mask.sum())
    coverage = float(mask.mean()) if len(mask) else 0.0
    if rows == 0:
        return {
            "rows": 0,
            "coverage": coverage,
            "accuracy": None,
            "wilson_lower": None,
            "selection_score": None,
        }
    successes = int(frame.loc[mask, "correct"].sum())
    lower = wilson_accuracy_lower_bound(successes, rows)
    return {
        "rows": rows,
        "coverage": coverage,
        "accuracy": float(successes / rows),
        "wilson_lower": lower,
        "selection_score": float(np.sqrt(coverage) * (lower - 0.5)),
    }


def _fold_order(frame: pd.DataFrame) -> list[str]:
    return [
        str(value)
        for value in (
            frame.groupby("fold", sort=False)["timestamp"].min().sort_values().index
        )
    ]


def _period_report(
    routed: pd.DataFrame,
    baseline: pd.DataFrame,
    static: pd.DataFrame,
) -> dict[str, object]:
    return {
        "rows": len(routed),
        "baseline": {
            "probability": probability_metrics(baseline),
            "lane": selected_lane_metrics(
                baseline, routed["router_baseline_selected"]
            ),
        },
        "router": {
            "probability": probability_metrics(routed),
            "lane": selected_lane_metrics(routed, routed["router_selected"]),
        },
        "static_champion": {
            "probability": probability_metrics(static),
            "lane": selected_lane_metrics(
                static, routed["router_static_selected"]
            ),
        },
        "router_selection_counts": {
            str(key): int(value)
            for key, value in routed["router_candidate_id"].value_counts().items()
        },
    }


def build_chronological_role_route(
    baseline: pd.DataFrame,
    candidates: Mapping[str, tuple[pd.DataFrame, float]],
    role: str,
    static_champion_id: str,
    fallback_threshold: float,
    development_folds: Sequence[str],
    confirmation_folds: Sequence[str],
) -> tuple[dict[str, object], pd.DataFrame]:
    """Select one fixed candidate per fold using only earlier OOS folds."""
    if not candidates:
        raise ValueError(f"role has no candidates: {role}")
    if static_champion_id not in candidates:
        raise ValueError(f"static champion is not in the candidate pool: {role}")
    if not 0.5 < fallback_threshold < 1:
        raise ValueError("fallback threshold must be between 0.5 and 1")
    for candidate_id, (frame, threshold) in candidates.items():
        if not 0.5 < threshold < 1:
            raise ValueError(f"candidate threshold must be between 0.5 and 1: {candidate_id}")
        assert_aligned(baseline, frame, candidate_id)
        if not baseline["correct"].astype(bool).equals(frame["correct"].astype(bool)):
            raise ValueError(
                f"router candidate must preserve baseline direction: {candidate_id}"
            )

    fold_order = _fold_order(baseline)
    development_names = set(development_folds)
    confirmation_names = set(confirmation_folds)
    static_frame, static_threshold = candidates[static_champion_id]
    routed_folds: list[pd.DataFrame] = []
    baseline_folds: list[pd.DataFrame] = []
    static_folds: list[pd.DataFrame] = []
    selection_rows: list[dict[str, object]] = []

    for position, fold in enumerate(fold_order):
        current_mask = baseline["fold"].astype(str).eq(fold)
        baseline_current = baseline.loc[current_mask].reset_index(drop=True)
        static_current = static_frame.loc[current_mask].reset_index(drop=True)
        if position == 0:
            selected_id = "baseline_fallback"
            selected_threshold = fallback_threshold
            selected_current = baseline_current.copy()
            prior_scores: dict[str, object] = {}
            evaluation = False
        else:
            prior_folds = set(fold_order[:position])
            prior_mask = baseline["fold"].astype(str).isin(prior_folds)
            prior_scores = {}
            for candidate_id, (frame, threshold) in candidates.items():
                metrics = lane_metrics(frame.loc[prior_mask], threshold)
                prior_scores[candidate_id] = {
                    "threshold": threshold,
                    **metrics,
                }
            selected_id = max(
                sorted(candidates),
                key=lambda candidate_id: (
                    float(
                        prior_scores[candidate_id]["selection_score"]
                        if prior_scores[candidate_id]["selection_score"] is not None
                        else -np.inf
                    ),
                    candidate_id,
                ),
            )
            selected_frame, selected_threshold = candidates[selected_id]
            selected_current = selected_frame.loc[current_mask].reset_index(drop=True)
            evaluation = True

        routed = selected_current.copy()
        routed["router_role"] = role
        routed["router_candidate_id"] = selected_id
        routed["router_threshold"] = selected_threshold
        routed["router_selected"] = routed["confidence"].ge(selected_threshold)
        routed["router_evaluation"] = evaluation
        routed["router_baseline_selected"] = baseline_current["confidence"].ge(
            selected_threshold
        )
        routed["router_static_selected"] = static_current["confidence"].ge(
            static_threshold
        )
        routed["router_static_candidate_id"] = static_champion_id
        routed["router_static_threshold"] = static_threshold
        routed_folds.append(routed)
        baseline_folds.append(baseline_current)
        static_folds.append(static_current)
        selection_rows.append(
            {
                "fold": fold,
                "evaluation": evaluation,
                "calibration_folds": fold_order[:position],
                "selected_candidate": selected_id,
                "selected_threshold": selected_threshold,
                "prior_candidate_metrics": prior_scores,
            }
        )

    routed_all = pd.concat(routed_folds, ignore_index=True)
    baseline_all = pd.concat(baseline_folds, ignore_index=True)
    static_all = pd.concat(static_folds, ignore_index=True)
    evaluation_mask = routed_all["router_evaluation"].astype(bool)
    period_masks = {
        "nested_development": evaluation_mask
        & routed_all["fold"].astype(str).isin(development_names),
        "confirmation": evaluation_mask
        & routed_all["fold"].astype(str).isin(confirmation_names),
        "all_nested": evaluation_mask,
    }
    periods = {
        period: _period_report(
            routed_all.loc[mask].reset_index(drop=True),
            baseline_all.loc[mask].reset_index(drop=True),
            static_all.loc[mask].reset_index(drop=True),
        )
        for period, mask in period_masks.items()
        if mask.any()
    }
    return (
        {
            "role": role,
            "candidate_pool": {
                candidate_id: {"threshold": threshold}
                for candidate_id, (_, threshold) in candidates.items()
            },
            "static_champion": static_champion_id,
            "static_threshold": static_threshold,
            "first_fold_policy": "baseline fallback; excluded from nested metrics",
            "folds": selection_rows,
            "periods": periods,
        },
        routed_all,
    )


def run_chronological_role_router(
    project_root: Path,
    registry_path: Path,
    baseline_dirs: Sequence[Path],
    output_dir: Path,
    timeframe: int = 15,
) -> dict[str, object]:
    project_root = project_root.resolve()
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    baseline = read_prediction_sets(baseline_dirs, timeframe)
    candidates_by_id = {
        str(candidate["candidate_id"]): candidate
        for candidate in registry["candidates"]
        if bool(candidate["eligible"])
    }
    development_folds = tuple(registry["selection_policy"]["development_folds"])
    confirmation_folds = tuple(registry["selection_policy"]["confirmation_folds"])
    report: dict[str, object] = {
        "format_version": 1,
        "scope": f"M{timeframe} chronological role router",
        "registry": str(registry_path),
        "candidate_pool_policy": "all registry candidates with eligible=true; registry class and confirmation gate are not used for fold selection",
        "selection_objective": "maximum prior-OOS sqrt(coverage) * (Wilson95Lower(accuracy) - 0.50)",
        "roles": {},
    }
    manifest: dict[str, object] = {
        "format_version": 1,
        "kind": "chronological_role_router",
        "timeframe": timeframe,
        "roles": {},
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    for role, role_entry in registry["roles"].items():
        static_champion = role_entry["champion"]
        if static_champion is None:
            continue
        role_candidates = {
            candidate_id: (
                read_prediction_sets(
                    [project_root / str(candidate["prediction_dir"])], timeframe
                ),
                float(candidate["fixed_confidence_threshold"]),
            )
            for candidate_id, candidate in candidates_by_id.items()
            if candidate["role"] == role
        }
        fallback_threshold = float(
            candidates_by_id[str(static_champion)]["fixed_confidence_threshold"]
        )
        role_report, routed = build_chronological_role_route(
            baseline,
            role_candidates,
            str(role),
            str(static_champion),
            fallback_threshold,
            development_folds,
            confirmation_folds,
        )
        filename = f"m{timeframe}_{role}_router_predictions.parquet"
        routed.to_parquet(output_dir / filename, index=False)
        report["roles"][role] = role_report
        manifest["roles"][role] = {"predictions": filename}
    (output_dir / "router_metrics.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return report
