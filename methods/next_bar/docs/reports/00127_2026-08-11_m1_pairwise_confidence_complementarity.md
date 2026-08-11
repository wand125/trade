# 00127 M1 Pairwise Confidence Complementarity

日時: 2026-08-11 18:11 JST

## 目的

M1の固定confidence候補から、互いの非重複採用行にもedgeがあり、unionでaccuracyとcoverageの目的関数を改善する真に補完的な組合せを体系的に探した。直前のTransition guard × Distribution Shiftだけを見た判断ではなく、正式configを持つ4候補・全6組を同じdevelopment規則で比較した。

## 固定候補と選択規則

- causal TCN 0.515
- Five-model Disagreement 0.515
- Transition guard 0.515
- Distribution Shift 0.51

全候補はbaseline方向を維持し、2,183,717 OOS行のfold、timestamp、target、correctを厳密整列した。閾値は各configに固定済みの値を使い、新しいgrid探索やconfidence平均を行わない。

各pairのdevelopment=test2020〜2023について、unionのselection scoreが両親の高い方を上回り、first-onlyとsecond-onlyのWilson正答率下限が両方50%を超える場合だけ選択する。confirmation=test2024〜2026途中は選択に使わず、同じ条件の監査だけを行う。目的関数は `sqrt(coverage) * (Wilson95Lower(accuracy) - 0.5)`、損失倍率は標準1.0のみである。

## 全6組のdevelopment screening

| pair | union score − better parent | exclusive edge | development Jaccard | 選択 |
|---|---:|---|---:|---|
| Disagreement + Shift | +0.0000454 | 両方確認 | 60.57% | 選択 |
| TCN + Shift | -0.0000236 | TCN-only未確認 | 58.80% | 不採用 |
| Transition guard + Shift | -0.0000777 | guard-only未確認 | 49.99% | 不採用 |
| TCN + Disagreement | -0.0000812 | 両方確認 | 80.61% | 不採用 |
| Disagreement + Transition guard | -0.0001345 | guard-only未確認 | 76.23% | 不採用 |
| TCN + Transition guard | -0.0002964 | 両方確認 | 76.62% | 不採用 |

6組中、事前gateを通ったのはDisagreement + Distribution Shiftだけだった。他5組はconfirmationを見る前に棄却される。

## 選択pairのconfirmation

| period | set | rows | coverage | accuracy | score |
|---|---|---:|---:|---:|---:|
| development | Disagreement | 360,525 | 26.9153% | 52.1609% | 0.010365 |
| development | Shift | 579,078 | 43.2316% | 51.7039% | 0.010357 |
| development | union | 585,157 | 43.6855% | 51.7030% | 0.010410 |
| confirmation | Disagreement | 73,946 | 8.7589% | 53.0306% | 0.007904 |
| confirmation | Shift | 198,605 | 23.5247% | 51.8985% | 0.008142 |
| confirmation | union | 198,991 | 23.5705% | 51.8913% | 0.008116 |
| all | Disagreement | 434,471 | 19.8959% | 52.3089% | 0.009636 |
| all | Shift | 777,683 | 35.6128% | 51.7536% | 0.009802 |
| all | union | 784,148 | 35.9089% | 51.7508% | 0.009829 |

developmentのDisagreement-onlyは6,079行、51.6203%、Wilson下限50.3634%でgateを通った。しかしconfirmationでは386行、48.1865%、Wilson下限43.2442%へ反転した。Shift-onlyはdevelopment 224,632行・50.9683%、confirmation 125,045行・51.2176%でedgeを維持した。したがってconfirmationのunionはShiftへ386行の負け越し集合を追加し、scoreを0.008142から0.008116へ下げた。

## 日次bootstrap

20,000回のUTC日paired block bootstrapを、materialize済みboolean採用列へ直接適用した。

| comparison / period | accuracy delta | coverage delta | score delta / 95% interval |
|---|---:|---:|---:|
| union − Shift / development | -0.0009pt | +0.4538pt | +0.0000529 / -0.0000320〜+0.0001379 |
| union − Shift / confirmation | -0.0072pt | +0.0457pt | -0.0000260 / -0.0000734〜+0.0000213 |
| union − Shift / all | -0.0028pt | +0.2961pt | +0.0000267 / -0.0000322〜+0.0000861 |
| union − Disagreement / development | -0.4578pt | +16.7701pt | +0.0000454 / -0.0005030〜+0.0005895 |
| union − Disagreement / confirmation | -1.1393pt | +14.8116pt | +0.0002120 / -0.0007841〜+0.0012132 |
| union − Disagreement / all | -0.5581pt | +16.0129pt | +0.0001925 / -0.0002870〜+0.0006795 |

union−Shiftで確定したのはcoverage増加だけで、accuracy・selection scoreは3期間すべて0を跨いだ。union−Disagreementではcoverage増加とaccuracy低下が確定し、scoreは未確定だった。集合比較はDisagreementの確率・confidenceを共通anchorとして保存するため、Brier/log loss差0は設計上の同一性であり改善証拠ではない。

## 信頼度品質

development unionの実績51.7030%に対し、Disagreement source meanは51.9817%、Shift source meanは52.1110%で両方過信・局所不整合だった。confirmationでは実績51.8913%に対し51.4522% / 51.5314%となり、両方過小評価・局所不整合へ反転した。

Disagreement-only自体はdevelopment/confirmationともmean confidenceがWilson区間内だが、行数が6,079から386へ縮小し、正答率が51.62%から48.19%へ反転した。unionは新しい各行oddsを学習しておらず、期間間で安定したfair oddsとはみなせない。

## 判断

固定4候補の全pairからdevelopment規則で唯一選ばれたDisagreement + Distribution Shift unionは、confirmationのexclusive edgeとselection scoreを再現しなかった。日次bootstrapも目的関数の増分を支持せず、source confidenceの期間間calibration driftも残る。

unionを再現専用として棄却し、新config、registry候補、authoritative confidence、fair odds、paper/live policyを発行しない。既存のTransition guard accuracy specialist、Distribution Shift ultra-broad、Disagreement balanced challenger、TCN sequence challengerを独立維持する。同じ4候補についてpair、union/intersection、閾値、source順、集合固有校正を履歴内再探索しない。

次の補完性探索では既存confidenceの再結合ではなく、異なる加工情報から独立した採用根拠を作り、exclusive edgeを事前固定条件として評価する。

## 成果物

- 全6組screening: `experiments/next_bar/m1_fixed_confidence_pairwise_complementarity_001.json`
- 選択pair詳細: `experiments/next_bar/disagreement_distribution_shift_selection_sets_m1_fixed_001`
- union−Shift bootstrap: `experiments/next_bar/disagreement_distribution_shift_union_vs_shift_m1_bootstrap.json`
- union−Disagreement bootstrap: `experiments/next_bar/disagreement_distribution_shift_union_vs_disagreement_m1_bootstrap.json`
- 実装: `methods/next_bar/scripts/pairwise_confidence_complementarity.py`
