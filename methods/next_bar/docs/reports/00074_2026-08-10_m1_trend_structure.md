# 00074 M1 Trend Structure

日時: 2026-08-10 21:43 JST

## 目的

M1 Path Persistence方向候補の窓やweightを再探索せず、別系統の加工指標がM1でも独立edgeを持つか検証した。M15で事前定義済みのTrend Structure 11特徴を変更せずM1へ移植する。

## 固定仕様と品質修正

Wilder型DI/ADX、ATR正規化MACD、短長ATR/volatility比、upside/downside realized-volatility balance、方向entropyをbaseline 38特徴へ追加した。raw価格水準とvolumeは使わない。HGB、Platt、expanding 7fold、学習上限75万行、baseline 75% + Trend 25%を固定した。損失倍率は標準1.0のみである。

学習前に完全無変動窓のDI、ADX、MACD/ATR、volatility比などの0/0を「トレンド／変動の証拠なし」の0へ定義した。flat系列で11列すべて有限0になる回帰テストを追加した。現コードのbaselineとTrendはいずれもsource 6,025,170行、usable 5,737,928行、OOS 2,183,717行で完全一致した。

## 単体と固定25%方向blend

| period | baseline accuracy | Trend single accuracy | 25% blend accuracy | blend純改善 / p |
|---|---:|---:|---:|---:|
| development | 50.93738% | 50.93611% | 50.96433% | +361 / 0.0608 |
| confirmation | 50.60001% | 50.64573% | 50.63744% | +316 / 0.0336 |
| all | 50.80695% | 50.82385% | 50.83795% | +677 / 0.0053 |

Trend単体は全体+369件だがp=0.445、accuracy 4/7、Brier/log loss各2/7しか改善せず不採用。固定25% blendはbaselineの誤り29,761件を直し、正解29,084件を壊した。accuracyは6/7、Brier/log loss各6/7、ECE 5/7fold改善した。

| metric | baseline all | Trend 25% all | delta |
|---|---:|---:|---:|
| accuracy | 50.80695% | 50.83795% | +0.03100pt |
| Brier | 0.24986888 | 0.24986430 | -0.00000458 |
| log loss | 0.69288487 | 0.69287566 | -0.00000921 |
| ECE | 0.20289% | 0.16341% | -0.03948pt |

## 日次block bootstrap

UTC日paired bootstrap 20,000回のbaseline比accuracy差は、development +0.02695ptの95%区間が-0.00185〜+0.05532ptで僅かに0を跨いだ。confirmationは+0.03743pt、+0.00313〜+0.07194pt、全期間は+0.03100pt、+0.00892〜+0.05299ptで改善側だった。

全期間Brier差の95%区間は-0.00000642〜-0.00000273、log lossは-0.00001289〜-0.00000549で改善側。confirmation proper score差は点推定改善だが区間は0を跨ぐ。

## Path Persistenceとの直接比較

| period | Trend 25% accuracy | Path 25% accuracy | Trend−Path |
|---|---:|---:|---:|
| development | 50.96433% | 50.97889% | -0.01456pt |
| confirmation | 50.63744% | 50.64573% | -0.00829pt |
| all | 50.83795% | 50.85009% | -0.01214pt |

Pathがaccuracyを3期間すべて上回り、直接年別勝数もPath 4/7、Trend 3/7だった。全期間Trend−Path accuracyの日次95%区間は-0.03418〜+0.00977ptで0を跨ぐ。TrendはBrier/log lossが僅かに良いが、その直接差の区間も0を跨いだ。統計的置換確定ではないため、point値とfold安定性が高いPathをM1方向championとして維持する。

## Confidence用途

development gridは0.515を選び、scoreを0.009587から0.010026へ改善した。confirmationもaggregate scoreは0.006837から0.006866へ僅かに上がったが、年別accuracy/score改善は2024だけで、2025と2026途中は悪化した。確認1/3foldではconfidence edgeとして不十分なため採用しない。

## 判断

Trend Structure 25%はbaselineに対する方向edgeがconfirmation、全期間bootstrap、accuracy 6/7foldで再現したため、独立したM1方向secondary challengerとして `m1_trend_structure_direction_challenger_v1.json` に固定する。

ただしPath Persistenceを置換せず、両候補を同じ履歴でunion、平均、再weightしない。authoritative方向、confidence、odds、paper/live policyは変更しない。完全未使用期間ではPathとTrendを並行評価し、各々baseline以上のaccuracy、Brier、log lossを要求する。

## 成果物

- Trend OOS: `experiments/next_bar/walk_forward_trend_structure_m1_finite_001`
- direction blend: `experiments/next_bar/trend_structure_m1_blend_current_001`
- rejected confidence blend: `experiments/next_bar/trend_structure_m1_confidence_blend_current_001`
- candidate analysis: `experiments/next_bar/trend_structure_m1_candidate_analysis.json`
- baseline bootstrap: `experiments/next_bar/trend_structure_m1_direction_bootstrap.json`
- Path direct comparison: `experiments/next_bar/trend_vs_path_m1_direction_analysis.json`
- Path direct bootstrap: `experiments/next_bar/trend_vs_path_m1_direction_bootstrap.json`
