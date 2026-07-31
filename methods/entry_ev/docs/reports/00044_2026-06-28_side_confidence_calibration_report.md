# Side Confidence Calibration Report

日時: 2026-06-28 16:55 JST
更新日時: 2026-06-28 16:55 JST

## Summary

- Experiment ID: `20260628_075447_side_confidence_smoke`
- Status: diagnostic infrastructure added
- Main result: `best_side` probability is overconfident overall. Across valid+test, mean confidence is `0.5861` while accuracy is `0.5089`; 2024-12 test is worse with accuracy `0.4770` and overconfidence `0.1074`.
- Report numbering note: this file is numbered from the internal `日時`, not filesystem mtime or `更新日時`.

## What Changed

Added `trade_data.modeling side-confidence-report`.

The command reads one or more prediction parquet files and writes:

- `summary.json`
- `group_metrics.csv`
- `bucket_metrics.csv`
- `worst_groups.csv`

It summarizes:

- predicted best side
- side confidence
- side accuracy
- balanced accuracy
- confidence minus realized hit rate
- overconfidence / underconfidence
- predicted vs actual long share
- high-confidence share

## Command

```bash
python3 -m trade_data.modeling side-confidence-report \
  --predictions experiments/20260628_074412_best_side_confidence_smoke/predictions_valid.parquet \
  --predictions experiments/20260628_074412_best_side_confidence_smoke/predictions_test.parquet \
  --output-dir data/reports/modeling \
  --label side_confidence_smoke \
  --min-group-rows 500 \
  --bucket-count 5 \
  --top-n 12
```

## Artifacts

- Report directory: `data/reports/modeling/20260628_075447_side_confidence_smoke/`
- Inputs:
  - `experiments/20260628_074412_best_side_confidence_smoke/predictions_valid.parquet`
  - `experiments/20260628_074412_best_side_confidence_smoke/predictions_test.parquet`

## Overall Metrics

| scope | rows | accuracy | balanced accuracy | confidence mean | overconfidence | predicted long share | actual long share |
|---|---:|---:|---:|---:|---:|---:|---:|
| valid+test | 54,725 | 0.5089 | 0.5119 | 0.5861 | 0.0772 | 0.5819 | 0.4821 |
| valid | 25,962 | 0.5443 | 0.5464 | 0.5880 | 0.0437 | 0.6132 | 0.4908 |
| test | 28,763 | 0.4770 | 0.4797 | 0.5844 | 0.1074 | 0.5538 | 0.4744 |

## Worst Groups

| group | rows | accuracy | confidence | overconfidence | note |
|---|---:|---:|---:|---:|---|
| test `range_normal_vol` | 2,075 | 0.3817 | 0.5771 | 0.1954 | below-random side choice despite moderate confidence |
| test `london` | 7,559 | 0.4046 | 0.5806 | 0.1760 | large test-only side failure |
| valid `down_low_vol` | 3,204 | 0.4498 | 0.6192 | 0.1694 | predicted long share `0.8361` vs actual long share `0.4607` |
| valid `rollover` | 1,080 | 0.4148 | 0.5688 | 0.1540 | low accuracy even without high confidence |
| valid `down` | 6,505 | 0.4586 | 0.6106 | 0.1520 | strong long bias in down trend |

## Bucket Findings

Confidence buckets reveal the main problem:

| split | bucket | rows | accuracy | confidence | overconfidence |
|---|---|---:|---:|---:|---:|
| test | 0.50-0.60 | 18,038 | 0.5038 | 0.5424 | 0.0386 |
| test | 0.60-0.70 | 8,894 | 0.4359 | 0.6372 | 0.2013 |
| test | 0.70-0.80 | 1,643 | 0.3920 | 0.7322 | 0.3402 |
| valid | 0.50-0.60 | 15,721 | 0.5302 | 0.5448 | 0.0146 |
| valid | 0.60-0.70 | 8,639 | 0.5685 | 0.6383 | 0.0698 |
| valid | 0.70-0.80 | 1,508 | 0.5325 | 0.7348 | 0.2023 |

In 2024-12 test, higher confidence is often worse. This contradicts a simple confidence threshold policy.

## Interpretation

- `best_side` probability is currently not calibrated enough for hard gating.
- In down/low-vol and test London/range-normal-vol regimes, the classifier can become confidently wrong.
- The issue is not just low-confidence noise. Some high-confidence bins are more overfit than low-confidence bins.
- Future side calibration should be regime-aware and OOF-based. A global threshold like `min_side_confidence=0.6` is likely to select overfit trades.

## Next Actions

- Run this diagnostic on walk-forward OOF predictions after regenerating broader `best_side` datasets.
- Try group-wise shrinkage or isotonic/logistic calibration on OOF `best_side` probabilities, but evaluate through executable backtest, not classification alone.
- Consider a side-confidence penalty that is regime-aware rather than global.
- Track whether high confidence remains inversely predictive in 2024-12 after using more training months.
