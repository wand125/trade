# 00077 M1 Volatility State

日時: 2026-08-10 23:48 JST

## 目的

価格履歴の数値をそのまま渡さず、完成足間の変動状態とその遷移へ加工する。M15で事前固定した11特徴、HGB/Platt、25% weightを結果確認後に変更せずM1へ移植し、Path Persistence、Session Relative、TCNと独立比較した。

## 固定仕様と品質監査

5/20本volatilityのvol-of-volと加速度、20本rangeの変動係数・自己相関・中央値乖離、5/50本圧縮率、20本bipower jump比、Parkinson/Garman–Klass分散とclose分散のbalanceを使う。raw価格水準、volume、未来足、targetは特徴に使わない。

完全無変動履歴では比率と対称変化の0/0を「変動状態の証拠なし」の0へ定義した。11列すべてが有限0になる既存回帰テスト、価格scale不変、未来側OHLC改変不影響、artifact/latest経路を確認した。

source 6,025,170行、usable 5,737,928行、baselineと同じtimestamp/targetのOOS 2,183,717行に完全整列した。

## 単体と固定25%方向blend

| period | baseline accuracy | Volatility single | 25% blend | blend純改善 / p |
|---|---:|---:|---:|---:|
| development | 50.93738% | 50.94813% | 50.96336% | +348 / 0.1287 |
| confirmation | 50.60001% | 50.54611% | 50.64905% | +414 / 0.0297 |
| all | 50.80695% | 50.79271% | 50.84184% | +762 / 0.0104 |

単体は全体-311件、accuracy 4/7、Brier/log loss各2/7で棄却する。通常blendはaccuracy 6/7、Brier/log loss 7/7、ECE 5/7foldを改善した。全体Brierは0.24986888→0.24985785、log loss 0.69288487→0.69286274、ECE 0.20289%→0.14680%。

UTC日paired bootstrap 20,000回のcandidate−baseline accuracy差95%区間はdevelopment -0.0087〜+0.0606ptで0を跨ぐが、confirmation +0.0040〜+0.0928pt、all +0.0078〜+0.0618ptで改善側だった。Brier/log loss差はdevelopment、confirmation、allの全てで改善側だった。

## 既存方向候補との比較

| period | Volatility | Path | Session |
|---|---:|---:|---:|
| development accuracy | 50.96336% | 50.97889% | 50.96269% |
| confirmation accuracy | 50.64905% | 50.64573% | 50.63862% |
| all accuracy | 50.84184% | 50.85009% | 50.83740% |

Pathにはaccuracy 4/7fold勝つが、全体で-0.00824pt。Volatility−Path accuracy差の日次95%区間は-0.0361〜+0.0194ptで未確定のため、Pathをaccuracy point championとして維持する。一方VolatilityのBrier/log lossは全期間区間でPathより改善側だった。

Sessionには全体+0.00444pt、confirmation +0.01042ptだが、年別は3/7対4/7。accuracy、Brier、log lossの直接差区間は全て0を跨ぐ。したがって履歴上の微差で片方を棄却せず、Volatilityをaccuracyとproper scoreを同時に改善したbalanced direction candidate、Sessionをproper-score重視specialistとして役割分離する。Path/Volatility/Sessionをstack、union、再weightしない。

## Confidence用途

development目的関数は0.515を選び、scoreを0.009587→0.010221へ改善した。confirmationでもaccuracy 52.509%→52.741%、score 0.006837→0.007366へ上がり、accuracy/score 7/7、Brier/log loss 6/7fold改善した。

ただし同じ固定0.515のTCNと直接比較すると、Volatilityはconfirmation coverageが+1.520pt広い一方、accuracyが-0.300pt、全期間-0.095ptだった。UTC日bootstrapのVolatility−TCN accuracy差95%区間はconfirmation -0.516〜-0.082pt、all -0.172〜-0.017ptでVolatility劣位。selection score差区間は両期間とも0を跨ぎ、全期間Brier/log lossもTCNが改善側だった。TCNはaccuracy 6/7、score 5/7fold勝つため、Volatility confidenceは重複候補として不採用とする。

## 判断

`m1_volatility_state_direction_candidate_v1.json` にbalanced secondary方向候補として固定する。M1方向候補の役割はPath＝accuracy champion、Volatility＝balanced secondary、Session＝probability-quality specialist、Trend＝tertiary structural challengerとする。

authoritative方向、confidence、fair odds、paper/live policyは変更しない。完全未使用期間でbaseline以上のaccuracy、Brier、log lossを同時に要求し、rolling window、特徴subset、25% weightを再探索しない。confidenceには使わず、TCN 0.515をselective候補として維持する。

## 成果物

- Volatility OOS: `experiments/next_bar/walk_forward_volatility_state_m1_finite_001`
- direction blend: `experiments/next_bar/volatility_state_m1_blend_current_001`
- rejected confidence blend: `experiments/next_bar/volatility_state_m1_confidence_blend_current_001`
- candidate analysis: `experiments/next_bar/volatility_state_m1_candidate_analysis.json`
- baseline bootstrap: `experiments/next_bar/volatility_state_m1_direction_bootstrap.json`
- Path comparison/bootstrap: `experiments/next_bar/volatility_state_vs_path_m1_direction_analysis.json`, `experiments/next_bar/volatility_state_vs_path_m1_direction_bootstrap.json`
- Session comparison/bootstrap: `experiments/next_bar/volatility_state_vs_session_m1_direction_analysis.json`, `experiments/next_bar/volatility_state_vs_session_m1_direction_bootstrap.json`
- TCN confidence comparison/bootstrap: `experiments/next_bar/volatility_state_vs_tcn_m1_confidence_0515_analysis.json`, `experiments/next_bar/volatility_state_vs_tcn_m1_confidence_0515_bootstrap.json`
