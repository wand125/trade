from __future__ import annotations

import unittest

import pandas as pd

from scripts.experiments.entry_ev_selector_surface_winner_damage_diagnostics import (
    annotate_choices,
    summarize_winner_damage,
)


class EntryEvSelectorSurfaceWinnerDamageDiagnosticsTest(unittest.TestCase):
    def sample_choices(self) -> pd.DataFrame:
        rows = []
        base = {
            "risk_selector": "feature:a",
            "replacement_score_mode": "bias_corrected",
            "calibration_min_context_count": 50,
            "candidate_min_prior_count": 100,
            "candidate_min_prior_month_count": 2,
            "candidate_min_prior_actual_mean": 0.0,
            "replacement_chosen": True,
        }
        rows.append(
            {
                **base,
                "role": "r1",
                "family": "f",
                "month": "2025-01",
                "baseline_month_pnl": -1.0,
                "month_pnl_after_replacement": 2.0,
                "delta_vs_baseline": 3.0,
                "risk_trade_selected": True,
                "risk_trade_is_loss": True,
                "risk_trade_adjusted_pnl": -2.0,
            }
        )
        rows.append(
            {
                **base,
                "role": "r2",
                "family": "f",
                "month": "2025-02",
                "baseline_month_pnl": 5.0,
                "month_pnl_after_replacement": 4.0,
                "delta_vs_baseline": -1.0,
                "risk_trade_selected": True,
                "risk_trade_is_loss": False,
                "risk_trade_adjusted_pnl": 1.5,
            }
        )
        rows.append(
            {
                **base,
                "role": "r3",
                "family": "f",
                "month": "2025-03",
                "baseline_month_pnl": 1.0,
                "month_pnl_after_replacement": 1.0,
                "delta_vs_baseline": 0.0,
                "risk_trade_selected": False,
                "risk_trade_is_loss": False,
                "risk_trade_adjusted_pnl": 0.0,
            }
        )
        return pd.DataFrame(rows)

    def test_annotate_choices_splits_current_negative_and_winner_damage(self) -> None:
        output = annotate_choices(self.sample_choices())

        self.assertEqual(
            output["baseline_bucket"].tolist(),
            ["current_negative", "current_nonnegative", "current_nonnegative"],
        )
        self.assertEqual(output["risk_selected_loss"].tolist(), [True, False, False])
        self.assertEqual(output["risk_selected_winner"].tolist(), [False, True, False])
        self.assertEqual(output["baseline_positive_degraded"].tolist(), [False, True, False])
        self.assertEqual(output["current_negative_positive_after"].tolist(), [True, False, False])

    def test_summarize_winner_damage_applies_constraints(self) -> None:
        summary = summarize_winner_damage(
            self.sample_choices(),
            min_loss_precision=0.5,
            max_winner_selected=0,
            max_baseline_positive_degraded=0,
            min_current_negative_delta=0.0,
        )

        row = summary.iloc[0]
        self.assertEqual(int(row["target_count"]), 3)
        self.assertEqual(int(row["loss_selected_count"]), 1)
        self.assertEqual(int(row["winner_selected_count"]), 1)
        self.assertAlmostEqual(float(row["loss_selection_precision"]), 0.5)
        self.assertEqual(int(row["baseline_positive_degraded_count"]), 1)
        self.assertFalse(bool(row["passes_winner_damage_constraints"]))


if __name__ == "__main__":
    unittest.main()
