# Entry EV Direction s0.1 Residual Loss Diagnostics

日時: 2026-07-01 23:36 JST
更新日時: 2026-07-01 23:36 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00249の次アクションとして、q99 direction s0.1に残った損失を分解する `scripts/experiments/entry_ev_direction_residual_loss_diagnostics.py` を追加した。
- fixed 2025-03..12のdirection s0.1 tradesをprediction parquetでenrichし、direction risk、replacement quality、EV overestimate、exit capture、profit barrier miss、holding gapを同じtrade rowに並べた。
- q99/floor5は 50 trades / total `-147.3314`。loss tradesは 30 / loss PnL `-554.4084`、win PnL `+407.0770`。
- q99/floor5の損失は `direction_side_inversion_target` が loss PnL `-506.6136`、`exit_capture_failure_target` が loss PnL `-530.4240`、`profit_barrier_miss_loss_target` が loss PnL `-530.6412` を覆う。
- large loss 10件は全てdirection errorかつexit capture failure。したがって残差は「entry direction」と「exit capture」の複合であり、replacement qualityのbinary positive headで吸収する問題ではない。
- `hold_too_long_loss_target` は q99で 11 trades / loss PnL `-322.7892`。短縮すべきexit timingが大きな残差候補。
- 低direction-risk大損も3件 / `-104.5680` あり、特に2025-10 `long/range_normal_vol/ny_overlap` は risk `0.2544` のまま `-55.9080`。direction riskだけでは拾えない。
- 判断: residual loss diagnosticsはaccepted。次は q99 residualに対して、entry側は direction-side inversion head、exit側は hold-too-long / low-capture / profit-barrier miss を分けたexit targetへ進む。現行replacement quality headの再調整は本流にしない。

## Artifacts

- Script: `scripts/experiments/entry_ev_direction_residual_loss_diagnostics.py`
- Test: `tests/test_entry_ev_direction_residual_loss_diagnostics.py`
- Input policy run:
  - `data/reports/backtests/20260701_135349_20260701_entry_ev_direction_inversion_s0p1_fixed2025_03_12_trades_s1/`
- Input predictions:
  - `data/reports/backtests/20260701_141851_20260701_entry_ev_replacement_quality_policy_inputs_s1/enriched_predictions/refit2025_predictions_replacement_quality.parquet`
- Diagnostic run:
  - `data/reports/backtests/20260701_143603_20260701_entry_ev_direction_s0p1_residual_loss_diagnostics_s1/`

## Method

For each selected trade, the script adds:

```text
selected_direction_inversion_risk/source/support
selected_replacement_quality/source/support
selected_ev_overestimate_risk/source
selected_pred_mlp_exit_minutes
selected_time_exit_prob
selected_loss_first_prob
selected fixed 60/240/720m predicted and actual PnL
exit_capture_ratio
```

Residual diagnostic targets:

| target | definition |
|---|---|
| `residual_loss_target` | realized adjusted PnL < 0 |
| `large_loss_target` | adjusted PnL <= `-20` |
| `direction_side_inversion_target` | opposite side oracle PnL > taken side oracle PnL |
| `exit_capture_failure_target` | exit regret >= `20`, or oracle edge >= `5` and capture ratio <= `0.25` |
| `low_capture_with_oracle_edge_target` | oracle edge >= `5` and capture ratio <= `0.25` |
| `forced_exit_loss_target` | forced exit and realized loss |
| `profit_barrier_miss_loss_target` | actual taken profit barrier missed and realized loss |
| `ev_overestimate_loss_target` | predicted taken EV > realized PnL and realized loss |
| `hold_too_long_loss_target` | oracle holding was at least 30 minutes shorter, exit regret positive, and realized loss |
| `low_direction_risk_large_loss_target` | direction risk <= `0.45` and large loss |
| `low_replacement_quality_loss_target` | replacement quality <= `0.40` and realized loss |

This is a diagnostic over stateful replay output. It is not pointwise deletion evidence.

## Candidate Overview

