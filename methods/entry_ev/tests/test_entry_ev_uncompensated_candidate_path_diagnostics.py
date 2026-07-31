from __future__ import annotations

import unittest

import pandas as pd

from scripts.experiments.entry_ev_uncompensated_candidate_path_diagnostics import (
    add_context_targets,
    add_sequence_state,
    normalize_trade_paths,
    summarize_candidates,
    summarize_month_paths,
)


def trade_paths() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "source": ["s"] * 5,
            "role": ["r"] * 5,
            "family": ["f"] * 5,
            "variant": ["uncomp", "uncomp", "uncomp", "comp", "comp"],
            "candidate": ["c"] * 5,
            "month": ["2026-01"] * 5,
            "direction": ["long", "long", "short", "long", "long"],
            "combined_regime": [
                "range_normal_vol",
                "range_normal_vol",
                "down_low_vol",
                "range_normal_vol",
                "range_normal_vol",
            ],
            "session_regime": ["asia", "asia", "london", "asia", "asia"],
            "entry_decision_timestamp": [
                "2026-01-01 00:00:00+00:00",
                "2026-01-01 01:00:00+00:00",
                "2026-01-01 02:00:00+00:00",
                "2026-01-01 00:00:00+00:00",
                "2026-01-01 01:00:00+00:00",
            ],
            "exit_decision_timestamp": [
                "2026-01-01 00:10:00+00:00",
                "2026-01-01 01:10:00+00:00",
                "2026-01-01 02:10:00+00:00",
                "2026-01-01 00:10:00+00:00",
                "2026-01-01 01:10:00+00:00",
            ],
            "adjusted_pnl": [-3.0, 1.0, 2.0, -3.0, 5.0],
        }
    )


class EntryEvUncompensatedCandidatePathDiagnosticsTest(unittest.TestCase):
    def test_context_targets_are_path_variant_specific(self) -> None:
        normalized = normalize_trade_paths(trade_paths(), large_loss_threshold=-2.0)
        enriched = add_context_targets(
            normalized,
            context_columns=["direction", "combined_regime", "session_regime"],
            large_win_threshold=5.0,
        )

        uncomp = enriched[enriched["variant"].eq("uncomp") & enriched["adjusted_pnl"].eq(-3.0)].iloc[0]
        comp = enriched[enriched["variant"].eq("comp") & enriched["adjusted_pnl"].eq(-3.0)].iloc[0]

        self.assertTrue(bool(uncomp["large_loss_uncompensated_by_context"]))
        self.assertFalse(bool(comp["large_loss_uncompensated_by_context"]))
        self.assertTrue(bool(comp["large_loss_compensated_by_context"]))

    def test_normalize_excludes_entry_blocked_rows_by_default(self) -> None:
        frame = pd.DataFrame(
            {
                "source": ["s", "s"],
                "role": ["r", "r"],
                "family": ["f", "f"],
                "variant": ["v", "v"],
                "candidate": ["c", "c"],
                "month": ["2026-01", "2026-01"],
                "direction": ["long", "long"],
                "entry_blocked": [False, True],
                "adjusted_pnl": [1.0, -10.0],
            }
        )

        normalized = normalize_trade_paths(frame, large_loss_threshold=-2.0)
        included = normalize_trade_paths(
            frame,
            large_loss_threshold=-2.0,
            exclude_entry_blocked=False,
        )

        self.assertEqual(len(normalized), 1)
        self.assertEqual(normalized["adjusted_pnl"].sum(), 1.0)
        self.assertEqual(len(included), 2)

    def test_month_and_candidate_summary_count_next_winner_targets(self) -> None:
        enriched = add_sequence_state(
            add_context_targets(
                normalize_trade_paths(trade_paths(), large_loss_threshold=-2.0),
                context_columns=["direction", "combined_regime", "session_regime"],
                large_win_threshold=5.0,
            )
        )
        monthly = summarize_month_paths(enriched)
        candidates = summarize_candidates(monthly)
        uncomp = candidates[candidates["variant"].eq("uncomp")].iloc[0]
        comp = candidates[candidates["variant"].eq("comp")].iloc[0]

        self.assertEqual(uncomp["uncompensated_target_count"], 1)
        self.assertEqual(uncomp["uncompensated_target_next_win_count"], 1)
        self.assertEqual(uncomp["uncompensated_target_next_win_pnl"], 1.0)
        self.assertEqual(comp["uncompensated_target_count"], 0)
        self.assertGreater(comp["month_pnl_min"], uncomp["month_pnl_min"])


if __name__ == "__main__":
    unittest.main()
