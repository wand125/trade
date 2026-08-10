import unittest

import numpy as np
import pandas as pd

from trade_data.next_bar_odds_recalibration import (
    chronological_correctness_recalibration,
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
    def test_recalibration_is_chronological_and_preserves_predictions(self):
        source = prediction_frame()
        calibrated, report = chronological_correctness_recalibration(source)

        self.assertEqual(report["rows"], 12)
        self.assertEqual(report["folds"][0]["calibration_folds"], ["test2020"])
        self.assertEqual(calibrated["predicted_up"].tolist(), source.loc[6:, "predicted_up"].tolist())
        self.assertTrue(calibrated["isotonic_confidence"].between(0, 1).all())
        self.assertTrue(calibrated["platt_correctness_confidence"].between(0, 1).all())

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


if __name__ == "__main__":
    unittest.main()
