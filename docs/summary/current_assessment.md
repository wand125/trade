# Current Assessment

最終更新: 2026-07-02 14:40 JST

## 結論

標準採用できる利益最大化policyはまだない。

現在の標準判断は NoTrade-first。候補policyは、複数chronological window、role/month PnL floor、trade support、side balance、NoTrade比較を通らない限り標準化しない。

直近で最も進んだ候補は exit-regret系から、capture-adjusted score上のcoarse side/regime tail-risk headへ移ったが、外部HGB chronologyで弱い再現に留まった。`00258` で `confidence_exit t0.4` selectorがbroad/fixed2025を改善し、`00261` でreplacement guard replayも改善した。ただし `00262` のNoTrade-first admissionでは strict / relaxed ともNoTrade。`00263` でfresh2024 0-tradeの主因はpost-block `side_gap_pct` 汚染と分かり、`00264` でpre-block side-gap quantileを実装した。`00265` では追加refit rowsのtailを分解し、`00266` では前月までの `direction_regime` 損失で q99/floor5 の追加rowを止める余地を確認した。`00267` でこれをstateful replayへ接続し、q99/floor5はoverall `+55.6750` まで改善したが、標準strict/relaxed admissionはrole trade support不足でNoTradeのまま。`00269` では外部HGB preflightに固定適用し、supportはあるがoverall `-9.5756` でNoTrade未満。`00270` では外部HGB+MLP hybrid 2025-09..12にも固定適用し、q99 `-28.3940`, q95 `+0.0820` だがmonth floor未達でNoTradeだった。`00271` ではその損失を教師/特徴量設計の観点で分解し、同方向oracle利益を実行exitで取り逃すexit-capture failureとEV過大評価が中心だと確認した。`00272` では既存executable EV補正をpost-selector scoreに掛けたがNoTrade未満。`00273` ではselector前base scoreへ移してq95 `-12.1040` まで戻したが、まだNoTrade未満だった。`00274` では `direction_regime` tail-riskを重ねるとq99が `+3.1260` まで改善したが、3 trades / all-long / month floor未達でadmissionはNoTradeだった。`00275` で外部HGBへ固定適用すると、bestはoverall `-9.1956` と00269比 `+0.3800` の小幅改善に留まり、標準化を支持しなかった。`00276` でexit timingへ戻り、低いloss-first dynamic exit thresholdを検証した。HGB単体では q95 + `loss_exit20/25` がgateを通ったが、hybridでは最良閾値が `0.35` 付近へずれた。統合では q95 + `loss_exit30` が total `+44.5308`, role min `+2.6780`, positive roles `3/3` まで改善したが、month min `-4.1460` が残った。`00277` で q95 + `loss_exit30` を内部chronologyへ再探索なしで固定適用し、base `-14.6536` から `+67.5682` へ改善、00276外部と統合して total `+112.0990`, positive roles `6/6` になった。ただし month min `-11.3450` と追加entry負けが残った。`00278` でdynamic exit後cooldownを追加し、q95 + `loss_exit30_cd15` は内部+外部統合 total `+118.6900`, positive roles `6/6`, month min `-6.8324`, trades `266` へ改善した。ただしmonth floorはまだ負、fresh/hybrid supportも薄いため標準採用はしない。`00279` でraw `0.30` をglobal expanding loss-first quantileへ置き換えたが、best totalの `lfq60_cd15` は total `+135.3536` でも positive roles `4/6`, month min `-28.9404` で崩れた。`00280` で raw `loss_exit30_cd15` の残存損失をprediction文脈へjoinして分解し、loss trade 122件 `-229.4220` のうち no-edge entryは3件 `-34.6800` だけ、119件 `-194.7420` は同方向oracle利益ありと確認した。`00281` ではprior exit-capture risk、executable EV calibration、direct score shrinkを検証し、hard blockもdirect multiplicative shrinkもraw benchmarkを下回ると確認した。`00282` ではselected-trade supervised shrinkageがraw/prior calibrationよりMAEを改善するが、rank/gateとしては勝ちtradeを削ると確認した。`00283` でshrinkage headをprediction row側へ戻し、q95 no-floor + `loss_exit30_cd15` は total `+219.7158` まで伸びたが month min `-35.1586` でraw cd15より悪化した。`00284` ではraw cd15 scoreを維持し、shrinkage outputを補助featureにしたdownside meta hard blockを試したが、`gte1` はbaseline `+118.6900` から `+15.4886` へ悪化し、`gte3` はbaseline同等のno-opだった。`00285` ではsoft risk marginを試したが、best totalの `w0.25` も `+23.7938` でbaselineを大きく下回った。`00286` でcandidate-level stateful floor selectorを追加し、現候補群はfloor-only条件でもNoTradeと確認した。次はscore gatingではなく、raw cd15 losing monthsのexit timing / cooldown / post-exit re-entry path改善へ進む。

