from __future__ import annotations

import unittest

import pandas as pd

from scripts.experiments.entry_ev_support_repair_thin_month_candidate_diagnostics import (
    add_candidate_diagnostic_columns,
    normalize_external_horizon_candidates,
    select_target_months,
    summarize_target_candidates,
)


class EntryEvSupportRepairThinMonthCandidateDiagnosticsTest(unittest.TestCase):
    def test_select_target_months_marks_negative_and_thin_months(self) -> None:
        monthly = pd.DataFrame(
            {
                "scenario_label": ["s1", "s1", "s1"],
                "role": ["r1", "r2", "r3"],
                "family": ["f1", "f2", "f3"],
                "month": ["2026-01", "2026-02", "2026-03"],
                "total_adjusted_pnl": [-1.0, 2.0, 3.0],
                "trade_count": [3.0, 1.0, 3.0],
                "long_trade_count": [2.0, 0.0, 2.0],
                "short_trade_count": [1.0, 1.0, 1.0],
                "max_side_trade_share": [2.0 / 3.0, 1.0, 2.0 / 3.0],
            }
        )

        targets = select_target_months(
            monthly,
            scenario_label="s1",
            month_pnl_floor=0.0,
            min_month_trades=2.0,
            max_side_share=0.95,
        )

        self.assertEqual(targets["target_key"].tolist(), ["r1|2026-01", "r2|2026-02"])
        self.assertEqual(targets["target_needed_side"].tolist(), ["short", "long"])
        self.assertEqual(targets.iloc[0]["target_reason"], "month_pnl_below_floor")
        self.assertEqual(
            targets.iloc[1]["target_reason"],
            "month_trades_low,side_share_high",
        )

    def test_summary_ranks_by_observable_prediction_not_actual(self) -> None:
        monthly = pd.DataFrame(
            {
                "scenario_label": ["s1", "s1"],
                "role": ["r1", "r2"],
                "family": ["f1", "f2"],
                "month": ["2026-01", "2026-02"],
                "total_adjusted_pnl": [-1.0, 1.0],
                "trade_count": [1.0, 1.0],
                "long_trade_count": [1.0, 0.0],
                "short_trade_count": [0.0, 1.0],
                "max_side_trade_share": [1.0, 1.0],
            }
        )
        targets = select_target_months(
            monthly,
            scenario_label="s1",
            month_pnl_floor=0.0,
            min_month_trades=2.0,
            max_side_share=0.95,
        )
        candidates = add_candidate_diagnostic_columns(
            pd.DataFrame(
                {
                    "scenario_label": ["s1", "s1", "s1"],
                    "role": ["r1", "r1", "r2"],
                    "family": ["f1", "f1", "f2"],
                    "month": ["2026-01", "2026-01", "2026-02"],
                    "side": ["short", "short", "long"],
                    "decision_timestamp": [
                        "2026-01-01T00:00:00Z",
                        "2026-01-01T00:05:00Z",
                        "2026-02-01T00:00:00Z",
                    ],
                    "hv_chosen_horizon_minutes": [60.0, 60.0, 720.0],
                    "hv_chosen_pred_pnl": [3.0, 1.0, 1.0],
                    "hv_chosen_pred_executable_prob": [0.6, 0.7, 0.7],
                    "hv_chosen_pred_tail_loss_prob": [0.1, 0.1, 0.1],
                    "hv_chosen_pred_harmful_overestimate_prob": [0.2, 0.1, 0.1],
                    "hv_chosen_pred_model_used": [True, True, True],
                    "pred_fixed_best_horizon_minutes": [60.0, 60.0, 60.0],
                    "actual_pnl_at_hv_chosen_horizon": [-10.0, 20.0, 5.0],
                    "repair_score": [1.0, 10.0, 2.0],
                    "current_selected": [False, False, True],
                    "selection_status": ["quota_full", "quota_full", "selected"],
                    "reject_reason": ["quota_full", "quota_full", "selected"],
                }
            ),
            strict_min_prob=0.45,
            strict_min_pred_pnl=0.0,
            strict_max_tail_prob=0.3,
            relaxed_min_pred_pnl=-2.0,
        )

        summary = summarize_target_candidates(targets, candidates)
        r1 = summary[summary["target_key"].eq("r1|2026-01")].iloc[0]
        r2 = summary[summary["target_key"].eq("r2|2026-02")].iloc[0]

        self.assertAlmostEqual(float(r1["needed_top_pred_pnl_pred_pnl"]), 3.0)
        self.assertAlmostEqual(float(r1["needed_top_pred_pnl_actual_pnl"]), -10.0)
        self.assertAlmostEqual(float(r1["needed_side_oracle_best_actual"]), 20.0)
        self.assertAlmostEqual(float(r1["needed_top_oracle_actual_actual_pnl"]), 20.0)
        self.assertAlmostEqual(float(r1["needed_top_oracle_actual_pred_pnl"]), 1.0)
        self.assertEqual(int(r1["needed_side_strict_guarded_pass_unique_count"]), 2)
        self.assertTrue(bool(r1["needed_top_pred_pnl_model_used"]))
        self.assertTrue(bool(candidates.iloc[2]["singleton_720_pred_pnl_lt2"]))
        self.assertEqual(int(r2["needed_side_strict_pass_unique_count"]), 1)
        self.assertEqual(int(r2["needed_side_strict_guarded_pass_unique_count"]), 0)
        self.assertTrue(bool(r2["needed_top_pred_pnl_singleton_720_pred_pnl_lt2"]))

    def test_external_horizon_candidates_map_to_common_schema(self) -> None:
        external = normalize_external_horizon_candidates(
            pd.DataFrame(
                {
                    "role": ["r1", "r1"],
                    "family": ["f1", "f1"],
                    "month": ["2026-01", "2026-01"],
                    "decision_timestamp": [
                        "2026-01-01T00:00:00Z",
                        "2026-01-01T00:05:00Z",
                    ],
                    "side": ["long", "long"],
                    "needed_side": ["long", "long"],
                    "extra_side_needed": [1.0, 1.0],
                    "row_scope": ["available_candidates", "greedy_selected"],
                    "horizon_minutes": [240.0, 240.0],
                    "actual_pnl": [5.0, -2.0],
                    "pred_executable_prob": [0.5, 0.6],
                    "pred_pnl": [1.2, 2.0],
                    "pred_tail_loss_prob": [0.2, 0.2],
                    "pred_model_used": [False, True],
                    "target_fixed_best_horizon_minutes": [240.0, 240.0],
                }
            ),
            scenario_label="s1",
            row_scopes=["available_candidates"],
        )

        self.assertEqual(len(external), 1)
        self.assertEqual(external.iloc[0]["scenario_label"], "s1")
        self.assertEqual(external.iloc[0]["selection_status"], "external_horizon")
        self.assertAlmostEqual(
            float(external.iloc[0]["actual_pnl_at_hv_chosen_horizon"]),
            5.0,
        )
        self.assertFalse(bool(external.iloc[0]["hv_chosen_pred_model_used"]))


if __name__ == "__main__":
    unittest.main()
