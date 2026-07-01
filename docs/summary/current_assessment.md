# Current Assessment

最終更新: 2026-07-02 03:03 JST

## 結論

標準採用できる利益最大化policyはまだない。

現在の標準判断は NoTrade-first。候補policyは、複数chronological window、role/month PnL floor、trade support、side balance、NoTrade比較を通らない限り標準化しない。

直近で最も進んだ候補は exit-regret系。`00258` で `confidence_exit t0.4` selectorがbroad/fixed2025を改善し、`00261` でreplacement guard replayも改善した。ただし `00262` のNoTrade-first admissionでは strict / relaxed ともNoTrade。`00263` でfresh2024 0-tradeの主因はpost-block `side_gap_pct` 汚染と分かり、`00264` でpre-block side-gap quantileを実装した。しかしrefit tailが戻るため、標準policyではなくdiagnostic infrastructureに留める。

## 現在の判断

| 項目 | 判断 |
|---|---|
| Standard policy | なし。NoTrade-firstを維持 |
| Current diagnostic candidate | `exit_regret_selector_replguard_confidenceexit_bucket_t0p4` |
| Why not standard | `sg95` post-blockではfresh2024が0 trade。pre-block/sg0ではrefit tailが大きい |
| Useful signal | exit-regret / loss-first / replacement-stateful-net |
| Main risk | 勝ちtrade削除、only-candidate replacement悪化、May tail、same-window tuning |

## 研究レーン

| レーン | Reports | 現状 |
|---|---|---|
| Short budget / side drift | `00174`..`00207` | budget0とside drift guardはtailを縮めるが、same-family / 2024 chronologyで標準化できず診断baseline止まり。 |
| Entry EV admission | `00208`..`00224` | raw/calibrated EV、rank、quantile、positive floor、hold-capを検証。NoTrade-first selectorは通らない。 |
| Executable EV / capture | `00225`..`00232` | executable EVやdense captureはrow-level改善があるが、stateful validationでtailとsupport不足が残る。 |
| Side balance / composite | `00233`..`00239` | side-balanceやcomposite hard gateでは候補が生まれず、component targetへ分解。 |
| Component / exit-regret | `00240`..`00264` | EV overestimateからdirection/exit/replacementへ分解。現時点の最有望はexit-regret + replacement guardだが、admission未通過。00264でpre-block side-gap quantileを追加したがpolicyはreject。 |

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

## 次にやること

1. pre-block side-gapで新たに入ったrefit2025 rowsを分解し、どのcontext/monthがtailを戻したか確認する。
2. two-stage admissionを検討する。pre-block side-gapでsupportを正常化し、その後にreplacement/tail risk guardで新規refit rowsを審査する。
3. May 2025 tailを診断する。replacement guard後もq99/q95のMay worstが残る。
4. q95/q99の選択は同じreplay上でチューニングせず、外部validationで支持されるまでdiagnostic candidateに留める。
5. role trade support、role PnL、month floor、side share、NoTrade-first比較を標準採用ゲートとして維持する。

## 最短で読む順

1. `00258_2026-07-02_entry_ev_exit_regret_selector_candidate.md`
2. `00259_2026-07-02_entry_ev_exit_regret_selector_delta.md`
3. `00260_2026-07-02_entry_ev_exit_regret_replacement_risk.md`
4. `00261_2026-07-02_entry_ev_exit_regret_replacement_guard_replay.md`
5. `00262_2026-07-02_entry_ev_exit_regret_replacement_guard_admission.md`
6. `00263_2026-07-02_entry_ev_quantile_candidate_support_diagnostics.md`
7. `00264_2026-07-02_entry_ev_preblock_side_gap_quantile.md`
