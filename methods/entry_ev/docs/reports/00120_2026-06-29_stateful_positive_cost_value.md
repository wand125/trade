# Stateful Positive Cost Value

日時: 2026-06-29 09:10 JST
更新日時: 2026-06-29 09:10 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻である `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## 目的

`00119` の次手として、`stateful_entry_value` よりも勝ち機会の取り逃しを強く罰する `stateful_positive_cost_value` を学習する。

狙い:

- 一玉制約で後続の良い取引をブロックするentryを下げる。
- raw EVの平均過大評価を抑える。
- ただし、単純なhard gate / scalar penaltyで良い取引まで削らないか確認する。

## 実行

```bash
PYTHONPATH=src python3 -m trade_data.meta_model oof-stateful-value-model \
  --examples data/reports/backtests/20260628_234917_stateful_candidate_examples_validation/stateful_candidate_examples.csv \
  --validation-predictions data/reports/modeling/20260628_230654_20260629_side_outcome_stack_fixed_component/predictions_validation_oof_candidate_quality_model.parquet \
  --apply-predictions data/reports/modeling/20260628_230654_20260629_side_outcome_stack_fixed_component/predictions_apply_candidate_quality_model.parquet \
  --validation-months 2024-07,2024-09,2024-11,2025-01 \
  --apply-months 2024-12,2025-02,2025-03 \
  --output-dir data/reports/modeling \
  --label stateful_positive_cost_value_model \
  --target-column stateful_positive_cost_value \
  --prediction-prefix stateful_positive_cost \
  --source-mode columns \
  --long-column pred_long_best_adjusted_pnl \
  --short-column pred_short_best_adjusted_pnl
```

artifacts:

- model: `data/reports/modeling/20260629_000824_stateful_positive_cost_value_model/`
- direct validation: `data/reports/backtests/stateful_positive_cost_direct_validation/`
- risk validation: `data/reports/backtests/stateful_positive_cost_risk_validation/`
- risk apply: `data/reports/backtests/stateful_positive_cost_risk_apply/`

## OOF Metrics

| metric | raw EV | positive-cost mean | positive-cost lower |
|---|---:|---:|---:|
| target mean | `1.6588` | - | - |
| predicted mean | `16.4274` | `1.7441` | `-4.5184` |
| bias | `14.7685` | `0.0853` | `-6.1773` |
| overestimate mean | `15.6463` | `4.2896` | `1.9390` |
| MAE | - | `8.4938` | - |
| R2 | - | `-0.0085` | - |
| lower coverage | - | - | `0.7441` |

`stateful_entry_value` と同じく、平均biasは大きく改善する。一方でR2は負で、候補の順位付け能力はまだ弱い。

## Direct Replacement Validation

`pred_candidate_quality_stateful_positive_cost_<side>_adjusted_pnl` をentry EVへ直接使い、threshold `1.5/2.0/2.5/3.0` とside margin `0/0.5/1.0` を確認した。

上位集計:

| threshold | side margin | sum pnl | min month pnl | trades | max DD | forced max |
|---:|---:|---:|---:|---:|---:|---:|
| `2.0` | `0.0` | `270.3750` | `-64.5430` | `1349` | `152.8240` | `0.0283` |
| `2.5` | `0.0` | `193.7668` | `0.0000` | `480` | `104.4782` | `0.0426` |
| `2.0` | `0.5` | `193.4386` | `0.0000` | `293` | `94.4470` | `0.0533` |
| `3.0` | `0.0` | `158.5170` | `0.0000` | `197` | `75.1426` | `0.0342` |

direct replacementは標準baseline `sum=622.6486`, `min=138.0338`, `trades=275` を超えない。`2.0/0.0` は取引過多で2024-07が `-64.5430`。`2.5` 以上は一部月が0 tradeになり、NoTrade寄りになる。

apply側のpositive-cost meanは最大でも `1.7923` 付近で、validation direct thresholdをそのまま外挿すると取引が消えやすい。

## Overestimate Risk Validation

raw EVは維持し、positive-cost meanとの過大評価分だけ `risk_penalty` で削った。

| risk penalty | sum pnl | min month pnl | trades | max DD | forced max |
|---:|---:|---:|---:|---:|---:|
| `0.00` | `622.6486` | `138.0338` | `275` | `85.0166` | `0.0000` |
| `0.10` | `606.7320` | `73.5066` | `241` | `75.6610` | `0.0000` |
| `0.25` | `353.0882` | `65.9728` | `133` | `86.3254` | `0.0000` |
| `0.50` | `6.4750` | `-14.5080` | `5` | `42.1320` | `0.0000` |

`0.10` は2024-07を `198.1782 -> 217.2678`、2024-11を `142.8264 -> 175.8326` に改善するが、2024-09を `138.0338 -> 73.5066` に壊す。validation全体ではbaseline未満。

## Apply Holdout

| risk penalty | sum pnl | min month pnl | trades | max DD | forced max |
|---:|---:|---:|---:|---:|---:|
| `0.00` | `242.5008` | `-20.8252` | `426` | `122.9852` | `0.0326` |
| `0.10` | `14.1920` | `-38.4826` | `365` | `105.7046` | `0.0241` |
| `0.25` | `-43.2934` | `-61.5238` | `215` | `93.1080` | `0.0000` |

`0.25` は2024-12を `-20.8252 -> 2.3752` へ改善するが、2025-02/2025-03を大きく削る。`0.10` も2025-02を `179.2484 -> 74.9774`、2025-03を `84.0776 -> -38.4826` に悪化させる。

## 判断

`stateful_positive_cost_value` modelは校正信号として残すが、direct replacementやscalar overestimate penaltyとして標準policyには採用しない。

理由:

- 平均biasは改善するが、R2が負で順位付けには弱い。
- direct replacementは閾値が月に強く依存し、取引過多または0 trade化する。
- risk penaltyはvalidation/applyともbaselineを超えず、良い月の利益を大きく削る。
- 現行backtestでは補正後EVでside選択、entry threshold、side marginを全て判定するため、penaltyを入れるとtie-breakだけでなくentry集合そのものが変わりすぎる。

次に実装すべきこと:

1. `timed_ev` にnear-tie専用のsecondary scoreを追加する。
2. primary raw EVでentry可否を決め、`abs(long_raw_ev - short_raw_ev) <= tie_break_margin` のときだけstateful scoreでsideまたは同時刻候補順位を調整する。
3. `stateful_positive_cost_value` はhard gateではなく、同時刻・近接EV候補の優先順位にだけ使う。
4. examplesを追加月へ増やす。現状254例では、深いモデルや強いpenaltyを信頼するには不足している。
