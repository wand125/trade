from __future__ import annotations

import unittest

import pandas as pd

from scripts.experiments.entry_ev_support_repair_horizon_replay import (
    read_choice_candidates,
    replay_scenarios,
    select_support_additions,
    update_monthly_metrics,
)


class EntryEvSupportRepairHorizonReplayTest(unittest.TestCase):
    def test_select_support_additions_rejects_overlap_and_respects_quota(self) -> None:
        base_trades = pd.DataFrame(
            {
                "role": ["r"],
                "family": ["f"],
                "month": ["2026-01"],
                "direction": ["short"],
                "entry_timestamp": [pd.Timestamp("2026-01-01T00:00:00Z")],
                "exit_timestamp": [pd.Timestamp("2026-01-01T01:00:00Z")],
                "adjusted_pnl": [1.0],
                "repair_source": ["base"],
            }
        )
        choices = pd.DataFrame(
            {
                "role": ["r", "r", "r"],
                "family": ["f", "f", "f"],
                "month": ["2026-01", "2026-01", "2026-01"],
                "side": ["long", "long", "long"],
                "entry_timestamp": [
                    pd.Timestamp("2026-01-01T00:30:00Z"),
                    pd.Timestamp("2026-01-01T01:10:00Z"),
                    pd.Timestamp("2026-01-01T03:00:00Z"),
                ],
                "exit_timestamp": [
                    pd.Timestamp("2026-01-01T02:00:00Z"),
                    pd.Timestamp("2026-01-01T02:10:00Z"),
                    pd.Timestamp("2026-01-01T04:00:00Z"),
                ],
                "hv_chosen_score": [10.0, 9.0, 8.0],
                "actual_pnl_at_hv_chosen_horizon": [5.0, 4.0, 3.0],
                "adjusted_pnl": [5.0, 4.0, 3.0],
                "extra_side_needed": [1, 1, 1],
            }
        )

        selected, rejected = select_support_additions(base_trades, choices)

        self.assertEqual(len(selected), 1)
        self.assertEqual(float(selected.iloc[0]["adjusted_pnl"]), 4.0)
        self.assertCountEqual(rejected["reject_reason"].tolist(), ["overlap", "quota_full"])

    def test_update_monthly_metrics_adds_side_counts_and_pnl(self) -> None:
        base_monthly = pd.DataFrame(
            {
                "source": ["s"],
                "role": ["r"],
                "family": ["f"],
                "variant": ["v"],
                "candidate": ["c"],
                "entry_block_rule": ["rule"],
                "month": ["2026-01"],
                "total_adjusted_pnl": [1.0],
                "trade_count": [1],
                "long_trade_count": [0],
                "short_trade_count": [1],
                "max_side_trade_share": [1.0],
                "max_drawdown": [0.0],
            }
        )
        base_trades = pd.DataFrame(
            {
                "role": ["r"],
                "family": ["f"],
                "month": ["2026-01"],
                "direction": ["short"],
                "entry_timestamp": [pd.Timestamp("2026-01-01T00:00:00Z")],
                "exit_timestamp": [pd.Timestamp("2026-01-01T00:10:00Z")],
                "adjusted_pnl": [1.0],
                "repair_source": ["base"],
            }
        )
        additions = pd.DataFrame(
            {
                "role": ["r"],
                "family": ["f"],
                "month": ["2026-01"],
                "direction": ["long"],
                "side": ["long"],
                "entry_timestamp": [pd.Timestamp("2026-01-01T01:00:00Z")],
                "exit_timestamp": [pd.Timestamp("2026-01-01T02:00:00Z")],
                "adjusted_pnl": [4.0],
            }
        )

        updated = update_monthly_metrics(
            base_monthly,
            base_trades,
            additions,
            scenario={"scenario_label": "s1"},
        ).iloc[0]

        self.assertEqual(float(updated["total_adjusted_pnl"]), 5.0)
        self.assertEqual(float(updated["trade_count"]), 2.0)
        self.assertEqual(float(updated["long_trade_count"]), 1.0)
        self.assertEqual(float(updated["short_trade_count"]), 1.0)
        self.assertEqual(float(updated["max_side_trade_share"]), 0.5)

    def test_replay_scenarios_can_remove_side_share_blocker(self) -> None:
        base_monthly = pd.DataFrame(
            {
                "source": ["s"],
                "role": ["r"],
                "family": ["f"],
                "variant": ["v"],
                "candidate": ["c"],
                "entry_block_rule": ["rule"],
                "month": ["2026-01"],
                "total_adjusted_pnl": [1.0],
                "trade_count": [1],
                "long_trade_count": [0],
                "short_trade_count": [1],
                "max_side_trade_share": [1.0],
                "max_drawdown": [0.0],
            }
        )
        base_trades = pd.DataFrame(
            {
                "role": ["r"],
                "family": ["f"],
                "month": ["2026-01"],
                "direction": ["short"],
                "entry_timestamp": [pd.Timestamp("2026-01-01T00:00:00Z")],
                "exit_timestamp": [pd.Timestamp("2026-01-01T00:10:00Z")],
                "adjusted_pnl": [1.0],
                "repair_source": ["base"],
            }
        )
        choices = pd.DataFrame(
            {
                "row_scope": ["available_candidates"],
                "prob_threshold": [0.6],
                "ev_threshold": [2.0],
                "tail_prob_threshold": [0.3],
                "require_model_used": [True],
                "role": ["r"],
                "family": ["f"],
                "month": ["2026-01"],
                "side": ["long"],
                "entry_timestamp": [pd.Timestamp("2026-01-01T01:00:00Z")],
                "exit_timestamp": [pd.Timestamp("2026-01-01T02:00:00Z")],
                "hv_chosen_horizon_minutes": [60],
                "hv_chosen_score": [3.0],
                "actual_pnl_at_hv_chosen_horizon": [4.0],
                "adjusted_pnl": [4.0],
                "extra_side_needed": [1],
            }
        )

        summary, _, additions, _ = replay_scenarios(
            base_monthly,
            base_trades,
            choices,
            min_total_pnl=0.0,
            min_role_total_pnl=0.0,
            month_floor=0.0,
            shallow_month_floor=-1.0,
            min_role_trades=1,
            min_month_trades=1,
            max_side_trade_share=0.95,
            cap_to_extra_side_needed=True,
            overlap_key_columns=["role"],
        )

        self.assertEqual(len(additions), 1)
        self.assertTrue(bool(summary.iloc[0]["selector_pass"]))
        self.assertEqual(summary.iloc[0]["blockers"], "")
        self.assertEqual(int(summary.iloc[0]["remaining_extra_trades_needed"]), 0)

    def test_read_choice_candidates_filters_unchosen_and_non_target_rows(self) -> None:
        frame = pd.DataFrame(
            {
                "role": ["r", "r", "r"],
                "family": ["f", "f", "f"],
                "month": ["2026-01", "2026-01", "2026-01"],
                "decision_timestamp": [
                    "2026-01-01T00:00:00Z",
                    "2026-01-01T01:00:00Z",
                    "2026-01-01T02:00:00Z",
                ],
                "side": ["long", "short", "long"],
                "needed_side": ["long", "long", "long"],
                "extra_side_needed": [1, 1, 1],
                "hv_chosen_horizon_minutes": [60, 60, 0],
                "hv_chosen_score": [2.0, 3.0, 4.0],
                "actual_pnl_at_hv_chosen_horizon": [1.0, 2.0, 3.0],
                "row_scope": ["available_candidates"] * 3,
                "prob_threshold": [0.6] * 3,
                "ev_threshold": [2.0] * 3,
                "tail_prob_threshold": [0.3] * 3,
                "require_model_used": [True] * 3,
            }
        )

        path = self.create_temp_csv(frame)
        output = read_choice_candidates(path, row_scopes=["available_candidates"], target_only=True)

        self.assertEqual(len(output), 1)
        self.assertEqual(output.iloc[0]["side"], "long")

    def create_temp_csv(self, frame: pd.DataFrame):
        import tempfile
        from pathlib import Path

        temp = tempfile.NamedTemporaryFile(suffix=".csv", delete=False)
        temp.close()
        path = Path(temp.name)
        frame.to_csv(path, index=False)
        self.addCleanup(path.unlink)
        return path


if __name__ == "__main__":
    unittest.main()
