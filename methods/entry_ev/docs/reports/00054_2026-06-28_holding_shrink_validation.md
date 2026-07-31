# Holding Shrink Validation

日時: 2026-06-28 18:40 JST
更新日時: 2026-06-28 18:40 JST

## Summary

- Experiment ID: `holding_shrink_validation`
- Status: implemented, validated, not promoted
- Main result: exit-event probabilityで予定保有時間を短縮する `time_exit_holding_shrink` / `loss_first_holding_shrink` を追加した。validation 4foldではno-shrinkより明確に改善してstrict候補を作ったが、2024-12反証月ではNoTradeに大きく負け、entry EV penalty候補にも届かなかった。実装は探索軸として残すが、標準policyには昇格しない。
- Report numbering note: this file is numbered from the internal file `日時`, not filesystem mtime or `更新日時`.

## Implementation

Added `ModelPolicyConfig` fields:

- `time_exit_holding_shrink`
- `loss_first_holding_shrink`

Holding adjustment:

```text
long_holding_multiplier  = 1 - time_exit_holding_shrink  * pred_long_exit_event_prob_0
long_holding_multiplier -=     loss_first_holding_shrink * pred_long_exit_event_prob_2
short_holding_multiplier = 1 - time_exit_holding_shrink  * pred_short_exit_event_prob_0
short_holding_multiplier -=     loss_first_holding_shrink * pred_short_exit_event_prob_2

holding_minutes *= clip(multiplier, 0, 1)
holding_minutes  = clip(holding_minutes, min_predicted_hold_minutes, max_predicted_hold_minutes)
```

This is intentionally different from `time_exit_penalty` / `loss_first_penalty`:

- penalty: entry scoreを落として、参入そのものを減らす。
- holding shrink: entry scoreは維持し、入った後の予定決済を早める。

CLI additions:

- `model-policy --time-exit-holding-shrink`
- `model-policy --loss-first-holding-shrink`
- `model-sweep --time-exit-holding-shrinks`
- `model-sweep --loss-first-holding-shrinks`

Unit coverage:

- `test_timed_model_signal_shrinks_holding_time_with_exit_event_probability`
- sweep normalization default now covers `time_exit_holding_shrink=0.0` and `loss_first_holding_shrink=0.0`

## Validation 4fold

Predictions:

- `experiments/20260628_064332_policy_exit_event_prob_p1_l1p2/predictions_valid.parquet`

Grid:

- policy: `timed_ev`
- entry threshold: `5,10`
- short offset: `8,12`
- side margin: `1`
- holding columns: `pred_long_exit_event_minutes`, `pred_short_exit_event_minutes`
- min entry rank: `0.5`
- max predicted hold minutes: `480,720`
- time-exit holding shrink: `0,0.25,0.5,0.75,1`
- loss-first holding shrink: `0,0.25,0.5,0.75,1`
- EV penalties: `0`
- profit-barrier hard gate: disabled
- extra side margins: `session_regime=asia:5,session_regime=rollover:5`

Artifacts:

- sweeps: `data/reports/backtests/holding_shrink_soft/`
- summary CSV: `data/reports/backtests/20260628_holding_shrink_validation_summary.csv`

Eligibility definition:

- all 4 folds present
- each fold adjusted pnl `>= 0`
- each fold trades `>= 10`
- forced exit max `<= 0.05`
- drawdown max `<= 100`
- strict additionally requires side share max `<= 0.85` and smoothed actual barrier miss max `<= 0.55`

Top strict rows:

| entry | short offset | time shrink | loss shrink | max hold | min pnl | total pnl | min trades | forced max | drawdown max | side share max | smoothed miss max | avg holding mean | worst month |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `10` | `8` | `0.25` | `0.75` | `720` | `55.5528` | `450.7384` | `47` | `0.050000` | `78.5920` | `0.808511` | `0.532258` | `491.0680` | `2024-09` |
| `10` | `8` | `0.75` | `0.75` | `480` | `53.2266` | `443.0060` | `54` | `0.041096` | `73.2788` | `0.814815` | `0.538462` | `396.1514` | `2024-09` |
| `10` | `8` | `0.75` | `0.75` | `720` | `47.0364` | `436.7650` | `52` | `0.046154` | `70.8360` | `0.826923` | `0.533333` | `435.6793` | `2024-09` |
| `10` | `8` | `0.25` | `1.00` | `720` | `45.3490` | `397.1808` | `51` | `0.046154` | `86.0068` | `0.823529` | `0.526316` | `430.1742` | `2024-09` |
| `10` | `8` | `0.50` | `0.75` | `720` | `45.3438` | `459.1104` | `50` | `0.049180` | `69.0080` | `0.820000` | `0.523810` | `459.6640` | `2024-09` |

