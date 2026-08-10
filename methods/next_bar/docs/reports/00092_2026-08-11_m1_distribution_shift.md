# 00092 M1 Rolling Distribution Shift

日時: 2026-08-11 06:50 JST

## 目的

既存Trend/Pathと重複するentropy・serial-dependence案を監査段階で中止し、完成済みM1の短期分布が直前の長期分布からどれだけ移動したかを加工する。現在値そのものではなく、履歴順位、location/scale変化、方向・tail占有率変化、candle pressure分布変化を次足方向へ利用できるか固定条件で検証した。

## 固定特徴と品質

次の16列をbaseline 38列へ追加した。

- 直近128本内のreturn、absolute return、range、absolute bodyの中心化empirical rank 4列。
- 直近8本と、その直前の非重複64本におけるreturn location、absolute-return scale、variance scale、up比率のshift 4列。
- prior 64本の20%/80% return quantileに対する直近8本のtail balanceとtail activity 2列。
- range/body scale shift 2列。
- body/wick/close pressureの平均shiftとclose-pressure dispersion shift 4列。

rankはtie時0、scale差は対称比、return locationだけreference標準偏差で正規化して±5へclipした。raw OHLC価格水準、volume、未来足、targetはmodel featureへ使わない。価格10倍scale不変、未来側OHLC改変が過去特徴へ不影響、完全無変動履歴の全16列が有限0、raw価格排除、保存artifactからのlatest推論をテストした。

source 6,025,170行、usable 5,737,873行から、baselineとfold、timestamp、targetが完全一致する2,183,717 OOS行を生成した。HGB、Platt、最大750,000行expanding train、7fold、seed 42、baseline 75% + candidate 25%を固定し、結果を見て窓、特徴subset、weightを変更していない。損失倍率は標準1.0である。

## 単体と固定25%方向blend

| period | baseline | Distribution Shift単体 | HGB 75% + Shift 25% |
|---|---:|---:|---:|
| development accuracy | 50.93738% | 50.87795% | 50.97359% |
| confirmation accuracy | 50.60001% | 50.63921% | 50.64431% |
| all accuracy | 50.80695% | 50.78566% | 50.84629% |

単体はdevelopment -796件、confirmation +331件、all -465件で、accuracy 4/7、Brier/log loss各3/7foldのため不採用とする。

通常25% blendはdevelopment +485件、confirmation +374件、all +859件、McNemar exact p=0.00449だった。accuracy、Brier、log lossを7/7fold、ECEを5/7fold改善した。all Brierは0.24986888→0.24985785、log lossは0.69288487→0.69286275、ECEは0.2029%→0.1415%となった。

UTC日20,000回paired bootstrapのaccuracy差95%区間はdevelopment +0.00022〜+0.07127pt、confirmation +0.00059〜+0.08845pt、all +0.01141〜+0.06746ptで、全3期間が改善側だった。all Brier差区間は-0.00001389〜-0.00000820、log loss差は-0.00002785〜-0.00001645である。

## 既存方向候補との比較

| model | development | confirmation | all |
|---|---:|---:|---:|
| Distribution Shift 25% | 50.97359% | 50.64431% | 50.84629% |
| Path 25% | 50.97889% | 50.64573% | 50.85009% |
| Extra Trees 25% | 50.98292% | 50.63021% | 50.84656% |
| Volatility State 25% | 50.96336% | 50.64905% | 50.84184% |
| Session Relative 25% | 50.96269% | 50.63862% | 50.83740% |

Pathには全体-83件、accuracy 3/7対4/7で、accuracy差bootstrap区間は-0.03149〜+0.02398ptと未確定だった。一方、Brier差区間-0.00000976〜-0.00000417、log loss差-0.00001957〜-0.00000837でDistribution Shiftが明確に良い。Pathをaccuracy point championとして維持する。

Extra Treesとは全体6件差でaccuracy区間は-0.02704〜+0.02634pt、3/7対4/7の同等だった。Distribution Shiftはconfirmationが+0.01410ptで、all Brier/log loss改善区間も確定したため、Extra Treesのstability研究役割を引き継ぐ。Extra Treesは異種学習器比較用に残す。

Volatilityには全体+97件、Sessionには+194件だが、直接のaccuracy/proper score区間はいずれも0を跨いだ。Volatilityのbalanced state候補、Sessionのprobability-quality候補を履歴上の微差で棄却せず、union・再weightは行わない。

## 固定0.51 confidence

