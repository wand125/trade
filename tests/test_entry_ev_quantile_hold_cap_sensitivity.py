import importlib.util
import sys
import unittest
from pathlib import Path

import pandas as pd


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "experiments"
    / "entry_ev_quantile_hold_cap_sensitivity.py"
)
SPEC = importlib.util.spec_from_file_location(
    "entry_ev_quantile_hold_cap_sensitivity",
    SCRIPT_PATH,
)
entry_ev_quantile_hold_cap_sensitivity = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = entry_ev_quantile_hold_cap_sensitivity
SPEC.loader.exec_module(entry_ev_quantile_hold_cap_sensitivity)


class EntryEvQuantileHoldCapSensitivityTests(unittest.TestCase):
    def test_derive_context_side_block_rules_aggregates_direction_error(self):
        context_summary = pd.DataFrame(
            {
                "role": ["fresh", "fresh", "fresh"],
                "candidate": ["q95", "q99", "q95"],
                "direction": ["short", "short", "long"],
                "combined_regime": ["range_low_vol", "range_low_vol", "up_low_vol"],
                "session_regime": ["ny_overlap", "ny_overlap", "london"],
                "trade_count": [1, 3, 2],
                "total_adjusted_pnl": [-4.0, -6.0, 5.0],
                "direction_error_rate": [1.0, 2.0 / 3.0, 1.0],
                "exit_regret_sum": [10.0, 30.0, 8.0],
            }
        )

        rules, eligible = (
            entry_ev_quantile_hold_cap_sensitivity.derive_context_side_block_rules(
                context_summary,
                roles={"fresh"},
                candidates={"q95", "q99"},
                min_trade_count=4,
                min_direction_error_rate=0.75,
                max_total_pnl=0.0,
            )
        )

        self.assertEqual(
            rules,
            ["short:combined_regime=range_low_vol+session_regime=ny_overlap"],
        )
        self.assertEqual(len(eligible), 1)
        self.assertEqual(eligible.iloc[0]["trade_count"], 4)
        self.assertAlmostEqual(eligible.iloc[0]["direction_error_rate"], 0.75)

    def test_summarize_candidates_uses_notrade_first_blockers(self):
        monthly = pd.DataFrame(
            {
                "guard_mode": ["none", "none", "none", "none"],
                "max_predicted_hold_minutes": [260.0, 260.0, 480.0, 480.0],
                "role": ["a", "b", "a", "b"],
                "candidate": ["q95", "q95", "q95", "q95"],
                "month": ["2024-01", "2024-02", "2024-01", "2024-02"],
                "total_adjusted_pnl": [5.0, -1.0, 12.0, 3.0],
                "trade_count": [10, 10, 12, 11],
                "max_drawdown": [2.0, 3.0, 4.0, 5.0],
                "long_trade_count": [5, 5, 6, 5],
                "short_trade_count": [5, 5, 6, 6],
                "signal_long_count": [10, 10, 12, 11],
                "signal_short_count": [10, 10, 12, 11],
            }
        )

        summary = entry_ev_quantile_hold_cap_sensitivity.summarize_candidates(monthly)
        best = summary.iloc[0]
        worst = summary.iloc[1]

        self.assertTrue(best["selector_pass"])
        self.assertEqual(best["max_predicted_hold_minutes"], 480.0)
        self.assertFalse(worst["selector_pass"])
        self.assertIn("role_total_pnl_below_floor", worst["blockers"])


if __name__ == "__main__":
    unittest.main()
