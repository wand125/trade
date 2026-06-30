# Ideas Backlog

未検証アイデアを集約する。採用したものは実験レポートか decisions に移す。

## 特徴量

- rolling FFT の低周波/高周波比率。
- price derivative と acceleration。
- denoised close の slope。
- realized volatility regime。
- London/New York overlap flag。
- gap after weekend flag。
- high-low range の急拡大。
- Tick spread の proxy を M1 特徴量に合成。
- 直近 N 回の swing high/low 距離。

## ラベル

- 未来 24 時間内の best exit による long/short/stay label。
- 最大利益だけでなく、最大逆行幅を差し引いた label。
- 期待値が高くても drawdown が大きい entry を除外。
- exit model を survival/hazard として扱う。
- entry と exit を分離して学習する。
- side/context guard発火後の代替tradeを `positive_replacement_regret` で審査し、margin不足ならstay flatにする。

## モデル

- TCN で M1 sequence を処理。
- M1 と M5 の multi-branch network。
- entry classifier + exit hazard model。
- expected value regression + threshold policy。
- imitation learning from oracle policy。
- policy gradient は後半で検討。

## 評価

- 月別 leaderboard。
- volatility regime 別 leaderboard。
- trade count normalized score。
- drawdown penalty score。
- forced exit penalty。
- 取引時間帯別スコア。
- walk-forward split で、どの市場局面で壊れるかを見える化する。
- no_trade を必ず比較対象に残し、取引したくなるバイアスを抑える。

## 過学習対策

