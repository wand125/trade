# Trade Failure Analysis

日時: 2026-06-28 06:25 JST

## 目的

学習時間探索はいったん止め、fixed testで負けたtradeを分解する。対象は、1.0/1.2 aligned datasetの低LR1280モデルで、validation上は最も強かった候補。

Model:

- `experiments/20260627_210612_policy_iter1280_lr001_p1_l1p2/`

Validation-selected policy:

- `timed_ev`
- `entry_threshold=15`
- `side_margin=0`
- `risk_penalty=0`
- `max_wait_regret=inf`
- `min_entry_rank=0`
- `require_profit_barrier=true`

Fixed test:

| month | adjusted pnl | raw pnl | trades | win rate | profit factor | max DD | forced exits |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2024-12 | -134.5306 | -101.4610 | 55 | 0.4000 | 0.3220 | 143.4870 | 1 |
| 2025-02 | -110.0922 | -66.1180 | 72 | 0.5278 | 0.5827 | 130.8148 | 0 |

## 実装

`trade-backtest analyze-trades` を追加した。

入力:

- `trades.csv`
- `predictions_test.parquet`

出力:

- `summary.json`
- `enriched_trades.csv`
- `failure_flags.csv`
- `worst_trades.csv`
- `group_by_*.csv`

主な追加列:

- actual/predicted taken EV
- actual/predicted opposite EV
- direction error
- no-edge entry
- predicted side error
- exit regret
- best-side regret
- EV overestimate vs oracle/realized
- barrier hit / wait regret / entry rank buckets

Artifacts:

- `data/reports/backtests/20260627_212215_analyze_lr001_2024-12/`
- `data/reports/backtests/20260627_212215_analyze_lr001_2025-02/`

## Summary

| month | trades | adjusted pnl | long pnl | short pnl | direction error rate | no-edge rate | predicted side error rate | exit regret sum | best-side regret sum | EV overestimate vs realized mean |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2024-12 | 55 | -134.5306 | -70.6460 | -63.8846 | 0.5273 | 0.0364 | 0.5455 | 992.6144 | 1618.8316 | 22.1092 |
| 2025-02 | 72 | -110.0922 | 1.1926 | -111.2848 | 0.4444 | 0.0694 | 0.4444 | 1592.6430 | 2339.5342 | 22.5829 |

読み取り:

- 両月とも、実現PnLに対して予測EVが平均約22ドル過大。
- exit regretが非常に大きく、entry後に理論上は取れた利益を実行policyが逃している。
- 2024-12はlong/short両方が負ける。
- 2025-02はlongはほぼ横ばいだが、shortが `-111.2848` で損失を支配する。

## Failure Flags

2024-12:

| flag | trades | losing trades | adjusted pnl | loss pnl | exit regret |
|---|---:|---:|---:|---:|---:|
| losing_trade | 33 | 33 | -198.4176 | -198.4176 | 580.4134 |
| predicted_side_error | 30 | 24 | -164.2032 | -183.7572 | 340.5410 |
| direction_error | 29 | 23 | -164.1312 | -183.6852 | 330.0790 |
| profit_barrier_miss | 35 | 24 | -152.1212 | -184.2612 | 398.0490 |
| EV overestimated oracle | 33 | 24 | -156.1542 | -184.2612 | 348.4520 |

2025-02:

| flag | trades | losing trades | adjusted pnl | loss pnl | exit regret |
|---|---:|---:|---:|---:|---:|
| losing_trade | 34 | 34 | -263.8452 | -263.8452 | 839.1790 |
| direction_error | 32 | 19 | -197.0412 | -222.8532 | 478.3470 |
| predicted_side_error | 32 | 19 | -197.0412 | -222.8532 | 478.3470 |
| profit_barrier_miss | 40 | 21 | -194.7428 | -231.9288 | 779.6576 |
| no_edge_entry | 5 | 5 | -104.2896 | -104.2896 | 99.9024 |

## Buckets

### Direction

| month | direction | trades | adjusted pnl | win rate | direction error rate | exit regret |
|---|---|---:|---:|---:|---:|---:|
| 2024-12 | long | 27 | -70.6460 | 0.4074 | 0.4815 | 535.9688 |
| 2024-12 | short | 28 | -63.8846 | 0.3929 | 0.5714 | 456.6456 |
| 2025-02 | long | 42 | 1.1926 | 0.5714 | 0.3810 | 917.5918 |
| 2025-02 | short | 30 | -111.2848 | 0.4667 | 0.5333 | 675.0512 |

