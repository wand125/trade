# 00096 M1 Rolling Full Path

日時: 2026-08-11 08:08 JST

## 目的

履歴の数値をそのまま渡さず、完成済みM1足の順序付き価格経路へ加工する。M15 Full Pathで有効だった考え方をM1へ固定移植し、直近15本の全体range内でcloseがどこを通ったかを11点の経路形状として表現した。結果を見てwindow、採取点、特徴subset、HGB、blend weight、confidence閾値を変更しない。

事前監査ではsourceのvolume 6,025,170行が全て0だったため特徴から除外した。既に棄却したcorrectness meta、cross-TF metaの再探索も避け、未検証だった順序情報だけを対象にした。

## 固定特徴と品質

直近15完成足の最初のopenを原点、15本のjoint high-low rangeを分母とし、1、2、4、5、7、8、10、11、13、14、15本目のclose位置を正規化した。各値は `[-1, 1]` へclipし、range 0では11列全て0とした。

生価格水準、volume、未来足、targetは特徴へ使わない。価格10倍scale不変、未来側OHLC改変が過去特徴へ不影響、完全無変動履歴が有限0、式の数値一致、保存artifactからのlatest推論をテストした。baseline 38列へ11列を追加した全49特徴である。

source 6,025,170行、usable 5,737,928行から、baselineとtimestamp、decision/target timestamp、target、foldが全件一致する2,183,717 OOS行を生成した。HGB 200 iteration、31 leaves、learning rate 0.05、min leaf 100、L2 1、expanding train最大750,000行、Platt、seed 42、通常・方向維持ともbaseline 75% + candidate 25%を固定した。損失倍率は標準1.0のみである。

## 単体と通常方向blend

| period | baseline | Full Path単体 | 通常25% blend |
|---|---:|---:|---:|
| development | 50.93738% | 50.93327% | 50.93962% |
| confirmation | 50.60001% | 50.63009% | 50.64608% |
| all | 50.80695% | 50.81606% | 50.82614% |

単体はall +199件、accuracy 3/7fold、Brier/log loss 2/7foldで、McNemar exact p=0.6663だった。既存方向を改善する根拠はない。

通常25% blendはdevelopment +30件、confirmation +389件、all +419件、accuracy 5/7fold、Brier/log loss 6/7foldだった。confirmationのMcNemar exact p=0.00605で、UTC日paired bootstrap 20,000回のaccuracy差95%区間も+0.01464〜+0.07764ptと改善側だった。一方、developmentは-0.02501〜+0.02881pt、allは-0.00161〜+0.03992ptで0を跨いだ。development/allのBrier・log lossは改善側だが、confirmationのproper score差は実質0で区間も跨いだ。

既存Pathとの直接比較では、Pathがdevelopment +0.03927pt、all +0.02395ptで、日次95%区間もそれぞれ+0.01033〜+0.06879pt、+0.00120〜+0.04651ptとPath優位だった。confirmationは-0.00036ptで同等、proper score差も3期間全て未確定である。Rolling Full Pathの確認期間改善は保存価値があるが、既存Pathに対する増分役割を作らない。Distribution Shiftのall accuracy 50.84629%もRolling Full Pathの50.82614%を上回る。

## 方向維持confidence 0.515

development固定grid `0.51, 0.515, 0.525, 0.535, 0.55` のcoverage-aware score最大は0.515だった。

| period | baseline accuracy / coverage / score | Rolling Full Path accuracy / coverage / score |
|---|---:|---:|
| development | 51.9505% / 28.6110% / 0.009587 | 52.0247% / 28.3304% / 0.009931 |
| confirmation | 52.5091% / 9.9208% / 0.006837 | 52.5373% / 9.6961% / 0.006835 |
| all | 52.0507% / 21.3852% / 0.008820 | 52.1157% / 21.1262% / 0.009062 |

