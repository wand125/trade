# Entry EV Support-Aware Progression Compare

日時: 2026-07-02 14:09 JST
更新日時: 2026-07-02 14:09 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00295のsupport-aware分類を、raw cd15 -> hold-extension -> side horizon -> entry block -> residual combo の候補系列へ横断適用した。
- default support-aware条件では、00293 residual comboだけが `support_aware_only` になった。
- raw cd15、00290 hold-extension、00291 side horizon、00292 entry blockは、structural negative monthsまたはsupport-limited負け月過多でblocked。
- ただしdefaultで通った00293 bestも、support-limited許容を `3 -> 2` に下げる、またはshallow floorを `-1.0 -> -0.25` に厳しくするとblocked。
- 判断: support-aware分類は候補系列の進歩を説明する診断として有効。ただし通過は感度設定に依存するため、標準policyはNoTradeのまま。

## Artifacts

- Default progression compare:
  - `data/reports/backtests/20260702_050625_20260702_entry_ev_support_aware_progression_compare_s1/`
- Sensitivity:
  - `data/reports/backtests/20260702_050652_20260702_entry_ev_support_aware_progression_compare_support2_s1/`
  - `data/reports/backtests/20260702_050652_20260702_entry_ev_support_aware_progression_compare_shallow025_s1/`

## Compared Sources

| source | meaning |
|---|---|
| `raw_cd15` | 00278 raw `loss_exit30_cd15` internal HGB + external hybrid |
| `holdext_00290` | 00290 stateful hold-extension replay |
| `sidehorizon_00291` | 00291 side-aware fixed 720m replay |
| `entryblock_00292` | 00292 entry-block no-replacement overlay |
| `residualcombo_00293` | 00293 residual floor combo overlay |

## Default Results

Best row by source:

| source | best total | role min | month min | status | support-limited neg | shallow neg | structural neg |
|---|---:|---:|---:|---|---:|---:|---:|
| `residualcombo_00293` | `+329.4348` | `+0.5354` | `-0.7200` | `support_aware_only` | `3` | `1` | `0` |
| `entryblock_00292` | `+323.5700` | `+0.0074` | `-2.4566` | `blocked` | `4` | `0` | `1` |
| `sidehorizon_00291` | `+318.8540` | `+0.0074` | `-4.1460` | `blocked` | `5` | `0` | `1` |
| `holdext_00290` | `+250.7350` | `+0.0074` | `-6.8324` | `blocked` | `5` | `0` | `4` |
| `raw_cd15` | `+118.6900` | `+0.0074` | `-6.8324` | `blocked` | `5` | `2` | `4` |

The only default support-aware pass is:

```text
source: residualcombo_00293
variant: loss_exit30_cd15__holdext_isolated_large_loss_long_t-5_h720__entryblock_short_rollover_or_london_midloss_or_holdext_range_ny
candidate: q95_sg95_rank90_floor5_side_regime_session_month
diagnostic_status: support_aware_only
standard_pass: false
support_aware_floor_pass: true
total_pnl: +329.4348
role_total_pnl_min: +0.5354
month_pnl_min: -0.7200
negative_month_count: 4
support_limited_negative_month_count: 3
shallow_negative_month_count: 1
structural_negative_month_count: 0
strict_blockers: month_pnl_below_floor,role_trades_low,month_trades_low,side_share_high
```

This confirms that the candidate progression is not just raising total PnL. It is moving the worst-month failure type from structural losses toward sparse/thin-support residual losses.

## Sensitivity

| run | change | selected | diagnostic best status | blocker |
|---|---|---|---|---|
| default | support-limited <= `3`, shallow floor `-1.0` | `NoTrade` | `support_aware_only` | diagnostic-only |
| support2 | support-limited <= `2` | `NoTrade` | `blocked` | `too_many_support_limited_negative_months` |
| shallow025 | shallow floor `-0.25` | `NoTrade` | `blocked` | `structural_negative_months` |

The pass depends on allowing exactly three support-limited negative months and treating the `-0.7200` month as shallow. That is too fragile to promote.

## Decision

Accepted:

- support-aware classification as a cross-candidate comparison layer
- using floor-breach class progression as a signal that residual combo improved the kind of failure
- keeping `residualcombo_00293` as the current diagnostic benchmark

Rejected:

- promoting `support_aware_only` to standard policy
- relaxing support-limited negative month tolerance based on this same candidate family
- treating 1-trade / side-concentrated months as solved performance

Standard policy remains NoTrade.

## Next

1. Keep strict standard admission as the final gate.
2. Use support-aware classification in future reports to distinguish structural failure from thin-support residual failure.
3. Do not add more single-month blacklist rules to chase the remaining sparse floor breaches.
4. The next useful step is either unused chronology for the residual combo branch or a policy-level mechanism that reduces thin-support months without same-window overfitting.

## Verification

- `uv run python -m py_compile scripts/experiments/entry_ev_stateful_support_aware_admission.py tests/test_entry_ev_stateful_support_aware_admission.py`: OK
- `uv run python -m unittest tests.test_entry_ev_stateful_support_aware_admission tests.test_entry_ev_stateful_floor_meta_selector tests.test_entry_ev_overlay_residual_floor_diagnostics tests.test_docs_reports`: OK
- default progression compare run: OK
- support2 progression compare run: OK
- shallow025 progression compare run: OK
