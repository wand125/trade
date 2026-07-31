# Exit Event Timing Targets

日時: 2026-06-28 15:21 JST
更新日時: 2026-06-28 15:21 JST

## Summary

- Experiment ID: `exit_event_timing_targets`
- Status: implemented with smoke validation
- Main result: side別に「利確が先」「損切りが先」「時間切れ」のexit event targetと、そのevent到達までの分数targetをdataset/modelingへ追加した。軽量smokeではHGBが `pred_long_exit_event_minutes` / `pred_short_exit_event_minutes` を出力し、既存 `timed_ev` policyのholding columnとしてbacktestに接続できることを確認した。
- Report numbering note: this file is numbered by the internal `日時`, not by file update time or `更新日時`.

## Motivation

selected-trade quality gateは、group補正でも小型HGBでもvalidation topを改善しなかった。問題はentry後の品質を後段gateで落とすより、exit timingを直接学習して、利確/損切り/時間切れの構造をpolicyへ渡すことにある。

今回の目的は、性能改善の結論ではなく、次の本番validationに使える教師targetを追加すること。

## Target Definition

side別に以下を追加した。

| target | type | meaning |
|---|---|---|
| `long_exit_event` | classification | long entry後、`0=time_exit`, `1=profit_first`, `2=loss_first` |
| `short_exit_event` | classification | short entry後、`0=time_exit`, `1=profit_first`, `2=loss_first` |
| `long_exit_event_minutes` | regression | long sideの最初のexit eventまでのwall-clock minutes |
| `short_exit_event_minutes` | regression | short sideの最初のexit eventまでのwall-clock minutes |
| `long_exit_event_time_bin` | classification | `long_exit_event_minutes` の時間bucket |
| `short_exit_event_time_bin` | classification | `short_exit_event_minutes` の時間bucket |

profit/loss barrierは既存の `min_adjusted_edge` と profit/loss multiplierから作る。

```text
profit_barrier_raw = min_adjusted_edge / profit_multiplier
loss_barrier_raw = min_adjusted_edge / loss_multiplier
```

profit hitとloss hitが同じbarの場合はprofit優先にした。これは既存 `profit_barrier_hit_before_loss` の挙動と揃えるため。

市場休止やgapをまたぐ場合、event minutesは1440分を超えることがある。既存backtestも24h超過後の次barで強制決済するため、このtargetもwall-clock minutesとして扱う。

## Implementation

追加:

- `EXIT_EVENT_TIME = 0`
- `EXIT_EVENT_PROFIT = 1`
- `EXIT_EVENT_LOSS = 2`
- `barrier_exit_event(...)`
- dataset columns:
  - `long_exit_event`
  - `short_exit_event`
  - `long_exit_event_minutes`
  - `short_exit_event_minutes`
  - `long_exit_event_time_bin`
  - `short_exit_event_time_bin`
- modeling target set:
  - `policy` / `full` regression targetsへ `*_exit_event_minutes`
  - `policy` / `full` classification targetsへ `*_exit_event`, `*_exit_event_time_bin`

既存の `model-policy --long-holding-column` / `--short-holding-column` により、`timed_ev` policyでは以下のように差し替え可能。

```text
--long-holding-column pred_long_exit_event_minutes
--short-holding-column pred_short_exit_event_minutes
```

## Smoke Data

Smoke dataset directory:

- `data/processed/datasets/xauusd_m1_exit_event_smoke/`

Generated months:

- `2024-07`
- `2024-09`
- `2025-01`

2025-01 event class distribution:

| side | time_exit | profit_first | loss_first |
|---|---:|---:|---:|
| long | 5,301 | 16,820 | 8,076 |
| short | 5,283 | 6,241 | 18,673 |

2025-01 event minutes:

| side | mean | median | p90 |
|---|---:|---:|---:|
| long | `980.1190` | `715.0000` | `2979.4000` |
| short | `972.8273` | `684.0000` | `3024.0000` |

## Smoke Model

Lightweight smoke model:

