# Current Assessment

最終更新: 2026-07-03 21:28 JST

## 結論

標準採用できる利益最大化policyはまだない。

現在の標準判断は NoTrade-first。候補policyは、複数chronological window、role/month PnL floor、trade support、side balance、NoTrade比較を通らない限り標準化しない。

00360/00362時点では、残targetの候補生成不足は同一原因ではない。`fresh2024 2024-11 long` はrole/month rowが1件あるが `available_candidates` が0で、`greedy_selected` の1行だけがrelaxed条件で候補になるrow-scope/candidate availability問題。`refit2025 2025-03 short` は00322 base / 00358 rankerのpost-00318 feedでは0件だったが、00362のupstream監査でraw prediction rows `28,972`、short side rows `28,972`、candidate rows `41`、available `33` が存在すると分かった。直接原因は `extra_short_needed=0` / `extra_long_needed=0` でrepair targetが発行されないこと。これはraw universe coverage不足ではなく、support-sufficient negative monthのrepair-target objective mismatchとして扱う。`fresh2024 2024-03` と `fresh2024 2024-08` は00358 ranker上ではavailable supportがあり、candidate generationではなくcalibration / horizon choice問題として扱う。

00361時点では、`fresh2024 2024-11` の入口は `selected_onefail_replacement` として作れるが、global wideningは危険。00358 rankerのselected one-fail replacementは8行あり、strict choices 6件 / actual sum `-83.4028`、relaxed choices 8件 / `-68.0198`。したがって selected one-failはtarget-aware replacement / horizon-calibration診断として扱い、標準policyへglobal適用しない。

00362時点では、`refit2025 2025-03` へthin-support候補を追加する方向は本流ではない。同月はcurrent trades `9`、side mix `5L / 4S`、PnL `-0.4730` で、side/trade supportは足りている。次は既存tradeのreplacement、early exit、exit timing、EV過大評価補正を扱うsupport-sufficient negative-month repair laneを分ける。

00363時点では、support-sufficient negative-month repair laneの初回診断を追加した。`refit2025 2025-03` はloss trades 4本 / loss PnL `-3.4800` で、事後oracleではloss全skip `+3.0070`、single worst skip `+1.8670`、single fixed-best exit repair `+4.1230`、top-score replacement `+4.2170` まで改善余地がある。ただし現predicted fixed-horizon argmaxはsingle bestでも月PnL `-8.8574` へ悪化するため、exit selectorとしてreject。次はloss-risk classifier、horizon abstention、target-aware replacement selectorが本流。

00364時点では、support-sufficient negative monthのloss-risk priorを診断した。対象月だけなら `lossfirst_ge0p40_or_ev_ge5_lossfirst_lt0p30` が4/4 lossを捕捉し、target flagged PnL `-1.5900`、skip delta `+1.5900` になる。ただし全240 selected tradesでは176 tradesをflagし、flagged PnL `+332.3394`。`ev_ge5_lossfirst_lt0p30` / `side_gap_ge0p15_lossfirst_lt0p30` も対象short損失2本を拾うが、全体 flagged PnL はそれぞれ `+284.9458` / `+210.1174`。したがってdirect block / hard gateはrejectし、loss-riskはreplacement selector、horizon abstention、expected PnL calibrationの補助featureに回す。

00365時点では、loss-riskをhorizon abstentionへ回す診断を追加した。全240 selected tradesでpredicted fixed-horizon argmaxを全採用するとextension deltaは `-221.4806`。`refit2025 2025-03` ではcurrent month PnL `-0.4730` が `-50.9070` まで崩れる。`lossfirst_ge0p40_or_pred_best_ge5_or_ev_lowlf` はtarget harmful horizon 7/7を止め、target extension delta `-50.4340 -> +26.1200`、全体でも `-221.4806 -> +207.3556` へ反転した。これはstateful replay candidateだが、selected-trade counterfactualであり、one-position constraint下のskip影響をまだ測っていないため標準policyにはしない。

00366時点では、00365のbroad ruleをstateful hold-extension replayへ戻した。`all / predicted / t-5` ではvetoなし total `+52.4794`, month min `-324.7062` から、ruleあり total `+267.8748`, month min `-32.9086` へ改善し、`refit2025 2025-03` も `-26.7670 -> +16.0670` へ改善した。一方、本線の `isolated_large_loss_long / fixed720 / t-5` では、vetoなし total `+338.4078`, month min `-0.8832` がbestで、ruleありは全8 extensionsを止めて raw base total `+139.1098`, month min `-6.8324` に戻る。したがって00365 broad ruleは探索的predicted-horizon安全診断として残すが、本線policy vetoとしてはreject。support-sufficient negative month向けにはreplacement selector / expected PnL calibrationを優先する。

00367時点では、support-sufficient negative monthのreplacement candidateをprior-calibrated expected PnLでrankする診断を追加した。`refit2025 2025-03` ではtarget月より前のprior rowsは `664` / prior months `2`。min prior count `20` の `bias_corrected` はmean month PnL `+22.1670`, best `+23.6370` まで伸びるが、`downside_bias_corrected` / `conservative` は `2025-03-31 short 720m` actual `-19.1604` を選びmean `-18.7634` へ悪化した。min prior count `50` では `prior_actual_mean` がmean `+18.3040`, best `+19.7740`、`bias_corrected` がmean `+8.0640` で、support thresholdの重要性が確認できた。全choiceは `one_failed_strict_stage` なので標準policyではないが、replacement selector featureとしては有望。

00368時点では、00367のreplacement selectorをloss-risk selectorと接続し、全current tradesからobservable risk selectorで外す1本を選ぶsurfaceへ進めた。`feature:side_gap_ge0p15_lossfirst_lt0p30` は `2025-03-21 14:00 short -2.3400` を選び、min prior month `2` / prior count `>=50` / prior actual mean `>=0` でも `bias_corrected` replacementでmonth PnL `+22.4970`、`prior_actual_mean` で `+19.7740` まで残る。一方、`combined:any_lossrisk` や `score:loss_first_prob` はwinner `2025-03-31 03:40 short +1.3800` を外すため、broad risk aggregationはまだ危険。min prior month `3` では候補0で、prior span不足も明確。selector surfaceはaccepted infrastructureだが、単一target月・one-fail依存なので標準policyではない。

00369時点では、00368をauto target化して対象母集団を確認した。現00314/00318 branchのnegative monthは4件だが、support-sufficient negative monthは `refit2025_validation 2025-03` の1件のみ。`fresh2024 2024-03`, `fresh2024 2024-11`, `hybrid2025_0912 2025-11` はsupport-limited negative monthで、side/trade supportの別目的が必要。したがってsupport-sufficient selector surfaceは現branch単体ではtarget count 1のinfrastructureであり、標準policy evidenceにはならない。次は他branch/variantでsupport-sufficient targetを探すか、support-limited laneを分けて扱う。

00370時点では、過去のselector monthly metrics全体からsupport negative monthを棚卸しした。17件のmetricsを読み、inventory rows 29,371 / negative rows 9,491 / support-sufficient negative rows 5,065 / support-limited negative rows 4,426。target identityは20件で、support-sufficient configを持つtargetは14件、support-limited onlyは6件。現branch以外にはsupport-sufficient target候補がある。ただしconfig rowsはvariant/parameter重複を含むため独立サンプルではなく、policy evidenceではなくtarget選定用の地図として扱う。次はcanonical support-sufficient target setを作り、00368/00369のselector surfaceを複数targetへ広げる。

00371時点では、00370 inventoryからcanonical support-sufficient target setを作り、selector surfaceを複数targetへ広げた。support-sufficient config数 `>=50`、metric parent数 `>=5` で11 targetを選び、現00314/00318 configで10 targetを評価した。評価対象10件のbaselineは9件がpositiveで、negativeは `refit2025 2025-03` だけ。non-oracle bestの `combined:any_lossrisk` + `bias_corrected` はmean delta `+12.3633` だが、loss selected 3件 / winner selected 7件でwinner damageが大きい。`side_gap_ge0p15_lossfirst_lt0p30` もwinner selected 5件で、`hgb2024_0306 2024-05` を `+0.9578 -> -19.3690` へ悪化。したがってtarget inventory injectionはinfrastructureとして採用するが、現risk selectorは標準policy化しない。次はcurrent-branch negative repairとcross-artifact robustnessを分けて評価する。

00372時点では、00371 surfaceをwinner-damage制約でpost-processした。制約はloss precision `>=0.5`、winner selected 0、baseline-positive degradation 0、current-negative delta `>=0`。16 surface rowsで通過は0件。非oracleの `ev_ge5_lossfirst_lt0p30` はprecision `0.5556` だがwinner selected 4件、`combined:any_lossrisk` はprecision `0.3000` / winner selected 7件、`side_gap_ge0p15_lossfirst_lt0p30` はprecision `0.2857` / winner selected 5件。`oracle:worst_loss` でも `hgb2024_0306 2024-05` を `+0.9578 -> -11.7730` へ反転させるため、replacement selection/calibrationも未解決。winner-damage diagnosticsは採用するが、現risk selector / replacement selectorは標準policy化しない。

00373時点では、00372のwinner-damage制約をselector surface本体のsummary rankingへ直接組み込んだ。`loss_selection_precision`、winner selected、baseline-positive degradation、current-negative delta、違反数、合否列を出力し、mean PnLより制約pass / violation countを優先して並べる。00371と同じcanonical target setでは16 rows中通過0件。最小違反はoracle系で、loss precision 1.0 / winner selected 0 / current-negative delta positiveだがbaseline-positive degradationが1-3件残る。非oracleでは `ev_ge5_lossfirst_lt0p30` がprecision `0.5556` を満たすがwinner selected 4件。結論は00372と同じで、現risk selector / replacement selectorは標準policy化しない。次はbaseline-positive degradationを起こすreplacement abstention/calibrationを診断する。

00374時点では、replacement candidateを通す/捨てるabstention gateをsurface上で診断した。候補を捨てた場合はbaseline維持に戻し、winner damageは実際にreplacement interventionしたtradeだけで数える。`abstain_all_replacements` は16/16 rowsで制約を通るが改善0。observable gateでは `prior_actual_mean >=25` / `prior_margin >=0` などで非oracle通過行が出た。代表例は `feature:side_gap_ge0p15_lossfirst_lt0p30` + `prior_actual_mean` + candidate prior count `>=100` + abstention `prior_actual_mean >=25` で、`refit2025 2025-03` のlossだけへ介入しcurrent-negative delta `+20.2470`、mean delta `+2.0247`、winner intervention 0、baseline-positive degradation 0。`hgb2024_0306 2024-05` は介入せずbaseline維持になる。これはdiagnostic candidateだが、実質1 current-negative targetへの介入なので標準policy化しない。

00375時点では、00374のabstention gateを広いsupport-sufficient target集合へstressした。inventory条件を `support_sufficient_config_count >=1`、`metric_parent_count >=2` へ緩め、13 evaluated targetsになった。追加評価は `hgb2024_0306 2024-06`、`hgb2025_08 2025-08`、`cal2024 2024-01`。winner-damage ranking単体は通過0件で、nonoracle loss precisionは悪化した。abstention後は `side_gap` + `prior_actual_mean` + `prior_actual_mean >=25` が引き続き通過したが、介入は同じ `refit2025 2025-03` の1件のみで、追加3targetはbaseline維持。つまりgateは広い集合でも壊れなかったが、複数targetで効いた証拠ではない。次はcurrent-negative evaluated targetを増やせる別branch/artifact configを探す。

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

`00300` で00299 calibration residualをcontext / support / score binへ分解した。`short|ny_late` は17 trades / total `-13.0136`、pnl bias `+2.4593`、large loss 5件。`long|range_normal_vol|ny_overlap` は9 trades / total `-12.5040`、overestimate rate `0.8889`、train rows平均 `160.8`、train months平均 `11.8` で、support十分でも外している。PnL score最低binは total `+144.3950` と強く、low-score gateが勝ちを削る理由も再確認した。危険contextは見えたが、同一branch上のpost-hoc static blacklistはrejectし、prior-only context residual pressure / uncertainty headへ戻す。

`00301` で対象月より前だけを使うprior residual pressureを作った。最良診断ruleは factor mode / `direction,combined_regime,session_regime` / `prior_count_ge5_lossrate_ge0p5_bias_pos` で、6 tradesをflagし flagged PnL `-10.8380`, kept PnL `+340.2728`, loss precision `0.6667`。ただし同じruleはPnL modeでは flagged PnL `+1.5620` と悪化し、広いdirection/session ruleは69 trades / flagged PnL `+152.2132` と勝ちを大きく削る。prior residual pressureはhard gateではなくfeatureとしてuncertainty / large-loss headやcandidate-level selectorへ入れる。

`00302` でprior residual pressureをlarge-loss headのfeatureとして試した。base特徴だけでは PnL AUC `0.6682`, AP `0.2146`、factor AUC `0.6741`, AP `0.1714` だが、base+priorでは PnL AP `0.1604`, factor AP `0.1532` に悪化。high-risk除去も全て悪化し、最小悪化の `factor base_prior prob_ge_0.4` でも2 trades / flagged PnL `+15.0000`。large-loss head infrastructureは残すが、現prior pressure feature追加とdirect risk hard gateはreject。次はpointwise gateではなく、candidate-level selector / stateful replay / path-aware labelへ進む。

