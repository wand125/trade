import importlib.util
import sys
import unittest
from pathlib import Path

import pandas as pd


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "experiments"
    / "entry_ev_dense_executable_capture_model.py"
)
SPEC = importlib.util.spec_from_file_location(
    "entry_ev_dense_executable_capture_model",
    SCRIPT_PATH,
)
entry_ev_dense_executable_capture_model = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = entry_ev_dense_executable_capture_model
SPEC.loader.exec_module(entry_ev_dense_executable_capture_model)


class EntryEvDenseExecutableCaptureModelTests(unittest.TestCase):
    def prediction_frame(self):
        return pd.DataFrame(
            {
                "dataset_month": ["2024-01", "2024-02"],
                "decision_timestamp": [
                    "2024-01-10T00:00:00Z",
                    "2024-02-10T00:00:00Z",
                ],
                "combined_regime": ["range", "range"],
                "session_regime": ["asia", "asia"],
                "pred_calibrated_long_best_adjusted_pnl": [10.0, 10.0],
                "pred_calibrated_short_best_adjusted_pnl": [8.0, 8.0],
                "pred_long_entry_local_rank": [0.8, 0.9],
                "pred_short_entry_local_rank": [0.4, 0.5],
                "pred_mlp_long_exit_event_minutes": [60.0, 60.0],
                "pred_mlp_short_exit_event_minutes": [60.0, 60.0],
                "pred_long_fixed_60m_adjusted_pnl": [1.0, 1.0],
                "pred_short_fixed_60m_adjusted_pnl": [1.0, 1.0],
                "pred_long_fixed_240m_adjusted_pnl": [2.0, 2.0],
                "pred_short_fixed_240m_adjusted_pnl": [2.0, 2.0],
                "pred_long_fixed_720m_adjusted_pnl": [3.0, 3.0],
                "pred_short_fixed_720m_adjusted_pnl": [3.0, 3.0],
                "pred_best_side_prob_1": [0.6, 0.6],
                "pred_best_side_prob_-1": [0.4, 0.4],
                "long_best_adjusted_pnl": [10.0, 10.0],
                "short_best_adjusted_pnl": [8.0, 8.0],
                "long_fixed_720m_adjusted_pnl": [2.0, 9.0],
                "short_fixed_720m_adjusted_pnl": [4.0, 1.0],
            }
        )

    def test_chronological_capture_predictions_use_prior_months_only(self):
        rows = entry_ev_dense_executable_capture_model.side_rows_for_family(
            self.prediction_frame(),
            family="example",
            target_mode="fixed_720m",
            long_column="pred_calibrated_long_best_adjusted_pnl",
            short_column="pred_calibrated_short_best_adjusted_pnl",
            long_rank_column="pred_long_entry_local_rank",
            short_rank_column="pred_short_entry_local_rank",
            long_holding_column="pred_mlp_long_exit_event_minutes",
            short_holding_column="pred_mlp_short_exit_event_minutes",
            min_oracle_edge=0.0,
            min_capture_factor=0.0,
            max_capture_factor=1.0,
        )
        scored, fold_summary = (
            entry_ev_dense_executable_capture_model.chronological_capture_predictions(
                rows,
                min_train_months=1,
                min_train_rows=1,
                max_train_rows=0,
                max_iter=5,
                learning_rate=0.1,
                max_leaf_nodes=3,
                min_samples_leaf=20,
                l2_regularization=0.0,
                random_seed=1,
                default_capture_factor=1.0,
                min_capture_factor=0.0,
                max_capture_factor=1.0,
            )
        )

        january = scored[scored["month"].eq("2024-01")]
        february = scored[scored["month"].eq("2024-02")]

        self.assertTrue((january["pred_dense_capture_factor"] == 1.0).all())
        # February must use only January targets: long 2/10 and short 4/8 => mean 0.35.
        self.assertTrue(
            (february["pred_dense_capture_factor"].round(6) == 0.35).all()
        )
        february_summary = fold_summary[fold_summary["target_month"].eq("2024-02")].iloc[0]
        self.assertEqual(february_summary["train_months"], 1)
        self.assertEqual(february_summary["train_rows"], 2)

    def test_attach_predictions_writes_dense_columns_and_quantiles(self):
        frame = self.prediction_frame()
        rows = entry_ev_dense_executable_capture_model.side_rows_for_family(
            frame,
            family="example",
            target_mode="fixed_720m",
            long_column="pred_calibrated_long_best_adjusted_pnl",
            short_column="pred_calibrated_short_best_adjusted_pnl",
            long_rank_column="pred_long_entry_local_rank",
            short_rank_column="pred_short_entry_local_rank",
            long_holding_column="pred_mlp_long_exit_event_minutes",
            short_holding_column="pred_mlp_short_exit_event_minutes",
            min_oracle_edge=0.0,
            min_capture_factor=0.0,
            max_capture_factor=1.0,
        )
        rows["pred_dense_capture_factor"] = [0.2, 0.9, 0.5, 0.125]
        rows["pred_dense_capture_model_used"] = True
        rows["pred_dense_capture_train_rows"] = 10
        rows["pred_dense_capture_train_months"] = 2

        outputs = entry_ev_dense_executable_capture_model.attach_predictions_to_families(
            {"example": frame},
            rows,
            long_column="pred_calibrated_long_best_adjusted_pnl",
            short_column="pred_calibrated_short_best_adjusted_pnl",
            long_output_column="dense_long",
            short_output_column="dense_short",
            score_kind="dense_executable",
            long_rank_column="pred_long_entry_local_rank",
            short_rank_column="pred_short_entry_local_rank",
            quantile_scopes=["month"],
        )
        enriched = outputs["example"]

        self.assertIn("dense_long", enriched.columns)
        self.assertIn("dense_short", enriched.columns)
        self.assertIn("pred_dense_executable_selected_score_pct_month", enriched.columns)
        self.assertEqual(enriched["dense_long"].round(6).tolist(), [2.0, 9.0])
        self.assertEqual(enriched["dense_short"].round(6).tolist(), [4.0, 1.0])


if __name__ == "__main__":
    unittest.main()
