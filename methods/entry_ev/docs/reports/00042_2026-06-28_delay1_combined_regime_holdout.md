# Delay 1 Combined Regime Holdout

日時: 2026-06-28 16:31 JST
更新日時: 2026-06-28 16:31 JST

## Summary

- Experiment ID: `delay1_combined_regime_holdout`
- Status: implemented, validated, and rejected as a promotion candidate
- Main result: `combined_regime` / `direction:combined_regime` の最悪損益診断とcandidate gateを追加したが、2024-12 holdoutは改善しなかった。
- Best validation candidate with combined gate: `entry_threshold=5`, `short_entry_threshold_offset=20`, `profit_barrier_threshold=0.4`, `max_predicted_hold_minutes=480`
- 2024-12 cost-aware holdout: adjusted pnl `-149.7354`, 33 trades, profit factor `0.3820`, max drawdown `176.6504`
- Report numbering note: this file is numbered by the internal `日時`, not by file update time or `更新日時`.

## Implementation

`model-sweep` metricsに以下を追加した。

- `combined_regime_adjusted_pnl_min`
- `worst_combined_regime`
- `worst_combined_regime_trade_count`
- `direction_combined_regime_adjusted_pnl_min`
- `worst_direction_combined_regime`
- `worst_direction_combined_regime_trade_count`

`model-candidate-selection` には以下を追加した。

- `--max-combined-regime-loss-per-fold`
- `--max-direction-combined-regime-loss-per-fold`

目的は、2024-12 holdoutで目立った `range_low_vol` や `direction:combined_regime` 単位の崩れを、validation候補選択時点で検出すること。

## Delay 1 Validation Sweep

Setup:

- predictions: `experiments/20260628_064332_policy_exit_event_prob_p1_l1p2/predictions_valid.parquet`
- execution delay: `1`
- policy: `timed_ev`
- holding columns: `pred_long_exit_event_minutes`, `pred_short_exit_event_minutes`
- profit-first gate columns: `pred_long_exit_event_prob_1`, `pred_short_exit_event_prob_1`
- loss multiplier: model/data line is `p1_l1p2`

Artifacts:

- no-cost sweeps: `data/reports/backtests/20260628_072504_model_sweep_2024-07/`, `...2024-09/`, `...2024-11/`, `...2025-01/`
- cost-aware sweeps: `data/reports/backtests/20260628_072645_model_sweep_2024-07/`, `...2024-09/`, `...2024-11/`, `...2025-01/`
- baseline support-aware selection: `data/reports/backtests/20260628_072821_model_candidate_selection/`
- combined gate `60/60`: `data/reports/backtests/20260628_072839_model_candidate_selection/`
- combined gate `60/65`: `data/reports/backtests/20260628_073009_model_candidate_selection/`

Baseline selection without combined gate:

| eligible | pre-plateau | top entry | top short offset | top hold cap | cost min pnl | base min pnl | support |
|---:|---:|---:|---:|---:|---:|---:|---:|
| `13` | `21` | `5` | `12` | `720` | `58.2310` | `67.5110` | `1` |

Combined gate sensitivity:

| combined gate | direction combined gate | eligible | pre-plateau | top entry | top short offset | top hold cap | cost min pnl |
|---:|---:|---:|---:|---:|---:|---:|---:|
| `60` | `60` | `0` | `13` | n/a | n/a | n/a | n/a |
| `60` | `65` | `3` | `16` | `5` | `20` | `480` | `45.4484` |
| `80` | `65` | `11` | `20` | `10` | `8` | `480` | `55.8644` |
| `100` | `65` | `13` | `21` | `5` | `12` | `720` | `58.2310` |

Selected combined-gate candidate:

| entry | short offset | profit threshold | max hold min | cost min pnl | base min pnl | min trades | forced max | max drawdown | combined min | direction combined min | support |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `5` | `20` | `0.4` | `480` | `45.4484` | `50.7284` | `22` | `0.000000` | `67.1084` | `-56.3772` | `-60.2384` | `2` |

## 2024-12 Holdout

Artifact:

- backtest: `data/reports/backtests/20260628_073040_model_timed_ev_2024-12/`
- analysis: `data/reports/backtests/20260628_073055_holdout_2024_12_combined_gate_top/`

Result:

| metric | value |
|---|---:|
| adjusted pnl | `-149.7354` |
| raw pnl | `-109.3520` |
| trades | `33` |
| win rate | `0.4545` |
| profit factor | `0.3820` |
| max drawdown | `176.6504` |
| forced exits | `2` |

Failure analysis:

| metric | value |
|---|---:|
| long adjusted pnl | `-116.2186` |
| short adjusted pnl | `-33.5168` |
| direction error rate | `0.575758` |
| predicted side error rate | `0.575758` |
| exit regret mean | `16.019952` |
| EV overestimate vs realized mean | `21.857830` |
| profit barrier miss trades | `25` |
| profit barrier miss adjusted pnl | `-184.2444` |

## Decision

combined regime gateは診断軸として残すが、今回の候補は採用しない。

理由:

- `60/65` gateはvalidation候補を絞れたが、2024-12 holdoutではbaseline delay1候補より悪化した。
- forced exitは主因ではなく、direction error、profit barrier miss、EV overestimateが主因のまま残った。
- regime別の過去損失をhard gateにするだけでは、未知月のside/entry calibration崩れを吸収できない。

## Next Actions

1. exit-event datasetを2025-02以降にも拡張し、2024-12単月に過度に反応しないwalk-forward検証へ戻す。
2. `combined_regime` gateはhard採用ではなく、candidate tie-break / failure analysisとして使う。
3. 次はside/entry calibrationを直接扱う。特に `actual_best_side`, profit barrier miss, EV overestimateを教師信号またはcalibration targetにする。
4. low-vol/range/londonのような崩れはpost-hoc blockではなく、OOFで学習した「入る価値の低さ」として扱う。
5. 2024-12は候補固定後の反証月として扱い、見た後に閾値を再選択しすぎない。
