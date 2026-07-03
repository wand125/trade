from __future__ import annotations

import unittest

import pandas as pd

from scripts.experiments.entry_ev_broad_prior_horizon_choice_replay import (
    DEFAULT_HORIZON_CATEGORICAL_FEATURES,
    DEFAULT_HORIZON_NUMERIC_FEATURES,
    add_residual_prior_columns,
    add_head_reliability_columns,
    apply_positive_pnl_gate,
    apply_switch_abstention,
    chronological_ranker_predictions,
    expand_horizon_examples,
    pivot_ranker_predictions,
    positive_pnl_gate_mask,
    score_predictions,
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
        scored["ranker_pred_harmful_overestimate_prob"] = [0.2, 0.3]
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
            support_score_weight=2.0,
            harmful_score_weight=5.0,
            lower_bound_mae_weight=0.25,
            lower_bound_bias_weight=0.25,
            lower_bound_tail_miss_weight=5.0,
        )

        self.assertAlmostEqual(float(output.iloc[0]["pred_hv_60m_pnl"]), 1.0)
        self.assertAlmostEqual(float(output.iloc[0]["pred_hv_720m_pnl"]), 4.55)
        self.assertAlmostEqual(float(output.iloc[0]["ranker_hv_720m_pred_pnl"]), 4.0)
        self.assertTrue(bool(output.iloc[0]["pred_hv_720m_pnl_model_used"]))

    def test_residual_prior_columns_use_only_prior_months(self) -> None:
        rows = sample_rows()
        rows.loc[0, "pred_fixed_720m_adjusted_pnl"] = 1.0
        train_examples = expand_horizon_examples(
            rows,
            horizons=[60, 720],
            min_executable_pnl=0.0,
            tail_loss_threshold=-3.0,
            min_delta_vs_60=0.0,
        )
        eval_examples = expand_horizon_examples(
            rows.iloc[[2]],
            horizons=[60, 720],
            min_executable_pnl=0.0,
            tail_loss_threshold=-3.0,
            min_delta_vs_60=0.0,
        )

        output = add_residual_prior_columns(
            eval_examples,
            train_examples,
            context_specs=[["horizon_bucket", "side"], []],
            min_prior_rows=1,
            min_prior_months=1,
            shrinkage_count=0.0,
            tail_loss_threshold=-3.0,
            min_executable_pnl=0.0,
        )

        row_720 = output[output["hv_chosen_horizon_minutes"].eq(720.0)].iloc[0]
        self.assertEqual(int(row_720["residual_prior_count"]), 1)
        self.assertEqual(int(row_720["residual_prior_months"]), 1)
        self.assertAlmostEqual(float(row_720["residual_prior_bias"]), 6.0)
        self.assertAlmostEqual(float(row_720["residual_prior_mae"]), 6.0)
        self.assertAlmostEqual(float(row_720["residual_prior_tail_miss_rate"]), 1.0)

    def test_lower_bound_score_subtracts_residual_uncertainty(self) -> None:
        frame = pd.DataFrame(
            {
                "ranker_pred_pnl": [10.0],
                "ranker_pred_delta_vs_60": [4.0],
                "ranker_pred_beats60_prob": [0.5],
                "ranker_pred_tail_loss_prob": [0.2],
                "ranker_pred_harmful_overestimate_prob": [0.0],
                "residual_prior_mae": [3.0],
                "residual_prior_bias": [2.0],
                "residual_prior_tail_miss_rate": [0.4],
            }
        )

        score = score_predictions(
            frame,
            score_mode="pnl_delta_tail_lower",
            delta_weight=0.25,
            beats60_weight=0.5,
            tail_score_weight=2.0,
            support_score_weight=2.0,
            harmful_score_weight=5.0,
            lower_bound_mae_weight=0.5,
            lower_bound_bias_weight=0.25,
            lower_bound_tail_miss_weight=5.0,
        )

        self.assertAlmostEqual(float(score.iloc[0]), 6.85)

    def test_support_harmful_score_relaxes_penalty_for_support_success_proxy(self) -> None:
        frame = pd.DataFrame(
            {
                "side": ["long", "short"],
                "needed_side": ["long", "long"],
                "extra_side_needed": [1.0, 1.0],
                "ranker_pred_pnl": [4.0, 4.0],
                "ranker_pred_delta_vs_60": [0.0, 0.0],
                "ranker_pred_beats60_prob": [0.0, 0.0],
                "ranker_pred_executable_prob": [0.8, 0.8],
                "ranker_pred_tail_loss_prob": [0.1, 0.1],
                "ranker_pred_harmful_overestimate_prob": [0.5, 0.5],
            }
        )

        score = score_predictions(
            frame,
            score_mode="pnl_support_harmful_guard",
            delta_weight=0.25,
            beats60_weight=0.5,
            tail_score_weight=2.0,
            support_score_weight=2.0,
            harmful_score_weight=5.0,
            lower_bound_mae_weight=0.25,
            lower_bound_bias_weight=0.25,
            lower_bound_tail_miss_weight=5.0,
        )

        self.assertGreater(float(score.iloc[0]), float(score.iloc[1]))

    def test_tail_support_gated_score_uses_train_support_before_penalty(self) -> None:
        frame = pd.DataFrame(
            {
                "ranker_pred_pnl": [4.0, 4.0],
                "ranker_pred_delta_vs_60": [0.0, 0.0],
                "ranker_pred_beats60_prob": [0.0, 0.0],
                "ranker_pred_tail_loss_prob": [0.8, 0.8],
                "ranker_pred_tail_loss_prob_model_used": [True, True],
                "ranker_pred_tail_loss_prob_train_months": [1, 3],
                "ranker_pred_tail_loss_prob_train_rows": [100, 300],
            }
        )

        score = score_predictions(
            frame,
            score_mode="pnl_delta_tail_support_gated",
            delta_weight=0.25,
            beats60_weight=0.5,
            tail_score_weight=2.0,
            support_score_weight=2.0,
            harmful_score_weight=5.0,
            lower_bound_mae_weight=0.25,
            lower_bound_bias_weight=0.25,
            lower_bound_tail_miss_weight=5.0,
            tail_penalty_min_train_months=2,
            tail_penalty_min_train_rows=200,
        )

        self.assertAlmostEqual(float(score.iloc[0]), 4.0)
        self.assertAlmostEqual(float(score.iloc[1]), 2.4)

    def test_head_reliability_columns_use_only_prior_months(self) -> None:
        scored = pd.DataFrame(
            {
                "month": ["2026-01", "2026-01", "2026-02"],
                "hv_chosen_horizon_minutes": [720.0, 720.0, 720.0],
                "horizon_bucket": ["720m", "720m", "720m"],
                "row_scope": ["available_candidates"] * 3,
                "ranker_pred_delta_vs_60": [0.1, 0.9, 0.8],
                "horizon_actual_delta_vs_60": [0.0, 1.0, 0.0],
                "ranker_pred_beats60_prob": [0.1, 0.9, 0.8],
                "target_horizon_beats_60": [False, True, False],
                "ranker_pred_tail_loss_prob": [0.1, 0.9, 0.8],
                "target_horizon_tail_loss": [False, True, False],
            }
        )

        output = add_head_reliability_columns(
            scored,
            context_specs=[["horizon_bucket"], []],
            min_prior_rows=2,
            min_prior_months=1,
            shrinkage_count=0.0,
        )

        jan = output[output["month"].eq("2026-01")].iloc[0]
        feb = output[output["month"].eq("2026-02")].iloc[0]
        self.assertFalse(bool(jan["tail_reliability_used"]))
        self.assertEqual(int(feb["tail_reliability_count"]), 2)
        self.assertEqual(int(feb["tail_reliability_months"]), 1)
        self.assertAlmostEqual(float(feb["tail_reliability_positive_score"]), 1.0)

        scored_frame = pd.DataFrame(
            {
                "ranker_pred_pnl": [4.0],
                "ranker_pred_delta_vs_60": [0.0],
                "ranker_pred_beats60_prob": [0.0],
                "ranker_pred_tail_loss_prob": [0.8],
                "tail_reliability_positive_score": [
                    float(feb["tail_reliability_positive_score"])
                ],
            }
        )
        score = score_predictions(
            scored_frame,
            score_mode="pnl_tail_reliability_gated",
            delta_weight=0.25,
            beats60_weight=0.5,
            tail_score_weight=2.0,
            support_score_weight=2.0,
            harmful_score_weight=5.0,
            lower_bound_mae_weight=0.25,
            lower_bound_bias_weight=0.25,
            lower_bound_tail_miss_weight=5.0,
        )
        self.assertAlmostEqual(float(score.iloc[0]), 2.4)

    def test_pred_pnl_lt0_switch_veto_reverts_group_to_baseline_score(self) -> None:
        scored = pd.DataFrame(
            {
                "family": ["f", "f", "f", "f"],
                "role": ["r", "r", "r", "r"],
                "month": ["2026-01", "2026-01", "2026-01", "2026-01"],
                "decision_timestamp": [
                    "2026-01-01T00:00:00Z",
                    "2026-01-01T00:00:00Z",
                    "2026-01-01T00:05:00Z",
                    "2026-01-01T00:05:00Z",
                ],
                "side": ["long", "long", "long", "long"],
                "row_scope": ["available_candidates"] * 4,
                "selection_bucket": ["unit"] * 4,
                "needed_side": ["long"] * 4,
                "extra_side_needed": [1.0] * 4,
                "hv_chosen_horizon_minutes": [60.0, 720.0, 60.0, 720.0],
                "ranker_pred_pnl": [5.0, -1.0, 1.0, 2.0],
                "ranker_pred_delta_vs_60": [0.0, 40.0, 0.0, 4.0],
                "ranker_pred_beats60_prob": [0.0, 0.0, 0.0, 0.0],
                "ranker_pred_tail_loss_prob": [0.0, 0.0, 0.0, 0.0],
                "ranker_pred_harmful_overestimate_prob": [0.0, 0.0, 0.0, 0.0],
            }
        )

        output = apply_switch_abstention(
            scored,
            score_mode="pnl_delta",
            abstention_rule="pred_pnl_lt0_switch_veto",
            baseline_score_mode="pnl",
            delta_weight=0.25,
            beats60_weight=0.5,
            tail_score_weight=2.0,
            support_score_weight=2.0,
            harmful_score_weight=5.0,
            lower_bound_mae_weight=0.25,
            lower_bound_bias_weight=0.25,
            lower_bound_tail_miss_weight=5.0,
        )

        first = output[output["decision_timestamp"].eq("2026-01-01T00:00:00Z")]
        second = output[output["decision_timestamp"].eq("2026-01-01T00:05:00Z")]
        first_choice = first.loc[first["ranker_choice_score"].idxmax()]
        second_choice = second.loc[second["ranker_choice_score"].idxmax()]

        self.assertTrue(bool(first["ranker_abstention_veto"].all()))
        self.assertEqual(float(first_choice["hv_chosen_horizon_minutes"]), 60.0)
        self.assertAlmostEqual(float(first.iloc[1]["ranker_choice_score_raw"]), 9.0)
        self.assertAlmostEqual(float(first.iloc[1]["ranker_choice_score"]), -1.0)
        self.assertFalse(bool(second["ranker_abstention_veto"].any()))
        self.assertEqual(float(second_choice["hv_chosen_horizon_minutes"]), 720.0)

    def test_residual_prior_columns_are_score_only_by_default(self) -> None:
        self.assertNotIn("residual_prior_mae", DEFAULT_HORIZON_NUMERIC_FEATURES)
        self.assertNotIn("residual_prior_tail_miss_rate", DEFAULT_HORIZON_NUMERIC_FEATURES)
        self.assertNotIn("residual_prior_context_spec", DEFAULT_HORIZON_CATEGORICAL_FEATURES)

    def test_harmful_overestimate_target_uses_fixed_prediction_error(self) -> None:
        rows = sample_rows().iloc[[0]].copy()
        rows["side_fixed_60m_adjusted_pnl"] = [2.0]
        rows["side_fixed_720m_adjusted_pnl"] = [-5.0]
        rows["pred_fixed_720m_adjusted_pnl"] = [3.0]

        output = expand_horizon_examples(
            rows,
            horizons=[720],
            min_executable_pnl=0.0,
            tail_loss_threshold=-3.0,
            min_delta_vs_60=0.0,
            harmful_overestimate_threshold=2.0,
            harmful_underperform_60_threshold=2.0,
        )

        self.assertTrue(bool(output.iloc[0]["target_horizon_harmful_overestimate"]))

    def test_positive_pnl_gate_uses_chosen_horizon_risk_columns(self) -> None:
        choices = pd.DataFrame(
            {
                "id": ["bias_tail", "tail_prob", "negative_pred"],
                "hv_chosen_horizon_minutes": [720.0, 720.0, 720.0],
                "hv_chosen_pred_pnl": [2.0, 2.0, -1.0],
                "hv_chosen_pred_tail_loss_prob": [0.20, 0.35, 0.90],
                "ranker_hv_720m_residual_bias": [1.0, -1.0, 5.0],
                "ranker_hv_720m_residual_tail_miss_rate": [0.20, 0.20, 0.90],
            }
        )

        gated_bias, vetoed_bias = apply_positive_pnl_gate(
            choices,
            "positive_bias_and_tail_miss_ge_0p10",
        )
        gated_tail, vetoed_tail = apply_positive_pnl_gate(choices, "tail_prob_ge_0p30")

        self.assertEqual(vetoed_bias["id"].tolist(), ["bias_tail"])
        self.assertEqual(gated_bias["id"].tolist(), ["tail_prob", "negative_pred"])
        self.assertEqual(vetoed_tail["id"].tolist(), ["tail_prob"])
        self.assertEqual(gated_tail["id"].tolist(), ["bias_tail", "negative_pred"])
        self.assertTrue(bool(vetoed_bias.iloc[0]["positive_pnl_gate_veto"]))
        self.assertAlmostEqual(
            float(vetoed_bias.iloc[0]["positive_pnl_gate_residual_tail_miss_rate"]),
            0.20,
        )

    def test_positive_pnl_gate_rejects_unknown_rule(self) -> None:
        choices = pd.DataFrame({"hv_chosen_pred_pnl": [1.0]})

        with self.assertRaises(ValueError):
            positive_pnl_gate_mask(choices, "unknown_rule")


if __name__ == "__main__":
    unittest.main()
