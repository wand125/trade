# Candidate Quality Component Holdout Apply

日時: 2026-06-29 03:24 JST
更新日時: 2026-06-29 03:24 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻である `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## 目的

`00088` では、validation 4fold上で `component_fixed_weighted quality>=0` がbaselineと同じfold最低PnLを保ち、sumとEV過大評価を小さく改善した。

今回は同じcomponent列をprefixed applyへ生成し、2024-12 / 2025-02 fixed holdoutに事前選択済み条件で適用した。

## 条件

- validation fit months: `2024-07,2024-09,2024-11,2025-01`
- apply months: `2024-12`, `2025-02`
- base apply predictions:
  - `data/reports/modeling/20260629_hgb_mlp_exit_hybrid_forced_targets/predictions_hgb_entry_mlp_exit_2024_12_forced.parquet`
  - `data/reports/modeling/20260629_hgb_mlp_exit_hybrid_forced_targets/predictions_hgb_entry_mlp_exit_2025_02_forced.parquet`
- component targets:
  - `timed_barrier_component_adjusted_pnl`
  - `fixed_horizon_component_adjusted_pnl`
  - `clipped_best_adjusted_pnl`
- composite: `component_fixed_weighted = weighted_mean(timed=0.25, fixed=0.5, clipped=0.25)`
- policy: `timed_ev`
- fixed policy key: `entry=12`, `short offset=6`, `side margin=5`, `risk penalty=0`, `min entry rank=0.5`
- holding columns: `pred_mlp_long_exit_event_minutes`, `pred_mlp_short_exit_event_minutes`
- max predicted hold minutes: `480`
- policy evaluation: profit multiplier `1.0`, loss multiplier `1.20`

## Apply列確認

| apply month | rows | long mean | short mean | long risk mean | short risk mean | missing |
|---|---:|---:|---:|---:|---:|---:|
| 2024-12 | `28763` | `4.2406` | `3.9316` | `-9.8191` | `-10.5521` | `0` |
| 2025-02 | `27441` | `4.4250` | `3.8783` | `-9.9960` | `-13.2573` | `0` |

## Validation再確認

同じ固定policy keyで、quality閾値だけを比較した。

| min quality | validation min pnl | validation sum pnl | min trades | forced exit max | EV overestimate mean | direction error mean |
|---:|---:|---:|---:|---:|---:|---:|
| `-inf` | `82.7176` | `406.6546` | `24` | `0.0370` | `15.5226` | `0.3809` |
| `0` | `82.7176` | `410.7146` | `24` | `0.0370` | `15.4567` | `0.3809` |
| `2` | `71.1944` | `363.5200` | `21` | `0.0370` | `15.9182` | `0.3898` |
| `5` | `-20.9426` | `89.0904` | `6` | `0.0000` | `18.5945` | `0.4688` |

## Fixed Holdout

`quality>=0` は両holdoutでbaselineと完全に同じだった。つまり、validation上の小改善はfixed holdoutでは追加filterとして働かなかった。

| month | min quality | adjusted pnl | trades | forced exit rate | profit factor | max drawdown | EV overestimate mean | direction error |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2024-12 | `-inf` | `-31.7576` | `52` | `0.0577` | `0.8560` | `99.1124` | `22.1346` | `0.5962` |
| 2024-12 | `0` | `-31.7576` | `52` | `0.0577` | `0.8560` | `99.1124` | `22.1346` | `0.5962` |
| 2024-12 | `2` | `-16.4354` | `43` | `0.0698` | `0.9202` | `86.9762` | `21.4707` | `0.5581` |
| 2024-12 | `5` | `29.9552` | `14` | `0.0714` | `1.5779` | `28.6002` | `20.0615` | `0.6429` |
| 2025-02 | `-inf` | `47.1824` | `126` | `0.0000` | `1.1661` | `118.9336` | `23.2076` | `0.4127` |
| 2025-02 | `0` | `47.1824` | `126` | `0.0000` | `1.1661` | `118.9336` | `23.2076` | `0.4127` |
| 2025-02 | `2` | `62.7588` | `125` | `0.0000` | `1.2236` | `119.7216` | `23.0908` | `0.4160` |
| 2025-02 | `5` | `-27.1872` | `41` | `0.0000` | `0.8121` | `46.3084` | `25.5667` | `0.4634` |

## 判断

`component_fixed_weighted quality>=0` は標準policyへ昇格しない。holdoutで何も取引を落とさず、baselineと同一になったため、validationのsum改善は実行上の汎化改善として弱い。

`quality>=2` は2024-12を `-31.7576 -> -16.4354`、2025-02を `47.1824 -> 62.7588` に改善した。しかしvalidationではfold最低PnLを `82.7176 -> 71.1944`、sumを `410.7146 -> 363.5200` に落としている。これは採用ではなく、次のblind holdoutで事前登録して確認する候補に留める。

`quality>=5` は2024-12だけ良く、2025-02とvalidationを壊す。post-hoc overfitの形なので採用しない。

追加holdoutとして2025-03を使うには、今回と同じ HGB entry + MLP exit hybrid prediction frameが必要だが、現時点で同一形式の2025-03 parquetは存在しない。別モデルの2025-03 predictionを流用すると比較条件が変わるため、このレポートでは使わない。

次は、`xauusd_m1_p1_l1p2_policy_combined` に2025-03以降を生成し、同一HGB+MLP+forced target形式のpredictionを作った上で、`quality>=2` を事前登録候補として確認する。

## Artifacts

- 2024-12 prefixed apply final: `data/reports/modeling/20260628_181856_candidate_quality_apply_2024_12_clipped_best/`
- 2025-02 prefixed apply final: `data/reports/modeling/20260628_182030_candidate_quality_apply_2025_02_clipped_best/`
- composite apply predictions: `data/reports/modeling/20260629_candidate_quality_component_fixed_weighted_apply/`
- no-gate fixed backtests: `data/reports/backtests/candidate_quality_component_fixed_weighted_apply_baseline/`
- quality `0` fixed backtests: `data/reports/backtests/candidate_quality_component_fixed_weighted_apply_quality0/`
- quality threshold diagnostic sweeps: `data/reports/backtests/candidate_quality_component_fixed_weighted_apply_quality_sweep/`

## Verification

- `PYTHONPATH=src python3 -m trade_data.meta_model combine-candidate-quality-components`: OK for 2024-12 / 2025-02, missing output columns `0`
- `PYTHONPATH=src python3 -m trade_data.backtest model-policy`: OK for baseline and quality `0`, 2024-12 / 2025-02
- `PYTHONPATH=src python3 -m trade_data.backtest model-sweep`: OK for quality threshold diagnostics, 2024-12 / 2025-02
- `PYTHONPATH=src python3 -m unittest tests.test_docs_reports`: OK, 1 test
- `git diff --check`: OK