`00303` で00302 large-loss head predictionsをpath-awareに分解した。実大損23件のうち、同じ `direction|combined_regime|session_regime` / month内でnet positiveに補償されたものは1件だけ。ただしrisk threshold除去は20本すべて悪化し、positive deltaは0本。最小悪化の `factor base_prior prob_ge_0.4` は2 trades / flagged PnL `+15.0000`、`pnl base prob_ge_0.2` は17 trades / flagged PnL `+58.1320`。`2025-11 short|down_normal_vol|london` は `-7.9800` large loss と `+62.0800` winnerが同context-monthにあり、context total `+54.1000`。結論は「大損が一般に補償される」ではなく、「risk scoreがwinner / positive context-monthも巻き込む」。次は `is_large_loss` ではなく `large_loss_uncompensated_by_context` / negative path contextを教師候補にする。ただし同月実現PnLは未来情報なので、実行時はprior-only context、candidate-level state、entry/exit featuresで代理する。

`00304` で `large_loss_uncompensated_by_context` を教師にしたchronological OOF headを追加した。best APは `pnl / source base / base` の `0.1463` で、00302 large-loss headのbest AP `0.2146` より低い。target rowの予測平均はbest `0.0774`、non-target平均 `0.0529` 程度で分離が弱い。threshold除去は160本すべて悪化し、positive block deltaは0本、最小悪化でも flagged PnL `+5.6900`。top predicted rowsは依然として2025-11 `short|down_normal_vol|london` の補償済みpairを拾う。target generationとhead infrastructureは残すが、現feature/headのdirect hard gateはreject。次はpointwise classifierを増やさず、candidate-level selector / stateful replayへ戻す。

`00305` でuncompensated targetをselected-trade path上のsequence/stateへ戻して分解した。`pnl/base/base` は232 trades / total `+329.4348` / target 22件で、targetは `>10` trade月に18/22、次trade勝ちに15/22、前回勝ち後に12/22、short側に16/22が集中した。high-risk threshold除去は96本すべて悪化し、positive block deltaは0本、最小悪化でも flagged PnL `+5.6900`。したがってtargetは「孤立した悪玉」ではなく、前後winnerや高密度pathに埋まっている。sequence-state diagnosticsはaccepted、uncompensated probabilityのdirect gateはreject。次はcandidate-level selector / stateful replayでreplacement / skipped next winner / missed future candidateを明示的に扱う。`next_*` は診断専用で、実行featureにはしない。

`00306` でrealized candidate path variantごとにuncompensated targetを比較した。00293 best branchは232 trades / total `+329.4348` / role min `+0.5354` / month min `-0.7200` / target 22件で、候補群内ではmonth floorが最良。target countとtotal PnLの相関は `+0.0502` と弱く、target countとmonth floorの相関は `+0.5674`。`t-5_hpredicted` はtarget 19件でtotal `+351.2472` だがmonth min `-23.5914`、`t-5_h720` no entry-blockはtarget 20件でもmonth min `-112.1634`。したがってtarget count最小化はreject。realized candidate-path diagnosticsはacceptedだが、full replacement replay evidenceではない。次は未選択entry candidate feedを使うstateful replacement replayへ進む。

`00307` で未選択entry candidate feedへ戻し、short entry-blockをprediction-row observable flagにしたうえで、side EV penalty replacement replayへ接続した。対象はshort側の `rollover_lossprob_ge0p4 OR london_midloss_sidegap_pos` で、00293 comboのうちhold-extension後にしか分からない `holdext_long_range_normal_ny` はまだ含めていない。raw `loss_exit30_cd15` 段階の合算では baseline `+118.6900` / 266 trades / month min `-6.8324` から replacement `+126.8118` / 254 trades / month min `-6.8324` へ `+8.1218` 改善した。hybrid 2025-12は `-4.1460 -> +4.5000` と強く改善した一方、internal+hgb側は `+112.0660 -> +111.5418` と小幅悪化し、refit2025 2025-09/02のmonth floorも未解決。prediction-row flag generationとside EV penalty replacement replayはaccepted infrastructureだが、全family一律short block標準化はreject。次はhold-extension state-dependent blockをfull replayへ戻すか、side-aware hold-extensionとreplacementを統合する。

`00308` で00307 replacement pathへhold-extension target / stateful replayを戻した。`--require-model-used` なしの `isolated_large_loss_long / t-5 / h720` は total `+307.7638` だが、replacementで生じた hgb2024_0306 2024-03 long tradeが `pred_hold_extension_model_used_720m=False` のfallback scoreでfixed720延長され、`-2.0400 -> -20.1840` となりmonth min `-17.6936` へ壊れた。`entry_ev_hold_extension_stateful_replay.py` に `--require-model-used` を追加し、実モデルが使われたhorizonだけを延長対象にすると、同branchは total `+326.1098` / month min `-0.8832` / role min `+0.5354`。さらに `holdext_long_range_normal_ny` blockで total `+326.9930` / month min `-0.7200`。00293 bestよりtotalは `-2.4418` 低いが、short blockを削除ではなくreplacementで処理する統合pathとして前進。次は `holdext_long_range_normal_ny` をpost-hold no-replacement blockではなく実行時proxy / extension vetoへ戻す。

`00309` で00308 branchをdefault/support2/shallow025のsupport-aware admissionで再評価し、post-hold block込みbestはdefaultで `support_aware_only` だが、support2では `too_many_support_limited_negative_months`、shallow025では `structural_negative_months` でblockedと確認した。さらに `--extension-veto-rules` を追加し、`holdext_long_range_normal_ny` を実行時extension vetoとして戻したが、対象tradeはbase exit `-2.5152`、fixed720 `-0.8832` なので、延長を止めると total `+326.1098 -> +325.2078`、month min `-0.8832 -> -1.7852` へ悪化した。post-hold blockの改善は「延長が悪い」ではなく「trade全体を削除した」効果だったため、extension veto proxyはreject。次はこのcontextをentry-time observableなposition-quality問題として扱う。

`00310` でentry-time observableなposition-quality proxyを検証した。`long_range_normal_ny_fixed60_pred_gt0` は `isolated_large_loss_long / threshold -5 / fixed720 / require-model-used` branchを total `+326.1098 -> +337.6010`、month min `-0.8832 -> -0.7200` まで改善した。ただしblocked 4件は全て `refit2025_validation` の `long / range_normal_vol / ny_overlap` に集中し、standard admissionは `month_pnl_below_floor,role_trades_low,month_trades_low,side_share_high` でblocked。default support-awareでは `support_aware_only` だが、support2では `too_many_support_limited_negative_months`、shallow025では `structural_negative_months` でblocked。entry-time proxy infrastructureはaccepted、`long_range_normal_ny_fixed60_pred_gt0` はdiagnostic candidate、標準policyはNoTrade。

`00311` で00310候補のholdout supportを確認した。refit2025をdiscovery、非refit rolesをholdoutに分けると、`long_range_normal_ny_fixed60_pred_gt0` は全体 +11.4912、discovery +11.4912、holdout発火0件 / delta `0.0000`。broader `long_range_normal_ny` はholdoutで2件発火し net +0.7370だが、cal loss 1件とhgb winner 1件を同時に削る。したがって00310候補は未使用chronology支持なし。holdout-support diagnosticsはaccepted、rule自体はhard blockではなく短期path過大評価feature候補へ戻す。

`00312` でfixed60 short-horizon overestimateをprior-only uncertainty featureへ戻した。`selected_fixed_60m_pred_pnl > 0` かつ `selected_fixed_60m_actual_pnl < 0` を診断targetにし、対象月より前だけのcontext priorから `prior_fixed_false_positive_rate`, `prior_fixed_overestimate_mean`, `prior_fixed_uncertainty_pressure` を生成した。細粒度 `family,direction,combined_regime,session_regime` の `prior_count_ge5_pnl_neg_fp_rate_ge0p4` は4 trades / flagged PnL `-11.4360` / final loss precision `1.0000` で00310のrefit集中blockをほぼ再現したが、非refit holdoutでは発火0件。fixed60 prior uncertainty diagnosticsはaccepted infrastructure、hard gateはreject、次はcandidate-level selector / uncertainty headのfeatureとして検証する。

`00313` で00312の `prior_fixed_*` をchronological OOF uncertainty headへ接続した。`fixed_false_positive` ではfine contextでAPが改善し、default categoricalでは `0.4642 -> 0.4765`、role/family/group_keyを外したnoroleでも `0.4616 -> 0.4816`。ただしhigh-risk threshold除去はPnLに変換されず、default `base_fixed_prior` top q95は flagged PnL `+62.0720`、norole top q95も `+7.5910` で勝ちtradeを削る。したがって `prior_fixed_*` はuncertainty featureとして有用だが、direct hard gateではなくsoft calibration / uncertainty marginへ回す。

`00314` でfixed60 uncertaintyをprediction-row soft marginへ戻した。selected-trade実績から対象月より前だけのfixed60 false-positive priorを作り、`margin_score = base_score - weight * prior_fp_rate * max(side_fixed60_pred_pnl, 0)` をlong/short両側へ追加した。重要な罠として、既存score kindは `preblockgap` side-gap quantileを継承しており、新score kindでside-gap quantileを再計算するとw0 no-op controlが baseline `+126.8118` を `+24.9388` へ崩した。`--side-gap-source-score-kind` でpreblockgap side-gapを継承するとw0はbaselineを再現した。raw replacementでは family-aware w5 が `+139.1098`、hold-extension後は `+338.4078`、position-quality overlay後は `+339.2910` / month min `-0.7200` まで改善し、00310同proxy `+337.6010` を上回った。ただしstandard admissionはblocked、default support-awareは `support_aware_only`、support2/shallow025ではblocked。diagnostic bestは更新したが、標準policyはNoTrade。

`00315` で00314 w5と00310 referenceのtrade set deltaを監査した。`entryblock_none` は `+326.1098 -> +338.4078`、差分 `+12.2980` だが、added 0 / removed 5 / common_changed 0。`long_range_normal_ny_fixed60_pred_gt0` は `+337.6010 -> +339.2910`、差分 `+1.6900` で、added 0 / removed 2 / common_changed 0。removedは全て `refit2025_validation` に集中し、00310でblockedされた4本のうち3本は00314ではw5 marginで先に候補集合から消えていた。したがって00314の改善源は理解できたが、非refit支持やsupport-limited negative month問題は未解決。trade-set delta diagnosticsはaccepted infrastructure、標準policyはNoTrade。

`00316` で00314 family-aware w5のrefit集中改善を、粗いpriorへ寄せても再現できるか検証した。fixed60 uncertainty marginに prior shrinkageを追加し、child `family,direction,combined_regime,session_regime` を parent `direction,combined_regime,session_regime` へ疑似カウントalphaで寄せた。w0 controlは baseline `+126.8118` を再現したが、best shrink raw replayは `s2_w5` の `+107.0324` / month min `-6.8324` で、00314 family-aware w5 raw `+139.1098` を下回った。prior shrinkage implementationはaccepted infrastructure、current shrinkage policyはreject、標準policyはNoTrade。

`00317` でsupport-limited negative months と side-share blockersをstandard admission repair targetへ分解した。00314 best overlayのmonth PnL不足は合計 `+2.1686` と小さいが、month support / side-shareを満たすには long `5` / short `3` の `8` extra trades が必要。00310 referenceと00314 w5は同じrepair targetで、00314はtotalを改善したがstandard-admission readinessは改善していない。repair target diagnosticsはaccepted infrastructure、標準policyはNoTrade。次はrow削除ではなく、thin monthへ反対側候補を追加/置換できるentry coverage / side-balance designへ進む。

`00318` でthin monthの反対側candidateをprediction rowsから診断した。strict条件では8 repair target中 `refit2025_validation 2025-08 short` の1件しか埋まらない。`one_failed_strict_stage` まで緩めると8 targetすべてに候補は存在するが、8本合計のfixed60実現は `-17.7984`、fixed240は `-31.7138`、fixed720は `-80.4158`。oracle bestだけは `+86.0590`。fresh2024の3ヶ月はscore floor `5` 未満のnear-missで、fixed60は `-14.1240`, `-11.0604`, `+0.3000`。thin-month opposite candidate diagnosticsはaccepted infrastructureだが、side-balanced support overlayはまだ標準候補にしない。次はnear-miss support candidate用のexit timing / EV calibration targetへ進む。

