# 00135 M30 Distribution Shift Windows Transfer

日時: 2026-08-12 00:19 JST

## 結論

M1で有効だったRolling Distribution Shift 16特徴を定義・学習条件・25% weightを変えずM30へ固定移植した。Windows/WSL2 canonical環境でbaseline、Shift、既存0.52候補のPressure、比較親Profileを同じ71,260 OOS行・7foldから全て再学習し、platformを混在させていない。

Shift単体と通常25% blendの方向edgeは棄却する。baseline方向を維持してconfidenceだけを25%混ぜる0.52 laneは、baselineへのall accuracy、selection score、Brier、log lossの日次bootstrap区間がすべて改善側だった。Pressure/Profileへのaccuracy・score増分は未確定だが、confirmation/all coverageを有意に広げ、点accuracyも下げなかった。`m30_distribution_shift_confidence_candidate_v1.json` のparallel coverage challengerとして採用する。

Pressure 0.52は全行proper scoreが良く、Shiftの直接置換は確定していないため維持する。0.55はPressureに年別score 3/7対4/7で、既存Pressure+AR shadowを変更しない。authoritative confidence、fair odds、paper/live売買policyへは昇格しない。損失倍率は標準1.0だけを使った。

## 固定条件

- 直近128本内のreturn、absolute return、range、absolute bodyの中心化rank 4列
- 直近8本対、その直前の非重複64本のreturn location、absolute-return scale、variance scale、up比率 4列
- prior 64本の20/80%分位に対するrecent tail balance/activity 2列
- range/body scale shift 2列
- body/wick/close pressure平均shiftとclose-pressure dispersion shift 4列
- baseline 38列 + Shift 16列 = 54加工特徴
- HGB 200 iteration、learning rate 0.05、31 leaves、min leaf 100、L2 1、最大750,000 train行
- expanding、Platt、seed 42、uniform weighting、全教師、baseline 75% + candidate 25%
- 0.515/0.52/0.525/0.53/0.54/0.55固定grid、development=test2020〜2023、confirmation=test2024〜2026_partial
- raw OHLC水準、volume、未来行をmodel featureへ使用しない

## Platform・品質監査

baseline、Shift、Pressure、Profileは各71,260 OOS行、test2020〜2026_partialの7foldで、fold/timestamp/targetが完全一致した。Shift predictionの重複・欠損は0。大きなmodel/parquet artifactはWindows側だけに保持した。

Windows baselineのall accuracyは51.70362%、Brier 0.24951842、log loss 0.69218345。以下はすべて同じWindows baselineを親にした比較であり、既存Mac artifactを混ぜていない。

## 単体と通常方向blend

| model | development accuracy | confirmation accuracy | all accuracy | all Brier | all log loss |
|---|---:|---:|---:|---:|---:|
| baseline | 51.73972% | 51.64672% | 51.70362% | 0.24951842 | 0.69218345 |
| Shift単体 | 51.85669% | 51.40089% | 51.67976% | 0.24954311 | 0.69223147 |
| baseline 75% + Shift 25% | 51.83146% | 51.51658% | 51.70923% | 0.24949129 | 0.69212850 |

Shift単体はbaseline比development +51件、confirmation -68件、all -17件。通常blendは+40/-36/+4件、McNemar exact p=0.95278、accuracy 2/7foldだった。通常blendのproper score改善は方向accuracyを補わず、方向候補にはしない。

## 方向維持confidence 0.52

development固定gridのselection score最大は0.52だった。

| 期間 | model | rows | coverage | accuracy | mean confidence | selection score |
|---|---|---:|---:|---:|---:|---:|
| development | baseline | 18,048 | 41.39544% | 52.99756% | - | 0.014598 |
| development | Shift | 17,539 | 40.22799% | 53.38959% | 53.80333% | 0.016812 |
| confirmation | baseline | 9,378 | 33.90333% | 53.46556% | - | 0.014293 |
| confirmation | Shift | 9,346 | 33.78764% | 53.47742% | 53.39990% | 0.014328 |
| all | baseline | 27,426 | 38.48723% | 53.15759% | - | 0.015923 |
| all | Shift | 26,885 | 37.72804% | 53.42012% | 53.66309% | 0.017342 |

Shiftはbaseline比accuracy 5/7、selection score 4/7、Brier/log loss/ECE各6/7fold改善した。20,000回UTC日block bootstrapは次の通り。

