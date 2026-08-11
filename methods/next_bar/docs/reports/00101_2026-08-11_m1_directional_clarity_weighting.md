# 00101 M1 Directional-Clarity Sample Weighting

日時: 2026-08-11 10:20 JST

## 目的

時間減衰ではなく教師側の品質を加工する固定学習フローをM1へ移植した。M15で実装・棄却済みのDirectional-Clarity sample weightingを結果に合わせて変更せず、M1では曖昧な次足を捨てずに明瞭な過去教師の損失寄与を増やすと、方向accuracyまたはconfidence rankingが改善するか検証した。

## 固定仕様と品質

trainで解決済みの次足について `directional_clarity = abs(next close - next open) / (next high - next low)` を0〜1へ制限し、raw weightを `0.5 + directional_clarity` とする。重み範囲0.5〜1.5、最大比3倍で、sampled train内の平均1へ正規化する。全train行と方向0/1教師を維持する。

次足rangeとbodyはtrain sample weightだけに使い、特徴manifest、calibration、test入力、latest推論へ渡さない。各foldのtrainより後のlabelは参照しない。重み範囲・平均1・欠損guard・small pipeline・artifact latest経路は既存テストで確認済みである。

M15固定仕様からweight offset、非線形化、上限、HGB parameter、blend weight、confidence gridを変更していない。baseline 38特徴、HGB 200 iteration、31 leaves、learning rate 0.05、min leaf 100、L2 1、expanding train最大750,000行、Platt、seed 42、baseline 75% + candidate 25%とした。損失倍率は標準1.0のみである。

source 6,025,170行、usable 5,737,928行から、baselineとtimestamp、decision/target timestamp、target、foldが一致する2,183,717 OOS行を生成した。

## 単体と通常方向blend

| period | baseline | Clarity単体 | 通常25% blend |
|---|---:|---:|---:|
| development | 50.93738% | 50.96545% | 50.98188% |
| confirmation | 50.60001% | 50.66101% | 50.63223% |
| all | 50.80695% | 50.84775% | 50.84670% |

単体はbaseline比development +376件、confirmation +515件、all +891件だった。全期間exact paired p=0.05093で境界的だが、accuracy 5/7、Brier/log loss 7/7foldを改善した。

通常25% blendはdevelopment +596件、confirmation +272件、all +868件で、accuracy、Brier、log lossを全て7/7fold改善した。exact paired pはdevelopment 0.00131、confirmation 0.05998、all 0.000219である。UTC日paired bootstrap 20,000回もdevelopment/allのaccuracyと3期間全てのBrier/log loss改善を支持した。all accuracy差95%区間は+0.01891〜+0.06035pt、confirmationは-0.00059〜+0.06474ptで0を僅かに跨いだ。M15では再現しなかった教師品質weightの補完性が、M1では安定して現れた。

## 既存方向候補との直接比較

Path Persistence 25%はall accuracy 50.85009%、Clarityは50.84670%で74件差だった。Path−Clarityの日次accuracy差95%区間は-0.01940〜+0.02612ptで同等、年別はPath 4/7、Clarity 3/7。一方ClarityのBrier/log lossはallでPathより有意に良く、development点精度もClarityが40件上だった。Path accuracy championを置換しないが、Clarityはbaseline改善が単なる精度ノイズではなく、より滑らかな確率を持つことを示した。

Distribution Shift 25%はall accuracy 50.84629%、Clarityは9件だけ上で、Clarityがaccuracy 5/7fold勝った。しかし日次accuracy差は同等で、Distribution ShiftのBrier/log loss改善はdevelopment/allで確定した。confirmationもShiftがaccuracy +102件、proper score点推定で上回る。確率品質・stability役割はDistribution Shiftを維持する。

Extra Trees 25%とはallでClarity +3件、年別accuracy/scoreは3対3、tie 1、proper-score差も未確定だった。ClarityはSession Relativeへaccuracy 5/7、Volatility Stateへ4/7勝つが、all Brier/log lossは両既存probability-quality候補より悪い。新しいforward役割を作るには既存候補との重複が大きく、候補数を増やす品質上の根拠がない。

## 方向維持confidence 0.51

development固定grid `0.51, 0.515, 0.525, 0.535, 0.55` のcoverage-aware score最大は0.51だった。

| period | baseline accuracy / coverage / score | Clarity accuracy / coverage / score |
|---|---:|---:|
| development | 51.5790% / 44.0150% / 0.009629 | 51.6232% / 44.3059% / 0.009958 |
| confirmation | 51.8000% / 24.2132% / 0.007791 | 51.7609% / 24.3040% / 0.007615 |
| all | 51.6359% / 36.3595% / 0.009202 | 51.6585% / 36.5731% / 0.009367 |

