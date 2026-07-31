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
    / "entry_ev_exit_shortening_target_diagnostics.py"
)
SPEC = importlib.util.spec_from_file_location(
    "entry_ev_exit_shortening_target_diagnostics",
    SCRIPT_PATH,
)
entry_ev_exit_shortening_target_diagnostics = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = entry_ev_exit_shortening_target_diagnostics
SPEC.loader.exec_module(entry_ev_exit_shortening_target_diagnostics)


def residual_row(
    month: str,
    pnl: float,
    *,
    oracle_edge: float,
    holding: float,
    oracle_hold: float,
    exit_regret: float,
    pred_exit_hold: float,
    pred_taken_hold: float,
    barrier_hit: float = 1.0,
    forced: bool = False,
) -> dict[str, object]:
    entry = pd.Timestamp(f"{month}-01 00:00:00", tz="UTC")
    return {
        "run_name": "direction",
        "role": "fixed",
        "month": month,
        "candidate": "q99",
        "direction": "long",
        "entry_decision_timestamp": entry,
        "combined_regime": "range_normal_vol",
        "session_regime": "ny_overlap",
        "adjusted_pnl": pnl,
        "holding_minutes": holding,
        "actual_taken_best_adjusted_pnl": oracle_edge,
        "actual_taken_best_holding_minutes": oracle_hold,
        "exit_regret": exit_regret,
        "oracle_holding_gap_minutes": oracle_hold - holding,
        "selected_pred_mlp_exit_minutes": pred_exit_hold,
        "pred_taken_best_holding_minutes": pred_taken_hold,
        "selected_time_exit_prob": 0.2,
        "selected_loss_first_prob": 0.8 if pnl < 0 else 0.1,
        "selected_fixed_60m_pred_pnl": 10.0,
        "selected_fixed_720m_pred_pnl": -15.0 if pnl < 0 else 20.0,
        "selected_ev_overestimate_risk": 0.7,
        "selected_direction_risk_bucket": "medium",
        "actual_taken_profit_barrier_hit": barrier_hit,
        "is_forced_exit": forced,
        "exit_reason": "forced_exit" if forced else "signal_close",
    }


class EntryEvExitShorteningTargetDiagnosticsTests(unittest.TestCase):
    def test_add_exit_features_marks_narrow_shortening_targets(self):
        frame = pd.DataFrame(
            [
                residual_row(
                    "2025-02",
                    -25.0,
                    oracle_edge=30.0,
                    holding=120.0,
                    oracle_hold=30.0,
                    exit_regret=25.0,
                    pred_exit_hold=120.0,
                    pred_taken_hold=30.0,
                    barrier_hit=0.0,
                    forced=True,
                ),
                residual_row(
                    "2025-03",
                    8.0,
                    oracle_edge=20.0,
                    holding=60.0,
                    oracle_hold=60.0,
                    exit_regret=0.0,
                    pred_exit_hold=60.0,
                    pred_taken_hold=60.0,
                ),
            ]
        )
        normalized = entry_ev_exit_shortening_target_diagnostics.normalize_trades(
            frame,
            candidates=set(),
            months=set(),
        )
        enriched = entry_ev_exit_shortening_target_diagnostics.add_exit_features_and_targets(
            normalized,
            large_loss_threshold=-20.0,
            min_oracle_edge=5.0,
            low_capture_threshold=0.25,
            large_exit_regret_threshold=20.0,
            hold_too_long_minutes=30.0,
            pred_hold_too_long_minutes=30.0,
        )

        loss_row = enriched.iloc[0]
        win_row = enriched.iloc[1]
        self.assertTrue(bool(loss_row["hold_too_long_loss_target"]))
        self.assertTrue(bool(loss_row["exit_shortening_residual_target"]))
        self.assertTrue(bool(loss_row["hold_prediction_too_long_loss_target"]))
        self.assertTrue(bool(loss_row["low_capture_loss_target"]))
        self.assertTrue(bool(loss_row["late_exit_regret_loss_target"]))
        self.assertTrue(bool(loss_row["forced_exit_loss_target"]))
        self.assertTrue(bool(loss_row["profit_barrier_miss_loss_target"]))
        self.assertTrue(bool(loss_row["large_exit_shortening_loss_target"]))
        self.assertFalse(bool(win_row["exit_shortening_residual_target"]))

    def test_build_diagnostics_chronological_oof_uses_only_prior_months(self):
        rows = [
            residual_row(
                "2025-01",
                5.0,
                oracle_edge=10.0,
                holding=60.0,
                oracle_hold=60.0,
                exit_regret=0.0,
                pred_exit_hold=60.0,
                pred_taken_hold=60.0,
            ),
            residual_row(
                "2025-02",
                -20.0,
                oracle_edge=30.0,
                holding=120.0,
                oracle_hold=30.0,
                exit_regret=25.0,
                pred_exit_hold=60.0,
                pred_taken_hold=60.0,
            ),
            residual_row(
                "2025-03",
                -22.0,
                oracle_edge=35.0,
                holding=120.0,
                oracle_hold=30.0,
                exit_regret=30.0,
                pred_exit_hold=60.0,
                pred_taken_hold=60.0,
            ),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            input_path = tmp_path / "residual.csv"
            pd.DataFrame(rows).to_csv(input_path, index=False)
            args = argparse.Namespace(
                residual_trades=[input_path],
                targets="exit_shortening_residual_target",
                calibration_specs="side_context",
                candidates="q99",
                months="",
                large_loss_threshold=-20.0,
                min_oracle_edge=5.0,
                low_capture_threshold=0.25,
                large_exit_regret_threshold=20.0,
                hold_too_long_minutes=30.0,
                pred_hold_too_long_minutes=30.0,
                prior_strength=0.0,
                min_group_support=1,
                top_n=10,
                output_dir=tmp_path,
                label="unit_exit_shortening",
            )

            output_dir = entry_ev_exit_shortening_target_diagnostics.build_diagnostics(args)
            predictions = pd.read_csv(
                output_dir / "exit_shortening_chronological_predictions.csv"
            )
            summary = pd.read_csv(output_dir / "exit_shortening_chronological_summary.csv")

        jan = predictions[predictions["month"].eq("2025-01")].iloc[0]
        feb = predictions[predictions["month"].eq("2025-02")].iloc[0]
        mar = predictions[predictions["month"].eq("2025-03")].iloc[0]
        metric = summary.iloc[0]

        self.assertEqual(jan["prediction_source"], "no_prior")
        self.assertEqual(feb["prediction_source"], "bucket")
        self.assertAlmostEqual(feb["predicted_target_rate"], 0.0)
        self.assertAlmostEqual(mar["predicted_target_rate"], 0.5)
        self.assertEqual(metric["target"], "exit_shortening_residual_target")
        self.assertEqual(metric["row_count"], 3)

    def test_calibration_specs_use_only_decision_time_feature_buckets(self):
        forbidden = {
            "adjusted_pnl",
            "actual_taken_best_adjusted_pnl",
            "actual_taken_best_holding_minutes",
            "exit_regret",
            "oracle_holding_gap_minutes",
            "exit_capture_ratio",
        }
        for columns in entry_ev_exit_shortening_target_diagnostics.CALIBRATION_SPECS.values():
            self.assertTrue(forbidden.isdisjoint(columns))


if __name__ == "__main__":
    unittest.main()
