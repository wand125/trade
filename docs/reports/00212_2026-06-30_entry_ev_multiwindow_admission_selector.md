# Entry EV Multiwindow Admission Selector

日時: 2026-06-30 14:09 JST
更新日時: 2026-06-30 14:09 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00211の反省を受け、`entry_ev_admission_selection.py` に `--multi-window` modeを追加した。各 `--family-sweeps` を1つのvalidation windowとして扱い、同じpolicy keyを複数windowで集約してからNoTrade-first selectionする。
- 追加したgateは `min_windows`, `min_positive_windows`, `min_active_windows`, `min_window_total`, `min_window_trades`, `min_monthly_trades`, `max_monthly_trades`, `max_side_trade_share`, regime/session worst bucket floors。
- 実データでは fresh2024 validation (`2024-03..04`) と refit2025 validation (`2025-01..02`) を同時に評価した。
- Promotion gate `min_window_trades=10`, `min_worst_pnl=0`, `min_positive_windows=2` では標準selectorはNoTradeを返す。best validation totalは `+190.4544` だが、fresh2024側windowのtradesが `4` しかない。
- Relaxed gate `min_window_trades=1` では `entry10/short9/min_rank0.0` が選ばれる。multi-window validation total `+190.4544`, worst `+0.7230`, worst window `+17.0910`, trades `173`。
- しかし relaxed-selected rowを両fixed test windowへ適用すると total `-943.9322`, worst `-294.1980`, trades `1144`。NoTrade `0` に大きく負ける。
- `max_side_trade_share <= 0.95` を足すとNoTradeに戻る。relaxed-selected rowは validation side share `0.9595`, worst window side share `0.9763` で、ほぼlong偏重だった。
- 判断: multi-window selectorはaccepted infrastructure。現時点の標準policyはNoTrade。`side balance` と `window trade support` は有効なpromoter rejection gate候補だが、閾値自体はまだ標準化しない。

## Artifacts

- Script: `scripts/experiments/entry_ev_admission_selection.py`
- Tests: `tests/test_entry_ev_admission_selection.py`
- Strict support selector:
  - `data/reports/backtests/20260630_entry_evcal_rank_multiwindow_selector_support10_worst0/20260630_050919_entry_ev_rank_multiwindow_support10_worst0/`
- Relaxed selector:
  - `data/reports/backtests/20260630_entry_evcal_rank_multiwindow_selector_relaxed/20260630_050919_entry_ev_rank_multiwindow_relaxed/`
- Side balance selector:
  - `data/reports/backtests/20260630_entry_evcal_rank_multiwindow_selector_side095/20260630_050919_entry_ev_rank_multiwindow_side095/`
- Fixed test audit:
  - `data/reports/backtests/20260630_entry_evcal_rank_multiwindow_fixed_test_audit/combined_fixed_test_summary_all_available.csv`
  - `data/reports/backtests/20260630_entry_evcal_rank_multiwindow_fixed_test_audit/combined_fixed_test_summary_both_windows.csv`
  - `data/reports/backtests/20260630_entry_evcal_rank_multiwindow_fixed_test_audit/selected_config_monthly_details.csv`

Each multi-window run writes both:

```text
validation_summary.csv
window_validation_summary.csv
```

The first is policy-key level across windows. The second preserves one row per validation window, so later review can see whether a candidate was supported by both windows or just one.

## Selector Changes

The standard selector still remains NoTrade-first. In `--multi-window` mode it now checks:

```text
validation_total > min_positive_pnl
validation_trades >= min_trades
validation_active_months >= min_active_months
validation_worst >= min_worst_pnl
validation_windows >= min_windows
validation_positive_windows >= min_positive_windows
validation_active_windows >= min_active_windows
validation_worst_window >= min_window_total
validation_min_window_trades >= min_window_trades
validation_min_monthly_trades >= min_monthly_trades
validation_max_monthly_trades <= max_monthly_trades
validation_max_side_trade_share <= max_side_trade_share
validation_direction_session_pnl_min >= min_direction_session_pnl
validation_combined_regime_pnl_min >= min_combined_regime_pnl
validation_direction_combined_regime_pnl_min >= min_direction_combined_regime_pnl
```

This converts 00211's conclusion into code: support is not just total trades. It must be distributed across validation windows and not depend on one side/regime bucket.

## Multi-Window Validation

Validation windows:

| window | months | source |
|---|---|---|
| `fresh2024` | `2024-03, 2024-04` | 00210 rank validation |
| `refit2025` | `2025-01, 2025-02` | 00211 refit validation |

Selector outcomes:

| selector gate | selected | key evidence |
|---|---|---|
| strict support `min_window_trades=10`, `min_worst_pnl=0`, `positive_windows=2` | NoTrade | best row total `+190.4544`, but min window trades `4` |
| relaxed `min_window_trades=1`, `min_worst_pnl=0`, `positive_windows=2` | `entry10/short9/min_rank0.0` | total `+190.4544`, worst `+0.7230`, worst window `+17.0910`, trades `173` |
| relaxed + `max_side_trade_share<=0.95` | NoTrade | relaxed-selected row side share `0.9595` |

Top multi-window validation rows:

| entry | short offset | min rank | total | worst window | worst month | trades | min window trades | side share | direction/session min | combined min |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `10` | `9` | `0.0` | `+190.4544` | `+17.0910` | `+0.7230` | `173` | `4` | `0.9595` | `-27.7386` | `-53.8964` |
| `14` | `6` | `0.0` | `+180.7204` | `+7.7270` | `0.0000` | `170` | `1` | `0.9706` | `-27.7386` | `-54.2664` |
| `12` | `6` | `0.5` | `+170.7764` | `+8.6630` | `-16.3290` | `171` | `7` | `0.9415` | `-33.5236` | `-37.5764` |

The relaxed row looks strong by total, but it is mostly one-sided and has weak fresh2024 support. This is exactly the class of candidate that 00211 showed can collapse.

## Fixed Test Audit

Fixed test windows:

| window | months |
|---|---|
| `test2024_05_12` | `2024-05..2024-12` |
| `test2025_03_12` | `2025-03..2025-12` |

Relaxed-selected row:

| entry | short offset | min rank | total | worst | active months | trades | max DD | long PnL | short PnL |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `10` | `9` | `0.0` | `-943.9322` | `-294.1980` | `15` | `1144` | `330.9088` | `-424.4576` | `-519.4746` |

Monthly detail for the relaxed-selected row:

| month | PnL | trades | long PnL | short PnL |
|---|---:|---:|---:|---:|
| 2024-05 | `-0.0120` | `1` | `0.0000` | `-0.0120` |
| 2024-06 | `+32.5900` | `1` | `0.0000` | `+32.5900` |
| 2024-07 | `0.0000` | `0` | `0.0000` | `0.0000` |
| 2024-08 | `+48.2500` | `3` | `0.0000` | `+48.2500` |
| 2024-09 | `0.0000` | `0` | `0.0000` | `0.0000` |
| 2024-10 | `0.0000` | `0` | `0.0000` | `0.0000` |
| 2024-11 | `+9.3462` | `4` | `0.0000` | `+9.3462` |
| 2024-12 | `-2.2800` | `1` | `0.0000` | `-2.2800` |
| 2025-03 | `+115.2168` | `83` | `+133.0168` | `-17.8000` |
| 2025-04 | `-252.4842` | `142` | `-128.5420` | `-123.9422` |
| 2025-05 | `-195.9904` | `127` | `-133.5518` | `-62.4386` |
| 2025-06 | `-294.1980` | `104` | `-179.9420` | `-114.2560` |
| 2025-07 | `-138.1228` | `100` | `-127.2828` | `-10.8400` |
| 2025-08 | `+2.4958` | `83` | `-17.0022` | `+19.4980` |
| 2025-09 | `+66.9778` | `100` | `+132.6052` | `-65.6274` |
| 2025-10 | `-281.2020` | `130` | `-128.8592` | `-152.3428` |
| 2025-11 | `-193.5708` | `135` | `-82.3438` | `-111.2270` |
| 2025-12 | `+139.0514` | `130` | `+107.4442` | `+31.6072` |

Comparable fixed-test top among configs present in both test windows:

| entry | short offset | min rank | total | worst | trades | max DD | long PnL | short PnL |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `14` | `9` | `0.6` | `+98.9868` | `-133.6912` | `113` | `138.0052` | `+33.3250` | `+65.6618` |
| `14` | `6` | `0.6` | `-36.0064` | `-180.4392` | `127` | `182.7532` | `+33.3250` | `-69.3314` |
| `12` | `9` | `0.6` | `-39.8304` | `-180.4392` | `125` | `182.7532` | `+33.3250` | `-73.1554` |

Even the comparable hindsight top has a worst month of `-133.6912`. It is not a robust standard candidate.

## Decision

Accepted:

- `--multi-window` selector mode.
- Window-level summary artifact.
- `min_window_trades`, `min_positive_windows`, and `max_side_trade_share` as admission rejection gates.
- Fixed-test audit must distinguish configs available in both test windows from configs available only in one window.

Rejected for standard adoption:

- Relaxed multi-window selection `entry10/short9/min_rank0.0`, because fixed tests total `-943.9322`.
- Test-only or partially available rank candidates as adoption evidence.
- Treating validation total alone as sufficient once multiple windows are introduced.

Current standard remains NoTrade.

## Next

1. Promote `multi-window` selector to the default admission review path for entry EV/rank experiments.
2. Add a formal side-balance policy candidate, but only after testing several thresholds (`0.90`, `0.95`, `0.98`) across more windows. Do not freeze `0.95` from this single audit.
3. Generate additional validation windows so that a candidate must pass more than two regimes before fixed test.
4. Add side/regime-specific rank calibration before increasing model complexity.
5. Keep sparse high-rank short-only rows as diagnostics; do not use them for standard selection unless they have validation trades in multiple windows.

## Verification

- `python3 -m py_compile scripts/experiments/entry_ev_admission_selection.py tests/test_entry_ev_admission_selection.py`: OK
- `python3 -m unittest tests.test_entry_ev_admission_selection`: OK
- multi-window selector strict run: OK
- multi-window selector relaxed run: OK
- multi-window selector side-balance run: OK
- fixed test audit CSV generation: OK
