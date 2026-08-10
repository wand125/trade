# 00065 Directional-clarity sample weighting

日時: 2026-08-10 19:06 JST

## 目的

Directional Clarityのhard filterは情報を捨て、signed continuous targetはbaselineを改善しても既存候補に届かなかった。方向0/1教師と全train行を維持し、明瞭な次足ほど損失への寄与だけを増やす方式を検証する。

## 実装と固定条件

- `--train-weighting directional_clarity` を追加した。
- raw weightは `0.5 + abs(next_bar_body) / next_bar_range`、範囲0.5〜1.5、最大比3倍。各trainで平均1へ正規化する。
- 次足rangeは教師重みにだけ使用し、feature manifest、calibration/test入力、latest推論へ渡さない。
- binary HGB、baseline 38加工特徴、後続Platt校正、expanding 7fold、25% blend、既存confidence gridを固定した。
- weight offset、非線形化、上限、blend weight、閾値は探索しない。

## 方向結果

| model | development accuracy | confirmation accuracy | all accuracy |
|---|---:|---:|---:|
| HGB baseline | 52.014% | 51.501% | 51.816% |
| Clarity Weighted単体 | 51.990% | 51.560% | 51.824% |
| baseline 75% + candidate 25% | 52.003% | 51.548% | 51.827% |

単体はdevelopment -22件、confirmation +33件、全期間+11件、paired p=0.932だった。通常blendもdevelopment -10件、confirmation +26件、全期間+16件、p=0.798。通常blendはaccuracy 5/7、Brier/log loss 6/7、ECE 5/7 fold改善したが、development方向が悪化し、既存Pressure/Volatility Shape方向候補より弱いため採用しない。

## 方向維持confidence 0.525

baseline方向を固定した25% probability blendについて、development gridは0.525を選んだ。

| period / candidate | accuracy | coverage | selection score |
|---|---:|---:|---:|
| development baseline | 53.858% | 37.908% | 0.02048 |
| development Clarity Weighted | 54.006% | 37.805% | 0.02135 |
| confirmation baseline | 53.777% | 26.375% | 0.01527 |
| confirmation Clarity Weighted | 53.944% | 25.827% | 0.01591 |
| all Clarity Weighted | 53.987% | 33.179% | 0.02040 |

baseline比ではaccuracy 5/7、score 4/7、Brier/log loss 6/7、ECE 4/7 fold改善した。しかしBalanced roleの既存候補を超えない。

| candidate | development acc / score | confirmation acc / score | all acc / score |
|---|---:|---:|---:|
| Clarity Weighted | 54.006% / 0.02135 | 53.944% / 0.01591 | 53.987% / 0.02040 |
| Signed-body Quantile champion | 54.078% / 0.02177 | 54.086% / 0.01689 | 54.080% / 0.02100 |
| Clear-body challenger | 54.173% / 0.02164 | 54.201% / 0.01675 | 54.182% / 0.02088 |

Signed-body Quantileにはaccuracy/score 3/7対4/7、選択集合Jaccard 90.2%。Clear-bodyには2/7対5/7だった。Signed-bodyはClarity Weightedを全期間のcoverage、accuracy、Wilson下限、selection scoreで同時に上回る。

UTC日20,000回paired bootstrapのClarity Weighted−Signed-body全期間差はaccuracy -0.093pt、95%区間-0.236〜+0.050pt、coverage -0.187ptで区間全体が負、selection score -0.000604、区間-0.001428〜+0.000227だった。Clarity Weighted優位確率はaccuracy 10.2%、score 7.5%。全期間Brier/log lossは実質同値で優位確率49%前後だった。

## 判断

方向明瞭度の固定sample weightingはbaseline confidenceをdevelopment/confirmationで改善したが、hard filter、連続回帰と同様に既存候補へ増分edgeを加えないため採用しない。

- `train_weighting=directional_clarity` とartifact/latest経路は再現用に残す。
- candidate config、registry entry、latest artifactは発行しない。
- Signed-body Quantile/Clear-body 0.525と既存方向候補を維持する。
- weight式、blend weight、confidence閾値を同じ履歴へ合わせて再探索しない。

主要成果物:

- `experiments/next_bar/walk_forward_directional_clarity_weighted_001`
- `experiments/next_bar/directional_clarity_weighted_candidate_analysis.json`
- `experiments/next_bar/directional_clarity_weighted_vs_signed_body_quantile_m15_0525_analysis.json`
- `experiments/next_bar/directional_clarity_weighted_vs_clear_body_m15_0525_analysis.json`
- `experiments/next_bar/directional_clarity_weighted_vs_signed_body_quantile_m15_0525_daily_bootstrap.json`
