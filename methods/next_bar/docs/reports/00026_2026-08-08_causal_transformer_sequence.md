# 00026 Causal Transformer sequence model

日時: 2026-08-08 07:16 JST

## 目的

TCNとは異なるsequence inductive biasとして、完成足系列をself-attentionで処理する小型因果Transformerを独立評価する。入力データは共通化し、モデル方式だけを独立させる。

## 結果前に固定した方法

- 実装: `--feature-set tcn_sequence --model-type causal_transformer`
- 入力: 完成足16本×5 channel。ATR正規化return/body/range、中心化close location、ATR正規化wick balance。
- 標準化: 各foldのtrainだけでchannel mean/stdを推定し、calibration/testへ固定。
- network: learned position、model dimension 16、4-head、encoder 1層、feed-forward 32、dropout 0、last-token pooling、2,625 parameters。
- 学習: AdamW、8 epoch、batch 2,048、learning rate 0.0005、weight decay 0.0001、seed 42。
- 確率: 後続calibration期間だけでPlatt校正。
- 評価: M15 2020〜2026途中の同一7fold、固定25% blend。confidence閾値はdevelopment 2020〜2023だけで選び、confirmationへ固定。

2020 pilotは実行安定性だけを確認し、parameterを変更せず7foldへ進んだ。学習lossは0.7048から0.6908へ収束した。artifact保存、同一seed完全一致、latest predictionをテストした。

## 単体と通常blend

| period | model | accuracy | Brier | log loss | ECE |
|---|---|---:|---:|---:|---:|
| all | baseline | 51.816% | 0.2494261 | 0.6919985 | 0.347% |
| all | Transformer single | 51.536% | 0.2496817 | 0.6925107 | 0.218% |
| confirmation | baseline | 51.501% | 0.2495525 | 0.6922506 | 0.298% |
| confirmation | Transformer single | 51.153% | 0.2497340 | 0.6926147 | 0.357% |

単体は方向accuracy、Brier、log lossを明確に悪化させたため棄却する。通常25% blendも全体51.769%、confirmation 51.412%でbaseline未満。誤り修正3,262件、新規誤り3,331件、McNemar exact p=0.402で方向edgeはない。

## 方向維持型confidence blend

| period | metric | baseline | candidate |
|---|---|---:|---:|
| development | Brier | 0.2493466 | 0.2493336 |
| development | log loss | 0.6918398 | 0.6918130 |
| development | ECE | 0.377% | 0.153% |
| confirmation | Brier | 0.2495525 | 0.2495623 |
| confirmation | log loss | 0.6922506 | 0.6922705 |
| confirmation | ECE | 0.298% | 0.167% |
| all | Brier | 0.2494261 | 0.2494220 |
| all | log loss | 0.6919985 | 0.6919897 |
| all | ECE | 0.347% | 0.158% |

ECEは大きく縮小したが、confirmationのBrier/log lossは悪化した。fold改善はBrier 3/7、log loss 3/7、ECE 4/7で、authoritative confidenceに必要な確率品質の再現性がない。

## developmentで選んだconfidence 0.52 lane

| period | model | rows | coverage | accuracy | selection score |
|---|---|---:|---:|---:|---:|
| development | baseline | 42,153 | 47.319% | 53.379% | 0.01997 |
| development | candidate | 39,368 | 44.192% | 53.607% | 0.02070 |
| confirmation | baseline | 20,545 | 36.650% | 52.918% | 0.01353 |
| confirmation | candidate | 18,965 | 33.832% | 53.282% | 0.01496 |
| all | baseline | 62,698 | 43.198% | 53.228% | 0.01865 |
| all | candidate | 58,333 | 40.191% | 53.501% | 0.01963 |

accuracyは6/7 fold、selection scoreは5/7 foldで改善した。しかし同じ0.52広coverage候補のsigned-bodyはdevelopment 0.02087、confirmation 0.01580、全体0.02004でTransformerをすべて上回る。2026途中foldではTransformerのselection scoreもbaselineを下回った。

## 判断

- Transformer単体と通常方向blendは棄却する。
- 方向維持型0.52はselective accuracyを改善したが、confirmation Brier/log loss悪化、proper score 3/7、既存signed-body候補より低いselection scoreのためforward configを発行しない。
- 実装は独立architectureの再現用として残すが、この履歴へepoch、窓長、head数、dimensionを合わせる再探索は行わない。
- authoritative confidence、odds、現行採用policy、paper policyは変更しない。
- 損失倍率は標準1.0のみとする。
