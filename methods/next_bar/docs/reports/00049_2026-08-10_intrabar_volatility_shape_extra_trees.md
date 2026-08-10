# 00049 Intrabar volatility shape with Extra Trees

日時: 2026-08-10 16:25 JST

## 目的

M15で方向edgeがあったVolatility Shapeを、HGBとは異なるランダム分割型Extra Treesで学ぶ。加工なしExtra Treesとの差から特徴寄与を、HGB Shapeとの差から学習器寄与を切り分け、正式baselineとの方向blendおよびconfidenceに採用価値があるか検証する。

## 固定条件

既存Extra Trees confidence候補と同じ200 trees、max depth 12、min samples leaf 50、max features 0.75、seed 42を使った。feature setだけをbaseline 38特徴から `intrabar_volatility_shape` 79特徴へ変更した。Platt校正、M15 7fold、正式HGB baseline 75% + candidate 25%、方向維持confidence、閾値gridは既存手順のままで、結果後にtree parameterやweightを変更していない。

## Extra Trees内の特徴増分

| period | baseline-feature Extra Trees | Shape Extra Trees |
|---|---:|---:|
| development | 52.076% | 52.288% |
| confirmation | 51.292% | 51.303% |
| all | 51.773% | 51.908% |

Shape特徴はExtra Trees内でaccuracyを5/7 fold改善し、全体純改善195件、paired p=0.0703だった。developmentはp=0.0272、confirmationは純改善6件、p=0.939である。無符号形状特徴が別学習器でも一定の情報を持つことは再現した。

一方、Brier/log loss改善は各3/7 foldで、confirmation確率品質は悪化した。HGB Shape単体との比較でもdevelopmentはほぼ同じだが、confirmation 51.583%対51.303%、全体52.008%対51.908%でExtra Trees版が下回り、paired純改善-145件だった。HGB Shape方向候補を置換しない。

## 正式baselineとの方向比較

Shape Extra Trees単体は正式baselineに対しdevelopment 52.014%から52.288%へ上がる一方、confirmationは51.501%から51.303%へ悪化した。accuracy改善4/7、全体p=0.347である。

正式baseline 75% + Shape Extra Trees 25%もdevelopment 52.014%から52.099%へ改善したが、confirmationは51.501%から51.453%へ悪化した。accuracy 5/7、Brier/log loss 6/7だが、確認期間方向gateを満たさないため方向用途には採用しない。

## Confidence

development gridは0.525を選び、baseline比ではdevelopment/confirmationのaccuracy・selection scoreを改善した。全体scoreは0.01961から0.02037、confirmationは0.01527から0.01590で、Brier/log loss/ECEは各6/7 fold改善した。ただしlane accuracy・score改善は4/7で、2023、2025、2026途中が悪化した。

特徴増分を同じExtra Trees学習器で直接比較すると、結果は逆だった。

| threshold | period | baseline-feature Extra Trees score | Shape Extra Trees score |
|---|---|---:|---:|
| 0.525 | development | 0.02157 | 0.02131 |
| 0.525 | confirmation | 0.01613 | 0.01590 |
| 0.525 | all | 0.02061 | 0.02037 |
| 0.530 | development | 0.02094 | 0.02042 |
| 0.530 | confirmation | 0.01574 | 0.01528 |
| 0.530 | all | 0.02006 | 0.01957 |

0.525では既存Extra Treesがaccuracy・score各5/7、0.53では各6/7 fold勝った。選択集合は約92%重複する。Shape版はaggregate Brier/log loss/ECEを改善するが、高信頼境界のaccuracy/coverage評価関数を悪化させるため、既存Extra Trees 0.53候補を維持する。

## 成果物と判断

- OOS単体: `experiments/next_bar/walk_forward_intrabar_volatility_shape_extra_trees_m15_001`
- 通常25% blend: `experiments/next_bar/ensemble_intrabar_volatility_shape_extra_trees_m15_25_001`
- 方向維持confidence: `experiments/next_bar/intrabar_volatility_shape_extra_trees_m15_confidence_blend_001`
- baseline分析: `experiments/next_bar/intrabar_volatility_shape_extra_trees_m15_candidate_analysis.json`
- Extra Trees親方向比較: `experiments/next_bar/intrabar_volatility_shape_extra_trees_vs_extra_trees_m15_direction_analysis.json`
- HGB Shape方向比較: `experiments/next_bar/intrabar_volatility_shape_extra_trees_vs_hgb_m15_direction_analysis.json`
- Extra Trees 0.525/0.53比較: `experiments/next_bar/extra_trees_vs_intrabar_volatility_shape_extra_trees_m15_0525_analysis.json`, `experiments/next_bar/extra_trees_vs_intrabar_volatility_shape_extra_trees_m15_053_analysis.json`

方向・confidenceとも不採用とし、再現成果物だけを残す。M15 HGB Shape単体方向候補とbaseline-feature Extra Trees 0.53 confidence候補を維持する。同じ履歴でExtra Trees parameter、Shape subset、blend weight、閾値を再探索しない。損失倍率は標準1.0のみとする。
