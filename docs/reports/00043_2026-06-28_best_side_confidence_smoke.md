# Best Side Confidence Smoke

日時: 2026-06-28 16:48 JST
更新日時: 2026-06-28 16:48 JST

## Summary

- Experiment ID: `20260628_074412_best_side_confidence_smoke`
- Status: diagnostic only, not adopted
- Main result: `best_side` auxiliary classification and side-confidence gates are wired, but the 2024-12 smoke backtest remains negative. Best sweep result was adjusted pnl `-109.8978`, still worse than NoTrade `0.0`.
- Report numbering note: this file is numbered from the internal `日時`, not filesystem mtime or `更新日時`.

## Hypothesis

`long / short / stay_flat` に圧縮すると entry に向いている度合いや方向選択の情報を落としすぎる。そこで `label` とは別に、no-trade edgeを満たすかに関係なく long と short のどちらが相対的に有利だったかを `best_side` として学習し、`pred_best_side_prob_1` / `pred_best_side_prob_-1` をpolicy側の補助信号にする。

## Data

- Dataset: `data/processed/datasets/xauusd_m1_best_side_smoke/`
- Months: 2024-09 to 2024-12
- Train: 2024-09, 2024-10
- Validation: 2024-11
- Test: 2024-12
- PnL adjustment: profit `1.0`, loss `1.20`
- Horizon: 24h
- Edge: `min_adjusted_edge=1.5`
- Purge / embargo: enabled, 24h embargo

Rows:

| split | rows |
|---|---:|
| train | 57,855 |
| validation | 25,962 |
| test | 28,763 |

## Implementation

- `future_best_labels` now emits `best_side`.
- `build_month_dataset` stores `best_side` as an `int8` target.
- `target-set policy` and `full` include `best_side` as a classification target.
- `prediction_frame` preserves `best_side` and emits classifier probabilities such as `pred_best_side_prob_1` and `pred_best_side_prob_-1`.
- `model-policy` / `model-sweep` support:
  - `--side-confidence-penalty`
  - `--min-side-confidence`
  - `--long-side-confidence-column`
  - `--short-side-confidence-column`

## Model Metrics

`best_side` classification:

| split | accuracy | balanced accuracy | macro f1 |
|---|---:|---:|---:|
| train | 0.6673 | 0.6710 | 0.6624 |
| validation | 0.5443 | 0.5464 | 0.5393 |
| test | 0.4770 | 0.4797 | 0.4766 |

The valid score is only weakly above random, and the 2024-12 test score is below random. This is a clear regime-drift / overfitting warning.

Selection metrics in the model report still use oracle exits from target data, so they are only side-ranking diagnostics. Executable evaluation must rely on `model-sweep`.

## Backtest Smoke

Test month: 2024-12. Policy: `timed_ev`, execution delay `1`, spread `0.1`, slippage `0.05`, profit-first threshold `0.4`, max predicted hold `720`.

| side penalty | min side confidence | adjusted pnl | trades | win rate | profit factor | max drawdown | direction error | side error | actual barrier miss |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 10 | 0.55 | -109.8978 | 331 | 0.5045 | 0.7276 | 119.9102 | 0.5831 | 0.5861 | 0.5317 |
| 5 | 0.55 | -121.6732 | 336 | 0.4851 | 0.7022 | 129.8210 | 0.5804 | 0.5833 | 0.5268 |
| 0 | 0.55 | -138.2744 | 350 | 0.4714 | 0.6811 | 146.9518 | 0.5886 | 0.5886 | 0.5343 |
| 10 | 0.00 | -192.2654 | 460 | 0.4609 | 0.6650 | 202.9242 | 0.5239 | 0.5261 | 0.5261 |
| 0 | 0.00 | -220.5348 | 506 | 0.4506 | 0.6484 | 241.2352 | 0.5296 | 0.5296 | 0.5336 |

## Findings

- Side confidence can reduce bad trade volume and drawdown in this smoke, but it does not create a profitable policy.
- The best result still loses to NoTrade, so the gate is not an adoption candidate.
- `best_side` is useful as an auxiliary diagnostic target because it separates direction-choice quality from no-trade thresholding.
- The 2024-12 side classifier is below random, so any hard gate based on this probability can become regime-specific filtering unless validated with walk-forward OOF.
- The current failure remains direction error, profit barrier miss, and EV overestimate rather than a single missing threshold.

## Artifacts

- Dataset: `data/processed/datasets/xauusd_m1_best_side_smoke/`
- Model: `experiments/20260628_074412_best_side_confidence_smoke/`
- Sweep: `data/reports/backtests/20260628_074450_model_sweep_2024-12/`

## Next Actions

- Regenerate the broader production dataset with `best_side` after confirming the target contract.
- Train/evaluate `best_side` with month-balanced or walk-forward OOF predictions before using it as a hard gate.
- Treat side confidence as a calibration/diagnostic signal first, not as a standalone policy selector.
- Continue toward side/entry calibration and expected PnL calibration with explicit out-of-sample checks.
