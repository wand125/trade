# Available Context Drift

日時: 2026-06-29 11:17 JST
更新日時: 2026-06-29 11:17 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻である `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## 目的

`00133` では `only_candidate + direction + combined_regime` の共通flipを見た。ただし `delta_status=only_candidate` はbase/candidate比較後に分かる情報で、live predictionへそのまま特徴として入れるとリーク寄りになる。

今回は `delta_status` を落とし、予測時点で使える `direction + combined_regime` だけでも反転が残るか確認する。

## 実装

`model-trade-delta-preflight` に以下を追加した。

- `split_group_metrics_direction_combined_regime.csv`
- `group_drift_direction_combined_regime.csv`
- `split_stateful_group_metrics_direction_combined_regime.csv`
- `stateful_group_drift_direction_combined_regime.csv`

`model-trade-delta-drift-stability` に以下を追加した。

- `flip_stability_available_pnl.csv`
- `flip_stability_available_pnl_monthly_support.csv`
- `flip_stability_available_pnl_monthly_support_summary.csv`
- `flip_stability_available_stateful.csv`
- `flip_stability_available_stateful_monthly_support.csv`
- `flip_stability_available_stateful_monthly_support_summary.csv`

## 実行

guard top:

```bash
python3 -m trade_data.backtest model-trade-delta-preflight \
  --validation-deltas data/reports/backtests/20260629_014012_guard_fixed_parent_validation_base_delta,data/reports/backtests/20260629_014012_guard_fixed_parent_validation_highcost_delta \
  --holdout-deltas data/reports/backtests/20260629_014012_guard_fixed_parent_apply_base_delta,data/reports/backtests/20260629_014012_guard_fixed_parent_apply_highcost_delta \
  --label guard_fixed_available_context_preflight
```

stack0:

```bash
python3 -m trade_data.backtest model-trade-delta-preflight \
  --validation-deltas data/reports/backtests/20260628_234917_stateful_candidate_examples_validation \
  --holdout-deltas data/reports/backtests/20260628_234210_stateful_candidate_examples_smoke \
  --label stack0_available_context_preflight
```

drift stability:

```bash
python3 -m trade_data.backtest model-trade-delta-drift-stability \
  --preflight-runs data/reports/backtests/20260629_021649_guard_fixed_available_context_preflight,data/reports/backtests/20260629_021656_stack0_available_context_preflight \
  --label guard_stack0_available_context_drift_stability
```

## 結果

summary:

| metric | common flip groups | monthly support rows |
|---|---:|---:|
| status PnL | 3 | 49 |
| status stateful | 6 | 99 |
| available PnL | 1 | 41 |
| available stateful | 2 | 48 |

available PnL common flip:

| group | validation total | holdout total | holdout - validation |
|---|---:|---:|---:|
| short / down_normal_vol | `+97.2160` | `-212.6270` | `-309.8430` |

available stateful common flips:

| group | validation total | holdout total | holdout - validation |
|---|---:|---:|---:|
| long / down_low_vol | `+358.3530` | `-234.8292` | `-593.1822` |
| long / up_normal_vol | `+63.3320` | `-9.9444` | `-73.2764` |

主な月別support:

| comparison | split | group | months | rows | sum | min month | negative months | positive months |
|---|---|---|---:|---:|---:|---:|---:|---:|
| guard top | validation | short / down_normal_vol | 4 | 34 | `+88.1512` | `+0.7320` | 0 | 12 |
| guard top | holdout | short / down_normal_vol | 4 | 60 | `-202.5290` | `-42.7390` | 10 | 4 |
| stack0 | validation | short / down_normal_vol | 4 | 18 | `+9.0648` | `-23.0010` | 1 | 2 |
| stack0 | holdout | short / down_normal_vol | 2 | 30 | `-10.0980` | `-6.9480` | 2 | 0 |
| guard top | validation | long / down_low_vol | 4 | 14 | `+218.2502` | `-14.4392` | 2 | 12 |
| guard top | holdout | long / down_low_vol | 4 | 14 | `-181.8266` | `-67.6918` | 7 | 7 |
| stack0 | validation | long / down_low_vol | 4 | 7 | `+140.1028` | `-19.7396` | 2 | 5 |
| stack0 | holdout | long / down_low_vol | 2 | 4 | `-53.0026` | `-40.0522` | 3 | 1 |

## OOF context check

既存 `stateful_entry_value` OOF examplesで、同じavailable contextを `candidate-quality-report` で確認した。

```bash
python3 -m trade_data.meta_model candidate-quality-report \
  --examples data/reports/modeling/20260628_235629_stateful_entry_value_model/validation_oof_stateful_value_examples.csv \
  --output-dir data/reports/modeling \
  --label stateful_entry_context_report \
  --target-column target \
  --raw-prediction-column pred_taken_ev \
  --mean-prediction-column pred_candidate_quality_taken_adjusted_pnl \
  --lower-prediction-column pred_candidate_quality_taken_lower_adjusted_pnl \
  --downside-thresholds 0,-15 \
  --groupings 'candidate_side,combined_regime;delta_status,candidate_side,combined_regime;dataset_month,candidate_side,combined_regime;candidate_side,session_regime;delta_status,candidate_side,session_regime' \
  --bucket-group-columns candidate_side,combined_regime \
  --min-group-support 1 \
  --summary-rows 20
```

OOF validation上の同context:

| group | support | target mean | target <= 0 | target q10 | mean prediction | lower prediction |
|---|---:|---:|---:|---:|---:|---:|
| short / down_normal_vol | 15 | `+4.7383` | `0.4000` | `-6.7176` | `+3.1007` | `-3.1517` |
| long / down_low_vol | 66 | `+2.1228` | `0.3485` | `-11.8098` | `+2.4227` | `-4.0287` |
| long / up_normal_vol | 2 | `+8.3915` | `0.0000` | `+7.1663` | `+3.5835` | `-2.2478` |

## 判断

`direction + combined_regime` だけでも反転は一部残る。特に `short/down_normal_vol` は通常PnLで、`long/down_low_vol` はstateful opportunity-costで強い反転を持つ。

ただし、既存validation OOFではこれらのavailable contextは悪いgroupとして見えていない。`short/down_normal_vol` も `long/down_low_vol` もtarget meanはプラスで、downside率も全体から大きく悪化していない。したがって、単純にこのcontextを特徴列へ足すだけでは、holdout崩れを先に学べる可能性は低い。

扱い:

- `delta_status` はlive特徴に使わない。
- `direction + combined_regime` はhard blockにしない。
- available-context driftは、追加walk-forward、stress-aware target、regime drift診断の監査軸として使う。
- 次はexamplesを増やして、validation内だけで悪いgroupを後付け選別するのではなく、月・regimeの変化に壊れにくいtarget設計へ戻す。

## Artifacts

- OOF context report: `data/reports/modeling/20260629_021331_stateful_entry_context_report/`
- guard available preflight: `data/reports/backtests/20260629_021649_guard_fixed_available_context_preflight/`
- stack0 available preflight: `data/reports/backtests/20260629_021656_stack0_available_context_preflight/`
- drift stability: `data/reports/backtests/20260629_021703_guard_stack0_available_context_drift_stability/`

## Verification

- targeted model trade delta tests: OK
- `python3 -m unittest tests.test_backtest tests.test_docs_reports`: OK, 77 tests
