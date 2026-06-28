import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd

from trade_data.backtest import (
    BacktestConfig,
    ModelPolicyConfig,
    apply_execution_cost,
    combined_regime_diagnostics,
    direction_session_diagnostics,
    enrich_trades_with_predictions,
    fixed_horizon_scores,
    model_signal_from_predictions,
    normalize_sweep_metrics,
    plateau_support_counts,
    parse_optional_rule_sets,
    prepare_analysis_predictions,
    profit_barrier_calibration_diagnostics,
    profit_barrier_diagnostics,
    read_holdout_run_frame,
    read_model_trade_exposure_frame,
    read_model_trade_delta_frames,
    run_backtest,
    run_model_policy,
    summarize_holdout_audit,
    summarize_candidate_selection,
    summarize_candidate_selection_jackknife,
    summarize_trades,
    summarize_sweep_frames,
    trade_analysis_summary,
    trade_delta_group_summary,
    trade_exposure_group_summary,
    trade_failure_flags,
    trade_group_summary,
    trades_to_frame,
    SWEEP_KEY_COLUMNS,
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
    def test_parse_optional_rule_sets_supports_empty_and_multiple_sets(self):
        rule_sets = parse_optional_rule_sets(
            "none;long:session_regime=ny_late;long:combined_regime=range_low_vol,"
            "long:session_regime=ny_late;long:session_regime=ny_late",
        )

        self.assertEqual(
            rule_sets,
            [
                (),
                ("long:session_regime=ny_late",),
                ("long:combined_regime=range_low_vol", "long:session_regime=ny_late"),
            ],
        )

    def test_parse_optional_rule_sets_uses_fallback_for_existing_single_rule_arg(self):
        fallback = ("long:session_regime=ny_late",)

        self.assertEqual(parse_optional_rule_sets(None, fallback), [fallback])

    def test_run_model_policy_filters_preloaded_predictions_by_candidate_requirements(self):
        df = frame_with_opens([100, 101, 102, 103])
        predictions = pd.DataFrame(
            {
                "decision_timestamp": [df["timestamp"].iloc[0]],
                "pred_long_best_adjusted_pnl": [20.0],
                "pred_short_best_adjusted_pnl": [0.0],
                "pred_long_best_holding_minutes": [float("nan")],
                "pred_short_best_holding_minutes": [60.0],
            }
        )
        backtest_config = BacktestConfig(
            evaluation_start=df["timestamp"].iloc[0],
            evaluation_end=df["timestamp"].iloc[-1] + pd.Timedelta(minutes=1),
        )
        policy_config = ModelPolicyConfig(
            predictions=Path("preloaded.parquet"),
            policy="timed_ev",
            entry_threshold=10.0,
            side_margin=0.0,
        )

        metrics, trades, _, signal = run_model_policy(
            df,
            backtest_config,
            policy_config,
            predictions=predictions,
        )

        self.assertEqual(metrics["trade_count"], 0)
        self.assertTrue(trades.empty)
        self.assertEqual(signal.tolist(), [0, 0, 0, 0])

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
        self.assertAlmostEqual(trade["adjusted_pnl"], 5.0)

    def test_execution_cost_is_adverse_for_entry_and_exit(self):
        config = BacktestConfig(
            evaluation_start=pd.Timestamp("2025-01-01", tz="UTC"),
            evaluation_end=pd.Timestamp("2025-01-02", tz="UTC"),
            spread_points=0.2,
            slippage_points=0.1,
        )

        self.assertAlmostEqual(apply_execution_cost(100.0, 1, True, config), 100.2)
        self.assertAlmostEqual(apply_execution_cost(100.0, 1, False, config), 99.8)
        self.assertAlmostEqual(apply_execution_cost(100.0, -1, True, config), 99.8)
        self.assertAlmostEqual(apply_execution_cost(100.0, -1, False, config), 100.2)

    def test_backtest_applies_spread_slippage_and_execution_delay(self):
        df = frame_with_opens([100, 101, 105, 106, 107, 108])
        signal = pd.Series([1, 1, 0, 0, 0, 0])
        config = BacktestConfig(
            evaluation_start=df["timestamp"].iloc[0],
            evaluation_end=df["timestamp"].iloc[-1] + pd.Timedelta(minutes=1),
            spread_points=0.2,
            slippage_points=0.1,
            execution_delay_bars=1,
        )

        trades = trades_to_frame(run_backtest(df, signal, config))

        self.assertEqual(len(trades), 1)
        trade = trades.iloc[0]
        self.assertEqual(trade["entry_timestamp"], df["timestamp"].iloc[2])
        self.assertEqual(trade["exit_timestamp"], df["timestamp"].iloc[4])
        self.assertAlmostEqual(trade["entry_price"], 105.2)
        self.assertAlmostEqual(trade["exit_price"], 106.8)
        self.assertAlmostEqual(trade["raw_pnl"], 1.6)

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
        self.assertAlmostEqual(metrics["long_trade_share"], 0.5)
        self.assertAlmostEqual(metrics["short_trade_share"], 0.5)
        self.assertAlmostEqual(metrics["max_side_trade_share"], 0.5)
        self.assertAlmostEqual(metrics["long_raw_pnl"], 3.0)
        self.assertAlmostEqual(metrics["short_raw_pnl"], 5.0)
        self.assertAlmostEqual(metrics["long_adjusted_pnl"], 3.0)
        self.assertAlmostEqual(metrics["short_adjusted_pnl"], 5.0)
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

    def test_model_signal_uses_profit_barrier_threshold(self):
        df = frame_with_opens([100, 101, 102])
        predictions = pd.DataFrame(
            {
                "decision_timestamp": df["timestamp"],
                "pred_long_best_adjusted_pnl": [20.0, 20.0, 20.0],
                "pred_short_best_adjusted_pnl": [1.0, 1.0, 1.0],
                "pred_long_profit_barrier_hit_prob": [0.6, 0.8, 0.2],
                "pred_short_profit_barrier_hit_prob": [1.0, 1.0, 1.0],
            }
        )
        config = ModelPolicyConfig(
            predictions=Path("unused"),
            policy="stateless_ev",
            entry_threshold=10,
            long_profit_barrier_column="pred_long_profit_barrier_hit_prob",
            short_profit_barrier_column="pred_short_profit_barrier_hit_prob",
            require_profit_barrier=True,
            profit_barrier_threshold=0.7,
        )

        signal = model_signal_from_predictions(df, predictions, config)

        self.assertEqual(signal.tolist(), [0, 1, 0])

    def test_model_signal_can_block_entry_regimes(self):
        df = frame_with_opens([100, 101, 102])
        predictions = pd.DataFrame(
            {
                "decision_timestamp": df["timestamp"],
                "pred_long_best_adjusted_pnl": [20.0, 20.0, 20.0],
                "pred_short_best_adjusted_pnl": [1.0, 1.0, 1.0],
                "session_regime": ["asia", "ny_late", "rollover"],
            }
        )
        config = ModelPolicyConfig(
            predictions=Path("unused"),
            policy="stateless_ev",
            entry_threshold=10,
            block_session_regimes=("asia", "rollover"),
        )

        signal = model_signal_from_predictions(df, predictions, config)

        self.assertEqual(signal.tolist(), [0, 1, 0])

    def test_model_signal_can_add_side_margin_in_specific_regimes(self):
        df = frame_with_opens([100, 101, 102])
        predictions = pd.DataFrame(
            {
                "decision_timestamp": df["timestamp"],
                "pred_long_best_adjusted_pnl": [20.0, 20.0, 20.0],
                "pred_short_best_adjusted_pnl": [17.0, 17.0, 17.0],
                "session_regime": ["asia", "ny_late", "asia"],
            }
        )
        config = ModelPolicyConfig(
            predictions=Path("unused"),
            policy="stateless_ev",
            entry_threshold=10,
            side_margin=0,
            extra_side_margin_rules=("session_regime=asia:5",),
        )

        signal = model_signal_from_predictions(df, predictions, config)

        self.assertEqual(signal.tolist(), [0, 1, 0])

    def test_model_signal_can_block_side_specific_compound_regime(self):
        df = frame_with_opens([100, 101, 102])
        predictions = pd.DataFrame(
            {
                "decision_timestamp": df["timestamp"],
                "pred_long_best_adjusted_pnl": [1.0, 1.0, 20.0],
                "pred_short_best_adjusted_pnl": [20.0, 20.0, 17.0],
                "trend_regime": ["range", "range", "range"],
                "volatility_regime": ["low_vol", "low_vol", "low_vol"],
                "session_regime": ["asia", "london", "asia"],
            }
        )
        config = ModelPolicyConfig(
            predictions=Path("unused"),
            policy="stateless_ev",
            entry_threshold=10,
            side_block_rules=("short:trend_regime=range+volatility_regime=low_vol+session_regime=asia",),
        )

        signal = model_signal_from_predictions(df, predictions, config)

        self.assertEqual(signal.tolist(), [0, -1, 1])

    def test_model_signal_can_add_side_specific_compound_margin(self):
        df = frame_with_opens([100, 101, 102])
        predictions = pd.DataFrame(
            {
                "decision_timestamp": df["timestamp"],
                "pred_long_best_adjusted_pnl": [17.0, 17.0, 20.0],
                "pred_short_best_adjusted_pnl": [20.0, 20.0, 17.0],
                "trend_regime": ["range", "range", "range"],
                "volatility_regime": ["low_vol", "low_vol", "low_vol"],
                "session_regime": ["asia", "london", "asia"],
            }
        )
        config = ModelPolicyConfig(
            predictions=Path("unused"),
            policy="stateless_ev",
            entry_threshold=10,
            side_margin=0,
            side_extra_margin_rules=(
                "short:trend_regime=range+volatility_regime=low_vol+session_regime=asia:5",
            ),
        )

        signal = model_signal_from_predictions(df, predictions, config)

        self.assertEqual(signal.tolist(), [0, -1, 1])

    def test_model_signal_can_subtract_side_specific_ev_penalty_before_selection(self):
        df = frame_with_opens([100, 101, 102])
        predictions = pd.DataFrame(
            {
                "decision_timestamp": df["timestamp"],
                "pred_long_best_adjusted_pnl": [20.0, 20.0, 20.0],
                "pred_short_best_adjusted_pnl": [17.0, 17.0, 17.0],
                "session_regime": ["ny_late", "london", "ny_late"],
            }
        )
        config = ModelPolicyConfig(
            predictions=Path("unused"),
            policy="stateless_ev",
            entry_threshold=10,
            side_margin=0,
            side_ev_penalty_rules=("long:session_regime=ny_late:5",),
        )

        signal = model_signal_from_predictions(df, predictions, config)

        self.assertEqual(signal.tolist(), [-1, 1, -1])

    def test_model_signal_can_apply_side_specific_entry_offsets(self):
        df = frame_with_opens([100, 101, 102])
        predictions = pd.DataFrame(
            {
                "decision_timestamp": df["timestamp"],
                "pred_long_best_adjusted_pnl": [15.0, 20.0, 15.0],
                "pred_short_best_adjusted_pnl": [20.0, 1.0, 20.0],
            }
        )
        config = ModelPolicyConfig(
            predictions=Path("unused"),
            policy="stateless_ev",
            entry_threshold=10,
            short_entry_threshold_offset=15,
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

    def test_timed_model_signal_skips_entries_with_invalid_raw_holding_time(self):
        df = frame_with_opens([100, 101, 102, 103, 104, 105], start="2025-01-01 00:00:00+00:00")
        predictions = pd.DataFrame(
            {
                "decision_timestamp": df["timestamp"],
                "pred_long_best_adjusted_pnl": [20, 20, 20, 20, 20, 20],
                "pred_short_best_adjusted_pnl": [1, 1, 1, 1, 1, 1],
                "pred_long_best_holding_minutes": [-5, -5, -5, -5, -5, -5],
                "pred_short_best_holding_minutes": [2, 2, 2, 2, 2, 2],
            }
        )
        config = ModelPolicyConfig(
            predictions=Path("unused"),
            policy="timed_ev",
            entry_threshold=10,
            exit_threshold=0,
            min_valid_predicted_hold_minutes=2,
        )

        signal = model_signal_from_predictions(df, predictions, config)

        self.assertEqual(signal.tolist(), [0, 0, 0, 0, 0, 0])

    def test_timed_model_signal_uses_holding_fallback_for_invalid_primary_time(self):
        df = frame_with_opens([100, 101, 102, 103, 104, 105], start="2025-01-01 00:00:00+00:00")
        predictions = pd.DataFrame(
            {
                "decision_timestamp": df["timestamp"],
                "pred_long_best_adjusted_pnl": [20, 20, 20, 20, 20, 20],
                "pred_short_best_adjusted_pnl": [1, 1, 1, 1, 1, 1],
                "pred_long_best_holding_minutes": [-5, -5, -5, -5, -5, -5],
                "pred_short_best_holding_minutes": [2, 2, 2, 2, 2, 2],
                "pred_long_exit_event_minutes": [3, 3, 3, 3, 3, 3],
                "pred_short_exit_event_minutes": [3, 3, 3, 3, 3, 3],
            }
        )
        config = ModelPolicyConfig(
            predictions=Path("unused"),
            policy="timed_ev",
            entry_threshold=10,
            exit_threshold=0,
            min_valid_predicted_hold_minutes=2,
            long_holding_fallback_column="pred_long_exit_event_minutes",
            short_holding_fallback_column="pred_short_exit_event_minutes",
        )

        signal = model_signal_from_predictions(df, predictions, config)

        self.assertEqual(signal.tolist(), [1, 1, 1, 1, 0, 1])

    def test_timed_model_signal_shrinks_holding_time_with_exit_event_probability(self):
        df = frame_with_opens([100, 101, 102, 103, 104, 105], start="2025-01-01 00:00:00+00:00")
        predictions = pd.DataFrame(
            {
                "decision_timestamp": df["timestamp"],
                "pred_long_best_adjusted_pnl": [20, 20, 20, 20, 20, 20],
                "pred_short_best_adjusted_pnl": [1, 1, 1, 1, 1, 1],
                "pred_long_best_holding_minutes": [4, 4, 4, 4, 4, 4],
                "pred_short_best_holding_minutes": [4, 4, 4, 4, 4, 4],
                "pred_long_exit_event_prob_0": [0.25, 0.25, 0.25, 0.25, 0.25, 0.25],
                "pred_short_exit_event_prob_0": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                "pred_long_exit_event_prob_2": [0.25, 0.25, 0.25, 0.25, 0.25, 0.25],
                "pred_short_exit_event_prob_2": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            }
        )
        common_config = {
            "predictions": Path("unused"),
            "policy": "timed_ev",
            "entry_threshold": 10,
            "exit_threshold": 0,
        }

        unshrunk_signal = model_signal_from_predictions(
            df,
            predictions,
            ModelPolicyConfig(**common_config),
        )
        shrunk_signal = model_signal_from_predictions(
            df,
            predictions,
            ModelPolicyConfig(
                **common_config,
                time_exit_holding_shrink=1.0,
                loss_first_holding_shrink=1.0,
            ),
        )

        self.assertEqual(unshrunk_signal.tolist(), [1, 1, 1, 1, 1, 0])
        self.assertEqual(shrunk_signal.tolist(), [1, 1, 1, 0, 1, 1])

    def test_timed_model_signal_exits_on_dynamic_exit_event_probability(self):
        df = frame_with_opens([100, 101, 102, 103, 104, 105], start="2025-01-01 00:00:00+00:00")
        predictions = pd.DataFrame(
            {
                "decision_timestamp": df["timestamp"],
                "pred_long_best_adjusted_pnl": [20, 20, 20, 20, 20, 20],
                "pred_short_best_adjusted_pnl": [1, 1, 1, 1, 1, 1],
                "pred_long_best_holding_minutes": [10, 10, 10, 10, 10, 10],
                "pred_short_best_holding_minutes": [10, 10, 10, 10, 10, 10],
                "pred_long_exit_event_prob_2": [0.0, 0.0, 0.9, 0.0, 0.0, 0.0],
                "pred_short_exit_event_prob_2": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            }
        )
        config = ModelPolicyConfig(
            predictions=Path("unused"),
            policy="timed_ev",
            entry_threshold=10,
            exit_threshold=0,
            loss_first_exit_threshold=0.8,
        )

        signal = model_signal_from_predictions(df, predictions, config)

        self.assertEqual(signal.tolist(), [1, 1, 0, 1, 1, 1])

    def test_fixed_horizon_scores_select_best_available_horizon(self):
        frame = pd.DataFrame(
            {
                "h60": [1.0, float("nan")],
                "h240": [3.0, float("nan")],
                "h720": [2.0, float("nan")],
            }
        )

        scores, minutes = fixed_horizon_scores(frame, (60.0, 240.0, 720.0))

        self.assertEqual(scores.iloc[0], 3.0)
        self.assertEqual(minutes.iloc[0], 240.0)
        self.assertTrue(pd.isna(scores.iloc[1]))
        self.assertTrue(pd.isna(minutes.iloc[1]))

    def test_fixed_horizon_scores_can_use_conservative_aggregation(self):
        frame = pd.DataFrame(
            {
                "h60": [30.0, 5.0],
                "h240": [0.0, 5.0],
                "h720": [-15.0, float("nan")],
            }
        )

        mean_scores, mean_minutes = fixed_horizon_scores(
            frame,
            (60.0, 240.0, 720.0),
            score_mode="mean",
        )
        min_scores, min_minutes = fixed_horizon_scores(
            frame,
            (60.0, 240.0, 720.0),
            score_mode="min",
        )

        self.assertAlmostEqual(mean_scores.iloc[0], 5.0)
        self.assertAlmostEqual(mean_scores.iloc[1], 5.0)
        self.assertAlmostEqual(min_scores.iloc[0], -15.0)
        self.assertAlmostEqual(min_scores.iloc[1], 5.0)
        self.assertEqual(mean_minutes.iloc[0], 60.0)
        self.assertEqual(min_minutes.iloc[0], 60.0)

    def test_fixed_horizon_model_signal_uses_best_horizon_as_exit_time(self):
        df = frame_with_opens(
            [100, 101, 102, 103, 104, 105],
            start="2025-01-01 00:00:00+00:00",
        )
        predictions = pd.DataFrame(
            {
                "decision_timestamp": df["timestamp"],
                "pred_long_best_adjusted_pnl": [0, 0, 0, 0, 0, 0],
                "pred_short_best_adjusted_pnl": [0, 0, 0, 0, 0, 0],
                "pred_long_fixed_1m_adjusted_pnl": [20, 20, 20, 20, 20, 20],
                "pred_long_fixed_3m_adjusted_pnl": [30, 30, 30, 30, 30, 30],
                "pred_short_fixed_1m_adjusted_pnl": [1, 1, 1, 1, 1, 1],
                "pred_short_fixed_3m_adjusted_pnl": [2, 2, 2, 2, 2, 2],
            }
        )
        config = ModelPolicyConfig(
            predictions=Path("unused"),
            policy="fixed_horizon_ev",
            entry_threshold=10,
            fixed_horizon_minutes=(1.0, 3.0),
            long_fixed_horizon_columns=(
                "pred_long_fixed_1m_adjusted_pnl",
                "pred_long_fixed_3m_adjusted_pnl",
            ),
            short_fixed_horizon_columns=(
                "pred_short_fixed_1m_adjusted_pnl",
                "pred_short_fixed_3m_adjusted_pnl",
            ),
        )

        signal = model_signal_from_predictions(df, predictions, config)

        self.assertEqual(signal.tolist(), [1, 1, 1, 1, 0, 1])

    def test_fixed_horizon_model_signal_can_use_mean_score_mode(self):
        df = frame_with_opens([100, 101, 102])
        predictions = pd.DataFrame(
            {
                "decision_timestamp": df["timestamp"],
                "pred_long_best_adjusted_pnl": [0, 0, 0],
                "pred_short_best_adjusted_pnl": [0, 0, 0],
                "pred_long_fixed_1m_adjusted_pnl": [30, 30, 30],
                "pred_long_fixed_3m_adjusted_pnl": [0, 0, 0],
                "pred_short_fixed_1m_adjusted_pnl": [1, 1, 1],
                "pred_short_fixed_3m_adjusted_pnl": [1, 1, 1],
            }
        )
        common_config = {
            "predictions": Path("unused"),
            "policy": "fixed_horizon_ev",
            "entry_threshold": 20,
            "fixed_horizon_minutes": (1.0, 3.0),
            "long_fixed_horizon_columns": (
                "pred_long_fixed_1m_adjusted_pnl",
                "pred_long_fixed_3m_adjusted_pnl",
            ),
            "short_fixed_horizon_columns": (
                "pred_short_fixed_1m_adjusted_pnl",
                "pred_short_fixed_3m_adjusted_pnl",
            ),
        }

        default_signal = model_signal_from_predictions(
            df,
            predictions,
            ModelPolicyConfig(**common_config),
        )
        conservative_signal = model_signal_from_predictions(
            df,
            predictions,
            ModelPolicyConfig(**common_config, fixed_horizon_score_mode="mean"),
        )

        self.assertEqual(default_signal.tolist(), [1, 1, 0])
        self.assertEqual(conservative_signal.tolist(), [0, 0, 0])

    def test_profit_barrier_miss_penalty_reduces_low_probability_side_ev(self):
        df = frame_with_opens([100, 101])
        predictions = pd.DataFrame(
            {
                "decision_timestamp": df["timestamp"],
                "pred_long_best_adjusted_pnl": [20.0, 20.0],
                "pred_short_best_adjusted_pnl": [18.0, 18.0],
                "pred_long_profit_barrier_hit": [0.0, 1.0],
                "pred_short_profit_barrier_hit": [1.0, 0.0],
            }
        )
        common_config = {
            "predictions": Path("unused"),
            "policy": "stateless_ev",
            "entry_threshold": 10.0,
            "side_margin": 0.1,
        }

        unpenalized_signal = model_signal_from_predictions(
            df,
            predictions,
            ModelPolicyConfig(**common_config),
        )
        penalized_signal = model_signal_from_predictions(
            df,
            predictions,
            ModelPolicyConfig(**common_config, profit_barrier_miss_penalty=5.0),
        )

        self.assertEqual(unpenalized_signal.tolist(), [1, 1])
        self.assertEqual(penalized_signal.tolist(), [-1, 1])

    def test_exit_event_probability_penalties_reduce_risky_side_ev(self):
        df = frame_with_opens([100, 101])
        predictions = pd.DataFrame(
            {
                "decision_timestamp": df["timestamp"],
                "pred_long_best_adjusted_pnl": [20.0, 20.0],
                "pred_short_best_adjusted_pnl": [18.0, 18.0],
                "pred_long_exit_event_prob_0": [1.0, 0.0],
                "pred_short_exit_event_prob_0": [0.0, 0.0],
                "pred_long_exit_event_prob_2": [0.0, 1.0],
                "pred_short_exit_event_prob_2": [0.0, 0.0],
            }
        )
        common_config = {
            "predictions": Path("unused"),
            "policy": "stateless_ev",
            "entry_threshold": 10.0,
            "side_margin": 0.1,
        }

        unpenalized_signal = model_signal_from_predictions(
            df,
            predictions,
            ModelPolicyConfig(**common_config),
        )
        time_penalized_signal = model_signal_from_predictions(
            df,
            predictions,
            ModelPolicyConfig(**common_config, time_exit_penalty=5.0),
        )
        loss_penalized_signal = model_signal_from_predictions(
            df,
            predictions,
            ModelPolicyConfig(**common_config, loss_first_penalty=5.0),
        )

        self.assertEqual(unpenalized_signal.tolist(), [1, 1])
        self.assertEqual(time_penalized_signal.tolist(), [-1, 1])
        self.assertEqual(loss_penalized_signal.tolist(), [1, -1])

    def test_side_confidence_penalty_reduces_low_confidence_side_ev(self):
        df = frame_with_opens([100, 101])
        predictions = pd.DataFrame(
            {
                "decision_timestamp": df["timestamp"],
                "pred_long_best_adjusted_pnl": [20.0, 20.0],
                "pred_short_best_adjusted_pnl": [18.0, 18.0],
                "pred_best_side_prob_1": [0.2, 0.9],
                "pred_best_side_prob_-1": [0.9, 0.2],
            }
        )
        common_config = {
            "predictions": Path("unused"),
            "policy": "stateless_ev",
            "entry_threshold": 10.0,
            "side_margin": 0.1,
        }

        unpenalized_signal = model_signal_from_predictions(
            df,
            predictions,
            ModelPolicyConfig(**common_config),
        )
        penalized_signal = model_signal_from_predictions(
            df,
            predictions,
            ModelPolicyConfig(**common_config, side_confidence_penalty=5.0),
        )

        self.assertEqual(unpenalized_signal.tolist(), [1, 1])
        self.assertEqual(penalized_signal.tolist(), [-1, 1])

    def test_side_confidence_penalty_rule_applies_only_matching_regime(self):
        df = frame_with_opens([100, 101])
        predictions = pd.DataFrame(
            {
                "decision_timestamp": df["timestamp"],
                "pred_long_best_adjusted_pnl": [20.0, 20.0],
                "pred_short_best_adjusted_pnl": [18.0, 18.0],
                "pred_best_side_prob_1": [0.6, 0.6],
                "pred_best_side_prob_-1": [0.9, 0.9],
                "combined_regime": ["down_normal_vol", "range_low_vol"],
            }
        )
        config = ModelPolicyConfig(
            predictions=Path("unused"),
            policy="stateless_ev",
            entry_threshold=10.0,
            side_margin=0.1,
            side_confidence_penalty_rules=("combined_regime=down_normal_vol:10",),
        )

        signal = model_signal_from_predictions(df, predictions, config)

        self.assertEqual(signal.tolist(), [-1, 1])

    def test_side_confidence_overfit_penalty_rule_penalizes_high_confidence_side(self):
        df = frame_with_opens([100, 101])
        predictions = pd.DataFrame(
            {
                "decision_timestamp": df["timestamp"],
                "pred_long_best_adjusted_pnl": [20.0, 20.0],
                "pred_short_best_adjusted_pnl": [18.0, 18.0],
                "pred_best_side_prob_1": [0.9, 0.9],
                "pred_best_side_prob_-1": [0.2, 0.2],
                "combined_regime": ["down_normal_vol", "range_low_vol"],
            }
        )
        config = ModelPolicyConfig(
            predictions=Path("unused"),
            policy="stateless_ev",
            entry_threshold=10.0,
            side_margin=0.1,
            side_confidence_overfit_penalty_rules=("combined_regime=down_normal_vol:5",),
        )

        signal = model_signal_from_predictions(df, predictions, config)

        self.assertEqual(signal.tolist(), [-1, 1])

    def test_model_signal_can_filter_low_side_confidence(self):
        df = frame_with_opens([100, 101, 102])
        predictions = pd.DataFrame(
            {
                "decision_timestamp": df["timestamp"],
                "pred_long_best_adjusted_pnl": [20.0, 20.0, 5.0],
                "pred_short_best_adjusted_pnl": [10.0, 10.0, 16.0],
                "pred_best_side_prob_1": [0.4, 0.8, 0.2],
                "pred_best_side_prob_-1": [0.6, 0.2, 0.9],
            }
        )
        config = ModelPolicyConfig(
            predictions=Path("unused"),
            policy="stateless_ev",
            entry_threshold=10.0,
            min_side_confidence=0.7,
        )

        signal = model_signal_from_predictions(df, predictions, config)

        self.assertEqual(signal.tolist(), [0, 1, -1])

    def test_model_signal_can_filter_low_predicted_trade_quality(self):
        df = frame_with_opens([100, 101, 102])
        predictions = pd.DataFrame(
            {
                "decision_timestamp": df["timestamp"],
                "pred_long_best_adjusted_pnl": [20.0, 20.0, 5.0],
                "pred_short_best_adjusted_pnl": [10.0, 10.0, 16.0],
                "pred_trade_quality_long_adjusted_pnl": [-2.0, 4.0, 3.0],
                "pred_trade_quality_short_adjusted_pnl": [8.0, 8.0, 7.0],
            }
        )
        config = ModelPolicyConfig(
            predictions=Path("unused"),
            policy="stateless_ev",
            entry_threshold=10.0,
            min_trade_quality=0.0,
        )

        signal = model_signal_from_predictions(df, predictions, config)

        self.assertEqual(signal.tolist(), [0, 1, -1])

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
        self.assertEqual(normalized["profit_barrier_miss_penalty"].tolist(), [0.0])
        self.assertEqual(normalized["time_exit_penalty"].tolist(), [0.0])
        self.assertEqual(normalized["loss_first_penalty"].tolist(), [0.0])
        self.assertEqual(normalized["time_exit_holding_shrink"].tolist(), [0.0])
        self.assertEqual(normalized["loss_first_holding_shrink"].tolist(), [0.0])
        self.assertEqual(normalized["time_exit_exit_threshold"].tolist(), [float("inf")])
        self.assertEqual(normalized["loss_first_exit_threshold"].tolist(), [float("inf")])
        self.assertEqual(normalized["min_trade_quality"].tolist(), [-float("inf")])
        self.assertEqual(normalized["fixed_horizon_score_mode"].tolist(), ["max"])
        self.assertEqual(normalized["long_entry_threshold_offset"].tolist(), [0.0])
        self.assertEqual(normalized["short_entry_threshold_offset"].tolist(), [0.0])
        self.assertEqual(normalized["max_wait_regret"].tolist(), [float("inf")])
        self.assertEqual(normalized["min_predicted_hold_minutes"].tolist(), [1.0])
        self.assertEqual(normalized["max_predicted_hold_minutes"].tolist(), [1440.0])
        self.assertEqual(normalized["min_valid_predicted_hold_minutes"].tolist(), [-float("inf")])
        self.assertEqual(normalized["long_holding_fallback_column"].tolist(), [""])
        self.assertEqual(normalized["short_holding_fallback_column"].tolist(), [""])
        self.assertEqual(normalized["min_entry_rank"].tolist(), [0.0])
        self.assertEqual(normalized["require_profit_barrier"].tolist(), [False])
        self.assertEqual(normalized["profit_barrier_threshold"].tolist(), [0.5])
        self.assertEqual(normalized["side_ev_penalty_rules"].tolist(), [""])
        self.assertEqual(normalized["side_extra_margin_rules"].tolist(), [""])
        self.assertEqual(normalized["side_block_rules"].tolist(), [""])
        self.assertTrue(pd.isna(normalized["direction_session_adjusted_pnl_min"]).sum() == 0)
        self.assertEqual(normalized["worst_direction_session"].tolist(), [""])
        self.assertEqual(normalized["worst_direction_session_trade_count"].tolist(), [0])
        self.assertTrue(pd.isna(normalized["combined_regime_adjusted_pnl_min"]).sum() == 0)
        self.assertEqual(normalized["worst_combined_regime"].tolist(), [""])
        self.assertEqual(normalized["worst_combined_regime_trade_count"].tolist(), [0])
        self.assertTrue(
            pd.isna(normalized["direction_combined_regime_adjusted_pnl_min"]).sum() == 0
        )
        self.assertEqual(normalized["worst_direction_combined_regime"].tolist(), [""])
        self.assertEqual(normalized["worst_direction_combined_regime_trade_count"].tolist(), [0])
        self.assertEqual(normalized["direction_error_rate"].tolist(), [0.0])
        self.assertEqual(normalized["predicted_side_error_rate"].tolist(), [0.0])
        self.assertEqual(normalized["no_edge_rate"].tolist(), [0.0])
        self.assertEqual(normalized["exit_regret_mean"].tolist(), [0.0])
        self.assertEqual(normalized["ev_overestimate_vs_realized_mean"].tolist(), [0.0])
        self.assertEqual(normalized["predicted_profit_barrier_miss_rate"].tolist(), [0.0])
        self.assertEqual(normalized["actual_profit_barrier_miss_rate"].tolist(), [0.0])
        self.assertEqual(normalized["predicted_profit_barrier_miss_count"].tolist(), [0.0])
        self.assertEqual(normalized["actual_profit_barrier_miss_count"].tolist(), [0.0])
        self.assertEqual(normalized["profit_barrier_calibration_overestimate_max"].tolist(), [0.0])
        self.assertEqual(normalized["worst_profit_barrier_calibration_bucket"].tolist(), [""])
        self.assertEqual(normalized["block_trend_regimes"].tolist(), [""])
        self.assertEqual(normalized["block_volatility_regimes"].tolist(), [""])
        self.assertEqual(normalized["block_session_regimes"].tolist(), [""])
        self.assertEqual(normalized["block_gap_regimes"].tolist(), [""])
        self.assertEqual(normalized["block_combined_regimes"].tolist(), [""])
        self.assertEqual(normalized["sweep_source"].tolist(), ["fold_a"])
        self.assertAlmostEqual(normalized["forced_exit_rate"].iloc[0], 0.25)

    def test_sweep_summary_keeps_predicted_hold_cap_as_key(self):
        def fold(long_cap_pnl, short_cap_pnl):
            return pd.DataFrame(
                {
                    "policy": ["timed_ev", "timed_ev"],
                    "entry_threshold": [10, 10],
                    "exit_threshold": [0, 0],
                    "side_margin": [1, 1],
                    "max_predicted_hold_minutes": [720, 1440],
                    "total_adjusted_pnl": [long_cap_pnl, short_cap_pnl],
                    "total_raw_pnl": [long_cap_pnl + 5, short_cap_pnl + 5],
                    "trade_count": [20, 20],
                    "win_rate": [0.6, 0.6],
                    "max_drawdown": [20, 20],
                    "forced_exit_rate": [0.0, 0.0],
                    "forced_exit_count": [0, 0],
                }
            )

        summary = summarize_sweep_frames(
            [fold(30, 10), fold(25, 15)],
            min_folds=2,
            min_trades_per_fold=10,
            max_forced_exit_rate=0.0,
            max_drawdown=100.0,
            min_adjusted_pnl_per_fold=0.0,
            sort_by="min_pnl",
        )

        self.assertEqual(len(summary), 2)
        self.assertEqual(summary.iloc[0]["max_predicted_hold_minutes"], 720)
        self.assertAlmostEqual(summary.iloc[0]["total_adjusted_pnl_min"], 25.0)
        self.assertEqual(summary.iloc[1]["max_predicted_hold_minutes"], 1440)
        self.assertAlmostEqual(summary.iloc[1]["total_adjusted_pnl_min"], 10.0)

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

    def test_candidate_selection_combines_cost_and_plateau_gates(self):
        def fold(values):
            rows = []
            for offset, pnl, long_pnl, short_pnl in values:
                rows.append(
                    {
                        "policy": "fixed_horizon_ev",
                        "entry_threshold": 0,
                        "long_entry_threshold_offset": 0,
                        "short_entry_threshold_offset": offset,
                        "exit_threshold": 0,
                        "side_margin": 2,
                        "risk_penalty": 0,
                        "max_wait_regret": 4,
                        "min_entry_rank": 0.5,
                        "require_profit_barrier": "False",
                        "extra_side_margin_rules": "",
                        "block_trend_regimes": "",
                        "block_volatility_regimes": "",
                        "block_session_regimes": "",
                        "block_gap_regimes": "",
                        "block_combined_regimes": "",
                        "total_adjusted_pnl": pnl,
                        "total_raw_pnl": pnl + 5,
                        "trade_count": 40,
                        "win_rate": 0.55,
                        "max_drawdown": 30.0,
                        "forced_exit_rate": 0.0,
                        "forced_exit_count": 0,
                        "long_adjusted_pnl": long_pnl,
                        "short_adjusted_pnl": short_pnl,
                    }
                )
            return pd.DataFrame(rows)

        base_a = fold([(4, 30, 20, 10), (8, 28, 15, 13), (10, 24, 12, 12)])
        base_b = fold([(4, 26, 18, 8), (8, 27, 14, 13), (10, 23, 11, 12)])
        cost_a = fold([(4, 10, 18, -45), (8, 18, 10, 8), (10, 16, 8, 8)])
        cost_b = fold([(4, 9, 16, -44), (8, 17, 9, 8), (10, 14, 7, 7)])

        summary = summarize_candidate_selection(
            base_frames=[base_a, base_b],
            cost_frames=[cost_a, cost_b],
            min_folds=2,
            min_trades_per_fold=30,
            max_forced_exit_rate=0.0,
            max_drawdown=100.0,
            min_base_adjusted_pnl_per_fold=0.0,
            min_cost_adjusted_pnl_per_fold=0.0,
            max_cost_pnl_drop=20.0,
            max_side_loss_per_fold=20.0,
            plateau_column="short_entry_threshold_offset",
            plateau_radius=2.0,
            min_plateau_neighbors=1,
        )

        top = summary.iloc[0]
        self.assertEqual(top["short_entry_threshold_offset"], 8)
        self.assertTrue(bool(top["eligible"]))
        self.assertEqual(top["plateau_support_count"], 1)
        offset4 = summary[summary["short_entry_threshold_offset"] == 4].iloc[0]
        self.assertFalse(bool(offset4["eligible"]))
        self.assertFalse(bool(offset4["side_loss_ok"]))

    def test_plateau_support_counts_handles_categorical_sweep_key(self):
        rows = []
        for rules, eligible in [
            ("short:combined_regime=range_normal_vol:5", True),
            ("short:combined_regime=range_normal_vol:5", True),
            ("short:combined_regime=range_normal_vol:10", True),
            ("short:combined_regime=range_normal_vol:10", False),
        ]:
            row = {column: "" for column in SWEEP_KEY_COLUMNS}
            row.update(
                {
                    "policy": "timed_ev",
                    "entry_threshold": 12,
                    "long_entry_threshold_offset": 0,
                    "short_entry_threshold_offset": 6,
                    "exit_threshold": 0,
                    "side_margin": 5,
                    "risk_penalty": 0,
                    "fixed_horizon_score_mode": "max",
                    "min_predicted_hold_minutes": 1,
                    "max_predicted_hold_minutes": 480,
                    "min_valid_predicted_hold_minutes": -float("inf"),
                    "max_wait_regret": float("inf"),
                    "min_entry_rank": 0.5,
                    "min_trade_quality": -float("inf"),
                    "profit_barrier_miss_penalty": 0,
                    "time_exit_penalty": 0,
                    "loss_first_penalty": 0,
                    "time_exit_holding_shrink": 0,
                    "loss_first_holding_shrink": 0,
                    "time_exit_exit_threshold": float("inf"),
                    "loss_first_exit_threshold": float("inf"),
                    "side_confidence_penalty": 0,
                    "min_side_confidence": 0,
                    "require_profit_barrier": False,
                    "profit_barrier_threshold": 0.5,
                    "side_ev_penalty_rules": rules,
                    "eligible": eligible,
                }
            )
            rows.append(row)
        frame = pd.DataFrame(rows)

        support = plateau_support_counts(
            frame,
            plateau_column="side_ev_penalty_rules",
            plateau_radius=0,
            eligible_column="eligible",
        )

        self.assertEqual(support.tolist(), [1, 1, 0, 1])

    def test_candidate_selection_allows_separate_base_and_cost_fold_requirements(self):
        def fold(pnl):
            return pd.DataFrame(
                [
                    {
                        "policy": "fixed_horizon_ev",
                        "entry_threshold": 0,
                        "long_entry_threshold_offset": 0,
                        "short_entry_threshold_offset": 8,
                        "exit_threshold": 0,
                        "side_margin": 2,
                        "risk_penalty": 0,
                        "max_wait_regret": 4,
                        "min_entry_rank": 0.5,
                        "require_profit_barrier": "False",
                        "extra_side_margin_rules": "",
                        "block_trend_regimes": "",
                        "block_volatility_regimes": "",
                        "block_session_regimes": "",
                        "block_gap_regimes": "",
                        "block_combined_regimes": "",
                        "total_adjusted_pnl": pnl,
                        "total_raw_pnl": pnl + 5,
                        "trade_count": 40,
                        "win_rate": 0.55,
                        "max_drawdown": 30.0,
                        "forced_exit_rate": 0.0,
                        "forced_exit_count": 0,
                        "long_adjusted_pnl": 20,
                        "short_adjusted_pnl": 10,
                    }
                ]
            )

        default_summary = summarize_candidate_selection(
            base_frames=[fold(30), fold(28)],
            cost_frames=[fold(20), fold(18), fold(17)],
            min_folds=3,
            min_trades_per_fold=30,
            max_forced_exit_rate=0.0,
            max_drawdown=100.0,
            min_base_adjusted_pnl_per_fold=0.0,
            min_cost_adjusted_pnl_per_fold=0.0,
            max_cost_pnl_drop=20.0,
            max_side_loss_per_fold=20.0,
            plateau_column="short_entry_threshold_offset",
            plateau_radius=2.0,
            min_plateau_neighbors=0,
        )
        self.assertFalse(bool(default_summary.iloc[0]["eligible"]))
        self.assertEqual(default_summary.iloc[0]["fold_count_base"], 2)
        self.assertEqual(default_summary.iloc[0]["fold_count_cost"], 3)

        explicit_summary = summarize_candidate_selection(
            base_frames=[fold(30), fold(28)],
            cost_frames=[fold(20), fold(18), fold(17)],
            min_folds=3,
            min_base_folds=2,
            min_cost_folds=3,
            min_trades_per_fold=30,
            max_forced_exit_rate=0.0,
            max_drawdown=100.0,
            min_base_adjusted_pnl_per_fold=0.0,
            min_cost_adjusted_pnl_per_fold=0.0,
            max_cost_pnl_drop=20.0,
            max_side_loss_per_fold=20.0,
            plateau_column="short_entry_threshold_offset",
            plateau_radius=2.0,
            min_plateau_neighbors=0,
        )
        self.assertTrue(bool(explicit_summary.iloc[0]["eligible"]))
        self.assertTrue(bool(explicit_summary.iloc[0]["eligible_base"]))
        self.assertTrue(bool(explicit_summary.iloc[0]["eligible_cost"]))

    def test_candidate_selection_can_gate_direction_session_loss(self):
        def fold(values):
            rows = []
            for offset, pnl, direction_session_pnl in values:
                rows.append(
                    {
                        "policy": "fixed_horizon_ev",
                        "entry_threshold": 0,
                        "long_entry_threshold_offset": 0,
                        "short_entry_threshold_offset": offset,
                        "exit_threshold": 0,
                        "side_margin": 1,
                        "risk_penalty": 0,
                        "max_wait_regret": 4,
                        "min_entry_rank": 0.5,
                        "require_profit_barrier": "True",
                        "profit_barrier_threshold": 0.4,
                        "extra_side_margin_rules": "session_regime=asia:5",
                        "side_extra_margin_rules": "",
                        "side_block_rules": "",
                        "block_trend_regimes": "",
                        "block_volatility_regimes": "",
                        "block_session_regimes": "",
                        "block_gap_regimes": "",
                        "block_combined_regimes": "",
                        "total_adjusted_pnl": pnl,
                        "total_raw_pnl": pnl + 5,
                        "trade_count": 30,
                        "win_rate": 0.6,
                        "max_drawdown": 40,
                        "forced_exit_rate": 0.0,
                        "forced_exit_count": 0,
                        "long_adjusted_pnl": 20,
                        "short_adjusted_pnl": 10,
                        "direction_session_adjusted_pnl_min": direction_session_pnl,
                        "worst_direction_session": "short:asia",
                        "worst_direction_session_trade_count": 6,
                    }
                )
            return pd.DataFrame(rows)

        base_a = fold([(6, 40, -55), (8, 32, -8)])
        base_b = fold([(6, 38, -54), (8, 30, -9)])
        cost_a = fold([(6, 30, -57), (8, 24, -10)])
        cost_b = fold([(6, 29, -56), (8, 23, -11)])

        summary = summarize_candidate_selection(
            base_frames=[base_a, base_b],
            cost_frames=[cost_a, cost_b],
            min_folds=2,
            min_trades_per_fold=20,
            max_forced_exit_rate=0.0,
            max_drawdown=100.0,
            min_base_adjusted_pnl_per_fold=0.0,
            min_cost_adjusted_pnl_per_fold=0.0,
            max_cost_pnl_drop=20.0,
            max_side_loss_per_fold=20.0,
            max_direction_session_loss_per_fold=20.0,
            plateau_column="short_entry_threshold_offset",
            plateau_radius=2.0,
            min_plateau_neighbors=0,
        )

        offset6 = summary[summary["short_entry_threshold_offset"] == 6].iloc[0]
        offset8 = summary[summary["short_entry_threshold_offset"] == 8].iloc[0]
        self.assertFalse(bool(offset6["eligible"]))
        self.assertFalse(bool(offset6["direction_session_loss_ok"]))
        self.assertTrue(bool(offset8["eligible"]))
        self.assertEqual(summary.iloc[0]["short_entry_threshold_offset"], 8)

    def test_candidate_selection_can_rank_by_group_loss_penalty(self):
        def fold(values):
            rows = []
            for offset, pnl, direction_session_pnl in values:
                rows.append(
                    {
                        "policy": "fixed_horizon_ev",
                        "entry_threshold": 0,
                        "long_entry_threshold_offset": 0,
                        "short_entry_threshold_offset": offset,
                        "exit_threshold": 0,
                        "side_margin": 1,
                        "risk_penalty": 0,
                        "max_wait_regret": 4,
                        "min_entry_rank": 0.5,
                        "require_profit_barrier": "True",
                        "profit_barrier_threshold": 0.4,
                        "extra_side_margin_rules": "",
                        "side_extra_margin_rules": "",
                        "side_block_rules": "",
                        "block_trend_regimes": "",
                        "block_volatility_regimes": "",
                        "block_session_regimes": "",
                        "block_gap_regimes": "",
                        "block_combined_regimes": "",
                        "total_adjusted_pnl": pnl,
                        "total_raw_pnl": pnl + 5,
                        "trade_count": 30,
                        "win_rate": 0.6,
                        "max_drawdown": 40,
                        "forced_exit_rate": 0.0,
                        "forced_exit_count": 0,
                        "long_adjusted_pnl": 20,
                        "short_adjusted_pnl": 10,
                        "direction_session_adjusted_pnl_min": direction_session_pnl,
                    }
                )
            return pd.DataFrame(rows)

        base_a = fold([(6, 80, -50), (8, 50, -5)])
        base_b = fold([(6, 78, -48), (8, 48, -4)])
        cost_a = fold([(6, 60, -50), (8, 35, -5)])
        cost_b = fold([(6, 58, -48), (8, 34, -4)])

        summary = summarize_candidate_selection(
            base_frames=[base_a, base_b],
            cost_frames=[cost_a, cost_b],
            min_folds=2,
            min_trades_per_fold=20,
            max_forced_exit_rate=0.0,
            max_drawdown=100.0,
            min_base_adjusted_pnl_per_fold=0.0,
            min_cost_adjusted_pnl_per_fold=0.0,
            max_cost_pnl_drop=30.0,
            max_side_loss_per_fold=20.0,
            max_direction_session_loss_per_fold=100.0,
            group_loss_penalty_weight=1.0,
            plateau_column="short_entry_threshold_offset",
            plateau_radius=2.0,
            min_plateau_neighbors=0,
        )

        offset6 = summary[summary["short_entry_threshold_offset"] == 6].iloc[0]
        offset8 = summary[summary["short_entry_threshold_offset"] == 8].iloc[0]
        self.assertTrue(bool(offset6["eligible"]))
        self.assertTrue(bool(offset8["eligible"]))
        self.assertEqual(offset6["group_loss_penalty"], 50)
        self.assertEqual(offset8["group_loss_penalty"], 5)
        self.assertEqual(offset6["robust_total_adjusted_pnl_min_cost"], 8)
        self.assertEqual(offset8["robust_total_adjusted_pnl_min_cost"], 29)
        self.assertEqual(summary.iloc[0]["short_entry_threshold_offset"], 8)

    def test_candidate_selection_can_gate_combined_regime_loss(self):
        def fold(values):
            rows = []
            for offset, pnl, combined_pnl, direction_combined_pnl in values:
                rows.append(
                    {
                        "policy": "fixed_horizon_ev",
                        "entry_threshold": 0,
                        "long_entry_threshold_offset": 0,
                        "short_entry_threshold_offset": offset,
                        "exit_threshold": 0,
                        "side_margin": 1,
                        "risk_penalty": 0,
                        "max_wait_regret": 4,
                        "min_entry_rank": 0.5,
                        "require_profit_barrier": "True",
                        "profit_barrier_threshold": 0.4,
                        "extra_side_margin_rules": "session_regime=asia:5",
                        "side_extra_margin_rules": "",
                        "side_block_rules": "",
                        "block_trend_regimes": "",
                        "block_volatility_regimes": "",
                        "block_session_regimes": "",
                        "block_gap_regimes": "",
                        "block_combined_regimes": "",
                        "total_adjusted_pnl": pnl,
                        "total_raw_pnl": pnl + 5,
                        "trade_count": 30,
                        "win_rate": 0.6,
                        "max_drawdown": 40,
                        "forced_exit_rate": 0.0,
                        "forced_exit_count": 0,
                        "long_adjusted_pnl": 20,
                        "short_adjusted_pnl": 10,
                        "combined_regime_adjusted_pnl_min": combined_pnl,
                        "worst_combined_regime": "range_low_vol",
                        "worst_combined_regime_trade_count": 8,
                        "direction_combined_regime_adjusted_pnl_min": direction_combined_pnl,
                        "worst_direction_combined_regime": "long:range_low_vol",
                        "worst_direction_combined_regime_trade_count": 6,
                    }
                )
            return pd.DataFrame(rows)

        base_a = fold([(6, 46, -70, -65), (8, 32, -10, -9)])
        base_b = fold([(6, 44, -68, -64), (8, 30, -11, -10)])
        cost_a = fold([(6, 36, -72, -66), (8, 24, -12, -11)])
        cost_b = fold([(6, 35, -71, -65), (8, 23, -13, -12)])

        summary = summarize_candidate_selection(
            base_frames=[base_a, base_b],
            cost_frames=[cost_a, cost_b],
            min_folds=2,
            min_trades_per_fold=20,
            max_forced_exit_rate=0.0,
            max_drawdown=100.0,
            min_base_adjusted_pnl_per_fold=0.0,
            min_cost_adjusted_pnl_per_fold=0.0,
            max_cost_pnl_drop=20.0,
            max_side_loss_per_fold=20.0,
            max_combined_regime_loss_per_fold=30.0,
            max_direction_combined_regime_loss_per_fold=30.0,
            plateau_column="short_entry_threshold_offset",
            plateau_radius=2.0,
            min_plateau_neighbors=0,
        )

        offset6 = summary[summary["short_entry_threshold_offset"] == 6].iloc[0]
        offset8 = summary[summary["short_entry_threshold_offset"] == 8].iloc[0]
        self.assertFalse(bool(offset6["eligible"]))
        self.assertFalse(bool(offset6["combined_regime_loss_ok"]))
        self.assertFalse(bool(offset6["direction_combined_regime_loss_ok"]))
        self.assertTrue(bool(offset8["eligible"]))
        self.assertEqual(summary.iloc[0]["short_entry_threshold_offset"], 8)

    def test_candidate_selection_can_gate_profit_barrier_miss_rates(self):
        def fold(values):
            rows = []
            for offset, pnl, predicted_miss_rate, actual_miss_rate in values:
                rows.append(
                    {
                        "policy": "fixed_horizon_ev",
                        "entry_threshold": 0,
                        "long_entry_threshold_offset": 0,
                        "short_entry_threshold_offset": offset,
                        "exit_threshold": 0,
                        "side_margin": 1,
                        "risk_penalty": 0,
                        "max_wait_regret": 4,
                        "min_entry_rank": 0.5,
                        "require_profit_barrier": "True",
                        "profit_barrier_threshold": 0.4,
                        "extra_side_margin_rules": "",
                        "side_extra_margin_rules": "",
                        "side_block_rules": "",
                        "block_trend_regimes": "",
                        "block_volatility_regimes": "",
                        "block_session_regimes": "",
                        "block_gap_regimes": "",
                        "block_combined_regimes": "",
                        "total_adjusted_pnl": pnl,
                        "total_raw_pnl": pnl + 5,
                        "trade_count": 30,
                        "win_rate": 0.6,
                        "max_drawdown": 40,
                        "forced_exit_rate": 0.0,
                        "forced_exit_count": 0,
                        "long_adjusted_pnl": 20,
                        "short_adjusted_pnl": 10,
                        "predicted_profit_barrier_miss_rate": predicted_miss_rate,
                        "predicted_profit_barrier_miss_count": int(predicted_miss_rate * 30),
                        "predicted_profit_barrier_observed_count": 30,
                        "predicted_profit_barrier_miss_adjusted_pnl": -5.0,
                        "actual_profit_barrier_miss_rate": actual_miss_rate,
                        "actual_profit_barrier_miss_count": int(actual_miss_rate * 30),
                        "actual_profit_barrier_observed_count": 30,
                        "actual_profit_barrier_miss_adjusted_pnl": -20.0,
                    }
                )
            return pd.DataFrame(rows)

        base_a = fold([(6, 40, 0.0, 0.7), (8, 32, 0.1, 0.2)])
        base_b = fold([(6, 38, 0.0, 0.65), (8, 30, 0.1, 0.25)])
        cost_a = fold([(6, 30, 0.0, 0.75), (8, 24, 0.1, 0.3)])
        cost_b = fold([(6, 29, 0.0, 0.7), (8, 23, 0.1, 0.2)])

        summary = summarize_candidate_selection(
            base_frames=[base_a, base_b],
            cost_frames=[cost_a, cost_b],
            min_folds=2,
            min_trades_per_fold=20,
            max_forced_exit_rate=0.0,
            max_drawdown=100.0,
            min_base_adjusted_pnl_per_fold=0.0,
            min_cost_adjusted_pnl_per_fold=0.0,
            max_cost_pnl_drop=20.0,
            max_side_loss_per_fold=20.0,
            max_actual_profit_barrier_miss_rate=0.5,
            max_predicted_profit_barrier_miss_rate=0.2,
            plateau_column="short_entry_threshold_offset",
            plateau_radius=2.0,
            min_plateau_neighbors=0,
        )

        offset6 = summary[summary["short_entry_threshold_offset"] == 6].iloc[0]
        offset8 = summary[summary["short_entry_threshold_offset"] == 8].iloc[0]
        self.assertFalse(bool(offset6["eligible"]))
        self.assertFalse(bool(offset6["actual_profit_barrier_miss_ok"]))
        self.assertTrue(bool(offset6["predicted_profit_barrier_miss_ok"]))
        self.assertTrue(bool(offset8["eligible"]))
        self.assertEqual(summary.iloc[0]["short_entry_threshold_offset"], 8)

    def test_candidate_selection_can_gate_smoothed_profit_barrier_miss_rate(self):
        def fold(values):
            rows = []
            for offset, pnl, smoothed_actual_miss_rate in values:
                rows.append(
                    {
                        "policy": "fixed_horizon_ev",
                        "entry_threshold": 0,
                        "long_entry_threshold_offset": 0,
                        "short_entry_threshold_offset": offset,
                        "exit_threshold": 0,
                        "side_margin": 1,
                        "risk_penalty": 0,
                        "max_wait_regret": 4,
                        "min_entry_rank": 0.5,
                        "require_profit_barrier": "True",
                        "profit_barrier_threshold": 0.4,
                        "extra_side_margin_rules": "",
                        "side_extra_margin_rules": "",
                        "side_block_rules": "",
                        "block_trend_regimes": "",
                        "block_volatility_regimes": "",
                        "block_session_regimes": "",
                        "block_gap_regimes": "",
                        "block_combined_regimes": "",
                        "total_adjusted_pnl": pnl,
                        "total_raw_pnl": pnl + 5,
                        "trade_count": 30,
                        "win_rate": 0.6,
                        "max_drawdown": 40,
                        "forced_exit_rate": 0.0,
                        "forced_exit_count": 0,
                        "long_adjusted_pnl": 20,
                        "short_adjusted_pnl": 10,
                        "actual_profit_barrier_miss_rate": 0.2,
                        "actual_profit_barrier_miss_rate_smoothed": smoothed_actual_miss_rate,
                        "actual_profit_barrier_miss_count": 6,
                        "actual_profit_barrier_observed_count": 30,
                        "actual_profit_barrier_miss_adjusted_pnl": -20.0,
                    }
                )
            return pd.DataFrame(rows)

        base_a = fold([(6, 40, 0.62), (8, 32, 0.25)])
        base_b = fold([(6, 38, 0.60), (8, 30, 0.24)])
        cost_a = fold([(6, 30, 0.64), (8, 24, 0.30)])
        cost_b = fold([(6, 29, 0.61), (8, 23, 0.26)])

        summary = summarize_candidate_selection(
            base_frames=[base_a, base_b],
            cost_frames=[cost_a, cost_b],
            min_folds=2,
            min_trades_per_fold=20,
            max_forced_exit_rate=0.0,
            max_drawdown=100.0,
            min_base_adjusted_pnl_per_fold=0.0,
            min_cost_adjusted_pnl_per_fold=0.0,
            max_cost_pnl_drop=20.0,
            max_side_loss_per_fold=20.0,
            max_smoothed_actual_profit_barrier_miss_rate=0.4,
            plateau_column="short_entry_threshold_offset",
            plateau_radius=2.0,
            min_plateau_neighbors=0,
        )

        offset6 = summary[summary["short_entry_threshold_offset"] == 6].iloc[0]
        offset8 = summary[summary["short_entry_threshold_offset"] == 8].iloc[0]
        self.assertFalse(bool(offset6["eligible"]))
        self.assertFalse(bool(offset6["smoothed_actual_profit_barrier_miss_ok"]))
        self.assertTrue(bool(offset8["eligible"]))
        self.assertEqual(summary.iloc[0]["short_entry_threshold_offset"], 8)

    def test_candidate_selection_can_gate_profit_barrier_calibration_overestimate(self):
        def fold(values):
            rows = []
            for offset, pnl, overestimate in values:
                rows.append(
                    {
                        "policy": "fixed_horizon_ev",
                        "entry_threshold": 0,
                        "long_entry_threshold_offset": 0,
                        "short_entry_threshold_offset": offset,
                        "exit_threshold": 0,
                        "side_margin": 1,
                        "risk_penalty": 0,
                        "max_wait_regret": 4,
                        "min_entry_rank": 0.5,
                        "require_profit_barrier": "True",
                        "profit_barrier_threshold": 0.4,
                        "extra_side_margin_rules": "",
                        "side_extra_margin_rules": "",
                        "side_block_rules": "",
                        "block_trend_regimes": "",
                        "block_volatility_regimes": "",
                        "block_session_regimes": "",
                        "block_gap_regimes": "",
                        "block_combined_regimes": "",
                        "total_adjusted_pnl": pnl,
                        "total_raw_pnl": pnl + 5,
                        "trade_count": 30,
                        "win_rate": 0.6,
                        "max_drawdown": 40,
                        "forced_exit_rate": 0.0,
                        "forced_exit_count": 0,
                        "long_adjusted_pnl": 20,
                        "short_adjusted_pnl": 10,
                        "profit_barrier_calibration_observed_count": 30,
                        "profit_barrier_calibration_bucket_count": 2,
                        "profit_barrier_calibration_overestimate_max": overestimate,
                        "profit_barrier_calibration_abs_error_max": overestimate,
                        "worst_profit_barrier_calibration_bucket": "0.6-0.8",
                        "worst_profit_barrier_calibration_bucket_count": 10,
                        "worst_profit_barrier_calibration_predicted_mean": 0.7,
                        "worst_profit_barrier_calibration_actual_hit_rate": 0.7 - overestimate,
                        "worst_profit_barrier_calibration_overestimate": overestimate,
                    }
                )
            return pd.DataFrame(rows)

        base_a = fold([(6, 40, 0.45), (8, 32, 0.10)])
        base_b = fold([(6, 38, 0.42), (8, 30, 0.12)])
        cost_a = fold([(6, 30, 0.46), (8, 24, 0.13)])
        cost_b = fold([(6, 29, 0.44), (8, 23, 0.11)])

        summary = summarize_candidate_selection(
            base_frames=[base_a, base_b],
            cost_frames=[cost_a, cost_b],
            min_folds=2,
            min_trades_per_fold=20,
            max_forced_exit_rate=0.0,
            max_drawdown=100.0,
            min_base_adjusted_pnl_per_fold=0.0,
            min_cost_adjusted_pnl_per_fold=0.0,
            max_cost_pnl_drop=20.0,
            max_side_loss_per_fold=20.0,
            max_profit_barrier_calibration_overestimate=0.2,
            plateau_column="short_entry_threshold_offset",
            plateau_radius=2.0,
            min_plateau_neighbors=0,
        )

        offset6 = summary[summary["short_entry_threshold_offset"] == 6].iloc[0]
        offset8 = summary[summary["short_entry_threshold_offset"] == 8].iloc[0]
        self.assertFalse(bool(offset6["eligible"]))
        self.assertFalse(bool(offset6["profit_barrier_calibration_ok"]))
        self.assertTrue(bool(offset8["eligible"]))
        self.assertEqual(summary.iloc[0]["short_entry_threshold_offset"], 8)

    def test_candidate_selection_can_gate_smoothed_profit_barrier_calibration_overestimate(self):
        def fold(values):
            rows = []
            for offset, pnl, smoothed_overestimate in values:
                rows.append(
                    {
                        "policy": "fixed_horizon_ev",
                        "entry_threshold": 0,
                        "long_entry_threshold_offset": 0,
                        "short_entry_threshold_offset": offset,
                        "exit_threshold": 0,
                        "side_margin": 1,
                        "risk_penalty": 0,
                        "max_wait_regret": 4,
                        "min_entry_rank": 0.5,
                        "require_profit_barrier": "True",
                        "profit_barrier_threshold": 0.4,
                        "extra_side_margin_rules": "",
                        "side_extra_margin_rules": "",
                        "side_block_rules": "",
                        "block_trend_regimes": "",
                        "block_volatility_regimes": "",
                        "block_session_regimes": "",
                        "block_gap_regimes": "",
                        "block_combined_regimes": "",
                        "total_adjusted_pnl": pnl,
                        "total_raw_pnl": pnl + 5,
                        "trade_count": 30,
                        "win_rate": 0.6,
                        "max_drawdown": 40,
                        "forced_exit_rate": 0.0,
                        "forced_exit_count": 0,
                        "long_adjusted_pnl": 20,
                        "short_adjusted_pnl": 10,
                        "profit_barrier_calibration_observed_count": 30,
                        "profit_barrier_calibration_bucket_count": 2,
                        "profit_barrier_calibration_overestimate_max": 0.1,
                        "profit_barrier_calibration_overestimate_smoothed_max": (
                            smoothed_overestimate
                        ),
                        "profit_barrier_calibration_abs_error_max": smoothed_overestimate,
                        "worst_profit_barrier_calibration_bucket": "0.6-0.8",
                        "worst_profit_barrier_calibration_bucket_count": 10,
                        "worst_profit_barrier_calibration_predicted_mean": 0.7,
                        "worst_profit_barrier_calibration_actual_hit_rate": 0.6,
                        "worst_profit_barrier_calibration_actual_hit_rate_smoothed": (
                            0.7 - smoothed_overestimate
                        ),
                        "worst_profit_barrier_calibration_overestimate": 0.1,
                        "worst_profit_barrier_calibration_overestimate_smoothed": (
                            smoothed_overestimate
                        ),
                    }
                )
            return pd.DataFrame(rows)

        base_a = fold([(6, 40, 0.32), (8, 32, 0.10)])
        base_b = fold([(6, 38, 0.31), (8, 30, 0.12)])
        cost_a = fold([(6, 30, 0.34), (8, 24, 0.13)])
        cost_b = fold([(6, 29, 0.33), (8, 23, 0.11)])

        summary = summarize_candidate_selection(
            base_frames=[base_a, base_b],
            cost_frames=[cost_a, cost_b],
            min_folds=2,
            min_trades_per_fold=20,
            max_forced_exit_rate=0.0,
            max_drawdown=100.0,
            min_base_adjusted_pnl_per_fold=0.0,
            min_cost_adjusted_pnl_per_fold=0.0,
            max_cost_pnl_drop=20.0,
            max_side_loss_per_fold=20.0,
            max_smoothed_profit_barrier_calibration_overestimate=0.2,
            plateau_column="short_entry_threshold_offset",
            plateau_radius=2.0,
            min_plateau_neighbors=0,
        )

        offset6 = summary[summary["short_entry_threshold_offset"] == 6].iloc[0]
        offset8 = summary[summary["short_entry_threshold_offset"] == 8].iloc[0]
        self.assertFalse(bool(offset6["eligible"]))
        self.assertFalse(bool(offset6["smoothed_profit_barrier_calibration_ok"]))
        self.assertTrue(bool(offset8["eligible"]))
        self.assertEqual(summary.iloc[0]["short_entry_threshold_offset"], 8)

    def test_candidate_selection_can_gate_short_trade_share(self):
        def fold(values):
            rows = []
            for offset, pnl, short_share in values:
                long_count = int(round(30 * (1 - short_share)))
                short_count = 30 - long_count
                rows.append(
                    {
                        "policy": "fixed_horizon_ev",
                        "entry_threshold": 0,
                        "long_entry_threshold_offset": 0,
                        "short_entry_threshold_offset": offset,
                        "exit_threshold": 0,
                        "side_margin": 1,
                        "risk_penalty": 0,
                        "max_wait_regret": 4,
                        "min_entry_rank": 0.5,
                        "require_profit_barrier": "True",
                        "profit_barrier_threshold": 0.4,
                        "extra_side_margin_rules": "",
                        "side_extra_margin_rules": "",
                        "side_block_rules": "",
                        "block_trend_regimes": "",
                        "block_volatility_regimes": "",
                        "block_session_regimes": "",
                        "block_gap_regimes": "",
                        "block_combined_regimes": "",
                        "total_adjusted_pnl": pnl,
                        "total_raw_pnl": pnl + 5,
                        "trade_count": 30,
                        "win_rate": 0.6,
                        "max_drawdown": 40,
                        "forced_exit_rate": 0.0,
                        "forced_exit_count": 0,
                        "long_adjusted_pnl": 20,
                        "short_adjusted_pnl": 10,
                        "long_trade_count": long_count,
                        "short_trade_count": short_count,
                        "long_trade_share": long_count / 30,
                        "short_trade_share": short_count / 30,
                        "max_side_trade_share": max(long_count, short_count) / 30,
                    }
                )
            return pd.DataFrame(rows)

        base_a = fold([(6, 40, 0.9), (8, 32, 0.4)])
        base_b = fold([(6, 38, 0.86), (8, 30, 0.43)])
        cost_a = fold([(6, 30, 0.9), (8, 24, 0.4)])
        cost_b = fold([(6, 29, 0.86), (8, 23, 0.43)])

        summary = summarize_candidate_selection(
            base_frames=[base_a, base_b],
            cost_frames=[cost_a, cost_b],
            min_folds=2,
            min_trades_per_fold=20,
            max_forced_exit_rate=0.0,
            max_drawdown=100.0,
            min_base_adjusted_pnl_per_fold=0.0,
            min_cost_adjusted_pnl_per_fold=0.0,
            max_cost_pnl_drop=20.0,
            max_side_loss_per_fold=20.0,
            max_short_trade_share=0.8,
            plateau_column="short_entry_threshold_offset",
            plateau_radius=2.0,
            min_plateau_neighbors=0,
        )

        offset6 = summary[summary["short_entry_threshold_offset"] == 6].iloc[0]
        offset8 = summary[summary["short_entry_threshold_offset"] == 8].iloc[0]
        self.assertFalse(bool(offset6["eligible"]))
        self.assertFalse(bool(offset6["short_trade_share_ok"]))
        self.assertTrue(bool(offset8["eligible"]))
        self.assertEqual(summary.iloc[0]["short_entry_threshold_offset"], 8)

    def test_candidate_selection_can_gate_trade_analysis_diagnostics(self):
        def fold(values):
            rows = []
            for offset, pnl, direction_error, exit_regret, ev_overestimate in values:
                rows.append(
                    {
                        "policy": "fixed_horizon_ev",
                        "entry_threshold": 0,
                        "long_entry_threshold_offset": 0,
                        "short_entry_threshold_offset": offset,
                        "exit_threshold": 0,
                        "side_margin": 1,
                        "risk_penalty": 0,
                        "max_wait_regret": 4,
                        "min_entry_rank": 0.5,
                        "require_profit_barrier": "True",
                        "profit_barrier_threshold": 0.4,
                        "extra_side_margin_rules": "",
                        "side_extra_margin_rules": "",
                        "side_block_rules": "",
                        "block_trend_regimes": "",
                        "block_volatility_regimes": "",
                        "block_session_regimes": "",
                        "block_gap_regimes": "",
                        "block_combined_regimes": "",
                        "total_adjusted_pnl": pnl,
                        "total_raw_pnl": pnl + 5,
                        "trade_count": 30,
                        "win_rate": 0.6,
                        "max_drawdown": 40,
                        "forced_exit_rate": 0.0,
                        "forced_exit_count": 0,
                        "long_adjusted_pnl": 20,
                        "short_adjusted_pnl": 10,
                        "direction_error_rate": direction_error,
                        "predicted_side_error_rate": direction_error,
                        "no_edge_rate": 0.1,
                        "exit_regret_mean": exit_regret,
                        "ev_overestimate_vs_realized_mean": ev_overestimate,
                    }
                )
            return pd.DataFrame(rows)

        base_a = fold([(6, 45, 0.70, 25.0, 18.0), (8, 30, 0.35, 8.0, 6.0)])
        base_b = fold([(6, 43, 0.65, 23.0, 17.0), (8, 28, 0.34, 9.0, 7.0)])
        cost_a = fold([(6, 35, 0.72, 26.0, 19.0), (8, 24, 0.36, 10.0, 8.0)])
        cost_b = fold([(6, 33, 0.66, 24.0, 18.0), (8, 22, 0.32, 9.0, 7.0)])

        summary = summarize_candidate_selection(
            base_frames=[base_a, base_b],
            cost_frames=[cost_a, cost_b],
            min_folds=2,
            min_trades_per_fold=20,
            max_forced_exit_rate=0.0,
            max_drawdown=100.0,
            min_base_adjusted_pnl_per_fold=0.0,
            min_cost_adjusted_pnl_per_fold=0.0,
            max_cost_pnl_drop=20.0,
            max_side_loss_per_fold=20.0,
            max_direction_error_rate=0.5,
            max_predicted_side_error_rate=0.5,
            max_exit_regret_mean=15.0,
            max_ev_overestimate_vs_realized_mean=10.0,
            plateau_column="short_entry_threshold_offset",
            plateau_radius=2.0,
            min_plateau_neighbors=0,
        )

        offset6 = summary[summary["short_entry_threshold_offset"] == 6].iloc[0]
        offset8 = summary[summary["short_entry_threshold_offset"] == 8].iloc[0]
        self.assertFalse(bool(offset6["eligible"]))
        self.assertFalse(bool(offset6["direction_error_rate_ok"]))
        self.assertFalse(bool(offset6["exit_regret_ok"]))
        self.assertFalse(bool(offset6["ev_overestimate_vs_realized_ok"]))
        self.assertTrue(bool(offset8["eligible"]))
        self.assertEqual(summary.iloc[0]["short_entry_threshold_offset"], 8)

    def test_candidate_selection_can_soft_penalize_combined_diagnostics(self):
        def fold(values):
            rows = []
            for offset, pnl, direction_error, actual_miss, ev_overestimate in values:
                rows.append(
                    {
                        "policy": "fixed_horizon_ev",
                        "entry_threshold": 0,
                        "long_entry_threshold_offset": 0,
                        "short_entry_threshold_offset": offset,
                        "exit_threshold": 0,
                        "side_margin": 1,
                        "risk_penalty": 0,
                        "max_wait_regret": 4,
                        "min_entry_rank": 0.5,
                        "require_profit_barrier": "True",
                        "profit_barrier_threshold": 0.4,
                        "extra_side_margin_rules": "",
                        "side_extra_margin_rules": "",
                        "side_block_rules": "",
                        "block_trend_regimes": "",
                        "block_volatility_regimes": "",
                        "block_session_regimes": "",
                        "block_gap_regimes": "",
                        "block_combined_regimes": "",
                        "total_adjusted_pnl": pnl,
                        "total_raw_pnl": pnl + 5,
                        "trade_count": 30,
                        "win_rate": 0.6,
                        "max_drawdown": 40,
                        "forced_exit_rate": 0.0,
                        "forced_exit_count": 0,
                        "long_adjusted_pnl": 20,
                        "short_adjusted_pnl": 10,
                        "direction_error_rate": direction_error,
                        "actual_profit_barrier_miss_rate_smoothed": actual_miss,
                        "ev_overestimate_vs_realized_mean": ev_overestimate,
                    }
                )
            return pd.DataFrame(rows)

        base_a = fold([(6, 80, 0.70, 0.70, 20.0), (8, 45, 0.35, 0.45, 8.0)])
        base_b = fold([(6, 78, 0.65, 0.68, 18.0), (8, 44, 0.36, 0.44, 9.0)])
        cost_a = fold([(6, 60, 0.72, 0.72, 21.0), (8, 35, 0.36, 0.46, 8.0)])
        cost_b = fold([(6, 58, 0.66, 0.69, 19.0), (8, 34, 0.34, 0.45, 9.0)])

        summary = summarize_candidate_selection(
            base_frames=[base_a, base_b],
            cost_frames=[cost_a, cost_b],
            min_folds=2,
            min_trades_per_fold=20,
            max_forced_exit_rate=0.0,
            max_drawdown=100.0,
            min_base_adjusted_pnl_per_fold=0.0,
            min_cost_adjusted_pnl_per_fold=0.0,
            max_cost_pnl_drop=30.0,
            max_side_loss_per_fold=20.0,
            diagnostic_penalty_weight=1.0,
            diagnostic_direction_error_rate_threshold=0.4,
            diagnostic_actual_profit_barrier_miss_rate_threshold=0.5,
            diagnostic_ev_overestimate_vs_realized_mean_threshold=10.0,
            plateau_column="short_entry_threshold_offset",
            plateau_radius=2.0,
            min_plateau_neighbors=0,
        )

        offset6 = summary[summary["short_entry_threshold_offset"] == 6].iloc[0]
        offset8 = summary[summary["short_entry_threshold_offset"] == 8].iloc[0]
        self.assertTrue(bool(offset6["eligible"]))
        self.assertTrue(bool(offset8["eligible"]))
        self.assertAlmostEqual(offset6["diagnostic_penalty"], 65.0)
        self.assertAlmostEqual(offset8["diagnostic_penalty"], 0.0)
        self.assertAlmostEqual(offset6["robust_total_adjusted_pnl_min_cost"], -7.0)
        self.assertAlmostEqual(offset8["robust_total_adjusted_pnl_min_cost"], 34.0)
        self.assertEqual(summary.iloc[0]["short_entry_threshold_offset"], 8)

    def test_candidate_selection_can_rank_near_top_by_risk_proxy(self):
        def fold(values):
            rows = []
            for offset, pnl, drawdown, direction_session_pnl, ev_overestimate, exit_regret in values:
                rows.append(
                    {
                        "policy": "timed_ev",
                        "entry_threshold": 15,
                        "long_entry_threshold_offset": 0,
                        "short_entry_threshold_offset": offset,
                        "exit_threshold": 0,
                        "side_margin": 5,
                        "risk_penalty": 0,
                        "max_wait_regret": float("inf"),
                        "min_entry_rank": 0.5,
                        "require_profit_barrier": "False",
                        "extra_side_margin_rules": "",
                        "side_extra_margin_rules": "",
                        "side_block_rules": "",
                        "block_trend_regimes": "",
                        "block_volatility_regimes": "",
                        "block_session_regimes": "",
                        "block_gap_regimes": "",
                        "block_combined_regimes": "",
                        "total_adjusted_pnl": pnl,
                        "total_raw_pnl": pnl + 5,
                        "trade_count": 30,
                        "win_rate": 0.6,
                        "max_drawdown": drawdown,
                        "forced_exit_rate": 0.0,
                        "forced_exit_count": 0,
                        "direction_session_adjusted_pnl_min": direction_session_pnl,
                        "ev_overestimate_vs_realized_mean": ev_overestimate,
                        "exit_regret_mean": exit_regret,
                        "actual_profit_barrier_miss_rate_smoothed": 0.4,
                        "max_side_trade_share": 0.7,
                    }
                )
            return pd.DataFrame(rows)

        high_pnl_high_risk = (6, 90, 80, -60, 20, 18)
        near_top_lower_risk = (8, 84, 20, -8, 8, 6)
        base_a = fold([high_pnl_high_risk, near_top_lower_risk])
        base_b = fold([(6, 88, 76, -55, 18, 16), (8, 83, 22, -9, 7, 5)])
        cost_a = fold([(6, 80, 82, -62, 21, 19), (8, 75, 21, -10, 8, 6)])
        cost_b = fold([(6, 79, 78, -58, 19, 17), (8, 74, 23, -11, 7, 5)])

        default_summary = summarize_candidate_selection(
            base_frames=[base_a, base_b],
            cost_frames=[cost_a, cost_b],
            min_folds=2,
            min_trades_per_fold=20,
            max_forced_exit_rate=0.0,
            max_drawdown=100.0,
            min_base_adjusted_pnl_per_fold=0.0,
            min_cost_adjusted_pnl_per_fold=0.0,
            max_cost_pnl_drop=20.0,
            max_side_loss_per_fold=100.0,
            plateau_column="short_entry_threshold_offset",
            plateau_radius=2.0,
            min_plateau_neighbors=0,
        )
        risk_summary = summarize_candidate_selection(
            base_frames=[base_a, base_b],
            cost_frames=[cost_a, cost_b],
            min_folds=2,
            min_trades_per_fold=20,
            max_forced_exit_rate=0.0,
            max_drawdown=100.0,
            min_base_adjusted_pnl_per_fold=0.0,
            min_cost_adjusted_pnl_per_fold=0.0,
            max_cost_pnl_drop=20.0,
            max_side_loss_per_fold=100.0,
            plateau_column="short_entry_threshold_offset",
            plateau_radius=2.0,
            min_plateau_neighbors=0,
            candidate_rank_mode="near_top_risk",
            near_top_cost_pnl_tolerance=10.0,
        )

        self.assertEqual(default_summary.iloc[0]["short_entry_threshold_offset"], 6)
        self.assertEqual(risk_summary.iloc[0]["short_entry_threshold_offset"], 8)
        self.assertTrue(bool(risk_summary.iloc[0]["near_top_cost_pnl_ok"]))
        self.assertLess(
            risk_summary.iloc[0]["near_top_risk_score"],
            risk_summary.iloc[1]["near_top_risk_score"],
        )

    def test_candidate_selection_can_rank_stress_score_with_cost_sum_reward(self):
        def fold(values):
            rows = []
            for offset, pnl, drawdown in values:
                rows.append(
                    {
                        "policy": "timed_ev",
                        "entry_threshold": 15,
                        "long_entry_threshold_offset": 0,
                        "short_entry_threshold_offset": offset,
                        "exit_threshold": 0,
                        "side_margin": 5,
                        "risk_penalty": 0,
                        "max_wait_regret": float("inf"),
                        "min_entry_rank": 0.5,
                        "require_profit_barrier": "False",
                        "extra_side_margin_rules": "",
                        "side_extra_margin_rules": "",
                        "side_block_rules": "",
                        "block_trend_regimes": "",
                        "block_volatility_regimes": "",
                        "block_session_regimes": "",
                        "block_gap_regimes": "",
                        "block_combined_regimes": "",
                        "total_adjusted_pnl": pnl,
                        "total_raw_pnl": pnl + 5,
                        "trade_count": 30,
                        "win_rate": 0.6,
                        "max_drawdown": drawdown,
                        "forced_exit_rate": 0.0,
                        "forced_exit_count": 0,
                        "direction_session_adjusted_pnl_min": 0.0,
                        "ev_overestimate_vs_realized_mean": 5.0,
                        "exit_regret_mean": 5.0,
                        "actual_profit_barrier_miss_rate_smoothed": 0.4,
                        "max_side_trade_share": 0.7,
                    }
                )
            return pd.DataFrame(rows)

        base_a = fold([(6, 90, 20), (8, 86, 20)])
        base_b = fold([(6, 88, 20), (8, 84, 20)])
        cost_a = fold([(6, 82, 20), (8, 150, 20)])
        cost_b = fold([(6, 80, 20), (8, 75, 20)])

        default_summary = summarize_candidate_selection(
            base_frames=[base_a, base_b],
            cost_frames=[cost_a, cost_b],
            min_folds=2,
            min_trades_per_fold=20,
            max_forced_exit_rate=0.0,
            max_drawdown=100.0,
            min_base_adjusted_pnl_per_fold=0.0,
            min_cost_adjusted_pnl_per_fold=0.0,
            max_cost_pnl_drop=20.0,
            max_side_loss_per_fold=100.0,
            plateau_column="short_entry_threshold_offset",
            plateau_radius=2.0,
            min_plateau_neighbors=0,
        )
        stress_summary = summarize_candidate_selection(
            base_frames=[base_a, base_b],
            cost_frames=[cost_a, cost_b],
            min_folds=2,
            min_trades_per_fold=20,
            max_forced_exit_rate=0.0,
            max_drawdown=100.0,
            min_base_adjusted_pnl_per_fold=0.0,
            min_cost_adjusted_pnl_per_fold=0.0,
            max_cost_pnl_drop=20.0,
            max_side_loss_per_fold=100.0,
            plateau_column="short_entry_threshold_offset",
            plateau_radius=2.0,
            min_plateau_neighbors=0,
            candidate_rank_mode="stress_score",
            near_top_cost_pnl_tolerance=10.0,
            stress_cost_pnl_sum_reward_weight=1.0,
        )

        self.assertEqual(default_summary.iloc[0]["short_entry_threshold_offset"], 6)
        self.assertEqual(stress_summary.iloc[0]["short_entry_threshold_offset"], 8)
        self.assertTrue(bool(stress_summary.iloc[0]["near_top_cost_pnl_ok"]))
        self.assertGreater(
            stress_summary.iloc[0]["total_adjusted_pnl_sum_cost"],
            stress_summary.iloc[1]["total_adjusted_pnl_sum_cost"],
        )
        self.assertLess(
            stress_summary.iloc[0]["stress_risk_score"],
            stress_summary.iloc[1]["stress_risk_score"],
        )

    def test_candidate_selection_can_rank_near_top_by_pnl_stability(self):
        def fold(values):
            rows = []
            for offset, pnl in values:
                rows.append(
                    {
                        "policy": "timed_ev",
                        "entry_threshold": 15,
                        "long_entry_threshold_offset": 0,
                        "short_entry_threshold_offset": offset,
                        "exit_threshold": 0,
                        "side_margin": 5,
                        "risk_penalty": 0,
                        "max_wait_regret": float("inf"),
                        "min_entry_rank": 0.5,
                        "require_profit_barrier": "False",
                        "extra_side_margin_rules": "",
                        "side_extra_margin_rules": "",
                        "side_block_rules": "",
                        "block_trend_regimes": "",
                        "block_volatility_regimes": "",
                        "block_session_regimes": "",
                        "block_gap_regimes": "",
                        "block_combined_regimes": "",
                        "total_adjusted_pnl": pnl,
                        "total_raw_pnl": pnl + 5,
                        "trade_count": 30,
                        "win_rate": 0.6,
                        "max_drawdown": 20,
                        "forced_exit_rate": 0.0,
                        "forced_exit_count": 0,
                        "direction_session_adjusted_pnl_min": 0.0,
                        "ev_overestimate_vs_realized_mean": 5.0,
                        "exit_regret_mean": 5.0,
                        "actual_profit_barrier_miss_rate_smoothed": 0.4,
                        "max_side_trade_share": 0.7,
                    }
                )
            return pd.DataFrame(rows)

        base_a = fold([(6, 150), (8, 86)])
        base_b = fold([(6, 50), (8, 84)])
        cost_a = fold([(6, 100), (8, 79)])
        cost_b = fold([(6, 80), (8, 78)])

        default_summary = summarize_candidate_selection(
            base_frames=[base_a, base_b],
            cost_frames=[cost_a, cost_b],
            min_folds=2,
            min_trades_per_fold=20,
            max_forced_exit_rate=0.0,
            max_drawdown=100.0,
            min_base_adjusted_pnl_per_fold=0.0,
            min_cost_adjusted_pnl_per_fold=0.0,
            max_cost_pnl_drop=100.0,
            max_side_loss_per_fold=100.0,
            plateau_column="short_entry_threshold_offset",
            plateau_radius=2.0,
            min_plateau_neighbors=0,
        )
        stability_summary = summarize_candidate_selection(
            base_frames=[base_a, base_b],
            cost_frames=[cost_a, cost_b],
            min_folds=2,
            min_trades_per_fold=20,
            max_forced_exit_rate=0.0,
            max_drawdown=100.0,
            min_base_adjusted_pnl_per_fold=0.0,
            min_cost_adjusted_pnl_per_fold=0.0,
            max_cost_pnl_drop=100.0,
            max_side_loss_per_fold=100.0,
            plateau_column="short_entry_threshold_offset",
            plateau_radius=2.0,
            min_plateau_neighbors=0,
            candidate_rank_mode="near_top_risk",
            near_top_cost_pnl_tolerance=5.0,
            near_top_pnl_stability_weight=1.0,
        )

        self.assertEqual(default_summary.iloc[0]["short_entry_threshold_offset"], 6)
        self.assertEqual(stability_summary.iloc[0]["short_entry_threshold_offset"], 8)
        self.assertGreater(
            stability_summary.iloc[1]["pnl_stability_risk_all"],
            stability_summary.iloc[0]["pnl_stability_risk_all"],
        )
        self.assertLess(
            stability_summary.iloc[0]["near_top_risk_score"],
            stability_summary.iloc[1]["near_top_risk_score"],
        )

    def test_candidate_selection_jackknife_evaluates_left_out_fold(self):
        def fold(month, values):
            rows = []
            for offset, pnl in values:
                rows.append(
                    {
                        "policy": "timed_ev",
                        "entry_threshold": 12,
                        "long_entry_threshold_offset": 0,
                        "short_entry_threshold_offset": offset,
                        "exit_threshold": 0,
                        "side_margin": 5,
                        "risk_penalty": 0,
                        "max_wait_regret": float("inf"),
                        "min_entry_rank": 0.5,
                        "require_profit_barrier": "False",
                        "extra_side_margin_rules": "",
                        "side_extra_margin_rules": "",
                        "side_block_rules": "",
                        "block_trend_regimes": "",
                        "block_volatility_regimes": "",
                        "block_session_regimes": "",
                        "block_gap_regimes": "",
                        "block_combined_regimes": "",
                        "side_ev_penalty_rules": "",
                        "period_start": f"{month}-01T00:00:00+00:00",
                        "total_adjusted_pnl": pnl,
                        "total_raw_pnl": pnl + 5,
                        "trade_count": 30,
                        "win_rate": 0.6,
                        "max_drawdown": 20,
                        "forced_exit_rate": 0.0,
                        "forced_exit_count": 0,
                        "direction_session_adjusted_pnl_min": 0.0,
                        "ev_overestimate_vs_realized_mean": 5.0,
                        "exit_regret_mean": 5.0,
                        "actual_profit_barrier_miss_rate_smoothed": 0.4,
                        "max_side_trade_share": 0.7,
                    }
                )
            return pd.DataFrame(rows)

        base_frames = [
            fold("2024-01", [(6, 100), (8, 90)]),
            fold("2024-02", [(6, 95), (8, 90)]),
            fold("2024-03", [(6, -10), (8, 85)]),
        ]
        cost_frames = [
            fold("2024-01", [(6, 90), (8, 80)]),
            fold("2024-02", [(6, 85), (8, 80)]),
            fold("2024-03", [(6, -20), (8, 75)]),
        ]
        summary = summarize_candidate_selection_jackknife(
            base_frames=base_frames,
            cost_frames=cost_frames,
            selection_config={
                "min_folds": 3,
                "min_base_folds": 3,
                "min_cost_folds": 3,
                "min_trades_per_fold": 20,
                "max_forced_exit_rate": 0.0,
                "max_drawdown": 100.0,
                "min_base_adjusted_pnl_per_fold": 0.0,
                "min_cost_adjusted_pnl_per_fold": 0.0,
                "max_cost_pnl_drop": 100.0,
                "max_side_loss_per_fold": 100.0,
                "plateau_column": "short_entry_threshold_offset",
                "plateau_radius": 2.0,
                "min_plateau_neighbors": 0,
            },
        )

        self.assertEqual(set(summary["left_out_fold"]), {"2024-01", "2024-02", "2024-03"})
        held_out_march = summary.loc[summary["left_out_fold"] == "2024-03"].iloc[0]
        self.assertEqual(held_out_march["short_entry_threshold_offset"], 6)
        self.assertEqual(held_out_march["holdout_cost_total_adjusted_pnl_min"], -20)
        self.assertFalse(bool(held_out_march["holdout_pass"]))
        self.assertFalse(bool(held_out_march["matches_full_top"]))

    def test_holdout_run_frame_reads_model_policy_config_keys(self):
        with TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            (run_dir / "config.json").write_text(
                """
{
  "model_policy_config": {
    "predictions": "predictions.parquet",
    "policy": "timed_ev",
    "entry_threshold": 15.0,
    "short_entry_threshold_offset": 4.0,
    "side_margin": 5.0,
    "max_predicted_hold_minutes": 480.0,
    "min_entry_rank": 0.5,
    "side_ev_penalty_rules": ["long:session_regime=ny_late:15"]
  }
}
""".strip(),
                encoding="utf-8",
            )
            (run_dir / "metrics.json").write_text(
                """
{
  "strategy": "model_timed_ev",
  "period_start": "2025-02-01T00:00:00+00:00",
  "period_end": "2025-03-01T00:00:00+00:00",
  "total_adjusted_pnl": 12.0,
  "total_raw_pnl": 15.0,
  "trade_count": 3,
  "win_rate": 0.6666666667,
  "max_drawdown": 4.0,
  "forced_exit_count": 0
}
""".strip(),
                encoding="utf-8",
            )

            frame = read_holdout_run_frame(run_dir)

        row = frame.iloc[0]
        self.assertEqual(row["policy"], "timed_ev")
        self.assertEqual(row["entry_threshold"], 15.0)
        self.assertEqual(row["short_entry_threshold_offset"], 4.0)
        self.assertEqual(row["max_predicted_hold_minutes"], 480.0)
        self.assertEqual(row["min_entry_rank"], 0.5)
        self.assertEqual(row["side_ev_penalty_rules"], "long:session_regime=ny_late:15")
        self.assertAlmostEqual(row["forced_exit_rate"], 0.0)

    def test_holdout_run_frame_reads_model_sweep_metrics_grid(self):
        with TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            (run_dir / "config.json").write_text("{}", encoding="utf-8")
            pd.DataFrame(
                [
                    {
                        "policy": "timed_ev",
                        "entry_threshold": 12,
                        "long_entry_threshold_offset": 0,
                        "short_entry_threshold_offset": 6,
                        "exit_threshold": 0,
                        "side_margin": 5,
                        "risk_penalty": 0,
                        "max_wait_regret": float("inf"),
                        "min_entry_rank": 0.5,
                        "require_profit_barrier": "False",
                        "side_ev_penalty_rules": "",
                        "period_start": "2025-03-01T00:00:00+00:00",
                        "period_end": "2025-04-01T00:00:00+00:00",
                        "total_adjusted_pnl": 12.0,
                        "total_raw_pnl": 15.0,
                        "trade_count": 30,
                        "win_rate": 0.55,
                        "max_drawdown": 20.0,
                        "forced_exit_count": 0,
                    },
                    {
                        "policy": "timed_ev",
                        "entry_threshold": 12,
                        "long_entry_threshold_offset": 0,
                        "short_entry_threshold_offset": 6,
                        "exit_threshold": 0,
                        "side_margin": 5,
                        "risk_penalty": 0,
                        "max_wait_regret": float("inf"),
                        "min_entry_rank": 0.5,
                        "require_profit_barrier": "False",
                        "side_ev_penalty_rules": "short:combined_regime=up_low_vol:10",
                        "period_start": "2025-03-01T00:00:00+00:00",
                        "period_end": "2025-04-01T00:00:00+00:00",
                        "total_adjusted_pnl": 18.0,
                        "total_raw_pnl": 21.0,
                        "trade_count": 32,
                        "win_rate": 0.58,
                        "max_drawdown": 18.0,
                        "forced_exit_count": 0,
                    },
                ]
            ).to_csv(run_dir / "metrics.csv", index=False)

            frame = read_holdout_run_frame(run_dir)

        self.assertEqual(len(frame), 2)
        self.assertEqual(frame.iloc[0]["policy"], "timed_ev")
        self.assertEqual(frame.iloc[1]["side_ev_penalty_rules"], "short:combined_regime=up_low_vol:10")
        self.assertAlmostEqual(frame.iloc[0]["forced_exit_rate"], 0.0)
        self.assertEqual(frame.iloc[0]["holdout_run"], str(run_dir))

    def test_holdout_audit_requires_all_holdout_cases_to_pass(self):
        def holdout(month, values):
            rows = []
            for offset, pnl in values:
                rows.append(
                    {
                        "policy": "timed_ev",
                        "entry_threshold": 15,
                        "long_entry_threshold_offset": 0,
                        "short_entry_threshold_offset": offset,
                        "exit_threshold": 0,
                        "side_margin": 5,
                        "risk_penalty": 0,
                        "max_wait_regret": float("inf"),
                        "min_entry_rank": 0.5,
                        "require_profit_barrier": "False",
                        "extra_side_margin_rules": "",
                        "side_extra_margin_rules": "",
                        "side_block_rules": "",
                        "block_trend_regimes": "",
                        "block_volatility_regimes": "",
                        "block_session_regimes": "",
                        "block_gap_regimes": "",
                        "block_combined_regimes": "",
                        "period_start": f"{month}-01T00:00:00+00:00",
                        "period_end": f"{month}-28T00:00:00+00:00",
                        "total_adjusted_pnl": pnl,
                        "total_raw_pnl": pnl + 5,
                        "trade_count": 20,
                        "win_rate": 0.55,
                        "max_drawdown": 30,
                        "forced_exit_rate": 0.0,
                        "forced_exit_count": 0,
                    }
                )
            return pd.DataFrame(rows)

        validation = pd.DataFrame(
            {
                "policy": ["timed_ev", "timed_ev", "timed_ev"],
                "entry_threshold": [15, 15, 15],
                "long_entry_threshold_offset": [0, 0, 0],
                "short_entry_threshold_offset": [4, 8, 8],
                "exit_threshold": [0, 0, 0],
                "side_margin": [5, 5, 5],
                "risk_penalty": [0, 0, 0],
                "max_wait_regret": [float("inf"), float("inf"), float("inf")],
                "min_entry_rank": [0.5, 0.5, 0.5],
                "require_profit_barrier": ["False", "False", "False"],
                "long_holding_fallback_column": [float("nan"), float("nan"), float("nan")],
                "short_holding_fallback_column": [float("nan"), float("nan"), float("nan")],
                "eligible": [True, True, True],
                "total_adjusted_pnl_min_cost": [40.0, 35.0, 34.0],
            }
        )

        summary = summarize_holdout_audit(
            holdout_frames=[
                holdout("2024-12", [(4, -10), (8, 15)]),
                holdout("2025-02", [(4, 30), (8, 20)]),
            ],
            validation_summary=validation,
            min_holdout_cases=2,
            min_trades_per_case=10,
            max_forced_exit_rate=0.0,
            max_drawdown=100.0,
            min_adjusted_pnl_per_case=0.0,
        )

        top = summary.iloc[0]
        self.assertEqual(top["short_entry_threshold_offset"], 8)
        self.assertTrue(bool(top["audit_eligible"]))
        offset4 = summary[summary["short_entry_threshold_offset"] == 4].iloc[0]
        self.assertFalse(bool(offset4["holdout_eligible"]))
        self.assertEqual(offset4["holdout_case_ok_count"], 1)
        self.assertEqual(summary["short_entry_threshold_offset"].tolist().count(8), 1)

    def test_direction_session_diagnostics_reports_worst_group(self):
        timestamps = pd.date_range("2025-01-01 00:00:00+00:00", periods=3, freq="min")
        trades = pd.DataFrame(
            {
                "direction": ["short", "short", "long"],
                "entry_decision_timestamp": [timestamps[0], timestamps[1], timestamps[2]],
                "adjusted_pnl": [-30.0, -10.0, 5.0],
            }
        )
        predictions = pd.DataFrame(
            {
                "decision_timestamp": timestamps,
                "session_regime": ["asia", "asia", "london"],
            }
        )

        diagnostics = direction_session_diagnostics(trades, predictions)

        self.assertEqual(diagnostics["worst_direction_session"], "short:asia")
        self.assertEqual(diagnostics["worst_direction_session_trade_count"], 2)
        self.assertAlmostEqual(diagnostics["direction_session_adjusted_pnl_min"], -40.0)

    def test_combined_regime_diagnostics_reports_worst_groups(self):
        timestamps = pd.date_range("2025-01-01 00:00:00+00:00", periods=3, freq="min")
        trades = pd.DataFrame(
            {
                "direction": ["long", "long", "short"],
                "entry_decision_timestamp": [timestamps[0], timestamps[1], timestamps[2]],
                "adjusted_pnl": [-20.0, -5.0, -12.0],
            }
        )
        predictions = pd.DataFrame(
            {
                "decision_timestamp": timestamps,
                "combined_regime": ["range_low_vol", "range_low_vol", "up_normal_vol"],
            }
        )

        diagnostics = combined_regime_diagnostics(trades, predictions)

        self.assertEqual(diagnostics["worst_combined_regime"], "range_low_vol")
        self.assertEqual(diagnostics["worst_combined_regime_trade_count"], 2)
        self.assertAlmostEqual(diagnostics["combined_regime_adjusted_pnl_min"], -25.0)
        self.assertEqual(diagnostics["worst_direction_combined_regime"], "long:range_low_vol")
        self.assertEqual(diagnostics["worst_direction_combined_regime_trade_count"], 2)
        self.assertAlmostEqual(diagnostics["direction_combined_regime_adjusted_pnl_min"], -25.0)

    def test_profit_barrier_diagnostics_reports_predicted_and_actual_misses(self):
        timestamps = pd.date_range("2025-01-01 00:00:00+00:00", periods=3, freq="min")
        trades = pd.DataFrame(
            {
                "direction": ["long", "short", "short"],
                "entry_decision_timestamp": [timestamps[0], timestamps[1], timestamps[2]],
                "adjusted_pnl": [12.0, -15.0, -5.0],
            }
        )
        predictions = pd.DataFrame(
            {
                "decision_timestamp": timestamps,
                "pred_long_profit_barrier_hit_prob": [0.6, 0.9, 0.8],
                "pred_short_profit_barrier_hit_prob": [0.7, 0.3, 0.5],
                "long_profit_barrier_hit": [1, 1, 1],
                "short_profit_barrier_hit": [1, 0, 1],
            }
        )
        config = ModelPolicyConfig(
            predictions=Path("unused.parquet"),
            long_profit_barrier_column="pred_long_profit_barrier_hit_prob",
            short_profit_barrier_column="pred_short_profit_barrier_hit_prob",
            profit_barrier_threshold=0.5,
        )

        diagnostics = profit_barrier_diagnostics(trades, predictions, config)

        self.assertEqual(diagnostics["predicted_profit_barrier_observed_count"], 3)
        self.assertEqual(diagnostics["actual_profit_barrier_observed_count"], 3)
        self.assertEqual(diagnostics["predicted_profit_barrier_miss_count"], 1)
        self.assertEqual(diagnostics["actual_profit_barrier_miss_count"], 1)
        self.assertAlmostEqual(diagnostics["predicted_profit_barrier_miss_rate"], 1 / 3)
        self.assertAlmostEqual(diagnostics["actual_profit_barrier_miss_rate"], 1 / 3)
        self.assertAlmostEqual(diagnostics["predicted_profit_barrier_miss_adjusted_pnl"], -15.0)
        self.assertAlmostEqual(diagnostics["actual_profit_barrier_miss_adjusted_pnl"], -15.0)

    def test_profit_barrier_calibration_diagnostics_reports_worst_bucket(self):
        timestamps = pd.date_range("2025-01-01 00:00:00+00:00", periods=4, freq="min")
        trades = pd.DataFrame(
            {
                "direction": ["long", "short", "short", "long"],
                "entry_decision_timestamp": [timestamps[0], timestamps[1], timestamps[2], timestamps[3]],
                "adjusted_pnl": [12.0, -15.0, -5.0, 8.0],
            }
        )
        predictions = pd.DataFrame(
            {
                "decision_timestamp": timestamps,
                "pred_long_profit_barrier_hit_prob": [0.9, 0.2, 0.1, 0.55],
                "pred_short_profit_barrier_hit_prob": [0.2, 0.75, 0.55, 0.1],
                "long_profit_barrier_hit": [1, 1, 1, 0],
                "short_profit_barrier_hit": [1, 0, 0, 1],
            }
        )
        config = ModelPolicyConfig(
            predictions=Path("unused.parquet"),
            long_profit_barrier_column="pred_long_profit_barrier_hit_prob",
            short_profit_barrier_column="pred_short_profit_barrier_hit_prob",
        )

        diagnostics = profit_barrier_calibration_diagnostics(trades, predictions, config)

        self.assertEqual(diagnostics["profit_barrier_calibration_observed_count"], 4)
        self.assertEqual(diagnostics["profit_barrier_calibration_bucket_count"], 3)
        self.assertEqual(diagnostics["worst_profit_barrier_calibration_bucket"], "0.6-0.8")
        self.assertEqual(diagnostics["worst_profit_barrier_calibration_bucket_count"], 1)
        self.assertAlmostEqual(
            diagnostics["worst_profit_barrier_calibration_predicted_mean"], 0.75
        )
        self.assertAlmostEqual(
            diagnostics["worst_profit_barrier_calibration_actual_hit_rate"], 0.0
        )
        self.assertAlmostEqual(
            diagnostics["profit_barrier_calibration_overestimate_max"], 0.75
        )
        self.assertAlmostEqual(
            diagnostics["profit_barrier_calibration_overestimate_smoothed_max"],
            0.75 - (1 / 3),
        )
        self.assertAlmostEqual(
            diagnostics["worst_profit_barrier_calibration_actual_hit_rate_smoothed"],
            1 / 3,
        )
        self.assertAlmostEqual(
            diagnostics["worst_profit_barrier_calibration_overestimate_smoothed"],
            0.75 - (1 / 3),
        )
        self.assertAlmostEqual(
            diagnostics["profit_barrier_calibration_0p4_0p6_predicted_mean"], 0.55
        )
        self.assertAlmostEqual(
            diagnostics["profit_barrier_calibration_0p4_0p6_actual_hit_rate"], 0.0
        )
        self.assertAlmostEqual(
            diagnostics["profit_barrier_calibration_0p4_0p6_actual_hit_rate_smoothed"],
            1 / 4,
        )

    def test_trade_analysis_joins_predictions_and_flags_failures(self):
        timestamps = pd.date_range("2025-01-01 00:00:00+00:00", periods=5, freq="min")
        trades = pd.DataFrame(
            {
                "direction": ["long", "short"],
                "entry_timestamp": [timestamps[1], timestamps[2]],
                "exit_timestamp": [timestamps[3], timestamps[4]],
                "entry_price": [100.0, 105.0],
                "exit_price": [102.0, 107.0],
                "raw_pnl": [2.0, -2.0],
                "adjusted_pnl": [2.0, -2.4],
                "holding_minutes": [2.0, 2.0],
                "exit_reason": ["signal_close", "signal_close"],
                "entry_decision_timestamp": [timestamps[0], timestamps[1]],
                "exit_decision_timestamp": [timestamps[2], timestamps[3]],
            }
        )
        predictions = pd.DataFrame(
            {
                "decision_timestamp": [timestamps[0], timestamps[1]],
                "dataset_month": ["2025-01", "2025-01"],
                "trend_regime": ["up", "down"],
                "volatility_regime": ["normal_vol", "high_vol"],
                "session_regime": ["asia", "london"],
                "gap_regime": ["normal_gap", "normal_gap"],
                "combined_regime": ["up_normal_vol", "down_high_vol"],
                "long_best_adjusted_pnl": [10.0, 5.0],
                "short_best_adjusted_pnl": [3.0, -1.0],
                "long_best_holding_minutes": [5.0, 4.0],
                "short_best_holding_minutes": [6.0, 3.0],
                "long_max_adverse_pnl": [-1.0, -2.0],
                "short_max_adverse_pnl": [-2.0, -3.0],
                "long_profit_barrier_hit": [1, 1],
                "short_profit_barrier_hit": [0, 0],
                "long_wait_regret": [0.0, 1.0],
                "short_wait_regret": [2.0, 4.0],
                "long_entry_local_rank": [0.9, 0.8],
                "short_entry_local_rank": [0.1, 0.2],
                "pred_long_best_adjusted_pnl": [12.0, 4.0],
                "pred_short_best_adjusted_pnl": [2.0, 15.0],
                "pred_long_best_holding_minutes": [4.0, 4.0],
                "pred_short_best_holding_minutes": [6.0, 3.0],
                "pred_long_max_adverse_pnl": [-1.0, -2.0],
                "pred_short_max_adverse_pnl": [-2.0, -3.0],
                "pred_long_wait_regret": [0.0, 2.0],
                "pred_short_wait_regret": [1.0, 2.0],
                "pred_long_entry_local_rank": [0.9, 0.7],
                "pred_short_entry_local_rank": [0.3, 0.4],
                "pred_long_profit_barrier_hit": [1, 1],
                "pred_short_profit_barrier_hit": [0, 1],
            }
        )

        enriched = enrich_trades_with_predictions(trades, predictions)

        self.assertEqual(len(enriched), 2)
        self.assertAlmostEqual(enriched.iloc[0]["actual_taken_best_adjusted_pnl"], 10.0)
        self.assertAlmostEqual(enriched.iloc[0]["exit_regret"], 8.0)
        self.assertFalse(bool(enriched.iloc[0]["direction_error"]))
        self.assertTrue(bool(enriched.iloc[1]["direction_error"]))
        self.assertTrue(bool(enriched.iloc[1]["no_edge_entry"]))
        self.assertAlmostEqual(enriched.iloc[1]["ev_overestimate_vs_oracle"], 16.0)

        summary = trade_analysis_summary(enriched)
        self.assertEqual(summary["trade_count"], 2)
        self.assertEqual(summary["matched_prediction_count"], 2)
        self.assertAlmostEqual(summary["total_adjusted_pnl"], -0.4)

        flags = trade_failure_flags(enriched)
        direction_row = flags[flags["flag"] == "direction_error"].iloc[0]
        self.assertEqual(direction_row["trade_count"], 1)

        grouped = trade_group_summary(enriched, "direction")
        self.assertEqual(set(grouped["direction"]), {"long", "short"})
        regime_grouped = trade_group_summary(enriched, "trend_regime")
        self.assertEqual(set(regime_grouped["trend_regime"]), {"up", "down"})

    def test_model_trade_exposure_reads_run_config_and_groups_regime_exposure(self):
        timestamps = pd.date_range("2024-12-01 00:00:00+00:00", periods=5, freq="min")
        trades = pd.DataFrame(
            {
                "direction": ["long", "short"],
                "entry_timestamp": [timestamps[1], timestamps[2]],
                "exit_timestamp": [timestamps[3], timestamps[4]],
                "entry_price": [100.0, 105.0],
                "exit_price": [102.0, 107.0],
                "raw_pnl": [2.0, -2.0],
                "adjusted_pnl": [2.0, -2.4],
                "holding_minutes": [2.0, 2.0],
                "exit_reason": ["signal_close", "signal_close"],
                "entry_decision_timestamp": [timestamps[0], timestamps[1]],
                "exit_decision_timestamp": [timestamps[2], timestamps[3]],
            }
        )
        predictions = pd.DataFrame(
            {
                "decision_timestamp": [timestamps[0], timestamps[1]],
                "dataset_month": ["2024-12", "2024-12"],
                "trend_regime": ["up", "down"],
                "volatility_regime": ["low_vol", "low_vol"],
                "session_regime": ["london", "asia"],
                "gap_regime": ["normal_gap", "normal_gap"],
                "combined_regime": ["up_low_vol", "down_low_vol"],
                "long_best_adjusted_pnl": [10.0, 1.0],
                "short_best_adjusted_pnl": [2.0, 8.0],
                "long_best_holding_minutes": [5.0, 4.0],
                "short_best_holding_minutes": [6.0, 3.0],
                "long_max_adverse_pnl": [-1.0, -2.0],
                "short_max_adverse_pnl": [-2.0, -3.0],
                "long_profit_barrier_hit": [1, 0],
                "short_profit_barrier_hit": [0, 1],
                "long_wait_regret": [0.0, 1.0],
                "short_wait_regret": [2.0, 0.0],
                "long_entry_local_rank": [0.9, 0.2],
                "short_entry_local_rank": [0.1, 0.8],
                "pred_long_best_adjusted_pnl": [12.0, 2.0],
                "pred_short_best_adjusted_pnl": [2.0, 10.0],
                "pred_long_best_holding_minutes": [4.0, 4.0],
                "pred_short_best_holding_minutes": [6.0, 3.0],
                "pred_long_max_adverse_pnl": [-1.0, -2.0],
                "pred_short_max_adverse_pnl": [-2.0, -3.0],
                "pred_long_wait_regret": [0.0, 2.0],
                "pred_short_wait_regret": [1.0, 0.0],
                "pred_long_entry_local_rank": [0.9, 0.2],
                "pred_short_entry_local_rank": [0.3, 0.8],
                "pred_long_profit_barrier_hit": [1, 0],
                "pred_short_profit_barrier_hit": [0, 1],
            }
        )

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            predictions_path = root / "predictions.parquet"
            predictions.to_parquet(predictions_path)
            run_dir = root / "run_2024-12"
            run_dir.mkdir()
            trades.to_csv(run_dir / "trades.csv", index=False)
            (run_dir / "config.json").write_text(
                json.dumps(
                    {
                        "backtest_config": {
                            "evaluation_start": "2024-12-01T00:00:00+00:00"
                        },
                        "model_policy_config": {
                            "predictions": str(predictions_path),
                            "long_column": "pred_long_best_adjusted_pnl",
                            "short_column": "pred_short_best_adjusted_pnl",
                        },
                    }
                ),
                encoding="utf-8",
            )

            enriched = read_model_trade_exposure_frame(run_dir)
            grouped = trade_exposure_group_summary(
                enriched,
                ["month", "direction", "combined_regime"],
            )

        self.assertEqual(enriched["month"].unique().tolist(), ["2024-12"])
        short_row = grouped[grouped["direction"] == "short"].iloc[0]
        self.assertEqual(short_row["combined_regime"], "down_low_vol")
        self.assertAlmostEqual(short_row["total_adjusted_pnl"], -2.4)
        self.assertAlmostEqual(short_row["trade_share"], 0.5)

    def test_model_trade_delta_compares_added_and_removed_trades_with_gate_quality(self):
        timestamps = pd.date_range("2025-03-01 00:00:00+00:00", periods=8, freq="min")
        base_trades = pd.DataFrame(
            {
                "direction": ["long", "short"],
                "entry_timestamp": [timestamps[1], timestamps[2]],
                "exit_timestamp": [timestamps[3], timestamps[4]],
                "entry_price": [100.0, 110.0],
                "exit_price": [105.0, 102.0],
                "raw_pnl": [5.0, 8.0],
                "adjusted_pnl": [5.0, 8.0],
                "holding_minutes": [2.0, 2.0],
                "exit_reason": ["signal_close", "signal_close"],
                "entry_decision_timestamp": [timestamps[0], timestamps[1]],
                "exit_decision_timestamp": [timestamps[2], timestamps[3]],
            }
        )
        candidate_trades = pd.DataFrame(
            {
                "direction": ["long", "short"],
                "entry_timestamp": [timestamps[1], timestamps[5]],
                "exit_timestamp": [timestamps[3], timestamps[7]],
                "entry_price": [100.0, 120.0],
                "exit_price": [105.0, 124.0],
                "raw_pnl": [5.0, -4.0],
                "adjusted_pnl": [5.0, -4.8],
                "holding_minutes": [2.0, 2.0],
                "exit_reason": ["signal_close", "signal_close"],
                "entry_decision_timestamp": [timestamps[0], timestamps[4]],
                "exit_decision_timestamp": [timestamps[2], timestamps[6]],
            }
        )
        predictions = pd.DataFrame(
            {
                "decision_timestamp": [timestamps[0], timestamps[1], timestamps[4]],
                "dataset_month": ["2025-03", "2025-03", "2025-03"],
                "trend_regime": ["up", "down", "range"],
                "volatility_regime": ["low_vol", "low_vol", "high_vol"],
                "session_regime": ["london", "asia", "ny"],
                "gap_regime": ["normal_gap", "normal_gap", "wide_gap"],
                "combined_regime": ["up_low_vol", "down_low_vol", "range_high_vol"],
                "long_best_adjusted_pnl": [6.0, 1.0, -1.0],
                "short_best_adjusted_pnl": [2.0, 9.0, -2.0],
                "pred_long_best_adjusted_pnl": [7.0, 2.0, 1.0],
                "pred_short_best_adjusted_pnl": [1.0, 10.0, 12.0],
                "pred_stack_long_quality": [6.0, 3.0, -1.0],
                "pred_stack_short_quality": [0.5, -2.0, 4.0],
            }
        )

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            predictions_path = root / "predictions.parquet"
            predictions.to_parquet(predictions_path)
            base_run = root / "base_2025-03"
            candidate_run = root / "candidate_2025-03"
            base_run.mkdir()
            candidate_run.mkdir()
            base_trades.to_csv(base_run / "trades.csv", index=False)
            candidate_trades.to_csv(candidate_run / "trades.csv", index=False)
            config = {
                "backtest_config": {"evaluation_start": "2025-03-01T00:00:00+00:00"},
                "model_policy_config": {
                    "predictions": str(predictions_path),
                    "long_column": "pred_long_best_adjusted_pnl",
                    "short_column": "pred_short_best_adjusted_pnl",
                    "long_trade_quality_column": "pred_stack_long_quality",
                    "short_trade_quality_column": "pred_stack_short_quality",
                    "min_trade_quality": 0.0,
                },
            }
            (base_run / "config.json").write_text(json.dumps(config), encoding="utf-8")
            (candidate_run / "config.json").write_text(json.dumps(config), encoding="utf-8")

            delta = read_model_trade_delta_frames([base_run], [candidate_run])[0]
            grouped = trade_delta_group_summary(delta, ["month", "delta_status"])

        self.assertEqual(delta["delta_status"].value_counts().to_dict(), {
            "common": 1,
            "only_base": 1,
            "only_candidate": 1,
        })
        self.assertAlmostEqual(delta["pnl_delta"].sum(), -12.8)
        removed = delta[delta["delta_status"] == "only_base"].iloc[0]
        self.assertAlmostEqual(removed["base_adjusted_pnl"], 8.0)
        self.assertAlmostEqual(removed["gate_trade_quality_taken"], -2.0)
        added = delta[delta["delta_status"] == "only_candidate"].iloc[0]
        self.assertAlmostEqual(added["candidate_adjusted_pnl"], -4.8)
        self.assertAlmostEqual(added["gate_trade_quality_taken"], 4.0)
        only_base_summary = grouped[grouped["delta_status"] == "only_base"].iloc[0]
        self.assertAlmostEqual(only_base_summary["pnl_delta"], -8.0)

    def test_prepare_analysis_predictions_uses_requested_ev_columns(self):
        timestamps = pd.date_range("2025-01-01 00:00:00+00:00", periods=1, freq="min")
        predictions = pd.DataFrame(
            {
                "decision_timestamp": timestamps,
                "long_best_adjusted_pnl": [1.0],
                "short_best_adjusted_pnl": [2.0],
                "pred_long_best_adjusted_pnl": [10.0],
                "pred_short_best_adjusted_pnl": [20.0],
                "pred_regime_calibrated_long_best_adjusted_pnl": [30.0],
                "pred_regime_calibrated_short_best_adjusted_pnl": [40.0],
            }
        )

        prepared = prepare_analysis_predictions(
            predictions,
            "pred_regime_calibrated_long_best_adjusted_pnl",
            "pred_regime_calibrated_short_best_adjusted_pnl",
        )

        self.assertEqual(prepared["pred_long_best_adjusted_pnl"].tolist(), [30.0])
        self.assertEqual(prepared["pred_short_best_adjusted_pnl"].tolist(), [40.0])


if __name__ == "__main__":
    unittest.main()
