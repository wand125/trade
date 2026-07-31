# Selected Trade Quality EV Replacement

日時: 2026-06-28 23:27 JST
更新日時: 2026-06-28 23:27 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

前回の selected-trade quality calibration は、実行trade単位の過大評価診断としては有効だったが、`min_trade_quality` hard gate では未来月の良いtradeも落とした。今回は hard gate ではなく、校正済みtrade qualityをそのまま long/short entry EV 列として置換し、低いthreshold帯で `timed_ev` を再評価した。

結論:

- strict validation 4foldで eligible 候補は `0`。
- 最良near-missでも validation min adjusted pnl `-4.1156`, sum `36.1418`, min trades `5` で、直前hybrid基準の min `81.5352`, sum `396.9782`, min trades `23` から大きく劣化した。
- fixed holdoutも 2024-12 `-24.2766`, 2025-02 `-41.1456` と両方NoTradeに負けた。
- 校正済みEV置換は標準採用しない。trade qualityは平均過大評価を下げるが、entry rankingの主スコアとしては情報を削りすぎる。

## Setup

Source predictions:

- validation OOF: `data/reports/modeling/20260628_141725_selected_trade_quality_hybrid_session_p20_2024_12/predictions_validation_oof_trade_quality_calibrated.parquet`
- 2024-12 apply: `data/reports/modeling/20260628_141725_selected_trade_quality_hybrid_session_p20_2024_12/predictions_apply_trade_quality_calibrated.parquet`
- 2025-02 apply: `data/reports/modeling/20260628_141743_selected_trade_quality_hybrid_session_p20_2025_02/predictions_apply_trade_quality_calibrated.parquet`

Policy:

- policy: `timed_ev`
- long EV column: `pred_trade_quality_long_adjusted_pnl`
- short EV column: `pred_trade_quality_short_adjusted_pnl`
- holding columns: `pred_mlp_long_exit_event_minutes`, `pred_mlp_short_exit_event_minutes`
- max predicted hold: `480`
- validation months: `2024-07,2024-09,2024-11,2025-01`
- evaluation: profit `1.0`, loss `1.20`

Calibrated quality distribution was much lower than the original EV scale. The prior `entry_threshold=15` is unusable after replacement, so the sweep used thresholds `-2,0,1,2,3,4,5`.

## Validation

Top summary:

| entry | short offset | side margin | min rank | eligible | eligible folds | min pnl | sum pnl | min trades | max DD | EV over realized | direction error | max smoothed miss |
|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `5` | `2` | `1` | `0.5` | false | `1` | `-4.1156` | `36.1418` | `5` | `83.7744` | `5.1600` | `0.4341` | `0.6667` |
| `5` | `2` | `0` | `0.5` | false | `0` | `-4.1156` | `35.2312` | `5` | `80.8454` | `5.1815` | `0.4324` | `0.6667` |
| `5` | `2` | `3` | `0.5` | false | `0` | `-11.7426` | `23.8882` | `5` | `76.0852` | `5.2471` | `0.4288` | `0.6667` |
| `5` | `2` | `0` | `0.0` | false | `0` | `-12.5136` | `8.0702` | `5` | `81.5264` | `6.0075` | `0.4225` | `0.6667` |
| `5` | `2` | `1` | `0.0` | false | `0` | `-13.6468` | `6.9370` | `5` | `86.6492` | `6.0053` | `0.4280` | `0.6744` |

Best near-miss fold details:

| month | adjusted pnl | raw pnl | trades | PF | max DD | long trades | short trades | direction error | EV over realized | smoothed miss |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2024-07 | `5.6786` | `8.1400` | `7` | `1.3845` | `8.5284` | `5` | `2` | `0.5714` | `5.0564` | `0.6667` |
| 2024-09 | `-4.1156` | `3.9330` | `7` | `0.9148` | `29.2068` | `2` | `5` | `0.4286` | `7.5659` | `0.4444` |
| 2024-11 | `0.5110` | `44.2070` | `41` | `1.0019` | `83.7744` | `30` | `11` | `0.5366` | `6.2907` | `0.6279` |
| 2025-01 | `34.0678` | `37.5910` | `5` | `2.6116` | `21.1392` | `0` | `5` | `0.2000` | `1.7269` | `0.2857` |

問題点:

- foldごとのtrade数が薄く、2025-01は5 tradesだけで成績が決まる。
- 2024-11は raw pnl が大きくても loss multiplier 後の adjusted pnl がほぼゼロまで縮む。
- EV overestimate平均は下がったが、entry rankingとして必要な収益機会を拾えなくなった。

## Fixed Holdout

Best near-missを固定して 2024-12 / 2025-02 に適用した。

| month | adjusted pnl | raw pnl | trades | win rate | PF | max DD | forced | long trades | short trades | direction error | EV over realized | smoothed miss |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2024-12 | `-24.2766` | `-8.5190` | `63` | `0.4286` | `0.7432` | `34.2464` | `0` | `55` | `8` | `0.2381` | `6.4576` | `0.2769` |
| 2025-02 | `-41.1456` | `-13.2280` | `82` | `0.5244` | `0.7544` | `86.2856` | `0` | `20` | `62` | `0.5488` | `8.2734` | `0.5952` |

2024-12は前回の `min_trade_quality=4` gateの `-4.6296` より悪く、2025-02は前回baseline `+81.8334` から大きく悪化した。校正済みqualityを直接EVに置換すると、平均biasは下がっても、月ごとの有効な取引方向を十分に残せない。

## Decision

- calibrated EV replacementは標準policyへ採用しない。
- selected-trade qualityは、entry EVそのものではなく、過大評価診断、soft penalty、またはfailure classifierの入力として扱う。
- 次に試すなら、`pred_taken_ev - calibrated_quality` の過大評価幅を直接penalty化する。ただしhard gateや全面置換ではなく、validationでtrade数とfold最低PnLを壊さない範囲に限定する。
- さらに進めるなら、実行trade単位の `large_loss`, `wrong_side`, `profit_barrier_miss`, `exit_regret` を分類target化し、EVを一律に下げずに「壊れ方」を分けて学習する。

## Artifacts

- validation sweeps: `data/reports/backtests/selected_trade_quality_ev_replacement_validation/`
- validation summary: `data/reports/backtests/selected_trade_quality_ev_replacement_summary/20260628_142622_model_sweep_summary/`
- fixed tests: `data/reports/backtests/selected_trade_quality_ev_replacement_fixed_tests/`

## Verification

- `PYTHONPATH=src python3 -m unittest tests.test_docs_reports`
- `git diff --check`
