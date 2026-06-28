# Selected Trade Quality Hybrid Gate

日時: 2026-06-28 23:19 JST
更新日時: 2026-06-28 23:19 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

前回の candidate-entry residual は、entry候補行だけに絞っても validation robustness が弱かった。今回はさらに絞り、1玉制約で実際に選ばれた selected trades だけを使って、HGB entry + MLP exit hybrid の trade quality calibration を再検証した。

既存の `oof-trade-quality-calibration` を使い、hybrid top policyの validation 4ヶ月実行trade 106件から side/session別に `pred_taken_ev -> adjusted_pnl` をOOF校正した。

結論:

- trade単位では raw bias `+15.8005` が calibrated bias `-0.4206` まで下がり、過大評価平均も `17.3736 -> 5.8545` へ改善した。
- ただし `min_trade_quality` gateとして使うと、validation topはgateなし `-inf` のまま。閾値を上げるほど fold最低PnLと取引数が落ちた。
- fixed 2024-12では `min_trade_quality=4` が `-54.6032 -> -4.6296` まで改善したが、2025-02は `+81.8334 -> +8.5648` に崩れる。
- 標準採用しない。selected-trade qualityは「過大評価診断」としては有効だが、単純な下限gateでは未来月の良いtradeも落としすぎる。

## Setup

Base policy:

- predictions: `data/reports/modeling/20260628_hgb_mlp_exit_hybrid/predictions_hgb_entry_mlp_exit_oof.parquet`
- policy: `timed_ev`
- entry threshold: `15`
- short entry offset: `4`
- side margin: `5`
- min entry rank: `0.5`
- holding columns: `pred_mlp_long_exit_event_minutes`, `pred_mlp_short_exit_event_minutes`
- max predicted hold: `480`
- evaluation: profit `1.0`, loss `1.20`

Validation trade generation:

| month | adjusted pnl | raw pnl | trades | max DD | forced |
|---|---:|---:|---:|---:|---:|
| 2024-07 | `106.4014` | `117.9640` | `23` | `25.7280` | `0` |
| 2024-09 | `81.5352` | `98.9710` | `24` | `33.9690` | `0` |
| 2024-11 | `117.0340` | `147.1450` | `31` | `60.0744` | `0` |
| 2025-01 | `92.0076` | `107.2740` | `28` | `59.6820` | `0` |

Calibration:

- CLI: `python3 -m trade_data.meta_model oof-trade-quality-calibration`
- source mode: `columns`
- source EV: `pred_long_best_adjusted_pnl`, `pred_short_best_adjusted_pnl`
- group columns: `session_regime`
- min group size: `5`
- prior strength: `20`
- prediction shrinkage: `0.65`
- selected validation trades: `106`

## Trade Quality Calibration

OOF selected-trade metrics:

| metric | value |
|---|---:|
| trade count | `106` |
| raw bias | `15.8005` |
| calibrated bias | `-0.4206` |
| bias reduction | `15.3798` |
| raw overestimate mean | `17.3736` |
| calibrated overestimate mean | `5.8545` |
| calibrated MAE | `12.1297` |
| calibrated RMSE | `17.0065` |
| calibrated R2 | `-0.0684` |

Final calibrator side stats:

| side | n | pred mean | target mean | target std |
|---|---:|---:|---:|---:|
| long | `51` | `17.9679` | `3.3581` | `15.2177` |
| short | `55` | `21.0085` | `4.1039` | `17.5130` |

校正は平均的な過大評価を大きく落とした。しかしR2は負で、tradeの良し悪しを個別に順位付けする力は弱い。

## Validation Gate Results

4fold summary:

| min trade quality | eligible | eligible folds | min pnl | sum pnl | min trades | max DD | EV over realized mean |
|---:|---|---:|---:|---:|---:|---:|---:|
| `-inf` | true | `4` | `81.5352` | `396.9782` | `23` | `60.0744` | `15.6838` |
| `0` | true | `4` | `68.7954` | `382.4130` | `23` | `60.0744` | `15.8225` |
| `2` | true | `4` | `55.8764` | `290.8736` | `21` | `61.2828` | `16.7819` |
| `4` | true | `4` | `21.0614` | `214.5450` | `10` | `54.1356` | `17.6467` |
| `6` | false | `1` | `-58.1698` | `49.6506` | `2` | `71.5258` | `22.3797` |
| `8` | false | `1` | `-23.2884` | `86.1756` | `0` | `36.6444` | `17.8399` |

