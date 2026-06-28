import argparse
import unittest

import pandas as pd

from trade_data.meta_model import (
    GroupEVCalibrationConfig,
    MetaModelConfig,
    TradeQualityModelConfig,
    add_group_calibrated_fixed_horizon_columns,
    add_group_calibrated_ev_columns,
    add_meta_predictions,
    add_trade_quality_model_columns,
    add_trade_quality_model_values_to_enriched,
    add_trade_quality_columns,
    add_trade_source_ev_columns,
    available_feature_columns,
    build_training_frame,
    build_sample_weights,
    combine_fit_predictions,
    fit_group_target_calibrator,
    fit_group_ev_calibrator,
    fit_trade_quality_model,
    fit_trade_quality_calibrator,
    filter_months,
    fixed_horizon_target_specs,
    parse_csv_ints,
    parse_csv_months,
    parse_csv_strings,
    trade_quality_calibration_metrics,
    side_target_means,
    train_model,
)


def prediction_frame():
    return pd.DataFrame(
        {
            "long_best_adjusted_pnl": [10.0, 20.0, 5.0],
            "short_best_adjusted_pnl": [3.0, 4.0, 15.0],
            "pred_long_best_adjusted_pnl": [9.0, 18.0, 6.0],
            "pred_short_best_adjusted_pnl": [4.0, 5.0, 14.0],
            "long_fixed_60m_adjusted_pnl": [1.0, 3.0, 9.0],
            "short_fixed_60m_adjusted_pnl": [8.0, 4.0, 2.0],
            "pred_long_fixed_60m_adjusted_pnl": [11.0, 13.0, 19.0],
            "pred_short_fixed_60m_adjusted_pnl": [18.0, 14.0, 12.0],
            "pred_long_max_adverse_pnl": [-2.0, -3.0, -1.0],
            "pred_short_max_adverse_pnl": [-1.0, -2.0, -4.0],
            "pred_long_best_holding_minutes": [30.0, 60.0, 45.0],
            "pred_short_best_holding_minutes": [20.0, 40.0, 80.0],
            "pred_long_wait_regret": [1.0, 0.5, 2.0],
            "pred_short_wait_regret": [2.0, 1.0, 0.5],
            "pred_long_entry_local_rank": [0.8, 0.9, 0.4],
            "pred_short_entry_local_rank": [0.3, 0.4, 0.9],
            "pred_long_entry_urgency": [1.0, 2.0, -1.0],
            "pred_short_entry_urgency": [-1.0, 0.0, 2.0],
            "pred_long_profit_barrier_hit": [1, 1, 0],
            "pred_short_profit_barrier_hit": [0, 0, 1],
            "pred_long_wait_regret_quantile": [1, 0, 3],
            "pred_short_wait_regret_quantile": [3, 2, 0],
            "pred_long_entry_local_rank_bin": [4, 4, 1],
            "pred_short_entry_local_rank_bin": [1, 2, 4],
            "pred_best_adjusted_pnl_quantile": [2, 4, 3],
            "pred_side_score_quantile": [3, 4, 0],
            "pred_label": [1, 1, -1],
            "session_regime": ["asia", "asia", "ny_late"],
            "volatility_regime": ["low_vol", "low_vol", "normal_vol"],
        }
    )


