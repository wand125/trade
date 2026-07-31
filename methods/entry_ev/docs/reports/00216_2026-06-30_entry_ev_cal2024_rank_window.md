# Entry EV Cal2024 Rank Window

日時: 2026-06-30 14:50 JST
更新日時: 2026-06-30 14:50 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00215の次アクションとして、既存non-rankだった `2024-01..02` をfull rank gridで再生成した。
- これは `2023-01..12` fit / `2024-01..02` validation artifactなので、clean outer holdoutではなく `calibration-validation` として扱う。
- `2024-01` と `2024-02` は各 `72` rowsで、`entry=[8,10,12,14]`, `short_offset=[3,6,9]`, `min_entry_rank=[0.0,0.5,0.6,0.7,0.8,0.9]` を満たす。
- cal2024 rank window全体は `144` rows, trade count `8`, total `-70.3272`。active rowsはすべてshortで損失。
- cal2024を fresh2024 / refit2025 と合わせた3-window selectorへ追加した。
- strict gate (`positive_windows=3`, `min_window_trades=10`) はNoTrade。
- relaxed gate (`positive_windows=2`, `active_windows=2`, cal2024は0-trade非負確認扱い) は以前と同じ `entry10/short9/min_rank0.0` を選ぶ。
- side-balance gate `max_side_trade_share=0.95` を加えるとNoTradeに戻る。
- 判断: cal2024 full rank化はaccepted artifactだが、採用候補を増やしていない。標準policyはNoTradeのまま。

## Artifacts

- Updated inventory script: `scripts/experiments/entry_ev_validation_inventory.py`
- Updated tests: `tests/test_entry_ev_validation_inventory.py`
- Cal2024 rank sweeps:
  - `data/reports/backtests/20260630_entry_evcal_rank_calibration_2024_01_02_calibrated/20260630_054721_model_sweep_2024-01/metrics.csv`
  - `data/reports/backtests/20260630_entry_evcal_rank_calibration_2024_01_02_calibrated/20260630_054742_model_sweep_2024-02/metrics.csv`
- 3-window selector outputs:
  - strict: `data/reports/backtests/20260630_entry_evcal_rank_multiwindow_with_cal2024_selector_support10_worst0/20260630_054825_entry_ev_rank_multiwindow_cal2024_support10_worst0/`
  - relaxed: `data/reports/backtests/20260630_entry_evcal_rank_multiwindow_with_cal2024_selector_relaxed/20260630_054848_entry_ev_rank_multiwindow_cal2024_relaxed/`
  - side095: `data/reports/backtests/20260630_entry_evcal_rank_multiwindow_with_cal2024_selector_side095/20260630_054910_entry_ev_rank_multiwindow_cal2024_side095/`
- Inventory v3:
  - `data/reports/backtests/20260630_entry_ev_validation_inventory_v3/20260630_055028_entry_ev_validation_inventory_with_cal2024/`

## Cal2024 Rank Sweep

Input prediction:

```text
data/reports/modeling/20260630_chrono_hgb_mlp_exit_2024_01_02/predictions_hgb_entry_mlp_exit_2024_01_02.parquet
```

Sweep grid:

```text
policy: timed_ev
entry_thresholds: 8,10,12,14
short_entry_threshold_offsets: 3,6,9
side_margin: 5
max_predicted_hold_minutes: 260
min_valid_predicted_hold_minutes: 30
min_entry_ranks: 0,0.5,0.6,0.7,0.8,0.9
long/short EV columns: pred_calibrated_*_best_adjusted_pnl
holding columns: pred_mlp_*_exit_event_minutes
```

Monthly aggregate:

| month | rows | trades | total | worst row |
|---|---:|---:|---:|---:|
| `2024-01` | `72` | `6` | `-64.3752` | `-10.7292` |
| `2024-02` | `72` | `2` | `-5.9520` | `-2.9760` |

