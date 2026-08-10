# 00094 M1 Distribution Shift × LightGBM

日時: 2026-08-11 07:08 JST

## 目的

採用済み研究候補のDistribution Shift 16特徴について、HGBで得たedgeが特徴そのものに由来するのか、学習器との相互作用なのかを固定LightGBMで検証した。結果を見て特徴、木の設定、blend weight、confidence閾値を調整しない、feature × learnerの独立感度試験である。

## 固定仕様と品質

baseline 38特徴へDistribution Shift 16特徴を加えた54特徴を使用した。短期8本、直前非重複64本、履歴順位128本、quantile、scale不変・未来不参照・flat有限0の定義は親HGB版から変更していない。

LightGBM 4.7.0、300 trees、31 leaves、learning rate 0.03、min child 100、row/column sample 0.8、L2 5、seed 42、expanding train最大750,000行、後続Plattを固定した。通常方向blendと方向維持confidenceはともにbaseline 75% + LightGBM 25%である。2020〜2026途中の7fold、2,183,717 OOS行を生成し、baselineおよび親Distribution Shiftとtimestamp、target、foldが全件一致、重複0、確率欠損0だった。7 model artifactの保存・再読込とlatest推論も確認した。損失倍率は標準1.0のみである。

## 単体と通常方向blend

| period | baseline | Shift × LightGBM単体 | 通常25% blend |
|---|---:|---:|---:|
| development | 50.93738% | 50.89983% | 50.94201% |
| confirmation | 50.60001% | 50.62121% | 50.62666% |
| all | 50.80695% | 50.79211% | 50.82009% |

単体はbaseline比all -324件だった。さらに同じ固定LightGBMへbaseline 38特徴だけを入れた親LightGBM単体に対しall accuracy -0.05779ptで、UTC日paired bootstrap 20,000回の95%区間は-0.11021〜-0.00442ptだった。Distribution Shift特徴の追加は、LightGBM単体の方向精度を明確に悪化させた。

通常25% blendはdevelopment +62件、confirmation +225件、all +287件、McNemar exact p=0.3372だった。Brier/log lossは7/7fold改善したがaccuracy改善は3/7foldで、accuracy差95%区間はdevelopment -0.02951〜+0.03852pt、confirmation -0.01871〜+0.07174pt、all -0.01391〜+0.04011ptと全期間で0を跨いだ。proper score改善だけでは次足方向candidateへ採用しない。

## 方向維持confidence 0.51

baseline方向を完全に維持し、development固定grid `0.51, 0.515, 0.525, 0.535, 0.55` でcoverage-aware score最大の0.51を一度だけ選んだ。

| period | baseline accuracy / coverage / score | Shift × LightGBM accuracy / coverage / score |
|---|---:|---:|
| development | 51.5790% / 44.0150% / 0.009629 | 51.6915% / 43.6815% / 0.010333 |
| confirmation | 51.8000% / 24.2132% / 0.007791 | 51.8294% / 24.2639% / 0.007945 |
| all | 51.6359% / 36.3595% / 0.009202 | 51.7273% / 36.1745% / 0.009726 |

baseline比ではaccuracy 6/7、selection score 6/7、Brier/log loss 7/7foldを改善した。日次bootstrapのaccuracy差とscore差はdevelopment/allで改善側だったが、confirmationは両方0を跨いだ。

親HGB Distribution Shift 0.51との直接比較では、LightGBM版のdevelopment coverageは43.6815%で親43.2316%より+0.4499pt広い。一方、開発期間の最大化対象scoreは0.010333で親0.010357を下回った。confirmationもaccuracy 51.8294%対51.8985%、score 0.007945対0.008142、allも51.7273%対51.7536%、0.009726対0.009802だった。fold勝敗は親がaccuracy/score各4/7、LightGBM版が各3/7で、選択行Jaccardはdevelopment 0.9191だった。両者のaccuracy、score、proper score差のbootstrap区間は0を跨いだため統計的な大差ではないが、事前の採用目的関数を改善しない以上、親を置換しない。

現Transition guard champion 0.515にはaccuracy 0/7で、all accuracy差-0.8555ptのbootstrap区間も全て悪化側だった。LightGBM版はcoverageを+20.157pt増やし、all scoreの点推定は0.009726対0.009674と僅かに高いが、score差区間は0を跨ぎ、development scoreは0.010333対0.010447で下回った。高精度役割にも目的関数championにも昇格しない。

## 信頼度品質

0.51 laneはdevelopmentでaccuracy 51.6915%に対しmean confidence 52.1404%の過信、confirmationで51.8294%に対し51.5417%の過小評価となり、局所校正が時期で反転した。confirmationの累積accuracyは0.51、0.515、0.525、0.535で51.829%、52.797%、55.318%、57.662%と上昇したが、0.55は76件・50.0%、Wilson下限39.03%でedge未確認だった。

confirmation 0.51の固定side × volatility 6セルではdown-high、up-high、up-low、up-normalだけがWilson edgeを通り、down-low 2,605件・accuracy 49.789%とdown-normal 10,964件・50.575%は未確認だった。確認期間を見た後の除外ruleは作らない。順位付けの一部は有効でも確率値をfair oddsとして認可できる品質ではない。

## 判断

Distribution Shift × LightGBMの単体、通常方向blend、方向維持0.51を再現専用として棄却する。LightGBM化は親HGB版より僅かにcoverageを増やしたが、開発期間の最大化対象scoreを上げず、追加特徴はbaseline-feature LightGBM単体の方向精度を明確に悪化させた。親HGB Distribution Shiftの通常25% stability/proper-score方向challengerと0.51 ultra-broad coverage Pareto challengerを維持する。

54特徴、LightGBM parameter、25% weight、0.51を同じ履歴で再探索しない。config、registry、authoritative方向/confidence、fair odds、採用条件、paper/live policyは変更しない。latest推論はartifact再現確認に限り、運用候補の発行ではない。

## 成果物

- OOS: `experiments/next_bar/walk_forward_distribution_shift_lightgbm_m1_fixed_001`
- direction blend: `experiments/next_bar/distribution_shift_lightgbm_m1_blend_fixed_001`
- direction-preserving confidence: `experiments/next_bar/distribution_shift_lightgbm_m1_confidence_fixed_001`
- candidate analysis: `experiments/next_bar/distribution_shift_lightgbm_m1_candidate_analysis.json`
- baseline comparisons: `experiments/next_bar/distribution_shift_lightgbm_vs_baseline_m1_direction_bootstrap.json`, `experiments/next_bar/distribution_shift_lightgbm_vs_baseline_m1_confidence_051_bootstrap.json`
- baseline-feature LightGBM comparison: `experiments/next_bar/distribution_shift_lightgbm_vs_parent_lightgbm_m1_direction_bootstrap.json`
- parent HGB comparison: `experiments/next_bar/distribution_shift_hgb_051_vs_lightgbm_051_m1_analysis.json`, `experiments/next_bar/distribution_shift_hgb_051_vs_lightgbm_051_m1_bootstrap.json`
- champion comparison: `experiments/next_bar/distribution_shift_lightgbm_051_vs_transition_guard_champion_0515_m1_analysis.json`, `experiments/next_bar/distribution_shift_lightgbm_051_vs_transition_guard_champion_0515_m1_bootstrap.json`
- reliability/subgroups: `experiments/next_bar/distribution_shift_hgb_vs_lightgbm_m1_confidence_reliability.json`, `experiments/next_bar/distribution_shift_lightgbm_m1_confidence_subgroups.json`
- latest reproducibility check: `experiments/next_bar/distribution_shift_lightgbm_m1_latest_prediction.json`