class MetaModelTests(unittest.TestCase):
    def test_parse_csv_months(self):
        self.assertEqual(parse_csv_months("2024-07,2024-09"), ["2024-07", "2024-09"])
        self.assertIsNone(parse_csv_months(None))

        with self.assertRaises(argparse.ArgumentTypeError):
            parse_csv_months("2024-13")

    def test_parse_csv_strings_allows_empty(self):
        self.assertEqual(parse_csv_strings("session_regime,volatility_regime"), ["session_regime", "volatility_regime"])
        self.assertEqual(parse_csv_strings(""), [])

    def test_parse_csv_ints_allows_empty_and_rejects_text(self):
        self.assertEqual(parse_csv_ints("60, 240,720"), [60, 240, 720])
        self.assertEqual(parse_csv_ints(""), [])

        with self.assertRaises(argparse.ArgumentTypeError):
            parse_csv_ints("60m")

    def test_filter_months_uses_dataset_month(self):
        df = pd.DataFrame(
            {
                "dataset_month": ["2024-07", "2024-09", "2024-09"],
                "value": [1, 2, 3],
            }
        )

        filtered = filter_months(df, ["2024-09"], "test")

        self.assertEqual(filtered["value"].tolist(), [2, 3])

    def test_filter_months_rejects_missing_month(self):
        df = pd.DataFrame({"dataset_month": ["2024-07"], "value": [1]})

        with self.assertRaises(ValueError):
            filter_months(df, ["2024-09"], "test")

    def test_combine_fit_predictions_prepends_base_and_resets_index(self):
        primary = pd.DataFrame({"dataset_month": ["2024-07"], "value": [2]}, index=[10])
        base = pd.DataFrame({"dataset_month": ["2023-01", "2023-02"], "value": [0, 1]}, index=[20, 21])

        combined = combine_fit_predictions(primary, base)

        self.assertEqual(combined["dataset_month"].tolist(), ["2023-01", "2023-02", "2024-07"])
        self.assertEqual(combined.index.tolist(), [0, 1, 2])

    def test_build_training_frame_expands_long_and_short_examples(self):
        frame = build_training_frame(prediction_frame())

        self.assertEqual(len(frame), 6)
        self.assertEqual(set(frame["side"].tolist()), {1.0, -1.0})
        self.assertIn("pred_side_ev", frame.columns)
        self.assertIn("target", frame.columns)

    def test_available_feature_columns_includes_present_regime_features(self):
        df = prediction_frame()
        df["roll_vol_60"] = [0.1, 0.2, 0.3]

        self.assertIn("roll_vol_60", available_feature_columns(df))

    def test_month_side_sample_weighting_balances_cells(self):
        df = prediction_frame()
        df["dataset_month"] = ["2024-07", "2024-07", "2024-09"]
        frame = build_training_frame(df)

        weights = pd.Series(build_sample_weights(frame, "month_side"))
        weighted = frame.assign(weight=weights).groupby(["dataset_month", "side"])["weight"].sum()

        self.assertAlmostEqual(float(weighted.max()), float(weighted.min()))
        self.assertAlmostEqual(float(weights.mean()), 1.0)

    def test_meta_model_adds_side_predictions(self):
        df = prediction_frame()
        frame = build_training_frame(df)
        config = MetaModelConfig(
            max_iter=2,
            learning_rate=0.1,
            max_leaf_nodes=3,
            max_depth=None,
            min_samples_leaf=1,
            l2_regularization=0.0,
            max_features=1.0,
            early_stopping=False,
            validation_fraction=0.1,
            n_iter_no_change=10,
            tol=1e-7,
            random_seed=1,
            target_clip_quantile=1.0,
            entry_threshold=5.0,
            sample_weighting="none",
            prediction_shrinkage=1.0,
        )

        model = train_model(frame, config)
        output = add_meta_predictions(df, model)

        self.assertIn("pred_meta_long_adjusted_pnl", output.columns)
        self.assertIn("pred_meta_short_adjusted_pnl", output.columns)
        self.assertFalse(output["pred_meta_long_adjusted_pnl"].isna().any())

    def test_meta_prediction_shrinkage_uses_side_means(self):
        df = prediction_frame()
        frame = build_training_frame(df)
        config = MetaModelConfig(
            max_iter=2,
            learning_rate=0.1,
            max_leaf_nodes=3,
            max_depth=None,
            min_samples_leaf=1,
            l2_regularization=0.0,
            max_features=1.0,
            early_stopping=False,
            validation_fraction=0.1,
            n_iter_no_change=10,
            tol=1e-7,
            random_seed=1,
            target_clip_quantile=1.0,
            entry_threshold=5.0,
            sample_weighting="none",
            prediction_shrinkage=0.0,
        )

        model = train_model(frame, config)
        means = side_target_means(frame)
        output = add_meta_predictions(df, model, prediction_shrinkage=0.0, side_means=means)

        self.assertTrue((output["pred_meta_long_adjusted_pnl"] == means["long"]).all())
        self.assertTrue((output["pred_meta_short_adjusted_pnl"] == means["short"]).all())

    def test_group_ev_calibration_shrinks_predictions_to_regime_mean(self):
        df = prediction_frame()
        df["long_best_adjusted_pnl"] = [2.0, 4.0, 20.0]
        df["pred_long_best_adjusted_pnl"] = [20.0, 22.0, 20.0]
        config = GroupEVCalibrationConfig(
            group_columns=("session_regime",),
            min_group_size=1,
            prior_strength=0.0,
            prediction_shrinkage=0.0,
        )

        calibrator = fit_group_ev_calibrator(df, config)
        output = add_group_calibrated_ev_columns(df, calibrator)

        self.assertEqual(output["pred_regime_calibrated_long_best_adjusted_pnl"].tolist(), [3.0, 3.0, 20.0])

    def test_group_ev_calibration_falls_back_to_side_stats_for_small_groups(self):
        df = prediction_frame()
        config = GroupEVCalibrationConfig(
            group_columns=("session_regime",),
            min_group_size=3,
            prior_strength=0.0,
            prediction_shrinkage=0.0,
        )

        calibrator = fit_group_ev_calibrator(df, config)
        output = add_group_calibrated_ev_columns(df, calibrator)

        side_mean = df["long_best_adjusted_pnl"].mean()
        self.assertTrue((output["pred_regime_calibrated_long_best_adjusted_pnl"] == side_mean).all())

    def test_fixed_horizon_group_calibration_adds_regime_adjusted_columns(self):
        df = prediction_frame()
        config = GroupEVCalibrationConfig(
            group_columns=("session_regime",),
            min_group_size=1,
            prior_strength=0.0,
            prediction_shrinkage=0.0,
        )
        specs = fixed_horizon_target_specs((60,))

        calibrator = fit_group_target_calibrator(df, config, specs)
        output = add_group_calibrated_fixed_horizon_columns(df, calibrator)

        self.assertEqual(output["pred_regime_calibrated_long_fixed_60m_adjusted_pnl"].tolist(), [2.0, 2.0, 9.0])
        self.assertEqual(output["pred_regime_calibrated_short_fixed_60m_adjusted_pnl"].tolist(), [6.0, 6.0, 2.0])

    def test_trade_quality_calibration_adds_side_quality_columns(self):
        predictions = add_trade_source_ev_columns(
            prediction_frame(),
            source_mode="columns",
            long_column="pred_long_best_adjusted_pnl",
            short_column="pred_short_best_adjusted_pnl",
            long_fixed_horizon_columns=(),
            short_fixed_horizon_columns=(),
            fixed_horizon_score_mode="max",
        )
        trades = pd.DataFrame(
            {
                "direction": ["long", "long", "short"],
                "adjusted_pnl": [1.0, 3.0, 9.0],
                "pred_taken_ev": [11.0, 13.0, 12.0],
                "session_regime": ["asia", "asia", "ny_late"],
            }
        )
        config = GroupEVCalibrationConfig(
            group_columns=("session_regime",),
            min_group_size=1,
            prior_strength=0.0,
            prediction_shrinkage=0.0,
        )

        calibrator = fit_trade_quality_calibrator(trades, config)
        output = add_trade_quality_columns(predictions, calibrator)
        metrics = trade_quality_calibration_metrics(trades, calibrator)

        self.assertEqual(output["pred_trade_quality_long_adjusted_pnl"].tolist(), [2.0, 2.0, 2.0])
        self.assertEqual(output["pred_trade_quality_short_adjusted_pnl"].tolist(), [9.0, 9.0, 9.0])
        self.assertAlmostEqual(metrics["calibrated_bias"], 0.0)

    def test_trade_quality_model_adds_side_quality_columns(self):
        predictions = add_trade_source_ev_columns(
            prediction_frame(),
            source_mode="columns",
            long_column="pred_long_best_adjusted_pnl",
            short_column="pred_short_best_adjusted_pnl",
            long_fixed_horizon_columns=(),
            short_fixed_horizon_columns=(),
            fixed_horizon_score_mode="max",
        )
        trades = pd.DataFrame(
            {
                "direction": ["long", "long", "short", "short"],
                "direction_sign": [1, 1, -1, -1],
                "adjusted_pnl": [1.0, 3.0, 9.0, 7.0],
                "pred_taken_ev": [11.0, 13.0, 12.0, 10.0],
                "pred_opposite_ev": [8.0, 9.0, 4.0, 5.0],
                "pred_best_ev": [11.0, 13.0, 12.0, 10.0],
                "pred_taken_best_holding_minutes": [10.0, 20.0, 30.0, 40.0],
                "pred_taken_max_adverse_pnl": [-1.0, -2.0, -3.0, -4.0],
                "pred_taken_wait_regret": [0.1, 0.2, 0.3, 0.4],
                "pred_taken_entry_local_rank": [0.8, 0.7, 0.9, 0.6],
                "pred_taken_profit_barrier_hit": [1.0, 1.0, 1.0, 0.0],
                "entry_decision_timestamp": pd.date_range(
                    "2025-01-01",
                    periods=4,
                    freq="h",
                    tz="UTC",
                ),
                "dataset_month": ["2024-07", "2024-07", "2024-09", "2024-09"],
                "session_regime": ["asia", "asia", "ny_late", "ny_late"],
                "volatility_regime": ["low_vol", "low_vol", "normal_vol", "normal_vol"],
            }
        )
        config = TradeQualityModelConfig(
            max_iter=2,
            learning_rate=0.1,
            max_leaf_nodes=3,
            max_depth=None,
            min_samples_leaf=1,
            l2_regularization=0.0,
            max_features=1.0,
            early_stopping=False,
            validation_fraction=0.1,
            n_iter_no_change=10,
            tol=1e-7,
            random_seed=1,
            target_clip_quantile=1.0,
            sample_weighting="none",
            prediction_shrinkage=1.0,
        )

        bundle = fit_trade_quality_model(trades, config)
        output = add_trade_quality_model_columns(predictions, bundle)
        scored = add_trade_quality_model_values_to_enriched(trades, bundle)

        self.assertIn("pred_trade_quality_long_adjusted_pnl", output.columns)
        self.assertIn("pred_trade_quality_short_adjusted_pnl", output.columns)
        self.assertFalse(output["pred_trade_quality_long_adjusted_pnl"].isna().any())
        self.assertFalse(scored["pred_trade_quality_taken_adjusted_pnl"].isna().any())


if __name__ == "__main__":
    unittest.main()
