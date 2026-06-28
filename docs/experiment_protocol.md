# Experiment Protocol

## 目的

実験結果を後から比較・再現できるようにする。

## 実験単位

1 回の実験は、以下を固定したものとする。

- data version
- train/valid/test split
- feature set
- label definition
- model architecture
- hyperparameters
- backtest specification
- random seed

実験開始前に `docs/trading_ml_generalization_principles.md` のチェックリストを確認する。特に、時系列分割、未来情報の混入、NoTrade比較、コスト感度、regime別評価の有無を明示する。

## ディレクトリ案

将来の実装では、実験成果物を以下に保存する。

```text
experiments/
  20260628_120000_baseline_ma_cross/
    config.yaml
    metrics.json
    monthly_scores.csv
    trades.parquet
    equity_curve.parquet
    predictions.parquet
    model.pt
    report.md
```

## 必須ログ

学習中:

- epoch
- train loss
- validation loss
- validation adjusted pnl
- validation max drawdown
- validation trade count
- learning rate
- elapsed time

学習後:

- test monthly score
- trade count
- win rate
- profit factor
- max drawdown
- forced exit count
- average holding time
- best checkpoint
- failure analysis

## ベンチマーク

各モデルは必ず以下と比較する。

- No trade
- Random policy
- Simple rule-based strategy
- Previous best model

比較は同一期間、同一バックテスト仕様、同一データで行う。

## 汎化レビュー

採用候補は、単月の最高スコアではなく、未知regimeへの壊れにくさで判断する。

最低限、以下を確認する。

- train / validation / test が時系列順で分離されている。
- ラベルの未来窓が重なる場合は purging / embargo を適用、または適用しない理由を記録している。
- test結果を見てpolicy thresholdを選び直していない。
- NoTrade、random、previous bestを上回るか確認している。
- long/short、regime、時間帯、volatility、holding bucket別の損益を見ている。
- spread / slippage / execution delayを悪化させたときの感度を確認する予定または結果がある。
- 周辺パラメータでも成績が残るかを確認している。
- 失敗trade分析でdirection error、exit regret、EV overestimateを確認している。

## モデル保存

保存ルール:

- validation adjusted pnl が改善したら checkpoint を保存する。
- validation drawdown が悪化しすぎた checkpoint は別フラグを付ける。
- 最終 checkpoint と best checkpoint を区別する。
- checkpoint だけでなく config と feature definition も保存する。

## レポート

実験ごとに `docs/reports/` または `experiments/.../report.md` にレポートを書く。

`docs/reports/` に置くレポートのファイル名は `00001_YYYY-MM-DD_slug.md` の通し番号形式にする。通し番号はファイルシステムの更新時刻ではなく、レポート本文冒頭の `日時: YYYY-MM-DD HH:MM JST` の昇順で決める。新規レポートは既存レポートの最大番号の次を使う。

各レポートの冒頭には、日付だけでなく時刻まで含めた `日時: YYYY-MM-DD HH:MM JST` と `更新日時: YYYY-MM-DD HH:MM JST` を記録する。`日時` は作成時刻、`更新日時` は最終更新時刻として扱う。

テンプレート:

- `docs/templates/experiment_report.md`

## 失敗の記録

失敗した実験も残す。特に以下は価値がある。

- validation は良いが test が悪い。
- 取引回数が極端に少ない。
- ロング/ショートの片側に偏る。
- 特定月だけ異常に良い。
- gap 周辺で損失が集中する。
- 標準損失補正やコスト変更に弱い。
