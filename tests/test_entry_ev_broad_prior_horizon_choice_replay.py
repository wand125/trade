from __future__ import annotations

import unittest

import pandas as pd

from scripts.experiments.entry_ev_broad_prior_horizon_choice_replay import (
    chronological_ranker_predictions,
    expand_horizon_examples,
    pivot_ranker_predictions,
)


def sample_rows() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "family": ["f", "f", "f"],
            "role": ["r", "r", "r"],
            "month": ["2026-01", "2026-01", "2026-02"],
            "decision_timestamp": [
                "2026-01-01T00:00:00Z",
                "2026-01-02T00:00:00Z",
                "2026-02-01T00:00:00Z",
            ],
            "side": ["long", "short", "long"],
            "needed_side": ["long", "short", "long"],
            "row_scope": ["available_candidates"] * 3,
            "selection_bucket": ["unit"] * 3,
            "combined_regime": ["range", "trend", "range"],
            "session_regime": ["asia", "london", "asia"],
            "near_miss_bucket": ["one_failed", "one_failed", "one_failed"],
            "side_score": [4.0, 5.0, 6.0],
            "side_fixed_60m_adjusted_pnl": [2.0, -1.0, 3.0],
            "side_fixed_720m_adjusted_pnl": [-5.0, 4.0, 8.0],
            "pred_fixed_60m_adjusted_pnl": [1.0, -0.5, 2.0],
            "pred_fixed_720m_adjusted_pnl": [-2.0, 3.0, 4.0],
        }
    )


class EntryEvBroadPriorHorizonChoiceReplayTest(unittest.TestCase):
    def test_chronological_ranker_predictions_use_only_prior_train_months(self) -> None:
        rows = sample_rows()
        train_examples = expand_horizon_examples(
            rows.iloc[:2],
            horizons=[60, 720],
            min_executable_pnl=0.0,
            tail_loss_threshold=-3.0,
            min_delta_vs_60=0.0,
        )
        eval_examples = expand_horizon_examples(
            rows,
            horizons=[60, 720],
            min_executable_pnl=0.0,
            tail_loss_threshold=-3.0,
            min_delta_vs_60=0.0,
        )

        _, folds = chronological_ranker_predictions(
            train_examples=train_examples,
            eval_examples=eval_examples,
            min_train_months=1,
            min_train_rows=4,
            max_train_rows=0,
            numeric_features=["side_score", "horizon_minutes", "horizon_pred_fixed_pnl"],
            categorical_features=["side", "horizon_bucket"],
            max_iter=5,
            learning_rate=0.1,
            l2_regularization=1.0,
            max_leaf_nodes=4,
            random_state=7,
        )

        jan = folds[folds["target_month"].eq("2026-01")]
        feb = folds[folds["target_month"].eq("2026-02")]
        self.assertTrue(jan["train_rows_full"].eq(0).all())
        self.assertTrue(feb["train_rows_full"].eq(4).all())
        self.assertTrue(feb["train_months"].eq(1).all())

    def test_pivot_ranker_predictions_maps_composite_score_to_horizon_columns(self) -> None:
        base_rows = sample_rows().iloc[[2]].copy()
        base_rows["pred_hv_60m_pnl"] = -999.0
        scored = expand_horizon_examples(
            base_rows,
            horizons=[60, 720],
            min_executable_pnl=0.0,
            tail_loss_threshold=-3.0,
            min_delta_vs_60=0.0,
        )
        scored["ranker_pred_executable_prob"] = [0.8, 0.7]
        scored["ranker_pred_pnl"] = [1.0, 4.0]
        scored["ranker_pred_tail_loss_prob"] = [0.1, 0.2]
        scored["ranker_pred_delta_vs_60"] = [0.0, 2.0]
        scored["ranker_pred_beats60_prob"] = [0.4, 0.9]
        scored["ranker_core_model_used"] = [True, True]
        scored["duration_prior_count"] = [10, 10]
        scored["duration_prior_months"] = [2, 2]
        scored["duration_prior_mean_pnl"] = [1.0, -1.0]
        scored["duration_prior_delta_vs_60_mean"] = [0.0, -2.0]
        scored["duration_prior_tail_loss_rate"] = [0.1, 0.3]
        scored["repair_duration_risk_score"] = [0.5, 3.5]

        output = pivot_ranker_predictions(
            base_rows,
            scored,
            horizons=[60, 720],
            score_mode="pnl_delta_tail",
            delta_weight=0.25,
            beats60_weight=0.5,
            tail_score_weight=2.0,
        )

        self.assertAlmostEqual(float(output.iloc[0]["pred_hv_60m_pnl"]), 1.0)
        self.assertAlmostEqual(float(output.iloc[0]["pred_hv_720m_pnl"]), 4.55)
        self.assertAlmostEqual(float(output.iloc[0]["ranker_hv_720m_pred_pnl"]), 4.0)
        self.assertTrue(bool(output.iloc[0]["pred_hv_720m_pnl_model_used"]))


if __name__ == "__main__":
    unittest.main()
