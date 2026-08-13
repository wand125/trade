# 00149 M5 Rolling Full Path固定移植

日時: 2026-08-13 13:38 JST

## 目的

M1で固定済みのRolling Full PathをM5へ無調整で移植し、75分の順序付き価格経路が、次足方向、broad confidence、高信頼度、既存候補への多様化に増分価値を持つか確認した。履歴OHLCをそのままmodelへ入れず、共同高安range内の経路座標へ加工して使う。

## 固定仕様と品質

直近15完成M5足について、最初のopenを原点、15本全体の `max(high) - min(low)` をscaleとし、完成位置1/2/4/5/7/8/10/11/13/14/15本目のcloseを `(close - first open) / joint range` へ変換する。各値を `[-1,1]` へclipし、flat windowは0とする固定11特徴である。M5では75分の経路を表し、baseline 38特徴と合わせて49特徴になる。生のopen/high/low/close、volume、未来足をmodel featureへ使わない。

M1の式・artifact/latest試験に加え、M5について11列の完全な集合、49特徴、有限 `[-1,1]`、価格10倍scale不変、未来側M1価格の改変が過去M5特徴へ影響しないこと、厳密な最終window式、train/latestを回帰テストした。window、採取点、正規化、clip、feature subsetをM5結果に合わせて変更していない。

HGB 200 iteration、learning rate 0.05、31 leaves、min leaf 100、L2 1、最大750,000 train行、Platt、expanding、uniform weighting、全教師、seed 42、標準損失1.0を固定した。通常/方向維持blendはbaseline 75% + Rolling Full Path 25%。confidence gridは事前固定の0.51/0.515/0.525/0.535/0.55、developmentはtest2020〜2023、confirmationはtest2024〜2026_partialである。model parameter、weight、閾値、subgroup filterを結果に合わせて再探索していない。

Windows/WSL canonical環境で439,881 OOS行を既存baselineと完全整列した。比較途中にWindowsが自然再起動したが、保存済みOOSを再利用し、復帰後の同一commit・同一artifactから分析を再開した。共有中のComfyUI、Claude、Open WebUI、Ollamaを停止せず、GPUを非表示、単独8 thread、nice 10、ionice 7、空きmemory 16GiB・load 8 gateを維持した。復帰時は空き36GiB、load 0.03だった。

## 単体と方向

| model | development accuracy | confirmation accuracy | all accuracy | all Brier | all log loss |
|---|---:|---:|---:|---:|---:|
| baseline | 51.91385% | 51.03316% | 51.57463% | 0.249535053 | 0.692215561 |
| Rolling Full Path単体 | 51.88205% | 51.09041% | 51.57713% | 0.249552199 | 0.692250258 |
| baseline 75% + Rolling Full Path 25% | 51.90904% | 51.09750% | 51.59645% | 0.249531364 | 0.692208197 |

単体はbaseline比development -86件、confirmation +97件、all +11件、accuracy 4/7foldだった。通常25%方向blendはdevelopment -13件、confirmation +109件、all +96件、fix 3,469 / harm 3,373、McNemar p=0.25076で、accuracy 4/7、Brier/log loss各6/7、ECE 7/7foldだった。confirmation accuracy差+0.06433ptの日次95%区間は+0.00406〜+0.12438ptだが、developmentは点値悪化、all区間は-0.01541〜+0.05872ptである。確認期間だけの改善を方向候補へ昇格させない。

既存Pressure方向に対してRollingはdevelopment -95件、confirmation +95件、all同率で、accuracy/score各5/7foldだった。しかしRolling − Pressureのall Brier差+0.000010064、log loss差+0.000020241の95%区間はそれぞれ+0.000003763〜+0.000016391、+0.000007584〜+0.000032968で、Pressureの確率品質が有意に良かった。PressureとRollingの固定50/50平均はbaseline 75% + Pressure 12.5% + Rolling 12.5%に相当するが、Pressure比confirmation/all -11件、accuracy/score各3/7、proper scoreも悪化したため親を更新しない。

