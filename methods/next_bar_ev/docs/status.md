# Next-bar EV status

更新日時: 2026-08-16 03:04 JST

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

## 次の検証

1. spreadの薄い別銘柄、またはより長い固定保有期間で、gross edgeと実測all-in costの間に余力があるか事前にscreenする。
2. commission/slippageのdeal履歴を取得できた場合は、別銘柄・長期保有候補の1 oz往復all-in costへ換算する。XAUUSD-m M15の不採用判断を覆す用途には使わない。
3. `m15_paper_policy_v1` は研究再現用に固定したまま、追加期間の予測品質だけを監視する。TitanFX XAUUSD-mでの売買forward適用は行わない。
4. entry delayは追加supportを得るまで現4policyを変更せず監視する。
