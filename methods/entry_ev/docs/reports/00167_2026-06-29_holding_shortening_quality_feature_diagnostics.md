# Holding Shortening Quality Feature Diagnostics

日時: 2026-06-29 20:28 JST
更新日時: 2026-06-29 20:28 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

`00166` で holding-shortening probability / quantile を trade quality / trade overestimate model の optional feature へ接続した。今回は、その特徴を実際の highcost risk5 selected trades で評価した。

対象は holding-shortening OOF predictionが揃っている `2025-02..2025-04`。apply診断は `2025-05` の highcost risk5 selected trades。

結論:

- quality modelでは、validation OOFのbias/RMSE/R2は微改善したが、MAEと過大評価平均はわずかに悪化した。
- 2025-05 apply selected tradesでは、quality modelもholding-feature入りの方が全指標でわずかに悪い。
- overestimate amount modelでは、validation OOFでも2025-05 applyでもholding-feature入りが R2 / AUC / MAE / RMSE を悪化させた。
- selected trade上のholding probability / quantile と実現PnLの相関はほぼ0。overestimate targetとの相関もvalidationでは薄く、2025-05では逆方向に反転した。

したがって、holding-shortening featureは配線として残すが、現時点では quality / overestimate の本流特徴として採用しない。次は直接特徴投入ではなく、context-aware holding-cap target や exit-regret/holding-error系の教師に回す。

## Data

Validation months:

- `2025-02`
- `2025-03`
- `2025-04`

Apply month:

- `2025-05`

Selected trades:

- `data/reports/backtests/20260629_selected_trade_context_wf/fixed_highcost_risk5/20260629_040921_model_timed_ev_2025-02/trades.csv`
- `data/reports/backtests/20260629_selected_trade_context_wf/fixed_highcost_risk5/20260629_040923_model_timed_ev_2025-03/trades.csv`
- `data/reports/backtests/20260629_selected_trade_context_wf/fixed_highcost_risk5/20260629_040925_model_timed_ev_2025-04/trades.csv`
- `data/reports/backtests/20260629_selected_trade_context_wf/fixed_highcost_risk5/20260629_040926_model_timed_ev_2025-05/trades.csv`

Merged prediction outputs:

- `data/reports/modeling/20260629_holding_shortening_quality_feature_merge/predictions_validation_trade_failure_holding_features.parquet`
- `data/reports/modeling/20260629_holding_shortening_quality_feature_merge/predictions_apply_trade_failure_holding_features_2025_05.parquet`
- `data/reports/modeling/20260629_holding_shortening_quality_feature_merge/predictions_validation_full_holding_features.parquet`
- `data/reports/modeling/20260629_holding_shortening_quality_feature_merge/predictions_apply_full_holding_features_2025_05.parquet`

## Implementation

`scripts/experiments/merge_prediction_columns.py` を追加した。

用途:

- base prediction parquetへ、別prediction parquetの指定列を `dataset_month, decision_timestamp` で結合する。
- source側の重複keyを検出する。
- 追加列、既存skip列、missing source列、match数をJSON summaryへ残す。

今回追加した列:

- `pred_long_fixed_60m_beats_exit_event_prob_1`
- `pred_short_fixed_60m_beats_exit_event_prob_1`
- `pred_long_fixed_60m_beats_exit_event_multimonth_quantile`
- `pred_short_fixed_60m_beats_exit_event_multimonth_quantile`

## OOF Metrics

Quality model:

| run | bias | overestimate mean | MAE | RMSE | R2 |
|---|---:|---:|---:|---:|---:|
| baseline | `-0.2321` | `4.2721` | `8.7763` | `12.8536` | `-0.0199` |
| holding features | `-0.1415` | `4.3196` | `8.7806` | `12.8331` | `-0.0166` |

Overestimate amount model:

| run | predicted mean | bias | MAE | RMSE | R2 | high-overestimate AUC |
|---|---:|---:|---:|---:|---:|---:|
| baseline | `20.0093` | `0.2775` | `8.9035` | `12.5405` | `0.0979` | `0.6991` |
| holding features | `20.1041` | `0.3722` | `8.9896` | `12.6334` | `0.0845` | `0.6901` |

## Apply 2025-05 Selected-Trade Diagnostics

Quality model:

| run | bias | overestimate mean | MAE | RMSE | R2 |
|---|---:|---:|---:|---:|---:|
| baseline | `1.0544` | `5.3685` | `9.6827` | `14.3178` | `0.0123` |
| holding features | `1.1311` | `5.4123` | `9.6935` | `14.3387` | `0.0095` |

Overestimate amount model:

| run | predicted mean | bias | MAE | RMSE | R2 | high-overestimate AUC |
|---|---:|---:|---:|---:|---:|---:|
| baseline | `21.1258` | `-2.6196` | `9.7150` | `13.8739` | `0.1560` | `0.7635` |
| holding features | `21.1089` | `-2.6366` | `9.7358` | `13.8862` | `0.1545` | `0.7609` |

## Feature Correlation

Selected trades上の単純相関。

| phase | feature | corr adjusted PnL | corr overestimate target |
|---|---|---:|---:|
| validation 2025-02..04 | holding prob | `0.0070` | `0.0814` |
| validation 2025-02..04 | holding quantile | `0.0042` | `0.0134` |
| apply 2025-05 | holding prob | `-0.0319` | `-0.0296` |
| apply 2025-05 | holding quantile | `-0.0396` | `-0.1426` |

validation側の薄い正方向がapplyで反転しており、少なくともこのまま連続回帰featureに入れると安定しない。

## Artifacts

- quality baseline: `experiments/20260629_112337_trade_quality_baseline_no_holding_2025_02_04_apply_2025_05/`
- quality holding features: `experiments/20260629_112353_trade_quality_holding_features_2025_02_04_apply_2025_05/`
- overestimate baseline: `experiments/20260629_112412_trade_overestimate_baseline_no_holding_2025_02_04_apply_2025_05/`
- overestimate holding features: `experiments/20260629_112431_trade_overestimate_holding_features_2025_02_04_apply_2025_05/`
- metric comparison: `data/reports/modeling/20260629_holding_shortening_quality_feature_merge/quality_overestimate_metric_comparison.csv`
- feature correlation: `data/reports/modeling/20260629_holding_shortening_quality_feature_merge/holding_feature_selected_trade_correlation.csv`

## Verification

- `python3 -m py_compile scripts/experiments/merge_prediction_columns.py`: OK
- `python3 -m unittest tests.test_merge_prediction_columns`: OK, 2 tests
- `python3 -m unittest tests.test_docs_reports`: OK, 3 tests
- `python3 -m unittest tests.test_meta_model`: OK, 48 tests
- `python3 -m unittest tests.test_backtest`: OK, 82 tests
- `git diff --check`: OK

## Decision

holding-shortening featureはfeature plumbingとして残すが、今回の quality / overestimate model には採用しない。特にoverestimate residualの本流は、現行の q90 excess risk / exit-regret / holding-error の方を優先する。
