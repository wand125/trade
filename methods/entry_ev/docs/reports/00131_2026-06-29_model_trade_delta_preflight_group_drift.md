# Model Trade Delta Preflight Group Drift

日時: 2026-06-29 10:54 JST
更新日時: 2026-06-29 10:54 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻である `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## 目的

`00130` で候補採用前のpreflightは追加できたが、case単位のfailだけでは「どのregimeが壊れたか」が見えにくい。

今回はpreflightにgroup drift出力を追加し、validationでプラスだったstatus/direction/regimeがholdoutでマイナスへ反転していないかを自動で確認する。

## 実装

`model-trade-delta-preflight` に以下の出力を追加した。

- `split_group_metrics_status_direction_combined_regime.csv`
- `group_drift_status_direction_combined_regime.csv`
- `split_stateful_group_metrics_status_direction_combined_regime.csv`
- `stateful_group_drift_status_direction_combined_regime.csv`

通常PnLは `group_by_month_status_direction_combined_regime.csv` を読み、stateful側は `group_by_blocking_candidate_month_status_direction_combined_regime.csv` を読む。

group driftは `delta_status`, `direction`, `combined_regime` ごとにvalidation/holdoutを集計し、以下をflag化する。

- `validation_positive_holdout_negative`
- `validation_nonnegative_holdout_negative`
- `*_holdout_minus_validation`

## 実データ確認

対象は `00130` と同じ、標準候補 vs validation top候補。

```bash
python3 -m trade_data.backtest model-trade-delta-preflight \
  --validation-deltas data/reports/backtests/20260629_014012_guard_fixed_parent_validation_base_delta,data/reports/backtests/20260629_014012_guard_fixed_parent_validation_highcost_delta \
  --holdout-deltas data/reports/backtests/20260629_014012_guard_fixed_parent_apply_base_delta,data/reports/backtests/20260629_014012_guard_fixed_parent_apply_highcost_delta \
  --label guard_fixed_entry_side_preflight_drift
```

summary:

- preflight pass: `False`
- PnL group validation-positive / holdout-negative: `10`
- stateful group validation-positive / holdout-negative: `10`

通常PnLの主な反転group:

| delta status | side | regime | validation delta | holdout delta | holdout - validation |
|---|---|---|---:|---:|---:|
| only_candidate | long | down_low_vol | `+84.3218` | `-93.4838` | `-177.8056` |
| only_candidate | short | down_normal_vol | `+25.4090` | `-91.0014` | `-116.4104` |
| only_candidate | short | up_normal_vol | `+36.7550` | `-35.2176` | `-71.9726` |
| only_candidate | long | down_normal_vol | `+6.6700` | `-14.7912` | `-21.4612` |

stateful netの主な反転group:

| delta status | side | regime | validation stateful | holdout stateful | holdout - validation |
|---|---|---|---:|---:|---:|
| only_candidate | short | down_normal_vol | `+25.4090` | `-228.1214` | `-253.5304` |
| only_candidate | long | down_low_vol | `+107.4676` | `-136.4816` | `-243.9492` |
| only_candidate | short | up_normal_vol | `+28.0524` | `-139.7138` | `-167.7662` |
| only_candidate | long | up_low_vol | `+35.6784` | `-125.5044` | `-161.1828` |

## 判断

validation top候補は、単に総取引数を減らして勝ったのではなく、validationでは良く見えた `only_candidate` regimeがholdoutで大きく反転している。

ただし、この結果をそのまま `long:down_low_vol` や `short:down_normal_vol` のhard blockにしない。過去にも局所blockは別月で壊れている。今回の使い方は以下に限定する。

- 候補採用前の反証説明として使う。
- 追加walk-forwardで同じ反転groupが再現するか確認する。
- 再現する場合は、hard blockではなくOOF downside / stateful target / regime drift featureへ戻す。

## Artifacts

- preflight drift: `data/reports/backtests/20260629_015420_guard_fixed_entry_side_preflight_drift/`
- PnL drift: `data/reports/backtests/20260629_015420_guard_fixed_entry_side_preflight_drift/group_drift_status_direction_combined_regime.csv`
- stateful drift: `data/reports/backtests/20260629_015420_guard_fixed_entry_side_preflight_drift/stateful_group_drift_status_direction_combined_regime.csv`

## Verification

- targeted preflight/group drift unit test: OK
- real preflight drift run: OK
- `python3 -m unittest tests.test_backtest tests.test_docs_reports`: OK, 76 tests
- `git diff --check`: OK