`00319` でnear-miss support candidatesをexit timing / EV calibration targetへ変換した。00318のgreedy selected 11本は、future-labelでfixed horizonを最適選択できればfixed-best合計 `+77.1400` だが、単純fixed60は `-26.4512`、fixed240は `-31.5870`、fixed720は `-46.0898`。現prediction parquetのfixed-horizon予測で選ぶと実現合計は `-6.8562`、one-fail strict 8本では `-41.1822` まで悪化する。available candidates 132本はfixed-best合計 `+572.2276`、oracle best `+1676.3210` とtarget poolは豊富だが、actual at predicted horizonは `-681.7860`。near-miss exit target diagnosticsはaccepted infrastructure、actual fixed-bestは教師labelとして有望だが、現predicted fixed horizon choiceはpolicy evidenceではなくreject。次はnear-miss pool用のchronological exit-viability / horizon headへ進む。

`00320` でnear-miss fixed-best targetをchronological exit-viability / horizon headへ接続した。default headはgreedy selectedで viability AUC `0.5556`、head選択horizonの実現平均 `-13.7712`、best thresholdでも `-17.8948`。available candidates側は全設定で大きく負で、bestでも `-232.0894`。available-only trainingはgreedy selectedのbest thresholdが `+3.1230` になるが、flagged 1件、`model_used=0` のfallback由来。chronological near-miss exit head infrastructureはacceptedだが、current PnL-regression argmax horizon selectorはreject。次はhorizon-specific binary viability / abstention-first decisionへ切り替える。

`00321` でhorizon-specific binary viability / abstention-first decisionを実装した。default runでは available candidates の60m executable AUCが `0.6635`、greedy selectedの240m executable AUCが `0.6167` と一部の識別力は出たが、tail-loss headは弱く、available candidates 60m tail-loss AUC `0.3225`、greedy selected 720m tail-loss AUC `0.3333`。threshold後の実PnLは全runで負で、default bestはgreedy selected `-36.8370`、model-used必須では `-39.9600`、available candidatesでは `-354.5204`。horizon-specific viability diagnosticsはacceptedだが、current direct horizon selector / near-miss support overlayはreject。次はdirect selectorではなくfeature化し、より広いcandidate universeでtail-loss / PnL calibrationを改善する。

`00322` でnear-miss-only headを広いprediction-row candidate universeで再学習した。s1 q90 broad trainingは4303 train rowsで、available candidatesのmodel-used raw bestが `+23.5350`、非重複後 `+14.8160`、greedy selectedはmodel-used raw `+16.8700`、非重複後 `+13.7800`。s2 q90 + one-failed trainingは9697 train rowsで、available candidatesはraw `+71.3850`、非重複後 `+18.4790`、greedy selectedはraw `+34.3230`、非重複後 `+20.5430`。一方、s3 score>=5 broad trainingは90447 train rowsでも available candidates raw `-40.6836`、非重複後 `-12.8676` と失敗した。broad candidate universe horizon viabilityとnon-overlap auditはaccepted infrastructure、q90 + one-failed trainingはdiagnostic candidate。ただしraw threshold PnLとoverlapping available choicesはstateful policy evidenceとして扱わない。

`00323` で00322 s2 outputを00314 best branchのsupport repairへ接続した。best totalは available candidates / prob `0.6` / EV `0` / tail `0.3` / model-used yesで、5本追加、added PnL `+23.4090`、combined total `+362.7000`。ただしmonth min `-0.6120`、remaining extra trades `3`、remaining month PnL hurdle `+1.4486` で、blockersは `month_pnl_below_floor,side_share_high`。EV `-2` は6本追加でremaining extra trades `2` まで縮めるが、refit2025 2025-07 short `-4.9356` を拾ってmonth min `-2.8532` へ悪化する。support-repair horizon replay infrastructureはaccepted、00322 s2 support additionsは標準policy / support overlayとしてreject。

`00324` で00323の残存target月を00322 s2 predictions上でcoverage分解した。`refit2025 2025-07 short` はavailable candidatesにfixed-best positive 3本、oracle non-overlap `+31.8900` があり、p0.5 / EV0 / tail0.3 / model-used yesで240m `+4.6900` を選べる。一方、`fresh2024 2024-03 long` はfixed-best positive 12本 / max `+13.4900` があるが、全horizonが `model_used=0` かつpredicted EV負で、require-model-usedを外しp0.3 / EV-2まで緩めると17 choices / `-137.9060`。`fresh2024 2024-11 long` は候補1本でactual 240m `+2.4500` だが、緩めると720m `-5.2800` を選ぶ。target coverage diagnosticsはaccepted、fresh2024側は単純threshold緩和で拾わない。

`00325` でtarget-aware repair utilityを00323 replayへ接続した。actual-floor diagnosticでは available candidates / p0.5 / EV0 / tail0.3 / model-used yesが5本追加、added PnL `+32.3700`、combined total `+371.6610` まで伸び、00323 bestから `+8.9610` 改善した。ただしmonth min `-0.6120`、remaining extra trades `3`、remaining month PnL hurdle `+1.4486` でstandard gateは通らない。さらにactual-floorはfuture realized PnLを使うためpolicy evidenceではない。pred-only対照ではfresh2024 2024-08 long 720m `-29.1360` を拾い、month min `-19.8260`、role min `-20.8016` へ悪化した。target-aware repair utility infrastructureはaccepted、pred-only repair_score replayはreject。次はpre-chosen horizonではなくrow x horizon候補をrepair utilityで採点する。

`00326` でprediction rowsからthreshold scenario gridを作り、60/240/720mを別候補としてrepairするrow x horizon replayを実装した。actual-floor upper-boundは6本追加、added PnL `+35.3200`、combined total `+374.6110`。pred-only / no horizon penaltyはfresh2024 2024-08 long 720m `-29.1360` を拾って `+3.2340` に留まるが、observable proxyのhorizon penalty `0.25` では同rowを60m `+2.9500` に切り替え、actual-floorなしでadded PnL `+35.3200` / combined `+374.6110` に到達した。ただし同一repair set上で見つけたduration penaltyで、`0.5/1.0` は良い長期候補も削るため、標準policyにはしない。次はduration risk / horizon choiceをchronological OOFでcalibrateする。

`00327` でhpen0.25をtarget monthより前の候補だけで選ぶchronological duration penalty calibrationを実装した。strict校正(min prior 10 rows / 2 months)もloose校正(min prior 1 row / 1 month)も、added PnL `+3.2340`、combined `+342.5250`、month min `-19.8260`、role min `-20.8016` でpred-only no-penaltyと同じ失敗に戻った。fresh2024 2024-08はprior候補0件で `0.00` fallbackとなり、悪い720m `-29.1360` を止められなかった。fallback0.25を事前固定すると00326 hpen0.25と同じ combined `+374.6110` を再現するが、これはlearned calibrationではない。chronological calibration infrastructureはaccepted、support-repair対象行だけでduration penaltyを学ぶ方針はreject。次は00322 broad candidate universeなど広いprior dataでduration riskを学習してsupport repairへ戻す。

`00328` で00322 s2 broad candidate universeをtrain rows付きで再生成し、target月より前のbroad rowsからcontext別duration priorを作った。fresh2024 2024-08の `long / down_low_vol / asia / one_failed` priorは48 rows / 6 monthsで、60m mean `+0.9061`、240m mean `+1.7885`、720m mean `-3.4993`、720m delta vs 60m `-4.4053`、tail-loss rate `0.4145`。悪い720mを事前に警告できる。ただしdirect penalty replayのbestはadded PnL `+23.7960`、combined `+363.0870` で00326 hpen0.25には届かない。p0.4系では2024-08を720m `-29.1360` から60m `+2.9500` へ切り替えられるが、勝ち候補も削る。broad duration prior infrastructureはaccepted、current direct penaltyはreject。次はpriorをfeatureとしてchronological horizon-choice ranker/headへ入れる。

`00329` でbroad duration priorを静的penaltyではなく、chronological horizon-choice ranker/headのfeatureとして使った。broad train rowsを60/240/720mのhorizon-level examplesへ展開し、target月より前だけで `pnl / delta_vs_60 / executable / tail_loss / beats_60` headを学習した。default complexityはbest added PnL `+29.2630`、combined `+368.5540` で00328 direct penaltyを超えたが00326 hpen0.25には届かない。tail強化だけでは `+364.4940` に悪化。低複雑度版 (`max_leaf_nodes=4`, `l2=5`) は5本追加、added PnL `+63.9770`、combined `+403.2680` まで伸びた。ただしmonth min `-0.6120`、role trade min `3`、remaining extra trades `3`、blockers `month_pnl_below_floor,role_trades_low,side_share_high` が残る。broad-prior horizon-choice ranker infrastructureとlow-complexity diagnostic branchはaccepted、標準policyはNoTrade。次はhorizon/context別prior residualからlower-bound scoreを作る。

`00330` でhorizon/context別prior residualからlower-bound scoreを作った。residual priorはtarget月より前のprediction errorだけで `bias / mae / rmse / overestimate_rate / tail_miss_rate` を計算し、`pnl_lower`, `pnl_delta_lower`, `pnl_delta_tail_lower` に入れた。公平な比較のため、residual prior列はデフォルトではranker featureに入れずscore-only / diagnosticsにした。strong penaltyは追加をほぼ消してbest combined `+339.2910`、light penaltyもbest `+376.8110` で00329 baseline `+403.2680` を超えず、tiny penaltyはほぼno-opだった。lower-boundは720mを抑えるが、現support-repair surfaceでは勝ち720mも大きく削る。chronological residual prior / lower-bound score infrastructureはaccepted、現weightのlower-bound scoreはpolicy候補としてreject。次はharmful overestimateとprofitable high-variance 720mを分離するtarget、およびthin month/supportを明示的にrewardする目的関数へ進む。

`00331` でharmful overestimate target diagnosticsを追加し、既存horizon-choice rankerへ `target_horizon_harmful_overestimate` classifier headを入れた。available candidatesのharmful head AUCは60m `0.8859`、240m `0.9391`、720m `0.8758` とsignalは出た。context splitでは720m `short/up_normal_vol/asia/one_failed` がharmful PnL `-330.4680`、720m `short/down_normal_vol/asia/one_failed` がprofitable HV720 PnL `+89.4930` で、global residual penaltyでは分離できないことを確認した。direct harmful penalty replayはweight 1 best `+397.3780`、weight 5 best `+394.7840` で00329 baseline `+403.2680` を超えない。harmful-overestimate target/head infrastructureはaccepted、direct harmful penaltyはreject。次はharmful probabilityをsupport-aware objectiveのfeatureとして使う。

`00332` でharmful probabilityをsupport-aware objectiveへ入れた。horizon-choice score側に `pnl_support_harmful_guard` 系modeを追加したが、bestは `+370.0040` で00329 baseline `+403.2680` を大きく下回った。support repair層にも `hv_chosen_pred_harmful_overestimate_prob`, `repair_support_success_proxy`, `repair_harmful_penalty_weight`, `repair_harmful_penalty_threshold` を追加したが、continuous penaltyはweight `0.1` 以上で勝ち候補を落として `+396.9280` へ悪化した。threshold `0.5/0.7` はbaselineを維持したが改善ではなくno-op。support-aware harmful objective infrastructureはaccepted、score-side / repair-side scalar harmful penaltyはreject。次は同一decision cluster内のpairwise/listwise switching targetとcontext別harmful calibrationへ進む。

`00333` でsupport repair pairwise/listwise switching診断を追加した。baseline best scenarioでは近傍代替がある選択候補は3本、pairwise examplesは22本だけだった。harmful probabilityが低い代替へ切り替えるruleは1件発火し、その1件はactual `-5.8900` の悪化。EV -2 scenarioでは72 pairsまで増えたが、harmful-lower switchは9 pairsすべて悪化しactual delta sum `-118.6696`。pairwise/listwise switch診断インフラはaccepted。ただし現selected-addition中心のsupport repair surfaceは学習policyにするには薄く、harmful-lower / tail-lower / support-proxy-higher switch ruleはreject。次はstateful selection前の広いgated候補を非重複cluster化し、listwise repair utility targetとcontext別harmful calibrationへ進む。

