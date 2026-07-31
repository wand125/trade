import importlib.util
import sys
import unittest
from pathlib import Path

import pandas as pd


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "experiments"
    / "entry_ev_quantile_hold_cap_sensitivity.py"
)
SPEC = importlib.util.spec_from_file_location(
    "entry_ev_quantile_hold_cap_sensitivity",
    SCRIPT_PATH,
)
entry_ev_quantile_hold_cap_sensitivity = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = entry_ev_quantile_hold_cap_sensitivity
SPEC.loader.exec_module(entry_ev_quantile_hold_cap_sensitivity)


class EntryEvQuantileHoldCapSensitivityTests(unittest.TestCase):
    def test_derive_context_side_block_rules_aggregates_direction_error(self):
        context_summary = pd.DataFrame(
            {
                "role": ["fresh", "fresh", "fresh"],
                "candidate": ["q95", "q99", "q95"],
                "direction": ["short", "short", "long"],
                "combined_regime": ["range_low_vol", "range_low_vol", "up_low_vol"],
                "session_regime": ["ny_overlap", "ny_overlap", "london"],
                "trade_count": [1, 3, 2],
                "total_adjusted_pnl": [-4.0, -6.0, 5.0],
                "direction_error_rate": [1.0, 2.0 / 3.0, 1.0],
                "exit_regret_sum": [10.0, 30.0, 8.0],
            }
        )

        rules, eligible = (
            entry_ev_quantile_hold_cap_sensitivity.derive_context_side_block_rules(
                context_summary,
                roles={"fresh"},
                candidates={"q95", "q99"},
                min_trade_count=4,
                min_direction_error_rate=0.75,
                max_total_pnl=0.0,
            )
        )

        self.assertEqual(
            rules,
            ["short:combined_regime=range_low_vol+session_regime=ny_overlap"],
        )
        self.assertEqual(len(eligible), 1)
        self.assertEqual(eligible.iloc[0]["trade_count"], 4)
        self.assertAlmostEqual(eligible.iloc[0]["direction_error_rate"], 0.75)

    def test_summarize_candidates_uses_notrade_first_blockers(self):
        monthly = pd.DataFrame(
            {
                "guard_mode": ["none", "none", "none", "none"],
                "max_predicted_hold_minutes": [260.0, 260.0, 480.0, 480.0],
                "role": ["a", "b", "a", "b"],
                "candidate": ["q95", "q95", "q95", "q95"],
                "month": ["2024-01", "2024-02", "2024-01", "2024-02"],
                "total_adjusted_pnl": [5.0, -1.0, 12.0, 3.0],
                "trade_count": [10, 10, 12, 11],
                "max_drawdown": [2.0, 3.0, 4.0, 5.0],
                "long_trade_count": [5, 5, 6, 5],
                "short_trade_count": [5, 5, 6, 6],
                "signal_long_count": [10, 10, 12, 11],
                "signal_short_count": [10, 10, 12, 11],
            }
        )

        summary = entry_ev_quantile_hold_cap_sensitivity.summarize_candidates(monthly)
        best = summary.iloc[0]
        worst = summary.iloc[1]

        self.assertTrue(best["selector_pass"])
        self.assertEqual(best["max_predicted_hold_minutes"], 480.0)
        self.assertFalse(worst["selector_pass"])
        self.assertIn("role_total_pnl_below_floor", worst["blockers"])

    def test_prior_inversion_uses_only_prior_months_and_deduplicates_trades(self):
        trades = pd.DataFrame(
            {
                "role": ["fresh", "fresh", "fresh", "fresh"],
                "candidate": ["q95", "q99", "q95", "q95"],
                "month": ["2024-01", "2024-01", "2024-02", "2024-03"],
                "direction": ["short", "short", "short", "short"],
                "entry_decision_timestamp": [
                    "2024-01-10T00:00:00Z",
                    "2024-01-10T00:00:00Z",
                    "2024-02-10T00:00:00Z",
                    "2024-03-10T00:00:00Z",
                ],
                "combined_regime": [
                    "range_low_vol",
                    "range_low_vol",
                    "range_low_vol",
                    "range_low_vol",
                ],
                "session_regime": ["ny_overlap", "ny_overlap", "ny_overlap", "ny_overlap"],
                "adjusted_pnl": [-5.0, -5.0, -4.0, -100.0],
                "direction_error": [True, True, True, True],
                "exit_regret": [1.0, 1.0, 2.0, 50.0],
            }
        )
        prior_frame = entry_ev_quantile_hold_cap_sensitivity.prior_trade_context_frame(
            trades,
            roles={"fresh"},
            candidates={"q95", "q99"},
        )

        self.assertEqual(len(prior_frame), 3)
        rules, eligible = (
            entry_ev_quantile_hold_cap_sensitivity.derive_prior_context_side_block_rules(
                prior_frame,
                target_month="2024-03",
                min_prior_months=2,
                recent_month_count=0,
                min_trade_count=2,
                min_direction_error_rate=1.0,
                max_total_pnl=0.0,
            )
        )

        self.assertEqual(
            rules,
            ["short:combined_regime=range_low_vol+session_regime=ny_overlap"],
        )
        self.assertEqual(eligible.iloc[0]["trade_count"], 2)
        self.assertEqual(eligible.iloc[0]["total_adjusted_pnl"], -9.0)

    def test_prior_risk_scores_contexts_before_blocking(self):
        trades = pd.DataFrame(
            {
                "role": ["fresh", "fresh", "fresh"],
                "candidate": ["q95", "q95", "q95"],
                "month": ["2024-01", "2024-02", "2024-02"],
                "direction": ["short", "short", "long"],
                "entry_decision_timestamp": [
                    "2024-01-10T00:00:00Z",
                    "2024-02-10T00:00:00Z",
                    "2024-02-11T00:00:00Z",
                ],
                "combined_regime": ["range_low_vol", "range_low_vol", "range_low_vol"],
                "session_regime": ["ny_overlap", "ny_overlap", "ny_overlap"],
                "adjusted_pnl": [-10.0, -5.0, -30.0],
                "direction_error": [True, True, True],
                "exit_regret": [1.0, 2.0, 3.0],
            }
        )
        prior_frame = entry_ev_quantile_hold_cap_sensitivity.prior_trade_context_frame(
            trades,
            roles={"fresh"},
            candidates={"q95"},
        )

        rules, eligible = (
            entry_ev_quantile_hold_cap_sensitivity.derive_prior_context_side_risk_rules(
                prior_frame,
                target_month="2024-03",
                min_prior_months=1,
                recent_month_count=0,
                min_trade_count=1,
                min_risk_score=0.98,
                max_total_pnl=0.0,
                support_scale=1.0,
                pnl_scale=10.0,
            )
        )

        self.assertEqual(
            rules,
            ["long:combined_regime=range_low_vol+session_regime=ny_overlap"],
        )
        self.assertGreaterEqual(eligible.iloc[0]["prior_context_risk_score"], 0.50)


if __name__ == "__main__":
    unittest.main()
