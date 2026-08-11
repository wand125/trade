# 00122 M30 Directional Follow-through Sample Weighting

日時: 2026-08-11 16:45 JST

## 目的

M30では次足の絶対振幅を使うBody/ATRより、実体/rangeを使うDirectional-Clarity教師重みの方が有効だった。相対形状をさらに分解し、実体が大きいだけでなく終値が方向側の高安へ到達した教師を重くすると、方向または高信頼度選別へ独立した増分が生じるか検証した。

## 固定仕様と品質

trainで解決済みの次足について、`clarity = abs(close - open) / (high - low)`、方向側close到達度をupなら `(close - low) / range`、downなら `(high - close) / range` とした。`follow_through = clarity * direction_aligned_close_location` を0〜1へ制限し、raw weightを `0.5 + follow_through`、範囲0.5〜1.5、最大比3倍とし、sampled train内の平均1へ正規化する。

次足OHLCはtrain sample weightだけへ使い、入力特徴、calibration、test、latest推論へ渡さない。全方向教師を残す。baseline加工38特徴、HGB 200 iteration、31 leaves、learning rate 0.05、min leaf 100、L2 1、seed 42、expanding、最大train 750,000行、Platt、標準損失1.0を固定した。weight offset、積の形、model parameter、25%/50% blend、0.55を結果に合わせて探索していない。

test2020〜test2026途中の7fold、71,260 OOS行をbaseline・既存候補とtimestamp/targetで完全整列した。境界、平均1、特徴manifest非混入、artifact/latestをテストした。最終fold artifactの2026-06-01 04:30 UTCはup、probability up 53.2038%だった。経験的オッズ検証はないため `odds_valid=false` である。

## 単体と通常方向blend

| model | development accuracy | confirmation accuracy | all accuracy | all Brier | all log loss | all ECE |
|---|---:|---:|---:|---:|---:|---:|
| HGB baseline | 51.9897% | 51.5202% | 51.8075% | 0.249497879 | 0.692142533 | 0.1608% |
| Follow-through weighted単体 | 52.0402% | 51.8456% | 51.9646% | 0.249357022 | 0.691857821 | 0.2561% |
| baseline 75% + Follow-through 25% | 51.9828% | 51.5130% | 51.8004% | 0.249432972 | 0.692011857 | 0.1950% |

単体はbaseline比development +22件、confirmation +90件、all +112件、accuracy 4/7foldだった。日次bootstrap 20,000回のall accuracy差+0.1572ptの95%区間は-0.1075〜+0.4212ptで未確定だった。一方、all Brier差区間-0.00023050〜-0.00005072、log loss差-0.00046480〜-0.00010375は改善を支持した。ECEは悪化したため単体確率をfair oddsへ使わない。

通常25% blendは-3/-2/-5件、accuracy 2/7foldで方向用途へ使わない。Brier 6/7、log loss 7/7foldの改善は確率平滑化であり、正答数を増やす方向edgeではない。

単体を同じ教師重みのDirectional-Clarityと比べるとdevelopment -44件、confirmation +13件、all -31件、年別3勝3敗1分だった。Extra Treesには-16/+56/+40件でも年別3/7、現行Haar入り方向候補には-67/+47/-20件で3/7だった。全直接bootstrapでaccuracy差区間は0を跨いだため、新しい方向candidateを発行しない。

## Haar方向候補との固定平均

現行Haar入り方向co-challengerとFollow-through単体を固定50/50平均した。

| period | Haar親 accuracy | 固定平均 accuracy | 固定平均 Brier / log loss / ECE |
|---|---:|---:|---:|
| development | 52.1939% | 52.2007% | 0.249281263 / 0.691706904 / 0.0444% |
| confirmation | 51.6756% | 51.6648% | 0.249479301 / 0.692103786 / 0.0574% |
| all | 51.9927% | 51.9927% | 0.249358135 / 0.691860962 / 0.0483% |