## broad confidence 0.515

developmentの固定gridでselection score最大は0.515だった。

| period | model | rows | coverage | accuracy | selection score |
|---|---|---:|---:|---:|---:|
| development | baseline | 158,280 | 58.52468% | 52.75588% | 0.0192008 |
| development | Rolling | 157,754 | 58.33019% | 52.79676% | 0.0194780 |
| confirmation | baseline | 63,694 | 37.59288% | 52.36600% | 0.0121277 |
| confirmation | Rolling | 63,634 | 37.55747% | 52.44052% | 0.0125777 |
| all | baseline | 221,974 | 50.46228% | 52.64400% | 0.0173063 |
| all | Rolling | 221,388 | 50.32907% | 52.69436% | 0.0176388 |

baseline比はaccuracy 6/7、selection score 5/7、Brier/log loss各6/7foldだった。20,000回UTC日bootstrapのall accuracy差+0.05036ptは95%区間+0.00376〜+0.09750pt、selection score差+0.0003325は+0.0000022〜+0.0006669で改善側だった。一方、developmentとconfirmationを個別に見るとaccuracy・score・proper scoreは全て0跨ぎで、all coverageは-0.13322pt、区間-0.18015〜-0.08626ptへ確定低下した。全期間だけの小差を独立採用証拠とはしない。

## 既存broad候補との比較

| candidate | all rows | coverage | accuracy | selection score | Rolling accuracy/score fold勝敗 |
|---|---:|---:|---:|---:|---:|
| Rolling Full Path | 221,388 | 50.32907% | 52.69436% | 0.0176388 | — |
| Profile | 221,844 | 50.43273% | 52.68116% | 0.0175648 | 3/7, 3/7 |
| EWMA | 221,618 | 50.38135% | 52.69382% | 0.0176449 | 4/7, 4/7 |
| Haar | 221,540 | 50.36362% | 52.69838% | 0.0176739 | 3/7, 3/7 |
| Profile × TCN | 218,343 | 49.63683% | 52.72988% | 0.0177572 | 2/7, 2/7 |

RollingはProfileにall accuracy +0.01320pt、score +0.0000741の点値でも両bootstrap区間が0を跨ぎ、coverage -0.10366ptが確定した。さらにRolling − Profileのall Brier差+0.000009552、log loss差+0.000019165の区間はそれぞれ+0.000003145〜+0.000015971、+0.000006315〜+0.000032075でRolling劣後側だった。confirmationのaccuracy/scoreもProfileを下回る。EWMA、Haar、Profile×TCNのaggregate objectiveも更新しない。

Profile confidenceとRolling confidenceの固定50/50平均は、Profile比development accuracy +0.05826pt、score +0.0004235でも、confirmation accuracy -0.11462pt、score -0.0006982へ反転した。all accuracy/score各4/7でもProfile×TCNには各2/7のため、多様化成分として採用しない。

## 高信頼度と校正

Rollingのconfirmation cumulative accuracyは0.515で52.44052%、0.525で53.25588%、0.535で54.97868%、0.55で57.92880%と単調に上昇した。各mean confidenceは52.48248%、53.34186%、54.21746%、55.52222%で全閾値が局所整合し、development/allもaccuracy単調性を満たした。ただしdevelopment/allの0.515〜0.535は平均confidenceに対して過信だった。

0.55はconfirmation 927件、all 23,744件・56.04784%・coverage 5.39782%・score 0.0125822である。既存Directional Follow-throughはconfirmation 940件・58.51064%、all 24,328件・56.19040%・coverage 5.53059%・score 0.0130897でRollingを上回った。Rollingはaccuracy 2/7、score 3/7foldで、coverage低下がdevelopment/allで確定し、all Brier/log lossも有意に悪かった。test2026_partialはRolling 217件・51.15207%、Wilson下限44.53920%で、直近tailのedgeは未確認だった。

