from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

import pandas as pd


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "experiments"
    / "entry_ev_quantile_candidate_support_diagnostics.py"
)
SPEC = importlib.util.spec_from_file_location(
    "entry_ev_quantile_candidate_support_diagnostics",
    MODULE_PATH,
)
entry_ev_quantile_candidate_support_diagnostics = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = entry_ev_quantile_candidate_support_diagnostics
SPEC.loader.exec_module(entry_ev_quantile_candidate_support_diagnostics)

from entry_ev_quantile_policy_backtest import policy_candidate_from_name


class EntryEvQuantileCandidateSupportDiagnosticsTest(unittest.TestCase):
    def test_summarizes_candidate_gate_funnel(self):
        frame = pd.DataFrame(
            {
                "dataset_month": ["2025-01"] * 4,
                "long_score": [6.0, 4.0, 8.0, 1.0],
                "short_score": [1.0, 0.0, 2.0, 8.0],
                "long_hold": [60.0, 60.0, 60.0, 60.0],
                "short_hold": [60.0, 60.0, 60.0, 60.0],
                "pred_test_selected_score_pct_side_regime_session_month": [
                    0.99,
                    0.99,
                    0.90,
                    0.96,
                ],
                "pred_test_side_gap_pct_side_regime_session_month": [
                    0.95,
                    0.95,
                    0.95,
                    0.96,
                ],
                "pred_test_selected_entry_rank_pct_side_regime_session_month": [
                    0.90,
                    0.90,
                    0.90,
                    0.91,
                ],
            }
        )
        candidate = policy_candidate_from_name(
            "q95_sg95_rank90_floor5_side_regime_session_month"
        )

        base = entry_ev_quantile_candidate_support_diagnostics.add_base_columns(
            frame,
            family="toy",
            long_column="long_score",
            short_column="short_score",
            long_holding_column="long_hold",
            short_holding_column="short_hold",
            min_valid_predicted_hold_minutes=30.0,
        )
        scored = entry_ev_quantile_candidate_support_diagnostics.add_candidate_columns(
            base,
            candidate=candidate,
            score_kind="test",
        )
        summary = (
            entry_ev_quantile_candidate_support_diagnostics.summarize_candidate_group(
                scored,
                candidate=candidate,
            )
        )

        self.assertEqual(summary["valid_prediction_count"], 4)
        self.assertEqual(summary["quantile_all_ok_count"], 3)
        self.assertEqual(summary["quantile_hold_ok_count"], 3)
        self.assertEqual(summary["threshold_after_quantile_hold_count"], 2)
        self.assertEqual(summary["candidate_row_count"], 2)
        self.assertEqual(summary["candidate_long_count"], 1)
        self.assertEqual(summary["candidate_short_count"], 1)
        self.assertEqual(summary["first_zero_stage"], "")

    def test_first_zero_stage_reports_threshold(self):
        row = pd.Series(
            {
                "row_count": 10,
                "valid_prediction_count": 10,
                "selected_holding_ok_count": 10,
                "score_quantile_ok_count": 3,
                "side_gap_quantile_ok_count": 3,
                "rank_quantile_ok_count": 3,
                "quantile_all_ok_count": 3,
                "quantile_hold_ok_count": 3,
                "threshold_after_quantile_hold_count": 0,
                "side_margin_after_quantile_hold_count": 3,
                "candidate_row_count": 0,
            }
        )

        stage = entry_ev_quantile_candidate_support_diagnostics.first_zero_stage(row)

        self.assertEqual(stage, "threshold_after_quantile_hold")


if __name__ == "__main__":
    unittest.main()
