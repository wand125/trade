# Current Assessment

最終更新: 2026-06-30 18:00 JST

## 結論

現時点では、標準採用できる利益最大化トレードpolicyはない。

ただし、研究は停滞していない。データ生成、backtest、OOF、walk-forward、candidate selection、trade delta、context guard、entry budget までの検証基盤は整っている。00207で全2024を同一chronological protocolへ揃え、混合family問題は解消した。00208では calibrated entry EV + 高いshort threshold が full 2024 testでNoTradeを超えたが、validationではNoTrade tieとしてしか選べていなかった。00209でNoTrade-first selectorを実装し、00210で `min_entry_rank` を明示したrank gate / support auditへ進めた。00211では追加refit foldで、support gateが十分なvalidation-positive候補を選んでも未来10ヶ月で大きく崩れることを確認した。00212でmulti-window selectorを実装し、単一2ヶ月validationではなく複数validation windowで候補を審査できるようにした。00213でside/regime/window gateの感度を振ったが、固定テストに耐える候補は出ていない。00214ではsparse high-rank fixed-positive rowもvalidation support不足と確認した。00215では既存artifactを棚卸しし、追加validationとして使える完全rank gridは `2024-03..04` と `2025-01..02` の2本だけだと確認した。00216で `2024-01..02` をfull rank化したが、これはcalibration-validationで、selectorの標準結論はNoTradeのまま。00217ではprediction入力側を診断し、cal2024はside margin supportがほぼなく、refit2025はlong EV scaleが極端に大きいというfold間scale driftを確認した。00218でquantile admission診断を追加し、side/regime/session-local quantileが候補数とside構成を比較可能にする有望軸だと確認した。00219でquantile列をstateful `timed_ev` backtestへ接続したが、cal2024のno-entry問題を解消する一方でfresh/refit validationのworst monthが負になり、標準採用には届かなかった。00220でrole-level selectorを追加し、fixed diagnosticを使わずにstrict3/clean2ともNoTradeになることを機械的に確認した。00221でpositive EV floorを事前登録候補として実装したが、floor `5/10` でもstrict3/clean2はNoTradeだった。00222では実tradeをrole/context別に分解し、q95/q99系はrefit2025のdirection error / exit regret、q90系はfresh2024の悪いshort contextが主な崩れだと確認した。00223でexit captureを診断し、q95/q99では `max_predicted_hold=260m` が強くbindingしている一方、oracle best holdingはさらに長いことを確認した。00224でhold-cap sensitivityを実行し、`720m` はexit capture改善軸として有望だが、same-validation context-side guardなし/ありのどちらでもNoTrade-first gateは通らないと確認した。00225でprior-only inversion guardへ置き換えたところ、validationでは `720m q95_floor5` が `+139.0422 / min month -0.4914` まで改善したが、fresh fixed diagnosticでは guard が良い取引も削ったため標準採用しない。00226でprior context risk scoreを追加し、cal+fresh priorなら fresh fixed `720m q95_floor5` が `+402.1118 -> +427.6524` へ改善したが、min month `-9.1718` が残るため標準採用しない。00227で残った `2024-03` をtrade単位に分解し、同月の失敗はentry floor不足ではなく、direction-side inversion、exit capture、realized-executable EV calibration不足だと確認した。00228でexit-capture failureをtarget化し、prior exit risk hard blockはfresh q95/720 fixedで大きく利益を削ると確認した。00229でexecutable EV calibrationを追加し、raw EVの過大評価は大きく縮むがhard thresholdはwindow間で不安定だと確認した。00230でcandidate-level selector featureに戻してもNoTrade-firstの結論は変わらなかった。現在の主課題は「固定testをvalidationへ流用せずにmulti-window admission evidenceを増やすこと」と「post-trade selectorではなくstateful entry ranking / replacement choiceにexecutable EVを入れること」。

採用判断は、全期間を見たbestではなく、prior-only / chronological / fresh apply で壊れないかを優先する。

## 現在の主要評価