| candidate | trades | total | loss PnL | win PnL | win rate | DD | dir error | exit failure | profit miss | avg pred hold | avg actual hold |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| q99/floor5 | `50` | `-147.3314` | `-554.4084` | `+407.0770` | `0.4000` | `309.7736` | `0.5400` | `0.7400` | `0.6200` | `665.5m` | `845.5m` |
| q95/floor5 | `73` | `-163.3410` | `-726.8160` | `+563.4750` | `0.4521` | `399.0892` | `0.5342` | `0.7397` | `0.5479` | `640.1m` | `652.6m` |

Reading:

- q99 has fewer trades and lower total loss than q95, but lower win rate and still large drawdown.
- Both candidates have extremely high exit capture failure rate. This points to exit modeling, not only entry filtering.

## q99 Flag Summary

| flag | count | share | flag total | flag loss PnL | nonflag loss PnL | large losses |
|---|---:|---:|---:|---:|---:|---:|
| `residual_loss_target` | `30` | `0.6000` | `-554.4084` | `-554.4084` | `0.0000` | `10` |
| `ev_overestimate_loss_target` | `30` | `0.6000` | `-554.4084` | `-554.4084` | `0.0000` | `10` |
| `profit_barrier_miss_loss_target` | `27` | `0.5400` | `-530.6412` | `-530.6412` | `-23.7672` | `10` |
| `exit_capture_failure_target` | `37` | `0.7400` | `-341.5840` | `-530.4240` | `-23.9844` | `10` |
| `direction_side_inversion_target` | `27` | `0.5400` | `-439.8136` | `-506.6136` | `-47.7948` | `10` |
| `large_loss_target` | `10` | `0.2000` | `-387.7368` | `-387.7368` | `-166.6716` | `10` |
| `low_capture_with_oracle_edge_target` | `29` | `0.5800` | `-331.4136` | `-360.1236` | `-194.2848` | `7` |
| `hold_too_long_loss_target` | `11` | `0.2200` | `-322.7892` | `-322.7892` | `-231.6192` | `7` |
| `forced_exit_loss_target` | `4` | `0.0800` | `-152.5164` | `-152.5164` | `-401.8920` | `3` |
| `low_replacement_quality_loss_target` | `7` | `0.1400` | `-113.4396` | `-113.4396` | `-440.9688` | `3` |
| `low_direction_risk_large_loss_target` | `3` | `0.0600` | `-104.5680` | `-104.5680` | `-449.8404` | `3` |

Reading:

- Direction inversion is a strong residual explanation, but not sufficient alone.
- Exit capture failure is even broader and covers all large losses.
- Low replacement quality covers too little. This confirms 00249: binary replacement quality is not the right safety layer.

## Worst q99 Contexts

| direction | context | trades | total | loss PnL | dir error | exit failure | dir risk | repl quality |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| short | down_normal_vol / asia | `4` | `-70.2060` | `-77.9160` | `0.7500` | `1.0000` | `0.6302` | `0.6050` |
| short | down_normal_vol / london | `2` | `-66.8420` | `-77.0520` | `0.5000` | `1.0000` | `0.7258` | `0.7937` |
| long | range_normal_vol / ny_overlap | `4` | `-63.0980` | `-66.1680` | `0.5000` | `0.7500` | `0.2902` | `0.4099` |
| long | down_normal_vol / rollover | `2` | `-60.1368` | `-60.1368` | `1.0000` | `1.0000` | `0.7268` | `0.7778` |
| long | down_normal_vol / london | `1` | `-32.9760` | `-32.9760` | `1.0000` | `1.0000` | `0.6333` | `0.8889` |
| long | range_high_vol / rollover | `1` | `-24.0876` | `-24.0876` | `1.0000` | `1.0000` | `0.7265` | `0.5000` |
| short | down_high_vol / ny_late | `1` | `-23.3556` | `-23.3556` | `1.0000` | `1.0000` | `0.4227` | `0.3541` |

Key residual contexts match the 00248 expectation:

