# Report Map

最終更新: 2026-07-03 14:12 JST

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
| `00258`..`00358` | Exit-regret / replacement guard / executable EV insight | exit-regret selectorとreplacement guard replayが改善。ただしadmission gateではNoTrade。00278で q95 + raw `loss_exit30_cd15` が combined total `+118.6900` / month min `-6.8324` まで改善。00307でshort entry-block replacementを未選択entry候補feedへ戻し、raw replacementは `+126.8118`。00308でreplacement pathへhold-extensionを統合し、require-model-used guardでfallback fixed720 tailを防いだ。00310でentry-time observableなposition-quality proxy `long_range_normal_ny_fixed60_pred_gt0` が total `+337.6010` / month min `-0.7200` まで改善したが、00311で非refit holdout発火0件と確認。00314でfixed60 uncertainty soft marginのfamily-aware w5がposition-quality overlay後 `+339.2910` / month min `-0.7200` までdiagnostic bestを更新。00317でstandard admission repair targetを計算し、side/support修復に `8` extra tradesが必要と確認。00318から00322で反対側near-missをexit target化し、広いcandidate universeのhorizon viabilityを試した。00323でsupport repairへ接続するとcombined `+362.7000` まで伸びたがstandard blockersが残る。00325 actual-floor upper-boundはcombined `+371.6610`。00326でrow x horizon化とhorizon penalty `0.25` を試すと、actual-floorなしでもfresh2024 2024-08を60mへ切り替え、combined `+374.6110` まで伸びた。00327でsupport-repair-only calibrationはprior不足で失敗。00329でbroad priorをhorizon-choice ranker featureへ入れ、低複雑度版はcombined `+403.2680` まで伸びた。00335でactual PnL tie-breaker leakを修正し、leak-free best combinedは `+400.1440` に下方修正。00339でthin-month候補面を見直し、fresh2024 2024-03はoracle positiveがあってもmodel-used 0、fresh2024 2024-11/refit2025 2025-03は候補生成不足と確認。00340でfresh03は240mだけが `+49.0950` で、exit timing / horizon confidence / EV calibrationが主弱点と確認。00341でmintrain1はfresh03を `-137.9060 -> -69.6140` へ改善するがtail-aware scoreは悪化。00342でtail support gateはfresh03の `pnl_delta_tail` を `-111.0260 -> -19.2310` へ改善するが、full replayは `+389.5310` でplain `pnl +400.1440` を超えない。00343でprior/OOB head reliabilityを追加するとreliability-gated scoreはplain `pnl` と同じcombined `+400.1440` だが、candidate-levelで2024-08/2025-07を悪化。00344で横断diagnosticsを作るとavailable candidatesでreliability-gated scoreはtarget subset `-131.8792`、all rows `-137.6916` 悪化。00345で `ranker_pred_pnl < 0` switch vetoを診断し、candidate-levelではreliability-gated悪化を回復。00346で同vetoをstateful replayへ戻すとbestはplain `pnl` と同じ5 trades / combined `+400.1440`、selector pass 0件で優位性なし。00347でpositive predicted PnL failureを診断し、market dedup 205件中124件が損失、合計 `-1104.5216` と確認。00348でpositive-PnL hard gateをstateful replayへ戻すと、`tail_prob_ge_0p30` はbest no-op、`positive_bias_and_tail_miss_ge_0p10` はbest combinedを `+400.1440 -> +393.2940` へ悪化。00349でpositive-PnL soft penaltyをstateful replayへ戻すと、`residual_bias_tail_miss` w0.05..0.25 と `tail_prob` w1/w2 はbest no-op、`tail_prob` w5はcombinedを `+399.8040` へ悪化。00350でover-gatingを分解し、`tail_prob_ge_0p30` はnear-best aggregateでselected winner damage 0のcleanなcontext risk signalだがbestでは発火0、harmful/residual/720m系はselected winnersを巻き込むと確認。00351でcontextual risk confidenceをmarket candidate dedupで検証し、defaultではconfident context 0、min4 sensitivityではwinner over-gating。00352でsupport countを追加し、`horizon,side` + support2 + positive-biasはcleanなdiagnostic signal、regime追加はsupport不足と確認。00353 hard gateは候補veto82 rows / `-1222.4120` を捕まえたが最終採用は不変。00354 soft penaltyは656 rows / `-9779.2960` をpenalizeしたが選択additionsとの交差0で不変。00355でpenalized rowsは全件 `tail_prob_ceiling` によるpre-filter rejectと確認。00356でtail ceilingは高tail大損領域を強く削るが、tail pass後のresidual global hard gateはwinner damageが大きいと確認。00357でactual selected additionsに絞るとtail pass positiveは8件 / `+59.0070`、lossは1件 / `-29.1360` のsingletonで、`pred_pnl_lt_2` はwin damage 0で拾う。00358で `singleton_720_pred_pnl_lt2` をstateful replayへ戻すと、scenario悪化0でknown singleton lossを止めたが、bestは既存no-gate EV2と同点でNoTrade-first admission未通過。scalar penalty / simple reranker / direct feature selector / singleton_any / global fallback緩和 / global early-support relaxation / tail-aware early score / train-support count gate / reliability direct multiplier / stateful pred-pnl negative switch veto / positive-PnL hard gate / positive-PnL soft penalty / global harmful/residual/720m gate / thin exact-context hard gate / coarse diagnostic-only positive-bias hard prefilter/soft penalty / tail-pass residual global hard gate / broad selected_tail_pass_pred_pnl_lt2 / unique 1件支持のsingleton標準化 / 240m固定ruleはreject。標準policyはNoTrade。 |

## Current Clusters

