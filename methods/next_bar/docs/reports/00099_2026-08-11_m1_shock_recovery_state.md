# 00099 M1 Shock / Recovery State

日時: 2026-08-11 09:21 JST

## 目的

履歴の価格値をそのまま入力せず、固定2σ shockが発生した後に値動きが継続するか、反転・回復するかをイベント起点の状態へ加工した。Change-Point Stateは小さな偏りをCUSUMへ累積し、Distribution Shiftは固定窓間の分布差を表す。今回は未検証だったshock後のresponse、最大順行、最大逆行だけを一度検証した。

## 固定特徴と品質

M1 log returnと `log(high / low)` を、現在足を含まない直前64本の平均・標準偏差で標準化し、innovationを `[-5, 5]` へclipした。絶対innovationが2以上ならshockとし、結果を見る前に追跡期間16本、response上限3へ固定した。

return shockから方向、2σ超過量、age、shock後累積returnをshock実体で割ったresponse、最大continuation、最大reversalを作る。range shockから方向、超過量、ageを作り、return/rangeの現在innovationと同時shock indicatorを合わせて12列とした。timestamp gapが1本を超えたらイベント状態をresetする。

生OHLC価格水準、未来足、targetは特徴へ使わない。価格10倍scale不変、未来側OHLC改変が過去特徴へ不影響、完全無変動履歴が有限0、shock直後response式、gap reset、保存artifactからのlatest推論をテストした。baseline 38列へ12列を追加した全50特徴である。

source 6,025,170行、usable 5,737,928行から、baselineとtimestamp、decision/target timestamp、target、foldが全件一致する2,183,717 OOS行を生成した。HGB 200 iteration、31 leaves、learning rate 0.05、min leaf 100、L2 1、expanding train最大750,000行、Platt、seed 42、通常・方向維持ともbaseline 75% + candidate 25%を固定した。損失倍率は標準1.0のみである。

## 単体と通常方向blend

| period | baseline | Shock単体 | 通常25% blend |
|---|---:|---:|---:|
| development | 50.93738% | 50.93828% | 50.95776% |
| confirmation | 50.60001% | 50.66942% | 50.61659% |
| all | 50.80695% | 50.83433% | 50.82586% |

単体はconfirmationで+586件、exact McNemar p=0.04389だったが、developmentは+12件、allは+598件でもp=0.2010だった。accuracy 5/7foldに対しBrier/log loss改善は2/7foldだけで、developmentとallのproper scoreを悪化させたため単体採用しない。

通常25% blendはdevelopment +273件、confirmation +140件、all +413件で、accuracy、Brier、log lossを全て7/7fold改善した。確率品質の補完性は明確で、UTC日paired bootstrap 20,000回でもBrier/log lossはdevelopment、confirmation、allの全てで改善側だった。

一方、accuracy差95%区間はdevelopment -0.00675〜+0.04760pt、confirmation -0.01657〜+0.04918pt、all -0.00205〜+0.03956ptで全て0を跨いだ。全期間McNemarもp=0.07944で、方向精度改善は確定しない。

既存Distribution Shift通常25% blendはdevelopment 50.97359%、confirmation 50.64431%、all 50.84629%で、Shockの50.95776%、50.61659%、50.82586%を全て上回った。accuracy・selection scoreは6/7fold、Brier/log lossは3期間の日次bootstrapでDistribution Shift優位だった。Shockのaccuracy差は日次区間で未確定でも、同じstability/proper-score役割に劣る候補を追加しない。

## 方向維持confidence 0.51

development固定grid `0.51, 0.515, 0.525, 0.535, 0.55` のcoverage-aware score最大は0.51だった。

| period | baseline accuracy / coverage / score | Shock accuracy / coverage / score |
|---|---:|---:|
| development | 51.5790% / 44.0150% / 0.009629 | 51.6024% / 43.9340% / 0.009775 |
| confirmation | 51.8000% / 24.2132% / 0.007791 | 51.8226% / 23.8513% / 0.007835 |
| all | 51.6359% / 36.3595% / 0.009202 | 51.6585% / 36.1699% / 0.009312 |

