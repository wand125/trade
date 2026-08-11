# 00118 M30 Volatility State Fixed Transfer

日時: 2026-08-11 15:55 JST

## 目的

価格履歴をそのまま使わず、変動の不安定性、加速、圧縮、jump、OHLC分散構成へ加工するVolatility StateをM30へ固定移植した。M1では通常25%方向blendがaccuracy 6/7、Brier/log loss 7/7foldを改善したため、M30のHaar入り方向候補とPressure系confidenceへ独立した増分があるかを検証した。

## 固定仕様と品質

5/20本volatilityの20/50本vol-of-volと3/5本加速度、20本rangeの変動係数・自己相関・中央値乖離、5/50本圧縮率、20本bipower jump比、Parkinson/Garman–Klass分散とclose realized varianceのbalanceからなる固定11列をbaselineへ追加した。完全無変動履歴の0/0は変動状態の証拠なしの0とする。生OHLC価格水準、volume、未来足、targetは特徴へ使わない。

HGB 200 iteration、learning rate 0.05、31 leaves、min leaf 100、L2 1、expanding、uniform sample、全教師、Platt、標準損失1.0を固定した。M1/M15からwindow、11列、parameter、25% weightを変更せず、M30履歴で探索していない。test2020〜test2026途中の固定7fold、71,260 OOS行でbaseline・既存候補とtimestamp/targetを完全整列した。

最終fold artifactから2026-06-01 04:30 UTCを再推論し、up、probability up 52.6613%を確認した。経験的オッズ検証はないため `odds_valid=false` である。

## 方向

| model | development accuracy | confirmation accuracy | all accuracy | all Brier | all log loss | all ECE |
|---|---:|---:|---:|---:|---:|---:|
| HGB baseline | 51.9897% | 51.5202% | 51.8075% | 0.249497879 | 0.692142533 | 0.1608% |
| Volatility単体 | 51.8911% | 51.5744% | 51.7682% | 0.249518507 | 0.692183251 | 0.1170% |
| baseline 75% + Volatility 25% | 52.0264% | 51.4407% | 51.7990% | 0.249474349 | 0.692094922 | 0.1104% |

Volatility単体はbaseline比development -43件、confirmation +15件、all -28件、accuracy/Brier/log loss各3/7foldで方向用途を棄却する。通常25% blendはdevelopment +16件、confirmation -22件、all -6件、accuracy 2/7foldだった。全期間Brier/log lossは改善したが、確認期間方向精度を下げた。

通常blend−baselineの日次bootstrap 20,000回では、all accuracy差-0.0084ptの95%区間が-0.1384〜+0.1211ptで0を跨いだ。all Brier差は-0.00004585〜-0.00000108、log loss差は-0.00009248〜-0.00000246で改善を支持したが、development・confirmation単独のproper score区間は0を跨いだ。確率平滑化だけを方向採用根拠にしない。

現行Haar入り方向co-challengerとの直接比較では、通常blendがdevelopment 52.0264%対52.1939%、confirmation 51.4407%対51.6756%、all 51.7990%対51.9927%で下回り、accuracy 1/7対6/7foldだった。方向多様化の固定平均は行わない。

## confidence

development gridの候補selection score最大は0.515だったが、baselineよりaccuracy・coverage・scoreをすべて下げた。

| period | baseline coverage / accuracy / score | Volatility coverage / accuracy / score |
|---|---:|---:|
| development | 52.9829% / 53.1126% / 0.017968 | 51.4048% / 53.0118% / 0.016905 |
| confirmation | 43.3028% / 53.2977% / 0.015815 | 43.1763% / 53.3199% / 0.015929 |
| all | 49.2254% / 53.1758% / 0.018616 | 48.2108% / 53.1189% / 0.017990 |

confirmationの僅かな点改善はdevelopmentで再現せず、年別accuracy/scoreは3/7対4/7だった。日次bootstrapでもall accuracy差-0.0569pt、score差-0.000626の区間は0を跨ぎ、coverage差-1.0146ptの95%区間-1.1929〜-0.8344ptだけが低下側で確定した。Brier/log lossは全期間で改善したが、lane objectiveを補わない。

既存Pressure 0.52との比較ではVolatility 0.515がcoverage 48.2108%対36.4861%と広い一方、accuracy 53.1189%対53.7577%、score 0.017990対0.019034だった。accuracyは0/7対7/7、scoreは3/7対4/7であり、broad confidence役割へ追加しない。

0.55ではVolatilityが4,300件、coverage 6.0342%、accuracy 55.2791%、score 0.009307だった。Pressure + AR shadowは4,412件、6.1914%、56.1423%、0.011629で、accuracy 5/7、score 6/7fold勝ちとなった。tail用途にも使わない。

## 固定confidence多様化

PressureとVolatility confidenceを固定50/50平均した。0.52ではall accuracy 53.5486%、score 0.017699でPressureの53.7577%、0.019034を下回り、accuracy/score 2/7foldだった。

0.55では固定平均が年別accuracy 5/7となったが、all accuracy 56.1102%、coverage 5.9599%、score 0.011261でPressure + ARの56.1423%、6.1914%、0.011629をすべて下回った。日次bootstrapのaccuracy差95%区間は-0.5186〜+0.4405pt、score差は-0.001564〜+0.000790で0を跨ぎ、coverage差-0.2913〜-0.1718ptだけが低下側で確定した。固定平均を採用しない。

## 判断

Volatility単体、通常25%方向blend、方向維持0.515/0.55、Pressureとの固定50/50 confidence平均をすべて再現専用とする。M30でも変動状態はaggregate proper scoreの平滑化には有効だったが、方向精度とcoverage-aware objectiveを上積みしない。window、jump定義、OHLC variance estimator、feature subset、weight、thresholdを同じ履歴へ合わせて再探索しない。

config、registry、authoritative方向/confidence、Haar入り方向co-challenger、Pressure 0.52、Pressure + AR 0.55 shadow、fair odds、adoption/paper/live policyは変更しない。

## 成果物

- Volatility OOS: `experiments/next_bar/walk_forward_volatility_state_m30_fixed_001`
- normal/confidence blends: `experiments/next_bar/volatility_state_m30_*_fixed_001`
- candidate分析: `experiments/next_bar/volatility_state_m30_candidate_analysis.json`
- 既存候補との直接比較: `experiments/next_bar/volatility_state_vs_*_m30_*`
- direction/confidence bootstrap: `experiments/next_bar/volatility_state_vs_baseline_m30_*_bootstrap*`
- rejected fixed confidence average: `experiments/next_bar/pressure_volatility_state_equal_m30_confidence_fixed_001`
- fixed average comparison/bootstrap: `experiments/next_bar/pressure_volatility_equal_vs_*`
- latest artifact check: `experiments/next_bar/volatility_state_m30_latest_prediction.json`
