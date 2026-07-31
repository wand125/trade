import importlib.util
import unittest
from pathlib import Path

import pandas as pd


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "experiments" / "holding_max_grid.py"
SPEC = importlib.util.spec_from_file_location("holding_max_grid", SCRIPT_PATH)
holding_max_grid = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(holding_max_grid)


class HoldingMaxGridTests(unittest.TestCase):
    def test_prediction_coverage_marks_post_exit_predictions(self):
        predictions = pd.DataFrame(
            {
                "decision_timestamp": pd.to_datetime(
                    [
                        "2025-06-01 00:00:00+00:00",
                        "2025-06-30 23:59:00+00:00",
                        "2025-07-01 01:00:00+00:00",
                    ],
                    utc=True,
                ),
                "dataset_month": ["2025-06", "2025-06", "2025-07"],
            }
        )

        coverage = holding_max_grid.prediction_coverage(
            predictions,
            months=["2025-06"],
            max_hold_hours=24.0,
        )

        self.assertEqual(coverage.loc[0, "evaluation_prediction_rows"], 2)
        self.assertEqual(coverage.loc[0, "post_exit_prediction_rows"], 1)
        self.assertTrue(bool(coverage.loc[0, "has_post_exit_predictions"]))
        self.assertFalse(bool(coverage.loc[0, "covers_full_max_exit_window"]))

    def test_prediction_coverage_marks_full_window_only_when_post_exit_reaches_end(self):
        predictions = pd.DataFrame(
            {
                "decision_timestamp": pd.to_datetime(
                    [
                        "2025-06-30 23:59:00+00:00",
                        "2025-07-02 00:00:00+00:00",
                    ],
                    utc=True,
                ),
                "dataset_month": ["2025-06", "2025-07"],
            }
        )

        coverage = holding_max_grid.prediction_coverage(
            predictions,
            months=["2025-06"],
            max_hold_hours=24.0,
        )

        self.assertEqual(coverage.loc[0, "post_exit_prediction_rows"], 1)
        self.assertTrue(bool(coverage.loc[0, "has_post_exit_predictions"]))
        self.assertTrue(bool(coverage.loc[0, "covers_full_max_exit_window"]))

    def test_merge_prediction_frames_rejects_duplicate_timestamps(self):
        required_columns = ["decision_timestamp", "pred_long", "pred_short"]
        frame = pd.DataFrame(
            {
                "decision_timestamp": pd.to_datetime(["2025-06-01 00:00:00+00:00"], utc=True),
                "dataset_month": ["2025-06"],
                "pred_long": [1.0],
                "pred_short": [2.0],
            }
        )
        with self.subTest("duplicate timestamps"):
            with self.assertRaisesRegex(ValueError, "duplicate timestamps"):
                holding_max_grid.merge_prediction_frames_from_frames(
                    [frame, frame],
                    required_columns=required_columns,
                )


if __name__ == "__main__":
    unittest.main()
