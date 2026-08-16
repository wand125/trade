# 00168 M5 EWMA Asymmetry runtime parity

日時: 2026-08-16 18:36 JST

## 目的

M5のparallel broad confidence候補として固定済みのEWMA Asymmetryを、保存済みWindows canonical artifactだけから方向維持75/25でlatest推論する。候補model単体latestではなく、実際のconfidence blendについてruntime parityを閉じる。

## 固定仕様とparity

baseline HGB 75%とEWMA Asymmetry HGB 25%を固定平均し、baseline方向を維持する。confidence閾値は0.515、standard loss multiplierは1.0である。

両artifactは7fold境界、flat tolerance、最大train行、seed、HGB parameter、Platt、uniform sample、全教師、expandingが一致した。特徴集合だけがbaseline 38列とEWMA追加12列（計50列）で意図的に異なる。再学習は行っていない。

## latest結果

判定時刻は2026-06-01 04:55 UTC、volatility high。

| source/candidate | probability up | weight |
|---|---:|---:|
| baseline | 0.5233518569 | 0.75 |
| EWMA Asymmetry | 0.5295695162 | 0.25 |
| direction-preserving candidate | 0.5249062717 | — |

方向はup。固定confidence 0.515を通過した。JSON丸め後の直接式との差は`2.50e-11`。`odds_valid=false`、`strict_prediction_eligible=false`を維持した。

## 判断

M5 EWMA Asymmetry 0.515 broad confidence候補の **full runtime parityをaccepted** とする。保存済み最終fold modelと既存データ末尾の機能確認であり、fresh edgeではない。

既存OOS 439,881行のうちlaneは221,618行、coverage 50.3814%、accuracy 52.6938%、selection score 0.0176449だった。baselineへのconfirmation accuracy/scoreとall proper scoreの改善は支持されたが、Profileへの全期間差は未確定で、down-normalのWilson edgeも未確認である。完全未使用期間の4指標と固定6セルの局所校正が通るまで、Profile/Profile×TCN/Profile×Transition、authoritative confidence、fair odds、paper/live policyを変更しない。

## 成果物

- `experiments/next_bar/ewma_asymmetry_state_m5_latest_confidence_candidate_windows.json`
- `experiments/next_bar/ewma_asymmetry_state_m5_latest_confidence_candidate_parity_windows.json`
- `methods/next_bar/config/m5_ewma_asymmetry_confidence_candidate_v1.json`

実行は`run_low_priority_worker.sh`、8 thread、nice/I/O低優先度、CPU only。共有高負荷処理を停止していない。

## 検証

- 75/25直接式と出力確率を照合
- 7fold境界と主要学習設定のartifact parityを照合
- runtime/account/credential変更なし
