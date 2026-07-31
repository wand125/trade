# Shared MLP Regression Smoke

日時: 2026-06-28 20:01 JST
更新日時: 2026-06-28 20:01 JST

## 目的

HGBのtarget独立fitでは、dense entry quality targetやexit timing targetがEV予測の表現改善に直接効かない。次の本流として、共有表現を持つ小型MLPで複数回帰targetを同時学習できる基盤を追加する。

Report numbering note: this file is numbered from the internal file `日時`, not filesystem mtime or `更新日時`. Latest-report checks and renumbering must use the internal `日時`.

## 実装

`trade_data.modeling` に `train-shared-mlp` を追加した。

- scikit-learn `MLPRegressor` を `StandardScaler` と `TransformedTargetRegressor` で包む。
- 1つのmulti-output regressorで回帰targetを同時出力する。
- `target-set` は既存定義を使うが、classification targetはこのprototypeでは学習しない。
- HGBと同じく `predictions_train.parquet`, `predictions_valid.parquet`, `predictions_test.parquet`, `metrics.json`, `report.md` を保存する。
- EV列が含まれる場合は、既存のlinear EV calibrationとoracle-exit selection metricsも保存する。

この段階ではPyTorch/TCNではなく、依存を増やさない最小のshared representation smokeとする。

## Smoke

コマンド:

```bash
python3 -m trade_data.modeling train-shared-mlp \
  --dataset-dir data/processed/datasets/xauusd_m1_p1_l1p2_policy_combined \
  --train-months 2024-07 \
  --valid-months 2024-09 \
  --test-months 2024-12 \
  --target-set policy \
  --sample-frac 0.02 \
  --max-iter 3 \
  --hidden-layers 8 \
  --alpha 0.01 \
  --learning-rate-init 0.001 \
  --entry-threshold 10 \
  --purge-label-overlap true \
  --embargo-hours 24 \
  --label shared_mlp_policy_smoke
```

結果:

| item | value |
|---|---:|
| train rows after sampling/purge | `632` |
| valid rows | `28885` |
| test rows | `28763` |
| regression targets | `19` |
| hidden layers | `8` |
| n_iter | `3/3` |
| validation score final | `-0.316513` |

`max_iter=3` に張り付いており、これは性能実験ではなく接続smokeである。

Oracle-exit selection metrics:

| split | ev | selected trades | oracle-exit pnl | side accuracy |
|---|---|---:|---:|---:|
| valid | raw | `22846` | `399059.9712` | `0.5680` |
| test | raw | `23723` | `298848.3864` | `0.4839` |
| test | calibrated | `28763` | `358828.8998` | `0.4744` |

## Executable Backtest Smoke

生成したtest predictionを `timed_ev` に接続した。

```bash
python3 -m trade_data.backtest model-policy \
  --month 2024-12 \
  --predictions experiments/20260628_110048_shared_mlp_policy_smoke/predictions_test.parquet \
  --policy timed_ev \
  --entry-threshold 10 \
  --side-margin 1 \
  --long-holding-column pred_long_exit_event_minutes \
  --short-holding-column pred_short_exit_event_minutes \
  --min-predicted-hold-minutes 1 \
  --max-predicted-hold-minutes 720 \
  --output-dir data/reports/backtests/shared_mlp_policy_smoke
```

| metric | value |
|---|---:|
| adjusted pnl | `-88.1778` |
| raw pnl | `19.2880` |
| trades | `689` |
| win rate | `0.6967` |
| profit factor | `0.8632` |
| max drawdown | `155.4504` |
| forced exits | `5` |
| signal long / short / flat | `24841 / 899 / 12456` |

raw pnlはプラスだが、取引数が多すぎてコスト込みでNoTradeに負ける。long signalに大きく偏っている。これは極小smokeなので採用可否ではなく、今後の本実験でturnover制御とside balanceを必ず見るための注意点とする。

## 判断

shared MLP regression基盤は追加できた。現時点では標準policyへ昇格しない。

次の本実験では、最低でも次を満たす必要がある。

- 代表validation 4foldで同じCLIを使う。
- `sample-frac=1.0` または十分大きいsampleで学習する。
- `max_iter` / `early_stopping` / `validation_score` を記録する。
- executable backtestで取引数、turnover、side share、drawdown、forced exitを比較する。
- classification probabilityが必要なexit-event/profit-barrier policyとは、HGB classifierとのhybridかshared classifier追加を分けて検証する。

## Artifacts

- MLP smoke model: `experiments/20260628_110048_shared_mlp_policy_smoke/`
- 2024-12 executable smoke: `data/reports/backtests/shared_mlp_policy_smoke/20260628_110101_model_timed_ev_2024-12/`
