# Profit Barrier Calibration Candidate Gate

日時: 2026-06-28 10:21 JST
更新日時: 2026-06-28 10:21 JST

## 目的

前回追加した profit barrier miss率では、`require_profit_barrier=true` かつ threshold通過後の候補がすべて `predicted_profit_barrier_miss_rate=0.0` になり、確率過大評価を見抜けなかった。

今回は、取ったsideの predicted profit barrier probability をbucket分けし、bucketごとのactual hit rateを標準metricsへ入れる。

狙いは、単なるhit/missではなく次を見ること。

- predicted probability bucketごとのactual hit rate
- predicted meanとactual hit rateの差
- 最大過大評価bucket
- candidate selectionで過大評価の大きい候補を落とせるか

## 実装

`model-policy` / `model-sweep` metricsに以下を追加した。

- `profit_barrier_calibration_observed_count`
- `profit_barrier_calibration_bucket_count`
- `profit_barrier_calibration_overestimate_max`
- `profit_barrier_calibration_abs_error_max`
- `worst_profit_barrier_calibration_bucket`
- `worst_profit_barrier_calibration_bucket_count`
- `worst_profit_barrier_calibration_predicted_mean`
- `worst_profit_barrier_calibration_actual_hit_rate`
- `worst_profit_barrier_calibration_overestimate`
- `profit_barrier_calibration_0p0_0p2_*`
- `profit_barrier_calibration_0p2_0p4_*`
- `profit_barrier_calibration_0p4_0p6_*`
- `profit_barrier_calibration_0p6_0p8_*`
- `profit_barrier_calibration_0p8_1p0_*`

`model-candidate-selection` には以下を追加した。

- `--max-profit-barrier-calibration-overestimate`

候補選択のsummaryは横に広くなりすぎないよう、bucket詳細は `model-sweep` metricsに残し、candidate selectionではsummary列だけを集計する。

## Smoke

対象:

- model: `experiments/20260628_003756_full_fixed_horizon_blind_2025_05_barrier_prob_p1_l1p2/`
- month: `2025-05`
- policy: `fixed_horizon_ev`
- entry threshold: `0`
- short offset: `6`
- side margin: `1`
- max wait regret: `4`
- min entry rank: `0.5`
- barrier threshold: `0.40`
- extra margin: `session_regime=asia:5,session_regime=rollover:5`
- cost case: spread `0.1`, slippage `0.05`, delay `0`

Artifacts:

- no-cost no block sweep: `data/reports/backtests/20260628_011416_model_sweep_2025-05_2/`
- no-cost asia short block sweep: `data/reports/backtests/20260628_011416_model_sweep_2025-05_1/`
- cost no block sweep: `data/reports/backtests/20260628_011416_model_sweep_2025-05_3/`
- cost asia short block sweep: `data/reports/backtests/20260628_011416_model_sweep_2025-05/`
- candidate selection: `data/reports/backtests/20260628_011509_model_candidate_selection/`

## 結果

No block:

- adjusted pnl: `-57.6474`
- trades: `34`
- `actual_profit_barrier_miss_rate`: `0.5000`
- `profit_barrier_calibration_overestimate_max`: `0.054305`
- worst bucket: `0.6-0.8`
- worst bucket count: `5`
- worst bucket predicted mean: `0.654305`
- worst bucket actual hit rate: `0.600000`

`short:session_regime=asia` block:

- adjusted pnl: `+83.0630`
- trades: `28`
- `actual_profit_barrier_miss_rate`: `0.464286`
- `profit_barrier_calibration_overestimate_max`: `0.248089`
- worst bucket: `0.6-0.8`
- worst bucket count: `7`
- worst bucket predicted mean: `0.676661`
- worst bucket actual hit rate: `0.428571`

Candidate selection smoke:

- `--max-profit-barrier-calibration-overestimate 0.2`
- direction/session loss gateは緩めた。
- actual/predicted barrier miss rate gateも緩めた。

結果:

| side block | base pnl | cost pnl | actual miss max | calibration overestimate max | calibration ok | eligible |
|---|---:|---:|---:|---:|---|---|
| none | `-57.6474` | `-65.0034` | `0.500000` | `0.054305` | true | true |
| `short:session_regime=asia` | `+83.0630` | `+77.0270` | `0.464286` | `0.248089` | false | false |

## 判断

calibration gateは実装上は機能する。0.6-0.8 bucketで、blockあり候補の predicted mean `0.676661` に対してactual hit rateが `0.428571` まで落ちており、barrier probabilityの過大評価を検出できた。

ただし、このsmokeではPnLが良いblockあり候補のほうがcalibration overestimateは悪い。したがって `--max-profit-barrier-calibration-overestimate 0.2` を採用閾値として使うのは早い。現時点では、採用gateではなく診断軸として扱う。

次は、validation fold全体でcalibration overestimateの台地を見る。特に、PnL、direction/session損失、actual miss率、calibration overestimateのどれをhard gateにし、どれを診断値に留めるかを分ける。

## 検証

- `python3 -m py_compile src/trade_data/backtest.py`: OK
- `python3 -m unittest tests.test_backtest`: 30 tests OK
- `python3 -m unittest discover tests`: 66 tests OK
- `model-candidate-selection --help`: OK
- `model-sweep --help`: OK
