import importlib.util
import sys
import unittest
from pathlib import Path

import pandas as pd


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "experiments"
    / "entry_ev_quantile_trade_diagnostics.py"
)
SPEC = importlib.util.spec_from_file_location(
    "entry_ev_quantile_trade_diagnostics",
    SCRIPT_PATH,
)
entry_ev_quantile_trade_diagnostics = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = entry_ev_quantile_trade_diagnostics
SPEC.loader.exec_module(entry_ev_quantile_trade_diagnostics)


class EntryEvQuantileTradeDiagnosticsTests(unittest.TestCase):
    def test_summarize_trade_groups_tracks_role_failure_rates(self):
        trades = pd.DataFrame(
            {
                "role": ["fresh", "fresh", "fresh"],
                "candidate": ["q95", "q95", "q95"],
                "direction": ["long", "short", "short"],
                "adjusted_pnl": [5.0, -3.0, -2.0],
                "holding_minutes": [30.0, 40.0, 50.0],
                "no_edge_entry": [False, True, True],
                "direction_error": [False, True, False],
                "predicted_side_error": [False, True, True],
                "matched_prediction": [True, True, True],
                "actual_taken_profit_barrier_hit": [1.0, 0.0, 0.0],
                "pred_taken_profit_barrier_hit": [0.8, 0.9, 0.7],
                "pred_taken_ev": [10.0, 8.0, 6.0],
                "actual_taken_best_adjusted_pnl": [7.0, -1.0, 0.0],
                "ev_overestimate_vs_oracle": [3.0, 9.0, 6.0],
                "ev_overestimate_vs_realized": [5.0, 11.0, 8.0],
                "exit_regret": [2.0, 0.0, 0.0],
                "best_side_regret": [2.0, 4.0, 3.0],
            }
        )

        summary = entry_ev_quantile_trade_diagnostics.summarize_trade_groups(
            trades,
            ["role", "candidate"],
        )
        row = summary.iloc[0]

        self.assertEqual(row["trade_count"], 3)
        self.assertEqual(row["total_adjusted_pnl"], 0.0)
        self.assertEqual(row["loss_adjusted_pnl"], -5.0)
        self.assertAlmostEqual(row["short_trade_share"], 2 / 3)
        self.assertAlmostEqual(row["no_edge_rate"], 2 / 3)
        self.assertAlmostEqual(row["direction_error_rate"], 1 / 3)
        self.assertAlmostEqual(row["actual_profit_barrier_hit_rate"], 1 / 3)
        self.assertAlmostEqual(row["ev_overestimate_vs_oracle_mean"], 6.0)

    def test_summarize_candidate_role_spread_finds_worst_role(self):
        role_summary = pd.DataFrame(
            {
                "role": ["cal", "fresh", "refit"],
                "candidate": ["q95", "q95", "q95"],
                "trade_count": [5, 6, 7],
                "total_adjusted_pnl": [10.0, 2.0, -8.0],
                "no_edge_rate": [0.1, 0.2, 0.7],
                "ev_overestimate_vs_oracle_mean": [1.0, 2.0, 9.0],
            }
        )

        spread = entry_ev_quantile_trade_diagnostics.summarize_candidate_role_spread(
            role_summary
        )
        row = spread.iloc[0]

        self.assertEqual(row["candidate"], "q95")
        self.assertEqual(row["positive_role_count"], 2)
        self.assertEqual(row["negative_role_count"], 1)
        self.assertEqual(row["role_total_pnl_min"], -8.0)
        self.assertEqual(row["role_total_pnl_spread"], 18.0)
        self.assertEqual(row["worst_role"], "refit")
        self.assertEqual(row["worst_role_trade_count"], 7)


if __name__ == "__main__":
    unittest.main()
