# Current Assessment

最終更新: 2026-07-02 03:38 JST

## 結論

標準採用できる利益最大化policyはまだない。

現在の標準判断は NoTrade-first。候補policyは、複数chronological window、role/month PnL floor、trade support、side balance、NoTrade比較を通らない限り標準化しない。

直近で最も進んだ候補は exit-regret系。`00258` で `confidence_exit t0.4` selectorがbroad/fixed2025を改善し、`00261` でreplacement guard replayも改善した。ただし `00262` のNoTrade-first admissionでは strict / relaxed ともNoTrade。`00263` でfresh2024 0-tradeの主因はpost-block `side_gap_pct` 汚染と分かり、`00264` でpre-block side-gap quantileを実装した。`00265` では追加refit rowsのtailを分解し、`00266` では前月までの `direction_regime` 損失で q99/floor5 の追加rowを止める余地を確認した。`00267` でこれをstateful replayへ接続し、q99/floor5はoverall `+55.6750` まで改善したが、標準strict/relaxed admissionはrole trade support不足でNoTradeのまま。

## 現在の判断

| 項目 | 判断 |
|---|---|
| Standard policy | なし。NoTrade-firstを維持 |
| Current diagnostic candidate | q99/floor5: `exit_regret_selector_replguard` + pre-block support normalization + prior `direction_regime` guard |
| Why not standard | strict/relaxed admissionで `role_trades_low`。fresh2024は1 tradeしかない |
| Useful signal | exit-regret / loss-first / replacement-stateful-net |
| Main risk | 勝ちtrade削除、only-candidate replacement悪化、high-score losing tail、May tail、q99/q95 same-window selection |

## 研究レーン

| レーン | Reports | 現状 |
|---|---|---|
| Short budget / side drift | `00174`..`00207` | budget0とside drift guardはtailを縮めるが、same-family / 2024 chronologyで標準化できず診断baseline止まり。 |
| Entry EV admission | `00208`..`00224` | raw/calibrated EV、rank、quantile、positive floor、hold-capを検証。NoTrade-first selectorは通らない。 |
| Executable EV / capture | `00225`..`00232` | executable EVやdense captureはrow-level改善があるが、stateful validationでtailとsupport不足が残る。 |
| Side balance / composite | `00233`..`00239` | side-balanceやcomposite hard gateでは候補が生まれず、component targetへ分解。 |
| Component / exit-regret | `00240`..`00267` | EV overestimateからdirection/exit/replacementへ分解。00267でq99 prior guardがstateful replay上は改善したが、標準admission未通過。policyはdiagnostic candidate止まり。 |

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

## 次にやること

1. q99/floor5 + prior direction_regime guardを固定し、外部chronologyまたは再生成familyへ再探索なしで適用する。
2. fresh2024 support不足を調べる。利益は出ているが1 tradeでは標準gateを通せない。
3. q95はstress比較に留める。statefulでもtail/DDがq99より悪い。
4. threshold/scopeを同じrefit windowで追加探索しない。
5. role trade support、role PnL、month floor、side share、NoTrade-first比較を標準採用ゲートとして維持する。

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
