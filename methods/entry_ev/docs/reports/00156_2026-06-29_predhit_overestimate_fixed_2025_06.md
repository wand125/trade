# Predhit Overestimate Fixed 2025-06

日時: 2026-06-29 17:43 JST
更新日時: 2026-06-29 17:43 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻である `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## 目的

`00155` で `pred_hit_actual_miss_prob * high-overestimate q75 prob` のinteraction riskは、2025-02..2025-05の固定4ヶ月では `w4` がrisk0/risk5を上回った。

ただしweight感度が大きく、安定した台地ではなかった。今回は `w4` / `w6` を再探索せず、未使用月の2025-06へ固定適用して反証する。

## 前提

2025-06の既存blind prediction artifactは旧schemaで、現行policyに必要な `pred_mlp_*`, stateful risk, failure probability, trade quality, q75 high-overestimate列が揃っていなかった。そのため、2025-05固定確認と同じ学習設定で2025-06用のcurrent hybrid predictionを作り直した。

評価条件は現行標準に合わせる。

- profit multiplier: `1.0`
- loss multiplier: `1.2`
- spread: `0.2`
- slippage: `0.1`
- execution delay: `1`
- policy: `timed_ev`
- entry threshold: `12`
- short threshold offset: `6`
- side margin: `5`
- risk penalty: `5`
- MLP holding guard: `30..480m`

## 生成手順

1. `xauusd_m1_p1_l1p2_policy_combined` に2025-06 datasetを追加。
2. 2025-05固定確認と同じHGB設定で2025-06をtest monthとして学習・予測。
3. 同じMLP設定でexit timing predictionを作り、HGB entry predictionへmerge。
4. `oof-stateful-risk-model` で `walkforward_floor_lowered` riskを2025-06へapply。
5. `oof-trade-failure-model` で `pred_hit_actual_miss`, `ev_overestimate_high`, `exit_regret_high`, `any_failure` を付与。
6. `oof-trade-quality-model` でtrade quality列を付与。
7. `oof-trade-overestimate-high-model` でq75 high-overestimate probabilityを付与。
8. `scripts/experiments/predhit_overestimate_interaction.py` で `w4` / `w6` だけを評価。

stateful risk validation指標:

| target | candidate count | prevalence | predicted mean | bias | brier | AUC |
|---|---:|---:|---:|---:|---:|---:|
| walkforward floor lowered | 1220 | `0.2754` | `0.1214` | `-0.1540` | `0.2131` | `0.6365` |

failure model validation指標:

| target | prevalence | predicted mean | bias | brier | AUC |
|---|---:|---:|---:|---:|---:|
| pred hit actual miss | `0.0717` | `0.0694` | `-0.0023` | `0.0409` | `0.9624` |
| ev overestimate high | `0.0179` | `0.0131` | `-0.0048` | `0.0178` | `0.1912` |
| exit regret high | `0.1992` | `0.1851` | `-0.0141` | `0.1673` | `0.3443` |
| any failure | `0.7112` | `0.7110` | `-0.0002` | `0.2103` | `0.4602` |

q75 high-overestimate validation指標:

| trade count | target rate | predicted mean | bias | brier | AUC | top quartile target rate |
|---:|---:|---:|---:|---:|---:|---:|
| 281 | `0.2811` | `0.2488` | `-0.0323` | `0.2015` | `0.5509` | `0.3662` |

## 結果

2025-06単月では `predhit_q75_w4` / `w6` はbaseline risk5を下回った。`predhit_evhigh` interactionはrisk scaleが小さく、baselineと同一になった。

| label | adjusted PnL | max DD | trades | win rate |
|---|---:|---:|---:|---:|
| risk0 | `120.5302` | `88.1532` | 121 | `0.5372` |
| baseline risk5 | `111.4464` | `88.0656` | 120 | `0.5417` |
| predhit evhigh w4 | `111.4464` | `88.0656` | 120 | `0.5417` |
| predhit evhigh w6 | `111.4464` | `88.0656` | 120 | `0.5417` |
| predhit q75 w4 | `105.8618` | `88.0656` | 122 | `0.5410` |
| predhit q75 w6 | `102.0418` | `88.0656` | 122 | `0.5410` |

risk scale:

| interaction | side | mean risk | p90 risk | max risk |
|---|---:|---:|---:|---:|
| predhit evhigh | long | `0.000488` | `0.000875` | `0.051987` |
| predhit evhigh | short | `0.002115` | `0.006158` | `0.062800` |
| predhit q75 | long | `0.006018` | `0.007162` | `0.106785` |
| predhit q75 | short | `0.032325` | `0.110356` | `0.164072` |

## Delta Diagnosis

baseline risk5と比較した差分:

| candidate | PnL delta | base trades | candidate trades | removed positive | removed negative | added positive | added negative |
|---|---:|---:|---:|---:|---:|---:|---:|
| predhit q75 w4 | `-5.5846` | 120 | 122 | `25.6700` | `0.0000` | `29.5030` | `-3.9156` |
| predhit q75 w6 | `-9.4046` | 120 | 122 | `25.6700` | `0.0000` | `25.6830` | `-3.9156` |

悪化の主因は、baseline側の良い `only_base short/range_normal_vol +25.6700` を落としたこと。追加tradeである `only_candidate short/range_normal_vol` はw4では `+25.6000`、w6では `+21.7800` で、落とした利益を完全には埋められない。さらに `only_candidate long/up_low_vol -3.9156` が加わる。

この形は、2025-02..2025-05の改善が「狭いinteractionが悪いexit/holdingを少し動かした」可能性を示しつつも、未使用月では良いbase tradeの取りこぼしとして出たことを意味する。

## 判断

1. `predhit_q75_w4` / `w6` は2025-06固定未使用月でbaseline risk5に負けたため、標準policy候補から降格する。
2. `predhit_evhigh` interactionは発火幅が小さく、今回もbaselineと同一。単独で追う優先度は低い。
3. 2025-06は `risk0` が `baseline risk5` も上回った。stateful risk5はmax DDをわずかに下げるだけで利益を削っており、risk penalty全般を利益最大化signalとして扱いすぎない。
4. q75 high-overestimate probabilityは、直接risk penaltyではなく、exit timing calibration、EV過大評価校正、またはselected tradeのdiagnostic featureとして残す。
5. 次はinteraction重み探索を続けるより、未使用月で壊れた取引差分を教師化する。特に「良いbase tradeを落とす/悪いcandidate tradeを追加する」経路依存をstateful targetへ戻す。

## Artifacts

- 2025-06 dataset: `data/processed/datasets/xauusd_m1_p1_l1p2_policy_combined/xauusd_m1_2025-06_h24_edge15.parquet`
- HGB 2025-06: `experiments/20260629_083635_policy_combined_side_exit_test_2025_06/`
- MLP 2025-06: `experiments/20260629_083658_shared_mlp_hgb_split_test_2025_06/`
- hybrid 2025-06: `data/reports/modeling/20260629_hgb_mlp_exit_hybrid_2025_06/`
- stateful apply: `data/reports/modeling/20260629_083956_stateful_risk_mean_match_session_floor_lowered_apply_2025_06/`
- failure apply: `experiments/20260629_084045_trade_failure_pred_hit_ev_overestimate_highcost_risk5_apply_2025_06/`
- trade quality apply: `experiments/20260629_084143_trade_quality_with_failure_prob_highcost_risk5_apply_2025_06/`
- q75 high-overestimate apply: `experiments/20260629_084211_trade_overestimate_high_q75_expanding_min3_highcost_risk5_apply_2025_06/`
- interaction evaluation: `data/reports/modeling/20260629_084234_predhit_overestimate_interaction_fixed_2025_06/`
- interaction backtests: `data/reports/backtests/20260629_084234_predhit_overestimate_interaction_fixed_2025_06/`
- w4 delta: `data/reports/backtests/20260629_084308_predhit_q75_w4_fixed_2025_06_delta/`
- w6 delta: `data/reports/backtests/20260629_084308_predhit_q75_w6_fixed_2025_06_delta/`

## 検証

- `python3 -m trade_data.meta_model oof-stateful-risk-model`: pass
- `python3 -m trade_data.meta_model oof-trade-failure-model`: pass
- `python3 -m trade_data.meta_model oof-trade-quality-model`: pass
- `python3 -m trade_data.meta_model oof-trade-overestimate-high-model`: pass
- `python3 scripts/experiments/predhit_overestimate_interaction.py --months 2025-06 --weights 4,6`: pass
- `python3 -m trade_data.backtest model-trade-delta`: pass, w4/w6

## 次の作業

1. q75 interactionの標準採用は止める。
2. `risk0 > risk5` となった2025-06を含め、stateful riskを「利益最大化」ではなく「drawdown/損失抑制」の補助signalとして再評価する。
3. 2025-06の `only_base short/range_normal_vol +25.6700` を落とす失敗を、entry/exit/holdingのstateful targetへ戻す。
4. 直接penaltyよりも、exit timing targetとEV calibrationの補助特徴として `pred_hit_actual_miss` / q75 high-overestimateを使う。
