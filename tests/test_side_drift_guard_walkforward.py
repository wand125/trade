import importlib.util
import unittest
from pathlib import Path

import pandas as pd


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "experiments"
    / "side_drift_guard_walkforward.py"
)
SPEC = importlib.util.spec_from_file_location("side_drift_guard_walkforward", SCRIPT_PATH)
side_drift_guard_walkforward = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(side_drift_guard_walkforward)


class SideDriftGuardWalkforwardTests(unittest.TestCase):
    def test_select_prior_guard_rules_uses_prediction_bias_and_trade_loss(self):
        predictions = pd.DataFrame(
            {
                "dataset_month": ["2025-01"] * 5 + ["2025-02"] * 5,
                "combined_regime": ["range_low_vol"] * 10,
                "session_regime": ["london"] * 10,
                "pred_ev_side": [-1, -1, -1, -1, 1, -1, -1, -1, 1, 1],
                "actual_label_side": [1, 1, 1, -1, 1, 1, 1, -1, 1, -1],
            }
        )
        trades = pd.DataFrame(
            {
                "month": ["2025-01", "2025-01", "2025-02", "2025-02"],
                "combined_regime": ["range_low_vol"] * 4,
                "session_regime": ["london"] * 4,
                "direction_side": [-1, -1, -1, -1],
                "adjusted_pnl": [-5.0, -3.0, -2.0, 1.0],
                "direction_error": [1.0, 1.0, 1.0, 0.0],
            }
        )

        selected = side_drift_guard_walkforward.select_prior_guard_rules(
            predictions,
            trades,
            context_columns=["combined_regime", "session_regime"],
            sides=["short"],
            min_prediction_rows=5,
            min_prediction_months=2,
            min_side_bias=0.10,
            min_selected_trades=3,
            min_selected_months=2,
            max_selected_pnl=0.0,
        )

        self.assertEqual(len(selected), 1)
        self.assertEqual(selected.loc[0, "side"], "short")
        self.assertEqual(selected.loc[0, "combined_regime"], "range_low_vol")
        self.assertEqual(selected.loc[0, "session_regime"], "london")
        self.assertGreater(selected.loc[0, "side_share_bias"], 0.10)
        self.assertLess(selected.loc[0, "selected_adjusted_pnl"], 0.0)

    def test_select_prior_guard_rules_rejects_profitable_selected_context(self):
        predictions = pd.DataFrame(
            {
                "dataset_month": ["2025-01", "2025-01", "2025-02", "2025-02"],
                "combined_regime": ["range_low_vol"] * 4,
                "session_regime": ["london"] * 4,
                "pred_ev_side": [-1, -1, -1, -1],
                "actual_label_side": [1, 1, 1, 1],
            }
        )
        trades = pd.DataFrame(
            {
                "month": ["2025-01", "2025-02"],
                "combined_regime": ["range_low_vol", "range_low_vol"],
                "session_regime": ["london", "london"],
                "direction_side": [-1, -1],
                "adjusted_pnl": [5.0, 3.0],
                "direction_error": [1.0, 1.0],
            }
        )

        selected = side_drift_guard_walkforward.select_prior_guard_rules(
            predictions,
            trades,
            context_columns=["combined_regime", "session_regime"],
            sides=["short"],
            min_prediction_rows=4,
            min_prediction_months=2,
            min_side_bias=0.10,
            min_selected_trades=2,
            min_selected_months=2,
            max_selected_pnl=0.0,
        )

        self.assertTrue(selected.empty)

    def test_context_rule_formats_side_ev_penalty_rule(self):
        rule = pd.Series(
            {
                "side": "short",
                "combined_regime": "range_low_vol",
                "session_regime": "london",
            }
        )

        text = side_drift_guard_walkforward.context_rule(
            rule,
            ["combined_regime", "session_regime"],
            7.5,
        )

        self.assertEqual(text, "short:combined_regime=range_low_vol+session_regime=london:7.5")

    def test_aggregate_policy_summary_keeps_rule_count(self):
        metrics = pd.DataFrame(
            {
                "cost_case": ["stress", "stress"],
                "variant": ["guard", "guard"],
                "penalty": [5.0, 5.0],
                "month": ["2025-01", "2025-02"],
                "trade_count": [2, 3],
                "total_adjusted_pnl": [1.0, -2.0],
                "max_drawdown": [3.0, 4.0],
                "win_rate": [0.5, 0.2],
                "forced_exit_count": [0, 1],
                "guard_rule_count": [1, 2],
            }
        )

        summary = side_drift_guard_walkforward.aggregate_policy_summary(metrics)

        self.assertEqual(len(summary), 1)
        self.assertEqual(int(summary.loc[0, "months"]), 2)
        self.assertEqual(int(summary.loc[0, "trades"]), 5)
        self.assertAlmostEqual(summary.loc[0, "total_pnl"], -1.0)
        self.assertEqual(int(summary.loc[0, "total_rule_count"]), 3)


if __name__ == "__main__":
    unittest.main()
