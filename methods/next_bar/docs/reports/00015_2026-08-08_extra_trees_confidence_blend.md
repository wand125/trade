# 00015 Extra Trees diversity and high-confidence adoption lane

日時: 2026-08-08 01:41 JST

## 目的

boosting型HGBとは構造の異なる多数のランダム木を追加し、M15の方向精度とconfidenceによる採用条件を改善できるか確認する。

## 固定条件

- baselineと同じ38個の加工済み定常特徴を使用し、raw OHLC価格水準は不使用
- Extra Trees 200本、max depth 12、min samples leaf 50、max features 0.75
- random seed 42
- 2020〜2026途中の同一7fold expanding walk-forward
- ensembleはHGB 75% + Extra Trees 25%。weightは事前固定し、結果を見て調整しない
- 採用閾値は0.53/0.54/0.55/0.60の固定gridをdevelopmentで比較し、選択した値をconfirmationへ変更せず適用

単体実験は `walk_forward_extra_trees_001`、通常blendは `ensemble_extra_trees_25_001`、方向維持型blendは `extra_trees_confidence_blend_001`。

## 方向精度

| model | all accuracy | confirmation accuracy | Brier | log loss | ECE |
|---|---:|---:|---:|---:|---:|
| HGB baseline | 51.816% | 51.501% | 0.2494261 | 0.6919985 | 0.347% |
| Extra Trees | 51.773% | 51.292% | 0.2494140 | 0.6919738 | 0.430% |
| unrestricted 25% blend | 51.862% | 51.471% | 0.2493946 | 0.6919348 | 0.278% |

Extra Trees単体は全体・confirmationの方向精度が悪化した。通常blendは全体で+0.046ptだが、confirmationでは-0.030pt。HGBの誤りを直した2,224件に対し新規誤りが2,157件、McNemar exact p=0.319であり、方向モデルの置換根拠としては弱い。通常blendは方向候補として採用しない。

Extra TreesとHGBは12.00%の行で方向が異なり、通常blendがHGB方向を変えたのは3.02%。モデル多様性はあるが、その全てを方向変更へ使うのではなくconfidenceの強さへ利用する。

## 方向維持型confidence blend

HGB方向を固定し、blend確率のedgeだけをconfidenceへ使う。Extra TreesがHGBを0.5越しに否定した場合はconfidenceをほぼ0.50へ落とす。

| period | metric | baseline | candidate |
|---|---|---:|---:|
| 2020–2023 | Brier | 0.2493466 | 0.2493005 |
| 2020–2023 | log loss | 0.6918398 | 0.6917467 |
| 2020–2023 | ECE | 0.377% | 0.343% |
| 2024–2026途中 | Brier | 0.2495525 | 0.2495469 |
| 2024–2026途中 | log loss | 0.6922506 | 0.6922395 |
| 2024–2026途中 | ECE | 0.298% | 0.280% |
| all | Brier | 0.2494261 | 0.2493957 |
| all | log loss | 0.6919985 | 0.6919370 |
| all | ECE | 0.347% | 0.319% |

方向と全体accuracyはHGB baselineと完全同一。Brier、log loss、ECEはdevelopmentとconfirmationの両方で改善した。

## 採用条件

developmentで固定gridを比較すると、selection score最大はconfidence 0.53だった。この閾値を変更せずconfirmationへ適用した。

| period | model | rows | coverage | accuracy | Wilson lower | selection score |
|---|---|---:|---:|---:|---:|---:|
| 2020–2023 | baseline | 26,607 | 29.868% | 54.309% | 53.710% | 0.02027 |
| 2020–2023 | candidate | 26,170 | 29.377% | 54.467% | 53.863% | 0.02094 |
| 2024–2026途中 | baseline | 10,336 | 18.438% | 54.479% | 53.518% | 0.01511 |
| 2024–2026途中 | candidate | 10,173 | 18.148% | 54.664% | 53.695% | 0.01574 |
| all | baseline | 36,943 | 25.453% | 54.357% | 53.848% | 0.01942 |
| all | candidate | 36,343 | 25.040% | 54.522% | 54.010% | 0.02006 |

候補はcoverageを0.413pt減らす代わりにaccuracyを0.165pt上げ、selection scoreを3.35%改善した。年別ではaccuracyが7/7 fold、selection scoreが6/7 foldでbaselineを上回った。0.54と0.55はconfirmationでselection scoreが悪化したため採用しない。0.60はsupport不足。

## 判断

- Extra Trees単体と通常25% blendは方向モデルとして不採用。
- 方向維持型blend + confidence 0.53を `m15_extra_trees_confidence_blend_candidate_v1.json` の優先high-confidence candidateとして固定する。
- 現行方向、authoritative confidence、採用policy、paper売買policyはまだ変更しない。
- logistic confidence blendは純粋なECE候補として残し、Extra Trees blendはaccuracy/coverage採用laneとして分離する。
- 次の完全未使用期間でconfidence 0.53のaccuracy・selection score・Brierがすべてbaseline以上なら昇格を検討する。
- この実験は方向と信頼度の評価であり、損益を目的関数に含めていない。後続の損益診断を行う場合も損失倍率は標準の1.0だけを使う。
