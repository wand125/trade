# Entry EV Residual Floor Combo Overlay

日時: 2026-07-02 13:38 JST
更新日時: 2026-07-02 13:38 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00292で残ったrefit2025 2025-03/08 floorを診断した。
- `entry_ev_stateful_entry_block_overlay.py` に residual floor向けの追加ruleを入れた。
- best side-horizon候補に、00292のshort rollover block、London short mid-loss block、hold-extension false-positive blockを合成した。
- 合成rule `short_rollover_or_london_midloss_or_holdext_range_ny` は total `+329.4348`, role min `+0.5354`, month min `-0.7200` まで改善した。
- ただしselectorはNoTrade。24件blockのno-replacement overlayであり、標準policy evidenceではない。

## Artifacts

- Updated script:
  - `scripts/experiments/entry_ev_stateful_entry_block_overlay.py`
- Updated test:
  - `tests/test_entry_ev_stateful_entry_block_overlay.py`
- Overlay run:
  - `data/reports/backtests/20260702_043727_20260702_entry_ev_stateful_entry_block_overlay_residual_combo_s1/`
- Strict selector:
  - `data/reports/backtests/20260702_043757_20260702_entry_ev_stateful_entry_block_overlay_residual_combo_selector_s1/`
- Floor-only selector:
  - `data/reports/backtests/20260702_043757_20260702_entry_ev_stateful_entry_block_overlay_residual_combo_selector_flooronly_s1/`

## Rules Added

追加した診断rule:

```text
short_london_midloss_sidegap_pos
  short
  session_regime == london
  0.30 <= selected_loss_first_prob <= 0.45
  pred_side_confidence_gap > 0

holdext_long_range_normal_ny
  hold_extension_applied
  long
  combined_regime == range_normal_vol
  session_regime == ny_overlap
  holding_minutes >= 720

short_rollover_or_london_midloss_or_holdext_range_ny
  short_rollover_lossprob_ge0p4
  OR short_london_midloss_sidegap_pos
  OR holdext_long_range_normal_ny
```

`short_london_midloss_sidegap_pos` はrefit2025 2025-03/08の残存short lossを拾うための診断。`holdext_long_range_normal_ny` は00291/00292後に残った2025-08のfixed720 false positiveを拾う診断。

## Results

Best row:

| variant | total | delta vs input | month min | role min | trades | blocked | blocked PnL |
|---|---:|---:|---:|---:|---:|---:|---:|
| `isolated_large_loss_long_t-5_h720 + combo block` | `+329.4348` | `+10.5808` | `-0.7200` | `+0.5354` | `232` | `24` | `-10.5808` |

Progression:

| stage | total | month min | role min | reading |
|---|---:|---:|---:|---|
| 00290 hold-extension threshold 5 predicted | `+250.7350` | `-6.8324` | `+0.0074` | stateful extension works but floor unchanged |
| 00291 side-aware fixed720 | `+318.8540` | `-4.1460` | `+0.0074` | long isolated-loss recall improves |
| 00292 short rollover entry block | `+323.5700` | `-2.4566` | `+0.0074` | hybrid 2025-12 fixed |
| 00293 residual combo block | `+329.4348` | `-0.7200` | `+0.5354` | refit2025 2025-03/08 mostly fixed |

Month improvements for the 00293 combo:

| role | month | after | input | delta | blocked |
|---|---|---:|---:|---:|---:|
| refit2025_validation | 2025-03 | `-0.4730` | `-2.4566` | `+1.9836` | `2` |
| refit2025_validation | 2025-08 | `0.0000` | `-2.1480` | `+2.1480` | `2` |
| hybrid2025_0912_external | 2025-12 | `+0.5700` | `-4.1460` | `+4.7160` | `1` |
| cal2024_validation | 2024-01 | `+10.0346` | `+8.4124` | `+1.6222` | `9` |
| refit2025_validation | 2025-06 | `+14.8104` | `+12.9324` | `+1.8780` | `2` |
| refit2025_validation | 2025-12 | `+14.2350` | `+12.9240` | `+1.3110` | `2` |

Remaining worst months:

| role | month | after |
|---|---|---:|
| hybrid2025_0912_external | 2025-11 | `-0.7200` |
| fresh2024_validation | 2024-11 | `-0.6120` |
| refit2025_validation | 2025-03 | `-0.4730` |
| fresh2024_validation | 2024-03 | `-0.3636` |
| hgb2025_08_external | 2025-08 | `+0.5354` |

## Selector Check

Strict selector:

```text
variant: loss_exit30_cd15__holdext_isolated_large_loss_long_t-5_h720__entryblock_short_rollover_or_london_midloss_or_holdext_range_ny
total_pnl: +329.4348
role_total_pnl_min: +0.5354
month_pnl_min: -0.7200
trade_count: 232
blockers: month_pnl_below_floor,role_trades_low,month_trades_low,side_share_high
selected: NoTrade
```

Floor-only selector:

```text
variant: loss_exit30_cd15__holdext_isolated_large_loss_long_t-5_h720__entryblock_short_rollover_or_london_midloss_or_holdext_range_ny
total_pnl: +329.4348
role_total_pnl_min: +0.5354
month_pnl_min: -0.7200
blockers: month_pnl_below_floor
selected: NoTrade
```

## Decision

Accepted:

- residual floor combo overlay diagnostics
- `short_london_midloss_sidegap_pos` and `holdext_long_range_normal_ny` as diagnostic rules

Rejected:

- standardizing the combo block now
- interpreting no-replacement block overlay as full stateful replay
- chasing remaining `-0.7200` / `-0.6120` sparse months with single-trade blacklists

Standard policy remains NoTrade.

## Next

1. Analyze remaining small negative months without immediately adding single-trade blacklists:
   - hybrid 2025-11 `-0.7200`
   - fresh2024 2024-11 `-0.6120`
   - fresh2024 2024-03 `-0.3636`
2. Promote the best diagnostic branch to full stateful replacement replay only if the rule can be justified beyond no-replacement arithmetic.
3. Check whether the remaining floor is better handled by admission support requirements rather than more blocking.

## Verification

- `uv run python -m py_compile scripts/experiments/entry_ev_stateful_entry_block_overlay.py tests/test_entry_ev_stateful_entry_block_overlay.py`: OK
- `uv run python -m unittest tests.test_entry_ev_stateful_entry_block_overlay`: OK
- residual combo overlay run: OK
- strict 00286 selector: OK
- floor-only 00286 selector: OK