baseline比ではdevelopmentとallのaccuracy・selection score・proper scoreの日次区間が改善側だった。しかし固定confirmationではaccuracy差区間-0.10287〜+0.15927pt、score差-0.000413〜+0.000407、Brier/log lossも0を跨ぎ、点scoreは僅かに反転した。accuracy 5/7、score 4/7foldで、confirmation gateを通らない。

既存Disagreement 0.515との直接比較では、Rolling Full Pathはall coverageが21.126%対19.896%と1.230pt広い一方、Disagreementはaccuracy 52.309%対52.116%、score 0.009636対0.009062だった。Disagreementはaccuracy・score各6/7foldで勝ち、日次bootstrapもdevelopment、confirmation、allのaccuracy、Wilson下限、selection score、Brier、log loss全てでDisagreement優位を支持した。特にconfirmationはaccuracy +0.4933pt、score +0.001069である。balanced confidence役割を置換しない。

## 高信頼度と局所品質

Rolling Full Pathの累積accuracyは概ねconfidenceとともに上昇したが、校正はDisagreementより弱い。all 0.55以上は17,458件、coverage 0.7995%、accuracy 54.9376%、mean confidence 56.2022%、Wilson下限54.1985%で、1.2646ptの過信だった。Disagreementは同閾値で11,820件、accuracy 55.7530%、mean confidence 56.0906%、校正gap -0.3377ptだった。

confirmation 0.55以上は146件、accuracy 56.8493%、Wilson下限48.7413%でedge未確認だった。confirmation 0.515の固定side × volatility 6セルではdown-high、up-high、up-normalだけがWilson edgeを通り、down-low 705件・47.943%、down-normal 2,672件・49.588%、up-low 1,690件・49.882%はedge未確認だった。confirmationを見た後のsubgroup除外ruleは作らない。fair odds・採用policyには使わない。

latest artifactは2026-06-01 04:59 UTC判定でup、probability up 50.0756%を返し、保存・推論経路を確認した。empirical odds calibrationなしのため `odds_valid=false` である。

## 判断

Rolling Full Pathの単体、通常方向blend、方向維持0.515を再現専用として棄却する。通常blendのconfirmation方向改善は再現したが、全期間accuracy区間が0を跨ぎ、既存Pathがdevelopment/allで有意に上回るため固有の方向役割がない。confidenceもconfirmation objectiveが未確定で、Disagreementに6/7foldと全期間bootstrapで負けた。

15本窓、11採取点、HGB parameter、25% weight、0.515を同じ履歴で再探索しない。Path/Distribution Shift方向候補、Transition guard/Disagreement/Distribution Shift confidence候補を維持し、config、registry、authoritative方向/confidence、fair odds、paper/live policyを変更しない。

## 成果物

- OOS: `experiments/next_bar/walk_forward_rolling_full_path_m1_fixed_001`
- direction blend: `experiments/next_bar/rolling_full_path_m1_blend_fixed_001`
- direction-preserving confidence: `experiments/next_bar/rolling_full_path_m1_confidence_fixed_001`
- candidate analysis: `experiments/next_bar/rolling_full_path_m1_candidate_analysis.json`
- baseline bootstraps: `experiments/next_bar/rolling_full_path_vs_baseline_m1_direction_bootstrap.json`, `experiments/next_bar/rolling_full_path_vs_baseline_m1_confidence_0515_bootstrap.json`
- Path direct bootstrap: `experiments/next_bar/path_vs_rolling_full_path_m1_direction_bootstrap.json`
- Disagreement direct comparison: `experiments/next_bar/disagreement_0515_vs_rolling_full_path_0515_m1_analysis.json`, `experiments/next_bar/disagreement_0515_vs_rolling_full_path_0515_m1_bootstrap.json`
- reliability/subgroups: `experiments/next_bar/disagreement_vs_rolling_full_path_m1_confidence_reliability.json`, `experiments/next_bar/rolling_full_path_m1_confidence_subgroups.json`
- latest reproducibility check: `experiments/next_bar/rolling_full_path_m1_latest_prediction.json`
