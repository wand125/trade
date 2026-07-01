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
    / "entry_ev_direction_residual_loss_diagnostics.py"
)
SPEC = importlib.util.spec_from_file_location(
    "entry_ev_direction_residual_loss_diagnostics",
    SCRIPT_PATH,
)
entry_ev_direction_residual_loss_diagnostics = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = entry_ev_direction_residual_loss_diagnostics
SPEC.loader.exec_module(entry_ev_direction_residual_loss_diagnostics)


def trade_row(decision_time: str, direction: str, pnl: float) -> dict[str, object]:
    entry_decision = pd.Timestamp(decision_time, tz="UTC")
    entry = entry_decision + pd.Timedelta(minutes=1)
    exit_time = entry + pd.Timedelta(minutes=60)
    return {
        "direction": direction,
        "entry_timestamp": entry,
        "exit_timestamp": exit_time,
        "entry_price": 100.0,
        "exit_price": 100.0 + pnl,
        "raw_pnl": pnl,
        "adjusted_pnl": pnl,
        "holding_minutes": 60.0,
        "exit_reason": "signal_close" if pnl >= 0 else "forced_exit",
        "entry_decision_timestamp": entry_decision,
        "exit_decision_timestamp": exit_time - pd.Timedelta(minutes=1),
    }


