import importlib.util
import sys
import unittest
from pathlib import Path

import pandas as pd


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "experiments"
    / "entry_ev_side_balance_downside_interaction.py"
)
SPEC = importlib.util.spec_from_file_location(
    "entry_ev_side_balance_downside_interaction",
    SCRIPT_PATH,
)
entry_ev_side_balance_downside_interaction = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = entry_ev_side_balance_downside_interaction
SPEC.loader.exec_module(entry_ev_side_balance_downside_interaction)


class EntryEvSideBalanceDownsideInteractionTests(unittest.TestCase):
    def trades(self):
        return pd.DataFrame(
            {
                "role": ["valid", "valid", "valid"],
                "candidate": ["q99", "q99", "q99"],
                "month": ["2024-01", "2024-02", "2024-02"],
                "direction": ["long", "long", "short"],
                "entry_decision_timestamp": [
                    "2024-01-05T00:00:00Z",
                    "2024-02-05T00:00:00Z",
                    "2024-02-06T00:00:00Z",
                ],
                "combined_regime": ["range", "range", "range"],
                "session_regime": ["asia", "asia", "asia"],
                "adjusted_pnl": [-10.0, -3.0, 5.0],
                "direction_error": [True, False, False],
                "no_edge_entry": [False, False, False],
                "exit_regret": [12.0, 2.0, 1.0],
                "pred_side_balance_long_share_drift": [0.10, 0.10, 0.10],
                "pred_side_balance_long_scale": [0.90, 0.90, 0.90],
                "pred_side_balance_short_scale": [1.00, 1.00, 1.00],
            }
        )

    def test_prior_downside_features_use_only_prior_months_and_matching_context(self):
        frame = entry_ev_side_balance_downside_interaction.normalize_trades(self.trades())
        enriched = (
            entry_ev_side_balance_downside_interaction.add_prior_downside_features(
                frame,
                frame,
                min_prior_months=1,
                recent_month_count=0,
                support_scale=1.0,
                pnl_scale=20.0,
                large_exit_regret_threshold=10.0,
            )
        )

        january = enriched[enriched["month"].eq("2024-01")].iloc[0]
        feb_long = enriched[
            enriched["month"].eq("2024-02") & enriched["direction"].eq("long")
        ].iloc[0]
        feb_short = enriched[
            enriched["month"].eq("2024-02") & enriched["direction"].eq("short")
        ].iloc[0]

        self.assertEqual(january["prior_trade_count"], 0.0)
        self.assertEqual(feb_long["prior_trade_count"], 1.0)
        self.assertEqual(feb_long["prior_loss_rate"], 1.0)
        self.assertEqual(feb_long["prior_direction_error_rate"], 1.0)
        self.assertEqual(feb_long["prior_large_exit_regret_rate"], 1.0)
        self.assertGreater(feb_long["prior_downside_risk_score"], 0.0)
        self.assertEqual(feb_short["prior_trade_count"], 0.0)

    def test_interaction_screen_removes_only_risky_drift_trade(self):
        frame = entry_ev_side_balance_downside_interaction.normalize_trades(self.trades())
        enriched = (
            entry_ev_side_balance_downside_interaction.add_prior_downside_features(
                frame,
                frame,
                min_prior_months=1,
                recent_month_count=0,
                support_scale=1.0,
                pnl_scale=20.0,
                large_exit_regret_threshold=10.0,
            )
        )
        screens = (
            entry_ev_side_balance_downside_interaction.summarize_interaction_screens(
                enriched,
                drift_thresholds=[0.05],
                risk_thresholds=[0.10],
                interaction_thresholds=[0.005],
            )
        )
        screen = screens[
            screens["screen"].eq("risk_and_overrepresented")
            & screens["candidate"].eq("q99")
        ].iloc[0]

        self.assertEqual(screen["removed_trade_count"], 1)
        self.assertAlmostEqual(screen["removed_total_pnl"], -3.0)
        self.assertAlmostEqual(screen["kept_total_pnl"], -5.0)
        self.assertAlmostEqual(screen["pointwise_delta_if_removed"], 3.0)


if __name__ == "__main__":
    unittest.main()
