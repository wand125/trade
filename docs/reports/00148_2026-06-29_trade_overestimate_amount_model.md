# Trade Overestimate Amount Model

日時: 2026-06-29 15:39 JST
更新日時: 2026-06-29 15:39 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻である `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## 目的

`00147` の反省として、quality scoreをhard filterやside反転に使わず、`pred_taken_ev - adjusted_pnl` の正の部分を連続targetとして学習する。

狙いは「入る方向」を直接変えるのではなく、既存raw EV / stateful risk / MLP holding guardを維持したまま、EV過大評価が大きい候補だけをsoft penaltyで下げること。

## 実装

`oof-trade-overestimate-model` を追加した。

- target: `trade_overestimate_target_amount = max(pred_taken_ev - adjusted_pnl, 0)`
- output: `pred_trade_overestimate_{long,short}_amount`
- risk: `pred_trade_overestimate_{long,short}_risk = -amount`
- OOF: validation monthを1つ抜き、残り月でfitしてholdout monthをscore
- apply: validation全体でfitした最終modelで2025-05をscore

また、`pred_trade_quality_{long,short}_adjusted_pnl` をanalysis/enrichで保持し、optional side featureとして `pred_taken_trade_quality_adjusted_pnl`, `pred_opposite_trade_quality_adjusted_pnl`, `gap` に展開できるようにした。

## OOF Model Metrics

対象は highcost risk5 の2024-11..2025-04 selected trades 502件。

| metric | value |
|---|---:|
| target mean | `18.2772` |
| predicted mean | `17.7814` |
| bias | `-0.4958` |
| MAE | `8.3937` |
| RMSE | `11.6532` |
| R2 | `0.1273` |
| high-overestimate threshold | `24.4142` |
| high-overestimate AUC | `0.6814` |

連続amount targetとしては、これまでのselected-trade quality回帰より明確にrank signalがある。

## Policy Connection

既存の stateful risk5 を置き換えず、combined riskを作った。

```text
combined_risk = stateful_risk + (lambda / 5) * overestimate_risk
```

`model-policy` 側は `risk_penalty=5` のままなので、既存stateful penaltyは維持され、overestimate側だけ `lambda * amount` がEVから引かれる。

まずamount全体を直接penaltyしたが、全候補にほぼ定数penaltyが入り、baselineを下回った。

| lambda | validation PnL | trades | min month | max DD |
|---:|---:|---:|---:|---:|
| baseline | `407.8172` | 502 | `-16.9006` | `224.7524` |
| 0.005 | `385.1526` | 500 | `-29.6668` | `224.7524` |
| 0.010 | `342.3462` | 497 | `-36.2332` | `227.2004` |
| 0.050 | `314.3812` | 466 | `-32.7744` | `225.0164` |
| 0.250 | `-33.1338` | 225 | `-70.4586` | `236.0430` |

この結果から、amountの平均水準をそのまま引くのは不採用。

次に、validation OOF prediction分布の上位だけをpenaltyした。q90 thresholdは long `18.8171`, short `21.1886`。

| run | validation PnL | trades | min month | max DD |
|---|---:|---:|---:|---:|
| baseline | `407.8172` | 502 | `-16.9006` | `224.7524` |
| q90 w0.25 | `412.0320` | 502 | `-16.9006` | `224.7524` |
| q90 w1.0 | `430.6252` | 504 | `-21.0666` | `200.7864` |
| q90 w2.0 | `460.6640` | 529 | `-2.3046` | `204.8324` |
| q75 w0.25 | `407.9682` | 494 | `-11.7306` | `228.2744` |

q90 w2.0 はvalidation合計、最悪月、max DDでbaselineを上回った。

## 2025-05 Fixed Apply

validationで上位だった候補だけを2025-05に適用した。

| run | adjusted PnL | trades | win rate | profit factor | max DD |
|---|---:|---:|---:|---:|---:|
| baseline stateful risk5 | `-52.9764` | 105 | `0.5238` | `0.9016` | `137.4392` |
| q90 w2.0 | `25.5248` | 106 | `0.5660` | `1.0531` | `151.0632` |
| q90 w0.25 | `-11.2524` | 103 | `0.5340` | `0.9773` | `127.9592` |
| q90 w1.0 | `-34.1266` | 102 | `0.5294` | `0.9315` | `129.6962` |
| q75 w0.25 | `-51.1994` | 99 | `0.5253` | `0.8993` | `118.0042` |

q90 w2.0 は2025-05でもNoTradeを上回り、baselineから `+78.5012` 改善した。一方でmax DDはbaselineより悪化しているため、採用候補ではあるが標準policyへ即昇格はしない。

## 判断

1. `ev_overestimate_amount` の連続target実装は採用する。
2. amount全体を直接penaltyする方式は採用しない。平均水準を引いて良いtradeまで落とす。
3. 上位過大評価だけをpenaltyする q90 excess risk は採用候補。validationと2025-05 applyで同方向に改善した。
4. ただし q90 threshold / lambda は今回のvalidation内で選んだため、次の未使用月またはchronological validationで固定確認する。
5. 次は q90 excess riskを、別月・別cost・regime別・trade deltaで確認し、改善が少数tradeや特定月に依存していないかを見る。

## Artifacts

- full validation merge: `data/reports/modeling/20260629_1525_failure_quality_stateful_full_validation/`
- OOF overestimate model: `experiments/20260629_063131_trade_overestimate_amount_with_failure_quality_highcost_risk5/`
- amount combined risk: `data/reports/modeling/20260629_1532_trade_overestimate_combined_risk/`
- excess combined risk: `data/reports/modeling/20260629_1539_trade_overestimate_excess_risk/`
- amount validation backtests: `data/reports/backtests/20260629_trade_overestimate_soft_penalty_validation/`
- excess validation backtests: `data/reports/backtests/20260629_trade_overestimate_excess_soft_penalty_validation/`
- 2025-05 apply backtests: `data/reports/backtests/20260629_trade_overestimate_excess_soft_penalty_apply_2025_05/`

## 検証

- `python3 -m unittest tests.test_meta_model`: OK, 45 tests
- `python3 -m unittest tests.test_backtest tests.test_docs_reports`: OK, 82 tests
- `git diff --check`: OK

## 次の作業

1. q90 w2.0 を固定候補として、未使用月またはより後ろのchronological foldで確認する。
2. `model-trade-delta` で baseline vs q90 w2.0 のonly_candidate / only_base / blockingを診断する。
3. q90 thresholdを固定する方法を明確化する。validation OOF prediction分布由来か、train selected tradeのtarget分位由来かを比較する。
