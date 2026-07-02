from __future__ import annotations

import unittest

import pandas as pd

from scripts.experiments.entry_ev_uncompensated_sequence_state_diagnostics import (
    add_sequence_state,
    risk_threshold_summary,
    sequence_state_summary,
)


def prediction_rows() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "supervised_target_mode": ["pnl", "pnl", "pnl"],
            "large_loss_feature_set": ["base", "base", "base"],
            "uncompensated_feature_set": ["base", "base", "base"],
            "source": ["s", "s", "s"],
            "role": ["r", "r", "r"],
            "family": ["f", "f", "f"],
            "variant": ["v", "v", "v"],
            "candidate": ["c", "c", "c"],
            "month": ["2026-01", "2026-01", "2026-01"],
            "direction": ["long", "long", "short"],
            "combined_regime": ["range_normal_vol", "range_normal_vol", "down_high_vol"],
            "session_regime": ["asia", "asia", "london"],
            "context_key": ["long|range|asia", "long|range|asia", "short|down|london"],
            "entry_decision_timestamp": [
                "2026-01-01 00:00:00+00:00",
                "2026-01-01 01:10:00+00:00",
                "2026-01-01 03:00:00+00:00",
            ],
            "exit_decision_timestamp": [
                "2026-01-01 00:10:00+00:00",
                "2026-01-01 01:30:00+00:00",
                "2026-01-01 03:20:00+00:00",
            ],
            "adjusted_pnl": [-2.0, 3.0, -4.0],
            "is_large_loss": [False, False, True],
            "uncompensated_loss_target": [True, False, True],
            "pred_uncompensated_loss_prob": [0.9, 0.8, 0.1],
            "pred_large_loss_prob": [0.2, 0.3, 0.7],
        }
    )


class EntryEvUncompensatedSequenceStateDiagnosticsTest(unittest.TestCase):
    def test_add_sequence_state_adds_prev_next_path_features(self) -> None:
        enriched = add_sequence_state(prediction_rows())

        self.assertEqual(enriched["trade_index_in_month"].tolist(), [1, 2, 3])
        self.assertEqual(enriched["month_trade_count"].tolist(), [3, 3, 3])
        self.assertEqual(enriched.loc[0, "prev_result_bucket"], "first")
        self.assertEqual(enriched.loc[0, "next_result_bucket"], "next_win")
        self.assertEqual(enriched.loc[1, "prev_result_bucket"], "prev_loss")
        self.assertEqual(enriched.loc[1, "next_result_bucket"], "next_loss")
        self.assertEqual(enriched.loc[1, "decision_minutes_since_prev_exit"], 60.0)
        self.assertTrue(bool(enriched.loc[1, "same_context_as_prev"]))
        self.assertTrue(bool(enriched.loc[1, "prev_was_target"]))

    def test_risk_threshold_summary_counts_removed_pnl_and_neighbor_wins(self) -> None:
        enriched = add_sequence_state(prediction_rows())
        summary = risk_threshold_summary(enriched, thresholds=[0.5], quantiles=[])
        row = summary.iloc[0]

        self.assertEqual(row["flagged_trade_count"], 2)
        self.assertEqual(row["flagged_pnl"], 1.0)
        self.assertEqual(row["block_delta_if_removed"], -1.0)
        self.assertEqual(row["flagged_target_count"], 1)
        self.assertEqual(row["target_recall"], 0.5)
        self.assertEqual(row["flagged_next_win_count"], 1)
        self.assertEqual(row["flagged_next_win_pnl"], 3.0)

    def test_sequence_state_summary_groups_uncompensated_targets(self) -> None:
        enriched = add_sequence_state(prediction_rows())
        summary = sequence_state_summary(
            enriched,
            group_specs=[["prev_result_bucket"]],
        )
        prev_loss = summary[summary["sequence_group_key"].eq("prev_loss")].iloc[0]

        self.assertEqual(prev_loss["row_count"], 1)
        self.assertEqual(prev_loss["target_count"], 0)
        self.assertEqual(prev_loss["total_pnl"], 3.0)


if __name__ == "__main__":
    unittest.main()
