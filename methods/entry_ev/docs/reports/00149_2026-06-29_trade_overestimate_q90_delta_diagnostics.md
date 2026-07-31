# Trade Overestimate Q90 Delta Diagnostics

日時: 2026-06-29 15:49 JST
更新日時: 2026-06-29 15:54 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻である `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## 目的

`00148` の `q90 w2.0` はvalidationと2025-05 fixed applyの両方で損益を改善した。

今回は `model-trade-delta` と `model-trade-delta-preflight` で、改善がどの取引差分に依存しているか、またvalidationで良く見えたgroupが2025-05で反転していないかを確認する。

## 対象

baselineは highcost `mean_match + session_floor_lowered risk=5`。candidateは `q90 w2.0` excess overestimate risk。

比較対象:

- validation: 2024-11..2025-04
- holdout/apply: 2025-05

## Delta Summary

月別差分:

| split | month count | base PnL | candidate PnL | delta | min month delta |
|---|---:|---:|---:|---:|---:|
| validation | 6 | `407.8172` | `460.6640` | `52.8468` | `-0.9926` |
| 2025-05 | 1 | `-52.9764` | `25.5248` | `78.5012` | `78.5012` |

validationは2025-03だけ小幅悪化し、他5ヶ月は改善した。2025-05は大きく改善した。

status別では構造が違う。

| split | status | delta | 補足 |
|---|---|---:|---|
| validation | only_candidate | `46.6642` | 追加trade自体が合計プラス |
| validation | only_base | `19.8270` | 外したbase tradeは小幅改善 |
| validation | common | `-13.6444` | 共通tradeはやや悪化 |
| 2025-05 | only_base | `158.6046` | 悪いbase tradeを外した効果が主 |
| 2025-05 | common | `12.8290` | 共通tradeも小幅改善 |
| 2025-05 | only_candidate | `-92.9324` | 追加tradeは大きく悪化 |

2025-05の改善は、candidateが新たに良いtradeを見つけたというより、base側の悪いtradeを外した効果が大きい。ここは採用時のリスクとして扱う。

## Positive And Negative Groups

validationで大きく良かったgroup:

| status | direction | combined regime | validation delta |
|---|---|---|---:|
| only_candidate | short | up_normal_vol | `109.0090` |
| only_base | long | up_low_vol | `55.6844` |
| common | short | range_normal_vol | `44.4396` |
| only_base | short | up_low_vol | `29.4360` |
| only_base | short | range_low_vol | `29.3110` |

validationで悪かったgroup:

| status | direction | combined regime | validation delta |
|---|---|---|---:|
| only_candidate | short | down_normal_vol | `-44.6100` |
| only_candidate | short | range_low_vol | `-38.0022` |
| common | short | down_normal_vol | `-34.9656` |
| only_candidate | long | up_low_vol | `-30.8274` |

2025-05で悪かったgroup:

| status | direction | combined regime | 2025-05 delta |
|---|---|---|---:|
| only_candidate | short | up_normal_vol | `-93.7270` |
| only_candidate | short | range_low_vol | `-51.4800` |
| only_base | short | range_normal_vol | `-14.0720` |

特に `only_candidate short/up_normal_vol` は、validationでは `+109.0090` だったが、2025-05では `-93.7270` に反転した。candidateの最大リスクはここ。

## Stateful / Blocking View

stateful candidate examples:

| split/month | candidate count | target mean | target sum | positive cost mean | blocking cost |
|---|---:|---:|---:|---:|---:|
| validation total | 529 | `0.9060` | `479.2626` | n/a | `193.6562` |
| validation min month 2025-04 | 79 | `-0.9005` | `-71.1366` | `-0.9611` | `96.8032` |
| 2025-05 | 106 | `1.2205` | `129.3704` | `-0.2185` | `48.6900` |

validation内でも2025-04はstateful targetが負。q90 w2.0 はvalidation PnLを改善するが、すべての月でstatefulに健全ではない。

worst stateful groups:

| split | direction | combined regime | target sum |
|---|---|---|---:|
| validation 2025-04 | short | range_normal_vol | `-67.4818` |
| validation 2024-12 | long | down_low_vol | `-63.8614` |
| validation 2025-04 | short | down_normal_vol | `-52.2010` |
| 2025-05 | long | down_low_vol | `-104.7140` |

2025-05では `long/down_low_vol` のcommon trade損失がまだ残っている。q90 overestimate riskはbaseの悪いshortを外せたが、long/down_low_volの構造的損失はまだ消せていない。

## Preflight

`model-trade-delta-preflight` 結果:

| metric | value |
|---|---:|
| validation case pass | `1 / 1` |
| holdout case pass | `1 / 1` |
| preflight pass | `true` |
| validation negative month count | `1` |
| holdout negative month count | `0` |
| group drift validation-positive / holdout-negative | `3` |
| stateful group drift validation-positive / holdout-negative | `2` |

PnL条件ではpass。ただしgroup driftは無視できない。

最悪のPnL group drift:

| status | direction | combined regime | validation delta | 2025-05 delta | holdout - validation |
|---|---|---|---:|---:|---:|
| only_candidate | short | up_normal_vol | `109.0090` | `-93.7270` | `-202.7360` |
| only_base | long | up_low_vol | `55.6844` | `-0.0800` | `-55.7644` |
| common | short | range_normal_vol | `44.4396` | `0.0000` | `-44.4396` |

最悪のstateful group drift:

| status | direction | combined regime | validation stateful | 2025-05 stateful | holdout - validation |
|---|---|---|---:|---:|---:|
| common | long | down_low_vol | `33.7666` | `-106.9060` | `-140.6726` |
| only_candidate | short | up_normal_vol | `102.5100` | `-15.4150` | `-117.9250` |

## 判断

1. `q90 w2.0` はPnL deltaとpreflightでは採用候補に残す。
2. ただし改善の質は完全ではない。2025-05は「悪いbase tradeを外した効果」が主で、only_candidateは合計 `-92.9324`。
3. validationで強かった `only_candidate short/up_normal_vol` が2025-05で反転しているため、同groupを盲信しない。
4. `long/down_low_vol` のcommon損失はq90 overestimate riskでは解消されていない。次のdownside targetまたはcontext riskの対象。
5. 標準policyへ即採用せず、q90 w2.0を固定候補としてさらに未使用月/chronological foldへ進める。

## Artifacts

- validation delta: `data/reports/backtests/20260629_064726_trade_overestimate_q90_w2p0_delta_validation/`
- 2025-05 delta: `data/reports/backtests/20260629_064544_trade_overestimate_q90_w2p0_delta_2025_05/`
- preflight: `data/reports/backtests/20260629_064900_trade_overestimate_q90_w2p0_delta_preflight/`

## 検証

- `model-trade-delta`: validation / 2025-05 とも完了
- `model-trade-delta-preflight`: 完了
- `python3 -m unittest tests.test_docs_reports`: pass
- `git diff --check`: pass

## 次の作業

1. q90 w2.0を追加未使用月に固定適用する。
2. `only_candidate short/up_normal_vol` をside/regime別の補助riskで抑える案は、2025-05を見たpost-hoc調整にならないよう、validation内だけで再定義する。
3. `long/down_low_vol` common損失を、overestimate riskとは別のwalk-forward downside/context targetで扱う。
