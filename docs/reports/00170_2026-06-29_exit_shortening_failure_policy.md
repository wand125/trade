# Exit Shortening Failure Policy

日時: 2026-06-29 21:22 JST
更新日時: 2026-06-29 21:22 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- Experiment ID: `exit_shortening_high_failure_policy`
- Status: candidate, not promoted to standard policy
- Main result: `exit_shortening_high` has weak chronological OOF ranking as entry risk, but works better when connected to holding-time cap.
- Best candidate in this run: existing `stateful_p5` + `exit_shortening_high_prob >= 0.30` -> cap predicted hold to `60m`, total adjusted PnL `457.3926` on 2025-01..2025-05.

## Hypothesis

`00169` showed that trades where `oracle_holding_gap_minutes <= -30` and `exit_regret >= 5` are a large-loss bucket. The hypothesis was:

- as entry risk, high probability should suppress bad entries;
- as exit timing, high probability should shorten overlong predicted holds.

## Data

- Selected trades: fixed highcost risk5, 2024-11..2025-05.
- Prediction frame: `data/reports/modeling/20260629_fixed_highcost_wf_predictions_combined/predictions_validation_oof_plus_2025_05_apply.parquet`
- Target: `exit_shortening_high = oracle_holding_gap_minutes <= -30 and exit_regret >= 5`
- OOF scheme: chronological expanding, `min_train_months=2`
- Skipped folds: 2024-11, 2024-12
- Scored selected trades: `453` across 2025-01..2025-05

## Implementation

- Added `exit_shortening_high` to selected-trade failure targets.
- Added `--exit-shortening-gap-minutes`.
- Added `--oof-scheme expanding` and `--min-train-months` to `oof-trade-failure-model`.
- Saved fold plan information for profiled folds and fail-fast behavior when all folds are skipped.

## OOF Metrics

| scope | trades | prevalence | pred mean | bias | brier | AUC |
|---|---:|---:|---:|---:|---:|---:|
| 2025-01..05 | `453` | `0.1987` | `0.2461` | `0.0475` | `0.1623` | `0.5269` |

| holdout | fit months | trades | prevalence | pred mean | AUC | brier |
|---|---:|---:|---:|---:|---:|---:|
| 2025-01 | `2` | `67` | `0.2090` | `0.2731` | `0.5660` | `0.1713` |
| 2025-02 | `3` | `104` | `0.2212` | `0.2669` | `0.4200` | `0.1778` |
| 2025-03 | `4` | `103` | `0.1748` | `0.2452` | `0.4899` | `0.1523` |
| 2025-04 | `5` | `74` | `0.1757` | `0.2437` | `0.5404` | `0.1491` |
| 2025-05 | `6` | `105` | `0.2095` | `0.2110` | `0.5967` | `0.1604` |

Selected-trade probability bins did not show useful PnL monotonicity:

| probability bin | trades | total pnl | avg pnl | target rate | pred mean | large loss rate |
|---|---:|---:|---:|---:|---:|---:|
| `(0.111, 0.214]` | `91` | `18.2848` | `0.2009` | `0.1429` | `0.1799` | `0.0659` |
| `(0.214, 0.234]` | `92` | `133.5016` | `1.4511` | `0.2065` | `0.2247` | `0.0761` |
| `(0.234, 0.249]` | `92` | `32.7510` | `0.3560` | `0.2391` | `0.2419` | `0.0870` |
| `(0.249, 0.280]` | `87` | `21.5058` | `0.2472` | `0.2069` | `0.2629` | `0.0920` |
| `(0.280, 0.446]` | `91` | `36.2330` | `0.3982` | `0.1978` | `0.3222` | `0.0440` |

## Policy Results

Entry-risk use was not useful:

| variant | trades | total pnl | worst month | max DD |
|---|---:|---:|---:|---:|
| no_risk | `474` | `414.1398` | `-30.2776` | `249.9600` |
| stateful_p5 baseline | `452` | `405.3160` | `8.5354` | `218.4530` |
| exit_short_p5 | `435` | `268.5116` | `-27.2746` | `250.3360` |
| exit_short_p10 | `381` | `283.9166` | `-36.2110` | `259.9100` |
| exit_short_p20 | `262` | `106.0726` | `-56.4262` | `220.3140` |
| stateful + exit_short w0.2 | `448` | `354.3786` | `-0.6716` | `219.2490` |
| stateful + exit_short w0.5 | `429` | `298.6034` | `-2.5310` | `228.5660` |
| stateful + exit_short w1.0 | `398` | `150.3628` | `-36.1856` | `264.8540` |

Exit-timing use improved the fixed validation window:

| variant | trades | total pnl | worst month | max DD |
|---|---:|---:|---:|---:|
| stateful_p5 baseline | `452` | `405.3160` | `8.5354` | `218.4530` |
| cap threshold `0.25`, cap `60m` | `612` | `456.2090` | `-0.9754` | `149.2600` |
| cap threshold `0.28`, cap `60m` | `534` | `451.5832` | `10.1594` | `210.6890` |
| cap threshold `0.30`, cap `60m` | `511` | `457.3926` | `8.6094` | `210.6890` |
| cap threshold `0.30`, cap `90m` | `498` | `450.3364` | `15.9594` | `218.7290` |
| cap threshold `0.30`, cap `120m` | `486` | `438.7204` | `28.4114` | `217.3470` |
| cap threshold `0.32`, cap `60m` | `474` | `409.8536` | `8.5354` | `218.4530` |

Monthly PnL for the strongest candidate:

| month | baseline pnl | candidate pnl | baseline trades | candidate trades |
|---|---:|---:|---:|---:|
| 2025-01 | `163.5204` | `192.1208` | `67` | `95` |
| 2025-02 | `137.8984` | `135.3518` | `104` | `127` |
| 2025-03 | `70.0514` | `69.6598` | `102` | `106` |
| 2025-04 | `8.5354` | `8.6094` | `74` | `75` |
| 2025-05 | `25.3104` | `51.6508` | `105` | `108` |

## Findings

- `exit_shortening_high` is too weak and poorly monotonic to use as an entry-risk penalty.
- The same signal is more aligned with holding-time control: it can shorten trades and free the single allowed position for later entries.
- The useful region is around probability `0.28..0.30` with cap `60..90m`; `0.32` mostly collapses back to baseline.
- This is still tuned on 2025-01..2025-05, so it is not a standard policy yet.

## Artifacts

- Failure OOF: `data/reports/modeling/20260629_121119_trade_failure_exit_shortening_expanding_min2_highcost_risk5_2024_11_2025_05/`
- Combined risk parquet: `data/reports/modeling/20260629_exit_shortening_combined_risk/predictions_validation_oof_stateful_plus_exit_shortening_risk.parquet`
- Policy runs: `data/reports/backtests/20260629_exit_shortening_failure_policy/`
- Summary CSV: `data/reports/backtests/20260629_exit_shortening_failure_policy/policy_summary_by_variant.csv`

## Next Actions

- Fix `threshold=0.30`, `cap=60m` and apply to fresh months such as 2025-06..2025-08 without retuning.
- Compare against `threshold=0.28`, `cap=60m` and `threshold=0.30`, `cap=90m` as stability neighbors.
- Add trade-delta diagnostics for baseline vs cap candidate to identify whether extra entries or shortened exits drive the improvement.
- Keep entry-risk use of this target disabled unless calibration improves.
