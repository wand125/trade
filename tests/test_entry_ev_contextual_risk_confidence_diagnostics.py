from __future__ import annotations

import unittest

import pandas as pd

from scripts.experiments.entry_ev_contextual_risk_confidence_diagnostics import (
    add_prior_context_stats,
    apply_confidence_thresholds,
    attach_prior_confidence,
    contextual_rule_summary,
    deduplicate_prior_rows,
    expand_rule_rows,
    monthly_context_rule_summary,
)
from scripts.experiments.entry_ev_over_gating_diagnostics import add_scenario_key
from scripts.experiments.entry_ev_positive_pnl_failure_diagnostics import normalize_candidates


CONTEXT_COLUMNS = [
    "hv_chosen_horizon_minutes",
    "side",
    "combined_regime",
    "session_regime",
    "near_miss_bucket",
]


def sample_candidates() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "candidate_file": ["c.csv"] * 4,
            "family": ["f"] * 4,
            "role": ["fresh"] * 4,
            "month": ["2026-01", "2026-01", "2026-02", "2026-02"],
            "side": ["short", "short", "short", "long"],
            "row_scope": ["available_candidates"] * 4,
            "decision_timestamp": [
                "2026-01-01T00:00:00Z",
                "2026-01-02T00:00:00Z",
                "2026-02-01T00:00:00Z",
                "2026-02-02T00:00:00Z",
            ],
            "ranker_score_mode": ["pnl"] * 4,
            "ranker_abstention_rule": ["none"] * 4,
            "positive_pnl_gate_rule": ["none"] * 4,
            "positive_pnl_penalty_label": ["none"] * 4,
            "combined_regime": ["up_normal_vol", "up_normal_vol", "up_normal_vol", "up_normal_vol"],
            "session_regime": ["asia", "asia", "asia", "asia"],
            "near_miss_bucket": ["one_failed"] * 4,
            "prob_threshold": [0.5] * 4,
            "ev_threshold": [0.0] * 4,
            "tail_prob_threshold": [0.5] * 4,
            "require_model_used": [True] * 4,
            "hv_chosen_horizon_minutes": [720.0, 720.0, 720.0, 720.0],
            "hv_chosen_pred_pnl": [2.0, 3.0, 4.0, 5.0],
            "hv_chosen_pred_tail_loss_prob": [0.35, 0.38, 0.36, 0.36],
            "hv_chosen_pred_harmful_overestimate_prob": [0.1, 0.1, 0.1, 0.1],
            "hv_chosen_pred_executable_prob": [0.7] * 4,
            "hv_chosen_pred_model_used": [True] * 4,
            "actual_pnl_at_hv_chosen_horizon": [-6.0, -7.0, -4.0, 8.0],
            "target_pnl_hurdle": [0.0] * 4,
            "extra_side_needed": [1.0] * 4,
            "repair_score": [1.0] * 4,
        }
    )


def sample_focus() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "row_scope": ["available_candidates"],
            "prob_threshold": [0.5],
            "ev_threshold": [0.0],
            "tail_prob_threshold": [0.5],
            "require_model_used": [True],
            "ranker_score_mode": ["pnl"],
            "ranker_abstention_rule": ["none"],
            "positive_pnl_gate_rule": ["none"],
            "positive_pnl_penalty_label": ["none"],
            "combined_total_pnl": [10.0],
            "added_count": [1],
            "added_pnl": [-4.0],
            "selector_pass": [False],
            "blockers": ["month_pnl_below_floor"],
        }
    )


class EntryEvContextualRiskConfidenceDiagnosticsTest(unittest.TestCase):
    def test_prior_stats_use_only_previous_months_in_same_context(self) -> None:
        candidates = normalize_candidates(sample_candidates())
        expanded = expand_rule_rows(
            candidates,
            rules=["tail_prob_ge_0p30"],
            context_columns=CONTEXT_COLUMNS,
        )
        monthly = monthly_context_rule_summary(expanded, CONTEXT_COLUMNS)
        prior = add_prior_context_stats(monthly)

        feb_short = prior[
            prior["month"].eq("2026-02")
            & prior["side"].eq("short")
            & prior["rule"].eq("tail_prob_ge_0p30")
        ].iloc[0]
        feb_long = prior[
            prior["month"].eq("2026-02")
            & prior["side"].eq("long")
            & prior["rule"].eq("tail_prob_ge_0p30")
        ].iloc[0]
        self.assertEqual(int(feb_short["prior_flagged_count"]), 2)
        self.assertAlmostEqual(float(feb_short["prior_flagged_actual_pnl_sum"]), -13.0)
        self.assertEqual(int(feb_long["prior_flagged_count"]), 0)

    def test_prior_dedup_uses_unique_market_candidates(self) -> None:
        duplicated = pd.concat(
            [
                sample_candidates(),
                sample_candidates().iloc[[0]].assign(ranker_score_mode="pnl_delta_tail"),
            ],
            ignore_index=True,
        )
        candidates = normalize_candidates(duplicated)
        expanded = expand_rule_rows(
            candidates,
            rules=["tail_prob_ge_0p30"],
            context_columns=CONTEXT_COLUMNS,
        )
        expanded["selected_addition"] = expanded["ranker_score_mode"].eq("pnl_delta_tail")

        deduped = deduplicate_prior_rows(expanded, "market_candidate_key")
        self.assertEqual(len(deduped), 4)
        duplicated_key = expanded.loc[
            expanded["ranker_score_mode"].eq("pnl_delta_tail"),
            "market_candidate_key",
        ].iloc[0]
        kept = deduped[deduped["market_candidate_key"].eq(duplicated_key)].iloc[0]
        self.assertTrue(bool(kept["selected_addition"]))

        monthly = monthly_context_rule_summary(deduped, CONTEXT_COLUMNS)
        prior = add_prior_context_stats(monthly)
        feb_short = prior[
            prior["month"].eq("2026-02")
            & prior["side"].eq("short")
            & prior["rule"].eq("tail_prob_ge_0p30")
        ].iloc[0]
        self.assertEqual(int(feb_short["prior_flagged_count"]), 2)
        self.assertAlmostEqual(float(feb_short["prior_flagged_actual_pnl_sum"]), -13.0)

    def test_contextual_summary_flags_only_prior_confident_context(self) -> None:
        candidates = normalize_candidates(sample_candidates())
        focus = add_scenario_key(sample_focus())
        expanded = expand_rule_rows(
            candidates,
            rules=["tail_prob_ge_0p30"],
            context_columns=CONTEXT_COLUMNS,
        )
        monthly = monthly_context_rule_summary(expanded, CONTEXT_COLUMNS)
        prior = apply_confidence_thresholds(
            add_prior_context_stats(monthly),
            min_prior_flagged=2,
            min_prior_gate_delta=5.0,
            min_prior_loss_precision=1.0,
            max_prior_winner_damage_ratio=0.0,
            max_prior_selected_win_count=0,
        )
        expanded = attach_prior_confidence(expanded, prior)
        summary = contextual_rule_summary(expanded, focus)

        row = summary.iloc[0]
        self.assertEqual(int(row["context_risk_flag_count"]), 1)
        self.assertEqual(int(row["flagged_loss_count"]), 1)
        self.assertAlmostEqual(float(row["flagged_loss_pnl"]), -4.0)
        self.assertEqual(int(row["flagged_win_count"]), 0)


if __name__ == "__main__":
    unittest.main()
