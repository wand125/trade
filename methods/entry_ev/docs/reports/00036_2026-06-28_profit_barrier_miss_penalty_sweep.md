# Profit Barrier Miss Penalty Sweep

日時: 2026-06-28 14:39 JST
更新日時: 2026-06-28 14:39 JST

## Summary

- Experiment ID: `profit_barrier_miss_penalty_sweep`
- Status: implemented and validation-tested
- Main result: profit barrier hit probabilityを `1 - p` で線形penalty化する探索軸を追加したが、validation 4foldでは非zero penaltyが全てstrict candidate selectionから落ちた。標準候補は raw fixed horizon + `score_mode=max` + penalty `0.0` を維持する。
- Report numbering note: this file is numbered by the internal `日時`, not by file update time or `更新日時`.

## Motivation

前回のOOF calibrationは、fixed horizon target全体のbias補正としては有効だったが、実際にentryされるtradeのEV過大評価とprofit barrier missを下げられなかった。

そこで今回は、候補選択時のentry scoreに対して、side別profit barrier hit probabilityが低いほどEVを下げるpenaltyを入れた。

```text
long_score  = long_ev  - penalty * clip(1 - long_profit_barrier_hit_probability, 0, 1)
short_score = short_ev - penalty * clip(1 - short_profit_barrier_hit_probability, 0, 1)
```

これは「profit barrierを踏みにくい予測をentry候補から落とす」ための単純なsoft gateであり、成功すればhard thresholdより滑らかにtrade qualityを上げられる。

## Implementation

追加:

- `ModelPolicyConfig.profit_barrier_miss_penalty`
- `model-policy --profit-barrier-miss-penalty`
- `model-sweep --profit-barrier-miss-penalties`
- `SWEEP_KEY_COLUMNS` に `profit_barrier_miss_penalty`
- 古いsweep metricsには `profit_barrier_miss_penalty=0.0` を補完

変更ファイル:

- `src/trade_data/backtest.py`
- `tests/test_backtest.py`

## Sweep Setup

Base predictions:

- `experiments/20260628_040828_policy_timebarrier_p1_l1p2/predictions_valid.parquet`

Validation months:

- `2024-07`
- `2024-09`
- `2024-11`
- `2025-01`

Policy setup:

- policy: `fixed_horizon_ev`
- fixed horizon score mode: `max`
- entry threshold: `0`
- long offset: `0`
- short offsets: `4`, `8`
- side margin: `1`
- risk penalty: `0`
- profit barrier miss penalties: `0`, `2`, `4`, `6`, `8`
- max wait regret: `4`
- min entry rank: `0`, `0.5`
- profit barrier probability: 24h `pred_long_profit_barrier_hit_prob`, `pred_short_profit_barrier_hit_prob`
- profit barrier thresholds: `0.0`, `0.2`
- extra margin: `session_regime=asia:5`, `session_regime=rollover:5`

Candidate gates:

- min folds: `4`
- min trades per fold: `10`
- max forced exit rate: `0.05`
- max drawdown: `100`
- min base/cost adjusted pnl per fold: `0`
- max direction/session loss per fold: `60`
- max short trade share: `0.65`
- max smoothed actual barrier miss: `0.55`

Cost cases:

- standard delay 0: spread `0.1`, slippage `0.05`, delay `0`
- stricter diagnostic delay 1: spread `0.1`, slippage `0.05`, delay `1`

## Results

Standard cost case, delay `0`:

| penalty | eligible | base min pnl | cost min pnl | min trades | forced exit max | max drawdown | worst dir/session | short share max | smoothed miss max | EV overestimate max | exit regret max |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `0.0` | 7 | `39.7538` | `27.2158` | 47 | `0.0000` | `69.0110` | `-39.1342` | `0.170213` | `0.454545` | `15.692745` | `25.465302` |
| `2.0` | 0 | `-28.7360` | `-57.6296` | 73 | `0.0000` | `73.3278` | `-68.9736` | `0.067308` | `0.650943` | `16.381976` | `24.316077` |
| `4.0` | 0 | `-10.9996` | `-13.8696` | 13 | `0.0000` | `50.8532` | `-23.8684` | `0.400000` | `0.745455` | `19.669432` | `23.532020` |
| `6.0` | 0 | `0.0000` | `-0.0624` | 0 | `0.0000` | `1.6440` | `-0.8124` | `0.600000` | `0.714286` | `18.464942` | `20.801100` |
| `8.0` | 0 | `0.0000` | `0.0000` | 0 | `0.0000` | `0.4620` | `0.0000` | `1.000000` | `0.500000` | `25.137611` | `18.778500` |

