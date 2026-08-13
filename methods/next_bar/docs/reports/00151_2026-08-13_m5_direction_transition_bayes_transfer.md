# 00151 M5 Direction Transition Bayes固定移植

日時: 2026-08-13 14:38 JST

## 目的

M1で固定済みのDirection Transition BayesをM5へ無調整で移植し、連続値の加工特徴をHGBへ渡す既存経路とは独立した離散状態・階層ベイズ学習が、次足方向、確率品質、broad confidence、高信頼度へ増分価値を持つか確認した。

## 固定仕様と品質

現在方向 `{-1,0,+1}`、同方向run lengthを0〜4へcapした値、直近8本の非flat遷移に占める反転率、5本/20本標準偏差比を0.8未満low・1.25超high・それ以外normalとした状態の4列を使う。baseline 38列と合わせて42特徴で、生OHLC価格水準とvolumeは使わない。135 encoded slot中81状態が構造的に到達可能である。

全体up率へ親状態をprior strength 256で縮約し、親確率へ完全状態を64で縮約する。Platt、expanding、uniform weighting、全教師、最大750,000 train行、seed 42、標準損失1.0を固定した。通常/方向維持blendはbaseline 75% + Transition 25%。confidence gridは0.51/0.515/0.525/0.535/0.55、developmentはtest2020〜2023、confirmationはtest2024〜2026_partialで、状態境界、prior、weight、閾値、subgroup filterを結果に合わせて変更していない。

M5について完全4列、42特徴、有限値、価格10倍scale不変、未来側M1 OHLCの変更が過去M5特徴へ影響しないこと、最終方向・run・反転率・volatility stateの厳密式、train/latest、135/81状態、prior 64/256を追加テストした。Windows/WSL canonical環境で既存baselineと完全整列する439,881 OOS行を生成した。共有中のComfyUI、Claude、Open WebUI、Ollamaを停止せず、GPU非表示、単独8 thread、nice 10、ionice 7、空きmemory 16GiB・load 8 gateを維持した。

## 単体と通常25% blend

| model | development accuracy | confirmation accuracy | all accuracy | all Brier | all log loss |
|---|---:|---:|---:|---:|---:|
| baseline | 51.91385% | 51.03316% | 51.57463% | 0.249535053 | 0.692215561 |
| Transition単体 | 51.44870% | 50.84489% | 51.21612% | 0.249763989 | 0.692675076 |
| baseline 75% + Transition 25% | 51.90460% | 51.12819% | 51.60555% | 0.249517587 | 0.692180734 |

単体はbaselineにaccuracy/Brier/log loss各0/7foldで方向用途に使わない。通常25% blendはdevelopment -25件、confirmation +161件、all +136件、accuracy 6/7foldだった。baseline比all accuracy差+0.03092ptの日次95%区間は-0.03478〜+0.09623ptで未確定だが、all Brier/log lossは改善側だった。既存Pressure方向にはdevelopment -107件、confirmation +147件、all +40件、accuracy 3/7対4/7で、直接bootstrapも主指標差が0を跨ぐため単独方向候補には採用しない。

## Pressureとの固定方向平均

既存Pressure通常25%方向blendとTransition通常25%方向blendを固定50/50平均した。これはbaseline 75% + Pressure 12.5% + Transition 12.5%に等しい。

| period | baseline accuracy | 固定平均 accuracy | net correct |
|---|---:|---:|---:|
| development | 51.91385% | 51.96598% | +141 |
| confirmation | 51.03316% | 51.06208% | +49 |
| all | 51.57463% | 51.61782% | +190 |

baseline比accuracyは7/7、Brier/log loss/ECEは各5/7fold改善した。all accuracy差95%区間は-0.00642〜+0.09371ptで未確定だが、Brier差区間-0.00003051〜-0.00001361、log loss差-0.00006126〜-0.00002715は改善側だった。Pressure比もaccuracy/score 5/7、all Brier/log loss区間を改善した一方、accuracy差+0.02137ptの区間は-0.02371〜+0.06778ptで未確定である。Pressureを置換せず、確率品質を前向きに比較するparallel direction shadowへ固定する。

## Profileとの固定confidence平均 0.515

Profile方向維持25% confidenceとTransition方向維持25% confidenceを固定50/50平均し、baseline方向を維持した。これはbaseline 75% + Profile 12.5% + Transition 12.5%に等しい。developmentの事前固定gridで0.515が目的関数最大だった。

| period | rows | coverage | accuracy | selection score |
|---|---:|---:|---:|---:|
| development | 151,362 | 55.96672% | 52.91355% | 0.0199147 |
| confirmation | 59,574 | 35.16122% | 52.55313% | 0.0127606 |
| all | 210,936 | 47.95297% | 52.81175% | 0.0179952 |

baseline 0.515比はaccuracy 7/7、proper score 5/7fold。all accuracy差+0.16775pt、selection score差+0.0006889、Brier/log lossの各95%区間は全て改善側で、confirmation accuracy差+0.18713ptの区間も+0.05182〜+0.32332ptだった。coverageはallで-2.50932ptへ確定低下した。

