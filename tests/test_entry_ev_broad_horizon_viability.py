from __future__ import annotations

import unittest

import pandas as pd

from scripts.experiments.entry_ev_broad_horizon_viability import (
    add_candidate_flags,
    build_side_rows_from_predictions,
    chronological_broad_horizon_predictions,
    filter_broad_candidates,
)
from scripts.experiments.entry_ev_near_miss_horizon_viability import add_horizon_targets
from scripts.experiments.entry_ev_near_miss_exit_target_diagnostics import (
    add_fixed_horizon_targets,
)


class EntryEvBroadHorizonViabilityTest(unittest.TestCase):
    def test_build_side_rows_preserves_actual_and_predicted_horizons(self) -> None:
        predictions = pd.DataFrame(
            {
                "decision_timestamp": [
                    "2026-01-01T00:00:00Z",
                    "2026-01-01T00:01:00Z",
                ],
                "dataset_month": ["2026-01", "2026-01"],
                "combined_regime": ["range", "trend"],
                "session_regime": ["asia", "london"],
                "long_score": [10.0, 1.0],
                "short_score": [0.0, 9.0],
                "long_holding": [120.0, 120.0],
                "short_holding": [120.0, 120.0],
                "pred_long_entry_local_rank": [0.9, 0.1],
                "pred_short_entry_local_rank": [0.2, 0.8],
                "long_best_adjusted_pnl": [5.0, -1.0],
                "short_best_adjusted_pnl": [-2.0, 4.0],
                "long_best_holding_minutes": [60.0, 60.0],
                "short_best_holding_minutes": [60.0, 60.0],
                "long_fixed_60m_adjusted_pnl": [3.0, -2.0],
                "short_fixed_60m_adjusted_pnl": [-3.0, 2.0],
                "pred_long_fixed_60m_adjusted_pnl": [2.5, -1.5],
                "pred_short_fixed_60m_adjusted_pnl": [-2.5, 1.5],
            }
        )

        rows = build_side_rows_from_predictions(
            predictions,
            family="unit",
            role="unit_role",
            horizons=[60],
            long_column="long_score",
            short_column="short_score",
            long_holding_column="long_holding",
            short_holding_column="short_holding",
            side_penalty_rules=[],
            min_valid_predicted_hold_minutes=30.0,
            max_predicted_hold_minutes=720.0,
        )

        self.assertEqual(len(rows), 4)
        first_long = rows[(rows["side"].eq("long")) & (rows["side_score"].eq(10.0))].iloc[0]
        self.assertEqual(first_long["side_fixed_60m_adjusted_pnl"], 3.0)
        self.assertEqual(first_long["pred_fixed_60m_adjusted_pnl"], 2.5)
        self.assertTrue(first_long["holding_ok"])

    def test_filter_can_keep_broad_and_one_failed_rows(self) -> None:
        rows = pd.DataFrame(
            {
                "holding_ok": [True, True],
                "side_score": [1.0, -1.0],
                "score_pct": [0.95, 0.1],
                "side_margin_pct": [0.95, 0.1],
                "entry_rank_pct": [0.95, 0.1],
                "one_failed_strict_stage": [False, True],
                "family": ["f", "f"],
                "month": ["2026-01", "2026-01"],
                "decision_timestamp": pd.to_datetime(
                    ["2026-01-01T00:00:00Z", "2026-01-01T00:01:00Z"],
                    utc=True,
                ),
                "side": ["long", "short"],
            }
        )

        filtered = filter_broad_candidates(
            rows,
            min_score=0.0,
            min_score_pct=0.9,
            min_side_margin_pct=0.9,
            min_entry_rank_pct=0.9,
            include_one_failed=True,
        )

        self.assertEqual(set(filtered["side"]), {"long", "short"})

    def test_chronological_broad_predictions_use_only_prior_train_months(self) -> None:
        train = pd.DataFrame(
            {
                "month": ["2026-01", "2026-01", "2026-01"],
                "decision_timestamp": pd.to_datetime(
                    [
                        "2026-01-01T00:00:00Z",
                        "2026-01-01T00:01:00Z",
                        "2026-01-01T00:02:00Z",
                    ],
                    utc=True,
                ),
                "side": ["long", "short", "long"],
                "side_score": [1.0, 2.0, 3.0],
                "side_best_adjusted_pnl": [2.0, -2.0, 3.0],
                "side_fixed_60m_adjusted_pnl": [2.0, -2.0, 3.0],
                "target_fixed_best_adjusted_pnl": [2.0, -2.0, 3.0],
            }
        )
        eval_rows = pd.DataFrame(
            {
                "month": ["2026-01", "2026-02"],
                "decision_timestamp": pd.to_datetime(
                    ["2026-01-02T00:00:00Z", "2026-02-01T00:00:00Z"],
                    utc=True,
                ),
                "side": ["long", "short"],
                "side_score": [4.0, 5.0],
                "side_best_adjusted_pnl": [1.0, -1.0],
                "side_fixed_60m_adjusted_pnl": [1.0, -1.0],
                "target_fixed_best_adjusted_pnl": [1.0, -1.0],
            }
        )
        train = add_fixed_horizon_targets(train, horizons=[60], min_executable_pnl=0.0)
        train = add_horizon_targets(
            train,
            horizons=[60],
            min_executable_pnl=0.0,
            tail_loss_threshold=-1.5,
        )
        eval_rows = add_fixed_horizon_targets(
            eval_rows,
            horizons=[60],
            min_executable_pnl=0.0,
        )
        eval_rows = add_horizon_targets(
            eval_rows,
            horizons=[60],
            min_executable_pnl=0.0,
            tail_loss_threshold=-1.5,
        )

        _, folds = chronological_broad_horizon_predictions(
            train_rows=train,
            eval_rows=eval_rows,
            horizons=[60],
            min_train_months=1,
            min_train_rows=3,
            max_train_rows=0,
            numeric_features=["side_score"],
            categorical_features=["side"],
            max_iter=5,
            learning_rate=0.1,
            l2_regularization=1.0,
            max_leaf_nodes=4,
            random_state=3,
        )

        jan = folds[folds["target_month"].eq("2026-01")]
        feb = folds[folds["target_month"].eq("2026-02")]
        self.assertTrue(jan["train_rows_full"].eq(0).all())
        self.assertTrue(feb["train_rows_full"].eq(3).all())
        self.assertTrue(feb["train_months"].eq(1).all())


if __name__ == "__main__":
    unittest.main()
