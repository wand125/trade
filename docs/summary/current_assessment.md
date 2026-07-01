# Current Assessment

最終更新: 2026-07-02 02:17 JST

## 結論

標準採用できる利益最大化policyはまだない。

現在の実務上の標準判断は NoTrade-first。候補policyは、複数chronological window、role/month PnL floor、trade support、side balance、NoTrade比較を通らない限り標準化しない。

研究の価値は明確に残っている。backtest、OOF、walk-forward、candidate selection、trade delta、context guard、entry budget、entry EV calibration、component target診断までの基盤は使える。問題は「signalが全くない」ではなく、「単一gateや単一validation windowで拾ったedgeが別windowで反転する」こと。

## 現在の判断

| 項目 | 状態 | 判断 |
|---|---|---|
| Standard policy | なし | NoTrade-firstを維持 |
| Best current evidence | `00253` で `exit_risk bucket t0.10..t0.20` hard selectorがfixed 2025でpositive total/worst month改善したが、`00254` のchronological validationではbaseline超えなし。`00256` のfixed stressもpolicy evidenceではない | fixed-window candidate rejected for now |
| Latest diagnostic result | `00260` でexit-regret selectorのonly-candidate replacementを `replacement_stateful_net` targetで分解。`conf_gap_extreme` はbroad/fixedで10 rows / harmful 8 / stateful net `-378.9356` を拾う | replacement-risk replay candidate / not standard |
| Pointwise screens | q95 floor5 の high EV-overestimate risk rows は損失を拾うが、contextによって勝ちも削る | replacement未評価なのでpolicyではない |
| Main failure | validation support不足、fold間EV scale drift、side/context反転、exit capture不足、one-position replacement、common-entry loss、target featureのwindow依存 | hard blockではなく分解targetで扱う |

## 研究レーン

| レーン | 代表reports | 現状 |
|---|---|---|
| Short budget / side drift | `00174`..`00207` | `budget0` や side drift guard はtailを縮めるが、same-family / 2024 chronologyで標準採用には届かない。診断baselineとして残す。 |
| Entry EV admission | `00208`..`00221` | raw / calibrated EV threshold、rank gate、quantile admission、positive floorを検証。候補数やscaleは改善するが、NoTrade-first selectorは通らない。 |
| Exit capture / hold cap | `00222`..`00232` | `720m` や executable EV calibration は診断上有効。ただし月次tail、support不足、fresh/refit反転が残る。direct score標準化はしない。 |
| Side balance / downside | `00233`..`00239` | side-balance単独、downside interaction、coverage gate、composite gateはいずれも標準候補を生まない。component targetへ分解する方針に転換。 |
| Component target / EV overestimate / direction / replacement / exit | `00240`..`00260` | EV overestimateは有効だがfixed/broad residualではloss-first / exit-regret系signalがより安定。exit-regret `confidence_exit t0.4` hard selectorは有望なpre-registered candidateだが、deltaでは勝ちtrade削除とreplacement悪化が残る。00260で `replacement_stateful_net` targetと `conf_gap_extreme` replacement-risk candidateを追加。direction-side inversionは単独selector/direct penaltyでは標準化できない。 |

## 採用済みインフラ

- NoTrade-first candidate selector
- multi-window admission selector
- gate sensitivity / sparse-rank diagnostics
- validation inventory / full-rank window棚卸し
- quantile admission columns and stateful replay
- prior inversion / prior context risk score diagnostics
- executable EV calibration diagnostics
- component target decomposition
- component target calibration
- EV-overestimate risk selector diagnostics
- EV-overestimate context diagnostics
- EV-overestimate context calibration sweep
- EV-overestimate side-prior-pressure prediction input generation
- fixed-period common-entry/replacement path diagnostics
- common-entry and replacement loss target diagnostics
- direction-side inversion prediction-row input generation
- direction-side inversion selector/ranking diagnostics
- replacement-positive-quality prediction-row input generation
- direction-risk x low-replacement-quality combined stateful replay
- direction s0.1 residual loss diagnostics
- exit-shortening residual target diagnostics and chronological OOF calibration
- forced-exit-loss prediction-row input generation and stateful replay
- forced-exit hard selector input generation and stateful replay
- multi-family policy trade enrichment for validation diagnostics
- direction/exit residual target diagnostics
- fixed-period direction/exit residual stress diagnostics
- broad validation direction/exit residual diagnostics
- exit-regret risk prediction-row input generation
- exit-regret hard selector input generation
- entry-EV policy-run trade delta diagnostics
- entry-EV replacement-risk delta diagnostics

## 採用しないもの

