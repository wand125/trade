# 00091 M1 × M5/M15 as-of Meta 再検証

日時: 2026-08-11 06:30 JST

## 目的

M1内の複数モデルを組み合わせたconfidence改善が一巡したため、M1だけでは得られない確定済みM5/M15予測を独立contextとして再評価した。過去のM1 as-of meta結果を見て条件を再探索せず、現M1 baselineと最新Transition guard 50/50 championへ同一行で直接比較する。

## 固定仕様と因果性

M1 baselineをtargetとし、M5/M15 baselineの直近確定済みOOS予測をbackward as-of joinした。同時刻contextは使わず、最大age 15分、logit 3列のL2 logistic regression、`C=0.10`、baseline 75% + meta 25%、seed 42に固定した。

各test foldのmetaは、それより前のtest OOS foldだけで学習する。test2020はmeta学習専用とし、評価はtest2021〜test2026途中の6fold、1,801,986行である。元M1 2,183,717行のうちas-of結合可能なのは2,141,340行、98.06%だった。M5 ageは中央値2分・最大14分、M15 ageは中央値7分・最大15分で、未来contextは0行だった。

比較時の母集団差をなくすため、baselineと現championをmeta評価行のfold、timestamp、targetへ厳密に整列する部分集合materializerを追加した。重複、target不一致、欠損、順序不一致を停止する。

## 全方向と確率品質

| model | accuracy | Brier | log loss | ECE |
|---|---:|---:|---:|---:|
| aligned baseline | 50.65789% | 0.24991305 | 0.69297329 | 0.1950% |
| meta単体 | 50.62476% | 0.24994181 | 0.69303088 | 0.1768% |
| baseline 75% + meta 25% | 50.66865% | 0.24991578 | 0.69297874 | 0.1603% |

25% blendはbaseline比で純+194件、accuracy +0.01077ptだった。しかしUTC日20,000回paired bootstrapの95%区間は-0.01385〜+0.03525ptで0を跨いだ。developmentは+0.00237pt、confirmationは+0.02054ptだが、いずれも区間が0を跨ぐ。

一方、Brier差は+0.00000273、95%区間+0.00000083〜+0.00000463、log loss差は+0.00000546、区間+0.00000164〜+0.00000926で、悪化側に確定した。ECE点推定だけの改善では方向候補へ昇格できない。

## 固定0.515選別

| period | aligned baseline accuracy / coverage / score | cross-TF meta accuracy / coverage / score | 現champion accuracy / coverage / score |
|---|---:|---:|---:|
| development | 51.6892% / 21.2464% / 0.006791 | 51.6522% / 20.7943% / 0.006539 | 52.1772% / 14.6010% / 0.007325 |
| confirmation | 52.4833% / 9.9070% / 0.006743 | 52.6531% / 8.6073% / 0.006711 | 53.3008% / 7.0183% / 0.007672 |
| all | 51.9162% / 16.0079% / 0.006937 | 51.9147% / 15.1643% / 0.006726 | 52.5054% / 11.0980% / 0.007617 |

metaはbaseline比でaccuracy 4/6fold、selection score 2/6foldに留まり、development・confirmation・allのselection scoreをすべて下げた。現championにはaccuracy・scoreとも0/6対6/6だった。

現champion比の日次bootstrapでは、全期間accuracy差-0.5908pt、95%区間-0.7261〜-0.4554pt、selection score差-0.000891、区間-0.001347〜-0.000425だった。coverageは+4.0662ptだが、Wilson下限、Brier、log lossもすべて悪化側に確定し、coverage増で精度低下を補えない。

## 信頼度曲線

metaの全期間累積accuracyは0.515=51.9147%、0.525=52.7304%、0.535=52.9853%、0.55=53.1423%だった。現championは同じ閾値で52.5054%、53.5102%、53.7243%、54.3315%と全て上回った。

metaは0.515でmean confidence 52.2956%に対してaccuracy 51.9147%、0.55では55.7814%に対して53.1423%となり、高い閾値ほど過信が拡大した。confirmationの0.55は65件・accuracy 49.23%しかなく、現champion側も32件でedge未確認である。高閾値の点推定を採用根拠やfair oddsに使えない。

## 判断

固定M1 × M5/M15 as-of metaは方向・confidenceの両用途で棄却し、再現専用とする。因果的な上位足context経路は成立したが、方向の小幅改善は統計的に未確定でproper scoreが悪化し、0.515では現championに全fold負けた。

config、registry、latest、fair odds、paper/live policyは発行・変更しない。今回の履歴を見て最大age、M30追加、context subset、C、blend weight、閾値を再探索しない。この結果は上位足情報が常に無効という意味ではなく、今回固定した確率再混合が現championへ増分edgeを与えなかったことを示す。

## 成果物

- meta OOS: `experiments/next_bar/cross_timeframe_meta_m1_asof_m5_m15_fixed_001`
- baseline aligned subset: `experiments/next_bar/baseline_m1_cross_tf_aligned_001`
- champion aligned subset: `experiments/next_bar/transition_guard_champion_m1_cross_tf_aligned_001`
- baseline analysis: `experiments/next_bar/cross_timeframe_meta_m1_candidate_analysis.json`
- champion analysis: `experiments/next_bar/cross_timeframe_meta_vs_transition_guard_champion_m1_analysis.json`
- direction bootstrap: `experiments/next_bar/cross_timeframe_meta_vs_baseline_m1_direction_bootstrap.json`
- champion bootstrap: `experiments/next_bar/cross_timeframe_meta_vs_transition_guard_champion_m1_bootstrap.json`
- reliability: `experiments/next_bar/cross_timeframe_meta_vs_transition_guard_champion_m1_reliability.json`
- subset utility: `methods/next_bar/scripts/materialize_prediction_subset.py`