| 系列 | 現状 | 代表結果 | 判断 |
|---|---|---|---|
| Holding max cap | `250..260m` はholding安定化候補 | 2025-01..08 coststress `260m` は total `+458.9738`。fresh 2025-09..12 は `260m` でも `-839.2544` | 標準採用しない。fresh失敗はholdingではなくside drift |
| Full-2024 chronological protocol | 00206の混合familyを解消したcanonical 2024 artifact | 2024-05..12 OOF比較で source p10/replm10 が最良だが total `-3.1736`。risk5 side `-10.4618`、risk0 side `-32.7828`、risk0 no-side `-141.8816` | 標準採用なし。NoTrade超えまでdiagnostic |
| Entry EV calibrated admission | raw EV thresholdの過適合を診断し、calibrated EVの高threshold候補を固定testした | raw validation `entry12/short3` は `+22.7292` だが full 2024 test `-442.4662`。calibrated `entry10/short6` は test `+100.3612`, worst `-43.2296`, trades `60`; `entry12/short6` は `+74.0644`, worst `-37.8326`, trades `26` | 診断候補。validationではNoTrade tieなので標準採用しない |
| Entry EV NoTrade selector | validation-positiveでなければ標準はNoTradeにするselectorを実装 | Fresh `2024-03..04` validation bestは calibrated `entry12/short6` の `-1.8610`。standard selectorはNoTrade。diagnostic fixed testは `+65.4014`, worst `-37.8326`, trades `19` だが、00210で `min_rank0.5` 入りと訂正 | selectorはaccepted infrastructure。`cal12/short6/min_rank0.5` は診断候補のみ |
| Entry EV rank gate support | `min_entry_rank` を明示grid化し、support gateを追加 | Fresh `2024-03..04` bestは `entry10/short9/min_rank0.0` の `+17.0910`, worst `+0.7230`, trades `4`。`min_trades=10`, active2, worst0ではNoTrade。Fixed `2024-05..12` は同row `+87.8942`, worst `-2.2800`, trades `10`; `entry8/short9/min_rank0.6` は `+74.2970`, worst `-20.1600`, trades `11` | rankはdiagnostic admission axis。support不足で標準採用しない |
| Entry EV rank refit 2025 | 追加model-refit foldでsupport gateを検証 | train `2024`, validation `2025-01..02`, test `2025-03..12`。support gateは `entry12/short3/min_rank0.0` を validation `+209.4234`, worst `+71.1950`, trades `170` で選ぶが、fixed testは `-1002.1534`, worst `-294.1980`, trades `1147`。test hindsight top `entry14/short9/min_rank0.7` は `+324.5040` だがvalidation 0 trades | 標準採用なし。2ヶ月validationではregime代表性が足りない |
| Entry EV multi-window selector | 複数validation windowでNoTrade-first selectionできるようにした | fresh2024 + refit2025のstrict gateはNoTrade。relaxed gateは `entry10/short9/min_rank0.0` を validation `+190.4544`, trades `173` で選ぶが、fixed tests `2024-05..12 + 2025-03..12` では `-943.9322`。`max_side_trade_share<=0.95` ではNoTrade | accepted infrastructure。標準policyはNoTrade |
| Entry EV gate sensitivity | side/regime/window support gateをgrid評価した | `576` gate中 `568` はNoTrade、`8` は全て `entry10/short9/min_rank0.0` を選び fixed tests `-943.9322`。`max_side_trade_share<=0.95`, `min_window_trades=10`, `min_combined_regime_pnl>=-50` は全てNoTrade | accepted infrastructure。閾値調整だけでは汎化候補なし |
| Entry EV sparse rank diagnostics | fixed-positive sparse high-rank rowをvalidation evidenceだけで診断した | `72` candidates中 validation eligible `0`。fixed-positiveは `entry14/short9/min_rank0.6` だけだが、validation total `-0.3844`, trades `3`, min window trades `0`, side share `1.0000`; fresh2024は0 trade | accepted infrastructure。sparse high-rank rowは現validationでは採用不可 |
| Entry EV validation inventory | 既存rank sweep artifactのvalidation再利用可否を棚卸し | `39` metrics files中、full-rank validation candidateは fresh2024 `2024-03..04` と refit2025 `2025-01..02` の2本だけ。`2025-03..12` はfull rankだがfixed test、`2024-05..12` はfixed testかつpartial rank | accepted infrastructure。固定testをvalidationへ流用せず、新foldかrank sweep再生成が必要 |
| Entry EV cal2024 rank window | `2024-01..02` をfull rank gridへ再生成し3-window selectorへ追加 | cal2024は `144` rows, trades `8`, total `-70.3272`。strict 3-window supportはNoTrade。relaxedでは同じ `entry10/short9/min_rank0.0`、side095ではNoTrade | accepted artifact。calibration-validationであり、support増加や標準採用にはならない |
| Entry EV admission input diagnostics | prediction row側でEV scale、side gap、rank、holding validity、stateless entry countを診断 | cal2024は `56,077` rows中 `side_gap>=5` が `11` だけで、`entry10/short9/min_rank0.0` は0 entry。refit2025は同configで `29,567` entries、うち `29,522` long。`entry14/short9/min_rank0.6` はfresh2024 0 entry、refit2025 25 long-only | accepted infrastructure。絶対EV thresholdのscale driftが主因。標準policyはNoTrade |
| Entry EV scale quantile diagnostics | raw/calibrated EV、side gap、rankをlocal quantile化し、fold間候補数を比較 | calibrated selected score q95は cal `11.16..11.22`, fresh `12.08..15.86`, refit `23.52..23.73`。`side_regime_session_month` q99/q95/rank90 gateは cal `41`, fresh `316`, refit `32` entries | accepted infrastructure。次はquantile列をstateful backtestへ接続。標準policyはNoTrade |
| Entry EV quantile policy backtest | quantile admissionを `timed_ev` stateful backtestへ接続 | `side_regime_session_month` q99/q95/rank90は cal2024 `+6.2048`, worst `+1.8830`, trades `14`。fresh validationは total `+34.2940` だが worst `-12.4240`、refit validationは total `-27.9456`。q95はrefit `-23.2338`、rank0はfresh validation `-70.7894` | accepted infrastructure。候補数正規化は有効だがPnL汎化は未達。標準policyはNoTrade |
| Entry EV quantile role selector | quantile monthly metricsをvalidation roleだけでNoTrade-first選択 | strict3はNoTrade。clean2もNoTrade。clean2の絶対閾値baselineは total `+254.7066`, min role `+16.1220`, min month `+1.0490` だが role trades low と side share `0.9595` で落ちる | accepted infrastructure。fixed diagnosticを選択に使わない。標準policyはNoTrade |
| Entry EV quantile positive floor | quantile gateに小さなselected EV floorを事前登録候補として追加 | floor `5/10`, score q `90/95/99`, side gap q `90/95`, rank q90の8候補。strict3/clean2ともNoTrade。`q95 floor10` はfresh validation worstを `-3.6326 -> -1.6462` に改善するがrefit validationは `-23.6438` | floor syntaxはaccepted infrastructure。現floor候補は標準採用しない |
| Entry EV quantile trade context diagnostics | quantile/floor候補の実tradeをrole/context別に再結合 | q95/q99系はworst roleがrefit2025。q95 floor10 refitは total `-23.6438`, direction error `0.4643`, exit regret `572.3960`。q90系はfresh2024がworst。worst contextは refit short `range_normal_vol/ny_overlap` total `-256.8672`, direction error `1.0` | accepted infrastructure。entry floorではなくcontext-side inversionとexit captureを分けて見る |
| Entry EV quantile exit capture diagnostics | q95/q99 selected tradesのholding capとoracle holdingを比較 | q95 fresh early-exit rate `0.7895`, cap-hit `0.9474`, policy hold - oracle `-412.0192`; q95 refit early-exit `0.7857..0.7931`, cap-hit `0.9286..0.9310`, policy hold - oracle `-593.6399..-675.9972`; q99 cal early-exit `1.0` | accepted infrastructure。blind hold cap延長は不可。context-side inversion guardとhold-cap sensitivityを分ける |
| Entry EV quantile hold-cap sensitivity | q95/q99候補で `260/480/720/1440m` capとdiagnostic inversion guardを比較 | no-guard `q95_floor5`: `260m -5.6974 / min role -23.2338`, `720m +117.0340 / min role +16.2628` だが min month `-9.1718`。diagnostic guard min1 `720m q95_floor5` は `+273.6662 / min role +27.7034`; support>=4 guardでも `+235.0452 / min role +25.3464`。全て `month_pnl_below_floor` | accepted infrastructure。`720m` は次の診断cap。same-validation guardと候補policyは標準採用しない |
| Entry EV quantile prior inversion guard | same-validation guardを対象月より前のselected-trade context実績だけで作る `prior_inversion` modeへ置換 | fast prior `720m q95_floor5` は validation `+139.0422 / min role +17.7308 / min month -0.4914`。fresh fixedでは no-guard `720m` `+402.1118 / min role +76.2204` に対し prior guard `+373.4814 / min role +2.0982` | prior-only guard infrastructureはaccepted。現blocking ruleはover-blocking気味なので標準採用しない |
| Entry EV prior context risk score | prior context-side evidenceをscore化し、pointwise診断とstateful `prior_risk` guardで検証 | validation q95_floor5/720mは `+117.0340 -> +133.2270`。fresh-only prior fixedは `+402.1118 -> +396.0818`、cal+fresh prior fixedは `+427.6524`。min month `-9.1718` は残る | risk diagnostics, `prior_risk`, `--prior-roles` はaccepted infrastructure。標準採用しない |
| Entry EV residual 2024-03 loss diagnostics | q95_floor5/720mで残った fresh `2024-03` の負け月をtrade単位で分解 | 18 trades total `-9.1718`。same-side oracle total `+327.9840`, actual best total `+485.5670`, `no_edge_entry=0`。direction error 7件 / `-46.3626`, large exit regret 13件 / `-30.5188`, prior risk `>=0.50` 0件 | accepted diagnostic。entry floorではなくdirection-side inversion、exit capture、realized EV calibrationへ戻す |
| Entry EV exit capture target diagnostics | same-side oracle利益を実現できないtradeをtarget化し、prior-only context riskを診断 | validation q95/q99では exit_capture_failure rateが refit `0.8621..0.8929`, fresh q95 `0.8421`。`risk>=0.20` はvalidationで68 trades / `-23.1116` を拾うが、fresh q95/720 fixedでは77 trades / `+225.3034` を消す | target/feature infrastructureはaccepted。prior exit risk hard blockは標準採用しない |
| Entry EV executable EV calibration | prior-only capture factorで raw predicted EV を現exit policyで実現可能なEVへ割り引く | validation q95/q99では refit MAE `20.8969..22.0208 -> 7.3980..7.6244`、fresh q95 `13.9256 -> 6.1870`。fresh q95/720でも validation `14.7507 -> 8.4237`, fixed `13.4582 -> 7.0417`。ただし threshold `2/3` はwindow間で符号反転 | accepted continuous feature。hard thresholdは標準採用しない |
| Entry EV executable EV selector feature | executable EVをcandidate-level NoTrade-first selector featureとして評価 | validation q95/q99はq99が `capture_ev_mean > 5` だが refit/month floorsでNoTrade。fresh q95/720は validation total `+76.2204`, fixed total `+325.8914` でも validation min month `-9.1718` でNoTrade | accepted diagnostic。post-trade selectorでは昇格せず、stateful entry rankingへ移す |
| Side drift guard | prior-onlyで悪いshort contextを検出できるが、short-only抑制では残存riskがlongや良いshort削除へ移る | strict short p10 + admission margin10 は 2025-01..12 total `-90.1378`。00205では `2025-04..06` raw EV short bias `+0.27..+0.30` を確認。00207の全2024 OOFではsourceが相対最良でも total `-3.1736` | 診断baseline。side/EV calibration preflightとして使い、単独policy化しない |
| Residual short failure | 残存損失はほぼshort | p10 + margin10 の負け月で short `-716.6702`、long `-8.4414` | 次はshort側のreplacement riskと初回損失制御 |
| Online context drawdown | realized lossだけで発火できる | prior-only `worst` + margin-aware は min4 total `+69.9374`、min8 total `-199.4438` | risk mandate候補。利益最大化policyではない |
| Short raw gap guard | 介入対象の発見には有効 | all-window bestは total `+18.5106` だが prior-only min4 `-274.9360` | 単独採用しない |
| Short entry budget / budget0 | active short contextを完全stay-flat化できるが、固定適用では期間依存が残る | 2025 all-window `gap5/budget0` total `+508.9838`、2024-11..2025-04 smoke `+445.8266`。一方、2024-11..2025-08の追加same-familyでは10ヶ月 `+384.6968` でも、追加apply 2025-05..08だけは `+13.9434` でsource `+66.7730` とbaseline `+176.8236` に負けた | `gap5/budget0` も標準採用しない。diagnostic baseline / intervention locatorへ降格 |
| Online context feature | post-filterでは損失説明力あり | context特徴追加はOOF AUCを改善せず。min8 large_loss AUC `0.5523 -> 0.5364` | raw feature昇格なし |
| Cooldown / recovery | hard blockの緩和 | cooldown/recoveryはprior-onlyで既存hard block系に負ける | 採用しない |

