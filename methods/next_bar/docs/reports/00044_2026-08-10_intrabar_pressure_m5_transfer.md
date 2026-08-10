# 00044 Intrabar Pressure M5 transfer

日時: 2026-08-10 15:28 JST

## 目的

M15で定義したIntrabar Pressure 11特徴を変更せずM5へ移植する。HGB、Platt、7fold、baseline 75% + Pressure 25%も固定し、方向精度、確率品質、高信頼度帯をM5正式baselineと比較する。結果後の特徴subset、weight、閾値調整は行わない。

## データ整合

M5正式baselineと同じ439,881 OOS行、同じtest2020〜test2026_partialを使用した。fold、bar timestamp、targetは完全整列した。Pressureは完成M5内の完成済みM1 OHLCだけを使い、価格水準とvolumeを入力しない。

## 方向結果

| period | baseline | Pressure単体 | Pressure 25% blend |
|---|---:|---:|---:|
| development | 51.8795% | 51.9120% | 51.9235% |
| confirmation | 51.0408% | 51.0875% | 51.0509% |
| all | 51.5564% | 51.5944% | 51.5874% |

25% blendはdevelopmentとconfirmationをともに改善し、accuracyは5/7 foldで改善した。baseline誤り修正5,145件、新規誤り5,009件、純改善136件、McNemar exact p=0.1803である。

| metric | baseline all | Pressure 25% all | improved folds |
|---|---:|---:|---:|
| Brier | 0.2495472 | 0.2495296 | 7/7 |
| log loss | 0.6922400 | 0.6922047 | 7/7 |
| ECE | 0.3687% | 0.3379% | 5/7 |

方向差の統計的証拠はまだ弱いが、M15で固定済みの特徴と比率がM5でもdevelopment/confirmation、accuracy 5/7、proper score 7/7を改善した。現行置換ではなくparallel forward direction candidateへ固定する。

## 親Profile方向blendとの比較

| period | Profile 25% | Pressure 25% |
|---|---:|---:|
| development | 51.8817% | 51.9235% |
| confirmation | 51.0231% | 51.0509% |
| all | 51.5510% | 51.5874% |

Pressureはaccuracyで6/7 fold勝ち、3期間すべてでProfile方向blendを上回った。M15で追加した買い／売り圧力proxyは、M5でもtrajectoryだけの親特徴に対する増分を持つ。

## Confidenceと高信頼度帯

development目的関数が選んだ方向維持thresholdは0.515だった。

| period | model | coverage | accuracy | selection score |
|---|---|---:|---:|---:|
| development | baseline | 58.400% | 52.750% | 0.01913 |
| development | Pressure | 58.549% | 52.792% | 0.01948 |
| confirmation | baseline | 37.242% | 52.355% | 0.01199 |
| confirmation | Pressure | 37.142% | 52.412% | 0.01232 |

Pressure 0.515はbaseline比でaccuracy・selection scoreを6/7、Brier/log loss/ECEを7/7 fold改善した。confirmationの固定高信頼帯は次の通り。

| threshold | rows | coverage | accuracy | mean confidence | Wilson lower |
|---|---:|---:|---:|---:|---:|
| 0.515 | 62,930 | 37.142% | 52.412% | 52.453% | 52.022% |
| 0.525 | 24,147 | 14.252% | 53.530% | 53.271% | 52.901% |
| 0.535 | 6,939 | 4.095% | 54.749% | 54.152% | 53.575% |
| 0.550 | 653 | 0.385% | 58.346% | 55.618% | 54.527% |

ただし既に採用済みのProfile 0.515と直接比較するとPressureはaccuracy・selection scoreとも3/7対4/7で負け、選択集合のJaccardは0.950だった。3期間のscore差も約1e-5で実質同等である。重複したconfidence候補は増やさず、Profile 0.515を維持する。

## Profile + Pressure平均は棄却

列衝突を解消してensemble成果物を再入力可能にし、baseline方向へ固定したProfile 25% blendとPressure 25% blendの等重み平均も検証した。方向guardが働かない行では `75% baseline + 12.5% Profile + 12.5% Pressure` に等しい。Profile単体confidenceに対しfold勝敗は3/7対4/7、confirmation scoreは0.01231から0.01210、全体scoreは0.01755から0.01749へ悪化した。相関の高い2候補の平均によるノイズ低減は再現せず、採用しない。

## Runtime parity

Pressure latest artifactをbaselineと同じ60/20/20境界・主要設定で生成した。2026-06-01 04:55 UTCはbaseline up 0.533271、Pressure up 0.541363、25% blend up 0.535294だった。artifact parityは通過した。経験的oddsは接続せず `odds_valid=false`、`strict_prediction_eligible=false` のままである。

## 成果物と判断

- Pressure OOS: `experiments/next_bar/walk_forward_intrabar_pressure_m5_001`
- 通常方向blend: `experiments/next_bar/ensemble_intrabar_pressure_m5_25_001`
- 方向維持blend: `experiments/next_bar/intrabar_pressure_m5_confidence_blend_001`
- candidate分析: `experiments/next_bar/intrabar_pressure_m5_candidate_analysis.json`
- reliability分析: `experiments/next_bar/intrabar_pressure_m5_reliability_analysis.json`
- Profile直接比較: `experiments/next_bar/intrabar_pressure_vs_profile_m5_0515_analysis.json`
- 棄却したProfile/Pressure平均: `experiments/next_bar/intrabar_profile_pressure_m5_confidence_blend_001`
- latest artifact: `experiments/next_bar/intrabar_pressure_m5_latest_artifact_001`
- latest ensemble: `experiments/next_bar/intrabar_pressure_m5_latest_ensemble_001`
- 固定設定: `methods/next_bar/config/m5_intrabar_pressure_direction_candidate_v1.json`

通常25%方向blendだけをparallel forward候補として採用する。Pressure confidenceとProfile/Pressure平均は採用しない。fresh期間でaccuracy、Brier、log lossがbaseline以上の場合だけauthoritative方向への昇格を検討する。損失倍率は標準1.0のみとする。
