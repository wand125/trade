# Data Strategy

## 現在のデータ

HistData 由来の XAUUSD データを使う。

- M1: `data/processed/histdata/xauusd/xauusd_m1.parquet`
- M5: `data/processed/histdata/xauusd/xauusd_m5.parquet`
- Tick sample: `data/processed/histdata/xauusd/tick/year=2025/month=01/HISTDATA_COM_ASCII_XAUUSD_T_202501.parquet`

HistData の timestamp は EST 固定として扱い、変換済み Parquet では UTC に正規化している。

## データ品質

検査項目:

- timestamp 重複
- NULL
- OHLC 不整合
- 異常 gap
- 異常リターン
- 極端なボラティリティ
- Tick の Bid/Ask 逆転
- Tick の spread 分布

週末、祝日、短縮取引に由来する gap は、原則として欠損補完しない。取引不可時間として扱う。

## 前処理

基本特徴量:

- close-to-close diff
- log return
- high-low range
- open-close body
- upper/lower wick
- rolling mean
- rolling std
- rolling min/max
- rolling z-score
- rolling volume/tick count

微分・差分:

- 1 階差分
- 2 階差分
- rolling slope
- local acceleration
- denoised slope

周波数特徴:

- rolling FFT power
- low-frequency energy
- high-frequency energy
- spectral centroid
- short-time FFT
- wavelet 系特徴の検討

時間特徴:

- hour of day
- day of week
- London/New York overlap
- 月初/月末
- 重要指標発表時間帯の外部データ候補

リスク特徴:

- realized volatility
- ATR-like range
- spread proxy
- gap duration
- recent drawdown
- volatility regime

Regime feature / label:

- `trend_score_240`
- `volatility_score_60`
- `trend_regime`
- `volatility_regime`
- `session_regime`
- `gap_regime`
- `combined_regime`

`trend_score_240` と `volatility_score_60` は過去rolling特徴から作るため、学習featureとして使う。カテゴリregimeは、主にbacktestと失敗trade分析の集計軸として使う。

## 初期特徴量セット

実装ファイル:

- `src/trade_data/dataset.py`

初期の月次 dataset では以下を生成する。

- log return: 1, 5, 15, 60
- price diff: 1階差分、2階差分
- candle shape: high-low range, open-close body, upper/lower wick
- gap: gap minutes, gap flag
- RSI: 14
- EMA distance: 12, 26, 12-26
- rolling stats: 15, 60, 240
- ATR-like range: 15, 60, 240
- time encoding: hour sin/cos, day-of-week sin/cos
- FFT: 64, 256 window の low/high power と spectral centroid

CLI:

```bash
python -m trade_data.dataset build --month 2025-01 --min-adjusted-edge 15
```

初期 dataset は、3クラスラベルだけでなく以下のターゲットも含む。

- long/short best adjusted pnl
- long/short best raw pnl
- long/short forced adjusted pnl
- long/short forced raw pnl
- long/short max adverse pnl
- long/short best holding minutes
- side score
- forced side score
- best adjusted pnl quantile
- side score quantile
- best holding time bin

## 欠損・ノイズ対応

方針:

- price の線形補完は原則しない。
- rolling 特徴量の warmup は明示的に drop する。
- gap 直後の bar には gap flag を付ける。
- 極端リターンは削除せず、異常フラグを付けて比較する。
- 学習時には noise injection を使い、ロバスト性を検証する。

## データ分割

ランダム分割は禁止ではないが、主評価には使わない。

基本:

- train: 過去期間
- validation: train の後続期間
- test: validation のさらに後続期間

推奨:

- walk-forward
- 年別 holdout
- 月別 holdout
- volatility regime 別 holdout
- embargo period の導入
- ラベル期間がvalidation/testに重なるtrain/valid rowのpurging

例:

```text
train: 2009-2018
valid: 2019-2020
test:  2021

train: 2009-2019
valid: 2020-2021
test:  2022
```

最終的には複数 split の平均・分散で評価する。
