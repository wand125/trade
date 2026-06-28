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
- report: `docs/reports/00003_2026-06-28_hgb_multitask_initial.md`

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

- report: `docs/reports/00006_2026-06-28_mixed_regime_weighted_training.md`
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

- report: `docs/reports/00007_2026-06-28_dense_entry_quality_targets.md`
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

### Validation-internal OOF Meta

作業:

- `meta_model fit` に `--train-months` / `--apply-months` を追加し、同じprediction fileから月を分けてfit/applyできるようにした。
- validation 4ヶ月で leave-one-month-out meta を実施。
- 各holdout月のmeta予測でpolicy sweepし、4fold summaryで候補を選択した。

OOF artifacts:

- `experiments/20260627_194501_meta_oof_2024-07/`
- `experiments/20260627_194501_meta_oof_2024-09/`
- `experiments/20260627_194501_meta_oof_2024-11/`
- `experiments/20260627_194501_meta_oof_2025-01/`
- summary: `data/reports/backtests/20260627_194724_model_sweep_summary_1/`

選択:

- policy: `timed_ev`
- entry threshold: 10
- side margin: 5
- risk penalty: 0.2
- max wait regret: 2
- min entry rank: 0.5
- require profit barrier: false
- validation OOF mean adjusted pnl: +72.4758
- validation OOF min adjusted pnl: +3.0118
- min trades per fold: 28
- max drawdown: 83.2353
- forced exit max: 0

test:

- final meta artifact: `experiments/20260627_194740_meta_all_valid_to_test_oof_selected/`
- 2024-12: adjusted pnl -97.3488, 31 trades, profit factor 0.5403, max drawdown 143.0608
- 2025-02: adjusted pnl -0.4358, 21 trades, profit factor 0.9971, max drawdown 72.8378

比較:

- 同じpolicyのmetaなしbase予測は 2024-12 -130.3193 / 2025-02 -47.2025。
- OOF選択metaはbaseよりtest合計を改善したが、no_trade 0.0 にはまだ負ける。
- final metaのtest R2は long -0.0652 / short -0.1921 で、EV calibration自体の汎化はまだできていない。

判断:

- 過学習は悪化していない。fit月と選択月を分けたことで、同月fit/同月選択の漏れは抑えられた。
- ただしtestでNoTradeに勝てていないため、過学習は解消していない。
- 次はvalidationだけでmetaを学習するのをやめ、train期間にもOOF predictionsを作ってmeta学習量を増やす。
- 2024-12の失敗tradeをentry方向、exit遅れ、EV過大評価に分けて診断する。

### 学習時間と過学習対策

作業:

- HGBに過学習抑制パラメータを追加。
  - `max_depth`
  - `max_features`
  - `early_stopping`
  - `validation_fraction`
  - `n_iter_no_change`
  - `tol`
- defaultを保守的に変更。
  - `learning_rate=0.03`
  - `max_leaf_nodes=15`
  - `max_depth=4`
  - `min_samples_leaf=100`
  - `l2_regularization=0.2`
  - `max_features=0.8`
  - `target_clip_quantile=0.99`
  - `sample_weighting=month_label`
- `model_diagnostics` を追加し、targetごとの `n_iter` とmax_iter到達有無を保存。
- `target-set policy` を追加し、executable policyに必要なtargetだけで長時間学習比較できるようにした。
- meta modelにも `month_side` weighting、regime feature input、prediction shrinkage、強めの正則化defaultを追加。
- 2019-01 から 2022-12 のdatasetを生成し、データ増量の準備も行った。

実験:

- report: `docs/reports/00009_2026-06-28_training_time_and_generalization.md`
- iter80: `experiments/20260627_201301_policy_iter80_base_train/`
- iter320: `experiments/20260627_201455_policy_iter320_base_train/`
- train rows: 546,537
- target set: `policy`
- valid: 2024-07, 2024-09, 2024-11, 2025-01
- test: 2024-12, 2025-02

結果:

- iter80もiter320も、14 targetすべてがmax_iterに到達した。
- iter320はvalidation selection pnlを増やしたが、test side accuracyは改善しなかった。
- iter80はvalidation sweepで10 trades/fold条件でもeligibleなし。
- iter320は10 trades/fold条件でeligibleが出たが、30 trades/fold条件ではeligibleなし。
- min fold pnl優先候補:
  - `timed_ev entry=15 side_margin=0 risk=0 max_wait_regret=4 min_entry_rank=0 require_profit_barrier=true`
  - validation mean adjusted pnl: +41.8295
  - validation min adjusted pnl: +26.2700
  - min trades per fold: 15
  - max drawdown: 51.2338
- test:
  - 2024-12: -99.9843
  - 2025-02: -38.9125

判断:

- 学習時間を伸ばす余地はある。少なくとも `max_iter=320` でも内部early stoppingは発火していない。
- ただし、学習時間を80から320へ伸ばしてもtestでNoTradeを超えない。
- validationでは改善するため、長く回すほどvalidationに適合する可能性がある。
- 今後さらに長く回す場合は、低learning rate、OOF validation、追加test月をセットにして、validation過適合かどうかを確認する。
- データ増量は面白いが、本流は「反復数を伸ばしても汎化するか」を厳密に見ること。

### 1280 Iter 追試

作業:

- iter320と同じ条件で `max_iter=1280` を試した。
- artifact: `experiments/20260627_202929_policy_iter1280_base_train/`

結果:

- 14 targetすべてが `max_iter=1280` に到達した。
- valid selection pnlは 1,025,559.2831 まで増えた。
- ただし valid R2 は long 0.0014 / short -0.0107 で、iter320より悪化。
- test R2 は long -0.0213 / short -0.0591。
- test side accuracyは 0.4744 でiter320より少し上がったが、実行可能backtestでは改善しなかった。
- validation sweepでは、30 trades/foldでも10 trades/foldでもeligible候補なし。
- 参考候補 `timed_ev entry=15 side_margin=0 risk=0.2 max_wait_regret=4 require_profit_barrier=true` のtest:
  - 2024-12: -97.7620
  - 2025-02: -97.0460

判断:

- 1280は採用しない。
- 長く回すほど内部lossとselection量は増えるが、月別validationとtest backtestは安定しない。
- 次に長時間学習を試すなら、`learning_rate` を下げ、OOFまたは月別backtestをearly stopping指標にする必要がある。

### 1.0/1.2 Target/Evaluation Alignment

方針:

- 教師生成とvalidation/test評価の倍率差が予測EVのずれを作っている可能性を検証する。
- 新dataset `data/processed/datasets/xauusd_m1_p1_l1p2/` を作成し、profit 1.0 / loss 1.2 で教師を再生成した。
- validation/test/backtestも profit 1.0 / loss 1.2 に揃えた。
- 80iterへ戻す方針を維持しつつ、ユーザー指定により320iterも比較検証した。

実験:

- iter80: `experiments/20260627_203932_policy_iter80_p1_l1p2/`
- iter320: `experiments/20260627_204140_policy_iter320_p1_l1p2/`
- report: `docs/reports/00009_2026-06-28_training_time_and_generalization.md`

結果:

- iter80は10 trades/fold条件でもvalidation eligibleなし。
- iter320は10 trades/fold条件でvalidation eligible 31件。
- min fold pnl優先候補:
  - `timed_ev entry=5 side_margin=0 risk=0.1 max_wait_regret=inf min_entry_rank=0.5 require_profit_barrier=true`
  - validation mean adjusted pnl: `+31.5473`
  - validation min adjusted pnl: `+16.5412`
  - min trades/fold: `38`
  - max drawdown: `73.3766`
- `16.5412` は4つのvalidation月のうち最悪月の月間 `total_adjusted_pnl`。1オンス前提なので概ねUSDだが、profit 1.0 / loss 1.2 を適用したadjusted値で、raw値や%ではない。
- fixed test:
  - 2024-12: adjusted pnl `-131.6996`, raw pnl `-102.5750`, 35 trades
  - 2025-02: adjusted pnl `-71.2528`, raw pnl `-42.0540`, 39 trades
- test診断sweepでは、10 trades/fold以上かつ各fold PnL 0以上のeligible候補なし。

判断:

- 倍率をtrain/valid/testで揃えてもtest汎化は改善しなかった。
- 320iterはvalidationでは成立するがholdoutで崩れるため採用しない。
- 10 trades/月条件は今後の探索で許容するが、少数tradeだけのtestプラスはedgeとして扱わない。
- 次は倍率差ではなく、validation選択の過適合、regime差、exit timing target、expected PnL calibrationを優先する。

### 長時間学習と方向性レビュー

作業:

- 1.0/1.2 aligned datasetで長時間学習を追加診断した。
- same LR: `max_iter=1280`, `learning_rate=0.03`
- low LR: `max_iter=1280`, `learning_rate=0.01`
- 実験中にdocsを再読し、方向性レビューを作成した。
- report: `docs/reports/00008_2026-06-28_research_direction_review.md`

Artifacts:

- same LR: `experiments/20260627_205602_policy_iter1280_p1_l1p2/`
- low LR: `experiments/20260627_210612_policy_iter1280_lr001_p1_l1p2/`
- training report: `docs/reports/00009_2026-06-28_training_time_and_generalization.md`

結果:

- same LR 1280:
  - validation 30 trades/fold eligibleなし。
  - validation 10 trades/fold候補は `mean pnl=15.6527`, `min pnl=1.1964` と薄い。
  - fixed test: 2024-12 `-69.7450`, 2025-02 `-137.1102`。
- low LR 1280:
  - validation 30 trades/foldでeligible 2件。
  - min fold pnl優先候補:
    - `timed_ev entry=15 side_margin=0 risk=0 max_wait_regret=inf min_entry_rank=0 require_profit_barrier=true`
    - validation mean adjusted pnl `+48.2348`
    - validation min adjusted pnl `+40.8376`
    - min trades/fold `46`
  - fixed test: 2024-12 `-134.5306`, 2025-02 `-110.0922`。
- test sweepを後付けで見るとプラス候補はあるが、最上位test候補はvalidationでは `min pnl=-28.2506` でeligibleではない。

判断:

- 低LR長時間学習はvalidationでは明確に良くなる。
- しかしtest固定適用で崩れるため、主因は学習時間不足ではなく、validation selection過適合、regime shift、EV calibration崩れ、exit timing未解決と見る。
- HGBの反復数探索はここでいったん打ち切る。
- 次は以下を優先する。
  - 2024-12/2025-02のtrade failure analyzer。
  - train期間OOF predictions。
  - side/regime別EV calibration。
  - exit timing target強化。
  - shared representationを持つ小型MLP/TCN。

### 汎化原則レビューと失敗trade分析

作業:

- トレードMLの汎化原則を `docs/trading_ml_generalization_principles.md` に整理した。
- 現状がその原則を守れているかを `docs/reports/00011_2026-06-28_generalization_principles_review.md` にレビューした。
- 低LR1280モデルの固定test負けを分解する `trade-backtest analyze-trades` を追加した。
- 失敗trade分析レポートを `docs/reports/00010_2026-06-28_trade_failure_analysis.md` に作成した。

判断:

- NoTrade比較、月別validation/test、次足open約定、executable backtest、失敗trade分析は守れている。
- purging / embargo、regime別標準評価、spread/slippage/delay感度、validationを見すぎない運用は未整備。
- 2024-12/2025-02は何度も見たため、今後の最終holdoutとしては弱い。
- 低LR1280のtest失敗では、予測EVが実現PnLに対して平均約22ドル過大だった。
- actual barrier miss、direction error、exit regretが損失の中心。
- predicted barrierは今回の全tradeを通しており、filterとして弱い。
- `min_entry_rank=0.5` focused sweepは損失を抑えたが、NoTradeには届かなかった。

次の行動:

