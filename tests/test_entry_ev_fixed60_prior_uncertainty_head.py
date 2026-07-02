import importlib.util
import sys
import unittest
from pathlib import Path

import pandas as pd


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "experiments"
    / "entry_ev_fixed60_prior_uncertainty_head.py"
)
SPEC = importlib.util.spec_from_file_location(
    "entry_ev_fixed60_prior_uncertainty_head",
    SCRIPT_PATH,
)
entry_ev_fixed60_prior_uncertainty_head = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = entry_ev_fixed60_prior_uncertainty_head
SPEC.loader.exec_module(entry_ev_fixed60_prior_uncertainty_head)


class EntryEvFixed60PriorUncertaintyHeadTests(unittest.TestCase):
    def prior_rows(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "group_spec": ["direction,session_regime"] * 6,
                "group_key": [
                    "long|ny",
                    "short|ny",
                    "long|ny",
                    "short|ny",
                    "long|ny",
                    "short|ny",
                ],
                "month": [
                    "2024-01",
                    "2024-01",
                    "2024-02",
                    "2024-02",
                    "2024-03",
                    "2024-03",
                ],
                "source": ["unit"] * 6,
                "role": ["cal"] * 6,
                "family": ["fam"] * 6,
                "direction": ["long", "short", "long", "short", "long", "short"],
                "combined_regime": ["range"] * 6,
                "session_regime": ["ny"] * 6,
                "adjusted_pnl": [-2.0, 3.0, -3.0, 2.0, -4.0, 1.0],
                "fixed_false_positive": [True, False, True, False, True, False],
                "is_loss": [True, False, True, False, True, False],
                "fixed_pred_pnl": [1.0, -0.5, 2.0, -0.2, 3.0, -0.1],
                "selected_fixed_60m_pred_pnl": [1.0, -0.5, 2.0, -0.2, 3.0, -0.1],
                "selected_fixed_240m_pred_pnl": [1.0, 0.0, 2.0, 0.0, 3.0, 0.0],
                "selected_fixed_720m_pred_pnl": [1.0, 0.0, 2.0, 0.0, 3.0, 0.0],
                "selected_loss_first_prob": [0.7, 0.1, 0.8, 0.2, 0.9, 0.1],
                "pred_side_confidence_gap": [0.1] * 6,
                "pred_taken_entry_local_rank": [0.5] * 6,
                "pred_taken_ev": [5.0] * 6,
                "pred_opposite_ev": [0.0] * 6,
                "entry_hour": [15] * 6,
                "prior_trade_count": [0, 0, 1, 1, 2, 2],
                "prior_month_count": [0, 0, 1, 1, 2, 2],
                "prior_adjusted_pnl_sum": [0, 0, -2, 3, -5, 5],
                "prior_adjusted_pnl_mean": [0, 0, -2, 3, -2.5, 2.5],
                "prior_adjusted_loss_rate": [0, 0, 1, 0, 1, 0],
                "prior_fixed_pred_mean": [0, 0, 1, -0.5, 1.5, -0.35],
                "prior_fixed_actual_mean": [0, 0, -1, 0.5, -1.5, 0.5],
                "prior_fixed_error_mean": [0, 0, 2, -1, 3, -1],
                "prior_fixed_abs_error_mean": [0, 0, 2, 1, 3, 1],
                "prior_fixed_overestimate_mean": [0, 0, 2, 0, 3, 0],
                "prior_fixed_pred_positive_rate": [0, 0, 1, 0, 1, 0],
                "prior_fixed_actual_negative_rate": [0, 0, 1, 0, 1, 0],
                "prior_fixed_false_positive_trade_rate": [0, 0, 1, 0, 1, 0],
                "prior_fixed_false_positive_rate": [0, 0, 1, 0, 1, 0],
                "prior_fixed_uncertainty_pressure": [0, 0, 5, 0, 8, 0],
            }
        )

    def test_chronological_predictions_use_prior_months_only(self):
        frame = entry_ev_fixed60_prior_uncertainty_head.normalize_prior_rows(
            self.prior_rows(),
            group_specs={"direction,session_regime"},
            target_columns=["fixed_false_positive"],
        )
        feature_sets = entry_ev_fixed60_prior_uncertainty_head.build_feature_sets(
            frame,
            numeric_features=["fixed_pred_pnl"],
            prior_numeric_features=["prior_fixed_uncertainty_pressure"],
        )
        predictions, folds = entry_ev_fixed60_prior_uncertainty_head.chronological_predictions(
            frame,
            target_columns=["fixed_false_positive"],
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

        jan = folds[
            folds["fold"].eq("2024-01") & folds["feature_set"].eq("base")
        ].iloc[0]
        feb = folds[
            folds["fold"].eq("2024-02") & folds["feature_set"].eq("base")
        ].iloc[0]

        self.assertFalse(bool(jan["model_used"]))
        self.assertEqual(jan["train_rows"], 0)
        self.assertTrue(bool(feb["model_used"]))
        self.assertEqual(feb["train_rows"], 2)
        self.assertEqual(
            set(predictions["fixed60_uncertainty_feature_set"]),
            {"base", "base_fixed_prior"},
        )

    def test_threshold_summary_reports_target_precision_and_pnl(self):
        frame = pd.DataFrame(
            {
                "uncertainty_target": ["fixed_false_positive"] * 3,
                "group_spec": ["g"] * 3,
                "fixed60_uncertainty_feature_set": ["base"] * 3,
                "target_value": [True, False, True],
                "fixed_false_positive": [True, False, True],
                "is_loss": [True, False, True],
                "adjusted_pnl": [-5.0, 3.0, -1.0],
                "pred_fixed60_uncertainty_prob": [0.9, 0.2, 0.8],
            }
        )
        summary = entry_ev_fixed60_prior_uncertainty_head.threshold_summary(
            frame,
            thresholds=[0.5],
            quantiles=[],
        )
        row = summary.iloc[0]

        self.assertEqual(row["flagged_trade_count"], 2)
        self.assertEqual(row["flagged_target_count"], 2)
        self.assertEqual(row["target_precision"], 1.0)
        self.assertEqual(row["flagged_pnl"], -6.0)
        self.assertEqual(row["block_delta_if_removed"], 6.0)


if __name__ == "__main__":
    unittest.main()