Stricter diagnostic cost case, delay `1`:

| penalty | eligible | base min pnl | cost min pnl | min trades | forced exit max | max drawdown | worst dir/session | short share max | smoothed miss max | EV overestimate max | exit regret max |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `0.0` | 7 | `32.8776` | `23.4720` | 48 | `0.0000` | `70.4524` | `-38.9090` | `0.187500` | `0.492308` | `14.766051` | `25.705279` |
| `2.0` | 0 | `-50.6908` | `-50.7946` | 73 | `0.0000` | `103.4936` | `-69.3410` | `0.243697` | `0.677686` | `18.143508` | `23.464597` |
| `4.0` | 0 | `-10.9290` | `-13.3438` | 8 | `0.0000` | `42.8860` | `-23.5350` | `0.444444` | `0.755102` | `19.234509` | `24.470963` |
| `6.0` | 0 | `0.0000` | `0.0000` | 0 | `0.0000` | `1.7280` | `-0.7880` | `0.600000` | `0.714286` | `18.737302` | `20.768500` |
| `8.0` | 0 | `0.0000` | `-1.5360` | 0 | `0.0000` | `2.4060` | `-2.4060` | `1.000000` | `0.500000` | `25.418111` | `19.637000` |

## Interpretation

線形penaltyは、今回のgridでは期待した効果を出さなかった。

- penalty `2.0` はtrade数を保ったまま、profit barrier missとdirection/session損失を悪化させた。
- penalty `4.0` 以上は候補を薄くしすぎ、月10trades条件を満たさない月が出る。
- EV overestimateは明確に下がらず、むしろpenaltyありのbest rowでは悪化した。
- short shareを下げるだけでは十分でなく、long側の低quality entryも残る。
- 現行のEV overestimate診断は、entryに使ったpenalty後scoreではなく、選択されたtradeのraw予測EVと実現PnLの差を見ている。したがってこの結果は「penalty後scoreの校正失敗」というより、「penaltyで選ばれたtrade集合の実現品質が改善しない」という意味で読む。

これは、profit barrier hit probabilityを直接 `1 - p` で引く形が粗すぎることを示している。確率のcalibrationが十分でない状態で線形penaltyをかけると、単にentry分布を歪め、未知foldのPnLを改善しない。

## Decision

- `profit_barrier_miss_penalty` の実装は探索軸として残す。
- 標準設定では `profit_barrier_miss_penalty=0.0` を維持する。
- 非zero penalty `2/4/6/8` は現validation 4foldでは採用しない。
- 次は、selected tradesの実現PnL、actual barrier miss、exit regretを直接targetにした二段階モデル、またはhazard/survival型exit timing targetを優先する。

## Artifacts

- No-cost sweeps:
  - `data/reports/backtests/20260628_053518_model_sweep_2024-07/`
  - `data/reports/backtests/20260628_053518_model_sweep_2024-09/`
  - `data/reports/backtests/20260628_053518_model_sweep_2024-11/`
  - `data/reports/backtests/20260628_053518_model_sweep_2025-01/`
- Cost sweeps, delay `0`:
  - `data/reports/backtests/20260628_053731_model_sweep_2024-07/`
  - `data/reports/backtests/20260628_053731_model_sweep_2024-09/`
  - `data/reports/backtests/20260628_053731_model_sweep_2024-11/`
  - `data/reports/backtests/20260628_053731_model_sweep_2025-01/`
- Candidate selection, delay `0`: `data/reports/backtests/20260628_053757_model_candidate_selection/`
- Cost sweeps, delay `1`:
  - `data/reports/backtests/20260628_053602_model_sweep_2024-07/`
  - `data/reports/backtests/20260628_053602_model_sweep_2024-09/`
  - `data/reports/backtests/20260628_053602_model_sweep_2024-11/`
  - `data/reports/backtests/20260628_053602_model_sweep_2025-01/`
- Candidate selection, delay `1`: `data/reports/backtests/20260628_053630_model_candidate_selection/`

## Verification

- `python3 -m unittest tests.test_backtest`: OK
