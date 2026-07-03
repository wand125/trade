from __future__ import annotations

import unittest

import pandas as pd

from scripts.experiments.entry_ev_horizon_confidence_support_audit import (
    add_score_columns,
    choice_summary,
    filter_targets,
    missing_target_summary,
    normalize_scored_examples,
    parse_targets,
)


def sample_scored_examples() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "family": ["f"] * 6,
            "role": ["r"] * 6,
            "month": ["2026-01"] * 6,
            "side": ["long"] * 6,
            "row_scope": ["available_candidates"] * 6,
            "selection_bucket": ["x"] * 6,
            "decision_timestamp": [
                "2026-01-01T00:00:00Z",
                "2026-01-01T00:00:00Z",
                "2026-01-01T00:00:00Z",
                "2026-01-01T00:05:00Z",
                "2026-01-01T00:05:00Z",
                "2026-01-01T00:05:00Z",
            ],
            "hv_chosen_horizon_minutes": [60, 240, 720, 60, 240, 720],
            "horizon_actual_pnl": [-3.0, 5.0, -8.0, 2.0, 3.0, -4.0],
            "ranker_pred_pnl": [0.5, 1.2, 0.1, 1.0, 0.8, 0.7],
            "ranker_pred_delta_vs_60": [0.0, 1.0, 0.0, 0.0, 0.5, 0.1],
            "ranker_pred_executable_prob": [0.3, 0.7, 0.2, 0.6, 0.4, 0.5],
            "ranker_pred_tail_loss_prob": [0.2, 0.1, 0.6, 0.2, 0.1, 0.4],
            "ranker_pred_beats60_prob": [0.2, 0.8, 0.1, 0.5, 0.7, 0.3],
            "ranker_core_model_used": [True] * 6,
        }
    )


class EntryEvHorizonConfidenceSupportAuditTest(unittest.TestCase):
    def test_choice_summary_uses_prediction_scores_not_actual_values(self) -> None:
        rows = normalize_scored_examples(sample_scored_examples())
        rows = add_score_columns(
            rows,
            tail_weight=2.0,
            delta_weight=0.25,
            beats60_weight=0.5,
            executable_weight=1.0,
        )

        summary, choices = choice_summary(rows, score_columns=["score_pnl"])

        self.assertEqual(len(summary), 1)
        row = summary.iloc[0]
        self.assertEqual(int(row["candidate_count"]), 2)
        self.assertAlmostEqual(float(row["chosen_actual_sum"]), 7.0)
        self.assertAlmostEqual(float(row["oracle_actual_sum"]), 8.0)
        self.assertEqual(int(row["chosen_240m_count"]), 1)
        self.assertNotIn("actual", str(row["score_name"]))
        self.assertEqual(len(choices), 2)

    def test_filter_targets_and_missing_targets_track_absent_scope(self) -> None:
        rows = normalize_scored_examples(sample_scored_examples())
        targets = parse_targets("r:2026-01:long,missing:2026-02:short")

        filtered = filter_targets(
            rows,
            targets=targets,
            row_scopes=["available_candidates"],
        )
        missing = missing_target_summary(
            rows,
            targets=targets,
            row_scopes=["available_candidates", "greedy_selected"],
        )

        self.assertEqual(len(filtered), 6)
        present = missing[
            missing["target_key"].eq("r|2026-01|long")
            & missing["row_scope"].eq("available_candidates")
        ].iloc[0]
        absent = missing[missing["target_key"].eq("missing|2026-02|short")].iloc[0]
        self.assertTrue(bool(present["has_rows"]))
        self.assertFalse(bool(absent["has_rows"]))


if __name__ == "__main__":
    unittest.main()
