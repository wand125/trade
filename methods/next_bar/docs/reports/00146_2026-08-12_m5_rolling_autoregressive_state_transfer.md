# 00146 M5 Rolling Autoregressive State固定移植

日時: 2026-08-12 22:48 JST

## 目的

M15/M30で固定済みのRolling Autoregressive StateをM5へ無調整で移植し、次足方向、broad confidence、高信頼度、既存confidence候補への多様化に増分価値があるかを確認した。履歴returnをそのまま入力せず、局所AR係数、1-step forecast、fitted energy、innovationへ加工して使う。

## 固定仕様と品質

完成足log returnへ32/128本のridge AR(3)を因果的にfitした。ridgeは `0.05 * trace(X'X) / 3`、各窓で3係数、RMS正規化した次足forecast、fitted energy、直前行modelによる最新innovationを作り、短長forecast/energy/innovation差を加えた固定15特徴である。係数は2で割り、forecast/innovationは3 RMSで割って全列を `[-1,1]` にclipする。flat/gap窓は0。baseline 38特徴と合わせて53特徴で、生価格水準、volume、未来足をmodel featureへ使わない。

M1で確認済みの厳密ridge解、flat/gap reset、artifact/latestに加え、M5について15列の完全な集合、53特徴、定常性、有限 `[-1,1]`、価格10倍scale不変、未来側M1価格の改変が過去M5特徴へ影響しないことを回帰テストした。対象テストは2件成功した。

HGB 200 iteration、learning rate 0.05、31 leaves、min leaf 100、L2 1、最大750,000 train行、Platt、expanding、uniform weighting、全教師、seed 42、標準損失1.0を固定した。通常/方向維持blendはbaseline 75% + AR 25%。confidence gridは事前固定の0.51/0.515/0.525/0.535/0.55、developmentはtest2020〜2023、confirmationはtest2024〜2026_partialであり、AR次数、window、ridge、model parameter、weight、閾値、subgroup filterを結果に合わせて再探索していない。

Windows/WSL canonical環境で439,881 OOS行を既存baselineと完全整列した。共有中のComfyUI、Claude、Open WebUI、Ollamaを停止せず、GPUを非表示、単独8 thread、nice 10、ionice 7、空きmemory 16GiB・load 8 gateで実行した。開始時は空き27GiB、load 0.14だった。

## 単体と方向

| model | development accuracy | confirmation accuracy | all accuracy | all Brier | all log loss |
|---|---:|---:|---:|---:|---:|
| baseline | 51.91385% | 51.03316% | 51.57463% | 0.249535053 | 0.692215561 |
| AR単体 | 51.88575% | 50.91158% | 51.51052% | 0.249547161 | 0.692239931 |
| baseline 75% + AR 25% | 51.94010% | 50.98182% | 51.57099% | 0.249528395 | 0.692202206 |

AR単体はbaseline比development -76件、confirmation -206件、all -282件だった。通常25%方向blendはdevelopment +71件、confirmation -87件、all -16件、fix 3,519 / harm 3,535、McNemar p=0.8583、accuracy 4/7foldだった。Brier/log lossは5/7fold、all点値では改善したが、確認期間の方向悪化を優先して方向用途へ採用しない。

## broad confidence 0.515

developmentの固定gridでselection score最大は0.515だった。ただしbaselineの同閾値より僅かに低い。

| period | model | rows | coverage | accuracy | Wilson lower | selection score |
|---|---|---:|---:|---:|---:|---:|
| development | baseline | 158,280 | 58.52468% | 52.75588% | 52.50986% | 0.0192008 |
| development | AR | 158,274 | 58.52246% | 52.75535% | 52.50933% | 0.0191963 |
| confirmation | baseline | 63,694 | 37.59288% | 52.36600% | 51.97800% | 0.0121277 |
| confirmation | AR | 62,728 | 37.02274% | 52.48215% | 52.09120% | 0.0127242 |
| all | baseline | 221,974 | 50.46228% | 52.64400% | 52.43624% | 0.0173063 |
| all | AR | 221,002 | 50.24132% | 52.67780% | 52.46960% | 0.0175048 |

baseline比confirmation accuracy差+0.11615ptの日次95%区間は+0.01928〜+0.21267pt、selection score差+0.0005965の区間も+0.0000058〜+0.0011836で改善を支持した。一方coverageは-0.57014ptへ確定低下した。all accuracy/selection score区間は0を跨ぎ、coverageは-0.22097ptへ確定低下した。all Brier/log lossは改善区間だった。年別はARがaccuracy/score各5/7、proper score各5/7、ECE 6/7foldだったが、development目的を更新せず、単独採用には弱い。

## 既存broad候補との比較

| candidate | all rows | coverage | accuracy | selection score | AR accuracy/score fold勝敗 |
|---|---:|---:|---:|---:|---:|
| AR | 221,002 | 50.24132% | 52.67780% | 0.0175048 | — |
| Profile | 221,844 | 50.43273% | 52.68116% | 0.0175648 | 2/7, 3/7 |
| EWMA | 221,618 | 50.38135% | 52.69382% | 0.0176449 | 2/7, 2/7 |
| Haar | 221,540 | 50.36362% | 52.69838% | 0.0176739 | 3/7, 3/7 |
| Profile × TCN | 218,343 | 49.63683% | 52.72988% | 0.0177572 | 0/7, 0/7 |

