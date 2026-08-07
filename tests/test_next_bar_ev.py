import unittest

import numpy as np
import pandas as pd

from trade_data.next_bar import (
    OddsCalibrationConfig,
    build_feature_frame,
    build_labeled_dataset,
    fit_empirical_odds_calibrator,
    resample_complete_bars,
)
from trade_data.next_bar_ev import (
    EVConfig,
    build_ev_dataset,
    candidate_masks,
    evaluate_ev_selection,
    fit_ev_models,
    parse_float_tuple,
    predict_ev,
)


def m1_frame(rows: int) -> pd.DataFrame:
    timestamp = pd.date_range("2024-01-01", periods=rows, freq="min", tz="UTC")
    increments = 0.03 * np.sin(np.arange(rows) / 9) + 0.02 * np.cos(np.arange(rows) / 17)
    close = 2000 + np.cumsum(increments)
    open_ = np.r_[close[0] - increments[0], close[:-1]]
    return pd.DataFrame(
        {
            "timestamp": timestamp,
            "open": open_,
            "high": np.maximum(open_, close) + 0.02,
            "low": np.minimum(open_, close) - 0.02,
            "close": close,
            "volume": 0,
        }
    )


def fabricated_predictions(source: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    bars = resample_complete_bars(source, 1)
    labeled, feature_columns, _ = build_labeled_dataset(bars, 1)
    frame = labeled.iloc[:1600].copy()
    correct_mask = np.arange(len(frame)) % 5 != 0
    predicted_up = np.where(correct_mask, frame["target_up"], 1 - frame["target_up"])
    frame["probability_up"] = np.where(predicted_up == 1, 0.55, 0.45)
    frame["predicted_up"] = predicted_up.astype("int8")
    frame["predicted_direction"] = np.where(predicted_up == 1, "up", "down")
    frame["confidence"] = 0.55
    frame["correct"] = correct_mask
    frame["volatility_regime"] = np.where(np.arange(len(frame)) % 2, "high", "normal")
    frame["fold"] = np.where(np.arange(len(frame)) < 1000, "f1", "f2")
    columns = [
        "timestamp",
        "decision_timestamp",
        "target_timestamp",
        "target_up",
        "next_bar_body",
        "probability_up",
        "predicted_up",
        "predicted_direction",
        "confidence",
        "correct",
        "volatility_regime",
        "fold",
    ]
    return frame[columns], feature_columns


class NextBarEVTests(unittest.TestCase):
    def test_float_tuple_parser(self):
        self.assertEqual(parse_float_tuple("0,0.1,0.25"), (0.0, 0.1, 0.25))

    def test_ev_dataset_uses_normalized_targets_and_derived_features(self):
        source = m1_frame(2200)
        predictions, feature_columns = fabricated_predictions(source)
        dataset, ev_features = build_ev_dataset(
            source, predictions, 1, feature_columns
        )

        self.assertGreater(len(dataset), 1000)
        self.assertTrue(np.isfinite(dataset["realized_signed_atr"]).all())
        self.assertTrue(dataset["atr_absolute_20"].gt(0).all())
        self.assertTrue(dataset["realized_mae_atr"].ge(0).all())
        self.assertFalse({"open", "high", "low", "close"}.intersection(ev_features))

    def test_nested_ev_models_produce_cost_sensitive_policy_metrics(self):
        source = m1_frame(2200)
        predictions, feature_columns = fabricated_predictions(source)
        dataset, ev_features = build_ev_dataset(
            source, predictions, 1, feature_columns
        )
        train = dataset.loc[dataset["fold"] == "f1"]
        test = dataset.loc[dataset["fold"] == "f2"]
        config = EVConfig(
            timeframes=(1,),
            min_confidence=0.54,
            max_iter=5,
            min_samples_leaf=10,
            odds_bins=3,
            odds_min_support=20,
            odds_prior_strength=20,
            round_trip_costs=(0.0, 0.10),
        )
        models = fit_ev_models(train, ev_features, config)
        odds = fit_empirical_odds_calibrator(
            train,
            OddsCalibrationConfig(bins=3, min_support=20, prior_strength=20),
        )
        predicted = predict_ev(test, models, odds, config)
        metrics = evaluate_ev_selection(
            predicted, candidate_masks(predicted, config)["direction_only"], config
        )

        self.assertTrue(np.isfinite(predicted["expected_ev_atr"]).all())
        self.assertTrue(np.isfinite(predicted["direct_risk_ev_atr"]).all())
        self.assertTrue(np.isfinite(predicted["kelly_fraction_raw"]).all())
        self.assertTrue(predicted["kelly_fraction_raw"].between(0, 1).all())
        self.assertTrue(
            predicted["risk_adjusted_ev_after_cost_atr"].le(
                predicted["risk_adjusted_expected_ev_atr"]
            ).all()
        )
        self.assertTrue(np.isfinite(predicted["realized_risk_adjusted_atr"]).all())
        self.assertTrue(predicted["tail_loss_probability"].between(0, 1).all())
        self.assertEqual(metrics["rows"], len(test))
        zero_cost, higher_cost = metrics["cost_sensitivity"]
        self.assertAlmostEqual(
            zero_cost["net_total"] - higher_cost["net_total"],
            0.10 * len(test),
        )
        self.assertAlmostEqual(
            metrics["decision_cost_headroom"],
            metrics["all_fold_cost_ceiling"] - config.decision_round_trip_cost,
        )
        self.assertIn("direct_risk_ev_positive", candidate_masks(predicted, config))
        self.assertAlmostEqual(
            metrics["direct_risk_ev_bias_atr"],
            metrics["mean_direct_risk_ev_atr"]
            - metrics["actual_mean_risk_adjusted_atr"],
        )
        self.assertEqual(
            [row["stop_atr"] for row in metrics["stop_sensitivity"]],
            list(config.stop_atr_levels),
        )


if __name__ == "__main__":
    unittest.main()
