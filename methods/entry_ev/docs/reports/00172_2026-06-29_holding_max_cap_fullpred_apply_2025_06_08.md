# Holding Max Cap Full-Pred Apply 2025-06..08

日時: 2026-06-29 21:53 JST
更新日時: 2026-06-29 21:53 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- Experiment ID: `holding_max_grid_fullpred_apply_2025_06_08`
- Status: fixed candidate promoted for broader chronological verification, not yet standard policy
- Main result: replacing the `stateful_p5` timed exit max predicted hold from `480m` to `240m` improved 2025-06..08 adjusted PnL from `276.3928` to `339.5826`.
- Cost stress also improved: `480m` total `170.9710`, `240m` total `215.3210`.
- The prior raw `exit_shortening_high` probability cap remains rejected. This result comes from a simple global holding cap, not from the compressed failure probability threshold.
- Important evaluation rule: monthly backtests must pass the full apply prediction frame, not only `dataset_month == target_month`, because positions opened near month end may legally exit in the next month within the 24h holding rule.

## Motivation

`00171` rejected the fixed raw `exit_shortening_high` probability cap on 2025-06..08. The follow-up holding-error decomposition showed two facts:

- `exit_shortening_target` trades were harmful in the baseline: 56 trades, total adjusted PnL `-399.9896`, average `-7.1427`.
- `hold_extension_target` trades were profitable overall: 242 trades, total adjusted PnL `+453.3604`, average `+1.8734`.

This means a binary "shorten when probability is high" rule is too brittle, but the baseline still contains long-holding tail risk. The next test therefore changed only `max_predicted_hold_minutes`, keeping the policy and predictions fixed.

## Setup

- Baseline policy: `timed_ev`, `entry=12`, short offset `6`, side margin `5`, `stateful_p5`.
- Baseline holding column: `pred_mlp_long/short_exit_event_minutes`.
- Baseline max predicted hold: `480m`.
- Evaluation months: 2025-06, 2025-07, 2025-08.
- Loss multiplier: `1.20`.
- No-cost case: spread `0.0`, slippage `0.0`, execution delay `0`.
- Cost stress case: spread `0.2`, slippage `0.1`, execution delay `1`.
- Prediction input: full apply predictions from `predictions_apply_trade_failure_model.parquet`.

The full prediction frame matters. During an initial diagnostic, filtering predictions to the target month forced signal closure at month boundary and failed to reproduce the existing baseline. Passing the full apply frame reproduced `stateful_p5` exactly: 2025-06 `129.3446`, 2025-07 `56.0720`, 2025-08 `90.9762`.

## Coarse Grid

No-cost:

| max hold | trades | total pnl | worst month | max DD | forced exits |
|---:|---:|---:|---:|---:|---:|
| `240` | `397` | `339.5826` | `65.1768` | `100.9688` | `0` |
| `1440` | `323` | `292.9736` | `35.7446` | `132.0482` | `7` |
| `960` | `323` | `280.2808` | `26.0218` | `132.0482` | `7` |
| `720` | `327` | `277.4332` | `31.8942` | `129.6362` | `6` |
| `480` | `338` | `276.3928` | `56.0720` | `100.2362` | `2` |
| `600` | `329` | `275.9014` | `35.9274` | `131.2442` | `4` |
| `360` | `351` | `179.8196` | `33.7826` | `101.6008` | `1` |

Cost stress:

| max hold | trades | total pnl | worst month | max DD | forced exits |
|---:|---:|---:|---:|---:|---:|
| `240` | `397` | `215.3210` | `0.1744` | `117.3338` | `0` |
| `1440` | `330` | `194.6394` | `-15.4322` | `141.6064` | `7` |
| `960` | `330` | `182.8594` | `-25.1222` | `141.6064` | `7` |
| `720` | `333` | `174.2648` | `-23.9038` | `139.0504` | `6` |
| `480` | `340` | `170.9710` | `-0.2572` | `110.1244` | `2` |
| `600` | `333` | `169.0946` | `-21.5572` | `142.7704` | `4` |
| `300` | `365` | `146.1932` | `-18.3764` | `129.2378` | `0` |
| `180` | `437` | `106.5146` | `8.7802` | `85.8956` | `0` |
| `360` | `352` | `72.2702` | `-16.9986` | `107.5152` | `1` |

## Fine Grid

Around the candidate:

| cost case | max hold | trades | total pnl | worst month | max DD |
|---|---:|---:|---:|---:|---:|
| no-cost | `200` | `416` | `303.4524` | `57.8738` | `102.1190` |
| no-cost | `220` | `408` | `285.1864` | `64.5320` | `99.7884` |
| no-cost | `240` | `397` | `339.5826` | `65.1768` | `100.9688` |
| no-cost | `260` | `386` | `303.9294` | `60.8726` | `106.6204` |
| no-cost | `280` | `374` | `287.9734` | `68.3446` | `112.6496` |
| cost stress | `200` | `416` | `153.3972` | `5.1994` | `115.1572` |
| cost stress | `220` | `408` | `173.8044` | `3.8050` | `108.8540` |
| cost stress | `240` | `397` | `215.3210` | `0.1744` | `117.3338` |
| cost stress | `260` | `386` | `201.5234` | `10.1308` | `123.1248` |
| cost stress | `280` | `374` | `184.8732` | `28.0618` | `120.6472` |

