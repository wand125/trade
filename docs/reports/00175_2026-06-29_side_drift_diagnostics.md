# Side Drift Diagnostics

日時: 2026-06-29 22:35 JST
更新日時: 2026-06-29 22:35 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- Added `scripts/experiments/side_drift_diagnostics.py`.
- Purpose: compare dense label side shares, raw predicted EV side shares, selected trade side shares, and realized PnL by month/regime/session.
- Fresh 2025-09..12 failure is confirmed as side-distribution drift, not just holding-time error.
- Main fresh symptom: actual labels are long-leaning, but raw EV predictions are short-leaning by about `+0.414` short share over the dense label distribution.
- Selected short trades lose money in all four fresh months; selected short PnL is `-704.9300` out of total `-839.2544`.
- Do not tune hard blocks on 2025-09..12. Next step is a walk-forward side-prior / side-calibration guard selected only from earlier windows.

## Script

`side_drift_diagnostics.py` writes:

- `prediction_month_summary.csv`
- `prediction_group_summary.csv`
- `selected_trade_month_summary.csv`
- `selected_trade_group_summary.csv`
- `side_drift_alerts.csv`
- `enriched_selected_trades.csv`
- `metrics.json`

The alert table joins prediction-side bias with selected trade realized PnL. A row is active when:

- selected side has at least `min_alert_trades`
- predicted side share exceeds actual dense-label side share by at least `min_alert_bias`
- selected trades for that side/context have negative total adjusted PnL

This is a diagnostic, not a rule generator.

## Runs

Fresh failure window:

```bash
python3 scripts/experiments/side_drift_diagnostics.py \
  --predictions data/reports/modeling/20260629_132211_stateful_risk_mean_match_session_floor_lowered_apply_2025_09_12/predictions_apply_stateful_risk_model.parquet \
  --policy-summary data/reports/backtests/20260629_132337_holding_max_fixed_2025_09_12/policy_summary.csv \
  --months 2025-09,2025-10,2025-11,2025-12 \
  --variants coststress_maxhold_260 \
  --cost-cases coststress \
  --group-columns combined_regime,session_regime \
  --label side_drift_fresh_2025_09_12_coststress_260
```

Reference window:

```bash
python3 scripts/experiments/side_drift_diagnostics.py \
  --predictions data/reports/modeling/20260629_130347_holding_max_fine_grid_2025_01_08/predictions_holding_max_grid_input.parquet \
  --policy-summary data/reports/backtests/20260629_130347_holding_max_fine_grid_2025_01_08/policy_summary.csv \
  --months 2025-01,2025-02,2025-03,2025-04,2025-05,2025-06,2025-07,2025-08 \
  --variants coststress_maxhold_260 \
  --cost-cases coststress \
  --group-columns combined_regime,session_regime \
  --label side_drift_reference_2025_01_08_coststress_260
```

## Monthly Prediction Drift

Fresh 2025-09..12:

| month | actual long label share | actual short label share | pred EV long share | pred EV short share | short overprediction | nonflat label match |
|---|---:|---:|---:|---:|---:|---:|
| 2025-09 | `0.6348` | `0.3054` | `0.2569` | `0.7431` | `0.4376` | `0.3913` |
| 2025-10 | `0.5410` | `0.4401` | `0.1625` | `0.8375` | `0.3974` | `0.4552` |
| 2025-11 | `0.5633` | `0.4122` | `0.1643` | `0.8357` | `0.4234` | `0.4456` |
| 2025-12 | `0.5617` | `0.4011` | `0.2001` | `0.7999` | `0.3988` | `0.4945` |

Reference 2025-01..08:

| metric | fresh | reference |
|---|---:|---:|
| mean short overprediction | `0.4143` | `0.2211` |
| min short overprediction | `0.3974` | `0.1092` |
| max short overprediction | `0.4376` | `0.2965` |
| mean nonflat label match | `0.4466` | `0.5117` |
| mean actual side score | `3.6203` | `2.4867` |
| mean predicted side score | `-6.0428` | `-3.0632` |

