# 00070 Volatility State Features

日時: 2026-08-10 20:08 JST

## 目的

足内経路の追加とは独立に、完成M15間で「変動が安定して継続しているか、加速・jump・圧縮遷移しているか」を加工する。次足方向そのものだけでなく、予測しやすい状態のconfidence順位付けを改善できるか検証した。

## 固定特徴

既存baselineの単純なvolatility/ATR水準、trend-structureの短長比を繰り返さず、結果を見る前に次の11列を固定した。

- volatility 5の20/50本変動係数
- volatility 5の3本変化、volatility 20の5本変化を有界対称比へ加工
- log high-low rangeの20本変動係数、lag-1自己相関、20本中央値乖離
- 過去50本range中央値未満だった直近5本の比率
- 20本close realized varianceに対するbipower超過jump比率
- Parkinson/Garman–Klass varianceとclose realized varianceの有界balance

すべて現在の完成足までのrolling値で、次足rangeや将来volatilityは使わない。raw価格水準を含まず、scale 10倍一致、未来側OHLC改変が過去特徴へ不影響、flat相場で有限0、11列の範囲、artifact/latest推論をテストした。baseline 38列へ追加した全49特徴、標準HGB/Platt、expanding 7fold、損失倍率1.0である。

## 方向結果

| period | baseline | Volatility State単体 | 通常25% blend |
|---|---:|---:|---:|
| development | 52.0144% | 51.9392% | 52.0144% |
| confirmation | 51.5012% | 51.4030% | 51.3691% |
| all | 51.8162% | 51.7321% | 51.7652% |

単体はbaseline比-122件、p=0.323、accuracy 4/7だがBrier/log lossは各1/7しか改善しなかった。通常blendは全体-74件、p=0.232。特にconfirmationはfix 643件、harm 717件、純-74件、p=0.0477で悪化が支持された。方向用途は棄却する。

## 方向維持confidence

development gridでは0.525が最大selection scoreになった。

| period | baseline accuracy / coverage / score | Volatility State accuracy / coverage / score |
|---|---:|---:|
| development | 53.858% / 37.908% / 0.02048 | 54.074% / 37.253% / 0.02159 |
| confirmation | 53.777% / 26.375% / 0.015268 | 53.769% / 26.509% / 0.015271 |
| all | 53.834% / 33.454% / 0.01961 | 53.980% / 33.103% / 0.02033 |

development改善はconfirmationでaccuracy -0.009pt、score +0.000003の実質横ばいになった。年別accuracy/scoreは各4/7、Brier/log loss 5/7、ECE 4/7で、事前gateのscore 5/7に届かない。

## 既存0.525候補との比較

| comparator | Volatility State / comparator all accuracy | all score | Volatility Stateのaccuracy / score勝数 |
|---|---:|---:|---:|
| Signed-body Quantile | 53.980% / 54.080% | 0.02033 / 0.02100 | 3/7、3/7 |
| Clear-body | 53.980% / 54.182% | 0.02033 / 0.02088 | 0/7、2/7 |

Signed-body Quantileにはdevelopment、confirmation、allのaccuracy/scoreが全て負けた。Clear-bodyよりcoverageは広いがaccuracyは7/7 foldで負け、confirmation scoreも0.01527対0.01675だった。既存balanced候補を置換する根拠はない。

## 判断

変動状態はbaseline confidenceの確率誤差を少し滑らかにするが、方向edgeを持たず、確認期間のaccuracy×coverage順位付けにも再現しなかった。feature setとOOS成果物は再現用に残すが、config、registry、latest artifactは発行しない。

同じ履歴でwindow、jump定義、OHLC variance estimator、特徴subset、blend weight、閾値を再探索しない。Volatility Shape/Pressure方向候補、Signed-body Quantile/Clear-body 0.525、Full Path 0.53を維持する。

## 成果物

- OOS: `experiments/next_bar/walk_forward_volatility_state_m15_001`
- 通常blend: `experiments/next_bar/ensemble_volatility_state_m15_25_001`
- 方向維持confidence: `experiments/next_bar/volatility_state_m15_confidence_blend_001`
- candidate analysis: `experiments/next_bar/volatility_state_m15_candidate_analysis.json`
- 既存0.525比較: `experiments/next_bar/volatility_state_vs_*_m15_0525_analysis.json`
