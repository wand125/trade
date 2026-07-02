from __future__ import annotations

import unittest

import pandas as pd

from scripts.experiments.entry_ev_isolated_exit_capture_diagnostics import (
    add_exit_capture_features,
    add_sequence_features,
    normalize_enriched_trades,
    replacement_grid_summary,
    summarize_groups,
)


def enriched_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "source": ["s", "s", "s"],
            "role": ["r", "r", "r"],
            "family": ["f", "f", "f"],
            "variant": ["v", "v", "v"],
            "candidate": ["c", "c", "c"],
            "month": ["2026-01", "2026-01", "2026-01"],
            "direction": ["long", "short", "short"],
            "entry_timestamp": [
                "2026-01-01 00:00:00+00:00",
                "2026-01-01 00:20:00+00:00",
                "2026-01-02 02:00:00+00:00",
            ],
            "exit_timestamp": [
                "2026-01-01 00:01:00+00:00",
                "2026-01-01 00:21:00+00:00",
                "2026-01-02 02:01:00+00:00",
            ],
            "entry_decision_timestamp": [
                "2025-12-31 23:59:00+00:00",
                "2026-01-01 00:19:00+00:00",
                "2026-01-02 01:59:00+00:00",
            ],
            "exit_decision_timestamp": [
                "2026-01-01 00:00:00+00:00",
                "2026-01-01 00:20:00+00:00",
                "2026-01-02 02:00:00+00:00",
            ],
            "adjusted_pnl": [-3.0, 2.0, -2.5],
            "holding_minutes": [1.0, 1.0, 1.0],
            "actual_taken_best_adjusted_pnl": [10.0, 4.0, 8.0],
            "actual_taken_best_holding_minutes": [30.0, 1.0, 40.0],
            "exit_regret": [13.0, 2.0, 10.5],
            "pred_taken_ev": [12.0, 5.0, 9.0],
            "long_fixed_60m_adjusted_pnl": [4.0, 99.0, 99.0],
            "short_fixed_60m_adjusted_pnl": [99.0, 1.0, 3.0],
            "combined_regime": ["range", "range", "range"],
            "session_regime": ["asia", "asia", "asia"],
        }
    )


class EntryEvIsolatedExitCaptureDiagnosticsTest(unittest.TestCase):
    def test_normalize_selects_fixed_horizon_by_direction(self) -> None:
        normalized = normalize_enriched_trades(enriched_frame(), fixed_horizons=[60])

        self.assertEqual(normalized.loc[0, "actual_taken_fixed_60m_adjusted_pnl"], 4.0)
        self.assertEqual(normalized.loc[1, "actual_taken_fixed_60m_adjusted_pnl"], 1.0)
        self.assertEqual(normalized.loc[2, "fixed_60m_delta_vs_realized"], 5.5)

    def test_sequence_marks_first_and_long_gap_as_isolated(self) -> None:
        normalized = normalize_enriched_trades(enriched_frame(), fixed_horizons=[60])
        sequenced = add_sequence_features(
            normalized,
            large_loss_threshold=-2.0,
            long_gap_minutes=1440.0,
        )

        self.assertEqual(sequenced.loc[0, "prev_result_bucket"], "first")
        self.assertTrue(bool(sequenced.loc[0, "isolated_context"]))
        self.assertFalse(bool(sequenced.loc[1, "isolated_context"]))
        self.assertTrue(bool(sequenced.loc[2, "long_gap_after_prev_exit"]))
        self.assertTrue(bool(sequenced.loc[2, "isolated_large_loss"]))

    def test_exit_capture_summary_counts_isolated_failures(self) -> None:
        normalized = normalize_enriched_trades(enriched_frame(), fixed_horizons=[60])
        sequenced = add_sequence_features(
            normalized,
            large_loss_threshold=-2.0,
            long_gap_minutes=1440.0,
        )
        captured = add_exit_capture_features(
            sequenced,
            min_oracle_edge=5.0,
            low_capture_threshold=0.25,
            large_exit_regret_threshold=5.0,
            hold_gap_minutes=5.0,
        )

        summary = summarize_groups(
            captured,
            ["source", "role"],
            fixed_horizons=[60],
        )

        self.assertEqual(summary.loc[0, "isolated_large_loss_count"], 2)
        self.assertEqual(summary.loc[0, "isolated_large_loss_capture_failure_count"], 2)
        self.assertEqual(summary.loc[0, "oracle_after_actual_exit_count"], 2)
        self.assertEqual(summary.loc[0, "fixed_60m_loss_improved_count"], 2)
        self.assertEqual(summary.loc[0, "fixed_60m_loss_delta_sum"], 12.5)

    def test_replacement_grid_reports_month_floor(self) -> None:
        normalized = normalize_enriched_trades(enriched_frame(), fixed_horizons=[60])
        sequenced = add_sequence_features(
            normalized,
            large_loss_threshold=-2.0,
            long_gap_minutes=1440.0,
        )
        captured = add_exit_capture_features(
            sequenced,
            min_oracle_edge=5.0,
            low_capture_threshold=0.25,
            large_exit_regret_threshold=5.0,
            hold_gap_minutes=5.0,
        )

        overall, monthly = replacement_grid_summary(
            captured,
            fixed_horizons=[60],
            rules=["isolated_large_loss_capture_failure"],
        )

        self.assertEqual(overall.loc[0, "flagged_trade_count"], 2)
        self.assertEqual(overall.loc[0, "delta_if_replaced_no_replay"], 12.5)
        self.assertEqual(overall.loc[0, "total_pnl_if_replaced_no_replay"], 9.0)
        self.assertEqual(overall.loc[0, "month_min_if_replaced_no_replay"], 9.0)
        self.assertEqual(monthly.loc[0, "pnl_if_replaced_no_replay"], 9.0)


if __name__ == "__main__":
    unittest.main()
