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
    / "entry_ev_side_prior_pressure_failure_diagnostics.py"
)
SPEC = importlib.util.spec_from_file_location(
    "entry_ev_side_prior_pressure_failure_diagnostics",
    SCRIPT_PATH,
)
entry_ev_side_prior_pressure_failure_diagnostics = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = entry_ev_side_prior_pressure_failure_diagnostics
SPEC.loader.exec_module(entry_ev_side_prior_pressure_failure_diagnostics)


def trade_row(decision_time: str, direction: str, pnl: float) -> dict[str, object]:
    entry_decision = pd.Timestamp(decision_time, tz="UTC")
    entry = entry_decision + pd.Timedelta(minutes=1)
    exit_time = entry + pd.Timedelta(minutes=30)
    return {
        "direction": direction,
        "entry_timestamp": entry,
        "exit_timestamp": exit_time,
        "entry_price": 100.0,
        "exit_price": 100.0 + pnl,
        "raw_pnl": pnl,
        "adjusted_pnl": pnl,
        "holding_minutes": 30.0,
        "exit_reason": "signal_close",
        "entry_decision_timestamp": entry_decision,
        "exit_decision_timestamp": exit_time - pd.Timedelta(minutes=1),
    }


class EntryEvSidePriorPressureFailureDiagnosticsTests(unittest.TestCase):
    def test_replacement_delta_summary_uses_only_candidate_minus_only_base(self):
        base = pd.DataFrame(
            {
                "candidate": ["c1", "c1"],
                "month": ["2025-03", "2025-03"],
                "direction": ["long", "short"],
                "entry_decision_timestamp": pd.to_datetime(
                    ["2025-03-01 00:00:00Z", "2025-03-02 00:00:00Z"],
                    utc=True,
                ),
                "adjusted_pnl": [5.0, -10.0],
                "variant": ["base", "base"],
            }
        )
        candidate = pd.DataFrame(
            {
                "candidate": ["c1", "c1"],
                "month": ["2025-03", "2025-03"],
                "direction": ["long", "short"],
                "entry_decision_timestamp": pd.to_datetime(
                    ["2025-03-01 00:00:00Z", "2025-03-03 00:00:00Z"],
                    utc=True,
                ),
                "adjusted_pnl": [5.0, -3.0],
                "variant": ["side_prior", "side_prior"],
            }
        )

        combined = entry_ev_side_prior_pressure_failure_diagnostics.add_replacement_status(
            base,
            candidate,
            base_label="base",
            candidate_label="side_prior",
        )
        summary = entry_ev_side_prior_pressure_failure_diagnostics.summarize_by(
            combined,
            ["candidate", "replacement_status"],
        )
        delta = entry_ev_side_prior_pressure_failure_diagnostics.replacement_delta_summary(
            summary,
            base_label="base",
            candidate_label="side_prior",
        ).iloc[0]
        variant_summary = entry_ev_side_prior_pressure_failure_diagnostics.summarize_by(
            combined,
            ["candidate", "variant", "replacement_status"],
        )
        path_delta = entry_ev_side_prior_pressure_failure_diagnostics.variant_path_delta_summary(
            variant_summary,
            base_label="base",
            candidate_label="side_prior",
        ).iloc[0]

        self.assertAlmostEqual(delta["only_base_pnl"], -10.0)
        self.assertAlmostEqual(delta["only_candidate_pnl"], -3.0)
        self.assertAlmostEqual(delta["replacement_delta_pnl"], 7.0)
        self.assertEqual(delta["common_count"], 2)
        self.assertAlmostEqual(path_delta["base_common_pnl"], 5.0)
        self.assertAlmostEqual(path_delta["candidate_common_pnl"], 5.0)
        self.assertAlmostEqual(path_delta["common_entry_delta_pnl"], 0.0)
        self.assertAlmostEqual(path_delta["replacement_delta_pnl"], 7.0)
        self.assertAlmostEqual(path_delta["base_total_pnl"], -5.0)
        self.assertAlmostEqual(path_delta["candidate_total_pnl"], 2.0)
        self.assertAlmostEqual(path_delta["total_delta_pnl"], 7.0)

    def test_build_diagnostics_writes_replacement_outputs(self):
        predictions = pd.DataFrame(
            {
                "decision_timestamp": pd.to_datetime(
                    [
                        "2025-03-01 00:00:00Z",
                        "2025-03-02 00:00:00Z",
                        "2025-03-03 00:00:00Z",
                    ],
                    utc=True,
                ),
                "dataset_month": ["2025-03", "2025-03", "2025-03"],
                "combined_regime": ["range", "range", "trend"],
                "session_regime": ["asia", "asia", "london"],
                "long_best_adjusted_pnl": [8.0, 2.0, 1.0],
                "short_best_adjusted_pnl": [1.0, -2.0, -4.0],
                "pred_side_balanced_dense_executable_long_best_adjusted_pnl": [8.0, 2.0, 1.0],
                "pred_side_balanced_dense_executable_short_best_adjusted_pnl": [1.0, 4.0, 6.0],
                "pred_side_prior_pressure_s0p5_long_best_adjusted_pnl": [7.0, 1.0, 1.0],
                "pred_side_prior_pressure_s0p5_short_best_adjusted_pnl": [1.0, 3.0, 5.0],
                "pred_side_prior_pressure_long_predicted_ev_overestimate_risk": [0.2, 0.5, 0.1],
                "pred_side_prior_pressure_short_predicted_ev_overestimate_risk": [0.1, 0.4, 0.8],
                "pred_side_prior_pressure_long_ev_overestimate_prediction_source": [
                    "bucket",
                    "bucket",
                    "global",
                ],
                "pred_side_prior_pressure_short_ev_overestimate_prediction_source": [
                    "bucket",
                    "bucket",
                    "global",
                ],
            }
        )

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            prediction_path = tmp_path / "pred.parquet"
            predictions.to_parquet(prediction_path, index=False)
            for run_name, decisions in {
                "base": [
                    ("2025-03-01 00:00:00", "long", 5.0),
                    ("2025-03-02 00:00:00", "short", -10.0),
                ],
                "side": [
                    ("2025-03-01 00:00:00", "long", 5.0),
                    ("2025-03-03 00:00:00", "short", -3.0),
                ],
            }.items():
                run_dir = tmp_path / run_name
                trade_dir = run_dir / "trades" / "fam" / "c1"
                trade_dir.mkdir(parents=True)
                pd.DataFrame(
                    [
                        {
                            "family": "fam",
                            "role": "fixed",
                            "month": "2025-03",
                            "candidate": "c1",
                            "total_adjusted_pnl": 0.0,
                            "trade_count": len(decisions),
                            "max_drawdown": 0.0,
                            "long_trade_count": 1,
                            "short_trade_count": 1,
                        }
                    ]
                ).to_csv(run_dir / "monthly_policy_metrics.csv", index=False)
                pd.DataFrame(
                    [trade_row(decision, direction, pnl) for decision, direction, pnl in decisions]
                ).to_csv(trade_dir / "2025-03.csv", index=False)

            args = argparse.Namespace(
                base_run_dir=tmp_path / "base",
                candidate_run_dir=tmp_path / "side",
                predictions=prediction_path,
                base_label="base",
                candidate_label="side_prior",
                base_long_column="pred_side_balanced_dense_executable_long_best_adjusted_pnl",
                base_short_column="pred_side_balanced_dense_executable_short_best_adjusted_pnl",
                candidate_long_column="pred_side_prior_pressure_s0p5_long_best_adjusted_pnl",
                candidate_short_column="pred_side_prior_pressure_s0p5_short_best_adjusted_pnl",
                extra_columns="",
                top_n=10,
                output_dir=tmp_path,
                label="unit_failure_diag",
            )

            run_dir = entry_ev_side_prior_pressure_failure_diagnostics.build_diagnostics(args)
            delta = pd.read_csv(run_dir / "replacement_delta_summary.csv")
            path_delta = pd.read_csv(run_dir / "path_delta_summary.csv")
            context = pd.read_csv(run_dir / "context_replacement_path_summary.csv")

            self.assertAlmostEqual(delta["replacement_delta_pnl"].iloc[0], 7.0)
            self.assertAlmostEqual(path_delta["total_delta_pnl"].iloc[0], 7.0)
            self.assertIn("selected_risk_mean", context.columns)


if __name__ == "__main__":
    unittest.main()
