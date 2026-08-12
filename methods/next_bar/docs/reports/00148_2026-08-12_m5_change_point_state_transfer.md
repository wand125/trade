# 00148 M5 Change-Point State固定移植

日時: 2026-08-12 23:32 JST

## 目的

M1で固定済みのChange-Point StateをM5へ無調整で移植し、return/rangeの小さな偏りを逐次蓄積するCUSUM状態が、次足方向、broad confidence、高信頼度、既存候補への多様化に増分価値を持つか確認した。履歴価格やreturnをそのまま入力せず、正負score、balance、alarm方向、alarm ageへ加工して使う。

## 固定仕様と品質

M5 log returnと `log(high / low)` の各現在値を、現在足を含まない直前64完成足の平均・標準偏差で標準化し、innovationを `[-5,5]` へclipする。正負CUSUMはdrift 0.25、alarm閾値5、score上限20とし、各系列から正score、負score、符号付きbalance、alarm方向、64本capのalarm ageを作る固定10特徴である。timestamp gapが1本を超える場合は逐次状態をresetする。baseline 38特徴と合わせて48特徴で、生価格水準、volume、未来足をmodel featureへ使わない。

M1で確認済みの厳密CUSUM式、flat有限0、gap reset、artifact/latestに加え、M5について10列の完全な集合、48特徴、有限 `[-1,1]`、価格10倍scale不変、未来側M1価格の改変が過去M5特徴へ影響しないことを回帰テストした。対象テストはMac/Windowsとも2件成功した。

HGB 200 iteration、learning rate 0.05、31 leaves、min leaf 100、L2 1、最大750,000 train行、Platt、expanding、uniform weighting、全教師、seed 42、標準損失1.0を固定した。通常/方向維持blendはbaseline 75% + Change-Point 25%。confidence gridは事前固定の0.51/0.515/0.525/0.535/0.55、developmentはtest2020〜2023、confirmationはtest2024〜2026_partialである。reference、CUSUM定数、model parameter、weight、閾値、subgroup filterを結果に合わせて再探索していない。

Windows/WSL canonical環境で439,881 OOS行を既存baselineと完全整列した。共有中のComfyUI、Claude、Open WebUI、Ollamaを停止せず、GPUを非表示、単独8 thread、nice 10、ionice 7、空きmemory 16GiB・load 8 gateで実行した。開始時は空き27.80GiB、load 0.01だった。

## 単体と方向

| model | development accuracy | confirmation accuracy | all accuracy | all Brier | all log loss |
|---|---:|---:|---:|---:|---:|
| baseline | 51.91385% | 51.03316% | 51.57463% | 0.249535053 | 0.692215561 |
| Change-Point単体 | 51.84285% | 51.02254% | 51.52689% | 0.249538493 | 0.692222566 |
| baseline 75% + Change-Point 25% | 51.93233% | 51.00897% | 51.57668% | 0.249527110 | 0.692199615 |

単体はbaseline比development -192件、confirmation -18件、all -210件、accuracy 2/7foldだった。通常25%方向blendはdevelopment +50件、confirmation -41件、all +9件、fix 3,664 / harm 3,655、McNemar p=0.92550、accuracy 4/7foldだった。Brier/log lossは7/7fold、development/allの日次bootstrap区間も改善側だったが、all accuracy差+0.00205ptの95%区間は-0.03622〜+0.04018pt、confirmationは点値で悪化したため方向用途へ採用しない。

既存M5 Pressure方向に対してChange-Pointはall -87件、confirmation -55件、accuracy/score各2/7対5/7foldで、Brier/log lossも全期間点値で悪かった。PressureとChange-Point方向blendの固定50/50平均はbaseline 75% + Pressure 12.5% + Change-Point 12.5%に相当し、Pressure比development +30件、confirmation -24件、all +6件、accuracy 4/7foldだった。all accuracy差+0.00136ptの日次95%区間は-0.03143〜+0.03456pt、Brier/log loss差も0跨ぎで、親を更新しなかった。

## broad confidence 0.515

developmentの固定gridでselection score最大は0.515だった。

| period | model | rows | coverage | accuracy | selection score |
|---|---|---:|---:|---:|---:|
| development | baseline | 158,280 | 58.52468% | 52.75588% | 0.0192008 |
| development | Change-Point | 158,262 | 58.51803% | 52.76883% | 0.0192987 |
| confirmation | baseline | 63,694 | 37.59288% | 52.36600% | 0.0121277 |
| confirmation | Change-Point | 62,670 | 36.98851% | 52.42062% | 0.0123429 |
| all | baseline | 221,974 | 50.46228% | 52.64400% | 0.0173063 |
| all | Change-Point | 220,932 | 50.22540% | 52.67005% | 0.0174468 |

baseline比all accuracy差+0.02605ptの95%区間は-0.02276〜+0.07434pt、selection score差+0.0001405の区間は-0.0002061〜+0.0004820で0を跨いだ。confirmationもaccuracy/score区間は0跨ぎだった。coverageはconfirmation -0.60438pt、all -0.23688ptへ確定低下した。Brier/log lossはdevelopment/allで改善区間となり、年別proper score各6/7foldだったが、accuracy 4/7、score 3/7foldで採用gateを通らなかった。

## 既存broad候補との比較

