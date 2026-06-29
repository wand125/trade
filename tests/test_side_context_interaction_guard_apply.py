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


if __name__ == "__main__":
    unittest.main()
