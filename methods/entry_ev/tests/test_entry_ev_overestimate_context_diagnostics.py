import importlib.util
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "experiments"
    / "entry_ev_overestimate_context_diagnostics.py"
)
SPEC = importlib.util.spec_from_file_location(
    "entry_ev_overestimate_context_diagnostics",
    SCRIPT_PATH,
)
entry_ev_overestimate_context_diagnostics = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = entry_ev_overestimate_context_diagnostics
SPEC.loader.exec_module(entry_ev_overestimate_context_diagnostics)


class EntryEvOverestimateContextDiagnosticsTests(unittest.TestCase):
    def test_bucketize_context_derives_low_capacity_buckets(self):
        frame = pd.DataFrame(
            {
                "prior_downside_support_weight": [0.0, 0.1, 0.3, 0.8],
                "feature_pressure_score": [0.1, 0.3, 0.6, 0.8],
                "side_balance_signed_drift_for_trade": [-0.1, 0.0, 0.1, np.nan],
                "prior_downside_risk_score": [0.0, 0.1, 0.3, 0.6],
            }
        )

        bucketed = entry_ev_overestimate_context_diagnostics.bucketize_context(frame)

        self.assertEqual(bucketed["prior_support_bucket"].tolist(), ["missing", "low", "medium", "high"])
        self.assertEqual(bucketed["feature_pressure_bucket"].tolist(), ["low", "medium", "high", "extreme"])
        self.assertEqual(bucketed["prior_downside_bucket"].tolist(), ["zero", "low", "medium", "high"])
        self.assertEqual(bucketed["side_drift_bucket"].tolist(), ["negative", "neutral", "positive", "neutral"])

    def test_summarize_by_tracks_high_risk_pnl(self):
        frame = pd.DataFrame(
            {
                "role": ["fresh", "fresh", "refit"],
                "direction": ["long", "long", "long"],
                "adjusted_pnl": [-5.0, 2.0, 7.0],
                "executable_ev_overestimate_target": [True, False, False],
                "predicted_ev_overestimate_risk": [0.7, 0.2, 0.8],
                "ev_overestimate_prediction_available": [True, True, True],
            }
        )

        summary = entry_ev_overestimate_context_diagnostics.summarize_by(
            frame,
            group_columns=["direction"],
            target="executable_ev_overestimate_target",
            risk_threshold=0.5,
        )
        row = summary.iloc[0]

        self.assertEqual(row["row_count"], 3)
        self.assertAlmostEqual(row["high_risk_pnl"], 2.0)
        self.assertAlmostEqual(row["low_or_unknown_risk_pnl"], 2.0)
        self.assertAlmostEqual(row["target_rate"], 1 / 3)

    def test_role_contrast_compares_fresh_and_refit_high_risk_pnl(self):
        role_context = pd.DataFrame(
            {
                "role": ["fresh2024_validation", "refit2025_validation"],
                "direction": ["long", "long"],
                "row_count": [2, 2],
                "total_pnl": [-10.0, 8.0],
                "target_rate": [0.5, 0.0],
                "predicted_risk_mean": [0.7, 0.8],
                "high_risk_count": [2, 2],
                "high_risk_share": [1.0, 1.0],
                "high_risk_pnl": [-10.0, 8.0],
            }
        )

        contrast = entry_ev_overestimate_context_diagnostics.build_role_contrast(
            role_context,
            context_columns=["direction"],
        )
        row = contrast.iloc[0]

        self.assertEqual(row["direction"], "long")
        self.assertAlmostEqual(row["fresh_minus_refit_high_risk_pnl"], -18.0)
        self.assertAlmostEqual(row["all_validation_high_risk_pnl"], -2.0)


if __name__ == "__main__":
    unittest.main()
