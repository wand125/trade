# Profit Barrier Prediction Calibration

日時: 2026-06-28 17:36 JST
更新日時: 2026-06-28 17:36 JST

## Summary

- Experiment ID: `profit_barrier_prediction_calibration`
- Status: implemented and diagnosed
- Main result: 全体平均ではprofit-barrier確率はやや過小評価だが、実際にgateで使う `0.4-0.6` bucketはtestで強く過大評価している。
- Report numbering note: this file is numbered from the internal `日時`, not filesystem mtime or `更新日時`.

## Implementation

`trade_data.modeling profit-barrier-report` を追加した。

この診断は prediction parquet を読み、long/short の `profit_barrier_hit` と `pred_*_profit_barrier_hit_prob_1` を縦持ちにして、以下を集計する。

- actual hit rate
- predicted probability mean / median
- calibration error
- overestimate / underestimate
- Brier score
- threshold hit rate and threshold accuracy
- month / side / session / volatility / trend / combined regime / bucket 別の壊れ方

## Smoke

Setup:

- predictions: `experiments/20260628_064332_policy_exit_event_prob_p1_l1p2/predictions_valid.parquet`
- predictions: `experiments/20260628_064332_policy_exit_event_prob_p1_l1p2/predictions_test.parquet`
- threshold: `0.4`
- min group rows: `500`

Artifact:

- `data/reports/modeling/20260628_083635_profit_barrier_valid_test_exit_event_prob/`

Overall:

| rows | actual hit rate | predicted mean | calibration error | Brier | predicted hit rate | threshold accuracy |
|---:|---:|---:|---:|---:|---:|---:|
| `288030` | `0.3661` | `0.3299` | `-0.0362` | `0.2278` | `0.1544` | `0.6087` |

Worst overestimate groups:

| group | rows | actual hit | predicted mean | overestimate | Brier |
|---|---:|---:|---:|---:|---:|
| `test|long` | `28763` | `0.2678` | `0.3314` | `0.0636` | `0.2088` |
| `valid|short` | `115252` | `0.2785` | `0.3289` | `0.0504` | `0.2007` |
| `test|ny_overlap` | `10080` | `0.2688` | `0.3127` | `0.0439` | `0.2025` |
| `test|range_normal_vol` | `4150` | `0.3031` | `0.3372` | `0.0341` | `0.2215` |

Bucket view:

| split | bucket | rows | actual hit | predicted mean | overestimate | threshold accuracy |
|---|---|---:|---:|---:|---:|---:|
| `test` | `0.00-0.20` | `3432` | `0.0233` | `0.1073` | `0.0840` | `0.9767` |
| `test` | `0.20-0.40` | `44550` | `0.3888` | `0.3220` | `0.0000` | `0.6112` |
| `test` | `0.40-0.60` | `9481` | `0.1807` | `0.4447` | `0.2640` | `0.1807` |
| `test` | `0.60-0.80` | `63` | `0.1905` | `0.6216` | `0.4311` | `0.1905` |
| `valid` | `0.40-0.60` | `34498` | `0.4865` | `0.4421` | `0.0000` | `0.4865` |
| `valid` | `0.60-0.80` | `419` | `0.2267` | `0.6231` | `0.3964` | `0.2267` |

## Interpretation

- 全体平均だけを見ると `predicted mean < actual hit rate` で、単純なglobal down-shiftは危険。
- しかし、policy gateで採用される `probability >= 0.4` のtest bucketは大きく過大評価している。
- 2024-12 holdoutで actual profit barrier miss rate が高かった理由は、threshold近辺のbucketがtestで壊れていることと整合する。
- これは「profit barrier確率を上げれば安全」というより、「probability bucketごとの校正と不確実性を見ないと危険」という結果。

## Decision

- `profit-barrier-report` を今後の標準診断に追加する。
- `profit_barrier_threshold=0.4` をhardに信じるのではなく、bucket別actual hit rateを候補選定時に見る。
- 現時点ではprobabilityのglobal補正やhard gate追加はしない。まずOOFでbucket崩れの再現性を見る。

## Next Actions

1. train/validation OOF predictionに `profit-barrier-report` を適用し、`0.4-0.6` bucketの崩れがholdout固有か確認する。
2. selected tradeだけでなく、entry候補全体のprofit-barrier probability calibrationを比較表に入れる。
3. 次のcandidate selectionでは、raw probability thresholdだけでなくbucket overestimateとsmoothed actual hit rateを併記する。
