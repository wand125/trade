# 00126 M1 Transition guard × Distribution Shift Selection Sets

日時: 2026-08-11 18:00 JST

## 目的

M1の高精度laneであるTransition guard 0.515と、広いcoverageを持つDistribution Shift 0.51が補完的なら、予測確率を再混合せず採用集合のunion/intersectionだけでaccuracyとcoverageの目的関数を改善できる。既に固定済みの閾値を変えず、developmentだけで演算子を選び、confirmationは監査専用として検証した。

## 固定仕様と品質

firstをTransition guard 0.515、secondをDistribution Shift 0.51とし、first、second、union、intersectionのboolean採用集合を生成した。全2,183,717 OOS行でfold、timestamp、targetを厳密整列し、両候補の方向一致も要求した。合成確率や架空の信頼度は作らず、出力の方向確率・confidenceはfirstを保存し、各source confidenceと採用flagを別列へ残した。

評価はdevelopment=test2020〜2023、confirmation=test2024〜2026途中、目的関数は `sqrt(coverage) * (Wilson95Lower(accuracy) - 0.5)` とした。明示boolean採用列をUTC日paired block bootstrapへ渡せるようにし、閾値判定を再実行せず20,000回比較した。集合内では両sourceのmean confidence、Brier、log loss、ECE、Wilson区間、局所整合も再計算した。損失倍率は標準1.0のみである。

## 採用集合結果

| period | operator | rows | coverage | accuracy | score |
|---|---|---:|---:|---:|---:|
| development | Transition guard | 290,488 | 21.6867% | 52.4249% | 0.010447 |
| development | Distribution Shift | 579,078 | 43.2316% | 51.7039% | 0.010357 |
| development | union | 579,738 | 43.2809% | 51.7047% | 0.010369 |
| development | intersection | 289,828 | 21.6374% | 52.4249% | 0.010434 |
| confirmation | Transition guard | 59,296 | 7.0236% | 53.3560% | 0.007829 |
| confirmation | Distribution Shift | 198,605 | 23.5247% | 51.8985% | 0.008142 |
| confirmation | union | 198,628 | 23.5275% | 51.8975% | 0.008138 |
| confirmation | intersection | 59,273 | 7.0209% | 53.3599% | 0.007838 |
| all | Transition guard | 349,784 | 16.0178% | 52.5827% | 0.009674 |
| all | Distribution Shift | 777,683 | 35.6128% | 51.7536% | 0.009802 |
| all | union | 778,366 | 35.6441% | 51.7539% | 0.009809 |
| all | intersection | 349,101 | 15.9865% | 52.5836% | 0.009668 |

developmentの全演算子首位は既存Transition guard、合成演算子だけの首位はintersectionだった。しかしintersectionはguardから660行だけをdevelopmentで除き、confirmationでは23行だけを除くほぼ同一集合である。unionもShiftへdevelopment 660行、confirmation 23行を加えるだけだった。

全期間でboth 349,101行、guard-only 683行、Shift-only 428,582行だった。guard-onlyは52.1230%だがWilson下限48.3751%でedge未確認、confirmation 23行は43.4783%だった。Shift-onlyは全期間51.0775%、Wilson下限50.9278%で広coverageの弱いedgeを持つ。この包含構造では集合演算による新しいprecision/coverage frontierは作れない。

年別ではunion−Shiftがaccuracy 4/7、score 5/7、intersection−guardがaccuracy 4/7、score 2/7だった。点値の微差を安定した改善とは扱わない。

## Bootstrap

| comparison / all | delta | 95% interval | 判断 |
|---|---:|---:|---|
| intersection − guard accuracy | +0.000899pt | -0.006230〜+0.007967pt | 未確定 |
| intersection − guard coverage | -0.031277pt | -0.034660〜-0.027888pt | coverage減少のみ確定 |
| intersection − guard score | -0.00000650 | -0.00003516〜+0.00002170 | 未確定 |
| union − Shift accuracy | +0.000324pt | -0.002847〜+0.003537pt | 未確定 |
| union − Shift coverage | +0.031277pt | +0.027888〜+0.034660pt | coverage増加のみ確定 |
| union − Shift score | +0.00000653 | -0.00001239〜+0.00002582 | 未確定 |

development、confirmation、allのaccuracy/score区間はすべて0を跨いだ。各演算子の出力確率は同じfirst anchorを保持するため、Brier/log loss差は設計上0であり、確率品質改善の証拠ではない。

## 信頼度品質

| period / set | accuracy | Transition mean confidence | Shift mean confidence |
|---|---:|---:|---:|
| development / guard | 52.4249% | 52.4980% / 整合 | 52.8259% / 過信・不整合 |
| development / Shift | 51.7039% | 51.7698% / 整合 | 52.1249% / 過信・不整合 |
| confirmation / guard | 53.3560% | 51.9539% / 過小・不整合 | 52.1087% / 過小・不整合 |
| confirmation / Shift | 51.8985% | 51.3597% / 過小・不整合 | 51.5327% / 過小・不整合 |
| all / intersection | 52.5836% | 52.4073% / 不整合 | 52.7080% / 整合 |
| all / union | 51.7539% | 51.6651% / 整合 | 51.9727% / 過信・不整合 |

developmentではfirstであるTransition guard confidenceが両laneの実績に近い。一方confirmationでは実績edgeが上振れして両sourceとも過小評価となり、期間間calibration driftがある。intersection/unionは採用集合しか定義せず、新しい各行fair oddsを定義しない。first confidenceをそのまま使ってもconfirmationの局所整合を満たさないため、合成集合をauthoritative oddsとして認可しない。

## 判断

Transition guardとDistribution Shiftは補完候補に見えるが、固定閾値ではguard集合の99.80%以上がShiftに含まれる。union/intersectionは親から最大0.0313ptのcoverageを動かすだけで、accuracy・selection scoreの統計的増分も新しい信頼度写像も得られなかった。

両合成演算子を再現専用として棄却する。Transition guardをaccuracy specialist、Distribution Shiftをultra-broad confidence、Disagreementをbalanced challengerとして独立維持し、config、registry、authoritative方向/confidence、fair odds、paper/live policyを変更しない。union/intersection、閾値、source順、集合固有の再校正を同じ履歴で再探索しない。

## 成果物

- 固定集合・比較: `experiments/next_bar/transition_guard_distribution_shift_selection_sets_m1_fixed_001`
- intersection bootstrap: `experiments/next_bar/transition_guard_distribution_shift_intersection_vs_guard_m1_bootstrap.json`
- union bootstrap: `experiments/next_bar/transition_guard_distribution_shift_union_vs_shift_m1_bootstrap.json`
- 実装: `methods/next_bar/scripts/confidence_selection_operators.py`, `methods/next_bar/scripts/bootstrap_fixed_candidates.py`
