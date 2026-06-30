# Entry EV Rank Gate Support Audit

日時: 2026-06-30 13:34 JST
更新日時: 2026-06-30 13:34 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00209のfixed testを監査し、`cal12/short6` の `+65.4014` は保存済みfixed config上の `min_entry_rank=0.5` を含む結果だったと訂正した。
- そこで `min_entry_rank` を明示grid化し、fresh `2024-03..04` validationで calibrated entry EV + rank gateを再評価した。
- 低support標準selectorでは `entry10/short9/min_rank0.0` が validation total `+17.0910`, worst `+0.7230`, trades `4`, active months `2` で選ばれる。
- しかし validation trades が4件しかなく、月10trades緩和条件にも届かない。`min_trades=10`, `min_active_months=2`, `min_worst_pnl=0` のsupport gateでは標準selectorはNoTradeを返す。
- Fixed test `2024-05..12` では `entry10/short9/min_rank0.0` が total `+87.8942`, worst `-2.2800`, trades `10`。rank候補の `entry8/short9/min_rank0.6` も total `+74.2970`, worst `-20.1600`, trades `11`。
- 判断: rank gateは有効なdiagnostic admission axisとして残すが、標準policyは昇格しない。validation supportが薄く、低頻度の偶然勝ちを標準採用するリスクがまだ高い。

## Artifacts

- Selector script: `scripts/experiments/entry_ev_admission_selection.py`
- Tests: `tests/test_entry_ev_admission_selection.py`
- Fresh validation rank sweeps:
  - `data/reports/backtests/20260630_entry_evcal_rank_fresh0304_calibrated/20260630_043001_model_sweep_2024-03/metrics.csv`
  - `data/reports/backtests/20260630_entry_evcal_rank_fresh0304_calibrated/20260630_043046_model_sweep_2024-04/metrics.csv`
- Selector outputs:
  - low support: `data/reports/backtests/20260630_043144_20260630_entry_evcal_rank_fresh0304_selector/`
  - active2/worst0: `data/reports/backtests/20260630_043540_20260630_entry_evcal_rank_fresh0304_selector_support2_worst0/`
  - trades10/active2/worst0: `data/reports/backtests/20260630_043540_20260630_entry_evcal_rank_fresh0304_selector_support10_worst0/`
- Fixed test sweeps:
  - main grid: `data/reports/backtests/20260630_entry_evcal_rank_test_2024_05_12_calibrated/`
  - added `entry8/short9/min_rank0.6`: `data/reports/backtests/20260630_entry_evcal_rank_test_2024_05_12_calibrated_entry8/`

## Selector Changes

`entry_ev_admission_selection.py` now records `validation_active_months` and accepts support gates:

```text
--min-active-months
--min-worst-pnl
```

The standard selector therefore checks:

```text
validation_total > min_positive_pnl
validation_trades >= min_trades
validation_active_months >= min_active_months
validation_worst >= min_worst_pnl
validation_max_dd <= max_drawdown
```

This keeps NoTrade-first behavior while allowing us to state how much evidence is required before a sparse candidate can become standard.

## Fresh Validation

Validation months: `2024-03, 2024-04`.

| entry | short offset | min rank | validation total | worst | trades | active months | max DD | long PnL | short PnL |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `10` | `9` | `0.0` | `+17.0910` | `+0.7230` | `4` | `2` | `0.0000` | `+0.7230` | `+16.3680` |
| `12` | `6` | `0.6` | `+10.7950` | `+0.7230` | `4` | `2` | `21.4080` | `+0.7230` | `+10.0720` |
| `12` | `6` | `0.5` | `+8.6630` | `-16.3290` | `7` | `2` | `21.4080` | `+0.7230` | `+7.9400` |
| `14` | `6` | `0.0` | `+7.7270` | `0.0000` | `1` | `1` | `0.0000` | `0.0000` | `+7.7270` |
| `8` | `9` | `0.6` | `+6.3112` | `+0.7230` | `7` | `2` | `24.6588` | `+0.7230` | `+5.5882` |

Selector outcomes:

| selector gate | selected | validation evidence |
|---|---|---|
| `min_trades=1` | `entry10/short9/min_rank0.0` | total `+17.0910`, trades `4`, active months `2` |
| `min_trades=1`, `min_active_months=2`, `min_worst_pnl=0` | `entry10/short9/min_rank0.0` | same row, because both months are non-negative |
| `min_trades=10`, `min_active_months=2`, `min_worst_pnl=0` | NoTrade | best total still `+17.0910`, but no row has enough trades |

