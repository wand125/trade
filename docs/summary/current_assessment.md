# Current Assessment

最終更新: 2026-07-02 07:49 JST

## 結論

標準採用できる利益最大化policyはまだない。

現在の標準判断は NoTrade-first。候補policyは、複数chronological window、role/month PnL floor、trade support、side balance、NoTrade比較を通らない限り標準化しない。

直近で最も進んだ候補は exit-regret系。`00258` で `confidence_exit t0.4` selectorがbroad/fixed2025を改善し、`00261` でreplacement guard replayも改善した。ただし `00262` のNoTrade-first admissionでは strict / relaxed ともNoTrade。`00263` でfresh2024 0-tradeの主因はpost-block `side_gap_pct` 汚染と分かり、`00264` でpre-block side-gap quantileを実装した。`00265` では追加refit rowsのtailを分解し、`00266` では前月までの `direction_regime` 損失で q99/floor5 の追加rowを止める余地を確認した。`00267` でこれをstateful replayへ接続し、q99/floor5はoverall `+55.6750` まで改善したが、標準strict/relaxed admissionはrole trade support不足でNoTradeのまま。`00268` ではfresh support不足をepisode単位で分解し、rank0緩和はfresh supportを増やすがcal/refitを壊すことを確認した。`00269` では外部HGB preflightに固定適用し、supportはあるがoverall `-9.5756` でNoTrade未満。`00270` では外部HGB+MLP hybrid 2025-09..12にも固定適用し、q99 `-28.3940`, q95 `+0.0820` だがmonth floor未達でNoTradeだった。

## 現在の判断

| 項目 | 判断 |
|---|---|
| Standard policy | なし。NoTrade-firstを維持 |
| Current diagnostic candidate | なし。q99 prior guard branchはdiagnostic baselineとしてのみ保持 |
| Why not standard | strict/relaxed admissionで `role_trades_low`。外部HGBと外部full-hybrid preflightでもNoTrade未満 |
| Useful signal | exit-regret / loss-first / replacement-stateful-net |
| Main risk | 勝ちtrade削除、only-candidate replacement悪化、high-score losing tail、May tail、q99/q95 same-window selection、support緩和によるrole PnL崩壊、別familyでのPnL再現不足 |

## 研究レーン

| レーン | Reports | 現状 |
|---|---|---|
| Short budget / side drift | `00174`..`00207` | budget0とside drift guardはtailを縮めるが、same-family / 2024 chronologyで標準化できず診断baseline止まり。 |
| Entry EV admission | `00208`..`00224` | raw/calibrated EV、rank、quantile、positive floor、hold-capを検証。NoTrade-first selectorは通らない。 |
| Executable EV / capture | `00225`..`00232` | executable EVやdense captureはrow-level改善があるが、stateful validationでtailとsupport不足が残る。 |
| Side balance / composite | `00233`..`00239` | side-balanceやcomposite hard gateでは候補が生まれず、component targetへ分解。 |
| Component / exit-regret | `00240`..`00270` | EV overestimateからdirection/exit/replacementへ分解。00267でq99 prior guardがstateful replay上は改善したが、標準admission未通過。00268でfresh support不足がepisode集中であり、rank0緩和はcal/refitを壊すと確認。00269の外部HGB、00270の外部full-hybridでもNoTrade未満。branchはpolicy候補から外し、diagnostic baselineとして保持。 |

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

## 次にやること

1. q99 prior guard branchは閉じ、以後はdiagnostic baselineとしてだけ参照する。
2. 次はexit timing constraint、side/regime robustness、またはfull chronologyの学習設計を改善する。
3. `00270` の2025-09/12損失はfeature/target insightとしてのみ分解し、blacklist tuningには使わない。
4. fresh2024 support不足は、同一windowのrank/floor緩和ではなく、データ/window追加または別chronologyで解く。
5. threshold/scopeを同じrefit windowで追加探索しない。
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
