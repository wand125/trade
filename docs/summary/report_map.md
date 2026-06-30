# Report Map

最終更新: 2026-06-30 18:00 JST

`docs/reports/` を個別に読む前のテーマ地図。番号はレポート本文の `日時:` 順に由来する。

## 全体の流れ

| Reports | テーマ | 圧縮した結論 |
|---|---|---|
| `00001`..`00004` | baseline / dataset / initial model / executable policy | backtestとdatasetの土台を作成。分類指標だけでは実行PnLを説明できず、loss multiplier下では勝率より損失尾部が重要。 |
| `00005`..`00012` | multifold selection / regime-cost controls / generalization principles | 単月最適化を避けるため、複数fold、cost stress、purge/embargo、NoTrade比較を標準化。 |
| `00013`..`00031` | regime gate / short exposure / candidate gate | static regime/session blockやcandidate gateは、validationで良くてもblind月で壊れやすい。診断列は有用だがhard採用は危険。 |
| `00032`..`00058` | profit barrier / side confidence / exit event / holding shrink | profit-barrier確率、side-confidence、exit-event確率は診断には有効。ただしglobal hard gateや単純penaltyは未知月で壊れる。 |
| `00059`..`00078` | MLP hybrid / group loss / side EV penalty / selected trade quality | MLP exit hybridやside EV penaltyなどの実装基盤を追加。quality gateやEV replacementは安定せず、failure classifierは直接policy化には弱い。 |
| `00079`..`00114` | failure probability / candidate quality / side outcome stacking | trade failureやcandidate qualityをOOFで学習。AUCや校正改善だけでは実行PnL改善に直結しないことを確認。 |
| `00115`..`00143` | stateful value / blocking / context stress | 一玉制約とblocking costを扱う方向へ拡張。stateful系は価値があるが、context hard ruleは過学習しやすい。 |
| `00144`..`00156` | EV overestimate / pred-hit actual-miss / fixed checks | EV過大評価とpred-hit actual-missは失敗説明に効くが、raw thresholdや単月fixed checkではスケール差に弱い。 |
| `00157`..`00174` | holding overlay / holding shortening / max hold cap | holding capは強い改善軸だが、fresh 2025-09..12ではside driftが主因で救えない。`250..260m`は感度候補止まり。 |
| `00175`..`00179` | side drift diagnostics and guard | fresh failureはshort過剰選択。side drift guard + admission marginは損失を縮めるが、replacement shortが残る。 |
| `00180`..`00185` | online context drawdown/state | realized PnLだけを使うonline guardとstate診断を追加。hard block/worst objectiveはtail制御に有効だがprofit policyではない。 |
| `00186`..`00230` | short-specific interaction / entry budget / side calibration / chronological 2024 OOF / entry EV admission selector | short raw gapは介入箇所を示す。`budget0` とprior realized/context-alert composite triggerによりtailは大きく縮んだが、prediction/alert単独triggerは上積みできない。alert context限定budget/admission/first-lossは狭すぎる。00196..00230で、global budget0との差、`gap5` replacement short、prior signal coverage、entry-level residual signal、dynamic hook、replacement risk target、triggered profit-miss hook、same-family fixed check、side calibration、早期2024 risk列生成、全2024同一chronological protocol、entry EV calibration/admission、NoTrade-first selector、rank gate support、追加2025-refit fold、multi-window selector、gate sensitivity、sparse rank診断、validation inventory、cal2024 rank window、entry EV admission入力診断、scale quantile診断、quantile policy backtest、role selector、positive EV floor、trade context診断、exit capture診断、hold-cap sensitivity、prior-only inversion guard、prior context risk score、residual losing month診断、exit-capture target診断、executable EV calibration、executable EV selector featureを分解した。rank-gated admissionは2024 fresh validationではsupport不足、2025 refitではsupport gate通過後にtest崩壊、multi-window relaxed selectionもfixed testsで崩壊したため標準採用しない。cal2024はprediction入力側ではside margin supportがほぼなく、refit2025はlong EV scaleが大きすぎる。00218でside/regime/session-local quantileが候補数を比較可能にする軸だと確認し、00219でstateful backtestへ接続したが、fresh/refit validationのworstが負。00220のrole selectorでもstrict3/clean2ともNoTrade。00221のEV floor候補も全てNoTrade。00222で失敗はentry floorだけでなくcontext-side inversionとexit captureに分かれると確認し、00223でq95/q99は `260m` capがbindingしているがdirection/context errorも残るためblind hold延長は不可とした。00224で `720m` capは有望だが、same-validation guard込みでもmonth floorを通らないため標準はNoTrade。00225でprior-only guardへ置き換えてもvalidationは近似pass止まり、fresh fixedではover-blockingが出た。00226でrisk score化しcal+fresh prior fixedは改善したが、月次floor未達。00227で残差月はentry floor不足ではなくdirection-side inversion、exit capture、realized EV calibration不足だと確認した。00228でexit-capture targetは有用だがprior risk hard blockはfresh fixed利益を削ると確認した。00229でexecutable EV calibrationは有用だがhard thresholdは不安定と確認し、00230でcandidate-level selector featureでもNoTrade-first gateを超えないと確認した。 |

