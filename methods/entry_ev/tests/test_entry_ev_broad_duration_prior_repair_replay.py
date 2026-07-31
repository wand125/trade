from __future__ import annotations

import unittest

import pandas as pd

from scripts.experiments.entry_ev_broad_duration_prior_repair_replay import (
    add_duration_prior_columns,
    apply_duration_risk_weight,
    parse_context_specs,
)
from scripts.experiments.entry_ev_support_repair_horizon_replay import (
    add_repair_utility_columns,
)


class EntryEvBroadDurationPriorRepairReplayTest(unittest.TestCase):
    def test_add_duration_prior_columns_uses_only_prior_context(self) -> None:
        choices = pd.DataFrame(
            {
                "month": ["2026-02", "2026-02"],
                "side": ["long", "long"],
                "combined_regime": ["down_low_vol", "down_low_vol"],
                "session_regime": ["asia", "asia"],
                "near_miss_bucket": ["one_failed", "one_failed"],
                "hv_chosen_horizon_minutes": [60.0, 720.0],
            }
        )
        train = pd.DataFrame(
            {
                "month": ["2026-01", "2026-01", "2026-02"],
                "side": ["long", "long", "long"],
                "combined_regime": ["down_low_vol", "down_low_vol", "down_low_vol"],
                "session_regime": ["asia", "asia", "asia"],
                "near_miss_bucket": ["one_failed", "one_failed", "one_failed"],
                "side_fixed_60m_adjusted_pnl": [2.0, 3.0, 100.0],
                "side_fixed_720m_adjusted_pnl": [-10.0, -12.0, 100.0],
            }
        )

        result = add_duration_prior_columns(
            choices,
            train,
            context_specs=parse_context_specs("side,combined_regime,session_regime;global"),
            min_prior_rows=1,
            min_prior_months=1,
            shrinkage_count=0.0,
            tail_loss_threshold=-5.0,
            negative_pnl_weight=1.0,
            underperform_weight=1.0,
            loss_rate_weight=0.0,
            tail_loss_rate_weight=0.0,
        )

        row_720 = result[result["hv_chosen_horizon_minutes"].eq(720.0)].iloc[0]
        self.assertEqual(row_720["duration_prior_count"], 2)
        self.assertEqual(row_720["duration_prior_months"], 1)
        self.assertAlmostEqual(row_720["duration_prior_mean_pnl"], -11.0)
        self.assertAlmostEqual(row_720["duration_prior_delta_vs_60_mean"], -13.5)
        self.assertAlmostEqual(row_720["repair_duration_risk_score"], 24.5)

    def test_apply_duration_risk_weight_is_subtracted_from_repair_score(self) -> None:
        choices = pd.DataFrame(
            {
                "role": ["r"],
                "month": ["2026-01"],
                "side": ["long"],
                "hv_chosen_pred_pnl": [10.0],
                "hv_chosen_pred_tail_loss_prob": [1.0],
                "hv_chosen_horizon_minutes": [720.0],
                "repair_duration_risk_score": [8.0],
            }
        )
        base_monthly = pd.DataFrame(
            {
                "role": ["r"],
                "month": ["2026-01"],
                "long_trade_count": [0],
                "short_trade_count": [0],
                "trade_count": [0],
                "total_adjusted_pnl": [0.0],
            }
        )

        weighted = apply_duration_risk_weight(choices, risk_weight=0.25)
        scored = add_repair_utility_columns(
            base_monthly,
            weighted,
            min_month_trades=1,
            max_side_trade_share=0.95,
            repair_support_weight=1.0,
            repair_expected_pnl_weight=1.0,
            repair_tail_penalty_weight=1.0,
            repair_horizon_penalty_weight=0.0,
        )

        self.assertAlmostEqual(scored.iloc[0]["repair_duration_risk_penalty_amount"], 2.0)
        self.assertAlmostEqual(scored.iloc[0]["repair_score"], 8.0)


if __name__ == "__main__":
    unittest.main()
