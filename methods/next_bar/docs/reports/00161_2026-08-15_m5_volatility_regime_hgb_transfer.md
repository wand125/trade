# 00161 M5 Volatility-regime HGB Fixed Transfer

日時: 2026-08-15 01:31 JST

## 目的

M15で校正診断shadowに限定したVolatility-regime HGBを、未検証のM5へ定義を変えず固定移植する。履歴OHLCをそのまま使わずbaseline 38加工特徴を使い、判定時点で既知の `volatility_20` に応じてlow / normal / high専用HGBへ分けることで、方向精度または信頼度順位付けに増分edgeが出るかを確認する。

## 固定仕様と資源品質

各foldのtrainだけで `volatility_20` の1/3、2/3分位点を求め、3局面へbaselineと同じHGBを独立学習した。境界はcalibration/testへ固定し、test分布で再計算していない。baseline 38特徴、class probability、後続calibration期間のPlatt、expanding train最大750,000行、全教師、uniform sample、標準損失1.0を固定した。

test2020〜test2026途中の7fold、439,881 OOS行をWindows canonical環境で学習し、baselineとtimestamp/targetを完全整列した。正式実験は単独worker、最大8 threads、nice 10、ionice 7、GPU非表示、memory/load gate付きで実行し、ComfyUI/Ollamaは停止していない。

## 単体方向と固定25% blend

| model | development accuracy | confirmation accuracy | all accuracy | all Brier | all log loss | all ECE |
|---|---:|---:|---:|---:|---:|---:|
| HGB baseline | 51.91385% | 51.03316% | 51.57463% | 0.249535053 | 0.692215561 | 0.36137% |
| Regime HGB単体 | 51.86763% | 50.92397% | 51.50416% | 0.249593431 | 0.692333363 | 0.25530% |
| baseline 75% + Regime 25% | 51.93418% | 51.00838% | 51.57759% | 0.249525628 | 0.692196798 | 0.28709% |

単体はbaseline比development -125件、confirmation -185件、all -310件、McNemar exact p=0.1881だった。accuracy 2/7fold、Brier/log loss各0/7foldで、ECEだけ5/7fold改善した。局面ごとに学習行を約1/3へ減らす不利を、関係差が上回っていない。

通常25%方向blendはbaseline比development +55件、confirmation -42件、all +13件に留まり、McNemar p=0.91448だった。既存Intrabar Pressure方向候補との比較でもall accuracy 51.57759%対51.59645%、selection score 0.017708対0.017809、年別accuracy/score各3/7対4/7で負けた。単体・通常方向とも採用しない。

## 方向維持confidence 0.515

baseline方向を固定し、Regime HGBを25%だけconfidenceへ混ぜた。閾値はdevelopment固定gridから0.515を一度だけ選び、confirmationを選択に使っていない。

| period | baseline rows / coverage / accuracy / score | Regime rows / coverage / accuracy / score |
|---|---:|---:|
| development | 158,280 / 58.52468% / 52.75588% / 0.0192008 | 155,285 / 57.41727% / 52.83253% / 0.0195814 |
| confirmation | 63,694 / 37.59288% / 52.36600% / 0.0121277 | 60,247 / 35.55843% / 52.50552% / 0.0125619 |
| all | 221,974 / 50.46228% / 52.64400% / 0.0173063 | 215,532 / 48.99780% / 52.74112% / 0.0177117 |

UTC日paired bootstrap 20,000回では、all lane accuracy差+0.09712ptの95%区間は+0.03292〜+0.16105pt、Wilson下限も改善側だった。一方coverage差-1.46449ptは-1.53666〜-1.39185ptで悪化し、selection score差+0.0004054の区間は-0.0000458〜+0.0008552で0を跨いだ。

all Brier差-0.000009175とlog loss差-0.000018260は改善側だったが、confirmationでは両方悪化点値となり区間も0を跨いだ。aggregate平滑化を安定した確率品質とは解釈しない。

## 既存broad候補との比較

| candidate | all rows | coverage | accuracy | selection score | all ECE |
|---|---:|---:|---:|---:|---:|
| Regime HGB confidence | 215,532 | 48.99780% | 52.74112% | 0.0177117 | 0.28585% |
| Intrabar Profile | 221,844 | 50.43273% | 52.68116% | 0.0175648 | 0.35587% |
| Profile x Transition | 210,936 | 47.95297% | 52.81175% | 0.0179952 | 0.23764% |

RegimeはProfileより点accuracyとECEを上げたが、coverageを減らしselection scoreは年別3/7しか勝てず、confirmationではProfileのscore 0.013020を0.012562へ下げた。Profile x Transitionにはaccuracy 1/7、selection score 3/7で、development、confirmation、allのaccuracy・score・Brier・log loss・ECEを総合して置換できない。校正診断役としてもProfile x TransitionのECEが全体・確認期間とも良いため、新しいshadowを追加しない。

## 高信頼度と局面別品質

固定0.55はall 21,184件、coverage 4.81585%、accuracy 55.91484%、selection score 0.011511だった。既存Directional Follow-throughは24,328件、5.53059%、56.19040%、0.013090で、Regimeはaccuracy/score各1/7foldしか勝てない。confirmationも648件・57.56173%・score 0.002302対940件・58.51064%・0.003972で、高信頼度roleへ使わない。

predicted up/down x low/normal/high volatilityの固定6セルを監査した。0.515はconfirmationの6セル中5セルで局所整合したが、down-normalは3,776件・50.6886%でWilson edge未確認だった。0.55のconfirmationはup-high 478件以外が3〜66件と極端に疎い。allではup-normal 3,429件が実測54.2141%に対しmean confidence 56.4027%で過信・局所不整合だった。同じ履歴からup-highだけを後付け採用せず、6セルを診断結果として保存する。

## 判断

M5 Volatility-regime HGBは、単体方向のaccuracy/proper score悪化、通常blendのconfirmation反転、既存方向・broad・high-confidence候補への劣後、局面内の疎さと期間driftにより全用途を再現専用とする。

新config、registry候補、latest artifact、authoritative予測、fair odds、paper/live policyを発行しない。分位境界、局面数、model parameter、25% weight、閾値、subgroup filterを同じ履歴へ合わせて再探索しない。M15の既存ECE診断shadowは独立に維持する。

## 検証

既存testはtrain-only分位境界、全行routing、artifact保存とlatest round-tripを覆い、Windowsで対象2件が成功した。全suiteは既知のEntry EV文書内部時刻1件だけを除外し、1,401件成功、1件除外、54.65秒だった。Macは共有中の高負荷処理へ追加負荷をかけないため全suiteを重ねなかった。

## 成果物

- OOS: `experiments/next_bar/regime_hgb_m5_windows_canonical_001`
- normal/confidence blends: `experiments/next_bar/regime_hgb_m5_{direction,confidence}_blend_windows_canonical_001`
- candidate分析: `experiments/next_bar/regime_hgb_m5_candidate_analysis.json`
- Pressure/Profile/Profile x Transition/Follow-through比較: `experiments/next_bar/regime_hgb_m5_vs_*.json`
- 20,000回bootstrap: `experiments/next_bar/regime_hgb_m5_confidence_vs_baseline_bootstrap_20000.json`
- subgroup reliability: `experiments/next_bar/regime_hgb_m5_confidence_subgroups.json`