## テーマ別読む順

### 現在の失敗原因を知る

1. `00174_2026-06-29_holding_max_fresh_2025_09_12.md`
2. `00175_2026-06-29_side_drift_diagnostics.md`
3. `00179_2026-06-29_side_drift_guard_residual_diagnostics.md`
4. `00190_2026-06-30_context_entry_budget_zero.md`
5. `00191_2026-06-30_short_budget_drift_trigger.md`
6. `00192_2026-06-30_prediction_side_drift_trigger.md`
7. `00193_2026-06-30_context_alert_budget_trigger.md`
8. `00194_2026-06-30_alert_context_budget_admission.md`
9. `00195_2026-06-30_alert_context_first_loss_cap.md`
10. `00196_2026-06-30_budget0_replacement_path_diagnostics.md`
11. `00197_2026-06-30_fixed_short_budget_trigger_audit.md`
12. `00198_2026-06-30_replacement_prior_signal_audit.md`
13. `00199_2026-06-30_entry_signal_residual_context_audit.md`
14. `00200_2026-06-30_focus_entry_dynamic_hook.md`
15. `00201_2026-06-30_replacement_risk_target_diagnostics.md`
16. `00202_2026-06-30_triggered_replacement_risk_hook.md`
17. `00203_2026-06-30_triggered_profit_miss_samefamily_check.md`
18. `00204_2026-06-30_gap5_budget_samefamily_extension.md`
19. `00205_2026-06-30_samefamily_side_calibration_diagnostics.md`
20. `00206_2026-06-30_early2024_chrono_risk_oof.md`
21. `00207_2026-06-30_chrono_2024_full_protocol.md`
22. `00208_2026-06-30_entry_ev_calibration_admission.md`
23. `00209_2026-06-30_entry_ev_notrade_selector_fresh_fold.md`
24. `00210_2026-06-30_entry_ev_rank_gate_support_audit.md`
25. `00211_2026-06-30_entry_ev_rank_refit_2025_fold.md`
26. `00212_2026-06-30_entry_ev_multiwindow_admission_selector.md`
27. `00213_2026-06-30_entry_ev_gate_sensitivity.md`
28. `00214_2026-06-30_entry_ev_sparse_rank_diagnostics.md`
29. `00215_2026-06-30_entry_ev_validation_inventory.md`
30. `00216_2026-06-30_entry_ev_cal2024_rank_window.md`
31. `00217_2026-06-30_entry_ev_admission_input_diagnostics.md`
32. `00218_2026-06-30_entry_ev_scale_quantile_diagnostics.md`
33. `00219_2026-06-30_entry_ev_quantile_policy_backtest.md`
34. `00220_2026-06-30_entry_ev_quantile_role_selector.md`
35. `00221_2026-06-30_entry_ev_quantile_positive_floor.md`
36. `00222_2026-06-30_entry_ev_quantile_trade_context_diagnostics.md`
37. `00223_2026-06-30_entry_ev_quantile_exit_capture_diagnostics.md`
38. `00224_2026-06-30_entry_ev_quantile_hold_cap_sensitivity.md`
39. `00225_2026-06-30_entry_ev_quantile_prior_inversion_guard.md`
40. `00226_2026-06-30_entry_ev_prior_context_risk_score.md`
41. `00227_2026-06-30_entry_ev_residual_2024_03_loss_diagnostics.md`
42. `00228_2026-06-30_entry_ev_exit_capture_target_diagnostics.md`
43. `00229_2026-06-30_entry_ev_executable_ev_calibration.md`
44. `00230_2026-06-30_entry_ev_executable_ev_selector_feature.md`

### 現在の候補軸を知る

