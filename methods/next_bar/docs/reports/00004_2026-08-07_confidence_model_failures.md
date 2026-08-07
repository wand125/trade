# 00004 Confidence model failures

日時: 2026-08-07 18:08 JST
更新日時: 2026-08-07 18:08 JST

## 目的

全体ECEでは相殺されていたup/down非対称を修正し、予測方向が実際に当たる確率としてconfidenceを改善する。

## 候補

1. `side_platt`: calibration期間のpredicted up/downを分け、class confidenceからcorrectnessをPlatt校正。
2. `context_hgb`: calibration期間を前半、次の1/4、最後の1/4へ時系列分割し、方向確率校正、correctness HGB学習、correctness確率校正を別データで実行。入力は確率余裕、足形比率、RSI、volatility、ATR比、efficiency、gap、時刻周期のみ。

## 結果

class probability baselineのconfidence 0.55以上accuracyはM1 56.65%、M5 57.23%、M15 55.08%、M30 53.99%。

side PlattはM1 53.12%、M5 56.68%、M15 54.91%、M30 54.77%。M30以外は悪化し、fold間変動も縮まらなかった。

context HGBはM1 54.43%、M5 52.78%、M15 52.52%、M30 51.36%。全時間足で悪化した。coverageもM5 0.18%、M15 0.44%、M30 1.29%まで減少した。

## 判断

- `side_platt` と `context_hgb` は標準confidenceとして棄却。
- correctnessを1年のcalibration contextから学ぶ方法は局所関係へ過適合しやすい。
- confidenceは当面、方向確率のclass confidenceへ戻す。
- 正答率を作る方向モデル本体の改善を先に行い、同じ正規化加工系列を使うMLPを次候補とする。
