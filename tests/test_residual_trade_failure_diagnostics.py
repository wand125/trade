import importlib.util
import io
import json
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "experiments"
    / "residual_trade_failure_diagnostics.py"
)
SPEC = importlib.util.spec_from_file_location("residual_trade_failure_diagnostics", SCRIPT_PATH)
residual_trade_failure_diagnostics = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(residual_trade_failure_diagnostics)


def diagnostic_examples() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "month": ["2025-01", "2025-01", "2025-02", "2025-02"],
            "direction": ["long", "short", "short", "short"],
            "combined_regime": ["up_low_vol", "range_low_vol", "range_low_vol", "range_low_vol"],
            "session_regime": ["asia", "london", "asia", "asia"],
            "entry_hour": [0, 8, 1, 2],
            "adjusted_pnl": [10.0, -4.0, -20.0, -5.0],
            "direction_error": [False, True, True, False],
            "predicted_side_error": [False, True, True, False],
            "pred_taken_profit_barrier_hit": [0, 0, 0, 1],
            "actual_taken_profit_barrier_hit": [1, 0, 0, 0],
            "pred_taken_ev": [12.0, 10.0, 22.0, 18.0],
            "pred_side_gap": [2.0, 8.0, 11.0, 7.0],
            "pred_taken_side_confidence": [0.55, 0.52, 0.61, 0.53],
            "ev_overestimate_vs_realized": [2.0, 14.0, 42.0, 23.0],
            "exit_regret": [3.0, 9.0, 31.0, 15.0],
            "pred_side_gap_bucket": ["2-5", "5-10", ">10", "5-10"],
            "pred_side_confidence_bucket": ["0.55-0.7", "0.4-0.55", "0.55-0.7", "0.4-0.55"],
            "profit_barrier_outcome": [
                "pred_miss_actual_hit",
                "pred_miss_actual_miss",
                "pred_miss_actual_miss",
                "pred_hit_actual_miss",
            ],
            "pred_holding_bucket": ["6-12h", "6-12h", "6-12h", "12-24h"],
        }
    )


class ResidualTradeFailureDiagnosticsTests(unittest.TestCase):
    def test_select_residual_months_uses_negative_month_pnl(self):
        months = residual_trade_failure_diagnostics.select_residual_months(
            diagnostic_examples(),
            max_month_pnl=0.0,
        )

        self.assertEqual(months, ["2025-02"])

    def test_run_diagnostics_writes_residual_group_summaries(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            trades_path = root / "diagnostic_trades.csv"
            diagnostic_examples().to_csv(trades_path, index=False)

            with redirect_stdout(io.StringIO()):
                run_dir = residual_trade_failure_diagnostics.run_diagnostics(
                    trades_path=trades_path,
                    output_dir=root,
                    label="residual_smoke",
                    top_n=5,
                )

            metrics = json.loads((run_dir / "metrics.json").read_text(encoding="utf-8"))
            residual = pd.read_csv(run_dir / "residual_trades.csv")
            context = pd.read_csv(run_dir / "residual_by_context.csv")
            direction = pd.read_csv(run_dir / "residual_by_direction.csv")

            self.assertEqual(metrics["selected_months"], ["2025-02"])
            self.assertEqual(len(residual), 2)
            self.assertEqual(len(context), 1)
            self.assertAlmostEqual(context.loc[0, "total_adjusted_pnl"], -25.0)
            self.assertEqual(direction.loc[0, "direction"], "short")


if __name__ == "__main__":
    unittest.main()