Profile 0.515比はaccuracy 7/7、score 3/7fold。all accuracy差+0.13059ptの区間+0.06890〜+0.19293pt、score差+0.0004305の区間+0.0000009〜+0.0008639、Brier/log lossも改善側だった。ただしconfirmation score差は-0.0002591、区間-0.0010108〜+0.0004916で未確定、coverageは-2.30772ptへ確定低下した。

Profile×TCN 0.515比もaccuracy/score各5/7fold、all accuracy差+0.08187ptの区間+0.02358〜+0.14099pt、Brier/log lossは改善側だった。一方、all score差区間は0を跨ぎ、coverageは-1.68386ptへ確定低下した。既存Profile/Profile×TCNを履歴だけで置換せず、accuracy・proper-quality specialistのparallel broad confidence shadowへ固定する。

## 信頼度、高信頼度、局所監査

固定平均の累積accuracyはdevelopmentで0.515=52.91355%、0.525=53.65713%、0.535=54.68220%、0.55=56.13073%、confirmationで52.55313%、53.47180%、55.44908%、56.43154%と単調に上昇した。confirmation 0.515/0.525/0.55はmean confidenceと局所整合したが、0.535以上はsupportが急減し、0.575は3件だけだった。

0.515 confirmationの固定6セルではdown×normalだけが3,699件・50.8516%、Wilson下限49.2404%でedge未確認、他5セルはWilson下限50%超だった。診断後のセルなのでfilterへ変換しない。

0.55はall 18,718件・coverage 4.2552%・accuracy 56.1385%・score 0.011194、confirmation 482件・56.4315%だった。既存Directional Follow-throughはall 24,328件・coverage 5.5306%・accuracy 56.1904%・score 0.013090、confirmation 940件・58.5106%である。固定平均はscore 0/7fold、all score差区間-0.002657〜-0.001152なので0.55を棄却し、Follow-throughを維持する。

## latestと判断

Transition単体保存modelの最新M5は2026-06-01 04:55 UTC判定、up、`p(up)=0.5036710893`、volatility highだった。0.515未満で、`odds_valid=false`、`strict_prediction_eligible=false`である。単体artifactの機能確認値で、固定3成分shadowのfull runtime parityやfair oddsではない。

Transition単体、通常25%方向、単独0.51 confidence、0.55高信頼度は再現専用とする。Pressure×Transition方向平均は確率品質用、Profile×Transition 0.515はaccuracy/proper-quality broad confidence用の非権威forward shadowとして `m5_transition_bayes_ensemble_shadow_v1.json` に固定する。Pressure、Profile、Profile×TCN、Follow-through、authoritative方向/confidence、fair odds、adoption/paper/live policy、registryは置換しない。

完全未使用期間で、方向shadowはPressure以上のaccuracyかつBrier/log loss非悪化、confidence shadowはProfile/Profile×TCN以上のaccuracy・selection scoreかつproper score非悪化、down-normal Wilson edge、global/local calibration、full runtime parityを要求する。同じ履歴で状態、prior、weight、閾値、subgroup filterを再探索しない。

## 成果物

- 実装・テスト: `src/trade_data/next_bar.py`, `tests/test_next_bar.py`
- 単体OOS: `experiments/next_bar/direction_transition_bayes_m5_windows_canonical_001`
- 単体方向/方向維持blend: `experiments/next_bar/direction_transition_bayes_m5_{direction,confidence}_blend_windows_canonical_001`
- 固定方向平均: `experiments/next_bar/pressure_transition_bayes_equal_m5_direction_windows_canonical_001`
- 固定confidence平均: `experiments/next_bar/profile_transition_bayes_equal_m5_confidence_windows_canonical_001`
- 分析・比較・20,000回UTC日bootstrap: `experiments/next_bar/*transition_bayes*_windows*.json`
- reliability/subgroup: `experiments/next_bar/profile_transition_bayes*_reliability_windows.json`
- latest: `experiments/next_bar/direction_transition_bayes_m5_latest_prediction_windows.json`
- forward config: `methods/next_bar/config/m5_transition_bayes_ensemble_shadow_v1.json`

## 検証

- 対象テスト `pytest tests/test_next_bar.py -k direction_transition`: Mac 2 passed / 98 deselected（5.21秒）、Windows 2 passed / 98 deselected（1.85秒）。
- 全テストを無除外で実行すると、Mac/Windowsとも今回変更外の `methods/entry_ev/docs/reports/00384_2026-07-08_mql5_mt5_paid_expert_top_analysis.md` に内部日時がない既知の整合性検査だけが失敗し、1 failed / 1,396 passed / 83 subtestsだった。
- 上記既知検査1件だけを明示的にdeselectした全テスト: Mac 1,396 passed / 1 deselected / 83 subtests（143.29秒）、Windows 1,396 passed / 1 deselected / 83 subtests（48.53秒）。
- 変更5ファイルはMac/WindowsでSHA-256が全件一致し、`git diff --check`を通過した。口座・login・password・token・secret・API key・private key形式の値は一致0件だった。
- 口座runtime、login、password、token、secret、API key、private key、Windows Codex認証状態は同期・commit対象に含めない。
