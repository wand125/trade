# Ideas Backlog

未検証アイデアを集約する。採用したものは実験レポートか decisions に移す。

## 特徴量

- rolling FFT の低周波/高周波比率。
- price derivative と acceleration。
- denoised close の slope。
- realized volatility regime。
- London/New York overlap flag。
- gap after weekend flag。
- high-low range の急拡大。
- Tick spread の proxy を M1 特徴量に合成。
- 直近 N 回の swing high/low 距離。

## ラベル

- 未来 24 時間内の best exit による long/short/stay label。
- 最大利益だけでなく、最大逆行幅を差し引いた label。
- 期待値が高くても drawdown が大きい entry を除外。
- exit model を survival/hazard として扱う。
- entry と exit を分離して学習する。

## モデル

- TCN で M1 sequence を処理。
- M1 と M5 の multi-branch network。
- entry classifier + exit hazard model。
- expected value regression + threshold policy。
- imitation learning from oracle policy。
- policy gradient は後半で検討。

## 評価

- 月別 leaderboard。
- volatility regime 別 leaderboard。
- trade count normalized score。
- drawdown penalty score。
- forced exit penalty。
- 取引時間帯別スコア。
- walk-forward split で、どの市場局面で壊れるかを見える化する。
- no_trade を必ず比較対象に残し、取引したくなるバイアスを抑える。

## 過学習対策

- データを増やす目的は、モデルを大きくすることではなく、期間依存を測ること。
- 少ないデータでも過学習しにくいモデルが理想なので、まずは単純で検証しやすいモデルを優先する。
- train と valid/test の乖離を月別に記録し、平均だけでなく最悪月と分散を見る。
- validation 月で entry/exit threshold と calibration を決め、test 月で閾値を選ばない。
- expected pnl の絶対値は過大評価されやすいため、validation で calibration してから policy に入れる。
- exit timing target を追加し、oracle best exit と実行可能な close timing の差を縮める。
- データを増やしても単月最適化を始めると同じ問題が再発するため、walk-forward を必須にする。

## 外部データ候補

- 経済指標カレンダー。
- 米国金利。
- DXY。
- Gold futures。
- VIX。
- 実運用ブローカーの XAUUSD spread。

外部データを採用する場合は、取得元、時刻粒度、公開遅延、ライセンス、将来リークの有無を必ず記録する。
