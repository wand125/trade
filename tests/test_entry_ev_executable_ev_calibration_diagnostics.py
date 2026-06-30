import importlib.util
import sys
import unittest
from pathlib import Path

import pandas as pd


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "experiments"
    / "entry_ev_executable_ev_calibration_diagnostics.py"
)
SPEC = importlib.util.spec_from_file_location(
    "entry_ev_executable_ev_calibration_diagnostics",
    SCRIPT_PATH,
)
entry_ev_executable_ev_calibration_diagnostics = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = entry_ev_executable_ev_calibration_diagnostics
SPEC.loader.exec_module(entry_ev_executable_ev_calibration_diagnostics)


class EntryEvExecutableEvCalibrationDiagnosticsTests(unittest.TestCase):
    def test_add_capture_ratio_columns_clips_realized_capture(self):
        frame = pd.DataFrame(
            {
                "adjusted_pnl": [-20.0, 5.0, 4.0],
                "actual_taken_best_adjusted_pnl": [10.0, 10.0, -1.0],
            }
        )

        enriched = entry_ev_executable_ev_calibration_diagnostics.add_capture_ratio_columns(
            frame,
            min_oracle_edge=0.0,
            min_capture_factor=-1.0,
            max_capture_factor=1.0,
        )

        self.assertEqual(enriched["calibration_same_side_oracle_edge"].tolist(), [True, True, False])
        self.assertEqual(enriched["capture_ratio_clipped"].iloc[0], -1.0)
        self.assertEqual(enriched["capture_ratio_clipped"].iloc[1], 0.5)
        self.assertTrue(pd.isna(enriched["capture_ratio_clipped"].iloc[2]))

    def test_add_executable_ev_calibration_uses_only_prior_months(self):
        target = pd.DataFrame(
            {
                "role": ["fresh", "fresh"],
                "candidate": ["q95", "q95"],
                "month": ["2024-03", "2024-04"],
                "direction": ["short", "short"],
                "entry_decision_timestamp": [
                    "2024-03-10T00:00:00Z",
                    "2024-04-10T00:00:00Z",
                ],
                "combined_regime": ["range", "range"],
                "session_regime": ["asia", "asia"],
                "adjusted_pnl": [1.0, 1.0],
                "actual_taken_best_adjusted_pnl": [10.0, 10.0],
                "pred_taken_ev": [10.0, 10.0],
            }
        )
        prior = pd.DataFrame(
            {
                "role": ["cal", "fresh", "future"],
                "candidate": ["q95", "q95", "q95"],
                "month": ["2024-02", "2024-03", "2024-04"],
                "direction": ["short", "short", "short"],
                "entry_decision_timestamp": [
                    "2024-02-10T00:00:00Z",
                    "2024-03-10T00:00:00Z",
                    "2024-04-10T00:00:00Z",
                ],
                "combined_regime": ["range", "range", "range"],
                "session_regime": ["asia", "asia", "asia"],
                "adjusted_pnl": [5.0, -5.0, 10.0],
                "actual_taken_best_adjusted_pnl": [10.0, 10.0, 10.0],
                "pred_taken_ev": [10.0, 10.0, 10.0],
            }
        )
        target = entry_ev_executable_ev_calibration_diagnostics.normalize_trade_frame(
            target,
            name="target",
        )
        prior = entry_ev_executable_ev_calibration_diagnostics.normalize_trade_frame(
            prior,
            name="prior",
        )
        target = entry_ev_executable_ev_calibration_diagnostics.add_capture_ratio_columns(
            target,
            min_oracle_edge=0.0,
            min_capture_factor=-1.0,
            max_capture_factor=1.0,
        )
        prior = entry_ev_executable_ev_calibration_diagnostics.add_capture_ratio_columns(
            prior,
            min_oracle_edge=0.0,
            min_capture_factor=-1.0,
            max_capture_factor=1.0,
        )

        enriched = entry_ev_executable_ev_calibration_diagnostics.add_executable_ev_calibration(
            target,
            prior,
            min_prior_months=1,
            recent_month_count=0,
            support_scale=2.0,
            default_capture_factor=1.0,
            min_capture_factor=-1.0,
            max_capture_factor=1.0,
        )

        march = enriched[enriched["month"].eq("2024-03")].iloc[0]
        april = enriched[enriched["month"].eq("2024-04")].iloc[0]
        self.assertEqual(march["prior_context_capture_count"], 1)
        self.assertAlmostEqual(march["context_executable_capture_factor"], 0.5)
        self.assertAlmostEqual(march["executable_capture_factor"], 0.5)
        self.assertEqual(april["prior_context_capture_count"], 2)
        self.assertAlmostEqual(april["context_executable_capture_factor"], 0.0)
        self.assertAlmostEqual(april["executable_capture_factor"], 0.0)

    def test_summarize_thresholds_blocks_low_calibrated_ev(self):
        frame = pd.DataFrame(
            {
                "role": ["fresh", "fresh", "fresh"],
                "candidate": ["q95", "q95", "q95"],
                "adjusted_pnl": [-5.0, 3.0, -2.0],
                "exit_capture_failure": [True, False, True],
                "pred_capture_calibrated_ev": [-1.0, 6.0, 2.0],
            }
        )

        summary = entry_ev_executable_ev_calibration_diagnostics.summarize_thresholds(
            frame,
            ["role", "candidate"],
            [0.0, 5.0],
            score_column="pred_capture_calibrated_ev",
            score_label="capture_calibrated_ev",
        )
        zero = summary[summary["threshold"].eq(0.0)].iloc[0]
        five = summary[summary["threshold"].eq(5.0)].iloc[0]

        self.assertEqual(zero["flagged_trade_count"], 1)
        self.assertEqual(zero["flagged_adjusted_pnl"], -5.0)
        self.assertEqual(zero["block_delta_if_removed"], 5.0)
        self.assertEqual(five["flagged_trade_count"], 2)
        self.assertEqual(five["flagged_adjusted_pnl"], -7.0)
        self.assertEqual(five["failure_recall"], 1.0)


if __name__ == "__main__":
    unittest.main()