固定方向×volatilityの0.515 confirmationでは `down × normal` が4,321件・50.82157%、Wilson下限49.33085%でedge未確認だった。0.55は `up × high` の684件・58.47953%、Wilson下限54.74935%だけが十分なsupportとedgeを持ち、他5セルは5〜103件またはWilson下限50%以下だった。これは診断後の区分なので採用filterへ変換しない。global/localで一貫したfair oddsとは認可しない。

## latest

保存modelの最新M5は2026-06-01 04:55 UTC判定、up、`p(up)=0.5221608427`、volatility highだった。0.515は通るが、これはRolling単体modelであり方向維持25% full runtime blendではない。`odds_valid=false`、`strict_prediction_eligible=false`であり、運用へ接続しない。

## 判断

M5 Rolling Full Path単体、通常25%方向blend、方向維持0.515/0.55、Pressure方向との固定50/50平均、Profile confidenceとの固定50/50平均をすべて再現専用とする。0.515のall accuracy/selection score区間、confirmation方向区間、信頼度単調性から、順序付き経路加工がM5にも情報を持つことは確認できた。しかし開発期と確認期を個別には同時確定できず、方向はPressureと同率でもproper scoreが劣り、broad confidenceはProfileよりproper scoreが有意に悪く、Profile×TCNとFollow-throughの各roleを更新しない。固定多様化も親を上積みしなかった。

新しいconfig、registry、authoritative方向/confidence、fair odds、adoption/paper/live policyは発行・変更しない。同じ履歴でwindow、採取点、正規化、clip、feature subset、model parameter、weight、閾値、subgroup filterを再探索しない。

## 成果物

- 実装・テスト: `src/trade_data/next_bar.py`, `tests/test_next_bar.py`
- 単体OOS: `experiments/next_bar/rolling_full_path_m5_windows_canonical_001`
- 方向/方向維持blend: `experiments/next_bar/rolling_full_path_m5_{direction,confidence}_blend_windows_canonical_001`
- candidate分析: `experiments/next_bar/rolling_full_path_m5_candidate_analysis_windows.json`
- baseline bootstrap: `experiments/next_bar/rolling_full_path_m5_{direction,confidence}_vs_baseline_bootstrap_20000_windows.json`
- 既存候補比較: `experiments/next_bar/rolling_full_path_vs_{pressure,profile,ewma,haar,profile_tcn,follow_through}_m5_*_windows_comparison.json`
- 既存候補bootstrap: `experiments/next_bar/rolling_full_path_vs_{pressure,profile,follow_through}_m5_*_bootstrap_20000_windows.json`
- 固定平均: `experiments/next_bar/{pressure_rolling_full_path_equal_m5_direction,profile_rolling_full_path_equal_m5_confidence}_windows_canonical_001`
- reliability/subgroup: `experiments/next_bar/rolling_full_path*_m5_*reliability_windows.json`
- latest: `experiments/next_bar/rolling_full_path_m5_latest_prediction_windows.json`

## 検証

- 対象テスト `pytest tests/test_next_bar.py -k rolling_full_path`: Mac 2 passed / 96 deselected（7.10秒）、Windows 2 passed / 96 deselected（1.57秒）。
- 全テストを無除外で実行すると、Mac/Windowsとも今回変更外の `methods/entry_ev/docs/reports/00384_2026-07-08_mql5_mt5_paid_expert_top_analysis.md` に内部日時がない既知の整合性検査だけが失敗し、1 failed / 1,394 passed / 280 warningsだった。
- 上記既知検査1件だけを明示的にdeselectした全テスト: Mac 1,394 passed / 1 deselected / 280 warnings（134.27秒）、Windows 1,394 passed / 1 deselected / 280 warnings（47.78秒）。
- 変更4ファイルはMac/WindowsでSHA-256が全件一致した。口座・login・password・token・secret・API key・private key形式の値を表示しないscanは一致0件で、`git diff --check` も通過した。口座runtime、認証情報、個人設定、WindowsのCodex状態は同期・commit対象に含めない。
