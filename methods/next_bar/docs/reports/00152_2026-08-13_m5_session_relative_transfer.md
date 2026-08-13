# 00152 M5 Session Relative固定移植

日時: 2026-08-13 15:03 JST

## 目的

M1でprobability-quality方向候補、M15でconfidence shadowとして固定済みのSession RelativeをM5へ無調整で移植し、短期経路・足内Pressure・離散遷移とは異なる曜日×UTC時刻の季節性加工が、次足方向、確率品質、broad confidence、高信頼度へ増分価値を持つか確認した。

## 固定仕様と品質

曜日×UTC hourを168群とし、各群の現在足を除く直近32本、最小12本からreturn/body z-score、absolute-return/range ratio、方向biasの5列を作る。z-scoreは`[-10,10]`、ratioは`[0,10]`、biasは`[-1,1]`へ固定し、0/0は乖離なしの0とする。baseline 38列と合わせて43特徴で、生OHLC価格水準とvolumeは使わない。

HGB 200 iteration、learning rate 0.05、31 leaves、min leaf 100、L2 1、Platt、expanding、uniform weighting、全教師、最大750,000 train行、seed 42、標準損失1.0を固定した。通常/方向維持blendはbaseline 75% + Session 25%。confidence gridは0.51/0.515/0.525/0.535/0.55、developmentはtest2020〜2023、confirmationはtest2024〜2026_partialで、group粒度、window、min period、clip、parameter、weight、閾値、subgroup filterを結果に合わせて変更していない。

M5について完全5列、43特徴、有限値、生価格排除、価格10倍scale不変、未来側M1 OHLC変更が過去M5特徴へ影響しないこと、同一曜日×時刻の現在除外直近32本によるreturn z-scoreと方向biasの厳密式、train/latestを追加テストした。Mac/Windowsで対象2 testを通し、Windows canonical環境で既存baselineと完全整列する439,881 OOS行を生成した。共有中のComfyUI等を停止せず、GPU非表示、単独8 thread、nice 10、ionice 7、空きmemory 16GiB・load 8 gateを維持した。

## 単体と通常25% blend

| model | development accuracy | confirmation accuracy | all accuracy | all Brier | all log loss |
|---|---:|---:|---:|---:|---:|
| baseline | 51.91385% | 51.03316% | 51.57463% | 0.249535053 | 0.692215561 |
| Session単体 | 51.83990% | 51.24446% | 51.61055% | 0.249538131 | 0.692221690 |
| baseline 75% + Session 25% | 51.90719% | 51.08097% | 51.58895% | 0.249525739 | 0.692196835 |

単体はdevelopment -200件、confirmation +358件、all +158件、McNemar `p=0.39572`、accuracy/proper score各4/7未満で方向用途に使わない。通常25% blendはdevelopment -18件、confirmation +81件、all +63件、`p=0.50626`、accuracy 4/7、Brier/log loss 5/7foldだった。

通常blendのbaseline比all accuracy差+0.01432ptの日次20,000回bootstrap 95%区間は-0.02844〜+0.05588ptで未確定だった。一方、baseline−SessionのBrier差区間は+0.00000374〜+0.00001490、log loss差は+0.00000755〜+0.00002998で、確率品質改善は支持された。

既存Pressure方向blendはall accuracy 51.59645%、Brier 0.249521300、log loss 0.692187956で、Session通常blendはall -33件かつproper scoreも悪かった。両方向blendの固定50/50平均、すなわちbaseline 75% + Pressure 12.5% + Session 12.5%もall 51.58395%、baseline比+41件に留まり、Pressure比-55件、accuracy 3/7だった。Pressureとの差のaccuracy/Brier/log loss bootstrap区間は全て0を跨いだが、親を上積みする証拠がないため方向候補へ採用しない。

## 方向維持confidence

development gridの目的関数最大は事前固定0.515だった。

| period | rows | coverage | accuracy | selection score |
|---|---:|---:|---:|---:|
| development | 158,010 | 58.42485% | 52.77514% | 0.0193301 |
| confirmation | 63,784 | 37.64600% | 52.35482% | 0.0120693 |
| all | 221,794 | 50.42136% | 52.65426% | 0.0173716 |

baseline比ではdevelopment accuracy/scoreを上げたが、confirmationはaccuracy 52.36600%から52.35482%、score 0.0121277から0.0120693へ反転した。foldはaccuracy/score各3/7、proper score5/7で、単独confidence gateを満たさない。

