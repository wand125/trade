# 00139 M30 EWMA Asymmetry Transfer

日時: 2026-08-12 12:11 JST

## 結論

M5でparallel broad confidence候補になった `ewma_asymmetry_state` 12特徴を、定義・半減期・HGB parameter・Platt校正・25% blend・閾値gridを変えずM30へ固定移植した。Windows/WSL2 canonical環境でbaseline、Distribution Shift、Intrabar Pressureと同じ71,260 OOS行・7foldを比較した。

EWMA単体はbaselineよりdevelopment・confirmationの方向accuracyがともに高かったが、差は20,000回日次bootstrapで未確定、confirmationのBrier/log lossは悪化した。通常25%方向blendもconfirmationで-3件、accuracy 3/7foldだったため方向候補にはしない。

方向維持confidenceはdevelopmentだけで0.52が選ばれたが、confirmationでbaselineにaccuracy -0.16687pt、selection score -0.000921へ反転した。現行Distribution Shift 0.52にはaccuracy・selection score各1/7fold、固定50/50 confidence平均も各1/7foldだった。新しいconfig・registry候補を発行せず、M30では再現専用とする。

Distribution Shift 0.52 coverage challenger、Pressure 0.52、Pressure + AR 0.55 shadow、authoritative confidence、fair odds、paper/live売買policyは変更しない。損失倍率は標準1.0だけを使った。

## 固定条件

- 半減期4/16/64のprior-volatility標準化return innovationとdrift/volatility
- 4対16、16対64のvolatility balance
- 半減期16/64のupside/downside energy balanceとleverage moment
- baseline 38列 + EWMA 12列 = 50加工特徴
- M30、test2020〜test2026_partial、71,260 OOS行
- HGB 200 iteration、learning rate 0.05、31 leaves、min leaf 100、L2 1
- expanding、最大750,000 train行、Platt、uniform weighting、全教師、seed 42
- baseline 75% + candidate 25%、方向維持confidenceはbaseline方向を固定
- developmentだけで0.515/0.52/0.525/0.53/0.54/0.55を評価
- 主目的関数 `sqrt(coverage) * (Wilson95Lower(accuracy) - 0.50)`

M5/M15試験後に特徴式、clip、window、weightを変更していない。M30でも12列、全50列、[-1,1]境界、raw OHLC水準の不使用、有限値を回帰testへ追加した。各候補はfold、decision timestamp、targetを完全整列した。

## 方向結果

| model | development accuracy | confirmation accuracy | all accuracy | all Brier | all log loss |
|---|---:|---:|---:|---:|---:|
| baseline | 51.73972% | 51.64672% | 51.70362% | 0.24951842 | 0.69218345 |
| EWMA単体 | 51.82917% | 51.75879% | 51.80185% | 0.24948698 | 0.69212075 |
| baseline 75% + EWMA 25% | 51.82688% | 51.63588% | 51.75274% | 0.24948347 | 0.69211319 |

EWMA単体はbaseline比development +39件、confirmation +31件、all +70件、accuracy 5/7foldだった。しかしMcNemar exact p=0.47215で、all accuracy差+0.09823ptの日次bootstrap区間は-0.17209〜+0.36427ptだった。confirmationのBrier/log lossは点悪化し、3期間のaccuracy・Brier・log loss差のbootstrap区間は全て0を跨いだ。

通常25% blendは+38/-3/+35件、p=0.47827、accuracy 3/7foldだった。Brier/log lossは6/7fold改善したが、方向accuracyの確認期間再現性がない。単体・通常blendとも方向用途へ採用しない。

## 方向維持confidence 0.52

development目的関数最大はM30の既存候補と同じ0.52だった。

| 期間 | model | coverage | accuracy | selection score |
|---|---|---:|---:|---:|
| development | baseline | 41.39544% | 52.99756% | 0.014598 |
| development | EWMA | 40.43441% | 53.23047% | 0.015854 |
| confirmation | baseline | 33.90333% | 53.46556% | 0.014293 |
| confirmation | EWMA | 34.08409% | 53.29868% | 0.013372 |
| all | baseline | 38.48723% | 53.15759% | 0.015923 |
| all | EWMA | 37.96941% | 53.25424% | 0.016386 |

