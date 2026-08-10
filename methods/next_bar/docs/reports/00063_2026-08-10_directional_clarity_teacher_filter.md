# 00063 Directional-clarity teacher filter

日時: 2026-08-10 18:43 JST

## 目的

次足実体/ATRが大きい教師を残すClear-bodyとは別に、次足の実体がhigh-low rangeをどれだけ占めるかを教師品質に使う。長いwickを含む方向の曖昧な足を除外し、次足up/downまたはconfidence rankingが改善するか検証する。

## 実装と固定条件

- 教師専用列 `next_bar_directional_clarity = abs(next close - next open) / (next high - next low)` を追加した。値は0〜1へ制限する。
- `--train-target-filter body_range_upper_half` は各foldのtrain内中央値以上だけをHGB学習へ使う。calibration/testは全件を残す。
- 境界はtest2020〜2026途中で0.4558〜0.4571、保持行は各foldで約50%。未来足の値は教師選択だけに使い、feature manifest、校正入力、最新推論へ渡さない。
- baseline 38加工特徴、HGB、後続Platt校正、25% blend、閾値gridは既存比較と同一。追加parameter searchは行わない。
- expanding train、直後1年calibration、次の1年testの正しい7fold境界を成果物から再監査した。初回の境界指定不整合による試行結果は上書きし、判断に使っていない。

## 方向結果

| model | development accuracy | confirmation accuracy | all accuracy |
|---|---:|---:|---:|
| HGB baseline | 52.014% | 51.501% | 51.816% |
| Directional Clarity単体 | 51.902% | 51.312% | 51.674% |
| baseline 75% + candidate 25% | 52.009% | 51.492% | 51.809% |

単体は全期間でbaselineより206件悪化、paired p=0.137、accuracy改善2/7 foldだった。通常25% blendも純改善-10件、p=0.897で、方向用途には採用しない。通常blendのBrier/log lossは7/7 fold改善したが、方向正答率の改善には結び付かなかった。

## 方向維持confidence

baseline方向を固定した25% probability blendでは、Brier/log lossが7/7、ECEが6/7 fold改善した。development gridが選んだ閾値は0.53である。

| period / candidate | accuracy | coverage | selection score |
|---|---:|---:|---:|
| development baseline | 54.309% | 29.868% | 0.02027 |
| development Directional Clarity | 54.617% | 29.457% | 0.02178 |
| confirmation baseline | 54.479% | 18.438% | 0.01511 |
| confirmation Directional Clarity | 54.310% | 18.233% | 0.01427 |
| all Directional Clarity | 54.531% | 25.122% | 0.02014 |

developmentの改善はconfirmationでaccuracy、coverage、selection scoreすべて反転した。Selective roleの既存候補と0.53で直接比較した。

| candidate | development acc / score | confirmation acc / score | all acc / score |
|---|---:|---:|---:|
| Directional Clarity | 54.617% / 0.02178 | 54.310% / 0.01427 | 54.531% / 0.02014 |
| Distribution Shape champion | 54.575% / 0.02141 | 54.551% / 0.01512 | 54.568% / 0.02018 |
| Extra Trees challenger | 54.467% / 0.02094 | 54.664% / 0.01574 | 54.522% / 0.02006 |

Directional Clarityはdevelopmentで2候補を上回るが、confirmationでは両方を下回った。Distributionとの年別accuracy/scoreは3/7対4/7、選択集合Jaccardは全体84.1%。Extra Treesとも3/7対4/7だった。0.525のBalanced比較でもSigned-body Quantileにaccuracy 3/7、score 2/7、Clear-bodyにaccuracy 3/7、score 4/7で、置換根拠はない。

UTC日20,000回paired bootstrapのDirectional Clarity−Distribution全期間差はaccuracy -0.038pt、95%区間-0.253〜+0.180pt、selection score -0.000032、区間-0.001108〜+0.001059だった。Directional Clarity優位確率はaccuracy 36.7%、score 47.8%。Brier/log lossは点推定で改善し優位確率94%台だが、95%区間は僅かに0を跨いだ。

## 判断

Directional Clarityはconfidenceのproper score改善に利用価値を示したが、採用評価関数がdevelopmentからconfirmationへ再現せず、Selective champion/challengerを置換しない。

- `body_range_upper_half` と教師専用列は再現用に残す。
- candidate config、registry entry、latest artifactは発行しない。
- Distribution Shape 0.53 championとExtra Trees 0.53 challengerを維持する。
- clarity cutoff、保持率、body/ATRとの合成、blend weight、confidence閾値を同じ履歴へ合わせて再探索しない。

主要成果物:

- `experiments/next_bar/walk_forward_body_range_upper_half_m15_001`
- `experiments/next_bar/body_range_upper_half_m15_candidate_analysis.json`
- `experiments/next_bar/body_range_upper_half_vs_distribution_shape_m15_053_analysis.json`
- `experiments/next_bar/body_range_upper_half_vs_extra_trees_m15_053_analysis.json`
- `experiments/next_bar/body_range_upper_half_vs_distribution_shape_m15_053_daily_bootstrap.json`
