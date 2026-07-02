# Current Assessment

最終更新: 2026-07-02 13:12 JST

## 結論

標準採用できる利益最大化policyはまだない。

現在の標準判断は NoTrade-first。候補policyは、複数chronological window、role/month PnL floor、trade support、side balance、NoTrade比較を通らない限り標準化しない。

直近で最も進んだ候補は exit-regret系から、capture-adjusted score上のcoarse side/regime tail-risk headへ移ったが、外部HGB chronologyで弱い再現に留まった。`00258` で `confidence_exit t0.4` selectorがbroad/fixed2025を改善し、`00261` でreplacement guard replayも改善した。ただし `00262` のNoTrade-first admissionでは strict / relaxed ともNoTrade。`00263` でfresh2024 0-tradeの主因はpost-block `side_gap_pct` 汚染と分かり、`00264` でpre-block side-gap quantileを実装した。`00265` では追加refit rowsのtailを分解し、`00266` では前月までの `direction_regime` 損失で q99/floor5 の追加rowを止める余地を確認した。`00267` でこれをstateful replayへ接続し、q99/floor5はoverall `+55.6750` まで改善したが、標準strict/relaxed admissionはrole trade support不足でNoTradeのまま。`00269` では外部HGB preflightに固定適用し、supportはあるがoverall `-9.5756` でNoTrade未満。`00270` では外部HGB+MLP hybrid 2025-09..12にも固定適用し、q99 `-28.3940`, q95 `+0.0820` だがmonth floor未達でNoTradeだった。`00271` ではその損失を教師/特徴量設計の観点で分解し、同方向oracle利益を実行exitで取り逃すexit-capture failureとEV過大評価が中心だと確認した。`00272` では既存executable EV補正をpost-selector scoreに掛けたがNoTrade未満。`00273` ではselector前base scoreへ移してq95 `-12.1040` まで戻したが、まだNoTrade未満だった。`00274` では `direction_regime` tail-riskを重ねるとq99が `+3.1260` まで改善したが、3 trades / all-long / month floor未達でadmissionはNoTradeだった。`00275` で外部HGBへ固定適用すると、bestはoverall `-9.1956` と00269比 `+0.3800` の小幅改善に留まり、標準化を支持しなかった。`00276` でexit timingへ戻り、低いloss-first dynamic exit thresholdを検証した。HGB単体では q95 + `loss_exit20/25` がgateを通ったが、hybridでは最良閾値が `0.35` 付近へずれた。統合では q95 + `loss_exit30` が total `+44.5308`, role min `+2.6780`, positive roles `3/3` まで改善したが、month min `-4.1460` が残った。`00277` で q95 + `loss_exit30` を内部chronologyへ再探索なしで固定適用し、base `-14.6536` から `+67.5682` へ改善、00276外部と統合して total `+112.0990`, positive roles `6/6` になった。ただし month min `-11.3450` と追加entry負けが残った。`00278` でdynamic exit後cooldownを追加し、q95 + `loss_exit30_cd15` は内部+外部統合 total `+118.6900`, positive roles `6/6`, month min `-6.8324`, trades `266` へ改善した。ただしmonth floorはまだ負、fresh/hybrid supportも薄いため標準採用はしない。`00279` でraw `0.30` をglobal expanding loss-first quantileへ置き換えたが、best totalの `lfq60_cd15` は total `+135.3536` でも positive roles `4/6`, month min `-28.9404` で崩れた。`00280` で raw `loss_exit30_cd15` の残存損失をprediction文脈へjoinして分解し、loss trade 122件 `-229.4220` のうち no-edge entryは3件 `-34.6800` だけ、119件 `-194.7420` は同方向oracle利益ありと確認した。`00281` ではprior exit-capture risk、executable EV calibration、direct score shrinkを検証し、hard blockもdirect multiplicative shrinkもraw benchmarkを下回ると確認した。`00282` ではselected-trade supervised shrinkageがraw/prior calibrationよりMAEを改善するが、rank/gateとしては勝ちtradeを削ると確認した。`00283` でshrinkage headをprediction row側へ戻し、q95 no-floor + `loss_exit30_cd15` は total `+219.7158` まで伸びたが month min `-35.1586` でraw cd15より悪化した。`00284` ではraw cd15 scoreを維持し、shrinkage outputを補助featureにしたdownside meta hard blockを試したが、`gte1` はbaseline `+118.6900` から `+15.4886` へ悪化し、`gte3` はbaseline同等のno-opだった。`00285` ではsoft risk marginを試したが、best totalの `w0.25` も `+23.7938` でbaselineを大きく下回った。`00286` でcandidate-level stateful floor selectorを追加し、現候補群はfloor-only条件でもNoTradeと確認した。次はscore gatingではなく、raw cd15 losing monthsのexit timing / cooldown / post-exit re-entry path改善へ進む。

`00287` でraw cd15のpost-exit pathを分解し、`prev_loss` 後tradeは `+122.9292` と強く、単純なpost-loss cooldown拡張は勝ちを削ると確認した。次はscore gatingやentry削除ではなく、初回/孤立大損と前回勝ち後の大損に対するexit-capture改善へ戻る。