| Cluster | Key reports | What to remember |
|---|---|---|
| Latest decision | `00258`..`00358` | q95 + raw `loss_exit30_cd15` dynamic exit cooldownを軸に、short entry-block replacement、require-model-used hold-extension、entry-time position-quality proxyへ進んだ。00314でfixed60 uncertainty soft marginのfamily-aware w5がdiagnostic bestを更新したが、00315のtrade-set deltaでは改善源がrefit2025の少数removed tradeに集中し、added 0 / common_changed 0 と確認。00317のrepair targetでは00314 w5のtotal改善がstandard-admission readinessを改善していないと確認した。00318から00322でnear-miss support候補のexit timing / horizon viabilityを改善し、00323でstateful-compatible support repairへ接続したがstandard gateは未通過。00325ではtarget-aware repair utilityを接続し、actual-floor upper-boundならcombined `+371.6610` まで伸びた。00326ではrow x horizon化とhpen0.25でpred-onlyでもcombined `+374.6110` まで到達した。00329ではpriorをfeatureとしてchronological horizon-choice rankerへ入れ、低複雑度版がcombined `+403.2680` まで伸びた。00335でactual PnL tie-breaker leakを修正し、best combinedはleak-free `+400.1440` に下方修正。00339でthin-month候補面を診断し、fresh03はfallback/non-model calibration問題、fresh11/refit03は候補生成不足と確認。00340/00341でfresh03のhorizon confidence / tail calibration問題を確認。00342でtail support gateはfresh03局所を改善したがfull replayではplain PnLに負けた。00343/00344でprior/OOB reliabilityを検証し、direct score multiplierはtarget subset/all rowsの両方で悪化。00346 stateful pred-pnl negative vetoはplain `pnl` bestを改善せず、00347でpositive predicted PnL failureを診断するとmarket dedup positive pred 205件中124件が損失だった。00348でstateful hard gateへ戻すと、tail gateはbest no-op、positive-bias gateはbest悪化。00349でsoft penalty化してもbestはno-op、強いtail_prob penaltyは悪化。00350でover-gatingを分解し、tail probabilityはcontext-specific risk priorとして有用だがglobal gateではなく、harmful/residual系はwinner damageが大きいと確認。00351でcontext-specific abstention confidenceを試したが、market dedup後はdefault confident context 0、min4ではwinner over-gating。00352でsupport countを追加し、`horizon,side` + support2 + positive-biasをstateful replay候補にした。00353 hard gateと00354 soft penaltyはいずれも候補riskは検出するが最終採用は不変。00355でこれらのpenalized rowsは全件既存 `tail_prob_ceiling` に落とされていたと判明。00356でtail ceiling通過後の残存failureを見たが、global residual hard gateは勝ち候補削除が大きい。00357でactual selected lossは `fresh2024_validation 2024-08 long 720m` のsingletonに狭まり、00358で `singleton_720_pred_pnl_lt2` をstateful replayへ戻した。known lossは止まるが既存EV2 no-gate bestと同点で、admission blockersは残る。標準policyはNoTrade。 |
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
81. `00338_2026-07-03_entry_ev_support_repair_singleton_surface.md`
82. `00339_2026-07-03_entry_ev_support_repair_thin_month_candidates.md`
83. `00340_2026-07-03_entry_ev_support_repair_target_local_confidence.md`
84. `00341_2026-07-03_entry_ev_horizon_confidence_support_audit.md`
85. `00342_2026-07-03_entry_ev_tail_support_gated_horizon_choice.md`
86. `00343_2026-07-03_entry_ev_prior_oob_reliability_horizon_choice.md`
87. `00344_2026-07-03_entry_ev_horizon_reliability_diagnostics.md`
88. `00345_2026-07-03_entry_ev_horizon_reliability_abstention.md`
89. `00346_2026-07-03_entry_ev_stateful_reliability_abstention_replay.md`
90. `00347_2026-07-03_entry_ev_positive_pnl_failure_diagnostics.md`
91. `00348_2026-07-03_entry_ev_positive_pnl_gate_stateful_replay.md`
92. `00349_2026-07-03_entry_ev_positive_pnl_soft_penalty_replay.md`
93. `00350_2026-07-03_entry_ev_over_gating_context_diagnostics.md`
94. `00351_2026-07-03_entry_ev_contextual_risk_confidence_diagnostics.md`
95. `00352_2026-07-03_entry_ev_context_support_count_diagnostics.md`
96. `00353_2026-07-03_entry_ev_context_hs_support2_positive_pnl_gate_replay.md`
97. `00354_2026-07-03_entry_ev_contextual_positive_pnl_soft_penalty_replay.md`
98. `00355_2026-07-03_entry_ev_contextual_penalty_near_selected_diagnostics.md`
99. `00356_2026-07-03_entry_ev_tail_ceiling_residual_failure_diagnostics.md`
100. `00357_2026-07-03_entry_ev_tail_selected_residual_diagnostics.md`
101. `00358_2026-07-03_entry_ev_selected_tail_pred_pnl_gate_replay.md`

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
Report: 00358 Entry EV Selected Tail Pred PnL Gate Replay
Status: accepted infrastructure / standard NoTrade
Question: 00357のselected tail pred PnL guardをstateful replayへ戻すとstandard blockersは改善するか
Best evidence: `singleton_720_pred_pnl_lt2` はscenario改善96 / 悪化0、known singleton lossを止めるがbest combinedは既存no-gate EV2と同じ +400.1440、selector pass 0 / 288。
Decision: `singleton_720_pred_pnl_lt2` はdiagnostic candidateとして保持。broad `selected_tail_pass_pred_pnl_lt2` はscenario悪化32のためreject。標準policyはNoTrade
Next: known singletonではなくrole trade count / side share / shallow month floorを修復する候補生成へ戻る
```
