from __future__ import annotations

import unittest

import pandas as pd

from scripts.experiments.entry_ev_candidate_generation_gap_audit import (
    build_horizon_rows,
    normalize_predictions,
    summarize_gate,
    target_scope_summary,
)


def sample_prediction_frame() -> pd.DataFrame:
    frame = pd.DataFrame(
        {
            "family": ["f", "f", "f", "f"],
            "role": ["r", "r", "r", "r"],
            "month": ["2026-01", "2026-02", "2026-03", "2026-04"],
            "decision_timestamp": [
                "2026-01-01T00:00:00Z",
                "2026-02-01T00:00:00Z",
                "2026-03-01T00:00:00Z",
                "2026-04-01T00:00:00Z",
            ],
            "side": ["short", "long", "long", "long"],
            "needed_side": ["long", "long", "long", "long"],
            "extra_side_needed": [1, 0, 1, 1],
            "row_scope": [
                "available_candidates",
                "available_candidates",
                "available_candidates",
                "available_candidates",
            ],
            "selection_bucket": ["b", "b", "b", "b"],
            "stateful_available": [True, True, True, True],
            "selected_any": [False, False, False, False],
            "strict_side_specific": [False, False, False, False],
            "relaxed_side_specific": [False, False, False, False],
        }
    )
    for horizon in [60, 240, 720]:
        frame[f"side_fixed_{horizon}m_adjusted_pnl"] = [1.0, 2.0, 3.0, 4.0]
        frame[f"pred_hv_{horizon}m_executable_prob"] = [0.8, 0.8, 0.8, 0.8]
        frame[f"pred_hv_{horizon}m_pnl"] = [-5.0, -5.0, -5.0, -5.0]
        frame[f"pred_hv_{horizon}m_tail_loss_prob"] = [0.2, 0.2, 0.2, 0.2]
        frame[f"pred_hv_{horizon}m_executable_model_used"] = [True, True, True, True]
        frame[f"pred_hv_{horizon}m_pnl_model_used"] = [True, True, True, True]
        frame[f"pred_hv_{horizon}m_tail_model_used"] = [True, True, True, True]
    frame.loc[2, "pred_hv_240m_pnl"] = 1.5
    return frame


def build_summary(targets: list[tuple[str, str, str]]) -> pd.DataFrame:
    predictions = normalize_predictions(
        sample_prediction_frame(),
        horizons=[60, 240, 720],
        prefer_ranker_pnl=True,
    )
    horizon_rows = build_horizon_rows(
        predictions,
        targets=targets,
        row_scopes=["available_candidates"],
        horizons=[60, 240, 720],
    )
    strict = summarize_gate(
        horizon_rows,
        prefix="strict",
        min_prob=0.45,
        min_pred_pnl=0.0,
        max_tail_prob=0.5,
        require_model_used=True,
    )
    relaxed = summarize_gate(
        horizon_rows,
        prefix="relaxed",
        min_prob=0.30,
        min_pred_pnl=-2.0,
        max_tail_prob=0.5,
        require_model_used=True,
    )
    return target_scope_summary(
        predictions,
        targets=targets,
        row_scopes=["available_candidates"],
        horizons=[60, 240, 720],
        strict_summary=strict,
        relaxed_summary=relaxed,
        replay_summary=pd.DataFrame(),
    )


class EntryEvCandidateGenerationGapAuditTest(unittest.TestCase):
    def test_classifies_no_prediction_rows(self) -> None:
        summary = build_summary([("r", "2026-09", "long")]).iloc[0]

        self.assertEqual(summary["gap_stage"], "no_prediction_rows")

    def test_classifies_no_target_side_rows(self) -> None:
        summary = build_summary([("r", "2026-01", "long")]).iloc[0]

        self.assertEqual(summary["gap_stage"], "no_target_side_rows")

    def test_classifies_no_target_support_rows(self) -> None:
        summary = build_summary([("r", "2026-02", "long")]).iloc[0]

        self.assertEqual(summary["gap_stage"], "no_target_support_rows")

    def test_classifies_strict_candidate_exists(self) -> None:
        summary = build_summary([("r", "2026-03", "long")]).iloc[0]

        self.assertEqual(summary["gap_stage"], "strict_candidate_exists")
        self.assertEqual(int(summary["strict_choice_count"]), 1)

    def test_positive_actual_does_not_override_threshold_filtering(self) -> None:
        summary = build_summary([("r", "2026-04", "long")]).iloc[0]

        self.assertGreater(int(summary["actual_positive_horizon_count"]), 0)
        self.assertEqual(summary["gap_stage"], "threshold_filtered")


if __name__ == "__main__":
    unittest.main()
