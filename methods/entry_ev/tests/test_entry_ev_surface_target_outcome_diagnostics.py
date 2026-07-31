from __future__ import annotations

import unittest

import pandas as pd

from scripts.experiments.entry_ev_surface_target_outcome_diagnostics import (
    classify_outcomes,
    summarize_outcomes,
)


class EntryEvSurfaceTargetOutcomeDiagnosticsTest(unittest.TestCase):
    def test_classify_outcomes_separates_risk_candidate_and_replacement_gaps(self) -> None:
        base = {
            "risk_selector": "risk",
            "replacement_score_mode": "score",
            "calibration_min_context_count": 50,
            "candidate_min_prior_count": 100,
            "candidate_min_prior_month_count": 2,
            "candidate_min_prior_actual_mean": 0.0,
            "baseline_month_pnl": -1.0,
        }
        choices = pd.DataFrame(
            [
                {
                    **base,
                    "risk_trade_selected": False,
                    "risk_trade_is_loss": False,
                    "supported_candidate_rows": 0,
                    "replacement_chosen": False,
                    "month_pnl_after_replacement": -1.0,
                    "delta_vs_baseline": 0.0,
                },
                {
                    **base,
                    "risk_trade_selected": True,
                    "risk_trade_is_loss": False,
                    "supported_candidate_rows": 0,
                    "replacement_chosen": False,
                    "month_pnl_after_replacement": -1.0,
                    "delta_vs_baseline": 0.0,
                },
                {
                    **base,
                    "risk_trade_selected": True,
                    "risk_trade_is_loss": True,
                    "supported_candidate_rows": 0,
                    "replacement_chosen": False,
                    "month_pnl_after_replacement": -1.0,
                    "delta_vs_baseline": 0.0,
                },
                {
                    **base,
                    "risk_trade_selected": True,
                    "risk_trade_is_loss": True,
                    "supported_candidate_rows": 10,
                    "replacement_chosen": True,
                    "month_pnl_after_replacement": 2.0,
                    "delta_vs_baseline": 3.0,
                },
            ]
        )

        output = classify_outcomes(choices)
        summary = summarize_outcomes(output)

        self.assertEqual(
            output["target_outcome_category"].tolist(),
            [
                "no_risk_trade",
                "risk_trade_winner",
                "loss_selected_no_supported_candidate",
                "loss_replacement_repairs_month",
            ],
        )
        row = summary.iloc[0]
        self.assertEqual(int(row["success_count"]), 1)
        self.assertEqual(int(row["candidate_gap_count"]), 1)
        self.assertEqual(int(row["risk_gap_count"]), 2)


if __name__ == "__main__":
    unittest.main()
