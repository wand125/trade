from __future__ import annotations

import unittest

import pandas as pd

from scripts.experiments.entry_ev_surface_support_gap_diagnostics import (
    add_support_gap_columns,
    summarize_support_gaps,
)


class EntryEvSurfaceSupportGapDiagnosticsTest(unittest.TestCase):
    def test_add_support_gap_columns_splits_prior_filter_stages(self) -> None:
        base = {
            "role": "role",
            "family": "family",
            "month": "2025-03",
            "risk_selector": "risk",
            "replacement_score_mode": "score",
            "calibration_min_context_count": 50,
            "candidate_min_prior_count": 20,
            "candidate_min_prior_month_count": 2,
            "candidate_min_prior_actual_mean": 0.0,
            "baseline_month_pnl": -1.0,
        }
        choices = pd.DataFrame(
            [
                {
                    **base,
                    "risk_trade_id": "",
                    "risk_trade_selected": False,
                    "risk_trade_is_loss": False,
                    "candidate_rows": 0,
                    "supported_candidate_rows": 0,
                    "replacement_chosen": False,
                    "month_pnl_after_replacement": -1.0,
                    "delta_vs_baseline": 0.0,
                },
                {
                    **base,
                    "risk_trade_id": "winner",
                    "risk_trade_selected": True,
                    "risk_trade_is_loss": False,
                    "candidate_rows": 0,
                    "supported_candidate_rows": 0,
                    "replacement_chosen": False,
                    "month_pnl_after_replacement": -1.0,
                    "delta_vs_baseline": 0.0,
                },
                {
                    **base,
                    "risk_trade_id": "count_gap",
                    "risk_trade_selected": True,
                    "risk_trade_is_loss": True,
                    "candidate_rows": 1,
                    "supported_candidate_rows": 0,
                    "replacement_chosen": False,
                    "month_pnl_after_replacement": -1.0,
                    "delta_vs_baseline": 0.0,
                },
                {
                    **base,
                    "risk_trade_id": "month_gap",
                    "risk_trade_selected": True,
                    "risk_trade_is_loss": True,
                    "candidate_rows": 1,
                    "supported_candidate_rows": 0,
                    "replacement_chosen": False,
                    "month_pnl_after_replacement": -1.0,
                    "delta_vs_baseline": 0.0,
                },
                {
                    **base,
                    "risk_trade_id": "actual_gap",
                    "risk_trade_selected": True,
                    "risk_trade_is_loss": True,
                    "candidate_rows": 1,
                    "supported_candidate_rows": 0,
                    "replacement_chosen": False,
                    "month_pnl_after_replacement": -1.0,
                    "delta_vs_baseline": 0.0,
                },
                {
                    **base,
                    "risk_trade_id": "success",
                    "risk_trade_selected": True,
                    "risk_trade_is_loss": True,
                    "candidate_rows": 1,
                    "supported_candidate_rows": 1,
                    "replacement_chosen": True,
                    "month_pnl_after_replacement": 1.0,
                    "delta_vs_baseline": 2.0,
                },
            ]
        )
        candidates = pd.DataFrame(
            [
                {
                    "family": "family",
                    "month": "2025-03",
                    "risk_selector": "risk",
                    "risk_trade_id": "count_gap",
                    "calibration_min_context_count": 50,
                    "prior_count": 10,
                    "prior_month_count": 5,
                    "prior_actual_mean": 10.0,
                    "candidate_actual_at_pred_fixed_best_horizon": 2.0,
                },
                {
                    "family": "family",
                    "month": "2025-03",
                    "risk_selector": "risk",
                    "risk_trade_id": "month_gap",
                    "calibration_min_context_count": 50,
                    "prior_count": 25,
                    "prior_month_count": 1,
                    "prior_actual_mean": 10.0,
                    "candidate_actual_at_pred_fixed_best_horizon": 2.0,
                },
                {
                    "family": "family",
                    "month": "2025-03",
                    "risk_selector": "risk",
                    "risk_trade_id": "actual_gap",
                    "calibration_min_context_count": 50,
                    "prior_count": 25,
                    "prior_month_count": 2,
                    "prior_actual_mean": -1.0,
                    "candidate_actual_at_pred_fixed_best_horizon": 2.0,
                },
                {
                    "family": "family",
                    "month": "2025-03",
                    "risk_selector": "other_risk",
                    "risk_trade_id": "success",
                    "calibration_min_context_count": 50,
                    "prior_count": 25,
                    "prior_month_count": 2,
                    "prior_actual_mean": 1.0,
                    "candidate_actual_at_pred_fixed_best_horizon": 2.0,
                },
            ]
        )

        output = add_support_gap_columns(choices, candidates)
        summary = summarize_support_gaps(output)

        self.assertEqual(
            output["support_gap_stage"].tolist(),
            [
                "no_risk_trade",
                "risk_trade_winner",
                "prior_count_gap",
                "prior_month_gap",
                "prior_actual_gap",
                "supported_repaired",
            ],
        )
        self.assertEqual(output["target_outcome_success"].tolist()[-1], True)
        self.assertEqual(output["candidate_pool_match_scope"].tolist()[-1], "risk_selector_fallback")
        self.assertFalse(output["support_count_mismatch"].any())
        row = summary.iloc[0]
        self.assertEqual(int(row["success_count"]), 1)
        self.assertEqual(int(row["prior_count_gap_count"]), 1)
        self.assertEqual(int(row["prior_month_gap_count"]), 1)
        self.assertEqual(int(row["prior_actual_gap_count"]), 1)
        self.assertEqual(int(row["risk_gap_count"]), 2)


if __name__ == "__main__":
    unittest.main()
