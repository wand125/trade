# Current Assessment

最終更新: 2026-06-30 13:08 JST

## 結論

現時点では、標準採用できる利益最大化トレードpolicyはない。

ただし、研究は停滞していない。データ生成、backtest、OOF、walk-forward、candidate selection、trade delta、context guard、entry budget までの検証基盤は整っている。00207で全2024を同一chronological protocolへ揃え、混合family問題は解消した。00208では calibrated entry EV + 高いshort threshold が full 2024 testでNoTradeを超えたが、validationではNoTrade tieとしてしか選べていない。現在の主課題は「entry EVの絶対値を信用せず、fresh foldで壊れないadmission selectorを作ること」と「guardで悪いtradeを消しても、空いた時間のreplacement tradeが別の損失を作ること」。

採用判断は、全期間を見たbestではなく、prior-only / chronological / fresh apply で壊れないかを優先する。

## 現在の主要評価

| 系列 | 現状 | 代表結果 | 判断 |
|---|---|---|---|
| Holding max cap | `250..260m` はholding安定化候補 | 2025-01..08 coststress `260m` は total `+458.9738`。fresh 2025-09..12 は `260m` でも `-839.2544` | 標準採用しない。fresh失敗はholdingではなくside drift |
| Full-2024 chronological protocol | 00206の混合familyを解消したcanonical 2024 artifact | 2024-05..12 OOF比較で source p10/replm10 が最良だが total `-3.1736`。risk5 side `-10.4618`、risk0 side `-32.7828`、risk0 no-side `-141.8816` | 標準採用なし。NoTrade超えまでdiagnostic |
| Entry EV calibrated admission | raw EV thresholdの過適合を診断し、calibrated EVの高threshold候補を固定testした | raw validation `entry12/short3` は `+22.7292` だが full 2024 test `-442.4662`。calibrated `entry10/short6` は test `+100.3612`, worst `-43.2296`, trades `60`; `entry12/short6` は `+74.0644`, worst `-37.8326`, trades `26` | 診断候補。validationではNoTrade tieなので標準採用しない |
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

したがって、次の改善は「holding capの再探索」でも「2025系列へのshort hook追加」でもなく、entry EV calibration、admission control、NoTrade firstの比較、そしてより広いtrain history / purged walk-forwardでのentry品質改善を優先する。

## 次に検証すべきこと

1. Entry EV calibration / admission layerをfresh chronological foldsで再評価する。`cal10/6` と `cal12/6` は診断候補だが、validationでpositive edgeを示していないため、NoTrade tieの選択ルールを事前固定する。
2. 2025系列でshort hookをさらに積む前に、source policy自体のside prediction calibrationとregime別崩れを再評価する。
3. `pred_short_profit_barrier_hit` を0/1ではなく確率または校正済み確率に差し替えてから、profit-miss系hookを再評価する。
4. raw EV絶対値ではなく、side/regime別のrank、calibrated EV quantile、support-aware thresholdをadmission特徴として評価する。
5. side prior driftを、predicted side share vs dense label side share の prior window差分で補正する。
6. 新しいcandidateは必ず NoTrade、previous diagnostic baseline、cost stress、worst month、max DD、short PnLで比較する。

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
