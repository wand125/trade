# Trading ML Generalization Principles

日付: 2026-06-28 JST

## 中心原則

この研究で作るべきものは、「過去に勝つモデル」ではなく、未来の未知の相場 regime でも壊れにくい意思決定システムである。

したがって、評価の中心は予測精度だけではなく、以下に置く。

- 偽のedgeを殺せているか。
- 未来情報の混入を防げているか。
- NoTradeを含む意思決定として成立しているか。
- コスト、スプレッド、スリッページ、約定遅延に耐えるか。
- regimeが変わっても壊れ方が許容範囲に収まるか。
- 壊れたときに、どの条件で壊れたかを診断できるか。

## 1. 何に汎化したいかを先に定義する

XAUUSD短期取引では、「未来データに当たる」だけでは不十分。少なくとも次の軸に対して汎化を評価する。

- 上昇、下落、レンジ。
- 高ボラ、低ボラ、急変動後。
- London/New York/NY close前後などの時間帯。
- 指標発表、FOMC、金利環境変化などの外部イベント。
- スプレッド拡大、約定遅延、データgap。
- profit/loss倍率、手数料、スリッページの変化。

研究上の問いは「全体平均で勝つか」ではなく、「どの環境で勝ち、どの環境で死ぬか」にする。

## 2. Validationは未来のミニ本番にする

主評価でランダム分割を使わない。基本形は walk-forward validation とする。

```text
過去で学習
gap / embargo
直後の未来でvalidation
さらに進める
```

ラベルが未来24時間を使うため、train末尾とvalidation先頭、validation末尾とtest先頭にはラベル期間の重なりが起きうる。今後は purging と embargo を標準分割に入れる。

必須ルール:

- policy選択はvalidationだけで行う。
- test月を見て閾値や特徴量を調整しない。
- testで何度も診断した月は、最終holdoutから格下げする。
- 追加holdout月を定期的に用意する。

## 3. 特徴量はその時点で見えていた情報だけにする

各データには次の時刻概念を持つ。

```text
event_time       事象が起きた時刻
release_time     市場参加者が知れた時刻
available_time   自分のシステムが使えた時刻
decision_time    売買判断時刻
execution_time   約定想定時刻
```

モデル入力にできるのは `available_time <= decision_time` の情報だけ。

現在のM1特徴量では、decision bar確定後に判断し、次足openで約定する方針を採っている。外部ニュース、経済指標、LLM由来情報を追加する場合は、この時刻管理を必ず実装してから使う。

## 4. Backtestは売買シミュレーションとして扱う

予測精度と損益は一致しない。評価は必ず取引ルールへ接続して行う。

必須評価:

- adjusted pnl
- raw pnl
- NoTradeとの差
- random / rule-basedとの差
- trade count
- win rate
- profit factor
- max drawdown
- forced exit count
- exposure
- long/short別成績
- regime別成績
- コスト、スリッページ、約定遅延への感度

現状は profit/loss倍率でコストを粗く表現している。次段階では明示的なspread/slippage sensitivityを入れる。

## 5. NoTradeは重要な行動である

短期売買では、すべてのbarでlong/shortを出すモデルは壊れやすい。取引しない判断を明示的に扱う。

基本形:

```text
predicted EV > cost + safety margin       -> long
predicted EV < -cost - safety margin      -> short
それ以外                                  -> stay flat
```

ただしNoTradeへ寄りすぎると評価が停滞する。研究中は、月10 trades条件などの緩和条件も許容するが、少数tradeの単月プラスをedgeとはみなさない。

## 6. エラー分析はregime別に分ける

全体スコアだけで採用しない。最低限、以下で分解する。

- long / short
- 上昇 / 下落 / レンジ
- high vol / low vol
- 時間帯
- gap直後
- holding time bucket
- predicted EV bucket
- entry rank bucket
- wait regret bucket
- profit barrier hit / miss
- forced exit

候補モデルは、勝った理由よりも負けた理由を先に見る。

## 7. 過剰最適化を疑う

最高スコアの1点を信用しない。採用に近い候補は、周辺パラメータでも成績が残る必要がある。

良い兆候:

