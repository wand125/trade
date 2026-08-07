# 00001 Direction edge economics

日時: 2026-08-07 19:35 JST

## 目的

校正済み次足方向確率を、値幅・tail risk・コストを含む売買EVへ変換できるか確認する。

## 方法

- 対象: XAUUSD M15、2020〜2026年途中の方向モデルOOS予測。
- EVモデルは過去OOS foldだけで学習し、次foldを評価するnested chronology。
- entryは予測対象足open、exitは同じ足close、1 oz。
- confidence 0.54以上を基本母集団とした。
- 実体値幅はATR20で正規化。
- 正解時gain、不正解時loss、0.75 ATR以上のtail lossを別モデル化。
- 損失は1.2倍。コスト感応度は0、0.05、0.10、0.20、0.30。

## 結果

| policy | rows | accuracy | gross mean | gross positive folds | loss×1.2 mean | loss×1.2 positive folds |
|---|---:|---:|---:|---:|---:|---:|
| direction only | 17,354 | 54.30% | +0.0978 | 6/6 | -0.1039 | 0/6 |
| expected EV > 0 | 13,335 | 53.98% | +0.1279 | 6/6 | -0.0590 | 1/6 |
| component risk EV > 0 | 6,105 | 54.25% | +0.1447 | 6/6 | -0.0143 | 4/6 |
| direct risk EV + tail | 7,106 | 54.87% | +0.1099 | 6/6 | -0.0711 | 2/6 |

component risk EV候補の予測平均は `+0.0390 ATR` だったが、実現損失重み付き損益はnegative。direct risk EV + tailも予測平均 `+0.0758 ATR` に対して実現値 `-0.0162 ATR`、bias `+0.0920 ATR` だった。

post-hocに良く見えたtail probability 0.075は、未使用だった2021〜2022年を追加すると両年の損失重み付き損益がnegativeとなり棄却した。

## ATR stop

direction-onlyへ0.50、0.75、1.00、1.50、2.00 ATR stopを固定比較した。grossは全条件で6/6 fold positiveだが、損失1.2倍後は最大でも1/6 fold positive。最良の2.00 ATRでもaggregate `-1,531.86`、0.05 cost込み `-2,399.56` だった。

## 判断

方向accuracyのedgeは存在するが、外れ足の値幅とコストを吸収できない。単独次足売買、選別EV、固定ATR stopはいずれも標準採用しない。予測確率は「方向が当たるオッズ」であり、「利益になるオッズ」ではない。

追記: 損失1.2倍は2026-08-07 19:50 JST以降、標準採用条件ではなく任意stress testへ変更した。以後は通常損益とコスト控除後損益を主評価にする。
