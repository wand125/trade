# Entry EV Month Warmup Overlay

日時: 2026-07-02 14:21 JST
更新日時: 2026-07-02 14:21 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00296の次アクションとして、remaining thin-support negative monthsを単発blacklistで追わず、月内サポート形成を待つpolicy-level overlayを診断した。
- `scripts/experiments/entry_ev_month_warmup_overlay.py` を追加し、既存entry-block overlay trade pathに対して `skip_first_N`、`wait_opposite_seen`、`wait_both_sides_seen` をno-replacementで重ねられるようにした。
- 対象は00296のdiagnostic benchmark branchに絞った。
- 結果: `skip_first_1` は1-trade negative monthsを消す一方で、totalを `-54.0878` 落とし、month minも `-0.7200 -> -1.9596` へ悪化した。より強いwarmup ruleはさらに悪化した。
- 判断: month-warmup overlay infrastructureはaccepted diagnostics。現warmup rulesは勝ちtradeを削るためreject。標準policyはNoTrade。

## Artifacts

- New script:
  - `scripts/experiments/entry_ev_month_warmup_overlay.py`
- New test:
  - `tests/test_entry_ev_month_warmup_overlay.py`
- Warmup overlay run:
  - `data/reports/backtests/20260702_052051_20260702_entry_ev_month_warmup_overlay_residual_combo_best_s1/`
- Support-aware check:
  - `data/reports/backtests/20260702_052102_20260702_entry_ev_month_warmup_support_aware_best_s1/`

## Target Branch

```text
selector_variant:
  loss_exit30_cd15__holdext_isolated_large_loss_long_t-5_h720__entryblock_short_rollover_or_london_midloss_or_holdext_range_ny
candidate:
  q95_sg95_rank90_floor5_side_regime_session_month
```

This is the 00296 diagnostic benchmark: total `+329.4348`, role min `+0.5354`, month min `-0.7200`.

## Rules

All rules use only signals already visible within the current role/month path:

| rule | meaning |
|---|---|
| `none` | baseline branch |
| `skip_first_1/2/3` | skip the first N eligible candidate trades in each role/month |
| `wait_opposite_seen` | execute only after a prior opposite-side candidate signal exists in the same role/month |
| `skip_first_1_wait_opposite_seen` | combine first-signal skip and opposite-side wait |
| `wait_both_sides_seen` | execute only after both long and short candidate signals have already appeared |

This remains a no-replacement overlay. It is diagnostic, not full stateful replacement evidence.

## Results

| rule | total | delta vs input | month min | role min | trades | warmup blocked | blocked PnL |
|---|---:|---:|---:|---:|---:|---:|---:|
| `none` | `+329.4348` | `+0.0000` | `-0.7200` | `+0.5354` | `232` | `0` | `+0.0000` |
| `skip_first_1` | `+275.3470` | `-54.0878` | `-1.9596` | `+0.0000` | `210` | `22` | `+54.0878` |
| `wait_opposite_seen` | `+153.4300` | `-176.0048` | `-9.3634` | `-1.4806` | `176` | `56` | `+176.0048` |
| `skip_first_1_wait_opposite_seen` | `+153.4300` | `-176.0048` | `-9.3634` | `-1.4806` | `176` | `56` | `+176.0048` |
| `skip_first_2` | `+243.9064` | `-85.5284` | `-13.8634` | `+0.0000` | `193` | `39` | `+85.5284` |
| `skip_first_3` | `+237.4250` | `-92.0098` | `-11.1874` | `-1.3106` | `176` | `56` | `+92.0098` |
| `wait_both_sides_seen` | `+130.1576` | `-199.2772` | `-26.3534` | `-1.5906` | `161` | `71` | `+199.2772` |

Support-aware check:

| rule | diagnostic status | support-aware pass | total | month min | structural neg |
|---|---|---:|---:|---:|---:|
| `none` | `support_aware_only` | `true` | `+329.4348` | `-0.7200` | `0` |
| `skip_first_1` | `support_aware_only` | `true` | `+275.3470` | `-1.9596` | `0` |
| `skip_first_2` | `blocked` | `false` | `+243.9064` | `-13.8634` | `2` |
| `wait_opposite_seen` | `blocked` | `false` | `+153.4300` | `-9.3634` | `3` |
| `skip_first_1_wait_opposite_seen` | `blocked` | `false` | `+153.4300` | `-9.3634` | `3` |
| `skip_first_3` | `blocked` | `false` | `+237.4250` | `-11.1874` | `4` |
| `wait_both_sides_seen` | `blocked` | `false` | `+130.1576` | `-26.3534` | `4` |

`skip_first_1` reduces negative month count, but it does so by deleting profitable first signals. It creates a worse worst month in refit2025 2025-06 (`-1.9596`) and lowers total by `54.0878`.

## Decision

Accepted:

- month-warmup overlay diagnostics
- filtering the overlay to a named selector variant/candidate for lightweight branch-level diagnostics
- using warmup as a negative control for thin-support residual months

Rejected:

- `skip_first_1/2/3` as a standard policy mechanism
- `wait_opposite_seen` / `wait_both_sides_seen` as a standard policy mechanism
- treating support-aware pass of `skip_first_1` as improvement, because total and month floor both worsen

Standard policy remains NoTrade.

## Next

1. Do not chase remaining thin-support floor breaches with broad month-start warmup rules.
2. If reducing thin months is still needed, prefer unused chronology or model-level confidence calibration over monthly sequence deletion.
3. Keep 00293/00296 residual combo as diagnostic benchmark, not standard policy.

## Verification

- `uv run python -m py_compile scripts/experiments/entry_ev_month_warmup_overlay.py tests/test_entry_ev_month_warmup_overlay.py`: OK
- `uv run python -m unittest tests.test_entry_ev_month_warmup_overlay`: OK
- warmup overlay run: OK
- support-aware check run: OK
