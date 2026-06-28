# Stateful Candidate Examples

日時: 2026-06-29 08:42 JST
更新日時: 2026-06-29 08:42 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻である `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## 目的

`00115` ではcandidate取引が保有中にbase側の取引機会をブロックすることを確認した。

今回はこの診断を、次の学習に渡せる候補例CSVへ変換する。狙いは、pointwiseな実現PnLではなく、一玉制約の機会費用込みのtargetを作ること。

## 実装

`model-trade-delta` に `stateful_candidate_examples.csv` を追加した。

1行はcandidate policyで実際に取った取引。`common` と `only_candidate` の両方を含む。

追加した主な列:

- `target`
- `stateful_entry_value`
- `stateful_positive_cost_value`
- `blocking_cost`
- `positive_blocking_cost`
- `replacement_regret`
- `positive_replacement_regret`
- `candidate_actual_adjusted_pnl`
- `side`
- `candidate_side`
- `decision_timestamp`
- `pred_side_gap`
- `pred_abs_side_gap`
- `decision_hour_sin`
- `decision_hour_cos`

`--stateful-example-target` を追加し、`target` の作り方を選べる。

- `stateful_net`: `candidate_adjusted_pnl - blocked_base_adjusted_pnl`
- `stateful_positive_cost`: `candidate_adjusted_pnl - blocked_base_positive_pnl`
- `candidate_pnl`: 従来のcandidate自身のPnL

defaultは `stateful_net`。

## Smoke Run

```bash
PYTHONPATH=src python3 -m trade_data.backtest model-trade-delta \
  --base-runs data/reports/backtests/side_outcome_stack_trade_delta_raw_2024_12,data/reports/backtests/side_outcome_stack_trade_delta_raw_2025_03 \
  --candidate-runs data/reports/backtests/side_outcome_stack_trade_delta_stack0_2024_12,data/reports/backtests/side_outcome_stack_trade_delta_stack0_2025_03 \
  --output-dir data/reports/backtests \
  --label stateful_candidate_examples_smoke \
  --top-n 5
```

artifact:

- `data/reports/backtests/20260628_234210_stateful_candidate_examples_smoke/`

出力:

- `stateful_candidate_examples.csv`: `220` rows, `110` columns
- `trade_delta_rows.csv`
- `blocking_pairs.csv`
- `group_by_blocking_candidate_*`

## Target Distribution

| month | candidate count | target mean | stateful positive-cost mean | blocking cost sum | positive blocking cost sum |
|---|---:|---:|---:|---:|---:|
| 2024-12 | `83` | `0.5921` | `-0.5883` | `26.0390` | `30.0950` |
| 2025-03 | `137` | `-0.4640` | `-0.7904` | `100.0230` | `102.9960` |

2025-03はcandidate自身の取引だけでなく、機会費用込みでも負。positive-cost targetではさらに悪い。

status / direction別:

| month | status | direction | n | target sum | target mean | candidate pnl | blocking cost | positive blocking cost |
|---|---|---|---:|---:|---:|---:|---:|---:|
| 2024-12 | common | long | `21` | `21.5796` | `1.0276` | `21.5796` | `0.0000` | `0.0000` |
| 2024-12 | common | short | `17` | `24.8906` | `1.4642` | `24.8906` | `0.0000` | `0.0000` |
| 2024-12 | only_candidate | long | `33` | `-5.2276` | `-0.1584` | `-72.3252` | `22.3300` | `22.3300` |
| 2024-12 | only_candidate | short | `12` | `7.9038` | `0.6587` | `7.1248` | `3.7090` | `7.7650` |
| 2025-03 | common | long | `30` | `74.9792` | `2.4993` | `74.9792` | `0.0000` | `0.0000` |
| 2025-03 | common | short | `45` | `-15.4494` | `-0.3433` | `-15.4494` | `0.0000` | `0.0000` |
| 2025-03 | only_candidate | long | `33` | `-69.9094` | `-2.1185` | `-18.8318` | `75.3170` | `78.2900` |
| 2025-03 | only_candidate | short | `29` | `-53.1846` | `-1.8340` | `-45.9878` | `24.7060` | `24.7060` |

2025-03の `only_candidate long` は、candidate自身のPnLよりstateful targetのほうが大きく悪い。ここが一玉制約の機会費用。

## Raw EV Calibration Against Stateful Target

既存の `candidate-quality-report` を、`target=stateful_entry_value`, raw/mean/lower predictionを全て `pred_taken_ev` として実行した。

```bash
PYTHONPATH=src python3 -m trade_data.meta_model candidate-quality-report \
  --examples data/reports/backtests/20260628_234210_stateful_candidate_examples_smoke/stateful_candidate_examples.csv \
  --target-column target \
  --raw-prediction-column pred_taken_ev \
  --mean-prediction-column pred_taken_ev \
  --lower-prediction-column pred_taken_ev \
  --output-dir data/reports/modeling \
  --label stateful_candidate_examples_report \
  --groupings 'month;month,delta_status;month,delta_status,direction;month,delta_status,direction,combined_regime' \
  --bucket-score raw \
  --bucket-count 8 \
  --bucket-group-columns month,delta_status,direction \
  --summary-rows 12
```

artifact:

- `data/reports/modeling/20260628_234302_stateful_candidate_examples_report/`

overall:

| metric | value |
|---|---:|
| support | `220` |
| target mean | `-0.0655` |
| raw predicted mean | `18.4353` |
| raw bias | `18.5008` |
| raw overestimate mean | `18.7974` |
| mean MAE | `19.0939` |
| target rate <= 0 | `0.5227` |
| raw pred rate <= 0 | `0.0000` |

raw EVはstateful targetに対して平均 `18.5008` 過大評価。candidate自身のPnLだけでなく、機会費用込みでもEVの過大評価が中心問題。

## 判断

`stateful_candidate_examples.csv` を次の学習入力として採用する。

ただし、今回のsmokeは2024-12/2025-03の2ヶ月だけで、学習に使うには少ない。次はvalidation OOF側で同じ形式を作る。

次の手順:

1. 代表validation月ごとに raw base と candidate policy の `model-policy` runを保存する。
2. `model-trade-delta` で `stateful_candidate_examples.csv` を作る。
3. 月を抜くOOFで `stateful_entry_value` / `stateful_positive_cost_value` modelを学習する。
4. 予測列は hard gateではなく、candidate ranking / tie-break / EV補正として検証する。

## Verification

- `PYTHONPATH=src python3 -m unittest tests.test_backtest.BacktestTests.test_model_trade_delta_compares_added_and_removed_trades_with_gate_quality`: OK
- `PYTHONPATH=src python3 -m trade_data.backtest model-trade-delta`: OK for 2024-12 / 2025-03 smoke
- `PYTHONPATH=src python3 -m trade_data.meta_model candidate-quality-report`: OK for stateful examples smoke