1. analyzerを今後の候補診断に必須化する。
2. regime labelをdataset/backtest reportへ追加する。
3. spread/slippage/delay sensitivityをbacktestへ追加する。
4. purged/embargo walk-forward splitを実装する。
5. OOF predictionsとside/regime別EV calibrationへ進む。

### Regime / Cost / Purge Controls

作業:

- `src/trade_data/regime.py` を追加し、regime scoreとregime categoryを標準化した。
- datasetに `trend_score_240`, `volatility_score_60` をfeatureとして追加し、`trend_regime`, `volatility_regime`, `session_regime`, `gap_regime`, `combined_regime` を診断列として保存するようにした。
- `analyze-trades` がregime別group outputを出せるようにした。
- backtestに `spread_points`, `slippage_points`, `execution_delay_bars` を追加した。
- 固定policyのコスト感度を見る `model-cost-sensitivity` を追加した。
- `trade_data.modeling train` に `--purge-label-overlap` と `--embargo-hours` を追加した。デフォルトでラベル期間が後続valid/testに重なるtrain/valid行をpurgeする。
- report: `docs/reports/00012_2026-06-28_regime_cost_purge_controls.md`

検証:

- `python3 -m unittest discover tests`: 40 tests OK。
- `git diff --check`: OK。
- `model-cost-sensitivity --help` と `modeling train --help`: OK。

判断:

- 検証設計上の不足だったregime分析、執行stress、label overlap purgeの土台は入った。
- この時点では既存datasetにregime列がなかったため、次はdataset再生成が必要と判断した。
- 次の実験は、regime列込みdataset、purge有効学習、固定policyのcost sensitivity、regime別failure analysisの順に進める。

### Regime/Purge HGB 80iter Follow-up

作業:

- 1.0/1.2 aligned datasetをregime列込みで 2023-01 から 2025-02 まで再生成した。
- `feature_count` は 49。追加featureは `trend_score_240` と `volatility_score_60`。
- purge実装にバグを発見した。複数test月を1つの連続windowとして扱い、2025-01 validが丸ごと落ちていた。
- `dataset_month` ごとにblocked windowを分割するよう修正し、非連続test月の間にあるvalid月を保持するテストを追加した。
- purge有効、embargo 24hで HGB 80iter policy modelを再学習した。

Artifact:

- model: `experiments/20260627_215123_policy_iter80_p1_l1p2_regime_purge_e24_v2/`
- validation sweep summary: `data/reports/backtests/20260627_215228_model_sweep_summary/`
- fixed test: `data/reports/backtests/20260627_215245_model_timed_ev_2024-12/`, `data/reports/backtests/20260627_215245_model_timed_ev_2025-02/`
- regime analysis: `data/reports/backtests/20260627_215257_analyze_regime_purge_v2_2024-12/`, `data/reports/backtests/20260627_215257_analyze_regime_purge_v2_2025-02/`

結果:

- 修正後purge: train 546,537 -> 535,493、valid 119,241 -> 112,494、test 56,204。
- 30 trades/fold条件ではeligibleなし。
- 10 trades/fold条件では `timed_ev entry=15 risk=0 max_wait=2 min_rank=0.5` が validation全foldプラス。
- fixed test:
  - 2024-12: adjusted pnl `-35.7010`, 15 trades, max DD `58.5892`
  - 2025-02: adjusted pnl `-47.6716`, 17 trades, max DD `54.6236`
- 多めに取引するeligible候補は 2024-12 `-154.9860`、2025-02 `-125.5468` と悪化。
- regime分析では、両testともtradeが `low_vol` に集中した。
- 2025-02は `asia` が `-46.9276`、`rollover` が `-24.8160`、`ny_late` が `+24.0720`。

判断:

- regime/cost/purgeの基盤は有効だが、HGB 80iterの汎化成績はまだ改善していない。
- NoTradeに負けているため採用不可。
- 次は低ボラ・asia・rolloverでentryを抑えるregime gate、direction/regime別calibration、profit barrier確率化を試す。

### Regime Gate Experiment

作業:

- `model-policy` / `model-sweep` に hard regime gate を追加した。
- `--block-trend-regimes`, `--block-volatility-regimes`, `--block-session-regimes`, `--block-gap-regimes`, `--block-combined-regimes` を追加。
- gate条件は `quality_ok` に合成し、新規entryだけを抑制する。保有中のexitや強制決済は変えない。
- `model-sweep-summary` では block条件もpolicy keyに含め、gateあり/なしを別候補として集計する。
- report: `docs/reports/00013_2026-06-28_regime_gate_experiment.md`

検証:

- `python3 -m unittest discover tests`: 41 tests OK。
- `git diff --check`: OK。

Validation:

- 対象モデル: `experiments/20260627_215123_policy_iter80_p1_l1p2_regime_purge_e24_v2/`
- validation: 2024-07, 2024-09, 2024-11, 2025-01。
- `asia,rollover` gate top: mean pnl `31.3258`, min pnl `21.4868`, min trades `16`。
- `asia` gate top: mean pnl `40.0143`, min pnl `16.6970`, min trades `17`。
- `rollover` gate top: mean pnl `62.6525`, min pnl `38.4034`, min trades `15`。

Fixed test:

- `asia,rollover` validation top: 2024-12 `-121.9240`, 2025-02 `+58.5242`。
- `asia` validation top: 2024-12 `-127.9708`, 2025-02 `+63.3104`。
- `rollover` validation top: 2024-12 `-37.5214`, 2025-02 `-38.0992`。
- 前回候補に `asia,rollover` を足した場合: 2024-12 `+5.8384`、2025-02 `+24.0720`。ただし 7 trades / 3 trades と薄い。

判断:

- hard gateは損失回避のablationとして有用。
- ただし、採用policyとしては月間regime差に弱い。
- `asia` / `asia,rollover` は 2025-02を改善するが2024-12を悪化させる。
- `rollover` はvalidationでは強いがtestではNoTradeに負ける。
- 本流は hard block ではなく、side/regime別EV calibration、予測EV shrinkage、regime別threshold offsetへ進める。

### Side/Regime EV Calibration

作業:

- `trade_data.meta_model` に side/regime EV calibration を追加した。
- `fit-group-calibration` と `oof-group-calibration` を追加した。
- 出力列は `pred_regime_calibrated_long_best_adjusted_pnl` / `pred_regime_calibrated_short_best_adjusted_pnl`。
- validation内OOFでは、各validation月をholdoutし、残りvalidation月でcalibratorをfitする。
- testにはvalidation全体でfitしたcalibratorを固定適用する。
- report: `docs/reports/00014_2026-06-28_side_regime_ev_calibration.md`

検証:

- `python3 -m unittest tests.test_meta_model`: 11 tests OK。
- `python3 -m trade_data.meta_model oof-group-calibration --help`: OK。
- `git diff --check`: OK。

実験:

- 対象モデル: `experiments/20260627_215123_policy_iter80_p1_l1p2_regime_purge_e24_v2/`
- group columns: `volatility_regime,session_regime`
- validation: 2024-07, 2024-09, 2024-11, 2025-01。
- test: 2024-12, 2025-02。

Shrink to group mean:

- artifact: `experiments/20260627_221255_regime_ev_calib_vol_session/`
- summary: `data/reports/backtests/20260627_221441_model_sweep_summary/`
- OOF validation top: mean pnl `63.4787`, min pnl `13.9340`, min trades `28`。
- fixed test: 2024-12 `-260.2992`, 2025-02 `-6.6830`。

Residual offset:

- artifact: `experiments/20260627_221536_regime_ev_calib_vol_session_offset/`
- summary: `data/reports/backtests/20260627_221737_model_sweep_summary/`
- OOF validation top: mean pnl `102.5949`, min pnl `73.6080`, min trades `54`。
- fixed test top: 2024-12 `-185.8364`, 2025-02 `-65.1476`。
- fixed test conservative candidate: 2024-12 `-149.2616`, 2025-02 `-10.7646`。

判断:

- OOF validationでは強く改善するが、fixed testではraw EV候補より悪い。
- validation 4ヶ月だけのside/regime補正は未知test月へ汎化していない。
- calibrated EVはtestでentry数を増やしすぎる。
- 現時点では採用不可。
- 次は train期間OOF predictions を作ってcalibration fit月数を増やすか、exit timing target改善を優先する。

### Train-Period OOF Prediction Infrastructure

作業:

- `trade_data.modeling` に `oof` サブコマンドを追加した。
- 指定したOOF対象月を `--fold-month-count` ごとのholdout foldに分ける。
- 各foldでholdout月を学習から外し、必要なら `--purge-label-overlap` と `--embargo-hours` でlabel overlapを削除する。
- 予測は `predictions_oof.parquet` に保存する。
- report: `docs/reports/00015_2026-06-28_train_oof_predictions_infra.md`

検証:

- `python3 -m unittest tests.test_modeling`: 17 tests OK。
- `python3 -m trade_data.modeling oof --help`: OK。
- 軽量smoke run: `experiments/20260627_222746_oof_smoke_policy/`
- `python3 -m unittest discover tests`: 47 tests OK。
- `git diff --check`: OK。

判断:

- train期間OOF predictionsを作るための基盤は整った。
- smoke runは機能確認用であり、スコアは研究判断に使わない。
- 次は HGB 80iter regime/purge v2 と同じtrain monthsで本番OOFを実行し、validation OOFと結合してside/regime calibrationを再評価する。

### Train OOF Calibration and Loss 1.20 Standard

作業:

- `oof-group-calibration` に `--base-fit-predictions` / `--base-fit-months` を追加した。
- 各validation holdoutのcalibration fitを `train OOF + 他validation月` に変更できるようにした。
- `trade_data.dataset` と `trade_data.backtest` のデフォルト倍率を profit 1.0 / loss 1.20 に変更した。
- ADR `docs/decisions/0006_loss_multiplier_120_standard.md` を追加した。
- report: `docs/reports/00017_2026-06-28_train_oof_calibration_loss120.md`

実験:

- train OOF: `experiments/20260627_223559_policy_train_oof_4m_p1_l1p2_regime_purge_e24/`
- offset calibration: `experiments/20260627_223950_regime_ev_calib_train_oof4m_vol_session_offset/`
- shrink065 calibration: `experiments/20260627_224357_regime_ev_calib_train_oof4m_vol_session_shrink065/`
- shrink065 loss1.20 summary: `data/reports/backtests/20260627_224840_model_sweep_summary/`
- offset loss1.20 summary: `data/reports/backtests/20260627_225028_model_sweep_summary/`

結果:

- shrink065 top-min validation: mean pnl `49.9715`, min pnl `41.1354`, min trades `10`, max DD `35.1396`。
- shrink065 top-min fixed test: 2024-12 `+18.8306`, 2025-02 `-44.5990`。
- offset top-min validation: mean pnl `72.3580`, min pnl `46.8804`, min trades `15`, max DD `47.0160`。
- offset top-min fixed test: 2024-12 `-63.2266`, 2025-02 `-44.3740`。

判断:

- loss 1.20統一で損益は改善したが、NoTradeを安定して超える状態ではない。
- train OOFをcalibration fitに足す方向は、entry過多の抑制には効いた。
- shrink065は2024-12をプラス化したが、2025-02では少数のshort失敗が損失を支配する。
- 次は2025-02 short失敗tradeのregime/session分解と、exit timing targetの改善を優先する。

### 2026-06-28 08:07 JST Calibrated Trade Failure And Exit Targets

作業:

- `analyze-trades` に `--long-column` / `--short-column` を追加し、calibrated EV列を指定してtrade failure分析できるようにした。
- 既存レポートに日付だけでなく時刻を入れる運用へ変更した。
- 既存 `docs/reports/*.md` の冒頭メタデータを時刻付きへ整えた。通し番号や並びは本文の `日時` を基準にし、ファイル更新時刻や `更新日時` は採番に使わない。
- `future_best_labels` に固定保有 60/240/720 分のlong/short adjusted pnl targetを追加した。
- `modeling` は古いdatasetにも対応できるよう、存在しない研究用targetを自動的に落とし、missing targetsをmetricsへ記録するようにした。
- report: `docs/reports/00016_2026-06-28_calibrated_trade_failure_exit_targets.md`

