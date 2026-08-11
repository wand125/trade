# 00114 M30 Extra Trees Fixed Transfer

日時: 2026-08-11 14:51 JST

## 目的

加工済みbaseline 38特徴、教師、時系列分割を変えず、M1で方向blendの安定性が確認された固定Extra Treesを未検証のM30へ移植した。HGB/LightGBMと異なるランダム化木の誤差が、M30方向精度、確率品質、高信頼度選別を補完するかを確認する。

## 固定仕様と品質

Extra Trees 200本、max depth 12、min leaf 50、max features 0.75、seed 42、expanding training、uniform sample、全教師、後続calibration期間のPlattを固定した。特徴は生OHLC価格水準を含まないbaseline 38列であり、標準損失1.0を使用した。M1/M15実験からparameterを変更せず、M30履歴でtree数、depth、leaf、feature比、blend weight、confidence閾値を探索していない。

test2020〜test2026途中の固定7fold、71,260 OOS行で正式baselineとtimestamp/targetを完全整列した。保存済み最終fold artifactから2026-06-01 04:30 UTCを再推論し、up、probability up 52.7875%を確認した。経験的オッズ検証はないため `odds_valid=false` である。

## 単体と固定25% blend

| model | development accuracy | confirmation accuracy | all accuracy | all Brier | all log loss | all ECE |
|---|---:|---:|---:|---:|---:|---:|
| HGB baseline | 51.98972% | 51.52019% | 51.80747% | 0.249497879 | 0.692142533 | 0.16084% |
| Extra Trees単体 | 52.07688% | 51.64311% | 51.90850% | 0.249386230 | 0.691919030 | 0.20227% |
| baseline 75% + Extra Trees 25% | 52.12505% | 51.53465% | 51.89587% | 0.249432516 | 0.692011167 | 0.05832% |

単体はbaseline比development +38件、confirmation +34件、all +72件で、accuracy 4/7、Brier/log loss 5/7foldだった。通常25% blendはdevelopment +59件、confirmation +4件、all +63件、accuracy 4/7、Brier/log loss 6/7fold。blendは校正点値に強い一方、confirmation方向の増分が4件しかなく、現行co-challengerにも劣るため採用しない。

Extra Trees単体−baselineのUTC日paired bootstrap 20,000回では、all accuracy差+0.1010ptの95%区間は-0.1922〜+0.3958pt、改善確率74.54%で未確定だった。一方、Brier差区間-0.00021967〜-0.00000259、log loss差-0.00044086〜-0.00000418は改善を支持した。ECEはbaselineより悪く、確率品質の改善を局所校正まで一般化しない。

## 現行方向候補との比較

現行co-challengerはbaseline 75% + Pressure 6.25% + Ordinal Motif 6.25% + LightGBM 12.5%である。

| period | current co-challenger | Extra Trees単体 | Extra Trees差 |
|---|---:|---:|---:|
| development | 52.02642% | 52.07688% | +22件 |
| confirmation | 51.65395% | 51.64311% | -3件 |
| all | 51.88184% | 51.90850% | +19件 |

Extra Trees単体はaccuracy 4/7fold対3/7で、all Brier/log loss点値も良かった。しかしall accuracy差+0.0267ptの95%区間は-0.2589〜+0.3057pt、Brier/log loss差も0を跨いだ。confirmationで3件負けているため、現行候補の置換根拠にはしない。

現行候補とExtra Trees通常blendの固定50/50平均も探索なしで確認した。実効weightはbaseline 75%、Pressure 3.125%、Ordinal 3.125%、LightGBM 6.25%、Extra Trees 12.5%である。developmentは改善したがconfirmationは51.65395%→51.58888%、allは僅か1件改善だけで、年別2/7foldだった。4学習要素へ複雑化する根拠がないため棄却する。

## confidence

development grid最良0.515はaccuracy 53.2300%、score 0.018790でbaselineを上回ったが、confirmationは53.2325%対baseline 53.2977%、score 0.015311対0.015815へ反転したため棄却した。

方向維持0.55はall 4,642件、coverage 6.5142%、accuracy 55.7949%、score 0.011133だった。既存Pressure + AR shadowは4,412件、coverage 6.1914%、accuracy 56.1423%、score 0.011629であり、Extra Treesはaccuracy/scoreとも3/7fold対4/7だった。confirmationの点accuracyだけを理由に置換せず、confidence、fair odds、policyへ使わない。

## 判断

通常25% blend、0.515/0.55 confidence、現行候補との固定平均は再現専用とする。parameter、weight、thresholdを同じM30履歴へ合わせて再探索しない。authoritative方向/confidence、現行Pressure + Ordinal + LightGBM co-challenger、Pressure + AR confidence shadow、fair odds、adoption/paper/live policyは変更しない。

Extra Trees単体だけを `m30_extra_trees_direction_challenger_v1.json` のparallel standalone direction challengerへ固定する。baselineに対する開発・確認の点accuracyと全期間proper scoreが改善し、Brier/log lossは日次bootstrapでも支持されたが、accuracy差と現行候補への直接差は未確定でECEも悪化した。役割は異種学習器の確率品質検証であり、完全未使用期間でbaselineと現行co-challengerへhead-to-headする。

## 成果物

- Extra Trees OOS: `experiments/next_bar/walk_forward_extra_trees_m30_fixed_001`
- normal/confidence blends: `experiments/next_bar/extra_trees_m30_*_fixed_001`
- candidate分析: `experiments/next_bar/extra_trees_m30_candidate_analysis.json`
- baseline比較/bootstrap: `experiments/next_bar/extra_trees_single_vs_baseline_m30_direction_*`
- current co-challenger比較/bootstrap: `experiments/next_bar/extra_trees_single_vs_pressure_ordinal_lightgbm_m30_direction_*`
- rejected structured average: `experiments/next_bar/pressure_ordinal_lightgbm_extra*`
- rejected confidence: `experiments/next_bar/extra_trees_vs_pressure_ar_equal_m30_fixed_055.json`
- latest artifact check: `experiments/next_bar/extra_trees_m30_latest_prediction.json`
- fixed config: `methods/next_bar/config/m30_extra_trees_direction_challenger_v1.json`
