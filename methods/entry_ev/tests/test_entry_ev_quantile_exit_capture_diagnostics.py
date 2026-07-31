import importlib.util
import sys
import unittest
from pathlib import Path

import pandas as pd


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "experiments"
    / "entry_ev_quantile_exit_capture_diagnostics.py"
)
SPEC = importlib.util.spec_from_file_location(
    "entry_ev_quantile_exit_capture_diagnostics",
    SCRIPT_PATH,
)
entry_ev_quantile_exit_capture_diagnostics = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = entry_ev_quantile_exit_capture_diagnostics
SPEC.loader.exec_module(entry_ev_quantile_exit_capture_diagnostics)


class EntryEvQuantileExitCaptureDiagnosticsTests(unittest.TestCase):
    def test_add_exit_capture_columns_uses_side_specific_policy_hold(self):
        trades = pd.DataFrame(
            {
                "direction": ["long", "short"],
                "holding_minutes": [100.0, 300.0],
                "actual_taken_best_holding_minutes": [200.0, 120.0],
                "actual_taken_best_adjusted_pnl": [10.0, 8.0],
                "adjusted_pnl": [-2.0, 3.0],
                "exit_regret": [12.0, 5.0],
                "pred_mlp_long_exit_event_minutes": [500.0, 50.0],
                "pred_mlp_short_exit_event_minutes": [60.0, 20.0],
            }
        )

        output = entry_ev_quantile_exit_capture_diagnostics.add_exit_capture_columns(
            trades,
            long_policy_hold_column="pred_mlp_long_exit_event_minutes",
            short_policy_hold_column="pred_mlp_short_exit_event_minutes",
            min_policy_hold_minutes=30.0,
            max_policy_hold_minutes=260.0,
            tolerance_minutes=30.0,
        )

        self.assertEqual(output["policy_effective_hold_minutes"].tolist(), [260.0, 30.0])
        self.assertEqual(output["policy_hold_clipped_to_max"].tolist(), [True, False])
        self.assertEqual(output["policy_hold_clipped_to_min"].tolist(), [False, True])
        self.assertEqual(output["early_exit_vs_oracle"].tolist(), [True, False])
        self.assertEqual(output["late_exit_vs_oracle"].tolist(), [False, True])
        self.assertEqual(output["loss_with_oracle_edge"].tolist(), [True, False])

    def test_summarize_exit_capture_tracks_regret_and_hold_error(self):
        trades = pd.DataFrame(
            {
                "role": ["fresh", "fresh"],
                "candidate": ["q95", "q95"],
                "direction": ["long", "short"],
                "adjusted_pnl": [-2.0, 3.0],
                "holding_minutes": [100.0, 300.0],
                "actual_taken_best_holding_minutes": [200.0, 120.0],
                "actual_taken_best_adjusted_pnl": [10.0, 8.0],
                "exit_regret": [12.0, 5.0],
                "pred_mlp_long_exit_event_minutes": [500.0, 50.0],
                "pred_mlp_short_exit_event_minutes": [60.0, 20.0],
                "direction_error": [False, True],
                "no_edge_entry": [False, False],
            }
        )
        enriched = entry_ev_quantile_exit_capture_diagnostics.add_exit_capture_columns(
            trades,
            long_policy_hold_column="pred_mlp_long_exit_event_minutes",
            short_policy_hold_column="pred_mlp_short_exit_event_minutes",
            min_policy_hold_minutes=30.0,
            max_policy_hold_minutes=260.0,
            tolerance_minutes=30.0,
        )

        summary = entry_ev_quantile_exit_capture_diagnostics.summarize_exit_capture(
            enriched,
            ["role", "candidate"],
        )
        row = summary.iloc[0]

        self.assertEqual(row["trade_count"], 2)
        self.assertEqual(row["total_adjusted_pnl"], 1.0)
        self.assertEqual(row["exit_regret_sum"], 17.0)
        self.assertAlmostEqual(row["loss_with_oracle_edge_rate"], 0.5)
        self.assertAlmostEqual(row["early_exit_vs_oracle_rate"], 0.5)
        self.assertAlmostEqual(row["late_exit_vs_oracle_rate"], 0.5)
        self.assertAlmostEqual(row["policy_hold_minus_oracle_mean"], -15.0)
        self.assertAlmostEqual(row["direction_error_rate"], 0.5)


if __name__ == "__main__":
    unittest.main()
