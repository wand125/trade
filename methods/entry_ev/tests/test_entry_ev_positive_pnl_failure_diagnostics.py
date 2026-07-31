from __future__ import annotations

import unittest

import pandas as pd

from scripts.experiments.entry_ev_positive_pnl_failure_diagnostics import (
    normalize_candidates,
    overall_summary,
    rule_summary,
    top_failure_cases,
)


def sample_candidates() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "candidate_file": ["a.csv", "a.csv", "b.csv"],
            "family": ["f", "f", "f"],
            "role": ["fresh", "fresh", "refit"],
            "month": ["2026-01", "2026-01", "2026-02"],
            "side": ["long", "long", "short"],
            "row_scope": ["available_candidates"] * 3,
            "decision_timestamp": [
                "2026-01-01T00:00:00Z",
                "2026-01-01T00:05:00Z",
                "2026-02-01T00:00:00Z",
            ],
            "ranker_score_mode": ["pnl", "pnl", "pnl_delta_tail"],
            "ranker_abstention_rule": ["none", "none", "pred_pnl_lt0_switch_veto"],
            "combined_regime": ["range", "range", "trend"],
            "session_regime": ["asia", "asia", "ny"],
            "near_miss_bucket": ["one_failed", "one_failed", "strict"],
            "hv_chosen_horizon_minutes": [720.0, 720.0, 60.0],
            "hv_chosen_pred_pnl": [2.0, 3.0, 4.0],
            "hv_chosen_pred_tail_loss_prob": [0.35, 0.32, 0.05],
            "hv_chosen_pred_harmful_overestimate_prob": [0.4, 0.2, 0.1],
            "hv_chosen_pred_executable_prob": [0.7, 0.8, 0.9],
            "hv_chosen_pred_model_used": [True, True, True],
            "actual_pnl_at_hv_chosen_horizon": [-6.0, 8.0, -1.0],
            "target_pnl_hurdle": [0.0, 0.0, 0.0],
            "extra_side_needed": [1.0, 1.0, 1.0],
            "prob_threshold": [0.5, 0.5, 0.5],
            "ev_threshold": [0.0, 0.0, 0.0],
            "tail_prob_threshold": [0.5, 0.5, 0.5],
            "repair_score": [1.0, 2.0, 3.0],
            "ranker_hv_720m_prior_mean_pnl": [-1.0, -1.0, 0.0],
            "ranker_hv_720m_prior_tail_loss_rate": [0.4, 0.4, 0.0],
            "ranker_hv_720m_prior_risk_score": [6.0, 6.0, 0.0],
            "ranker_hv_720m_residual_bias": [3.0, 3.0, 0.0],
            "ranker_hv_720m_residual_mae": [12.0, 12.0, 0.0],
            "ranker_hv_720m_residual_overestimate_rate": [0.7, 0.7, 0.0],
            "ranker_hv_720m_residual_tail_miss_rate": [0.2, 0.2, 0.0],
            "ranker_hv_720m_tail_reliability": [0.1, 0.1, 0.0],
            "ranker_hv_720m_tail_reliability_used": [False, False, False],
            "ranker_hv_720m_tail_train_months": [2.0, 2.0, 0.0],
            "ranker_hv_720m_tail_train_rows": [100.0, 100.0, 0.0],
            "pred_hv_720m_pnl_model_used": [True, True, False],
            "pred_hv_720m_tail_model_used": [True, True, False],
            "ranker_hv_60m_prior_mean_pnl": [0.0, 0.0, 1.0],
            "ranker_hv_60m_prior_tail_loss_rate": [0.0, 0.0, 0.05],
            "ranker_hv_60m_prior_risk_score": [0.0, 0.0, 0.0],
            "ranker_hv_60m_residual_bias": [0.0, 0.0, 0.0],
            "ranker_hv_60m_residual_mae": [0.0, 0.0, 2.0],
            "ranker_hv_60m_residual_overestimate_rate": [0.0, 0.0, 0.3],
            "ranker_hv_60m_residual_tail_miss_rate": [0.0, 0.0, 0.0],
            "ranker_hv_60m_tail_reliability": [0.0, 0.0, 0.8],
            "ranker_hv_60m_tail_reliability_used": [False, False, True],
            "ranker_hv_60m_tail_train_months": [0.0, 0.0, 5.0],
            "ranker_hv_60m_tail_train_rows": [0.0, 0.0, 500.0],
            "pred_hv_60m_pnl_model_used": [False, False, True],
            "pred_hv_60m_tail_model_used": [False, False, True],
        }
    )


class EntryEvPositivePnlFailureDiagnosticsTest(unittest.TestCase):
    def test_normalize_extracts_chosen_horizon_wide_columns(self) -> None:
        output = normalize_candidates(sample_candidates())

        first = output.iloc[0]
        third = output.iloc[2]
        self.assertTrue(bool(first["positive_pred_loss"]))
        self.assertAlmostEqual(float(first["chosen_prior_mean_pnl"]), -1.0)
        self.assertAlmostEqual(float(first["chosen_residual_mae"]), 12.0)
        self.assertFalse(bool(first["chosen_tail_reliability_used"]))
        self.assertTrue(bool(first["chosen_pnl_model_used"]))
        self.assertAlmostEqual(float(third["chosen_prior_mean_pnl"]), 1.0)
        self.assertAlmostEqual(float(third["chosen_tail_reliability"]), 0.8)
        self.assertTrue(bool(third["chosen_tail_reliability_used"]))

    def test_rule_summary_tracks_loss_recall_and_winner_damage(self) -> None:
        output = normalize_candidates(sample_candidates())
        summary = rule_summary(
            output,
            rules=["tail_prob_ge_0p30", "prior_tail_ge_0p30"],
            dedup_mode="candidate_key",
        )

        tail = summary[summary["rule"].eq("tail_prob_ge_0p30")].iloc[0]
        self.assertEqual(int(tail["flagged_count"]), 2)
        self.assertEqual(int(tail["flagged_failure_count"]), 1)
        self.assertAlmostEqual(float(tail["flagged_failure_pnl"]), -6.0)
        self.assertEqual(int(tail["flagged_win_count"]), 1)
        self.assertAlmostEqual(float(tail["flagged_win_pnl"]), 8.0)

    def test_overall_and_cases_include_positive_pred_failures(self) -> None:
        output = normalize_candidates(sample_candidates())
        overall = overall_summary(output)
        all_rows = overall[overall["scope"].eq("candidate_key") & overall["ranker_score_mode"].isna()]
        self.assertEqual(int(all_rows.iloc[0]["positive_pred_loss_count"]), 2)

        cases = top_failure_cases(output, dedup_mode="market_candidate_key", limit=1)
        self.assertEqual(len(cases), 1)
        self.assertAlmostEqual(float(cases.iloc[0]["actual_pnl_at_hv_chosen_horizon"]), -6.0)


if __name__ == "__main__":
    unittest.main()
