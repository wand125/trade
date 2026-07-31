import importlib.util
import sys
import unittest
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "experiments" / "short_replacement_risk_target_diagnostics.py"
SPEC = importlib.util.spec_from_file_location(
    "short_replacement_risk_target_diagnostics",
    SCRIPT,
)
short_replacement_risk_target_diagnostics = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = short_replacement_risk_target_diagnostics
SPEC.loader.exec_module(short_replacement_risk_target_diagnostics)

MonthWindow = short_replacement_risk_target_diagnostics.MonthWindow


class ShortReplacementRiskTargetDiagnosticsTest(unittest.TestCase):
    def _rows(self):
        return pd.DataFrame(
            [
                {
                    "candidate": "gap5",
                    "month": "2025-09",
                    "direction": "short",
                    "delta_status": "only_candidate",
                    "candidate_adjusted_pnl": -12.0,
                    "combined_regime": "range_low_vol",
                    "session_regime": "ny_overlap",
                    "pred_taken_ev": 18.0,
                    "pred_side_confidence_gap": 0.10,
                    "pred_taken_entry_local_rank": 0.54,
                    "pred_taken_wait_regret": 3.0,
                    "pred_taken_max_adverse_pnl": -16.0,
                    "pred_taken_profit_barrier_hit": 0.0,
                },
                {
                    "candidate": "gap5",
                    "month": "2025-09",
                    "direction": "short",
                    "delta_status": "only_candidate",
                    "candidate_adjusted_pnl": 5.0,
                    "combined_regime": "range_low_vol",
                    "session_regime": "asia",
                    "pred_taken_ev": 21.0,
                    "pred_side_confidence_gap": -0.02,
                    "pred_taken_entry_local_rank": 0.51,
                    "pred_taken_wait_regret": 5.0,
                    "pred_taken_max_adverse_pnl": -10.0,
                    "pred_taken_profit_barrier_hit": 1.0,
                },
                {
                    "candidate": "gap5",
                    "month": "2025-09",
                    "direction": "long",
                    "delta_status": "only_candidate",
                    "candidate_adjusted_pnl": -99.0,
                },
                {
                    "candidate": "gap5",
                    "month": "2025-09",
                    "direction": "short",
                    "delta_status": "common",
                    "candidate_adjusted_pnl": -88.0,
                },
            ]
        )

    def test_replacement_examples_add_targets_and_filter_rows(self):
        rows = short_replacement_risk_target_diagnostics.replacement_examples(
            self._rows(),
            window=MonthWindow("late", "2025-09", "2025-09"),
            direction="short",
            delta_status="only_candidate",
            large_loss_threshold=10.0,
        )

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows["replacement_pnl"].sum(), -7.0)
        self.assertEqual(rows["replacement_is_loss"].tolist(), [True, False])
        self.assertEqual(rows["replacement_large_loss"].tolist(), [True, False])
        self.assertEqual(rows["replacement_ev_overestimate_vs_pnl"].tolist(), [30.0, 16.0])

    def test_condition_summary_reports_block_delta_and_loss_coverage(self):
        rows = short_replacement_risk_target_diagnostics.replacement_examples(
            self._rows(),
            window=MonthWindow("late", "2025-09", "2025-09"),
            direction="short",
            delta_status="only_candidate",
            large_loss_threshold=10.0,
        )
        summary = short_replacement_risk_target_diagnostics.condition_summary(rows)
        rank = summary[summary["condition"].eq("entry_rank_ge0p53")].iloc[0]
        side_gap = summary[summary["condition"].eq("side_gap_le0")].iloc[0]

        self.assertEqual(int(rank["covered_rows"]), 1)
        self.assertEqual(float(rank["covered_pnl"]), -12.0)
        self.assertEqual(float(rank["delta_if_block_covered"]), 12.0)
        self.assertEqual(float(rank["loss_pnl_coverage"]), 1.0)

        self.assertEqual(int(side_gap["covered_rows"]), 1)
        self.assertEqual(float(side_gap["covered_pnl"]), 5.0)
        self.assertEqual(float(side_gap["delta_if_block_covered"]), -5.0)


if __name__ == "__main__":
    unittest.main()
