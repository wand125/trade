# Joint Exit Candidate Quality Target

日時: 2026-06-29 02:28 JST
更新日時: 2026-06-29 02:28 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

前回の結論に沿って、forced barrier target単独ではなく、exit event、time-to-event、fixed horizon PnL、best PnLを混ぜた `joint_exit_adjusted_pnl` targetを追加した。

結論:

- OOFの回帰指標はforced barrier targetより改善した。
- ただし、生成したoverestimate riskを実行policyへsoft penaltyとして入れると、validationではrisk `0` が最良のまま。
- mean-riskもlower-riskも、fixed 2024-12 / 2025-02の両方で安定した改善にならない。
- 標準policyには採用しない。target familyと診断列は残し、次はscalar risk penaltyではなく、exit event class、time-to-event、side/regime別calibrationを分解して扱う。

## Implementation

`oof-candidate-quality-model --target-mode joint_exit_adjusted_pnl` を追加した。

targetは候補sideごとに以下を正規化weightで混合する。

```text
joint_target =
  0.7 * timed_barrier_component
+ 0.2 * fixed_horizon_component
+ 0.1 * clipped_best_component
```

今回の設定:

- barrier weight: `0.7`
- fixed horizon weight: `0.2`
- best PnL weight: `0.1`
- event time decay: `0.25`
- component clip: `min_adjusted_edge * 1.0`
- fixed horizon minutes: `60,240,720`
- evaluation multiplier: profit `1.0`, loss `1.20`

candidate examplesには診断列として以下を残す。

- `candidate_actual_barrier_target`
- `candidate_actual_timed_barrier_component`
- `candidate_actual_fixed_horizon_component`

## OOF Metrics

candidate countは `9091`。

| item | forced barrier | joint exit |
|---|---:|---:|
| target mean | `1.6521` | `2.3994` |
| raw bias | `20.3534` | `19.6061` |
| mean bias | `0.8738` | `0.6522` |
| lower bias | `-16.5050` | `-9.5179` |
| mean overestimate mean | `7.7839` | `5.6784` |
| lower overestimate mean | `0.1194` | `1.3386` |
| mean MAE | `14.6941` | `10.7047` |
| mean RMSE | `15.5222` | `11.4542` |
| mean R2 | `-0.1692` | `-0.1613` |
| lower coverage | `0.9925` | `0.6800` |

OOF上はMAE/RMSE/biasが改善した。特にlower coverageが過度に保守的だった状態から `0.6800` へ戻った。

## Validation Policy

共通条件:

- Validation months: `2024-07`, `2024-09`, `2024-11`, `2025-01`
- Base policy: `timed_ev`
- Entry spine: entry `12`, short offset `6`, side margin `5`, min rank `0.5`
- Base EV: `pred_long_best_adjusted_pnl`, `pred_short_best_adjusted_pnl`
- Holding: `pred_mlp_*_exit_event_minutes`, max hold `480`
- Risk penalties: `0,0.05,0.1,0.25,0.5,1,2`

mean overestimate risk:

| risk | min pnl | sum pnl | min trades | mean trades | max DD |
|---:|---:|---:|---:|---:|---:|
| `0.00` | `82.7176` | `406.6546` | `24` | `27.75` | `60.9864` |
| `0.05` | `35.4626` | `293.3680` | `22` | `25.25` | `58.7664` |
| `0.10` | `26.4640` | `258.5756` | `19` | `21.50` | `64.6908` |
| `0.25` | `-22.4846` | `108.4986` | `9` | `12.75` | `59.7396` |
| `0.50` | `-25.5398` | `-6.5898` | `0` | `2.75` | `42.1320` |

lower overestimate risk:

| risk | min pnl | sum pnl | min trades | mean trades | max DD |
|---:|---:|---:|---:|---:|---:|
| `0.00` | `82.7176` | `406.6546` | `24` | `27.75` | `60.9864` |
| `0.05` | `10.8048` | `303.3922` | `22` | `24.75` | `58.7664` |
| `0.10` | `-6.7386` | `224.8774` | `18` | `21.25` | `65.6508` |
| `0.25` | `-2.2290` | `127.5710` | `5` | `8.25` | `44.4036` |
| `0.50` | `0.0000` | `0.0000` | `0` | `0.00` | `0.0000` |

比較上、forced barrier mean-riskはrisk `0.05` でvalidation min pnl `62.5366`、risk `0.10` で `27.0340`。joint mean-riskはOOF指標が良いにもかかわらず、実行policy上はforced barrier riskを超えない。

