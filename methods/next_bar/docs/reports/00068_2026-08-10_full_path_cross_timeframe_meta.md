# 00068 Full Path × Cross-timeframe meta

日時: 2026-08-10 19:45 JST

## 目的

M15方向維持confidenceの現championであるIntrabar Full Pathへ、同じdecision timestampで確定済みのM5/M1方向確率を追加し、M15単独では表せない短期時間足の状態から方向精度または高信頼帯のaccuracy×coverageを改善できるか検証した。

## 実装と時系列制約

従来のcross-timeframe実装はM15/M5/M1が同じ予測directory群にある前提だった。M15だけFull Path、M5/M1は既存baselineを使えるよう、CLIへ `--target-predictions-dir` と `--context-predictions-dir` を追加した。旧 `--predictions-dir` は互換維持し、旧形式と分離形式の混在、片側欠落は停止する。

各test foldのlogistic meta modelは、それ以前のOOS foldだけで学習する。M15/M5/M1は同一decision timestampでinner joinし、target 120,023行は2021〜2026途中の6fold。C=0.10、初期blend weight=0.25で、損失倍率は標準1.0のみである。

## 固定25%結果

| metric | Full Path target | M1/M5 meta 25% blend | delta |
|---|---:|---:|---:|
| accuracy | 51.7884% | 51.7134% | -0.0750pt |
| balanced accuracy | 51.7336% | 51.6432% | -0.0904pt |
| Brier | 0.24951443 | 0.24950554 | -0.00000889 |
| log loss | 0.69217640 | 0.69215860 | -0.00001779 |
| ECE | 0.3580% | 0.4179% | +0.0599pt |

Full Pathの誤りを1,392件直した一方、正解を1,482件壊し、純-90件、McNemar exact p=0.0969だった。方向accuracyは6/6 foldで悪化した。Brier/log lossの僅かな改善は、主目的の方向識別とECE悪化を補わない。

| threshold | Full Path coverage / accuracy | 25% blend coverage / accuracy |
|---|---:|---:|
| 0.53 | 24.778% / 54.111% | 24.310% / 54.078% |
| 0.54 | 14.361% / 54.827% | 13.981% / 54.818% |
| 0.55 | 8.174% / 55.438% | 8.033% / 55.103% |

主要な0.53〜0.55帯はaccuracyとcoverageが同時に改善しなかった。0.60は531行、56.685%だったが、Full Path側も461行しかなく、開発期間で事前選択されたlaneではないため採用判断に使わない。

## Weight感度と未使用期間の分離

25%失敗後の診断として0.05/0.10/0.15/0.50も実行した。これは後付け感度分析であり、全期間の最大値を採用値にしない。

| meta weight | all accuracy | Full Path差 | accuracy改善fold | Brier |
|---:|---:|---:|---:|---:|
| 0.05 | 51.8109% | +0.0225pt | 4/6 | 0.24951153 |
| 0.10 | 51.8184% | +0.0300pt | 3/6 | 0.24950920 |
| 0.15 | 51.7842% | -0.0042pt | 2/6 | 0.24950742 |
| 0.25 | 51.7134% | -0.0750pt | 0/6 | 0.24950554 |
| 0.50 | 51.7659% | -0.0225pt | 3/6 | 0.24951062 |

点推定最大の10%は全期間+36件、p=0.304だった。しかしdevelopmentでは+58件、p=0.0316からconfirmationでは-22件、p=0.324へ反転した。developmentで選択された0.53 laneもaccuracy 53.756%対53.776%、coverage 32.000%対32.057%、selection score 0.01740対0.01753でFull Pathより低い。confirmation laneはaccuracyとscoreが上がったがcoverageは0.436pt低下した。

10%−Full Pathの日次paired bootstrap 20,000回では、全期間0.53 score差+0.000088の95%区間は-0.000508〜+0.000690、優位確率61.7%。accuracy差の区間も0を跨いだ。confirmationのBrier/log loss改善だけは支持されたが、主目的のlane score優位は未確定だった。

## Chronological weight選択監査

後付けの10%固定を避けるため、各foldより前のOOS 0.53 selection scoreだけで `{0, 0.05, 0.10, 0.15, 0.25, 0.50}` からweightを選んだ。最初の2021は証拠がないため0、以後は `0, 0, 0.05, 0.05, 0` となった。

この完全時系列ルーターはFull Path単体に対して方向-11件、p=0.483。0.53はaccuracy 54.100%対54.111%、coverage 24.683%対24.778%、selection score 0.01755対0.01764で全て下回った。小さいweightの見かけの改善も、過去だけで選択すると再現しなかった。

## 既存cross-timeframeとの比較と判断

既存baseline M15 × M5/M1 25% metaは51.7184%。Full Path単体は51.7884%で+84件、p=0.498、Full Path × meta 25%は51.7134%で既存metaより-6件、p=0.966だった。M15側を改善してもM1/M5 metaのincremental direction edgeは増えなかった。

Full Path × M1/M5 metaは不採用とする。固定25%、weight感度の点推定最大、過去だけのweight選択のいずれも方向と高信頼評価関数を安定して同時改善しないため、M30 as-of追加へ進めない。既存 `m15_cross_tf_meta_candidate_v1` とM30高信頼専用candidateは変更せず、Full Path 0.53 selective championを維持する。今回のsplit-source実装とOOS成果物は再現用に残すが、config、registry、latest artifactは発行しない。

## 成果物

- 固定25%: `experiments/next_bar/cross_timeframe_meta_full_path_m15_001`
- 感度分析: `experiments/next_bar/cross_timeframe_meta_full_path_m15_weight_0p{05,10,15,50}_001`
- target OOS: `experiments/next_bar/walk_forward_intrabar_full_path_m15_001`
- context OOS: `experiments/next_bar/context_confirmation_001`, `experiments/next_bar/walk_forward_001`
