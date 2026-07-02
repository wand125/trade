import importlib.util
import sys
import unittest
from pathlib import Path

import pandas as pd


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "experiments"
    / "entry_ev_selected_trade_large_loss_head.py"
)
SPEC = importlib.util.spec_from_file_location(
    "entry_ev_selected_trade_large_loss_head",
    SCRIPT_PATH,
)
entry_ev_selected_trade_large_loss_head = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = entry_ev_selected_trade_large_loss_head
SPEC.loader.exec_module(entry_ev_selected_trade_large_loss_head)


class EntryEvSelectedTradeLargeLossHeadTests(unittest.TestCase):
    def prior_rows(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "supervised_target_mode": ["factor"] * 6,
                "group_spec": ["direction,session_regime"] * 6,
                "month": [
                    "2024-01",
                    "2024-01",
                    "2024-02",
                    "2024-02",
                    "2024-03",
                    "2024-03",
                ],
                "role": ["cal"] * 6,
                "direction": ["long", "short", "long", "short", "long", "short"],
                "combined_regime": ["range"] * 6,
                "session_regime": ["asia", "ny", "asia", "ny", "asia", "ny"],
                "group_key": [
                    "long|asia",
                    "short|ny",
                    "long|asia",
                    "short|ny",
                    "long|asia",
                    "short|ny",
                ],
                "adjusted_pnl": [2.0, -3.0, 1.0, -4.0, 3.0, -5.0],
                "is_loss": [False, True, False, True, False, True],
                "is_large_loss": [False, True, False, True, False, True],
                "score": [0.1, 0.9, 0.2, 0.8, 0.1, 0.7],
                "raw_score": [10, 10, 10, 10, 10, 10],
                "pred_taken_ev": [10, 10, 10, 10, 10, 10],
                "selected_loss_first_prob": [0.1, 0.8, 0.2, 0.7, 0.1, 0.9],
                "pred_side_confidence_gap": [0.1, -0.1, 0.2, -0.2, 0.1, -0.3],
                "pred_taken_entry_local_rank": [0.5] * 6,
                "train_rows": [0, 0, 2, 2, 4, 4],
                "train_months": [0, 0, 1, 1, 2, 2],
                "prior_trade_count": [0, 0, 1, 1, 2, 2],
                "prior_month_count": [0, 0, 1, 1, 2, 2],
                "prior_total_pnl": [0, 0, 2, -3, 3, -7],
                "prior_avg_pnl": [0, 0, 2, -3, 1.5, -3.5],
                "prior_loss_rate": [0, 0, 0, 1, 0, 1],
                "prior_large_loss_rate": [0, 0, 0, 1, 0, 1],
                "prior_bias_mean": [0, 0, -1, 4, -0.5, 3.5],
                "prior_mae_mean": [0, 0, 1, 4, 1, 3.5],
                "prior_overestimate_rate": [0, 0, 0, 1, 0, 1],
                "prior_overestimate_mean": [0, 0, 0, 4, 0, 3.5],
                "prior_residual_pressure": [0, 0, 0, 6, 0, 8],
            }
        )

    def test_chronological_predictions_use_prior_months_only(self):
        frame = entry_ev_selected_trade_large_loss_head.normalize_prior_rows(
            self.prior_rows(),
            target_modes={"factor"},
            group_specs={"direction,session_regime"},
        )
        feature_sets = entry_ev_selected_trade_large_loss_head.build_feature_sets(
            frame,
            numeric_features=["score"],
            prior_numeric_features=["prior_residual_pressure"],
        )
        predictions, folds = entry_ev_selected_trade_large_loss_head.chronological_predictions(
            frame,
            feature_sets=feature_sets,
            categorical_features=["direction", "session_regime"],
            min_train_months=1,
            min_train_rows=2,
            max_iter=5,
            learning_rate=0.1,
            max_leaf_nodes=3,
            min_samples_leaf=1,
            l2_regularization=0.0,
            random_seed=1,
        )

        jan_fold = folds[
            folds["fold"].eq("2024-01") & folds["feature_set"].eq("base")
        ].iloc[0]
        feb_fold = folds[
            folds["fold"].eq("2024-02") & folds["feature_set"].eq("base")
        ].iloc[0]

        self.assertFalse(bool(jan_fold["model_used"]))
        self.assertEqual(jan_fold["train_rows"], 0)
        self.assertTrue(bool(feb_fold["model_used"]))
        self.assertEqual(feb_fold["train_rows"], 2)
        self.assertEqual(set(predictions["large_loss_feature_set"]), {"base", "base_prior"})

    def test_threshold_summary_reports_block_delta(self):
        frame = pd.DataFrame(
            {
                "supervised_target_mode": ["factor", "factor", "factor"],
                "group_spec": ["g", "g", "g"],
                "large_loss_feature_set": ["base", "base", "base"],
                "adjusted_pnl": [-5.0, 3.0, -1.0],
                "is_loss": [True, False, True],
                "is_large_loss": [True, False, False],
                "pred_large_loss_prob": [0.9, 0.2, 0.8],
            }
        )
        summary = entry_ev_selected_trade_large_loss_head.threshold_summary(
            frame,
            thresholds=[0.5],
            quantiles=[],
        )
        row = summary.iloc[0]

        self.assertEqual(row["flagged_trade_count"], 2)
        self.assertEqual(row["flagged_pnl"], -6.0)
        self.assertEqual(row["block_delta_if_removed"], 6.0)
        self.assertEqual(row["flagged_large_loss_count"], 1)


if __name__ == "__main__":
    unittest.main()
