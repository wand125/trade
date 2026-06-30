import importlib.util
import sys
import unittest
from pathlib import Path

import pandas as pd


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "experiments"
    / "entry_ev_side_balance_feature_diagnostics.py"
)
SPEC = importlib.util.spec_from_file_location(
    "entry_ev_side_balance_feature_diagnostics",
    SCRIPT_PATH,
)
entry_ev_side_balance_feature_diagnostics = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = entry_ev_side_balance_feature_diagnostics
SPEC.loader.exec_module(entry_ev_side_balance_feature_diagnostics)


class EntryEvSideBalanceFeatureDiagnosticsTests(unittest.TestCase):
    def trades(self):
        return pd.DataFrame(
            {
                "role": ["fresh", "fresh", "refit", "refit"],
                "candidate": ["q95", "q95", "q95", "q95"],
                "month": ["2024-03", "2024-03", "2025-01", "2025-01"],
                "direction": ["long", "short", "long", "short"],
                "adjusted_pnl": [-5.0, 3.0, -2.0, 4.0],
                "pred_side_balance_long_share_drift": [0.10, 0.10, -0.08, -0.08],
                "pred_side_balance_long_scale": [0.90, 0.90, 1.00, 1.00],
                "pred_side_balance_short_scale": [1.00, 1.00, 0.92, 0.92],
                "pred_side_balance_prior_count": [100.0, 100.0, 120.0, 120.0],
                "pred_side_balance_context_count": [20.0, 20.0, 30.0, 30.0],
                "pred_side_balance_context_support_weight": [0.2, 0.2, 0.3, 0.3],
                "direction_error": [True, False, True, False],
                "no_edge_entry": [False, False, True, False],
            }
        )

    def test_add_side_balance_trade_features_marks_selected_overrepresented_side(self):
        enriched = (
            entry_ev_side_balance_feature_diagnostics.add_side_balance_trade_features(
                self.trades()
            )
        )

        self.assertTrue(enriched.iloc[0]["side_balance_selected_side_overrepresented"])
        self.assertFalse(enriched.iloc[1]["side_balance_selected_side_overrepresented"])
        self.assertFalse(enriched.iloc[2]["side_balance_selected_side_overrepresented"])
        self.assertTrue(enriched.iloc[3]["side_balance_selected_side_overrepresented"])
        self.assertAlmostEqual(
            enriched.iloc[0]["side_balance_signed_drift_for_trade"],
            0.10,
        )
        self.assertAlmostEqual(
            enriched.iloc[1]["side_balance_signed_drift_for_trade"],
            -0.10,
        )
        self.assertAlmostEqual(enriched.iloc[0]["side_balance_taken_scale"], 0.90)
        self.assertAlmostEqual(enriched.iloc[3]["side_balance_taken_scale"], 0.92)

    def test_summarize_screen_effects_reports_pointwise_removed_pnl(self):
        enriched = (
            entry_ev_side_balance_feature_diagnostics.add_side_balance_trade_features(
                self.trades()
            )
        )
        effects = entry_ev_side_balance_feature_diagnostics.summarize_screen_effects(
            enriched,
            [0.05],
        )
        overrep = effects[
            effects["screen"].eq("selected_overrepresented")
            & effects["threshold"].eq(0.05)
        ].iloc[0]

        self.assertEqual(overrep["removed_trade_count"], 2)
        self.assertAlmostEqual(overrep["removed_total_pnl"], -1.0)
        self.assertAlmostEqual(overrep["kept_total_pnl"], 1.0)
        self.assertAlmostEqual(overrep["pointwise_delta_if_removed"], 1.0)

    def test_summarize_groups_includes_side_balance_feature_means(self):
        enriched = (
            entry_ev_side_balance_feature_diagnostics.add_side_balance_trade_features(
                self.trades()
            )
        )
        summary = entry_ev_side_balance_feature_diagnostics.summarize_groups(
            enriched,
            ["role", "candidate"],
        )
        fresh = summary[summary["role"].eq("fresh")].iloc[0]

        self.assertEqual(fresh["trade_count"], 2)
        self.assertAlmostEqual(fresh["total_adjusted_pnl"], -2.0)
        self.assertAlmostEqual(fresh["abs_drift_mean"], 0.10)
        self.assertAlmostEqual(fresh["selected_side_overrepresented_share"], 0.5)
        self.assertAlmostEqual(fresh["taken_penalty_mean"], 0.05)


if __name__ == "__main__":
    unittest.main()
