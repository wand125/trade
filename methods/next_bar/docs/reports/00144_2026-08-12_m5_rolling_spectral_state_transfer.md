# 00144 M5 Rolling Spectral State Fixed Transfer

日時: 2026-08-12 22:11 JST

## 結論

M1で実装済みのRolling Spectral Stateを、64完成足、固定周波数帯、12加工特徴、HGB/Platt、25% blend、閾値grid、標準損失1.0を変えずM5へ固定移植した。M5では直近320分のreturn列を価格履歴のまま使わず、周波数energy構成と位相へ圧縮する。

Spectral単体はbaseline比development -74件、confirmation +16件、all -58件だった。通常25%方向blendも-40/+29/-11件、accuracy 4/7foldで、方向用途には採用しない。

baseline方向を保存した25% confidenceはdevelopment目的関数から0.515を選んだ。confirmationのaccuracyはbaselineより+0.10288ptで日次bootstrap区間も僅かに改善側だったが、coverageは-0.51466ptへ確定低下し、selection scoreとproper scoreの区間は0を跨いだ。allもaccuracy、selection score、Brier、log lossの区間が全て0を跨ぎ、baseline adoption gateを通らない。

0.515はProfile/Haarにaccuracy・selection score 3/7対4/7、Profileとの固定50/50 confidence平均もProfileに3/7対4/7だった。0.55はFollow-throughよりconfirmation/allのaccuracy、coverage、selection score、proper scoreが全て低い。したがってM5 Rolling Spectral Stateは再現・独立研究用に保存し、config、registry、authoritative予測、fair odds、paper/live policyを変更しない。

## 固定加工と学習

各decision時点までの直近64本のlog returnを平均除去し、DFT energyを総分散で正規化した。追加12列は次の通り。

- low energy比 k1〜2、mid energy比 k3〜6、残差high energy比 k7以上
- low−high energy balance
- k=1/2/4/8、周期64/32/16/8本の正規化cos/sin成分8列

baseline 38列 + Spectral 12列 = 50加工特徴である。raw OHLC価格水準、volume、未来足、targetはmodel特徴へ含めない。flat、不正値、gapを含む64本窓は全12列を0へ戻す。

- HGB 200 iteration、learning rate 0.05、31 leaves、min leaf 100、L2 1
- expanding、最大750,000 train行、uniform weighting、全教師
- calibration期間だけのPlatt、seed 42
- baseline 75% + Spectral 25%、方向維持confidenceも25%
- development固定grid 0.51/0.515/0.525/0.535/0.55
- 主目的関数 `sqrt(coverage) * (Wilson95Lower(accuracy) - 0.50)`
- 標準損失1.0

M5結果を見てwindow、frequency、band、phase subset、model parameter、weight、threshold、subgroup filterを再探索していない。

## 単体と方向blend

| period | baseline | Spectral単体 | baseline 75% + Spectral 25% |
|---|---:|---:|---:|
| development | 51.91385% | 51.88649% | 51.89906% |
| confirmation | 51.03316% | 51.04261% | 51.05028% |
| all | 51.57463% | 51.56145% | 51.57213% |

Spectral単体はbaseline比-74/+16/-58件、通常blendは-40/+29/-11件だった。通常blendはaccuracy 4/7、Brier/log loss 5/7foldで、all Brierは0.249535053から0.249532677、log lossは0.692215561から0.692210855へ僅かに改善した。しかしconfirmation proper scoreは悪化し、accuracy点値もallでbaseline未満である。aggregate確率平滑化を方向edgeとは解釈しない。

## Broad confidence 0.515

| period | rows | coverage | accuracy | selection score |
|---|---:|---:|---:|---:|
| development | 158,345 | 58.54872% | 52.77401% | 0.019344 |
| confirmation | 62,822 | 37.07822% | 52.46888% | 0.012655 |
| all | 221,167 | 50.27883% | 52.68734% | 0.017579 |

baseline比accuracyは4/7、selection scoreは6/7、Brier/log lossは各4/7、ECEは6/7fold改善した。20,000回UTC日bootstrapは次の通り。

| period | accuracy差95%区間 | coverage差95%区間 | score差95%区間 | Brier差95%区間 | log loss差95%区間 |
|---|---:|---:|---:|---:|---:|
| development | -0.03458〜+0.07032pt | -0.04357〜+0.09130pt | -0.000260〜+0.000541 | -0.00001191〜+0.00000160 | -0.00002384〜+0.00000333 |
| confirmation | +0.00136〜+0.20472pt | -0.58590〜-0.44245pt | -0.000092〜+0.001148 | -0.00000251〜+0.00000727 | -0.00000502〜+0.00001457 |
| all | -0.00387〜+0.09065pt | -0.23546〜-0.13089pt | -0.000060〜+0.000609 | -0.00000686〜+0.00000228 | -0.00001372〜+0.00000466 |

confirmation accuracyだけは改善側だが、coverage低下を含む主目的関数とproper scoreは未確定である。allも全主指標が未確定なので採用しない。

## 既存候補と固定多様化

