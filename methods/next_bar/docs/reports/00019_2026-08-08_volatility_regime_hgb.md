# 00019 Volatility-regime HGB

日時: 2026-08-08 02:15 JST

## 目的

低・通常・高ボラで次足方向の関係が異なる可能性を検証する。同一HGBへ全局面を混ぜず、判定時点で既知の加工特徴 `volatility_20` によって3つの専用HGBへルーティングした。

## 固定した方法

- 各foldのtrainだけで `volatility_20` の1/3、2/3分位点を計算する。
- low / normal / highそれぞれへ、baselineと同じ38加工特徴、同じHGB parameterで独立モデルを学習する。
- trainで固定した境界をcalibration/testへそのまま適用する。test分布で境界を再計算しない。
- 確率校正は既存のchronological Platt、評価期間は2020〜2026途中の同一7fold。
- 結果を見る前に、単体、baseline 75% + regime 25%通常blend、baseline方向維持型confidence blendの3比較を固定した。

実装は `--model-type regime_hgb`。各モデル、境界、train件数をartifactへ保存し、1行の最新推論でも該当regimeだけへ安全にルーティングできることをテストした。

## 単体結果

| period | model | accuracy | Brier | log loss | ECE |
|---|---|---:|---:|---:|---:|
| 2020–2023 | baseline | 52.014% | 0.2493466 | 0.6918398 | 0.377% |
| 2020–2023 | regime single | 51.775% | 0.2495272 | 0.6922030 | 0.251% |
| 2024–2026途中 | baseline | 51.501% | 0.2495525 | 0.6922506 | 0.298% |
| 2024–2026途中 | regime single | 51.380% | 0.2496543 | 0.6924548 | 0.190% |
| all | baseline | 51.816% | 0.2494261 | 0.6919985 | 0.347% |
| all | regime single | 51.623% | 0.2495763 | 0.6923003 | 0.228% |

ECEだけは改善したが、accuracy、Brier、log lossはdevelopmentとconfirmationの両方で悪化した。局面ごとの学習件数を約1/3へ減らした不利を、関係の局面差が上回らなかった。

## 固定25% blend

通常blendは全体accuracyを51.816%から51.835%へ上げ、Brier、log loss、ECEも改善した。しかしconfirmation accuracyは51.501%から51.430%へ低下した。全体の誤り修正2,796件、新規誤り2,769件、McNemar exact p=0.727で、方向改善の根拠にはならない。

baseline方向を固定してconfidence edgeだけをregime HGBで25%補正すると、accuracyはbaselineと完全に同じになった。

| period | metric | baseline | direction-preserving blend |
|---|---|---:|---:|
| 2020–2023 | Brier | 0.2493466 | 0.2493239 |
| 2020–2023 | log loss | 0.6918398 | 0.6917940 |
| 2020–2023 | ECE | 0.377% | 0.203% |
| 2024–2026途中 | Brier | 0.2495525 | 0.2495512 |
| 2024–2026途中 | log loss | 0.6922506 | 0.6922482 |
| 2024–2026途中 | ECE | 0.298% | 0.196% |
| all | Brier | 0.2494261 | 0.2494117 |
| all | log loss | 0.6919985 | 0.6919694 |
| all | ECE | 0.347% | 0.200% |

aggregateでは3つの校正指標が両期間で改善し、これまでの方向維持型候補中でECEが最良だった。一方、fold別改善はBrier 2/7、log loss 2/7、ECE 5/7。Brier/log lossの改善量もconfirmationでは極小であり、確率校正全体を置換する安定性はない。

## 高信頼度レーン

coverage-aware selection scoreは `sqrt(coverage) * max(Wilson lower - 0.50, 0)` の固定評価。0.53〜0.60を確認したが、全thresholdでbaselineを下回った。

| period | confidence | model | rows | accuracy | selection score |
|---|---:|---|---:|---:|---:|
| all | 0.53 | baseline | - | - | 0.01942 |
| all | 0.53 | regime confidence | 33,033 | 54.473% | 0.01877 |
| all | 0.54 | baseline | - | - | 0.01568 |
| all | 0.54 | regime confidence | 17,866 | 55.066% | 0.01521 |
| all | 0.55 | baseline | 11,708 | 55.501% | 0.01306 |
| all | 0.55 | regime confidence | 9,435 | 55.644% | 0.01183 |
| confirmation | 0.55 | baseline | 1,887 | 55.750% | 0.00642 |
| confirmation | 0.55 | regime confidence | 1,428 | 56.513% | 0.00627 |

0.55のraw accuracyは上がったが、coverage縮小を補えず評価関数は悪化した。この候補から採用thresholdは作らない。

## 判断

- regime HGB単体は方向モデルとして棄却する。
- 通常25% blendもconfirmation方向精度が悪化したため棄却する。
- 方向維持型25% blendはECE診断用のparallel shadowとして `m15_regime_hgb_confidence_shadow_v1.json` に固定する。authoritative confidence、odds、採用policyは置換しない。
- fresh期間でECEだけでなくBrier、log loss、高信頼selection scoreも同時改善した場合に限り再検討する。
- 損益は評価関数へ含めていない。後続の損益診断でも損失倍率は標準1.0のみを使う。
