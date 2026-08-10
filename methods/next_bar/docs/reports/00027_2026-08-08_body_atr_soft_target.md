# 00027 Body/ATR soft direction target

日時: 2026-08-08 07:22 JST

## 目的

clear-body filterは曖昧な小実体教師を半分捨てることでconfidence選別を改善した。そこで全教師を残しつつ、小さい次足は0.5付近、大きく明確な次足だけ0/1へ近づけるbounded soft targetを試す。

## 結果前に固定した方法

教師確率は次式とした。

```text
soft P(up) = 0.5 + direction_sign * 0.5 * tanh(next_bar_body / decision_ATR20)
```

- 実装: `--model-type body_atr_soft_hgb`
- model: baselineと同じ38加工特徴からHGB squared-error regression。
- 未来の次足実体/ATRは教師変換だけに使い、feature manifest、calibration、test/latest入力には含めない。
- 回帰出力を0〜1へclipし、後続calibration期間だけでPlatt校正する。
- M15 2020〜2026途中の同一7fold、固定25% blend。confidence閾値はdevelopment 2020〜2023だけで選び、confirmationへ固定する。

教師変換の境界、artifact保存、feature除外、latest predictionをテストした。

## 単体と通常blend

| period | model | accuracy | Brier | log loss | ECE |
|---|---|---:|---:|---:|---:|
| all | baseline | 51.816% | 0.2494261 | 0.6919985 | 0.347% |
| all | soft target single | 51.565% | 0.2495035 | 0.6921534 | 0.201% |
| confirmation | baseline | 51.501% | 0.2495525 | 0.6922506 | 0.298% |
| confirmation | soft target single | 51.440% | 0.2495994 | 0.6923446 | 0.094% |

単体はECEを縮めるが、方向accuracy、Brier、log lossが悪化するため棄却する。通常25% blendはconfirmation accuracyを51.501%から51.542%へ上げたが、developmentと全体は悪化した。誤り修正2,330件、新規誤り2,370件、McNemar exact p=0.569のため方向edgeとして採用しない。

## 方向維持型confidence blend

| period | metric | baseline | candidate |
|---|---|---:|---:|
| development | Brier | 0.2493466 | 0.2493070 |
| development | log loss | 0.6918398 | 0.6917594 |
| development | ECE | 0.377% | 0.191% |
| confirmation | Brier | 0.2495525 | 0.2495418 |
| confirmation | log loss | 0.6922506 | 0.6922294 |
| confirmation | ECE | 0.298% | 0.190% |
| all | Brier | 0.2494261 | 0.2493977 |
| all | log loss | 0.6919985 | 0.6919409 |
| all | ECE | 0.347% | 0.191% |

3指標はdevelopment/confirmation合算で改善し、fold改善はBrier、log loss、ECEとも5/7だった。

## developmentで選んだconfidence 0.525 lane

| period | model | rows | coverage | accuracy | selection score |
|---|---|---:|---:|---:|---:|
| development | baseline | 33,770 | 37.908% | 53.858% | 0.02048 |
| development | soft target | 30,066 | 33.751% | 54.217% | 0.02123 |
| confirmation | baseline | 14,785 | 26.375% | 53.777% | 0.01527 |
| confirmation | soft target | 13,000 | 23.191% | 54.092% | 0.01558 |
| all | baseline | 48,555 | 33.454% | 53.834% | 0.01961 |
| all | soft target | 43,066 | 29.672% | 54.180% | 0.02020 |

accuracyは7/7 fold改善したが、selection scoreは5/7で、2023と2024はcoverage減少が精度上昇を上回った。

## clear-body 0.525との比較

| period | candidate | coverage | accuracy | selection score |
|---|---|---:|---:|---:|
| development | clear-body filter | 35.639% | 54.173% | 0.02164 |
| development | soft target | 33.751% | 54.217% | 0.02123 |
| confirmation | clear-body filter | 24.714% | 54.201% | 0.01675 |
| confirmation | soft target | 23.191% | 54.092% | 0.01558 |
| all | clear-body filter | 31.419% | 54.182% | 0.02088 |
| all | soft target | 29.672% | 54.180% | 0.02020 |

soft targetはdevelopment accuracyだけ僅かに高いが、confirmationと全体ではclear-bodyがcoverage、accuracy、selection scoreを同時に上回る。clear-bodyはBrier/log loss 7/7、lane score 7/7改善でもあり、soft targetを支配する。

## 判断

- soft target単体と通常方向blendは棄却する。
- 方向維持型0.525は有効性を示したが、同じ教師情報を使うclear-body 0.525に劣後するためforward configを発行しない。
- `tanh` scaleや別softening関数を今回の履歴へ合わせて再探索しない。明確な足の情報を使う正式候補はclear-body filterに集約する。
- authoritative confidence、odds、現行採用policy、paper policyは変更しない。
- 損失倍率は標準1.0のみとする。
