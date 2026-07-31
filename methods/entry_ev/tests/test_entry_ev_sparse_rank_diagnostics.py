import importlib.util
import unittest
from pathlib import Path

import pandas as pd


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "experiments"
    / "entry_ev_sparse_rank_diagnostics.py"
)
SPEC = importlib.util.spec_from_file_location(
    "entry_ev_sparse_rank_diagnostics",
    SCRIPT_PATH,
)
entry_ev_sparse_rank_diagnostics = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(entry_ev_sparse_rank_diagnostics)


class EntryEvSparseRankDiagnosticsTests(unittest.TestCase):
    def validation_summary(self):
        return pd.DataFrame(
            {
                "policy": ["timed_ev", "timed_ev"],
                "entry_threshold": [14.0, 10.0],
                "short_entry_threshold_offset": [9.0, 9.0],
                "side_margin": [5.0, 5.0],
                "risk_penalty": [0.0, 0.0],
                "min_entry_rank": [0.6, 0.0],
                "validation_total": [-0.4, 190.0],
                "validation_worst": [-5.0, 0.7],
                "validation_worst_window": [-0.4, 17.0],
                "validation_trades": [2, 173],
                "validation_active_months": [1, 4],
                "validation_min_window_trades": [0, 4],
                "validation_max_side_trade_share": [1.0, 0.96],
                "validation_direction_session_pnl_min": [-5.0, -28.0],
                "validation_combined_regime_pnl_min": [-5.0, -54.0],
                "validation_direction_combined_regime_pnl_min": [-5.0, -62.0],
            }
        )

    def fixed_summary(self):
        return pd.DataFrame(
            {
                "policy": ["timed_ev", "timed_ev"],
                "entry_threshold": [14.0, 10.0],
                "short_entry_threshold_offset": [9.0, 9.0],
                "side_margin": [5.0, 5.0],
                "risk_penalty": [0.0, 0.0],
                "min_entry_rank": [0.6, 0.0],
                "total_pnl": [99.0, -944.0],
                "worst_pnl": [-134.0, -294.0],
                "trades": [113, 1144],
            }
        )

    def test_fixed_metrics_join_on_common_sweep_keys(self):
        merged, join_columns = (
            entry_ev_sparse_rank_diagnostics.attach_fixed_metrics(
                self.validation_summary(),
                self.fixed_summary(),
            )
        )

        self.assertIn("entry_threshold", join_columns)
        self.assertIn("fixed_total_pnl", merged.columns)
        self.assertEqual(int(merged["fixed_match_count"].sum()), 2)
        self.assertAlmostEqual(float(merged.loc[0, "fixed_total_pnl"]), 99.0)

    def test_validation_blockers_do_not_use_fixed_pnl(self):
        gates = {
            "min_positive_pnl": 0.0,
            "min_trades": 20,
            "min_active_months": 4,
            "min_worst_pnl": 0.0,
            "min_window_total": 0.0,
            "min_window_trades": 1,
            "max_side_trade_share": 0.95,
            "min_direction_session_pnl": -float("inf"),
            "min_combined_regime_pnl": -float("inf"),
            "min_direction_combined_regime_pnl": -float("inf"),
        }
        merged, _ = entry_ev_sparse_rank_diagnostics.attach_fixed_metrics(
            self.validation_summary(),
            self.fixed_summary(),
        )

        diagnostics = entry_ev_sparse_rank_diagnostics.add_validation_diagnostics(
            merged,
            gates,
        )

        fixed_positive = diagnostics[diagnostics["fixed_positive_audit"]].iloc[0]
        self.assertFalse(bool(fixed_positive["promotion_eligible_by_validation"]))
        self.assertIn(
            "validation_total_not_positive",
            fixed_positive["validation_blockers"],
        )
        self.assertIn(
            "validation_window_trades_low",
            fixed_positive["validation_blockers"],
        )

    def test_rank_summary_counts_fixed_positive_separately_from_promotion(self):
        gates = {
            "min_positive_pnl": 0.0,
            "min_trades": 20,
            "min_active_months": 4,
            "min_worst_pnl": 0.0,
            "min_window_total": 0.0,
            "min_window_trades": 1,
            "max_side_trade_share": 0.95,
            "min_direction_session_pnl": -float("inf"),
            "min_combined_regime_pnl": -float("inf"),
            "min_direction_combined_regime_pnl": -float("inf"),
        }
        merged, _ = entry_ev_sparse_rank_diagnostics.attach_fixed_metrics(
            self.validation_summary(),
            self.fixed_summary(),
        )
        diagnostics = entry_ev_sparse_rank_diagnostics.add_validation_diagnostics(
            merged,
            gates,
        )

        rank_summary = entry_ev_sparse_rank_diagnostics.build_rank_summary(diagnostics)

        rank06 = rank_summary[rank_summary["min_entry_rank"] == 0.6].iloc[0]
        self.assertEqual(int(rank06["fixed_positive_count"]), 1)
        self.assertEqual(int(rank06["promotion_eligible_count"]), 0)


if __name__ == "__main__":
    unittest.main()
