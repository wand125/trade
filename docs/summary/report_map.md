# Report Map

最終更新: 2026-07-02 08:36 JST

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
| `00258`..`00275` | Exit-regret / replacement guard / executable EV insight | exit-regret selectorとreplacement guard replayが改善。ただしadmission gateではNoTrade。00263でpost-block side-gap quantile汚染を確認し、00264でpre-block quantileを実装。00265/00266で追加refit rowsとprior guardを分解し、00267でq99 prior guardをstateful replayへ接続。00268でfresh support不足はepisode集中であり、rank0緩和はcal/refitを壊すと確認。00269の外部HGB、00270の外部full-hybridでもNoTrade未満。00271で損失はno-edgeではなくexit-capture failure / executable EV過大評価に寄ると確認。00272でpost-selector executable scoreはNoTrade未満の負の対照。00273でselector前capture補正もNoTrade未満。00274でcoarse direction_regime tail-riskはq99をプラス化したが、support/side集中でNoTrade。00275で外部HGB再現は弱くdiagnosticへ降格。 |

## Current Clusters

| Cluster | Key reports | What to remember |
|---|---|---|
| Latest decision | `00258`..`00275` | q99 pre-block prior direction_regime guardはstateful replayで overall +55.6750 まで改善。ただしstrict/relaxed admissionはrole support不足でNoTrade。外部HGBと外部full-hybridでもNoTrade未満。00273でselector前capture補正もNoTrade未満。00274でcoarse `direction_regime` tail-riskはq99を同一foldでプラス化したが、00275の外部HGB固定適用ではbest `-9.1956` でNoTrade。tail-risk headはdiagnostic featureへ降格。 |
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
Report: 00275 Entry EV External HGB Side Regime Tail Check
Status: diagnostic branch / policy rejected
Question: 00274のcoarse side/regime tail-risk headは別chronologyの外部HGBでも再現するか
Best evidence: HGB 2025-08は +0.3800 の小幅改善だけで、overallは -9.1956、HGB 2024 lossを消せずNoTrade
Decision: 標準policyはNoTrade
Next: tail-risk gate追加探索を止め、exit timing / exit regret reductionへ戻す
```
