from __future__ import annotations

import unittest

import pandas as pd

from scripts.experiments.entry_ev_support_negative_month_inventory_diagnostics import (
    add_negative_flags,
    summarize_configs,
    summarize_targets,
)


class EntryEvSupportNegativeMonthInventoryDiagnosticsTest(unittest.TestCase):
    def sample_targets(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "metric_parent": ["m1", "m1", "m1", "m2"],
                "metric_path": ["p1", "p1", "p1", "p2"],
                "source": ["s", "s", "s", "s"],
                "variant": ["v", "v", "v", "v2"],
                "candidate": ["c", "c", "c", "c"],
                "entry_block_rule": ["e", "e", "e", "e"],
                "role": ["r1", "r2", "r3", "r1"],
                "family": ["f1", "f2", "f3", "f1"],
                "month": ["2025-01", "2025-02", "2025-03", "2025-01"],
                "total_adjusted_pnl": [-1.0, -2.0, 3.0, -0.5],
                "support_limited_month": [False, True, False, False],
                "floor_breach_class": ["shallow", "support_limited", "pass", "shallow"],
                "month_pnl_hurdle": [1.0, 2.0, 0.0, 0.5],
                "extra_trades_needed": [0, 1, 0, 0],
                "extra_long_needed": [0, 1, 0, 0],
                "extra_short_needed": [0, 0, 0, 0],
            }
        )

    def test_add_negative_flags_separates_support_types(self) -> None:
        output = add_negative_flags(self.sample_targets(), month_floor=0.0)

        self.assertEqual(output["negative_month"].tolist(), [True, True, False, True])
        self.assertEqual(
            output["support_sufficient_negative_month"].tolist(),
            [True, False, False, True],
        )
        self.assertEqual(
            output["support_limited_negative_month"].tolist(),
            [False, True, False, False],
        )

    def test_summarize_configs_counts_negative_classes(self) -> None:
        output = add_negative_flags(self.sample_targets(), month_floor=0.0)
        summary = summarize_configs(output)

        first = summary[summary["metric_parent"].eq("m1")].iloc[0]
        self.assertEqual(int(first["negative_month_count"]), 2)
        self.assertEqual(int(first["support_sufficient_negative_count"]), 1)
        self.assertEqual(int(first["support_limited_negative_count"]), 1)
        self.assertAlmostEqual(float(first["month_pnl_hurdle_sum"]), 3.0)

    def test_summarize_targets_counts_target_identity_across_configs(self) -> None:
        output = add_negative_flags(self.sample_targets(), month_floor=0.0)
        summary = summarize_targets(output)

        target = summary[
            summary["role"].eq("r1") & summary["month"].eq("2025-01")
        ].iloc[0]
        self.assertEqual(int(target["config_count"]), 2)
        self.assertEqual(int(target["support_sufficient_config_count"]), 2)
        self.assertEqual(int(target["support_limited_config_count"]), 0)
        self.assertAlmostEqual(float(target["best_month_pnl"]), -0.5)


if __name__ == "__main__":
    unittest.main()
