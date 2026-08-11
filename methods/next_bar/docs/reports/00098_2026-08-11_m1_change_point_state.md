# 00098 M1 Change-Point State

日時: 2026-08-11 08:52 JST

## 目的

価格履歴をそのまま入力せず、直近のreturnとrangeが過去の通常状態からどちら向きに、どの程度継続して外れたかを因果的CUSUM状態へ加工した。Distribution Shiftの固定窓分布比較とは異なり、今回は逐次蓄積する変化点score、alarm方向、alarm継続時間が次足方向と信頼度を補完できるかを一度だけ検証した。

## 固定特徴と品質

M1 log returnと `log(high / low)` の2系列を使う。各現在値を現在足を含まない直前64本の平均・標準偏差で標準化し、innovationを `[-5, 5]` へclipした。正負CUSUMはdrift 0.25、alarm閾値5、score上限20とし、各系列から正score、負score、符号付きbalance、alarm方向、alarm ageの5列、合計10列を追加した。alarm ageは64で上限化し、timestamp gapが1本超なら逐次状態をresetする。

生OHLC価格水準、未来足、targetは特徴へ使わない。価格10倍scale不変、未来側OHLC改変が過去特徴へ不影響、完全無変動履歴が有限0、gap直後のreset式、保存artifactからのlatest推論をテストした。baseline 38列へ10列を追加した全48特徴である。

source 6,025,170行、usable 5,737,928行から、baselineと同じ7fold・2,183,717 OOS行を生成した。HGB 200 iteration、31 leaves、learning rate 0.05、min leaf 100、L2 1、expanding train最大750,000行、Platt、seed 42、通常・方向維持ともbaseline 75% + candidate 25%を固定した。損失倍率は標準1.0のみである。

## 単体と通常方向blend

| period | baseline | Change-Point単体 | 通常25% blend |
|---|---:|---:|---:|
| development | 50.93738% | 50.86101% | 50.94970% |
| confirmation | 50.60001% | 50.66670% | 50.61185% |
| all | 50.80695% | 50.78588% | 50.81909% |

単体はconfirmationで+563件だったがdevelopment -1,023件、all -460件、accuracy 2/7fold、Brier/log loss 3/7foldで棄却する。

通常25% blendはdevelopment +165件、confirmation +100件、all +265件で、Brier/log lossを6/7fold改善した。UTC日paired bootstrap 20,000回ではBrier/log lossがdevelopment、confirmation、allの全てで改善側だったが、accuracy差95%区間はdevelopment -0.01353〜+0.03784pt、confirmation -0.02050〜+0.04448pt、all -0.00830〜+0.03207ptで全て0を跨いだ。確率品質の補完はあるが方向精度改善は確定しない。

既存Pathとの直接比較では、Pathがdevelopment +0.02919pt、all +0.03100ptで、日次95%区間もそれぞれ+0.00067〜+0.05772pt、+0.00869〜+0.05319ptとPath優位だった。Pathはaccuracy・selection score各6/7foldで勝つため、Change-Pointを方向候補へ追加しない。Distribution Shiftもall accuracy 50.84629%で上回り、確率品質役割も既に保持している。

## 方向維持confidence 0.515

development固定grid `0.51, 0.515, 0.525, 0.535, 0.55` のcoverage-aware score最大は0.515だった。

| period | baseline accuracy / coverage / score | Change-Point accuracy / coverage / score |
|---|---:|---:|
| development | 51.9505% / 28.6110% / 0.009587 | 52.0047% / 28.3257% / 0.009823 |
| confirmation | 52.5091% / 9.9208% / 0.006837 | 52.6387% / 9.8399% / 0.007212 |
| all | 52.0507% / 21.3852% / 0.008820 | 52.1185% / 21.1789% / 0.009087 |

これはbaselineに対して強い結果である。accuracy差の日次95%区間はdevelopment +0.00750〜+0.10104pt、confirmation +0.01167〜+0.24683pt、all +0.02391〜+0.11204ptで改善側だった。confirmation/allはselection scoreも改善側で、Brier/log lossは3期間全て改善した。accuracy・score・proper scoreは各6/7foldでbaselineを上回った。