1. `00178_2026-06-29_side_drift_guard_admission_margin.md`
2. `00182_2026-06-30_context_drawdown_guard_margin_sweep.md`
3. `00188_2026-06-30_short_entry_budget_guard.md`
4. `00190_2026-06-30_context_entry_budget_zero.md`
5. `00191_2026-06-30_short_budget_drift_trigger.md`
6. `00192_2026-06-30_prediction_side_drift_trigger.md`
7. `00193_2026-06-30_context_alert_budget_trigger.md`
8. `00194_2026-06-30_alert_context_budget_admission.md`
9. `00195_2026-06-30_alert_context_first_loss_cap.md`
10. `00196_2026-06-30_budget0_replacement_path_diagnostics.md`
11. `00197_2026-06-30_fixed_short_budget_trigger_audit.md`
12. `00198_2026-06-30_replacement_prior_signal_audit.md`
13. `00199_2026-06-30_entry_signal_residual_context_audit.md`
14. `00200_2026-06-30_focus_entry_dynamic_hook.md`
15. `00201_2026-06-30_replacement_risk_target_diagnostics.md`
16. `00202_2026-06-30_triggered_replacement_risk_hook.md`
17. `00203_2026-06-30_triggered_profit_miss_samefamily_check.md`
18. `00204_2026-06-30_gap5_budget_samefamily_extension.md`
19. `00205_2026-06-30_samefamily_side_calibration_diagnostics.md`
20. `00206_2026-06-30_early2024_chrono_risk_oof.md`
21. `00207_2026-06-30_chrono_2024_full_protocol.md`
22. `00208_2026-06-30_entry_ev_calibration_admission.md`
23. `00209_2026-06-30_entry_ev_notrade_selector_fresh_fold.md`
24. `00210_2026-06-30_entry_ev_rank_gate_support_audit.md`
25. `00211_2026-06-30_entry_ev_rank_refit_2025_fold.md`
26. `00212_2026-06-30_entry_ev_multiwindow_admission_selector.md`
27. `00213_2026-06-30_entry_ev_gate_sensitivity.md`
28. `00214_2026-06-30_entry_ev_sparse_rank_diagnostics.md`
29. `00215_2026-06-30_entry_ev_validation_inventory.md`
30. `00216_2026-06-30_entry_ev_cal2024_rank_window.md`
31. `00217_2026-06-30_entry_ev_admission_input_diagnostics.md`
32. `00218_2026-06-30_entry_ev_scale_quantile_diagnostics.md`
33. `00219_2026-06-30_entry_ev_quantile_policy_backtest.md`
34. `00220_2026-06-30_entry_ev_quantile_role_selector.md`
35. `00221_2026-06-30_entry_ev_quantile_positive_floor.md`
36. `00222_2026-06-30_entry_ev_quantile_trade_context_diagnostics.md`
37. `00223_2026-06-30_entry_ev_quantile_exit_capture_diagnostics.md`
38. `00224_2026-06-30_entry_ev_quantile_hold_cap_sensitivity.md`
39. `00225_2026-06-30_entry_ev_quantile_prior_inversion_guard.md`
40. `00226_2026-06-30_entry_ev_prior_context_risk_score.md`
41. `00227_2026-06-30_entry_ev_residual_2024_03_loss_diagnostics.md`
42. `00228_2026-06-30_entry_ev_exit_capture_target_diagnostics.md`
43. `00229_2026-06-30_entry_ev_executable_ev_calibration.md`
44. `00230_2026-06-30_entry_ev_executable_ev_selector_feature.md`

### holding / exit 系の経緯を知る

1. `00039_2026-06-28_exit_event_timing_targets.md`
2. `00041_2026-06-28_holding_cap_sweep.md`
3. `00160_2026-06-29_dense_holding_shortening_targets.md`
4. `00170_2026-06-29_exit_shortening_failure_policy.md`
5. `00171_2026-06-29_exit_shortening_fixed_apply_2025_06_08.md`
6. `00172_2026-06-29_holding_max_cap_fullpred_apply_2025_06_08.md`
7. `00173_2026-06-29_holding_max_grid_2025_01_08.md`
8. `00174_2026-06-29_holding_max_fresh_2025_09_12.md`
9. `00224_2026-06-30_entry_ev_quantile_hold_cap_sensitivity.md`
10. `00225_2026-06-30_entry_ev_quantile_prior_inversion_guard.md`
11. `00226_2026-06-30_entry_ev_prior_context_risk_score.md`
12. `00227_2026-06-30_entry_ev_residual_2024_03_loss_diagnostics.md`
13. `00228_2026-06-30_entry_ev_exit_capture_target_diagnostics.md`
14. `00229_2026-06-30_entry_ev_executable_ev_calibration.md`
15. `00230_2026-06-30_entry_ev_executable_ev_selector_feature.md`

### 過去に棄却した罠を確認する

1. `00022` / `00026`: side-specific regime suppression は別blind月で崩れた。
2. `00035`..`00056`: probability calibrationやexit penaltyは、validation改善がholdoutへ外挿しなかった。
3. `00071`: validation候補は固定holdout同時監査で全滅。
4. `00163`..`00165`: holding-shortening raw/quantile thresholdはprobability scale driftに弱い。
5. `00183`..`00184`: cooldown/recoveryはhard block系を超えなかった。

## 判断語彙

`standard policy`
: そのまま標準設定にしてよいもの。現時点では該当なし。

`accepted infrastructure`
: 今後も使う実装・診断・hook。backtest、OOF、trade delta、side drift diagnostics、entry budget hookなど。

`diagnostic baseline`
: 比較対象として残すが標準採用しないもの。`p10 + margin10`、context drawdown `worst` objective、short budget `defensive_budget`など。

`candidate`
: 未使用月への再探索なし適用が必要なもの。

`rejected`
: 検証済みで、現条件では標準採用しないもの。

`superseded`
: 後続レポートでより良い診断・実装に置き換わったもの。

## レポート要約カードの型

今後、重要レポートをsummaryへ追加するときはこの形式で1つずつ圧縮する。

