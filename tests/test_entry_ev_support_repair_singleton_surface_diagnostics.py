from __future__ import annotations

import unittest

import pandas as pd

from scripts.experiments.entry_ev_support_repair_singleton_surface_diagnostics import (
    add_singleton_surface_columns,
    surface_rule_summary,
    unique_rows,
)


class EntryEvSupportRepairSingletonSurfaceDiagnosticsTest(unittest.TestCase):
    def test_risk_rule_flags_only_singleton_rows(self) -> None:
        frame = add_singleton_surface_columns(
            pd.DataFrame(
                {
                    "candidate_id": [0, 1, 2, 3],
                    "scenario_label": ["s1", "s2", "s3", "s3"],
                    "role": ["r1", "r2", "r3", "r3"],
                    "month": ["2026-01", "2026-02", "2026-03", "2026-03"],
                    "side": ["long", "long", "short", "short"],
                    "decision_timestamp": [
                        "2026-01-01T00:00:00Z",
                        "2026-02-01T00:00:00Z",
                        "2026-03-01T00:00:00Z",
                        "2026-03-01T00:05:00Z",
                    ],
                    "extra_side_needed": [1.0, 1.0, 1.0, 1.0],
                    "current_replay_selected": [True, True, True, False],
                    "hv_chosen_horizon_minutes": [720.0, 720.0, 720.0, 720.0],
                    "ranker_hv_720m_prior_mean_pnl": [2.0, -1.0, -2.0, -3.0],
                    "ranker_hv_720m_prior_tail_loss_rate": [0.1, 0.5, 0.8, 0.8],
                    "actual_pnl_at_hv_chosen_horizon": [5.0, -6.0, -7.0, 9.0],
                }
            ),
            quota_columns=["scenario_label", "role", "month", "side"],
        )

        summary = surface_rule_summary(
            frame,
            rules=["singleton_720_prior_mean_neg_tail_ge0p35"],
        )
        row = summary.iloc[0]

        self.assertEqual(int(row["flagged_count"]), 1)
        self.assertEqual(int(row["flagged_current_count"]), 1)
        self.assertAlmostEqual(float(row["flagged_current_actual_sum"]), -6.0)
        self.assertEqual(int(row["current_singleton_loss_count"]), 1)
        self.assertAlmostEqual(float(row["current_loss_capture_rate"]), 1.0)

    def test_unique_rows_deduplicates_cross_scenario_candidates(self) -> None:
        frame = add_singleton_surface_columns(
            pd.DataFrame(
                {
                    "candidate_id": [0, 1],
                    "scenario_label": ["s1", "s2"],
                    "role": ["r1", "r1"],
                    "month": ["2026-01", "2026-01"],
                    "side": ["long", "long"],
                    "decision_timestamp": [
                        "2026-01-01T00:00:00Z",
                        "2026-01-01T00:00:00Z",
                    ],
                    "extra_side_needed": [1.0, 1.0],
                    "current_replay_selected": [True, True],
                    "hv_chosen_horizon_minutes": [720.0, 720.0],
                    "actual_pnl_at_hv_chosen_horizon": [-5.0, -5.0],
                }
            ),
            quota_columns=["scenario_label", "role", "month", "side"],
        )

        deduped = unique_rows(frame)

        self.assertEqual(len(deduped), 1)
        self.assertEqual(deduped.iloc[0]["scenario_label"], "s1")


if __name__ == "__main__":
    unittest.main()