development改善がconfirmationでaccuracy・scoreとも反転した。既存Distribution Shift 0.51はall 51.7536% / 35.6128% / 0.009802で、Clarityよりcoverageが0.9602pt狭い代わりにaccuracy +0.0951pt、score +0.000435だった。Shiftはaccuracy/score 6/7fold勝ち、日次bootstrapもdevelopment、confirmation、allのaccuracy・scoreとdevelopment/allのproper score優位を支持した。Clarity confidenceは採用しない。

## 高信頼度と局所品質

Clarity confidenceのall 0.55以上は17,965件、coverage 0.8227%、accuracy 55.0626%、mean confidence 56.2172%で1.1545pt過信した。0.575以上は2,365件、accuracy 57.2516%、mean confidence 58.7691%だが全件developmentで、confirmationは0件だった。

confirmation 0.55以上は145件、accuracy 57.2414%でも固定6セル全てWilson edge未確認だった。固定0.51ではdown-high、up-high、up-normalだけedge確認済みで、down-low 3,298件・49.8787%、down-normal 12,178件・50.7965%、up-low 8,703件・50.6722%は未確認だった。6セル中3セルしか通らず、結果確認後のsubgroup除外ruleは作らない。

latest artifactは2026-06-01 04:59 UTC判定でdown、probability down 50.6891%を返し、保存・推論経路を確認した。empirical odds calibrationなしのため `odds_valid=false` である。

## 判断

M1 Directional-Clarity weighting通常25% blendは、baselineに対するaccuracy・proper scoreを7/7foldかつ日次bootstrapで改善する有効な学習感度として保存する。ただしPathとの精度差は未確定、Distribution Shiftとの精度は実質同じでproper scoreが悪く、Extra Treesとは3件差、Session/Volatilityとのaccuracy/proper-score tradeoffも既存役割の中間に留まる。独立したforward役割がないため再現専用として棄却し、candidate configやregistry entryを増やさない。

単体と方向維持0.51も採用しない。M15/M1を通じてweight offset、非線形化、上限、blend weight、閾値を同じ履歴で再探索しない。Path/Distribution Shift/Extra Trees/Session/Volatility方向候補、Transition guard/Disagreement/Distribution Shift confidence候補を維持し、authoritative方向/confidence、fair odds、paper/live policyを変更しない。

## 成果物

- OOS: `experiments/next_bar/walk_forward_directional_clarity_weighted_m1_fixed_001`
- direction blend: `experiments/next_bar/directional_clarity_weighted_m1_blend_fixed_001`
- direction-preserving confidence: `experiments/next_bar/directional_clarity_weighted_m1_confidence_fixed_001`
- candidate analysis: `experiments/next_bar/directional_clarity_weighted_m1_candidate_analysis.json`
- baseline bootstrap: `experiments/next_bar/directional_clarity_weighted_vs_baseline_m1_direction_bootstrap.json`
- Path comparison: `experiments/next_bar/path_vs_directional_clarity_weighted_m1_direction_analysis.json`, `experiments/next_bar/path_vs_directional_clarity_weighted_m1_direction_bootstrap.json`
- Distribution Shift direction comparison: `experiments/next_bar/distribution_shift_vs_directional_clarity_weighted_m1_direction_analysis.json`, `experiments/next_bar/distribution_shift_vs_directional_clarity_weighted_m1_direction_bootstrap.json`
- Extra Trees comparison: `experiments/next_bar/extra_trees_vs_directional_clarity_weighted_m1_direction_analysis.json`, `experiments/next_bar/extra_trees_vs_directional_clarity_weighted_m1_direction_bootstrap.json`
- Session/Volatility comparisons: `experiments/next_bar/session_vs_directional_clarity_weighted_m1_direction_analysis.json`, `experiments/next_bar/volatility_vs_directional_clarity_weighted_m1_direction_analysis.json`
- Distribution Shift confidence comparison: `experiments/next_bar/distribution_shift_051_vs_directional_clarity_weighted_051_m1_analysis.json`, `experiments/next_bar/distribution_shift_051_vs_directional_clarity_weighted_051_m1_bootstrap.json`
- reliability/subgroups: `experiments/next_bar/directional_clarity_weighted_m1_confidence_subgroups.json`
- latest reproducibility check: `experiments/next_bar/directional_clarity_weighted_m1_latest_prediction.json`
