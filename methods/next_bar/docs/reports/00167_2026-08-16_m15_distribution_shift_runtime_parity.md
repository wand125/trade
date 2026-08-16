# 00167 M15 Distribution Shift runtime parity

日時: 2026-08-16 18:27 JST

## 目的

M15のWindows canonical broad confidence候補として固定済みのDistribution Shiftを、保存済みartifactだけから方向維持75/25でlatest推論する。候補昇格条件に残っていたruntime parityを閉じる。

## 固定仕様とparity

baseline HGB 75%とDistribution Shift HGB 25%を固定平均し、baseline方向を維持する。confidence閾値は0.515、standard loss multiplierは1.0である。

両artifactは7foldの境界、flat tolerance、最大train行、seed、HGB parameter、Platt、uniform sample、全教師、expandingが一致した。特徴集合だけがbaseline 38列とDistribution Shift追加16列（計54列）で意図的に異なる。再学習は行っていない。

## latest結果

判定時刻は2026-06-01 04:45 UTC、volatility normal。

| source/candidate | probability up | weight |
|---|---:|---:|
| baseline | 0.5583611895 | 0.75 |
| Distribution Shift | 0.5514037088 | 0.25 |
| direction-preserving candidate | 0.5566218193 | — |

方向はup。固定confidence 0.515を通過した。JSON丸め後の直接式との差は`2.50e-11`。`odds_valid=false`、`strict_prediction_eligible=false`を維持した。

## 判断

M15 Distribution Shift 0.515 broad confidence候補の **full runtime parityをaccepted** とする。保存済み最終fold modelと既存データ末尾の機能確認であり、fresh edgeではない。

既存OOS 145,140行ではcoverage 54.4440%、accuracy 52.9980%、selection score 0.0195522だった。同一Windows platformのProfileへaccuracy 7/7foldで勝ち、all accuracy差95%日次bootstrap区間は+0.019346〜+0.241333pt、Brier/log lossも改善側だった。ただしmixed-platform registryを直ちに更新しない。M15全候補の同一platform registry再構築とfresh global/local calibrationまで、authoritative confidence、fair odds、paper/live policyを変更しない。

## 成果物

- `experiments/next_bar/distribution_shift_m15_latest_confidence_candidate_windows.json`
- `experiments/next_bar/distribution_shift_m15_latest_confidence_candidate_parity_windows.json`
- `methods/next_bar/config/m15_distribution_shift_confidence_candidate_v1.json`

実行は`run_low_priority_worker.sh`、8 thread、nice/I/O低優先度、CPU only。共有高負荷処理を停止していない。

## 検証

- 75/25直接式と出力確率を照合
- 7fold境界と主要学習設定のartifact parityを照合
- runtime/account/credential変更なし
