# Report Map

最終更新: 2026-07-03 08:39 JST

`docs/reports/` を個別に読む前の研究地図。番号はレポート本文の `日時:` 順に由来する。

## Phase Map

| Reports | テーマ | 圧縮した結論 |
|---|---|---|
| `00001`..`00012` | Foundation | dataset、backtest、multifold、cost stress、generalization原則を整備。評価軸を分類指標から実行PnL/NoTrade比較へ移した。 |
| `00013`..`00058` | Static gates / probability / exit | static gate、profit barrier、side confidence、exit eventは診断に有効だが、global thresholdや単純penaltyは未知月で壊れる。 |
| `00059`..`00114` | MLP / side EV / failure / quality | MLP、side EV、failure classifier、quality modelを整備。OOF指標改善だけでは実行PnLへ変換されない。 |
| `00115`..`00156` | Stateful / context / overestimate | 一玉制約、blocking cost、EV過大評価、pred-hit missへ展開。hard ruleよりfeature/diagnosticへ戻す流れが固まる。 |
| `00157`..`00174` | Holding / max hold | holding capは相対改善するが、fresh 2025-09..12ではside driftが主因で標準化できない。 |
| `00175`..`00207` | Side drift / short budget | budget0、replacement path、same-family audit、full 2024 protocolを検証。tailは縮むが標準採用なし。 |
| `00208`..`00224` | Entry EV admission | raw/calibrated EV、rank、quantile、positive floor、hold-cap sensitivityを検証。NoTrade-first selectorは通らない。 |
| `00225`..`00239` | Executable EV / side balance / composite | executable EV、dense capture、side balance、composite gateを検証。hard gateでは候補が生まれずcomponent targetへ分解。 |
| `00240`..`00257` | Component targets / direction-exit | EV overestimate、forced-exit、direction/exit residualを分解。fixed 2025で有望なsignalは出るがvalidation再現が不足。 |
| `00258`..`00337` | Exit-regret / replacement guard / executable EV insight | exit-regret selectorとreplacement guard replayが改善。ただしadmission gateではNoTrade。00278で q95 + raw `loss_exit30_cd15` が combined total `+118.6900` / month min `-6.8324` まで改善。00307でshort entry-block replacementを未選択entry候補feedへ戻し、raw replacementは `+126.8118`。00308でreplacement pathへhold-extensionを統合し、require-model-used guardでfallback fixed720 tailを防いだ。00310でentry-time observableなposition-quality proxy `long_range_normal_ny_fixed60_pred_gt0` が total `+337.6010` / month min `-0.7200` まで改善したが、00311で非refit holdout発火0件と確認。00314でfixed60 uncertainty soft marginのfamily-aware w5がposition-quality overlay後 `+339.2910` / month min `-0.7200` までdiagnostic bestを更新。00317でstandard admission repair targetを計算し、side/support修復に `8` extra tradesが必要と確認。00318から00322で反対側near-missをexit target化し、広いcandidate universeのhorizon viabilityを試した。00323でsupport repairへ接続するとcombined `+362.7000` まで伸びたがstandard blockersが残る。00325 actual-floor upper-boundはcombined `+371.6610`。00326でrow x horizon化とhorizon penalty `0.25` を試すと、actual-floorなしでもfresh2024 2024-08を60mへ切り替え、combined `+374.6110` まで伸びた。00327でsupport-repair-only calibrationはprior不足で失敗。00329でbroad priorをhorizon-choice ranker featureへ入れ、低複雑度版はcombined `+403.2680` まで伸びた。00335でactual PnL tie-breaker leakを修正し、leak-free best combinedは `+400.1440` に下方修正。00336でlistwise teacher化を診断したが、EV -2のfresh singleton negativeはreranking不能。00337でrisk-conditioned singleton abstentionはEV -2の `-29.1360` を弾けたが、best相当へ戻すだけでstandard blockersは残る。scalar penalty / simple switch rule / simple reranker / direct feature selector / singleton_anyはreject。標準policyはNoTrade。 |

