import importlib.util
import sys
import unittest
from pathlib import Path

import pandas as pd


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "experiments"
    / "entry_ev_prior_context_risk_diagnostics.py"
)
SPEC = importlib.util.spec_from_file_location(
    "entry_ev_prior_context_risk_diagnostics",
    SCRIPT_PATH,
)
entry_ev_prior_context_risk_diagnostics = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = entry_ev_prior_context_risk_diagnostics
SPEC.loader.exec_module(entry_ev_prior_context_risk_diagnostics)


class EntryEvPriorContextRiskDiagnosticsTests(unittest.TestCase):
    def test_add_prior_context_risk_uses_only_prior_months(self):
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
                "combined_regime": ["range_low_vol", "range_low_vol"],
                "session_regime": ["ny_overlap", "ny_overlap"],
                "adjusted_pnl": [-2.0, 7.0],
                "direction_error": [True, False],
            }
        )
        prior = pd.DataFrame(
            {
                "role": ["fresh", "fresh", "fresh"],
                "candidate": ["q95", "q95", "q95"],
                "month": ["2024-02", "2024-03", "2024-04"],
                "direction": ["short", "short", "short"],
                "entry_decision_timestamp": [
                    "2024-02-10T00:00:00Z",
                    "2024-03-10T00:00:00Z",
                    "2024-04-10T00:00:00Z",
                ],
                "combined_regime": ["range_low_vol", "range_low_vol", "range_low_vol"],
                "session_regime": ["ny_overlap", "ny_overlap", "ny_overlap"],
                "adjusted_pnl": [-10.0, -20.0, 100.0],
                "direction_error": [True, True, False],
                "exit_regret": [1.0, 2.0, 3.0],
            }
        )
        target = entry_ev_prior_context_risk_diagnostics.normalize_trade_frame(
            target,
            name="target",
        )
        prior = entry_ev_prior_context_risk_diagnostics.normalize_trade_frame(
            prior,
            name="prior",
        )

        enriched = entry_ev_prior_context_risk_diagnostics.add_prior_context_risk(
            target,
            prior,
            min_prior_months=1,
            recent_month_count=0,
            support_scale=2.0,
            pnl_scale=10.0,
        )

        march = enriched[enriched["month"].eq("2024-03")].iloc[0]
        april = enriched[enriched["month"].eq("2024-04")].iloc[0]
        self.assertEqual(march["prior_trade_count"], 1)
        self.assertEqual(march["prior_total_adjusted_pnl"], -10.0)
        self.assertEqual(april["prior_trade_count"], 2)
        self.assertEqual(april["prior_total_adjusted_pnl"], -30.0)

    def test_dedupe_prior_trades_collapses_candidate_duplicates(self):
        prior = pd.DataFrame(
            {
                "month": ["2024-01", "2024-01", "2024-01"],
                "entry_decision_timestamp": [
                    "2024-01-10T00:00:00Z",
                    "2024-01-10T00:00:00Z",
                    "2024-01-11T00:00:00Z",
                ],
                "direction": ["short", "short", "long"],
                "combined_regime": ["range", "range", "range"],
                "session_regime": ["asia", "asia", "asia"],
                "adjusted_pnl": [-1.0, -1.0, 2.0],
            }
        )
        prior = entry_ev_prior_context_risk_diagnostics.normalize_trade_frame(
            prior,
            name="prior",
        )
        deduped = entry_ev_prior_context_risk_diagnostics.dedupe_prior_trades(prior)

        self.assertEqual(len(deduped), 2)

    def test_summarize_thresholds_reports_block_delta(self):
        frame = pd.DataFrame(
            {
                "role": ["fresh", "fresh", "fresh"],
                "candidate": ["q95", "q95", "q95"],
                "adjusted_pnl": [-5.0, 3.0, -2.0],
                "prior_context_risk_score": [0.8, 0.7, 0.1],
                "prior_trade_count": [2, 2, 0],
                "prior_direction_error_rate": [1.0, 1.0, 0.0],
                "prior_total_adjusted_pnl": [-4.0, -4.0, 0.0],
            }
        )
        summary = entry_ev_prior_context_risk_diagnostics.summarize_thresholds(
            frame,
            ["role", "candidate"],
            [0.75],
        )
        risk_row = summary[summary["flag"].eq("risk_score_gte_0.75")].iloc[0]
        hard_row = summary[
            summary["flag"].eq("direction_error_1_and_prior_pnl_negative")
        ].iloc[0]

        self.assertEqual(risk_row["flagged_trade_count"], 1)
        self.assertEqual(risk_row["flagged_adjusted_pnl"], -5.0)
        self.assertEqual(risk_row["block_delta_if_removed"], 5.0)
        self.assertEqual(hard_row["flagged_trade_count"], 2)
        self.assertEqual(hard_row["flagged_adjusted_pnl"], -2.0)


if __name__ == "__main__":
    unittest.main()