class EntryEvDirectionResidualLossDiagnosticsTests(unittest.TestCase):
    def test_build_diagnostics_flags_direction_and_exit_residuals(self):
        predictions = pd.DataFrame(
            {
                "decision_timestamp": pd.to_datetime(
                    ["2025-03-01 00:00:00Z", "2025-03-02 00:00:00Z"],
                    utc=True,
                ),
                "dataset_month": ["2025-03", "2025-03"],
                "combined_regime": ["range_normal_vol", "down_normal_vol"],
                "session_regime": ["ny_overlap", "london"],
                "long_best_adjusted_pnl": [30.0, 5.0],
                "short_best_adjusted_pnl": [50.0, 1.0],
                "long_best_holding_minutes": [30.0, 90.0],
                "short_best_holding_minutes": [45.0, 60.0],
                "long_max_adverse_pnl": [-5.0, -1.0],
                "short_max_adverse_pnl": [-2.0, -1.0],
                "long_profit_barrier_hit": [1, 1],
                "short_profit_barrier_hit": [1, 0],
                "long_wait_regret": [0.0, 0.0],
                "short_wait_regret": [0.0, 0.0],
                "long_entry_local_rank": [0.9, 0.8],
                "short_entry_local_rank": [0.9, 0.7],
                "pred_direction_inversion_bucket_s0p1_long_best_adjusted_pnl": [
                    10.0,
                    4.0,
                ],
                "pred_direction_inversion_bucket_s0p1_short_best_adjusted_pnl": [
                    9.0,
                    2.0,
                ],
                "pred_long_best_holding_minutes": [60.0, 90.0],
                "pred_short_best_holding_minutes": [45.0, 60.0],
                "pred_long_max_adverse_pnl": [-2.0, -1.0],
                "pred_short_max_adverse_pnl": [-2.0, -1.0],
                "pred_long_wait_regret": [1.0, 1.0],
                "pred_short_wait_regret": [1.0, 1.0],
                "pred_long_entry_local_rank": [0.8, 0.8],
                "pred_short_entry_local_rank": [0.7, 0.7],
                "pred_long_profit_barrier_hit": [1.0, 1.0],
                "pred_short_profit_barrier_hit": [1.0, 0.0],
                "pred_best_side_prob_1": [0.6, 0.6],
                "pred_best_side_prob_-1": [0.4, 0.4],
                "pred_direction_inversion_long_predicted_direction_inversion_risk": [
                    0.20,
                    0.10,
                ],
                "pred_direction_inversion_short_predicted_direction_inversion_risk": [
                    0.80,
                    0.80,
                ],
                "pred_direction_inversion_long_direction_inversion_prediction_support": [
                    5,
                    5,
                ],
                "pred_direction_inversion_short_direction_inversion_prediction_support": [
                    5,
                    5,
                ],
                "pred_direction_inversion_long_direction_inversion_prediction_source": [
                    "bucket",
                    "bucket",
                ],
                "pred_direction_inversion_short_direction_inversion_prediction_source": [
                    "bucket",
                    "bucket",
                ],
                "pred_direction_inversion_long_selected_risk_bucket": ["very_low", "very_low"],
                "pred_direction_inversion_short_selected_risk_bucket": ["extreme", "extreme"],
                "pred_direction_inversion_long_selected_side_support_bucket": ["high", "high"],
                "pred_direction_inversion_short_selected_side_support_bucket": ["high", "high"],
                "pred_direction_inversion_long_selected_side_pressure_bucket": ["low", "low"],
                "pred_direction_inversion_short_selected_side_pressure_bucket": ["high", "high"],
                "pred_replacement_quality_risk_pressure_long_predicted_replacement_quality": [
                    0.30,
                    0.90,
                ],
                "pred_replacement_quality_risk_pressure_short_predicted_replacement_quality": [
                    0.90,
                    0.90,
                ],
                "pred_replacement_quality_risk_pressure_long_replacement_quality_prediction_support": [
                    3,
                    3,
                ],
                "pred_replacement_quality_risk_pressure_short_replacement_quality_prediction_support": [
                    3,
                    3,
                ],
                "pred_replacement_quality_risk_pressure_long_replacement_quality_prediction_source": [
                    "bucket",
                    "bucket",
                ],
                "pred_replacement_quality_risk_pressure_short_replacement_quality_prediction_source": [
                    "bucket",
                    "bucket",
                ],
                "pred_side_prior_pressure_long_predicted_ev_overestimate_risk": [0.2, 0.2],
                "pred_side_prior_pressure_short_predicted_ev_overestimate_risk": [0.8, 0.8],
                "pred_side_prior_pressure_long_ev_overestimate_prediction_source": [
                    "bucket",
                    "bucket",
                ],
                "pred_side_prior_pressure_short_ev_overestimate_prediction_source": [
                    "bucket",
                    "bucket",
                ],
                "pred_mlp_long_exit_event_minutes": [60.0, 90.0],
                "pred_mlp_short_exit_event_minutes": [45.0, 60.0],
                "pred_long_exit_event_prob_0": [0.1, 0.1],
                "pred_short_exit_event_prob_0": [0.2, 0.2],
                "pred_long_exit_event_prob_2": [0.7, 0.1],
                "pred_short_exit_event_prob_2": [0.1, 0.1],
            }
        )

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            prediction_path = tmp_path / "pred.parquet"
            predictions.to_parquet(prediction_path, index=False)
            run_dir = tmp_path / "run"
            trade_dir = run_dir / "trades" / "fam" / "c1"
            trade_dir.mkdir(parents=True)
            pd.DataFrame(
                [
                    {
                        "family": "fam",
                        "role": "fixed",
                        "month": "2025-03",
                        "candidate": "c1",
                        "total_adjusted_pnl": -20.0,
                        "trade_count": 2,
                        "max_drawdown": 25.0,
                        "long_trade_count": 2,
                        "short_trade_count": 0,
                    }
                ]
            ).to_csv(run_dir / "monthly_policy_metrics.csv", index=False)
            pd.DataFrame(
                [
                    trade_row("2025-03-01 00:00:00", "long", -25.0),
                    trade_row("2025-03-02 00:00:00", "long", 5.0),
                ]
            ).to_csv(trade_dir / "2025-03.csv", index=False)

            args = argparse.Namespace(
                policy_run=[f"direction={run_dir}"],
                predictions=prediction_path,
                long_column="pred_direction_inversion_bucket_s0p1_long_best_adjusted_pnl",
                short_column="pred_direction_inversion_bucket_s0p1_short_best_adjusted_pnl",
                extra_columns="",
                large_loss_threshold=-20.0,
                low_direction_risk_threshold=0.45,
                low_replacement_quality_threshold=0.40,
                min_oracle_edge=5.0,
                low_exit_capture_threshold=0.25,
                large_exit_regret_threshold=20.0,
                hold_too_long_minutes=30.0,
                top_n=10,
                output_dir=tmp_path,
                label="unit_residual_diag",
            )

            output_dir = entry_ev_direction_residual_loss_diagnostics.build_diagnostics(args)
            flags = pd.read_csv(output_dir / "flag_residual_summary.csv")
            enriched = pd.read_csv(output_dir / "residual_enriched_trades.csv")
            worst = pd.read_csv(output_dir / "worst_residual_trades.csv")

            direction_row = flags[flags["flag"].eq("direction_side_inversion_target")].iloc[0]
            low_risk_row = flags[flags["flag"].eq("low_direction_risk_large_loss_target")].iloc[0]
            low_quality_row = flags[flags["flag"].eq("low_replacement_quality_loss_target")].iloc[0]

            self.assertAlmostEqual(direction_row["flag_loss_pnl"], -25.0)
            self.assertAlmostEqual(low_risk_row["flag_loss_pnl"], -25.0)
            self.assertAlmostEqual(low_quality_row["flag_loss_pnl"], -25.0)
            self.assertTrue(bool(enriched["exit_capture_failure_target"].iloc[0]))
            self.assertIn("direction_side_inversion_target", worst["residual_failure_combo"].iloc[0])


if __name__ == "__main__":
    unittest.main()