`240m` is the peak in this window. It is not perfectly flat, but neighboring `200m` and `260m` also beat the `480m` no-cost baseline; in cost stress, `220m`, `240m`, `260m`, and `280m` beat `480m`.

## Monthly Delta

No-cost `240m` versus `480m`:

| month | 480 pnl | 240 pnl | delta |
|---|---:|---:|---:|
| 2025-06 | `129.3446` | `208.2038` | `+78.8592` |
| 2025-07 | `56.0720` | `65.1768` | `+9.1048` |
| 2025-08 | `90.9762` | `66.2020` | `-24.7742` |

Cost stress `240m` versus `480m`:

| month | 480 pnl | 240 pnl | delta |
|---|---:|---:|---:|
| 2025-06 | `118.4894` | `198.2888` | `+79.7994` |
| 2025-07 | `-0.2572` | `0.1744` | `+0.4316` |
| 2025-08 | `52.7388` | `16.8578` | `-35.8810` |

The candidate is not uniformly better. It improves 2025-06 strongly, barely improves or modestly improves 2025-07, and worsens 2025-08. This is a fixed candidate for broader verification, not a final adoption.

## Holding-Error Comparison

Baseline `480m`:

| metric | value |
|---|---:|
| total adjusted PnL | `276.3928` |
| trades | `338` |
| exit-shortening rate | `0.1657` |
| hold-extension rate | `0.7160` |
| exit regret mean | `21.9292` |
| oracle gap mean | `492.4320` |

Candidate `240m`:

| metric | value |
|---|---:|
| total adjusted PnL | `339.5826` |
| trades | `397` |
| exit-shortening rate | `0.1486` |
| hold-extension rate | `0.7380` |
| exit regret mean | `21.7134` |
| oracle gap mean | `556.8564` |

The candidate reduces the explicit exit-shortening rate and forced exits, but it does not solve hold-extension. The improvement is likely from freeing the single-position slot sooner and avoiding harmful long-tail holds, not from a perfect exit timing model.

Direction-level effect:

| direction | baseline pnl | 240 pnl | delta |
|---|---:|---:|---:|
| long | `253.6366` | `233.8662` | `-19.7704` |
| short | `22.7562` | `105.7164` | `+82.9602` |

The main gain is short-side exposure quality. Remaining risks include `short/up_low_vol` and `long/range_low_vol`, while `short/range_normal_vol` and `short/up_normal_vol` improve materially.

## Delta Notes

No-cost candidate versus baseline:

- 2025-06 improves by `+78.8592`. It adds and reshapes trades enough to offset bad added `short/up_low_vol` exposure.
- 2025-07 improves by `+9.1048`, but candidate stateful target mean is slightly negative (`-0.1821`), so this is not a clean month.
- 2025-08 worsens by `-24.7742`; added `long/down_low_vol` exposure is a key residual failure.

Cost stress has the same pattern but harsher: 2025-08 delta is `-35.8810`.

## Findings

- A global max predicted hold cap is more robust than the raw `exit_shortening_high` probability threshold on this apply window.
- `240m` is the best tested value in both no-cost and cost-stress grids.
- The result is sensitive enough that `240m` should be treated as a fixed candidate, not as a tuned standard parameter.
- Monthly evaluation must keep post-month predictions available. Filtering predictions by target month changes exits near month-end and invalidates comparison with the 24h holding rule.
- The PnL values here are existing backtest `adjusted_pnl` units for relative strategy comparison, not a finalized real-dollar accounting model.

## Artifacts

- Baseline holding-error diagnostic: `data/reports/backtests/20260629_124055_stateful_p5_holding_error_apply_2025_06_08/`
- No-cost coarse grid: `data/reports/backtests/20260629_124947_holding_max_grid_fullpred_nocost_apply_2025_06_08/`
- Cost-stress coarse grid: `data/reports/backtests/20260629_125030_holding_max_grid_fullpred_coststress_apply_2025_06_08/`
- Fine grid: `data/reports/backtests/20260629_125118_holding_max_fine_grid_fullpred_apply_2025_06_08/`
- No-cost delta `240m` vs `480m`: `data/reports/backtests/20260629_125152_holding_max240_vs_480_delta_2025_06_08/`
- Cost-stress delta `240m` vs `480m`: `data/reports/backtests/20260629_125152_holding_max240_vs_480_delta_coststress_2025_06_08/`
- Candidate holding-error diagnostic: `data/reports/backtests/20260629_125231_stateful_p5_maxhold240_holding_error_2025_06_08/`

## Next Actions

- Fix `max_predicted_hold_minutes=240` as the next candidate and test it across broader chronological windows without retuning.
- Add a preflight check or documented protocol that monthly `model-policy` comparisons pass full prediction frames when post-month exits are allowed.
- Diagnose the 2025-08 degradation, especially added `long/down_low_vol` and short-side low-vol residual losses.
- Do not revive raw `exit_shortening_high` thresholds unless they are calibrated or rank-based and validated on fresh months.
