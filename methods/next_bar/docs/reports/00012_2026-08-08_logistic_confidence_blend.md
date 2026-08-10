# 00012 Logistic diversity and direction-preserving confidence blend

日時: 2026-08-08 01:24 JST

## 目的

非線形HGBと異なる誤り・確率形状を持つ線形モデルを追加し、M15の方向精度または信頼度オッズを改善できるか確認する。

## 固定条件

- 入力はbaselineと同じ38個の加工済み定常特徴
- raw OHLC価格水準は不使用
- StandardScaler + L2 logistic regression
- C=0.10
- 2020〜2026途中の同一7fold
- blendはHGB 75% + logistic 25%。weightは既存ensembleと同じ値へ事前固定し、探索しない

実験は `walk_forward_logistic_001`。

## 方向モデルとしての比較

| model | accuracy | balanced accuracy | Brier | log loss | ECE |
|---|---:|---:|---:|---:|---:|
| HGB baseline | 51.816% | 51.756% | 0.2494261 | 0.6919985 | 0.347% |
| logistic | 51.747% | 51.664% | 0.2495167 | 0.6921804 | 0.223% |
| unrestricted 25% blend | 51.814% | 51.748% | 0.2494085 | 0.6919627 | 0.257% |

logistic単体は方向精度とproper scoring ruleが悪化した。通常blendは全体accuracyがbaseline比-0.002ptとほぼ同じだが、2024〜2026途中のconfirmation accuracyは `51.501% -> 51.396%` と悪化した。paired純差は-3件、McNemar近似p=0.978。方向モデルとしては両方棄却する。

## 方向維持型confidence blend

通常blendが0.5をまたぐと方向まで変わる。そこでHGB方向を固定し、blendは確率edgeの大きさだけに利用した。

```text
raw_blend = 0.75 * P_HGB + 0.25 * P_logistic
aligned_edge = sign(P_HGB - 0.5) * (raw_blend - 0.5)
candidate_edge = max(aligned_edge, machine_epsilon)
P_candidate = 0.5 + sign(P_HGB - 0.5) * candidate_edge
```

logisticがHGB方向を0.5越しに否定した場合、その反対意見をHGB方向への強いconfidenceとして反射せず、confidenceをほぼ0.50へ落とす。

| period | metric | baseline | candidate |
|---|---|---:|---:|
| 2020–2023 | Brier | 0.2493466 | 0.2493243 |
| 2020–2023 | log loss | 0.6918398 | 0.6917943 |
| 2020–2023 | ECE | 0.377% | 0.263% |
| 2024–2026途中 | Brier | 0.2495525 | 0.2495444 |
| 2024–2026途中 | log loss | 0.6922506 | 0.6922345 |
| 2024–2026途中 | ECE | 0.298% | 0.224% |
| all | Brier | 0.2494261 | 0.2494093 |
| all | log loss | 0.6919985 | 0.6919643 |
| all | ECE | 0.347% | 0.248% |

方向とaccuracyはbaselineと完全に同じ。Brier、log loss、ECEはdevelopmentとconfirmationの両方で改善した。fold単位ではBrier/log lossが4/7、ECEが5/7で改善し、合算改善は一部foldに限定された偶然ではない。

成果物は `logistic_confidence_blend_001`。

## 高信頼採用条件への影響

confidence 0.54以上はaccuracy `54.809% -> 54.827%` とわずかに上がる一方、coverage `14.391% -> 12.769%`、selection score `0.01568 -> 0.01468`。coverage低下を補うほどの精度向上ではない。

confirmationのconfidence 0.55以上はaccuracy `55.750% -> 57.153%` だが、developmentの同条件ではselection scoreが悪化した。結果を見た後に0.55だけを採用することはしない。

## 判断

- logistic単体と通常25% blendは方向モデルとして不採用。
- 方向維持型blendを `m15_logistic_confidence_blend_candidate_v1.json` として、代替confidence/oddsのforward candidateに採用する。
- 現行方向、authoritative confidence、採用policy、paper売買policyはまだ変更しない。
- 新規期間では同じ方向に対するBrier、log loss、ECEだけを事前指定指標として比較する。
- 3指標がすべてbaseline以下ならauthoritative confidenceへの昇格を検討する。
