import importlib.util
import sys
import unittest
from pathlib import Path

import pandas as pd


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "experiments"
    / "entry_ev_selected_trade_prior_residual_pressure.py"
)
SPEC = importlib.util.spec_from_file_location(
    "entry_ev_selected_trade_prior_residual_pressure",
    SCRIPT_PATH,
)
entry_ev_selected_trade_prior_residual_pressure = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = entry_ev_selected_trade_prior_residual_pressure
SPEC.loader.exec_module(entry_ev_selected_trade_prior_residual_pressure)


class EntryEvSelectedTradePriorResidualPressureTests(unittest.TestCase):
    def scored_frame(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "supervised_target_mode": ["pnl", "pnl", "pnl", "pnl"],
                "month": ["2024-01", "2024-01", "2024-02", "2024-03"],
                "role": ["cal", "cal", "cal", "cal"],
                "direction": ["short", "short", "short", "long"],
                "combined_regime": ["range", "range", "range", "range"],
                "session_regime": ["ny_late", "ny_late", "ny_late", "ny_late"],
                "adjusted_pnl": [-3.0, 1.0, -2.0, 4.0],
                "score": [1.0, 0.0, 1.0, 2.0],
                "score_error": [4.0, -1.0, 3.0, -2.0],
                "abs_error": [4.0, 1.0, 3.0, 2.0],
                "is_loss": [True, False, True, False],
                "is_large_loss": [True, False, True, False],
                "is_overestimate": [True, False, True, False],
                "overestimate_amount": [4.0, 0.0, 3.0, 0.0],
            }
        )

    def test_prior_stats_exclude_current_month(self):
        rows = entry_ev_selected_trade_prior_residual_pressure.add_prior_stats_for_group_spec(
            self.scored_frame(),
            group_columns=["direction", "session_regime"],
            large_loss_threshold=-2.0,
        )

        jan = rows[rows["month"].eq("2024-01")]
        feb = rows[rows["month"].eq("2024-02")].iloc[0]
        mar = rows[rows["month"].eq("2024-03")].iloc[0]

        self.assertTrue((jan["prior_trade_count"] == 0).all())
        self.assertEqual(feb["prior_trade_count"], 2)
        self.assertEqual(feb["prior_month_count"], 1)
        self.assertEqual(feb["prior_total_pnl"], -2.0)
        self.assertEqual(feb["prior_loss_count"], 1)
        self.assertAlmostEqual(feb["prior_bias_mean"], 1.5)
        self.assertEqual(mar["prior_trade_count"], 0)

    def test_rule_summary_reports_flagged_pnl(self):
        rows = entry_ev_selected_trade_prior_residual_pressure.add_prior_stats_for_group_spec(
            self.scored_frame(),
            group_columns=["direction", "session_regime"],
            large_loss_threshold=-2.0,
        )
        summary = entry_ev_selected_trade_prior_residual_pressure.summarize_rules(rows)
        rule = summary[
            summary["rule"].eq("prior_count_ge3_total_neg")
        ]
        self.assertEqual(len(rule), 1)
        self.assertEqual(rule.iloc[0]["flagged_trade_count"], 0)

        count2_mask = rows["prior_trade_count"].ge(2) & rows["prior_total_pnl"].lt(0)
        manual = entry_ev_selected_trade_prior_residual_pressure.summarize_rule_frame(
            rows,
            count2_mask,
        )
        self.assertEqual(manual["flagged_trade_count"], 1)
        self.assertEqual(manual["flagged_pnl"], -2.0)
        self.assertEqual(manual["block_delta_if_removed"], 2.0)


if __name__ == "__main__":
    unittest.main()
