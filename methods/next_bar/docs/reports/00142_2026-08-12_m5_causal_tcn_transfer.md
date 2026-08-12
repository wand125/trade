# 00142 M5 Causal TCN Fixed Transfer

日時: 2026-08-12 18:23 JST

## 結論

M15で定義しM1でも固定検証した小型causal TCNを、sequence、network、8 epoch、Platt、25% blend、閾値gridを変更せずM5へ移植した。Windows/WSL2 canonical環境で439,881 OOS行・7foldを作り、baseline、Pressure方向、Profile/EWMA broad confidence、Follow-through high-confidenceと同一行比較した。

TCN単体はbaselineより741件悪く、通常25%方向blendの+61件も日次bootstrap区間が0を跨ぎ、Pressureを超えなかった。TCN単独の方向維持0.515はbaselineより全期間accuracyを改善したが、coverage-aware scoreとproper scoreの安定性が不足し、Profile/EWMAを上積みしなかった。0.55はFollow-throughへ明確に劣後した。

一方、事前に中立な固定50/50でProfile confidenceとTCN confidenceを平均すると、baseline比accuracy 7/7、selection score 6/7、Brier/log loss 5/7fold改善し、confirmationと全期間のaccuracy・selection score、全期間proper scoreの日次bootstrap区間も改善側となった。親Profileとの差はaccuracy 5/7、score 4/7で、全期間accuracy差区間の下限が-0.00046pt、score差も0を跨ぎ、confirmation scoreは僅かに低い。

したがって単独TCNと方向用途は再現専用とし、Profile×TCN固定平均0.515だけを `m5_profile_tcn_confidence_shadow_v1.json` の非権威parallel shadowへ固定する。Profile/EWMA 0.515、Pressure方向、Follow-through 0.55、authoritative confidence、fair odds、paper/live policyは置換しない。

## 固定したsequence学習

- 完成M5足16本 × 5加工channel
- ATR正規化return、body、range、中心化close location、ATR正規化wick balance
- baseline 38列 + sequence 80列 = 118加工特徴
- 各foldのtrainだけでchannel mean/stdを推定
- causal Conv1d 2層、kernel 3、dilation 1/2、hidden 16、1,073 parameter
- AdamW、8 epoch、batch 2,048、learning rate 0.001、weight decay 0.0001、seed 42
- expanding、最大750,000 train行、calibration期間だけのPlatt、uniform weighting、全教師
- raw OHLC水準、volume、未来足をmodel特徴へ含めない
- 損失倍率は標準1.0

M5結果を見てsequence長、channel、network容量、epoch、学習率、blend weightを再探索していない。M5回帰テストでは118特徴、sequence 80列、raw OHLC除外、有限性、価格10倍scale不変を確認する。

## 単体と方向blend

| period | baseline | TCN単体 | baseline 75% + TCN 25% |
|---|---:|---:|---:|
| development | 51.91385% | 51.73045% | 51.93086% |
| confirmation | 51.03316% | 50.88856% | 51.04202% |
| all | 51.57463% | 51.40618% | 51.58850% |

TCN単体はbaseline比-496/-245/-741件、accuracy・Brier・log loss各1/7foldで不採用。通常blendは+46/+15/+61件、accuracy 4/7、Brier/log loss各3/7foldだった。baseline比all accuracy差+0.01387ptの20,000回UTC日bootstrap区間は-0.03998〜+0.06801ptで0を跨いだ。

現行Pressure方向に対して通常TCN blendは全期間-35件、accuracy 3/7対4/7、Brier/log lossも点値で劣った。固定Pressure×TCN 50/50方向平均もPressure比-72件、accuracy 2/7対5/7で、confirmationを悪化させた。方向候補へ追加しない。

## TCN単独confidence 0.515

developmentの固定grid 0.51/0.515/0.525/0.535/0.55でTCN confidenceの目的関数最大は0.515だった。

| period | rows | coverage | accuracy | selection score |
|---|---:|---:|---:|---:|
| development | 154,440 | 57.10483% | 52.81663% | 0.019403 |
| confirmation | 60,571 | 35.74966% | 52.49212% | 0.012522 |
| all | 215,011 | 48.87936% | 52.72521% | 0.017577 |

baseline比accuracyは5/7、score 4/7、Brier/log loss各3/7foldだった。all accuracy差+0.08121ptのbootstrap区間は+0.00941〜+0.15343ptだが、coverageは-1.58293pt、score差区間は-0.000234〜+0.000777、Brier/log lossも0を跨いだ。confirmation accuracy・score区間も0を跨ぐため、TCN単独confidenceを候補化しない。

Profile 0.515にはall accuracy +0.04405ptでも区間-0.02776〜+0.11601pt、score +0.000012の区間-0.000495〜+0.000517で、confirmation scoreは-0.000498だった。foldはaccuracy 5/7、score 3/7。EWMAにはaccuracy 4/7、score 2/7で、all score -0.000068だった。既存broad候補を超えない。

0.55はall 19,478件・55.67820%・score 0.010478、confirmation 548件・57.48175%だった。Follow-throughはall 24,328件・56.19040%・0.013090で、TCN差はaccuracy -0.51220pt、score -0.002611、両95%区間が劣後側だった。high-confidence用途にも使わない。

## Profile × TCN固定50/50 confidence shadow