`00334` でstateful selection直前の広いgated候補面をlistwise clusterとして診断した。`selected + quota_full` rowsを再構成し、同じquotaと一玉非重複制約で `repair_score`, actual oracle, predicted PnL, low harmful, low tail, high support proxyのgreedy選択を比較した。baseline best scenarioは31候補、EV -2 scenarioは111候補まで広がった。ただし`00335` でsupport repair runtime sortと非oracle listwise selectorに `actual_pnl_at_hv_chosen_horizon` がtie-breakerとして混入していたことを確認したため、00334の `repair_score_greedy == current_replay` はleak混入後の読みとして破棄する。leak-free本体replayではbest scenarioがadded PnL `+63.9770 -> +60.8530`、combined `+403.2680 -> +400.1440`、EV -2 scenarioがadded PnL `+34.8410 -> +31.7170`、combined `+374.1320 -> +371.0080` に下方修正。`00339` でthin-month候補面を診断し、stateful-onlyではEV2 target 4件に候補0、00324外部候補を混ぜるとfresh2024 2024-03 longにoracle positive 18本 / `+90.5230` があるがmodel-used 0と確認した。fresh2024 2024-11 / refit2025 2025-03は候補生成不足。`00340` でfresh03をtarget-local confidence診断へ進めると、60m `-137.9060`、240m `+49.0950`、720m `-99.9060` で、問題はentry方向よりhorizon confidence / exit timing / EV calibrationに寄っていると確認した。`00341` で広いscored examples上のhorizon-confidence support auditへ進め、mintrain1ならfresh03の `score_pnl` は `-137.9060 -> -69.6140` まで改善するが、tail-aware scoreは悪化し、tail-loss AUCも `0.2384` と確認した。`00342` でtail penaltyをtrain support countでgateするとfresh03の `pnl_delta_tail` は `-111.0260 -> -19.2310` へ改善したが、full replayはcombined `+389.5310` でplain `pnl +400.1440` を超えなかった。`00343` で対象月より前のprediction-vs-actual実績からprior/OOB head reliabilityを作ると、reliability-gated scoreはfull replayでplain `pnl` と同じ5 trades / combined `+400.1440` に戻ったが、candidate-levelでは2024-08と2025-07を悪化させた。`00344` でhorizon reliability diagnosticsを作ると、available candidatesで `pnl_delta_tail_reliability_gated` はtarget subset `-131.8792`、all rows `-137.6916` 悪化し、direct multiplierが横断的に危険と確認した。`00345` でreliability-driven switchのabstentionを診断すると、`ranker_pred_pnl < 0` vetoは `pnl_delta_tail_reliability_gated` をtarget subset `-131.8792 -> +13.6962`、all rows `-137.6916 -> +57.0582` へ回復した。tie-breaker修正、listwise cluster診断、teacher diagnostics、singleton abstention/surface diagnostics、thin-month candidate diagnostics、target-local confidence diagnostics、horizon-confidence support audit、tail support metadata/gated score mode、prior/OOB head reliability columns、horizon reliability diagnostics、horizon switch abstention diagnosticsはaccepted。direct feature selector、`singleton_any`、global fallback/EV threshold緩和、global early-support relaxation、tail-aware early score、train-support count gate、reliability direct multiplier、固定240m ruleはreject。

`00346` で `ranker_pred_pnl < 0` switch vetoをstateful replayへ実装した。prediction artifacts上ではreliability-gated系で11..13 groupsのvetoが発火し、candidate aggregateは一部改善したが、best scenarioはplain `pnl` と同じ5 trades / added PnL `+60.8530` / combined `+400.1440` に収束した。best additionsではveto発火0件、selector pass 0件、blockersは `month_pnl_below_floor,role_trades_low,side_share_high` のまま。stateful horizon-switch abstention replay infrastructureはacceptedだが、`pred_pnl_lt0_switch_veto` は標準policyへ昇格しない。

`00347` でpositive predicted PnL failure diagnosticsを追加した。00346の `ranker_replay_candidates_*.csv` 8本を横断すると、market candidate dedupでpositive predicted PnL 205件中124件が損失、合計 `-1104.5216`。candidate-key dedupでも1623件中981件が損失、合計 `-8781.2836`。`positive_bias_and_tail_miss_ge_0p10` はmarket dedupで109件flag / loss precision `0.7706` / recall `0.6774` / flagged PnL `-1044.5162`、`tail_prob_ge_0p30` は86件flag / precision `0.7209` / recall `0.5000` / flagged PnL `-999.3158`。ただし両方とも勝ち候補を削るため、pointwise gateではなく次のstateful replay sensitivityへ進む。positive predicted PnL failure diagnosticsはaccepted infrastructure、標準policyはNoTrade。

`00348` でpositive predicted PnL failure ruleをstateful replayへ戻した。`--positive-pnl-gate-rules` を追加し、`none`, `positive_bias_and_tail_miss_ge_0p10`, `tail_prob_ge_0p30` を864条件で比較した。selector passは `0 / 864`。`tail_prob_ge_0p30` はcandidate surfaceでは負けを削るが、best scenarioでは発火せず、gateなしと同じ5 trades / added PnL `+60.8530` / combined `+400.1440`。`positive_bias_and_tail_miss_ge_0p10` はcandidate surfaceで大きな負け候補群を削るが、bestでは勝ち720m候補を削り、combined `+393.2940` へ悪化した。positive-PnL gate replay infrastructureはaccepted。両ruleはhard gateとしてrejectし、次はhorizon/context別calibration、soft penalty、over-gating diagnosticsへ進む。標準policyはNoTrade。

`00349` でpositive-PnL failure signalをhard gateではなくsoft penaltyとしてstateful replayへ入れた。`--positive-pnl-penalty-specs` を追加し、`none:0`, `residual_bias_tail_miss:0.05/0.10/0.25`, `tail_prob:1/2/5` を2016条件で比較した。selector passは `0 / 2016`。`residual_bias_tail_miss` はbest EV2 scenarioで勝ち候補だけをpenalizeし、weight `0.25` までbestは変わらずcombined `+400.1440`。`tail_prob` はweight `1/2` ではbest no-op、weight `5` は4 trades / combined `+399.8040` へ悪化した。positive-PnL soft penalty replay infrastructureはaccepted。今回のglobal soft penalty群はrejectし、次はglobal cutoff/penaltyではなくover-gating diagnosticsとhorizon/context別calibrationへ進む。標準policyはNoTrade。

`00350` でover-gating context diagnosticsを追加した。00349のsummary/additions/candidate filesを横断し、top/near-best 242 scenarioでrisk ruleが損失を捕まえる効果とselected winnersを巻き込む害を同時に集計した。best scenarioでは `tail_prob_ge_0p30` は発火0。`harmful_prob_ge_0p30` はloss PnL `-40.2876` を捕まえるがwin PnL `+89.7100` とselected flagged win PnL `+49.5600` を巻き込み、`residual_tail_miss_ge_0p10` はselected winners 5本 / `+60.8530` を全て巻き込む。near-best aggregateでは `tail_prob_ge_0p30` が flagged PnL `-59216.3688`、selected flagged win `0` で最もcleanだが、best additionsでは発火しない。over-gating diagnosticsはaccepted。global harmful/residual/720m risk rulesはreject継続。`tail_prob_ge_0p30` はglobal gateではなくcontext-specific risk priorとして扱う。標準policyはNoTrade。

`00351` でcontextual risk confidence diagnosticsを追加した。00350のcontext-specific tail riskを、対象月より前の同一exact contextで損失捕捉が確認できた時だけ信用する診断にした。初回row-weighted priorは同じmarket candidateを複数scenarioで重複計上していたため破棄し、prior confidenceは `market_candidate_key` dedupを既定に修正した。market dedup後のdefault条件では全ruleで `confident_context_count=0` / `context_risk_flag_count=0`。`min_prior_flagged=4` に緩めると `720m short / down_normal_vol / london / one_failed_strict_stage` がconfidentになるが、focus側では勝ち候補36 rows / `+465.8400` だけをflagする。exact-context hard gateは薄いpriorで壊れるためreject。context risk signalはhierarchical/shrunk featureとして扱う。

`00352` でcontext support count diagnosticsを追加した。00351のprior confidenceに `prior_observed_month_count`, `prior_flagged_month_count`, `prior_decision_count`, `prior_market_candidate_count` とsupport threshold CLIを足した。exact contextはdefaultで全rule発火0。`horizon,side` まで粗くするとsupportは増えるが、defaultでは harmful/residual/720m がselected winnersを巻き込み、support2でも harmful/residual はselected winner damageを出す。`horizon,side,combined_regime` + support2 は全rule発火0で薄すぎる。一方、`horizon,side` + support2 + `positive_bias_and_tail_miss_ge_0p10` は flagged PnL `-39210.5520`, loss count `1008`, win count `0`, selected flagged win `0` でclean。pre-registered stateful replay候補として扱い、標準policyにはしない。

`00353` で00352の `horizon,side` + support2 + `positive_bias_and_tail_miss_ge_0p10` をstateful replayへ戻した。`context_hs_support2_positive_bias_tail_miss_ge_0p10` gateはscenario / chosen horizon / side / month単位で過去月だけのmonthly prior confidenceを使う。候補段階では各score/abstentionで82 rowsをvetoし、vetoed PnL `-1222.4120`, loss 78 / win 4 とrisk候補検出は強い。ただし最終採用tradeとは交差せず、`none` vs contextual gateの最終summary差分は `0 / 288` scenarios。bestはどちらも5 trades / added PnL `+60.8530` / combined `+400.1440`。hookはaccepted infrastructureだが、hard prefilterとしては現bestを改善しない。

`00354` で同じcontextual confidenceをsoft repair penaltyへ接続した。`contextual_confidence` と `contextual_confidence_delta` を追加し、`none`, binary weight `1/2/5`, delta weight `1/2/5` を比較した。候補段階では各contextual labelで656 rowsをpenalizeし、penalized PnL `-9779.2960`, loss 624 / win 32 とrisk signalは再現。ただし選択された additions で penalty amount > 0 は0件。最終summary差分は全labelで `0 / 288` scenarios、best combinedはすべて `+400.1440`。soft penalty hookはaccepted infrastructureだが、repair score scalar penaltyとしても現bestを改善しない。

`00355` で00354 penalized rowsのquota rank / selected boundary / rejection reasonを診断した。各contextual labelは656 rows / 26 unique candidate identitiesをpenalizeし、selected additionsとの交差は0件のまま。一部はquota rank 1にいるが、penalized rowsは全件 `tail_prob_ceiling` でpre-filter rejectされていた。00354の `max_chosen_tail_prob=0.3` に対し、penalized rowsのtail probabilityは min `0.312885`, median `0.381267`, max `0.451762`。soft penaltyが効かなかった主因はrepair score順位ではなく、既存tail hard filterが先に全件を落としていたこと。contextual positive-bias confidenceは、現standard replayではtail ceilingの説明/監査signalとして扱う。

`00356` でtail ceiling通過後のpositive-PnL residual failureを診断した。00354 no-penalty candidatesを `max_chosen_tail_prob=0.3` pass/blockedに分けると、row-weighted positive predicted PnL 12544 rows / `-47285.8192` のうち、tail blocked側は3236 rows / `-47165.1376`、tail pass側は9308 rows / `-120.6816`。market candidate dedupでもpositive 205件 / `-1104.5216` に対し、tail blocked 86件 / `-999.3158`、tail pass 119件 / `-105.2058`。tail ceilingは高tail大損領域を落としているが、tail pass後にも低tail residual failureが残る。`pred_pnl_lt_1/2` などは損失捕捉が強いが勝ち候補も削るためglobal hard gateとしてはreject。次はselected/near-selected tail-pass residual failureへ絞る。

`00357` でselected / near-selected tail-pass residual failureを診断した。00354 no-penalty candidatesを00354 additions/rejectionsと突き合わせ、row-weightedだけでなく `candidate_identity_key` dedupを主判断にした。candidate identity dedupではtail pass positiveは118件 / `-90.3858`、loss 61件 / `-365.8848`。actual selected additionsに絞るとtail pass positiveは8件 / `+59.0070`、lossは1件 / `-29.1360`、winは7件 / `+88.1430`。selected lossは `fresh2024_validation 2024-08 long 720m` のsingletonで、`pred_pnl_lt_2` はこの1件だけをflagしwin damage 0。ただし支持はunique 1件なので標準policyにはせず、`selected tail-pass pred_pnl_lt2` / `singleton_720_pred_pnl_lt2` をstateful replay候補としてpre-registerする。`greedy_selected` row_scopeだけを見るとloss 0に見えるが、selection artifact上のactual additionsとは混同しない。

`00358` で00357のpre-registered候補をstateful replayへ戻した。`selected_tail_pass_pred_pnl_lt2` と `singleton_720_pred_pnl_lt2` positive PnL gate ruleを追加し、実行時featureは `hv_chosen_pred_pnl`, `hv_chosen_pred_tail_loss_prob`, `hv_chosen_horizon_minutes` に限定した。`singleton_720_pred_pnl_lt2` はscenario差分で改善96 / 悪化0 / 同値192、known singleton lossを止めてEV -2 / 0をEV2 no-gate相当の5 trades / `+60.8530` へ戻した。ただしbest combinedは既存no-gate EV2と同じ `+400.1440`、selector passは `0 / 288`、blockersは `month_pnl_below_floor,role_trades_low,side_share_high` のまま。`selected_tail_pass_pred_pnl_lt2` は改善96 / 悪化32で広すぎるためglobal hard gateとしてreject。

`00359` で00358後のthin month / side support候補面を監査した。`entry_ev_support_repair_thin_month_candidate_diagnostics.py` にdiagnostic-onlyの `needed_top_oracle_actual_*` 列を追加し、actual PnLはteacher/audit専用に限定した。00358 EV2 bestのstateful surfaceでは残target 4件に候補0。EV -2 + `singleton_720_pred_pnl_lt2` はtarget pool 12 unique / model-used 12 / relaxed guarded 11 / oracle positive 8だが、実質 `fresh2024 2024-08` に集中する。00324 external horizon coverageを足すと `fresh2024 2024-03` は51 unique / oracle positive 18 / oracle positive sum `+90.5230` だがmodel-used 0で、top predicted actualは `-12.7920`、top oracle actualは `+13.4900`。`fresh2024 2024-11` と `refit2025 2025-03` は候補0。残blockerはglobal gate不足ではなく、target-local calibration / fallback confidence / candidate generation不足。

