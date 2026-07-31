# 0009: MLP holding predictionにはfail-close guardを固定する

日付: 2026-06-29 10:05 JST
状態: accepted

## 背景

2025-04で `timed_ev` policyが異常高回転化し、trade数が約2500件まで増えた。主因はentry riskではなく、MLP exit holding predictionの負値・極短値がclipされ、ほぼ即時決済と再entryを繰り返すことだった。

`00125` で validation 4ヶ月と apply 4ヶ月に対して、primary MLP holdingの妥当性閾値を比較した。

## 決定

MLP holdingを使う `timed_ev` 系実験では、標準安全制約として `min_valid_predicted_hold_minutes=30` の fail-close skip を使う。

具体的には、primary holding predictionが非finiteまたは30分未満なら、その候補ではentryしない。HGB holdingへの fallback は標準採用しない。

これはvalidation PnLで最適化されたedgeではなく、外挿破綻値を売買ロジックへ渡さないための妥当性制約として扱う。閾値の細かい探索は行わず、`30` を固定する。

## 影響

- 2025-04型の高回転破綻を大きく抑える。
- apply 4ヶ月では base sum PnLが `-261.3216 -> 246.8762`、high cost sum PnLが `-1435.1746 -> 132.6970` に改善した。
- 代表validation 4ヶ月では `min_valid=-inf/30/60/120` が完全に同じ結果だったため、過去validationに対する過剰最適化ではない。
- MLP holding系の比較では、今後 `trade_count`, `median_holding_minutes`, high-cost drawdownを必ず確認する。
- CLIでは、`model-policy` の `--min-valid-predicted-hold-minutes` 省略時と `model-sweep` の default `auto` により、holding columnが `pred_mlp_*` なら `30` を自動適用する。従来clip-onlyを再現する場合だけ明示的に `-inf` を指定する。

## 代替案

- 従来のclip-only挙動を続ける: 2025-04で異常高回転を再発するため却下。
- `min_valid=60` または `120` を採用する: applyでは `30` より合計PnLと最低月が悪く、取引を削りすぎるため却下。
- HGB holding fallbackを採用する: 2025-04の損失は縮めるが、skipより弱く、悪い取引を残しやすいため却下。
- 2025-04だけを見て閾値を最適化する: post-hoc overfittingになるため却下。`30` は最小限の妥当性制約として固定し、細かく最適化しない。