`00287` でraw cd15のpost-exit pathを分解し、`prev_loss` 後tradeは `+122.9292` と強く、単純なpost-loss cooldown拡張は勝ちを削ると確認した。次はscore gatingやentry削除ではなく、初回/孤立大損と前回勝ち後の大損に対するexit-capture改善へ戻る。

`00288` で isolated large-loss capture failure 23件 / `-125.5752` を特定した。22/23件はoracle best holdが実exitより後で、hold-extension targetとして濃い。ただしfixed 60/240/720mの一律置換はtotalを伸ばしてもmonth floorを悪化させるためreject。次はfixed-horizon/hold-extension choiceをchronological supervised targetとして学習し、prediction-row featureとしてstateful replayへ戻す。

`00289` で fixed-horizon / hold-extension choiceをchronological supervised targetとして学習した。default `isolated` 学習や `all` 学習はmonth floorを壊したが、`train_universe=isolated_loss` で exit時点観測可能な `isolated_large_loss` にthreshold 5を適用すると、no-replay診断では flagged 7 trades、actual replacement delta `+128.0630`、total `+246.7530`、month min `-6.8324` になった。ただし2025-09/2025-06/hybrid 2025-12の負け月は未改善で、no-replay置換はstateful policy evidenceではない。次はexit-time hold-extension hookへ接続し、00286 selectorでfull stateful replayする。

`00290` でこのhold-extension候補をstateful replayへ接続した。`isolated_large_loss` threshold 5は延長中の後続base trade skip込みでも total `+250.7350`, delta vs base `+132.0450`、extended 7、skipped 8、skipped PnL `-3.9820` で改善を維持した。ただし month min は `-6.8324` のままで、strict selectorもfloor-only selectorもNoTrade。未改善の2025-09/2025-06は、実際にはfixed horizonで大きく改善するlong lossがあるがpredicted deltaがthreshold未満で、hookではなくmodel recall/calibrationが次の課題。

`00291` でside-aware fixed-horizon replayを追加した。`isolated_large_loss_long` + fixed `720` + threshold `-5` は total `+318.8540`, delta vs base `+200.1640`, month min `-4.1460` まで改善し、00290で残った2025-09/2025-06 long lossを一部拾えた。ただし strict/floor-only selectorはいずれもNoTradeで、残るworstはhybrid 2025-12 short `-4.1460`。この損失は00290診断上 `target_best_delta=0.0` でhold-extensionでは直せないため、次はentry/no-entry、early stop、short-side blockの診断へ移る。

`00292` で既存stateful pathへ観測可能featureをjoinするentry-block no-replacement overlayを追加した。hybrid 2025-12のproblem short 1件を `short_rollover_lossprob_ge0p4` などの狭い条件で除去すると、best side-horizon candidateは total `+323.5700`, month min `-2.4566` まで改善した。ただし1件blockで過学習リスクが高く、strict/floor-only selectorもNoTrade。次はrefit2025 2025-03/08の残存floorを診断する。

