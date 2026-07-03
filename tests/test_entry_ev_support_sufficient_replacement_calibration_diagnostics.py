from __future__ import annotations

import unittest

import pandas as pd

from scripts.experiments.entry_ev_support_sufficient_replacement_calibration_diagnostics import (
    add_candidate_horizon_columns_fast,
    add_prior_calibration,
    choose_top_candidate,
    choice_row,
    parse_context_specs,
    prior_metric_row,
)


class EntryEvSupportSufficientReplacementCalibrationDiagnosticsTest(unittest.TestCase):
    def test_fast_candidate_horizon_columns_match_expected_argmax(self) -> None:
        rows = pd.DataFrame(
            {
                "side_pred_fixed_60m_adjusted_pnl": [1.0, -1.0],
                "side_pred_fixed_240m_adjusted_pnl": [3.0, -2.0],
                "side_pred_fixed_720m_adjusted_pnl": [2.0, -0.5],
                "side_fixed_60m_adjusted_pnl": [5.0, -5.0],
                "side_fixed_240m_adjusted_pnl": [4.0, -4.0],
                "side_fixed_720m_adjusted_pnl": [6.0, -6.0],
            }
        )

        output = add_candidate_horizon_columns_fast(rows)

        self.assertEqual(output["candidate_pred_fixed_best_horizon_minutes"].tolist(), [240, 720])
        self.assertEqual(output["candidate_fixed_best_horizon_minutes_oracle"].tolist(), [720, 240])
        self.assertAlmostEqual(output["candidate_actual_at_pred_fixed_best_horizon"].iloc[0], 4.0)
        self.assertAlmostEqual(output["candidate_actual_at_pred_fixed_best_horizon"].iloc[1], -6.0)

    def test_prior_metric_row_computes_bias_against_prediction(self) -> None:
        frame = pd.DataFrame(
            {
                "month": ["2025-01", "2025-02"],
                "candidate_pred_fixed_best_pred_pnl": [2.0, 4.0],
                "candidate_actual_at_pred_fixed_best_horizon": [1.0, -2.0],
            }
        )

        metrics = prior_metric_row(frame)

        self.assertEqual(metrics["prior_count"], 2)
        self.assertEqual(metrics["prior_month_count"], 2)
        self.assertAlmostEqual(metrics["prior_pred_mean"], 3.0)
        self.assertAlmostEqual(metrics["prior_actual_mean"], -0.5)
        self.assertAlmostEqual(metrics["prior_bias_mean"], -3.5)
        self.assertAlmostEqual(metrics["prior_mae"], 3.5)

    def test_add_prior_calibration_uses_first_supported_context(self) -> None:
        prior = pd.DataFrame(
            {
                "month": ["2025-01", "2025-02", "2025-02"],
                "side": ["long", "long", "short"],
                "candidate_pred_fixed_best_horizon_minutes": [240, 240, 240],
                "combined_regime": ["range", "range", "range"],
                "session_regime": ["ny", "ny", "ny"],
                "candidate_pred_fixed_best_pred_pnl": [3.0, 5.0, 10.0],
                "candidate_actual_at_pred_fixed_best_horizon": [1.0, 2.0, -10.0],
            }
        )
        candidates = pd.DataFrame(
            {
                "side": ["long"],
                "candidate_pred_fixed_best_horizon_minutes": [240],
                "combined_regime": ["range"],
                "session_regime": ["ny"],
                "candidate_pred_fixed_best_pred_pnl": [4.0],
            }
        )

        output = add_prior_calibration(
            candidates,
            prior_rows=prior,
            context_specs=parse_context_specs(
                "side,candidate_pred_fixed_best_horizon_minutes,combined_regime,session_regime;side"
            ),
            min_prior_count=2,
        ).iloc[0]

        self.assertEqual(
            output["calibration_context_spec"],
            "side,candidate_pred_fixed_best_horizon_minutes,combined_regime,session_regime",
        )
        self.assertEqual(int(output["prior_count"]), 2)
        self.assertAlmostEqual(float(output["prior_bias_mean"]), -2.5)
        self.assertAlmostEqual(float(output["calibrated_bias_corrected_pred_pnl"]), 1.5)
        self.assertAlmostEqual(
            float(output["calibrated_downside_bias_corrected_pred_pnl"]),
            1.5,
        )
        self.assertAlmostEqual(float(output["calibrated_conservative_pred_pnl"]), -1.0)

    def test_choose_top_candidate_can_use_calibrated_score(self) -> None:
        pool = pd.DataFrame(
            {
                "side": ["long", "long"],
                "decision_timestamp": [
                    "2025-03-01T00:00:00Z",
                    "2025-03-01T01:00:00Z",
                ],
                "candidate_stage": ["one_failed_strict_stage", "one_failed_strict_stage"],
                "side_score": [10.0, 8.0],
                "score_pct": [0.9, 0.8],
                "side_margin_pct": [0.9, 0.8],
                "entry_rank_pct": [0.9, 0.8],
                "candidate_pred_fixed_best_horizon_minutes": [240, 240],
                "candidate_pred_fixed_best_pred_pnl": [5.0, 1.0],
                "candidate_actual_at_pred_fixed_best_horizon": [-3.0, 2.0],
                "candidate_fixed_best_actual_pnl_oracle": [-1.0, 4.0],
                "calibrated_conservative_pred_pnl": [-10.0, -1.0],
            }
        )

        raw_choice = choose_top_candidate(pool, score_mode="side_score")
        calibrated_choice = choose_top_candidate(pool, score_mode="conservative")

        self.assertEqual(str(raw_choice["decision_timestamp"]), "2025-03-01T00:00:00Z")
        self.assertEqual(
            str(calibrated_choice["decision_timestamp"]),
            "2025-03-01T01:00:00Z",
        )

        loss_trade = pd.Series(
            {
                "trade_id": "loss",
                "direction": "short",
                "entry_decision_timestamp": "2025-03-01T00:30:00Z",
                "adjusted_pnl": -2.0,
            }
        )
        row = choice_row(
            month_pnl=-1.0,
            loss_trade=loss_trade,
            score_mode="conservative",
            candidate=calibrated_choice,
        )

        self.assertAlmostEqual(row["month_pnl_at_pred_horizon"], 3.0)
        self.assertAlmostEqual(row["month_pnl_at_oracle_horizon"], 5.0)


if __name__ == "__main__":
    unittest.main()
