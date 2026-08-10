import unittest

import pandas as pd

from trade_data.next_bar_router import build_chronological_role_route
from trade_data.next_bar_regime_router import (
    build_chronological_regime_route,
    build_fixed_regime_route,
)


def prediction_frame(correct_by_fold: dict[str, list[bool]], confidences: list[float]) -> pd.DataFrame:
    rows = []
    timestamp = pd.Timestamp("2020-01-01", tz="UTC")
    for fold, correctness in correct_by_fold.items():
        for index, correct in enumerate(correctness):
            confidence = confidences[index % len(confidences)]
            rows.append(
                {
                    "fold": fold,
                    "timestamp": timestamp,
                    "target_up": int(correct),
                    "probability_up": confidence,
                    "confidence": confidence,
                    "correct": correct,
                }
            )
            timestamp += pd.Timedelta(minutes=15)
    return pd.DataFrame(rows)


class NextBarRouterTests(unittest.TestCase):
    def test_role_router_uses_only_prior_folds_and_baseline_fallback(self):
        folds = {
            "test2020": [True] * 20 + [False] * 2,
            "test2021": [True] * 40 + [False] * 40,
            "test2022": [False, False, True, True],
        }
        baseline = prediction_frame(folds, [0.56, 0.54])
        candidate_a = baseline.copy()
        candidate_b = baseline.copy()
        candidate_a["confidence"] = (
            [0.56] * 20
            + [0.51] * 2
            + [0.51] * 40
            + [0.56] * 40
            + [0.56, 0.56, 0.51, 0.51]
        )
        candidate_b["confidence"] = (
            [0.51] * 20
            + [0.56] * 2
            + [0.56] * 40
            + [0.51] * 40
            + [0.51, 0.51, 0.56, 0.56]
        )

        report, routed = build_chronological_role_route(
            baseline,
            {"candidate_a": (candidate_a, 0.55), "candidate_b": (candidate_b, 0.55)},
            "precision",
            "candidate_a",
            0.55,
            ("test2020", "test2021"),
            ("test2022",),
        )

        self.assertEqual(report["folds"][0]["selected_candidate"], "baseline_fallback")
        self.assertFalse(report["folds"][0]["evaluation"])
        self.assertEqual(report["folds"][1]["calibration_folds"], ["test2020"])
        self.assertEqual(report["folds"][1]["selected_candidate"], "candidate_a")
        self.assertEqual(report["folds"][2]["calibration_folds"], ["test2020", "test2021"])
        self.assertEqual(report["folds"][2]["selected_candidate"], "candidate_b")
        self.assertEqual(
            routed.loc[routed["fold"].eq("test2020"), "router_evaluation"].unique().tolist(),
            [False],
        )

        changed = candidate_b.copy()
        changed.loc[changed["fold"].eq("test2022"), "confidence"] = 0.99
        changed_report, _ = build_chronological_role_route(
            baseline,
            {"candidate_a": (candidate_a, 0.55), "candidate_b": (changed, 0.55)},
            "precision",
            "candidate_a",
            0.55,
            ("test2020", "test2021"),
            ("test2022",),
        )
        self.assertEqual(
            changed_report["folds"][2]["selected_candidate"], "candidate_b"
        )

    def test_role_router_rejects_direction_changes(self):
        folds = {"test2020": [True, False], "test2021": [True, False]}
        baseline = prediction_frame(folds, [0.56])
        changed = baseline.copy()
        changed.loc[0, "correct"] = False

        with self.assertRaisesRegex(ValueError, "preserve baseline direction"):
            build_chronological_role_route(
                baseline,
                {"changed": (changed, 0.55)},
                "precision",
                "changed",
                0.55,
                ("test2020",),
                ("test2021",),
            )

    def test_fixed_regime_router_freezes_development_winners(self):
        baseline = regime_prediction_frame()
        candidate_a = baseline.copy()
        candidate_b = baseline.copy()
        candidate_a["probability_up"] = [0.6, 0.6, 0.6, 0.4, 0.4, 0.6]
        candidate_b["probability_up"] = [0.4, 0.4, 0.4, 0.6, 0.6, 0.4]

        report, routed = build_fixed_regime_route(
            baseline,
            {"candidate_a": candidate_a, "candidate_b": candidate_b},
            ("test2020",),
            regimes=("low", "normal", "high"),
        )

        self.assertEqual(
            {
                regime: values["selected_candidate"]
                for regime, values in report["selections"].items()
            },
            {"low": "candidate_a", "normal": "candidate_b", "high": "candidate_a"},
        )
        self.assertEqual(
            routed.loc[routed["fold"].eq("test2021"), "router_candidate_id"].tolist(),
            ["candidate_a", "candidate_b", "candidate_a"],
        )

        changed = candidate_b.copy()
        changed.loc[changed["fold"].eq("test2021"), "probability_up"] = [0.99, 0.99, 0.99]
        changed_report, _ = build_fixed_regime_route(
            baseline,
            {"candidate_a": candidate_a, "candidate_b": changed},
            ("test2020",),
            regimes=("low", "normal", "high"),
        )
        self.assertEqual(changed_report["selections"], report["selections"])

    def test_chronological_regime_router_uses_only_prior_folds(self):
        baseline = regime_prediction_frame()
        candidate_a = baseline.copy()
        candidate_b = baseline.copy()
        candidate_a["probability_up"] = [0.6, 0.6, 0.6, 0.4, 0.6, 0.4]
        candidate_b["probability_up"] = [0.4, 0.4, 0.4, 0.6, 0.4, 0.6]

        report, routed = build_chronological_regime_route(
            baseline,
            {"candidate_a": candidate_a, "candidate_b": candidate_b},
            "candidate_a",
            ("test2020",),
            regimes=("low", "normal", "high"),
        )

        first = report["folds"][:3]
        second = report["folds"][3:]
        self.assertTrue(all(not row["evaluation"] for row in first))
        self.assertTrue(all(row["calibration_folds"] == ["test2020"] for row in second))
        self.assertEqual(
            [row["selected_candidate"] for row in second],
            ["candidate_a", "candidate_b", "candidate_a"],
        )
        self.assertEqual(
            routed.loc[routed["fold"].eq("test2020"), "router_evaluation"].unique().tolist(),
            [False],
        )


def regime_prediction_frame() -> pd.DataFrame:
    rows = []
    timestamp = pd.Timestamp("2020-01-01", tz="UTC")
    for fold in ("test2020", "test2021"):
        for regime, target in zip(("low", "normal", "high"), (1, 0, 1)):
            rows.append(
                {
                    "fold": fold,
                    "timestamp": timestamp,
                    "target_up": target,
                    "probability_up": 0.55,
                    "confidence": 0.55,
                    "correct": target == 1,
                    "volatility_regime": regime,
                }
            )
            timestamp += pd.Timedelta(minutes=1)
    return pd.DataFrame(rows)


if __name__ == "__main__":
    unittest.main()
