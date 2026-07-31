from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from scripts.experiments.entry_ev_loss_first_quantile_inputs import (
    FamilyPredictions,
    add_chronological_loss_first_quantiles,
    prediction_month_series,
)


class EntryEvLossFirstQuantileInputsTests(unittest.TestCase):
    def test_prediction_month_series_uses_dataset_month(self) -> None:
        frame = pd.DataFrame({"dataset_month": ["2024-01-01", "2024-02"]})

        months = prediction_month_series(frame)

        self.assertEqual(months.tolist(), ["2024-01", "2024-02"])

    def test_global_pooling_uses_only_prior_months(self) -> None:
        family_a = pd.DataFrame(
            {
                "dataset_month": ["2024-01", "2024-02"],
                "long_loss": [0.1, 0.3],
                "short_loss": [0.2, 0.4],
            }
        )
        family_b = pd.DataFrame(
            {
                "dataset_month": ["2024-01", "2024-02"],
                "long_loss": [0.5, 0.7],
                "short_loss": [0.6, 0.8],
            }
        )
        families = [
            FamilyPredictions("a", pd.NA, family_a, prediction_month_series(family_a)),
            FamilyPredictions("b", pd.NA, family_b, prediction_month_series(family_b)),
        ]

        outputs, summary = add_chronological_loss_first_quantiles(
            families,
            long_column="long_loss",
            short_column="short_loss",
            long_output_column="long_q",
            short_output_column="short_q",
            pooling="global",
            min_fit_rows=1,
            insufficient_fill_value=0.0,
        )

        self.assertEqual(outputs["a"].loc[0, "long_q"], 0.0)
        self.assertEqual(outputs["a"].loc[1, "long_q"], 0.5)
        self.assertEqual(outputs["b"].loc[1, "long_q"], 1.0)
        feb = summary[(summary["family"] == "a") & (summary["month"] == "2024-02")]
        self.assertEqual(feb["fit_rows"].tolist(), [2, 2])

    def test_family_pooling_excludes_other_families(self) -> None:
        family_a = pd.DataFrame(
            {
                "dataset_month": ["2024-01", "2024-02"],
                "long_loss": [0.1, 0.3],
                "short_loss": [0.2, 0.4],
            }
        )
        family_b = pd.DataFrame(
            {
                "dataset_month": ["2024-01", "2024-02"],
                "long_loss": [0.5, 0.7],
                "short_loss": [0.6, 0.8],
            }
        )
        families = [
            FamilyPredictions("a", pd.NA, family_a, prediction_month_series(family_a)),
            FamilyPredictions("b", pd.NA, family_b, prediction_month_series(family_b)),
        ]

        outputs, summary = add_chronological_loss_first_quantiles(
            families,
            long_column="long_loss",
            short_column="short_loss",
            long_output_column="long_q",
            short_output_column="short_q",
            pooling="family",
            min_fit_rows=1,
            insufficient_fill_value=0.0,
        )

        self.assertEqual(outputs["a"].loc[1, "long_q"], 1.0)
        self.assertEqual(outputs["b"].loc[1, "long_q"], 1.0)
        feb = summary[(summary["family"] == "a") & (summary["month"] == "2024-02")]
        self.assertEqual(feb["fit_rows"].tolist(), [1, 1])

    def test_insufficient_fit_leaves_quantiles_missing(self) -> None:
        frame = pd.DataFrame(
            {
                "dataset_month": ["2024-01", "2024-02"],
                "long_loss": [0.1, 0.3],
                "short_loss": [0.2, 0.4],
            }
        )
        families = [FamilyPredictions("a", pd.NA, frame, prediction_month_series(frame))]

        outputs, summary = add_chronological_loss_first_quantiles(
            families,
            long_column="long_loss",
            short_column="short_loss",
            long_output_column="long_q",
            short_output_column="short_q",
            pooling="family",
            min_fit_rows=2,
            insufficient_fill_value=0.0,
        )

        self.assertEqual(outputs["a"]["long_q"].tolist(), [0.0, 0.0])
        self.assertIn("insufficient_fit", summary["status"].tolist())


if __name__ == "__main__":
    unittest.main()
