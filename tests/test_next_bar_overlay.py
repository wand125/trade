import unittest

import numpy as np
import pandas as pd

from trade_data.next_bar_overlay import (
    OverlayConfig,
    attach_next_bar_overlay,
    evaluate_overlay_policies,
)


class NextBarOverlayTests(unittest.TestCase):
    def test_only_uses_prediction_during_its_active_target_bar(self):
        trades = pd.DataFrame(
            {
                "entry_decision_timestamp": pd.to_datetime(
                    ["2025-01-01 00:16Z", "2025-01-01 00:31Z"]
                ),
                "direction": ["long", "long"],
                "candidate_adjusted_pnl": [2.0, -1.0],
                "candidate_present": [True, True],
            }
        )
        predictions = pd.DataFrame(
            {
                "decision_timestamp": pd.to_datetime(["2025-01-01 00:15Z"]),
                "target_timestamp": pd.to_datetime(["2025-01-01 00:30Z"]),
                "predicted_direction": ["up"],
                "confidence": [0.56],
                "fold": ["test"],
            }
        )
        result = attach_next_bar_overlay(trades, predictions, OverlayConfig())

        self.assertTrue(result.loc[0, "next_bar_available"])
        self.assertTrue(result.loc[0, "next_bar_aligned"])
        self.assertAlmostEqual(result.loc[0, "trade_direction_odds"], 0.56 / 0.44)
        self.assertFalse(result.loc[1, "next_bar_available"])

    def test_veto_and_soft_size_are_no_replacement_counterfactuals(self):
        frame = pd.DataFrame(
            {
                "entry_decision_timestamp": pd.to_datetime(
                    ["2025-01-01 00:01Z", "2025-02-01 00:01Z"]
                ),
                "candidate_adjusted_pnl": [-10.0, 4.0],
                "next_bar_available": [True, True],
                "next_bar_high_confidence": [True, False],
                "next_bar_aligned": [False, True],
                "next_bar_high_confidence_opposed": [True, False],
                "trade_direction_probability": [0.44, 0.52],
                "month": ["2025-01", "2025-02"],
            }
        )
        policies = evaluate_overlay_policies(
            frame, OverlayConfig(loss_multiplier=1.20)
        )

        self.assertEqual(policies["baseline"]["total_pnl"], -6.0)
        self.assertEqual(
            policies["veto_high_confidence_opposed"]["total_pnl"], 4.0
        )
        self.assertEqual(
            policies["half_size_high_confidence_opposed"]["total_pnl"], -1.0
        )
        self.assertEqual(
            policies["baseline"]["risk_adjusted_total"], -8.0
        )


if __name__ == "__main__":
    unittest.main()
