# 00112 M15/M30 Rolling Autoregressive State

日時: 2026-08-11 14:28 JST

## 目的

完成足returnの値を直接モデルへ追加するのではなく、局所AR(3)の係数、次期予測、説明エネルギー、innovationへ加工し、M15/M30の次足方向とconfidenceに独立edgeがあるかを検証した。既存の単一lag autocorrelationやRolling Spectral Stateとは異なり、複数lagの条件付き線形状態を短長2窓で表す。

## 固定仕様と品質

完成足log returnへwindow 32/128のcausal ridge AR(3)を当てた。ridgeは各行の `0.05 * trace(X'X) / 3` とし、scaleに追随させた。各窓から3係数、RMS正規化した1-step forecast、centered target energyに対するfitted energy、1行前までのモデルで現在returnを評価したinnovationの6列を作り、短長のforecast・energy・innovation差3列を加えた固定15特徴とした。係数はclip後1/2、forecastとinnovationは3 RMSで正規化し、全出力を[-1,1]に制限した。

生価格水準、volume、targetは使わない。gapを含む窓とflat/不定窓は全0である。厳密ridge解、prior-row innovation、短長差、価格10倍scale不変、未来行改変不影響、gap reset、flat全0、53特徴artifact/latest経路をテストした。HGB/Platt、標準損失1.0、test2020〜test2026途中の固定7fold、通常/方向維持25% blendを使用し、AR次数、window、ridge、weightを結果に合わせて再探索していない。正式baselineとM15 145,140行、M30 71,260行で完全整列した。

## 単体と通常25% blend

| timeframe | model | development accuracy | confirmation accuracy | all accuracy | all Brier |
|---|---|---:|---:|---:|---:|
| M15 | baseline | 52.01441% | 51.50115% | 51.81618% | 0.249426100 |
| M15 | AR単体 | 52.02676% | 51.46904% | 51.81135% | 0.249416981 |
| M15 | baseline 75% + AR 25% | 52.03799% | 51.46190% | 51.81549% | 0.249406490 |
| M30 | baseline | 51.98972% | 51.52019% | 51.80747% | 0.249497879 |
| M30 | AR単体 | 51.89110% | 51.32497% | 51.67134% | 0.249440062 |
| M30 | baseline 75% + AR 25% | 52.02872% | 51.50573% | 51.82571% | 0.249460260 |

M15通常blendはdevelopment +21件に対しconfirmation -22件、all -1件で、accuracy改善2/7foldだった。Brier/log lossは5/7fold改善したが方向edgeは再現しなかった。

M30通常blendはdevelopment +17件、confirmation -4件、all +13件で、accuracy 5/7、Brier/log loss 6/7foldだった。しかし現行のPressure + Ordinal Motif方向候補よりall -24件で、固定50/50追加も51.84956%と親候補51.85939%を下回った。方向candidateへ追加しない。

## M15 confidence

development grid最良0.525ではARがbaselineをdevelopment/confirmationのaccuracy・scoreで小幅改善した。しかし既存Signed-body Quantile 0.525との直接比較はaccuracy/selection scoreとも0/7対7/7で、allはAR 47,909件・53.9105%・score 0.019901に対し既存候補48,428件・54.0803%・score 0.021004だった。

固定0.55でもARはdevelopment 9,486件・55.6926%へ改善したが、confirmationはbaseline 1,887件・55.7499%に対して1,877件・55.5674%へ反転した。既存Intrabar Structureはall 11,439件・56.0101%・score 0.014314で、ARの11,363件・55.6719%・score 0.013310を上回った。M15 confidenceへ採用しない。

## M30 confidence

development grid最良0.52のARは、confirmationだけbaselineを改善したがdevelopmentで悪化し、既存Pressureとの直接比較もaccuracy/score 2/7対5/7だった。allはAR 26,828件・53.5523%・score 0.018131に対しPressure 26,000件・53.7577%・score 0.019034であり、標準の0.52 laneを置換しない。

