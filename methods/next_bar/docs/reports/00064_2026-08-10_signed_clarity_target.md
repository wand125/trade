# 00064 Signed directional-clarity target

日時: 2026-08-10 18:58 JST

## 目的

Directional Clarityのhard filterは半数の教師を捨て、developmentのconfidence改善がconfirmationで反転した。全教師を残したまま、次足方向と足自体の明瞭さを単一の連続教師へ加工すると、方向またはconfidence rankingが改善するか検証する。

## 実装と固定条件

- `--model-type signed_clarity_hgb` を追加した。
- 教師は `sign(next_bar_body) * abs(next_bar_body) / next_bar_range`、すなわち `next_bar_body / next_bar_range`。範囲は−1〜+1で、0に近いほどwickの多い曖昧な次足を表す。
- 全train行を二乗誤差HGB回帰へ使い、raw回帰scoreをsigmoidへ通した後、後続calibration期間だけでPlatt校正する。
- 次足rangeは教師だけに使い、feature manifest、calibration/test入力、latest推論へ渡さない。
- baseline 38加工特徴、HGB parameter、expanding 7fold、25% blend、confidence閾値gridを固定し、target式やscaleを探索しない。

## 方向結果

| model | development accuracy | confirmation accuracy | all accuracy |
|---|---:|---:|---:|
| HGB baseline | 52.014% | 51.501% | 51.816% |
| Signed Clarity単体 | 51.990% | 51.537% | 51.815% |
| baseline 75% + candidate 25% | 52.059% | 51.537% | 51.858% |

単体は全期間でbaselineとほぼ同じ−2件、paired p=0.994だった。通常25% blendはdevelopment +40件、confirmation +20件、全期間+60件、p=0.349で、accuracy 4/7、Brier/log loss 6/7 fold改善した。

ただし既存方向候補へ直接比較すると、Pressure 25% blendにaccuracy 2/7対5/7で、development/confirmation/allおよびBrier/log lossすべて負けた。Volatility Shape単体にもaccuracy 2/7対5/7、全期間52.008%対51.858%で負けた。既存候補へ追加する増分edgeはない。

## 方向維持confidence 0.525

baseline方向を固定した25% blendについて、development gridは0.525を選んだ。

| period / candidate | accuracy | coverage | selection score |
|---|---:|---:|---:|
| development baseline | 53.858% | 37.908% | 0.02048 |
| development Signed Clarity | 54.086% | 37.201% | 0.02164 |
| confirmation baseline | 53.777% | 26.375% | 0.01527 |
| confirmation Signed Clarity | 53.931% | 25.460% | 0.01570 |
| all Signed Clarity | 54.039% | 32.666% | 0.02052 |

baseline比ではaccuracy/score 6/7、Brier/log loss 6/7、ECE 5/7 fold改善した。hard filterと異なりconfirmationにも再現したが、Balanced roleの既存候補を超えなかった。

| candidate | development acc / score | confirmation acc / score | all acc / score |
|---|---:|---:|---:|
| Signed Clarity | 54.086% / 0.02164 | 53.931% / 0.01570 | 54.039% / 0.02052 |
| Signed-body Quantile champion | 54.078% / 0.02177 | 54.086% / 0.01689 | 54.080% / 0.02100 |
| Clear-body challenger | 54.173% / 0.02164 | 54.201% / 0.01675 | 54.182% / 0.02088 |

Signed-body QuantileはSigned Clarityをcoverage・全期間accuracy・selection scoreで同時に上回り、年別accuracy/scoreも4/7対3/7だった。Clear-bodyにはaccuracy/score各1/7対6/7。選択集合JaccardはSigned-body 89.4%、Clear-body 86.6%である。

UTC日20,000回paired bootstrapのSigned Clarity−Signed-body全期間差はaccuracy -0.041pt、95%区間-0.194〜+0.114pt、coverage -0.700ptで区間全体が負、selection score -0.000484、区間-0.001363〜+0.000408だった。Signed Clarity優位確率はaccuracy 30.4%、score 14.7%。Brier/log lossは点推定で改善したが、優位確率78%台で区間は0を跨いだ。

## 判断

Signed Clarityはhard filteringより有効で、baselineの方向blendと0.525 confidenceをdevelopment/confirmationの両方で改善した。しかし方向・Balanced confidenceとも既存候補に支配されるため採用しない。

- `model_type=signed_clarity_hgb` とartifact/latest経路は再現用に残す。
- candidate config、registry entry、latest artifactは発行しない。
- 方向はVolatility Shape単体とPressure 25% blend、Balanced confidenceはSigned-body Quantile 0.525とClear-body 0.525を維持する。
- targetの非線形化、loss、blend weight、confidence閾値を同じ履歴へ合わせて再探索しない。

主要成果物:

- `experiments/next_bar/walk_forward_signed_clarity_hgb_001`
- `experiments/next_bar/signed_clarity_hgb_candidate_analysis.json`
- `experiments/next_bar/signed_clarity_vs_signed_body_quantile_m15_0525_analysis.json`
- `experiments/next_bar/signed_clarity_vs_clear_body_m15_0525_analysis.json`
- `experiments/next_bar/signed_clarity_vs_pressure_m15_direction_analysis.json`
- `experiments/next_bar/signed_clarity_vs_volatility_shape_m15_direction_analysis.json`
- `experiments/next_bar/signed_clarity_vs_signed_body_quantile_m15_0525_daily_bootstrap.json`
