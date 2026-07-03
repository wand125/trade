from __future__ import annotations

import unittest

import pandas as pd

from scripts.experiments.entry_ev_support_sufficient_horizon_abstention_diagnostics import (
    abstention_rule_catalog,
    add_horizon_outcome_columns,
    build_abstention_rule_hits,
    build_horizon_prior_context_rows,
    summarize_abstention_rule_hits,
)
from scripts.experiments.entry_ev_support_sufficient_loss_risk_prior_diagnostics import (
    add_observable_trade_features,
)


class EntryEvSupportSufficientHorizonAbstentionDiagnosticsTest(unittest.TestCase):
    def sample_trades(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "role": ["r", "r", "r"],
                "family": ["f", "f", "f"],
                "month": ["2026-01", "2026-01", "2026-01"],
                "direction": ["long", "long", "short"],
                "entry_decision_timestamp": [
                    "2026-01-01T00:00:00Z",
                    "2026-01-01T01:00:00Z",
                    "2026-01-01T02:00:00Z",
                ],
                "adjusted_pnl": [1.0, 2.0, -1.0],
                "session_regime": ["ny", "ny", "ny"],
                "combined_regime": ["range", "range", "down"],
                "entry_hour": [0, 1, 2],
                "selected_loss_first_prob": [0.50, 0.10, 0.20],
                "pred_taken_ev": [6.0, 6.0, 6.0],
                "pred_opposite_ev": [0.0, 0.0, 0.0],
                "pred_side_confidence_gap": [0.10, 0.10, 0.20],
                "pred_taken_entry_local_rank": [0.60, 0.60, 0.60],
                "selected_fixed_60m_pred_pnl": [1.0, 1.0, 1.0],
                "selected_fixed_240m_pred_pnl": [1.0, 8.0, 8.0],
                "selected_fixed_720m_pred_pnl": [9.0, 2.0, 2.0],
                "selected_fixed_60m_actual_pnl": [1.0, 2.0, -1.0],
                "selected_fixed_240m_actual_pnl": [1.0, 5.0, -5.0],
                "selected_fixed_720m_actual_pnl": [-4.0, 2.0, -1.0],
            }
        )

    def scored(self) -> pd.DataFrame:
        rows = add_observable_trade_features(self.sample_trades(), large_loss_threshold=-1.0)
        return add_horizon_outcome_columns(rows, min_delta=0.0)

    def test_horizon_outcome_columns_compare_predicted_horizon_to_current_exit(self) -> None:
        rows = self.scored()
        first = rows.iloc[0]
        second = rows.iloc[1]

        self.assertEqual(int(first["pred_fixed_best_horizon_minutes"]), 720)
        self.assertEqual(float(first["pred_extension_delta"]), -5.0)
        self.assertTrue(bool(first["pred_extension_harm"]))
        self.assertEqual(int(second["pred_fixed_best_horizon_minutes"]), 240)
        self.assertEqual(float(second["pred_extension_delta"]), 3.0)
        self.assertTrue(bool(second["pred_extension_help"]))

    def test_horizon_prior_context_uses_only_earlier_timestamps(self) -> None:
        rows = self.scored()
        prior = build_horizon_prior_context_rows(
            rows,
            rows,
            context_specs=[["direction", "session_regime"]],
            min_delta=0.0,
        )

        first = prior[prior["trade_id"].eq(rows.iloc[0]["trade_id"])].iloc[0]
        second = prior[prior["trade_id"].eq(rows.iloc[1]["trade_id"])].iloc[0]
        third = prior[prior["trade_id"].eq(rows.iloc[2]["trade_id"])].iloc[0]

        self.assertEqual(int(first["prior_count"]), 0)
        self.assertEqual(int(second["prior_count"]), 1)
        self.assertEqual(int(second["prior_extension_harm_count"]), 1)
        self.assertEqual(float(second["prior_extension_delta_sum"]), -5.0)
        self.assertEqual(int(third["prior_count"]), 0)

    def test_abstention_summary_reports_delta_vs_following_predicted_horizon(self) -> None:
        rows = self.scored()
        prior = build_horizon_prior_context_rows(
            rows,
            rows,
            context_specs=[["direction", "session_regime"]],
            min_delta=0.0,
        )
        hits = build_abstention_rule_hits(rows, prior)
        summary = summarize_abstention_rule_hits(
            hits,
            rows,
            target_trade_ids=set(rows["trade_id"]),
            catalog=abstention_rule_catalog([["direction", "session_regime"]]),
        )

        rule = summary[summary["rule"].eq("loss_first_ge0p40")].iloc[0]
        self.assertEqual(int(rule["flagged_trade_count"]), 1)
        self.assertEqual(int(rule["flagged_harm_count"]), 1)
        self.assertEqual(float(rule["flagged_extension_delta_sum"]), -5.0)
        self.assertEqual(float(rule["abstain_delta_vs_follow_if_flagged"]), 5.0)
        self.assertEqual(float(rule["extension_delta_after_abstention"]), -1.0)


if __name__ == "__main__":
    unittest.main()
