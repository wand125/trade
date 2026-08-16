# 00173 M5 Intrabar Profile runtime parity

日時: 2026-08-16 19:48 JST

## 目的

M5 broad confidenceの基準候補Intrabar Profileを、保存済みWindows canonical artifactだけから方向維持75/25でlatest推論する。Profile×TCN/Profile×Transitionの構成要素ではなく、単独Profile候補そのもののruntime parityを固定する。

## 固定仕様とparity

baseline HGB 75%とProfile HGB 25%を固定平均しbaseline方向を維持する。完成M5足内のM1 pathから作る固定27 intrabar特徴、HGB/Platt、uniform sample、全教師、expanding、confidence 0.515、standard loss multiplier 1.0を変更しない。両artifactは7fold境界と主要学習設定が一致し、再学習は行っていない。

## latest結果

判定時刻は2026-06-01 04:55 UTC、volatility high。baseline `0.5233518569`、Profile `0.5197680287`、固定blend `p(up)=0.5224558998`で方向up、0.515を通過した。直接式との差は`5.00e-11`。`odds_valid=false`、`strict_prediction_eligible=false`を維持した。

## 判断

M5 Intrabar Profile 0.515 broad confidence候補の **Windows full runtime parityをaccepted** とする。既存データ末尾の機能確認でありfresh edgeではない。完全未使用期間までauthoritative confidence、fair odds、paper/live policyを変更しない。

## 成果物と検証

- `experiments/next_bar/intrabar_profile_m5_latest_confidence_candidate_windows.json`
- `experiments/next_bar/intrabar_profile_m5_latest_confidence_candidate_parity_windows.json`
- low-priority worker、CPU only、再学習なし
- runtime/account/credential変更なし
