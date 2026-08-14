# 00157 M5 Extra Trees Fixed Transfer

日時: 2026-08-14 23:42 JST

## 目的

M1で方向blendの安定性、M15でconfidence補完、M30で単体proper score感度を確認した異種学習器Extra Treesを、未検証だったM5へ固定移植する。加工済みbaseline 38特徴、教師、時系列分割を変えず、HGBと異なるランダム化木の誤りが方向または信頼度を補完するかを確認する。

## 固定仕様と資源品質

M1/M15/M30と同じExtra Trees 200本、max depth 12、min leaf 50、max features 0.75、seed 42、expanding train最大750,000行、全教師、uniform sample、後続calibration期間のPlatt、標準損失1.0を固定した。生OHLC価格水準を含まないbaseline 38特徴を使い、M5結果を見てtree parameter、blend weight、閾値、subgroup filterを変更していない。

最初の実行で `ExtraTreesClassifier(n_jobs=-1)` が低優先度workerの8-thread環境変数を無視し、約18 CPU coreを使用することを検出した。今回のプロセスだけを中断し、生成済みtest2020〜2022 artifactは `extra_trees_m5_aborted_overthread_001` へ退避した。`--extra-trees-n-jobs` を追加して2-jobのpipeline testを通し、8 jobs明示で全foldを最初から再実行した。再実行はnice 10、ionice 7、GPU非表示、memory/load/singleton gateを維持し、ComfyUI/Ollamaを停止していない。

test2020〜test2026途中の固定7fold、439,881 OOS行で正式Windows baselineとtimestamp/targetを完全整列した。

## 単体方向と固定25% blend

| model | development accuracy | confirmation accuracy | all accuracy | all Brier | all log loss | all ECE |
|---|---:|---:|---:|---:|---:|---:|
| HGB baseline | 51.91385% | 51.03316% | 51.57463% | 0.249535053 | 0.692215561 | 0.36137% |
| Extra Trees単体 | 51.96857% | 51.06563% | 51.62078% | 0.249550651 | 0.692247621 | 0.29292% |
| baseline 75% + Extra Trees 25% | 51.93381% | 51.03021% | 51.58577% | 0.249525922 | 0.692197411 | 0.32861% |

単体はbaseline比development +148件、confirmation +55件、all +203件だが、方向accuracyは4/7fold、McNemar p=0.291、Brier/log lossは各2/7foldだった。通常25% blendは+54/-5/+49件、accuracy 4/7、proper score 5/7foldで、confirmation方向が反転した。

単体は既存Intrabar Pressure方向blendへall +107件でも年別3/7、Brier/log lossは悪化した。単体方向、通常25%方向とも既存方向roleを置換しない。

## 方向維持confidence 0.515

development gridだけで0.515を選んだ。

| period | baseline rows / coverage / accuracy / score | Extra Trees rows / coverage / accuracy / score |
|---|---:|---:|
| development | 158,280 / 58.52468% / 52.75588% / 0.0192008 | 158,118 / 58.46478% / 52.83206% / 0.0197727 |
| confirmation | 63,694 / 37.59288% / 52.36600% / 0.0121277 | 62,928 / 37.14078% / 52.43453% / 0.0124580 |
| all | 221,974 / 50.46228% / 52.64400% / 0.0173063 | 221,046 / 50.25132% / 52.71889% / 0.0177980 |

accuracyは7/7fold、selection scoreは6/7fold、Brier/log loss/ECEは各5/7fold改善した。UTC日paired bootstrap 20,000回ではbaseline比all accuracy差+0.07489ptの95%区間+0.02099〜+0.12887pt、score差+0.000492は+0.000111〜+0.000875、Brier/log lossも改善側だった。一方coverage差-0.21097ptは悪化側で、confirmation単独のaccuracy/score/proper score区間は0を跨いだ。

親Profile 0.515にはaccuracy/score各5/7fold、developmentはaccuracy/score改善区間が確定したが、confirmationはaccuracy -0.08107pt、coverage -0.32816pt、score -0.0005618へ反転した。all直接差は未確定で、coverage低下だけが確定した。

現行Profile×Transition broad shadowとの比較は次の通りである。

