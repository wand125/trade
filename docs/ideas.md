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
- 00203でtriggered profit-missを `2024-11,2024-12,2025-01..04` same-family smokeへ固定適用したところ、`gap5/budget0 +445.8266` に対して `+367.8768` へ悪化した。発火した2025-03/04で勝ちshortを削ったため、profit-miss hookは診断候補へ降格。次は `gap5/budget0` 単体を追加same-family windowへ固定適用する。純2024検証には2024前半の同一risk列生成が必要。

## 外部データ候補

- 経済指標カレンダー。
- 米国金利。
- DXY。
- Gold futures。
- VIX。
- 実運用ブローカーの XAUUSD spread。

外部データを採用する場合は、取得元、時刻粒度、公開遅延、ライセンス、将来リークの有無を必ず記録する。
