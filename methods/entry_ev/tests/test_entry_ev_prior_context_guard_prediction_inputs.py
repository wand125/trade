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
    / "entry_ev_prior_context_guard_prediction_inputs.py"
)
SPEC = importlib.util.spec_from_file_location(
    "entry_ev_prior_context_guard_prediction_inputs",
    SCRIPT_PATH,
)
entry_ev_prior_context_guard_prediction_inputs = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = entry_ev_prior_context_guard_prediction_inputs
SPEC.loader.exec_module(entry_ev_prior_context_guard_prediction_inputs)


class EntryEvPriorContextGuardPredictionInputsTest(unittest.TestCase):
    def test_add_prior_guard_columns_flags_pre_only_short_with_prior_loss(self):
        candidate = (
            entry_ev_prior_context_guard_prediction_inputs.policy_candidate_from_name(
                "q50_sg0_rank0_floor5_month"
            )
        )
        pre = pd.DataFrame(
            {
                "decision_timestamp": pd.to_datetime(
                    [
                        "2025-04-02 00:00:00+00:00",
                        "2025-05-02 00:00:00+00:00",
                        "2025-05-03 00:00:00+00:00",
                    ],
                    utc=True,
                ),
                "dataset_month": ["2025-04", "2025-05", "2025-05"],
                "combined_regime": [
                    "down_normal_vol",
                    "down_normal_vol",
                    "range_normal_vol",
                ],
                "pre_long": [1.0, 1.0, 1.0],
                "pre_short": [8.0, 9.0, 9.0],
                "post_long": [1.0, 1.0, 1.0],
                "post_short": [8.0, 9.0, 9.0],
                "long_hold": [60.0, 60.0, 60.0],
                "short_hold": [60.0, 60.0, 60.0],
                "pred_pre_selected_score_pct_month": [0.9, 0.9, 0.9],
                "pred_pre_side_gap_pct_month": [0.9, 0.9, 0.9],
                "pred_pre_selected_entry_rank_pct_month": [0.9, 0.9, 0.9],
            }
        )
        post = pre[
            [
                "decision_timestamp",
                "dataset_month",
                "combined_regime",
                "post_long",
                "post_short",
                "long_hold",
                "short_hold",
            ]
        ].copy()
        post["pred_post_selected_score_pct_month"] = [0.9, 0.1, 0.1]
        post["pred_post_side_gap_pct_month"] = [0.9, 0.9, 0.9]
        post["pred_post_selected_entry_rank_pct_month"] = [0.9, 0.9, 0.9]
        delta = pd.DataFrame(
            {
                "candidate": [candidate.name],
                "delta_status": ["only_candidate"],
                "month": ["2025-04"],
                "direction": ["short"],
                "combined_regime": ["down_normal_vol"],
                "candidate_adjusted_pnl": [-70.0],
            }
        )
        prior_active = (
            entry_ev_prior_context_guard_prediction_inputs.prior_context_active_table(
                delta,
                candidates=[candidate.name],
                thresholds=[20.0],
            )
        )

        guarded, summary = (
            entry_ev_prior_context_guard_prediction_inputs.add_prior_guard_columns(
                pre,
                post,
                family="toy",
                candidates=[candidate],
                prior_active=prior_active,
                thresholds=[20.0],
                pre_score_kind="pre",
                post_score_kind="post",
                pre_long_column="pre_long",
                pre_short_column="pre_short",
                post_long_column="post_long",
                post_short_column="post_short",
                long_holding_column="long_hold",
                short_holding_column="short_hold",
                min_valid_predicted_hold_minutes=30.0,
            )
        )

        guard_column = summary["guard_column"].iloc[0]
        self.assertEqual(guarded[guard_column].tolist(), ["0", "1", "0"])
        self.assertEqual(summary["newly_admitted_short_rows"].iloc[0], 2)
        self.assertEqual(summary["blocked_rows"].iloc[0], 1)


if __name__ == "__main__":
    unittest.main()
