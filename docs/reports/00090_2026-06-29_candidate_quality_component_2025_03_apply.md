# Candidate Quality Component 2025-03 Apply

日時: 2026-06-29 03:38 JST
更新日時: 2026-06-29 03:38 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻である `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## 目的

`00089` で、`component_fixed_weighted quality>=2` は2024-12 / 2025-02 fixed holdoutを改善したが、validation 4foldでは悪化した。

今回は同一 HGB entry + MLP exit + forced target frameを2025-03へ生成し、`quality>=2` を事前登録候補として追加holdout確認した。

## 条件

- dataset: `xauusd_m1_p1_l1p2_policy_combined`
- generated month: `2025-03`
- dataset rows: `28972`
- dataset label counts: `long=16517`, `flat=4792`, `short=7663`
- policy evaluation: profit multiplier `1.0`, loss multiplier `1.20`
- HGB train months: `2023-01..2024-06,2024-08,2024-10`
- validation months: `2024-07,2024-09,2024-11,2025-01`
- test/apply month: `2025-03`
- purge/embargo: label overlap purge enabled, embargo `24h`
- HGB config: `max_iter=80`, `learning_rate=0.05`, `max_leaf_nodes=15`, `max_depth=4`, `min_samples_leaf=100`, `l2=0.2`, `max_features=0.8`
- MLP config: hidden layers `32,16`, `alpha=0.01`, `max_iter=40`, `sample_frac=0.15`
- fixed policy key: `timed_ev`, `entry=12`, `short offset=6`, `side margin=5`, `risk penalty=0`, `min entry rank=0.5`
- holding columns: `pred_mlp_long_exit_event_minutes`, `pred_mlp_short_exit_event_minutes`
- max predicted hold minutes: `480`
- quality column: `component_fixed_weighted = weighted_mean(timed=0.25, fixed=0.5, clipped=0.25)`

## 2025-03 Prediction診断

HGB側は2025-03でside/EVが崩れており、backtestはentry方向のregime stressとして読む。

| model | split | long exit R2 | short exit R2 | side score R2 | best side balanced accuracy | label balanced accuracy |
|---|---|---:|---:|---:|---:|---:|
| HGB | validation | `0.3882` | `0.4020` | `-0.0076` | `0.4926` | `0.4670` |
| HGB | 2025-03 | `0.2932` | `0.3941` | `-0.3231` | `0.4633` | `0.3706` |
| MLP | validation | `0.3619` | `0.3629` | `-0.0781` | - | - |
| MLP | 2025-03 | `0.3005` | `0.3572` | `-0.8747` | - | - |

MLP exit timingは2025-03でもR2が残る。一方、entry方向とEV水準はかなり弱い。

## Apply列確認

`component_fixed_weighted` の2025-03 apply列は欠損0で生成できた。

| month | rows | long mean | short mean | long risk mean | short risk mean | missing |
|---|---:|---:|---:|---:|---:|---:|
| 2025-03 | `28972` | `4.4615` | `4.0020` | `-9.9267` | `-12.1513` | `0` |

## 2025-03 Fixed Holdout

事前登録候補 `quality>=2` はbaselineより悪化した。

| min quality | adjusted pnl | trades | forced exit rate | profit factor | max drawdown | EV overestimate mean | direction error | worst direction/session |
|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `-inf` | `-48.6826` | `112` | `0.0089` | `0.8285` | `97.4994` | `22.1394` | `0.7679` | `short:asia -67.7956` |
| `0` | `-48.6826` | `112` | `0.0089` | `0.8285` | `97.4994` | `22.1394` | `0.7679` | `short:asia -67.7956` |
| `2` | `-55.7516` | `104` | `0.0096` | `0.8107` | `105.6714` | `22.2468` | `0.7788` | `short:asia -98.6044` |
| `5` | `-45.2572` | `42` | `0.0238` | `0.6815` | `59.0798` | `24.3928` | `0.6667` | `short:london -58.0218` |
| `8` | `0.0000` | `0` | `0.0000` | - | `0.0000` | `0.0000` | `0.0000` | - |
| `10` | `0.0000` | `0` | `0.0000` | - | `0.0000` | `0.0000` | `0.0000` | - |
| `12` | `0.0000` | `0` | `0.0000` | - | `0.0000` | `0.0000` | `0.0000` | - |

`quality>=5` は2025-03単月では少し損失を縮めるが、validationと2025-02を壊しており、trade countも42まで落ちる。post-hoc採用しない。

`quality>=8` 以上はNoTrade化であり、月10trades条件を満たさない。これはリスク制御ではなく取引機会を消しているだけなので採用しない。

## 複数期間まとめ

| scope | min quality | adjusted/min pnl | trades/min trades | note |
|---|---:|---:|---:|---|
| validation | `-inf` | `82.7176` | `24` | baseline |
| validation | `0` | `82.7176` | `24` | sumだけ小改善 |
| validation | `2` | `71.1944` | `21` | validationを悪化 |
| 2024-12 | `-inf` | `-31.7576` | `52` | baseline |
| 2024-12 | `2` | `-16.4354` | `43` | 改善 |
| 2025-02 | `-inf` | `47.1824` | `126` | baseline |
| 2025-02 | `2` | `62.7588` | `125` | 改善 |
| 2025-03 | `-inf` | `-48.6826` | `112` | baseline |
| 2025-03 | `2` | `-55.7516` | `104` | 悪化 |

## 判断

`component_fixed_weighted quality>=2` は標準採用しない。2024-12 / 2025-02での改善は、2025-03追加holdoutで再現しなかった。

今回の失敗はquality gate単体よりも、2025-03でHGB entry/sideの汎化が崩れたことが大きい。short偏重、direction error `0.7679`、`short:asia` 損失集中が同時に出ており、entry方向の過大確信を別途抑える必要がある。

次は `component_fixed_weighted` をhard gateとして採用するのではなく、候補診断特徴として残す。優先すべき方向は、side/entry calibration、short exposure concentration、direction/session別の事前risk検知、または候補quality componentをmulti-feature stackingで扱うこと。

## Artifacts

- 2025-03 dataset: `data/processed/datasets/xauusd_m1_p1_l1p2_policy_combined/xauusd_m1_2025-03_h24_edge15.parquet`
- HGB 2025-03: `experiments/20260628_183132_policy_combined_side_exit_test_2025_03/`
- MLP 2025-03: `experiments/20260628_182929_shared_mlp_hgb_split_test_2025_03/`
- hybrid predictions: `data/reports/modeling/20260629_hgb_mlp_exit_hybrid_2025_03/`
- forced predictions: `data/reports/modeling/20260629_hgb_mlp_exit_hybrid_forced_targets/predictions_hgb_entry_mlp_exit_2025_03_forced.parquet`
- component apply predictions: `data/reports/modeling/20260629_candidate_quality_component_fixed_weighted_apply/predictions_component_fixed_weighted_2025_03.parquet`
- fixed holdout sweep: `data/reports/backtests/candidate_quality_component_fixed_weighted_apply_quality_sweep/20260628_183650_model_sweep_2025-03/`

## Verification

- `PYTHONPATH=src python3 -m trade_data.dataset build-range`: OK for `2025-03`
- `PYTHONPATH=src python3 -m trade_data.modeling train`: OK for HGB 2025-03
- `PYTHONPATH=src python3 -m trade_data.modeling train-shared-mlp`: OK for MLP 2025-03
- `PYTHONPATH=src python3 -m trade_data.modeling enrich-predictions`: OK, missing matches `0`
- `PYTHONPATH=src python3 -m trade_data.meta_model combine-candidate-quality-components`: OK, missing output columns `0`
- `PYTHONPATH=src python3 -m trade_data.backtest model-sweep`: OK for `2025-03`
