from __future__ import annotations

import unittest

import pandas as pd

from scripts.experiments.entry_ev_hold_extension_target_model import (
    add_hold_extension_targets,
    chronological_predictions,
    normalize_trades,
    threshold_summary,
)


def trade_frame() -> pd.DataFrame:
    rows = []
    for index, month in enumerate(["2026-01", "2026-02", "2026-03", "2026-04"]):
        rows.append(
            {
                "source": "s",
                "role": "r",
                "family": "f",
                "variant": "v",
                "candidate": "c",
                "month": month,
                "entry_decision_timestamp": f"{month}-01 00:00:00+00:00",
                "adjusted_pnl": -2.0 + index,
                "holding_minutes": 1.0,
                "actual_taken_fixed_60m_adjusted_pnl": 1.0 + index,
                "actual_taken_fixed_240m_adjusted_pnl": -4.0,
                "actual_taken_fixed_720m_adjusted_pnl": 0.0,
                "isolated_context": True,
                "is_loss": index < 2,
                "is_large_loss": index == 0,
                "isolated_large_loss": index == 0,
                "isolated_exit_capture_failure": index < 2,
                "isolated_large_loss_capture_failure": index == 0,
                "direction": "long",
                "combined_regime": "range",
                "session_regime": "asia",
                "prev_result_bucket": "first" if index == 0 else "prev_non_loss",
                "post_exit_gap_bucket": "first" if index == 0 else ">1440",
                "pred_taken_ev": 2.0,
                "pred_side_confidence_gap": 0.1,
            }
        )
    return pd.DataFrame(rows)


class EntryEvHoldExtensionTargetModelTest(unittest.TestCase):
    def test_add_hold_extension_targets_selects_best_horizon(self) -> None:
        frame = normalize_trades(trade_frame(), horizons=[60, 240, 720])
        targeted = add_hold_extension_targets(
            frame,
            horizons=[60, 240, 720],
            min_improvement=1.0,
        )

        self.assertEqual(targeted.loc[0, "target_delta_60m"], 3.0)
        self.assertEqual(targeted.loc[0, "target_best_horizon_minutes"], 60)
        self.assertEqual(targeted.loc[0, "target_best_delta"], 3.0)
        self.assertTrue(bool(targeted.loc[0, "target_extend_positive"]))

    def test_chronological_predictions_fallback_without_training_support(self) -> None:
        frame = add_hold_extension_targets(
            normalize_trades(trade_frame(), horizons=[60]),
            horizons=[60],
            min_improvement=1.0,
        )

        scored, folds = chronological_predictions(
            frame,
            horizons=[60],
            train_universe="isolated",
            min_train_months=99,
            min_train_rows=99,
            numeric_features=["pred_taken_ev"],
            categorical_features=["direction"],
            max_iter=5,
            learning_rate=0.1,
            l2_regularization=0.1,
            max_leaf_nodes=5,
            random_state=1,
        )

        self.assertFalse(bool(scored["pred_hold_extension_any_model_used"].any()))
        self.assertEqual(len(folds), 4)
        self.assertIn("pred_hold_extension_best_horizon_minutes", scored.columns)

    def test_threshold_summary_uses_predicted_horizon_actual_delta(self) -> None:
        frame = add_hold_extension_targets(
            normalize_trades(trade_frame(), horizons=[60]),
            horizons=[60],
            min_improvement=1.0,
        )
        frame["pred_hold_extension_delta_60m"] = [3.0, 2.0, 0.0, 0.0]
        frame["pred_hold_extension_best_delta"] = [3.0, 2.0, 0.0, 0.0]
        frame["pred_hold_extension_best_horizon_minutes"] = [60, 60, 0, 0]

        summary, monthly = threshold_summary(
            frame,
            horizons=[60],
            thresholds=[1.0],
            apply_universes=["isolated_loss"],
        )

        self.assertEqual(summary.loc[0, "flagged_trade_count"], 2)
        self.assertEqual(summary.loc[0, "flagged_actual_delta_sum"], 6.0)
        self.assertEqual(summary.loc[0, "total_pnl_if_replaced_no_replay"], 4.0)
        self.assertEqual(monthly["flagged_trade_count"].sum(), 2)


if __name__ == "__main__":
    unittest.main()
