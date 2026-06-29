# Dense Holding Shortening Targets

日時: 2026-06-29 18:45 JST
更新日時: 2026-06-29 19:12 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

`00159` の直接cap診断は有効だったが、common tradeに限定された疎なpost-hoc targetだった。そこで、全decision rowから学べる dense な holding短縮targetをdataset schemaへ追加した。

追加した中心targetは、barrier/time exit時点の実現PnLと、固定horizon決済がそのexit-event決済より良いかを表すdelta / beat label。これにより、モデルは「入る方向」だけでなく「標準exitを待つより60/240/720分で手放すべきか」を連続値と分類の両方で学習できる。

これは実装とdataset smokeの完了であり、policy成績の改善確認ではない。次は主dataset再生成、chronological OOF、holding policyへの接続で検証する。

## Implementation

変更:

- `src/trade_data/dataset.py`
  - `long_exit_event_raw_pnl`, `short_exit_event_raw_pnl`
  - `long_exit_event_adjusted_pnl`, `short_exit_event_adjusted_pnl`
  - `long/short_fixed_60m/240m/720m_minus_exit_event_adjusted_pnl`
  - `long/short_fixed_60m/240m/720m_beats_exit_event`
- `src/trade_data/modeling.py`
  - `policy` / `full` target-setに exit-event adjusted PnL と fixed-vs-event deltaを回帰targetとして追加。
  - fixed-vs-event beat labelを分類targetとして追加。
  - `prediction_frame` に新しい実測target列を残す。
  - 新targetだけを軽く診断する `target-set holding_shortening` を追加。

`fixed_{minutes}m_minus_exit_event_adjusted_pnl` は、値が正なら固定horizon決済のほうがbarrier/time exitより良い。`*_beats_exit_event` はその二値化。

## Smoke Dataset

2025-08をsmoke用ignored directoryへ再生成した。

Command:

```bash
python3 -m trade_data.dataset build \
  --month 2025-08 \
  --data data/processed/histdata/xauusd/xauusd_m1.parquet \
  --output-dir data/processed/datasets/xauusd_m1_dense_holding_target_smoke \
  --horizon-hours 24 \
  --warmup-days 14 \
  --post-days 4 \
  --min-adjusted-edge 15 \
  --profit-multiplier 1.0 \
  --loss-multiplier 1.2 \
  --include-fft
```

Result:

- rows: `28,971`
- output: `data/processed/datasets/xauusd_m1_dense_holding_target_smoke/xauusd_m1_2025-08_h24_edge15.parquet`
- label counts: short `9,434`, flat `5,036`, long `14,501`

New target distribution:

| target | notna | mean | p10 | p50 | p90 |
|---|---:|---:|---:|---:|---:|
| `long_exit_event_adjusted_pnl` | `28,971` | `0.1199` | `-16.0080` | `-0.1920` | `16.0000` |
| `short_exit_event_adjusted_pnl` | `28,971` | `-2.7898` | `-16.1760` | `-15.0240` | `15.8100` |
| `long_fixed_60m_minus_exit_event_adjusted_pnl` | `28,971` | `-0.0980` | `-18.0934` | `0.2510` | `17.4060` |
| `short_fixed_60m_minus_exit_event_adjusted_pnl` | `28,971` | `2.0451` | `-16.5380` | `4.1316` | `18.3400` |
| `long_fixed_240m_minus_exit_event_adjusted_pnl` | `28,971` | `0.9032` | `-16.9280` | `0.0000` | `17.9366` |
| `short_fixed_240m_minus_exit_event_adjusted_pnl` | `28,971` | `0.4160` | `-16.7110` | `0.0000` | `17.8160` |
| `long_fixed_720m_minus_exit_event_adjusted_pnl` | `28,971` | `3.6415` | `-13.0000` | `1.6596` | `21.2772` |
| `short_fixed_720m_minus_exit_event_adjusted_pnl` | `28,971` | `-3.4461` | `-20.9780` | `-0.7644` | `14.1720` |

Beat rates:

| target | rate |
|---|---:|
| `long_fixed_60m_beats_exit_event` | `0.5032` |
| `short_fixed_60m_beats_exit_event` | `0.5530` |
| `long_fixed_240m_beats_exit_event` | `0.4983` |
| `short_fixed_240m_beats_exit_event` | `0.4988` |
| `long_fixed_720m_beats_exit_event` | `0.5391` |
| `short_fixed_720m_beats_exit_event` | `0.4114` |

## Interpretation

60分beat labelは極端に片寄っておらず、分類targetとして使える密度がある。delta targetも全行で非欠損になり、exit timing / EV calibrationの補助回帰targetとして使える。

注意点:

- 旧datasetには新列がないため、新targetを学習する実験では主datasetを再生成する。
- `filter_available_target_names` により旧datasetを読む過去実験は新targetを自動で落とせるが、新targetの効果検証には再生成が必須。
- このtargetは「常に60分で切る」ruleではなく、side/regime/contextを見て短縮が有利な度合いを学習するための情報にする。

## Verification

