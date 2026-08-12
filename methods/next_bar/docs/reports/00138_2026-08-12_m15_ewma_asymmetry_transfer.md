# 00138 M15 EWMA Asymmetry Transfer

日時: 2026-08-12 11:37 JST

## 結論

M5でparallel broad confidence候補になった `ewma_asymmetry_state` 12特徴を、定義・半減期・HGB parameter・Platt校正・25% blend・閾値gridを変更せずM15へ固定移植した。Windows/WSL2 canonical環境でbaseline、既存Profile、既存Distribution Shiftと同じ145,140 OOS行・7foldを比較した。

単体方向と通常25%方向blendは不採用。方向維持confidenceのdevelopment固定0.515はbaselineとProfileを改善したが、現行Distribution Shift 0.515に全期間accuracy、selection score、Brier、log lossで点劣後し、直接差の20,000回日次bootstrap区間は全て0を跨いだ。既存候補に対する独立増分を確認できないためM15では再現専用とし、新しいconfig・registry候補を発行しない。

Distribution Shift 0.515 broad forward候補、既存precision候補、authoritative confidence、fair odds、paper/live売買policyは変更しない。損失倍率は標準1.0だけを使った。

## 固定条件

- 半減期4/16/64のreturn innovationとdrift/volatility
- 4対16、16対64のvolatility balance
- 半減期16/64のupside/downside energy balanceとleverage moment
- baseline 38列 + EWMA 12列 = 50加工特徴
- M15、test2020〜test2026_partial、145,140 OOS行
- HGB 200 iteration、learning rate 0.05、31 leaves、min leaf 100、L2 1
- expanding、最大750,000 train行、Platt、uniform weighting、全教師、seed 42
- baseline 75% + candidate 25%、方向維持confidenceはbaseline方向を固定
- developmentだけで0.51/0.515/0.525/0.535/0.55を評価
- 主目的関数 `sqrt(coverage) * (Wilson95Lower(accuracy) - 0.50)`

既存M5試験から特徴式を一切変更していない。M15でも12列、全50列、[-1,1]境界、raw OHLC水準の不使用、有限値を回帰テストへ追加した。candidate・baseline・Profile・Distribution Shiftはfold、timestamp、targetが完全一致し、latest artifactから有限予測が出ることも確認した。

## 方向結果

| model | development accuracy | confirmation accuracy | all accuracy | all Brier | all log loss |
|---|---:|---:|---:|---:|---:|
| baseline | 52.03462% | 51.33882% | 51.76588% | 0.24943106 | 0.69200802 |
| EWMA単体 | 51.88644% | 51.41909% | 51.70594% | 0.24943182 | 0.69200931 |
| baseline 75% + EWMA 25% | 51.99982% | 51.37628% | 51.75899% | 0.24941285 | 0.69197131 |

単体はbaseline比development -132件、confirmation +45件、all -87件、McNemar exact p=0.46248。通常blendは-31/+21/-10件、p=0.87712、accuracy 4/7foldだった。Brier/log lossは通常blendで6/7fold改善したが、方向accuracyの増分がなく方向用途には採用しない。

## 方向維持confidence 0.515

development目的関数最大はM5と同じ0.515だった。

| 期間 | model | coverage | accuracy | selection score |
|---|---|---:|---:|---:|
| development | baseline | 57.76074% | 53.10465% | 0.020317 |
| development | EWMA | 57.65634% | 53.16771% | 0.020774 |
| confirmation | baseline | 50.52001% | 52.55650% | 0.014035 |
| confirmation | EWMA | 49.49605% | 52.62741% | 0.014349 |
| all | baseline | 54.96417% | 52.91006% | 0.019006 |
| all | EWMA | 54.50462% | 52.97821% | 0.019418 |

