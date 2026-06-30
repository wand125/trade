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
    / "entry_ev_side_prior_pressure_policy_inputs.py"
)
SPEC = importlib.util.spec_from_file_location(
    "entry_ev_side_prior_pressure_policy_inputs",
    SCRIPT_PATH,
)
entry_ev_side_prior_pressure_policy_inputs = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = entry_ev_side_prior_pressure_policy_inputs
SPEC.loader.exec_module(entry_ev_side_prior_pressure_policy_inputs)


class EntryEvSidePriorPressurePolicyInputsTests(unittest.TestCase):
    def test_strength_label_is_column_safe(self):
        self.assertEqual(entry_ev_side_prior_pressure_policy_inputs.strength_label(1.0), "s1")
        self.assertEqual(entry_ev_side_prior_pressure_policy_inputs.strength_label(0.5), "s0p5")

    def test_build_policy_inputs_writes_enriched_prediction_parquet(self):
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
                "pred_side_balance_long_share_drift": [0.0, 0.1, 0.1, -0.1],
                "pred_side_balanced_dense_executable_long_best_adjusted_pnl": [
                    10.0,
                    12.0,
                    14.0,
                    16.0,
                ],
                "pred_side_balanced_dense_executable_short_best_adjusted_pnl": [
                    8.0,
                    9.0,
                    7.0,
                    15.0,
                ],
                "pred_long_entry_local_rank": [0.8, 0.9, 0.95, 0.7],
                "pred_short_entry_local_rank": [0.7, 0.6, 0.5, 0.9],
            }
        )
        component = pd.DataFrame(
            {
                "month": ["2024-01", "2024-02", "2024-02"],
                "direction": ["long", "long", "short"],
                "support_bucket": ["missing", "medium", "medium"],
                "pressure_bucket": ["low", "high", "high"],
                "prior_support_bucket": ["missing", "medium", "medium"],
                "feature_pressure_bucket": ["low", "high", "high"],
                "executable_ev_overestimate_target": [False, True, True],
            }
        )
        prior_trades = pd.DataFrame(
            {
                "month": ["2024-01", "2024-02", "2024-02"],
                "direction": ["long", "long", "short"],
                "combined_regime": ["range", "range", "range"],
                "session_regime": ["asia", "asia", "asia"],
                "adjusted_pnl": [2.0, -5.0, -4.0],
                "direction_error": [False, True, True],
                "no_edge_entry": [False, False, False],
                "exit_regret": [1.0, 12.0, 11.0],
            }
        )

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            prediction_path = tmp_path / "pred.parquet"
            component_path = tmp_path / "component.csv"
            prior_path = tmp_path / "prior.csv"
            predictions.to_parquet(prediction_path, index=False)
            component.to_csv(component_path, index=False)
            prior_trades.to_csv(prior_path, index=False)
            args = argparse.Namespace(
                family_predictions=[f"toy={prediction_path}"],
                component_targets=component_path,
                prior_trades=prior_path,
                target="executable_ev_overestimate_target",
                long_column="pred_side_balanced_dense_executable_long_best_adjusted_pnl",
                short_column="pred_side_balanced_dense_executable_short_best_adjusted_pnl",
                long_rank_column="pred_long_entry_local_rank",
                short_rank_column="pred_short_entry_local_rank",
                score_kind_prefix="side_prior_pressure",
                penalty_strengths="1.0",
                no_prior_risk=0.0,
                min_score_scale=0.0,
                prior_strength=1.0,
                min_group_support=1,
                min_prior_months=1,
                recent_month_count=0,
                support_scale=1.0,
                pnl_scale=10.0,
                large_exit_regret_threshold=10.0,
                risk_threshold=0.2,
                interaction_threshold=0.005,
                min_prior_support_weight=0.1,
                quantile_scopes="month",
                output_dir=tmp_path,
                label="unit_side_prior_pressure",
            )

            run_dir = entry_ev_side_prior_pressure_policy_inputs.build_policy_inputs(args)
            enriched = pd.read_parquet(
                run_dir / "enriched_predictions" / "toy_predictions_side_prior_pressure.parquet"
            )
            summary = pd.read_csv(run_dir / "score_adjustment_summary.csv")

            self.assertIn(
                "pred_side_prior_pressure_long_predicted_ev_overestimate_risk",
                enriched.columns,
            )
            self.assertIn(
                "pred_side_prior_pressure_s1_long_best_adjusted_pnl",
                enriched.columns,
            )
            self.assertIn(
                "pred_side_prior_pressure_s1_selected_score_pct_month",
                enriched.columns,
            )
            self.assertEqual(summary["score_kind"].iloc[0], "side_prior_pressure_s1")


if __name__ == "__main__":
    unittest.main()
