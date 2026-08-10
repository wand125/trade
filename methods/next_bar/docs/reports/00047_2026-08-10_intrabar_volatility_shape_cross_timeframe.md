# 00047 Intrabar volatility shape cross-timeframe

日時: 2026-08-10 16:05 JST

## 目的

M15で方向候補になった `intrabar_volatility_shape` を、特徴定義・HGB/Platt設定・7fold境界・25% blend weight・confidence閾値gridを変えずM5/M30へ移植する。時間足ごとに方向、確率品質、高信頼laneを独立評価し、既存Profile/Pressure候補に対する増分がある場合だけ採用する。

## データ整列

既存正式baselineと同じM5 439,881行、M30 71,260行、test2020〜test2026_partialを使った。fold、timestamp、targetの完全整列はensemble/analyzer入力guardで検証した。完成した各上位足内の完成済みM1だけを使い、raw価格水準とvolumeは入力しない。

## M5方向

| period | baseline | Shape single | baseline 75% + Shape 25% |
|---|---:|---:|---:|
| development | 51.879% | 51.970% | 51.916% |
| confirmation | 51.041% | 50.988% | 51.030% |
| all | 51.556% | 51.592% | 51.575% |

単体と通常blendはdevelopmentで改善したがconfirmationで反転した。単体の全体純改善155件、p=0.441、通常blendは純改善81件、p=0.426で、accuracy改善はいずれも4/7 foldだった。通常blendのBrier/log lossは7/7、ECEは6/7 fold改善したが、方向accuracyの確認期間gateを満たさない。

既存Pressure 25%方向blendとの直接比較ではShape blendがdevelopment、confirmation、allのaccuracyをすべて下回り、accuracy勝敗3/7、純改善-55件、p=0.537だった。M5方向候補には採用しない。

## M5 confidence

development gridは0.515を選んだ。baseline比でdevelopment selection scoreは0.01913から0.01921へ僅かに改善したが、confirmationはaccuracy 52.355%から52.321%、coverage 37.242%から36.796%、score 0.01199から0.01170へすべて悪化した。

同じ0.515の既存Profileと直接比較すると、Shapeはdevelopment/confirmation/allのaccuracy・scoreをすべて下回り、fold勝敗は1/7対6/7、selection Jaccardは約95%だった。proper score改善は再現したが、選別境界を悪化させる重複候補なのでconfidence registryへ追加しない。

## M30方向

| period | baseline | Shape single | baseline 75% + Shape 25% |
|---|---:|---:|---:|
| development | 51.990% | 51.682% | 51.974% |
| confirmation | 51.520% | 51.386% | 51.495% |
| all | 51.807% | 51.567% | 51.788% |

単体はdevelopment/confirmationとも悪化し、accuracy改善2/7、純改善-171件、p=0.140だった。通常blendも両期間で悪化し、純改善-14件、p=0.815である。Brier/log lossは通常blendで6/7 fold改善したが、方向用途には採用しない。

## M30 confidence

development gridは0.52を選んだ。developmentではaccuracy 53.415%から53.663%、score 0.01724から0.01821へ改善した。confirmation accuracyも53.636%から53.660%へ僅かに上がったが、coverageが31.268%から29.880%へ低下し、scoreは0.01445から0.01412へ悪化した。

既存Pressure 0.52との直接比較ではShapeがdevelopment/confirmation/allのaccuracy・coverage・scoreをすべて下回り、fold勝敗は2/7対5/7だった。Profile 0.52に対してはaccuracy勝敗5/7だがscore勝敗2/7で、confirmation scoreはProfile 0.01634に対しShape 0.01412と大きく低い。M30 confidence候補にも採用しない。

## 成果物と判断

- M5/M30単体OOS: `experiments/next_bar/walk_forward_intrabar_volatility_shape_m5_m30_001`
- M5通常blend/confidence: `experiments/next_bar/ensemble_intrabar_volatility_shape_m5_25_001`, `experiments/next_bar/intrabar_volatility_shape_m5_confidence_blend_001`
- M30通常blend/confidence: `experiments/next_bar/ensemble_intrabar_volatility_shape_m30_25_001`, `experiments/next_bar/intrabar_volatility_shape_m30_confidence_blend_001`
- M5分析: `experiments/next_bar/intrabar_volatility_shape_m5_candidate_analysis.json`
- M30分析: `experiments/next_bar/intrabar_volatility_shape_m30_candidate_analysis.json`
- M5 Profile比較: `experiments/next_bar/intrabar_profile_vs_volatility_shape_m5_0515_analysis.json`
- M30 Pressure/Profile比較: `experiments/next_bar/intrabar_pressure_vs_volatility_shape_m30_052_analysis.json`, `experiments/next_bar/intrabar_profile_vs_volatility_shape_m30_052_analysis.json`

M5/M30は方向・confidenceとも不採用とし、再現成果物だけを残す。M15 Shape単体方向候補、M5 Profile 0.515、M5 Pressure方向blend、M30 Pressure 0.52の既存候補を維持する。同じ履歴で時間足別特徴subset、top本数、segment、blend weight、閾値を再探索しない。損失倍率は標準1.0のみとする。
