# Current Assessment

最終更新: 2026-07-02 19:40 JST

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

## 現在の判断

| 項目 | 判断 |
|---|---|
| Standard policy | なし。NoTrade-firstを維持 |
| Current diagnostic candidate | q95 + raw `loss_exit30_cd15` dynamic exit cooldown + short entry-block replacement + fixed60 family-aware uncertainty margin w5 + require-model-used side-aware hold-extension + `long_range_normal_ny_fixed60_pred_gt0` position-quality overlay。00314で total `+339.2910` / month min `-0.7200` まで改善し、00315で改善源はrefit2025のremoved trade集中と確認した。00316でprior shrinkageはraw性能を落とすため採用しない。 |
| Why not standard | 00314 bestもmonth min `-0.7200` でNoTrade-first floorを通らず、standard admissionはmonth/role/month-trade/side-shareでblocked。default support-awareは `support_aware_only` だが、support2では `too_many_support_limited_negative_months`、shallow025では `structural_negative_months`。00311で `long_range_normal_ny_fixed60_pred_gt0` は未使用chronology支持がなく、00312の細粒度prior ruleもrefit集中をほぼ再現するだけでholdout発火0件。00313でfixed60 uncertainty headのAPは改善したが、high-risk除去は勝ちtradeを削る。00315で00314のw5改善もadded 0 / common_changed 0、全removedがrefit2025集中と分かり、00316で粗いpriorへ寄せても再現しなかったため、support/side/floor問題は残る。 |
| Useful signal | exit-regret / loss-first dynamic exit / replacement-stateful-net / same-side missed loss / low-capture loss / isolated large-loss capture failure / fixed-horizon improvement target / chronological hold-extension predicted delta / model-used-aware hold-extension replay / extension veto replay infrastructure / side-aware fixed horizon replay / stateful extension skip impact / selected-side capture ratio / short rollover loss-first block diagnostics / London short mid-loss block diagnostics / hold-extension false-positive block diagnostics / prediction-row entry-block flags / side EV penalty replacement replay / replacement->hold-extension integration diagnostics / entry-time position-quality proxy diagnostics / entry-block holdout-support diagnostics / fixed60 prior uncertainty diagnostics / fixed60 uncertainty head diagnostics / fixed60 uncertainty soft margin diagnostics / fixed60 prior shrinkage diagnostics / short-horizon predicted-vs-actual overestimate diagnostics / overlay residual floor support diagnostics / support-aware admission diagnostics / support-aware progression comparison diagnostics / month-warmup overlay diagnostics / confidence gate overlay diagnostics / confidence feature-bin diagnostics / chronological selected-trade calibration diagnostics / calibration residual context diagnostics / prior residual pressure diagnostics / chronological large-loss head diagnostics / path-aware large-loss compensation diagnostics / uncompensated path target diagnostics / uncompensated sequence-state diagnostics / uncompensated realized candidate-path diagnostics / supervised shrinkage and downside meta features |
| Main risk | 勝ちtrade削除、only-candidate replacement悪化、high-score losing tail、May/September tail、q99/q95 same-window selection、support緩和によるrole PnL崩壊、別familyでのPnL再現不足、no-replay改善をpolicy evidenceと誤読すること、1件/少数件blockを堅牢なedgeと誤読すること、extensionで直せない損失へextensionを無理に当てること、fallback hold-extension predictionでaggressive fixed720を開くこと、extension vetoをentry blockの代替と誤読すること、remaining sparse negative monthsを単発blacklistで追うこと、hindsight fixed-horizon rescueを実行可能policyと誤読すること、support-aware diagnostic passを標準admissionと誤読すること、month-warmupのsupport-aware passを改善と誤読すること、confidence gateの低活動floor改善を標準候補と誤読すること、calibration MAE改善をadmission改善と誤読すること、calibration residual contextをpost-hoc blacklist化すること、prior residual pressureの小幅改善を標準policyとして扱うこと、fixed60 prior ruleのrefit集中改善をhard gate化すること、prior shrinkageの低drawdownだけを見てtotal/month floor悪化を見落とすこと、large-loss classifier scoreをdirect hard gateとして扱うこと、positive context-monthをrisk scoreで丸ごと消すこと、uncompensated targetを孤立損失と誤読すること、target count最小化をpolicy objectiveにすること、realized path variant診断をfull replacement replay evidenceと誤読すること、raw cd15上のshort block replacement改善を00293 full comboの再現と誤読すること、全family一律short replacementを標準化すること、post-hold blockをentry-time executable policyと誤読すること、entry-time proxyのrefit集中を汎化edgeと誤読すること、holdoutで発火しないruleを再現ありと誤読すること、`next_*` 診断列を実行featureへ混ぜること、fixed-horizon actual PnLを実行featureへ混ぜること |

## 研究レーン