親比の正答数は+3/-3/0件、accuracy 4/7foldで、方向増分はない。一方、Brier/log lossの日次区間はdevelopment、confirmation、allの全区分で改善を支持した。方向候補として親を置換せず、この固定平均を高信頼度選別だけで評価した。

## 高信頼度0.55

単純な方向維持25% confidenceはdevelopment選択0.515でbaselineを下回ったため、broad confidenceへ採用しない。固定50/50平均の事前固定0.55を、既存Pressure + AR 0.55 shadowと比較した。

| period | Follow-through平均 coverage / accuracy / score | Pressure + AR coverage / accuracy / score |
|---|---:|---:|
| development | 9.4268% / 56.8370% / 0.016325 | 8.0392% / 56.1769% / 0.012839 |
| confirmation | 3.4164% / 55.8730% / 0.004971 | 3.2790% / 56.0088% / 0.004997 |
| all | 7.0937% / 56.6568% / 0.014079 | 6.1914% / 56.1423% / 0.011629 |

Follow-through平均はaccuracy 4/7、selection score 6/7foldだった。Pressure + AR比の日次bootstrapではdevelopment score差区間+0.000430〜+0.006584、all +0.000125〜+0.004844、all coverage差+0.7648〜+1.0397pt、Brier/log lossも改善側だった。confirmation score差-0.000026の区間は-0.003695〜+0.003610で同等域に留まり、置換はしない。

親Haar候補0.55に対してもall coverage 6.2489%→7.0937%、accuracy 56.3216%→56.6568%、score 0.012149→0.014079だった。confirmationはaccuracy 56.4067%→55.8730%と下げたがcoverage 2.5957%→3.4164%、score 0.004439→0.004971で、年別accuracy/score各4/7だった。親比bootstrapではcoverageと全期間区分のBrier/log loss改善を支持したがscore区間は0を跨いだ。

0.55のall accuracy 56.6568%とmean confidence 56.6480%の差は+0.0087pt、ECE 0.0203%で局所整合し、confirmationも55.8730%対56.0901%でWilson区間内だった。ただしconfirmationのup-low 64件は46.875%、up-normal 176件は52.841%と疎く不安定である。同じ履歴から除外guardを作らず、fair oddsを認可しない。

## 判断

Follow-through weighted単体と通常25% blendは再現専用とし、新しいM30方向候補へ追加しない。Haar親との固定50/50平均も方向用途では親を置換しない。

固定平均0.55だけを `m30_haar_directional_follow_through_confidence_shadow_v1.json` のparallel forward confidence shadowとして採用する。全期間のcoverage-aware score、proper score、校正と6/7foldを評価する一方、confirmation scoreはPressure + ARと同等、局所セルは疎く、nested runtime parityも未発行である。authoritative confidence、Pressure + AR shadow、fair odds、adoption/paper/live policyは変更しない。

weight式、model parameter、blend weight、threshold、subgroupを同じ履歴へ合わせて再探索しない。完全未使用期間でPressure + AR以上のaccuracy・coverage・selection score、confirmation score、固定方向×volatilityセル整合、full runtime parityを要求する。

## 成果物

- implementation: `src/trade_data/next_bar.py`
- tests: `tests/test_next_bar.py`
- Follow-through OOS/latest: `experiments/next_bar/walk_forward_directional_follow_through_weighted_m30_fixed_001`, `experiments/next_bar/directional_follow_through_weighted_m30_latest_prediction.json`
- normal/confidence blends and analysis: `experiments/next_bar/directional_follow_through_weighted_m30_*`
- standalone comparisons/bootstrap: `experiments/next_bar/directional_follow_through_single_vs_*`
- fixed Haar average: `experiments/next_bar/haar_directional_follow_through_equal_m30_direction_fixed_001`
- parent/Pressure + AR comparisons/bootstrap: `experiments/next_bar/haar_directional_follow_through_equal_vs_*`
- reliability/subgroups: `experiments/next_bar/haar_directional_follow_through_*analysis.json`
- adopted shadow config: `methods/next_bar/config/m30_haar_directional_follow_through_confidence_shadow_v1.json`
