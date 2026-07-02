from __future__ import annotations

import unittest

import pandas as pd

from scripts.experiments.entry_ev_support_repair_target_coverage_diagnostics import (
    horizon_long_frame,
    normalize_predictions,
    select_target_rows,
    summarize_target_groups,
    summarize_thresholds,
)


def sample_prediction_frame() -> pd.DataFrame:
    frame = pd.DataFrame(
        {
            "family": ["f", "f", "f"],
            "role": ["r", "r", "r"],
            "month": ["2026-01", "2026-01", "2026-02"],
            "decision_timestamp": [
                "2026-01-01T00:00:00Z",
                "2026-01-01T01:00:00Z",
                "2026-02-01T00:00:00Z",
            ],
            "row_scope": ["available_candidates", "available_candidates", "greedy_selected"],
            "selection_bucket": ["not_selected", "not_selected", "one_failed_strict_stage"],
            "selected_any": [False, False, True],
            "side": ["long", "long", "short"],
            "needed_side": ["long", "long", "short"],
            "extra_side_needed": [1, 1, 1],
            "stateful_available": [True, True, True],
            "strict_side_specific": [False, False, False],
            "relaxed_side_specific": [False, False, False],
            "one_failed_strict_stage": [True, True, True],
            "target_fixed_best_adjusted_pnl": [10.0, -2.0, 5.0],
            "target_fixed_best_horizon_minutes": [240, 60, 720],
            "target_pnl_hurdle": [1.0, 1.0, 2.0],
        }
    )
    for horizon in [60, 240, 720]:
        frame[f"side_fixed_{horizon}m_adjusted_pnl"] = [-1.0, -2.0, -3.0]
        frame[f"pred_hv_{horizon}m_executable_prob"] = [0.1, 0.1, 0.1]
        frame[f"pred_hv_{horizon}m_pnl"] = [-1.0, -1.0, -1.0]
        frame[f"pred_hv_{horizon}m_tail_loss_prob"] = [0.9, 0.9, 0.9]
        frame[f"pred_hv_{horizon}m_executable_model_used"] = [True, True, True]
        frame[f"pred_hv_{horizon}m_pnl_model_used"] = [True, True, True]
        frame[f"pred_hv_{horizon}m_tail_model_used"] = [True, True, True]
    frame.loc[0, "side_fixed_240m_adjusted_pnl"] = 10.0
    frame.loc[0, "pred_hv_240m_executable_prob"] = 0.7
    frame.loc[0, "pred_hv_240m_pnl"] = 1.5
    frame.loc[0, "pred_hv_240m_tail_loss_prob"] = 0.2
    frame.loc[2, "side_fixed_720m_adjusted_pnl"] = 5.0
    frame.loc[2, "pred_hv_720m_executable_prob"] = 0.8
    frame.loc[2, "pred_hv_720m_pnl"] = -0.5
    frame.loc[2, "pred_hv_720m_tail_loss_prob"] = 0.2
    return frame


class EntryEvSupportRepairTargetCoverageDiagnosticsTest(unittest.TestCase):
    def test_select_target_rows_filters_targets_and_needed_side(self) -> None:
        normalized = normalize_predictions(sample_prediction_frame(), horizons=[60, 240, 720])
        selected = select_target_rows(
            normalized,
            targets=[("r", "2026-01")],
            row_scopes=["available_candidates"],
            target_only=True,
        )

        self.assertEqual(len(selected), 2)
        self.assertEqual(selected["month"].unique().tolist(), ["2026-01"])
        self.assertTrue(selected["side"].eq(selected["needed_side"]).all())

    def test_summarize_target_groups_counts_positive_fixed_best(self) -> None:
        normalized = normalize_predictions(sample_prediction_frame(), horizons=[60, 240, 720])
        selected = select_target_rows(
            normalized,
            targets=[("r", "2026-01")],
            row_scopes=["available_candidates"],
            target_only=True,
        )

        summary = summarize_target_groups(selected, horizons=[60, 240, 720]).iloc[0]

        self.assertEqual(int(summary["candidate_rows"]), 2)
        self.assertEqual(int(summary["fixed_best_positive_rows"]), 1)
        self.assertEqual(float(summary["fixed240_max"]), 10.0)

    def test_threshold_summary_separates_ev_blocked_positive_actuals(self) -> None:
        normalized = normalize_predictions(sample_prediction_frame(), horizons=[60, 240, 720])
        selected = select_target_rows(
            normalized,
            targets=[("r", "2026-02")],
            row_scopes=["greedy_selected"],
            target_only=True,
        )
        horizon_rows = horizon_long_frame(selected, horizons=[60, 240, 720])

        summary = summarize_thresholds(
            horizon_rows,
            prob_thresholds=[0.6],
            ev_thresholds=[0.0],
            tail_prob_thresholds=[0.3],
            require_model_used_options=[True],
        ).iloc[0]

        self.assertEqual(int(summary["actual_positive_horizon_count"]), 1)
        self.assertEqual(int(summary["all_gate_pass_horizon_count"]), 0)
        self.assertEqual(int(summary["positive_actual_blocked_by_ev_count"]), 1)
        self.assertEqual(int(summary["choice_count"]), 0)

    def test_threshold_summary_counts_successful_choice(self) -> None:
        normalized = normalize_predictions(sample_prediction_frame(), horizons=[60, 240, 720])
        selected = select_target_rows(
            normalized,
            targets=[("r", "2026-01")],
            row_scopes=["available_candidates"],
            target_only=True,
        )
        horizon_rows = horizon_long_frame(selected, horizons=[60, 240, 720])

        summary = summarize_thresholds(
            horizon_rows,
            prob_thresholds=[0.6],
            ev_thresholds=[0.0],
            tail_prob_thresholds=[0.3],
            require_model_used_options=[True],
        ).iloc[0]

        self.assertEqual(int(summary["choice_count"]), 1)
        self.assertEqual(float(summary["choice_actual_pnl_sum"]), 10.0)


if __name__ == "__main__":
    unittest.main()
