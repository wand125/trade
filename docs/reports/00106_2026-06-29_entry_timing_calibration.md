# Entry Timing Calibration

日時: 2026-06-29 06:56 JST
更新日時: 2026-06-29 06:56 JST

## 目的

`00105` で `pred_*_wait_regret` のhard gateは棄却した。次の確認として、wait regretを単純閾値で切らず、side / regime / predicted wait-regret bucket別に「待ったほうがよかった確率」をOOF校正し、soft risk penaltyとして使えるか検証した。

今回も採番と最新判断はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、ファイル内の作成時刻 `日時` を基準にする。

## 実装

`trade_data.meta_model entry-timing-calibration` を追加した。

入力:

- actual: `long_wait_regret`, `short_wait_regret`
- prediction: `pred_long_wait_regret`, `pred_short_wait_regret`
- group: default `combined_regime`
- OOF split: `dataset_month`

出力:

- `pred_entry_timing_<prefix>_<side>_calibrated_wait_regret`
- `pred_entry_timing_<prefix>_<side>_bad_wait_prob`
- `pred_entry_timing_<prefix>_<side>_wait_excess_mean`
- `pred_entry_timing_<prefix>_<side>_wait_underestimate_mean`
- `pred_entry_timing_<prefix>_<side>_bad_wait_prob_risk`
- `pred_entry_timing_<prefix>_<side>_wait_excess_risk`
- `pred_entry_timing_<prefix>_<side>_wait_underestimate_risk`
- support/source/bucket columns

Risk列は既存backtestの `--risk-penalties` にそのまま渡せるよう、危険度を負値で保存する。

## OOF Calibration

代表4ヶ月OOF predictionに `bad_wait_threshold=4` で校正列を追加した。

- examples/predictions: `data/reports/modeling/20260629_candidate_quality_downside_calibration/predictions_fixed_component_oof_downside_holding.parquet`
- output: `data/reports/modeling/20260629_entry_timing_calibration/predictions_oof_wait4.parquet`
- stats: `data/reports/modeling/20260629_entry_timing_calibration/predictions_oof_wait4.timing_stats.csv`

全体統計:

| side | pred_wait_mean | actual_wait_mean | bad_wait_prob | wait_excess_mean |
|---|---:|---:|---:|---:|
| long | 2.7645 | 2.9766 | 0.2404 | 0.9021 |
| short | 2.6076 | 2.8576 | 0.2201 | 0.7914 |

校正列はほぼgroup sourceで埋まった。

- long source: group `115203`, side `49`
- short source: group `115080`, side `172`

## Validation

固定条件:

- policy: `timed_ev`
- entry: `12`
- short offset: `6`
- side margin: `5`
- min entry rank: `0.5`
- max hold: `480`
- holding: `pred_*_exit_event_time_bin_expected_minutes`
- profit/loss: `1.0 / 1.20`
- side EV penalty: `short:combined_regime=down_low_vol:5`, `short:combined_regime=up_low_vol:10`, `short:combined_regime=range_low_vol:5`

### Bad Wait Probability Risk

| risk penalty | sum pnl | min month pnl | min trades | max DD | EV overestimate mean |
|---:|---:|---:|---:|---:|---:|
| 0 | 673.9120 | 145.5682 | 66 | 92.0350 | 13.4983 |
| 5 | 538.1352 | 39.2836 | 57 | 93.8920 | 13.9092 |
| 10 | 356.7892 | 43.0100 | 51 | 118.4344 | 14.8356 |
| 15 | 409.8094 | 21.6514 | 41 | 103.3024 | 14.5749 |
| 20 | 402.0882 | 38.9050 | 37 | 51.0204 | 14.5664 |

### Wait Excess Risk

| risk penalty | sum pnl | min month pnl | min trades | max DD | EV overestimate mean |
|---:|---:|---:|---:|---:|---:|
| 0 | 673.9120 | 145.5682 | 66 | 92.0350 | 13.4983 |
| 0.5 | 589.5164 | 98.7648 | 66 | 97.0928 | 13.8131 |
| 1.0 | 583.6608 | 53.5200 | 63 | 97.3176 | 13.7673 |
| 1.5 | 512.6904 | 60.7466 | 61 | 94.1252 | 14.1003 |
| 2.0 | 475.9004 | 58.5830 | 57 | 111.2546 | 14.1750 |

## 判断

`entry-timing-calibration` の実装は採用する。これはwait regretをhard gateではなく、校正済みの診断/ranking特徴量として残せるため。

ただし、soft risk penaltyとしての標準policy採用はしない。

理由:

- validation 4foldでrisk `0` がsum pnlとmin month pnlの両方で最上位。
- `bad_wait_prob_risk` は2024-07/2024-11だけ改善するpenaltyがあるが、2024-09と2025-01を大きく削る。
- `wait_excess_risk` も同様に、riskを入れるほどmin month pnlとsum pnlが悪化する。
- EV overestimate meanも改善せず、むしろ悪化する。
- validationで棄却されたため、holdout固定確認には進めない。ここでholdoutを見て候補を選ぶとpost-hocになる。

次はentry timingを単独riskにせず、candidate quality / side confidence / exit event probabilityと合わせたstacking特徴として使う。単独penaltyやhard gateは継続して避ける。

## Artifacts

- calibrated prediction: `data/reports/modeling/20260629_entry_timing_calibration/predictions_oof_wait4.parquet`
- calibration stats: `data/reports/modeling/20260629_entry_timing_calibration/predictions_oof_wait4.timing_stats.csv`
- bad wait probability validation: `data/reports/backtests/entry_timing_calibrated_bad_wait_prob_validation/`
- bad wait probability summary: `data/reports/backtests/entry_timing_calibrated_bad_wait_prob_summary/20260628_215532_model_sweep_summary/metrics.csv`
- wait excess validation: `data/reports/backtests/entry_timing_calibrated_wait_excess_validation/`
- wait excess summary: `data/reports/backtests/entry_timing_calibrated_wait_excess_summary/20260628_215532_model_sweep_summary/metrics.csv`

## Verification

- `python3 -m unittest tests.test_meta_model`: OK
- `python3 -m unittest tests.test_backtest tests.test_modeling tests.test_dataset tests.test_docs_reports`: OK
- `python3 -m trade_data.meta_model entry-timing-calibration --help`: OK
