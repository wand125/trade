from __future__ import annotations

import unittest

import pandas as pd

from scripts.experiments.entry_ev_near_miss_horizon_viability import (
    add_horizon_targets,
    choose_horizon,
    chronological_horizon_predictions,
)
from scripts.experiments.entry_ev_near_miss_exit_head import normalize_rows


class EntryEvNearMissHorizonViabilityTest(unittest.TestCase):
    def test_horizon_targets_mark_executable_and_tail_loss(self) -> None:
        frame = pd.DataFrame(
            {
                "side_fixed_60m_adjusted_pnl": [1.0, -6.0],
                "side_fixed_240m_adjusted_pnl": [-1.0, 0.5],
            }
        )

        result = add_horizon_targets(
            frame,
            horizons=[60, 240],
            min_executable_pnl=0.0,
            tail_loss_threshold=-5.0,
        )

        self.assertEqual(result["target_fixed_60m_executable"].tolist(), [True, False])
        self.assertEqual(result["target_fixed_60m_tail_loss"].tolist(), [False, True])
        self.assertEqual(result["target_fixed_240m_executable"].tolist(), [False, True])
        self.assertEqual(result["target_fixed_240m_tail_loss"].tolist(), [False, False])

    def test_choose_horizon_respects_tail_gate_and_model_used(self) -> None:
        frame = pd.DataFrame(
            {
                "target_fixed_best_adjusted_pnl": [6.0, 4.0],
                "side_fixed_60m_adjusted_pnl": [2.0, 1.0],
                "side_fixed_240m_adjusted_pnl": [6.0, 4.0],
                "pred_hv_60m_executable_prob": [0.8, 0.8],
                "pred_hv_60m_pnl": [2.0, 2.0],
                "pred_hv_60m_tail_loss_prob": [0.1, 0.1],
                "pred_hv_60m_executable_model_used": [True, True],
                "pred_hv_60m_pnl_model_used": [True, True],
                "pred_hv_60m_tail_model_used": [True, True],
                "pred_hv_240m_executable_prob": [0.9, 0.9],
                "pred_hv_240m_pnl": [5.0, 5.0],
                "pred_hv_240m_tail_loss_prob": [0.9, 0.1],
                "pred_hv_240m_executable_model_used": [True, False],
                "pred_hv_240m_pnl_model_used": [True, False],
                "pred_hv_240m_tail_model_used": [True, False],
            }
        )

        without_requirement = choose_horizon(
            frame,
            horizons=[60, 240],
            prob_threshold=0.7,
            ev_threshold=0.0,
            tail_prob_threshold=0.5,
            require_model_used=False,
        )
        with_requirement = choose_horizon(
            frame,
            horizons=[60, 240],
            prob_threshold=0.7,
            ev_threshold=0.0,
            tail_prob_threshold=0.5,
            require_model_used=True,
        )

        self.assertEqual(without_requirement["hv_chosen_horizon_minutes"].tolist(), [60, 240])
        self.assertEqual(with_requirement["hv_chosen_horizon_minutes"].tolist(), [60, 60])

    def test_chronological_predictions_use_only_prior_months(self) -> None:
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
                "target_fixed_best_horizon_minutes": [60, 240, 60, 240],
                "side_fixed_60m_adjusted_pnl": [2.0, -3.0, 3.0, -4.0],
                "side_fixed_240m_adjusted_pnl": [1.0, -1.0, 1.0, -3.0],
                "side_score": [2.0, 1.0, 2.5, 0.5],
                "family": ["f", "f", "f", "f"],
                "role": ["r", "r", "r", "r"],
                "side": ["long", "short", "long", "short"],
                "row_scope": ["available_candidates"] * 4,
                "selection_bucket": ["not_selected"] * 4,
                "near_miss_bucket": ["one_failed_strict_stage"] * 4,
            }
        )
        normalized = normalize_rows(raw, horizons=[60, 240])
        frame = add_horizon_targets(
            normalized,
            horizons=[60, 240],
            min_executable_pnl=0.0,
            tail_loss_threshold=-5.0,
        )

        _, folds = chronological_horizon_predictions(
            frame,
            horizons=[60, 240],
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
