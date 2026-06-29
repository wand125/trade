# Holding Shortening Quantile Calibration

日時: 2026-06-29 19:58 JST
更新日時: 2026-06-29 19:58 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

`00163` の弱点は、holding-shortening probabilityのraw thresholdがfit方式でスケール移動することだった。そこで、2025-04 valid predictionの経験CDFでquantile列を作り、raw probabilityではなくvalidation分布上の相対順位でcapを発火させた。

結論:

- quantile化は `0.25 / cap60` が2025-04 valid最良で、disabled `-156.1574` を `-43.7680` へ改善した。
- 同じ `0.25 / cap60` を2025-05へ固定適用すると disabled `-179.2516` に対して `-89.7428` まで改善した。
- ただし、前回raw valid-calibrated `0.50 / cap60` の2025-05 `-79.7894` よりは少し悪い。
- `short/up_normal_vol` だけをblockすると2025-05は `-77.1744` まで改善するが、2025-04 validのPnLは `-43.7680 -> -60.0166` に悪化するため、PnL最大化ルールでは選ばれない。
- validで見える悪いgroupをまとめてblockすると2025-04は `+45.2330` まで良化するが、2025-05は `-115.9068` に悪化した。これはpost-hoc group blockの過学習例として扱う。

## Implementation

追加:

- `src/trade_data/quantile_calibration.py`
- `scripts/experiments/holding_shortening_quantile_calibration.py`
- `tests/test_quantile_calibration.py`

`holding_shortening_quantile_calibration.py` は、fit predictionの指定列から経験CDFを作り、apply predictionへ以下の列を追加する。

- `pred_long_fixed_60m_beats_exit_event_valid_quantile`
- `pred_short_fixed_60m_beats_exit_event_valid_quantile`

今回は2025-04 validをfit分布として、2025-04 valid自身と2025-05 testへ同じCDF変換を適用した。

Artifacts:

- quantile predictions: `data/reports/modeling/20260629_holding_shortening_quantile_2025_04_05/`
- valid sweep: `data/reports/backtests/holding_shortening_quantile_threshold_calibration_2025_04/20260629_105535_model_sweep_2025-04/`
- test sweep: `data/reports/backtests/holding_shortening_quantile_fixed_2025_05/20260629_105550_model_sweep_2025-05/`

## Quantile Distribution

2025-04 valid fit raw probability:

| side | mean | p25 | p50 | p75 | p90 | max |
|---|---:|---:|---:|---:|---:|---:|
| long | `0.5414` | `0.4982` | `0.5319` | `0.5727` | `0.6607` | `0.7450` |
| short | `0.5282` | `0.4982` | `0.5236` | `0.5625` | `0.5923` | `0.6970` |

2025-05 apply quantile:

| side | mean | p25 | p50 | p75 | p90 | max |
|---|---:|---:|---:|---:|---:|---:|
| long quantile | `0.4889` | `0.2869` | `0.4874` | `0.6883` | `0.8346` | `1.0000` |
| short quantile | `0.4941` | `0.2680` | `0.4882` | `0.7097` | `0.8908` | `0.9923` |

raw分布は2025-05側でやや低く出るが、quantile列はvalidation CDF上の位置として比較可能になる。

## Valid Selection

2025-04 valid, `timed_ev`, `entry_threshold=10`, `side_margin=5`, `loss_multiplier=1.20`, `cap=60`。

| quantile threshold | adjusted pnl | trades | profit factor | max DD | avg holding min |
|---:|---:|---:|---:|---:|---:|
| `0.25` | `-43.7680` | `113` | `0.9513` | `443.0094` | `282.7168` |
| `0.50` | `-125.2276` | `68` | `0.8510` | `496.0924` | `493.9706` |
| `0.75` | `-142.6026` | `56` | `0.8224` | `501.7704` | `605.2857` |
| `inf` | `-156.1574` | `51` | `0.8143` | `533.9704` | `685.2745` |
| `0.90` | `-156.1574` | `51` | `0.8143` | `533.9704` | `685.2745` |
| `0.10` | `-199.2236` | `172` | `0.8329` | `576.9952` | `179.1163` |
| `0.05` | `-248.1750` | `210` | `0.8068` | `590.9786` | `140.7095` |
| `0.00` | `-358.3866` | `290` | `0.7590` | `624.8526` | `81.2931` |

