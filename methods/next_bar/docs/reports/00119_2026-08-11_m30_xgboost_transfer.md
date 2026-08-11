# 00119 M30 XGBoost Fixed Transfer

日時: 2026-08-11 16:10 JST

## 目的

同じ加工済み市場状態でも学習器を変えると方向精度または信頼度品質を上積みできるかを調べるため、M1でbaselineを7/7fold改善した固定XGBoost仕様をM30へ移植した。方向単体・通常blendに加え、baseline方向を維持したconfidence、既存Pressure系との固定多様化まで、test2020〜test2026途中の同じ期間で評価した。

## 固定仕様と品質

生OHLC価格水準を直接入れず、baselineの加工済み38特徴を使用した。XGBoost 3.4.0、300 trees、depth 4、learning rate 0.03、min child weight 20、row/column subsample 0.8、L2 5、hist tree method、seed 42、expanding、uniform sample、全教師、最大train 750,000行、Platt、標準損失1.0を固定した。M1からtree parameter、feature、teacher、25% weightを変更せず、M30履歴へ合わせた探索はしていない。

7foldのbaseline・既存候補とtimestamp/targetを完全整列した71,260 OOS行を評価した。最終fold artifactから2026-06-01 04:30 UTCを再推論し、up、probability up 52.5754%を確認した。経験的オッズ検証はないため `odds_valid=false` である。

## 方向

| model | development accuracy | confirmation accuracy | all accuracy | all Brier | all log loss | all ECE |
|---|---:|---:|---:|---:|---:|---:|
| HGB baseline | 51.9897% | 51.5202% | 51.8075% | 0.249497879 | 0.692142533 | 0.1608% |
| XGBoost単体 | 51.9094% | 51.5563% | 51.7724% | 0.249428789 | 0.692002869 | 0.3649% |
| baseline 75% + XGBoost 25% | 51.9094% | 51.4877% | 51.7457% | 0.249453929 | 0.692053940 | 0.2330% |

XGBoost単体はbaseline比development -35件、confirmation +10件、all -25件、accuracy 3/7foldだった。Brierは5/7、log lossは6/7fold改善したが、ECEは3/7foldに留まった。通常25% blendは-35/-9/-44件、accuracy 3/7foldで、Brier/log lossは各6/7、ECEは4/7fold改善した。方向正答率の上積みとしては棄却する。

通常blend−baselineの日次bootstrap 20,000回では、all accuracy差-0.0617ptの95%区間が-0.1889〜+0.0645ptで0を跨いだ。一方、all Brier差-0.00004395の区間は-0.00006598〜-0.00002217、log loss差-0.00008859は-0.00013286〜-0.00004479で改善を支持した。developmentもproper scoreを改善したが、confirmationは区間が僅かに0を跨いだ。aggregateの確率平滑化だけを方向edgeと解釈しない。

現行Haar入り方向co-challengerとの直接比較では、XGBoost単体がdevelopment 51.9094%対52.1939%、confirmation 51.5563%対51.6756%、all 51.7724%対51.9927%で下回り、accuracy 1/7対6/7foldだった。all proper scoreもほぼ同等ながら僅かにHaar側が良かった。親方向モデルが明確に劣るため、追加の固定方向平均は行わない。

## confidence

baseline方向を維持してXGBoost確率だけを25%加えた0.515 laneを比較した。

| period | baseline coverage / accuracy / score | XGBoost coverage / accuracy / score |
|---|---:|---:|
| development | 52.9829% / 53.1126% / 0.017968 | 53.4508% / 53.1497% / 0.018340 |
| confirmation | 43.3028% / 53.2977% / 0.015815 | 43.7909% / 53.2321% / 0.015502 |
| all | 49.2254% / 53.1758% / 0.018616 | 49.7011% / 53.1779% / 0.018738 |

allではcoverage +0.4757pt、accuracy +0.0021pt、selection score +0.000122で、Brier/log lossも6/7fold、ECEも6/7fold改善した。しかし年別accuracy/scoreは4/7対baseline 3/7に過ぎず、confirmationではaccuracy -0.0656pt、score -0.000313へ反転した。

日次bootstrapではall coverage差の95%区間+0.2940〜+0.6551pt、Brier差-0.00006590〜-0.00002235、log loss差-0.00013274〜-0.00004518が改善を支持した。一方、all accuracy差区間-0.1670〜+0.1690pt、score差-0.001069〜+0.001295は0を跨いだ。広い選別とproper scoreの感度はあるが、coverage-aware objectiveの増分は確定しない。

既存Pressure 0.52との比較では、XGBoost 0.515がall coverage 49.7011%対36.4861%と広い一方、accuracy 53.1779%対53.7577%、score 0.018738対0.019034だった。XGBoostはaccuracy 0/7、score 3/7であり、broad confidence役割へ追加しない。

0.55ではXGBoostが4,848件、coverage 6.8033%、accuracy 55.5281%、score 0.010760だった。Pressure + AR shadowは4,412件、6.1914%、56.1423%、0.011629で、XGBoostはaccuracy 1/7、score 2/7foldだった。tail用途にも採用しない。

## 固定confidence多様化

PressureとXGBoost confidenceを固定50/50平均した。0.52ではall 26,415件、coverage 37.0685%、accuracy 53.6059%、score 0.018290で、Pressureの26,000件、36.4861%、53.7577%、0.019034を下回り、accuracy 2/7、score 3/7foldだった。

0.55では固定平均が4,523件、coverage 6.3472%、accuracy 56.0911%、score 0.011690、Pressure + ARは4,412件、6.1914%、56.1423%、0.011629だった。固定平均はdevelopmentでcoverageを増やしたが、confirmationではaccuracy 55.7395%対56.0088%、score 0.004502対0.004997へ悪化し、年別accuracy/scoreとも2/7対5/7だった。

日次bootstrapではall coverage差+0.1558ptの95%区間+0.0934〜+0.2186ptだけが増加側で確定した。all accuracy差-0.0512ptの区間-0.5187〜+0.4176pt、score差+0.000062の区間-0.001122〜+0.001248は0を跨ぎ、proper score差も未確定だった。既存shadowを置換できる多様化edgeではない。

## 判断

XGBoost単体、通常25%方向blend、方向維持0.515/0.55、Pressureとの固定50/50 confidence平均をすべて再現専用とする。学習器変更はM30でもBrier/log lossとcoverageを改善する感度を示したが、方向accuracyとconfirmationのcoverage-aware objectiveを上積みしなかった。tree parameter、feature、blend weight、thresholdを同じ履歴へ合わせて再探索しない。

config、registry、authoritative方向/confidence、Haar入り方向co-challenger、Pressure 0.52、Pressure + AR 0.55 shadow、fair odds、adoption/paper/live policyは変更しない。

## 成果物

- XGBoost OOS: `experiments/next_bar/walk_forward_xgboost_m30_fixed_001`
- normal/confidence blends: `experiments/next_bar/xgboost_m30_*_fixed_001`
- candidate分析: `experiments/next_bar/xgboost_m30_candidate_analysis.json`
- 既存候補との直接比較: `experiments/next_bar/xgboost*_vs_*_m30_*`
- direction/confidence bootstrap: `experiments/next_bar/xgboost_vs_baseline_m30_*_bootstrap*`
- rejected fixed confidence average: `experiments/next_bar/pressure_xgboost_equal_m30_confidence_fixed_001`
- fixed average comparison/bootstrap: `experiments/next_bar/pressure_xgboost_equal_vs_*`
- latest artifact check: `experiments/next_bar/xgboost_m30_latest_prediction.json`
