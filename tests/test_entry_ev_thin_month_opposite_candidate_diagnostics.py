from __future__ import annotations

import unittest

import pandas as pd

from scripts.experiments.entry_ev_thin_month_opposite_candidate_diagnostics import (
    apply_side_penalties,
    greedy_select_available,
    interval_overlaps,
    mark_stateful_available,
)


class EntryEvThinMonthOppositeCandidateDiagnosticsTest(unittest.TestCase):
    def test_interval_overlaps_uses_half_open_intervals(self) -> None:
        intervals = [
            (
                pd.Timestamp("2026-01-01 00:00:00Z"),
                pd.Timestamp("2026-01-01 01:00:00Z"),
            )
        ]

        self.assertTrue(
            interval_overlaps(
                pd.Timestamp("2026-01-01 00:30:00Z"),
                pd.Timestamp("2026-01-01 00:45:00Z"),
                intervals,
            )
        )
        self.assertFalse(
            interval_overlaps(
                pd.Timestamp("2026-01-01 01:00:00Z"),
                pd.Timestamp("2026-01-01 01:30:00Z"),
                intervals,
            )
        )

    def test_side_penalty_subtracts_only_matching_side(self) -> None:
        frame = pd.DataFrame(
            {
                "long_score": [10.0, 10.0],
                "short_score": [12.0, 12.0],
                "block_short": [True, False],
            }
        )

        result = apply_side_penalties(
            frame,
            long_column="long_score",
            short_column="short_score",
            rules=[("short", "block_short", "true", 100.0)],
        )

        self.assertEqual(result["_long_score"].tolist(), [10.0, 10.0])
        self.assertEqual(result["_short_score"].tolist(), [-88.0, 12.0])

    def test_greedy_select_available_respects_current_and_new_intervals(self) -> None:
        rows = pd.DataFrame(
            {
                "decision_timestamp": pd.to_datetime(
                    [
                        "2026-01-01 00:30:00Z",
                        "2026-01-01 01:00:00Z",
                        "2026-01-01 01:20:00Z",
                        "2026-01-01 02:00:00Z",
                    ],
                    utc=True,
                ),
                "side_pred_holding_minutes": [10.0, 30.0, 30.0, 30.0],
                "side_score": [100.0, 90.0, 80.0, 70.0],
                "score_pct": [1.0, 0.9, 0.8, 0.7],
                "side_margin_pct": [1.0, 0.9, 0.8, 0.7],
                "entry_rank_pct": [1.0, 0.9, 0.8, 0.7],
            }
        )
        current = [
            (
                pd.Timestamp("2026-01-01 00:00:00Z"),
                pd.Timestamp("2026-01-01 00:45:00Z"),
            )
        ]
        available = mark_stateful_available(rows, current)

        selected = greedy_select_available(
            available[available["stateful_available"]],
            needed_count=2,
            intervals=current,
        )

        self.assertEqual(
            selected["decision_timestamp"].dt.strftime("%H:%M").tolist(),
            ["01:00", "02:00"],
        )


if __name__ == "__main__":
    unittest.main()