方向維持25% blendのdevelopment固定grid目的関数最大は0.51だった。

| period | baseline accuracy / coverage / score | Distribution Shift accuracy / coverage / score |
|---|---:|---:|
| development | 51.5790% / 44.0150% / 0.009629 | 51.7039% / 43.2316% / 0.010357 |
| confirmation | 51.8000% / 24.2132% / 0.007791 | 51.8985% / 23.5247% / 0.008142 |
| all | 51.6359% / 36.3595% / 0.009202 | 51.7536% / 35.6128% / 0.009802 |

baseline比accuracy・scoreを6/7fold、proper scoreを7/7fold改善した。日次bootstrapではaccuracy差がdevelopment、confirmation、allで改善側、selection score差はdevelopmentとallで改善側だった。confirmation score差区間だけは-0.000102〜+0.000803で0を跨ぐ。

現Transition guard 50/50 championの0.515はdevelopment accuracy 52.4249% / coverage 21.6867% / score 0.010447で、Shift 0.51のscore 0.010357を僅かに上回る。Shiftはaccuracy 0/7、score 4/7だがcoverageを+21.545pt増やし、confirmation/all scoreはpoint優位で、score差bootstrapは未確定だった。registryではchampionを変更せず、Shiftをdevelopment coverage leaderかつPareto challengerへ追加した。Disagreement 0.515に対してもaccuracy 0/7、score 5/7で、役割は高精度ではなく超広coverageである。

## 校正と局所品質

Shift 0.51はdevelopmentでaccuracy 51.7039%に対しmean confidence 52.1249%で過信、confirmationではaccuracy 51.8985%に対し51.5327%で過小評価へ反転し、globalに局所整合しない。confirmationの固定6セルではdown-lowだけ2,336件、accuracy 49.914%、Wilson下限47.889%でedge未確認だった。developmentでは同じセルのedgeが確認できていたため、confirmationを見たpost-hoc除外ruleは作らない。

0.51→0.535のconfirmation累積accuracyは51.8985%→57.9769%へ上昇したが、0.55は57件・accuracy 43.86%でedge未確認となる。confidence順位付けには使えるが、確率値をfair oddsとして認可しない。

## 判断

`m1_distribution_shift_direction_confidence_candidate_v1.json` を発行する。通常25% blendをdistribution-shift stability/proper-score方向challenger、方向維持0.51をultra-broad coverage Pareto confidence challengerとして採用する。

Path accuracy champion、Transition guard 0.515 accuracy-confidence champion、Disagreement balanced-confidence challengerは置換しない。authoritative方向/confidence、fair odds、採用条件、paper/live policyも変更しない。完全未使用期間では方向accuracy/Brier/log lossのbaseline非劣化、0.51 selection score、固定6セル、とくにdown-low edge、runtime probability parity、局所校正を要求する。

8/64/128窓、quantile、feature subset、HGB parameter、25% weight、0.51閾値を同じ履歴で再探索しない。

## 成果物

- config: `methods/next_bar/config/m1_distribution_shift_direction_confidence_candidate_v1.json`
- OOS: `experiments/next_bar/walk_forward_distribution_shift_m1_fixed_001`
- direction blend: `experiments/next_bar/distribution_shift_m1_blend_current_001`
- confidence blend: `experiments/next_bar/distribution_shift_m1_confidence_blend_current_001`
- candidate analysis: `experiments/next_bar/distribution_shift_m1_candidate_analysis.json`
- baseline direction bootstrap: `experiments/next_bar/distribution_shift_vs_baseline_m1_direction_bootstrap.json`
- baseline confidence bootstrap: `experiments/next_bar/distribution_shift_vs_baseline_m1_confidence_051_bootstrap.json`
- Path/Extra Trees/Volatility/Session direct comparisons: `experiments/next_bar/distribution_shift_vs_*_m1_direction_{analysis,bootstrap}.json`
- champion/Disagreement confidence comparisons: `experiments/next_bar/distribution_shift_051_vs_*_0515_m1_confidence_{analysis,bootstrap}.json`
- reliability/subgroups: `experiments/next_bar/distribution_shift_vs_transition_guard_champion_m1_confidence_reliability.json`, `experiments/next_bar/distribution_shift_m1_confidence_subgroups.json`
- registry: `experiments/next_bar/m1_candidate_registry_distribution_shift_001.json`
- latest runtime: `experiments/next_bar/distribution_shift_m1_latest_prediction.json`