valid最良は `0.25 / cap60`。これはraw threshold `0.50 / cap60` と同じvalid PnLになった。

## Fixed Test

2025-05へ再探索なしで適用。

| variant | adjusted pnl | raw pnl | trades | win rate | profit factor | max DD | forced exits | avg holding min |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| disabled | `-179.2516` | `-43.8680` | `56` | `0.5179` | `0.7793` | `269.5060` | `1` | `539.1071` |
| raw valid-calibrated `0.50 / 60` | `-79.7894` | `47.0650` | `119` | `0.4622` | `0.8952` | `212.4794` | `1` | `231.5630` |
| quantile `0.25 / 60` | `-89.7428` | `46.3150` | `127` | `0.4646` | `0.8901` | `222.6048` | `1` | `215.2126` |
| quantile `0.25 / 60` + block `short/up_normal_vol` | `-77.1744` | `45.9360` | `119` | `0.4874` | `0.8955` | `200.0362` | `0` | `192.4118` |
| quantile `0.25 / 60` + visible-bad block | `-115.9068` | `12.1850` | `118` | `0.4576` | `0.8492` | `217.7606` | `0` | `188.2881` |

visible-bad block:

- `short:combined_regime=up_normal_vol`
- `long:combined_regime=range_normal_vol`
- `short:combined_regime=range_low_vol`

このvisible-bad blockは2025-04 validでは `+45.2330` まで良化したが、2025-05では悪化した。bad groupをtest差分から増やすほど過学習しやすい。

## Delta Notes

quantile `0.25 / 60` vs disabled:

| month | base trades | candidate trades | base pnl | candidate pnl | delta |
|---|---:|---:|---:|---:|---:|
| 2025-04 | `51` | `113` | `-156.1574` | `-43.7680` | `+112.3894` |
| 2025-05 | `56` | `127` | `-179.2516` | `-89.7428` | `+89.5088` |

両月で改善はするが、trade数が倍増し、`short/up_normal_vol` は両月で悪い追加tradeとして現れる。

2025-04 worst groups:

| status | side | regime | rows | pnl delta |
|---|---|---|---:|---:|
| only_candidate | short | `up_normal_vol` | `11` | `-109.7880` |
| only_base | short | `down_normal_vol` | `2` | `-85.3200` |
| only_candidate | short | `down_normal_vol` | `9` | `-68.1000` |
| only_candidate | long | `range_normal_vol` | `1` | `-25.6320` |
| only_candidate | short | `range_low_vol` | `7` | `-20.0550` |

2025-05 worst groups:

| status | side | regime | rows | pnl delta |
|---|---|---|---:|---:|
| only_base | short | `range_normal_vol` | `4` | `-77.3640` |
| common | short | `range_normal_vol` | `7` | `-67.4950` |
| only_candidate | long | `range_normal_vol` | `4` | `-65.5270` |
| only_candidate | short | `up_normal_vol` | `18` | `-49.4340` |
| only_candidate | short | `range_low_vol` | `10` | `-32.6592` |

## Judgment

quantile化はraw thresholdのfit-scale問題を扱う実装として残す。ただし、今回の単月valid/testではraw valid-calibrated `0.50 / 60` を明確に超えない。

`short/up_normal_vol` blockは2025-05だけ見ると改善するが、2025-04 validのPnL最大化では選べない。visible-bad blockはvalidを大幅改善する一方でtestを壊したため、標準採用しない。これはregime blockを少数月のdeltaから作る危険性の実例。

次は、holding-shorteningを単純なcap発火ではなく、entry quality/risk modelのfeatureに戻すか、複数月walk-forwardでquantile thresholdを選ぶ。単月validだけでblock ruleを増やす方向は袋小路。

## Verification

- `python3 -m py_compile src/trade_data/quantile_calibration.py scripts/experiments/holding_shortening_quantile_calibration.py`: OK
- `python3 -m unittest tests.test_quantile_calibration`: OK, 2 tests
- `python3 -m unittest tests.test_quantile_calibration tests.test_docs_reports`: OK, 5 tests
- `python3 -m unittest discover -s tests`: OK, 189 tests
- quantile column generation for 2025-04/2025-05: OK
- 2025-04 quantile sweep: OK
- 2025-05 fixed quantile sweep: OK
- 2025-04/2025-05 delta diagnostics: OK
