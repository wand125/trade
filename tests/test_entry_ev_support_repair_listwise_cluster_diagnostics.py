from __future__ import annotations

import unittest

import pandas as pd

from scripts.experiments.entry_ev_support_repair_listwise_cluster_diagnostics import (
    add_selector_flags,
    assign_interval_clusters,
    prepare_stateful_universe,
    quota_group_summary,
    selector_summary,
)


def sample_rows() -> tuple[pd.DataFrame, pd.DataFrame]:
    base = {
        "scenario_label": ["s1", "s1", "s1", "s1"],
        "role": ["r", "r", "r", "r"],
        "family": ["f", "f", "f", "f"],
        "month": ["2026-01", "2026-01", "2026-01", "2026-01"],
        "side": ["long", "long", "long", "long"],
        "needed_side": ["long", "long", "long", "long"],
        "extra_side_needed": [1.0, 1.0, 1.0, 1.0],
        "decision_timestamp": [
            "2026-01-01T10:00:00Z",
            "2026-01-01T10:10:00Z",
            "2026-01-01T10:20:00Z",
            "2026-01-01T12:00:00Z",
        ],
        "entry_timestamp": [
            "2026-01-01T10:00:00Z",
            "2026-01-01T10:10:00Z",
            "2026-01-01T10:20:00Z",
            "2026-01-01T12:00:00Z",
        ],
        "exit_timestamp": [
            "2026-01-01T11:00:00Z",
            "2026-01-01T11:10:00Z",
            "2026-01-01T11:20:00Z",
            "2026-01-01T13:00:00Z",
        ],
        "hv_chosen_horizon_minutes": [60.0, 60.0, 60.0, 60.0],
        "actual_pnl_at_hv_chosen_horizon": [5.0, 9.0, -2.0, 20.0],
        "adjusted_pnl": [5.0, 9.0, -2.0, 20.0],
        "hv_chosen_pred_pnl": [8.0, 7.0, 2.0, 10.0],
        "hv_chosen_pred_executable_prob": [0.8, 0.8, 0.8, 0.8],
        "hv_chosen_pred_tail_loss_prob": [0.2, 0.3, 0.1, 0.2],
        "hv_chosen_pred_harmful_overestimate_prob": [0.5, 0.2, 0.0, 0.4],
        "repair_score": [10.0, 9.0, 8.0, 7.0],
        "repair_expected_pnl": [8.0, 7.0, 2.0, 10.0],
        "repair_support_success_proxy": [0.4, 0.4, 0.4, 0.4],
        "support_reduction_value": [1.0, 1.0, 1.0, 1.0],
    }
    frame = pd.DataFrame(base)
    additions = frame.iloc[[0]].copy()
    additions["addition_rank"] = [1]
    rejections = frame.iloc[[1, 2, 3]].copy()
    rejections["reject_reason"] = ["quota_full", "pred_pnl_floor", "quota_full"]
    return additions, rejections


class EntryEvSupportRepairListwiseClusterDiagnosticsTest(unittest.TestCase):
    def test_prepare_stateful_universe_keeps_selected_and_allowed_rejections(self) -> None:
        additions, rejections = sample_rows()

        universe = prepare_stateful_universe(
            additions,
            rejections,
            scenario_label="s1",
            include_reject_reasons=["quota_full"],
        )

        self.assertEqual(len(universe), 3)
        self.assertEqual(int(universe["current_selected"].sum()), 1)
        self.assertNotIn("pred_pnl_floor", set(universe["reject_reason"]))

    def test_actual_oracle_uses_quota_and_overlap_constraints(self) -> None:
        additions, rejections = sample_rows()
        universe = prepare_stateful_universe(
            additions,
            rejections,
            scenario_label="s1",
            include_reject_reasons=["quota_full"],
        )
        universe = assign_interval_clusters(
            universe,
            cluster_columns=["scenario_label", "role", "month", "side"],
            cluster_gap_minutes=0.0,
        )
        universe = add_selector_flags(
            universe,
            quota_columns=["scenario_label", "role", "month", "side"],
            overlap_columns=["role"],
        )

        summary = selector_summary(universe)
        current = summary[summary["selector"].eq("current_replay")].iloc[0]
        oracle = summary[summary["selector"].eq("actual_oracle_greedy")].iloc[0]
        repair = summary[summary["selector"].eq("repair_score_greedy")].iloc[0]

        self.assertAlmostEqual(float(current["actual_pnl_sum"]), 5.0)
        self.assertAlmostEqual(float(oracle["actual_pnl_sum"]), 20.0)
        self.assertAlmostEqual(float(repair["actual_pnl_sum"]), 5.0)

    def test_interval_clusters_split_non_overlapping_episodes(self) -> None:
        additions, rejections = sample_rows()
        universe = prepare_stateful_universe(
            additions,
            rejections,
            scenario_label="s1",
            include_reject_reasons=["quota_full"],
        )
        clustered = assign_interval_clusters(
            universe,
            cluster_columns=["scenario_label", "role", "month", "side"],
            cluster_gap_minutes=0.0,
        )

        self.assertEqual(clustered["interval_cluster_id"].nunique(), 2)

    def test_quota_group_summary_tracks_oracle_delta(self) -> None:
        additions, rejections = sample_rows()
        universe = prepare_stateful_universe(
            additions,
            rejections,
            scenario_label="s1",
            include_reject_reasons=["quota_full"],
        )
        universe = assign_interval_clusters(
            universe,
            cluster_columns=["scenario_label", "role", "month", "side"],
            cluster_gap_minutes=0.0,
        )
        universe = add_selector_flags(
            universe,
            quota_columns=["scenario_label", "role", "month", "side"],
            overlap_columns=["role"],
        )

        row = quota_group_summary(
            universe,
            quota_columns=["scenario_label", "role", "month", "side"],
        ).iloc[0]

        self.assertAlmostEqual(float(row["current_replay_actual_sum"]), 5.0)
        self.assertAlmostEqual(float(row["actual_oracle_greedy_actual_sum"]), 20.0)
        self.assertAlmostEqual(float(row["oracle_delta_vs_current"]), 15.0)


if __name__ == "__main__":
    unittest.main()
