# 00090 M1 Chronological Expert Stacking

日時: 2026-08-11 06:10 JST

## 目的

固定等重みの5-model Disagreementに対し、各test foldより前のOOS予測だけからexpert weightを学習するとM1 confidenceを改善できるか検証した。M15で棄却済みの実装をM1へ固定移植し、結果を見てregularization、expert subset、stack weight、confidence閾値を変更しない。

## 固定仕様と因果性

入力expertは現在のDisagreementと同じbaseline HGB、Path Persistence HGB、Extra Trees、LightGBM、causal TCNである。各up確率をlogit変換し、StandardScaler + L2 logistic regressionを `C=0.10`、seed 42で学習した。

各test foldは、それより前のtest OOS foldだけをtrainに使う。test2020はprior OOSがないためbaseline fallback、test2021は2020だけ、test2026途中は2020〜2025だけでfitした。baseline 75% + stack 25%、baseline方向維持、0.515をM15仕様から固定した。2,183,717行は5 source間でfold、timestamp、decision/target timestamp、targetが完全一致した。

test2021以降の係数はExtra Trees、LightGBM、TCNが主に正で、Pathはほぼ0、baselineは小さい正となった。最終評価fold用の標準化後係数はbaseline +0.00495、Path +0.00085、Extra Trees +0.01599、LightGBM +0.01791、TCN +0.01399だった。

## 全行の方向と確率品質

| model | accuracy | Brier | log loss | ECE |
|---|---:|---:|---:|---:|
| baseline | 50.80695% | 0.24986888 | 0.69288487 | 0.2029% |
| stack単体 | 50.79811% | 0.24989484 | 0.69293696 | 0.2282% |
| direction-preserved 25% | 50.80695% | 0.24986921 | 0.69288553 | 0.1916% |

stack単体はaccuracy -193件でBrier/log loss/ECEも悪化した。方向維持版は設計どおりbaseline方向と100%一致し、ECEだけ改善したがBrier/log lossは僅かに悪化した。学習weightは全行確率品質の新しいedgeにならなかった。

## 固定0.515選別

| period | baseline accuracy / coverage / score | stack accuracy / coverage / score | 現champion accuracy / coverage / score |
|---|---:|---:|---:|
| development | 51.9505% / 28.6110% / 0.009587 | 51.9232% / 28.6092% / 0.009441 | 52.4249% / 21.6867% / 0.010447 |
| confirmation | 52.5091% / 9.9208% / 0.006837 | 52.7660% / 9.0271% / 0.007245 | 53.3560% / 7.0236% / 0.007829 |
| all | 52.0507% / 21.3852% / 0.008820 | 52.0630% / 21.0386% / 0.008800 | 52.5827% / 16.0178% / 0.009674 |

stackはbaselineにaccuracy 5/7、selection score 3/7foldしか勝たず、development scoreと全体scoreは悪化した。DisagreementおよびTransition guard 50/50 championにはaccuracy・scoreとも0/7対7/7だった。

現champion比の日次20,000回bootstrapでは、全期間accuracy差-0.5197pt、95%区間-0.6097〜-0.4304pt、selection score差-0.000874、区間-0.001241〜-0.000509で劣位が確定した。coverageは+5.0208ptだが、Brier差+0.00002175、log loss差+0.00004365も悪化区間が確定した。

## 信頼度曲線

stackの全期間累積accuracyは0.515=52.0630%、0.525=52.9639%、0.535=53.7472%、0.55=54.8407%と上昇する。しかし現championは同じ閾値で52.5827%、53.6025%、54.6527%、56.1506%と全て上回った。

stackはdevelopment 0.515でmean confidence 52.6731%に対しaccuracy 51.9232%、0.55で56.2395%に対し54.8556%となり過信した。confirmationでは逆に過小評価へ変わり、0.55は100件・accuracy 52.0%、Wilson下限42.32%でedge未確認だった。時期ごとのconfidence写像が安定していない。

## 判断

M1 chronological stackingは再現専用として棄却する。prior-OOSだけで学ぶ因果性は満たすが、固定等重みDisagreementと現championのaccuracy、coverage-aware score、proper scoreを上積みしない。config、latest shadow、fair odds、policyは発行・変更しない。同じM1履歴でC、expert subset、standardization、stack weight、別閾値を再探索しない。

## 成果物

- predictions/models: `experiments/next_bar/chronological_stacking_m1_direction_preserved_fixed_001`
- baseline analysis: `experiments/next_bar/chronological_stacking_m1_candidate_analysis.json`
- Disagreement comparison: `experiments/next_bar/chronological_stacking_vs_disagreement_m1_analysis.json`
- champion comparison: `experiments/next_bar/chronological_stacking_vs_transition_guard_champion_m1_analysis.json`
- champion bootstrap: `experiments/next_bar/chronological_stacking_vs_transition_guard_champion_m1_bootstrap.json`
- reliability: `experiments/next_bar/chronological_stacking_vs_transition_guard_champion_m1_reliability.json`
