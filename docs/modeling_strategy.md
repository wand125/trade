# Modeling Strategy

## 基本方針

深層学習は最終的な候補であり、最初にやることではない。

順序:

1. バックテスト仕様を固定する。
2. No trade / random / rule-based のベースラインを作る。
3. オラクル上限を近似する。
4. 特徴量と教師ラベルを作る。
5. 古典モデルと小型 MLP で有効性を測る。
6. 系列深層学習へ進む。
7. 必要なら方策最適化に進む。

## 問題設定

候補 A: 3 クラス分類

- `enter_long`
- `enter_short`
- `stay_flat`

候補 B: 2 段階モデル

- entry model: 入るかどうか。
- direction model: long or short。
- exit model: 保持するか決済するか。

候補 C: 回帰

- 未来 24 時間以内の期待 adjusted pnl を予測する。
- long expected value と short expected value を別々に出す。

候補 D: policy model

- 状態から action を直接出す。
- backtest environment 上で報酬を評価する。

初期推奨は候補 B だが、3クラス分類だけを主ターゲットにしない。回帰、ランキング、量子化分類を併用する multi-task target を使う。

## 教師ラベル

エントリーラベル候補:

- 未来 24 時間以内で、long の最良 exit が閾値以上なら long。
- 未来 24 時間以内で、short の最良 exit が閾値以上なら short。
- どちらも弱い場合は stay_flat。
- long と short の両方が有効な場合は、adjusted pnl が大きい方を採用。

注意:

- ラベル作成には未来を使ってよいが、特徴量には未来を使わない。
- ラベル作成時の future path と、推論時の意思決定を混同しない。
- 閾値は validation で調整し、test に合わせない。

## 初期ラベル実装

実装ファイル:

- `src/trade_data/dataset.py`

初期ラベルは、バックテスト仕様に合わせて以下で作る。

- decision bar の特徴量だけを使う。
- entry は次足 open とする。
- exit candidate は entry 後から 24 時間以内、または強制決済相当の最初の bar とする。
- long/short それぞれの best adjusted pnl を計算する。
- best adjusted pnl が `min_adjusted_edge` 以上なら、その方向を label にする。
- 閾値未満なら `stay_flat` とする。

ラベル値:

- `1`: long
- `0`: stay_flat
- `-1`: short

2025-01 の例:

| edge | short | stay_flat | long |
|---:|---:|---:|---:|
| 1 | 9615 | 100 | 20482 |
| 15 | 5175 | 8390 | 16632 |

edge は validation 期間で調整し、test 月に合わせて選ばない。

## Multi-task Target 方針

3クラスラベルは補助タスクまたは後処理確認用に残す。深層学習の主ターゲットは、以下のような情報量の多い値にする。

- long の best adjusted pnl
- short の best adjusted pnl
- long/short の強制決済 adjusted pnl
- long/short の最大逆行 pnl
- long/short の best exit までの時間
- long と short の差分 `side_score`
- best adjusted pnl の分位点 bin
- side_score の分位点 bin
- best exit time の bin

量子化は、連続値を捨てるためではなく、ノイズの多い損益回帰を安定させる補助タスクとして使う。

### Dense Entry Quality Target

`long / short / stay_flat` に圧縮すると、entry timing の情報が落ちすぎる。特に、entryに向いている度合いを学ばせたい場合、正例だけを拾う分類では学習量が少なくなりやすい。

そのため、entry timing は以下の密な target に分解する。

- `profit_barrier_hit`: 利益バリアへ損失バリアより先に到達したか。
- `wait_regret`: 近い未来により良いentryがあった場合の機会損失。
- `entry_local_rank`: 近傍時間窓内でのentry quality順位。
- `entry_urgency`: 近傍中央値に対する現在entry qualityの強さ。

これらは long/short 別に作り、回帰targetと量子化分類targetの両方で学習する。量子化は情報を捨てるためではなく、ノイズの強い連続targetを安定化する補助タスクとして使う。

初期実装:

- 近傍時間窓: `--entry-timing-lookahead-minutes`, default 60
- 学習target: 旧倍率 0.9 / 1.3 のdatasetから生成
- validation/test評価: 新倍率 1.0 / 1.25 のbacktestでpolicyを選ぶ

詳細判断は `docs/decisions/0005_dense_entry_quality_targets.md` に記録する。

推論時の基本方針:

```text
long_utility = predicted_long_ev - alpha * predicted_long_risk
short_utility = predicted_short_ev - alpha * predicted_short_risk

max(long_utility, short_utility) > threshold なら entry
long_utility > short_utility なら long
short_utility > long_utility なら short
それ以外は stay_flat
```

詳細判断は `docs/decisions/0002_multitask_targets.md` に記録する。

