import argparse
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "experiments"
    / "entry_ev_forced_exit_selector_inputs.py"
)
SPEC = importlib.util.spec_from_file_location(
    "entry_ev_forced_exit_selector_inputs",
    SCRIPT_PATH,
)
entry_ev_forced_exit_selector_inputs = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = entry_ev_forced_exit_selector_inputs
SPEC.loader.exec_module(entry_ev_forced_exit_selector_inputs)


class EntryEvForcedExitSelectorInputsTests(unittest.TestCase):
    def test_build_selector_inputs_blocks_bucket_side_without_penalty(self):
        predictions = pd.DataFrame(
            {
                "dataset_month": ["2024-03", "2024-03", "2024-03"],
                "decision_timestamp": pd.to_datetime(
                    [
                        "2024-03-01 00:00:00Z",
                        "2024-03-01 00:01:00Z",
                        "2024-03-01 00:02:00Z",
                    ],
                    utc=True,
                ),
                "pred_direction_inversion_bucket_s0p1_long_best_adjusted_pnl": [
                    10.0,
                    10.0,
                    10.0,
                ],
                "pred_direction_inversion_bucket_s0p1_short_best_adjusted_pnl": [
                    8.0,
                    8.0,
                    8.0,
                ],
                "pred_long_entry_local_rank": [0.9, 0.9, 0.9],
                "pred_short_entry_local_rank": [0.8, 0.8, 0.8],
                "pred_forced_exit_loss_exit_risk_long_predicted_forced_exit_loss_risk": [
                    0.60,
                    0.70,
                    0.60,
                ],
                "pred_forced_exit_loss_exit_risk_short_predicted_forced_exit_loss_risk": [
                    0.10,
                    0.20,
                    0.80,
                ],
                "pred_forced_exit_loss_exit_risk_long_forced_exit_loss_prediction_source": [
                    "bucket",
                    "global",
                    "bucket",
                ],
                "pred_forced_exit_loss_exit_risk_short_forced_exit_loss_prediction_source": [
                    "bucket",
                    "bucket",
                    "bucket",
                ],
            }
        )

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            prediction_path = tmp_path / "pred.parquet"
            predictions.to_parquet(prediction_path, index=False)
            args = argparse.Namespace(
                family_predictions=[f"toy={prediction_path}"],
                risk_name="forced_exit_loss",
                risk_specs="exit_risk",
                score_kind_prefix="forced_exit_selector",
                source_modes="bucket",
                risk_thresholds="0.5",
                long_column="pred_direction_inversion_bucket_s0p1_long_best_adjusted_pnl",
                short_column="pred_direction_inversion_bucket_s0p1_short_best_adjusted_pnl",
                long_rank_column="pred_long_entry_local_rank",
                short_rank_column="pred_short_entry_local_rank",
                blocked_score=-999.0,
                quantile_scopes="month",
                output_dir=tmp_path,
                label="unit_forced_exit_selector",
            )

            run_dir = entry_ev_forced_exit_selector_inputs.build_selector_inputs(args)
            enriched = pd.read_parquet(
                run_dir
                / "enriched_predictions"
                / "toy_predictions_forced_exit_selector.parquet"
            )
            summary = pd.read_csv(run_dir / "selector_block_summary.csv")

        score_kind = "forced_exit_selector_exitrisk_bucket_t0p5"
        long_score = f"pred_{score_kind}_long_best_adjusted_pnl"
        short_score = f"pred_{score_kind}_short_best_adjusted_pnl"

        self.assertEqual(enriched[long_score].iloc[0], -999.0)
        self.assertEqual(enriched[short_score].iloc[0], 8.0)
        self.assertEqual(enriched[long_score].iloc[1], 10.0)
        self.assertEqual(enriched[long_score].iloc[2], -999.0)
        self.assertEqual(enriched[short_score].iloc[2], -999.0)
        self.assertIn(f"pred_{score_kind}_selected_score_pct_month", enriched.columns)
        self.assertAlmostEqual(summary["long_block_share"].iloc[0], 2.0 / 3.0)
        self.assertAlmostEqual(summary["both_side_block_share"].iloc[0], 1.0 / 3.0)
        self.assertAlmostEqual(summary["selected_side_changed_share"].iloc[0], 1.0 / 3.0)


if __name__ == "__main__":
    unittest.main()
