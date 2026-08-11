# 00111 M15/M30 Rolling Ordinal Motif

日時: 2026-08-11 14:08 JST

## 目的

完成足returnの大きさそのものではなく、連続3本が作る6種類の順序patternをrolling分布へ加工し、M15/M30の次足方向とconfidenceに増分edgeがあるかを確認した。既存の足内M1順序特徴とは異なり、対象時間足の完成足間のreturn順序を使う。

## 固定仕様と品質

連続3 returnを値、同値時は位置の辞書順で `012/021/102/120/201/210` へ分類する。直前32/128 motifについて6比率、正規化entropy、現在motif頻度を作り、短長entropy差・頻度差を加えた固定18特徴とした。生価格水準、volume、targetは使わない。flatまたはtimestamp gapを含む窓は全0、全特徴は有限かつ[-1,1]である。

厳密手計算、価格10倍scale不変、未来行改変不影響、gap reset、flat全0、56特徴artifact/latest経路をテストした。HGB/Platt、標準損失1.0、test2020〜test2026途中の固定7fold、通常/方向維持25% blendを使い、結果を見たwindow、motif subset、weightの再探索は行っていない。OOSはM15 145,140行、M30 71,260行で正式baselineと完全整列した。

## 単体と通常25% blend

| timeframe | model | development accuracy | confirmation accuracy | all accuracy | all Brier |
|---|---|---:|---:|---:|---:|
| M15 | baseline | 52.01441% | 51.50115% | 51.81618% | 0.249426100 |
| M15 | Motif単体 | 51.95604% | 51.42266% | 51.75003% | 0.249437720 |
| M15 | baseline 75% + Motif 25% | 51.96165% | 51.44585% | 51.76244% | 0.249413208 |
| M30 | baseline | 51.98972% | 51.52019% | 51.80747% | 0.249497879 |
| M30 | Motif単体 | 51.83146% | 51.55634% | 51.72467% | 0.249499570 |
| M30 | baseline 75% + Motif 25% | 52.04477% | 51.61057% | 51.87623% | 0.249476887 |

M15は単体・通常blendともdevelopment、confirmation、all accuracyがbaselineを下回った。通常blendのBrier/log loss点値は改善してもaccuracy改善は1/7foldだけであり、方向用途へ使わない。

M30通常blendはbaseline比development +24件、confirmation +25件、all +49件、accuracy 4/7、Brier/log loss 5/7foldだった。baseline比all Brier/log lossの日次bootstrap区間はそれぞれ-0.00004051〜-0.00000125、-0.00008157〜-0.00000259で改善を支持したが、accuracy差+0.06876ptの区間は-0.05793〜+0.19507ptだった。既存Pressure方向blendにはdevelopment/confirmationとも高く5/7fold勝ったものの、all accuracy差+0.13893ptの区間は-0.01842〜+0.29565pt、Pressureのproper score点値が良かったため、Motif 25%単独で置換しない。

## confidence

M15のdevelopment grid最良0.525はbaseline比development/confirmationのaccuracyとselection scoreを小幅改善した。しかし既存Signed-body Quantile 0.525にdevelopment、confirmation、allのaccuracy・coverage・score・Brier/log lossで負け、年別accuracy/scoreは2/7対5/7だった。all selection score差の日次bootstrap区間も-0.001734〜-0.000015でMotif側の悪化を支持した。

M15 0.55はdevelopmentで僅かに改善したが、confirmationはbaseline 1,887件・55.7499%に対しMotif 1,865件・54.9062%へ反転した。M15 confidenceへ採用しない。

M30 0.515はdevelopment/confirmationのaccuracy・selection scoreがbaselineより悪く、現行Pressure 0.52を置換しない。探索的にdevelopment改善が大きかった固定0.55をconfirmationへ持ち出すと、Motifはdevelopment 3,642件・56.0956%、confirmation 1,002件・54.8902%、all 4,644件・55.8355%だった。baseline比all accuracy/scoreは日次bootstrapで改善したが、confirmation差はほぼ0で区間が広い。Pressure 0.55はconfirmation 858件・55.5944%、all 4,256件・55.9915%でMotifより高精度だった。固定50/50 confidence平均もconfirmation 929件・54.5748%へ悪化したため、precision lane、fair odds、policyへ使わない。

