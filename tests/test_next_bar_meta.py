import unittest

import numpy as np
import pandas as pd

from trade_data.next_bar_meta import (
    CrossTimeframeMetaConfig,
    apply_meta_blend,
    build_cross_timeframe_frame,
)


def predictions(timeframe: int, probabilities: list[float]) -> pd.DataFrame:
    timestamp = pd.date_range("2025-01-01", periods=len(probabilities), freq="15min", tz="UTC")
    return pd.DataFrame(
        {
            "timestamp": timestamp,
            "decision_timestamp": timestamp + pd.Timedelta(minutes=15),
            "target_timestamp": timestamp + pd.Timedelta(minutes=30),
            "target_up": [1, 0][: len(probabilities)],
            "probability_up": probabilities,
            "predicted_direction": ["up", "down"][: len(probabilities)],
            "confidence": [0.6] * len(probabilities),
            "fold": ["test"] * len(probabilities),
            "volatility_regime": ["normal"] * len(probabilities),
            "timeframe": [timeframe] * len(probabilities),
        }
    )


class NextBarMetaTests(unittest.TestCase):
    def test_builds_aligned_logit_features(self):
        target = predictions(15, [0.60, 0.40])
        contexts = {
            5: predictions(5, [0.55, 0.45]),
            1: predictions(1, [0.52, 0.48]),
        }
        frame, features = build_cross_timeframe_frame(
            target, contexts, CrossTimeframeMetaConfig()
        )

        self.assertEqual(features, ["logit_m15", "logit_m5", "logit_m1"])
        self.assertEqual(len(frame), 2)
        self.assertTrue(np.isfinite(frame[features]).all().all())

    def test_meta_blend_recomputes_direction_and_confidence(self):
        target = predictions(15, [0.60, 0.40])
        frame, _ = build_cross_timeframe_frame(
            target,
            {5: predictions(5, [0.55, 0.45]), 1: predictions(1, [0.52, 0.48])},
            CrossTimeframeMetaConfig(),
        )
        result = apply_meta_blend(frame, np.array([0.40, 0.60]), 0.25)

        self.assertAlmostEqual(result.loc[0, "probability_up"], 0.55)
        self.assertEqual(result["predicted_direction"].tolist(), ["up", "down"])
        self.assertTrue(result["correct"].all())


if __name__ == "__main__":
    unittest.main()
