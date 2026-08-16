# Next-bar EV status

更新日時: 2026-08-16 09:41 JST

## 現在の判断

- 標準評価は通常損益とコスト控除後損益。`loss_multiplier` の既定値は1.0で、1.2倍は任意stress testだけに残す。
- M15 confidence 0.54以上は17,354件、accuracy 54.30%、gross mean `+0.09781/oz`、6/6 OOS fold positive。
- round-trip cost 0.05後はnet mean `+0.04781`、6/6 fold positive。ただしall-fold cost ceilingは `0.05415`、headroomは `0.00415`しかない。
- cost 0.10後はnet mean `-0.00219`、positive fold 4/6。実コストなしではライブ採用できない。
- mean EV after costによる選別はaggregate positiveだがcost 0.05後4/6 foldで、direction-onlyより期間再現性が低い。
- `m15_paper_policy_v1.json` は固定1 ozのhistorical research candidateとして保存する。実spreadでadmission failしたため現在のpaper/live資格はなく、`live_action=no_trade`。
- Entry EV 607 tradeへの単純overlayは不採用。M1/M5 entry delayも4固定policyすべてadmission fail。
- M5 high-confidence opposed timeoutはdevelopment `+2.12`、confirmation `+1.79`だがdelayed 22件、worst month悪化でsupport/robustness不足。
- TitanFX XAUUSD-mのEA snapshot 9,458件（2026-08-11〜08-15）では実spreadが最小 `0.210/oz`、中央値 `0.260/oz`、p90 `0.310/oz`。中央値はcost ceiling `0.05415/oz` の約4.80倍で、gross mean `+0.09781/oz` はspreadの約37.6%に留まる。commission/slippageを含める前にadmission failとなるため、この銘柄のM15次足単独policyはreject / NoTrade。
- commission、slippage、元集計の `runtime/events.jsonl` は現在の `/srv/trade` から取得できず、推測で補完しない。spread数値の出典は `AGENTS.md`、判断の記録はreport 00005。
- 同じM15 OOS予測・confidence 0.54を固定した2本/4本保有は、17,134/16,663件、gross mean `+0.12298/+0.16761/oz`でも実spread中央値後 `-0.13702/-0.09239/oz`。各5/6 foldだけgross positiveで、all-fold cost ceilingは `-0.06681/-0.12203`へ悪化した。長期化によるXAUUSD-m M15 policy救済もreject / NoTrade（report 00006）。
- 固定precision championのIntrabar Structure 0.55も、評価6 fold 9,523件・accuracy 55.0982%・gross `+0.15625/oz`に対しspread中央値後 `-0.10375/oz`、net positive 3/6 fold。test2023はcost前 `-0.02731/oz`でall-fold cost ceilingが負のため、XAUUSD-m売買laneとしてreject / NoTrade。precision候補としての研究監視だけ維持する（report 00007）。
- Titan FX公式Micro平均spreadからEURUSD-m 1.40、USDJPY-m 1.53、AUDUSD-m 1.72、EURGBP-m 1.73、GBPUSD-m 1.77 pipsをmarket-data測定shortlistへ固定した。利益率順位ではなく測定順だけで、account type、実測p90、commission、slippage、bar値幅、fresh edgeが揃うまで学習・paper/live採用を認可しない（report 00008）。
- 銘柄別event JSONLからask-bidを集計するspread auditを追加。最低5,000件・5 UTC日、無条件policyはp90 <= historical all-fold cost ceilingをspread-only gateとし、commission/slippage/fresh edge不足時は常にall-in非認可とする。
- M30固有予測も実spreadで監査した。baseline 0.55は4,253件・gross `+0.28154/oz`・spread後`+0.02154/oz`、Pressure × AR 0.55は4,088件・`+0.28441/+0.02441/oz`だが、いずれもnet positive 3/6 foldで2024〜2026へ集中しall-fold cost ceilingは`-0.06162/-0.20876`。Pressure 0.52は22,556件・spread後`-0.21514/oz`・0/6 fold。3 laneともXAUUSD-m売買用途はreject / NoTrade、予測研究上のcandidate/shadowだけ維持する（report 00009）。
- M30 baseline 0.55方向の固定60/120分延長もscreenした。60分はgross/spread後`+0.19974/-0.06026/oz`・net 3/6 foldへ悪化。120分は`+0.36225/+0.10225/oz`・gross 6/6でもnet 4/6、all-fold cost ceiling `0.036996/oz`は実spreadの約14.2%だけだった。両保有をrejectし、独立M60/M120新規学習もcost余力不足で見送る（report 00010）。

## 次の検証

1. shortlist順に銘柄別bid/askを最低5 UTC日・5,000件取得し、`spread_audit.py` でminimum/median/p90、時間coverage、invalid件数を固定集計する。売買・EA設定変更は行わない。
2. commission/slippageのdeal履歴を取得できた場合は、別銘柄候補の1 oz往復all-in costへ換算する。XAUUSD-m M15の不採用判断を覆す用途には使わない。
3. `m15_paper_policy_v1` は研究再現用に固定したまま、追加期間の予測品質だけを監視する。TitanFX XAUUSD-mでの売買forward適用は行わない。
4. entry delayは追加supportを得るまで現4policyを変更せず監視する。
5. registryのbroad/balanced/selective laneはprediction artifactを取得できた場合だけ同じcost診断へ通す。再学習して過去期間を再選択せず、precision 0.55の不採用を別閾値探索で救済しない。
6. spread p90とcommission/slippageを含むall-in costに十分な余力がある銘柄だけ、履歴OHLC取得とbaseline予測研究へ進める。公式平均spreadだけでモデル学習やpolicy採用を始めない。
7. M30 baseline/Pressure/Pressure × ARはfresh予測品質だけを固定監視し、XAUUSD-m売買candidateとして閾値・filter・weightを追加探索しない。
8. XAUUSD-mではM30の追加holdingと独立M60/M120研究を停止する。別銘柄の実測cost gateを通るまで高時間足モデルを増やさない。
