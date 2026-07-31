# 0002: 3クラス分類だけを主ターゲットにしない

日付: 2026-06-28 JST
状態: accepted

## 背景

初期 dataset では、未来 24 時間以内の best exit から `long / short / stay_flat` の3クラスラベルを生成した。このラベルは分かりやすいが、深層学習の主ターゲットとしては情報を落としすぎる。

失われる情報:

- long と short の期待値の差の大きさ
- best exit までの時間
- 最大逆行幅
- 強制決済時の損益
- 閾値付近の曖昧さ
- 利益は大きいがリスクも大きい局面

## 決定

今後の学習では、3クラスラベルを主ターゲットにしない。

代わりに、以下の multi-task target を dataset に持たせる。

- `long_best_adjusted_pnl`
- `short_best_adjusted_pnl`
- `long_forced_adjusted_pnl`
- `short_forced_adjusted_pnl`
- `long_max_adverse_pnl`
- `short_max_adverse_pnl`
- `long_best_holding_minutes`
- `short_best_holding_minutes`
- `side_score = long_best_adjusted_pnl - short_best_adjusted_pnl`
- `best_adjusted_pnl` の分位点 bin
- `side_score` の分位点 bin
- `best_holding_minutes` の時間 bin
- `label` は補助タスク、または後処理確認用として残す

## 影響

初期の軽量モデルは、3クラス分類だけでなく、少なくとも以下を比較する。

- long/short expected pnl の回帰
- side_score の回帰またはランキング
- 分位点 bin の分類
- 回帰 + 分類の multi-task

推論時は、モデル出力の連続値から `long / short / stay_flat` を後処理で決める。

## 代替案

3クラス分類だけを使う案は、単純でバックテストへ接続しやすい。しかし情報圧縮が強く、閾値依存も大きいため主ターゲットにはしない。

