from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

import pandas as pd


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "experiments"
    / "short_budget_drift_trigger_selection.py"
)
SPEC = importlib.util.spec_from_file_location(
    "short_budget_drift_trigger_selection",
    SCRIPT_PATH,
)
short_budget_drift_trigger_selection = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = short_budget_drift_trigger_selection
SPEC.loader.exec_module(short_budget_drift_trigger_selection)

Candidate = short_budget_drift_trigger_selection.Candidate
RuleSpec = short_budget_drift_trigger_selection.RuleSpec


def base_frame() -> pd.DataFrame:
    rows = []
    months = ["2025-01", "2025-02", "2025-03", "2025-04", "2025-05"]
    primary_short = [20, 30, -40, -50, -500]
    primary_total = [120, 130, 40, 30, -500]
    defensive_short = [0, 0, 0, 0, 10]
    defensive_total = [90, 95, 90, 85, 80]
    for month, short_pnl, total_pnl, defensive_s, defensive_t in zip(
        months,
        primary_short,
        primary_total,
        defensive_short,
        defensive_total,
    ):
        rows.append(
            {
                "month": month,
                "short_gap_threshold": 5.0,
                "context_entry_budget": 0.0,
                "trade_count": 10,
                "total_adjusted_pnl": total_pnl,
                "max_drawdown": max(0, -total_pnl),
                "forced_exit_count": 0,
                "short_adjusted_pnl": short_pnl,
                "long_adjusted_pnl": total_pnl - short_pnl,
                "active_trade_count": 0,
                "active_trade_pnl": 0.0,
            }
        )
        rows.append(
            {
                "month": month,
                "short_gap_threshold": 0.0,
                "context_entry_budget": 0.0,
                "trade_count": 5,
                "total_adjusted_pnl": defensive_t,
                "max_drawdown": 0,
                "forced_exit_count": 0,
                "short_adjusted_pnl": defensive_s,
                "long_adjusted_pnl": defensive_t - defensive_s,
                "active_trade_count": 0,
                "active_trade_pnl": 0.0,
            }
        )
    return pd.DataFrame(rows)