## 採用状態

採用済みインフラ:

- leak-aware dataset / label生成
- executable monthly backtest
- cost stress、loss multiplier `1.20`
- OOF / chronological / walk-forward検証
- `model-trade-delta` 系の差分診断
- side drift / residual failure / online context state 診断
- side EV penalty、admission margin、context drawdown guard、entry budget hook

診断baselineとして残すもの:

- `p10 + admission margin10`
- side-month online drawdown guard の prior-only `worst` objective
- short budget `defensive_budget` / fixed `gap0/budget0`
- short budget drift trigger `gap5/budget0 -> gap0/budget0`
- fixed short budget trigger audit `gap5/budget0 -> gap0/budget0`
- prediction side drift trigger metrics as diagnostics only
- context alert composite trigger as explanation of 00191
- alert-context budget/admission hook as diagnostics only
- alert-context first-loss / fast-stop as diagnostics only
- budget0 replacement-path decomposition as candidate adoption preflight
- replacement prior signal audit as preflight, not dynamic policy
- focused entry-level residual signal audit as preflight, not dynamic policy
- focus entry dynamic hook as diagnostics only
- replacement risk target diagnostics
- triggered replacement profit-miss hook as diagnostic candidate after same-family smoke failure
- `gap5/budget0` as diagnostic baseline / intervention locator after additional same-family apply failure
- same-family side calibration diagnostics as required preflight before adding side hooks
- early-2024 chronological risk OOF bridge artifact
- full-2024 chronological HGB+MLP artifact as canonical 2024 comparison input
- calibrated entry EV high-threshold candidates `entry10/short6` and `entry12/short6` as fresh-fold diagnostic candidates only
- entry EV NoTrade-first selector as accepted infrastructure
- calibrated `entry12/short6/min_rank0.5` as diagnostic low-frequency candidate only after 00209 correction
- entry EV rank gate and support gates as diagnostic admission infrastructure
- `entry10/short9/min_rank0.0` and `entry8/short9/min_rank0.6` as low-support diagnostic rows only
- 2025-refit entry EV rank fold as admission validation-design stress test
- test hindsight `entry14/short9/min_rank0.7` as sparse short-only diagnostic clue, not selectable policy
- multi-window entry EV admission selector
- window-level trade support and side-balance rejection gates as diagnostics
- entry EV gate sensitivity infrastructure
- sparse high-rank diagnostic infrastructure
- entry EV validation inventory infrastructure
- cal2024 full-rank calibration-validation artifact
- entry EV admission input diagnostics
- entry EV scale quantile diagnostics
- entry EV quantile policy backtest infrastructure
- entry EV quantile role selector
- entry EV quantile positive floor candidate syntax
- entry EV quantile trade context diagnostics
- entry EV quantile exit capture diagnostics
- entry EV quantile hold-cap sensitivity
- entry EV quantile prior-only inversion guard infrastructure
- entry EV prior context risk score diagnostics
- `prior_risk` guard mode and `--prior-roles`
- entry EV residual month loss diagnostics
- entry EV exit-capture target diagnostics
- entry EV executable EV calibration diagnostics
- entry EV executable EV selector feature diagnostics
- holding max `250..260m` sensitivity
- `signal_short_raw_gap` as intervention locator