No-shrink reference:

| entry | short offset | max hold | strict eligible | min pnl | total pnl | min trades | forced max | drawdown max | side share max | smoothed miss max | avg holding mean |
|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `10` | `8` | `720` | `false` | `12.5636` | `287.8596` | `37` | `0.055556` | `77.0800` | `0.837838` | `0.553571` | `610.0054` |

Interpretation:

- holding shrink単独でも、validationでは no-shrink のforced exitとsmoothed missを下げ、strict候補を作った。
- `loss_first_holding_shrink=0.75` 周辺に候補が集まる。time-exitよりloss-first probabilityのほうがholding短縮に効いている。
- 一方でvalidation topのmin pnl `55.5528` は、前回のentry EV penalty top `75.1682` より低い。

## 2024-12 Diagnostic

Predictions:

- `experiments/20260628_064332_policy_exit_event_prob_p1_l1p2/predictions_test.parquet`

Fixed diagnostics:

| label | entry | short offset | time penalty | loss penalty | time shrink | loss shrink | max hold | artifact |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| holding shrink top | `10` | `8` | `0` | `0` | `0.25` | `0.75` | `720` | `data/reports/backtests/20260628_094021_model_timed_ev_2024-12/` |
| holding shrink top2 | `10` | `8` | `0` | `0` | `0.75` | `0.75` | `480` | `data/reports/backtests/20260628_094021_model_timed_ev_2024-12_1/` |
| entry penalty top | `10` | `8` | `6` | `6` | `0` | `0` | `720` | `data/reports/backtests/20260628_094021_model_timed_ev_2024-12_2/` |
| no-shrink reference | `10` | `8` | `0` | `0` | `0` | `0` | `720` | `data/reports/backtests/20260628_094021_model_timed_ev_2024-12_3/` |

Results:

| label | adjusted pnl | raw pnl | trades | profit factor | max drawdown | forced exits | avg holding | direction error | actual barrier miss | EV over realized |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| holding shrink top | `-209.0802` | `-142.9810` | `68` | `0.4728` | `223.9968` | `3` | `415.9412` | `0.5441` | `0.6765` | `20.5732` |
| holding shrink top2 | `-236.7336` | `-166.7680` | `76` | `0.4361` | `264.7456` | `4` | `395.0132` | `0.5395` | `0.6842` | `20.6189` |
| entry penalty top | `-172.7944` | `-115.6510` | `46` | `0.4960` | `209.0240` | `2` | `544.4783` | `0.5870` | `0.7391` | `21.9614` |
| no-shrink reference | `-227.4118` | `-158.4170` | `63` | `0.4507` | `246.1494` | `3` | `461.0000` | `0.5397` | `0.6508` | `21.4299` |

Key diagnostics:

- holding shrink topは no-shrink reference より損失を `18.3316` 縮めた。
- しかし entry penalty top より `36.2858` 悪く、NoTradeには大きく負ける。
- holding shrink topは平均保有時間を `461.0` から `415.9` 分へ短縮したが、trade数は `63` から `68` に増え、2024-12の悪い局面へのentryを十分には止められなかった。
- actual barrier missは no-shrink `0.6508` から holding shrink top `0.6765` へ悪化した。早く閉じるだけでは、profit-barrierへ届かないtradeを十分に救えていない。

## Decision

- `time_exit_holding_shrink` / `loss_first_holding_shrink` 実装は採用する。entry penaltyと異なる探索軸として有用。
- holding shrink単独候補は標準policyへ昇格しない。
- validationでは改善するが、2024-12反証月ではNoTradeに大きく負け、entry EV penalty候補にも届かない。
- exit-event probabilityを「予定保有時間の初期値」だけに反映する方式では弱い。次は、entry penaltyとの組み合わせ、または保有中に確率を再評価して途中決済するdynamic / hazard-like exitを検証する。

## Next Actions

1. holding shrinkとentry EV penaltyを同時に使う小さなgridを試す。
2. planned exitをentry時点で固定するだけでなく、保有中の各decision timestampで `loss_first` / `time_exit` probabilityを見て早期exitするpolicyを追加する。
3. 2024-12で後付け採用しない。validation-onlyで候補を固定し、2024-12は反証月として使う。
