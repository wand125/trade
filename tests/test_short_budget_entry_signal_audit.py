import importlib.util
import sys
import unittest
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "experiments" / "short_budget_entry_signal_audit.py"
SPEC = importlib.util.spec_from_file_location(
    "short_budget_entry_signal_audit",
    SCRIPT,
)
short_budget_entry_signal_audit = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = short_budget_entry_signal_audit
SPEC.loader.exec_module(short_budget_entry_signal_audit)


class ShortBudgetEntrySignalAuditTest(unittest.TestCase):
    def _rows(self):
        return pd.DataFrame(
            [
                {
                    "candidate": "gap5",
                    "window": "late",
                    "month": "2025-09",
                    "entry_decision_timestamp": "2025-09-01 10:00:00+00:00",
                    "candidate_adjusted_pnl": -5.0,
                    "combined_regime": "range_low_vol",
                    "session_regime": "ny_overlap",
                    "pred_side_confidence_gap": 0.10,
                    "pred_taken_entry_local_rank": 0.49,
                    "ev_overestimate_vs_realized": 20.0,
                    "prior_alert_or_pred_bias": False,
                    "is_loss": True,
                },
                {
                    "candidate": "gap5",
                    "window": "late",
                    "month": "2025-09",
                    "entry_decision_timestamp": "2025-09-02 10:00:00+00:00",
                    "candidate_adjusted_pnl": -10.0,
                    "combined_regime": "range_low_vol",
                    "session_regime": "ny_overlap",
                    "pred_side_confidence_gap": -0.01,
                    "pred_taken_entry_local_rank": 0.51,
                    "ev_overestimate_vs_realized": 35.0,
                    "prior_alert_or_pred_bias": False,
                    "is_loss": True,
                },
                {
                    "candidate": "gap5",
                    "window": "late",
                    "month": "2025-10",
                    "entry_decision_timestamp": "2025-10-01 10:00:00+00:00",
                    "candidate_adjusted_pnl": 3.0,
                    "combined_regime": "range_low_vol",
                    "session_regime": "ny_overlap",
                    "pred_side_confidence_gap": 0.02,
                    "pred_taken_entry_local_rank": 0.53,
                    "ev_overestimate_vs_realized": -2.0,
                    "prior_alert_or_pred_bias": True,
                    "is_loss": False,
                },
            ]
        )

    def test_current_month_context_state_is_prior_only(self):
        state = short_budget_entry_signal_audit.add_current_month_state(
            self._rows(),
            context_columns=["combined_regime", "session_regime"],
        )

        first = state[state["month"].eq("2025-09")].iloc[0]
        second = state[state["month"].eq("2025-09")].iloc[1]
        october = state[state["month"].eq("2025-10")].iloc[0]

        self.assertEqual(int(first["prior_context_trade_count"]), 0)
        self.assertEqual(float(first["prior_context_pnl"]), 0.0)
        self.assertEqual(int(first["prior_context_loss_count"]), 0)
        self.assertEqual(int(second["prior_context_trade_count"]), 1)
        self.assertEqual(float(second["prior_context_pnl"]), -5.0)
        self.assertEqual(int(second["prior_context_loss_count"]), 1)
        self.assertEqual(int(october["prior_context_trade_count"]), 0)

    def test_focus_entry_condition_and_summary(self):
        state = short_budget_entry_signal_audit.add_current_month_state(
            self._rows(),
            context_columns=["combined_regime", "session_regime"],
        )
        rows = short_budget_entry_signal_audit.add_conditions(
            state,
            focus_combined_regime="range_low_vol",
            focus_session_regime="ny_overlap",
        )
        summary = short_budget_entry_signal_audit.condition_summary(rows)
        focus_signal = summary[
            summary["condition"].eq("focus_side_gap_le0_or_entry_rank_ge0p52")
        ].iloc[0]
        combined_signal = summary[
            summary["condition"].eq("prior_or_focus_entry_signal")
        ].iloc[0]

        self.assertEqual(int(focus_signal["covered_rows"]), 2)
        self.assertEqual(float(focus_signal["covered_pnl"]), -7.0)
        self.assertEqual(int(combined_signal["covered_rows"]), 2)
        self.assertEqual(float(combined_signal["covered_pnl"]), -7.0)


if __name__ == "__main__":
    unittest.main()