標準採用しないもの:

- all-windowだけで選ばれた `threshold=40/60` や `gap5/th20/m20`
- static session/regime hard block
- raw probability threshold直結の holding shortening
- global side-confidence gate
- profit-barrier hard gate / linear penalty
- selected-trade quality hard gate / direct EV replacement
- cooldown / recovery based online guard
- raw online context stateの標準feature追加
- monthly prediction-share triggerの直接採用
- context alert count / loss-bias triggerの直接採用
- alert context限定budget/admissionの標準採用
- alert context限定first-loss / fast-stopの標準採用
- focus entry OR / side-gap-only dynamic hookの標準採用
- raw EV validation winners as direct admission policies
- calibrated EV high-threshold candidates as standard policies before fresh-fold validation
- diagnostic near-NoTrade candidate as standard policy when validation total is non-positive
- low-support rank-gated candidate as standard policy when validation trades are below the support gate
- support-gate-passing `entry12/short3/min_rank0.0` from the 2025-refit fold, because future test was `-1002.1534`
- relaxed multi-window `entry10/short9/min_rank0.0`, because fixed tests were `-943.9322`
- all gate-sensitivity variants selecting `entry10/short9/min_rank0.0`, because their fixed tests are also `-943.9322`
- sparse fixed-positive `entry14/short9/min_rank0.6`, because validation total is negative, one validation window has zero trades, and observed validation trades are long-only
- reusing existing fixed-test artifacts as validation windows without reserving a new outer test
- `max_side_trade_share=0.95` as a frozen standard threshold before testing more windows
- absolute calibrated EV thresholds as a sufficient cross-fold admission scale without side/regime-local normalization
- quantile gates as standard policies before stateful backtest and fixed-window audit
- tested quantile gates as standard policies after 00219, because validation roles still include negative worst months
- absolute EV baseline after 00220 clean2, because role trades and side concentration fail despite positive PnL
- positive EV floor candidates after 00221, because all candidates fail role/month PnL floors
- more floor tuning after 00222, because selected trade failures split into role-specific side inversion and exit capture, not a scalar EV floor problem
- blind `max_predicted_hold` extension after 00223, because exit capture improves only if direction/context risk is controlled
- same-validation diagnostic inversion guard after 00224, because it is a hypothesis generator and still fails month-level NoTrade gates
- current prior inversion guard after 00225, because the validation near-pass still has a negative month and the fresh fixed diagnostic shows over-blocking
- current `prior_risk` guard after 00226, because even the better cal+fresh prior fixed diagnostic still leaves a negative month and lacks enough chronological validation evidence
- lowering `prior_context_risk` threshold to `0.20` based on the 00227 residual month, because it is a local hindsight sensitivity and broader context block side effects are already known
- hard blocking by `prior_exit_capture_risk_score` after 00228, because validation gains do not survive the fresh q95/720 fixed window and the score deletes large positive realized PnL
- hard thresholding on `pred_capture_calibrated_ev` after 00229, because threshold `2/3/5` is not stable between validation q95/q99 and fresh q95/720 fixed
- promoting candidates from executable EV feature cleanliness after 00230, because NoTrade-first role/month PnL gates still fail

