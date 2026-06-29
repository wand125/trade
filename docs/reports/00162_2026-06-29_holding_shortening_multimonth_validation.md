# Holding Shortening Multimonth Validation

日時: 2026-06-29 19:32 JST
更新日時: 2026-06-29 19:32 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

`00161` の2025-02単月smokeを、同じ base EV/holding prediction と holding-shortening probability の結合方式で 2025-02..2025-04 の3ヶ月へ拡張した。

結論として、`holding_shortening_threshold=0.60`, `holding_shortening_cap_minutes=60` が3ヶ月合計で最良だった。disabled は3ヶ月合計 `-172.4522`、`0.60 / 60` は `-53.9566` で、差分は `+118.4956`。2025-03はプラス化し、2025-04の大きな負けも大幅に縮んだ。

ただし、これは2025-02..04内で探索した結果であり、標準policy採用ではない。次の未使用月/固定holdoutで、`0.60 / 60` を再探索なしで確認する。

## Data Join

Base EV/holding:

- `data/reports/modeling/20260629_policy_combined_exit_holding_holdouts/predictions_test_2025_02_exit_holding_columns.parquet`
- `data/reports/modeling/20260629_policy_combined_exit_holding_holdouts/predictions_test_2025_03_exit_holding_columns.parquet`
- `data/reports/modeling/20260629_policy_combined_exit_holding_holdouts/predictions_test_2025_04_exit_holding_columns.parquet`

Holding-shortening probability:

- `data/reports/modeling/20260629_100956_20260629_dense_holding_shortening_oof_smoke_2025_02_04/predictions_oof.parquet`

Merged outputs:

- `data/reports/modeling/20260629_holding_shortening_policy_hook_multimonth/predictions_2025_02_merged.parquet`
- `data/reports/modeling/20260629_holding_shortening_policy_hook_multimonth/predictions_2025_03_merged.parquet`
- `data/reports/modeling/20260629_holding_shortening_policy_hook_multimonth/predictions_2025_04_merged.parquet`

Rows:

| month | rows | decision range UTC |
|---|---:|---|
| 2025-02 | `27,441` | `2025-01-31 21:59` to `2025-02-28 21:58` |
| 2025-03 | `28,972` | `2025-02-28 21:59` to `2025-03-31 23:58` |
| 2025-04 | `28,948` | `2025-03-31 23:59` to `2025-04-30 23:58` |

Shortening probability medians:

| month | long p50 | short p50 | long max | short max |
|---|---:|---:|---:|---:|
| 2025-02 | `0.4931` | `0.5652` | `0.6948` | `0.7621` |
| 2025-03 | `0.5335` | `0.5779` | `0.7258` | `0.8105` |
| 2025-04 | `0.5321` | `0.5552` | `0.7328` | `0.8086` |

## Sweep

条件:

- month: `2025-02`, `2025-03`, `2025-04`
- policy: `timed_ev`
- `entry_threshold=10`
- `side_margin=5`
- `risk_penalty=0`
- `profit_multiplier=1.0`
- `loss_multiplier=1.20`
- `holding_shortening_thresholds=inf,0.60,0.65,0.70,0.75`
- `holding_shortening_cap_minutes=30,60,120`

Artifacts:

- monthly sweeps: `data/reports/backtests/holding_shortening_policy_hook_multimonth_sweep/20260629_102935_model_sweep_2025-02/`, `...2025-03/`, `...2025-04/`
- summary: `data/reports/backtests/holding_shortening_policy_hook_multimonth_summary/20260629_103213_model_sweep_summary/`

Top aggregate candidates:

