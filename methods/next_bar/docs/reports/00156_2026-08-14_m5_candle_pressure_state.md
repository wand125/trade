# 00156 M5 Candle Pressure State

日時: 2026-08-14 21:46 JST

## 目的

M1でbaselineへの方向補完性が出たCandle Pressure StateをM5へ無調整で固定移植し、完成M5の実体・ヒゲ・終値位置を複数足へ集約する加工が、足内M1 Profileとは異なる時間構造として次足方向・confidenceを改善するか検証した。

## OOS前監査と固定仕様

各完成M5について次の3系列を `[-1, 1]` で作る。

- body pressure: `(close - open) / (high - low)`
- wick pressure: `(lower wick - upper wick) / (high - low)`
- close pressure: `(2 * close - high - low) / (high - low)`

3/8/21本の各固定窓で3系列の平均、range加重body/wick pressureを作り、3本平均−8本平均のbody/wick/close加速度を追加する。M1と同じ18列、baseline 38列と合わせて全56特徴である。生OHLC価格水準、未完成足、未来値、volumeはモデルへ渡さず、flat rangeの0/0は圧力証拠なしの0とする。

全履歴6,025,170 M1本から作った1,182,985完成M5のうちwarmup後1,182,895行をOOS前に監査した。完全重複はない。wick pressure系の既存baselineとの最大絶対Pearson相関は0.157〜0.309だった一方、body pressure meanは0.758〜0.811、range加重body pressureは0.830〜0.859、close pressureは0.553〜0.716、加速度は0.500〜0.618だった。冗長性はあるが、M1固定仕様の移植であるため結果を見る前に18列を削らず固定した。

HGB 200 iteration、learning rate 0.05、31 leaves、min leaf 100、L2 1、Platt、expanding、uniform weighting、全教師、最大750,000 train行、seed 42、標準損失1.0を使った。通常/方向維持blendはbaseline 75% + candidate 25%、gridは0.51/0.515/0.525/0.535/0.55、developmentはtest2020〜2023、confirmationはtest2024〜2026_partialである。

## 単体方向と通常25% blend

| period | baseline | Candle単体 | 通常25% blend |
|---|---:|---:|---:|
| development | 51.91385% | 51.89832% | 51.92124% |
| confirmation | 51.03316% | 51.05028% | 51.04261% |
| all | 51.57463% | 51.57168% | 51.58281% |

単体はbaseline比development -42件、confirmation +29件、all -13件、McNemar `p=0.9435`。全期間Brier/log lossも悪化し、単体方向には使わない。

通常blendは+20/+16/+36件、accuracy 4/7、Brier/log loss/ECE各5/7fold。baseline比all accuracy +0.00818ptの日次95%区間は-0.02894〜+0.04533pt、Brier差 -0.00000494の区間は-0.00001011〜+0.00000013で、いずれも未確定だった。

既存Intrabar Pressure方向blendに対してはdevelopment -62件、confirmation +2件、all -60件で、accuracyはCandle 4/7でもall Brier +0.00000881、log loss +0.00001765の悪化区間が確定した。両方向blendの事前固定50/50平均、すなわちbaseline 75% + Intrabar Pressure 12.5% + Candle Pressure 12.5%もdevelopment/confirmation/allでPressureに負け、accuracy 0/7、all accuracy -0.02796pt、Brier/log loss悪化区間が確定した。方向候補を更新しない。

## development選択0.515

事前固定gridで方向維持blendのdevelopment目的関数が最大となった0.515を一度だけ選択した。

| period | model | rows | coverage | accuracy | selection score |
|---|---|---:|---:|---:|---:|
| development | baseline | 158,280 | 58.52468% | 52.75588% | 0.0192008 |
| development | Candle | 158,100 | 58.45813% | 52.76091% | 0.0192273 |
| confirmation | baseline | 63,694 | 37.59288% | 52.36600% | 0.0121277 |
| confirmation | Candle | 62,654 | 36.97907% | 52.35899% | 0.0119661 |
| all | baseline | 221,974 | 50.46228% | 52.64400% | 0.0173063 |
| all | Candle | 220,754 | 50.18494% | 52.64684% | 0.0172747 |

all accuracyは+0.00283ptに過ぎず、日次区間は-0.04433〜+0.05052pt。coverage -0.27735ptは95% -0.32813〜-0.22487ptで減少が確定し、selection scoreも点低下した。confirmationでもaccuracy/scoreは下がり、coverage -0.61382ptが確定した。baseline採用gateを満たさない。

## Profileと既存role

固定0.515で親ではない既存Profileと直接比較すると、Candleはaccuracy/score各2/7foldだった。