class ShortBudgetDriftTriggerSelectionTests(unittest.TestCase):
    def test_recent_short_pnl_trigger_uses_only_prior_months(self):
        rule = RuleSpec(
            name="trigger",
            primary=Candidate(5.0, 0.0),
            defensive=Candidate(0.0, 0.0),
            trigger_metric="recent_short_pnl",
            operator="lt",
            threshold=-20.0,
        )

        selected = short_budget_drift_trigger_selection.walkforward_trigger_selection(
            base_frame(),
            rules=[rule],
            min_train_months=3,
            train_window_months=0,
            recent_month_count=2,
        )

        first = selected[selected["target_month"] == "2025-04"].iloc[0]
        second = selected[selected["target_month"] == "2025-05"].iloc[0]
        self.assertEqual(first["selected_candidate"], "short_gap_threshold=5|context_entry_budget=0")
        self.assertFalse(bool(first["triggered"]))
        self.assertEqual(second["selected_candidate"], "short_gap_threshold=0|context_entry_budget=0")
        self.assertTrue(bool(second["triggered"]))
        self.assertEqual(float(second["target_total_pnl"]), 80.0)

    def test_make_rule_specs_includes_always_and_metric_rules(self):
        rules = short_budget_drift_trigger_selection.make_rule_specs(
            primary_candidates=[Candidate(5.0, 0.0)],
            defensive_candidate=Candidate(0.0, 0.0),
            metrics=["recent_short_losing_months"],
            threshold_overrides={"recent_short_losing_months": (1.0,)},
        )

        self.assertEqual(len(rules), 3)
        self.assertEqual(rules[-1].operator, "ge")
        self.assertEqual(rules[-1].threshold, 1.0)

    def test_summary_counts_triggered_months(self):
        rule = RuleSpec(
            name="always_defensive",
            primary=Candidate(5.0, 0.0),
            defensive=Candidate(0.0, 0.0),
            trigger_metric="recent_short_pnl",
            operator="lt",
            threshold=float("inf"),
        )
        selected = short_budget_drift_trigger_selection.walkforward_trigger_selection(
            base_frame(),
            rules=[rule],
            min_train_months=3,
            train_window_months=0,
            recent_month_count=2,
        )
        summary = short_budget_drift_trigger_selection.summarize_walkforward(selected)

        self.assertEqual(int(summary.iloc[0]["target_months"]), 2)
        self.assertEqual(int(summary.iloc[0]["triggered_months"]), 2)
        self.assertEqual(float(summary.iloc[0]["total_pnl"]), 165.0)

    def test_prediction_summary_metric_can_trigger_from_prior_months(self):
        prediction_summary = pd.DataFrame(
            {
                "dataset_month": ["2025-01", "2025-02", "2025-03", "2025-04"],
                "pred_ev_short_share": [0.4, 0.5, 0.9, 0.9],
                "actual_label_short_share": [0.3, 0.3, 0.3, 0.3],
                "pred_short_minus_actual_label_short_share": [0.1, 0.2, 0.6, 0.6],
                "pred_ev_matches_nonflat_label_rate": [0.7, 0.6, 0.4, 0.4],
                "pred_side_score_mean": [1.0, 0.0, -5.0, -5.0],
            }
        )
        rule = RuleSpec(
            name="prediction_trigger",
            primary=Candidate(5.0, 0.0),
            defensive=Candidate(0.0, 0.0),
            trigger_metric="recent_pred_short_bias_mean",
            operator="ge",
            threshold=0.5,
        )

        selected = short_budget_drift_trigger_selection.walkforward_trigger_selection(
            base_frame(),
            rules=[rule],
            min_train_months=3,
            train_window_months=0,
            recent_month_count=2,
            prediction_summary=(
                short_budget_drift_trigger_selection.normalize_prediction_summary(
                    prediction_summary
                )
            ),
        )

        first = selected[selected["target_month"] == "2025-04"].iloc[0]
        second = selected[selected["target_month"] == "2025-05"].iloc[0]
        self.assertEqual(first["selected_candidate"], "short_gap_threshold=5|context_entry_budget=0")
        self.assertFalse(bool(first["triggered"]))
        self.assertEqual(second["selected_candidate"], "short_gap_threshold=0|context_entry_budget=0")
        self.assertTrue(bool(second["triggered"]))
        self.assertAlmostEqual(float(second["recent_pred_short_bias_mean"]), 0.6)

    def test_side_drift_alert_metric_combines_prior_alerts_with_candidate_loss(self):
        side_drift_alerts = pd.DataFrame(
            {
                "month": ["2025-04"],
                "side": ["short"],
                "is_alert": [True],
                "loss_bias_score": [25.0],
                "total_adjusted_pnl": [-30.0],
            }
        )
        rule = RuleSpec(
            name="alert_and_loss",
            primary=Candidate(5.0, 0.0),
            defensive=Candidate(0.0, 0.0),
            trigger_metric="recent_short_alert_and_short_losing_months",
            operator="ge",
            threshold=1.0,
        )

        selected = short_budget_drift_trigger_selection.walkforward_trigger_selection(
            base_frame(),
            rules=[rule],
            min_train_months=3,
            train_window_months=0,
            recent_month_count=2,
            side_drift_alerts=(
                short_budget_drift_trigger_selection.normalize_side_drift_alerts(
                    side_drift_alerts
                )
            ),
        )

        first = selected[selected["target_month"] == "2025-04"].iloc[0]
        second = selected[selected["target_month"] == "2025-05"].iloc[0]
        self.assertEqual(first["selected_candidate"], "short_gap_threshold=5|context_entry_budget=0")
        self.assertFalse(bool(first["triggered"]))
        self.assertEqual(second["selected_candidate"], "short_gap_threshold=0|context_entry_budget=0")
        self.assertTrue(bool(second["triggered"]))
        self.assertAlmostEqual(
            float(second["recent_short_alert_and_short_losing_months"]),
            1.0,
        )
        self.assertAlmostEqual(float(second["recent_short_side_drift_loss_bias_sum"]), 25.0)


if __name__ == "__main__":
    unittest.main()
