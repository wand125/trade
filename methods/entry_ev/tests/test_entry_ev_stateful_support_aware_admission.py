from __future__ import annotations

import unittest

import pandas as pd

from scripts.experiments.entry_ev_stateful_support_aware_admission import (
    add_floor_breach_classification,
    select_diagnostic,
    summarize_support_aware_candidates,
)


def monthly_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "source": ["candidate"] * 5,
            "variant": ["v"] * 5,
            "candidate": ["c"] * 5,
            "role": ["r1", "r1", "r2", "r2", "r3"],
            "month": ["2026-01", "2026-02", "2026-01", "2026-02", "2026-01"],
            "total_adjusted_pnl": [10.0, -0.4, -0.6, -5.0, 2.0],
            "trade_count": [10.0, 1.0, 8.0, 8.0, 5.0],
            "long_trade_count": [5.0, 1.0, 4.0, 4.0, 3.0],
            "short_trade_count": [5.0, 0.0, 4.0, 4.0, 2.0],
            "max_side_trade_share": [0.5, 1.0, 0.5, 0.5, 0.6],
            "max_drawdown": [1.0, 0.4, 0.6, 5.0, 1.0],
        }
    )


class EntryEvStatefulSupportAwareAdmissionTest(unittest.TestCase):
    def test_add_floor_breach_classification_splits_support_shallow_and_structural(self) -> None:
        classified = add_floor_breach_classification(
            monthly_frame(),
            month_floor=0.0,
            thin_month_trade_threshold=5,
            concentrated_side_share_threshold=0.95,
            shallow_month_floor=-1.0,
        )

        classes = dict(zip(classified["month"], classified["floor_breach_class"]))

        self.assertEqual(classes["2026-01"], "pass")
        self.assertEqual(classified.loc[1, "floor_breach_class"], "support_limited")
        self.assertEqual(classified.loc[2, "floor_breach_class"], "shallow")
        self.assertEqual(classified.loc[3, "floor_breach_class"], "structural")

    def test_summarize_support_aware_candidates_blocks_structural_negative_month(self) -> None:
        classified = add_floor_breach_classification(
            monthly_frame(),
            month_floor=0.0,
            thin_month_trade_threshold=5,
            concentrated_side_share_threshold=0.95,
            shallow_month_floor=-1.0,
        )

        summary = summarize_support_aware_candidates(
            classified,
            min_total_pnl=0.0,
            min_role_total_pnl=-10.0,
            month_floor=0.0,
            shallow_month_floor=-1.0,
            min_role_trades=1,
            min_month_trades=1,
            max_side_trade_share=1.0,
            allow_shallow_negative_months=1,
            allow_support_limited_negative_months=1,
        )
        row = summary.iloc[0]

        self.assertFalse(bool(row["support_aware_floor_pass"]))
        self.assertEqual(row["support_limited_negative_month_count"], 1)
        self.assertEqual(row["shallow_negative_month_count"], 1)
        self.assertEqual(row["structural_negative_month_count"], 1)
        self.assertIn("structural_negative_months", row["support_aware_blockers"])

    def test_select_diagnostic_keeps_support_aware_only_as_notrade(self) -> None:
        frame = monthly_frame().iloc[[0, 1, 2, 4]].copy()
        classified = add_floor_breach_classification(
            frame,
            month_floor=0.0,
            thin_month_trade_threshold=5,
            concentrated_side_share_threshold=0.95,
            shallow_month_floor=-1.0,
        )
        summary = summarize_support_aware_candidates(
            classified,
            min_total_pnl=0.0,
            min_role_total_pnl=-10.0,
            month_floor=0.0,
            shallow_month_floor=-1.0,
            min_role_trades=1,
            min_month_trades=1,
            max_side_trade_share=0.95,
            allow_shallow_negative_months=1,
            allow_support_limited_negative_months=1,
        )

        selected = select_diagnostic(summary)

        self.assertEqual(selected["selected"], "NoTrade")
        self.assertEqual(selected["reason"], "support_aware_diagnostic_only")
        self.assertTrue(bool(summary.iloc[0]["support_aware_floor_pass"]))
        self.assertFalse(bool(summary.iloc[0]["standard_pass"]))


if __name__ == "__main__":
    unittest.main()