```text
Report: 00190 Context Entry Budget Zero
Status: diagnostic baseline / not standard
Question: active short contextをbudget0で完全stay-flat化するとprior-onlyで改善するか
Best evidence: defensive_budget min4 total +232.2466, worst -46.0150; min8 total -15.0104, worst -45.4774
Decision: hookとselectorは残す。標準採用しない
Next: gap0/budget0固定、prior side-drift detector、low-trade residual rule
```

```text
Report: 00191 Short Budget Drift Trigger
Status: diagnostic baseline / not standard
Question: prior recent deteriorationだけでgap5/budget0からgap0/budget0へ切り替えられるか
Best evidence: min4 total +232.2466, worst -46.0150; min8 total -15.0104, worst -45.4774
Decision: trigger scriptは残す。00190を上回らないため標準採用しない
Next: prediction-share / label-share side drift featuresをtriggerに追加
```

```text
Report: 00192 Prediction Side Drift Trigger
Status: diagnostic only / not standard
Question: 月次prediction side driftでrealized PnL悪化前にbudget0へ落とせるか
Best evidence: best label-share trigger min4 total +210.3068; realized trigger 00191 is +232.2466; min8 remains -15.0104
Decision: optional metricsは残すが月次prediction-share triggerは採用しない
Next: context/session-level drift alert or prediction-drift AND realized first-loss trigger
```

```text
Report: 00193 Context Alert Budget Trigger
Status: diagnostic only / not standard
Question: context/session side drift alertでglobal budget0発火を改善できるか
Best evidence: alert-only over-triggers to +150.3206; alert AND short losing month matches 00191 at +232.2466; min8 remains -15.0104
Decision: global context-alert triggerは採用しない
Next: apply budget/admission only to alert contexts, not entire months
```

```text
Report: 00194 Alert Context Budget Admission
Status: diagnostic infrastructure / not standard
Question: prior side-drift alert contextだけにbudget0や追加entry marginを掛けるとglobal month switchより堅牢になるか
Best evidence: alert-context budget0 improves baseline -90.1378 to +6.0170, but prior-only min4 best is -316.4554 and min8 best is -542.9034
Decision: hookは残すが標準採用しない
Next: context-specific first-loss cap was tested in 00195; then move to non-alert short exposure
```

```text
Report: 00195 Alert Context First Loss Cap
Status: diagnostic only / not standard
Question: prior side-drift alert context内でrealized loss後だけ止めればbudget0より堅牢になるか
Best evidence: all-window best threshold5 improves baseline -90.1378 to -71.8598, but alert-context budget0 is +6.0170; prior-only min4 is -396.3152 and min8 is -609.1884
Decision: alert-context first-loss / fast-stopは採用しない
Next: non-alert short exposure and replacement-path diagnostics after budget0
```

```text
Report: 00196 Budget0 Replacement Path Diagnostics
Status: diagnostic preflight / not standard
Question: alert context budget0がglobal gap0/gap5 budget0に届かない理由は何か
Best evidence: late alert-context budget0 removes base short -333.9178 but leaves common short -382.7524 and replacement short -293.7604; global gap0 removes late base short -716.6702 and admits only -38.6214 replacement short
Decision: alert-context-only gateを本流として増やさない。gap0 is defensive baseline; gap5 needs deterioration trigger
Next: fixed fresh verification of gap0, gap5, and gap5 -> gap0 trigger without re-search
```

```text
Report: 00197 Fixed Short Budget Trigger Audit
Status: diagnostic candidate / not standard
Question: 固定済みgap5/budget0 -> gap0/budget0 triggerは再探索なしで有効か。またgap5 late replacement shortはどこに集中するか
Best evidence: fixed trigger min4 total +232.2466, min6 +26.3116, min8 -15.0104; late replacement short gap5 67 trades -286.9878 vs gap0 16 trades -38.6214
Decision: scriptはaccepted infrastructure。fixed triggerはpreflight止まりで標準採用しない
Next: additional unseen months or 2024 same-family fixed apply; detect up_low_vol/ny_overlap and range_low_vol replacement risk with prior-only signals
```

```text
Report: 00198 Replacement Prior Signal Audit
Status: diagnostic preflight / not standard
Question: gap5 replacement shortはtarget月前のcontext signalで検知できるか
Best evidence: gap5 late replacement -286.9878; prior alert covers -133.9066; prior alert OR pred-bias covers -192.4296 but leaves -94.5582, mainly range_low_vol/ny_overlap
Decision: prior alert単体は採用しない。prediction bias併用もdynamic policyではなくpreflight
Next: range_low_vol/ny_overlapをentry-level EV overestimate, NY-overlap side inversion, or current-month first-lossで検出する
```

