from __future__ import annotations

import unittest

import pandas as pd

from scripts.experiments.entry_ev_horizon_reliability_abstention_diagnostics import (
    apply_veto_rule,
    normalize_choice_deltas,
    summarize_rule_outcomes,
)


def sample_choice_deltas() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "score_mode": [
                "pnl",
                "pnl_delta_tail_reliability_gated",
                "pnl_delta_tail_reliability_gated",
            ],
            "role": ["validation", "validation", "validation"],
            "month": ["2026-01", "2026-01", "2026-01"],
            "side": ["long", "long", "long"],
            "row_scope": [
                "available_candidates",
                "available_candidates",
                "available_candidates",
            ],
            "decision_timestamp": [
                "2026-01-01T00:00:00Z",
                "2026-01-01T00:05:00Z",
                "2026-01-01T00:10:00Z",
            ],
            "decision_key": ["baseline", "bad_switch", "good_switch"],
            "combined_regime": ["range", "range", "range"],
            "session_regime": ["asia", "asia", "asia"],
            "near_miss_bucket": ["one_failed", "one_failed", "one_failed"],
            "horizon_minutes": [60, 240, 240],
            "horizon_actual_pnl": [5.0, -3.0, 4.0],
            "baseline_horizon_minutes": [60, 60, 60],
            "baseline_actual_pnl": [5.0, 5.0, 1.0],
            "baseline_score": [5.0, 5.0, 1.0],
            "ranker_pred_pnl": [5.0, 4.0, 2.0],
            "ranker_pred_delta_vs_60": [0.0, 1.0, 1.0],
            "ranker_pred_beats60_prob": [0.0, 0.60, 0.60],
            "ranker_pred_tail_loss_prob": [0.0, 0.31, 0.10],
            "delta_reliability_positive_score": [0.0, 0.30, 0.30],
            "beats60_reliability_positive_score": [0.0, 0.30, 0.30],
            "tail_reliability_positive_score": [0.0, 0.30, 0.30],
            "chosen_score": [5.0, 4.0, 2.0],
            "actual_delta_vs_baseline": [0.0, -8.0, 3.0],
            "choice_changed_vs_baseline": [False, True, True],
            "choice_worse_than_baseline": [False, True, False],
            "choice_better_than_baseline": [False, False, True],
            "ranker_core_model_used": [True, True, True],
        }
    )


class EntryEvHorizonReliabilityAbstentionDiagnosticsTest(unittest.TestCase):
    def test_pred_pnl_below_baseline_rule_recovers_bad_switch_only(self) -> None:
        rows = normalize_choice_deltas(sample_choice_deltas())
        vetoed = apply_veto_rule(
            rows,
            rule_name="veto_chosen_pred_pnl_below_baseline",
            baseline_score_mode="pnl",
        )
        summary = summarize_rule_outcomes(vetoed)

        reliability = summary[
            summary["score_mode"].eq("pnl_delta_tail_reliability_gated")
        ].iloc[0]

        self.assertEqual(int(reliability["switch_count"]), 2)
        self.assertEqual(int(reliability["veto_count"]), 1)
        self.assertEqual(int(reliability["veto_recovers_loss_count"]), 1)
        self.assertEqual(int(reliability["veto_removes_gain_count"]), 0)
        self.assertAlmostEqual(float(reliability["original_delta_vs_baseline"]), -5.0)
        self.assertAlmostEqual(float(reliability["post_veto_delta_vs_baseline"]), 3.0)
        self.assertAlmostEqual(float(reliability["recovered_pnl_vs_original"]), 8.0)

    def test_veto_all_switches_recovers_loss_but_also_removes_gain(self) -> None:
        rows = normalize_choice_deltas(sample_choice_deltas())
        vetoed = apply_veto_rule(
            rows,
            rule_name="veto_all_switches",
            baseline_score_mode="pnl",
        )
        summary = summarize_rule_outcomes(vetoed)

        reliability = summary[
            summary["score_mode"].eq("pnl_delta_tail_reliability_gated")
        ].iloc[0]

        self.assertEqual(int(reliability["veto_count"]), 2)
        self.assertEqual(int(reliability["veto_recovers_loss_count"]), 1)
        self.assertEqual(int(reliability["veto_removes_gain_count"]), 1)
        self.assertAlmostEqual(float(reliability["original_delta_vs_baseline"]), -5.0)
        self.assertAlmostEqual(float(reliability["post_veto_delta_vs_baseline"]), 0.0)
        self.assertAlmostEqual(float(reliability["recovered_pnl_vs_original"]), 5.0)

    def test_unknown_rule_is_rejected(self) -> None:
        rows = normalize_choice_deltas(sample_choice_deltas())

        with self.assertRaisesRegex(ValueError, "unknown abstention rule"):
            apply_veto_rule(rows, rule_name="missing_rule", baseline_score_mode="pnl")


if __name__ == "__main__":
    unittest.main()
