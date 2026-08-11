import unittest

import numpy as np
import pandas as pd

from trade_data.next_bar_odds_recalibration import (
    chronological_correctness_recalibration,
    prequential_hierarchical_beta_recalibration,
)


def prediction_frame() -> pd.DataFrame:
    rows = []
    timestamp = pd.Timestamp("2020-01-01", tz="UTC")
    for fold, correctness in {
        "test2020": [True, False, True, False, True, False],
        "test2021": [True, True, False, False, True, False],
        "test2022": [False, True, True, False, True, False],
    }.items():
        for index, correct in enumerate(correctness):
            confidence = 0.51 + index * 0.01
            rows.append(
                {
                    "fold": fold,
                    "timestamp": timestamp,
                    "confidence": confidence,
                    "correct": correct,
                    "predicted_up": index % 2,
                }
            )
            timestamp += pd.Timedelta(minutes=15)
    return pd.DataFrame(rows)


class NextBarOddsRecalibrationTests(unittest.TestCase):
    def test_prequential_beta_uses_only_resolved_past_outcomes(self):
        timestamp = pd.date_range("2020-01-01", periods=12, freq="min", tz="UTC")
        source = pd.DataFrame(
            {
                "fold": ["test2020"] * 6 + ["test2021"] * 6,
                "timestamp": timestamp,
                "decision_timestamp": timestamp + pd.Timedelta(minutes=1),
                "target_timestamp": timestamp + pd.Timedelta(minutes=2),
                "confidence": [0.6] * 12,
                "correct": [True, True, False, True, False, True] * 2,
                "predicted_direction": ["up", "down"] * 6,
                "volatility_regime": ["normal"] * 12,
                "predicted_up": [True, False] * 6,
            }
        )
        calibrated, report = prequential_hierarchical_beta_recalibration(
            source,
            global_prior_strength=8,
            band_prior_strength=4,
            cell_prior_strength=2,
        )

        self.assertAlmostEqual(calibrated.loc[0, "adaptive_confidence"], 0.6)
        self.assertEqual(calibrated.loc[0, "adaptive_global_support"], 0)
        self.assertEqual(calibrated.loc[1, "adaptive_global_support"], 1)
        self.assertGreater(calibrated.loc[1, "adaptive_confidence"], 0.6)
        self.assertTrue(calibrated["adaptive_confidence"].between(0, 1).all())
        self.assertTrue(
            calibrated["adaptive_confidence_lower"]
            .le(calibrated["adaptive_confidence"])
            .all()
        )
        self.assertEqual(
            report["fixed_specification"]["hierarchy"],
            "global -> raw confidence band -> predicted direction x volatility regime",
        )
        self.assertIn("0.5", report["adaptive_lower_bound_lanes"]["development"])

        changed = source.copy()
        changed.loc[changed.index >= 6, "correct"] = ~changed.loc[
            changed.index >= 6, "correct"
        ]
        changed_calibrated, _ = prequential_hierarchical_beta_recalibration(
            changed,
            global_prior_strength=8,
            band_prior_strength=4,
            cell_prior_strength=2,
        )
        np.testing.assert_allclose(
            calibrated.loc[:6, "adaptive_confidence"],
            changed_calibrated.loc[:6, "adaptive_confidence"],
        )
        self.assertEqual(
            calibrated["predicted_up"].tolist(), source["predicted_up"].tolist()
        )

    def test_prequential_beta_rejects_unresolved_or_invalid_inputs(self):
        source = prediction_frame().assign(
            decision_timestamp=lambda frame: frame["timestamp"] + pd.Timedelta(minutes=1),
            target_timestamp=lambda frame: frame["timestamp"] + pd.Timedelta(minutes=1),
            predicted_direction="up",
            volatility_regime="normal",
        )
        with self.assertRaisesRegex(ValueError, "target_timestamp"):
            prequential_hierarchical_beta_recalibration(source)

    def test_recalibration_is_chronological_and_preserves_predictions(self):
        source = prediction_frame()
        calibrated, report = chronological_correctness_recalibration(source)

        self.assertEqual(report["rows"], 12)
        self.assertEqual(report["folds"][0]["calibration_folds"], ["test2020"])
        self.assertEqual(calibrated["predicted_up"].tolist(), source.loc[6:, "predicted_up"].tolist())
        self.assertTrue(calibrated["isotonic_confidence"].between(0, 1).all())
        self.assertTrue(calibrated["platt_correctness_confidence"].between(0, 1).all())
        self.assertEqual(report["fixed_thresholds"], [0.515, 0.525, 0.535, 0.55])
        self.assertEqual(report["periods"]["all_nested"]["raw_model_confidence"]["lanes"]["0.515"]["rows"], 10)

        changed = source.copy()
        changed.loc[changed["fold"].eq("test2021"), "correct"] = ~changed.loc[
            changed["fold"].eq("test2021"), "correct"
        ]
        changed_calibrated, _ = chronological_correctness_recalibration(changed)
        original_fold = calibrated.loc[calibrated["fold"].eq("test2021")]
        changed_fold = changed_calibrated.loc[changed_calibrated["fold"].eq("test2021")]
        np.testing.assert_allclose(
            original_fold["isotonic_confidence"], changed_fold["isotonic_confidence"]
        )
        np.testing.assert_allclose(
            original_fold["platt_correctness_confidence"],
            changed_fold["platt_correctness_confidence"],
        )

    def test_recalibration_requires_two_folds(self):
        with self.assertRaisesRegex(ValueError, "at least two"):
            chronological_correctness_recalibration(
                prediction_frame().loc[lambda frame: frame["fold"].eq("test2020")]
            )

    def test_recalibration_rejects_invalid_fixed_thresholds(self):
        with self.assertRaisesRegex(ValueError, "odds thresholds"):
            chronological_correctness_recalibration(
                prediction_frame(), thresholds=(0.49,)
            )


if __name__ == "__main__":
    unittest.main()
