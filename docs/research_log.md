# Research Log

時系列の作業記録。判断、実験、失敗、次の行動を追記する。

## 2026-06-28 JST

### 作業

- XAUUSD の HistData 取得パイプラインを作成。
- M1 の長期データを取得。
- M1 から M5 を生成。
- Tick の 2025 年 1 月サンプルを取得・変換。
- データ検証を実行。
- 研究目的とドキュメント運用を `GOAL.md` と `docs/` に整理。
- 体系的な作業まとめ、時系列ログ、実験レポートテンプレート、意思決定ログを追加。

### データ状態

- M1: 6,025,170 rows
- M5: 1,214,607 rows
- Tick sample: 5,798,226 rows

### 検証結果

- M1/M5 は timestamp 重複なし。
- M1/M5 は NULL なし。
- M1/M5 は OHLC 不整合なし。
- Tick sample は Bid/Ask 逆転なし。
- 大きな gap は週末・祝日由来が中心。

### 判断

- まず M1 ベースでバックテストとモデル評価の土台を作る。
- Tick は全期間取得せず、最初は約定・スプレッド検証用に限定利用する。
- 任意の 1 か月間の利益最大化を目的にするが、単月過学習を避けるため複数月検証を必須にする。

### 次の行動

- バックテスト環境を作る。
- `flat / long / short / close / hold` の状態遷移を実装する。
- ルールベースのベースラインを作り、月次スコアを出す。

### 追加作業

- M1 の次足 open 約定バックテストを実装。
- 1 玉制約、ロング/ショート、24 時間強制決済、月次評価を実装。
- `no_trade`, `random`, `ma_cross`, `rsi_reversal`, `breakout` のベースライン戦略を実装。
- trade log、equity curve、metrics、config の成果物保存を実装。
- 単体テストで、次足約定、強制決済、反転時に即時ドテンしない挙動を確認。

### ベンチマーク

対象月: 2025-01

| strategy | adjusted pnl | raw pnl | trades | win rate | max drawdown |
|---|---:|---:|---:|---:|---:|
| no_trade | 0.0000 | 0.000 | 0 | 0.0000 | 0.0000 |
| rsi_reversal | -56.5288 | 181.776 | 1069 | 0.6492 | 123.4142 |
| random | -107.9284 | -65.748 | 49 | 0.4082 | 112.7517 |
| ma_cross | -279.2953 | -39.229 | 485 | 0.3402 | 309.5242 |
| breakout | -311.2774 | -141.790 | 156 | 0.3077 | 320.3002 |

成果物:

- `data/reports/backtests/20260627_165623_benchmark_2025-01/`

### 判断

- ベースラインは 2025-01 では全て adjusted pnl がマイナス。
- raw pnl がプラスでも、利益 0.9 倍・損失 1.3 倍の補正で期待値が悪化する例が出ている。
- 次は、未来 24 時間の最良 exit に基づく教師ラベルと、リークのない特徴量を作る。

### 特徴量・ラベル作成

- `src/trade_data/dataset.py` を追加。
- M1 の月次 dataset 生成CLIを追加。
- 特徴量は現在barと過去rollingだけから作る。
- ラベルは次足open entry、未来24時間内のbest exitから作る。
- FFT特徴量として 64/256 window の low/high power と spectral centroid を追加。
- 2025-01 の edge1 と edge15 dataset を生成。

生成物:

- `data/processed/datasets/xauusd_m1/xauusd_m1_2025-01_h24_edge1.parquet`
- `data/processed/datasets/xauusd_m1/xauusd_m1_2025-01_h24_edge15.parquet`

edge15 summary:

- rows: 30,197
- feature_count: 47
- labels: short 5,175 / stay_flat 8,390 / long 16,632
- best adjusted pnl mean: 19.4884
- best adjusted pnl median: 19.2177

### 判断

