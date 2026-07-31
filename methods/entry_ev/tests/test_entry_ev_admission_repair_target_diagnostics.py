from __future__ import annotations

import unittest

import pandas as pd

from scripts.experiments.entry_ev_admission_repair_target_diagnostics import (
    build_candidate_summary,
    build_month_targets,
    build_role_targets,
    minimal_side_balanced_additions,
)


class EntryEvAdmissionRepairTargetDiagnosticsTest(unittest.TestCase):
    def test_minimal_side_balanced_additions_handles_empty_month(self) -> None:
        result = minimal_side_balanced_additions(
            long_count=0,
            short_count=0,
            min_trades=1,
            max_side_trade_share=0.95,
        )

        self.assertEqual(result["extra_long_needed"], 1)
        self.assertEqual(result["extra_short_needed"], 1)
        self.assertEqual(result["extra_trades_needed"], 2)
        self.assertEqual(result["post_max_side_trade_share"], 0.5)

    def test_minimal_side_balanced_additions_adds_minority_side(self) -> None:
        result = minimal_side_balanced_additions(
            long_count=7,
            short_count=0,
            min_trades=1,
            max_side_trade_share=0.95,
        )

        self.assertEqual(result["extra_long_needed"], 0)
        self.assertEqual(result["extra_short_needed"], 1)
        self.assertEqual(result["post_short_trade_count"], 1)
        self.assertLessEqual(result["post_max_side_trade_share"], 0.95)

    def test_candidate_summary_reports_pnl_and_support_repair_targets(self) -> None:
        monthly = pd.DataFrame(
            {
                "source": ["s", "s", "s"],
                "variant": ["v", "v", "v"],
                "candidate": ["c", "c", "c"],
                "entry_block_rule": ["none", "none", "none"],
                "role": ["r1", "r1", "r2"],
                "month": ["2026-01", "2026-02", "2026-01"],
                "total_adjusted_pnl": [-0.4, 2.0, 1.0],
                "trade_count": [1, 2, 0],
                "long_trade_count": [1, 1, 0],
                "short_trade_count": [0, 1, 0],
                "max_side_trade_share": [1.0, 0.5, 0.0],
            }
        )

        month_targets = build_month_targets(
            monthly,
            month_floor=0.0,
            min_month_trades=1,
            max_side_trade_share=0.95,
            shallow_month_floor=-1.0,
        )
        role_targets = build_role_targets(
            month_targets,
            min_role_trades=2,
            min_role_total_pnl=0.0,
        )
        summary = build_candidate_summary(
            month_targets,
            role_targets,
            min_total_pnl=0.0,
            min_role_total_pnl=0.0,
            month_floor=0.0,
            min_role_trades=2,
            min_month_trades=1,
            max_side_trade_share=0.95,
        ).iloc[0]

        self.assertAlmostEqual(summary["month_pnl_hurdle_sum"], 0.4)
        self.assertEqual(summary["monthly_support_extra_trades"], 3)
        self.assertEqual(summary["support_limited_negative_month_count"], 1)
        self.assertIn("month_pnl_below_floor", summary["standard_blockers"])
        self.assertIn("month_trades_low", summary["standard_blockers"])
        self.assertIn("side_share_high", summary["standard_blockers"])


if __name__ == "__main__":
    unittest.main()
