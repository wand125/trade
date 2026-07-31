# Entry EV Direction Exit Residual Target Diagnostics

日時: 2026-07-02 01:17 JST
更新日時: 2026-07-02 01:17 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00254でforced-exit selectorを止めたため、次の本流として direction / exit-capture residual target をvalidation enriched trades上で作った。
- `scripts/experiments/entry_ev_direction_exit_residual_target_diagnostics.py` を追加した。
- inputは00254のmulti-family enrichment output 77 trades。
- targetは `direction_error_loss_target`, `same_side_missed_loss_target`, `large_exit_regret_loss_target`, `hold_too_long_loss_target` などを同じ行に作る。
- calibration featureはdecision-timeで見える bucket のみ。実現PnL、actual best exit、exit regret、direction errorはtarget側だけで使い、group featureには入れない。
- validationでは `direction_error_loss_target` が29件 / target PnL `-104.8800`、`large_exit_regret_loss_target` が8件 / `-57.6552`、`hold_too_long_loss_target` が9件 / `-55.9920`。
- pointwiseでは `selected_ev_overestimate_risk` が direction/profit-barrier miss系に AUC `0.7083`、`selected_time_exit_prob` が realized lossに AUC `0.6802`。
- ただし chronological bucket calibrationは no-prior share `0.7403` と高く、best pooled AUCも `profit_exit -> hold_too_long 0.6875`, `profit_exit -> large_exit_regret 0.6667` 程度。direction error系は `side_context` pooled AUC `0.5208`。
- 判断: direction/exit residual target generationはaccepted。現validation supportだけでは標準policyやentry blockerへ接続しない。

## Artifacts

- Script:
  - `scripts/experiments/entry_ev_direction_exit_residual_target_diagnostics.py`
- Test:
  - `tests/test_entry_ev_direction_exit_residual_target_diagnostics.py`
- Input enriched trades:
  - `data/reports/backtests/20260701_155806_20260702_entry_ev_side_prior_pressure_s0p5_validation_trade_enrichment_s1/residual_enriched_trades.csv`
- Diagnostic artifact:
  - `data/reports/backtests/20260701_161638_20260702_entry_ev_direction_exit_residual_target_diagnostics_s1/`

## Method

Target families:

```text
realized_loss_target
direction_error_loss_target
same_side_missed_loss_target
low_capture_loss_target
large_exit_regret_loss_target
profit_barrier_miss_loss_target
hold_too_long_loss_target
direction_and_exit_loss_target
same_side_large_regret_loss_target
direction_or_exit_loss_target
```

Important definitions:

```text
same_side_oracle_edge := actual_taken_best_adjusted_pnl >= 5.0
low_exit_capture := same_side_oracle_edge and exit_capture_ratio <= 0.25
large_exit_regret := exit_regret >= 20.0
hold_too_long := oracle_holding_gap_minutes <= -30 and exit_regret > 0
```

Calibration specs:

```text
side_context       := direction + combined_regime + session_regime
confidence_exit    := direction + side_confidence_gap_bucket + loss_first_prob_bucket + time_exit_prob_bucket
profit_exit        := direction + pred_profit_barrier_bucket + loss_first_prob_bucket + pred_exit_hold_bucket
ev_exit            := direction + selected_ev_overestimate_bucket + pred_fixed_slope_bucket + pred_720_bucket
context_confidence := direction + combined_regime + session_regime + side_confidence_gap_bucket
```

`context_confidence` は実装には入れたが、今回の実行ではsupport不足を避けるため使っていない。

## Target Support

Validation enriched trades 77 rows:

| target | count | rate | target PnL | false PnL |
|---|---:|---:|---:|---:|
| `realized_loss_target` | `41` | `0.5325` | `-130.0872` | `+230.3970` |
| `direction_error_loss_target` | `29` | `0.3766` | `-104.8800` | `+205.1898` |
| `profit_barrier_miss_loss_target` | `29` | `0.3766` | `-104.8800` | `+205.1898` |
| `direction_and_exit_loss_target` | `29` | `0.3766` | `-104.8800` | `+205.1898` |
| `same_side_missed_loss_target` | `29` | `0.3766` | `-84.5832` | `+184.8930` |
| `low_capture_loss_target` | `29` | `0.3766` | `-84.5832` | `+184.8930` |
| `large_exit_regret_loss_target` | `8` | `0.1039` | `-57.6552` | `+157.9650` |
| `same_side_large_regret_loss_target` | `8` | `0.1039` | `-57.6552` | `+157.9650` |
| `hold_too_long_loss_target` | `9` | `0.1169` | `-55.9920` | `+156.3018` |

