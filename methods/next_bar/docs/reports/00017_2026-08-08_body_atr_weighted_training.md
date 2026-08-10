# 00017 Body/ATR-weighted HGB training

日時: 2026-08-08 01:56 JST

## 目的

方向がほぼランダムになりやすい小実体の次足を学習時だけ弱め、明確な実体を持つ教師を相対的に重視することで、M15の方向精度または高信頼度精度を改善できるか確認する。

## 固定条件

入力は現行HGBと同じ38加工特徴。次足実体は未来の教師情報なので入力特徴にはせず、train partitionのsample weightだけに使う。

```text
strength = abs(next_bar_body) / (decision_close * atr_ratio_20)
raw_weight = 0.5 + clip(strength, 0.0, 1.5)
sample_weight = raw_weight / mean(raw_weight in the train fold)
```

各foldの実weightは平均1.0、最小約0.508、最大約2.034。calibration/testは重み付けせず、通常Platt校正と全行評価を行う。weight式、HGB parameter、25% blendは事前固定し、結果を見た再調整はしない。

実験は `walk_forward_body_atr_weighted_001`。通常blendは `ensemble_body_atr_weighted_25_001`、方向維持型は `body_atr_weighted_confidence_blend_001`。

## 単体方向モデル

| period | model | accuracy | balanced accuracy | Brier | log loss | ECE |
|---|---|---:|---:|---:|---:|---:|
| 2020–2023 | baseline | 52.014% | 52.005% | 0.2493466 | 0.6918398 | 0.377% |
| 2020–2023 | weighted | 51.796% | 51.791% | 0.2493359 | 0.6918171 | 0.474% |
| 2024–2026途中 | baseline | 51.501% | 51.270% | 0.2495525 | 0.6922506 | 0.298% |
| 2024–2026途中 | weighted | 51.408% | 51.167% | 0.2495417 | 0.6922288 | 0.320% |
| all | baseline | 51.816% | 51.756% | 0.2494261 | 0.6919985 | 0.347% |
| all | weighted | 51.646% | 51.592% | 0.2494154 | 0.6919761 | 0.414% |

weighted単体はBrier/log lossをわずかに改善したが、方向accuracyが全体-0.170pt、development-0.219pt、confirmation-0.093pt。7fold中6foldでbaselineを下回るため方向モデルとして棄却する。

通常25% blendも全体accuracy 51.800%、confirmation 51.483%でbaselineを下回ったため、方向変更には使わない。

## 方向維持型confidence blend

HGB方向を固定し、weighted HGB 25%をconfidence edgeの強さだけに使った。

| period | metric | baseline | candidate |
|---|---|---:|---:|
| 2020–2023 | Brier | 0.2493466 | 0.2493001 |
| 2020–2023 | log loss | 0.6918398 | 0.6917457 |
| 2020–2023 | ECE | 0.377% | 0.292% |
| 2024–2026途中 | Brier | 0.2495525 | 0.2495315 |
| 2024–2026途中 | log loss | 0.6922506 | 0.6922085 |
| 2024–2026途中 | ECE | 0.298% | 0.255% |
| all | Brier | 0.2494261 | 0.2493895 |
| all | log loss | 0.6919985 | 0.6919245 |
| all | ECE | 0.347% | 0.276% |

方向と全体accuracyはbaselineと完全同一。3つの確率品質指標はdevelopmentとconfirmationの両方で改善した。

## confidence 0.54精度lane

| period | model | rows | coverage | accuracy | Wilson lower | selection score |
|---|---|---:|---:|---:|---:|---:|
| 2020–2023 | baseline | 16,172 | 18.154% | 54.675% | 53.906% | 0.01664 |
| 2020–2023 | candidate | 15,127 | 16.981% | 55.120% | 54.326% | 0.01783 |
| 2024–2026途中 | baseline | 4,715 | 8.411% | 55.270% | 53.847% | 0.01116 |
| 2024–2026途中 | candidate | 4,437 | 7.915% | 55.465% | 53.999% | 0.01125 |
| all | baseline | 20,887 | 14.391% | 54.809% | 54.133% | 0.01568 |
| all | candidate | 19,564 | 13.479% | 55.198% | 54.501% | 0.01652 |

coverageを0.912pt減らす代わりにaccuracyを0.389pt上げ、selection scoreを5.38%改善した。年別ではaccuracyが7/7 fold、selection scoreが5/7 foldで改善した。

confidence 0.53はaccuracyが小幅改善したものの、selection scoreが `0.01942 -> 0.01909` へ低下したため採用しない。広いcoverageを優先するlaneは、selection score 0.02006のExtra Trees confidence 0.53候補が優位である。

## 判断

- body/ATR weighted HGB単体と通常25% blendは方向モデルとして不採用。
- 方向維持型25% blend + confidence 0.54を `m15_body_atr_weighted_confidence_candidate_v1.json` の精度重視forward candidateに固定する。
- Extra Trees 0.53をcoverage重視、body/ATR weighted 0.54を精度重視として分離し、目的関数の異なる候補を結果後に混合しない。
- 現行方向、authoritative confidence、採用policy、paper売買policyは次の完全未使用期間まで変更しない。
- 次期forwardで0.54 accuracy、selection score、Brierがすべてbaseline以上なら昇格を検討する。
- 損益は目的関数に含めていない。後続診断を行う場合も損失倍率は標準1.0のみとする。
