# Current Assessment

最終更新: 2026-06-30 09:05 JST

## 結論

現時点では、標準採用できる利益最大化トレードpolicyはない。

ただし、研究は停滞していない。データ生成、backtest、OOF、walk-forward、candidate selection、trade delta、context guard、entry budget までの検証基盤は整っている。現在の主課題は「モデルが未知期間で short side に過剰に寄ること」と「guardで悪いtradeを消しても、空いた時間のreplacement tradeが別の損失を作ること」。

採用判断は、全期間を見たbestではなく、prior-only / chronological / fresh apply で壊れないかを優先する。

## 現在の主要評価

| 系列 | 現状 | 代表結果 | 判断 |
|---|---|---|---|
| Holding max cap | `250..260m` はholding安定化候補 | 2025-01..08 coststress `260m` は total `+458.9738`。fresh 2025-09..12 は `260m` でも `-839.2544` | 標準採用しない。fresh失敗はholdingではなくside drift |
| Side drift guard | prior-onlyで悪いshort contextを検出できる | strict short p10 + admission margin10 は 2025-01..12 total `-90.1378`。no guard `-419.0574` からは改善 | 診断baseline。まだNoTrade未満 |
| Residual short failure | 残存損失はほぼshort | p10 + margin10 の負け月で short `-716.6702`、long `-8.4414` | 次はshort側のreplacement riskと初回損失制御 |
| Online context drawdown | realized lossだけで発火できる | prior-only `worst` + margin-aware は min4 total `+69.9374`、min8 total `-199.4438` | risk mandate候補。利益最大化policyではない |
| Short raw gap guard | 介入対象の発見には有効 | all-window bestは total `+18.5106` だが prior-only min4 `-274.9360` | 単独採用しない |
| Short entry budget / budget0 | active short contextを完全stay-flat化でき、prior triggerで発火条件も説明可能 | all-window `gap5/budget0` total `+508.9838`、防御寄り `gap0/budget0` total `+418.2596`, worst `-45.4774`。trigger min4 `+232.2466`、min8 `-15.0104` | 現在最有望な防御軸。min8がまだNoTrade未満なので標準採用は保留 |
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

## 中心的な失敗構造

2025-09..12 の fresh failure では、dense label distribution は long 寄りなのに、raw EV prediction と実行tradeが short 寄りになる。

代表的な症状:

- fresh 2025-09..12 の mean short overprediction は `+0.4143`
- selected short PnL は `-704.9300`、long PnL は `-134.3244`
- worst contextは `short/range_low_vol` 周辺、特に `ny_overlap`, `rollover`, `asia`
- confidenceやside gapだけでは除外できない
- guard後も replacement short が残り、損失の尾部を作る

したがって、次の改善は「holding capの再探索」ではなく、short side admission / first-loss control / replacement-risk control を優先する。

## 次に検証すべきこと

1. `gap0/budget0` と `gap0/budget1` を、追加未使用月または追加データへ再探索なしで適用する。
2. realized PnL triggerに prediction-share / label-share side drift featuresを加え、PnL悪化前にbudget `0` を発火できるか確認する。
3. side drift guard後の replacement trade を、削除tradeと追加tradeに分けて評価する。
4. short/range_low_vol の context drawdownを、現在月のrealized PnLだけで発火させる低容量hookとして評価する。
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