## 中心的な失敗構造

2025-09..12 の fresh failure では、dense label distribution は long 寄りなのに、raw EV prediction と実行tradeが short 寄りになる。

代表的な症状:

- fresh 2025-09..12 の mean short overprediction は `+0.4143`
- selected short PnL は `-704.9300`、long PnL は `-134.3244`
- worst contextは `short/range_low_vol` 周辺、特に `ny_overlap`, `rollover`, `asia`
- confidenceやside gapだけでは除外できない
- guard後も replacement short が残り、損失の尾部を作る
- alert contextだけを止めても late common short `-382.7524` と replacement short `-293.7604` が残る
- `gap5` replacement shortのうち `up_low_vol/ny_overlap` は prior prediction biasで拾える。`range_low_vol/ny_overlap` は prior context signalでは拾いにくいが、entry-level side gap / rank signalを足すと大半を事前説明できる。ただしdynamic hookではreplacementが再発し、OR条件は小幅悪化した
- replacementは全期間では利益にもなるため、global hard gateは危険。late bad regimeでは `profit_hit_lt0p5` が強いが全期間では良いreplacementを消す。prior deterioration triggerと `min_prior_months=4` を加えたdynamic hookは2025 all-windowで `+790.3634` まで改善したが、2024-11..2025-04 same-family smokeでは勝ちを削った
- `gap5/budget0` 単体も、2024-11..2025-08の追加same-familyでは10ヶ月合計でsourceを上回るが、追加apply 2025-05..08だけではsourceとbaselineに負ける。特に2025-06の勝ちを削るため、同じ2025系列でshort hookを重ねるのは過適合になりやすい
- 00205では、raw EV short biasは明確だが、`gap5/budget0` 後の最大損失は `2025-07 down_low_vol/ny_overlap long -97.4172` などlong側にも移ると確認した。direction errorやEV overestimateの平均が少し良くても、PnL採用根拠にはならない
- 00206で早期2024のrisk OOFを `2024-05` まで前倒しし、00207で全2024を同一chronological protocolへ揃えた。全2024 OOFではsource p10/replm10が相対最良だが total `-3.1736` でNoTradeを超えず、side/risk hookの標準採用根拠にはならない
- 00208でraw EV thresholdのvalidation過適合が明確になった。calibrated EV + 高いshort thresholdはfull 2024 testで positive PnLを出したが、validationではNoTrade tieだったため、test-set selectionを避けるにはfresh chronological foldとNoTrade tie selectorが必要
- 00209でNoTrade-first selectorを実装した。fresh `2024-03..04` validationでは best calibrated `entry12/short6` も `-1.8610` でNoTrade未満なので、標準selectorはNoTradeを選ぶ。diagnostic fixed test `2024-05..12` は `+65.4014` だが、validation-negative候補なので標準採用しない
- 00210で00209のfixed testは `min_entry_rank=0.5` 入りだったと訂正し、rank gateを明示grid化した。fresh validationでbest `entry10/short9/min_rank0.0` は positive だが4 tradesしかない。月10trades相当のsupport gateではNoTradeを返すため、rank gateは有望な診断軸であって標準policyではない
- 00211で、追加refit foldでは逆にsupport gateを十分満たすrowが未来で壊れた。`2025-01..02` validationで `entry12/short3/min_rank0.0` は `+209.4234`, trades `170` だったが、`2025-03..12` testは `-1002.1534`。これはsupport不足ではなくvalidation windowのrepresentativeness不足で、2ヶ月validationだけでは未来regimeの防波堤にならない
- test hindsightの `entry14/short9/min_rank0.7` は `+324.5040` だがvalidation 0 tradesであり、選ぶとtest leakageになる。高rank short-only sparse entryは診断軸として残すが、selection ruleには使わない
- 00212でmulti-window selectorを実装した。fresh2024 + refit2025を同時に見ると、strict support gateはNoTrade。relaxed gateは `entry10/short9/min_rank0.0` を選ぶが、fixed testsで `-943.9322` へ崩れる。side share `0.9595` なので `max_side_trade_share<=0.95` ならNoTradeになるが、この閾値はまだ診断であり標準固定しない
- 00213でside/regime/window gate感度を576通り確認したが、policyを選ぶ8 gateは全て同じ崩壊候補だった。`max_side_trade_share<=0.95`, `min_window_trades=10`, `min_combined_regime_pnl>=-50` は全てNoTrade。fixed-test-positiveの `entry14/short9/min_rank0.6` はvalidation-negativeかつzero-support windowありなので、採用するとhindsightになる
- 00214で `entry14/short9/min_rank0.6` を詳しく見ると、fresh2024は0 trade、refit2025は3 long-only tradesで `-0.3844`。これは「validationで薄く良いsignal」ではなく「validationで未観測のhindsight-positive」。sparse high-rank rowsを扱うには追加validation windowsか、fixed-test PnLなしで支持されるside/regime-aware rank校正が必要
- 両fixed test windowに存在するconfigだけのhindsight topでも `entry14/short9/min_rank0.6` total `+98.9868`, worst `-133.6912` で、robust standardには遠い
- 00217でprediction row入力側を診断すると、cal2024はholding validityではなく `side_gap>=5` が `11 / 56,077` しかないことで高threshold候補が消える。一方、refit2025はlong EV scaleが大きく `entry10/short9/min_rank0.0` で `29,522` long entriesを出す。したがって絶対EV閾値をそのままfold横断のadmission scaleにするのは危険
- 00218でfold内quantileに変換するとcal2024のno-entry問題は解消し、`side_regime_session_month` q99/q95/rank90では cal2024 `41`, fresh2024 `316`, refit2025 `32` entriesまで候補数が近づく。ただしこれはstateless候補数であり、PnL edgeではない
- 00219でquantile列をstateful `timed_ev` へ接続した。`side_regime_session_month` q99/q95/rank90はcal2024では `+6.2048` と機能したが、fresh2024 validation worst `-12.4240`、refit2025 validation total `-27.9456` で標準採用不可。q95はfresh fixed diagnosticで強いがrefit validationで負け、rank0はrefitで強くてもfresh validationで大きく壊れる
- 00220でrole-level selectorを追加した。strict3/clean2ともNoTradeで、clean2の絶対閾値baselineも `role_trades_low` と `side_share_high` で落ちる。fixed diagnostic PnLは選択に使わず、後段監査に分離する
- 00221でpositive EV floorを事前登録候補として試した。floor10はfreshを少し改善するがrefitの負けを解けず、q90 score quantileはfresh tailを悪化させる。失敗は「EVが正か」だけではなく、role/regime instabilityに残っている
- 00222で実tradeをrole/context別に再結合した。q95/q99系のrefit負けはno-edge率が低く、direction errorとexit regretが大きい。fresh q95は平均ではoracle EV過大評価ではなく、entryに利益余地があってもrealized exitで取り逃している。q90 relaxationはfreshの悪いshort contextを増やす
- 00223でq95/q99のexit captureを診断した。MLP raw holdingは長いが `max_predicted_hold=260m` でcapされ、oracle best holdingより大幅に短い。early exit rateは多くのroleで `0.75` 以上。ただしrefit負けにはdirection/context errorも混ざるため、cap延長だけでは危険
- 00224でhold-cap sensitivityを実行した。`720m` はno-guardでもrole totalsを改善し、diagnostic inversion guardありでは全role positiveになる。ただしfresh `2024-03` などの月別tailは残り、全候補が `month_pnl_below_floor` で落ちる。same-validation guardは採用ルールではなく、prior-only inversion detectorを作るための仮説である
- 00225でprior-only inversion guardへ置き換えた。fast priorでは `720m q95_floor5` が validation `+139.0422`, min month `-0.4914` まで近づいたが、fresh fixedでは no-guard `720m` の方が `+402.1118 / min role +76.2204` と強く、prior guardは `+373.4814 / min role +2.0982` へ落ちた。したがって現guardは悪いcontextを拾う一方で良い取引も削る
- 00226でrisk score化した。pointwiseにはbroad hard flagがvalidationで `-84.6872` の損失を拾うがfresh q95の良いtradeも消す。`risk_score>=0.50` は狭く、stateful validationで q95_floor5/720mを `+133.2270` に改善した。fresh fixedではprior rolesをfreshだけにすると小幅悪化、cal+freshに広げると `+427.6524` へ改善する。ただし `2024-03` の負けは残る
- 00227で残った `2024-03` は、18 tradesすべてにsame-side oracle edgeがあり、`no_edge_entry=0`。loss 7件は全てsame-side oracle edgeを持ち、direction error 7件とlarge exit regret 13件が重なる。したがって単純なentry抑制ではなく、direction-side inversion target、exit timing target、realized-executable EV calibrationへ戻す必要がある
- 00228でexit-capture failureをtarget化した。target prevalenceは高く、refit負けroleでもfresh勝ちroleでも頻出する。prior exit riskはvalidation q95/q99では `risk>=0.20` が損失を拾うが、fresh q95/720 fixedでは同じthresholdが `+225.3034` の利益を消す。よってtargetは学習・校正に使い、hard blockにはしない
- 00229でexecutable EV calibrationを行うと、raw EVの過大評価は一貫して縮む。fresh q95/720 fixedでもMAEは `13.4582 -> 7.0417`。しかし低calibrated EV thresholdはwindow間で符号が反転するため、calibrated EVはcontinuous featureとして使い、単独thresholdにしない
- 00230でcandidate-level selector featureとして戻しても、NoTrade-first gatesは通らない。q99はexecutable EV featureが相対的に良いがrefit/month floorsで落ち、q95/720はfixedでは強いがvalidation `2024-03` が負。次はpost-trade candidate selectorではなく、entry時点のranking/replacement choiceで使う必要がある

