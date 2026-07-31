# Dense Entry Quality Targets

日時: 2026-06-28 04:49 JST
更新日時: 2026-06-28 08:02 JST

## 目的

`long / short / stay_flat` だけでは entry timing の情報を落としすぎるため、entry quality を密なtargetとして追加する。

狙い:

- entry正例の少なさを補う。
- 1つのdecision rowを多方面の教師信号として使う。
- EV予測の過大評価とentry timingの失敗を分離して観察する。
- 新targetをpolicy側でも使い、悪いentryを抑制できるか確認する。

## 実装

Dataset target:

- `long_profit_barrier_hit`, `short_profit_barrier_hit`
- `long_wait_regret`, `short_wait_regret`
- `long_entry_local_rank`, `short_entry_local_rank`
- `long_entry_urgency`, `short_entry_urgency`
- wait regret quantile
- entry local rank bin

Policy filter:

- `--max-wait-regret`
- `--min-entry-rank`
- `--require-profit-barrier`

デフォルトでは既存policyと同じ挙動にし、指定時だけentry条件に追加する。

## Dataset

旧倍率 0.9 / 1.3 のまま、2023-01 から 2025-12 までの主datasetを新schemaで再生成した。

Command:

```bash
python3 -m trade_data.dataset build-range \
  --start-month 2023-01 \
  --end-month 2025-12 \
  --min-adjusted-edge 15 \
  --entry-timing-lookahead-minutes 60
```

## Model

Artifact:

- `experiments/20260627_192112_hgb_multitask_edge15/`

Split:

- train: 2023-01..2023-12, 2024-01..2024-06, 2024-08, 2024-10
- valid: 2024-07, 2024-09, 2024-11, 2025-01
- test: 2024-12, 2025-02

Settings:

- model: HistGradientBoosting
- sample weighting: `month_label`
- target clip quantile: 0.99
- max leaf nodes: 15
- min samples leaf: 100
- l2 regularization: 0.2
- train target multipliers: 0.9 / 1.3
- validation/test backtest multipliers: 1.0 / 1.25

重要な注意:

現在のHGB実装はtargetごとの独立モデルであり、shared representationのmulti-task学習ではない。そのため、追加targetはEVモデル自体を改善しない。追加targetを性能に効かせるには、policy filterや二段階meta modelで予測値を使う必要がある。

## Validation

通常のEV sweepでは strict 条件を満たす候補なし。

Quality filter sweep:

- sweeps:
  - `data/reports/backtests/20260627_192749_model_sweep_2024-07/`
  - `data/reports/backtests/20260627_192749_model_sweep_2024-09/`
  - `data/reports/backtests/20260627_192749_model_sweep_2024-11/`
  - `data/reports/backtests/20260627_192749_model_sweep_2025-01/`
- summary: `data/reports/backtests/20260627_192904_model_sweep_summary/`
- constraints: min folds 4, min trades per fold 10, max forced exit rate 0.1, max drawdown 100, min pnl per fold 0

Selected validation candidate:

| policy | entry | exit | side margin | risk | max wait regret | min entry rank | barrier | mean pnl | min pnl | min trades | max DD | forced max |
|---|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|
| timed_ev | 5 | 0 | 5 | 0.1 | inf | 0.5 | false | 38.6307 | 2.3763 | 17 | 85.5988 | 0.0476 |

## Test

Validationで選んだ候補を固定して test に適用した。

Artifacts:

- `data/reports/backtests/20260627_192921_model_timed_ev_2024-12/`
- `data/reports/backtests/20260627_192921_model_timed_ev_2025-02/`

| test month | adjusted pnl | raw pnl | trades | win rate | profit factor | max DD | forced exits |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2024-12 | -135.9573 | -85.3350 | 22 | 0.4545 | 0.4629 | 155.0055 | 0 |
| 2025-02 | -101.0583 | -42.7980 | 32 | 0.4688 | 0.6531 | 116.0663 | 1 |

より強く絞る低頻度候補:

