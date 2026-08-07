# 00007 Adoption policy optimization

日時: 2026-08-07 18:50 JST

## 目的

正答率だけを最大化してprediction coverageが消える問題を避け、方向モデルを変更せずに採用条件を最適化する。

## 評価関数

```text
selection_score = coverage^0.5 * (Wilson accuracy lower bound - 0.50)
```

- Wilson z: 1.96
- minimum rows: 500
- minimum coverage: 1%
- candidate: confidence threshold、predicted direction、volatility regime、UTC hour、固定6時間帯
- quality score: `200 * max(Wilson lower bound - 0.50, 0)`

正答率ではなく95% Wilson下限を使い、少数件だけの高精度を抑制した。coverage power 0.5はqualityだけを選ぶ0と、全機会あたりの正答超過を選ぶ1の中間である。

## 同一5foldでの旧条件との比較

| TF | policy | coverage | accuracy | Wilson lower | selection score |
|---|---|---:|---:|---:|---:|
| M1 | fixed context | 42.37% | 50.93% | 50.81% | 0.00525 |
| M1 | optimized | 22.42% | 51.76% | 51.59% | 0.00751 |
| M5 | fixed context | 3.79% | 51.93% | 51.01% | 0.00196 |
| M5 | optimized | 42.54% | 52.17% | 51.90% | 0.01238 |
| M15 | fixed context | 42.95% | 51.60% | 51.12% | 0.00737 |
| M15 | optimized | 25.00% | 53.79% | 53.17% | 0.01585 |
| M30 | fixed context | 3.76% | 54.15% | 51.85% | 0.00359 |
| M30 | optimized | 46.29% | 52.60% | 51.95% | 0.01324 |

この表のoptimized値は全5foldで条件を選び同じ全5foldへ当てたreference値であり、条件選択後の完全未知評価ではない。条件選択processの評価には次のnested結果を使う。

## Nested chronological validation

各評価foldについて、それより前のout-of-sample foldだけでruleを選び、次foldへ固定適用した。

| TF | selected rows | coverage | accuracy | Wilson lower | worst fold | selection score |
|---|---:|---:|---:|---:|---:|---:|
| M1 | 325,131 | 28.40% | 51.30% | 51.12% | 50.73% | 0.00599 |
| M5 | 49,218 | 21.43% | 52.72% | 52.28% | 52.37% | 0.01057 |
| M15 | 19,273 | 25.52% | 53.02% | 52.31% | 50.00% | 0.01168 |
| M30 | 35,315 | 95.66% | 51.56% | 51.04% | 51.34% | 0.01020 |

M5は旧UTC21条件より大幅にcoverageが増え、nestedの全評価foldで52%を超えた。M15は合算品質が最も高いがworst foldは50.00%である。M30は選択ruleが時期によって広くなり、合算coverage 95.66%となったため、最新final ruleの46.29%と乖離している。これはpolicy driftとして監視対象にする。

## 最終rule

| TF | rule | reference accuracy | reference coverage |
|---|---|---:|---:|
| M1 | confidence >= 0.51060 and volatility normal/high | 51.76% | 22.42% |
| M5 | confidence >= 0.51500 | 52.17% | 42.54% |
| M15 | confidence >= 0.52723 | 53.79% | 25.00% |
| M30 | confidence >= 0.51500 | 52.60% | 46.29% |

成果物は `methods/next_bar/config/optimized_policy_v1.json`。最終ruleは今後の新規期間へ固定して評価し、同じ履歴で再調整しない。

## 判断

- accuracyとcoverageの明示的なtrade-off最適化は旧固定contextより全時間足でselection scoreを改善した。
- 予測品質はまだ数ポイントの方向edgeであり、quality scoreを利益率として扱わない。
- 次は方向の正否とは独立に、次足の実体値幅をATR単位で予測するmove-qualityを追加する。
