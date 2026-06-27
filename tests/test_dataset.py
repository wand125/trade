import unittest

import numpy as np
import pandas as pd

from trade_data.dataset import DatasetConfig, build_features, build_month_dataset, future_best_labels


def frame(opens, start="2025-01-01 00:00:00+00:00"):
    timestamps = pd.date_range(start=start, periods=len(opens), freq="min")
    values = pd.Series(opens, dtype="float64")
    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": values,
            "high": values + 0.1,
            "low": values - 0.1,
            "close": values,
        }
    )


class DatasetTests(unittest.TestCase):
    def test_future_best_labels_align_with_next_open_entry(self):
        df = frame([100, 101, 105, 99, 103, 102, 104])
        labels = future_best_labels(
            df,
            horizon=pd.Timedelta(minutes=3),
            min_adjusted_edge=1.0,
            profit_multiplier=0.9,
            loss_multiplier=1.3,
        )

        self.assertEqual(labels.loc[0, "entry_idx"], 1)
        self.assertEqual(labels.loc[0, "label"], 1)
        self.assertAlmostEqual(labels.loc[0, "long_best_adjusted_pnl"], 3.6)
        self.assertAlmostEqual(labels.loc[0, "short_best_adjusted_pnl"], 1.8)
        self.assertAlmostEqual(labels.loc[0, "long_forced_raw_pnl"], 2.0)
        self.assertAlmostEqual(labels.loc[0, "long_forced_adjusted_pnl"], 1.8)
        self.assertAlmostEqual(labels.loc[0, "long_max_adverse_pnl"], -2.0)
        self.assertAlmostEqual(labels.loc[0, "short_max_adverse_pnl"], -4.0)
        self.assertAlmostEqual(labels.loc[0, "side_score"], 1.8)
        self.assertEqual(labels.loc[0, "best_exit_idx"], 2)
        self.assertEqual(labels.loc[0, "long_profit_barrier_hit"], 1)
        self.assertEqual(labels.loc[0, "short_profit_barrier_hit"], 0)

        self.assertEqual(labels.loc[1, "entry_idx"], 2)
        self.assertEqual(labels.loc[1, "label"], -1)
        self.assertAlmostEqual(labels.loc[1, "short_best_adjusted_pnl"], 5.4)
        self.assertEqual(labels.loc[1, "best_exit_idx"], 3)
        self.assertEqual(labels.loc[1, "short_profit_barrier_hit"], 1)

    def test_features_use_current_and_past_values(self):
        df = frame([100, 101, 103, 106, 110])
        features, columns = build_features(df, include_fft=False)

        self.assertIn("ret_1", columns)
        expected = pd.Series([100, 101, 103, 106, 110], dtype="float64")
        self.assertAlmostEqual(features.loc[1, "ret_1"], float(np.log(expected[1] / expected[0])))
        self.assertAlmostEqual(features.loc[1, "diff_1"], 1.0)
        self.assertAlmostEqual(features.loc[2, "diff_2"], 1.0)

    def test_month_dataset_outputs_labels_and_features(self):
        values = [100 + (i % 20) for i in range(3000)]
        df = frame(values, start="2025-01-01 00:00:00+00:00")
        config = DatasetConfig(
            month="2025-01",
            horizon_hours=1,
            warmup_days=0,
            post_days=1,
            min_adjusted_edge=1.0,
            profit_multiplier=0.9,
            loss_multiplier=1.3,
            include_fft=False,
            quantile_bins=5,
            entry_timing_lookahead_minutes=60,
        )

        dataset, summary = build_month_dataset(df, "2025-01", config)

        self.assertGreater(len(dataset), 0)
        self.assertIn("ret_1", dataset.columns)
        self.assertIn("label", dataset.columns)
        self.assertIn("side_score", dataset.columns)
        self.assertIn("best_adjusted_pnl_quantile", dataset.columns)
        self.assertIn("long_profit_barrier_hit", dataset.columns)
        self.assertIn("short_profit_barrier_hit", dataset.columns)
        self.assertIn("long_wait_regret", dataset.columns)
        self.assertIn("short_wait_regret", dataset.columns)
        self.assertIn("long_entry_local_rank", dataset.columns)
        self.assertIn("short_entry_local_rank", dataset.columns)
        self.assertIn("long_entry_urgency", dataset.columns)
        self.assertIn("short_entry_urgency", dataset.columns)
        self.assertIn("long_wait_regret_quantile", dataset.columns)
        self.assertIn("long_entry_local_rank_bin", dataset.columns)
        self.assertIn("best_holding_time_bin", dataset.columns)
        self.assertEqual(summary["rows"], len(dataset))
        self.assertIn("target_columns", summary)
        self.assertIn("long_wait_regret", summary["target_columns"])
        self.assertIn("long_profit_barrier_hit", summary["target_columns"])


if __name__ == "__main__":
    unittest.main()
