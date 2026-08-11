# 00134 M15 Distribution Shift Windows Transfer

日時: 2026-08-12 00:00 JST

## 結論

M1で有効だったRolling Distribution Shift 16特徴を定義・学習条件・25% weightを変えずM15へ固定移植した。Windows/WSL2 canonical環境でbaseline、Shift、既存broad championのProfileを同じ7foldから全て再学習し、platformを混在させていない。

Shift単体と通常25% blendの方向edgeはconfirmationで安定せず棄却する。一方、baseline方向を維持してconfidenceだけを25%混ぜる0.515 laneは、同一platformのProfileにaccuracyとselection scoreで7/7fold勝った。全期間accuracy差+0.12993ptの日次bootstrap 95%区間は+0.01935〜+0.24133pt、Brier/log loss差も改善側だった。`m15_distribution_shift_confidence_candidate_v1.json` のWindows canonical broad forward候補として採用する。

既存M15 registryは旧Mac artifactを含むため、そこへWindows結果を混ぜてchampionを書き換えない。M15候補群をWindowsで同一platform再構築し、latest推論parityとfresh局所校正を通すまではauthoritative confidence、fair odds、paper/live売買policyを変更しない。損失倍率は標準1.0だけを使った。

## 固定条件

- 直近128本内のreturn、absolute return、range、absolute bodyの中心化rank 4列
- 直近8本対、その直前の非重複64本のreturn location、absolute-return scale、variance scale、up比率 4列
- prior 64本の20/80%分位に対するrecent tail balance/activity 2列
- range/body scale shift 2列
- body/wick/close pressure平均shiftとclose-pressure dispersion shift 4列
- baseline 38列 + Shift 16列 = 54加工特徴
- HGB 200 iteration、learning rate 0.05、31 leaves、min leaf 100、L2 1、最大750,000 train行
- expanding、Platt、seed 42、uniform weighting、全教師、baseline 75% + candidate 25%
- confidence grid 0.51/0.515/0.525/0.535/0.55、development=test2020〜2023、confirmation=test2024〜2026_partial
- raw OHLC水準、volume、未来行をmodel featureへ使用しない

## Platform・品質監査

baseline、Shift、Profileは各145,140 OOS行、test2020〜2026_partialの7foldで、fold/timestamp/targetが完全一致した。Profile artifactは65特徴、predictionの重複・欠損は0。Shiftも54特徴、重複・欠損0を確認した。大きなmodel/parquet artifactはWindows側だけに保持した。

Windows baselineのall accuracyは51.76588%、Brier 0.24943106、log loss 0.69200802。Windows Profile単体はall accuracy 51.84236%、Brier 0.24939917、log loss 0.69194507だった。旧Macの数値と直接混ぜず、以下はすべてWindows内比較である。

## 単体と通常方向blend

| model | development accuracy | confirmation accuracy | all accuracy | all Brier | all log loss |
|---|---:|---:|---:|---:|---:|
| baseline | 52.03462% | 51.33882% | 51.76588% | 0.24943106 | 0.69200802 |
| Shift単体 | 52.13340% | 51.24249% | 51.78931% | 0.24942385 | 0.69199377 |
| baseline 75% + Shift 25% | 52.05483% | 51.34238% | 51.77966% | 0.24940769 | 0.69196095 |

Shift単体はbaseline比development +88件、confirmation -54件、all +34件でaccuracy 4/7fold。通常blendは+18/+2/+20件、McNemar exact p=0.75847、accuracy 4/7foldだった。通常blendのBrier/log lossは6/7fold改善したが、方向accuracyのconfirmation再現性がなく方向候補にはしない。

## 方向維持confidence 0.515

developmentの固定gridでselection score最大の0.515を選んだ。

