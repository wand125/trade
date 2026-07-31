from __future__ import annotations

import unittest

import pandas as pd

from scripts.experiments.entry_ev_support_repair_singleton_abstention_diagnostics import (
    prepare_current_additions,
    rule_mask,
    summarize_abstention_rule,
)


class EntryEvSupportRepairSingletonAbstentionDiagnosticsTest(unittest.TestCase):
    def test_rule_flags_only_risky_singleton_720(self) -> None:
        additions = prepare_current_additions(
            pd.DataFrame(
                {
                    "scenario_label": ["s1", "s1", "s1"],
                    "role": ["r", "r", "r"],
                    "family": ["f", "f", "f"],
                    "month": ["2026-01", "2026-02", "2026-03"],
                    "side": ["long", "long", "short"],
                    "direction": ["long", "long", "short"],
                    "decision_timestamp": [
                        "2026-01-01T00:00:00Z",
                        "2026-02-01T00:00:00Z",
                        "2026-03-01T00:00:00Z",
                    ],
                    "entry_timestamp": [
                        "2026-01-01T00:00:00Z",
                        "2026-02-01T00:00:00Z",
                        "2026-03-01T00:00:00Z",
                    ],
                    "exit_timestamp": [
                        "2026-01-01T01:00:00Z",
                        "2026-02-01T01:00:00Z",
                        "2026-03-01T01:00:00Z",
                    ],
                    "current_replay_selected": [True, True, True],
                    "quota_group_is_singleton": [True, True, False],
                    "hv_chosen_horizon_minutes": [720.0, 720.0, 720.0],
                    "ranker_hv_720m_prior_mean_pnl": [-1.0, 2.0, -1.0],
                    "ranker_hv_720m_prior_tail_loss_rate": [0.5, 0.5, 0.5],
                    "actual_pnl_at_hv_chosen_horizon": [-5.0, 6.0, -7.0],
                    "adjusted_pnl": [-5.0, 6.0, -7.0],
                }
            )
        )

        mask = rule_mask(additions, "singleton_720_prior_mean_neg_tail_ge0p35")

        self.assertEqual(mask.tolist(), [True, False, False])

    def test_abstention_recomputes_monthly_metrics_from_kept_additions(self) -> None:
        base_monthly = pd.DataFrame(
            {
                "source": ["s", "s"],
                "role": ["r", "r"],
                "family": ["f", "f"],
                "month": ["2026-01", "2026-02"],
                "total_adjusted_pnl": [1.0, 1.0],
                "trade_count": [1.0, 1.0],
                "long_trade_count": [0.0, 0.0],
                "short_trade_count": [1.0, 1.0],
                "max_side_trade_share": [1.0, 1.0],
                "max_drawdown": [0.0, 0.0],
            }
        )
        base_trades = pd.DataFrame(
            {
                "role": ["r", "r"],
                "family": ["f", "f"],
                "month": ["2026-01", "2026-02"],
                "direction": ["short", "short"],
                "entry_timestamp": [
                    pd.Timestamp("2026-01-01T00:00:00Z"),
                    pd.Timestamp("2026-02-01T00:00:00Z"),
                ],
                "exit_timestamp": [
                    pd.Timestamp("2026-01-01T00:10:00Z"),
                    pd.Timestamp("2026-02-01T00:10:00Z"),
                ],
                "adjusted_pnl": [1.0, 1.0],
            }
        )
        additions = prepare_current_additions(
            pd.DataFrame(
                {
                    "scenario_label": ["s1", "s1"],
                    "role": ["r", "r"],
                    "family": ["f", "f"],
                    "month": ["2026-01", "2026-02"],
                    "side": ["long", "long"],
                    "direction": ["long", "long"],
                    "decision_timestamp": [
                        "2026-01-01T01:00:00Z",
                        "2026-02-01T01:00:00Z",
                    ],
                    "entry_timestamp": [
                        "2026-01-01T01:00:00Z",
                        "2026-02-01T01:00:00Z",
                    ],
                    "exit_timestamp": [
                        "2026-01-01T02:00:00Z",
                        "2026-02-01T02:00:00Z",
                    ],
                    "current_replay_selected": [True, True],
                    "quota_group_is_singleton": [True, True],
                    "hv_chosen_horizon_minutes": [720.0, 720.0],
                    "ranker_hv_720m_prior_mean_pnl": [-1.0, 2.0],
                    "ranker_hv_720m_prior_tail_loss_rate": [0.5, 0.5],
                    "actual_pnl_at_hv_chosen_horizon": [-5.0, 6.0],
                    "adjusted_pnl": [-5.0, 6.0],
                }
            )
        )

        row, flagged, _ = summarize_abstention_rule(
            rule="singleton_720_prior_mean_neg_tail_ge0p35",
            base_monthly=base_monthly,
            base_trades=base_trades,
            additions=additions,
            min_total_pnl=0.0,
            min_role_total_pnl=0.0,
            month_floor=0.0,
            shallow_month_floor=-1.0,
            min_role_trades=1,
            min_month_trades=1,
            max_side_trade_share=1.0,
        )

        self.assertEqual(int(row["abstained_count"]), 1)
        self.assertAlmostEqual(float(row["abstained_actual_sum"]), -5.0)
        self.assertAlmostEqual(float(row["combined_total_pnl"]), 8.0)
        self.assertEqual(len(flagged), 1)


if __name__ == "__main__":
    unittest.main()
