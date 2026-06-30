import importlib.util
import sys
import unittest
from pathlib import Path

import pandas as pd


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "experiments"
    / "entry_ev_quantile_policy_selection.py"
)
SPEC = importlib.util.spec_from_file_location(
    "entry_ev_quantile_policy_selection",
    SCRIPT_PATH,
)
entry_ev_quantile_policy_selection = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = entry_ev_quantile_policy_selection
SPEC.loader.exec_module(entry_ev_quantile_policy_selection)


class EntryEvQuantilePolicySelectionTests(unittest.TestCase):
    def monthly_frame(self):
        return pd.DataFrame(
            {
                "role": [
                    "valid_a",
                    "valid_b",
                    "valid_a",
                    "valid_b",
                    "fixed",
                    "fixed",
                ],
                "month": [
                    "2024-01",
                    "2025-01",
                    "2024-01",
                    "2025-01",
                    "2024-05",
                    "2024-05",
                ],
                "candidate": ["good", "good", "bad", "bad", "good", "bad"],
                "scope": ["month", "month", "month", "month", "month", "month"],
                "score_quantile": [0.99, 0.99, 0.95, 0.95, 0.99, 0.95],
                "side_gap_quantile": [0.95, 0.95, 0.95, 0.95, 0.95, 0.95],
                "rank_quantile": [0.90, 0.90, 0.90, 0.90, 0.90, 0.90],
                "entry_threshold": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                "short_entry_threshold_offset": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                "side_margin": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                "min_entry_rank": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                "total_adjusted_pnl": [12.0, 7.0, 20.0, -1.0, -50.0, 100.0],
                "trade_count": [12, 11, 12, 11, 8, 9],
                "max_drawdown": [4.0, 5.0, 3.0, 6.0, 20.0, 7.0],
                "long_trade_count": [6, 5, 11, 10, 4, 4],
                "short_trade_count": [6, 6, 1, 1, 4, 5],
            }
        )

    def test_summarize_candidates_keeps_fixed_diagnostic_separate(self):
        summary = entry_ev_quantile_policy_selection.summarize_candidates(
            self.monthly_frame(),
            validation_roles=["valid_a", "valid_b"],
            fixed_diagnostic_roles=["fixed"],
        )
        good = summary[summary["candidate"] == "good"].iloc[0]

        self.assertEqual(int(good["validation_role_count"]), 2)
        self.assertEqual(float(good["validation_total_pnl"]), 19.0)
        self.assertEqual(float(good["fixed_total_pnl"]), -50.0)

    def test_selector_ignores_bad_fixed_diagnostic_for_validation_choice(self):
        summary = entry_ev_quantile_policy_selection.summarize_candidates(
            self.monthly_frame(),
            validation_roles=["valid_a", "valid_b"],
            fixed_diagnostic_roles=["fixed"],
        )
        gated = entry_ev_quantile_policy_selection.apply_selector_gates(
            summary,
            min_validation_roles=2,
            min_positive_roles=2,
            min_active_roles=2,
            min_total_pnl=0.0,
            min_role_total_pnl=0.0,
            min_month_pnl=0.0,
            min_role_trades=10,
            min_month_trades=1,
            max_drawdown=float("inf"),
            max_side_trade_share=0.95,
        )
        selected = entry_ev_quantile_policy_selection.select_policy(gated)

        self.assertEqual(selected["selected"], "policy")
        self.assertEqual(selected["candidate"], "good")

    def test_selector_returns_no_trade_when_role_worst_fails(self):
        summary = entry_ev_quantile_policy_selection.summarize_candidates(
            self.monthly_frame(),
            validation_roles=["valid_a", "valid_b"],
            fixed_diagnostic_roles=["fixed"],
        )
        gated = entry_ev_quantile_policy_selection.apply_selector_gates(
            summary,
            min_validation_roles=2,
            min_positive_roles=2,
            min_active_roles=2,
            min_total_pnl=0.0,
            min_role_total_pnl=30.0,
            min_month_pnl=0.0,
            min_role_trades=10,
            min_month_trades=1,
            max_drawdown=float("inf"),
            max_side_trade_share=0.95,
        )
        selected = entry_ev_quantile_policy_selection.select_policy(gated)

        self.assertEqual(selected["selected"], "no_trade")
        self.assertTrue((gated["blockers"].str.contains("role_total_pnl_below_floor")).any())

    def test_selector_blocks_side_concentration(self):
        summary = entry_ev_quantile_policy_selection.summarize_candidates(
            self.monthly_frame(),
            validation_roles=["valid_a", "valid_b"],
            fixed_diagnostic_roles=["fixed"],
        )
        bad = summary[summary["candidate"] == "bad"].iloc[0]
        blockers = entry_ev_quantile_policy_selection.candidate_blockers(
            bad,
            min_validation_roles=2,
            min_positive_roles=1,
            min_active_roles=2,
            min_total_pnl=0.0,
            min_role_total_pnl=-10.0,
            min_month_pnl=-10.0,
            min_role_trades=10,
            min_month_trades=1,
            max_drawdown=float("inf"),
            max_side_trade_share=0.80,
        )

        self.assertIn("side_share_high", blockers)

    def test_build_blocker_summary_counts_each_blocker(self):
        gated = pd.DataFrame(
            {
                "blockers": [
                    "role_trades_low;side_share_high",
                    "side_share_high",
                    "",
                ]
            }
        )

        summary = entry_ev_quantile_policy_selection.build_blocker_summary(gated)

        counts = dict(zip(summary["blocker"], summary["candidate_count"]))
        self.assertEqual(counts["side_share_high"], 2)
        self.assertEqual(counts["role_trades_low"], 1)


if __name__ == "__main__":
    unittest.main()
