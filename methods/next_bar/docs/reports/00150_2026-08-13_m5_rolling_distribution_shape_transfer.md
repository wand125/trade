# 00150 M5 Rolling Distribution Shape固定移植

日時: 2026-08-13 14:03 JST

## 目的

M1で固定済みのRolling Distribution ShapeをM5へ無調整で移植し、320分のreturn分布形状が、次足方向、broad confidence、高信頼度、既存候補への多様化に増分価値を持つか確認した。履歴価格水準やreturn列をそのままmodelへ入れず、scale不変な分位・歪度・集中度へ加工して使う。

## 固定仕様と品質

直近64完成M5足のlog returnについて、10/25/50/75/90%分位をRMSで正規化し、Bowley skew、tail skew、IQR/interdecile中央spread比、mean absolute return/RMS集中度を加える固定9特徴である。M5では320分の分布を表し、baseline 38特徴と合わせて47特徴になる。生のopen/high/low/close、volume、未来足をmodel featureへ使わない。

M1の式・artifact/latest試験に加え、M5について9列の完全な集合、47特徴、有限値、2つの比率列の0〜1境界、価格10倍scale不変、未来側M1価格の改変が過去M5特徴へ影響しないこと、最終64本の分位/RMSとL1/L2式、train/latestを回帰テストした。window、分位点、正規化、feature subsetをM5結果に合わせて変更していない。

HGB 200 iteration、learning rate 0.05、31 leaves、min leaf 100、L2 1、最大750,000 train行、Platt、expanding、uniform weighting、全教師、seed 42、標準損失1.0を固定した。通常/方向維持blendはbaseline 75% + Distribution Shape 25%。confidence gridは事前固定の0.51/0.515/0.525/0.535/0.55、developmentはtest2020〜2023、confirmationはtest2024〜2026_partialである。model parameter、weight、閾値、subgroup filterを結果に合わせて再探索していない。

Windows/WSL canonical環境で439,881 OOS行を既存baselineと完全整列した。共有中のComfyUI、Claude、Open WebUI、Ollamaを停止せず、GPUを非表示、単独8 thread、nice 10、ionice 7、空きmemory 16GiB・load 8 gateを維持した。

## 単体と方向

| model | development accuracy | confirmation accuracy | all accuracy | all Brier | all log loss |
|---|---:|---:|---:|---:|---:|
| baseline | 51.91385% | 51.03316% | 51.57463% | 0.249535053 | 0.692215561 |
| Distribution Shape単体 | 51.88020% | 51.05205% | 51.56122% | 0.249544119 | 0.692233919 |
| baseline 75% + Shape 25% | 51.92124% | 51.05618% | 51.58804% | 0.249530014 | 0.692205472 |

単体はbaseline比development -91件、confirmation +32件、all -59件で、accuracy/proper score各2/7foldだった。通常25%方向blendはdevelopment +20件、confirmation +39件、all +59件、fix 3,194 / harm 3,135、McNemar p=0.46597で、accuracy、Brier、log loss、ECEが各5/7foldだった。20,000回UTC日bootstrapではdevelopment/allのBrier差95%区間がそれぞれ-0.000013765〜-0.000000322、-0.000009558〜-0.000000524、log lossも改善側だった。一方、accuracy差はdevelopment +0.00740pt、confirmation +0.02302pt、all +0.01341ptで全区間が0を跨いだ。確率平滑化だけを方向candidateの昇格根拠にしない。

既存Pressure方向に対してShapeはdevelopment -62件、confirmation +25件、all -37件で、accuracy/score各4/7foldだった。Shape − Pressureのall Brier差+0.000008714、log loss差+0.000017517の95%区間はそれぞれ+0.000002456〜+0.000014994、+0.000004941〜+0.000030115でShape劣後側だった。PressureとShapeの固定50/50平均もPressure比development -59件、confirmation +38件、all -21件で、all proper scoreが有意に悪化した。Pressureを更新しない。

