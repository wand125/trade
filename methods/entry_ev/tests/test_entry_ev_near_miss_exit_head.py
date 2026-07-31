from __future__ import annotations

import unittest

import pandas as pd

from scripts.experiments.entry_ev_near_miss_exit_head import (
    add_head_horizon_choice,
    chronological_head_predictions,
    normalize_rows,
)


class EntryEvNearMissExitHeadTest(unittest.TestCase):
    def test_head_horizon_choice_uses_predicted_best_and_scores_actual_pnl(self) -> None:
        frame = pd.DataFrame(
            {
                "pred_exit_head_fixed_60m_pnl": [1.0, -1.0],
                "pred_exit_head_fixed_240m_pnl": [5.0, 2.0],
                "pred_exit_head_fixed_720m_pnl": [3.0, 4.0],
                "side_fixed_60m_adjusted_pnl": [-2.0, 1.0],
                "side_fixed_240m_adjusted_pnl": [6.0, -3.0],
                "side_fixed_720m_adjusted_pnl": [2.0, 7.0],
                "target_fixed_best_adjusted_pnl": [6.0, 7.0],
            }
        )

        result = add_head_horizon_choice(
            frame,
            horizons=[60, 240, 720],
            min_predicted_pnl=0.0,
        )

        self.assertEqual(result["pred_exit_head_best_horizon_minutes"].tolist(), [240, 720])
        self.assertEqual(result["actual_pnl_at_exit_head_horizon"].tolist(), [6.0, 7.0])
        self.assertEqual(result["exit_head_choice_regret"].tolist(), [0.0, 0.0])

    def test_chronological_head_uses_only_prior_months(self) -> None:
        raw = pd.DataFrame(
            {
                "month": ["2026-01", "2026-01", "2026-02", "2026-02"],
                "decision_timestamp": [
                    "2026-01-01T00:00:00Z",
                    "2026-01-01T01:00:00Z",
                    "2026-02-01T00:00:00Z",
                    "2026-02-01T01:00:00Z",
                ],
                "target_fixed_executable": [True, False, True, False],
                "target_fixed_best_adjusted_pnl": [2.0, -1.0, 3.0, -2.0],
                "target_fixed_best_horizon_minutes": [60, 240, 60, 720],
                "side_fixed_60m_adjusted_pnl": [2.0, -3.0, 3.0, -4.0],
                "side_fixed_240m_adjusted_pnl": [1.0, -1.0, 1.0, -3.0],
                "side_fixed_720m_adjusted_pnl": [0.0, -2.0, 2.0, -2.0],
                "side_score": [2.0, 1.0, 2.5, 0.5],
                "family": ["f", "f", "f", "f"],
                "role": ["r", "r", "r", "r"],
                "side": ["long", "short", "long", "short"],
                "row_scope": ["available_candidates"] * 4,
                "selection_bucket": ["not_selected"] * 4,
                "near_miss_bucket": ["one_failed_strict_stage"] * 4,
            }
        )
        frame = normalize_rows(raw, horizons=[60, 240, 720])

        _, folds = chronological_head_predictions(
            frame,
            horizons=[60, 240, 720],
            train_universe="all",
            min_train_months=1,
            min_train_rows=2,
            numeric_features=["side_score"],
            categorical_features=["side"],
            max_iter=5,
            learning_rate=0.1,
            l2_regularization=1.0,
            max_leaf_nodes=4,
            random_state=7,
        )

        jan = folds[folds["target_month"].eq("2026-01")]
        feb = folds[folds["target_month"].eq("2026-02")]
        self.assertTrue(jan["train_rows"].eq(0).all())
        self.assertTrue(feb["train_rows"].eq(2).all())
        self.assertTrue(feb["train_months"].eq(1).all())


if __name__ == "__main__":
    unittest.main()