## 固定50/50方向多様化

Pressure通常25% blendとMotif通常25% blendを固定50/50平均した。最終weightはbaseline 75%、Pressure 12.5%、Motif 12.5%であり、履歴からweightを探索していない。

| period | baseline accuracy | Pressure accuracy | equal blend accuracy | equal Brier | equal log loss |
|---|---:|---:|---:|---:|---:|
| development | 51.98972% | 51.89569% | 52.02184% | 0.249416062 | 0.691978787 |
| confirmation | 51.52019% | 51.48765% | 51.60334% | 0.249533277 | 0.692211831 |
| all | 51.80747% | 51.73730% | 51.85939% | 0.249461561 | 0.692069248 |

equal blendはbaseline比accuracy 5/7、Brier/log loss 6/7foldで、development、confirmation、allの点値を全て改善した。baseline比all accuracy +37件のbootstrap区間は-0.07360〜+0.17589ptで未確定だが、Brierは-0.00005594〜-0.00001616、log lossは-0.00011274〜-0.00003280と改善を支持した。

既存Pressure方向blendに対してはdevelopment +55件、confirmation +32件、all +87件、accuracy 6/7fold。all accuracy差+0.12209ptの日次bootstrap区間は+0.00710〜+0.23595ptで正、Brier/log lossの小さな悪化区間は0を跨いだ。predicted up/downの2/2、low/normal/high volatilityの3/3で点accuracyもPressureを上回った。現在のPressureはconfidence用で方向用途は棄却済みだが、固定多様化により方向反転の誤差が相殺された。

## 判断

M15とM30単体Motif、M15 confidence、M30 0.515/0.55 confidence、confidence 50/50平均は採用しない。M30通常25% Motifはbaseline proper scoreを改善したが、単独では既存候補へのaccuracy優位が未確定なので多様化素材に限定する。

baseline 75% + Pressure 12.5% + Motif 12.5%のM30方向blendだけを `m30_pressure_ordinal_motif_direction_candidate_v1.json` の固定parallel forward候補として採用する。authoritative方向に対するaccuracy差はまだ未確定でruntime artifact parityも未実装なので、authoritative方向/confidence、Pressure 0.52、fair odds、adoption/paper/live policy、runtime latestは変更しない。完全未使用期間でbaseline以上のaccuracy、Brier、log lossを同時に確認するまでshadow比較とし、motif長、window、tie、weight、thresholdを履歴内再探索しない。

## 成果物

- 実装・テスト: `src/trade_data/next_bar.py`, `tests/test_next_bar.py`
- OOS: `experiments/next_bar/walk_forward_rolling_ordinal_motif_m15_m30_fixed_001`
- baseline blends: `experiments/next_bar/rolling_ordinal_motif_m15_*_fixed_001`, `experiments/next_bar/rolling_ordinal_motif_m30_*_fixed_001`
- candidate分析: `experiments/next_bar/rolling_ordinal_motif_m15_candidate_analysis.json`, `experiments/next_bar/rolling_ordinal_motif_m30_candidate_analysis.json`
- direct/bootstrap: `experiments/next_bar/rolling_ordinal_motif_vs_*`, `experiments/next_bar/pressure_ordinal_motif_equal_vs_*`
- 採用方向blend: `experiments/next_bar/pressure_ordinal_motif_equal_m30_direction_fixed_001`
- 棄却confidence blend: `experiments/next_bar/pressure_ordinal_motif_equal_m30_confidence_fixed_001`
- 固定設定: `methods/next_bar/config/m30_pressure_ordinal_motif_direction_candidate_v1.json`