## broad confidence 0.515

developmentの固定gridではShape内のselection score最大が0.515だったが、baselineの同じ0.515を上回らなかった。

| period | model | rows | coverage | accuracy | selection score |
|---|---|---:|---:|---:|---:|
| development | baseline | 158,280 | 58.52468% | 52.75588% | 0.0192008 |
| development | Shape | 157,684 | 58.30431% | 52.75678% | 0.0191679 |
| confirmation | baseline | 63,694 | 37.59288% | 52.36600% | 0.0121277 |
| confirmation | Shape | 63,506 | 37.48192% | 52.43284% | 0.0125156 |
| all | baseline | 221,974 | 50.46228% | 52.64400% | 0.0173063 |
| all | Shape | 221,190 | 50.28405% | 52.66377% | 0.0174133 |

baseline比はaccuracy 5/7、selection score 4/7、Brier/log loss各5/7foldだった。20,000回UTC日bootstrapのall accuracy差+0.01977pt、selection score差+0.0001070はともに0を跨ぎ、coverage -0.17823ptの区間-0.22574〜-0.13073ptだけが確定した。developmentもcoverageを確定的に削りscoreは僅かに悪化、confirmationのaccuracy/score改善は未確定だった。development/all proper score改善は確認したが、coverage-aware採用条件を満たさない。

## 既存broad候補との比較

| candidate | all rows | coverage | accuracy | selection score | Shape accuracy/score fold勝敗 |
|---|---:|---:|---:|---:|---:|
| Distribution Shape | 221,190 | 50.28405% | 52.66377% | 0.0174133 | — |
| Profile | 221,844 | 50.43273% | 52.68116% | 0.0175648 | 3/7, 2/7 |
| EWMA | 221,618 | 50.38135% | 52.69382% | 0.0176449 | 2/7, 1/7 |
| Haar | 221,540 | 50.36362% | 52.69838% | 0.0176739 | 2/7, 2/7 |
| Profile × TCN | 218,343 | 49.63683% | 52.72988% | 0.0177572 | 1/7, 2/7 |

Profileに対してShapeはall accuracy -0.01739pt、selection score -0.0001514、coverage -0.14868ptである。accuracy/score区間は0を跨いだが、coverage低下、Brier差+0.000008556、log loss差+0.000017148は95%区間がShape劣後側だった。confirmationでもaccuracy/scoreをProfileより下げた。EWMA、Haar、Profile×TCNのaggregate objectiveも更新しない。

Profile confidenceとShape confidenceの固定50/50平均は、Profile比development accuracy +0.03318pt、score +0.0002297でも、confirmation accuracy -0.05146pt、score -0.0003215へ反転した。all accuracy/scoreの点値は+0.00886pt/+0.0000451だが区間は0を跨ぎ、coverageとproper scoreが有意に悪化した。Profile×TCNにはaccuracy 1/7、score 2/7のため、多様化成分として採用しない。

## 高信頼度と校正

Shapeのconfirmation cumulative accuracyは0.515で52.43284%、0.525で53.35558%、0.535で54.95730%、0.55で57.64192%と単調に上昇した。各mean confidenceは52.48377%、53.34613%、54.21344%、55.53274%で全閾値が局所整合し、development/allもaccuracy単調性を満たした。ただしdevelopment/allの0.515〜0.535は平均confidenceに対して過信だった。

0.55はconfirmation 916件、all 23,625件・56.06349%・coverage 5.37077%・score 0.0125832である。既存Directional Follow-throughはconfirmation 940件・58.51064%、all 24,328件・56.19040%・coverage 5.53059%・score 0.0130897でShapeを上回った。Shapeはaccuracy/score各2/7foldで、coverage低下がdevelopment/allで確定し、all proper scoreも有意に悪かった。test2026_partialは210件・49.04762%、Wilson下限42.3643%で直近tailのedgeは未確認だった。

