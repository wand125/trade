from __future__ import annotations

import unittest

import pandas as pd

from scripts.experiments.entry_ev_entry_block_prediction_flags import (
    add_entry_block_prediction_flags,
)


class EntryEvEntryBlockPredictionFlagsTest(unittest.TestCase):
    def test_adds_short_rollover_and_london_midloss_flags(self) -> None:
        frame = pd.DataFrame(
            {
                "decision_timestamp": [
                    "2025-01-01 23:00:00+00:00",
                    "2025-01-01 12:00:00+00:00",
                    "2025-01-01 10:00:00+00:00",
                ],
                "session_regime": ["rollover", "london", "asia"],
                "combined_regime": ["down_high_vol", "range_normal_vol", "down_low_vol"],
                "pred_short_exit_event_prob_2": [0.5, 0.35, 0.2],
                "pred_best_side_prob_1": [0.60, 0.40, 0.50],
                "pred_best_side_prob_-1": [0.40, 0.60, 0.50],
            }
        )

        enriched = add_entry_block_prediction_flags(frame)

        self.assertEqual(
            enriched["entryblock_short_rollover_lossprob_ge0p4"].tolist(),
            ["true", "false", "false"],
        )
        self.assertEqual(
            enriched["entryblock_short_rollover_sidegap_neg"].tolist(),
            ["true", "false", "false"],
        )
        self.assertEqual(
            enriched["entryblock_short_down_high_vol_rollover_lossprob_ge0p4"].tolist(),
            ["true", "false", "false"],
        )
        self.assertEqual(
            enriched["entryblock_short_entry_hour_23_lossprob_ge0p4"].tolist(),
            ["true", "false", "false"],
        )
        self.assertEqual(
            enriched["entryblock_short_london_midloss_sidegap_pos"].tolist(),
            ["false", "true", "false"],
        )
        self.assertEqual(
            enriched["entryblock_short_rollover_or_london_midloss"].tolist(),
            ["true", "true", "false"],
        )


if __name__ == "__main__":
    unittest.main()