| 期間 | model | rows | coverage | accuracy | selection score |
|---|---|---:|---:|---:|---:|
| development | baseline | 51,455 | 57.76074% | 53.10465% | 0.020317 |
| development | Shift | 51,094 | 57.35550% | 53.20390% | 0.020986 |
| development | Profile | 52,437 | 58.86308% | 53.04270% | 0.020065 |
| confirmation | baseline | 28,320 | 50.52001% | 52.55650% | 0.014035 |
| confirmation | Shift | 27,926 | 49.81715% | 52.62121% | 0.014365 |
| confirmation | Profile | 28,402 | 50.66629% | 52.54560% | 0.013984 |
| all | baseline | 79,775 | 54.96417% | 52.91006% | 0.019006 |
| all | Shift | 79,020 | 54.44399% | 52.99798% | 0.019552 |
| all | Profile | 80,839 | 55.69726% | 52.86805% | 0.018835 |

Shiftはbaseline比accuracy 6/7、selection score 5/7、Brier/log loss 6/7、ECE 5/7fold改善した。baseline比all accuracy差+0.08792ptの95%区間は-0.00836〜+0.18429pt、score差+0.000547の区間は-0.000166〜+0.001259で0を跨ぐ。Brier/log lossはdevelopment/allで改善区間が0を跨がず、confirmationでは跨いだ。

Profileとの同一platform直接比較ではShiftがaccuracy・scoreとも7/7fold勝った。20,000回UTC日block bootstrapは次の通り。

| 期間 | accuracy差 Shift−Profile | 95%区間 | score差 | 95%区間 |
|---|---:|---:|---:|---:|
| development | +0.16120pt | +0.02213〜+0.30313pt | +0.000920 | -0.000135〜+0.002005 |
| confirmation | +0.07562pt | -0.10714〜+0.25548pt | +0.000381 | -0.000915〜+0.001656 |
| all | +0.12993pt | +0.01935〜+0.24133pt | +0.000717 | -0.000104〜+0.001540 |

all Brier差は-0.00002296、95%区間-0.00003643〜-0.00000912、log loss差は-0.00004624、区間-0.00007333〜-0.00001842でShiftを支持した。coverageはProfileよりall -1.25327ptだが、精度上昇によりpoint selection scoreは全期間区分で高い。score区間は0を跨ぐため、authoritative運用への即時昇格ではなく固定forward候補とする。

## 固定0.55

Shiftはall 10,927件・coverage 7.52859%・accuracy 55.78841%・score 0.013322、Profileは11,147件・7.68017%・55.71006%・0.013264だった。Shiftはaccuracy 5/7foldでもscoreは4/7で、test2026_partialではProfileがaccuracy・scoreとも上回った。既存Structure precision roleを再学習して置き換える前提に達していないため、0.55用途へ拡張しない。

## 共有計算資源

全学習は単独8 thread、nice 10、低I/O優先度、CPU onlyで実行し、画像生成・ローカルAI処理を停止しなかった。Profile学習中に既存ローカルAI処理がCPUを使った際も、研究workerは低優先度のまま譲りながら継続した。開始時gateは実行中の競合を動的停止しないため、今後の長時間workerでは定期的なcooperative pauseを検討するが、本実験の条件は変更していない。

## 判断と成果物

- 単体Shiftと通常25% blendは方向用途では再現専用。
- 方向維持0.515をWindows canonicalのM15 broad forward候補として固定。
- 0.55はprecision用途に使わない。
- 8/64/128、16特徴、HGB parameter、25% weight、0.515を同じ履歴で再探索しない。
- 同一platform registry再構築、latest parity、fresh global/local calibrationまでauthoritative confidence、fair odds、売買policyへ昇格しない。

Windows側にbaseline/Shift/Profileのmodel・OOS prediction、固定blend、candidate analysis、直接比較、20,000回bootstrapを保存した。M15でも16加工列・全54列・raw価格排除・有限値を確認する回帰testを追加した。

MacとWindows/WSLの全体testはどちらも `1380 passed, 1 deselected, 83 subtests passed` だった。deselectは既知の非next-bar docs時刻testである。変更5ファイルとWindows側の新規M15成果物に対する口座・login・password/token/secret・private key形式のscanは0件だった。