EWMAはbaseline比accuracy 5/7、score 4/7、Brier/log loss 6/7、ECE 5/7fold改善した。点値はdevelopment・confirmation・allで同方向だったが、20,000回日次bootstrapのaccuracy差95%区間はdevelopment -0.05290〜+0.18074pt、confirmation -0.08173〜+0.22175pt、all -0.02366〜+0.15958ptで全て0を跨いだ。selection score差も3期間で0跨ぎだった。

一方、Brier/log loss差はconfirmationとallで改善側に確定した。これは加工情報が確率の平滑化には有効である証拠だが、accuracyとcoverageを同時最大化する目的の新しい役割を単独では証明しない。

## 既存候補との比較

### Distribution Shift 0.515

| 期間 | model | coverage | accuracy | selection score |
|---|---|---:|---:|---:|
| development | EWMA | 57.65634% | 53.16771% | 0.020774 |
| development | Shift | 57.35550% | 53.20390% | 0.020986 |
| confirmation | EWMA | 49.49605% | 52.62741% | 0.014349 |
| confirmation | Shift | 49.81715% | 52.62121% | 0.014365 |
| all | EWMA | 54.50462% | 52.97821% | 0.019418 |
| all | Shift | 54.44399% | 52.99798% | 0.019552 |

EWMAはaccuracy 3/7、score 4/7で、全期間ではaccuracy -0.01977pt、score -0.000134、Brier +0.00000519、log loss +0.00001044と全主指標が僅かにShiftを下回った。直接bootstrapはaccuracy、coverage、score、Brier、log lossの全てで0跨ぎだった。confirmationではEWMAのaccuracyが+0.00619pt、proper scoreも点改善したが、coverage低下によりselection scoreは-0.000016で、期間固有の置換根拠にならない。

### Profile 0.515

EWMAはProfileへaccuracy 6/7、score 5/7fold勝ち、全期間accuracy +0.11016ptのbootstrap区間は+0.00129〜+0.21871pt、Brier/log lossもconfirmation/allで改善側だった。ただしProfileは既にShiftに置き換えるforward候補関係であり、より強いShiftに増分がないEWMAを追加して候補数を増やさない。

## 信頼度と局所品質

EWMA 0.515はconfirmation 27,746件、accuracy 52.62741%、mean confidence 52.88087%、Wilson 52.03956〜53.20715%で局所整合しedgeも確認した。固定6方向×volatilityセルでは4セルがWilson edgeを持ったが、down-lowは1,852件・50.70194%、down-normalは3,437件・51.23654%で下限50%未満だった。診断後filterへ変更しない。

0.55はconfirmation 1,748件・57.09382%、mean confidence 55.89221%、全期間11,115件・55.75349%だった。しかしShift 0.55の全期間55.78841%を超えず、既存M15 precision roleも置換しない。

## 共有計算資源と判断

実装確認、7fold学習、比較、20,000回bootstrap、reliability、subgroup、latest推論はWindows側の単独8 thread、nice 10、低I/O優先度、CPU only workerで順番に実行した。開始時はavailable memory 28.3GiB、load 0.51でgateを通過した。GPUを隠し、画像生成・ローカルAI・その他の高負荷処理を停止していない。

- EWMA単体・通常方向blendは不採用。
- M15 EWMA 0.515はbaseline/Profile改善の再現感度として保存するが、Shiftに増分がないため候補へ追加しない。
- half-life、clip、特徴subset、25% weight、0.515を同じ履歴で再探索しない。
- Distribution Shift 0.515、既存precision候補、authoritative confidence、fair odds、policyを維持する。
- 大きなmodel/parquetと比較成果物はWindows側だけに保存する。

Macの対象testは`88 passed`。Windows全体は既知のentry-EV docs時刻test 1件をdeselectして`1384 passed, 1 deselected, 83 subtests passed`だった。変更4ファイルとWindows新規JSON/manifestを口座、login、password、token、secret、private keyの語で走査し、実値を含む一致は0件だった。口座runtime・credentialは転送していない。
