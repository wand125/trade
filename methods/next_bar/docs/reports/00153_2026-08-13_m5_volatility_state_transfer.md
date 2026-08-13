# 00153 M5 Volatility State固定移植

日時: 2026-08-13 15:27 JST

## 目的

M1でbalanced secondary方向候補として固定済みのVolatility StateをM5へ無調整で移植し、価格履歴値を直接渡さず加工した変動状態が、次足方向、broad confidence、高信頼度、既存M5候補への多様化に増分価値を持つか確認した。

## 固定仕様と品質

完成足から次の固定11特徴を作り、baseline 38列と合わせて49特徴とした。

- 5本volatilityの20/50本vol-of-vol
- 5本volatilityの3本加速度、20本volatilityの5本加速度
- 20本rangeの変動係数、1-lag自己相関、中央値乖離
- prior 50本range中央値を下回る直近5本の圧縮率
- 20本realized varianceに対するbipower jump比率
- Parkinson/Garman–Klass varianceとclose varianceの対称balance

生OHLC価格水準、volume、未来足はmodel featureへ使わない。HGB 200 iteration、learning rate 0.05、31 leaves、min leaf 100、L2 1、Platt、expanding、uniform weighting、全教師、最大750,000 train行、seed 42、標準損失1.0を固定した。通常/方向維持blendはbaseline 75% + Volatility State 25%。confidence gridは0.51/0.515/0.525/0.535/0.55、developmentはtest2020〜2023、confirmationはtest2024〜2026_partialとした。window、jump/variance定義、feature subset、model parameter、weight、閾値、subgroup filterをM5結果に合わせて変更していない。

M5について完全11列、49特徴、定常性、生価格排除、有限値、価格10倍scale不変、未来側M1 OHLC改変が過去M5特徴へ影響しないこと、全11列の厳密式、flat有限0、train/latestを追加テストした。Windows canonical環境でbaselineと完全整列する439,881 OOS行・7foldを生成した。共有中の画像生成等を停止せず、GPU非表示、単独8 thread、nice 10、ionice 7、空きmemory 16GiB・load 8 gateを維持した。

## 単体と通常25% blend

| model | development accuracy | confirmation accuracy | all accuracy | all Brier | all log loss |
|---|---:|---:|---:|---:|---:|
| baseline | 51.91385% | 51.03316% | 51.57463% | 0.249535053 | 0.692215561 |
| Volatility State単体 | 51.86467% | 51.00129% | 51.53212% | 0.249544461 | 0.692234508 |
| baseline 75% + Volatility 25% | 51.89351% | 51.05205% | 51.56940% | 0.249529181 | 0.692203767 |

単体はbaseline比development -133件、confirmation -54件、all -187件、accuracy 1/7fold、McNemar `p=0.2640`で方向用途に使わない。通常25% blendはdevelopment -55件、confirmation +32件、all -23件、accuracy 4/7、Brier/log loss各6/7foldだった。方向accuracyの増分を確定せず、既存Pressure方向も置換しない。

## 方向維持confidence 0.515

developmentの事前固定gridで目的関数最大となった0.515を一度だけ固定した。

| period | model | rows | coverage | accuracy | selection score |
|---|---|---:|---:|---:|---:|
| development | baseline | 158,280 | 58.52468% | 52.75588% | 0.0192008 |
| development | Volatility | 157,478 | 58.22814% | 52.82325% | 0.0196616 |
| confirmation | baseline | 63,694 | 37.59288% | 52.36600% | 0.0121277 |
| confirmation | Volatility | 62,790 | 37.05933% | 52.43032% | 0.0124161 |
| all | baseline | 221,974 | 50.46228% | 52.64400% | 0.0173063 |
| all | Volatility | 220,268 | 50.07445% | 52.71124% | 0.0177099 |

Volatilityはbaseline比accuracy/selection score各6/7、Brier/log loss各6/7foldだった。20,000回UTC日bootstrapのVolatility−baseline差は次のとおりである。

| period | accuracy差 95%区間 | coverage差 95%区間 | score差 95%区間 | Brier差 95%区間 |
|---|---:|---:|---:|---:|
| development | +0.01301〜+0.12045pt | -0.36353〜-0.22977pt | +0.0000466〜+0.0008672 | -0.00001527〜-0.00000029 |
| confirmation | -0.03202〜+0.15927pt | -0.60471〜-0.46355pt | -0.0002987〜+0.0008658 | -0.00000746〜+0.00000240 |
| all | +0.02010〜+0.11406pt | -0.43700〜-0.33817pt | +0.0000691〜+0.0007353 | -0.00001073〜-0.00000091 |

development/allではaccuracy、selection score、proper scoreの改善が支持された。一方confirmationは全品質差が未確定で、coverage低下だけが確定した。全期間だけを見て確認期間の不確定性を無視しない。

## 既存候補との固定比較

| candidate 0.515 | all coverage | all accuracy | all score | accuracy/score fold |
|---|---:|---:|---:|---:|
| Profile | 50.43273% | 52.68116% | 0.0175648 | 4/7・4/7 |
| EWMA | 50.38135% | 52.69382% | 0.0176449 | 3/7・3/7 |
| Haar | 50.36362% | 52.69838% | 0.0176739 | 3/7・3/7 |
| Volatility | 50.07445% | 52.71124% | 0.0177099 | 4/7・4/7対EWMA/Haar |
| Profile×TCN | 49.63683% | 52.72988% | 0.0177572 | 5/7・4/7 |
| Profile×Transition | 47.95297% | 52.81175% | 0.0179952 | 6/7・6/7対Volatility |