ProfileとTCNはともにbaseline方向を保存した75/25 confidence blendである。この2本を固定50/50平均したため、最終確率はbaseline 75%、Profile 12.5%、TCN 12.5%に等価である。weight探索は行っていない。

| period | baseline rows / accuracy / score | 固定平均 rows / accuracy / score |
|---|---:|---:|
| development | 158,280 / 52.75588% / 0.019201 | 156,442 / 52.81382% / 0.019519 |
| confirmation | 63,694 / 52.36600% / 0.012128 | 61,901 / 52.51773% / 0.012839 |
| all | 221,974 / 52.64400% / 0.017306 | 218,343 / 52.72988% / 0.017757 |

baseline比はaccuracy 7/7、selection score 6/7、Brier/log loss/ECE各5/7fold改善した。20,000回日次bootstrapの差は次の通り。

| period | accuracy差95%区間 | score差95%区間 |
|---|---:|---:|
| development | -0.00578〜+0.12176pt | -0.000167〜+0.000802 |
| confirmation | +0.04056〜+0.26355pt | +0.000038〜+0.001392 |
| all | +0.03039〜+0.14123pt | +0.000061〜+0.000839 |

all Brier差区間は-0.00001878〜-0.00000603、log lossは-0.00003768〜-0.00001198で改善側だった。confirmation proper score差は0を跨ぐが、accuracy/coverage目的と全体確率品質のbaseline gateは通過した。

### 親ProfileとEWMAへの増分

Profile比はaccuracy 5/7、score 4/7。all accuracy +0.04872ptの区間は-0.00046〜+0.09864pt、score +0.000192の区間は-0.000157〜+0.000544で0を跨いだ。coverageは-0.79590ptで低下が確定し、confirmation scoreも-0.000180だった。親を置換する証拠ではない。

EWMA比はaccuracy 6/7、score 4/7で、all accuracy +0.03605pt、score +0.000112、proper scoreは点改善したが全区間が0を跨いだ。0.55はFollow-throughへdevelopment/confirmation/allのselection score区間が全て劣後側だった。既存候補を履歴上の僅差で置換・stack拡張しない。

## 信頼度と固定subgroup

固定平均のconfirmation累積帯は次の通り。

| threshold | rows | coverage | accuracy | mean confidence | Wilson lower |
|---:|---:|---:|---:|---:|---:|
| 0.515 | 61,901 | 36.53464% | 52.51773% | 52.44379% | 52.12419% |
| 0.525 | 22,912 | 13.52291% | 53.44797% | 53.30195% | 52.80156% |
| 0.535 | 6,982 | 4.12085% | 55.18476% | 54.17790% | 54.01572% |
| 0.550 | 701 | 0.41374% | 56.49073% | 55.49091% | 52.79511% |

confirmationは4帯ともmean confidenceがWilson区間内で、accuracyも閾値とともに単調上昇した。一方development 0.515は実測52.81382%に対しmean 53.30147%、allは52.72988%対53.05832%で過信し、期間横断のfair odds条件を満たさない。

方向×volatility固定6セルのconfirmation 0.515ではdown-normalが4,152件・50.96339%・Wilson下限49.44260%でedge未確認だった。0.55はup-high 511件だけがedgeを確認し、他5セルは3〜77件またはWilson下限50%未満だった。診断後のsubgroup filterは作らない。

## Runtimeと共有資源

TCN最終fold artifactは118特徴からlatest推論を再現した。2026-06-01 04:55 UTCのM5は `p(up)=0.5161988528`、`odds_valid=false`、`strict_prediction_eligible=false` だった。固定Profile×TCN ensembleの完全runtime artifactは運用用に発行しておらず、shadow昇格条件として確率parityを残す。

学習・blend・比較・20,000回bootstrap・reliability・subgroup・latest推論はWindows/WSL2の単独workerで順番に実行した。標準8 thread、nice 10、I/O低優先度、CPU only、available memory 16GiB/load 8 gateを維持し、利用中の画像生成GPUや他処理を停止していない。

## 検証

Macのfull suiteは1,387 passed、1 deselected、281 warnings、83 subtests passed（119.39秒）、Windows/WSL2は1,387 passed、1 deselected、280 warnings、83 subtests passed（46.76秒）だった。既知のdeselectは `DocsReportTests::test_report_numbers_follow_internal_report_time` で、本変更とは無関係である。コミット対象5ファイルと今回のWindows JSON成果物を、account/login/password/token/secret/API key/private key形式で値を表示せず検査し、一致0件を確認した。口座runtime、認証情報、個人設定は同期・コミットしていない。

## 判断

- TCN単体、通常25%方向、TCN単独confidence 0.515/0.55、Pressure×TCN方向平均を再現専用とする。
- Profile×TCN固定50/50 confidence 0.515だけを非権威parallel forward shadowへ固定する。
- Profile/EWMA broad confidence、Pressure方向、Follow-through high-confidence、authoritative confidence・fair odds・policyは置換しない。
- 完全未使用期間でProfileにaccuracy、selection score、Brier、log lossが同時非劣後、down-normal Wilson edge、global/local calibration、runtime parityを要求する。
- sequence、network、epoch、weight、閾値、subgroup filterを同じ履歴で再探索しない。
- 大きなmodel/parquet、比較、bootstrap、reliability成果物はWindows側だけに保存する。
