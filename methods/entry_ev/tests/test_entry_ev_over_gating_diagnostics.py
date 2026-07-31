from __future__ import annotations

import unittest

import pandas as pd

from scripts.experiments.entry_ev_over_gating_diagnostics import (
    add_scenario_key,
    attach_selected_additions,
    scenario_rule_summary,
    select_focus_scenarios,
    selected_over_gating_cases,
)
from scripts.experiments.entry_ev_positive_pnl_failure_diagnostics import normalize_candidates


def sample_summary() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "row_scope": ["available_candidates", "available_candidates"],
            "prob_threshold": [0.5, 0.6],
            "ev_threshold": [0.0, 0.0],
            "tail_prob_threshold": [0.5, 0.5],
            "require_model_used": [True, True],
            "ranker_score_mode": ["pnl", "pnl"],
            "ranker_abstention_rule": ["none", "none"],
            "positive_pnl_gate_rule": ["none", "none"],
            "positive_pnl_penalty_label": ["none", "none"],
            "combined_total_pnl": [100.0, 96.0],
            "added_pnl": [2.0, 1.0],
            "added_count": [1, 1],
            "selector_pass": [False, False],
            "blockers": ["month_pnl_below_floor", "role_trades_low"],
        }
    )


def sample_candidates() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "candidate_file": ["c.csv", "c.csv", "c.csv"],
            "family": ["f", "f", "f"],
            "role": ["fresh", "fresh", "fresh"],
            "month": ["2026-01", "2026-01", "2026-01"],
            "side": ["long", "long", "long"],
            "row_scope": ["available_candidates"] * 3,
            "decision_timestamp": [
                "2026-01-01T00:00:00Z",
                "2026-01-01T00:05:00Z",
                "2026-01-01T00:10:00Z",
            ],
            "ranker_score_mode": ["pnl", "pnl", "pnl"],
            "ranker_abstention_rule": ["none", "none", "none"],
            "positive_pnl_gate_rule": ["none", "none", "none"],
            "positive_pnl_penalty_label": ["none", "none", "none"],
            "combined_regime": ["range", "range", "range"],
            "session_regime": ["asia", "asia", "asia"],
            "near_miss_bucket": ["one_failed", "one_failed", "one_failed"],
            "prob_threshold": [0.5, 0.5, 0.5],
            "ev_threshold": [0.0, 0.0, 0.0],
            "tail_prob_threshold": [0.5, 0.5, 0.5],
            "require_model_used": [True, True, True],
            "hv_chosen_horizon_minutes": [720.0, 720.0, 60.0],
            "hv_chosen_pred_pnl": [2.0, 3.0, 1.0],
            "hv_chosen_pred_tail_loss_prob": [0.35, 0.32, 0.05],
            "hv_chosen_pred_harmful_overestimate_prob": [0.4, 0.2, 0.1],
            "hv_chosen_pred_executable_prob": [0.7, 0.8, 0.9],
            "hv_chosen_pred_model_used": [True, True, True],
            "actual_pnl_at_hv_chosen_horizon": [-6.0, 8.0, 4.0],
            "target_pnl_hurdle": [0.0, 0.0, 0.0],
            "extra_side_needed": [1.0, 1.0, 1.0],
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
            "pred_hv_60m_pnl_model_used": [False, False, True],
            "pred_hv_60m_tail_model_used": [False, False, True],
        }
    )


class EntryEvOverGatingDiagnosticsTest(unittest.TestCase):
    def test_focus_scenarios_keeps_top_and_near_best(self) -> None:
        focus = select_focus_scenarios(
            sample_summary(),
            top_n=1,
            near_best_margin=5.0,
            best_per_columns=["ranker_score_mode"],
        )

        self.assertEqual(len(focus), 2)
        self.assertEqual(float(focus.iloc[0]["combined_total_pnl"]), 100.0)

    def test_scenario_rule_summary_flags_selected_winner_damage(self) -> None:
        focus = select_focus_scenarios(
            sample_summary(),
            top_n=1,
            near_best_margin=0.0,
            best_per_columns=[],
        )
        candidates = normalize_candidates(sample_candidates())
        additions = normalize_candidates(sample_candidates().iloc[[1]].copy())
        candidates = attach_selected_additions(candidates, additions)
        summary = scenario_rule_summary(
            candidates,
            add_scenario_key(focus),
            rules=["tail_prob_ge_0p30"],
        )

        row = summary.iloc[0]
        self.assertEqual(int(row["flagged_loss_count"]), 1)
        self.assertEqual(int(row["flagged_win_count"]), 1)
        self.assertAlmostEqual(float(row["flagged_loss_pnl"]), -6.0)
        self.assertAlmostEqual(float(row["flagged_win_pnl"]), 8.0)
        self.assertEqual(int(row["selected_flagged_win_count"]), 1)
        self.assertTrue(bool(row["over_gating_selected_winner"]))
        self.assertAlmostEqual(float(row["pointwise_gate_delta"]), -2.0)

    def test_selected_over_gating_cases_returns_flagged_addition(self) -> None:
        focus = add_scenario_key(
            select_focus_scenarios(
                sample_summary(),
                top_n=1,
                near_best_margin=0.0,
                best_per_columns=[],
            )
        )
        additions = add_scenario_key(normalize_candidates(sample_candidates().iloc[[1]].copy()))
        cases = selected_over_gating_cases(additions, focus, rules=["tail_prob_ge_0p30"])

        self.assertEqual(len(cases), 1)
        self.assertEqual(cases.iloc[0]["rule"], "tail_prob_ge_0p30")
        self.assertTrue(bool(cases.iloc[0]["selected_over_gating_winner"]))
        self.assertAlmostEqual(float(cases.iloc[0]["actual_pnl_at_hv_chosen_horizon"]), 8.0)


if __name__ == "__main__":
    unittest.main()
