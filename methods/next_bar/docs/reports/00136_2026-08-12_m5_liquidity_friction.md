# 00136 M5 Liquidity Friction

日時: 2026-08-12 09:50 JST

## 結論

価格履歴のraw数値をそのま使わず、流動性摩擦のproxyへ加工する独立の `liquidity_friction` 10特徴を実装した。M5の同一Windows/WSL2 canonical baselineから固定条件で439,881 OOS行・7foldを作り、方向、方向維持confidence、既存Profile、固定50/50 confidence平均を比較した。

単体方向と通常25%方向blendは不採用。方向維持confidenceの固定0.515はbaselineへ年別の点値が安定したが、日次bootstrapで優位を確定できなかった。既存Profileへは開発期間の改善が確認期間で反転し、全期間のBrier/log lossも有意に悪化した。固定50/50平均も確認3/3foldでProfileを下回ったため、新しいconfigやregistry候補は発行せず再現専用とする。

Profile 0.515 broad confidence、Directional Follow-through 0.55 high-confidence shadow、authoritative confidence、fair odds、paper/live売買policyは変更しない。損失倍率は特別扱いせず標準1.0だけを使った。

## 固定特徴

- Corwin–Schultzの隣接完成2本実効spread proxy、rolling mean 8/32、rolling p90 32の4列
- Rollの負のlag-1 return自己共分散から作るspreadを、同期間の平均log rangeで有界比率化した32/128本の2列
- Parkinson range varianceとclose-return energyを有界比率化した16/64本の2列
- 現在値を除くprior 64本absolute-return medianの10%以下をnear-zeroとした32/128本率の2列
- baseline 38列 + Liquidity Friction 10列 = 48加工特徴

全列は0〜1に有界、価格scale不変、未来行不参照、raw OHLC水準・volume非使用である。隣接時間が切れた場合はCorwin–Schultz pairとclose returnをresetし、完全flatは十分なwarmup後に全10列0と定義した。式の一致、境界、scale、未来摂動、gap、flat、train/latestを回帰テストにした。

## 学習・評価条件

- M5、test2020〜test2026_partialの7fold、439,881 OOS行
- development=test2020〜2023、confirmation=test2024〜2026_partial
- HGB 200 iteration、learning rate 0.05、31 leaves、min leaf 100、L2 1、最大750,000 train行
- expanding、Platt、seed 42、uniform weighting、全教師、標準損失1.0
- baseline 75% + candidate 25%、開発期間の事前固定grid 0.51/0.515/0.525/0.535/0.55
- 候補とbaseline/Profileはfold・timestamp・targetが完全一致、duplicate 0、NaN 0

最大化する選択指標は `coverage * max(Wilson accuracy lower - 0.5, 0)` で、高信頼帯の精度だけでなくカバレッジを同時に評価した。閾値はdevelopmentで選び、confirmationで選び直していない。

## 方向結果

| model | all accuracy | all Brier | all log loss |
|---|---:|---:|---:|
| baseline | 51.57463% | 0.24953505 | 0.69221556 |
| Liquidity Friction単体 | 51.50848% | 0.24956345 | 0.69227247 |
| baseline 75% + Liquidity 25% | 51.56713% | - | - |

単体はbaseline比development -327件、confirmation +36件、all -291件で、開発期間のp=0.0147は悪化側だった。通常方向blendはall -33件、McNemar p=0.719997、accuracy 2/7fold。Brier/log loss/ECEは5/7fold改善したが、方向正答率を下げるため方向候補には使わない。

## 方向維持confidence 0.515

developmentでselection scoreが最大の事前gridは0.515だった。

| 期間 | model | rows | coverage | accuracy | selection score |
|---|---|---:|---:|---:|---:|
| development | baseline | 158,280 | 58.52468% | 52.75588% | 0.019201 |
| development | Liquidity | 157,658 | 58.29469% | 52.79910% | 0.019489 |
| confirmation | baseline | 63,694 | 37.59288% | 52.36600% | 0.012128 |
| confirmation | Liquidity | 62,801 | 37.06583% | 52.42432% | 0.012381 |
| all | baseline | 221,974 | 50.46228% | 52.64400% | 0.017306 |
| all | Liquidity | 220,459 | 50.11787% | 52.69234% | 0.017584 |

点値ではLiquidityがbaselineにaccuracy・selection score各6/7fold、Brier/log loss/ECE各5/7fold勝った。しかし20,000回のUTC日paired bootstrapは次の通り。