ただし既存confidence候補に対する増分役割はない。Disagreement 0.515はall accuracy 52.309% / coverage 19.896% / score 0.009636で、Change-Pointよりcoverageが1.283pt狭い一方、accuracy +0.1904pt、score +0.000549である。accuracy・score各6/7fold、all日次95%区間もaccuracy +0.1130〜+0.2673pt、score +0.000202〜+0.000897でDisagreement優位だった。

現Transition guard × Disagreement championはall accuracy 52.5827% / coverage 16.0178% / score 0.009674。Change-Point比accuracy +0.4642pt、score +0.000587で、accuracy 7/7fold、score 6/7fold、all日次区間はいずれもchampion優位だった。accuracy specialistを置換しない。

反対にultra-broad Distribution Shift 0.51はall accuracy 51.7536% / coverage 35.6128% / score 0.009802である。Change-Pointよりaccuracyは低いがcoverage +14.4339pt、score +0.000715。selection scoreは7/7foldで勝ち、development、confirmation、allの日次95%区間も全てDistribution Shift優位だった。Change-Pointは既存3候補の間に位置するが、balanced枠ではDisagreement、精度枠ではchampion、広域枠ではDistribution Shiftに負ける。

## 高信頼度と局所品質

Change-Pointの累積accuracyは0.515から0.575まで概ね上昇した。allでは0.525以上170,197件・53.0667%、0.55以上17,806件・55.0432%、0.575以上2,374件・57.4558%だった。しかしmean confidenceはそれぞれ53.6084%、56.2125%、58.7665%で、全て過信側である。Disagreementはall 0.55で11,820件・55.7530%とChange-Pointより+0.7097pt高かった。

confirmationでは0.525以上12,310件・54.8416%だが、0.55以上は170件・57.6471%、0.575以上は0件で、高信頼度tailは薄い。confirmation 0.515の固定side × volatility 6セルではdown-high、up-high、up-normalだけがWilson edgeを通った。down-low 736件・47.4185%、down-normal 2,665件・50.4690%、up-low 1,706件・50.0000%はedge未確認である。confirmationを見た後のsubgroup除外ruleは作らない。

latest artifactは2026-06-01 04:59 UTC判定でdown、probability down 50.0665%を返し、保存・推論経路を確認した。empirical odds calibrationなしのため `odds_valid=false` である。

## 判断

Change-Point Stateの単体、通常方向blend、方向維持0.515を再現専用として棄却する。baselineへのconfidence改善は統計的に支持されたためアイデア自体は有効だが、既存の精度・balanced・広域coverage候補のどの役割も更新せず、高信頼度tailと固定セルの局所整合も十分でない。候補数を増やす品質上の根拠がない。

64本reference、drift 0.25、alarm 5、score cap 20、age cap 64、10特徴、HGB parameter、25% weight、0.515を同じ履歴で再探索しない。Path/Distribution Shift方向候補、Transition guard/Disagreement/Distribution Shift confidence候補を維持し、config、registry、authoritative方向/confidence、fair odds、paper/live policyを変更しない。

## 成果物

- OOS: `experiments/next_bar/walk_forward_change_point_state_m1_fixed_001`
- direction blend: `experiments/next_bar/change_point_state_m1_blend_fixed_001`
- direction-preserving confidence: `experiments/next_bar/change_point_state_m1_confidence_fixed_001`
- candidate analysis: `experiments/next_bar/change_point_state_m1_candidate_analysis.json`
- baseline bootstraps: `experiments/next_bar/change_point_state_vs_baseline_m1_direction_bootstrap.json`, `experiments/next_bar/change_point_state_vs_baseline_m1_confidence_0515_bootstrap.json`
- Path direct comparison: `experiments/next_bar/path_vs_change_point_state_m1_direction_analysis.json`, `experiments/next_bar/path_vs_change_point_state_m1_direction_bootstrap.json`
- confidence direct comparisons: `experiments/next_bar/disagreement_0515_vs_change_point_state_0515_m1_{analysis,bootstrap}.json`, `experiments/next_bar/transition_guard_champion_0515_vs_change_point_state_0515_m1_{analysis,bootstrap}.json`, `experiments/next_bar/distribution_shift_051_vs_change_point_state_0515_m1_{analysis,bootstrap}.json`
- reliability/subgroups: `experiments/next_bar/disagreement_vs_change_point_state_m1_confidence_reliability.json`, `experiments/next_bar/change_point_state_m1_confidence_subgroups.json`
- latest reproducibility check: `experiments/next_bar/change_point_state_m1_latest_prediction.json`
