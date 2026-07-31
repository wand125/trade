import importlib.util
import sys
import unittest
from pathlib import Path

import pandas as pd


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "experiments"
    / "entry_ev_executable_ev_selector_diagnostics.py"
)
SPEC = importlib.util.spec_from_file_location(
    "entry_ev_executable_ev_selector_diagnostics",
    SCRIPT_PATH,
)
entry_ev_executable_ev_selector_diagnostics = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = entry_ev_executable_ev_selector_diagnostics
SPEC.loader.exec_module(entry_ev_executable_ev_selector_diagnostics)


class EntryEvExecutableEvSelectorDiagnosticsTests(unittest.TestCase):
    def trades(self):
        return pd.DataFrame(
            {
                "role": ["valid_a", "valid_a", "valid_b", "valid_b"],
                "candidate": ["good", "bad", "good", "bad"],
                "month": ["2024-01", "2024-01", "2024-02", "2024-02"],
                "direction": ["long", "short", "short", "short"],
                "entry_decision_timestamp": [
                    "2024-01-01T00:00:00Z",
                    "2024-01-01T00:05:00Z",
                    "2024-02-01T00:00:00Z",
                    "2024-02-01T00:05:00Z",
                ],
                "adjusted_pnl": [5.0, 4.0, 6.0, -3.0],
                "pred_raw_executable_ev": [10.0, 10.0, 10.0, 10.0],
                "pred_capture_calibrated_ev": [4.0, 1.0, 5.0, 1.0],
                "executable_capture_factor": [0.4, 0.1, 0.5, 0.1],
                "raw_ev_abs_error": [5.0, 6.0, 4.0, 13.0],
                "capture_calibrated_ev_abs_error": [1.0, 3.0, 1.0, 4.0],
                "raw_ev_error_vs_realized": [5.0, 6.0, 4.0, 13.0],
                "capture_calibrated_ev_error_vs_realized": [-1.0, -3.0, -1.0, 4.0],
                "prior_capture_support_weight": [1.0, 1.0, 1.0, 1.0],
                "exit_capture_failure": [False, True, False, True],
                "same_side_missed_loss": [False, False, False, True],
                "direction_error": [False, True, False, True],
            }
        )

    def test_summarize_candidates_tracks_executable_ev_features(self):
        frame = entry_ev_executable_ev_selector_diagnostics.normalize_trade_frame(
            self.trades()
        )
        role_month = entry_ev_executable_ev_selector_diagnostics.summarize_role_months(frame)
        summary = entry_ev_executable_ev_selector_diagnostics.summarize_candidates(role_month)
        good = summary[summary["candidate"].eq("good")].iloc[0]

        self.assertEqual(good["trade_count"], 2)
        self.assertEqual(good["total_pnl"], 11.0)
        self.assertEqual(good["min_role_total_pnl"], 5.0)
        self.assertAlmostEqual(good["capture_ev_mean"], 4.5)
        self.assertAlmostEqual(good["mae_delta_raw_minus_capture"], 3.5)

    def test_selector_keeps_notrade_when_month_floor_fails(self):
        frame = entry_ev_executable_ev_selector_diagnostics.normalize_trade_frame(
            self.trades()
        )
        role_month = entry_ev_executable_ev_selector_diagnostics.summarize_role_months(frame)
        summary = entry_ev_executable_ev_selector_diagnostics.summarize_candidates(role_month)
        gated = entry_ev_executable_ev_selector_diagnostics.apply_selector_gates(
            summary,
            min_roles=2,
            min_positive_roles=2,
            min_active_roles=2,
            min_total_pnl=0.0,
            min_role_total_pnl=0.0,
            min_month_pnl=0.0,
            min_role_trades=1,
            min_month_trades=1,
            max_drawdown=float("inf"),
            max_side_trade_share=float("inf"),
            min_capture_ev_mean=0.0,
            max_capture_ev_low2_share=float("inf"),
        )
        selected = entry_ev_executable_ev_selector_diagnostics.select_policy(gated)

        self.assertEqual(selected["selected"], "policy")
        self.assertEqual(selected["candidate"], "good")

        bad = gated[gated["candidate"].eq("bad")].iloc[0]
        self.assertIn("role_total_pnl_below_floor", bad["blockers"])

    def test_capture_ev_feature_can_block_low_quality_candidate(self):
        frame = entry_ev_executable_ev_selector_diagnostics.normalize_trade_frame(
            self.trades()
        )
        role_month = entry_ev_executable_ev_selector_diagnostics.summarize_role_months(frame)
        summary = entry_ev_executable_ev_selector_diagnostics.summarize_candidates(role_month)
        gated = entry_ev_executable_ev_selector_diagnostics.apply_selector_gates(
            summary,
            min_roles=2,
            min_positive_roles=1,
            min_active_roles=2,
            min_total_pnl=-10.0,
            min_role_total_pnl=-10.0,
            min_month_pnl=-10.0,
            min_role_trades=1,
            min_month_trades=1,
            max_drawdown=float("inf"),
            max_side_trade_share=float("inf"),
            min_capture_ev_mean=2.0,
            max_capture_ev_low2_share=0.25,
        )
        bad = gated[gated["candidate"].eq("bad")].iloc[0]

        self.assertIn("capture_ev_mean_low", bad["blockers"])
        self.assertIn("capture_ev_low2_share_high", bad["blockers"])


if __name__ == "__main__":
    unittest.main()
