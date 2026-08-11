# 00116 M30 Path Persistence Fixed Transfer

日時: 2026-08-11 15:17 JST

## 目的

M30 Haar Multiscaleで完成足経路の加工が方向精度を改善したため、同じ価格履歴を別の定常統計へ圧縮するPath Persistenceを固定移植した。Haarが窓の前半・後半の加速差を見るのに対し、Pathは経路効率、自己相関、反転率、variance ratio、方向持続率、streakを使い、Haar入り方向候補または既存Pressure confidenceへ増分があるかを検証した。

## 固定仕様と品質

5/10/20/50本の符号付きefficiency、10/20本のreturn autocorrelation・方向転換率、50本窓の2/5/10本variance ratio、20本のup/down persistence、最大20本の符号付きstreakからなる固定14列をbaselineへ追加した。M30では約2.5〜25時間の経路統計に対応する。完全無変動・片方向窓の0/0は持続性の証拠なしの0とし、生OHLC価格水準、volume、未来足、targetは特徴へ使わない。

HGB 200 iteration、learning rate 0.05、31 leaves、min leaf 100、L2 1、expanding、uniform sample、全教師、Platt、標準損失1.0を固定した。M1/M15からwindow、14列、parameter、25% weightを変更せず、M30履歴で探索していない。test2020〜test2026途中の固定7fold、71,260 OOS行でbaselineとtimestamp/targetを完全整列した。

最終fold artifactから2026-06-01 04:30 UTCを再推論し、up、probability up 52.6457%を確認した。経験的オッズ検証はないため `odds_valid=false` である。

## 方向

| model | development accuracy | confirmation accuracy | all accuracy | all Brier | all log loss | all ECE |
|---|---:|---:|---:|---:|---:|---:|
| HGB baseline | 51.98972% | 51.52019% | 51.80747% | 0.249497879 | 0.692142533 | 0.16084% |
| Path単体 | 51.60669% | 51.54550% | 51.58294% | 0.249457078 | 0.692060252 | 0.39332% |
| baseline 75% + Path 25% | 52.07230% | 51.53465% | 51.86360% | 0.249456388 | 0.692059035 | 0.06807% |

Path単体はbaseline比development -167件、confirmation +7件、all -160件、accuracy 1/7foldで方向用途を棄却する。Brier/log lossは5/7fold改善したが、方向誤りを確率品質だけで正当化しない。

通常25% blendはdevelopment +36件、confirmation +4件、all +40件、accuracy 3/7、Brier/log loss 6/7foldだった。all精度は現行Haar入りco-challenger 51.9927%より92件低く、既存方向役割への増分がない。Path通常blendをHaar候補へ追加平均する根拠もないため実施せず、方向candidate/configを発行しない。

## confidence 0.52

方向維持blendのdevelopment固定gridは0.52を選んだ。

| period | baseline coverage / accuracy / score | Path coverage / accuracy / score |
|---|---:|---:|
| development | 41.2441% / 53.4145% / 0.017242 | 40.9184% / 53.5706% / 0.018155 |
| confirmation | 31.2679% / 53.6363% / 0.014449 | 30.0965% / 53.8739% / 0.015369 |
| all | 37.3716% / 53.4865% / 0.017649 | 36.7177% / 53.6671% / 0.018557 |

Pathはbaselineに対して開発・確認のaccuracyとselection scoreを上げ、Brier/log loss 6/7foldを改善した。UTC日bootstrap 20,000回でもBrier/log loss差は開発・確認・全期間で改善側だった。一方、all accuracy差+0.1806ptの95%区間は-0.0347〜+0.3971pt、score差+0.000908は-0.000401〜+0.002215で未確定、coverage差-0.6539ptは-0.8239〜-0.4847ptで確定した。

既存Pressure 0.52との比較ではPathがaccuracy/score 4/7foldだったが、期間で優位が反転した。developmentはPath 53.5706%・0.018155に対しPressure 53.7689%・0.019210、confirmationはPath 53.8739%・0.015369に対しPressure 53.7345%・0.014787だった。全期間はPath 53.6671%・0.018557、Pressure 53.7577%・0.019034でPressureが上である。日次bootstrapはconfirmationのPath優位、allのPressure優位ともaccuracy/score区間が0を跨いだ。

## 固定confidence多様化

PressureとPathの方向維持確率を固定50/50平均した。0.52ではall accuracy 53.6321%、score 0.018253でPressureより低く、accuracy/score 2/7foldだった。0.55もall accuracy 56.0147%、score 0.011215で既存Pressure + AR shadowの56.1423%、0.011629を下回り、3/7foldだった。confirmationもPath平均は55.6069%・0.004029に対しPressure + ARは56.0088%・0.004997である。固定平均を採用しない。

## 判断

Path単体、通常25%方向blend、方向維持0.52、Pressureとの固定50/50 confidence平均をすべて再現専用とする。window、feature、HGB parameter、blend weight、thresholdを同じM30履歴へ合わせて再探索しない。config、registry、authoritative方向/confidence、Haar入り方向co-challenger、Pressure 0.52、Pressure + AR 0.55 shadow、fair odds、adoption/paper/live policyは変更しない。

Path 0.52がbaselineのproper scoreを強く改善したことは、経路持続性が確率平滑化には有効というlearning-flow sensitivityとして保存する。ただしcoverage-aware objectiveの優位は未確定で、既存Pressureへの明確な増分がないため、新しい候補を増やさない。

## 成果物

- Path OOS: `experiments/next_bar/walk_forward_path_persistence_m30_fixed_001`
- normal/confidence blends: `experiments/next_bar/path_persistence_m30_*_fixed_001`
- candidate分析: `experiments/next_bar/path_persistence_m30_candidate_analysis.json`
- Pressure比較: `experiments/next_bar/path_persistence_vs_pressure_m30_confidence_fixed_052.json`
- confidence bootstraps: `experiments/next_bar/path_persistence_vs_*_m30_confidence_052_bootstrap.json`
- rejected fixed confidence average: `experiments/next_bar/pressure_path_persistence_equal_m30_confidence_fixed_001`, `experiments/next_bar/pressure_path_equal_vs_*`
- latest artifact check: `experiments/next_bar/path_persistence_m30_latest_prediction.json`