`00360` で candidate generation gap auditを追加し、00322 base / 00358 ranker / 00358 replay candidateをtarget-scope表へ正規化した。stageは `no_prediction_rows`, `no_rows_in_scope`, `no_target_side_rows`, `no_target_support_rows`, `threshold_filtered`, `relaxed_only_candidate`, `strict_candidate_exists`。`fresh2024 2024-11 long` は00358 rankerでrole/month row 1、available scope 0、greedy 1でrelaxed only。`refit2025 2025-03 short` はbase/rankerともprediction row 0。actual PnLは診断列だけに使い、stage分類やgateには使わない。

`00361` で selected one-fail rowsを `selected_onefail_replacement` として再露出する診断を追加した。`fresh2024 2024-11 long` はscope内に1行出るがstrict EVは通らずrelaxedのみ通る。00358 rankerでは60m `+0.3000`, 240m `+2.4500`, 720m `-5.2800`。しかしglobal selected one-fail wideningは00358 ranker strict `-83.4028`, relaxed `-68.0198` と悪化。

`00362` で `refit2025 2025-03 short` のupstream universeを監査した。raw prediction rows `28,972`、short side rows `28,972`、candidate rows `41`、stateful available `33` が存在するため、raw coverage不足ではない。00318で0件になる直接原因は `extra_short_needed=0` / `extra_long_needed=0` で、repair targetが発行されないこと。これはsupport-sufficient negative monthのrepair-target objective mismatchとして扱う。

`00363` でsupport-sufficient negative monthを既存trade起点で診断した。`2025-03-20` のlong lossesはoracle fixed horizonなら直るが、現predictionは悪いhorizonを選ぶ。`2025-03-21 14:00 short -2.3400` はfixed horizonでは直らず、skip/replacement対象。top-score replacementはone-fail long `2025-03-26 14:34` で月PnL `+4.2170` まで改善するが、lossを事前に識別するheadが必要。

## 現在の判断

| 項目 | 判断 |
|---|---|
| Standard policy | なし。NoTrade-firstを維持 |
| Current diagnostic candidate | q95 + raw `loss_exit30_cd15` dynamic exit cooldown + short entry-block replacement + fixed60 family-aware uncertainty margin w5 + require-model-used side-aware hold-extension + `long_range_normal_ny_fixed60_pred_gt0` position-quality overlay。00314で total `+339.2910` / month min `-0.7200` まで改善し、00323でsupport repairに接続するとcombined totalは `+362.7000`。00326のrow x horizon + hpen0.25はactual-floorなしでcombined `+374.6110`。00329のbroad-prior low-complexity horizon-choice rankerはcombined `+403.2680` まで伸びたが、00335のleak-free修正で `+400.1440` に下方修正。00339ではthin-month候補面の不足が残り、fresh03はfallback/non-model calibration問題、fresh11/refit03は候補生成不足。00340/00341でfresh03のhorizon confidence / expected PnL / tail calibration不足を確認。00342のtail support gateはfresh03局所を改善するがfull replayではplain PnLに負け、00343/00344でreliability direct multiplierもreject。00346のstateful `ranker_pred_pnl < 0` switch vetoもbestを改善しない。00347でpositive predicted PnL failureが候補面の主問題と分かったが、00348 hard gateも00349 soft penaltyも改善なし。00350でover-gatingを分解し、00351/00352でcontext supportを検証した。00353 hard gateと00354 soft penaltyはいずれも最終採用と交差せず不変。00355でpenalized rowsは全件既存 `tail_prob_ceiling` によるpre-filter rejectと確認。00356でtail ceilingは高tail大損領域を大きく落とす一方、tail pass後のglobal residual hard gateは勝ち候補削除が大きいと確認。00357ではactual selected tail-pass lossが `fresh2024_validation 2024-08 long 720m` のsingletonに狭まった。00358で `singleton_720_pred_pnl_lt2` をstateful replayへ戻すと悪化scenario 0でknown singleton lossを止めたが、既存EV2 no-gate bestと同点で標準admission blockersは残った。00359で残target 4件を監査し、EV2 best stateful候補0、EV -2 + singletonは2024-08集中と確認。00360で `fresh2024 2024-11` はavailable row-scope不足、`refit2025 2025-03` はpost-00318 feed上の候補0へ分解した。00361でselected one-fail replacement scopeを作ると2024-11は見えるが、global wideningは大きく悪化。00362でrefit2025-03はraw rows/candidatesがあり、thin-supportではなくsupport-sufficient negative month修復の対象と確認。00363で既存trade repair診断を作り、現predicted fixed-horizon argmaxはreject、loss-risk + horizon abstention + target-aware replacementへ進む。 |
| Why not standard | 00314 bestもmonth min `-0.7200` でNoTrade-first floorを通らず、standard admissionはmonth/role/month-trade/side-shareでblocked。00317ではstandard admissionに `8` balanced extra tradesが必要と確認。00318/00319ではfuture-label fixed-bestなら改善余地があるが、現predicted fixed horizon選択は悪化。00320/00321のchronological headも悪化。00322のs2はrow-level raw PnLが正でもoverlapping cluster依存。00323/00325/00326でsupport repairは伸びたが、bestでもmonth min `-0.6120` とside-share blockerが残る。00327ではsupport-repair-only prior不足。00328ではbroad priorが2024-08の悪い720mを警告できるが、direct penaltyが勝ち候補も削る。00329の低複雑度rankerはtotalを大きく伸ばしたが、00335のleak-free replayでもmonth min `-0.6120`、role trade min `3`、remaining extra trades `3`、blockers `month_pnl_below_floor,role_trades_low,side_share_high` が残る。00330/00331/00332のrisk penaltyは勝ち候補を削るかno-op。00339ではremaining thin monthsのうちfresh03は良いoracle候補がmodel-used 0、fresh11/refit03はpost-00318 candidate feedに存在しないため、単純threshold緩和では標準化できない。00340の240m優位はtarget-local post-hoc診断であり、固定240mや時刻ruleを実行policyにはできない。00341のmintrain1はfresh03のPnL signalを一部拾うがtail-loss calibrationが悪く、他targetの候補生成不足も解かない。00342のtrain-support gateはfresh03局所を改善してもfull replayでplain PnLを超えず、strict gateは2024-08を悪化させる。00343/00344のprior/OOB reliabilityは診断列として有用だが、direct score multiplierではtarget subset/all rowsの両方でcandidate choiceを悪化させる。00346のstateful abstentionはbest additionsでveto発火0件、selector pass 0件で、plain `pnl` のbestを改善しない。00348のpositive-PnL hard gatesはcandidate surfaceでは負けを削っても、best replayではno-opまたは勝ち候補削除で悪化。00349のglobal positive-PnL soft penaltyは軽いweightではno-op、強いtail penaltyではwinner/supportを削って悪化する。00350のover-gating診断でもglobal harmful/residual/720m ruleはselected winnersを削るため標準化不可。00351ではmarket dedup後のexact-context confidenceがdefaultで発火せず、min4 sensitivityは勝ち候補だけを削った。00352のsupport2 positive-bias signalはdiagnosticとしてcleanだったが、00353 hard gateも00354 soft penaltyも最終採用tradeに当たらずbest改善0。00355でそのpenalized rowsは全件 `tail_prob_ceiling` によりpre-filter済みと分かったため、contextual penaltyを強めても現standard replayは改善しない。00356ではtail pass後のresidual rule候補もwinner damageが大きく、global hard gateで標準化できない。00357の `pred_pnl_lt_2` はactual selected lossをcleanに拾うが、unique selected failure 1件だけなので標準化には足りない。00358の `singleton_720_pred_pnl_lt2` はstateful replayで悪化0だが、既存EV2 thresholdと同点でNoTrade-first admissionを通らない。00359で残targetの候補面を見ても、EV2 statefulは候補0、external oracle positivesはmodel-used 0、2024-11/refit2025-03はpost-00318 feed上で候補0なので、現候補面のrerankingでは標準admissionを通せない。00362でrefit2025-03のraw rowsは存在すると分かったが、`extra_*_needed=0` のsupport-sufficient負け月なので、00318 thin-support laneへ混ぜても標準化の根拠にはならない。 |
| Useful signal | exit-regret / loss-first dynamic exit / replacement-stateful-net / same-side missed loss / low-capture loss / isolated large-loss capture failure / fixed-horizon improvement target / chronological hold-extension predicted delta / model-used-aware hold-extension replay / extension veto replay infrastructure / side-aware fixed horizon replay / stateful extension skip impact / selected-side capture ratio / short rollover loss-first block diagnostics / London short mid-loss block diagnostics / hold-extension false-positive block diagnostics / prediction-row entry-block flags / side EV penalty replacement replay / replacement->hold-extension integration diagnostics / entry-time position-quality proxy diagnostics / entry-block holdout-support diagnostics / fixed60 prior uncertainty diagnostics / fixed60 uncertainty head diagnostics / fixed60 uncertainty soft margin diagnostics / fixed60 prior shrinkage diagnostics / admission repair target diagnostics / thin-month opposite candidate diagnostics / one-fail strict near-miss diagnostics / near-miss fixed-best exit target diagnostics / predicted fixed-horizon choice calibration diagnostics / chronological near-miss exit head diagnostics / horizon-specific viability diagnostics / broad candidate horizon viability diagnostics / non-overlap horizon choice audit / support-repair horizon replay diagnostics / support-repair target coverage diagnostics / target-aware support repair replay diagnostics / row x horizon support repair diagnostics / chronological horizon duration penalty diagnostics / broad duration prior diagnostics / broad-prior horizon-choice ranker diagnostics / low-complexity horizon-ranker sensitivity / residual lower-bound horizon diagnostics / harmful-overestimate target diagnostics / harmful-overestimate head diagnostics / support-repair pairwise/listwise switch diagnostics / support-repair listwise cluster diagnostics / support-repair leak-free tie-breaker audit / support-repair listwise teacher diagnostics / fallback duration-penalty sensitivity / support-repair target-local confidence diagnostics / horizon-confidence support audit / candidate-generation gap audit / selected-onefail replacement scope diagnostics / upstream universe coverage diagnostics / support-sufficient negative-month repair diagnostics / tail-loss calibration diagnostics / short-horizon predicted-vs-actual overestimate diagnostics / overlay residual floor support diagnostics / support-aware admission diagnostics / support-aware progression comparison diagnostics / month-warmup overlay diagnostics / confidence gate overlay diagnostics / confidence feature-bin diagnostics / chronological selected-trade calibration diagnostics / calibration residual context diagnostics / prior residual pressure diagnostics / chronological large-loss head diagnostics / path-aware large-loss compensation diagnostics / uncompensated path target diagnostics / uncompensated sequence-state diagnostics / uncompensated realized candidate-path diagnostics / supervised shrinkage and downside meta features |
| Main risk | 勝ちtrade削除、only-candidate replacement悪化、high-score losing tail、May/September tail、q99/q95 same-window selection、support緩和によるrole PnL崩壊、別familyでのPnL再現不足、no-replay改善をpolicy evidenceと誤読すること、1件/少数件blockを堅牢なedgeと誤読すること、extensionで直せない損失へextensionを無理に当てること、fallback hold-extension predictionでaggressive fixed720を開くこと、extension vetoをentry blockの代替と誤読すること、remaining sparse negative monthsを単発blacklistで追うこと、hindsight fixed-horizon rescueを実行可能policyと誤読すること、support-aware diagnostic passを標準admissionと誤読すること、month-warmupのsupport-aware passを改善と誤読すること、confidence gateの低活動floor改善を標準候補と誤読すること、calibration MAE改善をadmission改善と誤読すること、calibration residual contextをpost-hoc blacklist化すること、prior residual pressureの小幅改善を標準policyとして扱うこと、fixed60 prior ruleのrefit集中改善をhard gate化すること、prior shrinkageの低drawdownだけを見てtotal/month floor悪化を見落とすこと、total改善だけをstandard-admission readiness改善と誤読すること、repair target不変のまま候補を前進扱いすること、oracle bestだけを見てside-balanced support overlayを採用すること、score floor未満のnear-missをsupport目的でそのまま入れること、fixed horizon実現悪化を無視すること、現predicted fixed horizon choiceをexit selectorとして使うこと、current PnL-regression argmax horizon headをexit selectorとして使うこと、current horizon-specific viability headをdirect exit selectorとして使うこと、available-only fallback positive rowをedgeと誤読すること、actual fixed-best targetをpolicy evidenceと誤読すること、actual-floor support repairを実行可能policy evidenceと誤読すること、pred-only repair_scoreのfresh2024 tailを見落とすこと、hpen0.25をchronological calibrationなしで標準化すること、fallback0.25をlearned evidenceと誤読すること、support-repair-only prior不足を見落としてduration penaltyを学習済みと扱うこと、broad priorの2024-08警告だけでdirect penaltyを採用すること、duration priorで勝ち候補を削ること、強すぎるhorizon penaltyで良い長期候補を削ること、low-complexity rankerのhigh totalだけを見てrole/month/side-share blockersを無視すること、fallback-allowed rankerをpolicy evidenceにすること、lower-bound residual scoreをglobal 720m suppressorとして採用すること、tiny lower-bound no-opを改善と誤読すること、harmful head AUCだけを見てdirect penaltyを採用すること、harmful probabilityをsupport objectiveなしにglobal penalty化すること、60m executable AUCだけを見てtail-loss/PnL calibration不全を見落とすこと、large-loss classifier scoreをdirect hard gateとして扱うこと、positive context-monthをrisk scoreで丸ごと消すこと、uncompensated targetを孤立損失と誤読すること、target count最小化をpolicy objectiveにすること、realized path variant診断をfull replacement replay evidenceと誤読すること、raw cd15上のshort block replacement改善を00293 full comboの再現と誤読すること、全family一律short replacementを標準化すること、post-hold blockをentry-time executable policyと誤読すること、entry-time proxyのrefit集中を汎化edgeと誤読すること、holdoutで発火0件のentry-block ruleを再現ありと誤読すること、`next_*` 診断列を実行featureへ混ぜること、fixed-horizon actual PnLを実行時featureとして使うこと |

