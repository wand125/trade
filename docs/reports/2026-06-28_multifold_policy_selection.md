# Multi-Fold Policy Selection

日付: 2026-06-28 JST

## 目的

単月 validation の最高スコアに寄せると、翌月 test で崩れやすい。そこで、複数 validation fold の `model-sweep` を同一 policy parameter ごとに集計し、制約を満たす候補から選ぶ。

## 標準フロー

| stage | multiplier | 用途 |
|---|---:|---|
| train / teacher target | profit 0.9, loss 1.3 | 厳しい旧条件で expected pnl target を学習する |
| validation policy selection | profit 1.0, loss 1.25 | no_trade寄りを緩和し、閾値とpolicyを選ぶ |
| final test | profit 1.0, loss 1.25 | validationで固定した設定だけを評価する |

## 実装

追加:

- `src/trade_data/backtest.py`: `model-sweep-summary`
- `tests/test_backtest.py`: sweep正規化と複数fold集計のテスト

集計キー:

- `policy`
- `entry_threshold`
- `exit_threshold`
- `side_margin`
- `risk_penalty`

## Validation Folds

| fold | valid month | model | sweep |
|---|---|---|---|
| A | 2024-07 | `experiments/20260627_174250_hgb_multitask_edge15/` | `data/reports/backtests/20260627_180433_model_sweep_2024-07/` |
| B | 2025-01 | `experiments/20260627_174030_hgb_multitask_edge15/` | `data/reports/backtests/20260627_180029_model_sweep_2025-01/` |

Summary artifact:

- `data/reports/backtests/20260627_180908_model_sweep_summary/`

Summary command:

```bash
python3 -m trade_data.backtest model-sweep-summary \
  --sweeps data/reports/backtests/20260627_180433_model_sweep_2024-07/metrics.csv,data/reports/backtests/20260627_180029_model_sweep_2025-01/metrics.csv \
  --min-folds 2 \
  --min-trades-per-fold 30 \
  --max-forced-exit-rate 0.0 \
  --max-drawdown 100 \
  --min-adjusted-pnl-per-fold 0 \
  --sort-by mean_pnl
```

## Selected Candidate

| policy | entry | exit | side margin | risk | valid mean pnl | valid min pnl | mean trades | max DD | forced exits |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `timed_ev` | 15 | 0 | 5 | 0 | 133.9964 | 120.5680 | 46.0 | 66.4905 | 0 |

この候補は、単月最高ではなく、2つの validation fold で強制決済率0、最低30 trades、各foldプラス、DD 100以下を満たした中で平均P/Lが最大だった。

## Test Diagnostic

2025-02 test に、上記候補を固定適用した。

Artifact:

- `data/reports/backtests/20260627_180701_model_timed_ev_2025-02/`

| metric | value |
|---|---:|
| adjusted pnl | 23.7253 |
| raw pnl | 78.7070 |
| trades | 42 |
| win rate | 0.5000 |
| profit factor | 1.0863 |
| max drawdown | 112.5325 |
| forced exits | 0 |

2025-02 baseline:

| strategy | adjusted pnl |
|---|---:|
| no_trade | 0.0000 |
| random | -14.0078 |
| breakout | -103.0195 |
| ma_cross | -203.7905 |
| rsi_reversal | -296.2607 |

## 判断

no_trade を超える実行可能policyが出た。ただし test の max drawdown は validation制約の 100 を少し超えており、まだ安定モデルではない。

単月 validation 最高の stateful/risk付き設定は 2025-02 test で +6.6193 に落ちたため、単月最適化は採用しない。次は fold を増やし、`timed_ev` の exit timing と calibration を改善する。

## 追加 Fold

2024-09 validation / 2024-10 test のfoldを追加した。

| split | period |
|---|---|
| train | 2023-01 to 2024-08 |
| valid | 2024-09 |
| test | 2024-10 |

Artifacts:

- model: `experiments/20260627_183038_hgb_multitask_edge15/`
- valid sweep: `data/reports/backtests/20260627_183050_model_sweep_2024-09/`
- 3fold summary: `data/reports/backtests/20260627_183241_model_sweep_summary/`
- test policy: `data/reports/backtests/20260627_183253_model_timed_ev_2024-10/`
- test benchmark: `data/reports/backtests/20260627_183253_benchmark_2024-10/`

3fold summary条件:

- folds: 2024-07, 2024-09, 2025-01
- min trades per fold: 30
- max forced exit rate: 0.0
- max drawdown: 100
- min adjusted pnl per fold: 0
- sort: mean adjusted pnl

3foldでも同じ候補が最上位だった。

| policy | entry | exit | side margin | risk | valid mean pnl | valid min pnl | mean trades | max DD | forced exits |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `timed_ev` | 15 | 0 | 5 | 0 | 126.3996 | 111.2060 | 43.3333 | 66.4905 | 0 |

2024-10 test:

| metric | value |
|---|---:|
| adjusted pnl | 48.9555 |
| raw pnl | 99.6620 |
| trades | 43 |
| win rate | 0.6047 |
| profit factor | 1.1931 |
| max drawdown | 77.1468 |
| forced exits | 0 |

2024-10 baseline:

| strategy | adjusted pnl |
|---|---:|
| random | 43.9895 |
| no_trade | 0.0000 |
| breakout | -206.6695 |
| rsi_reversal | -242.5953 |
| ma_cross | -397.3735 |

追加判断:

- 3fold集計で候補が変わらなかったため、`timed_ev entry=15 side_margin=5 risk=0` は現時点の標準候補として維持する。
- 2024-10 test では no_trade と random を上回った。
- ただし signal は long 側に強く偏った。上昇局面依存の可能性があるため、次は short が優勢なfoldを含める。
