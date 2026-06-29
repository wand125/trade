import argparse
import unittest

import numpy as np
import pandas as pd

from trade_data.meta_model import (
    CandidateFailureModelConfig,
    CandidateQualityModelConfig,
    CANDIDATE_QUALITY_LONG_COLUMN,
    CANDIDATE_QUALITY_LONG_LOWER_COLUMN,
    CANDIDATE_QUALITY_LONG_LOWER_OVERESTIMATE_RISK_COLUMN,
    CANDIDATE_QUALITY_LONG_OVERESTIMATE_RISK_COLUMN,
    CANDIDATE_QUALITY_SHORT_COLUMN,
    CANDIDATE_QUALITY_SHORT_LOWER_COLUMN,
    CANDIDATE_QUALITY_SHORT_LOWER_OVERESTIMATE_RISK_COLUMN,
    CANDIDATE_QUALITY_SHORT_OVERESTIMATE_RISK_COLUMN,
    CANDIDATE_QUALITY_TAKEN_COLUMN,
    CANDIDATE_QUALITY_TAKEN_LOWER_COLUMN,
    GroupEVCalibrationConfig,
    MetaModelConfig,
    ResidualPenaltyConfig,
    StatefulRiskModelConfig,
    TradeFailureModelConfig,
    TradeQualityModelConfig,
    TRADE_QUALITY_LONG_COLUMN,
    TRADE_QUALITY_SHORT_COLUMN,
    TRADE_OVERESTIMATE_LONG_COLUMN,
    TRADE_OVERESTIMATE_LONG_RISK_COLUMN,
    TRADE_OVERESTIMATE_SHORT_COLUMN,
    TRADE_OVERESTIMATE_SHORT_RISK_COLUMN,
    TRADE_OVERESTIMATE_TAKEN_COLUMN,
    add_candidate_failure_model_columns,
    add_candidate_failure_model_values_to_examples,
    add_candidate_quality_downside_calibration_columns,
    add_entry_timing_calibration_columns,
    add_group_calibrated_fixed_horizon_columns,
    add_group_calibrated_ev_columns,
    add_meta_predictions,
    add_residual_penalty_columns,
    add_side_outcome_calibration_columns,
    add_stateful_risk_model_columns,
    add_stateful_risk_model_values_to_examples,
    add_trade_failure_model_columns,
    add_trade_failure_model_values_to_enriched,
    add_trade_overestimate_model_columns,
    add_trade_overestimate_model_values_to_enriched,
    add_trade_failure_probability_calibration_columns,
    add_trade_failure_probability_values_to_enriched,
    add_trade_quality_model_columns,
    add_trade_quality_model_values_to_enriched,
    add_trade_quality_columns,
    add_trade_source_ev_columns,
    available_feature_columns,
    build_candidate_failure_training_frame,
    build_candidate_quality_training_frame,
    build_sample_weights,
    build_stateful_value_training_frame,
    build_stateful_risk_training_frame,
    build_trade_overestimate_training_frame,
    build_training_frame,
    calibrate_probabilities_to_mean,
    candidate_quality_bucket_metrics,
    candidate_entry_side_masks,
    candidate_failure_prob_column,
    candidate_failure_risk_column,
    candidate_failure_taken_prob_column,
    candidate_failure_target_column,
    candidate_quality_downside_columns_for_side,
    candidate_quality_distribution_metrics,
    candidate_quality_group_metrics,
    entry_timing_columns_for_side,
    combine_fit_predictions,
    combine_candidate_quality_component_columns,
    fit_candidate_failure_model_from_frame,
    fit_candidate_quality_downside_calibrator,
    fit_entry_timing_calibrator,
    fit_candidate_quality_model_from_frame,
    fit_group_ev_calibrator,
    fit_group_target_calibrator,
    fit_residual_penalty_calibrator,
    fit_side_outcome_calibrator,
    fit_stateful_risk_model_from_frame,
    fit_trade_failure_model,
    fit_trade_overestimate_model,
    fit_trade_failure_probability_calibrator,
    fit_trade_quality_calibrator,
    fit_trade_quality_model,
    filter_months,
    fixed_horizon_target_specs,
    enrich_trades_for_trade_quality,
    parse_csv_ints,
    parse_csv_months,
    parse_csv_strings,
    prepare_candidate_quality_report_frame,
    prepare_stateful_near_tie_report_frame,
    residual_penalty_output_column,
    residual_penalty_scored_metrics,
    side_outcome_columns_for_side,
    stateful_near_tie_margin_metrics,
    stateful_risk_prob_column,
    stateful_risk_risk_column,
    stateful_risk_taken_prob_column,
    stateful_risk_target_column,
    stateful_value_oof_fold_plan,
    trade_quality_calibration_metrics,
    trade_quality_features_from_enriched,
    trade_quality_features_from_predictions,
    trade_overestimate_prediction_activation_diagnostics,
    trade_overestimate_scale_fold_diagnostics,
    trade_overestimate_scale_summary,
    trade_overestimate_scored_metrics,
    side_target_means,
    add_candidate_quality_model_columns,
    add_candidate_quality_model_values_to_examples,
    trade_failure_calibrated_prob_column,
    trade_failure_calibrated_risk_column,
    trade_failure_prob_column,
    trade_failure_risk_column,
    trade_failure_taken_calibrated_prob_column,
    trade_failure_upper_prob_column,
    trade_failure_upper_risk_column,
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

    def test_prepare_stateful_near_tie_report_frame_joins_side_secondary_score(self):
        examples = pd.DataFrame(
            {
                "decision_timestamp": [
                    "2024-07-01 00:00:00+00:00",
                    "2024-07-01 00:01:00+00:00",
                ],
                "candidate_side": ["long", "short"],
                "stateful_positive_cost_value": [5.0, -2.0],
                "pred_taken_ev": [13.0, 12.0],
                "pred_opposite_ev": [10.0, 11.0],
            }
        )
        predictions = pd.DataFrame(
            {
                "decision_timestamp": pd.to_datetime(
                    [
                        "2024-07-01 00:00:00+00:00",
                        "2024-07-01 00:01:00+00:00",
                    ],
                    utc=True,
                ),
                "secondary_long": [4.0, 1.0],
                "secondary_short": [0.0, -3.0],
            }
        )

        frame = prepare_stateful_near_tie_report_frame(
            examples,
            predictions=predictions,
            secondary_long_column="secondary_long",
            secondary_short_column="secondary_short",
        )

        self.assertEqual(frame["_secondary_score"].tolist(), [4.0, -3.0])
        self.assertEqual(frame["_secondary_opposite_score"].tolist(), [0.0, 1.0])
        self.assertEqual(frame["_primary_gap"].tolist(), [3.0, 1.0])

    def test_stateful_near_tie_margin_metrics_reports_secondary_top_lift(self):
        examples = pd.DataFrame(
            {
                "decision_timestamp": pd.date_range("2024-07-01", periods=4, freq="min", tz="UTC"),
                "candidate_side": ["long", "long", "short", "short"],
                "stateful_positive_cost_value": [10.0, 8.0, -4.0, -6.0],
                "pred_taken_ev": [12.0, 12.0, 12.0, 12.0],
                "pred_opposite_ev": [10.0, 10.0, 10.0, 10.0],
                "secondary_taken": [9.0, 7.0, -1.0, -2.0],
            }
        )
        frame = prepare_stateful_near_tie_report_frame(
            examples,
            secondary_taken_column="secondary_taken",
        )

        metrics = stateful_near_tie_margin_metrics(
            frame,
            tie_margins=(1.0, 2.0),
            top_fractions=(0.5,),
        )

        support_by_margin = dict(zip(metrics["tie_margin"], metrics["support"]))
        self.assertEqual(support_by_margin[1.0], 0)
        self.assertEqual(support_by_margin[2.0], 4)
        margin_two = metrics[metrics["tie_margin"] == 2.0].iloc[0]
        self.assertAlmostEqual(margin_two["secondary_top_0p5_target_mean"], 9.0)
        self.assertAlmostEqual(margin_two["secondary_top_0p5_target_lift"], 7.0)

    def test_stateful_risk_model_adds_probability_and_risk_columns(self):
        examples = pd.DataFrame(
            {
                "dataset_month": ["2024-07", "2024-07", "2024-09", "2024-09", "2025-01", "2025-01"],
                "candidate_side": ["long", "short", "long", "short", "long", "short"],
                "target": [1.0, -2.0, 3.0, 4.0, -5.0, 6.0],
                "stateful_entry_value": [-1.0, 2.0, -3.0, 4.0, 5.0, -6.0],
                "stateful_positive_cost_value": [-2.0, 1.0, -4.0, 3.0, 6.0, -7.0],
                "blocking_cost": [0.0, 6.0, 0.0, 8.0, 2.0, 0.0],
                "positive_blocking_cost": [0.0, 6.0, 0.0, 8.0, 2.0, 0.0],
                "replacement_regret": [6.0, -2.0, 7.0, -1.0, 0.0, 8.0],
                "positive_replacement_regret": [7.0, -1.0, 8.0, 0.0, 1.0, 9.0],
                "walkforward_context_stress_flag": [
                    False,
                    True,
                    "false",
                    "true",
                    0,
                    1,
                ],
                "target_walkforward_context_stress_adjusted": [
                    1.0,
                    -1.0,
                    0.0,
                    2.0,
                    -3.0,
                    4.0,
                ],
                "target_walkforward_context_holdout_mean_floor": [
                    0.5,
                    -3.0,
                    3.0,
                    -1.0,
                    -6.0,
                    1.0,
                ],
                "target_walkforward_prior_context_mean_floor": [
                    0.75,
                    -1.0,
                    2.0,
                    5.0,
                    -7.0,
                    4.0,
                ],
                "pred_taken_ev": [12.0, 13.0, 14.0, 15.0, 16.0, 17.0],
                "pred_opposite_ev": [11.0, 12.0, 13.0, 14.0, 15.0, 16.0],
                "trend_regime": ["up", "down", "up", "down", "range", "range"],
                "volatility_regime": ["low_vol", "low_vol", "normal_vol", "normal_vol", "low_vol", "normal_vol"],
                "session_regime": ["asia", "london", "asia", "ny_late", "london", "rollover"],
                "gap_regime": ["normal_gap"] * 6,
                "combined_regime": ["up_low_vol", "down_low_vol", "up_normal_vol", "down_normal_vol", "range_low_vol", "range_normal_vol"],
            }
        )
        config = StatefulRiskModelConfig(
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
            random_seed=3,
            sample_weighting="none",
            prediction_shrinkage=1.0,
            probability_calibration="none",
            target_names=(
                "positive_blocking",
                "positive_replacement_regret_high",
                "stateful_nonpositive",
                "walkforward_stress_flag",
                "walkforward_stress_adjusted_nonpositive",
                "walkforward_floor_nonpositive",
                "walkforward_floor_lowered",
                "walkforward_prior_floor_nonpositive",
                "walkforward_prior_floor_lowered",
            ),
            blocking_cost_threshold=5.0,
            replacement_regret_threshold=5.0,
            prediction_prefix="stateful_test",
        )

        frame = build_stateful_risk_training_frame(examples, config)
        bundle = fit_stateful_risk_model_from_frame(frame, config)
        output = add_stateful_risk_model_columns(prediction_frame(), bundle)
        scored = add_stateful_risk_model_values_to_examples(frame, bundle)

        self.assertEqual(
            frame[stateful_risk_target_column("positive_blocking")].tolist(),
            [0, 1, 0, 1, 1, 0],
        )
        self.assertEqual(
            frame[stateful_risk_target_column("positive_replacement_regret_high")].tolist(),
            [1, 0, 1, 0, 0, 1],
        )
        self.assertEqual(
            frame[stateful_risk_target_column("walkforward_stress_flag")].tolist(),
            [0, 1, 0, 1, 0, 1],
        )
        self.assertEqual(
            frame[stateful_risk_target_column("walkforward_stress_adjusted_nonpositive")].tolist(),
            [0, 1, 1, 0, 1, 0],
        )
        self.assertEqual(
            frame[stateful_risk_target_column("walkforward_floor_nonpositive")].tolist(),
            [0, 1, 0, 1, 1, 0],
        )
        self.assertEqual(
            frame[stateful_risk_target_column("walkforward_floor_lowered")].tolist(),
            [1, 1, 0, 1, 1, 1],
        )
        self.assertEqual(
            frame[stateful_risk_target_column("walkforward_prior_floor_nonpositive")].tolist(),
            [0, 1, 0, 0, 1, 0],
        )
        self.assertEqual(
            frame[stateful_risk_target_column("walkforward_prior_floor_lowered")].tolist(),
            [1, 0, 1, 0, 1, 1],
        )
        for target_name in config.target_names:
            long_prob = stateful_risk_prob_column(target_name, "long", "stateful_test")
            short_prob = stateful_risk_prob_column(target_name, "short", "stateful_test")
            long_risk = stateful_risk_risk_column(target_name, "long", "stateful_test")
            taken_prob = stateful_risk_taken_prob_column(target_name, "stateful_test")
            self.assertIn(long_prob, output.columns)
            self.assertIn(short_prob, output.columns)
            self.assertIn(long_risk, output.columns)
            self.assertIn(taken_prob, scored.columns)
            self.assertTrue(output[long_prob].between(0.0, 1.0).all())
            self.assertTrue((output[long_risk] == -output[long_prob]).all())
            self.assertFalse(scored[taken_prob].isna().any())

    def test_stateful_risk_mean_match_calibration_preserves_order_and_matches_mean(self):
        probabilities = np.array([0.02, 0.05, 0.10, 0.30, 0.70], dtype="float64")

        calibrated = calibrate_probabilities_to_mean(probabilities, 0.4)

        self.assertAlmostEqual(float(calibrated.mean()), 0.4, places=6)
        self.assertEqual(np.argsort(calibrated).tolist(), np.argsort(probabilities).tolist())
        self.assertTrue(((calibrated > 0.0) & (calibrated < 1.0)).all())

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

    def test_group_ev_calibration_adds_support_aware_lower_columns(self):
        df = prediction_frame()
        df["long_best_adjusted_pnl"] = [2.0, 4.0, 20.0]
        df["pred_long_best_adjusted_pnl"] = [20.0, 22.0, 20.0]
        config = GroupEVCalibrationConfig(
            group_columns=("session_regime",),
            min_group_size=1,
            prior_strength=0.0,
            prediction_shrinkage=0.0,
            lower_z=1.0,
        )

        calibrator = fit_group_ev_calibrator(df, config)
        output = add_group_calibrated_ev_columns(df, calibrator)

        self.assertIn("pred_regime_calibrated_long_best_adjusted_pnl_lower", output.columns)
        self.assertEqual(
            output["pred_regime_calibrated_long_best_adjusted_pnl_support"].tolist(),
            [2, 2, 1],
        )
        self.assertEqual(
            output["pred_regime_calibrated_long_best_adjusted_pnl_source"].tolist(),
            ["group", "group", "group"],
        )
        self.assertAlmostEqual(
            output["pred_regime_calibrated_long_best_adjusted_pnl_lower"].iloc[0],
            3.0 - (1.0 / (2**0.5)),
        )

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

    def test_fixed_horizon_group_calibration_adds_support_aware_lower_columns(self):
        df = prediction_frame()
        config = GroupEVCalibrationConfig(
            group_columns=("session_regime",),
            min_group_size=1,
            prior_strength=0.0,
            prediction_shrinkage=0.0,
            lower_z=1.0,
        )
        specs = fixed_horizon_target_specs((60,))

        calibrator = fit_group_target_calibrator(df, config, specs)
        output = add_group_calibrated_fixed_horizon_columns(df, calibrator)

        self.assertIn("pred_regime_calibrated_long_fixed_60m_adjusted_pnl_lower", output.columns)
        self.assertEqual(
            output["pred_regime_calibrated_long_fixed_60m_adjusted_pnl_support"].tolist(),
            [2, 2, 1],
        )
        self.assertEqual(
            output["pred_regime_calibrated_long_fixed_60m_adjusted_pnl_source"].tolist(),
            ["group", "group", "group"],
        )
        self.assertAlmostEqual(
            output["pred_regime_calibrated_long_fixed_60m_adjusted_pnl_lower"].iloc[0],
            2.0 - (1.0 / (2**0.5)),
        )
        self.assertAlmostEqual(
            output["pred_regime_calibrated_short_fixed_60m_adjusted_pnl_lower"].iloc[0],
            6.0 - (2.0 / (2**0.5)),
        )

    def test_residual_penalty_only_penalizes_excess_group_overestimate(self):
        df = pd.DataFrame(
            {
                "long_best_adjusted_pnl": [0.0, 0.0, 10.0, 10.0],
                "short_best_adjusted_pnl": [5.0, 5.0, 5.0, 5.0],
                "pred_long_best_adjusted_pnl": [20.0, 20.0, 10.0, 10.0],
                "pred_short_best_adjusted_pnl": [5.0, 5.0, 5.0, 5.0],
                "session_regime": ["asia", "asia", "ny_late", "ny_late"],
            }
        )
        config = ResidualPenaltyConfig(
            group_columns=("session_regime",),
            min_group_size=1,
            prior_strength=0.0,
            penalty_weight=1.0,
        )

        calibrator = fit_residual_penalty_calibrator(
            df,
            config,
            long_column="pred_long_best_adjusted_pnl",
            short_column="pred_short_best_adjusted_pnl",
        )
        output = add_residual_penalty_columns(df, calibrator)
        long_output = residual_penalty_output_column("long")
        short_output = residual_penalty_output_column("short")
        metrics = residual_penalty_scored_metrics(
            output,
            long_column="pred_long_best_adjusted_pnl",
            short_column="pred_short_best_adjusted_pnl",
            entry_threshold=5.0,
        )

        self.assertEqual(output[f"{long_output}_penalty"].tolist(), [10.0, 10.0, 0.0, 0.0])
        self.assertEqual(output[long_output].tolist(), [10.0, 10.0, 10.0, 10.0])
        self.assertEqual(output[f"{short_output}_penalty"].tolist(), [0.0, 0.0, 0.0, 0.0])
        self.assertEqual(output[f"{long_output}_source"].tolist(), ["group", "group", "group", "group"])
        self.assertAlmostEqual(metrics["penalty_mean"]["long"], 5.0)
        self.assertAlmostEqual(metrics["penalty_positive_rate"]["long"], 0.5)

    def test_residual_penalty_can_fit_only_candidate_entry_rows(self):
        df = pd.DataFrame(
            {
                "long_best_adjusted_pnl": [0.0, 0.0, 0.0, 0.0],
                "short_best_adjusted_pnl": [0.0, 0.0, 0.0, 0.0],
                "pred_long_best_adjusted_pnl": [20.0, 20.0, 10.0, 20.0],
                "pred_short_best_adjusted_pnl": [0.0, 25.0, 0.0, 0.0],
                "pred_long_entry_local_rank": [0.9, 0.9, 0.9, 0.2],
                "pred_short_entry_local_rank": [0.1, 0.9, 0.1, 0.1],
                "session_regime": ["asia", "asia", "asia", "london"],
            }
        )
        config = ResidualPenaltyConfig(
            group_columns=("session_regime",),
            min_group_size=1,
            prior_strength=0.0,
            penalty_weight=1.0,
            candidate_entry_only=True,
            entry_threshold=15.0,
            side_margin=5.0,
            min_entry_rank=0.5,
        )

        masks = candidate_entry_side_masks(
            df,
            config,
            long_column="pred_long_best_adjusted_pnl",
            short_column="pred_short_best_adjusted_pnl",
        )
        calibrator = fit_residual_penalty_calibrator(
            df,
            config,
            long_column="pred_long_best_adjusted_pnl",
            short_column="pred_short_best_adjusted_pnl",
        )

        self.assertEqual(masks["long"].tolist(), [True, False, False, False])
        self.assertEqual(masks["short"].tolist(), [False, True, False, False])
        self.assertEqual(calibrator.side_stats["long"].n, 1)
        self.assertEqual(calibrator.side_stats["short"].n, 1)
        self.assertEqual(set(calibrator.group_stats["long"].keys()), {("asia",)})
        self.assertEqual(set(calibrator.group_stats["short"].keys()), {("asia",)})

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
        self.assertEqual(output["pred_trade_quality_long_overestimate"].tolist(), [7.0, 16.0, 4.0])
        self.assertEqual(output["pred_trade_quality_short_overestimate"].tolist(), [0.0, 0.0, 5.0])
        self.assertEqual(output["pred_trade_quality_long_overestimate_risk"].tolist(), [-7.0, -16.0, -4.0])
        self.assertEqual(output["pred_trade_quality_short_overestimate_risk"].tolist(), [-0.0, -0.0, -5.0])
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

    def test_trade_overestimate_model_adds_amount_and_risk_columns(self):
        predictions = add_trade_source_ev_columns(
            prediction_frame(),
            source_mode="columns",
            long_column="pred_long_best_adjusted_pnl",
            short_column="pred_short_best_adjusted_pnl",
            long_fixed_horizon_columns=(),
            short_fixed_horizon_columns=(),
            fixed_horizon_score_mode="max",
        )
        predictions[TRADE_QUALITY_LONG_COLUMN] = 2.5
        predictions[TRADE_QUALITY_SHORT_COLUMN] = -1.0
        trades = pd.DataFrame(
            {
                "direction": ["long", "long", "short", "short"],
                "direction_sign": [1, 1, -1, -1],
                "adjusted_pnl": [1.0, 20.0, 9.0, -8.0],
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

        frame = build_trade_overestimate_training_frame(trades)
        long_features = trade_quality_features_from_predictions(predictions, "long")
        bundle = fit_trade_overestimate_model(trades, config)
        output = add_trade_overestimate_model_columns(predictions, bundle)
        scored = add_trade_overestimate_model_values_to_enriched(trades, bundle)
        metrics = trade_overestimate_scored_metrics(scored)

        self.assertEqual(frame["target"].tolist(), [10.0, 0.0, 3.0, 18.0])
        self.assertEqual(long_features["pred_taken_trade_quality_adjusted_pnl"].tolist(), [2.5] * len(predictions))
        self.assertEqual(long_features["pred_opposite_trade_quality_adjusted_pnl"].tolist(), [-1.0] * len(predictions))
        self.assertEqual(long_features["pred_trade_quality_adjusted_pnl_gap"].tolist(), [3.5] * len(predictions))
        self.assertIn(TRADE_OVERESTIMATE_LONG_COLUMN, output.columns)
        self.assertIn(TRADE_OVERESTIMATE_SHORT_COLUMN, output.columns)
        self.assertFalse(output[TRADE_OVERESTIMATE_LONG_COLUMN].isna().any())
        self.assertFalse(output[TRADE_OVERESTIMATE_SHORT_COLUMN].isna().any())
        self.assertTrue((output[TRADE_OVERESTIMATE_LONG_COLUMN] >= 0).all())
        self.assertTrue((output[TRADE_OVERESTIMATE_SHORT_COLUMN] >= 0).all())
        self.assertEqual(
            output[TRADE_OVERESTIMATE_LONG_RISK_COLUMN].tolist(),
            (-output[TRADE_OVERESTIMATE_LONG_COLUMN]).tolist(),
        )
        self.assertEqual(
            output[TRADE_OVERESTIMATE_SHORT_RISK_COLUMN].tolist(),
            (-output[TRADE_OVERESTIMATE_SHORT_COLUMN]).tolist(),
        )
        self.assertIn(TRADE_OVERESTIMATE_TAKEN_COLUMN, scored.columns)
        self.assertAlmostEqual(metrics["target_mean"], 7.75)

    def test_trade_overestimate_scale_diagnostics_report_threshold_activation(self):
        fit_trades = pd.DataFrame(
            {
                "dataset_month": ["2025-01", "2025-02", "2025-01", "2025-02"],
                "direction": ["long", "long", "short", "short"],
                "ev_overestimate_vs_realized": [0.0, 10.0, 0.0, 20.0],
            }
        )
        oof_trades = pd.DataFrame(
            {
                "dataset_month": ["2025-03", "2025-03", "2025-03"],
                "direction": ["long", "long", "short"],
                "ev_overestimate_vs_realized": [15.0, 0.0, 25.0],
                TRADE_OVERESTIMATE_TAKEN_COLUMN: [5.0, 6.0, 7.0],
            }
        )
        fold_plan = [
            {
                "holdout_month": "2025-03",
                "fit_months": ["2025-01", "2025-02"],
                "status": "profiled",
            }
        ]
        fold_metrics = trade_overestimate_scale_fold_diagnostics(
            fit_trades,
            oof_trades,
            fold_plan,
            quantiles=(0.9,),
            fixed_long_threshold=12.0,
            fixed_short_threshold=22.0,
        )
        long_row = fold_metrics[
            (fold_metrics["side"] == "long") & (fold_metrics["holdout_month"] == "2025-03")
        ].iloc[0]
        short_row = fold_metrics[
            (fold_metrics["side"] == "short") & (fold_metrics["holdout_month"] == "2025-03")
        ].iloc[0]

        self.assertAlmostEqual(long_row["fit_target_q90"], 9.0)
        self.assertEqual(long_row["holdout_target_ge_fit_q90_count"], 1)
        self.assertEqual(long_row["holdout_pred_gt_fit_q90_count"], 0)
        self.assertEqual(short_row["holdout_target_ge_fixed_count"], 1)
        self.assertEqual(short_row["holdout_pred_gt_fixed_count"], 0)

        predictions = pd.DataFrame(
            {
                "dataset_month": ["2025-03", "2025-03"],
                TRADE_OVERESTIMATE_LONG_COLUMN: [3.0, 8.0],
                TRADE_OVERESTIMATE_SHORT_COLUMN: [9.0, 21.0],
            }
        )
        activation = trade_overestimate_prediction_activation_diagnostics(
            predictions,
            fold_metrics,
            quantile_label_name="q90",
            fixed_long_threshold=12.0,
            fixed_short_threshold=22.0,
        )
        summary = trade_overestimate_scale_summary(
            fold_metrics,
            activation,
            quantile_label_name="q90",
        )

        self.assertEqual(summary["selected_target_high_vs_fit_threshold_count"], 2)
        self.assertEqual(summary["selected_prediction_above_fit_threshold_count"], 0)
        self.assertEqual(summary["side_prediction_above_fit_threshold_count"], 1)
        self.assertEqual(summary["side_prediction_above_fixed_threshold_count"], 0)

    def test_trade_failure_model_adds_probability_and_risk_columns(self):
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
                "adjusted_pnl": [1.0, -6.0, 9.0, -8.0],
                "direction_error": [False, True, False, True],
                "actual_taken_profit_barrier_hit": [1.0, 0.0, 1.0, 0.0],
                "exit_regret": [0.0, 6.0, 0.0, 8.0],
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
        config = TradeFailureModelConfig(
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
            sample_weighting="none",
            prediction_shrinkage=1.0,
            large_loss_threshold=5.0,
            exit_regret_threshold=5.0,
            ev_overestimate_threshold=20.0,
            target_names=(
                "large_loss",
                "wrong_side",
                "profit_barrier_miss",
                "pred_hit_actual_miss",
                "exit_regret_high",
                "ev_overestimate_high",
                "any_failure",
            ),
        )

        bundle = fit_trade_failure_model(trades, config)
        output = add_trade_failure_model_columns(predictions, bundle)
        scored = add_trade_failure_model_values_to_enriched(trades, bundle)

        for target_name in config.target_names:
            long_prob = trade_failure_prob_column(target_name, "long")
            short_prob = trade_failure_prob_column(target_name, "short")
            long_risk = trade_failure_risk_column(target_name, "long")
            short_risk = trade_failure_risk_column(target_name, "short")
            self.assertIn(long_prob, output.columns)
            self.assertIn(short_prob, output.columns)
            self.assertFalse(output[long_prob].isna().any())
            self.assertFalse(output[short_prob].isna().any())
            self.assertEqual(output[long_risk].tolist(), (-output[long_prob]).tolist())
            self.assertEqual(output[short_risk].tolist(), (-output[short_prob]).tolist())
            self.assertIn(f"pred_trade_failure_{target_name}_taken_prob", scored.columns)
            self.assertIn(f"trade_failure_{target_name}", scored.columns)
        self.assertEqual(scored["trade_failure_pred_hit_actual_miss"].tolist(), [0, 1, 0, 0])
        self.assertEqual(scored["trade_failure_ev_overestimate_high"].tolist(), [0, 0, 0, 0])
        self.assertEqual(scored["trade_failure_any_failure"].tolist(), [0, 1, 0, 1])

    def test_candidate_failure_model_adds_probability_and_risk_columns(self):
        predictions = add_trade_source_ev_columns(
            prediction_frame(),
            source_mode="columns",
            long_column="pred_long_best_adjusted_pnl",
            short_column="pred_short_best_adjusted_pnl",
            long_fixed_horizon_columns=(),
            short_fixed_horizon_columns=(),
            fixed_horizon_score_mode="max",
        )
        predictions["dataset_month"] = ["2024-07", "2024-07", "2024-09"]
        predictions["decision_timestamp"] = pd.date_range(
            "2025-01-01",
            periods=3,
            freq="h",
            tz="UTC",
        )
        predictions["long_best_adjusted_pnl"] = [10.0, -12.0, 5.0]
        predictions["short_best_adjusted_pnl"] = [3.0, 4.0, -15.0]
        predictions["long_max_adverse_pnl"] = [-12.0, -3.0, -2.0]
        predictions["short_max_adverse_pnl"] = [-2.0, -4.0, -14.0]
        predictions["combined_regime"] = [
            "range_normal_vol",
            "up_normal_vol",
            "range_normal_vol",
        ]
        predictions["session_regime"] = ["rollover", "asia", "ny_late"]
        config = CandidateFailureModelConfig(
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
            sample_weighting="none",
            prediction_shrinkage=1.0,
            large_adverse_threshold=10.0,
            large_loss_threshold=10.0,
            target_names=(
                "large_adverse",
                "large_loss",
                "wrong_side",
                "range_normal_vol_selected_failure",
                "normal_vol_selected_failure",
                "time_session_selected_failure",
                "any_failure",
            ),
            entry_threshold=7.0,
            long_entry_threshold_offset=0.0,
            short_entry_threshold_offset=0.0,
            side_margin=1.0,
            min_entry_rank=0.0,
        )

        examples = build_candidate_failure_training_frame(
            predictions,
            config,
            long_column="pred_trade_source_long_ev",
            short_column="pred_trade_source_short_ev",
        )
        bundle = fit_candidate_failure_model_from_frame(examples, config)
        output = add_candidate_failure_model_columns(predictions, bundle)
        scored = add_candidate_failure_model_values_to_examples(examples, bundle)

        long_prob = candidate_failure_prob_column("large_adverse", "long")
        short_prob = candidate_failure_prob_column("large_adverse", "short")
        long_risk = candidate_failure_risk_column("large_adverse", "long")
        short_risk = candidate_failure_risk_column("large_adverse", "short")
        taken_prob = candidate_failure_taken_prob_column("large_adverse")

        self.assertEqual(len(examples), 3)
        self.assertEqual(
            examples[candidate_failure_target_column("large_adverse")].tolist(),
            [1, 0, 1],
        )
        self.assertEqual(
            examples[candidate_failure_target_column("large_loss")].tolist(),
            [0, 1, 1],
        )
        self.assertEqual(
            examples[candidate_failure_target_column("wrong_side")].tolist(),
            [0, 1, 1],
        )
        self.assertEqual(
            examples[candidate_failure_target_column("range_normal_vol_selected_failure")].tolist(),
            [0, 0, 1],
        )
        self.assertEqual(
            examples[candidate_failure_target_column("normal_vol_selected_failure")].tolist(),
            [0, 1, 1],
        )
        self.assertEqual(
            examples[candidate_failure_target_column("time_session_selected_failure")].tolist(),
            [0, 0, 1],
        )
        self.assertEqual(
            examples[candidate_failure_target_column("any_failure")].tolist(),
            [1, 1, 1],
        )
        self.assertIn(long_prob, output.columns)
        self.assertIn(short_prob, output.columns)
        self.assertFalse(output[long_prob].isna().any())
        self.assertFalse(output[short_prob].isna().any())
        self.assertEqual(output[long_risk].tolist(), (-output[long_prob]).tolist())
        self.assertEqual(output[short_risk].tolist(), (-output[short_prob]).tolist())
        for target_name in config.target_names:
            self.assertIn(candidate_failure_prob_column(target_name, "long"), output.columns)
            self.assertIn(candidate_failure_prob_column(target_name, "short"), output.columns)
            self.assertIn(candidate_failure_taken_prob_column(target_name), scored.columns)
            self.assertFalse(scored[candidate_failure_taken_prob_column(target_name)].isna().any())
        self.assertIn(taken_prob, scored.columns)

    def test_candidate_failure_legacy_large_adverse_does_not_require_new_target_columns(self):
        predictions = add_trade_source_ev_columns(
            prediction_frame(),
            source_mode="columns",
            long_column="pred_long_best_adjusted_pnl",
            short_column="pred_short_best_adjusted_pnl",
            long_fixed_horizon_columns=(),
            short_fixed_horizon_columns=(),
            fixed_horizon_score_mode="max",
        ).drop(
            columns=[
                "long_best_adjusted_pnl",
                "short_best_adjusted_pnl",
                "session_regime",
                "volatility_regime",
            ],
            errors="ignore",
        )
        predictions["dataset_month"] = ["2024-07", "2024-07", "2024-09"]
        predictions["decision_timestamp"] = pd.date_range(
            "2025-01-01",
            periods=3,
            freq="h",
            tz="UTC",
        )
        predictions["long_max_adverse_pnl"] = [-12.0, -3.0, -2.0]
        predictions["short_max_adverse_pnl"] = [-2.0, -4.0, -14.0]
        config = CandidateFailureModelConfig(
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
            sample_weighting="none",
            prediction_shrinkage=1.0,
            large_adverse_threshold=10.0,
            large_loss_threshold=10.0,
            target_names=("large_adverse",),
            entry_threshold=7.0,
            long_entry_threshold_offset=0.0,
            short_entry_threshold_offset=0.0,
            side_margin=1.0,
            min_entry_rank=0.0,
        )

        examples = build_candidate_failure_training_frame(
            predictions,
            config,
            long_column="pred_trade_source_long_ev",
            short_column="pred_trade_source_short_ev",
        )

        self.assertEqual(len(examples), 3)
        self.assertEqual(
            examples[candidate_failure_target_column("large_adverse")].tolist(),
            [1, 0, 1],
        )

    def test_candidate_quality_model_adds_mean_lower_and_risk_columns(self):
        predictions = add_trade_source_ev_columns(
            prediction_frame(),
            source_mode="columns",
            long_column="pred_long_best_adjusted_pnl",
            short_column="pred_short_best_adjusted_pnl",
            long_fixed_horizon_columns=(),
            short_fixed_horizon_columns=(),
            fixed_horizon_score_mode="max",
        )
        predictions["dataset_month"] = ["2024-07", "2024-07", "2024-09"]
        predictions["decision_timestamp"] = pd.date_range(
            "2025-01-01",
            periods=3,
            freq="h",
            tz="UTC",
        )
        config = CandidateQualityModelConfig(
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
            lower_quantile=0.25,
            entry_threshold=7.0,
            long_entry_threshold_offset=0.0,
            short_entry_threshold_offset=0.0,
            side_margin=1.0,
            min_entry_rank=0.0,
        )

        examples = build_candidate_quality_training_frame(
            predictions,
            config,
            long_column="pred_trade_source_long_ev",
            short_column="pred_trade_source_short_ev",
        )
        bundle = fit_candidate_quality_model_from_frame(examples, config)
        output = add_candidate_quality_model_columns(predictions, bundle)
        scored = add_candidate_quality_model_values_to_examples(examples, bundle)

        self.assertEqual(len(examples), 3)
        self.assertEqual(examples["target"].tolist(), [10.0, 20.0, 15.0])
        for column in [
            CANDIDATE_QUALITY_LONG_COLUMN,
            CANDIDATE_QUALITY_SHORT_COLUMN,
            CANDIDATE_QUALITY_LONG_LOWER_COLUMN,
            CANDIDATE_QUALITY_SHORT_LOWER_COLUMN,
            CANDIDATE_QUALITY_LONG_OVERESTIMATE_RISK_COLUMN,
            CANDIDATE_QUALITY_SHORT_OVERESTIMATE_RISK_COLUMN,
            CANDIDATE_QUALITY_LONG_LOWER_OVERESTIMATE_RISK_COLUMN,
            CANDIDATE_QUALITY_SHORT_LOWER_OVERESTIMATE_RISK_COLUMN,
        ]:
            self.assertIn(column, output.columns)
            self.assertFalse(output[column].isna().any())
        self.assertTrue((output[CANDIDATE_QUALITY_LONG_OVERESTIMATE_RISK_COLUMN] <= 0).all())
        self.assertTrue((output[CANDIDATE_QUALITY_SHORT_OVERESTIMATE_RISK_COLUMN] <= 0).all())
        self.assertIn(CANDIDATE_QUALITY_TAKEN_COLUMN, scored.columns)
        self.assertIn(CANDIDATE_QUALITY_TAKEN_LOWER_COLUMN, scored.columns)
        self.assertFalse(scored[CANDIDATE_QUALITY_TAKEN_COLUMN].isna().any())
        self.assertFalse(scored[CANDIDATE_QUALITY_TAKEN_LOWER_COLUMN].isna().any())

    def test_candidate_quality_model_can_prefix_prediction_columns(self):
        predictions = add_trade_source_ev_columns(
            prediction_frame(),
            source_mode="columns",
            long_column="pred_long_best_adjusted_pnl",
            short_column="pred_short_best_adjusted_pnl",
            long_fixed_horizon_columns=(),
            short_fixed_horizon_columns=(),
            fixed_horizon_score_mode="max",
        )
        config = CandidateQualityModelConfig(
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
            lower_quantile=0.25,
            entry_threshold=7.0,
            long_entry_threshold_offset=0.0,
            short_entry_threshold_offset=0.0,
            side_margin=1.0,
            min_entry_rank=0.0,
            prediction_prefix="timed_component",
        )
        examples = build_candidate_quality_training_frame(
            predictions,
            config,
            long_column="pred_trade_source_long_ev",
            short_column="pred_trade_source_short_ev",
        )
        bundle = fit_candidate_quality_model_from_frame(examples, config)

        output = add_candidate_quality_model_columns(predictions, bundle)

        expected_columns = [
            "pred_candidate_quality_timed_component_long_adjusted_pnl",
            "pred_candidate_quality_timed_component_long_lower_adjusted_pnl",
            "pred_candidate_quality_timed_component_long_overestimate_risk",
            "pred_candidate_quality_timed_component_long_lower_overestimate_risk",
            "pred_candidate_quality_timed_component_short_adjusted_pnl",
            "pred_candidate_quality_timed_component_short_lower_adjusted_pnl",
            "pred_candidate_quality_timed_component_short_overestimate_risk",
            "pred_candidate_quality_timed_component_short_lower_overestimate_risk",
        ]
        for column in expected_columns:
            self.assertIn(column, output.columns)
            self.assertFalse(output[column].isna().any())
        self.assertNotIn(CANDIDATE_QUALITY_LONG_COLUMN, output.columns)

    def test_stateful_value_training_frame_uses_external_target(self):
        predictions = add_trade_source_ev_columns(
            prediction_frame(),
            source_mode="columns",
            long_column="pred_long_best_adjusted_pnl",
            short_column="pred_short_best_adjusted_pnl",
            long_fixed_horizon_columns=(),
            short_fixed_horizon_columns=(),
            fixed_horizon_score_mode="max",
        )
        predictions["dataset_month"] = ["2024-07", "2024-07", "2024-09"]
        base_config = CandidateQualityModelConfig(
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
            lower_quantile=0.25,
            entry_threshold=7.0,
            long_entry_threshold_offset=0.0,
            short_entry_threshold_offset=0.0,
            side_margin=1.0,
            min_entry_rank=0.0,
            prediction_prefix="stateful_entry",
        )
        examples = build_candidate_quality_training_frame(
            predictions,
            base_config,
            long_column="pred_trade_source_long_ev",
            short_column="pred_trade_source_short_ev",
        )
        examples["stateful_entry_value"] = [3.0, -4.0, 8.0]
        examples = examples.rename(columns={"dataset_month": "month"})

        stateful_frame = build_stateful_value_training_frame(examples)
        bundle = fit_candidate_quality_model_from_frame(stateful_frame, base_config)
        output = add_candidate_quality_model_columns(predictions, bundle)
        scored = add_candidate_quality_model_values_to_examples(stateful_frame, bundle)

        self.assertEqual(stateful_frame["target"].tolist(), [3.0, -4.0, 8.0])
        self.assertEqual(stateful_frame["dataset_month"].tolist(), ["2024-07", "2024-07", "2024-09"])
        self.assertIn("pred_candidate_quality_stateful_entry_long_adjusted_pnl", output.columns)
        self.assertIn("pred_candidate_quality_stateful_entry_short_adjusted_pnl", output.columns)
        self.assertIn(CANDIDATE_QUALITY_TAKEN_COLUMN, scored.columns)
        self.assertFalse(scored[CANDIDATE_QUALITY_TAKEN_COLUMN].isna().any())

    def test_stateful_value_oof_fold_plan_supports_expanding_scheme(self):
        months = ["2024-07", "2024-09", "2024-11", "2024-12"]

        expanding = stateful_value_oof_fold_plan(
            months,
            scheme="expanding",
            min_train_months=2,
        )
        self.assertEqual(expanding[0]["status"], "skipped")
        self.assertEqual(expanding[0]["holdout_month"], "2024-07")
        self.assertEqual(expanding[0]["skip_reason"], "insufficient_train_months")
        self.assertEqual(expanding[1]["fit_months"], ["2024-07"])
        self.assertEqual(expanding[1]["holdout_month"], "2024-09")
        self.assertEqual(expanding[1]["status"], "skipped")
        self.assertEqual(expanding[2]["fit_months"], ["2024-07", "2024-09"])
        self.assertEqual(expanding[2]["holdout_month"], "2024-11")
        self.assertEqual(expanding[2]["status"], "profiled")
        self.assertEqual(
            expanding[3]["fit_months"],
            ["2024-07", "2024-09", "2024-11"],
        )
        self.assertEqual(expanding[3]["holdout_month"], "2024-12")

        leave_one = stateful_value_oof_fold_plan(months, scheme="leave_one_month")
        self.assertEqual(leave_one[0]["fit_months"], ["2024-09", "2024-11", "2024-12"])
        self.assertTrue(all(row["status"] == "profiled" for row in leave_one))

    def test_candidate_quality_component_columns_can_be_combined(self):
        predictions = add_trade_source_ev_columns(
            prediction_frame(),
            source_mode="columns",
            long_column="pred_long_best_adjusted_pnl",
            short_column="pred_short_best_adjusted_pnl",
            long_fixed_horizon_columns=(),
            short_fixed_horizon_columns=(),
            fixed_horizon_score_mode="max",
        )
        component_values = {
            "timed": (
                [1.0, 2.0, 3.0],
                [0.0, 1.0, 2.0],
                [2.0, 4.0, 6.0],
                [1.0, 3.0, 5.0],
            ),
            "fixed": (
                [3.0, 4.0, 5.0],
                [2.0, 3.0, 4.0],
                [6.0, 8.0, 10.0],
                [5.0, 7.0, 9.0],
            ),
            "clipped": (
                [5.0, 6.0, 7.0],
                [4.0, 5.0, 6.0],
                [10.0, 12.0, 14.0],
                [9.0, 11.0, 13.0],
            ),
        }
        for prefix, (long_mean, long_lower, short_mean, short_lower) in component_values.items():
            predictions[f"pred_candidate_quality_{prefix}_long_adjusted_pnl"] = long_mean
            predictions[f"pred_candidate_quality_{prefix}_long_lower_adjusted_pnl"] = long_lower
            predictions[f"pred_candidate_quality_{prefix}_short_adjusted_pnl"] = short_mean
            predictions[f"pred_candidate_quality_{prefix}_short_lower_adjusted_pnl"] = short_lower

        output = combine_candidate_quality_component_columns(
            predictions,
            component_prefixes=["timed", "fixed", "clipped"],
            output_prefix="component_stack",
            mode="weighted_mean",
            weights=[1.0, 2.0, 1.0],
        )

        self.assertEqual(
            output["pred_candidate_quality_component_stack_long_adjusted_pnl"].tolist(),
            [3.0, 4.0, 5.0],
        )
        self.assertEqual(
            output["pred_candidate_quality_component_stack_short_adjusted_pnl"].tolist(),
            [6.0, 8.0, 10.0],
        )
        self.assertEqual(
            output["pred_candidate_quality_component_stack_long_lower_adjusted_pnl"].tolist(),
            [2.0, 3.0, 4.0],
        )
        self.assertEqual(
            output["pred_candidate_quality_component_stack_long_overestimate_risk"].tolist(),
            [-6.0, -14.0, -1.0],
        )
        self.assertEqual(
            output["pred_candidate_quality_component_stack_short_overestimate_risk"].tolist(),
            [-0.0, -0.0, -4.0],
        )

    def test_candidate_quality_report_metrics_capture_month_and_bucket_drift(self):
        examples = pd.DataFrame(
            {
                "target": [10.0, -5.0, 0.0, -20.0],
                "pred_taken_ev": [12.0, 8.0, 5.0, 1.0],
                "pred_candidate_quality_taken_adjusted_pnl": [9.0, 0.0, 3.0, -3.0],
                "pred_candidate_quality_taken_lower_adjusted_pnl": [5.0, -8.0, -1.0, -10.0],
                "dataset_month": ["2024-07", "2024-07", "2024-09", "2024-09"],
                "candidate_side": ["long", "short", "long", "short"],
                "combined_regime": [
                    "up_low_vol",
                    "range_normal_vol",
                    "range_normal_vol",
                    "down_high_vol",
                ],
            }
        )

        frame = prepare_candidate_quality_report_frame(examples)
        overall = candidate_quality_distribution_metrics(frame, downside_thresholds=(0.0, -15.0))
        month_metrics = candidate_quality_group_metrics(
            frame,
            [("dataset_month",)],
            downside_thresholds=(0.0, -15.0),
            min_support=1,
        )
        bucket_metrics = candidate_quality_bucket_metrics(
            frame,
            score_column="_mean_pred",
            bucket_count=2,
            group_columns=("dataset_month",),
            downside_thresholds=(0.0, -15.0),
            min_support=1,
        )

        self.assertEqual(overall["support"], 4)
        self.assertAlmostEqual(overall["target_mean"], -3.75)
        self.assertAlmostEqual(overall["raw_bias"], 10.25)
        self.assertAlmostEqual(overall["mean_bias"], 6.0)
        self.assertAlmostEqual(overall["lower_coverage"], 0.75)
        self.assertAlmostEqual(overall["target_rate_le_0"], 0.75)
        self.assertAlmostEqual(overall["target_rate_le_neg15"], 0.25)
        self.assertEqual(len(month_metrics), 2)
        july = month_metrics[month_metrics["dataset_month"] == "2024-07"].iloc[0]
        september = month_metrics[month_metrics["dataset_month"] == "2024-09"].iloc[0]
        self.assertAlmostEqual(july["target_mean"], 2.5)
        self.assertAlmostEqual(july["target_mean_shift"], 6.25)
        self.assertAlmostEqual(september["target_rate_le_0"], 1.0)
        self.assertEqual(int(bucket_metrics["support"].sum()), 4)
        self.assertEqual(set(bucket_metrics["bucket"].astype(str)), {"q01", "q02"})

    def test_candidate_quality_downside_calibration_adds_side_risk_columns(self):
        examples = pd.DataFrame(
            {
                "target": [10.0, -20.0, 0.0, -5.0, 5.0, -15.0],
                "pred_taken_ev": [12.0, 12.0, 6.0, 6.0, 4.0, 4.0],
                "pred_candidate_quality_taken_adjusted_pnl": [8.0, 9.0, 2.0, 3.0, -1.0, -2.0],
                "pred_candidate_quality_taken_lower_adjusted_pnl": [4.0, 5.0, -3.0, -4.0, -5.0, -6.0],
                "candidate_side": ["long", "long", "long", "short", "short", "short"],
                "combined_regime": [
                    "range_low_vol",
                    "range_low_vol",
                    "up_low_vol",
                    "range_low_vol",
                    "up_low_vol",
                    "up_low_vol",
                ],
            }
        )
        predictions = pd.DataFrame(
            {
                "pred_candidate_quality_fixed_component_long_adjusted_pnl": [8.0, 2.0],
                "pred_candidate_quality_fixed_component_short_adjusted_pnl": [3.0, -1.0],
                "combined_regime": ["range_low_vol", "up_low_vol"],
            }
        )
        bundle = fit_candidate_quality_downside_calibrator(
            examples,
            input_prediction_prefix="fixed_component",
            output_prefix="fixed_downside",
            group_columns=("combined_regime",),
            bucket_count=2,
            min_group_size=1,
            prior_strength=0.0,
            lower_z=0.0,
            downside_threshold=0.0,
            large_downside_threshold=-15.0,
        )

        output = add_candidate_quality_downside_calibration_columns(predictions, bundle)
        long_columns = candidate_quality_downside_columns_for_side("long", "fixed_downside")
        short_columns = candidate_quality_downside_columns_for_side("short", "fixed_downside")

        self.assertEqual(output[long_columns["quality_bucket"]].tolist(), ["q02", "q01"])
        self.assertEqual(output[short_columns["quality_bucket"]].tolist(), ["q02", "q01"])
        self.assertEqual(output[long_columns["source"]].tolist(), ["group", "group"])
        self.assertEqual(output[short_columns["source"]].tolist(), ["group", "group"])
        self.assertAlmostEqual(output[long_columns["calibrated_mean"]].iloc[0], -5.0)
        self.assertAlmostEqual(output[long_columns["downside_prob"]].iloc[0], 0.5)
        self.assertAlmostEqual(output[long_columns["overestimate"]].iloc[0], 14.5)
        self.assertAlmostEqual(output[long_columns["overestimate_risk"]].iloc[0], -14.5)
        self.assertAlmostEqual(output[short_columns["calibrated_mean"]].iloc[1], -5.0)
        self.assertAlmostEqual(output[short_columns["downside_prob"]].iloc[1], 0.5)
        self.assertAlmostEqual(output[short_columns["large_downside_prob"]].iloc[1], 0.5)
        self.assertLessEqual(output[short_columns["downside_risk"]].iloc[1], 0.0)

    def test_entry_timing_calibration_adds_side_wait_risk_columns(self):
        examples = pd.DataFrame(
            {
                "long_wait_regret": [0.0, 8.0, 1.0, 6.0],
                "short_wait_regret": [7.0, 2.0, 0.0, 9.0],
                "pred_long_wait_regret": [1.0, 9.0, 2.0, 8.0],
                "pred_short_wait_regret": [8.0, 2.0, 1.0, 9.0],
                "combined_regime": [
                    "range_low_vol",
                    "range_low_vol",
                    "up_low_vol",
                    "up_low_vol",
                ],
            }
        )
        predictions = pd.DataFrame(
            {
                "pred_long_wait_regret": [9.0, 1.0],
                "pred_short_wait_regret": [9.0, 1.0],
                "combined_regime": ["range_low_vol", "up_low_vol"],
            }
        )
        bundle = fit_entry_timing_calibrator(
            examples,
            output_prefix="wait4",
            group_columns=("combined_regime",),
            bucket_count=2,
            min_group_size=1,
            prior_strength=0.0,
            bad_wait_threshold=4.0,
        )

        output = add_entry_timing_calibration_columns(predictions, bundle)
        long_columns = entry_timing_columns_for_side("long", "wait4")
        short_columns = entry_timing_columns_for_side("short", "wait4")

        self.assertEqual(output[long_columns["source"]].tolist(), ["group", "group"])
        self.assertEqual(output[short_columns["source"]].tolist(), ["group", "group"])
        self.assertAlmostEqual(output[long_columns["bad_wait_prob"]].iloc[0], 1.0)
        self.assertAlmostEqual(output[long_columns["bad_wait_prob_risk"]].iloc[0], -1.0)
        self.assertAlmostEqual(output[long_columns["wait_excess_mean"]].iloc[0], 4.0)
        self.assertAlmostEqual(output[long_columns["wait_excess_risk"]].iloc[0], -4.0)
        self.assertAlmostEqual(output[short_columns["bad_wait_prob"]].iloc[1], 0.0)
        self.assertAlmostEqual(output[short_columns["bad_wait_prob_risk"]].iloc[1], -0.0)

    def test_side_outcome_calibration_adds_ev_distribution_columns(self):
        examples = pd.DataFrame(
            {
                "long_best_adjusted_pnl": [10.0, -20.0, 8.0, -5.0],
                "short_best_adjusted_pnl": [-5.0, 15.0, 1.0, 0.0],
                "pred_trade_source_long_ev": [12.0, 12.0, 4.0, 4.0],
                "pred_trade_source_short_ev": [3.0, 10.0, 3.0, 3.0],
                "pred_best_side_prob_1": [0.8, 0.9, 0.6, 0.4],
                "pred_best_side_prob_-1": [0.2, 0.1, 0.4, 0.6],
                "combined_regime": [
                    "range_low_vol",
                    "range_low_vol",
                    "up_low_vol",
                    "up_low_vol",
                ],
            }
        )
        predictions = pd.DataFrame(
            {
                "pred_trade_source_long_ev": [12.0, 4.0],
                "pred_trade_source_short_ev": [10.0, 3.0],
                "pred_best_side_prob_1": [0.9, 0.4],
                "pred_best_side_prob_-1": [0.1, 0.6],
                "combined_regime": ["range_low_vol", "up_low_vol"],
            }
        )
        bundle = fit_side_outcome_calibrator(
            examples,
            output_prefix="evdist",
            group_columns=("combined_regime",),
            bucket_count=2,
            confidence_bucket_count=2,
            min_group_size=1,
            prior_strength=0.0,
            lower_z=0.0,
            no_edge_threshold=0.0,
            large_loss_threshold=-15.0,
        )

        output = add_side_outcome_calibration_columns(predictions, bundle)
        long_columns = side_outcome_columns_for_side("long", "evdist")
        short_columns = side_outcome_columns_for_side("short", "evdist")

        self.assertEqual(output[long_columns["source"]].tolist(), ["group", "group"])
        self.assertEqual(output[long_columns["ev_bucket"]].tolist(), ["q02", "q01"])
        self.assertEqual(output[long_columns["confidence_bucket"]].tolist(), ["q02", "q01"])
        self.assertAlmostEqual(output[long_columns["calibrated_target_mean"]].iloc[0], -5.0)
        self.assertAlmostEqual(output[long_columns["no_edge_prob"]].iloc[0], 0.5)
        self.assertAlmostEqual(output[long_columns["wrong_side_prob"]].iloc[0], 0.5)
        self.assertAlmostEqual(output[long_columns["ev_overestimate"]].iloc[0], 17.0)
        self.assertAlmostEqual(output[long_columns["ev_overestimate_risk"]].iloc[0], -17.0)
        self.assertAlmostEqual(output[long_columns["confidence_overestimate"]].iloc[0], 0.45)
        self.assertAlmostEqual(output[long_columns["realized_ev_score"]].iloc[0], -22.0)
        self.assertEqual(output[short_columns["source"]].tolist(), ["group", "group"])
        self.assertLessEqual(output[short_columns["wrong_side_risk"]].iloc[0], 0.0)

    def test_trade_quality_features_include_optional_side_diagnostics(self):
        predictions = pd.DataFrame(
            {
                "pred_trade_source_long_ev": [12.0],
                "pred_trade_source_short_ev": [7.0],
                "pred_best_side_prob_1": [0.65],
                "pred_best_side_prob_-1": [0.35],
                "pred_trade_failure_pred_hit_actual_miss_long_prob": [0.20],
                "pred_trade_failure_pred_hit_actual_miss_short_prob": [0.55],
                "pred_side_outcome_evdist_long_wrong_side_prob": [0.25],
                "pred_side_outcome_evdist_short_wrong_side_prob": [0.60],
                "pred_candidate_quality_component_fixed_weighted_long_adjusted_pnl": [4.0],
                "pred_candidate_quality_component_fixed_weighted_short_adjusted_pnl": [-2.0],
            }
        )

        long_features = trade_quality_features_from_predictions(predictions, "long")
        short_features = trade_quality_features_from_predictions(predictions, "short")

        self.assertAlmostEqual(
            long_features["pred_taken_side_outcome_wrong_side_prob"].iloc[0],
            0.25,
        )
        self.assertAlmostEqual(
            long_features["pred_opposite_side_outcome_wrong_side_prob"].iloc[0],
            0.60,
        )
        self.assertAlmostEqual(
            long_features["pred_side_outcome_wrong_side_prob_gap"].iloc[0],
            -0.35,
        )
        self.assertAlmostEqual(long_features["pred_taken_side_confidence"].iloc[0], 0.65)
        self.assertAlmostEqual(long_features["pred_opposite_side_confidence"].iloc[0], 0.35)
        self.assertAlmostEqual(long_features["pred_side_confidence_gap"].iloc[0], 0.30)
        self.assertAlmostEqual(
            long_features["pred_taken_trade_failure_pred_hit_actual_miss_prob"].iloc[0],
            0.20,
        )
        self.assertAlmostEqual(
            long_features["pred_opposite_trade_failure_pred_hit_actual_miss_prob"].iloc[0],
            0.55,
        )
        self.assertAlmostEqual(
            long_features["pred_trade_failure_pred_hit_actual_miss_prob_gap"].iloc[0],
            -0.35,
        )
        self.assertAlmostEqual(
            short_features["pred_taken_side_outcome_wrong_side_prob"].iloc[0],
            0.60,
        )
        self.assertAlmostEqual(
            short_features["pred_opposite_side_outcome_wrong_side_prob"].iloc[0],
            0.25,
        )
        self.assertAlmostEqual(short_features["pred_taken_side_confidence"].iloc[0], 0.35)
        self.assertAlmostEqual(short_features["pred_opposite_side_confidence"].iloc[0], 0.65)
        self.assertAlmostEqual(short_features["pred_side_confidence_gap"].iloc[0], -0.30)
        self.assertAlmostEqual(
            short_features["pred_taken_trade_failure_pred_hit_actual_miss_prob"].iloc[0],
            0.55,
        )
        self.assertAlmostEqual(
            short_features["pred_opposite_trade_failure_pred_hit_actual_miss_prob"].iloc[0],
            0.20,
        )
        self.assertAlmostEqual(
            short_features["pred_trade_failure_pred_hit_actual_miss_prob_gap"].iloc[0],
            0.35,
        )
        self.assertAlmostEqual(
            short_features["pred_taken_component_fixed_weighted_quality"].iloc[0],
            -2.0,
        )
        self.assertAlmostEqual(
            short_features["pred_component_fixed_weighted_quality_gap"].iloc[0],
            -6.0,
        )

    def test_trade_quality_features_from_enriched_include_failure_probability_features(self):
        enriched = pd.DataFrame(
            {
                "direction": ["long", "short"],
                "direction_sign": [1, -1],
                "adjusted_pnl": [1.0, -2.0],
                "pred_taken_ev": [12.0, 7.0],
                "pred_opposite_ev": [7.0, 12.0],
                "pred_best_ev": [12.0, 12.0],
                "pred_trade_failure_pred_hit_actual_miss_long_prob": [0.20, 0.25],
                "pred_trade_failure_pred_hit_actual_miss_short_prob": [0.55, 0.65],
                "entry_decision_timestamp": pd.date_range(
                    "2025-01-01",
                    periods=2,
                    freq="h",
                    tz="UTC",
                ),
            }
        )

        features = trade_quality_features_from_enriched(enriched)

        self.assertEqual(
            features["pred_taken_trade_failure_pred_hit_actual_miss_prob"].tolist(),
            [0.20, 0.65],
        )
        self.assertEqual(
            features["pred_opposite_trade_failure_pred_hit_actual_miss_prob"].tolist(),
            [0.55, 0.25],
        )
        self.assertAlmostEqual(
            features["pred_trade_failure_pred_hit_actual_miss_prob_gap"].iloc[0],
            -0.35,
        )
        self.assertAlmostEqual(
            features["pred_trade_failure_pred_hit_actual_miss_prob_gap"].iloc[1],
            0.40,
        )

    def test_enrich_trades_for_trade_quality_preserves_failure_probability_columns(self):
        predictions = add_trade_source_ev_columns(
            prediction_frame(),
            source_mode="columns",
            long_column="pred_long_best_adjusted_pnl",
            short_column="pred_short_best_adjusted_pnl",
            long_fixed_horizon_columns=(),
            short_fixed_horizon_columns=(),
            fixed_horizon_score_mode="max",
        )
        predictions["decision_timestamp"] = pd.date_range(
            "2025-01-01",
            periods=3,
            freq="h",
            tz="UTC",
        )
        predictions["pred_trade_failure_pred_hit_actual_miss_long_prob"] = [0.20, 0.25, 0.30]
        predictions["pred_trade_failure_pred_hit_actual_miss_short_prob"] = [0.55, 0.60, 0.65]
        trades = pd.DataFrame(
            {
                "direction": ["short"],
                "entry_timestamp": [pd.Timestamp("2025-01-01 01:01", tz="UTC")],
                "exit_timestamp": [pd.Timestamp("2025-01-01 02:01", tz="UTC")],
                "entry_price": [100.0],
                "exit_price": [99.0],
                "raw_pnl": [1.0],
                "adjusted_pnl": [1.0],
                "holding_minutes": [60.0],
                "exit_reason": ["signal_close"],
                "entry_decision_timestamp": [pd.Timestamp("2025-01-01 01:00", tz="UTC")],
                "exit_decision_timestamp": [pd.Timestamp("2025-01-01 02:00", tz="UTC")],
            }
        )

        enriched = enrich_trades_for_trade_quality(trades, predictions)
        features = trade_quality_features_from_enriched(enriched)

        self.assertIn("pred_trade_failure_pred_hit_actual_miss_long_prob", enriched.columns)
        self.assertAlmostEqual(
            features["pred_taken_trade_failure_pred_hit_actual_miss_prob"].iloc[0],
            0.60,
        )
        self.assertAlmostEqual(
            features["pred_opposite_trade_failure_pred_hit_actual_miss_prob"].iloc[0],
            0.25,
        )

    def test_candidate_quality_barrier_event_target_uses_forced_pnl_on_time_exit(self):
        predictions = add_trade_source_ev_columns(
            prediction_frame(),
            source_mode="columns",
            long_column="pred_long_best_adjusted_pnl",
            short_column="pred_short_best_adjusted_pnl",
            long_fixed_horizon_columns=(),
            short_fixed_horizon_columns=(),
            fixed_horizon_score_mode="max",
        )
        predictions["long_exit_event"] = [1, 2, 0]
        predictions["short_exit_event"] = [2, 1, 0]
        predictions["long_forced_adjusted_pnl"] = [3.0, -4.0, 5.0]
        predictions["short_forced_adjusted_pnl"] = [-3.0, 4.0, -6.0]
        config = CandidateQualityModelConfig(
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
            lower_quantile=0.25,
            entry_threshold=7.0,
            long_entry_threshold_offset=0.0,
            short_entry_threshold_offset=0.0,
            side_margin=1.0,
            min_entry_rank=0.0,
            target_mode="barrier_event_adjusted_pnl",
            min_adjusted_edge=15.0,
        )

        examples = build_candidate_quality_training_frame(
            predictions,
            config,
            long_column="pred_trade_source_long_ev",
            short_column="pred_trade_source_short_ev",
        )

        self.assertEqual(len(examples), 3)
        self.assertEqual(examples["target"].tolist(), [15.0, -15.0, -6.0])
        self.assertEqual(examples["candidate_actual_adjusted_pnl"].tolist(), [10.0, 20.0, 15.0])
        self.assertEqual(examples["candidate_actual_forced_adjusted_pnl"].tolist(), [3.0, -4.0, -6.0])
        self.assertEqual(examples["candidate_actual_exit_event"].tolist(), [1.0, 2.0, 0.0])

    def test_candidate_quality_barrier_event_target_falls_back_to_fixed_time_exit(self):
        predictions = add_trade_source_ev_columns(
            prediction_frame(),
            source_mode="columns",
            long_column="pred_long_best_adjusted_pnl",
            short_column="pred_short_best_adjusted_pnl",
            long_fixed_horizon_columns=(),
            short_fixed_horizon_columns=(),
            fixed_horizon_score_mode="max",
        )
        predictions["long_exit_event"] = [1, 2, 0]
        predictions["short_exit_event"] = [2, 1, 0]
        predictions["long_fixed_720m_adjusted_pnl"] = [2.0, -3.0, 4.0]
        predictions["short_fixed_720m_adjusted_pnl"] = [-2.0, 3.0, -7.0]
        config = CandidateQualityModelConfig(
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
            lower_quantile=0.25,
            entry_threshold=7.0,
            long_entry_threshold_offset=0.0,
            short_entry_threshold_offset=0.0,
            side_margin=1.0,
            min_entry_rank=0.0,
            target_mode="barrier_event_adjusted_pnl",
            min_adjusted_edge=15.0,
            time_exit_target_minutes=720,
        )

        examples = build_candidate_quality_training_frame(
            predictions,
            config,
            long_column="pred_trade_source_long_ev",
            short_column="pred_trade_source_short_ev",
        )

        self.assertEqual(examples["target"].tolist(), [15.0, -15.0, -7.0])
        self.assertEqual(examples["candidate_actual_time_exit_adjusted_pnl"].tolist(), [2.0, -3.0, -7.0])
        self.assertEqual(
            examples["candidate_actual_time_exit_source"].tolist(),
            [
                "long_fixed_720m_adjusted_pnl",
                "long_fixed_720m_adjusted_pnl",
                "short_fixed_720m_adjusted_pnl",
            ],
        )

    def test_candidate_quality_joint_exit_target_blends_event_timing_fixed_and_best_pnl(self):
        predictions = add_trade_source_ev_columns(
            prediction_frame(),
            source_mode="columns",
            long_column="pred_long_best_adjusted_pnl",
            short_column="pred_short_best_adjusted_pnl",
            long_fixed_horizon_columns=(),
            short_fixed_horizon_columns=(),
            fixed_horizon_score_mode="max",
        )
        predictions["long_exit_event"] = [1, 2, 0]
        predictions["short_exit_event"] = [2, 1, 0]
        predictions["long_exit_event_minutes"] = [100.0, 100.0, 100.0]
        predictions["short_exit_event_minutes"] = [100.0, 100.0, 100.0]
        predictions["long_forced_adjusted_pnl"] = [3.0, -4.0, 5.0]
        predictions["short_forced_adjusted_pnl"] = [-3.0, 4.0, -6.0]
        predictions["long_fixed_240m_adjusted_pnl"] = [5.0, 6.0, 7.0]
        predictions["long_fixed_720m_adjusted_pnl"] = [9.0, 12.0, 15.0]
        predictions["short_fixed_240m_adjusted_pnl"] = [6.0, 5.0, 8.0]
        predictions["short_fixed_720m_adjusted_pnl"] = [10.0, 9.0, 14.0]
        config = CandidateQualityModelConfig(
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
            lower_quantile=0.25,
            entry_threshold=7.0,
            long_entry_threshold_offset=0.0,
            short_entry_threshold_offset=0.0,
            side_margin=1.0,
            min_entry_rank=0.0,
            target_mode="joint_exit_adjusted_pnl",
            min_adjusted_edge=15.0,
            time_exit_target_minutes=100,
            joint_barrier_weight=0.7,
            joint_fixed_horizon_weight=0.2,
            joint_best_weight=0.1,
            joint_time_decay=0.25,
            joint_component_clip_multiple=1.0,
            joint_fixed_horizon_minutes=(60, 240, 720),
        )

        examples = build_candidate_quality_training_frame(
            predictions,
            config,
            long_column="pred_trade_source_long_ev",
            short_column="pred_trade_source_short_ev",
        )

        expected_targets = [9.875, -4.975, -1.1]
        self.assertEqual(len(examples), 3)
        for actual, expected in zip(examples["target"].tolist(), expected_targets, strict=True):
            self.assertAlmostEqual(actual, expected)
        self.assertEqual(
            examples["candidate_actual_time_exit_source"].tolist(),
            [
                "long_forced_adjusted_pnl",
                "long_forced_adjusted_pnl",
                "short_forced_adjusted_pnl",
            ],
        )
        self.assertEqual(
            examples["candidate_actual_fixed_horizon_component"].round(6).tolist(),
            [5.0, 7.0, 8.0],
        )
        self.assertEqual(
            examples["candidate_actual_timed_barrier_component"].round(6).tolist(),
            [11.25, -11.25, -6.0],
        )

    def test_candidate_quality_component_target_modes_keep_joint_parts_separate(self):
        predictions = add_trade_source_ev_columns(
            prediction_frame(),
            source_mode="columns",
            long_column="pred_long_best_adjusted_pnl",
            short_column="pred_short_best_adjusted_pnl",
            long_fixed_horizon_columns=(),
            short_fixed_horizon_columns=(),
            fixed_horizon_score_mode="max",
        )
        predictions["long_exit_event"] = [1, 2, 0]
        predictions["short_exit_event"] = [2, 1, 0]
        predictions["long_exit_event_minutes"] = [100.0, 100.0, 100.0]
        predictions["short_exit_event_minutes"] = [100.0, 100.0, 100.0]
        predictions["long_forced_adjusted_pnl"] = [3.0, -4.0, 5.0]
        predictions["short_forced_adjusted_pnl"] = [-3.0, 4.0, -6.0]
        predictions["long_fixed_240m_adjusted_pnl"] = [5.0, 6.0, 7.0]
        predictions["long_fixed_720m_adjusted_pnl"] = [9.0, 12.0, 15.0]
        predictions["short_fixed_240m_adjusted_pnl"] = [6.0, 5.0, 8.0]
        predictions["short_fixed_720m_adjusted_pnl"] = [10.0, 9.0, 14.0]
        base_config = dict(
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
            lower_quantile=0.25,
            entry_threshold=7.0,
            long_entry_threshold_offset=0.0,
            short_entry_threshold_offset=0.0,
            side_margin=1.0,
            min_entry_rank=0.0,
            min_adjusted_edge=15.0,
            time_exit_target_minutes=100,
            joint_time_decay=0.25,
            joint_component_clip_multiple=1.0,
            joint_fixed_horizon_minutes=(60, 240, 720),
        )

        expected_by_mode = {
            "timed_barrier_component_adjusted_pnl": [11.25, -11.25, -6.0],
            "fixed_horizon_component_adjusted_pnl": [5.0, 7.0, 8.0],
            "clipped_best_adjusted_pnl": [10.0, 15.0, 15.0],
        }
        for target_mode, expected_targets in expected_by_mode.items():
            with self.subTest(target_mode=target_mode):
                config = CandidateQualityModelConfig(**base_config, target_mode=target_mode)
                examples = build_candidate_quality_training_frame(
                    predictions,
                    config,
                    long_column="pred_trade_source_long_ev",
                    short_column="pred_trade_source_short_ev",
                )

                self.assertEqual(len(examples), 3)
                for actual, expected in zip(examples["target"].tolist(), expected_targets, strict=True):
                    self.assertAlmostEqual(actual, expected)

    def test_trade_failure_probability_calibration_adds_side_prob_and_risk_columns(self):
        predictions = prediction_frame().copy()
        predictions[trade_failure_prob_column("large_loss", "long")] = [0.2, 0.9, 0.1]
        predictions[trade_failure_prob_column("large_loss", "short")] = [0.3, 0.4, 0.3]
        trades = pd.DataFrame(
            {
                "direction": ["long", "long", "short", "short"],
                "trade_failure_large_loss": [0, 1, 1, 1],
                "pred_trade_failure_large_loss_taken_prob": [0.2, 0.2, 0.3, 0.3],
                "session_regime": ["asia", "asia", "ny_late", "ny_late"],
            }
        )
        config = GroupEVCalibrationConfig(
            group_columns=("session_regime",),
            min_group_size=1,
            prior_strength=0.0,
            prediction_shrinkage=0.0,
            lower_z=1.0,
        )

        calibrator = fit_trade_failure_probability_calibrator(trades, config, "large_loss")
        output = add_trade_failure_probability_calibration_columns(predictions, calibrator)
        scored = add_trade_failure_probability_values_to_enriched(trades, calibrator)

        long_calibrated = trade_failure_calibrated_prob_column("large_loss", "long")
        short_calibrated = trade_failure_calibrated_prob_column("large_loss", "short")
        long_risk = trade_failure_calibrated_risk_column("large_loss", "long")
        long_upper = trade_failure_upper_prob_column("large_loss", "long")
        long_upper_risk = trade_failure_upper_risk_column("large_loss", "long")
        taken_calibrated = trade_failure_taken_calibrated_prob_column("large_loss")

        self.assertEqual(output[long_calibrated].tolist(), [0.5, 0.5, 0.5])
        self.assertEqual(output[short_calibrated].tolist(), [1.0, 1.0, 1.0])
        self.assertEqual(output[long_risk].tolist(), [-0.5, -0.5, -0.5])
        self.assertAlmostEqual(output[long_upper].iloc[0], 0.8535533905932737)
        self.assertEqual(output[long_upper].tolist(), output[long_upper].iloc[0:1].tolist() * 3)
        self.assertEqual(output[long_upper_risk].tolist(), (-output[long_upper]).tolist())
        self.assertEqual(output[f"{long_calibrated}_support"].tolist(), [2, 2, 2])
        self.assertEqual(output[f"{short_calibrated}_source"].tolist(), ["side", "side", "group"])
        self.assertEqual(scored[taken_calibrated].tolist(), [0.5, 0.5, 1.0, 1.0])


if __name__ == "__main__":
    unittest.main()
