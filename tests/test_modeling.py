import unittest

import numpy as np
import pandas as pd

from trade_data.dataset import iter_months
from trade_data.modeling import (
    add_calibrated_ev_columns,
    apply_split_purging,
    build_sample_weights,
    chunk_months,
    evaluate_models,
    filter_available_target_names,
    fit_linear_calibrator,
    parse_csv_months,
    prediction_frame,
    prediction_frame_evaluation_metrics,
    profit_barrier_bucket_metrics,
    profit_barrier_frame,
    profit_barrier_group_metrics,
    regression_training_values,
    resolve_target_names,
    resolve_split_months,
    selection_metrics,
    side_confidence_bucket_metrics,
    side_confidence_frame,
    side_confidence_group_metrics,
    validate_disjoint_splits,
)


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

    def test_side_confidence_frame_uses_probability_winning_side(self):
        predictions = pd.DataFrame(
            {
                "best_side": [1, -1, -1],
                "pred_best_side_prob_1": [0.8, 0.6, 0.3],
                "pred_best_side_prob_-1": [0.2, 0.4, 0.7],
            }
        )

        output = side_confidence_frame(predictions)

        self.assertEqual(output["side_confidence_predicted_side"].tolist(), [1, 1, -1])
        self.assertEqual(output["side_confidence_hit"].tolist(), [True, False, True])
        self.assertEqual(output["side_confidence"].tolist(), [0.8, 0.6, 0.7])

    def test_side_confidence_group_metrics_exposes_overconfidence(self):
        predictions = pd.DataFrame(
            {
                "best_side": [1, -1, -1, -1],
                "pred_best_side_prob_1": [0.8, 0.8, 0.7, 0.2],
                "pred_best_side_prob_-1": [0.2, 0.2, 0.3, 0.8],
                "dataset_month": ["2024-01", "2024-01", "2024-02", "2024-02"],
            }
        )

        metrics = side_confidence_group_metrics(predictions, ["dataset_month"], min_rows=1)
        month_1 = metrics.loc[
            (metrics["group_key"] == "dataset_month") & (metrics["group_value"] == "2024-01")
        ].iloc[0]

        self.assertEqual(int(month_1["rows"]), 2)
        self.assertAlmostEqual(month_1["accuracy"], 0.5)
        self.assertAlmostEqual(month_1["confidence_mean"], 0.8)
        self.assertAlmostEqual(month_1["overconfidence"], 0.3)

    def test_side_confidence_bucket_metrics_groups_by_split_when_available(self):
        predictions = pd.DataFrame(
            {
                "best_side": [1, -1, -1],
                "pred_best_side_prob_1": [0.55, 0.8, 0.1],
                "pred_best_side_prob_-1": [0.45, 0.2, 0.9],
                "prediction_split": ["valid", "valid", "test"],
            }
        )

        buckets = side_confidence_bucket_metrics(predictions, bucket_count=5, min_confidence=0.5)

        self.assertEqual(set(buckets["prediction_split"]), {"valid", "test"})
        self.assertTrue((buckets["rows"] > 0).all())

    def test_profit_barrier_frame_stacks_long_and_short_probabilities(self):
        predictions = pd.DataFrame(
            {
                "long_profit_barrier_hit": [1, 0],
                "short_profit_barrier_hit": [0, 1],
                "pred_long_profit_barrier_hit_prob_1": [0.8, 0.6],
                "pred_short_profit_barrier_hit_prob_1": [0.2, 0.7],
                "dataset_month": ["2024-01", "2024-01"],
            }
        )

        output = profit_barrier_frame(predictions)

        self.assertEqual(len(output), 4)
        self.assertEqual(output["barrier_side"].tolist(), ["long", "long", "short", "short"])
        self.assertEqual(output["profit_barrier_actual"].tolist(), [1.0, 0.0, 0.0, 1.0])
        self.assertEqual(output["profit_barrier_probability"].tolist(), [0.8, 0.6, 0.2, 0.7])

    def test_profit_barrier_group_metrics_exposes_overestimate(self):
        predictions = pd.DataFrame(
            {
                "long_profit_barrier_hit": [1, 0, 0],
                "short_profit_barrier_hit": [0, 0, 1],
                "pred_long_profit_barrier_hit_prob_1": [0.9, 0.8, 0.7],
                "pred_short_profit_barrier_hit_prob_1": [0.4, 0.6, 0.6],
                "dataset_month": ["2024-01", "2024-01", "2024-02"],
            }
        )

        metrics = profit_barrier_group_metrics(
            predictions,
            ["dataset_month", "barrier_side"],
            min_rows=1,
            threshold=0.5,
        )
        month_1 = metrics.loc[
            (metrics["group_key"] == "dataset_month") & (metrics["group_value"] == "2024-01")
        ].iloc[0]
        long_side = metrics.loc[
            (metrics["group_key"] == "barrier_side") & (metrics["group_value"] == "long")
        ].iloc[0]

        self.assertEqual(int(month_1["rows"]), 4)
        self.assertAlmostEqual(month_1["actual_hit_rate"], 0.25)
        self.assertAlmostEqual(month_1["predicted_probability_mean"], 0.675)
        self.assertAlmostEqual(month_1["overestimate"], 0.425)
        self.assertEqual(int(long_side["rows"]), 3)
        self.assertAlmostEqual(long_side["predicted_hit_rate"], 1.0)

    def test_profit_barrier_bucket_metrics_groups_by_split_when_available(self):
        predictions = pd.DataFrame(
            {
                "long_profit_barrier_hit": [1, 0, 0],
                "short_profit_barrier_hit": [0, 1, 0],
                "pred_long_profit_barrier_hit_prob_1": [0.9, 0.3, 0.55],
                "pred_short_profit_barrier_hit_prob_1": [0.1, 0.8, 0.45],
                "prediction_split": ["valid", "valid", "test"],
            }
        )

        buckets = profit_barrier_bucket_metrics(
            predictions,
            bucket_count=5,
            min_probability=0.0,
            threshold=0.5,
        )

        self.assertEqual(set(buckets["prediction_split"]), {"valid", "test"})
        self.assertTrue((buckets["rows"] > 0).all())

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

    def test_chunk_months_groups_contiguous_months(self):
        chunks = chunk_months(["2024-01", "2024-02", "2024-03", "2024-04", "2024-05"], 2)

        self.assertEqual(chunks, [["2024-01", "2024-02"], ["2024-03", "2024-04"], ["2024-05"]])

    def test_chunk_months_rejects_non_positive_size(self):
        with self.assertRaises(ValueError):
            chunk_months(["2024-01"], 0)

    def test_resolve_split_months_accepts_explicit_non_contiguous_months(self):
        months = resolve_split_months("train", "2024-01,2024-03", None, None)

        self.assertEqual(months, ["2024-01", "2024-03"])

    def test_resolve_policy_target_set_keeps_policy_columns(self):
        regression_targets, classification_targets = resolve_target_names("policy")

        self.assertIn("long_best_adjusted_pnl", regression_targets)
        self.assertIn("short_best_adjusted_pnl", regression_targets)
        self.assertIn("long_fixed_60m_adjusted_pnl", regression_targets)
        self.assertIn("short_fixed_720m_adjusted_pnl", regression_targets)
        self.assertIn("long_wait_regret", regression_targets)
        self.assertIn("short_entry_local_rank", regression_targets)
        self.assertIn("long_profit_barrier_hit", classification_targets)
        self.assertIn("long_profit_barrier_hit_60m", classification_targets)
        self.assertIn("best_side", classification_targets)

    def test_full_target_set_includes_fixed_exit_horizon_targets(self):
        regression_targets, classification_targets = resolve_target_names("full")

        self.assertIn("long_fixed_60m_adjusted_pnl", regression_targets)
        self.assertIn("short_fixed_720m_adjusted_pnl", regression_targets)
        self.assertIn("long_profit_barrier_hit_240m", classification_targets)

    def test_side_confidence_target_set_keeps_only_side_diagnostics(self):
        regression_targets, classification_targets = resolve_target_names("side_confidence")

        self.assertEqual(regression_targets, ["long_best_adjusted_pnl", "short_best_adjusted_pnl"])
        self.assertEqual(classification_targets, ["best_side"])

    def test_profit_barrier_target_set_keeps_only_barrier_classifiers(self):
        regression_targets, classification_targets = resolve_target_names("profit_barrier")

        self.assertEqual(regression_targets, [])
        self.assertEqual(classification_targets, ["long_profit_barrier_hit", "short_profit_barrier_hit"])

    def test_filter_available_target_names_drops_missing_research_targets(self):
        frame = pd.DataFrame(
            {
                "long_best_adjusted_pnl": [1.0],
                "short_best_adjusted_pnl": [2.0],
                "label": [1],
            }
        )

        regression_targets, classification_targets, missing = filter_available_target_names(
            [frame],
            ["long_best_adjusted_pnl", "long_fixed_60m_adjusted_pnl"],
            ["label", "long_profit_barrier_hit"],
        )

        self.assertEqual(regression_targets, ["long_best_adjusted_pnl"])
        self.assertEqual(classification_targets, ["label"])
        self.assertEqual(missing["regression"], ["long_fixed_60m_adjusted_pnl"])
        self.assertEqual(missing["classification"], ["long_profit_barrier_hit"])

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
                "best_side": [-1, 1],
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
                "trend_score_240": [1.0, -1.0],
                "volatility_score_60": [0.001, 0.002],
                "trend_regime": ["up", "down"],
                "volatility_regime": ["high_vol", "high_vol"],
                "session_regime": ["asia", "london"],
                "gap_regime": ["normal_gap", "normal_gap"],
                "combined_regime": ["up_high_vol", "down_high_vol"],
            }
        )
        predictions = {
            "long_best_adjusted_pnl": [1.5, 2.5],
            "short_best_adjusted_pnl": [2.5, 1.5],
        }

        output = prediction_frame(df, predictions)

        self.assertEqual(output["roll_vol_60"].tolist(), [0.01, 0.02])
        self.assertEqual(output["trend_regime"].tolist(), ["up", "down"])
        self.assertEqual(output["best_side"].tolist(), [-1, 1])
        self.assertIn("pred_long_best_adjusted_pnl", output.columns)

    def test_evaluate_models_adds_binary_classifier_probability(self):
        class BinaryClassifier:
            classes_ = np.array([0, 1])

            def predict(self, x):
                return np.array([0, 1])

            def predict_proba(self, x):
                return np.array([[0.8, 0.2], [0.3, 0.7]])

        frame = pd.DataFrame({"feature": [1.0, 2.0], "long_profit_barrier_hit": [0, 1]})

        _, predictions = evaluate_models(
            {"long_profit_barrier_hit": BinaryClassifier()},
            frame,
            ["feature"],
            regression_targets=[],
            classification_targets=["long_profit_barrier_hit"],
        )

        self.assertEqual(predictions["long_profit_barrier_hit"].tolist(), [0, 1])
        self.assertEqual(predictions["long_profit_barrier_hit_prob"].tolist(), [0.2, 0.7])
        self.assertEqual(predictions["long_profit_barrier_hit_prob_0"].tolist(), [0.8, 0.3])
        self.assertEqual(predictions["long_profit_barrier_hit_prob_1"].tolist(), [0.2, 0.7])

    def test_evaluate_models_adds_multiclass_classifier_probabilities(self):
        class MulticlassClassifier:
            classes_ = np.array([0, 1, 2])

            def predict(self, x):
                return np.array([0, 1])

            def predict_proba(self, x):
                return np.array([[0.6, 0.3, 0.1], [0.2, 0.7, 0.1]])

        frame = pd.DataFrame({"feature": [1.0, 2.0], "long_exit_event": [0, 1]})

        _, predictions = evaluate_models(
            {"long_exit_event": MulticlassClassifier()},
            frame,
            ["feature"],
            regression_targets=[],
            classification_targets=["long_exit_event"],
        )

        self.assertEqual(predictions["long_exit_event"].tolist(), [0, 1])
        self.assertEqual(predictions["long_exit_event_prob_0"].tolist(), [0.6, 0.2])
        self.assertEqual(predictions["long_exit_event_prob_1"].tolist(), [0.3, 0.7])
        self.assertEqual(predictions["long_exit_event_prob_2"].tolist(), [0.1, 0.1])
        self.assertNotIn("long_exit_event_prob", predictions)

    def test_prediction_frame_evaluation_metrics_uses_available_targets(self):
        frame = pd.DataFrame(
            {
                "long_best_adjusted_pnl": [10.0, 1.0],
                "short_best_adjusted_pnl": [0.0, 12.0],
                "pred_long_best_adjusted_pnl": [11.0, 2.0],
                "pred_short_best_adjusted_pnl": [1.0, 13.0],
                "label": [1, -1],
                "pred_label": [1, -1],
            }
        )

        metrics = prediction_frame_evaluation_metrics(
            frame,
            regression_targets=["long_best_adjusted_pnl", "short_best_adjusted_pnl"],
            classification_targets=["label", "best_holding_time_bin"],
            entry_threshold=5.0,
        )

        self.assertIn("long_best_adjusted_pnl", metrics["regression"])
        self.assertIn("label", metrics["classification"])
        self.assertNotIn("best_holding_time_bin", metrics["classification"])
        self.assertEqual(metrics["selection"]["selected_trade_count"], 2)

    def test_prediction_frame_evaluation_metrics_allows_no_ev_selection_columns(self):
        frame = pd.DataFrame(
            {
                "long_profit_barrier_hit": [1, 0],
                "pred_long_profit_barrier_hit": [1, 1],
            }
        )

        metrics = prediction_frame_evaluation_metrics(
            frame,
            regression_targets=[],
            classification_targets=["long_profit_barrier_hit"],
            entry_threshold=10.0,
        )

        self.assertIn("long_profit_barrier_hit", metrics["classification"])
        self.assertNotIn("selection", metrics)

    def test_apply_split_purging_removes_label_overlap(self):
        train = pd.DataFrame(
            {
                "decision_timestamp": pd.to_datetime(
                    ["2025-01-01 00:00", "2025-01-01 01:00"],
                    utc=True,
                ),
                "entry_timestamp": pd.to_datetime(
                    ["2025-01-01 00:01", "2025-01-01 01:01"],
                    utc=True,
                ),
            }
        )
        valid = pd.DataFrame(
            {
                "decision_timestamp": pd.to_datetime(["2025-01-01 02:00"], utc=True),
                "entry_timestamp": pd.to_datetime(["2025-01-01 02:01"], utc=True),
            }
        )
        test = pd.DataFrame(
            {
                "decision_timestamp": pd.to_datetime(["2025-01-02 00:00"], utc=True),
                "entry_timestamp": pd.to_datetime(["2025-01-02 00:01"], utc=True),
            }
        )

        purged_train, purged_valid, _, stats = apply_split_purging(
            train,
            valid,
            test,
            horizon_hours=1.5,
            embargo_hours=0.0,
            enabled=True,
        )

        self.assertEqual(len(purged_train), 1)
        self.assertEqual(len(purged_valid), 1)
        self.assertEqual(stats["train_rows_removed"], 1)
        self.assertEqual(purged_train["decision_timestamp"].iloc[0], train["decision_timestamp"].iloc[0])

    def test_split_purging_keeps_gap_between_discontinuous_test_months(self):
        train = pd.DataFrame(
            {
                "decision_timestamp": pd.to_datetime(["2025-01-01 00:00"], utc=True),
                "entry_timestamp": pd.to_datetime(["2025-01-01 00:01"], utc=True),
                "dataset_month": ["2025-01"],
            }
        )
        valid = pd.DataFrame(
            {
                "decision_timestamp": pd.to_datetime(["2025-01-15 00:00"], utc=True),
                "entry_timestamp": pd.to_datetime(["2025-01-15 00:01"], utc=True),
                "dataset_month": ["2025-01"],
            }
        )
        test = pd.DataFrame(
            {
                "decision_timestamp": pd.to_datetime(["2024-12-01 00:00", "2025-02-01 00:00"], utc=True),
                "entry_timestamp": pd.to_datetime(["2024-12-01 00:01", "2025-02-01 00:01"], utc=True),
                "dataset_month": ["2024-12", "2025-02"],
            }
        )

        _, purged_valid, _, stats = apply_split_purging(
            train,
            valid,
            test,
            horizon_hours=24,
            embargo_hours=24,
            enabled=True,
        )

        self.assertEqual(len(purged_valid), 1)
        self.assertEqual(stats["valid_rows_removed"], 0)


if __name__ == "__main__":
    unittest.main()
