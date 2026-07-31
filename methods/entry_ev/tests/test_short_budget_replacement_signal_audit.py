import importlib.util
import sys
import unittest
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "experiments" / "short_budget_replacement_signal_audit.py"
SPEC = importlib.util.spec_from_file_location(
    "short_budget_replacement_signal_audit",
    SCRIPT,
)
short_budget_replacement_signal_audit = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = short_budget_replacement_signal_audit
SPEC.loader.exec_module(short_budget_replacement_signal_audit)


class ShortBudgetReplacementSignalAuditTest(unittest.TestCase):
    def _replacement_rows(self):
        return pd.DataFrame(
            [
                {
                    "candidate": "gap5",
                    "window": "late",
                    "month": "2025-03",
                    "direction": "short",
                    "delta_status": "only_candidate",
                    "candidate_adjusted_pnl": -10.0,
                    "combined_regime": "range_low_vol",
                    "session_regime": "asia",
                    "is_loss": True,
                },
                {
                    "candidate": "gap5",
                    "window": "late",
                    "month": "2025-03",
                    "direction": "short",
                    "delta_status": "only_candidate",
                    "candidate_adjusted_pnl": 4.0,
                    "combined_regime": "up_low_vol",
                    "session_regime": "london",
                    "is_loss": False,
                },
            ]
        )

    def _alerts(self):
        return pd.DataFrame(
            [
                {
                    "month": "2025-02",
                    "combined_regime": "range_low_vol",
                    "session_regime": "asia",
                    "side": "short",
                    "is_alert": True,
                    "loss_bias_score": 12.0,
                    "total_adjusted_pnl": -20.0,
                    "side_share_bias": 0.4,
                },
                {
                    "month": "2025-03",
                    "combined_regime": "up_low_vol",
                    "session_regime": "london",
                    "side": "short",
                    "is_alert": True,
                    "loss_bias_score": 99.0,
                    "total_adjusted_pnl": -99.0,
                    "side_share_bias": 0.9,
                },
            ]
        )

    def _prediction_groups(self):
        return pd.DataFrame(
            [
                {
                    "dataset_month": "2025-02",
                    "combined_regime": "range_low_vol",
                    "session_regime": "asia",
                    "prediction_rows": 100,
                    "pred_ev_short_share": 0.8,
                    "actual_label_short_share": 0.3,
                    "pred_short_minus_actual_label_short_share": 0.5,
                    "pred_ev_matches_nonflat_label_rate": 0.4,
                    "pred_side_score_mean": -2.0,
                },
                {
                    "dataset_month": "2025-02",
                    "combined_regime": "up_low_vol",
                    "session_regime": "london",
                    "prediction_rows": 80,
                    "pred_ev_short_share": 0.2,
                    "actual_label_short_share": 0.4,
                    "pred_short_minus_actual_label_short_share": -0.2,
                    "pred_ev_matches_nonflat_label_rate": 0.6,
                    "pred_side_score_mean": 1.0,
                },
            ]
        )

    def _selected_groups(self):
        return pd.DataFrame(
            [
                {
                    "month": "2025-02",
                    "combined_regime": "range_low_vol",
                    "session_regime": "asia",
                    "direction_side_name": "short",
                    "trade_count": 3,
                    "total_adjusted_pnl": -12.0,
                    "ev_overestimate_vs_realized_mean": 26.0,
                },
                {
                    "month": "2025-02",
                    "combined_regime": "up_low_vol",
                    "session_regime": "london",
                    "direction_side_name": "short",
                    "trade_count": 2,
                    "total_adjusted_pnl": 5.0,
                    "ev_overestimate_vs_realized_mean": 10.0,
                },
            ]
        )

    def test_enrichment_uses_prior_months_only(self):
        enriched = short_budget_replacement_signal_audit.enrich_replacement_rows(
            self._replacement_rows(),
            side_drift_alerts=self._alerts(),
            prediction_groups=self._prediction_groups(),
            selected_groups=self._selected_groups(),
            recent_month_count=1,
        )

        range_row = enriched[enriched["combined_regime"].eq("range_low_vol")].iloc[0]
        self.assertEqual(int(range_row["prior_alert_count"]), 1)
        self.assertTrue(bool(range_row["prior_alert_or_pred_bias"]))
        self.assertEqual(float(range_row["prior_short_pnl_sum"]), -12.0)

        up_row = enriched[enriched["combined_regime"].eq("up_low_vol")].iloc[0]
        self.assertEqual(int(up_row["prior_alert_count"]), 0)
        self.assertEqual(int(up_row["same_month_alert_count"]), 1)
        self.assertFalse(bool(up_row["prior_alert_or_pred_bias"]))

    def test_condition_summary_reports_covered_and_uncovered_pnl(self):
        enriched = short_budget_replacement_signal_audit.enrich_replacement_rows(
            self._replacement_rows(),
            side_drift_alerts=self._alerts(),
            prediction_groups=self._prediction_groups(),
            selected_groups=self._selected_groups(),
            recent_month_count=1,
        )
        summary = short_budget_replacement_signal_audit.condition_summary(enriched)
        alert_or_bias = summary[summary["condition"].eq("prior_alert_or_pred_bias")].iloc[0]

        self.assertEqual(int(alert_or_bias["covered_rows"]), 1)
        self.assertEqual(float(alert_or_bias["covered_pnl"]), -10.0)
        self.assertEqual(int(alert_or_bias["uncovered_rows"]), 1)
        self.assertEqual(float(alert_or_bias["uncovered_pnl"]), 4.0)


if __name__ == "__main__":
    unittest.main()
