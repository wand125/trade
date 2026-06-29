# Research Plan

## 原則

この研究は、いきなり深層学習で最適化しない。まずバックテスト仕様、データ分割、ベースライン、オラクル上限を整え、その後に深層学習モデルを比較する。

全てのモデルは、過去データだけを入力として意思決定し、将来情報を特徴量に混ぜない。

## Phase 0: 文書とデータ基盤

目的:

- 研究ゴール、取引ルール、評価方針を明文化する。
- データ取得・変換・検証を再実行可能にする。
- 研究を途中再開できる記録構造を作る。

完了条件:

- `GOAL.md` がある。
- `docs/` が整備されている。
- M1/M5 Parquet が生成済み。
- データ検証結果が記録されている。

## Phase 1: バックテスト環境

目的:

- 取引ルールを厳密に再現する。
- 1 か月単位の損益を計算できるようにする。
- モデルなしのベースラインを測る。

実装するもの:

- ポジション状態管理
- ロング/ショートの損益計算
- 24 時間強制決済
- 同時保有 1 玉制約
- 月次集計
- trade log 出力
- equity curve 出力

最初のベースライン:

- 常に取引しない
- ランダムエントリー
- 移動平均クロス
- RSI/逆張り
- ボラティリティブレイク
- オラクル上限の近似

## Phase 2: 特徴量と教師ラベル

目的:

- 価格系列から、将来リークのない特徴量を作る。
- エントリー方向と決済判断の教師ラベルを定義する。

特徴量候補:

- 価格差分
- log return
- rolling return
- rolling volatility
- rolling z-score
- high-low range
- ATR 系の変動幅
- EMA/SMA 乖離
- RSI/MACD 系の短期モメンタム
- 時間帯、曜日、月末/月初
- FFT/STFT の低周波・高周波エネルギー
- 1 階差分、2 階差分
- ノイズ除去後の傾き

ラベル候補:

- 未来 24 時間以内の最大期待損益が正か。
- ロング/ショート/見送りの 3 クラス。
- 期待損益の回帰。
- 決済タイミングの hazard model。
- 取引単位の ranking target。
- 一玉制約の機会費用を含む `stateful_entry_value` / `blocking_cost` target。
- guardで抑制した後の代替tradeを評価する `stateful_positive_cost_value` / `positive_replacement_regret` target。

## Phase 3: 古典モデルと軽量モデル

目的:

- 深層学習前に、単純モデルの基準点を作る。
- 特徴量の有効性を素早く確認する。

候補:

- Logistic Regression
- Random Forest
- Gradient Boosting
- LightGBM/XGBoost 系
- 小型 MLP

評価:

- 分類精度だけでなく、必ずバックテスト損益で見る。
- 月別スコアの分散を見る。
- 取引回数が少なすぎるモデルは別枠で評価する。

## Phase 4: 深層学習

目的:

- 系列パターンから、エントリー・方向・決済を予測する。

候補:

- 1D CNN
- TCN
- LSTM/GRU
- Transformer encoder
- CNN + RNN
- マルチタスクモデル

調整対象:

- 入力系列長
- 足種別 M1/M5
- 特徴量セット
- レイヤー数
- hidden size
- dropout
- weight decay
- learning rate
- batch size
- loss function
- class weight
- early stopping

## Phase 5: 方策最適化

目的:

- エントリー、ホールド、決済を一体の意思決定問題として扱う。

候補:

- Offline imitation learning
- DQN 系
- PPO 系
- ルールベース exit + learned entry
- learned entry + learned exit
- side/context guard 発火後に、代替tradeへ入るか stay flat/cooldown するかを決める admission policy。

注意:

- 強化学習は過学習しやすいため、Phase 1 から 4 の基盤なしに進めない。
- 報酬は月次損益だけでなく、ドローダウンや取引回数も監視する。

## Phase 6: ロバスト性検証

目的:

- 期間依存の過学習を避ける。
- 欠損、ノイズ、スプレッド変動に強いモデルを選ぶ。

検証:

- walk-forward
- 年別 holdout
- 月別 holdout
- high volatility month / low volatility month の比較
- 価格ノイズ注入
- 欠損注入
- スプレッド悪化シナリオ
- 取引不可時間帯の除外
