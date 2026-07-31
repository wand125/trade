from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

import pandas as pd

from trade_data.backtest import ModelPolicyConfig


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "experiments"
    / "side_context_interaction_guard_apply.py"
)
SPEC = importlib.util.spec_from_file_location(
    "side_context_interaction_guard_apply",
    SCRIPT_PATH,
)
side_context_interaction_guard_apply = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = side_context_interaction_guard_apply
SPEC.loader.exec_module(side_context_interaction_guard_apply)


class SideContextInteractionGuardApplyTests(unittest.TestCase):
    def test_interaction_context_tracks_only_matching_side_rule(self):
        timestamps = pd.to_datetime(
            [
                "2025-01-01T00:00:00Z",
                "2025-01-01T00:01:00Z",
                "2025-01-01T00:02:00Z",
            ]
        )
        df = pd.DataFrame({"timestamp": timestamps})
        predictions = pd.DataFrame(
            {
                "decision_timestamp": timestamps,
                "combined_regime": ["up_low_vol", "up_low_vol", "down_low_vol"],
                "dataset_month": ["2025-01", "2025-01", "2025-01"],
            }
        )
        config = ModelPolicyConfig(
            predictions=Path("predictions.parquet"),
            side_ev_penalty_rules=("short:combined_regime=up_low_vol:5",),
        )
        signal = pd.Series([-1, 1, -1], index=df.index)

        any_context, any_active = side_context_interaction_guard_apply.interaction_entry_context(
            df,
            predictions,
            config,
            signal,
            context_columns=("dataset_month",),
            match_mode="any_rule",
        )
        selected_context, selected_active = (
            side_context_interaction_guard_apply.interaction_entry_context(
                df,
                predictions,
                config,
                signal,
                context_columns=("dataset_month",),
                match_mode="selected_side_rule",
            )
        )

        self.assertEqual(any_active.tolist(), [True, True, False])
        self.assertEqual(selected_active.tolist(), [True, False, False])
        self.assertEqual(any_context.iloc[0], "guarded|dataset_month=2025-01")
        self.assertEqual(any_context.iloc[1], "guarded|dataset_month=2025-01")
        self.assertTrue(any_context.iloc[2].startswith("inactive|"))
        self.assertTrue(selected_context.iloc[1].startswith("inactive|"))
        self.assertNotEqual(any_context.iloc[2], selected_context.iloc[1])

    def test_signal_short_raw_gap_mode_uses_final_short_signal_and_raw_gap(self):
        timestamps = pd.to_datetime(
            [
                "2025-01-01T00:00:00Z",
                "2025-01-01T00:01:00Z",
                "2025-01-01T00:02:00Z",
            ]
        )
        df = pd.DataFrame({"timestamp": timestamps})
        predictions = pd.DataFrame(
            {
                "decision_timestamp": timestamps,
                "dataset_month": ["2025-01", "2025-01", "2025-01"],
                "pred_long_best_adjusted_pnl": [10.0, 10.0, 10.0],
                "pred_short_best_adjusted_pnl": [17.0, 13.0, 25.0],
            }
        )
        config = ModelPolicyConfig(predictions=Path("predictions.parquet"))
        signal = pd.Series([-1, -1, 1], index=df.index)

        context, active = side_context_interaction_guard_apply.interaction_entry_context(
            df,
            predictions,
            config,
            signal,
            context_columns=("dataset_month",),
            match_mode="signal_short_raw_gap",
            short_gap_threshold=5.0,
        )

        self.assertEqual(active.tolist(), [True, False, False])
        self.assertEqual(context.iloc[0], "guarded|dataset_month=2025-01")
        self.assertTrue(context.iloc[1].startswith("inactive|"))
        self.assertTrue(context.iloc[2].startswith("inactive|"))

    def test_focus_short_entry_signal_uses_context_side_gap_and_entry_rank(self):
        timestamps = pd.to_datetime(
            [
                "2025-01-01T00:00:00Z",
                "2025-01-01T00:01:00Z",
                "2025-01-01T00:02:00Z",
                "2025-01-01T00:03:00Z",
                "2025-01-01T00:04:00Z",
            ]
        )
        df = pd.DataFrame({"timestamp": timestamps})
        predictions = pd.DataFrame(
            {
                "decision_timestamp": timestamps,
                "dataset_month": ["2025-01"] * 5,
                "combined_regime": [
                    "range_low_vol",
                    "range_low_vol",
                    "range_low_vol",
                    "range_low_vol",
                    "range_low_vol",
                ],
                "session_regime": [
                    "ny_overlap",
                    "ny_overlap",
                    "asia",
                    "ny_overlap",
                    "ny_overlap",
                ],
                "pred_long_best_adjusted_pnl": [12.0, 12.0, 12.0, 12.0, 12.0],
                "pred_short_best_adjusted_pnl": [13.0, 13.0, 13.0, 13.0, 13.0],
                "pred_best_side_prob_1": [0.51, 0.45, 0.51, 0.45, 0.51],
                "pred_best_side_prob_-1": [0.49, 0.55, 0.49, 0.55, 0.49],
                "pred_short_entry_local_rank": [0.50, 0.53, 0.50, 0.53, 0.55],
            }
        )
        config = ModelPolicyConfig(predictions=Path("predictions.parquet"))
        signal = pd.Series([-1, -1, -1, -1, 1], index=df.index)

        context, active = side_context_interaction_guard_apply.interaction_entry_context(
            df,
            predictions,
            config,
            signal,
            context_columns=("dataset_month", "combined_regime"),
            match_mode="focus_short_entry_signal",
            focus_combined_regime="range_low_vol",
            focus_session_regime="ny_overlap",
            focus_side_gap_threshold=0.0,
            focus_entry_rank_threshold=0.52,
        )

        self.assertEqual(active.tolist(), [True, True, False, True, False])
        self.assertEqual(
            context.iloc[0],
            "guarded|dataset_month=2025-01|combined_regime=range_low_vol",
        )
        self.assertTrue(context.iloc[2].startswith("inactive|"))
        self.assertTrue(context.iloc[4].startswith("inactive|"))

    def test_signal_short_raw_gap_or_focus_short_entry_unions_both_masks(self):
        timestamps = pd.to_datetime(
            [
                "2025-01-01T00:00:00Z",
                "2025-01-01T00:01:00Z",
                "2025-01-01T00:02:00Z",
            ]
        )
        df = pd.DataFrame({"timestamp": timestamps})
        predictions = pd.DataFrame(
            {
                "decision_timestamp": timestamps,
                "dataset_month": ["2025-01"] * 3,
                "combined_regime": ["range_low_vol", "range_low_vol", "up_low_vol"],
                "session_regime": ["ny_overlap", "asia", "london"],
                "pred_long_best_adjusted_pnl": [20.0, 10.0, 10.0],
                "pred_short_best_adjusted_pnl": [21.0, 20.0, 13.0],
                "pred_best_side_prob_1": [0.51, 0.70, 0.40],
                "pred_best_side_prob_-1": [0.49, 0.30, 0.60],
                "pred_short_entry_local_rank": [0.50, 0.50, 0.50],
            }
        )
        config = ModelPolicyConfig(predictions=Path("predictions.parquet"))
        signal = pd.Series([-1, -1, -1], index=df.index)

        _, active = side_context_interaction_guard_apply.interaction_entry_context(
            df,
            predictions,
            config,
            signal,
            context_columns=("dataset_month", "combined_regime"),
            match_mode="signal_short_raw_gap_or_focus_short_entry",
            short_gap_threshold=5.0,
            focus_combined_regime="range_low_vol",
            focus_session_regime="ny_overlap",
            focus_side_gap_threshold=0.0,
            focus_entry_rank_threshold=0.52,
        )

        self.assertEqual(active.tolist(), [True, True, False])

    def test_replacement_trigger_metrics_use_only_prior_months(self):
        summary = side_context_interaction_guard_apply.normalize_replacement_trigger_summary(
            pd.DataFrame(
                {
                    "month": ["2025-01", "2025-02", "2025-03"],
                    "match_mode": ["signal_short_raw_gap"] * 3,
                    "short_gap_threshold": [5.0, 5.0, 5.0],
                    "context_entry_budget": [0.0, 0.0, 0.0],
                    "short_adjusted_pnl": [10.0, -2.0, -50.0],
                }
            )
        )

        february = side_context_interaction_guard_apply.replacement_trigger_metrics(
            summary,
            target_month="2025-02",
            trigger_match_mode="signal_short_raw_gap",
            trigger_short_gap_threshold=5.0,
            trigger_entry_budget=0.0,
            min_prior_months=1,
            recent_month_count=3,
            min_short_losing_months=1.0,
        )
        march = side_context_interaction_guard_apply.replacement_trigger_metrics(
            summary,
            target_month="2025-03",
            trigger_match_mode="signal_short_raw_gap",
            trigger_short_gap_threshold=5.0,
            trigger_entry_budget=0.0,
            min_prior_months=1,
            recent_month_count=3,
            min_short_losing_months=1.0,
        )
        march_min4 = side_context_interaction_guard_apply.replacement_trigger_metrics(
            summary,
            target_month="2025-03",
            trigger_match_mode="signal_short_raw_gap",
            trigger_short_gap_threshold=5.0,
            trigger_entry_budget=0.0,
            min_prior_months=4,
            recent_month_count=3,
            min_short_losing_months=1.0,
        )

        self.assertFalse(february["replacement_trigger_active"])
        self.assertEqual(february["replacement_trigger_short_losing_months"], 0.0)
        self.assertTrue(march["replacement_trigger_active"])
        self.assertEqual(march["replacement_trigger_short_losing_months"], 1.0)
        self.assertEqual(march["replacement_trigger_short_pnl"], 8.0)
        self.assertFalse(march_min4["replacement_trigger_active"])
        self.assertEqual(march_min4["replacement_trigger_prior_months"], 2)

    def test_triggered_replacement_modes_union_raw_gap_with_triggered_risk(self):
        timestamps = pd.to_datetime(
            [
                "2025-03-01T00:00:00Z",
                "2025-03-01T00:01:00Z",
                "2025-03-01T00:02:00Z",
                "2025-03-01T00:03:00Z",
            ]
        )
        df = pd.DataFrame({"timestamp": timestamps})
        predictions = pd.DataFrame(
            {
                "decision_timestamp": timestamps,
                "dataset_month": ["2025-03"] * 4,
                "pred_long_best_adjusted_pnl": [10.0, 13.0, 19.0, 18.0],
                "pred_short_best_adjusted_pnl": [17.0, 14.0, 20.0, 22.0],
                "pred_short_profit_barrier_hit": [0.8, 0.8, 0.4, 0.8],
            }
        )
        config = ModelPolicyConfig(predictions=Path("predictions.parquet"))
        signal = pd.Series([-1, -1, -1, -1], index=df.index)

        _, low_ev_active = side_context_interaction_guard_apply.interaction_entry_context(
            df,
            predictions,
            config,
            signal,
            context_columns=("dataset_month",),
            match_mode="signal_short_raw_gap_or_triggered_low_ev",
            short_gap_threshold=5.0,
            replacement_trigger_active=True,
            replacement_pred_ev_threshold=15.0,
        )
        _, profit_miss_active = side_context_interaction_guard_apply.interaction_entry_context(
            df,
            predictions,
            config,
            signal,
            context_columns=("dataset_month",),
            match_mode="signal_short_raw_gap_or_triggered_profit_miss",
            short_gap_threshold=5.0,
            replacement_trigger_active=True,
            replacement_profit_barrier_threshold=0.5,
        )
        _, inactive_trigger = side_context_interaction_guard_apply.interaction_entry_context(
            df,
            predictions,
            config,
            signal,
            context_columns=("dataset_month",),
            match_mode="signal_short_raw_gap_or_triggered_low_ev",
            short_gap_threshold=5.0,
            replacement_trigger_active=False,
            replacement_pred_ev_threshold=15.0,
        )

        self.assertEqual(low_ev_active.tolist(), [True, True, False, False])
        self.assertEqual(profit_miss_active.tolist(), [True, False, True, False])
        self.assertEqual(inactive_trigger.tolist(), [True, False, False, False])

    def test_prior_side_drift_alert_mode_uses_only_prior_matching_contexts(self):
        timestamps = pd.to_datetime(
            [
                "2025-02-01T00:00:00Z",
                "2025-02-01T00:01:00Z",
                "2025-02-01T00:02:00Z",
                "2025-02-01T00:03:00Z",
            ]
        )
        df = pd.DataFrame({"timestamp": timestamps})
        predictions = pd.DataFrame(
            {
                "decision_timestamp": timestamps,
                "combined_regime": [
                    "range_low_vol",
                    "up_normal_vol",
                    "down_normal_vol",
                    "late_only",
                ],
                "session_regime": ["london", "asia", "london", "rollover"],
            }
        )
        alerts = side_context_interaction_guard_apply.read_side_drift_alerts(
            []
        )
        self.assertIsNone(alerts)
        alerts = pd.DataFrame(
            {
                "month": ["2025-01", "2025-01", "2025-02"],
                "side": ["short", "long", "short"],
                "combined_regime": ["range_low_vol", "up_normal_vol", "late_only"],
                "session_regime": ["london", "asia", "rollover"],
                "is_alert": [True, True, True],
            }
        )
        alerts = side_context_interaction_guard_apply.read_side_drift_alerts_from_frame(
            alerts
        )
        config = ModelPolicyConfig(predictions=Path("predictions.parquet"))
        signal = pd.Series([-1, 1, -1, -1], index=df.index)

        context, active = side_context_interaction_guard_apply.interaction_entry_context(
            df,
            predictions,
            config,
            signal,
            context_columns=("combined_regime", "session_regime"),
            match_mode="prior_side_drift_alert",
            side_drift_alerts=alerts,
            target_month="2025-02",
            alert_sides=("short", "long"),
        )

        self.assertEqual(active.tolist(), [True, True, False, False])
        self.assertEqual(
            context.iloc[0],
            "guarded|combined_regime=range_low_vol|session_regime=london",
        )
        self.assertEqual(
            context.iloc[1],
            "guarded|combined_regime=up_normal_vol|session_regime=asia",
        )
        self.assertTrue(context.iloc[3].startswith("inactive|"))

    def test_filter_active_signal_by_entry_margin_blocks_weak_active_rows(self):
        signal = pd.Series([-1, -1, 1, -1])
        active = pd.Series([True, True, True, False])
        entry_margin = pd.Series([4.0, 12.0, float("nan"), 1.0])

        filtered = side_context_interaction_guard_apply.filter_active_signal_by_entry_margin(
            signal,
            active,
            entry_margin,
            active_min_entry_margin=10.0,
        )

        self.assertEqual(filtered.tolist(), [0, -1, 0, -1])

    def test_active_only_budget_context_drops_inactive_rows(self):
        entry_context = pd.Series(
            [
                "guarded|dataset_month=2025-01",
                "inactive|row=1",
                "guarded|dataset_month=2025-01",
            ],
            dtype="string",
        )
        active = pd.Series([True, False, True])

        budget_context = side_context_interaction_guard_apply.active_only_budget_context(
            entry_context,
            active,
        )

        self.assertEqual(budget_context.iloc[0], "guarded|dataset_month=2025-01")
        self.assertTrue(pd.isna(budget_context.iloc[1]))
        self.assertEqual(budget_context.iloc[2], "guarded|dataset_month=2025-01")


if __name__ == "__main__":
    unittest.main()
