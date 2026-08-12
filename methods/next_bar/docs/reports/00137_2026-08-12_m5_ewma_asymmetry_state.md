# 00137 M5 EWMA Asymmetry State

日時: 2026-08-12 10:40 JST

## 結論

履歴OHLCをそのまま使わず、指数減衰するreturn・volatility・上下非対称性へ加工する `ewma_asymmetry_state` 12特徴を実装した。M5 Windows/WSL2 canonical環境で、既存baseline・Profileと同じ439,881 OOS行・7fold、HGB/Platt、標準損失1.0から固定検証した。

単体方向と通常25%方向blendは採用しない。baseline方向を維持してconfidenceだけ25%混ぜる固定0.515は、confirmationのaccuracy・selection scoreと全期間proper scoreが20,000回UTC日bootstrapでも改善した。このため `m5_ewma_asymmetry_confidence_candidate_v1.json` のparallel broad forward候補として採用する。

現行Profile 0.515との差は統計的に未確定で、開発期間はEWMA、確認期間はProfileが僅差で勝った。固定50/50合成も確認期間を悪化させたため、Profileを置換・合成しない。0.55は最新foldが偶然水準を下回り、Follow-throughよりselection scoreが弱い。authoritative confidence、fair odds、paper/live売買policyは変更しない。

## 仮説選定

最初に複数時間幅のvariance ratio・方向持続性を候補としたが、既存 `path_persistence` が5/10/20/50本efficiency、10/20本自己相関、50本variance ratio、方向持続率、streakを既に扱っていた。独立性がないため実装前に中止し、結果を見て定義を変えずEWMA Asymmetryへ切り替えた。

Shock Recoveryは直前64本z-scoreの2σイベント後16本を追跡し、Change Pointは固定窓innovationのCUSUM、Volatility Stateはrolling window統計である。今回の特徴は連続的な指数減衰状態とreturn符号別energy、lagged returnと現在varianceの非対称momentを扱う点で独立している。

## 固定特徴

- 半減期4/16/64の現在return ÷ 直前EWMA volatilityを[-5,5] clip後5で割ったinnovation 3列
- 半減期4/16/64のEWMA drift ÷ EWMA volatilityを[-3,3] clip後3で割った3列
- EWMA volatilityの4対16、16対64を対称比率化した2列
- 半減期16/64のupside/downside squared-return energy balance 2列
- 半減期16/64の「直前return × 現在squared return」EWMAをvarianceの1.5乗で標準化したleverage moment 2列
- baseline 38列 + EWMA 12列 = 50加工特徴

全出力は[-1,1]に有界、価格10倍scale不変、未来行の改変は過去へ影響しない。timestamp gapごとに系列を分けてEWMAを再初期化し、gap先頭と完全flat系列は全12列0とした。raw OHLC水準、volume、target、未来足を特徴へ使わない。

## 学習・品質条件

- M5、test2020〜test2026_partialの7fold、439,881 OOS行
- development=test2020〜2023、confirmation=test2024〜2026_partial
- HGB 200 iteration、learning rate 0.05、31 leaves、min leaf 100、L2 1
- expanding、最大750,000 train行、Platt、seed 42、uniform weighting、全教師
- baseline 75% + candidate 25%、標準損失1.0
- 閾値grid 0.51/0.515/0.525/0.535/0.55をdevelopmentだけで評価
- 主目的関数 `sqrt(coverage) * (Wilson95Lower(accuracy) - 0.50)`

candidate・baseline・Profileはfold、timestamp、targetを完全整列し、duplicate 0、NaN 0を確認した。最終fold artifactのlatest推論は成功し、M5 50特徴から有限確率を出力した。

## 方向結果

| model | development accuracy | confirmation accuracy | all accuracy | all Brier | all log loss |
|---|---:|---:|---:|---:|---:|
| baseline | 51.91385% | 51.03316% | 51.57463% | 0.24953505 | 0.69221556 |
| EWMA単体 | 51.88390% | 51.07625% | 51.57281% | 0.24953804 | 0.69222175 |
| baseline 75% + EWMA 25% | 51.90497% | 51.05972% | 51.57940% | 0.24952659 | 0.69219860 |

単体はbaseline比development -81件、confirmation +73件、all -8件、McNemar p=0.96823。通常blendは-24/+45/+21件、p=0.81931、accuracy 4/7foldだった。通常blendのBrier/log lossは7/7fold改善したが方向accuracy増分がなく、方向モデルには採用しない。

## 方向維持confidence 0.515

development目的関数最大の固定閾値は0.515だった。

| 期間 | model | rows | coverage | accuracy | selection score |
|---|---|---:|---:|---:|---:|
| development | baseline | 158,280 | 58.52468% | 52.75588% | 0.019201 |
| development | EWMA | 158,222 | 58.50324% | 52.77837% | 0.019369 |
| confirmation | baseline | 63,694 | 37.59288% | 52.36600% | 0.012128 |
| confirmation | EWMA | 63,396 | 37.41700% | 52.48281% | 0.012808 |
| all | baseline | 221,974 | 50.46228% | 52.64400% | 0.017306 |
| all | EWMA | 221,618 | 50.38135% | 52.69382% | 0.017645 |

