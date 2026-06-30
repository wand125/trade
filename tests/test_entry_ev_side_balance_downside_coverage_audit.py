import importlib.util
import sys
import unittest
from pathlib import Path

import pandas as pd


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "experiments"
    / "entry_ev_side_balance_downside_coverage_audit.py"
)
SPEC = importlib.util.spec_from_file_location(
    "entry_ev_side_balance_downside_coverage_audit",
    SCRIPT_PATH,
)
entry_ev_side_balance_downside_coverage_audit = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = entry_ev_side_balance_downside_coverage_audit
SPEC.loader.exec_module(entry_ev_side_balance_downside_coverage_audit)


def role_month(candidate, role, pnl, trades=2, prior_zero=0.0, support=0.5, pressure=0.2):
    return {
        "candidate": candidate,
        "role": role,
        "month": "2024-01",
        "trade_count": trades,
        "total_pnl": pnl,
        "max_drawdown": 0.0,
        "prior_zero_share": prior_zero,
        "prior_support_mean": support,
        "feature_pressure_score": pressure,
        "uncovered_loss_pnl": min(pnl, 0.0),
    }


class EntryEvSideBalanceDownsideCoverageAuditTests(unittest.TestCase):
    def test_summarize_coverage_marks_missing_required_role(self):
        frame = pd.DataFrame(
            [
                role_month("thin", "cal", 5.0),
                role_month("thin", "refit", 4.0),
            ]
        )
        summary, role_summary = entry_ev_side_balance_downside_coverage_audit.summarize_coverage(
            frame,
            ["cal", "fresh", "refit"],
        )

        row = summary.iloc[0]
        self.assertEqual(row["active_required_role_count"], 2)
        self.assertIn("fresh", row["missing_required_roles"])
        fresh = role_summary[role_summary["role"].eq("fresh")].iloc[0]
        self.assertFalse(bool(fresh["role_present"]))
        self.assertEqual(fresh["role_prior_zero_share"], 1.0)

    def test_coverage_gates_reject_prior_zero_and_missing_role(self):
        frame = pd.DataFrame(
            [
                role_month("thin", "cal", 5.0, prior_zero=0.0),
                role_month("thin", "refit", 4.0, prior_zero=0.0),
                role_month("covered", "cal", 3.0, prior_zero=0.0),
                role_month("covered", "fresh", 2.0, prior_zero=0.25),
                role_month("covered", "refit", 1.0, prior_zero=0.0),
                role_month("zero", "cal", 3.0, prior_zero=1.0),
                role_month("zero", "fresh", 2.0, prior_zero=1.0),
                role_month("zero", "refit", 1.0, prior_zero=1.0),
            ]
        )
        summary, _ = entry_ev_side_balance_downside_coverage_audit.summarize_coverage(
            frame,
            ["cal", "fresh", "refit"],
        )
        gated = entry_ev_side_balance_downside_coverage_audit.apply_coverage_gates(
            summary,
            required_role_count=3,
            min_active_required_roles=3,
            min_required_role_trades=1,
            min_total_pnl=0.0,
            min_required_role_total_pnl=0.0,
            min_required_month_pnl=0.0,
            max_required_role_prior_zero_share=0.75,
            min_required_role_prior_support_mean=0.0,
            max_required_role_feature_pressure_score=0.5,
        )
        selection = entry_ev_side_balance_downside_coverage_audit.select_policy(gated)

        self.assertEqual(selection["candidate"], "covered")
        thin = gated[gated["candidate"].eq("thin")].iloc[0]
        zero = gated[gated["candidate"].eq("zero")].iloc[0]
        self.assertIn("required_roles_missing", thin["blockers"])
        self.assertIn("required_role_prior_zero_high", zero["blockers"])


if __name__ == "__main__":
    unittest.main()
