import importlib.util
import sys
import unittest
from pathlib import Path

import pandas as pd


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "experiments"
    / "entry_ev_exit_capture_target_diagnostics.py"
)
SPEC = importlib.util.spec_from_file_location(
    "entry_ev_exit_capture_target_diagnostics",
    SCRIPT_PATH,
)
entry_ev_exit_capture_target_diagnostics = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = entry_ev_exit_capture_target_diagnostics
SPEC.loader.exec_module(entry_ev_exit_capture_target_diagnostics)


class EntryEvExitCaptureTargetDiagnosticsTests(unittest.TestCase):
    def test_add_exit_capture_targets_marks_missed_same_side_profit(self):
        trades = pd.DataFrame(
            {
                "adjusted_pnl": [-2.0, 2.0, 5.0],
                "actual_taken_best_adjusted_pnl": [10.0, 20.0, -1.0],
                "exit_regret": [12.0, 18.0, 0.0],
            }
        )

        enriched = entry_ev_exit_capture_target_diagnostics.add_exit_capture_targets(
            trades,
            min_oracle_edge=0.0,
            low_capture_threshold=0.25,
            large_exit_regret_threshold=10.0,
        )

        self.assertEqual(enriched["same_side_oracle_edge"].tolist(), [True, True, False])
        self.assertEqual(enriched["same_side_missed_loss"].tolist(), [True, False, False])
        self.assertEqual(enriched["low_exit_capture"].tolist(), [True, True, False])
        self.assertEqual(enriched["large_exit_regret"].tolist(), [True, True, False])
        self.assertEqual(enriched["exit_capture_failure"].tolist(), [True, True, False])
        self.assertAlmostEqual(enriched["exit_capture_ratio"].iloc[0], -0.2)
        self.assertAlmostEqual(enriched["exit_capture_shortfall"].iloc[1], 18.0)

    def test_add_prior_exit_capture_risk_uses_only_prior_months(self):
        target = pd.DataFrame(
            {
                "role": ["fresh", "fresh"],
                "candidate": ["q95", "q95"],
                "month": ["2024-03", "2024-04"],
                "direction": ["short", "short"],
                "entry_decision_timestamp": [
                    "2024-03-10T00:00:00Z",
                    "2024-04-10T00:00:00Z",
                ],
                "combined_regime": ["range", "range"],
                "session_regime": ["asia", "asia"],
                "adjusted_pnl": [1.0, 1.0],
                "actual_taken_best_adjusted_pnl": [5.0, 5.0],
                "exit_regret": [4.0, 4.0],
            }
        )
        prior = pd.DataFrame(
            {
                "role": ["cal", "fresh", "future"],
                "candidate": ["q95", "q95", "q95"],
                "month": ["2024-02", "2024-03", "2024-04"],
                "direction": ["short", "short", "short"],
                "entry_decision_timestamp": [
                    "2024-02-10T00:00:00Z",
                    "2024-03-10T00:00:00Z",
                    "2024-04-10T00:00:00Z",
                ],
                "combined_regime": ["range", "range", "range"],
                "session_regime": ["asia", "asia", "asia"],
                "adjusted_pnl": [-5.0, -4.0, 100.0],
                "actual_taken_best_adjusted_pnl": [10.0, 8.0, 1.0],
                "exit_regret": [15.0, 12.0, 0.0],
            }
        )
        target = entry_ev_exit_capture_target_diagnostics.normalize_trade_frame(
            target,
            name="target",
        )
        prior = entry_ev_exit_capture_target_diagnostics.normalize_trade_frame(
            prior,
            name="prior",
        )
        target = entry_ev_exit_capture_target_diagnostics.add_exit_capture_targets(
            target,
            min_oracle_edge=0.0,
            low_capture_threshold=0.25,
            large_exit_regret_threshold=10.0,
        )
        prior = entry_ev_exit_capture_target_diagnostics.add_exit_capture_targets(
            prior,
            min_oracle_edge=0.0,
            low_capture_threshold=0.25,
            large_exit_regret_threshold=10.0,
        )

        enriched = entry_ev_exit_capture_target_diagnostics.add_prior_exit_capture_risk(
            target,
            prior,
            min_prior_months=1,
            recent_month_count=0,
            support_scale=2.0,
            regret_scale=10.0,
        )

        march = enriched[enriched["month"].eq("2024-03")].iloc[0]
        april = enriched[enriched["month"].eq("2024-04")].iloc[0]
        self.assertEqual(march["prior_exit_trade_count"], 1)
        self.assertEqual(march["prior_exit_capture_failure_count"], 1)
        self.assertEqual(april["prior_exit_trade_count"], 2)
        self.assertEqual(april["prior_exit_capture_failure_count"], 2)

    def test_add_prior_exit_capture_risk_can_condition_on_family(self):
        target = pd.DataFrame(
            {
                "family": ["fam_a", "fam_b"],
                "role": ["fresh", "fresh"],
                "candidate": ["q95", "q95"],
                "month": ["2024-04", "2024-04"],
                "direction": ["short", "short"],
                "entry_decision_timestamp": [
                    "2024-04-10T00:00:00Z",
                    "2024-04-11T00:00:00Z",
                ],
                "combined_regime": ["range", "range"],
                "session_regime": ["asia", "asia"],
                "adjusted_pnl": [1.0, 1.0],
                "actual_taken_best_adjusted_pnl": [5.0, 5.0],
                "exit_regret": [4.0, 4.0],
            }
        )
        prior = pd.DataFrame(
            {
                "family": ["fam_a", "fam_b"],
                "role": ["cal", "cal"],
                "candidate": ["q95", "q95"],
                "month": ["2024-03", "2024-03"],
                "direction": ["short", "short"],
                "entry_decision_timestamp": [
                    "2024-03-10T00:00:00Z",
                    "2024-03-11T00:00:00Z",
                ],
                "combined_regime": ["range", "range"],
                "session_regime": ["asia", "asia"],
                "adjusted_pnl": [-5.0, 4.0],
                "actual_taken_best_adjusted_pnl": [10.0, 10.0],
                "exit_regret": [15.0, 6.0],
            }
        )
        target = entry_ev_exit_capture_target_diagnostics.normalize_trade_frame(
            target,
            name="target",
        )
        prior = entry_ev_exit_capture_target_diagnostics.normalize_trade_frame(
            prior,
            name="prior",
        )
        target = entry_ev_exit_capture_target_diagnostics.add_exit_capture_targets(
            target,
            min_oracle_edge=0.0,
            low_capture_threshold=0.25,
            large_exit_regret_threshold=10.0,
        )
        prior = entry_ev_exit_capture_target_diagnostics.add_exit_capture_targets(
            prior,
            min_oracle_edge=0.0,
            low_capture_threshold=0.25,
            large_exit_regret_threshold=10.0,
        )

        enriched = entry_ev_exit_capture_target_diagnostics.add_prior_exit_capture_risk(
            target,
            prior,
            min_prior_months=1,
            recent_month_count=0,
            support_scale=2.0,
            regret_scale=10.0,
            context_columns=["family", "direction", "combined_regime", "session_regime"],
        )

        fam_a = enriched[enriched["family"].eq("fam_a")].iloc[0]
        fam_b = enriched[enriched["family"].eq("fam_b")].iloc[0]
        self.assertEqual(fam_a["prior_exit_capture_failure_count"], 1)
        self.assertEqual(fam_b["prior_exit_capture_failure_count"], 0)

    def test_summarize_thresholds_reports_precision_and_recall(self):
        frame = pd.DataFrame(
            {
                "role": ["fresh", "fresh", "fresh"],
                "candidate": ["q95", "q95", "q95"],
                "adjusted_pnl": [-5.0, 3.0, -2.0],
                "exit_capture_failure": [True, False, True],
                "same_side_missed_loss": [True, False, True],
                "low_exit_capture": [True, False, True],
                "large_exit_regret": [True, False, False],
                "exit_regret": [15.0, 1.0, 5.0],
                "exit_capture_shortfall": [15.0, 1.0, 7.0],
                "prior_exit_capture_risk_score": [0.8, 0.7, 0.1],
            }
        )

        summary = entry_ev_exit_capture_target_diagnostics.summarize_thresholds(
            frame,
            ["role", "candidate"],
            [0.75],
        )
        row = summary.iloc[0]

        self.assertEqual(row["flagged_trade_count"], 1)
        self.assertEqual(row["flagged_adjusted_pnl"], -5.0)
        self.assertEqual(row["block_delta_if_removed"], 5.0)
        self.assertEqual(row["flagged_exit_capture_failure_count"], 1)
        self.assertEqual(row["flagged_failure_precision"], 1.0)
        self.assertEqual(row["failure_recall"], 0.5)


if __name__ == "__main__":
    unittest.main()
