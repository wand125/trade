# Side Outcome Stacking Features

日時: 2026-06-29 08:09 JST
更新日時: 2026-06-29 08:09 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻である `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## 目的

`00112` では、side-outcome EV分布校正を単独gateにするとvalidationでは改善するがholdoutで崩れることを確認した。

今回は単一risk列の閾値ではなく、side-outcome列と既存 `component_fixed_weighted` quality列を二段目candidate-quality modelの特徴量に入れる。

狙いは、以下を同時に扱わせること。

- side別のwrong-side確率
- no-edge / large-loss確率
- EV過大評価
- side-outcome target mean/lower
- component quality mean/lower
- taken sideとopposite sideの差

## 実装

`trade_quality_features_from_predictions` に任意のside別補助特徴を追加した。対象列がpredictionに存在する場合だけ値が入り、存在しない場合は `0` になるため既存artifactとは互換。

追加特徴は、各featureについて以下の3種類を作る。

- `pred_taken_<feature>`
- `pred_opposite_<feature>`
- `pred_<feature>_gap`

追加した主なfeature:

- `side_outcome_target_mean`
- `side_outcome_target_lower`
- `side_outcome_conservative_ev_score`
- `side_outcome_no_edge_prob`
- `side_outcome_large_loss_prob`
- `side_outcome_wrong_side_prob`
- `side_outcome_ev_overestimate`
- `side_outcome_wrong_side_gap_mean`
- `component_fixed_weighted_quality`
- `component_fixed_weighted_lower_quality`
- `component_fixed_weighted_overestimate_risk`
- `component_fixed_weighted_lower_overestimate_risk`

## Model

対象prediction:

- validation OOF: `data/reports/modeling/20260629_side_outcome_evdist_oof/predictions_component_fixed_weighted_side_outcome_oof.parquet`
- holdout apply: `data/reports/modeling/20260629_side_outcome_evdist_apply/predictions_component_fixed_weighted_side_outcome_holdouts.parquet`

重要な注意:

`oof-candidate-quality-model` のdefaultは `source_mode=fixed_horizon` なので、今回の固定candidate条件と一致しない。固定候補 `down5,up10` と同じEV列を使うため、`--source-mode columns --long-column pred_long_best_adjusted_pnl --short-column pred_short_best_adjusted_pnl` を明示した。

model設定:

- target mode: `fixed_horizon_component_adjusted_pnl`
- prediction prefix: `side_outcome_stack_fixed`
- validation months: `2024-07`, `2024-09`, `2024-11`, `2025-01`
- apply months: `2024-12`, `2025-02`, `2025-03`
- candidate filter: `entry=12`, `short offset=6`, `side margin=5`, `min rank=0.5`
- HGB: `max_iter=80`, `learning_rate=0.04`, `max_leaf_nodes=15`, `max_depth=3`, `min_samples_leaf=80`
- regularization: `l2=1.0`, `max_features=0.7`, `sample_weighting=month_side`, `prediction_shrinkage=0.5`

OOF candidate metrics:

| metric | value |
|---|---:|
| candidate count | `9091` |
| target mean | `1.2754` |
| raw predicted mean | `22.0055` |
| mean predicted mean | `1.3052` |
| lower predicted mean | `-3.4575` |
| raw bias | `20.7301` |
| mean bias | `0.0298` |
| raw overestimate mean | `20.7301` |
| mean overestimate mean | `3.7140` |
| lower overestimate mean | `2.0451` |
| mean MAE | `7.3982` |
| mean RMSE | `9.0067` |
| mean R2 | `0.0168` |
| lower coverage | `0.6998` |

R2は薄いが正になった。これまでのcandidate quality系に比べると、少なくとも固定component targetでは特徴量追加が前進している。

## Validation

固定売買条件は `00112` と同じ。

- `policy=timed_ev`
- `entry_threshold=12`
- `short_entry_threshold_offset=6`
- `side_margin=5`
- `min_entry_rank=0.5`
- `max_predicted_hold_minutes=480`
- `side_ev_penalty_rules=short:combined_regime=down_low_vol:5,short:combined_regime=up_low_vol:10`
- `pred_mlp_*_exit_event_minutes`
- loss multiplier `1.20`

`pred_candidate_quality_side_outcome_stack_fixed_*_adjusted_pnl` を `min_trade_quality` gateにした。

| mode | min trade quality | validation sum | validation min | trades | min trades | max DD | direction error | EV overestimate |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| stack mean gate | `0` | `673.0854` | `148.8660` | `254` | `59` | `81.8534` | `0.3865` | `13.6846` |
| stack mean gate | `-1` | `678.0540` | `147.2162` | `270` | `64` | `85.0166` | `0.3865` | `13.6806` |
| raw | `-inf` | `622.6486` | `138.0338` | `275` | `65` | `85.0166` | `0.3943` | `13.8658` |
| stack lower gate | `-6` | `540.1712` | `121.0960` | `265` | `59` | `85.0166` | `0.3889` | `14.1486` |

mean gate `>=0` はvalidationでrawを上回り、前回の `wrong_side_risk >= -0.45` のvalidation min `148.1228` もわずかに上回った。

lower gateはvalidation時点でrawを下回ったため、holdoutへ進めない。

## Holdout

validationで事前候補にした mean gate `>=0` と、近傍の `>=-1` をholdoutへ適用した。

| mode | min trade quality | holdout sum | holdout min | trades | min trades | max DD | direction error | EV overestimate |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| stack mean gate | `0` | `155.4990` | `-18.7302` | `374` | `83` | `109.2604` | `0.5352` | `19.0776` |
| raw | `-inf` | `242.5008` | `-20.8252` | `426` | `92` | `122.9852` | `0.5249` | `19.0017` |
| stack mean gate | `-1` | `158.9004` | `-47.5352` | `401` | `87` | `120.5932` | `0.5269` | `19.0905` |
| wrong-side gate | `-0.45` | `145.5712` | `-57.7274` | `361` | `79` | `119.6508` | `0.5075` | `19.3266` |

月別:

| month | raw | stack mean `>=0` | stack mean `>=-1` |
|---|---:|---:|---:|
| 2024-12 | `-20.8252` | `-18.7302` | `-47.5352` |
| 2025-02 | `179.2484` | `179.5190` | `174.4482` |
| 2025-03 | `84.0776` | `-5.2898` | `31.9874` |

`>=0` は2024-12の下振れとmax drawdownを少し改善するが、2025-03を大きく壊し、holdout合計はrawを大きく下回る。

## 判断

side-outcome/component補助特徴をcandidate-quality modelへ入れる実装は採用する。OOF candidate targetのR2が薄く正になり、raw EV過大評価も大きく圧縮できた。

ただし、`side_outcome_stack_fixed` gateは標準policyには採用しない。

- validationでは `mean>=0` がrawより良い。
- holdoutでは最低月とmaxDDは少し改善するが、合計PnLが `242.5008 -> 155.4990` に落ちる。
- 2025-03を `84.0776 -> -5.2898` に壊しており、未知regimeへの外挿として不安定。

次は、単一gateではなくcandidate selectionのranking/tie-breakや、月別・regime別のmodel confidence診断として使う。特に「合計PnLを削ってdrawdownを下げる」挙動は、risk budgetを明示した別評価軸なら意味があるが、現行目的の月次利益最大化では標準候補にしない。

## Artifacts

- model output: `data/reports/modeling/20260628_230654_20260629_side_outcome_stack_fixed_component/`
- validation mean gate: `data/reports/backtests/side_outcome_stack_fixed_mean_gate_validation/`
- validation lower gate: `data/reports/backtests/side_outcome_stack_fixed_lower_gate_validation/`
- validation summary: `data/reports/backtests/20260629_side_outcome_stack_fixed_gate_validation_summary.csv`
- mean gate validation months: `data/reports/backtests/20260629_side_outcome_stack_fixed_mean_gate_validation_months.csv`
- mean gate validation summary: `data/reports/backtests/20260629_side_outcome_stack_fixed_mean_gate_validation_summary.csv`
- holdout mean gate: `data/reports/backtests/side_outcome_stack_fixed_mean_gate_holdout/`
- holdout months: `data/reports/backtests/20260629_side_outcome_stack_fixed_mean_gate_holdout_months.csv`
- holdout summary: `data/reports/backtests/20260629_side_outcome_stack_fixed_mean_gate_holdout_summary.csv`

## Verification

- `PYTHONPATH=src python3 -m unittest tests.test_meta_model`: OK
- `PYTHONPATH=src python3 -m unittest tests.test_docs_reports`: OK
- `python3 -m trade_data.meta_model oof-candidate-quality-model`: OK
- `python3 -m trade_data.backtest model-sweep`: OK for validation and holdout comparisons
