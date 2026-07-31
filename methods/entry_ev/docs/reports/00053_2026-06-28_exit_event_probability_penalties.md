# Exit Event Probability Penalties

日時: 2026-06-28 18:28 JST
更新日時: 2026-06-28 18:28 JST

## Summary

- Experiment ID: `exit_event_probability_penalties`
- Status: implemented, diagnosed, not promoted
- Main result: `time_exit` / `loss_first` probability penaltyを `model-policy` / `model-sweep` に追加した。validation 4foldでは soft penalty がno-penaltyを大きく改善したが、2024-12反証月ではNoTradeに届かなかった。探索軸として残すが、標準policyには昇格しない。
- Report numbering note: this file is numbered from the internal file `日時`, not filesystem mtime or `更新日時`.

## Implementation

Added `ModelPolicyConfig` fields:

- `long_time_exit_column`, default `pred_long_exit_event_prob_0`
- `short_time_exit_column`, default `pred_short_exit_event_prob_0`
- `long_loss_first_column`, default `pred_long_exit_event_prob_2`
- `short_loss_first_column`, default `pred_short_exit_event_prob_2`
- `time_exit_penalty`
- `loss_first_penalty`

Score adjustment:

```text
long_ev  -= time_exit_penalty  * pred_long_exit_event_prob_0
short_ev -= time_exit_penalty  * pred_short_exit_event_prob_0
long_ev  -= loss_first_penalty * pred_long_exit_event_prob_2
short_ev -= loss_first_penalty * pred_short_exit_event_prob_2
```

CLI additions:

- `model-policy --time-exit-penalty`
- `model-policy --loss-first-penalty`
- `model-policy --long-time-exit-column`
- `model-policy --short-time-exit-column`
- `model-policy --long-loss-first-column`
- `model-policy --short-loss-first-column`
- `model-sweep --time-exit-penalties`
- `model-sweep --loss-first-penalties`

Unit coverage:

- `test_exit_event_probability_penalties_reduce_risky_side_ev`
- existing sweep normalization test now covers default `time_exit_penalty=0.0` and `loss_first_penalty=0.0`

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
- profit-barrier hard gate: disabled
- time-exit penalty: `0,2,4,6`
- loss-first penalty: `0,2,4,6`
- extra side margins: `session_regime=asia:5,session_regime=rollover:5`

Artifacts:

- sweeps: `data/reports/backtests/exit_event_penalty_soft/`
- summary CSV: `data/reports/backtests/20260628_exit_event_penalty_soft_validation_summary.csv`

Eligibility definition:

- all 4 folds present
- each fold adjusted pnl `>= 0`
- each fold trades `>= 10`
- forced exit max `<= 0.05`
- drawdown max `<= 100`
- strict additionally requires side share max `<= 0.85` and smoothed actual barrier miss max `<= 0.55`

Top rows:

| entry | short offset | time penalty | loss penalty | max hold | strict eligible | min pnl | total pnl | min trades | forced max | drawdown max | side share max | smoothed miss max |
|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|
| `10` | `8` | `6` | `6` | `720` | `true` | `75.1682` | `531.6246` | `36` | `0.000000` | `85.6920` | `0.825000` | `0.523810` |
| `10` | `8` | `4` | `6` | `720` | `true` | `63.6298` | `476.6438` | `37` | `0.045455` | `85.6920` | `0.829268` | `0.523810` |
| `5` | `12` | `6` | `6` | `720` | `true` | `40.5626` | `403.8764` | `41` | `0.024390` | `87.8746` | `0.833333` | `0.543478` |

No-penalty reference:

| entry | short offset | time penalty | loss penalty | max hold | basic eligible | min pnl | total pnl | min trades | forced max | drawdown max | smoothed miss max |
|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|
| `10` | `8` | `0` | `0` | `720` | `false` | `12.5636` | `287.8596` | `37` | `0.055556` | `77.0800` | `0.553571` |

Interpretation:

- validation上は、time/loss soft penaltyがforced exitとsmoothed missを下げ、strict候補を複数作った。
- topは previous profit-barrier linear penalty validationの top min pnl `52.3018` を超え、validationだけなら有望。
- ただし validationで選ばれたsoft penaltyが未知月へ外挿するかは未確認だったため、2024-12へ固定適用した。

## 2024-12 Diagnostic

Predictions:

- `experiments/20260628_064332_policy_exit_event_prob_p1_l1p2/predictions_test.parquet`

Fixed diagnostics:

| label | entry | short offset | time penalty | loss penalty | max hold | artifact |
|---|---:|---:|---:|---:|---:|---|
| validation top | `10` | `8` | `6` | `6` | `720` | `data/reports/backtests/20260628_092737_model_timed_ev_2024-12/` |
| no penalty reference | `10` | `8` | `0` | `0` | `720` | `data/reports/backtests/20260628_092737_model_timed_ev_2024-12_1/` |
| time-only | `10` | `8` | `6` | `0` | `720` | `data/reports/backtests/20260628_092737_model_timed_ev_2024-12_2/` |
| loss-only | `10` | `8` | `0` | `6` | `720` | `data/reports/backtests/20260628_092737_model_timed_ev_2024-12_3/` |

Results:

| label | adjusted pnl | raw pnl | trades | profit factor | max drawdown | forced exits | direction error | actual barrier miss | EV over realized |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| validation top | `-172.7944` | `-115.6510` | `46` | `0.4960` | `209.0240` | `2` | `0.5870` | `0.7391` | `21.9614` |
| no penalty reference | `-227.4118` | `-158.4170` | `63` | `0.4507` | `246.1494` | `3` | `0.5397` | `0.6508` | `21.4299` |
| time-only | `-178.2488` | `-115.9030` | `57` | `0.5235` | `200.4348` | `2` | `0.5965` | `0.6842` | `21.1240` |
| loss-only | `-175.3652` | `-114.1910` | `50` | `0.5222` | `194.1028` | `2` | `0.6200` | `0.7400` | `21.5784` |

Key diagnostics:

- soft penaltyは no-penaltyより損失とdrawdownを縮めた。
- ただしbest caseでも adjusted pnl `-172.7944` で、NoTradeに大きく負ける。
- 2024-12ではdirection errorが `0.5870` から `0.6200` と高く、exit-event probability penaltyだけでは方向選択の壊れ方を直せない。
- actual profit-barrier missも `0.6842` から `0.7400` と高く、time/loss event probabilityが本当に避けたいtradeを十分に落とせていない。

## Decision

- `time_exit_penalty` / `loss_first_penalty` 実装は採用する。探索軸として有用。
- ただし、今回のsoft penalty候補は標準policyへ昇格しない。
- exit-event probabilityはvalidationでは良いが、2024-12反証月では過学習的に見える。
- 次は単純なentry score penaltyではなく、exit policyそのものを変える。具体的には hazard-like な「途中で閉じる」判断、または predicted event probabilityに応じた予定保有時間の短縮を検証する。

## Next Actions

1. `timed_ev` のholding minutesを、event probabilityで短縮する policy variantを追加する。
2. 例: `planned_holding *= 1 - shrink * loss_first_prob` または `planned_holding *= 1 - shrink * time_exit_prob`。
3. loss/time probabilityが高いtradeをentryで落とすのではなく、早めに閉じてtail lossを削れるかを見る。
4. 2024-12で後付け採用しない。validation-onlyで候補を固定し、2024-12は反証月として使う。
