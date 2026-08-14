# 00159 M5 XGBoost Fixed Transfer

日時: 2026-08-15 00:25 JST

## 目的

M1で通常方向blendの改善を確認し、M15/M30では不採用だった固定XGBoostを、未検証のM5へ移植する。加工済みbaseline 38特徴、教師、時系列分割を変えず、depth制約付きboosted treeがHGBと異なる方向またはconfidence edgeを持つかを確認する。

## 固定仕様と資源品質

XGBoost、300 trees、depth 4、learning rate 0.03、min child weight 20、row/column sample 0.8、L2 5、hist tree method、seed 42を固定した。expanding train最大750,000行、全教師、uniform sample、後続calibration期間のPlatt、標準損失1.0、baseline 38特徴を使った。test2020〜test2026途中の固定7fold、439,881 OOS行をWindows canonical環境で学習し、正式baselineとtimestamp/targetを完全整列した。

既存実装の `n_jobs=-1` が共有WindowsのCPU方針を破るため `--xgboost-n-jobs` を追加した。pipeline testでCLI値がreportと保存modelへ伝播することを確認し、正式実験は8 jobs、単独worker、nice 10、ionice 7、GPU非表示、memory/load gate付きで実行した。ComfyUI/Ollamaは停止していない。

## 単体方向と固定25% blend

| model | development accuracy | confirmation accuracy | all accuracy | all Brier | all log loss | all ECE |
|---|---:|---:|---:|---:|---:|---:|
| HGB baseline | 51.91385% | 51.03316% | 51.57463% | 0.249535053 | 0.692215561 | 0.36137% |
| XGBoost単体 | 51.90202% | 51.01605% | 51.56076% | 0.249543364 | 0.692232576 | 0.34980% |
| baseline 75% + XGBoost 25% | 51.93307% | 51.02254% | 51.58236% | 0.249530325 | 0.692206181 | 0.34139% |

単体はbaseline比development -32件、confirmation -29件、all -61件、McNemar p=0.70584、accuracy 3/7、Brier/log loss各2/7foldだった。通常25%方向blendは+52/-18/+34件、p=0.67460、accuracy 3/7、Brier/log loss各4/7foldで、confirmation方向が反転した。

既存Intrabar Pressure方向blendはdevelopment 51.94417%、confirmation 51.04143%、all 51.59645%で、XGBoost blendはaccuracy 3/7、all Brier/log loss/ECEも悪い。方向用途へ採用しない。

## 方向維持confidence 0.515

development gridだけで0.515を選んだ。

| period | XGBoost rows / coverage / accuracy / score | Profile rows / coverage / accuracy / score | Profile×Transition rows / coverage / accuracy / score |
|---|---:|---:|---:|
| development | 157,729 / 58.32095% / 52.75885% / 0.0191867 | 158,360 / 58.55426% / 52.74754% / 0.0191423 | 151,362 / 55.96672% / 52.91355% / 0.0199147 |
| confirmation | 63,164 / 37.28007% / 52.49984% / 0.0128847 | 63,484 / 37.46894% / 52.51559% / 0.0130197 | 59,574 / 35.16122% / 52.55313% / 0.0127606 |
| all | 220,893 / 50.21654% / 52.68478% / 0.0175496 | 221,844 / 50.43273% / 52.68116% / 0.0175648 | 210,936 / 47.95297% / 52.81175% / 0.0179952 |

baseline比ではdevelopment scoreが僅かに低く、confirmationでaccuracy/scoreを上げ、all accuracy +0.04078pt、score +0.0002433となった。accuracy/score各5/7、Brier/log loss各4/7、ECE 5/7foldである。

親Profileにはaccuracy/score各5/7foldだが、all accuracy差は+0.00362pt、score差-0.0000152で実質同値だった。UTC日paired bootstrap 20,000回のall accuracy差95%区間は-0.04951〜+0.05651pt、score差は-0.0003918〜+0.0003601で0を跨いだ。一方coverage差-0.21619ptの区間は-0.27001〜-0.16222pt、Brier差+0.000008912は+0.000003680〜+0.000014175、log loss差+0.000017946は+0.000007431〜+0.000028531で、XGBoostのcoverage/proper score悪化が確定した。

