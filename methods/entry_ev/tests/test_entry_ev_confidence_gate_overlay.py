import unittest

import pandas as pd

from scripts.experiments.entry_ev_confidence_gate_overlay import (
    apply_confidence_gate_rule,
    confidence_pass_mask,
    summarize_confidence_gate,
)


def sample_trades() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "source": ["s"] * 4,
            "role": ["r"] * 4,
            "family": ["f"] * 4,
            "selector_variant": ["v"] * 4,
            "candidate": ["c"] * 4,
            "month": ["2025-01"] * 4,
            "direction": ["long", "short", "long", "short"],
            "entry_decision_timestamp": pd.to_datetime(
                [
                    "2025-01-01 00:00:00Z",
                    "2025-01-01 01:00:00Z",
                    "2025-01-01 02:00:00Z",
                    "2025-01-01 03:00:00Z",
                ],
                utc=True,
            ),
            "adjusted_pnl": [-1.0, 2.0, 3.0, -4.0],
            "entry_blocked": [False, False, True, False],
            "pred_taken_entry_local_rank": [0.54, 0.56, 0.70, 0.60],
            "pred_side_confidence_gap": [0.00, 0.20, 0.30, -0.10],
            "selected_loss_first_prob": [0.25, 0.40, 0.20, 0.30],
            "pred_taken_ev": [7.0, 11.0, 20.0, 9.0],
            "selected_fixed_720m_pred_pnl": [-1.0, 2.0, 5.0, 0.5],
        }
    )


class EntryEvConfidenceGateOverlayTest(unittest.TestCase):
    def test_confidence_pass_mask_combines_atoms(self) -> None:
        mask = confidence_pass_mask(sample_trades(), "rank_ge0p55_sidegap_ge0p10")

        self.assertEqual(mask.tolist(), [False, True, True, False])

    def test_apply_confidence_gate_ignores_existing_blocked_for_gate_count(self) -> None:
        frame = apply_confidence_gate_rule(sample_trades(), "rank_ge0p55")

        self.assertEqual(frame["confidence_gate_blocked"].tolist(), [True, False, False, False])
        self.assertEqual(frame["final_blocked"].tolist(), [True, False, True, False])

    def test_summarize_confidence_gate_outputs_selector_monthly_metrics(self) -> None:
        _, monthly = summarize_confidence_gate(sample_trades(), ["none", "rank_ge0p55"])
        by_rule = monthly.set_index("confidence_gate_rule")

        self.assertAlmostEqual(by_rule.loc["none", "total_adjusted_pnl"], -3.0)
        self.assertEqual(int(by_rule.loc["none", "trade_count"]), 3)
        self.assertAlmostEqual(by_rule.loc["rank_ge0p55", "total_adjusted_pnl"], -2.0)
        self.assertEqual(int(by_rule.loc["rank_ge0p55", "trade_count"]), 2)
        self.assertEqual(int(by_rule.loc["rank_ge0p55", "confidence_blocked_trade_count"]), 1)
        self.assertIn("__confgate_rank_ge0p55", by_rule.loc["rank_ge0p55", "variant"])


if __name__ == "__main__":
    unittest.main()
