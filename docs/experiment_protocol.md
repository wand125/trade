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

## モデル保存

保存ルール:

- validation adjusted pnl が改善したら checkpoint を保存する。
- validation drawdown が悪化しすぎた checkpoint は別フラグを付ける。
- 最終 checkpoint と best checkpoint を区別する。
- checkpoint だけでなく config と feature definition も保存する。

## レポート

実験ごとに `docs/reports/` または `experiments/.../report.md` にレポートを書く。

テンプレート:

- `docs/templates/experiment_report.md`

## 失敗の記録

失敗した実験も残す。特に以下は価値がある。

- validation は良いが test が悪い。
- 取引回数が極端に少ない。
- ロング/ショートの片側に偏る。
- 特定月だけ異常に良い。
- gap 周辺で損失が集中する。
- 損失補正 1.3 倍に弱い。

