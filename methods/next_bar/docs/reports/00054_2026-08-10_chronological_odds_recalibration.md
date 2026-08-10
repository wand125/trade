# 00054 Chronological correctness odds recalibration

## 目的

M15 Intrabar Volatility Shapeのpredicted-class confidenceを「予測方向が正しい確率」としてさらに改善できるか、過去OOSだけで学ぶ単調isotonicとglobal correctness Plattを比較した。方向予測と正誤列は変更しない。

## 方法

- 各評価foldより前の全OOS foldで `confidence -> correct` を学習する。
- isotonic regressionは `[0, 1]`、範囲外clipで単調写像する。
- Plattはconfidence 1変数のunregularized相当logistic regressionとする。
- 最初のfoldはcalibration用OOSがないため除外し、2021〜2026途中の121,950件を元confidenceと同一行で比較する。
- current foldの正解を反転してもcurrent foldの校正値が変わらない因果性テストを追加した。

実装は `src/trade_data/next_bar_odds_recalibration.py`、CLIは `methods/next_bar/scripts/chronological_odds_recalibration.py`、成果物は `experiments/next_bar/intrabar_volatility_shape_m15_chronological_odds_recalibration_001` である。

## 結果

| method | mean confidence | Brier | log loss | ECE |
|---|---:|---:|---:|---:|
| 元Shape confidence | 52.1731% | 0.2495824 | 0.6923127 | 0.420% |
| chronological isotonic | 52.4562% | 0.2499363 | 0.6964012 | 0.742% |
| chronological correctness Platt | 52.4200% | 0.2497004 | 0.6925555 | 0.668% |

正答率は全方式で51.7532%と同一である。isotonicはBrier/log lossを6/6評価foldで改善できず、ECE改善も1/6だった。correctness PlattもBrier/log loss改善2/6、ECE改善1/6に留まり、合算proper metricは3つとも悪化した。

特に最初のnested評価である2021は、2020の高い実績を引き継いでmean confidenceを元の53.213%からisotonic 54.798%、Platt 54.454%へ押し上げたが、実accuracyは52.505%であり過信した。年をまたぐ実績水準のshiftを単純なexpanding再校正が追えない。

## 判定

両方式を棄却する。既に棄却した階層bin校正とside Plattに加え、単調isotonicも元Shape confidenceを上回らなかった。`m15_intrabar_volatility_shape_odds_shadow_v1.json` の元model confidenceを非認可odds shadowとして維持し、authoritative oddsへの昇格はfresh期間のglobal/local整合とWilson edgeで判定する。

