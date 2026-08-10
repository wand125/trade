# 00086 M1 Five-model Disagreement Confidence

日時: 2026-08-11 JST

## 目的

単一モデルの確率をそのまま信頼度とせず、異なる加工・学習器がbaseline方向へ与えるedgeの一致度を新しいconfidenceへ変換する。M15で固定済みの方向維持equal-mean仕様と0.515をM1へ移植し、既存TCN selective confidenceへcoverage・確率品質の増分があるか検証した。

## 固定仕様

完全整列した2,183,717 OOS行について、次の5モデルを等重みで使った。

1. baseline HGB
2. Path Persistence HGB
3. Extra Trees
4. LightGBM
5. causal TCN

baseline予測方向を `s`、各モデルのup確率を `p_i` とし、方向整列edge `e_i = s * (p_i - 0.5)` の平均を求めた。最終edgeは `max(mean(e_i), epsilon)` とし、方向はbaselineから変えない。M15 shadowからの固定移植なので、M1結果を見てmodel subset、weight、penalty、閾値を変更していない。損失倍率は標準1.0である。

## Baselineとの比較

| period | model | coverage | accuracy | selection score |
|---|---|---:|---:|---:|
| development | baseline 0.515 | 28.611% | 51.950% | 0.009587 |
| development | disagreement 0.515 | 26.915% | 52.161% | 0.010365 |
| confirmation | baseline 0.515 | 9.921% | 52.509% | 0.006837 |
| confirmation | disagreement 0.515 | 8.759% | 53.031% | 0.007904 |
| all | baseline 0.515 | 21.385% | 52.051% | 0.008820 |
| all | disagreement 0.515 | 19.896% | 52.309% | 0.009636 |

disagreementはaccuracy・selection scoreを6/7fold改善した。UTC日paired bootstrap 20,000回のaccuracy差95%区間はdevelopment +0.126〜+0.298pt、confirmation +0.300〜+0.741pt、all +0.178〜+0.338pt。selection scoreもdevelopment +0.000339〜+0.001235、confirmation +0.000389〜+0.001736、all +0.000452〜+0.001176で全て改善側だった。

方向をbaselineに固定したまま全行のBrierは0.24986888→0.24984746、log lossは0.69288487→0.69284188、ECEは0.2029%→0.1373%へ改善した。Brier/log lossの日次区間も3期間すべて改善側で、単なる閾値選別ではなく確率加工自体に情報がある。

## TCN 0.515との比較

| period | disagreement coverage / accuracy / score | TCN coverage / accuracy / score |
|---|---:|---:|
| development | 26.915% / 52.161% / 0.010365 | 25.802% / 52.159% / 0.010123 |
| confirmation | 8.759% / 53.031% / 0.007904 | 7.941% / 53.041% / 0.007506 |
| all | 19.896% / 52.309% / 0.009636 | 18.897% / 52.303% / 0.009348 |

disagreementはselection scoreを6/7fold、TCNはaccuracyを4/7foldで勝った。all coverage差は+0.999ptで日次95%区間も+0.950〜+1.048pt。accuracy差は-0.066〜+0.079ptで同等、selection score差は-0.000029〜+0.000608で僅かに0を跨ぐ。一方、all Brier差は-0.00000957〜-0.00000328、log loss差は-0.0000192〜-0.00000659でdisagreement改善側だった。

TCNを統計的に置換したとはいえないが、同等精度でcoverageを広げ、確率品質を改善する別の役割がある。TCNをselective accuracy specialist、disagreementをbalanced coverage/probability-quality confidence challengerとして並行固定する。

## 信頼度と固定subgroup

confirmation 0.515はaccuracy 53.031%に対しmean confidence 51.970%で、約1.060pt過小評価している。TCNも約1.070pt過小評価しており、disagreementだけの問題ではないが、fair oddsとしては局所不整合である。

方向×volatilityの固定6セルではconfirmationのdown-high、up-high、up-normalがWilson edgeを通った。down-low、down-normal、up-lowはsupportまたはedge不足で、特にdown-low 447行はaccuracy 49.888%、down-normal 2,749行は50.055%だった。この区分は監査用に固定して監視するが、今回の履歴から除外filterは作らない。

高閾値の参考値はconfirmation 0.525で8,526行・coverage 1.010%・accuracy 56.181%、0.535で1,418行・58.886%だった。ただし0.515が固定目的関数の主laneであり、高閾値を新たな採用ruleへ変換しない。

## 判断

`m1_disagreement_confidence_candidate_v1.json` にbalanced coverage/probability-quality selective-confidence challengerとして採用する。固定0.515はbaselineに対してdevelopment、confirmation、bootstrap、6/7foldで再現し、TCNと同等精度のままcoverageとproper scoreを改善した。

TCN 0.515はaccuracy specialistとして維持する。disagreementはauthoritative confidence、fair odds、売買policyを置換せず、runtimeで5モデル確率を同じ式へ通すparityが未検証なのでparallel forward candidateに限定する。完全未使用期間ではTCN以上のaccuracy、coverage、selection score、Brier、log lossと固定6セルを同時監視する。

同じ履歴でmodel subset、非等重み、penalty、0.515以外の採用閾値、side/regime filterを再探索しない。

## 成果物

- config: `methods/next_bar/config/m1_disagreement_confidence_candidate_v1.json`
- OOS: `experiments/next_bar/disagreement_confidence_m1_fixed_001`
- baseline comparison/bootstrap: `experiments/next_bar/disagreement_vs_baseline_m1_confidence_0515_analysis.json`, `experiments/next_bar/disagreement_vs_baseline_m1_confidence_0515_bootstrap.json`
- TCN comparison/bootstrap: `experiments/next_bar/disagreement_vs_tcn_m1_confidence_0515_analysis.json`, `experiments/next_bar/disagreement_vs_tcn_m1_confidence_0515_bootstrap.json`
- reliability: `experiments/next_bar/disagreement_vs_tcn_m1_confidence_reliability.json`
- fixed subgroups: `experiments/next_bar/disagreement_m1_confidence_subgroups.json`