- 複数foldで最低P/Lが崩れない。
- 取引回数が薄すぎない。
- 周辺thresholdでも大きく死なない。
- コストを少し悪化させても即死しない。
- long/shortの片側だけに依存しすぎない。

悪い兆候:

- 特定月、特定thresholdだけが異常に良い。
- 1から2回の大勝ちで成績が決まる。
- validationを何度も見たあとにだけ成立する。
- testで後付け選択した候補だけが良い。

## 8. 投資可能 universe を意識する

現状はXAUUSD単一なのでsurvivorship biasは株式ほど問題にならない。ただし、将来ほかの銘柄や市場へ拡張する場合は、各時点で本当に取引可能だった銘柄集合、上場廃止、流動性制約、取引停止を管理する。

XAUUSDでも、取引不可時間、流動性が薄い時間、異常spreadは universe / execution 制約として扱う。

## 9. ラベル設計で差がつく

「次足が上がるか」だけではノイズが強すぎる。ラベルは取引可能な値幅とexit条件に近づける。

現在の方針:

- `long_best_adjusted_pnl`
- `short_best_adjusted_pnl`
- `profit_barrier_hit`
- `wait_regret`
- `entry_local_rank`
- `entry_urgency`
- `best_holding_minutes`

今後追加する候補:

- fixed horizon return
- barrier hit time
- stop/profitどちらが先か
- holding中のclose probability
- hazard-like exit target
- side/regime別calibrated EV

量子化は情報を捨てるためではなく、ノイズの強い連続targetを安定させる補助タスクとして使う。

## 10. LLMを使う場合はparametric look-aheadに注意する

LLMは歴史的事実を事前学習で知っている可能性がある。ニュース、マクロ、銘柄名、過去イベントの解釈を売買判断へ直接入れる場合は危険。

本研究でLLMを使う場合の制限:

- 直接の売買判断には使わない。
- 仮説生成、特徴量候補、レポート整理、エラー分析補助に限定する。
- 過去時点の判断を再現する場合は、その時点で公開済みの文書だけをRAGで渡す。
- 未来情報を含む要約を使わない。

## 実験前チェックリスト

各実験は、最低限これを記録してから実行する。

- train / validation / test の期間。
- gap / embargo の有無。
- target生成倍率とvalidation/test評価倍率。
- 特徴量が `available_time <= decision_time` を満たす根拠。
- backtestの約定価格、profit/loss倍率、明示コストの有無。
- NoTrade、random、previous bestとの比較。
- policy選択に使うfoldと、最終testに使うfoldの分離。
- 最低trade数、max drawdown、forced exit条件。
- regime別に見る切り口。
- 失敗trade分析を実行するか。

## 実験後チェックリスト

候補を採用に近づける前に、以下を確認する。

- NoTradeを複数月で上回るか。
- validationで選んだpolicyを固定したtestで崩れないか。
- test結果を見て選び直していないか。
- 予測EVが実現PnLに対して過大評価されていないか。
- direction error、exit regret、barrier miss、entry rankがどこで悪いか。
- long/short、regime、時間帯別の損失集中がないか。
- 周辺パラメータでも成績が台地状に残るか。
- コストやスリッページを悪化させても即死しないか。

## 参考

- SEC Investor.gov, Investor Bulletin: Performance Claims: https://www.investor.gov/introduction-investing/general-resources/news-alerts/alerts-bulletins/investor-bulletins-47
- GMO, 金融時系列予測におけるクロスバリデーション手法: https://recruit.group.gmo/engineer/jisedai/blog/cv-in-financial-time-series/
- Purged cross-validation: https://en.wikipedia.org/wiki/Purged_cross-validation
- Portfolio Optimization Book, Seven Sins of Quantitative Investing: https://portfoliooptimizationbook.com/book/8.2-seven-sins.html
- Portfolio Optimization Book, The Dangers of Backtesting: https://portfoliooptimizationbook.com/book/8.3-dangers-backtesting.html
- Machine Learning-Based Bitcoin Trading Under Transaction Costs: https://arxiv.org/abs/2606.00060
- Summoning the Oracle to Slay It: Mitigating Look-Ahead Bias in Financial Backtesting with Large Language Models: https://arxiv.org/abs/2605.24564
