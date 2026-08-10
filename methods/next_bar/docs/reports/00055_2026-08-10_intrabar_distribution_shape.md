# 00055 Intrabar return distribution shape

日時: 2026-08-10 17:26 JST

## 目的

M15 Volatility Shapeは足内の分散集中度、時間重心、最大jumpを使うが、M1 return分布の位置・裾・robust skewを直接表現しない。完成M15内の完成済みM1だけから価格水準非依存の分布形状を作り、方向予測とconfidence順位付けへの増分を検証した。

## 固定特徴

結果を見る前に親 `intrabar_volatility_shape` へ次の9列を追加した。

- M1 close-to-close log returnのq10/q25/q50/q75/q90を足内return RMSで割った5列
- q25/q50/q75によるBowley skew
- q10/q50/q90によるtail skew
- IQR / interdecile range
- median absolute deviation / return RMS

15本という短い足内標本なので、標本skewness/kurtosisの高次momentは使わない。return energyまたは分母が0なら0とする。親41 intrabar特徴＋9列＝50 intrabar、全88 model特徴である。価格10倍一致、未来M1改変が過去完成足へ不影響、flat有限0、artifact/latest推論をテストした。

## 方向結果

| period | 正式baseline | Distribution Shape | 親Volatility Shape |
|---|---:|---:|---:|
| development | 52.0144% | 52.0492% | 52.2748% |
| confirmation | 51.5012% | 51.5386% | 51.5832% |
| all | 51.8162% | 51.8520% | 52.0077% |

Distribution単体は正式baselineを全期間で52件改善したが、p=0.721で方向edgeは弱い。親Shapeには全体で226件負け、paired p=0.0491、accuracy 2/7 fold勝利だった。正式baseline 75% + Distribution 25%の通常blendも全体-48件、confirmation-49件、p=0.503であり、方向モデルと通常方向blendには採用しない。

## 方向維持confidence

baseline方向を固定した25% confidence blendはBrier/log lossを7/7 fold、ECEを5/7 fold改善した。developmentの事前gridで0.53が最大selection scoreとなった。

| period | baseline accuracy / coverage / score | Distribution confidence accuracy / coverage / score |
|---|---:|---:|
| development | 54.309% / 29.868% / 0.02027 | 54.575% / 29.111% / 0.02141 |
| confirmation | 54.479% / 18.438% / 0.01511 | 54.551% / 17.894% / 0.01512 |
| all | 54.357% / 25.453% / 0.01942 | 54.568% / 24.779% / 0.02018 |

0.53 laneはbaselineにaccuracy・score各5/7 fold勝ち、development/confirmationともmean confidenceがWilson区間内で、下限も50%を超えた。confirmationのscore改善は+0.000016と小さいため、fresh確認なしにauthoritative confidenceへは使わない。

## Extra Trees championとの比較

| period | Distribution score | Extra Trees score | Distribution accuracy | Extra Trees accuracy |
|---|---:|---:|---:|---:|
| development | 0.02141 | 0.02094 | 54.575% | 54.467% |
| confirmation | 0.01512 | 0.01574 | 54.551% | 54.664% |
| all | 0.02018 | 0.02006 | 54.568% | 54.522% |

Distributionはdevelopment objectiveと全体proper score、年別accuracy/score 5/7で勝った。Extra Treesはconfirmation accuracy/scoreとcoverageで勝ち、2025・2026途中の2年連続で優位だった。選択集合Jaccardは85.5%で大半は共通だが、完全同一ではない。

registryは事前規定どおりdevelopment selection scoreをchampion objective、confirmationをgate/auditにのみ使うため、Distribution 0.53をselective roleの履歴上championに更新した。Extra Trees 0.53とbody/ATR weighted 0.54はchallengerとして残し、fresh期間で並行比較する。

## Runtime parity

baselineと同じtrain/calibration/test境界・HGB設定でlatest artifactを生成し、parity検査を通した。最新2026-06-01 04:45 UTCはbaseline up 0.577254、Distribution up 0.562220、方向維持25% blend up 0.573495で0.53 laneを通る。odds校正・運用認可は接続していないため `odds_valid=false` のままである。

## 成果物と判断

- config: `methods/next_bar/config/m15_intrabar_distribution_shape_confidence_candidate_v1.json`
- OOS: `experiments/next_bar/walk_forward_intrabar_distribution_shape_m15_001`
- 通常blend: `experiments/next_bar/ensemble_intrabar_distribution_shape_m15_25_001`
- 方向維持confidence: `experiments/next_bar/intrabar_distribution_shape_m15_confidence_blend_001`
- Extra Trees比較: `experiments/next_bar/intrabar_distribution_shape_vs_extra_trees_m15_053_analysis.json`
- reliability: `experiments/next_bar/intrabar_distribution_shape_vs_extra_trees_m15_reliability_analysis.json`
- latest artifact/output: `experiments/next_bar/intrabar_distribution_shape_m15_latest_artifact_001`, `experiments/next_bar/intrabar_distribution_shape_m15_latest_ensemble_001`

方向用途は棄却し、固定0.53のselective confidence forward candidateとして採用する。registry上は履歴championだが、authoritative confidence、現行adoption policy、paper/live売買policyは変更しない。fresh期間でExtra Trees以上のaccuracy・selection score・Brierを同時に確認できた場合だけ実運用昇格を検討する。損失倍率は標準1.0のみとする。

