# 00169 M1 Path Persistence runtime parity

日時: 2026-08-16 19:07 JST

## 目的

M1のparallel direction accuracy championとして固定済みのPath Persistenceを、保存済みWindows canonical artifactだけから通常75/25 blendでlatest推論する。方向維持confidenceではなく、実際の方向候補についてruntime parityを固定する。

## 固定仕様とparity

baseline HGB 75%とPath Persistence HGB 25%を固定平均し、`probability_up >= 0.5`で方向を決める。Pathの5/10/20/50本、14加工特徴、HGB/Platt、uniform sample、全教師、expanding、standard loss multiplier 1.0を変更しない。

両artifactは7fold境界、flat tolerance、最大train行、seed、HGB parameter、Platt、uniform sample、全教師、expandingが一致した。特徴集合だけがbaseline 38列とPath追加14列（計52列）で意図的に異なる。再学習は行っていない。

## latest結果

判定時刻は2026-06-01 04:59 UTC、volatility normal。

| source/candidate | probability up | direction | weight |
|---|---:|---|---:|
| baseline | 0.4972960077 | down | 0.75 |
| Path Persistence | 0.5026628577 | up | 0.25 |
| direction candidate | 0.4986377202 | down | — |

親2本は方向不一致だったが、固定blendはdownとなった。直接式との差は浮動小数精度内の`5.55e-17`。confidence/odds用途ではないため、`odds_valid=false`、`strict_prediction_eligible=false`を維持した。

## 判断

M1 Path Persistence 75/25方向候補の **full runtime parityをaccepted** とする。保存済み最終fold modelと既存データ末尾の機能確認であり、fresh edgeではない。

既存OOS 2,183,717行ではbaseline比+942件、accuracy 7/7fold、paired UTC-day bootstrapでdevelopment/confirmation/allのaccuracy差とall Brier/log loss差が改善側だった。一方、confidence選別はconfirmation 0/3foldなので不採用のままである。完全未使用期間でaccuracy、Brier、log lossを同時に確認するまでauthoritative direction/confidence、fair odds、paper/live policyを変更しない。

## 成果物

- `experiments/next_bar/path_persistence_m1_latest_direction_candidate_windows.json`
- `experiments/next_bar/path_persistence_m1_latest_direction_candidate_parity_windows.json`
- `methods/next_bar/config/m1_path_persistence_direction_candidate_v1.json`

実行は`run_low_priority_worker.sh`、8 thread、nice/I/O低優先度、CPU only。共有高負荷処理を停止していない。

## 検証

- 75/25直接式と出力確率を照合
- 7fold境界と主要学習設定のartifact parityを照合
- runtime/account/credential変更なし
