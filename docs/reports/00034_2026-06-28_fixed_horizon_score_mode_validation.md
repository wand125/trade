# Fixed Horizon Score Mode Validation

日時: 2026-06-28 14:10 JST
更新日時: 2026-06-28 14:12 JST

## Summary

- Experiment ID: `fixed_horizon_score_mode_validation`
- Status: implemented and validation-tested
- Main result: `fixed_horizon_ev` に `max/mean/median/min` のscore aggregation modeを追加したが、validation 4foldでは従来の `max` だけがeligibleに残った。単純な保守的集約は採用しない。
- Report numbering note: this file is numbered by the internal `日時`, not by file update time or `更新日時`.

## Motivation

前回のtime-limited profit barrier probabilityは、binary classifierとしての識別力が弱く、hard gateに昇格できなかった。

残っている弱点は、exit timing と EV overestimate。現行の `fixed_horizon_ev` は 60m / 240m / 720m の固定horizon予測から最大値をentry scoreにするため、構造的に楽観寄りになる可能性がある。

そこで、固定horizon列の集約を切り替えられるようにした。

| mode | entry score | planned exit time |
|---|---|---|
| `max` | horizon予測の最大値 | 最大値を出したhorizon |
| `mean` | horizon予測の平均 | 最大値を出したhorizon |
| `median` | horizon予測の中央値 | 最大値を出したhorizon |
| `min` | horizon予測の最小値 | 最大値を出したhorizon |

保持時間は従来互換のため最大score horizonから取る。entry scoreだけを保守化し、「一部のhorizonだけ高い」予測を落とせるかを見る。

## Implementation

追加:

- `ModelPolicyConfig.fixed_horizon_score_mode`
- `model-policy --fixed-horizon-score-mode`
- `model-sweep --fixed-horizon-score-modes`
- `SWEEP_KEY_COLUMNS` に `fixed_horizon_score_mode`
- 古いsweep metricsには `fixed_horizon_score_mode=max` を補完

変更ファイル:

- `src/trade_data/backtest.py`
- `tests/test_backtest.py`

## Sweep Setup

既存の timebarrier policy model を使った。

- Predictions: `experiments/20260628_040828_policy_timebarrier_p1_l1p2/predictions_valid.parquet`
- Months: `2024-07`, `2024-09`, `2024-11`, `2025-01`
- Policy: `fixed_horizon_ev`
- Fixed horizon score modes: `max`, `mean`, `median`, `min`
- Entry threshold: `0`
- Long offset: `0`
- Short offsets: `4`, `8`
- Side margin: `1`
- Max wait regret: `4`
- Min entry rank: `0`, `0.5`
- Profit barrier probability: 24h `pred_long/short_profit_barrier_hit_prob`
- Profit barrier thresholds: `0.0`, `0.2`
- Extra margin: `session_regime=asia:5`, `session_regime=rollover:5`
- Cost case: spread `0.1`, slippage `0.05`, delay `0`

Candidate gates:

- min folds: `4`
- min trades per fold: `10`
- max forced exit rate: `0.05`
- max drawdown: `100`
- min base/cost adjusted pnl per fold: `0`
- max direction/session loss per fold: `60`
- max short trade share: `0.65`
- max smoothed actual barrier miss: `0.55`

## Results

Candidate selection:

| mode | eligible | top cost min pnl | top cost min trades | short share max | smoothed miss max | EV overestimate max | exit regret max |
|---|---:|---:|---:|---:|---:|---:|---:|
| `max` | 7 | `27.2158` | 47 | `0.170213` | `0.454545` | `15.692745` | `25.465302` |
| `mean` | 0 | `-57.7550` | 92 | `0.065217` | `0.595745` | `16.620512` | `22.515032` |
| `median` | 0 | `-53.7286` | 77 | `0.064935` | `0.475610` | `16.457595` | `22.309429` |
| `min` | 0 | `-46.6480` | 57 | `0.000000` | `0.609756` | `16.510913` | `21.548846` |

全sweep平均:

| cost case | mode | avg pnl | avg trades | avg short share | avg EV overestimate | avg exit regret |
|---|---|---:|---:|---:|---:|---:|
| no cost | `max` | `62.6514` | `71.25` | `0.1283` | `14.5381` | `19.3169` |
| no cost | `mean` | `6.8658` | `139.75` | `0.0079` | `14.6953` | `19.4529` |
| no cost | `median` | `1.7068` | `109.00` | `0.0075` | `14.6647` | `19.0900` |
| no cost | `min` | `-0.4708` | `80.25` | `0.0000` | `15.8195` | `18.1787` |
| cost | `max` | `47.2890` | `71.25` | `0.1283` | `14.7537` | `19.5325` |
| cost | `mean` | `-23.4563` | `139.75` | `0.0079` | `14.9121` | `19.6697` |
| cost | `median` | `-22.0206` | `109.00` | `0.0075` | `14.8821` | `19.3074` |
| cost | `min` | `-17.8276` | `80.25` | `0.0000` | `16.0359` | `18.3952` |

## Interpretation

単純な保守的horizon集約は、短期的には逆効果だった。

- `mean/median/min` は short exposure を強く落とし、ほぼlong-onlyに近づく。
- EV overestimate は大きく下がらない。
- exit regret は一部下がるが、cost-aware PnL の悪化を補えない。
- `mean/median` は取引数を増やすが、低quality long entryが増えてfold最低PnLを壊す。
- `min` は最も保守的だが、edgeが薄くなりすぎてNoTradeを超えられない。

したがって、`fixed_horizon_score_mode` は診断・ablation用に残すが、採用候補は従来の `max` のままにする。

## Verification

- `python3 -m unittest discover tests`: 73 tests OK
- `git diff --check`: OK
- `docs/reports` numbering check: 34 files OK, ordered by internal `日時`

## Artifacts

- Base sweeps:
  - `data/reports/backtests/20260628_050708_model_sweep_2024-07/`
  - `data/reports/backtests/20260628_050721_model_sweep_2024-09/`
  - `data/reports/backtests/20260628_050733_model_sweep_2024-11/`
  - `data/reports/backtests/20260628_050745_model_sweep_2025-01/`
- Cost sweeps:
  - `data/reports/backtests/20260628_050757_model_sweep_2024-07/`
  - `data/reports/backtests/20260628_050809_model_sweep_2024-09/`
  - `data/reports/backtests/20260628_050822_model_sweep_2024-11/`
  - `data/reports/backtests/20260628_050834_model_sweep_2025-01/`
- Candidate selection: `data/reports/backtests/20260628_050919_horizon_score_mode_candidate_selection/`
- Summary CSV: `data/reports/backtests/20260628_horizon_score_mode_candidate_selection_summary.csv`

## Next Actions

1. `fixed_horizon_score_mode=max` を維持し、単純な mean/median/min 集約は採用しない。
2. EV過大評価対策は、horizon集約ではなく、OOFで実現PnLに対する calibration/penalty を学習する方向へ進める。
3. shortを減らすだけではなく、long-only化で壊れるfoldを検出するため、dominant side share gateの使い方を再確認する。
4. 次のblind前に、候補固定基準を再度書き出す。