- fixed testでだけ良い候補をvalidationへ流用すること
- single 2-month validationだけで候補を標準化すること
- raw EV / calibrated EV の絶対thresholdをそのまま標準policyにすること
- sparse high-rank candidateをsupport不足のまま採用すること
- same-validation inversion guard
- current prior inversion / prior risk hard block
- executable EV hard threshold
- dense executable capture scoreのdirect replacement
- generic side-balance direct penalty
- side-balance-only screen
- composite hard gate
- component targetを単一binary no-trade labelへ潰すこと
- EV-overestimate high-risk rowsのpointwise削除をstateful policy結果として扱うこと
- `side_drift_bucket` や `full_context` を小データのbucket keyへ直入れすること
- `side_prior_pressure_s0p5` のrelaxed validation near-missを標準policyにすること
- `side_prior_pressure_s0p5` のfixed 2025 path分解後に、同じwindowでpenalty strengthだけを再探索すること
- `common_failure_target` をそのまま単一binary training labelにすること
- 現定義の広い `exit_capture_failure_target` を単独headにすること
- `direction_inversion_bucket_s0p1` を標準policyにすること
- global fallback direction inversion riskをscore penaltyに直接使うこと
- direction inversion high-risk rowsのpointwise削除をstateful policy evidenceとして扱うこと
- 現行 `replacement_positive_quality_target` を標準headにすること
- direction risk x low replacement quality combined scoreを標準policyにすること
- `hold_too_long_loss_target` / `exit_shortening_residual_target` を現featureのままdirect policy scoreに入れること
- forced-exit riskを現penalty scoreのまま標準policyにすること
- global fallback forced-exit riskをdirect score penaltyに使うこと
- fixed 2025で見つけた `exitrisk_bucket_t0p10..t0p20` をそのまま標準policyへ昇格すること
- `ev_exit` selectorを総損益最大化のprimary policyとして使うこと
- validation forced-exit selectorの低閾値再探索を続けること
- `direction_or_exit_loss_target` のように実質realized lossへ潰れる広すぎるtargetをtraining labelにすること
- validation 77 rows / no-prior 0.74 のcalibrationをentry blockerへ直結すること
- fixed 2025 stressで見つけた `selected_loss_first_prob` をhard blockへ直結すること
- fixed stressのchronological bucket calibrationを標準policy evidenceとして扱うこと
- broad validationのexit-regret AUCだけでhard selectorを採用すること
- s1の取引数減少を利益edgeとして扱うこと
- soft `exit_regret_confexit_bucket_s0p5` penalty
- `exit_regret_selector_confidenceexit_bucket_t0p4` を追加holdoutなしで標準policyにすること
- exit-regret selectorをclean loss removerとして扱うこと
- only-candidate replacement悪化を未確認のまま採用すること
- replacement-riskのpointwise suppression estimateをstateful policy evidenceとして扱うこと
- `conf_gap_extreme` replacement guardをstateful replayなしで標準policyにすること

## 次にやること

1. `exit_regret_selector_confidenceexit_bucket_t0p4` に `conf_gap_extreme` replacement guardを加え、threshold `t0.4` は動かさずstateful replayする。
2. replay結果を00258/00259 candidate、s1 exposure baseline、NoTradeと比較する。
3. 改善する場合だけ、`conf_gap_extreme` をpre-registerして追加chronologyまたは別familyへ再探索なしに適用する。
4. 2025-03/09/11の悪化月を診断し、勝ちtrade削除を減らす条件を探す。ただし同じrowsで閾値再調整しない。
5. side concentrationが高いため、候補selectorにside share / role-month support gateを加える。

## 代表的な読む順

最新判断だけ確認する:

1. `00239_2026-06-30_entry_ev_composite_target_decomposition.md`
2. `00240_2026-07-01_entry_ev_component_target_calibration.md`
3. `00241_2026-07-01_entry_ev_overestimate_risk_selector.md`
4. `00242_2026-07-01_entry_ev_overestimate_context_diagnostics.md`
5. `00243_2026-07-01_entry_ev_context_calibration_sweep.md`
6. `00244_2026-07-01_entry_ev_side_prior_pressure_policy_inputs.md`
7. `00245_2026-07-01_entry_ev_side_prior_pressure_fixed2025_failure_diagnostics.md`
8. `00246_2026-07-01_entry_ev_common_loss_target_diagnostics.md`
9. `00247_2026-07-01_entry_ev_direction_inversion_policy_inputs.md`
10. `00248_2026-07-01_entry_ev_direction_inversion_selector_diagnostics.md`
11. `00249_2026-07-01_entry_ev_replacement_quality_policy_inputs.md`
12. `00250_2026-07-01_entry_ev_direction_s0p1_residual_loss_diagnostics.md`
13. `00251_2026-07-01_entry_ev_exit_shortening_target_diagnostics.md`
14. `00252_2026-07-02_entry_ev_forced_exit_policy_inputs.md`
15. `00253_2026-07-02_entry_ev_forced_exit_selector_inputs.md`
16. `00254_2026-07-02_entry_ev_forced_exit_validation_selector_check.md`
17. `00255_2026-07-02_entry_ev_direction_exit_residual_target_diagnostics.md`
18. `00256_2026-07-02_entry_ev_direction_exit_fixed2025_stress.md`
19. `00257_2026-07-02_entry_ev_direction_exit_broad_validation.md`
20. `00258_2026-07-02_entry_ev_exit_regret_selector_candidate.md`
21. `00259_2026-07-02_entry_ev_exit_regret_selector_delta.md`
22. `00260_2026-07-02_entry_ev_exit_regret_replacement_risk.md`

entry EV admissionの流れを見る:

1. `00208_2026-06-30_entry_ev_calibration_admission.md`
2. `00212_2026-06-30_entry_ev_multiwindow_admission_selector.md`
3. `00218_2026-06-30_entry_ev_scale_quantile_diagnostics.md`
4. `00220_2026-06-30_entry_ev_quantile_role_selector.md`
5. `00224_2026-06-30_entry_ev_quantile_hold_cap_sensitivity.md`

short budget / side driftの経緯を見る:

1. `00174_2026-06-29_holding_max_fresh_2025_09_12.md`
2. `00178_2026-06-29_side_drift_guard_admission_margin.md`
3. `00190_2026-06-30_context_entry_budget_zero.md`
4. `00196_2026-06-30_budget0_replacement_path_diagnostics.md`
5. `00207_2026-06-30_chrono_2024_full_protocol.md`