`00293` でrefit2025 2025-03/08と2025-08の残存floorを診断し、London short mid-loss block、hold-extension false-positive block、00292のshort rollover blockを合成した。best comboは total `+329.4348`, role min `+0.5354`, month min `-0.7200` まで改善し、refit2025 2025-03は `-2.4566 -> -0.4730`、refit2025 2025-08は `-2.1480 -> 0.0000` になった。ただし24件blockのno-replacement overlayで、strict selectorは `month_pnl_below_floor,role_trades_low,month_trades_low,side_share_high`、floor-only selectorも `month_pnl_below_floor` によりNoTrade。remaining sparse negative monthsを単発blacklistで追わず、full stateful policyへ昇格できる構造か確認する。

`00294` で00293 best branchのremaining negative monthsをunblocked tradesだけで診断した。4 negative monthsのうち3件は1 trade monthかつside share `1.0`。refit2025 2025-03だけは9 tradesだが、主損失 short `down_normal_vol / ny_overlap` はfixed 60/240/720mでさらに悪化し、同contextは全体では `+19.5636`。したがって次の改善軸は追加entry-blockではなく、support-aware admission diagnosticsと、hindsight fixed-horizon rescueをchronological policyに戻せるかの検証。

`00295` でsupport-aware admission diagnosticsを追加した。月次floor breachを support-limited / shallow / structural に分けると、00293 best branchはdefault設定では structural negative month `0` で `support_aware_only` になる。ただしsupport-limited負け月許容を3から2へ下げる、またはshallow floorを `-1.0` から `-0.25` へ厳しくするとblocked。これは標準化ではなく、失敗種類を分ける診断層として使う。

`00296` でsupport-aware分類を raw cd15 -> hold-extension -> side horizon -> entry block -> residual combo の候補系列へ横断適用した。default条件で `support_aware_only` になるのは00293 residual comboだけで、raw cd15/00290/00291/00292はstructural negative monthsまたはsupport-limited負け月過多でblocked。候補系列はtotalだけでなくfailure typeをstructuralからthin-support residualへ移している。ただし00293 bestもsupport2/shallow025感度ではblockedなので、標準policyはNoTradeのまま。

`00297` で月内サポート形成を待つmonth-warmup overlayを追加した。00296 diagnostic benchmarkに対して `skip_first_1` は1-trade negative monthsを消すが、total `+329.4348 -> +275.3470`、month min `-0.7200 -> -1.9596` へ悪化。`wait_opposite_seen` / `wait_both_sides_seen` はさらにtotal/role/month floorを壊した。month-warmup diagnosticsは採用するが、現warmup rulesはreject。thin-support residual monthsを広い月初削除で解く方向は本流にしない。

`00298` でconfidence gate overlayを追加した。`taken_ev_ge10` は month minを `0.0000` まで上げるが、total `+36.0280`、trades `111` へ落ち、standard blockersは `role_trades_low,month_trades_low`。rank/side-gap/lossprob/fixed-horizon predicted PnL gateはmonth/role floorを悪化。feature binでも `pred_taken_ev` 高位binが強いわけではなく、現confidence特徴は直接hard gateではなくchronological calibration / uncertainty診断へ回す。

`00299` で00293 residual combo branch上のunblocked selected tradesを対象に、chronological OOF expected PnL calibrationを再診断した。raw EVは実績平均 `+1.4200` に対してscore平均 `+10.1991`, MAE `10.7256` と過大評価が大きいが、OOF補正後は factor EV MAE `2.9448`, PnL EV MAE `3.0165` まで縮んだ。一方でSpearmanは factor `0.1329`, PnL `0.1072` と低く、factor `< 0` gateも `+7.8728` の小幅改善に留まる。PnL低score gateは勝ちtradeを削るため、直接hard gateはreject。calibration scoreはuncertainty / regime diagnostics / admission explanationへ回す。

## 現在の判断

