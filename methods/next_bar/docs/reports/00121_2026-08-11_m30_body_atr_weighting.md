# 00121 M30 Body/ATR Sample Weighting

日時: 2026-08-11 17:05 JST

## 目的

M15でconfidence候補、M1でbaseline方向改善を示した教師品質加工をM30へ固定移植した。次足の値幅が大きい教師を重くする学習フローが、M30の方向または信頼度へ独立した増分を持つか検証した。

## 固定仕様と品質

trainで解決済みの次足について `strength = abs(next close - next open) / (decision close * atr_ratio_20)` とし、raw weightを `0.5 + clip(strength, 0, 1.5)` とした。重み範囲0.5〜2.0、最大比4倍で、sampled train内の平均1へ正規化する。次足bodyはtrain sample weightだけへ使い、特徴、calibration、test入力、latest推論へ渡さない。ATRは判定時までの完成足だけから作る。

baseline 38加工特徴、HGB 200 iteration、31 leaves、learning rate 0.05、min leaf 100、L2 1、seed 42、expanding、最大train 750,000行、全教師、Platt、25% blend、標準損失1.0を固定した。M1からweight式、model parameter、confidence grid `0.51,0.515,0.525,0.535,0.55` を変更していない。

test2020〜test2026途中の7fold、71,260 OOS行をbaseline・既存候補とtimestamp/targetで完全整列した。最終fold artifactから2026-06-01 04:30 UTCを再推論し、up、probability up 53.3266%を確認した。経験的オッズ検証はないため `odds_valid=false` である。

## 単体と通常方向blend

| model | development accuracy | confirmation accuracy | all accuracy | all Brier | all log loss | all ECE |
|---|---:|---:|---:|---:|---:|---:|
| HGB baseline | 51.9897% | 51.5202% | 51.8075% | 0.249497879 | 0.692142533 | 0.1608% |
| Body/ATR weighted単体 | 51.6870% | 51.4732% | 51.6040% | 0.249584911 | 0.692316689 | 0.3234% |
| baseline 75% + Body/ATR 25% | 51.9094% | 51.5491% | 51.7696% | 0.249475319 | 0.692097000 | 0.1290% |

単体はbaseline比development -132件、confirmation -13件、all -145件だった。accuracy/Brier/log lossは各2/7fold、McNemar exact p=0.2016であり、方向にも確率品質にも使わない。

通常25% blendは-35/+8/-27件、accuracy 3/7foldだった。Brier/log lossは4/7foldで、日次bootstrap 20,000回のall accuracy差-0.0379ptの95%区間は-0.1904〜+0.1160pt、Brier/log loss差も0を跨いだ。confirmationの小さな点改善を方向edgeと解釈しない。

同じ教師品質加工のDirectional-Clarity通常25% blendと直接比較すると、Body/ATRはdevelopment -62件、confirmation +3件、all -59件、年別accuracy 3/7対4/7だった。all accuracy差区間は-0.2287〜+0.0597ptで0を跨いだ一方、Body/ATR minus ClarityのBrier差区間は+0.000000823〜+0.000054686、log loss差は+0.000001269〜+0.000109670で、Clarityのproper score優位を支持した。絶対的な次足振幅より、range内の相対的な方向明瞭度の方がM30教師重みとして有効である。

## confidence

development gridの候補selection score最大は0.515だったが、同じ閾値のbaselineを既に下回った。

| period | baseline coverage / accuracy / score | Body/ATR coverage / accuracy / score |
|---|---:|---:|
| development | 52.9829% / 53.1126% / 0.017968 | 51.6273% / 53.1432% / 0.017897 |
| confirmation | 43.3028% / 53.2977% / 0.015815 | 42.5400% / 53.0127% / 0.013762 |
| all | 49.2254% / 53.1758% / 0.018616 | 48.0999% / 53.0984% / 0.017822 |

confirmationでaccuracy -0.2850pt、coverage -0.7628pt、score -0.002053へ反転した。日次bootstrapではcoverage低下を全期間区分で支持し、accuracy・score・Brier・log loss差は0を跨いだ。0.515をconfidence候補へ固定しない。

Pressure 0.52との比較ではBody/ATR 0.515がall coverage 48.0999%対36.4861%と広い一方、accuracy 53.0984%対53.7577%、score 0.017822対0.019034で、accuracy 0/7、score 1/7だった。Body/ATR 0.55もall 4,289件、coverage 6.0188%、accuracy 55.8405%、score 0.010671で、Pressure + AR 0.55の4,412件、6.1914%、56.1423%、0.011629を下回り、accuracy/score各3/7だった。

PressureとBody/ATR confidenceの固定50/50平均は0.52でPressureにaccuracy 2/7、score 3/7だった。0.55はall accuracy 56.1667%でもcoverage 5.8939%、score 0.011316でPressure + ARの56.1423%、6.1914%、0.011629を置換せず、confirmationはaccuracy 54.9296%対56.0088%、score 0.002762対0.004997へ悪化した。年別accuracy/score各3/7であり、相補性も採用しない。

## 判断

Body/ATR weighted単体、通常25%方向blend、方向維持0.515/0.55、Pressureとの固定50/50 confidence平均を再現専用とする。次足の絶対振幅を強調する教師重みはM30で方向を悪化させ、相対形状を使うDirectional-Clarityにもproper scoreで劣った。

weight式、feature、model parameter、blend weight、thresholdを同じ履歴へ合わせて再探索しない。M15の0.54候補は時間足独立で維持する。M30 config、registry、authoritative方向/confidence、現行Haar入り方向co-challenger、Pressure 0.52、Pressure + AR 0.55 shadow、fair odds、adoption/paper/live policyは変更しない。

## 成果物

- Body/ATR OOS: `experiments/next_bar/walk_forward_body_atr_weighted_m30_fixed_001`
- normal/confidence blends: `experiments/next_bar/body_atr_weighted_m30_*_fixed_001`
- candidate分析: `experiments/next_bar/body_atr_weighted_m30_candidate_analysis.json`
- baseline/既存候補比較: `experiments/next_bar/body_atr_weighted_vs_*_m30_*`
- rejected confidence average: `experiments/next_bar/pressure_body_atr_equal_m30_confidence_fixed_001`
- confidence average comparisons: `experiments/next_bar/pressure_body_atr_equal_vs_*`
- latest artifact check: `experiments/next_bar/body_atr_weighted_m30_latest_prediction.json`
