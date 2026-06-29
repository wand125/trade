# Exit Shortening Fixed Apply 2025-06..08

日時: 2026-06-29 21:34 JST
更新日時: 2026-06-29 21:34 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- Experiment ID: `exit_shortening_fixed_apply_2025_06_08`
- Status: fixed candidate rejected
- Main result: fixed `threshold=0.30`, `cap=60m` did not fire on 2025-06..08 because final apply probability scale collapsed below the threshold.
- Baseline `stateful_p5` and fixed cap variants were identical: total adjusted PnL `276.3928`, trades `338`, worst month `56.0720`, max DD `100.2362`.
- Lower post-hoc diagnostic thresholds fired but degraded PnL, so the raw probability cap should not be adopted.

## Hypothesis

`00170` found that `exit_shortening_high` was weak as entry risk but improved 2025-01..05 when used as a holding-time cap trigger. This test fixed the best candidate, `threshold=0.30`, `cap=60m`, and applied it to fresh months 2025-06..08 without retuning.

## Data

- Training selected trades: fixed highcost risk5, 2024-11..2025-05.
- Apply months: 2025-06, 2025-07, 2025-08.
- Apply prediction source: stateful risk apply predictions for each month, concatenated into `input_apply_stateful_risk_2025_06_08.parquet`.
- Failure target: `exit_shortening_high = oracle_holding_gap_minutes <= -30 and exit_regret >= 5`.
- Policy baseline: `timed_ev`, `entry=12`, short offset `6`, side margin `5`, `stateful_p5`, loss multiplier `1.20`.

## Probability Scale

The fixed validation OOF distribution had meaningful mass above `0.30`:

| frame | side | p50 | p75 | p90 | p95 | max | rows >= 0.30 |
|---|---|---:|---:|---:|---:|---:|---:|
| validation OOF | long | `0.2299` | `0.2629` | `0.3000` | `0.3582` | `0.5314` | `21992` |
| validation OOF | short | `0.2420` | `0.2825` | `0.3065` | `0.3491` | `0.5328` | `24766` |

The final apply model did not:

| frame | side | p50 | p75 | p90 | p95 | max | rows >= 0.30 |
|---|---|---:|---:|---:|---:|---:|---:|
| apply default shrinkage | long | `0.2084` | `0.2194` | `0.2382` | `0.2439` | `0.2478` | `0` |
| apply default shrinkage | short | `0.2110` | `0.2354` | `0.2427` | `0.2478` | `0.2478` | `0` |
| apply no shrinkage diagnostic | long | `0.2046` | `0.2203` | `0.2471` | `0.2553` | `0.2608` | `0` |
| apply no shrinkage diagnostic | short | `0.2082` | `0.2430` | `0.2536` | `0.2608` | `0.2608` | `0` |

Removing `prediction_shrinkage` did not restore the validation scale. The issue is not only the 0.7 shrinkage setting; the final model/apply distribution itself is compressed.

## Policy Results

| variant | months | trades | total pnl | worst month | max DD |
|---|---:|---:|---:|---:|---:|
| stateful_p5 baseline | `3` | `338` | `276.3928` | `56.0720` | `100.2362` |
| fixed cap `0.30/60m` | `3` | `338` | `276.3928` | `56.0720` | `100.2362` |
| fixed cap `0.28/60m` | `3` | `338` | `276.3928` | `56.0720` | `100.2362` |
| fixed cap `0.30/90m` | `3` | `338` | `276.3928` | `56.0720` | `100.2362` |
| diagnostic cap `0.24/60m` | `3` | `348` | `246.7446` | `70.3238` | `90.6066` |
| diagnostic cap `0.22/60m` | `3` | `401` | `114.0804` | `-23.6882` | `84.5010` |

Monthly PnL:

| variant | 2025-06 | 2025-07 | 2025-08 |
|---|---:|---:|---:|
| stateful_p5 baseline | `129.3446` | `56.0720` | `90.9762` |
| fixed cap `0.30/60m` | `129.3446` | `56.0720` | `90.9762` |
| diagnostic cap `0.24/60m` | `95.9046` | `70.3238` | `80.5162` |
| diagnostic cap `0.22/60m` | `69.2364` | `68.5322` | `-23.6882` |

## Delta Diagnostics

`0.30/60m` had zero delta versus baseline in all three months.

For the post-hoc `0.24/60m` diagnostic:

| month | base pnl | candidate pnl | delta | key failure |
|---|---:|---:|---:|---|
| 2025-06 | `129.3446` | `95.9046` | `-33.4400` | common trades lost PnL after shortened holding, especially `long/range_normal_vol` and `short/up_normal_vol` |
| 2025-07 | `56.0720` | `70.3238` | `+14.2518` | mixed; added trades helped, but some positive base trades were blocked |
| 2025-08 | `90.9762` | `80.5162` | `-10.4600` | removed a good `long/down_low_vol` base trade and shortened common long trades |

This confirms that lowering the raw threshold is not a clean fix. It sometimes frees the position for later entries, but it also cuts profitable holds and blocks good baseline trades.

## Findings

- The fixed candidate from `00170` is rejected on fresh months because it does not activate.
- The probability-scale gap between validation OOF and final apply is large enough that raw thresholds are not robust.
- Lowering the threshold on the apply distribution is post-hoc and empirically worsens 2025-06..08.
- `exit_shortening_high` remains useful as a diagnostic target, but not as a raw probability cap trigger.

## Artifacts

- Apply input: `data/reports/modeling/20260629_exit_shortening_fixed_apply_2025_06_08/input_apply_stateful_risk_2025_06_08.parquet`
- Default apply model: `data/reports/modeling/20260629_123022_trade_failure_exit_shortening_fixed_apply_2025_06_08/`
- No-shrink diagnostic model: `data/reports/modeling/20260629_123322_trade_failure_exit_shortening_noshrink_apply_2025_06_08/`
- Policy runs: `data/reports/backtests/20260629_exit_shortening_fixed_apply_2025_06_08/`
- Policy summary: `data/reports/backtests/20260629_exit_shortening_fixed_apply_2025_06_08/policy_summary_by_variant.csv`
- Fixed delta: `data/reports/backtests/20260629_exit_shortening_fixed_apply_2025_06_08/20260629_123235_delta_stateful_vs_fixed_0p30_60/`
- Diagnostic delta: `data/reports/backtests/20260629_exit_shortening_fixed_apply_2025_06_08/20260629_123245_delta_stateful_vs_diag_0p24_60/`

## Next Actions

- Do not promote raw `exit_shortening_high` probability thresholds to the standard policy.
- If this target is reused, convert it to a calibrated or rank-based feature and verify on fresh months before connecting it to exits.
- Prefer targets closer to realized action value, such as predicted cap value or holding-error magnitude, rather than binary exit-shortening probability.
- Continue with trade-delta/error decomposition on the strong 2025-06..08 baseline to find failure modes that remain even without cap intervention.
