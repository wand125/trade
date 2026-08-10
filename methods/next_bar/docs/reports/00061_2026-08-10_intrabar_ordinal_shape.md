# 00061 Intrabar ordinal shape

日時: 2026-08-10 18:22 JST

## 目的

M15内のM1 returnを振幅ではなく順序へ加工する。DCT/autocorrelationが線形な周波数・相関を表すのに対し、3点ordinal patternは非線形な加速・減速・反転構造を価格scale非依存で表現できる。Volatility Shapeへの増分方向edgeと高信頼順位付けを検証する。

## 結果前に固定した特徴

`--feature-set intrabar_ordinal_shape` は親Volatility Shapeへ次の7列を追加する。

- 連続する3本のM1 close-to-close returnについて、6種類の順列 `012/021/102/120/201/210` の出現比率。
- 6比率から計算する `log(6)` 正規化permutation entropy。

同値returnは `(return, 時間位置)` の辞書順で決定し、価格scale依存のepsilonを加えない。各patternは排他的で、非flat完成足では6比率の合計が1になる。親の41 intrabar列へ7列を加え、48 intrabar、全86特徴とした。

厳密な単調増加returnで012比率1・entropy 0、価格10倍不変、未来M1改変が過去特徴へ不影響、flat時有限0、全特徴の範囲 `[0, 1]`、artifact/latest推論をテストした。HGB、Platt、expanding training、M15同一7fold、25% blendを固定し、pattern subsetやweightを結果後に変更していない。

## 方向結果

| period | baseline | Ordinal Shape | parent Volatility Shape |
|---|---:|---:|---:|
| development | 52.014% | 52.141% | 52.275% |
| confirmation | 51.501% | 51.548% | 51.583% |
| all | 51.816% | 51.912% | 52.008% |

Ordinal単体はbaselineをdevelopment/confirmation/allで上回ったが、accuracy改善は4/7 fold、全期間純改善139件、paired p=0.331である。親Shapeに対してはdevelopment -119件、confirmation -20件、全期間-139件、p=0.194、accuracy/Brier/log loss各2/7 fold改善に留まった。親への追加で全体方向境界を悪化させるため方向候補には採用しない。

baseline 75% + Ordinal 25%の通常方向blendはdevelopment 52.007%、confirmation 51.385%、all 51.767%だった。全期間純改善-72件、p=0.312で、Brier/log lossが6/7 fold改善しても方向用途には使わない。

## Baseline方向維持confidence

25% confidence blendはBrier/log lossをdevelopment・confirmationの両方、6/7 foldで、ECEを5/7 foldで改善した。development gridは0.53を選んだ。

| period / model | accuracy | coverage | selection score |
|---|---:|---:|---:|
| development baseline | 54.309% | 29.868% | 0.02027 |
| development Ordinal | 54.517% | 29.175% | 0.02113 |
| confirmation baseline | 54.479% | 18.438% | 0.01511 |
| confirmation Ordinal | 54.341% | 17.816% | 0.01419 |
| all Ordinal | 54.468% | 24.788% | 0.01968 |

development改善はconfirmationで反転し、2025/2026途中もaccuracy・scoreが悪化した。現行Distribution Shape 0.53との直接比較でも、Ordinalはdevelopment/confirmation/allのaccuracyとscoreがすべて低く、年別accuracy/score各3/7対4/7だった。selective confidence候補には採用しない。

## 自身の0.55 precision lane

Ordinal情報は全体方向より、自身の高信頼順位付けに明確な増分を持った。

| period | Ordinal accuracy / coverage / score | parent Shape accuracy / coverage / score |
|---|---:|---:|
| development | 55.892% / 10.898% / 0.01618 | 55.345% / 11.277% / 0.01468 |
| confirmation | 57.347% / 2.877% / 0.00834 | 56.158% / 3.027% / 0.00659 |
| all | 56.099% / 7.800% / 0.01448 | 55.463% / 8.091% / 0.01298 |

親Shapeにはaccuracy 5/7、score 6/7 fold勝った。ただしprecision championのIntrabar Structure 0.55と比べると採用根拠は不足した。

| period | Ordinal accuracy / coverage / score | Structure accuracy / coverage / score |
|---|---:|---:|
| development | 55.892% / 10.898% / 0.01618 | 55.934% / 10.888% / 0.01631 |
| confirmation | 57.347% / 2.877% / 0.00834 | 56.437% / 3.104% / 0.00722 |
| all | 56.099% / 7.800% / 0.01448 | 56.010% / 7.881% / 0.01431 |

Ordinalはaccuracy 5/7でもscoreは3/7だけ勝ち、候補選択に使えるdevelopment objectiveはStructureが上だった。選択集合Jaccardは全体47.7%で差はあるが、日次5,000回bootstrapの全期間Ordinal−Structure差はaccuracy +0.089pt、95%区間-0.704〜+0.897pt、score +0.000162、区間-0.002049〜+0.002441だった。confirmation accuracy差+0.910ptも区間-1.406〜+3.218ptで優位未確定である。Ordinal自身の全体Brier/log lossはStructureより点推定で悪かった。

## 判断

Ordinal Shapeは方向、baseline方向confidence 0.53、precision candidateのすべてで採用しない。

- ordinal patternには親Shapeの0.55 tailを改善する情報があるため、feature setと成果物は再現用に残す。
- candidate config、registry entry、latest artifactは発行しない。
- Volatility Shape方向候補、Distribution/Extra Trees 0.53、Intrabar Structure 0.55を維持する。
- pattern長、tie処理、pattern subset、blend weight、閾値を同じ履歴へ合わせて再探索しない。

主要成果物:

- `experiments/next_bar/walk_forward_intrabar_ordinal_shape_m15_001`
- `experiments/next_bar/intrabar_ordinal_shape_m15_candidate_analysis.json`
- `experiments/next_bar/intrabar_ordinal_shape_vs_volatility_shape_m15_incremental_analysis.json`
- `experiments/next_bar/intrabar_ordinal_shape_vs_volatility_shape_m15_055_analysis.json`
- `experiments/next_bar/intrabar_ordinal_shape_vs_distribution_shape_m15_053_analysis.json`
- `experiments/next_bar/intrabar_ordinal_shape_vs_structure_m15_055_analysis.json`
- `experiments/next_bar/intrabar_ordinal_shape_vs_structure_m15_055_daily_bootstrap.json`
