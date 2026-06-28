# Side Confidence Target Weighting

日時: 2026-06-28 19:39 JST
更新日時: 2026-06-28 19:39 JST

## Summary

- Experiment ID: `side_confidence_target_weighting`
- Status: validated, not promoted
- Main result: `target-set side_confidence` を同一splitで再学習し、さらに `month_target` sample weightingを追加して `best_side` の月別class imbalanceを補正した。通常の専用モデルはpolicy内 `best_side` と完全に同じ結果で、現在のHGBはtargetごとに独立fitなので「multi-taskに混ぜたせいでsideが弱い」という仮説は否定的。`month_target` はbalanced accuracyとoverconfidenceをわずかに改善したが、`min_side_confidence=0.55` のvalidation 4foldを大きく壊したため採用しない。
- Report numbering note: this file is numbered from the internal file `日時`, not filesystem mtime or `更新日時`.

## Implementation

Added target-aware sample weighting to `trade_data.modeling`:

- `--sample-weighting target`
- `--sample-weighting month_target`

Behavior:

- classification targets use their own target class labels for balancing.
- `month_target` balances `dataset_month x target class`.
- regression targets fall back to no weighting for `target` and month weighting for `month_target`.
- existing `none`, `month`, `label`, `month_label` behavior is unchanged.

## Setup

Dataset:

- `data/processed/datasets/xauusd_m1_p1_l1p2_policy_combined/`
- Profit/loss multipliers: `1.0 / 1.2`
- Train months: `2023-01` to `2024-10`, excluding validation months and `2024-12`
- Validation months: `2024-07`, `2024-09`, `2024-11`, `2025-01`
- Test month: `2024-12`

Models:

| label | target set | sample weighting | artifact |
|---|---|---|---|
| policy combined reference | `policy` | `month_label` | `experiments/20260628_101740_policy_combined_side_exit_p1_l1p2/` |
| dedicated side confidence | `side_confidence` | `month_label` | `experiments/20260628_103304_side_confidence_dedicated_p1_l1p2/` |
| target-weighted side confidence | `side_confidence` | `month_target` | `experiments/20260628_103541_side_confidence_month_target_p1_l1p2/` |

## Model Diagnostics

Overall side-confidence report on validation plus 2024-12 test:

| model | accuracy | balanced accuracy | confidence mean | overconfidence | predicted long share | high confidence share |
|---|---:|---:|---:|---:|---:|---:|
| policy combined reference | `0.4750` | `0.4856` | `0.5404` | `0.0654` | `0.4211` | `0.000486` |
| dedicated side confidence, `month_label` | `0.4750` | `0.4856` | `0.5404` | `0.0654` | `0.4211` | `0.000486` |
| dedicated side confidence, `month_target` | `0.4748` | `0.4896` | `0.5353` | `0.0605` | `0.3914` | `0.001597` |

Split metrics for `month_target`:

| split | accuracy | balanced accuracy | macro F1 |
|---|---:|---:|---:|
| valid | `0.4805` | `0.5003` | `0.4804` |
| test 2024-12 | `0.4516` | `0.4454` | `0.4402` |

Interpretation:

- `target-set side_confidence` with `month_label` exactly matches the policy model's `best_side` classifier because models are fit independently per target.
- `month_target` slightly improves balanced accuracy and reduces mean overconfidence, but the absolute signal remains weak.
- The model still predicts too few longs relative to actual best-side long share (`0.3914` predicted vs `0.5690` actual).

## Policy Replacement Test

To isolate side confidence, the policy combined predictions were kept intact and only `pred_best_side_prob_-1`, `pred_best_side_prob_1`, and `pred_best_side` were replaced by the `month_target` side model outputs.

Merged prediction artifacts:

- `data/reports/modeling/20260628_103557_side_confidence_month_target_report/policy_predictions_valid_month_target_side.parquet`
- `data/reports/modeling/20260628_103557_side_confidence_month_target_report/policy_predictions_test_month_target_side.parquet`

Focused validation setting:

- policy: `timed_ev`
- entry threshold: `10`
- short offset: `8`
- side margin: `1`
- `time_exit_penalty=6`
- `loss_first_penalty=6`
- `time_exit_holding_shrink=0`
- max predicted hold: `720`
- `min_entry_rank=0.5`
- extra side margins: `session_regime=asia:5,session_regime=rollover:5`

Validation 4fold:

| side confidence | min side confidence | min pnl | total pnl | min trades | total trades | max drawdown | forced max | actual miss max | direction error max |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| disabled reference | `0.00` | `75.1682` | `531.6246` | `36` | `157` | `85.6920` | `0.000000` | `0.523810` | `0.425000` |
| month-target side | `0.55` | `-15.2120` | `178.8212` | `19` | `95` | `95.9854` | `0.041667` | `0.545455` | `0.451613` |
| prior policy side from report 00057 | `0.55` | `65.0410` | `375.9450` | `22` | n/a | n/a | n/a | `0.516129` | `0.413793` |

2024-12 fixed diagnostic:

| side confidence | min side confidence | adjusted pnl | raw pnl | trades | profit factor | max drawdown | forced exits | actual miss smoothed | direction error |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| prior policy side from report 00057 | `0.55` | `-91.9786` | `-54.0030` | `33` | `0.5963` | `139.2716` | `2` | `0.714286` | `0.484848` |
| month-target side | `0.55` | `-88.1826` | `-53.9040` | `32` | `0.5712` | `151.1466` | `2` | `0.676471` | `0.531250` |

## Decision

- `month_target` sample weighting is useful infrastructure and remains available.
- `target-set side_confidence`専用化だけでは改善しない。現行HGBはtargetごとに独立fitなので、shared representationがない限りmulti-task crowdingは主因ではない。
- `month_target` は2024-12だけ adjusted pnlを小さく改善したが、validation 4foldで `min pnl=-15.2120` まで崩れた。validation優先の原則により採用しない。
- `min_side_confidence` hard gateは引き続き標準採用しない。

## Next Actions

1. side confidenceを直接hard gateにする探索は止め、OOF calibrationやregime別誤差診断に戻す。
2. shared representationを持つ小型MLP/TCNを試す場合は、HGBの「targetごと独立」という制約を解消できるかを主検証点にする。
3. 次はentry/sideそのものより、trade集合に対するdirection error、profit-barrier miss、EV overestimateを同時に下げる候補選定へ戻る。
