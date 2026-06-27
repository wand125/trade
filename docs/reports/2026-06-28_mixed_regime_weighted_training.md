# Mixed-Regime Weighted Training

日付: 2026-06-28 JST

## 目的

直近の down-regime fold で、従来候補が 2024-12 test に大きく負けた。単純な policy threshold 調整ではなく、学習データの作り方を改善する。

仮説:

- 連続した一部期間だけのtrainでは、長期的に正しいアルゴリズムになりにくい。
- 月ごとの局面差と label imbalance が、EV予測とexit timingを歪めている。
- 非連続の複数局面をtrainに混ぜ、月×ラベルでsample weightを揃えると、validation上の局面耐性が上がる。

## 実装

追加:

- `--train-months`, `--valid-months`, `--test-months`
- `--sample-weighting none|month|label|month_label`

`month_label` は、各 `dataset_month × label` セルの総重みを揃える。これにより、特定月や多数派ラベルが学習を支配しにくくなる。

## Split

Train months:

```text
2023-01, 2023-02, 2023-03, 2023-04, 2023-05, 2023-06,
2023-07, 2023-08, 2023-09, 2023-10, 2023-11, 2023-12,
2024-01, 2024-02, 2024-03, 2024-04, 2024-05, 2024-06,
2024-08, 2024-10
```

Validation months:

```text
2024-07, 2024-09, 2024-11, 2025-01
```

Test months:

```text
2024-12, 2025-02
```

## Model

Artifact:

- `experiments/20260627_185200_hgb_multitask_edge15/`

Settings:

- model: HistGradientBoosting multi-task
- train target: old multipliers 0.9 / 1.3
- validation/test evaluation: relaxed multipliers 1.0 / 1.25
- max iter: 80
- learning rate: 0.03
- max leaf nodes: 15
- min samples leaf: 100
- l2 regularization: 0.2
- target clip quantile: 0.99
- sample weighting: `month_label`

## Validation

Sweep artifacts:

- `data/reports/backtests/20260627_185215_model_sweep_2024-07/`
- `data/reports/backtests/20260627_185412_model_sweep_2024-09/`
- `data/reports/backtests/20260627_185609_model_sweep_2024-11/`
- `data/reports/backtests/20260627_185805_model_sweep_2025-01/`

Strict summary:

- artifact: `data/reports/backtests/20260627_185959_model_sweep_summary/`
- constraints: forced exit rate 0, max drawdown 100, min pnl per fold 0
- result: eligible candidate なし

Relaxed summary:

- artifact: `data/reports/backtests/20260627_190009_model_sweep_summary/`
- constraints: forced exit rate <= 0.1, max drawdown <= 150, min pnl per fold 0
- selected candidate: `timed_ev`, entry 10, exit 0, side margin 5, risk penalty 0.4

Selected validation metrics:

| metric | value |
|---|---:|
| mean adjusted pnl | 146.0508 |
| min adjusted pnl | 73.0053 |
| sum adjusted pnl | 584.2030 |
| mean trades | 47.75 |
| min trades | 42 |
| max drawdown | 124.0158 |
| max forced exit rate | 0.0213 |

2024-11 validation improved compared with the previous standard candidate. The selected candidate had positive short-side P/L in that down month.

## Test

Selected candidate was fixed from validation and applied to test months.

Artifacts:

- `data/reports/backtests/20260627_190023_model_timed_ev_2024-12/`
- `data/reports/backtests/20260627_190023_model_timed_ev_2025-02/`

| test month | adjusted pnl | raw pnl | trades | profit factor | max DD | forced exits | long pnl | short pnl |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2024-12 | -183.5370 | -116.2770 | 52 | 0.4542 | 214.6258 | 2 | -128.3435 | -55.1935 |
| 2025-02 | 54.9137 | 103.1370 | 45 | 1.2277 | 100.7745 | 0 | 54.0967 | 0.8170 |

## 判断

学習データ混合と `month_label` weighting は、validationの下落月には効いた。しかし、2024-12 test には汎化しなかった。

つまり、現時点では学習品質はまだ不十分。改善は見えたが、testで判明した過学習問題は解決していない。

次は以下を優先する。

- oracle best exit target だけでなく、fixed horizon return と barrier hit probability を教師に加える。
- long/short 別、regime 別のEV calibrationを行う。
- regime feature を追加する。
- validation summary に方向別P/Lとdirection exposure制約を入れる。