- edge1 は stay_flat が 100 件しかなく、分類問題として偏りが強い。
- edge15 は stay_flat が増え、初期学習に使いやすい。
- ただし edge は test 月に合わせず、validation で調整する。
- 次は複数月 dataset を生成し、train/valid/test split を固定する。

### Target 方針の見直し

- 3クラスラベルだけでは情報を落としすぎるため、主ターゲットにしない方針に変更。
- `docs/decisions/0002_multitask_targets.md` を追加。
- dataset に連続ターゲットと量子化補助ターゲットを追加。
- edge1/edge15 dataset を新フォーマットで再生成。

追加ターゲット:

- long/short best adjusted pnl
- long/short forced adjusted pnl
- long/short max adverse pnl
- long/short best holding minutes
- side score
- best adjusted pnl quantile
- side score quantile
- holding time bins

再生成結果:

- edge1: rows 30,197 / columns 80 / nulls 0
- edge15: rows 30,197 / columns 80 / nulls 0
- edge15 labels: short 5,175 / stay_flat 8,390 / long 16,632
- edge15 best adjusted pnl quantile: 6,040 / 6,039 / 6,039 / 6,039 / 6,040
- edge15 side score quantile: 6,040 / 6,039 / 6,039 / 6,039 / 6,040

### 複数月 Dataset

2024-01 から 2024-07 まで、edge15 の dataset を同一仕様で生成した。

split:

- train: 2024-01 から 2024-06
- valid: 2024-07
- test: 2025-01

月次 rows:

| month | rows | short | stay_flat | long |
|---|---:|---:|---:|---:|
| 2024-01 | 30,028 | 6,941 | 17,253 | 5,834 |
| 2024-02 | 28,808 | 3,269 | 22,609 | 2,930 |
| 2024-03 | 27,589 | 4,204 | 9,955 | 13,430 |
| 2024-04 | 30,299 | 11,303 | 3,862 | 15,134 |
| 2024-05 | 31,523 | 10,681 | 10,511 | 10,331 |
| 2024-06 | 27,507 | 7,833 | 9,598 | 10,076 |
| 2024-07 | 31,587 | 8,951 | 8,728 | 13,908 |

### 初回 Multi-task 学習

`src/trade_data/modeling.py` を追加し、軽量な HistGradientBoosting で初回モデルを学習した。

学習ターゲット:

- regression: `long_best_adjusted_pnl`, `short_best_adjusted_pnl`, `side_score`
- classification: `best_adjusted_pnl_quantile`, `side_score_quantile`, `label`

実験:

- command: `python3 -m trade_data.modeling train --train-start 2024-01 --train-end 2024-06 --valid-start 2024-07 --valid-end 2024-07 --test-start 2025-01 --test-end 2025-01 --min-adjusted-edge 15 --max-iter 80 --learning-rate 0.05 --entry-threshold 15`
- artifacts: `experiments/20260627_171852_hgb_multitask_edge15/`
- report: `docs/reports/2026-06-28_hgb_multitask_initial.md`

主要結果:

| split | rows | selected trades | oracle-exit adjusted pnl | avg pnl | side acc | label macro F1 |
|---|---:|---:|---:|---:|---:|---:|
| train | 175,754 | 67,942 | 1,786,652.8970 | 26.2967 | 0.8215 | 0.7885 |
| valid | 31,587 | 14,741 | 217,820.3601 | 14.7765 | 0.5207 | 0.4351 |
| test | 30,197 | 22,589 | 319,595.3148 | 14.1483 | 0.5636 | 0.4200 |

判断:

- train と valid/test の差が大きく、過学習または期間依存が見える。
- test の side accuracy は 0.5636 で完全なランダムよりは良いが、regression R2 は不安定。
- selection metric は oracle exit を使っているため、まだ実行可能な取引成績ではない。
- 次は予測値だけで entry/exit する backtest policy を実装し、同じ取引制約で評価する。

