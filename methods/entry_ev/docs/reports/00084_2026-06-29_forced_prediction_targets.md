# Forced Prediction Targets

日時: 2026-06-29 02:11 JST
更新日時: 2026-06-29 02:11 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

前回の `barrier_event_adjusted_pnl` targetでは、hybrid prediction parquetに `*_forced_adjusted_pnl` が無く、time exit targetが `*_fixed_720m_adjusted_pnl` にfallbackしていた。今回はこのartifact gapを修正し、prediction parquetへforced exit target列を残せるようにした。

結論:

- `prediction_frame` が `long_forced_raw_pnl`, `short_forced_raw_pnl`, `long_forced_adjusted_pnl`, `short_forced_adjusted_pnl`, `forced_side_score` を保存するようにした。
- 既存predictionを壊さず補完するため、`trade_data.modeling enrich-predictions` を追加した。
- 既存hybrid OOF / 2024-12 / 2025-02 artifactへforced列をjoinし、全行で欠損なしを確認した。
- forced列を使ったbarrier targetでは、time exit sourceが `long_forced_adjusted_pnl` / `short_forced_adjusted_pnl` だけになり、720m fallbackは解消した。
- OOF biasは少し改善したが、実行policyのvalidation topはrisk `0` のまま。forced target化だけでは成績改善にならない。

## Implementation

追加した保存対象:

```text
long_forced_raw_pnl
short_forced_raw_pnl
long_forced_adjusted_pnl
short_forced_adjusted_pnl
forced_side_score
```

既存artifact補完用CLI:

```bash
python -m trade_data.modeling enrich-predictions \
  --predictions data/reports/modeling/<run>/predictions_oof.parquet \
  --output-path data/reports/modeling/<run>/predictions_oof_forced.parquet \
  --dataset-dir data/processed/datasets/xauusd_m1_p1_l1p2_policy_combined \
  --months 2024-07,2024-09,2024-11,2025-01 \
  --horizon-hours 24 \
  --min-adjusted-edge 15
```

join keyは `dataset_month` + `decision_timestamp`。行がdataset contextに無い場合は失敗させる。target値がNaNでも結合行が存在すれば成功するよう、target値そのものではなく明示markerで一致判定する。

## Enriched Artifacts

| artifact | rows | added columns | missing matches |
|---|---:|---:|---:|
| OOF forced predictions | `115252` | `5` | `0` |
| 2024-12 forced predictions | `28763` | `5` | `0` |
| 2025-02 forced predictions | `27441` | `5` | `0` |

OOF forced columnsの欠損:

| column | nulls |
|---|---:|
| `long_forced_adjusted_pnl` | `0` |
| `short_forced_adjusted_pnl` | `0` |
| `forced_side_score` | `0` |
| `long_fixed_720m_adjusted_pnl` | `0` |
| `short_fixed_720m_adjusted_pnl` | `0` |

## Barrier Target Check

`oof-candidate-quality-model --target-mode barrier_event_adjusted_pnl` をenriched predictionで再実行した。

time exit source:

| source | count |
|---|---:|
| `short_forced_adjusted_pnl` | `6561` |
| `long_forced_adjusted_pnl` | `2530` |

これで前回の `fixed_720m_adjusted_pnl` fallbackは解消した。

OOF指標:

| item | fallback target | forced target |
|---|---:|---:|
| candidate count | `9091` | `9091` |
| target mean | `1.5739` | `1.6521` |
| raw bias | `20.4316` | `20.3534` |
| mean bias | `0.9855` | `0.8738` |
| lower bias | `-16.4275` | `-16.5050` |
| mean overestimate mean | `7.7639` | `7.7839` |
| mean MAE | `14.5424` | `14.6941` |
| mean R2 | `-0.1730` | `-0.1692` |
| lower coverage | `0.9925` | `0.9925` |

target semanticsは正しくなり、biasとR2はわずかに改善した。ただしMAEは少し悪化しており、順位付け性能が改善したとは言えない。

## Validation Policy

共通条件:

- Validation months: `2024-07`, `2024-09`, `2024-11`, `2025-01`
- Evaluation multiplier: profit `1.0`, loss `1.20`
- Base policy: `timed_ev`
- Base EV: `pred_long_best_adjusted_pnl`, `pred_short_best_adjusted_pnl`
- Risk: `pred_candidate_quality_*_overestimate_risk`
- Holding: `pred_mlp_*_exit_event_minutes`, max hold `480`
- Candidate spine: entry `12`, short offset `6`, side margin `5`, min rank `0.5`

