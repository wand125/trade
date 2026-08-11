# 00133 M5 Distribution Shift Windows Transfer

日時: 2026-08-11 23:24 JST

## 結論

M1で方向stability/proper-score候補になったRolling Distribution Shift 16特徴を、定義を変えずM5へ固定移植した。Windows/WSL2 canonical環境でbaseline、Shift、既存Profileを同じ7foldから全て再学習し、Mac/Windows artifactを混在させなかった。

Shift単体と通常25%方向blendはbaseline方向accuracyを改善せず棄却する。方向維持25%・confidence 0.515はbaselineよりaccuracy・selection scoreを5/7fold、Brierを5/7fold改善したが、同一platformのProfile 0.515にconfirmation/all scoreと5/7foldで負けた。固定0.55もconfirmationでProfileに負ける。M5では再現専用とし、config、registry、authoritative direction/confidence、fair odds、paper/live policyを変更しない。損失倍率は標準1.0だけを使った。

## 仮説と固定加工

現在のM5価格水準を使わず、完成済みM5足の短期分布が直前の長期分布からどれだけ移動したかを加工する。

- 直近128本内のreturn、absolute return、range、absolute bodyの中心化rank 4列
- 直近8本対、その直前の非重複64本のreturn location、absolute-return scale、variance scale、up比率 4列
- prior 64本の20/80%分位に対するrecent tail balance/activity 2列
- range/body scale shift 2列
- body/wick/close pressure平均shiftとclose-pressure dispersion shift 4列

M1で固定した8/64/128本、feature subset、HGB 200 iteration、learning rate 0.05、31 leaves、min leaf 100、L2 1、最大750,000 train行、Platt、expanding、seed 42、uniform weighting、全教師、25% blendを変更していない。raw OHLC水準、volume、未来足はmodel featureへ使わない。confidence gridもM1固定の0.51/0.515/0.525/0.535/0.55だけとし、development=test2020〜2023、confirmation=test2024〜2026_partialとした。

## Platform統一

共通M1 6,025,170行からM5 7fold、439,881 OOS行を作った。baseline 38特徴、Shift 54特徴、Profile 65特徴で、各predictionのfold/timestamp/targetは完全一致し、重複・欠損は0だった。

Windows再学習baselineのall accuracyは51.57463%。既存Mac baselineは51.55644%で0.01819pt差があり、同じ比較へ混ぜない必要性を再確認した。Windows Profile 0.515のall accuracy/coverage/scoreは52.68116% / 50.43273% / 0.017565で、既存Mac Profileの52.68482% / 50.20312% / 0.017547と近く、Profileの役割はplatform移行後も維持された。

## 単体と通常方向blend

| model | development accuracy | confirmation accuracy | all accuracy | all Brier | all log loss |
|---|---:|---:|---:|---:|---:|
| Windows baseline | 51.91385% | 51.03316% | 51.57463% | 0.24953505 | 0.69221556 |
| Shift単体 | 51.88722% | 51.05028% | 51.56486% | 0.24955123 | 0.69224826 |
| baseline 75% + Shift 25% | 51.89092% | 51.06858% | 51.57418% | 0.24952712 | 0.69219964 |

Shift単体はbaseline比development -72件、confirmation +29件、all -43件。通常blendはdevelopment -62件、confirmation +60件、all -2件で、McNemar exact p=0.99145、accuracy 3/7foldだった。通常blendのBrier/log lossは5/7fold改善したが、方向accuracy非改善をproper scoreだけで採用しない。

## 方向維持confidence 0.515

developmentの固定gridでShiftのselection score最大は0.515だった。

| 期間 | model | rows | coverage | accuracy | selection score |
|---|---|---:|---:|---:|---:|
| development | baseline | 158,280 | 58.52468% | 52.75588% | 0.019201 |
| development | Shift | 157,336 | 58.17563% | 52.76796% | 0.019230 |
| development | Profile | 158,360 | 58.55426% | 52.74754% | 0.019142 |
| confirmation | baseline | 63,694 | 37.59288% | 52.36600% | 0.012128 |
| confirmation | Shift | 62,773 | 37.04930% | 52.41425% | 0.012316 |
| confirmation | Profile | 63,484 | 37.46894% | 52.51559% | 0.013020 |
| all | baseline | 221,974 | 50.46228% | 52.64400% | 0.017306 |
| all | Shift | 220,109 | 50.03831% | 52.66709% | 0.017391 |
| all | Profile | 221,844 | 50.43273% | 52.68116% | 0.017565 |

Shiftはbaseline比accuracy/score各5/7fold、Brier 5/7、log loss 4/7、ECE 5/7だった。20,000回UTC日block bootstrapではbaseline比all accuracy差+0.02308ptの95%区間が-0.03077〜+0.07694pt、score差+0.000084の区間が-0.000296〜+0.000468で、どちらも0を跨いだ。Brier/log lossはdevelopmentとallで改善区間が0を跨がず、confirmationでは跨いだ。

Profileとの直接比較はShiftのaccuracy/score勝数2/7、Profile 5/7。all accuracy差-0.01408ptの区間は-0.07378〜+0.04587ptで未確定だが、confirmation score差は-0.000704、bootstrap区間-0.001484〜+0.000077でProfile側へ偏った。developmentのBrier/log lossはProfileが明確に良く、Shiftのdevelopment point scoreだけを採用根拠にしない。

## 固定0.55

| 期間 | model | rows | accuracy | selection score |
|---|---|---:|---:|---:|
| development | Shift | 22,983 | 56.0240% | 0.015687 |
| development | Profile | 23,051 | 55.9282% | 0.015433 |
| confirmation | Shift | 831 | 56.4380% | 0.002132 |
| confirmation | Profile | 872 | 57.5688% | 0.003058 |
| all | Shift | 23,814 | 56.0385% | 0.012581 |
| all | Profile | 23,923 | 55.9880% | 0.012495 |

development/allの僅かなpoint優位はconfirmationで反転し、fold勝数も3/7対4/7だった。既存Directional Follow-through high-confidence shadowを再学習して比較する前提条件に達していない。

## 共有worker挙動

最初のblend解析開始時は1分load 12.58が上限8を超え、workerがexit 75で処理を延期した。上限を緩めず、load 6.01へ下がってから再実行した。全学習は単独8 thread、nice 10、低I/O優先度、CPU onlyで順番に実行し、画像生成・ローカルAI・WSLを停止していない。

## 判断と成果物

- M5 Shift単体、通常25%方向blend、方向維持0.515/0.55を再現専用とする。
- 8/64/128、feature subset、HGB parameter、weight、thresholdを同じ履歴で再探索しない。
- M5 Profile 0.515 broad confidenceとDirectional Follow-through 0.55 high-confidence shadowを維持する。
- fair odds、latest runtime、運用config、registry entryを発行しない。

Windows側にbaseline/Shift/Profileのmodel・OOS prediction、固定blend、candidate analysis、baseline/Profile比較、20,000回bootstrapを保存した。大きなartifactは母艦へ戻さない。

M5でも16加工列・全54列・raw価格排除・有限値を確認する回帰testを追加した。MacとWindows/WSLの全体testはどちらも `1379 passed, 1 deselected, 83 subtests passed` だった。deselectは既知の非next-bar docs時刻testである。変更ファイルとWindows側の新規M5成果物に対する口座・login・password/token/secret・private key形式のscanは0件だった。
