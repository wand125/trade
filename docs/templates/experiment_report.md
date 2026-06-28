# Experiment Report Template

ファイル名: NNNNN_YYYY-MM-DD_slug.md
日時: YYYY-MM-DD HH:MM JST
更新日時: YYYY-MM-DD HH:MM JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- Experiment ID:
- Owner:
- Status:
- Main result:

## Hypothesis

何を検証したか。

## Data

- Source:
- Timeframe:
- Train period:
- Validation period:
- Test period:
- Excluded periods:

## Backtest Spec

- Execution price:
- Max holding:
- Position size:
- PnL adjustment:
- Spread/slippage:

## Features

- Feature set:
- Lookback:
- Normalization:
- Leakage checks:

## Model

- Model type:
- Layers:
- Hidden size:
- Optimizer:
- Loss:
- Learning rate:
- Batch size:
- Epochs:
- Random seed:

## Metrics

| split | adjusted pnl | raw pnl | trades | win rate | profit factor | max drawdown |
|---|---:|---:|---:|---:|---:|---:|
| train | | | | | | |
| validation | | | | | | |
| test | | | | | | |

## Monthly Scores

| month | adjusted pnl | trades | win rate | max drawdown | forced exits |
|---|---:|---:|---:|---:|---:|
| | | | | | |

## Artifacts

- Config:
- Checkpoint:
- Predictions:
- Trades:
- Equity curve:

## Findings

- What worked:
- What failed:
- Overfitting signs:
- Robustness notes:

## Next Actions

- 
