# 00078 M1 Haar Multiscale

日時: 2026-08-11 00:13 JST

## 目的

価格履歴をそのまま並べず、直近経路の加速・減速・反転を複数scaleの前半対後半差へ圧縮する。M15で事前固定した12特徴、HGB/Platt、25% weightを結果確認後に変更せずM1へ移植し、既存M1方向候補と独立比較した。

## 固定仕様と品質監査

4/8/16/32本の各窓を前半と後半へ二分し、窓内volatilityで標準化したreturn差、総absolute returnで標準化した変動量差、方向平均差を各scaleで作る。raw価格水準、volume、未来足、targetは特徴へ使わない。

完全無変動窓ではreturn差とabsolute-return差が0/0だったため、「加速・構成変化なし」の0へ定義した。warmupの欠損は維持する。flat系列で12列が有限0、価格10倍で数値誤差内一致、未来側OHLC改変不影響、artifact/latest経路を回帰テストした。

source 6,025,170行、usable 5,737,928行。baselineと同じtimestamp/targetのOOS 2,183,717行に完全整列した。

## 単体と固定25%方向blend

| period | baseline accuracy | Haar single | 25% blend | blend純改善 / p |
|---|---:|---:|---:|---:|
| development | 50.93738% | 50.92148% | 50.96911% | +425 / 0.0204 |
| confirmation | 50.60001% | 50.67688% | 50.63163% | +267 / 0.0668 |
| all | 50.80695% | 50.82692% | 50.83864% | +692 / 0.00307 |

単体はconfirmation精度を上げるがdevelopmentで-213件、Brier/log loss各3/7foldのため単独採用しない。通常blendはaccuracy、Brier、log lossを7/7fold、ECEを5/7fold改善した。全体Brierは0.24986888→0.24986430、log loss 0.69288487→0.69287568、ECE 0.20289%→0.16197%。

UTC日paired bootstrap 20,000回のHaar−baseline accuracy差95%区間はdevelopment +0.0051〜+0.0584pt、confirmation -0.0022〜+0.0653pt、all +0.0108〜+0.0527pt。confirmation精度だけ僅かに0を跨ぐが、Brier/log loss差はdevelopment、confirmation、allの全てで改善側だった。

## 既存方向候補との比較

| period | Haar | Path | Volatility | Session | Trend |
|---|---:|---:|---:|---:|---:|
| development accuracy | 50.96911% | 50.97889% | 50.96336% | 50.96269% | 50.96433% |
| confirmation accuracy | 50.63163% | 50.64573% | 50.64905% | 50.63862% | 50.63744% |
| all accuracy | 50.83864% | 50.85009% | 50.84184% | 50.83740% | 50.83795% |

HaarはPathにaccuracy 2/7、Volatilityに3/7、SessionとTrendに各4/7fold。全ての直接accuracy差の日次95%区間は0を跨ぐ。Pathをaccuracy champion、Volatilityをbalanced secondaryとして維持する。

Haarの全期間Brier/log lossはVolatilityとSessionより明確に悪く、Sessionのprobability-quality specialistも置換しない。Trendとの差は全期間accuracy +15件、Brier/log lossはほぼ同値で、全直接差区間が0を跨ぐ。履歴内の僅差でTrendを棄却せず、Haarをtertiary multiscale、Trendをtertiary structural challengerとして別々に固定する。候補をstack、union、再weightしない。

## Confidence用途

development目的関数は0.515を選び、scoreを0.009587→0.009790へ改善した。confirmationでもaccuracy 52.509%→52.583%、score 0.006837→0.007010へ改善したが、accuracyは5/7、scoreは4/7foldに留まる。

同じ0.515のTCNと直接比較すると、Haarはcoverageが広い一方、confirmation accuracy 52.583%対53.041%、score 0.007010対0.007506。accuracy・scoreともTCNに0/7対7/7で負け、全期間Brier/log lossもTCNが良い。Haar confidenceは不採用とし、TCN 0.515をselective confidence候補として維持する。

## 判断

`m1_haar_multiscale_direction_challenger_v1.json` にtertiary multiscale方向challengerとして固定する。authoritative方向、confidence、fair odds、paper/live policyは変更しない。

完全未使用期間でbaseline以上のaccuracy、Brier、log lossを同時に要求する。窓、系列、特徴subset、25% weightを再探索せず、既存候補と合成しない。confidence 0.515は使わない。

## 成果物

- Haar OOS: `experiments/next_bar/walk_forward_haar_multiscale_m1_finite_001`
- direction blend: `experiments/next_bar/haar_multiscale_m1_blend_current_001`
- rejected confidence blend: `experiments/next_bar/haar_multiscale_m1_confidence_blend_current_001`
- candidate analysis: `experiments/next_bar/haar_multiscale_m1_candidate_analysis.json`
- baseline bootstrap: `experiments/next_bar/haar_multiscale_m1_direction_bootstrap.json`
- Path comparison/bootstrap: `experiments/next_bar/haar_vs_path_m1_direction_analysis.json`, `experiments/next_bar/haar_vs_path_m1_direction_bootstrap.json`
- Volatility comparison/bootstrap: `experiments/next_bar/haar_vs_volatility_state_m1_direction_analysis.json`, `experiments/next_bar/haar_vs_volatility_state_m1_direction_bootstrap.json`
- Session comparison/bootstrap: `experiments/next_bar/haar_vs_session_m1_direction_analysis.json`, `experiments/next_bar/haar_vs_session_m1_direction_bootstrap.json`
- Trend comparison/bootstrap: `experiments/next_bar/haar_vs_trend_m1_direction_analysis.json`, `experiments/next_bar/haar_vs_trend_m1_direction_bootstrap.json`
- TCN confidence comparison: `experiments/next_bar/haar_vs_tcn_m1_confidence_0515_analysis.json`