結果:

- calibrated列で再分析した shrink065 top-min は、2024-12 `+18.8306`、2025-02 `-44.5990`。
- 2025-02は 12 trades、direction error rate `0.7500`、predicted side error rate `0.7500`、EV overestimate vs realized mean `20.0388`。
- 2025-02の実績best sideがshortだった8 tradesは全てlongで入り、adjusted pnl `-30.7830`。
- 唯一のshortは `2025-02-10 04:32 UTC` の `asia/up/low_vol` で、adjusted pnl `-39.0000`。

判断:

- 問題は単純な「shortが多すぎる」ではなく、calibrated EVの方向選択が未知月で壊れていること。
- 全tradeでexit regretが正で、勝ちtradeも含めて手放し方に改善余地がある。
- 固定horizon targetはまずfull target setの研究用targetとして追加し、policy target setにはまだ入れない。

### 2026-06-28 08:26 JST Fixed Horizon Exit Policy

作業:

- `data/processed/datasets/xauusd_m1_p1_l1p2/` を 2023-01 から 2025-02 まで再生成し、固定保有 60/240/720 分targetを実データに反映した。
- `trade_data.backtest` に `fixed_horizon_ev` policyを追加した。
- `--extra-side-margin-rules` を追加し、`session_regime=asia:5,session_regime=rollover:5` のようなregime別追加side marginを指定できるようにした。
- `target-set full` のHGB 80iterモデルを学習した。
- report: `docs/reports/00018_2026-06-28_fixed_horizon_exit_policy.md`

Artifacts:

- model: `experiments/20260627_231921_full_fixed_horizon_targets_p1_l1p2/`
- no extra margin validation summary: `data/reports/backtests/20260627_232147_model_sweep_summary/`
- asia/rollover +5 validation summary: `data/reports/backtests/20260627_232445_model_sweep_summary/`
- fixed test: `data/reports/backtests/20260627_232459_model_fixed_horizon_ev_2024-12/`, `data/reports/backtests/20260627_232459_model_fixed_horizon_ev_2025-02/`

結果:

- validation top-min候補: `fixed_horizon_ev`, entry `2`, side margin `2`, max wait regret `4`, min entry rank `0.5`, barrierなし, `asia/rollover +5`。
- validation: mean pnl `27.2219`, min pnl `19.1398`, min trades `45`, max DD `50.3740`。
- fixed test 2024-12: adjusted pnl `+30.2662`, 58 trades, max DD `25.2926`。
- fixed test 2025-02: adjusted pnl `+4.6898`, 71 trades, max DD `99.4746`。

判断:

- validationで選んだ同一候補が 2024-12 / 2025-02 の両test月でNoTradeを上回った。
- ただし2025-02のedgeは薄く、slippageやspreadで消える。
- 2025-02はlong pnl `+17.6144`、short pnl `-12.9246` で、short側の弱さは残る。
- 次は short専用entry threshold / side margin、barrier hit probability calibration、コスト込みvalidation選択を優先する。

### 2026-06-28 08:38 JST Side-Specific Entry Offsets

作業:

- `model-policy` / `model-sweep` に `long_entry_threshold_offset` と `short_entry_threshold_offset` を追加した。
- `SWEEP_KEY_COLUMNS` と `model-sweep-summary` 正規化にoffset列を追加した。
- `stateless_ev`, `stateful_ev`, `timed_ev`, `fixed_horizon_ev` のentry判定とflip判定にside別thresholdを適用した。
- レポート時刻を `YYYY-MM-DD HH:MM JST` で記録する方針を再確認し、既存fixed horizonレポートにも更新時刻を追記した。
- report: `docs/reports/00019_2026-06-28_side_specific_entry_offsets.md`

実験:

- model: `experiments/20260627_231921_full_fixed_horizon_targets_p1_l1p2/`
- validation months: 2024-07, 2024-09, 2024-11, 2025-01
- grid: entry `0,2,4`, long offset `0`, short offset `0,2,4,6,8`, side margin `1,2,3`
- no-cost summary: `data/reports/backtests/20260627_233509_model_sweep_summary/`
- cost-aware summary: `data/reports/backtests/20260627_233552_model_sweep_summary/`

結果:

- no-cost / cost-aware validation top-minはともに `entry=0`, `short offset=4`, `side margin=2`。
- top-min候補のfixed testは 2024-12 `+22.7102`、2025-02 `+0.3502`。前回候補より2025-02が薄くなった。
- validation rank-3の `entry=0`, `short offset=8`, `side margin=2` は診断比較で 2024-12 `+27.4184`、2025-02 `+26.8074`。
- `short offset=8` のcost sensitivityは 2024-12で spread `0.2` / slippage `0.10` / delay `1` が `-7.0904`、2025-02で同条件が `+16.8146`。
- trade failure分析では、2024-12 direction error rate `0.6034`、2025-02 `0.4754`。2025-02のexit regret sumは `1189.8406` で依然大きい。

判断:

- short専用entry threshold offsetは有効な調整軸。
- validation top-minだけでは未知月の安定性を選び切れていない。
- `short offset=8` はfixed test上では良いが、testを見てからの採用になるため本採用しない。
- 次は事前登録した選択基準として、cost-aware validation、周辺offsetの台地、side/regime別PnL、max drawdown、execution delay感度を組み込む。
- 新しいblind holdout月を追加し、2024-12/2025-02を見すぎない。

### 2026-06-28 08:53 JST Blind Holdout Candidate Selection

作業:

- `model-candidate-selection` を追加し、no-cost/cost-aware validation、cost drop、side loss、short offset plateauを同時に評価できるようにした。
- 2025-03 の p1/l1.2 fixed horizon datasetを追加生成した。
- 前回fixed horizon modelと同じtrain/validationで、testだけ2025-03にしたHGB 80iter full modelを学習した。
- report: `docs/reports/00020_2026-06-28_blind_holdout_candidate_selection.md`

Artifacts:

- dataset: `data/processed/datasets/xauusd_m1_p1_l1p2/xauusd_m1_2025-03_h24_edge15.parquet`
- model: `experiments/20260627_235034_full_fixed_horizon_blind_2025_03_p1_l1p2/`
- candidate selection: `data/reports/backtests/20260627_235220_model_candidate_selection/`
- blind test: `data/reports/backtests/20260627_235231_model_fixed_horizon_ev_2025-03/`
- cost sensitivity: `data/reports/backtests/20260627_235330_model_cost_sensitivity_2025-03/`

結果:

- candidate selection条件は `max_forced_exit_rate=0.04`, `max_side_loss_per_fold=45`, cost drop max `20`, short offset plateau radius `4`。
- validation選択候補は `fixed_horizon_ev`, entry `0`, short offset `8`, side margin `1`。
- 2025-03 blind holdoutは adjusted pnl `-49.7004`, raw pnl `-24.2030`, 63 trades, profit factor `0.6751`, max DD `73.8334`。
- long pnl `-0.3766`、short pnl `-49.3238`。short 5 tradesのうち、2025-03-31 01:28 UTC の1 tradeが `-49.3248`。
- 最大損失tradeは `range / low_vol / asia`、actual best sideはlong、predicted short fixed EVは `9.5934`、predicted short profit barrier hitは `0`。
- cost sensitivityは全条件でマイナス。spread `0.2` / slippage `0.10` / delay `1` では adjusted pnl `-75.9388`。

判断:

- short offsetとcost-aware validationだけでは汎化不足。
- 2024-12/2025-02で良く見えたshort offset候補は、2025-03でNoTradeに負けたため採用しない。
- 最大損失は predicted profit barrier hitが0のshortを許したこと、かつ721分まで保有したことが中心。
- 次は profit barrier probability calibration、`asia / range / low_vol` shortの抑制、hazard-like close probability / stop-loss timing targetを優先する。

### 2026-06-28 09:08 JST Profit Barrier Probability Gate

作業:

- binary classifierのclass `1` probabilityを `pred_<target>_prob` として保存するようにした。
- `model-policy` に `--profit-barrier-threshold`、`model-sweep` に `--profit-barrier-thresholds` を追加した。
- `SWEEP_KEY_COLUMNS` とsummary正規化へ `profit_barrier_threshold` を追加し、閾値違いの候補が混ざらないようにした。
- 既存 `docs/reports/*.md` の冒頭メタデータを時刻付きへ整えた。通し番号や並びは本文の `日時` を基準にし、ファイル更新時刻や `更新日時` は採番に使わない。
- report: `docs/reports/00021_2026-06-28_profit_barrier_probability_gate.md`

Artifacts:

- model: `experiments/20260628_000509_full_fixed_horizon_blind_2025_03_barrier_prob_p1_l1p2/`
- no-cost validation sweeps: `data/reports/backtests/20260628_000602_model_sweep_2024-07/`, `...2024-09/`, `...2024-11/`, `...2025-01/`
- cost-aware validation sweeps: `data/reports/backtests/20260628_000643_model_sweep_2024-07/`, `...2024-09/`, `...2024-11/`, `...2025-01/`
- candidate selection: `data/reports/backtests/20260628_000706_model_candidate_selection/`
- blind test: `data/reports/backtests/20260628_000729_model_fixed_horizon_ev_2025-03/`
- cost sensitivity: `data/reports/backtests/20260628_000839_model_cost_sensitivity_2025-03/`
- failure analysis: `data/reports/backtests/20260628_000901_barrier_prob_gate_2025-03/`

結果:

- validation選択候補は `fixed_horizon_ev`, entry `0`, short offset `8`, side margin `1`, profit barrier threshold `0.40`。
- validation base min pnl `22.4864`, base mean pnl `49.7168`, cost min pnl `17.4064`, cost mean pnl `43.1869`, min trades `24`。
- 2025-03 blindは adjusted pnl `-29.5462`, raw pnl `-14.4330`, 29 trades, profit factor `0.6742`, max DD `54.1392`。
- long pnl `+18.0844`、short pnl `-47.6306`。
- 前回blind `-49.7004` より損失は縮小したが、NoTrade `0.0` には届かない。
- cost sensitivityは全条件でマイナス。spread `0.2` / slippage `0.10` / delay `1` は adjusted pnl `-55.7310`。
- 最大損失は引き続き 2025-03-31 01:28 UTC の `asia / range / low_vol` shortで、adjusted pnl `-49.3248`。
- このtradeの predicted short barrier probabilityは `0.4859`。閾値 `0.50` なら落ちるが、validationでは月10tradesを満たしにくく、blind後の診断でも `6` trades / adjusted pnl `-39.5282` と悪化した。

判断:

- profit barrier probability gateは有効なfilter軸だが、単独では採用不可。
- 最大損失は barrier確率だけでなく、fixed horizon 720m short EVの過大評価とexit timingの遅さが重なっている。
- 次は `asia / range / low_vol` のshortだけを抑制する side-specific regime suppression、exit timing target、candidate selectionへのprofit barrier miss率追加を優先する。

### 2026-06-28 09:26 JST Side-Specific Regime Suppression

作業:

- `model-policy` / `model-sweep` に `--side-block-rules` と `--side-extra-margin-rules` を追加した。
- rule形式は `short:session_regime=asia`、`short:trend_regime=range+volatility_regime=low_vol+session_regime=asia`、`short:session_regime=asia:5`。
- `model-candidate-selection` の集計keyへ `side_extra_margin_rules` / `side_block_rules` を追加した。
- 既存レポート `docs/reports/00021_2026-06-28_profit_barrier_probability_gate.md` は更新時刻 `2026-06-28 09:26 JST` で追記した。
- report: `docs/reports/00022_2026-06-28_side_specific_regime_suppression.md`