Reading:

- `direction_or_exit_loss_target` is equal to realized loss on this validation slice, so it is too broad.
- Direction/profit-barrier miss targets have useful support but are not yet calibrated well with the current bucket features.
- Large exit regret and hold-too-long targets are narrower and higher-severity, but support is still small.

## Pointwise Scores

Top pointwise score diagnostics:

| target | score | predicted rows | AUC | target PnL |
|---|---|---:|---:|---:|
| `direction_error_loss_target` | `selected_ev_overestimate_risk` | `20` | `0.7083` | `-104.8800` |
| `profit_barrier_miss_loss_target` | `selected_ev_overestimate_risk` | `20` | `0.7083` | `-104.8800` |
| `direction_and_exit_loss_target` | `selected_ev_overestimate_risk` | `20` | `0.7083` | `-104.8800` |
| `realized_loss_target` | `selected_time_exit_prob` | `77` | `0.6802` | `-130.0872` |
| `same_side_missed_loss_target` | `selected_ev_overestimate_risk` | `20` | `0.6458` | `-84.5832` |
| `large_exit_regret_loss_target` | `selected_loss_first_prob` | `77` | `0.6232` | `-57.6552` |

Reading:

- EV-overestimate risk is still the best pointwise feature for direction/profit-barrier miss loss, but it exists for only 20 selected rows in this validation artifact.
- Time-exit probability has signal for broad realized loss, but broad realized loss is not a precise entry decision target.
- These are feature candidates, not policy evidence.

## Chronological Calibration

Best chronological summary rows:

| spec | target | count | predicted rows | pooled AUC | bucket share | no-prior share |
|---|---|---:|---:|---:|---:|---:|
| `profit_exit` | `hold_too_long_loss_target` | `9` | `20` | `0.6875` | `0.0779` | `0.7403` |
| `profit_exit` | `large_exit_regret_loss_target` | `8` | `20` | `0.6667` | `0.0779` | `0.7403` |
| `profit_exit` | `same_side_large_regret_loss_target` | `8` | `20` | `0.6667` | `0.0779` | `0.7403` |
| `side_context` | `direction_error_loss_target` | `29` | `20` | `0.5208` | `0.0649` | `0.7403` |
| `side_context` | `profit_barrier_miss_loss_target` | `29` | `20` | `0.5208` | `0.0649` | `0.7403` |

Reading:

- `profit_exit` has a small signal for hold-too-long / large-exit-regret, but bucket coverage is too low.
- Direction error target support is better, but chronological `side_context` pooled AUC `0.5208` is too weak.
- The high no-prior share is the main blocker: this validation window is too short to turn these targets into reliable bucket rates.

## Decision

Accepted:

- Direction/exit residual target generation from enriched trades.
- Decision-time-only bucket calibration specs.
- Pointwise score diagnostics for EV-overestimate, time-exit, loss-first, side-confidence, profit-barrier prediction.

Not accepted:

- `direction_or_exit_loss_target` as a training label; it collapses to realized loss here.
- Direct entry blocker / hard selector from these validation calibrations.
- Fine-tuning bucket specs on this 77-row validation artifact.

Standard policy remains NoTrade.

## Next

1. Use this script on wider enriched validation families before building prediction-row policy inputs.
2. Treat `selected_ev_overestimate_risk` as a feature for direction/profit-barrier miss target, not as a hard block.
3. Treat `profit_exit` features as a candidate for hold-too-long / large-exit-regret target, but only after support improves.
4. Avoid broad `realized_loss` / `direction_or_exit` labels for deep learning; they are too close to generic no-trade pressure.
5. If connecting to policy later, use NoTrade-first selector plus role/month support gates before any stateful replay claim.

## Verification

- `python3 -m unittest tests.test_entry_ev_direction_exit_residual_target_diagnostics tests.test_entry_ev_multifamily_policy_trade_enrichment tests.test_docs_reports`: OK
- validation direction/exit residual diagnostic run: OK
