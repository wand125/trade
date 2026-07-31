import importlib.util
import unittest
from pathlib import Path

import pandas as pd


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "experiments"
    / "entry_ev_admission_selection.py"
)
SPEC = importlib.util.spec_from_file_location("entry_ev_admission_selection", SCRIPT_PATH)
entry_ev_admission_selection = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(entry_ev_admission_selection)


class EntryEvAdmissionSelectionTests(unittest.TestCase):
    def summary_frame(self):
        return pd.DataFrame(
            {
                "family": ["calibrated", "calibrated", "raw"],
                "entry_threshold": [12.0, 10.0, 12.0],
                "short_entry_threshold_offset": [6.0, 6.0, 3.0],
                "validation_total": [-1.0, -20.0, -40.0],
                "validation_worst": [-1.0, -15.0, -30.0],
                "validation_trades": [7, 20, 60],
                "validation_active_months": [2, 2, 2],
                "validation_max_dd": [5.0, 15.0, 30.0],
            }
        )

    def test_standard_selector_returns_no_trade_when_no_positive_edge(self):
        selected = entry_ev_admission_selection.select_standard_policy(
            self.summary_frame(),
            min_positive_pnl=0.0,
            min_trades=1,
            min_active_months=0,
            min_worst_pnl=-float("inf"),
            max_drawdown=float("inf"),
        )

        self.assertEqual(selected["selected"], "no_trade")

    def test_standard_selector_selects_positive_eligible_policy(self):
        frame = self.summary_frame()
        frame.loc[0, "validation_total"] = 5.0

        selected = entry_ev_admission_selection.select_standard_policy(
            frame,
            min_positive_pnl=0.0,
            min_trades=1,
            min_active_months=0,
            min_worst_pnl=-float("inf"),
            max_drawdown=float("inf"),
        )

        self.assertEqual(selected["selected"], "policy")
        self.assertEqual(float(selected["entry_threshold"]), 12.0)
        self.assertEqual(float(selected["short_entry_threshold_offset"]), 6.0)

    def test_standard_selector_honors_support_and_worst_gates(self):
        frame = self.summary_frame()
        frame.loc[0, "validation_total"] = 5.0
        frame.loc[0, "validation_active_months"] = 1

        selected = entry_ev_admission_selection.select_standard_policy(
            frame,
            min_positive_pnl=0.0,
            min_trades=1,
            min_active_months=2,
            min_worst_pnl=0.0,
            max_drawdown=float("inf"),
        )

        self.assertEqual(selected["selected"], "no_trade")

    def test_diagnostic_near_notrade_prefers_conservative_thresholds(self):
        selected = entry_ev_admission_selection.select_near_notrade_diagnostic(
            self.summary_frame(),
            near_notrade_tolerance=2.0,
            max_trades=10,
        )

        self.assertEqual(selected["selected"], "policy")
        self.assertEqual(float(selected["entry_threshold"]), 12.0)
        self.assertEqual(float(selected["short_entry_threshold_offset"]), 6.0)

    def test_aggregate_validation_sums_by_family_and_policy(self):
        frame = pd.DataFrame(
            {
                "family": ["calibrated", "calibrated"],
                "month": ["2024-03", "2024-04"],
                "policy": ["timed_ev", "timed_ev"],
                "entry_threshold": [12.0, 12.0],
                "long_entry_threshold_offset": [0.0, 0.0],
                "short_entry_threshold_offset": [6.0, 6.0],
                "exit_threshold": [0.0, 0.0],
                "side_margin": [5.0, 5.0],
                "risk_penalty": [0.0, 0.0],
                "fixed_horizon_score_mode": ["max", "max"],
                "min_predicted_hold_minutes": [1.0, 1.0],
                "max_predicted_hold_minutes": [260.0, 260.0],
                "min_valid_predicted_hold_minutes": [30.0, 30.0],
                "total_adjusted_pnl": [-16.0, 14.0],
                "total_raw_pnl": [-15.0, 15.0],
                "trade_count": [2, 5],
                "win_rate": [0.5, 0.6],
                "max_drawdown": [17.0, 21.0],
                "forced_exit_count": [0, 0],
                "long_trade_count": [1, 0],
                "short_trade_count": [1, 5],
                "long_adjusted_pnl": [1.0, 0.0],
                "short_adjusted_pnl": [-17.0, 14.0],
                "ev_overestimate_vs_realized_mean": [20.0, 16.0],
            }
        )
        frame = entry_ev_admission_selection.normalize_sweep_metrics(frame, "test")

        summary = entry_ev_admission_selection.aggregate_validation(frame)

        self.assertEqual(len(summary), 1)
        self.assertAlmostEqual(float(summary.loc[0, "validation_total"]), -2.0)
        self.assertEqual(int(summary.loc[0, "validation_trades"]), 7)
        self.assertEqual(int(summary.loc[0, "validation_active_months"]), 2)
        self.assertAlmostEqual(float(summary.loc[0, "validation_ev_over_realized"]), 18.0)

    def test_multiwindow_selector_requires_positive_windows(self):
        frame = pd.DataFrame(
            {
                "family": ["win_a", "win_b"],
                "month": ["2024-03", "2025-01"],
                "policy": ["timed_ev", "timed_ev"],
                "entry_threshold": [12.0, 12.0],
                "long_entry_threshold_offset": [0.0, 0.0],
                "short_entry_threshold_offset": [6.0, 6.0],
                "exit_threshold": [0.0, 0.0],
                "side_margin": [5.0, 5.0],
                "risk_penalty": [0.0, 0.0],
                "fixed_horizon_score_mode": ["max", "max"],
                "min_predicted_hold_minutes": [1.0, 1.0],
                "max_predicted_hold_minutes": [260.0, 260.0],
                "min_valid_predicted_hold_minutes": [30.0, 30.0],
                "total_adjusted_pnl": [20.0, -5.0],
                "total_raw_pnl": [20.0, -4.0],
                "trade_count": [12, 11],
                "win_rate": [0.7, 0.4],
                "max_drawdown": [3.0, 6.0],
                "forced_exit_count": [0, 0],
                "long_trade_count": [6, 10],
                "short_trade_count": [6, 1],
                "long_adjusted_pnl": [10.0, -6.0],
                "short_adjusted_pnl": [10.0, 1.0],
            }
        )
        frame = entry_ev_admission_selection.normalize_sweep_metrics(frame, "test")

        summary = entry_ev_admission_selection.aggregate_multiwindow_validation(frame)

        self.assertEqual(len(summary), 1)
        self.assertEqual(int(summary.loc[0, "validation_windows"]), 2)
        self.assertEqual(int(summary.loc[0, "validation_positive_windows"]), 1)
        self.assertAlmostEqual(float(summary.loc[0, "validation_worst_window"]), -5.0)

        selected = entry_ev_admission_selection.select_standard_policy(
            summary,
            min_positive_pnl=0.0,
            min_trades=1,
            min_active_months=0,
            min_worst_pnl=-float("inf"),
            max_drawdown=float("inf"),
            min_windows=2,
            min_positive_windows=2,
        )

        self.assertEqual(selected["selected"], "no_trade")

        selected = entry_ev_admission_selection.select_standard_policy(
            summary,
            min_positive_pnl=0.0,
            min_trades=1,
            min_active_months=0,
            min_worst_pnl=-float("inf"),
            max_drawdown=float("inf"),
            min_windows=2,
            min_positive_windows=1,
        )

        self.assertEqual(selected["selected"], "policy")


if __name__ == "__main__":
    unittest.main()
