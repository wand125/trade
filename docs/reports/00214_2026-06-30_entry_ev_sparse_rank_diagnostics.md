# Entry EV Sparse Rank Diagnostics

日時: 2026-06-30 14:31 JST
更新日時: 2026-06-30 14:31 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00213で残した課題として、fixed-test-positiveに見えた sparse high-rank rowを、fixed-test PnLで採用せず、validation evidenceだけで診断した。
- `entry_ev_sparse_rank_diagnostics.py` を追加した。multi-window validation summary、window-level validation summary、fixed-test summaryを読み、各候補のvalidation blockerを列挙する。
- 採用判定の仮gateは `min_trades=20`, `active_months>=4`, `validation_worst>=0`, `worst_window>=0`, `min_window_trades>=1`, `max_side_trade_share<=0.95`。
- fixed-test PnLは `fixed_positive_audit` として横に置くだけで、`promotion_eligible_by_validation` には使わない。
- 実データでは `72` candidates中、validation gateを通る候補は `0`。fixed-positive audit rowは1件だけで、`entry14/short9/min_rank0.6`。
- そのrowは fixed total `+98.9868` だが、validation total `-0.3844`, trades `3`, active months `2`, min window trades `0`, side share `1.0000`。fresh2024 windowは0 trade、refit2025 windowは3 long-only tradesで `-0.3844`。
- 判断: sparse high-rank rowを今の2-window validationから標準採用する根拠はない。fixed-positive rowは「将来良かった候補」ではなく「validationで観測されていない候補」と扱う。

## Artifacts

- Script: `scripts/experiments/entry_ev_sparse_rank_diagnostics.py`
- Tests: `tests/test_entry_ev_sparse_rank_diagnostics.py`
- Run:
  - `data/reports/backtests/20260630_entry_ev_sparse_rank_diagnostics/20260630_053120_entry_ev_sparse_rank_diagnostics/`
- Outputs:
  - `candidate_diagnostics.csv`
  - `rank_summary.csv`
  - `blocker_summary.csv`
  - `window_details.csv`
  - `diagnostics.json`

## Method

Input:

```text
validation_summary.csv:
data/reports/backtests/20260630_entry_evcal_rank_multiwindow_selector_relaxed/20260630_050919_entry_ev_rank_multiwindow_relaxed/validation_summary.csv

window_validation_summary.csv:
data/reports/backtests/20260630_entry_evcal_rank_multiwindow_selector_relaxed/20260630_050919_entry_ev_rank_multiwindow_relaxed/window_validation_summary.csv

fixed summary:
data/reports/backtests/20260630_entry_evcal_rank_multiwindow_fixed_test_audit/combined_fixed_test_summary_both_windows.csv
```

Command:

```bash
python3 scripts/experiments/entry_ev_sparse_rank_diagnostics.py \
  --validation-summary data/reports/backtests/20260630_entry_evcal_rank_multiwindow_selector_relaxed/20260630_050919_entry_ev_rank_multiwindow_relaxed/validation_summary.csv \
  --window-validation-summary data/reports/backtests/20260630_entry_evcal_rank_multiwindow_selector_relaxed/20260630_050919_entry_ev_rank_multiwindow_relaxed/window_validation_summary.csv \
  --fixed-test-summary data/reports/backtests/20260630_entry_evcal_rank_multiwindow_fixed_test_audit/combined_fixed_test_summary_both_windows.csv \
  --output-dir data/reports/backtests/20260630_entry_ev_sparse_rank_diagnostics \
  --label entry_ev_sparse_rank_diagnostics \
  --min-trades 20 \
  --min-active-months 4 \
  --min-worst-pnl 0 \
  --min-window-total 0 \
  --min-window-trades 1 \
  --max-side-trade-share 0.95
```

Fixed-test metrics are joined on common sweep keys only:

```text
policy, entry_threshold, short_entry_threshold_offset, side_margin, risk_penalty, min_entry_rank
```

This keeps the diagnostic compatible with older fixed summaries while avoiding a full-key mismatch.

## Rank Summary

