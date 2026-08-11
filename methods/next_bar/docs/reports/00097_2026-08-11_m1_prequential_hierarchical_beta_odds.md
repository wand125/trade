# 00097 M1 Prequential Hierarchical Beta Odds

日時: 2026-08-11 08:22 JST

## 目的

現M1 confidence accuracy championの方向を変えず、confidenceを「予測方向が正しい確率」に近づける。prior-fold expanding isotonic/Plattは年次shiftを追えず既に棄却済みなので再探索しない。今回は各予測のtargetが確定した時点だけで逐次更新する、固定90日ローリング階層Beta-Binomialを一度だけ検証した。

## 固定仕様と因果性

各decisionで利用できるのは `target_timestamp <= decision_timestamp` を満たす過去の正誤だけで、現在行と未来行のcorrectは見ない。直近90 UTC日の履歴を次の順で縮約した。

1. global正答率を現在のraw confidenceへprior strength 8,192で縮約する。
2. 固定raw confidence bandをglobal posteriorへ4,096で縮約する。
3. band × predicted direction × volatility regimeセルをband posteriorへ2,048で縮約する。

band境界は `0.50, 0.51, 0.515, 0.525, 0.535, 0.55, 0.575, 0.60, 1.00`。posterior平均をadaptive confidence、posterior標準誤差の1.96倍を引いた値を保守下限とした。方向、正誤、raw probability、0.515閾値は変更しない。window、prior、band、階層、閾値を結果に合わせて動かさない。

小型データで、直前targetが解決するまで更新されないこと、未来correct改変が過去confidenceへ影響しないこと、予測方向不変、確率有限範囲、invalid timestamp拒否をテストした。現champion 2,183,717行へ適用し、重複0、欠損0を確認した。

## 全行の確率品質

| period | method | mean confidence | Brier | log loss | ECE |
|---|---|---:|---:|---:|---:|
| development | raw | 50.98795% | 0.24981532 | 0.69277751 | 0.05063% |
| development | adaptive | 50.83255% | 0.24984495 | 0.69283688 | 0.10483% |
| confirmation | raw | 50.60503% | 0.24989099 | 0.69292906 | 0.00502% |
| confirmation | adaptive | 50.55118% | 0.24990420 | 0.69295550 | 0.13328% |
| all | raw | 50.83991% | 0.24984457 | 0.69283610 | 0.03300% |
| all | adaptive | 50.72377% | 0.24986786 | 0.69288274 | 0.10730% |

adaptiveはBrier/log loss/ECEをdevelopment、confirmation、allの点推定で全て悪化させた。foldではBrier/log loss改善1/7、ECE改善1/7だけだった。UTC日paired bootstrap 20,000回でもallのadaptive−raw Brier差95%区間は+0.00001257〜+0.00003392、log lossは+0.00002517〜+0.00006794で、悪化が確定した。developmentも両proper scoreの悪化区間が確定した。

## 固定0.515 lane

| period | raw accuracy / coverage / score | adaptive accuracy / coverage / score |
|---|---:|---:|
| development | 52.4249% / 21.6867% / 0.010447 | 52.3269% / 21.4204% / 0.009924 |
| confirmation | 53.3560% / 7.0236% / 0.007829 | 52.5278% / 12.0520% / 0.007710 |
| all | 52.5827% / 16.0178% / 0.009674 | 52.3795% / 17.7985% / 0.009376 |

adaptiveはconfirmation coverageを+5.0284pt広げたがaccuracyを-0.8282pt下げた。日次95%区間は-1.1189〜-0.5385ptで精度悪化が確定した。allもcoverage +1.7807ptに対してaccuracy -0.2032pt、95%区間-0.3398〜-0.0675ptで悪化した。selection scoreは3/7foldだけrawを上回り、all差区間は0を跨ぐものの点値は-0.000298だった。accuracy勝ちはtest2020だけの1/7foldである。

posterior保守下限を自然なedge境界0.5で選ぶ感度でも、all accuracy 51.7325%、coverage 27.2918%、score 0.008388でraw 0.515を下回った。保守下限0.515はaccuracy 53.4855%でもcoverage 3.8173%、score 0.006148で、精度と引き換えに目的関数を大きく失った。下限を新しい採用ruleにしない。

## 高信頼度と局所品質

all 0.55以上はraw 8,422件・accuracy 56.1506%・coverage 0.3857%・score 0.003160に対し、adaptive 4,767件・56.3038%・0.2183%・0.002285だった。+0.1532ptの点精度と引き換えにcoverageを43%失い、coverage-aware objectiveを下げた。confirmationではrawも39件でedge未確認、adaptiveは0件だった。

adaptive confirmation 0.515の6セルではdown-high、up-high、up-normalだけがWilson edgeを通った。down-low 854件・48.244%、down-normal 3,318件・49.397%、up-low 104件・51.923%はedge未確認で、元championの局所弱点を解消していない。raw confidenceが0.5近辺でも過去セル平均によって0.515を超える行が増え、coverage拡大と精度低下が同時に起きた。

adaptive confidenceが0.5未満になった468,223行も、元方向accuracyはdevelopment 50.275%、confirmation 49.929%、all 50.095%で時期によって符号が反転した。これを方向反転ruleへ流用しない。

## 判断

prequential hierarchical Beta oddsを再現専用として棄却する。短期feedbackを使っても、階層セルの過去正答率は次の期間の正答確率として安定せず、全行proper score、0.515 accuracy、selection scoreを同時最大化できなかった。確認0.515の局所校正gapは縮小したが、精度低下と弱いセルの残存を伴うため、ECEだけを理由に採用しない。

現Transition guard × Disagreement 50/50 championのraw confidenceを維持する。90日window、8,192/4,096/2,048 prior、band、階層、下限、別閾値を同じ履歴で再探索しない。config、registry、authoritative confidence、fair odds、paper/live policyを変更しない。fair oddsは引き続きfresh期間のglobal/local整合を要求する。

## 成果物

- predictions/report: `experiments/next_bar/transition_guard_champion_m1_prequential_beta_001`
- fixed subgroup audit: `experiments/next_bar/transition_guard_champion_m1_prequential_beta_subgroups.json`
- raw reliability comparison: `experiments/next_bar/transition_guard_champion_raw_vs_prequential_beta_reliability.json`
- implementation: `src/trade_data/next_bar_odds_recalibration.py`
- CLI: `methods/next_bar/scripts/prequential_hierarchical_beta_odds.py`
- tests: `tests/test_next_bar_odds_recalibration.py`
