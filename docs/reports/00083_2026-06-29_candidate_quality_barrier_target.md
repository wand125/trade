# Candidate Quality Barrier Target

日時: 2026-06-29 01:56 JST
更新日時: 2026-06-29 01:56 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

candidate-entry quality modelに `--target-mode barrier_event_adjusted_pnl` を追加し、単純なhindsight best PnLではなく、profit/loss barrier到達順とtime exit PnLを反映するtargetを試した。

結論:

- barrier targetはraw EVの過大評価をかなり露出する。raw predicted mean `22.0055` に対しtarget meanは `1.5739`。
- 平均モデルはbiasを `20.4316` から `0.9855` まで縮めたが、`R2=-0.1730` で候補順位として弱い。
- 下方分位はcoverage `0.9925` で保守的すぎ、entry scoreとしてはほぼNoTrade寄りになる。
- overestimate riskをsoft penalty化してもvalidation最良はrisk `0` のまま。riskを足すほどfold最低PnLが下がる。
- fixed 2024-12ではriskが一部損失を縮めるが、2025-02の利益を大きく削る。標準採用しない。

## Implementation

追加したtarget mode:

```bash
python -m trade_data.meta_model oof-candidate-quality-model \
  --target-mode barrier_event_adjusted_pnl \
  --min-adjusted-edge 15 \
  --time-exit-target-minutes 720
```

target mapping:

| actual exit event | target |
|---|---:|
| profit first | `+min_adjusted_edge` |
| loss first | `-min_adjusted_edge` |
| time exit | forced adjusted PnL |

今回のhybrid prediction parquetには `*_forced_adjusted_pnl` が無かったため、time exit targetは `*_fixed_720m_adjusted_pnl` へfallbackした。fallback sourceはexample CSVの `candidate_actual_time_exit_source` に残す。

従来の `best_adjusted_pnl` targetはデフォルトとして残し、既存CLI挙動は変えていない。

## OOF Metrics

Validation OOF candidate examples: `9091`

| item | value |
|---|---:|
| target mean | `1.5739` |
| raw predicted mean | `22.0055` |
| mean predicted mean | `2.5594` |
| lower predicted mean | `-14.8536` |
| raw bias | `20.4316` |
| mean bias | `0.9855` |
| lower bias | `-16.4275` |
| raw overestimate mean | `20.4382` |
| mean overestimate mean | `7.7639` |
| lower overestimate mean | `0.1186` |
| mean MAE | `14.5424` |
| mean RMSE | `15.4850` |
| mean R2 | `-0.1730` |
| lower coverage | `0.9925` |

exit event distribution:

| event | count |
|---|---:|
| time exit | `825` |
| profit first | `4575` |
| loss first | `3691` |

## Validation Policy

共通条件:

- Validation months: `2024-07`, `2024-09`, `2024-11`, `2025-01`
- Evaluation multiplier: profit `1.0`, loss `1.20`
- Base policy: `timed_ev`
- Base EV: `pred_long_best_adjusted_pnl`, `pred_short_best_adjusted_pnl`
- Holding: `pred_mlp_*_exit_event_minutes`, max hold `480`
- Candidate spine: entry `12`, short offset `6`, side margin `5`, min rank `0.5`

barrier overestimate risk:

| risk | min pnl | sum pnl | min trades | mean trades | max DD | direction error | EV over mean |
|---:|---:|---:|---:|---:|---:|---:|---:|
| `0.00` | `82.7176` | `406.6546` | `24` | `27.75` | `60.9864` | `0.3809` | `15.5226` |
| `0.05` | `64.1002` | `356.8508` | `22` | `25.50` | `59.7104` | `0.3948` | `16.0825` |
| `0.10` | `27.1240` | `274.2074` | `19` | `21.75` | `65.5536` | `0.4122` | `16.7631` |
| `0.25` | `1.2864` | `126.6808` | `7` | `12.75` | `59.7396` | `0.4014` | `19.2369` |
| `0.50` | `-0.1920` | `39.4142` | `0` | `3.25` | `42.1320` | `0.4250` | `13.8667` |

mean barrier qualityをEVへ直接使った場合:

| selection | min pnl | sum pnl | min trades | mean trades | max DD | direction error | EV over mean |
|---|---:|---:|---:|---:|---:|---:|---:|
| best by min pnl | `-8.7380` | `65.3992` | `9` | `21.25` | `171.8952` | `0.5821` | `3.8284` |
| best with min trades >= 10 | `-22.0486` | `41.0182` | `16` | `36.25` | `171.8952` | `0.6171` | `3.0749` |

lower barrier qualityをEVへ直接使った場合:

| selection | min pnl | sum pnl | min trades | mean trades | max DD | direction error | EV over mean |
|---|---:|---:|---:|---:|---:|---:|---:|
| best by min pnl | `-50.9794` | `-46.2330` | `0` | `74.50` | `65.4654` | `0.2181` | `1.1422` |
| best with min trades >= 10 | `-676.7136` | `-2042.5124` | `9425` | `11401.75` | `684.8542` | `0.4310` | `-14.6198` |

直接EV置換は、meanは方向ミスとDDが大きく、lowerは閾値設計が極端になる。どちらも標準候補ではない。

## Fixed Holdout

barrier overestimate risk, min rank `0.5`:

| month | risk | adjusted pnl | raw pnl | trades | max DD | direction error | EV over mean |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2024-12 | `0.00` | `-31.7576` | `4.998` | `52` | `99.1124` | `0.5962` | `22.1346` |
| 2024-12 | `0.05` | `-59.7292` | `-23.389` | `47` | `85.6152` | `0.6596` | `23.3581` |
| 2024-12 | `0.10` | `-2.2914` | `21.390` | `43` | `53.4326` | `0.6512` | `22.1654` |
| 2024-12 | `0.25` | `-35.5098` | `-21.630` | `23` | `35.5098` | `0.5652` | `25.5075` |
| 2024-12 | `0.50` | `2.1200` | `2.120` | `1` | `0.0000` | `1.0000` | `18.7571` |
| 2025-02 | `0.00` | `47.1824` | `94.519` | `126` | `118.9336` | `0.4127` | `23.2076` |
| 2025-02 | `0.05` | `10.8590` | `52.120` | `110` | `107.5074` | `0.4636` | `23.9386` |
| 2025-02 | `0.10` | `-17.9024` | `23.880` | `110` | `106.4004` | `0.4818` | `24.7478` |
| 2025-02 | `0.25` | `-22.4438` | `9.510` | `74` | `89.4996` | `0.4595` | `26.1315` |
| 2025-02 | `0.50` | `11.7908` | `14.504` | `4` | `16.2792` | `0.5000` | `24.6600` |

2024-12だけならrisk `0.10` や高riskが見えるが、2025-02を削る。高riskは取引数も落ちすぎる。

## Decision

標準policyへ昇格しない。

理由:

- barrier targetは「どこで手放すか」を入れた点では正しいが、現モデルは候補順位付けに十分な汎化性能を出していない。
- soft riskはvalidationでrisk `0` を超えず、fixed holdoutでは片月依存。
- lower quantileは過大評価抑制には効くが、取引判断へ直接使うと情報を落としすぎる。
- time exitがfixed 720m fallbackであり、実際のforced PnL列が無い。targetの意味がまだ粗い。

次は、prediction parquet側に `*_forced_adjusted_pnl` を確実に残すか、exit event class、time-to-event、fixed horizon PnLをjointに扱う校正targetへ進む。今回のtarget modeは診断と比較軸として残す。

## Artifacts

- candidate barrier quality 2024-12 apply: `data/reports/modeling/20260628_164936_candidate_quality_barrier_q25_720m_2024_12/`
- candidate barrier quality 2025-02 apply: `data/reports/modeling/20260628_165001_candidate_quality_barrier_q25_720m_2025_02/`
- barrier risk validation summary: `data/reports/backtests/candidate_quality_barrier_overestimate_risk_summary/20260628_165132_model_sweep_summary/`
- barrier mean direct summary: `data/reports/backtests/candidate_quality_barrier_mean_direct_summary/20260628_165417_model_sweep_summary/`
- barrier lower direct summary: `data/reports/backtests/candidate_quality_barrier_lower_direct_summary/20260628_165559_model_sweep_summary/`
- fixed smoke: `data/reports/backtests/candidate_quality_barrier_overestimate_risk_fixed/`