### 実行可能 Model Policy

`src/trade_data/backtest.py` に、保存済みモデル予測を使う backtest policy を追加した。

追加CLI:

- `python3 -m trade_data.backtest model-policy ...`
- `python3 -m trade_data.backtest model-sweep ...`

policy:

- `stateless_ev`: 各 decision bar で predicted long/short EV が entry threshold を超えた時だけ desired position を出す。
- `stateful_ev`: flat 時は entry threshold を超えた時だけ入る。保有中は、保有側EVが exit threshold 未満、または反対側EVが十分強い場合に閉じる。

validation sweep:

- month: 2024-07
- predictions: `experiments/20260627_171852_hgb_multitask_edge15/predictions_valid.parquet`
- artifacts: `data/reports/backtests/20260627_172832_model_sweep_2024-07/`
- best valid setting: `stateful_ev`, entry threshold 30, exit threshold 10, side margin 5
- best valid adjusted pnl: -5.4446

test:

- month: 2025-01
- predictions: `experiments/20260627_171852_hgb_multitask_edge15/predictions_test.parquet`
- artifacts: `data/reports/backtests/20260627_172849_model_stateful_ev_2025-01/`
- adjusted pnl: -35.8255
- raw pnl: 4.5610
- trades: 21
- win rate: 0.5714
- profit factor: 0.7239
- max drawdown: 71.5889
- forced exits: 1

判断:

- oracle exit を使った selection metric と実行可能 backtest の差が大きい。
- raw pnl はわずかにプラスでも、利益 0.9 倍・損失 1.3 倍の補正後はマイナスになる。
- valid 最良設定でも valid adjusted pnl がマイナスなので、このモデルは no_trade をまだ超えていない。
- 2025-01 の trading baseline では `rsi_reversal` が -56.5288 だったため、model policy の -35.8255 は既存 trading baseline より損失が小さい。
- 次は exit timing target、risk target、expected pnl calibration を改善する。

### 過学習対策の方針整理

会話上の判断:

- 少ないデータでも過学習しにくい設計が理想。
- ただし XAUUSD の M1 データは年単位で増やせるため、まず期間依存を測れるだけの月数を用意する。
- データ増加の目的は「複雑なモデルを正当化すること」ではなく、「どの月・局面で壊れるかを見える化すること」。
- 単月最適化を避けるため、validation で閾値・calibration を決め、test では一度だけ評価する。
- 現モデルの主な弱点は、方向よりも exit timing と predicted EV の過大評価。

次に試すこと:

1. 追加月の dataset を生成する。
2. `long/short_best_holding_minutes` を予測対象に加え、exit timing に使う。
3. validation で expected pnl calibration を行い、calibrated EV で backtest policy を動かす。
4. walk-forward split で複数月に対する安定性を確認する。
5. 正則化を強めた HGB と比較し、モデル容量より汎化を優先する。

### 旧倍率train / 新倍率validation のpolicy選択

会話上の判断:

- 学習 dataset と教師 target は旧倍率 0.9 / 1.3 のまま維持する。
- validation と final test の executable backtest は新倍率 1.0 / 1.25 で評価する。
- validation を旧倍率のままにすると、no_trade に近い低参入設定へ寄りすぎるため、新倍率でpolicyを選ぶ。
- test 月で閾値を選ばない。複数 validation fold の集計でpolicyを選ぶ。

実装:

- `src/trade_data/backtest.py` に `model-sweep-summary` を追加。
- 複数の `model-sweep` CSVを、`policy`, `entry_threshold`, `exit_threshold`, `side_margin`, `risk_penalty` ごとに集計する。
- 集計時に、fold数、最低取引数、強制決済率、drawdown、各foldの最低 adjusted pnl を制約として使えるようにした。
- `tests/test_backtest.py` に、sweep CSV正規化と複数fold集計のテストを追加。

実験:

