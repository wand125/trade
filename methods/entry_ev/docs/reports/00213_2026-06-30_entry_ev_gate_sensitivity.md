# Entry EV Gate Sensitivity

日時: 2026-06-30 14:21 JST
更新日時: 2026-06-30 14:21 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00212で残した課題として、`max_side_trade_share=0.95` を単点で固定せず、side balance / regime floor / window support gateの感度をまとめて評価した。
- `entry_ev_admission_gate_sensitivity.py` を追加し、既存の multi-window `validation_summary.csv` と fixed-test summaryを読み、selector gate gridごとにNoTrade-first selectionを再実行できるようにした。
- base gateは `min_trades=20`, `active_months>=4`, `validation_worst>=0`, `windows=2`, `positive_windows=2`, `active_windows=2`, `worst_window>=0`。
- gridは `min_window_trades in {1,4,10}`, `max_side_trade_share in {0.90,0.95,0.98,inf}`, `min_direction_session_pnl in {-inf,-30,0}`, `min_combined_regime_pnl in {-inf,-50,-40,0}`, `min_direction_combined_regime_pnl in {-inf,-60,-40,0}`。合計 `576` gate。
- 結果は `568` gateがNoTrade、`8` gateだけがpolicyを選択。選ばれたpolicyは全て `entry10/short9/min_rank0.0`。
- そのpolicyは multi-window validation total `+190.4544` だが、両fixed test windowでは total `-943.9322`, worst `-294.1980`, trades `1144`。
- `max_side_trade_share<=0.95` は全てNoTrade、`min_window_trades=10` も全てNoTrade、`min_combined_regime_pnl>=-50` も全てNoTrade。
- 判断: side/regime gate感度分析の実装はaccepted infrastructure。ただし、単純なgate閾値調整では汎化候補を発見できなかった。標準policyはNoTradeのまま。

## Artifacts

- Script: `scripts/experiments/entry_ev_admission_gate_sensitivity.py`
- Tests: `tests/test_entry_ev_admission_gate_sensitivity.py`
- Gate sensitivity run:
  - `data/reports/backtests/20260630_entry_evcal_rank_multiwindow_gate_sensitivity/20260630_052055_entry_ev_rank_multiwindow_gate_sensitivity/`
- Main outputs:
  - `gate_sensitivity.csv`
  - `selected_policy_details.csv`
  - `selection.json`

## Method

Input validation summary:

```text
data/reports/backtests/20260630_entry_evcal_rank_multiwindow_selector_relaxed/20260630_050919_entry_ev_rank_multiwindow_relaxed/validation_summary.csv
```

Input fixed-test summary:

```text
data/reports/backtests/20260630_entry_evcal_rank_multiwindow_fixed_test_audit/combined_fixed_test_summary_both_windows.csv
```

The script reuses the same gate semantics as `entry_ev_admission_selection.py` by calling `filter_standard_candidates` and `select_standard_policy`. Fixed-test metrics are joined only on the intersection of `SWEEP_KEY_COLUMNS` present in both validation and fixed summaries, so older or narrower summaries remain compatible.

Command:

```bash
python3 scripts/experiments/entry_ev_admission_gate_sensitivity.py \
  --validation-summary data/reports/backtests/20260630_entry_evcal_rank_multiwindow_selector_relaxed/20260630_050919_entry_ev_rank_multiwindow_relaxed/validation_summary.csv \
  --fixed-test-summary data/reports/backtests/20260630_entry_evcal_rank_multiwindow_fixed_test_audit/combined_fixed_test_summary_both_windows.csv \
  --output-dir data/reports/backtests/20260630_entry_evcal_rank_multiwindow_gate_sensitivity \
  --label entry_ev_rank_multiwindow_gate_sensitivity \
  --min-trades 20 \
  --min-active-months 4 \
  --min-worst-pnl 0 \
  --min-windows 2 \
  --min-positive-windows 2 \
  --min-active-windows 2 \
  --min-window-total 0 \
  --min-window-trades-values 1,4,10 \
  --max-side-trade-share-values 0.90,0.95,0.98,inf \
  --min-direction-session-pnl-values=-inf,-30,0 \
  --min-combined-regime-pnl-values=-inf,-50,-40,0 \
  --min-direction-combined-regime-pnl-values=-inf,-60,-40,0
```