## Current Clusters

| Cluster | Key reports | What to remember |
|---|---|---|
| Latest decision | `00258`..`00337` | q95 + raw `loss_exit30_cd15` dynamic exit cooldownを軸に、short entry-block replacement、require-model-used hold-extension、entry-time position-quality proxyへ進んだ。00314でfixed60 uncertainty soft marginのfamily-aware w5がdiagnostic bestを更新したが、00315のtrade-set deltaでは改善源がrefit2025の少数removed tradeに集中し、added 0 / common_changed 0 と確認。00317のrepair targetでは00314 w5のtotal改善がstandard-admission readinessを改善していないと確認した。00318から00322でnear-miss support候補のexit timing / horizon viabilityを改善し、00323でstateful-compatible support repairへ接続したがstandard gateは未通過。00325ではtarget-aware repair utilityを接続し、actual-floor upper-boundならcombined `+371.6610` まで伸びた。00326ではrow x horizon化とhpen0.25でpred-onlyでもcombined `+374.6110` まで到達した。00329ではpriorをfeatureとしてchronological horizon-choice rankerへ入れ、低複雑度版がcombined `+403.2680` まで伸びた。00335でactual PnL tie-breaker leakを修正し、best combinedはleak-free `+400.1440` に下方修正。00336でteacher化したが、baseline bestのoracle改善は `+5.7600` だけで、EV -2の悪いfresh唯一候補はsingleton negativeのためreranking不能。00337でrisk-conditioned abstentionはこのsingletonを弾けたが、best相当へ戻すだけでstandard blockersは残る。標準policyはNoTrade。次は条件付きabstentionを広いsingleton面で検証し、fresh/thin month候補生成へ進む。 |
| Entry EV selector | `00208`..`00221` | 絶対EVはscale driftに弱く、quantile/rankもrole/month floorを通らない。 |
| Exit capture | `00222`..`00232` | 720mやexecutable EVは診断上改善するが、direction/context errorが残る。 |
| Side balance | `00233`..`00239` | side-balance単独では不安定。component targetへ分解。 |
| Short budget legacy | `00190`..`00207` | budget0は強いが標準化できない。比較baselineとして残す。 |

## Reading Paths

最新判断を読む:

1. `00258_2026-07-02_entry_ev_exit_regret_selector_candidate.md`
2. `00259_2026-07-02_entry_ev_exit_regret_selector_delta.md`
3. `00260_2026-07-02_entry_ev_exit_regret_replacement_risk.md`
4. `00261_2026-07-02_entry_ev_exit_regret_replacement_guard_replay.md`
5. `00262_2026-07-02_entry_ev_exit_regret_replacement_guard_admission.md`
6. `00263_2026-07-02_entry_ev_quantile_candidate_support_diagnostics.md`
7. `00264_2026-07-02_entry_ev_preblock_side_gap_quantile.md`
8. `00265_2026-07-02_entry_ev_preblock_delta_context_diagnostics.md`
9. `00266_2026-07-02_entry_ev_preblock_prior_context_guard.md`
10. `00267_2026-07-02_entry_ev_preblock_prior_guard_stateful_replay.md`
11. `00268_2026-07-02_entry_ev_fresh_support_episode_diagnostics.md`
12. `00269_2026-07-02_entry_ev_external_hgb_prior_guard_replay.md`
13. `00270_2026-07-02_entry_ev_external_hybrid_2025_09_12_replay.md`
14. `00271_2026-07-02_entry_ev_external_hybrid_loss_target_insight.md`
15. `00272_2026-07-02_entry_ev_external_hybrid_executable_ev_preflight.md`
16. `00273_2026-07-02_entry_ev_external_hybrid_base_executable_selector.md`
17. `00274_2026-07-02_entry_ev_external_hybrid_side_regime_tail_risk.md`
18. `00275_2026-07-02_entry_ev_external_hgb_side_regime_tail_check.md`
19. `00276_2026-07-02_entry_ev_exit_timing_loss_exit_threshold.md`
20. `00277_2026-07-02_entry_ev_loss_exit30_fixed_internal_chronology.md`
21. `00278_2026-07-02_entry_ev_loss_exit30_dynamic_exit_cooldown.md`
22. `00279_2026-07-02_entry_ev_loss_first_global_expanding_quantile.md`
23. `00280_2026-07-02_entry_ev_raw_cd15_residual_loss_diagnostics.md`
24. `00281_2026-07-02_entry_ev_capture_shrink_overlay.md`
25. `00282_2026-07-02_entry_ev_selected_trade_supervised_shrinkage.md`
26. `00283_2026-07-02_entry_ev_supervised_shrinkage_policy_inputs.md`
27. `00284_2026-07-02_entry_ev_downside_meta_block_inputs.md`
28. `00285_2026-07-02_entry_ev_downside_meta_risk_margin.md`
29. `00286_2026-07-02_entry_ev_stateful_floor_meta_selector.md`
30. `00287_2026-07-02_entry_ev_post_exit_path_diagnostics.md`
31. `00288_2026-07-02_entry_ev_isolated_exit_capture_diagnostics.md`
32. `00289_2026-07-02_entry_ev_hold_extension_target_model.md`
33. `00290_2026-07-02_entry_ev_hold_extension_stateful_replay.md`
34. `00291_2026-07-02_entry_ev_hold_extension_side_horizon_replay.md`
35. `00292_2026-07-02_entry_ev_stateful_entry_block_overlay.md`
36. `00293_2026-07-02_entry_ev_residual_floor_combo_overlay.md`
37. `00294_2026-07-02_entry_ev_overlay_residual_floor_diagnostics.md`
38. `00295_2026-07-02_entry_ev_support_aware_admission.md`
39. `00296_2026-07-02_entry_ev_support_aware_progression_compare.md`
40. `00297_2026-07-02_entry_ev_month_warmup_overlay.md`
41. `00298_2026-07-02_entry_ev_confidence_gate_overlay.md`
42. `00299_2026-07-02_entry_ev_residual_combo_selected_trade_calibration.md`
43. `00300_2026-07-02_entry_ev_calibration_residual_context_diagnostics.md`
44. `00301_2026-07-02_entry_ev_prior_residual_pressure.md`
45. `00302_2026-07-02_entry_ev_prior_pressure_large_loss_head.md`
46. `00303_2026-07-02_entry_ev_path_compensation_diagnostics.md`
47. `00304_2026-07-02_entry_ev_uncompensated_loss_head.md`
48. `00305_2026-07-02_entry_ev_uncompensated_sequence_state.md`
49. `00306_2026-07-02_entry_ev_uncompensated_candidate_path.md`
50. `00307_2026-07-02_entry_ev_short_entryblock_replacement_replay.md`
51. `00308_2026-07-02_entry_ev_replacement_hold_extension_integration.md`
52. `00309_2026-07-02_entry_ev_hold_extension_veto_diagnostics.md`
53. `00310_2026-07-02_entry_ev_position_quality_proxy_overlay.md`
54. `00311_2026-07-02_entry_ev_position_quality_holdout_support.md`
55. `00312_2026-07-02_entry_ev_fixed60_prior_uncertainty.md`
56. `00313_2026-07-02_entry_ev_fixed60_prior_uncertainty_head.md`
57. `00314_2026-07-02_entry_ev_fixed60_uncertainty_soft_margin.md`
58. `00315_2026-07-02_entry_ev_fixed60_margin_trade_set_delta.md`
59. `00316_2026-07-02_entry_ev_fixed60_margin_prior_shrinkage.md`
60. `00317_2026-07-02_entry_ev_admission_repair_targets.md`
61. `00318_2026-07-02_entry_ev_thin_month_opposite_candidates.md`
62. `00319_2026-07-02_entry_ev_near_miss_exit_target.md`
63. `00320_2026-07-02_entry_ev_near_miss_exit_head.md`
64. `00321_2026-07-02_entry_ev_near_miss_horizon_viability.md`
65. `00322_2026-07-02_entry_ev_broad_horizon_viability.md`
66. `00323_2026-07-02_entry_ev_support_repair_horizon_replay.md`
67. `00324_2026-07-03_entry_ev_support_repair_target_coverage.md`
68. `00325_2026-07-03_entry_ev_target_aware_support_repair_replay.md`
69. `00326_2026-07-03_entry_ev_row_horizon_support_repair.md`
70. `00327_2026-07-03_entry_ev_horizon_duration_penalty_calibration.md`
71. `00328_2026-07-03_entry_ev_broad_duration_prior_repair_replay.md`
72. `00329_2026-07-03_entry_ev_broad_prior_horizon_choice_ranker.md`
73. `00330_2026-07-03_entry_ev_horizon_choice_lower_bound.md`
74. `00331_2026-07-03_entry_ev_harmful_overestimate_target.md`
75. `00332_2026-07-03_entry_ev_support_aware_harmful_objective.md`
76. `00333_2026-07-03_entry_ev_support_repair_pairwise_switch.md`
77. `00334_2026-07-03_entry_ev_support_repair_listwise_cluster.md`
78. `00335_2026-07-03_entry_ev_support_repair_leakfree_tiebreak.md`
79. `00336_2026-07-03_entry_ev_support_repair_listwise_teacher.md`
80. `00337_2026-07-03_entry_ev_support_repair_singleton_abstention.md`