- fold A validation: 2024-07
  - model: `experiments/20260627_174250_hgb_multitask_edge15/`
  - sweep: `data/reports/backtests/20260627_180433_model_sweep_2024-07/`
- fold B validation: 2025-01
  - model: `experiments/20260627_174030_hgb_multitask_edge15/`
  - sweep: `data/reports/backtests/20260627_180029_model_sweep_2025-01/`
- summary: `data/reports/backtests/20260627_180908_model_sweep_summary/`

summary条件:

- min folds: 2
- min trades per fold: 30
- max forced exit rate: 0.0
- max drawdown: 100
- min adjusted pnl per fold: 0
- sort: mean adjusted pnl

暫定候補:

- policy: `timed_ev`
- entry threshold: 15
- exit threshold: 0
- side margin: 5
- risk penalty: 0
- validation mean adjusted pnl: 133.9964
- validation min adjusted pnl: 120.5680
- validation mean trades: 46.0
- validation max drawdown: 66.4905
- validation forced exits: 0

2025-02 test 診断:

- artifacts: `data/reports/backtests/20260627_180701_model_timed_ev_2025-02/`
- adjusted pnl: +23.7253
- raw pnl: +78.7070
- trades: 42
- win rate: 0.5000
- profit factor: 1.0863
- max drawdown: 112.5325
- forced exits: 0

比較:

- 2025-02 no_trade: 0.0000
- 2025-02 random: -14.0078
- 2025-02 breakout: -103.0195
- 2025-02 ma_cross: -203.7905
- 2025-02 rsi_reversal: -296.2607

判断:

- no_trade を超える実行可能policyが出た。
- ただし 2025-02 test の drawdown は validation制約の 100 を少し超えたため、まだ安定とは言えない。
- validation単月最高の stateful/risk付き設定は test で +6.6193 まで落ちた。単月最適化は危険。
- forced exit rate 0 を制約に入れると、exit timing が壊れている候補を避けやすい。
- 次は fold を増やし、`timed_ev` の保持時間予測だけでなく exit probability / trailing logic を比較する。

### 追加 Walk-forward Fold

目的:

- 2foldだけではpolicy selectionが偶然安定して見えている可能性がある。
- 2024-07 と 2025-01 の間に 2024-09 validation fold を追加し、同じ候補が残るか確認する。

split:

- train: 2023-01 から 2024-08
- valid: 2024-09
- test: 2024-10

model:

- artifacts: `experiments/20260627_183038_hgb_multitask_edge15/`
- model type: HistGradientBoosting multi-task
- train target: 旧倍率 0.9 / 1.3
- validation/test backtest: 新倍率 1.0 / 1.25

2024-09 valid sweep:

- artifacts: `data/reports/backtests/20260627_183050_model_sweep_2024-09/`
- 単月上位は risk付き `stateful_ev` だったが、強制決済を含む。
- forced exit rate 0 の候補では `timed_ev` が有力。

3fold summary:

- artifacts: `data/reports/backtests/20260627_183241_model_sweep_summary/`
- folds: 2024-07, 2024-09, 2025-01
- constraints: min trades 30, max forced exit rate 0, max drawdown 100, min adjusted pnl per fold 0
- selected candidate: `timed_ev`, entry threshold 15, exit threshold 0, side margin 5, risk penalty 0
- validation mean adjusted pnl: 126.3996
- validation min adjusted pnl: 111.2060
- mean trades: 43.3333
- max drawdown: 66.4905
- forced exits: 0

2024-10 test:

- artifacts: `data/reports/backtests/20260627_183253_model_timed_ev_2024-10/`
- adjusted pnl: +48.9555
- raw pnl: +99.6620
- trades: 43
- win rate: 0.6047
- profit factor: 1.1931
- max drawdown: 77.1468
- forced exits: 0

2024-10 baseline:

- random: +43.9895
- no_trade: 0.0000
- breakout: -206.6695
- rsi_reversal: -242.5953
- ma_cross: -397.3735

