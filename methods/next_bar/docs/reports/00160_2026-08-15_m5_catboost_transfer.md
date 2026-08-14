# 00160 M5 CatBoost Fixed Transfer

日時: 2026-08-15 00:48 JST

## 目的

M1で通常方向blendのbaseline改善を確認し、M15では不採用だった固定CatBoostを、未検証のM5へ移植する。加工済みbaseline 38特徴、教師、時系列分割を変えず、Ordered symmetric treeがHGBと異なる方向またはconfidence edgeを持つかを確認する。

## 固定仕様と資源品質

CatBoost、Ordered boosting、symmetric depth 6、300 iteration、learning rate 0.03、L2 5、random strength 1、Bayesian bootstrap、bagging temperature 1、seed 42を固定した。expanding train最大750,000行、全教師、uniform sample、後続calibration期間のPlatt、標準損失1.0、baseline 38特徴を使った。test2020〜test2026途中の固定7fold、439,881 OOS行をWindows canonical環境で学習し、正式baselineとtimestamp/targetを完全整列した。

既存実装の `thread_count=-1` が共有WindowsのCPU方針を破るため `--catboost-thread-count` を追加した。pipeline testで設定値がreportと保存modelへ伝播することを確認し、正式実験は8 threads、単独worker、nice 10、ionice 7、GPU非表示、memory/load gate付きで実行した。ComfyUI/Ollamaは停止していない。

## 単体方向と固定25% blend

| model | development accuracy | confirmation accuracy | all accuracy | all Brier | all log loss | all ECE |
|---|---:|---:|---:|---:|---:|---:|
| HGB baseline | 51.91385% | 51.03316% | 51.57463% | 0.249535053 | 0.692215561 | 0.36137% |
| CatBoost単体 | 51.87207% | 50.93814% | 51.51234% | 0.249553591 | 0.692253032 | 0.41273% |
| baseline 75% + CatBoost 25% | 51.90904% | 51.00129% | 51.55940% | 0.249528769 | 0.692203039 | 0.36540% |

単体はbaseline比development -113件、confirmation -161件、all -274件、McNemar p=0.12993、accuracy 2/7、Brier/log loss各1/7foldだった。通常25%方向blendも-13/-54/-67件、p=0.45555、accuracy/Brier/log loss各3/7foldだった。

既存Intrabar Pressure方向blendにaccuracy 2/7、all accuracy -0.03706ptで、Brier/log loss/ECEも悪い。単体・通常方向とも採用しない。

## 方向維持confidence 0.515

development gridだけで0.515を選んだ。

| period | baseline rows / coverage / accuracy / score | CatBoost rows / coverage / accuracy / score |
|---|---:|---:|
| development | 158,280 / 58.52468% / 52.75588% / 0.0192008 | 158,028 / 58.43150% / 52.79191% / 0.0194595 |
| confirmation | 63,694 / 37.59288% / 52.36600% / 0.0121277 | 62,833 / 37.08471% / 52.48357% / 0.0127455 |
| all | 221,974 / 50.46228% / 52.64400% / 0.0173063 | 220,861 / 50.20926% / 52.70419% / 0.0176857 |

baseline比ではaccuracy/score各5/7fold、Brier 4/7、log loss 3/7、ECE 5/7だった。UTC日paired bootstrap 20,000回ではall accuracy差+0.06019ptの95%区間+0.00873〜+0.11326pt、score差+0.0003794は+0.0000144〜+0.0007553、Brier差-0.000006024とlog loss差-0.000012000も改善側だった。confirmation accuracy差+0.11757ptの区間も+0.00976〜+0.22606ptだったが、scoreとproper scoreは0を跨ぎ、coverage差-0.50817ptだけ悪化が確定した。

加工済みbaseline特徴をCatBoostへ通すと、方向を変えずconfidence順位付けを改善できること自体は再現した。

## 既存broad候補との比較

