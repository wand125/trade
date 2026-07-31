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
    / "entry_ev_base_policy_input_aliases.py"
)
SPEC = importlib.util.spec_from_file_location(
    "entry_ev_base_policy_input_aliases",
    SCRIPT_PATH,
)
entry_ev_base_policy_input_aliases = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = entry_ev_base_policy_input_aliases
SPEC.loader.exec_module(entry_ev_base_policy_input_aliases)


class EntryEvBasePolicyInputAliasesTest(unittest.TestCase):
    def test_prepare_predictions_adds_alias_risk_and_quantiles(self):
        frame = pd.DataFrame(
            {
                "decision_timestamp": pd.to_datetime(
                    [
                        "2025-01-01 00:00:00+00:00",
                        "2025-01-01 00:01:00+00:00",
                    ],
                    utc=True,
                ),
                "dataset_month": ["2025-01", "2025-01"],
                "combined_regime": ["range_low_vol", "range_low_vol"],
                "session_regime": ["asia", "asia"],
                "pred_calibrated_long_best_adjusted_pnl": [1.0, 3.0],
                "pred_calibrated_short_best_adjusted_pnl": [2.0, 1.0],
                "pred_long_entry_local_rank": [0.2, 0.8],
                "pred_short_entry_local_rank": [0.7, 0.1],
                "pred_long_exit_event_minutes": [60.0, 90.0],
                "pred_short_exit_event_minutes": [120.0, 30.0],
            }
        )

        output = entry_ev_base_policy_input_aliases.prepare_predictions(
            frame,
            family="toy",
            score_kind="base",
            long_column="pred_calibrated_long_best_adjusted_pnl",
            short_column="pred_calibrated_short_best_adjusted_pnl",
            long_rank_column="pred_long_entry_local_rank",
            short_rank_column="pred_short_entry_local_rank",
            long_holding_source="pred_long_exit_event_minutes",
            short_holding_source="pred_short_exit_event_minutes",
            long_holding_output="pred_mlp_long_exit_event_minutes",
            short_holding_output="pred_mlp_short_exit_event_minutes",
            risk_prefix="pred_base",
            quantile_scopes=["month"],
        )

        self.assertEqual(output["pred_mlp_long_exit_event_minutes"].tolist(), [60.0, 90.0])
        self.assertEqual(output["pred_mlp_short_exit_event_minutes"].tolist(), [120.0, 30.0])
        self.assertEqual(output["pred_base_long_predicted_ev_overestimate_risk"].tolist(), [0.0, 0.0])
        self.assertIn("pred_base_selected_score_pct_month", output.columns)
        self.assertIn("pred_base_side_gap_pct_month", output.columns)
        self.assertIn("pred_base_selected_entry_rank_pct_month", output.columns)


if __name__ == "__main__":
    unittest.main()
