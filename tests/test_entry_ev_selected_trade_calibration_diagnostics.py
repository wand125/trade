import importlib.util
import sys
import unittest
from pathlib import Path

import pandas as pd


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "experiments"
    / "entry_ev_selected_trade_calibration_diagnostics.py"
)
SPEC = importlib.util.spec_from_file_location(
    "entry_ev_selected_trade_calibration_diagnostics",
    SCRIPT_PATH,
)
entry_ev_selected_trade_calibration_diagnostics = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = entry_ev_selected_trade_calibration_diagnostics
SPEC.loader.exec_module(entry_ev_selected_trade_calibration_diagnostics)


class EntryEvSelectedTradeCalibrationDiagnosticsTests(unittest.TestCase):
    def prediction_frame(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "supervised_target_mode": ["pnl", "pnl", "factor", "factor"],
                "role": ["cal", "cal", "cal", "cal"],
                "source": ["s1", "s1", "s1", "s1"],
                "family": ["fam", "fam", "fam", "fam"],
                "candidate": ["q95", "q95", "q95", "q95"],
                "month": ["2024-01", "2024-01", "2024-01", "2024-01"],
                "direction": ["long", "short", "long", "short"],
                "combined_regime": ["range", "down", "range", "down"],
                "session_regime": ["asia", "london", "asia", "london"],
                "adjusted_pnl": [2.0, -3.0, 2.0, -3.0],
                "score_raw_ev": [10.0, 8.0, 10.0, 8.0],
                "pred_supervised_pnl_ev": [1.5, 1.0, None, None],
                "pred_supervised_factor_ev": [None, None, 1.0, -1.0],
                "pred_supervised_pnl_train_rows": [30, 30, None, None],
                "pred_supervised_factor_train_rows": [None, None, 40, 40],
                "pred_supervised_pnl_train_months": [2, 2, None, None],
                "pred_supervised_factor_train_months": [None, None, 3, 3],
                "pred_supervised_pnl_model_used": [True, True, False, False],
                "pred_supervised_factor_model_used": [False, False, True, True],
                "pred_taken_ev": [10.0, 8.0, 10.0, 8.0],
                "selected_loss_first_prob": [0.2, 0.6, 0.2, 0.6],
                "pred_side_confidence_gap": [0.1, -0.2, 0.1, -0.2],
                "pred_taken_entry_local_rank": [0.8, 0.4, 0.8, 0.4],
            }
        )

    def test_add_mode_scores_uses_mode_specific_score_columns(self):
        normalized = entry_ev_selected_trade_calibration_diagnostics.normalize_predictions(
            self.prediction_frame()
        )
        enriched = entry_ev_selected_trade_calibration_diagnostics.add_mode_scores(
            normalized,
            large_loss_threshold=-2.0,
        )

        pnl_short = enriched[
            enriched["supervised_target_mode"].eq("pnl") & enriched["direction"].eq("short")
        ].iloc[0]
        factor_short = enriched[
            enriched["supervised_target_mode"].eq("factor")
            & enriched["direction"].eq("short")
        ].iloc[0]

        self.assertEqual(pnl_short["score"], 1.0)
        self.assertEqual(pnl_short["score_error"], 4.0)
        self.assertEqual(pnl_short["train_rows"], 30)
        self.assertEqual(factor_short["score"], -1.0)
        self.assertEqual(factor_short["score_error"], 2.0)
        self.assertEqual(factor_short["train_rows"], 40)
        self.assertTrue(bool(factor_short["is_large_loss"]))

    def test_group_summary_reports_bias_and_loss_counts(self):
        normalized = entry_ev_selected_trade_calibration_diagnostics.normalize_predictions(
            self.prediction_frame()
        )
        enriched = entry_ev_selected_trade_calibration_diagnostics.add_mode_scores(
            normalized,
            large_loss_threshold=-2.0,
        )
        summary = entry_ev_selected_trade_calibration_diagnostics.summarize_groups(
            enriched,
            [["direction"]],
        )

        pnl_short = summary[
            summary["supervised_target_mode"].eq("pnl")
            & summary["group_key"].eq("short")
        ].iloc[0]
        self.assertEqual(pnl_short["trade_count"], 1)
        self.assertEqual(pnl_short["loss_count"], 1)
        self.assertEqual(pnl_short["bias"], 4.0)
        self.assertEqual(pnl_short["mae"], 4.0)

    def test_bin_summary_includes_score_and_support_bins(self):
        normalized = entry_ev_selected_trade_calibration_diagnostics.normalize_predictions(
            self.prediction_frame()
        )
        enriched = entry_ev_selected_trade_calibration_diagnostics.add_mode_scores(
            normalized,
            large_loss_threshold=-2.0,
        )
        summary = entry_ev_selected_trade_calibration_diagnostics.summarize_bins(
            enriched,
            columns=["score", "train_rows"],
            bins=2,
        )

        self.assertIn("score", set(summary["bin_source"]))
        self.assertIn("train_rows", set(summary["bin_source"]))
        self.assertGreaterEqual(int(summary["trade_count"].sum()), 4)


if __name__ == "__main__":
    unittest.main()
