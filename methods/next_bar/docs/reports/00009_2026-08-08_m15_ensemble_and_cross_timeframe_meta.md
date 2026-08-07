# 00009 M15 ensemble and cross-timeframe meta

日時: 2026-08-08 00:20 JST

## 目的

M15次足方向の全体accuracyと高信頼accuracyを、確率品質とfold再現性を壊さず改善する。

## 固定feature ensemble

baseline HGB確率75%とenhanced-manual HGB確率25%をブレンドした。weightは2022〜2026年で比較後に0.25へ固定し、このensemble設計に未使用だった2020〜2021年へ持ち込んだ。

- 2020 accuracy: 52.837% → 52.885%
- 2021 accuracy: 52.457% → 52.475%
- 7fold合算: 51.816% → 51.866%
- 6/7 fold改善
- confidence 0.54以上: 54.809% → 54.899%
- Brier: 0.2494261 → 0.2493985
- log loss: 0.6919985 → 0.6919426

一方、各foldで過去foldだけからweightを選ぶnested方式は、weightが0.25/0.75間で揺れ、2021〜2026年合算でbaseline比 `-0.031pt`。固定0.25の広い期間再現はあるが、weight選択そのもののforward evidenceではない。

## Cross-timeframe meta

M15/M5/M1の各direction modelによるOOS `probability_up` を同じdecision timestampでjoinした。各test foldでは、それ以前のOOS foldだけを使ってlogistic regressionを学習する。

```text
features = logit(P_M15), logit(P_M5), logit(P_M1)
P_final = 0.75 * P_M15 + 0.25 * P_meta
```

設定はC=0.10、meta weight=0.25。評価は最初の2020 foldをmeta学習に使い、2021〜2026途中の120,023行。

| metric | M15 baseline | cross-TF blend | delta |
|---|---:|---:|---:|
| accuracy | 51.645% | 51.718% | +0.073pt |
| balanced accuracy | 51.591% | 51.648% | +0.057pt |
| Brier | 0.2495634 | 0.2495398 | -0.0000236 |
| log loss | 0.6922743 | 0.6922268 | -0.0000475 |
| ECE | 0.504% | 0.406% | -0.098pt |

fold accuracyは2021、2022、2023、2024、2026途中で改善し、2025だけ `-0.117pt`。5/6 fold改善。

## 高信頼帯

| threshold | baseline rows / accuracy | candidate rows / accuracy |
|---|---:|---:|
| 0.53 | 29,962 / 54.012% | 29,260 / 54.029% |
| 0.54 | 17,117 / 54.408% | 16,676 / 54.479% |
| 0.55 | 9,721 / 54.819% | 9,461 / 54.941% |

高信頼accuracyは上がったがcoverageは2.7〜3.3%相対で減った。accuracy/coverageの交換として小さい範囲に収まる。

## 売買候補への影響

固定feature ensembleはM15 confidence 0.54以上のgross meanを `0.09781 -> 0.11263/oz` へ上げたが、all-fold cost ceilingは `0.05415 -> 0.04732` へ低下し、cost 0.05 positive foldは6/6から5/6になった。したがって既存paper売買policyはbaselineのまま維持する。

## 判断

- cross-timeframe blendをaccuracy改善のforward candidateとして採用する。
- 現行M15方向モデルとpaper売買policyはまだ置換しない。
- Cとmeta weightはここで固定し、追加探索しない。
- 次の完全未使用期間でaccuracyとBrierが両方baseline以上なら昇格を検討する。
- 固定設定: `methods/next_bar/config/m15_cross_tf_meta_candidate_v1.json`