Artifacts:

- narrow candidate selection: `data/reports/backtests/20260628_001732_model_candidate_selection/`
- medium candidate selection: `data/reports/backtests/20260628_002001_model_candidate_selection/`
- asia short candidate selection: `data/reports/backtests/20260628_002217_model_candidate_selection/`
- validation-selected blind: `data/reports/backtests/20260628_002235_model_fixed_horizon_ev_2025-03/`
- reference blind: `data/reports/backtests/20260628_002236_model_fixed_horizon_ev_2025-03/`
- cost sensitivity: `data/reports/backtests/20260628_002255_model_cost_sensitivity_2025-03/`
- failure analysis: `data/reports/backtests/20260628_002507_side_specific_asia_short_block_2025-03/`

結果:

- `short:trend_regime=range+volatility_regime=low_vol+session_regime=asia` は、2025-03 blindを `-27.4534` までしか改善しなかった。`trend_regime` が変わった直後の再entryを許した。
- `short:volatility_regime=low_vol+session_regime=asia` は、2025-03 blind `-26.8930`。`asia / normal_vol` shortへの再entryを許した。
- `short:session_regime=asia` はvalidation-selected `entry=0`, `short offset=6`, `side_margin=1`, `barrier threshold=0.40` で、2025-03 blind adjusted pnl `+18.0748`, raw pnl `+29.2330`, 35 trades, profit factor `1.2700`, max DD `44.6526`。
- 同candidateのshort pnlは `-0.0096` で、2025-03の最大short損失はほぼ消えた。
- ただし spread `0.2` / slippage `0.10` / delay `1` では adjusted pnl `-6.1046` まで落ちる。
- `short offset=8` referenceは2025-03 blind `+27.1356`、最悪コスト条件でも `+5.4936` だが、validation選択では2番手なので採用しない。

判断:

- `short:session_regime=asia` は、今回のlineで初めて2025-03 blindのNoTradeを上回った。
- ただし2025-03の最大損失を見た後に作ったruleなので、2025-03でのプラスは最終採用根拠にしない。
- 次は2025-04以降のblindで事前登録候補として検証する。
- failure analysisでは direction error rate `0.4286`、predicted side error rate `0.4571`、exit regret sum `702.5012` が残る。改善は方向予測ではなく、危険時間帯のshortをno-trade化した効果が中心。
- 次の本流は、side/regime別損失集中をcandidate selectionに入れることと、exit timing target改善。

### 2026-06-28 09:39 JST 2025-04/05 Blind Check For Asia Short Block

作業:

- 2025-04 / 2025-05 の p1/l1.2 fixed horizon datasetを生成した。
- 同じtrain/validation条件で、testだけ2025-04 / 2025-05にしたHGB 80iter full modelを学習した。
- 2025-03後に事前登録した `short:session_regime=asia` 候補を固定適用した。
- 既存レポート `docs/reports/00022_2026-06-28_side_specific_regime_suppression.md` は更新時刻 `2026-06-28 09:39 JST` で追記した。

Artifacts:

- dataset 2025-04: `data/processed/datasets/xauusd_m1_p1_l1p2/xauusd_m1_2025-04_h24_edge15.parquet`
- dataset 2025-05: `data/processed/datasets/xauusd_m1_p1_l1p2/xauusd_m1_2025-05_h24_edge15.parquet`
- model 2025-04: `experiments/20260628_003331_full_fixed_horizon_blind_2025_04_barrier_prob_p1_l1p2/`
- model 2025-05: `experiments/20260628_003756_full_fixed_horizon_blind_2025_05_barrier_prob_p1_l1p2/`
- 2025-04 selected: `data/reports/backtests/20260628_003401_model_fixed_horizon_ev_2025-04/`
- 2025-04 cost sensitivity: `data/reports/backtests/20260628_003424_model_cost_sensitivity_2025-04/`
- 2025-04 failure analysis: `data/reports/backtests/20260628_003423_side_specific_asia_short_block_2025-04/`
- 2025-05 selected: `data/reports/backtests/20260628_003824_model_fixed_horizon_ev_2025-05/`
- 2025-05 cost sensitivity: `data/reports/backtests/20260628_003846_model_cost_sensitivity_2025-05/`
- 2025-05 failure analysis: `data/reports/backtests/20260628_003846_side_specific_asia_short_block_2025-05/`

結果:

- 固定候補は `fixed_horizon_ev`, entry `0`, short offset `6`, side margin `1`, max wait regret `4`, min entry rank `0.5`, barrier threshold `0.40`, `short:session_regime=asia`。
- 2025-04 selectedは adjusted pnl `+56.3148`, raw pnl `+81.4040`, 31 trades, profit factor `1.3741`, max DD `56.7380`。
- 2025-04 blockなし同条件は adjusted pnl `-24.5976`、short pnl `-79.7916`。blockなしでは `asia` shortが 14 trades / `-106.2104`。
- 2025-04 cost worst spread `0.2` / slippage `0.10` / delay `1` は adjusted pnl `+51.5630`。
- 2025-05 selectedは adjusted pnl `+83.0630`, raw pnl `+109.8070`, 28 trades, profit factor `1.5176`, max DD `53.2900`。
- 2025-05 blockなし同条件は adjusted pnl `-57.6474`、short pnl `-77.4874`。blockなしでは `asia` shortが 15 trades / `-100.5254`。
- 2025-05 cost worst spread `0.2` / slippage `0.10` / delay `1` は adjusted pnl `+68.2500`。
- offset8 referenceは2025-04 `+10.4808`、2025-05 `+7.1750` で、validation-selected offset6より明確に弱い。

判断:

- `short:session_regime=asia` は2025-04/05でも機能し、2025-03専用の後付けruleではない可能性が高まった。
- 暫定採用候補へ昇格する。
- ただし2025-04 failure analysisでは direction error rate `0.5161`、predicted side error rate `0.5484`、exit regret sum `1183.4512`。方向予測そのものは依然弱い。
- 次はcandidate selectionへside/session別損失集中を追加し、このruleを手作業ではなくvalidation内で検出できるようにする。

### 2026-06-28 09:51 JST Direction Session Candidate Gate

作業:

- `model-sweep` metricsへ `direction_session_adjusted_pnl_min`, `worst_direction_session`, `worst_direction_session_trade_count` を追加した。
- `model-candidate-selection` に `--max-direction-session-loss-per-fold` を追加した。
- 古いsweep CSVは新列なしでも読めるよう、normalize時は `direction_session_adjusted_pnl_min=inf` として扱う。
- report: `docs/reports/00023_2026-06-28_direction_session_candidate_gate.md`

Artifacts:

- no-cost no block: `data/reports/backtests/20260628_005016_model_sweep_2025-05/`
- no-cost asia short block: `data/reports/backtests/20260628_005016_model_sweep_2025-05_1/`
- cost no block: `data/reports/backtests/20260628_005015_model_sweep_2025-05_1/`
- cost asia short block: `data/reports/backtests/20260628_005015_model_sweep_2025-05/`
- candidate selection: `data/reports/backtests/20260628_005032_model_candidate_selection/`

結果:

- 2025-05 no blockは `direction_session_adjusted_pnl_min=-100.5254`, `worst_direction_session=short:asia`, costでは `-103.8054`。
- 2025-05 asia short blockは `direction_session_adjusted_pnl_min=+19.8400`, costでは `+17.4840`。
- `--max-direction-session-loss-per-fold 45` により、no blockは `direction_session_loss_ok=False`, `eligible=False`、blockありは `eligible=True`。

検証:

- `python3 -m py_compile src/trade_data/backtest.py`: OK。
- `python3 -m unittest tests.test_backtest`: 26 tests OK。
- `python3 -m unittest discover tests`: 62 tests OK。
- `model-candidate-selection --help`, `model-sweep --help`: OK。
- `git diff --check`: OK。

判断:

- side/session別損失集中を候補選択へ組み込めるようになった。
- 次は predicted/actual profit barrier miss率もcandidate selectionへ追加する。

### 2026-06-28 09:54 JST Report Timestamp Normalization

作業:

- 既存 `docs/reports/*.md` の旧形式レポートに、冒頭の `日時` / `更新日時` を追加した。
- 旧Summary内の `- Datetime` / `- Updated` は、重複しないよう冒頭メタデータへ移した。
- `docs/README.md`, `docs/experiment_protocol.md`, `docs/templates/experiment_report.md` を、冒頭に `日時` と `更新日時` を置く運用へ更新した。

判断:

- レポート作成時刻と更新時刻は、以後 `YYYY-MM-DD HH:MM JST` で明示する。
- 既存レポートの補正では、既存の `Datetime` / `Updated` 記録を優先し、不足分だけ確認可能な時刻情報で補った。通し番号や並びは本文の `日時` を基準にし、ファイル更新時刻や `更新日時` は採番に使わない。

### 2026-06-28 10:06 JST Profit Barrier Miss Candidate Gate

作業:

- `model-policy` / `model-sweep` metricsへ predicted/actual profit barrier miss率を追加した。
- `model-candidate-selection` に `--max-predicted-profit-barrier-miss-rate` と `--max-actual-profit-barrier-miss-rate` を追加した。
- `require_profit_barrier=false` でも、prediction parquetにbarrier列が存在すれば predicted miss を測れるよう、barrier列を任意読み込みにした。
- report: `docs/reports/00024_2026-06-28_profit_barrier_miss_candidate_gate.md`

Artifacts:

- model-policy block: `data/reports/backtests/20260628_010449_model_fixed_horizon_ev_2025-05/`
- model-policy no block: `data/reports/backtests/20260628_010449_model_fixed_horizon_ev_2025-05_1/`
- no-cost no block sweep: `data/reports/backtests/20260628_010537_model_sweep_2025-05_1/`
- no-cost asia short block sweep: `data/reports/backtests/20260628_010537_model_sweep_2025-05_3/`
- cost no block sweep: `data/reports/backtests/20260628_010537_model_sweep_2025-05_2/`
- cost asia short block sweep: `data/reports/backtests/20260628_010537_model_sweep_2025-05/`
- candidate selection: `data/reports/backtests/20260628_010550_model_candidate_selection/`

結果:

- 2025-05 no blockは `actual_profit_barrier_miss_rate=0.5000`, `actual_profit_barrier_miss_count=17`, `actual_profit_barrier_miss_adjusted_pnl=-221.5828`。
- 2025-05 asia short blockは `actual_profit_barrier_miss_rate=0.464286`, `actual_profit_barrier_miss_count=13`, `actual_profit_barrier_miss_adjusted_pnl=-126.3004`。
- `--max-actual-profit-barrier-miss-rate 0.48` により、direction/session gateを緩めても no blockは `actual_profit_barrier_miss_ok=False`, blockありは `eligible=True`。
- `predicted_profit_barrier_miss_rate` は両候補とも `0.0`。barrier thresholdを通過した候補の過大評価はmiss率だけでは検出できない。

検証:

- `python3 -m py_compile src/trade_data/backtest.py`: OK。
- `python3 -m unittest tests.test_backtest`: 28 tests OK。
- `python3 -m unittest discover tests`: 64 tests OK。
- `model-candidate-selection --help`, `model-sweep --help`: OK。

判断:

- actual barrier miss率は候補選択の追加gateとして機能する。
- 閾値 `0.48` はsmoke用であり、採用するにはvalidation fold全体で台地を見る。
- 次は predicted probability bucket別のactual hit rateを標準診断に入れ、calibrationの過大評価を直接見る。

### 2026-06-28 10:19 JST Report Sequence Numbers

作業:

- `docs/reports` の既存24本を `00001_YYYY-MM-DD_slug.md` 形式へリネームした。
- 通し番号はファイルシステムの更新時刻ではなく、各レポート本文冒頭の `日時: YYYY-MM-DD HH:MM JST` の昇順で決めた。
- docs内の既存レポート参照を通し番号付きパスへ更新した。
- `GOAL.md`, `docs/README.md`, `docs/experiment_protocol.md`, `docs/templates/experiment_report.md` に命名ルールを追加した。

判断:

- 新規 `docs/reports` レポートは、既存最大番号の次を使う。
- 採番順を判断するときは、必ずレポート本文の `日時` を見る。`更新日時` やファイル更新時刻は採番基準にしない。

### 2026-06-28 10:21 JST Profit Barrier Calibration Candidate Gate

作業:

- predicted profit barrier probability bucket別のactual hit rateを `model-policy` / `model-sweep` metricsへ追加した。
- bucketは `0.0-0.2`, `0.2-0.4`, `0.4-0.6`, `0.6-0.8`, `0.8-1.0`。
- `model-candidate-selection` に `--max-profit-barrier-calibration-overestimate` を追加した。
- candidate selectionのsummaryは横に広くなりすぎないよう、bucket詳細は `model-sweep` metricsに残し、candidate selectionではsummary列だけを集計する。
- report: `docs/reports/00025_2026-06-28_profit_barrier_calibration_candidate_gate.md`

Artifacts:

- no-cost no block sweep: `data/reports/backtests/20260628_011416_model_sweep_2025-05_2/`
- no-cost asia short block sweep: `data/reports/backtests/20260628_011416_model_sweep_2025-05_1/`
- cost no block sweep: `data/reports/backtests/20260628_011416_model_sweep_2025-05_3/`
- cost asia short block sweep: `data/reports/backtests/20260628_011416_model_sweep_2025-05/`
- candidate selection: `data/reports/backtests/20260628_011509_model_candidate_selection/`

結果:

- 2025-05 no blockは calibration overestimate max `0.054305`。worst bucketは `0.6-0.8`, count `5`, predicted mean `0.654305`, actual hit rate `0.600000`。
- 2025-05 asia short blockは calibration overestimate max `0.248089`。worst bucketは `0.6-0.8`, count `7`, predicted mean `0.676661`, actual hit rate `0.428571`。
- `--max-profit-barrier-calibration-overestimate 0.2` では、no blockは `profit_barrier_calibration_ok=True`、blockありは `False`。

検証:

- `python3 -m py_compile src/trade_data/backtest.py`: OK。
- `python3 -m unittest tests.test_backtest`: 30 tests OK。
- `python3 -m unittest discover tests`: 66 tests OK。
- `model-candidate-selection --help`, `model-sweep --help`: OK。

判断:

- calibration overestimateは、barrier threshold通過後の過大評価を検出する診断軸として有効。
- ただし今回のsmokeでは、PnLが良いblockあり候補のほうがcalibration overestimateは悪い。
- したがって `--max-profit-barrier-calibration-overestimate 0.2` は採用閾値にしない。validation fold全体で台地を見るまでhard gateではなく診断値として扱う。

### 2026-06-28 10:37 JST 2025-06 Blind Holdout Failure

作業:

- 2025-06 の p1/l1.2 fixed horizon datasetを追加生成した。
- 同じtrain/validation設定で、2025-06 blind modelを学習した。
- report: `docs/reports/00026_2026-06-28_blind_2025_06_asia_short_block_failure.md`

Artifacts:

- dataset: `data/processed/datasets/xauusd_m1_p1_l1p2/xauusd_m1_2025-06_h24_edge15.parquet`
- model: `experiments/20260628_013141_full_fixed_horizon_blind_2025_06_barrier_prob_p1_l1p2/`
- selected asia short block: `data/reports/backtests/20260628_013232_model_fixed_horizon_ev_2025-06_1/`
- no block: `data/reports/backtests/20260628_013232_model_fixed_horizon_ev_2025-06/`
- offset8 reference: `data/reports/backtests/20260628_013232_model_fixed_horizon_ev_2025-06_2/`
- cost sensitivity: `data/reports/backtests/20260628_013232_model_cost_sensitivity_2025-06/`
- failure analysis: `data/reports/backtests/20260628_013257_side_specific_asia_short_block_2025-06/`
- validation back-check candidate selection: `data/reports/backtests/20260628_013608_model_candidate_selection/`

結果:

- 2025-06 dataset rows: `28,889`
- label counts: short `14,763`, flat `953`, long `13,173`
- selected `short:session_regime=asia` block: adjusted pnl `-100.4662`, raw pnl `-74.9250`, 15 trades, profit factor `0.3444`, max DD `133.5832`
- no block: adjusted pnl `-109.9862`, 18 trades
- offset8 reference: adjusted pnl `-80.9672`, 11 trades
- selectedの short pnlは `-101.0232`
- worst direction/sessionは `short:london`, adjusted pnl `-101.2102`
- actual profit barrier miss rateは `0.4667`
- calibration overestimate maxは `0.4667`
- direction error rateは `0.6000`
- profit barrier missは 7 trades / adjusted pnl `-152.0642`

Post-hoc diagnostics:

- `short:london` block only: adjusted pnl `-36.2062`, 12 trades
- `short:asia,london` block: adjusted pnl `+0.7440`, 2 trades
- all short sessions blocked in this candidate: adjusted pnl `+0.5570`, 1 trade

Validation back-check:

- no block、`short:asia`、`short:london`、`short:asia,london` を4 validation monthsへ戻して確認した。
- どの条件もeligibleではなかった。
- `short:london` はvalidation base mean pnl `+3.9695` だが min pnl `-19.9560`、min trades `2` で採用根拠にならない。
- `short:asia,london` はvalidation mean pnl `-6.3636` で、London blockを事前選択する根拠はない。

判断:

- `short:session_regime=asia` は暫定採用候補から降格する。
- 2025-04 / 2025-05の改善は、asia shortの局所損失を避けた効果であって、方向予測そのものの改善ではなかった。
- 2025-06では同じshort過大評価が London shortへ移動した。
- session hard blockを増やすとNoTradeへ近づくだけなので、本流にはしない。
- 次は short exposure concentration、support-aware actual miss / calibration、exit timing targetを優先する。

### 2026-06-28 10:47 JST Short Exposure And Support-Aware Gates

作業:

- `model-policy` / `model-sweep` metricsへ side exposure concentration列を追加した。
- `long_trade_share`, `short_trade_share`, `max_side_trade_share` を保存する。
- profit barrier miss rateへ Laplace-smoothed rateを追加した。
- profit barrier calibrationへ smoothed actual hit rate / overestimateを追加した。
- `model-candidate-selection` に以下を追加した。
  - `--max-short-trade-share`
  - `--max-side-trade-share`
  - `--max-smoothed-actual-profit-barrier-miss-rate`
  - `--max-smoothed-profit-barrier-calibration-overestimate`
- report: `docs/reports/00027_2026-06-28_short_exposure_support_aware_gates.md`

Artifacts:

- no-cost selected: `data/reports/backtests/20260628_014713_model_sweep_2025-06_1/`
- no-cost no-short diagnostic: `data/reports/backtests/20260628_014713_model_sweep_2025-06/`
- cost selected: `data/reports/backtests/20260628_014713_model_sweep_2025-06_2/`
- cost no-short diagnostic: `data/reports/backtests/20260628_014713_model_sweep_2025-06_3/`
- candidate selection: `data/reports/backtests/20260628_014727_model_candidate_selection/`

結果:

- 2025-06 selected `short:session_regime=asia`:
  - no-cost adjusted pnl `-100.4662`
  - cost adjusted pnl `-103.7488`
  - trades `15`
  - `short_trade_share=0.933333`
  - `max_side_trade_share=0.933333`
  - `actual_profit_barrier_miss_rate_smoothed=0.470588`
  - `profit_barrier_calibration_overestimate_smoothed_max=0.470588`
  - `short_trade_share_ok=false`
  - `eligible=false`
- all short sessions blocked diagnostic:
  - no-cost adjusted pnl `0.5570`
  - cost adjusted pnl `0.3570`
  - trades `1`
  - `max_side_trade_share=1.000000`
  - smoothed actual miss / calibration `0.333333`
  - `eligible_base=false`, `eligible_cost=false`

検証:

- `python3 -m py_compile src/trade_data/backtest.py`: OK。
- `python3 -m unittest tests.test_backtest`: 33 tests OK。
- `model-candidate-selection --help`: OK。
- `git diff --check`: OK。

判断:

- `--max-short-trade-share` は 2025-06の失敗候補を直接落とせる。
- `--max-side-trade-share` は少数tradeのNoTrade類似候補も検出するが、主に診断として使う。
- smoothed actual miss / calibrationは raw 0/1の過反応を弱める。1 trade候補を raw 0.0 として楽観せず `0.333333` に補正できた。
- 次は validation 4fold以上で short share閾値と smoothed gateの台地を見る。

### 2026-06-28 10:52 JST Report Numbering Rule Clarification

作業:

- `docs/reports` の通し番号は、ファイルシステムの更新時刻や本文の `更新日時` ではなく、本文冒頭の `日時: YYYY-MM-DD HH:MM JST` だけを基準にする運用を再確認した。
- `GOAL.md`, `docs/README.md`, `docs/experiment_protocol.md`, `docs/status.md` に `更新日時` を採番基準にしないことを明記した。

判断:

- `更新日時` は追記・修正履歴の管理に使う。
- 通し番号の並び替えや新規番号判断には `日時` のみを使う。

### 2026-06-28 11:14 JST High Turnover Gate Validation

作業:

- validation 4foldで short share / smoothed miss / smoothed calibration gateを比較した。
- 前回候補周辺gridを追加列込みで再生成した。
- 月10trades条件を満たせなかったため、high-turnover gridを追加した。
- high-turnover gridでは `min_entry_rank=0/0.5`, `max_wait_regret=4/inf`, `profit_barrier_threshold=0.0/0.2` を含めた。
- 2025-06は既知の失敗月として、暫定候補A/Bの回帰チェックだけを実施した。
- report: `docs/reports/00028_2026-06-28_high_turnover_gate_validation.md`

Artifacts:

- fixed-neighborhood comparison: `data/reports/backtests/20260628_020416_model_sweep_candidate_gate_comparison.csv`
- high-turnover comparison: `data/reports/backtests/20260628_021001_high_turnover_candidate_gate_comparison.csv`
- forced/direction gate comparison: `data/reports/backtests/20260628_021102_high_turnover_forced_direction_gate_comparison.csv`
- selected validation comparison: `data/reports/backtests/20260628_021208_model_candidate_selection/`
- 2025-06 known-month regression: `data/reports/backtests/20260628_021217_known_2025_06_regression_candidates.csv`
- decision: `docs/decisions/0007_high_turnover_gate_selection.md`

結果:

- 前回候補周辺gridは `min-trades-per-fold=10` を満たせず、最大でも `trade_count_min_base=5`。
- high-turnover gridでは、PnL条件を緩めると48候補が残った。
- `max-forced-exit-rate=0` では全滅。`0.05` なら候補が残る。
- `max-direction-session-loss-per-fold=45` では全滅。`60` なら5候補が残る。
- `max-short-trade-share=0.65` でも上位候補は残る。
- smoothed actual missは `0.55` なら5候補、`0.50` なら1候補。
- smoothed calibrationを `0.60` まで締めると、asia block候補だけが残る。

2025-06既知月回帰:

- A no block candidate: cost adjusted pnl `+37.0572`, 52 trades, short pnl `-14.2222`, max drawdown `77.7572`。
- B asia block calibration candidate: cost adjusted pnl `-29.4530`, 50 trades, short pnl `-84.9312`, max drawdown `123.6128`。

判断:

- 暫定hard gateは `max-short-trade-share=0.65` と `max-smoothed-actual-profit-barrier-miss-rate=0.55`。
- smoothed calibrationはhard gateにしない。診断またはtie-breakに留める。
- 暫定候補Aを、次の未見月 2025-07 で見る前に `docs/decisions/` へ固定する。
- 固定記録は `docs/decisions/0007_high_turnover_gate_selection.md` に作成済み。

