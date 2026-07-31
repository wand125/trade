# Holding Guard Validation Apply

日時: 2026-06-29 10:05 JST
更新日時: 2026-06-29 10:05 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻である `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## 目的

`00124` で 2025-04 の主因は stateful entry risk ではなく、MLP holding prediction の外挿破綻による異常高回転だと確認した。

今回は `timed_ev` の holding guard / fallback を、2025-04単月の後付けではなく、代表validation 4ヶ月とapply 4ヶ月の両方で固定条件比較する。

検証する選択肢:

- `skip`: primary MLP holding が無効または閾値未満なら、その候補は入らない。
- `fallback`: primary MLP holding が無効または閾値未満なら、HGB exit event minutesをholdingに使う。

## 条件

共通policy:

- policy: `timed_ev`
- entry threshold: `12`
- short entry threshold offset: `6`
- side margin: `5`
- min entry rank: `0.5`
- long/short EV: `pred_long_best_adjusted_pnl`, `pred_short_best_adjusted_pnl`
- primary holding: `pred_mlp_long_exit_event_minutes`, `pred_mlp_short_exit_event_minutes`
- fallback holding: `pred_long_exit_event_minutes`, `pred_short_exit_event_minutes`
- max predicted hold: `480`
- side EV penalty: `short:combined_regime=down_low_vol:5`, `short:combined_regime=up_low_vol:10`
- profit/loss: `1.0 / 1.20`
- high cost: spread `0.2`, slippage `0.1`, execution delay `1`

月:

- validation: `2024-07`, `2024-09`, `2024-11`, `2025-01`
- apply: `2024-12`, `2025-02`, `2025-03`, `2025-04`

`min_valid_predicted_hold_minutes` は `-inf`, `30`, `60`, `120` を比較した。`-inf` は従来のclip-only挙動。

## Validation Result

代表validationでは、skip / fallback とも `min_valid` を上げても結果は完全に同じだった。つまり、validationの選択済みtradeにはMLP holdingの負値・極端な短時間予測が出ていない。

| mode | cost | min_valid | sum PnL | min month | trades | max DD | forced |
|---|---|---:|---:|---:|---:|---:|---:|
| skip | base | `-inf/30/60/120` | `622.6486` | `138.0338` | `275` | `85.0166` | `0` |
| skip | high | `-inf/30/60/120` | `500.5422` | `96.8776` | `275` | `88.9514` | `0` |
| fallback | base | `-inf/30/60/120` | `622.6486` | `138.0338` | `275` | `85.0166` | `0` |
| fallback | high | `-inf/30/60/120` | `500.5422` | `96.8776` | `275` | `88.9514` | `0` |

このため、guard threshold はvalidation PnLで最適化できるパラメータではない。採るなら、外挿破綻値を取引ロジックへ渡さない安全制約として採る。

## Apply Result

apply 4ヶ月では、従来挙動が2025-04で異常高回転化した。`skip min_valid=30` はtrade数を大きく抑え、base/high costの両方で4ヶ月合計、最低月、drawdownを改善した。

| mode | cost | min_valid | sum PnL | min month | trades | max DD | forced |
|---|---|---:|---:|---:|---:|---:|---:|
| skip | base | `-inf` | `-261.3216` | `-503.8224` | `2910` | `718.7252` | `4` |
| skip | base | `30` | `246.8762` | `-18.7168` | `377` | `249.9600` | `4` |
| skip | base | `60` | `171.1262` | `-70.3180` | `356` | `305.8864` | `3` |
| skip | base | `120` | `33.7764` | `-170.9948` | `327` | `292.5160` | `4` |
| skip | high | `-inf` | `-1435.1746` | `-1503.3702` | `2913` | `1541.9652` | `4` |
| skip | high | `30` | `132.6970` | `-34.3748` | `380` | `259.0392` | `4` |
| skip | high | `60` | `57.3158` | `-84.5128` | `358` | `298.6506` | `4` |
| skip | high | `120` | `-44.3274` | `-158.7062` | `330` | `280.2572` | `5` |
| fallback | base | `-inf` | `-261.3216` | `-503.8224` | `2910` | `718.7252` | `4` |
| fallback | base | `30` | `-42.2164` | `-276.5130` | `376` | `525.5602` | `4` |
| fallback | base | `60` | `-34.1336` | `-265.3590` | `368` | `523.8182` | `4` |
| fallback | base | `120` | `-47.5860` | `-259.7532` | `353` | `518.2124` | `4` |
| fallback | high | `-inf` | `-1435.1746` | `-1503.3702` | `2913` | `1541.9652` | `4` |
| fallback | high | `30` | `-132.4234` | `-261.2606` | `379` | `528.7000` | `4` |
| fallback | high | `60` | `-125.7582` | `-252.0706` | `371` | `524.2820` | `4` |
| fallback | high | `120` | `-142.4664` | `-250.4794` | `356` | `522.6908` | `4` |

## 月別 delta

`skip min_valid=30` の月別delta:

| month | base delta | high cost delta | base trades | high trades |
|---|---:|---:|---:|---:|
| `2024-12` | `+10.2944` | `+23.3654` | `92 -> 77` | `94 -> 79` |
| `2025-02` | `+5.3848` | `+49.7088` | `182 -> 113` | `182 -> 113` |
| `2025-03` | `+7.4130` | `+15.8778` | `152 -> 110` | `152 -> 110` |
| `2025-04` | `+485.1056` | `+1478.9196` | `2484 -> 77` | `2485 -> 78` |

`skip min_valid=30` は、2025-04だけでなく4ヶ月全てでdeltaが正だった。これはholding predictionの異常値を取引頻度へ直結させない制約として筋がよい。

## 判断

`min_valid_predicted_hold_minutes=30` の fail-close skip を、MLP holdingを使う `timed_ev` 実験の標準安全制約にする。

ただし、これはvalidation PnLで選ばれたedgeではない。扱いは以下。

- 標準policy候補の成績比較では、MLP holding policyに `min_valid=30` を含める。
- 閾値の細かい最適化はしない。`30` は「負値・極端な短時間holdingを拒否する最小限の妥当性制約」として固定する。
- `fallback` は2025-04の損失を縮めるが、skipより弱く、HGB holdingへ逃がして悪い取引を残す傾向があるため標準にはしない。
- validationで効果が出ないため、これをPnL改善パラメータとして扱わない。外挿破綻を売買ルールへ渡さない fail-close として扱う。

次にやること:

1. 今後のMLP holding系実験では `--min-valid-predicted-hold-minutes 30` を固定する。
2. その上で、entry/side EV calibration、exit timing target、stateful/ranking targetを再評価する。
3. 2025-04型の高回転破綻が再発していないかを、trade count / median holding / forced rate / high-cost drawdownで必ず確認する。

## Artifacts

- validation summary: `data/reports/backtests/20260629_holding_guard_validation_apply_summary.csv`
- validation skip base: `data/reports/backtests/holding_guard_validation_skip_base/`
- validation skip high cost: `data/reports/backtests/holding_guard_validation_skip_highcost/`
- validation fallback base: `data/reports/backtests/holding_guard_validation_fallback_base/`
- validation fallback high cost: `data/reports/backtests/holding_guard_validation_fallback_highcost/`
- apply skip base: `data/reports/backtests/holding_guard_apply_skip_base/`
- apply skip high cost: `data/reports/backtests/holding_guard_apply_skip_highcost/`
- apply fallback base: `data/reports/backtests/holding_guard_apply_fallback_base/`
- apply fallback high cost: `data/reports/backtests/holding_guard_apply_fallback_highcost/`

## Verification

- `python3 -m unittest tests.test_docs_reports`: OK, 2 tests