Profile×Transitionにはaccuracy 2/7、selection score 3/7fold、all accuracy -0.12697pt、score -0.0004457、Brier/log loss/ECEも悪い。broad confidenceへ採用しない。

## 高信頼度0.55

| period | XGBoost rows / coverage / accuracy / score | Follow-through rows / coverage / accuracy / score |
|---|---:|---:|
| development | 23,065 / 8.52838% / 56.18036% / 0.0161759 | 23,388 / 8.64781% / 56.09714% / 0.0160568 |
| confirmation | 815 / 0.48102% / 58.15951% / 0.0032890 | 940 / 0.55480% / 58.51064% / 0.0039719 |
| all | 23,880 / 5.42874% / 56.24791% / 0.0130892 | 24,328 / 5.53059% / 56.19040% / 0.0130897 |

XGBoostはaccuracy/score各4/7fold、all accuracy +0.05751ptだがselection score差は-0.0000005で同値だった。20,000回bootstrapのall accuracy差95%区間は-0.15121〜+0.26533pt、score差は-0.0004923〜+0.0004863で未確定である。coverage差-0.10185ptは-0.12613〜-0.07781pt、Brier/log loss悪化も区間全体で確定した。confirmationもaccuracy -0.35113pt、score -0.0006829へ反転したため、high-confidence roleへ採用しない。

## 信頼度品質

XGBoostの固定confidence band accuracyはdevelopment/confirmation/allの全期間で単調だった。confirmation 0.515は63,164件、実測52.49984%、mean confidence 52.47592%で局所整合し、0.55も815件、58.15951%対55.49778%でedgeを過小評価した。development 0.515は52.75885%対53.37065%で過信・不整合だった。

confidenceが強くなるほど正答率が上がる基本形は確認できたが、Profileと同じ方向・ほぼ同じ選択集合で、既存候補以上のaccuracy×coverageやproper scoreは作れない。全体比較で採用gateを満たさないため、方向×volatility cell、別threshold、固定平均、別weightを履歴へ合わせて探索しない。

## 判断

M5 XGBoostは単体、通常方向、0.515 broad、0.55 high-confidenceを全て再現専用とする。方向はPressure、broad confidenceはProfileとProfile×Transition、高信頼度はFollow-throughが同じ役割で上回る。

新config、registry候補、latest artifact、authoritative予測、fair odds、paper/live policyを発行しない。300 trees、depth 4、学習率0.03、min child weight 20、row/column 0.8、L2 5、25% weight、0.515/0.55を同じ履歴で再探索しない。

## 検証

WindowsでXGBoost job数のpipeline testが成功した。全suiteは既知のEntry EV文書内部時刻1件だけを除外し、1,401件成功、1件除外、55.05秒だった。Macは共有中の高負荷処理へ追加負荷をかけないため全suiteを重ねず、Windows canonical結果を採用した。

## 成果物

- OOS: `experiments/next_bar/xgboost_m5_windows_canonical_001`
- normal/confidence blends: `experiments/next_bar/xgboost_m5_{direction,confidence}_blend_windows_canonical_001`
- candidate分析: `experiments/next_bar/xgboost_m5_candidate_analysis.json`
- Pressure/Profile/Profile×Transition/Follow-through比較: `experiments/next_bar/xgboost_vs_*_m5_*_analysis.json`
- 20,000回bootstrap: `experiments/next_bar/xgboost_vs_profile_m5_confidence_0515_daily_bootstrap.json`, `xgboost_vs_follow_through_m5_confidence_055_daily_bootstrap.json`
- reliability: `experiments/next_bar/xgboost_vs_profile_m5_confidence_reliability.json`
