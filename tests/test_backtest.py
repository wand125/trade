import unittest
from pathlib import Path

import pandas as pd

from trade_data.backtest import (
    BacktestConfig,
    ModelPolicyConfig,
    model_signal_from_predictions,
    normalize_sweep_metrics,
    run_backtest,
    summarize_trades,
    summarize_sweep_frames,
    trades_to_frame,
)


def frame_with_opens(opens, start="2025-01-01 00:00:00+00:00"):
    timestamps = pd.date_range(start=start, periods=len(opens), freq="min")
    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": opens,
            "high": opens,
            "low": opens,
            "close": opens,
        }
    )


class BacktestTests(unittest.TestCase):
    def test_next_open_execution_and_adjusted_pnl(self):
        df = frame_with_opens([100, 101, 105, 106, 107])
        signal = pd.Series([1, 1, 0, 0, 0])
        config = BacktestConfig(
            evaluation_start=df["timestamp"].iloc[0],
            evaluation_end=df["timestamp"].iloc[-1] + pd.Timedelta(minutes=1),
        )

        trades = trades_to_frame(run_backtest(df, signal, config))

        self.assertEqual(len(trades), 1)
        trade = trades.iloc[0]
        self.assertEqual(trade["direction"], "long")
        self.assertEqual(trade["entry_timestamp"], df["timestamp"].iloc[1])
        self.assertEqual(trade["exit_timestamp"], df["timestamp"].iloc[3])
        self.assertEqual(trade["entry_price"], 101)
        self.assertEqual(trade["exit_price"], 106)
        self.assertAlmostEqual(trade["raw_pnl"], 5.0)
        self.assertAlmostEqual(trade["adjusted_pnl"], 4.5)

    def test_forced_exit_after_24_hours(self):
        opens = [100.0] * 1500
        df = frame_with_opens(opens)
        signal = pd.Series([1] * len(df))
        config = BacktestConfig(
            evaluation_start=df["timestamp"].iloc[0],
            evaluation_end=df["timestamp"].iloc[1442],
        )

        trades = trades_to_frame(run_backtest(df, signal, config))

        self.assertEqual(len(trades), 1)
        trade = trades.iloc[0]
        self.assertEqual(trade["exit_reason"], "forced_exit")
        self.assertEqual(trade["holding_minutes"], 1440.0)
        self.assertEqual(
            trade["exit_timestamp"],
            trade["entry_timestamp"] + pd.Timedelta(hours=24),
        )

    def test_opposite_signal_closes_before_next_entry(self):
        df = frame_with_opens([100, 101, 102, 103, 104, 105])
        signal = pd.Series([1, -1, -1, 0, 0, 0])
        config = BacktestConfig(
            evaluation_start=df["timestamp"].iloc[0],
            evaluation_end=df["timestamp"].iloc[-1] + pd.Timedelta(minutes=1),
        )

        trades = trades_to_frame(run_backtest(df, signal, config))

        self.assertEqual(len(trades), 2)
        self.assertEqual(trades.iloc[0]["direction"], "long")
        self.assertEqual(trades.iloc[0]["exit_timestamp"], df["timestamp"].iloc[2])
        self.assertEqual(trades.iloc[1]["direction"], "short")
        self.assertEqual(trades.iloc[1]["entry_timestamp"], df["timestamp"].iloc[3])

    def test_trade_summary_includes_direction_pnl(self):
        df = frame_with_opens([100, 101, 103, 104, 102, 97])
        signal = pd.Series([1, 1, 0, -1, -1, 0])
        config = BacktestConfig(
            evaluation_start=df["timestamp"].iloc[0],
            evaluation_end=df["timestamp"].iloc[-1] + pd.Timedelta(minutes=1),
        )
        trades = trades_to_frame(run_backtest(df, signal, config))

        metrics = summarize_trades(trades, config, "test")

        self.assertEqual(metrics["long_trade_count"], 1)
        self.assertEqual(metrics["short_trade_count"], 1)
        self.assertAlmostEqual(metrics["long_raw_pnl"], 3.0)
        self.assertAlmostEqual(metrics["short_raw_pnl"], 5.0)
        self.assertAlmostEqual(metrics["long_adjusted_pnl"], 2.7)
        self.assertAlmostEqual(metrics["short_adjusted_pnl"], 4.5)
        self.assertAlmostEqual(metrics["long_win_rate"], 1.0)
        self.assertAlmostEqual(metrics["short_win_rate"], 1.0)

    def test_stateless_model_signal_uses_entry_threshold(self):
        df = frame_with_opens([100, 101, 102, 103, 104, 105])
        predictions = pd.DataFrame(
            {
                "decision_timestamp": df["timestamp"],
                "pred_long_best_adjusted_pnl": [0, 11, 8, 7, -1, 20],
                "pred_short_best_adjusted_pnl": [0, 2, 3, 4, 1, 1],
            }
        )
        config = ModelPolicyConfig(
            predictions=Path("unused"),
            policy="stateless_ev",
            entry_threshold=10,
        )

        signal = model_signal_from_predictions(df, predictions, config)

        self.assertEqual(signal.tolist(), [0, 1, 0, 0, 0, 1])

    def test_model_signal_can_penalize_predicted_adverse_move(self):
        df = frame_with_opens([100, 101, 102])
        predictions = pd.DataFrame(
            {
                "decision_timestamp": df["timestamp"],
                "pred_long_best_adjusted_pnl": [20.0, 20.0, 20.0],
                "pred_short_best_adjusted_pnl": [18.0, 18.0, 18.0],
                "pred_long_max_adverse_pnl": [-30.0, -30.0, -30.0],
                "pred_short_max_adverse_pnl": [-1.0, -1.0, -1.0],
            }
        )
        config = ModelPolicyConfig(
            predictions=Path("unused"),
            policy="stateless_ev",
            entry_threshold=10,
            risk_penalty=1.0,
        )

        signal = model_signal_from_predictions(df, predictions, config)

        self.assertEqual(signal.tolist(), [-1, -1, -1])

    def test_model_signal_can_filter_low_quality_entries(self):
        df = frame_with_opens([100, 101, 102])
        predictions = pd.DataFrame(
            {
                "decision_timestamp": df["timestamp"],
                "pred_long_best_adjusted_pnl": [20.0, 20.0, 20.0],
                "pred_short_best_adjusted_pnl": [1.0, 1.0, 1.0],
                "pred_long_wait_regret": [5.0, 1.0, 1.0],
                "pred_short_wait_regret": [0.0, 0.0, 0.0],
                "pred_long_entry_local_rank": [0.2, 0.8, 0.8],
                "pred_short_entry_local_rank": [1.0, 1.0, 1.0],
                "pred_long_profit_barrier_hit": [1, 1, 0],
                "pred_short_profit_barrier_hit": [1, 1, 1],
            }
        )
        config = ModelPolicyConfig(
            predictions=Path("unused"),
            policy="stateless_ev",
            entry_threshold=10,
            max_wait_regret=2.0,
            min_entry_rank=0.5,
            require_profit_barrier=True,
        )

        signal = model_signal_from_predictions(df, predictions, config)

        self.assertEqual(signal.tolist(), [0, 1, 0])

    def test_stateful_model_signal_holds_until_exit_threshold(self):
        df = frame_with_opens([100, 101, 102, 103, 104, 105])
        predictions = pd.DataFrame(
            {
                "decision_timestamp": df["timestamp"],
                "pred_long_best_adjusted_pnl": [0, 11, 8, 7, -1, 20],
                "pred_short_best_adjusted_pnl": [0, 2, 3, 4, 1, 1],
            }
        )
        config = ModelPolicyConfig(
            predictions=Path("unused"),
            policy="stateful_ev",
            entry_threshold=10,
            exit_threshold=0,
        )

        signal = model_signal_from_predictions(df, predictions, config)

        self.assertEqual(signal.tolist(), [0, 1, 1, 1, 0, 1])

    def test_timed_model_signal_exits_after_predicted_holding_time(self):
        df = frame_with_opens([100, 101, 102, 103, 104, 105], start="2025-01-01 00:00:00+00:00")
        predictions = pd.DataFrame(
            {
                "decision_timestamp": df["timestamp"],
                "pred_long_best_adjusted_pnl": [20, 20, 20, 20, 20, 20],
                "pred_short_best_adjusted_pnl": [1, 1, 1, 1, 1, 1],
                "pred_long_best_holding_minutes": [2, 2, 2, 2, 2, 2],
                "pred_short_best_holding_minutes": [2, 2, 2, 2, 2, 2],
            }
        )
        config = ModelPolicyConfig(
            predictions=Path("unused"),
            policy="timed_ev",
            entry_threshold=10,
            exit_threshold=0,
        )

        signal = model_signal_from_predictions(df, predictions, config)

        self.assertEqual(signal.tolist(), [1, 1, 1, 0, 1, 1])

    def test_sweep_metrics_normalization_adds_missing_risk_penalty(self):
        frame = pd.DataFrame(
            {
                "policy": ["timed_ev"],
                "entry_threshold": [15],
                "exit_threshold": [0],
                "side_margin": [5],
                "total_adjusted_pnl": [10.0],
                "total_raw_pnl": [12.0],
                "trade_count": [4],
                "win_rate": [0.5],
                "max_drawdown": [3.0],
                "forced_exit_count": [1],
            }
        )

        normalized = normalize_sweep_metrics(frame, "fold_a")

        self.assertEqual(normalized["risk_penalty"].tolist(), [0.0])
        self.assertEqual(normalized["max_wait_regret"].tolist(), [float("inf")])
        self.assertEqual(normalized["min_entry_rank"].tolist(), [0.0])
        self.assertEqual(normalized["require_profit_barrier"].tolist(), [False])
        self.assertEqual(normalized["sweep_source"].tolist(), ["fold_a"])
        self.assertAlmostEqual(normalized["forced_exit_rate"].iloc[0], 0.25)

    def test_sweep_summary_selects_mean_pnl_under_fold_constraints(self):
        fold_a = pd.DataFrame(
            {
                "policy": ["timed_ev", "timed_ev", "stateful_ev"],
                "entry_threshold": [5, 15, 10],
                "exit_threshold": [0, 0, 5],
                "side_margin": [5, 5, 0],
                "risk_penalty": [0, 0, 0.1],
                "require_profit_barrier": ["False", "False", "True"],
                "total_adjusted_pnl": [120.0, 110.0, 200.0],
                "total_raw_pnl": [130.0, 120.0, 220.0],
                "trade_count": [40, 35, 40],
                "win_rate": [0.55, 0.6, 0.7],
                "max_drawdown": [50.0, 40.0, 30.0],
                "forced_exit_rate": [0.0, 0.0, 0.1],
                "forced_exit_count": [0, 0, 4],
            }
        )
        fold_b = pd.DataFrame(
            {
                "policy": ["timed_ev", "timed_ev", "stateful_ev"],
                "entry_threshold": [5, 15, 10],
                "exit_threshold": [0, 0, 5],
                "side_margin": [5, 5, 0],
                "risk_penalty": [0, 0, 0.1],
                "require_profit_barrier": ["False", "False", "True"],
                "total_adjusted_pnl": [100.0, 140.0, 210.0],
                "total_raw_pnl": [110.0, 150.0, 230.0],
                "trade_count": [42, 36, 44],
                "win_rate": [0.52, 0.62, 0.71],
                "max_drawdown": [55.0, 45.0, 35.0],
                "forced_exit_rate": [0.0, 0.0, 0.1],
                "forced_exit_count": [0, 0, 4],
            }
        )

        summary = summarize_sweep_frames(
            [fold_a, fold_b],
            min_folds=2,
            min_trades_per_fold=30,
            max_forced_exit_rate=0.0,
            max_drawdown=100.0,
            min_adjusted_pnl_per_fold=0.0,
            sort_by="mean_pnl",
        )

        top = summary.iloc[0]
        self.assertEqual(top["policy"], "timed_ev")
        self.assertEqual(top["entry_threshold"], 15)
        self.assertTrue(bool(top["eligible"]))
        stateful = summary[summary["policy"] == "stateful_ev"].iloc[0]
        self.assertFalse(bool(stateful["eligible"]))


if __name__ == "__main__":
    unittest.main()
