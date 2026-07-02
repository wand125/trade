from __future__ import annotations

import unittest

import pandas as pd

from scripts.experiments.entry_ev_horizon_choice_nonoverlap_audit import audit_choices


class EntryEvHorizonChoiceNonoverlapAuditTest(unittest.TestCase):
    def test_nonoverlap_keeps_highest_score_non_overlapping_rows(self) -> None:
        frame = pd.DataFrame(
            {
                "family": ["f", "f", "f"],
                "role": ["r", "r", "r"],
                "month": ["2026-01", "2026-01", "2026-01"],
                "row_scope": ["available_candidates"] * 3,
                "decision_timestamp": [
                    "2026-01-01T00:00:00Z",
                    "2026-01-01T00:10:00Z",
                    "2026-01-01T02:00:00Z",
                ],
                "prob_threshold": [0.6, 0.6, 0.6],
                "ev_threshold": [2.0, 2.0, 2.0],
                "tail_prob_threshold": [0.3, 0.3, 0.3],
                "require_model_used": [True, True, True],
                "hv_chosen_horizon_minutes": [60, 60, 60],
                "hv_chosen_score": [5.0, 10.0, 1.0],
                "actual_pnl_at_hv_chosen_horizon": [1.0, 2.0, 3.0],
                "hv_choice_executable": [True, True, True],
                "hv_choice_regret": [0.0, 0.0, 0.0],
                "hv_choice_model_used": [True, True, True],
            }
        )

        summary, choices = audit_choices(frame, sort_column="hv_chosen_score")

        self.assertEqual(int(summary.iloc[0]["raw_chosen_count"]), 3)
        self.assertEqual(int(summary.iloc[0]["nonoverlap_chosen_count"]), 2)
        self.assertEqual(float(summary.iloc[0]["nonoverlap_actual_pnl_sum"]), 5.0)
        self.assertEqual(
            choices["decision_timestamp"].astype(str).tolist(),
            ["2026-01-01 00:10:00+00:00", "2026-01-01 02:00:00+00:00"],
        )


if __name__ == "__main__":
    unittest.main()
