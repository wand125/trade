# 00014 Fixed three-year rolling training window

日時: 2026-08-08 01:31 JST

## 目的

古い市場状態を学習から外し、近年のregimeへ追従することでM15方向精度を改善できるか確認する。

## 設計

現行は各foldの `train_end` より前の全履歴を使うexpanding学習。candidateはtrainだけを直前1095日に固定した。

```text
train_start = train_end - 1095 days
train_start <= decision_timestamp < train_end
```

calibration期間、test期間、baseline加工特徴、HGB parameter、random seedは変更していない。window長は3年に事前固定し、結果を見た後の長さ探索はしない。実験は `walk_forward_rolling_3y_001`。

## 結果

| period | model | accuracy | balanced accuracy | Brier | log loss | ECE |
|---|---|---:|---:|---:|---:|---:|
| 2020–2023 | expanding | 52.014% | 52.005% | 0.2493466 | 0.6918398 | 0.377% |
| 2020–2023 | rolling 3y | 51.674% | 51.662% | 0.2495048 | 0.6921561 | 0.200% |
| 2024–2026途中 | expanding | 51.501% | 51.270% | 0.2495525 | 0.6922506 | 0.298% |
| 2024–2026途中 | rolling 3y | 51.064% | 50.648% | 0.2497929 | 0.6927327 | 0.504% |
| all | expanding | 51.816% | 51.756% | 0.2494261 | 0.6919985 | 0.347% |
| all | rolling 3y | 51.439% | 51.338% | 0.2496161 | 0.6923788 | 0.317% |

rollingは全体accuracyを-0.378pt、confirmationを-0.437pt悪化させ、7/7 foldすべてでexpanding accuracyを下回った。

## 高信頼帯

| threshold | expanding accuracy / coverage / score | rolling accuracy / coverage / score |
|---|---:|---:|
| 0.53 | 54.357% / 25.453% / 0.01942 | 54.100% / 16.771% / 0.01422 |
| 0.54 | 54.809% / 14.391% / 0.01568 | 54.423% / 8.514% / 0.01034 |
| 0.55 | 55.501% / 8.067% / 0.01306 | 55.064% / 4.361% / 0.00801 |

confirmationのconfidence 0.54 selection scoreは0.01116から0.00375へ低下した。近年データだけでは高信頼候補のsupportも不足する。

## 判断

- 固定3年rolling trainingは不採用。
- window長を履歴へ合わせて追加探索しない。
- 現行のexpanding trainingを維持する。
- `--train-window-days` 実装はregime drift研究の再現用として残す。既定値0は従来どおり全履歴を使う。
