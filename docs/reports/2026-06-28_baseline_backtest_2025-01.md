# Baseline Backtest: 2025-01

## Summary

- Experiment ID: `2026-06-28_baseline_backtest_2025-01`
- Datetime: 2026-06-28 01:58 JST
- Updated: 2026-06-28 08:02 JST
- Status: completed
- Main result: 2025-01 の初期ベースラインは、no trade を除き全て adjusted pnl がマイナス。

## Hypothesis

深層学習に入る前に、単純なルールベース戦略とランダム戦略を同一バックテスト仕様で比較し、最低限の基準点を作る。

## Data

- Source: HistData XAUUSD M1
- Data file: `data/processed/histdata/xauusd/xauusd_m1.parquet`
- Evaluation period: 2025-01-01 00:00 UTC to 2025-02-01 00:00 UTC
- Warmup: 7 days
- Post period: 4 days

## Backtest Spec

- Execution price: next M1 open
- Position size: 1 ounce
- Max holding: 24 hours
- Concurrent positions: 1
- Profit multiplier: 0.9
- Loss multiplier: 1.3
- Spread/slippage: not explicit in this baseline

## Strategies

- `no_trade`
- `random`
- `ma_cross`
- `rsi_reversal`
- `breakout`

## Metrics

| strategy | adjusted pnl | raw pnl | trades | win rate | profit factor | max drawdown | forced exits |
|---|---:|---:|---:|---:|---:|---:|---:|
| no_trade | 0.0000 | 0.000 | 0 | 0.0000 | - | 0.0000 | 0 |
| rsi_reversal | -56.5288 | 181.776 | 1069 | 0.6492 | 0.9210 | 123.4142 | 0 |
| random | -107.9284 | -65.748 | 49 | 0.4082 | 0.3189 | 112.7517 | 1 |
| ma_cross | -279.2953 | -39.229 | 485 | 0.3402 | 0.6478 | 309.5242 | 5 |
| breakout | -311.2774 | -141.790 | 156 | 0.3077 | 0.4785 | 320.3002 | 5 |

## Artifacts

- `data/reports/backtests/20260627_165623_benchmark_2025-01/`

## Findings

- `rsi_reversal` は raw pnl がプラスだが、損失 1.3 倍・利益 0.9 倍補正後はマイナス。
- 補正後損益では、損失の大きさと頻度が勝率より重要になる。
- `ma_cross` と `breakout` は 24 時間強制決済が発生しており、exit 制御が粗い。
- `no_trade` がこの月の最高 adjusted pnl になっているため、学習モデルはまず「取引しない判断」を超える必要がある。

## Next Actions

- future 24h path から、long/short/stay の教師ラベルを作る。
- adjusted pnl だけでなく、最大逆行幅を考慮したラベルを比較する。
- 複数月で同じベースライン表を出し、月依存性を確認する。