- train: `2024-07`
- valid: `2024-09`
- test: `2025-01`
- target set: `policy`
- max iter: `5`
- sample frac: `0.2`

Artifact:

- `experiments/20260628_062101_exit_event_target_smoke/`

Exit timing metrics:

| split | target | MAE | RMSE | R2 |
|---|---|---:|---:|---:|
| valid | `long_exit_event_minutes` | `537.5728` | `676.4928` | `0.1628` |
| valid | `short_exit_event_minutes` | `524.9559` | `656.6593` | `0.1565` |
| test | `long_exit_event_minutes` | `600.3732` | `854.8331` | `0.1306` |
| test | `short_exit_event_minutes` | `611.3872` | `876.4042` | `0.1450` |

Exit event classification smoke:

| split | target | accuracy | balanced accuracy | macro F1 |
|---|---|---:|---:|---:|
| valid | `long_exit_event` | `0.4529` | `0.4152` | `0.4317` |
| valid | `short_exit_event` | `0.5695` | `0.4079` | `0.3628` |
| test | `long_exit_event` | `0.5171` | `0.4870` | `0.5016` |
| test | `short_exit_event` | `0.6795` | `0.4657` | `0.4686` |

## Smoke Backtest

Connection smoke:

- predictions: `experiments/20260628_062101_exit_event_target_smoke/predictions_valid.parquet`
- month: `2024-09`
- policy: `timed_ev`
- holding columns:
  - `pred_long_exit_event_minutes`
  - `pred_short_exit_event_minutes`
- cost: spread `0.1`, slippage `0.05`, delay `0`

Result:

| metric | value |
|---|---:|
| adjusted pnl | `-118.8852` |
| raw pnl | `-73.3650` |
| trades | `47` |
| win rate | `0.4043` |
| profit factor | `0.5647` |
| max drawdown | `170.1374` |
| forced exits | `3` |

このbacktestは軽量1ヶ月trainの接続確認であり、採用判断には使わない。性能評価は、既存の4fold validationとcost-aware candidate selectionで実施する必要がある。

## Interpretation

- exit event minutesは、軽量smokeでもR2が正になったため、既存のbest holding minutesより学習しやすい可能性がある。
- event classificationはclass imbalanceの影響が強く、balanced accuracyはまだ弱い。
- `timed_ev` policyへは追加実装なしで接続できる。
- ただし、holding timeだけを差し替えてもentry/side選択が壊れていれば損失は出る。次はfixed horizon EV候補と組み合わせたvalidation gridで、holding column差し替えだけの効果を比較する。

## Decision

- exit event timing targetsを本流の次実験軸へ昇格する。
- 今回のsmoke backtest結果は採用/不採用判断に使わない。
- 次は新target入りdatasetをvalidation 4fold対象月へ再生成し、`pred_*_exit_event_minutes` をholding columnにした `timed_ev` と、従来 `pred_*_best_holding_minutes` を比較する。
- さらに、`long_exit_event` / `short_exit_event` のprofit/loss/time確率をgateやpenaltyとして使うには、多クラスprobability出力が必要。これは次の実装候補。

## Artifacts

- smoke datasets:
  - `data/processed/datasets/xauusd_m1_exit_event_smoke/xauusd_m1_2024-07_h24_edge15.parquet`
  - `data/processed/datasets/xauusd_m1_exit_event_smoke/xauusd_m1_2024-09_h24_edge15.parquet`
  - `data/processed/datasets/xauusd_m1_exit_event_smoke/xauusd_m1_2025-01_h24_edge15.parquet`
- smoke model: `experiments/20260628_062101_exit_event_target_smoke/`
- smoke backtest: `data/reports/backtests/20260628_062138_model_timed_ev_2024-09/`

## Verification

- `python3 -m unittest tests.test_dataset tests.test_modeling`: OK
- `python3 -m trade_data.dataset build ... --month 2025-01 ...`: OK
- `python3 -m trade_data.modeling train ... --target-set policy ...`: OK
- `python3 -m trade_data.backtest model-policy ... --long-holding-column pred_long_exit_event_minutes ...`: OK
