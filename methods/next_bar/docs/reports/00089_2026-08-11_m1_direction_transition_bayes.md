# 00089 M1 Direction Transition Bayes と confidence guard

日時: 2026-08-11 05:35 JST

## 目的

加工済み履歴を汎用木へ渡す流れとは別に、直近の方向遷移状態から次足up確率を直接推定する小標本向け学習器を固定比較した。方向、確率品質、0.515高信頼選別を分離し、coverageとWilson下限を合わせた既定評価関数を最大化する。

## 固定仕様と品質

状態は現在方向 `{-1,0,+1}`、連続方向本数を0〜4へcapしたrun length、直近8本の非flat遷移に占める反転率3区分、5本/20本volatility比のlow/normal/highで構成する。生OHLC価格水準とvolumeは使わない。135 encoded slotのうち構造的に到達可能なのは81状態で、各foldは81/81状態と9/9親状態を観測した。

全体up率へ親状態をprior strength 256で縮約し、親確率へ完全状態を64で縮約する階層ベイズ二項推定を固定した。結果を見てstate分割、prior、25% blend、Platt、0.515を変更していない。scale不変、未来変更不変、flat有限0、artifact保存・別process読込、latest推論、決定時刻/target/foldのbaseline完全一致を検証した。

7fold OOSは2,183,717行。到達可能状態のfold別中央値は約1,907〜1,987行で、疎状態を単純実績率として扱わず階層縮約した。

## 単体と方向25% blend

遷移モデル単体accuracyは50.4655%、Brier 0.2499596、log loss 0.6930664で方向用途には弱い。通常25% blendはbaselineに対して全体+89件、accuracy 50.8110%、Brier 0.2498576、log loss 0.6928621となった。

accuracy差の日次bootstrap 95%区間は-0.0274〜+0.0358ptで未確定。一方、Brier差は-0.00001626〜-0.00000633、log loss差は-0.00003268〜-0.00001274で改善が確定した。ただしSession Relative 25%がaccuracy 50.8374%、Brier 0.2498561、log loss 0.6928593で点優位、直接差も遷移側の新しい役割を支持しない。方向候補には採用しない。

## 元の方向維持confidence

baseline方向を変えず、baseline 75% + 遷移Bayes 25%のedge強度だけをconfidenceにした。

| period | accuracy | coverage | selection score |
|---|---:|---:|---:|
| development | 52.2278% | 21.4216% | 0.009465 |
| confirmation | 53.3546% | 6.1526% | 0.007256 |
| all | 52.4006% | 15.5185% | 0.008794 |

0.515でTCNより全期間accuracy +0.0978ptだがcoverage -3.3786pt、score -0.000554。accuracy差95%区間は+0.0088〜+0.1855pt、score差は-0.000922〜-0.000195で、精度とcoverage目的のtrade-offだった。Disagreementにはaccuracy差区間が僅かに0を跨ぎ、coverage -4.3774pt、score -0.000842、Brier/log loss悪化が確定したため、元confidenceは採用しない。

累積accuracyは全期間で0.515=52.4006%、0.525=53.5081%、0.535=54.2687%、0.55=55.9882%と上昇した。確認期間も0.515〜0.535は上昇したが、0.55は16件だけで独立edgeを確認できない。

## development-only subgroup guard

固定6セルをdevelopmentだけで監査すると、`predicted_direction=up × volatility_regime=low` は0.515以上29,394件、accuracy 50.6022%、mean confidence 52.1284%で唯一大きく過信していた。このセルだけconfidenceを0.5へ落としてabstainするルールを固定し、その後confirmationを監査した。confirmationでも同セルは1,208件、accuracy 50.4967%でedge未確認だった。

guard後は元遷移confidenceに対し次のように改善した。

| period | raw accuracy / coverage / score | guard accuracy / coverage / score |
|---|---:|---:|
| development | 52.2278% / 21.4216% / 0.009465 | 52.4134% / 19.2271% / 0.009736 |
| confirmation | 53.3546% / 6.1526% / 0.007256 | 53.4227% / 6.0096% / 0.007326 |
| all | 52.4006% / 15.5185% / 0.008794 | 52.5795% / 14.1171% / 0.009029 |