Both windows have short bias, but fresh is materially more extreme and less accurate.

## Selected Trade Outcome

`coststress_maxhold_260` selected trade summary:

| window | total PnL | long PnL | short PnL | short-losing months | weighted direction error | weighted EV overestimate |
|---|---:|---:|---:|---:|---:|---:|
| fresh 2025-09..12 | `-839.2544` | `-134.3244` | `-704.9300` | `4/4` | `0.6111` | `26.1986` |
| reference 2025-01..08 | `458.9738` | `407.3946` | `51.5792` | `3/8` | `0.4472` | `19.1641` |

The reference window also has bad contexts, but the long side and some short months offset them. Fresh does not offset: short losses dominate every month.

## Top Fresh Alerts

| month | context | side | pred side share | actual label share | bias | trades | pnl | direction error |
|---|---|---|---:|---:|---:|---:|---:|---:|
| 2025-09 | `range_low_vol / london` | short | `0.9873` | `0.1877` | `0.7996` | `17` | `-140.3796` | `0.8235` |
| 2025-10 | `range_low_vol / rollover` | short | `1.0000` | `0.1250` | `0.8750` | `4` | `-47.7366` | `1.0000` |
| 2025-12 | `range_low_vol / asia` | short | `0.9806` | `0.3124` | `0.6681` | `13` | `-51.6430` | `0.6923` |
| 2025-12 | `up_normal_vol / rollover` | short | `1.0000` | `0.2124` | `0.7876` | `4` | `-35.2420` | `1.0000` |
| 2025-12 | `range_low_vol / london` | short | `0.9551` | `0.3423` | `0.6128` | `8` | `-34.5584` | `0.7500` |
| 2025-11 | `range_low_vol / asia` | short | `0.9925` | `0.2541` | `0.7384` | `4` | `-24.1680` | `1.0000` |

Fresh active alerts:

| side | alerts | pnl | loss-bias score | trades |
|---|---:|---:|---:|---:|
| short | `11` | `-406.7756` | `281.0084` | `69` |
| long | `1` | `-11.0414` | `1.4428` | `6` |

## Interpretation

- The model is not merely picking the wrong exit time. It enters too many shorts under contexts whose dense labels are not short-favorable.
- `range_low_vol` is the dominant fresh failure context, but the exact session differs by month. A static block learned from 2025-09..12 would be post-hoc and unsafe.
- The current raw EV side selection is too confident: alert rows often have `pred_ev_matches_trade_rate = 1.0`, meaning the policy follows the raw EV side, while realized label/direction diagnostics disagree.
- Existing stateful risk and holding cap reduce some tail behavior but do not correct side priors.

## Decision

- Keep `side_drift_diagnostics.py` as a standard research diagnostic.
- Do not promote `250m` or `260m` to standard policy based on fresh results.
- Do not add a fresh-window hard block such as `short/range_low_vol/london`.
- Next implementation should be a side prior drift guard that is selected walk-forward from earlier months. Candidate design:
  - compute prior prediction-vs-label side share bias by month/regime/session;
  - apply a penalty or offset only when prior windows repeatedly show one-sided overprediction and negative selected-side PnL;
  - evaluate with chronological windows, not random or same-month selection.

## Artifacts

- Fresh diagnostics: `data/reports/modeling/20260629_133440_side_drift_fresh_2025_09_12_coststress_260/`
- Reference diagnostics: `data/reports/modeling/20260629_133501_side_drift_reference_2025_01_08_coststress_260/`

## Verification

- `python3 -m unittest tests.test_side_drift_diagnostics`: OK, 4 tests
- `python3 -m py_compile scripts/experiments/side_drift_diagnostics.py`: OK
- `python3 scripts/experiments/side_drift_diagnostics.py --help`: OK

## Next Actions

- Build a walk-forward side drift guard rather than a fresh-window hard block.
- Start with side/context prior tables using only months before the target month.
- Prefer soft penalties or side-threshold offsets over binary blocks, because reference months still contain profitable short trades.