```text
Report: 00199 Entry Signal Residual Context Audit
Status: diagnostic preflight / not standard
Question: 00198で残ったrange_low_vol/ny_overlap replacement shortをentry時点のcausal signalで覆えるか
Best evidence: gap5 late replacement -286.9878; prior OR focus entry signal covers -252.0972 and leaves -34.8906. Focus entry signal alone catches 2025-10/12 initial losses that first-loss control cannot catch.
Decision: focused entry signalは有望だが、まだpreflight。gap0へ広げると良いreplacementを消す可能性がある
Next: dynamic hook was tested in 00200; move to replacement-aware target
```

```text
Report: 00200 Focus Entry Dynamic Hook
Status: diagnostic infrastructure / not standard
Question: focused entry signalをgap5/budget0へ動的に重ねると、一玉制約とreplacement込みで改善するか
Best evidence: original OR condition worsens +508.9838 -> +507.4968 and worst -215.1172 -> -220.3612. Rank-only 0.53 gives +511.5964 with same worst/DD, but the gain is only +2.6126.
Decision: hookは残す。OR condition and side-gap-only are rejected. Rank-only is weak candidate, not standard.
Next: model only_candidate replacement short as replacement risk target
```

```text
Report: 00201 Replacement Risk Target Diagnostics
Status: diagnostic infrastructure / not standard
Question: only_candidate shortをreplacement risk target化すると、悪いreplacementを事前評価できるか
Best evidence: global_gap5 replacement is +210.5324 over all 2025 but -286.9878 in late 2025-08..12. profit_hit<0.5 covers -291.8810 late but +144.2660 over all year; pred_ev<15 is smaller but negative in both all-year (-87.9540) and late (-83.8596).
Decision: target化は採用。global profit_hit gateは棄却。pred_ev<15は低容量candidate
Next: dynamic hook was tested in 00202; validate fixed triggered profit-miss on unseen same-family data
```

```text
Report: 00202 Triggered Replacement Risk Hook
Status: historical candidate / refuted later / not standard
Question: prior deterioration trigger後だけreplacement risk hookを動的に重ねると、一玉制約とreplacement込みで改善するか
Best evidence: gap5/budget0 baseline +508.9838 / worst -215.1172. triggered profit-miss min4 +790.3634 / worst -46.0150 / max DD 129.7364. low-EV only +540.5594 and leaves worst unchanged.
Decision: triggered profit-miss was strongest candidate before 00203; low-EV is diagnostic only. Not standard until unseen same-family validation.
Next: fixed triggered profit-miss was checked in 00203 and failed to beat gap5/budget0
```

```text
Report: 00203 Triggered Profit-Miss Same-Family Check
Status: fixed-check refutation / not standard
Question: 00202のtriggered profit-missを同一risk列の別期間へ再探索なしで固定適用すると汎化するか
Best evidence: 2024-11..2025-04 same-family smoke: gap5/budget0 +445.8266 / worst -39.0766; triggered profit-miss +367.8768 / worst -39.0766. Trigger fired in 2025-03/04 and removed profitable short exposure.
Decision: triggered profit-miss is downgraded to diagnostic candidate. gap5/budget0 was checked next in 00204.
Next: 00204 refuted promotion of gap5/budget0 on additional apply months; generate wider same-risk 2024 columns for pure 2024 checks.
```

```text
Report: 00204 Gap5 Budget Same-Family Extension
Status: fixed-check refutation / diagnostic baseline
Question: 00203で残ったgap5/budget0単体を追加same-family windowへ再探索なしで固定適用すると安定するか
Best evidence: 2024-11..2025-08 10ヶ月では gap5/budget0 +384.6968 vs source +219.9460。ただし追加apply 2025-05..08だけでは gap5 +13.9434, source +66.7730, baseline +176.8236。2025-06でsourceより -86.2130 悪い。
Decision: gap5/budget0は標準採用候補から外し、diagnostic baseline / intervention locatorとして残す。
Next: pure 2024 same-risk列を生成し、baseline / p10+replm10 / gap0 / gap5 を広いregimeで固定比較する。
```

```text
Report: 00205 Same-Family Side Calibration Diagnostics
Status: diagnostic preflight / not standard
Question: 00204のgap5失敗は単純なshort過剰で説明できるか。純2024検証の不足はデータ不足か。
Best evidence: local M1 data covers 2009-03-15..2026-06-01. raw EV short bias is +0.27..+0.30 in 2025-04..06, but gap5 removes good 2025-06 shorts and worsens source by -86.2130; residual largest gap5 loss includes long 2025-07 down_low_vol/ny_overlap -97.4172.
Decision: 2025系列へshort-only hookを追加しない。side_drift_diagnosticsをfuture candidate preflightにする。
Next: generate early-2024 HGB+MLP forced predictions, then produce same-risk columns before 2024-11 without final-model leakage.
```

```text
Report: 00206 Early-2024 Chronological Risk OOF
Status: bridge artifact / fixed-check diagnostic
Question: 早期2024のpredictionとstateful risk列を前倒し生成できるか。純2024側でsource/side penaltyは安定するか。
Best evidence: 2023-only HGB+MLP generated 2024-03..06 hybrid predictions; expanded risk OOF starts at 2024-05 with AUC 0.6800. Pure-2024 available 6 months: source p10/replm10 +21.6688, no-side +12.0322; no-side has better worst month -74.9020 and max DD 112.0964.
Decision: source/side penaltyは標準採用しない。early risk OOFを診断artifactとして残す。
Next: decide whether to regenerate all 2024 months under one chronological protocol before gap0/gap5/budget0 pure-2024 checks.
```

