# 00033 Causal online expert weighting

日時: 2026-08-10 13:25 JST

## 目的

固定モデルの等重み集約ではなく、直近に実際に良かったモデルへ因果的に重みを移す学習フローがM15次足予測とconfidenceを改善するか確認する。モデル予測値をそのまま採用せず、各時点までに確定したrolling log lossから動的weightへ加工する。

## 結果前に固定した方法

前実験と同じ145,140行・7 OOS foldへ完全整列する5モデルをexpertとした。

1. baseline binary HGB
2. clear-body-filtered binary HGB
3. Extra Trees classifier
4. signed-body HGB regressor
5. intrabar-structure binary HGB

各decision時点で `target_timestamp <= decision_timestamp` を満たす過去結果だけを更新に使う。直近2,000予測、すなわちM15で約1か月分について各モデルのbinary log lossを合計し、学習率1の `weight_i ∝ exp(-loss_sum_i)` とした。履歴ゼロ時は等重み、fold境界でも直近の確定済み結果を引き継ぐ。窓長、学習率、モデル集合は結果後に変更しない。

方向自由のオンライン平均と、同じweightを使いbaseline方向だけを固定するconfidence版を一度だけ生成した。実装は `src/trade_data/next_bar_online_ensemble.py`、CLIは `methods/next_bar/scripts/online_ensemble.py` である。

## 因果性・品質確認

- 現在行のtargetを現在行のweightへ入れない。
- target確定が次decisionより遅い場合は更新を待つ。
- 2,000件を超えた古いlossはrolling windowから除外する。
- targetがdecision以前の不正な行、時系列順でないtarget、入力不整列を停止する。

これらを単体テストへ追加した。

## オンラインweightの状態

| model | 全期間平均weight | 最終weight |
|---|---:|---:|
| baseline HGB | 18.72% | 25.85% |
| clear-body HGB | 21.41% | 14.02% |
| Extra Trees | 21.87% | 22.42% |
| signed-body HGB | 14.47% | 12.37% |
| intrabar structure HGB | 23.53% | 25.35% |

平均最大weightは45.93%、平均実効モデル数は3.30だった。単一expertへ完全には崩壊していない。

## 方向自由版

| period | model | accuracy | Brier | log loss | ECE |
|---|---|---:|---:|---:|---:|
| development | baseline | 52.014% | 0.2493466 | 0.6918398 | 0.377% |
| development | online | 52.047% | 0.2492263 | 0.6915964 | 0.102% |
| confirmation | baseline | 51.501% | 0.2495525 | 0.6922506 | 0.298% |
| confirmation | online | 51.430% | 0.2495394 | 0.6922245 | 0.203% |
| all | baseline | 51.816% | 0.2494261 | 0.6919985 | 0.347% |
| all | online | 51.809% | 0.2493472 | 0.6918390 | 0.141% |

確率品質は改善したが、方向accuracyはconfirmationで0.071pt、全体で0.008pt悪化した。誤り修正6,803件、新規誤り6,814件、McNemar exact p=0.932であり、方向置換には使わない。

## baseline方向固定confidence版

| period | metric | baseline | online confidence |
|---|---|---:|---:|
| development | Brier | 0.2493466 | 0.2492132 |
| development | log loss | 0.6918398 | 0.6915700 |
| development | ECE | 0.377% | 0.074% |
| confirmation | Brier | 0.2495525 | 0.2495398 |
| confirmation | log loss | 0.6922506 | 0.6922253 |
| confirmation | ECE | 0.298% | 0.104% |
| all | Brier | 0.2494261 | 0.2493393 |
| all | log loss | 0.6919985 | 0.6918231 |
| all | ECE | 0.347% | 0.085% |

Brier/log lossは6/7 fold、ECEは4/7 foldでbaselineを改善した。

## developmentで選んだconfidence 0.515 lane

| period | model | rows | coverage | accuracy | selection score |
|---|---|---:|---:|---:|---:|
| development | baseline | 52,243 | 58.645% | 53.102% | 0.02048 |
| development | online | 46,989 | 52.747% | 53.476% | 0.02197 |
| confirmation | baseline | 27,681 | 49.380% | 52.574% | 0.01395 |
| confirmation | online | 25,071 | 44.724% | 52.834% | 0.01482 |
| all | baseline | 79,924 | 55.067% | 52.919% | 0.01909 |
| all | online | 72,060 | 49.649% | 53.253% | 0.02035 |

accuracyは6/7 fold、selection scoreは5/7 foldで改善した。2026途中ではaccuracy 53.270%から53.206%、score 0.01499から0.01427へ悪化した。

## 既存方式との直接比較

同じ5モデル固定等重み・方向固定の0.515と比べると、オンライン版はconfirmation scoreを0.01418から0.01482、全体を0.02031から0.02035へ上げた。一方developmentは0.02228から0.02197へ下がり、全体Brier 0.2493383から0.2493393、log loss 0.6918211から0.6918231、ECE 0.030%から0.085%へ悪化した。直接fold比較でもBrier/log loss改善は各3/7だった。

既存signed-body confidence 0.52はconfirmation coverage 30.745%、accuracy 53.594%、selection score 0.01580であり、オンライン0.515の目的関数0.01482を上回る。

## 判断

- 方向自由版は棄却する。
- オンラインconfidenceはbaselineに対して改善するが、固定等重みの確率品質と既存signed-bodyのconfirmation目的関数を超えないためforward/shadow configを発行しない。
- 実装と成果物は因果的online ensembleの再現用として残す。
- 同じ履歴でhistory rows、学習率、expert subset、閾値を再探索しない。
- authoritative confidence、fair odds、現行採用policy、paper policyは変更しない。損失倍率は標準1.0のみとする。
