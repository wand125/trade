import unittest
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

from trade_data.next_bar import build_feature_frame, resample_complete_bars
from trade_data.next_bar_state_correctness import (
    StateCorrectnessConfig,
    build_latest_state_correctness_prediction,
    build_state_correctness_frame,
    chronological_state_correctness_predictions,
    run_state_correctness,
)


class FixedProbabilityModel:
    classes_ = np.asarray([0, 1])

    def predict_proba(self, values):
        return np.tile(np.asarray([[0.4, 0.6]]), (len(values), 1))


class FixedCalibrator:
    def predict(self, values):
        return np.full(len(values), 0.57)


def source_bars(rows: int = 500) -> pd.DataFrame:
    timestamp = pd.date_range("2019-12-31", periods=rows, freq="min", tz="UTC")
    movement = 0.0002 * np.sin(np.arange(rows) / 7) + 0.0001 * np.cos(
        np.arange(rows) / 13
    )
    open_ = 100 + np.cumsum(np.r_[0.0, movement[:-1]])
    close = open_ + movement
    high = np.maximum(open_, close) + 0.0003
    low = np.minimum(open_, close) - 0.0003
    return pd.DataFrame(
        {
            "timestamp": timestamp,
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
        }
    )


def reference_predictions(bars: pd.DataFrame) -> pd.DataFrame:
    timestamps = bars["timestamp"].iloc[180:450].reset_index(drop=True)
    rows = []
    fold_names = ("test2020", "test2021", "test2022")
    for index, timestamp in enumerate(timestamps):
        fold = fold_names[index // 90]
        predicted_up = int(index % 2 == 0)
        target_up = int(index % 5 not in (0, 1))
        probability = 0.53 if predicted_up else 0.47
        rows.append(
            {
                "fold": fold,
                "timestamp": timestamp,
                "decision_timestamp": timestamp + pd.Timedelta(minutes=1),
                "target_timestamp": timestamp + pd.Timedelta(minutes=2),
                "target_up": target_up,
                "probability_up": probability,
                "probability_down": 1 - probability,
                "predicted_up": predicted_up,
                "predicted_direction": "up" if predicted_up else "down",
                "confidence": max(probability, 1 - probability),
                "correct": predicted_up == target_up,
                "body_ratio": 999.0,
                "volatility_20": 999.0,
            }
        )
    return pd.DataFrame(rows)


class NextBarStateCorrectnessTests(unittest.TestCase):
    def test_features_are_stationary_finite_and_causal(self):
        bars = source_bars()
        reference = reference_predictions(bars)
        config = StateCorrectnessConfig()
        frame, features = build_state_correctness_frame(reference, bars, config)

        self.assertEqual(len(frame), len(reference))
        self.assertEqual(len(features), 57)
        self.assertTrue(np.isfinite(frame[list(features)].to_numpy()).all())
        self.assertFalse(frame["body_ratio"].eq(999.0).any())
        self.assertFalse(frame["volatility_20"].eq(999.0).any())
        self.assertNotIn("open", features)
        self.assertNotIn("close", features)

        changed_bars = bars.copy()
        cutoff = reference["timestamp"].iloc[100]
        future = changed_bars["timestamp"].gt(cutoff)
        changed_bars.loc[future, ["open", "high", "low", "close"]] += 10
        changed, changed_features = build_state_correctness_frame(
            reference, changed_bars, config
        )
        before = frame["timestamp"].le(cutoff)
        self.assertEqual(features, changed_features)
        np.testing.assert_allclose(
            frame.loc[before, list(features)],
            changed.loc[before, list(features)],
        )

    def test_chronological_model_preserves_direction_and_ignores_future_labels(self):
        bars = source_bars()
        frame, features = build_state_correctness_frame(
            reference_predictions(bars), bars, StateCorrectnessConfig()
        )
        config = StateCorrectnessConfig(
            max_train_rows=1_000,
            max_iter=2,
            min_samples_leaf=5,
        )
        predicted, reports, _ = chronological_state_correctness_predictions(
            frame, features, config
        )

        self.assertFalse(reports[0]["evaluation"])
        self.assertEqual(reports[1]["train_folds"], ["test2020"])
        self.assertEqual(reports[2]["train_folds"], ["test2020", "test2021"])
        self.assertTrue(
            predicted["predicted_up"].astype("int8").equals(
                predicted["reference_predicted_up"].astype("int8")
            )
        )
        self.assertTrue(
            predicted["probability_up"].ge(0.5).astype("int8").equals(
                predicted["predicted_up"].astype("int8")
            )
        )
        np.testing.assert_allclose(
            predicted["probability_up"] + predicted["probability_down"], 1
        )

        changed = frame.copy()
        last_fold = changed["fold"].eq("test2022")
        changed.loc[last_fold, "reference_correct"] = ~changed.loc[
            last_fold, "reference_correct"
        ]
        changed_predicted, _, _ = chronological_state_correctness_predictions(
            changed, features, config
        )
        prior = predicted["fold"].isin(["test2020", "test2021"])
        np.testing.assert_allclose(
            predicted.loc[prior, "state_probability_correct_calibrated"],
            changed_predicted.loc[prior, "state_probability_correct_calibrated"],
        )

    def test_latest_prediction_preserves_direction_and_applies_fixed_precision_lane(self):
        bars = source_bars()
        config = StateCorrectnessConfig()
        state, state_features = build_feature_frame(
            bars, config.timeframe, config.feature_set
        )
        bar_start = state["timestamp"].iloc[-1]
        reference = pd.DataFrame(
            [
                {
                    "timeframe": "M1",
                    "timeframe_minutes": 1,
                    "bar_start": bar_start,
                    "decision_timestamp": bar_start + pd.Timedelta(minutes=1),
                    "probability_up": 0.53,
                    "predicted_direction": "up",
                    "volatility_regime": "normal",
                }
            ]
        )
        artifact = {
            "model": FixedProbabilityModel(),
            "calibrator": FixedCalibrator(),
            "config": vars(config),
            "feature_columns": list(state_features) + [
                "reference_confidence_feature",
                "reference_aligned_edge_feature",
                "reference_predicted_up_feature",
            ],
        }

        latest = build_latest_state_correctness_prediction(bars, reference, artifact)

        self.assertEqual(latest.loc[0, "predicted_direction"], "up")
        self.assertAlmostEqual(latest.loc[0, "confidence"], 0.57)
        self.assertAlmostEqual(latest.loc[0, "probability_up"], 0.57)
        self.assertTrue(latest.loc[0, "prediction_eligible"])
        self.assertFalse(latest.loc[0, "odds_valid"])

        down = reference.copy()
        down.loc[0, "probability_up"] = 0.47
        down.loc[0, "predicted_direction"] = "down"
        excluded = build_latest_state_correctness_prediction(bars, down, artifact)
        self.assertAlmostEqual(excluded.loc[0, "probability_up"], 0.43)
        self.assertFalse(excluded.loc[0, "prediction_eligible"])

    def test_runtime_tail_reproduces_latest_distribution_shift_features(self):
        bars = source_bars(5_000)
        config = StateCorrectnessConfig()
        full, features = build_feature_frame(
            resample_complete_bars(bars, 1), 1, config.feature_set
        )
        tail, tail_features = build_feature_frame(
            resample_complete_bars(bars.tail(4_096).reset_index(drop=True), 1),
            1,
            config.feature_set,
        )

        self.assertEqual(features, tail_features)
        np.testing.assert_allclose(
            full.iloc[-1][list(features)].to_numpy(dtype="float64"),
            tail.iloc[-1][list(features)].to_numpy(dtype="float64"),
            rtol=1e-7,
            atol=1e-12,
        )

    def test_run_accepts_nonoverlapping_reference_directories(self):
        bars = source_bars()
        reference = reference_predictions(bars)
        fold_names = (
            "test2020",
            "test2021",
            "test2022",
            "test2023",
            "test2024",
            "test2025",
            "test2026_partial",
        )
        for fold, indices in zip(fold_names, np.array_split(reference.index, 7)):
            reference.loc[indices, "fold"] = fold
        config = StateCorrectnessConfig(max_iter=2, min_samples_leaf=5)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            input_path = root / "m1.parquet"
            bars.to_parquet(input_path, index=False)
            reference_dirs = []
            for fold in fold_names:
                directory = root / fold
                directory.mkdir()
                reference.loc[reference["fold"].eq(fold)].to_parquet(
                    directory / "m1_walk_forward_predictions.parquet", index=False
                )
                reference_dirs.append(directory)

            with self.assertRaisesRegex(ValueError, "confirmation"):
                run_state_correctness(
                    input_path, reference_dirs[:2], root / "incomplete", config
                )

            report = run_state_correctness(
                input_path,
                reference_dirs,
                root / "complete",
                config,
            )

        self.assertEqual(len(report["reference_dirs"]), 7)


if __name__ == "__main__":
    unittest.main()