### 2026-06-28 12:27 JST Blind 2025-07 Candidate A Evaluation

作業:

- 2025-07の1.0/1.20 datasetを追加生成した。
- 2025-07をtest monthにしたblind modelを、候補A固定時と同じtrain/validation設定で学習した。
- `docs/decisions/0007_high_turnover_gate_selection.md` で固定した候補Aを、no-costとstandard cost-aware caseで評価した。
- `analyze-trades` と `model-cost-sensitivity` で失敗要因を分解した。
- report: `docs/reports/00029_2026-06-28_blind_2025_07_candidate_a.md`

Artifacts:

- dataset summary: `data/processed/datasets/xauusd_m1_p1_l1p2/xauusd_m1_2025-07_h24_edge15.summary.json`
- model: `experiments/20260628_032236_full_fixed_horizon_blind_2025_07_barrier_prob_p1_l1p2/`
- comparison: `data/reports/backtests/20260628_032236_candidate_a_2025_07_blind_comparison.csv`
- no-cost backtest: `data/reports/backtests/20260628_032312_model_fixed_horizon_ev_2025-07/`
- cost-aware backtest: `data/reports/backtests/20260628_032314_model_fixed_horizon_ev_2025-07/`
- cost analysis: `data/reports/backtests/20260628_032410_candidate_a_2025_07_cost_analysis/`
- cost sensitivity: `data/reports/backtests/20260628_032641_model_cost_sensitivity_2025-07/`

結果:

- no-cost adjusted pnl `+1.5838`, raw pnl `+22.8040`, 66 trades, profit factor `1.0124`。
- standard cost-aware adjusted pnl `-12.7764`, raw pnl `+9.6040`, 66 trades, profit factor `0.9049`。
- short trade shareは `0.0758` で、short concentrationは回避した。
- cost-awareの損失中心は long `-11.7354`, `ny_overlap` `-20.0054`, `low_vol` `-30.8756`, `down_low_vol` `-27.1054`。
- direction error rate `0.5303`、actual profit barrier miss rate `0.6515`、EV overestimate vs realized mean `15.6821`。
- spread/slippage感度では、no-cost `+1.5838` から slippage `0.05` だけで `-5.5862`、slippage `0.10` で `-12.7764`。

判断:

- 候補Aは2025-07 blindで失敗。採用候補から外す。
- 2025-06のshort集中崩れは回避できたが、edgeがlong/low-vol側で消えた。
- 次はcost-aware評価を主目的へ寄せ、profit barrier classifierとexit timing targetを作り直す。
- `ny_overlap` や `low_vol` のpost-hoc blockは直接採用しない。validation foldで支持されるかを確認する。
- レポート通し番号は、今後もファイル更新時刻や `更新日時` ではなく、本文冒頭の `日時` を基準にする。

### 2026-06-28 12:37 JST Trade Analysis Diagnostic Gates

作業:

- `model-sweep` metricsへ trade-analysis diagnostic列を追加した。
- 追加列は `direction_error_rate`, `no_edge_rate`, `predicted_side_error_rate`, `exit_regret_mean`, `ev_overestimate_vs_realized_mean` など。
- `model-candidate-selection` に以下のgateを追加した。
  - `--max-direction-error-rate`
  - `--max-predicted-side-error-rate`
  - `--max-no-edge-rate`
  - `--max-exit-regret-mean`
  - `--max-ev-overestimate-vs-realized-mean`
- report: `docs/reports/00030_2026-06-28_trade_analysis_diagnostic_gates.md`

Artifacts:

- no-cost one-point sweep: `data/reports/backtests/20260628_033639_model_sweep_2025-07/`
- cost-aware one-point sweep: `data/reports/backtests/20260628_033650_model_sweep_2025-07/`
- candidate-selection smoke: `data/reports/backtests/20260628_033702_model_candidate_selection/`

結果:

- 2025-07候補Aのpost-hoc smokeで、新diagnosticが `analyze-trades` と一致することを確認した。
- no-cost: direction error rate `0.5303`, exit regret mean `17.2330`, EV overestimate vs realized mean `15.4645`。
- cost-aware: direction error rate `0.5303`, exit regret mean `17.4505`, EV overestimate vs realized mean `15.6821`。
- `max-direction-error-rate=0.5`, `max-exit-regret-mean=15`, `max-ev-overestimate-vs-realized-mean=10` で候補Aは `eligible=false`。

検証:

- `python3 -m unittest tests.test_backtest`: 34 tests OK。
- `python3 -m unittest discover tests`: 70 tests OK。
- `python3 -m trade_data.backtest model-candidate-selection --help`: OK。
- `git diff --check`: OK。

判断:

- 2025-07の失敗要因を、post-hoc分析だけでなくvalidation候補選定へ戻せるようになった。
- ただし、この閾値は2025-07を見た後のsmoke値なので採用基準ではない。次はvalidation 4foldで閾値台地を確認する。
- `ny_overlap` / `low_vol` の直接blockではなく、direction error、exit regret、EV overestimateのような構造的な失敗指標を使う。

### 2026-06-28 12:48 JST Diagnostic Gate Validation

validation 4foldのhigh-turnover gridを、新しいtrade-analysis diagnostic列入りで再生成した。

確認したdiagnostic gate:

- direction error rate
- predicted side error rate
- no-edge rate
- exit regret mean
- EV overestimate vs realized mean

結果:

- no diagnostic / lenient / balanced gate: eligible `5`
- focused gate: eligible `2`
- strict gate: eligible `1`
- 2025-07 smoke-like gate (`exit_regret_mean<=15`, `EV overestimate<=10`): eligible `0`

判断:

- 2025-07の失敗をpost-hocで落とせた厳しいgateは、validationでは候補を全滅させるため採用しない。
- 現時点ではdiagnosticを主hard gateにせず、tie-breakと失敗分析に使う。
- 既存 `docs/reports/*.md` 30本について、ファイル更新時刻ではなく本文内 `日時` 順で採番が一致することを確認した。

成果物:

- `docs/reports/00031_2026-06-28_diagnostic_gate_validation.md`
- `docs/decisions/0008_trade_analysis_diagnostic_gate_policy.md`
- `data/reports/backtests/20260628_034513_model_candidate_selection/`
- `data/reports/backtests/20260628_124813_diagnostic_gate_threshold_comparison.csv`

次は exit timing target、risk target、expected pnl calibration を改善する。

### 2026-06-28 12:58 JST Time-Limited Profit Barrier Targets

作業:

- `long_profit_barrier_hit_60m/240m/720m` と `short_profit_barrier_hit_60m/240m/720m` をdataset targetに追加した。
- `target-set policy` / `full` のclassification targetへ追加した。
- 既存の `--long-profit-barrier-column` / `--short-profit-barrier-column` に `pred_long_profit_barrier_hit_240m_prob` のような列を差し替えられるようにした。
- report: `docs/reports/00032_2026-06-28_time_limited_profit_barrier_targets.md`

Smoke:

- `/tmp` に 2025-01 から 2025-03 のdatasetを生成。
- 2025-01では、60m targetはlong `0.0023` / short `0.0063` と希少。
- 240m targetはlong `0.0665` / short `0.0420`、720m targetはlong `0.3255` / short `0.1196`。
- 軽量HGB smoke `experiments/20260628_035801_exit_target_smoke/` で新targetの学習と確率列保存を確認。

判断:

- 60m targetはhard gateには早い。class weightingやpositive supportを検討するまでは診断扱い。
- 240m/720m targetは、24h targetより短いexit依存を落とすfilterとしてvalidationで比較する価値がある。
- 主datasetはまだ再生成していない。次は本番dataset再生成、policy再学習、cost-aware validation sweep。

検証:

- `python3 -m unittest tests.test_dataset tests.test_modeling`: 25 tests OK。
- `python3 -m unittest discover tests`: 71 tests OK。
- `git diff --check`: OK。

### 2026-06-28 13:53 JST Timebarrier Validation Sweep

作業:

- 主dataset `data/processed/datasets/xauusd_m1_p1_l1p2/` を、時間別profit barrier target込みで 2023-01 から 2025-07 まで再生成した。
- `target-set policy` に固定horizon回帰targetが不足していたため、`EXIT_FIXED_HORIZON_TARGETS` を追加した。
- policy HGBを再学習し、`fixed_horizon_ev` と 24h/240m/720m profit barrier probabilityを同時に使える prediction frameを作成した。
- 24h, 240m, 720m probabilityのvalidation 4fold sweepを比較した。
- 240m / 720m はfine thresholdも追加で検証した。
- report: `docs/reports/00033_2026-06-28_timebarrier_validation_sweep.md`

Artifacts:

- model: `experiments/20260628_040828_policy_timebarrier_p1_l1p2/`
- broad summary: `data/reports/backtests/20260628_timebarrier_candidate_selection_summary.csv`
- fine summary: `data/reports/backtests/20260628_timebarrier_fine_candidate_selection_summary.csv`
- 240m fine candidate selection: `data/reports/backtests/20260628_045220_barrier240_fine_candidate_selection/`
- 720m fine candidate selection: `data/reports/backtests/20260628_045221_barrier720_fine_candidate_selection/`

結果:

| variant | eligible | top threshold | cost min pnl | min trades | forced exit max | worst dir/session | smoothed miss max |
|---|---:|---:|---:|---:|---:|---:|---:|
| 24h broad | 12 | `0.2` | `27.2158` | 47 | `0.0000` | `-39.1342` | `0.454545` |
| 240m broad | 5 | `0.0` | `20.6606` | 56 | `0.035714` | `-51.5902` | `0.500000` |
| 720m broad | 5 | `0.0` | `20.6606` | 56 | `0.035714` | `-51.5902` | `0.500000` |
| 240m fine | 8 | `0.0` | `20.6606` | 56 | `0.035714` | `-51.5902` | `0.500000` |
| 720m fine | 8 | `0.0` | `20.6606` | 56 | `0.035714` | `-51.5902` | `0.500000` |

classifier診断:

- time-limited barrier classifierのvalidation balanced accuracyはほぼ `0.5`。
- 60m targetは希少で、現HGBではhard gateに向かない。
- 240m / 720m probabilityは候補を絞れるが、現在のtop候補ではthreshold `0.0` が勝っており、filterとして強く機能していない。

判断:

- 240m / 720m probabilityはhard gateへ昇格しない。
- 24h profit barrier probability threshold `0.2` は、現validation上ではまだ上位候補。
- 次はtime-limited binary probabilityよりも、exit regret / EV overestimateを直接下げるtarget、またはhazard / survival形式のexit timing targetを優先する。
- レポート採番は、引き続きファイル更新時刻や `更新日時` ではなく、ファイル本文の `日時` を基準にする。

### 2026-06-28 14:10 JST Fixed Horizon Score Mode Validation

作業:

- `fixed_horizon_ev` に `fixed_horizon_score_mode` を追加した。
- `model-policy --fixed-horizon-score-mode` と `model-sweep --fixed-horizon-score-modes` を追加した。
- modeは `max`, `mean`, `median`, `min`。
- `SWEEP_KEY_COLUMNS` に `fixed_horizon_score_mode` を追加し、古いsweep metricsには `max` を補完する。
- validation 4foldで `max/mean/median/min` を比較した。
- report: `docs/reports/00034_2026-06-28_fixed_horizon_score_mode_validation.md`

Artifacts:

