import importlib.util
import sys
import unittest
from pathlib import Path

import pandas as pd


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "experiments"
    / "entry_ev_quantile_policy_backtest.py"
)
SPEC = importlib.util.spec_from_file_location(
    "entry_ev_quantile_policy_backtest",
    SCRIPT_PATH,
)
entry_ev_quantile_policy_backtest = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = entry_ev_quantile_policy_backtest
SPEC.loader.exec_module(entry_ev_quantile_policy_backtest)


class EntryEvQuantilePolicyBacktestTests(unittest.TestCase):
    def test_policy_candidate_from_name_parses_quantiles(self):
        candidate = entry_ev_quantile_policy_backtest.policy_candidate_from_name(
            "q99_sg95_rank90_side_regime_session_month"
        )

        self.assertEqual(candidate.name, "q99_sg95_rank90_side_regime_session_month")
        self.assertEqual(candidate.scope, "side_regime_session_month")
        self.assertEqual(candidate.score_quantile, 0.99)
        self.assertEqual(candidate.side_gap_quantile, 0.95)
        self.assertEqual(candidate.rank_quantile, 0.90)
        self.assertEqual(candidate.entry_threshold, 0.0)

    def test_absolute_candidate_preserves_existing_gate(self):
        candidate = entry_ev_quantile_policy_backtest.policy_candidate_from_name(
            "abs_entry10_short9_side5_rank0"
        )

        self.assertEqual(candidate.entry_threshold, 10.0)
        self.assertEqual(candidate.short_entry_threshold_offset, 9.0)
        self.assertEqual(candidate.side_margin, 5.0)
        self.assertEqual(candidate.score_quantile, 0.0)

    def test_policy_candidate_accepts_one_word_scope(self):
        candidate = entry_ev_quantile_policy_backtest.policy_candidate_from_name(
            "q99_sg95_rank90_month"
        )

        self.assertEqual(candidate.scope, "month")
        self.assertEqual(candidate.score_quantile, 0.99)

    def test_parse_role_months_maps_family_month_pairs(self):
        role_lookup = entry_ev_quantile_policy_backtest.parse_role_months(
            ["validation=fresh2024:2024-03,2024-04"]
        )

        self.assertEqual(role_lookup[("fresh2024", "2024-03")], "validation")
        self.assertEqual(role_lookup[("fresh2024", "2024-04")], "validation")

    def test_build_model_policy_config_wires_quantile_columns(self):
        candidate = entry_ev_quantile_policy_backtest.policy_candidate_from_name(
            "q95_sg95_rank90_side_month"
        )

        config = entry_ev_quantile_policy_backtest.build_model_policy_config(
            prediction_path=Path("predictions.parquet"),
            candidate=candidate,
            score_kind="calibrated",
            long_column="long_ev",
            short_column="short_ev",
            long_holding_column="long_hold",
            short_holding_column="short_hold",
            min_valid_predicted_hold_minutes=30.0,
            max_predicted_hold_minutes=260.0,
        )

        self.assertEqual(config.entry_score_quantile_column, "pred_calibrated_selected_score_pct_side_month")
        self.assertEqual(config.side_gap_quantile_column, "pred_calibrated_side_gap_pct_side_month")
        self.assertEqual(
            config.entry_rank_quantile_column,
            "pred_calibrated_selected_entry_rank_pct_side_month",
        )
        self.assertEqual(config.min_valid_predicted_hold_minutes, 30.0)
        self.assertEqual(config.max_predicted_hold_minutes, 260.0)

    def test_summarize_by_group_tracks_worst_month_and_side_share(self):
        monthly = pd.DataFrame(
            {
                "family": ["a", "a", "a"],
                "candidate": ["x", "x", "y"],
                "month": ["2024-01", "2024-02", "2024-01"],
                "total_adjusted_pnl": [10.0, -3.0, 5.0],
                "trade_count": [2, 1, 0],
                "max_drawdown": [4.0, 3.0, 0.0],
                "long_trade_count": [1, 0, 0],
                "short_trade_count": [1, 1, 0],
                "signal_long_count": [10, 0, 0],
                "signal_short_count": [5, 7, 0],
            }
        )

        summary = entry_ev_quantile_policy_backtest.summarize_by_group(
            monthly,
            ["family", "candidate"],
        )
        x_row = summary[summary["candidate"] == "x"].iloc[0]

        self.assertEqual(x_row["month_count"], 2)
        self.assertEqual(x_row["active_months"], 2)
        self.assertEqual(x_row["total_adjusted_pnl_sum"], 7.0)
        self.assertEqual(x_row["total_adjusted_pnl_min"], -3.0)
        self.assertEqual(x_row["trade_count_sum"], 3)
        self.assertAlmostEqual(x_row["short_trade_share"], 2 / 3)


if __name__ == "__main__":
    unittest.main()
