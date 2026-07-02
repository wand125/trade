# Entry EV Stateful Entry Block Overlay

日時: 2026-07-02 13:26 JST
更新日時: 2026-07-02 13:26 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00291で残ったhybrid 2025-12 short lossを、entry/no-entry側から診断した。
- `scripts/experiments/entry_ev_stateful_entry_block_overlay.py` を追加し、既存stateful trade pathに観測可能featureをjoinして、entry block ruleをno-replacement overlayとして月次/selector形式へ戻せるようにした。
- best side-horizon candidate `isolated_large_loss_long + fixed720 + threshold -5` に狭いshort rollover blockを重ねると、problem trade 1件だけを除去し、total `+318.8540 -> +323.5700`, month min `-4.1460 -> -2.4566` へ改善した。
- ただしselectorはまだNoTrade。改善は1件だけで、標準policyにするには弱い。

## Artifacts

- Added script:
  - `scripts/experiments/entry_ev_stateful_entry_block_overlay.py`
- Added test:
  - `tests/test_entry_ev_stateful_entry_block_overlay.py`
- Overlay run:
  - `data/reports/backtests/20260702_042547_20260702_entry_ev_stateful_entry_block_overlay_s1/`
- Strict selector:
  - `data/reports/backtests/20260702_042614_20260702_entry_ev_stateful_entry_block_overlay_selector_s1/`
- Floor-only selector:
  - `data/reports/backtests/20260702_042614_20260702_entry_ev_stateful_entry_block_overlay_selector_flooronly_s1/`

## Focus Trade

00291のbest candidateで残ったworstはhybrid 2025-12だった。

```text
direction: short
entry: 2025-12-07 23:15 UTC
exit: 2025-12-07 23:36 UTC
adjusted_pnl: -4.7160
context: down_high_vol / rollover
selected_loss_first_prob: 0.440477
pred_side_confidence_gap: -0.028502
pred_taken_entry_local_rank: 0.467618
selected_fixed_60m_pred_pnl: +0.909509
selected_fixed_60m_actual_pnl: -12.7440
```

The trade was already cut by `loss_exit30_cd15` after 21 minutes. Fixed 60m would have made it worse. The M1 path around the entry also has sparse rollover/gap behavior, so the useful diagnostic is not hold-extension. It is either entry suppression or a more explicit gap/rollover risk feature.

## Method

The overlay is deliberately diagnostic:

```text
input stateful path
  -> join observable trade features by source/role/family/variant/candidate/month/direction/entry_timestamp
  -> apply entry block rule
  -> remove flagged trades without replacement
  -> recompute monthly metrics
  -> feed monthly metrics to 00286 selector
```

This is not a full stateful replacement replay. If blocking a trade would free capital and allow a different skipped trade, that replacement is not added. For the focus trade, this caveat is acceptable for diagnosis because the next hybrid 2025-12 trade occurs later and was already present in the path.

Rules tested:

```text
none
short_rollover_lossprob_ge0p4
short_rollover_sidegap_neg
short_rollover_sidegap_neg_lossprob_ge0p4
short_down_high_vol_rollover
short_down_high_vol_rollover_lossprob_ge0p4
short_rollover_entry_rank_lt0p5
short_entry_hour_23_lossprob_ge0p4
```

## Results

For `isolated_large_loss_long + fixed720 + threshold -5`, all narrow focus rules selected the same single trade.

| entry block rule | total | delta vs input | month min | role min | trades | blocked | blocked PnL |
|---|---:|---:|---:|---:|---:|---:|---:|
| none | `+318.8540` | `0.0000` | `-4.1460` | `+0.0074` | `256` | `0` | `0.0000` |
| short_rollover_lossprob_ge0p4 | `+323.5700` | `+4.7160` | `-2.4566` | `+0.0074` | `255` | `1` | `-4.7160` |
| short_rollover_sidegap_neg | `+323.5700` | `+4.7160` | `-2.4566` | `+0.0074` | `255` | `1` | `-4.7160` |
| short_down_high_vol_rollover | `+323.5700` | `+4.7160` | `-2.4566` | `+0.0074` | `255` | `1` | `-4.7160` |
| short_entry_hour_23_lossprob_ge0p4 | `+323.5700` | `+4.7160` | `-2.4566` | `+0.0074` | `255` | `1` | `-4.7160` |

Blocked trade:

| role | month | direction | entry | adjusted PnL | context | loss-first | side gap |
|---|---|---|---|---:|---|---:|---:|
| hybrid2025_0912_external | 2025-12 | short | 2025-12-07 23:15 UTC | `-4.7160` | down_high_vol / rollover | `0.440477` | `-0.028502` |

After blocking it, hybrid 2025-12 improves from `-4.1460` to `+0.5700`.

Remaining worst months:

| role | month | after | input | delta | blocked |
|---|---|---:|---:|---:|---:|
| refit2025_validation | 2025-03 | `-2.4566` | `-2.4566` | `0.0000` | `0` |
| refit2025_validation | 2025-08 | `-2.1480` | `-2.1480` | `0.0000` | `0` |
| hybrid2025_0912_external | 2025-11 | `-0.7200` | `-0.7200` | `0.0000` | `0` |
| fresh2024_validation | 2024-11 | `-0.6120` | `-0.6120` | `0.0000` | `0` |
| fresh2024_validation | 2024-03 | `-0.3636` | `-0.3636` | `0.0000` | `0` |

## Selector Check

Strict selector best:

```text
variant: loss_exit30_cd15__holdext_isolated_large_loss_long_t-5_h720__entryblock_short_rollover_lossprob_ge0p4
total_pnl: +323.5700
role_total_pnl_min: +0.0074
month_pnl_min: -2.4566
trade_count: 255
blockers: month_pnl_below_floor,role_trades_low,side_share_high
selected: NoTrade
```

Floor-only selector:

```text
variant: loss_exit30_cd15__holdext_isolated_large_loss_long_t-5_h720__entryblock_short_rollover_lossprob_ge0p4
total_pnl: +323.5700
role_total_pnl_min: +0.0074
month_pnl_min: -2.4566
blockers: month_pnl_below_floor
selected: NoTrade
```

## Decision

Accepted:

- stateful entry-block no-replacement overlay infrastructure
- short rollover loss-first / side-gap / down-high-vol rules as diagnostics for this specific failure mode

Rejected:

- standardizing any of these rules now
- interpreting a 1-trade block as robust policy evidence
- treating the no-replacement overlay as full stateful replacement replay

Standard policy remains NoTrade.

## Next

1. Move to remaining worst months: refit2025 2025-03 `-2.4566` and 2025-08 `-2.1480`.
2. Check whether those are also sparse isolated failures or whether they share a broader observable pattern.
3. If a block/exit rule remains useful, promote it from no-replacement overlay to full stateful replay before any policy claim.

## Verification

- `uv run python -m py_compile scripts/experiments/entry_ev_stateful_entry_block_overlay.py tests/test_entry_ev_stateful_entry_block_overlay.py`: OK
- `uv run python -m unittest tests.test_entry_ev_stateful_entry_block_overlay`: OK
- entry block overlay run: OK
- strict 00286 selector: OK
- floor-only 00286 selector: OK