```text
Report: 00207 Full-2024 Chronological Protocol
Status: canonical 2024 diagnostic / not standard
Question: 00206の混合family bridgeを解消して、2024-03..12を同一chronological protocolで比較するとsource/risk hookはNoTradeを超えるか。
Best evidence: train 2023-01..12, valid 2024-01..02, test 2024-03..12. OOF 2024-05..12: source p10/replm10 -3.1736, risk5 side -10.4618, risk0 side -32.7828, no-side -141.8816. Best still below NoTrade.
Decision: 標準採用なし。source/risk5はdiagnostic baseline。entry EV calibration / admission layerを優先する。
Next: fix EV scale drift and evaluate candidates against NoTrade first; run gap0/gap5/budget0 on this family only as diagnostic stress test.
```

```text
Report: 00208 Entry EV Calibration Admission
Status: diagnostic candidate / not standard
Question: raw EVとcalibrated EVのadmission thresholdは2024 validationからtestへ外挿するか。
Best evidence: raw validation winner entry12/short3 is +22.7292 on validation but -442.4662 on full 2024 test. Calibrated entry10/short6 is +100.3612 and entry12/short6 is +74.0644 on full 2024 test, but both are selected only as validation NoTrade ties.
Decision: calibrated EV + high short thresholdは診断候補。validationでpositive edgeを証明していないため標準採用しない。
Next: pre-register NoTrade tie selector and rerun the same calibrated admission grid on fresh chronological folds.
```

```text
Report: 00209 Entry EV NoTrade Selector Fresh Fold
Status: accepted selector infrastructure / diagnostic candidate only / not standard
Question: NoTrade tie/near-tieをtestで都合よく選ばないselectorを実装すると、fresh 2024-03..04 validationでcalibrated admissionは標準選択されるか。
Best evidence: standard selector chooses NoTrade because best validation total is -1.8610. Diagnostic selector picks calibrated entry12/short6; fixed 2024-05..12 test is +65.4014, worst -37.8326, trades 19. 00210 corrected this fixed test as min_entry_rank=0.5.
Decision: selector is accepted infrastructure; standard policy remains NoTrade. cal12/short6/min_rank0.5 is diagnostic only.
Next: 00210 added explicit rank-grid support audit; run selector on additional chronological model-refit folds.
```

```text
Report: 00210 Entry EV Rank Gate Support Audit
Status: diagnostic admission axis / accepted support-gate infrastructure / not standard
Question: `min_entry_rank` を明示grid化し、support gateを追加するとfresh validationでNoTradeを超える候補を標準選択できるか。
Best evidence: fresh 2024-03..04 best is entry10/short9/min_rank0.0 with +17.0910, worst +0.7230, but only 4 validation trades. With min_trades=10, active_months>=2, worst>=0, standard selector returns NoTrade. Fixed 2024-05..12 for that row is +87.8942, worst -2.2800, trades 10; entry8/short9/min_rank0.6 is +74.2970, worst -20.1600, trades 11.
Decision: rank gate is useful diagnostic admission axis, but low-support candidates are not standard policies.
Next: run rank/quantile admission on additional chronological model-refit folds and require support before promotion.
```

```text
Report: 00211 Entry EV Rank Refit 2025 Fold
Status: validation-design stress test / not standard
Question: 2024で再fitし、2025-01..02 validationでsupport gateを満たすrank候補は2025-03..12へ外挿するか。
Best evidence: validation selects entry12/short3/min_rank0.0 with +209.4234, worst +71.1950, trades 170. Fixed test collapses to -1002.1534, worst -294.1980, trades 1147.
Decision: support gateだけでは不十分。2ヶ月validationは未来10ヶ月regimeを代表できない。
Next: use multiple validation windows, side/regime floors, side balance, and trade-frequency gates.
```

```text
Report: 00212 Entry EV Multi-Window Admission Selector
Status: accepted selector infrastructure / not standard
Question: fresh2024 and refit2025 validation windowsを同時に通すと、NoTradeを上回る候補を選べるか。
Best evidence: strict support gate returns NoTrade. Relaxed min_window_trades=1 selects entry10/short9/min_rank0.0 with validation +190.4544, but fixed tests are -943.9322. max_side_trade_share<=0.95 returns NoTrade.
Decision: multi-window selector is accepted, but relaxed-selected policy is rejected. Side balance and window support are rejection axes, not frozen thresholds yet.
Next: evaluate side/regime/window gate sensitivity before freezing any admission gate.
```