| レーン | Reports | 現状 |
|---|---|---|
| Short budget / side drift | `00174`..`00207` | budget0とside drift guardはtailを縮めるが、same-family / 2024 chronologyで標準化できず診断baseline止まり。 |
| Entry EV admission | `00208`..`00224` | raw/calibrated EV、rank、quantile、positive floor、hold-capを検証。NoTrade-first selectorは通らない。 |
| Executable EV / capture | `00225`..`00232` | executable EVやdense captureはrow-level改善があるが、stateful validationでtailとsupport不足が残る。 |
| Side balance / composite | `00233`..`00239` | side-balanceやcomposite hard gateでは候補が生まれず、component targetへ分解。 |
| Component / exit-regret | `00240`..`00316` | EV overestimateからdirection/exit/replacementへ分解。00267でq99 prior guardがstateful replay上は改善したが、標準admission未通過。00268でfresh support不足はepisode集中であり、rank0緩和はcal/refitを壊すと確認。00269の外部HGB、00270の外部full-hybridでもNoTrade未満。00271で損失はno-edgeではなくexit-capture failure / executable EV過大評価に寄ると確認。00272でpost-selector executable scoreは負の対照としてreject。00273でselector前capture補正もNoTrade未満。00274でcoarse `direction_regime` tail-riskはq99をプラス化したが、support/side集中でNoTrade。00275で外部HGB再現は弱く、tail-risk headはdiagnosticへ降格。00276/00277でlow loss-first dynamic exitが全role positiveまで進み、00278でcooldownが過剰回転を抑えた。00279のglobal quantile化はtotal改善と引き換えにtail/roleを壊し、policy候補にはしない。00280でraw cd15の残存損失はentry無価値ではなくexit-capture / EV過大評価が中心と確認。00281でprior capture factorのhard block/direct shrinkはreject。00282でsupervised shrinkageはscale補正として有効だが、direct gateはreject。00283でprediction-row shrinkage inputはaccepted、score replacementはreject。00284でdownside meta hard blockはreject、00285でdownside soft marginもreject。00286でstateful floor selectorを追加し、現候補群は全てNoTrade。00287でpost-exit pathを分解し、broad post-loss cooldownは勝ちを削ると確認。00288でisolated large-loss capture failureを特定し、一律fixed horizonはfloor悪化でreject。00289でhold-extension choice targetを学習し、`isolated_loss` training + `isolated_large_loss` threshold 5を次のfull replay候補にした。00290でstateful replayに接続しtotal改善は維持したがmonth floor未達でNoTrade。00291でside-aware fixed 720mはtotal/floorを改善。00292でhybrid 2025-12 shortをentry block overlayで消し、00293でrefit2025 2025-03/08 residual floorも縮めた。00294で残存floorはthin support中心と確認し、00295でsupport-aware admission診断へ分解。00296で候補系列横断でも00293だけがdefault `support_aware_only` だが、感度で落ちるため標準policyはNoTrade。00297でmonth-warmupはreject。00298でconfidence hard gateも低活動化またはfloor悪化でreject。00299でOOF calibrationはscale補正に有効だが、direct hard gateはreject。00300でcalibration residual contextを分解し、00301のprior-only residual pressure、00302のlarge-loss headはいずれもdirect gateとしてreject。00303でpath-aware補償を分解し、00304でuncompensated target headを試したが、現featureではpositive pathを分離できずdirect gateはreject。00305でuncompensated targetは高密度pathやnext winnerに埋まると確認。00306でrealized candidate path variantを比較し、target count最小化もreject。00307で未選択entry候補feed上のshort entry-block replacementを試し、raw cd15 totalは改善したがmonth floorとfamily再現は未解決。00308でreplacement pathへhold-extensionを統合し、require-model-used guardでfallback fixed720 tailを防いだ。00309でholdext false-positive blockをextension vetoに戻したが悪化。00310でentry-time observable position-quality proxyへ戻し、`long_range_normal_ny_fixed60_pred_gt0` はtotalを伸ばしたがrefit集中。00311で同ruleはholdout発火0件と確認し、hard block候補からfeature候補へ戻した。00312でfixed60 false-positiveをprior-only uncertainty feature化したが、細粒度ruleの改善はrefit集中の再現に留まるためhard gateにはしない。00313でuncertainty head化しAP改善を確認。00314でsoft marginへ戻し、preblockgap継承ありfamily-aware w5がdiagnostic bestを更新。00315でtrade-set deltaを監査し、改善源はrefit2025 removed tradeに集中すると確認。00316で粗いprior shrinkageを試したがraw性能が落ちたため、standard admissionはNoTrade。 |

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
- extension-veto-aware entry-block overlay grouping
- entry-time position-quality proxy overlay rules
- entry-block holdout-support diagnostics
- fixed60 prior uncertainty diagnostics
- fixed60 prior uncertainty head diagnostics
- fixed60 uncertainty soft-margin prediction-row input generation
- preblockgap side-gap quantile inheritance for score-head experiments
- trade-set delta diagnostics for score-head and entry-block comparisons
- fixed60 prior shrinkage diagnostics for score-head experiments

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
- fixed-horizon actual PnLを実行時featureとして使うこと
- `next_*` sequence diagnosticsを実行時featureとして使うこと

## 次にやること

1. Context-count shrinkageではなく、OOF calibrated EV uncertaintyをcontinuous featureとしてexpected PnLへ入れる。
2. support-limited negative monthsとside-share blockersを直接扱う。row削除だけでtotalを追わない。
3. entry-block候補は今後もholdout-support diagnosticsを通し、発火0件や1件支持ならhard blockへ昇格しない。
4. Short replacementは全family一律ではなく、family / regime / prior context supportで分割して再評価する。
5. `large_loss_uncompensated_by_context` は教師候補として残し、entry/exit sequence features、replacement state、skipped next winner costと組み合わせる。
6. large-loss probabilityとuncompensated-loss probabilityはhard gateではなく、candidate-level selector / stateful replay / exit timing targetの補助featureへ回す。
7. sequence-state診断の `next_*` はerror analysis専用にし、実行時featureは `prev_*`, 月内trade count, prior-only contextに限定する。
8. `isolated_large_loss_long + fixed720 + threshold -5 + replacement + require-model-used` はdiagnostic branchとして維持し、extension veto悪化とentry-time proxyのrefit集中も含めて標準policyにはしない。
9. support-aware分類を今後の候補比較に使うが、通過だけで標準化しない。
10. role trade support、role PnL、month floor、side share、NoTrade-first比較を標準採用ゲートとして維持する。

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
