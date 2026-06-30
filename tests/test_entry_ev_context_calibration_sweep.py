import argparse
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "experiments"
    / "entry_ev_context_calibration_sweep.py"
)
SPEC = importlib.util.spec_from_file_location(
    "entry_ev_context_calibration_sweep",
    SCRIPT_PATH,
)
entry_ev_context_calibration_sweep = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = entry_ev_context_calibration_sweep
SPEC.loader.exec_module(entry_ev_context_calibration_sweep)


class EntryEvContextCalibrationSweepTests(unittest.TestCase):
    def test_parse_model_specs_requires_unique_named_specs(self):
        specs = entry_ev_context_calibration_sweep.parse_model_specs(
            "base=support_bucket,pressure_bucket;side=direction,support_bucket"
        )

        self.assertEqual(specs[0], ("base", ["support_bucket", "pressure_bucket"]))
        self.assertEqual(specs[1], ("side", ["direction", "support_bucket"]))

        with self.assertRaises(argparse.ArgumentTypeError):
            entry_ev_context_calibration_sweep.parse_model_specs(
                "base=support_bucket;base=pressure_bucket"
            )

    def test_build_calibration_sweep_writes_context_outputs(self):
        rows = []
        for idx, (month, role) in enumerate(
            [
                ("2024-01", "cal2024_calibration_validation"),
                ("2024-01", "cal2024_calibration_validation"),
                ("2024-02", "fresh2024_validation"),
                ("2024-02", "fresh2024_validation"),
                ("2024-03", "refit2025_validation"),
                ("2024-03", "refit2025_validation"),
            ]
        ):
            is_long = idx % 2 == 0
            rows.append(
                {
                    "candidate": "c1" if idx < 4 else "c2",
                    "role": role,
                    "month": month,
                    "direction": "long" if is_long else "short",
                    "entry_decision_timestamp": f"{month}-01 00:0{idx}:00+00:00",
                    "adjusted_pnl": -5.0 if idx in {2, 4} else 3.0,
                    "support_bucket": "low" if idx < 4 else "high",
                    "pressure_bucket": "low" if idx < 3 else "high",
                    "prior_downside_support_weight": 0.0 if idx < 2 else 0.4,
                    "feature_pressure_score": 0.2 if idx < 3 else 0.8,
                    "side_balance_signed_drift_for_trade": -0.1 if is_long else 0.1,
                    "prior_downside_risk_score": 0.0 if idx < 2 else 0.5,
                    "executable_ev_overestimate_target": idx in {2, 4},
                }
            )
        frame = pd.DataFrame(rows)

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            component_path = tmp_path / "component.csv"
            frame.to_csv(component_path, index=False)
            args = argparse.Namespace(
                component_targets=component_path,
                target="executable_ev_overestimate_target",
                model_specs=(
                    "base=support_bucket,pressure_bucket;"
                    "side=direction,support_bucket,pressure_bucket;"
                    "full=direction,support_bucket,pressure_bucket,"
                    "prior_support_bucket,feature_pressure_bucket,side_drift_bucket"
                ),
                validation_roles=(
                    "cal2024_calibration_validation,fresh2024_validation,"
                    "refit2025_validation"
                ),
                prior_strength=1.0,
                min_group_support=1,
                risk_threshold=0.5,
                pointwise_thresholds="0.5",
                output_dir=tmp_path,
                label="unit_context_calibration",
            )

            run_dir = entry_ev_context_calibration_sweep.build_calibration_sweep(args)

            metric_summary = pd.read_csv(run_dir / "context_calibration_metric_summary.csv")
            candidate_summary = pd.read_csv(
                run_dir / "validation_candidate_context_risk_summary.csv"
            )
            pointwise = pd.read_csv(run_dir / "validation_pointwise_context_screen_effects.csv")

            self.assertEqual(
                set(metric_summary["calibration_spec"]),
                {"base", "side", "full"},
            )
            self.assertIn("high_risk_pnl", candidate_summary.columns)
            self.assertIn("predicted_high_only", set(pointwise["screen_mode"]))

    def test_pointwise_screen_zero_fills_empty_months(self):
        frame = pd.DataFrame(
            {
                "calibration_spec": ["base", "base"],
                "candidate": ["c1", "c1"],
                "role": ["fresh", "fresh"],
                "month": ["2024-01", "2024-02"],
                "adjusted_pnl": [2.0, -3.0],
                "executable_ev_overestimate_target": [False, True],
                "predicted_target_rate": [0.2, 0.8],
                "prediction_source": ["bucket", "bucket"],
            }
        )

        screened = entry_ev_context_calibration_sweep.pointwise_screen_effects(
            frame,
            target="executable_ev_overestimate_target",
            thresholds=[0.5],
        )
        row = screened[screened["screen_mode"].eq("predicted_high_only")].iloc[0]

        self.assertEqual(row["kept_trades"], 1)
        self.assertAlmostEqual(row["kept_min_month_pnl"], 0.0)


if __name__ == "__main__":
    unittest.main()
