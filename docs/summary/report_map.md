# Report Map

最終更新: 2026-07-02 01:35 JST

`docs/reports/` を個別に読む前のテーマ地図。番号はレポート本文の `日時:` 順に由来する。

## Phase Map

| Reports | テーマ | 圧縮した結論 |
|---|---|---|
| `00001`..`00012` | Foundation | dataset、backtest、multifold、cost stress、generalization原則を整備。分類指標ではなく実行PnLとNoTrade比較を中心にする方針へ移行。 |
| `00013`..`00031` | Static gates / candidate selection | regime/session block、direction/session gate、diagnostic gateはvalidationで良くてもblindで壊れやすい。hard gate乱立を避ける方針が固まる。 |
| `00032`..`00058` | Probability / side confidence / exit event | profit barrier、side confidence、exit eventは診断には有効。ただしglobal thresholdや単純penaltyは未知月で壊れる。 |
| `00059`..`00078` | MLP / side EV / quality | MLP exit hybrid、side EV penalty、selected trade qualityを実装。quality gateやdirect EV replacementは安定しない。 |
| `00079`..`00114` | Failure / candidate quality / side outcome | failure classifierやcandidate qualityはOOF指標改善だけでは実行PnLに変換されない。 |
| `00115`..`00143` | Stateful value / context stress | 一玉制約、blocking cost、context stressへ拡張。context hard ruleは過学習しやすく、feature/diagnosticへ戻す方針。 |
| `00144`..`00156` | EV overestimate / pred-hit miss | EV過大評価やpred-hit actual-missは失敗説明に効くが、raw thresholdはscale driftに弱い。 |
| `00157`..`00174` | Holding / exit / max hold | holding capは改善軸だが、fresh 2025-09..12ではside driftが主因で救えない。 |
| `00175`..`00207` | Side drift / short budget / 2024 chronology | short過剰、budget0、replacement path、same-family audit、full 2024 chronological protocolを検証。tailは縮むが標準採用なし。 |
| `00208`..`00224` | Entry EV admission | raw/calibrated EV、rank gate、quantile admission、positive floor、hold-cap sensitivityを検証。NoTrade-first selectorは通らない。 |
| `00225`..`00232` | Prior inversion / executable EV / dense capture | prior guard、risk score、exit capture target、executable EV calibration、stateful score、dense capture modelを検証。featureとして有用だが標準policyなし。 |
| `00233`..`00239` | Side balance / downside / composite | side balance、downside pressure、coverage、composite hard gateを検証。hard gateでは候補が生まれず、component targetへ分解。 |
| `00240`..`00257` | Component targets / EV overestimate / direction / replacement / exit | EV overestimateは相対的に残るが、fixed/broad residualではloss-first / exit-regret系signalがより安定。replacement qualityは弱い。forced-exit riskは標準化不可。multi-family enrichment、direction/exit residual target generation、fixed stress、broad validation診断はacceptedだが、まだpolicy化しない。 |

## Current Clusters

| Cluster | Key reports | What to remember |
|---|---|---|
| Latest decision | `00239`..`00257` | composite hard gateからcomponent targetへ分解。`side_prior_pressure_s0p5` はvalidation near-missだがfixed/broadで崩壊。direction inversion、replacement quality、forced-exit direct penaltyは標準化できない。forced-exit hard selectorもvalidationではbaselineを超えない。direction/exit residual targetは作れ、exit-regret系ではbroad validation signalが残るが、標準はNoTrade。 |
| Entry EV selector | `00208`, `00212`, `00213`, `00215`..`00221` | absolute EVはscale driftに弱い。quantile/rankは候補数を揃えるが、role/month floorを通らない。 |
| Exit capture | `00222`..`00232` | 260m capがbindingし、720mは診断上改善する。ただしdirection/context errorが混ざるためhold延長だけでは採用不可。 |
| Side balance | `00233`..`00238` | refitのlong過剰は縮むがfresh tailを悪化させる。side-balance単独ではなくdownside/context targetへ分解する。 |
| Short budget legacy | `00190`..`00207` | budget0は強いがsame-family / 2024 protocolで標準化できない。今後の比較baselineとして残す。 |
| Holding legacy | `00157`..`00174` | holding capは相対改善するが、fresh failureの主因はentry side drift。 |

