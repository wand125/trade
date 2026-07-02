from __future__ import annotations

import unittest

import pandas as pd

from scripts.experiments.entry_ev_support_repair_listwise_teacher_diagnostics import (
    feature_selector_summary,
    overview_summary,
    parse_score_specs,
    prepare_teacher_examples,
    quota_teacher_summary,
)


def sample_teacher_rows() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "scenario_label": ["s1", "s1", "s1"],
            "role": ["r", "r", "r"],
            "month": ["2026-01", "2026-01", "2026-02"],
            "side": ["long", "long", "short"],
            "decision_timestamp": [
                "2026-01-01T10:00:00Z",
                "2026-01-01T12:00:00Z",
                "2026-02-01T10:00:00Z",
            ],
            "entry_timestamp": [
                "2026-01-01T10:00:00Z",
                "2026-01-01T12:00:00Z",
                "2026-02-01T10:00:00Z",
            ],
            "exit_timestamp": [
                "2026-01-01T11:00:00Z",
                "2026-01-01T13:00:00Z",
                "2026-02-01T11:00:00Z",
            ],
            "extra_side_needed": [1.0, 1.0, 1.0],
            "actual_pnl_at_hv_chosen_horizon": [1.0, 5.0, -4.0],
            "current_replay_selected": [True, False, True],
            "actual_oracle_greedy_selected": [False, True, True],
            "hv_chosen_pred_pnl": [1.0, 5.0, 2.0],
            "repair_score": [1.0, 4.0, 2.0],
            "hv_chosen_horizon_minutes": [60.0, 60.0, 60.0],
        }
    )


class EntryEvSupportRepairListwiseTeacherDiagnosticsTest(unittest.TestCase):
    def test_parse_score_specs_supports_directions(self) -> None:
        self.assertEqual(
            parse_score_specs("repair_score:desc,harmful:asc"),
            [("repair_score", False), ("harmful", True)],
        )

    def test_teacher_group_summary_marks_singleton_negative(self) -> None:
        quota_columns = ["scenario_label", "role", "month", "side"]
        examples = prepare_teacher_examples(sample_teacher_rows(), quota_columns=quota_columns)
        summary = quota_teacher_summary(examples, quota_columns=quota_columns)
        singleton = summary[summary["month"].eq("2026-02")].iloc[0]
        learnable = summary[summary["month"].eq("2026-01")].iloc[0]

        self.assertFalse(bool(learnable["is_singleton_group"]))
        self.assertAlmostEqual(float(learnable["oracle_delta_vs_current"]), 4.0)
        self.assertTrue(bool(singleton["is_singleton_group"]))
        self.assertTrue(bool(singleton["singleton_negative_current"]))

    def test_feature_selector_summary_scores_observable_teacher_hit(self) -> None:
        quota_columns = ["scenario_label", "role", "month", "side"]
        examples = prepare_teacher_examples(sample_teacher_rows(), quota_columns=quota_columns)
        selectors = feature_selector_summary(
            examples,
            score_specs=[("hv_chosen_pred_pnl", False)],
            quota_columns=quota_columns,
            overlap_columns=["role"],
        )
        scored = selectors[selectors["selector"].eq("hv_chosen_pred_pnl_desc")].iloc[0]

        self.assertAlmostEqual(float(scored["actual_pnl_sum"]), 1.0)
        self.assertEqual(int(scored["oracle_overlap_count"]), 2)

    def test_overview_splits_learnable_and_singleton_delta(self) -> None:
        quota_columns = ["scenario_label", "role", "month", "side"]
        examples = prepare_teacher_examples(sample_teacher_rows(), quota_columns=quota_columns)
        groups = quota_teacher_summary(examples, quota_columns=quota_columns)
        selectors = feature_selector_summary(
            examples,
            score_specs=[("hv_chosen_pred_pnl", False)],
            quota_columns=quota_columns,
            overlap_columns=["role"],
        )
        overview = overview_summary(examples, groups, selectors).iloc[0]

        self.assertEqual(int(overview["learnable_group_count"]), 1)
        self.assertEqual(int(overview["singleton_group_count"]), 1)
        self.assertAlmostEqual(float(overview["learnable_oracle_delta_sum"]), 4.0)
        self.assertAlmostEqual(float(overview["singleton_negative_actual_sum"]), -4.0)


if __name__ == "__main__":
    unittest.main()
