import unittest

import numpy as np
import pandas as pd

from trade_data.quantile_calibration import (
    add_empirical_quantile_columns,
    empirical_cdf_scores,
)


class QuantileCalibrationTests(unittest.TestCase):
    def test_empirical_cdf_scores_uses_fit_distribution(self):
        fit = pd.Series([0.1, 0.2, 0.4, 0.4])
        values = pd.Series([0.05, 0.1, 0.3, 0.4, 0.5, np.nan])

        scores = empirical_cdf_scores(fit, values)

        self.assertEqual(scores.iloc[:5].tolist(), [0.0, 0.25, 0.5, 1.0, 1.0])
        self.assertTrue(np.isnan(scores.iloc[5]))

    def test_add_empirical_quantile_columns_adds_named_outputs(self):
        fit = pd.DataFrame(
            {
                "long_prob": [0.2, 0.4, 0.6, 0.8],
                "short_prob": [0.1, 0.3, 0.5, 0.7],
            }
        )
        apply = pd.DataFrame(
            {
                "long_prob": [0.5, 0.9],
                "short_prob": [0.2, 0.6],
            }
        )

        output, summary = add_empirical_quantile_columns(
            fit,
            apply,
            ["long_prob", "short_prob"],
            output_columns=["long_q", "short_q"],
        )

        self.assertEqual(output["long_q"].tolist(), [0.5, 1.0])
        self.assertEqual(output["short_q"].tolist(), [0.25, 0.75])
        self.assertEqual(summary["source_columns"], ["long_prob", "short_prob"])
        self.assertEqual(summary["output_columns"], ["long_q", "short_q"])


if __name__ == "__main__":
    unittest.main()