00322..00366追加リスク: overlapping candidate clusterのraw利益をpolicy evidenceと誤読しない。non-overlap診断もfull stateful replayではない。score>=5 broad universeのtail-loss AUC改善だけで720mを再開しない。support repair countを減らすためにEV-2の負け候補を入れてmonth floorを壊さない。fresh2024 2024-03のhidden oracle positivesをfallback/non-model evidenceのまま採用しない。actual-floorの上限診断を実行可能policy evidenceにしない。pred-only repair_scoreはfresh2024 2024-08の悪い720mを拾うため、そのまま採用しない。hpen0.25は有望だが、同一repair set上の診断値なので標準化しない。00327のfallback0.25再現はlearned evidenceではない。support-repair対象行だけのpriorは疎すぎる。00328のbroad priorは警告信号として有効だが、direct penaltyを学習済みpolicyとして扱わない。00329のlow-complexity rankerはdiagnostic bestだが、standard blockersを解いていない。00330のlower-bound scoreは勝ち720mを削るため、residual priorはまず診断/featuresとして扱う。00331のharmful headは識別力があるが、direct penaltyではbaselineを超えない。00332のsupport-aware harmful penaltyは中程度false positiveで勝ち候補を落とすか、高閾値でno-opになるため、scalar penaltyを改善と誤読しない。00334のactual oracleは教師設計用でありpolicy evidenceではない。00334のcurrent-vs-repair一致は00335でleak混入後の読みと判明したため破棄する。`actual_pnl_at_hv_chosen_horizon` をoracle以外のselector tie-breakerや実行featureへ混ぜない。00339のexternal oracle positivesは候補存在診断であり、model-used 0や負EVを無視してpolicy採用しない。候補0のtargetを「問題なし」と誤読せず、候補生成不足として扱う。00340のtarget-local 240m優位を固定horizon ruleへ変換しない。`entry_hour>=15` のような少数target-local ruleを汎化edgeとして扱わない。00341のmintrain1改善をglobal early-support relaxationの根拠にしない。tail-aware scoreはtail-loss AUCが悪い状態では安全化ではなく誤選択増幅になり得る。00342のtail support gateはfresh03局所では効くが、train countだけを信頼性proxyとして標準policyにしない。strict count gateは2024-08のような別targetを悪化させる。00343/00344のprior/OOB reliabilityはhead診断として使い、positive AUC/SpearmanをそのままPnL multiplierとして扱わない。plain PnLと同点になったscoreや、一部greedy改善を標準policy改善と誤読しない。00345のpost-hoc switch veto改善をstateful policy evidenceとして扱わない。00346でstateful replayへ戻してもbestを改善しなかったため、`ranker_pred_pnl < 0` vetoを標準policyとして扱わない。00347のpositive-PnL failure ruleはpointwise候補面診断であり、stateful replay前にhard gateとして標準化しない。00348でstateful replayへ戻しても、positive-PnL hard gateはno-opまたは勝ち候補削除で悪化したため、global hard cutoffとして標準化しない。00349のglobal soft penaltyもno-opまたは悪化なので、global penaltyを十分な解と扱わない。00350のover-gating診断はpolicy evidenceではなく診断であり、context-specificに見えるtail riskもfull stateful replay前に標準化しない。00351のrow-weighted prior supportを採用しない。market-dedup後の薄いexact context confidenceをhard gate化しない。00352のcoarse support2 positive-bias diagnosticをstateful replay前に標準化しない。00353で候補vetoが強くても最終採用が不変だったのでhard prefilter改善と誤読しない。00354で候補penaltyが強くても選択additionsにpenalty対象が0件だったのでrepair score改善と誤読しない。00355でpenalized rowsは全件tail ceiling済みと分かったため、contextual penaltyを強めれば改善するとは扱わない。tail ceilingを外す場合はcounterfactual replayなしに判断しない。selected winner damageがあるharmful/residual ruleをglobal gateへ戻さない。00356のtail pass residual ruleは全候補集計だけでpolicy化しない。`pred_pnl_lt_1/2` の損失捕捉を、勝ち削除コスト抜きでhard gate化しない。available candidates全体のfailureを、greedy selectedのfailureと混同しない。00357のselected `pred_pnl_lt_2` はunique 1件支持なので標準化しない。`greedy_selected` row_scopeとselection artifact上のactual additionsを混同しない。00358のbroad `selected_tail_pass_pred_pnl_lt2` はscenario悪化があるためglobal gateにしない。`singleton_720_pred_pnl_lt2` の悪化0を標準policy採用と誤読しない。00359の `needed_top_oracle_actual_*` を実行featureやselector tie-breakerに使わない。00359で候補0と分かったtargetをrerankingで解こうとしない。00360のgap_stage分類にactual PnLを混ぜない。`fresh2024 2024-11` のgreedy 1行を汎化済みedgeと誤読しない。00361のselected-onefail re-exposureをglobal available wideningとして採用しない。2024-11の1行を救うために2025-07/2025-11/2024-08の大損720mを再開しない。00362でraw prediction rowsが存在すると分かったため、`refit2025 2025-03` をraw universe不足として追い続けない。support-sufficient negative monthを00318 thin-support laneへ無理に混ぜない。00363のfixed-best exit oracleを実行可能exit selectorと誤読しない。現predicted fixed-horizon argmaxは悪化するため、そのまま使わない。00364の対象月だけで当たるloss-risk ruleをglobal blockへ昇格しない。全体 flagged PnL がpositiveなら、target loss recallよりwinner damageを優先してrejectする。00365のhorizon abstention診断はselected-trade counterfactualであり、stateful replayなしに標準policy化しない。broad abstention ruleの高いcounterfactual改善を、one-position constraint下の実行PnL改善と同一視しない。00366でbroad abstention ruleは `all/predicted` では有効でも、本線 `isolated_large_loss_long/fixed720` のpositive recovery extensionsを全停止するため、本線hold-extension vetoへ重ねない。

00367..00375追加リスク: replacement改善をloss trade事前識別の証拠と誤読しない。min prior month `1` の高PnL候補をsupport十分と扱わない。winnerを外してもreplacementで月PnLが改善したケースをloss-risk selector成功と扱わない。one-fail replacement候補の単一target月改善を標準policyへ昇格しない。auto target count 1を複数target検証済みと誤読しない。00370のconfig rows / variant rowsを独立サンプル数として扱わない。realized monthly PnLで作ったtarget inventoryを実行時featureやpolicy evidenceとして扱わない。00371のcross-artifact target identityでbaselineがpositiveの月を、current negative-month repair成功と誤読しない。winnerを外してreplacementで上回ったケースをloss-risk selectorの精度として扱わない。00372/00373でoracle loss selectionでもbaseline-positive degradationが残るため、risk selectorだけを改善すれば十分と扱わない。winner-damage rankingで上位でも制約未通過ならpolicy候補と扱わない。00374/00375のabstention通過を、target 1件改善の薄さやpost-surface閾値選択を無視して標準policy化しない。広いtarget setで壊れなかったことを複数target有効性と誤読しない。

## 研究レーン

| レーン | Reports | 現状 |
|---|---|---|
| Short budget / side drift | `00174`..`00207` | budget0とside drift guardはtailを縮めるが、same-family / 2024 chronologyで標準化できず診断baseline止まり。 |
| Entry EV admission | `00208`..`00224` | raw/calibrated EV、rank、quantile、positive floor、hold-capを検証。NoTrade-first selectorは通らない。 |
| Executable EV / capture | `00225`..`00232` | executable EVやdense captureはrow-level改善があるが、stateful validationでtailとsupport不足が残る。 |
| Side balance / composite | `00233`..`00239` | side-balanceやcomposite hard gateでは候補が生まれず、component targetへ分解。 |
| Component / exit-regret | `00240`..`00322` | EV overestimateからdirection/exit/replacementへ分解。00267でq99 prior guardがstateful replay上は改善したが、標準admission未通過。00268でfresh support不足はepisode集中であり、rank0緩和はcal/refitを壊すと確認。00269の外部HGB、00270の外部full-hybridでもNoTrade未満。00271で損失はno-edgeではなくexit-capture failure / executable EV過大評価に寄ると確認。00272でpost-selector executable scoreは負の対照としてreject。00273でselector前capture補正もNoTrade未満。00274でcoarse `direction_regime` tail-riskはq99をプラス化したが、support/side集中でNoTrade。00275で外部HGB再現は弱く、tail-risk headはdiagnosticへ降格。00276/00277でlow loss-first dynamic exitが全role positiveまで進み、00278でcooldownが過剰回転を抑えた。00279のglobal quantile化はtotal改善と引き換えにtail/roleを壊し、policy候補にはしない。00280でraw cd15の残存損失はentry無価値ではなくexit-capture / EV過大評価が中心と確認。00281でprior capture factorのhard block/direct shrinkはreject。00282でsupervised shrinkageはscale補正として有効だが、direct gateはreject。00283でprediction-row shrinkage inputはaccepted、score replacementはreject。00284でdownside meta hard blockはreject、00285でdownside soft marginもreject。00286でstateful floor selectorを追加し、現候補群は全てNoTrade。00287でpost-exit pathを分解し、broad post-loss cooldownは勝ちを削ると確認。00288でisolated large-loss capture failureを特定し、一律fixed horizonはfloor悪化でreject。00289でhold-extension choice targetを学習し、`isolated_loss` training + `isolated_large_loss` threshold 5を次のfull replay候補にした。00290でstateful replayに接続しtotal改善は維持したがmonth floor未達でNoTrade。00291でside-aware fixed 720mはtotal/floorを改善。00292でhybrid 2025-12 shortをentry block overlayで消し、00293でrefit2025 2025-03/08 residual floorも縮めた。00294で残存floorはthin support中心と確認し、00295でsupport-aware admission診断へ分解。00296で候補系列横断でも00293だけがdefault `support_aware_only` だが、感度で落ちるため標準policyはNoTrade。00297でmonth-warmupはreject。00298でconfidence hard gateも低活動化またはfloor悪化でreject。00299でOOF calibrationはscale補正に有効だが、direct hard gateはreject。00300でcalibration residual contextを分解し、00301のprior-only residual pressure、00302のlarge-loss headはいずれもdirect gateとしてreject。00303でpath-aware補償を分解し、00304でuncompensated target headを試したが、現featureではpositive pathを分離できずdirect gateはreject。00305でuncompensated targetは高密度pathやnext winnerに埋まると確認。00306でrealized candidate path variantを比較し、target count最小化もreject。00307で未選択entry候補feed上のshort entry-block replacementを試し、raw cd15 totalは改善したがmonth floorとfamily再現は未解決。00308でreplacement pathへhold-extensionを統合し、require-model-used guardでfallback fixed720 tailを防いだ。00309でholdext false-positive blockをextension vetoに戻したが悪化。00310でentry-time observable position-quality proxyへ戻し、`long_range_normal_ny_fixed60_pred_gt0` はtotalを伸ばしたがrefit集中。00311で同ruleはholdout発火0件と確認し、hard block候補からfeature候補へ戻した。00312でfixed60 false-positiveをprior-only uncertainty feature化したが、細粒度ruleの改善はrefit集中の再現に留まるためhard gateにはしない。00313でuncertainty head化しAP改善を確認。00314でsoft marginへ戻し、preblockgap継承ありfamily-aware w5がdiagnostic bestを更新。00315でtrade-set deltaを監査し、改善源はrefit2025 removed tradeに集中すると確認。00316で粗いprior shrinkageを試したがraw性能が落ちた。00317でadmission repair targetを計算し、total改善だけではsupport/side修復が進まないと確認。00318で反対側near-miss候補はあるがfixed horizon実現が悪いと確認した。00319でfixed-best exit targetは有望だが現predicted fixed horizon choiceは悪化すると確認。00320でchronological exit headも悪化し、00321のhorizon-specific viabilityもdirect selectorとしては悪化。00322で広いcandidate universeはrow-level改善を出したが、非重複後に縮み、score>=5 broad universeも失敗したため、standard admissionはNoTrade。 |

