import importlib.util
import sys
import unittest
from pathlib import Path

import pandas as pd


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "experiments"
    / "entry_ev_short_horizon_prior_uncertainty.py"
)
SPEC = importlib.util.spec_from_file_location(
    "entry_ev_short_horizon_prior_uncertainty",
    SCRIPT_PATH,
)
entry_ev_short_horizon_prior_uncertainty = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = entry_ev_short_horizon_prior_uncertainty
SPEC.loader.exec_module(entry_ev_short_horizon_prior_uncertainty)


class EntryEvShortHorizonPriorUncertaintyTests(unittest.TestCase):
    def trade_frame(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "source": ["unit", "unit", "unit", "unit"],
                "role": ["cal", "cal", "cal", "fresh"],
                "family": ["fam", "fam", "fam", "fresh"],
                "month": ["2024-01", "2024-01", "2024-02", "2024-03"],
                "direction": ["long", "long", "long", "short"],
                "combined_regime": ["range", "range", "range", "range"],
                "session_regime": ["ny", "ny", "ny", "ny"],
                "adjusted_pnl": [-2.0, 1.0, -3.0, 4.0],
                "selected_fixed_60m_pred_pnl": [1.0, -0.5, 2.0, 3.0],
                "selected_fixed_60m_actual_pnl": [-1.0, 0.25, -2.0, -1.0],
                "selector_variant": ["base", "base", "base", "base"],
                "entry_block_rule": ["none", "none", "none", "none"],
            }
        )

    def test_prior_stats_exclude_current_month(self):
        normalized = entry_ev_short_horizon_prior_uncertainty.normalize_trades(
            self.trade_frame(),
            horizon_minutes=60,
            entry_block_rule="none",
            selector_variant_contains=None,
        )
        targets = entry_ev_short_horizon_prior_uncertainty.add_short_horizon_targets(
            normalized
        )
        rows = entry_ev_short_horizon_prior_uncertainty.add_prior_stats_for_group_spec(
            targets,
            group_columns=["direction", "combined_regime", "session_regime"],
        )

        jan = rows[rows["month"].eq("2024-01")]
        feb = rows[rows["month"].eq("2024-02")].iloc[0]
        mar = rows[rows["month"].eq("2024-03")].iloc[0]

        self.assertTrue((jan["prior_trade_count"] == 0).all())
        self.assertEqual(feb["prior_trade_count"], 2)
        self.assertEqual(feb["prior_month_count"], 1)
        self.assertEqual(feb["prior_fixed_pred_positive_count"], 1)
        self.assertEqual(feb["prior_fixed_false_positive_count"], 1)
        self.assertAlmostEqual(feb["prior_fixed_false_positive_rate"], 1.0)
        self.assertEqual(mar["prior_trade_count"], 0)

    def test_rule_summary_reports_false_positive_precision(self):
        normalized = entry_ev_short_horizon_prior_uncertainty.normalize_trades(
            self.trade_frame(),
            horizon_minutes=60,
            entry_block_rule="none",
            selector_variant_contains=None,
        )
        targets = entry_ev_short_horizon_prior_uncertainty.add_short_horizon_targets(
            normalized
        )
        rows = entry_ev_short_horizon_prior_uncertainty.add_prior_stats_for_group_spec(
            targets,
            group_columns=["direction", "combined_regime", "session_regime"],
        )
        rows["scope"] = "all"
        summary = entry_ev_short_horizon_prior_uncertainty.summarize_rules(rows)
        rule = summary[
            summary["rule"].eq("prior_count_ge3_fp_rate_ge0p5")
        ].iloc[0]
        self.assertEqual(rule["flagged_trade_count"], 0)

        manual_mask = rows["prior_trade_count"].ge(2) & rows[
            "prior_fixed_false_positive_rate"
        ].ge(0.5)
        manual = entry_ev_short_horizon_prior_uncertainty.summarize_rule_frame(
            rows,
            manual_mask,
        )
        self.assertEqual(manual["flagged_trade_count"], 1)
        self.assertEqual(manual["flagged_false_positive_count"], 1)
        self.assertEqual(manual["false_positive_precision"], 1.0)
        self.assertEqual(manual["flagged_pnl"], -3.0)

    def test_scope_rows_split_discovery_and_holdout(self):
        normalized = entry_ev_short_horizon_prior_uncertainty.normalize_trades(
            self.trade_frame(),
            horizon_minutes=60,
            entry_block_rule="none",
            selector_variant_contains=None,
        )
        targets = entry_ev_short_horizon_prior_uncertainty.add_short_horizon_targets(
            normalized
        )
        scoped = entry_ev_short_horizon_prior_uncertainty.add_scope_rows(
            targets,
            roles=["cal"],
            families=[],
            sources=[],
        )

        counts = scoped["scope"].value_counts().to_dict()
        self.assertEqual(counts["all"], 4)
        self.assertEqual(counts["discovery"], 3)
        self.assertEqual(counts["holdout"], 1)


if __name__ == "__main__":
    unittest.main()
