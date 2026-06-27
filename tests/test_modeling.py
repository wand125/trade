import unittest

from trade_data.dataset import iter_months
from trade_data.modeling import (
    add_calibrated_ev_columns,
    build_sample_weights,
    fit_linear_calibrator,
    parse_csv_months,
    regression_training_values,
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


if __name__ == "__main__":
    unittest.main()
