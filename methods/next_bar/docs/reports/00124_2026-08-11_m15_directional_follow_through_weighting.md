# 00124 M15 Directional Follow-through Sample Weighting

日時: 2026-08-11 17:14 JST

## 目的

M30で高信頼度shadow、M5で0.55 shadowとなったDirectional Follow-through教師重みを、式、学習器、blend比率を変えずM15へ移植した。M15にはcoverage帯別の既存championがあるため、baselineだけでなくPressure方向、Directional-Clarity、Profile 0.515、Signed-body Quantile 0.525、Full Path 0.53、Structure 0.55へ直接比較した。

## 固定仕様と品質

解決済みtrain次足だけで `clarity = abs(close - open) / (high - low)` と方向側close到達度を計算し、積を0〜1へ制限した。raw sample weightは `0.5 + clarity * direction_aligned_close_location`、範囲0.5〜1.5、sampled train内平均1である。次足OHLCはtrain sample weight以外へ渡さず、入力特徴、calibration、test、latest推論には使わない。

baseline加工38特徴、HGB 200 iteration、31 leaves、learning rate 0.05、min leaf 100、L2 1、seed 42、expanding、最大train 750,000行、Platt、全教師、標準損失1.0を固定した。test2020〜test2026途中の7fold、145,140 OOS行を既存候補とtimestamp/targetで完全整列した。M15用の教師式、model parameter、25%/50%比率、confidence閾値を結果に合わせて再探索していない。

保存artifactのlatest推論は2026-06-01 04:30 UTCから次M15をup、probability up 55.4165%とした。経験的校正を接続していないため `odds_valid=false` である。

## 単体と方向用途

| model | development accuracy | confirmation accuracy | all accuracy | all Brier | all log loss | all ECE |
|---|---:|---:|---:|---:|---:|---:|
| HGB baseline | 52.0144% | 51.5012% | 51.8162% | 0.249426100 | 0.691998452 | 0.3467% |
| Follow-through weighted単体 | 51.9414% | 51.4762% | 51.7617% | 0.249401586 | 0.691947981 | 0.4644% |
| baseline 75% + Follow-through 25% | 51.9987% | 51.4298% | 51.7790% | 0.249402012 | 0.691949686 | 0.3778% |

単体はbaseline比development -65件、confirmation -14件、all -79件、accuracy 3/7foldだった。通常25% blendも-14/-40/-54件、accuracy 0/7fold、McNemar exact p=0.373で、方向正答率を改善しない。通常blendのBrier/log lossは7/7fold改善し、日次bootstrapもdevelopment/allの改善を支持したが、方向を当てるedgeではなく確率平滑化である。

通常blendは現行Pressure方向候補にdevelopment -65件、confirmation -76件、all -141件、accuracy 1/7対6/7だった。PressureとFollow-through単体の固定50/50平均もparent比-66/-40/-106件、accuracy 2/7対5/7である。Follow-through単体はDirectional-Clarity単体にも-43/-47/-90件、3/7対4/7で、相対形状教師を方向側close到達度で狭める増分はM15で再現しなかった。

## Confidence role比較

baseline方向を維持した25% confidenceはdevelopment gridで0.53を選んだ。baseline比ではdevelopment accuracy +0.1954pt、score +0.001054、confirmation accuracy +0.0084pt、score -0.000023、all accuracy +0.1431pt、score +0.000693だった。Brier/log lossは7/7fold改善した。

日次bootstrapではdevelopmentのaccuracy・scoreと3期間のproper score改善を支持したが、confirmation/allのaccuracy・score区間は0を跨いだ。0.53 laneのall accuracy 54.4998%に対しmean confidence 54.6705%、confirmationは54.4879%対54.1456%で、ともにWilson区間内かつedge確認済みだった。

各role championとの直接比較は次の通り。

| threshold / role | Follow-through all coverage / accuracy / score | champion all coverage / accuracy / score | accuracy / score fold勝敗 |
|---|---:|---:|---:|
| 0.515 broad / Profile | 55.2942% / 52.8597% / 0.018695 | 54.8967% / 53.0555% / 0.020070 | 1/7 / 1/7 |
| 0.525 balanced / Signed-body Quantile | 33.4863% / 53.8743% / 0.019853 | 33.3664% / 54.0803% / 0.021004 | 0/7 / 0/7 |
| 0.53 selective / Full Path | 25.3865% / 54.4998% / 0.020108 | 24.9773% / 54.6673% / 0.020763 | 3/7 / 3/7 |
| 0.55 precision / Structure | 7.9130% / 55.4375% / 0.012734 | 7.8814% / 56.0101% / 0.014314 | 1/7 / 1/7 |

Full Path 0.53との日次bootstrapでは、confirmation accuracy差-0.4173ptの95%区間が-0.7678〜-0.0744ptでFull Path優位だった。all Brier差区間+0.00001253〜+0.00004599、log loss +0.00002510〜+0.00009221もFollow-through確率の悪化を示した。Follow-throughはcoverageを0.4093pt増やすが、精度とqualityを落とした。

Full Path confidenceとFollow-through confidenceの固定50/50平均も、0.53でparent比development/confirmation/allのscoreを全て下げ、score 2/7対5/7だった。既存championへの多様化成分としても採用しない。

## 高信頼度の校正

Follow-through 0.55はall 11,485件、coverage 7.9130%、accuracy 55.4375%、mean confidence 56.5524%で1.1149pt過信し、Wilson上限56.3446%も超えた。confirmationは1,818件で局所整合したが、Structureはaccuracy 56.4368%対55.5556%、score 0.007215対0.005874だった。高閾値の点精度を理由にshadowを追加しない。

## 判断

M15 Directional Follow-throughは単体、通常25%方向blend、方向維持confidence、Pressure/Full Pathとの固定50/50平均を全て再現専用とする。新しいdirection/config/registry/shadow/latest runtime/fair odds/policyは発行しない。

教師品質を方向側close到達度まで狭める処理はM30/M5の0.55選別には一部有効だったが、M15ではDirectional-Clarity方向、全confidence role champion、局所確率品質のいずれも上積みしなかった。時間足ごとの独立性を維持し、M15はPressure方向とProfile/Quantile/Full Path/Structureの既存候補を継続する。

## 成果物

- implementation: `src/trade_data/next_bar.py`
- tests: `tests/test_next_bar.py`
- OOS/latest: `experiments/next_bar/walk_forward_directional_follow_through_weighted_m15_fixed_001`, `experiments/next_bar/directional_follow_through_weighted_m15_latest_prediction.json`
- normal/confidence blends and analysis: `experiments/next_bar/directional_follow_through_weighted_m15_*`
- direction and Clarity comparisons: `experiments/next_bar/directional_follow_through_m15_direction_vs_pressure.json`, `experiments/next_bar/directional_follow_through_m15_single_vs_clarity*`
- role comparisons/bootstrap/reliability: `experiments/next_bar/directional_follow_through_m15_vs_*`
- fixed diversification: `experiments/next_bar/pressure_directional_follow_through_equal_m15_*`, `experiments/next_bar/full_path_directional_follow_through_equal_m15_*`
