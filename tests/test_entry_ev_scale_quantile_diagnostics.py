import importlib.util
import unittest
from pathlib import Path

import pandas as pd


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "experiments"
    / "entry_ev_scale_quantile_diagnostics.py"
)
SPEC = importlib.util.spec_from_file_location(
    "entry_ev_scale_quantile_diagnostics",
    SCRIPT_PATH,
)
entry_ev_scale_quantile_diagnostics = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(entry_ev_scale_quantile_diagnostics)


class EntryEvScaleQuantileDiagnosticsTests(unittest.TestCase):
    def prediction_frame(self):
        return pd.DataFrame(
            {
                "dataset_month": ["2024-01"] * 4,
                "combined_regime": ["up", "up", "down", "down"],
                "session_regime": ["asia", "asia", "ny", "ny"],
                "pred_long_best_adjusted_pnl": [10.0, 20.0, 30.0, 5.0],
                "pred_short_best_adjusted_pnl": [1.0, 2.0, 3.0, 40.0],
                "pred_calibrated_long_best_adjusted_pnl": [1.0, 2.0, 3.0, 4.0],
                "pred_calibrated_short_best_adjusted_pnl": [4.0, 3.0, 2.0, 1.0],
                "pred_long_entry_local_rank": [0.1, 0.2, 0.3, 0.4],
                "pred_short_entry_local_rank": [0.4, 0.3, 0.2, 0.1],
            }
        )

    def test_build_score_frame_selects_side_and_score_kind(self):
        frame = entry_ev_scale_quantile_diagnostics.build_score_frame(
            self.prediction_frame(),
            family="example",
            score_kind="raw",
            long_score_column="pred_long_best_adjusted_pnl",
            short_score_column="pred_short_best_adjusted_pnl",
            long_rank_column="pred_long_entry_local_rank",
            short_rank_column="pred_short_entry_local_rank",
        )

        self.assertEqual(frame["selected_side_name"].tolist(), ["long", "long", "long", "short"])
        self.assertEqual(frame["selected_score"].tolist(), [10.0, 20.0, 30.0, 40.0])
        self.assertEqual(frame["selected_rank"].tolist(), [0.1, 0.2, 0.3, 0.1])

    def test_percentile_rank_by_group_counts_scope_rows(self):
        frame = entry_ev_scale_quantile_diagnostics.build_score_frame(
            self.prediction_frame(),
            family="example",
            score_kind="raw",
            long_score_column="pred_long_best_adjusted_pnl",
            short_score_column="pred_short_best_adjusted_pnl",
            long_rank_column="pred_long_entry_local_rank",
            short_rank_column="pred_short_entry_local_rank",
        )
        scoped = entry_ev_scale_quantile_diagnostics.add_scope_quantiles(
            frame,
            scope_name="month",
        )

        self.assertEqual(scoped["selected_score_scope_count"].tolist(), [4, 4, 4, 4])
        self.assertEqual(scoped["selected_score_pct"].tolist(), [0.25, 0.5, 0.75, 1.0])

    def test_monthly_quantile_gate_summary_counts_supported_entries(self):
        frame = entry_ev_scale_quantile_diagnostics.build_score_frame(
            self.prediction_frame(),
            family="example",
            score_kind="raw",
            long_score_column="pred_long_best_adjusted_pnl",
            short_score_column="pred_short_best_adjusted_pnl",
            long_rank_column="pred_long_entry_local_rank",
            short_rank_column="pred_short_entry_local_rank",
        )

        monthly = entry_ev_scale_quantile_diagnostics.build_monthly_quantile_gate_summary(
            [frame],
            quantile_scopes=["month"],
            score_quantiles=[0.75],
            side_gap_quantiles=[0.75],
            rank_quantiles=[0.0],
            min_scope_rows=4,
        )
        family = (
            entry_ev_scale_quantile_diagnostics
            .aggregate_family_quantile_gate_summary(monthly)
        )

        self.assertEqual(int(monthly.loc[0, "quantile_enter_count"]), 2)
        self.assertEqual(int(monthly.loc[0, "quantile_long_enter_count"]), 1)
        self.assertEqual(int(monthly.loc[0, "quantile_short_enter_count"]), 1)
        self.assertEqual(int(family.loc[0, "active_months"]), 1)

    def test_side_scope_min_rows_blocks_singleton_side(self):
        frame = entry_ev_scale_quantile_diagnostics.build_score_frame(
            self.prediction_frame(),
            family="example",
            score_kind="raw",
            long_score_column="pred_long_best_adjusted_pnl",
            short_score_column="pred_short_best_adjusted_pnl",
            long_rank_column="pred_long_entry_local_rank",
            short_rank_column="pred_short_entry_local_rank",
        )

        monthly = entry_ev_scale_quantile_diagnostics.build_monthly_quantile_gate_summary(
            [frame],
            quantile_scopes=["side_month"],
            score_quantiles=[0.9],
            side_gap_quantiles=[0.0],
            rank_quantiles=[0.0],
            min_scope_rows=2,
        )

        self.assertEqual(int(monthly.loc[0, "quantile_enter_count"]), 1)
        self.assertEqual(int(monthly.loc[0, "quantile_long_enter_count"]), 1)
        self.assertEqual(int(monthly.loc[0, "quantile_short_enter_count"]), 0)

    def test_enrich_prediction_frame_writes_quantile_columns(self):
        enriched = (
            entry_ev_scale_quantile_diagnostics.enrich_prediction_frame_with_quantiles(
                self.prediction_frame(),
                family="example",
                score_kinds=["raw"],
                quantile_scopes=["month"],
                long_rank_column="pred_long_entry_local_rank",
                short_rank_column="pred_short_entry_local_rank",
            )
        )

        self.assertIn("pred_raw_selected_score_pct_month", enriched.columns)
        self.assertIn("pred_raw_side_gap_pct_month", enriched.columns)
        self.assertIn("pred_raw_selected_entry_rank_pct_month", enriched.columns)
        self.assertIn("pred_raw_quantile_scope_count_month", enriched.columns)
        self.assertEqual(
            enriched["pred_raw_selected_score_pct_month"].tolist(),
            [0.25, 0.5, 0.75, 1.0],
        )
        self.assertEqual(enriched["pred_raw_quantile_scope_count_month"].tolist(), [4, 4, 4, 4])


if __name__ == "__main__":
    unittest.main()
