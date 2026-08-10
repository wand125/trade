# 00023 Signed-body quantile distribution

日時: 2026-08-08 06:21 JST

## 目的

符号付き次足実体の点推定だけでなく予測分布の幅を学び、予測値に対する不確実性をconfidenceへ反映する。中央値が同じでも25–75%分位幅が狭ければ高信頼、広ければ低信頼とする。

## 固定した方法

レポート00022と同じ、次足実体を判定時ATRで正規化した符号付き `asinh` 連続教師を使う。HGB quantile regressionを0.25、0.50、0.75の3本だけ学習し、次式をraw direction scoreとした。

```text
score = predicted q50 / max(abs(predicted q75 - predicted q25), 1e-6)
raw P(up) = sigmoid(score)
```

その後のPlatt校正は各foldのtrainより後のcalibration期間だけで行う。分位、幅のfloor、HGB parameter、2020〜2026途中の7fold、固定blend weight 25%は結果前に固定し、再調整していない。実装名は `--model-type signed_body_quantile_hgb`。

## 単体と通常blend

| period | model | accuracy | Brier | log loss | ECE |
|---|---|---:|---:|---:|---:|
| all | baseline | 51.816% | 0.2494261 | 0.6919985 | 0.347% |
| all | quantile single | 51.725% | 0.2494022 | 0.6919504 | 0.486% |
| confirmation | baseline | 51.501% | 0.2495525 | 0.6922506 | 0.298% |
| confirmation | quantile single | 51.439% | 0.2495565 | 0.6922585 | 0.437% |

単体は全体Brier/log lossだけ改善したが、方向accuracyとECE、confirmation proper scoreが悪化したため方向モデルとして棄却する。

通常25% blendも全体accuracy 51.800%、confirmation 51.496%でbaseline未満。誤り修正1,776件、新規誤り1,800件、McNemar exact p=0.701のため方向用途には採用しない。

## 方向維持型confidence blend

baseline方向を固定し、quantile modelをconfidence edgeへ25%使った。

| period | metric | baseline | candidate |
|---|---|---:|---:|
| 2020–2023 | Brier | 0.2493466 | 0.2493094 |
| 2020–2023 | log loss | 0.6918398 | 0.6917647 |
| 2020–2023 | ECE | 0.377% | 0.356% |
| 2024–2026途中 | Brier | 0.2495525 | 0.2495414 |
| 2024–2026途中 | log loss | 0.6922506 | 0.6922285 |
| 2024–2026途中 | ECE | 0.298% | 0.300% |
| all | Brier | 0.2494261 | 0.2493990 |
| all | log loss | 0.6919985 | 0.6919438 |
| all | ECE | 0.347% | 0.334% |

Brierとlog lossはdevelopment・confirmationの両方、6/7 foldで改善。ECEはconfirmationで僅かに悪化し、fold改善3/7なので、オッズ値そのものの置換には使わない。

## developmentで選んだconfidence 0.525 lane

00022と同じ固定候補グリッドでdevelopment selection scoreが最大だった0.525を選び、confirmationへ固定した。

| period | model | rows | coverage | accuracy | selection score |
|---|---|---:|---:|---:|---:|
| 2020–2023 | baseline | 33,770 | 37.908% | 53.858% | 0.02048 |
| 2020–2023 | candidate | 33,598 | 37.715% | 54.078% | 0.02177 |
| 2024–2026途中 | baseline | 14,785 | 26.375% | 53.777% | 0.01527 |
| 2024–2026途中 | candidate | 14,830 | 26.455% | 54.086% | 0.01689 |
| all | baseline | 48,555 | 33.454% | 53.834% | 0.01961 |
| all | candidate | 48,428 | 33.366% | 54.080% | 0.02100 |

全体coverageはほぼ同じまま、accuracy +0.246pt、selection score +7.12%。confirmationでもaccuracy +0.309pt、score +10.61%を再現した。年別accuracyとselection scoreはいずれも6/7 fold改善し、悪化は2025だけだった。

0.55は全体accuracyが55.50%から55.31%へ下がる。0.52も改善するがdevelopmentでは0.525のscoreが上なので採用しない。0.525だけを固定候補とする。

## 判断

- quantile単体と通常blendは方向用途として棄却する。
- 方向維持型25% blend + confidence 0.525を `m15_signed_body_quantile_confidence_candidate_v1.json` の中coverage選別候補へ固定する。
- confirmation ECEが僅かに悪化したため、authoritative confidenceやfair oddsの置換候補にはしない。
- 00022のsigned-body 0.52とstackせず、fresh期間で広coverage 0.52と中coverage 0.525を独立比較する。
- 損益は目的関数へ含めず、損失倍率は標準1.0のみとする。
