# 00021 Beta probability calibration

日時: 2026-08-08 06:01 JST

## 目的

予測信頼度をフェアオッズとして使うため、Plattより柔軟でisotonicより滑らかなbeta calibrationをM15へ適用し、確率品質と高信頼度選別を改善できるか確認する。

## 固定した方法

raw probabilityを `log(p)` と `-log(1-p)` へ加工し、正解ラベルに対するロジスティック曲線を学習した。2係数を0以上へ制約して単調性を保証し、未来testの順位を入れ替えない。各foldでdirection HGBのtrainは従来どおり、それより後のcalibration期間だけでbeta係数を学習し、次のtestへ固定適用した。

実装は `--probability-calibration beta`。2020〜2026途中の同一7fold、baseline 38特徴、HGB parameter、学習期間はPlatt比較と同一。方向変化を分離するため、baseline方向を維持しbetaのconfidence強度だけを100%使う診断も事前固定で実施した。

## beta単体

| period | model | accuracy | Brier | log loss | ECE |
|---|---|---:|---:|---:|---:|
| 2020–2023 | Platt | 52.014% | 0.2493466 | 0.6918398 | 0.377% |
| 2020–2023 | beta | 52.007% | 0.2493623 | 0.6918721 | 0.401% |
| 2024–2026途中 | Platt | 51.501% | 0.2495525 | 0.6922506 | 0.298% |
| 2024–2026途中 | beta | 51.549% | 0.2495593 | 0.6922646 | 0.280% |
| all | Platt | 51.816% | 0.2494261 | 0.6919985 | 0.347% |
| all | beta | 51.830% | 0.2494384 | 0.6920237 | 0.353% |

confirmation方向精度は0.048pt上がったが、主目的のBrierとlog lossはdevelopment・confirmationの両方で悪化した。全体ECEも悪化しているため、方向精度の小差だけでは採用しない。

## 方向固定confidence診断

方向をPlatt baselineに固定しても、beta confidenceのBrierは0.2494383、log lossは0.6920236、ECEは0.366%で、baselineの0.2494261、0.6919985、0.347%を全て下回った。fold改善はBrier 2/7、log loss 2/7、ECE 4/7だけだった。

| period | confidence | model | rows | accuracy | selection score |
|---|---:|---|---:|---:|---:|
| all | 0.53 | Platt | 36,943 | 54.357% | 0.01942 |
| all | 0.53 | beta | 37,195 | 54.376% | 0.01959 |
| all | 0.55 | Platt | 11,708 | 55.501% | 0.01306 |
| all | 0.55 | beta | 11,757 | 55.465% | 0.01299 |
| confirmation | 0.55 | Platt | 1,887 | 55.750% | 0.00642 |
| confirmation | 0.55 | beta | 1,952 | 54.867% | 0.00495 |

0.53は合算scoreだけ僅かに改善したがdevelopmentでは悪化し、0.55はconfirmationで明確に悪化した。高信頼採用laneにも使わない。

各foldの制約付きbeta係数は、7/7で2係数の片方が0の境界へ張り付き、使用する片側も年によって交互に変わった。raw HGB確率の狭い範囲では追加自由度が安定した曲率として推定されていない。

## 判断

- beta calibrationは方向、confidence/odds、高信頼採用条件の全用途で棄却する。
- 標準は `--probability-calibration platt` のままとする。
- `beta` 実装は単調性・artifact保存・最新推論テスト付きの再現実験用として残す。係数制約や正則化を履歴へ合わせて再調整しない。
- 損益は目的関数へ含めておらず、損失倍率1.2の特別ルールも使っていない。
