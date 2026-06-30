# Entry EV Validation Inventory

日時: 2026-06-30 14:42 JST
更新日時: 2026-06-30 14:42 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00214の次アクションとして、既存entry EV / rank sweep artifactが追加validation windowとして使えるかを棚卸しした。
- `scripts/experiments/entry_ev_validation_inventory.py` を追加した。`metrics.csv` 群を読み、月、family、role、protocol、grid完全性、reference key一致数をCSV化する。
- 実データでは `39` metrics filesを検査し、window candidate summaryは `10` family groups。
- 完全rank gridとしてvalidation候補に使える既存windowは2本だけ。
- 使えるwindowは fresh2024 rank validation `2024-03,2024-04` と refit2025 rank validation `2025-01,2025-02`。
- refit2025 `2025-03..12` は完全rank gridだが固定testなので、同じaudit内でvalidationへ流用しない。
- chrono2024 `2024-05..12` は固定test扱いで、しかも `18` rows/month の部分rank gridと `1` row/month のentry8追加だけなので、完全rank validationとして比較できない。
- `2024-01..02` のvalidation artifactはnon-rank gridで、rank gridを増やすなら再生成が必要。

## Artifacts

- Script: `scripts/experiments/entry_ev_validation_inventory.py`
- Tests: `tests/test_entry_ev_validation_inventory.py`
- Run:
  - `data/reports/backtests/20260630_entry_ev_validation_inventory/20260630_054205_entry_ev_validation_inventory/`
- Outputs:
  - `monthly_inventory.csv`
  - `window_candidate_summary.csv`
  - `inventory.json`

## Method

Command:

```bash
python3 scripts/experiments/entry_ev_validation_inventory.py \
  --metric-glob 'data/reports/backtests/20260630_entry_evcal*/**/metrics.csv' \
  --reference-summary data/reports/backtests/20260630_entry_evcal_rank_multiwindow_selector_relaxed/20260630_050919_entry_ev_rank_multiwindow_relaxed/validation_summary.csv \
  --output-dir data/reports/backtests/20260630_entry_ev_validation_inventory \
  --label entry_ev_validation_inventory
```

Classification:

| class | condition |
|---|---|
| `full_rank_grid` | `min_entry_rank=[0.0,0.5,0.6,0.7,0.8,0.9]`, `entry=[8,10,12,14]`, `short_offset=[3,6,9]`, rows >= `72` |
| `partial_rank_grid` | nonzero rankを含むが、full rank gridではない |
| `nonrank_grid` | rankは実質 `0.0` のみで、旧threshold grid |

Role:

| role | interpretation |
|---|---|
| `validation_candidate` | 追加validationとして比較可能な候補 |
| `fixed_test_or_holdout` | 同じaudit内でvalidationに流用しない |
| `calibration_validation_nonrank` | rank grid化するなら再生成が必要 |
| `fresh_validation_nonrank` | rank grid化済みの別artifactを優先する |

Reference key matchは、multi-window selector relaxed runの `validation_summary.csv` に対し、以下の列で比較した。

```text
policy, entry_threshold, short_entry_threshold_offset, side_margin, risk_penalty, min_entry_rank
```

## Inventory Summary

| family | role | grid | months | status |
|---|---|---|---|---|
| `20260630_entry_evcal_rank_fresh0304_calibrated` | validation | full rank | `2024-03,2024-04` | usable validation window |
| `20260630_entry_evcal_rank_refit2025_validation_calibrated` | validation | full rank | `2025-01,2025-02` | usable validation window |
| `20260630_entry_evcal_rank_refit2025_test_calibrated` | fixed test | full rank | `2025-03..2025-12` | not reusable for same audit |
| `20260630_entry_evcal_rank_test_2024_05_12_calibrated` | fixed test | partial rank | `2024-05..2024-12` | incomplete grid, not comparable |
| `20260630_entry_evcal_rank_test_2024_05_12_calibrated_entry8` | fixed test | partial rank | `2024-05..2024-12` | ad hoc one-row add-on |
| `20260630_entry_evcal_validation_calibrated` | calibration validation | non-rank | `2024-01,2024-02` | regenerate rank sweep if needed |
| `20260630_entry_evcal_validation_raw` | calibration validation | non-rank | `2024-01,2024-02` | regenerate rank sweep if needed |
| `20260630_entry_evcal_fresh0304_calibrated` | fresh validation | non-rank | `2024-03,2024-04` | superseded by rank grid |

## Decision

Accepted:

- Entry EV validation inventory infrastructure.
- Existing validation evidence count is only two full-rank windows: `2024-03..04` and `2025-01..02`.
- Fixed test months remain fixed test months unless a new outer test is explicitly reserved.
- Partial rank grid artifacts cannot be mixed into full rank selector comparison without regeneration.

Rejected:

- Treating `2025-03..12` full-rank fixed test as additional validation for the current selector.
- Treating `2024-05..12` partial rank fixed test rows as if they were full comparable validation grid.
- Promoting sparse high-rank candidates from fixed-test positivity without new validation support.

## Next

1. If adding early validation, regenerate full rank sweeps for `2024-01..02`; label them calibration-validation, not clean outer holdout.
2. If using `2024-05..12` as validation, regenerate full rank grid and reserve a later untouched outer test before selection.
3. Prefer new chronological folds with explicit train / validation / test roles over recycling fixed-test months.
4. Keep NoTrade-first selection until additional validation windows support a policy without fixed-test leakage.

## Verification

- `python3 -m unittest tests.test_entry_ev_validation_inventory`: OK
- `python3 -m py_compile scripts/experiments/entry_ev_validation_inventory.py tests/test_entry_ev_validation_inventory.py`: OK
- `python3 -m unittest tests.test_entry_ev_validation_inventory tests.test_entry_ev_sparse_rank_diagnostics tests.test_entry_ev_admission_gate_sensitivity tests.test_entry_ev_admission_selection tests.test_docs_reports`: OK, `20` tests
- `python3 -m py_compile scripts/experiments/entry_ev_validation_inventory.py scripts/experiments/entry_ev_sparse_rank_diagnostics.py scripts/experiments/entry_ev_admission_gate_sensitivity.py scripts/experiments/entry_ev_admission_selection.py tests/test_entry_ev_validation_inventory.py tests/test_entry_ev_sparse_rank_diagnostics.py tests/test_entry_ev_admission_gate_sensitivity.py tests/test_entry_ev_admission_selection.py`: OK
- `git diff --check`: OK
- Internal `日時:` report order audit: OK, `215` reports, latest `00215_2026-06-30_entry_ev_validation_inventory.md`
- inventory run: OK, `39` metrics files, `2` usable full-rank validation windows