`min_trade_quality` を上げるほど、trade数が減るだけでEV過大評価やdirection errorは改善しない。validationで採用できる台地はない。

## Fixed Holdout

2024-12:

| min trade quality | adjusted pnl | raw pnl | trades | PF | max DD | forced | EV over realized |
|---:|---:|---:|---:|---:|---:|---:|---:|
| `-inf` | `-54.6032` | `-18.1410` | `49` | `0.7504` | `97.3520` | `1` | `23.0714` |
| `0` | `-54.6032` | `-18.1410` | `49` | `0.7504` | `97.3520` | `1` | `23.0714` |
| `2` | `-13.5278` | `14.8310` | `47` | `0.9205` | `68.0316` | `0` | `22.5904` |
| `4` | `-4.6296` | `20.1380` | `42` | `0.9688` | `54.4624` | `0` | `23.2721` |
| `6` | `-8.7988` | `-0.4660` | `19` | `0.8240` | `19.6920` | `0` | `25.2318` |
| `8` | `-8.8202` | `-5.4730` | `5` | `0.5608` | `20.0832` | `0` | `31.1866` |

2025-02:

| min trade quality | adjusted pnl | raw pnl | trades | PF | max DD | forced | EV over realized |
|---:|---:|---:|---:|---:|---:|---:|---:|
| `-inf` | `81.8334` | `121.7120` | `118` | `1.3420` | `99.3504` | `0` | `23.1866` |
| `0` | `81.8334` | `121.7120` | `118` | `1.3420` | `99.3504` | `0` | `23.1866` |
| `2` | `59.5624` | `98.4650` | `115` | `1.2552` | `99.3504` | `0` | `23.4909` |
| `4` | `8.5648` | `46.3180` | `107` | `1.0378` | `114.2850` | `0` | `24.5837` |
| `6` | `-60.2624` | `-25.1240` | `78` | `0.7142` | `107.9318` | `0` | `26.9448` |
| `8` | `-21.6454` | `-1.0620` | `41` | `0.8247` | `65.5718` | `0` | `29.5532` |

2024-12ではgateが効いたように見えるが、2025-02の利益をほぼ消す。これは、2024-12の後付け防御としては説明力があるが、未知月へ汎化するquality rankingではない。

## Decision

- selected-trade quality calibrationは診断基盤として残す。
- `min_trade_quality` gateは標準policyへ採用しない。
- selected-trade targetは否定しない。今回は「group平均qualityを下限gateに使う」設計が弱い、という反証。
- 次は `min_trade_quality` のhard gateではなく、校正EVをentry EVへ置換する、または `pred_taken_ev - calibrated_quality` をsoft overestimate penaltyとして使う。
- もう一段進めるなら、実行trade単位で `direction_error`, `actual_profit_barrier_miss`, `large_loss`, `exit_regret` を分類targetにし、gateではなくrisk scoreとしてEVへ反映する。

## Artifacts

- validation trade runs: `data/reports/backtests/hybrid_top_trade_quality_validation_trades/`
- calibration 2024-12 apply: `data/reports/modeling/20260628_141725_selected_trade_quality_hybrid_session_p20_2024_12/`
- calibration 2025-02 apply: `data/reports/modeling/20260628_141743_selected_trade_quality_hybrid_session_p20_2025_02/`
- validation sweeps: `data/reports/backtests/selected_trade_quality_hybrid_session_p20_validation/`
- validation summary: `data/reports/backtests/selected_trade_quality_hybrid_session_p20_summary/20260628_141849_model_sweep_summary/`
- fixed tests: `data/reports/backtests/selected_trade_quality_hybrid_session_p20_fixed_tests/`

## Verification

- `PYTHONPATH=src python3 -m unittest tests.test_docs_reports`
- `git diff --check`
