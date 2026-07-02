# Report Map

最終更新: 2026-07-02 14:31 JST

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
| `00258`..`00298` | Exit-regret / replacement guard / executable EV insight | exit-regret selectorとreplacement guard replayが改善。ただしadmission gateではNoTrade。00263でpost-block side-gap quantile汚染を確認し、00264でpre-block quantileを実装。00265/00266で追加refit rowsとprior guardを分解し、00267でq99 prior guardをstateful replayへ接続。00268でfresh support不足はepisode集中であり、rank0緩和はcal/refitを壊すと確認。00269の外部HGB、00270の外部full-hybridでもNoTrade未満。00271で損失はno-edgeではなくexit-capture failure / executable EV過大評価に寄ると確認。00272でpost-selector executable scoreはNoTrade未満の負の対照。00273でselector前capture補正もNoTrade未満。00274でcoarse direction_regime tail-riskはq99をプラス化したが、support/side集中でNoTrade。00275で外部HGB再現は弱くdiagnosticへ降格。00276/00277でlow loss-first dynamic exitが全role positiveまで改善し、00278でdynamic exit cooldownが過剰回転を抑えた。00279でglobal expanding quantile化を試したがtail/role floorを壊し、raw cd15維持。00280でraw cd15残存損失はentry無価値ではなくexit-capture failure / EV過大評価が中心と確認。00281でprior capture factorのhard block/direct shrinkをreject。00282でselected-trade supervised shrinkageはscale補正として有効だが、低score gateでは勝ちtradeを削ると確認。00283でprediction-row shrinkage inputはacceptedだが、direct score replacementはmonth floorを壊すためreject。00284でdownside meta hard blockを試したが、実効thresholdは悪化、保守thresholdはno-op。00285でdownside soft risk marginもbaselineを大幅に下回りreject。00286でstateful floor selectorを追加し、現候補群はfloor-onlyでもNoTrade。00287でpost-exit pathを分解し、broad post-loss cooldownは勝ちを削ると確認。00288でisolated large-loss capture failureを特定し、一律fixed horizonはfloor悪化でreject。00289でhold-extension choice targetを学習し、`isolated_loss` training + `isolated_large_loss` threshold 5を次のfull replay候補にした。00290でstateful replayに接続し、total改善は維持したがmonth floor未達でNoTrade。00291でside-aware fixed 720m replayを追加し、long isolated large-lossのrecallは改善。00292でhybrid 2025-12 shortをentry-block overlayで消し、00293でrefit2025 2025-03/08 floorも縮めた。00294で残存floorはthin support中心と確認し、00295でsupport-aware admission診断へ分解。00296で候補系列横断では00293だけがdefault `support_aware_only` だが感度で落ちるため、標準policyはNoTrade。00297でmonth-warmupはreject。00298でconfidence hard gateも低活動化またはfloor悪化でreject。 |

## Current Clusters

| Cluster | Key reports | What to remember |
|---|---|---|
| Latest decision | `00258`..`00298` | q99 pre-block prior direction_regime guardはstateful replayで overall +55.6750 まで改善。ただしstrict/relaxed admissionはrole support不足でNoTrade。00274のcoarse `direction_regime` tail-riskは00275の外部HGB固定適用で再現せずdiagnosticへ降格。00278で q95 + raw `loss_exit30_cd15` が combined total +118.6900 / positive roles 6/6 / month min -6.8324 まで改善。00279のglobal quantile版はtotal改善と引き換えにtail/roleを壊すため、固定診断候補はraw cd15のまま。00280でloss trade 122件の大半が同方向oracle利益ありと分かり、00281でprior capture factorのhard block/direct shrinkはraw benchmarkを下回ると確認。00282でsupervised shrinkageはMAE/RMSEを改善したがrank/gateは弱い。00283でprediction-row inputへ戻したがscore replacementはtailを壊した。00284でdownside meta hard blockも `gte1` が +15.4886 へ悪化、`gte3` はno-op。00285のsoft risk marginもbest `w0.25` が +23.7938 でbaselineを大きく下回った。00286でcandidate-level stateful floor selectorを追加し、現候補群はfloor-onlyでもNoTrade。00287でpost-exit pathを分解し、`prev_loss` 後tradeは +122.9292 と強く、広いpost-loss cooldownはreject。00288でisolated large-loss capture failure 23件 / -125.5752を特定したが、一律fixed horizonはfloor悪化でreject。00289で `isolated_loss` training + `isolated_large_loss` threshold 5がno-replay total +246.7530 / month min -6.8324を示し、00290でstateful total +250.7350まで維持した。00291で `isolated_large_loss_long + fixed720 + threshold -5` がtotal +318.8540 / month min -4.1460まで改善。00292でshort rollover entry block overlayによりtotal +323.5700 / month min -2.4566へ改善。00293でresidual combo blockによりtotal +329.4348 / role min +0.5354 / month min -0.7200まで進んだ。00296の候補系列比較では00293だけがdefault `support_aware_only` だが、support2/shallow025ではblocked。00297のmonth-warmupは悪化。00298のconfidence gateは `taken_ev_ge10` がfloorを消すもののtotal +36.0280でsupport不足。他gateは悪化。標準policyはNoTrade。 |
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
Report: 00298 Entry EV Confidence Gate Overlay
Status: accepted infrastructure / diagnostic candidate remains NoTrade
Question: thin-support residual monthsをモデルconfidence hard gateで抑えられるか
Best evidence: taken_ev_ge10はmonth min 0.0だがtotal +36.0280 / support不足。他gateはfloor悪化
Decision: 標準policyはNoTrade
Next: direct hard gateはrejectし、chronological calibration / uncertainty診断へ回す
```
