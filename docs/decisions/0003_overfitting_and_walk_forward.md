# 0003: データ増加は期間依存の測定を目的にする

日付: 2026-06-28 JST
状態: accepted

## 背景

初回 HGB multi-task model は train では高い予測指標を出したが、valid/test では大きく劣化した。さらに oracle exit を使う selection metric は良く見えた一方、実行可能 backtest policy では no_trade を超えられなかった。

これは、単にモデルが弱いというより、以下が混在している可能性が高い。

- train 月への過学習
- 市場局面の変化
- predicted EV の過大評価
- exit timing の未学習
- oracle best exit と実行可能な決済判断の差

## 決定

データを増やす。ただし、目的はモデルを大きくすることではなく、期間依存を測ることに置く。

今後の評価では、単月の最高損益ではなく、walk-forward split ごとの以下を重視する。

- no_trade に勝つ月数
- 月次 adjusted pnl の平均と最悪月
- max drawdown
- trade count
- forced exit count
- validation と test の乖離

## 実験方針

- validation 月で entry/exit threshold と calibration を決める。
- test 月では閾値を選ばず、一度だけ評価する。
- expected pnl は validation で calibration してから policy に入力する。
- exit timing target を学習し、best holding minutes を決済判断に使う。
- モデル容量を大きくする前に、正則化を強めた軽量モデルで安定性を測る。

## 影響

深層学習へ進む前に、以下を実装・記録する。

- 追加月 dataset
- calibrated EV prediction
- holding-time-aware executable policy
- walk-forward 実験ログ

## 代替案

少ないデータだけで強い正則化をかける案は、検証が速く、理想には近い。しかし市場局面の違いを測れないため、今の段階では過学習と局面変化を切り分けにくい。
