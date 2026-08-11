# 00117 M30 Session Relative Fixed Transfer

日時: 2026-08-11 15:36 JST

## 目的

M15 confidence shadowとM1方向候補で使ったSession RelativeをM30へ固定移植した。同じ曜日×UTC時刻における通常状態からの乖離は、Haarの短期経路やPressureの足内形状と異なる周期的regime表現であるため、方向、confidence、既存候補との固定多様化に増分があるかを検証した。

## 固定仕様と品質

現在足を除く曜日×UTC時刻groupの直近32観測、最低12観測から、return/body z-score、absolute-return/range ratio、方向biasの5列を作る。標準偏差・平均絶対値が0のとき、0/0は乖離なしの0、非ゼロ/0は固定clip端へ定義する。M30では各groupが週2観測なので、概ね16週の同時刻履歴である。生OHLC価格水準、volume、未来足、targetは特徴へ使わない。

HGB 200 iteration、learning rate 0.05、31 leaves、min leaf 100、L2 1、expanding、uniform sample、全教師、Platt、標準損失1.0を固定した。prior本数、最低本数、5特徴、parameter、25% weightをM1/M15から変更せず、M30履歴で再探索していない。test2020〜test2026途中の固定7foldで検証した。

Session groupの最低12観測を満たすまでのtest2020先頭44行だけが欠けるため、比較はbaselineと既存候補をtimestamp/targetで厳密inner整列した71,216行で行った。confirmation行数は変わらない。最終fold artifactから2026-06-01 04:30 UTCを再推論し、up、probability up 53.4828%を確認した。経験的オッズ検証はないため `odds_valid=false` である。

## 方向

| model | development accuracy | confirmation accuracy | all accuracy | all Brier | all log loss | all ECE |
|---|---:|---:|---:|---:|---:|---:|
| aligned baseline | 52.0009% | 51.5202% | 51.8142% | 0.249495019 | 0.692136795 | 0.1541% |
| Session単体 | 51.8609% | 51.7986% | 51.8367% | 0.249443115 | 0.692031536 | 0.2382% |
| baseline 75% + Session 25% | 51.9389% | 51.5708% | 51.7959% | 0.249453653 | 0.692053399 | 0.1558% |

Session単体はbaseline比development -61件、confirmation +77件、all +16件でaccuracy 4/7fold、Brier/log loss 6/7foldだった。通常25% blendは-27/+14/-13件、accuracy 3/7foldであり、方向候補にはしない。

現行Haar入り方向co-challengerとの直接比較では、Session単体がdevelopment 51.8609%対52.1961%、all 51.8367%対51.9939%で下回り、accuracy 2/7対5/7foldだった。confirmationだけは51.7986%対51.6756%だったが、全体の方向品質を上積みしないため固定平均も行わない。

## confidence 0.52

方向維持blendのdevelopment固定gridは0.52を選んだ。

| period | aligned baseline coverage / accuracy / score | Session coverage / accuracy / score |
|---|---:|---:|
| development | 41.2444% / 53.4179% / 0.017262 | 40.9413% / 53.5778% / 0.018205 |
| confirmation | 31.2679% / 53.6363% / 0.014449 | 31.2100% / 53.9210% / 0.016022 |
| all | 37.3694% / 53.4889% / 0.017662 | 37.1616% / 53.6898% / 0.018828 |

baseline比でaccuracyとselection scoreは開発・確認・全期間の点値を改善した。UTC日bootstrap 20,000回ではdevelopment/allのBrier・log loss改善を支持したが、all accuracy差+0.2009ptの95%区間は-0.0109〜+0.4130pt、score差+0.001166は-0.000124〜+0.002461で0を跨いだ。coverage差-0.2078ptは-0.3633〜-0.0507ptで低下側だった。

既存Pressure 0.52との同一行直接比較では、Sessionはconfirmationでaccuracy 53.9210%対53.7345%、score 0.016022対0.014787と上回った。一方developmentは53.5778%対53.7785%、allは53.6898%対53.7641%、年別accuracy/scoreは3/7対4/7でPressureが上である。直接bootstrapでもSessionのall accuracy差-0.0744pt、score差-0.000243の区間は0を跨ぎ、確定したのはcoverage +0.6782ptだけだった。Brier/log lossにもPressureへの増分はない。

0.55ではSessionはall 4,621件、coverage 6.4887%、accuracy 55.0097%、score 0.009098だった。既存Pressure + AR shadowは4,410件、6.1924%、56.1678%、0.011692でaccuracy/score 6/7fold勝ちとなり、Sessionをtail用途にも使わない。

## 固定confidence多様化

PressureとSessionの方向維持確率を固定50/50平均した。0.52ではall accuracy 53.6442%、score 0.018406でPressureの53.7641%、0.019071を下回り、accuracy/score 1/7foldだった。0.55もall accuracy 55.9211%、score 0.011073でPressure + ARの56.1678%、0.011692を下回り、2/7foldだった。Brier/log loss点値の僅かな平滑化改善だけでは採用しない。

## 判断

Session単体、通常25%方向blend、方向維持0.52、Pressureとの固定50/50 confidence平均をすべて再現専用とする。periodic regime表現はbaselineのproper score改善に有効だったが、現行Haar入り方向候補、Pressure 0.52、Pressure + AR 0.55の役割を上積みしない。window、group粒度、最低本数、clip、weight、thresholdを同じ履歴へ合わせて再探索せず、config、registry、authoritative方向/confidence、fair odds、adoption/paper/live policyを変更しない。

## 成果物

- Session OOS: `experiments/next_bar/walk_forward_session_relative_m30_fixed_001`
- aligned baseline: `experiments/next_bar/baseline_m30_session_relative_aligned_001`
- normal/confidence blends: `experiments/next_bar/session_relative_m30_*_fixed_001`
- candidate分析: `experiments/next_bar/session_relative_m30_candidate_analysis.json`
- 既存候補との直接比較: `experiments/next_bar/session_relative_vs_*_m30_*`
- confidence bootstrap: `experiments/next_bar/session_relative_vs_*_m30_confidence_bootstrap_052.json`
- rejected fixed confidence average: `experiments/next_bar/pressure_session_relative_equal_m30_confidence_fixed_001`
- latest artifact check: `experiments/next_bar/session_relative_m30_latest_prediction.json`
