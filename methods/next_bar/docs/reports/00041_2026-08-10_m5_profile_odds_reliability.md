# 00041 M5 Profile odds reliability

日時: 2026-08-10 14:48 JST

## 目的

M5 Intrabar Profileの方向維持confidenceが、単なる順位付けではなく「予測方向が正しい確率」として使えるか検証する。固定confidence帯ごとの実測accuracy、平均confidence、Wilson 95%区間、supportをdevelopmentとconfirmationへ分け、過去OOSだけで追加校正して次foldを測るnested odds calibrationも実施する。

## 固定した監査帯

結果を見る前に帯境界を0.500、0.515、0.525、0.535、0.550、0.575、0.600、1.000へ固定した。累積閾値も0.515、0.525、0.535、0.550、0.575、0.600だけを出力する。帯や閾値はaccuracy最大化のため再探索しない。

`compare_confidence_reliability.py` を追加し、次を機械可読JSONへ保存する。

- 各非重複帯と累積閾値のrows、coverage、accuracy、mean confidence。
- accuracy − mean confidenceのcalibration gap。
- Wilson上下限内にmean confidenceが入るか。
- Wilson下限が50%を超えるか。
- confidence上昇に対する帯別accuracyの単調性。

## Confirmationの高信頼度

| threshold | rows | coverage | accuracy | mean confidence | gap | Wilson lower | consistent | edge |
|---|---:|---:|---:|---:|---:|---:|---|---|
| 0.515 | 62,885 | 37.115% | 52.412% | 52.454% | -0.042pt | 52.021% | yes | yes |
| 0.525 | 24,128 | 14.241% | 53.498% | 53.273% | +0.225pt | 52.868% | yes | yes |
| 0.535 | 6,896 | 4.070% | 55.249% | 54.157% | +1.092pt | 54.073% | yes | yes |
| 0.550 | 668 | 0.394% | 57.784% | 55.624% | +2.161pt | 54.005% | yes | yes |
| 0.575 | 12 | 0.007% | 50.000% | 58.444% | -8.444pt | 25.378% | yes* | no |

`consistent` はmean confidenceが広いWilson区間内という意味であり、support十分を意味しない。0.575以上は12件しかなく、edge下限も50%を超えないため利用不可とする。0.600以上は0件だった。

採用閾値0.515では、baselineの実測52.355%・平均52.460%に対し、Profileは実測52.412%・平均52.454%。Profileはaccuracyを上げながら絶対calibration gapを0.105ptから0.042ptへ縮めた。

0.515、0.525、0.535、0.550の各累積laneはconfirmationでmodel confidenceがWilson区間内、かつaccuracy下限が50%超だった。高confidenceほど実測accuracyが上がる関係も0.550まで保たれた。ただし0.550は668件、0.394% coverageなので主candidateは0.515のままとし、0.550へ閾値変更しない。

## Developmentとの違い

development 0.515はaccuracy 52.794%に対しmean confidence 53.374%で、Wilson上限53.040%を0.334pt超える軽い過信だった。0.525と0.535も過信側である。一方、0.550以上は区間内だった。

confirmationで局所整合が改善しているものの、developmentとconfirmationの両方で0.515の厳密な局所整合を満たしてはいない。このため履歴結果だけでauthoritative fair oddsへ昇格させない。

## Nested chronological odds calibration

test2020を初期校正に使い、以後は各foldより前のOOSだけでreliability tableを作って次foldを評価した。最初のfoldは校正専用なので評価はtest2021〜2026途中の369,813行である。

| source | Brier | log loss | ECE |
|---|---:|---:|---:|
| baseline model confidence | 0.2496902 | 0.6925266 | 0.473% |
| Profile model confidence | 0.2496781 | 0.6925025 | 0.461% |
| Profile hierarchical empirical odds | 0.2497901 | 0.6927278 | 0.538% |

Profile model confidenceは同じbaseline方向に対して3指標をすべて改善し、Brierは実測accuracyを定数確率にしたnull 0.2498290も下回った。既存global gateのECE 1%以下も満たす。

一方、confidence 10分位×予測方向×volatility regimeの階層実績再校正は3指標をすべて悪化させた。追加テーブルでconfidence値を置換せず、元のblend model confidenceを選ぶ。

## 判断と成果物

- 固定帯比較: `experiments/next_bar/intrabar_profile_m5_reliability_analysis.json`
- Profile nested odds: `experiments/next_bar/intrabar_profile_m5_odds_calibration.json`
- baseline nested odds: `experiments/next_bar/baseline_m5_complete_odds_calibration.json`
- odds shadow設定: `methods/next_bar/config/m5_intrabar_profile_odds_shadow_v1.json`
- 比較器: `methods/next_bar/scripts/compare_confidence_reliability.py`

M5 Profile confidenceは0.515〜0.550のconfirmationで「信頼度が上がるほど正答率が上がる」「推定値と実測が区間上整合する」「下限も50%超」を満たした。オッズ候補として有望だが、0.515のdevelopment過信、0.575以上のsupport不足、最新推論でbaseline/Profile blendを再現するruntime経路が未検証である。

したがって `forward_shadow_local_odds` として固定し、authoritative fair oddsとpaper policyは変更しない。完全未使用期間で0.515の局所整合・edge下限・proper scoreを再確認し、runtime blend parity testが通った場合だけ昇格する。損失倍率は標準1.0のみとする。
