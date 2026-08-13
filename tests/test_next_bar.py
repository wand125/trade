import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from trade_data.next_bar import (
    AdoptionOptimizationConfig,
    BetaCalibrator,
    CHANGE_POINT_DRIFT,
    CHANGE_POINT_REFERENCE_WINDOW,
    CHANGE_POINT_SCORE_CAP,
    SHOCK_RESPONSE_CAP,
    SHOCK_TRACKING_BARS,
    SHOCK_Z_THRESHOLD,
    INTRABAR_FULL_PATH_GRID_POINTS,
    INTRABAR_PATH_SIGNATURE_COLUMNS,
    OddsCalibrationConfig,
    RECENCY_WEIGHT_HALF_LIFE_DAYS,
    TemperatureCalibrator,
    TrainConfig,
    VolatilityRegimeHGBClassifier,
    WalkForwardFold,
    build_labeled_dataset,
    build_walk_forward_odds_calibration,
    build_feature_frame,
    calibrate_prediction_odds,
    chronological_split,
    evaluate_probabilities,
    evaluate_adoption_rule,
    evaluate_context_rule,
    filter_training_targets,
    fit_context_confidence_model,
    fit_direction_confidence_calibrator,
    fit_beta_calibrator,
    fit_empirical_odds_calibrator,
    fit_isotonic_calibrator,
    fit_temperature_calibrator,
    intrabar_path_signature,
    model_training_target,
    optimize_adoption_rule,
    optimize_walk_forward_policy,
    predict_latest,
    parse_walk_forward_fold,
    resample_complete_bars,
    train_all_timeframes,
    training_sample_weights,
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
    def test_volatility_regime_hgb_fixes_train_quantiles_and_routes_all_rows(self):
        rows = 300
        values = pd.DataFrame(
            {
                "volatility_20": np.linspace(0.001, 0.030, rows),
                "signal": np.sin(np.arange(rows) / 5.0),
            }
        )
        labels = pd.Series(np.arange(rows) % 2, dtype="int8")
        model = VolatilityRegimeHGBClassifier(
            max_iter=5,
            learning_rate=0.05,
            max_leaf_nodes=7,
            min_samples_leaf=5,
            l2_regularization=1.0,
            random_state=42,
        )

        model.fit(values, labels)
        probabilities = model.predict_proba(values.iloc[[0, 100, 200, 299]])

        self.assertEqual(set(model.models_), {"low", "normal", "high"})
        self.assertEqual(sum(model.regime_counts_.values()), rows)
        self.assertEqual(probabilities.shape, (4, 2))
        np.testing.assert_allclose(probabilities.sum(axis=1), 1.0)
        self.assertAlmostEqual(
            float(model.low_threshold_),
            float(values["volatility_20"].quantile(1 / 3)),
        )

    def test_body_atr_training_weights_are_bounded_and_mean_normalized(self):
        frame = pd.DataFrame({"next_bar_body_atr": [0.0, 0.5, 1.5, 3.0]})

        weights = training_sample_weights(frame, "body_atr")

        assert weights is not None
        self.assertAlmostEqual(float(weights.mean()), 1.0)
        self.assertAlmostEqual(float(weights[-1]), float(weights[-2]))
        self.assertAlmostEqual(float(weights[-1] / weights[0]), 4.0)

    def test_directional_clarity_weights_are_bounded_and_run_training_pipeline(self):
        frame = pd.DataFrame(
            {"next_bar_directional_clarity": [0.0, 0.25, 0.5, 1.0]}
        )
        weights = training_sample_weights(frame, "directional_clarity")

        assert weights is not None
        self.assertAlmostEqual(float(weights.mean()), 1.0)
        self.assertAlmostEqual(float(weights[-1] / weights[0]), 3.0)

        source = m1_frame(1800)
        config = TrainConfig(
            timeframes=(1,),
            train_weighting="directional_clarity",
            max_train_rows=1_000,
            max_iter=5,
            min_samples_leaf=10,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            report = train_all_timeframes(source, output_dir, config)
            latest = predict_latest(source, output_dir)
            manifest = json.loads(
                (output_dir / "manifest.json").read_text(encoding="utf-8")
            )

        metrics = report["timeframes"]["M1"]
        self.assertEqual(metrics["train_weighting"], "directional_clarity")
        self.assertAlmostEqual(metrics["train_sample_weight"]["mean"], 1.0)
        self.assertNotIn(
            "next_bar_directional_clarity",
            manifest["timeframes"]["M1"]["features"],
        )
        self.assertTrue(latest["probability_up"].between(0, 1).all())

    def test_directional_follow_through_weights_are_bounded_and_run_pipeline(self):
        frame = pd.DataFrame(
            {"next_bar_directional_follow_through": [0.0, 0.25, 0.5, 1.0]}
        )
        weights = training_sample_weights(frame, "directional_follow_through")

        assert weights is not None
        self.assertAlmostEqual(float(weights.mean()), 1.0)
        self.assertAlmostEqual(float(weights[-1] / weights[0]), 3.0)

        source = m1_frame(1800)
        config = TrainConfig(
            timeframes=(1,),
            train_weighting="directional_follow_through",
            max_train_rows=1_000,
            max_iter=5,
            min_samples_leaf=10,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            report = train_all_timeframes(source, output_dir, config)
            latest = predict_latest(source, output_dir)
            manifest = json.loads(
                (output_dir / "manifest.json").read_text(encoding="utf-8")
            )

        metrics = report["timeframes"]["M1"]
        self.assertEqual(metrics["train_weighting"], "directional_follow_through")
        self.assertAlmostEqual(metrics["train_sample_weight"]["mean"], 1.0)
        self.assertNotIn(
            "next_bar_directional_follow_through",
            manifest["timeframes"]["M1"]["features"],
        )
        self.assertTrue(latest["probability_up"].between(0, 1).all())

    def test_recency_weights_use_only_training_timestamps_and_run_pipeline(self):
        frame = pd.DataFrame(
            {
                "decision_timestamp": pd.to_datetime(
                    ["2020-01-03", "2022-01-02", "2024-01-02"],
                    utc=True,
                )
            }
        )
        weights = training_sample_weights(frame, "recency_half_life_730d")

        assert weights is not None
        self.assertEqual(RECENCY_WEIGHT_HALF_LIFE_DAYS, 730.0)
        self.assertAlmostEqual(float(weights.mean()), 1.0)
        self.assertAlmostEqual(float(weights[2] / weights[1]), 2.0, places=12)
        self.assertAlmostEqual(float(weights[2] / weights[0]), 4.0, places=12)
        with self.assertRaisesRegex(ValueError, "decision_timestamp"):
            training_sample_weights(pd.DataFrame({"other": [1]}), "recency_half_life_730d")

        source = m1_frame(1800)
        config = TrainConfig(
            timeframes=(1,),
            train_weighting="recency_half_life_730d",
            max_train_rows=1_000,
            max_iter=5,
            min_samples_leaf=10,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            report = train_all_timeframes(source, output_dir, config)
            latest = predict_latest(source, output_dir)

        metrics = report["timeframes"]["M1"]
        self.assertEqual(metrics["train_weighting"], "recency_half_life_730d")
        self.assertAlmostEqual(metrics["train_sample_weight"]["mean"], 1.0)
        self.assertLess(
            metrics["train_sample_weight"]["minimum"],
            metrics["train_sample_weight"]["maximum"],
        )
        self.assertTrue(latest["probability_up"].between(0, 1).all())

    def test_body_atr_upper_half_filter_uses_train_median_only(self):
        frame = pd.DataFrame(
            {
                "target_up": [0, 1, 0, 1],
                "next_bar_body_atr": [0.1, 0.2, 0.3, 0.4],
            }
        )
        filtered, diagnostics = filter_training_targets(
            frame, "body_atr_upper_half"
        )

        self.assertEqual(filtered.index.tolist(), [2, 3])
        self.assertAlmostEqual(diagnostics["body_atr_threshold"], 0.25)
        self.assertEqual(diagnostics["input_rows"], 4)
        self.assertEqual(diagnostics["output_rows"], 2)

    def test_body_range_upper_half_filter_uses_train_median_only(self):
        frame = pd.DataFrame(
            {
                "target_up": [0, 1, 0, 1],
                "next_bar_directional_clarity": [0.1, 0.2, 0.3, 0.4],
            }
        )

        filtered, diagnostics = filter_training_targets(
            frame, "body_range_upper_half"
        )

        self.assertEqual(filtered.index.tolist(), [2, 3])
        self.assertAlmostEqual(diagnostics["directional_clarity_threshold"], 0.25)
        self.assertIsNone(diagnostics["body_atr_threshold"])
        self.assertEqual(diagnostics["input_rows"], 4)
        self.assertEqual(diagnostics["output_rows"], 2)

    def test_body_range_upper_half_filter_runs_training_and_latest_prediction(self):
        source = m1_frame(1800)
        config = TrainConfig(
            timeframes=(1,),
            train_target_filter="body_range_upper_half",
            max_train_rows=1_000,
            max_iter=5,
            min_samples_leaf=10,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            report = train_all_timeframes(source, output_dir, config)
            latest = predict_latest(source, output_dir)
            manifest = json.loads(
                (output_dir / "manifest.json").read_text(encoding="utf-8")
            )

        diagnostics = report["timeframes"]["M1"]["train_target_filter"]
        self.assertEqual(diagnostics["mode"], "body_range_upper_half")
        self.assertLess(diagnostics["output_rows"], diagnostics["input_rows"])
        self.assertGreaterEqual(diagnostics["directional_clarity_threshold"], 0)
        self.assertLessEqual(diagnostics["directional_clarity_threshold"], 1)
        self.assertNotIn(
            "next_bar_directional_clarity",
            manifest["timeframes"]["M1"]["features"],
        )
        self.assertTrue(latest["probability_up"].between(0, 1).all())

    def test_body_atr_upper_half_filter_runs_training_and_latest_prediction(self):
        source = m1_frame(1800)
        config = TrainConfig(
            timeframes=(1,),
            train_target_filter="body_atr_upper_half",
            max_train_rows=1_000,
            max_iter=5,
            min_samples_leaf=10,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            report = train_all_timeframes(source, output_dir, config)
            latest = predict_latest(source, output_dir)

        diagnostics = report["timeframes"]["M1"]["train_target_filter"]
        self.assertEqual(diagnostics["mode"], "body_atr_upper_half")
        self.assertLess(diagnostics["output_rows"], diagnostics["input_rows"])
        self.assertGreater(diagnostics["body_atr_threshold"], 0)
        self.assertTrue(latest["probability_up"].between(0, 1).all())

    def test_body_atr_weighting_runs_hgb_training_pipeline(self):
        source = m1_frame(1800)
        config = TrainConfig(
            timeframes=(1,),
            train_weighting="body_atr",
            max_train_rows=1_000,
            max_iter=5,
            min_samples_leaf=10,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            report = train_all_timeframes(source, output_dir, config)
            manifest = json.loads(
                (output_dir / "manifest.json").read_text(encoding="utf-8")
            )

        metrics = report["timeframes"]["M1"]
        self.assertEqual(metrics["train_weighting"], "body_atr")
        self.assertAlmostEqual(metrics["train_sample_weight"]["mean"], 1.0)
        self.assertNotIn(
            "next_bar_body_atr", manifest["timeframes"]["M1"]["features"]
        )

    def test_isotonic_calibrator_is_monotone_and_clips_out_of_bounds(self):
        calibrator = fit_isotonic_calibrator(
            np.array([0, 0, 1, 0, 1, 1], dtype="int8"),
            np.array([0.10, 0.20, 0.40, 0.60, 0.80, 0.90]),
        )

        calibrated = calibrator.predict(np.array([-1.0, 0.15, 0.50, 0.85, 2.0]))

        self.assertTrue(np.all(np.diff(calibrated) >= 0))
        self.assertGreater(calibrated.min(), 0)
        self.assertLess(calibrated.max(), 1)

    def test_isotonic_probability_calibration_runs_the_prediction_pipeline(self):
        source = m1_frame(1800)
        config = TrainConfig(
            timeframes=(1,),
            probability_calibration="isotonic",
            max_train_rows=1_000,
            max_iter=5,
            min_samples_leaf=10,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            report = train_all_timeframes(source, output_dir, config)
            latest = predict_latest(source, output_dir)
            manifest = json.loads(
                (output_dir / "manifest.json").read_text(encoding="utf-8")
            )

        self.assertEqual(report["config"]["probability_calibration"], "isotonic")
        self.assertEqual(
            report["timeframes"]["M1"]["probability_calibrator"]["method"],
            "isotonic",
        )
        self.assertTrue(latest["probability_up"].between(0, 1).all())

    def test_beta_calibrator_is_monotone_and_runs_prediction_pipeline(self):
        raw = np.linspace(0.02, 0.98, 400)
        labels = (np.sin(np.arange(400) / 7.0) + raw * 2 > 1).astype("int8")
        calibrator = fit_beta_calibrator(labels, raw)
        self.assertIsInstance(calibrator, BetaCalibrator)
        self.assertGreaterEqual(calibrator.log_probability_coefficient, 0)
        self.assertGreaterEqual(
            calibrator.negative_log_complement_coefficient, 0
        )
        calibrated = calibrator.predict(raw)
        self.assertTrue(np.all(np.diff(calibrated) >= 0))

        source = m1_frame(1800)
        config = TrainConfig(
            timeframes=(1,),
            probability_calibration="beta",
            max_train_rows=1_000,
            max_iter=5,
            min_samples_leaf=10,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            report = train_all_timeframes(source, output_dir, config)
            latest = predict_latest(source, output_dir)

        self.assertEqual(report["config"]["probability_calibration"], "beta")
        self.assertEqual(
            report["timeframes"]["M1"]["probability_calibrator"]["method"],
            "beta",
        )
        self.assertTrue(latest["probability_up"].between(0, 1).all())

    def test_temperature_calibrator_preserves_direction_and_runs_pipeline(self):
        raw = np.linspace(0.02, 0.98, 400)
        labels = (np.sin(np.arange(400) / 9.0) + raw * 2 > 1).astype("int8")
        calibrator = fit_temperature_calibrator(labels, raw)
        self.assertIsInstance(calibrator, TemperatureCalibrator)
        self.assertGreater(calibrator.temperature, 0)
        calibrated = calibrator.predict(raw)
        self.assertTrue(np.all(np.diff(calibrated) >= 0))
        np.testing.assert_array_equal(calibrated >= 0.5, raw >= 0.5)

        source = m1_frame(1800)
        config = TrainConfig(
            timeframes=(1,),
            probability_calibration="temperature",
            max_train_rows=1_000,
            max_iter=5,
            min_samples_leaf=10,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            report = train_all_timeframes(source, output_dir, config)
            latest = predict_latest(source, output_dir)

        self.assertEqual(report["config"]["probability_calibration"], "temperature")
        self.assertEqual(
            report["timeframes"]["M1"]["probability_calibrator"]["method"],
            "temperature",
        )
        self.assertTrue(latest["probability_up"].between(0, 1).all())

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

    def test_trend_structure_features_are_stationary_causal_and_run_latest(self):
        source = m1_frame(1800)
        bars = resample_complete_bars(source, 1)
        frame, feature_columns = build_feature_frame(bars, 1, "trend_structure")
        trend_columns = [
            name
            for name in feature_columns
            if name
            in {
                "plus_di_14",
                "minus_di_14",
                "adx_14",
                "di_balance_14",
                "adx_change_3",
                "macd_atr_20",
                "macd_signal_gap_atr_20",
                "atr_compression_5_20",
                "volatility_ratio_5_20",
                "realized_volatility_balance_20",
                "direction_entropy_20",
            }
        ]
        self.assertEqual(len(trend_columns), 11)
        validate_stationary_feature_set(feature_columns)
        self.assertFalse({"open", "high", "low", "close"}.intersection(feature_columns))

        changed = source.copy()
        for column in ["open", "high", "low", "close"]:
            changed.loc[changed.index >= 200, column] += 100.0
        changed_bars = resample_complete_bars(changed, 1)
        changed_frame, changed_columns = build_feature_frame(
            changed_bars, 1, "trend_structure"
        )
        self.assertEqual(feature_columns, changed_columns)
        pd.testing.assert_frame_equal(
            frame.loc[:199, trend_columns],
            changed_frame.loc[:199, trend_columns],
        )

        flat_source = m1_frame(200)
        for column in ("open", "high", "low", "close"):
            flat_source[column] = 100.0
        flat_frame, _ = build_feature_frame(
            resample_complete_bars(flat_source, 1), 1, "trend_structure"
        )
        self.assertTrue(
            np.isfinite(flat_frame.loc[100:, trend_columns]).all().all()
        )
        self.assertTrue(flat_frame.loc[100:, trend_columns].eq(0).all().all())

        config = TrainConfig(
            timeframes=(1,),
            feature_set="trend_structure",
            max_train_rows=1_000,
            max_iter=5,
            min_samples_leaf=10,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            report = train_all_timeframes(source, output_dir, config)
            latest = predict_latest(source, output_dir)

        self.assertEqual(report["config"]["feature_set"], "trend_structure")
        self.assertTrue(latest["probability_up"].between(0, 1).all())

    def test_volatility_state_features_are_stationary_causal_finite_and_run_latest(self):
        source = m1_frame(1800)
        bars = resample_complete_bars(source, 1)
        frame, feature_columns = build_feature_frame(bars, 1, "volatility_state")
        state_columns = [
            "volatility_of_volatility_5_20",
            "volatility_of_volatility_5_50",
            "volatility_acceleration_5_3",
            "volatility_acceleration_20_5",
            "range_coefficient_of_variation_20",
            "range_autocorrelation_20",
            "range_median_deviation_20",
            "range_compression_fraction_5_50",
            "jump_variation_fraction_20",
            "parkinson_close_variance_balance_20",
            "garman_klass_close_variance_balance_20",
        ]
        self.assertTrue(set(state_columns).issubset(feature_columns))
        self.assertEqual(len(feature_columns), 49)
        self.assertTrue(
            np.isfinite(frame[state_columns].dropna().to_numpy()).all()
        )
        for column in (
            "volatility_acceleration_5_3",
            "volatility_acceleration_20_5",
            "range_median_deviation_20",
            "jump_variation_fraction_20",
            "parkinson_close_variance_balance_20",
            "garman_klass_close_variance_balance_20",
        ):
            self.assertTrue(frame[column].dropna().between(-1, 1).all())
        validate_stationary_feature_set(feature_columns)

        scaled = source.copy()
        for column in ("open", "high", "low", "close"):
            scaled[column] *= 10
        scaled_frame, scaled_columns = build_feature_frame(
            resample_complete_bars(scaled, 1), 1, "volatility_state"
        )
        self.assertEqual(feature_columns, scaled_columns)
        np.testing.assert_allclose(
            frame[state_columns],
            scaled_frame[state_columns],
            rtol=1e-8,
            atol=1e-10,
            equal_nan=True,
        )

        changed = source.copy()
        for column in ("open", "high", "low", "close"):
            changed.loc[changed.index >= 200, column] += 100.0
        changed_frame, changed_columns = build_feature_frame(
            resample_complete_bars(changed, 1), 1, "volatility_state"
        )
        self.assertEqual(feature_columns, changed_columns)
        pd.testing.assert_frame_equal(
            frame.loc[:199, state_columns],
            changed_frame.loc[:199, state_columns],
        )

        flat_source = m1_frame(200)
        for column in ("open", "high", "low", "close"):
            flat_source[column] = 100.0
        flat_frame, _ = build_feature_frame(
            resample_complete_bars(flat_source, 1), 1, "volatility_state"
        )
        self.assertTrue(np.isfinite(flat_frame.loc[100:, state_columns]).all().all())
        self.assertTrue(flat_frame.loc[100:, state_columns].eq(0).all().all())

        config = TrainConfig(
            timeframes=(1,),
            feature_set="volatility_state",
            max_train_rows=1_000,
            max_iter=5,
            min_samples_leaf=10,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            report = train_all_timeframes(source, output_dir, config)
            latest = predict_latest(source, output_dir)

        self.assertEqual(report["config"]["feature_set"], "volatility_state")
        self.assertTrue(latest["probability_up"].between(0, 1).all())

    def test_candle_pressure_state_features_are_stationary_causal_finite_and_run_latest(self):
        source = m1_frame(1800)
        bars = resample_complete_bars(source, 1)
        frame, feature_columns = build_feature_frame(
            bars, 1, "candle_pressure_state"
        )
        pressure_columns = [
            name
            for name in feature_columns
            if name.startswith(
                (
                    "body_pressure_",
                    "wick_pressure_",
                    "close_pressure_",
                    "range_weighted_body_pressure_",
                    "range_weighted_wick_pressure_",
                )
            )
        ]
        self.assertEqual(len(pressure_columns), 18)
        self.assertEqual(len(feature_columns), 56)
        validate_stationary_feature_set(feature_columns)
        self.assertFalse({"open", "high", "low", "close"}.intersection(feature_columns))
        self.assertTrue(
            np.isfinite(frame[pressure_columns].dropna().to_numpy()).all()
        )
        self.assertTrue(
            frame[pressure_columns].dropna().to_numpy().min() >= -2.0
        )
        self.assertTrue(
            frame[pressure_columns].dropna().to_numpy().max() <= 2.0
        )

        scaled = source.copy()
        for column in ("open", "high", "low", "close"):
            scaled[column] *= 10
        scaled_frame, scaled_columns = build_feature_frame(
            resample_complete_bars(scaled, 1), 1, "candle_pressure_state"
        )
        self.assertEqual(feature_columns, scaled_columns)
        np.testing.assert_allclose(
            frame[pressure_columns],
            scaled_frame[pressure_columns],
            rtol=1e-8,
            atol=1e-10,
            equal_nan=True,
        )

        changed = source.copy()
        for column in ("open", "high", "low", "close"):
            changed.loc[changed.index >= 200, column] += 100.0
        changed_frame, changed_columns = build_feature_frame(
            resample_complete_bars(changed, 1), 1, "candle_pressure_state"
        )
        self.assertEqual(feature_columns, changed_columns)
        pd.testing.assert_frame_equal(
            frame.loc[:199, pressure_columns],
            changed_frame.loc[:199, pressure_columns],
        )

        flat_source = m1_frame(200)
        for column in ("open", "high", "low", "close"):
            flat_source[column] = 100.0
        flat_frame, _ = build_feature_frame(
            resample_complete_bars(flat_source, 1), 1, "candle_pressure_state"
        )
        self.assertTrue(
            np.isfinite(flat_frame.loc[100:, pressure_columns]).all().all()
        )
        self.assertTrue(flat_frame.loc[100:, pressure_columns].eq(0).all().all())

        config = TrainConfig(
            timeframes=(1,),
            feature_set="candle_pressure_state",
            max_train_rows=1_000,
            max_iter=5,
            min_samples_leaf=10,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            report = train_all_timeframes(source, output_dir, config)
            latest = predict_latest(source, output_dir)

        self.assertEqual(report["config"]["feature_set"], "candle_pressure_state")
        self.assertTrue(latest["probability_up"].between(0, 1).all())

    def test_bar_breakout_rejection_features_are_stationary_causal_finite_and_run_latest(self):
        source = m1_frame(1800)
        bars = resample_complete_bars(source, 1)
        frame, feature_columns = build_feature_frame(
            bars, 1, "bar_breakout_rejection"
        )
        state_columns = [
            name
            for name in feature_columns
            if name.startswith(
                (
                    "close_breakout_",
                    "high_rejection_",
                    "low_rejection_",
                    "inside_previous_bar",
                    "outside_previous_bar",
                    "upward_range_expansion",
                    "downward_range_expansion",
                    "close_distance_to_prior_",
                )
            )
        ]
        self.assertEqual(len(state_columns), 18)
        self.assertEqual(len(feature_columns), 56)
        validate_stationary_feature_set(feature_columns)
        self.assertFalse({"open", "high", "low", "close"}.intersection(feature_columns))
        self.assertTrue(np.isfinite(frame[state_columns].dropna().to_numpy()).all())
        for column in state_columns:
            if "distance" not in column:
                self.assertTrue(frame[column].dropna().isin([0.0, 1.0]).all())

        scaled = source.copy()
        for column in ("open", "high", "low", "close"):
            scaled[column] *= 10
        scaled_frame, scaled_columns = build_feature_frame(
            resample_complete_bars(scaled, 1), 1, "bar_breakout_rejection"
        )
        self.assertEqual(feature_columns, scaled_columns)
        np.testing.assert_allclose(
            frame[state_columns],
            scaled_frame[state_columns],
            rtol=1e-8,
            atol=1e-10,
            equal_nan=True,
        )

        changed = source.copy()
        for column in ("open", "high", "low", "close"):
            changed.loc[changed.index >= 200, column] += 100.0
        changed_frame, changed_columns = build_feature_frame(
            resample_complete_bars(changed, 1), 1, "bar_breakout_rejection"
        )
        self.assertEqual(feature_columns, changed_columns)
        pd.testing.assert_frame_equal(
            frame.loc[:199, state_columns],
            changed_frame.loc[:199, state_columns],
        )

        flat_source = m1_frame(200)
        for column in ("open", "high", "low", "close"):
            flat_source[column] = 100.0
        flat_frame, _ = build_feature_frame(
            resample_complete_bars(flat_source, 1), 1, "bar_breakout_rejection"
        )
        self.assertTrue(np.isfinite(flat_frame.loc[100:, state_columns]).all().all())
        self.assertTrue(flat_frame.loc[100:, state_columns].eq(0).all().all())

        config = TrainConfig(
            timeframes=(1,),
            feature_set="bar_breakout_rejection",
            max_train_rows=1_000,
            max_iter=5,
            min_samples_leaf=10,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            report = train_all_timeframes(source, output_dir, config)
            latest = predict_latest(source, output_dir)

        self.assertEqual(report["config"]["feature_set"], "bar_breakout_rejection")
        self.assertTrue(latest["probability_up"].between(0, 1).all())

    def test_distribution_shift_features_are_stationary_causal_finite_and_run_latest(self):
        source = m1_frame(1800)
        bars = resample_complete_bars(source, 1)
        frame, feature_columns = build_feature_frame(
            bars, 1, "distribution_shift"
        )
        shift_columns = [
            name
            for name in feature_columns
            if name.startswith("distribution_shift_")
        ]
        self.assertEqual(len(shift_columns), 16)
        self.assertEqual(len(feature_columns), 54)
        validate_stationary_feature_set(feature_columns)
        self.assertFalse(
            {"open", "high", "low", "close"}.intersection(feature_columns)
        )
        self.assertTrue(np.isfinite(frame[shift_columns].dropna()).all().all())
        bounded_columns = [
            name
            for name in shift_columns
            if name != "distribution_shift_return_location_8_64"
        ]
        self.assertTrue(
            frame[bounded_columns].dropna().to_numpy().min() >= -1.0
        )
        self.assertTrue(
            frame[bounded_columns].dropna().to_numpy().max() <= 1.0
        )

        scaled = source.copy()
        for column in ("open", "high", "low", "close"):
            scaled[column] *= 10
        scaled_frame, scaled_columns = build_feature_frame(
            resample_complete_bars(scaled, 1), 1, "distribution_shift"
        )
        self.assertEqual(feature_columns, scaled_columns)
        np.testing.assert_allclose(
            frame[shift_columns],
            scaled_frame[shift_columns],
            rtol=1e-8,
            atol=1e-10,
            equal_nan=True,
        )

        changed = source.copy()
        for column in ("open", "high", "low", "close"):
            changed.loc[changed.index >= 300, column] += 100.0
        changed_frame, changed_columns = build_feature_frame(
            resample_complete_bars(changed, 1), 1, "distribution_shift"
        )
        self.assertEqual(feature_columns, changed_columns)
        pd.testing.assert_frame_equal(
            frame.loc[:299, shift_columns],
            changed_frame.loc[:299, shift_columns],
        )

        flat_source = m1_frame(320)
        for column in ("open", "high", "low", "close"):
            flat_source[column] = 100.0
        flat_frame, _ = build_feature_frame(
            resample_complete_bars(flat_source, 1), 1, "distribution_shift"
        )
        self.assertTrue(
            np.isfinite(flat_frame.loc[200:, shift_columns]).all().all()
        )
        self.assertTrue(flat_frame.loc[200:, shift_columns].eq(0).all().all())

        config = TrainConfig(
            timeframes=(1,),
            feature_set="distribution_shift",
            max_train_rows=1_000,
            max_iter=5,
            min_samples_leaf=10,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            report = train_all_timeframes(source, output_dir, config)
            latest = predict_latest(source, output_dir)

        self.assertEqual(report["config"]["feature_set"], "distribution_shift")
        self.assertTrue(latest["probability_up"].between(0, 1).all())

    def test_distribution_shift_features_transfer_to_m5(self):
        source = m1_frame(1800)
        bars = resample_complete_bars(source, 5)
        frame, feature_columns = build_feature_frame(
            bars, 5, "distribution_shift"
        )
        shift_columns = [
            name
            for name in feature_columns
            if name.startswith("distribution_shift_")
        ]

        self.assertEqual(len(shift_columns), 16)
        self.assertEqual(len(feature_columns), 54)
        validate_stationary_feature_set(feature_columns)
        self.assertFalse(
            {"open", "high", "low", "close"}.intersection(feature_columns)
        )
        self.assertGreater(len(frame[shift_columns].dropna()), 0)
        self.assertTrue(np.isfinite(frame[shift_columns].dropna()).all().all())

    def test_distribution_shift_features_transfer_to_m15(self):
        source = m1_frame(3600)
        bars = resample_complete_bars(source, 15)
        frame, feature_columns = build_feature_frame(
            bars, 15, "distribution_shift"
        )
        shift_columns = [
            name
            for name in feature_columns
            if name.startswith("distribution_shift_")
        ]

        self.assertEqual(len(shift_columns), 16)
        self.assertEqual(len(feature_columns), 54)
        validate_stationary_feature_set(feature_columns)
        self.assertFalse(
            {"open", "high", "low", "close"}.intersection(feature_columns)
        )
        self.assertGreater(len(frame[shift_columns].dropna()), 0)
        self.assertTrue(np.isfinite(frame[shift_columns].dropna()).all().all())

    def test_distribution_shift_features_transfer_to_m30(self):
        source = m1_frame(7200)
        bars = resample_complete_bars(source, 30)
        frame, feature_columns = build_feature_frame(
            bars, 30, "distribution_shift"
        )
        shift_columns = [
            name
            for name in feature_columns
            if name.startswith("distribution_shift_")
        ]

        self.assertEqual(len(shift_columns), 16)
        self.assertEqual(len(feature_columns), 54)
        validate_stationary_feature_set(feature_columns)
        self.assertFalse(
            {"open", "high", "low", "close"}.intersection(feature_columns)
        )
        self.assertGreater(len(frame[shift_columns].dropna()), 0)
        self.assertTrue(np.isfinite(frame[shift_columns].dropna()).all().all())

    def test_liquidity_friction_is_stationary_causal_bounded_and_runs_latest(self):
        source = m1_frame(1800)
        bars = resample_complete_bars(source, 1)
        frame, feature_columns = build_feature_frame(
            bars, 1, "liquidity_friction"
        )
        liquidity_columns = [
            name for name in feature_columns if name.startswith("liquidity_")
        ]

        self.assertEqual(len(liquidity_columns), 10)
        self.assertEqual(len(feature_columns), 48)
        validate_stationary_feature_set(feature_columns)
        self.assertFalse(
            {"open", "high", "low", "close"}.intersection(feature_columns)
        )
        finite = frame[liquidity_columns].dropna()
        self.assertGreater(len(finite), 0)
        self.assertTrue(np.isfinite(finite).all().all())
        self.assertGreaterEqual(float(finite.to_numpy().min()), 0.0)
        self.assertLessEqual(float(finite.to_numpy().max()), 1.0)

        scaled = source.copy()
        for column in ("open", "high", "low", "close"):
            scaled[column] *= 10
        scaled_frame, scaled_columns = build_feature_frame(
            resample_complete_bars(scaled, 1), 1, "liquidity_friction"
        )
        self.assertEqual(feature_columns, scaled_columns)
        np.testing.assert_allclose(
            frame[liquidity_columns],
            scaled_frame[liquidity_columns],
            rtol=1e-8,
            atol=1e-10,
            equal_nan=True,
        )

        changed = source.copy()
        for column in ("open", "high", "low", "close"):
            changed.loc[changed.index >= 300, column] += 100.0
        changed_frame, changed_columns = build_feature_frame(
            resample_complete_bars(changed, 1), 1, "liquidity_friction"
        )
        self.assertEqual(feature_columns, changed_columns)
        pd.testing.assert_frame_equal(
            frame.loc[:299, liquidity_columns],
            changed_frame.loc[:299, liquidity_columns],
        )

        target = len(bars) - 1
        log_range = np.log(bars["high"] / bars["low"])
        beta = log_range.iloc[target] ** 2 + log_range.iloc[target - 1] ** 2
        pair_high = max(bars.loc[target, "high"], bars.loc[target - 1, "high"])
        pair_low = min(bars.loc[target, "low"], bars.loc[target - 1, "low"])
        gamma = np.log(pair_high / pair_low) ** 2
        denominator = 3.0 - 2.0 * np.sqrt(2.0)
        alpha = max(
            0.0,
            (np.sqrt(2.0 * beta) - np.sqrt(beta)) / denominator
            - np.sqrt(gamma / denominator),
        )
        alpha = min(alpha, 10.0)
        expected_spread = 2.0 * np.expm1(alpha) / (2.0 + np.expm1(alpha))
        self.assertAlmostEqual(
            float(frame.loc[target, "liquidity_corwin_schultz_spread_pair"]),
            expected_spread,
            places=12,
        )

        flat_source = m1_frame(400)
        for column in ("open", "high", "low", "close"):
            flat_source[column] = 100.0
        flat_frame, _ = build_feature_frame(
            resample_complete_bars(flat_source, 1), 1, "liquidity_friction"
        )
        self.assertTrue(
            np.isfinite(flat_frame.loc[220:, liquidity_columns]).all().all()
        )
        self.assertTrue(flat_frame.loc[220:, liquidity_columns].eq(0).all().all())

        gapped = bars.copy()
        gapped.loc[gapped.index >= 300, "timestamp"] += pd.Timedelta(minutes=5)
        gapped_frame, _ = build_feature_frame(gapped, 1, "liquidity_friction")
        self.assertEqual(
            float(
                gapped_frame.loc[
                    300, "liquidity_corwin_schultz_spread_pair"
                ]
            ),
            0.0,
        )

        config = TrainConfig(
            timeframes=(1,),
            feature_set="liquidity_friction",
            max_train_rows=1_000,
            max_iter=5,
            min_samples_leaf=10,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            report = train_all_timeframes(source, output_dir, config)
            latest = predict_latest(source, output_dir)

        self.assertEqual(report["config"]["feature_set"], "liquidity_friction")
        self.assertTrue(latest["probability_up"].between(0, 1).all())

    def test_ewma_asymmetry_state_is_causal_bounded_gap_safe_and_runs_latest(self):
        source = m1_frame(1800)
        bars = resample_complete_bars(source, 1)
        frame, feature_columns = build_feature_frame(
            bars, 1, "ewma_asymmetry_state"
        )
        ewma_columns = [
            name for name in feature_columns if name.startswith("ewma_")
        ]

        self.assertEqual(len(ewma_columns), 12)
        self.assertEqual(len(feature_columns), 50)
        validate_stationary_feature_set(feature_columns)
        self.assertFalse(
            {"open", "high", "low", "close"}.intersection(feature_columns)
        )
        self.assertTrue(np.isfinite(frame[ewma_columns]).all().all())
        self.assertGreaterEqual(float(frame[ewma_columns].to_numpy().min()), -1.0)
        self.assertLessEqual(float(frame[ewma_columns].to_numpy().max()), 1.0)

        scaled = source.copy()
        for column in ("open", "high", "low", "close"):
            scaled[column] *= 10
        scaled_frame, scaled_columns = build_feature_frame(
            resample_complete_bars(scaled, 1), 1, "ewma_asymmetry_state"
        )
        self.assertEqual(feature_columns, scaled_columns)
        np.testing.assert_allclose(
            frame[ewma_columns],
            scaled_frame[ewma_columns],
            rtol=1e-8,
            atol=1e-10,
        )

        changed = source.copy()
        for column in ("open", "high", "low", "close"):
            changed.loc[changed.index >= 300, column] += 100.0
        changed_frame, changed_columns = build_feature_frame(
            resample_complete_bars(changed, 1), 1, "ewma_asymmetry_state"
        )
        self.assertEqual(feature_columns, changed_columns)
        pd.testing.assert_frame_equal(
            frame.loc[:299, ewma_columns],
            changed_frame.loc[:299, ewma_columns],
        )

        target = 200
        returns = np.log(bars["close"] / bars["close"].shift(1))
        prior_energy = (
            returns.pow(2)
            .ewm(
                halflife=4,
                adjust=False,
                ignore_na=True,
                min_periods=4,
            )
            .mean()
            .iloc[target - 1]
        )
        expected_innovation = np.clip(
            returns.iloc[target] / np.sqrt(prior_energy), -5.0, 5.0
        ) / 5.0
        self.assertAlmostEqual(
            float(frame.loc[target, "ewma_return_innovation_hl4"]),
            float(expected_innovation),
            places=12,
        )

        flat_source = m1_frame(400)
        for column in ("open", "high", "low", "close"):
            flat_source[column] = 100.0
        flat_frame, _ = build_feature_frame(
            resample_complete_bars(flat_source, 1), 1, "ewma_asymmetry_state"
        )
        self.assertTrue(np.isfinite(flat_frame[ewma_columns]).all().all())
        self.assertTrue(flat_frame[ewma_columns].eq(0).all().all())

        gapped = bars.copy()
        gapped.loc[gapped.index >= 300, "timestamp"] += pd.Timedelta(minutes=5)
        gapped_frame, _ = build_feature_frame(gapped, 1, "ewma_asymmetry_state")
        self.assertTrue(gapped_frame.loc[300, ewma_columns].eq(0).all())

        config = TrainConfig(
            timeframes=(1,),
            feature_set="ewma_asymmetry_state",
            max_train_rows=1_000,
            max_iter=5,
            min_samples_leaf=10,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            report = train_all_timeframes(source, output_dir, config)
            latest = predict_latest(source, output_dir)

        self.assertEqual(report["config"]["feature_set"], "ewma_asymmetry_state")
        self.assertTrue(latest["probability_up"].between(0, 1).all())

    def test_ewma_asymmetry_state_features_transfer_to_m15(self):
        source = m1_frame(3600)
        bars = resample_complete_bars(source, 15)
        frame, feature_columns = build_feature_frame(
            bars, 15, "ewma_asymmetry_state"
        )
        ewma_columns = [
            name for name in feature_columns if name.startswith("ewma_")
        ]

        self.assertEqual(len(ewma_columns), 12)
        self.assertEqual(len(feature_columns), 50)
        validate_stationary_feature_set(feature_columns)
        self.assertFalse(
            {"open", "high", "low", "close"}.intersection(feature_columns)
        )
        self.assertGreater(len(frame[ewma_columns].dropna()), 0)
        self.assertTrue(np.isfinite(frame[ewma_columns].dropna()).all().all())
        self.assertGreaterEqual(
            float(frame[ewma_columns].dropna().to_numpy().min()), -1.0
        )
        self.assertLessEqual(
            float(frame[ewma_columns].dropna().to_numpy().max()), 1.0
        )

    def test_ewma_asymmetry_state_features_transfer_to_m30(self):
        source = m1_frame(7200)
        bars = resample_complete_bars(source, 30)
        frame, feature_columns = build_feature_frame(
            bars, 30, "ewma_asymmetry_state"
        )
        ewma_columns = [
            name for name in feature_columns if name.startswith("ewma_")
        ]

        self.assertEqual(len(ewma_columns), 12)
        self.assertEqual(len(feature_columns), 50)
        validate_stationary_feature_set(feature_columns)
        self.assertFalse(
            {"open", "high", "low", "close"}.intersection(feature_columns)
        )
        self.assertGreater(len(frame[ewma_columns].dropna()), 0)
        self.assertTrue(np.isfinite(frame[ewma_columns].dropna()).all().all())
        self.assertGreaterEqual(
            float(frame[ewma_columns].dropna().to_numpy().min()), -1.0
        )
        self.assertLessEqual(
            float(frame[ewma_columns].dropna().to_numpy().max()), 1.0
        )

    def test_rolling_distribution_shape_is_exact_stationary_causal_and_runs_latest(self):
        source = m1_frame(1800)
        bars = resample_complete_bars(source, 1)
        frame, feature_columns = build_feature_frame(
            bars, 1, "rolling_distribution_shape"
        )
        distribution_columns = [
            "rolling_return_quantile_10_rms_64",
            "rolling_return_quantile_25_rms_64",
            "rolling_return_quantile_50_rms_64",
            "rolling_return_quantile_75_rms_64",
            "rolling_return_quantile_90_rms_64",
            "rolling_return_bowley_skew_64",
            "rolling_return_tail_skew_64",
            "rolling_return_central_spread_fraction_64",
            "rolling_return_l1_l2_concentration_64",
        ]
        self.assertTrue(set(distribution_columns).issubset(feature_columns))
        self.assertEqual(len(feature_columns), 47)
        validate_stationary_feature_set(feature_columns)
        self.assertFalse(
            {"open", "high", "low", "close"}.intersection(feature_columns)
        )
        self.assertTrue(np.isfinite(frame[distribution_columns]).all().all())
        self.assertTrue(
            frame["rolling_return_central_spread_fraction_64"].between(0, 1).all()
        )
        self.assertTrue(
            frame["rolling_return_l1_l2_concentration_64"].between(0, 1).all()
        )

        returns = np.log(
            bars["close"].to_numpy(dtype="float64")
            / bars["close"].shift(1).to_numpy(dtype="float64")
        )[-64:]
        return_rms = float(np.sqrt(np.mean(returns * returns)))
        quantiles = np.quantile(returns, [0.10, 0.25, 0.50, 0.75, 0.90])
        np.testing.assert_allclose(
            frame.iloc[-1][distribution_columns[:5]].to_numpy(dtype="float64"),
            quantiles / return_rms,
            rtol=1e-12,
            atol=1e-12,
        )
        self.assertAlmostEqual(
            float(frame.iloc[-1]["rolling_return_l1_l2_concentration_64"]),
            float(np.mean(np.abs(returns)) / return_rms),
            places=12,
        )

        scaled = source.copy()
        for column in ("open", "high", "low", "close"):
            scaled[column] *= 10
        scaled_frame, scaled_columns = build_feature_frame(
            resample_complete_bars(scaled, 1), 1, "rolling_distribution_shape"
        )
        self.assertEqual(feature_columns, scaled_columns)
        np.testing.assert_allclose(
            frame[distribution_columns],
            scaled_frame[distribution_columns],
            rtol=1e-8,
            atol=1e-10,
        )

        changed = source.copy()
        for column in ("open", "high", "low", "close"):
            changed.loc[changed.index >= 300, column] += 100.0
        changed_frame, changed_columns = build_feature_frame(
            resample_complete_bars(changed, 1), 1, "rolling_distribution_shape"
        )
        self.assertEqual(feature_columns, changed_columns)
        pd.testing.assert_frame_equal(
            frame.loc[:299, distribution_columns],
            changed_frame.loc[:299, distribution_columns],
        )

        flat_source = m1_frame(200)
        for column in ("open", "high", "low", "close"):
            flat_source[column] = 100.0
        flat_frame, _ = build_feature_frame(
            resample_complete_bars(flat_source, 1),
            1,
            "rolling_distribution_shape",
        )
        self.assertTrue(
            np.isfinite(flat_frame.loc[100:, distribution_columns]).all().all()
        )
        self.assertTrue(
            flat_frame.loc[100:, distribution_columns].eq(0).all().all()
        )

        config = TrainConfig(
            timeframes=(1,),
            feature_set="rolling_distribution_shape",
            max_train_rows=1_000,
            max_iter=5,
            min_samples_leaf=10,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            report = train_all_timeframes(source, output_dir, config)
            latest = predict_latest(source, output_dir)

        self.assertEqual(
            report["config"]["feature_set"], "rolling_distribution_shape"
        )
        self.assertTrue(latest["probability_up"].between(0, 1).all())

    def test_rolling_distribution_shape_transfers_to_m5_without_scale_or_future_leakage(self):
        source = m1_frame(6000)
        bars = resample_complete_bars(source, 5)
        frame, feature_columns = build_feature_frame(
            bars, 5, "rolling_distribution_shape"
        )
        distribution_columns = [
            "rolling_return_quantile_10_rms_64",
            "rolling_return_quantile_25_rms_64",
            "rolling_return_quantile_50_rms_64",
            "rolling_return_quantile_75_rms_64",
            "rolling_return_quantile_90_rms_64",
            "rolling_return_bowley_skew_64",
            "rolling_return_tail_skew_64",
            "rolling_return_central_spread_fraction_64",
            "rolling_return_l1_l2_concentration_64",
        ]

        self.assertEqual(len(feature_columns), 47)
        self.assertEqual(
            {name for name in feature_columns if name.startswith("rolling_return_")},
            set(distribution_columns),
        )
        validate_stationary_feature_set(feature_columns)
        self.assertFalse(
            {"open", "high", "low", "close"}.intersection(feature_columns)
        )
        self.assertTrue(np.isfinite(frame[distribution_columns]).all().all())
        self.assertTrue(
            frame["rolling_return_central_spread_fraction_64"].between(0, 1).all()
        )
        self.assertTrue(
            frame["rolling_return_l1_l2_concentration_64"].between(0, 1).all()
        )

        returns = np.log(
            bars["close"].to_numpy(dtype="float64")
            / bars["close"].shift(1).to_numpy(dtype="float64")
        )[-64:]
        return_rms = float(np.sqrt(np.mean(returns * returns)))
        quantiles = np.quantile(returns, [0.10, 0.25, 0.50, 0.75, 0.90])
        np.testing.assert_allclose(
            frame.iloc[-1][distribution_columns[:5]].to_numpy(dtype="float64"),
            quantiles / return_rms,
            rtol=1e-12,
            atol=1e-12,
        )
        self.assertAlmostEqual(
            float(frame.iloc[-1]["rolling_return_l1_l2_concentration_64"]),
            float(np.mean(np.abs(returns)) / return_rms),
            places=12,
        )

        scaled = source.copy()
        for column in ("open", "high", "low", "close"):
            scaled[column] *= 10.0
        scaled_frame, scaled_columns = build_feature_frame(
            resample_complete_bars(scaled, 5), 5, "rolling_distribution_shape"
        )
        self.assertEqual(feature_columns, scaled_columns)
        np.testing.assert_allclose(
            frame[distribution_columns],
            scaled_frame[distribution_columns],
            rtol=1e-8,
            atol=1e-10,
        )

        changed = source.copy()
        for column in ("open", "high", "low", "close"):
            changed.loc[changed.index >= 3000, column] += 100.0
        changed_frame, changed_columns = build_feature_frame(
            resample_complete_bars(changed, 5), 5, "rolling_distribution_shape"
        )
        self.assertEqual(feature_columns, changed_columns)
        pd.testing.assert_frame_equal(
            frame.loc[:499, distribution_columns],
            changed_frame.loc[:499, distribution_columns],
        )

        config = TrainConfig(
            timeframes=(5,),
            feature_set="rolling_distribution_shape",
            max_train_rows=1_000,
            max_iter=5,
            min_samples_leaf=10,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            report = train_all_timeframes(source, output_dir, config)
            latest = predict_latest(source, output_dir)

        self.assertEqual(
            report["config"]["feature_set"], "rolling_distribution_shape"
        )
        self.assertEqual(latest["timeframe"].tolist(), ["M5"])
        self.assertTrue(latest["probability_up"].between(0, 1).all())

    def test_rolling_spectral_state_is_exact_stationary_causal_gap_safe_and_runs_latest(self):
        source = m1_frame(1800)
        bars = resample_complete_bars(source, 1)
        frame, feature_columns = build_feature_frame(
            bars, 1, "rolling_spectral_state"
        )
        spectral_columns = [
            name for name in feature_columns if name.startswith("rolling_spectral_")
        ]
        self.assertEqual(len(spectral_columns), 12)
        self.assertEqual(len(feature_columns), 50)
        validate_stationary_feature_set(feature_columns)
        self.assertFalse(
            {"open", "high", "low", "close"}.intersection(feature_columns)
        )
        self.assertTrue(np.isfinite(frame[spectral_columns]).all().all())
        self.assertTrue(
            frame[spectral_columns].to_numpy(dtype="float64").min() >= -1.0
        )
        self.assertTrue(
            frame[spectral_columns].to_numpy(dtype="float64").max() <= 1.0
        )

        returns = np.log(
            bars["close"].to_numpy(dtype="float64")
            / bars["close"].shift(1).to_numpy(dtype="float64")
        )[-64:]
        centered = returns - returns.mean()
        transform = np.fft.fft(centered)
        denominator = 64 * np.sum(centered * centered)
        fractions = 2 * np.abs(transform) ** 2 / denominator
        self.assertAlmostEqual(
            float(frame.iloc[-1]["rolling_spectral_low_fraction_64"]),
            float(fractions[1:3].sum()),
            places=11,
        )
        self.assertAlmostEqual(
            float(frame.iloc[-1]["rolling_spectral_mid_fraction_64"]),
            float(fractions[3:7].sum()),
            places=11,
        )
        for frequency in (1, 2, 4, 8):
            normalization = np.sqrt(2.0 / denominator)
            self.assertAlmostEqual(
                float(frame.iloc[-1][f"rolling_spectral_cos_k{frequency}_64"]),
                float(transform[frequency].real * normalization),
                places=11,
            )
            self.assertAlmostEqual(
                float(frame.iloc[-1][f"rolling_spectral_sin_k{frequency}_64"]),
                float(transform[frequency].imag * normalization),
                places=11,
            )

        scaled = source.copy()
        for column in ("open", "high", "low", "close"):
            scaled[column] *= 10
        scaled_frame, scaled_columns = build_feature_frame(
            resample_complete_bars(scaled, 1), 1, "rolling_spectral_state"
        )
        self.assertEqual(feature_columns, scaled_columns)
        np.testing.assert_allclose(
            frame[spectral_columns],
            scaled_frame[spectral_columns],
            rtol=1e-7,
            atol=1e-9,
        )

        changed = source.copy()
        for column in ("open", "high", "low", "close"):
            changed.loc[changed.index >= 300, column] += 100.0
        changed_frame, changed_columns = build_feature_frame(
            resample_complete_bars(changed, 1), 1, "rolling_spectral_state"
        )
        self.assertEqual(feature_columns, changed_columns)
        pd.testing.assert_frame_equal(
            frame.loc[:299, spectral_columns],
            changed_frame.loc[:299, spectral_columns],
        )

        flat_source = m1_frame(200)
        for column in ("open", "high", "low", "close"):
            flat_source[column] = 100.0
        flat_frame, _ = build_feature_frame(
            resample_complete_bars(flat_source, 1), 1, "rolling_spectral_state"
        )
        self.assertTrue(flat_frame[spectral_columns].eq(0).all().all())

        gapped = bars.iloc[:200].copy()
        gapped.loc[gapped.index >= 100, "timestamp"] += pd.Timedelta(minutes=10)
        gapped_frame, _ = build_feature_frame(gapped, 1, "rolling_spectral_state")
        self.assertTrue(
            gapped_frame.loc[100:163, spectral_columns].eq(0).all().all()
        )

        config = TrainConfig(
            timeframes=(1,),
            feature_set="rolling_spectral_state",
            max_train_rows=1_000,
            max_iter=5,
            min_samples_leaf=10,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            report = train_all_timeframes(source, output_dir, config)
            latest = predict_latest(source, output_dir)

        self.assertEqual(report["config"]["feature_set"], "rolling_spectral_state")
        self.assertTrue(latest["probability_up"].between(0, 1).all())

    def test_rolling_spectral_state_transfers_to_m5(self):
        source = m1_frame(6000)
        bars = resample_complete_bars(source, 5)
        frame, feature_columns = build_feature_frame(
            bars, 5, "rolling_spectral_state"
        )
        spectral_columns = [
            name for name in feature_columns if name.startswith("rolling_spectral_")
        ]

        self.assertEqual(len(feature_columns), 50)
        self.assertEqual(len(spectral_columns), 12)
        validate_stationary_feature_set(feature_columns)
        self.assertFalse(
            {"open", "high", "low", "close"}.intersection(feature_columns)
        )
        usable = frame[spectral_columns].dropna()
        self.assertGreater(len(usable), 0)
        self.assertTrue(np.isfinite(usable).all().all())
        self.assertTrue(
            usable.to_numpy(dtype="float64").min() >= -1.0
        )
        self.assertTrue(
            usable.to_numpy(dtype="float64").max() <= 1.0
        )

        scaled = source.copy()
        for column in ("open", "high", "low", "close"):
            scaled[column] *= 10.0
        scaled_frame, scaled_columns = build_feature_frame(
            resample_complete_bars(scaled, 5), 5, "rolling_spectral_state"
        )
        self.assertEqual(feature_columns, scaled_columns)
        np.testing.assert_allclose(
            frame[spectral_columns],
            scaled_frame[spectral_columns],
            rtol=1e-7,
            atol=3e-9,
            equal_nan=True,
        )

    def test_rolling_ordinal_motif_is_exact_stationary_causal_gap_safe_and_runs_latest(self):
        source = m1_frame(1800)
        bars = resample_complete_bars(source, 1)
        frame, feature_columns = build_feature_frame(
            bars, 1, "rolling_ordinal_motif"
        )
        ordinal_columns = [
            name for name in feature_columns if name.startswith("rolling_ordinal_")
        ]
        self.assertEqual(len(ordinal_columns), 18)
        self.assertEqual(len(feature_columns), 56)
        validate_stationary_feature_set(feature_columns)
        self.assertFalse(
            {"open", "high", "low", "close"}.intersection(feature_columns)
        )
        self.assertTrue(np.isfinite(frame[ordinal_columns]).all().all())
        values = frame[ordinal_columns].to_numpy(dtype="float64")
        self.assertGreaterEqual(values.min(), -1.0)
        self.assertLessEqual(values.max(), 1.0)

        returns = np.log(
            bars["close"].to_numpy(dtype="float64")
            / bars["close"].shift(1).to_numpy(dtype="float64")
        )

        def ordinal_pattern(end: int) -> str:
            sample = returns[end - 2 : end + 1]
            ordered = sorted(range(3), key=lambda position: (sample[position], position))
            ranks = [0, 0, 0]
            for rank, position in enumerate(ordered):
                ranks[position] = rank
            return "".join(str(rank) for rank in ranks)

        patterns = ("012", "021", "102", "120", "201", "210")
        target = len(bars) - 1
        expected_entropy = {}
        expected_current_frequency = {}
        for window in (32, 128):
            observed = [
                ordinal_pattern(end)
                for end in range(target - window + 1, target + 1)
            ]
            fractions = {
                pattern: observed.count(pattern) / window for pattern in patterns
            }
            for pattern, fraction in fractions.items():
                self.assertAlmostEqual(
                    float(
                        frame.iloc[-1][
                            f"rolling_ordinal_{pattern}_fraction_{window}"
                        ]
                    ),
                    fraction,
                    places=12,
                )
            entropy = -sum(
                fraction * np.log(fraction)
                for fraction in fractions.values()
                if fraction > 0
            ) / np.log(6)
            current_frequency = fractions[observed[-1]]
            expected_entropy[window] = entropy
            expected_current_frequency[window] = current_frequency
            self.assertAlmostEqual(
                float(frame.iloc[-1][f"rolling_ordinal_entropy_{window}"]),
                entropy,
                places=12,
            )
            self.assertAlmostEqual(
                float(
                    frame.iloc[-1][
                        f"rolling_ordinal_current_frequency_{window}"
                    ]
                ),
                current_frequency,
                places=12,
            )
        self.assertAlmostEqual(
            float(frame.iloc[-1]["rolling_ordinal_entropy_short_long_delta"]),
            expected_entropy[32] - expected_entropy[128],
            places=12,
        )
        self.assertAlmostEqual(
            float(
                frame.iloc[-1][
                    "rolling_ordinal_current_frequency_short_long_delta"
                ]
            ),
            expected_current_frequency[32] - expected_current_frequency[128],
            places=12,
        )

        scaled = source.copy()
        for column in ("open", "high", "low", "close"):
            scaled[column] *= 10
        scaled_frame, scaled_columns = build_feature_frame(
            resample_complete_bars(scaled, 1), 1, "rolling_ordinal_motif"
        )
        self.assertEqual(feature_columns, scaled_columns)
        np.testing.assert_allclose(
            frame[ordinal_columns],
            scaled_frame[ordinal_columns],
            rtol=1e-7,
            atol=1e-9,
        )

        changed = source.copy()
        for column in ("open", "high", "low", "close"):
            changed.loc[changed.index >= 300, column] += 100.0
        changed_frame, changed_columns = build_feature_frame(
            resample_complete_bars(changed, 1), 1, "rolling_ordinal_motif"
        )
        self.assertEqual(feature_columns, changed_columns)
        pd.testing.assert_frame_equal(
            frame.loc[:299, ordinal_columns],
            changed_frame.loc[:299, ordinal_columns],
        )

        flat_source = m1_frame(200)
        for column in ("open", "high", "low", "close"):
            flat_source[column] = 100.0
        flat_frame, _ = build_feature_frame(
            resample_complete_bars(flat_source, 1), 1, "rolling_ordinal_motif"
        )
        self.assertTrue(flat_frame[ordinal_columns].eq(0).all().all())

        gapped = bars.iloc[:500].copy()
        gapped.loc[gapped.index >= 300, "timestamp"] += pd.Timedelta(minutes=10)
        gapped_frame, _ = build_feature_frame(gapped, 1, "rolling_ordinal_motif")
        self.assertTrue(gapped_frame.loc[300, ordinal_columns].eq(0).all())

        config = TrainConfig(
            timeframes=(1,),
            feature_set="rolling_ordinal_motif",
            max_train_rows=1_000,
            max_iter=5,
            min_samples_leaf=10,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            report = train_all_timeframes(source, output_dir, config)
            latest = predict_latest(source, output_dir)

        self.assertEqual(report["config"]["feature_set"], "rolling_ordinal_motif")
        self.assertTrue(latest["probability_up"].between(0, 1).all())

    def test_rolling_ordinal_motif_transfers_to_m5_without_scale_or_future_leakage(self):
        source = m1_frame(6000)
        bars = resample_complete_bars(source, 5)
        frame, feature_columns = build_feature_frame(
            bars, 5, "rolling_ordinal_motif"
        )
        ordinal_columns = [
            name for name in feature_columns if name.startswith("rolling_ordinal_")
        ]
        expected_ordinal_columns = {
            *(
                f"rolling_ordinal_{pattern}_fraction_{window}"
                for window in (32, 128)
                for pattern in ("012", "021", "102", "120", "201", "210")
            ),
            *(f"rolling_ordinal_entropy_{window}" for window in (32, 128)),
            *(
                f"rolling_ordinal_current_frequency_{window}"
                for window in (32, 128)
            ),
            "rolling_ordinal_entropy_short_long_delta",
            "rolling_ordinal_current_frequency_short_long_delta",
        }

        self.assertEqual(len(feature_columns), 56)
        self.assertEqual(set(ordinal_columns), expected_ordinal_columns)
        self.assertEqual(len(ordinal_columns), 18)
        validate_stationary_feature_set(feature_columns)
        self.assertFalse(
            {"open", "high", "low", "close"}.intersection(feature_columns)
        )
        values = frame[ordinal_columns].to_numpy(dtype="float64")
        self.assertTrue(np.isfinite(values).all())
        self.assertGreaterEqual(values.min(), -1.0)
        self.assertLessEqual(values.max(), 1.0)

        scaled = source.copy()
        for column in ("open", "high", "low", "close"):
            scaled[column] *= 10.0
        scaled_frame, scaled_columns = build_feature_frame(
            resample_complete_bars(scaled, 5), 5, "rolling_ordinal_motif"
        )
        self.assertEqual(feature_columns, scaled_columns)
        np.testing.assert_allclose(
            frame[ordinal_columns],
            scaled_frame[ordinal_columns],
            rtol=1e-7,
            atol=3e-9,
            equal_nan=True,
        )

        changed = source.copy()
        for column in ("open", "high", "low", "close"):
            changed.loc[changed.index >= 3000, column] += 100.0
        changed_frame, changed_columns = build_feature_frame(
            resample_complete_bars(changed, 5), 5, "rolling_ordinal_motif"
        )
        self.assertEqual(feature_columns, changed_columns)
        pd.testing.assert_frame_equal(
            frame.loc[:499, ordinal_columns],
            changed_frame.loc[:499, ordinal_columns],
        )

    def test_rolling_autoregressive_state_is_exact_stationary_causal_gap_safe_and_runs_latest(self):
        source = m1_frame(1800)
        bars = resample_complete_bars(source, 1)
        frame, feature_columns = build_feature_frame(
            bars, 1, "rolling_autoregressive_state"
        )
        ar_columns = [
            name for name in feature_columns if name.startswith("rolling_ar_")
        ]
        self.assertEqual(len(ar_columns), 15)
        self.assertEqual(len(feature_columns), 53)
        validate_stationary_feature_set(feature_columns)
        self.assertFalse(
            {"open", "high", "low", "close"}.intersection(feature_columns)
        )
        values = frame[ar_columns].to_numpy(dtype="float64")
        self.assertTrue(np.isfinite(values).all())
        self.assertGreaterEqual(values.min(), -1.0)
        self.assertLessEqual(values.max(), 1.0)

        returns = np.log(
            bars["close"].to_numpy(dtype="float64")
            / bars["close"].shift(1).to_numpy(dtype="float64")
        )

        def fit_ar(end: int, window: int) -> tuple[np.ndarray, float, float]:
            endpoints = np.arange(end - window + 1, end + 1)
            target = returns[endpoints]
            design = np.column_stack(
                [returns[endpoints - lag] for lag in (1, 2, 3)]
            )
            xtx = design.T @ design
            xty = design.T @ target
            ridge = 0.05 * np.trace(xtx) / 3.0
            coefficients = np.linalg.solve(xtx + ridge * np.eye(3), xty)
            rms = float(np.sqrt(np.mean(target * target)))
            explained = (
                2.0 * coefficients @ xty
                - coefficients @ xtx @ coefficients
            )
            fit_energy = float(np.clip(explained / (target @ target), -1, 1))
            return coefficients, rms, fit_energy

        target = len(bars) - 1
        expected_forecasts = {}
        expected_fit_energies = {}
        expected_innovations = {}
        for window in (32, 128):
            coefficients, rms, fit_energy = fit_ar(target, window)
            next_design = returns[[target, target - 1, target - 2]]
            forecast = float(
                np.clip(coefficients @ next_design / rms, -3, 3) / 3.0
            )
            prior_coefficients, prior_rms, _ = fit_ar(target - 1, window)
            current_design = returns[[target - 1, target - 2, target - 3]]
            innovation = float(
                np.clip(
                    (returns[target] - prior_coefficients @ current_design)
                    / prior_rms,
                    -3,
                    3,
                )
                / 3.0
            )
            for lag, coefficient in enumerate(coefficients, start=1):
                self.assertAlmostEqual(
                    float(
                        frame.iloc[-1][
                            f"rolling_ar_lag{lag}_coefficient_{window}"
                        ]
                    ),
                    float(np.clip(coefficient, -2, 2) / 2.0),
                    places=10,
                )
            self.assertAlmostEqual(
                float(frame.iloc[-1][f"rolling_ar_forecast_{window}"]),
                forecast,
                places=10,
            )
            self.assertAlmostEqual(
                float(frame.iloc[-1][f"rolling_ar_fit_energy_{window}"]),
                fit_energy,
                places=10,
            )
            self.assertAlmostEqual(
                float(
                    frame.iloc[-1][
                        f"rolling_ar_latest_innovation_{window}"
                    ]
                ),
                innovation,
                places=10,
            )
            expected_forecasts[window] = forecast
            expected_fit_energies[window] = fit_energy
            expected_innovations[window] = innovation

        self.assertAlmostEqual(
            float(frame.iloc[-1]["rolling_ar_forecast_short_long_delta"]),
            expected_forecasts[32] - expected_forecasts[128],
            places=10,
        )
        self.assertAlmostEqual(
            float(frame.iloc[-1]["rolling_ar_fit_energy_short_long_delta"]),
            expected_fit_energies[32] - expected_fit_energies[128],
            places=10,
        )
        self.assertAlmostEqual(
            float(frame.iloc[-1]["rolling_ar_innovation_short_long_delta"]),
            expected_innovations[32] - expected_innovations[128],
            places=10,
        )

        scaled = source.copy()
        for column in ("open", "high", "low", "close"):
            scaled[column] *= 10
        scaled_frame, scaled_columns = build_feature_frame(
            resample_complete_bars(scaled, 1),
            1,
            "rolling_autoregressive_state",
        )
        self.assertEqual(feature_columns, scaled_columns)
        np.testing.assert_allclose(
            frame[ar_columns],
            scaled_frame[ar_columns],
            rtol=1e-7,
            atol=1e-9,
        )

        changed = source.copy()
        for column in ("open", "high", "low", "close"):
            changed.loc[changed.index >= 300, column] += 100.0
        changed_frame, changed_columns = build_feature_frame(
            resample_complete_bars(changed, 1),
            1,
            "rolling_autoregressive_state",
        )
        self.assertEqual(feature_columns, changed_columns)
        pd.testing.assert_frame_equal(
            frame.loc[:299, ar_columns],
            changed_frame.loc[:299, ar_columns],
        )

        flat_source = m1_frame(200)
        for column in ("open", "high", "low", "close"):
            flat_source[column] = 100.0
        flat_frame, _ = build_feature_frame(
            resample_complete_bars(flat_source, 1),
            1,
            "rolling_autoregressive_state",
        )
        self.assertTrue(flat_frame[ar_columns].eq(0).all().all())

        gapped = bars.iloc[:500].copy()
        gapped.loc[gapped.index >= 300, "timestamp"] += pd.Timedelta(minutes=10)
        gapped_frame, _ = build_feature_frame(
            gapped,
            1,
            "rolling_autoregressive_state",
        )
        self.assertTrue(gapped_frame.loc[300, ar_columns].eq(0).all())

        config = TrainConfig(
            timeframes=(1,),
            feature_set="rolling_autoregressive_state",
            max_train_rows=1_000,
            max_iter=5,
            min_samples_leaf=10,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            report = train_all_timeframes(source, output_dir, config)
            latest = predict_latest(source, output_dir)

        self.assertEqual(
            report["config"]["feature_set"],
            "rolling_autoregressive_state",
        )
        self.assertTrue(latest["probability_up"].between(0, 1).all())

    def test_rolling_autoregressive_state_transfers_to_m5_without_scale_or_future_leakage(self):
        source = m1_frame(6000)
        bars = resample_complete_bars(source, 5)
        frame, feature_columns = build_feature_frame(
            bars, 5, "rolling_autoregressive_state"
        )
        ar_columns = [
            name for name in feature_columns if name.startswith("rolling_ar_")
        ]
        expected_ar_columns = {
            *(
                f"rolling_ar_lag{lag}_coefficient_{window}"
                for window in (32, 128)
                for lag in (1, 2, 3)
            ),
            *(f"rolling_ar_forecast_{window}" for window in (32, 128)),
            *(f"rolling_ar_fit_energy_{window}" for window in (32, 128)),
            *(
                f"rolling_ar_latest_innovation_{window}"
                for window in (32, 128)
            ),
            "rolling_ar_forecast_short_long_delta",
            "rolling_ar_fit_energy_short_long_delta",
            "rolling_ar_innovation_short_long_delta",
        }

        self.assertEqual(len(feature_columns), 53)
        self.assertEqual(set(ar_columns), expected_ar_columns)
        self.assertEqual(len(ar_columns), 15)
        validate_stationary_feature_set(feature_columns)
        self.assertFalse(
            {"open", "high", "low", "close"}.intersection(feature_columns)
        )
        values = frame[ar_columns].to_numpy(dtype="float64")
        self.assertTrue(np.isfinite(values).all())
        self.assertGreaterEqual(values.min(), -1.0)
        self.assertLessEqual(values.max(), 1.0)

        scaled = source.copy()
        for column in ("open", "high", "low", "close"):
            scaled[column] *= 10.0
        scaled_frame, scaled_columns = build_feature_frame(
            resample_complete_bars(scaled, 5), 5, "rolling_autoregressive_state"
        )
        self.assertEqual(feature_columns, scaled_columns)
        np.testing.assert_allclose(
            frame[ar_columns],
            scaled_frame[ar_columns],
            rtol=1e-7,
            atol=3e-9,
            equal_nan=True,
        )

        changed = source.copy()
        for column in ("open", "high", "low", "close"):
            changed.loc[changed.index >= 3000, column] += 100.0
        changed_frame, changed_columns = build_feature_frame(
            resample_complete_bars(changed, 5), 5, "rolling_autoregressive_state"
        )
        self.assertEqual(feature_columns, changed_columns)
        pd.testing.assert_frame_equal(
            frame.loc[:499, ar_columns],
            changed_frame.loc[:499, ar_columns],
        )

    def test_rolling_transition_memory_is_exact_stationary_causal_gap_safe_and_runs_latest(self):
        source = m1_frame(1800)
        bars = resample_complete_bars(source, 1)
        frame, feature_columns = build_feature_frame(
            bars, 1, "rolling_transition_memory"
        )
        transition_columns = [
            name for name in feature_columns if name.startswith("transition_memory_")
        ]
        self.assertEqual(len(transition_columns), 9)
        self.assertEqual(len(feature_columns), 47)
        validate_stationary_feature_set(feature_columns)
        self.assertFalse(
            {"open", "high", "low", "close"}.intersection(feature_columns)
        )
        values = frame[transition_columns].to_numpy(dtype="float64")
        self.assertTrue(np.isfinite(values).all())
        self.assertGreaterEqual(values.min(), -1.0)
        self.assertLessEqual(values.max(), 1.0)

        raw_return = np.log(
            bars["close"].to_numpy(dtype="float64")
            / bars["close"].shift(1).to_numpy(dtype="float64")
        )
        candle_range = bars["high"] - bars["low"]
        body_fraction = (
            (bars["close"] - bars["open"]).abs()
            / candle_range.replace(0, np.nan)
        ).fillna(0.0).to_numpy()
        close_location = (
            (bars["close"] - bars["low"])
            / candle_range.replace(0, np.nan)
        ).fillna(0.5).to_numpy()
        previous_close = bars["close"].shift(1)
        true_range = pd.concat(
            [
                candle_range,
                (bars["high"] - previous_close).abs(),
                (bars["low"] - previous_close).abs(),
            ],
            axis=1,
        ).max(axis=1)
        prior_median = true_range.rolling(20, min_periods=5).median().shift(1).to_numpy()
        state = (
            (raw_return > 0).astype("int8") * 8
            + (np.abs(body_fraction) >= 0.5).astype("int8") * 4
            + (close_location >= 0.5).astype("int8") * 2
            + (np.isfinite(prior_median) & (true_range.to_numpy() >= prior_median)).astype("int8")
        )
        valid = np.isfinite(raw_return) & (np.abs(raw_return) > 1e-15)
        target_row = len(bars) - 1
        probabilities = {}
        for window in (32, 128):
            prior_rows = np.arange(max(0, target_row - window), target_row)
            transition_rows = prior_rows[
                valid[prior_rows]
                & valid[prior_rows + 1]
            ]
            global_count = len(transition_rows)
            global_up = int((raw_return[transition_rows + 1] > 0).sum())
            global_probability = (global_up + 1.0) / (global_count + 2.0)
            matching = transition_rows[state[transition_rows] == state[target_row]]
            matching_up = int((raw_return[matching + 1] > 0).sum())
            probability = (matching_up + 8.0 * global_probability) / (
                len(matching) + 8.0
            )
            probabilities[window] = probability
            expected_reversal = (
                1.0 - probability if raw_return[target_row] > 0 else probability
            )
            self.assertAlmostEqual(
                float(frame.iloc[-1][f"transition_memory_up_edge_{window}"]),
                2.0 * probability - 1.0,
                places=12,
            )
            self.assertAlmostEqual(
                float(frame.iloc[-1][f"transition_memory_support_fraction_{window}"]),
                len(matching) / window,
                places=12,
            )
            self.assertAlmostEqual(
                float(
                    frame.iloc[-1][
                        f"transition_memory_local_global_delta_{window}"
                    ]
                ),
                probability - global_probability,
                places=12,
            )
            self.assertAlmostEqual(
                float(frame.iloc[-1][f"transition_memory_reversal_edge_{window}"]),
                2.0 * expected_reversal - 1.0,
                places=12,
            )
        self.assertAlmostEqual(
            float(frame.iloc[-1]["transition_memory_short_long_delta"]),
            probabilities[32] - probabilities[128],
            places=12,
        )

        scaled = source.copy()
        for column in ("open", "high", "low", "close"):
            scaled[column] *= 10
        scaled_frame, scaled_columns = build_feature_frame(
            resample_complete_bars(scaled, 1), 1, "rolling_transition_memory"
        )
        self.assertEqual(feature_columns, scaled_columns)
        np.testing.assert_allclose(
            frame[transition_columns],
            scaled_frame[transition_columns],
            rtol=1e-7,
            atol=1e-9,
        )

        changed = source.copy()
        for column in ("open", "high", "low", "close"):
            changed.loc[changed.index >= 300, column] += 100.0
        changed_frame, changed_columns = build_feature_frame(
            resample_complete_bars(changed, 1), 1, "rolling_transition_memory"
        )
        self.assertEqual(feature_columns, changed_columns)
        pd.testing.assert_frame_equal(
            frame.loc[:299, transition_columns],
            changed_frame.loc[:299, transition_columns],
        )

        gapped = bars.iloc[:400].copy()
        gapped.loc[gapped.index >= 300, "timestamp"] += pd.Timedelta(minutes=10)
        gapped_frame, _ = build_feature_frame(gapped, 1, "rolling_transition_memory")
        self.assertTrue(gapped_frame.loc[300, transition_columns].eq(0).all())

        m5_bars = resample_complete_bars(source, 5)
        m5_frame, m5_feature_columns = build_feature_frame(
            m5_bars, 5, "rolling_transition_memory"
        )
        m5_transition_columns = [
            name
            for name in m5_feature_columns
            if name.startswith("transition_memory_")
        ]
        self.assertEqual(m5_feature_columns, feature_columns)
        self.assertEqual(m5_transition_columns, transition_columns)
        self.assertTrue(
            np.isfinite(m5_frame[m5_transition_columns].to_numpy()).all()
        )

        gapped_m5 = m5_bars.copy()
        gapped_m5.loc[gapped_m5.index >= 300, "timestamp"] += pd.Timedelta(
            minutes=10
        )
        gapped_m5_frame, _ = build_feature_frame(
            gapped_m5, 5, "rolling_transition_memory"
        )
        self.assertTrue(
            gapped_m5_frame.loc[300, m5_transition_columns].eq(0).all()
        )

        for timeframe in (15, 30):
            higher_bars = resample_complete_bars(source, timeframe)
            higher_frame, higher_feature_columns = build_feature_frame(
                higher_bars, timeframe, "rolling_transition_memory"
            )
            higher_transition_columns = [
                name
                for name in higher_feature_columns
                if name.startswith("transition_memory_")
            ]
            self.assertEqual(higher_feature_columns, feature_columns)
            self.assertEqual(higher_transition_columns, transition_columns)
            self.assertGreater(len(higher_frame), 0)
            self.assertTrue(
                np.isfinite(
                    higher_frame[higher_transition_columns].to_numpy()
                ).all()
            )

        flat_source = m1_frame(200)
        for column in ("open", "high", "low", "close"):
            flat_source[column] = 100.0
        flat_frame, _ = build_feature_frame(
            resample_complete_bars(flat_source, 1), 1, "rolling_transition_memory"
        )
        self.assertTrue(flat_frame[transition_columns].eq(0).all().all())

        config = TrainConfig(
            timeframes=(1, 5),
            feature_set="rolling_transition_memory",
            max_train_rows=1_000,
            max_iter=5,
            min_samples_leaf=10,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            report = train_all_timeframes(source, output_dir, config)
            latest = predict_latest(source, output_dir)

        self.assertEqual(
            report["config"]["feature_set"], "rolling_transition_memory"
        )
        self.assertEqual(set(latest["timeframe"]), {"M1", "M5"})
        self.assertTrue(latest["probability_up"].between(0, 1).all())

    def test_rolling_full_path_is_exact_stationary_causal_and_runs_latest(self):
        source = m1_frame(1800)
        bars = resample_complete_bars(source, 1)
        frame, feature_columns = build_feature_frame(
            bars, 1, "rolling_full_path"
        )
        path_columns = [
            f"rolling_full_path_level_{point:02d}"
            for point in INTRABAR_FULL_PATH_GRID_POINTS
        ]
        self.assertTrue(set(path_columns).issubset(feature_columns))
        self.assertEqual(len(path_columns), 11)
        self.assertEqual(len(feature_columns), 49)
        validate_stationary_feature_set(feature_columns)
        self.assertFalse(
            {"open", "high", "low", "close"}.intersection(feature_columns)
        )
        self.assertTrue(np.isfinite(frame[path_columns]).all().all())
        self.assertTrue(
            ((frame[path_columns] >= -1) & (frame[path_columns] <= 1)).all().all()
        )

        last_window = bars.iloc[-15:]
        path_scale = float(last_window["high"].max() - last_window["low"].min())
        expected = np.array(
            [
                (
                    float(last_window.iloc[point - 1]["close"])
                    - float(last_window.iloc[0]["open"])
                )
                / path_scale
                for point in INTRABAR_FULL_PATH_GRID_POINTS
            ]
        )
        np.testing.assert_allclose(
            frame.iloc[-1][path_columns].to_numpy(dtype="float64"),
            expected,
            rtol=1e-12,
            atol=1e-12,
        )

        scaled = source.copy()
        for column in ("open", "high", "low", "close"):
            scaled[column] *= 10
        scaled_frame, scaled_columns = build_feature_frame(
            resample_complete_bars(scaled, 1), 1, "rolling_full_path"
        )
        self.assertEqual(feature_columns, scaled_columns)
        np.testing.assert_allclose(
            frame[path_columns],
            scaled_frame[path_columns],
            rtol=1e-9,
            atol=1e-9,
        )

        changed = source.copy()
        for column in ("open", "high", "low", "close"):
            changed.loc[changed.index >= 300, column] += 100.0
        changed_frame, changed_columns = build_feature_frame(
            resample_complete_bars(changed, 1), 1, "rolling_full_path"
        )
        self.assertEqual(feature_columns, changed_columns)
        pd.testing.assert_frame_equal(
            frame.loc[:299, path_columns],
            changed_frame.loc[:299, path_columns],
        )

        flat_source = m1_frame(200)
        for column in ("open", "high", "low", "close"):
            flat_source[column] = 100.0
        flat_frame, _ = build_feature_frame(
            resample_complete_bars(flat_source, 1),
            1,
            "rolling_full_path",
        )
        self.assertTrue(np.isfinite(flat_frame.loc[30:, path_columns]).all().all())
        self.assertTrue(flat_frame.loc[30:, path_columns].eq(0).all().all())

        config = TrainConfig(
            timeframes=(1,),
            feature_set="rolling_full_path",
            max_train_rows=1_000,
            max_iter=5,
            min_samples_leaf=10,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            report = train_all_timeframes(source, output_dir, config)
            latest = predict_latest(source, output_dir)

        self.assertEqual(report["config"]["feature_set"], "rolling_full_path")
        self.assertTrue(latest["probability_up"].between(0, 1).all())

    def test_rolling_full_path_transfers_to_m5_without_scale_or_future_leakage(self):
        source = m1_frame(6000)
        bars = resample_complete_bars(source, 5)
        frame, feature_columns = build_feature_frame(
            bars, 5, "rolling_full_path"
        )
        path_columns = [
            f"rolling_full_path_level_{point:02d}"
            for point in INTRABAR_FULL_PATH_GRID_POINTS
        ]

        self.assertEqual(len(feature_columns), 49)
        self.assertEqual(
            {name for name in feature_columns if name.startswith("rolling_full_path_")},
            set(path_columns),
        )
        self.assertEqual(len(path_columns), 11)
        validate_stationary_feature_set(feature_columns)
        self.assertFalse(
            {"open", "high", "low", "close"}.intersection(feature_columns)
        )
        values = frame[path_columns].to_numpy(dtype="float64")
        self.assertTrue(np.isfinite(values).all())
        self.assertGreaterEqual(values.min(), -1.0)
        self.assertLessEqual(values.max(), 1.0)

        last_window = bars.iloc[-15:]
        path_scale = float(last_window["high"].max() - last_window["low"].min())
        expected = np.array(
            [
                (
                    float(last_window.iloc[point - 1]["close"])
                    - float(last_window.iloc[0]["open"])
                )
                / path_scale
                for point in INTRABAR_FULL_PATH_GRID_POINTS
            ]
        )
        np.testing.assert_allclose(
            frame.iloc[-1][path_columns].to_numpy(dtype="float64"),
            expected,
            rtol=1e-12,
            atol=1e-12,
        )

        scaled = source.copy()
        for column in ("open", "high", "low", "close"):
            scaled[column] *= 10.0
        scaled_frame, scaled_columns = build_feature_frame(
            resample_complete_bars(scaled, 5), 5, "rolling_full_path"
        )
        self.assertEqual(feature_columns, scaled_columns)
        np.testing.assert_allclose(
            frame[path_columns],
            scaled_frame[path_columns],
            rtol=1e-7,
            atol=3e-9,
            equal_nan=True,
        )

        changed = source.copy()
        for column in ("open", "high", "low", "close"):
            changed.loc[changed.index >= 3000, column] += 100.0
        changed_frame, changed_columns = build_feature_frame(
            resample_complete_bars(changed, 5), 5, "rolling_full_path"
        )
        self.assertEqual(feature_columns, changed_columns)
        pd.testing.assert_frame_equal(
            frame.loc[:499, path_columns],
            changed_frame.loc[:499, path_columns],
        )

        config = TrainConfig(
            timeframes=(5,),
            feature_set="rolling_full_path",
            max_train_rows=1_000,
            max_iter=5,
            min_samples_leaf=10,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            report = train_all_timeframes(source, output_dir, config)
            latest = predict_latest(source, output_dir)

        self.assertEqual(report["config"]["feature_set"], "rolling_full_path")
        self.assertEqual(latest["timeframe"].tolist(), ["M5"])
        self.assertTrue(latest["probability_up"].between(0, 1).all())

    def test_change_point_state_is_stationary_causal_gap_safe_and_runs_latest(self):
        source = m1_frame(1800)
        bars = resample_complete_bars(source, 1)
        frame, feature_columns = build_feature_frame(
            bars, 1, "change_point_state"
        )
        state_columns = [
            f"change_point_{channel}_{state}_64"
            for channel in ("return", "range")
            for state in (
                "positive",
                "negative",
                "balance",
                "alarm_direction",
                "alarm_age",
            )
        ]
        self.assertTrue(set(state_columns).issubset(feature_columns))
        self.assertEqual(len(state_columns), 10)
        self.assertEqual(len(feature_columns), 48)
        validate_stationary_feature_set(feature_columns)
        self.assertFalse(
            {"open", "high", "low", "close"}.intersection(feature_columns)
        )
        self.assertTrue(np.isfinite(frame[state_columns]).all().all())
        for channel in ("return", "range"):
            self.assertTrue(
                frame[f"change_point_{channel}_positive_64"].between(0, 1).all()
            )
            self.assertTrue(
                frame[f"change_point_{channel}_negative_64"].between(0, 1).all()
            )
            self.assertTrue(
                frame[f"change_point_{channel}_balance_64"].between(-1, 1).all()
            )
            self.assertTrue(
                frame[f"change_point_{channel}_alarm_direction_64"]
                .isin([-1, 0, 1])
                .all()
            )
            self.assertTrue(
                frame[f"change_point_{channel}_alarm_age_64"].between(0, 1).all()
            )

        scaled = source.copy()
        for column in ("open", "high", "low", "close"):
            scaled[column] *= 10
        scaled_frame, scaled_columns = build_feature_frame(
            resample_complete_bars(scaled, 1), 1, "change_point_state"
        )
        self.assertEqual(feature_columns, scaled_columns)
        np.testing.assert_allclose(
            frame[state_columns],
            scaled_frame[state_columns],
            rtol=1e-9,
            atol=1e-9,
        )

        changed = source.copy()
        for column in ("open", "high", "low", "close"):
            changed.loc[changed.index >= 300, column] += 100.0
        changed_frame, changed_columns = build_feature_frame(
            resample_complete_bars(changed, 1), 1, "change_point_state"
        )
        self.assertEqual(feature_columns, changed_columns)
        pd.testing.assert_frame_equal(
            frame.loc[:299, state_columns],
            changed_frame.loc[:299, state_columns],
        )

        gapped_bars = bars.copy()
        gapped_bars.loc[gapped_bars.index >= 300, "timestamp"] += pd.Timedelta(
            minutes=5
        )
        gapped_frame, _ = build_feature_frame(gapped_bars, 1, "change_point_state")
        returns = np.log(
            gapped_bars["close"] / gapped_bars["close"].shift(1)
        )
        prior = returns.iloc[
            300 - CHANGE_POINT_REFERENCE_WINDOW : 300
        ]
        innovation = float(
            np.clip(
                (returns.iloc[300] - prior.mean()) / prior.std(),
                -5.0,
                5.0,
            )
        )
        self.assertAlmostEqual(
            float(gapped_frame.loc[300, "change_point_return_positive_64"]),
            max(0.0, innovation - CHANGE_POINT_DRIFT) / CHANGE_POINT_SCORE_CAP,
            places=12,
        )
        self.assertAlmostEqual(
            float(gapped_frame.loc[300, "change_point_return_negative_64"]),
            max(0.0, -innovation - CHANGE_POINT_DRIFT) / CHANGE_POINT_SCORE_CAP,
            places=12,
        )

        flat_source = m1_frame(200)
        for column in ("open", "high", "low", "close"):
            flat_source[column] = 100.0
        flat_frame, _ = build_feature_frame(
            resample_complete_bars(flat_source, 1), 1, "change_point_state"
        )
        self.assertTrue(flat_frame.loc[100:, state_columns].eq(0).all().all())

        config = TrainConfig(
            timeframes=(1,),
            feature_set="change_point_state",
            max_train_rows=1_000,
            max_iter=5,
            min_samples_leaf=10,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            report = train_all_timeframes(source, output_dir, config)
            latest = predict_latest(source, output_dir)

        self.assertEqual(report["config"]["feature_set"], "change_point_state")
        self.assertTrue(latest["probability_up"].between(0, 1).all())

    def test_change_point_state_transfers_to_m5_without_scale_or_future_leakage(self):
        source = m1_frame(6000)
        bars = resample_complete_bars(source, 5)
        frame, feature_columns = build_feature_frame(
            bars, 5, "change_point_state"
        )
        state_columns = [
            f"change_point_{channel}_{state}_64"
            for channel in ("return", "range")
            for state in (
                "positive",
                "negative",
                "balance",
                "alarm_direction",
                "alarm_age",
            )
        ]

        self.assertEqual(len(feature_columns), 48)
        self.assertEqual(
            {name for name in feature_columns if name.startswith("change_point_")},
            set(state_columns),
        )
        self.assertEqual(len(state_columns), 10)
        validate_stationary_feature_set(feature_columns)
        self.assertFalse(
            {"open", "high", "low", "close"}.intersection(feature_columns)
        )
        values = frame[state_columns].to_numpy(dtype="float64")
        self.assertTrue(np.isfinite(values).all())
        self.assertGreaterEqual(values.min(), -1.0)
        self.assertLessEqual(values.max(), 1.0)

        scaled = source.copy()
        for column in ("open", "high", "low", "close"):
            scaled[column] *= 10.0
        scaled_frame, scaled_columns = build_feature_frame(
            resample_complete_bars(scaled, 5), 5, "change_point_state"
        )
        self.assertEqual(feature_columns, scaled_columns)
        np.testing.assert_allclose(
            frame[state_columns],
            scaled_frame[state_columns],
            rtol=1e-7,
            atol=3e-9,
            equal_nan=True,
        )

        changed = source.copy()
        for column in ("open", "high", "low", "close"):
            changed.loc[changed.index >= 3000, column] += 100.0
        changed_frame, changed_columns = build_feature_frame(
            resample_complete_bars(changed, 5), 5, "change_point_state"
        )
        self.assertEqual(feature_columns, changed_columns)
        pd.testing.assert_frame_equal(
            frame.loc[:499, state_columns],
            changed_frame.loc[:499, state_columns],
        )

        config = TrainConfig(
            timeframes=(5,),
            feature_set="change_point_state",
            max_train_rows=1_000,
            max_iter=5,
            min_samples_leaf=10,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            report = train_all_timeframes(source, output_dir, config)
            latest = predict_latest(source, output_dir)

        self.assertEqual(report["config"]["feature_set"], "change_point_state")
        self.assertEqual(latest["timeframe"].tolist(), ["M5"])
        self.assertTrue(latest["probability_up"].between(0, 1).all())

    def test_shock_recovery_state_is_stationary_causal_gap_safe_and_runs_latest(self):
        source = m1_frame(1800)
        for column in ("open", "high", "low", "close"):
            source.loc[source.index >= 300, column] *= 1.02
        bars = resample_complete_bars(source, 1)
        frame, feature_columns = build_feature_frame(
            bars, 1, "shock_recovery_state"
        )
        state_columns = [
            "shock_return_innovation",
            "shock_range_innovation",
            "shock_return_direction",
            "shock_return_excess",
            "shock_return_age",
            "shock_return_response",
            "shock_return_max_continuation",
            "shock_return_max_reversal",
            "shock_range_direction",
            "shock_range_excess",
            "shock_range_age",
            "shock_joint_event",
        ]
        self.assertTrue(set(state_columns).issubset(feature_columns))
        self.assertEqual(len(state_columns), 12)
        self.assertEqual(len(feature_columns), 50)
        validate_stationary_feature_set(feature_columns)
        self.assertFalse(
            {"open", "high", "low", "close"}.intersection(feature_columns)
        )
        self.assertTrue(np.isfinite(frame[state_columns]).all().all())
        for column in (
            "shock_return_innovation",
            "shock_range_innovation",
            "shock_return_response",
        ):
            self.assertTrue(frame[column].between(-1, 1).all())
        for column in (
            "shock_return_excess",
            "shock_return_age",
            "shock_return_max_continuation",
            "shock_return_max_reversal",
            "shock_range_excess",
            "shock_range_age",
            "shock_joint_event",
        ):
            self.assertTrue(frame[column].between(0, 1).all())
        for column in ("shock_return_direction", "shock_range_direction"):
            self.assertTrue(frame[column].isin([-1, 0, 1]).all())

        self.assertGreaterEqual(
            abs(float(frame.loc[300, "shock_return_innovation"])) * 5.0,
            SHOCK_Z_THRESHOLD,
        )
        shock_direction = float(frame.loc[300, "shock_return_direction"])
        self.assertEqual(
            shock_direction,
            float(np.sign(frame.loc[300, "shock_return_innovation"])),
        )
        self.assertEqual(float(frame.loc[300, "shock_return_age"]), 0.0)
        self.assertEqual(float(frame.loc[300, "shock_return_response"]), 0.0)
        self.assertLess(
            abs(float(frame.loc[301, "shock_return_innovation"])) * 5.0,
            SHOCK_Z_THRESHOLD,
        )
        event_return = float(np.log(bars.loc[300, "close"] / bars.loc[299, "close"]))
        next_return = float(np.log(bars.loc[301, "close"] / bars.loc[300, "close"]))
        expected_response = float(np.clip(
            shock_direction * next_return / abs(event_return),
            -SHOCK_RESPONSE_CAP,
            SHOCK_RESPONSE_CAP,
        ) / SHOCK_RESPONSE_CAP)
        self.assertEqual(float(frame.loc[301, "shock_return_direction"]), shock_direction)
        self.assertAlmostEqual(
            float(frame.loc[301, "shock_return_age"]),
            1.0 / SHOCK_TRACKING_BARS,
            places=12,
        )
        self.assertAlmostEqual(
            float(frame.loc[301, "shock_return_response"]),
            expected_response,
            places=12,
        )

        scaled = source.copy()
        for column in ("open", "high", "low", "close"):
            scaled[column] *= 10
        scaled_frame, scaled_columns = build_feature_frame(
            resample_complete_bars(scaled, 1), 1, "shock_recovery_state"
        )
        self.assertEqual(feature_columns, scaled_columns)
        np.testing.assert_allclose(
            frame[state_columns],
            scaled_frame[state_columns],
            rtol=1e-9,
            atol=1e-9,
        )

        changed = source.copy()
        for column in ("open", "high", "low", "close"):
            changed.loc[changed.index >= 900, column] += 100.0
        changed_frame, changed_columns = build_feature_frame(
            resample_complete_bars(changed, 1), 1, "shock_recovery_state"
        )
        self.assertEqual(feature_columns, changed_columns)
        pd.testing.assert_frame_equal(
            frame.loc[:899, state_columns],
            changed_frame.loc[:899, state_columns],
        )

        gapped_bars = bars.copy()
        gapped_bars.loc[gapped_bars.index >= 301, "timestamp"] += pd.Timedelta(
            minutes=5
        )
        gapped_frame, _ = build_feature_frame(
            gapped_bars, 1, "shock_recovery_state"
        )
        self.assertEqual(float(gapped_frame.loc[301, "shock_return_direction"]), 0.0)
        self.assertEqual(float(gapped_frame.loc[301, "shock_return_age"]), 0.0)
        self.assertEqual(float(gapped_frame.loc[301, "shock_return_response"]), 0.0)

        flat_source = m1_frame(200)
        for column in ("open", "high", "low", "close"):
            flat_source[column] = 100.0
        flat_frame, _ = build_feature_frame(
            resample_complete_bars(flat_source, 1), 1, "shock_recovery_state"
        )
        self.assertTrue(flat_frame.loc[100:, state_columns].eq(0).all().all())

        config = TrainConfig(
            timeframes=(1,),
            feature_set="shock_recovery_state",
            max_train_rows=1_000,
            max_iter=5,
            min_samples_leaf=10,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            report = train_all_timeframes(source, output_dir, config)
            latest = predict_latest(source, output_dir)

        self.assertEqual(report["config"]["feature_set"], "shock_recovery_state")
        self.assertTrue(latest["probability_up"].between(0, 1).all())

    def test_shock_recovery_state_transfers_to_m5_without_scale_or_future_leakage(self):
        source = m1_frame(6000)
        bars = resample_complete_bars(source, 5)
        frame, feature_columns = build_feature_frame(
            bars, 5, "shock_recovery_state"
        )
        state_columns = [
            name for name in feature_columns if name.startswith("shock_")
        ]
        expected_state_columns = {
            "shock_return_innovation",
            "shock_range_innovation",
            "shock_return_direction",
            "shock_return_excess",
            "shock_return_age",
            "shock_return_response",
            "shock_return_max_continuation",
            "shock_return_max_reversal",
            "shock_range_direction",
            "shock_range_excess",
            "shock_range_age",
            "shock_joint_event",
        }

        self.assertEqual(len(feature_columns), 50)
        self.assertEqual(set(state_columns), expected_state_columns)
        self.assertEqual(len(state_columns), 12)
        validate_stationary_feature_set(feature_columns)
        self.assertFalse(
            {"open", "high", "low", "close"}.intersection(feature_columns)
        )
        values = frame[state_columns].to_numpy(dtype="float64")
        self.assertTrue(np.isfinite(values).all())
        self.assertGreaterEqual(values.min(), -1.0)
        self.assertLessEqual(values.max(), 1.0)

        scaled = source.copy()
        for column in ("open", "high", "low", "close"):
            scaled[column] *= 10.0
        scaled_frame, scaled_columns = build_feature_frame(
            resample_complete_bars(scaled, 5), 5, "shock_recovery_state"
        )
        self.assertEqual(feature_columns, scaled_columns)
        np.testing.assert_allclose(
            frame[state_columns],
            scaled_frame[state_columns],
            rtol=1e-7,
            atol=3e-9,
            equal_nan=True,
        )

        changed = source.copy()
        for column in ("open", "high", "low", "close"):
            changed.loc[changed.index >= 3000, column] += 100.0
        changed_frame, changed_columns = build_feature_frame(
            resample_complete_bars(changed, 5), 5, "shock_recovery_state"
        )
        self.assertEqual(feature_columns, changed_columns)
        pd.testing.assert_frame_equal(
            frame.loc[:499, state_columns],
            changed_frame.loc[:499, state_columns],
        )

        config = TrainConfig(
            timeframes=(5,),
            feature_set="shock_recovery_state",
            max_train_rows=1_000,
            max_iter=5,
            min_samples_leaf=10,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            report = train_all_timeframes(source, output_dir, config)
            latest = predict_latest(source, output_dir)

        self.assertEqual(report["config"]["feature_set"], "shock_recovery_state")
        self.assertEqual(latest["timeframe"].tolist(), ["M5"])
        self.assertTrue(latest["probability_up"].between(0, 1).all())

    def test_path_persistence_features_are_stationary_causal_and_run_latest(self):
        source = m1_frame(1800)
        bars = resample_complete_bars(source, 1)
        frame, feature_columns = build_feature_frame(bars, 1, "path_persistence")
        persistence_columns = [
            name
            for name in feature_columns
            if name.startswith(
                (
                    "signed_efficiency_",
                    "return_autocorrelation_",
                    "direction_change_fraction_",
                    "variance_ratio_",
                )
            )
            or name
            in {
                "up_persistence_20",
                "down_persistence_20",
                "signed_return_streak_20",
            }
        ]
        self.assertEqual(len(persistence_columns), 14)
        validate_stationary_feature_set(feature_columns)
        self.assertFalse({"open", "high", "low", "close"}.intersection(feature_columns))

        changed = source.copy()
        for column in ["open", "high", "low", "close"]:
            changed.loc[changed.index >= 200, column] += 100.0
        changed_bars = resample_complete_bars(changed, 1)
        changed_frame, changed_columns = build_feature_frame(
            changed_bars, 1, "path_persistence"
        )
        self.assertEqual(feature_columns, changed_columns)
        pd.testing.assert_frame_equal(
            frame.loc[:199, persistence_columns],
            changed_frame.loc[:199, persistence_columns],
        )

        flat_source = m1_frame(200)
        for column in ("open", "high", "low", "close"):
            flat_source[column] = 100.0
        flat_frame, _ = build_feature_frame(
            resample_complete_bars(flat_source, 1), 1, "path_persistence"
        )
        self.assertTrue(
            np.isfinite(flat_frame.loc[100:, persistence_columns]).all().all()
        )
        self.assertTrue(
            flat_frame.loc[100:, persistence_columns].eq(0).all().all()
        )

        config = TrainConfig(
            timeframes=(1,),
            feature_set="path_persistence",
            max_train_rows=1_000,
            max_iter=5,
            min_samples_leaf=10,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            report = train_all_timeframes(source, output_dir, config)
            latest = predict_latest(source, output_dir)

        self.assertEqual(report["config"]["feature_set"], "path_persistence")
        self.assertTrue(latest["probability_up"].between(0, 1).all())

    def test_path_persistence_features_transfer_to_m5(self):
        source = m1_frame(6000)
        bars = resample_complete_bars(source, 5)
        frame, feature_columns = build_feature_frame(bars, 5, "path_persistence")
        persistence_columns = [
            "signed_efficiency_5",
            "signed_efficiency_10",
            "signed_efficiency_20",
            "signed_efficiency_50",
            "return_autocorrelation_10",
            "return_autocorrelation_20",
            "direction_change_fraction_10",
            "direction_change_fraction_20",
            "variance_ratio_2_50",
            "variance_ratio_5_50",
            "variance_ratio_10_50",
            "up_persistence_20",
            "down_persistence_20",
            "signed_return_streak_20",
        ]

        self.assertEqual(len(feature_columns), 52)
        self.assertTrue(set(persistence_columns).issubset(feature_columns))
        validate_stationary_feature_set(feature_columns)
        self.assertFalse({"open", "high", "low", "close"}.intersection(feature_columns))
        usable = frame[persistence_columns].dropna()
        self.assertGreater(len(usable), 0)
        self.assertTrue(np.isfinite(usable).all().all())

        scaled = source.copy()
        for column in ("open", "high", "low", "close"):
            scaled[column] *= 10.0
        scaled_frame, scaled_columns = build_feature_frame(
            resample_complete_bars(scaled, 5), 5, "path_persistence"
        )
        self.assertEqual(feature_columns, scaled_columns)
        np.testing.assert_allclose(
            frame[persistence_columns],
            scaled_frame[persistence_columns],
            rtol=1e-9,
            atol=1e-9,
            equal_nan=True,
        )

    def test_direction_transition_state_is_causal_finite_and_runs_latest(self):
        source = m1_frame(1800)
        bars = resample_complete_bars(source, 1)
        frame, feature_columns = build_feature_frame(
            bars, 1, "direction_transition_state"
        )
        state_columns = [
            "transition_current_direction",
            "transition_run_length_bucket",
            "transition_reversal_fraction_8",
            "transition_volatility_state_5_20",
        ]
        self.assertTrue(set(state_columns).issubset(feature_columns))
        validate_stationary_feature_set(feature_columns)
        self.assertFalse({"open", "high", "low", "close"}.intersection(feature_columns))
        self.assertTrue(np.isfinite(frame[state_columns].dropna()).all().all())
        self.assertTrue(frame["transition_current_direction"].dropna().isin([-1, 0, 1]).all())
        self.assertTrue(frame["transition_run_length_bucket"].dropna().between(0, 4).all())
        self.assertTrue(frame["transition_reversal_fraction_8"].dropna().between(0, 1).all())
        self.assertTrue(
            frame["transition_volatility_state_5_20"]
            .dropna()
            .isin([-1, 0, 1])
            .all()
        )

        scaled = source.copy()
        for column in ("open", "high", "low", "close"):
            scaled[column] *= 10
        scaled_frame, scaled_columns = build_feature_frame(
            resample_complete_bars(scaled, 1), 1, "direction_transition_state"
        )
        self.assertEqual(feature_columns, scaled_columns)
        pd.testing.assert_frame_equal(
            frame[state_columns], scaled_frame[state_columns]
        )

        changed = source.copy()
        for column in ("open", "high", "low", "close"):
            changed.loc[changed.index >= 200, column] += 100.0
        changed_frame, changed_columns = build_feature_frame(
            resample_complete_bars(changed, 1), 1, "direction_transition_state"
        )
        self.assertEqual(feature_columns, changed_columns)
        pd.testing.assert_frame_equal(
            frame.loc[:199, state_columns], changed_frame.loc[:199, state_columns]
        )

        flat_source = m1_frame(200)
        for column in ("open", "high", "low", "close"):
            flat_source[column] = 100.0
        flat_frame, _ = build_feature_frame(
            resample_complete_bars(flat_source, 1),
            1,
            "direction_transition_state",
        )
        self.assertTrue(flat_frame.loc[100:, state_columns].eq(0).all().all())

        config = TrainConfig(
            timeframes=(1,),
            feature_set="direction_transition_state",
            model_type="transition_bayes",
            max_train_rows=1_000,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "first"
            repeat_dir = Path(temp_dir) / "repeat"
            report = train_all_timeframes(source, output_dir, config)
            train_all_timeframes(source, repeat_dir, config)
            latest = predict_latest(source, output_dir)
            first_predictions = pd.read_parquet(
                output_dir / "m1_test_predictions.parquet"
            )
            repeat_predictions = pd.read_parquet(
                repeat_dir / "m1_test_predictions.parquet"
            )

        diagnostics = report["timeframes"]["M1"]["model_diagnostics"]
        self.assertEqual(report["config"]["model_type"], "transition_bayes")
        self.assertEqual(diagnostics["encoded_state_slots"], 135)
        self.assertEqual(diagnostics["structurally_reachable_states"], 81)
        self.assertEqual(diagnostics["unexpected_state_rows"], 0.0)
        self.assertEqual(diagnostics["state_prior_strength"], 64.0)
        self.assertEqual(diagnostics["parent_prior_strength"], 256.0)
        self.assertTrue(0 < diagnostics["observed_states"] <= 81)
        self.assertTrue(latest["probability_up"].between(0, 1).all())
        np.testing.assert_allclose(
            first_predictions["raw_probability_up"],
            repeat_predictions["raw_probability_up"],
            rtol=0,
            atol=0,
        )

    def test_direction_transition_bayes_transfers_to_m5_exactly_and_causally(self):
        source = m1_frame(6000)
        bars = resample_complete_bars(source, 5)
        frame, feature_columns = build_feature_frame(
            bars, 5, "direction_transition_state"
        )
        state_columns = [
            "transition_current_direction",
            "transition_run_length_bucket",
            "transition_reversal_fraction_8",
            "transition_volatility_state_5_20",
        ]

        self.assertEqual(len(feature_columns), 42)
        self.assertEqual(
            {name for name in feature_columns if name.startswith("transition_")},
            set(state_columns),
        )
        validate_stationary_feature_set(feature_columns)
        self.assertFalse(
            {"open", "high", "low", "close"}.intersection(feature_columns)
        )
        self.assertTrue(np.isfinite(frame[state_columns].dropna()).all().all())

        returns = np.log(
            bars["close"].to_numpy(dtype="float64")
            / bars["close"].shift(1).to_numpy(dtype="float64")
        )
        directions = np.sign(returns)
        expected_run_length = 0
        if directions[-1] != 0:
            expected_run_length = 1
            for value in directions[-2::-1]:
                if value != directions[-1] or expected_run_length == 4:
                    break
                expected_run_length += 1
        recent_current = directions[-8:]
        recent_previous = directions[-9:-1]
        valid = (recent_current != 0) & (recent_previous != 0)
        expected_reversal_fraction = float(
            np.mean(recent_current[valid] != recent_previous[valid])
        )
        short_volatility = float(np.std(returns[-5:], ddof=1))
        long_volatility = float(np.std(returns[-20:], ddof=1))
        volatility_ratio = short_volatility / long_volatility
        expected_volatility_state = (
            -1.0
            if volatility_ratio < 0.8
            else 1.0
            if volatility_ratio > 1.25
            else 0.0
        )
        self.assertEqual(
            float(frame.iloc[-1]["transition_current_direction"]),
            float(directions[-1]),
        )
        self.assertEqual(
            float(frame.iloc[-1]["transition_run_length_bucket"]),
            float(expected_run_length),
        )
        self.assertAlmostEqual(
            float(frame.iloc[-1]["transition_reversal_fraction_8"]),
            expected_reversal_fraction,
            places=12,
        )
        self.assertEqual(
            float(frame.iloc[-1]["transition_volatility_state_5_20"]),
            expected_volatility_state,
        )

        scaled = source.copy()
        for column in ("open", "high", "low", "close"):
            scaled[column] *= 10.0
        scaled_frame, scaled_columns = build_feature_frame(
            resample_complete_bars(scaled, 5), 5, "direction_transition_state"
        )
        self.assertEqual(feature_columns, scaled_columns)
        pd.testing.assert_frame_equal(
            frame[state_columns], scaled_frame[state_columns]
        )

        changed = source.copy()
        for column in ("open", "high", "low", "close"):
            changed.loc[changed.index >= 3000, column] += 100.0
        changed_frame, changed_columns = build_feature_frame(
            resample_complete_bars(changed, 5), 5, "direction_transition_state"
        )
        self.assertEqual(feature_columns, changed_columns)
        pd.testing.assert_frame_equal(
            frame.loc[:499, state_columns],
            changed_frame.loc[:499, state_columns],
        )

        config = TrainConfig(
            timeframes=(5,),
            feature_set="direction_transition_state",
            model_type="transition_bayes",
            max_train_rows=1_000,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            report = train_all_timeframes(source, output_dir, config)
            latest = predict_latest(source, output_dir)

        diagnostics = report["timeframes"]["M5"]["model_diagnostics"]
        self.assertEqual(report["config"]["model_type"], "transition_bayes")
        self.assertEqual(diagnostics["encoded_state_slots"], 135)
        self.assertEqual(diagnostics["structurally_reachable_states"], 81)
        self.assertEqual(diagnostics["state_prior_strength"], 64.0)
        self.assertEqual(diagnostics["parent_prior_strength"], 256.0)
        self.assertEqual(latest["timeframe"].tolist(), ["M5"])
        self.assertTrue(latest["probability_up"].between(0, 1).all())

    def test_haar_multiscale_features_are_stationary_causal_and_run_latest(self):
        source = m1_frame(1800)
        bars = resample_complete_bars(source, 1)
        frame, feature_columns = build_feature_frame(bars, 1, "haar_multiscale")
        haar_columns = [name for name in feature_columns if name.startswith("haar_")]
        self.assertEqual(len(haar_columns), 12)
        for window in (4, 8, 16, 32):
            self.assertIn(f"haar_return_detail_{window}", haar_columns)
            self.assertIn(f"haar_absolute_detail_{window}", haar_columns)
            self.assertIn(f"haar_direction_detail_{window}", haar_columns)
        validate_stationary_feature_set(feature_columns)
        self.assertFalse({"open", "high", "low", "close"}.intersection(feature_columns))

        scaled = source.copy()
        for column in ("open", "high", "low", "close"):
            scaled[column] *= 10
        scaled_frame, scaled_columns = build_feature_frame(
            resample_complete_bars(scaled, 1), 1, "haar_multiscale"
        )
        self.assertEqual(feature_columns, scaled_columns)
        np.testing.assert_allclose(
            frame[haar_columns],
            scaled_frame[haar_columns],
            rtol=1e-7,
            atol=3e-9,
            equal_nan=True,
        )

        changed = source.copy()
        for column in ["open", "high", "low", "close"]:
            changed.loc[changed.index >= 200, column] += 100.0
        changed_bars = resample_complete_bars(changed, 1)
        changed_frame, changed_columns = build_feature_frame(
            changed_bars, 1, "haar_multiscale"
        )
        self.assertEqual(feature_columns, changed_columns)
        pd.testing.assert_frame_equal(
            frame.loc[:199, haar_columns],
            changed_frame.loc[:199, haar_columns],
        )

        flat_source = m1_frame(200)
        for column in ("open", "high", "low", "close"):
            flat_source[column] = 100.0
        flat_frame, _ = build_feature_frame(
            resample_complete_bars(flat_source, 1), 1, "haar_multiscale"
        )
        self.assertTrue(np.isfinite(flat_frame.loc[100:, haar_columns]).all().all())
        self.assertTrue(flat_frame.loc[100:, haar_columns].eq(0).all().all())

        config = TrainConfig(
            timeframes=(1,),
            feature_set="haar_multiscale",
            max_train_rows=1_000,
            max_iter=5,
            min_samples_leaf=10,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            report = train_all_timeframes(source, output_dir, config)
            latest = predict_latest(source, output_dir)

        self.assertEqual(report["config"]["feature_set"], "haar_multiscale")
        self.assertTrue(latest["probability_up"].between(0, 1).all())

    def test_haar_multiscale_features_transfer_to_m5(self):
        source = m1_frame(6000)
        bars = resample_complete_bars(source, 5)
        frame, feature_columns = build_feature_frame(bars, 5, "haar_multiscale")
        haar_columns = [name for name in feature_columns if name.startswith("haar_")]

        self.assertEqual(len(feature_columns), 50)
        self.assertEqual(len(haar_columns), 12)
        for window in (4, 8, 16, 32):
            self.assertIn(f"haar_return_detail_{window}", haar_columns)
            self.assertIn(f"haar_absolute_detail_{window}", haar_columns)
            self.assertIn(f"haar_direction_detail_{window}", haar_columns)
        validate_stationary_feature_set(feature_columns)
        self.assertFalse({"open", "high", "low", "close"}.intersection(feature_columns))
        usable = frame[haar_columns].dropna()
        self.assertGreater(len(usable), 0)
        self.assertTrue(np.isfinite(usable).all().all())

        scaled = source.copy()
        for column in ("open", "high", "low", "close"):
            scaled[column] *= 10.0
        scaled_frame, scaled_columns = build_feature_frame(
            resample_complete_bars(scaled, 5), 5, "haar_multiscale"
        )
        self.assertEqual(feature_columns, scaled_columns)
        np.testing.assert_allclose(
            frame[haar_columns],
            scaled_frame[haar_columns],
            rtol=1e-7,
            atol=3e-9,
            equal_nan=True,
        )

    def test_session_relative_features_use_prior_stationary_rows_and_run_latest(self):
        source = m1_frame(2400)
        bars = resample_complete_bars(source, 1)
        frame, feature_columns = build_feature_frame(bars, 1, "session_relative")
        session_columns = [
            name for name in feature_columns if name.startswith("session_")
        ]
        self.assertEqual(
            session_columns,
            [
                "session_return_z_32",
                "session_body_z_32",
                "session_absolute_return_ratio_32",
                "session_range_ratio_32",
                "session_direction_bias_32",
            ],
        )
        validate_stationary_feature_set(feature_columns)
        self.assertFalse({"open", "high", "low", "close"}.intersection(feature_columns))
        self.assertTrue(frame["session_direction_bias_32"].dropna().between(-1, 1).all())

        flat_source = m1_frame(2400)
        for column in ("open", "high", "low", "close"):
            flat_source[column] = 100.0
        flat_frame, _ = build_feature_frame(
            resample_complete_bars(flat_source, 1), 1, "session_relative"
        )
        eligible = flat_frame["session_direction_bias_32"].notna()
        self.assertTrue(np.isfinite(flat_frame.loc[eligible, session_columns]).all().all())
        self.assertTrue(flat_frame.loc[eligible, session_columns].eq(0).all().all())

        changed = source.copy()
        for column in ["open", "high", "low", "close"]:
            changed.loc[changed.index >= 1200, column] += 100.0
        changed_bars = resample_complete_bars(changed, 1)
        changed_frame, changed_columns = build_feature_frame(
            changed_bars, 1, "session_relative"
        )
        self.assertEqual(feature_columns, changed_columns)
        pd.testing.assert_frame_equal(
            frame.loc[:1199, session_columns],
            changed_frame.loc[:1199, session_columns],
        )

        config = TrainConfig(
            timeframes=(1,),
            feature_set="session_relative",
            max_train_rows=1_000,
            max_iter=5,
            min_samples_leaf=10,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            report = train_all_timeframes(source, output_dir, config)
            latest = predict_latest(source, output_dir)

        self.assertEqual(report["config"]["feature_set"], "session_relative")
        self.assertTrue(latest["probability_up"].between(0, 1).all())

    def test_session_relative_transfers_to_m5_causally_and_scale_invariant(self):
        source = m1_frame(33_000)
        bars = resample_complete_bars(source, 5)
        frame, feature_columns = build_feature_frame(bars, 5, "session_relative")
        session_columns = [
            name for name in feature_columns if name.startswith("session_")
        ]

        self.assertEqual(len(feature_columns), 43)
        self.assertEqual(
            session_columns,
            [
                "session_return_z_32",
                "session_body_z_32",
                "session_absolute_return_ratio_32",
                "session_range_ratio_32",
                "session_direction_bias_32",
            ],
        )
        validate_stationary_feature_set(feature_columns)
        self.assertFalse({"open", "high", "low", "close"}.intersection(feature_columns))
        usable = frame[session_columns].dropna()
        self.assertGreater(len(usable), 0)
        self.assertTrue(np.isfinite(usable).all().all())

        row_index = int(usable.index[-1])
        timestamps = pd.to_datetime(bars["timestamp"], utc=True)
        session_hour = timestamps.dt.dayofweek * 24 + timestamps.dt.hour
        same_session_prior = bars.index[
            (bars.index < row_index) & session_hour.eq(session_hour.iloc[row_index])
        ][-32:]
        returns = np.log(bars["close"] / bars["close"].shift(1))
        prior_returns = returns.loc[same_session_prior]
        expected_return_z = (
            returns.iloc[row_index] - prior_returns.mean()
        ) / prior_returns.std(ddof=0)
        expected_direction_bias = np.sign(prior_returns).mean()
        self.assertAlmostEqual(
            float(frame.loc[row_index, "session_return_z_32"]),
            float(np.clip(expected_return_z, -10, 10)),
            places=12,
        )
        self.assertAlmostEqual(
            float(frame.loc[row_index, "session_direction_bias_32"]),
            float(expected_direction_bias),
            places=12,
        )

        scaled = source.copy()
        for column in ("open", "high", "low", "close"):
            scaled[column] *= 10.0
        scaled_frame, scaled_columns = build_feature_frame(
            resample_complete_bars(scaled, 5), 5, "session_relative"
        )
        self.assertEqual(feature_columns, scaled_columns)
        np.testing.assert_allclose(
            frame[session_columns],
            scaled_frame[session_columns],
            rtol=1e-7,
            atol=3e-9,
            equal_nan=True,
        )

        change_timestamp = source.loc[25_000, "timestamp"]
        changed = source.copy()
        for column in ("open", "high", "low", "close"):
            changed.loc[changed["timestamp"] >= change_timestamp, column] += 100.0
        changed_frame, changed_columns = build_feature_frame(
            resample_complete_bars(changed, 5), 5, "session_relative"
        )
        self.assertEqual(feature_columns, changed_columns)
        prior_rows = frame["timestamp"] < change_timestamp.floor("5min")
        pd.testing.assert_frame_equal(
            frame.loc[prior_rows, session_columns],
            changed_frame.loc[prior_rows, session_columns],
        )

        config = TrainConfig(
            timeframes=(5,),
            feature_set="session_relative",
            max_train_rows=1_000,
            max_iter=5,
            min_samples_leaf=10,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            report = train_all_timeframes(source, output_dir, config)
            latest = predict_latest(source, output_dir)

        self.assertEqual(report["config"]["feature_set"], "session_relative")
        self.assertEqual(report["config"]["timeframes"], (5,))
        self.assertTrue(latest["probability_up"].between(0, 1).all())

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

    def test_tcn_sequence_features_are_causal_stationary_windows(self):
        source = m1_frame(400)
        bars = resample_complete_bars(source, 1)
        frame, feature_columns = build_feature_frame(bars, 1, "tcn_sequence")

        tcn_columns = [name for name in feature_columns if name.startswith("tcn_")]
        self.assertIn("tcn_return_atr_lag_0", tcn_columns)
        self.assertIn("tcn_body_atr_lag_15", tcn_columns)
        self.assertEqual(len(tcn_columns), 80)
        validate_stationary_feature_set(feature_columns)

        changed = source.copy()
        for column in ["open", "high", "low", "close"]:
            changed.loc[changed.index >= 200, column] += 100.0
        changed_bars = resample_complete_bars(changed, 1)
        changed_frame, changed_columns = build_feature_frame(
            changed_bars, 1, "tcn_sequence"
        )
        self.assertEqual(feature_columns, changed_columns)
        pd.testing.assert_frame_equal(
            frame.loc[:199, tcn_columns],
            changed_frame.loc[:199, tcn_columns],
        )

        flat_source = m1_frame(200)
        for column in ("open", "high", "low", "close"):
            flat_source[column] = 100.0
        flat_frame, _ = build_feature_frame(
            resample_complete_bars(flat_source, 1), 1, "tcn_sequence"
        )
        self.assertTrue(np.isfinite(flat_frame.loc[100:, tcn_columns]).all().all())
        self.assertTrue(flat_frame.loc[100:, tcn_columns].eq(0).all().all())

    def test_tcn_sequence_features_transfer_to_m5(self):
        source = m1_frame(6000)
        bars = resample_complete_bars(source, 5)
        frame, feature_columns = build_feature_frame(bars, 5, "tcn_sequence")
        tcn_columns = [name for name in feature_columns if name.startswith("tcn_")]

        self.assertEqual(len(feature_columns), 118)
        self.assertEqual(len(tcn_columns), 80)
        self.assertIn("tcn_return_atr_lag_0", tcn_columns)
        self.assertIn("tcn_wick_balance_atr_lag_15", tcn_columns)
        validate_stationary_feature_set(feature_columns)
        self.assertFalse({"open", "high", "low", "close"}.intersection(feature_columns))
        usable = frame[tcn_columns].dropna()
        self.assertGreater(len(usable), 0)
        self.assertTrue(np.isfinite(usable).all().all())

        scaled = source.copy()
        for column in ("open", "high", "low", "close"):
            scaled[column] *= 10.0
        scaled_frame, scaled_columns = build_feature_frame(
            resample_complete_bars(scaled, 5), 5, "tcn_sequence"
        )
        self.assertEqual(feature_columns, scaled_columns)
        np.testing.assert_allclose(
            frame[tcn_columns],
            scaled_frame[tcn_columns],
            rtol=1e-9,
            atol=1e-9,
            equal_nan=True,
        )

    def test_intrabar_manual_features_are_processed_and_causal(self):
        source = m1_frame(1500)
        bars = resample_complete_bars(source, 15)
        _, feature_columns = build_feature_frame(bars, 15, "intrabar_manual")

        self.assertIn("intrabar_return_std", feature_columns)
        self.assertIn("intrabar_up_fraction", feature_columns)
        self.assertIn("intrabar_body_directional_efficiency", feature_columns)
        self.assertIn("intrabar_late_minus_early", feature_columns)
        self.assertFalse({"open", "high", "low", "close"}.intersection(feature_columns))

        changed = source.copy()
        for column in ["open", "high", "low", "close"]:
            changed.loc[changed.index >= 60, column] += 100.0
        changed_bars = resample_complete_bars(changed, 15)
        intrabar_columns = [
            name for name in feature_columns if name.startswith("intrabar_")
        ]
        pd.testing.assert_frame_equal(
            bars.loc[:3, intrabar_columns],
            changed_bars.loc[:3, intrabar_columns],
        )

    def test_intrabar_manual_features_run_training_and_latest_prediction(self):
        source = m1_frame(5000)
        config = TrainConfig(
            timeframes=(15,),
            feature_set="intrabar_manual",
            max_train_rows=1_000,
            max_iter=5,
            min_samples_leaf=5,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            report = train_all_timeframes(source, output_dir, config)
            latest = predict_latest(source, output_dir)

        self.assertEqual(report["config"]["feature_set"], "intrabar_manual")
        self.assertEqual(int(latest.loc[0, "timeframe_minutes"]), 15)
        self.assertTrue(latest["probability_up"].between(0, 1).all())

    def test_intrabar_structure_features_are_stationary_and_run_latest_prediction(self):
        source = m1_frame(5000)
        bars = resample_complete_bars(source, 15)
        feature_frame, feature_columns = build_feature_frame(
            bars, 15, "intrabar_structure"
        )

        self.assertIn("intrabar_high_minus_low_position", feature_columns)
        self.assertIn("intrabar_direction_change_fraction", feature_columns)
        self.assertIn("intrabar_realized_variance_range", feature_columns)
        self.assertIn("intrabar_max_drawdown_atr_20", feature_columns)
        self.assertEqual(
            len([name for name in feature_columns if name.startswith("intrabar_")]),
            15,
        )
        validate_stationary_feature_set(feature_columns)

        changed = source.copy()
        for column in ["open", "high", "low", "close"]:
            changed.loc[changed.index >= 60, column] += 100.0
        changed_bars = resample_complete_bars(changed, 15)
        changed_features, changed_columns = build_feature_frame(
            changed_bars, 15, "intrabar_structure"
        )
        self.assertEqual(feature_columns, changed_columns)
        pd.testing.assert_frame_equal(
            feature_frame.loc[:3, feature_columns],
            changed_features.loc[:3, feature_columns],
        )

        config = TrainConfig(
            timeframes=(15,),
            feature_set="intrabar_structure",
            max_train_rows=1_000,
            max_iter=5,
            min_samples_leaf=5,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            report = train_all_timeframes(source, output_dir, config)
            latest = predict_latest(source, output_dir)

        self.assertEqual(report["config"]["feature_set"], "intrabar_structure")
        self.assertTrue(latest["probability_up"].between(0, 1).all())

    def test_intrabar_profile_features_capture_processed_completed_path(self):
        source = m1_frame(5000)
        bars = resample_complete_bars(source, 15)
        feature_frame, feature_columns = build_feature_frame(
            bars, 15, "intrabar_profile"
        )

        self.assertIn("intrabar_profile_level_20", feature_columns)
        self.assertIn("intrabar_profile_deviation_80", feature_columns)
        self.assertIn("intrabar_profile_rms_deviation", feature_columns)
        self.assertIn("intrabar_high_minus_low_position", feature_columns)
        self.assertEqual(
            len([name for name in feature_columns if name.startswith("intrabar_")]),
            27,
        )
        validate_stationary_feature_set(feature_columns)

        changed = source.copy()
        for column in ["open", "high", "low", "close"]:
            changed.loc[changed.index >= 60, column] += 100.0
        changed_bars = resample_complete_bars(changed, 15)
        changed_features, changed_columns = build_feature_frame(
            changed_bars, 15, "intrabar_profile"
        )
        self.assertEqual(feature_columns, changed_columns)
        pd.testing.assert_frame_equal(
            feature_frame.loc[:3, feature_columns],
            changed_features.loc[:3, feature_columns],
        )

        config = TrainConfig(
            timeframes=(15,),
            feature_set="intrabar_profile",
            max_train_rows=1_000,
            max_iter=5,
            min_samples_leaf=5,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            report = train_all_timeframes(source, output_dir, config)
            latest = predict_latest(source, output_dir)

        self.assertEqual(report["config"]["feature_set"], "intrabar_profile")
        self.assertTrue(latest["probability_up"].between(0, 1).all())

    def test_intrabar_profile_sampling_transfers_to_m5_and_m30(self):
        source = m1_frame(5000)
        profile_columns = [
            f"intrabar_profile_{kind}_{percentile}"
            for kind in ("level", "deviation")
            for percentile in (20, 40, 60, 80)
        ]
        for timeframe in (5, 30):
            bars = resample_complete_bars(source, timeframe)
            features, feature_columns = build_feature_frame(
                bars, timeframe, "intrabar_profile"
            )

            self.assertTrue(set(profile_columns).issubset(feature_columns))
            self.assertTrue(
                np.isfinite(features[profile_columns].to_numpy()).all()
            )
            validate_stationary_feature_set(feature_columns)

        flat_source = m1_frame(10)
        for column in ("open", "high", "low", "close"):
            flat_source[column] = 100.0
        flat_bars = resample_complete_bars(flat_source, 5)
        self.assertTrue(
            np.isfinite(flat_bars[profile_columns].to_numpy()).all()
        )
        self.assertTrue((flat_bars[profile_columns] == 0).all().all())
        self.assertTrue(
            np.isfinite(flat_bars["intrabar_realized_variance_range"]).all()
        )
        self.assertTrue(
            flat_bars["intrabar_realized_variance_range"].eq(0).all()
        )
        for column in (
            "intrabar_body_directional_efficiency",
            "intrabar_body_concentration",
            "intrabar_close_path_efficiency",
        ):
            self.assertTrue(np.isfinite(flat_bars[column]).all())
            self.assertTrue(flat_bars[column].eq(0).all())

    def test_intrabar_full_path_is_stationary_causal_finite_and_runs_latest(self):
        source = m1_frame(5000)
        bars = resample_complete_bars(source, 15)
        features, feature_columns = build_feature_frame(
            bars, 15, "intrabar_full_path"
        )
        full_path_columns = [
            f"intrabar_full_path_level_{point:02d}"
            for point in (1, 2, 4, 5, 7, 8, 10, 11, 13, 14, 15)
        ]

        self.assertTrue(set(full_path_columns).issubset(feature_columns))
        self.assertEqual(
            len([name for name in feature_columns if name.startswith("intrabar_")]),
            38,
        )
        self.assertTrue(np.isfinite(features[full_path_columns]).all().all())
        first_m15 = source.iloc[:15]
        first_scale = float(first_m15["high"].max() - first_m15["low"].min())
        expected_first_path = np.array(
            [
                (
                    float(first_m15.iloc[point - 1]["close"])
                    - float(first_m15.iloc[0]["open"])
                )
                / first_scale
                for point in (1, 2, 4, 5, 7, 8, 10, 11, 13, 14, 15)
            ]
        )
        np.testing.assert_allclose(
            bars.loc[0, full_path_columns].to_numpy(dtype="float64"),
            expected_first_path,
            rtol=1e-12,
            atol=1e-12,
        )
        validate_stationary_feature_set(feature_columns)

        scaled = source.copy()
        for column in ("open", "high", "low", "close"):
            scaled[column] *= 10
        scaled_features, scaled_columns = build_feature_frame(
            resample_complete_bars(scaled, 15), 15, "intrabar_full_path"
        )
        self.assertEqual(feature_columns, scaled_columns)
        np.testing.assert_allclose(
            features[full_path_columns],
            scaled_features[full_path_columns],
            rtol=1e-10,
            atol=1e-10,
        )

        changed = source.copy()
        for column in ("open", "high", "low", "close"):
            changed.loc[changed.index >= 60, column] += 100.0
        changed_features, changed_columns = build_feature_frame(
            resample_complete_bars(changed, 15), 15, "intrabar_full_path"
        )
        self.assertEqual(feature_columns, changed_columns)
        pd.testing.assert_frame_equal(
            features.loc[:3, feature_columns],
            changed_features.loc[:3, feature_columns],
        )

        flat_source = m1_frame(30)
        for column in ("open", "high", "low", "close"):
            flat_source[column] = 100.0
        flat_bars = resample_complete_bars(flat_source, 15)
        self.assertTrue(np.isfinite(flat_bars[full_path_columns]).all().all())
        self.assertTrue(flat_bars[full_path_columns].eq(0).all().all())

        config = TrainConfig(
            timeframes=(15,),
            feature_set="intrabar_full_path",
            max_train_rows=1_000,
            max_iter=5,
            min_samples_leaf=5,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            report = train_all_timeframes(source, output_dir, config)
            latest = predict_latest(source, output_dir)

        self.assertEqual(report["config"]["feature_set"], "intrabar_full_path")
        self.assertTrue(latest["probability_up"].between(0, 1).all())

    def test_intrabar_path_signature_is_order_sensitive_stationary_and_runs_latest(self):
        straight = np.linspace(1 / 15, 1, 15, dtype="float64")[None, :]
        np.testing.assert_allclose(
            intrabar_path_signature(straight),
            np.zeros((1, 3)),
            atol=1e-12,
        )
        np.testing.assert_allclose(
            intrabar_path_signature(np.array([[0.75]], dtype="float64")),
            np.zeros((1, 3)),
            atol=1e-12,
        )
        early_jump = np.ones((1, 15), dtype="float64")
        late_jump = np.zeros((1, 15), dtype="float64")
        late_jump[0, -1] = 1.0
        early_signature = intrabar_path_signature(early_jump)
        late_signature = intrabar_path_signature(late_jump)
        self.assertFalse(np.allclose(early_signature, late_signature))
        self.assertLess(float(early_signature[0, 0]), 0.0)
        self.assertGreater(float(late_signature[0, 0]), 0.0)

        source = m1_frame(5000)
        bars = resample_complete_bars(source, 15)
        features, feature_columns = build_feature_frame(
            bars, 15, "intrabar_path_signature"
        )
        signature_columns = list(INTRABAR_PATH_SIGNATURE_COLUMNS)
        self.assertTrue(set(signature_columns).issubset(feature_columns))
        self.assertEqual(
            len([name for name in feature_columns if name.startswith("intrabar_")]),
            41,
        )
        self.assertTrue(np.isfinite(features[signature_columns]).all().all())
        validate_stationary_feature_set(feature_columns)

        scaled = source.copy()
        for column in ("open", "high", "low", "close"):
            scaled[column] *= 10
        scaled_features, scaled_columns = build_feature_frame(
            resample_complete_bars(scaled, 15), 15, "intrabar_path_signature"
        )
        self.assertEqual(feature_columns, scaled_columns)
        np.testing.assert_allclose(
            features[signature_columns],
            scaled_features[signature_columns],
            rtol=1e-10,
            atol=1e-10,
        )

        changed = source.copy()
        for column in ("open", "high", "low", "close"):
            changed.loc[changed.index >= 60, column] += 100.0
        changed_features, changed_columns = build_feature_frame(
            resample_complete_bars(changed, 15), 15, "intrabar_path_signature"
        )
        self.assertEqual(feature_columns, changed_columns)
        pd.testing.assert_frame_equal(
            features.loc[:3, feature_columns],
            changed_features.loc[:3, feature_columns],
        )

        flat_source = m1_frame(30)
        for column in ("open", "high", "low", "close"):
            flat_source[column] = 100.0
        flat_bars = resample_complete_bars(flat_source, 15)
        self.assertTrue(np.isfinite(flat_bars[signature_columns]).all().all())
        self.assertTrue(flat_bars[signature_columns].eq(0).all().all())

        config = TrainConfig(
            timeframes=(15,),
            feature_set="intrabar_path_signature",
            max_train_rows=1_000,
            max_iter=5,
            min_samples_leaf=5,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            report = train_all_timeframes(source, output_dir, config)
            latest = predict_latest(source, output_dir)

        self.assertEqual(report["config"]["feature_set"], "intrabar_path_signature")
        self.assertTrue(latest["probability_up"].between(0, 1).all())

    def test_intrabar_pressure_features_are_stationary_causal_and_finite(self):
        source = m1_frame(5000)
        bars = resample_complete_bars(source, 15)
        features, feature_columns = build_feature_frame(
            bars, 15, "intrabar_pressure"
        )
        pressure_columns = [
            "intrabar_clv_mean",
            "intrabar_clv_std",
            "intrabar_early_clv_mean",
            "intrabar_late_clv_mean",
            "intrabar_clv_late_minus_early",
            "intrabar_range_weighted_clv",
            "intrabar_signed_range_pressure",
            "intrabar_wick_pressure",
            "intrabar_body_range_pressure",
            "intrabar_clv_body_divergence",
            "intrabar_clv_body_agreement",
        ]
        self.assertTrue(set(pressure_columns).issubset(feature_columns))
        self.assertEqual(
            len([name for name in feature_columns if name.startswith("intrabar_")]),
            38,
        )
        self.assertTrue(np.isfinite(features[pressure_columns].to_numpy()).all())
        validate_stationary_feature_set(feature_columns)

        scaled = source.copy()
        for column in ("open", "high", "low", "close"):
            scaled[column] *= 10
        scaled_features, scaled_columns = build_feature_frame(
            resample_complete_bars(scaled, 15), 15, "intrabar_pressure"
        )
        self.assertEqual(feature_columns, scaled_columns)
        np.testing.assert_allclose(
            features[pressure_columns],
            scaled_features[pressure_columns],
            rtol=1e-10,
            atol=1e-10,
        )

        changed = source.copy()
        for column in ("open", "high", "low", "close"):
            changed.loc[changed.index >= 60, column] += 100.0
        changed_features, changed_columns = build_feature_frame(
            resample_complete_bars(changed, 15), 15, "intrabar_pressure"
        )
        self.assertEqual(feature_columns, changed_columns)
        pd.testing.assert_frame_equal(
            features.loc[:3, feature_columns],
            changed_features.loc[:3, feature_columns],
        )

        flat_source = m1_frame(30)
        for column in ("open", "high", "low", "close"):
            flat_source[column] = 100.0
        flat_bars = resample_complete_bars(flat_source, 15)
        self.assertTrue(np.isfinite(flat_bars[pressure_columns]).all().all())
        self.assertTrue((flat_bars[pressure_columns] == 0).all().all())

        config = TrainConfig(
            timeframes=(15,),
            feature_set="intrabar_pressure",
            max_train_rows=1_000,
            max_iter=5,
            min_samples_leaf=5,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            report = train_all_timeframes(source, output_dir, config)
            latest = predict_latest(source, output_dir)

        self.assertEqual(report["config"]["feature_set"], "intrabar_pressure")
        self.assertTrue(latest["probability_up"].between(0, 1).all())

    def test_intrabar_volatility_shape_is_stationary_causal_and_finite(self):
        source = m1_frame(5000)
        bars = resample_complete_bars(source, 15)
        features, feature_columns = build_feature_frame(
            bars, 15, "intrabar_volatility_shape"
        )
        shape_columns = [
            "intrabar_range_concentration",
            "intrabar_range_top3_fraction",
            "intrabar_range_dispersion",
            "intrabar_range_center_of_mass",
            "intrabar_early_range_fraction",
            "intrabar_late_range_fraction",
            "intrabar_range_late_minus_early",
            "intrabar_variance_concentration",
            "intrabar_variance_top3_fraction",
            "intrabar_variance_center_of_mass",
            "intrabar_early_variance_fraction",
            "intrabar_late_variance_fraction",
            "intrabar_variance_late_minus_early",
            "intrabar_range_variance_concentration_gap",
        ]
        self.assertTrue(set(shape_columns).issubset(feature_columns))
        self.assertEqual(
            len([name for name in feature_columns if name.startswith("intrabar_")]),
            41,
        )
        self.assertTrue(np.isfinite(features[shape_columns].to_numpy()).all())
        validate_stationary_feature_set(feature_columns)

        scaled = source.copy()
        for column in ("open", "high", "low", "close"):
            scaled[column] *= 10
        scaled_features, scaled_columns = build_feature_frame(
            resample_complete_bars(scaled, 15), 15, "intrabar_volatility_shape"
        )
        self.assertEqual(feature_columns, scaled_columns)
        np.testing.assert_allclose(
            features[shape_columns],
            scaled_features[shape_columns],
            rtol=1e-10,
            atol=1e-10,
        )

        changed = source.copy()
        for column in ("open", "high", "low", "close"):
            changed.loc[changed.index >= 60, column] += 100.0
        changed_features, changed_columns = build_feature_frame(
            resample_complete_bars(changed, 15), 15, "intrabar_volatility_shape"
        )
        self.assertEqual(feature_columns, changed_columns)
        pd.testing.assert_frame_equal(
            features.loc[:3, feature_columns],
            changed_features.loc[:3, feature_columns],
        )

        flat_source = m1_frame(30)
        for column in ("open", "high", "low", "close"):
            flat_source[column] = 100.0
        flat_bars = resample_complete_bars(flat_source, 15)
        self.assertTrue(np.isfinite(flat_bars[shape_columns]).all().all())
        self.assertTrue((flat_bars[shape_columns] == 0).all().all())

        config = TrainConfig(
            timeframes=(15,),
            feature_set="intrabar_volatility_shape",
            max_train_rows=1_000,
            max_iter=5,
            min_samples_leaf=5,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            report = train_all_timeframes(source, output_dir, config)
            latest = predict_latest(source, output_dir)

        self.assertEqual(
            report["config"]["feature_set"], "intrabar_volatility_shape"
        )
        self.assertTrue(latest["probability_up"].between(0, 1).all())

    def test_intrabar_full_path_volatility_shape_union_is_stationary_and_runs_latest(self):
        source = m1_frame(5000)
        bars = resample_complete_bars(source, 15)
        features, feature_columns = build_feature_frame(
            bars, 15, "intrabar_full_path_volatility_shape"
        )
        union_columns = [
            name
            for name in feature_columns
            if name.startswith("intrabar_full_path_level_")
            or name
            in {
                "intrabar_range_concentration",
                "intrabar_range_top3_fraction",
                "intrabar_range_dispersion",
                "intrabar_range_center_of_mass",
                "intrabar_early_range_fraction",
                "intrabar_late_range_fraction",
                "intrabar_range_late_minus_early",
                "intrabar_variance_concentration",
                "intrabar_variance_top3_fraction",
                "intrabar_variance_center_of_mass",
                "intrabar_early_variance_fraction",
                "intrabar_late_variance_fraction",
                "intrabar_variance_late_minus_early",
                "intrabar_range_variance_concentration_gap",
            }
        ]

        self.assertEqual(len(union_columns), 25)
        self.assertEqual(
            len([name for name in feature_columns if name.startswith("intrabar_")]),
            52,
        )
        self.assertEqual(len(feature_columns), 90)
        self.assertTrue(np.isfinite(features[union_columns]).to_numpy().all())
        validate_stationary_feature_set(feature_columns)

        scaled = source.copy()
        for column in ("open", "high", "low", "close"):
            scaled[column] *= 10
        scaled_features, scaled_columns = build_feature_frame(
            resample_complete_bars(scaled, 15),
            15,
            "intrabar_full_path_volatility_shape",
        )
        self.assertEqual(feature_columns, scaled_columns)
        np.testing.assert_allclose(
            features[union_columns],
            scaled_features[union_columns],
            rtol=1e-10,
            atol=1e-10,
        )

        changed = source.copy()
        for column in ("open", "high", "low", "close"):
            changed.loc[changed.index >= 60, column] += 100.0
        changed_features, changed_columns = build_feature_frame(
            resample_complete_bars(changed, 15),
            15,
            "intrabar_full_path_volatility_shape",
        )
        self.assertEqual(feature_columns, changed_columns)
        pd.testing.assert_frame_equal(
            features.loc[:3, feature_columns],
            changed_features.loc[:3, feature_columns],
        )

        flat_source = m1_frame(30)
        for column in ("open", "high", "low", "close"):
            flat_source[column] = 100.0
        flat_bars = resample_complete_bars(flat_source, 15)
        self.assertTrue(np.isfinite(flat_bars[union_columns]).to_numpy().all())
        self.assertTrue(flat_bars[union_columns].eq(0).all().all())

        config = TrainConfig(
            timeframes=(15,),
            feature_set="intrabar_full_path_volatility_shape",
            max_train_rows=1_000,
            max_iter=5,
            min_samples_leaf=5,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            report = train_all_timeframes(source, output_dir, config)
            latest = predict_latest(source, output_dir)

        self.assertEqual(
            report["config"]["feature_set"],
            "intrabar_full_path_volatility_shape",
        )
        self.assertTrue(latest["probability_up"].between(0, 1).all())

    def test_intrabar_signed_variation_is_stationary_causal_and_finite(self):
        source = m1_frame(5000)
        bars = resample_complete_bars(source, 15)
        features, feature_columns = build_feature_frame(
            bars, 15, "intrabar_signed_variation"
        )
        signed_variation_columns = [
            "intrabar_upside_semivariance_fraction",
            "intrabar_downside_semivariance_fraction",
            "intrabar_semivariance_imbalance",
            "intrabar_semivariance_entropy",
            "intrabar_upside_variance_concentration",
            "intrabar_downside_variance_concentration",
            "intrabar_upside_variance_center_of_mass",
            "intrabar_downside_variance_center_of_mass",
            "intrabar_semivariance_timing_spread",
            "intrabar_bipower_variation_ratio",
            "intrabar_jump_variation_fraction",
            "intrabar_signed_largest_jump_fraction",
            "intrabar_continuous_semivariance_imbalance",
            "intrabar_semivariance_imbalance_late_minus_early",
        ]
        self.assertTrue(set(signed_variation_columns).issubset(feature_columns))
        self.assertEqual(
            len([name for name in feature_columns if name.startswith("intrabar_")]),
            55,
        )
        self.assertTrue(
            np.isfinite(features[signed_variation_columns].to_numpy()).all()
        )
        validate_stationary_feature_set(feature_columns)
        nonzero_variance = bars[
            [
                "intrabar_upside_semivariance_fraction",
                "intrabar_downside_semivariance_fraction",
            ]
        ].sum(axis=1).gt(0)
        np.testing.assert_allclose(
            bars.loc[nonzero_variance, "intrabar_upside_semivariance_fraction"]
            + bars.loc[
                nonzero_variance, "intrabar_downside_semivariance_fraction"
            ],
            1.0,
            rtol=1e-12,
            atol=1e-12,
        )
        self.assertTrue(
            bars["intrabar_semivariance_entropy"].between(0, 1).all()
        )
        self.assertTrue(
            bars["intrabar_jump_variation_fraction"].between(0, 1).all()
        )

        scaled = source.copy()
        for column in ("open", "high", "low", "close"):
            scaled[column] *= 10
        scaled_features, scaled_columns = build_feature_frame(
            resample_complete_bars(scaled, 15), 15, "intrabar_signed_variation"
        )
        self.assertEqual(feature_columns, scaled_columns)
        np.testing.assert_allclose(
            features[signed_variation_columns],
            scaled_features[signed_variation_columns],
            rtol=1e-10,
            atol=1e-10,
        )

        changed = source.copy()
        for column in ("open", "high", "low", "close"):
            changed.loc[changed.index >= 60, column] += 100.0
        changed_features, changed_columns = build_feature_frame(
            resample_complete_bars(changed, 15), 15, "intrabar_signed_variation"
        )
        self.assertEqual(feature_columns, changed_columns)
        pd.testing.assert_frame_equal(
            features.loc[:3, feature_columns],
            changed_features.loc[:3, feature_columns],
        )

        flat_source = m1_frame(30)
        for column in ("open", "high", "low", "close"):
            flat_source[column] = 100.0
        flat_bars = resample_complete_bars(flat_source, 15)
        self.assertTrue(
            np.isfinite(flat_bars[signed_variation_columns]).all().all()
        )
        self.assertTrue(
            (flat_bars[signed_variation_columns] == 0).all().all()
        )

        config = TrainConfig(
            timeframes=(15,),
            feature_set="intrabar_signed_variation",
            max_train_rows=1_000,
            max_iter=5,
            min_samples_leaf=5,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            report = train_all_timeframes(source, output_dir, config)
            latest = predict_latest(source, output_dir)

        self.assertEqual(
            report["config"]["feature_set"], "intrabar_signed_variation"
        )
        self.assertTrue(latest["probability_up"].between(0, 1).all())

    def test_intrabar_frequency_shape_is_stationary_causal_and_finite(self):
        source = m1_frame(5000)
        bars = resample_complete_bars(source, 15)
        features, feature_columns = build_feature_frame(
            bars, 15, "intrabar_frequency_shape"
        )
        frequency_columns = [
            "intrabar_return_dct_energy_fraction_1",
            "intrabar_return_dct_energy_fraction_2",
            "intrabar_return_dct_energy_fraction_3",
            "intrabar_return_dct_energy_fraction_4",
            "intrabar_return_low_frequency_fraction",
            "intrabar_return_mid_frequency_fraction",
            "intrabar_return_high_frequency_fraction",
            "intrabar_return_low_high_frequency_balance",
            "intrabar_return_autocorrelation_1",
            "intrabar_return_autocorrelation_2",
            "intrabar_return_autocorrelation_3",
            "intrabar_range_low_frequency_fraction",
        ]
        self.assertTrue(set(frequency_columns).issubset(feature_columns))
        self.assertEqual(
            len([name for name in feature_columns if name.startswith("intrabar_")]),
            53,
        )
        self.assertTrue(np.isfinite(features[frequency_columns].to_numpy()).all())
        validate_stationary_feature_set(feature_columns)
        for column in [
            *frequency_columns[:7],
            frequency_columns[-1],
        ]:
            self.assertTrue(features[column].between(0, 1).all())
        for column in frequency_columns[7:11]:
            self.assertTrue(features[column].between(-1, 1).all())
        nonzero_centered_energy = features[
            [
                "intrabar_return_low_frequency_fraction",
                "intrabar_return_mid_frequency_fraction",
                "intrabar_return_high_frequency_fraction",
            ]
        ].sum(axis=1).gt(0)
        np.testing.assert_allclose(
            features.loc[
                nonzero_centered_energy,
                [
                    "intrabar_return_low_frequency_fraction",
                    "intrabar_return_mid_frequency_fraction",
                    "intrabar_return_high_frequency_fraction",
                ],
            ].sum(axis=1),
            1.0,
            rtol=1e-10,
            atol=1e-10,
        )

        scaled = source.copy()
        for column in ("open", "high", "low", "close"):
            scaled[column] *= 10
        scaled_features, scaled_columns = build_feature_frame(
            resample_complete_bars(scaled, 15), 15, "intrabar_frequency_shape"
        )
        self.assertEqual(feature_columns, scaled_columns)
        np.testing.assert_allclose(
            features[frequency_columns],
            scaled_features[frequency_columns],
            rtol=1e-9,
            atol=1e-9,
        )

        changed = source.copy()
        for column in ("open", "high", "low", "close"):
            changed.loc[changed.index >= 60, column] += 100.0
        changed_features, changed_columns = build_feature_frame(
            resample_complete_bars(changed, 15), 15, "intrabar_frequency_shape"
        )
        self.assertEqual(feature_columns, changed_columns)
        pd.testing.assert_frame_equal(
            features.loc[:3, feature_columns],
            changed_features.loc[:3, feature_columns],
        )

        flat_source = m1_frame(30)
        for column in ("open", "high", "low", "close"):
            flat_source[column] = 100.0
        flat_bars = resample_complete_bars(flat_source, 15)
        self.assertTrue(np.isfinite(flat_bars[frequency_columns]).all().all())
        self.assertTrue((flat_bars[frequency_columns] == 0).all().all())

        config = TrainConfig(
            timeframes=(15,),
            feature_set="intrabar_frequency_shape",
            max_train_rows=1_000,
            max_iter=5,
            min_samples_leaf=5,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            report = train_all_timeframes(source, output_dir, config)
            latest = predict_latest(source, output_dir)

        self.assertEqual(report["config"]["feature_set"], "intrabar_frequency_shape")
        self.assertTrue(latest["probability_up"].between(0, 1).all())

    def test_intrabar_ordinal_shape_is_exact_stationary_causal_and_finite(self):
        timestamps = pd.date_range(
            "2024-01-01 00:00:00+00:00", periods=30, freq="min"
        )
        returns = np.r_[
            np.full(15, 0.0001),
            np.linspace(0.0001, 0.0015, 15),
        ]
        close = 100.0 * np.exp(np.cumsum(returns))
        open_ = np.r_[100.0, close[:-1]]
        ordered_source = pd.DataFrame(
            {
                "timestamp": timestamps,
                "open": open_,
                "high": np.maximum(open_, close) + 0.001,
                "low": np.minimum(open_, close) - 0.001,
                "close": close,
            }
        )
        ordered_bars = resample_complete_bars(ordered_source, 15)
        ordered = ordered_bars.iloc[-1]
        self.assertAlmostEqual(
            ordered["intrabar_ordinal_pattern_012_fraction"], 1.0
        )
        for pattern in ("021", "102", "120", "201", "210"):
            self.assertAlmostEqual(
                ordered[f"intrabar_ordinal_pattern_{pattern}_fraction"], 0.0
            )
        self.assertAlmostEqual(ordered["intrabar_ordinal_pattern_entropy"], 0.0)

        source = m1_frame(5000)
        bars = resample_complete_bars(source, 15)
        features, feature_columns = build_feature_frame(
            bars, 15, "intrabar_ordinal_shape"
        )
        ordinal_columns = [
            "intrabar_ordinal_pattern_012_fraction",
            "intrabar_ordinal_pattern_021_fraction",
            "intrabar_ordinal_pattern_102_fraction",
            "intrabar_ordinal_pattern_120_fraction",
            "intrabar_ordinal_pattern_201_fraction",
            "intrabar_ordinal_pattern_210_fraction",
            "intrabar_ordinal_pattern_entropy",
        ]
        pattern_columns = ordinal_columns[:-1]
        self.assertTrue(set(ordinal_columns).issubset(feature_columns))
        self.assertEqual(
            len([name for name in feature_columns if name.startswith("intrabar_")]),
            48,
        )
        self.assertTrue(np.isfinite(features[ordinal_columns]).all().all())
        self.assertTrue(features[ordinal_columns].ge(0).all().all())
        self.assertTrue(features[ordinal_columns].le(1).all().all())
        np.testing.assert_allclose(
            features[pattern_columns].sum(axis=1),
            1.0,
            rtol=1e-10,
            atol=1e-10,
        )
        validate_stationary_feature_set(feature_columns)

        scaled = source.copy()
        for column in ("open", "high", "low", "close"):
            scaled[column] *= 10
        scaled_features, scaled_columns = build_feature_frame(
            resample_complete_bars(scaled, 15), 15, "intrabar_ordinal_shape"
        )
        self.assertEqual(feature_columns, scaled_columns)
        np.testing.assert_allclose(
            features[ordinal_columns],
            scaled_features[ordinal_columns],
            rtol=1e-10,
            atol=1e-10,
        )

        changed = source.copy()
        for column in ("open", "high", "low", "close"):
            changed.loc[changed.index >= 60, column] += 100.0
        changed_features, changed_columns = build_feature_frame(
            resample_complete_bars(changed, 15), 15, "intrabar_ordinal_shape"
        )
        self.assertEqual(feature_columns, changed_columns)
        pd.testing.assert_frame_equal(
            features.loc[:3, feature_columns],
            changed_features.loc[:3, feature_columns],
        )

        flat_source = m1_frame(30)
        for column in ("open", "high", "low", "close"):
            flat_source[column] = 100.0
        flat_bars = resample_complete_bars(flat_source, 15)
        self.assertTrue(np.isfinite(flat_bars[ordinal_columns]).all().all())
        self.assertTrue(flat_bars[ordinal_columns].eq(0).all().all())

        config = TrainConfig(
            timeframes=(15,),
            feature_set="intrabar_ordinal_shape",
            max_train_rows=1_000,
            max_iter=5,
            min_samples_leaf=5,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            report = train_all_timeframes(source, output_dir, config)
            latest = predict_latest(source, output_dir)

        self.assertEqual(report["config"]["feature_set"], "intrabar_ordinal_shape")
        self.assertTrue(latest["probability_up"].between(0, 1).all())

    def test_intrabar_distribution_shape_is_stationary_causal_and_finite(self):
        source = m1_frame(5000)
        bars = resample_complete_bars(source, 15)
        features, feature_columns = build_feature_frame(
            bars, 15, "intrabar_distribution_shape"
        )
        distribution_columns = [
            "intrabar_return_quantile_10_rms",
            "intrabar_return_quantile_25_rms",
            "intrabar_return_quantile_50_rms",
            "intrabar_return_quantile_75_rms",
            "intrabar_return_quantile_90_rms",
            "intrabar_return_bowley_skew",
            "intrabar_return_tail_skew",
            "intrabar_return_central_spread_fraction",
            "intrabar_return_mad_rms",
        ]
        self.assertTrue(set(distribution_columns).issubset(feature_columns))
        self.assertEqual(
            len([name for name in feature_columns if name.startswith("intrabar_")]),
            50,
        )
        self.assertTrue(np.isfinite(features[distribution_columns]).all().all())
        validate_stationary_feature_set(feature_columns)
        self.assertTrue(
            features["intrabar_return_central_spread_fraction"].between(0, 1).all()
        )

        scaled = source.copy()
        for column in ("open", "high", "low", "close"):
            scaled[column] *= 10
        scaled_features, scaled_columns = build_feature_frame(
            resample_complete_bars(scaled, 15), 15, "intrabar_distribution_shape"
        )
        self.assertEqual(feature_columns, scaled_columns)
        np.testing.assert_allclose(
            features[distribution_columns],
            scaled_features[distribution_columns],
            rtol=1e-8,
            atol=1e-8,
        )

        changed = source.copy()
        for column in ("open", "high", "low", "close"):
            changed.loc[changed.index >= 60, column] += 100.0
        changed_features, changed_columns = build_feature_frame(
            resample_complete_bars(changed, 15), 15, "intrabar_distribution_shape"
        )
        self.assertEqual(feature_columns, changed_columns)
        pd.testing.assert_frame_equal(
            features.loc[:3, feature_columns],
            changed_features.loc[:3, feature_columns],
        )

        flat_source = m1_frame(30)
        for column in ("open", "high", "low", "close"):
            flat_source[column] = 100.0
        flat_bars = resample_complete_bars(flat_source, 15)
        self.assertTrue(np.isfinite(flat_bars[distribution_columns]).all().all())
        self.assertTrue((flat_bars[distribution_columns] == 0).all().all())

        config = TrainConfig(
            timeframes=(15,),
            feature_set="intrabar_distribution_shape",
            max_train_rows=1_000,
            max_iter=5,
            min_samples_leaf=5,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            report = train_all_timeframes(source, output_dir, config)
            latest = predict_latest(source, output_dir)

        self.assertEqual(
            report["config"]["feature_set"], "intrabar_distribution_shape"
        )
        self.assertTrue(latest["probability_up"].between(0, 1).all())

    def test_intrabar_flow_shape_is_stationary_causal_and_finite(self):
        source = m1_frame(5000)
        bars = resample_complete_bars(source, 15)
        features, feature_columns = build_feature_frame(
            bars, 15, "intrabar_flow_shape"
        )
        flow_columns = [
            "intrabar_clv_mean",
            "intrabar_clv_std",
            "intrabar_early_clv_mean",
            "intrabar_late_clv_mean",
            "intrabar_clv_late_minus_early",
            "intrabar_range_weighted_clv",
            "intrabar_signed_range_pressure",
            "intrabar_wick_pressure",
            "intrabar_body_range_pressure",
            "intrabar_clv_body_divergence",
            "intrabar_clv_body_agreement",
            "intrabar_range_concentration",
            "intrabar_range_top3_fraction",
            "intrabar_range_dispersion",
            "intrabar_range_center_of_mass",
            "intrabar_early_range_fraction",
            "intrabar_late_range_fraction",
            "intrabar_range_late_minus_early",
            "intrabar_variance_concentration",
            "intrabar_variance_top3_fraction",
            "intrabar_variance_center_of_mass",
            "intrabar_early_variance_fraction",
            "intrabar_late_variance_fraction",
            "intrabar_variance_late_minus_early",
            "intrabar_range_variance_concentration_gap",
        ]
        self.assertTrue(set(flow_columns).issubset(feature_columns))
        self.assertEqual(
            len([name for name in feature_columns if name.startswith("intrabar_")]),
            52,
        )
        self.assertTrue(np.isfinite(features[flow_columns]).all().all())
        validate_stationary_feature_set(feature_columns)

        scaled = source.copy()
        for column in ("open", "high", "low", "close"):
            scaled[column] *= 10
        scaled_features, scaled_columns = build_feature_frame(
            resample_complete_bars(scaled, 15), 15, "intrabar_flow_shape"
        )
        self.assertEqual(feature_columns, scaled_columns)
        np.testing.assert_allclose(
            features[flow_columns],
            scaled_features[flow_columns],
            rtol=1e-8,
            atol=1e-8,
        )

        changed = source.copy()
        for column in ("open", "high", "low", "close"):
            changed.loc[changed.index >= 60, column] += 100.0
        changed_features, changed_columns = build_feature_frame(
            resample_complete_bars(changed, 15), 15, "intrabar_flow_shape"
        )
        self.assertEqual(feature_columns, changed_columns)
        pd.testing.assert_frame_equal(
            features.loc[:3, feature_columns],
            changed_features.loc[:3, feature_columns],
        )

        flat_source = m1_frame(30)
        for column in ("open", "high", "low", "close"):
            flat_source[column] = 100.0
        flat_bars = resample_complete_bars(flat_source, 15)
        self.assertTrue(np.isfinite(flat_bars[flow_columns]).all().all())
        self.assertTrue((flat_bars[flow_columns] == 0).all().all())

        config = TrainConfig(
            timeframes=(15,),
            feature_set="intrabar_flow_shape",
            max_train_rows=1_000,
            max_iter=5,
            min_samples_leaf=5,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            report = train_all_timeframes(source, output_dir, config)
            latest = predict_latest(source, output_dir)

        self.assertEqual(report["config"]["feature_set"], "intrabar_flow_shape")
        self.assertTrue(latest["probability_up"].between(0, 1).all())

    def test_intrabar_breakout_state_is_exact_stationary_causal_and_finite(self):
        breakout_columns = [
            "intrabar_close_breakout_up_fraction",
            "intrabar_close_breakout_down_fraction",
            "intrabar_high_rejection_fraction",
            "intrabar_low_rejection_fraction",
            "intrabar_inside_bar_fraction",
            "intrabar_outside_bar_fraction",
            "intrabar_range_expansion_fraction",
            "intrabar_upward_range_expansion_fraction",
            "intrabar_downward_range_expansion_fraction",
            "intrabar_direction_continuation_fraction",
            "intrabar_direction_reversal_fraction",
            "intrabar_signed_run_length_imbalance",
        ]
        event_source = pd.DataFrame(
            {
                "timestamp": pd.date_range(
                    "2024-01-01", periods=6, freq="min", tz="UTC"
                ),
                "open": [100.0, 100.5, 101.2, 100.8, 100.9, 101.0],
                "high": [101.0, 101.5, 102.0, 101.5, 102.0, 101.2],
                "low": [99.5, 100.2, 100.5, 100.6, 100.0, 99.8],
                "close": [100.5, 101.2, 100.8, 100.9, 101.0, 99.9],
            }
        )
        event_bar = resample_complete_bars(event_source, 6).iloc[0]
        expected = {
            "intrabar_close_breakout_up_fraction": 1 / 5,
            "intrabar_close_breakout_down_fraction": 1 / 5,
            "intrabar_high_rejection_fraction": 2 / 5,
            "intrabar_low_rejection_fraction": 1 / 5,
            "intrabar_inside_bar_fraction": 1 / 5,
            "intrabar_outside_bar_fraction": 1 / 5,
            "intrabar_range_expansion_fraction": 2 / 5,
            "intrabar_upward_range_expansion_fraction": 1 / 5,
            "intrabar_downward_range_expansion_fraction": 1 / 5,
            "intrabar_direction_continuation_fraction": 2 / 5,
            "intrabar_direction_reversal_fraction": 3 / 5,
            "intrabar_signed_run_length_imbalance": 1 / 6,
        }
        for column, value in expected.items():
            self.assertAlmostEqual(event_bar[column], value)

        source = m1_frame(5000)
        bars = resample_complete_bars(source, 15)
        features, feature_columns = build_feature_frame(
            bars, 15, "intrabar_breakout_state"
        )
        self.assertTrue(set(breakout_columns).issubset(feature_columns))
        self.assertEqual(
            len([name for name in feature_columns if name.startswith("intrabar_")]),
            39,
        )
        self.assertTrue(np.isfinite(features[breakout_columns]).all().all())
        self.assertTrue(
            features[breakout_columns[:-1]].ge(0).all().all()
        )
        self.assertTrue(
            features[breakout_columns[:-1]].le(1).all().all()
        )
        self.assertTrue(
            features["intrabar_signed_run_length_imbalance"].between(-1, 1).all()
        )
        validate_stationary_feature_set(feature_columns)

        scaled = source.copy()
        for column in ("open", "high", "low", "close"):
            scaled[column] *= 10
        scaled_features, scaled_columns = build_feature_frame(
            resample_complete_bars(scaled, 15), 15, "intrabar_breakout_state"
        )
        self.assertEqual(feature_columns, scaled_columns)
        np.testing.assert_allclose(
            features[breakout_columns],
            scaled_features[breakout_columns],
            rtol=0,
            atol=0,
        )

        changed = source.copy()
        for column in ("open", "high", "low", "close"):
            changed.loc[changed.index >= 60, column] += 100.0
        changed_features, changed_columns = build_feature_frame(
            resample_complete_bars(changed, 15), 15, "intrabar_breakout_state"
        )
        self.assertEqual(feature_columns, changed_columns)
        pd.testing.assert_frame_equal(
            features.loc[:3, feature_columns],
            changed_features.loc[:3, feature_columns],
        )

        flat_source = m1_frame(30)
        for column in ("open", "high", "low", "close"):
            flat_source[column] = 100.0
        flat_bars = resample_complete_bars(flat_source, 15)
        self.assertTrue(np.isfinite(flat_bars[breakout_columns]).all().all())
        self.assertTrue((flat_bars[breakout_columns] == 0).all().all())

        config = TrainConfig(
            timeframes=(15,),
            feature_set="intrabar_breakout_state",
            max_train_rows=1_000,
            max_iter=5,
            min_samples_leaf=5,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            report = train_all_timeframes(source, output_dir, config)
            latest = predict_latest(source, output_dir)

        self.assertEqual(
            report["config"]["feature_set"], "intrabar_breakout_state"
        )
        self.assertTrue(latest["probability_up"].between(0, 1).all())

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
        self.assertAlmostEqual(
            row["next_bar_directional_clarity"],
            abs(following["close"] - following["open"])
            / (following["high"] - following["low"]),
        )
        close_location = (following["close"] - following["low"]) / (
            following["high"] - following["low"]
        )
        direction_aligned_close_location = (
            close_location
            if following["close"] > following["open"]
            else 1.0 - close_location
        )
        self.assertAlmostEqual(
            row["next_bar_directional_follow_through"],
            row["next_bar_directional_clarity"]
            * direction_aligned_close_location,
        )
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
            walk_forward_predictions = pd.read_parquet(
                output_dir / "m1_walk_forward_predictions.parquet"
            )
            split_directories = []
            manifest = json.loads(
                (output_dir / "manifest.json").read_text(encoding="utf-8")
            )
            for fold in ("wf1", "wf2"):
                split_directory = output_dir / f"split_{fold}"
                split_directory.mkdir()
                split_directories.append(split_directory)
                (split_directory / "manifest.json").write_text(
                    json.dumps(manifest), encoding="utf-8"
                )
                walk_forward_predictions.loc[
                    walk_forward_predictions["fold"].eq(fold)
                ].to_parquet(
                    split_directory / "m1_walk_forward_predictions.parquet",
                    index=False,
                )
            combined_odds = build_walk_forward_odds_calibration(
                split_directories,
                output_dir / "combined_odds_calibration.json",
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
            self.assertEqual(
                combined_odds["_meta"]["source"],
                [str(directory) for directory in split_directories],
            )
            self.assertEqual(
                combined_odds["M1"]["nested_validation"]["selected_metrics"][
                    "rows"
                ],
                int(walk_forward_predictions["fold"].eq("wf2").sum()),
            )
            with self.assertRaisesRegex(ValueError, "overlap"):
                build_walk_forward_odds_calibration(
                    [split_directories[0], split_directories[0]],
                    output_dir / "overlapping_odds_calibration.json",
                    OddsCalibrationConfig(
                        bins=3, min_support=10, prior_strength=10
                    ),
                )

    def test_fixed_training_window_excludes_older_rows(self):
        source = m1_frame(5000)
        config = TrainConfig(
            timeframes=(1,),
            train_window_days=1,
            max_train_rows=2_000,
            max_iter=5,
            min_samples_leaf=10,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            report = train_all_timeframes(source, Path(temp_dir), config)

        train_end = pd.Timestamp(report["split_boundaries"]["train_end"])
        train_start = pd.Timestamp(
            report["timeframes"]["M1"]["split_ranges"]["train"]["decision_start"]
        )
        self.assertGreaterEqual(train_start, train_end - pd.Timedelta(days=1))
        self.assertEqual(report["timeframes"]["M1"]["train_window_days"], 1)

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

    def test_tcn_round_trips_through_saved_latest_prediction(self):
        source = m1_frame(1800)
        config = TrainConfig(
            timeframes=(1,),
            feature_set="tcn_sequence",
            model_type="tcn",
            max_train_rows=1_000,
            tcn_epochs=1,
            tcn_batch_size=128,
            tcn_hidden_channels=4,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            report = train_all_timeframes(source, output_dir, config)
            latest = predict_latest(source, output_dir)

        diagnostics = report["timeframes"]["M1"]["model_diagnostics"]
        self.assertEqual(report["config"]["model_type"], "tcn")
        self.assertEqual(diagnostics["sequence_length"], 16)
        self.assertEqual(diagnostics["hidden_channels"], 4)
        self.assertGreater(diagnostics["parameter_count"], 0)
        self.assertEqual(len(diagnostics["training_loss"]), 1)
        self.assertTrue(latest["probability_up"].between(0, 1).all())

    def test_module_entrypoint_saves_portable_artifacts(self):
        source = m1_frame(1800)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(__file__).resolve().parents[1]
            input_path = Path(temp_dir) / "m1.parquet"
            output_dir = Path(temp_dir) / "model"
            latest_path = Path(temp_dir) / "latest.json"
            source.to_parquet(input_path, index=False)
            environment = os.environ.copy()
            environment["PYTHONPATH"] = str(root / "src")
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "trade_data.next_bar",
                    "train-evaluate",
                    "--input",
                    str(input_path),
                    "--output-dir",
                    str(output_dir),
                    "--timeframes",
                    "1",
                    "--max-train-rows",
                    "1000",
                    "--max-iter",
                    "5",
                ],
                cwd=root,
                env=environment,
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "trade_data.next_bar",
                    "predict-latest",
                    "--input",
                    str(input_path),
                    "--model-dir",
                    str(output_dir),
                    "--output",
                    str(latest_path),
                ],
                cwd=root,
                env=environment,
                check=True,
                capture_output=True,
                text=True,
            )
            latest = json.loads(latest_path.read_text(encoding="utf-8"))

        self.assertTrue(all(0 <= row["probability_up"] <= 1 for row in latest))

    def test_causal_transformer_round_trips_through_saved_latest_prediction(self):
        source = m1_frame(1800)
        config = TrainConfig(
            timeframes=(1,),
            feature_set="tcn_sequence",
            model_type="causal_transformer",
            max_train_rows=1_000,
            transformer_epochs=1,
            transformer_batch_size=128,
            transformer_model_dimension=8,
            transformer_attention_heads=2,
            transformer_encoder_layers=1,
            transformer_feedforward_dimension=16,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "first"
            repeat_dir = Path(temp_dir) / "repeat"
            report = train_all_timeframes(source, output_dir, config)
            train_all_timeframes(source, repeat_dir, config)
            latest = predict_latest(source, output_dir)
            first_predictions = pd.read_parquet(
                output_dir / "m1_test_predictions.parquet"
            )
            repeat_predictions = pd.read_parquet(
                repeat_dir / "m1_test_predictions.parquet"
            )

        diagnostics = report["timeframes"]["M1"]["model_diagnostics"]
        self.assertEqual(report["config"]["model_type"], "causal_transformer")
        self.assertEqual(diagnostics["sequence_length"], 16)
        self.assertEqual(diagnostics["model_dimension"], 8)
        self.assertEqual(diagnostics["attention_heads"], 2)
        self.assertEqual(diagnostics["dropout"], 0.0)
        self.assertGreater(diagnostics["parameter_count"], 0)
        self.assertEqual(len(diagnostics["training_loss"]), 1)
        self.assertTrue(latest["probability_up"].between(0, 1).all())
        np.testing.assert_allclose(
            first_predictions["raw_probability_up"],
            repeat_predictions["raw_probability_up"],
            rtol=0,
            atol=0,
        )

    def test_causal_gru_round_trips_through_saved_latest_prediction(self):
        source = m1_frame(1800)
        config = TrainConfig(
            timeframes=(1,),
            feature_set="tcn_sequence",
            model_type="causal_gru",
            max_train_rows=1_000,
            tcn_epochs=1,
            tcn_batch_size=128,
            tcn_hidden_channels=4,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "first"
            repeat_dir = Path(temp_dir) / "repeat"
            report = train_all_timeframes(source, output_dir, config)
            train_all_timeframes(source, repeat_dir, config)
            latest = predict_latest(source, output_dir)
            first_predictions = pd.read_parquet(
                output_dir / "m1_test_predictions.parquet"
            )
            repeat_predictions = pd.read_parquet(
                repeat_dir / "m1_test_predictions.parquet"
            )

        diagnostics = report["timeframes"]["M1"]["model_diagnostics"]
        self.assertEqual(report["config"]["model_type"], "causal_gru")
        self.assertEqual(diagnostics["sequence_length"], 16)
        self.assertEqual(diagnostics["hidden_channels"], 4)
        self.assertEqual(diagnostics["parameter_count"], 137)
        self.assertEqual(len(diagnostics["training_loss"]), 1)
        self.assertTrue(latest["probability_up"].between(0, 1).all())
        np.testing.assert_allclose(
            first_predictions["raw_probability_up"],
            repeat_predictions["raw_probability_up"],
            rtol=0,
            atol=0,
        )

    def test_logistic_uses_the_same_processed_feature_pipeline(self):
        source = m1_frame(1800)
        config = TrainConfig(
            timeframes=(1,),
            model_type="logistic",
            max_train_rows=1_000,
            max_iter=20,
            logistic_c=0.10,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            report = train_all_timeframes(source, output_dir, config)

            self.assertEqual(report["config"]["model_type"], "logistic")
            self.assertEqual(report["config"]["logistic_c"], 0.10)
            self.assertTrue((output_dir / "m1_model.joblib").exists())

    def test_extra_trees_uses_the_same_processed_feature_pipeline(self):
        source = m1_frame(1800)
        config = TrainConfig(
            timeframes=(1,),
            model_type="extra_trees",
            max_train_rows=1_000,
            extra_trees_estimators=5,
            extra_trees_max_depth=4,
            extra_trees_min_samples_leaf=10,
            extra_trees_max_features=0.75,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            report = train_all_timeframes(source, output_dir, config)

            self.assertEqual(report["config"]["model_type"], "extra_trees")
            self.assertEqual(report["config"]["extra_trees_estimators"], 5)
            self.assertTrue((output_dir / "m1_model.joblib").exists())

    def test_xgboost_round_trips_through_processed_latest_prediction(self):
        source = m1_frame(1800)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(__file__).resolve().parents[1]
            input_path = Path(temp_dir) / "m1.parquet"
            output_dir = Path(temp_dir) / "model"
            latest_path = Path(temp_dir) / "latest.json"
            source.to_parquet(input_path, index=False)
            environment = os.environ.copy()
            environment["PYTHONPATH"] = str(root / "src")
            subprocess.run(
                [
                    sys.executable,
                    str(root / "methods/next_bar/scripts/run.py"),
                    "train-evaluate",
                    "--input",
                    str(input_path),
                    "--output-dir",
                    str(output_dir),
                    "--timeframes",
                    "1",
                    "--model-type",
                    "xgboost",
                    "--max-train-rows",
                    "1000",
                    "--xgboost-estimators",
                    "5",
                    "--xgboost-max-depth",
                    "2",
                    "--xgboost-learning-rate",
                    "0.05",
                    "--xgboost-min-child-weight",
                    "5",
                ],
                cwd=root,
                env=environment,
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                [
                    sys.executable,
                    str(root / "methods/next_bar/scripts/run.py"),
                    "predict-latest",
                    "--input",
                    str(input_path),
                    "--model-dir",
                    str(output_dir),
                    "--output",
                    str(latest_path),
                ],
                cwd=root,
                env=environment,
                check=True,
                capture_output=True,
                text=True,
            )
            report = json.loads(
                (output_dir / "metrics.json").read_text(encoding="utf-8")
            )
            latest = json.loads(latest_path.read_text(encoding="utf-8"))
            manifest = json.loads(
                (output_dir / "manifest.json").read_text(encoding="utf-8")
            )

        self.assertEqual(report["config"]["model_type"], "xgboost")
        self.assertEqual(report["config"]["xgboost_estimators"], 5)
        self.assertFalse(
            {"open", "high", "low", "close"}.intersection(
                manifest["timeframes"]["M1"]["features"]
            )
        )
        self.assertTrue(all(0 <= row["probability_up"] <= 1 for row in latest))

    def test_catboost_round_trips_through_processed_latest_prediction(self):
        source = m1_frame(1800)
        config = TrainConfig(
            timeframes=(1,),
            model_type="catboost",
            max_train_rows=1_000,
            catboost_iterations=5,
            catboost_depth=2,
            catboost_learning_rate=0.05,
            catboost_l2=5.0,
            catboost_random_strength=1.0,
            catboost_bagging_temperature=1.0,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            report = train_all_timeframes(source, output_dir, config)
            latest = predict_latest(source, output_dir)
            manifest = json.loads(
                (output_dir / "manifest.json").read_text(encoding="utf-8")
            )

        self.assertEqual(report["config"]["model_type"], "catboost")
        self.assertEqual(report["config"]["catboost_iterations"], 5)
        self.assertEqual(report["config"]["catboost_depth"], 2)
        self.assertFalse(
            {"open", "high", "low", "close"}.intersection(
                manifest["timeframes"]["M1"]["features"]
            )
        )
        self.assertTrue(latest["probability_up"].between(0, 1).all())

    def test_lightgbm_round_trips_through_processed_latest_prediction(self):
        source = m1_frame(1800)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(__file__).resolve().parents[1]
            input_path = Path(temp_dir) / "m1.parquet"
            output_dir = Path(temp_dir) / "model"
            latest_path = Path(temp_dir) / "latest.json"
            source.to_parquet(input_path, index=False)
            environment = os.environ.copy()
            environment["PYTHONPATH"] = str(root / "src")
            subprocess.run(
                [
                    sys.executable,
                    str(root / "methods/next_bar/scripts/run.py"),
                    "train-evaluate",
                    "--input",
                    str(input_path),
                    "--output-dir",
                    str(output_dir),
                    "--timeframes",
                    "1",
                    "--model-type",
                    "lightgbm",
                    "--max-train-rows",
                    "1000",
                    "--lightgbm-estimators",
                    "5",
                    "--lightgbm-num-leaves",
                    "7",
                    "--lightgbm-learning-rate",
                    "0.05",
                    "--lightgbm-min-child-samples",
                    "10",
                ],
                cwd=root,
                env=environment,
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                [
                    sys.executable,
                    str(root / "methods/next_bar/scripts/run.py"),
                    "predict-latest",
                    "--input",
                    str(input_path),
                    "--model-dir",
                    str(output_dir),
                    "--output",
                    str(latest_path),
                ],
                cwd=root,
                env=environment,
                check=True,
                capture_output=True,
                text=True,
            )
            report = json.loads(
                (output_dir / "metrics.json").read_text(encoding="utf-8")
            )
            latest = json.loads(latest_path.read_text(encoding="utf-8"))
            manifest = json.loads(
                (output_dir / "manifest.json").read_text(encoding="utf-8")
            )

        self.assertEqual(report["config"]["model_type"], "lightgbm")
        self.assertEqual(report["config"]["lightgbm_estimators"], 5)
        self.assertEqual(report["config"]["lightgbm_num_leaves"], 7)
        self.assertFalse(
            {"open", "high", "low", "close"}.intersection(
                manifest["timeframes"]["M1"]["features"]
            )
        )
        self.assertTrue(all(0 <= row["probability_up"] <= 1 for row in latest))

    def test_regime_hgb_round_trips_through_latest_prediction(self):
        source = m1_frame(1800)
        config = TrainConfig(
            timeframes=(1,),
            model_type="regime_hgb",
            max_train_rows=1_000,
            max_iter=5,
            min_samples_leaf=10,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            report = train_all_timeframes(source, output_dir, config)
            latest = predict_latest(source, output_dir)
        diagnostics = report["timeframes"]["M1"]["model_diagnostics"]
        self.assertEqual(report["config"]["model_type"], "regime_hgb")
        self.assertEqual(
            set(diagnostics["train_rows_by_regime"]), {"low", "normal", "high"}
        )
        self.assertEqual(len(latest), 1)
        self.assertTrue(latest["probability_up"].between(0, 1).all())

    def test_body_atr_soft_hgb_uses_bounded_target_and_latest_prediction(self):
        target_frame = pd.DataFrame(
            {
                "target_up": [0, 1, 0, 1],
                "next_bar_body_atr": [0.0, 0.5, 2.0, 10.0],
            }
        )
        target = model_training_target(target_frame, "body_atr_soft_hgb")
        np.testing.assert_allclose(
            target,
            [
                0.5 - 0.5 * np.tanh(0.0),
                0.5 + 0.5 * np.tanh(0.5),
                0.5 - 0.5 * np.tanh(2.0),
                0.5 + 0.5 * np.tanh(10.0),
            ],
        )
        self.assertTrue(((target >= 0) & (target <= 1)).all())

        source = m1_frame(1800)
        config = TrainConfig(
            timeframes=(1,),
            model_type="body_atr_soft_hgb",
            max_train_rows=1_000,
            max_iter=5,
            min_samples_leaf=10,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            report = train_all_timeframes(source, output_dir, config)
            latest = predict_latest(source, output_dir)
            manifest = json.loads(
                (output_dir / "manifest.json").read_text(encoding="utf-8")
            )

        diagnostics = report["timeframes"]["M1"]["model_diagnostics"]
        self.assertEqual(report["config"]["model_type"], "body_atr_soft_hgb")
        self.assertIn("tanh", diagnostics["target_transform"])
        self.assertNotIn(
            "next_bar_body_atr", manifest["timeframes"]["M1"]["features"]
        )
        self.assertTrue(latest["probability_up"].between(0, 1).all())

    def test_body_multiclass_hgb_uses_train_median_and_latest_prediction(self):
        target_frame = pd.DataFrame(
            {
                "target_up": [0, 0, 0, 0, 1, 1, 1, 1],
                "next_bar_body_atr": [0.1, 1.0, 0.2, 2.0, 0.1, 1.1, 0.3, 3.0],
            }
        )
        target = model_training_target(target_frame, "body_multiclass_hgb")
        np.testing.assert_array_equal(target, [1, 0, 1, 0, 2, 3, 2, 3])

        source = m1_frame(1800)
        config = TrainConfig(
            timeframes=(1,),
            model_type="body_multiclass_hgb",
            max_train_rows=1_000,
            max_iter=3,
            min_samples_leaf=10,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            report = train_all_timeframes(source, output_dir, config)
            latest = predict_latest(source, output_dir)
            manifest = json.loads(
                (output_dir / "manifest.json").read_text(encoding="utf-8")
            )

        diagnostics = report["timeframes"]["M1"]["model_diagnostics"]
        self.assertEqual(report["config"]["model_type"], "body_multiclass_hgb")
        self.assertEqual(set(diagnostics["train_rows_by_class"]), {"0", "1", "2", "3"})
        self.assertIn("P(up_small)", diagnostics["direction_probability"])
        self.assertNotIn(
            "next_bar_body_atr", manifest["timeframes"]["M1"]["features"]
        )
        self.assertTrue(latest["probability_up"].between(0, 1).all())

    def test_signed_body_hgb_uses_continuous_target_and_latest_prediction(self):
        target_frame = pd.DataFrame(
            {
                "target_up": [0, 1, 0, 1],
                "next_bar_body_atr": [0.0, 0.5, 2.0, 10.0],
            }
        )
        target = model_training_target(target_frame, "signed_body_hgb")
        np.testing.assert_allclose(
            target,
            [-np.arcsinh(0.0), np.arcsinh(0.5), -np.arcsinh(2.0), np.arcsinh(10.0)],
        )

        source = m1_frame(1800)
        config = TrainConfig(
            timeframes=(1,),
            model_type="signed_body_hgb",
            max_train_rows=1_000,
            max_iter=5,
            min_samples_leaf=10,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            report = train_all_timeframes(source, output_dir, config)
            latest = predict_latest(source, output_dir)
            signed_manifest = json.loads(
                (output_dir / "manifest.json").read_text(encoding="utf-8")
            )

        diagnostics = report["timeframes"]["M1"]["model_diagnostics"]
        self.assertEqual(report["config"]["model_type"], "signed_body_hgb")
        self.assertIn("asinh", diagnostics["target_transform"])
        self.assertNotIn(
            "next_bar_body_atr",
            signed_manifest["timeframes"]["M1"]["features"],
        )
        self.assertTrue(latest["probability_up"].between(0, 1).all())

    def test_signed_clarity_hgb_uses_bounded_target_and_latest_prediction(self):
        target_frame = pd.DataFrame(
            {
                "target_up": [0, 1, 0, 1],
                "next_bar_directional_clarity": [0.0, 0.25, 0.5, 1.0],
            }
        )
        target = model_training_target(target_frame, "signed_clarity_hgb")
        np.testing.assert_allclose(target, [0.0, 0.25, -0.5, 1.0])

        source = m1_frame(1800)
        config = TrainConfig(
            timeframes=(1,),
            model_type="signed_clarity_hgb",
            max_train_rows=1_000,
            max_iter=5,
            min_samples_leaf=10,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            report = train_all_timeframes(source, output_dir, config)
            latest = predict_latest(source, output_dir)
            manifest = json.loads(
                (output_dir / "manifest.json").read_text(encoding="utf-8")
            )

        diagnostics = report["timeframes"]["M1"]["model_diagnostics"]
        self.assertEqual(report["config"]["model_type"], "signed_clarity_hgb")
        self.assertIn("next_bar_range", diagnostics["target_transform"])
        self.assertGreaterEqual(diagnostics["transformed_target"]["minimum"], -1)
        self.assertLessEqual(diagnostics["transformed_target"]["maximum"], 1)
        self.assertNotIn(
            "next_bar_directional_clarity",
            manifest["timeframes"]["M1"]["features"],
        )
        self.assertTrue(latest["probability_up"].between(0, 1).all())

    def test_signed_body_quantile_hgb_uses_fixed_distribution_and_latest_prediction(self):
        source = m1_frame(1800)
        config = TrainConfig(
            timeframes=(1,),
            model_type="signed_body_quantile_hgb",
            max_train_rows=1_000,
            max_iter=3,
            min_samples_leaf=10,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            report = train_all_timeframes(source, output_dir, config)
            latest = predict_latest(source, output_dir)
            manifest = json.loads(
                (output_dir / "manifest.json").read_text(encoding="utf-8")
            )

        diagnostics = report["timeframes"]["M1"]["model_diagnostics"]
        self.assertEqual(
            report["config"]["model_type"], "signed_body_quantile_hgb"
        )
        self.assertEqual(diagnostics["quantiles"], [0.25, 0.5, 0.75])
        self.assertIn("q75", diagnostics["direction_score"])
        self.assertNotIn(
            "next_bar_body_atr", manifest["timeframes"]["M1"]["features"]
        )
        self.assertTrue(latest["probability_up"].between(0, 1).all())


if __name__ == "__main__":
    unittest.main()