固定方向×volatilityの0.515 confirmationでは `down × normal` が4,314件・50.27816%、Wilson下限48.78654%でedge未確認だった。0.55は `up × high` の676件・57.69231%、Wilson下限53.93477%だけが十分なsupportとedgeを持ち、他5セルは3〜101件またはWilson下限50%以下だった。これは診断後の区分なので採用filterへ変換しない。global/localで一貫したfair oddsとは認可しない。

## latest

保存modelの最新M5は2026-06-01 04:55 UTC判定、up、`p(up)=0.5211812362`、volatility highだった。0.515は通るが、これはShape単体modelであり方向維持25% full runtime blendではない。`odds_valid=false`、`strict_prediction_eligible=false`であり、運用へ接続しない。

## 判断

M5 Rolling Distribution Shape単体、通常25%方向blend、方向維持0.515/0.55、Pressure方向との固定50/50平均、Profile confidenceとの固定50/50平均をすべて再現専用とする。通常方向blendのdevelopment/all proper-score改善と、confirmationで52.43%から57.64%へ上がる信頼度順位性から、分布形状加工がM5にも弱い情報を持つことは確認できた。しかし方向accuracy増分は未確定でPressureよりproper scoreが悪く、broad confidenceはcoverageを削ってProfileよりproper scoreが有意に悪く、Profile×TCNとFollow-throughの各roleを更新しない。固定多様化も親を上積みしなかった。

新しいconfig、registry、authoritative方向/confidence、fair odds、adoption/paper/live policyは発行・変更しない。同じ履歴でwindow、分位点、正規化、feature subset、model parameter、weight、閾値、subgroup filterを再探索しない。

## 成果物

- 実装・テスト: `src/trade_data/next_bar.py`, `tests/test_next_bar.py`
- 単体OOS: `experiments/next_bar/rolling_distribution_shape_m5_windows_canonical_001`
- 方向/方向維持blend: `experiments/next_bar/rolling_distribution_shape_m5_{direction,confidence}_blend_windows_canonical_001`
- candidate分析: `experiments/next_bar/rolling_distribution_shape_m5_candidate_analysis_windows.json`
- baseline bootstrap: `experiments/next_bar/rolling_distribution_shape_m5_{direction,confidence}_vs_baseline_bootstrap_20000_windows.json`
- 既存候補比較: `experiments/next_bar/rolling_distribution_shape_vs_{pressure,profile,ewma,haar,profile_tcn,follow_through}_m5_*_windows_comparison.json`
- 既存候補bootstrap: `experiments/next_bar/rolling_distribution_shape_vs_{pressure,profile,follow_through}_m5_*_bootstrap_20000_windows.json`
- 固定平均: `experiments/next_bar/{pressure_rolling_distribution_shape_equal_m5_direction,profile_rolling_distribution_shape_equal_m5_confidence}_windows_canonical_001`
- reliability/subgroup: `experiments/next_bar/rolling_distribution_shape*_m5_*reliability_windows.json`
- latest: `experiments/next_bar/rolling_distribution_shape_m5_latest_prediction_windows.json`

## 検証

- 対象テスト `pytest tests/test_next_bar.py -k rolling_distribution_shape`: Mac 2 passed / 97 deselected（5.77秒）、Windows 2 passed / 97 deselected（1.52秒）。
- 上記既知検査1件だけを明示的にdeselectした全テスト: Mac 1,395 passed / 1 deselected / 280 warnings（129.74秒）、Windows 1,395 passed / 1 deselected / 280 warnings（48.42秒）。
- 変更4ファイルはMac/WindowsでSHA-256が全件一致した。口座・login・password・token・secret・API key・private key形式の値を表示しないscanは一致0件で、`git diff --check` も通過した。口座runtime、認証情報、個人設定、WindowsのCodex状態は同期・commit対象に含めない。
