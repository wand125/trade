# 00016 Isotonic probability calibration

日時: 2026-08-08 01:48 JST

## 目的

現行のparametricなPlatt校正に対し、単調な非線形写像を学ぶisotonic regressionでM15の確率・信頼度オッズを改善できるか確認する。

## 固定条件

- 方向モデルは現行HGB、baseline 38加工特徴、全parameterを固定
- 2020〜2026途中の同一7fold expanding walk-forward
- 各foldのcalibration期間だけでisotonic写像を学習し、後続testへ適用
- `y_min=1e-6`、`y_max=1-1e-6`、範囲外は端点へclip
- 閾値比較は0.53/0.54/0.55/0.60/0.80。結果を見た追加parameter調整はしない

実験は `walk_forward_isotonic_001`。方向固定診断は `isotonic_confidence_001`。

## 全確率を置換した結果

| period | calibration | accuracy | balanced accuracy | Brier | log loss | ECE |
|---|---|---:|---:|---:|---:|---:|
| 2020–2023 | Platt | 52.014% | 52.005% | 0.2493466 | 0.6918398 | 0.377% |
| 2020–2023 | isotonic | 52.027% | 52.022% | 0.2495555 | 0.6934277 | 0.570% |
| 2024–2026途中 | Platt | 51.501% | 51.270% | 0.2495525 | 0.6922506 | 0.298% |
| 2024–2026途中 | isotonic | 51.259% | 51.128% | 0.2497840 | 0.6932068 | 0.940% |
| all | Platt | 51.816% | 51.756% | 0.2494261 | 0.6919985 | 0.347% |
| all | isotonic | 51.730% | 51.696% | 0.2496438 | 0.6933424 | 0.713% |

isotonicはconfirmationでaccuracyを-0.243pt悪化させた。Platt誤りを直した1,740件に対し新規誤り1,876件で、paired exact p=0.0248。Brier、log loss、ECEもdevelopmentとconfirmationの両方で悪化した。

## 方向固定によるconfidence単独診断

isotonicの0.5境界移動を除くため、方向を現行HGBへ固定し、isotonic確率のedgeだけをconfidenceとして評価した。

| period | calibration | Brier | log loss | ECE | confidence 0.54 accuracy / rows / score |
|---|---|---:|---:|---:|---:|
| 2020–2023 | Platt | 0.2493466 | 0.6918398 | 0.377% | 54.675% / 16,172 / 0.01664 |
| 2020–2023 | isotonic | 0.2495543 | 0.6934252 | 0.563% | 55.025% / 15,153 / 0.01745 |
| 2024–2026途中 | Platt | 0.2495525 | 0.6922506 | 0.298% | 55.270% / 4,715 / 0.01116 |
| 2024–2026途中 | isotonic | 0.2497672 | 0.6931732 | 0.665% | 53.625% / 6,620 / 0.00832 |

developmentではconfidence 0.54のselection scoreが上がったが、同じ閾値のconfirmationで大きく悪化した。0.53も全体score `0.01942 -> 0.01611`、confirmation `0.01511 -> 0.01474` と悪化した。

さらにisotonicのconfidence 0.80以上は85件、平均confidence 89.23%に対しaccuracy 55.29%、Wilson下限44.72%だった。少数のstepに局所適合し、高信頼度を過大評価している。

## 判断

- isotonicを方向確率、authoritative confidence、odds、採用policyのいずれにも採用しない。
- 標準校正はPlattのままとする。
- `--probability-calibration isotonic` は再現実験用として残し、別parameterや閾値を履歴へ合わせて追加探索しない。
- この実験は方向と確率品質だけを評価し、損益目的関数は使用していない。
