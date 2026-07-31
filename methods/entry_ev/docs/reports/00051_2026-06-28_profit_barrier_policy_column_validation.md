# Profit Barrier Policy Column Validation

日時: 2026-06-28 18:06 JST
更新日時: 2026-06-28 18:06 JST

## Summary

- Experiment ID: `profit_barrier_policy_column_validation`
- Status: diagnosed and rejected for promotion
- Main result: raw profit-barrier probabilityだけがvalidation gridでbasic gateを満たしたが、2024-12 holdoutで大きく崩れた。calibrated/lower列はvalidation内で2024-11がマイナスになり、2024-12でもrawより悪化した。
- Report numbering note: this file is numbered from the internal file `日時`, not filesystem mtime or `更新日時`.

## Setup

Model:

- base predictions: `experiments/20260628_064332_policy_exit_event_prob_p1_l1p2/`
- valid months: `2024-07`, `2024-09`, `2024-11`, `2025-01`
- holdout diagnostic: `2024-12`

Calibration artifacts:

- valid month-OOF calibration: `data/reports/modeling/20260628_090051_policy_valid_month_oof_profit_barrier_calibration/`
- valid-fit/test-apply calibration: `data/reports/modeling/20260628_090105_policy_valid_fit_test_profit_barrier_calibration/`

Policy grid:

- policy: `timed_ev`
- holding columns: `pred_long_exit_event_minutes`, `pred_short_exit_event_minutes`
- entry threshold: `5,10`
- short offset: `8,12`
- side margin: `1`
- min entry rank: `0.5`
- profit-barrier threshold: `0.35,0.40,0.45,0.50`
- max predicted hold minutes: `480,720`
- extra side margins: `session_regime=asia:5,session_regime=rollover:5`

Compared columns:

| variant | long column | short column |
|---|---|---|
| raw | `pred_long_profit_barrier_hit_prob_1` | `pred_short_profit_barrier_hit_prob_1` |
| calibrated | `pred_long_profit_barrier_hit_calibrated_prob` | `pred_short_profit_barrier_hit_calibrated_prob` |
| lower | `pred_long_profit_barrier_hit_calibrated_prob_lower` | `pred_short_profit_barrier_hit_calibrated_prob_lower` |

## Calibration Check

Policy valid, month-OOF:

| probability | actual hit | predicted mean | calibration error | Brier | threshold accuracy |
|---|---:|---:|---:|---:|---:|
| raw | `0.3745` | `0.3299` | `-0.0445` | `0.2270` | `0.6205` |
| calibrated | `0.3745` | `0.3743` | `-0.0002` | `0.2191` | `0.6142` |
| lower | `0.3745` | `0.3720` | `-0.0025` | `0.2191` | `0.6189` |

Policy test 2024-12, fitted on all valid:

| probability | actual hit | predicted mean | calibration error | Brier | threshold accuracy |
|---|---:|---:|---:|---:|---:|
| raw | `0.3325` | `0.3297` | `-0.0027` | `0.2310` | `0.5616` |
| calibrated | `0.3325` | `0.3782` | `0.0457` | `0.2488` | `0.4623` |
| lower | `0.3325` | `0.3762` | `0.0437` | `0.2484` | `0.4623` |

Interpretation: valid内OOFではcalibrationが改善するが、2024-12への外挿では明確に悪化した。

## Validation Sweep

Aggregated artifact:

- `data/reports/backtests/20260628_profit_barrier_column_validation_summary.csv`

Best rows by variant:

| variant | entry | short offset | threshold | max hold | basic eligible | min pnl | total pnl | min trades | forced max | drawdown max | side share max |
|---|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|
| raw | `10` | `8` | `0.35` | `720` | `true` | `25.5832` | `284.1632` | `34` | `0.0435` | `90.0226` | `0.8235` |
| calibrated | `5` | `12` | `0.50` | `720` | `false` | `-48.8580` | `140.2438` | `22` | `0.0857` | `78.5518` | `1.0000` |
| lower | `5` | `12` | `0.50` | `720` | `false` | `-48.8580` | `140.2438` | `22` | `0.0857` | `78.5518` | `1.0000` |

Key observations:

- calibrated/lowerは2024-11で `-48.8580` まで落ち、long-only化してbasic gateを満たさない。
- rawはvalidation上では `entry=10`, `short offset=8`, threshold `0.35`, max hold `720` がbasic gateを満たす。
- ただしraw topも side share max `0.8235` でやや偏りがあり、smoothed miss max `0.5417` と余裕は薄い。

## 2024-12 Diagnostic

Fixed settings:

- entry `10`
- short offset `8`
- threshold `0.35`
- max hold `720`
- same holding/side-margin/rank settings as validation

Artifacts:

- raw: `data/reports/backtests/20260628_090555_model_timed_ev_2024-12/`
- calibrated: `data/reports/backtests/20260628_090556_model_timed_ev_2024-12/`
- lower: `data/reports/backtests/20260628_090558_model_timed_ev_2024-12/`

| variant | adjusted pnl | raw pnl | trades | win rate | profit factor | max drawdown | forced exits |
|---|---:|---:|---:|---:|---:|---:|---:|
| raw | `-184.9344` | `-126.3610` | `54` | `0.3889` | `0.4738` | `228.6692` | `2` |
| calibrated | `-215.7914` | `-153.5060` | `54` | `0.3519` | `0.4226` | `234.5290` | `3` |
| lower | `-215.7914` | `-153.5060` | `54` | `0.3519` | `0.4226` | `234.5290` | `3` |

## Decision

- calibrated/lower profit-barrier columnsをhard gateへ昇格しない。
- raw profit-barrier columnも、今回のvalidation-selected settingは2024-12で大きく崩れたため採用しない。
- profit-barrier probabilityは「校正診断」や「候補分析」には有効だが、entry gateとして単独で強く使うと未知月で壊れる。
- 次は profit-barrier をhard gateではなく、EV score penalty / tie-break / uncertainty penaltyとして試す。特にside/regime別の崩れを同時に見る。

## Next Actions

1. `profit_barrier_miss_penalty` を raw/calibrated/lower probabilityで比較できるようにする。
2. hard thresholdではなく `penalty * (1 - calibrated_probability_lower)` をEVから引く設定を検証する。
3. 2024-12は引き続き反証月として扱い、thresholdを後付けで選び直さない。
4. 低supportまたは月×sideで誤差が大きいbucketは、entry増加ではなくrisk penalty方向へ使う。
