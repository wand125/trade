import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from trade_data.next_bar import (
    AdoptionOptimizationConfig,
    OddsCalibrationConfig,
    TrainConfig,
    WalkForwardFold,
    build_labeled_dataset,
    build_walk_forward_odds_calibration,
    build_feature_frame,
    calibrate_prediction_odds,
    chronological_split,
    evaluate_probabilities,
    evaluate_adoption_rule,
    evaluate_context_rule,
    fit_context_confidence_model,
    fit_direction_confidence_calibrator,
    fit_empirical_odds_calibrator,
    optimize_adoption_rule,
    optimize_walk_forward_policy,
    predict_latest,
    parse_walk_forward_fold,
    resample_complete_bars,
    train_all_timeframes,
    validate_stationary_feature_set,
    walk_forward_all_timeframes,
    wilson_accuracy_lower_bound,
)


def m1_frame(rows: int, start: str = "2024-01-01 00:00:00+00:00") -> pd.DataFrame:
    timestamp = pd.date_range(start, periods=rows, freq="min")
    increments = 0.02 * np.sin(np.arange(rows) / 7.0) + 0.01 * np.cos(np.arange(rows) / 19.0)
    close = 2000.0 + np.cumsum(increments)
    open_ = np.r_[close[0] - increments[0], close[:-1]]
    return pd.DataFrame(
        {
            "timestamp": timestamp,
            "open": open_,
            "high": np.maximum(open_, close) + 0.01,
            "low": np.minimum(open_, close) - 0.01,
            "close": close,
        }
    )


