from __future__ import annotations

import unittest

import pandas as pd

from scripts.experiments.entry_ev_support_repair_horizon_replay import (
    add_repair_utility_columns,
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

    def test_select_support_additions_can_sort_by_repair_score(self) -> None:
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
                "role": ["r", "r"],
                "family": ["f", "f"],
                "month": ["2026-01", "2026-01"],
                "side": ["long", "long"],
                "entry_timestamp": [
                    pd.Timestamp("2026-01-01T01:00:00Z"),
                    pd.Timestamp("2026-01-01T03:00:00Z"),
                ],
                "exit_timestamp": [
                    pd.Timestamp("2026-01-01T02:00:00Z"),
                    pd.Timestamp("2026-01-01T04:00:00Z"),
                ],
                "hv_chosen_score": [100.0, 1.0],
                "repair_score": [0.0, 10.0],
                "support_reduction_value": [0, 1],
                "repair_expected_pnl": [0.0, 2.0],
                "actual_pnl_at_hv_chosen_horizon": [1.0, 2.0],
                "adjusted_pnl": [1.0, 2.0],
                "extra_side_needed": [1, 1],
            }
        )

        selected, rejected = select_support_additions(
            base_trades,
            choices,
            selection_mode="repair_score",
        )

        self.assertEqual(len(selected), 1)
        self.assertEqual(float(selected.iloc[0]["repair_score"]), 10.0)
        self.assertEqual(float(selected.iloc[0]["adjusted_pnl"]), 2.0)
        self.assertEqual(rejected.iloc[0]["reject_reason"], "quota_full")

    def test_score_tie_breaker_does_not_use_future_actual_pnl(self) -> None:
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
                "role": ["r", "r"],
                "family": ["f", "f"],
                "month": ["2026-01", "2026-01"],
                "side": ["long", "long"],
                "decision_timestamp": [
                    pd.Timestamp("2026-01-01T01:00:00Z"),
                    pd.Timestamp("2026-01-01T03:00:00Z"),
                ],
                "entry_timestamp": [
                    pd.Timestamp("2026-01-01T01:00:00Z"),
                    pd.Timestamp("2026-01-01T03:00:00Z"),
                ],
                "exit_timestamp": [
                    pd.Timestamp("2026-01-01T02:00:00Z"),
                    pd.Timestamp("2026-01-01T04:00:00Z"),
                ],
                "hv_chosen_score": [10.0, 10.0],
                "actual_pnl_at_hv_chosen_horizon": [-10.0, 10.0],
                "adjusted_pnl": [-10.0, 10.0],
                "extra_side_needed": [1, 1],
            }
        )

        selected, _ = select_support_additions(base_trades, choices)

        self.assertEqual(len(selected), 1)
        self.assertEqual(
            pd.Timestamp(selected.iloc[0]["decision_timestamp"]),
            pd.Timestamp("2026-01-01T01:00:00Z"),
        )
        self.assertEqual(float(selected.iloc[0]["actual_pnl_at_hv_chosen_horizon"]), -10.0)

    def test_repair_score_tie_breaker_does_not_use_future_actual_pnl(self) -> None:
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
                "role": ["r", "r"],
                "family": ["f", "f"],
                "month": ["2026-01", "2026-01"],
                "side": ["long", "long"],
                "decision_timestamp": [
                    pd.Timestamp("2026-01-01T01:00:00Z"),
                    pd.Timestamp("2026-01-01T03:00:00Z"),
                ],
                "entry_timestamp": [
                    pd.Timestamp("2026-01-01T01:00:00Z"),
                    pd.Timestamp("2026-01-01T03:00:00Z"),
                ],
                "exit_timestamp": [
                    pd.Timestamp("2026-01-01T02:00:00Z"),
                    pd.Timestamp("2026-01-01T04:00:00Z"),
                ],
                "hv_chosen_score": [1.0, 1.0],
                "repair_score": [10.0, 10.0],
                "support_reduction_value": [1.0, 1.0],
                "repair_expected_pnl": [2.0, 2.0],
                "actual_pnl_at_hv_chosen_horizon": [-10.0, 10.0],
                "adjusted_pnl": [-10.0, 10.0],
                "extra_side_needed": [1, 1],
            }
        )

        selected, _ = select_support_additions(
            base_trades,
            choices,
            selection_mode="repair_score",
        )

        self.assertEqual(len(selected), 1)
        self.assertEqual(
            pd.Timestamp(selected.iloc[0]["decision_timestamp"]),
            pd.Timestamp("2026-01-01T01:00:00Z"),
        )
        self.assertEqual(float(selected.iloc[0]["actual_pnl_at_hv_chosen_horizon"]), -10.0)

    def test_repair_score_penalizes_harmful_probability_after_support_relief(self) -> None:
        base_monthly = pd.DataFrame(
            {
                "role": ["r"],
                "family": ["f"],
                "month": ["2026-01"],
                "total_adjusted_pnl": [1.0],
                "trade_count": [1],
                "long_trade_count": [0],
                "short_trade_count": [1],
                "max_drawdown": [0.0],
            }
        )
        choices = pd.DataFrame(
            {
                "role": ["r", "r"],
                "family": ["f", "f"],
                "month": ["2026-01", "2026-01"],
                "side": ["long", "long"],
                "hv_chosen_horizon_minutes": [60, 60],
                "hv_chosen_pred_pnl": [3.0, 3.0],
                "hv_chosen_pred_executable_prob": [0.8, 0.8],
                "hv_chosen_pred_tail_loss_prob": [0.1, 0.1],
                "hv_chosen_pred_harmful_overestimate_prob": [0.1, 0.9],
            }
        )

        scored = add_repair_utility_columns(
            base_monthly,
            choices,
            min_month_trades=1,
            max_side_trade_share=0.95,
            repair_support_weight=1.0,
            repair_expected_pnl_weight=1.0,
            repair_tail_penalty_weight=1.0,
            repair_horizon_penalty_weight=0.0,
            repair_harmful_penalty_weight=5.0,
        )

        self.assertGreater(float(scored.iloc[0]["repair_score"]), float(scored.iloc[1]["repair_score"]))
        self.assertLess(float(scored.iloc[0]["repair_harmful_penalty_amount"]), 0.2)

        thresholded = add_repair_utility_columns(
            base_monthly,
            choices,
            min_month_trades=1,
            max_side_trade_share=0.95,
            repair_support_weight=1.0,
            repair_expected_pnl_weight=1.0,
            repair_tail_penalty_weight=1.0,
            repair_horizon_penalty_weight=0.0,
            repair_harmful_penalty_weight=5.0,
            repair_harmful_penalty_threshold=0.5,
        )

        self.assertAlmostEqual(float(thresholded.iloc[0]["repair_harmful_penalty"]), 0.0)
        self.assertAlmostEqual(float(thresholded.iloc[1]["repair_harmful_penalty"]), 0.8)

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

    def test_replay_scenarios_repair_mode_can_filter_negative_actual_candidate(self) -> None:
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
                "row_scope": ["available_candidates", "available_candidates"],
                "prob_threshold": [0.5, 0.5],
                "ev_threshold": [0.0, 0.0],
                "tail_prob_threshold": [0.3, 0.3],
                "require_model_used": [True, True],
                "role": ["r", "r"],
                "family": ["f", "f"],
                "month": ["2026-01", "2026-01"],
                "side": ["long", "long"],
                "entry_timestamp": [
                    pd.Timestamp("2026-01-01T01:00:00Z"),
                    pd.Timestamp("2026-01-01T03:00:00Z"),
                ],
                "exit_timestamp": [
                    pd.Timestamp("2026-01-01T02:00:00Z"),
                    pd.Timestamp("2026-01-01T04:00:00Z"),
                ],
                "hv_chosen_horizon_minutes": [60, 60],
                "hv_chosen_score": [10.0, 2.0],
                "hv_chosen_pred_pnl": [10.0, 2.0],
                "hv_chosen_pred_tail_loss_prob": [0.1, 0.1],
                "actual_pnl_at_hv_chosen_horizon": [-5.0, 3.0],
                "adjusted_pnl": [-5.0, 3.0],
                "extra_side_needed": [1, 1],
            }
        )

        summary, _, additions, rejections = replay_scenarios(
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
            selection_mode="repair_score",
            min_chosen_actual_pnl=0.0,
        )

        self.assertEqual(len(additions), 1)
        self.assertEqual(float(additions.iloc[0]["adjusted_pnl"]), 3.0)
        self.assertEqual(int(summary.iloc[0]["rejected_actual_pnl_floor_count"]), 1)
        self.assertEqual(rejections.iloc[0]["reject_reason"], "actual_pnl_floor")

    def test_row_horizon_grid_expands_before_replay_and_filters_by_horizon_actual(self) -> None:
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
        prediction_row = {
            "role": ["r"],
            "family": ["f"],
            "month": ["2026-01"],
            "decision_timestamp": ["2026-01-01T01:00:00Z"],
            "side": ["long"],
            "needed_side": ["long"],
            "extra_side_needed": [1],
            "row_scope": ["available_candidates"],
            "side_fixed_60m_adjusted_pnl": [-5.0],
            "side_fixed_240m_adjusted_pnl": [4.0],
            "side_fixed_720m_adjusted_pnl": [-8.0],
            "pred_hv_60m_executable_prob": [0.6],
            "pred_hv_60m_pnl": [1.0],
            "pred_hv_60m_tail_loss_prob": [0.1],
            "pred_hv_60m_executable_model_used": [True],
            "pred_hv_60m_pnl_model_used": [True],
            "pred_hv_60m_tail_model_used": [True],
            "ranker_hv_60m_pred_harmful_overestimate_prob": [0.1],
            "pred_hv_240m_executable_prob": [0.6],
            "pred_hv_240m_pnl": [2.0],
            "pred_hv_240m_tail_loss_prob": [0.1],
            "pred_hv_240m_executable_model_used": [True],
            "pred_hv_240m_pnl_model_used": [True],
            "pred_hv_240m_tail_model_used": [True],
            "ranker_hv_240m_pred_harmful_overestimate_prob": [0.2],
            "pred_hv_720m_executable_prob": [0.6],
            "pred_hv_720m_pnl": [10.0],
            "pred_hv_720m_tail_loss_prob": [0.1],
            "pred_hv_720m_executable_model_used": [True],
            "pred_hv_720m_pnl_model_used": [True],
            "pred_hv_720m_tail_model_used": [True],
            "ranker_hv_720m_pred_harmful_overestimate_prob": [0.9],
        }
        path = self.create_temp_csv(pd.DataFrame(prediction_row))

        choices = read_choice_candidates(
            path,
            row_scopes=["available_candidates"],
            target_only=True,
            choice_input_mode="row_horizon_grid",
            prob_thresholds=[0.5],
            ev_thresholds=[0.0],
            tail_prob_thresholds=[0.3],
            require_model_used_options=[True],
        )
        self.assertCountEqual(
            choices["hv_chosen_horizon_minutes"].astype(int).tolist(),
            [60, 240, 720],
        )
        harmful_by_horizon = dict(
            zip(
                choices["hv_chosen_horizon_minutes"].astype(int),
                choices["hv_chosen_pred_harmful_overestimate_prob"].astype(float),
                strict=True,
            )
        )
        self.assertAlmostEqual(harmful_by_horizon[720], 0.9)

        summary, _, additions, rejections = replay_scenarios(
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
            selection_mode="repair_score",
            min_chosen_actual_pnl=0.0,
        )

        self.assertEqual(len(additions), 1)
        self.assertEqual(int(additions.iloc[0]["hv_chosen_horizon_minutes"]), 240)
        self.assertEqual(float(additions.iloc[0]["adjusted_pnl"]), 4.0)
        self.assertEqual(int(summary.iloc[0]["rejected_actual_pnl_floor_count"]), 2)
        self.assertTrue(rejections["reject_reason"].eq("actual_pnl_floor").all())

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
