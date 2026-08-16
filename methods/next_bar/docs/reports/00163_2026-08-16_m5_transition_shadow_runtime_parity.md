# 00163 M5 Transition shadow runtime parity

日時: 2026-08-16 10:30 JST

## 目的

report 00151で固定したPressure×Transition方向shadowとProfile×Transition confidence 0.515 shadowを、保存済みWindows canonical artifactだけからlatest推論できるようにする。再学習せず、OOSと同じ3-source固定重み、時刻、方向維持をruntimeで検証する。

## 実装

`predict_latest_multi_ensemble.py`と共通関数を追加した。

- `--source LABEL=MODEL_DIR=WEIGHT`を複数受け取り、重みが有限・非負・合計1であることを要求
- 全sourceの7fold境界と主要train/calibration設定を照合
- model typeとfeature setの意図的な差はparity manifestへ記録
- timeframe、bar start、decision timestampの完全一致を要求
- confidence shadowは最初のsourceであるbaseline方向を維持
- source別probabilityとweightをlatest JSONへ保存
- odds認可経路を持たず、`odds_valid=false`、`strict_prediction_eligible=false`を固定

入力modelは各walk-forward artifactの最後の`test2026_partial` modelで、train end 2025-01-01、calibration end 2026-01-01、test end 2026-06-01で揃っている。新規fitは行っていない。

## latest結果

判定時刻は2026-06-01 04:55 UTC、volatilityはhigh、全sourceとshadow方向はupだった。

| shadow/source | probability up | weight |
|---|---:|---:|
| baseline | 0.5233518569 | 0.750 |
| Pressure | 0.5176241393 | 0.125 |
| Transition | 0.5036710893 | 0.125 |
| Pressure×Transition方向shadow | 0.5201757962 | — |
| Profile | 0.5197680287 | 0.125 |
| Profile×Transition confidence shadow | 0.5204437824 | — |

confidence shadowは固定0.515を通過した。JSON丸め値による直接加重式との差は方向shadow`5.0e-11`、confidence shadow`2.5e-11`である。内部float経路は同じ加重式を使用する。

## 判断

2本のshadowの **full runtime parityをaccepted** とする。report 00151の未達条件からruntime実装不足を外す。

これは既存OOS最終fold modelを既存データ末尾へ適用した機能確認であり、完全未使用期間の精度証拠ではない。Pressure/Profile/Profile×TCN/Follow-through、authoritative direction/confidence、fair odds、registry、paper/live policyは変更しない。0.55 Transition案も復活させない。standard loss multiplierは1.0のみとする。

残る昇格条件はfresh期間での親head-to-head、direction accuracyとproper score、confidence accuracy/selection score/proper score、down-normal Wilson edge、global/local calibrationである。

## 成果物

- `experiments/next_bar/pressure_transition_bayes_m5_latest_direction_shadow_windows.json`
- `experiments/next_bar/pressure_transition_bayes_m5_latest_direction_shadow_parity_windows.json`
- `experiments/next_bar/profile_transition_bayes_m5_latest_confidence_shadow_windows.json`
- `experiments/next_bar/profile_transition_bayes_m5_latest_confidence_shadow_parity_windows.json`
- `methods/next_bar/config/m5_transition_bayes_ensemble_shadow_v1.json`

実行は既存`run_low_priority_worker.sh`、8 thread、nice/I/O低優先度、CPU only。ComfyUI、Ollama、Open WebUI、Claude等を停止していない。

## 検証

- `tests/test_next_bar_ensemble.py`: 24 passed
- 固定重み、方向維持、時刻不一致、重み不正、fold/config不一致をテスト
- runtime/account/credential変更なし
