from __future__ import annotations

import unittest

import pandas as pd

from scripts.experiments.entry_ev_support_sufficient_selector_surface_diagnostics import (
    candidate_support_mask,
    choose_supported_candidate,
    choose_trade_by_risk,
    selector_choice_row,
)


class EntryEvSupportSufficientSelectorSurfaceDiagnosticsTest(unittest.TestCase):
    def test_candidate_support_mask_requires_count_months_and_actual_floor(self) -> None:
        pool = pd.DataFrame(
            {
                "prior_count": [60, 60, 40, 80],
                "prior_month_count": [2, 1, 2, 2],
                "prior_actual_mean": [6.0, 8.0, 9.0, -1.0],
            }
        )

        mask = candidate_support_mask(
            pool,
            min_prior_count=50,
            min_prior_month_count=2,
            min_prior_actual_mean=5.0,
        )

        self.assertEqual(mask.tolist(), [True, False, False, False])

    def test_choose_trade_by_feature_risk_uses_observable_score_not_outcome(self) -> None:
        trades = pd.DataFrame(
            {
                "trade_id": ["a", "b", "c"],
                "entry_decision_timestamp": [
                    "2025-03-01T00:00:00Z",
                    "2025-03-01T01:00:00Z",
                    "2025-03-01T02:00:00Z",
                ],
                "adjusted_pnl": [5.0, -1.0, -10.0],
                "loss_first_prob": [0.20, 0.25, 0.50],
                "taken_ev": [6.0, 8.0, 100.0],
                "side_confidence_gap": [0.10, 0.10, 0.10],
                "pred_fixed_best_pred_pnl": [1.0, 1.0, 1.0],
                "pred_fixed_best_horizon_minutes": [240, 240, 240],
                "risk_rule_hit_count": [1, 1, 1],
            }
        )

        chosen = choose_trade_by_risk(
            trades,
            selector="feature:ev_ge5_lossfirst_lt0p30",
        )

        self.assertEqual(str(chosen["trade_id"]), "b")

    def test_choose_supported_candidate_filters_before_scoring(self) -> None:
        pool = pd.DataFrame(
            {
                "side": ["long", "long"],
                "decision_timestamp": [
                    "2025-03-01T00:00:00Z",
                    "2025-03-01T01:00:00Z",
                ],
                "candidate_stage": ["one_failed_strict_stage", "one_failed_strict_stage"],
                "side_score": [10.0, 8.0],
                "score_pct": [0.9, 0.8],
                "side_margin_pct": [0.9, 0.8],
                "entry_rank_pct": [0.9, 0.8],
                "candidate_pred_fixed_best_horizon_minutes": [720, 720],
                "candidate_pred_fixed_best_pred_pnl": [1.0, 1.0],
                "candidate_actual_at_pred_fixed_best_horizon": [1.0, 2.0],
                "candidate_fixed_best_actual_pnl_oracle": [1.0, 2.0],
                "prior_count": [100, 20],
                "prior_month_count": [2, 2],
                "prior_actual_mean": [1.0, 20.0],
                "calibrated_prior_actual_mean": [1.0, 20.0],
            }
        )

        chosen = choose_supported_candidate(
            pool,
            score_mode="prior_actual_mean",
            min_prior_count=50,
            min_prior_month_count=2,
            min_prior_actual_mean=0.0,
        )

        self.assertEqual(str(chosen["decision_timestamp"]), "2025-03-01T00:00:00Z")

    def test_selector_choice_row_accounts_for_replacing_selected_trade(self) -> None:
        risk_trade = pd.Series(
            {
                "trade_id": "loss",
                "direction": "short",
                "entry_decision_timestamp": "2025-03-01T00:00:00Z",
                "adjusted_pnl": -2.0,
                "risk_rule_hit_count": 1,
            }
        )
        candidate = pd.Series(
            {
                "side": "long",
                "decision_timestamp": "2025-03-01T01:00:00Z",
                "candidate_stage": "one_failed_strict_stage",
                "side_score": 7.0,
                "candidate_pred_fixed_best_horizon_minutes": 720,
                "candidate_pred_fixed_best_pred_pnl": 1.0,
                "candidate_actual_at_pred_fixed_best_horizon": 5.0,
                "candidate_fixed_best_actual_pnl_oracle": 6.0,
                "calibrated_prior_actual_mean": 10.0,
                "calibration_context_spec": "side",
                "calibration_context_key": "long",
                "prior_count": 100,
                "prior_month_count": 2,
                "prior_actual_mean": 10.0,
            }
        )

        row = selector_choice_row(
            role="r",
            family="f",
            month="2025-03",
            month_pnl=-1.0,
            risk_selector="feature:ev_ge5_lossfirst_lt0p30",
            risk_trade=risk_trade,
            replacement_score_mode="prior_actual_mean",
            calibration_min_context_count=50,
            candidate_min_prior_count=50,
            candidate_min_prior_month_count=2,
            candidate_min_prior_actual_mean=0.0,
            candidate=candidate,
            candidate_rows=10,
            supported_candidate_rows=3,
        )

        self.assertAlmostEqual(row["skip_only_month_pnl"], 1.0)
        self.assertAlmostEqual(row["month_pnl_after_replacement"], 6.0)
        self.assertAlmostEqual(row["delta_vs_baseline"], 7.0)


if __name__ == "__main__":
    unittest.main()
