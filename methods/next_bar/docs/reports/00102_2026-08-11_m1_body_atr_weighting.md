# 00102 M1 Body/ATR Sample Weighting

日時: 2026-08-11 10:41 JST

## 目的

M1 Directional-Clarity weightingの改善が教師品質weight一般に再現するか切り分けるため、M15で固定済みのBody/ATR sample weightingをM1へ無変更移植した。Clarityは次足実体を次足自身のrangeで割る相対的な足形明瞭度、Body/ATRは次足実体を判定時点ATRで割る絶対的な値動き強度を教師重みへ使う。

## 固定仕様と品質

trainで解決済みの次足について `strength = abs(next_bar_body) / (decision_close * atr_ratio_20)`、`raw_weight = 0.5 + clip(strength, 0, 1.5)` とし、sampled train内の平均1へ正規化する。raw weightは0.5〜2.0、最大比4倍で、全train行と方向0/1教師を維持する。

次足bodyはtrain sample weightだけに使い、入力特徴、calibration、test、latest推論へ渡さない。ATRはdecisionまでに確定した入力から作る。各foldのtrainより後のlabelは参照しない。重み範囲・平均1・欠損guard・HGB training pipelineを固定テストで確認した。

M15仕様からweight式、clip、HGB parameter、blend weight、confidence gridを変更していない。baseline 38特徴、HGB 200 iteration、31 leaves、learning rate 0.05、min leaf 100、L2 1、expanding train最大750,000行、Platt、seed 42、baseline 75% + candidate 25%とした。損失倍率は標準1.0のみである。

source 6,025,170行、usable 5,737,928行から、baselineとtimestamp、decision/target timestamp、target、foldが一致する2,183,717 OOS行を生成した。

## 単体と通常方向blend

| period | baseline | Body/ATR単体 | 通常25% blend |
|---|---:|---:|---:|
| development | 50.93738% | 50.86026% | 50.97344% |
| confirmation | 50.60001% | 50.57928% | 50.62725% |
| all | 50.80695% | 50.75163% | 50.83960% |

単体はbaseline比development -1,033件、confirmation -175件、all -1,208件、exact paired p=0.02528である。accuracyは2/7fold、Brier/log lossは0/7foldしか改善せず、M15と同じく単体方向モデルを棄却する。

通常25% blendはdevelopment +483件、confirmation +230件、all +713件で、accuracy 7/7、Brier/log loss 6/7foldを改善した。exact paired pはdevelopment 0.01957、confirmation 0.14550、all 0.00609である。UTC日paired bootstrap 20,000回はdevelopment/allのaccuracy・proper score改善を支持し、all accuracy差95%区間は+0.00908〜+0.05615ptだった。confirmationの方向・proper score区間は0を跨いだ。

Body/ATR weightingにもbaselineとの補完性はあるが、Directional-Clarity 25% blendはall accuracyで+155件、Brier/log lossも有意に良く、年別accuracy 4/7対3/7だった。accuracy差自体は日次区間で未確定でも、同じ教師重みカテゴリではClarityの点推定と確率品質が全期間上回る。

Distribution ShiftはBody/ATRよりall +146件、accuracy 5/7foldで、Brier/log lossのall差も明確に優位だった。accuracy差区間は0を跨いでも、既存stability/probability-quality役割をBody/ATRへ置換しない。

## 方向維持confidence 0.515

development固定grid `0.51, 0.515, 0.525, 0.535, 0.55` のcoverage-aware score最大は0.515だった。

| period | baseline accuracy / coverage / score | Body/ATR accuracy / coverage / score |
|---|---:|---:|
| development | 51.9505% / 28.6110% / 0.009587 | 52.0044% / 27.1713% / 0.009602 |
| confirmation | 52.5091% / 9.9208% / 0.006837 | 52.8199% / 9.0836% / 0.007434 |
| all | 52.0507% / 21.3852% / 0.008820 | 52.1463% / 20.1785% / 0.008979 |

