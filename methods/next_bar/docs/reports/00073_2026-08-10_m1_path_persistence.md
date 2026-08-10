# 00073 M1 Path Persistence

日時: 2026-08-10 21:17 JST

## 目的

M1 × M5/M15 as-of metaが増分edgeを作れなかったため、別時間足の確率を再混合せず、M1自身の完成済み価格経路を定常量へ加工する。M15で定義済みのPath Persistence 14特徴を変更せずM1へ移植し、次足方向とconfidence順位付けを改善できるか検証した。

## 固定仕様

5/10/20/50本の符号付きefficiency、10/20本return自己相関、方向転換率、2/5/10本集約returnの50本variance ratio、up/down継続率、最大20本の符号付きstreakをbaseline 38特徴へ追加した。raw価格水準とvolumeは使わない。

HGB、Platt、expanding 7fold、各fold学習上限75万行、baseline 75% + Path 25%を固定した。developmentは2020〜2023、confirmationは2024〜2026途中。損失倍率は標準1.0のみである。

## 行整合の品質修正

最初の学習では旧baseline成果物2,183,780行に対し候補が2,183,693行となり、ensembleの厳密整列gateが停止した。完全無変動または片方向だけの窓で効率比、自己相関、variance ratio、継続率が0/0となっていたため、「持続性の証拠なし」を意味する0へ定義した。flat系列の全14列が有限0になる回帰テストを追加した。

さらに旧baseline artifactと現コードに前処理版差があったため、旧成果物とのintersection比較を行わず、現コードでbaselineも再学習した。baselineとPathはいずれもsource 6,025,170行、usable 5,737,928行、最終OOS 2,183,717行で完全一致した。以後の結果はこの同一母集団だけを使う。

## 単体と固定25%方向blend

| period | baseline accuracy | Path single accuracy | 25% blend accuracy | blend純改善 / p |
|---|---:|---:|---:|---:|
| development | 50.93738% | 50.93611% | 50.97889% | +556 / 0.0039 |
| confirmation | 50.60001% | 50.63625% | 50.64573% | +386 / 0.0079 |
| all | 50.80695% | 50.82018% | 50.85009% | +942 / 0.000093 |

Path単体は全体+289件、p=0.548、accuracy 4/7foldに留まり、Brier/log lossも悪化したため置換しない。一方、通常25% blendはbaselineの誤り29,469件を直し、正解28,527件を壊して純+942件。accuracyは7/7fold、Brier/log lossは各6/7、ECEは5/7fold改善した。

| metric | baseline all | 25% blend all | delta |
|---|---:|---:|---:|
| accuracy | 50.80695% | 50.85009% | +0.04314pt |
| Brier | 0.24986888 | 0.24986479 | -0.00000409 |
| log loss | 0.69288487 | 0.69287667 | -0.00000821 |
| ECE | 0.20289% | 0.15077% | -0.05212pt |

## 日次block bootstrap

UTC日をblockにしたpaired bootstrap 20,000回でもaccuracy差は改善側だった。

| period | accuracy差 | 95% CI | 候補優位確率 |
|---|---:|---:|---:|
| development | +0.04151pt | +0.01355〜+0.06937pt | 99.80% |
| confirmation | +0.04572pt | +0.01139〜+0.08061pt | 99.50% |
| all | +0.04314pt | +0.02161〜+0.06478pt | 100.00% |

全期間Brier差の95%区間は-0.00000592〜-0.00000227、log lossは-0.00001189〜-0.00000454で、ともに改善側だった。confirmationのproper score差は点推定では改善したが区間が0を跨ぐため、fresh期間ではaccuracyと併せて監視する。

## Confidence用途

baseline方向を維持した25% confidence blendはdevelopment gridで0.51を選んだ。developmentはaccuracy 51.5790%→51.6516%、coverage 44.015%→43.747%、score 0.009629→0.010077と改善した。

しかしconfirmationはaccuracy 51.8000%→51.7078%、coverage 24.213%→23.943%、score 0.007791→0.007290へすべて悪化し、0.51のaccuracy/scoreは2024、2025、2026途中の3/3foldで負けた。高信頼度の見かけの改善は開発期間に限定されるため、confidence・odds用途には採用しない。

## 判断

固定25% M1 Path Persistenceを方向専用のparallel forward candidateとして採用し、`m1_path_persistence_direction_candidate_v1.json` に固定する。全7fold、開発/確認、日次blockで方向edgeが再現したため、今回の検証で初めてM1に明確な加工特徴候補が得られた。

現行のauthoritative方向、confidence、fair odds、paper/live policyは置換しない。完全未使用期間でbaseline以上のaccuracy、Brier、log lossを同時に確認するまでparallel shadowとする。特徴窓、subset、blend weight、confidence閾値を同じ履歴で再探索しない。

## 成果物

- current baseline: `experiments/next_bar/walk_forward_baseline_m1_current_001`
- Path OOS: `experiments/next_bar/walk_forward_path_persistence_m1_finite_001`
- direction blend: `experiments/next_bar/path_persistence_m1_blend_current_001`
- rejected confidence blend: `experiments/next_bar/path_persistence_m1_confidence_blend_current_001`
- analysis: `experiments/next_bar/path_persistence_m1_candidate_analysis.json`
- daily bootstrap: `experiments/next_bar/path_persistence_m1_direction_bootstrap.json`