component targetの流れを読む:

1. `00239_2026-06-30_entry_ev_composite_target_decomposition.md`
2. `00240_2026-07-01_entry_ev_component_target_calibration.md`
3. `00241_2026-07-01_entry_ev_overestimate_risk_selector.md`
4. `00242_2026-07-01_entry_ev_overestimate_context_diagnostics.md`
5. `00253_2026-07-02_entry_ev_forced_exit_selector_inputs.md`
6. `00257_2026-07-02_entry_ev_direction_exit_broad_validation.md`

entry admissionの流れを読む:

1. `00208_2026-06-30_entry_ev_calibration_admission.md`
2. `00212_2026-06-30_entry_ev_multiwindow_admission_selector.md`
3. `00218_2026-06-30_entry_ev_scale_quantile_diagnostics.md`
4. `00220_2026-06-30_entry_ev_quantile_role_selector.md`
5. `00224_2026-06-30_entry_ev_quantile_hold_cap_sensitivity.md`

古い罠を確認する:

1. `00022` / `00026`: static side/session blockはblindで崩れる。
2. `00035`..`00056`: calibrationやexit penaltyのvalidation改善はholdoutへ外挿しない。
3. `00071`: validation候補は固定holdout同時監査で全滅。
4. `00163`..`00165`: holding-shortening thresholdはprobability scale driftに弱い。
5. `00211`..`00214`: sparse high-rank positive rowはsupport/representativeness不足。

## Status Terms

`standard policy`
: そのまま標準設定にしてよいもの。現時点では該当なし。

`accepted infrastructure`
: 今後も使う実装・診断・hook。

`diagnostic baseline`
: 比較対象として残すが標準採用しないもの。

`candidate`
: 未使用windowへ再探索なし適用が必要なもの。

`rejected`
: 現条件では標準採用しないもの。

## Summary Card Template

```text
Report: 00337 Entry EV Support Repair Singleton Abstention
Status: accepted infrastructure / standard NoTrade
Question: singleton negativeをobservable abstentionで事前に弾けるか
Best evidence: EV -2のfresh2024 2024-08 long -29.1360はprior mean/tail/riskやpred_pnlで弾け、combined +371.0080 -> +400.1440。ただしbest相当へ戻るだけでstandard blockersは残る。
Decision: 標準policyはNoTrade
Next: risk-conditioned abstentionを広いsingleton面で検証し、fresh/thin month候補生成を追加
```