- base sweeps: `data/reports/backtests/20260628_050708_model_sweep_2024-07/`, `20260628_050721_model_sweep_2024-09/`, `20260628_050733_model_sweep_2024-11/`, `20260628_050745_model_sweep_2025-01/`
- cost sweeps: `data/reports/backtests/20260628_050757_model_sweep_2024-07/`, `20260628_050809_model_sweep_2024-09/`, `20260628_050822_model_sweep_2024-11/`, `20260628_050834_model_sweep_2025-01/`
- candidate selection: `data/reports/backtests/20260628_050919_horizon_score_mode_candidate_selection/`
- summary: `data/reports/backtests/20260628_horizon_score_mode_candidate_selection_summary.csv`

結果:

| mode | eligible | top cost min pnl | top cost min trades | short share max | EV overestimate max | exit regret max |
|---|---:|---:|---:|---:|---:|---:|
| `max` | 7 | `27.2158` | 47 | `0.170213` | `15.692745` | `25.465302` |
| `mean` | 0 | `-57.7550` | 92 | `0.065217` | `16.620512` | `22.515032` |
| `median` | 0 | `-53.7286` | 77 | `0.064935` | `16.457595` | `22.309429` |
| `min` | 0 | `-46.6480` | 57 | `0.000000` | `16.510913` | `21.548846` |

判断:

- 単純な保守的horizon集約は採用しない。
- `mean/median/min` はshort exposureを強く落とすが、EV overestimateは大きく改善せず、long-only寄りでfold最低PnLを壊す。
- `fixed_horizon_score_mode=max` を維持する。
- EV過大評価対策は、horizon集約ではなくOOFで実現PnLに対するcalibration/penaltyを学習する方向へ進める。

### 2026-06-28 14:26 JST Fixed Horizon OOF Calibration

作業:

- fixed horizon EV target用の汎用group calibrationを追加した。
- `oof-fixed-horizon-calibration` CLIを追加し、validation月をleave-one-month-outで校正できるようにした。
- `docs/reports` の採番が本文 `日時` の昇順であることを確認する `tests/test_docs_reports.py` を追加した。
- regime calibration (`volatility_regime,session_regime`, shrink `0.65`) と global bias calibration (groupなし, shrink `1.0`) を比較した。
- report: `docs/reports/00035_2026-06-28_fixed_horizon_oof_calibration.md`

Artifacts:

- regime calibration: `experiments/20260628_052021_fixed_horizon_oof_group_calib_p1_l1p2/`
- regime candidate selection: `data/reports/backtests/20260628_052218_model_candidate_selection/`
- global bias calibration: `experiments/20260628_052305_fixed_horizon_oof_global_bias_p1_l1p2/`
- global strict selection: `data/reports/backtests/20260628_052436_model_candidate_selection/`
- global relaxed diagnostic selection: `data/reports/backtests/20260628_052503_model_candidate_selection/`

結果:

| variant | strict eligible | top cost min pnl | min trades | forced exit max | smoothed miss max | EV overestimate max |
|---|---:|---:|---:|---:|---:|---:|
| raw fixed horizon | 7 | `27.2158` | 47 | `0.000000` | `0.454545` | `15.692745` |
| regime calibration | 0 | `9.3470` | 3 | `0.000000` | `0.666667` | `20.238968` |
| global bias calibration | 0 | `38.0184` | 76 | `0.057471` | `0.617978` | `15.713636` |

判断:

- regime別fixed horizon calibrationは採用しない。
- global bias calibrationはtarget biasを下げるが、trade selection後のEV overestimateを下げないため採用保留。
- strict gateを緩めるとglobal bias候補は3件残るが、profit-barrier missとforced exitを悪化させているため、採用ではなく診断扱い。
- 次はtrade selection後の実現PnL penalty、profit-barrier missを直接下げるexit target、hazard/survival型exit timing targetへ進む。

### 2026-06-28 14:39 JST Profit Barrier Miss Penalty Sweep

作業:

- `fixed_horizon_ev` のentry scoreに `profit_barrier_miss_penalty * (1 - side_profit_barrier_hit_probability)` を引くsoft penaltyを追加した。
- `model-policy --profit-barrier-miss-penalty` と `model-sweep --profit-barrier-miss-penalties` を追加した。
- 古いsweep metricsには `profit_barrier_miss_penalty=0.0` を補完する。
- report: `docs/reports/00036_2026-06-28_profit_barrier_miss_penalty_sweep.md`
- 採番は引き続きファイル更新時刻や `更新日時` ではなく、レポート本文の `日時` を基準にする。

Artifacts:

- no-cost sweeps: `data/reports/backtests/20260628_053518_model_sweep_2024-07/`, `...2024-09/`, `...2024-11/`, `...2025-01/`
- cost delay0 sweeps: `data/reports/backtests/20260628_053731_model_sweep_2024-07/`, `...2024-09/`, `...2024-11/`, `...2025-01/`
- candidate selection delay0: `data/reports/backtests/20260628_053757_model_candidate_selection/`
- cost delay1 sweeps: `data/reports/backtests/20260628_053602_model_sweep_2024-07/`, `...2024-09/`, `...2024-11/`, `...2025-01/`
- candidate selection delay1: `data/reports/backtests/20260628_053630_model_candidate_selection/`

結果:

| cost case | eligible penalty | best cost min pnl | min trades | smoothed miss max | EV overestimate max |
|---|---:|---:|---:|---:|---:|
| delay0 | `0.0` | `27.2158` | 47 | `0.454545` | `15.692745` |
| delay1 | `0.0` | `23.4720` | 48 | `0.492308` | `14.766051` |

判断:

- penalty `2/4/6/8` は、delay0 / delay1 のどちらでもstrict candidate selectionに残らなかった。
- 線形miss penaltyはtrade集合の実現品質を改善せず、smoothed missやEV overestimateを悪化させた。
- 実装は探索軸として残すが、標準設定は `profit_barrier_miss_penalty=0.0` を維持する。
- 次はselected tradesの実現PnL、actual barrier miss、exit regretを直接targetにする二段階モデル、またはhazard/survival型exit timing targetへ進む。

### 2026-06-28 15:00 JST Selected Trade Quality Calibration

作業:

- policyが実際に選んだtradeだけを使う `TradeQualityCalibrator` を追加した。
- `trade_data.meta_model oof-trade-quality-calibration` を追加し、validation月leave-one-month-outで `pred_trade_quality_long/short_adjusted_pnl` を生成できるようにした。
- `model-policy --min-trade-quality` と `model-sweep --min-trade-qualities` を追加した。
- 現行基準候補のcost-aware trades 4ヶ月分を生成し、OOF quality列を作った。
- report: `docs/reports/00037_2026-06-28_selected_trade_quality_calibration.md`

Artifacts:

- selected-trade fit trades: `data/reports/backtests/20260628_055630_model_fixed_horizon_ev_2024-07/`, `...2024-09/`, `...2024-11/`, `...2025-01/`
- OOF quality predictions: `experiments/20260628_055648_trade_quality_oof_fixed_horizon/`
- no-cost quality sweeps: `data/reports/backtests/20260628_055803_model_sweep_2024-07/`, `...2024-09/`, `...2024-11/`, `...2025-01/`
- cost quality sweeps: `data/reports/backtests/20260628_055853_model_sweep_2024-07/`, `...2024-09/`, `...2024-11/`, `...2025-01/`
- candidate selection: `data/reports/backtests/20260628_055927_model_candidate_selection/`

結果:

| min trade quality | eligible | best cost min pnl | best base min pnl | min trades | best smoothed miss | best EV overestimate |
|---:|---:|---:|---:|---:|---:|---:|
| `-inf` | 7 | `27.2158` | `39.7538` | 47 | `0.454545` | `14.377795` |
| `-1.0` | 6 | `22.7466` | `34.8046` | 47 | `0.454545` | `14.377795` |
| `0.0` | 3 | `9.2116` | `20.8296` | 47 | `0.464286` | `14.549737` |
| `0.5` | 3 | `4.7194` | `15.3554` | 27 | `0.488889` | `14.763182` |
| `1.0` | 0 | `-9.1060` | `-4.2660` | 17 | `0.625000` | `16.130152` |

判断:

- OOF selected-trade calibrationはraw biasを `0.628560` から `-0.078209` へ下げたが、R2は `-0.017978` で個別trade識別力は弱い。
- `min_trade_quality` gateはtop候補を改善しない。`0` 以上ではcost min pnlが大きく悪化する。
- 実装は残すが、標準候補には採用しない。標準は `min_trade_quality=-inf`。
- 次はgroup平均ではなく小型モデルでselected-trade targetを学習するか、hazard/survival型exit timing targetへ進む。

### 2026-06-28 15:11 JST Selected Trade Quality Model

作業:

- selected tradesの実現PnLを小型HGBで学習する `TradeQualityModelConfig` / `TradeQualityModelBundle` を追加した。
- `trade_data.meta_model oof-trade-quality-model` を追加し、validation月leave-one-month-outでHGB版 `pred_trade_quality_long/short_adjusted_pnl` を生成できるようにした。
- report: `docs/reports/00038_2026-06-28_selected_trade_quality_model.md`
- 採番は引き続きファイル更新時刻や `更新日時` ではなく、レポート本文の `日時` を基準にする。

Artifacts:

- HGB OOF quality predictions: `experiments/20260628_060718_trade_quality_model_oof_fixed_horizon/`
- no-cost quality sweeps: `data/reports/backtests/20260628_060955_model_sweep_2024-07/`, `...2024-09/`, `...2024-11/`, `...2025-01/`
- cost quality sweeps: `data/reports/backtests/20260628_061047_model_sweep_2024-07/`, `...2024-09/`, `...2024-11/`, `...2025-01/`
- candidate selection: `data/reports/backtests/20260628_061118_model_candidate_selection/`

結果:

| min trade quality | eligible | best cost min pnl | best base min pnl | min trades | best smoothed miss | best EV overestimate |
|---:|---:|---:|---:|---:|---:|---:|
| `-inf` | 7 | `27.2158` | `39.7538` | 47 | `0.454545` | `14.377795` |
| `-1.0` | 7 | `27.2158` | `39.7538` | 47 | `0.454545` | `14.377795` |
| `0.0` | 7 | `27.2158` | `39.7538` | 47 | `0.459016` | `14.411078` |
| `0.5` | 0 | `-15.5310` | `-10.3410` | 23 | `0.450000` | `17.109478` |
| `1.0` | 4 | `1.7620` | `4.1220` | 10 | `0.477612` | `18.353985` |

判断:

- HGB版selected-trade qualityはgroup補正よりMAEを少し下げたが、bias/R2は悪く、安定した個別trade識別器にはなっていない。
- `min_trade_quality=0.0` はtop候補を壊さないが、改善もしない。
- `1.0` 以上はtrade数とfold最低PnLを大きく削る。
- selected-trade quality modelは診断・探索基盤として残すが、標準候補には採用しない。標準は引き続き `min_trade_quality=-inf`。
- 次はtrade後品質の単発gateより、exit timing targetを直接増やす。特に利確/損切り/時間切れの時刻をhazard/survival型またはtime-bucket classificationで扱う。

### 2026-06-28 15:21 JST Exit Event Timing Targets

作業:

- side別に `time_exit/profit_first/loss_first` を表す `long_exit_event` / `short_exit_event` をdatasetに追加した。
- side別に最初のexit eventまでの `long_exit_event_minutes` / `short_exit_event_minutes` を追加した。
- `long_exit_event_time_bin` / `short_exit_event_time_bin` を追加した。
- `trade_data.modeling` の `policy` / `full` target setへexit event targetを追加した。
- report: `docs/reports/00039_2026-06-28_exit_event_timing_targets.md`
- 採番は引き続きファイル更新時刻や `更新日時` ではなく、レポート本文の `日時` を基準にする。

Artifacts:

- smoke datasets: `data/processed/datasets/xauusd_m1_exit_event_smoke/`
- smoke model: `experiments/20260628_062101_exit_event_target_smoke/`
- smoke backtest: `data/reports/backtests/20260628_062138_model_timed_ev_2024-09/`

