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
