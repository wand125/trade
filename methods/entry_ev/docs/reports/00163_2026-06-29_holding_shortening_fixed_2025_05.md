# Holding Shortening Fixed 2025-05

日時: 2026-06-29 19:44 JST
更新日時: 2026-06-29 19:44 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

`00162` で固定候補にした `holding_shortening_threshold=0.60`, `holding_shortening_cap_minutes=60` を、未使用月2025-05へ再探索なしで適用した。

結果は disabled と完全同一だった。2025-05の実選択trade上では shortening probability の最大値が `0.5959` で、固定閾値 `0.60` に届かず発火0だったため。

そこで、2025-04 valid だけで確率スケールを再校正し、capは `60` 固定のまま threshold を選んだ。valid最良の `0.50 / 60` を2025-05へ固定適用すると、adjusted PnLは `-179.2516 -> -79.7894` へ改善した。ただしまだNoTrade未満であり、trade数は `56 -> 119` に増えた。標準採用はせず、probability calibrationとentry quality gateを次に進める。

## Implementation Fix

`trade_data.modeling train --target-set holding_shortening` を実行すると、EV side predictionがないのにselection metrics / EV calibration / report selection tableを前提として落ちた。

修正:

- `train()` は `SELECTION_COLUMNS` があるときだけselection metricsを出す。
- EV calibrationは `EV_TARGETS` が regression target に含まれるときだけ実行する。
- `write_report()` はselection metricsがないtarget-setでもreportを書ける。

この修正により、holding-shortening専用HGBをtrain/test splitでapply artifact化できるようになった。

## Model

Chronological apply model:

- train: `2023-01..2025-03`
- valid: `2025-04`
- test: `2025-05`
- dataset: `data/processed/datasets/xauusd_m1_p1_l1p2_policy_combined_dense_holding/`
- target set: `holding_shortening`
- `max_iter=80`
- `sample_frac=1.0`
- purge label overlap: enabled
- embargo: `24h`

Artifact:

- `data/reports/modeling/20260629_104053_20260629_holding_shortening_apply_2025_05/`

Rows after purge:

| split | rows |
|---|---:|
| train | `749,574` |
| valid | `26,192` |
| test | `30,147` |

Test 60m beat classification:

| target | accuracy | balanced accuracy | macro F1 |
|---|---:|---:|---:|
| `long_fixed_60m_beats_exit_event` | `0.5225` | `0.5212` | `0.4776` |
| `short_fixed_60m_beats_exit_event` | `0.5235` | `0.5153` | `0.4863` |

## Prediction Merge

Base EV/holding:

- `data/reports/modeling/20260629_hgb_mlp_exit_hybrid_2025_05/predictions_hgb_entry_mlp_exit_2025_05.parquet`

Holding-shortening test probabilities:

- `data/reports/modeling/20260629_104053_20260629_holding_shortening_apply_2025_05/predictions_test.parquet`

Merged output:

- `data/reports/modeling/20260629_holding_shortening_apply_2025_05_merged/predictions_2025_05_merged.parquet`
- rows: `30,147`
- range: `2025-04-30 23:59 UTC` to `2025-05-30 21:58 UTC`

Probability distribution:

| side | mean | p50 | p75 | max |
|---|---:|---:|---:|---:|
| long 60m beat prob | `0.5360` | `0.5304` | `0.5563` | `0.7473` |
| short 60m beat prob | `0.5261` | `0.5222` | `0.5523` | `0.6711` |

Actual selected trades under disabled policy:

- count: `56`
- selected shortening probability max: `0.5959`
- selected rows `>=0.60`: `0`
- selected rows `>=0.55`: `6`
- selected rows `>=0.50`: `34`

## Fixed Candidate

Evaluation:

- month: `2025-05`
- policy: `timed_ev`
- `entry_threshold=10`
- `side_margin=5`
- `profit_multiplier=1.0`
- `loss_multiplier=1.20`

| variant | adjusted pnl | raw pnl | trades | win rate | profit factor | max DD | forced exits | avg holding min |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| disabled | `-179.2516` | `-43.8680` | `56` | `0.5179` | `0.7793` | `269.5060` | `1` | `539.1071` |
| fixed `0.60 / 60` | `-179.2516` | `-43.8680` | `56` | `0.5179` | `0.7793` | `269.5060` | `1` | `539.1071` |

`0.60 / 60` は2025-05で発火せず、disabled同一だった。これはvalid/OFFで選んだraw probability thresholdを、別fitのapply modelへそのまま持ち込むとスケールが合わないことを示す。

Artifacts:

- disabled: `data/reports/backtests/holding_shortening_fixed_2025_05_disabled/20260629_104137_model_timed_ev_2025-05/`
- fixed `0.60 / 60`: `data/reports/backtests/holding_shortening_fixed_2025_05_t060_cap60/20260629_104137_model_timed_ev_2025-05/`

