# 00022 Signed-body regression confidence

日時: 2026-08-08 06:08 JST

## 目的

次足をup/downだけで教師化すると、小さいノイズ足と大きく明確な足が同じ1件になる。そこで次足実体を判定時点の過去20本ATRで正規化し、方向符号を付けた連続教師を学習して、方向確率と高信頼度選別を改善できるか確認する。

## 固定した方法

教師は次式とした。

```text
signed target = sign(next bar close - open)
                * asinh(abs(next bar close - open) / decision-time ATR20)
```

`asinh` は小さい値ではほぼ線形、大きい値では対数的に圧縮するため、値幅情報を保ちながら外れ値支配を抑える。未来の次足実体は教師にだけ使い、feature manifestへは含めない。

baselineと同じ38加工特徴からHGB regressionを学習し、回帰値を単調sigmoidへ通した後、次のchronological calibration期間だけでPlatt校正する。実装名は `--model-type signed_body_hgb`。HGB parameter、2020〜2026途中の7fold、固定blend weight 25%は従来比較と同一。

## 単体と通常blend

| period | model | accuracy | Brier | log loss | ECE |
|---|---|---:|---:|---:|---:|
| all | baseline binary HGB | 51.816% | 0.2494261 | 0.6919985 | 0.347% |
| all | signed-body regression | 51.349% | 0.2496294 | 0.6924052 | 0.070% |
| confirmation | baseline binary HGB | 51.501% | 0.2495525 | 0.6922506 | 0.298% |
| confirmation | signed-body regression | 50.959% | 0.2496742 | 0.6924944 | 0.314% |

単体の低ECEは平均confidenceを51.4%へ縮めた結果で、方向精度・Brier・log lossは悪化した。方向モデルとして棄却する。

通常25% blendも全体accuracy 51.802%、confirmation 51.485%でbaselineを下回った。誤り修正2,675件、新規誤り2,695件、McNemar exact p=0.795のため方向用途には採用しない。

## 方向維持型confidence blend

baseline方向を固定し、signed-body modelを25%だけconfidence edgeへ使った。

| period | metric | baseline | candidate |
|---|---|---:|---:|
| 2020–2023 | Brier | 0.2493466 | 0.2493113 |
| 2020–2023 | log loss | 0.6918398 | 0.6917680 |
| 2020–2023 | ECE | 0.377% | 0.052% |
| 2024–2026途中 | Brier | 0.2495525 | 0.2495474 |
| 2024–2026途中 | log loss | 0.6922506 | 0.6922405 |
| 2024–2026途中 | ECE | 0.298% | 0.102% |
| all | Brier | 0.2494261 | 0.2494025 |
| all | log loss | 0.6919985 | 0.6919505 |
| all | ECE | 0.347% | 0.071% |

3指標はdevelopment・confirmationの両方で改善した。fold単位では各4/7改善なので、確率品質だけでauthoritative confidenceへ昇格するにはまだ弱い。

## developmentで選んだconfidence 0.52 lane

固定候補グリッド0.515、0.52、0.525、0.53、0.54、0.55、0.60をdevelopmentだけで比較した。candidateのselection scoreが最大でbaselineも上回った0.52を選び、confirmationでは変更せず評価した。

| period | model | rows | coverage | accuracy | Wilson lower | selection score |
|---|---|---:|---:|---:|---:|---:|
| 2020–2023 | baseline | 42,153 | 47.319% | 53.379% | 52.903% | 0.01997 |
| 2020–2023 | candidate | 35,839 | 40.231% | 53.807% | 53.291% | 0.02087 |
| 2024–2026途中 | baseline | 20,545 | 36.650% | 52.918% | 52.235% | 0.01353 |
| 2024–2026途中 | candidate | 17,235 | 30.745% | 53.594% | 52.849% | 0.01580 |
| all | baseline | 62,698 | 43.198% | 53.228% | 52.837% | 0.01865 |
| all | candidate | 53,074 | 36.567% | 53.738% | 53.314% | 0.02004 |

全体ではcoverageを6.63pt絞る代わりにaccuracyを0.510pt上げ、selection scoreを7.45%改善した。年別accuracyは7/7 fold、selection scoreは6/7 foldで改善した。confirmationではaccuracy +0.677pt、score +16.76%で再現した。

0.55ではaccuracyが55.50%から56.02%へ上がるがcoverage縮小でscoreが0.01306から0.01167へ下がるため採用しない。0.525はdevelopmentで改善したがconfirmation scoreが低下し、0.53以上も同様。固定候補は0.52だけとする。

## 判断

- signed-body regression単体と通常blendは方向用途として棄却する。
- baseline方向維持型25% blend + confidence 0.52を、広いcoverageを持つ `m15_signed_body_confidence_candidate_v1.json` のforward candidateへ固定する。
- authoritative confidence、odds、既存adoption policy、paper policyは次の完全未使用期間まで変更しない。
- 既存のExtra Trees 0.53、body/ATR weighted 0.54、intrabar 0.55候補と履歴上でstack・再最適化しない。0.52は独立した広coverage laneとしてforward比較する。
- 損益は目的関数へ含めず、損失倍率は標準1.0のみとする。