All active rows were short-side losses. The apparent non-negative rows are mostly no-trade rows, not positive evidence.

## 3-Window Selector

Validation windows:

| family | months | role |
|---|---|---|
| `cal2024` | `2024-01,2024-02` | calibration-validation, not clean holdout |
| `fresh2024` | `2024-03,2024-04` | full-rank validation |
| `refit2025` | `2025-01,2025-02` | full-rank validation |

Selector outcomes:

| gate | selected | key evidence |
|---|---|---|
| strict support10/worst0 | NoTrade | best validation total `+190.4544`, but cal2024 has 0 trade for that row and `min_window_trades=10` / `positive_windows=3` fail |
| relaxed cal-nonnegative | `entry10/short9/min_rank0.0` | validation total `+190.4544`, trades `173`, windows `3`, positive windows `2`, active windows `2`, worst window `0.0000`, min window trades `0`, side share `0.9595` |
| relaxed + side095 | NoTrade | selected relaxed row breaches `max_side_trade_share=0.95`; no alternative passes all gates |

Relaxed selected row by window:

| family | total | trades | active months | side share | long PnL | short PnL |
|---|---:|---:|---:|---:|---:|---:|
| `cal2024` | `0.0000` | `0` | `0` | `0.0000` | `0.0000` | `0.0000` |
| `fresh2024` | `+17.0910` | `4` | `2` | `0.7500` | `+0.7230` | `+16.3680` |
| `refit2025` | `+173.3634` | `169` | `2` | `0.9763` | `+165.5018` | `+7.8616` |

This is the same relaxed row found in 00212/00213. Adding cal2024 does not add support; it only shows that the row did not trade in early 2024.

## Inventory Update

`entry_ev_validation_inventory.py` now recognizes rank calibration families:

| family | role | status |
|---|---|---|
| `20260630_entry_evcal_rank_calibration_2024_01_02_calibrated` | `calibration_validation_rank` | `calibration_full_rank_not_clean_holdout` |

The usable clean full-rank validation windows remain only:

```text
2024-03..04 fresh2024
2025-01..02 refit2025
```

## Decision

Accepted:

- Full rank sweep for `2024-01..02` as a calibration-validation artifact.
- Inventory classification for `calibration_validation_rank`.
- 3-window selector diagnostics using cal2024 + fresh2024 + refit2025.

Rejected for standard adoption:

- Treating cal2024 as a third clean validation window.
- Treating a cal2024 no-trade result as positive evidence.
- Relaxed `entry10/short9/min_rank0.0`, because it remains side-skewed and already failed fixed tests in 00212/00213.

Current standard remains NoTrade.

## Next

1. To truly increase validation evidence, create a new chronological fold with a new untouched outer test, rather than adding no-trade calibration months.
2. Investigate why `2024-01..02` calibrated high-threshold rows vanish: EV scale, rank distribution, or MLP holding validity may be too conservative.
3. Continue side/regime-aware rank or EV quantile calibration, but require support from active validation windows, not no-trade ties.

## Verification

- `python3 -m unittest tests.test_entry_ev_validation_inventory`: OK, `6` tests
- `python3 -m unittest tests.test_entry_ev_validation_inventory tests.test_entry_ev_admission_selection tests.test_docs_reports`: OK, `15` tests
- `python3 -m py_compile scripts/experiments/entry_ev_validation_inventory.py scripts/experiments/entry_ev_admission_selection.py tests/test_entry_ev_validation_inventory.py tests/test_entry_ev_admission_selection.py`: OK
- `git diff --check`: OK
- Internal `日時:` report order audit: OK, `216` reports, latest `00216_2026-06-30_entry_ev_cal2024_rank_window.md`
- Cal2024 rank sweeps: OK, `144` rows, `8` trades, total `-70.3272`
- 3-window selector runs: OK
- Inventory v3 run: OK, cal2024 classified as `calibration_full_rank_not_clean_holdout`