forced barrier overestimate risk:

| risk | min pnl | sum pnl | min trades | mean trades | max DD |
|---:|---:|---:|---:|---:|---:|
| `0.00` | `82.7176` | `406.6546` | `24` | `27.75` | `60.9864` |
| `0.05` | `62.5366` | `359.6626` | `22` | `25.25` | `59.9214` |
| `0.10` | `27.0340` | `275.1414` | `19` | `21.75` | `63.1788` |
| `0.25` | `-19.1186` | `92.7284` | `7` | `13.00` | `59.7396` |
| `0.50` | `-10.6122` | `6.3178` | `0` | `3.50` | `72.4272` |

topは前回同様risk `0`。forced target化後も、overestimate riskを入れるほどfold最低PnLは下がる。

## Fixed Smoke

forced barrier overestimate risk, min rank `0.5`:

| month | risk | adjusted pnl | raw pnl | trades | max DD | direction error | EV over mean |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2024-12 | `0.00` | `-31.7576` | `4.998` | `52` | `99.1124` | `0.5962` | `22.1346` |
| 2024-12 | `0.05` | `-59.7292` | `-23.389` | `47` | `85.6152` | `0.6596` | `23.3581` |
| 2024-12 | `0.10` | `0.1206` | `23.567` | `43` | `53.7926` | `0.6512` | `22.1083` |
| 2024-12 | `0.25` | `-31.0590` | `-17.921` | `24` | `31.0590` | `0.5833` | `25.1832` |
| 2024-12 | `0.50` | `0.0000` | `0.000` | `0` | `0.0000` | `0.0000` | `0.0000` |
| 2025-02 | `0.00` | `47.1824` | `94.519` | `126` | `118.9336` | `0.4127` | `23.2076` |
| 2025-02 | `0.05` | `13.0490` | `54.310` | `110` | `107.5074` | `0.4636` | `23.9046` |
| 2025-02 | `0.10` | `-17.3004` | `25.100` | `111` | `106.4004` | `0.4775` | `24.7256` |
| 2025-02 | `0.25` | `-48.6162` | `-12.805` | `80` | `101.4436` | `0.4375` | `26.2692` |
| 2025-02 | `0.50` | `21.8284` | `23.787` | `6` | `11.7516` | `0.6667` | `21.2023` |

2024-12のrisk `0.10` はNoTrade近辺まで改善したが、validationで選べる台地ではない。2025-02ではrisk `0.10` がマイナスへ崩れる。risk `0.50` は片月の取引数が0または6で、月10trades条件に合わない。

## Decision

forced PnL列のartifact gapは修正済み。今後のprediction artifactはtime exit targetを固定720m fallbackに頼らず作れる。

ただし、forced barrier risk policyは標準採用しない。理由:

- validation topがrisk `0` のままで、risk列の追加は実行成績を改善していない。
- fixed smokeの改善は片月・少数trade依存で、robustな選択基準になっていない。
- forced target化はtarget semanticsの修正であり、モデルの汎化性能そのものを十分には上げていない。

次はforced target単独のriskではなく、exit event class、time-to-event、fixed horizon PnL、EV calibration errorをjointに扱うtargetへ進む。

## Artifacts

- enriched hybrid predictions: `data/reports/modeling/20260629_hgb_mlp_exit_hybrid_forced_targets/`
- forced barrier quality 2024-12 apply: `data/reports/modeling/20260628_170650_candidate_quality_barrier_forced_q25_2024_12/`
- forced barrier quality 2025-02 apply: `data/reports/modeling/20260628_170650_candidate_quality_barrier_forced_q25_2025_02/`
- forced barrier risk validation sweeps: `data/reports/backtests/candidate_quality_barrier_forced_overestimate_risk_validation/`
- forced barrier risk validation summary: `data/reports/backtests/candidate_quality_barrier_forced_overestimate_risk_summary/20260628_170819_model_sweep_summary/`
- forced fixed smoke: `data/reports/backtests/candidate_quality_barrier_forced_overestimate_risk_fixed/`
