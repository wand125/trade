# 00147 M5 Shock / Recovery State固定移植

日時: 2026-08-12 23:12 JST

## 目的

M1で固定済みのShock / Recovery StateをM5へ無調整で移植し、固定shock後の継続・反転状態が次足方向、broad confidence、高信頼度、既存候補への多様化に増分価値を持つか確認した。履歴価格やreturnをそのまま入力せず、固定2σ eventからのage、超過量、応答、最大継続・反転へ加工して使う。

## 固定仕様と品質

現在足を含まない直前64完成足でreturnとrangeを標準化し、2σを超えたshockを16本追跡する。return shockの方向・超過量・age・3倍capした累積response・最大continuation・最大reversal、range shockの方向・超過量・age、return/range同時eventを固定12特徴とした。baseline 38特徴と合わせて50特徴で、生価格水準、volume、未来足をmodel featureへ使わない。

M1で確認済みのflat有限0、gap reset、response式、artifact/latestに加え、M5について12列の完全な集合、50特徴、有限 `[-1,1]`、価格10倍scale不変、未来側M1価格の改変が過去M5特徴へ影響しないことを回帰テストした。対象テストは2件成功した。

HGB 200 iteration、learning rate 0.05、31 leaves、min leaf 100、L2 1、最大750,000 train行、Platt、expanding、uniform weighting、全教師、seed 42、標準損失1.0を固定した。通常/方向維持blendはbaseline 75% + Shock 25%。confidence gridは事前固定の0.51/0.515/0.525/0.535/0.55、developmentはtest2020〜2023、confirmationはtest2024〜2026_partialである。reference、2σ、追跡長、response cap、model parameter、weight、閾値、subgroup filterを結果に合わせて再探索していない。

Windows/WSL canonical環境で439,881 OOS行を既存baselineと完全整列した。共有中のComfyUI、Claude、Open WebUI、Ollamaを停止せず、GPUを非表示、単独8 thread、nice 10、ionice 7、空きmemory 16GiB・load 8 gateで実行した。開始時は空き27GiB、load 0.07だった。

## 単体と方向

| model | development accuracy | confirmation accuracy | all accuracy | all Brier | all log loss |
|---|---:|---:|---:|---:|---:|
| baseline | 51.91385% | 51.03316% | 51.57463% | 0.249535053 | 0.692215561 |
| Shock単体 | 51.91533% | 51.04320% | 51.57940% | 0.249534993 | 0.692215542 |
| baseline 75% + Shock 25% | 51.94786% | 51.05500% | 51.60396% | 0.249527782 | 0.692200966 |

Shock単体はbaseline比all +21件だった。通常25%方向blendはdevelopment +92件、confirmation +37件、all +129件、fix 3,163 / harm 3,034、McNemar p=0.10394で、accuracy 4/7fold、Brier/log loss 6/7fold、ECE 3/7foldだった。日次bootstrapのall accuracy差+0.02933ptの95%区間は-0.00481〜+0.06374ptで0を跨いだ。一方、all Brier差-0.000007271、log loss差-0.000014595は改善側だった。

既存M5 Pressure方向に対してShockはall +33件、accuracy差+0.00750ptだったが、95%区間は-0.03711〜+0.05301ptだった。Shockはaccuracy 3/7fold、Pressureは4/7foldで、ShockのBrier差+0.000006482とlog loss差+0.000013010は悪化区間が確定した。PressureとShockの固定50/50方向平均もall 51.58986%で両親を上積みしなかった。方向用途へ採用しない。

## broad confidence 0.515

developmentの固定gridでselection score最大は0.515だった。

| period | model | rows | coverage | accuracy | selection score |
|---|---|---:|---:|---:|---:|
| development | baseline | 158,280 | 58.52468% | 52.75588% | 0.0192008 |
| development | Shock | 157,777 | 58.33869% | 52.77132% | 0.0192852 |
| confirmation | baseline | 63,694 | 37.59288% | 52.36600% | 0.0121277 |
| confirmation | Shock | 62,966 | 37.16321% | 52.48229% | 0.0127537 |
| all | baseline | 221,974 | 50.46228% | 52.64400% | 0.0173063 |
| all | Shock | 220,743 | 50.18244% | 52.68887% | 0.0175721 |

baseline比confirmation accuracy差+0.11629ptの日次95%区間は+0.02770〜+0.20484pt、selection score差+0.0006260の区間は+0.0000884〜+0.0011631で改善を支持した。all accuracy差+0.04487ptの区間は-0.00065〜+0.08990pt、selection score差+0.0002658の区間は-0.0000566〜+0.0005852で、採用gateを僅かに通らなかった。coverageはdevelopment -0.18599pt、confirmation -0.42968pt、all -0.27985ptへ確定低下した。年別はaccuracy/score各5/7、Brier/log loss/ECE各5/7foldだった。

## 既存broad候補との比較

| candidate | all rows | coverage | accuracy | selection score | Shock accuracy/score fold勝敗 |
|---|---:|---:|---:|---:|---:|
| Shock | 220,743 | 50.18244% | 52.68887% | 0.0175721 | — |
| Profile | 221,844 | 50.43273% | 52.68116% | 0.0175648 | 3/7, 2/7 |
| EWMA | 221,618 | 50.38135% | 52.69382% | 0.0176449 | 4/7, 4/7 |
| Haar | 221,540 | 50.36362% | 52.69838% | 0.0176739 | 3/7, 3/7 |
| Profile × TCN | 218,343 | 49.63683% | 52.72988% | 0.0177572 | 3/7, 4/7 |

