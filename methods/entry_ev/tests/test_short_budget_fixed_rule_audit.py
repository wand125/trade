import importlib.util
import sys
import unittest
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "experiments" / "short_budget_fixed_rule_audit.py"
SPEC = importlib.util.spec_from_file_location(
    "short_budget_fixed_rule_audit",
    SCRIPT,
)
short_budget_fixed_rule_audit = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = short_budget_fixed_rule_audit
SPEC.loader.exec_module(short_budget_fixed_rule_audit)

Candidate = short_budget_fixed_rule_audit.Candidate
Rule = short_budget_fixed_rule_audit.Rule


class ShortBudgetFixedRuleAuditTest(unittest.TestCase):
    def _summary(self):
        rows = []
        for month, primary_short, defensive_short in [
            ("2025-01", 10.0, 5.0),
            ("2025-02", -4.0, 4.0),
            ("2025-03", 8.0, 3.0),
            ("2025-04", -6.0, 2.0),
        ]:
            rows.append(
                {
                    "month": month,
                    "short_gap_threshold": 5.0,
                    "context_entry_budget": 0.0,
                    "trade_count": 10,
                    "total_adjusted_pnl": primary_short,
                    "max_drawdown": 10.0,
                    "forced_exit_count": 0,
                    "short_adjusted_pnl": primary_short,
                    "long_adjusted_pnl": 0.0,
                    "active_trade_count": 0,
                    "active_trade_pnl": 0.0,
                }
            )
            rows.append(
                {
                    "month": month,
                    "short_gap_threshold": 0.0,
                    "context_entry_budget": 0.0,
                    "trade_count": 8,
                    "total_adjusted_pnl": defensive_short,
                    "max_drawdown": 5.0,
                    "forced_exit_count": 0,
                    "short_adjusted_pnl": defensive_short,
                    "long_adjusted_pnl": 0.0,
                    "active_trade_count": 0,
                    "active_trade_pnl": 0.0,
                }
            )
        return pd.DataFrame(rows)

    def test_fixed_rule_uses_only_prior_recent_months(self):
        rule = Rule(
            primary=Candidate(5.0, 0.0),
            defensive=Candidate(0.0, 0.0),
            trigger_metric="recent_short_losing_months",
            operator="ge",
            threshold=1.0,
        )
        rows = short_budget_fixed_rule_audit.fixed_rule_rows(
            self._summary(),
            rule=rule,
            min_train_months=2,
            train_window_months=0,
            recent_month_count=1,
        )
        trigger_rows = rows[rows["policy_name"].eq("trigger")].reset_index(drop=True)

        self.assertEqual(trigger_rows.loc[0, "target_month"], "2025-03")
        self.assertTrue(bool(trigger_rows.loc[0, "triggered"]))
        self.assertEqual(
            trigger_rows.loc[0, "selected_candidate"],
            "short_gap_threshold=0|context_entry_budget=0",
        )
        self.assertEqual(trigger_rows.loc[1, "target_month"], "2025-04")
        self.assertFalse(bool(trigger_rows.loc[1, "triggered"]))
        self.assertEqual(
            trigger_rows.loc[1, "selected_candidate"],
            "short_gap_threshold=5|context_entry_budget=0",
        )

    def test_summary_reports_primary_defensive_and_trigger(self):
        rule = Rule(
            primary=Candidate(5.0, 0.0),
            defensive=Candidate(0.0, 0.0),
            trigger_metric="recent_short_losing_months",
            operator="ge",
            threshold=1.0,
        )
        rows = short_budget_fixed_rule_audit.fixed_rule_rows(
            self._summary(),
            rule=rule,
            min_train_months=2,
            train_window_months=0,
            recent_month_count=1,
        )
        summary = short_budget_fixed_rule_audit.summarize(rows)
        self.assertEqual(set(summary["policy_name"]), {"primary", "defensive", "trigger"})
        trigger = summary[summary["policy_name"].eq("trigger")].iloc[0]
        self.assertEqual(int(trigger["target_months"]), 2)
        self.assertEqual(int(trigger["triggered_months"]), 1)


if __name__ == "__main__":
    unittest.main()
