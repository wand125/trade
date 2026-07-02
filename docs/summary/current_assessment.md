# Current Assessment

最終更新: 2026-07-02 09:28 JST

## 結論

標準採用できる利益最大化policyはまだない。

現在の標準判断は NoTrade-first。候補policyは、複数chronological window、role/month PnL floor、trade support、side balance、NoTrade比較を通らない限り標準化しない。

直近で最も進んだ候補は exit-regret系から、capture-adjusted score上のcoarse side/regime tail-risk headへ移ったが、外部HGB chronologyで弱い再現に留まった。`00258` で `confidence_exit t0.4` selectorがbroad/fixed2025を改善し、`00261` でreplacement guard replayも改善した。ただし `00262` のNoTrade-first admissionでは strict / relaxed ともNoTrade。`00263` でfresh2024 0-tradeの主因はpost-block `side_gap_pct` 汚染と分かり、`00264` でpre-block side-gap quantileを実装した。`00265` では追加refit rowsのtailを分解し、`00266` では前月までの `direction_regime` 損失で q99/floor5 の追加rowを止める余地を確認した。`00267` でこれをstateful replayへ接続し、q99/floor5はoverall `+55.6750` まで改善したが、標準strict/relaxed admissionはrole trade support不足でNoTradeのまま。`00269` では外部HGB preflightに固定適用し、supportはあるがoverall `-9.5756` でNoTrade未満。`00270` では外部HGB+MLP hybrid 2025-09..12にも固定適用し、q99 `-28.3940`, q95 `+0.0820` だがmonth floor未達でNoTradeだった。`00271` ではその損失を教師/特徴量設計の観点で分解し、同方向oracle利益を実行exitで取り逃すexit-capture failureとEV過大評価が中心だと確認した。`00272` では既存executable EV補正をpost-selector scoreに掛けたがNoTrade未満。`00273` ではselector前base scoreへ移してq95 `-12.1040` まで戻したが、まだNoTrade未満だった。`00274` では `direction_regime` tail-riskを重ねるとq99が `+3.1260` まで改善したが、3 trades / all-long / month floor未達でadmissionはNoTradeだった。`00275` で外部HGBへ固定適用すると、bestはoverall `-9.1956` と00269比 `+0.3800` の小幅改善に留まり、標準化を支持しなかった。`00276` でexit timingへ戻り、低いloss-first dynamic exit thresholdを検証した。HGB単体では q95 + `loss_exit20/25` がgateを通ったが、hybridでは最良閾値が `0.35` 付近へずれた。統合では q95 + `loss_exit30` が total `+44.5308`, role min `+2.6780`, positive roles `3/3` まで改善したが、month min `-4.1460` が残った。`00277` で q95 + `loss_exit30` を内部chronologyへ再探索なしで固定適用し、base `-14.6536` から `+67.5682` へ改善、00276外部と統合して total `+112.0990`, positive roles `6/6` になった。ただし month min `-11.3450` と追加entry負けが残った。`00278` でdynamic exit後cooldownを追加し、q95 + `loss_exit30_cd15` は内部+外部統合 total `+118.6900`, positive roles `6/6`, month min `-6.8324`, trades `266` へ改善した。ただしmonth floorはまだ負、fresh/hybrid supportも薄いため標準採用はしない。

## 現在の判断

| 項目 | 判断 |
|---|---|
| Standard policy | なし。NoTrade-firstを維持 |
| Current diagnostic candidate | q95 + `loss_exit30_cd15` dynamic exit cooldown。pre-standard diagnostic candidate。`loss_exit30` 単体はbaselineへ降格 |
| Why not standard | `00278` 統合では positive roles `6/6` だが month min `-6.8324` が残る。fresh/hybrid supportが薄く、hybrid 2025-12 `-4.1460` はcooldownでは消えない |
| Useful signal | exit-regret / loss-first dynamic exit / replacement-stateful-net / same-side missed loss / low-capture loss / profit-barrier miss |
| Main risk | 勝ちtrade削除、only-candidate replacement悪化、high-score losing tail、May/September tail、q99/q95 same-window selection、support緩和によるrole PnL崩壊、別familyでのPnL再現不足 |

## 研究レーン