結果:

| split | target | MAE | RMSE | R2 |
|---|---|---:|---:|---:|
| valid | `long_exit_event_minutes` | `537.5728` | `676.4928` | `0.1628` |
| valid | `short_exit_event_minutes` | `524.9559` | `656.6593` | `0.1565` |
| test | `long_exit_event_minutes` | `600.3732` | `854.8331` | `0.1306` |
| test | `short_exit_event_minutes` | `611.3872` | `876.4042` | `0.1450` |

接続確認:

- `pred_long_exit_event_minutes` / `pred_short_exit_event_minutes` は保存された。
- 既存 `timed_ev` policyの `--long-holding-column` / `--short-holding-column` に渡してbacktestが実行できた。
- smoke backtestは `2024-09` で adjusted pnl `-118.8852`, 47 trades。これは軽量1ヶ月trainの接続確認であり、採用判断には使わない。

判断:

- exit event timing targetは本流の次実験軸へ昇格する。
- 次はvalidation 4fold用に新target入りdatasetを再生成し、従来 `pred_*_best_holding_minutes` と `pred_*_exit_event_minutes` をholding columnとして比較する。
- 多クラス `exit_event` のprobability出力を追加し、profit/loss/time確率をgateやpenaltyに使えるようにする。

### 2026-06-28 15:50 JST Exit Event Holding Validation

作業:

- 新target入りdataset `data/processed/datasets/xauusd_m1_p1_l1p2_exit_event/` を 2023-01 から 2025-01 まで生成した。
- `policy` target setでHGB 80iterを再学習し、validation 4foldで従来holding columnとexit-event holding columnを比較した。
- 多クラスclassifierについて `pred_<target>_prob_<class>` を出力するようにし、`pred_long_exit_event_prob_1` / `pred_short_exit_event_prob_1` をprofit-first gateとして使えるようにした。
- `short_entry_threshold_offset=8,12,16,20` の拡張gridも試した。
- report: `docs/reports/00040_2026-06-28_exit_event_holding_validation.md`
- 採番は引き続きファイル更新時刻や `更新日時` ではなく、レポート本文の `日時` を基準にする。

Artifacts:

- model with exit-event class probabilities: `experiments/20260628_064332_policy_exit_event_prob_p1_l1p2/`
- best-holding comparison: `data/reports/backtests/20260628_063841_model_candidate_selection/`
- exit-event holding comparison: `data/reports/backtests/20260628_063856_model_candidate_selection/`
- exit-event profit probability gate: `data/reports/backtests/20260628_064600_model_candidate_selection/`
- short offset expansion strict: `data/reports/backtests/20260628_064844_model_candidate_selection/`
- short offset expansion forced-exit 10% diagnostic: `data/reports/backtests/20260628_065005_model_candidate_selection/`

結果:

| variant | strict eligible | best cost min pnl | main failure |
|---|---:|---:|---|
| best holding + old barrier prob | 0 | `30.2476` | smoothed barrier miss `0.551020` |
| exit-event holding + old barrier prob | 0 | `59.5464` | forced exit `0.097561` |
| exit-event holding + exit-event profit prob | 0 | `75.8344` | forced exit `0.125000` |
| exit-event holding + profit prob + short offset expansion | 0 | `75.8344` | forced exit `0.125000` |

10% forced-exit diagnostic:

| entry | short offset | min entry rank | profit-first threshold | cost min pnl | min trades | forced exit max | short share max | smoothed miss max |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `5` | `12` | `0.5` | `0.4` | `56.6182` | `29` | `0.081081` | `0.540541` | `0.538462` |
| `0` | `16` | `0.5` | `0.4` | `53.2866` | `32` | `0.055556` | `0.550000` | `0.534884` |

判断:

- exit-event minutesはbest holding minutesより学習しやすく、validation PnL台地も押し上げる。
- ただし、strict `max_forced_exit_rate=0.05` では採用不可。5% gateを緩めて採用するのは、まだtime-expiry riskの取り扱いが粗い。
- `pred_*_exit_event_prob_1` はbarrier missを抑える方向に効いたため、研究信号として残す。
- 次はholding minuteをそのまま使うのではなく、time-exit probability penalty、holding cap、hazard/survival型exit policyで強制決済率を直接下げる。

### 2026-06-28 16:05 JST Holding Cap Sweep

作業:

- `model-sweep` の `--min-predicted-hold-minutes` / `--max-predicted-hold-minutes` をCSV grid対応にした。
- `min_predicted_hold_minutes` / `max_predicted_hold_minutes` をcandidate keyへ追加し、cap違いの候補がfold集計で混ざらないようにした。
- exit-event holding + profit-first probability gateのvalidation 4foldで、`max_predicted_hold_minutes=240,480,720,960,1200,1440` を比較した。
- report: `docs/reports/00041_2026-06-28_holding_cap_sweep.md`
- 採番は引き続きファイル更新時刻や `更新日時` ではなく、レポート本文の `日時` を基準にする。

Artifacts:

- no-cost sweeps: `data/reports/backtests/20260628_065828_model_sweep_2024-07/`, `...2024-09/`, `...2024-11/`, `...2025-01/`
- cost-aware sweeps: `data/reports/backtests/20260628_065950_model_sweep_2024-07/`, `...2024-09/`, `...2024-11/`, `...2025-01/`
- strict candidate selection: `data/reports/backtests/20260628_070227_model_candidate_selection/`
- 10% forced-exit diagnostic: `data/reports/backtests/20260628_070240_model_candidate_selection/`
- delay `1` fixed top diagnostic: `data/reports/backtests/20260628_070518_model_sweep_2024-07/`, `...2024-09/`, `...2024-11/`, `...2025-01/`

結果:

| forced-exit gate | eligible | best cost min pnl | best base min pnl | min trades | forced exit max | best cap |
|---:|---:|---:|---:|---:|---:|---:|
| `0.05` | `20` | `84.7072` | `92.2774` | `32` | `0.028571` | `720` |
| `0.10` | `29` | `84.7072` | `92.2774` | `32` | `0.028571` | `720` |

Best strict candidate:

- `policy=timed_ev`
- `entry_threshold=10`
- `short_entry_threshold_offset=8`
- `profit_barrier_threshold=0.4`
- `max_predicted_hold_minutes=720`
- cost-aware fold pnl: `151.2868`, `98.1128`, `87.6574`, `84.7072`
- cost-aware min trades `32`, max drawdown `80.4432`, max forced exit rate `0.028571`

判断:

- holding capはforced-exit問題に直接効き、strict gateを緩めずに候補を復活させた。
- cap `720` は `480` よりPnLが高く、`960` 以上よりforced exitが少ないため、現時点の中心候補。
- delay `1` 固定診断では4fold全てプラスだが、smoothed miss max `0.552632` が現行gate `0.55` を少し超えた。delay `1` はfull-grid選定前に標準採用しない。
- 次は閾値を固定して未使用blind月へ適用する。test結果を見てcapやthresholdを再選択しない。

### 2026-06-28 16:31 JST Delay 1 Combined Regime Holdout

作業:

- `model-sweep` metricsへ `combined_regime` / `direction:combined_regime` の最悪損益診断を追加した。
- `model-candidate-selection` に `--max-combined-regime-loss-per-fold` と `--max-direction-combined-regime-loss-per-fold` を追加した。
- delay `1` のvalidation 4fold full-gridを、新しい診断列入りで再生成した。
- combined regime gateの閾値感度を確認し、`60/65` gateのtop候補を2024-12 holdoutへ固定適用した。
- report: `docs/reports/00042_2026-06-28_delay1_combined_regime_holdout.md`
- 採番は引き続きファイル更新時刻や `更新日時` ではなく、レポート本文の `日時` を基準にする。

Artifacts:

- no-cost sweeps: `data/reports/backtests/20260628_072504_model_sweep_2024-07/`, `...2024-09/`, `...2024-11/`, `...2025-01/`
- cost-aware sweeps: `data/reports/backtests/20260628_072645_model_sweep_2024-07/`, `...2024-09/`, `...2024-11/`, `...2025-01/`
- baseline support-aware selection: `data/reports/backtests/20260628_072821_model_candidate_selection/`
- combined gate `60/60`: `data/reports/backtests/20260628_072839_model_candidate_selection/`
- combined gate `60/65`: `data/reports/backtests/20260628_073009_model_candidate_selection/`
- 2024-12 holdout: `data/reports/backtests/20260628_073040_model_timed_ev_2024-12/`
- 2024-12 analysis: `data/reports/backtests/20260628_073055_holdout_2024_12_combined_gate_top/`

結果:

| selection | eligible | pre-plateau | top | cost min pnl |
|---|---:|---:|---|---:|
| baseline support-aware | `13` | `21` | `entry=5, short offset=12, cap=720` | `58.2310` |
| combined `60/60` | `0` | `13` | n/a | n/a |
| combined `60/65` | `3` | `16` | `entry=5, short offset=20, cap=480` | `45.4484` |

2024-12 holdout:

- adjusted pnl `-149.7354`
- raw pnl `-109.3520`
- trades `33`
- win rate `0.4545`
- profit factor `0.3820`
- max drawdown `176.6504`
- forced exits `2`

失敗診断:

- long adjusted pnl `-116.2186`
- short adjusted pnl `-33.5168`
- direction error rate `0.575758`
- exit regret mean `16.019952`
- EV overestimate vs realized mean `21.857830`
- profit barrier miss trades `25`, adjusted pnl `-184.2444`

判断:

- combined regime gateはvalidation候補を絞るが、hard gateとして採用候補を改善しなかった。
- 2024-12の主因はforced exitではなく、direction error、profit barrier miss、EV過大評価。
- combined regimeはcandidate tie-break / failure analysisには使うが、標準hard gateにはしない。
- 次はside/entry calibrationを直接扱う。特に `actual_best_side`, profit barrier miss, EV overestimateを教師信号またはcalibration targetにする。

### 2026-06-28 16:48 JST Best Side Confidence Smoke

作業:

- `label` とは別に、long/shortの相対的に良い方向を保持する `best_side` targetを追加した。
- `target-set policy` / `full` で `best_side` をclassification targetに含め、`pred_best_side_prob_1` / `pred_best_side_prob_-1` を保存するようにした。
- `model-policy` / `model-sweep` に `--side-confidence-penalty` と `--min-side-confidence` を追加した。
- 2024-09..2024-12のsmoke datasetとHGB modelを作成し、2024-12 testでside-confidence sweepを行った。
- report: `docs/reports/00043_2026-06-28_best_side_confidence_smoke.md`
- 採番はファイル更新時刻や `更新日時` ではなく、レポート本文の `日時` を基準にする。

Artifacts:

- dataset: `data/processed/datasets/xauusd_m1_best_side_smoke/`
- model: `experiments/20260628_074412_best_side_confidence_smoke/`
- sweep: `data/reports/backtests/20260628_074450_model_sweep_2024-12/`

結果:

| split | best_side balanced accuracy | macro f1 |
|---|---:|---:|
| train | `0.6710` | `0.6624` |
| validation | `0.5464` | `0.5393` |
| test | `0.4797` | `0.4766` |

2024-12 executable smoke:

| side penalty | min side confidence | adjusted pnl | trades | profit factor | max drawdown |
|---:|---:|---:|---:|---:|---:|
| `10` | `0.55` | `-109.8978` | `331` | `0.7276` | `119.9102` |
| `0` | `0.00` | `-220.5348` | `506` | `0.6484` | `241.2352` |

判断:

- side-confidence gateは損失と取引数を減らすが、NoTradeには負けるため採用しない。
- `best_side` は方向選択の診断 target としては有用。ただし2024-12ではbelow-randomなので、hard gateにするにはwalk-forward OOFの確認が必須。
- 次は広い期間のdatasetに反映し、side confidenceをcalibration/diagnosticとして使う。
