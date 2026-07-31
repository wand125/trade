import importlib.util
import sys
import unittest
from pathlib import Path

import pandas as pd


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "experiments"
    / "entry_ev_selected_trade_path_compensation_diagnostics.py"
)
SPEC = importlib.util.spec_from_file_location(
    "entry_ev_selected_trade_path_compensation_diagnostics",
    SCRIPT_PATH,
)
entry_ev_selected_trade_path_compensation_diagnostics = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = entry_ev_selected_trade_path_compensation_diagnostics
SPEC.loader.exec_module(entry_ev_selected_trade_path_compensation_diagnostics)


class EntryEvSelectedTradePathCompensationDiagnosticsTests(unittest.TestCase):
    def prediction_frame(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "supervised_target_mode": ["factor"] * 4,
                "group_spec": ["direction,combined_regime,session_regime"] * 4,
                "large_loss_feature_set": ["base"] * 4,
                "month": ["2025-01"] * 4,
                "role": ["cal"] * 4,
                "direction": ["short", "short", "long", "long"],
                "combined_regime": ["down", "down", "range", "range"],
                "session_regime": ["london", "london", "ny", "ny"],
                "adjusted_pnl": [-5.0, 10.0, -4.0, 1.0],
                "is_loss": [True, False, True, False],
                "is_large_loss": [True, False, True, False],
                "pred_large_loss_prob": [0.90, 0.80, 0.70, 0.10],
            }
        )

    def enriched_frame(self) -> pd.DataFrame:
        normalized = (
            entry_ev_selected_trade_path_compensation_diagnostics.normalize_predictions(
                self.prediction_frame(),
                target_modes={"factor"},
                group_specs={"direction,combined_regime,session_regime"},
                feature_sets={"base"},
                context_columns=["direction", "combined_regime", "session_regime"],
            )
        )
        return entry_ev_selected_trade_path_compensation_diagnostics.add_context_month_stats(
            normalized,
            context_columns=["direction", "combined_regime", "session_regime"],
            large_win_threshold=5.0,
        )

    def test_large_loss_is_compensated_by_same_context_month(self):
        enriched = self.enriched_frame()

        compensated_loss = enriched[enriched["adjusted_pnl"].eq(-5.0)].iloc[0]
        uncompensated_loss = enriched[enriched["adjusted_pnl"].eq(-4.0)].iloc[0]

        self.assertEqual(compensated_loss["context_key"], "short|down|london")
        self.assertEqual(compensated_loss["context_month_total_pnl"], 5.0)
        self.assertTrue(bool(compensated_loss["context_month_net_positive"]))
        self.assertTrue(bool(compensated_loss["context_month_has_large_win"]))
        self.assertTrue(bool(compensated_loss["large_loss_compensated_by_context"]))

        self.assertEqual(uncompensated_loss["context_key"], "long|range|ny")
        self.assertEqual(uncompensated_loss["context_month_total_pnl"], -3.0)
        self.assertFalse(bool(uncompensated_loss["context_month_net_positive"]))
        self.assertFalse(bool(uncompensated_loss["large_loss_compensated_by_context"]))

    def test_threshold_summary_reports_flagged_context_compensation(self):
        enriched = self.enriched_frame()
        summary = entry_ev_selected_trade_path_compensation_diagnostics.threshold_summary(
            enriched,
            thresholds=[0.5],
            quantiles=[],
        )
        row = summary.iloc[0]

        self.assertEqual(row["flagged_trade_count"], 3)
        self.assertEqual(row["flagged_pnl"], 1.0)
        self.assertEqual(row["block_delta_if_removed"], -1.0)
        self.assertEqual(row["flagged_large_loss_count"], 2)
        self.assertEqual(row["flagged_compensated_large_loss_count"], 1)
        self.assertEqual(row["flagged_uncompensated_large_loss_count"], 1)
        self.assertEqual(row["flagged_context_month_count"], 2)
        self.assertEqual(row["flagged_positive_context_month_count"], 1)
        self.assertEqual(row["flagged_negative_context_month_count"], 1)
        self.assertEqual(row["flagged_context_month_total_pnl"], 2.0)


if __name__ == "__main__":
    unittest.main()
