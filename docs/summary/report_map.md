# Report Map

最終更新: 2026-06-30 09:05 JST

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
| `00186`..`00191` | short-specific interaction / entry budget | short raw gapは介入箇所を示す。`budget0` とprior triggerによりtailは大きく縮んだが、min8ではまだNoTradeを超えない。 |

## テーマ別読む順

### 現在の失敗原因を知る

1. `00174_2026-06-29_holding_max_fresh_2025_09_12.md`
2. `00175_2026-06-29_side_drift_diagnostics.md`
3. `00179_2026-06-29_side_drift_guard_residual_diagnostics.md`
4. `00190_2026-06-30_context_entry_budget_zero.md`
5. `00191_2026-06-30_short_budget_drift_trigger.md`

### 現在の候補軸を知る

1. `00178_2026-06-29_side_drift_guard_admission_margin.md`
2. `00182_2026-06-30_context_drawdown_guard_margin_sweep.md`
3. `00188_2026-06-30_short_entry_budget_guard.md`
4. `00190_2026-06-30_context_entry_budget_zero.md`
5. `00191_2026-06-30_short_budget_drift_trigger.md`

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

この型により、各レポートの数値を「採用判断」とセットで読めるようにする。
