# Entry EV Executable EV Calibration

日時: 2026-06-30 17:51 JST
更新日時: 2026-06-30 17:54 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00228のexit-capture targetを使い、oracle EVを「現exit policyで実現できるcapture factor」で割り引く `scripts/experiments/entry_ev_executable_ev_calibration_diagnostics.py` を追加した。
- 対象月より前のselected tradeだけで、global + context-local capture factorを推定し、`pred_capture_calibrated_ev = pred_taken_ev * executable_capture_factor` を作る。
- 結論: executable EV calibrationは、raw EVの過大評価とMAEを大きく改善する。validation q95/q99でも fresh q95/720でも改善は一貫している。
- ただし、低calibrated EVをhard thresholdで落とすとwindow間で符号が反転する。`EV<3` はvalidation横断では `+87.4464` 改善だが、fresh q95/720では `-31.9218` 悪化。`EV<2` はfresh q95/720では `+49.6632` 改善だが、validation横断では `-5.3592` 悪化。
- 標準policyはNoTradeのまま。executable EVはhard thresholdではなく、continuous EV補正、selector feature、rank featureとして次に使う。

## Artifacts

- Script: `scripts/experiments/entry_ev_executable_ev_calibration_diagnostics.py`
- Test: `tests/test_entry_ev_executable_ev_calibration_diagnostics.py`
- Validation q95/q99, capture factor `[-1, 1]`:
  - `data/reports/backtests/20260630_entry_ev_executable_ev_calibration_diagnostics/20260630_085003_entry_ev_executable_ev_validation_q95q99/`
- Fresh q95_floor5 / 720m, capture factor `[-1, 1]`:
  - `data/reports/backtests/20260630_entry_ev_executable_ev_calibration_diagnostics/20260630_085016_entry_ev_executable_ev_fresh_q95_720/`
- Validation q95/q99, non-negative capture factor `[0, 1]`:
  - `data/reports/backtests/20260630_entry_ev_executable_ev_calibration_diagnostics/20260630_085034_entry_ev_executable_ev_validation_q95q99_nonnegative/`
- Fresh q95_floor5 / 720m, non-negative capture factor `[0, 1]`:
  - `data/reports/backtests/20260630_entry_ev_executable_ev_calibration_diagnostics/20260630_085034_entry_ev_executable_ev_fresh_q95_720_nonnegative/`
- Low threshold sensitivity:
  - `data/reports/backtests/20260630_entry_ev_executable_ev_calibration_diagnostics/20260630_085054_entry_ev_executable_ev_validation_q95q99_nonnegative_lowthr/`
  - `data/reports/backtests/20260630_entry_ev_executable_ev_calibration_diagnostics/20260630_085054_entry_ev_executable_ev_fresh_q95_720_nonnegative_lowthr/`

## Calibration Method

For each target month:

```text
capture_ratio = adjusted_pnl / actual_taken_best_adjusted_pnl
capture_ratio is computed only when actual_taken_best_adjusted_pnl > 0
capture_ratio is clipped to [0, 1] for the main executable discount run

global_capture_factor  = mean prior clipped capture ratio before target month
context_capture_factor = mean prior clipped capture ratio for same
                         direction + combined_regime + session_regime
support_weight         = clip(context_capture_count / 4, 0, 1)

executable_capture_factor =
  (1 - support_weight) * global_capture_factor
  + support_weight * context_capture_factor

pred_capture_calibrated_ev =
  pred_taken_ev * executable_capture_factor
```

This is prior-only by month. It does not use same-month or future realized PnL.

## Validation q95/q99

Non-negative capture factor `[0, 1]`:

| role / candidate | trades | PnL | raw MAE | calibrated MAE | MAE delta | raw bias | calibrated bias | factor mean |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| refit q99 floor10 | `18` | `-27.9456` | `22.0208` | `7.6244` | `+14.3964` | `22.0208` | `5.2193` | `0.1908` |
| refit q95 floor10 | `28` | `-23.6438` | `21.3481` | `7.6192` | `+13.7289` | `21.3481` | `4.6512` | `0.1950` |
| refit q95 floor5 | `29` | `-23.2338` | `20.8969` | `7.3980` | `+13.4988` | `20.8969` | `4.5324` | `0.1947` |
| fresh q95 floor5 | `38` | `+1.9920` | `13.9256` | `6.1870` | `+7.7386` | `13.2975` | `2.7429` | `0.2092` |
| fresh q99 floor5 | `12` | `+34.2940` | `12.2327` | `8.1127` | `+4.1199` | `10.2263` | `0.2163` | `0.2361` |
| cal q95 floor5 | `30` | `+15.5444` | `11.2274` | `9.0492` | `+2.1782` | `11.0045` | `8.2793` | `0.7608` |

