from __future__ import annotations

import unittest

import pandas as pd

from scripts.experiments.entry_ev_stateful_floor_meta_selector import (
    select_policy,
    summarize_candidates,
    summarize_role_rows,
)


def monthly_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "source": ["stable", "stable", "fragile", "fragile"],
            "variant": ["v", "v", "v", "v"],
            "candidate": ["c", "c", "c", "c"],
            "role": ["r1", "r2", "r1", "r2"],
            "month": ["2026-01", "2026-01", "2026-01", "2026-01"],
            "total_adjusted_pnl": [4.0, 3.0, 30.0, -10.0],
            "trade_count": [4.0, 4.0, 4.0, 4.0],
            "max_drawdown": [1.0, 1.0, 5.0, 10.0],
            "long_trade_count": [2.0, 2.0, 4.0, 4.0],
            "short_trade_count": [2.0, 2.0, 0.0, 0.0],
            "max_side_trade_share": [0.5, 0.5, 1.0, 1.0],
        }
    )


class EntryEvStatefulFloorMetaSelectorTest(unittest.TestCase):
    def test_summarize_role_rows_groups_role_totals(self) -> None:
        summary = summarize_role_rows(monthly_frame())
        stable = summary[summary["source"].eq("stable")]

        self.assertEqual(stable["role_total_pnl"].tolist(), [4.0, 3.0])
        self.assertEqual(stable["role_trade_count"].tolist(), [4, 4])

    def test_summarize_candidates_prefers_floor_stable_over_high_total_fragile(self) -> None:
        summary = summarize_candidates(
            monthly_frame(),
            min_total_pnl=0.0,
            min_role_total_pnl=0.0,
            min_month_pnl=0.0,
            min_role_trades=4,
            min_month_trades=1,
            max_side_trade_share=0.95,
            role_floor_penalty=25.0,
            month_floor_penalty=15.0,
            drawdown_penalty=0.0,
            trade_support_penalty=5.0,
        )

        self.assertEqual(summary.loc[0, "source"], "stable")
        self.assertTrue(bool(summary.loc[0, "selector_pass"]))
        fragile = summary[summary["source"].eq("fragile")].iloc[0]
        self.assertFalse(bool(fragile["selector_pass"]))
        self.assertIn("role_total_pnl_below_floor", fragile["blockers"])
        self.assertIn("month_pnl_below_floor", fragile["blockers"])
        self.assertIn("side_share_high", fragile["blockers"])

    def test_select_policy_returns_notrade_with_diagnostic_best_when_no_pass(self) -> None:
        summary = summarize_candidates(
            monthly_frame()[monthly_frame()["source"].eq("fragile")],
            min_total_pnl=0.0,
            min_role_total_pnl=0.0,
            min_month_pnl=0.0,
            min_role_trades=4,
            min_month_trades=1,
            max_side_trade_share=0.95,
            role_floor_penalty=25.0,
            month_floor_penalty=15.0,
            drawdown_penalty=0.0,
            trade_support_penalty=5.0,
        )

        selected = select_policy(summary)

        self.assertEqual(selected["selected"], "NoTrade")
        self.assertEqual(selected["diagnostic_best_source"], "fragile")
        self.assertEqual(selected["reason"], "no_candidate_passed_stateful_floor_gates")


if __name__ == "__main__":
    unittest.main()
