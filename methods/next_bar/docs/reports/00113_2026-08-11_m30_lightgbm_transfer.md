# 00113 M30 LightGBM Fixed Transfer

日時: 2026-08-11 14:40 JST

## 目的

加工済みbaseline 38特徴と教師・時系列分割を固定し、M1で有効だった異種学習器LightGBMを未検証のM30へparameter変更なしで移植した。HGBと異なるleaf-wise分割誤差が、M30方向またはconfidence rankingを補完するかを検証する。

## 事前監査

当初候補のrun-hazard特徴は、既存Path Persistenceのsigned streak・方向別persistenceとDirection Transition Stateのrun length・反転率・階層遷移に重複していた。独立指標にならないため実装・OOS前に中止した。履歴結果を見てrun定義を変えることも行わず、既に固定・実装済みでM30未検証だった学習器移植へ切り替えた。

## 固定仕様と品質

LightGBM 4.7.0、GBDT、31 leaves、300 trees、learning rate 0.03、min child 100、row/column sample 0.8、L2 5、seed 42、deterministic、force column-wise、early stoppingなし。特徴は生価格水準を含まないbaseline 38列、binary target、uniform sample、標準損失1.0、後続calibration期間のPlattを維持した。M1/M15実験からparameterを変更せず、M30履歴での探索はない。

test2020〜test2026途中の固定7fold、71,260 OOS行で正式baselineとtimestamp/targetを完全整列した。LightGBMは別CLI processで学習し、保存済み最終fold artifactから2026-06-01 04:30 UTCを再推論してup、probability up 52.4700%を確認した。empirical oddsはなく `odds_valid=false` である。

## 単体と25% blend

| model | development accuracy | confirmation accuracy | all accuracy | all Brier | all log loss |
|---|---:|---:|---:|---:|---:|
| HGB baseline | 51.98972% | 51.52019% | 51.80747% | 0.249497879 | 0.692142533 |
| LightGBM単体 | 51.99431% | 51.74433% | 51.89728% | 0.249454540 | 0.692054508 |
| baseline 75% + LightGBM 25% | 51.97367% | 51.67926% | 51.85939% | 0.249460140 | 0.692066407 |

単体はbaseline比development +2件、confirmation +62件、all +64件だったがaccuracyは4/7foldであり、単独置換に十分な安定性ではない。通常25% blendはdevelopment -7件、confirmation +44件、all +37件、accuracy 4/7、Brier/log loss 6/7fold。全体accuracyは現行Pressure + Ordinal Motif方向候補と同率で、開発は低いが確認は21件高く、all Brier/log lossも僅かに良かった。

## 固定方向多様化

現行baseline 75% + Pressure 12.5% + Ordinal Motif 12.5%候補とLightGBM通常25% blendを固定50/50平均した。最終weightはbaseline 75%、Pressure 6.25%、Ordinal Motif 6.25%、LightGBM 12.5%である。履歴からweightを探索していない。

| period | baseline accuracy | parent accuracy | equal candidate accuracy |
|---|---:|---:|---:|
| development | 51.98972% | 52.02184% | 52.02642% |
| confirmation | 51.52019% | 51.60334% | 51.65395% |
| all | 51.80747% | 51.85939% | 51.88184% |

equal candidateはbaseline比development +16件、confirmation +37件、all +53件。parent比development +2件、confirmation +14件、all +16件で5/7fold勝った。all Brier 0.249458633、log loss 0.692063369、ECE 0.0006533で、baselineとparentの点値をともに上回った。

20,000回UTC日bootstrapのbaseline比all accuracy差+0.07438ptは95%区間-0.04745〜+0.19749pt、改善確率88.51%で未確定だった。一方Brier差区間-0.00005756〜-0.00002104、log loss差-0.00011604〜-0.00004248は改善を支持した。parent比accuracy差+0.02245ptの区間は-0.07428〜+0.11772pt、Brier/log lossも0を跨いだため、parentの正式置換根拠にはしない。

## confidence

development grid最良0.515はcandidate scoreがbaselineとほぼ同じだったが、confirmationはaccuracy 53.1235%対baseline 53.2977%、score 0.014855対0.015815へ反転したため棄却した。

固定0.55ではLightGBMがdevelopment 3,822件・55.8870%、confirmation 960件・56.1458%、all 4,782件・55.9389%だった。既存Pressureよりselection score 6/7foldで高いがaccuracyは3/7で、前実験のPressure + AR shadowにはaccuracy 2/7、score 3/7だった。Pressure・AR・LightGBMの固定3等分も親shadowよりall accuracy 56.1423%→55.9698%、score 0.011629→0.011356、accuracy/score各2/7へ悪化した。LightGBM confidenceを採用せず、既存Pressure 0.52とPressure + AR 0.55 shadowを維持する。

## 判断

LightGBM単体、通常25% blend単独、0.515/0.55 confidence、3等分confidenceは再現専用とする。leaves、trees、learning rate、sampling、regularization、blend weight、thresholdをM30履歴へ合わせて再探索しない。authoritative方向/confidence、fair odds、adoption/paper/live policy、runtime latestは変更しない。

baseline 75% + Pressure 6.25% + Ordinal Motif 6.25% + LightGBM 12.5%だけを `m30_pressure_ordinal_lightgbm_direction_candidate_v1.json` のparallel direction co-challengerへ固定する。開発・確認の両方でbaselineとparentの点accuracyを上回り、baseline proper scoreはbootstrapでも改善したが、accuracy区間は0を跨ぎfull ensemble runtime parityも未発行である。現行Pressure + Ordinal Motif候補を維持し、完全未使用期間で両候補をhead-to-headする。

## 成果物

- LightGBM OOS: `experiments/next_bar/walk_forward_lightgbm_m30_fixed_001`
- normal/confidence blends: `experiments/next_bar/lightgbm_m30_*_fixed_001`
- candidate分析: `experiments/next_bar/lightgbm_m30_candidate_analysis.json`, `experiments/next_bar/lightgbm_m30_threshold_055_analysis.json`
- direction co-challenger: `experiments/next_bar/pressure_ordinal_lightgbm_equal_m30_direction_fixed_001`
- parent comparison/bootstrap: `experiments/next_bar/pressure_ordinal_lightgbm_equal_vs_pressure_ordinal_m30_direction_*`
- baseline bootstrap: `experiments/next_bar/pressure_ordinal_lightgbm_equal_vs_baseline_m30_direction_bootstrap.json`
- rejected confidence: `experiments/next_bar/lightgbm_vs_*_m30_fixed_055.json`, `experiments/next_bar/pressure_ar_lightgbm_equal_m30_confidence_fixed_001`
- latest artifact check: `experiments/next_bar/lightgbm_m30_latest_prediction.json`
- fixed config: `methods/next_bar/config/m30_pressure_ordinal_lightgbm_direction_candidate_v1.json`
