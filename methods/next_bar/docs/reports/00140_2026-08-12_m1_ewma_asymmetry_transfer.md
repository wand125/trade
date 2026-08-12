# 00140 M1 EWMA Asymmetry Transfer

日時: 2026-08-12 12:47 JST

## 結論

M5でparallel broad confidence候補になった `ewma_asymmetry_state` 12特徴を、定義・半減期・HGB parameter・Platt校正・25% blend・閾値gridを変えずM1へ固定移植した。Windows/WSL2 canonical環境でbaseline、Distribution Shift、Path Persistenceを同じ2,183,717 OOS行・7foldから全て再学習し、旧Mac artifactを混ぜていない。

方向維持confidence 0.51はbaselineへaccuracy・selection scoreを7/7fold改善し、20,000回日次bootstrapでもdevelopment/confirmation/all accuracy、development/all score、all Brier/log lossが改善側だった。加工情報はM1でも有効である。

しかし現行Distribution Shift 0.51にはall accuracy -0.05302pt、selection score -0.000287、Brier +0.00000309、log loss +0.00000620で、4指標すべての日次区間がEWMA劣後側だった。固定50/50 confidence平均もShiftを改善しない。単体方向はbaselineより+621件でもaccuracy区間が0を跨ぎ、confirmation proper scoreを有意に悪化させ、Path/Shift方向候補の3指標を同時に超えない。M1では再現専用とし、新しいconfig・registry候補を発行しない。

EWMAの全時間足固定移植はこれで完了した。M5 0.515だけをparallel broad候補として維持し、M1/M15/M30は各時間足のDistribution Shift候補を超えないため再現専用とする。authoritative方向/confidence、fair odds、paper/live売買policyは変更しない。損失倍率は標準1.0だけを使った。

## 固定条件

- 半減期4/16/64のprior-volatility標準化return innovationとdrift/volatility
- 4対16、16対64のvolatility balance
- 半減期16/64のupside/downside energy balanceとleverage moment
- baseline 38列 + EWMA 12列 = 50加工特徴
- M1、test2020〜test2026_partial、2,183,717 OOS行
- HGB 200 iteration、learning rate 0.05、31 leaves、min leaf 100、L2 1
- expanding、最大750,000 train行、Platt、uniform weighting、全教師、seed 42
- baseline 75% + candidate 25%、方向維持confidenceはbaseline方向を固定
- developmentだけで0.51/0.515/0.525/0.535/0.55を評価
- 主目的関数 `sqrt(coverage) * (Wilson95Lower(accuracy) - 0.50)`

M5/M15/M30試験後に特徴式、clip、half-life、weightを変更していない。既存M1の厳密式、[-1,1]境界、scale不変、未来不参照、gap reset、flat全0、raw OHLC水準排除、artifact latestの回帰testをそのまま使った。全候補はfold、decision timestamp、targetが完全一致した。

## 方向結果

| model | development accuracy | confirmation accuracy | all accuracy | all Brier | all log loss |
|---|---:|---:|---:|---:|---:|
| baseline | 50.90043% | 50.61233% | 50.78904% | 0.24987395 | 0.69289503 |
| EWMA単体 | 50.92603% | 50.64526% | 50.81748% | 0.24987219 | 0.69289150 |
| baseline 75% + EWMA 25% | 50.92155% | 50.62050% | 50.80516% | 0.24986592 | 0.69287891 |
| baseline 75% + Shift 25% | 50.92357% | 50.61576% | 50.80457% | 0.24986241 | 0.69287188 |
| baseline 75% + Path 25% | 50.93163% | 50.62085% | 50.81148% | 0.24986747 | 0.69288204 |

EWMA単体はbaseline比development +343件、confirmation +278件、all +621件、accuracy 4/7fold、McNemar exact p=0.23702だった。all accuracy差+0.02844ptのbootstrap区間は-0.01633〜+0.07379ptで未確定である。confirmationではBrier差+0.00000852、log loss差+0.00001708の区間が悪化側だった。方向accuracy点改善だけで3指標gateを通らない。

通常25% blendは+283/+69/+352件、p=0.17910、accuracy 4/7fold、Brier/log loss 6/7fold改善した。all Brier/log loss差はbootstrapでも改善側だが、accuracy差+0.01612ptの区間-0.00673〜+0.03884ptは0を跨いだ。

Windowsで再構築したPath 25%はEWMA 25%にall +138件、accuracy 5/7fold。EWMA単体はPathよりall +131件・4/7foldだが、accuracy差区間は0を跨ぎ、confirmation Brier/log lossはPathより有意に悪かった。Shift 25%に対してもEWMA単体はall +282件でもaccuracy差未確定で、all Brier/log lossは有意に悪い。既存方向候補を置換・追加しない。

## 方向維持confidence 0.51

development目的関数最大は、既存Shiftと同じ0.51だった。