Brier/log lossは7/7foldかつ3期間の日次bootstrapでbaselineを改善した。しかしaccuracy、Wilson下限、selection scoreの95%区間はdevelopment、confirmation、allの全てで0を跨ぎ、coverageはall -0.1896ptだった。点scoreだけではconfidence候補へ昇格できない。

Distribution Shift 0.51との直接比較では、Shockはall coverage 36.170%対35.613%と+0.557pt広いが、accuracy 51.6585%対51.7536%、score 0.009312対0.009802だった。Distribution Shiftはaccuracy 6/7fold、score 7/7foldで勝ち、all日次95%区間はaccuracy +0.05288〜+0.13675pt、score +0.000238〜+0.000740、Brier/log lossも改善側だった。developmentも全指標で優位、confirmation点scoreも上回るため、ultra-broad coverage役割を置換しない。

## 高信頼度と局所品質

Shock confidenceは閾値とともに概ねaccuracyが上がるが、上側tailは過信かつ疎い。all 0.55以上は17,586件、coverage 0.8053%、accuracy 54.7765%、mean confidence 56.2100%で、1.4335pt過信した。0.575以上は2,326件・56.7498%だが全件developmentで、confirmationは0件だった。

confirmation 0.55以上は156件・54.4872%で、6セル全てedge未確認だった。固定0.51の6セルでもdown-low 3,172件・50.3783%、up-low 8,414件・50.6418%はWilson edge未確認で、計4/6セルだけが通った。確認結果を見た後のsubgroup除外ruleは作らず、fair odds・policyには使わない。

latest artifactは2026-06-01 04:59 UTC判定でdown、probability down 50.7587%を返し、保存・推論経路を確認した。empirical odds calibrationなしのため `odds_valid=false` である。

## 判断

Shock / Recovery Stateの単体、通常方向blend、方向維持0.51を再現専用として棄却する。イベント後responseはbaselineのproper scoreを一貫して改善したため有効な加工だが、方向accuracyのbootstrap gateを通らず、既存Distribution Shiftが方向・confidenceの同じ役割を上回る。高信頼度tailと固定セルの局所整合も不十分で、候補数を増やす品質上の根拠がない。

64本reference、2σ、16本追跡、response cap 3、12特徴、HGB parameter、25% weight、0.51を同じ履歴で再探索しない。Path/Distribution Shift方向候補、Transition guard/Disagreement/Distribution Shift confidence候補を維持し、config、registry、authoritative方向/confidence、fair odds、paper/live policyを変更しない。

## 成果物

- OOS: `experiments/next_bar/walk_forward_shock_recovery_state_m1_fixed_001`
- direction blend: `experiments/next_bar/shock_recovery_state_m1_blend_fixed_001`
- direction-preserving confidence: `experiments/next_bar/shock_recovery_state_m1_confidence_fixed_001`
- candidate analysis: `experiments/next_bar/shock_recovery_state_m1_candidate_analysis.json`
- baseline bootstraps: `experiments/next_bar/shock_recovery_state_vs_baseline_m1_direction_bootstrap.json`, `experiments/next_bar/shock_recovery_state_vs_baseline_m1_confidence_051_bootstrap.json`
- Distribution Shift direction comparison: `experiments/next_bar/distribution_shift_vs_shock_recovery_state_m1_direction_analysis.json`, `experiments/next_bar/distribution_shift_vs_shock_recovery_state_m1_direction_bootstrap.json`
- Distribution Shift confidence comparison: `experiments/next_bar/distribution_shift_051_vs_shock_recovery_state_051_m1_analysis.json`, `experiments/next_bar/distribution_shift_051_vs_shock_recovery_state_051_m1_bootstrap.json`
- reliability/subgroups: `experiments/next_bar/shock_recovery_state_m1_confidence_subgroups.json`
- latest reproducibility check: `experiments/next_bar/shock_recovery_state_m1_latest_prediction.json`
