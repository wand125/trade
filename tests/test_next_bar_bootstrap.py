import unittest

import pandas as pd

from trade_data.next_bar_bootstrap import paired_daily_block_bootstrap


def prediction_frames() -> tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    for day in range(8):
        fold = "test2020" if day < 4 else "test2024"
        for row in range(10):
            correct = row < 6
            rows.append(
                {
                    "fold": fold,
                    "timestamp": pd.Timestamp("2020-01-01", tz="UTC")
                    + pd.Timedelta(days=day, minutes=15 * row),
                    "target_up": int(correct),
                    "probability_up": 0.55 if correct else 0.45,
                    "confidence": 0.54,
                    "correct": correct,
                }
            )
    second = pd.DataFrame(rows)
    first = second.copy()
    first.loc[~first["correct"], "confidence"] = 0.51
    first["probability_up"] = first["target_up"] * 0.56 + (1 - first["target_up"]) * 0.44
    return first, second


class NextBarBootstrapTests(unittest.TestCase):
    def test_daily_bootstrap_is_paired_deterministic_and_period_aware(self):
        first, second = prediction_frames()
        report = paired_daily_block_bootstrap(
            first, second, 0.53, iterations=200, random_seed=7
        )
        repeated = paired_daily_block_bootstrap(
            first, second, 0.53, iterations=200, random_seed=7
        )

        self.assertEqual(report, repeated)
        self.assertEqual(report["periods"]["development"]["utc_day_blocks"], 4)
        self.assertEqual(report["periods"]["confirmation"]["utc_day_blocks"], 4)
        score = report["periods"]["all"]["metrics"]["lane_selection_score"]
        self.assertGreater(score["delta_first_minus_second"], 0)
        self.assertTrue(score["interval_supports_first_better"])
        brier = report["periods"]["all"]["metrics"]["brier_score"]
        self.assertLess(brier["delta_first_minus_second"], 0)
        self.assertTrue(brier["interval_supports_first_better"])

        all_rows = paired_daily_block_bootstrap(
            first, second, 0.5, iterations=100, random_seed=7
        )
        coverage = all_rows["periods"]["all"]["metrics"]["lane_coverage"]
        self.assertEqual(coverage["delta_first_minus_second"], 0.0)

    def test_daily_bootstrap_rejects_misaligned_predictions(self):
        first, second = prediction_frames()
        second.loc[0, "timestamp"] += pd.Timedelta(minutes=1)
        with self.assertRaisesRegex(ValueError, "align"):
            paired_daily_block_bootstrap(first, second, 0.53, iterations=100)


if __name__ == "__main__":
    unittest.main()
