# Executable Model Policy Backtest: 2025-01

日時: 2026-06-28 02:30 JST
更新日時: 2026-06-28 08:02 JST

## Summary

- Experiment ID: `2026-06-28_executable_model_policy_2025-01`
- Status: completed
- Main result: HGB multi-task model predictions were connected to an executable backtest policy, but the selected policy still lost money after adjusted pnl.

## Purpose

The previous HGB report used oracle exits from the label data. This experiment evaluates the same model predictions under the real backtest constraints:

- next M1 open execution
- one open position at a time
- no new entry until the existing position is closed
- max holding 24 hours
- profit multiplier 0.9
- loss multiplier 1.3

## Implementation

Implemented in `src/trade_data/backtest.py`.

New commands:

- `model-policy`: run one executable policy from saved predictions
- `model-sweep`: sweep thresholds on a validation month and save `metrics.csv`

Policies:

- `stateless_ev`: desired position is long/short only when predicted best side EV is above the entry threshold.
- `stateful_ev`: enters from flat when predicted best side EV is above the entry threshold, then holds until the current side EV drops below the exit threshold or the opposite side becomes strong enough.

## Validation Sweep

Validation month: 2024-07

Command:

```bash
python3 -m trade_data.backtest model-sweep \
  --month 2024-07 \
  --predictions experiments/20260627_171852_hgb_multitask_edge15/predictions_valid.parquet \
  --policies stateful_ev,stateless_ev \
  --entry-thresholds 5,10,15,20,25,30 \
  --exit-thresholds=-5,0,5,10 \
  --side-margins 0,5,10 \
  --top-n 12
```

Artifacts:

- `data/reports/backtests/20260627_172832_model_sweep_2024-07/metrics.csv`

Top validation result:

| policy | entry threshold | exit threshold | side margin | adjusted pnl | raw pnl | trades | win rate | max drawdown |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| stateful_ev | 30 | 10 | 5 | -5.4446 | 2.2220 | 11 | 0.5455 | 19.9940 |

No swept setting beat no_trade on validation.

## Test Backtest

The best validation setting was applied once to the test month.

Test month: 2025-01

Command:

```bash
python3 -m trade_data.backtest model-policy \
  --month 2025-01 \
  --predictions experiments/20260627_171852_hgb_multitask_edge15/predictions_test.parquet \
  --policy stateful_ev \
  --entry-threshold 30 \
  --exit-threshold 10 \
  --side-margin 5
```

Artifacts:

- `data/reports/backtests/20260627_172849_model_stateful_ev_2025-01/metrics.json`
- `data/reports/backtests/20260627_172849_model_stateful_ev_2025-01/trades.csv`
- `data/reports/backtests/20260627_172849_model_stateful_ev_2025-01/equity_curve.csv`
- `data/reports/backtests/20260627_172849_model_stateful_ev_2025-01/desired_position.csv`

Metrics:

| metric | value |
|---|---:|
| adjusted pnl | -35.8255 |
| raw pnl | 4.5610 |
| trades | 21 |
| win rate | 0.5714 |
| profit factor | 0.7239 |
| max drawdown | 71.5889 |
| forced exits | 1 |
| avg holding minutes | 599.2857 |
| median holding minutes | 564.0000 |
| long trades | 5 |
| short trades | 16 |

## Baseline Context

2025-01 adjusted pnl:

| strategy | adjusted pnl | trades |
|---|---:|---:|
| no_trade | 0.0000 | 0 |
| model_stateful_ev | -35.8255 | 21 |
| rsi_reversal | -56.5288 | 1069 |
| random | -107.9284 | 49 |
| ma_cross | -279.2953 | 485 |
| breakout | -311.2774 | 156 |

The model policy is better than the initial trading baselines for this month, but it still does not beat no_trade.

## Findings

- Oracle-exit selection metrics were too optimistic for executable trading.
- Raw pnl can be positive while adjusted pnl is negative because the loss multiplier is harsher than the profit multiplier.
- The selected policy traded much less than the default threshold-15 policy, reducing drawdown and loss.
- The current model is not sufficiently calibrated for expected pnl. A high predicted EV threshold was required to reduce overtrading.
- Exit logic is still weak because the model was not directly trained to predict executable exit timing.

## Next Actions

- Add explicit exit timing targets and train a hold/close head.
- Add risk-aware utility using predicted adverse excursion or downside quantiles.
- Calibrate predicted EV on validation periods before thresholding.
- Expand walk-forward validation before moving to larger neural models.