Profile 0.515比はaccuracy/score 3/7。Spectralはdevelopmentでaccuracy +0.02647pt、score +0.000202だったが、confirmationでaccuracy -0.04671pt、score -0.000365へ反転した。allはaccuracy +0.00617pt、score +0.000015でもcoverage -0.15391ptで、Brier/log lossはProfileが良い。

Haar 0.515比もaccuracy/score 3/7。allでSpectralはaccuracy -0.01105pt、coverage -0.08480pt、score -0.000094、confirmationでも3指標を下げた。既存独立challengerを置換しない。

ProfileとSpectral confidenceの固定50/50平均はall accuracy 52.69004%、coverage 50.32975%、score 0.017608でProfile点値を僅かに上げたが、confirmation accuracy 52.45800%、score 0.012622へ低下し、年別accuracy/score 3/7対4/7だった。追加stackを発行しない。

## High confidence 0.55

| period | Spectral rows / accuracy / score | Follow-through rows / accuracy / score |
|---|---:|---:|
| development | 23,136 / 56.04685% / 0.015813 | 23,388 / 56.09714% / 0.016057 |
| confirmation | 836 / 58.25359% / 0.003428 | 940 / 58.51064% / 0.003972 |
| all | 23,972 / 56.12381% / 0.012827 | 24,328 / 56.19040% / 0.013090 |

Spectralは年別accuracy/score 4/7でも、全3期間のcoverageが低下した。20,000回日次bootstrapでall coverage差は-0.10691〜-0.05462pt、Brier差は+0.00000353〜+0.00001379、log loss差は+0.00000717〜+0.00002780となり、proper score劣後が確定した。confirmation proper scoreも劣後側で、precision roleを置換しない。

## 信頼度と固定subgroup

Spectral confirmation累積帯は次の通り。

| threshold | rows | coverage | accuracy | mean confidence | Wilson lower |
|---:|---:|---:|---:|---:|---:|
| 0.515 | 62,822 | 37.07822% | 52.46888% | 52.47301% | 52.07822% |
| 0.525 | 24,079 | 14.21168% | 53.17497% | 53.33081% | 52.54424% |
| 0.535 | 7,722 | 4.55761% | 54.93395% | 54.19983% | 53.82200% |
| 0.550 | 836 | 0.49342% | 58.25359% | 55.52065% | 54.88037% |

confirmationは4帯とも局所整合しaccuracyも単調上昇した。一方development 0.515は実測52.77401%に対しmean 53.37046%、allは52.68734%対53.11554%で過信し、期間横断fair odds条件を満たさない。

方向×volatility固定6セルのconfirmation 0.515ではdown-normalが4,198件・50.57170%・Wilson下限49.05944%でedge未確認だった。0.55はup-high 614件・59.12052%・Wilson下限55.18690%だけがedgeを確認し、他5セルは4〜93件またはWilson下限50%以下だった。診断後のsubgroup filterは作らない。

## Runtimeと共有資源

最終fold artifactの50特徴から2026-06-01 04:55 UTCを再推論し、`p(up)=0.5213385371` を得た。context filterは接続せず、経験的oddsも認可していないため `odds_valid=false`、`strict_prediction_eligible=false` である。confidence blendの完全runtime parityは不採用のため発行しない。

最初の起動はWindows仮想環境にconsole script `trade-next-bar` が存在せず、学習開始・出力作成前に終了した。依存追加や環境変更をせず、同じ仮想環境の `python -m trade_data.next_bar` へ切り替えて固定コマンドを再実行した。

学習、blend、比較、20,000回bootstrap、reliability、subgroup、latest推論はWindows/WSL2の単独workerで順番に実行した。標準8 thread、nice 10、I/O低優先度、CPU only、available memory 16GiB/load 8 gateを維持し、ComfyUI画像生成・Claude・Open WebUI・Ollama等を停止していない。

## 判断

- Spectral単体、通常25%方向、方向維持0.515/0.55、Profile×Spectral confidence平均をすべて再現専用とする。
- M1固定の64本、band、phase、12特徴、HGB/Platt、25%を維持し、M5履歴へ合わせて再探索しない。
- Pressure方向、Profile/EWMA/Haar 0.515、Profile×TCN shadow、Follow-through 0.55を置換しない。
- config、registry、authoritative予測、fair odds、paper/live policyを変更しない。
- model/parquet、比較、bootstrap、reliability成果物はWindows側だけに保存する。

## 検証

- M5転移の定常性、raw OHLC除外、有限性、[-1,1]境界、価格10倍scale不変: 2 passed、91 deselected
- Mac全体テスト（既知の無関係な文書時刻テストを除外）: 1389 passed、1 deselected、280 warnings、83 subtests、124.92秒
- Windows/WSL2全体テスト（同じ1件を除外、nice 10・I/O低優先度）: 1389 passed、1 deselected、280 warnings、83 subtests、50.23秒
- 除外した既知失敗: `methods/entry_ev/tests/test_docs_reports.py::DocsReportTests::test_report_numbers_follow_internal_report_time`。既存レポート `00384_2026-07-08_mql5_mt5_paid_expert_top_analysis.md` の内部時刻欠落であり、本実験の変更範囲外である。
