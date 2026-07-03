from __future__ import annotations

import unittest

import pandas as pd

from scripts.experiments.entry_ev_upstream_universe_coverage_diagnostics import (
    classify_upstream_gap,
    filter_repair_targets,
    role_to_family,
)


def repair_target_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "role": ["refit2025_validation", "fresh2024_validation"],
            "family": ["refit2025", "fresh2024"],
            "month": ["2025-03", "2024-11"],
            "candidate": ["c", "c"],
            "variant": ["branch__entryblock_rule_a", "branch__entryblock_rule_a"],
            "entry_block_rule": ["rule_a", "rule_a"],
            "extra_long_needed": [0, 1],
            "extra_short_needed": [0, 0],
            "total_adjusted_pnl": [-0.5, -4.0],
            "month_pnl_hurdle": [0.5, 4.0],
        }
    )


class EntryEvUpstreamUniverseCoverageDiagnosticsTest(unittest.TestCase):
    def test_role_to_family_removes_validation_suffix(self) -> None:
        self.assertEqual(role_to_family("refit2025_validation"), "refit2025")

    def test_filter_repair_targets_keeps_zero_extra_rows(self) -> None:
        filtered = filter_repair_targets(
            repair_target_frame(),
            candidate="c",
            variant_contains="branch",
            entry_block_rule="rule_a",
        )

        self.assertEqual(len(filtered), 2)
        self.assertEqual(int(filtered.iloc[0]["extra_short_needed"]), 0)

    def test_classifies_floor_breach_zero_extra_before_prediction_filters(self) -> None:
        stage = classify_upstream_gap(
            pd.Series(
                {
                    "repair_target_present": True,
                    "repair_target_emitted_by_00318": False,
                    "month_floor_breach": True,
                    "raw_prediction_rows": 100,
                    "side_rows": 100,
                    "candidate_rows": 10,
                    "candidate_available_rows": 5,
                }
            )
        )

        self.assertEqual(stage, "repair_target_has_no_extra_side_need")

    def test_classifies_no_prediction_rows_after_emitted_target(self) -> None:
        stage = classify_upstream_gap(
            pd.Series(
                {
                    "repair_target_present": True,
                    "repair_target_emitted_by_00318": True,
                    "month_floor_breach": True,
                    "raw_prediction_rows": 0,
                }
            )
        )

        self.assertEqual(stage, "no_prediction_rows")

    def test_classifies_stateful_overlap_after_candidate_filter(self) -> None:
        stage = classify_upstream_gap(
            pd.Series(
                {
                    "repair_target_present": True,
                    "repair_target_emitted_by_00318": True,
                    "month_floor_breach": True,
                    "raw_prediction_rows": 100,
                    "side_rows": 50,
                    "holding_ok_rows": 40,
                    "candidate_rows": 3,
                    "candidate_available_rows": 0,
                }
            )
        )

        self.assertEqual(stage, "stateful_overlap_filtered")


if __name__ == "__main__":
    unittest.main()