- データを増やす目的は、モデルを大きくすることではなく、期間依存を測ること。
- 少ないデータでも過学習しにくいモデルが理想なので、まずは単純で検証しやすいモデルを優先する。
- train と valid/test の乖離を月別に記録し、平均だけでなく最悪月と分散を見る。
- validation 月で entry/exit threshold と calibration を決め、test 月で閾値を選ばない。
- expected pnl の絶対値は過大評価されやすいため、validation で calibration してから policy に入れる。
- exit timing target を追加し、oracle best exit と実行可能な close timing の差を縮める。
- データを増やしても単月最適化を始めると同じ問題が再発するため、walk-forward を必須にする。
- `direction + combined_regime + session_regime` の決済済み実績だけを使う online context drawdown guard。月内またはrolling recent tradesの同一文脈損失が閾値を超えたら、追加admission marginまたはcooldownでstay flatに寄せる。
- online drawdown guardの閾値はvalidation total PnLだけで選ぶと `inf` または低margin relaxationに寄りやすい。prior-only `worst` objective と高い再入場margin (`20/20`) はtail riskを縮める候補だが利益最大化ではないため、未使用月で事前登録mandateとして検証する。
- cooldownだけでbreach後の再入場を許可すると、良い前半月だけでなくside driftが壊れた後半月のshort損失も戻る。cooldownは標準採用せず、breach後の再入場判断は recent side drift / realized context loss / prediction-side bias を特徴量化して審査する。
- `prior_context_pnl`, `prior_context_active_loss_breach`, `prior_context_trade_count`, `minutes_since_context_breach`, `entry_margin` を selected-trade failure / stateful risk / candidate selection の特徴量へ戻す。recovery hard rule単体は prior-only で改善しない。
- raw online context stateをそのままselected-trade classifierへ足すとOOF AUCが悪化したため、次は `side_drift_short_bias`, `prior_context_active_loss`, `entry_margin` の低容量な相互作用だけを候補化し、post-trade filterではなくdynamic backtestで評価する。
- side drift context全体へのonline drawdown guardはtotalだけ少し改善してもshort driftを直せない。次は short限定で、prior side/context lossがactiveかつprediction short biasが高い場合にだけ追加entry marginまたはstay-flatへ寄せる。
- raw short score gapによる `signal_short_raw_gap` はall-windowでtotalを改善できるが、prior-only selectionでは2025-09..12に崩れる。score gap閾値そのものを採用せず、対象月より前だけで見える prior side-drift profile、short active PnL、short exposure budget を組み合わせて評価する。
- `context_entry_budget` はall-windowで強いが、total/worstだけのprior-only selectionではNoTrade超えに届かない。次は prior short active PnL、short losing-month count、late-regime short deteriorationを使って `gap0/budget1`, `gap0/budget2`, `gap5/budget1` のような防御候補を選ぶ。
- short budget selectorではactive/short PnL最大化より `defensive_budget` が有効。次は固定 `gap0/budget1` を追加未使用月で確認し、budget=1でも残る初回short大損を fast stop、per-regime first-loss cap、または prior side-label inversion による budget0 で抑える。
- `context_entry_budget=0` は `gap0/budget0` でlate short regimeのworstを大きく縮める。常時固定ではなく、prior side-drift deterioration、short label/prediction share inversion、recent short losing-month countから budget0 を発火する低容量detectorを作る。
- realized PnLだけのshort budget drift triggerは `gap5/budget0 -> gap0/budget0` を説明できるが、`00190` を上回らない。
- 月次平均の prediction-share / label-share drift trigger は発火が早すぎ、00191のrealized triggerを上回らなかった。次は `dataset_month + combined_regime + session_regime` などのcontext/session単位alert、または `prediction short bias high AND recent short losing month >= 1` のAND条件で、PnL悪化前のbudget0発火を再評価する。
- context/session alertとshort losing monthのANDは00191と同じ成績で、global month-level budget0 triggerの上積みにはならなかった。alert contextだけの `context_entry_budget=0/1` や追加entry marginは00194、context-specific first-loss capは00195で検証済み。
- alert contextだけへの `context_entry_budget=0/1` と追加entry marginはbaselineを改善したがglobal budget0系に届かず、prior-onlyでも崩れた。同じalert context内のfirst-loss / fast-stopも全期間小改善止まりでprior-onlyでは崩れた。00196でlate windowのcommon shortとreplacement shortが残存差分だと確認し、00197で固定 `gap5/budget0 -> gap0/budget0` triggerとcandidate-only late replacement shortを分解した。2024側の同一family固定適用は、coststress 260 + stateful risk5 + replacement margin10の2024 prediction/backtest生成後に行う。
- 00198で、`gap5` replacement shortのprior signal coverageを監査した。prior alert単体は弱く、prior alert OR prediction short biasなら損失上限を大きく削れるが、`range_low_vol/ny_overlap` はprior context signalでほぼ拾えない。次はentry-level EV overestimate、NY-overlap固有のside inversion、またはcurrent-month first-loss controlでこの未検知contextを狙う。
- 00199で、`range_low_vol/ny_overlap` replacement shortはentry時点の `side_gap <= 0` または `candidate_entry_rank >= 0.52` をprior signalに足すと大半を覆えると分かった。first-loss controlは月初の初回損失を拾えないため弱い。次は `gap5` / primary branch限定のdynamic hookに入れ、one-position replacement込みで改善するか確認する。`gap0` へ広げるのは良いreplacementを消す可能性があるため避ける。
- 00200でfocus entry signalをdynamic hook化した。00199のOR条件はreplacement込みで `+508.9838 -> +507.4968` と悪化し、side-gap onlyも悪化。rank-only `0.53` は `+511.5964` と小幅改善するが採用するほどではない。次は `model-trade-delta` の `only_candidate` shortをreplacement risk targetとして学習・診断し、削除後に悪いreplacementが入る局面を事前に避ける。
- 00201で `only_candidate` shortをreplacement risk target化した。`profit_hit_lt0p5` はlate `gap5` replacement損失をほぼ覆うが全期間では良いreplacementを消すためglobal gate不可。`pred_ev_lt15` はsupportが少ないものの全期間/lateとも悪いreplacementに寄る。trigger限定dynamic hookは00202で検証済み。
- 00202でtrigger限定replacement risk hookをdynamic backtestした。`min_prior_months=4` と `recent_short_losing_months>=1` の後だけ `pred_short_profit_barrier_hit=0` を止めると、`gap5/budget0` baseline `+508.9838 / worst -215.1172` から `+790.3634 / worst -46.0150` へ改善。low-EVはworstを止めない。次は同一familyの2024または追加未使用月へ、trigger条件とthresholdを再探索せず固定適用する。
- 00203でtriggered profit-missを `2024-11,2024-12,2025-01..04` same-family smokeへ固定適用したところ、`gap5/budget0 +445.8266` に対して `+367.8768` へ悪化した。発火した2025-03/04で勝ちshortを削ったため、profit-miss hookは診断候補へ降格。
- 00204で `gap5/budget0` 単体を `2024-11..2025-08` same-familyへ拡張した。10ヶ月合計は `+384.6968` でsource `+219.9460` を上回るが、追加apply `2025-05..08` だけでは `+13.9434` でsource `+66.7730` とbaseline `+176.8236` に負けた。`gap5/budget0` も標準採用候補から外し、診断baselineにする。純2024検証には2024前半の同一risk列生成が必要。
- 00205でsame-family side calibrationを診断した。raw EVには `2025-04..06` でshort biasがあるが、gap5は2025-06の良いshortを消して悪化し、残存最大損失はlong側にも移った。これ以上2025系列にshort-only hookを積まず、早期2024のHGB+MLP forced prediction生成、同一risk列拡張、side/EV calibration preflightを優先する。
- 00206で早期2024のchronological HGB+MLP predictionとstateful risk OOFを生成した。risk OOFは `2024-05` から出せたが、2024-03..06は2023-only model、2024-07以降は既存familyなのでbridge artifact。純2024利用可能6ヶ月ではsource p10/replm10が合計 `+21.6688` で最良、no-sideは `+12.0322` だが worst/DD が最良。次は混合familyのままgap0/gap5比較へ進むか、全2024を同一chronological protocolで再生成するかを決める。
- 00207で全2024を同一chronological protocolへ再生成し、混合family問題を解消した。OOF 8ヶ月ではsource p10/replm10が相対最良でも total `-3.1736` でNoTradeを超えない。HGB validationではcalibrated selectionが `0` rowなのにtestでは大量選択されるため、次はside hookではなくentry EV scale drift、validation-time calibration、NoTrade first admission layerを主軸にする。`gap0/gap5/budget0` をこのfamilyで試す場合も、標準採用ではなく診断stress testとして扱う。
- 00208でraw EV thresholdのvalidation過適合を確認した。raw `entry12/short3` はvalidation `+22.7292` からfull 2024 test `-442.4662` へ崩れた。一方、calibrated `entry10/short6` と `entry12/short6` はtestでNoTradeを超えたが、validationでは `0` tradeのNoTrade tieとしてしか選ばれていない。次はNoTrade tie selectorを事前固定し、fresh chronological foldsでcalibrated high-threshold candidateを再評価する。
- 00209でNoTrade-first selectorを実装し、fresh `2024-03..04` validationでは best calibrated `entry12/short6` も `-1.8610` でNoTrade未満だった。diagnostic fixed test `2024-05..12` は `+65.4014` だが、validation-negative候補なので標準採用しない。次は追加chronological model-refit folds、side/regime別calibrated EV quantile/rank、support-aware admission特徴で validation total がNoTradeを超えるかを確認する。
- 00210で00209のfixed testが `min_entry_rank=0.5` 入りだったと訂正し、rank gateを明示grid化した。fresh validation best `entry10/short9/min_rank0.0` は `+17.0910` だが4 tradesしかなく、`min_trades=10`, active2, worst0 gateではNoTrade。rank gateはdiagnostic admission axisとして残し、side/regime別rank・quantile校正・追加chronological model-refit foldsでsupportを増やせるかを検証する。
- 00211で追加2025-refit foldを確認したところ、support gateを十分満たす `entry12/short3/min_rank0.0` が validation `+209.4234`, trades `170` から test `-1002.1534` へ崩れた。これはsupport不足ではなく、2ヶ月validationだけでは未来10ヶ月のregimeを代表できない問題。次は複数validation window、side/regime worst bucket、side balance、trade frequency制約をselectorへ入れる。test hindsight topの `entry14/short9/min_rank0.7` はvalidation 0 tradesなので採用不可だが、高rank short-only sparse entryの診断軸として残す。
- 00212でmulti-window selectorを実装した。fresh2024 + refit2025のstrict gateはNoTrade、relaxed gateは `entry10/short9/min_rank0.0` を選ぶが fixed tests `-943.9322`。`max_side_trade_share<=0.95` ではNoTradeになるため、side-balanceは有効なrejection axis候補。ただし `0.95` を固定閾値にせず、`0.90/0.95/0.98` とregime worst bucket floorを追加validation windowsで評価する。
- 00213で `0.90/0.95/0.98/inf` side share、window support、regime floorを576通り評価した。選ばれた8 gateは全て同じ `entry10/short9/min_rank0.0` でfixed `-943.9322`。したがって閾値チューニングではなく、validation window追加、side/regime別rank・calibrated EV quantile、sparse high-rank rowをtest PnLなしで説明する診断へ進む。
- 00214でsparse high-rank fixed-positive rowをvalidation evidenceだけで診断した。`entry14/short9/min_rank0.6` はfixed `+98.9868` だが、fresh2024は0 trade、refit2025は3 long-only tradesで `-0.3844`。sparse rowを採用するには、固定test PnLではなく追加validation windowsかside/regime-aware rank・calibrated EV quantileで支持される必要がある。
- 00215で既存entry EV/rank artifactを棚卸しした。full-rank validationとして使える既存windowは `2024-03..04` と `2025-01..02` の2本だけ。`2025-03..12` はfull rankでもfixed test、`2024-05..12` はpartial rank fixed test。次にvalidationを増やすなら、`2024-01..02` をfull rank sweepとして再生成するか、新しいchronological foldを作り、別のouter testを明示的に予約する。
- 00216で `2024-01..02` をfull rank sweepとして再生成したが、calibration-validationでありclean holdoutではない。cal2024自体はtrade 8 / total `-70.3272` で、3-window selectorに入れてもstrictはNoTrade、relaxedは既存の `entry10/short9/min_rank0.0` のまま、side095でNoTrade。次はno-trade calibration windowを増やすより、新しいchronological foldと新outer test、またはEV scale/rank distributionの消失理由を診断する。
- 00217でEV scale/rank distributionの入力診断を実施した。cal2024はholding validityではなく `side_gap>=5` が `11 / 56,077` しかないことで高threshold候補が消え、refit2025はlong EV scaleが大きく `entry10/short9/min_rank0.0` で `29,522` long entriesを出す。次は絶対EV thresholdではなく、side/regime-local EV quantile、side-gap quantile、rank quantileをadmission scaleとして比較する。
- 00218でquantile admission診断を追加した。`side_regime_session_month` scopeの `score>=q99`, `side_gap>=q95`, `rank>=q90` は cal2024 `41`, fresh2024 `316`, refit2025 `32` entriesとなり、絶対閾値よりfold間候補数が比較しやすい。次はこのquantile列をprediction/backtest inputに接続し、stateful timed-EV policyとしてNoTradeと比較する。
- 00219でquantile列をstateful timed-EVへ接続した。cal2024のno-entry問題は解消したが、fresh/refit validationのworst monthが負になった。quantile gate単独は標準採用せず、追加chronological validation windows、role-level worst-month gate、side share cap、small positive EV floorを事前登録してから再評価する。
- 00220でrole-level selectorを追加した。strict3/clean2ともNoTradeで、clean2の絶対閾値baselineもrole trades不足とside concentrationで落ちる。今後のquantile候補はこのselectorを通してからfixed diagnostic/cost stressを見る。
- 00221でpositive EV floor候補を追加した。floor `5/10` を入れてもstrict3/clean2はNoTradeで、floor10はfresh validationを少し改善する一方refitの負けを解けない。同じrole上でfloor値を細かく探索せず、次はselected trade contextとEV calibrationをrole別に比較するか、chronological validation windowを増やす。
- 00222でquantile/floor候補の実tradeをrole/context別に診断した。q95/q99系はrefitのdirection error / exit regret、q90系はfreshの悪いshort contextが主因。次はcontext-side inversion preflightとexit capture診断を分け、entry floorだけで救おうとしない。
- 00223でq95/q99のexit captureを診断した。`max_predicted_hold=260m` が強くbindingし、oracle best holdingより早く出ているtradeが多い。ただしrefit側にはdirection/context errorも残るため、blind cap延長は危険。次は `260/480/720/1440` hold-cap sensitivityをvalidation roleだけで事前登録し、context-side inversion guardなし/ありを分けて評価する。
- 00224でhold-cap sensitivityを実施した。`720m` はexit capture改善軸として有望で、same-validation diagnostic inversion guardありならrole totalsは全て正になる。ただし月別tailが残り、全候補が `month_pnl_below_floor` で落ちる。次は同月結果から作ったguardではなく、prior-only selected-trade context direction error / side PnL / prediction side bias で inversion detectorを作る。
- 00225でprior-only inversion guardを試すと、validationは `720m q95_floor5` が min month `-0.4914` まで近づいたが、fresh fixedではguardが良い取引も削った。context-side evidenceは即hard blockにせず、prior direction error、prior side PnL、support、predicted side bias、side share driftをrisk scoreやrank特徴へ変換して、entry admission / exit cap selection / model featureに戻す。
- 00226でprior context risk scoreを実装した。`risk_score>=0.50` は広いhard blockより副作用が小さく、cal+fresh priorならfresh fixed q95_floor5/720mを改善したが、月次floorは通らない。次はprior role protocolを事前固定した複数windowで評価し、hard blockではなくselector feature、candidate rank、exit cap selectionの説明変数へ移す。
- 00227でfresh `2024-03` 残差を分解した。18 tradesすべてにsame-side oracle edgeがあり、`no_edge_entry=0`。lossはdirection-side inversionとexit capture不足が主因なので、次は同方向oracle利益余地をrealizedで逃すtradeをexit timing targetにし、actual best sideが逆側へ大きく寄るtradeをdirection-side inversion targetとして分ける。予測EVはoracle基準ではなく、現exit policyで実現可能なEVへcalibrationする。
- 00228でexit-capture targetを実装した。`exit_capture_failure` は失敗説明として強いが、勝ちroleにも多いためhard blockには使えない。次は `same_side_missed_loss` をrisk target、`low_exit_capture` や `exit_capture_shortfall` をexit timing / capture improvement targetへ分け、predicted oracle EVに expected capture ratio を掛けた executable EV calibration を試す。
- 00229でexecutable EV calibrationを試した。raw EVの過大評価は大きく縮むが、低calibrated EV hard thresholdはwindow間で符号反転する。次は `pred_capture_calibrated_ev`, `executable_capture_factor`, `raw_ev - executable_ev` をselector/ranking featureにし、NoTrade-first monthly gateで評価する。
- 00230でcandidate-level selector featureへ戻してもNoTrade-first gateは超えなかった。次はpost-trade candidate selectorではなく、stateful policy内で competing entry / replacement entry のscoreを `pred_capture_calibrated_ev` に差し替え、同じ一玉制約で実際の経路が変わるかを見る。
- 00231でstateful policyのlong/short scoreをexecutable EVへ差し替えるとrefit2025のlong過剰は大きく改善したが、best near-missの `720m q99 floor5` もvalidation min month `-1.8000` とtrade support不足でNoTrade。floorなしとfloor `2/3/4` はtailを戻すため、floor細密探索は本流にしない。次はexecutable EVを粗いcontext平均factorではなく、dense target / model feature / calibration layerとして学習させ、追加chronological validationでsupportを増やす。

## 外部データ候補

- 経済指標カレンダー。
- 米国金利。
- DXY。
- Gold futures。
- VIX。
- 実運用ブローカーの XAUUSD spread。

外部データを採用する場合は、取得元、時刻粒度、公開遅延、ライセンス、将来リークの有無を必ず記録する。
