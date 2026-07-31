import importlib.util
import unittest
from pathlib import Path

import pandas as pd


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "experiments"
    / "context_drawdown_guard_selection.py"
)
SPEC = importlib.util.spec_from_file_location("context_drawdown_guard_selection", SCRIPT_PATH)
context_drawdown_guard_selection = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(context_drawdown_guard_selection)


def selection_examples() -> pd.DataFrame:
    rows = []
    for month, no_guard_pnl, guarded_pnl in [
        ("2025-01", 100.0, 20.0),
        ("2025-02", -50.0, -5.0),
        ("2025-03", -80.0, -10.0),
        ("2025-04", -90.0, -15.0),
    ]:
        rows.append(
            {
                "month": month,
                "context_drawdown_guard_loss_threshold": float("inf"),
                "trade_count": 10,
                "total_adjusted_pnl": no_guard_pnl,
                "max_drawdown": abs(min(no_guard_pnl, 0.0)),
                "forced_exit_count": 0,
                "short_adjusted_pnl": no_guard_pnl,
                "long_adjusted_pnl": 0.0,
            }
        )
        rows.append(
            {
                "month": month,
                "context_drawdown_guard_loss_threshold": 20.0,
                "trade_count": 5,
                "total_adjusted_pnl": guarded_pnl,
                "max_drawdown": abs(min(guarded_pnl, 0.0)),
                "forced_exit_count": 0,
                "short_adjusted_pnl": guarded_pnl,
                "long_adjusted_pnl": 0.0,
            }
        )
    return pd.DataFrame(rows)


class ContextDrawdownGuardSelectionTests(unittest.TestCase):
    def test_select_threshold_can_prioritize_total_or_worst_month(self):
        prior = context_drawdown_guard_selection.normalize_summary(
            selection_examples()[lambda frame: frame["month"].isin(["2025-01", "2025-02"])]
        )

        total = context_drawdown_guard_selection.select_threshold(prior, objective="total")
        worst = context_drawdown_guard_selection.select_threshold(prior, objective="worst")

        self.assertEqual(total["context_drawdown_guard_loss_threshold"], float("inf"))
        self.assertEqual(worst["context_drawdown_guard_loss_threshold"], 20.0)

    def test_walkforward_selection_uses_only_prior_months(self):
        selected = context_drawdown_guard_selection.walkforward_selection(
            selection_examples(),
            objectives=["worst"],
            min_train_months=2,
        )

        target = selected[selected["target_month"] == "2025-03"].iloc[0]

        self.assertEqual(target["prior_start_month"], "2025-01")
        self.assertEqual(target["prior_end_month"], "2025-02")
        self.assertEqual(target["selected_threshold"], 20.0)
        self.assertEqual(target["target_total_pnl"], -10.0)

    def test_summarize_walkforward_reports_threshold_set(self):
        selected = context_drawdown_guard_selection.walkforward_selection(
            selection_examples(),
            objectives=["total", "worst"],
            min_train_months=2,
        )

        summary = context_drawdown_guard_selection.summarize_walkforward(selected)

        self.assertIn("selected_thresholds", summary.columns)
        worst_row = summary[summary["selection_name"] == "worst"].iloc[0]
        self.assertEqual(worst_row["selected_thresholds"], "20")

    def test_summarize_walkforward_sorts_threshold_set_numerically(self):
        selected = pd.DataFrame(
            [
                {
                    "selection_name": "example",
                    "objective": "worst",
                    "target_month": "2025-03",
                    "selected_threshold": 100.0,
                    "target_trade_count": 1,
                    "target_total_pnl": 1.0,
                    "target_max_drawdown": 0.0,
                    "target_forced_exit_count": 0,
                    "target_short_pnl": 1.0,
                    "target_long_pnl": 0.0,
                },
                {
                    "selection_name": "example",
                    "objective": "worst",
                    "target_month": "2025-04",
                    "selected_threshold": 20.0,
                    "target_trade_count": 1,
                    "target_total_pnl": 1.0,
                    "target_max_drawdown": 0.0,
                    "target_forced_exit_count": 0,
                    "target_short_pnl": 1.0,
                    "target_long_pnl": 0.0,
                },
                {
                    "selection_name": "example",
                    "objective": "worst",
                    "target_month": "2025-05",
                    "selected_threshold": float("inf"),
                    "target_trade_count": 1,
                    "target_total_pnl": 1.0,
                    "target_max_drawdown": 0.0,
                    "target_forced_exit_count": 0,
                    "target_short_pnl": 1.0,
                    "target_long_pnl": 0.0,
                },
            ]
        )

        summary = context_drawdown_guard_selection.summarize_walkforward(selected)

        self.assertEqual(summary.iloc[0]["selected_thresholds"], "20,100,inf")

    def test_risk_budget_marks_fallback_when_constraints_are_impossible(self):
        prior = context_drawdown_guard_selection.normalize_summary(
            selection_examples()[lambda frame: frame["month"].isin(["2025-01", "2025-02"])]
        )

        selected = context_drawdown_guard_selection.select_threshold(
            prior,
            objective="risk_budget",
            min_validation_worst_month_pnl=999.0,
        )

        self.assertFalse(bool(selected["eligible"]))

    def test_walkforward_selection_can_use_multiple_candidate_columns(self):
        examples = selection_examples()
        expanded = []
        for _, row in examples.iterrows():
            for margin, adjustment in [(float("inf"), 0.0), (20.0, 2.0)]:
                candidate = row.copy()
                candidate["context_drawdown_guard_min_entry_margin"] = margin
                candidate["total_adjusted_pnl"] = float(candidate["total_adjusted_pnl"]) + adjustment
                expanded.append(candidate)
        frame = pd.DataFrame(expanded)

        selected = context_drawdown_guard_selection.walkforward_selection(
            frame,
            objectives=["total"],
            min_train_months=2,
            candidate_columns=(
                "context_drawdown_guard_loss_threshold",
                "context_drawdown_guard_min_entry_margin",
            ),
        )

        target = selected[selected["target_month"] == "2025-03"].iloc[0]

        self.assertIn("selected_context_drawdown_guard_min_entry_margin", selected.columns)
        self.assertEqual(target["selected_threshold"], float("inf"))
        self.assertEqual(target["selected_context_drawdown_guard_min_entry_margin"], 20.0)
        self.assertIn("context_drawdown_guard_min_entry_margin=20", target["selected_candidate"])


if __name__ == "__main__":
    unittest.main()