class NextBarTests(unittest.TestCase):
    def test_empirical_odds_are_shrunk_and_include_support(self):
        rows = 2_000
        correct = np.zeros(rows, dtype=bool)
        correct[:600] = True
        correct[1_000:1_520] = True
        predictions = pd.DataFrame(
            {
                "decision_timestamp": pd.date_range(
                    "2024-01-01", periods=rows, freq="h", tz="UTC"
                ),
                "target_up": np.r_[correct[:1_000], ~correct[1_000:]].astype("int8"),
                "probability_up": np.r_[np.full(1_000, 0.55), np.full(1_000, 0.45)],
                "predicted_direction": np.r_[
                    np.full(1_000, "up"), np.full(1_000, "down")
                ],
                "confidence": 0.55,
                "correct": correct,
                "volatility_regime": np.r_[
                    np.full(1_000, "high"), np.full(1_000, "normal")
                ],
            }
        )
        calibrator = fit_empirical_odds_calibrator(
            predictions,
            OddsCalibrationConfig(bins=5, min_support=100, prior_strength=100),
        )
        calibrator["calibration_valid"] = True
        odds = calibrate_prediction_odds(0.55, "up", "high", calibrator)

        self.assertEqual(odds["support_count"], 1_000)
        self.assertEqual(odds["calibration_level"], "side_regime_bin")
        self.assertGreater(odds["confidence"], 0.59)
        self.assertLess(odds["confidence"], 0.60)
        self.assertTrue(odds["odds_valid"])
        self.assertAlmostEqual(odds["fair_decimal_odds"], 1 / odds["confidence"])

    def test_wilson_lower_bound_penalizes_small_samples(self):
        small = wilson_accuracy_lower_bound(6, 10)
        large = wilson_accuracy_lower_bound(600, 1000)

        self.assertLess(small, large)
        self.assertLess(large, 0.60)

    def test_adoption_optimizer_balances_quality_and_coverage(self):
        rows = 1_000
        timestamps = pd.date_range("2024-01-01", periods=rows, freq="h", tz="UTC")
        high = np.zeros(rows, dtype=bool)
        high[:200] = True
        correct = np.zeros(rows, dtype=bool)
        correct[:120] = True
        correct[200:608] = True
        target = correct.astype("int8")
        predictions = pd.DataFrame(
            {
                "decision_timestamp": timestamps,
                "target_up": target,
                "probability_up": np.full(rows, 0.51),
                "predicted_direction": "up",
                "confidence": 0.51,
                "correct": correct,
                "volatility_regime": np.where(high, "high", "normal"),
            }
        )
        config = AdoptionOptimizationConfig(
            min_rows=100,
            min_coverage=0.10,
            confidence_thresholds=(0.50,),
        )
        rule, metrics = optimize_adoption_rule(predictions, config)
        evaluated = evaluate_adoption_rule(predictions, rule, config)

        self.assertTrue(rule["enabled"])
        self.assertEqual(rule.get("volatility_regimes"), ["high"])
        self.assertAlmostEqual(metrics["coverage"], 0.20)
        self.assertAlmostEqual(evaluated["accuracy"], 0.60)
        self.assertGreater(metrics["selection_score"], 0)

    def test_context_rule_applies_optimized_confidence_and_direction(self):
        timestamp = pd.Timestamp("2024-01-01 21:30", tz="UTC")
        rule = {
            "min_confidence": 0.54,
            "predicted_directions": ["up"],
            "utc_hours": [21],
        }

        self.assertEqual(
            evaluate_context_rule(
                timestamp, "high", rule, confidence=0.55, predicted_direction="up"
            ),
            (True, "context_selected"),
        )
        self.assertEqual(
            evaluate_context_rule(
                timestamp, "high", rule, confidence=0.53, predicted_direction="up"
            ),
            (False, "confidence_below_threshold"),
        )

    def test_context_rule_can_abstain_by_hour_or_volatility(self):
        timestamp = pd.Timestamp("2024-01-01 21:30", tz="UTC")
        self.assertEqual(
            evaluate_context_rule(timestamp, "high", {"utc_hours": [21]}),
            (True, "context_selected"),
        )
        self.assertEqual(
            evaluate_context_rule(timestamp, "normal", {"volatility_regimes": ["high"]}),
            (False, "volatility_regime_not_selected"),
        )

    def test_raw_price_levels_are_rejected_as_model_features(self):
        validate_stationary_feature_set(["log_return_1", "rsi_14"])
        with self.assertRaisesRegex(ValueError, "raw price levels"):
            validate_stationary_feature_set(["log_return_1", "close"])

    def test_enhanced_manual_features_are_derived_not_price_levels(self):
        bars = resample_complete_bars(m1_frame(400), 1)
        _, feature_columns = build_feature_frame(bars, 1, "enhanced_manual")

        self.assertIn("body_atr_20", feature_columns)
        self.assertIn("up_fraction_20", feature_columns)
        self.assertIn("ema_spread_atr_20", feature_columns)
        self.assertFalse({"open", "high", "low", "close"}.intersection(feature_columns))

    def test_sequence_manual_features_preserve_recent_order_without_price_levels(self):
        bars = resample_complete_bars(m1_frame(400), 1)
        _, feature_columns = build_feature_frame(bars, 1, "sequence_manual")

        self.assertIn("sequence_return_atr_lag_0", feature_columns)
        self.assertIn("sequence_body_atr_lag_7", feature_columns)
        self.assertIn("sequence_close_location_centered_lag_3", feature_columns)
        self.assertEqual(
            len([name for name in feature_columns if name.startswith("sequence_")]),
            40,
        )
        self.assertFalse({"open", "high", "low", "close"}.intersection(feature_columns))

    def test_walk_forward_fold_parser_validates_order(self):
        fold = parse_walk_forward_fold("wf1,2022-01-01,2023-01-01,2024-01-01")
        self.assertEqual(fold.name, "wf1")
        self.assertEqual(fold.train_end, pd.Timestamp("2022-01-01", tz="UTC"))
        with self.assertRaises(Exception):
            parse_walk_forward_fold("bad,2024-01-01,2023-01-01,2025-01-01")

    def test_resample_keeps_only_complete_bars(self):
        source = m1_frame(12)
        bars = resample_complete_bars(source, 5)

        self.assertEqual(len(bars), 2)
        self.assertEqual(bars["source_rows"].tolist(), [5, 5])
        self.assertEqual(bars.loc[0, "open"], source.loc[0, "open"])
        self.assertEqual(bars.loc[0, "close"], source.loc[4, "close"])

    def test_label_is_the_immediately_following_completed_bar(self):
        source = m1_frame(400)
        bars = resample_complete_bars(source, 5)
        dataset, _, diagnostics = build_labeled_dataset(bars, 5)
        row = dataset.iloc[0]
        current_index = bars.index[bars["timestamp"] == row["timestamp"]][0]
        following = bars.iloc[current_index + 1]

        self.assertEqual(row["decision_timestamp"], row["timestamp"] + pd.Timedelta(minutes=5))
        self.assertEqual(row["target_timestamp"], following["timestamp"] + pd.Timedelta(minutes=5))
        self.assertEqual(row["target_up"], int(following["close"] > following["open"]))
        self.assertGreater(diagnostics["excluded_feature_warmup_or_nonfinite"], 0)

    def test_split_purges_label_that_crosses_boundary(self):
        source = m1_frame(500)
        bars = resample_complete_bars(source, 1)
        dataset, _, _ = build_labeled_dataset(bars, 1)
        train_end = dataset["decision_timestamp"].iloc[200]
        calibration_end = dataset["decision_timestamp"].iloc[300]
        test_end = dataset["target_timestamp"].iloc[-1] + pd.Timedelta(minutes=1)
        splits = chronological_split(dataset, train_end, calibration_end, test_end)

        self.assertTrue((splits["train"]["target_timestamp"] <= train_end).all())
        self.assertTrue((splits["calibration"]["decision_timestamp"] >= train_end).all())
        self.assertTrue((splits["calibration"]["target_timestamp"] <= calibration_end).all())
        self.assertTrue((splits["test"]["decision_timestamp"] >= calibration_end).all())

    def test_probability_metrics_include_confidence_coverage(self):
        metrics = evaluate_probabilities(
            np.array([1, 0, 1, 0]), np.array([0.9, 0.2, 0.6, 0.7]), thresholds=(0.5, 0.8)
        )

        self.assertAlmostEqual(metrics["accuracy"], 0.75)
        self.assertEqual(metrics["confidence_table"][1]["rows"], 2)
        self.assertAlmostEqual(metrics["confidence_table"][1]["accuracy"], 1.0)

    def test_confidence_is_calibrated_separately_by_predicted_direction(self):
        probability = np.array([0.9, 0.8, 0.7, 0.6, 0.4, 0.3, 0.2, 0.1])
        labels = np.array([1, 1, 1, 0, 0, 1, 1, 1])
        calibrator = fit_direction_confidence_calibrator(labels, probability)
        confidence = calibrator.predict(np.array([0.8, 0.2]))

        self.assertEqual(calibrator.predicted_up_rows, 4)
        self.assertEqual(calibrator.predicted_down_rows, 4)
        self.assertGreater(confidence[0], confidence[1])

    def test_context_confidence_model_uses_derived_context(self):
        bars = resample_complete_bars(m1_frame(1800), 1)
        dataset, _, _ = build_labeled_dataset(bars, 1)
        train = dataset.iloc[:700]
        calibration = dataset.iloc[700:1100]
        train_probability = np.where(train["body_ratio"] > 0, 0.55, 0.45)
        calibration_probability = np.where(calibration["body_ratio"] > 0, 0.55, 0.45)
        model = fit_context_confidence_model(
            train,
            train_probability,
            calibration,
            calibration_probability,
            min_samples_leaf=10,
            random_seed=42,
        )
        confidence = model.predict(calibration.iloc[:10], calibration_probability[:10])

        self.assertEqual(len(confidence), 10)
        self.assertTrue(((confidence > 0) & (confidence < 1)).all())
        self.assertFalse({"open", "high", "low", "close"}.intersection(model.feature_columns))

    def test_end_to_end_training_and_latest_prediction(self):
        source = m1_frame(1800)
        config = TrainConfig(
            timeframes=(1, 5),
            train_fraction=0.6,
            calibration_fraction=0.2,
            max_train_rows=2_000,
            max_iter=10,
            min_samples_leaf=10,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            report = train_all_timeframes(source, output_dir, config)
            latest = predict_latest(source, output_dir)

            self.assertEqual(set(report["timeframes"]), {"M1", "M5"})
            self.assertTrue((output_dir / "manifest.json").exists())
            self.assertTrue((output_dir / "metrics.json").exists())
            self.assertEqual(latest["timeframe"].tolist(), ["M1", "M5"])
            self.assertTrue(latest["class_confidence"].between(0.5, 1.0).all())
            self.assertTrue(latest["confidence"].between(0.0, 1.0).all())
            self.assertTrue(latest["prediction_eligible"].all())
            self.assertIn("context_diagnostics", report["timeframes"]["M1"])

    def test_walk_forward_runs_multiple_expanding_folds(self):
        source = m1_frame(3000)
        folds = [
            WalkForwardFold(
                "wf1",
                pd.Timestamp("2024-01-01 12:00", tz="UTC"),
                pd.Timestamp("2024-01-01 18:00", tz="UTC"),
                pd.Timestamp("2024-01-02 00:00", tz="UTC"),
            ),
            WalkForwardFold(
                "wf2",
                pd.Timestamp("2024-01-01 18:00", tz="UTC"),
                pd.Timestamp("2024-01-02 00:00", tz="UTC"),
                pd.Timestamp("2024-01-02 12:00", tz="UTC"),
            ),
        ]
        config = TrainConfig(
            timeframes=(1,), max_train_rows=2_000, max_iter=5, min_samples_leaf=10
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            report = walk_forward_all_timeframes(source, output_dir, config, folds)
            policy = optimize_walk_forward_policy(
                output_dir,
                output_dir / "optimized_policy.json",
                AdoptionOptimizationConfig(min_rows=10, min_coverage=0.05),
            )
            odds = build_walk_forward_odds_calibration(
                output_dir,
                output_dir / "odds_calibration.json",
                OddsCalibrationConfig(bins=3, min_support=10, prior_strength=10),
            )
            latest = predict_latest(source, output_dir)

            self.assertEqual(len(report["timeframes"]["M1"]["fold_metrics"]), 2)
            self.assertIn("aggregate_context_diagnostics", report["timeframes"]["M1"])
            self.assertEqual(latest.loc[0, "timeframe"], "M1")
            self.assertTrue((output_dir / "m1_walk_forward_predictions.parquet").exists())
            self.assertTrue((output_dir / "optimized_policy.json").exists())
            self.assertEqual(
                policy["_meta"]["validation"],
                "nested chronological: prior OOS folds select, next fold evaluates",
            )
            self.assertIn("nested_validation", policy["M1"])
            self.assertTrue((output_dir / "odds_calibration.json").exists())
            self.assertIn("empirical_odds", odds["M1"]["nested_validation"])

    def test_mlp_uses_the_same_processed_feature_pipeline(self):
        source = m1_frame(1800)
        config = TrainConfig(
            timeframes=(1,),
            model_type="mlp",
            max_train_rows=1_000,
            max_iter=2,
            mlp_batch_size=128,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            report = train_all_timeframes(source, output_dir, config)

            self.assertEqual(report["config"]["model_type"], "mlp")
            self.assertTrue((output_dir / "m1_model.joblib").exists())


if __name__ == "__main__":
    unittest.main()
