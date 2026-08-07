# 00003 Enhanced manual feature candidate

日時: 2026-08-07 13:03 JST
更新日時: 2026-08-07 13:03 JST

## 仮説

生価格を追加せず、方向系列、実体/ATR、ヒゲ差/ATR、rolling up比率、trend/volatility比、短長volatility/ATR比、return autocorrelation/skew、EMA差/ATRを追加すれば次足方向の表現力とdown側識別が改善する。

## 比較条件

- baseline: `experiments/next_bar/walk_forward_001`
- candidate: `experiments/next_bar/walk_forward_enhanced_manual_001`
- 5fold、モデル、学習件数、確率校正を固定し、加工特徴だけを変更した。
- raw `open/high/low/close` は両候補ともモデル特徴に含めていない。

## 結果

| TF | accuracy差 | balanced accuracy差 | 改善fold | conf>=0.55 accuracy差 |
|---|---:|---:|---:|---:|
| M1 | +0.063pt | +0.060pt | 4/5 | −3.243pt |
| M5 | −0.020pt | −0.018pt | 3/5 | −0.587pt |
| M15 | +0.044pt | +0.046pt | 3/5 | +0.193pt |
| M30 | −0.198pt | −0.196pt | 1/5 | +0.043pt |

M1は全体accuracyが上がった一方、down accuracyが48.88%から48.27%へ低下し、confidence 0.55以上のdown accuracyも45.66%から28.14%へ悪化した。up側への偏りを強めた改善であり、目的と一致しない。

M15はdown accuracyが48.33%から48.62%へ改善したが、confidence 0.55以上のdown accuracyは34.06%から30.26%へ悪化。M30は2024 fold以外で悪化した。

## 判断

- 全時間足共通のfeature setとしては棄却。
- M1/M15の一部加工には信号候補があるが、一括特徴追加では寄与を分離できないため未採用。
- 全体ECEが小さくても、予測方向別confidenceは大きく誤校正されている。次は方向分類確率と「その方向予測が当たる確率」を分け、up/down別correctness calibrationを行う。
