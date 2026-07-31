# Entry EV Short Entry-Block Replacement Replay

日時: 2026-07-02 16:32 JST
更新日時: 2026-07-02 16:32 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00306の次アクションとして、realized path overlayではなく、未選択entry候補feed上でshort entry-blockをreplacement replayへ戻した。
- `scripts/experiments/entry_ev_entry_block_prediction_flags.py` を追加し、prediction parquetにentry-block用のobservable boolean flagを付与した。
- `entry_ev_quantile_exit_timing_sensitivity.py` に `--side-ev-penalty-rules` と `--side-ev-penalty-replacement-min-margin` を追加し、片側に大きなEV penaltyを入れて反対側replacementを許せるようにした。
- 今回replayしたのはshort側の `rollover_lossprob_ge0p4 OR london_midloss_sidegap_pos`。00293 comboのうち、hold-extension後にしか分からない `holdext_long_range_normal_ny` はまだ含めていない。
- raw `loss_exit30_cd15` 段階の合算では baseline `+118.6900` / 266 trades / month min `-6.8324` から、replacement `+126.8118` / 254 trades / month min `-6.8324` へ `+8.1218` 改善した。
- 改善の中心はhybrid 2025-12で、baseline `-4.1460` が replacement `+4.5000` へ改善。internal+hgb側は total `+112.0660 -> +111.5418` と小幅悪化だが、role minは `+0.0074 -> +0.5354` に改善した。
- 判断: prediction-row flag + side EV penalty replacement replayはaccepted infrastructure。short entry-block replacementはdiagnostic candidate。ただしmonth floor `-6.8324` が残るため標準policyはNoTrade。

## Artifacts

- New script:
  - `scripts/experiments/entry_ev_entry_block_prediction_flags.py`
- Updated script:
  - `scripts/experiments/entry_ev_quantile_exit_timing_sensitivity.py`
- New / updated tests:
  - `tests/test_entry_ev_entry_block_prediction_flags.py`
  - `tests/test_entry_ev_quantile_exit_timing_sensitivity.py`
- Flag runs:
  - `data/reports/backtests/20260702_072914_20260702_entry_ev_entry_block_prediction_flags_internal_hgb_s1/`
  - `data/reports/backtests/20260702_073133_20260702_entry_ev_entry_block_prediction_flags_hybrid_s1/`
- Replay runs:
  - baseline internal+hgb: `data/reports/backtests/20260702_073001_20260702_entry_ev_short_entryblock_replacement_internal_hgb_baseline_s1/`
  - replacement internal+hgb: `data/reports/backtests/20260702_073039_20260702_entry_ev_short_entryblock_replacement_internal_hgb_s1/`
  - delta internal+hgb: `data/reports/backtests/20260702_073124_20260702_entry_ev_short_entryblock_replacement_delta_internal_hgb_s1/`
  - baseline hybrid: `data/reports/backtests/20260702_073146_20260702_entry_ev_short_entryblock_replacement_hybrid_baseline_s1/`
  - replacement hybrid: `data/reports/backtests/20260702_073201_20260702_entry_ev_short_entryblock_replacement_hybrid_s1/`
  - delta hybrid: `data/reports/backtests/20260702_073211_20260702_entry_ev_short_entryblock_replacement_delta_hybrid_s1/`

## Method

Prediction flags:

```text
entryblock_short_rollover_lossprob_ge0p4:
  session_regime == rollover
  pred_short_exit_event_prob_2 >= 0.4

entryblock_short_london_midloss_sidegap_pos:
  session_regime == london
  0.3 <= pred_short_exit_event_prob_2 <= 0.45
  pred_best_side_prob_-1 - pred_best_side_prob_1 > 0

entryblock_short_rollover_or_london_midloss:
  OR of the two rules above
```

Replay hook:

```text
side_ev_penalty_rules:
  short:entryblock_short_rollover_or_london_midloss=true:1000000
```

This is different from `side_block_rules`:

- `side_block_rules` suppresses the selected side and can become NoTrade.
- `side_ev_penalty_rules` penalizes one side before side selection, so the opposite side can be selected if it still passes entry gates.

## Combined Result

Baseline:

| metric | value |
|---|---:|
| total PnL | `+118.6900` |
| trades | `266` |
| month min | `-6.8324` |
| max drawdown | `30.8714` |
| overall side share | `0.5150` |

Replacement:

| metric | value |
|---|---:|
| total PnL | `+126.8118` |
| trades | `254` |
| month min | `-6.8324` |
| max drawdown | `30.8714` |
| overall side share | `0.5787` |

Delta:

| metric | value |
|---|---:|
| total delta | `+8.1218` |
| trade count delta | `-12` |
| month floor delta | `0.0000` |
| side share delta | `+0.0637` |

Reading:

- replacement improves total but does not fix the main remaining month floor.
- side share becomes more long-skewed because short candidates are penalized in the flagged contexts.
- This is useful infrastructure evidence, not standard admission evidence.

## Role Summary

