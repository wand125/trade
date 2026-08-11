# 00128 M1 State Correctness Precision Lane

日時: 2026-08-11 21:16 JST

## 目的

既存confidence候補の集合再結合ではなく、加工済み市場状態から「baselineの次足方向予測が正しい確率」を独立に学習した。主目的のaccuracy×coverage、固定高信頼度tail、方向×volatilityの局所安定性、確率校正を時系列OOSで評価し、使える部分だけを採用する。

## 固定仕様と因果性

入力は価格水準を含まないbaseline 38特徴とDistribution Shift 16特徴、baselineのconfidence・方向整列edge・predicted-up flagの計57列である。HGBは100 iteration、learning rate 0.05、15 leaves、min leaf 50、L2 2、最大750,000行、seed 42。各test foldでは過去OOSだけを時系列順に使い、古い80%でcorrect/incorrectを学習、直近20%でPlatt校正した。最初のtest2020は過去OOSがないためfallbackとし、全評価から除外した。

未来bar改変と未来label改変の非影響、方向維持、有限・stationary特徴、重複列のraw再計算優先をテストした。損失倍率は標準1.0のみである。

## 主目的の結果

固定grid `0.50, 0.505, 0.51, 0.515, 0.52, 0.525, 0.53, 0.54, 0.55, 0.575, 0.60` のdevelopment目的関数最大は0.505だった。

| period | candidate coverage / accuracy / score | baseline同閾値 coverage / accuracy / score |
|---|---:|---:|
| development | 63.5201% / 51.0141% / 0.007100 | 63.3584% / 51.0031% / 0.007002 |
| confirmation | 51.1725% / 51.0194% / 0.006226 | 53.4022% / 51.1237% / 0.007145 |
| all nested | 57.8507% / 51.0163% / 0.007007 | 58.7870% / 51.0534% / 0.007354 |

Distribution Shift 0.51との直接比較ではcandidateはconfirmation accuracyで-0.8791pt、scoreで-0.001916、all accuracyで-0.5881pt、scoreで-0.001086だった。20,000回の日次bootstrapもconfirmation/allのaccuracyとscore悪化を支持した。したがって主候補0.505は棄却し、broad confidence、方向、fair odds、policyへ採用しない。

## 固定0.55と採用条件

0.55は事前gridに含めた高信頼度感度である。guard前はdevelopment 2,736件・53.582%、confirmation 2,495件・57.515%だったが、固定6セルではdevelopmentのWilson下限が50%を超え、mean confidenceがWilson区間内だったのは `up × high` と `up × normal` だけだった。down全セルとup × lowをabstentionにする条件をdevelopmentだけから固定し、その後confirmationへ適用した。

| period | rows | 全体coverage | accuracy | Wilson下限 | score | mean confidence |
|---|---:|---:|---:|---:|---:|---:|
| development | 1,552 | 0.1561% | 56.1856% | 53.7048% | 0.001464 | 55.8462% |
| confirmation | 2,063 | 0.2444% | 58.1677% | 56.0258% | 0.002979 | 56.2338% |
| all nested | 3,615 | 0.1966% | 57.3167% | 55.6974% | 0.002526 | 56.0674% |

confirmation各foldはtest2024 176件・58.5227%、test2025 886件・58.8036%、test2026途中 1,001件・57.5425%で、方向性は3/3fold再現した。test2024を含む各年のsupportはまだ疎い。

## 既存候補との役割比較

| all nested | rows | coverage | accuracy | Wilson下限 | score |
|---|---:|---:|---:|---:|---:|
| State correctness up/non-low 0.55 | 3,615 | 0.1966% | 57.3167% | 55.6974% | 0.002526 |
| Transition guard 0.55 | 2,039 | 0.1109% | 54.1442% | 51.9756% | 0.000658 |
| Disagreement 0.55 | 3,528 | 0.1919% | 53.8832% | 52.2350% | 0.000979 |
| Distribution Shift 0.51 | 555,122 | 30.1911% | 51.6043% | 51.4729% | 0.008093 |

20,000回のpaired UTC-day bootstrapではState−Transitionのall accuracy差95%区間が+0.7026〜+5.6388pt、score差が+0.000955〜+0.002778、State−Disagreementは+1.3603〜+5.5120pt、+0.000653〜+0.002449で、ともに改善を支持した。Distribution Shiftに対してaccuracy差は+4.0851〜+7.4038ptだが、coverageが約30pt小さいためscore差は-0.006577〜-0.004567である。したがって置換ではなく、既存broad laneと役割の異なるprecision laneとする。

## 信頼度品質

実績−mean confidenceはdevelopment +0.3394pt、confirmation +1.9339pt、all +1.2494ptで、3期間ともmean confidenceはWilson区間内、Wilson edgeも確認できた。confirmationではやや過小評価だが、fair oddsとして有利な方向のずれである。

一方、全行のBrier/log lossはTransition guard・Disagreementより僅かに悪く、bootstrap区間は改善を支持しなかった。このモデルは高精度行のrankerとしては有望だが、全分布のauthoritative probability置換ではない。`1 / confidence` はshadow表示だけ許可し、`odds_valid=false` を維持する。

## Runtime

保存済み最新chronological correctness modelとbaseline最新artifactを結ぶ `predict_latest_state_correctness.py` を追加した。Distribution Shiftの最大rolling窓128本に対して末尾4,096 M1本を使い、全履歴と最新特徴が浮動小数点許容差内で一致することをテストした。実データlatestは2026-06-01 04:59 UTC判定、baseline down、state confidence 50.7340%のため固定0.55未満で不採用を返した。方向は変えず、fair oddsは非認可である。

## 判断

主目的で選んだ0.505は棄却する。固定0.55かつbaseline up、volatility normal/highの条件だけを、M1 sparse precision forward shadowとして採用する。authoritative方向/confidence/fair odds、paper/live policy、既存Transition guard・Disagreement・Distribution Shiftは変更しない。

このセル条件は6セルからdevelopmentで選んだため、多重比較とselection biasが残る。完全未使用期間で1,000件以上、Wilson下限50%超、既存precision候補以上のaccuracy/score、global・固定セル校正、proper score非劣位を再確認するまで昇格しない。同じ履歴でthreshold、方向、volatility境界、HGB parameter、校正方式を再探索しない。

## 成果物

- 実装: `src/trade_data/next_bar_state_correctness.py`
- 学習/runtime CLI: `methods/next_bar/scripts/state_correctness.py`, `methods/next_bar/scripts/predict_latest_state_correctness.py`
- OOS: `experiments/next_bar/state_correctness_m1_fixed_001`
- 固定guard: `experiments/next_bar/state_correctness_up_nonlow_m1_fixed_001`
- 既存候補比較・bootstrap: `experiments/next_bar/state_correctness_up_nonlow_055_vs_*`
- latest: `experiments/next_bar/state_correctness_m1_latest_prediction.json`
- shadow config: `methods/next_bar/config/m1_state_correctness_up_nonlow_high_confidence_shadow_v1.json`
