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
    / "entry_ev_side_regime_tail_policy_inputs.py"
)
SPEC = importlib.util.spec_from_file_location(
    "entry_ev_side_regime_tail_policy_inputs",
    SCRIPT_PATH,
)
entry_ev_side_regime_tail_policy_inputs = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = entry_ev_side_regime_tail_policy_inputs
SPEC.loader.exec_module(entry_ev_side_regime_tail_policy_inputs)


class EntryEvSideRegimeTailPolicyInputsTests(unittest.TestCase):
    def test_build_policy_inputs_writes_chronological_tail_score(self):
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
                "combined_regime": ["down_high_vol", "down_high_vol", "down_high_vol", "range"],
                "session_regime": ["asia", "london", "rollover", "asia"],
                "pred_base_long_best_adjusted_pnl": [10.0, 10.0, 10.0, 10.0],
                "pred_base_short_best_adjusted_pnl": [8.0, 8.0, 8.0, 8.0],
                "pred_long_entry_local_rank": [0.8, 0.8, 0.8, 0.8],
                "pred_short_entry_local_rank": [0.7, 0.7, 0.7, 0.7],
            }
        )
        targets = pd.DataFrame(
            {
                "month": ["2024-01", "2024-02", "2024-02"],
                "direction": ["long", "long", "short"],
                "combined_regime": ["down_high_vol", "down_high_vol", "range"],
                "session_regime": ["asia", "london", "asia"],
                "direction_side_inversion_target": [True, True, False],
                "candidate_adjusted_pnl": [-10.0, -8.0, 4.0],
            }
        )

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            prediction_path = tmp_path / "pred.parquet"
            target_path = tmp_path / "targets.csv"
            predictions.to_parquet(prediction_path, index=False)
            targets.to_csv(target_path, index=False)
            args = argparse.Namespace(
                family_predictions=[f"toy={prediction_path}"],
                targets=target_path,
                target="direction_side_inversion_target",
                group_specs="direction_regime",
                score_kind_prefix="side_regime_tail",
                long_column="pred_base_long_best_adjusted_pnl",
                short_column="pred_base_short_best_adjusted_pnl",
                long_rank_column="pred_long_entry_local_rank",
                short_rank_column="pred_short_entry_local_rank",
                penalty_strengths="0.5",
                no_prior_risk=0.0,
                min_score_scale=0.0,
                use_global_risk=False,
                prior_strength=1.0,
                min_group_support=1,
                quantile_scopes="month",
                output_dir=tmp_path,
                label="unit_side_regime_tail_inputs",
            )

            run_dir = entry_ev_side_regime_tail_policy_inputs.build_policy_inputs(args)
            enriched = pd.read_parquet(
                run_dir / "enriched_predictions" / "toy_predictions_side_regime_tail.parquet"
            )
            summary = pd.read_csv(run_dir / "score_adjustment_summary.csv")

            risk_column = (
                "pred_side_regime_tail_direction_regime_long_predicted_tail_risk"
            )
            score_column = (
                "pred_side_regime_tail_direction_regime_s0p5_long_best_adjusted_pnl"
            )
            quantile_column = (
                "pred_side_regime_tail_direction_regime_s0p5_selected_score_pct_month"
            )
            self.assertIn(risk_column, enriched.columns)
            self.assertIn(score_column, enriched.columns)
            self.assertIn(quantile_column, enriched.columns)
            march = enriched[enriched["dataset_month"].eq("2024-03")].reset_index(drop=True)
            self.assertEqual(
                march[
                    "pred_side_regime_tail_direction_regime_long_tail_prediction_source"
                ].iloc[0],
                "bucket",
            )
            self.assertEqual(
                int(
                    march[
                        "pred_side_regime_tail_direction_regime_long_tail_prediction_support"
                    ].iloc[0]
                ),
                2,
            )
            self.assertLess(
                march[score_column].iloc[0],
                march["pred_base_long_best_adjusted_pnl"].iloc[0],
            )
            self.assertEqual(
                summary["score_kind"].iloc[0],
                "side_regime_tail_direction_regime_s0p5",
            )


if __name__ == "__main__":
    unittest.main()