| period | Candle coverage / accuracy / score | Profile coverage / accuracy / score |
|---|---:|---:|
| development | 58.45813% / 52.76091% / 0.0192273 | 58.55426% / 52.74754% / 0.0191423 |
| confirmation | 36.97907% / 52.35899% / 0.0119661 | 37.46894% / 52.51559% / 0.0130197 |
| all | 50.18494% / 52.64684% / 0.0172747 | 50.43273% / 52.68116% / 0.0175648 |

confirmationの日次差はaccuracy -0.15661pt（95% -0.26992〜-0.04421pt）、coverage -0.48987pt、score -0.0010536、Brier/log lossも全て悪化側だった。allもcoverageとproper scoreの悪化が確定した。

ProfileとCandle confidenceの固定50/50平均はdevelopmentでaccuracy/scoreを点改善したが、confirmationは63,042件・coverage 37.20807%・accuracy 52.41585%・score 0.0123574へ反転した。Profile比accuracy -0.09974pt（95% -0.17890〜-0.02006pt）、coverage -0.26087pt、score -0.0006623がすべて悪化側で、固定多様化にも使わない。

現行Profile × Transition 0.515に対してCandleはaccuracy 0/7、score 1/7fold。all accuracy 52.64684%対52.81175%、score 0.0172747対0.0179952で、accuracy・score・proper scoreのbootstrap区間も悪化側だった。

0.55のCandleはall 23,830件・coverage 5.41737%・accuracy 56.04280%・score 0.0125959、confirmation 811件・57.33662%・0.0027023だった。Directional Follow-throughはall 24,328件・56.19040%・0.0130897、confirmation 940件・58.51064%・0.0039719で、Candleはaccuracy/score各3/7、coverageとproper scoreの悪化が確定した。high-confidence roleも更新しない。

## 信頼度と最新推論

全期間の固定band accuracyは0.50〜0.51から0.60以上まで低下なしで、0.515/0.55の累積accuracyは52.64684% / 56.04280%、mean confidenceは53.11337% / 56.36794%だった。方向×volatilityの固定6セルは両閾値で全てWilson下限50%超だが、local consistencyは0.515で2/6、0.55で6/6セル。0.515は4セルで過信方向であり、結果後のcell filterにはしない。

保存済み最終artifactの最新M5は2026-06-01 04:55 UTC判定、up、`p(up)=0.5329706033`、volatility highだった。fair odds校正を付けていないため `odds_valid=false`、`strict_prediction_eligible=false` である。

## 判断

Candle Pressure StateはM5でも通常blendのproper scoreを5/7fold改善し、信頼度別accuracyは単調だった。しかし方向差は未確定、0.515はcoverageを有意に削って目的関数を下げ、確認期間ではProfileへ主要指標が有意に悪化した。Intrabar Pressureとの方向平均も7/7foldで負け、Profile × TransitionとFollow-throughを超えない。

`candle_pressure_state` のM5 OOS成果物は再現用に残すが、config、registry、authoritative予測、fair odds、paper/live policyは変更しない。同じ履歴で3/8/21窓、18列subset、高相関列除外、HGB parameter、blend weight、閾値、subgroup filterを再探索しない。損失倍率は標準1.0のみとする。

## 成果物

- M5追加テスト: `tests/test_next_bar.py`
- 単体OOS: `experiments/next_bar/candle_pressure_state_m5_windows_canonical_001`
- 通常/方向維持blend: `experiments/next_bar/candle_pressure_state_m5_{direction,confidence}_blend_windows_canonical_001`
- Pressure/Profile固定平均: `experiments/next_bar/{pressure_candle_pressure_equal_m5_direction,profile_candle_pressure_equal_m5_confidence}_windows_canonical_001`
- candidate分析・既存role比較・20,000回UTC日bootstrap: `experiments/next_bar/*candle_pressure*_windows*.json`
- reliability/subgroup: `experiments/next_bar/candle_pressure_state_{vs_profile_m5_reliability,m5_subgroups}_windows.json`
- latest artifact/prediction: `experiments/next_bar/candle_pressure_state_m5_latest_{artifact,prediction}_windows*`

## 検証

- M5について18列・全56特徴、定常性、価格10倍scale不変、未来M1改変不影響、flat有限0、train/latestをWindows対象テストで確認した。
- 既知の無関係なEntry EV docs時刻検査1件だけを明示deselectしたWindows全テストは1,400 passed / 1 deselected / 83 subtests（55.16秒）。
- Windows OOSはbaselineと同じ439,881行・7fold、標準損失1.0、同一canonical platformで評価した。
- Mac対象テストは共有高負荷処理との競合で収集だけに66秒かかったため、実行開始前に中断して母艦資源を解放した。
- 共有中の画像生成等を停止せず、GPU非表示、単独8 thread、nice 10、ionice 7、空きmemory 16GiB・load 8 gateを維持した。
- 口座runtime、login、password、token、secret、API key、private key、Windows Codex認証状態は同期・commit対象に含めない。