- policy: `timed_ev`
- entry threshold: 20
- side margin: 0
- risk penalty: 0.2
- max wait regret: 4
- min entry rank: 0.5

Artifacts:

- `data/reports/backtests/20260627_192937_model_timed_ev_2024-12/`
- `data/reports/backtests/20260627_192937_model_timed_ev_2025-02/`

| test month | adjusted pnl | raw pnl | trades | win rate | profit factor | max DD | forced exits |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2024-12 | -9.5233 | -1.7540 | 5 | 0.6000 | 0.7548 | 30.9213 | 0 |
| 2025-02 | -43.2768 | -19.1100 | 11 | 0.4545 | 0.6418 | 63.8468 | 0 |

## 判断

Dense entry quality target と policy filter は、露出と損失を抑える方向には効いた。しかし no_trade はまだ超えていない。

主な反省:

- 独立HGBでは追加targetがEV予測を直接改善しない。
- `min_entry_rank` はvalidationでは効いたが、testでは十分ではなかった。
- 強く絞ると2024-12の大損は抑えられるが、取引数が少なく、2025-02もプラスにできない。
- `require_profit_barrier` は今回の上位候補には出てこなかった。

次にやるべきこと:

1. 予測済みtargetを入力にした二段階meta modelを作る。
2. meta model は validation月だけで calibrate し、testには固定適用する。
3. targetごとの独立HGBではなく、shared representationを持つ小型MLP/TCNでmulti-task学習を試す。
4. entryだけでなく、保有中のexit判定に `wait_regret`, `entry_rank`, `barrier_hit` を使えるか検討する。

## Meta Model 追試

上記の反省を受けて、予測済みtargetを入力にした二段階meta EV modelを追加した。

Implementation:

- `src/trade_data/meta_model.py`
- `trade-meta`

方法:

- validation predictions を long/short の side-aware examples に展開する。
- 入力は base model の予測済みEV、risk、holding、wait regret、entry rank、urgency、barrier、量子化target。
- target は side別の実際の adjusted pnl。
- fit は validation predictions のみ。
- test predictions に `pred_meta_long_adjusted_pnl`, `pred_meta_short_adjusted_pnl` を付与する。

Artifact:

- `experiments/20260627_193559_meta_ev_dense_entry_quality/`

Meta regression:

| split | long r2 | short r2 | selected side acc |
|---|---:|---:|---:|
| validation-fit | 0.1837 | 0.1980 | 0.6967 |
| test-apply | -0.0652 | -0.1921 | 0.4288 |

Test with meta EV, candidate `timed_ev entry=15 side_margin=5 risk=0.1 min_entry_rank=0.5`:

| test month | adjusted pnl | raw pnl | trades | win rate | profit factor | max DD | forced exits |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2024-12 | -240.5445 | -160.0240 | 48 | 0.4167 | 0.4025 | 292.4770 | 2 |
| 2025-02 | 23.7068 | 82.9970 | 54 | 0.5741 | 1.0800 | 130.4910 | 0 |

Test with stronger filter `entry=20 risk=0.2 max_wait_regret=4 min_entry_rank=0.5`:

| test month | adjusted pnl | raw pnl | trades | win rate | profit factor | max DD | forced exits |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2024-12 | -114.5178 | -88.3520 | 9 | 0.3333 | 0.1247 | 122.5578 | 1 |
| 2025-02 | -71.8913 | -46.2570 | 12 | 0.4167 | 0.4391 | 92.7683 | 0 |

判断:

- meta model は validation-fit では改善するが、test-apply ではR2がマイナスになり、再過学習が強い。
- 2025-02 は一部プラスへ戻るが、2024-12で大きく崩れる。
- 予測済みtargetだけを使う二段階HGBでは、regime shiftをまだ処理できていない。

次の修正:

- meta model のfit月とpolicy選択月を分ける。
- validation内でも walk-forward meta validation を行い、同じ月でfitとpolicy選択をしない。
- regime featureをmeta model入力へ追加する。
- shared representationの深層学習へ進む前に、meta modelの過学習を月別に可視化する。

