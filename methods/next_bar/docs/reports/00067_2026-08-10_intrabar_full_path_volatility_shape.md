# 00067 Intrabar Full Path × Volatility Shape

日時: 2026-08-10 19:34 JST

## 目的

採用済みFull Pathは完成M15内15本のM1 close順序、Volatility ShapeはM1 rangeとclose-to-close分散の集中位置を表す。親Profile以外の重複がない固定unionで、方向とconfidenceのどちらかをさらに改善できるか検証した。

## 固定定義

結果を見る前に、Full Pathの追加11列とVolatility Shapeの14列を全て使うと固定した。親Profileを含め52 intrabar特徴、全90 model特徴である。特徴subset、weight、HGB parameterは変更していない。価格10倍一致、未来M1改変が過去完成足へ不影響、flat有限0、stationary validator、artifact/latest推論をテストした。

## 方向結果

| period | 正式baseline | union単体 | 通常25% blend |
|---|---:|---:|---:|
| development | 52.0144% | 52.0975% | 52.1199% |
| confirmation | 51.5012% | 51.5029% | 51.3888% |
| all | 51.8162% | 51.8679% | 51.8375% |

union単体はbaseline比全体+75件、p=0.603、通常blendは+31件、p=0.673である。通常blendはaccuracy 5/7、Brier/log loss 7/7 fold改善したがconfirmation方向を-63件悪化させた。

より重要な親比較では、union単体はFull Pathにaccuracy 2/7、Volatility Shapeには0/7で、全体も51.868%対51.965%・52.008%だった。追加情報を同じHGBへ単純投入すると方向識別が希釈されたため、方向用途は棄却する。

## 方向維持confidence

developmentの事前gridでは0.525が最大selection scoreになった。

| period | baseline accuracy / coverage / score | union accuracy / coverage / score |
|---|---:|---:|
| development | 53.858% / 37.908% / 0.02048 | 54.041% / 37.365% / 0.02142 |
| confirmation | 53.777% / 26.375% / 0.01527 | 53.888% / 25.834% / 0.01563 |
| all | 53.834% / 33.454% / 0.01961 | 53.994% / 32.912% / 0.02035 |

baseline比ではaccuracy 6/7、selection score 4/7、Brier/log loss 7/7、ECE 5/7 fold改善した。aggregateは両期間で正方向だが、事前の採用gateであるscore 5/7に届かない。

## 親・既存候補との比較

| comparator at 0.525 | union / comparator all accuracy | union / comparator all score | unionのaccuracy / score勝数 |
|---|---:|---:|---:|
| Full Path | 53.994% / 53.958% | 0.02035 / 0.02014 | 3/7、3/7 |
| Volatility Shape | 53.994% / 53.911% | 0.02035 / 0.01990 | 3/7、3/7 |
| Signed-body Quantile | 53.994% / 54.080% | 0.02035 / 0.02100 | 1/7、1/7 |
| Clear-body | 53.994% / 54.182% | 0.02035 / 0.02088 | 2/7、2/7 |

親にはaggregateで僅かに勝つが年別3/7で、confirmationではFull Pathにaccuracy・score・Brier/log lossが全て負けた。balanced championのSigned-body Quantileにはdevelopment、confirmation、allのaccuracy・scoreが全て負け、年別も1/7だった。Clear-bodyにも2/7である。

UTC日paired bootstrap 20,000回では、union−Full Pathの全期間accuracy差+0.037pt、score差+0.000207の95%区間はともに0を跨ぎ、confirmationは負方向だった。union−Signed-body Quantileは全期間accuracy -0.086pt、score -0.000655で、unionのscore優位確率は9.31%だった。一方Brier/log lossはunionが有意に良い。つまり確率全体の滑らかさは改善するが、主目的である高信頼帯のaccuracy×coverage順位付けは悪化する。

## 判断

固定unionは、情報を増やせば必ず良くなるわけではなく、HGBの有限容量内で経路と集中度が競合することを示した。方向単体、通常方向blend、0.525 confidenceの全てを不採用とする。feature setとOOS成果物は再現用に残すが、forward config、candidate registry、latest artifactは発行しない。

Full Path 0.53 selective champion、Volatility Shape単体方向候補、Signed-body Quantile/Clear-body 0.525を維持する。同じ履歴でunionのsubset、別weight、閾値、tree capacityを再探索しない。損失倍率は標準1.0のみとする。

## 成果物

- OOS: `experiments/next_bar/walk_forward_intrabar_full_path_volatility_shape_m15_001`
- 通常blend: `experiments/next_bar/ensemble_intrabar_full_path_volatility_shape_m15_25_001`
- 方向維持confidence: `experiments/next_bar/intrabar_full_path_volatility_shape_m15_confidence_blend_001`
- candidate analysis: `experiments/next_bar/intrabar_full_path_volatility_shape_m15_candidate_analysis.json`
- 親・既存候補比較: `experiments/next_bar/intrabar_full_path_volatility_shape_vs_*`
