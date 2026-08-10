# 00035 Four-class body target

日時: 2026-08-10 13:42 JST

## 目的

clear-body教師の有効性を、曖昧な小実体足を捨てずに利用できる教師表現へ拡張する。次足を方向と実体大小の4クラスとして同時学習し、方向確率とconfidence選別を改善できるか確認する。

## 結果前に固定した方法

- model type: `--model-type body_multiclass_hgb`
- 各foldで実際に学習へ渡すtrainの `next_bar_body_atr` 中央値だけを大小境界に使う。
- class 0: down-large
- class 1: down-small
- class 2: up-small
- class 3: up-large
- 多クラスHGBの `P(up-small) + P(up-large)` をraw方向確率へ戻す。
- calibration/testの実体値や大小ラベルは閾値決定・入力に使わず、後続calibration期間の方向labelだけでPlatt校正する。
- baselineと同じ加工特徴、HGB parameter、expanding training、M15 2020〜2026途中の7fold。
- 単体、通常25% blend、baseline方向を維持する25% confidence blendを比較する。
- confidence閾値は2020〜2023 developmentの固定gridだけで選び、2024〜2026途中へ固定する。

4クラス符号・中央値境界、up確率集約、artifact保存、最新推論を単体テストした。

## 単体と通常blend

| period | model | accuracy | Brier | log loss | ECE |
|---|---|---:|---:|---:|---:|
| development | baseline | 52.014% | 0.2493466 | 0.6918398 | 0.377% |
| development | multiclass single | 51.982% | 0.2494336 | 0.6920125 | 0.382% |
| confirmation | baseline | 51.501% | 0.2495525 | 0.6922506 | 0.298% |
| confirmation | multiclass single | 51.494% | 0.2495765 | 0.6922988 | 0.097% |
| all | baseline | 51.816% | 0.2494261 | 0.6919985 | 0.347% |
| all | multiclass single | 51.793% | 0.2494888 | 0.6921230 | 0.271% |

単体は方向精度、Brier、log lossが悪化したため方向モデルとして棄却する。

通常25% blendはconfirmationを51.501%から51.517%へ僅かに上げたが、developmentと全体は悪化した。誤り修正2,664件、新規誤り2,688件、McNemar exact p=0.753で方向edgeではない。

## 方向維持型confidence blend

| period | metric | baseline | multiclass confidence |
|---|---|---:|---:|
| development | Brier | 0.2493466 | 0.2493118 |
| development | log loss | 0.6918398 | 0.6917687 |
| development | ECE | 0.377% | 0.301% |
| confirmation | Brier | 0.2495525 | 0.2495375 |
| confirmation | log loss | 0.6922506 | 0.6922207 |
| confirmation | ECE | 0.298% | 0.209% |
| all | Brier | 0.2494261 | 0.2493990 |
| all | log loss | 0.6919985 | 0.6919433 |
| all | ECE | 0.347% | 0.265% |

Brier、log loss、ECEはいずれも5/7 foldで改善した。

## developmentで選んだconfidence 0.525 lane

| period | model | rows | coverage | accuracy | selection score |
|---|---|---:|---:|---:|---:|
| development | baseline | 33,770 | 37.908% | 53.858% | 0.02048 |
| development | multiclass | 32,773 | 36.789% | 54.087% | 0.02152 |
| confirmation | baseline | 14,785 | 26.375% | 53.777% | 0.01527 |
| confirmation | multiclass | 13,536 | 24.147% | 54.115% | 0.01609 |
| all | baseline | 48,555 | 33.454% | 53.834% | 0.01961 |
| all | multiclass | 46,309 | 31.906% | 54.095% | 0.02057 |

accuracyとselection scoreは7/7 foldすべてでbaselineを改善した。

## clear-body 0.525との直接比較

| period | model | coverage | accuracy | selection score |
|---|---|---:|---:|---:|
| development | clear-body | 35.639% | 54.173% | 0.02164 |
| development | multiclass | 36.789% | 54.087% | 0.02152 |
| confirmation | clear-body | 24.714% | 54.201% | 0.01675 |
| confirmation | multiclass | 24.147% | 54.115% | 0.01609 |
| all | clear-body | 31.419% | 54.182% | 0.02088 |
| all | multiclass | 31.906% | 54.095% | 0.02057 |

全3期間でclear-bodyのaccuracyとselection scoreが高い。年別直接比較でもmulticlassのaccuracy改善は1/7、score改善は3/7、Brier/log loss改善は各3/7だった。ECEだけは5/7改善した。

## 最新推論確認

全期間60%/20%/20%で実データartifactを別学習し、データ末尾まで `predict-latest` を実行した。2026-06-01 04:45 UTC判定はup、model confidence 0.56657だった。これは保存・推論経路の確認値で、empirical oddsとしては無効である。

## 判断

- 4クラス単体と通常方向blendは棄却する。
- 方向維持型0.525はbaselineに対しaccuracy・selection scoreを7/7 foldで改善したため `config/m15_body_multiclass_confidence_shadow_v1.json` に固定する。
- 同じ実体情報を使うclear-body 0.525がdevelopment、confirmation、全体、直接fold安定性、Brier/log lossで上回るためforward candidateへは昇格しない。
- 完全未使用期間では教師表現の独立shadowとして監視し、同じ履歴でclass境界、class数、HGB parameter、blend weight、閾値を再探索しない。
- authoritative confidence、fair odds、現行採用policy、paper policyは変更しない。損失倍率は標準1.0のみとする。
