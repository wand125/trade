# Current Assessment

最終更新: 2026-06-30 11:23 JST

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
| Short entry budget / budget0 | active short contextを完全stay-flat化でき、fixed `gap5 -> gap0` triggerも対象月前だけで説明可能 | all-window `gap5/budget0` total `+508.9838`、防御寄り `gap0/budget0` total `+418.2596`, worst `-45.4774`。focus entry ORはdynamicでは `+507.4968` に悪化。replacement risk targetでは late `gap5` replacement `-286.9878`、`pred_ev_lt15` が全12ヶ月 `-87.9540` / late `-83.8596` | 現在最有望な防御軸。ただしlate-onlyでは利益policyにならない。次はtrigger限定replacement low-EV hook |
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
- replacementは全期間では利益にもなるため、global hard gateは危険。late bad regimeでは `profit_hit_lt0p5` が強いが全期間では良いreplacementを消す。`pred_ev_lt15` は小supportながら全期間/lateとも悪いreplacementに寄る

したがって、次の改善は「holding capの再探索」ではなく、short side admission / first-loss control / replacement-risk control を優先する。

## 次に検証すべきこと

1. prior deterioration trigger後だけに限定した replacement low-EV hookをdynamic backtestする。まず `pred_taken_ev < 15`、次に trigger限定 `profit_hit_lt0p5` を比較する。
2. `gap0/budget0`, `gap5/budget0`, `gap5 -> gap0` deterioration triggerを、追加未使用月または2024側の同一familyへ再探索なしで適用する。2024側はcoststress 260 + stateful risk5 + replacement margin10のprediction/backtest生成が先に必要。
3. side drift guard後の replacement trade を、削除tradeと追加tradeに分けるだけでなく、追加tradeを目的変数化する。
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