Profileに対するARのall accuracy差は-0.00336ptで区間が0を跨いだが、coverageは-0.19142ptへ確定低下した。Brier差+0.00000720の95%区間は+0.00000093〜+0.00001363、log loss差+0.00001441は+0.00000179〜+0.00002734で、確率品質はProfileより明確に悪かった。EWMA、Haar、Profile×TCNにもaggregate accuracy/scoreを更新せず、特にProfile×TCNにはaccuracy/scoreとも0/7foldだった。

Profile confidenceとAR confidenceの固定50/50平均はProfile比all accuracy +0.00779pt、score +0.0000308だったが、accuracy/scoreの95%区間は0を跨ぎ、coverageは-0.12913ptへ確定低下した。confirmation scoreは-0.0000120で改善せず、Profile×TCNにはaccuracy/score各2/7だった。多様化成分として採用しない。

## 高信頼度と校正

ARのconfirmation cumulative accuracyは0.515で52.48215%、0.525で53.29647%、0.535で55.07303%、0.55で57.66423%と単調に上昇した。各閾値のmean confidenceは52.46947%、53.33278%、54.20268%、55.53178%である。0.515/0.525は実績とほぼ一致し、0.535/0.55は点値で過小評価だがWilson区間内だった。

ただし0.55はconfirmation 822件、all 24,032件・56.12101%・coverage 5.46330%・score 0.0128384である。既存Directional Follow-throughはconfirmation 940件・58.51064%、all 24,328件・56.19040%・coverage 5.53059%・score 0.0130897でARを上回った。ARはaccuracy 3/7、score 2/7foldで、confirmation Brier/log lossの日次区間もFollow-throughより明確に悪かった。test2026_partialもAR 202件・48.51485%、Follow-through 228件・49.12281%で、直近tailのedgeは未確認だった。

固定方向×volatilityの0.515 confirmationでは、`down × normal` が4,184件・50.78872%、Wilson下限49.27382%でedge未確認だった。`up × normal` も13,778件・51.61852%に対しmean confidence 52.40115%で過信した。確認後の除外filterは作らない。confirmation全体の累積帯は局所整合した一方、development/allの0.515以上は平均confidenceに対して過信であり、global/localに一貫したfair oddsとは認可しない。

## latest

保存modelの最新M5は2026-06-01 04:55 UTC判定、up、`p(up)=0.5222235623`、volatility highだった。0.515は通るが、これはAR単体modelであり、方向維持25% full runtime blendではない。`odds_valid=false`、`strict_prediction_eligible=false`であり、運用へ接続しない。

## 判断

M5 AR単体、通常25%方向blend、方向維持0.515/0.55、Profileとの固定50/50 confidence平均をすべて再現専用とする。0.515のconfirmationでbaseline accuracy/selection score改善、全期間proper score改善、信頼度単調性を確認できたため、局所AR状態加工がM5にも情報を持つことは確認できた。しかしdevelopment目的を更新せずcoverageを削り、Profileよりproper scoreが有意に悪く、Profile×TCNおよびFollow-throughの各roleを超えず、固定多様化も親を上積みしなかった。

新しいconfig、registry、authoritative方向/confidence、fair odds、adoption/paper/live policyは発行・変更しない。同じ履歴でAR次数、window、ridge、feature subset、model parameter、weight、閾値、subgroup filterを再探索しない。

## 成果物

- 実装・テスト: `src/trade_data/next_bar.py`, `tests/test_next_bar.py`
- 単体OOS: `experiments/next_bar/rolling_autoregressive_state_m5_windows_canonical_001`
- 方向/方向維持blend: `experiments/next_bar/rolling_autoregressive_state_m5_{direction,confidence}_blend_windows_canonical_001`
- candidate分析: `experiments/next_bar/rolling_autoregressive_state_m5_candidate_analysis_windows.json`
- baseline/Profile/Follow-through bootstrap: `experiments/next_bar/rolling_*ar*_m5_*bootstrap*.json`
- 既存候補比較: `experiments/next_bar/rolling_ar_vs_{profile,ewma,haar,profile_tcn,follow_through}_m5_*_windows_comparison.json`
- 固定平均: `experiments/next_bar/profile_rolling_ar_equal_m5_confidence_windows_canonical_001`
- reliability/subgroup: `experiments/next_bar/rolling_autoregressive_state_m5_*_windows.json`
- latest: `experiments/next_bar/rolling_autoregressive_state_m5_latest_prediction_windows.json`

## 検証

- 対象テスト: `2 passed, 93 deselected`
- 全テスト（Mac）: `1391 passed, 1 deselected, 280 warnings, 83 subtests passed`、122.89秒。
- 全テスト（Windows）: `1391 passed, 1 deselected, 280 warnings, 83 subtests passed`、47.53秒。
- deselectは今回と無関係な既存 `entry_ev` レポート `00384_2026-07-08_mql5_mt5_paid_expert_top_analysis.md` の内部時刻欠落1件。通常実行でも新規テストを含む1391件は成功した。
- Mac/Windows同期、秘密情報scan、commit/pushは最終commitで確認する。
