from __future__ import annotations

import unittest

import pandas as pd

from scripts.experiments.entry_ev_horizon_overestimate_target_diagnostics import (
    add_target_columns,
    threshold_rule_summary,
)


def sample_examples() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "role": ["fresh", "fresh", "refit"],
            "family": ["f", "f", "r"],
            "month": ["2026-01", "2026-01", "2026-02"],
            "side": ["long", "long", "short"],
            "needed_side": ["long", "long", "short"],
            "row_scope": ["available_candidates"] * 3,
            "horizon_minutes": [720.0, 720.0, 60.0],
            "horizon_bucket": ["720m", "720m", "60m"],
            "combined_regime": ["range", "range", "trend"],
            "session_regime": ["asia", "asia", "ny"],
            "near_miss_bucket": ["one_failed", "one_failed", "strict"],
            "horizon_actual_pnl": [-3.0, 12.0, 2.0],
            "horizon_actual_delta_vs_60": [-6.0, 8.0, 0.0],
            "ranker_pred_pnl": [5.0, 3.0, 1.0],
            "ranker_pred_executable_prob": [0.7, 0.8, 0.6],
            "ranker_pred_tail_loss_prob": [0.2, 0.1, 0.05],
            "target_pnl_hurdle": [0.5, 0.5, 0.0],
            "extra_side_needed": [1.0, 1.0, 1.0],
            "target_horizon_tail_loss": [False, False, False],
            "residual_prior_count": [20.0, 20.0, 20.0],
            "residual_prior_months": [2.0, 2.0, 2.0],
            "residual_prior_bias": [4.0, 4.0, 0.0],
            "residual_prior_mae": [12.0, 12.0, 4.0],
            "residual_prior_rmse": [15.0, 15.0, 5.0],
            "residual_prior_overestimate_rate": [0.7, 0.7, 0.4],
            "residual_prior_tail_miss_rate": [0.2, 0.2, 0.0],
            "duration_prior_mean_pnl": [1.0, 1.0, 0.5],
            "duration_prior_delta_vs_60_mean": [0.0, 0.0, 0.0],
            "duration_prior_tail_loss_rate": [0.1, 0.1, 0.0],
            "repair_duration_risk_score": [1.0, 1.0, 0.0],
            "ranker_core_model_used": [True, True, True],
        }
    )


class EntryEvHorizonOverestimateTargetDiagnosticsTest(unittest.TestCase):
    def test_add_target_columns_separates_harmful_and_profitable_720(self) -> None:
        output = add_target_columns(
            sample_examples(),
            overestimate_threshold=2.0,
            underperform_60_threshold=2.0,
            min_executable_pnl=0.0,
            min_profitable_pnl=5.0,
            high_variance_mae_threshold=10.0,
            high_tail_miss_threshold=0.1,
        )

        harmful = output.iloc[0]
        profitable = output.iloc[1]
        support = output.iloc[2]
        self.assertTrue(bool(harmful["harmful_overestimate"]))
        self.assertTrue(bool(harmful["support_harmful_overestimate"]))
        self.assertTrue(bool(harmful["dangerous_high_variance_720"]))
        self.assertEqual(harmful["target_class"], "support_harmful_overestimate")
        self.assertFalse(bool(profitable["harmful_overestimate"]))
        self.assertTrue(bool(profitable["profitable_high_variance_720"]))
        self.assertEqual(profitable["target_class"], "profitable_high_variance_720")
        self.assertTrue(bool(support["support_success"]))

    def test_threshold_summary_tracks_winner_damage(self) -> None:
        output = add_target_columns(
            sample_examples(),
            overestimate_threshold=2.0,
            underperform_60_threshold=2.0,
            min_executable_pnl=0.0,
            min_profitable_pnl=5.0,
            high_variance_mae_threshold=10.0,
            high_tail_miss_threshold=0.1,
        )

        summary = threshold_rule_summary(
            output,
            mae_thresholds=[10.0],
            tail_miss_thresholds=[],
            bias_thresholds=[],
        )
        row = summary[
            summary["scope"].eq("all") & summary["rule"].eq("residual_mae_ge_10")
        ].iloc[0]
        self.assertEqual(int(row["flagged_harmful_count"]), 1)
        self.assertEqual(int(row["flagged_profitable_hv720_count"]), 1)
        self.assertAlmostEqual(float(row["flagged_profitable_hv720_pnl"]), 12.0)


if __name__ == "__main__":
    unittest.main()
