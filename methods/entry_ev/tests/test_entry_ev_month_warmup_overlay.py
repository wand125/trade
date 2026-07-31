import unittest

import pandas as pd

from scripts.experiments.entry_ev_month_warmup_overlay import (
    apply_month_warmup_rule,
    summarize_month_warmup,
)


def sample_trades() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "source": ["s"] * 5,
            "role": ["r"] * 5,
            "family": ["f"] * 5,
            "selector_variant": ["v"] * 5,
            "candidate": ["c"] * 5,
            "month": ["2025-01"] * 5,
            "direction": ["long", "long", "short", "short", "long"],
            "entry_decision_timestamp": pd.to_datetime(
                [
                    "2025-01-01 00:00:00Z",
                    "2025-01-01 01:00:00Z",
                    "2025-01-01 02:00:00Z",
                    "2025-01-01 03:00:00Z",
                    "2025-01-01 04:00:00Z",
                ],
                utc=True,
            ),
            "adjusted_pnl": [-1.0, 2.0, 3.0, -4.0, 5.0],
            "entry_blocked": [False, True, False, False, False],
        }
    )


class EntryEvMonthWarmupOverlayTest(unittest.TestCase):
    def test_skip_first_eligible_ignores_existing_blocked_trade(self) -> None:
        frame = apply_month_warmup_rule(sample_trades(), "skip_first_1")

        self.assertEqual(frame["month_warmup_blocked"].tolist(), [True, False, False, False, False])
        self.assertEqual(frame["final_blocked"].tolist(), [True, True, False, False, False])

    def test_wait_opposite_seen_uses_prior_candidate_signals(self) -> None:
        frame = apply_month_warmup_rule(sample_trades(), "wait_opposite_seen")

        self.assertEqual(frame["month_warmup_blocked"].tolist(), [True, False, False, False, False])
        self.assertEqual(frame["final_blocked"].tolist(), [True, True, False, False, False])

    def test_summarize_month_warmup_outputs_selector_monthly_metrics(self) -> None:
        _, monthly = summarize_month_warmup(sample_trades(), ["none", "skip_first_1"])
        by_rule = monthly.set_index("month_warmup_rule")

        self.assertAlmostEqual(by_rule.loc["none", "total_adjusted_pnl"], 3.0)
        self.assertEqual(int(by_rule.loc["none", "trade_count"]), 4)
        self.assertAlmostEqual(by_rule.loc["skip_first_1", "total_adjusted_pnl"], 4.0)
        self.assertEqual(int(by_rule.loc["skip_first_1", "trade_count"]), 3)
        self.assertEqual(int(by_rule.loc["skip_first_1", "warmup_blocked_trade_count"]), 1)
        self.assertIn("__monthwarmup_skip_first_1", by_rule.loc["skip_first_1", "variant"])


if __name__ == "__main__":
    unittest.main()