EWMAはbaselineにaccuracy 5/7、selection score 6/7、Brier/log loss 7/7、ECE 4/7fold勝った。UTC日20,000回paired bootstrapは次の通り。

| 期間 | accuracy差 | 95%区間 | score差 | 95%区間 |
|---|---:|---:|---:|---:|
| development | +0.02250pt | -0.03630〜+0.08022pt | +0.000168 | -0.000279〜+0.000609 |
| confirmation | +0.11681pt | +0.01697〜+0.21539pt | +0.000681 | +0.000069〜+0.001283 |
| all | +0.04982pt | -0.00011〜+0.10001pt | +0.000339 | -0.000016〜+0.000694 |

all accuracy区間は下限が僅かに0未満だが、confirmationではaccuracy・Wilson lower・selection scoreの全区間が改善側だった。all Brier差は-0.00000814、95%区間-0.00001334〜-0.00000294、log loss差は-0.00001632、区間-0.00002677〜-0.00000587で改善した。確認側の選別精度と全行確率品質が別々の指標で再現したため、parallel候補のgateを通す。

## Profile 0.515との直接比較

| 期間 | model | coverage | accuracy | selection score |
|---|---|---:|---:|---:|
| development | EWMA | 58.50324% | 52.77837% | 0.019369 |
| development | Profile | 58.55426% | 52.74754% | 0.019142 |
| confirmation | EWMA | 37.41700% | 52.48281% | 0.012808 |
| confirmation | Profile | 37.46894% | 52.51559% | 0.013020 |
| all | EWMA | 50.38135% | 52.69382% | 0.017645 |
| all | Profile | 50.43273% | 52.68116% | 0.017565 |

年別はEWMAがaccuracy 4/7、score 3/7、Profileが3/7・4/7。allのEWMA−Profile accuracyは+0.01266pt、bootstrap区間-0.04323〜+0.06927pt、scoreは+0.000080、区間-0.000316〜+0.000480で未確定だった。all Brier差+0.00000520、log loss差+0.00001040も区間が0を跨いだ。EWMAはbaselineへの独立edgeを持つが、Profile置換を支持しない。

Profile confidenceとEWMA confidenceの固定50/50はdevelopment scoreを+0.000070にした一方、confirmationは-0.000266、allは-0.000042となり、年別accuracy/score各3/7対4/7だった。weightや閾値を再探索せず、両候補を独立forward比較する。

## 信頼度・局所校正

EWMA 0.515 confirmationは63,396件、mean confidence 52.48282%、実測52.48281%、Wilson 52.09393〜52.87138%で完全に局所整合し、下限も50%を超えた。development/allはmean confidenceが実測を約0.58/0.42pt上回り、局所区間外なので履歴全体をfair odds認可には使わない。

方向×volatilityの固定6セルではconfirmationの5セルがWilson edgeを持ったが、down-normalは4,297件、accuracy 50.6633%、Wilson下限49.1685%で未確認だった。このセルは診断後に判明したため除外filterへ変換せず、同じ6セルをfresh期間で監視する。

0.55はall 23,668件・56.1222%・score 0.012732でProfileより点値が高かったが、confirmationは904件だけである。特にtest2026_partialは229件・47.5983%・Wilson下限41.2228%だった。Follow-through 0.55はall score 0.013413、confirmation 1,277件・57.6351%で上回るため、EWMAをprecision laneへ採用しない。

## 共有計算資源

実装テスト、7fold学習、blend、比較、20,000回bootstrapは単独8 thread、nice 10、低I/O優先度、CPU onlyで順番に実行した。GPUは非表示とし、画像生成・ローカルAI・その他の高負荷処理を停止していない。

## 判断

- EWMA 0.515をWindows canonicalのM5 parallel broad confidence候補として固定する。
- Profile 0.515を置換せず、固定50/50も使わない。
- 単体・通常blendを方向へ使わず、EWMA 0.55も使わない。
- half-life、clip、feature subset、25% weight、0.515を同じ履歴で再探索しない。
- 完全未使用期間でaccuracy、selection score、Brier、log loss、6局所セルとruntime blend parityを確認する。
- authoritative confidence、fair odds、paper/live policyは変更しない。

大きなmodel/parquetと比較・bootstrap・reliability成果物はWindows側だけに保存した。

MacとWindows/WSLの全体testはどちらも `1383 passed, 1 deselected, 83 subtests passed` だった。deselectは今回と無関係のentry-EV既存レポートに内部時刻がないdocs検査1件である。変更7ファイルとWindows側の新規EWMA成果物に対する口座・login・password/token/secret・private key形式のscanは0件だった。
