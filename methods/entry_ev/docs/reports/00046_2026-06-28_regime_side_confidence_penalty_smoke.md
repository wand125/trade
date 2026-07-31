# Regime Side Confidence Penalty Smoke

日時: 2026-06-28 17:20 JST
更新日時: 2026-06-28 17:20 JST

## Summary

- Experiment IDs:
  - `20260628_081824_model_sweep_2024-12`
  - `20260628_081949_model_sweep_2024-12`
- Status: implemented as exploration axes, not adopted
- Main result: regime-specific side-confidence penalties worsened the 2024-12 smoke. The best prior global confidence gate remained less bad.
- Report numbering note: this file is numbered from the internal `日時`, not filesystem mtime or `更新日時`.

## What Changed

Added two policy controls:

- `--side-confidence-penalty-rules`
  - syntax: `column=value+...:penalty`
  - subtracts `penalty * (1 - side_confidence)` in matching regimes

- `--side-confidence-overfit-penalty-rules`
  - syntax: `column=value+...:penalty`
  - subtracts `penalty * side_confidence` in matching regimes
  - intended for regimes where high confidence is itself overfit

Both controls are available in `model-policy`, `model-cost-sensitivity`, and `model-sweep`.

## Why

The representative OOF report showed that global calibration was not the main issue. The dangerous part was regime-local overconfidence, especially high-confidence buckets. This test checked whether regime-aware penalties can reduce those failures in the executable 2024-12 smoke.

## Data And Policy

- Predictions: `experiments/20260628_074412_best_side_confidence_smoke/predictions_test.parquet`
- Month: 2024-12
- Policy: `timed_ev`
- Entry threshold: `5`
- Short offset: `12`
- Side margin: `1`
- Profit-first threshold: `0.4`
- Max predicted hold: `720`
- Execution delay: `1`
- Spread/slippage: `0.1` / `0.05`
- Existing extra margins: `session_regime=asia:5,session_regime=rollover:5`

Rules tested:

- Low-confidence penalty:
  - `combined_regime=range_normal_vol:10`
  - `session_regime=london:10`
- High-confidence overfit penalty:
  - `combined_regime=range_normal_vol:10`
  - `session_regime=london:10`

## Results

| variant | adjusted pnl | trades | profit factor | max drawdown | long trades | short trades | worst direction/session |
|---|---:|---:|---:|---:|---:|---:|---|
| prior best global confidence gate | -109.8978 | 331 | 0.7276 | 119.9102 | 330 | 1 | `long:london` |
| regime low-confidence penalty | -222.3816 | 473 | 0.6309 | 233.7378 | 458 | 15 | `long:london` |
| regime high-confidence overfit penalty | -249.2666 | 503 | 0.6269 | 263.4316 | 488 | 15 | `long:london` |

## Findings

- Both regime-specific variants increased trade count and worsened drawdown.
- The main failure remained `long:london`, so the rule did not solve the concentration problem.
- Penalizing confidence inside unstable regimes is not enough when entry/exit selection still keeps many weak long trades.
- The overfit penalty is directionally plausible as a tool, but this smoke shows it must be validated through executable backtest and not only through classification calibration.
- The prior global confidence gate is still not adopted either, because it loses to NoTrade.

## Next Actions

- Keep both rule types as exploration axes, not standard settings.
- Prefer candidate selection gates that directly penalize bad executed trade groups, such as direction/session and direction/combined-regime loss.
- Before more side-confidence penalty tuning, check whether a side confidence signal improves an already viable candidate; do not use it to rescue a failing candidate.
- Consider calibration models that affect entry selection probability or margin, not just EV subtraction.
