# 00158 M5 LightGBM Fixed Transfer

日時: 2026-08-15 00:07 JST

## 目的

M1で異種学習器方向co-challenger、M30で方向ensemble構成要素になった固定LightGBMを、未検証だったM5へ移植する。生OHLC水準ではなく加工済みbaseline 38特徴を入力し、HGBと異なるleaf-wise GBDTの誤りが方向、broad confidence、高信頼度のいずれかを補完するかを確認する。

## 固定仕様と資源品質

LightGBM 4.7.0、GBDT、300 trees、31 leaves、learning rate 0.03、min child 100、row/column sample 0.8、L2 5、seed 42、deterministic、force column-wiseを固定した。expanding train最大750,000行、全教師、uniform sample、後続calibration期間のPlatt、標準損失1.0、baseline 38特徴を使い、early stoppingは使わない。test2020〜test2026途中の固定7fold、439,881 OOS行をWindows canonical環境で学習し、正式baselineとtimestamp/targetを完全整列した。

共有Windowsで全CPUを占有しないよう `--lightgbm-n-jobs` を追加した。pipeline testでCLI値がreportと保存modelへ伝播することを確認し、正式実験は8 jobs、単独worker、nice 10、ionice 7、GPU非表示、memory/load gate付きで実行した。ComfyUI/Ollamaは停止していない。

## 単体方向と固定25% blend

| model | development accuracy | confirmation accuracy | all accuracy | all Brier | all log loss | all ECE |
|---|---:|---:|---:|---:|---:|---:|
| HGB baseline | 51.91385% | 51.03316% | 51.57463% | 0.249535053 | 0.692215561 | 0.36137% |
| LightGBM単体 | 51.88538% | 51.08628% | 51.57759% | 0.249544906 | 0.692235438 | 0.40067% |
| baseline 75% + LightGBM 25% | 51.94343% | 51.02490% | 51.58963% | 0.249530288 | 0.692206020 | 0.34873% |

単体はbaseline比development -77件、confirmation +90件、all +13件、McNemar all p=0.94136で、accuracy 4/7、Brier/log loss各3/7foldだった。通常25%方向blendは+80/-14/+66件、p=0.42394、accuracy 6/7foldだがconfirmationが反転した。

既存Intrabar Pressure方向blendはdevelopment 51.94417%、confirmation 51.04143%、all 51.59645%で、LightGBM blendはaccuracy 3/7、Brier/log loss/ECEも全期間で悪い。方向用途へ採用しない。

## 方向維持confidence 0.515

development gridだけで0.515を選んだ。

| period | LightGBM rows / coverage / accuracy / score | Profile rows / coverage / accuracy / score | Profile×Transition rows / coverage / accuracy / score |
|---|---:|---:|---:|
| development | 158,655 / 58.66334% / 52.77615% / 0.0193811 | 158,360 / 58.55426% / 52.74754% / 0.0191423 | 151,362 / 55.96672% / 52.91355% / 0.0199147 |
| confirmation | 63,678 / 37.58344% / 52.42784% / 0.0125051 | 63,484 / 37.46894% / 52.51559% / 0.0130197 | 59,574 / 35.16122% / 52.55313% / 0.0127606 |
| all | 222,333 / 50.54390% / 52.67639% / 0.0175518 | 221,844 / 50.43273% / 52.68116% / 0.0175648 | 210,936 / 47.95297% / 52.81175% / 0.0179952 |

baseline比ではaccuracy/selection score各5/7fold、Brier/log loss各4/7、ECE 5/7で、点値は僅かに改善した。親Profileにはaccuracy 4/7、score 5/7だが、developmentの微増をconfirmationで反転し、all accuracy/scoreはほぼ同値、Brier/log lossは悪い。

現行Profile×Transition broad shadowにはaccuracy 0/7、selection score 2/7foldだった。LightGBMはcoverageを+2.59193pt広げる代わりにall accuracy -0.13536pt、score -0.0004435、Brier/log loss/ECEを悪化させる。broad confidenceへ採用せず、0.515のbootstrapや別閾値探索へ計算を広げない。

## 高信頼度0.55と直接bootstrap

| period | LightGBM rows / coverage / accuracy / score | Follow-through rows / coverage / accuracy / score |
|---|---:|---:|
| development | 23,650 / 8.74468% / 56.19873% / 0.0164578 | 23,388 / 8.64781% / 56.09714% / 0.0160568 |
| confirmation | 873 / 0.51525% / 57.50286% / 0.0030132 | 940 / 0.55480% / 58.51064% / 0.0039719 |
| all | 24,523 / 5.57492% / 56.24516% / 0.0132774 | 24,328 / 5.53059% / 56.19040% / 0.0130897 |

