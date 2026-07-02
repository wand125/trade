from __future__ import annotations

import unittest

import pandas as pd

from scripts.experiments.entry_ev_post_exit_path_diagnostics import (
    cooldown_grid_summary,
    enrich_trade_sequence,
    summarize_group,
)


def trades_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "source": ["s", "s", "s"],
            "family": ["f", "f", "f"],
            "variant": ["v", "v", "v"],
            "candidate": ["c", "c", "c"],
            "month": ["2026-01", "2026-01", "2026-01"],
            "direction": ["long", "long", "short"],
            "entry_timestamp": [
                "2026-01-01 00:00:00+00:00",
                "2026-01-01 00:20:00+00:00",
                "2026-01-01 02:00:00+00:00",
            ],
            "exit_timestamp": [
                "2026-01-01 00:01:00+00:00",
                "2026-01-01 00:21:00+00:00",
                "2026-01-01 02:01:00+00:00",
            ],
            "entry_decision_timestamp": [
                "2025-12-31 23:59:00+00:00",
                "2026-01-01 00:19:00+00:00",
                "2026-01-01 01:59:00+00:00",
            ],
            "exit_decision_timestamp": [
                "2026-01-01 00:00:00+00:00",
                "2026-01-01 00:20:00+00:00",
                "2026-01-01 02:00:00+00:00",
            ],
            "adjusted_pnl": [-2.0, -1.5, 3.0],
            "holding_minutes": [1.0, 1.0, 1.0],
        }
    )


class EntryEvPostExitPathDiagnosticsTest(unittest.TestCase):
    def test_enrich_trade_sequence_adds_prev_exit_features(self) -> None:
        enriched = enrich_trade_sequence(trades_frame(), large_loss_threshold=-2.0)

        self.assertEqual(enriched["trade_index_in_month"].tolist(), [1, 2, 3])
        self.assertTrue(bool(enriched.loc[1, "prev_was_loss"]))
        self.assertTrue(bool(enriched.loc[1, "same_side_as_prev"]))
        self.assertEqual(enriched.loc[1, "decision_minutes_since_prev_exit"], 19.0)
        self.assertEqual(enriched.loc[1, "post_exit_gap_bucket"], "15-30")

    def test_cooldown_grid_estimates_removed_pnl(self) -> None:
        enriched = enrich_trade_sequence(trades_frame(), large_loss_threshold=-2.0)

        summary = cooldown_grid_summary(
            enriched,
            cooldown_minutes=[30],
            prev_loss_thresholds=[0],
        )

        self.assertEqual(summary.loc[0, "flagged_trade_count"], 1)
        self.assertEqual(summary.loc[0, "flagged_pnl"], -1.5)
        self.assertEqual(summary.loc[0, "delta_if_removed_no_replacement"], 1.5)
        self.assertEqual(summary.loc[0, "kept_pnl_if_removed_no_replacement"], 1.0)

    def test_summarize_group_reports_loss_and_win_pnl(self) -> None:
        enriched = enrich_trade_sequence(trades_frame(), large_loss_threshold=-2.0)

        summary = summarize_group(enriched, ["source", "month"])

        self.assertEqual(summary.loc[0, "trade_count"], 3)
        self.assertEqual(summary.loc[0, "loss_count"], 2)
        self.assertEqual(summary.loc[0, "loss_pnl"], -3.5)
        self.assertEqual(summary.loc[0, "win_pnl"], 3.0)


if __name__ == "__main__":
    unittest.main()