探索前から報告対象として固定した0.55ではAR単独confidenceがdevelopment 3,666件・55.9738%、confirmation 964件・56.3278%、all 4,630件・56.0475%となった。Pressureよりall精度+0.0560pt、coverage +0.5248pt、score +0.000773でscoreは5/7fold勝ったが、accuracyは3/7だった。20,000回の日次bootstrapではcoverage差だけが正で、all accuracy差区間-0.7050〜+0.8078pt、score差-0.001108〜+0.002642だったため単独置換はしない。

Pressure confidenceとAR confidenceを履歴探索なしの固定50/50で平均すると、次の結果になった。方向と確率値はPressure側のbaseline方向・確率を維持し、採否用confidenceだけを平均している。

| period | Pressure rows / accuracy / coverage / score | equal selector rows / accuracy / coverage / score |
|---|---:|---:|
| development | 3,398 / 56.0918% / 7.7938% / 0.012332 | 3,505 / 56.1769% / 8.0392% / 0.012839 |
| confirmation | 858 / 55.5944% / 3.1018% / 0.003966 | 907 / 56.0088% / 3.2790% / 0.004997 |
| all | 4,256 / 55.9915% / 5.9725% / 0.010986 | 4,412 / 56.1423% / 6.1914% / 0.011629 |

equal selectorはdevelopment、confirmation、allの点accuracy・coverage・scoreを全て上げ、fold別accuracy 4/7、score 6/7だった。Pressure比20,000回日次bootstrapでall coverage差は+0.1527〜+0.2838ptと正だったが、accuracy差は-0.3724〜+0.6814pt、score差は-0.000654〜+0.001959で0を跨いだ。scoreが上回るbootstrap確率はall 83.785%、confirmation 84.13%である。方向確率は同じなのでBrier/log lossはPressureと同値である。

## 判断

M15のAR方向/confidence、M30のAR方向、標準0.52 confidence、AR単独0.55は再現専用とする。AR次数、window、ridge、blend weight、閾値を同じ履歴へ合わせて再探索しない。現行のM30 Pressure + Ordinal Motif方向候補、Pressure 0.52 confidence、fair odds、adoption/paper/live policy、runtime latestは変更しない。

PressureとARの固定等比confidence selector 0.55だけは、開発・確認の双方を改善しscore 6/7foldだったため `m30_pressure_ar_confidence_shadow_v1.json` のparallel forward shadowへ固定する。ただしbootstrapでaccuracy/score優位は未確定、runtime parityも未発行であり、予測確率やfair oddsとして認可しない。完全未使用期間でPressure以上のaccuracy、coverage、selection scoreを同時に確認するまでshadow比較に限定する。

## 成果物

- 実装・テスト: `src/trade_data/next_bar.py`, `tests/test_next_bar.py`
- OOS: `experiments/next_bar/walk_forward_rolling_autoregressive_state_m15_m30_fixed_001`
- baseline blends: `experiments/next_bar/rolling_autoregressive_state_m15_*_fixed_001`, `experiments/next_bar/rolling_autoregressive_state_m30_*_fixed_001`
- candidate分析: `experiments/next_bar/rolling_autoregressive_state_m15_candidate_analysis.json`, `experiments/next_bar/rolling_autoregressive_state_m30_candidate_analysis.json`
- 既存候補比較: `experiments/next_bar/rolling_autoregressive_state_vs_*`
- 採用shadow: `experiments/next_bar/pressure_rolling_autoregressive_state_equal_m30_confidence_fixed_001`
- direct/bootstrap: `experiments/next_bar/pressure_rolling_autoregressive_state_equal_vs_pressure_m30_fixed_055*.json`
- 棄却方向blend: `experiments/next_bar/pressure_ordinal_motif_ar_equal_m30_direction_fixed_001`
- 固定設定: `methods/next_bar/config/m30_pressure_ar_confidence_shadow_v1.json`
