# Calibrated Trade Failure And Exit Targets

日時: 2026-06-28 08:07 JST

## 目的

loss 1.20 標準化後の暫定比較基準 `shrink065 top-min` を、calibrated EV 列で正しく再分析する。

あわせて、次の弱点である exit timing target の追加を開始する。

対象候補:

- model/calibration: `experiments/20260627_224357_regime_ev_calib_train_oof4m_vol_session_shrink065/`
- 2024-12 trades: `data/reports/backtests/20260627_224855_model_timed_ev_2024-12_1/trades.csv`
- 2025-02 trades: `data/reports/backtests/20260627_224900_model_timed_ev_2025-02_1/trades.csv`
- predictions: `predictions_test_regime_calibrated.parquet`
- analysis EV columns:
  - `pred_regime_calibrated_long_best_adjusted_pnl`
  - `pred_regime_calibrated_short_best_adjusted_pnl`

## 実装

`trade_data.backtest analyze-trades` に `--long-column` / `--short-column` を追加した。

これにより、calibrated predictions を分析するときに、canonical な `pred_long_best_adjusted_pnl` / `pred_short_best_adjusted_pnl` ではなく、実際にpolicyが使ったEV列を指定できる。

この修正がないと、calibrated policyのtradeにraw EVを突き合わせてしまい、方向ミスやEV過大評価の診断がずれる。

## 分析Artifact

- 2024-12: `data/reports/backtests/20260627_225848_analyze_shrink065_topmin_calib_2024-12/`
- 2025-02: `data/reports/backtests/20260627_225848_analyze_shrink065_topmin_calib_2025-02/`

## Summary

| month | trades | adjusted pnl | raw pnl | win rate | long pnl | short pnl | direction error rate | predicted side error rate | exit regret sum | best side regret sum | EV overestimate vs realized mean |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2024-12 | 12 | 18.8306 | 25.3280 | 0.6667 | -12.5294 | 31.3600 | 0.5000 | 0.5000 | 183.3884 | 350.2406 | 14.7013 |
| 2025-02 | 12 | -44.5990 | -31.0630 | 0.5000 | -5.5990 | -39.0000 | 0.7500 | 0.7500 | 225.5660 | 464.2190 | 20.0388 |

## 2025-02 Breakdown

方向別:

| direction | trades | adjusted pnl | direction error rate | predicted side error rate | exit regret |
|---|---:|---:|---:|---:|---:|
| long | 11 | -5.5990 | 0.7273 | 0.7273 | 185.3760 |
| short | 1 | -39.0000 | 1.0000 | 1.0000 | 40.1900 |

session別:

| session | trades | adjusted pnl | direction error rate |
|---|---:|---:|---:|
| asia | 2 | -37.2070 | 1.0000 |
| rollover | 8 | -28.8420 | 0.7500 |
| ny_late | 2 | 21.4500 | 0.5000 |

実績best side別:

| actual best side | trades | executed side | adjusted pnl | direction error rate |
|---|---:|---|---:|---:|
| short | 8 | all long | -30.7830 | 1.0000 |
| long | 4 | mostly long, one short | -13.8160 | 0.2500 |

worst trade:

- entry: `2025-02-10 04:32 UTC`
- side: short
- adjusted pnl: `-39.0000`
- raw pnl: `-32.5000`
- regime: `asia`, `up`, `low_vol`
- actual best side: long
- actual taken best adjusted pnl: `1.1900`
- actual opposite best adjusted pnl: `65.2700`
- EV overestimate vs realized: `55.0888`
- exit regret: `40.1900`
- best side regret: `104.2700`

## 判断

- 問題は単純な「shortが多すぎる」ではない。
- 2025-02では actual best side が short の局面を long で入り、唯一のshortは大きく外している。
- calibrated EV の方向選択が未知月で壊れている。
- 全tradeで exit regret が正で、勝ちtradeも含めて手放し方に改善余地がある。
- predicted wait regret は全tradeが `0-2` bucket に入り、今回候補の失敗分離には効いていない。
- 2025-02の損失は `low_vol` に集中し、特に `asia` / `rollover` の扱いが弱い。

## Exit Timing Target

`future_best_labels` に固定保有時間のtargetを追加した。

追加列:

- `long_fixed_60m_adjusted_pnl`
- `short_fixed_60m_adjusted_pnl`
- `long_fixed_240m_adjusted_pnl`
- `short_fixed_240m_adjusted_pnl`
- `long_fixed_720m_adjusted_pnl`
- `short_fixed_720m_adjusted_pnl`

狙い:

- 「24時間内の最良exit」だけではなく、固定保有時間ごとのEVカーブを学習できるようにする。
- exit timingを、単一のbest holding minutes回帰ではなく、複数horizonの損益面として扱う。
- まずは full target set の研究用targetに追加し、policy target set にはまだ入れない。

`prediction_frame` は、古いdatasetでも動くよう、存在しないtarget列を自動的に落とす。`train` / `oof` も、指定targetのうち全frameに存在するものだけを使い、missing targetをmetricsへ記録する。

## 次

1. 固定horizon target入りdatasetを再生成する。
2. fixed horizon EVを使った exit policy を作る。
3. 2025-02の `low_vol + asia/rollover` をvalidation基準に入れ、方向選択の壊れ方を事前に検出する。
4. calibrated EV の方向選択に、side別・regime別の安全marginを追加する。
