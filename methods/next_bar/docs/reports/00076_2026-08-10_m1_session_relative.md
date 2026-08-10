# 00076 M1 Session Relative

日時: 2026-08-10 23:27 JST

## 目的

Path/Trendの価格経路とTCNのsequence学習とは独立に、現在M1足がその曜日×UTC時の局所通常状態からどれだけ外れたかを加工する。M15で事前固定した5特徴、HGB/Platt、25% weightを結果確認後に変更せずM1へ移植した。

## 固定仕様とM1での意味

同じUTC曜日×時に属する現在以外の直近32観測、最低12観測からreturn/body z-score、absolute return/range ratio、過去方向biasを作る。zは[-10,10]、ratioは[0,10]。raw価格水準、volume、未来足、targetは使わない。

M15では32観測がおよそ8週間に相当するが、M1では同じ1時間内の直近分足が大半を占める。このためM1版は厳密なminute-of-hour季節性ではなく、曜日×時で区切った局所session regimeからの乖離として解釈する。group/windowをM1結果へ合わせて変更しない。

完全無変動履歴でprior std/meanが0になる場合、0/0を乖離なしの0、非ゼロ/0を固定clip端へ定義した。flat系列で十分なprior supportがある全5列が有限0になる回帰テストを追加した。未来側OHLC改変不影響、価格水準排除、artifact/latest経路の既存テストも維持した。

source 6,025,170行のうちsession固有warmupを含むfeature除外は36,750行、usable 5,736,657行。baselineよりusableは1,271行少ないが、評価開始前だけの差であり、OOSは同じtimestamp/targetの2,183,717行に完全整列した。

## 単体と固定25%方向blend

| period | baseline accuracy | Session single | 25% blend | blend純改善 / p |
|---|---:|---:|---:|---:|
| development | 50.93738% | 50.97105% | 50.96269% | +339 / 0.1475 |
| confirmation | 50.60001% | 50.62228% | 50.63862% | +326 / 0.0841 |
| all | 50.80695% | 50.83621% | 50.83740% | +665 / 0.0268 |

単体は全体+639件だがaccuracy 4/7、Brier/log loss各4/7で、単独採用には弱い。通常blendはaccuracy、Brier、log lossを7/7fold、ECEを5/7fold改善した。全体Brierは0.24986888→0.24985615、log loss 0.69288487→0.69285933、ECE 0.20289%→0.15423%。

UTC日paired bootstrap 20,000回のcandidate−baseline accuracy差95%区間はdevelopment -0.0100〜+0.0610pt、confirmation -0.0041〜+0.0815ptで僅かに0を跨ぎ、全期間は+0.0034〜+0.0575ptで改善側だった。Brier/log loss差はdevelopment、confirmation、allの全てで改善側だった。

## 既存方向候補との比較

| period | Session | Path | Trend |
|---|---:|---:|---:|
| development accuracy | 50.96269% | 50.97889% | 50.96433% |
| confirmation accuracy | 50.63862% | 50.64573% | 50.63744% |
| all accuracy | 50.83740% | 50.85009% | 50.83795% |

PathはSessionにaccuracy 5/7fold勝ち、全体+0.01268pt。日次accuracy差区間は0を跨ぐがpoint championはPathを維持する。一方SessionはPathよりBrier/log lossがdevelopment、confirmation、allの全区間で有意に良かった。

Trendとは全体12件差だけで、Sessionが年別4/7勝った。accuracy差区間は0を跨ぐが、SessionのBrier/log lossは3期間全てで明確に良い。このためSessionをprobability-quality secondary、Trendをtertiary challengerへ整理する。3候補をunion、stack、再weightしない。

## Confidence用途

development目的関数は0.51を選び、scoreを0.009629→0.010275へ改善した。confirmationではaccuracy 51.80000%→51.80276%だがcoverage低下によりscoreが0.007791→0.007708へ下がったため、Session confidenceは不採用。

各候補のdevelopment固定policyを直接比較すると、Session 0.51はTCN 0.515よりconfirmation coverageが15.75pt高く、accuracyは1.239pt低い。selection scoreはSessionが+0.000203高いが日次95%区間は-0.000820〜+0.001256で未確定だった。同じ閾値baselineを改善するTCN 0.515を高精度selective confidence候補として維持する。

この比較のため、paired bootstrapへfirst/second別固定閾値を追加した。閾値は各候補のdevelopmentで既に選ばれた値だけを渡し、confirmationを使った再探索には使わない。

## 判断

`m1_session_relative_direction_candidate_v1.json` にprobability-quality secondary方向候補として固定する。Pathをaccuracy champion、Sessionをproper-score重視secondary、Trendをtertiary challengerとする。

authoritative方向、confidence、fair odds、paper/live policyは変更しない。完全未使用期間でbaseline以上のaccuracy、Brier、log lossを同時に要求する。Sessionのgroup/window/clip/weightを履歴内再探索せず、Path/Trend/TCNとstackしない。

## 成果物

- Session OOS: `experiments/next_bar/walk_forward_session_relative_m1_finite_001`
- direction blend: `experiments/next_bar/session_relative_m1_blend_current_001`
- rejected confidence blend: `experiments/next_bar/session_relative_m1_confidence_blend_current_001`
- candidate analysis: `experiments/next_bar/session_relative_m1_candidate_analysis.json`
- baseline bootstrap: `experiments/next_bar/session_relative_m1_direction_bootstrap.json`
- Path direct comparison/bootstrap: `experiments/next_bar/session_vs_path_m1_direction_analysis.json`, `experiments/next_bar/session_vs_path_m1_direction_bootstrap.json`
- Trend direct comparison/bootstrap: `experiments/next_bar/session_vs_trend_m1_direction_analysis.json`, `experiments/next_bar/session_vs_trend_m1_direction_bootstrap.json`
- TCN policy bootstrap: `experiments/next_bar/session_051_vs_tcn_0515_m1_confidence_bootstrap.json`