LightGBMは点値でaccuracy/score各5/7fold、all accuracy +0.05476pt、score +0.0001877だった。しかし20,000回のUTC日paired bootstrapは次の通りである。

| period / LightGBM−Follow-through | point delta | 95% interval | 判断 |
|---|---:|---:|---|
| development accuracy | +0.10159pt | -0.11420〜+0.31608pt | 未確定 |
| development score | +0.0004010 | -0.0002359〜+0.0010299 | 未確定 |
| confirmation accuracy | -1.00777pt | -2.65408〜+0.64878pt | 反転・未確定 |
| confirmation score | -0.0009587 | -0.0021554〜+0.0002408 | 反転・未確定 |
| all accuracy | +0.05476pt | -0.16161〜+0.26837pt | 未確定 |
| all score | +0.0001877 | -0.0003197〜+0.0006904 | 未確定 |

coverage増加だけはdevelopment/allで区間全体が正だったが、confirmationは区間全体が負だった。さらに全行Brier差+0.000006262の95%区間は+0.000001645〜+0.000010754、log loss差+0.000012641は+0.000003359〜+0.000021672で、LightGBMの確率品質悪化が確定した。高信頼度点値だけでFollow-throughを置換または並列追加しない。

## 固定平均と局所信頼度

Follow-through confidenceとLightGBM confidenceの固定50/50平均はall 24,372件、coverage 5.54059%、accuracy 56.18333%、score 0.0130861で、Follow-throughの56.19040% / 0.0130897にもLightGBMの56.24516% / 0.0132774にも届かなかった。別weightを探索しない。

LightGBM 0.55は全体ではmean confidence 56.36138%、accuracy 56.24516%で局所整合し、confidence band accuracyも単調だった。しかし方向×volatility固定6セルではdown×highがdevelopment 6,379件・55.36918%からconfirmation 78件・47.43590%へ崩れた。up×highはdevelopment 8,122件・57.74440%、confirmation 648件・58.64198%で再現したため、同じ固定セルのFollow-throughと直接比較した。

up×highでLightGBMはall 8,770件・57.81072%、Follow-throughは8,714件・57.55107%だった。20,000回bootstrapのall accuracy差+0.25965ptは95%区間-0.11354〜+0.63112pt、score差+0.0004018も-0.0001218〜+0.0009210で未確定だった。confirmation accuracyは-0.23248ptへ反転したため、結果後の局所候補を発行しない。

## 判断

M5 LightGBMは単体、通常方向、0.515 broad、0.55 high-confidence、Follow-throughとの固定平均、up×high局所セルの全てを再現専用とする。方向はPressure、broad confidenceはProfileとProfile×Transition、high-confidenceはFollow-throughが同じ役割で上回り、LightGBM固有の再現可能な増分edgeは得られなかった。

新config、registry候補、latest artifact、authoritative予測、fair odds、paper/live policyを発行しない。31 leaves、300 trees、学習率0.03、min child 100、row/column 0.8、L2 5、25% weight、0.515/0.55、subgroup filterを同じ履歴で再探索しない。

## 検証

WindowsでLightGBM job数のpipeline testが成功した。全suiteは既知のEntry EV文書内部時刻1件だけを除外し、1,401件成功、1件除外、55.46秒だった。Macは共有中の高負荷処理へ追加負荷をかけないため全suiteを重ねず、Windows canonical結果を採用した。

## 成果物

- OOS: `experiments/next_bar/lightgbm_m5_windows_canonical_001`
- normal/confidence blends: `experiments/next_bar/lightgbm_m5_{direction,confidence}_blend_windows_canonical_001`
- candidate分析: `experiments/next_bar/lightgbm_m5_candidate_analysis.json`
- Pressure/Profile/Profile×Transition/Follow-through比較: `experiments/next_bar/lightgbm_vs_*_m5_*_analysis.json`
- high-confidence bootstrap: `experiments/next_bar/lightgbm_vs_follow_through_m5_confidence_055_daily_bootstrap.json`
- rejected equal blend: `experiments/next_bar/follow_through_lightgbm_equal_m5_confidence_windows_canonical_001`
- reliability/subgroup: `experiments/next_bar/lightgbm_vs_follow_through_m5_confidence_reliability.json`, `lightgbm_m5_confidence_subgroup_reliability.json`
- fixed up×high selection/bootstrap: `experiments/next_bar/{lightgbm,follow_through}_m5_up_high_055_selection_windows_001`, `lightgbm_vs_follow_through_m5_up_high_055_daily_bootstrap.json`