VolatilityはProfile/EWMA/Haarよりall accuracy/scoreの点値が僅かに高いが、coverageが低く、直接bootstrapのaccuracy/score区間は0を跨いだ。Profile比all Brier/log lossはProfile優位で確定し、confirmationではProfile/Haarがaccuracy・scoreで上回った。

Profile×TransitionはVolatilityよりall accuracy +0.10051ptで95%区間+0.03338〜+0.16904pt、Brier/log lossも改善側だった。Volatilityはcoverageを+2.12148pt広げるがselection score差は未確定で、Profile自体よりもcoverageが狭いため独立coverage roleにはならない。

ProfileとVolatility confidenceの固定50/50平均はall accuracy 52.69093%、score 0.0175970でProfileを僅かに上回ったが、confirmationはProfileよりaccuracy -0.07282pt、score -0.0004931へ反転した。直接bootstrapもconfirmation/all accuracy・score区間が0を跨ぎ、all proper scoreはProfileより悪かった。親を増分改善するensembleとして採用しない。

## 信頼度、高信頼度、局所監査

Volatility confidenceの累積accuracyはdevelopment、confirmation、allの全てで閾値上昇に対して単調だった。confirmationでは0.515=52.43032%、0.525=53.27696%、0.535=55.19062%、0.55=58.64571%で、各累積帯の平均confidenceと局所整合した。0.515は62,790件、実測52.43032%、mean confidence 52.47590%である。

固定6セルのconfirmation 0.515では、down×normalが4,170件・50.57554%、Wilson下限49.05821%でedge未確認だった。down×highは8,068件・51.83441%、up×highは29,041件・53.06980%で、up×highのWilson下限52.49545%が最も強かった。診断後のセルをfilterへ変換しない。

0.55はall 23,318件・coverage 5.3010%・accuracy 56.00395%・score 0.012354、confirmation 827件・58.64571%だった。既存Follow-throughはall 24,328件・5.5306%・56.19040%・0.013090、confirmation 940件・58.51064%。Volatilityはaccuracy 3/7、selection score 0/7で、all score差Volatility−Follow-throughの95%区間は-0.001285〜-0.000178だった。高信頼度roleには使わない。

保存Volatility単体modelの最新M5は2026-06-01 04:55 UTC判定、up、`p(up)=0.5208389209`、volatility highだった。単体artifactの機能確認値で、fair odds校正を付けていないため`odds_valid=false`、`strict_prediction_eligible=false`である。

## 判断

Volatility StateはM5でもbaselineに対する有効な変動状態加工であり、0.515のdevelopment/all accuracy・selection score・proper scoreと、全期間の信頼度順位性を改善した。しかしconfirmationの主差は未確定、Profile/Haarより確認期間で反転、Profileとの固定平均も親を上積みせず、Profile×Transitionには全期間accuracy・proper scoreで明確に劣った。0.55はFollow-throughへselection score 0/7だった。

M5 Volatility単体、通常25%方向、方向維持0.515/0.55、Profileとの固定50/50平均を全て再現専用とする。新config・registryを発行せず、Pressure方向、Profile/EWMA/Haar/Profile×TCN/Profile×Transition broad confidence、Follow-through high confidence、authoritative方向/confidence、fair odds、paper/live policyを変更しない。同じ履歴でwindow、jump/variance定義、feature subset、parameter、weight、閾値、subgroup filterを再探索しない。

## 成果物

- 実装・テスト: `src/trade_data/next_bar.py`, `tests/test_next_bar.py`
- 単体OOS: `experiments/next_bar/volatility_state_m5_windows_canonical_001`
- 通常/方向維持blend: `experiments/next_bar/volatility_state_m5_{direction,confidence}_blend_windows_canonical_001`
- 固定平均: `experiments/next_bar/profile_volatility_state_equal_m5_confidence_windows_canonical_001`
- candidate分析・固定比較・20,000回UTC日bootstrap: `experiments/next_bar/*volatility_state*_windows*.json`
- reliability/subgroup: `experiments/next_bar/volatility_state_{vs_baseline_m5_reliability,m5_subgroups}_windows.json`
- latest: `experiments/next_bar/volatility_state_m5_latest_prediction_windows.json`

## 検証

- 対象テスト `pytest tests/test_next_bar.py -k volatility_state`: Mac 2 passed / 100 deselected（5.88秒）、Windows 2 passed / 100 deselected（1.57秒）。
- 既知の無関係なEntry EV docs時刻検査1件だけを明示deselectした全テスト: Mac 1,398 passed / 1 deselected / 83 subtests（138.70秒）、Windows 1,398 passed / 1 deselected / 83 subtests（51.06秒）。
- 除外した検査を単独実行すると、今回変更外の `methods/entry_ev/docs/reports/00384_2026-07-08_mql5_mt5_paid_expert_top_analysis.md` に内部日時がない既知理由だけで失敗することを再確認した。
- Windows OOSはbaselineと同じ439,881行・7fold、標準損失1.0、同一canonical platformで評価した。
- 変更4ファイルはMac/WindowsでSHA-256が全件一致し、`git diff --check`を通過した。変更ファイルとWindows側のVolatility State成果物に対する口座・login・password/token/secret・API key・private key形式の値は一致0件だった。
- 口座runtime、login、password、token、secret、API key、private key、Windows Codex認証状態は同期・commit対象に含めない。
