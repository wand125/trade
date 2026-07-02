# Entry EV Hold Extension Side Horizon Replay

日時: 2026-07-02 13:12 JST
更新日時: 2026-07-02 13:12 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00290で残った2025-09/2025-06 isolated large-loss longのrecall不足に対し、side-aware fixed-horizon replayを追加した。
- `scripts/experiments/entry_ev_hold_extension_stateful_replay.py` に `--horizon-modes` と universe side suffix (`isolated_large_loss_long` など) を追加した。
- predicted best horizonではなく、long isolated large-lossだけをfixed 720mへ延長する診断を実施した。
- bestは `isolated_large_loss_long`, threshold `-5`, horizon `720`。stateful total `+318.8540`, delta vs base `+200.1640`, month min `-4.1460`。
- ただしselectorはNoTrade。残るworstはhybrid 2025-12 short `-4.1460` で、extension targetでは `target_best_delta=0.0`。hold-extensionでは直せない損失に移った。

## Artifacts

- Updated script:
  - `scripts/experiments/entry_ev_hold_extension_stateful_replay.py`
- Updated test:
  - `tests/test_entry_ev_hold_extension_stateful_replay.py`
- Replay:
  - `data/reports/backtests/20260702_041059_20260702_entry_ev_hold_extension_side_horizon_replay_s1/`
- Strict selector:
  - `data/reports/backtests/20260702_041151_20260702_entry_ev_hold_extension_side_horizon_selector_s1/`
- Floor-only selector:
  - `data/reports/backtests/20260702_041151_20260702_entry_ev_hold_extension_side_horizon_selector_flooronly_s1/`

## Why

00290で、2025-09/2025-06には実際にfixed horizonで大きく改善するlong lossがあるのに、predicted best deltaがthreshold未満でflagされないことが分かった。

追加確認では、2025-09の主要2件はこうだった。

| month | side | PnL | true best delta | predicted best | predicted best horizon | key issue |
|---|---|---:|---:|---:|---:|---|
| 2025-09 | long | `-3.4680` | `+32.3510` | `+0.1408` | `60` | predicted 720 delta is negative, but actual 720 is strong |
| 2025-09 | long | `-2.4324` | `+6.9124` | `+0.9040` | `60` | actual best is 240, predicted 60 is harmful |
| 2025-06 | long | `-2.6760` | `+19.4460` | `+4.8980` | `720` | just below threshold 5 |

This means the miss is not only threshold calibration. It is also horizon-head error.

## Method

New replay dimensions:

```text
apply_universe:
  isolated_large_loss
  isolated_large_loss_long

threshold:
  -5, 0, 1, 5

horizon_mode:
  predicted
  720
```

For `horizon_mode=predicted`, threshold is applied to `pred_hold_extension_best_delta`.

For `horizon_mode=720`, threshold is applied to `pred_hold_extension_delta_720m`, and the trade is extended to fixed 720m if the threshold passes.

The `-5` threshold is a diagnostic recall setting. It does not use future PnL, but it intentionally allows weakly negative predicted 720m delta when the row is an isolated large-loss long.

## Results

Top stateful rows:

| apply universe | threshold | horizon | total | delta vs base | month min | role min | extended | skipped | skipped PnL |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|
| isolated_large_loss_long | `-5` | `720` | `+318.8540` | `+200.1640` | `-4.1460` | `+0.0074` | `10` | `10` | `-1.7520` |
| isolated_large_loss_long | `1` | `720` | `+285.6370` | `+166.9470` | `-6.8324` | `+0.0074` | `7` | `8` | `-3.9820` |
| isolated_large_loss_long | `0` | `720` | `+285.2070` | `+166.5170` | `-6.8324` | `+0.0074` | `8` | `9` | `-3.2520` |
| isolated_large_loss | `5` | `predicted` | `+250.7350` | `+132.0450` | `-6.8324` | `+0.0074` | `7` | `8` | `-3.9820` |
| isolated_large_loss | `-5` | `predicted` | `+306.6284` | `+187.9384` | `-23.4696` | `+0.0074` | `20` | `14` | `-10.4544` |
| isolated_large_loss | `-5` | `720` | `+170.5374` | `+51.8474` | `-112.1634` | `+0.0074` | `21` | `20` | `-0.2204` |

Reading:

- Side-awareness is essential. Applying low threshold or fixed 720 to all isolated large-loss rows destroys the floor.
- Long-only fixed 720 picks up the 2025-09/2025-06 missed long losses and improves the floor from `-6.8324` to `-4.1460`.
- The remaining worst month is no longer internal refit2025 2025-09; it is hybrid 2025-12.

## Selector Check

Strict selector for the best side-horizon candidate:

```text
variant: loss_exit30_cd15__holdext_isolated_large_loss_long_t-5_h720
total_pnl: +318.8540
role_total_pnl_min: +0.0074
month_pnl_min: -4.1460
trade_count: 256
blockers: month_pnl_below_floor,role_trades_low,side_share_high
selected: NoTrade
```

Floor-only selector:

```text
variant: loss_exit30_cd15__holdext_isolated_large_loss_long_t-5_h720
total_pnl: +318.8540
role_total_pnl_min: +0.0074
month_pnl_min: -4.1460
blockers: month_pnl_below_floor
selected: NoTrade
```

## Remaining Worst Months

For the best side-horizon candidate:

| source / role | month | after | base | delta | extended | skipped | reading |
|---|---:|---:|---:|---:|---:|---:|---|
| hybrid 2025-09..12 | 2025-12 | `-4.1460` | `-4.1460` | `0.0000` | `0` | `0` | extension cannot help |
| internal refit2025 | 2025-03 | `-2.4566` | `-2.4566` | `0.0000` | `0` | `0` | separate issue |
| internal refit2025 | 2025-08 | `-2.1480` | `-3.0500` | `+0.9020` | `1` | `1` | small improvement |
| hybrid 2025-09..12 | 2025-11 | `-0.7200` | `-0.7200` | `0.0000` | `0` | `0` | support too thin |

The 2025-12 hybrid short loss had `target_best_delta=0.0` in 00290. It is not a hold-extension opportunity.

## Decision

Accepted:

- side suffix apply universes for hold-extension replay
- fixed horizon modes in stateful replay
- long-only fixed 720 diagnostic line as a stronger candidate than 00290

Rejected:

- lowering threshold globally for all isolated large-loss rows
- fixed 720 for all isolated large-loss rows
- standardizing the long-only fixed 720 candidate while month floor is still negative

Standard policy remains NoTrade.

## Next

1. Move from hold-extension to the residual hybrid 2025-12 short loss:
   - entry/no-entry, early stop, or short-side block diagnostics.
   - Do not try to force extension when target best delta is `0.0`.
2. Keep `isolated_large_loss_long + fixed720 + threshold -5` as a diagnostic branch, not standard policy.
3. Combine only after the residual short-loss branch is independently justified and stateful selector passes.

## Verification

- `uv run python -m py_compile scripts/experiments/entry_ev_hold_extension_stateful_replay.py tests/test_entry_ev_hold_extension_stateful_replay.py`: OK
- `uv run python -m unittest tests.test_entry_ev_hold_extension_stateful_replay`: OK
- side-aware fixed-horizon replay: OK
- strict 00286 selector: OK
- floor-only 00286 selector: OK