| 期間 | accuracy差 | 95%区間 | score差 | 95%区間 |
|---|---:|---:|---:|---:|
| development | +0.39203pt | +0.12534〜+0.66623pt | +0.002214 | +0.000508〜+0.003957 |
| confirmation | +0.01187pt | -0.33173〜+0.35640pt | +0.000035 | -0.001971〜+0.002044 |
| all | +0.26254pt | +0.05052〜+0.47706pt | +0.001419 | +0.000112〜+0.002745 |

all Brier差は-0.00002661、95%区間-0.00005084〜-0.00000255、log loss差は-0.00005390、区間-0.00010259〜-0.00000547で改善側だった。confirmationは点値を維持したが区間上は未確定なので、完全未使用期間のgateを残す。

0.52のmean confidenceはdevelopmentで実績より0.41375pt高く、confirmationでは0.07753pt低く、allでは0.24297pt高い。いずれもmean confidenceがWilson区間内で局所整合したが、この履歴だけでfair oddsを認可しない。

## Pressure/Profile直接比較

| 期間 | model | coverage | accuracy | selection score |
|---|---|---:|---:|---:|
| development | Shift | 40.22799% | 53.38959% | 0.016812 |
| development | Pressure | 40.23028% | 53.35234% | 0.016576 |
| development | Profile | 40.10872% | 53.39395% | 0.016808 |
| confirmation | Shift | 33.78764% | 53.47742% | 0.014328 |
| confirmation | Pressure | 32.55125% | 53.32075% | 0.013060 |
| confirmation | Profile | 33.23090% | 53.38338% | 0.013618 |
| all | Shift | 37.72804% | 53.42012% | 0.017342 |
| all | Pressure | 37.24951% | 53.34162% | 0.016729 |
| all | Profile | 37.43896% | 53.39031% | 0.017079 |

ShiftはPressure/Profileへaccuracy 4/7、score 5/7fold。all accuracy差のbootstrap区間はPressure比-0.17521〜+0.32764pt、Profile比-0.20917〜+0.26613pt、score差も両方0を跨いだ。置換確定とはしない。

一方、Shiftのall coverage差はPressure比+0.47853pt、95%区間+0.25413〜+0.70277pt、Profile比+0.28908pt、区間+0.10139〜+0.47628pt。confirmationもPressure比+1.23640pt、Profile比+0.55674ptで区間が改善側だった。点精度を維持して選択機会を広げるparallel coverage役割として保存する。

全行probability qualityはPressureのBrier 0.24947071、Profile 0.24947714、Shift 0.24949181の順で、Shiftは両候補より僅かに悪い。coverage改善だけでPressureを置換せず、fresh accuracy・score・calibrationを同時に要求する。

## 不採用variant

- 固定0.55はShiftがall 4,432件・55.5505%・score 0.010184、Pressureが4,266件・55.3446%・0.009417だったが、fold scoreは3/7対4/7。既存Pressure+AR 0.55を再学習して置換する条件に達しない。
- Shift confidenceとPressure confidenceの固定50/50はconfirmation scoreを0.014457へ上げたが、development 0.016050、all 0.016905でShift単独を下回った。weightや閾値を再探索せず棄却する。

## 共有計算資源

全学習は単独8 thread、nice 10、低I/O優先度、CPU onlyで順番に実行した。開始時load 0.12、利用可能メモリ28GiBで、worker gateを緩めず、画像生成・ローカルAI処理を停止していない。

## 判断と成果物

- 単体Shiftと通常25% blendは方向用途では再現専用。
- 方向維持0.52をWindows canonicalのM30 parallel coverage challengerとして固定。
- Pressure 0.52とPressure+AR 0.55を維持し、0.55 Shiftと固定Pressure平均は使わない。
- 8/64/128、16特徴、HGB parameter、25% weight、0.52を同じ履歴で再探索しない。
- latest parity、fresh Pressure head-to-head、global/local calibrationまでauthoritative confidence、fair odds、売買policyへ昇格しない。

Windows側にbaseline/Shift/Pressure/Profileのmodel・OOS prediction、固定blend、candidate analysis、直接比較、20,000回bootstrap、reliability監査を保存した。M30でも16加工列・全54列・raw価格排除・有限値を確認する回帰testを追加した。

MacとWindows/WSLの全体testはどちらも `1381 passed, 1 deselected, 83 subtests passed` だった。deselectは既知の非next-bar docs時刻testである。変更5ファイルとWindows側の新規M30成果物に対する口座・login・password/token/secret・private key形式のscanは0件だった。
