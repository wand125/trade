# Report Map

最終更新: 2026-06-30 11:23 JST

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
| `00186`..`00201` | short-specific interaction / entry budget | short raw gapは介入箇所を示す。`budget0` とprior realized/context-alert composite triggerによりtailは大きく縮んだが、prediction/alert単独triggerは上積みできない。alert context限定budget/admission/first-lossは狭すぎる。00196..00201で、global budget0との差、`gap5` replacement short、prior signal coverage、entry-level residual signal、dynamic hook、replacement risk targetを分解した。次はtrigger限定replacement low-EV hook。 |

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
Next: dynamic backtest trigger-limited replacement low-EV hook
```

この型により、各レポートの数値を「採用判断」とセットで読めるようにする。