`00288` で isolated large-loss capture failure 23件 / `-125.5752` を特定した。22/23件はoracle best holdが実exitより後で、hold-extension targetとして濃い。ただしfixed 60/240/720mの一律置換はtotalを伸ばしてもmonth floorを悪化させるためreject。次はfixed-horizon/hold-extension choiceをchronological supervised targetとして学習し、prediction-row featureとしてstateful replayへ戻す。

`00289` で fixed-horizon / hold-extension choiceをchronological supervised targetとして学習した。default `isolated` 学習や `all` 学習はmonth floorを壊したが、`train_universe=isolated_loss` で exit時点観測可能な `isolated_large_loss` にthreshold 5を適用すると、no-replay診断では flagged 7 trades、actual replacement delta `+128.0630`、total `+246.7530`、month min `-6.8324` になった。ただし2025-09/2025-06/hybrid 2025-12の負け月は未改善で、no-replay置換はstateful policy evidenceではない。次はexit-time hold-extension hookへ接続し、00286 selectorでfull stateful replayする。

`00290` でこのhold-extension候補をstateful replayへ接続した。`isolated_large_loss` threshold 5は延長中の後続base trade skip込みでも total `+250.7350`, delta vs base `+132.0450`、extended 7、skipped 8、skipped PnL `-3.9820` で改善を維持した。ただし month min は `-6.8324` のままで、strict selectorもfloor-only selectorもNoTrade。未改善の2025-09/2025-06は、実際にはfixed horizonで大きく改善するlong lossがあるがpredicted deltaがthreshold未満で、hookではなくmodel recall/calibrationが次の課題。

`00291` でside-aware fixed-horizon replayを追加した。`isolated_large_loss_long` + fixed `720` + threshold `-5` は total `+318.8540`, delta vs base `+200.1640`, month min `-4.1460` まで改善し、00290で残った2025-09/2025-06 long lossを一部拾えた。ただし strict/floor-only selectorはいずれもNoTradeで、残るworstはhybrid 2025-12 short `-4.1460`。この損失は00290診断上 `target_best_delta=0.0` でhold-extensionでは直せないため、次はentry/no-entry、early stop、short-side blockの診断へ移る。

## 現在の判断

| 項目 | 判断 |
|---|---|
| Standard policy | なし。NoTrade-firstを維持 |
| Current diagnostic candidate | q95 + raw `loss_exit30_cd15` dynamic exit cooldown + side-aware hold-extension diagnostic。`isolated_large_loss_long + fixed720 + threshold -5` はtotal/floorを改善するがfloor未達のためdiagnostic止まり |
| Why not standard | raw `loss_exit30_cd15` は positive roles `6/6` だが month min負が残る。00291 bestもmonth min `-4.1460` でNoTrade-first floorを通らず、残るhybrid 2025-12 short lossはhold-extension targetでは改善不能 |
| Useful signal | exit-regret / loss-first dynamic exit / replacement-stateful-net / same-side missed loss / low-capture loss / isolated large-loss capture failure / fixed-horizon improvement target / chronological hold-extension predicted delta / side-aware fixed horizon replay / stateful extension skip impact / selected-side capture ratio / supervised shrinkage and downside meta features |
| Main risk | 勝ちtrade削除、only-candidate replacement悪化、high-score losing tail、May/September tail、q99/q95 same-window selection、support緩和によるrole PnL崩壊、別familyでのPnL再現不足、no-replay改善をpolicy evidenceと誤読すること、extensionで直せない `target_best_delta=0.0` の損失へextensionを無理に当てること |

## 研究レーン

