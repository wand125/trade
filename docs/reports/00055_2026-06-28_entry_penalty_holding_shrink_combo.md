# Entry Penalty Holding Shrink Combo

日時: 2026-06-28 18:48 JST
更新日時: 2026-06-28 18:48 JST

## Summary

- Experiment ID: `entry_penalty_holding_shrink_combo`
- Status: validated, not promoted
- Main result: `time_exit_penalty` / `loss_first_penalty` と `time_exit_holding_shrink` / `loss_first_holding_shrink` の小gridを比較した。validation 4foldでは組み合わせtopがentry penalty単独のmin pnl `75.1682` を `85.1886` へ上げた。一方、2024-12反証月ではbest fixed candidateでも adjusted pnl `-159.0158` でNoTradeに大きく負ける。組み合わせは探索軸として残すが、標準policyには昇格しない。
- Report numbering note: this file is numbered from the internal file `日時`, not filesystem mtime or `更新日時`.

## Setup

Predictions:

- validation: `experiments/20260628_064332_policy_exit_event_prob_p1_l1p2/predictions_valid.parquet`
- 2024-12 diagnostic: `experiments/20260628_064332_policy_exit_event_prob_p1_l1p2/predictions_test.parquet`

Validation grid:

- policy: `timed_ev`
- entry threshold: `10`
- short offset: `8`
- side margin: `1`
- holding columns: `pred_long_exit_event_minutes`, `pred_short_exit_event_minutes`
- min entry rank: `0.5`
- max predicted hold minutes: `480,720`
- time-exit penalty: `0,3,6`
- loss-first penalty: `0,3,6`
- time-exit holding shrink: `0,0.25,0.5`
- loss-first holding shrink: `0,0.5,0.75`
- profit-barrier hard gate: disabled
- extra side margins: `session_regime=asia:5,session_regime=rollover:5`

Artifacts:

- validation sweeps: `data/reports/backtests/entry_penalty_holding_shrink_combo/`
- validation summary: `data/reports/backtests/20260628_entry_penalty_holding_shrink_combo_summary.csv`

Eligibility definition:

- all 4 folds present
- each fold adjusted pnl `>= 0`
- each fold trades `>= 10`
- forced exit max `<= 0.05`
- drawdown max `<= 100`
- strict additionally requires side share max `<= 0.85` and smoothed actual barrier miss max `<= 0.55`

## Validation 4fold

Top strict rows:

| time penalty | loss penalty | time shrink | loss shrink | max hold | min pnl | total pnl | min trades | forced max | drawdown max | side share max | smoothed miss max | EV over realized max | worst month |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `6` | `6` | `0.50` | `0.00` | `720` | `85.1886` | `493.4848` | `37` | `0.023256` | `83.3160` | `0.825000` | `0.534884` | `16.8375` | `2024-09` |
| `6` | `6` | `0.25` | `0.00` | `720` | `80.0648` | `513.3876` | `36` | `0.023256` | `83.8800` | `0.825000` | `0.534884` | `16.5309` | `2024-09` |
| `6` | `6` | `0.00` | `0.00` | `720` | `75.1682` | `531.6246` | `36` | `0.000000` | `85.6920` | `0.825000` | `0.523810` | `15.9873` | `2024-09` |
| `3` | `6` | `0.50` | `0.50` | `720` | `57.7468` | `500.6788` | `40` | `0.025000` | `82.7436` | `0.825000` | `0.530612` | `17.3442` | `2024-11` |
| `0` | `0` | `0.25` | `0.75` | `720` | `55.5528` | `450.7384` | `47` | `0.050000` | `78.5920` | `0.808511` | `0.532258` | `17.2439` | `2024-09` |

Interpretation:

- `time_exit_penalty=6`, `loss_first_penalty=6` を維持し、`time_exit_holding_shrink=0.25-0.50` を足すとfold最低値が上がる。
- `loss_first_holding_shrink` は、entry penaltyと組み合わせるとtopには残らなかった。単独では効いたが、entry側でloss-first確率を既に強く落とすため、holding短縮まで重ねると過剰に見える。
- validation min pnlは combo top `85.1886` > entry penalty単独 `75.1682`。一方、total pnlは entry penalty単独 `531.6246` > combo top `493.4848`。

## 2024-12 Diagnostic

Fixed diagnostics:

| label | time penalty | loss penalty | time shrink | loss shrink | max hold | artifact |
|---|---:|---:|---:|---:|---:|---|
| combo top min-pnl | `6` | `6` | `0.50` | `0.00` | `720` | `data/reports/backtests/20260628_094754_model_timed_ev_2024-12/` |
| combo top2 holdout | `6` | `6` | `0.25` | `0.00` | `720` | `data/reports/backtests/20260628_094754_model_timed_ev_2024-12_1/` |
| entry penalty reference | `6` | `6` | `0.00` | `0.00` | `720` | `data/reports/backtests/20260628_094754_model_timed_ev_2024-12_2/` |
| no-shrink reference | `0` | `0` | `0.00` | `0.00` | `720` | `data/reports/backtests/20260628_094754_model_timed_ev_2024-12_3/` |

Results:

| label | adjusted pnl | raw pnl | trades | profit factor | max drawdown | forced exits | avg holding | direction error | actual barrier miss | EV over realized |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| combo top min-pnl | `-173.6648` | `-118.7120` | `47` | `0.4733` | `200.9338` | `2` | `536.5532` | `0.6383` | `0.7447` | `21.6446` |
| combo top2 holdout | `-159.0158` | `-103.6750` | `46` | `0.5211` | `197.5966` | `2` | `542.1087` | `0.5870` | `0.7174` | `21.5154` |
| entry penalty reference | `-172.7944` | `-115.6510` | `46` | `0.4960` | `209.0240` | `2` | `544.4783` | `0.5870` | `0.7391` | `21.9614` |
| no-shrink reference | `-227.4118` | `-158.4170` | `63` | `0.4507` | `246.1494` | `3` | `461.0000` | `0.5397` | `0.6508` | `21.4299` |

Key diagnostics:

- combo top2は entry penalty reference より adjusted pnlを `13.7786` 改善し、drawdownも `209.0240` から `197.5966` へ縮めた。
- ただしNoTradeには大きく負ける。
- combo top min-pnlはvalidationで最も安定したが、2024-12ではdirection error `0.6383` と悪化し、entry penalty referenceとほぼ同じ損失になった。
- actual barrier missは combo top2 `0.7174` で entry penalty reference `0.7391` より少し改善したが、依然として高い。
- 2024-12のbestは、以前のprofit-barrier raw penalty smoke `-141.9282` にも届いていない。

## Decision

- `entry penalty + holding shrink` はvalidation上のfold最低値を改善するため、探索軸として有用。
- ただし、2024-12反証月ではNoTradeに届かず、標準policyへ昇格しない。
- entry時点で予定保有時間を微調整するだけでは、未知regimeのdirection errorとactual barrier missを十分に抑えられない。
- 次は、保有中の各decision timestampでprobabilityを再評価し、閾値を超えたら途中決済するdynamic / hazard-like exit policyを実装する。

## Next Actions

1. `timed_ev`派生として、保有中に `pred_*_exit_event_prob_0` / `pred_*_exit_event_prob_2` を見て早期exitするpolicyを追加する。
2. validation-onlyでexit probability thresholdを選び、2024-12は反証月として固定適用する。
3. entry penalty + dynamic exit、profit-barrier raw penalty、no-shrink referenceを同一表で比較する。