## Fixed Smoke

min rank `0.5` だけを比較した。

joint mean overestimate risk:

| month | risk | adjusted pnl | raw pnl | trades | max DD | direction error |
|---|---:|---:|---:|---:|---:|---:|
| 2024-12 | `0.00` | `-31.7576` | `4.998` | `52` | `99.1124` | `0.5962` |
| 2024-12 | `0.05` | `-62.3712` | `-25.479` | `47` | `87.8472` | `0.6596` |
| 2024-12 | `0.10` | `-15.8984` | `8.722` | `44` | `67.1276` | `0.6364` |
| 2024-12 | `0.25` | `-41.0600` | `-26.432` | `28` | `41.0600` | `0.6429` |
| 2025-02 | `0.00` | `47.1824` | `94.519` | `126` | `118.9336` | `0.4127` |
| 2025-02 | `0.05` | `12.8810` | `54.170` | `110` | `107.5074` | `0.4636` |
| 2025-02 | `0.10` | `-12.9558` | `28.336` | `109` | `103.3764` | `0.4771` |
| 2025-02 | `0.25` | `-71.0294` | `-32.407` | `76` | `124.2122` | `0.4474` |

joint lower overestimate risk:

| month | risk | adjusted pnl | raw pnl | trades | max DD | direction error |
|---|---:|---:|---:|---:|---:|---:|
| 2024-12 | `0.00` | `-31.7576` | `4.998` | `52` | `99.1124` | `0.5962` |
| 2024-12 | `0.05` | `-1.6336` | `25.411` | `47` | `54.8100` | `0.6170` |
| 2024-12 | `0.10` | `-23.0408` | `3.039` | `43` | `61.2558` | `0.6279` |
| 2024-12 | `0.25` | `-23.4172` | `-16.296` | `11` | `33.7362` | `0.6364` |
| 2025-02 | `0.00` | `47.1824` | `94.519` | `126` | `118.9336` | `0.4127` |
| 2025-02 | `0.05` | `23.7418` | `63.739` | `111` | `89.9544` | `0.4685` |
| 2025-02 | `0.10` | `39.7902` | `81.370` | `109` | `105.0304` | `0.4679` |
| 2025-02 | `0.25` | `13.3350` | `33.497` | `49` | `51.8520` | `0.5918` |

lower-risk `0.05` は2024-12の損失を大きく縮めるが、2025-02ではrisk `0` より悪化する。validationでもrisk `0.05` のmin pnlは `10.8048` まで落ちるため、事前選択できる台地ではない。

## Decision

`joint_exit_adjusted_pnl` はtarget設計としては前進。OOF上の平均回帰誤差は明確に改善した。

ただし、実行policyへ単一のoverestimate riskとして入れる経路は採用しない。

理由:

- validation最良はrisk `0` のままで、risk penaltyを入れるほどfold最低PnLが落ちる。
- fixed smokeでは2024-12改善と2025-02悪化が入れ替わり、月依存の挙動になっている。
- OOFの回帰誤差改善が、entry/side/exitの意思決定改善に変換されていない。

次はjoint targetを一つのscalar penaltyへ潰さず、以下に分解する。

- exit event classの校正
- time-to-eventの校正
- side/regime別のEV residual
- fixed horizon成分とbarrier成分の別モデル化
- policy選択時の複数holdout同時監査

## Artifacts

- joint quality 2024-12 apply: `data/reports/modeling/20260628_172218_candidate_quality_joint_exit_w721_2024_12/`
- joint quality 2025-02 apply: `data/reports/modeling/20260628_172218_candidate_quality_joint_exit_w721_2025_02/`
- mean-risk validation sweeps: `data/reports/backtests/candidate_quality_joint_exit_overestimate_risk_validation/`
- mean-risk validation summary: `data/reports/backtests/candidate_quality_joint_exit_overestimate_risk_summary/20260628_172335_model_sweep_summary/`
- lower-risk validation sweeps: `data/reports/backtests/candidate_quality_joint_exit_lower_overestimate_risk_validation/`
- lower-risk validation summary: `data/reports/backtests/candidate_quality_joint_exit_lower_overestimate_risk_summary/20260628_172653_model_sweep_summary/`
- mean-risk fixed smoke: `data/reports/backtests/candidate_quality_joint_exit_overestimate_risk_fixed/`
- lower-risk fixed smoke: `data/reports/backtests/candidate_quality_joint_exit_lower_overestimate_risk_fixed/`
