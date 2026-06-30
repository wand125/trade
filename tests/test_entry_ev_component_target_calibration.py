import importlib.util
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "experiments"
    / "entry_ev_component_target_calibration.py"
)
SPEC = importlib.util.spec_from_file_location(
    "entry_ev_component_target_calibration",
    SCRIPT_PATH,
)
entry_ev_component_target_calibration = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = entry_ev_component_target_calibration
SPEC.loader.exec_module(entry_ev_component_target_calibration)


def row(month, role, target, support="high", pressure="low", pnl=1.0):
    return {
        "candidate": "c1",
        "role": role,
        "month": month,
        "adjusted_pnl": pnl,
        "support_bucket": support,
        "pressure_bucket": pressure,
        "direction_side_inversion_target": target,
        "exit_capture_failure_target": False,
        "executable_ev_overestimate_target": False,
        "realized_loss_target": pnl < 0,
    }


class EntryEvComponentTargetCalibrationTests(unittest.TestCase):
    def test_normalize_targets_maps_missing_group_values(self):
        frame = pd.DataFrame([row("2024-01", "cal", False, support=np.nan, pressure="")])
        normalized = entry_ev_component_target_calibration.normalize_targets(
            frame,
            targets=["direction_side_inversion_target"],
            group_columns=["support_bucket", "pressure_bucket"],
        )

        self.assertEqual(normalized.iloc[0]["support_bucket"], "missing")
        self.assertEqual(normalized.iloc[0]["pressure_bucket"], "missing")

    def test_chronological_month_predictions_use_only_prior_months(self):
        frame = pd.DataFrame(
            [
                row("2024-01", "cal", False),
                row("2024-02", "fresh", True),
                row("2024-03", "refit", True),
            ]
        )
        normalized = entry_ev_component_target_calibration.normalize_targets(
            frame,
            targets=["direction_side_inversion_target"],
            group_columns=["support_bucket", "pressure_bucket"],
        )
        predictions, metrics = (
            entry_ev_component_target_calibration.chronological_month_predictions(
                normalized,
                targets=["direction_side_inversion_target"],
                group_columns=["support_bucket", "pressure_bucket"],
                prior_strength=0.0,
                min_group_support=1,
            )
        )

        feb = predictions[
            predictions["month"].eq("2024-02")
            & predictions["target"].eq("direction_side_inversion_target")
        ].iloc[0]
        jan = predictions[
            predictions["month"].eq("2024-01")
            & predictions["target"].eq("direction_side_inversion_target")
        ].iloc[0]
        feb_metrics = metrics[
            metrics["fold"].eq("2024-02")
            & metrics["target"].eq("direction_side_inversion_target")
        ].iloc[0]

        self.assertEqual(jan["prediction_source"], "no_prior")
        self.assertEqual(feb["prediction_source"], "bucket")
        self.assertEqual(feb["predicted_target_rate"], 0.0)
        self.assertEqual(feb_metrics["train_rows"], 1)

    def test_role_holdout_predictions_exclude_holdout_role(self):
        frame = pd.DataFrame(
            [
                row("2024-01", "cal", False),
                row("2024-02", "fresh", True),
                row("2024-03", "refit", True),
            ]
        )
        normalized = entry_ev_component_target_calibration.normalize_targets(
            frame,
            targets=["direction_side_inversion_target"],
            group_columns=["support_bucket", "pressure_bucket"],
        )
        predictions, metrics = entry_ev_component_target_calibration.role_holdout_predictions(
            normalized,
            targets=["direction_side_inversion_target"],
            group_columns=["support_bucket", "pressure_bucket"],
            prior_strength=0.0,
            min_group_support=1,
        )

        fresh = predictions[
            predictions["role"].eq("fresh")
            & predictions["target"].eq("direction_side_inversion_target")
        ].iloc[0]
        fresh_metrics = metrics[
            metrics["fold"].eq("fresh")
            & metrics["target"].eq("direction_side_inversion_target")
        ].iloc[0]

        self.assertEqual(fresh["prediction_source"], "bucket")
        self.assertEqual(fresh["predicted_target_rate"], 0.5)
        self.assertEqual(fresh_metrics["train_rows"], 2)
        self.assertEqual(fresh_metrics["train_roles"], 2)


if __name__ == "__main__":
    unittest.main()
