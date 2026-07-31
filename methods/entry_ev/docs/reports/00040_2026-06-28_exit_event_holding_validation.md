# Exit Event Holding Validation

日時: 2026-06-28 15:50 JST
更新日時: 2026-06-28 15:50 JST

## Summary

- Experiment ID: `exit_event_holding_validation`
- Status: implemented and validated; not promoted to strict production candidate
- Main result: `pred_*_exit_event_minutes` は従来の `pred_*_best_holding_minutes` よりvalidation foldのPnL台地を押し上げた。一方で、strict gateの `max_forced_exit_rate=0.05` では採用候補は0件。多クラス `exit_event` のprofit-first probabilityを出力し、gateとして使うとbarrier missは改善したが、5% forced-exit基準ではまだ落ちる。診断として10% forced-exitまで緩めると2候補が残った。
- Report numbering note: this file is numbered by the internal `日時`, not by file update time or `更新日時`.

## Setup

Validation folds:

- `2024-07`
- `2024-09`
- `2024-11`
- `2025-01`

Training:

- Dataset: `data/processed/datasets/xauusd_m1_p1_l1p2_exit_event/`
- Profit multiplier: `1.0`
- Loss multiplier: `1.20`
- HGB config: same as report `00033`, `max_iter=80`, `target_set=policy`, purge enabled, embargo `24h`

Model artifacts:

- first exit-event model: `experiments/20260628_063308_policy_exit_event_p1_l1p2/`
- multiclass probability model: `experiments/20260628_064332_policy_exit_event_prob_p1_l1p2/`

Code change:

- `evaluate_models` now preserves binary `pred_<target>_prob` and also writes class-specific `pred_<target>_prob_<class>` for all classifiers.
- This exposes `pred_long_exit_event_prob_1` / `pred_short_exit_event_prob_1`, where class `1` means `profit_first`.

## Model Metrics

Validation metrics from `experiments/20260628_064332_policy_exit_event_prob_p1_l1p2/`:

| target | split | metric | value |
|---|---|---:|---:|
| `long_exit_event_minutes` | valid | R2 | `0.384815` |
| `short_exit_event_minutes` | valid | R2 | `0.401334` |
| `long_best_holding_minutes` | valid | R2 | `0.111177` |
| `short_best_holding_minutes` | valid | R2 | `-0.080884` |
| `long_exit_event` | valid | balanced accuracy | `0.465838` |
| `short_exit_event` | valid | balanced accuracy | `0.473513` |

Interpretation:

- event minutes regression is materially easier than best holding minutes regression.
- event class prediction remains weak, so class probability should be treated as a noisy quality gate, not as a direct trading signal.

## Holding Column Comparison

Strict selection gate:

- `min_folds=4`
- `min_trades_per_fold=10`
- `max_forced_exit_rate=0.05`
- `max_drawdown=100`
- `min_base_adjusted_pnl_per_fold=0`
- `min_cost_adjusted_pnl_per_fold=0`
- `max_direction_session_loss_per_fold=60`
- `max_short_trade_share=0.65`
- `max_smoothed_actual_profit_barrier_miss_rate=0.55`

| variant | candidate selection | eligible | best cost min pnl | key failure |
|---|---|---:|---:|---|
| best holding minutes + old profit-barrier prob | `data/reports/backtests/20260628_063841_model_candidate_selection/` | `0` | `30.2476` | smoothed actual barrier miss `0.551020` just above gate |
| exit-event minutes + old profit-barrier prob | `data/reports/backtests/20260628_063856_model_candidate_selection/` | `0` | `59.5464` | forced exit rate `0.097561` |
| exit-event minutes + exit-event profit prob | `data/reports/backtests/20260628_064600_model_candidate_selection/` | `0` | `75.8344` | forced exit rate `0.125000` |
| exit-event minutes + exit-event profit prob + short offset 8..20 | `data/reports/backtests/20260628_064844_model_candidate_selection/` | `0` | `75.8344` | forced exit rate `0.125000` |

Important distinction:

- The raw top-min PnL improved from `30.2476` to `75.8344`.
- The strict gate did its job: it rejects the improvement because it relies on more time-expiring positions than we currently allow.

## Forced Exit Sensitivity

For diagnosis only, the final grid was rerun with `max_forced_exit_rate=0.10`.

Artifact:

- `data/reports/backtests/20260628_065005_model_candidate_selection/`

Eligible candidates:

| entry | short offset | min entry rank | profit-first prob threshold | cost min pnl | base min pnl | min trades | forced exit max | short share max | smoothed miss max |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `5` | `12` | `0.5` | `0.4` | `56.6182` | `64.7382` | `29` | `0.081081` | `0.540541` | `0.538462` |
| `0` | `16` | `0.5` | `0.4` | `53.2866` | `62.3286` | `32` | `0.055556` | `0.550000` | `0.534884` |

This is not adopted as the standard gate. It shows that exit-event probability is useful, but the current policy still holds too close to the 24h boundary.

## Decision

- Do not promote exit-event holding to the strict standard candidate yet.
- Keep `pred_*_exit_event_minutes` and `pred_*_exit_event_prob_1` as live research signals.
- Keep strict `max_forced_exit_rate=0.05` for candidate adoption unless a later report explicitly changes the risk policy.
- Next improvement should reduce time-expiry risk directly:
  - cap predicted holding more aggressively,
  - add a time-exit probability penalty,
  - or train a hazard/survival-style exit policy instead of predicting only a single holding minute.

## Artifacts

- full target dataset:
  - `data/processed/datasets/xauusd_m1_p1_l1p2_exit_event/`
- model with class-specific probabilities:
  - `experiments/20260628_064332_policy_exit_event_prob_p1_l1p2/`
- baseline holding candidate selection:
  - `data/reports/backtests/20260628_063841_model_candidate_selection/`
- exit-event holding candidate selection:
  - `data/reports/backtests/20260628_063856_model_candidate_selection/`
- exit-event probability gate:
  - `data/reports/backtests/20260628_064600_model_candidate_selection/`
- short offset expansion, strict 5% forced exit:
  - `data/reports/backtests/20260628_064844_model_candidate_selection/`
- short offset expansion, diagnostic 10% forced exit:
  - `data/reports/backtests/20260628_065005_model_candidate_selection/`

## Verification

- `python3 -m unittest tests.test_modeling`: OK
