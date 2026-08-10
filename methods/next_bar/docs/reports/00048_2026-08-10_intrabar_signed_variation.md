# 00048 Intrabar signed variation

日時: 2026-08-10 16:14 JST

## 目的

M15 Intrabar Volatility Shapeが捉えた無符号の値幅・分散形状へ、上昇／下降の符号とjump／continuous分解を加える。親Shapeに対する増分方向edgeと、既存0.525 confidence候補を上回る選別能力があるかを検証する。

## 結果前に固定した特徴

`--feature-set intrabar_signed_variation` はVolatility Shapeへ14特徴を追加する。

- upside/downside semivariance構成比、不均衡、二値entropy。
- 方向別分散の最大集中度と時間重心、両重心の差。
- bipower variation / realized variance、非負jump fraction。
- 最大絶対returnの符号付き分散構成比。
- 最大returnを除いたcontinuous semivariance不均衡。
- 終盤1/3と序盤1/3のsemivariance不均衡差。

完成済みM1 close-to-close log returnだけを使い、各完成M15内のrealized varianceで正規化する。raw価格水準とvolumeは使わない。OHLCの10倍scale不変、未来M1改変が過去特徴へ影響しない、flat足で有限な意味的ゼロ、構成比恒等式、entropy/jump範囲、55 intrabar特徴、artifact/latest推論をテストした。

HGB、Platt、M15 7fold、25% blend、confidence gridは既存条件を変えず、結果後に特徴subsetや閾値を調整していない。

## 単体方向

| period | baseline | Signed Variation single |
|---|---:|---:|
| development | 52.014% | 52.197% |
| confirmation | 51.501% | 51.560% |
| all | 51.816% | 51.951% |

development/confirmationともbaselineを上回ったがaccuracy改善は4/7 fold、全体fixes 10,345件、harms 10,149件、純改善196件、paired p=0.173だった。

親Volatility Shape単体との直接比較では、development 52.275%対52.197%、confirmation 51.583%対51.560%、全体52.008%対51.951%とすべて下回った。accuracy/proper score勝敗も各2/7、純改善-82件、p=0.488である。符号特徴はbaselineより有効でも、親Shapeへ追加すると方向境界を悪化させるため方向候補には採用しない。

## 通常25% blend

development accuracyは52.014%から52.056%へ改善したが、confirmationは51.501%から51.469%へ悪化した。全体純改善19件、p=0.801、accuracy改善3/7 foldである。Brier/log lossは6/7 fold改善したが方向用途には使わない。

## Confidence

development gridは0.525を選んだ。

| period | baseline score | Signed Variation score | baseline accuracy | candidate accuracy |
|---|---:|---:|---:|---:|
| development | 0.02048 | 0.02131 | 53.858% | 54.036% |
| confirmation | 0.01527 | 0.01533 | 53.777% | 53.798% |
| all | 0.01961 | 0.02017 | 53.834% | 53.963% |

accuracy・scoreは5/7、Brier/log lossは6/7、ECEは5/7 fold改善した。ただし改善年は2020〜2024へ偏り、2025と2026途中はaccuracy・scoreがともに悪化した。

同じ0.525で親Shapeと比べるとSigned Variationはaccuracy 4/7、score 3/7。ProfileおよびPressureにもaccuracy 4/7、score 3/7で、confirmation scoreは両者より低い。既存中coverage候補との比較はさらに明確だった。

| candidate | all accuracy | all score | confirmation accuracy | confirmation score |
|---|---:|---:|---:|---:|
| clear-body 0.525 | 54.182% | 0.02088 | 54.201% | 0.01675 |
| signed-body quantile 0.525 | 54.080% | 0.02100 | 54.086% | 0.01689 |
| Signed Variation 0.525 | 53.963% | 0.02017 | 53.798% | 0.01533 |

clear-bodyにaccuracy 1/7・score 2/7、signed-body quantileにaccuracy 3/7・score 2/7しか勝てない。確率品質改善はあるが、採用目的であるaccuracy/coverage評価関数を既存候補より下げるためregistryへ追加しない。

## 成果物と判断

- OOS単体: `experiments/next_bar/walk_forward_intrabar_signed_variation_m15_001`
- 通常25% blend: `experiments/next_bar/ensemble_intrabar_signed_variation_m15_25_001`
- 方向維持confidence: `experiments/next_bar/intrabar_signed_variation_m15_confidence_blend_001`
- baseline分析: `experiments/next_bar/intrabar_signed_variation_m15_candidate_analysis.json`
- 親Shape方向比較: `experiments/next_bar/intrabar_signed_variation_vs_volatility_shape_m15_direction_analysis.json`
- 親Shape 0.525比較: `experiments/next_bar/intrabar_volatility_shape_vs_signed_variation_m15_0525_analysis.json`
- 既存0.525比較: `experiments/next_bar/body_atr_upper_half_vs_intrabar_signed_variation_m15_0525_analysis.json`, `experiments/next_bar/signed_body_quantile_vs_intrabar_signed_variation_m15_0525_analysis.json`

方向・confidenceとも不採用とし、実装と再現成果物だけを残す。M15 Shape単体方向候補、Profile broad confidence、clear-body/signed-body quantile 0.525候補を維持する。同じ履歴でsemivariance窓、jump定義、特徴subset、blend weight、閾値を再探索しない。損失倍率は標準1.0のみとする。