| 期間 | accuracy差 | 95%区間 | score差 | 95%区間 |
|---|---:|---:|---:|---:|
| development | +0.04322pt | -0.01195〜+0.09724pt | +0.000289 | -0.000132〜+0.000702 |
| confirmation | +0.05832pt | -0.05591〜+0.17394pt | +0.000253 | -0.000446〜+0.000958 |
| all | +0.04833pt | -0.00254〜+0.09915pt | +0.000278 | -0.000083〜+0.000639 |

全期間accuracyが良い確率は96.84%だが、95%区間はわずかに0を跨ぎ、Brier/log loss差の区間も0跨ぎだった。点値とfold勝数だけで新候補にしない。

## Profile 0.515との直接比較

| 期間 | model | coverage | accuracy | selection score |
|---|---|---:|---:|---:|
| development | Liquidity | 58.29469% | 52.79910% | 0.019489 |
| development | Profile | 58.55426% | 52.74754% | 0.019142 |
| confirmation | Liquidity | 37.06583% | 52.42432% | 0.012381 |
| confirmation | Profile | 37.46894% | 52.51559% | 0.013020 |
| all | Liquidity | 50.11787% | 52.69234% | 0.017584 |
| all | Profile | 50.43273% | 52.68116% | 0.017565 |

Liquidityはdevelopment score +0.000347だがconfirmation -0.000639へ反転し、fold勝数はaccuracy 3/7、score 4/7だった。特にconfirmationのtest2024、test2025、test2026_partialはaccuracy・scoreともProfileの3/3勝だった。

20,000回日次bootstrapのallはaccuracy差+0.01117pt、95%区間-0.04525〜+0.06743pt、score差+0.000020、区間-0.000381〜+0.000419で優位未確定。一方、LiquidityのBrier差は+0.00001119、区間+0.00000499〜+0.00001744、log loss差は+0.00002236、区間+0.00000989〜+0.00003491で、Profileより明確に悪かった。confirmation accuracy差も-0.09127ptで、改善が将来側へ安定していない。

## 固定50/50 confidence平均

Liquidity confidenceをProfile confidenceへ50%だけ混ぜた。方向と方向確率はProfileのままで、選別confidenceだけの独立情報追加を見た。

| 期間 | model | coverage | accuracy | selection score |
|---|---|---:|---:|---:|
| development | 50/50 | 58.42411% | 52.77328% | 0.019316 |
| development | Profile | 58.55426% | 52.74754% | 0.019142 |
| confirmation | 50/50 | 37.23935% | 52.42412% | 0.012414 |
| confirmation | Profile | 37.46894% | 52.51559% | 0.013020 |
| all | 50/50 | 50.26428% | 52.67364% | 0.017480 |
| all | Profile | 50.43273% | 52.68116% | 0.017565 |

50/50はProfileにaccuracy・scoreとも2/7勝5/7敗。confirmationは3foldすべて負け、allもaccuracy・coverage・scoreが低い。point gateを通らないためこのvariantのbootstrapは行わず、weightや閾値を履歴へ合わせて再探索しない。

## 高信頼帯0.55

Liquidityのallは23,531行、coverage 5.34940%、accuracy 55.97297%、score 0.012346。Profileは23,923行、accuracy 55.98796%、score 0.012495で、高信頼帯も既存候補を超えない。confirmationはLiquidity 826行・57.1429%・score 0.002613、Profile 872行・57.5688%・0.003058で、新しいprecision laneにする根拠がない。

## 共有計算資源

学習・比較・bootstrapは単独8 thread、nice 10、低I/O優先度、CPU onlyで順番に実行した。GPUは隠蔽し、画像生成・ローカルAI・その他の高負荷処理を停止していない。今回はGPU候補ではなく、exclusive windowも要求しなかった。

## 成果物と判断

Windows側にstandalone、通常25%方向blend、方向維持25% confidence blend、candidate analysis、baseline/Profile直接比較、20,000回bootstrap、0.55比較、Profileと50/50 confidence平均を保存した。大きなmodel/parquetはMacへ複製しない。

実装とartifactは後続の別モデル・新規期間での固定感度試験に使えるため保存する。ただし今回のM5 HGB候補は不採用で、window、特徴subset、blend weight、thresholdを同じ履歴で追加最適化しない。次に試す場合は、事前に固定した異種学習器か完全未使用期間とする。

MacとWindows/WSLの全体testはどちらも `1382 passed, 1 deselected, 83 subtests passed` だった。deselectは今回と無関係のentry-EV既存レポートに内部時刻がないdocs検査1件である。変更5ファイルとWindows側の新規M5成果物に対する口座・login・password/token/secret・private key形式のscanは0件だった。