## Results

Gate selection count:

| selected | count |
|---|---:|
| NoTrade | `568` |
| policy | `8` |

Policy rows by gate:

| min window trades | max side share | selected gates |
|---:|---:|---:|
| `1` | `0.98` | `2` |
| `1` | `inf` | `2` |
| `4` | `0.98` | `2` |
| `4` | `inf` | `2` |
| `10` | any | `0` |

The only selected row:

| entry | short offset | min rank | validation total | worst window | min window trades | side share | dir/session min | combined min | dir/combined min | fixed total | fixed worst | fixed trades |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `10` | `9` | `0.0` | `+190.4544` | `+17.0910` | `4` | `0.9595` | `-27.7386` | `-53.8964` | `-62.4464` | `-943.9322` | `-294.1980` | `1144` |

Hard rejection observations:

| gate family | result |
|---|---|
| `max_side_trade_share<=0.90` | all NoTrade |
| `max_side_trade_share<=0.95` | all NoTrade |
| `min_window_trades=10` | all NoTrade |
| `min_combined_regime_pnl>=-50` | all NoTrade |
| `min_direction_combined_regime_pnl>=-60` | all NoTrade for the selected validation winner |

Comparable fixed-test positive row:

| entry | short offset | min rank | validation total | validation worst window | min window trades | side share | fixed total | fixed worst | fixed trades |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `14` | `9` | `0.6` | `-0.3844` | `-0.3844` | `0` | `1.0000` | `+98.9868` | `-133.6912` | `113` |

This row is important diagnostically, but it is not selectable under the current rule. It is validation-negative, has a zero-trade validation window, and is perfectly one-sided in validation. Promoting it from fixed-test outcome would be hindsight selection.

## Interpretation

The gate grid confirms that 00212's relaxed winner was not a near-miss robust candidate. It survives only when side balance is loose (`0.98` or `inf`), regime floor is loose, and window support is allowed at `4` trades. Tightening any of those to a more defensive level returns NoTrade.

The fixed-test-positive `min_rank=0.6` row shows that sparse high-rank rows may contain signal, but current validation cannot distinguish robust sparse signal from hindsight. That should push the next work toward additional validation windows and rank/EV calibration, not toward relaxing selection rules until the fixed-test positive row is admitted.

## Decision

Accepted:

- `entry_ev_admission_gate_sensitivity.py` as admission-gate sensitivity infrastructure.
- Reusing the selector's gate helper so sensitivity runs and standard selection do not diverge.
- Fixed-test join on common sweep keys only.
- Side-balance, window-support, and regime-floor grids as standard diagnostics before freezing a threshold.

Rejected for standard adoption:

- Relaxed `entry10/short9/min_rank0.0`, because all selected gate variants fixed-test to `-943.9322`.
- `max_side_trade_share=0.95` as a frozen global standard threshold. It is useful as a rejection probe, but this audit alone does not prove the best threshold.
- Fixed-test-positive `entry14/short9/min_rank0.6` as a policy, because validation evidence is non-positive and sparse.

Current standard remains NoTrade.

## Next

1. Increase the number of validation windows before trying to promote any entry EV/rank candidate.
2. Keep `max_side_trade_share`, `min_window_trades`, and regime floors as diagnostics, but do not tune them against fixed-test PnL.
3. Investigate sparse high-rank rows as a separate diagnostic target: why fixed-positive rows are validation-negative or zero-support, without using fixed-test PnL for selection.
4. Add side/regime-aware rank or calibrated EV quantile features, then re-run multi-window admission.

## Verification

- `python3 -m py_compile scripts/experiments/entry_ev_admission_selection.py scripts/experiments/entry_ev_admission_gate_sensitivity.py tests/test_entry_ev_admission_selection.py tests/test_entry_ev_admission_gate_sensitivity.py`: OK
- `python3 -m unittest tests.test_entry_ev_admission_selection tests.test_entry_ev_admission_gate_sensitivity tests.test_docs_reports`: OK
- `git diff --check`: OK
- Internal `日時:` report order audit: OK, `213` reports, latest `00213_2026-06-30_entry_ev_gate_sensitivity.md`
- gate sensitivity run: OK, `576` gates