| 期間 | model | coverage | accuracy | selection score |
|---|---|---:|---:|---:|
| development | baseline | 44.24940% | 51.58754% | 0.009714 |
| development | EWMA | 43.88180% | 51.63571% | 0.009989 |
| confirmation | baseline | 25.02052% | 51.64723% | 0.007173 |
| confirmation | EWMA | 24.08844% | 51.74023% | 0.007475 |
| all | baseline | 36.81539% | 51.60322% | 0.009065 |
| all | EWMA | 36.22956% | 51.66258% | 0.009344 |

EWMAはbaselineへaccuracy・score各7/7、Brier/log loss/ECE各6/7fold改善した。日次bootstrapのaccuracy差はdevelopment +0.04818pt、95%区間+0.00811〜+0.08820pt、confirmation +0.09300pt、+0.01483〜+0.17172pt、all +0.05936pt、+0.02357〜+0.09535ptで全区分が改善側だった。selection score差はdevelopment +0.000275とall +0.000280が改善側、confirmation +0.000302は0跨ぎ。all Brier差-0.00000785、log loss差-0.00001575も改善側だった。baselineへの独立edgeは確認する。

## Distribution Shift 0.51との直接比較

| 期間 | model | coverage | accuracy | selection score |
|---|---|---:|---:|---:|
| development | EWMA | 43.88180% | 51.63571% | 0.009989 |
| development | Shift | 43.39034% | 51.68065% | 0.010224 |
| confirmation | EWMA | 24.08844% | 51.74023% | 0.007475 |
| confirmation | Shift | 24.28862% | 51.81464% | 0.007877 |
| all | EWMA | 36.22956% | 51.66258% | 0.009344 |
| all | Shift | 36.00549% | 51.71559% | 0.009632 |

EWMAはShiftへaccuracy 2/7、score 1/7foldだった。all accuracy差-0.05302ptのbootstrap区間は-0.09643〜-0.00942pt、score差-0.000287は-0.000547〜-0.000027、Brier差+0.00000309は+0.00000033〜+0.00000588、log loss差+0.00000620は+0.00000066〜+0.00001179で、全主指標がEWMA劣後側だった。coverage +0.22407ptだけは増加側だが、精度と評価値を下げるためPareto候補にしない。

Shift/EWMA confidenceの事前固定50/50平均もdevelopment・confirmation・allのaccuracy/scoreを全てShiftより下げ、accuracy 3/7、score 2/7foldだった。allはaccuracy 51.68425%、score 0.009447で、Shift 51.71559%、0.009632に届かない。weight・閾値を再探索せず棄却する。

## 信頼度・局所品質

EWMA 0.51はconfirmation 203,364件、accuracy 51.74023%、mean confidence 51.54059%、Wilson 51.52302〜51.95738%で局所整合しedgeを確認した。allでは実測51.66258%に対しmean 51.99187%で過信し、局所区間外だった。Shiftもconfirmationで実測51.81464%に対しmean 51.53830%で過小評価となり、どちらもこの履歴だけでfair odds認可には使わない。

固定6方向×volatilityセルの0.51 confirmationは5/6セルがWilson edgeを持ったが、down-lowは3,249件・49.67682%・下限47.95896%だった。up-highは104,680件・52.23921%に対しmean 51.65841%で局所不整合だった。診断後filterへ変換しない。

0.55はconfirmation 153件・54.90196%でWilson下限46.99347%、edge未確認、0.575は0件だった。最終foldと同じruntime artifactのtestでも0.55は101件・48.51485%へ崩れたためprecision laneに使わない。

## Runtime parityと共有計算資源

最終foldと同じ2025-01-01/2026-01-01/2026-06-01境界でbaseline/EWMA runtime artifactを別生成し、HGB/Platt parameter、uniform weighting、expanding条件の一致検査を通した。latest M1はdown、confidence 50.38404%を出力し、認可していないため `odds_valid=false` のままである。

baseline、Shift、EWMA、Pathの7fold学習、blend、6本の20,000回bootstrap、reliability、subgroup、runtime artifact/latestはWindows側の単独8 thread、nice 10、低I/O優先度、CPU only workerで順番に実行した。開始時available memory 28.3GiB、load 0.04でgateを通過し、画像生成・ローカルAI等を停止していない。大きなmodel/parquet/比較成果物はWindows側だけに保存する。

## 判断

- M1 EWMA単体・通常方向blend・方向維持0.51を再現専用とする。
- Shiftとの固定50/50 confidence平均、0.55/0.575 precision利用も不採用。
- half-life、clip、feature subset、25% weight、0.51、平均weightを同じ履歴で再探索しない。
- Path方向、Distribution Shift方向/0.51、Transition guard、Disagreementを維持する。
- M5 EWMA 0.515だけを時間足固有のparallel broad候補として維持する。
- config、registry、authoritative方向/confidence、fair odds、売買policyを変更しない。

Mac全体は `1385 passed, 1 deselected, 83 subtests passed`、Windows全体も `1385 passed, 1 deselected, 83 subtests passed` だった。deselectは既知のentry-EV docs時刻test 1件である。変更3ファイルとWindows新規JSON/manifestをaccount、login、password、token、secret、private keyの代入形式で走査し、実値を含む一致は0件だった。口座runtime・credentialは転送していない。
