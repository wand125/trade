import unittest
import json
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

from trade_data.next_bar_ensemble import (
    assert_latest_artifact_parity,
    blend_latest_prediction_frames,
    blend_prediction_frames,
    blend_probability_values,
)
from trade_data.next_bar_disagreement import combine_disagreement_predictions
from trade_data.next_bar_online_ensemble import combine_online_experts
from trade_data.next_bar_stacking import (
    ChronologicalStackingConfig,
    build_stacking_frame,
    chronological_stack_predictions,
)
from trade_data.next_bar_pairwise_gate import (
    PairwiseCorrectnessGateConfig,
    build_pairwise_gate_frame,
    chronological_pairwise_gate_predictions,
)


def prediction_frame(probabilities: list[float]) -> pd.DataFrame:
    rows = len(probabilities)
    timestamp = pd.date_range("2025-01-01", periods=rows, freq="15min", tz="UTC")
    targets = [1 if index % 2 == 0 else 0 for index in range(rows)]
    return pd.DataFrame(
        {
            "timestamp": timestamp,
            "decision_timestamp": timestamp + pd.Timedelta(minutes=15),
            "target_timestamp": timestamp + pd.Timedelta(minutes=30),
            "target_up": targets,
            "probability_up": probabilities,
            "predicted_up": targets,
            "predicted_direction": ["up" if target else "down" for target in targets],
            "confidence": [0.6] * rows,
            "correct": [True] * rows,
            "fold": ["test"] * rows,
            "volatility_regime": ["normal"] * rows,
        }
    )


