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
    OddsCalibrationConfig,
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
