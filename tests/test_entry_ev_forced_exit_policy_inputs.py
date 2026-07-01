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
    / "entry_ev_forced_exit_policy_inputs.py"
)
SPEC = importlib.util.spec_from_file_location(
    "entry_ev_forced_exit_policy_inputs",
    SCRIPT_PATH,
)
entry_ev_forced_exit_policy_inputs = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = entry_ev_forced_exit_policy_inputs
SPEC.loader.exec_module(entry_ev_forced_exit_policy_inputs)


class EntryEvForcedExitPolicyInputsTests(unittest.TestCase):
    def test_build_policy_inputs_writes_forced_exit_risk_and_scores(self):
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
                "combined_regime": ["range", "range", "range", "down"],
                "session_regime": ["asia", "asia", "asia", "london"],
                "pred_side_prior_pressure_long_predicted_ev_overestimate_risk": [
                    0.20,
                    0.20,
                    0.20,
                    0.80,
                ],
                "pred_side_prior_pressure_short_predicted_ev_overestimate_risk": [
                    0.40,
                    0.40,
                    0.40,
                    0.10,
                ],
                "pred_direction_inversion_long_selected_risk_bucket": [
                    "very_low",
                    "very_low",
                    "very_low",
                    "high",
                ],
                "pred_direction_inversion_short_selected_risk_bucket": [
                    "medium",
                    "medium",
                    "medium",
                    "very_low",
                ],
                "pred_mlp_long_exit_event_minutes": [120.0, 120.0, 120.0, 60.0],
                "pred_mlp_short_exit_event_minutes": [60.0, 60.0, 60.0, 60.0],
                "pred_long_best_holding_minutes": [60.0, 60.0, 60.0, 60.0],
                "pred_short_best_holding_minutes": [60.0, 60.0, 60.0, 60.0],
                "pred_long_exit_event_prob_0": [0.2, 0.2, 0.2, 0.2],
                "pred_short_exit_event_prob_0": [0.1, 0.1, 0.1, 0.1],
                "pred_long_exit_event_prob_2": [0.8, 0.8, 0.8, 0.2],
                "pred_short_exit_event_prob_2": [0.1, 0.1, 0.1, 0.1],
                "pred_long_profit_barrier_hit": [0.0, 0.0, 0.0, 1.0],
                "pred_short_profit_barrier_hit": [1.0, 1.0, 1.0, 1.0],
                "pred_long_fixed_60m_adjusted_pnl": [5.0, 5.0, 5.0, 5.0],
                "pred_short_fixed_60m_adjusted_pnl": [5.0, 5.0, 5.0, 5.0],
                "pred_long_fixed_720m_adjusted_pnl": [-20.0, -20.0, -20.0, 15.0],
                "pred_short_fixed_720m_adjusted_pnl": [15.0, 15.0, 15.0, 15.0],
                "pred_direction_inversion_bucket_s0p1_long_best_adjusted_pnl": [
                    10.0,
                    10.0,
                    10.0,
                    10.0,
                ],
                "pred_direction_inversion_bucket_s0p1_short_best_adjusted_pnl": [
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
                "direction": ["long", "long", "long"],
                "loss_first_prob_bucket": ["high", "high", "high"],
                "pred_profit_barrier_bucket": ["pred_miss", "pred_miss", "pred_miss"],
                "pred_fixed_slope_bucket": [
                    "strong_decay",
                    "strong_decay",
                    "strong_decay",
                ],
                "selected_ev_overestimate_bucket": ["low", "low", "low"],
                "pred_720_bucket": ["nonpositive", "nonpositive", "nonpositive"],
                "forced_exit_loss_target": [True, False, True],
                "adjusted_pnl": [-20.0, 5.0, -25.0],
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
                exit_targets=targets_path,
                target="forced_exit_loss_target",
                risk_name="forced_exit_loss",
                risk_specs="exit_risk",
                risk_prefix="pred_side_prior_pressure",
                long_column="pred_direction_inversion_bucket_s0p1_long_best_adjusted_pnl",
                short_column="pred_direction_inversion_bucket_s0p1_short_best_adjusted_pnl",
                long_rank_column="pred_long_entry_local_rank",
                short_rank_column="pred_short_entry_local_rank",
                score_kind_prefix="forced_exit_loss",
                source_modes="bucket",
                penalty_strengths="0.5",
                no_prior_risk=0.0,
                min_score_scale=0.0,
                prior_strength=1.0,
                min_group_support=1,
                quantile_scopes="month",
                output_dir=tmp_path,
                label="unit_forced_exit_inputs",
            )

            run_dir = entry_ev_forced_exit_policy_inputs.build_policy_inputs(args)
            enriched = pd.read_parquet(
                run_dir / "enriched_predictions" / "toy_predictions_forced_exit.parquet"
            )
            summary = pd.read_csv(run_dir / "score_adjustment_summary.csv")
            calibration = pd.read_csv(run_dir / "forced_exit_target_calibration_overall.csv")

        risk_column = (
            "pred_forced_exit_loss_exit_risk_long_predicted_forced_exit_loss_risk"
        )
        score_column = (
            "pred_forced_exit_loss_exitrisk_bucket_s0p5_long_best_adjusted_pnl"
        )
        source_column = (
            "pred_forced_exit_loss_exit_risk_long_forced_exit_loss_prediction_source"
        )
        march = enriched[enriched["dataset_month"].eq("2024-03")].reset_index(drop=True)

        self.assertIn(risk_column, enriched.columns)
        self.assertIn(score_column, enriched.columns)
        self.assertIn(
            "pred_forced_exit_loss_exitrisk_bucket_s0p5_selected_score_pct_month",
            enriched.columns,
        )
        self.assertEqual(march[source_column].iloc[0], "bucket")
        self.assertAlmostEqual(march[risk_column].iloc[0], 2.0 / 3.0)
        self.assertLess(
            march[score_column].iloc[0],
            march["pred_direction_inversion_bucket_s0p1_long_best_adjusted_pnl"].iloc[0],
        )
        self.assertEqual(summary["score_kind"].iloc[0], "forced_exit_loss_exitrisk_bucket_s0p5")
        self.assertEqual(calibration["risk_spec"].iloc[0], "exit_risk")


if __name__ == "__main__":
    unittest.main()
