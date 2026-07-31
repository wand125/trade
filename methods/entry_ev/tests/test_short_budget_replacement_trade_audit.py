import importlib.util
import sys
import unittest
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "experiments" / "short_budget_replacement_trade_audit.py"
SPEC = importlib.util.spec_from_file_location(
    "short_budget_replacement_trade_audit",
    SCRIPT,
)
short_budget_replacement_trade_audit = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = short_budget_replacement_trade_audit
SPEC.loader.exec_module(short_budget_replacement_trade_audit)

MonthWindow = short_budget_replacement_trade_audit.MonthWindow


class ShortBudgetReplacementTradeAuditTest(unittest.TestCase):
    def _rows(self):
        return pd.DataFrame(
            [
                {
                    "candidate": "gap5",
                    "month": "2025-08",
                    "direction": "short",
                    "delta_status": "only_candidate",
                    "candidate_adjusted_pnl": -10.0,
                    "is_loss": True,
                    "is_win": False,
                    "is_forced_exit": True,
                    "combined_regime": "range_low_vol",
                    "session_regime": "ny_overlap",
                    "candidate_exit_reason": "time_stop",
                    "pred_taken_ev": 6.0,
                    "ev_overestimate_vs_realized": 16.0,
                },
                {
                    "candidate": "gap5",
                    "month": "2025-09",
                    "direction": "short",
                    "delta_status": "only_candidate",
                    "candidate_adjusted_pnl": 4.0,
                    "is_loss": False,
                    "is_win": True,
                    "is_forced_exit": False,
                    "combined_regime": "up_low_vol",
                    "session_regime": "asia",
                    "candidate_exit_reason": "signal_close",
                    "pred_taken_ev": 3.0,
                    "ev_overestimate_vs_realized": -1.0,
                },
                {
                    "candidate": "gap5",
                    "month": "2025-09",
                    "direction": "long",
                    "delta_status": "only_candidate",
                    "candidate_adjusted_pnl": -99.0,
                    "is_loss": True,
                },
                {
                    "candidate": "gap5",
                    "month": "2025-09",
                    "direction": "short",
                    "delta_status": "common",
                    "candidate_adjusted_pnl": -88.0,
                    "is_loss": True,
                },
                {
                    "candidate": "gap5",
                    "month": "2025-07",
                    "direction": "short",
                    "delta_status": "only_candidate",
                    "candidate_adjusted_pnl": -77.0,
                    "is_loss": True,
                },
            ]
        )

    def test_replacement_rows_filter_to_window_short_only_candidate(self):
        rows = short_budget_replacement_trade_audit.replacement_rows(
            self._rows(),
            window=MonthWindow("late", "2025-08", "2025-09"),
            direction="short",
            delta_status="only_candidate",
        )

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows["candidate_adjusted_pnl"].sum(), -6.0)
        self.assertEqual(set(rows["window"]), {"late"})

    def test_summary_and_grouped_summary(self):
        rows = short_budget_replacement_trade_audit.replacement_rows(
            self._rows(),
            window=MonthWindow("late", "2025-08", "2025-09"),
            direction="short",
            delta_status="only_candidate",
        )

        summary = short_budget_replacement_trade_audit.summarize_rows(rows)
        self.assertEqual(int(summary.loc[0, "rows"]), 2)
        self.assertEqual(float(summary.loc[0, "total_pnl"]), -6.0)
        self.assertEqual(int(summary.loc[0, "loss_count"]), 1)
        self.assertEqual(int(summary.loc[0, "forced_exit_count"]), 1)

        by_regime = short_budget_replacement_trade_audit.grouped_summary(
            rows,
            ["combined_regime", "session_regime"],
        )
        self.assertEqual(set(by_regime["combined_regime"]), {"range_low_vol", "up_low_vol"})


if __name__ == "__main__":
    unittest.main()
