# Report Map

最終更新: 2026-07-02 20:12 JST

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
| `00258`..`00318` | Exit-regret / replacement guard / executable EV insight | exit-regret selectorとreplacement guard replayが改善。ただしadmission gateではNoTrade。00278で q95 + raw `loss_exit30_cd15` が combined total `+118.6900` / month min `-6.8324` まで改善。00307でshort entry-block replacementを未選択entry候補feedへ戻し、raw replacementは `+126.8118`。00308でreplacement pathへhold-extensionを統合し、require-model-used guardでfallback fixed720 tailを防いだ。00310でentry-time observableなposition-quality proxy `long_range_normal_ny_fixed60_pred_gt0` が total `+337.6010` / month min `-0.7200` まで改善したが、00311で非refit holdout発火0件と確認。00312でfixed60 false-positiveをprior-only uncertainty featureへ戻し、00313でuncertainty headのAP改善を確認したがdirect thresholdは勝ちtradeを削るためreject。00314でfixed60 uncertaintyをsoft marginへ戻し、family-aware w5がposition-quality overlay後 `+339.2910` / month min `-0.7200` までdiagnostic bestを更新。00315でtrade-set deltaを確認し、00314改善はrefit2025の少数removed tradeに集中、added 0 / common_changed 0 と判明。00316でfamily priorを粗いpriorへshrinkするとbest raw `+107.0324` まで落ち、current shrinkage policyはreject。00317でstandard admission repair targetを計算し、side/support修復に `8` extra tradesが必要と確認。00318で反対側near-miss候補を探し、one-fail strictなら8 targetを埋められるがfixed60/fixed240/fixed720が崩れるため、side-balanced support overlayはまだ標準候補にしない。標準policyはNoTrade。 |

## Current Clusters

| Cluster | Key reports | What to remember |
|---|---|---|
| Latest decision | `00258`..`00318` | q95 + raw `loss_exit30_cd15` dynamic exit cooldownを軸に、short entry-block replacement、require-model-used hold-extension、entry-time position-quality proxyへ進んだ。00314でfixed60 uncertainty soft marginのfamily-aware w5がdiagnostic bestを更新したが、00315のtrade-set deltaでは改善源がrefit2025の少数removed tradeに集中し、added 0 / common_changed 0 と確認。00317のrepair targetでは00314 w5のtotal改善がstandard-admission readinessを改善していないと確認した。00318ではone-fail strict候補でsupport数は埋まるが、fixed horizon実現が悪く、oracle bestとの差が大きい。次はnear-miss support candidate用exit timing / EV calibration target。標準policyはNoTrade。 |
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
Report: 00318 Entry EV Thin Month Opposite Candidates
Status: accepted infrastructure / standard NoTrade
Question: thin monthに反対側candidateを追加してside/support repair targetを埋められるか
Best evidence: one-fail strictなら8 targetすべてに候補はあるが、8本合計のfixed60は -17.7984、fixed240は -31.7138、fixed720は -80.4158。oracle bestだけは +86.0590。
Decision: 標準policyはNoTrade
Next: near-miss support candidate用のexit timing / EV calibration targetを作る
```
