# HGB Multi-task Initial Model

## Summary

- Experiment ID: `2026-06-28_hgb_multitask_initial`
- Datetime: 2026-06-28 02:22 JST
- Status: completed
- Main result: 初回の軽量 multi-task モデルを固定 split で学習し、entry/side ranking の暫定基準を作った。

## Purpose

深層学習へ進む前に、情報量を落としすぎない target 設計が最低限の予測力を持つか確認する。3クラス分類単独ではなく、long/short の期待 adjusted pnl と side_score を主に見る。

## Data Split

- train: 2024-01 から 2024-06
- valid: 2024-07
- test: 2025-01
- horizon: 24 hours
- min adjusted edge: 15
- feature count: 47

Rows:

| split | rows |
|---|---:|
| train | 175,754 |
| valid | 31,587 |
| test | 30,197 |

## Model

- Implementation: `src/trade_data/modeling.py`
- Model family: scikit-learn `HistGradientBoostingRegressor` / `HistGradientBoostingClassifier`
- max_iter: 80
- learning_rate: 0.05
- max_leaf_nodes: 31
- random_seed: 7

Regression targets:

- `long_best_adjusted_pnl`
- `short_best_adjusted_pnl`
- `side_score`

Classification targets:

- `best_adjusted_pnl_quantile`
- `side_score_quantile`
- `label`

Command:

```bash
python3 -m trade_data.modeling train \
  --train-start 2024-01 --train-end 2024-06 \
  --valid-start 2024-07 --valid-end 2024-07 \
  --test-start 2025-01 --test-end 2025-01 \
  --min-adjusted-edge 15 \
  --max-iter 80 \
  --learning-rate 0.05 \
  --entry-threshold 15
```

## Artifacts

- `experiments/20260627_171852_hgb_multitask_edge15/metrics.json`
- `experiments/20260627_171852_hgb_multitask_edge15/report.md`
- `experiments/20260627_171852_hgb_multitask_edge15/models/`
- `experiments/20260627_171852_hgb_multitask_edge15/predictions_train.parquet`
- `experiments/20260627_171852_hgb_multitask_edge15/predictions_valid.parquet`
- `experiments/20260627_171852_hgb_multitask_edge15/predictions_test.parquet`

## Selection Metrics

This metric selects long or short from predicted long/short adjusted pnl and enters only when the predicted best side is above 15. It still uses oracle exits from the label data, so this is not an executable backtest result.

| split | selected trades | oracle-exit adjusted pnl | avg pnl | side acc | oracle upper bound |
|---|---:|---:|---:|---:|---:|
| train | 67,942 | 1,786,652.8970 | 26.2967 | 0.8215 | 2,782,398.7647 |
| valid | 14,741 | 217,820.3601 | 14.7765 | 0.5207 | 654,072.1218 |
| test | 22,589 | 319,595.3148 | 14.1483 | 0.5636 | 500,932.7370 |

## Classification Metrics

| split | label accuracy | label balanced accuracy | label macro F1 |
|---|---:|---:|---:|
| train | 0.7978 | 0.7804 | 0.7885 |
| valid | 0.4401 | 0.4443 | 0.4351 |
| test | 0.4502 | 0.4383 | 0.4200 |

## Regression R2

| split | long best pnl | short best pnl | side score |
|---|---:|---:|---:|
| train | 0.4225 | 0.4595 | 0.3209 |
| valid | -0.1282 | 0.0033 | -0.0642 |
| test | 0.0049 | -1.5642 | -0.5043 |

## Findings

- train と valid/test の差が大きく、期間依存または過学習が強い。
- 3クラス label の macro F1 は valid/test で 0.42 から 0.44 程度に落ちる。
- test の selected side accuracy は 0.5636 だが、valid は 0.5207 なので安定した優位性とはまだ言えない。
- `short_best_adjusted_pnl` と `side_score` の test R2 が悪く、2025-01 の short 側分布が学習期間とずれている可能性がある。
- oracle exit を使う selection metric は上限寄りの評価であり、取引ルール上の利益とは別物。

## Next Actions

- モデル予測だけを使う executable backtest policy を作る。
- exit timing target を学習し、予測 holding minutes または exit utility で決済する。
- walk-forward split を増やし、2024-08 以降や 2025 の別月で安定性を見る。
- HGB の過学習対策として `max_leaf_nodes`, `l2_regularization`, `min_samples_leaf`, `sample_frac` を比較する。
- 深層学習では連続値回帰、分位点分類、time-bin分類を同時に最適化する。
