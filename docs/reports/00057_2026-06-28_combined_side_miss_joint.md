# Combined Side Confidence And Miss Control

日時: 2026-06-28 19:25 JST
更新日時: 2026-06-28 19:25 JST

## Summary

- Experiment ID: `combined_side_miss_joint`
- Status: validated, not promoted
- Main result: exit-event / profit-barrier / best_side probabilityを同じpolicy modelに同居させ、side-confidence制御とprofit-barrier miss制御をjoint sweepした。validation topは前回と同じ `time_exit_penalty=6`, `loss_first_penalty=6`, `time_exit_holding_shrink=0.25` で、side-confidenceやprofit-barrier miss penaltyを足さない候補だった。2024-12反証月では `min_side_confidence=0.55` を足した候補が `-91.9786` まで損失を縮めたが、NoTradeには届かない。side-confidenceは損失圧縮の補助にはなるが、標準policyには昇格しない。
- Report numbering note: this file is numbered from the internal file `日時`, not filesystem mtime or `更新日時`.

## Setup

Dataset:

- Generated: `data/processed/datasets/xauusd_m1_p1_l1p2_policy_combined/`
- Months: `2023-01` to `2025-01`
- Profit/loss multipliers: `1.0 / 1.2`
- Important change: `best_side`, exit-event targets, profit-barrier targets are present in the same monthly parquet.

Model:

- Experiment: `experiments/20260628_101740_policy_combined_side_exit_p1_l1p2/`
- Train months: `2023-01` to `2024-10`, excluding validation months and `2024-12`
- Validation months: `2024-07`, `2024-09`, `2024-11`, `2025-01`
- Test month: `2024-12`
- Target set: `policy`
- HGB: `max_iter=80`, `learning_rate=0.05`, `month_label` weighting, purge on, embargo `24h`

Side-confidence report:

- Report artifact: `data/reports/modeling/20260628_101811_combined_side_exit_side_confidence_report/`
- Overall rows: `144015`
- Accuracy: `0.4750`
- Balanced accuracy: `0.4856`
- Confidence mean: `0.5404`
- Overconfidence: `0.0654`
- High confidence share: `0.000486`

Interpretation:

- `best_side` probability is not a strong standalone signal in this combined model.
- Confidence is mildly overconfident and rarely high, so hard gating should be treated as trade-throttling, not reliable direction selection.

## Joint Sweep

Grid:

- policy: `timed_ev`
- entry threshold: `10`
- short offset: `8`
- side margin: `1`
- holding columns: `pred_long_exit_event_minutes`, `pred_short_exit_event_minutes`
- max predicted hold minutes: `480,720`
- min entry rank: `0.5`
- profit-barrier miss penalty: `0,4,8`
- time-exit penalty: `0,6`
- loss-first penalty: `0,6`
- time-exit holding shrink: `0,0.25`
- loss-first holding shrink: `0`
- side-confidence penalty: `0,4,8`
- min side confidence: `0,0.55,0.60`
- profit-barrier hard gate: disabled
- extra side margins: `session_regime=asia:5,session_regime=rollover:5`

Artifacts:

- validation sweeps: `data/reports/backtests/combined_side_miss_joint/`
- validation summary: `data/reports/backtests/20260628_combined_side_miss_joint_summary.csv`
- 2024-12 fixed diagnostics: `data/reports/backtests/combined_side_miss_joint/fixed_2024_12/`
- 2024-12 fixed summary: `data/reports/backtests/20260628_combined_side_miss_joint_2024_12_fixed.csv`

Eligibility definition:

- all 4 folds present
- each fold adjusted pnl `>= 0`
- each fold trades `>= 10`
- forced exit max `<= 0.05`
- drawdown max `<= 100`
- strict additionally requires side share max `<= 0.85` and `actual_profit_barrier_miss_rate_smoothed <= 0.55`
- `predicted_profit_barrier_miss_rate_smoothed` is diagnostic only, because it measures model-side barrier pessimism/optimism rather than realized miss.

## Validation 4fold

Strict eligible count: `45`

Basic eligible count: `99`

Top and representative rows:

| label | profit miss penalty | time penalty | loss penalty | time shrink | side penalty | min side conf | max hold | strict | min pnl | total pnl | min trades | actual miss max | predicted miss max | direction error max |
|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|
| prior combo top | `0` | `6` | `6` | `0.25` | `0` | `0.00` | `720` | `true` | `80.0648` | `513.3876` | `36` | `0.534884` | `0.928571` | `0.463415` |
| entry penalty ref | `0` | `6` | `6` | `0.00` | `0` | `0.00` | `720` | `true` | `75.1682` | `531.6246` | `36` | `0.523810` | `0.928571` | `0.425000` |
| min side confidence | `0` | `6` | `6` | `0.00` | `0` | `0.55` | `720` | `true` | `65.0410` | `375.9450` | `22` | `0.516129` | `0.964286` | `0.413793` |
| loss penalty + side penalty | `0` | `0` | `6` | `0.00` | `4` | `0.00` | `720` | `true` | `55.0364` | `520.2350` | `34` | `0.500000` | `0.923077` | `0.475000` |
| profit miss + min side conf | `4` | `0` | `0` | `0.25` | `0` | `0.60` | `480` | `true` | `41.5250` | `331.6830` | `14` | `0.480000` | `0.842105` | `0.434783` |
| no-penalty ref | `0` | `0` | `0` | `0.00` | `0` | `0.00` | `720` | `false` | `12.5636` | `287.8596` | `37` | `0.553571` | `0.962963` | `0.518519` |

Interpretation:

- validation top does not use side-confidence or profit-barrier miss penalty.
- `min_side_confidence=0.55` reduces actual miss max and direction error max slightly, but it cuts total pnl and min trades.
- profit-barrier miss penalty can reduce actual miss diagnostics, but it lowers fold minimum and trade count. It looks like a throttle, not a better signal.
- `predicted miss max` remains very high for many profitable validation candidates, so predicted miss cannot be used as a hard eligibility gate without over-filtering.

## 2024-12 Diagnostic

Fixed diagnostics:

| label | profit miss penalty | time penalty | loss penalty | time shrink | side penalty | min side conf | max hold | adjusted pnl | raw pnl | trades | profit factor | max drawdown | forced exits | actual miss smoothed | direction error |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| min side confidence | `0` | `6` | `6` | `0.00` | `0` | `0.55` | `720` | `-91.9786` | `-54.0030` | `33` | `0.5963` | `139.2716` | `2` | `0.714286` | `0.484848` |
| profit miss + min side conf | `4` | `0` | `0` | `0.25` | `0` | `0.60` | `480` | `-92.1928` | `-65.7040` | `22` | `0.4199` | `126.9888` | `3` | `0.791667` | `0.590909` |
| loss penalty + side penalty | `0` | `0` | `6` | `0.00` | `4` | `0.00` | `720` | `-126.5046` | `-76.4450` | `43` | `0.5788` | `168.7124` | `2` | `0.733333` | `0.581395` |
| prior combo top | `0` | `6` | `6` | `0.25` | `0` | `0.00` | `720` | `-159.0158` | `-103.6750` | `46` | `0.5211` | `197.5966` | `2` | `0.708333` | `0.586957` |
| no-penalty ref | `0` | `0` | `0` | `0.00` | `0` | `0.00` | `720` | `-227.4118` | `-158.4170` | `63` | `0.4507` | `246.1494` | `3` | `0.646154` | `0.539683` |

Key diagnostics:

- `min_side_confidence=0.55` improves 2024-12 from prior combo `-159.0158` to `-91.9786`, and drawdown from `197.5966` to `139.2716`.
- The same candidate has lower validation min pnl (`65.0410` vs `80.0648`) and lower total pnl (`375.9450` vs `513.3876`).
- It still loses to NoTrade and actual miss remains high (`0.714286`).
- profit-barrier miss penalty plus min side confidence also improves 2024-12 loss, but forced exits rise to `3/22`, profit factor is worse, and actual miss is even higher.

## Decision

- Rebuilding the policy dataset with `best_side` coexisting with exit-event targets succeeded.
- The combined model's best_side probability is too weak to promote as a standard hard gate or global penalty.
- `min_side_confidence=0.55` is a useful risk-reduction diagnostic because it cuts 2024-12 loss, but it is not a validated edge.
- Standard policy remains the prior exit-event penalty / holding-shrink family as a reference only, not a deployed candidate.
- Next research should use best_side as an OOF calibration diagnostic, not a direct policy gate. A separate side-confidence model or OOF calibration layer may be better than adding best_side to the already crowded policy multi-task HGB.

## Next Actions

1. Generate broader blocked OOF predictions for `best_side` on the combined production dataset.
2. Compare a separate `target-set side_confidence` model against the crowded `target-set policy` model on the same months.
3. Only re-test `min_side_confidence` after side-confidence calibration improves; do not adopt the 2024-12-improving threshold from a single反証月.
