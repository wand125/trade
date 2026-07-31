from __future__ import annotations

import unittest

import pandas as pd

from scripts.experiments.entry_ev_replacement_abstention_surface_diagnostics import (
    GateSpec,
    simulate_gate_choices,
    summarize_gate_surface,
)


class EntryEvReplacementAbstentionSurfaceDiagnosticsTest(unittest.TestCase):
    def test_simulate_gate_abstains_to_baseline_and_counts_only_interventions(self) -> None:
        base = {
            "replacement_score_mode": "bias_corrected",
            "calibration_min_context_count": 50,
            "candidate_min_prior_count": 100,
            "candidate_min_prior_month_count": 2,
            "candidate_min_prior_actual_mean": 0.0,
            "replacement_chosen": True,
            "prior_actual_mean": 10.0,
            "prior_mae": 2.0,
            "selection_score": 8.0,
            "candidate_pred_pnl": 3.0,
        }
        choices = pd.DataFrame(
            [
                {
                    **base,
                    "risk_selector": "selector",
                    "baseline_month_pnl": -1.0,
                    "month_pnl_after_replacement": 5.0,
                    "delta_vs_baseline": 6.0,
                    "risk_trade_selected": True,
                    "risk_trade_is_loss": True,
                },
                {
                    **base,
                    "risk_selector": "selector",
                    "baseline_month_pnl": 2.0,
                    "month_pnl_after_replacement": -10.0,
                    "delta_vs_baseline": -12.0,
                    "risk_trade_selected": True,
                    "risk_trade_is_loss": False,
                },
            ]
        )
        gate = GateSpec(
            gate_name="keep_first",
            gate_family="test",
            keep_mask=pd.Series([True, False], index=choices.index),
        )

        simulated = simulate_gate_choices(choices, gate)
        summary = summarize_gate_surface(
            simulated,
            min_loss_precision=0.5,
            max_winner_interventions=0,
            max_baseline_positive_degraded=0,
            min_current_negative_delta=0.0,
        )

        self.assertEqual(simulated["simulated_month_pnl_after_abstention"].tolist(), [5.0, 2.0])
        row = summary.iloc[0]
        self.assertTrue(bool(row["passes_abstention_constraints"]))
        self.assertEqual(int(row["replacement_intervention_count"]), 1)
        self.assertEqual(int(row["loss_intervention_count"]), 1)
        self.assertEqual(int(row["winner_intervention_count"]), 0)
        self.assertEqual(int(row["baseline_positive_degraded_count"]), 0)
        self.assertAlmostEqual(float(row["current_negative_mean_delta"]), 6.0)


if __name__ == "__main__":
    unittest.main()
