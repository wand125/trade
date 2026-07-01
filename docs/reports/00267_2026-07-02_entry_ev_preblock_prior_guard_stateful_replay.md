# Entry EV Pre-Block Prior Guard Stateful Replay

日時: 2026-07-02 03:38 JST
更新日時: 2026-07-02 03:38 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00266のno-replacement estimateを、実際のstateful replayへ接続した。
- `scripts/experiments/entry_ev_prior_context_guard_prediction_inputs.py` を追加し、pre-block prediction parquetへ候補別prior `direction_regime` guard列を生成した。
- `scripts/experiments/entry_ev_quantile_policy_backtest.py` に `--side-block-rules` を追加し、既存 `ModelPolicyConfig.side_block_rules` へ渡せるようにした。
- q99/floor5 prior guardは pre-block単体 q99/floor5を `-23.5882 -> +55.6750` へ改善した。
- refit2025は `-50.0440 -> +29.2192`。worst monthは `-128.3504 -> -26.4120` まで縮んだ。
- q95/floor5も `-14.6536 -> +52.8696` へ改善したが、refit worst `-55.4316`, max DD `110.4772` でq99より弱い。
- strict/relaxed admissionはNoTrade。support-relaxed diagnostic gateでは q99/floor5 が選択された。
- 判断: stateful replay evidenceはaccepted。q99 prior guardはdiagnostic candidateへ昇格。ただし標準policyはNoTrade。

## Artifacts

- Added script:
  - `scripts/experiments/entry_ev_prior_context_guard_prediction_inputs.py`
- Updated script:
  - `scripts/experiments/entry_ev_quantile_policy_backtest.py`
  - `scripts/experiments/entry_ev_quantile_policy_selection.py`
- Added tests:
  - `tests/test_entry_ev_prior_context_guard_prediction_inputs.py`
- Updated tests:
  - `tests/test_entry_ev_quantile_policy_backtest.py`
  - `tests/test_entry_ev_quantile_policy_selection.py`
- Guarded prediction inputs:
  - `data/reports/backtests/20260701_183345_20260702_entry_ev_preblock_prior_context_guard_inputs_s1/`
- q99 stateful replay:
  - `data/reports/backtests/20260701_183428_20260702_entry_ev_preblock_prior_guard_q99_loss20_broad_s1/`
- q95 stress replay:
  - `data/reports/backtests/20260701_183529_20260702_entry_ev_preblock_prior_guard_q95_loss60_broad_s1/`
- Combined monthly metrics:
  - `data/reports/backtests/20260701_183600_20260702_entry_ev_preblock_prior_guard_q99_q95_combined_s1/`
- Admission:
  - `data/reports/backtests/20260701_183711_20260702_entry_ev_preblock_prior_guard_admission_strict3_s1/`
  - `data/reports/backtests/20260701_183711_20260702_entry_ev_preblock_prior_guard_admission_relaxed3_s1/`
  - `data/reports/backtests/20260701_183806_20260702_entry_ev_preblock_prior_guard_admission_support_relaxed3_s1/`
- q99 no-guard vs guard delta:
  - `data/reports/backtests/20260701_183817_20260702_entry_ev_preblock_prior_guard_q99_vs_noguard_delta_s1/`

## Implementation

New prediction-input flow:

```text
pre-block prediction rows
+ post-block prediction rows
+ prior only-candidate delta rows
-> pred_prior_direction_regime_guard_<candidate>_loss<threshold>_block
```

The guard column is `1` only when all are true:

1. the row passes the pre-block candidate condition,
2. the same row does not pass the post-block candidate condition,
3. selected side is short,
4. `direction_regime = short/<combined_regime>` has prior-month only-candidate PnL below the threshold.

The replay then uses:

```text
--side-block-rules short:pred_prior_direction_regime_guard_q99_sg95_rank90_floor5_side_regime_session_month_loss20_block=1
```

This is not a static context blacklist. It is candidate-specific and only targets pre-block-added rows with prior downside.

## Guard Input Support

Input generation summary:

| family | candidate | pre pass rows | post pass rows | newly admitted | newly admitted short | blocked rows |
|---|---|---:|---:|---:|---:|---:|
| cal2024 | q99/floor5 | `29` | `29` | `0` | `0` | `0` |
| fresh2024 | q99/floor5 | `26` | `0` | `26` | `26` | `0` |
| refit2025 | q99/floor5 | `225` | `101` | `127` | `56` | `12` |
| cal2024 | q95/floor5 | `122` | `122` | `0` | `0` | `0` |
| fresh2024 | q95/floor5 | `34` | `0` | `34` | `34` | `0` |
| refit2025 | q95/floor5 | `535` | `280` | `279` | `112` | `23` |

For this refit delta, loss thresholds `20/40/60` produce the same blocked row count. The replay uses q99 loss20 and q95 loss60 as representative settings.

## Stateful Replay

q99/floor5:

| family | total pnl | worst month | trades | max DD | max side share |
|---|---:|---:|---:|---:|---:|
| cal2024 | `+2.4158` | `-1.8000` | `10` | `14.0472` | `0.6000` |
| fresh2024 | `+24.0400` | `0.0000` | `1` | `0.0000` | `1.0000` |
| refit2025 | `+29.2192` | `-26.4120` | `56` | `83.1360` | `0.5714` |
| overall | `+55.6750` | `-26.4120` | `67` | `83.1360` | `0.5672` |

q95/floor5 stress:

| family | total pnl | worst month | trades | max DD | max side share |
|---|---:|---:|---:|---:|---:|
| cal2024 | `-1.6986` | `-1.8000` | `21` | `26.9590` | `0.6190` |
| fresh2024 | `+32.7380` | `-0.6120` | `3` | `0.6120` | `1.0000` |
| refit2025 | `+21.8302` | `-55.4316` | `90` | `110.4772` | `0.6111` |
| overall | `+52.8696` | `-55.4316` | `114` | `110.4772` | `0.5965` |

Reading:

- q99 is better on total, worst month, drawdown, and side share.
- q95 increases trade support but keeps a larger tail.

## Admission

Strict gate:

| candidate | eligible | blockers |
|---|---|---|
| q99/floor5 | false | `month_pnl_below_floor;role_trades_low;month_trades_low` |
| q95/floor5 | false | `positive_roles_low;role_total_pnl_below_floor;month_pnl_below_floor;role_trades_low;month_trades_low` |

Relaxed diagnostic gate:

| candidate | eligible | blockers |
|---|---|---|
| q99/floor5 | false | `role_trades_low` |
| q95/floor5 | false | `role_trades_low` |

Support-relaxed diagnostic gate:

| candidate | eligible | validation total | min role total | min month | trades | selected |
|---|---|---:|---:|---:|---:|---|
| q99/floor5 | true | `+55.6750` | `+2.4158` | `-26.4120` | `67` | yes |
| q95/floor5 | true | `+52.8696` | `-1.6986` | `-55.4316` | `114` | no |

Standard gate remains NoTrade because role trade support is still too thin, especially fresh2024.

## Delta

q99 pre-block no-guard versus q99 prior guard:

| metric | no guard | prior guard | delta |
|---|---:|---:|---:|
| trades | `70` | `67` | `-3` |
| adjusted pnl | `-23.5882` | `+55.6750` | `+79.2632` |
| removed positive pnl | | `+56.2100` | |
| removed negative pnl | | `-145.8000` | |
| added positive pnl | | `+22.6300` | |
| added negative pnl | | `-32.9568` | |

Month delta:

| month | no guard | prior guard | delta |
|---|---:|---:|---:|
| 2025-05 | `-128.3504` | `-15.5072` | `+112.8432` |
| 2025-11 | `+74.4778` | `+40.8978` | `-33.5800` |
| other months | unchanged | unchanged | `0.0000` |

Removed base rows:

| month | direction | base pnl |
|---|---|---:|
| 2025-05 | short | `-60.0480` |
| 2025-05 | short | `-77.0520` |
| 2025-05 | short | `-8.7000` |
| 2025-11 | short | `+1.0100` |
| 2025-11 | short | `+55.2000` |

Added replacement rows:

| month | direction | candidate pnl |
|---|---|---:|
| 2025-05 | short | `-32.9568` |
| 2025-11 | short | `+22.6300` |

Interpretation:

- The guard did exactly what the no-replacement diagnostic predicted for 2025-05: it removes the large `short/down_normal_vol` losses.
- It also confirms the known cost: later 2025-11 profitable `short/down_normal_vol` rows are removed.
- Replacement path is tolerable in this run but still adds one negative 2025-05 trade.

## Decision

Accepted:

- prior-guard prediction input infrastructure
- `--side-block-rules` passthrough for quantile policy replay
- q99 prior guard as a diagnostic stateful replay candidate
- selector bugfix for empty blocker summary

Not accepted:

- standard policy promotion
- q95 as primary candidate
- treating support-relaxed selection as standard admission
- tuning thresholds further on the same refit window

Standard policy remains NoTrade.

## Next

1. Freeze q99/floor5 + prior direction_regime guard as a pre-registered diagnostic candidate.
2. Test it on an external chronology or regenerated family, without changing threshold/guard scope.
3. Investigate fresh2024 support. The policy is profitable but only 1 trade, so standard gate cannot pass.
4. Consider whether support should be improved by more data/windows rather than by loosening admission.

## Verification

- `python3 -m unittest tests.test_entry_ev_prior_context_guard_prediction_inputs tests.test_entry_ev_quantile_policy_backtest`: OK
- `python3 -m unittest tests.test_entry_ev_quantile_policy_selection`: OK
- prediction guard input generation: OK
- q99/q95 stateful replay: OK
- strict/relaxed/support-relaxed admission selector runs: OK
- q99 no-guard vs guard delta: OK