## Valid Calibration

2025-04 valid predictionをbase EV/holdingへ結合し、capは `60` 固定でthresholdだけをvalid内で比較した。

Valid artifact:

- `data/reports/modeling/20260629_holding_shortening_apply_2025_05_merged/predictions_2025_04_valid_merged.parquet`
- `data/reports/backtests/holding_shortening_threshold_calibration_2025_04/20260629_104318_model_sweep_2025-04/`

Valid result:

| threshold | cap | adjusted pnl | trades | profit factor | max DD | avg holding min |
|---:|---:|---:|---:|---:|---:|---:|
| `0.500` | `60` | `-43.7680` | `113` | `0.9513` | `443.0094` | `282.7168` |
| `0.575` | `60` | `-125.9514` | `55` | `0.8415` | `511.1144` | `634.6545` |
| `0.525` | `60` | `-130.7956` | `68` | `0.8465` | `501.6604` | `493.7059` |
| `0.550` | `60` | `-142.1956` | `59` | `0.8260` | `500.7884` | `574.6610` |
| `inf` | `60` | `-156.1574` | `51` | `0.8143` | `533.9704` | `685.2745` |
| `0.600` | `60` | `-156.1574` | `51` | `0.8143` | `533.9704` | `685.2745` |

Valid選定値:

- `holding_shortening_threshold=0.50`
- `holding_shortening_cap_minutes=60`

## Valid-Calibrated Fixed Test

2025-05へ `0.50 / 60` を再探索なしで適用した。

| variant | adjusted pnl | raw pnl | trades | win rate | profit factor | max DD | forced exits | avg holding min |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| disabled | `-179.2516` | `-43.8680` | `56` | `0.5179` | `0.7793` | `269.5060` | `1` | `539.1071` |
| valid-calibrated `0.50 / 60` | `-79.7894` | `47.0650` | `119` | `0.4622` | `0.8952` | `212.4794` | `1` | `231.5630` |

Artifact:

- `data/reports/backtests/holding_shortening_fixed_2025_05_t050_cap60_valid_calibrated/20260629_104332_model_timed_ev_2025-05/`

## Delta Diagnosis

Delta artifact:

- `data/reports/backtests/holding_shortening_fixed_2025_05_delta_t050_cap60/20260629_104345_model_trade_delta/`

Month summary:

| base trades | candidate trades | base pnl | candidate pnl | delta | removed positive | removed negative | added positive | added negative |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `56` | `119` | `-179.2516` | `-79.7894` | `+99.4622` | `178.7000` | `-315.7680` | `424.3930` | `-523.8168` |

Worst delta groups:

| status | direction | combined regime | rows | pnl delta |
|---|---|---|---:|---:|
| only_candidate | short | `up_normal_vol` | `16` | `-78.5240` |
| only_base | short | `range_normal_vol` | `4` | `-77.3640` |
| common | short | `range_normal_vol` | `7` | `-67.4950` |
| only_candidate | long | `range_normal_vol` | `4` | `-65.5270` |
| only_candidate | short | `range_low_vol` | `11` | `-38.6832` |

改善は明確だが、candidateはtrade数を倍増させ、悪い追加tradeも大量に入れている。保有短縮だけではentry qualityを担保できない。

## Interpretation

学び:

- Raw probability thresholdはfit方式が変わるとそのまま移植できない。`0.60` はOOF smoke / multimonthでは有効だったが、chronological apply modelでは選択tradeに発火しなかった。
- Valid月で閾値を再校正すると、2025-05では大幅改善した。
- それでもNoTrade未満で、trade数が増えすぎる。holding-shortening probabilityはexit timing補助として有望だが、entry quality / regime gate / side-specific filterと併用する必要がある。

次にやること:

- `0.50 / 60` を即採用しない。valid-calibrated thresholdとして候補に残す。
- `short/up_normal_vol`, `long/range_normal_vol`, `short/range_low_vol` のonly-candidate悪化を抑えるentry quality gateを組み合わせる。
- probability calibrationを明示的に行い、raw thresholdではなくcalibrated probabilityまたはvalidation quantileでpolicyへ渡す。

## Verification

- `python3 -m py_compile src/trade_data/modeling.py`: OK
- `python3 -m unittest tests.test_modeling`: OK, 47 tests
- `python3 -m unittest tests.test_modeling tests.test_docs_reports`: OK, 51 tests
- `python3 -m unittest discover -s tests`: OK, 187 tests
- holding-shortening train smoke: OK
- chronological train/apply: OK
- 2025-05 fixed backtests: OK
- 2025-04 threshold calibration sweep: OK
- 2025-05 delta diagnosis: OK
