# 00115 M30 Haar Multiscale Fixed Transfer

日時: 2026-08-11 15:05 JST

## 目的

価格履歴をそのまま渡さず、直近経路の加速・減速・反転を複数scaleの前半対後半差へ圧縮するHaar MultiscaleをM30へ固定移植した。M1で方向blendを7/7fold改善し、M15では不採用だった時間足依存の加工が、M30の約2〜16時間構造と既存Pressure・Ordinal Motifを補完するか検証した。

## 固定仕様と品質

4/8/16/32本の各窓を前半・後半へ分け、volatility標準化return差、absolute-return構成差、方向平均差の固定12列を作る。M30ではおよそ2/4/8/16時間の変化に対応する。完全無変動窓の0/0は変化なしの0とし、生OHLC価格水準、volume、未来足、targetは特徴へ使わない。

HGB 200 iteration、learning rate 0.05、31 leaves、min leaf 100、L2 1、expanding、uniform sample、全教師、Platt、標準損失1.0を固定した。M1/M15からwindow、列、parameter、25% weightを変更せず、M30履歴で探索していない。test2020〜test2026途中の固定7fold、71,260 OOS行でbaselineとtimestamp/targetを完全整列した。

最終fold artifactから2026-06-01 04:30 UTCを再推論し、up、probability up 52.6354%を確認した。経験的オッズ検証はないため `odds_valid=false` である。

## 単体と固定25% blend

| model | development accuracy | confirmation accuracy | all accuracy | all Brier | all log loss | all ECE |
|---|---:|---:|---:|---:|---:|---:|
| HGB baseline | 51.98972% | 51.52019% | 51.80747% | 0.249497879 | 0.692142533 | 0.16084% |
| Haar単体 | 52.17321% | 51.66841% | 51.97727% | 0.249470190 | 0.692086596 | 0.04522% |
| baseline 75% + Haar 25% | 52.08147% | 51.56357% | 51.88044% | 0.249458973 | 0.692064352 | 0.06170% |

Haar単体はbaseline比development +80件、confirmation +41件、all +121件、accuracy 5/7fold。25% blendはdevelopment +40件、confirmation +12件、all +52件、accuracy/Brier/log loss各5/7foldだった。通常blendは現行Pressure + Ordinal + LightGBM co-challengerよりall -1件でconfirmationも弱いため採用しない。

Haar単体−baselineの日次bootstrap 20,000回ではall accuracy差+0.1698ptの95%区間は-0.1079〜+0.4484pt、改善確率88.10%で未確定だった。Brier/log lossも点値は改善したが区間は0を跨いだ。Haar単体は現行co-challengerをdevelopment +64件、confirmation +4件、all +68件、年別4/7で上回ったが、直接accuracy/proper score区間は全て0を跨いだ。Extra Trees単体にはall +49件、年別5/7で勝つ一方、proper scoreはExtra Trees寄りだった。

## 固定方向多様化

精度寄りHaar単体と、確率品質寄りの現行baseline 75% + Pressure 6.25% + Ordinal 6.25% + LightGBM 12.5% co-challengerを固定50/50平均した。最終weightはbaseline HGB 37.5%、Pressure HGB 3.125%、Ordinal HGB 3.125%、LightGBM 6.25%、Haar HGB 50%である。50/50以外を探索していない。

| period | baseline | current co-challenger | Haar単体 | equal candidate |
|---|---:|---:|---:|---:|
| development | 51.98972% | 52.02642% | 52.17321% | 52.19386% |
| confirmation | 51.52019% | 51.65395% | 51.66841% | 51.67564% |
| all | 51.80747% | 51.88184% | 51.97727% | 51.99270% |

equal candidateはbaseline比development +89件、confirmation +43件、all +132件、accuracy 6/7fold。current co-challenger比development +73件、confirmation +6件、all +79件、accuracy 5/7fold。Haar単体比も+9/+2/+11件、4/7foldで、all Brier 0.249427476、log loss 0.692000846へ改善した。

baseline比all accuracy差+0.1852ptの日次95%区間は-0.0224〜+0.3928pt、改善確率95.93%で僅かに0を跨いだ。一方Brier差区間-0.00012372〜-0.00001847、log loss差-0.00024876〜-0.00003718は改善を支持した。current co-challenger比accuracy差+0.1109ptの区間は-0.0836〜+0.3016ptで、proper score差も0を跨いだためparentの正式置換根拠にはしない。

## confidence

Haar方向維持blendはdevelopment grid最良0.515でもbaselineよりaccuracy、coverage、selection scoreが低く、confirmationでも反転を解消しなかった。固定0.52では既存Pressureにaccuracy 1/7、score 2/7foldだった。

equal direction candidateの0.55はall 4,453件、coverage 6.2489%、accuracy 56.3216%、score 0.012149で、Pressure + AR shadowの56.1423%、6.1914%、0.011629を点値で上回った。しかしconfirmationはaccuracy 56.4067%でもcoverageが2.5957%へ下がり、score 0.004439対0.004997、年別accuracy/score各3/7対4/7だった。履歴内で見つかった方向候補のtailをconfidence採用へ二重利用せず、Pressure + AR shadowを維持する。

## 判断

Haar単体、通常25% blend、Haar 0.515/0.52/0.55 confidenceは再現・構成要素専用とする。window、系列、HGB parameter、blend weight、thresholdを同じM30履歴へ合わせて再探索しない。authoritative方向/confidence、現行Pressure + Ordinal + LightGBM co-challenger、Pressure + AR confidence shadow、fair odds、adoption/paper/live policyは変更しない。

固定50/50 equal candidateだけを `m30_pressure_ordinal_lightgbm_haar_direction_candidate_v1.json` のparallel direction co-challengerへ固定する。baselineに対して開発・確認の方向点値、6/7fold、bootstrapでのproper scoreを改善し、current co-challengerにも5/7foldで勝った。ただしaccuracy区間とparent直接差は未確定でfull ensemble runtime parityも未発行である。完全未使用期間でbaseline、parent、Haar単体へhead-to-headする。

## 成果物

- Haar OOS: `experiments/next_bar/walk_forward_haar_multiscale_m30_fixed_001`
- normal/confidence blends: `experiments/next_bar/haar_multiscale_m30_*_fixed_001`
- candidate分析: `experiments/next_bar/haar_multiscale_m30_candidate_analysis.json`
- Haar direct comparisons/bootstrap: `experiments/next_bar/haar_*_m30_*`
- fixed equal candidate: `experiments/next_bar/pressure_ordinal_lightgbm_haar_equal_m30_direction_fixed_001`
- equal comparisons/bootstrap: `experiments/next_bar/pressure_ordinal_lightgbm_haar_equal_vs_*`
- rejected confidence: `experiments/next_bar/haar_vs_pressure*_m30_confidence_fixed_*.json`, `experiments/next_bar/pressure_ordinal_lightgbm_haar_equal_vs_pressure_ar_m30_confidence_fixed_055.json`
- latest artifact check: `experiments/next_bar/haar_multiscale_m30_latest_prediction.json`
- fixed config: `methods/next_bar/config/m30_pressure_ordinal_lightgbm_haar_direction_candidate_v1.json`