したがって、次の改善は「holding capの再探索」でも「floor閾値の細密探索」でもなく、entry EV calibration、rank/quantile admission control、prior-only context-side inversion、exit captureを、より多いchronological validation window / purged walk-forward / regime別安定性評価へ分解して進めることを優先する。

## 次に検証すべきこと

1. Entry admission reviewは `--multi-window` selector、gate sensitivity、sparse-rank blocker診断を標準入口にする。単一2ヶ月validationだけで標準候補を選ばない。
2. 2025系列でshort hookをさらに積む前に、source policy自体のside prediction calibrationとregime別崩れを再評価する。
3. `pred_short_profit_barrier_hit` を0/1ではなく確率または校正済み確率に差し替えてから、profit-miss系hookを再評価する。
4. raw EVやcalibrated EVの絶対値ではなく、side/regime別のrank、calibrated EV quantile、side gap quantile、support-aware thresholdをadmission特徴として評価し、より多いvalidation windowでtotal、worst、trade support、side balance、regime worst bucketがNoTradeを超えるかを見る。00219/00221のquantile/floor候補は標準採用せず、00222のcontext診断を使ってside inversionとexit captureを分離する。
5. 00226..00229の prior risk / executable EV系はインフラとして残すが、現blocking ruleと局所threshold低下は標準採用しない。次はprior rolesを事前固定した複数chronological windowで、risk scoreやcapture-calibrated EVをhard blockではなくrank特徴やselector featureとして評価する。
6. side prior driftを、predicted side share vs dense label side share の prior window差分で補正する。
7. 新しいcandidateは必ず NoTrade、previous diagnostic baseline、cost stress、worst month、max DD、short PnLで比較する。

