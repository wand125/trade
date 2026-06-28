# Selected Trade Quality Model

日時: 2026-06-28 15:11 JST
更新日時: 2026-06-28 15:11 JST

## Summary

- Experiment ID: `selected_trade_quality_model`
- Status: implemented and validation-tested
- Main result: selected tradesの実現PnLをgroup平均ではなく小型HGBで学習するOOF基盤を追加した。個別tradeのMAEはgroup補正よりわずかに改善したが、`min_trade_quality` gateとしてはtop候補を改善せず、標準設定は引き続き `min_trade_quality=-inf`。
- Report numbering note: this file is numbered by the internal `日時`, not by file update time or `更新日時`.

## Motivation

前回のside/regime group平均補正はraw biasを大きく下げたが、個別tradeを見分ける力が弱く、`min_trade_quality` gateとしては悪化した。

今回は、policyが実際に選んだtradeだけを使い、以下の情報から実現adjusted PnLを直接推定する小型モデルを試す。

- 予測EVと反対side EV
- side gap
- fixed horizon由来の保有時間、max adverse、wait regret、entry rank
- profit barrier hit probability
- trend/volatility score
- trend/volatility/session/gap/combined regime
- decision hour

validation月はleave-one-month-outにし、holdout月のtrade quality列はその月をfitに使わず生成した。

## Implementation

追加:

- `TradeQualityModelConfig`
- `TradeQualityModelBundle`
- `trade_data.meta_model oof-trade-quality-model`
- `pred_trade_quality_long_adjusted_pnl`
- `pred_trade_quality_short_adjusted_pnl`
- `pred_trade_quality_taken_adjusted_pnl`

モデル:

- `HistGradientBoostingRegressor`
- `max_iter=80`
- `learning_rate=0.03`
- `max_leaf_nodes=5`
- `max_depth=2`
- `min_samples_leaf=20`
- `l2_regularization=1.0`
- `max_features=0.8`
- `early_stopping=true`
- `target_clip_quantile=0.98`
- `sample_weighting=month_side`
- `prediction_shrinkage=0.7`

categoryは現時点では小型診断モデルとしてordinal code化している。深層学習の本流モデルへ入れる場合はembeddingまたはone-hotを再検討する。

## Setup

Validation months:

- `2024-07`
- `2024-09`
- `2024-11`
- `2025-01`

Base selected-trade fit policy:

- policy: `fixed_horizon_ev`
- score mode: `max`
- entry threshold: `0`
- short offset: `8`
- side margin: `1`
- max wait regret: `4`
- min entry rank: `0.5`
- profit barrier threshold: `0.2`
- extra margin: `session_regime=asia:5`, `session_regime=rollover:5`
- cost case: spread `0.1`, slippage `0.05`, delay `0`

Sweep grid:

- min trade quality: `-inf`, `-1`, `0`, `0.5`, `1`, `1.5`, `2`
- short offsets: `4`, `8`
- min entry rank: `0`, `0.5`
- profit barrier thresholds: `0.0`, `0.2`
- strict candidate gates are the same as report `00037`.

## Model Diagnostics

OOF selected-trade model on 246 selected trades:

| metric | value |
|---|---:|
| raw bias | `0.628560` |
| model bias | `0.230816` |
| bias reduction | `0.397744` |
| raw overestimate mean | `2.182599` |
| model overestimate mean | `1.948136` |
| model MAE | `3.665455` |
| model RMSE | `6.762978` |
| model R2 | `-0.023487` |

group平均補正のMAE `3.688478` よりは小さいが、biasとR2はgroup補正より悪い。つまり、小型HGBは局所的な誤差を少し拾うが、まだ安定した個別trade識別器にはなっていない。

Prediction distribution:

| column | mean | p10 | p50 | p90 |
|---|---:|---:|---:|---:|
| long quality | `0.857503` | `-0.064574` | `0.703182` | `2.010290` |
| short quality | `0.815953` | `-0.136643` | `0.721066` | `1.877920` |

