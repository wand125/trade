from __future__ import annotations

import unittest

import pandas as pd

from scripts.experiments.entry_ev_near_miss_exit_target_diagnostics import (
    add_fixed_horizon_targets,
    add_predicted_fixed_choice,
    mark_selected_rows,
    normalize_candidate_rows,
)


class EntryEvNearMissExitTargetDiagnosticsTest(unittest.TestCase):
    def test_fixed_horizon_targets_choose_best_and_zero_unexecutable(self) -> None:
        frame = pd.DataFrame(
            {
                "family": ["f", "f"],
                "role": ["r", "r"],
                "month": ["2026-01", "2026-01"],
                "decision_timestamp": ["2026-01-01T00:00:00Z", "2026-01-01T01:00:00Z"],
                "side": ["long", "short"],
                "side_score": [5.0, 6.0],
                "side_best_adjusted_pnl": [10.0, 2.0],
                "side_fixed_60m_adjusted_pnl": [-3.0, -4.0],
                "side_fixed_240m_adjusted_pnl": [4.0, -2.0],
                "side_fixed_720m_adjusted_pnl": [1.0, -3.0],
            }
        )

        normalized = normalize_candidate_rows(frame, horizons=[60, 240, 720])
        result = add_fixed_horizon_targets(
            normalized,
            horizons=[60, 240, 720],
            min_executable_pnl=0.0,
        )

        self.assertEqual(result["target_fixed_best_horizon_minutes"].tolist(), [240, 240])
        self.assertEqual(result["target_fixed_executable_horizon_minutes"].tolist(), [240, 0])
        self.assertEqual(result["target_fixed_executable"].tolist(), [True, False])
        self.assertEqual(result["target_fixed60_loss_rescuable"].tolist(), [True, False])

    def test_predicted_fixed_choice_scores_actual_selected_horizon(self) -> None:
        frame = pd.DataFrame(
            {
                "side_fixed_60m_adjusted_pnl": [1.0, -3.0],
                "side_fixed_240m_adjusted_pnl": [5.0, 4.0],
                "side_fixed_720m_adjusted_pnl": [2.0, -1.0],
                "target_fixed_best_adjusted_pnl": [5.0, 4.0],
                "pred_fixed_60m_adjusted_pnl": [0.5, -2.0],
                "pred_fixed_240m_adjusted_pnl": [2.0, -1.0],
                "pred_fixed_720m_adjusted_pnl": [3.0, -0.5],
            }
        )

        result = add_predicted_fixed_choice(
            frame,
            horizons=[60, 240, 720],
            min_predicted_pnl=0.0,
            min_executable_pnl=0.0,
        )

        self.assertEqual(result["pred_fixed_best_horizon_minutes"].tolist(), [720, 0])
        self.assertEqual(result["actual_pnl_at_pred_fixed_best_horizon"].tolist()[0], 2.0)
        self.assertTrue(result["pred_fixed_choice_executable"].tolist()[0])
        self.assertFalse(result["pred_fixed_choice_executable"].tolist()[1])
        self.assertEqual(result["pred_fixed_choice_regret"].tolist()[0], 3.0)

    def test_mark_selected_rows_sets_scope_and_bucket(self) -> None:
        candidates = pd.DataFrame(
            {
                "family": ["f", "f"],
                "role": ["r", "r"],
                "month": ["2026-01", "2026-01"],
                "decision_timestamp": pd.to_datetime(
                    ["2026-01-01T00:00:00Z", "2026-01-01T01:00:00Z"],
                    utc=True,
                ),
                "side": ["long", "long"],
                "selection_bucket": ["not_selected", "not_selected"],
                "selected_any": [False, False],
                "row_scope": ["available_candidates", "available_candidates"],
            }
        )
        selected = pd.DataFrame(
            {
                "family": ["f"],
                "role": ["r"],
                "month": ["2026-01"],
                "decision_timestamp": ["2026-01-01T01:00:00Z"],
                "side": ["long"],
                "selection_bucket": ["one_failed_strict_stage"],
            }
        )

        result = mark_selected_rows(candidates, selected)

        self.assertEqual(result["selected_any"].tolist(), [False, True])
        self.assertEqual(result["row_scope"].tolist(), ["available_candidates", "greedy_selected"])
        self.assertEqual(result["selection_bucket"].tolist(), ["not_selected", "one_failed_strict_stage"])


if __name__ == "__main__":
    unittest.main()