- `python3 -m unittest tests.test_dataset tests.test_modeling`: OK, 52 tests
- `python3 -m py_compile src/trade_data/dataset.py src/trade_data/modeling.py`: OK
- smoke dataset build: OK
- smoke summary target_columns: new columns present

## Full Dataset Refresh

既存artifactを壊さないため、主系列とは別のignored directoryへ 2023-01..2025-08 の32ヶ月を新schemaで再生成した。

Output:

- `data/processed/datasets/xauusd_m1_p1_l1p2_policy_combined_dense_holding/`
- range summary: `build_range_2023-01_2025-08_edge15.summary.json`

Validation:

- months: `32`
- rows: `899,408`
- missing new target columns: `0`
- all checked new targets notna rows: `899,408`

Aggregate target means:

| target | mean |
|---|---:|
| `long_exit_event_adjusted_pnl` | `0.1245` |
| `short_exit_event_adjusted_pnl` | `-2.3110` |
| `long_fixed_60m_minus_exit_event_adjusted_pnl` | `-0.3514` |
| `short_fixed_60m_minus_exit_event_adjusted_pnl` | `1.9199` |
| `long_fixed_60m_beats_exit_event` | `0.4786` |
| `short_fixed_60m_beats_exit_event` | `0.5536` |
| `long_fixed_240m_beats_exit_event` | `0.4661` |
| `short_fixed_240m_beats_exit_event` | `0.5226` |
| `long_fixed_720m_beats_exit_event` | `0.4647` |
| `short_fixed_720m_beats_exit_event` | `0.4726` |

## OOF Smoke

全 `policy` target-setで2024-11..2025-04のHGB OOFを回したところ、fold 0だけでも多数targetをfitして7分超になったため中断した。新target診断には重すぎるため、`target-set holding_shortening` を追加した。

軽量smoke:

```bash
python3 -m trade_data.modeling oof \
  --dataset-dir data/processed/datasets/xauusd_m1_p1_l1p2_policy_combined_dense_holding \
  --output-dir data/reports/modeling \
  --label 20260629_dense_holding_shortening_oof_smoke_2025_02_04 \
  --start-month 2025-02 \
  --end-month 2025-04 \
  --target-set holding_shortening \
  --max-iter 40 \
  --sample-frac 0.2 \
  --purge-label-overlap true \
  --embargo-hours 24
```

Artifacts:

- `data/reports/modeling/20260629_100956_20260629_dense_holding_shortening_oof_smoke_2025_02_04/`

Rows:

- input / OOF predictions: `85,361`
- regression targets: `8`
- classification targets: `6`

OOF regression:

| target | R2 | MAE |
|---|---:|---:|
| `long_exit_event_adjusted_pnl` | `-0.0259` | `15.1470` |
| `short_exit_event_adjusted_pnl` | `-0.0118` | `14.6709` |
| `long_fixed_60m_minus_exit_event_adjusted_pnl` | `-0.0218` | `12.6631` |
| `short_fixed_60m_minus_exit_event_adjusted_pnl` | `0.0015` | `12.1913` |
| `long_fixed_240m_minus_exit_event_adjusted_pnl` | `-0.0137` | `11.9772` |
| `short_fixed_240m_minus_exit_event_adjusted_pnl` | `0.0110` | `11.4578` |
| `long_fixed_720m_minus_exit_event_adjusted_pnl` | `0.0149` | `16.6647` |
| `short_fixed_720m_minus_exit_event_adjusted_pnl` | `0.0125` | `17.0218` |

OOF classification:

| target | balanced accuracy | macro F1 |
|---|---:|---:|
| `long_fixed_60m_beats_exit_event` | `0.5290` | `0.5206` |
| `short_fixed_60m_beats_exit_event` | `0.5372` | `0.5231` |
| `long_fixed_240m_beats_exit_event` | `0.5240` | `0.5228` |
| `short_fixed_240m_beats_exit_event` | `0.5430` | `0.5430` |
| `long_fixed_720m_beats_exit_event` | `0.5331` | `0.5259` |
| `short_fixed_720m_beats_exit_event` | `0.5214` | `0.4954` |

Interpretation:

- 回帰R2はほぼ0で、連続deltaをHGBで直接高精度に読むのは難しい。
- beat分類はbalanced accuracy `0.52..0.54` 台で、弱いrank signalはある。
- 次は連続deltaを直接policyへ使うより、beat probability、bucket化、regime別calibration、またはcandidate/ranking特徴として使うほうが筋がよい。

## Next Actions

1. `dense_holding` datasetを使い、全32ヶ月またはchronological expandingで `holding_shortening` target-setを本設定に近い学習量で再評価する。
2. 本格実験で採用する場合は、既存主dataset directoryを新schemaへ更新するか、artifact名に `dense_holding` を残して混同を防ぐ。
3. `pred_fixed_60m_beats_exit_event_prob_1` をholding短縮・exit選択の補助scoreへ接続する。連続deltaは直接使うよりcalibration/bucket化を先に試す。
4. 既存のpost-hoc `range_low_vol:london/rollover` 除外と比較し、固定ruleではなく予測targetで同等以上のcontext-aware判断ができるかを見る。
