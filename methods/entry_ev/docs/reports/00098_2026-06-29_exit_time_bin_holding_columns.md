# Exit Time Bin Holding Columns

日時: 2026-06-29 05:18 JST
更新日時: 2026-06-29 05:18 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻である `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## 目的

`00097` ではlog回帰targetでexit minutesを `0..1440` 分へ閉じた。次の課題は、連続minutes回帰だけに依存せず、既存の `long_exit_event_time_bin` / `short_exit_event_time_bin` classifier出力も `timed_ev` のholding columnとして使えるようにすること。

今回の目的はbin分類の採用判断ではなく、既存targetからpolicyへ渡せるholding列を安定して生成すること。

## 実装

`prediction_frame` に以下の派生列を追加した。

- `pred_long_exit_event_time_bin_minutes`
- `pred_short_exit_event_time_bin_minutes`
- `pred_long_exit_event_time_bin_expected_minutes`
- `pred_short_exit_event_time_bin_expected_minutes`

class label由来の `*_minutes` はbin上限へ変換する。

| bin | range | mapped minutes |
|---:|---|---:|
| `0` | `0..15m` | `15` |
| `1` | `15..60m` | `60` |
| `2` | `60..240m` | `240` |
| `3` | `240..720m` | `720` |
| `4` | `720..1440m` | `1440` |
| `5` | `1440m+` | `1440` |

probability由来の `*_expected_minutes` は代表値 `[7.5, 37.5, 150, 480, 1080, 1440]` の期待値にする。classifierが一部classしか持たない場合、欠けたclassの確率は0として扱う。

これにより、次のようにbacktestへ渡せる。

```bash
--long-holding-column pred_long_exit_event_time_bin_expected_minutes
--short-holding-column pred_short_exit_event_time_bin_expected_minutes
```

## Smoke

`2025-01` train、`2025-02` validation、`2025-04` testで小型HGB smokeを実行した。設定は `max_iter=10`, `sample_frac=0.1` の配線確認用で、モデル候補として扱わない。

2025-04 testのtime-bin分類はまだ弱い。

| target | accuracy | balanced accuracy | macro F1 |
|---|---:|---:|---:|
| `long_exit_event_time_bin` | `0.0560` | `0.2765` | `0.0788` |
| `short_exit_event_time_bin` | `0.0909` | `0.2439` | `0.1162` |

派生列は保存できた。

| column | min | median | p95 | max |
|---|---:|---:|---:|---:|
| `pred_long_exit_event_time_bin_minutes` | `720.00` | `1440.00` | `1440.00` | `1440.00` |
| `pred_short_exit_event_time_bin_minutes` | `720.00` | `1440.00` | `1440.00` | `1440.00` |
| `pred_long_exit_event_time_bin_expected_minutes` | `694.46` | `803.93` | `945.47` | `997.36` |
| `pred_short_exit_event_time_bin_expected_minutes` | `689.25` | `795.43` | `953.66` | `1011.54` |

## 2025-04 Backtest Smoke

`pred_*_exit_event_time_bin_expected_minutes` をholding columnにして `timed_ev` を実行した。比較のため、同じHGB smoke prediction内の `pred_*_exit_event_minutes_from_log` でも同条件を実行した。

設定は `entry=12`, short offset `6`, side margin `5`, rank `0.5`, max predicted hold `480`, short low-vol penalty `down5,up10,range5`。

| holding source | scenario | adjusted pnl | raw pnl | trades | win rate | profit factor | max DD | avg hold min | forced exit rate |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| time-bin expected | base | `32.6798` | `143.4390` | `52` | `0.5769` | `1.0492` | `312.5000` | `609.98` | `0.0385` |
| time-bin expected | high cost | `13.4170` | `125.2650` | `54` | `0.5556` | `1.0200` | `316.0840` | `587.39` | `0.0370` |
| log-derived minutes | base | `32.6798` | `143.4390` | `52` | `0.5769` | `1.0492` | `312.5000` | `609.98` | `0.0385` |
| log-derived minutes | high cost | `13.4170` | `125.2650` | `54` | `0.5556` | `1.0200` | `316.0840` | `587.39` | `0.0370` |

このsmokeではtime-bin expectedとlog-derived holdingが同じtrade集合になった。多くのholdingが `max_predicted_hold_minutes=480` の上限側へ寄るためであり、bin分類がlog回帰より優れているとは判断しない。

## 判断

bin分類由来のholding派生列は採用する。採用理由は「勝ったから」ではなく、exit timingを連続回帰以外の表現からpolicyへ接続できるようになったため。

一方、今回の小型HGB smokeは分類指標が弱く、2025-04単月でlong-onlyに寄っている。モデル候補としては採用しない。

次の検証:

- 複数foldのHGB policy predictionで、log-derived / time-bin expected / time-bin upperを同じgridで比較する。
- `max_predicted_hold_minutes` を固定しすぎるとholding source差が消えるため、`480/720/1440` のcap別に比較する。
- time-bin分類だけでなく、event class probability (`time_exit`, `profit_first`, `loss_first`) と組み合わせたhazard-like exitを再評価する。
- 2025-04に直接合わせた採用はしない。

## Artifacts

- smoke model: `experiments/20260628_201748_hgb_time_bin_holding_smoke_2025_04/`
- test predictions: `experiments/20260628_201748_hgb_time_bin_holding_smoke_2025_04/predictions_test.parquet`
- time-bin expected base: `data/reports/backtests/hgb_time_bin_holding_smoke_2025_04_expected_base_sweep/20260628_201815_model_sweep_2025-04/`
- time-bin expected high cost: `data/reports/backtests/hgb_time_bin_holding_smoke_2025_04_expected_highcost_sweep/20260628_201815_model_sweep_2025-04/`
- log-derived base: `data/reports/backtests/hgb_time_bin_holding_smoke_2025_04_log_base_sweep/20260628_201836_model_sweep_2025-04/`
- log-derived high cost: `data/reports/backtests/hgb_time_bin_holding_smoke_2025_04_log_highcost_sweep/20260628_201836_model_sweep_2025-04/`

## Verification

- `python3 -m py_compile src/trade_data/modeling.py tests/test_modeling.py`: OK
- `python3 -m unittest tests.test_modeling`: OK, 44 tests
- `python3 -m unittest tests.test_modeling tests.test_docs_reports`: OK, 46 tests
- `python3 -m unittest discover tests`: OK, 144 tests
- `python3 -m trade_data.modeling train`: OK for HGB time-bin holding smoke
- `python3 -m trade_data.backtest model-sweep`: OK for time-bin expected and log-derived base/high-cost smoke
- `git diff --check`: OK
