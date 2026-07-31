from __future__ import annotations

import unittest

import pandas as pd

from scripts.experiments.entry_ev_horizon_reliability_diagnostics import (
    add_score_mode_columns,
    choice_deltas,
    choice_summary,
    filter_targets,
    horizon_head_summary,
    missing_target_summary,
    normalize_scored_examples,
    parse_targets,
)


def sample_scored_examples() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "family": ["f"] * 6,
            "role": ["r"] * 6,
            "month": ["2026-01"] * 6,
            "side": ["long"] * 6,
            "row_scope": ["available_candidates"] * 6,
            "combined_regime": ["range"] * 6,
            "session_regime": ["asia"] * 6,
            "near_miss_bucket": ["one_failed"] * 6,
            "horizon_bucket": ["60m", "240m", "720m", "60m", "240m", "720m"],
            "decision_timestamp": [
                "2026-01-01T00:00:00Z",
                "2026-01-01T00:00:00Z",
                "2026-01-01T00:00:00Z",
                "2026-01-01T00:05:00Z",
                "2026-01-01T00:05:00Z",
                "2026-01-01T00:05:00Z",
            ],
            "hv_chosen_horizon_minutes": [60, 240, 720, 60, 240, 720],
            "horizon_actual_pnl": [5.0, -3.0, 1.0, 2.0, 4.0, -1.0],
            "horizon_actual_delta_vs_60": [0.0, -8.0, -4.0, 0.0, 2.0, -3.0],
            "target_horizon_tail_loss": [False, False, False, False, False, False],
            "target_horizon_beats_60": [False, False, False, False, True, False],
            "ranker_pred_pnl": [5.0, 4.9, 1.0, 1.0, 2.0, 1.0],
            "ranker_pred_delta_vs_60": [0.0, 8.0, 0.0, 0.0, 2.0, 0.0],
            "ranker_pred_beats60_prob": [0.0, 1.0, 0.0, 0.0, 1.0, 0.0],
            "ranker_pred_tail_loss_prob": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            "delta_reliability_positive_score": [0.0, 1.0, 0.0, 0.0, 1.0, 0.0],
            "beats60_reliability_positive_score": [0.0, 1.0, 0.0, 0.0, 1.0, 0.0],
            "tail_reliability_positive_score": [0.0] * 6,
            "delta_reliability_score": [0.0, 1.0, 0.0, 0.0, 1.0, 0.0],
            "beats60_reliability_score": [0.0, 1.0, 0.0, 0.0, 1.0, 0.0],
            "tail_reliability_score": [0.0] * 6,
            "delta_reliability_count": [20] * 6,
            "beats60_reliability_count": [20] * 6,
            "tail_reliability_count": [20] * 6,
            "delta_reliability_used": [True] * 6,
            "beats60_reliability_used": [True] * 6,
            "tail_reliability_used": [True] * 6,
            "ranker_core_model_used": [True] * 6,
        }
    )


class EntryEvHorizonReliabilityDiagnosticsTest(unittest.TestCase):
    def test_choice_deltas_find_reliability_worsening_against_pnl(self) -> None:
        rows = normalize_scored_examples(sample_scored_examples())
        rows = add_score_mode_columns(
            rows,
            score_modes=["pnl", "pnl_delta_tail_reliability_gated"],
            delta_weight=0.25,
            beats60_weight=0.5,
            tail_score_weight=2.0,
            support_score_weight=2.0,
            harmful_score_weight=5.0,
            lower_bound_mae_weight=0.25,
            lower_bound_bias_weight=0.25,
            lower_bound_tail_miss_weight=5.0,
        )

        deltas = choice_deltas(
            rows,
            score_modes=["pnl", "pnl_delta_tail_reliability_gated"],
            baseline_score_mode="pnl",
        )
        summary = choice_summary(deltas)
        reliability = summary[
            summary["score_mode"].eq("pnl_delta_tail_reliability_gated")
        ].iloc[0]

        self.assertEqual(int(reliability["changed_count"]), 1)
        self.assertEqual(int(reliability["worse_count"]), 1)
        self.assertAlmostEqual(float(reliability["delta_vs_baseline_sum"]), -8.0)
        self.assertEqual(int(reliability["chosen_240m_count"]), 2)

    def test_horizon_summary_and_missing_targets(self) -> None:
        rows = normalize_scored_examples(sample_scored_examples())
        filtered = filter_targets(
            rows,
            targets=parse_targets("r:2026-01:long"),
            row_scopes=["available_candidates"],
        )
        summary = horizon_head_summary(filtered)
        missing = missing_target_summary(
            rows,
            targets=parse_targets("r:2026-01:long,missing:2026-02:short"),
            row_scopes=["available_candidates"],
        )

        h240 = summary[summary["horizon_minutes"].eq(240)].iloc[0]
        self.assertEqual(int(h240["row_count"]), 2)
        self.assertAlmostEqual(float(h240["actual_pnl_sum"]), 1.0)
        self.assertAlmostEqual(float(h240["delta_reliability_positive_score_mean"]), 1.0)
        absent = missing[missing["target_key"].eq("missing|2026-02|short")].iloc[0]
        self.assertFalse(bool(absent["has_rows"]))


if __name__ == "__main__":
    unittest.main()