| threshold | cap | sum pnl | mean pnl | min pnl | max DD | mean trades | forced exits |
|---:|---:|---:|---:|---:|---:|---:|---:|
| `0.60` | `60` | `-53.9566` | `-17.9855` | `-43.7620` | `461.3556` | `69.6667` | `3` |
| `0.65` | `120` | `-119.4782` | `-39.8261` | `-96.9486` | `488.8364` | `52.0000` | `3` |
| `0.60` | `30` | `-133.9162` | `-44.6387` | `-88.3664` | `471.6436` | `88.0000` | `3` |
| `0.70` | `120` | `-139.4462` | `-46.4821` | `-119.5336` | `527.9464` | `46.3333` | `3` |
| `0.60` | `120` | `-148.4146` | `-49.4715` | `-133.3340` | `536.9004` | `57.6667` | `3` |
| `inf` | `60` | `-172.4522` | `-57.4841` | `-125.9826` | `533.9704` | `43.0000` | `3` |

Selected monthly comparison:

| month | variant | adjusted pnl | trades | profit factor | max DD | avg holding min |
|---|---|---:|---:|---:|---:|---:|
| 2025-02 | disabled | `-53.5244` | `34` | `0.7894` | `142.0054` | `600.0000` |
| 2025-02 | `0.60 / 60` | `-43.7620` | `46` | `0.8381` | `154.1220` | `404.8478` |
| 2025-02 | `0.65 / 120` | `-26.8748` | `38` | `0.8915` | `138.2088` | `502.3684` |
| 2025-03 | disabled | `7.0548` | `39` | `1.0266` | `100.5582` | `541.6154` |
| 2025-03 | `0.60 / 60` | `32.6068` | `78` | `1.1197` | `93.6258` | `238.1795` |
| 2025-03 | `0.65 / 120` | `4.3452` | `55` | `1.0158` | `122.0678` | `342.7636` |
| 2025-04 | disabled | `-125.9826` | `56` | `0.8523` | `533.9704` | `667.4821` |
| 2025-04 | `0.60 / 60` | `-42.8014` | `85` | `0.9508` | `461.3556` | `422.2118` |
| 2025-04 | `0.65 / 120` | `-96.9486` | `63` | `0.8819` | `488.8364` | `574.5556` |

## Summary Bug Fix

`model-sweep-summary` 実行時に `sweep_source` が重複追加され、`groupby(...).agg(fold_count=("sweep_source", "nunique"))` が失敗した。

原因:

- `read_sweep_frames()` が読み込み時に `sweep_source` を付ける。
- `summarize_sweep_frames()` 内の `normalize_sweep_metrics()` が、既存列の有無を見ずに `sweep_source` を再追加していた。

修正:

- 既存の `sweep_source` があれば尊重し、欠損だけfallback sourceで埋める。
- 既存sourceを持つframeを正規化しても `sweep_source` が1列のまま残る回帰テストを追加。

## Interpretation

`0.60 / 60` は3ヶ月で一貫して disabled を上回った。特に2025-04では `-125.9826 -> -42.8014` と大きく改善しており、長く持ちすぎる失敗を削れている可能性がある。

一方で、2025-02では `0.65 / 120` の方が良く、cap/thresholdの最適点は月ごとに動く。`0.60 / 60` は3ヶ月の中で最もバランスが良い候補だが、探索対象月で選んだ値なので、まだ採用してはいけない。

次の評価では `0.60 / 60` を固定候補として扱い、未使用月または新しく生成した apply prediction で再探索なし確認を行う。あわせて、forced exitが2025-04で3件残るため、cost stress / forced-exit rate / regime別損益も確認する。

## Verification

- `python3 -m py_compile src/trade_data/backtest.py`: OK
- `python3 -m unittest tests.test_backtest`: OK, 82 tests
- monthly `model-sweep`: OK
- `model-sweep-summary`: OK after `sweep_source` fix

## Next

- `0.60 / 60` を事前登録した固定候補として、未使用月へ再探索なしで適用する。
- holding-shortening probabilityをbase EV/holdingと同時生成する正式pipelineを作る。
- probability calibrationを確認し、`0.60` が月依存の過大評価閾値になっていないか調べる。