## Candidate Selection Results

Strict candidate selection:

| min trade quality | eligible | best cost min pnl | best base min pnl | min trades | best smoothed miss | best EV overestimate | best exit regret |
|---:|---:|---:|---:|---:|---:|---:|---:|
| `-inf` | 7 | `27.2158` | `39.7538` | 47 | `0.454545` | `14.377795` | `20.940811` |
| `-1.0` | 7 | `27.2158` | `39.7538` | 47 | `0.454545` | `14.377795` | `20.940811` |
| `0.0` | 7 | `27.2158` | `39.7538` | 47 | `0.459016` | `14.411078` | `20.939889` |
| `0.5` | 0 | `-15.5310` | `-10.3410` | 23 | `0.450000` | `17.109478` | `23.323417` |
| `1.0` | 4 | `1.7620` | `4.1220` | 10 | `0.477612` | `18.353985` | `19.413000` |
| `1.5` | 0 | `0.0000` | `0.0000` | 0 | `0.444444` | `14.540704` | `19.213560` |
| `2.0` | 0 | `-1.9902` | `0.0000` | 0 | `0.440000` | `15.456543` | `25.861382` |

Top eligible remains:

- `min_trade_quality=-inf`
- `short offset=8`
- `min_entry_rank=0.5`
- `profit_barrier_threshold=0.2`
- cost min pnl `27.2158`

`min_trade_quality=0.0` はtop候補を壊さないが、改善もしない。`1.0` 以上はtrade数を大きく削り、fold最低PnLが `1.7620` まで落ちる。

## Interpretation

今回のHGB selected-trade modelは、group平均より少し細かく誤差を拾ったが、validation選定で使うほどのedgeは出なかった。

- `min_trade_quality=0.0` は標準候補と同じtopを残すだけ。
- `min_trade_quality=0.5` はstrict eligibleが消える。
- `min_trade_quality=1.0` はeligibleが4件残るが、best cost min pnlが薄すぎる。
- actual profit-barrier miss、EV overestimate、exit regretを同時に改善する閾値台地がない。

この結果はselected-trade targetの否定ではない。むしろ、246 tradesだけで小型HGBを直接fitしても、将来月で安定するquality scoreにはまだならない、という反証として扱う。

## Decision

- `oof-trade-quality-model` は診断・探索基盤として残す。
- 現時点ではHGB版 `min_trade_quality` gateも標準候補へ採用しない。
- 標準候補は raw fixed horizon + `score_mode=max` + `profit_barrier_miss_penalty=0.0` + `min_trade_quality=-inf` を維持する。
- 次は、trade後品質を単発回帰でgateするより、exit timing targetを直接増やす。特に「利確/損切り/時間切れのどれがいつ起きるか」をhazard/survival型またはtime-bucket classificationで扱う。

## Artifacts

- HGB OOF trade quality model: `experiments/20260628_060718_trade_quality_model_oof_fixed_horizon/`
- no-cost sweeps:
  - `data/reports/backtests/20260628_060955_model_sweep_2024-07/`
  - `data/reports/backtests/20260628_060955_model_sweep_2024-09/`
  - `data/reports/backtests/20260628_060955_model_sweep_2024-11/`
  - `data/reports/backtests/20260628_060955_model_sweep_2025-01/`
- cost sweeps:
  - `data/reports/backtests/20260628_061047_model_sweep_2024-07/`
  - `data/reports/backtests/20260628_061047_model_sweep_2024-09/`
  - `data/reports/backtests/20260628_061047_model_sweep_2024-11/`
  - `data/reports/backtests/20260628_061047_model_sweep_2025-01/`
- candidate selection: `data/reports/backtests/20260628_061118_model_candidate_selection/`

## Verification

- `python3 -m unittest tests.test_meta_model tests.test_backtest`: OK