| min rank | candidates | validation positive | validation eligible | fixed positive | validation total max | validation total mean | min window trades min | side share max | fixed total max |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `0.0` | `12` | `12` | `0` | `0` | `+190.4544` | `+130.0089` | `0` | `0.9880` | `-818.2432` |
| `0.5` | `12` | `12` | `0` | `0` | `+170.7764` | `+132.8041` | `0` | `0.9877` | `-755.0340` |
| `0.6` | `12` | `5` | `0` | `1` | `+10.4106` | `-7.2061` | `0` | `1.0000` | `+98.9868` |
| `0.7` | `12` | `0` | `0` | `0` | `0.0000` | `0.0000` | `0` | `0.0000` | `NaN` |
| `0.8` | `12` | `0` | `0` | `0` | `0.0000` | `0.0000` | `0` | `0.0000` | `NaN` |
| `0.9` | `12` | `0` | `0` | `0` | `0.0000` | `0.0000` | `0` | `0.0000` | `NaN` |

## Fixed-Positive Audit

Only one row is fixed-positive:

| entry | short offset | min rank | validation total | validation worst | worst window | validation trades | active months | min window trades | side share | blockers | fixed total | fixed worst | fixed trades |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|
| `14` | `9` | `0.6` | `-0.3844` | `-5.4684` | `-0.3844` | `3` | `2` | `0` | `1.0000` | total, trades, active months, worst, worst window, window trades, side share | `+98.9868` | `-133.6912` | `113` |

Window detail:

| window | validation total | trades | side | interpretation |
|---|---:|---:|---|---|
| `fresh2024` | `0.0000` | `0` | none | not observed |
| `refit2025` | `-0.3844` | `3` | long-only | observed weakly and negative |

This is not a case where validation saw a sparse but clean positive signal. It is a case where the candidate was effectively untested in one window and negative in the other.

## Blockers

Across all candidates, common blockers under the defensive gate:

| blocker | candidate count | fixed-positive count |
|---|---:|---:|
| validation active months low | `47` | `1` |
| validation trades low | `47` | `1` |
| validation total not positive | `43` | `1` |
| validation window trades low | `41` | `1` |
| validation worst below floor | `29` | `1` |
| validation worst window below floor | `28` | `1` |
| validation side share high | `12` | `1` |

Top validation-positive but blocked rows confirm the other side of the problem: lower-rank candidates can have high validation total, but they are blocked by side imbalance, weak worst month/window, or active-month support and fixed-test negative PnL.

## Decision

Accepted:

- Sparse-rank diagnostic infrastructure.
- Validation-only blocker labeling.
- Fixed-test-positive rows as audit clues, not selection evidence.

Rejected for standard adoption:

- `entry14/short9/min_rank0.6`, despite fixed total `+98.9868`, because validation support is absent/negative.
- Relaxing NoTrade-first or window-support gates to admit sparse rows.

Current standard remains NoTrade.

## Next

1. Add more validation windows. Sparse rows cannot be judged from two windows when one has zero trades.
2. Evaluate side/regime-aware rank or calibrated EV quantile so high-rank rows can be supported by validation evidence, not hindsight.
3. Keep fixed-positive sparse rows as a diagnostic target: explain why validation does not see them before considering any policy relaxation.

## Verification

- `python3 -m py_compile scripts/experiments/entry_ev_sparse_rank_diagnostics.py scripts/experiments/entry_ev_admission_gate_sensitivity.py scripts/experiments/entry_ev_admission_selection.py tests/test_entry_ev_sparse_rank_diagnostics.py tests/test_entry_ev_admission_gate_sensitivity.py tests/test_entry_ev_admission_selection.py`: OK
- `python3 -m unittest tests.test_entry_ev_sparse_rank_diagnostics tests.test_entry_ev_admission_gate_sensitivity tests.test_entry_ev_admission_selection tests.test_docs_reports`: OK
- `git diff --check`: OK
- Internal `日時:` report order audit: OK, `214` reports, latest `00214_2026-06-30_entry_ev_sparse_rank_diagnostics.md`
- sparse rank diagnostic run: OK
