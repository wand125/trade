# Exit Holding Holdout Stress

日時: 2026-06-29 05:38 JST
更新日時: 2026-06-29 05:38 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻である `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## 目的

`00099` で代表4ヶ月validationの最上位だった `bin_expected cap=480` を、固定holdoutへそのまま適用する。

対象月:

- `2024-12`
- `2025-02`
- `2025-03`
- `2025-04`

`bin_expected` とvalidation上で差が小さかった `raw_event` も同条件で比較し、holding表現の差とentry/side崩れを分けて見る。

## 実装と設定

既存の各holdout predictionへ `trade_data.modeling derive-exit-holding-columns` を適用し、`pred_*_exit_event_time_bin_expected_minutes` を追加した。

固定policy:

- policy: `timed_ev`
- entry threshold: `12`
- long offset: `0`
- short offset: `6`
- side margin: `5`
- min entry rank: `0.5`
- profit/loss multiplier: `1.0 / 1.20`
- side EV penalty: `short:down_low_vol:5`, `short:up_low_vol:10`, `short:range_low_vol:5`
- holding cap: `480`

high cost:

- spread: `0.2`
- slippage: `0.1`
- execution delay bars: `1`

## Base Results

| source | month | adjusted pnl | raw pnl | trades | win rate | profit factor | max DD | forced exits |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| `bin_expected` | `2024-12` | `7.2314` | `63.1560` | `73` | `0.5205` | `1.0216` | `117.9006` | `3` |
| `bin_expected` | `2025-02` | `101.3432` | `153.4120` | `72` | `0.5000` | `1.3244` | `105.1896` | `0` |
| `bin_expected` | `2025-03` | `-0.9018` | `58.7680` | `83` | `0.4940` | `0.9975` | `87.8826` | `0` |
| `bin_expected` | `2025-04` | `-223.7292` | `-62.8020` | `86` | `0.4884` | `0.7683` | `474.6194` | `1` |
| `raw_event` | `2024-12` | `7.2314` | `63.1560` | `73` | `0.5205` | `1.0216` | `117.9006` | `3` |
| `raw_event` | `2025-02` | `98.6022` | `150.7490` | `72` | `0.4861` | `1.3151` | `105.7416` | `0` |
| `raw_event` | `2025-03` | `-0.9144` | `59.2680` | `83` | `0.4940` | `0.9975` | `87.9702` | `0` |
| `raw_event` | `2025-04` | `-157.1394` | `-3.0310` | `80` | `0.4625` | `0.8301` | `455.0816` | `1` |

Group summary:

| source | min pnl | sum pnl | positive months | max DD | total trades | forced exits |
|---|---:|---:|---:|---:|---:|---:|
| `raw_event` | `-157.1394` | `-52.2202` | `2` | `455.0816` | `308` | `4` |
| `bin_expected` | `-223.7292` | `-116.0564` | `2` | `474.6194` | `314` | `4` |

## High Cost Results

| source | month | adjusted pnl | raw pnl | trades | win rate | profit factor | max DD | forced exits |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| `bin_expected` | `2024-12` | `-19.0956` | `39.8740` | `75` | `0.4933` | `0.9460` | `116.6702` | `3` |
| `bin_expected` | `2025-02` | `55.1380` | `111.4300` | `72` | `0.4722` | `1.1633` | `120.9330` | `0` |
| `bin_expected` | `2025-03` | `-21.3864` | `40.9600` | `83` | `0.4819` | `0.9428` | `95.1884` | `0` |
| `bin_expected` | `2025-04` | `-200.9822` | `-44.7140` | `87` | `0.4943` | `0.7856` | `481.9694` | `1` |
| `raw_event` | `2024-12` | `-19.0956` | `39.8740` | `75` | `0.4933` | `0.9460` | `116.6702` | `3` |
| `raw_event` | `2025-02` | `46.5036` | `103.6390` | `72` | `0.4583` | `1.1357` | `123.1496` | `0` |
| `raw_event` | `2025-03` | `-23.4346` | `39.3910` | `83` | `0.4819` | `0.9378` | `96.9528` | `0` |
| `raw_event` | `2025-04` | `-167.4006` | `-11.9450` | `81` | `0.4691` | `0.8205` | `490.0372` | `1` |

Group summary:

| source | min pnl | sum pnl | positive months | max DD | total trades | forced exits |
|---|---:|---:|---:|---:|---:|---:|
| `raw_event` | `-167.4006` | `-163.4272` | `1` | `490.0372` | `311` | `4` |
| `bin_expected` | `-200.9822` | `-186.3262` | `1` | `481.9694` | `317` | `4` |

## 2025-04 Failure Breakdown

2025-04 baseの `bin_expected` は adjusted pnl `-223.7292`。entry decision timestampでprediction行へ結合すると、損失は次に集中していた。

Direction:

| direction | trades | adjusted pnl | mean pnl |
|---|---:|---:|---:|
| short | `56` | `-243.5286` | `-4.3487` |
| long | `30` | `19.7994` | `0.6600` |

Session:

| session | trades | adjusted pnl | mean pnl |
|---|---:|---:|---:|
| rollover | `13` | `-206.7266` | `-15.9020` |
| ny_late | `18` | `-127.7102` | `-7.0950` |
| london | `28` | `-37.4410` | `-1.3372` |
| ny_overlap | `12` | `26.5066` | `2.2089` |
| asia | `15` | `121.6420` | `8.1095` |

Direction x combined regime:

| group | trades | adjusted pnl | mean pnl |
|---|---:|---:|---:|
| `short:range_normal_vol` | `19` | `-145.5636` | `-7.6612` |
| `short:up_normal_vol` | `22` | `-144.7394` | `-6.5791` |
| `long:range_normal_vol` | `10` | `-110.9304` | `-11.0930` |

既存のside EV penaltyはlow-volだけを対象にしているため、この2025-04のnormal-vol failureを止められていない。

## 判断

`bin_expected cap=480` はvalidation 4foldでは最上位だったが、固定holdoutでは標準policyへ昇格しない。

理由:

- base/high costとも、4holdout合計と最低月PnLで `raw_event cap=480` に劣る。
- 2025-04でNoTradeに大きく負ける。
- 2025-04の主因はexit holding表現だけではなく、short normal-vol / rollover / ny_late のentry/side selection failure。
- high costではpositive monthが1ヶ月だけになり、コスト耐性も弱い。

次の方針:

- `bin_expected` は保持するが、標準candidateにはしない。
- 2025-04へ直接合わせたnormal-vol penaltyを採用しない。
- 次はvalidation fold内で `short:range_normal_vol`, `short:up_normal_vol`, `long:range_normal_vol`, `rollover`, `ny_late` のリスクを診断軸として事前登録し、cost-aware validationで台地があるか確認する。
- log-derived holding比較は、log列を含むdataset/train artifactを再生成して別枠で実施する。

## Artifacts

- derived holdout predictions: `data/reports/modeling/20260629_policy_combined_exit_holding_holdouts/`
- detail summary: `data/reports/backtests/exit_holding_holdout_bin_expected_vs_raw_summary.csv`
- group summary: `data/reports/backtests/exit_holding_holdout_bin_expected_vs_raw_group_summary.csv`
- bin expected base runs: `data/reports/backtests/exit_holding_holdout_bin_expected_base/`
- bin expected high cost runs: `data/reports/backtests/exit_holding_holdout_bin_expected_highcost/`
- raw event base runs: `data/reports/backtests/exit_holding_holdout_raw_event_base/`
- raw event high cost runs: `data/reports/backtests/exit_holding_holdout_raw_event_highcost/`

## Verification

- `python3 -m trade_data.modeling derive-exit-holding-columns`: OK for 4 holdout prediction files
- `python3 -m trade_data.backtest model-policy`: OK for 16 runs
- metrics aggregation: OK
- `python3 -m unittest tests.test_docs_reports`: OK, 2 tests
- `git diff --check`: OK