## モデル候補

軽量モデル:

- Logistic Regression
- Random Forest
- Gradient Boosting
- 小型 MLP

初回ベンチマーク:

- `src/trade_data/modeling.py` で HistGradientBoosting の multi-task baseline を実装。
- これは深層学習前の固定比較対象であり、最終モデルではない。
- regression で long/short expected adjusted pnl と side_score を予測する。
- classification で分位点 bin と補助 `label` を予測する。
- 現在のHGB実装はtargetごとの独立モデルであり、shared representationを持たない。そのため、dense entry quality targetはEV予測の表現改善には直接効かない。
- 現時点の selection metric は oracle exit を使うため、entry/side ranking の暫定評価に限る。
- 次の評価では、予測値だけで entry/exit を実行する backtest policy に接続する。

実行可能 policy:

- `src/trade_data/backtest.py` の `model-policy` で保存済み予測を backtest に接続する。
- `stateful_ev` は flat 時だけ entry threshold を見て入り、保有中は current side EV と exit threshold で閉じる。
- `model-sweep` は validation 月で閾値を選ぶために使い、test 月で閾値を選ばない。
- `model-sweep-summary` は複数 validation fold の sweep を同一 policy parameter ごとに集計する。
- policy selection は単月の最高損益ではなく、fold 数、最低取引数、強制決済率、drawdown、各foldの最低P/Lを満たす候補から選ぶ。
- dense entry quality prediction は `--max-wait-regret`, `--min-entry-rank`, `--require-profit-barrier` でentry filterとして使える。
- 2025-01 の初回 test は adjusted pnl `-35.8255` で、trading baseline より損失は小さいが no_trade には負けた。
- 以後は oracle-exit metric と executable backtest score を明確に分けて記録する。
- 教師 target は旧倍率 0.9 / 1.3 を維持し、validation/test の executable backtest は新倍率 1.0 / 1.25 で評価する。

直近の暫定採用条件:

- train target: 旧倍率 0.9 / 1.3
- validation/test backtest: 新倍率 1.0 / 1.25
- policy選択: 複数 validation sweep を横断集計
- 制約: 各fold 30 trades以上、強制決済率、max drawdown、各fold adjusted pnl を明示的に制御する
- 2024-11/2024-12 の down-regime fold を入れると、従来候補は棄却された

学習品質改善の優先順位:

1. 連続期間だけでなく、上昇・下落・レンジ月を混ぜた train split を使う。
2. `month_label` sample weighting で、特定月・多数派ラベルが損失を支配しないようにする。
3. 複数 validation 月で calibration と policy selection を行う。
4. それでも test が崩れる場合は、閾値ではなく教師 target と特徴量を変える。

次に改善する target / feature:

- fixed horizon return を追加し、oracle best exit だけに依存しない。
- long/short 別、regime 別の calibration を追加する。
- 直近数日トレンド、ボラティリティ、ATR percentile、MA乖離、drawdown などの regime feature を追加する。
- exit timing は best holding minutes 回帰だけでなく、exit probability / hazard target と比較する。
- HGBの予測済みtargetを入力にした二段階meta modelを作り、executable trade outcomeをvalidationでcalibrateする。
- meta model は同じvalidation月でfitとpolicy selectionをしない。validation内walk-forwardで、meta fit月、policy selection月、test月を分ける。

深層学習:

- 1D CNN
- TCN
- LSTM
- GRU
- Transformer encoder
- CNN + GRU
- multi-task network

## 入力設計

入力系列:

- M1 の直近 60 分
- M1 の直近 240 分
- M5 の直近 24 本
- M1 + M5 の multi-timeframe

特徴量:

- OHLC 正規化
- returns
- rolling stats
- volatility
- FFT features
- time features
- gap flags

正規化:

- train period の統計量だけで fit する。
- validation/test の統計量を fit に使わない。
- rolling z-score は過去 window のみで計算する。

## 学習設定

候補:

- optimizer: AdamW を初期候補にする。
- loss: cross entropy, focal loss, utility-weighted loss を比較する。
- scheduler: ReduceLROnPlateau または cosine decay を比較する。
- regularization: dropout, weight decay, early stopping。
- imbalance 対応: class weight, sampling, threshold tuning。

保存するもの:

- model checkpoint
- config
- train/valid loss
- train/valid backtest score
- monthly score table
- predictions
- trade log
- equity curve

## 過学習対策

- walk-forward で評価する。
- test 月は最後まで触らない。
- 単月の最高スコアではなく、複数月の平均と分散で見る。
- 特徴量の追加ごとにベースラインと比較する。
- validation が改善しても、取引回数や drawdown が悪化していないか確認する。
- モデルサイズを大きくする前に、単純モデルの失敗理由を確認する。
