# Training Time and Generalization

日付: 2026-06-28 JST

## 目的

汎化性能を高めるため、過学習を避けるパラメータ設定を導入し、学習時間を伸ばすことで改善するかを確認する。

あわせて、データを数倍に増やす準備として 2019-01 から 2022-12 のdatasetを生成した。ただし今回の主比較は、時間的に古いデータの効果ではなく、同じsplitで学習反復数を増やす効果を見る。

## 実装

`src/trade_data/modeling.py`:

- HGBに過学習抑制パラメータを追加。
  - `--max-depth`
  - `--max-features`
  - `--early-stopping`
  - `--validation-fraction`
  - `--n-iter-no-change`
  - `--tol`
- defaultを保守的に変更。
  - `max_iter=200`
  - `learning_rate=0.03`
  - `max_leaf_nodes=15`
  - `max_depth=4`
  - `min_samples_leaf=100`
  - `l2_regularization=0.2`
  - `max_features=0.8`
  - `target_clip_quantile=0.99`
  - `sample_weighting=month_label`
- `--target-set policy` を追加。
  - executable policyに必要なtargetだけを学習し、長時間学習の比較を速くする。
- prediction frameに低次元regime特徴を残す。
- `model_diagnostics` に targetごとの `n_iter`, `hit_max_iter`, final score を保存する。
- `--label` でexperiment directory名を明示できるようにした。

`src/trade_data/meta_model.py`:

- base predictionに残したregime特徴をmeta inputとして利用可能にした。
- `month_side` sample weightingを追加。
- prediction shrinkageを追加。
- defaultをより保守的にした。
  - `max_leaf_nodes=7`
  - `max_depth=3`
  - `min_samples_leaf=300`
  - `l2_regularization=1.0`
  - `target_clip_quantile=0.98`
  - `prediction_shrinkage=0.75`

## Data Scale

追加生成:

- 2019-01 から 2022-12
- artifact summary: `data/processed/datasets/xauusd_m1/build_range_2019-01_2022-12_edge15.summary.json`

利用可能dataset:

- edge15 monthly datasets: 2019-01 から 2025-12
- months: 84
- rows: 2,433,133

68ヶ月trainのfull target学習も試したが、時間がかかりすぎるため中断した。古いデータ追加は比較軸として残すが、今回の本流ではない。

## Training Time Experiment

Split:

- train: 2023-01..2023-12, 2024-01..2024-06, 2024-08, 2024-10
- valid: 2024-07, 2024-09, 2024-11, 2025-01
- test: 2024-12, 2025-02
- train rows: 546,537
- target set: `policy`
- evaluation multipliers: profit 1.0 / loss 1.25

Common params:

- `learning_rate=0.03`
- `max_leaf_nodes=15`
- `max_depth=4`
- `min_samples_leaf=300`
- `l2_regularization=0.5`
- `max_features=0.8`
- `early_stopping=true`
- `validation_fraction=0.15`
- `target_clip_quantile=0.99`
- `sample_weighting=month_label`

Artifacts:

- iter80: `experiments/20260627_201301_policy_iter80_base_train/`
- iter320: `experiments/20260627_201455_policy_iter320_base_train/`

Model diagnostics:

| run | targets | hit max_iter | min iter | max iter |
|---|---:|---:|---:|---:|
| iter80 | 14 | 14 | 80 | 80 |
| iter320 | 14 | 14 | 320 | 320 |

すべてのtargetが `max_iter` に到達した。内部early stoppingは発火していないため、反復数だけを見ると学習時間を伸ばす余地はある。

Selection metric:

| run | valid long r2 | valid short r2 | valid selected pnl | valid side acc | test long r2 | test short r2 | test selected pnl | test side acc |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| iter80 | -0.0196 | 0.0640 | 401,423.6509 | 0.5401 | -0.0072 | -0.0623 | 297,549.3014 | 0.4529 |
| iter320 | 0.0087 | 0.0386 | 787,915.4966 | 0.5157 | -0.0065 | -0.0451 | 517,566.6426 | 0.4515 |

iter320はselection pnlを増やしたが、test side accuracyは改善していない。これは予測EVの強さが増えても、方向汎化が改善していないことを示す。

## Executable Backtest

iter80:

- validation 4fold sweep
- strict 30 trades/fold: eligibleなし
- relaxed 10 trades/fold: eligibleなし

iter320:

- strict 30 trades/fold: eligibleなし
- relaxed 10 trades/fold: eligibleあり

min fold pnl優先の選択候補:

| policy | entry | side margin | risk | max wait regret | min entry rank | barrier | mean pnl | min pnl | min trades | max DD | forced max |
|---|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|
| timed_ev | 15 | 0 | 0 | 4 | 0 | true | 41.8295 | 26.2700 | 15 | 51.2338 | 0.0000 |

Test:

| test month | adjusted pnl | raw pnl | trades | win rate | profit factor | max DD | forced exits |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2024-12 | -99.9843 | -77.1590 | 16 | 0.3125 | 0.1239 | 99.9843 | 0 |
| 2025-02 | -38.9125 | -21.3300 | 12 | 0.5833 | 0.5574 | 40.0975 | 0 |

平均P/L優先候補も確認したが、testはさらに悪かった。

| test month | adjusted pnl | raw pnl | trades | win rate | profit factor | max DD | forced exits |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2024-12 | -125.5185 | -96.7850 | 12 | 0.3333 | 0.1263 | 125.5185 | 1 |
| 2025-02 | -46.2038 | -25.1330 | 12 | 0.4167 | 0.5614 | 71.6038 | 0 |

## 判断

- 学習時間を80から320へ伸ばすと、validationでは候補が出るようになった。
- ただしtestではNoTradeを超えず、2024-12/2025-02ともマイナス。
- すべてのtargetがmax_iterに到達しているため、純粋な収束不足の可能性は残る。
- しかし320でtest side accuracyが改善していないため、単純に長く学習するだけでは汎化性能は改善しにくい。
- 学習時間をさらに伸ばす場合は、validation-internal OOFや追加test月を使い、反復数増加がvalidation過適合になっていないかを必ず確認する。

次の方針:

1. `max_iter` をさらに伸ばす場合は、同時に `learning_rate` を下げ、OOF validationで比較する。
2. 30 trades/foldを満たせない候補は本採用しない。
3. 古いデータ追加は、full targetではなく `target-set policy` から検証する。
4. test side accuracyが上がらない限り、entry/exit policyの閾値調整だけでは解決しない。
