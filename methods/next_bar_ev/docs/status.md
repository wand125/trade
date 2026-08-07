# Next-bar EV status

更新日時: 2026-08-07 20:05 JST

## 現在の判断

- 標準評価は通常損益とコスト控除後損益。`loss_multiplier` の既定値は1.0で、1.2倍は任意stress testだけに残す。
- M15 confidence 0.54以上は17,354件、accuracy 54.30%、gross mean `+0.09781/oz`、6/6 OOS fold positive。
- round-trip cost 0.05後はnet mean `+0.04781`、6/6 fold positive。ただしall-fold cost ceilingは `0.05415`、headroomは `0.00415`しかない。
- cost 0.10後はnet mean `-0.00219`、positive fold 4/6。実コストなしではライブ採用できない。
- mean EV after costによる選別はaggregate positiveだがcost 0.05後4/6 foldで、direction-onlyより期間再現性が低い。
- `m15_paper_policy_v1.json` を固定1 ozのpaper candidateとして保存した。`live_action=no_trade`。
- Entry EV 607 tradeへの単純overlayは不採用。M1/M5 entry delayも4固定policyすべてadmission fail。
- M5 high-confidence opposed timeoutはdevelopment `+2.12`、confirmation `+1.79`だがdelayed 22件、worst month悪化でsupport/robustness不足。

## 次の検証

1. TitanFXの実spread、commission、slippageを1 oz往復価格差へ換算し、0.05415以下か測る。
2. `m15_paper_policy_v1` を新規期間へ固定forward適用する。
3. entry delayは追加supportを得るまで現4policyを変更せず監視する。
