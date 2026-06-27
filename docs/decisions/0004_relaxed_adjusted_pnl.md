# 0004: 評価倍率を 1.0 / 1.25 に緩和する

日付: 2026-06-28 JST
状態: accepted, revised

## 背景

初期ルールでは、利益は 0.9 倍、損失は 1.3 倍として adjusted pnl を計算していた。この条件では no_trade が強く、学習モデルや rule baseline の比較が進めにくい。

特に validation の policy selection を旧倍率で行うと、entry threshold や side margin の探索が no_trade に近い方向、つまり参入回数を過度に下げる方向へ寄りやすい。

## 決定

比較用の緩和ルールとして、以下を採用する。

- profit multiplier: 1.0
- loss multiplier: 1.25

この倍率は validation 以降の backtest evaluation 用に使う。学習 dataset と expected pnl target は旧倍率のまま維持する。

## 実装方針

評価だけを変えると、モデルが学習した expected pnl target と backtest の損益定義がズレる。そのため、以下を分けて扱う。

- 学習: 旧倍率 dataset で予測モデルを学習する。
- validation: 新倍率 backtest で calibration、policy、entry/exit threshold、side margin を選ぶ。
- test: validation で選んだ設定を固定し、新倍率 backtest で一度だけ評価する。

旧倍率 dataset は上書きしない。新倍率 dataset は生成済みだが、主経路の学習には使わない。

## 標準フロー

```text
train target: old multipliers 0.9 / 1.3
validation policy selection: new multipliers 1.0 / 1.25
final test: new multipliers 1.0 / 1.25
```

## 影響

以後のレポートでは、どの倍率を使ったかを必ず明記する。

validation を新倍率にすることで、policy selection の目的を「旧倍率下で no_trade に近づけること」ではなく、「緩和した評価条件で十分な参入を維持しながら損益を改善すること」に寄せる。

旧倍率:

- profit multiplier 0.9
- loss multiplier 1.3

新倍率:

- profit multiplier 1.0
- loss multiplier 1.25

## 修正履歴

当初は新倍率 dataset を作って再学習する案も検討した。しかし、旧倍率へ戻す可能性と、厳しい条件下での学習効率改善を優先するため、学習 target は旧倍率に固定する。
