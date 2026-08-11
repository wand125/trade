# 00103 M1 Body/ATR Upper-Half Teacher Filter

日時: 2026-08-11 11:03 JST

## 目的

教師品質を連続weightにするM1 Directional-Clarity / Body/ATR検証に続き、M15で固定済みの `body_atr_upper_half` をM1へ無変更移植した。小さな次足を弱く扱うのではなく、各foldのtrain内で次足実体/ATRが上位半分の明瞭な足だけを方向教師に残すhard filterが、M1の方向精度とconfidence rankingを改善するか確認した。

## 固定仕様と品質

各sampled trainで、解決済み次足について `next_bar_body_atr = abs(next close - next open) / decision ATR` を計算し、train内中央値以上の行だけでHGBを学習する。閾値はfoldごとのtrainだけから求め、calibration/testは全行を保持する。次足実体は教師選択だけに使い、入力特徴、校正、test、latest推論へ渡さない。

M15仕様から保持率、木、sample、blend weight、confidence gridを変更していない。baseline 38特徴、HGB 200 iteration、31 leaves、learning rate 0.05、min leaf 100、L2 1、expanding train最大750,000行、Platt、seed 42、baseline 75% + candidate 25%である。損失倍率は標準1.0のみとした。

train内中央値だけを使うことと後続期間label非参照を固定テストで確認した。source 6,025,170行、usable 5,737,928行から、baselineとtimestamp、decision/target timestamp、target、foldが一致する2,183,717 OOS行を生成した。

## 単体と通常方向blend

| period | baseline | filter単体 | 通常25% blend |
|---|---:|---:|---:|
| development | 50.93738% | 50.88139% | 50.97523% |
| confirmation | 50.60001% | 50.59551% | 50.60107% |
| all | 50.80695% | 50.77086% | 50.83058% |

単体はbaseline比development -750件、confirmation -38件、all -788件で、accuracy 3/7、Brier/log loss 2/7foldだった。all exact paired p=0.20571であり、方向モデルとして棄却する。

通常25% blendはdevelopment +507件、confirmation +9件、all +516件、accuracy/Brier/log loss 6/7foldだった。exact paired pはdevelopment 0.03681、confirmation 0.96743、all 0.09844である。baseline比UTC日paired bootstrap 20,000回ではdevelopment accuracy差95%区間が+0.00157〜+0.07449ptで改善を支持したが、confirmationとall accuracyは0を跨いだ。Brier/log lossはdevelopmentとallで改善側、confirmationは未確定だった。

したがってclear-body教師選択にもbaselineとの補完性はあるが、完全期間の方向精度改善は未確定である。既存Distribution Shift 25%はall 50.84629%で本方式50.83058%を343件上回り、accuracy/selection scoreを6/7foldで上回った。直接UTC日bootstrapのall差は0を跨いだものの、confirmationのBrier/log lossはDistribution Shift優位が確定し、同じstability/proper-score役割を置換しない。

## 方向維持confidence 0.51

development固定grid `0.51, 0.515, 0.525, 0.535, 0.55` のcoverage-aware score最大は0.51だった。

| period | baseline accuracy / coverage / score | filter accuracy / coverage / score |
|---|---:|---:|
| development | 51.5790% / 44.0150% / 0.009629 | 51.6314% / 43.1943% / 0.009876 |
| confirmation | 51.8000% / 24.2132% / 0.007791 | 51.8134% / 23.1592% / 0.007661 |
| all | 51.6359% / 36.3595% / 0.009202 | 51.6774% / 35.4486% / 0.009324 |

accuracyとselection scoreは5/7fold、Brier/log lossは6/7fold改善した。baselineとの日次bootstrapはdevelopment accuracyとall proper scoreを支持したが、development score、confirmationのaccuracy/score、all accuracy/scoreは0を跨いだ。確認期間では精度が僅かに上がる一方、coverage低下により目的関数が反転した。

既存Distribution Shift 0.51はall 51.7536% / coverage 35.6128% / score 0.009802で、本方式よりaccuracy +0.0762pt、coverage +0.1642pt、score +0.000478だった。accuracy 6/7、score 7/7foldで上回り、all日次95%区間もaccuracy +0.03118〜+0.12142pt、coverage +0.09751〜+0.23151pt、score +0.000210〜+0.000747と3指標すべてDistribution Shift優位を支持した。M1 confidence候補へ追加しない。

## 高信頼度と局所品質

全期間0.55以上は14,337件、coverage 0.6565%、accuracy 55.2835%、mean confidence 56.1281%だった。0.575以上は1,592件、accuracy 58.4799%、mean confidence 58.6289%であり、集計上はconfidence上昇と精度上昇が対応した。

しかし0.55以上はdevelopmentで14,294件・55.3169%に対し、confirmationでは43件・44.1860%しかなくedge未確認だった。0.575以上は全1,592件がdevelopmentで、confirmationは0件である。固定0.51のconfirmation 6セルは4/6セルだけedge確認済みで、down-low 2,656件・50.9413%とup-low 8,415件・50.8616%はWilson下限が50%を下回った。高信頼度tailと局所edgeは将来期間へ移っておらず、fair oddsに使える安定性はない。

latest artifactは2026-06-01 04:59 UTC判定でdown、probability down 50.8043%を返した。0.51選択閾値未満で、empirical odds calibrationもないため `odds_valid=false` である。

## 判断

M1 Body/ATR upper-half単体、通常25%方向blend、方向維持0.51を再現専用として棄却する。hard teacher filterは通常blendのproper scoreとdevelopment精度を改善し、教師品質加工が有効になり得ることは再確認できた。一方、confirmation方向改善は9件に留まり、confidence目的関数も反転した。方向・confidenceとも既存Distribution Shiftが直接比較で上回り、高信頼度tailも確認期間へ移らないため独立したforward役割がない。

M15のBody/ATR upper-half confidence 0.525 forward candidateは時間足独立なので変更しない。M1について保持率、中央値定義、ATR、木、blend weight、0.51以外の閾値を同じ履歴で再探索しない。config、registry、authoritative方向/confidence、fair odds、paper/live policyを変更しない。

## 成果物

- OOS: `experiments/next_bar/walk_forward_body_atr_upper_half_m1_fixed_001`
- direction blend: `experiments/next_bar/body_atr_upper_half_m1_blend_fixed_001`
- direction-preserving confidence: `experiments/next_bar/body_atr_upper_half_m1_confidence_fixed_001`
- candidate analysis: `experiments/next_bar/body_atr_upper_half_m1_candidate_analysis.json`
- baseline direction/confidence bootstraps: `experiments/next_bar/body_atr_upper_half_vs_baseline_m1_direction_bootstrap.json`, `experiments/next_bar/body_atr_upper_half_vs_baseline_m1_confidence_051_bootstrap.json`
- Distribution Shift direction comparison: `experiments/next_bar/distribution_shift_vs_body_atr_upper_half_m1_direction_analysis.json`, `experiments/next_bar/distribution_shift_vs_body_atr_upper_half_m1_direction_bootstrap.json`
- Distribution Shift confidence comparison: `experiments/next_bar/distribution_shift_051_vs_body_atr_upper_half_051_m1_analysis.json`, `experiments/next_bar/distribution_shift_051_vs_body_atr_upper_half_051_m1_bootstrap.json`
- reliability/subgroups: `experiments/next_bar/body_atr_upper_half_m1_confidence_subgroups.json`
- latest reproducibility check: `experiments/next_bar/body_atr_upper_half_m1_latest_prediction.json`