```text
Report: 00213 Entry EV Gate Sensitivity
Status: accepted diagnostic infrastructure / not standard
Question: side balance, window support, and regime floor thresholdsを振れば、fixed testに耐えるentry EV candidateが出るか。
Best evidence: 576 gate variants: 568 NoTrade, 8 policy. All 8 select entry10/short9/min_rank0.0 and fixed-test to -943.9322. max_side<=0.95, min_window_trades=10, and min_combined_regime>=-50 all produce NoTrade.
Decision: gate sensitivity infrastructure is accepted. Simple threshold tuning does not find a robust policy; current standard remains NoTrade.
Next: add more validation windows and investigate sparse high-rank rows without using fixed-test PnL for selection.
```

```text
Report: 00214 Entry EV Sparse Rank Diagnostics
Status: accepted diagnostic infrastructure / not standard
Question: fixed-test-positive sparse high-rank rowをfixed PnLで選ばず、validation evidenceだけで説明できるか。
Best evidence: 72 candidates, validation eligible 0. The only fixed-positive audit row is entry14/short9/min_rank0.6, but validation total is -0.3844, trades 3, min window trades 0, side share 1.0000. fresh2024 is 0 trades; refit2025 is 3 long-only trades and negative.
Decision: sparse high-rank row is not selectable. It is a hindsight clue, not validation-supported edge.
Next: add validation windows and side/regime-aware rank or calibrated EV quantile before any sparse-row promotion.
```

```text
Report: 00215 Entry EV Validation Inventory
Status: accepted inventory infrastructure / not standard
Question: 既存entry EV/rank artifactsを追加validation windowとして安全に使えるか。
Best evidence: 39 metrics files inspected. Full-rank validation candidates are only fresh2024 2024-03..04 and refit2025 2025-01..02. 2025-03..12 is fixed test; 2024-05..12 is fixed test and partial rank.
Decision: fixed-test artifactsをvalidationへ流用しない。新foldか明示的なrank sweep再生成が必要。
Next: regenerate 2024-01..02 full-rank as calibration-validation, then create new chronological fold for true evidence.
```

```text
Report: 00216 Entry EV Cal2024 Rank Window
Status: accepted calibration-validation artifact / not standard
Question: 2024-01..02をfull-rank grid化するとmulti-window admission evidenceは増えるか。
Best evidence: cal2024 full-rank has 144 rows, 8 trades, total -70.3272. 3-window strict selector returns NoTrade. Relaxed selector repeats entry10/short9/min_rank0.0, but side095 returns NoTrade.
Decision: cal2024 is not a clean holdout and adds no active support. Standard remains NoTrade.
Next: diagnose why high-threshold rows vanish and avoid treating no-trade calibration months as positive evidence.
```

```text
Report: 00217 Entry EV Admission Input Diagnostics
Status: accepted diagnostic infrastructure / not standard
Question: cal2024で高threshold/rank候補が消え、refit2025で候補が過剰に出る理由はprediction入力側で説明できるか。
Best evidence: cal2024 side_gap>=5 is only 11 / 56,077 and entry10/short9/min_rank0.0 has 0 stateless entries, while holding validity is complete. Refit2025 same config has 29,567 entries, 29,522 long. entry14/short9/min_rank0.6 has fresh2024 0 entries and refit2025 25 long-only entries.
Decision: absolute EV thresholds are not stable cross-fold admission scale. Use side/regime-local quantile/rank diagnostics before policy promotion.
Next: compare raw EV, calibrated EV, EV quantile, side-gap quantile, and entry-rank quantile across new chronological folds.
```

```text
Report: 00218 Entry EV Scale Quantile Diagnostics
Status: accepted diagnostic infrastructure / not standard
Question: fold内quantileでEV/side-gap/rankを比較すると、絶対EV閾値のscale driftを吸収できるか。
Best evidence: calibrated selected score q95: cal2024 11.16..11.22, fresh2024 12.08..15.86, refit2025 23.52..23.73. side_regime_session_month q99/sidegap95/rank90 gives cal2024 41 entries, fresh2024 316, refit2025 32, versus absolute gate no-entry/over-entry drift.
Decision: quantile admission is promising infrastructure but not a policy yet. It must be connected to stateful backtest and NoTrade comparison.
Next: add quantile columns to backtest input path and test pre-registered side_regime_session_month quantile gates.
```

```text
Report: 00219 Entry EV Quantile Policy Backtest
Status: accepted backtest infrastructure / not standard
Question: side/regime/session-local quantile gateをstateful timed_ev policyへ接続するとNoTradeを超えるか。
Best evidence: side_regime_session_month q99/sidegap95/rank90 is +6.2048 on cal2024 with 14 trades, but fresh2024 validation worst is -12.4240 and refit2025 validation total is -27.9456. q95 improves fresh fixed diagnostic but loses on refit validation.
Decision: quantile admission infrastructure is accepted, but tested quantile policies are rejected.
Next: add role-level NoTrade-first selector and keep fixed windows diagnostic-only.
```

