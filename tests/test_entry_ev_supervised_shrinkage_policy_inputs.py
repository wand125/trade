import importlib.util
import sys
import unittest
from pathlib import Path

import pandas as pd


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "experiments"
    / "entry_ev_supervised_shrinkage_policy_inputs.py"
)
SPEC = importlib.util.spec_from_file_location(
    "entry_ev_supervised_shrinkage_policy_inputs",
    SCRIPT_PATH,
)
entry_ev_supervised_shrinkage_policy_inputs = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = entry_ev_supervised_shrinkage_policy_inputs
SPEC.loader.exec_module(entry_ev_supervised_shrinkage_policy_inputs)


class EntryEvSupervisedShrinkagePolicyInputsTests(unittest.TestCase):
    def trade_frame(self):
        return pd.DataFrame(
            {
                "family": ["fam"],
                "role": ["cal"],
                "month": ["2024-01"],
                "candidate": ["q95"],
                "direction": ["long"],
                "entry_decision_timestamp": ["2024-01-10T00:00:00Z"],
                "adjusted_pnl": [2.0],
                "pred_taken_ev": [10.0],
                "pred_opposite_ev": [6.0],
                "pred_taken_entry_local_rank": [0.8],
                "pred_long_entry_local_rank": [0.8],
                "pred_short_entry_local_rank": [0.2],
                "pred_mlp_long_exit_event_minutes": [60.0],
                "pred_mlp_short_exit_event_minutes": [45.0],
                "selected_pred_mlp_exit_minutes": [60.0],
                "pred_long_exit_event_prob_0": [0.1],
                "pred_short_exit_event_prob_0": [0.2],
                "selected_time_exit_prob": [0.1],
                "pred_long_exit_event_prob_2": [0.3],
                "pred_short_exit_event_prob_2": [0.4],
                "selected_loss_first_prob": [0.3],
                "pred_long_fixed_60m_adjusted_pnl": [1.0],
                "pred_short_fixed_60m_adjusted_pnl": [-1.0],
                "pred_long_fixed_240m_adjusted_pnl": [2.0],
                "pred_short_fixed_240m_adjusted_pnl": [-2.0],
                "pred_long_fixed_720m_adjusted_pnl": [3.0],
                "pred_short_fixed_720m_adjusted_pnl": [-3.0],
                "selected_fixed_60m_pred_pnl": [1.0],
                "selected_fixed_240m_pred_pnl": [2.0],
                "selected_fixed_720m_pred_pnl": [3.0],
                "pred_best_side_prob_1": [0.7],
                "pred_best_side_prob_-1": [0.3],
                "combined_regime": ["range"],
                "session_regime": ["asia"],
            }
        )

    def prediction_frame(self):
        return pd.DataFrame(
            {
                "dataset_month": ["2024-01", "2024-02"],
                "decision_timestamp": [
                    "2024-01-12T00:00:00Z",
                    "2024-02-12T00:00:00Z",
                ],
                "combined_regime": ["range", "range"],
                "session_regime": ["asia", "asia"],
                "pred_calibrated_long_best_adjusted_pnl": [20.0, 20.0],
                "pred_calibrated_short_best_adjusted_pnl": [10.0, 10.0],
                "pred_long_entry_local_rank": [0.8, 0.8],
                "pred_short_entry_local_rank": [0.2, 0.2],
                "pred_mlp_long_exit_event_minutes": [60.0, 60.0],
                "pred_mlp_short_exit_event_minutes": [45.0, 45.0],
                "pred_long_exit_event_prob_0": [0.1, 0.1],
                "pred_short_exit_event_prob_0": [0.2, 0.2],
                "pred_long_exit_event_prob_2": [0.3, 0.3],
                "pred_short_exit_event_prob_2": [0.4, 0.4],
                "pred_long_fixed_60m_adjusted_pnl": [1.0, 1.0],
                "pred_short_fixed_60m_adjusted_pnl": [-1.0, -1.0],
                "pred_long_fixed_240m_adjusted_pnl": [2.0, 2.0],
                "pred_short_fixed_240m_adjusted_pnl": [-2.0, -2.0],
                "pred_long_fixed_720m_adjusted_pnl": [3.0, 3.0],
                "pred_short_fixed_720m_adjusted_pnl": [-3.0, -3.0],
                "pred_best_side_prob_1": [0.7, 0.7],
                "pred_best_side_prob_-1": [0.3, 0.3],
            }
        )

    def test_chronological_predictions_use_selected_trade_prior_months(self):
        train = entry_ev_supervised_shrinkage_policy_inputs.normalize_train_trades(
            self.trade_frame(),
            candidates=set(),
            roles=set(),
            months=set(),
        )
        train_rows = entry_ev_supervised_shrinkage_policy_inputs.train_rows_from_selected_trades(
            train
        )
        target_rows = entry_ev_supervised_shrinkage_policy_inputs.side_rows_for_family(
            self.prediction_frame(),
            family="fam",
            long_column="pred_calibrated_long_best_adjusted_pnl",
            short_column="pred_calibrated_short_best_adjusted_pnl",
            long_rank_column="pred_long_entry_local_rank",
            short_rank_column="pred_short_entry_local_rank",
            long_holding_column="pred_mlp_long_exit_event_minutes",
            short_holding_column="pred_mlp_short_exit_event_minutes",
        )

        scored, folds = entry_ev_supervised_shrinkage_policy_inputs.chronological_predictions(
            train_rows,
            target_rows,
            target_mode="factor",
            min_train_months=1,
            min_train_rows=1,
            max_train_rows=0,
            max_iter=5,
            learning_rate=0.1,
            max_leaf_nodes=3,
            min_samples_leaf=20,
            l2_regularization=0.0,
            random_seed=1,
            default_pnl=0.0,
            default_factor=0.0,
            min_factor=-1.0,
            max_factor=1.0,
        )

        jan = scored[scored["month"].eq("2024-01")]
        feb_long = scored[scored["month"].eq("2024-02") & scored["side"].eq("long")].iloc[0]
        feb_short = scored[scored["month"].eq("2024-02") & scored["side"].eq("short")].iloc[0]
        feb_fold = folds[folds["target_month"].eq("2024-02")].iloc[0]

        self.assertTrue((jan["pred_supervised_shrink_score"] == 0.0).all())
        self.assertAlmostEqual(feb_long["pred_supervised_shrink_raw_target"], 0.2)
        self.assertAlmostEqual(feb_long["pred_supervised_shrink_score"], 4.0)
        self.assertAlmostEqual(feb_short["pred_supervised_shrink_score"], 2.0)
        self.assertEqual(feb_fold["train_rows"], 1)
        self.assertEqual(feb_fold["train_months"], 1)

    def test_attach_predictions_writes_score_and_quantile_columns(self):
        frame = self.prediction_frame()
        target_rows = entry_ev_supervised_shrinkage_policy_inputs.side_rows_for_family(
            frame,
            family="fam",
            long_column="pred_calibrated_long_best_adjusted_pnl",
            short_column="pred_calibrated_short_best_adjusted_pnl",
            long_rank_column="pred_long_entry_local_rank",
            short_rank_column="pred_short_entry_local_rank",
            long_holding_column="pred_mlp_long_exit_event_minutes",
            short_holding_column="pred_mlp_short_exit_event_minutes",
        )
        target_rows["pred_supervised_shrink_score"] = [1.0, 2.0, 3.0, 4.0]
        target_rows["pred_supervised_shrink_raw_target"] = [0.1, 0.2, 0.3, 0.4]
        target_rows["pred_supervised_shrink_model_used"] = True
        target_rows["pred_supervised_shrink_train_rows"] = 10
        target_rows["pred_supervised_shrink_train_months"] = 2

        outputs = entry_ev_supervised_shrinkage_policy_inputs.attach_predictions_to_families(
            {"fam": frame},
            target_rows,
            long_output_column="shrink_long",
            short_output_column="shrink_short",
            score_kind="supervised_shrink",
            long_rank_column="pred_long_entry_local_rank",
            short_rank_column="pred_short_entry_local_rank",
            quantile_scopes=["month"],
        )
        enriched = outputs["fam"]

        self.assertEqual(enriched["shrink_long"].tolist(), [1.0, 2.0])
        self.assertEqual(enriched["shrink_short"].tolist(), [3.0, 4.0])
        self.assertIn("pred_supervised_shrink_selected_score_pct_month", enriched.columns)
        self.assertIn("pred_supervised_shrink_side_gap_pct_month", enriched.columns)


if __name__ == "__main__":
    unittest.main()
