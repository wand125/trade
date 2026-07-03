from __future__ import annotations

import unittest

import pandas as pd

from scripts.experiments.entry_ev_contextual_penalty_near_selected_diagnostics import (
    add_selection_rank_columns,
    attach_selected_additions,
    attach_selection_outcomes,
    near_selected_cases,
    normalize_replay_rows,
    parse_score_specs,
    penalty_label_summary,
    quota_group_summary,
    rejection_summary,
)


def sample_candidates() -> pd.DataFrame:
    base = {
        "row_scope": "available_candidates",
        "prob_threshold": 0.5,
        "ev_threshold": 0.0,
        "tail_prob_threshold": 0.5,
        "require_model_used": False,
        "ranker_score_mode": "pnl",
        "ranker_abstention_rule": "none",
        "positive_pnl_gate_rule": "none",
        "positive_pnl_penalty_label": "contextual_confidence_w1",
        "role": "fresh",
        "month": "2026-01",
        "side": "long",
        "extra_side_needed": 2.0,
        "hv_chosen_horizon_minutes": 60,
        "support_reduction_value": 1.0,
        "repair_expected_pnl": 0.0,
        "combined_regime": "range",
        "session_regime": "asia",
        "near_miss_bucket": "one_failed",
    }
    rows = []
    for i, (minute, score, actual, penalty) in enumerate(
        [
            (0, 10.0, 4.0, 0.0),
            (5, 9.0, -6.0, 1.0),
            (10, 8.0, 3.0, 0.0),
            (15, 1.0, -2.0, 1.0),
        ]
    ):
        row = dict(base)
        row.update(
            {
                "candidate_file": "candidates.csv",
                "decision_timestamp": f"2026-01-01T00:{minute:02d}:00Z",
                "entry_timestamp": f"2026-01-01T00:{minute:02d}:00Z",
                "exit_timestamp": f"2026-01-01T01:{minute:02d}:00Z",
                "repair_score": score,
                "hv_chosen_pred_pnl": score / 2.0,
                "actual_pnl_at_hv_chosen_horizon": actual,
                "adjusted_pnl": actual,
                "positive_pnl_penalty_amount": penalty,
                "positive_pnl_penalty_signal": penalty,
                "positive_pnl_penalty_contextual_prior_pointwise_gate_delta": 25.0,
                "positive_pnl_penalty_contextual_prior_loss_precision": 0.8,
                "positive_pnl_penalty_contextual_prior_winner_damage_ratio": 0.1,
                "positive_pnl_penalty_contextual_prior_observed_month_count": 2,
                "positive_pnl_penalty_contextual_prior_flagged_month_count": 2,
            }
        )
        rows.append(row)
    return pd.DataFrame(rows)


class ContextualPenaltyNearSelectedDiagnosticsTest(unittest.TestCase):
    def test_attach_selected_and_rank_penalized_rows(self) -> None:
        candidates = normalize_replay_rows(sample_candidates())
        additions = sample_candidates().iloc[[0, 2]].copy()

        attached = attach_selected_additions(candidates, additions)
        ranked = add_selection_rank_columns(
            attached,
            quota_columns=["scenario_key", "role", "month", "side"],
            rank_specs=parse_score_specs("repair_score:desc,decision_timestamp:asc"),
            near_rank_window=0,
        )

        self.assertEqual(int(ranked["selected_addition"].sum()), 2)
        penalized = ranked[ranked["penalized"]].sort_values("quota_rank")
        self.assertEqual(list(penalized["quota_rank"]), [2, 4])
        self.assertEqual(int(penalized.iloc[0]["group_quota"]), 2)
        self.assertTrue(bool(penalized.iloc[0]["within_quota"]))
        self.assertTrue(bool(penalized.iloc[0]["near_selected_boundary"]))
        self.assertFalse(bool(penalized.iloc[1]["near_selected_boundary"]))

    def test_summaries_track_selected_intersection_and_rank_gap(self) -> None:
        candidates = normalize_replay_rows(sample_candidates())
        additions = sample_candidates().iloc[[0, 2]].copy()
        rejections = sample_candidates().iloc[[1, 3]].copy()
        rejections["reject_reason"] = ["overlap", "quota_full"]
        attached = attach_selection_outcomes(candidates, additions, rejections)
        ranked = add_selection_rank_columns(
            attached,
            quota_columns=["scenario_key", "role", "month", "side"],
            rank_specs=parse_score_specs("repair_score:desc"),
            near_rank_window=1,
        )

        label = penalty_label_summary(ranked).iloc[0]
        self.assertEqual(int(label["penalized_count"]), 2)
        self.assertEqual(int(label["selected_penalized_count"]), 0)
        self.assertEqual(int(label["penalized_within_quota_count"]), 1)
        self.assertAlmostEqual(float(label["penalized_pnl"]), -8.0)

        groups = quota_group_summary(
            ranked,
            quota_columns=["scenario_key", "role", "month", "side"],
        )
        self.assertEqual(len(groups), 1)
        self.assertEqual(int(groups.iloc[0]["best_penalized_rank"]), 2)
        self.assertAlmostEqual(float(groups.iloc[0]["best_penalized_actual_pnl"]), -6.0)

        cases = near_selected_cases(ranked, limit=1)
        self.assertEqual(len(cases), 1)
        self.assertEqual(int(cases.iloc[0]["quota_rank"]), 2)
        self.assertEqual(cases.iloc[0]["selection_outcome"], "overlap")

        outcomes = rejection_summary(ranked)
        self.assertEqual(set(outcomes["selection_outcome"]), {"overlap", "quota_full"})


if __name__ == "__main__":
    unittest.main()
