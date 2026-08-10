import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from trade_data.next_bar_registry import (
    _rank_roles,
    align_prediction_subset,
    apply_confidence_exclusion_guard,
    blend_confidence_frames,
    compare_confidence_reliability_frames,
    compare_fixed_candidate_frames,
    confidence_reliability_profile,
    confidence_reliability_subgroups,
    confidence_role,
    discover_candidate_specs,
    lane_metrics,
    read_prediction_sets,
)


class NextBarRegistryTests(unittest.TestCase):
    def test_prediction_subset_uses_exact_reference_order_and_target(self):
        predictions = pd.DataFrame(
            {
                "fold": ["test2020", "test2021", "test2022"],
                "timestamp": pd.date_range(
                    "2020-01-01", periods=3, freq="min", tz="UTC"
                ),
                "target_up": [0, 1, 0],
                "probability_up": [0.4, 0.6, 0.45],
            }
        )
        reference = predictions.iloc[[2, 0]][
            ["fold", "timestamp", "target_up"]
        ].copy()

        aligned = align_prediction_subset(predictions, reference)

        self.assertEqual(aligned["fold"].tolist(), ["test2022", "test2020"])
        self.assertEqual(aligned["probability_up"].tolist(), [0.45, 0.4])

        missing = reference.copy()
        missing.loc[missing.index[0], "target_up"] = 1
        with self.assertRaisesRegex(ValueError, "cover every reference"):
            align_prediction_subset(predictions, missing)

    def test_confidence_blend_preserves_base_direction_probabilities(self):
        base = pd.DataFrame(
            {
                "fold": ["test2020", "test2020"],
                "timestamp": pd.date_range(
                    "2020-01-01", periods=2, freq="min", tz="UTC"
                ),
                "target_up": [1, 0],
                "probability_up": [0.56, 0.48],
                "confidence": [0.56, 0.52],
            }
        )
        contributor = base.copy()
        contributor["probability_up"] = [0.60, 0.40]
        contributor["confidence"] = [0.60, 0.60]

        blended = blend_confidence_frames(base, contributor, 0.25)

        self.assertEqual(blended["probability_up"].tolist(), [0.56, 0.48])
        self.assertAlmostEqual(blended.loc[0, "confidence"], 0.57)
        self.assertAlmostEqual(blended.loc[1, "confidence"], 0.54)
        self.assertTrue(blended["confidence_contributor_weight"].eq(0.25).all())

        with self.assertRaisesRegex(ValueError, "between 0 and 1"):
            blend_confidence_frames(base, contributor, 1.1)

    def test_confidence_exclusion_guard_abstains_only_matching_groups(self):
        frame = pd.DataFrame(
            {
                "predicted_direction": ["up", "up", "down"],
                "volatility_regime": ["low", "high", "low"],
                "confidence": [0.56, 0.57, 0.58],
            }
        )

        guarded = apply_confidence_exclusion_guard(
            frame,
            [{"predicted_direction": "up", "volatility_regime": "low"}],
        )

        self.assertEqual(guarded["confidence"].tolist(), [0.5, 0.57, 0.58])
        self.assertEqual(
            guarded["confidence_guard_excluded"].tolist(), [True, False, False]
        )
        self.assertEqual(guarded["pre_guard_confidence"].tolist(), [0.56, 0.57, 0.58])
        self.assertEqual(frame["confidence"].tolist(), [0.56, 0.57, 0.58])

        with self.assertRaisesRegex(ValueError, "missing"):
            apply_confidence_exclusion_guard(frame, [{"missing": "value"}])

    def test_prediction_reader_uses_manifest_filename_fallback(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            frame = pd.DataFrame(
                {
                    "fold": ["test2020"],
                    "timestamp": [pd.Timestamp("2020-01-01", tz="UTC")],
                    "target_up": [1],
                    "probability_up": [0.55],
                    "confidence": [0.55],
                    "correct": [True],
                }
            )
            frame.to_parquet(directory / "custom_predictions.parquet", index=False)
            (directory / "manifest.json").write_text(
                json.dumps(
                    {
                        "timeframes": {
                            "M1": {"predictions": "custom_predictions.parquet"}
                        }
                    }
                ),
                encoding="utf-8",
            )

            loaded = read_prediction_sets([directory], 1)

            self.assertEqual(len(loaded), 1)
            self.assertAlmostEqual(loaded.loc[0, "probability_up"], 0.55)

    def test_fixed_reliability_profile_reports_calibration_and_monotonicity(self):
        frame = pd.DataFrame(
            {
                "confidence": [0.51, 0.52, 0.54, 0.56, 0.58, 0.62],
                "correct": [False, True, False, True, True, True],
            }
        )

        profile = confidence_reliability_profile(
            frame,
            edges=(0.5, 0.55, 0.6, 1.0),
            thresholds=(0.55, 0.6),
        )

        self.assertEqual(profile["overall"]["rows"], 6)
        self.assertEqual(profile["bands"][0]["rows"], 3)
        self.assertEqual(profile["cumulative_thresholds"][0]["rows"], 3)
        self.assertIsNotNone(profile["overall"]["brier_score"])
        self.assertIsNotNone(profile["overall"]["log_loss"])
        self.assertIsNotNone(profile["overall"]["expected_calibration_error"])
        self.assertTrue(profile["monotonicity"]["observed_accuracy_nondecreasing"])
        self.assertFalse(profile["cumulative_thresholds"][0]["edge_confirmed"])

    def test_reliability_profile_reports_below_chance_confidence(self):
        frame = pd.DataFrame(
            {
                "confidence": [0.48, 0.49, 0.52, 0.56],
                "correct": [False, True, True, True],
            }
        )

        profile = confidence_reliability_profile(
            frame,
            edges=(0.5, 0.55, 1.0),
            thresholds=(0.55,),
        )

        self.assertEqual(profile["overall"]["rows"], 4)
        self.assertEqual(profile["below_first_edge"]["rows"], 2)
        self.assertEqual(profile["below_first_edge"]["coverage"], 0.5)
        self.assertAlmostEqual(profile["below_first_edge"]["mean_confidence"], 0.485)

    def test_reliability_comparison_separates_development_and_confirmation(self):
        timestamps = pd.date_range("2020-01-01", periods=4, freq="15min", tz="UTC")
        first = pd.DataFrame(
            {
                "fold": ["test2020", "test2020", "test2024", "test2024"],
                "timestamp": timestamps,
                "target_up": [1, 0, 1, 0],
                "probability_up": [0.60, 0.40, 0.60, 0.40],
                "confidence": [0.60, 0.60, 0.60, 0.60],
                "correct": [True, True, True, True],
            }
        )
        second = first.copy()
        second["confidence"] = [0.55, 0.55, 0.55, 0.55]

        report = compare_confidence_reliability_frames(
            first,
            second,
            edges=(0.5, 0.575, 1.0),
            thresholds=(0.55,),
        )

        self.assertEqual(report["periods"]["development"]["first"]["overall"]["rows"], 2)
        self.assertEqual(report["periods"]["confirmation"]["second"]["bands"][0]["rows"], 2)
        self.assertEqual(report["periods"]["all"]["direction_agreement_rate"], 1.0)

    def test_reliability_subgroups_keep_fixed_periods_and_thresholds(self):
        timestamps = pd.date_range("2020-01-01", periods=6, freq="15min", tz="UTC")
        frame = pd.DataFrame(
            {
                "fold": ["test2020"] * 3 + ["test2024"] * 3,
                "timestamp": timestamps,
                "target_up": [1, 0, 1, 0, 1, 0],
                "probability_up": [0.56, 0.44, 0.52, 0.44, 0.56, 0.48],
                "confidence": [0.56, 0.56, 0.52, 0.56, 0.56, 0.52],
                "correct": [True, True, False, True, False, True],
                "predicted_direction": ["up", "down", "up", "down", "up", "down"],
                "volatility_regime": ["high", "high", "low", "high", "high", "low"],
            }
        )

        report = confidence_reliability_subgroups(
            frame,
            ("predicted_direction", "volatility_regime"),
            edges=(0.5, 0.55, 1.0),
            thresholds=(0.55,),
        )

        confirmation = report["periods"]["confirmation"]
        self.assertEqual(confirmation["rows"], 3)
        self.assertEqual(len(confirmation["groups"]), 3)
        high_down = next(
            row
            for row in confirmation["groups"]
            if row["group"]
            == {"predicted_direction": "down", "volatility_regime": "high"}
        )
        self.assertEqual(high_down["profile"]["cumulative_thresholds"][0]["rows"], 1)
        self.assertAlmostEqual(high_down["period_coverage"], 1 / 3)

        with self.assertRaisesRegex(ValueError, "missing"):
            confidence_reliability_subgroups(frame, ("missing_group",))

    def test_fixed_candidate_comparison_reports_periods_and_fold_wins(self):
        timestamps = pd.date_range("2020-01-01", periods=4, freq="15min", tz="UTC")
        first = pd.DataFrame(
            {
                "fold": ["test2020", "test2020", "test2024", "test2024"],
                "timestamp": timestamps,
                "target_up": [1, 0, 1, 0],
                "probability_up": [0.60, 0.40, 0.60, 0.40],
                "confidence": [0.60, 0.60, 0.60, 0.60],
                "correct": [True, True, True, True],
            }
        )
        second = first.copy()
        second["probability_up"] = [0.55, 0.55, 0.55, 0.55]
        second["confidence"] = [0.55, 0.55, 0.55, 0.55]
        second["correct"] = [True, False, True, False]

        report = compare_fixed_candidate_frames(
            first, second, 0.54, "first", "second"
        )

        self.assertEqual(report["periods"]["development"]["first"]["lane"]["rows"], 2)
        self.assertEqual(report["periods"]["confirmation"]["second"]["lane"]["accuracy"], 0.5)
        self.assertEqual(report["fold_wins"]["first"]["accuracy"], 2)
        self.assertEqual(report["fold_wins"]["first"]["selection_score"], 2)

        all_rows = compare_fixed_candidate_frames(
            first, second, 0.5, "first", "second"
        )
        self.assertEqual(
            all_rows["periods"]["all"]["first"]["lane"]["coverage"], 1.0
        )
        self.assertEqual(
            all_rows["periods"]["all"]["second"]["lane"]["coverage"], 1.0
        )

        unequal = compare_fixed_candidate_frames(
            first,
            second,
            0.5,
            "first",
            "second",
            second_threshold=0.75,
        )
        self.assertEqual(unequal["first_threshold"], 0.5)
        self.assertEqual(unequal["second_threshold"], 0.75)
        self.assertEqual(
            unequal["periods"]["all"]["first"]["lane"]["coverage"], 1.0
        )
        self.assertLess(
            unequal["periods"]["all"]["second"]["lane"]["coverage"], 1.0
        )

    def test_confidence_roles_have_stable_boundaries(self):
        self.assertEqual(confidence_role(0.515), "broad")
        self.assertEqual(confidence_role(0.52), "broad")
        self.assertEqual(confidence_role(0.525), "balanced")
        self.assertEqual(confidence_role(0.53), "selective")
        self.assertEqual(confidence_role(0.54), "selective")
        self.assertEqual(confidence_role(0.55), "precision")

    def test_lane_metrics_combine_coverage_and_wilson_accuracy(self):
        frame = pd.DataFrame(
            {
                "confidence": [0.60, 0.58, 0.57, 0.56, 0.51, 0.50],
                "correct": [True, True, True, True, False, False],
            }
        )

        metrics = lane_metrics(frame, 0.55)

        self.assertEqual(metrics["rows"], 4)
        self.assertAlmostEqual(metrics["coverage"], 4 / 6)
        self.assertEqual(metrics["accuracy"], 1.0)
        self.assertGreater(metrics["selection_score"], 0.0)

    def test_discovery_rejects_an_implicit_threshold(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config_dir = root / "config"
            config_dir.mkdir()
            prediction_dir = root / "predictions"
            prediction_dir.mkdir()
            config = {
                "status": "forward_candidate_test",
                "confidence_candidate": {"preserve_baseline_direction": True},
                "experiments": {
                    "direction_preserving_blend": "predictions",
                },
            }
            path = config_dir / "m15_test_confidence_candidate.json"
            path.write_text(json.dumps(config), encoding="utf-8")

            with self.assertRaisesRegex(
                ValueError, "explicit fixed_confidence_threshold"
            ):
                discover_candidate_specs(config_dir, root, 15)

    def test_discovery_accepts_composed_confidence_prediction_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config_dir = root / "config"
            config_dir.mkdir()
            for key in ("predictions", "final_confidence_blend"):
                prediction_dir = root / key
                prediction_dir.mkdir()
                config = {
                    "status": "forward_candidate_test",
                    "confidence_candidate": {
                        "fixed_confidence_threshold": 0.515
                    },
                    "experiments": {key: key},
                }
                (config_dir / f"m1_{key}_confidence.json").write_text(
                    json.dumps(config), encoding="utf-8"
                )

            specs = discover_candidate_specs(config_dir, root, 1)

            self.assertEqual(len(specs), 2)
            self.assertEqual(
                {spec.prediction_dir.name for spec in specs},
                {"predictions", "final_confidence_blend"},
            )

    def test_role_champion_uses_development_objective_and_keeps_pareto_challenger(self):
        def candidate(
            candidate_id: str, coverage: float, accuracy: float, score: float
        ) -> dict[str, object]:
            lane = {
                "coverage": coverage,
                "accuracy": accuracy,
                "selection_score": score,
            }
            return {
                "candidate_id": candidate_id,
                "role": "selective",
                "eligible": True,
                "periods": {
                    "development": {"candidate_lane": lane},
                    "confirmation": {"candidate_lane": lane},
                },
                "historical_gate": {"passed": True},
            }

        high_score = candidate("high_score", 0.50, 0.54, 0.021)
        high_accuracy = candidate("high_accuracy", 0.20, 0.56, 0.019)
        dominated = candidate("dominated", 0.10, 0.53, 0.005)

        roles = _rank_roles([high_score, high_accuracy, dominated])

        self.assertEqual(roles["selective"]["champion"], "high_score")
        self.assertEqual(
            roles["selective"]["development_accuracy_leader"], "high_accuracy"
        )
        self.assertEqual(roles["selective"]["challengers"], ["high_accuracy"])
        self.assertEqual(roles["selective"]["dominated"], ["dominated"])


if __name__ == "__main__":
    unittest.main()
