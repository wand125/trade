# Entry EV Calibration Admission

日時: 2026-06-30 13:08 JST
更新日時: 2026-06-30 13:08 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00207で全2024同一chronological protocolを作ったが、OOF 8ヶ月のbestでもNoTrade `0` を超えなかった。今回の焦点はside hook追加ではなく、entry EV calibrationとadmission thresholdの確認。
- `2024-01..02` validation用にも同じHGB entry + MLP exit hybrid predictionを作り、raw EV列と `pred_calibrated_*_best_adjusted_pnl` 列を比較した。
- raw EVはvalidation gridでは良く見える候補を出すが、full 2024 testへ固定すると大きく崩れた。raw `entry=12, short_offset=3` はvalidation `+22.7292` だが、test `-442.4662`。
- calibrated EVはvalidationでは高threshold候補がNoTrade tieになり、positive edgeをvalidation上で証明できなかった。一方、同じ高threshold候補をfull 2024 testへ固定すると `cal_notrade_10_6` が `+100.3612`、`cal_notrade_12_6` が `+74.0644` になった。
- 判断: `pred_calibrated_*` と高いshort thresholdは強い診断候補。ただしvalidationでは「勝った」のではなく「取引しなかった」だけなので、標準policyには昇格しない。次はfresh chronological foldで、NoTrade tieの扱いとthreshold selectorを事前固定する。

## Artifacts

- Validation hybrid prediction: `data/reports/modeling/20260630_chrono_hgb_mlp_exit_2024_01_02/predictions_hgb_entry_mlp_exit_2024_01_02.parquet`
- Validation calibrated sweep:
  - `data/reports/backtests/20260630_entry_evcal_validation_calibrated/20260630_040137_model_sweep_2024-01/`
  - `data/reports/backtests/20260630_entry_evcal_validation_calibrated_v2/20260630_040205_model_sweep_2024-02/`
- Validation raw sweep: `data/reports/backtests/20260630_entry_evcal_validation_raw/`
- Fixed full-2024 tests:
  - raw `entry12/short3`: `data/reports/backtests/20260630_040416_chrono_2024_entry_evcal_raw_entry12_short3_fixed/`
  - raw `entry10/short6`: `data/reports/backtests/20260630_040416_chrono_2024_entry_evcal_raw_entry10_short6_fixed/`
  - calibrated `entry10/short6`: `data/reports/backtests/20260630_040416_chrono_2024_entry_evcal_cal_entry10_short6_fixed/`
  - calibrated `entry12/short6`: `data/reports/backtests/20260630_040415_chrono_2024_entry_evcal_cal_entry12_short6_fixed/`
  - calibrated `entry12/short3`: `data/reports/backtests/20260630_040526_chrono_2024_entry_evcal_cal_entry12_short3_fixed/`
- Compact comparison tables: `data/reports/backtests/20260630_041000_entry_ev_calibration_admission_compare/`

## EV Scale Drift

HGB entry EV distributions still drift between validation and test. Calibration reduces scale but does not remove all drift, especially on short side.

| split | column | mean | p50 | p90 | p99 | max |
|---|---|---:|---:|---:|---:|---:|
| valid `2024-01..02` | raw long EV | `11.5504` | `11.7450` | `13.9715` | `15.0903` | `17.0815` |
| valid `2024-01..02` | raw short EV | `10.7605` | `11.0901` | `13.0656` | `15.1231` | `24.8377` |
| valid `2024-01..02` | calibrated long EV | `9.3011` | `9.4249` | `10.8419` | `11.5539` | `12.8211` |
| valid `2024-01..02` | calibrated short EV | `9.7696` | `9.8895` | `10.6081` | `11.3566` | `14.8906` |
| test `2024-03..12` | raw long EV | `11.7785` | `11.9312` | `14.1729` | `15.6878` | `21.0732` |
| test `2024-03..12` | raw short EV | `13.8124` | `12.9075` | `19.1566` | `29.8617` | `49.4315` |
| test `2024-03..12` | calibrated long EV | `9.4463` | `9.5434` | `10.9701` | `11.9342` | `15.3615` |
| test `2024-03..12` | calibrated short EV | `10.8798` | `10.5506` | `12.8239` | `16.7182` | `23.8374` |

The raw short EV tail inflates badly in test. Calibrated columns are less inflated but still not stable enough to be treated as absolute expected PnL.

## Validation Grid

Common settings:

- train/model protocol: HGB and MLP fit on `2023-01..12`
- validation: `2024-01, 2024-02`
- coststress: spread `0.2`, slippage `0.1`, delay `1`
- profit multiplier `1.0`, loss multiplier `1.20`
- max predicted hold `260`
- side margin `5`, risk penalty `0`
- MLP exit columns with `min_valid_predicted_hold_minutes=30`
- entry thresholds `0,2,4,6,8,10,12`, short offsets `0,3,6`

Top validation rows:

| family | entry | short offset | validation total | worst | trades | max DD |
|---|---:|---:|---:|---:|---:|---:|
| calibrated | `10` | `6` | `0.0000` | `0.0000` | `0` | `0.0000` |
| calibrated | `12` | `3` | `0.0000` | `0.0000` | `0` | `0.0000` |
| calibrated | `12` | `6` | `0.0000` | `0.0000` | `0` | `0.0000` |
| raw | `12` | `3` | `+22.7292` | `-8.6636` | `61` | `20.8644` |
| raw | `10` | `6` | `+21.3196` | `-8.2736` | `61` | `15.1626` |

The important distinction is that raw candidates are selected by positive validation PnL and fail on test, while calibrated high-threshold candidates are selected only as NoTrade ties.

## Fixed 2024 Test

All rows below are fixed on `2024-03..12`, with no threshold re-selection on test.

| policy | total PnL | total `2024-05..12` | worst | max DD | trades | short PnL | forced | EV over realized |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| calibrated `entry10/short6` | `+100.3612` | `+130.3508` | `-43.2296` | `51.5828` | `60` | `+99.6382` | `0` | `15.1069` |
| calibrated `entry12/short6` | `+74.0644` | `+65.4014` | `-37.8326` | `37.8326` | `26` | `+73.3414` | `0` | `15.3825` |
| source OOF 8m | `-3.1736` | `-3.1736` | `-107.9646` | `123.1386` | `599` | `-27.7960` | `2` | `16.2584` |
| calibrated `entry12/short3` | `-27.2164` | `+85.1564` | `-101.1990` | `106.6356` | `98` | `-27.9394` | `0` | `16.0759` |
| raw base `entry12/short6` | `-260.3458` | `-141.4216` | `-81.0202` | `134.7892` | `426` | `-250.2582` | `4` | `19.6822` |
| raw validation `entry10/short6` | `-369.2984` | `-136.5404` | `-166.0098` | `183.2810` | `498` | `-363.5768` | `7` | `19.0235` |
| raw validation `entry12/short3` | `-442.4662` | `-231.6604` | `-150.2104` | `169.6968` | `516` | `-412.7976` | `7` | `18.9234` |

`calibrated entry12/short6` is the lower-risk candidate. `calibrated entry10/short6` has higher total PnL but is more exposed. `calibrated entry12/short3` shows that simply loosening the short threshold breaks the benefit.

## Monthly PnL

| month | cal `10/6` | cal `12/6` | source OOF8 | raw base `12/6` |
|---|---:|---:|---:|---:|
| 2024-03 | `-10.2966` | `-16.3290` |  | `-42.7274` |
| 2024-04 | `-19.6930` | `+24.9920` |  | `-76.1968` |
| 2024-05 | `+19.5864` | `-37.8326` | `-107.9646` | `-40.2318` |
| 2024-06 | `+35.2600` | `+29.5300` | `-13.8766` | `-3.3658` |
| 2024-07 | `+10.4700` | `0.0000` | `+18.1632` | `-28.7832` |
| 2024-08 | `+5.6340` | `+37.0940` | `-82.9640` | `-81.0202` |
| 2024-09 | `0.0000` | `0.0000` | `+28.7038` | `-76.0666` |
| 2024-10 | `-1.0100` | `-11.4600` | `-8.4240` | `-21.0610` |
| 2024-11 | `+103.6400` | `+52.0300` | `+187.2742` | `+172.2896` |
| 2024-12 | `-43.2296` | `-3.9600` | `-24.0856` | `-63.1826` |

The test success is not smooth. Both calibrated candidates still depend on a small number of months, and `cal10/6` has only `60` trades over ten months.

## Decision

No standard policy is promoted.

What changed:

- Raw EV thresholds are now clearly refuted as direct admission thresholds. Good validation PnL on raw EV did not generalize.
- Calibrated EV columns reduce the worst over-selection and can produce positive full-2024 test PnL under high thresholds.
- The most useful structure is not generic calibration. It is calibrated EV plus a high short admission threshold.

Why not adopt yet:

- Validation chose the best calibrated rows as NoTrade ties, not as profitable trading policies.
- Choosing `cal10/6` or `cal12/6` after seeing `2024-03..12` would be test-set selection.
- The trade count is low, so one favorable month can dominate the aggregate.
- EV over realized remains high at roughly `15`, so absolute EV calibration is still weak.

Next:

1. Add a threshold selector that handles NoTrade ties explicitly. If validation cannot distinguish trading from NoTrade, choose the most conservative diagnostic candidate or keep NoTrade as the selected policy.
2. Re-run this exact calibrated admission grid on fresh chronological folds before any standard adoption.
3. Prefer `cal12/6` as the lower-risk diagnostic candidate when a fixed candidate is required, but do not label it standard.
4. Investigate entry EV calibration by side and regime, especially the residual short EV scale drift.
5. Keep source OOF8 and raw base as comparison baselines so future improvement is measured against both NoTrade and the previous diagnostic policies.

## Verification

- Validation hybrid generation: OK, `56,077` rows, MLP exit missing `0`, forced target missing `0`
- Validation raw and calibrated sweeps: OK
- Fixed full-2024 tests: OK
- Compact comparison tables: OK
