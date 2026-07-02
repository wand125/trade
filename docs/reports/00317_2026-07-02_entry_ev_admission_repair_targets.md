# Entry EV Admission Repair Targets

日時: 2026-07-02 19:53 JST
更新日時: 2026-07-02 19:53 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00316の次アクションとして、support-limited negative months と side-share blockersを「どれだけ修復すればstandard admissionへ近づくか」に分解した。
- `scripts/experiments/entry_ev_admission_repair_target_diagnostics.py` を追加し、monthly metricsから role/month PnL floor、month trade support、side balance の修復targetを算出できるようにした。
- 00314 best overlay (`fixed60_margin_w5 + holdext/position-quality`) では、standard gateのPnL不足は合計 `+2.1686` と小さい。
- 一方、support/sideの修復には月別に `8` extra trades が必要で、その内訳は long `5` / short `3`。主因は1-trade / 0-trade / one-sided months。
- 00310 referenceと00314 w5は同じ repair targetになった。00314 w5はtotalを上げたが、standard admission blocker構造は改善していない。
- 判断: admission repair target diagnosticsはaccepted infrastructure。次はrow削除ではなく、thin monthへ反対側候補を作れるentry coverage / side-balance designを検証する。

## Artifacts

- New script:
  - `scripts/experiments/entry_ev_admission_repair_target_diagnostics.py`
- New tests:
  - `tests/test_entry_ev_admission_repair_target_diagnostics.py`
- Repair target runs:
  - `data/reports/backtests/20260702_105254_20260702_entry_ev_00317_admission_repair_targets_00314_w5_s1/`
  - `data/reports/backtests/20260702_105312_20260702_entry_ev_00317_admission_repair_targets_00310_proxy_s1/`

## Method

For each role/month:

```text
month_pnl_hurdle = max(0, month_floor - month_pnl)
extra trades = minimum long/short additions such that:
  final_trade_count >= min_month_trades
  max(final_long_share, final_short_share) <= max_side_trade_share
```

Important edge case:

```text
0-trade month + max_side_share < 1.0
=> 2 trades are needed, one long and one short.
```

This avoids underestimating side-share repair by adding a single one-sided trade to an empty month.

Candidate-level summary keeps strict blockers as observed, while repair targets estimate what would be needed to remove those blockers.

## Candidate Summary

00314 best overlay target:

| branch | total | month pnl hurdle | extra trades | extra long | extra short | negative months | support-limited neg | blockers |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| `holdext_long_range_normal_ny` | `+339.2910` | `+2.1686` | `8` | `5` | `3` | `4` | `3` | month/role/month-trade/side-share |
| `long_range_normal_ny_fixed60_pred_gt0` | `+339.2910` | `+2.1686` | `8` | `5` | `3` | `4` | `3` | month/role/month-trade/side-share |
| `none` | `+338.4078` | `+3.0518` | `7` | `4` | `3` | `5` | `4` | month/role/side-share |

00310 reference:

| branch | total | month pnl hurdle | extra trades | extra long | extra short | negative months | support-limited neg | blockers |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| `long_range_normal_ny_fixed60_pred_gt0` | `+337.6010` | `+2.1686` | `8` | `5` | `3` | `4` | `3` | month/role/month-trade/side-share |
| `none` | `+326.1098` | `+3.0518` | `7` | `4` | `3` | `5` | `4` | month/role/side-share |

Reading:

- 00314 w5 improves total versus 00310, but it does not reduce the standard admission repair target.
- The gap to month floor is tiny compared with total PnL. The hard part is coverage and balance, not raw PnL magnitude.
- A policy branch that only deletes bad rows can improve total while leaving the same admission blockers intact.

## Month Targets

For `long_range_normal_ny_fixed60_pred_gt0` / `holdext_long_range_normal_ny`:

| role | month | pnl | trades | long | short | side share | pnl hurdle | extra long | extra short | class |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `fresh2024_validation` | `2024-03` | `-0.3636` | `1` | `0` | `1` | `1.0000` | `0.3636` | `1` | `0` | support-limited |
| `fresh2024_validation` | `2024-08` | `+9.3100` | `1` | `0` | `1` | `1.0000` | `0.0000` | `1` | `0` | pass but one-sided |
| `fresh2024_validation` | `2024-11` | `-0.6120` | `1` | `0` | `1` | `1.0000` | `0.6120` | `1` | `0` | support-limited |
| `hybrid2025_0912_external` | `2025-10` | `+11.4900` | `3` | `0` | `3` | `1.0000` | `0.0000` | `1` | `0` | pass but one-sided |
| `hybrid2025_0912_external` | `2025-11` | `-0.7200` | `1` | `1` | `0` | `1.0000` | `0.7200` | `0` | `1` | support-limited |
| `refit2025_validation` | `2025-03` | `-0.4730` | `9` | `5` | `4` | `0.5556` | `0.4730` | `0` | `0` | shallow |
| `refit2025_validation` | `2025-07` | `+2.0824` | `7` | `7` | `0` | `1.0000` | `0.0000` | `0` | `1` | pass but one-sided |
| `refit2025_validation` | `2025-08` | `0.0000` | `0` | `0` | `0` | `0.0000` | `0.0000` | `1` | `1` | empty month |

Reading:

- Three negative months are support-limited and need one opposite-side trade plus small positive aggregate PnL.
- One negative month (`refit2025 2025-03`) is shallow but not support-limited: it needs only `+0.4730` PnL, not extra support.
- Four non-negative months still require extra support because side-share or zero-trade month would fail standard admission.
- Therefore, passing standard admission is not equivalent to fixing only negative months.

## Role Targets

After month-level repair additions:

| role | current trades | current role PnL | post-month-repair trades | remaining role trade shortfall |
|---|---:|---:|---:|---:|
| `fresh2024_validation` | `3` | `+8.3344` | `6` | `0` |
| `hybrid2025_0912_external` | `6` | `+15.2700` | `8` | `0` |
| `refit2025_validation` | `107` | `+284.0204` | `110` | `0` |

Reading:

- The original `role_trades_low` blocker is mostly a consequence of one-sided thin months.
- Month-level balanced additions would also fix role support for `fresh2024_validation`.
- This suggests the next experiment should search for additional balanced entries in thin months, not simply lower the admission threshold.

## Decision

Accepted:

- admission repair target diagnostics
- explicit treatment of 0-trade months as requiring two balanced trades under side-share gate
- keeping strict blockers separate from repair targets

Rejected:

- claiming 00314 w5 improved standard-admission readiness just because total PnL improved
- treating `+2.1686` PnL hurdle as the full problem
- fixing support-aware blockers with further row deletion only

Standard policy remains NoTrade.

## Next

1. Search prediction rows in the thin months for near-miss opposite-side candidates and quantify their expected/realized contribution under the same one-position state constraint.
2. Add a side-balanced support overlay that can add/replace candidates only when it improves month support without violating NoTrade-first gates.
3. Keep repair targets as a gate before downstream optimization: if a branch improves total but not repair targets, do not treat it as standard-readiness progress.

## Verification

- `uv run python -m py_compile scripts/experiments/entry_ev_admission_repair_target_diagnostics.py tests/test_entry_ev_admission_repair_target_diagnostics.py`: OK
- `uv run python -m unittest tests.test_entry_ev_admission_repair_target_diagnostics`: OK
- `uv run python -m unittest tests.test_entry_ev_admission_repair_target_diagnostics tests.test_docs_reports`: OK
- `git diff --check`: OK
- 00317 admission repair target runs: OK
