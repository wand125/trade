import unittest

import pandas as pd

from trade_data.next_bar_ensemble import blend_prediction_frames


def prediction_frame(probabilities: list[float]) -> pd.DataFrame:
    rows = len(probabilities)
    timestamp = pd.date_range("2025-01-01", periods=rows, freq="15min", tz="UTC")
    return pd.DataFrame(
        {
            "timestamp": timestamp,
            "decision_timestamp": timestamp + pd.Timedelta(minutes=15),
            "target_timestamp": timestamp + pd.Timedelta(minutes=30),
            "target_up": [1, 0][:rows],
            "probability_up": probabilities,
            "predicted_up": [1, 0][:rows],
            "predicted_direction": ["up", "down"][:rows],
            "confidence": [0.6] * rows,
            "correct": [True] * rows,
            "fold": ["test"] * rows,
            "volatility_regime": ["normal"] * rows,
        }
    )


class NextBarEnsembleTests(unittest.TestCase):
    def test_blends_probabilities_and_recomputes_prediction_fields(self):
        baseline = prediction_frame([0.60, 0.40])
        candidate = prediction_frame([0.40, 0.60])

        result = blend_prediction_frames(baseline, candidate, 0.25)

        self.assertAlmostEqual(result.loc[0, "probability_up"], 0.55)
        self.assertAlmostEqual(result.loc[1, "probability_up"], 0.45)
        self.assertEqual(result["predicted_direction"].tolist(), ["up", "down"])
        self.assertEqual(result["correct"].tolist(), [True, True])

    def test_rejects_misaligned_targets(self):
        baseline = prediction_frame([0.60, 0.40])
        candidate = prediction_frame([0.40, 0.60])
        candidate.loc[0, "target_up"] = 0

        with self.assertRaisesRegex(ValueError, "target_up"):
            blend_prediction_frames(baseline, candidate, 0.25)


if __name__ == "__main__":
    unittest.main()