| candidate | all coverage | all accuracy | all score | all Brier |
|---|---:|---:|---:|---:|
| Extra Trees 0.515 | 50.25132% | 52.71889% | 0.0177980 | 0.249525818 |
| Profile×Transition 0.515 | 47.95297% | 52.81175% | 0.0179952 | 0.249513819 |

Extra Treesはcoverage +2.29835ptの区間が改善側だが、accuracy -0.09286ptの95%区間は-0.16185〜-0.02411pt、Brier/log lossも悪化側だった。score差区間は0を跨ぎ、年別accuracy 2/7、score 3/7である。固定50/50 confidence平均もProfile×Transitionへaccuracy 1/7、score 2/7、all score 0.0176762へ悪化したため棄却し、別weightを探索しない。

## 高信頼度と局所校正

固定0.55は23,266件、coverage 5.28916%、accuracy 56.03885%、score 0.0124193だった。既存Follow-throughは24,328件、5.53059%、56.19040%、0.0130897で、Extra Treesはaccuracy 2/7、score 1/7しか勝てないためprecision roleへ使わない。

development、confirmation、allの固定confidence band accuracyはすべて閾値上昇に対して単調だった。confirmation 0.515は62,928件、実測52.43453%、mean confidence 52.46666%でglobal整合した。一方down×normalは4,157件、accuracy 50.06014%、mean confidence 52.08431%、Wilson edge未確認かつ局所不整合だった。Profile×Transitionも同セルのedgeは未確認だがaccuracy 50.85158%であり、Extra Treesへの置換根拠はない。結果後のcell filterは作らない。

## runtime parity

共有計算機向けに `--extra-trees-n-jobs` を実装した。また、latest ensemble parityは異種学習器を既定で拒否したまま、`--allow-heterogeneous-models` を明示した場合だけmodel type差を監査記録へ残して許可するようにした。split、教師、校正、seed、train設定の一致guardは維持し、対象3テストを通した。

既存baseline latestと同一splitでExtra Trees latest artifactを生成し、HGB/Extra Trees以外の全主要設定一致を確認した。2026-06-01 04:55 UTCはup、baseline `p(up)=0.5332709162`、Extra Trees `0.5373312496`、方向維持25% blend `0.5342859995` だった。経験的オッズを認可していないため `odds_valid=false`、`strict_prediction_eligible=false` である。

## 判断

M5 Extra Treesは、baselineに対する0.515 confidence改善を異種学習器感度として保存する。しかしconfirmation単独の統計gate、Profileの確認期間、Profile×Transitionのaccuracy/proper score、Follow-through 0.55、down-normal局所edgeを超えない。単体方向、通常方向、0.515/0.55、Profile×Transitionとの固定平均を再現専用とし、新config・registry候補を発行しない。

Profile×Transition broad shadow、Profile broad候補、Pressure方向、Follow-through high-confidence shadow、authoritative予測、fair odds、paper/live policyを変更しない。200 trees、depth 12、min leaf 50、max features 0.75、25% weight、0.515/0.55、subgroup filterを同履歴で再探索しない。

## 検証

WindowsでExtra Trees thread設定と異種artifact parityの対象3テストが成功した。全suiteは既知のEntry EV文書内部時刻1件だけを除外し、1,401件成功、1件除外、55.85秒だった。Macは共有中の高負荷処理へ追加負荷をかけないため全suiteを重ねず、Windows canonical結果を採用した。

## 成果物

- OOS: `experiments/next_bar/extra_trees_m5_windows_canonical_001`
- normal/confidence blends: `experiments/next_bar/extra_trees_m5_{direction,confidence}_blend_windows_canonical_001`
- candidate分析: `experiments/next_bar/extra_trees_m5_candidate_analysis.json`
- baseline/Profile/Profile×Transition比較・20,000回bootstrap: `experiments/next_bar/extra_trees_vs_*_m5_*`
- rejected equal blend: `experiments/next_bar/profile_transition_extra_trees_equal_m5_confidence_windows_canonical_001`
- reliability/subgroup: `experiments/next_bar/extra_trees_*m5*reliability.json`, `extra_trees_m5_confidence_subgroups.json`
- latest artifact/prediction/parity: `experiments/next_bar/extra_trees_m5_latest_{artifact,prediction,parity}*`
- resource audit: `experiments/next_bar/extra_trees_m5_aborted_overthread_001`
