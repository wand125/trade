# Log Exit Event Minutes Target

日時: 2026-06-29 05:09 JST
更新日時: 2026-06-29 05:09 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻である `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## 目的

`00095` と `00096` で確認した通り、exit minutesを非負制約なしの通常回帰としてpolicy holdingへ直結すると、未使用月で負値や異常大値を出して高回転化する。

この対策として、exit event minutesを `log1p(minutes)` で学習するtargetを追加し、予測時に `expm1(clip(log_pred, 0, log1p(1440)))` で `0..1440` 分へ戻す bounded holding列を作った。

目的はこのsmokeで勝つことではなく、policyへ渡すexit timing出力を物理的に妥当な範囲へ閉じること。

## 実装

datasetへ以下のtargetを追加した。

- `long_exit_event_log_minutes`
- `short_exit_event_log_minutes`

`policy` / `full` の regression target setにも追加し、prediction artifactには次の派生列を保存する。

- `pred_long_exit_event_minutes_from_log`
- `pred_short_exit_event_minutes_from_log`

派生列は `0` 分未満にならず、24時間強制決済ルールに合わせて最大 `1440` 分にclipする。

## Smoke

`2025-01` train、`2025-02` validation、`2025-04` testの小型MLP smokeを実行した。datasetは現行標準の `profit=1.0`, `loss=1.20` で再生成した。

学習は `max_iter=10`, `sample_frac=0.1` の配線確認用であり、性能候補として扱わない。`ConvergenceWarning` は想定内。

| split | target | MAE | R2 |
|---|---|---:|---:|
| valid | `long_exit_event_log_minutes` | `1.0146` | `-2.7658` |
| valid | `short_exit_event_log_minutes` | `1.0003` | `-7.5029` |
| test | `long_exit_event_log_minutes` | `2.0616` | `-5.4105` |
| test | `short_exit_event_log_minutes` | `2.0555` | `-9.8794` |

prediction分布では、raw minutes回帰はまだ負値・異常大値を出す。一方、log派生holdingは `0..1440` に収まった。

| column | min | median | p95 | max |
|---|---:|---:|---:|---:|
| `pred_long_exit_event_minutes` | `-54145.92` | `960.27` | `1181.82` | `1737.10` |
| `pred_short_exit_event_minutes` | `-125.60` | `787.82` | `1330.89` | `351152.22` |
| `pred_long_exit_event_minutes_from_log` | `0.00` | `783.77` | `1440.00` | `1440.00` |
| `pred_short_exit_event_minutes_from_log` | `0.00` | `787.19` | `1440.00` | `1440.00` |

## 2025-04 Backtest Smoke

MLP smoke predictionだけを使い、holding columnをlog派生列に差し替えて `timed_ev` を実行した。

設定は `entry=12`, short offset `6`, side margin `5`, rank `0.5`, max predicted hold `480`, short low-vol penalty `down5,up10,range5`。

| scenario | adjusted pnl | raw pnl | trades | win rate | profit factor | max DD | avg hold min | forced exit rate |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| base | `-28.4370` | `128.7810` | `93` | `0.5484` | `0.9699` | `369.8292` | `457.70` | `0.0430` |
| high cost | `-57.1444` | `97.4170` | `97` | `0.5361` | `0.9384` | `338.4370` | `438.21` | `0.0412` |

2025-04のNoTradeには届かないため、採用候補ではない。ただし `00095` のMLP holding破綻時の base `-477.6848` / high `-1503.3702` のような、負値holdingに起因する数千回高回転は止まった。

## 判断

log exit minutes targetとbounded派生列は採用する。これはシグナル改善ではなく、exit timing出力を安全にpolicyへ接続するための表現制約として扱う。

ただし今回の小型MLP smokeは汎化性能が低く、モデル候補にはしない。次は次の順で検証する。

- train/validation/testを複数foldへ戻し、log派生holdingでwalk-forward validationを行う。
- exit timingを連続minutesだけでなく、bin分類とhazard/event probabilityへ分解する。
- bounded holdingでもentry/side EVが崩れる月は残るため、entry qualityとexit timingを分けて失敗分析する。
- 2025-04に直接thresholdを合わせず、validationで選んだ候補だけを未使用月へ固定適用する。

## Artifacts

- smoke model: `experiments/20260628_200711_shared_mlp_log_exit_smoke_2025_04/`
- test predictions: `experiments/20260628_200711_shared_mlp_log_exit_smoke_2025_04/predictions_test.parquet`
- base sweep: `data/reports/backtests/shared_mlp_log_exit_smoke_2025_04_base_sweep/20260628_200852_model_sweep_2025-04/`
- high-cost sweep: `data/reports/backtests/shared_mlp_log_exit_smoke_2025_04_highcost_sweep/20260628_200852_model_sweep_2025-04/`

## Verification

- `python3 -m py_compile src/trade_data/dataset.py src/trade_data/modeling.py tests/test_dataset.py tests/test_modeling.py`: OK
- `python3 -m unittest tests.test_dataset`: OK, 6 tests
- `python3 -m unittest tests.test_modeling`: OK, 44 tests
- `python3 -m unittest tests.test_docs_reports`: OK, 2 tests
- `python3 -m unittest discover tests`: OK, 144 tests
- `python3 -m trade_data.dataset build`: OK for `2025-01`, `2025-02`, `2025-04`
- `python3 -m trade_data.modeling train-shared-mlp`: OK for log exit smoke, with expected `ConvergenceWarning`
- `python3 -m trade_data.backtest model-sweep`: OK for base/high-cost log-derived holding smoke
- `git diff --check`: OK
