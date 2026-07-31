# Candidate Entry Quality Quantile

日時: 2026-06-29 01:21 JST
更新日時: 2026-06-29 01:21 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

candidate-entry failure modelの反省を受け、二値failureではなく、entry候補行ごとの連続的な実現可能PnLを学習する `oof-candidate-quality-model` を追加した。平均回帰と下方分位回帰を同時に作り、直接EV置換と過大評価risk penaltyの両方を評価した。

結論:

- 連続targetはcandidate `9,091` 件で学習できたが、OOF平均モデルの `R2` は `-0.0509` で、実現PnLの順位付けには弱い。
- 下方分位は過大評価平均を `1.5366` まで下げるが、保守的すぎて取引候補を壊す。
- mean/lowerをEVへ直接使うとvalidation 4foldが大きくマイナス化する。
- lower overestimate riskは固定2024-12を少し救う一方、2025-02を壊す。validationでも最良はrisk `0`。
- 標準policyへは採用しない。candidate quality列は診断基盤として残し、次はexit timing込みtargetとcalibrationの使い方を改善する。

## Implementation

追加CLI:

```bash
python3 -m trade_data.meta_model oof-candidate-quality-model
```

主な出力列:

- `pred_candidate_quality_long_adjusted_pnl`
- `pred_candidate_quality_short_adjusted_pnl`
- `pred_candidate_quality_long_lower_adjusted_pnl`
- `pred_candidate_quality_short_lower_adjusted_pnl`
- `pred_candidate_quality_*_overestimate_risk`
- `pred_candidate_quality_*_lower_overestimate_risk`

平均モデルは `HistGradientBoostingRegressor`、下方分位は `loss=quantile`, `quantile=0.25` を使う。targetはcandidate side別の `*_best_adjusted_pnl` で、candidate filterは直近raw top骨格に合わせた。

## Setup

- Base predictions: HGB entry/side + MLP exit timing hybrid
- Validation months: `2024-07`, `2024-09`, `2024-11`, `2025-01`
- Fixed holdout months: `2024-12`, `2025-02`
- Candidate filter: entry `12`, short offset `6`, side margin `5`, min rank `0.5`
- Evaluation multiplier: profit `1.0`, loss `1.20`
- Policy: `timed_ev`
- Base EV columns: `pred_long_best_adjusted_pnl`, `pred_short_best_adjusted_pnl`
- Holding columns: `pred_mlp_long_exit_event_minutes`, `pred_mlp_short_exit_event_minutes`
- Max predicted hold: `480` minutes

## OOF Metrics

| item | value |
|---|---:|
| candidate count | `9091` |
| target mean | `23.1947` |
| raw predicted mean | `22.0055` |
| mean predicted mean | `20.3131` |
| lower predicted mean | `7.8121` |
| raw bias | `-1.1892` |
| mean bias | `-2.8816` |
| lower bias | `-15.3826` |
| raw overestimate mean | `7.7361` |
| mean overestimate mean | `6.6840` |
| lower overestimate mean | `1.5366` |
| mean MAE | `16.2496` |
| mean RMSE | `23.7564` |
| mean R2 | `-0.0509` |
| lower coverage | `0.6845` |

平均モデルはraw EVより過大評価平均を下げたが、`R2` が負で、候補順位としては弱い。下方分位は過大評価抑制には効くが、予測平均がtarget meanから大きく下がり、entry scoreとしては保守的すぎる。

## Validation Policy

mean candidate qualityをEVへ直接使った場合:

| selection | min pnl | sum pnl | min trades | mean trades | max DD | direction error | EV over mean |
|---|---:|---:|---:|---:|---:|---:|---:|
| best by min pnl | `-190.2562` | `-256.5606` | `206` | `433.75` | `274.3592` | `0.5170` | `24.2058` |

lower candidate qualityをEVへ直接使った場合:

| selection | min pnl | sum pnl | min trades | mean trades | max DD |
|---|---:|---:|---:|---:|---:|
| best with min trades >= 10 | `-152.8084` | `-431.4170` | `71` | `207.00` | `215.1460` |

