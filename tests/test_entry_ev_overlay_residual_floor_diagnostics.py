import importlib.util
import sys
import unittest
from pathlib import Path

import pandas as pd


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "experiments"
    / "entry_ev_overlay_residual_floor_diagnostics.py"
)
SPEC = importlib.util.spec_from_file_location(
    "entry_ev_overlay_residual_floor_diagnostics",
    SCRIPT_PATH,
)
entry_ev_overlay_residual_floor_diagnostics = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = entry_ev_overlay_residual_floor_diagnostics
SPEC.loader.exec_module(entry_ev_overlay_residual_floor_diagnostics)


class EntryEvOverlayResidualFloorDiagnosticsTest(unittest.TestCase):
    def test_add_fixed_horizon_deltas_selects_best_positive_horizon(self) -> None:
        frame = pd.DataFrame(
            {
                "adjusted_pnl": [-1.0, -2.0],
                "selected_fixed_60m_actual_pnl": [0.5, -3.0],
                "selected_fixed_240m_actual_pnl": [-0.5, 1.0],
                "selected_fixed_720m_actual_pnl": [2.0, -1.0],
            }
        )

        output = entry_ev_overlay_residual_floor_diagnostics.add_fixed_horizon_deltas(
            frame,
            horizons=[60, 240, 720],
        )

        self.assertEqual(output["best_fixed_horizon_minutes"].tolist(), [720.0, 240.0])
        self.assertEqual(output["best_fixed_delta_vs_realized"].tolist(), [3.0, 3.0])
        self.assertEqual(output["best_fixed_improves_realized"].tolist(), [True, True])

    def test_summarize_negative_months_marks_sparse_support_and_fixed_rescue(self) -> None:
        monthly = pd.DataFrame(
            {
                "role": ["fresh", "refit"],
                "month": ["2024-03", "2025-03"],
                "variant": ["v1", "v1"],
                "total_adjusted_pnl": [-0.5, 1.0],
                "trade_count": [1, 3],
                "long_trade_count": [0, 2],
                "short_trade_count": [1, 1],
                "max_side_trade_share": [1.0, 2 / 3],
            }
        )
        trades = pd.DataFrame(
            {
                "role": ["fresh", "refit", "refit", "refit"],
                "month": ["2024-03", "2025-03", "2025-03", "2025-03"],
                "adjusted_pnl": [-0.5, -1.0, 0.7, 1.3],
                "best_fixed_delta_vs_realized": [2.0, -0.2, 0.0, 0.0],
                "best_fixed_horizon_minutes": [720.0, 60.0, 60.0, 60.0],
            }
        )

        summary = entry_ev_overlay_residual_floor_diagnostics.summarize_negative_months(
            monthly=monthly,
            trades=trades,
            horizons=[60, 240, 720],
            month_floor=0.0,
            thin_month_trade_threshold=5,
            side_share_threshold=0.95,
        )

        self.assertEqual(len(summary), 1)
        row = summary.iloc[0]
        self.assertTrue(row["single_trade_month"])
        self.assertTrue(row["thin_month"])
        self.assertTrue(row["side_share_high"])
        self.assertEqual(row["fixed_best_improved_loss_count"], 1)
        self.assertEqual(row["fixed_best_improved_loss_delta_sum"], 2.0)
        self.assertEqual(row["fixed_best_horizon_counts"], "720m:1")


if __name__ == "__main__":
    unittest.main()