| candidate | all rows | coverage | accuracy | selection score | Change-Point accuracy/score fold勝敗 |
|---|---:|---:|---:|---:|---:|
| Change-Point | 220,932 | 50.22540% | 52.67005% | 0.0174468 | — |
| Profile | 221,844 | 50.43273% | 52.68116% | 0.0175648 | 3/7, 3/7 |
| EWMA | 221,618 | 50.38135% | 52.69382% | 0.0176449 | 3/7, 2/7 |
| Haar | 221,540 | 50.36362% | 52.69838% | 0.0176739 | 2/7, 2/7 |
| Profile × TCN | 218,343 | 49.63683% | 52.72988% | 0.0177572 | 1/7, 1/7 |

Change-PointはProfileに対しall accuracy -0.01111pt、coverage -0.20733pt、score -0.0001179で、confirmationも3指標を全て下げた。Brier/log lossもProfileより全期間点値で悪かった。EWMA、Haar、Profile×TCNのaggregate objectiveも更新しない。

Profile confidenceとChange-Point confidenceの固定50/50平均はProfile比development score -0.0000015、confirmation -0.0004787、all -0.0001586、accuracy/score各2/7対5/7foldだった。Profile×TCNにはaccuracy/score各0/7だったため、多様化成分として採用しない。

## 高信頼度と校正

Change-Pointのconfirmation cumulative accuracyは0.515で52.42062%、0.525で53.31641%、0.535で55.13934%、0.55で58.56981%と単調に上昇した。各閾値のmean confidenceは52.47590%、53.33635%、54.21558%、55.54671%で、全閾値が局所整合した。development/allもaccuracyの単調性を満たしたが、0.515〜0.55は平均confidenceに対して過信だった。

0.55はconfirmation 881件、all 23,834件・56.04598%・coverage 5.41828%・score 0.0126044である。既存Directional Follow-throughはconfirmation 940件・58.51064%、all 24,328件・56.19040%・coverage 5.53059%・score 0.0130897でChange-Pointを上回った。Change-Pointはaccuracy/score各2/7foldで、coverage低下の日次区間もdevelopment/confirmation/allで確定した。test2026_partialはChange-Point 229件・50.65502%でFollow-through 228件・49.12281%より点値は高いが、Wilson下限44.22238%でedge未確認だった。

固定方向×volatilityの0.515 confirmationでは、`down × normal` が4,158件・50.62530%、Wilson下限49.10575%でedge未確認だった。`up × normal` も13,780件・51.56749%に対しmean confidence 52.40032%で過信した。確認後の除外filterは作らない。confirmation全体の校正順位は良好でも、global/localで一貫したfair oddsとは認可しない。

## latest

保存modelの最新M5は2026-06-01 04:55 UTC判定、up、`p(up)=0.5177793369`、volatility highだった。0.515は通るが、これはChange-Point単体modelであり、方向維持25% full runtime blendではない。`odds_valid=false`、`strict_prediction_eligible=false`であり、運用へ接続しない。

## 判断

M5 Change-Point単体、通常25%方向blend、方向維持0.515/0.55、Pressure方向との固定50/50平均、Profile confidenceとの固定50/50平均をすべて再現専用とする。baselineに対するdevelopment/all proper score改善と信頼度単調性から、逐次CUSUM加工がM5にも確率情報を持つことは確認できた。しかし方向は確認期間で反転しPressureを超えず、confidenceはcoverageを削って主指標区間が未確定、既存Profile/EWMA/Haar/Profile×TCNおよびFollow-throughの各roleを更新せず、固定多様化も親を上積みしなかった。

新しいconfig、registry、authoritative方向/confidence、fair odds、adoption/paper/live policyは発行・変更しない。同じ履歴でreference、drift、alarm閾値、score/age cap、feature subset、model parameter、weight、閾値、subgroup filterを再探索しない。

## 成果物

- 実装・テスト: `src/trade_data/next_bar.py`, `tests/test_next_bar.py`
- 単体OOS: `experiments/next_bar/change_point_state_m5_windows_canonical_001`
- 方向/方向維持blend: `experiments/next_bar/change_point_state_m5_{direction,confidence}_blend_windows_canonical_001`
- candidate分析: `experiments/next_bar/change_point_state_m5_candidate_analysis_windows.json`
- baseline bootstrap: `experiments/next_bar/change_point_state_m5_{direction,confidence}_vs_baseline_bootstrap_20000_windows.json`
- 既存候補比較: `experiments/next_bar/change_point_state_vs_{pressure,profile,ewma,haar,profile_tcn,follow_through}_m5_*_windows_comparison.json`
- 固定平均: `experiments/next_bar/{pressure_change_point_equal_m5_direction,profile_change_point_equal_m5_confidence}_windows_canonical_001`
- reliability/subgroup: `experiments/next_bar/change_point_state*_m5_*_windows.json`
- latest: `experiments/next_bar/change_point_state_m5_latest_prediction_windows.json`

## 検証

- 対象テスト: `2 passed, 95 deselected`（Mac 5.66秒、Windows 1.63秒）。
- 全テスト（Mac）: `1393 passed, 1 deselected, 280 warnings, 83 subtests passed`、133.81秒。
- 全テスト（Windows）: `1393 passed, 1 deselected, 280 warnings, 83 subtests passed`、49.81秒。
- deselectは今回と無関係な既存 `entry_ev` レポート `00384_2026-07-08_mql5_mt5_paid_expert_top_analysis.md` の内部時刻欠落1件。
- 変更4ファイルのMac/Windows同期、SHA-256一致、差分の秘密情報scan 0件、`git diff --check` 成功を確認した。commit/pushは本commitで記録する。