ShockはProfileにall accuracy +0.00771pt、score +0.0000073だったが区間は0を跨ぎ、coverageは-0.25030ptへ確定低下した。Brier差+0.000006242とlog loss差+0.000012476は悪化区間が確定した。confirmationではProfileよりaccuracy・scoreとも点値が低かった。EWMA、Haar、Profile×TCNにもaggregate accuracy/scoreを更新しなかった。

Profile confidenceとShock confidenceの固定50/50平均はdevelopment score 0.0191487、confirmation 0.0126986、all 0.0174631で、Profileの0.0191423、0.0130197、0.0175648を確認期間と全期間で下回り、年別accuracy/scoreも各2/7対Profile 5/7だった。多様化成分として採用しない。

## 高信頼度と校正

Shockのconfirmation cumulative accuracyは0.515で52.48229%、0.525で53.42926%、0.535で54.92708%、0.55で57.96610%と単調に上昇した。各閾値のmean confidenceは52.47778%、53.34371%、54.21228%、55.54222%であり、全閾値で局所整合した。development/allもaccuracyの単調性を満たしたが、0.515〜0.535は平均confidenceに対して過信だった。

0.55はconfirmation 885件、all 23,776件・56.14906%・coverage 5.40510%・score 0.0128273である。既存Directional Follow-throughはconfirmation 940件・58.51064%、all 24,328件・56.19040%・coverage 5.53059%・score 0.0130897でShockを上回った。Shockはaccuracy 2/7、score 1/7foldで、coverage低下のbootstrap区間も確定した。test2026_partialもShock 213件・48.35681%、Follow-through 228件・49.12281%で直近tailのedgeは未確認だった。

固定方向×volatilityの0.515 confirmationでは、`down × normal` が4,198件・50.76227%、Wilson下限49.249%でedge未確認だった。`up × high` は29,102件・53.10632%と比較的安定したが、確認後の除外・採用filterは作らない。confirmation全体の校正と信頼度順位は良好でも、global/localで一貫したfair oddsとは認可しない。

## latest

保存modelの最新M5は2026-06-01 04:55 UTC判定、up、`p(up)=0.5233003144`、volatility highだった。0.515は通るが、これはShock単体modelであり、方向維持25% full runtime blendではない。`odds_valid=false`、`strict_prediction_eligible=false`であり、運用へ接続しない。

## 判断

M5 Shock単体、通常25%方向blend、方向維持0.515/0.55、Pressure方向との固定50/50平均、Profile confidenceとの固定50/50平均をすべて再現専用とする。0.515のconfirmationでbaseline accuracy/selection score改善、全期間proper score改善、信頼度単調性を確認できたため、shock後状態加工がM5にも情報を持つことは確認できた。しかしall採用gateは僅かに未確定でcoverageを削り、方向はPressureよりproper scoreが有意に悪く、broad confidenceは既存Profile/EWMA/Haar/Profile×TCN、高信頼度はFollow-throughを超えず、固定多様化も親を上積みしなかった。

新しいconfig、registry、authoritative方向/confidence、fair odds、adoption/paper/live policyは発行・変更しない。同じ履歴でreference、shock閾値、追跡長、response cap、feature subset、model parameter、weight、閾値、subgroup filterを再探索しない。

## 成果物

- 実装・テスト: `src/trade_data/next_bar.py`, `tests/test_next_bar.py`
- 単体OOS: `experiments/next_bar/shock_recovery_state_m5_windows_canonical_001`
- 方向/方向維持blend: `experiments/next_bar/shock_recovery_state_m5_{direction,confidence}_blend_windows_canonical_001`
- candidate分析: `experiments/next_bar/shock_recovery_state_m5_candidate_analysis_windows.json`
- baseline bootstrap: `experiments/next_bar/shock_recovery_state_m5_{direction,confidence}_vs_baseline_bootstrap_20000_windows.json`
- 既存候補比較: `experiments/next_bar/shock_recovery_vs_{pressure,profile,ewma_asymmetry,haar,profile_tcn,follow_through}_m5_*_windows_comparison.json`
- 固定平均: `experiments/next_bar/{pressure_shock_equal_m5_direction,profile_shock_equal_m5_confidence}_windows_canonical_001`
- reliability/subgroup: `experiments/next_bar/shock_recovery*_m5_*_windows.json`
- latest: `experiments/next_bar/shock_recovery_state_m5_latest_prediction_windows.json`

## 検証

- 対象テスト: `2 passed, 94 deselected`（Mac 6.67秒、Windows 1.60秒）。
- 全テスト（Mac）: `1392 passed, 1 deselected, 280 warnings, 83 subtests passed`、124.40秒。
- 全テスト（Windows）: `1392 passed, 1 deselected, 280 warnings, 83 subtests passed`、48.85秒。
- deselectは今回と無関係な既存 `entry_ev` レポート `00384_2026-07-08_mql5_mt5_paid_expert_top_analysis.md` の内部時刻欠落1件。通常実行でも新規テストを含む1392件は成功した。
- 変更4ファイルのMac/Windows同期、差分の秘密情報scan 0件、`git diff --check` 成功を確認した。commit/pushは本commitで記録する。
