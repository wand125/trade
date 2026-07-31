from __future__ import annotations

import unittest

import pandas as pd

from scripts.experiments.entry_ev_positive_pnl_failure_diagnostics import normalize_candidates
from scripts.experiments.entry_ev_tail_ceiling_residual_failure_diagnostics import (
    add_tail_ceiling_columns,
    filter_penalty_labels,
    tail_ceiling_summary,
    tail_pass_context_summary,
    tail_pass_failure_cases,
)


def sample_candidates() -> pd.DataFrame:
    base = {
        "candidate_file": "candidates.csv",
        "family": "f",
        "role": "fresh",
        "month": "2026-01",
        "side": "long",
        "row_scope": "available_candidates",
        "ranker_score_mode": "pnl",
        "ranker_abstention_rule": "none",
        "combined_regime": "range",
        "session_regime": "asia",
        "near_miss_bucket": "one_failed",
        "hv_chosen_horizon_minutes": 60.0,
        "hv_chosen_pred_harmful_overestimate_prob": 0.2,
        "hv_chosen_pred_executable_prob": 0.8,
        "hv_chosen_pred_model_used": True,
        "target_pnl_hurdle": 0.0,
        "extra_side_needed": 1.0,
        "prob_threshold": 0.5,
        "ev_threshold": 0.0,
        "tail_prob_threshold": 0.5,
        "repair_score": 1.0,
        "positive_pnl_penalty_label": "none",
        "ranker_hv_60m_prior_mean_pnl": 1.0,
        "ranker_hv_60m_prior_tail_loss_rate": 0.1,
        "ranker_hv_60m_prior_risk_score": 1.0,
        "ranker_hv_60m_residual_bias": 0.5,
        "ranker_hv_60m_residual_mae": 3.0,
        "ranker_hv_60m_residual_overestimate_rate": 0.4,
        "ranker_hv_60m_residual_tail_miss_rate": 0.05,
        "ranker_hv_60m_tail_reliability": 0.8,
        "ranker_hv_60m_tail_reliability_used": True,
        "ranker_hv_60m_tail_train_months": 5.0,
        "ranker_hv_60m_tail_train_rows": 100.0,
        "pred_hv_60m_pnl_model_used": True,
        "pred_hv_60m_tail_model_used": True,
    }
    rows = []
    specs = [
        ("2026-01-01T00:00:00Z", 4.0, -2.0, 0.20, "none"),
        ("2026-01-01T00:05:00Z", 5.0, 3.0, 0.25, "none"),
        ("2026-01-01T00:10:00Z", 6.0, -8.0, 0.35, "none"),
        ("2026-01-01T00:15:00Z", 7.0, -4.0, 0.20, "contextual_confidence_w1"),
    ]
    for timestamp, pred, actual, tail_prob, label in specs:
        row = dict(base)
        row.update(
            {
                "decision_timestamp": timestamp,
                "hv_chosen_pred_pnl": pred,
                "actual_pnl_at_hv_chosen_horizon": actual,
                "hv_chosen_pred_tail_loss_prob": tail_prob,
                "positive_pnl_penalty_label": label,
            }
        )
        rows.append(row)
    return pd.DataFrame(rows)


class TailCeilingResidualFailureDiagnosticsTest(unittest.TestCase):
    def test_tail_ceiling_columns_split_pass_and_blocked_failures(self) -> None:
        output = add_tail_ceiling_columns(
            normalize_candidates(sample_candidates()),
            max_tail_prob=0.3,
        )
        none_rows = filter_penalty_labels(output, ["none"])

        self.assertEqual(int(none_rows["tail_pass_positive"].sum()), 2)
        self.assertEqual(int(none_rows["tail_pass_positive_loss"].sum()), 1)
        self.assertEqual(int(none_rows["tail_blocked_positive_loss"].sum()), 1)
        self.assertEqual(int(none_rows["tail_pass_positive_large_loss"].sum()), 0)
        self.assertEqual(int(none_rows["tail_blocked_positive_large_loss"].sum()), 1)

    def test_tail_ceiling_summary_context_and_cases(self) -> None:
        output = add_tail_ceiling_columns(
            normalize_candidates(sample_candidates()),
            max_tail_prob=0.3,
        )
        none_rows = filter_penalty_labels(output, ["none"])
        summary = tail_ceiling_summary(
            none_rows,
            dedup_modes=["candidate_key"],
            group_columns=[
                "positive_pnl_penalty_label",
                "ranker_score_mode",
                "ranker_abstention_rule",
                "row_scope",
            ],
        )

        overall = summary[summary["scope"].eq("candidate_key") & summary["ranker_score_mode"].isna()]
        self.assertEqual(int(overall.iloc[0]["tail_pass_positive_loss_count"]), 1)
        self.assertAlmostEqual(float(overall.iloc[0]["tail_pass_positive_loss_pnl"]), -2.0)
        self.assertEqual(int(overall.iloc[0]["tail_blocked_positive_large_loss_count"]), 1)

        context = tail_pass_context_summary(none_rows, dedup_mode="candidate_key")
        self.assertEqual(len(context), 1)
        self.assertEqual(int(context.iloc[0]["tail_pass_positive_loss_count"]), 1)

        cases = tail_pass_failure_cases(none_rows, dedup_mode="candidate_key", limit=5)
        self.assertEqual(len(cases), 1)
        self.assertAlmostEqual(float(cases.iloc[0]["actual_pnl_at_hv_chosen_horizon"]), -2.0)


if __name__ == "__main__":
    unittest.main()
