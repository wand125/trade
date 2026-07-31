from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

import pandas as pd


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "experiments"
    / "online_context_state_diagnostics.py"
)
SPEC = importlib.util.spec_from_file_location("online_context_state_diagnostics", SCRIPT_PATH)
online_context_state_diagnostics = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(online_context_state_diagnostics)


class OnlineContextStateDiagnosticsTests(unittest.TestCase):
    def test_annotates_prior_context_state_without_future_trade(self):
        trades = pd.DataFrame(
            {
                "direction": ["short", "short", "short"],
                "entry_timestamp": pd.to_datetime(
                    [
                        "2025-01-01T00:01:00Z",
                        "2025-01-01T00:20:00Z",
                        "2025-01-01T01:00:00Z",
                    ]
                ),
                "exit_timestamp": pd.to_datetime(
                    [
                        "2025-01-01T00:10:00Z",
                        "2025-01-01T00:30:00Z",
                        "2025-01-01T01:10:00Z",
                    ]
                ),
                "entry_decision_timestamp": pd.to_datetime(
                    [
                        "2025-01-01T00:00:00Z",
                        "2025-01-01T00:19:00Z",
                        "2025-01-01T00:59:00Z",
                    ]
                ),
                "exit_decision_timestamp": pd.to_datetime(
                    [
                        "2025-01-01T00:09:00Z",
                        "2025-01-01T00:29:00Z",
                        "2025-01-01T01:09:00Z",
                    ]
                ),
                "adjusted_pnl": [-25.0, 10.0, -5.0],
                "dataset_month": ["2025-01", "2025-01", "2025-01"],
                "entry_margin": [1.0, 2.0, 3.0],
            }
        )

        annotated = online_context_state_diagnostics.annotate_online_context_state(
            trades,
            context_columns=("dataset_month",),
            thresholds=(20.0,),
        )

        self.assertEqual(annotated.loc[0, "prior_context_trade_count"], 0)
        self.assertEqual(annotated.loc[1, "prior_context_trade_count"], 1)
        self.assertAlmostEqual(annotated.loc[1, "prior_context_pnl"], -25.0)
        self.assertTrue(annotated.loc[1, "prior_context_ever_breached_20"])
        self.assertAlmostEqual(annotated.loc[1, "minutes_since_context_breach_20"], 10.0)
        self.assertEqual(annotated.loc[2, "prior_context_trade_count"], 2)
        self.assertAlmostEqual(annotated.loc[2, "prior_context_pnl"], -15.0)
        self.assertTrue(annotated.loc[2, "prior_context_ever_breached_20"])
        self.assertFalse(annotated.loc[2, "prior_context_active_loss_breach_20"])

    def test_threshold_reentry_summary_counts_breached_trades(self):
        trades = pd.DataFrame(
            {
                "direction": ["short", "short"],
                "entry_timestamp": pd.to_datetime(
                    ["2025-01-01T00:01:00Z", "2025-01-01T00:20:00Z"]
                ),
                "exit_timestamp": pd.to_datetime(
                    ["2025-01-01T00:10:00Z", "2025-01-01T00:30:00Z"]
                ),
                "entry_decision_timestamp": pd.to_datetime(
                    ["2025-01-01T00:00:00Z", "2025-01-01T00:19:00Z"]
                ),
                "exit_decision_timestamp": pd.to_datetime(
                    ["2025-01-01T00:09:00Z", "2025-01-01T00:29:00Z"]
                ),
                "adjusted_pnl": [-25.0, -10.0],
                "dataset_month": ["2025-01", "2025-01"],
                "entry_margin": [1.0, 2.0],
            }
        )
        annotated = online_context_state_diagnostics.annotate_online_context_state(
            trades,
            context_columns=("dataset_month",),
            thresholds=(20.0,),
        )

        summary = online_context_state_diagnostics.threshold_reentry_summary(
            annotated,
            thresholds=(20.0,),
            large_loss_threshold=-15.0,
        )

        breached = summary[
            (summary["threshold"] == 20.0) & (summary["mode"] == "ever_breached")
        ].iloc[0]
        self.assertEqual(breached["trade_count"], 1)
        self.assertAlmostEqual(breached["total_adjusted_pnl"], -10.0)


if __name__ == "__main__":
    unittest.main()
