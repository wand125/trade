import importlib.util
import sys
import unittest
from pathlib import Path

import pandas as pd


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "experiments"
    / "entry_ev_side_balance_score_inputs.py"
)
SPEC = importlib.util.spec_from_file_location(
    "entry_ev_side_balance_score_inputs",
    SCRIPT_PATH,
)
entry_ev_side_balance_score_inputs = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = entry_ev_side_balance_score_inputs
SPEC.loader.exec_module(entry_ev_side_balance_score_inputs)


class EntryEvSideBalanceScoreInputsTests(unittest.TestCase):
    def prediction_frame(self):
        return pd.DataFrame(
            {
                "dataset_month": ["2024-01", "2024-01", "2024-02"],
                "decision_timestamp": [
                    "2024-01-10T00:00:00Z",
                    "2024-01-11T00:00:00Z",
                    "2024-02-10T00:00:00Z",
                ],
                "combined_regime": ["range", "range", "range"],
                "session_regime": ["asia", "asia", "asia"],
                "pred_dense_executable_long_best_adjusted_pnl": [10.0, 9.0, 10.0],
                "pred_dense_executable_short_best_adjusted_pnl": [5.0, 4.0, 8.0],
                "pred_long_entry_local_rank": [0.8, 0.7, 0.9],
                "pred_short_entry_local_rank": [0.4, 0.3, 0.5],
                "long_fixed_720m_adjusted_pnl": [1.0, 1.0, 9.0],
                "short_fixed_720m_adjusted_pnl": [3.0, 2.0, 1.0],
            }
        )

    def test_add_side_balance_scores_uses_prior_month_only(self):
        frame = self.prediction_frame()
        rows = entry_ev_side_balance_score_inputs.prediction_balance_rows(
            frame,
            family="example",
            long_column="pred_dense_executable_long_best_adjusted_pnl",
            short_column="pred_dense_executable_short_best_adjusted_pnl",
            target_mode="fixed_720m",
            min_target_edge=0.0,
        )
        outputs, global_stats, _context_stats = (
            entry_ev_side_balance_score_inputs.add_side_balance_scores(
                {"example": frame},
                rows=rows,
                target_mode="fixed_720m",
                long_column="pred_dense_executable_long_best_adjusted_pnl",
                short_column="pred_dense_executable_short_best_adjusted_pnl",
                long_output_column="balanced_long",
                short_output_column="balanced_short",
                score_kind="side_balanced_dense_executable",
                long_rank_column="pred_long_entry_local_rank",
                short_rank_column="pred_short_entry_local_rank",
                quantile_scopes=["month"],
                min_prior_months=1,
                recent_month_count=0,
                context_columns=[],
                support_scale=1.0,
                penalty_strength=0.5,
                min_side_scale=0.2,
            )
        )
        enriched = outputs["example"]
        february = enriched[enriched["dataset_month"].eq("2024-02")].iloc[0]
        january = enriched[enriched["dataset_month"].eq("2024-01")]

        self.assertTrue((january["pred_side_balance_long_scale"] == 1.0).all())
        self.assertAlmostEqual(
            global_stats.loc[global_stats["target_month"].eq("2024-02"), "prior_long_share_drift"].iloc[0],
            1.0,
        )
        self.assertAlmostEqual(february["pred_side_balance_long_scale"], 0.5)
        self.assertAlmostEqual(february["balanced_long"], 5.0)
        self.assertAlmostEqual(february["balanced_short"], 8.0)

    def test_quantile_columns_are_written(self):
        frame = self.prediction_frame()
        rows = entry_ev_side_balance_score_inputs.prediction_balance_rows(
            frame,
            family="example",
            long_column="pred_dense_executable_long_best_adjusted_pnl",
            short_column="pred_dense_executable_short_best_adjusted_pnl",
            target_mode="fixed_720m",
            min_target_edge=0.0,
        )
        outputs, _global_stats, _context_stats = (
            entry_ev_side_balance_score_inputs.add_side_balance_scores(
                {"example": frame},
                rows=rows,
                target_mode="fixed_720m",
                long_column="pred_dense_executable_long_best_adjusted_pnl",
                short_column="pred_dense_executable_short_best_adjusted_pnl",
                long_output_column="balanced_long",
                short_output_column="balanced_short",
                score_kind="side_balanced_dense_executable",
                long_rank_column="pred_long_entry_local_rank",
                short_rank_column="pred_short_entry_local_rank",
                quantile_scopes=["month"],
                min_prior_months=1,
                recent_month_count=0,
                context_columns=[],
                support_scale=1.0,
                penalty_strength=0.5,
                min_side_scale=0.2,
            )
        )
        enriched = outputs["example"]

        self.assertIn(
            "pred_side_balanced_dense_executable_selected_score_pct_month",
            enriched.columns,
        )
        self.assertIn(
            "pred_side_balanced_dense_executable_side_gap_pct_month",
            enriched.columns,
        )


if __name__ == "__main__":
    unittest.main()