全期間のguard−raw accuracy差95%区間は+0.1222〜+0.2373pt、score差は+0.0000295〜+0.0004402で両方改善が確定した。ただしguard単体はDisagreementのscoreを下回る。

## Disagreementとの固定confidence blend

Disagreementをbase、guard済み遷移confidenceをcontributorとし、0.515固定のままdevelopment selection scoreだけでweightを選んだ。記録したgrid `0, 0.1, 0.2, 0.25, 0.3, 0.4, 0.5, 0.6, 0.7, 0.75, 0.8, 0.9, 1.0` ではcontributor 0.5がdevelopment最大0.0104465だった。confirmation指標は選択に使っていない。

| period | Disagreement accuracy / coverage / score | 50/50 blend accuracy / coverage / score |
|---|---:|---:|
| development | 52.1609% / 26.9153% / 0.010365 | 52.4249% / 21.6867% / 0.010447 |
| confirmation | 53.0306% / 8.7589% / 0.007904 | 53.3560% / 7.0236% / 0.007829 |
| all | 52.3089% / 19.8959% / 0.009636 | 52.5827% / 16.0178% / 0.009674 |

Disagreement比accuracyは7/7foldで勝ち、全期間差95%区間+0.1927〜+0.3578pt。scoreは2/7foldで、全期間差区間-0.000294〜+0.000372、confirmationは点で-0.0000746なのでbalanced roleは置換しない。

TCN 0.515にはaccuracy 7/7、score 6/7foldで勝った。全期間accuracy差+0.2800pt、95%区間+0.1936〜+0.3652pt、score差+0.000327、区間-0.0000247〜+0.000669。Brier/log lossも改善区間が確定した。baselineにはaccuracy・score各7/7、全期間score差区間+0.000464〜+0.001243である。

## 校正と判断

最終50/50 confidenceの全期間0.515 laneはmean 52.4058%に対しaccuracy 52.5827%で近いが、confirmationはmean 51.9539%に対しaccuracy 53.3560%、1.4021pt過小評価で局所整合しない。confirmation 0.55は39件・accuracy 46.1538%でedge未確認である。

50/50方式をM1の新しいaccuracy-specialist confidence forward候補に採用し、TCNの同役割を履歴上で更新する。Disagreementはcoverageとprobability-qualityを重視するbalanced候補として並行維持する。方向、authoritative confidence、fair odds、paper/live policyは変更しない。guard、50/50、0.515を同じ履歴で再探索せず、完全未使用期間で両役割を比較する。

実config 3件からregistryを再構築すると、0.515のbroad roleでは50/50方式がdevelopment selection-score championかつdevelopment/confirmation accuracy leader、Disagreementがcoverage leaderのPareto challenger、TCNがdominatedとなった。これは履歴上の候補順位であり、完全未使用期間を省略してauthoritative運用へ昇格する意味ではない。

## 成果物

- transition OOS: `experiments/next_bar/walk_forward_transition_bayes_m1_fixed_001`
- transition direction/confidence: `experiments/next_bar/transition_bayes_m1_blend_fixed_001`, `experiments/next_bar/transition_bayes_m1_confidence_fixed_001`
- reliability/subgroups: `experiments/next_bar/transition_bayes_vs_tcn_m1_confidence_reliability.json`, `experiments/next_bar/transition_bayes_m1_confidence_subgroups.json`
- guarded transition: `experiments/next_bar/transition_bayes_m1_up_low_guard_fixed_001`
- final confidence blend: `experiments/next_bar/disagreement_transition_guard_confidence_m1_fixed_001`
- rebuilt registry: `experiments/next_bar/m1_candidate_registry_transition_guard_001.json`
- final comparisons: `experiments/next_bar/disagreement_transition_guard_vs_baseline_m1_candidate_analysis.json`, `experiments/next_bar/disagreement_transition_guard_vs_tcn_m1_candidate_analysis.json`, `experiments/next_bar/disagreement_transition_guard_vs_disagreement_m1_candidate_analysis.json`
- 20,000 bootstrap: corresponding `*_confidence_bootstrap.json`
- forward config: `methods/next_bar/config/m1_transition_guard_disagreement_confidence_candidate_v1.json`
