# 00172 M5 Haar Multiscale runtime parity

日時: 2026-08-16 19:42 JST

## 目的

M5のindependent broad-confidence challengerであるHaar Multiscaleを、保存済みWindows canonical artifactだけから方向維持75/25でlatest推論し、runtime parityを閉じる。

## 固定仕様とparity

baseline HGB 75%とHaar Multiscale HGB 25%を固定平均し、baseline方向を維持する。4/8/16/32本、3系列・固定12特徴、HGB/Platt、uniform sample、全教師、expanding、confidence 0.515、standard loss multiplier 1.0を変更しない。

両artifactは7fold境界と主要学習設定が一致した。特徴集合だけがbaseline 38列とHaar追加12列（計50列）で意図的に異なる。再学習は行っていない。

## latest結果

判定時刻は2026-06-01 04:55 UTC、volatility high。

| source/candidate | probability up | weight |
|---|---:|---:|
| baseline | 0.5233518569 | 0.75 |
| Haar Multiscale | 0.5184021044 | 0.25 |
| direction-preserving candidate | 0.5221144187 | — |

方向はup。固定0.515を通過した。JSON丸め後の直接式との差は`7.50e-11`。`odds_valid=false`、`strict_prediction_eligible=false`を維持した。

## 判断

M5 Haar Multiscale 0.515 broad confidence候補の **full runtime parityをaccepted** とする。保存済みmodelと既存データ末尾の機能確認でありfresh edgeではない。既存OOSではbaseline gateを通ったがProfileよりproper scoreが悪く、Profile×TCNも支配していない。完全未使用期間のProfile/Profile×TCN head-to-head、down-normal edge、global/local calibrationまで、既存候補、authoritative confidence、fair odds、paper/live policyを変更しない。

## 成果物と検証

- `experiments/next_bar/haar_multiscale_m5_latest_confidence_candidate_windows.json`
- `experiments/next_bar/haar_multiscale_m5_latest_confidence_candidate_parity_windows.json`
- `methods/next_bar/config/m5_haar_multiscale_confidence_candidate_v1.json`
- low-priority worker、CPU only、再学習なし
- runtime/account/credential変更なし
