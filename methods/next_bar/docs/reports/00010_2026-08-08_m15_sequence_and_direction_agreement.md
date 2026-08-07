# 00010 M15 normalized sequence and direction agreement

日時: 2026-08-08 01:06 JST

## 目的

M15の次足精度をさらに上げるため、価格水準を使わない直近足系列と、M15/M5/M1の方向一致による高品質な見送り条件を同じ7foldで確認する。

## 正規化8本系列

直近8本の各足について、次の5値をATRで正規化してbaseline HGBへ追加した。

- close差、実体、range
- 足内のclose位置
- 上下wickのbalance

40特徴はいずれも判定時点までの完成足だけから作り、生のOHLC価格水準は含めない。実験は `experiments/next_bar/walk_forward_sequence_manual_001`。

| period | baseline accuracy | sequence accuracy | delta |
|---|---:|---:|---:|
| 2020–2023 development | 52.014% | 51.994% | -0.020pt |
| 2024–2026途中 confirmation | 51.501% | 51.253% | -0.248pt |
| 2020–2026途中 all | 51.816% | 51.708% | -0.108pt |

7fold中の改善は3foldだけだった。Brierは0.2494261から0.2494426、log lossは0.6919985から0.6920316、ECEは0.347%から0.415%へすべて悪化した。

confidence 0.54以上も、accuracy `54.809% -> 54.625%`、coverage `14.391% -> 13.719%`。系列順序を明示するだけでは情報追加より過学習の影響が大きいため、このfeature setは棄却する。実験再現用の `sequence_manual` は残すがcandidateにはしない。

## M15/M5/M1方向一致

正式baselineの各時間足OOS予測を、完全一致する `decision_timestamp` だけでjoinした。信頼度はcorrectness calibrationと混同せず、方向確率から作る `max(P(up), 1-P(up))` に統一した。

条件:

```text
M15 class confidence >= 0.54
and predicted_direction_M15 == predicted_direction_M5 == predicted_direction_M1
```

| period / condition | rows | coverage | accuracy | selection score |
|---|---:|---:|---:|---:|
| all: confidence 0.54 | 20,587 | 14.433% | 54.918% | 0.01610 |
| all: + 3TF agreement | 18,703 | 13.112% | 55.055% | 0.01572 |
| confirmation: confidence 0.54 | 4,677 | 8.434% | 55.356% | 0.01141 |
| confirmation: + 3TF agreement | 4,476 | 8.072% | 55.742% | 0.01217 |

全期間ではaccuracyが+0.137pt上がる一方、coverage低下により評価関数は2.35%下がった。development期間でも評価関数は下がった。対して2024–2026途中のconfirmationではaccuracyが+0.386pt、評価関数が6.67%上がった。除外された201件のconfirmation accuracyは46.77%だった。

この条件は全体の主採用条件より、少し狭い高精度laneとして有望。ただしconfirmationを見た後の判断であり、次の完全未使用期間をshadowで測る。

既存cross-timeframe meta candidateへ同じ方向一致を重ねても傾向は同じだった。2021〜2026途中の全期間ではaccuracy `54.479% -> 54.553%` に対しselection score `0.01388 -> 0.01357` と低下。2024〜2026途中ではaccuracy `55.664% -> 55.956%`、selection score `0.01126 -> 0.01184` と改善した。2つの探索後candidateを重ねた結果なので昇格根拠には使わず、shadow仮説の補助診断とする。

## 通常損益での確認

損失倍率は1.0。損失1.2倍の特別評価は使用しない。2021–2026途中の6foldで、M1/M5を同時刻joinできる行だけを比較した。

| condition | rows | accuracy | gross mean / oz | all-fold cost ceiling / oz | cost 0.05 positive folds |
|---|---:|---:|---:|---:|---:|
| confidence 0.54 | 17,117 | 54.408% | 0.09959 | 0.05500 | 6/6 |
| + 3TF agreement | 15,616 | 54.515% | 0.12657 | 0.05052 | 6/6 |

平均損益は改善したが、最悪foldのcost 0.05後余力は1ozあたり0.00052しかない。主paper policyを置換する品質ではない。

## 判断

- `sequence_manual` は不採用。
- 3TF方向一致は `m15_cross_tf_agreement_shadow_v1.json` としてshadow採用する。
- 現行M15方向モデル、採用条件、paper売買policyは変更しない。
- 次の完全未使用期間では、主にaccuracy、coverage、Wilson下限、selection scoreを固定条件で比較する。
- 売買昇格にはaccuracyだけでなく、実測costを引いた後の全fold余力も必要とする。
