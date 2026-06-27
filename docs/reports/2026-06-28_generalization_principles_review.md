# Generalization Principles Review

日付: 2026-06-28 JST

## 目的

トレードMLで守るべき汎化原則を、現在の研究実装がどこまで満たしているかレビューする。恒久的な原則は `docs/trading_ml_generalization_principles.md` に分離した。

## 結論

方向性は大きく外れていない。特に、ランダム分割を主評価にしていないこと、NoTradeを比較対象にしていること、月別validation/testを分けていること、失敗trade analyzerを作ったことは正しい。

一方で、現状はまだ「未来の未知regimeでも壊れにくい」とは言えない。主な弱点は以下。

- purging / embargo が未実装。
- validation月を何度も見ており、validation selectionへの過適合が進みやすい。
- 2024-12 / 2025-02を繰り返し診断しているため、最終holdoutとして弱くなっている。
- regime別の標準評価がまだ手作業に近い。
- spread / slippage / execution delay感度が未実装。
- predicted EVがtestで大きく過大評価される。
- exit timing targetが実行可能close判断へ十分つながっていない。

## 原則別レビュー

| 原則 | 現状 | 判定 | 次の対応 |
|---|---|---|---|
| 汎化対象の定義 | down月、short側、複数月は見始めた | 部分的 | trend/vol/session/eventのregime taxonomyを定義する |
| 未来のミニ本番validation | 月別walk-forward風に評価している | 部分的 | purged/embargo split generatorを実装する |
| 特徴量の時点管理 | M1はdecision bar後、次足open約定でリークを抑えている | 概ね良い | 外部データ導入前にavailable_time列を標準化する |
| 売買込みbacktest | executable model-policyで評価している | 良いが不十分 | spread/slippage/delay sensitivityを追加する |
| NoTrade判断 | NoTrade比較は常に実施している | 良い | NoTradeに寄りすぎる圧力と、過剰entryの両方を監視する |
| regime別エラー分析 | long/short、bucket分析はある | 部分的 | analyzer出力へregime列を追加する |
| 過剰最適化対策 | multi-fold summaryと最低trade数条件がある | 部分的 | plateau/sensitivity reportとnested selectionを追加する |
| 投資可能universe | 単一XAUUSDのため限定的 | 現状は許容 | 流動性薄い時間、spread異常をexecution制約として扱う |
| ラベル設計 | dense entry targetを導入済み | 良いが未完成 | barrier/rank/waitを確率・calibration targetとして扱う |
| LLM look-ahead | モデル入力には未使用 | 良い | LLMは仮説整理と文書化に限定する |

## 現状の実験から見える問題

低LR1280モデルはvalidationで強い候補を作ったが、fixed testでは以下のように崩れた。

| month | adjusted pnl | trades | win rate | profit factor | max DD |
|---|---:|---:|---:|---:|---:|
| 2024-12 | -134.5306 | 55 | 0.4000 | 0.3220 | 143.4870 |
| 2025-02 | -110.0922 | 72 | 0.5278 | 0.5827 | 130.8148 |

失敗trade analyzerでは、両月とも予測EVが実現PnLに対して平均約22ドル過大だった。これは「方向を少し当てる」だけでは足りず、EV calibrationとexit判断が壊れると損益が負けることを示している。

主な失敗要因:

- 2024-12: long/short両方で損失。direction error rate `0.5273`。
- 2025-02: short側だけで `-111.2848` と損失が集中。
- actual profit barrier missが損失の中心。
- `require_profit_barrier=true` は全tradeを通しており、現状のbarrier予測はfilterとして弱い。
- actual entry rankは強い説明力を持つが、predicted rankだけではまだ安定しない。
- exit regretが非常に大きく、entry後に理論上取れた利益を実行policyが逃している。

この結果は、今回の原則でいう「偽のedgeを殺す力」がまだ不足していることを示す。

## 守れていること

- 主評価をランダム分割にしていない。
- decision bar後に判断し、次足openで約定する仕様にしている。
- NoTrade、random、rule-based baselineを比較対象にしている。
- oracle exit metricとexecutable backtestを区別している。
- dense entry targetにより、3クラス分類だけに圧縮しない方針を採っている。
- 複数validation foldのsummaryで、単月最高スコアを避けようとしている。
- 失敗tradeをdirection、barrier、rank、wait、EV overestimateへ分解できるようになった。

## 守れていないこと

- purged / embargo validationがまだない。
- validation fold自体を繰り返し見ており、研究者側の過適合が起きやすい。
- 2024-12 / 2025-02は多く見たため、今後の最終判定には使いにくい。
- regime別レポートが標準成果物になっていない。
- spread、slippage、delayを悪化させるstress testがない。
- parameter plateauの確認が弱い。
- 現在のHGBは独立targetで、dense targetがshared representationとしてEV予測へ返っていない。
- profit barrier予測が0/1出力中心で、確率としてcalibrationできていない。

## 次の実装優先順位

1. `trade-backtest analyze-trades` を今後の候補診断に必須化する。
2. regime feature / regime label をdatasetとbacktest reportへ追加する。
3. spread / slippage / execution delay sensitivityをbacktestへ追加する。
4. purged / embargo walk-forward split generatorを作る。
5. train期間OOF predictionsを標準化し、meta calibrationのfit月とpolicy選択月を分ける。
6. barrier hit、entry rank、wait regretを確率出力・calibration対象として扱う。
7. 2024-12 / 2025-02以外の追加holdout月を用意する。
8. sweep summaryに周辺パラメータ安定性のreportを追加する。

## 判断

当面はモデル容量を増やすより、検証設計と偽edge排除を強める。深層学習へ進む前に、少なくとも次を揃える。

- OOF predictions。
- side/regime別EV calibration。
- exit timing target強化。
- regime別backtest summary。
- cost/slippage sensitivity。
- test未使用の新しいholdout pool。
