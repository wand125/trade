# 00069 Intrabar Path Signature

日時: 2026-08-10 19:57 JST

## 目的

Full Pathは完成M15内15本のM1 closeを順番ごとに保持するが、HGBが複数地点の高次な順序関係を直接作る必要がある。時間×正規化closeの区分線形経路を少数の順序感応係数へ加工し、親Full Pathの方向または0.53 selective confidenceを増分改善できるか検証した。

## 固定特徴

M15始値を `(time, price)=(0, 0)`、各M1 closeをM15 high-low rangeで正規化し、15等間隔の2次元経路とした。各線分のsignatureをChen積で厳密に合成し、終点だけで決まる対称項を除いた次の3列をFull Pathへ追加した。

- level 2のtime-price signed area
- level 3のtime-time-price bracket
- level 3のprice-time-price bracket

直線経路では3列が厳密に0になり、同じ終点でも早い上昇と遅い上昇はsigned areaの逆符号で区別される。学習済みbasis、raw価格水準、未来M1は使わない。41 intrabar・全79特徴について価格10倍一致、未来改変不影響、flat有限0、stationary validator、artifact/latest推論をテストした。大規模M1入力の一時level-3 tensorは10万行ずつ処理する。

## 方向結果

| period | baseline | Path Signature単体 | 通常25% blend |
|---|---:|---:|---:|
| development | 52.0144% | 52.1458% | 52.0268% |
| confirmation | 51.5012% | 51.5440% | 51.4316% |
| all | 51.8162% | 51.9133% | 51.7969% |

単体はbaseline比+141件、p=0.316で、両期間を改善した。通常blendはconfirmation -39件、全体-28件、p=0.698のため方向blendには使わない。

親Full Path単体との比較では、Path Signatureはdevelopment 52.146%対52.269%で負け、confirmation 51.544%対51.482%で勝ち、全体51.913%対51.965%、純-75件、p=0.482だった。年別accuracyは3/7に留まる。Brier/log lossは両期間で僅かに改善したが、方向の親増分edgeはないため単体方向候補にも採用しない。

## 方向維持confidence

development gridでは0.53が最大selection scoreになった。

| period | baseline accuracy / coverage / score | Path Signature accuracy / coverage / score |
|---|---:|---:|
| development | 54.309% / 29.868% / 0.02027 | 54.662% / 29.400% / 0.02201 |
| confirmation | 54.479% / 18.438% / 0.01511 | 54.676% / 18.007% / 0.01571 |
| all | 54.357% / 25.453% / 0.01942 | 54.666% / 24.999% / 0.02077 |

baseline比ではaccuracy 6/7、selection score 5/7、Brier/log loss 7/7、ECE 5/7 fold改善し、単独gateは通った。

ただし親Full Path 0.53との固定比較は次の通りだった。

| period | Path Signature accuracy / coverage / score | Full Path accuracy / coverage / score |
|---|---:|---:|
| development | 54.662% / 29.400% / 0.02201 | 54.580% / 29.801% / 0.02173 |
| confirmation | 54.676% / 18.007% / 0.01571 | 54.905% / 17.311% / 0.01628 |
| all | 54.666% / 24.999% / 0.020766 | 54.667% / 24.977% / 0.020763 |

年別はaccuracy 4/7、score 3/7。developmentの僅かな改善はconfirmationで、coverage +0.696ptと引き換えにaccuracy -0.229pt、score -0.000568へ反転した。全期間score差は+0.0000035で実質同値である。

UTC日paired bootstrap 20,000回では、全期間score差の95%区間は-0.000776〜+0.000772、Path Signature優位確率50.2%。confirmation score優位確率は18.1%だった。全期間Brier/log lossの僅かな改善も区間は0を跨いだ。

旧候補との0.53年別比較ではDistribution Shapeへaccuracy 5/7・score 4/7、Extra Treesへ各5/7勝った。しかし現championかつ直接の親であるFull Pathを上積みできないため、候補数を増やす根拠にはしない。

## 判断

Path Signatureはbaselineに対しては良質で、3特徴だけでも順序情報を木へ渡しやすくする効果を示した。しかしFull Pathが既に持つ15地点から得られるedgeとほぼ完全に重複し、confirmationのaccuracy×coverage交換は親より悪い。feature setとOOS成果物は再現用に残すが、config、registry、latest artifactは発行しない。

Full Path 0.53 selective champion、Volatility Shape方向候補、既存balanced/precision championを維持する。同じ履歴でsignature level、基底組合せ、特徴subset、blend weight、閾値を再探索しない。損失倍率は標準1.0のみとする。

## 成果物

- OOS: `experiments/next_bar/walk_forward_intrabar_path_signature_m15_001`
- 通常blend: `experiments/next_bar/ensemble_intrabar_path_signature_m15_25_001`
- 方向維持confidence: `experiments/next_bar/intrabar_path_signature_m15_confidence_blend_001`
- candidate analysis: `experiments/next_bar/intrabar_path_signature_m15_candidate_analysis.json`
- 親・旧候補比較: `experiments/next_bar/intrabar_path_signature_vs_*_m15_053_analysis.json`
- Full Path日次bootstrap: `experiments/next_bar/intrabar_path_signature_vs_full_path_m15_053_daily_bootstrap.json`
