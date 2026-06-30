# Same-Family Side Calibration Diagnostics

日時: 2026-06-30 12:14 JST
更新日時: 2026-06-30 12:14 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00204で `gap5/budget0` が追加apply `2025-05..08` に外挿しなかったため、同じ10ヶ月窓でside prediction calibrationと実約定side別PnLを診断した。
- ローカルM1価格データ自体は `2009-03-15` から `2026-06-01` まで存在する。純2024検証の不足は価格データではなく、同一familyの前段HGB+MLP forced predictionが早期2024へ未生成なこと。
- raw EV predictionは `2025-04..06` でshort過剰が強く、actual label short shareに対して `+0.27..+0.30` 程度shortへ寄る。
- ただし追加applyの失敗は「shortが多すぎる」だけでは説明できない。`gap5/budget0` は `2025-06` の良いshortを削り、`2025-07/08` ではlong側の大きな損失が残った。
- 結論: 次はshort-only hookを増やさず、同一family predictionを早期2024へ広げることと、side calibration / EV calibrationをsource policy側で再評価する。

## Artifacts

- Baseline side drift diagnostics: `data/reports/modeling/20260630_031330_20260630_122000_side_drift_baseline_samefamily_2024_11_2025_08/`
- Source side drift diagnostics: `data/reports/modeling/20260630_031330_20260630_122100_side_drift_source_samefamily_2024_11_2025_08/`
- Gap5 side drift diagnostics: `data/reports/modeling/20260630_031330_20260630_122200_side_drift_gap5_samefamily_2024_11_2025_08/`
- Gap5 normalized policy summary: `data/reports/backtests/20260630_030122_20260630_120900_short_raw_gap_budget_samefamily_2024_11_2025_08/policy_summary_gap5_budget0.csv`

Inputs:

- Predictions: `data/reports/modeling/20260630_025915_20260630_120600_holding_max260_samefamily_2024_11_2025_08/predictions_holding_max_grid_input.parquet`
- Baseline policy summary: `data/reports/backtests/20260630_025915_20260630_120600_holding_max260_samefamily_2024_11_2025_08/policy_summary.csv`
- Source policy summary: `data/reports/backtests/20260630_030015_20260630_120800_side_drift_p10_replm10_samefamily_2024_11_2025_08/policy_summary.csv`
- Gap5 summary: `data/reports/backtests/20260630_030122_20260630_120900_short_raw_gap_budget_samefamily_2024_11_2025_08/summary_by_run.csv`

## Data Coverage Preflight

- `data/processed/histdata/xauusd/xauusd_m1.parquet` has `6,025,170` rows.
- Earliest timestamp: `2009-03-15 22:00:00+00:00`.
- Latest timestamp: `2026-06-01 04:58:00+00:00`.
- Dataset parquet files already exist for 2024-01..12 and many earlier years.
- Current same-risk OOF artifact uses validation months `2024-07, 2024-09, 2024-11, 2024-12, 2025-01..04`, but with `min_train_months=2`, OOF predictions are emitted only from `2024-11` onward. `2024-07` and `2024-09` are skipped by design.
- Therefore, pure2024 fixed comparison needs early-2024 same-family HGB+MLP forced predictions and then a wider stateful risk OOF/apply run. It is not a raw data availability problem.

## Prediction Side Calibration

Raw EV prediction side distribution by month:

| month | actual label long | actual label short | flat | pred EV long | pred EV short | short bias | long bias | EV-best match |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2024-11 | `0.4045` | `0.4133` | `0.1823` | `0.4114` | `0.5886` | `+0.1753` | `+0.0069` | `0.5104` |
| 2024-12 | `0.2865` | `0.3931` | `0.3204` | `0.5553` | `0.4447` | `+0.0516` | `+0.2688` | `0.4115` |
| 2025-01 | `0.5747` | `0.2032` | `0.2222` | `0.6156` | `0.3844` | `+0.1812` | `+0.0409` | `0.5427` |
| 2025-02 | `0.4467` | `0.4486` | `0.1047` | `0.3461` | `0.6539` | `+0.2053` | `-0.1007` | `0.4360` |
| 2025-03 | `0.5701` | `0.2645` | `0.1654` | `0.4810` | `0.5190` | `+0.2545` | `-0.0891` | `0.4855` |
| 2025-04 | `0.4802` | `0.4997` | `0.0201` | `0.2038` | `0.7962` | `+0.2965` | `-0.2764` | `0.5033` |
| 2025-05 | `0.4540` | `0.5096` | `0.0363` | `0.2160` | `0.7840` | `+0.2743` | `-0.2380` | `0.4838` |
| 2025-06 | `0.4560` | `0.5110` | `0.0330` | `0.2149` | `0.7851` | `+0.2740` | `-0.2411` | `0.5329` |
| 2025-07 | `0.4406` | `0.4494` | `0.1100` | `0.4413` | `0.5587` | `+0.1092` | `+0.0008` | `0.5338` |
| 2025-08 | `0.5005` | `0.3256` | `0.1738` | `0.5007` | `0.4993` | `+0.1737` | `+0.0002` | `0.5442` |

