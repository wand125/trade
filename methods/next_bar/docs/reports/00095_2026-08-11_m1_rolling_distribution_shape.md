# 00095 M1 Rolling Distribution Shape

日時: 2026-08-11 07:36 JST

## 目的

次足予測へ履歴のreturn値を直接渡すのではなく、直近分布の絶対形状へ加工する。M15 intrabarで検証済みの分位形状を参考に、完成済みM1足の直近64本から頑健な位置、非対称性、裾、集中度を固定9列にして、既存Distribution Shiftとは独立に検証した。結果を見てwindow、分位点、特徴subset、HGB、blend weight、confidence閾値を変更しない。

## 固定特徴と品質

直近64本のlog returnから次を作った。

- 10% / 25% / 50% / 75% / 90%分位点を同じ窓のreturn RMSで正規化した5列。
- 25% / 50% / 75%のBowley skew、10% / 50% / 90%のtail skew。
- IQR / interdecile rangeの中央spread比。
- mean absolute return / RMSのL1/L2集中度。

生価格水準、volume、未来足、targetは特徴へ使わない。価格10倍scale不変、未来側OHLC改変が過去特徴へ不影響、完全無変動履歴の9列が有限0、分位式の数値一致、保存artifactからのlatest推論をテストした。baseline 38列へ9列を追加した全47特徴である。

source 6,025,170行、usable 5,737,928行から、baselineとtimestamp、decision/target timestamp、target、foldが全件一致する2,183,717 OOS行を生成した。HGB 200 iteration、31 leaves、learning rate 0.05、min leaf 100、L2 1、expanding train最大750,000行、Platt、seed 42、通常・方向維持ともbaseline 75% + candidate 25%を固定した。損失倍率は標準1.0のみである。

## 単体と通常方向blend

| period | baseline | Shape単体 | 通常25% blend |
|---|---:|---:|---:|
| development | 50.93738% | 50.93514% | 50.93357% |
| confirmation | 50.60001% | 50.66776% | 50.61375% |
| all | 50.80695% | 50.83177% | 50.80993% |

単体はall +542件、accuracy 5/7foldだったが、development -30件、confirmation +572件、McNemar exact p=0.2662だった。UTC日paired bootstrap 20,000回のaccuracy差95%区間はdevelopment -0.05812〜+0.05368pt、confirmation -0.00142〜+0.13703pt、all -0.01894〜+0.06798ptで、全期間0を跨いだ。Brier/log lossも各2/7foldで、方向候補として採用できない。

通常25% blendはdevelopment -51件、confirmation +116件、all +65件、McNemar exact p=0.7920、accuracy 3/7foldだった。accuracy差95%区間もdevelopment -0.03113〜+0.02365pt、confirmation -0.02157〜+0.04925pt、all -0.01932〜+0.02455ptで未確定だった。Brier/log lossは6/7fold改善し、development/allの日次区間も改善側だが、confirmation proper score区間は0を跨いだ。確率品質だけを理由に方向candidateへ追加しない。

## 方向維持confidence 0.51

development固定grid `0.51, 0.515, 0.525, 0.535, 0.55` のcoverage-aware score最大は0.51だった。

| period | baseline accuracy / coverage / score | Rolling Shape accuracy / coverage / score |
|---|---:|---:|
| development | 51.5790% / 44.0150% / 0.009629 | 51.6506% / 43.6951% / 0.010065 |
| confirmation | 51.8000% / 24.2132% / 0.007791 | 51.7932% / 23.9284% / 0.007706 |
| all | 51.6359% / 36.3595% / 0.009202 | 51.6872% / 36.0532% / 0.009468 |

developmentではaccuracy、score、Brier/log lossの日次区間が改善側だった。しかし事前固定したconfirmationではaccuracy -0.0068pt、coverage -0.2848pt、score -0.0000855と3指標すべて点推定で反転し、accuracy/score/proper scoreの日次区間も0を跨いだ。foldではbaseline比accuracy 6/7、score 5/7、Brier/log loss 6/7だが、confirmation gateを通らない。

既存Distribution Shift 0.51に対してRolling Shapeはdevelopment score 0.010065対0.010357、confirmation 0.007706対0.008142、all 0.009468対0.009802だった。Rolling Shapeのcoverageは各期間で約0.40〜0.46pt広いが、accuracy・scoreのfold勝敗は1/7対6/7である。Distribution Shiftのaccuracy優位はdevelopment、confirmation、allの日次区間すべて改善側、proper score優位も3期間すべて確定した。既存候補を置換しない。

## 高信頼度と局所品質

confirmationの累積accuracyは0.51、0.515、0.525、0.535で51.793%、52.555%、55.059%、57.084%と上がり、confidence順位付け自体はある。ただし0.55は119件・accuracy 56.30%、Wilson下限47.33%でedge未確認だった。0.51はaccuracy 51.793%に対しmean confidence 51.539%で0.254ptの過小評価だが、局所整合判定は不成立だった。

confirmation 0.51の固定side × volatility 6セルではdown-high、up-high、up-normalだけがWilson edgeを通った。down-low 3,177件・50.582%、down-normal 11,796件・50.771%、up-low 8,386件・50.918%はedge未確認だった。confirmationを見た後のsubgroup除外ruleは作らない。fair odds・採用policyには使わない。

## 判断

Rolling Distribution Shapeの単体、通常方向blend、方向維持0.51を再現専用として棄却する。単体のconfirmation点精度とconfidenceの順位性は保存価値があるが、方向改善の日次区間は確定せず、0.51のcoverage-aware objectiveはconfirmationで反転し、既存Distribution Shiftに6/7foldで負けた。

64本窓、5分位点、9列、HGB parameter、25% weight、0.51を同じ履歴で再探索しない。Path/Distribution Shift方向候補、Transition guard/Disagreement/Distribution Shift confidence候補を維持し、config、registry、authoritative方向/confidence、fair odds、paper/live policyを変更しない。latestはartifact再現確認に限る。

## 成果物

- OOS: `experiments/next_bar/walk_forward_rolling_distribution_shape_m1_fixed_001`
- direction blend: `experiments/next_bar/rolling_distribution_shape_m1_blend_fixed_001`
- direction-preserving confidence: `experiments/next_bar/rolling_distribution_shape_m1_confidence_fixed_001`
- candidate analysis: `experiments/next_bar/rolling_distribution_shape_m1_candidate_analysis.json`
- baseline bootstraps: `experiments/next_bar/rolling_distribution_shape_single_vs_baseline_m1_direction_bootstrap.json`, `experiments/next_bar/rolling_distribution_shape_vs_baseline_m1_direction_bootstrap.json`, `experiments/next_bar/rolling_distribution_shape_vs_baseline_m1_confidence_051_bootstrap.json`
- Distribution Shift direct comparison: `experiments/next_bar/distribution_shift_051_vs_rolling_distribution_shape_051_m1_analysis.json`, `experiments/next_bar/distribution_shift_051_vs_rolling_distribution_shape_051_m1_bootstrap.json`
- reliability/subgroups: `experiments/next_bar/distribution_shift_vs_rolling_distribution_shape_m1_confidence_reliability.json`, `experiments/next_bar/rolling_distribution_shape_m1_confidence_subgroups.json`
- latest reproducibility check: `experiments/next_bar/rolling_distribution_shape_m1_latest_prediction.json`