| Support repair continuation | `00323`..`00375` | 00322 s2を00314 best branchのsupport repairへ接続。00323 best totalは5本追加 / `+23.4090` / combined `+362.7000`。00325 actual-floor upper-boundはcombined `+371.6610`。00326 row x horizon + hpen0.25はactual-floorなしでcombined `+374.6110` まで伸びるが、00327のsupport-repair-only calibrationはprior不足で失敗。00329のbroad-prior low-complexity horizon-choice rankerはleak修正前combined `+403.2680`、00335 leak-free replayでは `+400.1440` まで伸びるが、month/role-trade/side-share blockersが残る。00339でthin-month候補面を診断し、fresh03はfallback/non-model calibration、fresh11/refit03は候補生成不足と確認。00340でfresh03 target-local confidenceを診断し、240mだけが正でexit timing / horizon confidence / EV calibrationが主弱点と確認。00341でmintrain1 sensitivityを監査し、fresh03のPnL signalは一部拾えるがtail calibrationが崩れると確認。00342でtail support gateはfresh03局所を改善したが、full replayではplain PnLを超えず、strict gateは2024-08を悪化。00343/00344でprior/OOB reliabilityを導入・診断したがdirect score multiplierはtarget subset/all rowsで悪化しreject。00346 stateful pred-pnl negative vetoはbest改善なし。00347でpositive predicted PnL failureが主なtrust問題と確認。00348のhard gateはbest no-op/悪化、00349のsoft penaltyもbest no-op/悪化。00350でover-gatingを分解し、tail probabilityはcontext-specific risk priorとして有用だが、global harmful/residual/720m rulesはwinner damageが大きいと確認。00351でexact-context confidenceを検証し、market dedup後はdefault confident context 0、min4 sensitivityはwinner over-gating。00352でsupport countを追加し、`horizon,side` + support2 + positive-biasはcleanなdiagnostic signal、regime追加は薄すぎると確認。00353 hard gateと00354 soft penaltyでは候補risk検出は再現したが最終採用は不変。00355でpenalized rowsは全件 `tail_prob_ceiling` によるpre-filter rejectと確認。00356でtail ceilingは高tail大損候補を強く削るが、tail pass後のglobal residual hard gateはwinner damageが大きいと確認。00357でactual selected tail-pass lossはsingletonと分かり、00358で `singleton_720_pred_pnl_lt2` をstateful replayへ戻すと悪化0でknown lossを止めた。ただしbestは既存EV2 no-gateと同点で、standard blockersは残る。00359で残target 4件を監査し、EV2 bestはstateful候補0、EV -2 + singletonは2024-08集中と確認。00360で2024-11はavailable row-scope不足、refit2025-03はpost-00318 feed上の候補0へ分解。00361でselected-onefail再露出は2024-11の入口になるが、globalでは大幅悪化と確認。00362でrefit2025-03はraw rows/candidates自体は存在し、`extra_*_needed=0` によるrepair-target objective mismatchと確認。00363でsupport-sufficient negative monthの既存trade repair診断を追加し、現predicted fixed-horizon argmaxはreject、loss-riskとreplacement selectorが必要と確認。00364でloss-risk priorを診断し、target月内のloss recallは高いが全体winner damageが大きいためdirect blockはreject。00365で同signalをhorizon abstentionへ回すと全体extension delta `-221.4806 -> +207.3556` の候補ruleが出た。00366でstateful replayへ戻すと `all/predicted` では改善するが、本線 `isolated_large_loss_long/fixed720` では全8 good extensionsを止めるため、broad ruleは本線vetoとしてreject。00367でprior-calibrated replacement rankingを追加し、`prior_actual_mean` / `bias_corrected` が有望だが2 prior months + one-fail依存なので標準policyではない。00368でloss-risk selectorと接続し、`side_gap_ge0p15_lossfirst_lt0p30` + min prior month2 filterはtarget worst lossを選べたが、broad risk selectorはwinnerを外す。00369でauto target化すると現branchのsupport-sufficient negative targetは1件だけと確認。00370で過去artifactを棚卸しし、現branch外にはsupport-sufficient target候補が複数あるが、config rowsは独立サンプルではないと確認。00371でcanonical target surfaceへ広げると、baseline positive月が多く、non-oracle selectorはwinner damageが大きいと確認。00372でwinner-damage制約を入れると全surface rowが落ち、oracleでもreplacement failureが残ると確認。00373で制約をsurface ranking本体へ入れても通過0件。00374でreplacement abstentionを入れると非oracle通過行が出たが、実質1 target改善。00375で広いtarget setへstressしても壊れなかったが、追加targetには介入せず、複数target有効性は未確認。 |

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
- calibration residual context diagnostics
- prior residual pressure diagnostics
- chronological large-loss head diagnostics
- path-aware large-loss compensation diagnostics
- uncompensated path target diagnostics
- uncompensated sequence-state diagnostics
- uncompensated realized candidate-path diagnostics
- prediction-row entry-block flag generation
- side EV penalty replacement replay
- replacement to hold-extension integration pipeline
- model-used-aware hold-extension replay
- extension veto replay infrastructure
- prediction-based horizon abstention veto diagnostics
- support-sufficient replacement calibration diagnostics
- support-sufficient selector surface diagnostics
- support-sufficient auto target inventory
- support negative month inventory diagnostics
- canonical support-sufficient target inventory selector-surface input
- selector surface winner-damage diagnostics
- winner-damage constrained selector surface ranking
- replacement abstention surface diagnostics
- broad support-sufficient target-set stress diagnostics
- extension-veto-aware entry-block overlay grouping
- entry-time position-quality proxy overlay rules
- entry-block holdout-support diagnostics
- fixed60 prior uncertainty diagnostics
- fixed60 prior uncertainty head diagnostics
- fixed60 uncertainty soft-margin prediction-row input generation
- preblockgap side-gap quantile inheritance for score-head experiments
- trade-set delta diagnostics for score-head and entry-block comparisons
- fixed60 prior shrinkage diagnostics for score-head experiments
- admission repair target diagnostics for standard blockers
- thin-month opposite candidate diagnostics and one-fail strict near-miss buckets
- near-miss fixed-best exit target diagnostics
- predicted fixed-horizon choice calibration diagnostics
- chronological near-miss exit head diagnostics
- horizon-specific near-miss viability diagnostics
- broad candidate horizon viability diagnostics
- horizon choice non-overlap audit
- support-repair horizon replay diagnostics
- support-repair target coverage diagnostics
- target-aware support repair replay diagnostics
- row x horizon support repair replay diagnostics
- chronological horizon duration penalty calibration diagnostics
- broad duration prior repair replay diagnostics
- row-level duration prior evidence columns
- broad-prior horizon-choice ranker diagnostics
- low-complexity horizon-ranker sensitivity diagnostics
- horizon/context residual prior diagnostics
- lower-bound horizon score modes
- harmful-overestimate target diagnostics
- harmful-overestimate horizon classifier head
- harmful guard score mode diagnostics
- support-aware harmful score mode diagnostics
- support repair harmful penalty infrastructure
- repair support-success proxy diagnostics
- support-repair pairwise/listwise switch diagnostics
- support-repair listwise cluster diagnostics
- support-repair leak-free tie-breaker audit and regression tests
- support-repair listwise teacher diagnostics
- support-repair singleton abstention diagnostics
- support-repair singleton surface diagnostics
- fallback duration-penalty sensitivity diagnostics
- support-repair target-local confidence diagnostics
- horizon-confidence support audit diagnostics
- candidate-generation gap audit diagnostics
- selected-onefail replacement scope diagnostics
- upstream universe coverage diagnostics
- support-sufficient negative-month repair diagnostics
- tail support metadata and gated horizon score modes
- prior/OOB head reliability diagnostics
- horizon reliability columns in prediction artifacts
- horizon reliability choice-delta diagnostics
- horizon reliability switch abstention diagnostics
- horizon-switch abstention replay infrastructure
- positive predicted PnL failure diagnostics
- positive-PnL gate stateful replay diagnostics
- positive-PnL soft penalty replay diagnostics
- over-gating context diagnostics
- contextual risk confidence diagnostics
- context support count diagnostics and support threshold controls
- tail ceiling residual failure diagnostics
- tail selected residual diagnostics
- selected tail pred PnL gate replay infrastructure
- thin-month oracle-top candidate audit diagnostics

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
- positive-PnL failure ruleをglobal hard gateとして標準化すること
- positive-PnL failure signalをglobal soft penaltyとして標準化すること
- harmful/residual/720m risk ruleをglobal gateとして標準化すること
- row-weighted prior supportをcontext confidence evidenceとして扱うこと
- market-dedup後の薄いexact-context confidenceをhard gate化すること
- coarse support2 positive-bias diagnosticをstateful replay前に標準化すること
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
- calibration residual contextをpost-hoc static blacklistとして扱うこと
- prior residual pressureの小幅改善を標準policyとして扱うこと
- broad prior context risk gateを標準policyとして扱うこと
- large-loss probabilityをdirect hard gateとして扱うこと
- high-risk contextをwinner/positive pathごと丸ごと消すこと
- uncompensated-loss probabilityをdirect hard gateとして扱うこと
- uncompensated targetを孤立損失として扱うこと
- target countの単純最小化をpolicy objectiveにすること
- realized path variant診断をfull replacement replay evidenceとして扱うこと
- short entry-block replacementを全familyに一律標準化すること
- raw cd15上のreplacement改善を00293 full combo再現として扱うこと
- fallback hold-extension predictionでaggressive fixed720を開くこと
- post-hold hold-extension blockをentry-time executable policyとして扱うこと
- `holdext_long_range_normal_ny` extension vetoをpost-hold no-replacement blockの代替として扱うこと
- broad `long_range_normal_ny` blockをtotal改善だけで標準化すること
- `long_range_normal_ny_lossprob_lt0p3_sidegap_ge0p2` のような1件proxyを標準policyとして扱うこと
- `long_range_normal_ny_fixed60_pred_gt0` のrefit集中改善を未使用chronologyなしで汎化edgeと扱うこと
- holdoutで発火0件のentry-block ruleを再現ありとして扱うこと
- fixed60 prior warning ruleをrefit集中のままhard gate化すること
- fixed60 uncertainty probabilityをdirect hard gateとして使うこと
- fixed60 prior shrinkageをraw total/month floor悪化のままpolicy branchへ昇格すること
- prior shrinkageのmax drawdown改善だけを見てNoTrade-first blockersを無視すること
- total改善だけをstandard-admission readiness改善として扱うこと
- repair target不変の候補を標準化へ近づいたものとして扱うこと
- support/side blockersをrow削除だけで解こうとすること
- oracle best PnLだけを見てside-balanced support overlayを採用すること
- score floor未満のnear-missをsupport目的だけでentryへ昇格すること
- fixed horizon実現悪化を無視してsupport repairを進めること
- current predicted fixed-horizon maximumをexit selectorとして使うこと
- current PnL-regression argmax horizon headをexit selectorとして使うこと
- current horizon-specific viability headをdirect exit selectorとして使うこと
- raw broad horizon threshold PnLをstateful policy evidenceとして扱うこと
- overlapping available-candidate choicesを一玉制約のpolicy resultとして扱うこと
- score>=5 broad horizon universeを現条件で標準化すること
- support repair count削減のためにEV-2の負け候補を入れてmonth floorを壊すこと
- support-repair overlay診断をfull candidate-stream stateful replayとして扱うこと
- fresh2024 2024-03のfallback/non-model hidden positivesをそのままedgeとして採用すること
- fresh2024 2024-11を単純threshold緩和で拾うこと
- target-local 240m優位を固定horizon ruleとして採用すること
- target-local時刻ruleを少数サンプルのままhard gate化すること
- mintrain1 sensitivityをglobal early-support relaxationとして採用すること
- tail-loss calibration不良のままtail-aware horizon scoreを標準policyにすること
- train support count gateだけでtail calibrationを直せたと扱うこと
- strict tail support gateをpolicy候補として扱うこと
- prior/OOB reliability scoreをそのままhorizon score multiplierとして標準policyにすること
- positive AUC/Spearmanを実行PnL上の正しいhorizon選択と同一視すること
- reliability-gated scoreがplain PnLと同点になっただけで改善と扱うこと
- post-hoc choice-delta上のswitch veto改善をstateful replay evidenceとして扱うこと
- `ranker_pred_pnl < 0` switch vetoをstateful replay前に標準policy化すること
- stateful replayでbestを改善しない `ranker_pred_pnl < 0` switch vetoを標準policy化すること
- `veto_chosen_pred_pnl_below_baseline` を名称の直感だけで採用すること
- positive predicted PnL failure ruleをpointwise candidate-surface診断だけでhard gate化すること
- stateful replayでno-opまたは悪化したpositive-PnL hard gateを標準policy化すること
- available-only fallback positive rowをedgeとして扱うこと
- actual fixed-best horizon targetを実行可能policy evidenceとして扱うこと
- actual-floor support repair runを実行可能policy evidenceとして扱うこと
- pred-only repair_score replayをpolicy候補として扱うこと
- horizon penalty `0.25` をchronological calibrationなしで標準policyにすること
- fallback0.25をlearned duration-penalty evidenceとして扱うこと
- support-repair対象行だけの疎なpriorでduration riskを学習できたと扱うこと
- broad duration priorの2024-08警告だけでdirect penaltyを標準化すること
- broad duration priorを勝ち候補保存なしで静的に差し引くこと
- low-complexity horizon-choice rankerのhigh totalだけを見て標準化すること
- fallback-allowed horizon ranker replayをpolicy evidenceとして扱うこと
- tail強化だけを次の本流修正として扱うこと
- stronger horizon penaltyをduration risk検証なしで採用すること
- lower-bound residual scoreを勝ち720m保存なしで標準scoreにすること
- tiny lower-bound no-opを改善として扱うこと
- harmful-overestimate probabilityをsupport objectiveなしで直接score penaltyにすること
- harmful head AUCだけを見てpolicy採用すること
- support-aware harmful scoreをEV/PnL列として混ぜ、EV gateを歪めること
- repair-side harmful probabilityのcontinuous scalar penaltyを標準policyにすること
- thresholded harmful penaltyのno-opを改善と扱うこと
- selected-addition近傍だけの薄いpairwise surfaceを学習policy evidenceとして扱うこと
- harmful-lower / tail-lower / support-proxy-higher switch ruleを標準policyにすること
- actual-oracle listwise selectorをpolicy evidenceとして扱うこと
- EV-2のlistwise oracle改善をfresh/thin month問題の解決と扱うこと
- `actual_pnl_at_hv_chosen_horizon` をoracle以外のselector tie-breakerへ混ぜること
- 00334のleak混入後current-vs-repair同値をpolicy evidenceとして扱うこと
- 00336のteacher AUCやoracle overlapを直接policy evidenceとして扱うこと
- singleton negative groupをlistwise rerankingで解けると扱うこと
- singleton_any abstentionを標準policyにすること
- 2 singleton事例だけでrisk-conditioned abstentionを標準policyにすること
- scenario-weighted singleton evidenceを独立サンプル数と誤読すること
- selected tail-pass `pred_pnl_lt2` をunique 1件支持のまま標準policyにすること
- `greedy_selected` row_scopeのloss 0をactual selected additionsのloss 0と誤読すること
- broad `selected_tail_pass_pred_pnl_lt2` をscenario悪化ありのままglobal hard gateにすること
- `singleton_720_pred_pnl_lt2` のstateful悪化0をNoTrade-first admission通過と誤読すること
- `needed_top_oracle_actual_*` を実行featureやselector tie-breakerに使うこと
- 候補0のthin targetをrerankingで解けると扱うこと
- support-sufficient negative monthを00318 thin-support laneへ無理に混ぜること
- 00370のconfig/variant inventory rowsを独立サンプルとして扱うこと
- realized monthly PnLで作ったtarget inventoryを実行時featureとして使うこと
- cross-artifact target identityのbaseline-positive月改善をcurrent negative-month repair成功として扱うこと
- winnerを外してreplacementで上回ったケースをloss-risk selector精度として扱うこと
- oracle loss selectionのbaseline-positive悪化を無視してrisk selectorだけを改善対象にすること
- winner-damage ranking上位を制約未通過のままpolicy候補として扱うこと
- abstain-all / no-intervention gateを利益改善として扱うこと
- `prior_actual_mean >=25` 系abstentionをtarget 1件支持のまま標準policy化すること
- broad target setで壊れなかっただけのabstention gateを複数target有効性と扱うこと
- fixed-horizon actual PnLを実行時featureとして使うこと
- `next_*` sequence diagnosticsを実行時featureとして使うこと

