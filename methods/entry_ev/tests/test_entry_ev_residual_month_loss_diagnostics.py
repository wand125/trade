import importlib.util
import sys
import unittest
from pathlib import Path

import pandas as pd


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "experiments"
    / "entry_ev_residual_month_loss_diagnostics.py"
)
SPEC = importlib.util.spec_from_file_location(
    "entry_ev_residual_month_loss_diagnostics",
    SCRIPT_PATH,
)
entry_ev_residual_month_loss_diagnostics = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = entry_ev_residual_month_loss_diagnostics
SPEC.loader.exec_module(entry_ev_residual_month_loss_diagnostics)


class EntryEvResidualMonthLossDiagnosticsTests(unittest.TestCase):
    def test_build_residual_summary_tracks_exit_capture_loss(self):
        trades = pd.DataFrame(
            {
                "role": ["fresh", "fresh", "fresh"],
                "candidate": ["q95", "q95", "q95"],
                "month": ["2024-03", "2024-03", "2024-03"],
                "direction": ["long", "short", "short"],
                "adjusted_pnl": [-2.0, -5.0, 4.0],
                "actual_taken_best_adjusted_pnl": [12.0, 0.0, 8.0],
                "actual_best_adjusted_pnl": [12.0, 20.0, 8.0],
                "exit_regret": [14.0, 0.0, 2.0],
                "best_side_regret": [14.0, 25.0, 4.0],
                "ev_overestimate_vs_oracle": [1.0, 5.0, 0.0],
                "ev_overestimate_vs_realized": [11.0, 9.0, -1.0],
                "pred_taken_ev": [9.0, 8.0, 7.0],
                "direction_error": [False, True, False],
                "no_edge_entry": [False, True, False],
                "predicted_side_error": [False, True, False],
                "prior_has_context": [True, False, True],
                "prior_context_risk_score": [0.6, 0.0, 0.2],
            }
        )
        trades = entry_ev_residual_month_loss_diagnostics.normalize_trade_frame(trades)
        trades = entry_ev_residual_month_loss_diagnostics.add_failure_flags(
            trades,
            exit_regret_threshold=10.0,
            best_side_regret_threshold=10.0,
            prior_risk_threshold=0.5,
        )

        summary = entry_ev_residual_month_loss_diagnostics.build_residual_summary(trades)

        self.assertEqual(summary["trade_count"], 3)
        self.assertEqual(summary["total_adjusted_pnl"], -3.0)
        self.assertEqual(summary["loss_trade_count"], 2)
        self.assertEqual(summary["loss_adjusted_pnl"], -7.0)
        self.assertEqual(summary["loss_with_same_side_oracle_edge_count"], 1)
        self.assertEqual(summary["direction_error_count"], 1)
        self.assertEqual(summary["large_exit_regret_count"], 1)
        self.assertEqual(summary["large_best_side_regret_count"], 2)
        self.assertEqual(summary["prior_context_risk_high_count"], 1)
        self.assertEqual(summary["exit_regret_sum"], 16.0)
        self.assertEqual(summary["same_side_oracle_total"], 20.0)

    def test_summarize_flags_reports_removal_delta_and_regret(self):
        trades = pd.DataFrame(
            {
                "role": ["fresh", "fresh", "fresh"],
                "candidate": ["q95", "q95", "q95"],
                "month": ["2024-03", "2024-03", "2024-03"],
                "direction": ["long", "short", "long"],
                "adjusted_pnl": [-6.0, -3.0, 5.0],
                "actual_taken_best_adjusted_pnl": [10.0, 2.0, 6.0],
                "actual_best_adjusted_pnl": [10.0, 12.0, 6.0],
                "exit_regret": [16.0, 1.0, 1.0],
                "best_side_regret": [16.0, 15.0, 1.0],
                "ev_overestimate_vs_oracle": [2.0, 3.0, 0.0],
                "ev_overestimate_vs_realized": [12.0, 8.0, -2.0],
                "pred_taken_ev": [8.0, 7.0, 6.0],
                "direction_error": [False, True, False],
                "no_edge_entry": [False, False, False],
                "predicted_side_error": [False, True, False],
                "prior_has_context": [False, False, False],
                "prior_context_risk_score": [0.0, 0.0, 0.0],
            }
        )
        trades = entry_ev_residual_month_loss_diagnostics.normalize_trade_frame(trades)
        trades = entry_ev_residual_month_loss_diagnostics.add_failure_flags(
            trades,
            exit_regret_threshold=10.0,
            best_side_regret_threshold=10.0,
            prior_risk_threshold=0.5,
        )

        summary = entry_ev_residual_month_loss_diagnostics.summarize_flags(trades)
        direction = summary[summary["flag"].eq("direction_error")].iloc[0]
        exit_regret = summary[summary["flag"].eq("large_exit_regret")].iloc[0]

        self.assertEqual(direction["flagged_trade_count"], 1)
        self.assertEqual(direction["flagged_adjusted_pnl"], -3.0)
        self.assertEqual(direction["block_delta_if_removed"], 3.0)
        self.assertEqual(exit_regret["flagged_trade_count"], 1)
        self.assertEqual(exit_regret["flagged_adjusted_pnl"], -6.0)
        self.assertEqual(exit_regret["exit_regret_sum"], 16.0)


if __name__ == "__main__":
    unittest.main()