| 項目 | 判断 |
|---|---|
| Standard policy | なし。NoTrade-firstを維持 |
| Current diagnostic candidate | q95 + raw `loss_exit30_cd15` dynamic exit cooldown + side-aware hold-extension + residual combo entry-block overlay diagnostic。`isolated_large_loss_long + fixed720 + threshold -5 + short rollover / London mid-loss / hold-extension false-positive block` は total `+329.4348`, role min `+0.5354`, month min `-0.7200`。00296の候補系列比較でもdefault support-awareで通る唯一のbranchだが標準ではNoTrade |
| Why not standard | 00293 bestもmonth min `-0.7200` でNoTrade-first floorを通らない。00296で進歩は確認したがsupport-aware passはsupport2/shallow025感度で落ち、00297のmonth-warmupも00298のconfidence hard gateも標準gateを通らない。00299のOOF calibrationはscale errorを縮めるがrank/gate品質は弱い。strict blockers `month_pnl_below_floor,role_trades_low,month_trades_low,side_share_high` が残る |
| Useful signal | exit-regret / loss-first dynamic exit / replacement-stateful-net / same-side missed loss / low-capture loss / isolated large-loss capture failure / fixed-horizon improvement target / chronological hold-extension predicted delta / side-aware fixed horizon replay / stateful extension skip impact / selected-side capture ratio / short rollover loss-first block diagnostics / London short mid-loss block diagnostics / hold-extension false-positive block diagnostics / overlay residual floor support diagnostics / support-aware admission diagnostics / support-aware progression comparison diagnostics / month-warmup overlay diagnostics / confidence gate overlay diagnostics / confidence feature-bin diagnostics / chronological selected-trade calibration diagnostics / supervised shrinkage and downside meta features |
| Main risk | 勝ちtrade削除、only-candidate replacement悪化、high-score losing tail、May/September tail、q99/q95 same-window selection、support緩和によるrole PnL崩壊、別familyでのPnL再現不足、no-replay改善をpolicy evidenceと誤読すること、1件/少数件blockを堅牢なedgeと誤読すること、extensionで直せない損失へextensionを無理に当てること、remaining sparse negative monthsを単発blacklistで追うこと、hindsight fixed-horizon rescueを実行可能policyと誤読すること、support-aware diagnostic passを標準admissionと誤読すること、month-warmupのsupport-aware passを改善と誤読すること、confidence gateの低活動floor改善を標準候補と誤読すること、calibration MAE改善をadmission改善と誤読すること |

## 研究レーン