The model has a sustained short-side bias, especially `2025-04..06`. However, the month-level EV-best match is not uniformly bad, which is why simple side-share correction can remove good trades.

## Policy Side Results

### All 10 months

| policy | trades | total PnL | short PnL | long PnL | short trades | long trades | worst month | avg direction error | avg no-edge | avg EV overestimate |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline | `1137` | `+433.3572` | `+141.4032` | `+291.9540` | `475` | `662` | `-26.2112` | `0.4548` | `0.0987` | `18.7466` |
| source p10/replm10 | `945` | `+219.9460` | `+13.0454` | `+206.9006` | `398` | `547` | `-102.2830` | `0.4653` | `0.0953` | `19.2959` |
| gap5/budget0 | `777` | `+384.6968` | `+177.7962` | `+206.9006` | `230` | `547` | `-90.5606` | `0.4695` | `0.1019` | `16.6286` |

### Additional apply months only: 2025-05..08

| policy | trades | total PnL | short PnL | long PnL | short trades | long trades | worst month | avg direction error | avg no-edge | avg EV overestimate |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline | `496` | `+176.8236` | `+63.5560` | `+113.2676` | `240` | `256` | `-24.6998` | `0.4696` | `0.0474` | `20.2606` |
| source p10/replm10 | `396` | `+66.7730` | `+37.4170` | `+29.3560` | `190` | `206` | `-102.2830` | `0.4476` | `0.0528` | `20.6874` |
| gap5/budget0 | `293` | `+13.9434` | `-15.4126` | `+29.3560` | `87` | `206` | `-90.5606` | `0.4534` | `0.0620` | `17.5188` |

Key point: `gap5/budget0` reduces short trades heavily, but in `2025-05..08` its short PnL becomes negative while the source short book remains positive.

## Failure Decomposition

Representative worst groups after `gap5/budget0`:

| month | context | side | trades | PnL | direction error | no-edge | EV overestimate |
|---|---|---|---:|---:|---:|---:|---:|
| 2025-07 | `down_low_vol / ny_overlap` | long | `4` | `-97.4172` | `0.7500` | `0.0000` | `39.5386` |
| 2024-12 | `down_low_vol / ny_late` | long | `7` | `-60.1988` | `0.4286` | `0.2857` | `22.6924` |
| 2024-11 | `range_normal_vol / ny_overlap` | long | `3` | `-59.8192` | `0.6667` | `0.0000` | `40.6135` |
| 2025-06 | `range_normal_vol / ny_overlap` | short | `6` | `-42.0708` | `0.6667` | `0.0000` | `23.7449` |
| 2025-08 | `up_low_vol / asia` | long | `8` | `-36.7772` | `0.6250` | `0.1250` | `19.5888` |

Active side drift alerts after `gap5/budget0` also become more long-heavy. The largest alert is `2025-07 down_low_vol/ny_overlap long`, not a short context. This means short-only suppression can move the residual risk into long exposure rather than solving the policy.

## Interpretation

- The raw EV model is often short-biased, but the bias is not monotonically bad. In `2025-06`, source short PnL is `+68.8738`; `gap5/budget0` turns the short contribution into `-17.3392`, a `-86.2130` swing.
- `gap5/budget0` has lower average EV overestimate than source in the additional apply window, but PnL is worse. Lower overestimate and direction-error metrics are not sufficient adoption evidence.
- The source policy's weakness is a mixed side/admission/EV calibration problem. In `2025-08`, source loses both long `-69.2542` and short `-33.0288`; gap5 trims short count but leaves the long loss unchanged.
- Further short-only hooks on the same 2025 family risk fitting the successful `2025-03/04` pattern while breaking `2025-05..08`.

## Decision

- Do not add another short-only budget hook from the current 2025 sequence.
- Keep `side_drift_diagnostics.py` outputs as the standard preflight for any future side/admission rule.
- Prioritize generating early-2024 same-family prediction inputs so the existing candidate family can be evaluated in a wider chronological regime.
- Revisit side correction as calibration, not hard suppression: predicted side share, dense label side share, selected trade side PnL, EV overestimate, and replacement behavior all need to be considered together.

## Next

1. Generate HGB+MLP forced predictions for early 2024 months, then rerun `oof-stateful-risk-model` so same-risk columns exist before `2024-11`.
2. Run baseline / p10+replm10 / gap0 / gap5 fixed comparison on pure2024, avoiding final-model leakage into earlier months.
3. Add a compact side-calibration preflight table to future candidate reports: side share bias, side PnL, direction error, no-edge rate, EV overestimate, and top loss-bias contexts.

## Verification

- Baseline side drift diagnostics artifact generated: OK
- Source side drift diagnostics artifact generated: OK
- Gap5 side drift diagnostics artifact generated: OK
- Data coverage preflight completed: OK
