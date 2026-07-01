# Current Assessment

最終更新: 2026-07-01 22:29 JST

## 結論

標準採用できる利益最大化policyはまだない。

現在の実務上の標準判断は NoTrade-first。候補policyは、複数chronological window、role/month PnL floor、trade support、side balance、NoTrade比較を通らない限り標準化しない。

研究の価値は明確に残っている。backtest、OOF、walk-forward、candidate selection、trade delta、context guard、entry budget、entry EV calibration、component target診断までの基盤は使える。問題は「signalが全くない」ではなく、「単一gateや単一validation windowで拾ったedgeが別windowで反転する」こと。

## 現在の判断

| 項目 | 状態 | 判断 |
|---|---|---|
| Standard policy | なし | NoTrade-firstを維持 |
| Best current evidence | `00243` で `side_prior_pressure` がbaseよりAUC改善し、`00244` でstateful validationも改善 | diagnostic baseline止まり |
| Latest diagnostic result | `00245` でfixed 2025崩壊をpath分解。q95はcommon-entry差 `-46.6146` とreplacement差 `-58.6720` が両方悪化。q99はreplacement差 `+60.6992` で改善するがtotalは `-177.3790` | s0.5は標準採用しない |
| Pointwise screens | q95 floor5 の high EV-overestimate risk rows は損失を拾うが、contextによって勝ちも削る | replacement未評価なのでpolicyではない |
| Main failure | validation support不足、fold間EV scale drift、side/context反転、exit capture不足、one-position replacement、common-entry loss | hard blockではなく分解targetで扱う |

## 研究レーン

| レーン | 代表reports | 現状 |
|---|---|---|
| Short budget / side drift | `00174`..`00207` | `budget0` や side drift guard はtailを縮めるが、same-family / 2024 chronologyで標準採用には届かない。診断baselineとして残す。 |
| Entry EV admission | `00208`..`00221` | raw / calibrated EV threshold、rank gate、quantile admission、positive floorを検証。候補数やscaleは改善するが、NoTrade-first selectorは通らない。 |
| Exit capture / hold cap | `00222`..`00232` | `720m` や executable EV calibration は診断上有効。ただし月次tail、support不足、fresh/refit反転が残る。direct score標準化はしない。 |
| Side balance / downside | `00233`..`00239` | side-balance単独、downside interaction、coverage gate、composite gateはいずれも標準候補を生まない。component targetへ分解する方針に転換。 |
| Component target / EV overestimate | `00240`..`00245` | EV overestimateが相対的に最も使えるtarget。`side_prior_pressure` はAUCとvalidationを改善したが、fixed 2025で崩れた。00245でcommon-entry lossとreplacement lossを分離し、次はdirection/exit/replacement-aware targetへ移す。 |

## 採用済みインフラ

- NoTrade-first candidate selector
- multi-window admission selector
- gate sensitivity / sparse-rank diagnostics
- validation inventory / full-rank window棚卸し
- quantile admission columns and stateful replay
- prior inversion / prior context risk score diagnostics
- executable EV calibration diagnostics
- component target decomposition
- component target calibration
- EV-overestimate risk selector diagnostics
- EV-overestimate context diagnostics
- EV-overestimate context calibration sweep
- EV-overestimate side-prior-pressure prediction input generation
- fixed-period common-entry/replacement path diagnostics

## 採用しないもの

- fixed testでだけ良い候補をvalidationへ流用すること
- single 2-month validationだけで候補を標準化すること
- raw EV / calibrated EV の絶対thresholdをそのまま標準policyにすること
- sparse high-rank candidateをsupport不足のまま採用すること
- same-validation inversion guard
- current prior inversion / prior risk hard block
- executable EV hard threshold
- dense executable capture scoreのdirect replacement
- generic side-balance direct penalty
- side-balance-only screen
- composite hard gate
- component targetを単一binary no-trade labelへ潰すこと
- EV-overestimate high-risk rowsのpointwise削除をstateful policy結果として扱うこと
- `side_drift_bucket` や `full_context` を小データのbucket keyへ直入れすること
- `side_prior_pressure_s0p5` のrelaxed validation near-missを標準policyにすること
- `side_prior_pressure_s0p5` のfixed 2025 path分解後に、同じwindowでpenalty strengthだけを再探索すること

## 次にやること

1. q95/q99共通のcommon-entry lossを抑えるtargetを作る。候補は `direction_side_inversion`, `exit_capture_failure`, `same_entry_exit_delta`, `realized_loss`。
2. `range_normal_vol/ny_overlap` の低risk大損を、side margin、predicted hold、exit regret、recent realized context lossで説明できるか調べる。
3. `only_side_prior` replacementをtargetにして、replacement quality / positive replacement regret を別に診断する。
4. component targetsをより多いchronological windowsで生成し、early monthのno-prior問題を下げる。
5. pointwise screenを使う場合は、必ずone-position stateful replayかreplacement-aware diagnosticsで確認する。
6. 新候補は NoTrade、previous diagnostic baseline、cost stress、worst month、max DD、side PnL、trade supportで比較する。

## 代表的な読む順

最新判断だけ確認する:

1. `00239_2026-06-30_entry_ev_composite_target_decomposition.md`
2. `00240_2026-07-01_entry_ev_component_target_calibration.md`
3. `00241_2026-07-01_entry_ev_overestimate_risk_selector.md`
4. `00242_2026-07-01_entry_ev_overestimate_context_diagnostics.md`
5. `00243_2026-07-01_entry_ev_context_calibration_sweep.md`
6. `00244_2026-07-01_entry_ev_side_prior_pressure_policy_inputs.md`
7. `00245_2026-07-01_entry_ev_side_prior_pressure_fixed2025_failure_diagnostics.md`

entry EV admissionの流れを見る:

1. `00208_2026-06-30_entry_ev_calibration_admission.md`
2. `00212_2026-06-30_entry_ev_multiwindow_admission_selector.md`
3. `00218_2026-06-30_entry_ev_scale_quantile_diagnostics.md`
4. `00220_2026-06-30_entry_ev_quantile_role_selector.md`
5. `00224_2026-06-30_entry_ev_quantile_hold_cap_sensitivity.md`

short budget / side driftの経緯を見る:

1. `00174_2026-06-29_holding_max_fresh_2025_09_12.md`
2. `00178_2026-06-29_side_drift_guard_admission_margin.md`
3. `00190_2026-06-30_context_entry_budget_zero.md`
4. `00196_2026-06-30_budget0_replacement_path_diagnostics.md`
5. `00207_2026-06-30_chrono_2024_full_protocol.md`