| レーン | Reports | 現状 |
|---|---|---|
| Short budget / side drift | `00174`..`00207` | budget0とside drift guardはtailを縮めるが、same-family / 2024 chronologyで標準化できず診断baseline止まり。 |
| Entry EV admission | `00208`..`00224` | raw/calibrated EV、rank、quantile、positive floor、hold-capを検証。NoTrade-first selectorは通らない。 |
| Executable EV / capture | `00225`..`00232` | executable EVやdense captureはrow-level改善があるが、stateful validationでtailとsupport不足が残る。 |
| Side balance / composite | `00233`..`00239` | side-balanceやcomposite hard gateでは候補が生まれず、component targetへ分解。 |
| Component / exit-regret | `00240`..`00299` | EV overestimateからdirection/exit/replacementへ分解。00267でq99 prior guardがstateful replay上は改善したが、標準admission未通過。00268でfresh support不足はepisode集中であり、rank0緩和はcal/refitを壊すと確認。00269の外部HGB、00270の外部full-hybridでもNoTrade未満。00271で損失はno-edgeではなくexit-capture failure / executable EV過大評価に寄ると確認。00272でpost-selector executable scoreは負の対照としてreject。00273でselector前capture補正もNoTrade未満。00274でcoarse `direction_regime` tail-riskはq99をプラス化したが、support/side集中でNoTrade。00275で外部HGB再現は弱く、tail-risk headはdiagnosticへ降格。00276/00277でlow loss-first dynamic exitが全role positiveまで進み、00278でcooldownが過剰回転を抑えた。00279のglobal quantile化はtotal改善と引き換えにtail/roleを壊し、policy候補にはしない。00280でraw cd15の残存損失はentry無価値ではなくexit-capture / EV過大評価が中心と確認。00281でprior capture factorのhard block/direct shrinkはreject。00282でsupervised shrinkageはscale補正として有効だが、direct gateはreject。00283でprediction-row shrinkage inputはaccepted、score replacementはreject。00284でdownside meta hard blockはreject、00285でdownside soft marginもreject。00286でstateful floor selectorを追加し、現候補群は全てNoTrade。00287でpost-exit pathを分解し、broad post-loss cooldownは勝ちを削ると確認。00288でisolated large-loss capture failureを特定し、一律fixed horizonはfloor悪化でreject。00289でhold-extension choice targetを学習し、`isolated_loss` training + `isolated_large_loss` threshold 5を次のfull replay候補にした。00290でstateful replayに接続しtotal改善は維持したがmonth floor未達でNoTrade。00291でside-aware fixed 720mはtotal/floorを改善。00292でhybrid 2025-12 shortをentry block overlayで消し、00293でrefit2025 2025-03/08 residual floorも縮めた。00294で残存floorはthin support中心と確認し、00295でsupport-aware admission診断へ分解。00296で候補系列横断でも00293だけがdefault `support_aware_only` だが、感度で落ちるため標準policyはNoTrade。00297でmonth-warmupはreject。00298でconfidence hard gateも低活動化またはfloor悪化でreject。00299でOOF calibrationはscale補正に有効だが、direct hard gateはreject。 |

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
- stateful entry-block no-replacement overlay diagnostics
- residual floor combo entry-block overlay diagnostics
- overlay residual floor support diagnostics
- support-aware admission diagnostics
- support-aware progression comparison diagnostics
- month-warmup overlay diagnostics
- confidence gate overlay diagnostics
- confidence feature-bin diagnostics
- residual combo selected-trade calibration diagnostics

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
- 1件だけを拾うentry block ruleを標準policyとして扱うこと
- no-replacement entry block overlayをfull stateful replacement replayとして扱うこと
- residual combo blockをmonth floor未達のまま標準policyとして扱うこと
- remaining sparse negative monthsを単発blacklistで追うこと
- hindsight fixed-horizon rescueを実行可能policy evidenceとして扱うこと
- 全体プラスのcontextを残存1件lossだけでblockすること
- support-aware diagnostic passを標準admissionとして扱うこと
- support-aware progression passを標準admissionとして扱うこと
- month-warmupのsupport-aware passを改善として扱うこと
- broad month-warmup ruleでthin-support residual monthsを解こうとすること
- confidence gateの低活動floor改善を標準候補として扱うこと
- raw predicted EV / rank / side-gap hard gateを標準policyとして扱うこと
- selected-trade OOF calibrationのMAE改善を標準policy improvementとして扱うこと
- direct calibrated PnL / factor EV hard gateを標準policyとして扱うこと

## 次にやること

1. support-aware分類を今後の候補比較に使うが、通過だけで標準化しない。
2. `support_aware_only` 候補は標準policyにせず、unused chronologyまたはmodel-level calibration reasonが出るまでNoTradeを維持する。
3. `isolated_large_loss_long + fixed720 + threshold -5 + residual combo block` はdiagnostic branchとして維持し、標準policyにはしない。
4. thin-support residual monthsはbroad month-warmupやconfidence hard gateではなく、unused chronologyまたはchronological calibration側で確認する。
5. calibration scoreはgateではなくuncertainty / regime diagnostics / admission explanationへ使う。
6. fixed-horizon rescueを試す場合は、hindsight deltaではなくchronological prediction/selector replayへ戻す。
7. role trade support、role PnL、month floor、side share、NoTrade-first比較を標準採用ゲートとして維持する。

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
35. `00292_2026-07-02_entry_ev_stateful_entry_block_overlay.md`
36. `00293_2026-07-02_entry_ev_residual_floor_combo_overlay.md`
37. `00294_2026-07-02_entry_ev_overlay_residual_floor_diagnostics.md`
38. `00295_2026-07-02_entry_ev_support_aware_admission.md`
39. `00296_2026-07-02_entry_ev_support_aware_progression_compare.md`
40. `00297_2026-07-02_entry_ev_month_warmup_overlay.md`
41. `00298_2026-07-02_entry_ev_confidence_gate_overlay.md`
42. `00299_2026-07-02_entry_ev_residual_combo_selected_trade_calibration.md`
