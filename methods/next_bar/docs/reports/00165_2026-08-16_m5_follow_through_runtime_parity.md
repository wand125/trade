# 00165 M5 Directional Follow-through runtime parity

日時: 2026-08-16 12:32 JST

## 目的

固定0.55 high-confidence shadowとして採用済みのM5 Directional Follow-throughを、保存済みWindows canonical artifactだけから方向維持75/25 latest推論する。report 00141以降に残っていたfull runtime parityを閉じる。

## parity guard拡張

Follow-throughはbaselineと同じ38特徴・HGB/Plattだが、解決済み次足の方向follow-through品質をtrain sample weightだけへ使う。したがって`train_weighting=uniform`対`directional_follow_through`は候補定義上の意図的差である。

multi-source CLIへ`--allow-config-difference`を追加した。

- 既定では従来どおり全主要設定一致を要求
- 指定できるのは既知のparity config keyだけ
- 明示したkey以外の差は拒否
- 実際に観測したsource別値をparity JSONへ保存
- 未知keyは拒否

今回許可したのは`train_weighting`だけである。fold境界、flat tolerance、最大train行、seed、HGB、Platt、全教師、expandingは一致した。

## latest結果

判定時刻は2026-06-01 04:55 UTC、volatility high。

| source/shadow | probability up | weight |
|---|---:|---:|
| baseline | 0.5233518569 | 0.75 |
| Directional Follow-through weighted | 0.5231690506 | 0.25 |
| direction-preserving shadow | 0.5233061553 | — |

方向はup。固定confidence 0.55未満なので、latestではhigh-confidence shadow非選択である。JSON丸め後の直接式との差は`2.50e-11`。`odds_valid=false`、`strict_prediction_eligible=false`を維持した。

## 判断

M5 Directional Follow-through 0.55 shadowの **full runtime parityをaccepted** とする。保存済み最終fold modelと既存データ末尾の機能確認であり、fresh edgeではない。

OOSではProfile 0.55比all accuracy/coverage/selection scoreを改善した一方、confirmationは1,277件である。完全未使用期間のaccuracy、coverage、selection score、global/local calibrationを満たすまで、Profile/Profile×Transition、authoritative confidence、fair odds、registry、paper/live policyを変更しない。

## 成果物

- `experiments/next_bar/directional_follow_through_m5_latest_confidence_shadow_windows.json`
- `experiments/next_bar/directional_follow_through_m5_latest_confidence_shadow_parity_windows.json`
- `methods/next_bar/config/m5_directional_follow_through_high_confidence_shadow_v1.json`

実行は`run_low_priority_worker.sh`、8 thread、nice/I/O低優先度、CPU only。再学習せず、共有高負荷処理を停止していない。standard loss multiplierは1.0のみ。

## 検証

- `tests/test_next_bar_ensemble.py`: 明示許可差分の記録、既定拒否、未知key拒否を追加
- runtime/account/credential変更なし
