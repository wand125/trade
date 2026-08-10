# 00025 Causal TCN sequence model

日時: 2026-08-08 06:53 JST

## 目的

手作業lagを木へ平坦に渡す方式では捉えにくい時間順序を、小型の因果畳み込みで直接学習する。生OHLC水準は使わず、加工した直近系列だけを入力する独立deep-learning候補とする。

## 固定した方法

- 実装: `--feature-set tcn_sequence --model-type tcn`
- 入力窓: 完成足16本、5 channel。ATR正規化return・body・range、中心化close location、ATR正規化wick balance。
- 標準化: channelごとのmean/stdを各foldのtrainだけで推定し、calibration/testへ固定。
- network: kernel 3の因果Conv1d 2層、2層目dilation 2、hidden 16、last/mean pooling、1,073 parameters。
- 学習: AdamW、8 epoch、batch 2,048、learning rate 0.001、weight decay 0.0001、seed 42。
- 確率: 後続calibration期間だけでPlatt校正。
- PyTorchはIntel macOSのみ互換上限2.2/NumPy 1.26、他platformはPyTorch 2.4以上を依存定義した。

未来のOHLCを改変しても過去のsequence featureが変わらないテスト、artifact保存後のlatest prediction、実データ最新推論まで通した。

## 単体と通常blend

| period | model | accuracy | Brier | log loss | ECE |
|---|---|---:|---:|---:|---:|
| all | baseline | 51.816% | 0.2494261 | 0.6919985 | 0.347% |
| all | TCN single | 51.642% | 0.2495703 | 0.6922877 | 0.239% |
| confirmation | baseline | 51.501% | 0.2495525 | 0.6922506 | 0.298% |
| confirmation | TCN single | 51.250% | 0.2496389 | 0.6924242 | 0.235% |

単体はECE以外が悪化したため棄却する。通常25% blendは全体51.825%だが、誤り修正2,825件・新規誤り2,812件、McNemar exact p=0.873で方向edgeではない。confirmation accuracyは51.449%へ悪化した。

## 方向維持型confidence blend

| period | metric | baseline | candidate |
|---|---|---:|---:|
| development | Brier | 0.2493466 | 0.2493238 |
| development | log loss | 0.6918398 | 0.6917935 |
| development | ECE | 0.377% | 0.239% |
| confirmation | Brier | 0.2495525 | 0.2495467 |
| confirmation | log loss | 0.6922506 | 0.6922392 |
| confirmation | ECE | 0.298% | 0.179% |
| all | Brier | 0.2494261 | 0.2494099 |
| all | log loss | 0.6919985 | 0.6919656 |
| all | ECE | 0.347% | 0.216% |

3指標はdevelopment/confirmationとも改善し、fold単位では各5/7改善した。

## developmentで選んだconfidence 0.52 lane

| period | model | rows | coverage | accuracy | selection score |
|---|---|---:|---:|---:|---:|
| development | baseline | 42,153 | 47.319% | 53.379% | 0.01997 |
| development | candidate | 40,479 | 45.440% | 53.569% | 0.02078 |
| confirmation | baseline | 20,545 | 36.650% | 52.918% | 0.01353 |
| confirmation | candidate | 19,045 | 33.974% | 53.216% | 0.01461 |
| all | baseline | 62,698 | 43.198% | 53.228% | 0.01865 |
| all | candidate | 59,524 | 41.011% | 53.456% | 0.01956 |

accuracyとselection scoreは6/7 foldで改善した。ただし既存signed-body 0.52候補は全体score 0.02004、confirmation 0.01580でTCNを上回る。

## 判断

- TCN単体と通常方向blendは棄却する。
- 方向維持型25% blend + confidence 0.52は独立sequenceの有効性を示したが、同じ広coverage目的のsigned-body候補より評価関数が低いため `m15_tcn_confidence_shadow_v1.json` のshadowへ固定する。
- TCNのepoch、窓長、channel数を今回の履歴へ合わせて再探索しない。次は別の完全未使用期間でshadow再現性を測るか、事前固定した別architectureとして小型Transformerを独立評価する。
- authoritative confidence、odds、現行採用policy、paper policyは変更しない。
- 損失倍率は標準1.0のみとする。