| レーン | Reports | 現状 |
|---|---|---|
| Short budget / side drift | `00174`..`00207` | budget0とside drift guardはtailを縮めるが、same-family / 2024 chronologyで標準化できず診断baseline止まり。 |
| Entry EV admission | `00208`..`00224` | raw/calibrated EV、rank、quantile、positive floor、hold-capを検証。NoTrade-first selectorは通らない。 |
| Executable EV / capture | `00225`..`00232` | executable EVやdense captureはrow-level改善があるが、stateful validationでtailとsupport不足が残る。 |
| Side balance / composite | `00233`..`00239` | side-balanceやcomposite hard gateでは候補が生まれず、component targetへ分解。 |
| Component / exit-regret | `00240`..`00278` | EV overestimateからdirection/exit/replacementへ分解。00267でq99 prior guardがstateful replay上は改善したが、標準admission未通過。00268でfresh support不足がepisode集中であり、rank0緩和はcal/refitを壊すと確認。00269の外部HGB、00270の外部full-hybridでもNoTrade未満。00271で損失はno-edgeではなくexit-capture failure / executable EV過大評価に寄ると確認。00272でpost-selector executable scoreは負の対照としてreject。00273でselector前capture補正もNoTrade未満。00274でcoarse `direction_regime` tail-riskはq99をプラス化したが、support/side集中でNoTrade。00275で外部HGB再現は弱く、tail-risk headはdiagnosticへ降格。00276/00277でlow loss-first dynamic exitが全role positiveまで進み、00278でcooldownが過剰回転を抑えたが、month floorと薄いsupportが残る。 |

## 採用済みインフラ

- NoTrade-first selector
- multi-window admission selector
- quantile admission and stateful replay
- trade delta / replacement-risk diagnostics
- component target decomposition and calibration
- forced-exit / direction-exit / exit-regret selector input generation
- replacement guard replay and admission diagnostics
- quantile candidate support diagnostics
- pre-block side-gap quantile selector input option
- policy delta context diagnostics
- prior context guard diagnostics
- prior-guard prediction input generation
- quantile policy side-block passthrough
- candidate episode support diagnostics
- base policy input aliases for external HGB preflight
- side/regime tail-risk prediction input generation
- side-gap source inheritance for post-selector score heads
- quantile policy exit-timing sensitivity replay
- variant trade delta diagnostics
- dynamic exit minimum-hold / cooldown hooks

## 採用しないもの

- fixed testだけで良い候補を標準化すること
- single 2-month validationだけで候補を標準化すること
- pointwise screenをstateful policy evidenceとして扱うこと
- raw/calibrated EVの絶対thresholdを標準policyにすること
- sparse high-rank候補をsupport不足のまま採用すること
- current replacement guard candidateを追加chronologyなしで標準化すること
- support-relaxed q99/floor5をfresh2024 0-tradeのまま標準化すること
- `sg0` をsame-window診断だけで標準化すること
- pre-block `sg95` をrefit tail悪化のまま標準化すること
- refit2025の同一window診断だけで `short/down_normal_vol` などを静的blacklist化すること
- prior context guardのno-replacement estimateをstateful policy evidenceとして扱うこと
- support-relaxed selectionを標準admissionとして扱うこと
- q99 rank0緩和をfresh support改善だけで採用すること
- 外部HGB preflightのpositive sub-windowだけでq99 prior guardを採用すること
- q99 prior guard branchをさらにthreshold rescueすること
- q95のnear-zero totalをmonth floor未達のまま救済候補にすること
- `direction_regime` tail-risk q99を3 trades/all-longのまま標準採用すること
- side-gap quantileを継承せず、no-prior rowのtrade pathまで変えるscore-head実験をpolicy evidenceにすること
- HGB単体で通った `loss_exit20/25` を追加chronologyなしで標準採用すること
- 同じ外部window上のloss-first exit threshold sweepをそのままpolicy化すること
- q95 + `loss_exit30` を全role positiveだけで標準採用すること
- q95 + `loss_exit30_cd15` をmonth floor負のまま標準採用すること
- minimum hold overlayをtotal改善だけで採用すること

## 次にやること

1. q95 + `loss_exit30_cd15` を固定し、残る負け月を refit churn / hybrid sparse residual / fresh sparse residual に分けて診断する。
2. absolute loss-first probability threshold `0.30` ではなく、対象月以前のvalidation分布に基づくquantile / calibrated thresholdへ置き換える。
3. hybrid 2025-11/12の残存損失はcooldownでは消えないため、direction / exit-capture featureへ戻して分解する。
4. score headをselector後に重ねる場合は `--side-gap-source-score-kind` でpre-block side-gap gateを明示的に継承する。
5. `direction_regime` tail-riskはdiagnostic featureとして保持し、policy candidateにはしない。
6. role trade support、role PnL、month floor、side share、NoTrade-first比較を標準採用ゲートとして維持する。

## 最短で読む順

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
