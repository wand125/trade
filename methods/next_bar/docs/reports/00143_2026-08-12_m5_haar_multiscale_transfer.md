# 00143 M5 Haar Multiscale Fixed Transfer

日時: 2026-08-12 21:48 JST

## 結論

M1で方向blendを7/7fold改善し、M30で方向多様化candidateの構成要素になったHaar Multiscaleを、4/8/16/32本、12加工特徴、HGB/Platt、25% blend、閾値grid、標準損失1.0を変えずM5へ固定移植した。Windows/WSL2 canonical環境でbaseline、Intrabar Pressure、Intrabar Profile、EWMA Asymmetry、Profile×TCN、Directional Follow-throughと同じ439,881 OOS行・7foldを比較した。

Haar単体はbaseline比-42件だった。通常25%方向blendは+111件、confirmation +94件、proper scoreを改善したが、accuracy差区間は0を跨ぎ、現行Pressureよりall +15件でもdevelopmentとproper scoreで劣った。Pressure×Haar固定平均もPressureにaccuracy/score 2/7foldで、方向用途は不採用とする。

baseline方向を保存した25% confidenceのdevelopment目的関数最大は0.515だった。confirmationとallのaccuracy、selection score、Brier、log lossはbaseline比20,000回日次bootstrap区間がすべて改善側で、accuracy/score 5/7、proper score 6/7foldだった。一方Profileにはaccuracy/score 5/7でもall proper scoreが有意に劣り、EWMAには4/7、Profile×TCNには3/7だった。

したがってHaar 0.515だけを `m5_haar_multiscale_confidence_candidate_v1.json` の独立parallel broad-confidence challengerへ固定する。Profile/EWMA、Profile×TCN shadow、Pressure方向、Follow-through 0.55、authoritative confidence、fair odds、paper/live policyは置換しない。

## 固定加工と学習

各4/8/16/32本窓を前半と後半へ分け、次の3量を作る。

- rolling volatilityで正規化した後半return−前半return
- 全absolute returnに対する後半−前半構成比
- 後半方向平均−前半方向平均を[-1, 1]へ正規化

baseline 38列 + Haar 12列 = 50加工特徴である。raw OHLC価格水準、volume、未来足、targetはmodel特徴へ含めない。0/0は変化の証拠なしの0とし、M5回帰テストでは12列、全50列、有限性、raw OHLC除外、価格10倍scale不変を確認する。

- HGB 200 iteration、learning rate 0.05、31 leaves、min leaf 100、L2 1
- expanding、最大750,000 train行、uniform weighting、全教師
- calibration期間だけのPlatt、seed 42
- baseline 75% + Haar 25%、方向維持confidenceも25%
- development固定grid 0.51/0.515/0.525/0.535/0.55
- 主目的関数 `sqrt(coverage) * (Wilson95Lower(accuracy) - 0.50)`
- 標準損失1.0

M5結果を見てwindow、feature、model parameter、weight、threshold、subgroup filterを再探索していない。

## 単体と方向blend

| period | baseline | Haar単体 | baseline 75% + Haar 25% |
|---|---:|---:|---:|
| development | 51.91385% | 51.83731% | 51.92013% |
| confirmation | 51.03316% | 51.13055% | 51.08864% |
| all | 51.57463% | 51.56508% | 51.59986% |

Haar単体はbaseline比-207/+165/-42件だった。通常blendは+17/+94/+111件、accuracy 4/7、Brier/log loss各5/7fold。baseline比all accuracy差+0.02523ptの95%区間は-0.01271〜+0.06365ptで0を跨いだ。一方all Brier差区間-0.00001205〜-0.00000187、log lossは-0.00002419〜-0.00000374で改善側だった。

現行Pressure方向に対し、Haar blendはdevelopment -65件、confirmation +80件、all +15件、accuracy 4/7対3/7だった。しかしall Brier差区間+0.00000033〜+0.00001316、log loss +0.00000063〜+0.00002645でHaarが有意に悪かった。固定Pressure×Haar 50/50もPressure比all -38件、accuracy/score 2/7対5/7で、development proper scoreも有意に悪化した。方向候補を増やさない。

## Broad confidence 0.515

| period | rows | coverage | accuracy | selection score |
|---|---:|---:|---:|---:|
| development | 158,322 | 58.54021% | 52.76967% | 0.019309 |
| confirmation | 63,218 | 37.31194% | 52.51985% | 0.013013 |
| all | 221,540 | 50.36362% | 52.69838% | 0.017674 |

baseline比accuracy/scoreは各5/7、Brier/log loss/ECEは各6/7fold改善した。20,000回UTC日bootstrapは次の通り。

| period | accuracy差95%区間 | score差95%区間 | Brier差95%区間 | log loss差95%区間 |
|---|---:|---:|---:|---:|
| development | -0.04171〜+0.06807pt | -0.000316〜+0.000522 | -0.00001462〜+0.00000033 | -0.00002943〜+0.00000070 |
| confirmation | +0.05684〜+0.25100pt | +0.000295〜+0.001479 | -0.00001073〜-0.00000011 | -0.00002150〜-0.00000020 |
| all | +0.00693〜+0.10263pt | +0.000031〜+0.000709 | -0.00001148〜-0.00000148 | -0.00002309〜-0.00000294 |