## 読むべき代表レポート

- `00174`: fresh 2025-09..12 の holding cap失敗とside drift露呈
- `00175`: side drift diagnostics
- `00178`: side drift guard + admission margin
- `00179`: residual short failure diagnostics
- `00182`: context drawdown margin-aware prior selection
- `00187`: short raw gap context guard
- `00188`: short entry budget guard
- `00189`: short budget selection
- `00190`: context entry budget zero
- `00191`: short budget drift trigger
- `00192`: prediction side drift trigger
- `00193`: context alert budget trigger
- `00194`: alert context budget admission
- `00195`: alert context first loss cap
- `00196`: budget0 replacement path diagnostics
- `00197`: fixed short budget trigger audit
- `00198`: replacement prior signal audit
- `00199`: entry signal residual context audit
- `00200`: focus entry dynamic hook
- `00201`: replacement risk target diagnostics
- `00202`: triggered replacement risk hook
- `00203`: triggered profit-miss same-family check
- `00204`: gap5 budget same-family extension
- `00205`: same-family side calibration diagnostics
- `00206`: early-2024 chronological risk OOF
- `00207`: full-2024 chronological protocol
- `00208`: entry EV calibration admission
- `00209`: entry EV NoTrade selector fresh fold
- `00210`: entry EV rank gate support audit
- `00211`: entry EV rank refit 2025 fold
- `00212`: entry EV multi-window admission selector
- `00213`: entry EV gate sensitivity
- `00214`: entry EV sparse rank diagnostics
- `00215`: entry EV validation inventory
- `00216`: entry EV cal2024 rank window
- `00217`: entry EV admission input diagnostics
- `00218`: entry EV scale quantile diagnostics
- `00219`: entry EV quantile policy backtest
- `00220`: entry EV quantile role selector
- `00221`: entry EV quantile positive floor
- `00222`: entry EV quantile trade context diagnostics
- `00223`: entry EV quantile exit capture diagnostics
- `00224`: entry EV quantile hold-cap sensitivity
- `00225`: entry EV quantile prior inversion guard
- `00226`: entry EV prior context risk score