| role | baseline PnL | replacement PnL | delta | baseline trades | replacement trades | reading |
|---|---:|---:|---:|---:|---:|---|
| cal2024_validation | `+8.8424` | `+6.9988` | `-1.8436` | `31` | `31` | worse |
| fresh2024_validation | `+8.3344` | `+8.3344` | `0.0000` | `3` | `3` | unchanged |
| hgb2024_0306_external | `+28.4820` | `+24.1320` | `-4.3500` | `84` | `82` | worse |
| hgb2025_08_external | `+0.0074` | `+0.5354` | `+0.5280` | `12` | `11` | floor improves |
| hybrid2025_0912_external | `+6.6240` | `+15.2700` | `+8.6460` | `6` | `6` | strong improvement |
| refit2025_validation | `+66.3998` | `+71.5412` | `+5.1414` | `130` | `121` | improves |

Reading:

- hybrid and refit improve enough to offset cal/hgb2024 degradation.
- hgb2024 degradation is important: the rule is not universally good across families.
- role min improves from `+0.0074` to `+0.5354`, matching the 00293 direction, but this still has sparse-role and month-floor blockers.

## Worst Months

Baseline worst months:

| family | role | month | PnL | trades |
|---|---|---|---:|---:|
| refit2025 | refit2025_validation | `2025-09` | `-6.8324` | `8` |
| refit2025 | refit2025_validation | `2025-06` | `-6.5136` | `6` |
| refit2025 | refit2025_validation | `2025-02` | `-6.0104` | `11` |
| hybrid2025_0912 | hybrid2025_0912_external | `2025-12` | `-4.1460` | `2` |
| refit2025 | refit2025_validation | `2025-08` | `-3.0500` | `3` |
| refit2025 | refit2025_validation | `2025-03` | `-2.4566` | `11` |

Replacement worst months:

| family | role | month | PnL | trades |
|---|---|---|---:|---:|
| refit2025 | refit2025_validation | `2025-09` | `-6.8324` | `8` |
| refit2025 | refit2025_validation | `2025-02` | `-6.0104` | `11` |
| refit2025 | refit2025_validation | `2025-06` | `-4.6356` | `4` |
| refit2025 | refit2025_validation | `2025-08` | `-1.7852` | `2` |
| hybrid2025_0912 | hybrid2025_0912_external | `2025-11` | `-0.7200` | `1` |
| fresh2024 | fresh2024_validation | `2024-11` | `-0.6120` | `1` |
| refit2025 | refit2025_validation | `2025-03` | `-0.4730` | `9` |

Reading:

- The replacement rule fixes the hybrid 2025-12 tail and improves refit 2025-03/06/08.
- It does not touch refit 2025-09 or 2025-02, so the raw cd15 month floor remains `-6.8324`.
- This supports the earlier conclusion: entry-block replacement is useful but not sufficient; exit/hold-extension path remains necessary.

## Delta Detail

Internal+hgb:

| metric | value |
|---|---:|
| baseline PnL | `+112.0660` |
| replacement PnL | `+111.5418` |
| delta | `-0.5242` |
| base trades | `260` |
| replacement trades | `248` |
| removed positive PnL | `+6.5120` |
| removed negative PnL | `-9.1296` |
| added positive PnL | `+0.4810` |
| added negative PnL | `-3.6228` |

Hybrid:

| metric | value |
|---|---:|
| baseline PnL | `+6.6240` |
| replacement PnL | `+15.2700` |
| delta | `+8.6460` |
| base trades | `6` |
| replacement trades | `6` |
| removed positive PnL | `0.0000` |
| removed negative PnL | `-4.7160` |
| added positive PnL | `+3.9300` |
| added negative PnL | `0.0000` |

Reading:

- hybrid is a clean replacement win: one negative short path is removed and a positive alternative is added.
- internal+hgb is mixed: it removes more negative than positive, but added replacement losses erase most of the benefit.
- Therefore a universal short block is still too blunt. The next selector needs family/regime support or prior-only context pressure, not just the same 00293 short rule.

## Decision

Accepted:

- prediction-row entry-block flag generation
- `side_ev_penalty_rules` passthrough in exit-timing sensitivity replay
- short-side replacement replay as a diagnostic path
- hybrid 2025-12 replacement evidence

Rejected:

- treating the 00293 no-replacement overlay as sufficient policy evidence
- treating the short block as universally good across families
- standardizing the replacement rule while month floor remains `-6.8324`
- claiming this replay covers hold-extension state-dependent blocks

Standard policy remains NoTrade.

## Next

1. Add the hold-extension state-dependent `holdext_long_range_normal_ny` logic to a full replay path, or define an execution-time proxy that can be applied before entry.
2. Combine side-aware fixed 720m hold-extension with this replacement mechanism rather than evaluating raw cd15 only.
3. Split short replacement by family/regime/prior context support; avoid one global short rule.
4. Continue using role/month floor, support, side share, and NoTrade-first admission as gates.

## Verification

- `uv run python -m py_compile scripts/experiments/entry_ev_entry_block_prediction_flags.py scripts/experiments/entry_ev_quantile_exit_timing_sensitivity.py tests/test_entry_ev_entry_block_prediction_flags.py tests/test_entry_ev_quantile_exit_timing_sensitivity.py`: OK
- `uv run python -m unittest tests.test_entry_ev_entry_block_prediction_flags tests.test_entry_ev_quantile_exit_timing_sensitivity`: OK
- entry-block prediction flag runs: OK
- short entry-block replacement replay runs: OK
- policy delta diagnostics runs: OK
