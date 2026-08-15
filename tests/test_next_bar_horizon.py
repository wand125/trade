import unittest

import numpy as np
import pandas as pd

from trade_data.next_bar import resample_complete_bars
from trade_data.next_bar_horizon import (
    build_fixed_horizon_outcomes,
    parse_positive_ints,
    summarize_fixed_horizons,
)


def source_frame(rows: int = 180) -> pd.DataFrame:
    timestamp = pd.date_range("2025-01-01", periods=rows, freq="min", tz="UTC")
    close = 2000 + np.arange(rows, dtype="float64") * 0.01
    open_ = np.r_[close[0] - 0.01, close[:-1]]
    return pd.DataFrame(
        {
            "timestamp": timestamp,
            "open": open_,
            "high": np.maximum(open_, close) + 0.01,
            "low": np.minimum(open_, close) - 0.01,
            "close": close,
            "volume": 0,
        }
    )


def prediction_frame() -> pd.DataFrame:
    decisions = pd.date_range("2025-01-01 00:15", periods=8, freq="15min", tz="UTC")
    return pd.DataFrame(
        {
            "timestamp": decisions - pd.Timedelta(minutes=15),
            "decision_timestamp": decisions,
            "target_timestamp": decisions + pd.Timedelta(minutes=15),
            "predicted_direction": ["up", "down"] * 4,
            "confidence": [0.55] * 8,
            "fold": ["a"] * 4 + ["b"] * 4,
        }
    )


class FixedHorizonTests(unittest.TestCase):
    def test_parser_rejects_nonpositive_and_duplicate_horizons(self):
        self.assertEqual(parse_positive_ints("1,2,4"), (1, 2, 4))
        with self.assertRaises(Exception):
            parse_positive_ints("1,1")
        with self.assertRaises(Exception):
            parse_positive_ints("0,2")

    def test_outcomes_use_decision_open_and_exact_future_close(self):
        source = source_frame()
        predictions = prediction_frame()
        outcomes = build_fixed_horizon_outcomes(source, predictions, 15, (1, 2, 4))
        bars = resample_complete_bars(source, 15).set_index("timestamp")
        first = outcomes.iloc[0]
        decision = first["decision_timestamp"]
        self.assertAlmostEqual(first["entry_open"], bars.loc[decision, "open"])
        self.assertAlmostEqual(
            first["gross_price_4"],
            bars.loc[decision + pd.Timedelta(minutes=45), "close"]
            - bars.loc[decision, "open"],
        )
        changed = source.copy()
        changed.loc[changed["timestamp"] < decision, ["open", "high", "low", "close"]] += 100
        changed_outcomes = build_fixed_horizon_outcomes(changed, predictions, 15, (1, 2, 4))
        np.testing.assert_allclose(
            outcomes[["gross_price_1", "gross_price_2", "gross_price_4"]],
            changed_outcomes[["gross_price_1", "gross_price_2", "gross_price_4"]],
            equal_nan=True,
        )

    def test_gap_invalidates_horizon_instead_of_bridging_it(self):
        source = source_frame()
        source = source.loc[~source["timestamp"].between(
            pd.Timestamp("2025-01-01 00:30", tz="UTC"),
            pd.Timestamp("2025-01-01 00:44", tz="UTC"),
        )]
        outcomes = build_fixed_horizon_outcomes(source, prediction_frame(), 15, (1, 2))
        first = outcomes.iloc[0]
        self.assertTrue(np.isfinite(first["gross_price_1"]))
        self.assertTrue(np.isnan(first["gross_price_2"]))

    def test_summary_uses_worst_fold_mean_as_cost_ceiling(self):
        outcomes = build_fixed_horizon_outcomes(source_frame(), prediction_frame(), 15, (1,))
        report = summarize_fixed_horizons(outcomes, (1,), 0.54, 0.26)
        result = report["results"][0]
        expected = min(row["gross_mean_per_oz"] for row in result["folds"])
        self.assertAlmostEqual(result["all_fold_cost_ceiling_per_oz"], expected)
        self.assertAlmostEqual(
            result["net_mean_per_oz"], result["gross_mean_per_oz"] - 0.26
        )

    def test_summary_can_exclude_seed_training_fold(self):
        outcomes = build_fixed_horizon_outcomes(source_frame(), prediction_frame(), 15, (1,))
        report = summarize_fixed_horizons(
            outcomes, (1,), 0.54, 0.26, excluded_folds=("a",)
        )
        result = report["results"][0]
        self.assertEqual(report["excluded_folds"], ["a"])
        self.assertEqual([row["fold"] for row in result["folds"]], ["b"])
        self.assertEqual(result["rows"], 4)


if __name__ == "__main__":
    unittest.main()
