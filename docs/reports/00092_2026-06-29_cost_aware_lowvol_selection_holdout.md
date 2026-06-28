# Cost-aware Low-vol Selection Holdout

日時: 2026-06-29 04:06 JST
更新日時: 2026-06-29 04:06 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻である `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## 目的

`00091` では `short low-vol side EV combo` がzero-cost fixed holdoutで改善したが、cost stressで崩れた。

今回は同じrule set gridをmoderate cost validationでも評価し、既存 `model-candidate-selection` でbase/cost両方を満たす候補を選び、selection topを固定holdoutのcost stressで確認する。

## 条件

- validation months: `2024-07`, `2024-09`, `2024-11`, `2025-01`
- holdout months: `2024-12`, `2025-02`, `2025-03`
- policy: `timed_ev`
- entry threshold: `12`
- long offset: `0`
- short offset: `6`
- side margin: `5`
- min entry rank: `0.5`
- holding columns: `pred_mlp_long_exit_event_minutes`, `pred_mlp_short_exit_event_minutes`
- max predicted hold: `480`
- evaluation multipliers: profit `1.0`, loss `1.20`
- moderate validation cost: `spread=0.1`, `slippage=0.05`, `execution_delay=1`

Candidate selection gates:

- min folds: `4`
- min trades per fold: `50`
- max forced exit rate: `0.05`
- max drawdown: `100` for strict, `120` for relaxed diagnostic
- min base adjusted pnl per fold: `80`
- min cost adjusted pnl per fold: `50`
- max short trade share: `0.65`
- max side trade share: `0.90`

## Moderate Cost Validation

Moderate costを入れても、validation topは `down5,up10,range5` だった。

| rule set | base min pnl | base sum pnl | mid-cost min pnl | mid-cost sum pnl | min trades | max drawdown |
|---|---:|---:|---:|---:|---:|---:|
| `down5,up10,range5` | `138.3706` | `676.1198` | `121.9972` | `621.3662` | `66` | `86.9156` |
| `down5,up10` | `138.0338` | `622.6486` | `112.1696` | `560.1664` | `65` | `87.1114` |
| `down5,up15` | `131.3082` | `623.1814` | `111.3052` | `530.7204` | `70` | `98.6364` |
| `down5,up15,range10` | `118.7610` | `638.9718` | `100.6632` | `574.3542` | `70` | `115.1136` |
| `down10,up10,range10` | `116.8422` | `630.6662` | `98.9742` | `585.3352` | `71` | `115.5498` |
| none | `82.7176` | `406.6546` | `74.6258` | `387.6658` | `24` | `64.9128` |

`none` はtrade数不足とshort share超過でselection対象から外れる。これはNoTrade寄りに逃げる候補を落とすという意味では妥当。

## Candidate Selection

strict条件では4候補がeligible。

| rule set | eligible | base min pnl | cost min pnl | max drawdown | max short share | max side share |
|---|---:|---:|---:|---:|---:|---:|
| `down5,up10,range5` | yes | `138.3706` | `121.9972` | `86.9156` | `0.3662` | `0.8732` |
| `down5,up10` | yes | `138.0338` | `112.1696` | `87.1114` | `0.3973` | `0.8462` |
| `down5,up15` | yes | `131.3082` | `111.3052` | `98.6364` | `0.4068` | `0.8143` |
| `up10,range10` | yes | `104.7616` | `67.9610` | `97.2002` | `0.3457` | `0.8571` |
| `down5,up15,range10` | no | `118.7610` | `100.6632` | `115.1136` | `0.3469` | `0.8857` |

`00091` でzero-cost holdoutが3ヶ月全てプラスだった `down5,up15,range10` は、validation drawdown gateで落ちる。これはcost-aware selection上は妥当な反応。

## Holdout Cost Stress

strict selection topの `down5,up10,range5` を固定holdoutでcost stressした。

| month | no cost | moderate cost | high cost | worst case | trades | no-cost max drawdown |
|---|---:|---:|---:|---:|---:|---:|
| 2024-12 | `-0.0572` | `-11.7670` | `-32.4176` | `-40.3112` | `91` | `124.8264` |
| 2025-02 | `98.6956` | `50.1102` | `16.4182` | `16.4182` | `153` | `140.8512` |
| 2025-03 | `26.8776` | `14.9374` | `-15.6634` | `-34.6572` | `139` | `82.4024` |

Cost scenarios:

- moderate: `spread=0.1`, `slippage=0.05`, `execution_delay=1`
- high: `spread=0.2`, `slippage=0.1`, `execution_delay=1`
- worst case: month内stress gridの最小adjusted pnl

Scenario別3ヶ月集計:

| spread | slippage | delay | sum pnl | min month pnl | max drawdown |
|---:|---:|---:|---:|---:|---:|
| `0.0` | `0.00` | `1` | `137.9352` | `8.8550` | `158.0102` |
| `0.0` | `0.00` | `0` | `125.5160` | `-0.0572` | `140.8512` |
| `0.0` | `0.05` | `1` | `95.6640` | `-1.4470` | `163.9002` |
| `0.1` | `0.05` | `1` | `53.2806` | `-11.7670` | `169.8202` |
| `0.2` | `0.10` | `1` | `-31.6628` | `-32.4176` | `181.6922` |

## 判断

cost-aware validation selectionは、zero-costだけの選定より前進している。`down5,up10,range5` はvalidationのbase/cost双方で強く、前回の `down5,up15,range10` よりholdout moderate costの損失も小さい。

それでも標準policyには昇格しない。理由は3つ。

- 2024-12がno-cost時点で `-0.0572` と実質NoTrade近辺で、moderate costでは `-11.7670`。
- 2025-03はhigh costで `-15.6634`、stress worstで `-34.6572`。
- holdout max drawdownが2024-12 `124.8264`、2025-02 `140.8512` とvalidation selection時の想定より大きい。

次はrule set探索をこれ以上広げるより、selection基準を「fold月のPnL」だけでなく、cost-stress上のdrawdown、月別下振れ、局所direction/session損失、EV overestimateを同時に扱う。特に、validationでmax drawdownが低く見える候補がholdoutでdrawdown拡大しており、drawdown予測またはstress-aware rankingが必要。

## Artifacts

- midcost validation sweep: `data/reports/backtests/component_fixed_weighted_short_lowvol_combo_validation_midcost/`
- strict cost-aware selection: `data/reports/backtests/component_fixed_weighted_short_lowvol_combo_cost_aware_selection_strict/20260628_190417_model_candidate_selection/`
- relaxed drawdown selection: `data/reports/backtests/component_fixed_weighted_short_lowvol_combo_cost_aware_selection_relaxed_dd/20260628_190418_model_candidate_selection/`
- top holdout cost stress: `data/reports/backtests/component_fixed_weighted_short_lowvol_combo_costaware_top_cost_stress/`

## Verification

- `PYTHONPATH=src python3 -m trade_data.backtest model-sweep`: OK for 4fold moderate cost validation
- `PYTHONPATH=src python3 -m trade_data.backtest model-candidate-selection`: OK for strict and relaxed selection
- `PYTHONPATH=src python3 -m trade_data.backtest model-cost-sensitivity`: OK for 2024-12 / 2025-02 / 2025-03 holdout stress