accuracyとscoreは6/7fold、proper scoreは5/7fold改善した。日次bootstrapはconfirmation/allのaccuracy、confirmationのscore、all proper score改善を支持した。all score差とdevelopment accuracy/scoreは0を跨いだ。M15で見つかったconfidence ranking情報はM1でも一部再現した。

しかし同じ0.515の5-model Disagreementはall 52.3090% / coverage 19.8959% / score 0.009636で、Body/ATRよりcoverageが0.2825pt狭い代わりにaccuracy +0.1626pt、score +0.000658だった。Disagreementはaccuracy 5/7、score 7/7fold勝ち、all日次95%区間はaccuracy +0.08338〜+0.24098pt、score +0.000306〜+0.001007、Brier/log lossも3期間で優位だった。Body/ATRをM1 confidence候補へ追加しない。

## 高信頼度と局所品質

Body/ATR confidenceのall 0.55以上は15,252件、coverage 0.6984%、accuracy 55.1862%、mean confidence 56.2159%で1.0297pt過信した。0.575以上は2,033件、accuracy 57.4029%、mean confidence 58.7581%だが全件developmentで、confirmationは0件だった。

confirmation 0.55以上は165件、accuracy 55.7576%でも固定6セル全てWilson edge未確認だった。固定0.515ではdown-high、up-high、up-normalだけedge確認済みで、down-low 705件・49.9291%、down-normal 2,507件・50.9374%、up-low 1,767件・50.7640%は未確認だった。6セル中3セルしか通らず、subgroup除外ruleは作らない。

latest artifactは2026-06-01 04:59 UTC判定でup、probability up 50.0736%を返し、保存・推論経路を確認した。empirical odds calibrationなしのため `odds_valid=false` である。

## 判断

M1 Body/ATR weighted単体、通常25%方向blend、方向維持0.515を再現専用として棄却する。通常blendはbaseline方向を7/7fold改善し、confidenceも確認期間の精度・scoreを改善したため、教師強度weightの情報は保存する。しかし同カテゴリのDirectional-Clarityが方向accuracy・proper scoreで上回り、方向はDistribution Shift、confidenceはDisagreementがさらに強い。独立したforward役割がない。

M15のBody/ATR 0.54 forward candidateは時間足独立なので変更しない。M1についてweight offset、clip、非線形化、blend weight、0.515以外の閾値を同じ履歴で再探索しない。config、registry、authoritative方向/confidence、fair odds、paper/live policyを変更しない。

## 成果物

- OOS: `experiments/next_bar/walk_forward_body_atr_weighted_m1_fixed_001`
- direction blend: `experiments/next_bar/body_atr_weighted_m1_blend_fixed_001`
- direction-preserving confidence: `experiments/next_bar/body_atr_weighted_m1_confidence_fixed_001`
- candidate analysis: `experiments/next_bar/body_atr_weighted_m1_candidate_analysis.json`
- baseline direction/confidence bootstraps: `experiments/next_bar/body_atr_weighted_vs_baseline_m1_direction_bootstrap.json`, `experiments/next_bar/body_atr_weighted_vs_baseline_m1_confidence_0515_bootstrap.json`
- Clarity direction comparison: `experiments/next_bar/directional_clarity_vs_body_atr_weighted_m1_direction_analysis.json`, `experiments/next_bar/directional_clarity_vs_body_atr_weighted_m1_direction_bootstrap.json`
- Distribution Shift direction comparison: `experiments/next_bar/distribution_shift_vs_body_atr_weighted_m1_direction_analysis.json`, `experiments/next_bar/distribution_shift_vs_body_atr_weighted_m1_direction_bootstrap.json`
- Disagreement confidence comparison: `experiments/next_bar/disagreement_0515_vs_body_atr_weighted_0515_m1_analysis.json`, `experiments/next_bar/disagreement_0515_vs_body_atr_weighted_0515_m1_bootstrap.json`
- reliability/subgroups: `experiments/next_bar/body_atr_weighted_m1_confidence_subgroups.json`
- latest reproducibility check: `experiments/next_bar/body_atr_weighted_m1_latest_prediction.json`
