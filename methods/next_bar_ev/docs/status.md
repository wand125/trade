# Next-bar EV status

更新日時: 2026-08-16 JST

## 現在の判断

- 標準評価は通常損益とコスト控除後損益。`loss_multiplier` の既定値は1.0で、1.2倍は任意stress testだけに残す。
- M15 confidence 0.54以上は17,354件、accuracy 54.30%、gross mean `+0.09781/oz`、6/6 OOS fold positive。
- round-trip cost 0.05後はnet mean `+0.04781`、6/6 fold positive。ただしall-fold cost ceilingは `0.05415`、headroomは `0.00415`しかない。
- cost 0.10後はnet mean `-0.00219`、positive fold 4/6。実コストなしではライブ採用できない。
- mean EV after costによる選別はaggregate positiveだがcost 0.05後4/6 foldで、direction-onlyより期間再現性が低い。
- `m15_paper_policy_v1.json` を固定1 ozのpaper candidateとして保存した。`live_action=no_trade`。
- Entry EV 607 tradeへの単純overlayは不採用。M1/M5 entry delayも4固定policyすべてadmission fail。
- M5 high-confidence opposed timeoutはdevelopment `+2.12`、confirmation `+1.79`だがdelayed 22件、worst month悪化でsupport/robustness不足。

- **TitanFXの実spreadを実測した結果、`m15_paper_policy_v1` はXAUUSD-mでは成立しない(2026-08-16、[[00005]])**。`runtime/events.jsonl` のbid/ask 9,458件(8/11〜8/15)で、XAUUSD-mのスプレッドは**中央値 0.260/oz、最小 0.210、p90 0.310**。**all-fold cost ceiling 0.05415/ozの約4.8倍**で、gross mean `+0.09781/oz` はスプレッド中央値の38%しかない。commission/slippageを加えれば差はさらに開く。`live_action=no_trade` を維持する。
- **否定されたのは回収経路であって方向edgeではない**。accuracy 54.30%・6/6 fold positiveは残っている。「M15の次足1本で回収する」形が成立しないという判定。
- 参考: USDJPY-mのスプレッドは中央値 0.013(1.3 pips)、p90 0.014。**価格比ではXAUUSD-m 0.0059% / USDJPY-m 0.0082% で金の方が薄い**ため、単純な銘柄変更では解けない。

## 次の検証

1. **保有期間の延長**(本命)。次足1本ではなくN本先まで持ち、コスト一定のままgrossが伸びるかを測る。00003のentry delay検証と接続する。
2. **commissionとslippageの実測**。`runtime/latest_deal_history.json` の約定履歴から1 oz往復価格差へ換算する。スプレッドだけで判定は覆らないが、コストモデルの完成に要る。
3. **方向モデルのgross edgeを価格比で表現し直す**。銘柄横断でcost headroomを比較できる形にする。
4. `m15_paper_policy_v1` を新規期間へ固定forward適用する(判定は変わらないが、モデルの劣化監視として継続)。
5. entry delayは追加supportを得るまで現4policyを変更せず監視する。
