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
    / "entry_ev_replacement_quality_policy_inputs.py"
)
SPEC = importlib.util.spec_from_file_location(
    "entry_ev_replacement_quality_policy_inputs",
    SCRIPT_PATH,
)
entry_ev_replacement_quality_policy_inputs = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = entry_ev_replacement_quality_policy_inputs
SPEC.loader.exec_module(entry_ev_replacement_quality_policy_inputs)


class EntryEvReplacementQualityPolicyInputsTests(unittest.TestCase):
    def test_build_policy_inputs_writes_quality_and_combo_scores(self):
        predictions = pd.DataFrame(
            {
                "dataset_month": ["2024-03", "2024-03"],
                "decision_timestamp": pd.to_datetime(
                    ["2024-03-01 00:00:00Z", "2024-03-01 00:01:00Z"],
                    utc=True,
                ),
                "combined_regime": ["range", "range"],
                "session_regime": ["asia", "asia"],
                "pred_side_prior_pressure_long_predicted_ev_overestimate_risk": [
                    0.10,
                    0.10,
                ],
                "pred_side_prior_pressure_short_predicted_ev_overestimate_risk": [
                    0.50,
                    0.50,
                ],
                "pred_side_prior_pressure_long_support_bucket": ["high", "missing"],
                "pred_side_prior_pressure_short_support_bucket": ["medium", "medium"],
                "pred_side_prior_pressure_long_pressure_bucket": ["low", "low"],
                "pred_side_prior_pressure_short_pressure_bucket": ["low", "low"],
                "pred_side_prior_pressure_s0p5_long_best_adjusted_pnl": [10.0, 10.0],
                "pred_side_prior_pressure_s0p5_short_best_adjusted_pnl": [8.0, 8.0],
                "pred_long_entry_local_rank": [0.8, 0.8],
                "pred_short_entry_local_rank": [0.7, 0.7],
                "pred_direction_inversion_long_predicted_direction_inversion_risk": [
                    0.80,
                    0.80,
                ],
                "pred_direction_inversion_short_predicted_direction_inversion_risk": [
                    0.80,
                    0.80,
                ],
                "pred_direction_inversion_long_direction_inversion_prediction_source": [
                    "bucket",
                    "global",
                ],
                "pred_direction_inversion_short_direction_inversion_prediction_source": [
                    "bucket",
                    "bucket",
                ],
            }
        )
        targets = pd.DataFrame(
            {
                "month": ["2024-01", "2024-02", "2024-01", "2024-02"],
                "direction": ["long", "long", "short", "short"],
                "combined_regime": ["range", "range", "range", "range"],
                "session_regime": ["asia", "asia", "asia", "asia"],
                "selected_risk_bucket": ["very_low", "very_low", "high", "high"],
                "selected_side_support_bucket": ["high", "high", "medium", "medium"],
                "selected_side_pressure_bucket": ["low", "low", "low", "low"],
                "replacement_positive_quality_target": [False, False, True, True],
                "replacement_adjusted_pnl": [-5.0, -2.0, 5.0, 3.0],
            }
        )

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            prediction_path = tmp_path / "pred.parquet"
            targets_path = tmp_path / "targets.csv"
            predictions.to_parquet(prediction_path, index=False)
            targets.to_csv(targets_path, index=False)
            args = argparse.Namespace(
                family_predictions=[f"toy={prediction_path}"],
                replacement_targets=targets_path,
                target="replacement_positive_quality_target",
                quality_spec="risk_pressure",
                risk_prefix="pred_side_prior_pressure",
                long_column="pred_side_prior_pressure_s0p5_long_best_adjusted_pnl",
                short_column="pred_side_prior_pressure_s0p5_short_best_adjusted_pnl",
                long_rank_column="pred_long_entry_local_rank",
                short_rank_column="pred_short_entry_local_rank",
                score_kind_prefix="replacement_quality_combo",
                penalty_strengths="0.5",
                direction_source_modes="bucket",
                quality_source_modes="bucket",
                no_prior_direction_risk=0.0,
                no_prior_replacement_quality=1.0,
                min_score_scale=0.0,
                prior_strength=0.0,
                min_group_support=1,
                quantile_scopes="month",
                output_dir=tmp_path,
                label="unit_replacement_quality_inputs",
            )

            run_dir = entry_ev_replacement_quality_policy_inputs.build_policy_inputs(args)
            enriched = pd.read_parquet(
                run_dir / "enriched_predictions" / "toy_predictions_replacement_quality.parquet"
            )
            summary = pd.read_csv(run_dir / "score_adjustment_summary.csv")

            score_kind = "replacement_quality_combo_drbucket_qbucket_s0p5"
            self.assertIn(
                "pred_replacement_quality_risk_pressure_long_predicted_replacement_quality",
                enriched.columns,
            )
            self.assertIn(f"pred_{score_kind}_long_best_adjusted_pnl", enriched.columns)
            self.assertIn(f"pred_{score_kind}_selected_score_pct_month", enriched.columns)

            first = enriched.iloc[0]
            self.assertEqual(
                first[
                    "pred_replacement_quality_risk_pressure_long_"
                    "replacement_quality_prediction_source"
                ],
                "bucket",
            )
            self.assertAlmostEqual(
                first["pred_replacement_quality_risk_pressure_long_predicted_replacement_quality"],
                0.0,
            )
            self.assertAlmostEqual(
                first[f"pred_{score_kind}_long_best_adjusted_pnl"],
                6.0,
            )
            self.assertAlmostEqual(
                first[f"pred_{score_kind}_short_best_adjusted_pnl"],
                8.0,
            )
            self.assertEqual(summary["score_kind"].iloc[0], score_kind)
            self.assertAlmostEqual(summary["long_low_quality_mean"].iloc[0], 0.5)


if __name__ == "__main__":
    unittest.main()
