import unittest

import pandas as pd

from trade_data.next_bar_entry_delay import (
    EntryDelayConfig,
    replay_entry_delay,
    summarize_replay,
)


class NextBarEntryDelayTests(unittest.TestCase):
    def setUp(self):
        self.m1 = pd.DataFrame(
            {
                "timestamp": pd.date_range("2025-01-01", periods=30, freq="min", tz="UTC"),
                "open": [100 + value for value in range(30)],
            }
        )
        self.trades = pd.DataFrame(
            {
                "entry_timestamp": pd.to_datetime(["2025-01-01 00:02Z"]),
                "exit_timestamp": pd.to_datetime(["2025-01-01 00:20Z"]),
                "direction": ["long"],
                "candidate_entry_price": [102.2],
                "candidate_exit_price": [110.2],
                "candidate_raw_pnl": [8.0],
                "candidate_adjusted_pnl": [7.9],
                "candidate_present": [True],
                "candidate_run_dir": ["run"],
                "month": ["2025-01"],
            }
        )
        self.predictions = pd.DataFrame(
            {
                "decision_timestamp": pd.to_datetime(
                    ["2025-01-01 00:00Z", "2025-01-01 00:05Z"]
                ),
                "target_timestamp": pd.to_datetime(
                    ["2025-01-01 00:05Z", "2025-01-01 00:10Z"]
                ),
                "predicted_direction": ["down", "up"],
                "confidence": [0.56, 0.52],
                "fold": ["test", "test"],
            }
        )

    def test_waits_for_release_and_preserves_execution_offset(self):
        result = replay_entry_delay(
            self.trades,
            self.predictions,
            self.m1,
            EntryDelayConfig(max_delay_minutes=15),
            high_confidence_only=False,
            timeout_action="skip",
        )

        self.assertEqual(
            result.loc[0, "delayed_entry_timestamp"],
            pd.Timestamp("2025-01-01 00:05Z"),
        )
        self.assertAlmostEqual(result.loc[0, "delayed_entry_price"], 105.2)
        self.assertAlmostEqual(result.loc[0, "delayed_raw_pnl"], 5.0)
        self.assertAlmostEqual(result.loc[0, "delayed_adjusted_pnl"], 4.9)
        self.assertAlmostEqual(result.loc[0, "entry_price_improvement"], -3.0)

    def test_timeout_skip_produces_zero_pnl_and_reduced_coverage(self):
        result = replay_entry_delay(
            self.trades,
            self.predictions.iloc[:1],
            self.m1,
            EntryDelayConfig(max_delay_minutes=5),
            high_confidence_only=False,
            timeout_action="skip",
        )
        metrics = summarize_replay(result, EntryDelayConfig())

        self.assertFalse(result.loc[0, "stateful_selected"])
        self.assertEqual(result.loc[0, "delayed_adjusted_pnl"], 0.0)
        self.assertEqual(metrics["coverage"], 0.0)
        self.assertEqual(metrics["pnl_delta"], -7.9)
        self.assertFalse(metrics["admission"]["accepted"])

    def test_low_confidence_opposition_does_not_delay_high_conf_policy(self):
        predictions = self.predictions.copy()
        predictions.loc[0, "confidence"] = 0.52
        result = replay_entry_delay(
            self.trades,
            predictions,
            self.m1,
            EntryDelayConfig(confidence_threshold=0.53),
            high_confidence_only=True,
            timeout_action="skip",
        )

        self.assertEqual(result.loc[0, "delay_minutes"], 0.0)
        self.assertAlmostEqual(result.loc[0, "delayed_adjusted_pnl"], 7.9)

    def test_additional_cost_only_applies_to_delayed_entries(self):
        result = replay_entry_delay(
            self.trades,
            self.predictions,
            self.m1,
            EntryDelayConfig(additional_costs=(0.10,)),
            high_confidence_only=False,
            timeout_action="skip",
        )
        metrics = summarize_replay(
            result, EntryDelayConfig(additional_costs=(0.10,))
        )

        self.assertEqual(metrics["delayed_rows"], 1)
        self.assertAlmostEqual(
            metrics["additional_cost_sensitivity"][0]["total_pnl"], 4.8
        )


if __name__ == "__main__":
    unittest.main()
