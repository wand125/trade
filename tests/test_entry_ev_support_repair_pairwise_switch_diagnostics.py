from __future__ import annotations

import unittest

import pandas as pd

from scripts.experiments.entry_ev_support_repair_pairwise_switch_diagnostics import (
    build_pairwise_examples,
    choose_scenario,
    listwise_switch_summary,
    pairwise_rule_summary,
)


def sample_candidates() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "scenario_label": ["s1", "s1", "s1"],
            "role": ["r", "r", "r"],
            "family": ["f", "f", "f"],
            "month": ["2026-01", "2026-01", "2026-01"],
            "side": ["long", "long", "long"],
            "needed_side": ["long", "long", "long"],
            "decision_timestamp": [
                "2026-01-01T10:00:00Z",
                "2026-01-01T10:10:00Z",
                "2026-01-01T10:20:00Z",
            ],
            "hv_chosen_horizon_minutes": [60.0, 60.0, 60.0],
            "actual_pnl_at_hv_chosen_horizon": [5.0, 8.0, 1.0],
            "hv_chosen_pred_pnl": [4.0, 3.0, 4.5],
            "hv_chosen_pred_executable_prob": [0.8, 0.7, 0.9],
            "hv_chosen_pred_tail_loss_prob": [0.2, 0.1, 0.3],
            "hv_chosen_pred_harmful_overestimate_prob": [0.4, 0.1, 0.0],
            "repair_score": [10.0, 9.0, 11.0],
            "repair_support_success_proxy": [0.6, 0.6, 0.6],
            "support_reduction_value": [1.0, 1.0, 1.0],
            "combined_regime": ["range", "range", "range"],
            "session_regime": ["asia", "asia", "asia"],
            "near_miss_bucket": ["one_failed", "one_failed", "one_failed"],
        }
    )


class EntryEvSupportRepairPairwiseSwitchDiagnosticsTest(unittest.TestCase):
    def test_pairwise_examples_compare_selected_with_near_alternatives(self) -> None:
        candidates = sample_candidates()
        additions = candidates.iloc[[0]].copy()
        additions["addition_rank"] = [1]

        pairs = build_pairwise_examples(
            candidates,
            additions,
            group_columns=["scenario_label", "role", "month", "side"],
            near_window_minutes=30.0,
            max_alternatives_per_choice=10,
            min_actual_delta=0.0,
            min_harmful_delta=0.0,
        )

        self.assertEqual(len(pairs), 2)
        self.assertCountEqual(pairs["switch_actual_delta"].round(6).tolist(), [3.0, -4.0])
        self.assertTrue(pairs["harmful_prefers_alt"].all())

    def test_listwise_summary_tracks_best_actual_and_lowest_harmful_alternatives(self) -> None:
        candidates = sample_candidates()
        additions = candidates.iloc[[0]].copy()
        additions["addition_rank"] = [1]
        pairs = build_pairwise_examples(
            candidates,
            additions,
            group_columns=["scenario_label", "role", "month", "side"],
            near_window_minutes=30.0,
            max_alternatives_per_choice=10,
            min_actual_delta=0.0,
            min_harmful_delta=0.0,
        )

        summary = listwise_switch_summary(pairs, min_actual_delta=0.0).iloc[0]

        self.assertAlmostEqual(float(summary["best_actual_switch_delta"]), 3.0)
        self.assertAlmostEqual(float(summary["lowest_harmful_switch_delta"]), -4.0)
        self.assertEqual(int(summary["harmful_correct_count"]), 1)
        self.assertEqual(int(summary["harmful_wrong_count"]), 1)

    def test_rule_summary_counts_harmful_lower_false_positive(self) -> None:
        candidates = sample_candidates()
        additions = candidates.iloc[[0]].copy()
        pairs = build_pairwise_examples(
            candidates,
            additions,
            group_columns=["scenario_label", "role", "month", "side"],
            near_window_minutes=30.0,
            max_alternatives_per_choice=10,
            min_actual_delta=0.0,
            min_harmful_delta=0.0,
        )

        rules = pairwise_rule_summary(
            pairs,
            switch_thresholds=[0.0],
            harmful_deltas=[0.0],
        )
        row = rules[rules["rule"].eq("harmful_lower_alt_ge_0")].iloc[0]

        self.assertEqual(int(row["pair_count"]), 2)
        self.assertEqual(int(row["switch_improves_count"]), 1)
        self.assertEqual(int(row["switch_hurts_count"]), 1)

    def test_choose_scenario_uses_best_summary_row(self) -> None:
        summary = pd.DataFrame(
            {
                "scenario_label": ["bad", "good"],
                "selector_pass": [False, False],
                "combined_total_pnl": [10.0, 20.0],
                "month_pnl_min": [1.0, -1.0],
                "remaining_extra_trades_needed": [0, 3],
            }
        )

        self.assertEqual(choose_scenario(summary, ""), "good")


if __name__ == "__main__":
    unittest.main()
