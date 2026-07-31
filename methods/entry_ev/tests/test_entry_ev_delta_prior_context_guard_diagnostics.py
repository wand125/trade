from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

import pandas as pd


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "experiments"
    / "entry_ev_delta_prior_context_guard_diagnostics.py"
)
SPEC = importlib.util.spec_from_file_location(
    "entry_ev_delta_prior_context_guard_diagnostics",
    SCRIPT_PATH,
)
entry_ev_delta_prior_context_guard_diagnostics = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = entry_ev_delta_prior_context_guard_diagnostics
SPEC.loader.exec_module(entry_ev_delta_prior_context_guard_diagnostics)


class EntryEvDeltaPriorContextGuardDiagnosticsTest(unittest.TestCase):
    def test_prior_stats_use_only_previous_months_in_same_context(self):
        frame = pd.DataFrame(
            {
                "candidate": ["q", "q", "q", "q"],
                "delta_status": [
                    "only_candidate",
                    "only_candidate",
                    "only_candidate",
                    "only_candidate",
                ],
                "month": ["2025-04", "2025-05", "2025-05", "2025-05"],
                "direction": ["short", "short", "short", "long"],
                "combined_regime": [
                    "down_normal_vol",
                    "down_normal_vol",
                    "down_normal_vol",
                    "down_normal_vol",
                ],
                "session_regime": ["asia", "asia", "asia", "asia"],
                "candidate_adjusted_pnl": [-70.0, 10.0, -20.0, -30.0],
            }
        )

        output = entry_ev_delta_prior_context_guard_diagnostics.add_prior_stats(
            frame,
            scope_column="direction_regime",
        )

        may_short = output[
            output["month"].eq("2025-05")
            & output["direction"].eq("short")
        ].reset_index(drop=True)
        self.assertEqual(may_short["prior_trade_count"].tolist(), [1.0, 1.0])
        self.assertEqual(may_short["prior_pnl_sum"].tolist(), [-70.0, -70.0])

        may_long = output[
            output["month"].eq("2025-05")
            & output["direction"].eq("long")
        ].iloc[0]
        self.assertEqual(may_long["prior_trade_count"], 0.0)
        self.assertEqual(may_long["prior_pnl_sum"], 0.0)

    def test_threshold_summary_estimates_blocked_pnl(self):
        rows = pd.DataFrame(
            {
                "candidate": ["q", "q", "q"],
                "delta_status": ["only_candidate", "only_candidate", "only_candidate"],
                "month": ["2025-04", "2025-05", "2025-06"],
                "candidate_adjusted_pnl": [-70.0, -20.0, 8.0],
                "prior_trade_count": [0, 1, 2],
                "prior_month_count": [0, 1, 2],
                "prior_pnl_sum": [0.0, -70.0, -90.0],
            }
        )

        summary = entry_ev_delta_prior_context_guard_diagnostics.summarize_thresholds(
            rows,
            scope_column="direction_regime",
            min_prior_counts=[1],
            min_prior_months=[1],
            loss_thresholds=[60.0],
        )

        self.assertEqual(summary["flagged_count"].iloc[0], 2)
        self.assertAlmostEqual(summary["flagged_pnl"].iloc[0], -12.0)
        self.assertAlmostEqual(summary["kept_pnl"].iloc[0], -70.0)
        self.assertAlmostEqual(summary["no_replacement_estimated_delta"].iloc[0], 12.0)


if __name__ == "__main__":
    unittest.main()
