# 00052 Intrabar frequency shape

日時: 2026-08-10 16:57 JST

## 目的

M15 Volatility ShapeはM1 range/varianceの集中度と時間重心を使うが、足内の値動きが低周波の滑らかな運動か、高周波の往復運動かを直接表現しない。完成M15を構成する15本の完成済みM1だけから固定周波数特徴を作り、親Shapeへの増分方向edgeと高信頼選別を検証する。

## 固定特徴

結果を見る前に次の12列へ固定し、周波数数、lag、weight、閾値を結果後に変更しなかった。

- close-to-close M1 returnを平均除去したDCT k=1..4のenergy fraction 4列
- k1+k2のlow、k3+k4のmid、残差high energy fraction
- low minus high frequency balance
- M1 returnのlag 1/2/3 normalized autocorrelation
- M1 high-low rangeを平均除去したDCT k1+k2 low-frequency fraction

DCTは固定長の直交cosine基底をコード内で計算し、SciPy変換や学習済みbasisを使わない。returnは比率、rangeはenergy比で正規化するため価格scaleを使わない。flat energyは0、各fractionは `[0, 1]`、balance/autocorrelationは `[-1, 1]` に固定した。

親 `intrabar_volatility_shape` の41 intrabar特徴へ12列を加え、53 intrabar、91 model特徴とした。scale 10倍一致、未来M1改変が過去完成足へ影響しないこと、flat足有限0、feature列契約、artifact保存とlatest推論を単体テストした。

## 方向結果

| period | 正式baseline | Frequency Shape | 親Volatility Shape |
|---|---:|---:|---:|
| development | 52.0144% | 52.1267% | 52.2748% |
| confirmation | 51.5012% | 51.5600% | 51.5832% |
| all | 51.8162% | 51.9078% | 52.0077% |

Frequency Shape単体は正式baselineをdevelopment/confirmation/allで上回り、accuracy 4/7、Brier/log loss各5/7 fold改善、純改善133件、paired p=0.361だった。しかし親Shapeにはaccuracy 1/7、Brier/log loss各2/7しか勝てず、純改善-145件、paired p=0.225である。周波数特徴の追加は親の方向edgeを希釈した。

正式baseline 75% + Frequency Shape 25%はdevelopment accuracyを52.014%から52.073%へ上げたが、confirmationは51.501%から51.391%へ低下し、純改善-10件、p=0.900だった。Brier/log lossは6/7 fold改善しても方向確認gateを通らないため採用しない。

## Confidence

方向維持25% confidence blendはdevelopment gridで0.53を選び、development scoreを0.02027から0.02161へ上げたが、confirmationは0.01511から0.01489へ下げた。現行baseline方向confidence候補には採用しない。

Frequency Shape単体自身の0.55 laneは、親Shapeに対して次の増分を示した。

| period | 親Shape accuracy / coverage / score | Frequency accuracy / coverage / score |
|---|---:|---:|
| development | 55.345% / 11.277% / 0.01468 | 55.788% / 10.763% / 0.01572 |
| confirmation | 56.158% / 3.027% / 0.00659 | 56.582% / 3.090% / 0.00745 |
| all | 55.463% / 8.091% / 0.01298 | 55.910% / 7.799% / 0.01395 |

親Shapeにはaccuracy・selection score各5/7 fold勝ち、development/confirmationとも局所整合・Wilson edgeを通った。周波数特徴は全体方向より高信頼順位付けへ情報を持つ可能性がある。

ただし現行precision championの方向維持Intrabar Structure 0.55と比較すると結果は逆だった。

| period | Structure accuracy / coverage / score | Frequency accuracy / coverage / score |
|---|---:|---:|
| development | 55.934% / 10.888% / 0.01631 | 55.788% / 10.763% / 0.01572 |
| confirmation | 56.437% / 3.104% / 0.00722 | 56.582% / 3.090% / 0.00745 |
| all | 56.010% / 7.881% / 0.01431 | 55.910% / 7.799% / 0.01395 |

Frequencyはconfirmationだけ僅かに上回るが、候補選択に使えるdevelopmentではaccuracy、coverage、scoreをすべてStructureが上回る。年別もStructure 4/7、Frequency 3/7で、registry基準ではFrequencyがdominatedとなる。選択集合Jaccardは46.6%だが、確認後に両者をstackして履歴へ合わせることはしない。

## 成果物と判断

- OOS: `experiments/next_bar/walk_forward_intrabar_frequency_shape_m15_001`
- baseline normal blend: `experiments/next_bar/ensemble_intrabar_frequency_shape_m15_25_001`
- baseline direction-preserving confidence: `experiments/next_bar/intrabar_frequency_shape_m15_confidence_blend_001`
- baseline分析: `experiments/next_bar/intrabar_frequency_shape_m15_candidate_analysis.json`
- 親Shape増分: `experiments/next_bar/intrabar_frequency_shape_vs_volatility_shape_m15_incremental_analysis.json`
- 親Shape 0.55: `experiments/next_bar/intrabar_frequency_shape_vs_volatility_shape_m15_055_analysis.json`
- Structure 0.55: `experiments/next_bar/intrabar_frequency_shape_vs_structure_confidence_m15_055_analysis.json`
- reliability: `experiments/next_bar/intrabar_frequency_shape_vs_volatility_shape_m15_reliability_analysis.json`

方向モデル、方向blend、baseline方向confidence、precision registryのすべてで不採用とし、特徴実装と再現成果物だけを残す。親HGB Shape方向候補とIntrabar Structure 0.55 precision championを維持する。同じ履歴でDCT frequency数、lag、feature subset、blend weight、閾値を再探索しない。損失倍率は標準1.0のみとする。
