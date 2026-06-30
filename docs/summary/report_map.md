# Report Map

最終更新: 2026-06-30 13:20 JST

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
| `00186`..`00209` | short-specific interaction / entry budget / side calibration / chronological 2024 OOF / entry EV admission selector | short raw gapは介入箇所を示す。`budget0` とprior realized/context-alert composite triggerによりtailは大きく縮んだが、prediction/alert単独triggerは上積みできない。alert context限定budget/admission/first-lossは狭すぎる。00196..00209で、global budget0との差、`gap5` replacement short、prior signal coverage、entry-level residual signal、dynamic hook、replacement risk target、triggered profit-miss hook、same-family fixed check、side calibration、早期2024 risk列生成、全2024同一chronological protocol、entry EV calibration/admission、NoTrade-first selectorを分解した。全2024 OOFではbest sourceでもNoTradeを超えず、fresh validationでもcalibrated high-threshold candidateはNoTrade未満なので標準採用しない。 |

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

### holding / exit 系の経緯を知る

1. `00039_2026-06-28_exit_event_timing_targets.md`
2. `00041_2026-06-28_holding_cap_sweep.md`
3. `00160_2026-06-29_dense_holding_shortening_targets.md`
4. `00170_2026-06-29_exit_shortening_failure_policy.md`
5. `00171_2026-06-29_exit_shortening_fixed_apply_2025_06_08.md`
6. `00172_2026-06-29_holding_max_cap_fullpred_apply_2025_06_08.md`
7. `00173_2026-06-29_holding_max_grid_2025_01_08.md`
8. `00174_2026-06-29_holding_max_fresh_2025_09_12.md`

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
Best evidence: standard selector chooses NoTrade because best validation total is -1.8610. Diagnostic selector picks calibrated entry12/short6; fixed 2024-05..12 test is +65.4014, worst -37.8326, trades 19.
Decision: selector is accepted infrastructure; standard policy remains NoTrade. cal12/short6 is diagnostic only.
Next: run selector on additional chronological model-refit folds; improve admission features until validation exceeds NoTrade.
```

この型により、各レポートの数値を「採用判断」とセットで読めるようにする。
