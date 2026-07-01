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
    / "entry_ev_direction_inversion_policy_inputs.py"
)
SPEC = importlib.util.spec_from_file_location(
    "entry_ev_direction_inversion_policy_inputs",
    SCRIPT_PATH,
)
entry_ev_direction_inversion_policy_inputs = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = entry_ev_direction_inversion_policy_inputs
SPEC.loader.exec_module(entry_ev_direction_inversion_policy_inputs)


class EntryEvDirectionInversionPolicyInputsTests(unittest.TestCase):
    def test_build_policy_inputs_writes_bucket_only_direction_risk(self):
        predictions = pd.DataFrame(
            {
                "dataset_month": ["2024-01", "2024-02", "2024-03", "2024-03"],
                "decision_timestamp": pd.to_datetime(
                    [
                        "2024-01-01 00:00:00Z",
                        "2024-02-01 00:00:00Z",
                        "2024-03-01 00:00:00Z",
                        "2024-03-01 00:01:00Z",
                    ],
                    utc=True,
                ),
                "combined_regime": ["range", "range", "range", "trend"],
                "session_regime": ["asia", "asia", "asia", "london"],
                "pred_side_prior_pressure_long_predicted_ev_overestimate_risk": [
                    0.10,
                    0.10,
                    0.10,
                    0.70,
                ],
                "pred_side_prior_pressure_short_predicted_ev_overestimate_risk": [
                    0.50,
                    0.50,
                    0.50,
                    0.10,
                ],
                "pred_side_prior_pressure_long_support_bucket": [
                    "high",
                    "high",
                    "high",
                    "missing",
                ],
                "pred_side_prior_pressure_short_support_bucket": [
                    "medium",
                    "medium",
                    "medium",
                    "high",
                ],
                "pred_side_prior_pressure_long_pressure_bucket": [
                    "low",
                    "low",
                    "low",
                    "high",
                ],
                "pred_side_prior_pressure_short_pressure_bucket": [
                    "low",
                    "low",
                    "low",
                    "low",
                ],
                "pred_side_prior_pressure_s0p5_long_best_adjusted_pnl": [
                    10.0,
                    10.0,
                    10.0,
                    10.0,
                ],
                "pred_side_prior_pressure_s0p5_short_best_adjusted_pnl": [
                    8.0,
                    8.0,
                    8.0,
                    8.0,
                ],
                "pred_long_entry_local_rank": [0.8, 0.8, 0.8, 0.8],
                "pred_short_entry_local_rank": [0.7, 0.7, 0.7, 0.7],
            }
        )
        targets = pd.DataFrame(
            {
                "month": ["2024-01", "2024-01", "2024-02"],
                "direction": ["long", "long", "short"],
                "selected_risk_bucket": ["very_low", "very_low", "high"],
                "selected_side_support_bucket": ["high", "high", "medium"],
                "selected_side_pressure_bucket": ["low", "low", "low"],
                "direction_side_inversion_target": [True, False, True],
                "candidate_adjusted_pnl": [-10.0, 5.0, -8.0],
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
                common_targets=targets_path,
                target="direction_side_inversion_target",
                risk_prefix="pred_side_prior_pressure",
                long_column="pred_side_prior_pressure_s0p5_long_best_adjusted_pnl",
                short_column="pred_side_prior_pressure_s0p5_short_best_adjusted_pnl",
                long_rank_column="pred_long_entry_local_rank",
                short_rank_column="pred_short_entry_local_rank",
                score_kind_prefix="direction_inversion_bucket",
                penalty_strengths="0.5",
                no_prior_risk=0.0,
                min_score_scale=0.0,
                use_global_risk=False,
                prior_strength=1.0,
                min_group_support=1,
                quantile_scopes="month",
                output_dir=tmp_path,
                label="unit_direction_inversion_inputs",
            )

            run_dir = entry_ev_direction_inversion_policy_inputs.build_policy_inputs(args)
            enriched = pd.read_parquet(
                run_dir / "enriched_predictions" / "toy_predictions_direction_inversion.parquet"
            )
            summary = pd.read_csv(run_dir / "score_adjustment_summary.csv")

            self.assertIn(
                "pred_direction_inversion_long_predicted_direction_inversion_risk",
                enriched.columns,
            )
            self.assertIn(
                "pred_direction_inversion_bucket_s0p5_long_best_adjusted_pnl",
                enriched.columns,
            )
            self.assertIn(
                "pred_direction_inversion_bucket_s0p5_selected_score_pct_month",
                enriched.columns,
            )
            march = enriched[enriched["dataset_month"].eq("2024-03")].reset_index(drop=True)
            self.assertEqual(
                march["pred_direction_inversion_long_direction_inversion_prediction_source"].iloc[0],
                "bucket",
            )
            self.assertLess(
                march["pred_direction_inversion_bucket_s0p5_long_best_adjusted_pnl"].iloc[0],
                march["pred_side_prior_pressure_s0p5_long_best_adjusted_pnl"].iloc[0],
            )
            self.assertEqual(summary["score_kind"].iloc[0], "direction_inversion_bucket_s0p5")
            self.assertFalse(bool(summary["use_global_risk"].iloc[0]))


if __name__ == "__main__":
    unittest.main()
