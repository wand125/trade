# 00170 M1 Distribution Shift Windows runtime parity

日時: 2026-08-16 19:24 JST

## 目的

M1のstability/proper-score方向challenger兼0.51 ultra-broad confidence challengerであるDistribution Shiftを、保存済みWindows canonical artifactだけから通常75/25でlatest推論する。旧platform由来latestを運用値として混在させず、Windows parityを固定する。

## 固定仕様とparity

baseline HGB 75%とDistribution Shift HGB 25%を固定平均する。方向用途は通常blend、confidence用途はbaseline方向維持である。今回のlatestは両sourceともdownなので、どちらの経路でも同じ確率となる。8/64/128本、固定16加工特徴、HGB/Platt、uniform sample、全教師、expanding、standard loss multiplier 1.0を変更しない。

両artifactは7fold境界、flat tolerance、最大train行、seed、HGB parameter、Platt、uniform sample、全教師、expandingが一致した。特徴集合だけがbaseline 38列とShift追加16列（計54列）で意図的に異なる。再学習は行っていない。

## latest結果

判定時刻は2026-06-01 04:59 UTC、volatility normal。

| source/candidate | probability up | direction | weight |
|---|---:|---|---:|
| baseline | 0.4972960077 | down | 0.75 |
| Distribution Shift | 0.4978306101 | down | 0.25 |
| direction candidate | 0.4974296583 | down | — |

直接式との差は0。固定confidence 0.51には届かず、ultra-broad laneでは非選択である。`odds_valid=false`、`strict_prediction_eligible=false`を維持した。

旧configのlatest `0.4985584768`に対してWindows値は`-0.0011288185`異なった。方向は同じdownだが、platformを混在させず旧値をlegacy記録へ退避し、Windows canonical値をlatestとする。

## 判断

M1 Distribution Shift 75/25の **Windows full runtime parityをaccepted** とする。保存済み最終fold modelと既存データ末尾の機能確認であり、fresh edgeではない。

既存OOS 2,183,717行では方向accuracy/Brier/log lossを7/7fold改善し、paired UTC-day bootstrapも支持した。一方、0.51 confidenceはdown-low edgeと局所校正が不十分である。完全未使用期間の方向3指標、confidence selection score、固定6セル、局所校正まで、Path accuracy champion、authoritative direction/confidence、fair odds、paper/live policyを変更しない。

## 成果物

- `experiments/next_bar/distribution_shift_m1_latest_direction_candidate_windows.json`
- `experiments/next_bar/distribution_shift_m1_latest_direction_candidate_parity_windows.json`
- `methods/next_bar/config/m1_distribution_shift_direction_confidence_candidate_v1.json`

実行は`run_low_priority_worker.sh`、8 thread、nice/I/O低優先度、CPU only。共有高負荷処理を停止していない。

## 検証

- 75/25直接式と出力確率を照合
- 7fold境界と主要学習設定のartifact parityを照合
- runtime/account/credential変更なし
