# Entry EV Support Repair Leak-Free Tiebreak

日時: 2026-07-03 08:17 JST
更新日時: 2026-07-03 08:17 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00334のlistwise cluster診断後に、support repairの実行時候補sortに `actual_pnl_at_hv_chosen_horizon` がtie-breakerとして混入していることを発見した。
- これはscoreが同点の候補で将来実損益を見てよい候補を選ぶlook-aheadであり、実行可能policy evidenceとして扱えない。
- `select_support_additions()` の `score` / `repair_score` sortからactual PnLを除去し、observableなscore列と時刻だけで決定するよう修正した。
- listwise診断の `repair_score_greedy` / `support_proxy_high_greedy` からもactual PnL tie-breakerを除去した。`actual_oracle_greedy` は診断上限 / teacher設計用なのでactual PnL使用を維持する。
- 修正後に00332 w0 s2条件の本体replayを再実行すると、best scenarioのadded PnLは `+63.9770 -> +60.8530`、EV -2 scenarioは `+34.8410 -> +31.7170` に低下した。
- 結論: 00334の「repair_score_greedyがcurrent replayと完全一致」という読みはleak混入後の結果なので破棄する。leak-free replay後は `current_replay == repair_score_greedy` に戻ったが、標準blockerは残る。標準policyはNoTrade。

## Artifacts

- Modified:
  - `scripts/experiments/entry_ev_support_repair_horizon_replay.py`
  - `scripts/experiments/entry_ev_support_repair_listwise_cluster_diagnostics.py`
- Added tests:
  - `tests/test_entry_ev_support_repair_horizon_replay.py`
  - `tests/test_entry_ev_support_repair_listwise_cluster_diagnostics.py`
- Leak-free replay:
  - `data/reports/backtests/20260702_231709_20260703_entry_ev_00335_support_repair_leakfree_replay_w0_s2/`
- Leak-free replay listwise diagnostics:
  - `data/reports/backtests/20260702_231734_20260703_entry_ev_00335_support_repair_leakfree_replay_listwise_best_s1/`
  - `data/reports/backtests/20260702_231734_20260703_entry_ev_00335_support_repair_leakfree_replay_listwise_evm2_s1/`
- Old replay candidate-surface re-diagnosis:
  - `data/reports/backtests/20260702_231437_20260703_entry_ev_00335_support_repair_leakfree_listwise_best_s1/`
  - `data/reports/backtests/20260702_231437_20260703_entry_ev_00335_support_repair_leakfree_listwise_evm2_s1/`

## Leak

Before this report, support repair selected tied candidates with this order:

```text
repair_score
support_reduction_value
repair_expected_pnl
actual_pnl_at_hv_chosen_horizon
decision_timestamp
entry_timestamp
```

When `repair_score`, support reduction, and expected PnL tied, the sort preferred higher realized future PnL. The same pattern existed in the listwise diagnostic selector specs.

Fixed runtime sort:

```text
repair_score
support_reduction_value
repair_expected_pnl
decision_timestamp
entry_timestamp
hv_chosen_horizon_minutes
```

Default score mode now uses:

```text
hv_chosen_score
decision_timestamp
entry_timestamp
hv_chosen_horizon_minutes
```

This makes tied candidates deterministic and observable at decision time. It is less flattering, but it is the correct evaluation basis.

## Results

Leak-free replay under the same 00332 w0 s2 low-complexity broad-prior ranker settings:

| scenario | added count | added PnL old | added PnL leak-free | combined old | combined leak-free | blockers leak-free |
|---|---:|---:|---:|---:|---:|---|
| p0.45 / EV 2 / tail 0.3 | `5` | `+63.9770` | `+60.8530` | `+403.2680` | `+400.1440` | `month_pnl_below_floor, role_trades_low, side_share_high` |
| p0.45 / EV -2 / tail 0.3 | `6` | `+34.8410` | `+31.7170` | `+374.1320` | `+371.0080` | `role_total_pnl_below_floor, month_pnl_below_floor, side_share_high` |

Leak-free replay listwise diagnostics:

| scenario | current / repair score actual | actual oracle | oracle delta | actual min | loss count |
|---|---:|---:|---:|---:|---:|
| p0.45 / EV 2 / tail 0.3 | `+60.8530` | `+66.6130` | `+5.7600` | `+0.3400` | `0` |
| p0.45 / EV -2 / tail 0.3 | `+31.7170` | `+57.1600` | `+25.4430` | `-29.1360` | `1` |

The old replay candidate-surface re-diagnosis showed the exact effect:

```text
refit2025_validation 2025-08 long:
  old current selected 17:28 actual +13.2500
  leak-free repair_score selected 17:22 actual +12.7200

refit2025_validation 2025-08 short:
  old current selected 03:27 actual +2.9340
  leak-free repair_score selected 03:23 actual +0.3400
```

The PnL difference is `-3.1240`. This was the hidden optimism in 00334.

## Decision

- Leak-free tie-breaker fix: accepted.
- Support repair listwise diagnostics: accepted infrastructure, but 00334 numbers must be read through this correction.
- 00329/00332 low-complexity ranker remains a diagnostic branch, not a standard policy.
- Simple reranking still does not solve standard blockers. EV -2 still contains `fresh2024_validation 2024-08 long -29.1360`, and reranking cannot remove it because the target group has only one candidate.
- Standard policy remains NoTrade.

## Next

1. Treat any selector using `actual_pnl_at_hv_chosen_horizon` outside explicit oracle diagnostics as a leakage bug.
2. Continue from the leak-free replay baseline, not from 00334's old current-vs-repair equality.
3. Build the next layer as chronological target/meta-selector or candidate-generation repair:
   - listwise candidate utility as teacher only when target construction is purged from execution features,
   - fresh/thin-month candidate generation,
   - abstention layer for singleton harmful support candidates.

## Verification

- `uv run python -m py_compile scripts/experiments/entry_ev_support_repair_horizon_replay.py scripts/experiments/entry_ev_support_repair_listwise_cluster_diagnostics.py tests/test_entry_ev_support_repair_horizon_replay.py tests/test_entry_ev_support_repair_listwise_cluster_diagnostics.py tests/test_docs_reports.py`: OK
- `uv run python -m unittest tests.test_entry_ev_support_repair_horizon_replay tests.test_entry_ev_support_repair_listwise_cluster_diagnostics tests.test_docs_reports`: OK
- Leak-free broad-prior horizon-choice replay: OK
- Leak-free listwise diagnostics on new replay: OK
