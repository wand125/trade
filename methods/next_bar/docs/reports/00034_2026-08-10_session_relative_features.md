# 00034 Session-relative features

日時: 2026-08-10 13:32 JST

## 目的

XAU/USDの日内・週内で変わる通常の値動き水準を除き、現在足がその時間帯としてどの程度異常かを加工特徴にする。UTC時刻のsin/cosはbaselineに既にあり、入力volumeは全6,025,170行で0だったため、新しい情報として使わない。

## 結果前に固定した方法

feature setは `--feature-set session_relative`。baseline特徴へ次の5列を追加した。

1. `session_return_z_32`
2. `session_body_z_32`
3. `session_absolute_return_ratio_32`
4. `session_range_ratio_32`
5. `session_direction_bias_32`

同じUTC曜日×時に属する過去32本だけを参照し、現在足はrolling統計からshiftして除外する。最低12本、z-scoreは[-10, 10]、ratioは[0, 10]へ固定した。価格水準、未来足、target、volumeは含めない。M15では約8週間の同時間帯観測に相当する。

モデルはbaselineと同じHGB、Platt calibration、expanding training。2020〜2026途中の同一7foldで単体、通常25% blend、baseline方向を維持する25% confidence blendを比較した。confidence閾値は2020〜2023 developmentの固定gridだけで選び、2024〜2026途中へ固定した。

## 品質確認

未来側OHLCを変更しても過去特徴が変わらないこと、定常feature guard、価格水準排除、artifact保存、最新推論をテストした。

## 単体と通常blend

| period | model | accuracy | Brier | log loss | ECE |
|---|---|---:|---:|---:|---:|
| development | baseline | 52.014% | 0.2493466 | 0.6918398 | 0.377% |
| development | session single | 52.080% | 0.2493255 | 0.6917964 | 0.315% |
| confirmation | baseline | 51.501% | 0.2495525 | 0.6922506 | 0.298% |
| confirmation | session single | 51.341% | 0.2495572 | 0.6922603 | 0.394% |
| all | baseline | 51.816% | 0.2494261 | 0.6919985 | 0.347% |
| all | session single | 51.794% | 0.2494150 | 0.6919755 | 0.346% |

単体はdevelopmentだけ方向精度が上がり、confirmationで反転したため方向モデルとして棄却する。

通常25% blendもconfirmation accuracyを51.501%から51.440%へ下げた。誤り修正1,827件、新規誤り1,847件、McNemar exact p=0.754で方向edgeではない。

## 方向維持型confidence blend

| period | metric | baseline | session confidence |
|---|---|---:|---:|
| development | Brier | 0.2493466 | 0.2493163 |
| development | log loss | 0.6918398 | 0.6917784 |
| development | ECE | 0.377% | 0.344% |
| confirmation | Brier | 0.2495525 | 0.2495429 |
| confirmation | log loss | 0.6922506 | 0.6922315 |
| confirmation | ECE | 0.298% | 0.263% |
| all | Brier | 0.2494261 | 0.2494038 |
| all | log loss | 0.6919985 | 0.6919534 |
| all | ECE | 0.347% | 0.313% |

Brier/log lossは6/7 fold、ECEは5/7 foldで改善した。

## developmentで選んだconfidence 0.525 lane

| period | model | rows | coverage | accuracy | selection score |
|---|---|---:|---:|---:|---:|
| development | baseline | 33,770 | 37.908% | 53.858% | 0.02048 |
| development | session | 33,250 | 37.325% | 53.979% | 0.02103 |
| confirmation | baseline | 14,785 | 26.375% | 53.777% | 0.01527 |
| confirmation | session | 14,380 | 25.652% | 54.166% | 0.01697 |
| all | baseline | 48,555 | 33.454% | 53.834% | 0.01961 |
| all | session | 47,630 | 32.817% | 54.035% | 0.02055 |

accuracyとselection scoreは5/7 foldで改善した。2021と2025は両方が悪化した。

## clear-body 0.525との直接比較

| period | model | coverage | accuracy | selection score |
|---|---|---:|---:|---:|
| development | clear-body | 35.639% | 54.173% | 0.02164 |
| development | session | 37.325% | 53.979% | 0.02103 |
| confirmation | clear-body | 24.714% | 54.201% | 0.01675 |
| confirmation | session | 25.652% | 54.166% | 0.01697 |
| all | clear-body | 31.419% | 54.182% | 0.02088 |
| all | session | 32.817% | 54.035% | 0.02055 |

session版はconfirmationでcoverageとselection scoreが僅かに高いが、accuracyはclear-bodyが高い。developmentと全体はclear-bodyが上回り、直接年別accuracy/scoreはsession版が3/7 foldだけ改善した。Brier/log loss/ECEもclear-bodyより全体で悪く、直接fold改善は各3/7だった。

## 最新推論確認

全期間60%/20%/20%で実データartifactを別学習し、データ末尾まで `predict-latest` を実行した。2026-06-01 04:45 UTC判定はup、model confidence 0.57357だった。これは保存・推論経路の確認値で、empirical oddsとしては無効である。

## 判断

- session-relative単体と通常方向blendは棄却する。
- 方向維持型0.525はbaseline比でdevelopment/confirmation、5/7 fold、proper scoreを改善したため `config/m15_session_relative_confidence_shadow_v1.json` に固定する。
- clear-bodyよりconfirmation selection scoreは僅かに高いが、accuracy、development、全体、直接fold安定性、確率品質が劣るためforward candidateへは昇格しない。
- 完全未使用期間で固定0.525を並行監視し、同じ履歴でwindow、group粒度、clip、blend weight、閾値を再探索しない。
- authoritative confidence、fair odds、現行採用policy、paper policyは変更しない。損失倍率は標準1.0のみとする。