判断:

- 3foldでも標準候補は変わらなかった。
- 2024-10 test では no_trade と random を上回った。
- ただし signal は long 側に偏っており、上昇局面依存の疑いが残る。
- 次は short 優勢またはレンジ相場を含むfoldを追加し、direction bias を評価する。

### Short/Down-Regime 確認

目的:

- 2024-10 test で標準候補の signal が long 側に偏っていた。
- short 優勢または下落局面で、標準候補が維持できるか確認する。

split:

- train: 2023-01 から 2024-10
- valid: 2024-11
- test: 2024-12

月次価格変化:

- 2024-11: -3.517%
- 2024-12: -1.090%

model:

- artifacts: `experiments/20260627_183919_hgb_multitask_edge15/`

2024-11 valid sweep:

- artifacts: `data/reports/backtests/20260627_183932_model_sweep_2024-11/`
- 単月上位は short を多く取る stateful 系だった。
- 従来候補 `timed_ev entry=15 side_margin=5 risk=0` は adjusted pnl -21.0065、max drawdown 199.0998、forced exit rate 0.0208 で、このfoldでは崩れた。

4fold strict summary:

- artifacts: `data/reports/backtests/20260627_184136_model_sweep_summary/`
- folds: 2024-07, 2024-09, 2024-11, 2025-01
- constraints: min trades 30, forced exit rate 0, max drawdown 100, min adjusted pnl per fold 0
- result: eligible candidate なし

4fold relaxed summary:

- artifacts: `data/reports/backtests/20260627_184150_model_sweep_summary/`
- constraints: min trades 30, forced exit rate 0.5, max drawdown 150, min adjusted pnl per fold 0
- top eligible: `stateful_ev`, entry 5, exit 10, side margin 5, risk penalty 0.1
- validation mean adjusted pnl: 113.5546
- validation min adjusted pnl: 100.7555
- forced exit rate max: 0.5000

2024-12 test:

- standard candidate artifact: `data/reports/backtests/20260627_184333_model_timed_ev_2024-12/`
- standard candidate adjusted pnl: -175.6668
- raw pnl: -107.4190
- trades: 44
- win rate: 0.3636
- profit factor: 0.4852
- max drawdown: 206.9538
- forced exits: 0
- long adjusted pnl: -110.5037
- short adjusted pnl: -65.1630
- long trades: 12
- short trades: 32

2024-12 baseline:

- rsi_reversal: +41.0018
- random: +0.8950
- no_trade: 0.0000
- ma_cross: -34.3620
- breakout: -158.6600

判断:

- 下落/short寄りfoldを入れると、従来の標準候補は棄却される。
- 2024-12では short signal が多いにもかかわらず short trades も損失なので、単純な long bias ではない。
- 失敗は、下落/レンジ局面での entry timing、exit timing、EV calibration の崩れと見る。
- 次は `model-sweep-summary` に方向別P/L、long/short exposure、regime別評価を入れる。
- モデル側では regime feature、volatility/trend classifier、side-specific calibration を検討する。

### Mixed-Regime Weighted Training

問題意識:

- testで過学習が判明しているため、現時点の学習品質は高くない。
- 一部の連続した数か月だけでtrain/validを作ると、相場局面に依存したモデルになりやすい。
- 学習データ自体に、上昇・下落・レンジを混ぜる必要がある。

実装:

- `src/trade_data/modeling.py` に `--train-months`, `--valid-months`, `--test-months` を追加。
- 非連続の月リストでsplitを作れるようにした。
- `--sample-weighting none|month|label|month_label` を追加。
- `month_label` は各 `dataset_month × label` セルの総重みを揃える。

実験:

