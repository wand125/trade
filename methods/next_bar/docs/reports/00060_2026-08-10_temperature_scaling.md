# 00060 Temperature scaling

日時: 2026-08-10 18:10 JST

## 目的

Platt校正は傾きと切片を学ぶため、校正によって0.5の方向境界も移動する。そこで、生確率のlogitを正の温度1個だけで縮放するtemperature scalingを追加し、方向を必ず維持したままconfidenceと高信頼帯を改善できるか検証する。

## 実装と固定条件

- `--probability-calibration temperature` を追加した。
- 写像は `sigmoid(logit(p) / T)`、`T > 0`。各foldの後続calibration期間だけでlog lossを最小化する。
- `T` は0.05〜20の固定範囲でL-BFGS-Bにより学習し、方向境界、HGB、baseline 38特徴、uniform binary target、7foldを固定した。
- model artifact保存とlatest予測のround-trip、単調性、方向維持、有限確率をテストした。
- developmentは2020〜2023、confirmationは2024〜2026-06、合計145,140 OOS行。

学習温度は年順に1.737、1.217、1.364、2.655、2.102、2.189、2.625だった。すべて1より大きくconfidenceを0.5側へ縮めた一方、縮小量には大きな期間差があった。

## 全確率と方向結果

| period / calibrator | accuracy | Brier | log loss | ECE |
|---|---:|---:|---:|---:|
| development Platt | 52.014% | 0.2493466 | 0.6918398 | 0.377% |
| development Temperature | 51.889% | 0.2492889 | 0.6917217 | 0.438% |
| confirmation Platt | 51.501% | 0.2495525 | 0.6922506 | 0.298% |
| confirmation Temperature | 51.376% | 0.2496663 | 0.6924789 | 0.175% |
| all Platt | 51.816% | 0.2494261 | 0.6919985 | 0.347% |
| all Temperature | 51.691% | 0.2494346 | 0.6920141 | 0.337% |

TemperatureはPlattよりdevelopmentのBrier/log lossだけ改善したが、confirmationでは両方悪化した。方向はdevelopment -112件、confirmation -70件、全期間-182件で、全期間paired p=0.232。accuracy/Brier/log loss/ECEのfold勝数もそれぞれ3/7、3/7、3/7、2/7に留まった。

Temperature自体は生モデルの方向を変えない。ただし比較対象のPlattが0.5境界を動かすため、両校正の最終方向には差が生じる。今回の結果は、そのPlattによる境界移動を捨てる根拠にならない。

## Development選択0.52

development gridではTemperatureのselection scoreが0.52で最大だった。

| period / calibrator | accuracy | coverage | selection score |
|---|---:|---:|---:|
| development Platt | 53.379% | 47.319% | 0.01997 |
| development Temperature | 53.639% | 45.983% | 0.02140 |
| confirmation Platt | 52.918% | 36.650% | 0.01353 |
| confirmation Temperature | 52.521% | 30.107% | 0.00970 |
| all Platt | 53.228% | 43.198% | 0.01865 |
| all Temperature | 53.313% | 39.851% | 0.01834 |

developmentのaccuracyとscore改善はconfirmationで反転した。foldではaccuracy 5/7でもselection scoreは3/7だけ改善し、coverageを減らして精度も下げたconfirmation失敗を補えない。

## 固定0.55とprecision champion

見かけ上の高信頼精度だけで採用しないため、同じ0.55で既存Intrabar Structure precision championと直接比較した。

| period / candidate | accuracy | coverage | selection score |
|---|---:|---:|---:|
| development Temperature | 56.144% | 10.103% | 0.01626 |
| development Structure | 55.934% | 10.888% | 0.01631 |
| confirmation Temperature | 57.664% | 1.466% | 0.00516 |
| confirmation Structure | 56.437% | 3.104% | 0.00722 |
| all Temperature | 56.272% | 6.767% | 0.01376 |
| all Structure | 56.010% | 7.881% | 0.01431 |

Temperatureはaccuracyを0.26pt上げたが、coverage低下により全期間scoreは下がった。年別もaccuracy 3/7、score 2/7だけの勝利だった。日次5,000回bootstrapの全期間Temperature−Structure差はaccuracy +0.261pt、95%区間-0.551〜+1.093pt、coverage -1.114pt、区間-1.287〜-0.950pt、score -0.000557、区間-0.002723〜+0.001673だった。confirmationのBrier差+0.000119とlog loss差+0.000238は95%区間も正で、Temperatureの確率品質悪化を支持した。

0.60以上はaccuracy 64.855%だったが276件、coverage 0.190%しかなく、採用判断に足る厚みはない。

## 判断

Temperature scalingは棄却する。方向維持という設計上の利点は確認できたが、校正の本来目的であるconfirmation proper scoreを悪化させ、0.52はselection scoreが反転、0.55はprecision championよりcoverage-aware objectiveが低かった。

- 実装とartifact/latest経路は再現用に残す。
- candidate config、registry entry、latest artifactは発行しない。
- 標準確率校正はPlatt、precision championはIntrabar Structure 0.55を維持する。
- 温度範囲、期間別温度の平滑化、別閾値を同じ履歴へ合わせて再探索しない。

主要成果物:

- `experiments/next_bar/walk_forward_temperature_m15_001`
- `experiments/next_bar/temperature_m15_candidate_analysis.json`
- `experiments/next_bar/temperature_vs_intrabar_structure_m15_055_analysis.json`
- `experiments/next_bar/temperature_vs_intrabar_structure_m15_055_daily_bootstrap.json`
