from __future__ import annotations

import unittest

import pandas as pd

from scripts.experiments.entry_ev_downside_meta_block_policy_inputs import (
    CATEGORICAL_FEATURES,
    NUMERIC_FEATURES,
    attach_predictions_to_families,
    chronological_downside_predictions,
    threshold_summary,
)


def minimal_feature_rows(months: list[str]) -> pd.DataFrame:
    frame = pd.DataFrame({"month": months})
    for column in NUMERIC_FEATURES:
        frame[column] = 0.0
    for column in CATEGORICAL_FEATURES:
        frame[column] = "all"
    return frame


class EntryEvDownsideMetaBlockPolicyInputsTest(unittest.TestCase):
    def test_chronological_predictions_use_prior_months_only(self) -> None:
        train = minimal_feature_rows(["2026-01"])
        train["target_downside"] = [2.0]

        target = minimal_feature_rows(["2026-01", "2026-02"])
        scored, folds = chronological_downside_predictions(
            train,
            target,
            min_train_months=1,
            min_train_rows=1,
            max_train_rows=0,
            max_iter=5,
            learning_rate=0.04,
            max_leaf_nodes=3,
            min_samples_leaf=1,
            l2_regularization=0.0,
            random_seed=1,
            default_downside=0.0,
            max_downside_prediction=30.0,
        )

        self.assertEqual(scored.loc[0, "pred_downside_meta_expected_downside"], 0.0)
        self.assertEqual(scored.loc[1, "pred_downside_meta_expected_downside"], 2.0)
        self.assertEqual(
            folds.set_index("target_month").loc["2026-01", "train_rows"],
            0,
        )
        self.assertEqual(
            folds.set_index("target_month").loc["2026-02", "train_rows"],
            1,
        )

    def test_attach_predictions_to_families_writes_side_block_columns(self) -> None:
        family_frames = {"fam": pd.DataFrame({"decision_timestamp": [1, 2]})}
        scored = pd.DataFrame(
            {
                "family": ["fam", "fam", "fam", "fam"],
                "side": ["long", "long", "short", "short"],
                "_row_id": [0, 1, 0, 1],
                "pred_downside_meta_expected_downside": [0.5, 1.2, 1.1, 0.0],
                "pred_downside_meta_model_used": [True, True, False, False],
                "pred_downside_meta_train_rows": [10, 10, 0, 0],
                "pred_downside_meta_train_months": [2, 2, 0, 0],
            }
        )

        outputs = attach_predictions_to_families(
            family_frames,
            scored,
            thresholds=[1.0],
            output_prefix="pred_downside_meta",
        )

        enriched = outputs["fam"]
        self.assertEqual(
            enriched["pred_downside_meta_long_block_gte_1"].tolist(),
            [0, 1],
        )
        self.assertEqual(
            enriched["pred_downside_meta_short_block_gte_1"].tolist(),
            [1, 0],
        )
        self.assertEqual(
            enriched["pred_downside_meta_long_expected_downside"].tolist(),
            [0.5, 1.2],
        )

    def test_threshold_summary_rewards_flagged_losing_rows(self) -> None:
        frame = pd.DataFrame(
            {
                "adjusted_pnl": [-2.0, 3.0, -1.0],
                "pred_downside_meta_expected_downside": [2.0, 0.0, 0.5],
            }
        )

        summary = threshold_summary(frame, thresholds=[1.0])

        self.assertEqual(summary.loc[0, "flagged_trade_count"], 1)
        self.assertEqual(summary.loc[0, "flagged_pnl"], -2.0)
        self.assertEqual(summary.loc[0, "block_delta_if_removed"], 2.0)
        self.assertEqual(summary.loc[0, "flagged_loss_precision"], 1.0)


if __name__ == "__main__":
    unittest.main()