| period | CatBoost rows / coverage / accuracy / score | Profile rows / coverage / accuracy / score | Profile×Transition rows / coverage / accuracy / score |
|---|---:|---:|---:|
| development | 158,028 / 58.43150% / 52.79191% / 0.0194595 | 158,360 / 58.55426% / 52.74754% / 0.0191423 | 151,362 / 55.96672% / 52.91355% / 0.0199147 |
| confirmation | 62,833 / 37.08471% / 52.48357% / 0.0127455 | 63,484 / 37.46894% / 52.51559% / 0.0130197 | 59,574 / 35.16122% / 52.55313% / 0.0127606 |
| all | 220,861 / 50.20926% / 52.70419% / 0.0176857 | 221,844 / 50.43273% / 52.68116% / 0.0175648 | 210,936 / 47.95297% / 52.81175% / 0.0179952 |

CatBoostはProfileへdevelopment点値を上げたがconfirmationで反転し、accuracy/score各2/7foldだった。20,000回bootstrapのall accuracy差+0.02303ptの95%区間は-0.03104〜+0.07773pt、score差+0.0001210も-0.0002617〜+0.0005077で未確定だった。一方coverage差-0.22347ptは-0.28216〜-0.16412pt、Brier差+0.000007313は+0.000001556〜+0.000013218、log loss差+0.000014717は+0.000003145〜+0.000026591でCatBoostの悪化が確定した。

Profile×Transitionにはaccuracy 1/7、selection score 3/7fold、all accuracy -0.10756pt、score -0.0003095、Brier/log loss/ECEも悪い。既存broad roleへ採用しない。

## 高信頼度と校正

固定0.55は23,787件、coverage 5.40760%、accuracy 56.08105%、score 0.0126722だった。Follow-throughは24,328件、5.53059%、56.19040%、0.0130897で、CatBoostはaccuracy 3/7、selection score 1/7foldしか勝てない。confirmationも733件・57.98090%・score 0.0028777対940件・58.51064%・0.0039719で、高信頼度roleへ使わない。

CatBoostの固定confidence band accuracyはdevelopment/confirmation/allで単調だった。confirmation 0.515は62,833件、実測52.48357%、mean confidence 52.47412%で局所整合し、0.55は733件、57.98090%対55.46145%でedgeを過小評価した。一方development 0.515は52.79191%対53.36718%で過信・不整合だった。期間間の局所校正driftが残り、authoritative oddsへ使わない。

## 判断

M5 CatBoostはbaselineへの0.515 confidence改善を異種学習器感度として保存する。しかしProfileへのconfirmation反転、coverage/proper score悪化、Profile×Transitionのaccuracy、Follow-through 0.55を超えず、新しいaccuracy×coverage frontierを作らない。

単体、通常方向、0.515/0.55を再現専用とし、新config、registry候補、latest artifact、authoritative予測、fair odds、paper/live policyを発行しない。depth、iteration、learning rate、random strength、bagging temperature、25% weight、閾値、subgroup filterを同じ履歴で再探索しない。

## 検証

WindowsでCatBoost thread countのpipeline testが成功した。全suiteは既知のEntry EV文書内部時刻1件だけを除外し、1,401件成功、1件除外、53.09秒だった。Macは共有中の高負荷処理へ追加負荷をかけないため全suiteを重ねず、Windows canonical結果を採用した。

## 成果物

- OOS: `experiments/next_bar/catboost_m5_windows_canonical_001`
- normal/confidence blends: `experiments/next_bar/catboost_m5_{direction,confidence}_blend_windows_canonical_001`
- candidate分析: `experiments/next_bar/catboost_m5_candidate_analysis.json`
- Pressure/Profile/Profile×Transition/Follow-through比較: `experiments/next_bar/catboost_vs_*_m5_*_analysis.json`
- 20,000回bootstrap: `experiments/next_bar/catboost_vs_baseline_m5_confidence_0515_daily_bootstrap.json`, `catboost_vs_profile_m5_confidence_0515_daily_bootstrap.json`
- reliability: `experiments/next_bar/catboost_vs_profile_m5_confidence_reliability.json`
