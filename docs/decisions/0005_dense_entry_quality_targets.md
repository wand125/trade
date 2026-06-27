# 0005: entry timingを密な品質ターゲットに分解する

日付: 2026-06-28 JST
状態: accepted

## 背景

`long / short / stay_flat` の3クラスラベルは、entry方向の大枠を見るには便利だが、entry timing を直接学習させるには情報を落としすぎる。

特に、entry すべき瞬間だけを正例にすると、以下の問題が出る。

- 正例が少なくなり、学習量が不足する。
- 閾値の少し上と大きく上の区別が消える。
- 「今入るべきか、数十分待つべきか」の差が消える。
- 方向が合っていても exit timing が悪いケースを分離できない。
- deep learning に渡す教師信号が疎になり、表現学習の効率が落ちる。

## 決定

entry timing は単一の分類ラベルに圧縮せず、同じ decision row に複数の密な教師信号を持たせる。

追加するターゲット:

- `long_profit_barrier_hit`
- `short_profit_barrier_hit`
- `long_wait_regret`
- `short_wait_regret`
- `long_entry_local_rank`
- `short_entry_local_rank`
- `long_entry_urgency`
- `short_entry_urgency`
- `long_wait_regret_quantile`
- `short_wait_regret_quantile`
- `long_entry_local_rank_bin`
- `short_entry_local_rank_bin`

意味:

- `profit_barrier_hit`: 未来24時間の経路で、損失バリアより先に利益バリアへ到達したか。
- `wait_regret`: 近い未来にもっと良いentry機会があった場合の機会損失。
- `entry_local_rank`: 近傍時間窓の中で、現在のentry qualityがどの順位にいるか。
- `entry_urgency`: 近傍中央値と比べて現在のentry qualityがどれだけ強いか。
- quantized target: 回帰ノイズを補助分類で安定させるためのbin。

初期実装では、近傍時間窓を `--entry-timing-lookahead-minutes` で指定し、デフォルトは60分とする。

## 影響

学習は以下の階層を持つ。

- EV回帰: long/short の期待 adjusted pnl を推定する。
- direction補助: side score と label を推定する。
- entry quality補助: wait regret、local rank、urgency を推定する。
- risk/exit補助: holding minutes と adverse pnl を推定する。
- barrier補助: 利益到達確率に近い分類を推定する。

これにより、1つの月次datasetの各行を、entry方向だけでなく entry quality / wait timing / exit timing / risk の多方面から学習に使う。

既存datasetには新しい列がないため、この変更後の学習にはdataset再生成が必要。

## 代替案

entry timing を `enter_now / wait` の分類にする案は単純だが、閾値依存が強く正例が少ない。今回の目的は深層学習に使える密な教師信号を増やすことなので、連続値と量子化分類を併用する。