```text
Report: 00220 Entry EV Quantile Role Selector
Status: accepted selector infrastructure / not standard
Question: validation roleだけでquantile candidatesをNoTrade-firstに選ぶと何が残るか。
Best evidence: strict3 and clean2 both select NoTrade. Clean2 absolute-threshold baseline has validation total +254.7066 and min role +16.1220, but fails role_trades_low and side_share_high.
Decision: fixed diagnostic PnL must not rescue validation-failing candidates. Current standard remains NoTrade.
Next: test pre-registered positive EV floor candidates, then inspect selected trades by context.
```

```text
Report: 00221 Entry EV Quantile Positive Floor
Status: accepted candidate syntax / not standard
Question: quantile gateに小さなselected EV floorを足すとrole/month floorsを通過するか。
Best evidence: q95 floor10 improves fresh validation worst from -3.6326 to -1.6462 but leaves refit validation at -23.6438. q90 floor candidates increase trades and worsen fresh tails. strict3/clean2 remain NoTrade.
Decision: floor syntax is accepted, but floor tuning is not solving the failure.
Next: split selected-trade failures into context-side inversion and exit capture.
```

```text
Report: 00222 Entry EV Quantile Trade Context Diagnostics
Status: accepted diagnostic infrastructure / not standard
Question: quantile/floor候補のselected tradesはどのrole/contextで壊れているか。
Best evidence: q95 floor10 refit has total -23.6438, direction error 0.4643, exit regret 572.3960. q90 failures concentrate in fresh2024 bad short contexts. Worst contexts include refit short range_normal_vol/ny_overlap with direction error 1.0.
Decision: entry floorだけで救わない。context-side inversion and exit capture must be diagnosed separately.
Next: run exit capture diagnostics on q95/q99 validation trades, and separately design context-side inversion guard.
```

```text
Report: 00223 Entry EV Quantile Exit Capture Diagnostics
Status: accepted diagnostic infrastructure / not standard
Question: q95/q99候補はentryが悪いのか、それとも260m hold capでexit captureを失っているのか。
Best evidence: q95 fresh early-exit rate is 0.7895, cap-hit 0.9474, policy hold minus oracle -412.0192. q95 refit early-exit is 0.7857..0.7931, cap-hit 0.9286..0.9310, policy hold minus oracle -593.6399..-675.9972. q99 cal early-exit and cap-hit are both 1.0.
Decision: exit capture issue is real, but blind max_predicted_hold extension is rejected because refit still has direction/context error.
Next: pre-register hold-cap sensitivity 260/480/720/1440 on validation roles, with and without context-side inversion guard.
```

```text
Report: 00224 Entry EV Quantile Hold-Cap Sensitivity
Status: accepted sensitivity infrastructure / diagnostic candidate only / not standard
Question: q95/q99候補で260/480/720/1440m hold capを比較し、context-side inversion guardなし/ありでNoTradeを超えるか。
Best evidence: no-guard q95_floor5 improves from 260m -5.6974 / min role -23.2338 to 720m +117.0340 / min role +16.2628, but min month remains -9.1718. Diagnostic inversion guard min1 at 720m reaches +273.6662 / min role +27.7034; support>=4 guard reaches +235.0452 / min role +25.3464. All rows still fail month_pnl_below_floor.
Decision: 720m is the next diagnostic cap, but blind promotion and same-validation guard are rejected. Current standard remains NoTrade.
Next: convert the inversion guard into a prior-only detector, then retest 720m vs 260m without target-month leakage.
```

```text
Report: 00225 Entry EV Quantile Prior Inversion Guard
Status: accepted guard infrastructure / current guard rejected / not standard
Question: same-validation inversion guardを対象月より前のtrade実績だけで作ると、720m q95候補はNoTradeを超えるか。
Best evidence: fast prior 720m q95_floor5 reaches validation +139.0422 / min role +17.7308 / min month -0.4914, but still fails month floor. Fresh fixed no-guard 720m is +402.1118 / min role +76.2204, while prior guard 720m is +373.4814 / min role +2.0982.
Decision: prior-only guard infrastructure is accepted. Current context blocking over-blocks good fixed trades, so it is not standard.
Next: turn prior direction error / side PnL / predicted side bias / support into a risk score or rank feature instead of hard blocking.
```

```text
Report: 00226 Entry EV Prior Context Risk Score
Status: accepted diagnostic infrastructure / current guard not standard
Question: prior context-side evidenceをscore化し、hard blockより少ない副作用で720m q95候補を改善できるか。
Best evidence: validation q95_floor5/720m improves +117.0340 -> +133.2270 but min month remains -9.1718. Fresh fixed fresh-only prior worsens +402.1118 -> +396.0818; cal+fresh prior improves to +427.6524, but min month still -9.1718.
Decision: risk score diagnostics, prior_risk guard, and prior_roles split are accepted. Standard policy remains NoTrade.
Next: predeclare prior roles across more chronological windows and use risk score as selector/ranking feature, not only a hard block.
```

この型により、各レポートの数値を「採用判断」とセットで読めるようにする。
