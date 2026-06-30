# Current Assessment

最終更新: 2026-07-01 08:16 JST

## 結論

標準採用できる利益最大化policyはまだない。

現在の実務上の標準判断は NoTrade-first。候補policyは、複数chronological window、role/month PnL floor、trade support、side balance、NoTrade比較を通らない限り標準化しない。

研究の価値は明確に残っている。backtest、OOF、walk-forward、candidate selection、trade delta、context guard、entry budget、entry EV calibration、component target診断までの基盤は使える。問題は「signalが全くない」ではなく、「単一gateや単一validation windowで拾ったedgeが別windowで反転する」こと。

## 現在の判断

| 項目 | 状態 | 判断 |
|---|---|---|
| Standard policy | なし | NoTrade-firstを維持 |
| Best current evidence | `00243` で `side_prior_pressure` がbaseよりchronological/role holdout AUCを改善 | 次の calibration / ranking head候補 |
| Latest selector result | `00241` の strict / relaxed / sensitivity は全てNoTrade | 現候補を昇格しない |
| Pointwise screens | q95 floor5 の high EV-overestimate risk rows は損失を拾うが、contextによって勝ちも削る | replacement未評価なのでpolicyではない |
| Main failure | validation support不足、fold間EV scale drift、side/context反転、exit capture不足、one-position replacement | hard blockではなく分解targetで扱う |

## 研究レーン

| レーン | 代表reports | 現状 |
|---|---|---|
| Short budget / side drift | `00174`..`00207` | `budget0` や side drift guard はtailを縮めるが、same-family / 2024 chronologyで標準採用には届かない。診断baselineとして残す。 |
| Entry EV admission | `00208`..`00221` | raw / calibrated EV threshold、rank gate、quantile admission、positive floorを検証。候補数やscaleは改善するが、NoTrade-first selectorは通らない。 |
| Exit capture / hold cap | `00222`..`00232` | `720m` や executable EV calibration は診断上有効。ただし月次tail、support不足、fresh/refit反転が残る。direct score標準化はしない。 |
| Side balance / downside | `00233`..`00239` | side-balance単独、downside interaction、coverage gate、composite gateはいずれも標準候補を生まない。component targetへ分解する方針に転換。 |
| Component target / EV overestimate | `00240`..`00243` | EV overestimateが相対的に最も使えるtarget。`side_prior_pressure` はbaseよりAUC改善。hard selectorではなく、prediction row側のranking/calibration headへ移す。 |

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

## 次にやること

1. `side_prior_pressure` EV-overestimate riskをprediction rowへ接続し、hard gateではなく entry ranking / score calibration / downside-weighted targetとして使う。
2. direction-side inversion targetは、selected side、actual best side、prior side PnL、prediction side drift、side margin/rankを足した別headで診断する。
3. exit-capture targetは、holding cap、exit event prediction、oracle best holding、capture shortfallを足したexit-specific headへ進める。
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
