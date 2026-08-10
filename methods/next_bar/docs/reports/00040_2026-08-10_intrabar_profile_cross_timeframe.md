# 00040 Intrabar profile cross-timeframe validation

日時: 2026-08-10 14:40 JST

## 目的

M15で増分edgeが確認できたIntrabar Profileを、そのままの特徴定義・HGB・Platt校正・25% blendでM5とM30へ移植する。時間足ごとに独立した7foldで検証し、同じ履歴を見た後の地点・特徴subset・weight再調整は行わない。

M1は下位足データを持たないため今回の足内profile対象外とした。

## データ品質修正

最初のM5実行ではbaseline 439,881行に対しcandidateが439,835行となり、46行が欠落した。原因は無変動の完成M5足で既存intrabar比率と新profile scaleが0/0になったことだった。

次の意味的ゼロを明示した。

- M5 rangeが0ならprofile level/deviationを0。
- absolute body合計が0ならbody directional efficiencyとconcentrationを0。
- absolute return合計が0ならclose path efficiencyを0。
- log rangeが0ならrealized variance/rangeを0。

flat-bar単体テストとM5/M30 sampling・有限値テストを追加した。修正後の正式M5成果物は全439,881行でbaselineと完全整列する。修正前の `walk_forward_intrabar_profile_m5_001`、`walk_forward_intrabar_profile_m5_aligned_001`、複合成果物内のM5は証拠から除外した。

## M5結果

### 単体方向

| period | baseline accuracy | profile single accuracy | fixes | harms | exact p |
|---|---:|---:|---:|---:|---:|
| development | 51.879% | 51.930% | 11,392 | 11,255 | 0.366 |
| confirmation | 51.041% | 51.073% | 7,959 | 7,905 | 0.674 |
| all | 51.556% | 51.600% | 19,351 | 19,160 | 0.333 |

合算では僅かに改善したが、confirmation 3foldでは1勝2敗で、対応あり差も有意ではない。通常25% blendも全体accuracy 51.551%、confirmation 51.023%、fixes 4,929対harms 4,953、p=0.817だった。M5方向モデルは置換しない。

### 方向維持confidence 0.515

閾値はdevelopmentの固定gridから一度だけ選んだ。

| period | model | coverage | accuracy | selection score |
|---|---|---:|---:|---:|
| development | baseline | 58.400% | 52.750% | 0.01913 |
| development | profile | 58.402% | 52.794% | 0.01947 |
| confirmation | baseline | 37.242% | 52.355% | 0.01199 |
| confirmation | profile | 37.115% | 52.412% | 0.01231 |
| all | baseline | 50.250% | 52.637% | 0.01722 |
| all | profile | 50.203% | 52.685% | 0.01755 |

accuracyとselection scoreはbaseline比6/7 fold改善した。方向をbaselineへ固定したまま、Brier、log loss、ECEは全て7/7 fold改善した。

| metric | baseline all | profile confidence all |
|---|---:|---:|
| Brier | 0.2495472 | 0.2495304 |
| log loss | 0.6922400 | 0.6922063 |
| ECE | 0.369% | 0.362% |

### 親Structureとの直接比較

同じ0.515でProfileとStructureを比較した。Profileはdevelopment、confirmation、allのselection scoreを全て改善し、fold別accuracy・scoreとも6/7で勝った。

| period | Structure score | Profile score |
|---|---:|---:|
| development | 0.01930 | 0.01947 |
| confirmation | 0.01189 | 0.01231 |
| all | 0.01730 | 0.01755 |

単なる親特徴の移植ではなく、追加trajectory 12特徴の増分効果がM5でも再現したと判断する。

## M30結果

方向用途は棄却した。単体accuracyは全体51.807%から51.753%、通常25% blendは51.725%へ悪化した。通常blendのfixes 1,507対harms 1,566、p=0.295である。

方向維持版はBrier/log lossを7/7、ECEを5/7 fold改善した。

| metric | baseline all | profile confidence all |
|---|---:|---:|
| Brier | 0.2494979 | 0.2494527 |
| log loss | 0.6921425 | 0.6920513 |
| ECE | 0.161% | 0.099% |

しかしdevelopment選択0.515のlaneはconfirmationでcoverage 43.303%から42.645%、accuracy 53.298%から53.196%、selection score 0.01581から0.01498へ全て悪化した。accuracy改善4/7、score改善3/7 foldに留まる。

よってM30は高信頼度選別候補にせず、aggregate calibrationだけを観測する研究shadowへ限定する。この改善値をfair oddsや採用判断には使わない。

## 最新推論と成果物

M5 profile単体の保存・最新推論を確認した。2026-06-01 04:55 UTC判定はup、model confidence 0.531473だった。empirical odds校正を接続していないため `odds_valid=false` であり、表示されたmodel probabilityを検証済みfair oddsとは扱わない。

- M5正式OOS: `experiments/next_bar/walk_forward_intrabar_profile_m5_complete_001`
- M5方向維持blend: `experiments/next_bar/intrabar_profile_m5_confidence_blend_001`
- M5分析: `experiments/next_bar/intrabar_profile_m5_candidate_analysis.json`
- M5親比較: `experiments/next_bar/intrabar_profile_vs_structure_m5_0515_analysis.json`
- M5最新artifact: `experiments/next_bar/intrabar_profile_m5_latest_artifact_001`
- M30 OOS: `experiments/next_bar/walk_forward_intrabar_profile_m5_m30_001` のM30のみ
- M30方向維持blend: `experiments/next_bar/intrabar_profile_m30_confidence_blend_001`
- M30分析: `experiments/next_bar/intrabar_profile_m30_candidate_analysis.json`
- M5固定設定: `methods/next_bar/config/m5_intrabar_profile_confidence_candidate_v1.json`
- M30 shadow設定: `methods/next_bar/config/m30_intrabar_profile_calibration_shadow_v1.json`

損失倍率は標準1.0のみとする。M5 0.515も履歴OOSで選んだ候補なのでauthoritative confidence、fair odds、現行policy、paper policyは置換せず、新しい完全未使用期間へ固定して判定する。
