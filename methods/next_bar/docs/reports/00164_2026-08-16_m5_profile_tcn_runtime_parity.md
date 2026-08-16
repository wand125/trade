# 00164 M5 Profile × TCN runtime parity

日時: 2026-08-16 11:04 JST

## 目的

report 00142で固定したProfile×TCN 0.515 sequence-diversity confidence shadowを、保存済みWindows canonical artifactだけからlatest推論する。固定3-source重みとbaseline方向維持をruntimeで再現し、未達だったfull parityを閉じる。

## 固定仕様

- sources: baseline HGB、Intrabar Profile HGB、causal TCN
- probability weights: 0.75 / 0.125 / 0.125
- direction: baseline方向を維持
- confidence threshold: 0.515
- model: 各walk-forward artifactの`test2026_partial`保存model
- train/calibration/test end: 2025-01-01 / 2026-01-01 / 2026-06-01
- odds runtime authorization: false
- standard loss multiplier: 1.0

sequence、network、epoch、weight、閾値を変更せず、新規fitを行っていない。

## latest結果

判定時刻は2026-06-01 04:55 UTC、volatility high。

| source/shadow | probability up | weight |
|---|---:|---:|
| baseline | 0.5233518569 | 0.750 |
| Profile | 0.5197680287 | 0.125 |
| TCN | 0.5161988528 | 0.125 |
| Profile×TCN shadow | 0.5220097528 | — |

方向はupで固定0.515を通過した。JSON丸め値の直接式との差は`6.25e-11`で、内部floatでは共通加重実装を使う。7fold境界、主要train/calibration設定、latest key、重み合計がparity guardを通過した。`odds_valid=false`、`strict_prediction_eligible=false`である。

## 判断

Profile×TCN shadowの **full runtime parityをaccepted** とする。これは既存最終fold modelと既存データ末尾の機能確認で、fresh予測品質の証拠ではない。

親ProfileへのOOS accuracy/selection score増分は区間が0を跨ぎ、confirmation down-normalも4,152件・accuracy 50.9634%・Wilson lower 49.4426%でedge未確認である。したがってProfile/EWMA/Profile×Transition/Follow-through、authoritative confidence、fair odds、registry、paper/live policyは変更しない。

## 成果物

- `experiments/next_bar/profile_tcn_m5_latest_confidence_shadow_windows.json`
- `experiments/next_bar/profile_tcn_m5_latest_confidence_shadow_parity_windows.json`
- `methods/next_bar/config/m5_profile_tcn_confidence_shadow_v1.json`

実行は`run_low_priority_worker.sh`、8 thread、nice/I/O低優先度、CPU only。共有高負荷処理は停止していない。

## 検証

- multi-source固定重み、方向維持、alignment、fold/config guardはreport 00163で追加した共通テストを使用
- runtime/account/credential変更なし
