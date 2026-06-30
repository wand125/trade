import importlib.util
import unittest
from pathlib import Path

import pandas as pd


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "experiments"
    / "entry_ev_admission_gate_sensitivity.py"
)
SPEC = importlib.util.spec_from_file_location(
    "entry_ev_admission_gate_sensitivity",
    SCRIPT_PATH,
)
entry_ev_admission_gate_sensitivity = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(entry_ev_admission_gate_sensitivity)


class EntryEvAdmissionGateSensitivityTests(unittest.TestCase):
    def validation_summary(self):
        return pd.DataFrame(
            {
                "policy": ["timed_ev", "timed_ev"],
                "entry_threshold": [10.0, 12.0],
                "short_entry_threshold_offset": [9.0, 6.0],
                "side_margin": [5.0, 5.0],
                "risk_penalty": [0.0, 0.0],
                "min_entry_rank": [0.0, 0.5],
                "validation_total": [12.0, 8.0],
                "validation_worst": [1.0, 2.0],
                "validation_trades": [30, 20],
                "validation_active_months": [4, 4],
                "validation_max_dd": [5.0, 4.0],
                "validation_windows": [2, 2],
                "validation_positive_windows": [2, 2],
                "validation_active_windows": [2, 2],
                "validation_worst_window": [1.0, 2.0],
                "validation_min_window_trades": [10, 6],
                "validation_max_side_trade_share": [0.96, 0.90],
                "validation_direction_session_pnl_min": [-20.0, -5.0],
                "validation_combined_regime_pnl_min": [-40.0, -10.0],
                "validation_direction_combined_regime_pnl_min": [-50.0, -12.0],
            }
        )

    def fixed_summary(self):
        return pd.DataFrame(
            {
                "policy": ["timed_ev"],
                "entry_threshold": [12.0],
                "short_entry_threshold_offset": [6.0],
                "side_margin": [5.0],
                "risk_penalty": [0.0],
                "min_entry_rank": [0.5],
                "total_pnl": [42.0],
                "worst_pnl": [-3.0],
                "trades": [11],
                "max_dd": [7.0],
            }
        )

    def test_parse_float_list_supports_infinities(self):
        values = entry_ev_admission_gate_sensitivity.parse_float_list(
            "-inf,-1.5,0,inf"
        )

        self.assertEqual(values[0], -float("inf"))
        self.assertEqual(values[-1], float("inf"))
        self.assertAlmostEqual(values[1], -1.5)

    def test_gate_grid_selects_lower_validation_policy_when_side_gate_rejects_top(self):
        base_gates = {
            "min_positive_pnl": 0.0,
            "min_trades": 1,
            "min_active_months": 0,
            "min_worst_pnl": 0.0,
            "max_drawdown": float("inf"),
            "min_windows": 2,
            "min_positive_windows": 2,
            "min_active_windows": 2,
            "min_window_total": 0.0,
            "min_monthly_trades": 0,
            "max_monthly_trades": float("inf"),
        }
        gates = [
            {
                "min_window_trades": 1,
                "max_side_trade_share": 0.95,
                "min_direction_session_pnl": -float("inf"),
                "min_combined_regime_pnl": -float("inf"),
                "min_direction_combined_regime_pnl": -float("inf"),
            }
        ]

        sensitivity, details = entry_ev_admission_gate_sensitivity.evaluate_gate_grid(
            self.validation_summary(),
            self.fixed_summary(),
            base_gates,
            gates,
        )

        self.assertEqual(len(sensitivity), 1)
        self.assertEqual(sensitivity.loc[0, "selected"], "policy")
        self.assertEqual(float(sensitivity.loc[0, "selected_entry_threshold"]), 12.0)
        self.assertAlmostEqual(float(sensitivity.loc[0, "fixed_total_pnl"]), 42.0)
        self.assertEqual(len(details), 1)

    def test_gate_grid_returns_no_trade_when_regime_floor_rejects_all(self):
        base_gates = {
            "min_positive_pnl": 0.0,
            "min_trades": 1,
            "min_active_months": 0,
            "min_worst_pnl": 0.0,
            "max_drawdown": float("inf"),
            "min_windows": 2,
            "min_positive_windows": 2,
            "min_active_windows": 2,
            "min_window_total": 0.0,
            "min_monthly_trades": 0,
            "max_monthly_trades": float("inf"),
        }
        gates = [
            {
                "min_window_trades": 1,
                "max_side_trade_share": float("inf"),
                "min_direction_session_pnl": 0.0,
                "min_combined_regime_pnl": 0.0,
                "min_direction_combined_regime_pnl": 0.0,
            }
        ]

        sensitivity, details = entry_ev_admission_gate_sensitivity.evaluate_gate_grid(
            self.validation_summary(),
            self.fixed_summary(),
            base_gates,
            gates,
        )

        self.assertEqual(sensitivity.loc[0, "selected"], "no_trade")
        self.assertEqual(int(sensitivity.loc[0, "eligible_count"]), 0)
        self.assertEqual(len(details), 0)


if __name__ == "__main__":
    unittest.main()
