# 00029 Path-persistence features

日時: 2026-08-08 11:41 JST

## 目的

価格履歴をそのまま使わず、直近経路がトレンド継続型か平均回帰型かを定常量へ加工し、M15次足方向とconfidence選別を改善できるか確認する。

## 結果前に固定した方法

- feature set: `--feature-set path_persistence`
- model: baselineと同じHGB、Platt calibration、expanding training。
- baseline加工特徴へ次の14列を追加した。
  - 5/10/20/50本の符号付きefficiency ratio
  - 10/20本のreturn autocorrelation
  - 10/20本の方向転換率
  - 50本窓における2/5/10本集約returnのvariance ratio
  - 20本のup継続率、down継続率
  - 最大20本でclipした符号付き連続方向長
- raw OHLC価格水準は特徴に含めない。
- M15 2020〜2026途中の同一7fold。通常25% blendとbaseline方向を維持する25% confidence blendを比較した。
- confidence閾値はdevelopment 2020〜2023の固定gridで選び、confirmation 2024〜2026途中へ固定した。

未来側OHLCを改変しても過去特徴が変わらないこと、stationary feature guard、artifact保存、最新推論をテストした。

## 単体と通常blend

| period | model | accuracy | Brier | log loss | ECE |
|---|---|---:|---:|---:|---:|
| development | baseline | 52.014% | 0.2493466 | 0.6918398 | 0.377% |
| development | single | 51.993% | 0.2493848 | 0.6919175 | 0.341% |
| confirmation | baseline | 51.501% | 0.2495525 | 0.6922506 | 0.298% |
| confirmation | single | 51.533% | 0.2495562 | 0.6922582 | 0.354% |
| all | baseline | 51.816% | 0.2494261 | 0.6919985 | 0.347% |
| all | single | 51.815% | 0.2494510 | 0.6920491 | 0.346% |

単体方向accuracyは全体で実質1件差だが、Brier/log lossが悪化したため置換しない。

通常25% blendはdevelopment accuracyを52.014%から52.073%へ改善した一方、confirmationは51.501%から51.433%へ悪化した。全体は51.816%から51.826%へ14件純改善しただけで、誤り修正1,889件、新規誤り1,875件、McNemar exact p=0.832である。方向edgeとして採用しない。

## 方向維持型confidence blend

| period | metric | baseline | candidate |
|---|---|---:|---:|
| development | Brier | 0.2493466 | 0.2493293 |
| development | log loss | 0.6918398 | 0.6918049 |
| development | ECE | 0.377% | 0.329% |
| confirmation | Brier | 0.2495525 | 0.2495390 |
| confirmation | log loss | 0.6922506 | 0.6922235 |
| confirmation | ECE | 0.298% | 0.300% |
| all | Brier | 0.2494261 | 0.2494103 |
| all | log loss | 0.6919985 | 0.6919666 |
| all | ECE | 0.347% | 0.317% |

Brier/log lossはdevelopmentとconfirmationの両方で改善し、fold改善も各6/7だった。ECEはconfirmationで僅かに悪化し、fold改善は4/7だった。

## developmentで選んだconfidence 0.525 lane

| period | model | rows | coverage | accuracy | selection score |
|---|---|---:|---:|---:|---:|
| development | baseline | 33,770 | 37.908% | 53.858% | 0.02048 |
| development | path blend | 32,996 | 37.040% | 53.952% | 0.02078 |
| confirmation | baseline | 14,785 | 26.375% | 53.777% | 0.01527 |
| confirmation | path blend | 14,814 | 26.427% | 53.976% | 0.01631 |
| all | baseline | 48,555 | 33.454% | 53.834% | 0.01961 |
| all | path blend | 47,810 | 32.941% | 53.959% | 0.02016 |

confirmationではcoverageを維持しながらaccuracyが0.199pt上がった。ただしaccuracy・selection scoreのfold改善は5/7で、2023と2025は悪化した。

## 既存0.525候補との比較

| period | candidate | coverage | accuracy | selection score |
|---|---|---:|---:|---:|
| development | clear-body | 35.639% | 54.173% | 0.02164 |
| development | path persistence | 37.040% | 53.952% | 0.02078 |
| confirmation | clear-body | 24.714% | 54.201% | 0.01675 |
| confirmation | path persistence | 26.427% | 53.976% | 0.01631 |
| all | clear-body | 31.419% | 54.182% | 0.02088 |
| all | path persistence | 32.941% | 53.959% | 0.02016 |

path persistenceはcoverageを1.4〜1.7pt増やすが、accuracyと採用評価関数は全3期間でclear-bodyを下回る。signed-body quantile 0.525のselection scoreもdevelopment 0.02100、confirmation 0.01689、全体0.02100でpath persistenceより高い。

## 最新推論確認

全期間の60%/20%/20%分割で別artifactを作成し、データ末尾の完成足まで `predict-latest` を実行した。2026-06-01 04:45 UTC判定はup、model confidence 0.54113だった。これは保存・推論経路の機能確認値であり、有効なempirical oddsではない。

## 判断

- 単体と通常方向blendは採用しない。
- 方向維持型0.525はconfirmationでもaccuracy、coverage、selection score、Brier、log lossを同時改善し、経路持続性がconfidence補助情報になることは確認できた。
- ただしfold再現性は5/7で、既存clear-bodyとquantileの評価関数を超えないためforward configは発行しない。
- 実装は再現用に残す。同じ履歴に合わせた窓長、variance aggregation、blend weight、閾値の再探索はしない。
- authoritative confidence、odds、現行policy、paper policyは変更しない。損失倍率は標準1.0のみとする。