## 次にやること

1. `fresh2024 2024-11` はselected-onefailの狭いreplacement replayを作り、horizon/tail guard付きで検証する。
2. support-sufficient negative month laneは、current-branch negative repairとcross-artifact robustnessを分ける。00375で広いtarget setでもabstention gateは壊れなかったが介入は1件のままなので、次はcurrent-negative evaluated targetを増やせる別branch/artifact configを探す。
3. `fresh2024 2024-03` はfallback/non-model confidence featuresを作り、chronologicalに検証してからreplayへ戻す。
4. `singleton_720_pred_pnl_lt2` はnarrow diagnostic guardとして保持し、追加support-repair surface / chronologyで再検証する。標準policyにはしない。
5. Prior/OOB reliabilityをdirect scoreではなくhead selection / abstention / confidence reportとして使う。fresh03で見えたPnL / beats60 signalとtail-loss calibrationを分離し、tail penaltyはtrain countや単純multiplierではなく過去OOF信頼性の診断として扱う。
6. harmful probabilityをhorizon / side / session / regime / support bucket別にcalibrateし、global scalar penaltyや単純なharmful-lower switch ruleとして使わない。00350でwinner damageが確認されたcontextを先に分離し、00352のsupport countを踏まえてshrunk featureにする。
7. 00329/00335 leak-free bestのremaining weak months、特に `fresh2024 2024-03`, `fresh2024 2024-08`, `fresh2024 2024-11`, `refit2025 2025-03` を00331..00375 target labelsで診断する。単純fallback緩和、global early-support relaxation、train-count gate、reliability direct multiplier、stateful pred-pnl negative veto、positive-PnL hard gate/soft penalty、global harmful/residual/720m gate、薄いexact-context hard gate、coarse diagnosticだけのpositive-bias hard prefilter/soft penalty、tail-pass residual global hard gate、unique 1件支持のselected pred_pnl_lt2標準化、support-sufficient negative monthのthin-support混入、predicted fixed-horizon argmax直用、単一target月のone-fail replacement標準化、variant inventory countの独立サンプル化、baseline-positive targetのmean改善による標準化、oracleでも悪化するreplacement selectorの標準化、winner-damage ranking上位の制約未通過採用、target 1件だけのabstention gate標準化、広いtarget setで壊れなかっただけのgate標準化は本流にしない。
8. 00346でcandidate aggregate改善がbest replayへ転写されなかった理由を、admission gate / repair utility / overlap制約別に切り分ける。
9. `role_trades_low` と `side_share_high` を解く候補は、non-negative floor contributionを必須にし、EV-2の負け候補をsupport目的だけで入れない。
10. thin month / opposite-side supportを目的関数に明示し、単純なhorizon EV最大化だけでrepair targetが不変になる状態を避ける。
11. actual-floorは診断専用に残し、実行可能policyではobservable / learned proxyで代替する。
12. fallback0.25とfallback-allowed rankerはdiagnostic sensitivityとして維持し、learned evidenceや標準policy値として扱わない。
13. repair targetを候補比較の補助ゲートにする。totalが改善してもrepair targetが不変なら、標準化への前進とは扱わない。
14. Context-count shrinkageではなく、OOF calibrated EV uncertaintyをcontinuous featureとしてexpected PnLへ入れる。
15. entry-block候補は今後もholdout-support diagnosticsを通し、発火0件や1件支持ならhard blockへ昇格しない。
16. `large_loss_uncompensated_by_context` は教師候補として残し、entry/exit sequence features、replacement state、skipped next winner costと組み合わせる。
17. sequence-state診断の `next_*` はerror analysis専用にし、実行時featureは `prev_*`, 月内trade count, prior-only contextに限定する。
18. `isolated_large_loss_long + fixed720 + threshold -5 + replacement + require-model-used` はdiagnostic branchとして維持し、extension veto悪化とentry-time proxyのrefit集中も含めて標準policyにはしない。
18. role trade support、role PnL、month floor、side share、NoTrade-first比較を標準採用ゲートとして維持する。

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
43. `00300_2026-07-02_entry_ev_calibration_residual_context_diagnostics.md`
44. `00301_2026-07-02_entry_ev_prior_residual_pressure.md`
45. `00302_2026-07-02_entry_ev_prior_pressure_large_loss_head.md`
46. `00303_2026-07-02_entry_ev_path_compensation_diagnostics.md`
47. `00304_2026-07-02_entry_ev_uncompensated_loss_head.md`
48. `00305_2026-07-02_entry_ev_uncompensated_sequence_state.md`
49. `00306_2026-07-02_entry_ev_uncompensated_candidate_path.md`
50. `00307_2026-07-02_entry_ev_short_entryblock_replacement_replay.md`
51. `00308_2026-07-02_entry_ev_replacement_hold_extension_integration.md`
52. `00309_2026-07-02_entry_ev_hold_extension_veto_diagnostics.md`
53. `00310_2026-07-02_entry_ev_position_quality_proxy_overlay.md`
54. `00311_2026-07-02_entry_ev_position_quality_holdout_support.md`
55. `00312_2026-07-02_entry_ev_fixed60_prior_uncertainty.md`
56. `00313_2026-07-02_entry_ev_fixed60_prior_uncertainty_head.md`
57. `00314_2026-07-02_entry_ev_fixed60_uncertainty_soft_margin.md`
58. `00315_2026-07-02_entry_ev_fixed60_margin_trade_set_delta.md`
59. `00316_2026-07-02_entry_ev_fixed60_margin_prior_shrinkage.md`
60. `00317_2026-07-02_entry_ev_admission_repair_targets.md`
61. `00318_2026-07-02_entry_ev_thin_month_opposite_candidates.md`
62. `00319_2026-07-02_entry_ev_near_miss_exit_target.md`
63. `00320_2026-07-02_entry_ev_near_miss_exit_head.md`
64. `00321_2026-07-02_entry_ev_near_miss_horizon_viability.md`
65. `00322_2026-07-02_entry_ev_broad_horizon_viability.md`
66. `00323_2026-07-02_entry_ev_support_repair_horizon_replay.md`
67. `00324_2026-07-03_entry_ev_support_repair_target_coverage.md`
68. `00325_2026-07-03_entry_ev_target_aware_support_repair_replay.md`
69. `00326_2026-07-03_entry_ev_row_horizon_support_repair.md`
70. `00327_2026-07-03_entry_ev_horizon_duration_penalty_calibration.md`
71. `00328_2026-07-03_entry_ev_broad_duration_prior_repair_replay.md`
72. `00329_2026-07-03_entry_ev_broad_prior_horizon_choice_ranker.md`
73. `00330_2026-07-03_entry_ev_horizon_choice_lower_bound.md`
74. `00331_2026-07-03_entry_ev_harmful_overestimate_target.md`
75. `00332_2026-07-03_entry_ev_support_aware_harmful_objective.md`
76. `00333_2026-07-03_entry_ev_support_repair_pairwise_switch.md`
77. `00334_2026-07-03_entry_ev_support_repair_listwise_cluster.md`
78. `00335_2026-07-03_entry_ev_support_repair_leakfree_tiebreak.md`
79. `00336_2026-07-03_entry_ev_support_repair_listwise_teacher.md`
80. `00337_2026-07-03_entry_ev_support_repair_singleton_abstention.md`
81. `00338_2026-07-03_entry_ev_support_repair_singleton_surface.md`
82. `00339_2026-07-03_entry_ev_support_repair_thin_month_candidates.md`
83. `00340_2026-07-03_entry_ev_support_repair_target_local_confidence.md`
84. `00341_2026-07-03_entry_ev_horizon_confidence_support_audit.md`
85. `00342_2026-07-03_entry_ev_tail_support_gated_horizon_choice.md`
86. `00343_2026-07-03_entry_ev_prior_oob_reliability_horizon_choice.md`
87. `00344_2026-07-03_entry_ev_horizon_reliability_diagnostics.md`
88. `00345_2026-07-03_entry_ev_horizon_reliability_abstention.md`
89. `00346_2026-07-03_entry_ev_stateful_reliability_abstention_replay.md`
90. `00347_2026-07-03_entry_ev_positive_pnl_failure_diagnostics.md`
91. `00348_2026-07-03_entry_ev_positive_pnl_gate_stateful_replay.md`
92. `00349_2026-07-03_entry_ev_positive_pnl_soft_penalty_replay.md`
93. `00350_2026-07-03_entry_ev_over_gating_context_diagnostics.md`
94. `00351_2026-07-03_entry_ev_contextual_risk_confidence_diagnostics.md`
95. `00352_2026-07-03_entry_ev_context_support_count_diagnostics.md`
96. `00353_2026-07-03_entry_ev_context_hs_support2_positive_pnl_gate_replay.md`
97. `00354_2026-07-03_entry_ev_contextual_positive_pnl_soft_penalty_replay.md`
98. `00355_2026-07-03_entry_ev_contextual_penalty_near_selected_diagnostics.md`
99. `00356_2026-07-03_entry_ev_tail_ceiling_residual_failure_diagnostics.md`
100. `00357_2026-07-03_entry_ev_tail_selected_residual_diagnostics.md`
101. `00358_2026-07-03_entry_ev_selected_tail_pred_pnl_gate_replay.md`
102. `00359_2026-07-03_entry_ev_00358_thin_month_candidate_audit.md`