class NextBarEnsembleTests(unittest.TestCase):

    @staticmethod
    def pairwise_source(probabilities: list[float], candidate: list[float]) -> pd.DataFrame:
        frame = prediction_frame(probabilities)
        frame["baseline_probability_up"] = [0.51 if value >= 0.5 else 0.49 for value in probabilities]
        frame["candidate_probability_up"] = candidate
        frame["volatility_20"] = np.linspace(0.001, 0.002, len(frame))
        frame["body_ratio"] = np.linspace(-0.5, 0.5, len(frame))
        frame["next_bar_body"] = np.linspace(-1.0, 1.0, len(frame))
        frame["predicted_up"] = frame["probability_up"].ge(0.5).astype("int8")
        frame["correct"] = frame["predicted_up"].eq(frame["target_up"])
        return frame

    def test_pairwise_gate_uses_only_prior_oos_disagreements(self):
        path = self.pairwise_source(
            [0.60, 0.40, 0.60, 0.40, 0.60, 0.40],
            [0.65, 0.35, 0.65, 0.35, 0.65, 0.35],
        )
        shift = self.pairwise_source(
            [0.40, 0.60, 0.40, 0.60, 0.40, 0.60],
            [0.35, 0.65, 0.35, 0.65, 0.35, 0.65],
        )
        shift["baseline_probability_up"] = path["baseline_probability_up"]
        folds = ["test2020", "test2020", "test2021", "test2021", "test2022", "test2022"]
        path["fold"] = folds
        shift["fold"] = folds
        frame = build_pairwise_gate_frame(path, shift)

        first_result, first_reports, _ = chronological_pairwise_gate_predictions(
            frame, PairwiseCorrectnessGateConfig()
        )
        altered = frame.copy()
        altered.loc[altered["fold"].eq("test2022"), "target_up"] = 1 - altered.loc[
            altered["fold"].eq("test2022"), "target_up"
        ]
        altered["path_correct"] = altered["path_predicted_up"].eq(
            altered["target_up"].astype("int8")
        )
        second_result, _, _ = chronological_pairwise_gate_predictions(
            altered, PairwiseCorrectnessGateConfig()
        )

        first_fold = first_result.loc[first_result["fold"].eq("test2020")]
        np.testing.assert_allclose(
            first_fold["probability_up"], first_fold["path_probability_up"]
        )
        self.assertEqual(first_reports[0]["train_folds"], [])
        self.assertEqual(first_reports[1]["train_folds"], ["test2020"])
        self.assertEqual(first_reports[2]["train_folds"], ["test2020", "test2021"])
        final_mask = first_result["fold"].eq("test2022")
        np.testing.assert_allclose(
            first_result.loc[final_mask, "gate_probability_path_correct"],
            second_result.loc[final_mask, "gate_probability_path_correct"],
        )

    def test_pairwise_gate_rejects_misaligned_targets(self):
        path = self.pairwise_source([0.60, 0.40], [0.65, 0.35])
        shift = self.pairwise_source([0.40, 0.60], [0.35, 0.65])
        shift["baseline_probability_up"] = path["baseline_probability_up"]
        shift.loc[0, "target_up"] = 1 - shift.loc[0, "target_up"]

        with self.assertRaisesRegex(ValueError, "target_up"):
            build_pairwise_gate_frame(path, shift)

    def test_oos_and_runtime_share_identical_probability_blend(self):
        baseline = prediction_frame([0.51, 0.49])
        candidate = prediction_frame([0.10, 0.90])
        oos = blend_prediction_frames(
            baseline, candidate, 0.25, preserve_baseline_direction=True
        )

        direct = blend_probability_values(
            baseline["probability_up"],
            candidate["probability_up"],
            0.25,
            preserve_baseline_direction=True,
        )

        np.testing.assert_array_equal(oos["probability_up"].to_numpy(), direct)

    def test_oos_blend_can_reuse_an_ensemble_as_an_immediate_source(self):
        baseline = prediction_frame([0.60, 0.40])
        first_candidate = prediction_frame([0.80, 0.20])
        second_candidate = prediction_frame([0.40, 0.60])
        first_blend = blend_prediction_frames(
            baseline, first_candidate, 0.25, preserve_baseline_direction=True
        )

        nested = blend_prediction_frames(
            first_blend, second_candidate, 0.50, preserve_baseline_direction=True
        )

        expected_first = 0.75 * baseline["probability_up"] + 0.25 * first_candidate[
            "probability_up"
        ]
        expected_nested = 0.50 * expected_first + 0.50 * second_candidate[
            "probability_up"
        ]
        np.testing.assert_allclose(nested["probability_up"], expected_nested)
        np.testing.assert_allclose(nested["baseline_probability_up"], expected_first)
        np.testing.assert_allclose(
            nested["candidate_probability_up"], second_candidate["probability_up"]
        )

    def test_latest_blend_requires_identical_keys_and_preserves_direction(self):
        timestamp = pd.Timestamp("2026-01-01", tz="UTC")
        baseline = pd.DataFrame(
            {
                "timeframe": ["M5"],
                "timeframe_minutes": [5],
                "bar_start": [timestamp],
                "decision_timestamp": [timestamp + pd.Timedelta(minutes=5)],
                "probability_up": [0.51],
                "volatility_regime": ["normal"],
            }
        )
        candidate = baseline.copy()
        candidate["probability_up"] = 0.10

        blended = blend_latest_prediction_frames(
            baseline,
            candidate,
            0.25,
            preserve_baseline_direction=True,
        )

        self.assertEqual(blended.loc[0, "predicted_direction"], "up")
        self.assertLess(blended.loc[0, "model_confidence"], 0.51)
        self.assertFalse(blended.loc[0, "odds_valid"])
        self.assertFalse(blended.loc[0, "odds_runtime_authorized"])
        candidate.loc[0, "decision_timestamp"] += pd.Timedelta(minutes=5)
        with self.assertRaisesRegex(ValueError, "identical prediction keys"):
            blend_latest_prediction_frames(baseline, candidate, 0.25)

    def test_latest_artifact_parity_rejects_different_boundaries(self):
        config = {
            "flat_tolerance": 0.0,
            "max_train_rows": 100,
            "random_seed": 42,
            "max_iter": 5,
            "learning_rate": 0.05,
            "max_leaf_nodes": 7,
            "min_samples_leaf": 5,
            "l2_regularization": 1.0,
            "confidence_model": "class_probability",
            "probability_calibration": "platt",
            "train_weighting": "uniform",
            "train_target_filter": "all",
            "model_type": "hgb",
            "train_window_days": 0,
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            baseline = root / "baseline"
            candidate = root / "candidate"
            baseline.mkdir()
            candidate.mkdir()
            (baseline / "metrics.json").write_text(
                json.dumps({"split_boundaries": {"train_end": "A"}, "config": config}),
                encoding="utf-8",
            )
            (candidate / "metrics.json").write_text(
                json.dumps({"split_boundaries": {"train_end": "B"}, "config": config}),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "split boundaries"):
                assert_latest_artifact_parity(baseline, candidate)

    def test_latest_shadow_suppresses_valid_odds_until_explicitly_authorized(self):
        timestamp = pd.Timestamp("2026-01-01", tz="UTC")
        baseline = pd.DataFrame(
            {
                "timeframe": ["M5"],
                "timeframe_minutes": [5],
                "bar_start": [timestamp],
                "decision_timestamp": [timestamp + pd.Timedelta(minutes=5)],
                "probability_up": [0.54],
                "volatility_regime": ["normal"],
            }
        )
        candidate = baseline.copy()
        cell = {
            "support_count": 1000,
            "correct_count": 550,
            "confidence": 0.55,
            "confidence_lower": 0.52,
            "confidence_upper": 0.58,
        }
        calibrator = {
            "M5": {
                "confidence_bin_edges": [],
                "config": {"min_support": 10},
                "global": cell,
                "cells": {
                    "side_regime_bin": {"up|normal|0": cell},
                    "side_bin": {},
                    "bin": {},
                },
                "selected_source": "model_confidence",
                "calibration_valid": True,
            }
        }

        shadow = blend_latest_prediction_frames(
            baseline, candidate, 0.25, odds_calibration=calibrator
        )
        authorized = blend_latest_prediction_frames(
            baseline,
            candidate,
            0.25,
            odds_calibration=calibrator,
            odds_runtime_authorized=True,
        )

        self.assertTrue(shadow.loc[0, "odds_calibration_gate_passed"])
        self.assertFalse(shadow.loc[0, "odds_valid"])
        self.assertFalse(shadow.loc[0, "strict_prediction_eligible"])
        self.assertTrue(authorized.loc[0, "odds_valid"])
        self.assertTrue(authorized.loc[0, "strict_prediction_eligible"])


    def test_chronological_stack_only_trains_on_prior_oos_folds(self):
        baseline = prediction_frame([0.60, 0.40, 0.55, 0.45])
        baseline["fold"] = ["test2020", "test2020", "test2021", "test2021"]
        expert = prediction_frame([0.70, 0.30, 0.65, 0.35])
        expert["fold"] = baseline["fold"]
        frame, features = build_stacking_frame(baseline, {"expert": expert})

        result, reports, _ = chronological_stack_predictions(
            frame,
            features,
            ChronologicalStackingConfig(stack_weight=0.25),
        )

        first = result.loc[result["fold"].eq("test2020")]
        np.testing.assert_allclose(
            first["stack_probability_up"], first["baseline_probability_up"]
        )
        self.assertEqual(reports[0]["train_folds"], [])
        self.assertEqual(reports[1]["train_folds"], ["test2020"])
        self.assertEqual(reports[1]["mode"], "prior_oos_logistic")

    def test_chronological_stack_rejects_misaligned_expert_targets(self):
        baseline = prediction_frame([0.60, 0.40])
        expert = prediction_frame([0.70, 0.30])
        expert.loc[0, "target_up"] = 0

        with self.assertRaisesRegex(ValueError, "target_up"):
            build_stacking_frame(baseline, {"expert": expert})

    def test_online_experts_only_learn_from_targets_known_at_decision_time(self):
        baseline = prediction_frame([0.80, 0.80])
        candidate = prediction_frame([0.20, 0.20])

        result = combine_online_experts(baseline, [candidate], history_rows=10)

        self.assertAlmostEqual(result.loc[0, "online_weight_0"], 0.5)
        self.assertAlmostEqual(result.loc[0, "probability_up"], 0.5)
        self.assertGreater(result.loc[1, "online_weight_0"], 0.75)
        self.assertGreater(result.loc[1, "probability_up"], 0.65)
        self.assertEqual(result["online_history_rows"].tolist(), [0, 1])

    def test_online_experts_do_not_use_a_target_before_its_timestamp(self):
        baseline = prediction_frame([0.80, 0.80])
        candidate = prediction_frame([0.20, 0.20])
        baseline.loc[0, "target_timestamp"] += pd.Timedelta(minutes=15)
        candidate.loc[0, "target_timestamp"] += pd.Timedelta(minutes=15)

        result = combine_online_experts(baseline, [candidate], history_rows=10)

        self.assertAlmostEqual(result.loc[1, "online_weight_0"], 0.5)
        self.assertAlmostEqual(result.loc[1, "probability_up"], 0.5)
        self.assertEqual(result["online_history_rows"].tolist(), [0, 0])

    def test_online_experts_reject_a_target_known_at_its_own_decision(self):
        baseline = prediction_frame([0.80, 0.80])
        candidate = prediction_frame([0.20, 0.20])
        baseline.loc[0, "target_timestamp"] = baseline.loc[0, "decision_timestamp"]
        candidate.loc[0, "target_timestamp"] = candidate.loc[0, "decision_timestamp"]

        with self.assertRaisesRegex(ValueError, "after its decision"):
            combine_online_experts(baseline, [candidate], history_rows=10)

    def test_online_experts_rolling_window_drops_old_losses(self):
        baseline = prediction_frame([0.80, 0.80, 0.80])
        candidate = prediction_frame([0.20, 0.20, 0.20])

        result = combine_online_experts(baseline, [candidate], history_rows=1)

        self.assertGreater(result.loc[1, "online_weight_0"], 0.75)
        self.assertLess(result.loc[2, "online_weight_0"], 0.25)
        self.assertEqual(result["online_history_rows"].tolist(), [0, 1, 1])

    def test_disagreement_penalty_preserves_direction_and_reduces_confidence(self):
        baseline = prediction_frame([0.60, 0.40])
        agreeing = prediction_frame([0.58, 0.42])
        disagreeing = prediction_frame([0.45, 0.55])

        agreement = combine_disagreement_predictions(
            baseline, [agreeing], uncertainty_penalty=1.0
        )
        disagreement = combine_disagreement_predictions(
            baseline, [disagreeing], uncertainty_penalty=1.0
        )

        self.assertEqual(agreement["predicted_up"].tolist(), [1, 0])
        self.assertEqual(disagreement["predicted_up"].tolist(), [1, 0])
        self.assertTrue(
            (disagreement["confidence"] < agreement["confidence"]).all()
        )
        self.assertTrue((disagreement["confidence"] >= 0.5).all())

    def test_disagreement_unrestricted_mode_uses_equal_probability_mean(self):
        baseline = prediction_frame([0.60, 0.40])
        first = prediction_frame([0.50, 0.50])
        second = prediction_frame([0.70, 0.30])
        combined = combine_disagreement_predictions(
            baseline,
            [first, second],
            uncertainty_penalty=1.0,
            preserve_baseline_direction=False,
        )
        np.testing.assert_allclose(combined["probability_up"], [0.60, 0.40])
        self.assertTrue((combined["ensemble_model_count"] == 3).all())

    def test_zero_penalty_uses_mean_edge_but_never_flips_baseline_direction(self):
        baseline = prediction_frame([0.60, 0.40])
        agreeing = prediction_frame([0.55, 0.45])
        opposing = prediction_frame([0.10, 0.90])

        agreement = combine_disagreement_predictions(
            baseline,
            [agreeing],
            uncertainty_penalty=0.0,
            preserve_baseline_direction=True,
        )
        opposition = combine_disagreement_predictions(
            baseline,
            [opposing],
            uncertainty_penalty=0.0,
            preserve_baseline_direction=True,
        )

        np.testing.assert_allclose(agreement["probability_up"], [0.575, 0.425])
        self.assertEqual(opposition["predicted_up"].tolist(), [1, 0])
        self.assertTrue((opposition["confidence"] < 0.500001).all())
        self.assertTrue((opposition["aligned_edge_mean"] < 0).all())

    def test_disagreement_mean_is_candidate_order_invariant_and_rejects_nan(self):
        baseline = prediction_frame([0.60, 0.40])
        first = prediction_frame([0.55, 0.45])
        second = prediction_frame([0.70, 0.30])

        forward = combine_disagreement_predictions(
            baseline, [first, second], uncertainty_penalty=0.0
        )
        reverse = combine_disagreement_predictions(
            baseline, [second, first], uncertainty_penalty=0.0
        )
        np.testing.assert_allclose(
            forward["probability_up"], reverse["probability_up"]
        )

        invalid = first.copy()
        invalid.loc[0, "probability_up"] = np.nan
        with self.assertRaisesRegex(ValueError, "finite and within"):
            combine_disagreement_predictions(
                baseline, [invalid], uncertainty_penalty=0.0
            )

    def test_blends_probabilities_and_recomputes_prediction_fields(self):
        baseline = prediction_frame([0.60, 0.40])
        candidate = prediction_frame([0.40, 0.60])

        result = blend_prediction_frames(baseline, candidate, 0.25)

        self.assertAlmostEqual(result.loc[0, "probability_up"], 0.55)
        self.assertAlmostEqual(result.loc[1, "probability_up"], 0.45)
        np.testing.assert_allclose(
            result["probability_down"], 1 - result["probability_up"]
        )
        np.testing.assert_allclose(result["class_confidence"], result["confidence"])
        self.assertEqual(result["predicted_direction"].tolist(), ["up", "down"])
        self.assertEqual(result["correct"].tolist(), [True, True])

    def test_rejects_misaligned_targets(self):
        baseline = prediction_frame([0.60, 0.40])
        candidate = prediction_frame([0.40, 0.60])
        candidate.loc[0, "target_up"] = 0

        with self.assertRaisesRegex(ValueError, "target_up"):
            blend_prediction_frames(baseline, candidate, 0.25)

    def test_direction_preserving_blend_changes_confidence_not_baseline_side(self):
        baseline = prediction_frame([0.51, 0.49])
        candidate = prediction_frame([0.10, 0.90])

        result = blend_prediction_frames(
            baseline,
            candidate,
            0.75,
            preserve_baseline_direction=True,
        )

        self.assertEqual(result["predicted_direction"].tolist(), ["up", "down"])
        self.assertGreater(result.loc[0, "probability_up"], 0.5)
        self.assertLess(result.loc[1, "probability_up"], 0.5)
        self.assertLess(result.loc[0, "confidence"], 0.500001)
        self.assertLess(result.loc[1, "confidence"], 0.500001)
        self.assertTrue(result["ensemble_preserve_baseline_direction"].all())


if __name__ == "__main__":
    unittest.main()
