# Holding Cap Sweep

日時: 2026-06-28 16:05 JST
更新日時: 2026-06-28 16:05 JST

## Summary

- Experiment ID: `holding_cap_sweep`
- Status: implemented and validated on the 4 validation folds; not yet promoted to blind-tested candidate
- Main result: `max_predicted_hold_minutes` を `model-sweep` の探索軸とcandidate keyへ追加すると、前回0件だったstrict `max_forced_exit_rate=0.05` 条件でeligible候補が20件残った。
- Best strict candidate: `entry_threshold=10`, `short_entry_threshold_offset=8`, `profit_barrier_threshold=0.4`, `max_predicted_hold_minutes=720`
- Best strict candidate score: cost-aware min adjusted pnl `84.7072`, min trades `32`, max forced exit rate `0.028571`, max drawdown `80.4432`
- Report numbering note: this file is numbered by the internal `日時`, not by file update time or `更新日時`.

## Setup

Validation folds:

- `2024-07`
- `2024-09`
- `2024-11`
- `2025-01`

Model:

- predictions: `experiments/20260628_064332_policy_exit_event_prob_p1_l1p2/predictions_valid.parquet`
- policy: `timed_ev`
- holding columns: `pred_long_exit_event_minutes`, `pred_short_exit_event_minutes`
- profit-first gate columns: `pred_long_exit_event_prob_1`, `pred_short_exit_event_prob_1`

Grid:

- `entry_threshold`: `0,5,10`
- `short_entry_threshold_offset`: `8,12,16,20`
- `min_entry_rank`: `0.5`
- `profit_barrier_threshold`: `0.4,0.5`
- `max_predicted_hold_minutes`: `240,480,720,960,1200,1440`
- `extra_side_margin_rules`: `session_regime=asia:5,session_regime=rollover:5`

Selection gates:

- `min_folds=4`
- `min_trades_per_fold=10`
- `max_forced_exit_rate=0.05`
- `max_drawdown=100`
- `min_base_adjusted_pnl_per_fold=0`
- `min_cost_adjusted_pnl_per_fold=0`
- `max_direction_session_loss_per_fold=60`
- `max_short_trade_share=0.65`
- `max_smoothed_actual_profit_barrier_miss_rate=0.55`
- plateau diagnostic: `plateau_column=max_predicted_hold_minutes`, `plateau_radius=240`, `min_plateau_neighbors=0`

## Implementation

`model-sweep` now treats predicted holding limits as grid values:

- `--min-predicted-hold-minutes` and `--max-predicted-hold-minutes` accept CSV floats in `model-sweep`.
- `min_predicted_hold_minutes` and `max_predicted_hold_minutes` are included in `SWEEP_KEY_COLUMNS`.
- Old sweep metrics without these columns are normalized to defaults `1.0` and `1440.0`.
- Validation rejects `max_predicted_hold_minutes < min_predicted_hold_minutes`.

This is important because otherwise cap `720` and cap `1440` can be aggregated as the same candidate during fold selection.

## Strict Candidate Selection

Artifacts:

- no-cost sweeps: `data/reports/backtests/20260628_065828_model_sweep_2024-07/`, `...2024-09/`, `...2024-11/`, `...2025-01/`
- cost-aware sweeps: `data/reports/backtests/20260628_065950_model_sweep_2024-07/`, `...2024-09/`, `...2024-11/`, `...2025-01/`
- strict candidate selection: `data/reports/backtests/20260628_070227_model_candidate_selection/`
- 10% forced-exit diagnostic: `data/reports/backtests/20260628_070240_model_candidate_selection/`

Candidate counts:

| selection | rows | eligible | pre-plateau eligible | base eligible | cost eligible |
|---|---:|---:|---:|---:|---:|
| strict forced exit `0.05` | `144` | `20` | `20` | `51` | `44` |
| diagnostic forced exit `0.10` | `144` | `29` | `29` | `73` | `66` |

Strict top candidates:

| entry | short offset | profit threshold | max hold min | cost min pnl | base min pnl | min trades | forced max | max drawdown | smoothed miss max | plateau support |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `10` | `8` | `0.4` | `720` | `84.7072` | `92.2774` | `32` | `0.028571` | `80.4432` | `0.540541` | `1` |
| `5` | `12` | `0.4` | `720` | `60.0750` | `69.1370` | `32` | `0.024390` | `78.4708` | `0.534884` | `1` |
| `10` | `12` | `0.4` | `720` | `59.1674` | `64.8674` | `27` | `0.033333` | `82.6654` | `0.468750` | `0` |
| `10` | `8` | `0.4` | `480` | `51.6754` | `58.8754` | `34` | `0.000000` | `74.4050` | `0.513514` | `1` |
| `0` | `16` | `0.4` | `720` | `45.2132` | `55.2132` | `35` | `0.044444` | `85.4222` | `0.531915` | `1` |