- report: `docs/reports/2026-06-28_mixed_regime_weighted_training.md`
- model: `experiments/20260627_185200_hgb_multitask_edge15/`
- train: 2023-01..2023-12, 2024-01..2024-06, 2024-08, 2024-10
- valid: 2024-07, 2024-09, 2024-11, 2025-01
- test: 2024-12, 2025-02
- sample weighting: `month_label`
- target clip quantile: 0.99
- max leaf nodes: 15
- min samples leaf: 100
- l2: 0.2

validation:

- strict summary artifact: `data/reports/backtests/20260627_185959_model_sweep_summary/`
- relaxed summary artifact: `data/reports/backtests/20260627_190009_model_sweep_summary/`
- strict constraints では eligible candidate なし。
- relaxed constraints では `timed_ev`, entry 10, side margin 5, risk penalty 0.4 が選ばれた。
- validation mean adjusted pnl: +146.0508
- validation min adjusted pnl: +73.0053
- max drawdown: 124.0158
- max forced exit rate: 0.0213

test:

- 2024-12 artifact: `data/reports/backtests/20260627_190023_model_timed_ev_2024-12/`
- 2024-12 adjusted pnl: -183.5370
- 2024-12 long adjusted pnl: -128.3435
- 2024-12 short adjusted pnl: -55.1935
- 2025-02 artifact: `data/reports/backtests/20260627_190023_model_timed_ev_2025-02/`
- 2025-02 adjusted pnl: +54.9137

判断:

- 学習データ混合と `month_label` weighting は、validation上の下落月では改善した。
- しかし 2024-12 test には汎化せず、過学習問題は解決していない。
- 2025-02 は改善したため、方向性に一部効果はある。
- 次は閾値調整ではなく、教師targetと特徴量の改善が必要。
- 特に oracle best exit target だけでは、実行可能なentry/exit timingを学習しきれていない可能性が高い。

### 評価倍率の緩和

会話上の判断:

- no_trade に負け続けると比較が難しいため、評価倍率を緩和する。
- 旧ルール: profit multiplier 0.9 / loss multiplier 1.3
- 新ルール: profit multiplier 1.0 / loss multiplier 1.25

作業方針:

- 既存モデルは旧倍率 target で学習しており、今後も学習 dataset は旧倍率を維持する。
- validation の policy 選択は新倍率 backtest で行う。
- test も validation で選んだ設定を固定した上で、新倍率 backtest で評価する。
- validation を旧倍率で行うと、no_trade に近い方向、つまり参入回数を下げる方向へ最適化されすぎるため、新倍率 validation で十分な参入を維持する。
- 旧 dataset を上書きしない。

補足:

- 新倍率 dataset は `data/processed/datasets/xauusd_m1_p100_l125/` に生成済みだが、主経路の学習には使わない。
- 以後は旧倍率 target での学習効率向上、calibration、exit timing、walk-forward 安定性を優先する。

標準フロー:

```text
train target: old multipliers 0.9 / 1.3
validation policy selection: new multipliers 1.0 / 1.25
final test: new multipliers 1.0 / 1.25
```

### Dense Entry Quality Target

会話上の問題提起:

- entry timing を直接学習させると、正例が少なくなり学習量が足りない。
- `long / short / stay_flat` まで圧縮すると、deep learning に渡す情報として粗すぎる。
- 1つのdatasetを、entry方向だけでなく、entryに向いている度合い、待つべきか、exit timing、EV calibration など多方面から学習に使いたい。

判断:

- entry timing は単一分類ではなく、密な品質targetに分解する。
- 量子化は情報を落とす主手段ではなく、連続targetのノイズを安定化する補助タスクとして使う。
- 学習datasetは旧倍率 0.9 / 1.3 を維持する。
- validation/test の policy 評価は新倍率 1.0 / 1.25 を維持する。

実装:

- `src/trade_data/dataset.py`
  - `long_profit_barrier_hit`, `short_profit_barrier_hit`
  - `long_wait_regret`, `short_wait_regret`
  - `long_entry_local_rank`, `short_entry_local_rank`
  - `long_entry_urgency`, `short_entry_urgency`
  - wait regret quantile と local rank bin
  - `--entry-timing-lookahead-minutes`, default 60
