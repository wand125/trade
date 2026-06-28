# Profit Barrier EV Penalty Validation

日時: 2026-06-28 18:17 JST
更新日時: 2026-06-28 18:17 JST

## Summary

- Experiment ID: `profit_barrier_ev_penalty_validation`
- Status: diagnosed and rejected for promotion
- Main result: validation 4foldでは calibrated/lower probabilityを使った線形EV penaltyがstrict条件を満たしたが、2024-12反証月では大きく崩れた。raw penaltyは2024-12の損失を縮めたが、NoTradeには届かない。
- Report numbering note: this file is numbered from the internal file `日時`, not filesystem mtime or `更新日時`.

## Setup

Base predictions:

- valid OOF-calibrated predictions: `data/reports/modeling/20260628_090051_policy_valid_month_oof_profit_barrier_calibration/predictions_profit_barrier_calibrated.parquet`
- test-applied calibrated predictions: `data/reports/modeling/20260628_090105_policy_valid_fit_test_profit_barrier_calibration/predictions_profit_barrier_calibrated.parquet`

Policy grid:

- policy: `timed_ev`
- holding columns: `pred_long_exit_event_minutes`, `pred_short_exit_event_minutes`
- entry threshold: `5,10`
- short offset: `8,12`
- side margin: `1`
- min entry rank: `0.5`
- max predicted hold minutes: `480,720`
- profit-barrier hard gate: disabled
- profit-barrier miss penalty: `0,0.5,1,2,4,6,8`
- extra side margins: `session_regime=asia:5,session_regime=rollover:5`

Compared penalty columns:

| variant | long column | short column |
|---|---|---|
| raw | `pred_long_profit_barrier_hit_prob_1` | `pred_short_profit_barrier_hit_prob_1` |
| calibrated | `pred_long_profit_barrier_hit_calibrated_prob` | `pred_short_profit_barrier_hit_calibrated_prob` |
| lower | `pred_long_profit_barrier_hit_calibrated_prob_lower` | `pred_short_profit_barrier_hit_calibrated_prob_lower` |

The penalty formula is the existing linear score adjustment:

```text
side_ev -= profit_barrier_miss_penalty * (1 - side_profit_barrier_probability)
```

## Validation 4fold

Artifacts:

- raw sweeps: `data/reports/backtests/profit_barrier_penalty_raw/`
- calibrated sweeps: `data/reports/backtests/profit_barrier_penalty_calibrated/`
- lower sweeps: `data/reports/backtests/profit_barrier_penalty_lower/`
- summary CSV: `data/reports/backtests/20260628_profit_barrier_penalty_validation_summary.csv`

Eligibility definition:

- all 4 folds present
- each fold adjusted pnl `>= 0`
- each fold trades `>= 10`
- forced exit max `<= 0.05`
- drawdown max `<= 100`
- strict additionally requires side share max `<= 0.85` and smoothed actual barrier miss max `<= 0.55`

Best rows:

| variant | entry | short offset | penalty | max hold | strict eligible | min pnl | total pnl | min trades | forced max | drawdown max | side share max | smoothed miss max |
|---|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|
| lower | `5` | `8` | `6` | `480` | `true` | `52.3018` | `462.2030` | `59` | `0.041096` | `71.9208` | `0.796610` | `0.546667` |
| calibrated | `5` | `8` | `6` | `480` | `true` | `52.3018` | `461.7346` | `59` | `0.041096` | `71.9208` | `0.796610` | `0.546667` |
| raw | `5` | `8` | `8` | `720` | `true` | `33.5668` | `317.7776` | `41` | `0.000000` | `99.3376` | `0.804878` | `0.540000` |

No-penalty reference:

| variant | entry | short offset | penalty | max hold | basic eligible | min pnl | total pnl | min trades | forced max | drawdown max |
|---|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|
| any | `10` | `8` | `0` | `720` | `false` | `12.5636` | `287.8596` | `37` | `0.055556` | `77.0800` |

Interpretation:

- 線形penaltyはvalidation上ではno-penaltyより明確に候補を改善した。
- 特に calibrated/lower `penalty=6`, max hold `480` は、high-turnoverかつside shareとsmoothed missの制約も通過した。
- ただしこの改善はvalidation grid上の選択であり、前回のhard gateと同じく外挿リスクがある。

## 2024-12 Diagnostic

Fixed diagnostics:

| label | columns | entry | short offset | penalty | max hold | artifact |
|---|---|---:|---:|---:|---:|---|
| no penalty reference | raw | `10` | `8` | `0` | `720` | `data/reports/backtests/20260628_091701_model_timed_ev_2024-12_1/` |
| raw validation strict | raw | `5` | `8` | `8` | `720` | `data/reports/backtests/20260628_091701_model_timed_ev_2024-12/` |
| calibrated validation top | calibrated | `5` | `8` | `6` | `480` | `data/reports/backtests/20260628_091701_model_timed_ev_2024-12_3/` |
| lower validation top | lower | `5` | `8` | `6` | `480` | `data/reports/backtests/20260628_091701_model_timed_ev_2024-12_2/` |

Results:

| label | adjusted pnl | raw pnl | trades | profit factor | max drawdown | forced exits | actual barrier miss | EV over realized |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| no penalty reference | `-227.4118` | `-158.4170` | `63` | `0.4507` | `246.1494` | `3` | `0.6508` | `21.4299` |
| raw validation strict | `-141.9282` | `-82.3560` | `56` | `0.6029` | `162.0080` | `2` | `0.6607` | `20.1974` |
| calibrated validation top | `-212.1886` | `-142.9850` | `72` | `0.4890` | `247.1292` | `4` | `0.7639` | `19.8757` |
| lower validation top | `-214.3986` | `-145.1950` | `72` | `0.4837` | `247.1292` | `4` | `0.7639` | `19.9147` |

Key diagnostics:

- raw penaltyは2024-12損失を `-227.4118` から `-141.9282` へ縮めたが、NoTradeに大きく負ける。
- calibrated/lower validation topは2024-12で崩れ、actual barrier missが `0.7639` まで悪化した。
- calibrated/lowerの2024-12 selected tradesでは `0.4-0.6` bucketのactual hit rateが `0.24`、predicted meanが約 `0.52` で、強い過大評価が再発している。
- 2024-12の損失中心は raw penaltyでも `long:london` と `long:down_low_vol`。profit-barrier penaltyだけでは方向選択の壊れ方を抑えられない。

## Decision

- Simple linear profit-barrier EV penaltyは標準policyへ昇格しない。
- calibrated/lower probabilityはvalidation上のcandidate selectionを改善したが、2024-12への外挿で悪化したため、単独のpenalty/tie-breakとしては危険。
- raw penaltyは損失縮小の診断価値はあるが、採用するには複数blind月でNoTrade超えとdrawdown改善を示す必要がある。
- profit-barrier probabilityは、引き続きhard gateでもglobal linear penaltyでもなく、side/regime別の壊れ方を説明するdiagnosticとして扱う。

## Next Actions

1. profit-barrier probability単独のpolicy改善はいったん打ち切る。
2. 次は exit timing側、特に time-exit probability penalty / hazard-like exit policy を優先する。
3. profit-barrierは future workとして、direction/sessionやcombined regimeのrisk penaltyと同時に使う場合だけ再評価する。
4. 2024-12で崩れた `penalty=6/8` を後付けで調整して採用しない。