### Actual Profit Barrier

| month | barrier hit | trades | adjusted pnl | win rate | direction error rate |
|---|---:|---:|---:|---:|---:|
| 2024-12 | 0 | 35 | -152.1212 | 0.3143 | 0.8000 |
| 2024-12 | 1 | 20 | 17.5906 | 0.5500 | 0.0500 |
| 2025-02 | 0 | 40 | -194.7428 | 0.4750 | 0.6750 |
| 2025-02 | 1 | 32 | 84.6506 | 0.5938 | 0.1563 |

Barrier hitの実績が外れたentryが損失の中心。`require_profit_barrier=true` は予測値に対するfilterだが、今回の全tradeで `pred_taken_profit_barrier_hit=1` になっており、予測barrierはfilterとして機能していない。

### Actual Entry Rank

| month | actual rank bucket | trades | adjusted pnl | win rate |
|---|---|---:|---:|---:|
| 2024-12 | <=0.25 | 18 | -126.3344 | 0.1667 |
| 2024-12 | 0.75-1.0 | 17 | 20.6830 | 0.6471 |
| 2025-02 | <=0.25 | 21 | -166.9824 | 0.2381 |
| 2025-02 | 0.75-1.0 | 21 | 32.3124 | 0.8095 |

実績entry rankはかなり説明力がある。しかし予測entry rankでは、強く絞ると取引数が薄くなり、validation/testで安定候補にならなかった。

### Predicted Wait Regret

| month | pred wait bucket | trades | adjusted pnl | direction error rate |
|---|---|---:|---:|---:|
| 2024-12 | 4-10 | 19 | -116.4410 | 0.7368 |
| 2024-12 | 0-2 | 14 | -3.7474 | 0.3571 |
| 2025-02 | 4-10 | 33 | -93.2942 | 0.4242 |
| 2025-02 | 0-2 | 8 | 12.1490 | 0.6250 |

predicted wait regretは一部効いているが、単独では方向エラーを十分に消せない。

## Focused Sweep

分析から、予測rank/waitで絞る追加sweepを実施した。学習は増やしていない。

Validation focused sweep:

- sweeps:
  - `data/reports/backtests/20260627_212315_model_sweep_2024-07/`
  - `data/reports/backtests/20260627_212315_model_sweep_2024-09/`
  - `data/reports/backtests/20260627_212315_model_sweep_2024-11/`
  - `data/reports/backtests/20260627_212315_model_sweep_2025-01/`
- summary:
  - `data/reports/backtests/20260627_212411_model_sweep_summary_1/`

結果:

- `min_entry_rank=0.65` / `0.75` は取引数が薄くなりすぎた。
- 30 trades/foldで残った最良候補は `min_entry_rank=0.5`。

Candidate:

| policy | entry | side margin | risk | max wait regret | min entry rank | barrier | mean pnl | min pnl | min trades | max DD |
|---|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|
| timed_ev | 15 | 0 | 0 | inf | 0.5 | true | 47.1290 | 19.7484 | 44 | 80.2586 |

Fixed test:

| month | adjusted pnl | raw pnl | trades | win rate | profit factor | max DD |
|---|---:|---:|---:|---:|---:|---:|
| 2024-12 | -115.2758 | -85.4050 | 49 | 0.4286 | 0.3568 | 124.8292 |
| 2025-02 | -69.0714 | -34.6360 | 60 | 0.5000 | 0.6657 | 99.3680 |

`min_entry_rank=0.5` は損失を抑えたが、NoTradeには届かない。予測rank filterは有効な方向だが、単独では根本解決にならない。

## 判断

- 失敗は単純な「entryしすぎ」ではない。
- 実績barrier miss、方向ミス、exit regret、EV過大評価が同時に出ている。
- 実績entry rankは強い説明力を持つが、予測rankはまだ十分に信頼できない。
- `require_profit_barrier=true` は現状の予測では通りすぎており、filterとして弱い。
- 2025-02はshort側の局面判定が特に壊れている。

## 次の実験

1. barrier hit / entry rank / wait regret を別個のcalibration targetとして評価する。
2. predicted barrierを確率として扱えるよう、分類出力を0/1ではなくprobabilityで保存する。
3. side/regime別にEV shrinkageを行う。
4. exit timingをbest holding minutes回帰ではなく、hazard/fixed horizon/barrier timeで学習する。
5. trade failure analyzerを標準診断にし、今後の全候補に適用する。
