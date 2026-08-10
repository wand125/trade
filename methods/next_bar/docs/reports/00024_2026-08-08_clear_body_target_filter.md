# 00024 Clear-body target filtering

日時: 2026-08-08 06:53 JST

## 目的

小さい次足を方向教師として同じ1件に数えるノイズを減らすため、各foldのtrain内で `next_bar_body_atr` が中央値以上の足だけを教師としてHGBを学習する。calibration/testは削らず、全件で確率校正・評価する。

## 固定した方法

- 実装: `--train-target-filter body_atr_upper_half`
- 閾値: 各foldのtrain内中央値。calibration/testや他foldの値は使わない。
- 入力: baselineと同じ38加工特徴。未来の次足実体はfilter教師にだけ使い、feature manifestには含めない。
- 評価: M15の2020〜2026途中7fold、Platt校正、通常blend/方向維持型blendとも候補weight 25%。
- confidence閾値: 0.515〜0.60の固定gridをdevelopment 2020〜2023だけで選び、confirmation 2024〜2026途中へ固定する。

## 単体と通常blend

| period | model | accuracy | Brier | log loss | ECE |
|---|---|---:|---:|---:|---:|
| all | baseline | 51.816% | 0.2494261 | 0.6919985 | 0.347% |
| all | filtered single | 51.707% | 0.2494333 | 0.6920113 | 0.357% |
| confirmation | baseline | 51.501% | 0.2495525 | 0.6922506 | 0.298% |
| confirmation | filtered single | 51.312% | 0.2495690 | 0.6922837 | 0.417% |

単体は全主要指標が悪化したため方向モデルとして棄却する。通常25% blendは全体51.818%だが、誤り修正2,798件・新規誤り2,796件、McNemar exact p=0.989で方向改善ではない。confirmation accuracyも51.440%へ悪化したため方向用途には採用しない。

## 方向維持型confidence blend

baseline方向を固定し、filtered modelをconfidence edgeへ25%使った。

| period | metric | baseline | candidate |
|---|---|---:|---:|
| development | Brier | 0.2493466 | 0.2492838 |
| development | log loss | 0.6918398 | 0.6917129 |
| development | ECE | 0.377% | 0.265% |
| confirmation | Brier | 0.2495525 | 0.2495328 |
| confirmation | log loss | 0.6922506 | 0.6922113 |
| confirmation | ECE | 0.298% | 0.236% |
| all | Brier | 0.2494261 | 0.2493800 |
| all | log loss | 0.6919985 | 0.6919054 |
| all | ECE | 0.347% | 0.254% |

Brier/log lossは7/7 fold、ECEは5/7 foldで改善した。

## developmentで選んだconfidence 0.525 lane

| period | model | rows | coverage | accuracy | selection score |
|---|---|---:|---:|---:|---:|
| development | baseline | 33,770 | 37.908% | 53.858% | 0.02048 |
| development | candidate | 31,748 | 35.639% | 54.173% | 0.02164 |
| confirmation | baseline | 14,785 | 26.375% | 53.777% | 0.01527 |
| confirmation | candidate | 13,854 | 24.714% | 54.201% | 0.01675 |
| all | baseline | 48,555 | 33.454% | 53.834% | 0.01961 |
| all | candidate | 45,602 | 31.419% | 54.182% | 0.02088 |

coverageを約2pt絞り、全体accuracyを+0.348pt、confirmationを+0.424pt改善した。accuracyとselection scoreはいずれも7/7 foldで改善した。

## 判断

- filtered singleと通常方向blendは棄却する。
- 方向維持型25% blend + confidence 0.525を `m15_body_atr_upper_half_confidence_candidate_v1.json` の中coverage forward候補に固定する。
- 同じ0.525 laneのsigned-body quantile候補よりaccuracyとECE安定性は高いが、全体selection scoreは0.02088対0.02100で僅かに低い。履歴上で勝者を選ばず、fresh期間で並行比較する。
- authoritative confidence、odds、現行採用policy、paper policyは変更しない。
- 損益は目的関数へ含めず、損失倍率は標準1.0のみとする。