confirmationとallではaccuracy/coverage-aware score/proper scoreが同時に改善した。coverageはconfirmation -0.28094pt、all -0.09866ptで低下が確定したが、selection score区間は改善側なのでbaseline adoption gateを通過した。

## 既存候補への増分

Profile 0.515比はaccuracy/score 5/7。all accuracy +0.01722pt、score +0.000109の区間は0を跨ぎ、confirmation scoreは-0.000006で同等だった。all coverageは-0.06911ptへ確定低下し、Brier差区間+0.00000065〜+0.00001306、log loss +0.00000122〜+0.00002616でProfileが有意に良い。Profileを置換しない。

EWMA比はaccuracy/score 4/7で、all accuracy +0.00456pt、score +0.000029、proper score差も全て未確定だった。Profile×TCN shadow比はaccuracy/score 3/7、all accuracy -0.03150pt、score -0.000083だが、coverageを+0.72679pt増やした。相互に優位は確定しないが、履歴内の候補poolをstack・再weightしない。

Profile×Haar固定50/50はbaseline比accuracy/score 6/7だったが、Profile比4/7、EWMA比3/7、Profile×TCN比1/7だった。追加ensembleは不採用とする。

## High confidence 0.55

Haar 0.55はall 23,721件・coverage 5.39259%・accuracy 56.21601%・score 0.012966、confirmation 901件・57.71365%・0.003254だった。Follow-throughはall 24,328件・56.19040%・0.013090、confirmation 940件・58.51064%・0.003972である。

Haarはaccuracy 4/7でもscore 3/7、all coverage -0.13799pt、score -0.000123、confirmation accuracy -0.79699pt、score -0.000718だった。差区間はaccuracy/scoreとも0を跨ぐが、coverage区間は劣後側で、precision roleを置換しない。

## 信頼度と固定subgroup

Haar confirmation累積帯は次の通り。

| threshold | rows | coverage | accuracy | mean confidence | Wilson lower |
|---:|---:|---:|---:|---:|---:|
| 0.515 | 63,218 | 37.31194% | 52.51985% | 52.48034% | 52.13044% |
| 0.525 | 24,375 | 14.38639% | 53.25538% | 53.33888% | 52.62855% |
| 0.535 | 7,861 | 4.63965% | 55.27287% | 54.21296% | 54.17140% |
| 0.550 | 901 | 0.53178% | 57.71365% | 55.53263% | 54.46182% |

confirmationは4帯ともmean confidenceがWilson区間内で、accuracyも単調上昇した。一方development 0.515は実測52.76967%に対しmean 53.36311%、allは52.69838%対53.11120%で過信し、期間横断fair odds条件を満たさない。

方向×volatility固定6セルのconfirmation 0.515では、down-normalが4,239件・50.97900%・Wilson下限49.47389%でedge未確認だった。0.55はup-high 669件だけがedgeを確認し、他5セルは5〜89件またはWilson下限50%以下だった。診断後のsubgroup filterは作らない。

## Runtimeと共有資源

最終fold artifactの50特徴から2026-06-01 04:55 UTCを再推論し、`p(up)=0.5184021044` を得た。context filterは接続せず、経験的oddsも認可していないため `odds_valid=false`、`strict_prediction_eligible=false` である。完全なbaseline×Haar runtime blend parityはforward昇格条件として残す。

学習、blend、比較、20,000回bootstrap、reliability、subgroup、latest推論はWindows/WSL2の単独workerで順番に実行した。標準8 thread、nice 10、I/O低優先度、CPU only、available memory 16GiB/load 8 gateを維持し、ComfyUI画像生成・ローカルAI・他処理を停止していない。

## 判断

- Haar単体、通常25%方向、Pressure×Haar方向平均、Haar 0.55、Profile×Haar confidence平均を再現専用とする。
- Haar方向維持25% confidence 0.515だけを独立parallel broad-confidence challengerへ固定する。
- Profile/EWMA、Profile×TCN shadow、Pressure方向、Follow-through 0.55を置換しない。
- 完全未使用期間でProfileおよびProfile×TCN以上のaccuracy/selection score、Profile以下のBrier/log loss、down-normal Wilson edge、global/local calibration、full runtime parityを要求する。
- window、feature、model parameter、weight、threshold、subgroup filterを同じ履歴で再探索しない。
- authoritative予測、fair odds、paper/live policyを変更しない。
- 大きなmodel/parquet、比較、bootstrap、reliability成果物はWindows側だけに保存する。

## 検証

- 追加したM5 Haar加工・文書テスト: 3 passed、1 deselected
- Mac全体テスト（既知の無関係な文書時刻テストを除外）: 1388 passed、1 deselected、280 warnings、83 subtests、117.67秒
- Windows/WSL2全体テスト（同じ1件を除外、nice 10・I/O低優先度）: 1388 passed、1 deselected、280 warnings、83 subtests、48.64秒
- 除外した既知失敗: `methods/entry_ev/tests/test_docs_reports.py::DocsReportTests::test_report_numbers_follow_internal_report_time`。既存レポート `00384_2026-07-08_mql5_mt5_paid_expert_top_analysis.md` の内部時刻欠落であり、本実験の変更範囲外である。
