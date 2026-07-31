import importlib.util
import unittest
from pathlib import Path

import pandas as pd


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "experiments" / "merge_prediction_columns.py"
SPEC = importlib.util.spec_from_file_location("merge_prediction_columns", SCRIPT_PATH)
merge_prediction_columns = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(merge_prediction_columns)


class MergePredictionColumnsTests(unittest.TestCase):
    def test_merge_prediction_columns_adds_requested_columns_by_key(self):
        base = pd.DataFrame(
            {
                "dataset_month": ["2025-02", "2025-02", "2025-03"],
                "decision_timestamp": pd.to_datetime(
                    ["2025-02-01 00:00", "2025-02-01 00:01", "2025-03-01 00:00"],
                    utc=True,
                ),
                "pred_base": [1.0, 2.0, 3.0],
            }
        )
        source = pd.DataFrame(
            {
                "dataset_month": ["2025-02", "2025-03"],
                "decision_timestamp": pd.to_datetime(
                    ["2025-02-01 00:00", "2025-03-01 00:00"],
                    utc=True,
                ),
                "pred_extra": [0.5, 0.7],
            }
        )

        output, summary = merge_prediction_columns.merge_prediction_columns(
            base,
            source,
            keys=["dataset_month", "decision_timestamp"],
            columns=["pred_extra"],
            replace_existing=False,
        )

        self.assertEqual(summary["added_columns"], ["pred_extra"])
        self.assertEqual(summary["matched_rows"], 2)
        self.assertEqual(summary["missing_matches"], 1)
        self.assertEqual(output["pred_extra"].iloc[0], 0.5)
        self.assertTrue(pd.isna(output["pred_extra"].iloc[1]))
        self.assertEqual(output["pred_extra"].iloc[2], 0.7)

    def test_merge_prediction_columns_skips_existing_without_replace(self):
        base = pd.DataFrame(
            {
                "dataset_month": ["2025-02"],
                "decision_timestamp": pd.to_datetime(["2025-02-01 00:00"], utc=True),
                "pred_extra": [0.1],
            }
        )
        source = pd.DataFrame(
            {
                "dataset_month": ["2025-02"],
                "decision_timestamp": pd.to_datetime(["2025-02-01 00:00"], utc=True),
                "pred_extra": [0.9],
            }
        )

        output, summary = merge_prediction_columns.merge_prediction_columns(
            base,
            source,
            keys=["dataset_month", "decision_timestamp"],
            columns=["pred_extra"],
            replace_existing=False,
        )

        self.assertEqual(summary["added_columns"], [])
        self.assertEqual(summary["skipped_existing_columns"], ["pred_extra"])
        self.assertEqual(output["pred_extra"].tolist(), [0.1])


if __name__ == "__main__":
    unittest.main()
