# Candidate Entry Failure Model

日時: 2026-06-29 01:02 JST
更新日時: 2026-06-29 01:02 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

selected trades 106件だけでfailure targetを学習する弱点を緩和するため、entry条件を通ったcandidate row全体からfailure probabilityを学習する `oof-candidate-failure-model` を追加した。

結論:

- candidate例は `9,091` 件まで増えたが、`large_adverse` OOF AUCは `0.3738` と逆相関気味で、通常riskとしては使えない。
- 反転risk `-(1 - prob)` も診断したが、validationのfold最低PnLはriskなしに届かなかった。
- fixed holdoutでは risk `10` が2024-12を改善する一方、2025-02をマイナス化した。
- したがって candidate-entry failure riskは標準採用しない。実装は診断基盤として残す。

## Implementation

追加CLI:

```bash
python3 -m trade_data.meta_model oof-candidate-failure-model
```

主な出力列:

- `pred_candidate_failure_<target>_<side>_prob`
- `pred_candidate_failure_<target>_<side>_risk`
- `pred_candidate_failure_<target>_taken_prob`

今回のtarget:

- `large_adverse`
- label: side別 `max_adverse_pnl <= -10`

`best_adjusted_pnl <= -10` はcandidate条件通過行では陽性がほぼ出ないため、今回は「最良退出後の最終損」ではなく「保有中に大きな逆行を食らう候補」をfailure proxyにした。

## Setup

- Base predictions: HGB entry/side + MLP exit timing hybrid
- Validation months: `2024-07`, `2024-09`, `2024-11`, `2025-01`
- Fixed holdout months: `2024-12`, `2025-02`
- Candidate filter: entry `12`, short offset `6`, side margin `5`, min rank `0.5`
- Evaluation multiplier: profit `1.0`, loss `1.20`
- Policy: `timed_ev`
- EV columns: `pred_long_best_adjusted_pnl`, `pred_short_best_adjusted_pnl`
- Holding columns: `pred_mlp_long_exit_event_minutes`, `pred_mlp_short_exit_event_minutes`
- Max predicted hold: `480` minutes

## OOF Metrics

| item | value |
|---|---:|
| candidate count | `9091` |
| long candidates | `2530` |
| short candidates | `6561` |
| prevalence | `0.5322` |
| predicted mean | `0.5007` |
| bias | `-0.0315` |
| brier | `0.2930` |
| AUC | `0.3738` |

Fold別AUC:

| holdout | candidates | prevalence | predicted mean | AUC |
|---|---:|---:|---:|---:|
| 2024-07 | `2124` | `0.2928` | `0.6075` | `0.3623` |
| 2024-09 | `1156` | `0.6055` | `0.4773` | `0.5208` |
| 2024-11 | `4075` | `0.6417` | `0.4328` | `0.4618` |
| 2025-01 | `1736` | `0.5190` | `0.5450` | `0.5117` |

2024-07 / 2024-11 のregime shiftが大きく、月別prevalenceに対してOOF予測平均が逆側に外れている。

## Validation Policy

通常risk `-prob`:

| risk | min pnl | sum pnl | min trades | mean trades | max DD | direction error | EV over mean |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | `82.7176` | `406.6546` | `24` | `27.75` | `60.9864` | `0.3809` | `15.5226` |
| 5 | `3.1382` | `275.5558` | `21` | `26.25` | `61.3428` | `0.3914` | `16.9884` |
| 10 | `5.9462` | `236.2612` | `13` | `21.00` | `62.0892` | `0.3947` | `17.7198` |
| 15 | `-27.2974` | `159.6310` | `5` | `12.50` | `64.9490` | `0.4108` | `19.8918` |
| 20 | `-32.2014` | `52.6534` | `4` | `6.75` | `83.2374` | `0.3830` | `20.8546` |
| 30 | `0.0000` | `42.5630` | `0` | `2.75` | `55.7364` | `0.1591` | `6.0596` |

反転risk `-(1 - prob)`:

| risk | min pnl | sum pnl | min trades | mean trades | max DD | direction error | EV over mean |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | `82.7176` | `406.6546` | `24` | `27.75` | `60.9864` | `0.3809` | `15.5226` |
| 5 | `39.9032` | `303.9662` | `22` | `26.00` | `66.7512` | `0.3916` | `16.8078` |
| 10 | `24.1200` | `261.0670` | `17` | `24.00` | `61.1352` | `0.3407` | `18.0455` |
| 15 | `5.3778` | `166.2316` | `11` | `12.75` | `42.1320` | `0.3212` | `18.9857` |
| 20 | `0.5170` | `89.4574` | `3` | `4.25` | `25.8720` | `0.1667` | `20.9286` |
| 30 | `0.0000` | `70.3790` | `0` | `1.25` | `1.7040` | `0.1250` | `6.9435` |

反転riskは通常riskよりは悪化が小さいが、riskなしを超えない。raw `large_loss threshold=10` risk topの validation min pnl `92.8530` にも届かない。

## Fixed Holdout

通常risk:

| month | risk | adjusted pnl | raw pnl | trades | profit factor | max DD | direction error |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2024-12 | 0 | `-31.7576` | `4.998` | `52` | `0.8560` | `99.1124` | `0.5962` |
| 2024-12 | 10 | `19.2252` | `31.945` | `40` | `1.2519` | `31.9748` | `0.6250` |
| 2025-02 | 0 | `47.1824` | `94.519` | `126` | `1.1661` | `118.9336` | `0.4127` |
| 2025-02 | 10 | `-18.6000` | `25.731` | `111` | `0.9301` | `73.9420` | `0.4865` |

2024-12だけならrisk `10` は改善するが、2025-02で壊れる。これはvalidationでriskなしが最良だった結果と整合する。

## Decision

標準policyへ昇格しない。

理由:

- OOF AUCが `0.3738` と弱く、単純なprobability riskは方向が信頼できない。
- 反転riskを使ってもvalidationのfold最低PnLはriskなしに届かない。
- fixed holdoutの改善が片月依存で、2025-02をNoTrade未満にする。
- `large_adverse` は「保有中の痛み」は捉えるが、「24h以内の最終損益最大化」に直結しない可能性が高い。

次はcandidate rowを使う場合でも、二値adverse分類ではなく、entry候補の連続的な期待値・下方分位・exit-timing込みの実現可能PnLをtarget化する。また、candidate failureを使うなら月別prevalence shiftを補正するcalibrationを先に入れる。

## Artifacts

- candidate model 2024-12 apply: `data/reports/modeling/20260628_155801_candidate_failure_large_adverse_t10_2024_12/`
- candidate model 2025-02 apply: `data/reports/modeling/20260628_155821_candidate_failure_large_adverse_t10_2025_02/`
- normal validation smoke: `data/reports/backtests/candidate_failure_large_adverse_t10_smoke_validation/`
- normal validation summary: `data/reports/backtests/candidate_failure_large_adverse_t10_smoke_summary/20260628_160008_model_sweep_summary/`
- inverse validation smoke: `data/reports/backtests/candidate_failure_large_adverse_t10_inverse_smoke_validation/`
- inverse validation summary: `data/reports/backtests/candidate_failure_large_adverse_t10_inverse_smoke_summary/20260628_160203_model_sweep_summary/`
- fixed smoke: `data/reports/backtests/candidate_failure_large_adverse_t10_fixed_smoke/`