lower overestimate riskを既存raw EVへsoft penaltyとして使った場合:

| risk | min pnl | sum pnl | min trades | mean trades | max DD | direction error | EV over mean |
|---:|---:|---:|---:|---:|---:|---:|---:|
| `0.00` | `82.7176` | `406.6546` | `24` | `27.75` | `60.9864` | `0.3809` | `15.5226` |
| `0.10` | `5.6070` | `201.6772` | `19` | `21.75` | n/a | n/a | n/a |
| `0.25` | `-16.5668` | `109.7294` | `8` | `12.75` | n/a | n/a | n/a |
| `0.50` | `1.1300` | `196.9250` | `1` | `4.50` | n/a | n/a | n/a |
| `1.00` | `-155.3284` | `-147.0434` | `0` | n/a | n/a | n/a | n/a |

直接EV置換は採用不可。risk penaltyもvalidation topはrisk `0` のままで、candidate quality由来のriskはfold最低PnLを改善しない。

## Fixed Holdout

lower overestimate risk:

| month | risk | adjusted pnl | raw pnl | trades | max DD | direction error |
|---|---:|---:|---:|---:|---:|---:|
| 2024-12 | `0.0` | `-31.7576` | `4.998` | `52` | `99.1124` | `0.5962` |
| 2024-12 | `0.1` | `-35.6986` | `-8.493` | `43` | `70.1478` | `0.6512` |
| 2024-12 | `0.5` | `-4.8092` | `-1.616` | `5` | `16.7792` | `0.4000` |
| 2025-02 | `0.0` | `47.1824` | `94.519` | `126` | `118.9336` | `0.4127` |
| 2025-02 | `0.1` | `9.8588` | `47.616` | `109` | `92.8764` | `0.4679` |
| 2025-02 | `0.5` | `-45.8502` | `-31.122` | `24` | `76.9890` | `0.7083` |

`risk=0.5` は2024-12の損失を縮めるが、取引数が5件まで落ち、2025-02をNoTrade未満にする。`risk=0.1` も2025-02の利益を大きく削る。

## Decision

標準policyへ昇格しない。

理由:

- OOF平均回帰の `R2` が負で、candidate qualityを直接EV化する根拠が弱い。
- 下方分位は過大評価抑制には効くが、trade selectionでは過剰に保守化する。
- validation 4foldではrisk `0` が最良で、quality riskを足すほどfold最低PnLが悪化する。
- fixed holdout改善は2024-12寄りで、2025-02を壊す。

次はcandidate rowを使う場合も、単純な最終best adjusted PnLの平均/下方分位ではなく、`entry -> exit` の時間構造、profit/loss barrier到達順、forced exit、予測EVのcalibration誤差を一体で扱うtargetに寄せる。candidate qualityはhard gateではなく、診断・過大評価分析・calibration補助として使う。

## Artifacts

- candidate quality 2024-12 apply: `data/reports/modeling/20260628_161319_candidate_quality_q25_2024_12/`
- candidate quality 2025-02 apply: `data/reports/modeling/20260628_161344_candidate_quality_q25_2025_02/`
- mean direct validation sweeps: `data/reports/backtests/candidate_quality_mean_direct_validation/`
- mean direct summary: `data/reports/backtests/candidate_quality_mean_direct_summary/20260628_161542_model_sweep_summary/`
- lower direct validation sweeps: `data/reports/backtests/candidate_quality_lower_direct_validation/`
- lower direct summary: `data/reports/backtests/candidate_quality_lower_direct_summary/20260628_161659_model_sweep_summary/`
- lower overestimate risk validation sweeps: `data/reports/backtests/candidate_quality_lower_overestimate_risk_validation/`
- lower overestimate risk summary: `data/reports/backtests/candidate_quality_lower_overestimate_risk_summary/20260628_161822_model_sweep_summary/`
- fixed holdout: `data/reports/backtests/candidate_quality_lower_overestimate_risk_fixed/`