- `short/down_normal_vol/asia`
- `short/down_normal_vol/london`
- `long/range_normal_vol/ny_overlap`
- `long/down_normal_vol/rollover`

## Large Loss Examples

All q99 large losses are direction error + exit capture failure.

| month | side | context | pnl | dir risk | repl quality | exit regret | taken oracle | opposite oracle | holding gap |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| 2025-05 | short | down_normal_vol / london | `-77.0520` | `0.6333` | `0.9206` | `74.9880` | `-2.0640` | `64.2100` | `-3479m` |
| 2025-10 | long | range_normal_vol / ny_overlap | `-55.9080` | `0.2544` | `0.5286` | `59.6680` | `3.7600` | `78.5900` | `-698m` |
| 2025-05 | short | down_normal_vol / asia | `-51.5760` | `0.6333` | `0.9206` | `63.5460` | `11.9700` | `62.8700` | `3886m` |
| 2025-06 | short | range_normal_vol / london | `-37.3404` | `0.6512` | `0.3929` | `38.0334` | `0.6930` | `31.1170` | `-3502m` |
| 2025-05 | long | down_normal_vol / london | `-32.9760` | `0.6333` | `0.8889` | `40.5690` | `7.5930` | `43.7200` | `1164m` |
| 2025-05 | long | down_normal_vol / rollover | `-30.4368` | `0.6354` | `0.8889` | `39.8528` | `9.4160` | `69.7740` | `-194m` |
| 2025-04 | long | down_normal_vol / rollover | `-29.7000` | `0.8182` | `0.6667` | `39.7300` | `10.0300` | `69.1600` | `-194m` |
| 2025-12 | short | range_normal_vol / london | `-25.3044` | `0.4227` | `0.3541` | `34.4074` | `9.1030` | `39.7000` | `-77m` |
| 2025-06 | long | range_high_vol / rollover | `-24.0876` | `0.7265` | `0.5000` | `42.5876` | `18.5000` | `26.8130` | `869m` |
| 2025-12 | short | down_high_vol / ny_late | `-23.3556` | `0.4227` | `0.3541` | `30.6456` | `7.2900` | `24.0300` | `-3226m` |

Important:

- The worst loss has replacement quality `0.9206`, so the 00249 safety layer cannot catch it.
- The 2025-10 `range_normal_vol/ny_overlap` loss has direction risk only `0.2544`, so direction risk alone cannot catch it.
- Several large losses have strongly negative holding gap, meaning the oracle same-side exit was far earlier than the executed exit. This supports a distinct hold-too-long / exit-shortening target.

## Decision

Accepted:

- Residual selected-trade diagnostic script.
- q99/q95 fixed 2025 residual summaries.
- Target flags for direction, exit capture, profit-barrier miss, holding-too-long, and low-risk residual loss.

Not accepted:

- Any pointwise deletion policy from this diagnostic.
- More tuning of replacement positive-quality strength on this fixed window.
- Treating direction risk as a complete residual loss detector.

Standard policy remains NoTrade.

## Next

1. Build a narrow `hold_too_long_loss_target` / `exit_shortening_residual_target` from selected trades and check chronological OOF calibration.
2. Split exit capture into:
   - same-side missed profit with positive oracle edge,
   - forced-exit loss,
   - predicted hold too long vs oracle hold.
3. Keep direction-side inversion as entry-side target, but add explicit low-risk residual cases such as `range_normal_vol/ny_overlap`.
4. Do not use replacement positive-quality as the main safety layer until it is reframed as stay-flat value or replacement regret.
5. Re-evaluate any new exit target through stateful replay, not pointwise deletion.

## Verification

- `python3 -m py_compile scripts/experiments/entry_ev_direction_residual_loss_diagnostics.py tests/test_entry_ev_direction_residual_loss_diagnostics.py`: OK
- `python3 -m unittest tests.test_entry_ev_direction_residual_loss_diagnostics`: OK
- Direction s0.1 fixed 2025 residual diagnostic run: OK