既存Profile 0.515はall 221,844件、coverage 50.43273%、accuracy 52.68116%、score 0.0175648でSessionを上回った。SessionはdevelopmentでProfileを僅かに上回った一方、confirmationはaccuracy -0.16077pt、score -0.0009504へ反転し、直接比較はaccuracy/score各3/7だった。

Profile confidenceとSession confidenceの固定50/50平均もall accuracy 52.65603%、score 0.0173802、accuracy/score各3/7でProfileを下回った。confirmationではProfile−固定平均accuracy差+0.11809ptの日次区間+0.03073〜+0.20655pt、score差+0.0007112の区間+0.0001773〜+0.0012533で、Session追加による悪化が支持された。Profileを維持する。

## 高信頼度、信頼度品質、latest

Session confidenceはallの固定帯でaccuracy decrease violation 0件となり、0.51=52.3010%、0.515=52.6543%、0.525=53.3929%、0.535=54.3873%、0.55=56.1557%と単調に上昇した。信頼度順位付け自体は有効である。

0.55はall 23,864件・coverage 5.4251%・accuracy 56.1557%・score 0.012869、confirmation 859件・57.8580%・score 0.003224だった。既存Directional Follow-throughはall 24,328件・5.5306%・56.1904%・0.013090、confirmation 940件・58.5106%・0.003972で、Sessionはaccuracy/coverage/scoreを全て下回り、score 2/7対5/7だった。高信頼候補にも使わない。

保存Session単体modelの最新M5は2026-06-01 04:55 UTC判定、up、`p(up)=0.5241770183`、volatility highだった。単体artifactの機能確認値で、fair odds校正を付けていないため`odds_valid=false`、`strict_prediction_eligible=false`である。

## 判断

Session RelativeはM5でもbaseline確率品質を改善し、信頼度上昇と正答率が単調に対応した。しかし通常方向はaccuracy未確定かつPressureに点劣後、0.515は確認期間で反転してProfileに劣り、Profile/Pressureとの固定平均も親を上積みせず、0.55はFollow-throughを超えなかった。

M5 Session単体、通常25%方向、方向維持0.515/0.55、Pressure/Profileとの固定平均は全て再現専用とし、config・registry・authoritative方向/confidence・fair odds・paper/live policyを変更しない。曜日×時刻group、window 32、min 12、clip、HGB parameter、25% weight、閾値、subgroup filterを同じ履歴で再探索しない。Pressure方向、Profile/EWMA/Haar/Profile×TCN/Transition broad confidence、Follow-through 0.55を維持する。

## 成果物

- 実装・テスト: `src/trade_data/next_bar.py`, `tests/test_next_bar.py`
- 単体OOS: `experiments/next_bar/session_relative_m5_windows_canonical_001`
- 通常/方向維持blend: `experiments/next_bar/session_relative_m5_{direction,confidence}_blend_windows_canonical_001`
- 固定平均: `experiments/next_bar/{pressure,profile}_session_relative_equal_m5_*_windows_canonical_001`
- candidate分析・固定比較・20,000回UTC日bootstrap: `experiments/next_bar/*session_relative*_windows*.json`
- reliability: `experiments/next_bar/session_relative_m5_reliability_windows.json`
- latest: `experiments/next_bar/session_relative_m5_latest_prediction_windows.json`

## 検証

- 対象テスト `pytest tests/test_next_bar.py -k session_relative`: Mac 2 passed / 99 deselected（6.77秒）、Windows 2 passed / 99 deselected（1.93秒）。
- 既知の無関係なEntry EV docs時刻検査1件だけを明示deselectした全テスト: Mac 1,397 passed / 1 deselected / 83 subtests（138.85秒）、Windows 1,397 passed / 1 deselected / 83 subtests（49.35秒）。
- 除外した検査を単独実行すると、今回変更外の `methods/entry_ev/docs/reports/00384_2026-07-08_mql5_mt5_paid_expert_top_analysis.md` に内部日時がない既知理由だけで失敗することを再確認した。
- Windows OOSはbaselineと同じ439,881行・7fold、標準損失1.0、同一canonical platformで評価した。
- 口座runtime、login、password、token、secret、API key、private key、Windows Codex認証状態は同期・commit対象に含めない。
