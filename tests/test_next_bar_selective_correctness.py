import unittest

import numpy as np
import pandas as pd

from trade_data.next_bar_selective_correctness import (
    SELECTIVE_CORRECTNESS_FEATURES,
    SelectiveCorrectnessConfig,
    build_selective_correctness_frame,
    chronological_selective_correctness_predictions,
)


def source_frame(offset: float = 0.0) -> pd.DataFrame:
    rows = []
    start = pd.Timestamp("2020-01-01", tz="UTC")
    row_number = 0
    for fold_index, fold in enumerate(("test2020", "test2021", "test2022")):
        for index in range(20):
            target_up = int((index + fold_index) % 3 != 0)
            predicted_up = int(index % 2 == 0)
            baseline_probability = 0.52 if predicted_up else 0.48
            candidate_probability = (
                0.54 + offset if predicted_up else 0.46 - offset
            )
            probability = 0.75 * baseline_probability + 0.25 * candidate_probability
            timestamp = start + pd.Timedelta(minutes=15 * row_number)
            rows.append(
                {
                    "fold": fold,
                    "timestamp": timestamp,
                    "decision_timestamp": timestamp,
                    "target_timestamp": timestamp + pd.Timedelta(minutes=15),
                    "target_up": target_up,
                    "volatility_regime": ("low", "normal", "high")[index % 3],
                    "volatility_20": 0.001 + index * 1e-5,
                    "body_ratio": (index % 5 - 2) / 10,
                    "baseline_probability_up": baseline_probability,
                    "candidate_probability_up": candidate_probability,
                    "probability_up": probability,
                    "probability_down": 1 - probability,
                    "predicted_up": predicted_up,
                    "correct": predicted_up == target_up,
                    "confidence": max(probability, 1 - probability),
                }
            )
            row_number += 1
    return pd.DataFrame(rows)


class NextBarSelectiveCorrectnessTests(unittest.TestCase):
    def test_features_are_finite_aligned_and_do_not_use_target(self):
        reference = source_frame(0.00)
        shape = source_frame(0.01)
        profile = source_frame(-0.01)
        frame = build_selective_correctness_frame(reference, shape, profile)
        self.assertEqual(len(frame), len(reference))
        self.assertEqual(len(SELECTIVE_CORRECTNESS_FEATURES), 24)
        self.assertTrue(
            np.isfinite(frame[list(SELECTIVE_CORRECTNESS_FEATURES)].to_numpy()).all()
        )

        changed_reference = reference.copy()
        changed_shape = shape.copy()
        changed_profile = profile.copy()
        for changed in (changed_reference, changed_shape, changed_profile):
            changed["target_up"] = 1 - changed["target_up"]
            changed["correct"] = changed["predicted_up"].eq(changed["target_up"])
        changed_frame = build_selective_correctness_frame(
            changed_reference, changed_shape, changed_profile
        )
        np.testing.assert_allclose(
            frame[list(SELECTIVE_CORRECTNESS_FEATURES)],
            changed_frame[list(SELECTIVE_CORRECTNESS_FEATURES)],
        )

    def test_chronological_model_uses_only_prior_oos_and_preserves_direction(self):
        frame = build_selective_correctness_frame(
            source_frame(0.00), source_frame(0.01), source_frame(-0.01)
        )
        predicted, reports, _ = chronological_selective_correctness_predictions(
            frame, SelectiveCorrectnessConfig()
        )
        self.assertFalse(reports[0]["evaluation"])
        self.assertEqual(reports[1]["train_folds"], ["test2020"])
        self.assertEqual(
            reports[2]["train_folds"], ["test2020", "test2021"]
        )
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
        self.assertTrue(predicted["confidence"].between(0.5, 1).all())
        np.testing.assert_allclose(
            predicted["probability_up"] + predicted["probability_down"], 1
        )
        np.testing.assert_allclose(
            predicted["confidence"],
            np.maximum(predicted["probability_up"], predicted["probability_down"]),
        )

        changed = frame.copy()
        last_fold = changed["fold"].eq("test2022")
        changed.loc[last_fold, "reference_correct"] = ~changed.loc[
            last_fold, "reference_correct"
        ]
        changed_predicted, _, _ = chronological_selective_correctness_predictions(
            changed, SelectiveCorrectnessConfig()
        )
        prior = predicted["fold"].isin(["test2020", "test2021"])
        np.testing.assert_allclose(
            predicted.loc[prior, "selection_probability_correct_raw"],
            changed_predicted.loc[prior, "selection_probability_correct_raw"],
        )

    def test_alignment_and_direction_mismatch_are_rejected(self):
        reference = source_frame(0.00)
        shape = source_frame(0.01)
        profile = source_frame(-0.01)
        shape.loc[0, "target_timestamp"] += pd.Timedelta(minutes=15)
        with self.assertRaisesRegex(ValueError, "source mismatch"):
            build_selective_correctness_frame(reference, shape, profile)

        shape = source_frame(0.01)
        shape.loc[0, "predicted_up"] = 1 - shape.loc[0, "predicted_up"]
        shape.loc[0, "correct"] = shape.loc[0, "predicted_up"] == shape.loc[0, "target_up"]
        with self.assertRaisesRegex(ValueError, "preserve the reference"):
            build_selective_correctness_frame(reference, shape, profile)


if __name__ == "__main__":
    unittest.main()
