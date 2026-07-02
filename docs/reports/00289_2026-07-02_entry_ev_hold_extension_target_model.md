# Entry EV Hold Extension Target Model

日時: 2026-07-02 12:44 JST
更新日時: 2026-07-02 12:44 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00288の次アクションとして、fixed-horizon / hold-extension choiceをchronological supervised targetとして学習する診断を追加した。
- `scripts/experiments/entry_ev_hold_extension_target_model.py` は00288の `isolated_exit_capture_trades.csv` を読み、actual fixed 60/240/720m deltaを教師にし、対象月より前の月だけでhorizon別deltaを回帰する。
- default `train_universe=isolated` は悪化。`isolated_loss` で学習すると、exit時点で観測可能な `isolated_large_loss` に閾値5で適用したno-replay診断は total `+246.7530`, month min `-6.8324` でbaseline floorを維持した。
- ただしこの設定は最悪月を直さない。2025-09 `-6.8324`, 2025-06 `-6.5136`, hybrid 2025-12 `-4.1460` は残る。
- `isolated_large_loss_capture_failure` は実行時にはfuture labelなので、そこへの適用結果は教師濃度の確認でありpolicy evidenceではない。
- 判断: hold-extension target model infrastructureはaccepted。`isolated_loss` training + `isolated_large_loss` threshold 5 is a promising diagnostic candidate, but not standard policy. 次はprediction-row/exit-time hookへ接続してfull stateful replayし、month floor改善を確認する。

## Artifacts

- Script:
  - `scripts/experiments/entry_ev_hold_extension_target_model.py`
- Test:
  - `tests/test_entry_ev_hold_extension_target_model.py`
- Runs:
  - `data/reports/backtests/20260702_034209_20260702_entry_ev_hold_extension_target_model_s1/`
  - `data/reports/backtests/20260702_034302_20260702_entry_ev_hold_extension_target_model_isoloss_s1/`
  - `data/reports/backtests/20260702_034308_20260702_entry_ev_hold_extension_target_model_isolated_min120_s1/`
  - `data/reports/backtests/20260702_034313_20260702_entry_ev_hold_extension_target_model_all_s1/`

## Method

Input:

```text
data/reports/backtests/20260702_033140_20260702_entry_ev_isolated_exit_capture_diagnostics_s2/isolated_exit_capture_trades.csv
```

Target:

```text
target_delta_60m  = actual selected-side fixed60 PnL  - current signal-close PnL
target_delta_240m = actual selected-side fixed240 PnL - current signal-close PnL
target_delta_720m = actual selected-side fixed720 PnL - current signal-close PnL
target_best_horizon = argmax(0, delta60, delta240, delta720)
```

Chronological training:

```text
for each target month:
  train = rows from months strictly before target month
  target = current month rows
  fit horizon-specific low-capacity HGB regressors
```

Main feature groups:

```text
current exit-state: adjusted_pnl, holding_minutes
entry/score context: pred_taken_ev, confidence gap, predicted holding, selected_loss_first_prob
fixed-horizon predicted proxies: selected_fixed_60m/240m/720m_pred_pnl
post-exit path: prev_result_bucket, post_exit_gap_bucket, prev pnl, gap minutes
regime: direction, family/role, combined_regime, session_regime
```

Important limitation:

- fixed-horizon replacement summaries are no-replay diagnostics.
- They are not full stateful replay and do not simulate replacement entries after the altered exit.
- `isolated_large_loss_capture_failure` is a future-known diagnostic label and cannot be used directly at execution time.

## Model Comparison

| training universe | best readable result | total after | month min after | decision |
|---|---|---:|---:|---|
| isolated | isolated_loss threshold5 | `+177.0178` | `-96.9674` | reject |
| all | capture-failure threshold0 | `+252.7124` | `-112.6914` | reject |
| isolated min120 | isolated_loss threshold2 | `+126.9412` | `-96.9674` | reject |
| isolated_loss | isolated_large_loss threshold5 | `+246.7530` | `-6.8324` | diagnostic candidate |

Reading:

- Training on all isolated rows or all rows overgeneralizes and chooses destructive extensions.
- Training only on isolated losses produces a much cleaner high-threshold signal.
- High threshold is essential; low threshold variants still damage floors.

## Best Diagnostic Candidate

`train_universe=isolated_loss`, apply to `isolated_large_loss`, threshold `5.0`:

| metric | value |
|---|---:|
| baseline total | `+118.6900` |
| flagged trades | `7` |
| flagged PnL | `-34.7952` |
| actual replacement delta | `+128.0630` |
| no-replay total after | `+246.7530` |
| no-replay month min after | `-6.8324` |
| target-positive flagged | `6/7` |

The same result appears for `isolated_large_loss_capture_failure` threshold `5.0`, but that universe is not executable because it uses future capture-failure labels. The executable diagnostic reading is therefore `isolated_large_loss` threshold `5.0`: at an exit signal, current PnL and path context are known.

Flagged rows:

| month | side | current PnL | target best delta | predicted delta | predicted horizon | reading |
|---|---|---:|---:|---:|---:|---|
| 2025-02 | long | `-4.5564` | `+12.0064` | `+8.5013` | `720` | useful |
| 2025-04 | long | `-5.6880` | `+89.5680` | `+8.3198` | `720` | useful |
| 2025-04 | long | `-11.7960` | `+31.5160` | `+5.4746` | `720` | useful but horizon mismatch |
| 2025-04 | long | `-3.4320` | `+20.1020` | `+10.3558` | `720` | useful but horizon mismatch |
| 2025-08 | long | `-2.5152` | `+4.5352` | `+13.7567` | `720` | useful but overestimated |
| 2025-10 | long | `-3.9876` | `+24.8146` | `+12.5325` | `720` | useful |
| 2025-12 | short | `-2.8200` | `0.0000` | `+5.5111` | `60` | false positive |

Monthly no-replay after for the same candidate:

| month | raw PnL | flagged | delta | after |
|---|---:|---:|---:|---:|
| 2025-09 | `-6.8324` | `0` | `0.0000` | `-6.8324` |
| 2025-06 | `-6.5136` | `0` | `0.0000` | `-6.5136` |
| hybrid 2025-12 | `-4.1460` | `0` | `0.0000` | `-4.1460` |
| 2025-12 | `+12.9240` | `1` | `-15.4560` | `-2.5320` |
| 2025-02 | `-6.0104` | `1` | `+12.0064` | `+5.9960` |

Reading:

- The candidate increases total and does not worsen the current worst month.
- It does not fix the current month floor; it leaves the two worst refit months untouched.
- It has a false positive in 2025-12, so full replay and a floor-aware selector are required before any policy claim.

## Prediction Metrics

For `train_universe=isolated_loss`:

| horizon | actual delta mean | pred delta mean | MAE | RMSE | model-used share |
|---:|---:|---:|---:|---:|---:|
| 60 | `+0.1550` | `+0.3812` | `5.8662` | `8.7748` | `0.7030` |
| 240 | `-0.2895` | `-2.3784` | `10.9271` | `16.0287` | `0.7030` |
| 720 | `+0.5383` | `+1.1915` | `18.6609` | `27.5142` | `0.7030` |

Reading:

- 720mの誤差が大きく、horizon選択はまだ荒い。
- 高閾値で候補を絞ると使える可能性があるが、全体に広げると壊れる。
- これは「policy」ではなく、exit-time ML hookの候補。

## Decision

Accepted:

- chronological hold-extension target model diagnostics
- horizon-specific OOF delta prediction
- threshold/month no-replay summaries
- `isolated_loss` training as the next candidate line

Rejected:

- default `isolated` training
- `all` training
- low-threshold extension over broad isolated/isolated_loss universes
- standardizing any hold-extension rule without full stateful replay

Standard policy remains NoTrade.

Raw `loss_exit30_cd15` remains the fixed diagnostic benchmark.

## Next

1. Add an exit-time hold-extension hook to stateful replay:
   - at signal close, if current trade is isolated large loss and predicted delta >= threshold, extend to the selected fixed horizon rather than closing immediately.
2. Replay `train_universe=isolated_loss`, threshold `5.0`, target `isolated_large_loss` as the first pre-registered candidate.
3. Evaluate with 00286 stateful floor selector. Do not rely on no-replay replacement estimates.
4. Investigate why 2025-09 and 2025-06 remain unflagged; likely need separate loss-first / regime-specific extension model.

## Verification

- `uv run python -m py_compile scripts/experiments/entry_ev_hold_extension_target_model.py tests/test_entry_ev_hold_extension_target_model.py`: OK
- `uv run python -m unittest tests.test_entry_ev_hold_extension_target_model`: OK
- hold-extension chronological diagnostics runs: OK