EWMAはbaseline比accuracy・score各3/7、Brier/log loss 6/7、ECE 5/7fold改善した。all Brier差-0.00003237とlog loss差-0.00006511はbootstrapでも改善側だった。一方、accuracy差区間はdevelopment -0.01473〜+0.48524pt、confirmation -0.51120〜+0.17334pt、all -0.10320〜+0.30165pt、score差も3期間すべて0跨ぎだった。confirmation反転を優先し、baseline改善だけで候補化しない。

## 既存M30候補との直接比較

### Distribution Shift 0.52

| 期間 | model | coverage | accuracy | selection score |
|---|---|---:|---:|---:|
| development | EWMA | 40.43441% | 53.23047% | 0.015854 |
| development | Shift | 40.22799% | 53.38959% | 0.016812 |
| confirmation | EWMA | 34.08409% | 53.29868% | 0.013372 |
| confirmation | Shift | 33.78764% | 53.47742% | 0.014328 |
| all | EWMA | 37.96941% | 53.25424% | 0.016386 |
| all | Shift | 37.72804% | 53.42012% | 0.017342 |

EWMAはShiftにaccuracy・score各1/7foldで、development、confirmation、allの全区分でaccuracyとscoreが低かった。all差はcoverage +0.24137pt、accuracy -0.16588pt、score -0.000956である。bootstrapではcoverage増加だけがconfirmation/allで確定し、accuracy・score・Brier・log loss差は0跨ぎだった。精度を下げたcoverage拡大は新しいPareto役割にしない。

ShiftとEWMA confidenceの事前固定50/50平均もShiftへaccuracy・score各1/7fold、all accuracy 53.20849%、score 0.016052で、Shift単独53.42012%、0.017342を下回った。weight・閾値を再探索せず棄却する。

### Intrabar Pressure 0.52

EWMAはPressureへaccuracy 3/7、score 4/7foldだった。allはcoverage +0.71990ptに対しaccuracy -0.08738pt、score -0.000343。confirmationのcoverage +1.53284ptだけはbootstrapで確定したが、accuracy・score・proper scoreは全て未確定で、現行Pressureを置換しない。

## 信頼度・局所品質

EWMA 0.52はconfirmation 9,428件、accuracy 53.29868%、mean confidence 53.41001%、Wilson 52.29045〜54.30423%で局所整合しedgeも確認した。ただしShiftは同期間53.47742%である。EWMA 0.55もconfirmation 1,073件・55.54520%、all 4,605件・55.41802%だが、Shiftのall 55.55054%を超えない。0.575はconfirmation 151件・62.25166%でもShiftは142件・64.78873%だった。

固定6方向×volatilityセルでは0.52 confirmationのWilson edgeは3/6セルだけだった。down-lowは366件・50.54645%、down-normalは759件・53.22793%、up-lowは806件・50.99256%で下限50%未満である。0.55はup-highだけがedgeを持ち、up-normalは176件・47.72727%、mean confidence 56.15940%で局所不整合だった。診断後filterへ変換しない。

## Runtime parityと共有計算資源

walk-forward成果物とは別に最終foldと同じ2025-01-01/2026-01-01/2026-06-01境界でbaseline/EWMA runtime artifactを生成した。設定一致検査は全HGB/Platt parameter、uniform weighting、expanding条件に合格した。latest M30はup、confidence 53.06139%を出力し、認可していないため `odds_valid=false` のままである。

学習、blend、4本の20,000回bootstrap、reliability、subgroup、runtime artifact/latestはWindows側の単独8 thread、nice 10、低I/O優先度、CPU only workerで順番に実行した。開始時available memory 28.2GiB、load 0.06でgateを通過し、画像生成・ローカルAI等を停止していない。大きなmodel/parquet/比較成果物はWindows側だけに保存する。

## 判断

- EWMA単体・通常方向blend・方向維持0.52をM30では再現専用とする。
- Shiftとの固定50/50 confidence平均、0.55/0.575 precision利用も不採用。
- half-life、clip、feature subset、25% weight、0.52、平均weightを同じ履歴で再探索しない。
- Distribution Shift 0.52、Pressure 0.52、Pressure + AR 0.55を維持する。
- config、registry、authoritative方向/confidence、fair odds、売買policyを変更しない。

Macの対象testは `89 passed`。Windows全体は既知のentry-EV docs時刻test 1件をdeselectして `1385 passed, 1 deselected, 83 subtests passed` だった。変更4ファイルとWindows新規JSON/manifestをaccount、login、password、token、secret、private keyの代入形式で走査し、実値を含む一致は0件だった。口座runtime・credentialは転送していない。
