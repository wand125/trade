import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from trade_data.next_bar_meta import (
    CrossTimeframeMetaConfig,
    apply_meta_blend,
    build_parser,
    build_cross_timeframe_frame,
    resolve_prediction_sources,
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
    def test_prediction_sources_support_legacy_or_split_target_context_inputs(self):
        shared = (Path("shared-a"), Path("shared-b"))
        target, context = resolve_prediction_sources(shared, (), ())
        self.assertEqual(target, shared)
        self.assertEqual(context, shared)

        target, context = resolve_prediction_sources(
            (), (Path("target"),), (Path("context-a"), Path("context-b"))
        )
        self.assertEqual(target, (Path("target"),))
        self.assertEqual(context, (Path("context-a"), Path("context-b")))

        with self.assertRaisesRegex(ValueError, "cannot be combined"):
            resolve_prediction_sources(shared, (Path("target"),), ())
        with self.assertRaisesRegex(ValueError, "provide --predictions-dir"):
            resolve_prediction_sources((), (Path("target"),), ())

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

    def test_asof_context_uses_only_latest_non_future_prediction(self):
        target = predictions(15, [0.60, 0.40])
        target["decision_timestamp"] = pd.to_datetime(
            ["2025-01-01 00:15:00Z", "2025-01-01 00:30:00Z"]
        )
        m30 = predictions(30, [0.70, 0.30])
        m30["decision_timestamp"] = pd.to_datetime(
            ["2025-01-01 00:00:00Z", "2025-01-01 00:30:00Z"]
        )
        frame, features = build_cross_timeframe_frame(
            target,
            {30: m30},
            CrossTimeframeMetaConfig(
                context_timeframes=(),
                asof_context_timeframes=(30,),
                asof_max_age_minutes=15,
            ),
        )

        self.assertEqual(features, ["logit_m15", "logit_m30"])
        self.assertEqual(frame["m30_probability_up"].tolist(), [0.70, 0.30])
        self.assertEqual(frame["m30_prediction_age_minutes"].tolist(), [15.0, 0.0])

    def test_asof_context_drops_predictions_older_than_maximum_age(self):
        target = predictions(15, [0.60, 0.40])
        target["decision_timestamp"] = pd.to_datetime(
            ["2025-01-01 00:16:00Z", "2025-01-01 00:30:00Z"]
        )
        m30 = predictions(30, [0.70])
        m30["decision_timestamp"] = pd.to_datetime(["2025-01-01 00:00:00Z"])
        frame, _ = build_cross_timeframe_frame(
            target,
            {30: m30},
            CrossTimeframeMetaConfig(
                context_timeframes=(),
                asof_context_timeframes=(30,),
                asof_max_age_minutes=15,
            ),
        )

        self.assertEqual(len(frame), 0)

    def test_m1_target_accepts_only_distinct_asof_higher_timeframes(self):
        target = predictions(1, [0.60, 0.40])
        target["decision_timestamp"] = pd.to_datetime(
            ["2025-01-01 00:14:00Z", "2025-01-01 00:15:00Z"]
        )
        m5 = predictions(5, [0.55])
        m5["decision_timestamp"] = pd.to_datetime(["2025-01-01 00:10:00Z"])
        m15 = predictions(15, [0.70])
        m15["decision_timestamp"] = pd.to_datetime(["2025-01-01 00:00:00Z"])
        frame, features = build_cross_timeframe_frame(
            target,
            {5: m5, 15: m15},
            CrossTimeframeMetaConfig(
                target_timeframe=1,
                context_timeframes=(),
                asof_context_timeframes=(5, 15),
                asof_max_age_minutes=14,
            ),
        )

        self.assertEqual(features, ["logit_m1", "logit_m5", "logit_m15"])
        self.assertEqual(frame["m5_prediction_age_minutes"].tolist(), [4.0])
        self.assertEqual(frame["m15_prediction_age_minutes"].tolist(), [14.0])
        self.assertEqual(len(frame), 1)

        with self.assertRaisesRegex(ValueError, "target timeframe"):
            build_cross_timeframe_frame(
                target,
                {1: target},
                CrossTimeframeMetaConfig(
                    target_timeframe=1,
                    context_timeframes=(),
                    asof_context_timeframes=(1,),
                ),
            )

    def test_cli_exposes_target_and_exact_context_timeframes(self):
        args = build_parser().parse_args(
            [
                "--predictions-dir",
                "predictions",
                "--output-dir",
                "output",
                "--target-timeframe",
                "1",
                "--context-timeframes",
                "",
                "--asof-context-timeframes",
                "5,15",
            ]
        )
        self.assertEqual(args.target_timeframe, 1)
        self.assertEqual(args.context_timeframes, "")
        self.assertEqual(args.asof_context_timeframes, "5,15")


if __name__ == "__main__":
    unittest.main()
