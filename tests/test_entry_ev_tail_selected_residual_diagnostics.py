from __future__ import annotations

import unittest

import pandas as pd

from scripts.experiments.entry_ev_contextual_penalty_near_selected_diagnostics import (
    add_selection_rank_columns,
    attach_selection_outcomes,
    normalize_replay_rows,
    parse_score_specs,
)
from scripts.experiments.entry_ev_tail_selected_residual_diagnostics import (
    add_tail_residual_columns,
    failure_cases,
    overall_summary,
    quota_group_summary,
    scoped_rule_summary,
    selection_outcome_summary,
)


def sample_candidates() -> pd.DataFrame:
    base = {
        "candidate_file": "candidates.csv",
        "row_scope": "available_candidates",
        "prob_threshold": 0.5,
        "ev_threshold": 0.0,
        "tail_prob_threshold": 0.3,
        "require_model_used": False,
        "ranker_score_mode": "pnl",
        "ranker_abstention_rule": "none",
        "positive_pnl_gate_rule": "none",
        "positive_pnl_penalty_label": "none",
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
    specs = [
        ("00", 10.0, 2.0, 5.0, 0.20),
        ("05", 9.0, 1.0, -4.0, 0.20),
        ("10", 8.0, 1.5, -6.0, 0.20),
        ("15", 7.0, 4.0, -10.0, 0.40),
        ("20", 1.0, 0.5, -8.0, 0.20),
    ]
    rows = []
    for minute, score, pred, actual, tail_prob in specs:
        row = dict(base)
        row.update(
            {
                "decision_timestamp": f"2026-01-01T00:{minute}:00Z",
                "entry_timestamp": f"2026-01-01T00:{minute}:00Z",
                "exit_timestamp": f"2026-01-01T01:{minute}:00Z",
                "repair_score": score,
                "hv_chosen_pred_pnl": pred,
                "hv_chosen_pred_tail_loss_prob": tail_prob,
                "hv_chosen_pred_harmful_overestimate_prob": 0.2,
                "actual_pnl_at_hv_chosen_horizon": actual,
                "adjusted_pnl": actual,
            }
        )
        rows.append(row)
    return pd.DataFrame(rows)


def ranked_candidates() -> pd.DataFrame:
    candidates = sample_candidates()
    additions = candidates.iloc[[0, 1]].copy()
    rejections = candidates.iloc[[2, 3, 4]].copy()
    rejections["reject_reason"] = ["quota_full", "tail_prob_ceiling", "quota_full"]
    attached = attach_selection_outcomes(
        normalize_replay_rows(candidates),
        additions,
        rejections,
    )
    ranked = add_selection_rank_columns(
        attached,
        quota_columns=["scenario_key", "role", "month", "side"],
        rank_specs=parse_score_specs("repair_score:desc,decision_timestamp:asc"),
        near_rank_window=1,
    )
    return add_tail_residual_columns(ranked, max_tail_prob=0.3)


class TailSelectedResidualDiagnosticsTest(unittest.TestCase):
    def test_overall_summary_separates_selected_near_and_blocked_rows(self) -> None:
        frame = ranked_candidates()
        summary = overall_summary(
            frame,
            group_columns=[
                "positive_pnl_penalty_label",
                "ranker_score_mode",
                "ranker_abstention_rule",
                "row_scope",
            ],
            focus_scopes=[
                "all_tail_pass_positive",
                "selected_addition",
                "near_selected_boundary",
                "within_quota",
            ],
        )
        overall = summary[summary["summary_scope"].eq("overall")].iloc[0]

        self.assertEqual(int(overall["all_tail_pass_positive_count"]), 4)
        self.assertAlmostEqual(float(overall["all_tail_pass_positive_actual_pnl_sum"]), -13.0)
        self.assertEqual(int(overall["all_tail_pass_positive_loss_count"]), 3)
        self.assertEqual(int(overall["selected_addition_count"]), 2)
        self.assertAlmostEqual(float(overall["selected_addition_actual_pnl_sum"]), 1.0)
        self.assertEqual(int(overall["selected_addition_loss_count"]), 1)
        self.assertEqual(int(overall["near_selected_boundary_count"]), 3)
        self.assertEqual(int(overall["within_quota_count"]), 2)

    def test_outcomes_groups_rules_and_cases_focus_on_tail_pass_failures(self) -> None:
        frame = ranked_candidates()

        outcomes = selection_outcome_summary(frame)
        by_outcome = outcomes.set_index("selection_outcome")
        self.assertEqual(int(by_outcome.loc["selected", "tail_pass_count"]), 2)
        self.assertEqual(int(by_outcome.loc["quota_full", "tail_pass_loss_count"]), 2)

        groups = quota_group_summary(
            frame,
            quota_columns=["scenario_key", "role", "month", "side"],
        )
        self.assertEqual(len(groups), 1)
        self.assertEqual(int(groups.iloc[0]["failure_count"]), 3)
        self.assertEqual(int(groups.iloc[0]["failure_selected_count"]), 1)
        self.assertEqual(int(groups.iloc[0]["failure_near_selected_count"]), 2)
        self.assertTrue(bool(groups.iloc[0]["best_failure_selected"]))

        rules = scoped_rule_summary(
            frame,
            rules=["pred_pnl_lt_2"],
            focus_scopes=["all_tail_pass_positive", "selected_addition"],
        )
        all_scope = rules[rules["focus_scope"].eq("all_tail_pass_positive")].iloc[0]
        self.assertEqual(int(all_scope["flagged_count"]), 3)
        self.assertEqual(int(all_scope["flagged_failure_count"]), 3)

        cases = failure_cases(frame, limit=2)
        self.assertEqual(len(cases), 2)
        self.assertTrue(bool(cases.iloc[0]["selected_addition"]))
        self.assertEqual(cases.iloc[0]["selection_outcome"], "selected")


if __name__ == "__main__":
    unittest.main()