Interpretation:

- raw EV is heavily optimistic.
- capture calibration reduces MAE for every role/candidate.
- refit failure roles see the largest improvement, but cal/fresh positive roles also improve.

## Fresh q95_floor5 / 720m

Non-negative capture factor `[0, 1]`:

| role | trades | PnL | raw MAE | calibrated MAE | MAE delta | raw bias | calibrated bias | factor mean |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| fresh validation | `36` | `+76.2204` | `14.7507` | `8.4237` | `+6.3270` | `11.2584` | `0.6557` | `0.2078` |
| fresh fixed | `127` | `+325.8914` | `13.4582` | `7.0417` | `+6.4166` | `10.6089` | `-0.1788` | `0.1795` |

Monthly fresh q95/720:

| month | role | PnL | raw MAE | calibrated MAE | MAE delta | factor mean |
|---|---|---:|---:|---:|---:|---:|
| `2024-03` | validation | `-9.1718` | `13.1181` | `5.4733` | `+7.6448` | `0.2261` |
| `2024-04` | validation | `+85.3922` | `16.3833` | `11.3741` | `+5.0092` | `0.1895` |
| `2024-08` | fixed | `+4.2806` | `15.8840` | `7.8131` | `+8.0709` | `0.2031` |
| `2024-11` | fixed | `+192.8188` | `14.9025` | `11.8699` | `+3.0327` | `0.1985` |

The calibration is useful even in profitable months. It is not merely a failure detector.

## Threshold Sensitivity

Overall pointwise removal, non-negative capture factor:

Validation q95/q99:

| score | threshold | flagged trades | flagged PnL | removal delta | precision | recall |
|---|---:|---:|---:|---:|---:|---:|
| raw EV | `<10` | `2` | `-5.1340` | `+5.1340` | `0.5000` | `0.0044` |
| calibrated EV | `<2` | `27` | `+5.3592` | `-5.3592` | `0.8148` | `0.0969` |
| calibrated EV | `<3` | `133` | `-87.4464` | `+87.4464` | `0.8571` | `0.5022` |
| calibrated EV | `<5` | `191` | `-34.7332` | `+34.7332` | `0.8272` | `0.6960` |

Fresh q95/720:

| score | threshold | flagged trades | flagged PnL | removal delta | precision | recall |
|---|---:|---:|---:|---:|---:|---:|
| raw EV | `<10` | `4` | `-3.8292` | `+3.8292` | `1.0000` | `0.0315` |
| calibrated EV | `<1` | `21` | `+11.3944` | `-11.3944` | `0.9048` | `0.1496` |
| calibrated EV | `<2` | `59` | `-49.6632` | `+49.6632` | `0.8983` | `0.4173` |
| calibrated EV | `<3` | `125` | `+31.9218` | `-31.9218` | `0.8400` | `0.8268` |
| calibrated EV | `<5` | `156` | `+303.0404` | `-303.0404` | `0.7821` | `0.9606` |

This is not stable enough for a hard threshold. Threshold `2` helps fresh q95/720 but hurts validation. Threshold `3` helps validation but hurts fresh q95/720.

## Decision

Accepted:

- Executable EV calibration diagnostic.
- Prior-only capture factor as a continuous EV correction.
- Non-negative capture factor `[0, 1]` as the safer default for executable EV discounting.

Not accepted:

- Hard thresholding on calibrated EV.
- Negative capture factor as direct execution score. It improves MAE but can turn many selected trades negative and makes threshold behavior too destructive.
- Treating lower calibrated EV as an automatic no-trade decision.

Standard policy remains NoTrade.

## Next

1. Feed `pred_capture_calibrated_ev` into a selector/ranking diagnostic alongside existing quantile gates, without using a hard threshold alone.
2. Compare raw selected EV vs executable EV as candidate ranking features at role/month level.
3. Use capture-calibrated EV to discount expected PnL in model selection, then require NoTrade-first monthly gates.
4. Keep exit-capture target and executable EV calibration separated from direction-side inversion target.

## Verification

- `python3 -m unittest tests.test_entry_ev_executable_ev_calibration_diagnostics tests.test_entry_ev_exit_capture_target_diagnostics tests.test_entry_ev_residual_month_loss_diagnostics tests.test_docs_reports`: OK, `11` tests
- `python3 -m py_compile scripts/experiments/entry_ev_executable_ev_calibration_diagnostics.py tests/test_entry_ev_executable_ev_calibration_diagnostics.py`: OK
- validation q95/q99 executable EV diagnostics: OK
- fresh q95_floor5 / 720m executable EV diagnostics: OK
- non-negative and low-threshold sensitivity runs: OK
- `git diff --check`: OK
