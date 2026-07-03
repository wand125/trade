from __future__ import annotations

import unittest

import pandas as pd

from scripts.experiments.entry_ev_support_sufficient_loss_risk_prior_diagnostics import (
    add_observable_trade_features,
    build_prior_context_rows,
    build_rule_hits,
    rule_catalog,
    summarize_rule_hits,
)


class EntryEvSupportSufficientLossRiskPriorDiagnosticsTest(unittest.TestCase):
    def sample_trades(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "role": ["r", "r", "r"],
                "family": ["f", "f", "f"],
                "month": ["2026-01", "2026-01", "2026-01"],
                "direction": ["short", "short", "long"],
                "entry_decision_timestamp": [
                    "2026-01-01T00:00:00Z",
                    "2026-01-01T01:00:00Z",
                    "2026-01-01T02:00:00Z",
                ],
                "adjusted_pnl": [-2.0, 1.0, -0.5],
                "session_regime": ["ny", "ny", "ny"],
                "combined_regime": ["down", "down", "down"],
                "entry_hour": [0, 1, 2],
                "selected_loss_first_prob": [0.20, 0.20, 0.60],
                "pred_taken_ev": [6.0, 6.0, 1.0],
                "pred_opposite_ev": [0.0, 0.0, 0.0],
                "pred_side_confidence_gap": [0.20, 0.20, 0.10],
                "pred_taken_entry_local_rank": [0.55, 0.55, 0.55],
                "selected_fixed_60m_pred_pnl": [1.0, 1.0, 1.0],
                "selected_fixed_240m_pred_pnl": [7.0, 7.0, 1.0],
                "selected_fixed_720m_pred_pnl": [2.0, 2.0, 1.0],
                "selected_fixed_60m_actual_pnl": [0.0, 0.0, 0.0],
                "selected_fixed_240m_actual_pnl": [-3.0, 2.0, -1.0],
                "selected_fixed_720m_actual_pnl": [-1.0, 1.0, -1.0],
            }
        )

    def test_observable_features_keep_predicted_horizon_separate_from_outcome(self) -> None:
        rows = add_observable_trade_features(self.sample_trades(), large_loss_threshold=-1.0)
        first = rows.iloc[0]

        self.assertEqual(int(first["pred_fixed_best_horizon_minutes"]), 240)
        self.assertEqual(float(first["pred_fixed_best_pred_pnl"]), 7.0)
        self.assertEqual(float(first["actual_at_pred_fixed_best_horizon"]), -3.0)
        self.assertTrue(bool(first["is_large_loss_trade"]))

    def test_prior_context_rows_use_only_earlier_timestamps(self) -> None:
        rows = add_observable_trade_features(self.sample_trades(), large_loss_threshold=-1.0)
        prior = build_prior_context_rows(
            rows,
            rows,
            context_specs=[["direction", "session_regime"]],
            large_loss_threshold=-1.0,
        )

        first = prior[prior["trade_id"].eq(rows.iloc[0]["trade_id"])].iloc[0]
        second = prior[prior["trade_id"].eq(rows.iloc[1]["trade_id"])].iloc[0]
        third = prior[prior["trade_id"].eq(rows.iloc[2]["trade_id"])].iloc[0]

        self.assertEqual(int(first["prior_count"]), 0)
        self.assertEqual(int(second["prior_count"]), 1)
        self.assertEqual(int(second["prior_loss_count"]), 1)
        self.assertEqual(float(second["prior_pnl_sum"]), -2.0)
        self.assertEqual(int(third["prior_count"]), 0)

    def test_rule_summary_tracks_loss_capture_and_winner_damage(self) -> None:
        rows = add_observable_trade_features(self.sample_trades(), large_loss_threshold=-1.0)
        prior = build_prior_context_rows(
            rows,
            rows,
            context_specs=[["direction", "session_regime"]],
            large_loss_threshold=-1.0,
        )
        hits = build_rule_hits(rows, prior)
        summary = summarize_rule_hits(
            hits,
            rows,
            target_trade_ids=set(rows["trade_id"]),
            catalog=rule_catalog([["direction", "session_regime"]]),
        )

        rule = summary[summary["rule"].eq("ev_ge5_lossfirst_lt0p30")].iloc[0]
        self.assertEqual(int(rule["flagged_trade_count"]), 2)
        self.assertEqual(int(rule["flagged_loss_count"]), 1)
        self.assertEqual(float(rule["flagged_pnl"]), -1.0)
        self.assertEqual(float(rule["flagged_winner_pnl"]), 1.0)
        self.assertEqual(float(rule["block_delta_if_removed"]), 1.0)


if __name__ == "__main__":
    unittest.main()
