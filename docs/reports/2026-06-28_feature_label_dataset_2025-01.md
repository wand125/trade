# Feature/Label Dataset: 2025-01

## Summary

- Experiment ID: `2026-06-28_feature_label_dataset_2025-01`
- Date: 2026-06-28 JST
- Status: completed
- Main result: leak-free M1 features and future-24h oracle-style labels were generated for 2025-01.

## Data

- Source: HistData XAUUSD M1
- Input: `data/processed/histdata/xauusd/xauusd_m1.parquet`
- Output edge1: `data/processed/datasets/xauusd_m1/xauusd_m1_2025-01_h24_edge1.parquet`
- Output edge15: `data/processed/datasets/xauusd_m1/xauusd_m1_2025-01_h24_edge15.parquet`

## Feature Set

- returns: 1, 5, 15, 60
- price difference: first and second difference
- candle shape: range, body, wicks
- gap flags
- RSI 14
- EMA 12/26 distances
- rolling stats: 15, 60, 240
- ATR-like range
- time sin/cos
- FFT 64/256 low power, high power, centroid

Feature count: 47

Output columns after multi-task target expansion: 80

## Label Definition

- decision uses current completed bar and past features.
- entry price is next M1 open.
- exit candidates are future opens up to 24 hours, including the forced-exit equivalent bar.
- long and short best adjusted pnl are computed separately.
- label chooses the direction with larger best adjusted pnl when it is above `min_adjusted_edge`.
- otherwise label is `stay_flat`.

## Label Distribution

| edge | rows | short | stay_flat | long |
|---:|---:|---:|---:|---:|
| 1 | 30,197 | 9,615 | 100 | 20,482 |
| 15 | 30,197 | 5,175 | 8,390 | 16,632 |

## Multi-Task Targets

The dataset now keeps continuous targets and quantized auxiliary targets.

Continuous targets:

- `long_best_adjusted_pnl`
- `short_best_adjusted_pnl`
- `long_forced_adjusted_pnl`
- `short_forced_adjusted_pnl`
- `long_max_adverse_pnl`
- `short_max_adverse_pnl`
- `side_score`
- `forced_side_score`
- `best_adjusted_pnl`
- `best_holding_minutes`

Quantized auxiliary targets:

- `best_adjusted_pnl_quantile`
- `side_score_quantile`
- `best_holding_time_bin`
- `long_best_holding_time_bin`
- `short_best_holding_time_bin`

For edge15, the 5-bin quantile targets are balanced by construction:

| target | bin0 | bin1 | bin2 | bin3 | bin4 |
|---|---:|---:|---:|---:|---:|
| best_adjusted_pnl_quantile | 6040 | 6039 | 6039 | 6039 | 6040 |
| side_score_quantile | 6040 | 6039 | 6039 | 6039 | 6040 |

Holding time bins for `best_holding_time_bin`:

| bin | meaning | count |
|---:|---|---:|
| 0 | <= 15 min | 51 |
| 1 | <= 60 min | 562 |
| 2 | <= 240 min | 2,191 |
| 3 | <= 720 min | 6,703 |
| 4 | <= 1440 min | 19,751 |
| 5 | > 1440 min / gap-forced equivalent | 939 |

## Notes

- edge1 is too trade-heavy for a first classification target.
- edge15 is more balanced and should be used as the first lightweight-model dataset.
- Threshold selection must be done on validation periods, not on test months.
- `label` should be treated as an auxiliary target; continuous and quantized targets should drive model selection.

## Next Actions

- Generate the same dataset for multiple months.
- Create train/validation/test split definitions.
- Train a lightweight baseline classifier before deep learning.