## Reading Paths

現在の結論を最短で読む:

1. `docs/summary/current_assessment.md`
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

entry EV admissionを追う:

1. `00208_2026-06-30_entry_ev_calibration_admission.md`
2. `00209_2026-06-30_entry_ev_notrade_selector_fresh_fold.md`
3. `00210_2026-06-30_entry_ev_rank_gate_support_audit.md`
4. `00211_2026-06-30_entry_ev_rank_refit_2025_fold.md`
5. `00212_2026-06-30_entry_ev_multiwindow_admission_selector.md`
6. `00218_2026-06-30_entry_ev_scale_quantile_diagnostics.md`
7. `00220_2026-06-30_entry_ev_quantile_role_selector.md`

component targetへ至る流れを追う:

1. `00224_2026-06-30_entry_ev_quantile_hold_cap_sensitivity.md`
2. `00225_2026-06-30_entry_ev_quantile_prior_inversion_guard.md`
3. `00228_2026-06-30_entry_ev_exit_capture_target_diagnostics.md`
4. `00229_2026-06-30_entry_ev_executable_ev_calibration.md`
5. `00232_2026-06-30_entry_ev_dense_executable_capture_model.md`
6. `00238_2026-06-30_entry_ev_side_balance_downside_composite_selector.md`
7. `00239_2026-06-30_entry_ev_composite_target_decomposition.md`
8. `00253_2026-07-02_entry_ev_forced_exit_selector_inputs.md`
9. `00254_2026-07-02_entry_ev_forced_exit_validation_selector_check.md`
10. `00255_2026-07-02_entry_ev_direction_exit_residual_target_diagnostics.md`
11. `00256_2026-07-02_entry_ev_direction_exit_fixed2025_stress.md`
12. `00257_2026-07-02_entry_ev_direction_exit_broad_validation.md`

古い罠を確認する:

1. `00022` / `00026`: static side/session blockはblindで崩れる。
2. `00035`..`00056`: calibrationやexit penaltyのvalidation改善はholdoutへ外挿しない。
3. `00071`: validation候補は固定holdout同時監査で全滅。
4. `00163`..`00165`: holding-shortening raw/quantile thresholdはprobability scale driftに弱い。
5. `00183`..`00184`: cooldown/recoveryはhard block系を超えない。
6. `00211`..`00214`: sparse/high-rank fixed-positive rowはvalidation support不足かrepresentativeness不足。

## Status Terms

`standard policy`
: そのまま標準設定にしてよいもの。現時点では該当なし。

`accepted infrastructure`
: 今後も使う実装・診断・hook。selector、diagnostic、calibration、target generationなど。

`diagnostic baseline`
: 比較対象として残すが標準採用しないもの。short budget、p10+margin10、entry EV candidate familiesなど。

`candidate`
: 未使用windowへ再探索なし適用が必要なもの。

`rejected`
: 現条件では標準採用しないもの。

`superseded`
: 後続レポートでより良い診断・実装に置き換わったもの。

## Summary Card Template

```text
Report: 00257 Entry EV Direction Exit Broad Validation
Status: accepted broad diagnostic / not policy
Question: broad validationでもexit-regret/direction residual target signalは残るか
Best evidence: s0.5 confidence_exit -> same_side_large_regret pooled AUC 0.6919, s1 side_context -> same_side_large_regret 0.7008, but direction/profit-barrier miss remains weak
Decision: exit-regret auxiliary featureへ進める。hard blockにはしない
Next: prior-month exit-regret risk inputをprediction rowへ接続し、NoTrade-first selectorで評価する
```
