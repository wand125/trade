# Fixed Horizon OOF Calibration

日時: 2026-06-28 14:26 JST
更新日時: 2026-06-28 14:26 JST

## Summary

- Experiment ID: `fixed_horizon_oof_calibration`
- Status: implemented and validation-tested
- Main result: fixed horizon EV予測へOOF calibration基盤を追加した。全体bias補正は予測targetのbiasを大きく減らしたが、trade selection上のEV過大評価とprofit barrier missは解決しなかった。regime別補正はentry分布を壊したため採用しない。
- Report numbering note: this file is numbered by the internal `日時`, not by file update time or `更新日時`.

## Motivation

直近の弱点は、entry方向そのものよりも以下にある。

- exit timingの不安定さ
- fixed horizon EVの過大評価
- 予測EVが高いtradeだけを選んだ時の実現PnLとの乖離

前回の `fixed_horizon_score_mode=mean/median/min` は、単純な保守化としては効かず、short exposureを落としすぎた。今回はhorizon集約ではなく、60/240/720分の固定horizon targetごとにOOF calibrationを試した。

## Implementation

追加:

- `GroupTargetSpec`
- `GroupTargetCalibrator`
- `fixed_horizon_target_specs`
- `fit_group_target_calibrator`
- `add_group_calibrated_fixed_horizon_columns`
- `oof-fixed-horizon-calibration` CLI
- `tests/test_docs_reports.py`

生成列:

- `pred_regime_calibrated_long_fixed_60m_adjusted_pnl`
- `pred_regime_calibrated_long_fixed_240m_adjusted_pnl`
- `pred_regime_calibrated_long_fixed_720m_adjusted_pnl`
- `pred_regime_calibrated_short_fixed_60m_adjusted_pnl`
- `pred_regime_calibrated_short_fixed_240m_adjusted_pnl`
- `pred_regime_calibrated_short_fixed_720m_adjusted_pnl`

`docs/reports` の通し番号について、本文内 `日時` を基準に昇順で並んでいることを単体テストで確認するようにした。ファイル更新時刻や `更新日時` は採番基準に使わない。

## Setup

Base predictions:

- `experiments/20260628_040828_policy_timebarrier_p1_l1p2/predictions_valid.parquet`

Validation months:

- `2024-07`
- `2024-09`
- `2024-11`
- `2025-01`

Backtest policy:

- policy: `fixed_horizon_ev`
- fixed horizon score mode: `max`
- entry threshold: `0`
- long offset: `0`
- short offsets: `4`, `8`
- side margin: `1`
- max wait regret: `4`
- min entry rank: `0`, `0.5`
- profit barrier probability: 24h `pred_long/short_profit_barrier_hit`
- profit barrier thresholds: `0.0`, `0.2`
- extra margin: `session_regime=asia:1`, `session_regime=rollover:1`
- standard cost case: spread `0.1`, slippage `0.05`, delay `1`

Candidate gates:

- min folds: `4`
- min trades per fold: `10`
- max forced exit rate: `0.05`
- max drawdown: `100`
- min base/cost adjusted pnl per fold: `0`
- max direction/session loss per fold: `60`
- max short trade share: `0.65`
- max smoothed actual barrier miss: `0.55`

## Calibration Variants

| variant | group columns | prediction shrinkage | artifact |
|---|---|---:|---|
| regime calibration | `volatility_regime,session_regime` | `0.65` | `experiments/20260628_052021_fixed_horizon_oof_group_calib_p1_l1p2/` |
| global bias calibration | none | `1.0` | `experiments/20260628_052305_fixed_horizon_oof_global_bias_p1_l1p2/` |

OOF regression diagnostics:

| target | raw bias | regime calibrated bias | global calibrated bias |
|---|---:|---:|---:|
| long 60m | `-0.1333` | `+0.0455` | `-0.0024` |
| long 240m | `-0.5879` | `+0.1863` | `-0.0083` |
| long 720m | `-2.2631` | `+0.4106` | `-0.0192` |
| short 60m | `+0.1682` | `-0.0380` | `+0.0020` |
| short 240m | `+0.6783` | `-0.1596` | `+0.0076` |
| short 720m | `+2.3445` | `-0.3650` | `+0.0197` |

global bias calibrationはtarget平均のbias補正としては良い。一方で、これは全体分布のbiasであり、実際にentryされる上位score tradeの過大評価を直接下げるものではない。

## Candidate Selection Results

Strict gates:

| variant | eligible | top cost min pnl | min trades | forced exit max | smoothed miss max | EV overestimate max | exit regret max |
|---|---:|---:|---:|---:|---:|---:|---:|
| raw fixed horizon | 7 | `27.2158` | 47 | `0.000000` | `0.454545` | `15.692745` | `25.465302` |
| regime calibration | 0 | `9.3470` | 3 | `0.000000` | `0.666667` | `20.238968` | `26.133486` |
| global bias calibration | 0 | `38.0184` | 76 | `0.057471` | `0.617978` | `15.713636` | `21.938103` |

regime calibrationはtrade数が薄い候補か、profit-barrier missが悪い候補に寄った。entry分布を壊しているので採用しない。

global bias calibrationはcost min pnlだけならraw topを上回るが、strict gateでは forced exit と smoothed actual profit-barrier miss で落ちる。EV overestimateはraw top `15.692745` に対して `15.713636` で、ほぼ改善していない。

Relaxed diagnostic gates:

- max forced exit rate: `0.07`
- max drawdown: `160`
- max smoothed actual barrier miss: `0.62`

| variant | eligible | top cost min pnl | min trades | forced exit max | smoothed miss max | EV overestimate max | exit regret max |
|---|---:|---:|---:|---:|---:|---:|---:|
| global bias calibration | 3 | `38.0184` | 76 | `0.057471` | `0.617978` | `15.713636` | `21.938103` |

緩和すれば候補は出るが、これは「評価gateを緩めれば採用できる」だけで、主問題のEV過大評価とprofit-barrier missを解決したとは言えない。採用候補ではなく診断候補として扱う。

## Artifacts

- OOF regime calibration: `experiments/20260628_052021_fixed_horizon_oof_group_calib_p1_l1p2/`
- Regime strict selection: `data/reports/backtests/20260628_052218_model_candidate_selection/`
- OOF global bias calibration: `experiments/20260628_052305_fixed_horizon_oof_global_bias_p1_l1p2/`
- Global strict selection: `data/reports/backtests/20260628_052436_model_candidate_selection/`
- Global relaxed diagnostic selection: `data/reports/backtests/20260628_052503_model_candidate_selection/`
- Raw reference selection: `data/reports/backtests/20260628_050919_horizon_score_mode_candidate_selection/`

## Decision

- fixed horizon OOF calibrationのコード基盤は残す。
- regime別fixed horizon calibrationは採用しない。
- global bias calibrationは、target bias補正としては有効だが、現行のentry selectionではEV過大評価を下げないため採用保留。
- 現時点の標準候補選定は raw fixed horizon + `score_mode=max` を維持する。
- 次は、trade selection後の実現PnLに対するpenalty、profit-barrier missを直接下げるexit target、またはhazard/survival型exit timing targetへ進める。

## Verification

- `python3 -m unittest tests.test_meta_model`: OK
- `python3 -m unittest tests.test_docs_reports tests.test_meta_model`: OK