| レーン | Reports | 現状 |
|---|---|---|
| Short budget / side drift | `00174`..`00207` | budget0とside drift guardはtailを縮めるが、same-family / 2024 chronologyで標準化できず診断baseline止まり。 |
| Entry EV admission | `00208`..`00224` | raw/calibrated EV、rank、quantile、positive floor、hold-capを検証。NoTrade-first selectorは通らない。 |
| Executable EV / capture | `00225`..`00232` | executable EVやdense captureはrow-level改善があるが、stateful validationでtailとsupport不足が残る。 |
| Side balance / composite | `00233`..`00239` | side-balanceやcomposite hard gateでは候補が生まれず、component targetへ分解。 |
| Component / exit-regret | `00240`..`00291` | EV overestimateからdirection/exit/replacementへ分解。00267でq99 prior guardがstateful replay上は改善したが、標準admission未通過。00268でfresh support不足がepisode集中であり、rank0緩和はcal/refitを壊すと確認。00269の外部HGB、00270の外部full-hybridでもNoTrade未満。00271で損失はno-edgeではなくexit-capture failure / executable EV過大評価に寄ると確認。00272でpost-selector executable scoreは負の対照としてreject。00273でselector前capture補正もNoTrade未満。00274でcoarse `direction_regime` tail-riskはq99をプラス化したが、support/side集中でNoTrade。00275で外部HGB再現は弱く、tail-risk headはdiagnosticへ降格。00276/00277でlow loss-first dynamic exitが全role positiveまで進み、00278でcooldownが過剰回転を抑えた。00279のglobal quantile化はtotal改善と引き換えにtail/roleを壊し、policy候補にはしない。00280でraw cd15の残存損失はentry無価値ではなくexit-capture / EV過大評価が中心と確認。00281でprior capture factorのhard block/direct shrinkはreject。00282でsupervised shrinkageはscale補正として有効だが、direct gateはreject。00283でprediction-row shrinkage inputはaccepted、score replacementはreject。00284でdownside meta hard blockはreject、00285でdownside soft marginもreject。00286でstateful floor selectorを追加し、現候補群は全てNoTrade。00287でpost-exit pathを分解し、broad post-loss cooldownは勝ちを削ると確認。00288でisolated large-loss capture failureを特定し、一律fixed horizonはfloor悪化でreject。00289でhold-extension choice targetを学習し、`isolated_loss` training + `isolated_large_loss` threshold 5を次のfull replay候補にした。00290でstateful replayに接続しtotal改善は維持したがmonth floor未達でNoTrade。00291でside-aware fixed 720mはtotal/floorを改善したが、残るhybrid 2025-12 short lossはextensionで直せないため次はentry/early-stop/block診断へ進む。 |

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
- chronological loss-first quantile input generation
- multifamily exit-timing trade enrichment and raw cd15 residual loss diagnostics
- configurable exit-capture context columns and partial capture-shrink ablation
- selected-trade supervised shrinkage diagnostics
- supervised shrinkage prediction-row policy input generation
- downside meta prediction-row side-block input generation
- exit-timing sensitivity side-block passthrough
- downside meta risk-margin score input generation
- stateful floor meta selector diagnostics
- post-exit path diagnostics and cooldown no-replacement estimates
- isolated exit-capture diagnostics and fixed-horizon replacement grid
- chronological hold-extension target model diagnostics
- stateful hold-extension replay and selector-compatible monthly metrics
- side-aware fixed-horizon hold-extension replay

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
- global expanding loss-first quantileをtotal改善だけで採用すること
- raw `loss_exit30_cd15` の残存損失を単純なentry方向問題として扱うこと
- single month/contextのworst tradeから静的blacklistを作ること
- prior exit-capture riskをhard blockとして使うこと
- historical capture factorをentry scoreへ直接掛けること
- selected-trade supervised shrinkageを低score gateとして直接使うこと
- supervised shrinkage scoreをmain entry scoreへ直接置き換えること
- expected-downside meta scoreを単純threshold hard blockとして使うこと
- expected-downside meta scoreをentry scoreへ直接足し引きすること
- broad post-loss cooldownを標準policyにすること
- post-exit no-replacement estimateをstateful policy evidenceとして扱うこと
- fixed 60/240/720mの一律置換を標準policyにすること
- actual fixed-horizon replacementを実行可能policy evidenceとして扱うこと
- no-replay hold-extension replacement estimateをstateful policy evidenceとして扱うこと
- default `isolated` / `all` hold-extension trainingをfloor悪化のまま標準化すること
- hold-extension total改善だけでmonth floor未達の候補を標準化すること
- future-label `isolated_large_loss_capture_failure` を実行可能policy evidenceとして扱うこと
- low threshold / fixed 720を全isolated large-lossへ広げること
- target_best_deltaが `0.0` の損失をhold-extensionで直そうとすること

## 次にやること

1. hybrid 2025-12 short `-4.1460` をentry/no-entry、early stop、short-side blockの3方向で診断する。
2. その損失が観測可能特徴量で事前識別できるかを、target-month-independentに確認する。
3. `isolated_large_loss_long + fixed720 + threshold -5` はdiagnostic branchとして維持し、標準policyにはしない。
4. 新しいshort-loss対策をstateful replayと00286 selectorへ戻す。
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
22. `00279_2026-07-02_entry_ev_loss_first_global_expanding_quantile.md`
23. `00280_2026-07-02_entry_ev_raw_cd15_residual_loss_diagnostics.md`
24. `00281_2026-07-02_entry_ev_capture_shrink_overlay.md`
25. `00282_2026-07-02_entry_ev_selected_trade_supervised_shrinkage.md`
26. `00283_2026-07-02_entry_ev_supervised_shrinkage_policy_inputs.md`
27. `00284_2026-07-02_entry_ev_downside_meta_block_inputs.md`
28. `00285_2026-07-02_entry_ev_downside_meta_risk_margin.md`
29. `00286_2026-07-02_entry_ev_stateful_floor_meta_selector.md`
30. `00287_2026-07-02_entry_ev_post_exit_path_diagnostics.md`
31. `00288_2026-07-02_entry_ev_isolated_exit_capture_diagnostics.md`
32. `00289_2026-07-02_entry_ev_hold_extension_target_model.md`
33. `00290_2026-07-02_entry_ev_hold_extension_stateful_replay.md`
34. `00291_2026-07-02_entry_ev_hold_extension_side_horizon_replay.md`