## Validation-internal OOF Meta

同じvalidation月でmeta modelのfitとpolicy選択を行うと過学習するため、validation 4ヶ月の中で leave-one-month-out を実施した。

方法:

- holdout月以外の3ヶ月でmeta modelをfitする。
- holdout月へmeta予測を付与する。
- holdout月だけでpolicy sweepする。
- 4つのholdout sweepを横断集計し、全foldで損益プラスになるpolicyだけを候補にする。

OOF meta artifacts:

- `experiments/20260627_194501_meta_oof_2024-07/`
- `experiments/20260627_194501_meta_oof_2024-09/`
- `experiments/20260627_194501_meta_oof_2024-11/`
- `experiments/20260627_194501_meta_oof_2025-01/`

OOF regression:

| holdout | long r2 | short r2 | selected side acc |
|---|---:|---:|---:|
| 2024-07 | 0.0286 | 0.0066 | 0.6395 |
| 2024-09 | 0.1403 | -0.1304 | 0.6231 |
| 2024-11 | 0.0615 | -0.0734 | 0.5462 |
| 2025-01 | 0.1715 | -0.5451 | 0.7515 |

Summary:

- strict summary: `data/reports/backtests/20260627_194724_model_sweep_summary_1/`
- constraints: min folds 4, min trades per fold 10, max forced exit rate 0.1, max drawdown 100, min pnl per fold 0
- min trades per fold 30 では eligible candidate なし。

Selected OOF candidate:

| policy | entry | exit | side margin | risk | max wait regret | min entry rank | barrier | mean pnl | min pnl | min trades | max DD | forced max |
|---|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|
| timed_ev | 10 | 0 | 5 | 0.2 | 2 | 0.5 | false | 72.4758 | 3.0118 | 28 | 83.2353 | 0.0000 |

この候補を固定し、全validation月でfitしたmeta modelをtestへ適用した。

Final meta artifact:

- `experiments/20260627_194740_meta_all_valid_to_test_oof_selected/`

Final meta regression:

| split | long r2 | short r2 | selected side acc |
|---|---:|---:|---:|
| validation-fit | 0.1837 | 0.1980 | 0.6967 |
| test-apply | -0.0652 | -0.1921 | 0.4288 |

Test with OOF-selected meta policy:

| test month | adjusted pnl | raw pnl | trades | win rate | profit factor | max DD | forced exits |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2024-12 | -97.3488 | -54.9980 | 31 | 0.5161 | 0.5403 | 143.0608 | 2 |
| 2025-02 | -0.4358 | 29.5100 | 21 | 0.5714 | 0.9971 | 72.8378 | 0 |

同じpolicyをmetaなしのbase predictionsへ適用した比較:

| test month | adjusted pnl | raw pnl | trades | win rate | profit factor | max DD | forced exits |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2024-12 | -130.3193 | -91.0640 | 14 | 0.5000 | 0.3360 | 130.3193 | 0 |
| 2025-02 | -47.2025 | -21.8350 | 13 | 0.3846 | 0.6279 | 66.4515 | 0 |

判断:

- OOFにより、同じvalidation月でfitとpolicy選択を行う過学習は抑えられた。
- 同一policy比較では、meta EVはtest合計を `-177.5218` から `-97.7845` へ改善した。
- ただし no_trade `0.0` にはまだ負けている。
- test-apply のR2はlong/shortともマイナスであり、EV calibrationの汎化は未達。
- 2024-12ではmax drawdownも大きく、regime shift時のentry/exit判定がまだ壊れる。

次の修正:

- validationだけでmetaをfitせず、train期間にもOOF predictionsを作り、meta学習量を増やす。
- OOF metaを標準のpolicy選択手順にし、fit月と選択月の混同を禁止する。
- regime特徴量、月次volatility、trend/downtrend特徴量をmeta入力へ追加する。
- EV予測をそのまま信じず、calibration shrinkageやquantile calibrationで過大評価を抑える。
- 2024-12の失敗tradeを分解し、entry方向の誤りかexit遅れかを別々に診断する。
