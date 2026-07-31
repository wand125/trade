import importlib.util
import sys
import unittest
from pathlib import Path

import pandas as pd


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "experiments"
    / "entry_ev_direction_inversion_selector_diagnostics.py"
)
SPEC = importlib.util.spec_from_file_location(
    "entry_ev_direction_inversion_selector_diagnostics",
    SCRIPT_PATH,
)
entry_ev_direction_inversion_selector_diagnostics = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = entry_ev_direction_inversion_selector_diagnostics
SPEC.loader.exec_module(entry_ev_direction_inversion_selector_diagnostics)


class EntryEvDirectionInversionSelectorDiagnosticsTests(unittest.TestCase):
    def test_selected_direction_features_follow_trade_side(self):
        frame = pd.DataFrame(
            {
                "direction": ["long", "short"],
                "pred_direction_inversion_long_predicted_direction_inversion_risk": [0.7, 0.2],
                "pred_direction_inversion_short_predicted_direction_inversion_risk": [0.1, 0.8],
                "pred_direction_inversion_long_direction_inversion_prediction_support": [4, 5],
                "pred_direction_inversion_short_direction_inversion_prediction_support": [6, 7],
                "pred_direction_inversion_long_direction_inversion_prediction_source": [
                    "bucket",
                    "global",
                ],
                "pred_direction_inversion_short_direction_inversion_prediction_source": [
                    "global",
                    "bucket",
                ],
                "pred_direction_inversion_long_selected_risk_bucket": ["high", "medium"],
                "pred_direction_inversion_short_selected_risk_bucket": ["low", "extreme"],
                "pred_direction_inversion_long_selected_side_support_bucket": ["high", "medium"],
                "pred_direction_inversion_short_selected_side_support_bucket": ["low", "high"],
                "pred_direction_inversion_long_selected_side_pressure_bucket": ["low", "medium"],
                "pred_direction_inversion_short_selected_side_pressure_bucket": ["high", "low"],
                "pred_direction_inversion_bucket_s0p1_long_best_adjusted_pnl": [9.0, 4.0],
                "pred_direction_inversion_bucket_s0p1_short_best_adjusted_pnl": [2.0, 5.0],
                "pred_side_prior_pressure_s0p5_long_best_adjusted_pnl": [10.0, 4.0],
                "pred_side_prior_pressure_s0p5_short_best_adjusted_pnl": [2.0, 8.0],
            }
        )

        enriched = entry_ev_direction_inversion_selector_diagnostics.add_selected_direction_features(
            frame
        )

        self.assertEqual(enriched["selected_direction_inversion_risk"].tolist(), [0.7, 0.8])
        self.assertEqual(enriched["selected_direction_inversion_source"].tolist(), ["bucket", "bucket"])
        self.assertEqual(enriched["selected_direction_inversion_support"].tolist(), [4.0, 7.0])
        self.assertEqual(enriched["selected_direction_score_delta"].tolist(), [-1.0, -3.0])

    def test_selector_gate_blocks_negative_and_high_global_share(self):
        summary = pd.DataFrame(
            {
                "run_name": ["a", "b"],
                "candidate": ["c1", "c2"],
                "total_pnl": [5.0, -1.0],
                "min_role_total_pnl": [5.0, -1.0],
                "min_month_pnl": [1.0, -1.0],
                "trade_count": [20, 20],
                "max_drawdown": [3.0, 3.0],
                "bucket_high_risk_share": [0.2, 0.2],
                "global_prediction_share": [0.1, 0.8],
                "bucket_prediction_share": [0.6, 0.2],
            }
        )

        gated = entry_ev_direction_inversion_selector_diagnostics.apply_selector_gates(
            summary,
            min_total_pnl=0.0,
            min_role_total_pnl=0.0,
            min_month_pnl=0.0,
            min_trades=10,
            max_drawdown=10.0,
            max_bucket_high_risk_share=0.5,
            max_global_prediction_share=0.5,
            min_bucket_prediction_share=0.5,
        )

        eligible = gated.set_index("candidate")["eligible"].to_dict()
        blockers = gated.set_index("candidate")["blockers"].to_dict()
        self.assertTrue(eligible["c1"])
        self.assertFalse(eligible["c2"])
        self.assertIn("total_pnl_below_floor", blockers["c2"])
        self.assertIn("global_prediction_share_high", blockers["c2"])


if __name__ == "__main__":
    unittest.main()
