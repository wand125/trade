# Exit Holding Multifold Comparison

日時: 2026-06-29 05:28 JST
更新日時: 2026-06-29 05:32 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻である `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## 目的

`00098` でtime-bin classifier由来のholding列を作れるようにした。今回は単月smokeではなく、既存の代表4ヶ月validation predictionで exit holding sourceを同じgridに並べる。

対象predictionは `experiments/20260628_101740_policy_combined_side_exit_p1_l1p2/predictions_valid.parquet`。これは `2024-07`, `2024-09`, `2024-11`, `2025-01` を含む。

注意: このartifactはlog target追加前に生成されているため、`pred_*_exit_event_log_minutes` を持たない。したがって今回の比較は `raw_event`, `time-bin upper`, `time-bin expected`, `time-bin expected + hazard/event probability` に限定し、log-derived holdingの4fold比較は未実施。

## 実装

既存predictionを再学習せず比較へ使えるよう、`trade_data.modeling derive-exit-holding-columns` を追加した。

このCLIはprediction parquetへ次を後付けする。

- `pred_*_exit_event_minutes_from_log`
- `pred_*_exit_event_time_bin_minutes`
- `pred_*_exit_event_time_bin_expected_minutes`

source列がない場合はmetricsへ `missing_source_columns` として記録する。

今回の出力ではtime-bin由来列4本が追加され、log sourceは欠落として記録された。

## 設定

固定entry条件:

- policy: `timed_ev`
- entry threshold: `12`
- short offset: `6`
- side margin: `5`
- min entry rank: `0.5`
- short low-vol penalty: `down5,up10,range5`
- profit/loss multiplier: `1.0 / 1.20`

holding source:

| source | long column | short column |
|---|---|---|
| `raw_event` | `pred_long_exit_event_minutes` | `pred_short_exit_event_minutes` |
| `bin_upper` | `pred_long_exit_event_time_bin_minutes` | `pred_short_exit_event_time_bin_minutes` |
| `bin_expected` | `pred_long_exit_event_time_bin_expected_minutes` | `pred_short_exit_event_time_bin_expected_minutes` |
| `bin_expected_hazard` | `pred_long_exit_event_time_bin_expected_minutes` | `pred_short_exit_event_time_bin_expected_minutes` |

`bin_expected_hazard` は追加で `time_exit_penalty=6`, `loss_first_penalty=6`, `time_exit_holding_shrink=0.25`, `time_exit_exit_threshold=0.90`, `loss_first_exit_threshold=0.75` を使った。

capは `max_predicted_hold_minutes=480,720,1440`。cost scenarioはbaseとhigh cost。

## Base Results

| source | cap | min pnl | sum pnl | min trades | max DD | max forced exit | max smoothed miss |
|---|---:|---:|---:|---:|---:|---:|---:|
| `bin_expected` | `480` | `145.5682` | `673.9120` | `66` | `92.0350` | `0.0000` | `0.5833` |
| `raw_event` | `480` | `138.0272` | `668.5058` | `66` | `92.0350` | `0.0000` | `0.5833` |
| `bin_upper` | `480` | `125.0672` | `637.7780` | `68` | `92.8354` | `0.0000` | `0.5600` |
| `bin_upper` | `1440` | `118.4556` | `609.8334` | `36` | `89.5538` | `0.4595` | `0.5750` |
| `bin_upper` | `720` | `110.9058` | `564.0420` | `53` | `82.0224` | `0.0377` | `0.5758` |
| `raw_event` | `720` | `105.7870` | `548.8594` | `53` | `83.9268` | `0.0566` | `0.5781` |
| `raw_event` | `1440` | `92.2080` | `549.4548` | `43` | `89.2782` | `0.0698` | `0.5574` |
| `bin_expected` | `720` | `84.6606` | `590.6580` | `53` | `83.6028` | `0.0566` | `0.6000` |
| `bin_expected` | `1440` | `68.3034` | `584.8480` | `45` | `83.6028` | `0.0408` | `0.6078` |
| `bin_expected_hazard` | `720` | `61.1578` | `431.8998` | `28` | `89.8422` | `0.0000` | `0.5641` |
| `bin_expected_hazard` | `1440` | `58.7144` | `439.5766` | `26` | `97.5222` | `0.0000` | `0.5676` |
| `bin_expected_hazard` | `480` | `29.6696` | `395.0048` | `30` | `80.3124` | `0.0000` | `0.5714` |

## High Cost Results

High costは `spread=0.2`, `slippage=0.1`, `execution_delay_bars=1`。

| source | cap | min pnl | sum pnl | min trades | max DD | max forced exit | max smoothed miss |
|---|---:|---:|---:|---:|---:|---:|---:|
| `bin_expected` | `480` | `120.5842` | `562.8784` | `66` | `97.1906` | `0.0000` | `0.5833` |
| `raw_event` | `480` | `118.3126` | `556.6908` | `66` | `97.1906` | `0.0000` | `0.5833` |
| `bin_upper` | `1440` | `104.5422` | `551.9314` | `36` | `90.3712` | `0.4474` | `0.5952` |
| `bin_upper` | `480` | `100.1852` | `519.1280` | `68` | `98.3306` | `0.0000` | `0.5600` |
| `bin_upper` | `720` | `83.5516` | `458.6376` | `53` | `83.9112` | `0.0370` | `0.5758` |
| `raw_event` | `1440` | `82.0584` | `480.6954` | `44` | `88.7182` | `0.0667` | `0.5574` |
| `raw_event` | `720` | `79.9370` | `442.0820` | `54` | `85.6044` | `0.0545` | `0.5781` |
| `bin_expected` | `720` | `77.5840` | `492.5560` | `54` | `86.2326` | `0.0545` | `0.6000` |
| `bin_expected` | `1440` | `60.9314` | `509.1050` | `45` | `85.1124` | `0.0392` | `0.6226` |
| `bin_expected_hazard` | `1440` | `48.5688` | `393.7548` | `26` | `103.8396` | `0.0000` | `0.5676` |
| `bin_expected_hazard` | `720` | `48.3208` | `387.7916` | `28` | `97.4392` | `0.0000` | `0.5641` |
| `bin_expected_hazard` | `480` | `13.8064` | `343.8420` | `30` | `93.4960` | `0.0000` | `0.5714` |

## 判断

この固定entry条件では、base/high costとも `bin_expected`, cap `480` が最も安定した。

- base: min pnl `145.5682`, sum pnl `673.9120`
- high cost: min pnl `120.5842`, sum pnl `562.8784`

ただし `raw_event`, cap `480` との差は小さい。time-bin expectedが圧倒的に新しいedgeを作ったというより、holding表現を分類確率の期待値にしても従来raw event minutesと同等以上に動くことを確認した、という扱いにする。

hazard/event probabilityの固定penalty/dynamic exitは、今回のentry条件では全体を削った。trade数を減らしてforced exitを抑える効果はあるが、fold最低PnLと合計PnLが落ちるため標準採用しない。

重要な制約:

- このartifactにはlog predictionがないため、log-derived holdingの4fold比較はまだ未完了。
- 2025-04で見つかったMLP log smokeとはモデルもsplitも違うため、今回の4fold成績を2025-04 holdoutへ外挿しない。
- `bin_expected cap=480` は次のholdout監査候補にしてよいが、採用前に2024-12 / 2025-02 / 2025-03 / 2025-04の未使用・既使用holdout stressへ固定適用する。

## Artifacts

- derived predictions: `data/reports/modeling/20260629_policy_combined_exit_holding_columns/predictions_valid_exit_holding_columns.parquet`
- derive metrics: `data/reports/modeling/20260629_policy_combined_exit_holding_columns/predictions_valid_exit_holding_columns.metrics.json`
- base detail summary: `data/reports/backtests/exit_holding_multifold_base_summary.csv`
- base/high detail summary: `data/reports/backtests/exit_holding_multifold_base_highcost_summary.csv`
- base/high group summary: `data/reports/backtests/exit_holding_multifold_base_highcost_group_summary.csv`
- sweep roots: `data/reports/backtests/exit_holding_multifold_base_*` and `data/reports/backtests/exit_holding_multifold_highcost_*`

## Verification

- `python3 -m py_compile src/trade_data/modeling.py tests/test_modeling.py`: OK
- `python3 -m unittest tests.test_modeling`: OK, 46 tests
- `python3 -m unittest tests.test_modeling tests.test_docs_reports`: OK, 48 tests
- `python3 -m unittest discover tests`: OK, 146 tests
- `python3 -m trade_data.modeling derive-exit-holding-columns --help`: OK
- `python3 -m trade_data.modeling derive-exit-holding-columns`: OK
- `python3 -m trade_data.backtest model-sweep`: OK for base/high cost 4fold comparison
- `git diff --check`: OK
