from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

import pandas as pd


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "experiments"
    / "entry_ev_policy_delta_context_diagnostics.py"
)
SPEC = importlib.util.spec_from_file_location(
    "entry_ev_policy_delta_context_diagnostics",
    SCRIPT_PATH,
)
entry_ev_policy_delta_context_diagnostics = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = entry_ev_policy_delta_context_diagnostics
SPEC.loader.exec_module(entry_ev_policy_delta_context_diagnostics)


class EntryEvPolicyDeltaContextDiagnosticsTest(unittest.TestCase):
    def test_enrich_delta_uses_candidate_timestamp_and_context(self):
        delta = pd.DataFrame(
            {
                "family": ["toy"],
                "candidate": ["q"],
                "month": ["2025-01"],
                "delta_status": ["only_candidate"],
                "direction": ["short"],
                "base_present": [False],
                "candidate_present": [True],
                "base_entry_decision_timestamp": [None],
                "candidate_entry_decision_timestamp": ["2025-01-02 00:00:00+00:00"],
                "base_adjusted_pnl": [0.0],
                "candidate_adjusted_pnl": [-10.0],
                "pnl_delta": [-10.0],
            }
        )
        predictions = pd.DataFrame(
            {
                "decision_timestamp": pd.to_datetime(
                    ["2025-01-02 00:00:00+00:00"],
                    utc=True,
                ),
                "dataset_month": ["2025-01"],
                "combined_regime": ["range_low_vol"],
                "session_regime": ["ny_overlap"],
                "pred_score_long_best_adjusted_pnl": [1.0],
                "pred_score_short_best_adjusted_pnl": [3.0],
            }
        )

        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            prediction_path = Path(tmp) / "pred.parquet"
            predictions.to_parquet(prediction_path, index=False)
            enriched = (
                entry_ev_policy_delta_context_diagnostics.enrich_delta_with_context(
                    delta,
                    family_predictions={"toy": prediction_path},
                    score_kind="score",
                )
            )

        self.assertEqual(enriched["context_id"].iloc[0], "short/range_low_vol/ny_overlap")
        self.assertEqual(enriched["prediction_selected_side"].iloc[0], "short")
        self.assertAlmostEqual(enriched["prediction_selected_score"].iloc[0], 3.0)

    def test_summarize_group_counts_candidate_pnl(self):
        frame = pd.DataFrame(
            {
                "candidate": ["q", "q"],
                "context_id": ["a", "a"],
                "base_present": [False, False],
                "candidate_present": [True, True],
                "base_adjusted_pnl": [0.0, 0.0],
                "candidate_adjusted_pnl": [5.0, -12.0],
                "pnl_delta": [5.0, -12.0],
                "prediction_selected_score": [6.0, 7.0],
                "prediction_side_gap": [2.0, 3.0],
            }
        )

        summary = entry_ev_policy_delta_context_diagnostics.summarize_group(
            frame,
            ["candidate", "context_id"],
        )

        self.assertEqual(summary["row_count"].iloc[0], 2)
        self.assertAlmostEqual(summary["candidate_adjusted_pnl"].iloc[0], -7.0)
        self.assertAlmostEqual(summary["added_positive_pnl"].iloc[0], 5.0)
        self.assertAlmostEqual(summary["added_negative_pnl"].iloc[0], -12.0)

    def test_add_delta_decision_timestamp_falls_back_to_shared_column(self):
        delta = pd.DataFrame(
            {
                "entry_decision_timestamp": ["2025-01-03 01:02:00+00:00"],
            }
        )

        output = entry_ev_policy_delta_context_diagnostics.add_delta_decision_timestamp(
            delta
        )

        self.assertEqual(
            str(output["delta_entry_decision_timestamp"].iloc[0]),
            "2025-01-03 01:02:00+00:00",
        )


if __name__ == "__main__":
    unittest.main()
