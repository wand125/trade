# 00028 Trend/structure indicators

日時: 2026-08-08 09:07 JST

## 目的

raw OHLCや価格水準をそのまま渡さず、トレンドの強さ・方向、momentum、volatility compression、方向の乱雑さを使いやすい定常指標へ加工し、M15の次足方向とconfidence選別が改善するか確認する。

## 結果前に固定した方法

- feature set: `--feature-set trend_structure`
- model: baselineと同じHGB、Platt calibration、expanding training。
- baseline加工特徴へ次の11列を追加した。
  - `plus_di_14`, `minus_di_14`, `adx_14`, `di_balance_14`, `adx_change_3`
  - `macd_atr_20`, `macd_signal_gap_atr_20`
  - `atr_compression_5_20`, `volatility_ratio_5_20`, `realized_volatility_balance_20`
  - `direction_entropy_20`
- DI/ADXはWilder型EWM、MACDはATR正規化、volatility系は短期/長期比、entropyは直近方向比率から計算する。raw価格水準は含めない。
- M15 2020〜2026途中の同一7fold。baseline 75% + candidate 25%の通常blendと、baseline方向を維持するconfidence blendを比較した。
- confidence閾値はdevelopment 2020〜2023の固定gridだけで選び、confirmation 2024〜2026途中へ固定した。

未来側のOHLCを改変しても過去特徴が変化しないこと、raw OHLCがmanifestへ入らないこと、artifactから最新足を予測できることをテストした。

## 単体と通常blend

| period | model | accuracy | Brier | log loss | ECE |
|---|---|---:|---:|---:|---:|
| all | baseline | 51.816% | 0.2494261 | 0.6919985 | 0.347% |
| all | trend single | 51.759% | 0.2494630 | 0.6920724 | 0.389% |
| confirmation | baseline | 51.501% | 0.2495525 | 0.6922506 | 0.298% |
| confirmation | trend single | 51.328% | 0.2495984 | 0.6923426 | 0.466% |

単体は全主要指標が悪化したため方向モデルとして棄却する。通常25% blendも全体accuracy 51.784%、confirmation 51.480%へ低下した。baselineの誤りを1,885件修正した一方で1,932件を新規に誤り、McNemar exact p=0.457のため方向edgeとは判断しない。

## 方向維持型confidence blend

| period | metric | baseline | candidate |
|---|---|---:|---:|
| development | Brier | 0.2493466 | 0.2493246 |
| development | log loss | 0.6918398 | 0.6917954 |
| development | ECE | 0.377% | 0.336% |
| confirmation | Brier | 0.2495525 | 0.2495528 |
| confirmation | log loss | 0.6922506 | 0.6922514 |
| confirmation | ECE | 0.298% | 0.276% |
| all | Brier | 0.2494261 | 0.2494128 |
| all | log loss | 0.6919985 | 0.6919715 |
| all | ECE | 0.347% | 0.313% |

developmentでは3指標とも改善したが、confirmationのBrier/log lossはごく僅かに悪化した。fold改善数はBrier 5/7、log loss 5/7、ECE 4/7である。

## developmentで選んだconfidence 0.525 lane

| period | model | rows | coverage | accuracy | selection score |
|---|---|---:|---:|---:|---:|
| development | baseline | 33,770 | 37.908% | 53.858% | 0.02048 |
| development | trend blend | 33,094 | 37.150% | 53.980% | 0.02098 |
| confirmation | baseline | 14,785 | 26.375% | 53.777% | 0.01527 |
| confirmation | trend blend | 14,528 | 25.916% | 53.951% | 0.01598 |
| all | baseline | 48,555 | 33.454% | 53.834% | 0.01961 |
| all | trend blend | 47,622 | 32.811% | 53.971% | 0.02018 |

固定閾値の改善はconfirmationにも再現した。年別ではaccuracyとselection scoreがともに5/7 fold改善し、2025と2026途中は悪化した。全期間のconfidence 0.55以上は11,268件、coverage 7.764%、accuracy 55.857%。0.60以上は385件、coverage 0.265%、accuracy 58.442%で、少数帯なので採用判断には使わない。

## clear-body 0.525との比較

| period | candidate | coverage | accuracy | selection score |
|---|---|---:|---:|---:|
| development | clear-body filter | 35.639% | 54.173% | 0.02164 |
| development | trend blend | 37.150% | 53.980% | 0.02098 |
| confirmation | clear-body filter | 24.714% | 54.201% | 0.01675 |
| confirmation | trend blend | 25.916% | 53.951% | 0.01598 |
| all | clear-body filter | 31.419% | 54.182% | 0.02088 |
| all | trend blend | 32.811% | 53.971% | 0.02018 |

trend blendはcoverageを約1.2〜1.5pt広く取れる一方、accuracyと今回の目的関数はdevelopment、confirmation、全体のすべてでclear-bodyを下回る。さらにconfirmation proper scoreが完全には再現しない。

## 最新推論確認

全期間の60%/20%/20%分割でM15 artifactを別途作成し、データ末尾の完成足に対して `predict-latest` を実行した。2026-06-01 04:45 UTC判定はup、model confidence 0.55835となり、11追加特徴を含む保存artifactから最新推論まで通ることを確認した。この値は機能確認用で、walk-forward採用結果や有効なempirical oddsではない。

## 判断

- `trend_structure` 単体と通常方向blendは棄却する。
- 方向維持型0.525はcoverage-aware scoreをdevelopment/confirmationの両方で改善し、加工指標がconfidence選別に使える証拠は得られた。
- ただし既存clear-body 0.525より目的関数と正答率が低く、confirmationのBrier/log lossも改善しないためforward configは発行しない。
- 実装は将来の直交性検証・特徴選択実験の再現用に残す。今回の同じ履歴で期間や指標パラメータを再調整しない。
- authoritative confidence、odds、現行policy、paper policyは変更しない。損失倍率は標準1.0のみとする。