Plateau support:

| selection | eligible | support `0` | support `1` | support `2` |
|---|---:|---:|---:|---:|
| strict forced exit `0.05` | `20` | `6` | `12` | `2` |
| diagnostic forced exit `0.10` | `29` | `5` | `14` | `10` |

Interpretation:

- strict候補は復活したが、plateauはまだ強くない。
- top candidateはcap `480` と `720` の近傍で残るため、完全な一点最適ではない。
- cap `960` 以上はPnLを大きく改善せず、forced exitだけを増やす。

## Cap Sensitivity

Same setting except `max_predicted_hold_minutes`:

| max hold min | strict eligible | cost min pnl | min trades | forced max | max drawdown | smoothed miss max |
|---:|---:|---:|---:|---:|---:|---:|
| `240` | `false` | `-5.8696` | `45` | `0.000000` | `87.4118` | `0.528302` |
| `480` | `true` | `51.6754` | `34` | `0.000000` | `74.4050` | `0.513514` |
| `720` | `true` | `84.7072` | `32` | `0.028571` | `80.4432` | `0.540541` |
| `960` | diagnostic only | `83.8434` | `29` | `0.093750` | `83.4500` | `0.514286` |
| `1200` | `false` | `75.8344` | `29` | `0.125000` | `83.4500` | `0.514286` |
| `1440` | `false` | `75.8344` | `29` | `0.125000` | `83.4500` | `0.514286` |

The useful range is `480` to `720`. `720` keeps the PnL advantage while staying inside forced-exit risk.

## Best Candidate Fold Details

Cost-aware, delay `0`:

| fold | adjusted pnl | trades | forced rate | max drawdown | worst direction/session pnl | short share | smoothed miss |
|---|---:|---:|---:|---:|---:|---:|---:|
| `2024-07` | `151.2868` | `32` | `0.000000` | `59.5340` | `-39.0570` | `0.187500` | `0.411765` |
| `2024-09` | `98.1128` | `32` | `0.000000` | `44.3364` | `-36.6766` | `0.312500` | `0.382353` |
| `2024-11` | `87.6574` | `35` | `0.028571` | `63.3042` | `-11.6100` | `0.542857` | `0.486486` |
| `2025-01` | `84.7072` | `35` | `0.028571` | `80.4432` | `-10.1952` | `0.285714` | `0.540541` |

Delay `1` fixed diagnostic, same candidate:

| fold | adjusted pnl | trades | forced rate | max drawdown | worst direction/session pnl | smoothed miss |
|---|---:|---:|---:|---:|---:|---:|
| `2024-07` | `159.7828` | `32` | `0.000000` | `57.7932` | `-39.1058` | `0.411765` |
| `2024-09` | `100.1970` | `32` | `0.000000` | `46.7640` | `-33.9726` | `0.382353` |
| `2024-11` | `86.4062` | `36` | `0.027778` | `62.6300` | `-11.2400` | `0.473684` |
| `2025-01` | `75.1692` | `36` | `0.027778` | `83.4264` | `-12.9204` | `0.552632` |

Delay `1` summary:

- min adjusted pnl: `75.1692`
- min trades: `32`
- max forced exit rate: `0.027778`
- max drawdown: `83.4264`
- max smoothed actual profit-barrier miss: `0.552632`

Delay `1` does not destroy the candidate, but the smoothed miss gate would need attention because it slightly exceeds `0.55`. Do not promote delay `1` as fully selected until the full grid is evaluated under delay `1`.

## Decision

- Promote holding cap from idea to active selection axis.
- Keep strict `max_forced_exit_rate=0.05`; the cap solves enough of the forced-exit issue without relaxing the risk rule.
- Do not yet promote the best candidate to final strategy, because it is still validation-selected and has not been blind-tested.
- Use this as the next fixed candidate for blind or forward-style checks:
  - `policy=timed_ev`
  - `entry_threshold=10`
  - `short_entry_threshold_offset=8`
  - `side_margin=1`
  - `min_entry_rank=0.5`
  - `profit_barrier_threshold=0.4`
  - `max_predicted_hold_minutes=720`
  - `extra_side_margin_rules=session_regime=asia:5,session_regime=rollover:5`

## Next Actions

1. Run the fixed candidate on an unused blind month, not by reselecting thresholds.
2. Run full-grid cost-aware candidate selection with `execution_delay_bars=1` before making delay a standard gate.
3. Keep `max_predicted_hold_minutes` in all future candidate keys.
4. Compare holding cap against time-exit probability penalty and hazard/survival exit policy.

## Verification

- `python3 -m py_compile src/trade_data/backtest.py`: OK
- `python3 -m unittest tests.test_backtest`: OK
- `python3 -m unittest tests.test_docs_reports`: OK
- `python3 -m unittest discover tests`: OK
- `git diff --check`: OK
