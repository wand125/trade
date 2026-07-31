from __future__ import annotations

import unittest

import pandas as pd

from scripts.experiments.entry_ev_support_sufficient_negative_month_repair_diagnostics import (
    add_candidate_horizon_columns,
    add_current_trade_repair_columns,
    build_month_summary,
)


class EntryEvSupportSufficientNegativeMonthRepairDiagnosticsTest(unittest.TestCase):
    def test_current_trade_keeps_oracle_and_predicted_horizon_separate(self) -> None:
        trades = pd.DataFrame(
            {
                "role": ["r"],
                "family": ["f"],
                "month": ["2026-01"],
                "direction": ["long"],
                "entry_decision_timestamp": ["2026-01-02T00:00:00Z"],
                "exit_decision_timestamp": ["2026-01-02T00:01:00Z"],
                "adjusted_pnl": [-1.0],
                "selected_fixed_60m_pred_pnl": [0.1],
                "selected_fixed_240m_pred_pnl": [0.2],
                "selected_fixed_720m_pred_pnl": [2.0],
                "selected_fixed_60m_actual_pnl": [3.0],
                "selected_fixed_240m_actual_pnl": [1.0],
                "selected_fixed_720m_actual_pnl": [-5.0],
            }
        )

        out = add_current_trade_repair_columns(trades).iloc[0]

        self.assertEqual(int(out["fixed_best_horizon_minutes_oracle"]), 60)
        self.assertEqual(float(out["fixed_best_actual_pnl_oracle"]), 3.0)
        self.assertEqual(int(out["pred_fixed_best_horizon_minutes"]), 720)
        self.assertEqual(float(out["actual_at_pred_fixed_best_horizon"]), -5.0)
        self.assertEqual(out["diagnostic_repair_class"], "loss_exit_horizon_oracle_improves")

    def test_candidate_horizon_columns_use_candidate_side_values(self) -> None:
        rows = pd.DataFrame(
            {
                "side_pred_fixed_60m_adjusted_pnl": [0.0],
                "side_pred_fixed_240m_adjusted_pnl": [4.0],
                "side_pred_fixed_720m_adjusted_pnl": [1.0],
                "side_fixed_60m_adjusted_pnl": [5.0],
                "side_fixed_240m_adjusted_pnl": [-2.0],
                "side_fixed_720m_adjusted_pnl": [1.5],
            }
        )

        out = add_candidate_horizon_columns(rows).iloc[0]

        self.assertEqual(int(out["candidate_pred_fixed_best_horizon_minutes"]), 240)
        self.assertEqual(float(out["candidate_actual_at_pred_fixed_best_horizon"]), -2.0)
        self.assertEqual(int(out["candidate_fixed_best_horizon_minutes_oracle"]), 60)
        self.assertEqual(float(out["candidate_fixed_best_actual_pnl_oracle"]), 5.0)

    def test_month_summary_identifies_support_sufficient_negative_month(self) -> None:
        trade_diag = add_current_trade_repair_columns(
            pd.DataFrame(
                {
                    "role": ["r", "r"],
                    "family": ["f", "f"],
                    "month": ["2026-01", "2026-01"],
                    "direction": ["long", "short"],
                    "entry_decision_timestamp": [
                        "2026-01-02T00:00:00Z",
                        "2026-01-03T00:00:00Z",
                    ],
                    "exit_decision_timestamp": [
                        "2026-01-02T00:01:00Z",
                        "2026-01-03T00:01:00Z",
                    ],
                    "adjusted_pnl": [-2.0, 1.0],
                    "selected_fixed_60m_pred_pnl": [0.0, 0.0],
                    "selected_fixed_240m_pred_pnl": [0.0, 0.0],
                    "selected_fixed_720m_pred_pnl": [0.0, 0.0],
                    "selected_fixed_60m_actual_pnl": [-3.0, 1.0],
                    "selected_fixed_240m_actual_pnl": [-4.0, 1.0],
                    "selected_fixed_720m_actual_pnl": [-5.0, 1.0],
                }
            )
        )
        repair_row = pd.Series({"extra_long_needed": 0, "extra_short_needed": 0})

        summary = build_month_summary(
            role="r",
            family="f",
            month="2026-01",
            repair_row=repair_row,
            trade_diag=trade_diag,
            replacement_summary=pd.DataFrame(),
        )

        self.assertTrue(summary["support_sufficient_negative_month"])
        self.assertEqual(float(summary["month_pnl"]), -1.0)
        self.assertEqual(float(summary["skip_all_loss_trades_month_pnl_oracle"]), 1.0)


if __name__ == "__main__":
    unittest.main()
