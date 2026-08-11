# 00131 M5 × M1 Cross-timeframe Meta Confidence

日時: 2026-08-11 23:08 JST

## 結論

M5 baseline確率と同一decision timestampのM1 baseline確率から、chronological logistic meta modelでM5 confidenceを補正した。方向を変えない重み0.50、confidence 0.51はM5 baselineより全6 foldでaccuracyが高く、全期間accuracy差の日次bootstrap区間も正だった。しかし既存M5 Intrabar Profile 0.515より全6 foldでaccuracyが低く、selection scoreとproper scoreも置換水準に達しない。M5 Directional Follow-through 0.55にも高信頼度用途で負ける。

この手法は再現専用として保存し、config、registry、authoritative direction/confidence、fair odds、paper/live policyを変更しない。損失倍率は標準1.0だけを使った。

## 入力監査

履歴値をそのまま使わない方針に従い、モデル入力は既に時系列外で生成されたM5/M1確率、confidence、方向一致などの加工値だけとした。raw M1の `volume` も候補として先に監査したが、全6,025,170行が0だった。情報量がないため特徴へ追加していない。

対象はM5のtest2021〜test2026_partial、364,774行。各test foldのmeta modelは、それ以前のOOS予測だけでfitした。最初のtest2021はtest2020だけをfitに使い、未来foldは使用していない。M1 contextはM5と完全に同じdecision timestampだけをjoinし、as-of補間は使っていない。正則化はC=0.10、seed 42で固定した。

## 方向変更の監査

通常の25% blendはbaseline方向を変更し、全期間accuracyを51.3252%から51.2841%へ0.0411pt下げた。baseline誤りを2,590件修正する一方で2,740件を壊し、正確二項検定p=0.04125、改善fold 0/6だった。この結果から、meta確率をconfidence強度だけに使う `--preserve-target-direction` を実装した。

`apply_meta_blend` は共通の方向維持blend関数を使い、方向境界を跨がない。出力には `meta_preserve_target_direction` を記録する。比較スクリプトはmanifest記載のprediction filenameも読めるよう共通registry loaderへ統一した。

## 固定weight感度

weightは0.125、0.25、0.50の3点だけを固定比較した。閾値はdevelopment=test2021〜2023のselection scoreだけで選び、confirmation=test2024〜2026_partialは選択に使っていない。

| weight | development選択閾値 | development score | confirmation score | 判定 |
|---:|---:|---:|---:|---|
| 0.125 | 0.53 | 0.015203 | 0.008958 | baseline development 0.015333未満 |
| 0.25 | 0.51 | 0.015213 | 0.010960 | 改善 |
| 0.50 | 0.51 | 0.015221 | 0.011279 | development首位として固定 |

0.50と0.25の差は小さいが、選択規則どおりconfirmationを見ずに0.50を採用して後続比較した。これ以上のweight・C・閾値探索は行わない。

## M5 baselineとの固定比較

| 期間 | 手法 | rows | coverage | accuracy | selection score |
|---|---|---:|---:|---:|---:|
| development | baseline 0.51 | 137,334 | 69.7463% | 52.0425% | 0.014850 |
| development | meta 0.50 / 0.51 | 132,633 | 67.3589% | 52.1235% | 0.015221 |
| confirmation | baseline 0.51 | 91,400 | 54.4472% | 51.8031% | 0.010914 |
| confirmation | meta 0.50 / 0.51 | 87,630 | 52.2014% | 51.8920% | 0.011279 |
| all | baseline 0.51 | 228,734 | 62.7057% | 51.9468% | 0.013795 |
| all | meta 0.50 / 0.51 | 220,263 | 60.3834% | 52.0314% | 0.014164 |

metaはaccuracy 6/6 fold、selection score 5/6 foldでbaselineを上回った。全期間の日次block bootstrap 20,000回ではaccuracy差+0.0846pt、95%区間+0.0213〜+0.1476ptだった。一方、selection score差+0.000370の区間は−0.000126〜+0.000861で0を跨いだ。developmentとconfirmationを別々にしたaccuracy差の区間も僅かに0を跨ぐ。

全行proper scoreはbaselineから、Brier 0.24968542→0.24968885、log loss 0.69251715→0.69252421と僅かに悪化し、ECEだけ0.00458649→0.00361653へ改善した。fold改善はBrier 2/6、log loss 2/6、ECE 3/6で、odds品質の昇格根拠にはならない。

## 既存championとの比較

既存M5 Profile 0.515は全期間172,400行、coverage 47.2621%、accuracy 52.3637%、score 0.014629だった。metaはcoverageを13.1213pt広げる一方、accuracyが0.3323pt低く、scoreも0.000465低い。accuracy差の20,000回bootstrap区間は−0.4481〜−0.2174pt、Brier/log lossもProfile優位の区間が0を跨がなかった。metaのaccuracy勝数は0/6 foldだった。

confidence 0.55ではmetaが13,366行、55.2746%、score 0.008480。既存M5 Follow-throughは16,122行、55.6693%、score 0.010304で、selection scoreは6/6 foldでFollow-throughが勝った。高信頼度laneにも新しい役割はない。

## 採否

- meta 0.50 / confidence 0.51はbaselineへの加工感度として有効だが、Profile broad confidenceを置換しない。
- meta 0.55はFollow-through high-confidence shadowを置換しない。
- meta確率はfair oddsとして認可しない。latest inference、運用config、registry entryを作らない。
- M5/M1、C=0.10、方向維持、weight 0.50、0.51を再探索せず、必要時の再現条件としてだけ保存する。

## 検証成果物

Windows canonical環境に、通常blend、方向維持weight 0.125/0.25/0.50、整列baseline/Profile/Follow-through subset、固定比較、20,000回bootstrapを保存した。大きなprediction/model artifactは母艦へ戻さない。実装と文書だけをGit管理する。

meta/ensemble/worker policyの対象30件を通した。MacとWindows/WSLの全体testはどちらも `1378 passed, 1 deselected, 83 subtests passed` だった。deselectは既知の非next-bar docs時刻testである。変更ファイルとWindows側の新規M5成果物に対する口座・login・password/token/secret・private key形式のscanは0件だった。
