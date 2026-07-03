from __future__ import annotations

import unittest

import pandas as pd

from scripts.experiments.entry_ev_candidate_generation_gap_audit import normalize_predictions
from scripts.experiments.entry_ev_selected_replacement_scope_diagnostics import (
    selected_replacement_rows,
    selected_scope_summary,
)


def sample_prediction_frame() -> pd.DataFrame:
    frame = pd.DataFrame(
        {
            "family": ["f", "f", "f"],
            "role": ["r", "r", "r"],
            "month": ["2026-01", "2026-01", "2026-01"],
            "decision_timestamp": [
                "2026-01-01T00:00:00Z",
                "2026-01-01T01:00:00Z",
                "2026-01-01T02:00:00Z",
            ],
            "side": ["long", "long", "short"],
            "needed_side": ["long", "long", "long"],
            "extra_side_needed": [1, 1, 1],
            "row_scope": [
                "greedy_selected",
                "available_candidates",
                "greedy_selected",
            ],
            "selection_bucket": [
                "one_failed_strict_stage",
                "not_selected",
                "one_failed_strict_stage",
            ],
            "stateful_available": [True, True, True],
            "selected_any": [True, False, True],
            "strict_side_specific": [False, True, False],
            "relaxed_side_specific": [False, True, False],
            "one_failed_strict_stage": [True, False, True],
            "holding_ok": [True, True, True],
            "side_score": [2.5, 6.0, 2.5],
            "score_pct": [0.99, 0.99, 0.99],
            "side_margin": [0.5, 0.5, 0.5],
            "side_margin_pct": [0.97, 0.97, 0.97],
            "entry_rank_pct": [0.93, 0.93, 0.93],
        }
    )
    for horizon in [60, 240, 720]:
        frame[f"side_fixed_{horizon}m_adjusted_pnl"] = [1.0, 2.0, 3.0]
        frame[f"pred_hv_{horizon}m_executable_prob"] = [0.6, 0.6, 0.6]
        frame[f"pred_hv_{horizon}m_pnl"] = [-0.5, 1.0, -0.5]
        frame[f"pred_hv_{horizon}m_tail_loss_prob"] = [0.2, 0.2, 0.2]
        frame[f"pred_hv_{horizon}m_executable_model_used"] = [True, True, True]
        frame[f"pred_hv_{horizon}m_pnl_model_used"] = [True, True, True]
        frame[f"pred_hv_{horizon}m_tail_model_used"] = [True, True, True]
    return frame


class EntryEvSelectedReplacementScopeDiagnosticsTest(unittest.TestCase):
    def test_selected_onefail_target_support_rows_are_reexposed(self) -> None:
        predictions = normalize_predictions(
            sample_prediction_frame(),
            horizons=[60, 240, 720],
            prefer_ranker_pnl=True,
        )
        selected = selected_replacement_rows(
            predictions,
            synthetic_scope="selected_onefail_replacement",
            selection_buckets=["one_failed_strict_stage"],
            require_stateful_available=True,
            require_target_support=True,
            strict_score_floor=5.0,
            strict_score_pct=0.95,
            strict_side_margin_pct=0.95,
            strict_entry_rank_pct=0.90,
            strict_min_side_margin=0.0,
        )

        self.assertEqual(len(selected), 1)
        self.assertEqual(selected.iloc[0]["row_scope"], "selected_onefail_replacement")
        self.assertEqual(selected.iloc[0]["source_row_scope"], "greedy_selected")
        self.assertEqual(selected.iloc[0]["recomputed_strict_failed_stages"], "score_floor")

    def test_selected_scope_summary_reports_fixed_horizon_diagnostics(self) -> None:
        predictions = normalize_predictions(
            sample_prediction_frame(),
            horizons=[60, 240, 720],
            prefer_ranker_pnl=True,
        )
        selected = selected_replacement_rows(
            predictions,
            synthetic_scope="selected_onefail_replacement",
            selection_buckets=["one_failed_strict_stage"],
            require_stateful_available=True,
            require_target_support=True,
            strict_score_floor=5.0,
            strict_score_pct=0.95,
            strict_side_margin_pct=0.95,
            strict_entry_rank_pct=0.90,
            strict_min_side_margin=0.0,
        )
        summary = selected_scope_summary(selected, horizons=[60, 240, 720]).iloc[0]

        self.assertEqual(int(summary["selected_replacement_rows"]), 1)
        self.assertEqual(float(summary["fixed240_actual_sum"]), 1.0)
        self.assertEqual(float(summary["pred240_pnl_max"]), -0.5)


if __name__ == "__main__":
    unittest.main()
