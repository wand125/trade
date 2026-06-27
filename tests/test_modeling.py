import unittest

from trade_data.dataset import iter_months
from trade_data.modeling import (
    add_calibrated_ev_columns,
    build_sample_weights,
    fit_linear_calibrator,
    parse_csv_months,
    prediction_frame,
    regression_training_values,
    resolve_target_names,
    resolve_split_months,
    selection_metrics,
    validate_disjoint_splits,
)

import pandas as pd


class ModelingTests(unittest.TestCase):
    def test_iter_months_inclusive(self):
        self.assertEqual(iter_months("2025-01", "2025-03"), ["2025-01", "2025-02", "2025-03"])

    def test_selection_metrics_uses_predicted_side_and_threshold(self):
        predictions = pd.DataFrame(
            {
                "pred_long_best_adjusted_pnl": [20.0, 1.0, 5.0],
                "pred_short_best_adjusted_pnl": [2.0, 30.0, 4.0],
                "long_best_adjusted_pnl": [18.0, 3.0, 7.0],
                "short_best_adjusted_pnl": [4.0, 25.0, 2.0],
            }
        )

        metrics = selection_metrics(predictions, threshold=10.0)

        self.assertEqual(metrics["selected_trade_count"], 2)
        self.assertAlmostEqual(metrics["selected_oracle_exit_adjusted_pnl"], 43.0)
        self.assertAlmostEqual(metrics["selected_side_accuracy"], 1.0)

    def test_linear_calibrator_maps_prediction_scale(self):
        calibrator = fit_linear_calibrator(
            pd.Series([2.0, 4.0, 6.0]),
            pd.Series([1.0, 2.0, 3.0]),
        )

        self.assertAlmostEqual(calibrator.slope, 2.0)
        self.assertAlmostEqual(calibrator.intercept, 0.0)

    def test_add_calibrated_ev_columns(self):
        predictions = pd.DataFrame(
            {
                "pred_long_best_adjusted_pnl": [1.0],
                "pred_short_best_adjusted_pnl": [2.0],
            }
        )

        calibrated = add_calibrated_ev_columns(
            predictions,
            {
                "long_best_adjusted_pnl": fit_linear_calibrator(pd.Series([2.0, 4.0]), pd.Series([1.0, 2.0])),
                "short_best_adjusted_pnl": fit_linear_calibrator(pd.Series([3.0, 5.0]), pd.Series([1.0, 2.0])),
            },
        )

        self.assertAlmostEqual(calibrated["pred_calibrated_long_best_adjusted_pnl"].iloc[0], 2.0)
        self.assertAlmostEqual(calibrated["pred_calibrated_short_best_adjusted_pnl"].iloc[0], 5.0)

    def test_regression_training_values_can_clip_outliers(self):
        values = regression_training_values(pd.Series([0.0, 1.0, 2.0, 100.0]), 0.75)

        self.assertGreater(values[-1], 2.0)
        self.assertLess(values[-1], 100.0)

    def test_regression_training_values_default_keeps_values(self):
        values = regression_training_values(pd.Series([0.0, 1.0, 2.0]), 1.0)

        self.assertEqual(values.tolist(), [0.0, 1.0, 2.0])

    def test_parse_csv_months(self):
        self.assertEqual(parse_csv_months("2024-01,2024-03"), ["2024-01", "2024-03"])

    def test_resolve_split_months_accepts_explicit_non_contiguous_months(self):
        months = resolve_split_months("train", "2024-01,2024-03", None, None)

        self.assertEqual(months, ["2024-01", "2024-03"])

    def test_resolve_policy_target_set_keeps_policy_columns(self):
        regression_targets, classification_targets = resolve_target_names("policy")

        self.assertIn("long_best_adjusted_pnl", regression_targets)
        self.assertIn("short_best_adjusted_pnl", regression_targets)
        self.assertIn("long_wait_regret", regression_targets)
        self.assertIn("short_entry_local_rank", regression_targets)
        self.assertIn("long_profit_barrier_hit", classification_targets)

    def test_validate_disjoint_splits_rejects_overlap(self):
        with self.assertRaises(ValueError):
            validate_disjoint_splits({"train": ["2024-01"], "valid": ["2024-01"], "test": ["2024-02"]})

    def test_month_label_sample_weighting_balances_cells(self):
        df = pd.DataFrame(
            {
                "dataset_month": ["2024-01", "2024-01", "2024-01", "2024-02", "2024-02"],
                "label": [1, 1, -1, 1, -1],
            }
        )

        weights = pd.Series(build_sample_weights(df, "month_label"))
        weighted = df.assign(weight=weights).groupby(["dataset_month", "label"])["weight"].sum()

        self.assertAlmostEqual(weighted.loc[("2024-01", 1)], weighted.loc[("2024-01", -1)])
        self.assertAlmostEqual(weighted.loc[("2024-01", -1)], weighted.loc[("2024-02", 1)])
        self.assertAlmostEqual(float(weights.mean()), 1.0)

    def test_prediction_frame_keeps_regime_features_when_present(self):
        df = pd.DataFrame(
            {
                "decision_timestamp": pd.date_range("2024-01-01", periods=2, tz="UTC"),
                "entry_timestamp": pd.date_range("2024-01-01 00:01", periods=2, tz="UTC"),
                "dataset_month": ["2024-01", "2024-01"],
                "label": [1, -1],
                "long_best_adjusted_pnl": [1.0, 2.0],
                "short_best_adjusted_pnl": [2.0, 1.0],
                "side_score": [-1.0, 1.0],
                "best_adjusted_pnl": [2.0, 2.0],
                "best_holding_minutes": [10.0, 20.0],
                "long_best_holding_minutes": [10.0, 20.0],
                "short_best_holding_minutes": [20.0, 10.0],
                "long_max_adverse_pnl": [-1.0, -2.0],
                "short_max_adverse_pnl": [-2.0, -1.0],
                "long_profit_barrier_hit": [1, 0],
                "short_profit_barrier_hit": [0, 1],
                "long_wait_regret": [0.1, 0.2],
                "short_wait_regret": [0.2, 0.1],
                "long_entry_local_rank": [0.7, 0.3],
                "short_entry_local_rank": [0.3, 0.7],
                "long_entry_urgency": [1.0, -1.0],
                "short_entry_urgency": [-1.0, 1.0],
                "long_wait_regret_quantile": [0, 1],
                "short_wait_regret_quantile": [1, 0],
                "long_entry_local_rank_bin": [3, 1],
                "short_entry_local_rank_bin": [1, 3],
                "roll_vol_60": [0.01, 0.02],
            }
        )
        predictions = {
            "long_best_adjusted_pnl": [1.5, 2.5],
            "short_best_adjusted_pnl": [2.5, 1.5],
        }

        output = prediction_frame(df, predictions)

        self.assertEqual(output["roll_vol_60"].tolist(), [0.01, 0.02])
        self.assertIn("pred_long_best_adjusted_pnl", output.columns)


if __name__ == "__main__":
    unittest.main()