Interpretation: the low-support row is not useless; it is exactly the kind of sparse diagnostic we want to study. It is not enough evidence for standard adoption.

## Fixed Test

Test months: `2024-05..12`.

| entry | short offset | min rank | test total | worst | trades | active months | max DD | long PnL | short PnL |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `10` | `6` | `0.0` | `+136.5024` | `-46.6514` | `42` | `7` | `47.0184` | `0.0000` | `+136.5024` |
| `10` | `6` | `0.5` | `+130.3508` | `-43.2296` | `41` | `7` | `43.5966` | `0.0000` | `+130.3508` |
| `10` | `9` | `0.0` | `+87.8942` | `-2.2800` | `10` | `5` | `6.7320` | `0.0000` | `+87.8942` |
| `8` | `9` | `0.6` | `+74.2970` | `-20.1600` | `11` | `5` | `26.0160` | `0.0000` | `+74.2970` |
| `12` | `6` | `0.0` | `+72.6094` | `-45.2606` | `19` | `6` | `45.2606` | `0.0000` | `+72.6094` |
| `10` | `9` | `0.6` | `+71.5000` | `0.0000` | `3` | `3` | `0.0000` | `0.0000` | `+71.5000` |
| `12` | `6` | `0.5` | `+65.4014` | `-37.8326` | `19` | `6` | `37.8326` | `0.0000` | `+65.4014` |
| `12` | `6` | `0.6` | `+39.1826` | `-11.2284` | `5` | `4` | `11.2284` | `0.0000` | `+39.1826` |

Validation-selected low-support row `entry10/short9/min_rank0.0` monthly:

| month | PnL | trades |
|---|---:|---:|
| 2024-05 | `-0.0120` | `1` |
| 2024-06 | `+32.5900` | `1` |
| 2024-07 | `0.0000` | `0` |
| 2024-08 | `+48.2500` | `3` |
| 2024-09 | `0.0000` | `0` |
| 2024-10 | `0.0000` | `0` |
| 2024-11 | `+9.3462` | `4` |
| 2024-12 | `-2.2800` | `1` |

Rank-gated diagnostic `entry8/short9/min_rank0.6` monthly:

| month | PnL | trades |
|---|---:|---:|
| 2024-05 | `+21.6916` | `2` |
| 2024-06 | `+23.4000` | `1` |
| 2024-07 | `0.0000` | `0` |
| 2024-08 | `+12.7540` | `2` |
| 2024-09 | `0.0000` | `0` |
| 2024-10 | `-20.1600` | `1` |
| 2024-11 | `+36.6114` | `5` |
| 2024-12 | `0.0000` | `0` |

The fixed tests show that the admission family has usable signal. They also show that the signal is mostly short-side, low-count, and sensitive to a small number of trades.

## Decision

No standard policy is promoted.

Accepted:

- `min_entry_rank` is a legitimate diagnostic admission axis.
- `validation_active_months`, `min_active_months`, and `min_worst_pnl` support gates are accepted selector infrastructure.
- `entry10/short9/min_rank0.0`, `entry12/short6/min_rank0.5`, `entry12/short6/min_rank0.6`, and `entry8/short9/min_rank0.6` remain diagnostic rows for the next folds.

Rejected for standard adoption:

- Selecting `entry10/short9/min_rank0.0` under `min_trades=1`. Four validation trades across two months is too little support.
- Treating 00209's `cal12/short6` fixed test as pure threshold evidence. It was rank-gated at `min_entry_rank=0.5`.
- Promoting a candidate because the later fixed test is positive when the validation support gate would choose NoTrade.

## Next

1. Run the same calibrated rank grid on additional chronological model-refit folds, not only this 2023-fit prediction family.
2. Use rank/quantile features to improve validation support, but keep `min_trades=10`, `active_months>=2`, and `worst>=0` as the current promotion bar unless a report explicitly changes it.
3. Add side/regime rank calibration so that `min_entry_rank` is not a global scalar across regimes with different prediction distributions.
4. Continue comparing against NoTrade, not just against other sparse trading rows.

## Verification

- Rank validation sweeps: OK
- Fixed test sweeps `2024-05..12`: OK
- Added selector support gates: OK
- `python3 -m unittest tests.test_entry_ev_admission_selection`: OK
- `python3 -m unittest tests.test_entry_ev_admission_selection tests.test_docs_reports`: OK
- `python3 -m py_compile scripts/experiments/entry_ev_admission_selection.py tests/test_entry_ev_admission_selection.py`: OK
- `git diff --check`: OK
- internal `日時` report ordering check: OK, latest `00210_2026-06-30_entry_ev_rank_gate_support_audit.md`
