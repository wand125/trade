import argparse
import contextlib
import importlib.util
import io
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "experiments"
    / "entry_ev_direction_exit_residual_target_diagnostics.py"
)
SPEC = importlib.util.spec_from_file_location(
    "entry_ev_direction_exit_residual_target_diagnostics",
    SCRIPT_PATH,
)
entry_ev_direction_exit_residual_target_diagnostics = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = entry_ev_direction_exit_residual_target_diagnostics
SPEC.loader.exec_module(entry_ev_direction_exit_residual_target_diagnostics)


def enriched_row(
    month: str,
    pnl: float,
    *,
    direction_error: bool,
    oracle_edge: float,
    exit_regret: float,
    actual_profit_hit: float,
) -> dict[str, object]:
    entry = pd.Timestamp(f"{month}-01 00:00:00", tz="UTC")
    return {
        "run_name": "validation",
        "role": "fresh",
        "family": "toy",
        "month": month,
        "candidate": "q95",
        "direction": "long",
        "entry_decision_timestamp": entry,
        "combined_regime": "range_normal_vol",
        "session_regime": "ny_overlap",
        "adjusted_pnl": pnl,
        "holding_minutes": 120.0,
        "exit_reason": "signal_close",
        "direction_error": direction_error,
        "actual_taken_best_adjusted_pnl": oracle_edge,
        "actual_taken_best_holding_minutes": 30.0,
        "actual_taken_profit_barrier_hit": actual_profit_hit,
        "exit_regret": exit_regret,
        "oracle_holding_gap_minutes": -90.0 if exit_regret > 0 else 0.0,
        "pred_taken_profit_barrier_hit": 0.0 if pnl < 0 else 1.0,
        "pred_side_confidence_gap": 0.05,
        "pred_taken_side_confidence": 0.525,
        "selected_loss_first_prob": 0.7 if pnl < 0 else 0.1,
        "selected_time_exit_prob": 0.2,
        "selected_pred_mlp_exit_minutes": 120.0,
        "pred_taken_best_holding_minutes": 60.0,
        "selected_ev_overestimate_risk": 0.6 if pnl < 0 else 0.2,
        "selected_fixed_60m_pred_pnl": 10.0,
        "selected_fixed_720m_pred_pnl": -15.0 if pnl < 0 else 20.0,
    }


class EntryEvDirectionExitResidualTargetDiagnosticsTests(unittest.TestCase):
    def test_add_feature_buckets_and_targets_marks_direction_exit_losses(self):
        frame = pd.DataFrame(
            [
                enriched_row(
                    "2025-01",
                    -12.0,
                    direction_error=True,
                    oracle_edge=25.0,
                    exit_regret=30.0,
                    actual_profit_hit=0.0,
                ),
                enriched_row(
                    "2025-02",
                    8.0,
                    direction_error=False,
                    oracle_edge=12.0,
                    exit_regret=0.0,
                    actual_profit_hit=1.0,
                ),
            ]
        )
        normalized = entry_ev_direction_exit_residual_target_diagnostics.normalize_trades(
            frame,
            candidates=set(),
            months=set(),
        )
        enriched = entry_ev_direction_exit_residual_target_diagnostics.add_feature_buckets_and_targets(
            normalized,
            min_oracle_edge=5.0,
            low_capture_threshold=0.25,
            large_exit_regret_threshold=20.0,
            hold_too_long_minutes=30.0,
        )

        loss_row = enriched.iloc[0]
        win_row = enriched.iloc[1]
        self.assertTrue(bool(loss_row["direction_error_loss_target"]))
        self.assertTrue(bool(loss_row["same_side_missed_loss_target"]))
        self.assertTrue(bool(loss_row["low_capture_loss_target"]))
        self.assertTrue(bool(loss_row["large_exit_regret_loss_target"]))
        self.assertTrue(bool(loss_row["profit_barrier_miss_loss_target"]))
        self.assertTrue(bool(loss_row["hold_too_long_loss_target"]))
        self.assertTrue(bool(loss_row["direction_and_exit_loss_target"]))
        self.assertTrue(bool(loss_row["same_side_large_regret_loss_target"]))
        self.assertFalse(bool(win_row["realized_loss_target"]))
        self.assertIn("loss_first_prob_bucket", enriched.columns)
        self.assertIn("side_confidence_gap_bucket", enriched.columns)

    def test_build_diagnostics_chronological_oof_uses_prior_months(self):
        rows = [
            enriched_row(
                "2025-01",
                5.0,
                direction_error=False,
                oracle_edge=10.0,
                exit_regret=0.0,
                actual_profit_hit=1.0,
            ),
            enriched_row(
                "2025-02",
                -10.0,
                direction_error=True,
                oracle_edge=20.0,
                exit_regret=25.0,
                actual_profit_hit=0.0,
            ),
            enriched_row(
                "2025-03",
                -11.0,
                direction_error=True,
                oracle_edge=20.0,
                exit_regret=25.0,
                actual_profit_hit=0.0,
            ),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            input_path = tmp_path / "enriched.csv"
            pd.DataFrame(rows).to_csv(input_path, index=False)
            args = argparse.Namespace(
                enriched_trades=[input_path],
                targets="direction_error_loss_target",
                calibration_specs="side_context",
                candidates="",
                months="",
                min_oracle_edge=5.0,
                low_capture_threshold=0.25,
                large_exit_regret_threshold=20.0,
                hold_too_long_minutes=30.0,
                prior_strength=0.0,
                min_group_support=1,
                top_n=10,
                output_dir=tmp_path,
                label="unit_direction_exit",
            )

            with contextlib.redirect_stdout(io.StringIO()):
                output_dir = (
                    entry_ev_direction_exit_residual_target_diagnostics.build_diagnostics(args)
                )
            predictions = pd.read_csv(
                output_dir / "direction_exit_chronological_predictions.csv"
            )
            summary = pd.read_csv(output_dir / "direction_exit_chronological_summary.csv")

        jan = predictions[predictions["month"].eq("2025-01")].iloc[0]
        feb = predictions[predictions["month"].eq("2025-02")].iloc[0]
        mar = predictions[predictions["month"].eq("2025-03")].iloc[0]
        self.assertEqual(jan["prediction_source"], "no_prior")
        self.assertEqual(feb["prediction_source"], "bucket")
        self.assertAlmostEqual(feb["predicted_target_rate"], 0.0)
        self.assertAlmostEqual(mar["predicted_target_rate"], 0.5)
        self.assertEqual(summary["target"].iloc[0], "direction_error_loss_target")

    def test_calibration_specs_exclude_realized_outcome_columns(self):
        forbidden = {
            "adjusted_pnl",
            "actual_taken_best_adjusted_pnl",
            "actual_taken_best_holding_minutes",
            "actual_taken_profit_barrier_hit",
            "exit_regret",
            "oracle_holding_gap_minutes",
            "direction_error",
            "exit_capture_ratio",
        }
        for columns in entry_ev_direction_exit_residual_target_diagnostics.CALIBRATION_SPECS.values():
            self.assertTrue(forbidden.isdisjoint(columns))


if __name__ == "__main__":
    unittest.main()