- `src/trade_data/modeling.py`
  - 上記targetを regression/classification のmulti-task学習対象に追加。
  - predictions parquet に真値と予測値を残す。
- `tests/test_dataset.py`
  - barrier hit と新target列の生成を確認。

次の行動:

1. 新schemaで旧倍率datasetを再生成する。
2. mixed-regime split で新target込みのHGBを学習する。
3. validation foldで calibrated EV と timed policy を再選択する。
4. 2024-12 test の失敗が entry quality target で緩和されるか確認する。

検証:

- `python3 -m unittest discover tests`: 23 tests OK
- 2025-01 の1か月datasetを `/tmp` に新schemaで生成し、rows 30,197、旧label分布は従来edge15と一致。
- 2024-07 から 2024-09 の3か月datasetを `/tmp` に新schemaで生成。
- `max_iter=2`, `sample_frac=0.2` のスモーク学習で、追加した全targetの train/evaluate/prediction 保存まで完了。

### Dense Entry Quality 実験

作業:

- 主datasetを 2023-01 から 2025-12 まで新schemaで再生成。
- dense entry quality target込みで mixed-regime HGB を再学習。
- HGBはtargetごとの独立モデルなので、追加targetがEVモデルの表現改善には直接効かない点を確認。
- `model-policy` / `model-sweep` に quality filter を追加。
  - `--max-wait-regret`
  - `--min-entry-rank`
  - `--require-profit-barrier`

実験:

- report: `docs/reports/2026-06-28_dense_entry_quality_targets.md`
- model: `experiments/20260627_192112_hgb_multitask_edge15/`
- validation quality summary: `data/reports/backtests/20260627_192904_model_sweep_summary/`

validation選択:

- `timed_ev`, entry 5, exit 0, side margin 5, risk penalty 0.1, min entry rank 0.5
- validation mean adjusted pnl: +38.6307
- validation min adjusted pnl: +2.3763
- min trades per fold: 17
- max drawdown: 85.5988
- max forced exit rate: 0.0476

test:

- 2024-12: adjusted pnl -135.9573
- 2025-02: adjusted pnl -101.0583

追加診断:

- 強く絞る候補では 2024-12 が -9.5233 まで改善したが、5 trades しかなく、2025-02 は -43.2768。

判断:

- entry quality filter は露出削減と損失抑制には効く。
- しかし no_trade を超えるedgeはまだ出ていない。
- 次は、予測済みtargetを入力にした二段階meta model、またはshared representationの小型深層学習へ進む。

### 二段階 Meta EV Model

作業:

- `src/trade_data/meta_model.py` を追加。
- validation predictions を long/short の side-aware examples に展開し、base modelの予測済みtargetから side別 adjusted pnl を再推定するHGBを実装。
- `trade-meta` CLIを追加。

実験:

- meta artifact: `experiments/20260627_193559_meta_ev_dense_entry_quality/`
- train predictions: `experiments/20260627_192112_hgb_multitask_edge15/predictions_valid.parquet`
- apply predictions: `experiments/20260627_192112_hgb_multitask_edge15/predictions_test.parquet`

結果:

- validation-fit R2: long 0.1837 / short 0.1980
- test-apply R2: long -0.0652 / short -0.1921
- meta EV + standard quality candidate:
  - 2024-12: -240.5445
  - 2025-02: +23.7068
- meta EV + stronger filter:
  - 2024-12: -114.5178
  - 2025-02: -71.8913

判断:

- validationにfitしたmeta modelは、testでは再過学習している。
- 2025-02は一部改善するが、2024-12で崩れるため採用しない。
- 次は meta fit 月と policy selection 月を分ける。validation内walk-forwardでmeta modelを評価する。
