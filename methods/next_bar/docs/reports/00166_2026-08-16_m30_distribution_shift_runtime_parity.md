# 00166 M30 Distribution Shift runtime parity

日時: 2026-08-16 14:01 JST

## 目的

M30のparallel coverage-aware confidence challengerとして固定済みのDistribution Shiftを、保存済みWindows canonical artifactだけから方向維持75/25でlatest推論する。候補昇格条件に残っていたruntime parityを閉じる。

## 固定仕様とparity

baseline HGB 75%とDistribution Shift HGB 25%を固定平均し、baseline方向を維持する。confidence閾値は0.52、standard loss multiplierは1.0である。

両artifactは7foldの境界、flat tolerance、最大train行、seed、HGB parameter、Platt、uniform sample、全教師、expandingが一致した。特徴集合だけがbaseline 38列とDistribution Shift追加16列（計54列）で意図的に異なる。再学習は行っていない。

## latest結果

判定時刻は2026-06-01 04:30 UTC、volatility normal。

| source/candidate | probability up | weight |
|---|---:|---:|
| baseline | 0.5323172046 | 0.75 |
| Distribution Shift | 0.5229820568 | 0.25 |
| direction-preserving candidate | 0.5299834177 | — |

方向はup。固定confidence 0.52を通過した。JSON丸め後の直接式との差は`5.00e-11`。`odds_valid=false`、`strict_prediction_eligible=false`を維持した。

## 判断

M30 Distribution Shift 0.52 coverage challengerの **full runtime parityをaccepted** とする。これは保存済み最終fold modelと既存データ末尾の機能確認であり、fresh edgeではない。

既存OOSでは71,260行についてcoverage 37.7280%、accuracy 53.4201%、selection score 0.0173422で、Windows baselineへのaccuracy差95%日次bootstrap区間は+0.050520〜+0.477064ptだった。一方、Pressureへのaccuracy・selection score差は区間が0を跨ぐ。完全未使用期間のPressure head-to-headとglobal/local calibrationが通るまで、Pressure 0.52、Pressure + AR 0.55、authoritative direction/confidence、fair odds、registry、paper/live policyを変更しない。

## 成果物

- `experiments/next_bar/distribution_shift_m30_latest_confidence_candidate_windows.json`
- `experiments/next_bar/distribution_shift_m30_latest_confidence_candidate_parity_windows.json`
- `methods/next_bar/config/m30_distribution_shift_confidence_candidate_v1.json`

実行は`run_low_priority_worker.sh`、8 thread、nice/I/O低優先度、CPU only。共有高負荷処理を停止していない。

## 検証

- 75/25直接式と出力確率を照合
- 7fold境界と主要学習設定のartifact parityを照合
- runtime/account/credential変更なし
