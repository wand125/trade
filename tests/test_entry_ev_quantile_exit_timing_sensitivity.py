from __future__ import annotations

import math
import unittest

import pandas as pd

from scripts.experiments.entry_ev_quantile_exit_timing_sensitivity import (
    parse_exit_timing_variant,
    parse_exit_timing_variants,
    summarize_candidates,
)


class EntryEvQuantileExitTimingSensitivityTest(unittest.TestCase):
    def test_parse_exit_timing_variant(self) -> None:
        variant = parse_exit_timing_variant("loss_exit75:0:0.25:inf:0.75")

        self.assertEqual(variant.label, "loss_exit75")
        self.assertEqual(variant.time_exit_holding_shrink, 0.0)
        self.assertEqual(variant.loss_first_holding_shrink, 0.25)
        self.assertTrue(math.isinf(variant.time_exit_exit_threshold))
        self.assertEqual(variant.loss_first_exit_threshold, 0.75)
        self.assertEqual(variant.dynamic_exit_min_holding_minutes, 0.0)
        self.assertEqual(variant.dynamic_exit_cooldown_minutes, 0.0)

    def test_parse_exit_timing_variant_with_dynamic_exit_guards(self) -> None:
        variant = parse_exit_timing_variant("loss_exit30_cd15:0:0:inf:0.30:5:15")

        self.assertEqual(variant.label, "loss_exit30_cd15")
        self.assertEqual(variant.loss_first_exit_threshold, 0.30)
        self.assertEqual(variant.dynamic_exit_min_holding_minutes, 5.0)
        self.assertEqual(variant.dynamic_exit_cooldown_minutes, 15.0)

    def test_parse_exit_timing_variants_rejects_duplicate_labels(self) -> None:
        with self.assertRaises(Exception):
            parse_exit_timing_variants("base:0:0:inf:inf,base:0.25:0:inf:inf")

    def test_parse_exit_timing_variant_rejects_negative_guard(self) -> None:
        with self.assertRaises(Exception):
            parse_exit_timing_variant("bad:0:0:inf:0.30:-1:0")

    def test_summarize_candidates_requires_positive_roles_and_trade_support(self) -> None:
        monthly = pd.DataFrame(
            {
                "variant": ["base", "base", "base", "base"],
                "role": ["a", "a", "b", "b"],
                "candidate": ["q99", "q99", "q99", "q99"],
                "month": ["2025-01", "2025-02", "2025-01", "2025-02"],
                "total_adjusted_pnl": [4.0, 4.0, 2.0, -1.0],
                "trade_count": [2, 2, 2, 2],
                "max_drawdown": [0.0, 0.0, 1.0, 1.0],
                "long_trade_count": [2, 2, 1, 1],
                "short_trade_count": [0, 0, 1, 1],
                "signal_long_count": [2, 2, 1, 1],
                "signal_short_count": [0, 0, 1, 1],
            }
        )

        summary = summarize_candidates(
            monthly,
            min_role_trades=4,
            min_month_trades=2,
            max_side_trade_share=0.95,
        )

        self.assertFalse(bool(summary.loc[0, "selector_pass"]))
        self.assertIn("month_pnl_below_floor", summary.loc[0, "blockers"])
        self.assertIn("side_share_high", summary.loc[0, "blockers"])


if __name__ == "__main__":
    unittest.main()
