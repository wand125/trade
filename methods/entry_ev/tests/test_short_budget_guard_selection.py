import importlib.util
import unittest
from pathlib import Path

import pandas as pd


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "experiments"
    / "short_budget_guard_selection.py"
)
SPEC = importlib.util.spec_from_file_location("short_budget_guard_selection", SCRIPT_PATH)
short_budget_guard_selection = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(short_budget_guard_selection)


class ShortBudgetGuardSelectionTests(unittest.TestCase):
    def base_frame(self):
        return pd.DataFrame(
            {
                "month": ["2025-01", "2025-01", "2025-02", "2025-02", "2025-03", "2025-03"],
                "short_gap_threshold": [0, 5, 0, 5, 0, 5],
                "context_entry_budget": [1, 1, 1, 1, 1, 1],
                "trade_count": [10, 10, 10, 10, 10, 10],
                "total_adjusted_pnl": [2, 10, 2, 10, -20, 10],
                "max_drawdown": [3, 4, 3, 4, 20, 4],
                "forced_exit_count": [0, 0, 0, 0, 0, 0],
                "short_adjusted_pnl": [1, 8, 1, 8, -30, 8],
                "long_adjusted_pnl": [1, 2, 1, 2, 10, 2],
                "active_trade_count": [2, 3, 2, 3, 2, 3],
                "active_trade_pnl": [1, -5, 1, -5, -30, -5],
            }
        )

    def test_active_stability_prefers_fewer_active_losing_months(self):
        selected = short_budget_guard_selection.select_candidate(
            self.base_frame(),
            objective="active_stability",
            candidate_columns=("short_gap_threshold", "context_entry_budget"),
            recent_month_count=2,
            active_loss_count_weight=25.0,
            short_loss_count_weight=10.0,
            worst_weight=1.0,
            drawdown_weight=0.25,
        )

        self.assertEqual(float(selected["short_gap_threshold"]), 0.0)

    def test_short_total_prefers_better_short_pnl(self):
        selected = short_budget_guard_selection.select_candidate(
            self.base_frame(),
            objective="short_total",
            candidate_columns=("short_gap_threshold", "context_entry_budget"),
            recent_month_count=2,
            active_loss_count_weight=25.0,
            short_loss_count_weight=10.0,
            worst_weight=1.0,
            drawdown_weight=0.25,
        )

        self.assertEqual(float(selected["short_gap_threshold"]), 5.0)

    def test_defensive_budget_prefers_lower_budget_then_worst_month(self):
        frame = pd.DataFrame(
            {
                "month": ["2025-01", "2025-01", "2025-02", "2025-02"],
                "short_gap_threshold": [0, 0, 0, 0],
                "context_entry_budget": [1, 2, 1, 2],
                "trade_count": [5, 8, 5, 8],
                "total_adjusted_pnl": [1, 20, -2, 20],
                "max_drawdown": [2, 4, 3, 4],
                "forced_exit_count": [0, 0, 0, 0],
                "short_adjusted_pnl": [1, 18, -2, 18],
                "long_adjusted_pnl": [0, 2, 0, 2],
                "active_trade_count": [1, 3, 1, 3],
                "active_trade_pnl": [1, 10, -2, 10],
            }
        )

        selected = short_budget_guard_selection.select_candidate(
            frame,
            objective="defensive_budget",
            candidate_columns=("short_gap_threshold", "context_entry_budget"),
            recent_month_count=2,
            active_loss_count_weight=25.0,
            short_loss_count_weight=10.0,
            worst_weight=1.0,
            drawdown_weight=0.25,
        )

        self.assertEqual(float(selected["context_entry_budget"]), 1.0)

    def test_walkforward_selection_uses_only_prior_months(self):
        frame = self.base_frame()
        selection = short_budget_guard_selection.walkforward_selection(
            frame,
            objectives=["active_stability"],
            min_train_months=2,
            train_window_months=0,
            candidate_columns=("short_gap_threshold", "context_entry_budget"),
            recent_month_count=2,
            active_loss_count_weight=25.0,
            short_loss_count_weight=10.0,
            worst_weight=1.0,
            drawdown_weight=0.25,
        )

        self.assertEqual(selection["target_month"].tolist(), ["2025-03"])
        self.assertEqual(float(selection.iloc[0]["selected_short_gap_threshold"]), 0.0)


if __name__ == "__main__":
    unittest.main()
