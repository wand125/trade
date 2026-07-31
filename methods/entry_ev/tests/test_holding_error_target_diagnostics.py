import importlib.util
import unittest
from pathlib import Path

import pandas as pd


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "experiments"
    / "holding_error_target_diagnostics.py"
)
SPEC = importlib.util.spec_from_file_location("holding_error_target_diagnostics", SCRIPT_PATH)
holding_error_target_diagnostics = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(holding_error_target_diagnostics)


class HoldingErrorTargetDiagnosticsTests(unittest.TestCase):
    def test_prepare_holding_error_frame_splits_shortening_and_extension_targets(self):
        frame = pd.DataFrame(
            {
                "case_label": ["risk5", "risk5", "risk5"],
                "month": ["2025-01", "2025-01", "2025-01"],
                "direction": ["long", "long", "short"],
                "combined_regime": ["range_low_vol", "range_low_vol", "up_low_vol"],
                "session_regime": ["london", "asia", "asia"],
                "base_adjusted_pnl": [-6.0, 4.0, -2.0],
                "base_holding_minutes": [120.0, 60.0, 90.0],
                "pred_taken_best_holding_minutes": [300.0, 240.0, 120.0],
                "actual_taken_best_holding_minutes": [30.0, 180.0, 95.0],
                "exit_regret": [8.0, 7.0, 2.0],
            }
        )

        output = holding_error_target_diagnostics.prepare_holding_error_frame(
            frame,
            pnl_source="base",
            min_abs_regret=5.0,
            min_abs_gap_minutes=30.0,
        )

        self.assertEqual(output["oracle_holding_gap_minutes"].tolist(), [-90.0, 120.0, 5.0])
        self.assertEqual(output["holding_error_minutes"].tolist(), [180.0, 180.0, 30.0])
        self.assertEqual(output["pred_minus_oracle_holding_minutes"].tolist(), [270.0, 60.0, 25.0])
        self.assertEqual(output["exit_shortening_target"].tolist(), [True, False, False])
        self.assertEqual(output["hold_extension_target"].tolist(), [False, True, False])
        self.assertEqual(output["holding_mismatch_target"].tolist(), [True, True, False])

    def test_walkforward_profiles_uses_prior_months_only(self):
        frame = pd.DataFrame(
            {
                "case_label": ["risk5", "risk5", "risk5", "risk5"],
                "month": ["2025-01", "2025-01", "2025-02", "2025-03"],
                "direction": ["long", "long", "long", "long"],
                "combined_regime": ["range_low_vol"] * 4,
                "session_regime": ["london"] * 4,
                "analysis_adjusted_pnl": [-4.0, -6.0, 2.0, -10.0],
                "positive_pnl": [False, False, True, False],
                "large_negative_pnl": [False, False, False, False],
                "exit_regret": [8.0, 9.0, 1.0, 7.0],
                "holding_error_minutes": [100.0, 120.0, 20.0, 140.0],
                "holding_error_abs": [100.0, 120.0, 20.0, 140.0],
                "oracle_holding_gap_minutes": [-90.0, -80.0, 40.0, -70.0],
                "oracle_gap_abs": [90.0, 80.0, 40.0, 70.0],
                "pred_minus_oracle_holding_minutes": [190.0, 200.0, -20.0, 210.0],
                "exit_shortening_target": [True, True, False, True],
                "hold_extension_target": [False, False, False, False],
                "holding_mismatch_target": [True, True, False, True],
            }
        )

        output = holding_error_target_diagnostics.walkforward_target_profiles(
            frame,
            ["case_label", "direction", "combined_regime", "session_regime"],
            min_prior_support=2,
        )

        march = output[output["target_month"].eq("2025-03")].iloc[0]
        self.assertEqual(march["prior_trade_count"], 3)
        self.assertAlmostEqual(march["prior_avg_adjusted_pnl"], -8.0 / 3.0)
        self.assertEqual(march["holdout_trade_count"], 1)
        self.assertAlmostEqual(march["holdout_avg_adjusted_pnl"], -10.0)

    def test_prepare_holding_error_frame_drops_rows_missing_selected_side(self):
        frame = pd.DataFrame(
            {
                "month": ["2025-01", "2025-01"],
                "direction": ["long", "short"],
                "base_adjusted_pnl": [1.0, None],
                "base_holding_minutes": [60.0, None],
                "candidate_adjusted_pnl": [1.5, -2.0],
                "candidate_holding_minutes": [60.0, 90.0],
                "pred_taken_best_holding_minutes": [120.0, 180.0],
                "actual_taken_best_holding_minutes": [30.0, 120.0],
                "exit_regret": [6.0, 7.0],
            }
        )

        base = holding_error_target_diagnostics.prepare_holding_error_frame(
            frame,
            pnl_source="base",
            min_abs_regret=5.0,
            min_abs_gap_minutes=30.0,
        )
        candidate = holding_error_target_diagnostics.prepare_holding_error_frame(
            frame,
            pnl_source="candidate",
            min_abs_regret=5.0,
            min_abs_gap_minutes=30.0,
        )

        self.assertEqual(len(base), 1)
        self.assertEqual(base["analysis_adjusted_pnl"].tolist(), [1.0])
        self.assertEqual(len(candidate), 2)
        self.assertEqual(candidate["analysis_adjusted_pnl"].tolist(), [1.5, -2.0])


if __name__ == "__main__":
    unittest.main()
