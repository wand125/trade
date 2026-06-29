import importlib.util
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "experiments"
    / "side_drift_diagnostics.py"
)
SPEC = importlib.util.spec_from_file_location("side_drift_diagnostics", SCRIPT_PATH)
side_drift_diagnostics = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(side_drift_diagnostics)


class SideDriftDiagnosticsTests(unittest.TestCase):
    def test_prediction_summary_tracks_actual_and_predicted_side_shares(self):
        predictions = pd.DataFrame(
            {
                "decision_timestamp": pd.to_datetime(
                    [
                        "2025-01-01 00:00:00+00:00",
                        "2025-01-01 00:01:00+00:00",
                        "2025-01-01 00:02:00+00:00",
                        "2025-01-01 00:03:00+00:00",
                    ],
                    utc=True,
                ),
                "dataset_month": ["2025-01"] * 4,
                "label": [1, 1, -1, 0],
                "best_side": [1, -1, -1, 1],
                "pred_long_best_adjusted_pnl": [1.0, 2.0, 1.0, 5.0],
                "pred_short_best_adjusted_pnl": [3.0, 4.0, 6.0, 2.0],
            }
        )

        with_sides = side_drift_diagnostics.add_prediction_side_columns(
            predictions,
            long_column="pred_long_best_adjusted_pnl",
            short_column="pred_short_best_adjusted_pnl",
        )
        summary = side_drift_diagnostics.summarize_predictions(with_sides, ["dataset_month"])

        self.assertEqual(int(summary.loc[0, "prediction_rows"]), 4)
        self.assertAlmostEqual(summary.loc[0, "actual_label_long_share"], 0.5)
        self.assertAlmostEqual(summary.loc[0, "actual_label_short_share"], 0.25)
        self.assertAlmostEqual(summary.loc[0, "actual_label_flat_share"], 0.25)
        self.assertAlmostEqual(summary.loc[0, "pred_ev_short_share"], 0.75)
        self.assertAlmostEqual(
            summary.loc[0, "pred_short_minus_actual_label_short_share"],
            0.50,
        )

    def test_enrich_trades_with_predictions_computes_direction_errors(self):
        predictions = pd.DataFrame(
            {
                "decision_timestamp": pd.to_datetime(
                    ["2025-01-01 00:00:00+00:00", "2025-01-01 01:00:00+00:00"],
                    utc=True,
                ),
                "dataset_month": ["2025-01", "2025-01"],
                "label": [1, -1],
                "best_side": [1, -1],
                "pred_long_best_adjusted_pnl": [10.0, 2.0],
                "pred_short_best_adjusted_pnl": [3.0, 9.0],
                "combined_regime": ["up_normal_vol", "range_low_vol"],
                "session_regime": ["london", "asia"],
            }
        )
        predictions = side_drift_diagnostics.add_prediction_side_columns(
            predictions,
            long_column="pred_long_best_adjusted_pnl",
            short_column="pred_short_best_adjusted_pnl",
        )
        trades = pd.DataFrame(
            {
                "direction": ["short", "short"],
                "entry_decision_timestamp": [
                    "2025-01-01 00:00:00+00:00",
                    "2025-01-01 01:00:00+00:00",
                ],
                "adjusted_pnl": [-2.0, 5.0],
                "month": ["2025-01", "2025-01"],
                "variant": ["v", "v"],
                "cost_case": ["c", "c"],
            }
        )

        enriched = side_drift_diagnostics.enrich_trades_with_predictions(
            trades,
            predictions,
            long_column="pred_long_best_adjusted_pnl",
            short_column="pred_short_best_adjusted_pnl",
        )

        self.assertTrue(bool(enriched.loc[0, "prediction_matched"]))
        self.assertTrue(bool(enriched.loc[0, "direction_error"]))
        self.assertFalse(bool(enriched.loc[1, "direction_error"]))
        self.assertAlmostEqual(enriched.loc[0, "ev_overestimate_vs_realized"], 5.0)

    def test_side_drift_alerts_flag_biased_losing_side(self):
        prediction_group = pd.DataFrame(
            {
                "dataset_month": ["2025-01"],
                "combined_regime": ["range_low_vol"],
                "session_regime": ["london"],
                "prediction_rows": [100],
                "pred_ev_long_share": [0.2],
                "actual_label_long_share": [0.8],
                "pred_ev_short_share": [0.8],
                "actual_label_short_share": [0.2],
            }
        )
        selected_group = pd.DataFrame(
            {
                "cost_case": ["stress"],
                "variant": ["candidate"],
                "month": ["2025-01"],
                "combined_regime": ["range_low_vol"],
                "session_regime": ["london"],
                "direction_side_name": ["short"],
                "trade_count": [4],
                "total_adjusted_pnl": [-12.0],
                "win_rate": [0.25],
                "direction_error_rate": [0.75],
            }
        )

        alerts = side_drift_diagnostics.build_side_drift_alerts(
            prediction_group,
            selected_group,
            group_columns=["combined_regime", "session_regime"],
            min_alert_trades=3,
            min_alert_bias=0.1,
        )

        self.assertEqual(len(alerts), 1)
        self.assertTrue(bool(alerts.loc[0, "is_alert"]))
        self.assertEqual(alerts.loc[0, "side"], "short")
        self.assertAlmostEqual(alerts.loc[0, "side_share_bias"], 0.6)

    def test_run_diagnostics_writes_expected_files(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            predictions = pd.DataFrame(
                {
                    "decision_timestamp": pd.to_datetime(
                        ["2025-01-01 00:00:00+00:00", "2025-01-01 01:00:00+00:00"],
                        utc=True,
                    ),
                    "dataset_month": ["2025-01", "2025-01"],
                    "label": [1, -1],
                    "best_side": [1, -1],
                    "pred_long_best_adjusted_pnl": [1.0, 1.0],
                    "pred_short_best_adjusted_pnl": [2.0, 3.0],
                    "combined_regime": ["range_low_vol", "range_low_vol"],
                    "session_regime": ["london", "london"],
                }
            )
            prediction_path = root / "predictions.parquet"
            predictions.to_parquet(prediction_path, index=False)
            run_dir = root / "run"
            run_dir.mkdir()
            pd.DataFrame(
                {
                    "direction": ["short"],
                    "entry_decision_timestamp": ["2025-01-01 00:00:00+00:00"],
                    "adjusted_pnl": [-2.0],
                }
            ).to_csv(run_dir / "trades.csv", index=False)
            policy_summary = root / "policy_summary.csv"
            pd.DataFrame(
                {
                    "month": ["2025-01"],
                    "run_dir": [str(run_dir)],
                    "variant": ["candidate"],
                    "cost_case": ["stress"],
                }
            ).to_csv(policy_summary, index=False)
            output_dir = root / "out"

            metrics = side_drift_diagnostics.run_diagnostics(
                predictions_path=prediction_path,
                policy_summary_path=policy_summary,
                months=["2025-01"],
                variants=["candidate"],
                cost_cases=["stress"],
                group_columns=["combined_regime", "session_regime"],
                long_column="pred_long_best_adjusted_pnl",
                short_column="pred_short_best_adjusted_pnl",
                output_dir=output_dir,
                min_alert_trades=1,
                min_alert_bias=0.1,
            )

            self.assertEqual(metrics["rows"]["predictions"], 2)
            self.assertTrue((output_dir / "prediction_month_summary.csv").exists())
            self.assertTrue((output_dir / "selected_trade_month_summary.csv").exists())
            self.assertTrue((output_dir / "side_drift_alerts.csv").exists())


if __name__ == "__main__":
    unittest.main()
